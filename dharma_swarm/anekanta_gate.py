"""Anekanta (many-sidedness) epistemological gate.

Compatibility wrapper around deterministic Semantic Anekanta v0.
"""

from __future__ import annotations

from pydantic import BaseModel

from dharma_swarm.models import GateResult
from dharma_swarm.semantic_anekanta import (
    MECHANISTIC_KEYWORDS,
    PHENOMENOLOGICAL_KEYWORDS,
    SYSTEMS_KEYWORDS,
    evaluate_semantic_anekanta,
)

_FRAME_MAP: dict[str, frozenset[str]] = {
    "mechanistic": MECHANISTIC_KEYWORDS,
    "phenomenological": PHENOMENOLOGICAL_KEYWORDS,
    "systems": SYSTEMS_KEYWORDS,
}

# ---------------------------------------------------------------------------
# Result model
# ---------------------------------------------------------------------------


class AnekantaResult(BaseModel):
    """Result of an Anekanta epistemological diversity check."""

    gate_result: GateResult
    frames_detected: list[str]
    frame_count: int
    reason: str


# ---------------------------------------------------------------------------
# Core evaluation
# ---------------------------------------------------------------------------


def evaluate_anekanta(description: str, content: str = "") -> AnekantaResult:
    """Evaluate epistemological diversity of a proposal.

    Args:
        description: Short description of the proposal.
        content: Optional longer body / diff / code content.

    Returns:
        AnekantaResult with gate verdict, detected frames, and reason.
    """
    semantic = evaluate_semantic_anekanta(description, content)
    return AnekantaResult(
        gate_result=semantic.gate_result,
        frames_detected=semantic.named_frames,
        frame_count=len(semantic.named_frames),
        reason=semantic.reason,
    )
