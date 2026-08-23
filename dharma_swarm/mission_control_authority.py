"""Exact file-backed authority adapters for governed campaign dispatch."""

from __future__ import annotations

import json
import re
from collections.abc import Iterator, Mapping
from pathlib import Path
from typing import Any

from dharma_swarm.mission_control_contract import (
    SCHEMA_VERSION,
    MissionControlError,
    TaskView,
    clean_identifier,
    task_view,
)
from dharma_swarm.mission_control_dispatch import (
    CAMPAIGN_LEASE_SCHEMA_VERSION,
    GOVERNANCE_METADATA_KEY,
    LEASE_DISPATCH_ACTION,
    LEASE_WORKSPACE_ACTION,
    DispatchAuthorityEnvelope,
    GovernanceAdmission,
    GovernedMissionDispatcher,
    MissionDispatchRequest,
    VerifiedDispatchAuthority,
)
from dharma_swarm.mission_control_execution import OwnerExecutionRef
from dharma_swarm.mission_control_observed_input import (
    OBSERVED_INPUT_REF_KEY,
    render_bound_observed_input_prompt,
)
from dharma_swarm.operator_core.execution_lease import (
    ExecutionLeaseError,
    content_hash,
    lease_path,
    load_execution_lease,
    revocations_path,
    safe_lease_id,
    validate_execution_lease,
)
from dharma_swarm.task_board import TaskBoard

CAMPAIGN_AUTHORITY_METADATA_KEY = "mission_campaign_authority"
CAMPAIGN_AUTHORITY_SCHEMA_VERSION = "dharma.sadhana.campaign_task_authority.v4"
SADHANA_BOOTSTRAP_SCHEMA_VERSION = "dharma.sadhana.mission_bootstrap.v1"
SADHANA_GOAL_CONTRACT_SCHEMA_VERSION = "dharma.sadhana.goal_contracts.v1"
_SHA256_RE = re.compile(r"sha256:[0-9a-f]{64}")
_RAW_SHA256_RE = re.compile(r"[0-9a-f]{64}")


def _authority_identifier(
    authority: Mapping[str, Any],
    key: str,
    *,
    default: str = "",
) -> str:
    raw = authority.get(key, default)
    if not isinstance(raw, str):
        raise MissionControlError(f"campaign authority {key} must be a string")
    cleaned = clean_identifier(raw, key)
    if cleaned != raw:
        raise MissionControlError(f"campaign authority {key} must be canonical")
    return cleaned


def _load_exact_lease(root: Path, lease_id: str) -> dict[str, Any]:
    if safe_lease_id(lease_id) != lease_id:
        raise ExecutionLeaseError("execution lease_id is not canonical")
    path = lease_path(root, lease_id)
    if path.is_symlink() or path.resolve(strict=False).parent != root:
        raise ExecutionLeaseError("execution lease path is not an exact root child")
    return load_execution_lease(root, lease_id)


def load_campaign_revocations_strict(root: Path) -> set[str]:
    """Load campaign lease revocations without skipping malformed evidence."""
    path = revocations_path(root)
    if not path.exists():
        return set()
    if path.is_symlink() or path.resolve(strict=False).parent != root:
        raise ExecutionLeaseError("revocation path is not an exact root child")
    revoked: set[str] = set()
    for line_number, line in enumerate(
        path.read_text(encoding="utf-8").splitlines(),
        start=1,
    ):
        if not line.strip():
            raise ExecutionLeaseError(
                f"revocation record {line_number} is empty"
            )
        payload = json.loads(line)
        if not isinstance(payload, dict) or payload.get("event") != "lease_revoked":
            raise ExecutionLeaseError(
                f"revocation record {line_number} has a foreign shape"
            )
        lease_id = payload.get("lease_id")
        if not isinstance(lease_id, str) or safe_lease_id(lease_id) != lease_id:
            raise ExecutionLeaseError(
                f"revocation record {line_number} has an invalid lease_id"
            )
        revoked.add(lease_id)
    return revoked


