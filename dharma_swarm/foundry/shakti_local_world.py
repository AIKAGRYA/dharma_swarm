from __future__ import annotations
import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Protocol, runtime_checkable
from dharma_swarm.foundry.evaluator import canonical_digest
from dharma_swarm.foundry.patches import (
    read_regular_nofollow,
    scoped_regular_file,
    write_immutable_beneath,
)
if TYPE_CHECKING:
    from dharma_swarm.foundry.shakti_system import CycleContext
class ShaktiSystemError(RuntimeError):
    pass
class AuthorityError(ShaktiSystemError):
    pass
class EvidenceError(ShaktiSystemError):
    pass
class CausalityError(ShaktiSystemError):
    pass
class DuplicateEffect(ShaktiSystemError):
    pass
class SystemStopped(ShaktiSystemError):
    pass
def _require_text(value: str, field_name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} is required")
def _digest_prefix(value: str, length: int = 16) -> str:
    return value.removeprefix("sha256:")[:length]
def _require_sha256(value: str, field_name: str) -> None:
    exact_shape = isinstance(value, str) and len(value) == 71 and value.startswith("sha256:")
    if not exact_shape or any(character not in "0123456789abcdef" for character in value[7:]):
        raise EvidenceError(f"{field_name} requires an exact lowercase SHA-256 digest")
@dataclass(frozen=True, slots=True)
class ActionSpec:
    effect_kind: str
    relative_path: str
    content: str
    declared_reversible: bool = True
    def __post_init__(self) -> None:
        _require_text(self.effect_kind, "effect_kind")
        _require_text(self.relative_path, "relative_path")
        _require_text(self.content, "content")
        if self.effect_kind != "write_local_artifact":
            raise ValueError("the MVP only admits write_local_artifact")
        if not self.declared_reversible:
            raise ValueError("the MVP only admits declared-reversible fixture effects")
    def to_dict(self) -> dict[str, object]:
        return {
            "effect_kind": self.effect_kind,
            "relative_path": self.relative_path,
            "content": self.content, "declared_reversible": self.declared_reversible,
        }
    @property
    def operation_hash(self) -> str:
        return canonical_digest(self.to_dict())
@dataclass(frozen=True, slots=True)
class AgentProposal:
    proposal_id: str
    agent_id: str
    context_hash: str
    title: str
    rationale: str
    human_question: str
    predicted_signal: str
    action: ActionSpec
    based_on_observation_id: str = ""
    def __post_init__(self) -> None:
        self.require_valid()
    def require_valid(self) -> None:
        for name in (
            "proposal_id", "agent_id", "context_hash", "title",
            "rationale", "human_question", "predicted_signal",
        ):
            _require_text(getattr(self, name), name)
        if self.proposal_id != canonical_digest(self.identity_payload()):
            raise CausalityError("proposal id does not bind the proposal body")
    @classmethod
    def create(
        cls,
        *,
        agent_id: str,
        context: CycleContext,
        title: str,
        rationale: str,
        human_question: str,
        predicted_signal: str,
        action: ActionSpec,
    ) -> AgentProposal:
        body: dict[str, object] = {
            "agent_id": agent_id,
            "context_hash": context.input_hash,
            "title": title,
            "rationale": rationale,
            "human_question": human_question,
            "predicted_signal": predicted_signal,
            "action": action.to_dict(),
            "based_on_observation_id": context.prior_observation_id,
        }
        return cls(proposal_id=canonical_digest(body), **{**body, "action": action})
    def identity_payload(self) -> dict[str, object]:
        return {
            "agent_id": self.agent_id,
            "context_hash": self.context_hash,
            "title": self.title,
            "rationale": self.rationale,
            "human_question": self.human_question,
            "predicted_signal": self.predicted_signal,
            "action": self.action.to_dict(),
            "based_on_observation_id": self.based_on_observation_id,
        }
    def to_dict(self) -> dict[str, object]:
        return {"proposal_id": self.proposal_id, **self.identity_payload()}
