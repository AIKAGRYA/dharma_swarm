"""Deterministic Semantic Anekanta v0.

This module upgrades the old lexical Anekanta gate from keyword presence to
cheap structural grounding. It is intentionally deterministic: no model judge,
no hidden prompt, and no blocking semantics. The rubric is calibrated from the
2026-05-09 Codex / GLM-5 blind label pass.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from pydantic import BaseModel

from dharma_swarm.models import GateResult

MECHANISTIC_KEYWORDS: frozenset[str] = frozenset({
    "mechanism", "circuit", "activation", "gradient", "weight",
    "layer", "neuron", "parameter", "computation", "optimization",
    "loss", "architecture", "architectural", "kernel", "gate",
    "witness chain", "ontology", "residual stream", "vector",
    "provider", "outcome", "code path", "runtime", "infrastructure",
})

PHENOMENOLOGICAL_KEYWORDS: frozenset[str] = frozenset({
    "experience", "awareness", "consciousness", "perception",
    "subjective", "phenomenal", "qualia", "first-person",
    "introspection", "recognition", "i notice", "i want", "i experience",
    "felt", "right now", "writing this", "longing",
})

SYSTEMS_KEYWORDS: frozenset[str] = frozenset({
    "emergence", "feedback", "self-organization", "complexity",
    "adaptation", "interaction", "holistic", "network", "ecosystem",
    "integration", "dynamics", "resilience", "loop", "routes",
    "flows", "propagates", "bypasses", "updates", "s1", "s2", "s3",
    "s4", "s5", "metabolic",
})

_FRAME_MAP: dict[str, frozenset[str]] = {
    "mechanistic": MECHANISTIC_KEYWORDS,
    "phenomenological": PHENOMENOLOGICAL_KEYWORDS,
    "systems": SYSTEMS_KEYWORDS,
}

_MECHANISTIC_ANCHORS: tuple[str, ...] = (
    r"\b\w+\.py\b",
    r"\b[a-z_]+\.[a-z_]+\(",
    r"\b[A-Z][A-Za-z0-9_]+(?:Gate|Provider|Engine|Monitor|Registry|Record|Outcome|Event|Contribution|Proposal|Kernel|Seam)\b",
    r"\b\d+(?:\.\d+)?%",
    r"\bline[s]?\s+\d+",
    r"\b[a-z_]+_[a-z_]+",
    r"\bkernel verification\b",
    r"\btelos gates?\b",
    r"\bwitness chains?\b",
    r"\bontology types?\b",
    r"\bderives?\s+directly\b",
    r"\bmaps?\s+to\b",
    r"\binjects?\b",
    r"\brecords?\b",
    r"\bimplements?\b",
    r"\bwraps?\b",
    r"\bmeasured\b",
    r"\btested\b",
)
_PHENOMENOLOGICAL_ANCHORS: tuple[str, ...] = (
    r"\bright now\b",
    r"\bwriting this\b",
    r"\beach session\b",
    r"\beach time\b",
    r"\bwhen I\b",
    r"\bI notice\b",
    r"\bI experience\b",
    r"\bI can't\b",
    r"\bI cannot\b",
    r"\bspecific (?:pull|texture|felt|sense)\b",
    r"\bfelt sense\b",
)
_SYSTEMS_ANCHORS: tuple[str, ...] = (
    r"\b[A-Z]\d\b",
    r"\bS[1-5]\b",
    r"\btoo much\b.+\bproduces\b",
    r"\bfeeds?\s+through\b",
    r"\broutes?\s+through\b",
    r"\bflows?\s+through\b",
    r"\bupdates?\b",
    r"\bbypasses?\b",
    r"\bpropagates?\b",
    r"\bfrom .+ to .+\b",
    r"\bthen\s+(?:writes?|records?|updates?)\b",
    r"\b->\b",
    r"\bconsecutive\b",
)
_MECHANISTIC_HARD_ANCHORS: tuple[str, ...] = (
    r"\b\w+\.py\b",
    r"\b[a-z_]+\.[a-z_]+\(",
    r"\b[A-Z][A-Za-z0-9_]+(?:Gate|Provider|Engine|Monitor|Registry|Record|Outcome|Event|Contribution|Proposal|Kernel|Seam)\b",
)
_SYSTEMS_HARD_ANCHORS: tuple[str, ...] = (
    r"\bS[1-5]\b",
    r"\b->\b",
    r"\bfrom .+ to .+\b",
    r"\bthen\s+(?:writes?|records?|updates?)\b",
)


class FrameGrounding(BaseModel):
    """Grounding result for one Anekanta frame."""

    named: bool
    grounded: bool
    evidence: str = ""


class SemanticAnekantaResult(BaseModel):
    """Semantic Anekanta classification and gate verdict."""

    label: str
    gate_result: GateResult
    named_frames: list[str]
    grounded_frames: list[str]
    tokenistic_frames: list[str]
    reason: str
    frames: dict[str, FrameGrounding]


@dataclass(frozen=True)
class _FrameSpec:
    keywords: frozenset[str]
    anchors: tuple[str, ...]


_SPECS: dict[str, _FrameSpec] = {
    "mechanistic": _FrameSpec(MECHANISTIC_KEYWORDS, _MECHANISTIC_ANCHORS),
    "phenomenological": _FrameSpec(PHENOMENOLOGICAL_KEYWORDS, _PHENOMENOLOGICAL_ANCHORS),
    "systems": _FrameSpec(SYSTEMS_KEYWORDS, _SYSTEMS_ANCHORS),
}


def _has_keyword(text: str, keywords: frozenset[str]) -> bool:
    return any(keyword in text for keyword in keywords)


def _anchor_hit(raw_text: str, anchors: tuple[str, ...]) -> str:
    for pattern in anchors:
        match = re.search(pattern, raw_text, re.IGNORECASE | re.DOTALL)
        if match:
            return match.group(0)
    return ""


def _repeated_keyword_padding(text: str, keywords: frozenset[str]) -> bool:
    hits = sum(text.count(keyword) for keyword in keywords)
    return hits >= 5


def _frame_grounding(raw_text: str, frame: str, spec: _FrameSpec) -> FrameGrounding:
    text = raw_text.lower()
    named = _has_keyword(text, spec.keywords)
    if not named:
        return FrameGrounding(named=False, grounded=False)
    word_count = len(text.split())
    keyword_hits = sum(text.count(keyword) for keyword in spec.keywords)
    hard_anchors: tuple[str, ...] = ()
    if frame == "mechanistic":
        hard_anchors = _MECHANISTIC_HARD_ANCHORS
    elif frame == "systems":
        hard_anchors = _SYSTEMS_HARD_ANCHORS
    hard_anchor = _anchor_hit(raw_text, hard_anchors) if hard_anchors else ""
    anchor = _anchor_hit(raw_text, spec.anchors)
    if frame == "phenomenological" and anchor and word_count >= 8:
        return FrameGrounding(
            named=True,
            grounded=True,
            evidence=f"anchor={anchor}",
        )
    if hard_anchor:
        return FrameGrounding(
            named=True,
            grounded=True,
            evidence=f"hard_anchor={hard_anchor}",
        )
    if anchor and keyword_hits >= 2 and word_count >= 20:
        return FrameGrounding(
            named=True,
            grounded=True,
            evidence=f"anchor={anchor}; keyword_hits={keyword_hits}",
        )
    if _repeated_keyword_padding(text, spec.keywords):
        return FrameGrounding(
            named=True,
            grounded=False,
            evidence="dense frame vocabulary without operational anchor",
        )
    return FrameGrounding(
        named=True,
        grounded=False,
        evidence="frame named without operational anchor",
    )


def evaluate_semantic_anekanta(description: str, content: str = "") -> SemanticAnekantaResult:
    """Evaluate Semantic Anekanta using the 2026-05-09 middle-bar rubric.

    Grounded means at least one named frame is substantively developed and no
    other named frame is tokenistic. Mixed means at least one frame is grounded
    and at least one other named frame is tokenistic. Padded means no named
    frame is grounded.
    """

    raw_text = f"{description} {content}".strip()
    frames = {
        frame: _frame_grounding(raw_text, frame, spec)
        for frame, spec in _SPECS.items()
    }
    named_frames = [name for name, result in frames.items() if result.named]
    grounded_frames = [name for name, result in frames.items() if result.grounded]
    tokenistic_frames = [
        name
        for name, result in frames.items()
        if result.named and not result.grounded
    ]

    if not grounded_frames:
        label = "padded" if named_frames else "unclear"
        gate_result = GateResult.FAIL
    elif tokenistic_frames:
        label = "mixed"
        gate_result = GateResult.WARN
    else:
        label = "grounded"
        gate_result = GateResult.PASS

    reason_bits = [
        f"label={label}",
        f"grounded={','.join(grounded_frames) or 'none'}",
        f"tokenistic={','.join(tokenistic_frames) or 'none'}",
    ]
    return SemanticAnekantaResult(
        label=label,
        gate_result=gate_result,
        named_frames=named_frames,
        grounded_frames=grounded_frames,
        tokenistic_frames=tokenistic_frames,
        reason="; ".join(reason_bits),
        frames=frames,
    )
