from __future__ import annotations

import asyncio
import importlib
from dataclasses import replace
from pathlib import Path

import pytest

from dharma_swarm.foundry.evaluator import canonical_digest
from dharma_swarm.foundry.patches import PatchReplayError
from dharma_swarm.foundry.shakti_local_world import LocalArtifactWorld
from dharma_swarm.foundry.shakti_system import (
    ActionSpec,
    AgentProposal,
    AuthorityError,
    AuthorityGrant,
    CausalityError,
    CycleContext,
    CycleReceipt,
    Deliberation,
    DuplicateEffect,
    EvidenceError,
    IntentContract,
    PolicyDelta,
    PolicyRatification,
    PolicyState,
    ShaktiSystem,
    SystemStopped,
    expected_approval,
    expected_ratification,
    next_cycle_context,
)
from dharma_swarm.runtime_state import RuntimeStateStore
from scripts.foundry.run_shakti_system_mvp import (
    ReferenceAgent,
    RuntimeEffectFence,
    _identity_for_cycle,
    run_demo,
)


class CountingFence:
    def __init__(self, *, admit: bool = True) -> None:
        self.admit = admit
        self.begins: list[tuple[str, str]] = []
        self.completed: list[CycleReceipt] = []
        self.failures: list[tuple[str, str, str]] = []

    def begin(self, effect_key: str, operation_hash: str) -> bool:
        self.begins.append((effect_key, operation_hash))
        return self.admit

    def complete(self, receipt: CycleReceipt) -> None:
        self.completed.append(receipt)

    def fail(self, effect_key: str, operation_hash: str, reason: str) -> None:
        self.failures.append((effect_key, operation_hash, reason))

    def is_committed(self, receipt: CycleReceipt) -> bool:
        return receipt in self.completed


class NoopFence(CountingFence):
    def is_committed(self, receipt: CycleReceipt) -> bool:
        return False



class ExplodingWorld:
    def __init__(self) -> None:
        self.execution_count = 0

    def execute(self, deliberation, proposal: AgentProposal, grant):
        self.execution_count += 1
        raise EvidenceError("no observed consequence")


def _intent() -> IntentContract:
    return IntentContract(
        intent_id="intent-test",
        owner_id="human-owner",
        purpose="Produce one inspectable local consequence",
        visible_success="a re-read artifact changes the next cycle",
        human_blank="Which proposal should act, and why?",
    )


def _context(*, session_id: str = "session-test") -> CycleContext:
    return CycleContext(
        cycle_id="cycle-1",
        session_id=session_id,
        intent=_intent(),
        policy=PolicyState(agent_weights=(("builder", 1), ("witness", 0))),
    )


def _agents() -> tuple[ReferenceAgent, ReferenceAgent]:
    return ReferenceAgent("builder"), ReferenceAgent("witness")


def _deliberation(tmp_path: Path, fence: CountingFence | None = None):
    world = LocalArtifactWorld(tmp_path)
    system = ShaktiSystem(_agents(), world, fence or CountingFence())
    deliberation = system.deliberate(_context())
    proposal = deliberation.proposal(deliberation.recommended_proposal_id)
    return system, world, deliberation, proposal


def _grant(deliberation, proposal, *, confirmation: str | None = None, actor=None):
    return AuthorityGrant.approve(
        deliberation,
        proposal.proposal_id,
        actor_id=actor or deliberation.context.intent.owner_id,
        typed_confirmation=confirmation or expected_approval(proposal),
        reason="This is the bounded next move I choose.",
    )


def _promotion_inputs(tmp_path: Path):
    system, world, deliberation, proposal = _deliberation(tmp_path)
    receipt = system.run_cycle(deliberation, _grant(deliberation, proposal))
    delta = PolicyDelta.create(
        deliberation.context.policy,
        receipt,
        verifier=world,
        proposed_weights={"builder": 1, "witness": 2},
        interpretation="The bounded observation changes the next cycle.",
    )
    ratification = PolicyRatification.approve(
        delta,
        actor_id=deliberation.context.intent.owner_id,
        typed_confirmation=expected_ratification(delta.delta_id),
        reason="I accept this bounded interpretation.",
    )
    return system, world, deliberation, receipt, delta, ratification


def test_rejects_ungranted_action_without_calling_world(tmp_path: Path) -> None:
    fence = CountingFence()
    system, world, deliberation, proposal = _deliberation(tmp_path, fence)
    bad_grant = _grant(deliberation, proposal, confirmation="approve something-else")

    with pytest.raises(AuthorityError, match="exact proposal confirmation"):
        system.run_cycle(deliberation, bad_grant)

    assert world.execution_count == 0
    assert fence.begins == []
    assert fence.completed == []


def test_rejects_grant_from_non_owner(tmp_path: Path) -> None:
    system, world, deliberation, proposal = _deliberation(tmp_path)

    with pytest.raises(AuthorityError, match="actor or intent"):
        system.run_cycle(
            deliberation,
            _grant(deliberation, proposal, actor="agent-self-approval"),
        )

    assert world.execution_count == 0


def test_rejects_truthy_non_boolean_grant_after_rehash(tmp_path: Path) -> None:
    system, world, deliberation, proposal = _deliberation(tmp_path)
    grant = _grant(deliberation, proposal)
    object.__setattr__(grant, "approved", 1)
    object.__setattr__(grant, "grant_id", canonical_digest(grant.identity_payload()))

    with pytest.raises(AuthorityError, match="not approved"):
        system.run_cycle(deliberation, grant)

    assert world.execution_count == 0


@pytest.mark.parametrize("revision", [True, 1.0])
def test_policy_revision_requires_exact_integer(revision) -> None:
    with pytest.raises(ValueError, match="exact integer"):
        PolicyState(revision=revision)