class _ExactFileExecutionLease(Mapping[str, Any]):
    """A mapping that rechecks the exact file and revocations on every read.

    ``GovernedMissionDispatcher`` validates its authority again immediately
    before invoking the executor.  Keeping that authority file-backed makes
    the final validation observe a lease mutation or revocation that happened
    after the verifier first returned.
    """

    def __init__(self, root: Path, lease_id: str, digest: str) -> None:
        self._root = root
        self._lease_id = lease_id
        self._digest = digest

    def _load(self) -> dict[str, Any]:
        try:
            lease = _load_exact_lease(self._root, self._lease_id)
            revoked = load_campaign_revocations_strict(self._root)
        except (ExecutionLeaseError, OSError, ValueError, json.JSONDecodeError) as exc:
            raise MissionControlError("execution authority could not be refreshed") from exc
        if self._lease_id in revoked:
            raise MissionControlError("execution authority was revoked before effect")
        if lease.get("content_hash") != self._digest or content_hash(lease) != self._digest:
            raise MissionControlError("execution authority changed before effect")
        return lease

    def __getitem__(self, key: str) -> Any:
        return self._load()[key]

    def __iter__(self) -> Iterator[str]:
        return iter(tuple(self._load()))

    def __len__(self) -> int:
        return len(self._load())


class FileExecutionLeaseAuthorityVerifier:
    """Re-read one exact lease and revocation file for every authorization."""

    def __init__(self, lease_root: Path | str, board: TaskBoard) -> None:
        if board is None:
            raise ValueError("campaign authority verifier requires the canonical TaskBoard")
        self._lease_root = Path(lease_root).expanduser().resolve(strict=False)
        self._board = board

    async def verify(
        self,
        envelope: DispatchAuthorityEnvelope,
        *,
        request: MissionDispatchRequest,
        admission: GovernanceAdmission,
    ) -> VerifiedDispatchAuthority:
        del admission
        expected = (
            request.claimed_principal,
            request.mission_id,
            request.task_id,
            request.dispatch_key,
            request.attempt_generation,
        )
        observed = (
            envelope.claimed_principal,
            envelope.mission_id,
            envelope.task_id,
            envelope.dispatch_key,
            envelope.attempt_generation,
        )
        if observed != expected:
            raise MissionControlError("authority envelope names a foreign dispatch")
        task = await self._board.get(request.task_id)
        if task is None or task.metadata.get("mission_id") != request.mission_id:
            raise MissionControlError("campaign task is missing before authority verification")
        authority = task.metadata.get(CAMPAIGN_AUTHORITY_METADATA_KEY)
        if not isinstance(authority, dict):
            raise MissionControlError("campaign task has no typed authority")
        GovernedCampaignTaskDispatcher._require_typed_authority(
            task_view(task, request.mission_id), authority
        )
        try:
            lease = _load_exact_lease(self._lease_root, envelope.authority_ref)
            revoked = load_campaign_revocations_strict(self._lease_root)
        except (ExecutionLeaseError, OSError, ValueError, json.JSONDecodeError) as exc:
            raise MissionControlError("execution authority could not be loaded") from exc
        digest = content_hash(lease)
        if lease.get("content_hash") != digest or digest != envelope.authority_digest:
            raise MissionControlError("execution authority digest does not match exact file")
        if lease.get("campaign_authority_schema") != CAMPAIGN_LEASE_SCHEMA_VERSION:
            raise MissionControlError("execution authority is not a campaign lease")
        if lease.get("effect_mode") != "read_only":
            raise MissionControlError(
                "write-capable execution authority has no enforced workspace sandbox"
            )
        if lease.get("allowed_actions") != [
            LEASE_DISPATCH_ACTION,
            LEASE_WORKSPACE_ACTION,
        ]:
            raise MissionControlError("execution authority actions are not exact")
        budget = lease.get("budget")
        if (
            not isinstance(budget, Mapping)
            or isinstance(budget.get("max_usd"), bool)
            or budget.get("max_usd") != 0
        ):
            raise MissionControlError("execution authority is not zero-dollar")
        validation = validate_execution_lease(
            lease,
            agent_uid=request.claimed_principal,
            task_id=request.task_id,
            requested_actions=[LEASE_DISPATCH_ACTION, LEASE_WORKSPACE_ACTION],
            revoked_lease_ids=revoked,
        )
        if not validation.valid:
            raise MissionControlError(
                "execution authority is invalid: " + "; ".join(validation.errors)
            )
        if lease.get("correlation_id") != request.request_id:
            raise MissionControlError("execution authority correlation is foreign")
        if lease.get("attempt_generation") != request.attempt_generation:
            raise MissionControlError("execution authority attempt generation is foreign")
        lineage = {
            "lease_id": authority.get("authority_ref"),
            "content_hash": authority.get("authority_digest"),
            "issued_to": authority.get("claimed_principal"),
            "task_id": request.task_id,
            "correlation_id": authority.get("request_id"),
            "campaign_authority_schema": CAMPAIGN_LEASE_SCHEMA_VERSION,
            "campaign_id": authority.get("campaign_id"),
            "mission_id": authority.get("mission_id"),
            "goal_id": authority.get("goal_id"),
            "portfolio_contract_sha256": authority.get("portfolio_contract_sha256"),
            "goal_contract_sha256": authority.get("goal_contract_sha256"),
            "manifest_digest": authority.get("manifest_digest"),
            "observed_input_manifest_digest": authority.get(
                "observed_input_manifest_digest"
            ),
            "held_out_oracle_manifest_digest": authority.get(
                "held_out_oracle_manifest_digest"
            ),
            "operator_control_semantics_sha256": authority.get(
                "operator_control_semantics_sha256"
            ),
            "operator_control_authority_binding_sha256": authority.get(
                "operator_control_authority_binding_sha256"
            ),
            "deployment_authority_topology_sha256": authority.get(
                "deployment_authority_topology_sha256"
            ),
            "deployment_authority_credential_clarification_sha256": authority.get(
                "deployment_authority_credential_clarification_sha256"
            ),
            OBSERVED_INPUT_REF_KEY: authority.get(OBSERVED_INPUT_REF_KEY),
            "agent_roster_sha256": authority.get("agent_roster_sha256"),
            "effect_mode": authority.get("effect_mode"),
            "campaign_end": authority.get("campaign_end"),
            "expires_at": authority.get("campaign_end"),
            "agent_name": authority.get("agent_name"),
            "workspace_path": authority.get("workspace_path"),
            "attempt_generation": authority.get("attempt_generation"),
            "max_attempts": authority.get("max_attempts"),
            "allowed_actions": [LEASE_DISPATCH_ACTION, LEASE_WORKSPACE_ACTION],
            "allowed_paths": authority.get("allowed_files"),
        }
        for key, value in lineage.items():
            if lease.get(key) != value:
                raise MissionControlError(f"execution authority lineage conflicts: {key}")
        return VerifiedDispatchAuthority(
            authenticated_principal=request.claimed_principal,
            mission_id=request.mission_id,
            task_id=request.task_id,
            dispatch_key=request.dispatch_key,
            authority_ref=envelope.authority_ref,
            authority_digest=envelope.authority_digest,
            execution_lease=_ExactFileExecutionLease(
                self._lease_root,
                envelope.authority_ref,
                envelope.authority_digest,
            ),
            revoked_lease_ids=tuple(sorted(revoked)),
            attempt_generation=request.attempt_generation,
        )


