"""Strict signed canary verification for one exact governed patch effect."""

from __future__ import annotations

import os
from collections.abc import Mapping
from typing import Any

from dharma_swarm.forge_v1.forge_v2.signals import canonical_sha256
from dharma_swarm.governed_patch_candidate_bundle import (
    CandidateBundle,
    verify_candidate_bundle,
)
from dharma_swarm.mission_control_a2a_candidate import (
    ExactProposalStoreExpectation,
    ExactProposalStoreObservation,
    require_store_expectation,
)
from dharma_swarm.mission_control_effect_records import EffectRefusal
from dharma_swarm.mission_control_effect_evidence import (
    FOUNDRY_POSITIVE_OUTCOME,
    SIGNED_PROCESS_RECEIPT_SCHEMA,
    VIBE_POSITIVE_OUTCOME,
    finite_sha256,
    process_observation,
    snapshot_mapping,
    valid_foundry_evidence,
    valid_process_receipt,
)
from dharma_swarm.mission_control_effect_warrant import (
    CanaryPatchBinding,
    CanaryVerifierBinding,
    IndependentPatchVerification,
    ScratchTargetBinding,
    effect_key_for,
    scratch_identity_for,
)
from dharma_swarm.mission_control_verification import PATCH_VIBE_SCHEMA
from dharma_swarm.mission_control_verification_vibe import _signed_payload_valid

FOUNDRY_PROCESS_ROLE = "foundry"
VIBE_PROCESS_ROLE = "vibe_halt"
_VIBE_KEYS = frozenset(
    """schema candidate_digest diff_sha256 verifier ran reported_outcome
    diff_bound calibration_only process findings errors blockers payload_sha256
    signature""".split()
)


def _mapping(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, Mapping):
        return None
    try:
        return dict(value)
    except Exception:
        return None


def _principal(receipt: dict[str, Any]) -> str:
    signature = _mapping(receipt.get("signature")) or {}
    return str(signature.get("public_key") or "")


def build_canary_patch_binding(
    expected: ExactProposalStoreExpectation,
    observation: ExactProposalStoreObservation,
    candidate: CandidateBundle,
    scratch: ScratchTargetBinding,
    *,
    foundry_verifier: CanaryVerifierBinding,
    vibe_verifier: CanaryVerifierBinding,
) -> CanaryPatchBinding:
    """Join exact RUNNING owner evidence to immutable bytes and scratch custody."""

    require_store_expectation(expected)
    if (
        type(observation) is not ExactProposalStoreObservation
        or observation._seal is None  # noqa: SLF001 - nominal owner evidence
        or type(scratch) is not ScratchTargetBinding
        or type(foundry_verifier) is not CanaryVerifierBinding
        or type(vibe_verifier) is not CanaryVerifierBinding
    ):
        raise ValueError("exact owner, scratch, and verifier bindings are required")
    candidate = verify_candidate_bundle(candidate)
    ref = expected.native_ref
    native = candidate.bindings
    expected_native = (
        ref.mission_id, ref.task_id, ref.packet_id, ref.delivery_id, ref.packet_id,
        ref.correlation_id, ref.delivery_id, ref.proposal_id, expected.base_sha,
        ref.agent_uid, expected.executor_run_id, expected.executor_process_boot_id,
    )
    actual_native = tuple(
        getattr(native, name) for name in (
            "mission_id", "task_id", "attempt_id", "lease_id", "packet_id",
            "correlation_id", "delivery_id", "proposal_id", "base_sha",
            "executor_agent_uid", "executor_run_id", "executor_process_boot_id",
        )
    )
    if actual_native != expected_native:
        raise ValueError("candidate native binding mismatch")
    if (
        observation.native_ref != ref
        or observation.executor_run_id != expected.executor_run_id
        or observation.executor_process_boot_id != expected.executor_process_boot_id
        or candidate.candidate_digest != expected.candidate_digest
        or candidate.diff_sha256 != expected.diff_sha256
        or expected.authorized_source_files != (candidate.authorized_source_path,)
        or scratch.base_sha != expected.base_sha
        or scratch.source_path != candidate.authorized_source_path
        or scratch.preimage_sha256 != candidate.source_sha256
        or scratch_identity_for(scratch) != scratch.scratch_identity
    ):
        raise ValueError("candidate, owner, or scratch binding mismatch")
    principals = (
        foundry_verifier.agent_uid, foundry_verifier.run_id,
        foundry_verifier.signer_public_key, vibe_verifier.agent_uid,
        vibe_verifier.run_id, vibe_verifier.signer_public_key,
    )
    if (
        foundry_verifier.role != "foundry_canary"
        or vibe_verifier.role != "vibe_canary"
        or any(type(value) is not str or not value for value in principals)
        or len({foundry_verifier.agent_uid, vibe_verifier.agent_uid, ref.agent_uid}) != 3
        or len({foundry_verifier.run_id, vibe_verifier.run_id, expected.executor_run_id}) != 3
        or len({foundry_verifier.signer_public_key, vibe_verifier.signer_public_key}) != 2
    ):
        raise ValueError("canary verifier principals are not independent")
    effect_key = effect_key_for(
        mission_attempt_id=observation.mission_attempt_id,
        mission_claim_id=observation.mission_claim_id,
        proposal_id=ref.proposal_id,
        candidate_bundle_sha256=candidate.bundle_sha256,
        scratch_identity=scratch.scratch_identity,
    )
    return CanaryPatchBinding(
        mission_id=ref.mission_id, task_id=ref.task_id,
        mission_attempt_id=observation.mission_attempt_id,
        mission_claim_id=observation.mission_claim_id, packet_id=ref.packet_id,
        correlation_id=ref.correlation_id, delivery_id=ref.delivery_id,
        proposal_id=ref.proposal_id, a2a_content_sha256=ref.content_sha256,
        attempt_key=expected.attempt_key, operator_id=expected.operator_id,
        assigned_by=expected.assigned_by,
        candidate_digest=expected.candidate_digest,
        diff_sha256=expected.diff_sha256, base_sha=expected.base_sha,
        artifact_sha256=expected.artifact_sha256,
        candidate_bundle_sha256=candidate.bundle_sha256,
        authorized_source_files=expected.authorized_source_files,
        executor_agent_uid=ref.agent_uid,
        executor_run_id=expected.executor_run_id,
        executor_process_boot_id=expected.executor_process_boot_id,
        proposal_receipt_id=observation.proposal_receipt_id,
        proposal_receipt_sha256=observation.proposal_receipt_sha256,
        oracle_argv_sha256=canonical_sha256(list(candidate.oracle_argv)),
        effect_key=effect_key, scratch=scratch,
        foundry_verifier=foundry_verifier, vibe_verifier=vibe_verifier,
    )


