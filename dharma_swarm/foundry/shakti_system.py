from __future__ import annotations
from dataclasses import dataclass
from typing import Protocol, Sequence, runtime_checkable
from dharma_swarm.foundry.evaluator import canonical_digest
from dharma_swarm.foundry.shakti_local_world import (
    ActionSpec as ActionSpec,
    AgentProposal as AgentProposal,
    AuthorityError as AuthorityError,
    AuthorityGrant as AuthorityGrant,
    CausalityError as CausalityError,
    CycleReceipt as CycleReceipt,
    Deliberation as Deliberation,
    DuplicateEffect as DuplicateEffect,
    EvidenceError as EvidenceError,
    LocalArtifactWorld,
    ShaktiSystemError as ShaktiSystemError,
    SystemStopped as SystemStopped,
    WorldObservation as WorldObservation,
    WorldPort as WorldPort,
    _digest_prefix,
    _require_sha256,
    _require_text,
    _validate_world_observation,
    expected_approval as expected_approval,
    validate_authority_grant as validate_authority_grant,
)
@dataclass(frozen=True, slots=True)
class IntentContract:
    intent_id: str
    owner_id: str
    purpose: str
    visible_success: str
    human_blank: str
    allowed_effect_kind: str = "write_local_artifact"
    prohibited_effects: tuple[str, ...] = (
        "external_contact",
        "payment",
        "publication",
        "deployment",
        "destructive_write",
    )
    def __post_init__(self) -> None:
        for name in (
            "intent_id",
            "owner_id",
            "purpose",
            "visible_success",
            "human_blank",
            "allowed_effect_kind",
        ):
            _require_text(getattr(self, name), name)
        if len(self.prohibited_effects) != len(set(self.prohibited_effects)):
            raise ValueError("prohibited effects must be unique")
        for effect in self.prohibited_effects:
            _require_text(effect, "prohibited effect")
        if self.allowed_effect_kind in self.prohibited_effects:
            raise AuthorityError("the allowed effect is also explicitly prohibited")
    def to_dict(self) -> dict[str, object]:
        return {
            "intent_id": self.intent_id,
            "owner_id": self.owner_id,
            "purpose": self.purpose,
            "visible_success": self.visible_success,
            "human_blank": self.human_blank,
            "allowed_effect_kind": self.allowed_effect_kind,
            "prohibited_effects": list(self.prohibited_effects),
        }
@dataclass(frozen=True, slots=True)
class PolicyState:
    revision: int = 0
    agent_weights: tuple[tuple[str, int], ...] = ()
    causal_receipt_id: str = ""
    causal_observation_id: str = ""
    causal_artifact_digest: str = ""
    interpretation: str = ""
    def __post_init__(self) -> None:
        self.require_valid()
    def require_valid(self) -> None:
        if type(self.revision) is not int:
            raise ValueError("policy revision must be an exact integer")
        if self.revision < 0:
            raise ValueError("policy revision cannot be negative")
        names = [name for name, _ in self.agent_weights]
        if len(names) != len(set(names)) or any(not name for name in names):
            raise ValueError("agent weights require unique non-empty agent ids")
        if any(type(weight) is not int for _, weight in self.agent_weights):
            raise ValueError("agent weights must be integers")
        causal_fields = (
            self.causal_receipt_id,
            self.causal_observation_id,
            self.causal_artifact_digest,
            self.interpretation.strip(),
        )
        if not self.revision and any(causal_fields):
            raise ValueError("initial policy cannot claim prior causal evidence")
        if self.revision and not all(causal_fields):
            raise ValueError("revised policy requires causal evidence and interpretation")
        if self.revision:
            _require_sha256(self.causal_observation_id, "causal_observation_id")
            _require_sha256(self.causal_artifact_digest, "causal_artifact_digest")
    def weight_for(self, agent_id: str) -> int:
        return dict(self.agent_weights).get(agent_id, 0)
    def to_dict(self) -> dict[str, object]:
        return {
            "revision": self.revision,
            "agent_weights": [list(item) for item in self.agent_weights],
            "causal_receipt_id": self.causal_receipt_id,
            "causal_observation_id": self.causal_observation_id,
            "causal_artifact_digest": self.causal_artifact_digest,
            "interpretation": self.interpretation,
        }
