#!/usr/bin/env python3
"""Run a governed retrieval benchmark over temp and live memory projections."""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import tempfile
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from dharma_swarm.memory_retrieval import GovernedRetrievalEngine, RetrievalQuery
from dharma_swarm.vector_store import VectorStore


@dataclass(frozen=True)
class IdeaCase:
    idea_id: str | None
    query: str
    content: str
    age_days: int
    kind: str


IDEA_CASES: tuple[IdeaCase, ...] = (
    IdeaCase(
        "a2a_consumer_liveness",
        "consumer liveness reply receipt semantic inbox",
        "Fresh A2A consumer liveness projection: semantic inbox drains require a verified reply receipt.",
        1,
        "recent",
    ),
    IdeaCase(
        "revenue_wedge_pipeline",
        "revenue wedge pipeline operator package",
        "Revenue Wedge Pipeline: package proof-backed offers from AGNI, CashClaw, and TAM into outbound operator loops.",
        2,
        "recent",
    ),
    IdeaCase(
        "memory_kernel_retrieval_tool",
        "memory kernel deterministic retrieval tool",
        "Memory Kernel retrieval tool should expose deterministic lookup, governed context admission, and no prompt injection.",
        6,
        "recent",
    ),
    IdeaCase(
        "semantic_commons_unresolved",
        "semantic commons unresolved blocker clearing",
        "Semantic Commons unresolved blocker clearing must remove lifecycle blockers after canonical object resolution.",
        0,
        "recent_edge",
    ),
    IdeaCase(
        "bronze_supply_chain",
        "bronze supply-chain minhash dedupe raw boundary receipts",
        "Bronze supply-chain intake closed MinHash dedupe and raw boundary receipts.",
        90,
        "three_months_old",
    ),
    IdeaCase(
        "vwrite_title_skip",
        "vwrite title format skip bug publish pipeline",
        "VWRITE publish pipeline died after a title-format skip bug; last publish was April 19.",
        70,
        "old",
    ),
    IdeaCase(
        "agni_one_route_pnl",
        "agni trading one route pnl",
        "Agni trading lab showed real P&L from one route over 88 days.",
        88,
        "three_months_old",
    ),
    IdeaCase(
        "tam_active_track_schema",
        "TAM ACTIVE_TRACK Schema v2",
        "TAM name locked: TRANSDIMENSIONAL ABUNDANCE MACHINE with ACTIVE_TRACK at Schema v2.",
        8,
        "exact_phrase",
    ),
    IdeaCase(
        "a2a_corr_handle",
        "corr-2026-06-a2a-liveness",
        "Correlation handle corr-2026-06-a2a-liveness maps the launchd drill to the domain reply.",
        1,
        "punctuation_handle",
    ),
    IdeaCase(
        None,
        "zxqwbblplk fnord qqqnotindexed",
        "",
        0,
        "negative_noise",
    ),
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--home", default=str(Path.home()))
    parser.add_argument("--temp-state-dir", default="")
    parser.add_argument("--live-state-dir", default=str(Path.home() / ".dharma"))
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--skip-live", action="store_true")
    parser.add_argument("--memory-kernel", action="store_true")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--report-path", default="")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    tmp_state = Path(args.temp_state_dir) if args.temp_state_dir else Path(
        tempfile.mkdtemp(prefix="memory_retrieval_bench_")
    )
    tmp_state.mkdir(parents=True, exist_ok=True)
    seed_store = VectorStore(state_dir=tmp_state, dim=64)
    seed_receipt = seed_cases(seed_store)

    kernel = build_memory_kernel(args) if args.memory_kernel else None
    temp_engine = GovernedRetrievalEngine(
        state_dir=tmp_state,
        vector_store=seed_store,
        memory_kernel=kernel,
        dim=64,
    )
    temp_runs = run_cases(temp_engine, args.top_k)

    live_runs: list[dict[str, Any]] = []
    live_diagnostics: dict[str, Any] | None = None
    if not args.skip_live:
        live_engine = GovernedRetrievalEngine(
            state_dir=Path(args.live_state_dir).expanduser(),
            memory_kernel=kernel,
            dim=64,
        )
        live_diagnostics = live_engine.diagnostics().to_json()
        live_runs = run_cases(live_engine, args.top_k, score_expected=False)

    payload = {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "temp_state_dir": str(tmp_state),
        "live_state_dir": "" if args.skip_live else str(Path(args.live_state_dir).expanduser()),
        "seed_receipt": seed_receipt,
        "temp_summary": summarize_runs(temp_runs),
        "temp_runs": temp_runs,
        "live_summary": summarize_runs(live_runs) if live_runs else None,
        "live_diagnostics": live_diagnostics,
        "live_runs": live_runs,
    }

    if args.report_path:
        report_path = Path(args.report_path)
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(render_markdown(payload), encoding="utf-8")
        payload["report_path"] = str(report_path)

    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(render_markdown(payload))
    return 0


