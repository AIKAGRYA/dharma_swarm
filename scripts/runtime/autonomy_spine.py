#!/usr/bin/env python3
"""Compatibility CLI for ds-goal missions backed by LivingAgentKernel wakes.

This is intentionally a bounded bridge. It creates mission/task ledgers that
can be projected into operator boards, enqueues ds_goal wakes, and runs a
finite kernel control tick. It does not start a standing daemon or replace the
existing LivingAgentKernel control loop.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dharma_swarm.operator_core.living_agent_kernel import KernelRunStore, LivingAgentKernel  # noqa: E402
from dharma_swarm.operator_core.runtime_truth import runtime_db_path_from_env, stable_payload_hash, utc_now  # noqa: E402
from dharma_swarm.board.adapters.ds_goal_adapter import load_ds_goal_cards  # noqa: E402
from dharma_swarm.runtime_state import (  # noqa: E402
    ArtifactRecord,
    DelegationRun,
    ExecutionIdentity,
    RuntimeReceipt,
    RuntimeStateStore,
    TaskClaim,
)
from dharma_swarm.spine.receipt import EvidenceReceipt  # noqa: E402
from dharma_swarm.spine.warrant import RuntimeWarrantDenied, issue_runtime_warrant  # noqa: E402

DEFAULT_STATE_ROOT = Path.home() / ".dharma" / "ds_goals"
DEFAULT_KERNEL_STORE = Path.home() / ".dharma" / "living_agent_kernel"
SCHEMA_VERSION = "dharma.ds_goal_spine.v1"
MISSION_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,95}$")


def _json_default(value: Any) -> str:
    return str(value)


def _print(payload: dict[str, Any], *, as_json: bool) -> None:
    if as_json:
        print(json.dumps(payload, sort_keys=True, default=_json_default))
        return
    status = payload.get("status") or payload.get("command_status") or "ok"
    mission_id = payload.get("mission_id") or ""
    path = payload.get("mission_dir") or payload.get("state_root") or ""
    print(f"{status}: {mission_id} {path}".strip())


def _jsonl_rows(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def _append_jsonl(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, sort_keys=True, default=_json_default) + "\n")


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=_json_default) + "\n", encoding="utf-8")


def _slug(value: str) -> str:
    raw = value.strip().lower()
    parts: list[str] = []
    current: list[str] = []
    for char in raw:
        if char.isalnum():
            current.append(char)
        elif current:
            parts.append("".join(current))
            current = []
    if current:
        parts.append("".join(current))
    slug = "-".join(parts)[:48].strip("-")
    return slug or f"mission-{uuid4().hex[:10]}"


def _validate_mission_id(mission_id: str) -> str:
    clean = str(mission_id or "").strip()
    if not MISSION_ID_RE.fullmatch(clean):
        raise ValueError(
            "mission_id must be 1-96 chars of letters, numbers, dash, underscore, or dot; "
            "path separators are not allowed"
        )
    return clean


def _mission_dir(state_root: Path, mission_id: str) -> Path:
    root = state_root.expanduser().resolve()
    mission_dir = root / _validate_mission_id(mission_id)
    resolved = mission_dir.resolve(strict=False)
    if resolved != root and root not in resolved.parents:
        raise ValueError(
            "mission_id resolves outside state root; symlinked mission directories are not allowed"
        )
    return mission_dir


def _receipt_path(mission_dir: Path) -> Path:
    return mission_dir / "receipts.jsonl"


def _append_receipt(mission_dir: Path, receipt: dict[str, Any]) -> dict[str, Any]:
    receipts = _jsonl_rows(_receipt_path(mission_dir))
    row = {
        "schema_version": SCHEMA_VERSION,
        "created_at": utc_now(),
        **receipt,
        "previous_record_hash": str(receipts[-1].get("record_hash") or "") if receipts else "",
        "record_hash": "",
    }
    row["record_hash"] = stable_payload_hash(row)
    _append_jsonl(_receipt_path(mission_dir), row)
    return row


def _read_mission(mission_dir: Path) -> dict[str, Any]:
    path = mission_dir / "mission.json"
    if not path.exists():
        raise FileNotFoundError(f"mission file missing: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _tasks_path(mission_dir: Path) -> Path:
    return mission_dir / "tasks.jsonl"


def _first_open_task(tasks: list[dict[str, Any]]) -> dict[str, Any] | None:
    for task in tasks:
        if task.get("kernel_result_ref"):
            continue
        if str(task.get("status") or "") in {"cancelled", "closed", "completed"}:
            continue
        return task
    return None


def _common_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--state-root", type=Path, default=DEFAULT_STATE_ROOT)
    parser.add_argument("--kernel-store", type=Path, default=DEFAULT_KERNEL_STORE)
    parser.add_argument(
        "--runtime-db",
        type=Path,
        default=None,
        help=(
            "RuntimeStateStore database path. Defaults to ~/.dharma/state/runtime.db "
            "when using the default state root; otherwise uses <state-root>/.runtime/runtime.db."
        ),
    )
    parser.add_argument("--agent-uid", default="codex_composer")
    parser.add_argument("--json", action="store_true")


def _runtime_db_path(args: argparse.Namespace) -> Path:
    if args.runtime_db is not None:
        return args.runtime_db.expanduser()
    state_root = args.state_root.expanduser().resolve()
    if state_root == DEFAULT_STATE_ROOT.expanduser().resolve():
        return runtime_db_path_from_env()
    return state_root / ".runtime" / "runtime.db"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    init = sub.add_parser("init", help="Create or reuse a ds-goal mission ledger.")
    _common_options(init)
    init.add_argument("--goal", required=True)
    init.add_argument("--mission-id", default="")
    init.add_argument("--title", default="")
    init.add_argument("--role", default="planner")
    init.add_argument("--allowed-write", action="append", default=[])
    init.add_argument("--verifier-command", default="")

    status = sub.add_parser("status", help="Print mission/task/kernel status.")
    _common_options(status)
    status.add_argument("--mission-id", required=True)
    status.add_argument("--latest-limit", type=int, default=20)
    status.add_argument("--board-cards", action="store_true", help="Include read-only BoardStore Card projection.")

    run = sub.add_parser("run", help="Run a bounded LivingAgentKernel tick for one ds-goal mission.")
    _common_options(run)
    run.add_argument("--mission-id", required=True)
    run.add_argument("--max-wakes", type=int, default=1)
    run.add_argument("--lease-seconds", type=int, default=300)
    run.add_argument("--duration-hours", type=float, default=0.0)
    run.add_argument("--dispatch-mode", default="bounded-kernel-tick")
    run.add_argument("--dry-run", action="store_true")

    return parser


def cmd_init(args: argparse.Namespace) -> int:
    mission_id = args.mission_id or _slug(args.goal)
    mission_dir = _mission_dir(args.state_root, mission_id)
    mission_path = mission_dir / "mission.json"
    tasks_path = _tasks_path(mission_dir)
    created = not mission_path.exists()
    mission = {
        "schema_version": SCHEMA_VERSION,
        "mission_id": mission_id,
        "goal": args.goal,
        "title": args.title or args.goal.splitlines()[0][:120],
        "created_at": utc_now(),
        "state_root": str(args.state_root.expanduser()),
        "kernel_store": str(args.kernel_store.expanduser()),
        "source": "ds-goal compatibility CLI",
    }
    if created:
        _write_json(mission_path, mission)
    else:
        mission = _read_mission(mission_dir)

    if not tasks_path.exists():
        task_id = f"{mission_id}-t01"
        task = {
            "schema": "dharma.autonomy_task.v1",
            "mission_id": mission_id,
            "task_id": task_id,
            "role": args.role,
            "agent_uid": args.agent_uid,
            "title": args.title or args.goal,
            "status": "claimed",
            "allowed_writes": list(args.allowed_write or []),
            "verifier_command": args.verifier_command,
            "lease": {
                "claimed_by": args.agent_uid,
                "claimed_at": utc_now(),
                "expires_at": "",
            },
            "return_address": f"autonomy://{mission_id}/{task_id}",
            "requested_tools": ["session_status"],
            "tool_calls": [{"name": "session_status", "arguments": {}}],
            "receipt_required": True,
        }
        _append_jsonl(tasks_path, task)

    tasks = _jsonl_rows(tasks_path)
    receipt = _append_receipt(
        mission_dir,
        {
            "event": "ds_goal_init",
            "status": "created" if created else "exists",
            "mission_id": mission_id,
            "mission_path": str(mission_path),
            "tasks_path": str(tasks_path),
            "task_count": len(tasks),
        },
    )
    _print(
        {
            "status": receipt["status"],
            "mission_id": mission_id,
            "mission_dir": str(mission_dir),
            "mission_path": str(mission_path),
            "tasks_path": str(tasks_path),
            "receipt_path": str(_receipt_path(mission_dir)),
            "receipt_hash": receipt["record_hash"],
            "task_count": len(tasks),
            "mission": mission,
        },
        as_json=args.json,
    )
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    mission_dir = _mission_dir(args.state_root, args.mission_id)
    try:
        mission = _read_mission(mission_dir)
    except FileNotFoundError as exc:
        _print({"status": "missing", "mission_id": args.mission_id, "error": str(exc)}, as_json=args.json)
        return 2
    tasks = _jsonl_rows(_tasks_path(mission_dir))
    store = KernelRunStore(args.kernel_store)
    payload = {
        "status": "ok",
        "mission_id": args.mission_id,
        "mission_dir": str(mission_dir),
        "mission": mission,
        "tasks": tasks,
        "task_count": len(tasks),
        "open_task_count": sum(1 for task in tasks if not task.get("kernel_result_ref")),
        "latest_wake_status": store.latest_wake_status(limit=args.latest_limit),
        "runtime_db": str(_runtime_db_path(args)),
    }
    if args.board_cards:
        payload["board_cards"] = [
            card.model_dump(mode="json")
            for card in load_ds_goal_cards(args.state_root, mission_id=args.mission_id)
        ]
    _print(payload, as_json=args.json)
    return 0


def _now_dt() -> datetime:
    return datetime.now(UTC).replace(microsecond=0)


def _kernel_result_artifact_path(mission_dir: Path, wake_id: str) -> Path:
    return mission_dir / "kernel_results" / f"{wake_id}.json"


def _task_claim_id(mission_id: str, task_id: str) -> str:
    return f"dsgoal-{mission_id}-{task_id}-claim"[:96]


def _runtime_identity_for_ds_goal(
    *,
    mission_id: str,
    task_id: str,
    agent_uid: str,
    wake_id: str,
    kernel_run_id: str,
    claim_id: str,
    artifact_id: str,
) -> ExecutionIdentity:
    trace_id = stable_payload_hash(
        {"surface": "ds-goal", "mission_id": mission_id, "task_id": task_id}
    ).replace("sha256:", "trace_", 1)[:32]
    correlation_id = f"ds_goal:{mission_id}:{task_id}"
    return ExecutionIdentity(
        trace_id=trace_id,
        correlation_id=correlation_id,
        task_id=task_id,
        run_id=kernel_run_id,
        claim_id=claim_id,
        idempotency_key=f"idem_ds_goal:{mission_id}:{task_id}",
        agent_id=agent_uid,
        session_id=f"ds_goal:{mission_id}",
        message_id=wake_id,
        artifact_id=artifact_id,
        metadata={
            "mission_id": mission_id,
            "source": "scripts/runtime/autonomy_spine.py",
        },
    )


def _runtime_run_id_for_ds_goal(mission_id: str, task_id: str) -> str:
    digest = stable_payload_hash(
        {"surface": "ds-goal", "mission_id": mission_id, "task_id": task_id}
    ).replace("sha256:", "", 1)
    return f"run_ds_goal_{digest[:24]}"


def _runtime_operation_hash_for_ds_goal(mission_id: str, task_id: str) -> str:
    return stable_payload_hash(
        {
            "surface": "ds-goal",
            "operation": "run",
            "mission_id": mission_id,
            "task_id": task_id,
        }
    )


def _begin_runtime_truth_for_dispatch(
    *,
    args: argparse.Namespace,
    task: dict[str, Any],
    wake_id: str,
) -> dict[str, Any]:
    started_at = datetime.now(UTC)
    task_id = str(task.get("task_id") or task.get("id") or "")
    mission_id = _validate_mission_id(str(args.mission_id))
    claim_id = _task_claim_id(mission_id, task_id)
    run_id = _runtime_run_id_for_ds_goal(mission_id, task_id)
    artifact_id = f"artifact_ds_goal_{mission_id}_{task_id}_{wake_id}".replace("-", "_")[:128]
    side_effect_key = f"ds_goal.run:{mission_id}:{task_id}"
    identity = _runtime_identity_for_ds_goal(
        mission_id=mission_id,
        task_id=task_id,
        agent_uid=args.agent_uid,
        wake_id=wake_id,
        kernel_run_id=run_id,
        claim_id=claim_id,
        artifact_id=artifact_id,
    )
    metadata = {
        **identity.to_metadata(),
        "mission_id": mission_id,
        "task_id": task_id,
        "wake_id": wake_id,
        "trace_id": identity.trace_id,
        "correlation_id": identity.correlation_id,
        "run_id": identity.run_id,
        "runtime_run_id": identity.run_id,
        "claim_id": identity.claim_id,
        "idempotency_key": identity.idempotency_key,
        "agent_id": identity.agent_id,
        "session_id": identity.session_id,
        "operation_hash": _runtime_operation_hash_for_ds_goal(mission_id, task_id),
    }
    store = RuntimeStateStore(_runtime_db_path(args))
    existing_idempotency = store.get_idempotency_record_sync(identity.idempotency_key, side_effect_key)
    if existing_idempotency is None:
        store.record_execution_identity_sync(identity, source="ds_goal.autonomy_spine", metadata=metadata)
    inserted = store.try_begin_idempotent_side_effect_sync(
        identity,
        side_effect_key,
        metadata=metadata,
        stale_after_seconds=max(int(args.lease_seconds), 1),
    )
    return {
        "store": store,
        "identity": identity,
        "side_effect_key": side_effect_key,
        "metadata": metadata,
        "idempotency_inserted": inserted,
        "artifact_id": artifact_id,
        "started_at": started_at,
    }


def _issue_runtime_warrant_for_kernel_wake(runtime_dispatch: dict[str, Any]) -> dict[str, Any]:
    warrant = issue_runtime_warrant(
        store=runtime_dispatch["store"],
        identity=runtime_dispatch["identity"],
        surface="scripts/runtime/autonomy_spine.py",
        action="kernel_wake",
        side_effect_key=str(runtime_dispatch["side_effect_key"]),
        idempotency_inserted=bool(runtime_dispatch["idempotency_inserted"]),
        requested_claims=("kernel_wake_attempt", "runtime_receipt_pending"),
        metadata={
            **dict(runtime_dispatch["metadata"]),
            "warrant_scope": "pre_kernel_wake_permission",
            "claim_boundary": "wake attempt only; done/completed requires kernel closeback receipt",
        },
    )
    return warrant.to_ref()


def _complete_denied_runtime_dispatch(
    *,
    runtime_dispatch: dict[str, Any],
    warrant_ref: dict[str, Any],
    reason: str,
) -> None:
    identity = runtime_dispatch["identity"]
    runtime_dispatch["store"].complete_idempotent_side_effect_sync(
        identity,
        str(runtime_dispatch["side_effect_key"]),
        status="failed",
        result_receipt_id=str(warrant_ref.get("receipt_id") or ""),
        metadata={
            **dict(runtime_dispatch["metadata"]),
            "runtime_warrant_ref": warrant_ref,
            "blocked_reason": reason,
        },
    )


def _evidence_receipt_ref(receipt: EvidenceReceipt) -> dict[str, Any]:
    return {
        "receipt_id": str(receipt.receipt_id),
        "trace_id": receipt.trace_id,
        "span_id": receipt.span_id,
        "task_id": receipt.task_id,
        "operation": receipt.operation,
        "status": receipt.status,
    }


def _build_kernel_wake_evidence_receipt(
    *,
    runtime_dispatch: dict[str, Any],
    mission_id: str,
    wake_id: str,
    runtime_status: str,
    kernel_status: str,
    receipt_hash: str,
) -> EvidenceReceipt:
    identity = runtime_dispatch["identity"]
    finished_at = datetime.now(UTC)
    started_at = runtime_dispatch.get("started_at")
    if not isinstance(started_at, datetime):
        started_at = finished_at
    if runtime_status == "completed":
        evidence_status = "ok"
        error_source = "none"
        error_detail = None
    elif runtime_status == "failed":
        evidence_status = "failed"
        error_source = "provider_failed"
        error_detail = kernel_status
    else:
        evidence_status = "dropped"
        error_source = "guardrail_blocked"
        error_detail = kernel_status
    warrant_ref = runtime_dispatch.get("runtime_warrant_ref")
    warrant_ref = warrant_ref if isinstance(warrant_ref, dict) else {}
    attributes = {
        "correlation_id": identity.correlation_id,
        "mission_id": mission_id,
        "wake_id": wake_id,
        "kernel_status": kernel_status,
        "ds_goal_receipt_hash": receipt_hash,
        "idempotency_key": identity.idempotency_key,
        "side_effect_key": str(runtime_dispatch["side_effect_key"]),
        "runtime_warrant_receipt_id": str(warrant_ref.get("receipt_id") or ""),
    }
    return EvidenceReceipt(
        trace_id=identity.trace_id,
        span_id=identity.run_id,
        parent_span_id=identity.parent_run_id or None,
        context_id=identity.session_id,
        task_id=identity.task_id,
        claim_id=identity.claim_id or None,
        agent_id=identity.agent_id,
        provider="living_agent_kernel",
        operation="ds_goal.kernel_wake",
        provider_attempted=True,
        status=evidence_status,
        error_source=error_source,
        error_detail=error_detail,
        started_at=started_at,
        finished_at=finished_at,
        latency_ms=int((finished_at - started_at).total_seconds() * 1000),
        attributes=attributes,
    )


def _write_kernel_result_artifact(path: Path, payload: dict[str, Any]) -> None:
    _write_json(path, payload)


def _record_runtime_truth_for_run(
    *,
    args: argparse.Namespace,
    mission_dir: Path,
    task: dict[str, Any],
    tick_payload: dict[str, Any],
    receipt_hash: str,
    wake_id: str,
    runtime_dispatch: dict[str, Any],
) -> dict[str, Any]:
    task_id = str(task.get("task_id") or task.get("id") or "")
    mission_id = str(args.mission_id)
    closebacks = tick_payload.get("closebacks") if isinstance(tick_payload.get("closebacks"), list) else []
    first_closeback = closebacks[0] if closebacks and isinstance(closebacks[0], dict) else {}
    kernel_result = first_closeback.get("result_ref") if isinstance(first_closeback.get("result_ref"), dict) else {}
    kernel_result_run_id = str(kernel_result.get("run_id") or "")
    kernel_status = str(kernel_result.get("status") or tick_payload.get("status") or "completed")
    runtime_status = "completed" if kernel_status == "completed" else ("failed" if kernel_status == "failed" else "blocked")
    identity = runtime_dispatch["identity"]
    claim_id = identity.claim_id
    artifact_id = str(runtime_dispatch["artifact_id"])
    side_effect_key = str(runtime_dispatch["side_effect_key"])
    artifact_path = _kernel_result_artifact_path(mission_dir, wake_id)
    artifact_payload = {
        "schema_version": "dharma.ds_goal_kernel_result_artifact.v1",
        "mission_id": mission_id,
        "task_id": task_id,
        "wake_id": wake_id,
        "kernel_result": kernel_result,
        "tick": tick_payload,
        "ds_goal_receipt_hash": receipt_hash,
    }
    _write_kernel_result_artifact(artifact_path, artifact_payload)
    artifact_checksum = stable_payload_hash(artifact_payload)
    evidence_receipt = _build_kernel_wake_evidence_receipt(
        runtime_dispatch=runtime_dispatch,
        mission_id=mission_id,
        wake_id=wake_id,
        runtime_status=runtime_status,
        kernel_status=kernel_status,
        receipt_hash=receipt_hash,
    )
    evidence_ref = _evidence_receipt_ref(evidence_receipt)
    runtime_dispatch["spine_evidence_receipt_ref"] = evidence_ref
    metadata = {
        **dict(runtime_dispatch["metadata"]),
        "mission_id": mission_id,
        "ds_goal_receipt_hash": receipt_hash,
        "wake_id": wake_id,
        "kernel_result_run_id": kernel_result_run_id,
        "runtime_warrant_ref": runtime_dispatch.get("runtime_warrant_ref"),
        "spine_evidence_receipt_ref": evidence_ref,
    }
    store = runtime_dispatch["store"]
    store.record_execution_identity_sync(identity, source="ds_goal.autonomy_spine", metadata=metadata)
    now = _now_dt()
    stale_after = now + timedelta(seconds=max(int(args.lease_seconds), 1))
    store.create_task_claim_sync(
        TaskClaim(
            claim_id=claim_id,
            task_id=task_id,
            agent_id=args.agent_uid,
            status=runtime_status,
            session_id=f"ds_goal:{mission_id}",
            claimed_at=now,
            acked_at=now,
            heartbeat_at=now,
            stale_after=stale_after,
            metadata=metadata,
        )
    )
    store.create_delegation_run_sync(
        DelegationRun(
            run_id=identity.run_id,
            task_id=task_id,
            assigned_to=args.agent_uid,
            status=runtime_status,
            session_id=f"ds_goal:{mission_id}",
            claim_id=claim_id,
            assigned_by="ds-goal",
            requested_output=["kernel_result", "ds_goal_receipt", "runtime_truth_projection"],
            current_artifact_id=artifact_id,
            started_at=now,
            completed_at=now,
            failure_code="" if runtime_status == "completed" else kernel_status,
            metadata=metadata,
        )
    )
    asyncio.run(
        store.record_artifact(
            ArtifactRecord(
                artifact_id=artifact_id,
                artifact_kind="ds_goal_kernel_result",
                session_id=f"ds_goal:{mission_id}",
                task_id=task_id,
                run_id=identity.run_id,
                trace_id=identity.trace_id,
                manifest_path=str(mission_dir / "mission.json"),
                payload_path=str(artifact_path),
                checksum=artifact_checksum,
                promotion_state="ephemeral",
                metadata=metadata,
            )
        )
    )
    inserted = bool(runtime_dispatch["idempotency_inserted"])
    final_receipt_id = f"rr_{identity.run_id}_ds_goal_{runtime_status}"
    store.complete_idempotent_side_effect_sync(
        identity,
        side_effect_key,
        status=runtime_status,
        result_receipt_id=final_receipt_id,
        metadata={**metadata, "idempotency_inserted": inserted},
    )
    final_receipt = store.record_runtime_receipt_sync(
        RuntimeReceipt(
            receipt_id=final_receipt_id,
            receipt_type="delegation_run",
            status=runtime_status,
            run_id=identity.run_id,
            task_id=identity.task_id,
            trace_id=identity.trace_id,
            correlation_id=identity.correlation_id,
            causation_id=identity.causation_id,
            parent_run_id=identity.parent_run_id,
            agent_id=identity.agent_id,
            idempotency_key=identity.idempotency_key,
            side_effect_key=side_effect_key,
            payload={
                **metadata,
                "kernel_status": kernel_status,
                "kernel_result_run_id": kernel_result_run_id,
                "artifact_id": artifact_id,
                "artifact_path": str(artifact_path),
                "spine_evidence_receipt": evidence_receipt.to_dict(),
            },
            created_at=_now_dt(),
        )
    )
    return {
        "runtime_db": str(_runtime_db_path(args)),
        "run_id": identity.run_id,
        "task_id": identity.task_id,
        "mission_id": mission_id,
        "claim_id": claim_id,
        "artifact_id": artifact_id,
        "artifact_path": str(artifact_path),
        "idempotency_key": identity.idempotency_key,
        "side_effect_key": side_effect_key,
        "idempotency_inserted": inserted,
        "receipt_id": final_receipt.receipt_id,
        "receipt_status": final_receipt.status,
        "runtime_warrant_ref": runtime_dispatch.get("runtime_warrant_ref"),
        "spine_evidence_receipt_ref": evidence_ref,
    }


def cmd_run(args: argparse.Namespace) -> int:
    mission_dir = _mission_dir(args.state_root, args.mission_id)
    try:
        _read_mission(mission_dir)
    except FileNotFoundError as exc:
        _print({"status": "missing", "mission_id": args.mission_id, "error": str(exc)}, as_json=args.json)
        return 2
    tasks = _jsonl_rows(_tasks_path(mission_dir))
    task = _first_open_task(tasks)
    if task is None:
        receipt = _append_receipt(
            mission_dir,
            {
                "event": "ds_goal_run",
                "status": "idle",
                "mission_id": args.mission_id,
                "reason": "no_open_task_without_kernel_result_ref",
            },
        )
        _print({"status": "idle", "mission_id": args.mission_id, "receipt_hash": receipt["record_hash"]}, as_json=args.json)
        return 0

    receipt_base = {
        "event": "ds_goal_run",
        "mission_id": args.mission_id,
        "task_id": str(task.get("task_id") or task.get("id") or ""),
        "duration_hours_requested": args.duration_hours,
        "dispatch_mode_requested": args.dispatch_mode,
        "bounded_max_wakes": max(0, min(int(args.max_wakes), 50)),
    }
    if args.dry_run:
        receipt = _append_receipt(mission_dir, {**receipt_base, "status": "dry_run"})
        _print(
            {
                "status": "dry_run",
                "mission_id": args.mission_id,
                "task_id": receipt_base["task_id"],
                "mission_dir": str(mission_dir),
                "receipt_hash": receipt["record_hash"],
            },
            as_json=args.json,
        )
        return 0

    wake_id = f"dsgoal-{args.mission_id}-{uuid4().hex[:8]}"
    runtime_dispatch = _begin_runtime_truth_for_dispatch(
        args=args,
        task=task,
        wake_id=wake_id,
    )
    if not runtime_dispatch["idempotency_inserted"]:
        receipt = _append_receipt(
            mission_dir,
            {
                **receipt_base,
                "status": "duplicate",
                "wake_id": wake_id,
                "runtime_run_id": runtime_dispatch["identity"].run_id,
                "idempotency_key": runtime_dispatch["identity"].idempotency_key,
                "side_effect_key": runtime_dispatch["side_effect_key"],
                "reason": "idempotency_record_already_exists",
            },
        )
        _print(
            {
                "status": "duplicate",
                "mission_id": args.mission_id,
                "task_id": receipt_base["task_id"],
                "wake_id": wake_id,
                "mission_dir": str(mission_dir),
                "receipt_hash": receipt["record_hash"],
                "runtime_truth_ref": {
                    "runtime_db": str(_runtime_db_path(args)),
                    "run_id": runtime_dispatch["identity"].run_id,
                    "task_id": runtime_dispatch["identity"].task_id,
                    "mission_id": args.mission_id,
                    "idempotency_key": runtime_dispatch["identity"].idempotency_key,
                    "side_effect_key": runtime_dispatch["side_effect_key"],
                    "idempotency_inserted": False,
                },
            },
            as_json=args.json,
        )
        return 0

    try:
        runtime_dispatch["runtime_warrant_ref"] = _issue_runtime_warrant_for_kernel_wake(runtime_dispatch)
    except RuntimeWarrantDenied as exc:
        warrant_ref = exc.warrant.to_ref() if exc.warrant is not None else {}
        _complete_denied_runtime_dispatch(
            runtime_dispatch=runtime_dispatch,
            warrant_ref=warrant_ref,
            reason=str(exc),
        )
        receipt = _append_receipt(
            mission_dir,
            {
                **receipt_base,
                "status": "warrant_denied",
                "wake_id": wake_id,
                "runtime_run_id": runtime_dispatch["identity"].run_id,
                "idempotency_key": runtime_dispatch["identity"].idempotency_key,
                "side_effect_key": runtime_dispatch["side_effect_key"],
                "runtime_warrant_ref": warrant_ref,
                "reason": str(exc),
            },
        )
        _print(
            {
                "status": "warrant_denied",
                "mission_id": args.mission_id,
                "task_id": receipt_base["task_id"],
                "wake_id": wake_id,
                "mission_dir": str(mission_dir),
                "receipt_hash": receipt["record_hash"],
                "runtime_truth_ref": {
                    "runtime_db": str(_runtime_db_path(args)),
                    "run_id": runtime_dispatch["identity"].run_id,
                    "task_id": runtime_dispatch["identity"].task_id,
                    "mission_id": args.mission_id,
                    "idempotency_key": runtime_dispatch["identity"].idempotency_key,
                    "side_effect_key": runtime_dispatch["side_effect_key"],
                    "idempotency_inserted": True,
                    "runtime_warrant_ref": warrant_ref,
                },
            },
            as_json=args.json,
        )
        return 2

    kernel = LivingAgentKernel(
        store=KernelRunStore(args.kernel_store),
        workspace_root=ROOT,
    )
    kernel.enqueue_source_wake("ds_goal", task, agent_uid=args.agent_uid, wake_id=wake_id)
    tick = kernel.run_control_tick(
        lease_owner=args.agent_uid,
        lease_seconds=args.lease_seconds,
        max_wakes=args.max_wakes,
        source_roots={"ds_goal": args.state_root},
    )
    tick_payload = tick.model_dump(mode="json")
    receipt = _append_receipt(
        mission_dir,
        {
            **receipt_base,
            "status": tick.status,
            "wake_id": wake_id,
            "tick": tick_payload,
        },
    )
    runtime_truth_ref = _record_runtime_truth_for_run(
        args=args,
        mission_dir=mission_dir,
        task=task,
        tick_payload=tick_payload,
        receipt_hash=str(receipt["record_hash"]),
        wake_id=wake_id,
        runtime_dispatch=runtime_dispatch,
    )
    _print(
        {
            "status": tick.status,
            "mission_id": args.mission_id,
            "task_id": receipt_base["task_id"],
            "wake_id": wake_id,
            "mission_dir": str(mission_dir),
            "receipt_hash": receipt["record_hash"],
            "tick": tick_payload,
            "runtime_truth_ref": runtime_truth_ref,
        },
        as_json=args.json,
    )
    return 0 if tick.status in {"idle", "completed", "review", "blocked"} else 1


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "init":
            return cmd_init(args)
        if args.command == "status":
            return cmd_status(args)
        if args.command == "run":
            return cmd_run(args)
    except ValueError as exc:
        _print({"status": "invalid", "error": str(exc)}, as_json=getattr(args, "json", False))
        return 2
    raise AssertionError(f"unhandled command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
