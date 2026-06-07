#!/usr/bin/env python3
"""Run CashClaw live intake in governed read-only mode."""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from dharma_swarm.revenue.live_intake import CashClawLiveIntake, score_pattern_card
from dharma_swarm.revenue.live_intake_sources import LIVE_INTAKE_ENV, load_source_configs


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-config", action="append", default=[], help="JSON file with LiveIntakeSourceConfig records")
    parser.add_argument("--fixture", action="append", default=[], help="Local JSON/JSONL/Markdown fixture/export file")
    parser.add_argument("--output-root", default="", help="Output directory; defaults to reports/revenue_wedge/cashclaw_live_intake/runs/<run_id>")
    parser.add_argument("--top-n", type=int, default=10)
    parser.add_argument("--allow-network", action="store_true", help=f"Allow network only if {LIVE_INTAKE_ENV}=1 and source host is allowlisted")
    parser.add_argument("--max-items", type=int, default=100)
    args = parser.parse_args(argv)

    configs = []
    for config_path in args.source_config:
        configs.extend(load_source_configs(config_path))

    run_id = "cashclaw-live-intake-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    output_root = Path(args.output_root) if args.output_root else REPO_ROOT / "reports" / "revenue_wedge" / "cashclaw_live_intake" / "runs" / run_id
    intake = CashClawLiveIntake(report_root=output_root.parent)
    result = intake.run(
        source_configs=configs,
        fixture_paths=args.fixture,
        output_root=output_root,
        top_n=args.top_n,
        max_items=args.max_items,
        allow_network=args.allow_network,
    )
    top_cards = sorted(result.pattern_cards, key=score_pattern_card, reverse=True)[: args.top_n]
    _write_cli_summary(output_root, result, top_cards)
    _print_summary(output_root, result, top_cards, allow_network=args.allow_network)
    return 0


def _write_cli_summary(output_root: Path, result, top_cards) -> None:
    payload = {
        "run_id": result.run_id,
        "source_items": result.source_item_count,
        "pattern_cards": result.pattern_card_count,
        "top_patterns": [
            {
                "pattern_card_id": card.pattern_card_id,
                "score": score_pattern_card(card),
                "pattern": card.what_is_being_built,
                "buyer_segment": card.buyer_segment,
                "risks": card.risks,
            }
            for card in top_cards
        ],
        "network_reads": result.network_reads_performed,
        "blocked_sources": result.blocked_sources,
        "errors": result.errors,
        "warnings": result.warnings,
    }
    (output_root / "cli_summary.json").write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _print_summary(output_root: Path, result, top_cards, *, allow_network: bool) -> None:
    env_enabled = os.environ.get(LIVE_INTAKE_ENV, "")
    print("CashClaw Live Intake")
    print(f"  Run ID:           {result.run_id}")
    print(f"  Source items:     {result.source_item_count}")
    print(f"  Pattern cards:    {result.pattern_card_count}")
    print(f"  Top patterns:     {len(top_cards)}")
    print(f"  Network reads:    {result.network_reads_performed} (allow flag={allow_network}, env={bool(env_enabled)})")
    print(f"  Blocked sources:  {result.blocked_sources}")
    print(f"  External effects: none")
    print(f"  Output:           {output_root}")
    if result.errors:
        print(f"  Errors:           {len(result.errors)}")
        for error in result.errors[:5]:
            print(f"    - {error}")
    if result.warnings:
        print(f"  Warnings:         {len(result.warnings)}")
        for warning in result.warnings[:5]:
            print(f"    - {warning}")


if __name__ == "__main__":
    raise SystemExit(main())
