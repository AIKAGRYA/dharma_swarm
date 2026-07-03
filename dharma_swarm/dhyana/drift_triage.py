"""Drift triage — rank DEGRADED control surface zones by urgency.

Given N drifted rows from the control surface projector, ranks them by:
  blast_radius × age_days × semantic_centrality

This answers the question: "Which of these 21 DEGRADED zones matters most
right now?" — something no existing mechanism does.

Output is a sorted list of DriftTriageEntry, highest priority first.
The consumer (operator brief, handoff prompt, or control surface UI)
decides what to do about it. Dhyana only observes and recommends.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class DriftTriageEntry:
    """A single drifted zone with computed priority score."""

    row_id: str
    label: str
    coherence_state: str
    kind: str
    owner_module: str
    declared_state: str
    observed_state: str
    blast_radius: float
    age_days: float
    semantic_centrality: float
    priority_score: float = 0.0
    recommended_action: str = ""
    related_br_ids: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.priority_score == 0.0:
            self.priority_score = (
                self.blast_radius * self.age_days * self.semantic_centrality
            )


def _estimate_blast_radius(row: object) -> float:
    """Estimate blast radius from a control surface row.

    Heuristic: count the number of downstream surfaces that depend on this
    zone. Modules in operator_core or board paths have higher blast radius
    than leaf modules.
    """
    owner = getattr(row, "owner_module", "") or ""
    # Core infrastructure has higher blast radius
    if "operator_core" in owner or "board" in owner:
        return 3.0
    if "operator_brief" in owner or "orchestrator" in owner:
        return 2.5
    if "api/" in owner or "dashboard/" in owner:
        return 2.0
    if "dharma_swarm/" in owner:
        return 1.5
    return 1.0


def _estimate_semantic_centrality(row: object) -> float:
    """Estimate semantic centrality of a control surface zone.

    Zones that are referenced by many other zones (control_surface,
    task_board, organism) are more central than leaf entities.
    """
    label = getattr(row, "label", "") or ""
    label_lower = label.lower()
    high_centrality = [
        "control_surface", "task_board", "organism", "kernel",
        "orchestrator", "board", "evolution", "telos",
    ]
    if any(term in label_lower for term in high_centrality):
        return 2.0
    medium_centrality = [
        "operator", "agent", "stigmergy", "cascade", "swarm",
    ]
    if any(term in label_lower for term in medium_centrality):
        return 1.5
    return 1.0


def _estimate_age_days(row: object) -> float:
    """Estimate how long a zone has been drifted.

    Uses the manifest's last_verified or defaults to a conservative 7 days
    if no timestamp is available.
    """
    # In a full implementation, this would check git blame or manifest
    # timestamps. For now, use a default that ensures scoring is meaningful.
    return 7.0


def _match_broken_register(label: str) -> list[str]:
    """Match a drifted zone to known broken register items."""
    label_lower = label.lower()
    matches: list[str] = []
    if "evolution" in label_lower or "darwin" in label_lower:
        matches.append("BR-003")
    if "cron" in label_lower or "scheduler" in label_lower:
        matches.append("BR-004")
    if "algedonic" in label_lower:
        matches.append("BR-005")
    if "identity" in label_lower or "agent_card" in label_lower:
        matches.append("BR-013")
    return matches


def triage_drifted_zones(rows: list[object] | None = None) -> list[DriftTriageEntry]:
    """Triage all DEGRADED/drifted zones from the control surface.

    If rows is None, attempts to build them from the control surface
    projector. Returns a priority-sorted list (highest first).

    Each row is expected to have attributes:
        id, label, coherence_state, kind, owner_module,
        declared_state, observed_state, next_action
    """
    if rows is None:
        try:
            from dharma_swarm.operator_core.control_surface import (
                build_control_surface_rows,
            )
            rows = build_control_surface_rows()
        except ImportError:
            logger.warning("control_surface module not available; cannot triage")
            return []
        except Exception as exc:
            logger.warning("control surface projection failed: %s", exc)
            return []

    degraded_states = ("drifted", "declared_only", "partial")
    entries: list[DriftTriageEntry] = []

    for row in rows:
        state = getattr(row, "coherence_state", "")
        if state not in degraded_states:
            continue

        label = getattr(row, "label", "") or ""
        blast_radius = _estimate_blast_radius(row)
        age_days = _estimate_age_days(row)
        semantic_centrality = _estimate_semantic_centrality(row)
        related_brs = _match_broken_register(label)

        entry = DriftTriageEntry(
            row_id=getattr(row, "id", ""),
            label=label,
            coherence_state=state,
            kind=getattr(row, "kind", ""),
            owner_module=getattr(row, "owner_module", "") or "",
            declared_state=getattr(row, "declared_state", "") or "",
            observed_state=getattr(row, "observed_state", "") or "",
            blast_radius=blast_radius,
            age_days=age_days,
            semantic_centrality=semantic_centrality,
            recommended_action=getattr(row, "next_action", "") or "",
            related_br_ids=related_brs,
        )
        entries.append(entry)

    # Sort by priority score, highest first
    entries.sort(key=lambda e: e.priority_score, reverse=True)

    logger.info(
        "drift_triage: %d zones triaged, top=%s (score=%.1f)",
        len(entries),
        entries[0].label if entries else "none",
        entries[0].priority_score if entries else 0.0,
    )

    return entries
