"""Exact matching and evidence digests for recovery owner modalities."""

from __future__ import annotations

from dharma_swarm.forge_v1.forge_v2.signals import canonical_sha256
from dharma_swarm.mission_control_a2a_candidate import (
    ExactProposalStoreExpectation,
    ExactProposalStoreObservation,
)
from dharma_swarm.mission_control_contract import MissionControlError
from dharma_swarm.mission_control_effect_owner_recovery import (
    ExpiredProposalRecoveryObservation,
)
from dharma_swarm.mission_control_effect_warrant import (
    CanaryPatchBinding,
    EffectBinding,
)


def expired_recovery_matches(
    binding: EffectBinding,
    expected: ExactProposalStoreExpectation,
    observed: ExpiredProposalRecoveryObservation,
) -> bool:
    ref = expected.native_ref
    canary = binding.canary
    return bool(
        type(observed) is ExpiredProposalRecoveryObservation
        and (
            canary.mission_id, canary.task_id, canary.packet_id,
            canary.correlation_id, canary.delivery_id, canary.proposal_id,
            canary.a2a_content_sha256,
        )
        == (
            ref.mission_id, ref.task_id, ref.packet_id, ref.correlation_id,
            ref.delivery_id, ref.proposal_id, ref.content_sha256,
        )
        and (
            canary.attempt_key, canary.operator_id, canary.assigned_by,
            canary.candidate_digest, canary.diff_sha256, canary.base_sha,
            canary.artifact_sha256, canary.authorized_source_files,
        )
        == (
            expected.attempt_key, expected.operator_id, expected.assigned_by,
            expected.candidate_digest, expected.diff_sha256, expected.base_sha,
            expected.artifact_sha256, expected.authorized_source_files,
        )
        and (
            canary.mission_attempt_id, canary.mission_claim_id,
            canary.executor_agent_uid, canary.executor_run_id,
            canary.executor_process_boot_id, canary.proposal_receipt_id,
            canary.proposal_receipt_sha256,
        )
        == (
            observed.mission_attempt_id, observed.mission_claim_id,
            ref.agent_uid, observed.executor_run_id,
            observed.executor_process_boot_id, observed.proposal_receipt_id,
            observed.proposal_receipt_sha256,
        )
        and (observed.mission_id, observed.task_id, observed.proposal_id)
        == (canary.mission_id, canary.task_id, canary.proposal_id)
        and (
            (
                observed.owner_transition == "expired_active"
                and observed.owner_reconciliation == "expired_lease"
                and not observed.transition_receipt_id
                and not observed.transition_receipt_sha256
                and not observed.successor_attempt_ids
            )
            or (
                observed.owner_transition == "canonical_stale_recovery"
                and observed.owner_reconciliation
                in {"coherent", "needs_task_projection"}
                and bool(observed.transition_receipt_id)
                and len(observed.transition_receipt_sha256) == 64
            )
            or (
                observed.owner_transition == "canonical_terminal"
                and observed.owner_reconciliation
                in {"coherent", "needs_task_projection"}
                and bool(observed.transition_receipt_id)
                and len(observed.transition_receipt_sha256) == 64
                and not observed.successor_attempt_ids
            )
        )
    )


def live_owner_matches(
    binding: CanaryPatchBinding,
    expected: ExactProposalStoreExpectation,
    observed: ExactProposalStoreObservation,
) -> bool:
    ref = expected.native_ref
    lifecycle = {
        binding.mission_attempt_id, binding.mission_claim_id,
        binding.packet_id, binding.delivery_id,
    }
    return bool(
        type(observed) is ExactProposalStoreObservation
        and len(lifecycle) == 4
        and (
            binding.mission_id, binding.task_id, binding.packet_id,
            binding.correlation_id, binding.delivery_id, binding.proposal_id,
        )
        == (
            ref.mission_id, ref.task_id, ref.packet_id, ref.correlation_id,
            ref.delivery_id, ref.proposal_id,
        )
        and binding.a2a_content_sha256 == ref.content_sha256
        and (binding.attempt_key, binding.operator_id, binding.assigned_by)
        == (expected.attempt_key, expected.operator_id, expected.assigned_by)
        and (
            binding.candidate_digest, binding.diff_sha256, binding.base_sha,
            binding.artifact_sha256, binding.authorized_source_files,
        )
        == (
            expected.candidate_digest, expected.diff_sha256, expected.base_sha,
            expected.artifact_sha256, expected.authorized_source_files,
        )
        and (
            binding.executor_agent_uid, binding.executor_run_id,
            binding.executor_process_boot_id,
        )
        == (ref.agent_uid, expected.executor_run_id, expected.executor_process_boot_id)
        and (
            binding.mission_attempt_id, binding.mission_claim_id,
            binding.proposal_receipt_id, binding.proposal_receipt_sha256,
        )
        == (
            observed.mission_attempt_id, observed.mission_claim_id,
            observed.proposal_receipt_id, observed.proposal_receipt_sha256,
        )
    )


def recovery_owner_evidence(
    observed: ExactProposalStoreObservation | ExpiredProposalRecoveryObservation,
) -> tuple[str, str]:
    if type(observed) is ExactProposalStoreObservation:
        basis = "live_owner"
    elif type(observed) is ExpiredProposalRecoveryObservation:
        basis = observed.owner_transition
    else:
        raise MissionControlError("exact recovery owner observation is required")
    return basis, canonical_sha256(observed.to_dict())


__all__ = [
    "expired_recovery_matches", "live_owner_matches", "recovery_owner_evidence",
]