@dataclass(frozen=True, slots=True)
class Deliberation:
    deliberation_id: str
    context: CycleContext
    proposals: tuple[AgentProposal, ...]
    recommended_proposal_id: str
    def __post_init__(self) -> None:
        self.require_valid()
    @classmethod
    def create(
        cls,
        *,
        context: CycleContext,
        proposals: tuple[AgentProposal, ...],
        recommended_proposal_id: str,
    ) -> Deliberation:
        body = {
            "context_hash": context.input_hash,
            "proposal_ids": [proposal.proposal_id for proposal in proposals],
            "recommended_proposal_id": recommended_proposal_id,
        }
        return cls(canonical_digest(body), context, proposals, recommended_proposal_id)
    def identity_payload(self) -> dict[str, object]:
        return {
            "context_hash": self.context.input_hash,
            "proposal_ids": [proposal.proposal_id for proposal in self.proposals],
            "recommended_proposal_id": self.recommended_proposal_id,
        }
    def require_valid(self) -> None:
        if not self.proposals:
            raise CausalityError("deliberation requires at least one proposal")
        proposal_ids = [proposal.proposal_id for proposal in self.proposals]
        if len(proposal_ids) != len(set(proposal_ids)):
            raise CausalityError("deliberation contains duplicate proposal identities")
        if self.recommended_proposal_id not in proposal_ids:
            raise CausalityError("recommended proposal is outside the deliberation")
        if self.deliberation_id != canonical_digest(self.identity_payload()):
            raise CausalityError("deliberation id does not bind its context and proposals")
        intent = self.context.intent
        for proposal in self.proposals:
            proposal.require_valid()
            if proposal.context_hash != self.context.input_hash:
                raise CausalityError("proposal does not bind this deliberation context")
            if proposal.based_on_observation_id != self.context.prior_observation_id:
                raise CausalityError("proposal changes the prior observation")
            if proposal.action.effect_kind != intent.allowed_effect_kind:
                raise AuthorityError("proposal effect is outside the intent contract")
            if proposal.action.effect_kind in intent.prohibited_effects:
                raise AuthorityError("proposal effect is explicitly prohibited")
    def proposal(self, proposal_id: str) -> AgentProposal:
        for proposal in self.proposals:
            if proposal.proposal_id == proposal_id:
                return proposal
        raise AuthorityError("grant targets a proposal outside this deliberation")
    def to_dict(self) -> dict[str, object]:
        return {
            "deliberation_id": self.deliberation_id,
            "context": self.context.to_dict(),
            "proposals": [proposal.to_dict() for proposal in self.proposals],
            "recommended_proposal_id": self.recommended_proposal_id,
        }
def expected_approval(proposal: AgentProposal) -> str:
    return f"approve {_digest_prefix(proposal.proposal_id)}"
@dataclass(frozen=True, slots=True)
class AuthorityGrant:
    grant_id: str
    intent_id: str
    proposal_id: str
    actor_id: str
    approved: bool
    typed_confirmation: str
    reason: str
    def __post_init__(self) -> None:
        if type(self.approved) is not bool:
            raise ValueError("approved must be a boolean")
        if self.grant_id != canonical_digest(self.identity_payload()):
            raise AuthorityError("grant id does not bind the grant body")
    @classmethod
    def approve(
        cls,
        deliberation: Deliberation,
        proposal_id: str,
        *,
        actor_id: str,
        typed_confirmation: str,
        reason: str,
    ) -> AuthorityGrant:
        body = {
            "intent_id": deliberation.context.intent.intent_id,
            "proposal_id": proposal_id,
            "actor_id": actor_id,
            "approved": True,
            "typed_confirmation": typed_confirmation,
            "reason": reason,
        }
        return cls(grant_id=canonical_digest(body), **body)
    def identity_payload(self) -> dict[str, object]:
        return {
            "intent_id": self.intent_id,
            "proposal_id": self.proposal_id,
            "actor_id": self.actor_id,
            "approved": self.approved,
            "typed_confirmation": self.typed_confirmation,
            "reason": self.reason,
        }
    def to_dict(self) -> dict[str, object]:
        return {"grant_id": self.grant_id, **self.identity_payload()}
def validate_authority_grant(
    deliberation: Deliberation,
    proposal: AgentProposal,
    grant: AuthorityGrant,
) -> None:
    deliberation.require_valid()
    if deliberation.proposal(proposal.proposal_id) != proposal:
        raise CausalityError("proposal body differs from the admitted deliberation")
    intent = deliberation.context.intent
    if grant.approved is not True:
        raise AuthorityError("proposal was not approved")
    if grant.grant_id != canonical_digest(grant.identity_payload()):
        raise AuthorityError("grant identity changed after creation")
    if grant.proposal_id != proposal.proposal_id:
        raise AuthorityError("grant targets another proposal")
    if grant.intent_id != intent.intent_id or grant.actor_id != intent.owner_id:
        raise AuthorityError("grant actor or intent does not match the contract")
    if grant.typed_confirmation != expected_approval(proposal):
        raise AuthorityError("grant does not contain the exact proposal confirmation")
    if not grant.reason.strip():
        raise AuthorityError("grant requires a human reason")