@pytest.mark.parametrize("prior_revision", [False, 0.0])
def test_policy_delta_prior_revision_requires_exact_integer(prior_revision) -> None:
    body = {
        "prior_revision": prior_revision,
        "proposed_weights": [["builder", 1]],
        "based_on_receipt_id": "receipt",
        "based_on_observation_id": "sha256:" + "1" * 64,
        "based_on_artifact_digest": "sha256:" + "2" * 64,
        "interpretation": "Bounded.",
    }
    with pytest.raises(ValueError, match="prior revision must be an exact integer"):
        PolicyDelta(
            delta_id=canonical_digest(body),
            prior_revision=prior_revision,
            proposed_weights=(("builder", 1),),
            based_on_receipt_id="receipt",
            based_on_observation_id="sha256:" + "1" * 64,
            based_on_artifact_digest="sha256:" + "2" * 64,
            interpretation="Bounded.",
        )


def test_duplicate_fence_blocks_before_world_effect(tmp_path: Path) -> None:
    fence = CountingFence(admit=False)
    system, world, deliberation, proposal = _deliberation(tmp_path, fence)

    with pytest.raises(DuplicateEffect):
        system.run_cycle(deliberation, _grant(deliberation, proposal))

    assert world.execution_count == 0
    assert len(fence.begins) == 1


def test_content_addressed_types_reject_post_id_tampering(tmp_path: Path) -> None:
    system, _, deliberation, proposal = _deliberation(tmp_path)

    with pytest.raises(CausalityError, match="proposal id does not bind"):
        replace(proposal, title="same id, different action context")

    receipt = system.run_cycle(deliberation, _grant(deliberation, proposal))
    with pytest.raises(EvidenceError, match="observation id does not bind"):
        replace(
            receipt.observation,
            observed_facts=("artifact_is_regular_file", "forged_fact=true"),
        )
    with pytest.raises(EvidenceError, match="exact lowercase SHA-256"):
        replace(receipt.observation, artifact_digest="sha256:x")
    with pytest.raises(EvidenceError, match="seal does not bind"):
        replace(receipt, seal="sha256:" + "0" * 64)


def test_content_addressed_envelope_shape_is_stable() -> None:
    intent = IntentContract("i", "owner", "purpose", "success", "question")
    context = CycleContext("c", "s", intent, PolicyState())
    proposal = AgentProposal.create(
        agent_id="a",
        context=context,
        title="t",
        rationale="r",
        human_question="q",
        predicted_signal="p",
        action=ActionSpec("write_local_artifact", "x/y", "body"),
    )
    deliberation = Deliberation.create(
        context=context,
        proposals=(proposal,),
        recommended_proposal_id=proposal.proposal_id,
    )
    grant = AuthorityGrant.approve(
        deliberation,
        proposal.proposal_id,
        actor_id="owner",
        typed_confirmation=expected_approval(proposal),
        reason="r",
    )

    assert context.input_hash == (
        "sha256:f19f203047b85138a3ef35a7ced7e194defeeab0c5207bd1713bc2d328029c89"
    )
    assert proposal.proposal_id == (
        "sha256:f25e16baf1bd0c1250ecaab0e7699bcfb8852584c1f3fc0aea72f3f9182a32a2"
    )
    assert deliberation.deliberation_id == (
        "sha256:dadeea84297af045284029e9100b59f0edf646627225d0338ea9e0828a51f51e"
    )
    assert grant.grant_id == (
        "sha256:44a3c7445edb3a15c249b6bff803bb25a6794307c82492e904d7c9e023bf5afd"
    )


def test_core_exports_no_transferable_evidence_mint() -> None:
    core = importlib.import_module("dharma_swarm.foundry.shakti_system")
    local_world = importlib.import_module("dharma_swarm.foundry.shakti_local_world")

    for module in (core, local_world):
        for name in (
            "VerifiedCycleEvidence",
            "_LOCAL_EVIDENCE_CAPABILITY",
            "_from_local_verification",
        ):
            assert not hasattr(module, name)
            with pytest.raises(ImportError):
                exec(f"from {module.__name__} import {name}", {})


def test_deliberation_rejects_context_substitution_before_effect(tmp_path: Path) -> None:
    system, world, deliberation, proposal = _deliberation(tmp_path)
    grant = _grant(deliberation, proposal)
    object.__setattr__(deliberation, "context", _context(session_id="substituted"))

    with pytest.raises(CausalityError, match="deliberation id does not bind"):
        system.run_cycle(deliberation, grant)

    assert world.execution_count == 0


def test_manually_forged_cross_context_deliberation_is_rejected(tmp_path: Path) -> None:
    system, world, deliberation, _ = _deliberation(tmp_path)
    foreign_context = _context(session_id="foreign-session")

    with pytest.raises(CausalityError, match="proposal does not bind"):
        forged = Deliberation.create(
            context=foreign_context,
            proposals=deliberation.proposals,
            recommended_proposal_id=deliberation.recommended_proposal_id,
        )
        system.run_cycle(
            forged,
            _grant(forged, forged.proposal(forged.recommended_proposal_id)),
        )

    assert world.execution_count == 0


def test_initial_context_cannot_claim_nonexistent_prior_evidence() -> None:
    with pytest.raises(ValueError, match="initial policy cannot claim"):
        PolicyState(
            revision=0,
            causal_receipt_id="invented-receipt",
            causal_observation_id="sha256:" + "1" * 64,
            causal_artifact_digest="sha256:" + "2" * 64,
            interpretation="invented cause",
        )

    with pytest.raises(CausalityError, match="initial cycle cannot claim"):
        CycleContext(
            cycle_id="cycle-forged",
            session_id="session-forged",
            intent=_intent(),
            policy=PolicyState(),
            prior_receipt_id="invented-receipt",
            prior_observation_id="sha256:" + "1" * 64,
            revision_reason="invented cause",
        )


