"""Campaign-specific fail-closed classification for graph recovery."""

from __future__ import annotations

import json
import logging
import sqlite3
from datetime import datetime
from typing import Any, Mapping

from dharma_swarm.loop_closure_quarantine import parse_ts
from dharma_swarm.graph.receipt_authority import claim_run_match
from dharma_swarm.spine.identity import ExecutionIdentity, MissingExecutionIdentity
from dharma_swarm.task_board_campaign_guard import (
    CAMPAIGN_RUNTIME_RECOVERY_FENCE_KEY,
    campaign_metadata_bound,
    campaign_runtime_recovery_fence,
    metadata_mapping,
    runtime_campaign_metadata_bound,
)
from dharma_swarm.task_board_projection_intent import (
    TASK_BOARD_PROJECTION_INTENT_KEY,
    TASK_BOARD_PROJECTION_WITNESS_KEY,
)

CAMPAIGN_RECOVERY_HOLD_KEY = "campaign_recovery_hold"
CAMPAIGN_RECOVERY_HOLD_SCHEMA = "dharma.sadhana.campaign_recovery_hold.v1"
BOARD_IN_FLIGHT_STATUSES = frozenset({"assigned", "running"})

logger = logging.getLogger(__name__)


def _load_json(raw: Any) -> dict[str, Any]:
    if isinstance(raw, dict):
        return dict(raw)
    if not isinstance(raw, str) or not raw:
        return {}
    try:
        value = json.loads(raw)
    except (json.JSONDecodeError, TypeError, ValueError):
        return {}
    return value if isinstance(value, dict) else {}


def campaign_hold_metadata(
    raw: Any,
    now: datetime,
    *,
    task_id: str,
    claim_id: str,
    run_id: str,
) -> dict[str, Any]:
    """Persist uncertainty; never state cessation or mint retry authority."""
    metadata = _load_json(raw)
    metadata[CAMPAIGN_RECOVERY_HOLD_KEY] = {
        "schema_version": CAMPAIGN_RECOVERY_HOLD_SCHEMA,
        "state": "effect_indeterminate",
        "retry_authorized": False,
        "cessation_proven": False,
        "observed_at": now.isoformat(),
        "task_id": task_id,
        "claim_id": claim_id,
        "run_id": run_id,
    }
    return metadata


def campaign_recovery_hold(
    raw: Any,
    *,
    task_id: str,
    claim_id: str,
) -> dict[str, Any] | None:
    marker = _load_json(raw).get(CAMPAIGN_RECOVERY_HOLD_KEY)
    valid = bool(
        isinstance(marker, dict)
        and set(marker)
        == {
            "schema_version",
            "state",
            "retry_authorized",
            "cessation_proven",
            "observed_at",
            "task_id",
            "claim_id",
            "run_id",
        }
        and marker.get("schema_version") == CAMPAIGN_RECOVERY_HOLD_SCHEMA
        and marker.get("state") == "effect_indeterminate"
        and marker.get("retry_authorized") is False
        and marker.get("cessation_proven") is False
        and parse_ts(marker.get("observed_at")) is not None
        and marker.get("task_id") == task_id
        and marker.get("claim_id") == claim_id
        and isinstance(marker.get("run_id"), str)
        and bool(marker.get("run_id"))
    )
    return marker if valid else None


def has_campaign_recovery_hold(
    raw: Any,
    *,
    task_id: str,
    claim_id: str,
) -> bool:
    return campaign_recovery_hold(raw, task_id=task_id, claim_id=claim_id) is not None


def explicit_legacy_runtime_compatibility(raw: Any) -> bool:
    """Recognize only the V4-marked legacy compatibility lane."""
    metadata = _load_json(raw)
    return bool(
        metadata.get("legacy_no_identity_allowed") is True
        and metadata.get("runtime_spine_status") == "legacy_no_identity"
        and not runtime_campaign_metadata_bound(metadata)
        and TASK_BOARD_PROJECTION_INTENT_KEY not in metadata
        and TASK_BOARD_PROJECTION_WITNESS_KEY not in metadata
    )


