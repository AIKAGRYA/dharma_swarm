#!/usr/bin/env python3
"""Run a deterministic 100-case live sweep over the compact memory index."""

from __future__ import annotations

import argparse
import json
import re
import signal
import sqlite3
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from dharma_swarm.memory_retrieval import GovernedRetrievalEngine, RetrievalQuery


CURATED_LAYERS = ("memory_context", "memory_graph", "source_file")
DEFAULT_CASE_COUNT = 100
DEFAULT_NEGATIVE_COUNT = 6
TOKEN_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_]*")
HEX_RE = re.compile(r"^[0-9a-f]{8,}$", re.IGNORECASE)
SHORT_SIGNAL_TERMS = {"ai", "go", "js", "mi", "py", "qa", "rv", "ts", "ui", "ux", "vs"}
STOPWORDS = {
    "agent",
    "agents",
    "and",
    "claude",
    "context",
    "dharma",
    "docs",
    "env",
    "file",
    "for",
    "from",
    "graph",
    "import",
    "insert",
    "json",
    "jsonl",
    "memory",
    "of",
    "observation",
    "path",
    "python",
    "python3",
    "resolve",
    "script",
    "scripts",
    "str",
    "swarm",
    "sys",
    "the",
    "source",
    "text",
    "to",
    "users",
    "usr",
    "dhyana",
}
RELATION_STOPWORDS = STOPWORDS - {"dharma", "swarm"}


@dataclass(frozen=True)
class BroadCase:
    name: str
    query: str
    case_kind: str
    expected_source: str = ""
    expected_layer: str | None = None
    expect_empty: bool = False
    max_ms: float = 1200.0
    forbid_source_prefixes: tuple[str, ...] = ("evolution_archive:",)


@dataclass(frozen=True)
class IndexedRow:
    vec_doc_id: int
    source: str
    layer: str
    content: str


class QueryTimeout(Exception):
    pass


def _alarm(_signum: int, _frame: object) -> None:
    raise QueryTimeout()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state-dir", type=Path, default=Path.home() / ".dharma")
    parser.add_argument("--case-count", type=int, default=DEFAULT_CASE_COUNT)
    parser.add_argument("--negative-count", type=int, default=DEFAULT_NEGATIVE_COUNT)
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--timeout-s", type=int, default=8)
    parser.add_argument("--fail-under", type=float, default=100.0)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    signal.signal(signal.SIGALRM, _alarm)
    state_dir = args.state_dir.expanduser()
    rows = load_indexed_rows(state_dir)
    cases = build_cases(
        rows,
        case_count=args.case_count,
        negative_count=args.negative_count,
    )
    engine = GovernedRetrievalEngine(state_dir=state_dir)
    result_rows = [run_case(engine, case, top_k=args.top_k, timeout_s=args.timeout_s) for case in cases]
    score = score_rows(result_rows)
    payload = {
        "schema_version": 1,
        "state_dir": str(state_dir),
        "score": score,
        "passed": score >= args.fail_under,
        "case_count": len(result_rows),
        "pass_count": sum(1 for row in result_rows if row["passed"]),
        "top_k": args.top_k,
        "rows": result_rows,
        "coverage": coverage_summary(cases),
    }
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(render_text(payload))
    return 0 if score >= args.fail_under else 1


def load_indexed_rows(state_dir: Path) -> list[IndexedRow]:
    db_path = Path(state_dir).expanduser() / "vectors.db"
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            """
            SELECT vec_doc_id, source, layer, content
            FROM memory_retrieval_docs
            WHERE valid_until IS NULL
              AND layer IN ('memory_context', 'memory_graph', 'source_file')
            ORDER BY layer, vec_doc_id
            """
        ).fetchall()
    finally:
        conn.close()
    return [
        IndexedRow(
            vec_doc_id=int(row["vec_doc_id"]),
            source=str(row["source"] or ""),
            layer=str(row["layer"] or ""),
            content=str(row["content"] or ""),
        )
        for row in rows
    ]