def _native_binding_from_candidate(candidate: CandidateBundle) -> dict[str, str]:
    return candidate.bindings.to_dict()


class IndependentPatchVerifier:
    """Pinned trust roots which can mint only a non-authorizing canary proof."""

    def __init__(
        self,
        *,
        trusted_foundry_public_keys: frozenset[str],
        trusted_vibe_public_keys: frozenset[str],
    ) -> None:
        roots = (*trusted_foundry_public_keys, *trusted_vibe_public_keys)
        if (
            type(trusted_foundry_public_keys) is not frozenset
            or type(trusted_vibe_public_keys) is not frozenset
            or not trusted_foundry_public_keys or not trusted_vibe_public_keys
            or not trusted_foundry_public_keys.isdisjoint(trusted_vibe_public_keys)
            or any(
                type(value) is not str or len(value) != 64
                or value != value.lower()
                or any(char not in "0123456789abcdef" for char in value)
                for value in roots
            )
        ):
            raise ValueError("nonempty disjoint exact Ed25519 trust roots are required")
        self._foundry = trusted_foundry_public_keys
        self._vibe = trusted_vibe_public_keys
        self._creator_pid = os.getpid()
        self._sentinel = object()
        self._issued: dict[int, tuple[IndependentPatchVerification, str]] = {}

    def validates(self, value: IndependentPatchVerification) -> bool:
        entry = self._issued.get(id(value))
        return bool(
            os.getpid() == self._creator_pid
            and type(value) is IndependentPatchVerification
            and value._seal is self._sentinel  # noqa: SLF001
            and entry is not None and entry[0] is value
            and entry[1] == canonical_sha256(value.to_dict())
        )
    def evaluate(
        self,
        binding: CanaryPatchBinding,
        *,
        foundry_process_receipt: Mapping[str, Any],
        foundry_canary_evidence: Mapping[str, Any],
        vibe_process_receipt: Mapping[str, Any],
        vibe_patch_receipt: Mapping[str, Any],
    ) -> IndependentPatchVerification | EffectRefusal:
        if os.getpid() != self._creator_pid:
            return EffectRefusal(("canary_verifier_process_inherited",))
        blockers: list[str] = []
        foundry_process = snapshot_mapping(foundry_process_receipt)
        foundry = snapshot_mapping(foundry_canary_evidence)
        vibe_process = snapshot_mapping(vibe_process_receipt)
        vibe = snapshot_mapping(vibe_patch_receipt)
        foundry_digest = finite_sha256(foundry or {})
        vibe_digest = finite_sha256(vibe or {})
        if foundry is None or not valid_foundry_evidence(foundry, binding):
            blockers.append("foundry_canary_evidence_not_positive_or_exact")
        foundry_process_valid = (
            binding.foundry_verifier.signer_public_key in self._foundry
            and foundry_process is not None
            and valid_process_receipt(
                foundry_process, binding=binding,
                role=FOUNDRY_PROCESS_ROLE, outcome=FOUNDRY_POSITIVE_OUTCOME,
                public_key=binding.foundry_verifier.signer_public_key,
                nested_digest=foundry_digest,
            )
        )
        if not foundry_process_valid:
            blockers.append("foundry_process_receipt_untrusted_or_inexact")
        if not self._valid_vibe(vibe, binding=binding):
            blockers.append("vibe_patch_receipt_not_clean_or_exact")
        vibe_process_valid = (
            binding.vibe_verifier.signer_public_key in self._vibe
            and vibe_process is not None
            and valid_process_receipt(
                vibe_process, binding=binding, role=VIBE_PROCESS_ROLE,
                outcome=VIBE_POSITIVE_OUTCOME,
                public_key=binding.vibe_verifier.signer_public_key,
                nested_digest=vibe_digest,
            )
        )
        if not vibe_process_valid:
            blockers.append("vibe_process_receipt_untrusted_or_inexact")
        if foundry_process_valid and vibe_process_valid:
            assert foundry_process is not None and vibe_process is not None
            foundry_observed = process_observation(foundry_process)
            vibe_observed = process_observation(vibe_process)
            if (
                any(foundry_observed[index] == vibe_observed[index]
                    for index in range(3))
                or foundry_observed[3:] == vibe_observed[3:]
                or foundry_observed[1] == binding.executor_process_boot_id
                or vibe_observed[1] == binding.executor_process_boot_id
            ):
                blockers.append("canary_process_or_key_custody_not_separated")
        if blockers:
            return EffectRefusal(tuple(blockers))
        result = IndependentPatchVerification(
            binding=binding,
            foundry_canary_evidence_sha256=foundry_digest,
            foundry_process_receipt_sha256=finite_sha256(foundry_process),
            vibe_process_receipt_sha256=finite_sha256(vibe_process),
            vibe_patch_receipt_sha256=vibe_digest,
        )
        object.__setattr__(result, "_seal", self._sentinel)
        self._issued[id(result)] = (result, canonical_sha256(result.to_dict()))
        return result

    def _valid_vibe(
        self, receipt: dict[str, Any] | None, *, binding: CanaryPatchBinding,
    ) -> bool:
        if receipt is None or frozenset(receipt) != _VIBE_KEYS:
            return False
        verifier = _mapping(receipt.get("verifier"))
        process = _mapping(receipt.get("process"))
        return bool(
            receipt.get("schema") == PATCH_VIBE_SCHEMA
            and receipt.get("candidate_digest") == binding.candidate_digest
            and receipt.get("diff_sha256") == binding.diff_sha256
            and verifier == {
                "agent_uid": binding.vibe_verifier.agent_uid,
                "run_id": binding.vibe_verifier.run_id,
                "parent_run_id": binding.executor_run_id,
            }
            and receipt.get("ran") is True
            and receipt.get("reported_outcome") == "clean"
            and receipt.get("diff_bound") is True
            and receipt.get("calibration_only") is False
            and process == {"exit_code": 0, "timed_out": False, "output_limited": False}
            and receipt.get("findings") == [] and receipt.get("errors") == []
            and receipt.get("blockers") == []
            and _principal(receipt) == binding.vibe_verifier.signer_public_key
            and _signed_payload_valid(receipt, signature_field="signature")
        )


__all__ = [
    "FOUNDRY_POSITIVE_OUTCOME", "IndependentPatchVerifier",
    "SIGNED_PROCESS_RECEIPT_SCHEMA",
    "VIBE_POSITIVE_OUTCOME",
    "build_canary_patch_binding",
]
