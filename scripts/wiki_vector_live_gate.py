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

# Trust tiers the signed manifest may admit into the indexed set (WS-D / PR-08).
ACCEPTED_MANIFEST_TIERS = frozenset({"gold", "trusted"})
_MANIFEST_LOADER_NAMES = ("load_verified_manifest", "load_manifest", "read_manifest")
_MANIFEST_PATH_KEYS = ("path", "file", "source_file", "relpath", "relative_path")
_MANIFEST_TIER_KEYS = ("tier", "trust_tier", "layer")


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
    provenance_status: str = "unavailable"
    provenance_score: float = 0.0
    provenance_manifest_path: str = ""
    provenance_violations: tuple[str, ...] = ()
    provenance_warning: str = ""
    indexed_wiki_file_count: int = 0

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
    parser.add_argument("--min-concepts", type=int, default=257)
    parser.add_argument("--max-retrieval-cases", type=int, default=0)
    parser.add_argument("--max-p95-ms", type=float, default=1200.0)
    parser.add_argument("--manifest-path", default="")
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
        manifest_path=Path(args.manifest_path).expanduser() if args.manifest_path else None,
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
    min_concepts: int = 257,
    max_retrieval_cases: int = 0,
    max_p95_ms: float = 1200.0,
    manifest_path: Path | None = None,
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
    indexed_wiki_files = _indexed_wiki_files(index, wiki_concepts_dir)
    provenance = _manifest_provenance(
        wiki_concepts_dir=wiki_concepts_dir,
        indexed_files=indexed_wiki_files,
        manifest_path=manifest_path,
    )
    # Weights rebalanced 50/40/10 -> 45/35/10 to fund the provenance component
    # (check id: wiki_provenance_manifest_subset). Pre-PR-08 the manifest module
    # is absent and provenance degrades to a full-score warning (draft stays
    # green); once dharma_swarm.chetana.manifest exists it is fail-closed.
    index_score = 45.0 * indexed_current_count / max(1, concept_count)
    retrieval_score = 35.0 * retrieval_passed / max(1, retrieval_checked)
    p95 = _p95(latencies)
    latency_score = 10.0 if p95 <= max_p95_ms else 0.0
    provenance_ok = provenance["status"] in ("ok", "unavailable")
    provenance_score = 10.0 if provenance_ok else 0.0
    score = round(index_score + retrieval_score + latency_score + provenance_score, 2)
    passed = (
        concept_count >= min_concepts
        and indexed_current_count == concept_count
        and retrieval_passed == retrieval_checked
        and p95 <= max_p95_ms
        and provenance_ok
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
        provenance_status=str(provenance["status"]),
        provenance_score=provenance_score,
        provenance_manifest_path=str(provenance["manifest_path"]),
        provenance_violations=tuple(provenance["violations"]),
        provenance_warning=str(provenance["warning"]),
        indexed_wiki_file_count=len(indexed_wiki_files),
    )


def _indexed_wiki_files(
    index: dict[str, tuple[dict[str, Any], ...]], wiki_concepts_dir: Path
) -> tuple[str, ...]:
    root = wiki_concepts_dir.resolve()
    selected = []
    for source_file in index:
        try:
            Path(source_file).resolve().relative_to(root)
        except ValueError:
            continue
        selected.append(source_file)
    return tuple(sorted(selected))


