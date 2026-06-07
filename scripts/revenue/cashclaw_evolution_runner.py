#!/usr/bin/env python3
"""Run one CashClaw evolution cycle: scan bounties with active variants.

This script is the Hermes cron entry point. Each run:
1. Loads active variants from the evolution DB
2. For each variant, runs a live-intake scan with that variant's weights
3. Records results (opportunities found, scores, cost)
4. Reports the top opportunity for each variant

Usage:
  python3 scripts/revenue/cashclaw_evolution_runner.py [--allow-network] [--variant VARIANT_ID]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from dharma_swarm.revenue.cashclaw_evolution import (
    CashClawEvolutionDB,
    CycleResult,
    Variant,
    _short_hash,
)


def run_variant_cycle(
    variant: Variant,
    *,
    allow_network: bool = False,
    output_root: Path,
) -> CycleResult:
    """Run one scan cycle for a single variant."""
    result_id = f"cycle-{variant.variant_id}-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')}"
    variant_dir = output_root / result_id
    variant_dir.mkdir(parents=True, exist_ok=True)

    try:
        from dharma_swarm.revenue.live_intake import CashClawLiveIntake, score_pattern_card
        from dharma_swarm.revenue.live_intake_sources import load_source_configs
    except ImportError:
        return CycleResult(
            result_id=result_id,
            variant_id=variant.variant_id,
            errors=1,
            notes="import failed — live_intake modules not available",
        )

    source_config_path = REPO_ROOT / "dharma_swarm" / "revenue" / "live_intake_sources.json"
    if not source_config_path.exists():
        source_config_paths = list(REPO_ROOT.glob("**/live_intake_sources*.json"))
        if source_config_paths:
            source_config_path = source_config_paths[0]
        else:
            return CycleResult(
                result_id=result_id,
                variant_id=variant.variant_id,
                errors=1,
                notes="no source config found",
            )

    configs = load_source_configs(str(source_config_path))
    intake = CashClawLiveIntake(report_root=output_root)
    result = intake.run(
        source_configs=configs,
        output_root=variant_dir,
        top_n=variant.top_n,
        max_items=100,
        allow_network=allow_network,
    )

    pattern_cards = sorted(
        result.pattern_cards, key=score_pattern_card, reverse=True
    )[: variant.top_n]

    above_threshold = [c for c in pattern_cards if score_pattern_card(c) >= variant.min_score_threshold]

    scores = [score_pattern_card(c) for c in pattern_cards]
    avg_score = sum(scores) / len(scores) if scores else 0.0

    top_value_cents = 0
    if above_threshold:
        top_value_cents = max(
            getattr(c, "estimated_value_cents", 0) for c in above_threshold
        )

    cycle_result = CycleResult(
        result_id=result_id,
        variant_id=variant.variant_id,
        opportunities_found=len(pattern_cards),
        opportunities_above_threshold=len(above_threshold),
        opportunities_submitted=0,
        revenue_earned_cents=0,
        cost_cents=0,
        top_opportunity_value_cents=top_value_cents,
        avg_score=round(avg_score, 2),
        sources_hit=result.source_item_count if hasattr(result, "source_item_count") else 0,
        errors=len(result.errors) if hasattr(result, "errors") else 0,
        notes=f"variant={variant.source_query_bias} gen={variant.generation}",
    )

    (variant_dir / "cycle_result.json").write_text(
        cycle_result.model_dump_json(indent=2) + "\n", encoding="utf-8"
    )

    (variant_dir / "top_opportunities.json").write_text(
        json.dumps(
            [
                {
                    "score": score_pattern_card(c),
                    "title": getattr(c, "what_is_being_built", ""),
                    "buyer": getattr(c, "buyer_segment", ""),
                    "value_cents": getattr(c, "estimated_value_cents", 0),
                    "risks": getattr(c, "risks", []),
                }
                for c in pattern_cards[:10]
            ],
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    return cycle_result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--allow-network", action="store_true")
    parser.add_argument("--variant", default="", help="Run only this variant ID")
    parser.add_argument("--seed", action="store_true", help="Seed initial variants if none exist")
    parser.add_argument("--db-path", default="", help="Path to evolution DB")
    parser.add_argument("--output-root", default="", help="Output directory")
    args = parser.parse_args(argv)

    db_path = Path(args.db_path) if args.db_path else None
    db = CashClawEvolutionDB(db_path)

    variants = db.get_active_variants()
    if not variants and args.seed:
        variants = db.seed_initial_variants()
        print(f"Seeded {len(variants)} initial variants")
    elif not variants:
        print("No active variants. Run with --seed to create initial population.")
        return 1

    if args.variant:
        variants = [v for v in variants if v.variant_id == args.variant]
        if not variants:
            print(f"Variant {args.variant} not found")
            return 1

    output_root = Path(args.output_root) if args.output_root else (
        REPO_ROOT / "reports" / "revenue_wedge" / "evolution"
        / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    )
    output_root.mkdir(parents=True, exist_ok=True)

    results = []
    for v in variants:
        print(f"Running variant: {v.variant_id} (bias={v.source_query_bias}, gen={v.generation})")
        cr = run_variant_cycle(
            v, allow_network=args.allow_network, output_root=output_root
        )
        db.record_result(cr)
        results.append(cr)
        print(
            f"  Found {cr.opportunities_found} ops, "
            f"{cr.opportunities_above_threshold} above threshold, "
            f"avg_score={cr.avg_score:.1f}, "
            f"top_value=${cr.top_opportunity_value_cents / 100:.0f}"
        )

    print(f"\nCycle complete: {len(results)} variants, output at {output_root}")
    print("\nLeaderboard:")
    for entry in db.get_leaderboard(limit=len(variants)):
        vid = entry["variant_id"]
        f = entry["fitness"]
        rev = entry["total_revenue_cents"]
        cycles = entry["total_cycles"]
        print(f"  {vid}: fitness={f:.1f}, cycles={cycles}, revenue=${rev / 100:.2f}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
