"""Panel diversity provenance gate — the "receipt, not vibes" check.

Origin: a 2026-07-01 live research + adjudication exercise (4 lensed review
agents on a proposed multi-agent "signal deliberation" system) independently
concluded, via two separate lenses, that the exercise's OWN construction — N
role-prompted calls to one underlying model — was itself an instance of the
exact failure it was meant to catch: multi-agent "deliberation" over a single
model's correlated samples produces no more answer diversity than one call
(Ringelmann effect; memetic drift). CLAUDE.md's Transcendence Principle already
states the negative case as the default expectation: "Same model prompted
differently may NOT suffice."

This module makes that a mechanically-checkable gate instead of an assertion.
It mirrors ``dharma_swarm/council/invariants.py``'s decorrelated-moat pattern
(``MIN_EVALUATOR_FAMILIES``/``MIN_SOURCE_FAMILIES`` / ``meets_decorrelation``)
but Council's own invariant is scoped to arena trace verification and
deliberately carries no significance/correctness vocabulary — so this is a new,
narrow primitive, not a Council profile. It is deliberately NOT a full "signal
council" or debate system: it only answers one question — given a set of
panel-lens-to-provider assignments (and optionally their reasoning text), is
there real cause to trust that the panel's agreement reflects genuine diversity
of competence, or is it a single-model multi-persona pass wearing a consensus
costume?

Fails closed: with fewer than ``min_families`` distinct providers actually
dispatched, the verdict is never "genuine_diversity" — regardless of how the
lenses argued or how unanimous they were.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

from dharma_swarm.model_hierarchy import CANONICAL_SEED_ORDER, default_model
from dharma_swarm.models import ProviderType

# Same floor as the Council's decorrelated moat (council/invariants.py). Kept
# as an independent constant here rather than imported: this module governs a
# different domain (panel-lens dispatch diversity, not evaluator/source
# corroboration for arena traces) and must not accidentally couple its
# lifecycle to Council's.
MIN_LENS_PROVIDER_FAMILIES = 2

# Above this pairwise shingle-Jaccard overlap on content-bearing tokens, two
# lenses' stated reasoning is treated as suspiciously convergent text — a
# signal of memetic drift (one lens's phrasing became the template for
# another's) even when their nominal verdicts differ.
REASONING_OVERLAP_SUSPICION_THRESHOLD = 0.55

PanelVerdict = Literal["genuine_diversity", "single_model_multi_persona", "insufficient_data"]

_STOPWORDS = frozenset(
    "a an the of to in on for and or is are was were be been being this that "
    "these those it its as at by with from not no".split()
)


@dataclass(frozen=True)
class LensAssignment:
    """One panel seat: a named role dispatched to a specific provider."""

    role: str
    provider: ProviderType


@dataclass(frozen=True)
class PanelDiversityReport:
    distinct_provider_count: int
    provider_types_used: tuple[str, ...]
    distinct_model_family_count: int
    model_families_used: tuple[str, ...]
    meets_family_floor: bool
    suspected_memetic_drift: bool
    overlapping_role_pairs: tuple[tuple[str, str], ...]
    verdict: PanelVerdict
    safe_to_trust_consensus: bool

    def to_json(self) -> dict[str, object]:
        return {
            "distinct_provider_count": self.distinct_provider_count,
            "provider_types_used": list(self.provider_types_used),
            "distinct_model_family_count": self.distinct_model_family_count,
            "model_families_used": list(self.model_families_used),
            "meets_family_floor": self.meets_family_floor,
            "suspected_memetic_drift": self.suspected_memetic_drift,
            "overlapping_role_pairs": [list(pair) for pair in self.overlapping_role_pairs],
            "verdict": self.verdict,
            "safe_to_trust_consensus": self.safe_to_trust_consensus,
        }


def assign_diverse_lenses(
    roles: tuple[str, ...],
    candidate_providers: tuple[ProviderType, ...] = CANONICAL_SEED_ORDER,
) -> tuple[LensAssignment, ...]:
    """Assign each role a provider, round-robin over the candidate pool.

    Providers are NOT guaranteed distinct (see below): this is the assignment
    half only. Whether the resulting assignment actually achieves provider
    diversity is judged separately by ``check_panel_diversity``, never
    assumed here (Copilot review finding, panel_diversity.py:99).

    This is the routing half of the fix: wire ``preferred_provider`` (already
    supported by ``ProviderRouteRequest.context`` / ``ProviderPolicyRouter``,
    see provider_policy.py's explicit-wins short-circuit) so each lens actually
    dispatches to a different model family instead of silently resolving to
    whichever single lane is cheapest/fastest right now.

    If there are more roles than candidate providers, providers repeat (a
    warning condition the caller should surface — this function does not raise,
    it only assigns; ``check_panel_diversity`` is what judges the result).
    """
    if not candidate_providers:
        raise ValueError("candidate_providers must be non-empty")
    return tuple(
        LensAssignment(role=role, provider=candidate_providers[i % len(candidate_providers)])
        for i, role in enumerate(roles)
    )


def check_panel_diversity(
    assignments: tuple[LensAssignment, ...],
    reasoning_by_role: dict[str, str] | None = None,
    *,
    min_families: int = MIN_LENS_PROVIDER_FAMILIES,
) -> PanelDiversityReport:
    """The provenance gate: is this panel's diversity real, absent, or unknown?

    Mirrors ``meets_decorrelation``'s shape (a hard family-count floor) plus an
    optional textual-overlap check when reasoning transcripts are available.
    Fails closed on every ambiguous path: no assignments, or below the family
    floor, never yields "genuine_diversity".
    """
    if not assignments:
        return PanelDiversityReport(
            distinct_provider_count=0,
            provider_types_used=(),
            distinct_model_family_count=0,
            model_families_used=(),
            meets_family_floor=False,
            suspected_memetic_drift=False,
            overlapping_role_pairs=(),
            verdict="insufficient_data",
            safe_to_trust_consensus=False,
        )

    provider_types_used = tuple(sorted({a.provider.value for a in assignments}))
    model_families_used = tuple(sorted({_model_family(a.provider) for a in assignments}))
    meets_floor = len(model_families_used) >= min_families

    overlapping_pairs: list[tuple[str, str]] = []
    if reasoning_by_role and len(reasoning_by_role) >= 2:
        roles = sorted(reasoning_by_role)
        for i, role_a in enumerate(roles):
            for role_b in roles[i + 1 :]:
                overlap = _shingle_jaccard(reasoning_by_role[role_a], reasoning_by_role[role_b])
                if overlap > REASONING_OVERLAP_SUSPICION_THRESHOLD:
                    overlapping_pairs.append((role_a, role_b))
    suspected_drift = bool(overlapping_pairs)

    if not meets_floor:
        verdict: PanelVerdict = "single_model_multi_persona"
        safe = False
    elif suspected_drift:
        # Real provider diversity but suspiciously convergent phrasing: don't
        # claim genuine diversity outright, but this isn't the single-model
        # case either. Treat as not-yet-trustworthy rather than guessing.
        verdict = "insufficient_data"
        safe = False
    else:
        verdict = "genuine_diversity"
        safe = True

    return PanelDiversityReport(
        distinct_provider_count=len(provider_types_used),
        provider_types_used=provider_types_used,
        distinct_model_family_count=len(model_families_used),
        model_families_used=model_families_used,
        meets_family_floor=meets_floor,
        suspected_memetic_drift=suspected_drift,
        overlapping_role_pairs=tuple(overlapping_pairs),
        verdict=verdict,
        safe_to_trust_consensus=safe,
    )


def _model_family(provider: ProviderType) -> str:
    model = default_model(provider).strip().lower()
    if not model:
        return provider.value
    normalized = model.replace("_", "-")
    if "claude-" in normalized:
        return "claude"
    if "gpt-" in normalized:
        return "gpt"
    if "qwen3-coder" in normalized or "qwen-3-coder" in normalized:
        return "qwen3-coder"
    if "qwen3" in normalized or "qwen-3" in normalized:
        return "qwen3"
    if "llama-3.3" in normalized or "llama3.3" in normalized:
        return "llama-3.3"
    if "deepseek" in normalized:
        return "deepseek"
    if "kimi" in normalized:
        return "kimi"
    if "glm" in normalized:
        return "glm"
    if "gemini" in normalized:
        return "gemini"
    if "mistral" in normalized:
        return "mistral"
    return normalized.split("/", 1)[-1].split(":", 1)[0]


def _shingle_jaccard(text_a: str, text_b: str, shingle_size: int = 3) -> float:
    """Trigram-shingle Jaccard overlap on content-bearing tokens.

    Dependency-free (no numpy/sklearn) so this stays cheap to run on every
    panel cycle. Not a semantic similarity measure — it catches shared
    *phrasing*, which is exactly the memetic-drift signature (one lens's
    template becoming another's), not shared topic (which is expected and
    fine).
    """
    shingles_a = _shingles(text_a, shingle_size)
    shingles_b = _shingles(text_b, shingle_size)
    if not shingles_a or not shingles_b:
        return 0.0
    intersection = shingles_a & shingles_b
    union = shingles_a | shingles_b
    return len(intersection) / len(union) if union else 0.0


def _shingles(text: str, size: int) -> set[tuple[str, ...]]:
    tokens = [t for t in re.findall(r"[a-z0-9]+", text.lower()) if t not in _STOPWORDS]
    if len(tokens) < size:
        return set()
    return {tuple(tokens[i : i + size]) for i in range(len(tokens) - size + 1)}


__all__ = [
    "MIN_LENS_PROVIDER_FAMILIES",
    "REASONING_OVERLAP_SUSPICION_THRESHOLD",
    "LensAssignment",
    "PanelDiversityReport",
    "PanelVerdict",
    "assign_diverse_lenses",
    "check_panel_diversity",
]