@dataclass(frozen=True, slots=True)
class WorldObservation:
    observation_id: str
    proposal_id: str
    operation_hash: str
    status: str
    observed_by: str
    observed_facts: tuple[str, ...]
    artifact_locator: str
    artifact_digest: str
    evidence_authority: str = "local_fixture"
    external_world_contact: bool = False
    def __post_init__(self) -> None:
        self.require_valid()
    def require_valid(self) -> None:
        for name in ("proposal_id", "operation_hash", "observed_by", "artifact_locator"):
            _require_text(getattr(self, name), name)
        if self.status != "observed":
            raise EvidenceError("world result is not an observation")
        if not self.observed_facts or any(not fact.strip() for fact in self.observed_facts):
            raise EvidenceError("observation requires at least one concrete fact")
        _require_sha256(self.artifact_digest, "artifact_digest")
        if self.evidence_authority != "local_fixture" or self.external_world_contact:
            raise EvidenceError("MVP evidence authority is local_fixture only")
        if self.observation_id != canonical_digest(self.identity_payload()):
            raise EvidenceError("observation id does not bind the observed facts")
    def identity_payload(self) -> dict[str, object]:
        return {
            "proposal_id": self.proposal_id,
            "operation_hash": self.operation_hash,
            "status": self.status,
            "observed_by": self.observed_by,
            "observed_facts": list(self.observed_facts),
            "artifact_locator": self.artifact_locator,
            "artifact_digest": self.artifact_digest,
            "evidence_authority": self.evidence_authority,
            "external_world_contact": self.external_world_contact,
        }
    def to_dict(self) -> dict[str, object]:
        return {"observation_id": self.observation_id, **self.identity_payload()}
def _validate_world_observation(
    proposal: AgentProposal,
    observation: WorldObservation,
) -> None:
    observation.require_valid()
    if observation.proposal_id != proposal.proposal_id:
        raise EvidenceError("observation belongs to a different proposal")
    if observation.operation_hash != proposal.action.operation_hash:
        raise EvidenceError("observation does not bind the executed operation")
@runtime_checkable
class WorldPort(Protocol):
    def execute(
        self,
        deliberation: Deliberation,
        proposal: AgentProposal,
        grant: AuthorityGrant,
    ) -> WorldObservation: ...
@dataclass(frozen=True, slots=True)
class CycleReceipt:
    receipt_id: str
    seal: str
    status: str
    cycle_id: str
    session_id: str
    intent_id: str
    input_hash: str
    prior_receipt_id: str
    prior_observation_id: str
    revision_reason: str
    selected_proposal_id: str
    selected_agent_id: str
    grant_id: str
    operation_hash: str
    effect_key: str
    observation: WorldObservation
    def __post_init__(self) -> None:
        self.require_valid()
    def identity_payload(self) -> dict[str, object]:
        return {
            "status": self.status,
            "cycle_id": self.cycle_id,
            "session_id": self.session_id,
            "intent_id": self.intent_id,
            "input_hash": self.input_hash,
            "prior_receipt_id": self.prior_receipt_id,
            "prior_observation_id": self.prior_observation_id,
            "revision_reason": self.revision_reason,
            "selected_proposal_id": self.selected_proposal_id,
            "selected_agent_id": self.selected_agent_id,
            "grant_id": self.grant_id,
            "operation_hash": self.operation_hash,
            "effect_key": self.effect_key,
            "observation": self.observation.to_dict(),
        }
    def require_valid(self) -> None:
        self.observation.require_valid()
        if self.status != "completed":
            raise EvidenceError("cycle receipt is not completed")
        for name in (
            "receipt_id", "cycle_id", "session_id",
            "intent_id", "selected_agent_id", "effect_key",
        ):
            _require_text(getattr(self, name), name)
        for name in ("seal", "input_hash", "selected_proposal_id", "grant_id", "operation_hash"):
            _require_sha256(getattr(self, name), name)
        causal_fields = self.prior_receipt_id, self.prior_observation_id, self.revision_reason
        if any(causal_fields) and not all(causal_fields):
            raise CausalityError("receipt has an incomplete prior-cause binding")
        if self.prior_observation_id:
            _require_sha256(self.prior_observation_id, "prior_observation_id")
        if self.seal != canonical_digest(self.identity_payload()):
            raise EvidenceError("cycle receipt seal does not bind its body")
        if self.receipt_id != f"shakti_cycle_{_digest_prefix(self.seal, 24)}":
            raise EvidenceError("cycle receipt id does not bind its seal")
        if self.selected_proposal_id != self.observation.proposal_id:
            raise EvidenceError("receipt proposal does not match its observation")
        if self.operation_hash != self.observation.operation_hash:
            raise EvidenceError("receipt operation does not match its observation")
        if self.effect_key != f"shakti_effect:{_digest_prefix(self.selected_proposal_id, 24)}":
            raise EvidenceError("receipt effect key does not bind its proposal")
    @classmethod
    def seal_completed(
        cls,
        deliberation: Deliberation,
        proposal: AgentProposal,
        grant: AuthorityGrant,
        observation: WorldObservation,
        effect_key: str,
    ) -> CycleReceipt:
        validate_authority_grant(deliberation, proposal, grant)
        _validate_world_observation(proposal, observation)
        context = deliberation.context
        body = {
            "status": "completed",
            "cycle_id": context.cycle_id,
            "session_id": context.session_id,
            "intent_id": context.intent.intent_id,
            "input_hash": context.input_hash,
            "prior_receipt_id": context.prior_receipt_id,
            "prior_observation_id": context.prior_observation_id,
            "revision_reason": context.revision_reason,
            "selected_proposal_id": proposal.proposal_id,
            "selected_agent_id": proposal.agent_id,
            "grant_id": grant.grant_id,
            "operation_hash": proposal.action.operation_hash,
            "effect_key": effect_key,
            "observation": observation.to_dict(),
        }
        seal = canonical_digest(body)
        return cls(
            receipt_id=f"shakti_cycle_{_digest_prefix(seal, 24)}",
            seal=seal,
            **{**body, "observation": observation},
        )
    def to_dict(self) -> dict[str, object]:
        return {"schema": "shakti_system_run.mvp.v1", "receipt_id": self.receipt_id,
                "seal": self.seal, **self.identity_payload()}
