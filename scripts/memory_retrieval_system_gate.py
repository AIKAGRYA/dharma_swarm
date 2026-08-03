#!/usr/bin/env python3
"""Score the live memory retrieval system across quality, health, and coverage."""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from dharma_swarm.memory_retrieval import GovernedRetrievalEngine
from scripts import memory_retrieval_broad_sweep as broad
from scripts import memory_retrieval_live_gate as live


REQUIRED_TRIGGERS = (
    "memory_retrieval_vec_ad",
    "memory_retrieval_vec_ai",
    "memory_retrieval_vec_au_delete_old",
    "memory_retrieval_vec_au_insert_new",
    "memory_retrieval_vec_au_refresh",
)


@dataclass(frozen=True)
class GateCheck:
    name: str
    score: float
    max_score: float
    passed: bool
    summary: str
    details: dict[str, Any]

    def to_json(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["score"] = round(self.score, 3)
        payload["max_score"] = round(self.max_score, 3)
        return payload


def run_system_gate(
    *,
    state_dir: Path,
    top_k: int = 1,
    negative_count: int = broad.DEFAULT_NEGATIVE_COUNT,
    timeout_s: int = 8,
    source_file_target: int = 256,
    memory_context_target: int = 100,
    memory_graph_target: int = 100,
    run_live: bool = True,
) -> dict[str, Any]:
    started = time.perf_counter()
    state_dir = Path(state_dir).expanduser()
    health = load_index_health(state_dir)
    telemetry_cursor = load_telemetry_cursor(state_dir)
    checks: list[GateCheck] = []

    rows = broad.load_indexed_rows(state_dir)
    broad_rows = run_broad_rows(
        state_dir=state_dir,
        rows=rows,
        top_k=top_k,
        negative_count=negative_count,
        timeout_s=timeout_s,
    )
    checks.append(
        score_broad_recall(
            rows,
            broad_rows,
            top_k=top_k,
            negative_count=negative_count,
            max_score=30.0,
        )
    )

    live_rows: list[dict[str, Any]] = []
    if run_live:
        live_rows = run_live_rows(state_dir=state_dir, top_k=top_k, timeout_s=timeout_s)
        checks.append(score_live_recall(live_rows, max_score=20.0))
    else:
        # A requested skip is neutral: excluded from the attainable score so
        # --skip-live can still reach passed=True, and marked in the payload.
        checks.append(
            GateCheck(
                name="live_semantic_gate",
                score=0.0,
                max_score=0.0,
                passed=True,
                summary="skipped (excluded from attainable score)",
                details={"skipped": True},
            )
        )

    checks.append(score_index_health(health, max_score=15.0))
    checks.append(
        score_source_coverage(
            health,
            source_file_target=source_file_target,
            memory_context_target=memory_context_target,
            memory_graph_target=memory_graph_target,
            max_score=15.0,
        )
    )
    checks.append(score_latency([*broad_rows, *live_rows], max_score=10.0))
    telemetry = load_telemetry_health(state_dir, after_id=telemetry_cursor)
    checks.append(
        score_telemetry(
            telemetry,
            expected_min_logs=len(broad_rows) + len(live_rows),
            max_score=10.0,
        )
    )

    score = round(sum(check.score for check in checks), 1)
    max_score = round(sum(check.max_score for check in checks), 1)
    return {
        "schema_version": 1,
        "state_dir": str(state_dir),
        "score": score,
        "max_score": max_score,
        "passed": score >= max_score,
        "elapsed_ms": round((time.perf_counter() - started) * 1000.0, 3),
        "checks": [check.to_json() for check in checks],
        "index_health": health,
        "telemetry": telemetry,
        "broad": {
            "case_count": len(broad_rows),
            "pass_count": sum(1 for row in broad_rows if row["passed"]),
            "score": broad.score_rows(broad_rows),
            "top_k": top_k,
            "coverage": broad.coverage_summary(
                broad.build_cases(
                    rows,
                    case_count=len(rows) + max(0, negative_count),
                    negative_count=negative_count,
                )
            )
            if rows
            else {"by_kind": {}, "by_layer": {}},
            "failures": [row for row in broad_rows if not row["passed"]],
        },
        "live": {
            "case_count": len(live_rows),
            "pass_count": sum(1 for row in live_rows if row["passed"]),
            "score": live.score_rows(live_rows) if live_rows else 0.0,
            "failures": [row for row in live_rows if not row["passed"]],
        },
    }


def run_broad_rows(
    *,
    state_dir: Path,
    rows: list[broad.IndexedRow],
    top_k: int,
    negative_count: int,
    timeout_s: int,
) -> list[dict[str, Any]]:
    if not rows:
        return []
    cases = broad.build_cases(
        rows,
        case_count=len(rows) + max(0, negative_count),
        negative_count=negative_count,
    )
    broad.install_alarm_handler()
    engine = GovernedRetrievalEngine(state_dir=state_dir)
    return [broad.run_case(engine, case, top_k=top_k, timeout_s=timeout_s) for case in cases]


def run_live_rows(*, state_dir: Path, top_k: int, timeout_s: int) -> list[dict[str, Any]]:
    live.install_alarm_handler()
    engine = GovernedRetrievalEngine(state_dir=state_dir)
    return [live.run_case(engine, case, top_k=top_k, timeout_s=timeout_s) for case in live.LIVE_CASES]


def load_index_health(state_dir: Path) -> dict[str, Any]:
    db_path = Path(state_dir).expanduser() / "vectors.db"
    health: dict[str, Any] = {
        "db_path": str(db_path),
        "db_exists": db_path.exists(),
        "db_bytes": db_path.stat().st_size if db_path.exists() else 0,
        "vec_document_sequence": 0,
        "max_curated_vec_doc_id": None,
        "sidecar_rows": 0,
        "sidecar_counts": {},
        "sidecar_min_doc_id": None,
        "sidecar_max_doc_id": None,
        "sidecar_freshness_delta": None,
        "triggers": [],
        "missing_triggers": list(REQUIRED_TRIGGERS),
        "fts_queryable": False,
    }
    if not db_path.exists():
        return health
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        seq = conn.execute(
            "SELECT seq FROM sqlite_sequence WHERE name = 'vec_documents'"
        ).fetchone()
        if seq is not None:
            health["vec_document_sequence"] = int(seq["seq"] or 0)
        max_curated = conn.execute(
            """
            SELECT max(id) AS max_doc_id
            FROM vec_documents
            WHERE layer IN ('memory_context', 'memory_graph', 'source_file')
            """
        ).fetchone()
        if max_curated is not None:
            health["max_curated_vec_doc_id"] = max_curated["max_doc_id"]

        counts = conn.execute(
            """
            SELECT layer, count(*) AS row_count
            FROM memory_retrieval_docs
            WHERE valid_until IS NULL
            GROUP BY layer
            """
        ).fetchall()
        health["sidecar_counts"] = {
            str(row["layer"]): int(row["row_count"] or 0) for row in counts
        }
        health["sidecar_rows"] = sum(health["sidecar_counts"].values())
        bounds = conn.execute(
            """
            SELECT min(vec_doc_id) AS min_doc_id, max(vec_doc_id) AS max_doc_id
            FROM memory_retrieval_docs
            WHERE valid_until IS NULL
            """
        ).fetchone()
        if bounds is not None:
            health["sidecar_min_doc_id"] = bounds["min_doc_id"]
            health["sidecar_max_doc_id"] = bounds["max_doc_id"]
            if bounds["max_doc_id"] is not None and health["max_curated_vec_doc_id"] is not None:
                health["sidecar_freshness_delta"] = max(
                    0,
                    int(health["max_curated_vec_doc_id"]) - int(bounds["max_doc_id"]),
                )

        trigger_rows = conn.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type = 'trigger'
              AND name LIKE 'memory_retrieval_%'
            ORDER BY name
            """
        ).fetchall()
        triggers = [str(row["name"]) for row in trigger_rows]
        health["triggers"] = triggers
        health["missing_triggers"] = [
            name for name in REQUIRED_TRIGGERS if name not in set(triggers)
        ]

        try:
            conn.execute("SELECT rowid FROM memory_retrieval_fts LIMIT 1").fetchone()
            health["fts_queryable"] = True
        except sqlite3.Error:
            health["fts_queryable"] = False
    finally:
        conn.close()
    return health


def load_telemetry_cursor(state_dir: Path) -> int:
    db_path = Path(state_dir).expanduser() / "vectors.db"
    if not db_path.exists():
        return 0
    conn = sqlite3.connect(db_path)
    try:
        table = conn.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type = 'table'
              AND name = 'memory_retrieval_query_log'
            """
        ).fetchone()
        if table is None:
            return 0
        row = conn.execute("SELECT max(id) FROM memory_retrieval_query_log").fetchone()
        return int(row[0] or 0) if row is not None else 0
    finally:
        conn.close()


