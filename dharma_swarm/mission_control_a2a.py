"""Read-only A2A-to-Mission-Control projection and in-process gate."""

from __future__ import annotations

import hashlib
import json
import re
import sqlite3
import stat
import tempfile
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Iterator, Mapping
from urllib.parse import quote

from dharma_swarm.a2a.agent_card import (
    A2A_INBOX_ROUTE_ALIAS,
    a2a_inbox_subject,
)
from dharma_swarm.a2a.envelope_schema import SEND_SCHEMA_VERSION
from dharma_swarm.mission_control_a2a_evidence import (
    CanonicalA2AEvidenceReader,
    DELIVERY_SCHEMA,
    read_bytes,
    read_json,
    safe_file,
)
from dharma_swarm.mission_control_contract import (
    SCHEMA_VERSION as MISSION_CONTROL_SCHEMA,
    MissionControlError,
    session_id as mission_session_id,
)
from dharma_swarm.mission_control_verification import (
    ExpectedPromotionBindings,
    PatchPromotionVerifier,
    PatchPromotionWarrant,
    PromotionRefusal,
)
from dharma_swarm.models import Task, TaskPriority, TaskStatus
from dharma_swarm.runtime_state import RuntimeReceipt, RuntimeStateStore
from dharma_swarm.spine.identity import ExecutionIdentity
from dharma_swarm.task_board import TaskBoard

A2A_BINDING_SCHEMA = "dharma.mission_control.a2a_binding.v1"
A2A_PROJECTION_SCHEMA = "dharma.mission_control.a2a_projection.v1"
PATCH_CANDIDATE_SCHEMA = "dharma.a2a.patch_candidate.v1"
_SCAN_LIMIT = 10_000
_TOKEN = re.compile(r"^[A-Za-z0-9_-]+$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_FOUNDRY_DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")
_GIT_SHA = re.compile(r"^(?:[0-9a-f]{40}|[0-9a-f]{64})$")
_DELIVERY_ID = re.compile(r"^[0-9a-f]{24}$")
_OBSERVATION_SEAL = object()
_MAX_DATABASE_BYTES = 128 * 1024 * 1024
_MAX_WAL_BYTES = 64 * 1024 * 1024


class A2AEvidencePhase(str, Enum):
    """Derived evidence phase; deliberately not a TaskStatus."""

    DELIVERED = "delivered"
    EXECUTED = "executed"
    VERIFYING = "verifying"


@dataclass(frozen=True, slots=True)
class A2ANativeExecutionRef:
    mission_id: str
    task_id: str
    agent_uid: str
    packet_id: str
    correlation_id: str
    delivery_id: str
    proposal_id: str
    content_sha256: str

    @property
    def attempt_id(self) -> str:
        return self.packet_id

    @property
    def lease_id(self) -> str:
        return self.delivery_id


@dataclass(frozen=True, slots=True)
class A2AExecutionObservation:
    """Nominal observation minted only by a successful exact read."""

    native_ref: A2ANativeExecutionRef
    phase: A2AEvidencePhase
    task_status: TaskStatus
    envelope_sha256: str
    artifact_sha256: str = ""
    semantic_job_status: str = ""
    responder_status: str = ""
    proposal_receipt_id: str = ""
    proposal_receipt_sha256: str = ""
    candidate_digest: str = ""
    diff_sha256: str = ""
    base_sha: str = ""
    authorized_source_files: tuple[str, ...] = ()
    executor_run_id: str = ""
    proves_executor_liveness: bool = False
    canonical_task_terminal: bool = False
    _seal: object | None = field(default=None, init=False, repr=False, compare=False)

    @classmethod
    def _mint(cls, **values: Any) -> A2AExecutionObservation:
        observation = cls(**values)
        object.__setattr__(observation, "_seal", _OBSERVATION_SEAL)
        return observation

    def __bool__(self) -> bool:
        return self._seal is _OBSERVATION_SEAL

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload.pop("_seal", None)
        payload["phase"] = self.phase.value
        payload["task_status"] = self.task_status.value
        return payload


