"""Read-only native A2A evidence projection into Mission Control types."""

from __future__ import annotations

import asyncio
import hashlib
import json
from pathlib import Path
from typing import Any

from dharma_swarm.a2a.agent_card import A2A_INBOX_ROUTE_ALIAS, a2a_inbox_subject
from dharma_swarm.a2a.envelope_schema import SEND_SCHEMA_VERSION
from dharma_swarm.mission_control_a2a import (
    PATCH_CANDIDATE_SCHEMA,
    _SCAN_LIMIT,
    A2AEvidencePhase,
    A2AExecutionObservation,
    A2ANativeExecutionRef,
    _delivery_id,
    _identity_matches_expected,
    _receipt_digest,
    _require_binding,
    _require_expected_ref,
    _safe_token,
)
from dharma_swarm.mission_control_a2a_evidence import (
    CanonicalA2AEvidenceReader,
    DELIVERY_SCHEMA,
)
from dharma_swarm.mission_control_a2a_candidate import (
    ExactProposalStoreExpectation,
    ExactProposalStoreObservation,
    load_exact_proposals,
    unwrap_exact_proposal,
)
from dharma_swarm.mission_control_a2a_io import (
    ReadQuery,
    _read_only_queries,
    read_json,
    read_semantic_job,
    read_task,
    require_mission,
    safe_file,
)
from dharma_swarm.mission_control_a2a_owner_readback import (
    observe_exact_proposal_store as _observe_exact_proposal_store,
)
from dharma_swarm.mission_control_contract import MissionControlError
from dharma_swarm.mission_control_verification import ExpectedPromotionBindings
from dharma_swarm.models import Task, TaskStatus
from dharma_swarm.runtime_state import RuntimeStateStore
from dharma_swarm.spine.identity import ExecutionIdentity
from dharma_swarm.task_board import TaskBoard