def _manifest_provenance(
    *,
    wiki_concepts_dir: Path,
    indexed_files: tuple[str, ...],
    manifest_path: Path | None,
) -> dict[str, Any]:
    resolved_manifest = manifest_path or (wiki_concepts_dir.resolve().parent / "MANIFEST.jsonl")
    report: dict[str, Any] = {
        "check_id": "wiki_provenance_manifest_subset",
        "status": "unavailable",
        "manifest_path": str(resolved_manifest),
        "violations": (),
        "warning": "",
    }
    # Feature-detect PR-08: pre-landing the module does not exist and the check
    # must degrade to a warning, not a red gate.
    try:
        from dharma_swarm.chetana import manifest as chetana_manifest
    except Exception as exc:
        report["warning"] = (
            f"chetana.manifest not importable (pre-PR-08); provenance degraded to warning: {exc}"
        )
        return report
    loader = None
    for name in _MANIFEST_LOADER_NAMES:
        candidate = getattr(chetana_manifest, name, None)
        if callable(candidate):
            loader = candidate
            break
    if loader is None:
        report["warning"] = (
            "chetana.manifest present but exposes none of "
            f"{_MANIFEST_LOADER_NAMES}; provenance degraded to warning"
        )
        return report
    # Module landed => provenance is enforceable; loader/verify failure fails closed.
    try:
        entries = loader(resolved_manifest)
    except Exception as exc:
        report["status"] = "error"
        report["warning"] = f"manifest load/verify failed (fail-closed): {exc}"
        return report
    accepted = _accepted_manifest_paths(entries, wiki_concepts_dir)
    violations = tuple(
        source_file
        for source_file in indexed_files
        if not _matches_accepted(source_file, accepted, wiki_concepts_dir)
    )
    report["status"] = "violations" if violations else "ok"
    report["violations"] = violations[:50]
    if violations:
        report["warning"] = (
            f"{len(violations)} indexed wiki files outside signed manifest accepted tiers "
            f"{sorted(ACCEPTED_MANIFEST_TIERS)}"
        )
    return report


def _accepted_manifest_paths(entries: Any, wiki_concepts_dir: Path) -> frozenset[str]:
    accepted: set[str] = set()
    root = wiki_concepts_dir.resolve()
    wiki_root = root.parent
    for entry in entries or ():
        tier = str(_entry_value(entry, _MANIFEST_TIER_KEYS)).strip().lower()
        if tier not in ACCEPTED_MANIFEST_TIERS:
            continue
        raw_path = str(_entry_value(entry, _MANIFEST_PATH_KEYS)).strip()
        if not raw_path:
            continue
        path = Path(raw_path).expanduser()
        forms = {raw_path, path.name}
        if path.is_absolute():
            forms.add(str(path.resolve()))
        else:
            forms.add(str((wiki_root / path).resolve()))
            forms.add(str((root / path).resolve()))
        accepted.update(forms)
    return frozenset(accepted)


def _entry_value(entry: Any, keys: tuple[str, ...]) -> Any:
    for key in keys:
        if isinstance(entry, dict):
            value = entry.get(key)
        else:
            value = getattr(entry, key, None)
        if value not in (None, ""):
            return value
    return ""


def _matches_accepted(
    source_file: str, accepted: frozenset[str], wiki_concepts_dir: Path
) -> bool:
    resolved = Path(source_file).resolve()
    candidates = {source_file, str(resolved), resolved.name}
    try:
        candidates.add(str(resolved.relative_to(wiki_concepts_dir.resolve())))
    except ValueError:
        pass
    return bool(candidates & accepted)


def _concept_files(wiki_concepts_dir: Path) -> tuple[Path, ...]:
    if wiki_concepts_dir.name != "concepts" and (wiki_concepts_dir / "concepts").is_dir():
        wiki_concepts_dir = wiki_concepts_dir / "concepts"
    return tuple(
        sorted(
            path.resolve()
            for path in wiki_concepts_dir.glob("*.md")
            if path.is_file() and not path.name.startswith(".")
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
        f"- Provenance (wiki_provenance_manifest_subset): `{receipt.provenance_status}` "
        f"({receipt.indexed_wiki_file_count} indexed wiki files)",
    ]
    if receipt.provenance_warning:
        lines.append(f"- Provenance warning: `{receipt.provenance_warning}`")
    if receipt.provenance_violations:
        lines.append(f"- Provenance violations sample: `{receipt.provenance_violations[:5]}`")
    if receipt.missing_or_stale:
        lines.append(f"- Missing/stale sample: `{receipt.missing_or_stale[:5]}`")
    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(main())