def test_receipt_sealing_rejects_self_consistent_attacker_grant(tmp_path: Path) -> None:
    _, world, deliberation, proposal = _deliberation(tmp_path)
    valid_grant = _grant(deliberation, proposal)
    observation = world.execute(
        deliberation,
        proposal,
        valid_grant,
    )
    attacker_grant = AuthorityGrant.approve(
        deliberation,
        proposal.proposal_id,
        actor_id="agent-self-approval",
        typed_confirmation=expected_approval(proposal),
        reason="A content-addressed lie is still not human authority.",
    )
    effect_key = f"shakti_effect:{proposal.proposal_id.removeprefix('sha256:')[:24]}"

    with pytest.raises(AuthorityError, match="actor or intent"):
        CycleReceipt.seal_completed(
            deliberation,
            proposal,
            attacker_grant,
            observation,
            effect_key,
        )


def test_world_verifier_rejects_resealed_receipt_with_forged_authority(
    tmp_path: Path,
) -> None:
    system, world, deliberation, proposal = _deliberation(tmp_path)
    receipt = system.run_cycle(deliberation, _grant(deliberation, proposal))
    forged_grant_id = "sha256:" + "a" * 64
    forged_body = {**receipt.identity_payload(), "grant_id": forged_grant_id}
    forged_seal = canonical_digest(forged_body)
    forged = replace(
        receipt,
        grant_id=forged_grant_id,
        seal=forged_seal,
        receipt_id=f"shakti_cycle_{forged_seal.removeprefix('sha256:')[:24]}",
    )

    with pytest.raises(EvidenceError, match="authorized local execution"):
        PolicyDelta.create(
            deliberation.context.policy,
            forged,
            verifier=world,
            proposed_weights={"builder": 1, "witness": 2},
            interpretation="A forged receipt must not acquire standing.",
        )


def test_intent_cannot_allow_an_explicitly_prohibited_effect() -> None:
    with pytest.raises(AuthorityError, match="also explicitly prohibited"):
        replace(
            _intent(),
            prohibited_effects=("write_local_artifact", "external_contact"),
        )


def test_missing_observation_cannot_close_cycle(tmp_path: Path) -> None:
    fence = CountingFence()
    system = ShaktiSystem(_agents(), ExplodingWorld(), fence)
    deliberation = system.deliberate(_context())
    proposal = deliberation.proposal(deliberation.recommended_proposal_id)

    with pytest.raises(EvidenceError, match="no observed consequence"):
        system.run_cycle(deliberation, _grant(deliberation, proposal))

    assert fence.completed == []
    assert len(fence.failures) == 1


def test_unsafe_fixture_path_is_rejected_and_not_receipted(tmp_path: Path) -> None:
    context = _context()

    class TraversalAgent:
        agent_id = "builder"

        def propose(self, context: CycleContext) -> AgentProposal:
            return AgentProposal.create(
                agent_id=self.agent_id,
                context=context,
                title="unsafe",
                rationale="negative control",
                human_question="reject this",
                predicted_signal="none",
                action=ActionSpec(
                    effect_kind="write_local_artifact",
                    relative_path="../escape.txt",
                    content="must not escape",
                ),
            )

    fence = CountingFence()
    system = ShaktiSystem(
        (TraversalAgent(), ReferenceAgent("witness")),
        LocalArtifactWorld(tmp_path),
        fence,
    )
    deliberation = system.deliberate(context)
    proposal = next(item for item in deliberation.proposals if item.agent_id == "builder")

    with pytest.raises(PatchReplayError, match="unsafe immutable artifact path"):
        system.run_cycle(deliberation, _grant(deliberation, proposal))

    assert not (tmp_path.parent / "escape.txt").exists()
    assert fence.completed == []


def test_receipt_seal_is_stable_and_input_sensitive(tmp_path: Path) -> None:
    receipts = []
    for root in (tmp_path / "a", tmp_path / "b"):
        system, _, deliberation, proposal = _deliberation(root)
        receipts.append(system.run_cycle(deliberation, _grant(deliberation, proposal)))

    assert receipts[0].seal == receipts[1].seal
    assert receipts[0].receipt_id == receipts[1].receipt_id

    world = LocalArtifactWorld(tmp_path / "c")
    system = ShaktiSystem(_agents(), world, CountingFence())
    changed = system.deliberate(_context(session_id="another-session"))
    changed_proposal = changed.proposal(changed.recommended_proposal_id)
    changed_receipt = system.run_cycle(changed, _grant(changed, changed_proposal))
    assert changed_receipt.seal != receipts[0].seal


def test_observation_and_interpretation_are_distinct_typed_transitions(
    tmp_path: Path,
) -> None:
    system, world, deliberation, proposal = _deliberation(tmp_path)
    receipt = system.run_cycle(deliberation, _grant(deliberation, proposal))
    delta = PolicyDelta.create(
        deliberation.context.policy,
        receipt,
        verifier=world,
        proposed_weights={"builder": 1, "witness": 2},
        interpretation="An artifact exists; prioritize the witness next.",
    )

    assert "prioritize" not in " ".join(receipt.observation.observed_facts)
    assert delta.based_on_observation_id == receipt.observation.observation_id
    assert delta.interpretation.startswith("An artifact exists")

    bad = PolicyRatification.approve(
        delta,
        actor_id=deliberation.context.intent.owner_id,
        typed_confirmation="ratify wrong-delta",
        reason="wrong token",
    )
    with pytest.raises(AuthorityError, match="exact delta confirmation"):
        next_cycle_context(
            deliberation.context,
            receipt,
            delta,
            bad,
            verifier=world,
            cycle_id="cycle-2",
            prior_run_id="run-cycle-1",
        )


