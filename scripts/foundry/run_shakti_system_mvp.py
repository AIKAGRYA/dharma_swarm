#!/usr/bin/env python3
"""Run the offline two-cycle Shakti System MVP.

Without ``--preauthorize-canned-demo`` this command previews the first authority
boundary and performs no fixture effect.  With the flag, fixed grants and a
fixed interpretation exercise the bounded two-cycle plumbing; this is not an
interactive human-choice test.  No model provider or network is used.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import uuid4

# Allow running as a plain script from the repo root.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from dharma_swarm.foundry.evaluator import canonical_digest  # noqa: E402
from dharma_swarm.foundry.shakti_local_world import LocalArtifactWorld  # noqa: E402
from dharma_swarm.foundry.shakti_system import (  # noqa: E402
    ActionSpec,
    AgentProposal,
    AuthorityError,
    AuthorityGrant,
    CausalityError,
    CycleContext,
    CycleReceipt,
    Deliberation,
    EffectFence,
    IntentContract,
    PolicyDelta,
    PolicyRatification,
    PolicyState,
    ShaktiSystem,
    expected_approval,
    expected_ratification,
    next_cycle_context,
    validate_authority_grant,
)
from dharma_swarm.operator_core.reversibility_gate import (  # noqa: E402
    ActionClass,
    classify_action,
)
from dharma_swarm.runtime_state import (  # noqa: E402
    OperatorAction,
    RuntimeStateStore,
    SessionEventRecord,
)
from dharma_swarm.spine.identity import ExecutionIdentity  # noqa: E402


def _event_id(name: str, payload: dict[str, Any]) -> str:
    digest = canonical_digest({"name": name, "payload": payload})
    return f"shakti_event_{digest.removeprefix('sha256:')[:24]}"


def _idempotency_key(context: CycleContext, proposal: AgentProposal) -> str:
    digest = canonical_digest(
        {
            "session_id": context.session_id,
            "cycle_id": context.cycle_id,
            "proposal_id": proposal.proposal_id,
        }
    )
    return f"idem_{digest.removeprefix('sha256:')[:24]}"


@dataclass(frozen=True, slots=True)
class ReferenceAgent:
    """Deterministic stand-in for a model-backed agent seat."""

    agent_id: str

    def propose(self, context: CycleContext) -> AgentProposal:
        if self.agent_id == "builder":
            title = "Materialize the smallest inspectable next step"
            rationale = (
                "Create one bounded artifact so the intention acquires an observable "
                "consequence instead of remaining a discussion."
            )
            predicted = "an immutable artifact exists and its bytes can be re-read"
        elif self.agent_id == "witness":
            title = "Materialize a witness checkpoint"
            rationale = (
                "Make the causal history inspectable, especially what prior observation "
                "the current move is responding to."
            )
            predicted = "a checkpoint explicitly cites the prior observation"
        else:  # pragma: no cover - constructor use is fixed by the demo
            raise ValueError(f"unknown reference agent: {self.agent_id}")
        content = json.dumps(
            {
                "agent": self.agent_id,
                "cycle": context.cycle_id,
                "intent": context.intent.purpose,
                "visible_success": context.intent.visible_success,
                "policy_revision": context.policy.revision,
                "based_on_observation": context.prior_observation_id or None,
                "revision_reason": context.revision_reason or None,
                "claim_boundary": "local fixture; not external-world proof",
            },
            indent=2,
            sort_keys=True,
        ) + "\n"
        action = ActionSpec(
            effect_kind="write_local_artifact",
            relative_path=(
                f"cycles/{context.cycle_id}/{self.agent_id}-"
                f"{context.input_hash.removeprefix('sha256:')[:12]}.json"
            ),
            content=content,
        )
        return AgentProposal.create(
            agent_id=self.agent_id,
            context=context,
            title=title,
            rationale=rationale,
            human_question=context.intent.human_blank,
            predicted_signal=predicted,
            action=action,
        )


class RejectingFence:
    """A deliberation-only fence used before any operator grant exists."""

    def begin(self, effect_key: str, operation_hash: str) -> bool:
        raise RuntimeError(f"unbound effect fence: {effect_key}:{operation_hash}")

    def complete(self, receipt: CycleReceipt) -> None:
        raise RuntimeError(f"unbound effect fence: {receipt.receipt_id}")

    def fail(self, effect_key: str, operation_hash: str, reason: str) -> None:
        return None

class RuntimeEffectFence(EffectFence):
    """Persist a granted local effect without inventing task/run lifecycle state."""

    def __init__(
        self,
        *,
        store: RuntimeStateStore,
        identity: ExecutionIdentity,
        operator_id: str,
        deliberation: Deliberation,
        grant: AuthorityGrant,
    ) -> None:
        self.store = store
        self.identity = identity.require_for_dispatch()
        self.operator_id = operator_id
        self.deliberation = deliberation
        self.grant = grant
        deliberation.require_valid()
        self.proposal = deliberation.proposal(grant.proposal_id)
        validate_authority_grant(deliberation, self.proposal, grant)
        self._require_bound_identity()
        self._started = False
        self._closed = False
        self._completed_receipt_id = ""

    def _require_bound_identity(self) -> None:
        context = self.deliberation.context
        proposal = self.proposal
        identity = self.identity
        if self.operator_id != context.intent.owner_id:
            raise AuthorityError("runtime operator does not own the intent contract")
        expected = {
            "session_id": context.session_id,
            "task_id": context.intent.intent_id,
            "agent_id": proposal.agent_id,
            "proposal_id": proposal.proposal_id,
            "causation_id": context.prior_observation_id,
            "idempotency_key": _idempotency_key(context, proposal),
        }
        mismatches = [
            name for name, value in expected.items() if getattr(identity, name) != value
        ]
        if mismatches:
            raise CausalityError(
                "runtime identity does not bind the granted deliberation: "
                + ", ".join(mismatches)
            )
        if identity.parent_run_id != context.prior_run_id:
            raise CausalityError("runtime parent binding does not match prior-cycle state")
        if identity.metadata.get("cycle_id") != context.cycle_id:
            raise CausalityError("runtime identity does not bind the cycle id")
        if identity.metadata.get("proof_mode") != "local_fixture":
            raise CausalityError("runtime identity does not bind the local proof mode")

    def _require_bound_effect(self, effect_key: str, operation_hash: str) -> None:
        expected_effect = (
            "shakti_effect:"
            + self.proposal.proposal_id.removeprefix("sha256:")[:24]
        )
        if effect_key != expected_effect:
            raise CausalityError("runtime effect key does not bind the granted proposal")
        if operation_hash != self.proposal.action.operation_hash:
            raise CausalityError("runtime operation does not bind the granted proposal")

    def _require_bound_receipt(self, receipt: CycleReceipt) -> None:
        receipt.require_valid()
        context = self.deliberation.context
        expected = {
            "cycle_id": context.cycle_id,
            "session_id": context.session_id,
            "intent_id": context.intent.intent_id,
            "input_hash": context.input_hash,
            "prior_receipt_id": context.prior_receipt_id,
            "prior_observation_id": context.prior_observation_id,
            "revision_reason": context.revision_reason,
            "selected_proposal_id": self.proposal.proposal_id,
            "selected_agent_id": self.proposal.agent_id,
            "grant_id": self.grant.grant_id,
            "operation_hash": self.proposal.action.operation_hash,
        }
        mismatches = [
            name for name, value in expected.items() if getattr(receipt, name) != value
        ]
        if mismatches:
            raise CausalityError(
                "runtime receipt does not bind the granted deliberation: "
                + ", ".join(mismatches)
            )
        self._require_bound_effect(receipt.effect_key, receipt.operation_hash)

    def _event(
        self,
        event_name: str,
        payload: dict[str, Any],
        *,
        summary: str,
    ) -> SessionEventRecord:
        return SessionEventRecord(
            event_id=_event_id(event_name, {"run_id": self.identity.run_id, **payload}),
            session_id=self.identity.session_id,
            ledger_kind="participatory_runtime",
            event_name=event_name,
            task_id=self.identity.task_id,
            run_id=self.identity.run_id,
            agent_id=self.identity.agent_id,
            summary=summary,
            event_text=summary,
            payload=payload,
        )

    def _record_event(
        self,
        event_name: str,
        payload: dict[str, Any],
        *,
        summary: str,
    ) -> SessionEventRecord:
        return self.store.record_session_event_sync(
            self._event(event_name, payload, summary=summary)
        )

    def _record_operator_action(
        self,
        *,
        action_id: str,
        action_name: str,
        reason: str,
        payload: dict[str, Any],
    ) -> None:
        action = OperatorAction(
            action_id=action_id,
            action_name=action_name,
            actor=self.operator_id,
            session_id=self.identity.session_id,
            task_id=self.identity.task_id,
            run_id=self.identity.run_id,
            reason=reason,
            payload=payload,
        )
        asyncio.run(self.store.record_operator_action(action))

    def begin(self, effect_key: str, operation_hash: str) -> bool:
        self._require_bound_identity()
        self._require_bound_effect(effect_key, operation_hash)
        decision = classify_action("write note to local fixture", operator_reachable=True)
        if decision.action_class is not ActionClass.REVERSIBLE_SAFE:
            raise RuntimeError("reversibility classifier rejected the local fixture effect")
        self._started = self.store.try_begin_idempotent_side_effect_sync(
            self.identity,
            effect_key,
            metadata={
                "operation_hash": operation_hash,
                "grant_id": self.grant.grant_id,
                "proof_mode": "local_fixture",
            },
        )
        if not self._started:
            return False
        try:
            self.store.record_execution_identity_sync(
                self.identity,
                source="foundry.shakti_system_mvp",
            )
            self._record_event(
                "approval_requested",
                {
                    "deliberation": self.deliberation.to_dict(),
                    "expected_confirmation": expected_approval(
                        self.deliberation.proposal(self.grant.proposal_id)
                    ),
                },
                summary="Agent proposals reached an exact authority boundary",
            )
            self._record_operator_action(
                action_id=self.grant.grant_id,
                action_name="approve_participatory_proposal",
                reason=self.grant.reason,
                payload=self.grant.to_dict(),
            )
            self._record_event(
                "operator_grant",
                self.grant.to_dict(),
                summary="Operator granted one exact local proposal",
            )
        except Exception as exc:
            self.fail(effect_key, operation_hash, f"grant persistence failed: {exc}")
            raise
        return self._started

    def complete(self, receipt: CycleReceipt) -> None:
        self._require_bound_identity()
        self._require_bound_receipt(receipt)
        observation = receipt.observation
        record = self.store.get_idempotency_record_sync(
            self.identity.idempotency_key,
            receipt.effect_key,
        )
        if record is None or record.status != "started":
            raise RuntimeError("effect fence is not in the started state")
        self.store.complete_idempotent_side_effect_sync(
            self.identity,
            receipt.effect_key,
            status="completed",
            result_receipt_id=receipt.receipt_id,
            metadata={
                "operation_hash": receipt.operation_hash,
                "observation_id": observation.observation_id,
            },
            expected_updated_at=record.updated_at,
        )
        event = self._event(
            "world_observation",
            observation.to_dict(),
            summary="Local fixture consequence was re-read and hashed",
        )
        commit_marker = self.store.build_runtime_receipt(
            self.identity,
            receipt_id=receipt.receipt_id,
            receipt_type="participatory_cycle",
            status="completed",
            side_effect_key=receipt.effect_key,
            payload=receipt.to_dict(),
        )
        self.store.record_session_event_with_runtime_receipt_sync(event, commit_marker)
        self._completed_receipt_id = receipt.receipt_id
        self._closed = True

    def is_committed(self, receipt: CycleReceipt) -> bool:
        markers = asyncio.run(
            self.store.list_runtime_receipts(
                run_id=self.identity.run_id,
                receipt_type="participatory_cycle",
                limit=2,
            )
        )
        if (
            not self._closed
            or receipt.receipt_id != self._completed_receipt_id
            or len(markers) != 1
        ):
            return False
        marker = markers[0]
        return (
            marker.receipt_id == receipt.receipt_id
            and marker.status == "completed"
            and marker.run_id == self.identity.run_id
            and marker.idempotency_key == self.identity.idempotency_key
            and marker.side_effect_key == receipt.effect_key
            and marker.payload == receipt.to_dict()
        )

    def fail(self, effect_key: str, operation_hash: str, reason: str) -> None:
        record = self.store.get_idempotency_record_sync(
            self.identity.idempotency_key,
            effect_key,
        )
        if self._started and record is not None and record.status == "started":
            self.store.complete_idempotent_side_effect_sync(
                self.identity,
                effect_key,
                status="failed",
                metadata={"operation_hash": operation_hash, "failure_reason": reason},
                expected_updated_at=record.updated_at,
            )
        event_name = "cycle_commit_failed" if record and record.status == "completed" else "cycle_failed"
        self._record_event(
            event_name,
            {
                "effect_key": effect_key,
                "operation_hash": operation_hash,
                "reason": reason,
            },
            summary="Cycle failed without a completed outcome",
        )

def _identity_for_cycle(
    *,
    context: CycleContext,
    proposal: AgentProposal,
    correlation_id: str,
    parent_run_id: str = "",
    causation_id: str = "",
) -> ExecutionIdentity:
    return ExecutionIdentity.new(
        task_id=context.intent.intent_id,
        agent_id=proposal.agent_id,
        session_id=context.session_id,
        correlation_id=correlation_id,
        causation_id=causation_id,
        parent_run_id=parent_run_id,
        idempotency_key=_idempotency_key(context, proposal),
        proposal_id=proposal.proposal_id,
        metadata={"cycle_id": context.cycle_id, "proof_mode": "local_fixture"},
    )


def _record_ratification(
    fence: RuntimeEffectFence,
    delta: PolicyDelta,
    ratification: PolicyRatification,
) -> None:
    fence._record_operator_action(
        action_id=ratification.ratification_id,
        action_name="ratify_policy_delta",
        reason=ratification.reason,
        payload={"delta": delta.to_dict(), "ratification": ratification.to_dict()},
    )
    fence._record_event(
        "policy_ratified",
        {"delta": delta.to_dict(), "ratification": ratification.to_dict()},
        summary="Operator ratified the interpretation used by the next cycle",
    )


def _deliberate(
    agents: tuple[ReferenceAgent, ...],
    world: LocalArtifactWorld,
    context: CycleContext,
) -> Deliberation:
    return ShaktiSystem(agents, world, RejectingFence()).deliberate(context)


def run_demo(
    *,
    artifact_root: Path,
    runtime_db: Path,
    operator_id: str = "local-operator",
    preauthorize_canned_demo: bool = False,
) -> dict[str, Any]:
    """Run or preview the bounded demo and return its JSON-ready report."""
    session_id = f"shakti_session_{uuid4().hex[:16]}"
    correlation_id = f"shakti_correlation_{uuid4().hex[:16]}"
    intent = IntentContract(
        intent_id="shakti-system-mvp",
        owner_id=operator_id,
        purpose=(
            "Turn a human intention into a bounded world consequence whose observation "
            "changes the next human-AI cycle."
        ),
        visible_success=(
            "cycle two explicitly cites cycle one's observation and changes proposal priority"
        ),
        human_blank="Which proposal do you authorize, and why is it the right next move?",
    )
    initial_policy = PolicyState(
        revision=0,
        agent_weights=(("builder", 1), ("witness", 0)),
    )
    context_one = CycleContext(
        cycle_id="cycle-1",
        session_id=session_id,
        intent=intent,
        policy=initial_policy,
    )
    agents = (ReferenceAgent("builder"), ReferenceAgent("witness"))
    world = LocalArtifactWorld(artifact_root)
    deliberation_one = _deliberate(agents, world, context_one)
    proposal_one = deliberation_one.proposal(deliberation_one.recommended_proposal_id)
    pending = {
        "status": "preview_only",
        "interaction_mode": "authority_boundary_preview",
        "proof_mode": "local_fixture",
        "external_world_contact": False,
        "model_provider_used": False,
        "intent": intent.to_dict(),
        "deliberation": deliberation_one.to_dict(),
        "expected_confirmation": expected_approval(proposal_one),
        "no_effect_executed": world.execution_count == 0,
        "claim_boundary": (
            "This is a local causal fixture, not proof of cosmic provenance or "
            "external-world usefulness."
        ),
    }
    if not preauthorize_canned_demo:
        return pending

    store = RuntimeStateStore(runtime_db, include_memory_plane=False)
    grant_one = AuthorityGrant.approve(
        deliberation_one,
        proposal_one.proposal_id,
        actor_id=operator_id,
        typed_confirmation=expected_approval(proposal_one),
        reason="Fixed preauthorization for the canned local fixture.",
    )
    identity_one = _identity_for_cycle(
        context=context_one,
        proposal=proposal_one,
        correlation_id=correlation_id,
    )
    fence_one = RuntimeEffectFence(
        store=store,
        identity=identity_one,
        operator_id=operator_id,
        deliberation=deliberation_one,
        grant=grant_one,
    )
    receipt_one = ShaktiSystem(agents, world, fence_one).run_cycle(
        deliberation_one,
        grant_one,
    )

    interpretation = (
        "The builder artifact now exists; prioritize the witness seat so the next move "
        "makes its dependence on that observation explicit."
    )
    delta = PolicyDelta.create(
        initial_policy,
        receipt_one,
        verifier=world,
        proposed_weights={"builder": 1, "witness": 2},
        interpretation=interpretation,
    )
    ratification = PolicyRatification.approve(
        delta,
        actor_id=operator_id,
        typed_confirmation=expected_ratification(delta.delta_id),
        reason="Fixed ratification for cycle two of the canned local fixture.",
    )
    context_two = next_cycle_context(
        context_one,
        receipt_one,
        delta,
        ratification,
        verifier=world,
        prior_run_id=identity_one.run_id,
        cycle_id="cycle-2",
    )
    _record_ratification(fence_one, delta, ratification)
    deliberation_two = _deliberate(agents, world, context_two)
    proposal_two = deliberation_two.proposal(deliberation_two.recommended_proposal_id)
    grant_two = AuthorityGrant.approve(
        deliberation_two,
        proposal_two.proposal_id,
        actor_id=operator_id,
        typed_confirmation=expected_approval(proposal_two),
        reason="Fixed preauthorization for the second canned fixture cycle.",
    )
    identity_two = _identity_for_cycle(
        context=context_two,
        proposal=proposal_two,
        correlation_id=correlation_id,
        parent_run_id=identity_one.run_id,
        causation_id=receipt_one.observation.observation_id,
    )
    fence_two = RuntimeEffectFence(
        store=store,
        identity=identity_two,
        operator_id=operator_id,
        deliberation=deliberation_two,
        grant=grant_two,
    )
    receipt_two = ShaktiSystem(agents, world, fence_two).run_cycle(
        deliberation_two,
        grant_two,
    )
    world.verify_receipt(receipt_two)

    runtime_receipts = asyncio.run(
        store.list_runtime_receipts(
            correlation_id=correlation_id,
            receipt_type="participatory_cycle",
            limit=10,
        )
    )
    causal_assertions = {
        "cycle_two_parent_is_cycle_one_run": (
            identity_two.parent_run_id == identity_one.run_id
        ),
        "cycle_two_causation_is_cycle_one_observation": (
            identity_two.causation_id == receipt_one.observation.observation_id
        ),
        "cycle_input_changed": receipt_two.input_hash != receipt_one.input_hash,
        "cycle_two_proposal_cites_cycle_one_observation": (
            proposal_two.based_on_observation_id
            == receipt_one.observation.observation_id
        ),
        "ratified_policy_changed_recommendation": (
            receipt_one.selected_agent_id != receipt_two.selected_agent_id
        ),
        "cycle_commit_markers_persisted": len(runtime_receipts) == 2,
        "required_local_artifact_rereads_completed": world.verification_count == 5,
    }
    return {
        "status": "completed_canned_local_fixture",
        "interaction_mode": "preauthorized_canned_fixture",
        "proof_mode": "local_fixture",
        "external_world_contact": False,
        "model_provider_used": False,
        "session_id": session_id,
        "correlation_id": correlation_id,
        "artifact_root": str(Path(artifact_root).resolve()),
        "runtime_db": str(Path(runtime_db).resolve()),
        "intent": intent.to_dict(),
        "cycle_one": {
            "identity": identity_one.to_dict(),
            "receipt": receipt_one.to_dict(),
        },
        "policy_delta": delta.to_dict(),
        "ratification": ratification.to_dict(),
        "cycle_two": {
            "identity": identity_two.to_dict(),
            "receipt": receipt_two.to_dict(),
        },
        "causal_assertions": causal_assertions,
        "causal_loop_proven": all(causal_assertions.values()),
        "world_effect_count": world.execution_count,
        "local_artifact_verification_count": world.verification_count,
        "claim_boundary": (
            "Proves only that fixed preauthorized inputs traverse the local two-cycle "
            "authority/evidence protocol and change the next input. It does not test "
            "live human choice or prove a cosmic sender, consciousness, or usefulness."
        ),
    }


def cmd_demo(args: argparse.Namespace) -> int:
    if args.artifact_root:
        artifact_root = Path(args.artifact_root)
    else:
        artifact_root = (
            Path(tempfile.gettempdir()) / f"shakti-system-mvp-{uuid4().hex[:12]}"
        )
    runtime_db = (
        Path(args.runtime_db)
        if args.runtime_db
        else artifact_root / "runtime.db"
    )
    report = run_demo(
        artifact_root=artifact_root,
        runtime_db=runtime_db,
        operator_id=args.operator_id,
        preauthorize_canned_demo=args.preauthorize_canned_demo,
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["status"] == "completed_canned_local_fixture" else 3


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    demo = sub.add_parser("demo", help="preview or run the bounded two-cycle fixture")
    demo.add_argument("--artifact-root", help="local fixture directory (default: temp dir)")
    demo.add_argument("--runtime-db", help="disposable RuntimeStateStore SQLite path")
    demo.add_argument("--operator-id", default="local-operator")
    demo.add_argument(
        "--preauthorize-canned-demo",
        action="store_true",
        help="preauthorize fixed grants and interpretation for the canned fixture",
    )
    demo.set_defaults(func=cmd_demo)
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
