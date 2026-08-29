"""Closed finite-JSON validators for independently signed effect canaries."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping
from typing import Any

from dharma_swarm.mission_control_effect_warrant import (
    FOUNDRY_CANARY_SCHEMA,
    CanaryPatchBinding,
)
from dharma_swarm.mission_control_verification_vibe import _signed_payload_valid

SIGNED_PROCESS_RECEIPT_SCHEMA = "dharma.governed_patch.signed_process_receipt.v1"
FOUNDRY_POSITIVE_OUTCOME = "foundry_canary_oracle_passed"
VIBE_POSITIVE_OUTCOME = "vibe_canary_clean"

_HEX64 = re.compile(r"^[0-9a-f]{64}$")
_SHA256 = re.compile(r"^sha256:[0-9a-f]{64}$")
_PROCESS_KEYS = frozenset(
    """schema role identity candidate_digest diff_sha256 outcome reasons evidence
    process key_custody repository_effect_authorized repository_effect_performed
    evidence_storage_effects_performed payload_sha256 signature""".split()
)
_IDENTITY_KEYS = frozenset(
    """trace_id correlation_id task_id run_id claim_id idempotency_key causation_id
    parent_run_id agent_id session_id external_a2a_task_id message_id event_id
    artifact_id proposal_id metadata""".split()
)
_METADATA_KEYS = frozenset(
    """authority_semantics repository_effect_performed evidence_storage_effects_performed
    repository_effect_authorized role process_boot_id signer_public_key""".split()
)
_OUTER_EVIDENCE_KEYS = frozenset(
    """native_bindings candidate_bundle_sha256 canary_binding_sha256
    nested_evidence_sha256 scanner_provenance_sha256""".split()
)
_FOUNDRY_KEYS = frozenset(
    """schema outcome binding candidate_bundle_sha256 oracle_argv_sha256 replay
    tripwires oracle_runs isolation_policy release_snapshot tool_snapshot cleanup
    promotion_allowed limitations exclusive_private_key_custody_unproven
    repository_effect_authorized repository_effect_performed""".split()
)
_REPLAY_KEYS = frozenset(
    "source_path preimage_sha256 postimage_sha256 diff_sha256 exact_patch_replayed".split()
)
_TRIPWIRE_KEYS = frozenset(
    "pre_worktree_clean pre_index_clean post_worktree_clean post_index_clean".split()
)
_RUN_KEYS = frozenset(
    "ordinal docker_image_digest argv_sha256 exit_code timed_out output_truncated stdout_sha256 stderr_sha256".split()
)
_ISOLATION_KEYS = frozenset(
    "network read_only_root no_new_privileges cap_drop_all memory_limit_bytes pids_limit cpu_limit_millis".split()
)
_SNAPSHOT_KEYS = frozenset("before_sha256 after_sha256".split())
_CLEANUP_KEYS = frozenset(
    "scratch_worktree_clean containers_removed temporary_files_removed".split()
)
_LIMITATIONS = [
    "canary_scope_only",
    "exclusive_private_key_custody_unproven",
    "same_uid_process_isolation_unproven",
]


def snapshot_mapping(value: Any) -> dict[str, Any] | None:
    """Snapshot once and reject aliases, non-finite numbers, and non-JSON values."""

    if not isinstance(value, Mapping):
        return None
    try:
        copied = dict(value)
        encoded = json.dumps(
            copied, sort_keys=True, separators=(",", ":"), allow_nan=False,
        )
        decoded = json.loads(encoded)
        return decoded if isinstance(decoded, dict) and decoded == copied else None
    except Exception:
        return None


def finite_sha256(value: Any) -> str:
    encoded = json.dumps(
        value, sort_keys=True, separators=(",", ":"), allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _exact_dict(value: Any, keys: frozenset[str]) -> dict[str, Any] | None:
    return value if isinstance(value, dict) and frozenset(value) == keys else None


def _hex64(value: Any) -> bool:
    return type(value) is str and _HEX64.fullmatch(value) is not None


def _positive_int(value: Any) -> bool:
    return type(value) is int and value > 0


def native_binding(binding: CanaryPatchBinding) -> dict[str, str]:
    return {
        "mission_id": binding.mission_id, "task_id": binding.task_id,
        "attempt_id": binding.packet_id, "lease_id": binding.delivery_id,
        "packet_id": binding.packet_id, "correlation_id": binding.correlation_id,
        "delivery_id": binding.delivery_id, "proposal_id": binding.proposal_id,
        "base_sha": binding.base_sha,
        "executor_agent_uid": binding.executor_agent_uid,
        "executor_run_id": binding.executor_run_id,
        "executor_process_boot_id": binding.executor_process_boot_id,
    }


def valid_foundry_evidence(data: dict[str, Any], binding: CanaryPatchBinding) -> bool:
    replay = _exact_dict(data.get("replay"), _REPLAY_KEYS)
    tripwires = _exact_dict(data.get("tripwires"), _TRIPWIRE_KEYS)
    isolation = _exact_dict(data.get("isolation_policy"), _ISOLATION_KEYS)
    release = _exact_dict(data.get("release_snapshot"), _SNAPSHOT_KEYS)
    tools = _exact_dict(data.get("tool_snapshot"), _SNAPSHOT_KEYS)
    cleanup = _exact_dict(data.get("cleanup"), _CLEANUP_KEYS)
    runs = data.get("oracle_runs")
    if not (
        frozenset(data) == _FOUNDRY_KEYS
        and data.get("schema") == FOUNDRY_CANARY_SCHEMA
        and data.get("outcome") == FOUNDRY_POSITIVE_OUTCOME
        and data.get("binding") == binding.to_dict()
        and data.get("candidate_bundle_sha256") == binding.candidate_bundle_sha256
        and data.get("oracle_argv_sha256") == binding.oracle_argv_sha256
        and replay == {
            "source_path": binding.scratch.source_path,
            "preimage_sha256": binding.scratch.preimage_sha256,
            "postimage_sha256": binding.scratch.postimage_sha256,
            "diff_sha256": binding.diff_sha256, "exact_patch_replayed": True,
        }
        and replay.get("exact_patch_replayed") is True
        and tripwires is not None and all(value is True for value in tripwires.values())
        and isolation is not None
        and isolation.get("network") == "none"
        and isolation.get("read_only_root") is True
        and isolation.get("no_new_privileges") is True
        and isolation.get("cap_drop_all") is True
        and all(_positive_int(isolation.get(name)) for name in (
            "memory_limit_bytes", "pids_limit", "cpu_limit_millis",
        ))
        and isinstance(runs, list) and len(runs) == 2
        and all(_exact_dict(run, _RUN_KEYS) is not None for run in runs)
        and [run["ordinal"] for run in runs] == [1, 2]
        and all(type(run["ordinal"]) is int for run in runs)
        and all(
            type(run["docker_image_digest"]) is str
            and _SHA256.fullmatch(run["docker_image_digest"]) is not None
            and run["argv_sha256"] == binding.oracle_argv_sha256
            and run["exit_code"] == 0 and type(run["exit_code"]) is int
            and run["timed_out"] is False and run["output_truncated"] is False
            and _hex64(run["stdout_sha256"]) and _hex64(run["stderr_sha256"])
            for run in runs
        )
        and all(runs[0][name] == runs[1][name] for name in (
            "docker_image_digest", "argv_sha256", "exit_code",
            "stdout_sha256", "stderr_sha256",
        ))
        and release is not None and tools is not None
        and all(_hex64(value) for value in (*release.values(), *tools.values()))
        and release["before_sha256"] == release["after_sha256"]
        and tools["before_sha256"] == tools["after_sha256"]
        and cleanup is not None and all(value is True for value in cleanup.values())
        and data.get("promotion_allowed") is False
        and data.get("limitations") == _LIMITATIONS
        and data.get("exclusive_private_key_custody_unproven") is True
        and data.get("repository_effect_authorized") is False
        and data.get("repository_effect_performed") is False
    ):
        return False
    return True


def valid_process_receipt(
    data: dict[str, Any], *, binding: CanaryPatchBinding, role: str,
    outcome: str, public_key: str, nested_digest: str,
) -> bool:
    identity = _exact_dict(data.get("identity"), _IDENTITY_KEYS)
    process = _exact_dict(data.get("process"), frozenset({"pid", "boot_id"}))
    custody = _exact_dict(data.get("key_custody"), frozenset({
        "owner_only_regular_file", "key_device", "key_inode",
        "exclusive_private_key_custody_proven",
    }))
    evidence = _exact_dict(data.get("evidence"), _OUTER_EVIDENCE_KEYS)
    verifier = binding.foundry_verifier if role == "foundry" else binding.vibe_verifier
    metadata = _exact_dict(identity.get("metadata") if identity else None, _METADATA_KEYS)
    reasons = data.get("reasons")
    expected_identity = {
        "trace_id": f"trace:{verifier.run_id}",
        "correlation_id": binding.correlation_id, "task_id": binding.task_id,
        "run_id": verifier.run_id, "claim_id": f"claim:{verifier.run_id}",
        "idempotency_key": (
            f"idem:governed_patch:{role}:{binding.proposal_id}:"
            f"{binding.candidate_digest}"
        ),
        "causation_id": binding.candidate_digest,
        "parent_run_id": binding.executor_run_id, "agent_id": verifier.agent_uid,
        "session_id": f"mission:{binding.mission_id}",
        "external_a2a_task_id": "", "message_id": "", "event_id": "",
        "artifact_id": binding.candidate_digest, "proposal_id": binding.proposal_id,
        "metadata": metadata,
    }
    expected_metadata = {
        "authority_semantics": "evidence_only",
        "repository_effect_performed": False,
        "evidence_storage_effects_performed": True,
        "repository_effect_authorized": False, "role": role,
        "process_boot_id": process.get("boot_id") if process else None,
        "signer_public_key": public_key,
    }
    return bool(
        frozenset(data) == _PROCESS_KEYS
        and data.get("schema") == SIGNED_PROCESS_RECEIPT_SCHEMA
        and data.get("role") == role and data.get("outcome") == outcome
        and data.get("candidate_digest") == binding.candidate_digest
        and data.get("diff_sha256") == binding.diff_sha256
        and data.get("repository_effect_authorized") is False
        and data.get("repository_effect_performed") is False
        and data.get("evidence_storage_effects_performed") is True
        and reasons == [] and identity == expected_identity
        and metadata == expected_metadata
        and process is not None and _positive_int(process.get("pid"))
        and type(process.get("boot_id")) is str and bool(process["boot_id"])
        and custody is not None
        and custody.get("owner_only_regular_file") is True
        and _positive_int(custody.get("key_device"))
        and _positive_int(custody.get("key_inode"))
        and custody.get("exclusive_private_key_custody_proven") is False
        and evidence == {
            "native_bindings": native_binding(binding),
            "candidate_bundle_sha256": binding.candidate_bundle_sha256,
            "canary_binding_sha256": binding.binding_sha256,
            "nested_evidence_sha256": nested_digest,
            "scanner_provenance_sha256": evidence.get("scanner_provenance_sha256")
            if evidence else None,
        }
        and _hex64(evidence.get("scanner_provenance_sha256") if evidence else None)
        and isinstance(data.get("signature"), dict)
        and data["signature"].get("public_key") == public_key
        and data["signature"].get("key_id") == f"governed-patch-{role}"
        and _signed_payload_valid(data, signature_field="signature")
    )


def process_observation(data: dict[str, Any]) -> tuple[int, str, str, int, int]:
    return (
        data["process"]["pid"], data["process"]["boot_id"],
        data["signature"]["public_key"], data["key_custody"]["key_device"],
        data["key_custody"]["key_inode"],
    )


__all__ = [
    "FOUNDRY_POSITIVE_OUTCOME", "SIGNED_PROCESS_RECEIPT_SCHEMA",
    "VIBE_POSITIVE_OUTCOME", "finite_sha256", "native_binding",
    "process_observation", "snapshot_mapping", "valid_foundry_evidence",
    "valid_process_receipt",
]