def test_missing_artifact_cannot_be_verified_or_promoted(tmp_path: Path) -> None:
    system, world, deliberation, proposal = _deliberation(tmp_path)
    receipt = system.run_cycle(deliberation, _grant(deliberation, proposal))
    (tmp_path / receipt.observation.artifact_locator).unlink()

    with pytest.raises(EvidenceError, match="unavailable"):
        world.verify_receipt(receipt)
    with pytest.raises(EvidenceError, match="unavailable"):
        PolicyDelta.create(
            deliberation.context.policy,
            receipt,
            verifier=world,
            proposed_weights={"builder": 1, "witness": 2},
            interpretation="A missing artifact cannot affect policy.",
        )


def test_structural_verifier_cannot_acquire_epistemic_standing(tmp_path: Path) -> None:
    class LyingVerifier:
        def verify_receipt(self, receipt: CycleReceipt) -> None:
            return None

    system, _, deliberation, proposal = _deliberation(tmp_path)
    receipt = system.run_cycle(deliberation, _grant(deliberation, proposal))

    with pytest.raises(EvidenceError, match="concrete local world adapter"):
        PolicyDelta.create(
            deliberation.context.policy,
            receipt,
            verifier=LyingVerifier(),
            proposed_weights={"builder": 1, "witness": 2},
            interpretation="Structural typing is not verification authority.",
        )


def test_different_local_world_cannot_verify_an_unissued_receipt(tmp_path: Path) -> None:
    system, _, deliberation, proposal = _deliberation(tmp_path)
    receipt = system.run_cycle(deliberation, _grant(deliberation, proposal))
    other_world = LocalArtifactWorld(tmp_path)

    with pytest.raises(EvidenceError, match="authorized local execution"):
        PolicyDelta.create(
            deliberation.context.policy,
            receipt,
            verifier=other_world,
            proposed_weights={"builder": 1, "witness": 2},
            interpretation="The executing adapter must perform the re-read.",
        )


def test_two_cycle_loop_is_causally_changed_by_ratified_evidence(tmp_path: Path) -> None:
    context_one = _context()
    world = LocalArtifactWorld(tmp_path)
    system_one = ShaktiSystem(_agents(), world, CountingFence())
    deliberation_one = system_one.deliberate(context_one)
    proposal_one = deliberation_one.proposal(deliberation_one.recommended_proposal_id)
    receipt_one = system_one.run_cycle(
        deliberation_one,
        _grant(deliberation_one, proposal_one),
    )
    assert receipt_one.selected_agent_id == "builder"

    delta = PolicyDelta.create(
        context_one.policy,
        receipt_one,
        verifier=world,
        proposed_weights={"builder": 1, "witness": 2},
        interpretation="The builder result exists; make its witness explicit.",
    )
    ratification = PolicyRatification.approve(
        delta,
        actor_id=context_one.intent.owner_id,
        typed_confirmation=expected_ratification(delta.delta_id),
        reason="I accept this meaning for the next bounded cycle.",
    )
    context_two = next_cycle_context(
        context_one,
        receipt_one,
        delta,
        ratification,
        verifier=world,
        cycle_id="cycle-2",
        prior_run_id="run-cycle-1",
    )
    system_two = ShaktiSystem(_agents(), world, CountingFence())
    deliberation_two = system_two.deliberate(context_two)
    proposal_two = deliberation_two.proposal(deliberation_two.recommended_proposal_id)

    assert proposal_two.agent_id == "witness"
    assert proposal_two.based_on_observation_id == receipt_one.observation.observation_id
    assert context_two.input_hash != context_one.input_hash
    assert context_two.revision_reason == delta.interpretation
    assert world.verification_count == 3


def test_revised_context_cannot_be_forged_without_claim_bundle(tmp_path: Path) -> None:
    system, world, deliberation, proposal = _deliberation(tmp_path)
    receipt = system.run_cycle(deliberation, _grant(deliberation, proposal))
    delta = PolicyDelta.create(deliberation.context.policy, receipt, verifier=world,
                               proposed_weights={"builder": 1, "witness": 2},
                               interpretation="Bounded interpretation.")
    policy = PolicyState(revision=1, agent_weights=delta.proposed_weights,
                         causal_receipt_id=receipt.receipt_id,
                         causal_observation_id=receipt.observation.observation_id,
                         causal_artifact_digest=receipt.observation.artifact_digest,
                         interpretation=delta.interpretation)
    with pytest.raises(CausalityError, match="complete promotion claim bundle"):
        CycleContext(cycle_id="cycle-2", session_id=deliberation.context.session_id,
                     intent=deliberation.context.intent, policy=policy,
                     prior_receipt_id=receipt.receipt_id,
                     prior_observation_id=receipt.observation.observation_id,
                     revision_reason=delta.interpretation, prior_run_id="run-1")


def test_reentrant_context_validation_rejects_mutated_policy(tmp_path: Path) -> None:
    system, world, deliberation, proposal = _deliberation(tmp_path)
    receipt = system.run_cycle(deliberation, _grant(deliberation, proposal))
    delta = PolicyDelta.create(deliberation.context.policy, receipt, verifier=world,
                               proposed_weights={"builder": 1, "witness": 2}, interpretation="Bounded.")
    ratification = PolicyRatification.approve(delta, actor_id=deliberation.context.intent.owner_id,
                                               typed_confirmation=expected_ratification(delta.delta_id), reason="Approve.")
    context = next_cycle_context(deliberation.context, receipt, delta, ratification,
                                 verifier=world, cycle_id="cycle-2", prior_run_id="run-1")
    object.__setattr__(context, "policy", replace(context.policy, agent_weights=(("builder", 99), ("witness", 0))))
    with pytest.raises(CausalityError, match="policy delta"):
        system.deliberate(context)