@dataclass(frozen=True, slots=True)
class CycleContext:
    cycle_id: str
    session_id: str
    intent: IntentContract
    policy: PolicyState
    prior_receipt_id: str = ""
    prior_observation_id: str = ""
    revision_reason: str = ""
    prior_run_id: str = ""
    prior_receipt: CycleReceipt | None = None
    policy_delta: PolicyDelta | None = None
    policy_ratification: PolicyRatification | None = None
    def __post_init__(self) -> None:
        self.require_valid()
    def require_valid(self) -> None:
        _require_text(self.cycle_id, "cycle_id")
        _require_text(self.session_id, "session_id")
        self.policy.require_valid()
        causal_fields = (
            self.prior_receipt_id,
            self.prior_observation_id,
            self.revision_reason,
            self.prior_run_id,
        )
        if not self.policy.revision and any(causal_fields):
            raise CausalityError("initial cycle cannot claim a prior causal transition")
        if any(causal_fields) and not all(causal_fields):
            raise CausalityError("later cycle requires receipt, observation, and reason")
        if self.policy.revision and not all(causal_fields):
            raise CausalityError("revised cycle requires a complete prior cause")
        if self.policy.revision and self.policy.revision != 1:
            raise CausalityError("two-cycle MVP requires revised policy revision 1")
        claim_bundle = self.prior_receipt, self.policy_delta, self.policy_ratification
        if not self.policy.revision and any(item is not None for item in claim_bundle):
            raise CausalityError("initial cycle cannot carry a promotion claim bundle")
        if self.policy.revision and not all(item is not None for item in claim_bundle):
            raise CausalityError("revised cycle requires a complete promotion claim bundle")
        if self.policy.revision:
            receipt, delta, ratification = claim_bundle
            if not isinstance(receipt, CycleReceipt) or not isinstance(delta, PolicyDelta):
                raise CausalityError("revised cycle claim bundle has invalid evidence types")
            if not isinstance(ratification, PolicyRatification):
                raise CausalityError("revised cycle claim bundle has invalid authority type")
            receipt.require_valid()
            if (
                receipt.session_id != self.session_id
                or receipt.intent_id != self.intent.intent_id
                or receipt.receipt_id != self.prior_receipt_id
                or receipt.observation.observation_id != self.prior_observation_id
            ):
                raise CausalityError("prior receipt does not bind the revised cycle")
            delta.require_valid("policy delta id does not bind the revised cycle")
            ratification.require_valid()
            if (
                delta.prior_revision != self.policy.revision - 1
                or delta.based_on_receipt_id != receipt.receipt_id
                or delta.based_on_observation_id != receipt.observation.observation_id
                or delta.based_on_artifact_digest != receipt.observation.artifact_digest
                or delta.proposed_weights != self.policy.agent_weights
                or delta.interpretation != self.revision_reason
            ):
                raise CausalityError("policy delta does not bind the revised cycle")
            if (
                ratification.delta_id != delta.delta_id
                or ratification.actor_id != self.intent.owner_id
                or ratification.approved is not True
                or ratification.typed_confirmation != expected_ratification(delta.delta_id)
                or not ratification.reason.strip()
            ):
                raise CausalityError("policy ratification does not bind the revised cycle")
            if (
                self.policy.causal_receipt_id != self.prior_receipt_id
                or self.policy.causal_observation_id != self.prior_observation_id
                or self.policy.causal_artifact_digest != delta.based_on_artifact_digest
                or self.policy.interpretation != self.revision_reason
            ):
                raise CausalityError("cycle context does not match ratified policy cause")
    def to_dict(self) -> dict[str, object]:
        return {
            "cycle_id": self.cycle_id,
            "session_id": self.session_id,
            "intent": self.intent.to_dict(),
            "policy": self.policy.to_dict(),
            "prior_receipt_id": self.prior_receipt_id,
            "prior_observation_id": self.prior_observation_id,
            "revision_reason": self.revision_reason,
            "prior_run_id": self.prior_run_id,
            "prior_receipt": self.prior_receipt.to_dict() if self.prior_receipt else None,
            "policy_delta": self.policy_delta.to_dict() if self.policy_delta else None,
            "policy_ratification": (
                self.policy_ratification.to_dict() if self.policy_ratification else None
            ),
        }
    @property
    def input_hash(self) -> str:
        return canonical_digest(self.to_dict())
    def require_claim_bundle(self, verifier: object) -> None:
        if self.policy.revision:
            assert self.prior_receipt is not None
            _verify_local_receipt(self.prior_receipt, verifier)