def load_telemetry_health(state_dir: Path, *, after_id: int = 0) -> dict[str, Any]:
    db_path = Path(state_dir).expanduser() / "vectors.db"
    health: dict[str, Any] = {
        "table_exists": False,
        "after_id": after_id,
        "new_rows": 0,
        "missing_core_fields": 0,
        "empty_result_rows": 0,
        "degraded_rows": 0,
        "p95_total_ms": None,
        "max_total_ms": None,
        "latest_query_time": None,
    }
    if not db_path.exists():
        return health
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        table = conn.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type = 'table'
              AND name = 'memory_retrieval_query_log'
            """
        ).fetchone()
        if table is None:
            return health
        health["table_exists"] = True
        rows = conn.execute(
            """
            SELECT query_time, query_hash, query_preview, result_count,
                   total_ms, degraded_reasons_json
            FROM memory_retrieval_query_log
            WHERE id > ?
            ORDER BY id
            """,
            (after_id,),
        ).fetchall()
        totals = sorted(
            float(row["total_ms"])
            for row in rows
            if row["total_ms"] is not None
        )
        health["new_rows"] = len(rows)
        health["missing_core_fields"] = sum(
            1
            for row in rows
            if not str(row["query_hash"] or "")
            or not str(row["query_preview"] or "")
            or row["total_ms"] is None
        )
        health["empty_result_rows"] = sum(1 for row in rows if int(row["result_count"] or 0) == 0)
        health["degraded_rows"] = sum(
            1
            for row in rows
            if str(row["degraded_reasons_json"] or "[]") not in ("[]", "")
        )
        if totals:
            health["p95_total_ms"] = round(percentile(totals, 0.95), 3)
            health["max_total_ms"] = round(max(totals), 3)
        if rows:
            health["latest_query_time"] = rows[-1]["query_time"]
    finally:
        conn.close()
    return health


def score_broad_recall(
    indexed_rows: list[broad.IndexedRow],
    rows: list[dict[str, Any]],
    *,
    top_k: int,
    negative_count: int,
    max_score: float,
) -> GateCheck:
    score = broad.score_rows(rows)
    expected_cases = len(indexed_rows) + max(0, negative_count) if indexed_rows else 0
    full_coverage = bool(rows) and len(rows) == expected_cases
    earned = max_score * (score / 100.0)
    passed = score >= 100.0 and full_coverage
    if not full_coverage:
        earned = min(earned, max_score * 0.8)
    return GateCheck(
        name="compact_sidecar_exhaustive_recall",
        score=earned,
        max_score=max_score,
        passed=passed,
        summary=f"{sum(1 for row in rows if row['passed'])}/{len(rows)} at recall@{top_k}",
        details={
            "indexed_rows": len(indexed_rows),
            "case_count": len(rows),
            "expected_cases": expected_cases,
            "score": score,
            "full_coverage": full_coverage,
            "top_k": top_k,
            "failures": [row["name"] for row in rows if not row["passed"]],
        },
    )


def score_live_recall(rows: list[dict[str, Any]], *, max_score: float) -> GateCheck:
    score = live.score_rows(rows)
    earned = max_score * (score / 100.0)
    return GateCheck(
        name="live_semantic_gate",
        score=earned,
        max_score=max_score,
        passed=score >= 100.0,
        summary=f"{sum(1 for row in rows if row['passed'])}/{len(rows)} live cases",
        details={
            "score": score,
            "failures": [row["name"] for row in rows if not row["passed"]],
        },
    )


def score_index_health(health: dict[str, Any], *, max_score: float) -> GateCheck:
    earned = 0.0
    details: dict[str, Any] = {}
    if health["db_exists"] and health["db_bytes"] > 0 and health["vec_document_sequence"] > 0:
        earned += 3.0
        details["db"] = "ok"
    if health["sidecar_rows"] > 0 and health["sidecar_counts"]:
        earned += 4.0
        details["sidecar"] = "ok"
    if not health["missing_triggers"]:
        earned += 4.0
        details["triggers"] = "ok"
    freshness_delta = health.get("sidecar_freshness_delta")
    if isinstance(freshness_delta, int) and freshness_delta <= 1_000:
        earned += 3.0
        details["freshness"] = "ok"
    if health.get("fts_queryable"):
        earned += 1.0
        details["fts"] = "ok"
    earned = min(max_score, earned)
    return GateCheck(
        name="index_health_and_freshness",
        score=earned,
        max_score=max_score,
        passed=earned >= max_score,
        summary=f"{health['sidecar_rows']} sidecar rows, freshness_delta={freshness_delta}",
        details={
            **details,
            "missing_triggers": health["missing_triggers"],
            "sidecar_counts": health["sidecar_counts"],
            "vec_document_sequence": health["vec_document_sequence"],
            "max_curated_vec_doc_id": health["max_curated_vec_doc_id"],
        },
    )


def score_source_coverage(
    health: dict[str, Any],
    *,
    source_file_target: int,
    memory_context_target: int,
    memory_graph_target: int,
    max_score: float,
) -> GateCheck:
    counts = dict(health.get("sidecar_counts") or {})
    source_count = int(counts.get("source_file", 0))
    context_count = int(counts.get("memory_context", 0))
    graph_count = int(counts.get("memory_graph", 0))
    source_score = 12.0 * min(1.0, source_count / max(1, source_file_target))
    context_score = 4.0 * min(1.0, context_count / max(1, memory_context_target))
    graph_score = 4.0 * min(1.0, graph_count / max(1, memory_graph_target))
    earned = min(max_score, source_score + context_score + graph_score)
    return GateCheck(
        name="curated_source_coverage",
        score=earned,
        max_score=max_score,
        passed=earned >= max_score,
        summary=(
            f"source_file={source_count}/{source_file_target}, "
            f"memory_context={context_count}/{memory_context_target}, "
            f"memory_graph={graph_count}/{memory_graph_target}"
        ),
        details={
            "source_file_count": source_count,
            "source_file_target": source_file_target,
            "memory_context_count": context_count,
            "memory_context_target": memory_context_target,
            "memory_graph_count": graph_count,
            "memory_graph_target": memory_graph_target,
        },
    )


def score_latency(rows: list[dict[str, Any]], *, max_score: float) -> GateCheck:
    elapsed = sorted(float(row.get("elapsed_ms") or 0.0) for row in rows)
    if not elapsed:
        return GateCheck(
            name="latency_budget",
            score=0.0,
            max_score=max_score,
            passed=False,
            summary="no latency rows",
            details={},
        )
    p95 = percentile(elapsed, 0.95)
    max_ms = max(elapsed)
    if p95 <= 750.0 and max_ms <= 1500.0:
        earned = max_score
    elif p95 <= 1200.0 and max_ms <= 2500.0:
        earned = max_score * 0.7
    else:
        earned = max_score * 0.3
    return GateCheck(
        name="latency_budget",
        score=earned,
        max_score=max_score,
        passed=earned >= max_score,
        summary=f"p95={p95:.1f}ms max={max_ms:.1f}ms",
        details={
            "case_count": len(elapsed),
            "p95_ms": round(p95, 3),
            "max_ms": round(max_ms, 3),
            "threshold_p95_ms": 750.0,
            "threshold_max_ms": 1500.0,
        },
    )


def score_telemetry(
    telemetry: dict[str, Any],
    *,
    expected_min_logs: int,
    max_score: float,
) -> GateCheck:
    earned = 0.0
    if telemetry.get("table_exists"):
        earned += 2.0
    if int(telemetry.get("new_rows") or 0) >= max(1, expected_min_logs):
        earned += 4.0
    if telemetry.get("new_rows") and int(telemetry.get("missing_core_fields") or 0) == 0:
        earned += 2.0
    p95 = telemetry.get("p95_total_ms")
    max_ms = telemetry.get("max_total_ms")
    if isinstance(p95, (int, float)) and isinstance(max_ms, (int, float)):
        if p95 <= 750.0 and max_ms <= 1500.0:
            earned += 2.0
        elif p95 <= 1200.0 and max_ms <= 2500.0:
            earned += 1.0
    earned = min(max_score, earned)
    return GateCheck(
        name="retrieval_telemetry",
        score=earned,
        max_score=max_score,
        passed=earned >= max_score,
        summary=(
            f"new_rows={telemetry.get('new_rows')}/{expected_min_logs}, "
            f"p95={telemetry.get('p95_total_ms')}ms"
        ),
        details={
            **telemetry,
            "expected_min_logs": expected_min_logs,
            "threshold_p95_ms": 750.0,
            "threshold_max_ms": 1500.0,
        },
    )


def percentile(sorted_values: list[float], fraction: float) -> float:
    if not sorted_values:
        return 0.0
    index = min(len(sorted_values) - 1, max(0, round((len(sorted_values) - 1) * fraction)))
    return sorted_values[index]


def render_text(payload: dict[str, Any]) -> str:
    lines = [
        f"Memory retrieval system gate: {payload['score']}/{payload['max_score']}",
        f"Passed: {payload['passed']}",
        "",
    ]
    for check in payload["checks"]:
        status = "PASS" if check["passed"] else "FAIL"
        lines.append(
            f"{status} {check['name']}: {check['score']}/{check['max_score']} - {check['summary']}"
        )
    if payload["broad"]["failures"]:
        lines.append("")
        for row in payload["broad"]["failures"]:
            lines.append(
                f"BROAD FAIL {row['name']} failure={row['failure']} "
                f"top={row['top_layer']}:{row['top_source']}"
            )
    if payload["live"]["failures"]:
        lines.append("")
        for row in payload["live"]["failures"]:
            lines.append(
                f"LIVE FAIL {row['name']} failure={row['failure']} "
                f"top={row['top_layer']}:{row['top_source']}"
            )
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state-dir", type=Path, default=Path.home() / ".dharma")
    parser.add_argument("--top-k", type=int, default=1)
    parser.add_argument("--negative-count", type=int, default=broad.DEFAULT_NEGATIVE_COUNT)
    parser.add_argument("--timeout-s", type=int, default=8)
    parser.add_argument("--source-file-target", type=int, default=256)
    parser.add_argument("--memory-context-target", type=int, default=100)
    parser.add_argument("--memory-graph-target", type=int, default=100)
    parser.add_argument("--skip-live", action="store_true")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--fail-under", type=float, default=100.0)
    parser.add_argument("--receipt-path", type=Path)
    args = parser.parse_args()

    payload = run_system_gate(
        state_dir=args.state_dir,
        top_k=args.top_k,
        negative_count=args.negative_count,
        timeout_s=args.timeout_s,
        source_file_target=args.source_file_target,
        memory_context_target=args.memory_context_target,
        memory_graph_target=args.memory_graph_target,
        run_live=not args.skip_live,
    )
    if args.receipt_path:
        args.receipt_path.parent.mkdir(parents=True, exist_ok=True)
        args.receipt_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(render_text(payload))
    return 0 if payload["score"] >= args.fail_under else 1


if __name__ == "__main__":
    raise SystemExit(main())