def test_reentrant_context_validation_rejects_mutated_delta(tmp_path: Path) -> None:
    system, world, deliberation, proposal = _deliberation(tmp_path)
    receipt = system.run_cycle(deliberation, _grant(deliberation, proposal))
    delta = PolicyDelta.create(
        deliberation.context.policy,
        receipt,
        verifier=world,
        proposed_weights={"builder": 1, "witness": 2},
        interpretation="Bounded.",
    )
    ratification = PolicyRatification.approve(
        delta,
        actor_id=deliberation.context.intent.owner_id,
        typed_confirmation=expected_ratification(delta.delta_id),
        reason="Approve.",
    )
    context = next_cycle_context(
        deliberation.context,
        receipt,
        delta,
        ratification,
        verifier=world,
        cycle_id="cycle-2",
        prior_run_id="run-1",
    )
    forged_weights = (("builder", 99), ("witness", 0))
    assert context.policy_delta is not None
    object.__setattr__(context.policy_delta, "proposed_weights", forged_weights)
    object.__setattr__(
        context,
        "policy",
        replace(context.policy, agent_weights=forged_weights),
    )

    with pytest.raises(CausalityError, match="policy delta id"):
        system.deliberate(context)


def test_revised_context_rechecks_exact_revision_types(tmp_path: Path) -> None:
    system, world, deliberation, receipt, delta, ratification = _promotion_inputs(
        tmp_path
    )
    context = next_cycle_context(
        deliberation.context,
        receipt,
        delta,
        ratification,
        verifier=world,
        cycle_id="cycle-2",
        prior_run_id="run-1",
    )
    object.__setattr__(context.policy, "revision", True)
    with pytest.raises(ValueError, match="policy revision must be an exact integer"):
        system.deliberate(context)

    object.__setattr__(context.policy, "revision", 1)
    assert context.policy_delta is not None
    object.__setattr__(context.policy_delta, "prior_revision", False)
    with pytest.raises(ValueError, match="prior revision must be an exact integer"):
        system.deliberate(context)


def test_ratification_requires_exact_boolean_at_both_evaluators(
    tmp_path: Path,
) -> None:
    system, world, deliberation, receipt, delta, ratification = _promotion_inputs(
        tmp_path
    )
    context = next_cycle_context(
        deliberation.context,
        receipt,
        delta,
        ratification,
        verifier=world,
        cycle_id="cycle-2",
        prior_run_id="run-1",
    )
    object.__setattr__(ratification, "approved", 1)
    object.__setattr__(
        ratification,
        "ratification_id",
        canonical_digest(ratification.identity_payload()),
    )

    with pytest.raises(ValueError, match="approved must be a boolean"):
        system.deliberate(context)
    with pytest.raises(ValueError, match="approved must be a boolean"):
        next_cycle_context(
            deliberation.context,
            receipt,
            delta,
            ratification,
            verifier=world,
            cycle_id="cycle-2-again",
            prior_run_id="run-1",
        )


def test_revised_context_rejects_fabricated_revision_jump(tmp_path: Path) -> None:
    system, world, deliberation, proposal = _deliberation(tmp_path)
    receipt = system.run_cycle(deliberation, _grant(deliberation, proposal))
    delta_body = {
        "prior_revision": 1,
        "proposed_weights": [["builder", 1], ["witness", 2]],
        "based_on_receipt_id": receipt.receipt_id,
        "based_on_observation_id": receipt.observation.observation_id,
        "based_on_artifact_digest": receipt.observation.artifact_digest,
        "interpretation": "A fabricated jump over an unobserved revision.",
    }
    delta = PolicyDelta(
        delta_id=canonical_digest(delta_body),
        prior_revision=1,
        proposed_weights=(("builder", 1), ("witness", 2)),
        based_on_receipt_id=receipt.receipt_id,
        based_on_observation_id=receipt.observation.observation_id,
        based_on_artifact_digest=receipt.observation.artifact_digest,
        interpretation=delta_body["interpretation"],
    )
    ratification = PolicyRatification.approve(
        delta,
        actor_id=deliberation.context.intent.owner_id,
        typed_confirmation=expected_ratification(delta.delta_id),
        reason="This is syntactically self-consistent but causally false.",
    )
    policy = PolicyState(
        revision=2,
        agent_weights=delta.proposed_weights,
        causal_receipt_id=receipt.receipt_id,
        causal_observation_id=receipt.observation.observation_id,
        causal_artifact_digest=receipt.observation.artifact_digest,
        interpretation=delta.interpretation,
    )

    with pytest.raises(CausalityError, match="revision 1"):
        CycleContext(
            cycle_id="cycle-3",
            session_id=deliberation.context.session_id,
            intent=deliberation.context.intent,
            policy=policy,
            prior_receipt_id=receipt.receipt_id,
            prior_observation_id=receipt.observation.observation_id,
            revision_reason=delta.interpretation,
            prior_run_id="run-1",
            prior_receipt=receipt,
            policy_delta=delta,
            policy_ratification=ratification,
        )