@runtime_checkable
class CouncilAgent(Protocol):
    agent_id: str
    def propose(self, context: CycleContext) -> AgentProposal: ...
def _verify_local_receipt(receipt: CycleReceipt, verifier: object) -> None:
    if type(verifier) is not LocalArtifactWorld:
        raise EvidenceError("evidence verifier must be the concrete local world adapter")
    verifier.verify_receipt(receipt)
def _mark_local_receipt_completed(world: object, receipt: CycleReceipt) -> None:
    if type(world) is LocalArtifactWorld:
        world._mark_completed(receipt)
@runtime_checkable
class EffectFence(Protocol):
    def begin(self, effect_key: str, operation_hash: str) -> bool: ...
    def complete(self, receipt: CycleReceipt) -> None: ...
    def is_committed(self, receipt: CycleReceipt) -> bool: ...
    def fail(self, effect_key: str, operation_hash: str, reason: str) -> None: ...
@dataclass(slots=True)
class SystemControl:
    stopped: bool = False
    reason: str = ""
    def stop(self, reason: str) -> None:
        _require_text(reason, "stop reason")
        self.stopped = True
        self.reason = reason
    def require_running(self) -> None:
        if self.stopped:
            raise SystemStopped(self.reason or "system stopped")
class ShaktiSystem:
    def __init__(
        self,
        agents: Sequence[CouncilAgent],
        world: WorldPort,
        fence: EffectFence,
        *,
        control: SystemControl | None = None,
    ) -> None:
        if len(agents) < 2:
            raise ValueError("MVP council requires at least two agents")
        agent_ids = [agent.agent_id for agent in agents]
        if len(agent_ids) != len(set(agent_ids)):
            raise ValueError("council agent ids must be unique")
        self._agents = tuple(agents)
        self._world = world
        self._fence = fence
        self.control = control or SystemControl()
    def deliberate(self, context: CycleContext) -> Deliberation:
        self.control.require_running()
        context.require_valid()
        context.require_claim_bundle(self._world)
        proposals = tuple(agent.propose(context) for agent in self._agents)
        for agent, proposal in zip(self._agents, proposals, strict=True):
            if proposal.agent_id != agent.agent_id:
                raise CausalityError("agent returned a proposal under another identity")
            if proposal.context_hash != context.input_hash:
                raise CausalityError("proposal does not bind this cycle input")
            if proposal.based_on_observation_id != context.prior_observation_id:
                raise CausalityError("proposal omits or changes the prior observation")
            if proposal.action.effect_kind != context.intent.allowed_effect_kind:
                raise AuthorityError("proposal effect is outside the intent contract")
            if proposal.proposal_id != canonical_digest(proposal.identity_payload()):
                raise CausalityError("proposal identity changed after creation")
        if len({proposal.proposal_id for proposal in proposals}) != len(proposals):
            raise CausalityError("council returned duplicate proposal identities")
        ordered = tuple(
            sorted(
                proposals,
                key=lambda proposal: (
                    -context.policy.weight_for(proposal.agent_id),
                    proposal.agent_id,
                    proposal.proposal_id,
                ),
            )
        )
        return Deliberation.create(
            context=context,
            proposals=ordered,
            recommended_proposal_id=ordered[0].proposal_id,
        )
    def run_cycle(
        self,
        deliberation: Deliberation,
        grant: AuthorityGrant,
    ) -> CycleReceipt:
        self.control.require_running()
        deliberation.require_valid()
        deliberation.context.require_valid()
        deliberation.context.require_claim_bundle(self._world)
        proposal = deliberation.proposal(grant.proposal_id)
        validate_authority_grant(deliberation, proposal, grant)
        effect_key = f"shakti_effect:{_digest_prefix(proposal.proposal_id, 24)}"
        operation_hash = proposal.action.operation_hash
        if not self._fence.begin(effect_key, operation_hash):
            raise DuplicateEffect(f"effect already consumed: {effect_key}")
        try:
            observation = self._world.execute(deliberation, proposal, grant)
            _validate_world_observation(proposal, observation)
            receipt = CycleReceipt.seal_completed(
                deliberation, proposal, grant, observation, effect_key
            )
            self._fence.complete(receipt)
            if not self._fence.is_committed(receipt):
                raise EvidenceError("effect fence did not commit a terminal cycle marker")
            _mark_local_receipt_completed(self._world, receipt)
            return receipt
        except Exception as exc:
            self._fence.fail(effect_key, operation_hash, str(exc))
            raise
    def stop(self, reason: str) -> None:
        self.control.stop(reason)