class LocalArtifactWorld:
    def __init__(self, root: Path, *, observed_by: str = "local-fixture-observer") -> None:
        self.root = Path(root)
        self.observed_by = observed_by
        self.execution_count = self.verification_count = 0
        self._pending_receipts: dict[str, CycleReceipt] = {}
        self._completed_receipts: dict[str, CycleReceipt] = {}
    def execute(
        self,
        deliberation: Deliberation,
        proposal: AgentProposal,
        grant: AuthorityGrant,
    ) -> WorldObservation:
        validate_authority_grant(deliberation, proposal, grant)
        action = proposal.action
        if action.effect_kind != "write_local_artifact" or not action.declared_reversible:
            raise AuthorityError("local fixture rejected the effect kind")
        data = action.content.encode("utf-8")
        artifact = write_immutable_beneath(self.root, action.relative_path, data)
        observed = read_regular_nofollow(artifact, field="local fixture artifact")
        if observed != data:
            raise EvidenceError("artifact bytes differ from the granted action")
        digest = "sha256:" + hashlib.sha256(observed).hexdigest()
        facts = (
            "artifact_is_regular_file",
            f"artifact_byte_count={len(observed)}",
            f"artifact_digest={digest}",
        )
        body = {
            "proposal_id": proposal.proposal_id,
            "operation_hash": action.operation_hash,
            "status": "observed",
            "observed_by": self.observed_by,
            "observed_facts": list(facts),
            "artifact_locator": action.relative_path,
            "artifact_digest": digest,
            "evidence_authority": "local_fixture",
            "external_world_contact": False,
        }
        self.execution_count += 1
        observation = WorldObservation(
            observation_id=canonical_digest(body),
            **{**body, "observed_facts": facts},
        )
        effect_key = f"shakti_effect:{_digest_prefix(proposal.proposal_id, 24)}"
        self._pending_receipts[observation.observation_id] = CycleReceipt.seal_completed(
            deliberation, proposal, grant, observation, effect_key
        )
        return observation
    def _mark_completed(self, receipt: CycleReceipt) -> None:
        if self._pending_receipts.get(receipt.observation.observation_id) != receipt:
            raise EvidenceError("receipt was not pending for this local execution")
        self._completed_receipts[receipt.observation.observation_id] = receipt
    def verify_receipt(self, receipt: CycleReceipt) -> None:
        receipt.require_valid()
        observation = receipt.observation
        if self._completed_receipts.get(observation.observation_id) != receipt:
            raise EvidenceError("receipt was not issued by this authorized local execution")
        artifact = scoped_regular_file(
            self.root,
            observation.artifact_locator,
            field="observed artifact",
            error_type=EvidenceError,
        )
        observed = read_regular_nofollow(
            artifact,
            field="observed artifact",
            error_type=EvidenceError,
        )
        digest = "sha256:" + hashlib.sha256(observed).hexdigest()
        expected_facts = (
            "artifact_is_regular_file",
            f"artifact_byte_count={len(observed)}",
            f"artifact_digest={digest}",
        )
        if digest != observation.artifact_digest:
            raise EvidenceError("verified artifact digest differs from the observation")
        if observation.observed_facts != expected_facts:
            raise EvidenceError("verified artifact facts differ from the observation")
        self.verification_count += 1