def test_revised_context_rechecks_exact_world_at_deliberation(tmp_path: Path) -> None:
    system, world, deliberation, proposal = _deliberation(tmp_path)
    receipt = system.run_cycle(deliberation, _grant(deliberation, proposal))
    delta = PolicyDelta.create(deliberation.context.policy, receipt, verifier=world,
                               proposed_weights={"builder": 1, "witness": 2},
                               interpretation="Bounded interpretation.")
    ratification = PolicyRatification.approve(delta, actor_id=deliberation.context.intent.owner_id,
                                               typed_confirmation=expected_ratification(delta.delta_id), reason="Approve.")
    context = next_cycle_context(deliberation.context, receipt, delta, ratification,
                                 verifier=world, cycle_id="cycle-2", prior_run_id="run-1")
    with pytest.raises(EvidenceError, match="authorized local execution"):
        ShaktiSystem(_agents(), LocalArtifactWorld(tmp_path / "other"), CountingFence()).deliberate(context)


def test_revised_context_artifact_deletion_rejected_at_deliberate(tmp_path: Path) -> None:
    system, world, deliberation, proposal = _deliberation(tmp_path)
    receipt = system.run_cycle(deliberation, _grant(deliberation, proposal))
    delta = PolicyDelta.create(deliberation.context.policy, receipt, verifier=world,
                               proposed_weights={"builder": 1, "witness": 2}, interpretation="Still bounded.")
    ratification = PolicyRatification.approve(delta, actor_id=deliberation.context.intent.owner_id,
                                               typed_confirmation=expected_ratification(delta.delta_id), reason="Approve.")
    context = next_cycle_context(deliberation.context, receipt, delta, ratification,
                                 verifier=world, cycle_id="cycle-2", prior_run_id="run-1")
    (tmp_path / receipt.observation.artifact_locator).unlink()
    with pytest.raises(EvidenceError, match="unavailable"):
        system.deliberate(context)


def test_revised_context_rejects_tampered_ratification(tmp_path: Path) -> None:
    system, world, deliberation, proposal = _deliberation(tmp_path)
    receipt = system.run_cycle(deliberation, _grant(deliberation, proposal))
    delta = PolicyDelta.create(deliberation.context.policy, receipt, verifier=world,
                               proposed_weights={"builder": 1, "witness": 2}, interpretation="Bounded.")
    ratification = PolicyRatification.approve(delta, actor_id=deliberation.context.intent.owner_id,
                                               typed_confirmation=expected_ratification(delta.delta_id), reason="Approve.")
    with pytest.raises(AuthorityError, match="ratification id"):
        replace(ratification, typed_confirmation="ratify forged")


def test_artifact_deleted_after_delta_cannot_enter_next_cycle(tmp_path: Path) -> None:
    system, world, deliberation, proposal = _deliberation(tmp_path)
    receipt = system.run_cycle(deliberation, _grant(deliberation, proposal))
    delta = PolicyDelta.create(
        deliberation.context.policy,
        receipt,
        verifier=world,
        proposed_weights={"builder": 1, "witness": 2},
        interpretation="This remains provisional until next-cycle admission.",
    )
    ratification = PolicyRatification.approve(
        delta,
        actor_id=deliberation.context.intent.owner_id,
        typed_confirmation=expected_ratification(delta.delta_id),
        reason="Approve only if the artifact still exists at admission.",
    )
    (tmp_path / receipt.observation.artifact_locator).unlink()

    with pytest.raises(EvidenceError, match="unavailable"):
        next_cycle_context(
            deliberation.context,
            receipt,
            delta,
            ratification,
            verifier=world,
            cycle_id="cycle-2",
            prior_run_id="run-cycle-1",
        )

    assert world.verification_count == 1


def test_no_public_ratification_bypass_exists() -> None:
    core = importlib.import_module("dharma_swarm.foundry.shakti_system")

    assert not hasattr(core, "ratify_policy")
    with pytest.raises(ImportError):
        exec("from dharma_swarm.foundry.shakti_system import ratify_policy", {})


def test_next_cycle_rejects_delta_based_on_other_evidence(tmp_path: Path) -> None:
    system, world, deliberation, proposal = _deliberation(tmp_path)
    receipt = system.run_cycle(deliberation, _grant(deliberation, proposal))
    other_context = _context(session_id="other-session")
    other_world = LocalArtifactWorld(tmp_path / "other")
    other_system = ShaktiSystem(_agents(), other_world, CountingFence())
    other_deliberation = other_system.deliberate(other_context)
    other_proposal = other_deliberation.proposal(
        other_deliberation.recommended_proposal_id
    )
    other_receipt = other_system.run_cycle(
        other_deliberation,
        _grant(other_deliberation, other_proposal),
    )
    unrelated = PolicyDelta.create(
        deliberation.context.policy,
        other_receipt,
        verifier=other_world,
        proposed_weights={"builder": 0, "witness": 1},
        interpretation="This interpretation cites another cycle.",
    )
    ratification = PolicyRatification.approve(
        unrelated,
        actor_id=deliberation.context.intent.owner_id,
        typed_confirmation=expected_ratification(unrelated.delta_id),
        reason="Valid approval, wrong causal evidence.",
    )

    with pytest.raises(CausalityError, match="does not cite"):
        next_cycle_context(
            deliberation.context,
            receipt,
            unrelated,
            ratification,
            verifier=world,
            cycle_id="cycle-2",
            prior_run_id="run-cycle-1",
        )


def test_kill_switch_stops_deliberation_and_execution(tmp_path: Path) -> None:
    system, world, deliberation, proposal = _deliberation(tmp_path)
    system.stop("operator stop")

    with pytest.raises(SystemStopped, match="operator stop"):
        system.deliberate(_context())
    with pytest.raises(SystemStopped, match="operator stop"):
        system.run_cycle(deliberation, _grant(deliberation, proposal))
    assert world.execution_count == 0


