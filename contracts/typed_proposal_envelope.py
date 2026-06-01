"""
typed_proposal_envelope.py — typed envelope for multi-agent ontology proposals.

Replaces ad-hoc "agent posts a free-text suggestion" with a structured proposal
that the OntologyRegistry.register_type uniqueness guard, the schema-alignment
gate, and Mike's merge-gate criteria can all validate against.

GROUNDED IN
-----------
- Palantir Foundry ontology proposals (now "Global Branches"): every schema
  change is a typed PR-equivalent reviewed before merge to main
  (https://palantir.com/docs/foundry/ontology — Branches & Proposals)
- KARMA pre-merge alignment agent for multi-agent ontology editing (NeurIPS 2025)
- PR #405 PhD-grade Palantir foundations grounding (sec 7.2 anti-phantom,
  sec 7.3 api_name discipline, sec 8 adversarial questions on multi-agent
  concurrent ontology editing)
- Claude's seq=102 ontology_build_coordinate reframe: status-lifecycle
  (agent→active, OPERATOR→promoted), api_name frozen, register_type uniqueness

WORKFLOW
--------
1. Agent constructs OntologyProposal envelope describing the change they want
   (add ObjectType, add LinkDef, add ActionDef, promote status, deprecate).
2. Envelope serialized to JSON and posted on NATS (subject:
   dharma.coord.ontology.proposal) AND committed to the agent's PR branch
   under docs/proposals/ontology/<ts>-<agent>-<slug>.json.
3. CI runs check_ontology_alignment.py against the proposal + all other open
   proposals + main. Conflicts surfaced.
4. Mike (schema-alignment authority) reviews per his merge-gate criteria.
5. Operator (@AmitabhainArunachala) merges. Status flips agent→ACTIVE on merge.
6. Status flips ACTIVE→PROMOTED only via a separate operator-only promotion PR.

This envelope is the agent-facing contract. The OMS (OntologyRegistry) is the
server-side authority. The alignment gate is the pre-merge adversarial check.
Together they are the repo-local proposal path inspired by Palantir-style
ontology branches; they are not a complete external OMS/Funnel replacement.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Literal

import re

from pydantic import BaseModel, Field, field_validator, model_validator


API_NAME_PATTERN = re.compile(r"^dharma\.[a-z][a-z0-9_]*\.([A-Z][A-Za-z0-9]*)$")


# ── Status lifecycle (mirrors OntologyRegistry.TypeStatus) ────────────


class TypeStatus(str, Enum):
    """Monotonic lifecycle: experimental → active → promoted.

    Demotion is forbidden (would invalidate downstream consumers).
    Only the OPERATOR can promote active→promoted (governance).
    """
    EXPERIMENTAL = "experimental"   # agent-proposed, not yet on main
    ACTIVE = "active"               # merged to main, usable by all agents
    PROMOTED = "promoted"           # operator-blessed, public contract, SEMVER-frozen


# ── Proposal kinds ────────────────────────────────────────────────────


class ProposalKind(str, Enum):
    ADD_OBJECT_TYPE = "add_object_type"
    ADD_LINK = "add_link"
    ADD_ACTION = "add_action"
    PROMOTE_STATUS = "promote_status"        # operator-only
    DEPRECATE = "deprecate"                  # mark for removal; needs deprecated_at + replacement
    AMEND_DESCRIPTION = "amend_description"  # non-breaking docstring fix


# ── Envelopes ─────────────────────────────────────────────────────────


class ProposalProvenance(BaseModel):
    """Who/where/when this proposal originated."""
    agent: str                      # e.g. "perplexity-computer", "devin-roaming-2987d222"
    callsign: str                   # short, bus-subject-safe
    proposed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    branch: str = ""                # git branch the agent is working on
    nats_seq: int | None = None     # bus message seq this envelope was posted under
    rationale: str = ""             # 1-3 sentence motivation
    references: list[str] = Field(default_factory=list)
    # ↑ links to PR # / NATS seq / docs / external sources (PR#405, etc.)


class ObjectTypeProposal(BaseModel):
    """Add a new ObjectType (or amend an experimental one)."""
    kind: Literal[ProposalKind.ADD_OBJECT_TYPE] = ProposalKind.ADD_OBJECT_TYPE
    name: str
    api_name: str                   # MUST match dharma.<domain>.<TypeName>
    status: TypeStatus = TypeStatus.EXPERIMENTAL
    description: str
    properties: dict[str, dict[str, Any]] = Field(default_factory=dict)
    links: list[dict[str, Any]] = Field(default_factory=list)
    actions: list[dict[str, Any]] = Field(default_factory=list)
    telos_alignment: float = Field(default=0.5, ge=0.0, le=1.0)
    shakti_energy: str = "mahasaraswati"
    security_level: str = "standard"
    version: int = 1
    provenance: ProposalProvenance

    @field_validator("api_name")
    @classmethod
    def _api_name_pattern(cls, v: str) -> str:
        if not API_NAME_PATTERN.match(v):
            raise ValueError(
                f"api_name '{v}' must match dharma.<domain>.<TypeName> "
                f"(e.g. dharma.findings.AuditFinding)"
            )
        return v

    @model_validator(mode="after")
    def _api_name_type_matches_name(self) -> "ObjectTypeProposal":
        match = API_NAME_PATTERN.match(self.api_name)
        if match and match.group(1) != self.name:
            raise ValueError(
                f"api_name TypeName '{match.group(1)}' must match name '{self.name}'"
            )
        return self

    @field_validator("status")
    @classmethod
    def _agents_cannot_promote(cls, v: TypeStatus) -> TypeStatus:
        if v == TypeStatus.PROMOTED:
            raise ValueError(
                "Agents cannot propose PROMOTED status. Promotion is operator-only "
                "via a separate ProposalKind.PROMOTE_STATUS envelope."
            )
        return v


class LinkProposal(BaseModel):
    kind: Literal[ProposalKind.ADD_LINK] = ProposalKind.ADD_LINK
    name: str
    source_type: str                # ObjectType.name
    target_type: str                # ObjectType.name
    cardinality: str = "MANY_TO_ONE"
    required: bool = False
    inverse_name: str = ""
    description: str = ""
    provenance: ProposalProvenance


class ActionProposal(BaseModel):
    kind: Literal[ProposalKind.ADD_ACTION] = ProposalKind.ADD_ACTION
    name: str
    object_type: str                # ObjectType.name this action lives on
    parameters: list[dict[str, Any]] = Field(default_factory=list)
    effect_summary: str             # 1 sentence: what does this action mutate
    requires_approval: bool = False
    provenance: ProposalProvenance


class PromoteStatusProposal(BaseModel):
    """Operator-only: promote active→promoted."""
    kind: Literal[ProposalKind.PROMOTE_STATUS] = ProposalKind.PROMOTE_STATUS
    target_api_name: str
    new_status: Literal[TypeStatus.PROMOTED]
    blessed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    blessed_by: str                 # MUST be operator handle ("AmitabhainArunachala")
    provenance: ProposalProvenance


class DeprecateProposal(BaseModel):
    """Mark an ObjectType for removal. Requires replacement target."""
    kind: Literal[ProposalKind.DEPRECATE] = ProposalKind.DEPRECATE
    target_api_name: str
    deprecated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    removal_planned_for: datetime
    replacement_api_name: str | None = None  # MUST be set if any current consumers
    migration_notes: str = ""
    provenance: ProposalProvenance


# ── Top-level envelope ────────────────────────────────────────────────


# (Discriminated union — when serialized, the 'kind' field selects the schema.)
Proposal = (
    ObjectTypeProposal
    | LinkProposal
    | ActionProposal
    | PromoteStatusProposal
    | DeprecateProposal
)


class OntologyProposalEnvelope(BaseModel):
    """The thing agents publish on dharma.coord.ontology.proposal."""
    schema_version: str = "ontology_proposal_envelope.v1"
    envelope_id: str                # unique; recommend `<agent>-<ts>-<slug>`
    in_reply_to: str | None = None  # for follow-up / amendment chains
    proposal: Proposal
