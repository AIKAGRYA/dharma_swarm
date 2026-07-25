#!/usr/bin/env python3
"""Gate the live wiki -> vector -> governed retrieval seam."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sqlite3
import statistics
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from dharma_swarm.daemon_config import dharma_state_dir
from dharma_swarm.memory_retrieval import GovernedRetrievalEngine, RetrievalQuery

# Calibrated to the manifest-FILTERED concept set: the 2026-07-25 signed
# manifest holds 204 gold+trusted top-level concepts/*.md rows (all on disk).
# The pre-manifest default (257) counted the unfiltered dir and is
# arithmetically unsatisfiable post-filter — a permanently red gate gets
# tuned out. Retune alongside every manifest revision.
DEFAULT_MIN_CONCEPTS = 200


@dataclass(frozen=True)
class WikiVectorGateReceipt:
    state_dir: str
    wiki_concepts_dir: str
    concept_count: int
    indexed_current_count: int
    retrieval_checked: int
    retrieval_passed: int
    p95_latency_ms: float
    max_latency_ms: float
    score: float
    passed: bool
    cases: tuple[dict[str, Any], ...]
    missing_or_stale: tuple[str, ...]

    def to_json(self) -> dict[str, Any]:
        return asdict(self)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state-dir", default=str(dharma_state_dir()))
    parser.add_argument(
        "--wiki-concepts-dir",
        default=str(dharma_state_dir() / "knowledge" / "wiki" / "concepts"),
    )
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--min-concepts", type=int, default=DEFAULT_MIN_CONCEPTS)
    parser.add_argument("--max-retrieval-cases", type=int, default=0)
    parser.add_argument("--max-p95-ms", type=float, default=1200.0)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--receipt-path", default="")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    receipt = run_gate(
        state_dir=Path(args.state_dir).expanduser(),
        wiki_concepts_dir=Path(args.wiki_concepts_dir).expanduser(),
        top_k=max(1, args.top_k),
        min_concepts=max(1, args.min_concepts),
        max_retrieval_cases=max(0, args.max_retrieval_cases),
        max_p95_ms=max(1.0, args.max_p95_ms),
    )
    if args.receipt_path:
        path = Path(args.receipt_path).expanduser()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(receipt.to_json(), indent=2, sort_keys=True), encoding="utf-8")
    if args.json:
        print(json.dumps(receipt.to_json(), indent=2, sort_keys=True))
    else:
        print(render_receipt(receipt))
    return 0 if receipt.passed else 1


def run_gate(
    *,
    state_dir: Path,
    wiki_concepts_dir: Path,
    top_k: int = 5,
    min_concepts: int = DEFAULT_MIN_CONCEPTS,
    max_retrieval_cases: int = 0,
    max_p95_ms: float = 1200.0,
) -> WikiVectorGateReceipt:
    concept_files = _concept_files(wiki_concepts_dir)
    index = _load_index_by_source_file(state_dir / "vectors.db")
    missing_or_stale: list[str] = []
    current_rows: dict[str, dict[str, Any]] = {}
    for path in concept_files:
        digest = _source_digest(path)
        rows = index.get(str(path), ())
        current = next((row for row in rows if row.get("source_digest") == digest), None)
        if current is None:
            missing_or_stale.append(str(path))
        else:
            current_rows[str(path)] = current

    retrieval_files = concept_files
    if max_retrieval_cases:
        retrieval_files = _spread_sample(concept_files, max_retrieval_cases)
    engine = GovernedRetrievalEngine(state_dir=state_dir)
    cases: list[dict[str, Any]] = []
    latencies: list[float] = []
    retrieval_passed = 0
    for path in retrieval_files:
        digest = _source_digest(path)
        query = _query_for_concept(path)
        t0 = time.perf_counter()
        result = engine.retrieve(
            RetrievalQuery(
                text=query,
                top_k=top_k,
                include_content=True,
                record_telemetry=False,
            )
        )
        latency_ms = round((time.perf_counter() - t0) * 1000.0, 3)
        latencies.append(latency_ms)
        matched = None
        for candidate in result.candidates:
            metadata = candidate.metadata
            if (
                str(metadata.get("source_file", "")) == str(path)
                and str(metadata.get("source_digest", "")) == digest
            ):
                matched = candidate
                break
        passed = matched is not None
        if passed:
            retrieval_passed += 1
        top = result.candidates[0] if result.candidates else None
        cases.append(
            {
                "path": str(path),
                "query": query,
                "source_digest": digest,
                "passed": passed,
                "latency_ms": latency_ms,
                "matched_rank": matched.rank if matched else None,
                "top_doc_id": top.doc_id if top else None,
                "top_source": top.source if top else None,
                "top_digest": str(top.metadata.get("source_digest", "")) if top else "",
            }
        )

    concept_count = len(concept_files)
    indexed_current_count = len(current_rows)
    retrieval_checked = len(retrieval_files)
    index_score = 50.0 * indexed_current_count / max(1, concept_count)
    retrieval_score = 40.0 * retrieval_passed / max(1, retrieval_checked)
    p95 = _p95(latencies)
    latency_score = 10.0 if p95 <= max_p95_ms else 0.0
    score = round(index_score + retrieval_score + latency_score, 2)
    passed = (
        concept_count >= min_concepts
        and indexed_current_count == concept_count
        and retrieval_passed == retrieval_checked
        and p95 <= max_p95_ms
    )
    return WikiVectorGateReceipt(
        state_dir=str(state_dir),
        wiki_concepts_dir=str(wiki_concepts_dir),
        concept_count=concept_count,
        indexed_current_count=indexed_current_count,
        retrieval_checked=retrieval_checked,
        retrieval_passed=retrieval_passed,
        p95_latency_ms=p95,
        max_latency_ms=round(max(latencies) if latencies else 0.0, 3),
        score=score,
        passed=passed,
        cases=tuple(cases),
        missing_or_stale=tuple(missing_or_stale[:50]),
    )


def _concept_files(wiki_concepts_dir: Path) -> tuple[Path, ...]:
    if wiki_concepts_dir.name != "concepts" and (wiki_concepts_dir / "concepts").is_dir():
        wiki_concepts_dir = wiki_concepts_dir / "concepts"
    from dharma_swarm.chetana.manifest import load_manifest

    # Only manifest-trusted files are gate-counted (fail-closed: no valid
    # signed manifest → zero concepts → gate fails on min_concepts).
    # verify_content=False on purpose: content drift must stay VISIBLE to the
    # gate's own digest comparison (missing_or_stale) instead of silently
    # shrinking the concept set; ingest refuses drifted bytes regardless.
    manifest = load_manifest(wiki_concepts_dir)
    return tuple(
        sorted(
            path.resolve()
            for path in wiki_concepts_dir.glob("*.md")
            if path.is_file()
            and not path.name.startswith(".")
            and manifest.is_trusted(path, verify_content=False)
        )
    )


def _load_index_by_source_file(db_path: Path) -> dict[str, tuple[dict[str, Any], ...]]:
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True, timeout=2.0)
    conn.row_factory = sqlite3.Row
    rows_by_file: dict[str, list[dict[str, Any]]] = {}
    try:
        rows = conn.execute(
            """
            SELECT vec_doc_id, source, metadata_json, ingestion_time
            FROM memory_retrieval_docs
            WHERE layer = 'source_file'
            """
        ).fetchall()
    finally:
        conn.close()
    for row in rows:
        try:
            metadata = json.loads(row["metadata_json"] or "{}")
        except json.JSONDecodeError:
            metadata = {}
        source_file = str(metadata.get("source_file", ""))
        if not source_file:
            continue
        rows_by_file.setdefault(source_file, []).append(
            {
                "vec_doc_id": int(row["vec_doc_id"]),
                "source": str(row["source"] or ""),
                "source_digest": str(metadata.get("source_digest", "")),
                "ingestion_time": str(row["ingestion_time"] or ""),
            }
        )
    return {key: tuple(value) for key, value in rows_by_file.items()}


def _source_digest(path: Path) -> str:
    return hashlib.sha256(path.read_text(encoding="utf-8").strip().encode("utf-8")).hexdigest()


def _query_for_concept(path: Path) -> str:
    content = path.read_text(encoding="utf-8", errors="replace")
    title = _frontmatter_title(content) or path.stem.replace("-", " ")
    source_terms = path.stem.replace("-", " ")
    return f"{title} {source_terms}".strip()


def _frontmatter_title(content: str) -> str:
    for line in content.splitlines()[:20]:
        match = re.match(r"^title:\s*(.+?)\s*$", line.strip())
        if match:
            return match.group(1).strip().strip('"').strip("'")
        if line.strip() == "---" and content.splitlines().index(line) > 0:
            break
    return ""


def _spread_sample(paths: tuple[Path, ...], count: int) -> tuple[Path, ...]:
    if count <= 0 or len(paths) <= count:
        return paths
    if count == 1:
        return (paths[0],)
    step = (len(paths) - 1) / (count - 1)
    selected = [paths[round(index * step)] for index in range(count)]
    return tuple(dict.fromkeys(selected))


def _p95(values: list[float]) -> float:
    if not values:
        return 0.0
    if len(values) == 1:
        return round(values[0], 3)
    return round(statistics.quantiles(values, n=20, method="inclusive")[18], 3)


def render_receipt(receipt: WikiVectorGateReceipt) -> str:
    status = "PASS" if receipt.passed else "FAIL"
    lines = [
        f"# Wiki Vector Live Gate: {status}",
        "",
        f"- Score: `{receipt.score}/100`",
        f"- Concepts: `{receipt.concept_count}`",
        f"- Current indexed: `{receipt.indexed_current_count}/{receipt.concept_count}`",
        f"- Retrieval: `{receipt.retrieval_passed}/{receipt.retrieval_checked}`",
        f"- p95 latency ms: `{receipt.p95_latency_ms}`",
        f"- Max latency ms: `{receipt.max_latency_ms}`",
    ]
    if receipt.missing_or_stale:
        lines.append(f"- Missing/stale sample: `{receipt.missing_or_stale[:5]}`")
    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(main())