class MissionControlA2AProjection:
    """Observe native evidence without mutating any participating store."""

    def __init__(
        self,
        board: TaskBoard,
        runtime_state: RuntimeStateStore,
        *,
        inbox_root: Path,
        semantic_job_root: Path,
        responder_state_root: Path,
        outbox_root: Path,
        trusted_receipt_roots: tuple[Path, ...] = (),
        max_evidence_bytes: int = 2 * 1024 * 1024,
    ) -> None:
        self._board_db = Path(board._db_path)  # noqa: SLF001
        self._runtime_db = Path(runtime_state.db_path)
        self._inbox_root = inbox_root
        self._job_root = semantic_job_root
        self._max_bytes = max(4096, max_evidence_bytes)
        self._evidence = CanonicalA2AEvidenceReader(
            responder_root=responder_state_root,
            outbox_root=outbox_root,
            trusted_receipt_roots=tuple(trusted_receipt_roots),
            max_bytes=self._max_bytes,
        )

    def _task(self, task_id: str) -> Task | None:
        return read_task(self._board_db, task_id)

    def _require_mission(self, mission_id: str) -> None:
        require_mission(self._runtime_db, mission_id)

    def _execution_identity(self, run_id: str) -> ExecutionIdentity | None:
        columns = (
            "trace_id, correlation_id, task_id, run_id, claim_id, "
            "idempotency_key, causation_id, parent_run_id, agent_id, session_id, "
            "external_a2a_task_id, message_id, event_id, artifact_id, proposal_id, "
            "metadata_json"
        )
        (rows,) = _read_only_queries(
            self._runtime_db,
            "RuntimeState",
            (
                ReadQuery(
                    f"SELECT {columns} FROM execution_identities "
                    "WHERE run_id = ? LIMIT 2",
                    (run_id,),
                ),
            ),
        )
        if not rows:
            return None
        if len(rows) != 1:
            raise MissionControlError(
                "RuntimeState contains duplicate execution identity",
            )
        row = rows[0]
        try:
            metadata = json.loads(str(row["metadata_json"] or "{}"))
        except json.JSONDecodeError as exc:
            raise MissionControlError(
                "durable execution identity metadata is malformed",
            ) from exc
        return ExecutionIdentity(
            trace_id=str(row["trace_id"]),
            correlation_id=str(row["correlation_id"]),
            task_id=str(row["task_id"]),
            run_id=str(row["run_id"]),
            claim_id=str(row["claim_id"] or ""),
            idempotency_key=str(row["idempotency_key"] or ""),
            causation_id=str(row["causation_id"] or ""),
            parent_run_id=str(row["parent_run_id"] or ""),
            agent_id=str(row["agent_id"] or ""),
            session_id=str(row["session_id"] or ""),
            external_a2a_task_id=str(row["external_a2a_task_id"] or ""),
            message_id=str(row["message_id"] or ""),
            event_id=str(row["event_id"] or ""),
            artifact_id=str(row["artifact_id"] or ""),
            proposal_id=str(row["proposal_id"] or ""),
            metadata=metadata if isinstance(metadata, dict) else {},
        )

    def _job(self, ref: A2ANativeExecutionRef) -> dict[str, Any]:
        path = safe_file(
            self._job_root,
            f"{_safe_token(ref.agent_uid, 'agent_uid')}.sqlite3",
        )
        return read_semantic_job(path, ref.packet_id, max_bytes=self._max_bytes)

    async def observe_exact_proposal_store(
        self,
        expected: ExactProposalStoreExpectation,
    ) -> ExactProposalStoreObservation:
        """Join RUNNING Mission Control lineage without minting effect authority."""

        return await asyncio.to_thread(
            _observe_exact_proposal_store,
            self._runtime_db,
            self._board_db,
            expected,
        )

    async def observe(
        self,
        mission_id: str,
        task_id: str,
        *,
        expected: ExpectedPromotionBindings | None = None,
    ) -> A2AExecutionObservation:
        """Return a sealed snapshot; perform no logical or schema writes."""

        self._require_mission(mission_id)
        task = self._task(task_id)
        if task is None:
            raise MissionControlError(f"task {task_id!r} was not found")
        if task.status != TaskStatus.PENDING:
            raise MissionControlError(
                "A2A projection requires a PENDING TaskBoard task"
            )
        ref = _require_binding(task, mission_id)
        delivery_path = safe_file(
            self._inbox_root,
            ref.agent_uid,
            f"{_safe_token(ref.packet_id, 'packet_id')}.json",
        )
        delivery, _ = read_json(delivery_path, limit=self._max_bytes)
        envelope = delivery.get("envelope")
        if (
            not isinstance(envelope, dict)
            or delivery.get("schema_version") != DELIVERY_SCHEMA
        ):
            raise MissionControlError("delivery record has the wrong schema")
        content = envelope.get("content")
        content_sha = (
            hashlib.sha256(content.encode()).hexdigest()
            if isinstance(content, str)
            else ""
        )
        expected_subject = a2a_inbox_subject(ref.agent_uid)
        expected_ack_subject = f"{expected_subject}.ack.{ref.packet_id}"
        expected_reply_subject = f"{expected_subject}.reply.{ref.packet_id}"
        envelope_sha = hashlib.sha256(
            json.dumps(envelope, sort_keys=True).encode()
        ).hexdigest()
        if (
            delivery.get("agent_uid") != ref.agent_uid
            or delivery.get("bridge_kind") != "filesystem_delivery_handler"
            or delivery.get("source_subject") != expected_subject
            or envelope.get("schema_version") != SEND_SCHEMA_VERSION
            or envelope.get("route") != A2A_INBOX_ROUTE_ALIAS
            or envelope.get("to") != ref.agent_uid
            or envelope.get("target_uid") != ref.agent_uid
            or envelope.get("subject") != expected_subject
            or envelope.get("ack_subject") != expected_ack_subject
            or envelope.get("reply_subject") != expected_reply_subject
            or envelope.get("packet_id") != ref.packet_id
            or envelope.get("sha256") != ref.content_sha256
            or content_sha != ref.content_sha256
            or delivery.get("envelope_sha256") != envelope_sha
            or _delivery_id(delivery_path, delivery, envelope) != ref.delivery_id
        ):
            raise MissionControlError(
                "delivery content does not match the task A2A binding"
            )
        if not str(envelope.get("reply_subject") or ""):
            raise MissionControlError("delivery envelope has no reply subject")
        job = self._job(ref)
        if (
            job["envelope"] != envelope
            or job["envelope_sha256"] != delivery.get("envelope_sha256")
            or job["status"] != "PENDING"
        ):
            raise MissionControlError("semantic job and delivery record disagree")

        processed = self._evidence.processed(ref, delivery_path)
        artifact_sha, responder_status, executed = self._evidence.canonical_execution(
            ref=ref,
            delivery_path=delivery_path,
            delivery=delivery,
            envelope=envelope,
            processed=processed,
        )
        phase = A2AEvidencePhase.EXECUTED if executed else A2AEvidencePhase.DELIVERED
        proposals = load_exact_proposals(
            self._runtime_db,
            ref,
            scan_limit=_SCAN_LIMIT,
        )
        if len(proposals) > _SCAN_LIMIT:
            raise MissionControlError("self-mod proposal evidence scan saturated")
        proposals = [
            item
            for item in proposals
            if item.receipt.payload.get("proposal_id") == ref.proposal_id
        ]
        proposal_id = proposal_sha = candidate_digest = diff_sha256 = ""
        base_sha = executor_run_id = ""
        authorized_source_files: tuple[str, ...] = ()
        if proposals:
            if (
                len(proposals) != 1
                or phase != A2AEvidencePhase.EXECUTED
                or expected is None
            ):
                raise MissionControlError(
                    "conflicting or premature patch-candidate evidence"
                )
            proposal_record = proposals[0]
            proposal = proposal_record.receipt
            executor = self._execution_identity(expected.executor_run_id)
            if executor is None or not _identity_matches_expected(
                executor,
                expected,
                role="executor",
            ):
                raise MissionControlError(
                    "patch candidate has no exact durable executor identity"
                )
            payload = unwrap_exact_proposal(proposal_record, ref, executor)
            required_payload = {
                "schema_version",
                "mission_id",
                "task_id",
                "attempt_id",
                "lease_id",
                "packet_id",
                "correlation_id",
                "delivery_id",
                "proposal_id",
                "candidate_digest",
                "diff_sha256",
                "base_sha",
                "artifact_sha256",
                "authorized_source_files",
            }
            payload_identity = (
                payload.get("mission_id") == ref.mission_id
                and payload.get("task_id") == ref.task_id
                and payload.get("attempt_id") == ref.attempt_id
                and payload.get("lease_id") == ref.lease_id
                and payload.get("packet_id") == ref.packet_id
                and payload.get("correlation_id") == ref.correlation_id
                and payload.get("delivery_id") == ref.delivery_id
                and payload.get("proposal_id") == ref.proposal_id
                and payload.get("candidate_digest") == expected.candidate_digest
                and payload.get("diff_sha256") == expected.diff_sha256
                and payload.get("base_sha") == expected.base_sha
                and payload.get("artifact_sha256") == artifact_sha
                and payload.get("authorized_source_files")
                == list(expected.authorized_source_files)
            )
            if (
                set(payload) != required_payload
                or payload.get("schema_version") != PATCH_CANDIDATE_SCHEMA
                or not payload_identity
            ):
                raise MissionControlError(
                    "patch candidate is not bound to the observed A2A execution",
                )
            _require_expected_ref(expected, ref, artifact_sha256=artifact_sha)
            _safe_token(proposal.receipt_id, "proposal receipt_id")
            proposal_id = proposal.receipt_id
            proposal_sha = _receipt_digest(proposal)
            candidate_digest = expected.candidate_digest
            diff_sha256 = expected.diff_sha256
            base_sha = expected.base_sha
            authorized_source_files = expected.authorized_source_files
            executor_run_id = expected.executor_run_id
            phase = A2AEvidencePhase.VERIFYING

        return A2AExecutionObservation._mint(
            native_ref=ref,
            phase=phase,
            task_status=task.status,
            envelope_sha256=str(delivery.get("envelope_sha256") or ""),
            artifact_sha256=artifact_sha,
            semantic_job_status=job["status"],
            responder_status=responder_status,
            proposal_receipt_id=proposal_id,
            proposal_receipt_sha256=proposal_sha,
            candidate_digest=candidate_digest,
            diff_sha256=diff_sha256,
            base_sha=base_sha,
            authorized_source_files=authorized_source_files,
            executor_run_id=executor_run_id,
        )


__all__ = ["MissionControlA2AProjection"]