def _canonical_digest(value: Mapping[str, Any]) -> str:
    encoded = json.dumps(
        dict(value), ensure_ascii=True, sort_keys=True, separators=(",", ":"),
    )
    return hashlib.sha256(encoded.encode()).hexdigest()


def _safe_token(value: str, label: str) -> str:
    if not value or len(value) > 96 or not _TOKEN.fullmatch(value):
        raise MissionControlError(f"invalid A2A {label}")
    return value


def _existing_db(path: Path, label: str) -> Path:
    candidate = path.expanduser()
    try:
        info = candidate.lstat()
    except OSError as exc:
        raise MissionControlError(f"{label} database is unavailable") from exc
    if stat.S_ISLNK(info.st_mode) or not stat.S_ISREG(info.st_mode):
        raise MissionControlError(f"{label} database is not a regular file")
    return candidate.resolve(strict=True)


def _regular_state(path: Path, label: str) -> tuple[int, int, int, int] | None:
    try:
        info = path.lstat()
    except FileNotFoundError:
        return None
    except OSError as exc:
        raise MissionControlError(f"{label} database snapshot is unavailable") from exc
    if stat.S_ISLNK(info.st_mode) or not stat.S_ISREG(info.st_mode):
        raise MissionControlError(f"{label} database snapshot is not regular")
    return info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns


def _snapshot_database(database: Path, destination: Path, label: str) -> None:
    wal = Path(f"{database}-wal")
    database_before = _regular_state(database, label)
    wal_before = _regular_state(wal, label)
    if database_before is None:
        raise MissionControlError(f"{label} database disappeared before snapshot")
    database_bytes = read_bytes(database, limit=_MAX_DATABASE_BYTES)
    wal_bytes = (
        read_bytes(wal, limit=_MAX_WAL_BYTES)
        if wal_before is not None
        else None
    )
    if (
        _regular_state(database, label) != database_before
        or _regular_state(wal, label) != wal_before
    ):
        raise MissionControlError(f"{label} database changed during snapshot")
    destination.write_bytes(database_bytes)
    if wal_bytes is not None:
        Path(f"{destination}-wal").write_bytes(wal_bytes)


@contextmanager
def _read_only_db(path: Path, label: str) -> Iterator[sqlite3.Connection]:
    database = _existing_db(path, label)
    connection: sqlite3.Connection | None = None
    with tempfile.TemporaryDirectory(prefix="dharma-mc-a2a-ro-") as raw:
        snapshot = Path(raw) / "evidence.sqlite3"
        _snapshot_database(database, snapshot, label)
        uri = f"file:{quote(str(snapshot))}?mode=rw"
        try:
            connection = sqlite3.connect(uri, uri=True)
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA query_only=ON")
            yield connection
        except sqlite3.Error as exc:
            raise MissionControlError(
                f"{label} database is unavailable or malformed",
            ) from exc
        finally:
            if connection is not None:
                connection.close()


def _delivery_id(
    path: Path,
    delivery: Mapping[str, Any],
    envelope: Mapping[str, Any],
) -> str:
    stable = {
        "path": str(path),
        "packet_id": str(envelope.get("packet_id") or ""),
        "reply_subject": str(envelope.get("reply_subject") or ""),
        "envelope_sha256": str(delivery.get("envelope_sha256") or ""),
    }
    return hashlib.sha256(
        json.dumps(stable, sort_keys=True).encode(),
    ).hexdigest()[:24]


def _receipt_digest(receipt: RuntimeReceipt) -> str:
    names = (
        "receipt_id",
        "receipt_type",
        "status",
        "run_id",
        "task_id",
        "trace_id",
        "correlation_id",
        "causation_id",
        "parent_run_id",
        "agent_id",
        "idempotency_key",
        "side_effect_key",
        "payload",
    )
    return _canonical_digest({name: getattr(receipt, name) for name in names})


