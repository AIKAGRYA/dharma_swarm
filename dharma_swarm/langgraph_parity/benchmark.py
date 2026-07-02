"""CLI and public imports for the LangGraph parity benchmark."""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence

from dharma_swarm.langgraph_parity.benchmark_receipts import (
    build_benchmark_receipt,
    record_benchmark_runtime_receipt,
    stable_payload_hash,
    write_report,
)
from dharma_swarm.langgraph_parity.benchmark_runner import (
    default_benchmark_tasks,
    format_markdown_report,
    run_benchmark,
)
from dharma_swarm.langgraph_parity.benchmark_types import (
    BENCHMARK_AGENT_ID,
    BENCHMARK_MODES,
    BENCHMARK_OPERATION,
    REQUIRED_CASE_TAGS,
    BenchmarkMode,
    BenchmarkReport,
    BenchmarkResult,
    BenchmarkTask,
    ProviderProfile,
)

_stable_payload_hash = stable_payload_hash

__all__ = [
    "BENCHMARK_AGENT_ID",
    "BENCHMARK_MODES",
    "BENCHMARK_OPERATION",
    "REQUIRED_CASE_TAGS",
    "BenchmarkMode",
    "BenchmarkReport",
    "BenchmarkResult",
    "BenchmarkTask",
    "ProviderProfile",
    "_stable_payload_hash",
    "build_benchmark_receipt",
    "default_benchmark_tasks",
    "format_markdown_report",
    "record_benchmark_runtime_receipt",
    "run_benchmark",
    "write_report",
]


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run the deterministic LangGraph parity isolation benchmark."
    )
    parser.add_argument(
        "--output-dir",
        default="reports/langgraph_parity/benchmark",
        help="Directory for benchmark_report.json and benchmark_report.md.",
    )
    parser.add_argument("--provider", default="local")
    parser.add_argument("--model", default="deterministic-isolation-harness-v1")
    parser.add_argument("--cost-per-1k-tokens", type=float, default=0.0002)
    parser.add_argument("--mission-id", default="")
    parser.add_argument(
        "--runtime-db",
        default="",
        help="Runtime DB path for the canonical receipt; defaults to the live runtime DB.",
    )
    parser.add_argument(
        "--no-runtime-receipt",
        action="store_true",
        help="Write report artifacts without recording a canonical runtime receipt.",
    )
    args = parser.parse_args(argv)

    report = run_benchmark(
        provider_profile=ProviderProfile(
            provider=args.provider,
            model=args.model,
            cost_per_1k_tokens=args.cost_per_1k_tokens,
        ),
        mission_id=args.mission_id,
    )
    json_path, markdown_path = write_report(report, args.output_dir)
    runtime_receipt = None
    if not args.no_runtime_receipt:
        runtime_receipt = record_benchmark_runtime_receipt(
            report,
            artifact_id=stable_payload_hash(report.to_dict()),
            artifact_path=json_path,
            runtime_db_path=args.runtime_db or None,
        )
    print(f"wrote {json_path}")
    print(f"wrote {markdown_path}")
    if runtime_receipt is not None:
        print(f"runtime_receipt_id={runtime_receipt.receipt_id}")
        print(f"runtime_run_id={runtime_receipt.run_id}")
    print(json.dumps(report.summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