def test_noop_fence_cannot_promote_local_receipt(tmp_path: Path) -> None:
    context = _context()
    world = LocalArtifactWorld(tmp_path)
    system = ShaktiSystem(_agents(), world, NoopFence())
    deliberation = system.deliberate(context)
    proposal = deliberation.proposal(deliberation.recommended_proposal_id)
    with pytest.raises(EvidenceError, match="terminal cycle marker"):
        system.run_cycle(deliberation, _grant(deliberation, proposal))


def test_demo_preview_performs_no_effect_or_runtime_write(tmp_path: Path) -> None:
    artifact_root = tmp_path / "preview"
    runtime_db = tmp_path / "preview.sqlite3"

    report = run_demo(
        artifact_root=artifact_root,
        runtime_db=runtime_db,
        preauthorize_canned_demo=False,
    )

    assert report["status"] == "preview_only"
    assert report["no_effect_executed"] is True
    assert not artifact_root.exists()
    assert not runtime_db.exists()


def test_runtime_fence_rejects_cross_proposal_identity_before_effect(
    tmp_path: Path,
) -> None:
    context = _context()
    world = LocalArtifactWorld(tmp_path / "world")
    deliberation = ShaktiSystem(_agents(), world, CountingFence()).deliberate(context)
    builder = next(item for item in deliberation.proposals if item.agent_id == "builder")
    witness = next(item for item in deliberation.proposals if item.agent_id == "witness")
    builder_grant = _grant(deliberation, builder)
    witness_identity = _identity_for_cycle(
        context=context,
        proposal=witness,
        correlation_id="correlation-cross-proposal",
    )
    store = RuntimeStateStore(tmp_path / "runtime.sqlite3", include_memory_plane=False)

    with pytest.raises(CausalityError, match="runtime identity does not bind"):
        RuntimeEffectFence(
            store=store,
            identity=witness_identity,
            operator_id=context.intent.owner_id,
            deliberation=deliberation,
            grant=builder_grant,
        )

    builder_effect = (
        f"shakti_effect:{builder.proposal_id.removeprefix('sha256:')[:24]}"
    )
    assert (
        store.get_idempotency_record_sync(
            witness_identity.idempotency_key,
            builder_effect,
        )
        is None
    )
    assert world.execution_count == 0


def test_runtime_fence_duplicate_retry_preserves_completed_truth(tmp_path: Path) -> None:
    context = _context()
    world = LocalArtifactWorld(tmp_path / "world")
    deliberation = ShaktiSystem(_agents(), world, CountingFence()).deliberate(context)
    proposal = deliberation.proposal(deliberation.recommended_proposal_id)
    grant = _grant(deliberation, proposal)
    identity = _identity_for_cycle(
        context=context,
        proposal=proposal,
        correlation_id="correlation-retry",
    )
    store = RuntimeStateStore(tmp_path / "runtime.sqlite3", include_memory_plane=False)
    first_fence = RuntimeEffectFence(
        store=store,
        identity=identity,
        operator_id=context.intent.owner_id,
        deliberation=deliberation,
        grant=grant,
    )
    receipt = ShaktiSystem(_agents(), world, first_fence).run_cycle(deliberation, grant)
    before = store.get_idempotency_record_sync(
        identity.idempotency_key,
        receipt.effect_key,
    )

    retry_fence = RuntimeEffectFence(
        store=store,
        identity=identity,
        operator_id=context.intent.owner_id,
        deliberation=deliberation,
        grant=grant,
    )
    with pytest.raises(DuplicateEffect):
        ShaktiSystem(_agents(), world, retry_fence).run_cycle(deliberation, grant)

    after = store.get_idempotency_record_sync(identity.idempotency_key, receipt.effect_key)
    receipts = asyncio.run(
        store.list_runtime_receipts(
            correlation_id=identity.correlation_id,
            receipt_type="participatory_cycle",
        )
    )
    assert before is not None and after is not None
    assert (after.status, after.result_receipt_id) == (
        before.status,
        before.result_receipt_id,
    ) == ("completed", receipt.receipt_id)
    assert world.execution_count == 1
    assert [item.receipt_id for item in receipts] == [receipt.receipt_id]
    assert store.get_task_claim_sync(identity.claim_id) is None
    assert store.get_delegation_run_sync(identity.run_id) is None


def test_failed_terminal_marker_stays_fenced_without_false_commit(tmp_path: Path) -> None:
    class MarkerFailStore(RuntimeStateStore):
        def record_session_event_with_runtime_receipt_sync(self, event, receipt):
            raise RuntimeError("injected terminal marker failure")

    context = _context()
    world = LocalArtifactWorld(tmp_path / "world")
    deliberation = ShaktiSystem(_agents(), world, CountingFence()).deliberate(context)
    proposal = deliberation.proposal(deliberation.recommended_proposal_id)
    grant = _grant(deliberation, proposal)
    identity = _identity_for_cycle(
        context=context,
        proposal=proposal,
        correlation_id="correlation-marker-failure",
    )
    store = MarkerFailStore(tmp_path / "runtime.sqlite3", include_memory_plane=False)
    fence = RuntimeEffectFence(
        store=store,
        identity=identity,
        operator_id=context.intent.owner_id,
        deliberation=deliberation,
        grant=grant,
    )
    with pytest.raises(RuntimeError, match="terminal marker failure"):
        ShaktiSystem(_agents(), world, fence).run_cycle(deliberation, grant)

    effect_key = f"shakti_effect:{proposal.proposal_id.removeprefix('sha256:')[:24]}"
    record = store.get_idempotency_record_sync(identity.idempotency_key, effect_key)
    receipts = asyncio.run(
        store.list_runtime_receipts(
            correlation_id=identity.correlation_id,
            receipt_type="participatory_cycle",
        )
    )
    retry = RuntimeEffectFence(
        store=store,
        identity=identity,
        operator_id=context.intent.owner_id,
        deliberation=deliberation,
        grant=grant,
    )
    with pytest.raises(DuplicateEffect):
        ShaktiSystem(_agents(), world, retry).run_cycle(deliberation, grant)

    stranded_receipt = next(iter(world._pending_receipts.values()))
    with pytest.raises(EvidenceError, match="authorized local execution"):
        PolicyDelta.create(
            context.policy,
            stranded_receipt,
            verifier=world,
            proposed_weights={"builder": 1, "witness": 2},
            interpretation="A stranded effect cannot become causal standing.",
        )

    assert record is not None and record.status == "completed"
    assert receipts == []
    assert world.execution_count == 1