def _require_binding(task: Task, mission_id: str) -> A2ANativeExecutionRef:
    if (
        task.metadata.get("mission_id") != mission_id
        or task.metadata.get("schema_version") != MISSION_CONTROL_SCHEMA
    ):
        raise MissionControlError(
            f"task {task.id!r} is not owned by mission {mission_id!r}",
        )
    binding = task.metadata.get("a2a_binding")
    if (
        not isinstance(binding, dict)
        or binding.get("schema_version") != A2A_BINDING_SCHEMA
    ):
        raise MissionControlError("task is missing the typed A2A binding")
    agent = str(binding.get("agent_uid") or "")
    packet = str(binding.get("packet_id") or "")
    correlation = str(binding.get("correlation_id") or "")
    delivery = str(binding.get("delivery_id") or "")
    proposal = str(binding.get("proposal_id") or "")
    content = str(binding.get("content_sha256") or "")
    _safe_token(agent, "agent_uid")
    _safe_token(packet, "packet_id")
    _safe_token(proposal, "proposal_id")
    if correlation != f"a2a_send:{agent}:{packet}":
        raise MissionControlError(
            "A2A correlation does not bind the target and packet",
        )
    if not _DELIVERY_ID.fullmatch(delivery) or not _SHA256.fullmatch(content):
        raise MissionControlError("A2A binding is incomplete")
    return A2ANativeExecutionRef(
        mission_id=mission_id,
        task_id=task.id,
        agent_uid=agent,
        packet_id=packet,
        correlation_id=correlation,
        delivery_id=delivery,
        proposal_id=proposal,
        content_sha256=content,
    )


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
        with _read_only_db(self._board_db, "TaskBoard") as connection:
            rows = connection.execute(
                "SELECT id, title, description, status, priority, assigned_to, "
                "created_by, created_at, updated_at, result, metadata "
                "FROM tasks WHERE id = ? LIMIT 2",
                (task_id,),
            ).fetchall()
            if not rows:
                return None
            if len(rows) != 1:
                raise MissionControlError(
                    "TaskBoard contains duplicate task identity",
                )
            dependencies = connection.execute(
                "SELECT depends_on_id FROM task_dependencies "
                "WHERE task_id = ? ORDER BY depends_on_id",
                (task_id,),
            ).fetchall()
        row = rows[0]
        try:
            metadata = json.loads(str(row["metadata"] or "{}"))
            if not isinstance(metadata, dict):
                raise TypeError("metadata is not an object")
            return Task(
                id=str(row["id"]),
                title=str(row["title"]),
                description=str(row["description"] or ""),
                status=TaskStatus(str(row["status"])),
                priority=TaskPriority(str(row["priority"])),
                assigned_to=row["assigned_to"],
                created_by=str(row["created_by"] or "system"),
                created_at=datetime.fromisoformat(str(row["created_at"])),
                updated_at=datetime.fromisoformat(str(row["updated_at"])),
                result=row["result"],
                metadata=metadata,
                depends_on=[str(item[0]) for item in dependencies],
            )
        except (TypeError, ValueError, json.JSONDecodeError) as exc:
            raise MissionControlError("TaskBoard task evidence is malformed") from exc

    def _require_mission(self, mission_id: str) -> None:
        with _read_only_db(self._runtime_db, "RuntimeState") as connection:
            rows = connection.execute(
                "SELECT metadata_json FROM sessions "
                "WHERE session_id = ? LIMIT 2",
                (mission_session_id(mission_id),),
            ).fetchall()
        if len(rows) != 1:
            raise MissionControlError(
                f"mission {mission_id!r} does not exist canonically",
            )
        try:
            metadata = json.loads(str(rows[0]["metadata_json"] or "{}"))
        except json.JSONDecodeError as exc:
            raise MissionControlError(
                "canonical mission metadata is malformed",
            ) from exc
        if (
            not isinstance(metadata, dict)
            or metadata.get("mission_id") != mission_id
            or metadata.get("schema_version") != MISSION_CONTROL_SCHEMA
        ):
            raise MissionControlError(
                f"mission {mission_id!r} does not exist canonically",
            )

    def _execution_identity(self, run_id: str) -> ExecutionIdentity | None:
        columns = (
            "trace_id, correlation_id, task_id, run_id, claim_id, "
            "idempotency_key, causation_id, parent_run_id, agent_id, session_id, "
            "external_a2a_task_id, message_id, event_id, artifact_id, proposal_id, "
            "metadata_json"
        )
        with _read_only_db(self._runtime_db, "RuntimeState") as connection:
            rows = connection.execute(
                f"SELECT {columns} FROM execution_identities "
                "WHERE run_id = ? LIMIT 2",
                (run_id,),
            ).fetchall()
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

    def _proposals(self, ref: A2ANativeExecutionRef) -> list[RuntimeReceipt]:
        columns = (
            "receipt_id, receipt_type, status, run_id, task_id, trace_id, "
            "correlation_id, causation_id, parent_run_id, agent_id, "
            "idempotency_key, side_effect_key, payload_json, created_at"
        )
        with _read_only_db(self._runtime_db, "RuntimeState") as connection:
            rows = connection.execute(
                f"SELECT {columns} FROM runtime_receipts "
                "WHERE correlation_id = ? AND receipt_type = 'self_mod_proposal' "
                "ORDER BY created_at ASC LIMIT ?",
                (ref.correlation_id, _SCAN_LIMIT + 1),
            ).fetchall()
        receipts: list[RuntimeReceipt] = []
        for row in rows:
            try:
                payload = json.loads(str(row["payload_json"] or "{}"))
                created_at = datetime.fromisoformat(str(row["created_at"]))
            except (ValueError, json.JSONDecodeError) as exc:
                raise MissionControlError(
                    "self-mod proposal evidence is malformed",
                ) from exc
            if not isinstance(payload, dict):
                raise MissionControlError(
                    "self-mod proposal payload must be an object",
                )
            receipts.append(
                RuntimeReceipt(
                    receipt_id=str(row["receipt_id"]),
                    receipt_type=str(row["receipt_type"]),
                    status=str(row["status"]),
                    run_id=str(row["run_id"] or ""),
                    task_id=str(row["task_id"] or ""),
                    trace_id=str(row["trace_id"] or ""),
                    correlation_id=str(row["correlation_id"] or ""),
                    causation_id=str(row["causation_id"] or ""),
                    parent_run_id=str(row["parent_run_id"] or ""),
                    agent_id=str(row["agent_id"] or ""),
                    idempotency_key=str(row["idempotency_key"] or ""),
                    side_effect_key=str(row["side_effect_key"] or ""),
                    payload=payload,
                    created_at=created_at,
                ),
            )
        return receipts

    def _job(self, ref: A2ANativeExecutionRef) -> dict[str, Any]:
        path = safe_file(
            self._job_root,
            f"{_safe_token(ref.agent_uid, 'agent_uid')}.sqlite3",
        )
        if path.stat().st_size > self._max_bytes * 16:
            raise MissionControlError(
                "semantic job database exceeds its read bound",
            )
        with _read_only_db(path, "semantic job") as connection:
            rows = connection.execute(
                "SELECT event_id, envelope_sha256, envelope_json, status, "
                "length(envelope_json) AS envelope_length FROM semantic_jobs "
                "WHERE event_id = ? LIMIT 2",
                (ref.packet_id,),
            ).fetchall()
        if len(rows) != 1:
            raise MissionControlError(
                "expected exactly one semantic job for the A2A packet",
            )
        if int(rows[0]["envelope_length"] or 0) > self._max_bytes:
            raise MissionControlError(
                "semantic job envelope exceeds its read bound",
            )
        try:
            envelope = json.loads(str(rows[0]["envelope_json"]))
        except json.JSONDecodeError as exc:
            raise MissionControlError(
                "semantic job envelope is malformed",
            ) from exc
        if not isinstance(envelope, dict):
            raise MissionControlError(
                "semantic job envelope must be an object",
            )
        return {
            "event_id": str(rows[0]["event_id"]),
            "envelope_sha256": str(rows[0]["envelope_sha256"]),
            "envelope": envelope,
            "status": str(rows[0]["status"]),
        }

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
                "A2A projection requires a PENDING TaskBoard task",
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
            json.dumps(envelope, sort_keys=True).encode(),
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
                "delivery content does not match the task A2A binding",
            )
        if not str(envelope.get("reply_subject") or ""):
            raise MissionControlError("delivery envelope has no reply subject")
        job = self._job(ref)
        if (
            job["envelope"] != envelope
            or job["envelope_sha256"] != delivery.get("envelope_sha256")
            or job["status"] != "PENDING"
        ):
            raise MissionControlError(
                "semantic job and delivery record disagree",
            )

        processed = self._evidence.processed(ref, delivery_path)
        artifact_sha, responder_status, executed = (
            self._evidence.canonical_execution(
                ref=ref,
                delivery_path=delivery_path,
                delivery=delivery,
                envelope=envelope,
                processed=processed,
            )
        )
        phase = (
            A2AEvidencePhase.EXECUTED
            if executed
            else A2AEvidencePhase.DELIVERED
        )
        proposals = self._proposals(ref)
        if len(proposals) > _SCAN_LIMIT:
            raise MissionControlError(
                "self-mod proposal evidence scan saturated",
            )
        proposals = [
            item
            for item in proposals
            if item.payload.get("proposal_id") == ref.proposal_id
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
                    "conflicting or premature patch-candidate evidence",
                )
            proposal = proposals[0]
            executor = self._execution_identity(expected.executor_run_id)
            if (
                executor is None
                or not _identity_matches_expected(
                    executor, expected, verifier=False,
                )
            ):
                raise MissionControlError(
                    "patch candidate has no exact durable executor identity",
                )
            payload = proposal.payload
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
            receipt_identity = (
                proposal.run_id == executor.run_id
                and proposal.task_id == executor.task_id
                and proposal.trace_id == executor.trace_id
                and proposal.correlation_id == executor.correlation_id
                and proposal.causation_id == executor.causation_id
                and proposal.parent_run_id == executor.parent_run_id
                and proposal.agent_id == executor.agent_id
                and proposal.idempotency_key == executor.idempotency_key
            )
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
                or proposal.status != "proposed"
                or proposal.receipt_type != "self_mod_proposal"
                or not receipt_identity
                or proposal.side_effect_key
                != f"self_mod:{ref.proposal_id}:proposal"
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


