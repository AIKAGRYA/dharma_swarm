#!/usr/bin/env python3
"""CashClaw Variant Breeder — select fittest, kill weakest, mutate survivors.

Run periodically (e.g. weekly) to evolve the CashClaw variant population.

Selection: top 50% survive, bottom 50% are deactivated.
Mutation: each survivor produces one mutated offspring with random weight
perturbations. This preserves diversity while rewarding fitness.

Usage:
  python3 scripts/revenue/cashclaw_breed_variants.py [--min-cycles 3] [--population 6]
"""

from __future__ import annotations

import argparse
import random
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from dharma_swarm.revenue.cashclaw_evolution import (
    CashClawEvolutionDB,
    Variant,
    _short_hash,
    SOURCE_QUERY_BIASES,
)

MUTABLE_WEIGHTS = (
    "cash_speed_weight",
    "deliverability_weight",
    "distribution_access_weight",
    "payment_clarity_weight",
    "risk_cleanliness_weight",
    "agent_leverage_weight",
    "receipt_quality_weight",
)

MUTABLE_THRESHOLDS = (
    "min_score_threshold",
    "max_risk_flags",
)


def mutate_variant(parent: Variant, generation: int) -> Variant:
    """Create a mutated offspring from a fit parent."""
    child_dict = parent.model_dump()
    child_dict["variant_id"] = f"v{generation}-{_short_hash(parent.variant_id + str(generation))}"
    child_dict["generation"] = generation
    child_dict["parent_id"] = parent.variant_id

    for w in MUTABLE_WEIGHTS:
        val = getattr(parent, w)
        delta = random.choice([-5, -3, -1, 0, 1, 3, 5])
        child_dict[w] = max(0, min(40, val + delta))

    for t in MUTABLE_THRESHOLDS:
        val = getattr(parent, t)
        delta = random.choice([-2, -1, 0, 1, 2])
        if t == "min_score_threshold":
            child_dict[t] = max(50, min(95, val + delta))
        else:
            child_dict[t] = max(0, min(5, val + delta))

    if random.random() < 0.3:
        child_dict["source_query_bias"] = random.choice(SOURCE_QUERY_BIASES)

    return Variant(**child_dict)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--min-cycles", type=int, default=2, help="Min cycles before a variant is eligible for selection")
    parser.add_argument("--population", type=int, default=6, help="Target population size after breeding")
    parser.add_argument("--db-path", default="")
    parser.add_argument("--dry-run", action="store_true", help="Show what would happen without changing anything")
    args = parser.parse_args(argv)

    db_path = Path(args.db_path) if args.db_path else None
    db = CashClawEvolutionDB(db_path)

    active = db.get_active_variants()
    if not active:
        print("No active variants to breed. Seed first.")
        return 1

    scored = []
    for v in active:
        fitness = db.get_fitness(v.variant_id)
        scored.append((v, fitness))

    scored.sort(key=lambda x: x[1].fitness, reverse=True)

    eligible = [(v, f) for v, f in scored if f.total_cycles >= args.min_cycles]
    if not eligible:
        print(f"No variants with >= {args.min_cycles} cycles. Need more data before breeding.")
        print("Current state:")
        for v, f in scored:
            print(f"  {v.variant_id}: fitness={f.fitness:.1f}, cycles={f.total_cycles}")
        return 0

    survivors = eligible[: len(eligible) // 2 + 1]
    culled = [v for v, _ in scored if v.variant_id not in {s.variant_id for s, _ in survivors}]

    generation = max(v.generation for v in active) + 1

    print(f"Population: {len(active)} active, {len(eligible)} eligible")
    print(f"Survivors: {[v.variant_id for v, _ in survivors]}")
    print(f"Cull candidates: {[v.variant_id for v in culled]}")

    if args.dry_run:
        print("\n[DRY RUN] No changes made.")
        return 0

    for v in culled:
        v.active = False
        db.upsert_variant(v)
        print(f"  Deactivated: {v.variant_id}")

    children = []
    for parent, _ in survivors:
        child = mutate_variant(parent, generation)
        db.upsert_variant(child)
        children.append(child)
        print(f"  Born: {child.variant_id} from {parent.variant_id} (gen {generation})")

    final = db.get_active_variants()
    print(f"\nNew population: {len(final)} variants (gen 0..{generation})")

    for v, f in sorted(
        [(v, db.get_fitness(v.variant_id)) for v in final],
        key=lambda x: x[1].fitness,
        reverse=True,
    ):
        print(f"  {v.variant_id}: fitness={f.fitness:.1f}, bias={v.source_query_bias}, cycles={f.total_cycles}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