def explicit_legacy_runtime_execution(
    row: Mapping[str, Any],
    raw: Any,
) -> bool:
    """Allow the marked legacy lane only for blank/canonical runtime owners."""
    return bool(
        str(row["assigned_by"] or "") in {"", "orchestrator"}
        and explicit_legacy_runtime_compatibility(raw)
    )


def _board_campaign_shaped(raw: Any) -> bool:
    metadata = _load_json(raw)
    return bool(
        campaign_metadata_bound(metadata)
        or any(
            key in metadata
            for key in (
                "campaign_dispatch_recovery",
                "campaign_dispatch_attempt_history",
                "mission_control_governance",
                "mission_control_owner_execution",
            )
        )
    )


def canonical_orchestrator_execution(
    row: Mapping[str, Any],
    raw: Any,
) -> dict[str, Any] | None:
    """Return the exact V4 identity only for its canonical runtime owner."""
    metadata = _load_json(raw)
    nested = metadata.get("execution_identity")
    if not isinstance(nested, dict) or str(row["assigned_by"] or "") != "orchestrator":
        return None
    try:
        identity = ExecutionIdentity.from_metadata(metadata, require=True)
    except (MissingExecutionIdentity, TypeError, ValueError):
        return None
    if identity is None or identity.to_dict() != nested:
        return None
    if not all(
        getattr(identity, key)
        for key in (
            "trace_id",
            "correlation_id",
            "task_id",
            "run_id",
            "claim_id",
            "idempotency_key",
            "agent_id",
            "session_id",
        )
    ):
        return None
    expected = {
        "run_id": str(row["run_id"] or ""),
        "task_id": str(row["task_id"] or ""),
        "claim_id": str(row["claim_id"] or ""),
        "agent_id": str(row["assigned_to"] or ""),
        "session_id": str(row["session_id"] or ""),
        "parent_run_id": str(row["parent_run_id"] or ""),
    }
    if any(getattr(identity, key) != value for key, value in expected.items()):
        return None
    required_aliases = {
        "trace_id": identity.trace_id,
        "correlation_id": identity.correlation_id,
        "run_id": identity.run_id,
        "runtime_run_id": identity.run_id,
        "claim_id": identity.claim_id,
        "agent_id": identity.agent_id,
        "session_id": identity.session_id,
        "idempotency_key": identity.idempotency_key,
    }
    if any(metadata.get(key) != value for key, value in required_aliases.items()):
        return None
    # RuntimeLifecycle's in-flight carrier predates these flat aliases.  The
    # exact values still exist in the nested identity and the SQL row, so an
    # absent alias is not ambiguity; a present disagreement is.  Terminal
    # ProjectionIntent preparation derives and seals all three atomically.
    optional_aliases = {
        "task_id": identity.task_id,
        "parent_run_id": identity.parent_run_id,
        "causation_id": identity.causation_id,
    }
    if any(
        key in metadata and metadata.get(key) != value
        for key, value in optional_aliases.items()
    ):
        return None
    return nested


def canonical_claim_execution(
    row: Mapping[str, Any],
    identity: dict[str, Any],
) -> bool:
    """Prove that one claim carrier belongs to the exact canonical attempt."""
    metadata = _load_json(row["metadata_json"])
    if metadata.get("execution_identity") != identity:
        return False
    expected = {
        "claim_id": str(row["claim_id"] or ""),
        "task_id": str(row["task_id"] or ""),
        "agent_id": str(row["agent_id"] or ""),
        "session_id": str(row["session_id"] or ""),
    }
    if any(identity.get(key) != value for key, value in expected.items()):
        return False
    required_aliases = {
        "trace_id": identity["trace_id"],
        "correlation_id": identity["correlation_id"],
        "run_id": identity["run_id"],
        "runtime_run_id": identity["run_id"],
        "claim_id": identity["claim_id"],
        "agent_id": identity["agent_id"],
        "session_id": identity["session_id"],
        "idempotency_key": identity["idempotency_key"],
    }
    if any(metadata.get(key) != value for key, value in required_aliases.items()):
        return False
    optional_aliases = {
        "task_id": identity["task_id"],
        "parent_run_id": identity["parent_run_id"],
        "causation_id": identity["causation_id"],
    }
    return not any(
        key in metadata and metadata.get(key) != value
        for key, value in optional_aliases.items()
    )