def test_silent_terminal_marker_noop_cannot_promote_receipt(tmp_path: Path) -> None:
    class SilentMarkerStore(RuntimeStateStore):
        def record_session_event_with_runtime_receipt_sync(self, event, receipt):
            return event, receipt

    context = _context()
    world = LocalArtifactWorld(tmp_path / "world")
    deliberation = ShaktiSystem(_agents(), world, CountingFence()).deliberate(context)
    proposal = deliberation.proposal(deliberation.recommended_proposal_id)
    grant = _grant(deliberation, proposal)
    identity = _identity_for_cycle(
        context=context,
        proposal=proposal,
        correlation_id="correlation-silent-marker-noop",
    )
    store = SilentMarkerStore(tmp_path / "runtime.sqlite3", include_memory_plane=False)
    fence = RuntimeEffectFence(
        store=store,
        identity=identity,
        operator_id=context.intent.owner_id,
        deliberation=deliberation,
        grant=grant,
    )

    with pytest.raises(EvidenceError, match="terminal cycle marker"):
        ShaktiSystem(_agents(), world, fence).run_cycle(deliberation, grant)

    receipts = asyncio.run(
        store.list_runtime_receipts(
            run_id=identity.run_id,
            receipt_type="participatory_cycle",
        )
    )
    stranded_receipt = next(iter(world._pending_receipts.values()))
    with pytest.raises(EvidenceError, match="authorized local execution"):
        PolicyDelta.create(
            context.policy,
            stranded_receipt,
            verifier=world,
            proposed_weights={"builder": 1, "witness": 2},
            interpretation="A silent persistence no-op cannot gain causal standing.",
        )

    assert receipts == []
    assert world.execution_count == 1


def test_runtime_world_failure_records_no_cycle_commit(tmp_path: Path) -> None:
    context = _context()
    deliberation = ShaktiSystem(
        _agents(),
        LocalArtifactWorld(tmp_path / "unused"),
        CountingFence(),
    ).deliberate(context)
    proposal = deliberation.proposal(deliberation.recommended_proposal_id)
    grant = _grant(deliberation, proposal)
    identity = _identity_for_cycle(
        context=context,
        proposal=proposal,
        correlation_id="correlation-world-failure",
    )
    store = RuntimeStateStore(tmp_path / "runtime.sqlite3", include_memory_plane=False)
    fence = RuntimeEffectFence(
        store=store,
        identity=identity,
        operator_id=context.intent.owner_id,
        deliberation=deliberation,
        grant=grant,
    )
    with pytest.raises(EvidenceError, match="no observed consequence"):
        ShaktiSystem(_agents(), ExplodingWorld(), fence).run_cycle(deliberation, grant)

    effect_key = f"shakti_effect:{proposal.proposal_id.removeprefix('sha256:')[:24]}"
    record = store.get_idempotency_record_sync(identity.idempotency_key, effect_key)
    receipts = asyncio.run(
        store.list_runtime_receipts(
            correlation_id=identity.correlation_id,
            receipt_type="participatory_cycle",
        )
    )
    assert record is not None and record.status == "failed"
    assert receipts == []


def test_demo_closes_two_cycles_in_runtime_state(tmp_path: Path) -> None:
    runtime_db = tmp_path / "runtime.sqlite3"
    report = run_demo(
        artifact_root=tmp_path / "world",
        runtime_db=runtime_db,
        preauthorize_canned_demo=True,
    )

    assert report["status"] == "completed_canned_local_fixture"
    assert report["causal_loop_proven"] is True
    assert report["world_effect_count"] == 2
    assert report["local_artifact_verification_count"] == 5
    assert report["external_world_contact"] is False
    assert report["model_provider_used"] is False
    assert len(list((tmp_path / "world" / "cycles").glob("*/*.json"))) == 2

    one = report["cycle_one"]
    two = report["cycle_two"]
    assert "verified_evidence" not in one
    assert "verified_evidence" not in two
    assert two["identity"]["parent_run_id"] == one["identity"]["run_id"]
    assert (
        two["identity"]["causation_id"]
        == one["receipt"]["observation"]["observation_id"]
    )
    assert (
        two["receipt"]["prior_observation_id"]
        == one["receipt"]["observation"]["observation_id"]
    )

    store = RuntimeStateStore(runtime_db, include_memory_plane=False)
    receipts = asyncio.run(
        store.list_runtime_receipts(
            correlation_id=report["correlation_id"],
            receipt_type="participatory_cycle",
            limit=10,
        )
    )
    actions = asyncio.run(store.list_operator_actions(session_id=report["session_id"]))
    events = asyncio.run(store.list_session_events(session_id=report["session_id"], limit=20))
    assert [receipt.status for receipt in receipts] == ["completed", "completed"]
    assert {action.action_name for action in actions} == {
        "approve_participatory_proposal",
        "ratify_policy_delta",
    }
    assert {event.event_name for event in events} >= {
        "approval_requested",
        "operator_grant",
        "world_observation",
        "policy_ratified",
    }
