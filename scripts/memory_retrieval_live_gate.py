#!/usr/bin/env python3
"""Score live governed retrieval against real local memory topics."""

from __future__ import annotations

import argparse
import json
import signal
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from dharma_swarm.memory_retrieval import GovernedRetrievalEngine, RetrievalQuery


@dataclass(frozen=True)
class LiveCase:
    name: str
    query: str
    expected_source_contains: tuple[str, ...] = ()
    expected_layer: str | None = None
    expect_empty: bool = False
    max_ms: float = 750.0
    forbid_source_prefixes: tuple[str, ...] = ("evolution_archive:",)


LIVE_CASES: tuple[LiveCase, ...] = (
    LiveCase("bronze", "Bronze supply-chain minhash dedupe raw boundary receipts", ("bronze",), "memory_context"),
    LiveCase("bronze_paraphrase", "did the HN supply chain bronze CLI deduplicate correctly", ("bronze",), "memory_context"),
    LiveCase("sarathi", "Sarathi apex holon Japan walk", ("sarathi",), "memory_context"),
    LiveCase("sarathi_paraphrase", "chief of staff seat for John's Japan walk", ("sarathi", "japan-walk"), "memory_context"),
    LiveCase("gaia", "GAIA ecological restoration carbon offset", ("gaia",), "source_file", max_ms=1500.0),
    LiveCase("gaia_paraphrase", "AI carbon offset restoration platform already implemented", ("gaia", "carbon-offset"), "source_file"),
    LiveCase("dharma_capital", "Dharma Capital Holon loop never closes", ("42219", "dharma-capital"), "memory_context"),
    LiveCase("vwrite", "VWRITE pipeline publish April 19 title format skip bug", ("42224", "vwrite"), "memory_context"),
    LiveCase("vwrite_paraphrase", "why did the writing pipeline stop publishing in April", ("42224", "vwrite"), "memory_context"),
    LiveCase("tam", "TAM operator package absent on main external contact", ("42221", "tam-operator"), "memory_context"),
    LiveCase("agni", "Agni Trading Lab real P&L over 88 days", ("42212", "agni-trading"), "memory_context"),
    LiveCase("cashclaw", "CashClaw Hermes bounty loop zero cash earned", ("42213", "cashclaw"), "memory_context"),
    LiveCase("memory_kernel", "memory kernel retrieval tool query relevance gap", ("memorykernel", "wiki-read-path"), "memory_graph"),
    LiveCase("nats", "A2A NATS duplicate window DLQ MaxDeliver", ("nats",), "memory_graph"),
    LiveCase("nats_paraphrase", "what made NATS exactly-once delivery unverified", ("nats", "duplicate_window"), "memory_graph"),
    LiveCase("corr_absent", "corr-2026-06-a2a-liveness", expect_empty=True),
    LiveCase("mcp_doc", "MCP Python SDK stdio SSE websocket memory", ("mcp-python-sdk", "communication-transports"), "source_file"),
    LiveCase("mcp_doc_paraphrase", "which MCP transport uses in-memory queues for testing", ("mcp-python-sdk", "communication-transports"), "source_file"),
    LiveCase("palantir", "Palantir pilot source card quality public docs", ("palantir-pilot-source-card-quality",), "source_file"),
    LiveCase("negative", "xyzzq impossible memory topic lunar cheese invoice", expect_empty=True),
)


class QueryTimeout(Exception):
    pass


def _alarm(_signum: int, _frame: object) -> None:
    raise QueryTimeout()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state-dir", type=Path, default=Path.home() / ".dharma")
    parser.add_argument("--top-k", type=int, default=3)
    parser.add_argument("--timeout-s", type=int, default=8)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--fail-under", type=float, default=100.0)
    args = parser.parse_args()

    signal.signal(signal.SIGALRM, _alarm)
    engine = GovernedRetrievalEngine(state_dir=args.state_dir.expanduser())
    rows = [run_case(engine, case, top_k=args.top_k, timeout_s=args.timeout_s) for case in LIVE_CASES]
    score = score_rows(rows)
    payload = {
        "schema_version": 1,
        "state_dir": str(args.state_dir.expanduser()),
        "score": score,
        "passed": score >= args.fail_under,
        "case_count": len(rows),
        "pass_count": sum(1 for row in rows if row["passed"]),
        "rows": rows,
    }
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(render_text(payload))
    return 0 if score >= args.fail_under else 1


def run_case(
    engine: GovernedRetrievalEngine,
    case: LiveCase,
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
            "top_snippet": "",
            "result_count": 0,
        }

    elapsed_ms = float(result.timings_ms.get("total") or round((time.perf_counter() - started) * 1000.0, 3))
    candidates = result.candidates
    top = candidates[0] if candidates else None
    top_source = top.source if top else ""
    top_layer = top.layer if top else ""
    top_text = f"{top_source} {top.content if top else ''}".lower()
    failures: list[str] = []

    if case.expect_empty:
        if candidates:
            failures.append("expected_empty")
    else:
        if not candidates:
            failures.append("no_results")
        if case.expected_layer and top_layer != case.expected_layer:
            failures.append(f"wrong_layer:{top_layer}")
        if case.expected_source_contains and not any(part.lower() in top_text for part in case.expected_source_contains):
            failures.append("wrong_source")
    if elapsed_ms > case.max_ms:
        failures.append(f"slow:{elapsed_ms:.1f}>{case.max_ms:.1f}")
    if any(top_source.startswith(prefix) for prefix in case.forbid_source_prefixes):
        failures.append(f"forbidden_source:{top_source}")

    return {
        **asdict(case),
        "passed": not failures,
        "elapsed_ms": round(elapsed_ms, 3),
        "failure": ",".join(failures),
        "top_source": top_source,
        "top_layer": top_layer,
        "top_snippet": " ".join((top.content if top else "").split())[:240],
        "result_count": len(candidates),
    }


def score_rows(rows: list[dict[str, Any]]) -> float:
    if not rows:
        return 0.0
    return round((sum(1 for row in rows if row["passed"]) / len(rows)) * 100.0, 1)


def render_text(payload: dict[str, Any]) -> str:
    lines = [
        f"Live memory retrieval gate: {payload['score']}/100",
        f"Passed {payload['pass_count']}/{payload['case_count']}",
        "",
    ]
    for row in payload["rows"]:
        status = "PASS" if row["passed"] else "FAIL"
        lines.append(
            f"{status} {row['name']} {row['elapsed_ms']}ms "
            f"top_layer={row['top_layer']} top_source={row['top_source']} failure={row['failure']}"
        )
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    raise SystemExit(main())
