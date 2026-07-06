"""Novelty-weighted parent selection for Forge Lab."""

from __future__ import annotations

import random
from dataclasses import dataclass

from dharma_swarm.forge_lab.candidate_store import CandidateRecord


@dataclass(frozen=True)
class ParentDraw:
    parent: CandidateRecord
    weight: float
    child_count: int


def child_counts(records: list[CandidateRecord]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for record in records:
        if record.parent_id:
            counts[record.parent_id] = counts.get(record.parent_id, 0) + 1
    return counts


def novelty_weight(
    record: CandidateRecord,
    counts: dict[str, int],
    *,
    novelty_pressure: float = 0.7,
) -> float:
    """Ported DGM shape: fitness^(1-p) * (1/(1+n_children))^p."""

    p = max(0.0, min(1.0, float(novelty_pressure)))
    fitness = max(0.0, float(record.weighted_fitness))
    novelty = 1.0 / (1.0 + counts.get(record.candidate_id, 0))
    if fitness == 0.0:
        return novelty**p
    return (fitness ** (1.0 - p)) * (novelty**p)


def draw_parent(
    records: list[CandidateRecord],
    *,
    rng: random.Random,
    novelty_pressure: float = 0.7,
) -> ParentDraw:
    candidates = [record for record in records if record.state == "graded"]
    if not candidates:
        raise ValueError("cannot draw parent from an empty graded archive")
    counts = child_counts(records)
    weights = [novelty_weight(record, counts, novelty_pressure=novelty_pressure) for record in candidates]
    if sum(weights) <= 0.0:
        weights = [1.0 for _ in candidates]
    parent = rng.choices(candidates, weights=weights, k=1)[0]
    return ParentDraw(
        parent=parent,
        weight=novelty_weight(parent, counts, novelty_pressure=novelty_pressure),
        child_count=counts.get(parent.candidate_id, 0),
    )


def draw_parents(
    records: list[CandidateRecord],
    *,
    children: int,
    rng: random.Random,
    novelty_pressure: float = 0.7,
) -> list[ParentDraw]:
    return [
        draw_parent(records, rng=rng, novelty_pressure=novelty_pressure)
        for _ in range(max(0, int(children)))
    ]