def _require_expected_ref(
    expected: ExpectedPromotionBindings,
    ref: A2ANativeExecutionRef,
    *,
    artifact_sha256: str | None,
) -> None:
    strings = (
        expected.mission_id,
        expected.task_id,
        expected.attempt_id,
        expected.packet_id,
        expected.proposal_id,
        expected.executor_agent_uid,
        expected.executor_run_id,
        expected.verifier_agent_uid,
        expected.verifier_run_id,
        expected.verifier_parent_run_id,
    )
    bare_digests = (expected.diff_sha256, expected.artifact_sha256)
    foundry_digests = (
        expected.candidate_digest,
        expected.lineage_digest,
        expected.command_digest,
        expected.output_digest,
        expected.isolation_digest,
    )
    if (
        any(not value or len(value) > 128 for value in strings)
        or expected.mission_id != ref.mission_id
        or expected.task_id != ref.task_id
        or expected.attempt_id != ref.attempt_id
        or expected.lease_id != ref.lease_id
        or expected.packet_id != ref.packet_id
        or expected.correlation_id != ref.correlation_id
        or expected.delivery_id != ref.delivery_id
        or expected.proposal_id != ref.proposal_id
        or expected.executor_agent_uid != ref.agent_uid
        or (
            artifact_sha256 is not None
            and expected.artifact_sha256 != artifact_sha256
        )
        or not all(_SHA256.fullmatch(value) for value in bare_digests)
        or not all(_FOUNDRY_DIGEST.fullmatch(value) for value in foundry_digests)
        or not _GIT_SHA.fullmatch(expected.base_sha)
        or not expected.authorized_source_files
        or any(
            not path
            or Path(path).is_absolute()
            or ".." in Path(path).parts
            for path in expected.authorized_source_files
        )
    ):
        raise MissionControlError(
            "promotion bindings do not match observed A2A execution",
        )


