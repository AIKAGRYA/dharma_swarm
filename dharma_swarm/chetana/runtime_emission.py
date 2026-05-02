"""Emit promoted chetana atoms into runtime memory.

This is a projection hook, not a second promotion path. The atom remains owned
by chetana.promote; this module emits a MemoryFact with provenance so runtime
context can retrieve promoted semantic atoms through the memory lattice.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, time, timezone
from typing import TYPE_CHECKING

from dharma_swarm.runtime_state import MemoryEdge, MemoryFact

if TYPE_CHECKING:
    from dharma_swarm.chetana.promote import PromoteResult
    from dharma_swarm.chetana.provenance import FrontmatterSchema

logger = logging.getLogger(__name__)

_MAX_BODY_CHARS = 8192
_MAX_EDGES_PER_ATOM = 16


async def emit_memory_fact_for_atom(
    result: "PromoteResult",
    schema: "FrontmatterSchema",
    body: str,
) -> None:
    """Emit a promoted atom as a runtime MemoryFact.

    Hook failures are caught by chetana.promote. This function should still be
    best-effort internally because runtime memory is a projection of the trusted
    atom, not the authority over it.
    """
    if result.decision == "BLOCK" or result.trusted_path is None:
        return
    if schema.provenance is None:
        logger.warning("runtime emission skipped atom without provenance: %s", schema.atom_id)
        return

    from dharma_swarm.memory_lattice import MemoryLattice

    lattice = MemoryLattice()
    await lattice.init_db()
    try:
        fact_id = lattice.runtime_state.new_fact_id()
        fact = MemoryFact(
            fact_id=fact_id,
            fact_kind=f"chetana.{schema.type}",
            truth_state=_truth_state_for_review_status(str(result.review_status or "")),
            text=_fact_text(schema.title, body),
            confidence=float(schema.confidence),
            valid_from=_parse_iso_datetime(schema.provenance.promoted_at),
            valid_to=_parse_iso_date(schema.stale_after),
            source_artifact_id=schema.atom_id,
            metadata={
                "source": "chetana.promote",
                "atom_id": schema.atom_id,
                "atom_type": schema.type,
                "para_class": schema.para_class,
                "tags": list(schema.tags),
                "trusted_path": str(result.trusted_path),
            },
            provenance={
                "source": "chetana.promote",
                "atom_path": str(result.trusted_path),
                "atom_id": schema.atom_id,
                "axiom_signature": schema.provenance.axiom_signature,
                "gate_check": schema.provenance.gate_check.model_dump(mode="json"),
                "gate_check_result": schema.provenance.gate_check.result,
                "review_status": result.review_status,
                "promoted_by": schema.provenance.promoted_by,
                "promoted_at": schema.provenance.promoted_at,
            },
        )
        admission = await lattice.admit_memory_fact(
            fact,
            action="chetana.promote.emit_memory_fact",
            metadata={"atom_id": schema.atom_id, "trusted_path": str(result.trusted_path)},
        )
        if not admission.accepted:
            logger.warning(
                "runtime emission fact admission rejected for atom %s: %s",
                schema.atom_id,
                admission.rationale,
            )
            return

        for related in list(schema.related)[:_MAX_EDGES_PER_ATOM]:
            edge = MemoryEdge(
                edge_id=lattice.runtime_state.new_edge_id(),
                from_fact_id=fact_id,
                to_fact_id=str(related),
                relation="chetana.related",
                weight=0.5,
                metadata={
                    "source": "chetana.promote",
                    "atom_id": schema.atom_id,
                    "related": str(related),
                },
            )
            await lattice.admit_memory_edge(
                edge,
                action="chetana.promote.emit_memory_edge",
                metadata={"atom_id": schema.atom_id, "related": str(related)},
            )
    finally:
        await lattice.close()


def _truth_state_for_review_status(review_status: str) -> str:
    if review_status in {"auto_promoted", "approved"}:
        return "promoted"
    return "candidate"


def _fact_text(title: str, body: str) -> str:
    text = f"{title}\n\n{body}".strip()
    if len(text) <= _MAX_BODY_CHARS:
        return text
    return text[: _MAX_BODY_CHARS - 15].rstrip() + "\n... [truncated]"


def _parse_iso_datetime(value: str) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(value)
    except (TypeError, ValueError):
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


def _parse_iso_date(value: str) -> datetime | None:
    try:
        parsed = date.fromisoformat(value)
    except (TypeError, ValueError):
        return None
    return datetime.combine(parsed, time.min, tzinfo=timezone.utc)