def build_cases(
    rows: list[IndexedRow],
    *,
    case_count: int = DEFAULT_CASE_COUNT,
    negative_count: int = DEFAULT_NEGATIVE_COUNT,
) -> tuple[BroadCase, ...]:
    if case_count <= negative_count:
        raise ValueError("case_count must be greater than negative_count")
    positive_target = case_count - negative_count
    positives = _positive_cases(rows, positive_target)
    negatives = _negative_cases(negative_count)
    return (*positives, *negatives)


def _positive_cases(rows: list[IndexedRow], positive_target: int) -> tuple[BroadCase, ...]:
    by_layer = {layer: [row for row in rows if row.layer == layer] for layer in CURATED_LAYERS}
    source_target = min(
        len(by_layer["source_file"]),
        min(20, max(1 if by_layer["source_file"] else 0, positive_target // 4)),
    )
    remaining_after_sources = max(0, positive_target - source_target)
    memory_context_target = min(len(by_layer["memory_context"]), remaining_after_sources // 2)
    memory_graph_target = min(
        len(by_layer["memory_graph"]),
        remaining_after_sources - memory_context_target,
    )
    base_quota = {
        "memory_context": memory_context_target,
        "memory_graph": memory_graph_target,
        "source_file": source_target,
    }
    remaining = max(0, positive_target - sum(base_quota.values()))
    for layer in ("memory_context", "memory_graph", "source_file"):
        available = max(0, len(by_layer[layer]) - base_quota[layer])
        take = min(available, remaining)
        base_quota[layer] += take
        remaining -= take
        if remaining <= 0:
            break

    cases: list[BroadCase] = []
    for layer in CURATED_LAYERS:
        for ordinal, row in enumerate(_spread_sample(by_layer[layer], base_quota[layer])):
            query = query_for_row(row, ordinal=ordinal)
            cases.append(
                BroadCase(
                    name=f"{layer}_{row.vec_doc_id}_{ordinal:02d}",
                    query=query,
                    case_kind="live_sidecar_expected_source",
                    expected_source=row.source,
                    expected_layer=row.layer,
                )
            )
    return tuple(cases[:positive_target])


def _negative_cases(count: int) -> tuple[BroadCase, ...]:
    seeds = (
        "xyzzq impossible memory topic lunar cheese invoice",
        "corr-2099-12-never-created-sentinel-handle",
        "nonexistent obsidian marmalade gateway qqqnotindexed",
        "ultramarine stapler economy absentrow zxqwbblplk",
        "moon glass checksum madeofnothing neverindexed",
        "banana telescope qxjvnotreal zzmissingtoken",
        "crystal ledger fakehandle qqqvoidtopic",
        "zephyr checksum impossible zzzmissingtopic",
    )
    return tuple(
        BroadCase(
            name=f"negative_{index:02d}",
            query=seed,
            case_kind="adversarial_negative",
            expect_empty=True,
            max_ms=1200.0,
        )
        for index, seed in enumerate(seeds[: max(0, count)])
    )


def _spread_sample(rows: list[IndexedRow], count: int) -> tuple[IndexedRow, ...]:
    if count <= 0 or not rows:
        return ()
    if count >= len(rows):
        return tuple(rows)
    if count == 1:
        return (rows[0],)
    return tuple(rows[round(index * (len(rows) - 1) / (count - 1))] for index in range(count))


def query_for_row(row: IndexedRow, *, ordinal: int = 0) -> str:
    source_terms = _source_terms(row.source)
    title_terms = _ordered_terms(_title_text(row.content))
    body_terms = _ordered_terms(_body_text(row.content))

    if row.source.startswith("memory_relation:"):
        relation_terms = _relation_source_terms(row.source)
        content_relation_terms = _relation_content_terms(row.content)
        terms = [
            *content_relation_terms[:14],
            *relation_terms[:14],
            *source_terms[:8],
            *title_terms[:6],
            *body_terms[:4],
        ]
    elif row.layer == "source_file":
        source_file_terms = _source_file_terms(row.source)
        terms = [*source_file_terms[:10], *title_terms[:8], *body_terms[:6], *source_terms[:8]]
    elif row.source.startswith("memory_graph:"):
        identity_terms = [*title_terms[:8], *source_terms[:8]]
        terms = [*identity_terms, *body_terms[: max(0, 6 - len(dict.fromkeys(identity_terms)))]]
    elif ordinal % 3 == 0:
        terms = [*title_terms[:8], *body_terms[:6], *source_terms[:3]]
    elif ordinal % 3 == 1:
        terms = [*source_terms[:6], *title_terms[:8], *body_terms[:4]]
    else:
        terms = [*title_terms[:5], *source_terms[:5], *body_terms[:6]]

    out: list[str] = []
    for term in terms:
        if term in out:
            continue
        out.append(term)
        if len(out) >= 12:
            break
    if len(out) < 3:
        for term in _ordered_terms(row.content):
            if term not in out:
                out.append(term)
            if len(out) >= 8:
                break
    return " ".join(out)


def _title_text(content: str) -> str:
    for pattern in (
        r"Observation:\s*(.+?)(?:\nSource file:|\n|$)",
        r"Memory graph entity:\s*(.+?)(?:\n|$)",
        r'"goal"\s*:\s*"([^"]+)"',
        r"^#\s+(.+)$",
        r'^title:\s*"?([^"\n]+)"?',
    ):
        match = re.search(pattern, content, flags=re.MULTILINE | re.DOTALL)
        if match:
            return match.group(1)
    return content[:240]


def _body_text(content: str) -> str:
    bullets = re.findall(r"^\s*[-*]\s+(.+)$", content, flags=re.MULTILINE)
    if bullets:
        return " ".join(bullets[:3])
    lines = [line.strip() for line in content.splitlines() if line.strip()]
    return " ".join(lines[:5])


def _source_terms(source: str) -> list[str]:
    without_prefix = source.split(":", 1)[-1]
    without_hash = re.sub(r":[0-9a-f]{8,}$", "", without_prefix, flags=re.IGNORECASE)
    return _ordered_terms(without_hash)


def _source_file_terms(source: str) -> list[str]:
    terms = _source_terms(source)
    tail = terms[-8:]
    return [*tail, *terms]


def _relation_source_terms(source: str) -> list[str]:
    parts = source.split(":")
    if len(parts) < 4 or parts[0] != "memory_relation":
        return _source_terms(source)
    from_terms = _ordered_terms(parts[1], stopwords=RELATION_STOPWORDS)
    predicate_terms = _ordered_terms(parts[2], stopwords=RELATION_STOPWORDS)
    to_terms = _ordered_terms(parts[3], stopwords=RELATION_STOPWORDS)
    return [*predicate_terms, *to_terms, *from_terms]


def _relation_content_terms(content: str) -> list[str]:
    match = re.search(
        r"Memory graph relation:\s*(?P<from>.+?)\s+--(?P<predicate>.+?)-->\s*(?P<to>.+?)(?:\n|$)",
        content,
        flags=re.MULTILINE | re.DOTALL,
    )
    if not match:
        return []
    return [
        *_ordered_terms(match.group("predicate"), stopwords=RELATION_STOPWORDS),
        *_ordered_terms(match.group("to"), stopwords=RELATION_STOPWORDS),
        *_ordered_terms(match.group("from"), stopwords=RELATION_STOPWORDS),
    ]


def _ordered_terms(text: str, *, stopwords: set[str] = STOPWORDS) -> list[str]:
    seen: set[str] = set()
    terms: list[str] = []
    normalized = text.replace("_", " ").replace("-", " ").replace("/", " ")
    for token in TOKEN_RE.findall(normalized.lower()):
        if (len(token) <= 2 and token not in SHORT_SIGNAL_TERMS) or token in stopwords or HEX_RE.match(token):
            continue
        token = _stem(token)
        if token in seen:
            continue
        seen.add(token)
        terms.append(token)
    return terms


def _stem(token: str) -> str:
    if token.endswith("ing") and len(token) > 5:
        return token[:-3]
    if token.endswith("ed") and len(token) > 4:
        return token[:-2]
    if token.endswith("es") and len(token) > 4:
        return token[:-2]
    if token.endswith("s") and len(token) > 4:
        return token[:-1]
    return token


def run_case(
    engine: GovernedRetrievalEngine,
    case: BroadCase,
    *,
    top_k: int,
    timeout_s: int,
) -> dict[str, Any]:
    started = time.perf_counter()
    try:
        signal.alarm(timeout_s)
        result = engine.retrieve(RetrievalQuery(text=case.query, top_k=top_k, include_content=True))
        signal.alarm(0)
    except QueryTimeout:
        signal.alarm(0)
        return {
            **asdict(case),
            "passed": False,
            "elapsed_ms": round((time.perf_counter() - started) * 1000.0, 3),
            "failure": "timeout",
            "top_source": "",
            "top_layer": "",
            "hit_rank": None,
            "result_count": 0,
        }

    elapsed_ms = float(result.timings_ms.get("total") or round((time.perf_counter() - started) * 1000.0, 3))
    candidates = result.candidates
    top = candidates[0] if candidates else None
    top_source = top.source if top else ""
    top_layer = top.layer if top else ""
    failures: list[str] = []
    hit_rank: int | None = None

    if case.expect_empty:
        if candidates:
            failures.append("expected_empty")
    else:
        for candidate in candidates:
            if candidate.source == case.expected_source and candidate.layer == case.expected_layer:
                hit_rank = candidate.rank
                break
        if hit_rank is None:
            failures.append("expected_source_not_in_top_k")
        if any((candidate.source or "").startswith(case.forbid_source_prefixes) for candidate in candidates):
            failures.append("forbidden_source_in_candidates")

    if elapsed_ms > case.max_ms:
        failures.append(f"slow:{elapsed_ms:.1f}>{case.max_ms:.1f}")

    return {
        **asdict(case),
        "passed": not failures,
        "elapsed_ms": round(elapsed_ms, 3),
        "failure": ",".join(failures),
        "top_source": top_source,
        "top_layer": top_layer,
        "hit_rank": hit_rank,
        "result_count": len(candidates),
    }


def score_rows(rows: list[dict[str, Any]]) -> float:
    if not rows:
        return 0.0
    return round((sum(1 for row in rows if row["passed"]) / len(rows)) * 100.0, 1)


def coverage_summary(cases: tuple[BroadCase, ...]) -> dict[str, Any]:
    by_kind: dict[str, int] = {}
    by_layer: dict[str, int] = {}
    for case in cases:
        by_kind[case.case_kind] = by_kind.get(case.case_kind, 0) + 1
        layer = case.expected_layer or "negative"
        by_layer[layer] = by_layer.get(layer, 0) + 1
    return {"by_kind": by_kind, "by_layer": by_layer}


def render_text(payload: dict[str, Any]) -> str:
    lines = [
        f"Broad memory retrieval sweep: {payload['score']}/100",
        f"Passed {payload['pass_count']}/{payload['case_count']} at recall@{payload['top_k']}",
        f"Coverage: {json.dumps(payload['coverage'], sort_keys=True)}",
        "",
    ]
    for row in payload["rows"]:
        if row["passed"]:
            continue
        lines.append(
            f"FAIL {row['name']} kind={row['case_kind']} hit_rank={row['hit_rank']} "
            f"top_layer={row['top_layer']} top_source={row['top_source']} failure={row['failure']} "
            f"query={row['query']!r}"
        )
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    raise SystemExit(main())
