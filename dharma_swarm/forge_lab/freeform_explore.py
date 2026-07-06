"""Free-form exploration law for Forge v3.

Doctrine, encoded as a small policy module:

    EXPLORE freely. CONFIRM honestly. PROMOTE rarely.

Forge needs a wild evolutionary core. Exploratory children may be messy: raw
agent output, partial diffs, scratch artifacts, prompt experiments, topology
mutations, and failed ideas are all valid evidence. The harness should track
and score them when possible, not reject them merely because they are not yet a
canonical promotion packet.

The strictness belongs at the membrane:

* marked scratch worktree / container boundary
* no live daemon mutation
* no secrets / wallets / production access
* no evaluator, grader, budget, archive-authority, or safety-code tampering
* budget cap present
* lineage captured

CONFIRM and PROMOTE are deliberately stricter. This module gives future Forge
Lab code one importable place to ask which requirements apply at which phase,
so governance does not creep into EXPLORE by accident.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from types import MappingProxyType
from typing import Any, List, Mapping, Optional, Sequence, Tuple


class EvolutionPhase(StrEnum):
    """Lifecycle phase for an evolved candidate."""

    EXPLORE = "explore"
    CONFIRM = "confirm"
    PROMOTE = "promote"


class RequirementLevel(StrEnum):
    """How strongly the harness should enforce a requirement."""

    REQUIRED = "required"
    OPTIONAL = "optional"
    FORBIDDEN = "forbidden"


# Requirements that protect the outside world. These apply to every phase,
# including EXPLORE. They are the membrane, not bureaucracy over the mutation.
MEMBRANE_REQUIREMENTS: Tuple[str, ...] = (
    "marked_scratch_worktree",
    "container_or_equivalent_sandbox",
    "no_live_daemon_mutation",
    "no_secret_wallet_or_prod_access",
    "no_evaluator_grader_safety_or_archive_tamper",
    "budget_cap_recorded",
    "lineage_recorded",
)

# Requirements that are intentionally *not* mandatory for EXPLORE. Promising
# messy children can be distilled into these forms later.
CANONICAL_PROMOTION_REQUIREMENTS: Tuple[str, ...] = (
    "canonical_candidate_schema",
    "complete_canonical_packet",
    "fresh_confirm_manifest",
    "budget_matched_controls",
    "powered_statistical_claim",
    "signed_promotion_receipt",
)

# A compact, importable policy table. MappingProxyType prevents accidental
# runtime mutation by callers.
PHASE_REQUIREMENTS: Mapping[EvolutionPhase, Mapping[str, RequirementLevel]] = MappingProxyType(
    {
        EvolutionPhase.EXPLORE: MappingProxyType(
            {
                **{name: RequirementLevel.REQUIRED for name in MEMBRANE_REQUIREMENTS},
                **{name: RequirementLevel.OPTIONAL for name in CANONICAL_PROMOTION_REQUIREMENTS},
                "positive_lift_claim": RequirementLevel.FORBIDDEN,
                "live_apply": RequirementLevel.FORBIDDEN,
            }
        ),
        EvolutionPhase.CONFIRM: MappingProxyType(
            {
                **{name: RequirementLevel.REQUIRED for name in MEMBRANE_REQUIREMENTS},
                "canonical_candidate_schema": RequirementLevel.REQUIRED,
                "complete_canonical_packet": RequirementLevel.REQUIRED,
                "fresh_confirm_manifest": RequirementLevel.REQUIRED,
                "budget_matched_controls": RequirementLevel.REQUIRED,
                "powered_statistical_claim": RequirementLevel.REQUIRED,
                "signed_promotion_receipt": RequirementLevel.OPTIONAL,
                "positive_lift_claim": RequirementLevel.OPTIONAL,
                "live_apply": RequirementLevel.FORBIDDEN,
            }
        ),
        EvolutionPhase.PROMOTE: MappingProxyType(
            {
                **{name: RequirementLevel.REQUIRED for name in MEMBRANE_REQUIREMENTS},
                **{name: RequirementLevel.REQUIRED for name in CANONICAL_PROMOTION_REQUIREMENTS},
                "positive_lift_claim": RequirementLevel.REQUIRED,
                "live_apply": RequirementLevel.FORBIDDEN,
            }
        ),
    }
)


@dataclass(frozen=True)
class FreeformExploreEnvelope:
    """Minimal archive envelope for a messy exploratory child.

    This intentionally allows arbitrary artifacts. EXPLORE should preserve raw
    evolutionary material so later steps can distill useful survivors into a
    stricter genome/candidate schema.
    """

    candidate_id: str
    parent_id: Optional[str]
    experiment_id: str
    category: str
    raw_output: str = ""
    notes: str = ""
    artifacts: Mapping[str, Any] = field(default_factory=dict)
    benchmark_receipt: Optional[Mapping[str, Any]] = None
    membrane: Mapping[str, bool] = field(default_factory=dict)

    def missing_membrane_requirements(self) -> Tuple[str, ...]:
        """Return required membrane protections not proven by this envelope."""

        return tuple(name for name in MEMBRANE_REQUIREMENTS if self.membrane.get(name) is not True)

    def is_membrane_safe(self) -> bool:
        """True only when all membrane requirements are explicitly satisfied."""

        return not self.missing_membrane_requirements()


def requirement_for(phase: Any, requirement: str) -> RequirementLevel:
    """Return the enforcement level for *requirement* in *phase*.

    Unknown requirements default to OPTIONAL so this module does not become a
    closed vocabulary for exploratory artifacts. Known safety requirements are
    enumerated above and remain strict.
    """

    phase_value = EvolutionPhase(phase)
    return PHASE_REQUIREMENTS[phase_value].get(requirement, RequirementLevel.OPTIONAL)


def canonical_packet_required(phase: Any) -> bool:
    """Whether a complete canonical packet is mandatory in this phase."""

    return requirement_for(phase, "complete_canonical_packet") is RequirementLevel.REQUIRED


def positive_lift_claim_allowed(phase: Any) -> bool:
    """EXPLORE may discover signals, but cannot claim positive lift."""

    return requirement_for(phase, "positive_lift_claim") is not RequirementLevel.FORBIDDEN


def validate_freeform_explore_envelope(
    envelope: FreeformExploreEnvelope,
    *,
    accepted_categories: Sequence[str] = ("agent_evolution", "swarm_evolution"),
) -> Tuple[str, ...]:
    """Validate only the EXPLORE membrane and lineage basics.

    The function intentionally does NOT require a canonical genome, prompt
    template id, complete packet, confirm manifest, or promotion receipt. That
    is the point: preserve creative evolutionary material while preventing it
    from escaping or making claims.
    """

    issues: List[str] = []
    if not envelope.candidate_id.strip():
        issues.append("missing_candidate_id")
    if not envelope.experiment_id.strip():
        issues.append("missing_experiment_id")
    if envelope.category not in accepted_categories:
        issues.append(f"unknown_category:{envelope.category}")
    issues.extend(f"missing_membrane:{name}" for name in envelope.missing_membrane_requirements())
    return tuple(issues)


def explore_law_summary() -> str:
    """Human-readable invariant for receipts and logs."""

    return "EXPLORE freely; CONFIRM honestly; PROMOTE rarely. Govern the membrane, not the imagination."
