"""Build warn-only semantic gate calibration metrics report."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from dharma_swarm.gate_metrics import build_warn_only_report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Summarize Semantic Anekanta/Bhed Gnan warn-only telemetry."
    )
    parser.add_argument(
        "--bhed-witness",
        type=Path,
        default=Path.home() / ".dharma/witness/bhed_gnan" / "2026-05-10.jsonl",
        help="Path to Bhed Gnan witness jsonl.",
    )
    parser.add_argument(
        "--chew-witness",
        type=Path,
        default=Path.home() / ".dharma/witness/inquiry_substrate_chew.jsonl",
        help="Path to inquiry_substrate_chew witness jsonl.",
    )
    parser.add_argument(
        "--adjudication",
        type=Path,
        default=None,
        help="Optional jsonl with manual signal adjudication rows.",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("quality-reports/semantic-gate-metrics.json"),
        help="Output report path.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    report = build_warn_only_report(
        bhed_witness_path=args.bhed_witness,
        chew_witness_path=args.chew_witness,
        adjudication_path=args.adjudication,
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    print(
        f"[semantic_gate_metrics] wrote {args.out} "
        f"(signals={sum(v.get('total', 0) for v in report['signal_prevalence'].values())})"
    )


if __name__ == "__main__":
    main()