def expected_ratification(delta_id: str) -> str:
    return f"ratify {_digest_prefix(delta_id)}"
@dataclass(frozen=True, slots=True)
class PolicyDelta:
    delta_id: str
    prior_revision: int
    proposed_weights: tuple[tuple[str, int], ...]
    based_on_receipt_id: str
    based_on_observation_id: str
    based_on_artifact_digest: str
    interpretation: str
    def __post_init__(self) -> None:
        self.require_valid("policy delta id does not bind the proposed policy")
    def require_valid(self, identity_error: str) -> None:
        if type(self.prior_revision) is not int:
            raise ValueError("policy delta prior revision must be an exact integer")
        _require_sha256(self.based_on_observation_id, "based_on_observation_id")
        _require_sha256(self.based_on_artifact_digest, "based_on_artifact_digest")
        if self.delta_id != canonical_digest(self.identity_payload()):
            raise CausalityError(identity_error)
    @classmethod
    def create(
        cls,
        policy: PolicyState,
        receipt: CycleReceipt,
        *,
        verifier: object,
        proposed_weights: dict[str, int],
        interpretation: str,
    ) -> PolicyDelta:
        _require_text(interpretation, "interpretation")
        _verify_local_receipt(receipt, verifier)
        weights = tuple(sorted(proposed_weights.items()))
        body = {
            "prior_revision": policy.revision,
            "proposed_weights": [list(item) for item in weights],
            "based_on_receipt_id": receipt.receipt_id,
            "based_on_observation_id": receipt.observation.observation_id,
            "based_on_artifact_digest": receipt.observation.artifact_digest,
            "interpretation": interpretation,
        }
        return cls(
            delta_id=canonical_digest(body),
            prior_revision=policy.revision,
            proposed_weights=weights,
            based_on_receipt_id=receipt.receipt_id,
            based_on_observation_id=receipt.observation.observation_id,
            based_on_artifact_digest=receipt.observation.artifact_digest,
            interpretation=interpretation,
        )
    def identity_payload(self) -> dict[str, object]:
        return {
            "prior_revision": self.prior_revision,
            "proposed_weights": [list(item) for item in self.proposed_weights],
            "based_on_receipt_id": self.based_on_receipt_id,
            "based_on_observation_id": self.based_on_observation_id,
            "based_on_artifact_digest": self.based_on_artifact_digest,
            "interpretation": self.interpretation,
        }
    def to_dict(self) -> dict[str, object]:
        return {"delta_id": self.delta_id, **self.identity_payload()}