def campaign_attempt_classification(
    *,
    task_id: str,
    board_task: Any | None,
    runtime_raws: tuple[Any, ...],
) -> tuple[bool, str]:
    """Classify all campaign surfaces without performing Board I/O."""
    runtime_bound = any(runtime_campaign_metadata_bound(raw) for raw in runtime_raws)
    markers = [
        raw
        for raw in runtime_raws
        if CAMPAIGN_RUNTIME_RECOVERY_FENCE_KEY in metadata_mapping(raw)
    ]
    fences = [campaign_runtime_recovery_fence(raw, task_id=task_id) for raw in markers]
    error = ""
    if any(fence is None for fence in fences):
        error = "malformed_runtime_recovery_fence"
    valid_fences = [fence for fence in fences if fence is not None]
    if len(valid_fences) > 1 and any(
        fence != valid_fences[0] for fence in valid_fences[1:]
    ):
        error = "runtime_recovery_fence_disagreement"

    board_bound = False
    board_shaped = False
    board_principal = ""
    if board_task is not None:
        from dharma_swarm.mission_control_executor_guard import campaign_principal

        board_bound, principal = campaign_principal(board_task)
        board_principal = str(principal or "")
        board_metadata = getattr(board_task, "metadata", {})
        board_metadata = board_metadata if isinstance(board_metadata, dict) else {}
        board_shaped = _board_campaign_shaped(board_metadata)
        if board_shaped and not board_bound:
            error = error or "malformed_board_campaign_authority"
    if runtime_bound and not board_bound:
        error = error or "runtime_campaign_missing_board_authority"
    if board_bound:
        status = getattr(
            getattr(board_task, "status", None),
            "value",
            getattr(board_task, "status", ""),
        )
        if (
            not board_principal
            or status not in BOARD_IN_FLIGHT_STATUSES
            or str(getattr(board_task, "assigned_to", "") or "") != board_principal
        ):
            error = error or "campaign_board_live_authority_mismatch"
        authority = board_metadata.get("mission_campaign_authority")
        authority = authority if isinstance(authority, dict) else {}
        for fence in valid_fences:
            if (
                fence.get("claimed_principal") != board_principal
                or any(
                    fence.get(key) != authority.get(key)
                    for key in (
                        "campaign_id",
                        "goal_id",
                        "authority_digest",
                        "attempt_generation",
                    )
                )
            ):
                error = error or "runtime_board_campaign_disagreement"
                break
    return board_shaped or board_bound or runtime_bound, error


def _row_values(row: sqlite3.Row, fields: tuple[str, ...]) -> tuple[Any, ...]:
    return tuple(row[field] for field in fields)