def seed_cases(store: VectorStore) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    seeded: list[dict[str, Any]] = []
    for case in IDEA_CASES:
        if case.idea_id is None:
            continue
        doc_id = store.upsert(
            case.content,
            source=f"benchmark:{case.idea_id}",
            layer="benchmark",
            metadata={"idea_id": case.idea_id, "kind": case.kind},
            event_time=now - timedelta(days=case.age_days),
        )
        seeded.append(
            {
                "idea_id": case.idea_id,
                "doc_id": doc_id,
                "kind": case.kind,
                "age_days": case.age_days,
            }
        )
    return {"seeded_count": len(seeded), "seeded": seeded}


def run_cases(
    engine: GovernedRetrievalEngine,
    top_k: int,
    *,
    score_expected: bool = True,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for case in IDEA_CASES:
        start = time.perf_counter()
        result = engine.retrieve(
            RetrievalQuery(
                text=case.query,
                top_k=top_k,
                include_content=True,
                enable_memory_kernel=engine.memory_kernel is not None,
                kernel_candidate_limit=12,
                kernel_admitted_limit=5,
            )
        )
        elapsed_ms = round((time.perf_counter() - start) * 1000.0, 3)
        candidates = [candidate.to_json() for candidate in result.candidates]
        expected_rank = expected_candidate_rank(candidates, case.idea_id)
        success: bool | None
        if not score_expected:
            success = None
        elif case.idea_id is None:
            success = len(candidates) == 0
        else:
            success = expected_rank is not None
        rows.append(
            {
                "query": case.query,
                "kind": case.kind,
                "expected_idea_id": case.idea_id,
                "success": success,
                "expected_rank": expected_rank,
                "elapsed_ms": elapsed_ms,
                "engine_timings_ms": result.timings_ms,
                "result_count": len(candidates),
                "top_candidate": candidates[0] if candidates else None,
                "memory_kernel": result.memory_kernel.to_json(),
                "diagnostics": result.diagnostics.to_json(),
            }
        )
    return rows


def expected_candidate_rank(candidates: list[dict[str, Any]], idea_id: str | None) -> int | None:
    if idea_id is None:
        return None
    for candidate in candidates:
        metadata = candidate.get("metadata") or {}
        if metadata.get("idea_id") == idea_id:
            return int(candidate.get("rank") or 0)
    return None


def summarize_runs(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not rows:
        return {"query_count": 0}
    latencies = [float(row["elapsed_ms"]) for row in rows]
    scored = [row for row in rows if row.get("success") is not None]
    successes = [row for row in scored if row.get("success") is True]
    positive_scored = [row for row in scored if row.get("expected_idea_id") is not None]
    top1 = [row for row in positive_scored if row.get("expected_rank") == 1]
    return {
        "query_count": len(rows),
        "scored_query_count": len(scored),
        "positive_scored_query_count": len(positive_scored),
        "success_count": len(successes),
        "success_rate": round(len(successes) / len(scored), 3) if scored else None,
        "top1_count": len(top1),
        "top1_rate": round(len(top1) / len(positive_scored), 3) if positive_scored else None,
        "latency_ms_min": round(min(latencies), 3),
        "latency_ms_median": round(statistics.median(latencies), 3),
        "latency_ms_max": round(max(latencies), 3),
    }


def build_memory_kernel(args: argparse.Namespace):
    from dharma_swarm.memory_kernel import CensusConfig, MemoryKernel, MemoryKernelConfig

    return MemoryKernel(
        MemoryKernelConfig(
            census=CensusConfig(
                repo_root=Path(args.repo_root),
                home=Path(args.home).expanduser(),
                include_discovered=False,
            )
        )
    )


def render_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Governed Memory Retrieval Benchmark",
        "",
        f"- Generated: `{payload['generated_at']}`",
        f"- Temp state: `{payload['temp_state_dir']}`",
        f"- Live state: `{payload['live_state_dir'] or 'skipped'}`",
        "",
        "## Temp Corpus",
        "",
    ]
    for key, value in (payload.get("temp_summary") or {}).items():
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(["", "## Temp Queries", ""])
    for row in payload.get("temp_runs", []):
        top = row.get("top_candidate") or {}
        top_id = ((top.get("metadata") or {}).get("idea_id") or "")
        lines.append(
            f"- `{row['kind']}` success=`{row['success']}` rank=`{row['expected_rank']}` "
            f"latency_ms=`{row['elapsed_ms']}` top=`{top_id}` query=`{row['query']}`"
        )
    if payload.get("live_summary"):
        lines.extend(["", "## Live Projection", ""])
        for key, value in payload["live_summary"].items():
            lines.append(f"- `{key}`: `{value}`")
        diagnostics = payload.get("live_diagnostics") or {}
        if diagnostics.get("degraded_reasons"):
            lines.append(f"- `degraded_reasons`: `{', '.join(diagnostics['degraded_reasons'])}`")
        lines.extend(["", "## Live Queries", ""])
        for row in payload.get("live_runs", []):
            top = row.get("top_candidate") or {}
            lines.append(
                f"- `{row['kind']}` results=`{row['result_count']}` latency_ms=`{row['elapsed_ms']}` "
                f"top_source=`{top.get('source', '')}` query=`{row['query']}`"
            )
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    raise SystemExit(main())