def _identity_matches_expected(
    identity: ExecutionIdentity,
    expected: ExpectedPromotionBindings,
    *,
    verifier: bool,
) -> bool:
    expected_agent = (
        expected.verifier_agent_uid
        if verifier
        else expected.executor_agent_uid
    )
    expected_run = (
        expected.verifier_run_id if verifier else expected.executor_run_id
    )
    return (
        identity.task_id == expected.task_id
        and identity.correlation_id == expected.correlation_id
        and identity.session_id == mission_session_id(expected.mission_id)
        and identity.proposal_id == expected.proposal_id
        and identity.agent_id == expected_agent
        and identity.run_id == expected_run
        and (
            identity.parent_run_id == expected.verifier_parent_run_id
            if verifier
            else True
        )
        and bool(identity.trace_id)
        and bool(identity.claim_id)
        and bool(identity.idempotency_key)
    )


class A2APatchPromotionEvaluator:
    """Revalidate and return only a projection-only in-process warrant."""

    def __init__(
        self,
        projection: MissionControlA2AProjection,
        *,
        verifier: PatchPromotionVerifier,
    ) -> None:
        if type(verifier) is not PatchPromotionVerifier:
            raise TypeError("verifier must be an exact PatchPromotionVerifier")
        self._projection = projection
        self._verifier = verifier

    async def issue_warrant(
        self,
        observation: A2AExecutionObservation,
        *,
        expected: ExpectedPromotionBindings,
        signed_patch_verification: Mapping[str, Any] | None,
        vibe_halt_receipt: Mapping[str, Any] | None,
    ) -> PatchPromotionWarrant | PromotionRefusal:
        if (
            not observation
            or observation.phase != A2AEvidencePhase.VERIFYING
        ):
            return PromotionRefusal(
                ("unsealed_or_nonverifying_a2a_observation",),
            )
        try:
            current = await self._projection.observe(
                expected.mission_id,
                expected.task_id,
                expected=expected,
            )
        except MissionControlError:
            return PromotionRefusal(("a2a_observation_revalidation_failed",))
        if not current or current != observation:
            return PromotionRefusal(
                ("a2a_observation_changed_before_evaluation",),
            )
        if (
            current.candidate_digest != expected.candidate_digest
            or current.diff_sha256 != expected.diff_sha256
            or current.base_sha != expected.base_sha
            or current.authorized_source_files
            != expected.authorized_source_files
            or current.executor_run_id != expected.executor_run_id
            or not current.proposal_receipt_id
            or not _SHA256.fullmatch(current.proposal_receipt_sha256)
        ):
            return PromotionRefusal(
                ("a2a_candidate_observation_mismatch",),
            )
        durable_verifier = self._projection._execution_identity(  # noqa: SLF001
            expected.verifier_run_id,
        )
        if (
            durable_verifier is None
            or not _identity_matches_expected(
                durable_verifier,
                expected,
                verifier=True,
            )
        ):
            return PromotionRefusal(
                ("missing_exact_durable_verifier_identity",),
            )
        result = self._verifier.evaluate(
            signed_patch_verification,
            expected=expected,
            vibe_halt_receipt=vibe_halt_receipt,
        )
        if isinstance(result, PromotionRefusal):
            return result
        if not result:
            return PromotionRefusal(("unsealed_promotion_warrant",))
        return result


__all__ = [
    "A2A_BINDING_SCHEMA",
    "A2AEvidencePhase",
    "A2AExecutionObservation",
    "A2ANativeExecutionRef",
    "A2APatchPromotionEvaluator",
    "MissionControlA2AProjection",
]
