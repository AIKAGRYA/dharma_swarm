"""Stage 2 of the seeing organ — Shakti reads the world, hands still down.

A read-only handoff: corroborated ``WorldSensemakingReceipt``s from the Frontier
Council (Stage 1) become ADVISORY warrant-pressure that S4 can read to bias
priorities. This is the *seeing* step, not the *acting* step:

  - It returns DATA OBJECTS (``WorldWarrantPressure``), never a dispatch and never
    a mutation. It does not write ACTIVE_TRACK.yaml, the ontology, or memory.
  - ``dispatch_authority`` stays ``False`` and is stamped on every projection.
  - Only ``corroborated`` receipts that carry ``no_action_authority`` and no
    ``dispatch_authority`` produce pressure. Refuted / insufficient / quarantined
    receipts produce NONE.

A pure function: no I/O, no owner mutation. Accepts receipt objects or the JSON
dicts they serialise to, so a downstream reader can hand it replayed receipts.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any

from dharma_swarm.world_radar.frontier_council import CORROBORATED, WorldSensemakingReceipt


@dataclass
class WorldWarrantPressure:
    """An ADVISORY, read-only pressure signal derived from a corroborated world
    receipt. It can inform priority; it cannot dispatch or mutate anything."""
    pressure_id: str
    source_receipt_id: str
    input_signal_hash: str
    claim: str
    corroboration_count: int
    source_family_count: int
    pressure_weight: float  # advisory magnitude in [0, 1], rises with corroboration
    risks: list[str] = field(default_factory=list)
    generated_at: str = ""
    is_advisory: bool = True
    no_action_authority: bool = True
    dispatch_authority: bool = False


def _as_dict(receipt: WorldSensemakingReceipt | dict[str, Any]) -> dict[str, Any]:
    return asdict(receipt) if isinstance(receipt, WorldSensemakingReceipt) else dict(receipt)


def _pressure_weight(corroboration_count: int, source_family_count: int) -> float:
    """Bounded advisory magnitude. Monotonic in decorrelated agreement; never 1.0
    from a single family (the moat: structure, not confidence)."""
    return round(min(1.0, 0.2 * int(corroboration_count) + 0.2 * int(source_family_count)), 4)


def world_warrant_pressure(
    receipts: list[WorldSensemakingReceipt | dict[str, Any]],
) -> list[WorldWarrantPressure]:
    """Project corroborated world-sensemaking receipts into advisory
    warrant-pressure. Hands stay down — returns data objects only; never
    dispatches, never mutates an owner. ``DISPATCH_AUTHORITY`` is untouched."""
    out: list[WorldWarrantPressure] = []
    for raw in receipts:
        r = _as_dict(raw)
        if r.get("verdict") != CORROBORATED:
            continue
        # Defensive: never project a receipt that claims any action authority.
        if r.get("dispatch_authority") is True or r.get("no_action_authority") is not True:
            continue
        corroboration = int(r.get("corroboration_count") or 0)
        source_families = int(r.get("source_family_count") or 0)
        out.append(
            WorldWarrantPressure(
                pressure_id=f"world_pressure_{str(r.get('receipt_id', ''))[-24:]}",
                source_receipt_id=str(r.get("receipt_id", "")),
                input_signal_hash=str(r.get("input_signal_hash", "")),
                claim=str(r.get("claim", "")),
                corroboration_count=corroboration,
                source_family_count=source_families,
                pressure_weight=_pressure_weight(corroboration, source_families),
                risks=list(r.get("risks") or []),
                generated_at=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                is_advisory=True,
                no_action_authority=True,
                dispatch_authority=False,
            )
        )
    return out