class GovernedCampaignTaskDispatcher:
    """Drive the complete P2 admission/authority ladder for one TaskView."""

    def __init__(
        self,
        dispatcher: GovernedMissionDispatcher,
        board: TaskBoard,
    ) -> None:
        self._dispatcher = dispatcher
        self._board = board

    async def _require_current_authority(
        self,
        task: TaskView,
        expected: Mapping[str, Any],
    ) -> TaskView:
        current = await self._board.get(task.task_id)
        if current is None or current.metadata.get("mission_id") != task.mission_id:
            raise MissionControlError("campaign task disappeared before authorization")
        authority = current.metadata.get(CAMPAIGN_AUTHORITY_METADATA_KEY)
        if not isinstance(authority, dict) or authority != dict(expected):
            raise MissionControlError("campaign task authority changed before effect")
        current_view = task_view(current, task.mission_id)
        self._require_typed_authority(current_view, authority)
        return current_view

    async def dispatch(self, task: TaskView) -> OwnerExecutionRef:
        authority = task.metadata.get(CAMPAIGN_AUTHORITY_METADATA_KEY)
        if not isinstance(authority, dict):
            raise MissionControlError("task has no campaign authority envelope")
        self._require_typed_authority(task, authority)
        await self._require_current_authority(task, authority)
        principal = _authority_identifier(authority, "claimed_principal")
        dispatch_key = _authority_identifier(
            authority,
            "dispatch_key",
            default="default",
        )
        authority_ref = _authority_identifier(authority, "authority_ref")
        authority_digest = _authority_identifier(authority, "authority_digest")
        request = MissionDispatchRequest.new(
            task.mission_id,
            task.task_id,
            dispatch_key=dispatch_key,
            claimed_principal=principal,
            attempt_generation=authority.get("attempt_generation"),
        )
        if authority.get("request_id") != request.request_id:
            raise MissionControlError("campaign authority request identity is foreign")
        governed = await self._dispatcher.canonical_governed_request(request)
        admission = await self._dispatcher.admit(request, governed)
        await self._require_current_authority(task, authority)
        result = await self._dispatcher.dispatch(
            request,
            governed,
            admission,
            DispatchAuthorityEnvelope(
                claimed_principal=principal,
                mission_id=task.mission_id,
                task_id=task.task_id,
                dispatch_key=dispatch_key,
                authority_ref=authority_ref,
                authority_digest=authority_digest,
                attempt_generation=request.attempt_generation,
            ),
        )
        return result.execution

    @staticmethod
    def _require_typed_authority(
        task: TaskView,
        authority: Mapping[str, Any],
    ) -> None:
        required = {
            "schema_version",
            "campaign_id",
            "mission_id",
            "goal_id",
            "portfolio_contract_sha256",
            "goal_contract_sha256",
            "manifest_digest",
            "observed_input_manifest_digest",
            "held_out_oracle_manifest_digest",
            "operator_control_semantics_sha256",
            "operator_control_authority_binding_sha256",
            "deployment_authority_topology_sha256",
            "deployment_authority_credential_clarification_sha256",
            OBSERVED_INPUT_REF_KEY,
            "agent_roster_sha256",
            "effect_mode",
            "campaign_end",
            "agent_name",
            "claimed_principal",
            "dispatch_key",
            "request_id",
            "workspace_path",
            "allowed_files",
            "max_usd",
            "authority_ref",
            "authority_digest",
            "attempt_generation",
            "max_attempts",
        }
        if set(authority) != required:
            raise MissionControlError("campaign authority fields are not exact")
        metadata = task.metadata
        expected = (
            CAMPAIGN_AUTHORITY_SCHEMA_VERSION,
            task.mission_id,
            task.mission_id,
            metadata.get("goal_id"),
            metadata.get("portfolio_contract_sha256"),
            metadata.get("goal_contract_sha256"),
            metadata.get("attempt_ceiling"),
            SCHEMA_VERSION,
            SADHANA_BOOTSTRAP_SCHEMA_VERSION,
            SADHANA_GOAL_CONTRACT_SCHEMA_VERSION,
            task.mission_id,
            task.title,
            0,
            metadata.get("attempt_ceiling"),
            False,
            "authority_unbound",
        )
        observed = (
            authority.get("schema_version"),
            authority.get("campaign_id"),
            authority.get("mission_id"),
            authority.get("goal_id"),
            authority.get("portfolio_contract_sha256"),
            authority.get("goal_contract_sha256"),
            authority.get("max_attempts"),
            metadata.get("schema_version"),
            metadata.get("sadhana_bootstrap_schema"),
            metadata.get("goal_contract_schema"),
            metadata.get("campaign_id"),
            metadata.get("goal_id"),
            metadata.get("cash_ceiling_usd"),
            metadata.get("attempt_ceiling"),
            metadata.get("dispatch_ready"),
            metadata.get("dispatch_blocker"),
        )
        if observed != expected:
            raise MissionControlError("campaign authority conflicts with bootstrap identity")
        generation = authority.get("attempt_generation")
        max_attempts = authority.get("max_attempts")
        if (
            isinstance(generation, bool)
            or not isinstance(generation, int)
            or isinstance(max_attempts, bool)
            or not isinstance(max_attempts, int)
            or max_attempts < 1
            or not 0 <= generation < max_attempts
        ):
            raise MissionControlError("campaign attempt generation is invalid")
        for field in (
            "portfolio_contract_sha256",
            "goal_contract_sha256",
            "manifest_digest",
            "observed_input_manifest_digest",
            "held_out_oracle_manifest_digest",
            "operator_control_semantics_sha256",
            "operator_control_authority_binding_sha256",
            "deployment_authority_topology_sha256",
            "deployment_authority_credential_clarification_sha256",
            "authority_digest",
        ):
            value = authority.get(field)
            if not isinstance(value, str) or _SHA256_RE.fullmatch(value) is None:
                raise MissionControlError(f"campaign authority {field} is invalid")
        roster_digest = authority.get("agent_roster_sha256")
        if not isinstance(roster_digest, str) or _RAW_SHA256_RE.fullmatch(
            roster_digest
        ) is None:
            raise MissionControlError("campaign authority agent roster digest is invalid")
        if authority.get("max_usd") != 0 or isinstance(authority.get("max_usd"), bool):
            raise MissionControlError("campaign authority is not zero-dollar")
        if authority.get("effect_mode") != "read_only":
            raise MissionControlError(
                "write-capable campaign dispatch has no enforced workspace sandbox"
            )
        cash_ceiling = metadata.get("cash_ceiling_usd")
        if (
            isinstance(cash_ceiling, bool)
            or not isinstance(cash_ceiling, (int, float))
            or cash_ceiling != 0
        ):
            raise MissionControlError("campaign bootstrap cash ceiling is not zero-dollar")
        render_bound_observed_input_prompt(metadata)
        governance = metadata.get(GOVERNANCE_METADATA_KEY)
        if not isinstance(governance, Mapping):
            raise MissionControlError("campaign authority has no governance contract")
        if (
            governance.get("allowed_files") != authority.get("allowed_files")
            or governance.get("workspace_path") != authority.get("workspace_path")
            or governance.get("manifest_digest") != authority.get("manifest_digest")
            or governance.get("observed_input_manifest_digest")
            != authority.get("observed_input_manifest_digest")
            or governance.get("held_out_oracle_manifest_digest")
            != authority.get("held_out_oracle_manifest_digest")
            or governance.get("operator_control_semantics_sha256")
            != authority.get("operator_control_semantics_sha256")
            or governance.get("operator_control_authority_binding_sha256")
            != authority.get("operator_control_authority_binding_sha256")
            or governance.get("deployment_authority_topology_sha256")
            != authority.get("deployment_authority_topology_sha256")
            or governance.get("deployment_authority_credential_clarification_sha256")
            != authority.get(
                "deployment_authority_credential_clarification_sha256"
            )
            or governance.get(OBSERVED_INPUT_REF_KEY)
            != authority.get(OBSERVED_INPUT_REF_KEY)
            or governance.get("agent_roster_sha256")
            != authority.get("agent_roster_sha256")
            or governance.get("effect_mode") != authority.get("effect_mode")
            or governance.get("campaign_end") != authority.get("campaign_end")
            or governance.get("attempt_generation")
            != authority.get("attempt_generation")
            or governance.get("max_attempts") != authority.get("max_attempts")
            or isinstance(governance.get("max_usd"), bool)
            or governance.get("max_usd") != 0
        ):
            raise MissionControlError("campaign authority conflicts with governance scope")
        routing = {
            "campaign_effect_mode": "read_only",
            "requires_tooling": False,
            "allow_provider_routing": False,
            "provider_allowlist": [metadata.get("preferred_provider")],
        }
        if any(metadata.get(key) != value for key, value in routing.items()):
            raise MissionControlError("campaign read-only routing boundary is not exact")
        if (
            not isinstance(metadata.get("preferred_provider"), str)
            or not metadata["preferred_provider"]
            or not isinstance(metadata.get("preferred_model"), str)
            or not metadata["preferred_model"]
        ):
            raise MissionControlError("campaign pinned provider/model routing is invalid")


__all__ = [
    "CAMPAIGN_AUTHORITY_METADATA_KEY",
    "CAMPAIGN_AUTHORITY_SCHEMA_VERSION",
    "SADHANA_BOOTSTRAP_SCHEMA_VERSION",
    "SADHANA_GOAL_CONTRACT_SCHEMA_VERSION",
    "FileExecutionLeaseAuthorityVerifier",
    "GovernedCampaignTaskDispatcher",
    "load_campaign_revocations_strict",
]