def _board_attempt_snapshots_locked(
    board_db: sqlite3.Connection | None,
    task_ids: set[str],
) -> dict[str, dict[str, Any] | None]:
    if not task_ids:
        return {}
    if board_db is None:
        return {task_id: None for task_id in task_ids}
    from dharma_swarm.mission_control_executor_guard import campaign_principal
    from dharma_swarm.models import Task, TaskStatus

    snapshots: dict[str, dict[str, Any] | None] = {}
    for task_id in task_ids:
        row = board_db.execute(
            "SELECT id, status, assigned_to, metadata FROM tasks WHERE id = ?",
            (task_id,),
        ).fetchone()
        if row is None:
            snapshots[task_id] = None
            continue
        metadata = _load_json(row["metadata"])
        try:
            task = Task(
                id=str(row["id"]),
                title="campaign heartbeat witness",
                status=TaskStatus(str(row["status"])),
                assigned_to=row["assigned_to"],
                metadata=metadata,
            )
            bound, principal = campaign_principal(task)
        except (TypeError, ValueError):
            bound, principal = False, ""
        identity = metadata.get("execution_identity")
        authority = metadata.get("mission_campaign_authority")
        campaign_shaped = _board_campaign_shaped(metadata)
        snapshots[task_id] = {
            "campaign_shaped": campaign_shaped,
            "campaign_valid": bool(
                campaign_shaped
                and bound
                and principal
                and isinstance(identity, dict)
                and isinstance(authority, dict)
            ),
            "identity": identity,
            "authority": authority,
            "principal": str(principal or ""),
            "status": str(row["status"]),
            "assigned_to": str(row["assigned_to"] or ""),
        }
    return snapshots


def _identity_registry_is_exact(
    db: sqlite3.Connection,
    identity: dict[str, Any],
) -> bool:
    row = db.execute(
        "SELECT trace_id, correlation_id, task_id, claim_id, idempotency_key,"
        " causation_id, parent_run_id, agent_id, session_id,"
        " external_a2a_task_id, message_id, event_id, artifact_id, proposal_id,"
        " metadata_json FROM execution_identities WHERE run_id = ?",
        (identity["run_id"],),
    ).fetchone()
    if row is None:
        return False
    fields = (
        "trace_id",
        "correlation_id",
        "task_id",
        "claim_id",
        "idempotency_key",
        "causation_id",
        "parent_run_id",
        "agent_id",
        "session_id",
        "external_a2a_task_id",
        "message_id",
        "event_id",
        "artifact_id",
        "proposal_id",
    )
    return all(str(row[field] or "") == identity[field] for field in fields) and (
        _load_json(row["metadata_json"]) == identity["metadata"]
    )