@dataclass(frozen=True, slots=True)
class PolicyRatification:
    ratification_id: str
    delta_id: str
    actor_id: str
    approved: bool
    typed_confirmation: str
    reason: str
    def __post_init__(self) -> None:
        self.require_valid()
    def require_valid(self) -> None:
        if type(self.approved) is not bool:
            raise ValueError("approved must be a boolean")
        if self.ratification_id != canonical_digest(self.identity_payload()):
            raise AuthorityError("ratification id does not bind the decision")
    @classmethod
    def approve(
        cls,
        delta: PolicyDelta,
        *,
        actor_id: str,
        typed_confirmation: str,
        reason: str,
    ) -> PolicyRatification:
        body = {
            "delta_id": delta.delta_id,
            "actor_id": actor_id,
            "approved": True,
            "typed_confirmation": typed_confirmation,
            "reason": reason,
        }
        return cls(ratification_id=canonical_digest(body), **body)
    def identity_payload(self) -> dict[str, object]:
        return {
            "delta_id": self.delta_id,
            "actor_id": self.actor_id,
            "approved": self.approved,
            "typed_confirmation": self.typed_confirmation,
            "reason": self.reason,
        }
    def to_dict(self) -> dict[str, object]:
        return {"ratification_id": self.ratification_id, **self.identity_payload()}
def next_cycle_context(
    previous: CycleContext,
    receipt: CycleReceipt,
    delta: PolicyDelta,
    ratification: PolicyRatification,
    *,
    verifier: object,
    prior_run_id: str,
    cycle_id: str,
) -> CycleContext:
    previous.require_valid()
    _verify_local_receipt(receipt, verifier)
    if (
        receipt.cycle_id != previous.cycle_id
        or receipt.session_id != previous.session_id
        or receipt.intent_id != previous.intent.intent_id
        or receipt.input_hash != previous.input_hash
        or receipt.prior_receipt_id != previous.prior_receipt_id
        or receipt.prior_observation_id != previous.prior_observation_id
        or receipt.revision_reason != previous.revision_reason
    ):
        raise CausalityError("receipt does not close the previous cycle")
    if (
        delta.based_on_receipt_id != receipt.receipt_id
        or delta.based_on_observation_id != receipt.observation.observation_id
        or delta.based_on_artifact_digest != receipt.observation.artifact_digest
    ):
        raise CausalityError("policy delta does not cite the re-read world observation")
    if delta.prior_revision != previous.policy.revision:
        raise CausalityError("policy delta was computed from another revision")
    delta.require_valid("policy delta identity changed after creation")
    ratification.require_valid()
    if ratification.approved is not True:
        raise AuthorityError("policy delta was not ratified")
    if ratification.delta_id != delta.delta_id or ratification.actor_id != previous.intent.owner_id:
        raise AuthorityError("ratification actor or delta does not match")
    if ratification.typed_confirmation != expected_ratification(delta.delta_id):
        raise AuthorityError("ratification does not contain the exact delta confirmation")
    if not ratification.reason.strip():
        raise AuthorityError("ratification requires a human reason")
    policy = PolicyState(
        revision=previous.policy.revision + 1,
        agent_weights=delta.proposed_weights,
        causal_receipt_id=delta.based_on_receipt_id,
        causal_observation_id=delta.based_on_observation_id,
        causal_artifact_digest=delta.based_on_artifact_digest,
        interpretation=delta.interpretation,
    )
    if policy.revision != previous.policy.revision + 1:
        raise CausalityError("next policy must advance exactly one ratified revision")
    return CycleContext(
        cycle_id=cycle_id,
        session_id=previous.session_id,
        intent=previous.intent,
        policy=policy,
        prior_receipt_id=receipt.receipt_id,
        prior_observation_id=receipt.observation.observation_id,
        revision_reason=policy.interpretation,
        prior_run_id=prior_run_id,
        prior_receipt=receipt,
        policy_delta=delta,
        policy_ratification=ratification,
    )
