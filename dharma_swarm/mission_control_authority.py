"""Exact file-backed authority adapters for governed campaign dispatch."""

from __future__ import annotations

import json
from collections.abc import Iterator, Mapping
from pathlib import Path
from typing import Any

from dharma_swarm.mission_control_contract import (
    MissionControlError,
    TaskView,
    clean_identifier,
)
from dharma_swarm.mission_control_dispatch import (
    LEASE_DISPATCH_ACTION,
    DispatchAuthorityEnvelope,
    GovernanceAdmission,
    GovernedMissionDispatcher,
    MissionDispatchRequest,
    VerifiedDispatchAuthority,
)
from dharma_swarm.mission_control_execution import OwnerExecutionRef
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


def _load_revocations_strict(root: Path) -> set[str]:
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
            revoked = _load_revocations_strict(self._root)
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

    def __init__(self, lease_root: Path | str) -> None:
        self._lease_root = Path(lease_root).expanduser().resolve(strict=False)

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
        )
        observed = (
            envelope.claimed_principal,
            envelope.mission_id,
            envelope.task_id,
            envelope.dispatch_key,
        )
        if observed != expected:
            raise MissionControlError("authority envelope names a foreign dispatch")
        try:
            lease = _load_exact_lease(self._lease_root, envelope.authority_ref)
            revoked = _load_revocations_strict(self._lease_root)
        except (ExecutionLeaseError, OSError, ValueError, json.JSONDecodeError) as exc:
            raise MissionControlError("execution authority could not be loaded") from exc
        digest = content_hash(lease)
        if lease.get("content_hash") != digest or digest != envelope.authority_digest:
            raise MissionControlError("execution authority digest does not match exact file")
        validation = validate_execution_lease(
            lease,
            agent_uid=request.claimed_principal,
            task_id=request.task_id,
            requested_actions=[LEASE_DISPATCH_ACTION],
            revoked_lease_ids=revoked,
        )
        if not validation.valid:
            raise MissionControlError(
                "execution authority is invalid: " + "; ".join(validation.errors)
            )
        if lease.get("correlation_id") != request.request_id:
            raise MissionControlError("execution authority correlation is foreign")
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
    ) -> None:
        current = await self._board.get(task.task_id)
        if current is None or current.metadata.get("mission_id") != task.mission_id:
            raise MissionControlError("campaign task disappeared before authorization")
        authority = current.metadata.get(CAMPAIGN_AUTHORITY_METADATA_KEY)
        if not isinstance(authority, dict) or authority != dict(expected):
            raise MissionControlError("campaign task authority changed before effect")

    async def dispatch(self, task: TaskView) -> OwnerExecutionRef:
        authority = task.metadata.get(CAMPAIGN_AUTHORITY_METADATA_KEY)
        if not isinstance(authority, dict):
            raise MissionControlError("task has no campaign authority envelope")
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
        )
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
            ),
        )
        return result.execution


__all__ = [
    "CAMPAIGN_AUTHORITY_METADATA_KEY",
    "FileExecutionLeaseAuthorityVerifier",
    "GovernedCampaignTaskDispatcher",
]