def heartbeat_live_claims_exact(
    *,
    runtime_state: Any,
    task_board: Any,
    census_succeeded: bool,
    invalidate_census: Any,
    default_window: float,
    now: datetime,
) -> int:
    """Heartbeat only while one Board→runtime authority fence is held."""
    if not census_succeeded:
        logger.error("reconciler: refusing heartbeat before successful census")
        return 0
    runtime_state.init_db_sync()
    claim_fields = (
        "claim_id",
        "task_id",
        "session_id",
        "agent_id",
        "status",
        "claimed_at",
        "heartbeat_at",
        "stale_after",
        "recovered_at",
        "metadata_json",
    )
    run_fields = (
        "run_id",
        "session_id",
        "task_id",
        "claim_id",
        "parent_run_id",
        "assigned_by",
        "assigned_to",
        "status",
        "metadata_json",
    )
    with sqlite3.connect(runtime_state.db_path) as read_db:
        read_db.row_factory = sqlite3.Row
        claims = read_db.execute(
            "SELECT " + ",".join(claim_fields) + " FROM task_claims"
            " WHERE status IN ('claimed', 'running') AND recovered_at IS NULL"
        ).fetchall()
        runs = read_db.execute(
            "SELECT " + ",".join(run_fields) + " FROM delegation_runs"
            " WHERE status IN ('claimed', 'running')"
        ).fetchall()
    runtime_campaign_ids = {
        str(claim["task_id"])
        for claim in claims
        if runtime_campaign_metadata_bound(claim["metadata_json"])
    } | {
        str(run["task_id"])
        for run in runs
        if runtime_campaign_metadata_bound(run["metadata_json"])
    }
    all_task_ids = {str(claim["task_id"]) for claim in claims} | {
        str(run["task_id"]) for run in runs
    }
    beaten = 0
    board_db: sqlite3.Connection | None = None
    try:
        board_path = getattr(task_board, "_db_path", None)
        if board_path is not None:
            board_db = sqlite3.connect(board_path, timeout=2.0)
            board_db.row_factory = sqlite3.Row
            board_db.execute("PRAGMA busy_timeout=2000")
            # TaskBoard terminal projection uses this same Board→runtime lock
            # order.  Holding the Board writer fence prevents reassignment or
            # generation advance after the authority snapshot but before the
            # runtime heartbeat commits.
            board_db.execute("BEGIN IMMEDIATE")
        board = _board_attempt_snapshots_locked(board_db, all_task_ids)
        with sqlite3.connect(runtime_state.db_path) as db:
            db.row_factory = sqlite3.Row
            db.execute("PRAGMA busy_timeout=2000")
            db.execute("BEGIN IMMEDIATE")
            locked_claims = db.execute(
                "SELECT " + ",".join(claim_fields) + " FROM task_claims"
                " WHERE status IN ('claimed', 'running') AND recovered_at IS NULL"
            ).fetchall()
            locked_runs = db.execute(
                "SELECT " + ",".join(run_fields) + " FROM delegation_runs"
                " WHERE status IN ('claimed', 'running')"
            ).fetchall()
            if (
                sorted(_row_values(row, claim_fields) for row in locked_claims)
                != sorted(_row_values(row, claim_fields) for row in claims)
                or sorted(_row_values(row, run_fields) for row in locked_runs)
                != sorted(_row_values(row, run_fields) for row in runs)
            ):
                raise RuntimeError("heartbeat authority changed after census")
            # From this point cardinality and row values are pinned by the
            # runtime writer transaction.  In particular, a second owner run
            # cannot appear after the candidate set is counted.
            claims = locked_claims
            runs = locked_runs
            for claim in claims:
                current_claim = db.execute(
                    "SELECT " + ",".join(claim_fields)
                    + " FROM task_claims WHERE claim_id = ?",
                    (str(claim["claim_id"]),),
                ).fetchone()
                if current_claim is None or _row_values(
                    current_claim, claim_fields
                ) != _row_values(claim, claim_fields):
                    raise RuntimeError("claim changed after heartbeat census")
                candidates = [
                    run
                    for run in runs
                    if str(run["task_id"]) == str(claim["task_id"])
                    and str(run["claim_id"] or "") == str(claim["claim_id"])
                ]
                exact = [run for run in candidates if claim_run_match(claim, run)]
                task_id = str(claim["task_id"])
                witness = board.get(task_id)
                runtime_campaign = task_id in runtime_campaign_ids
                board_campaign = bool(
                    isinstance(witness, dict) and witness.get("campaign_shaped")
                )
                campaign = runtime_campaign or board_campaign
                if campaign:
                    if not runtime_campaign or not board_campaign:
                        raise RuntimeError(
                            "campaign heartbeat authority surface is incomplete"
                        )
                    if len(exact) != 1:
                        raise RuntimeError("campaign heartbeat lacks one exact run")
                    run = exact[0]
                    identity = canonical_orchestrator_execution(
                        run, run["metadata_json"]
                    )
                    if (
                        identity is None
                        or not canonical_claim_execution(claim, identity)
                        or not _identity_registry_is_exact(db, identity)
                        or not isinstance(witness, dict)
                        or witness.get("campaign_valid") is not True
                    ):
                        raise RuntimeError("campaign heartbeat authority is incomplete")
                    hold = campaign_recovery_hold(
                        claim["metadata_json"],
                        task_id=str(claim["task_id"]),
                        claim_id=str(claim["claim_id"]),
                    )
                    run_hold = campaign_recovery_hold(
                        run["metadata_json"],
                        task_id=str(claim["task_id"]),
                        claim_id=str(claim["claim_id"]),
                    )
                    claim_has_hold = CAMPAIGN_RECOVERY_HOLD_KEY in _load_json(
                        claim["metadata_json"]
                    )
                    run_has_hold = CAMPAIGN_RECOVERY_HOLD_KEY in _load_json(
                        run["metadata_json"]
                    )
                    if claim_has_hold or run_has_hold:
                        if hold is not None and hold == run_hold:
                            continue
                        raise RuntimeError(
                            "campaign heartbeat hold authority disagrees"
                        )
                    fence = campaign_runtime_recovery_fence(
                        run["metadata_json"], task_id=str(claim["task_id"])
                    )
                    if not (
                        witness["identity"] == identity
                        and witness["status"] in BOARD_IN_FLIGHT_STATUSES
                        and witness["assigned_to"] == identity["agent_id"]
                        and witness["principal"] == identity["agent_id"]
                        and isinstance(fence, dict)
                        and all(
                            witness["authority"].get(key) == fence.get(key)
                            for key in (
                                "campaign_id",
                                "goal_id",
                                "authority_digest",
                                "attempt_generation",
                                "claimed_principal",
                            )
                        )
                    ):
                        raise RuntimeError("campaign heartbeat Board attempt changed")
                elif len(exact) > 1:
                    raise RuntimeError("ordinary heartbeat has ambiguous runtime owner")
                elif exact:
                    ordinary_identity = canonical_orchestrator_execution(
                        exact[0], exact[0]["metadata_json"]
                    )
                    legacy_exact = (
                        explicit_legacy_runtime_compatibility(claim["metadata_json"])
                        and explicit_legacy_runtime_execution(
                            exact[0], exact[0]["metadata_json"]
                        )
                    )
                    if not legacy_exact and (
                        ordinary_identity is None
                        or not canonical_claim_execution(claim, ordinary_identity)
                    ):
                        raise RuntimeError(
                            "ordinary heartbeat runtime owner is unknown"
                        )
                elif not exact:
                    raise RuntimeError("ordinary heartbeat owner is unknown")

                if exact:
                    source_run = exact[0]
                    current_run = db.execute(
                        "SELECT " + ",".join(run_fields)
                        + " FROM delegation_runs WHERE run_id = ?",
                        (str(source_run["run_id"]),),
                    ).fetchone()
                    if current_run is None or _row_values(
                        current_run, run_fields
                    ) != _row_values(source_run, run_fields):
                        raise RuntimeError("run changed after heartbeat census")
                claimed_at = parse_ts(claim["claimed_at"])
                stale_after = parse_ts(claim["stale_after"])
                window = (
                    max((stale_after - claimed_at).total_seconds() / 3.0, 1.0)
                    if claimed_at is not None and stale_after is not None
                    else default_window
                )
                last = parse_ts(claim["heartbeat_at"]) or claimed_at
                if last is not None and (now - last).total_seconds() < window:
                    continue
                cursor = db.execute(
                    "UPDATE task_claims SET heartbeat_at = ? WHERE claim_id = ?"
                    " AND status = ? AND heartbeat_at IS ? AND metadata_json = ?",
                    (
                        now.isoformat(),
                        str(claim["claim_id"]),
                        str(claim["status"]),
                        claim["heartbeat_at"],
                        claim["metadata_json"],
                    ),
                )
                if cursor.rowcount != 1:
                    raise RuntimeError("claim heartbeat lost exact writer fence")
                beaten += 1
            db.commit()
        if board_db is not None:
            board_db.rollback()
    except BaseException as exc:
        if board_db is not None and board_db.in_transaction:
            board_db.rollback()
        invalidate_census()
        if isinstance(exc, RuntimeError):
            raise
        raise RuntimeError("claim heartbeat transaction failed") from exc
    finally:
        if board_db is not None:
            board_db.close()
    return beaten


__all__ = [
    "BOARD_IN_FLIGHT_STATUSES",
    "CAMPAIGN_RECOVERY_HOLD_KEY",
    "CAMPAIGN_RECOVERY_HOLD_SCHEMA",
    "campaign_attempt_classification",
    "campaign_hold_metadata",
    "campaign_recovery_hold",
    "canonical_claim_execution",
    "canonical_orchestrator_execution",
    "explicit_legacy_runtime_compatibility",
    "explicit_legacy_runtime_execution",
    "heartbeat_live_claims_exact",
    "has_campaign_recovery_hold",
]
