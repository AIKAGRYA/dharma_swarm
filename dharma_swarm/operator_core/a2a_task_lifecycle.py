"""A2A task lifecycle helpers.

Receipts may differ by closure layer.  Correlation identity must not.

This module owns the narrow, file-native contract for closing tasks on the
existing ``~/.dharma/a2a_bus/tasks/queue.jsonl`` surface.  It does not create a
new bus, dispatcher, authority layer, or runtime.  It gives persistent-agent
wake scripts one shared way to claim a task and prove closure with a receipt.

Correlation spine convention (declared, not yet enforced via lint):
  - A2ATaskReceipt        (this module — request/response layer)
  - SpineEvidenceReceipt  (spine/receipt.py — dispatch/invocation layer)
  - ClosureEvidenceReceipt (closure_v0 — test/work-packet layer)
  All link by ``correlation_id``, never by inheritance.
"""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import tempfile
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator, Literal

from dharma_swarm.daemon_config import dharma_state_dir
from dharma_swarm.operator_core.return_address import build_return_address

TaskStatus = Literal["pending", "open", "ready", "claimed", "completed", "failed", "blocked"]
CloseStatus = Literal["completed", "failed", "blocked"]

OPEN_STATUSES = {"pending", "open", "ready"}
CLOSED_STATUSES = {"completed", "failed", "blocked", "done", "closed", "cancelled"}
VALID_CLOSE_STATUSES = {"completed", "failed", "blocked"}
RETURN_ADDRESS_REQUIRED_KEYS = {"resume_surface", "resume_ref", "obligation", "base_case"}


class A2ATaskLifecycleError(RuntimeError):
    """Raised when a task lifecycle mutation is unsafe or invalid."""


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def iso_now() -> str:
    return utc_now().isoformat()


def short_hash(value: str, length: int = 16) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:length]


def _content_hash(payload: dict[str, Any]) -> str:
    stable = {key: value for key, value in payload.items() if key != "content_hash"}
    encoded = json.dumps(stable, ensure_ascii=True, sort_keys=True, default=str)
    return f"sha256:{hashlib.sha256(encoded.encode('utf-8')).hexdigest()}"


def default_state_root() -> Path:
    return dharma_state_dir("DHARMA_STATE_DIR", "DHARMA_HOME")


def queue_path(state_root: Path | str | None = None) -> Path:
    root = Path(state_root) if state_root is not None else default_state_root()
    return root / "a2a_bus" / "tasks" / "queue.jsonl"


def inbox_dir(agent_uid: str, state_root: Path | str | None = None) -> Path:
    root = Path(state_root) if state_root is not None else default_state_root()
    return root / "a2a_bus" / "inboxes" / agent_uid


def make_return_address(
    *,
    agent_uid: str,
    resume_surface: str = "a2a_task_queue",
    resume_ref: str,
    obligation: str = "close_task_with_receipt",
    base_case: str = "status in completed|failed|blocked with valid receipt",
    depth: int = 0,
    trace_id: str | None = None,
) -> dict[str, Any]:
    """Build the minimal recursive return-address object.

    The return address is intentionally boring: it tells the next wake loop
    where to resume, what obligation remains, and what counts as a base case.
    """

    return build_return_address(
        agent_uid=agent_uid,
        resume_surface=resume_surface,
        resume_ref=resume_ref,
        obligation=obligation,
        base_case=base_case,
        depth=depth,
        trace_id=trace_id,
    )


def build_task_receipt(
    *,
    task_id: str,
    agent_uid: str,
    status: CloseStatus,
    summary: str,
    correlation_id: str | None = None,
    artifacts: list[str | dict[str, Any]] | None = None,
    return_address: dict[str, Any] | None = None,
    model_identity: str | None = None,
    harness: str | None = None,
    authority: str | None = None,
    evidence: dict[str, Any] | None = None,
    evaluation: dict[str, Any] | None = None,
    next_wake_hint: str | None = None,
    duration_ms: float | None = None,
    replay_command: str | None = None,
    spine_receipt_id: str | None = None,
    completion_via: str = "dharma_swarm.operator_core.a2a_task_lifecycle",
    failure_reason: str | None = None,
    timestamp: str | None = None,
) -> dict[str, Any]:
    """Build a CWT/GEPA-readable closure receipt for an A2A task.

    Phase 2A additions (pure additive, backwards compatible):
        correlation_id: Cross-layer trace identity. Required for three-layer
            receipt chain (A2A → spine → closure_v0). If provided, stamped
            into every receipt. Chains to spine.EvidenceReceipt.trace_id.
        duration_ms: Wall-clock time from task submission to completion.
        replay_command: Shell command to reproduce this task invocation.
        spine_receipt_id: Optional pointer to the spine.EvidenceReceipt
            that captured the dispatch invocation. Enables bi-directional
            chain navigation without log scanning.
    """

    ts = timestamp or iso_now()
    receipt: dict[str, Any] = {
        "schema_version": "dharma_a2a_task_receipt.v1",
        "receipt_id": f"a2a-task-receipt:{task_id}:{short_hash(agent_uid + status + ts, 12)}",
        "timestamp": ts,
        "created_at": ts,
        "closed_at": ts,
        "task_id": task_id,
        "agent_uid": agent_uid,
        "status": status,
        "summary": summary,
        "receipt_summary": summary,
        "completion_via": completion_via,
        "artifacts": artifacts or [],
        "evaluation": evaluation
        or {
            "overall_verdict": "not_checked",
            "criteria_results": [],
            "gate_results": [],
        },
        "return_address": return_address
        or make_return_address(agent_uid=agent_uid, resume_ref=f"a2a_task:{task_id}"),
    }
    if model_identity:
        receipt["model_identity"] = model_identity
    if harness:
        receipt["harness"] = harness
    if authority:
        receipt["authority"] = authority
    if evidence:
        receipt["evidence"] = evidence
    if next_wake_hint:
        receipt["next_wake_hint"] = next_wake_hint
    if correlation_id:
        receipt["correlation_id"] = correlation_id
    if duration_ms is not None:
        receipt["duration_ms"] = duration_ms
    if replay_command:
        receipt["replay_command"] = replay_command
    if spine_receipt_id:
        receipt["spine_receipt_id"] = spine_receipt_id
    if status in {"failed", "blocked"}:
        receipt["failure_reason"] = failure_reason or "not specified"
    receipt["content_hash"] = _content_hash(receipt)
    return receipt


def _read_queue_entries(path: Path) -> list[tuple[str | None, dict[str, Any] | None]]:
    if not path.exists():
        return []
    entries: list[tuple[str | None, dict[str, Any] | None]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        try:
            value = json.loads(stripped)
        except json.JSONDecodeError:
            entries.append((stripped, None))
            continue
        entries.append((None, value if isinstance(value, dict) else None))
    return entries


def _write_queue_entries(path: Path, entries: list[tuple[str | None, dict[str, Any] | None]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines: list[str] = []
    for raw, row in entries:
        if row is not None:
            lines.append(json.dumps(row, ensure_ascii=True, sort_keys=True))
        elif raw:
            lines.append(raw)
    payload = "\n".join(lines) + ("\n" if lines else "")
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=str(path.parent), delete=False) as handle:
        tmp = Path(handle.name)
        handle.write(payload)
    tmp.replace(path)


@contextmanager
def _queue_lock(path: Path) -> Iterator[None]:
    """Serialize read-modify-write on the queue via an exclusive advisory lock.

    Two concurrent workers must not both claim (or both close) the same task.
    ``claim_task``/``close_task`` do read -> mutate -> write, and the writer
    replaces the queue file by atomic rename (swapping the inode), so a lock
    taken on the queue file itself would not exclude a claimant that opened it
    after the rename. We therefore lock a stable sidecar file that is never
    renamed, so every contender contends on the same inode. ``flock`` is
    per-open-file-description, so independent ``os.open`` calls exclude one
    another even within a single process (thread-vs-thread), which is exactly
    the double-claim case this guards.
    """

    path.parent.mkdir(parents=True, exist_ok=True)
    lock_path = path.with_name(path.name + ".lock")
    fd = os.open(str(lock_path), os.O_CREAT | os.O_RDWR, 0o644)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        yield
    finally:
        fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)


def _find_task(
    entries: list[tuple[str | None, dict[str, Any] | None]],
    task_id: str,
) -> dict[str, Any]:
    for _, row in entries:
        if row is not None and str(row.get("id") or "") == task_id:
            return row
    raise A2ATaskLifecycleError(f"A2A task not found: {task_id}")


def _status(row: dict[str, Any]) -> str:
    return str(row.get("status") or "pending").lower()


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tmp.replace(path)


def _artifact_path(value: str | dict[str, Any]) -> str | None:
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        candidate = value.get("path") or value.get("file") or value.get("artifact_path")
        return str(candidate) if candidate else None
    return None


def validate_task_receipt(
    receipt: Any,
    *,
    task_id: str | None = None,
    agent_uid: str | None = None,
    status: CloseStatus | None = None,
    require_artifact_or_evidence: bool = False,
) -> dict[str, Any]:
    """Return a machine-readable validation result for an A2A receipt."""

    errors: list[str] = []
    warnings: list[str] = []
    if not isinstance(receipt, dict):
        return {"valid": False, "errors": ["receipt must be an object"], "warnings": []}

    for key in (
        "schema_version",
        "receipt_id",
        "timestamp",
        "created_at",
        "closed_at",
        "content_hash",
        "task_id",
        "agent_uid",
        "status",
        "summary",
        "receipt_summary",
        "completion_via",
        "evaluation",
        "return_address",
    ):
        if not receipt.get(key):
            errors.append(f"missing required receipt field: {key}")

    schema = str(receipt.get("schema_version") or "")
    if schema and schema != "dharma_a2a_task_receipt.v1":
        errors.append("schema_version must be dharma_a2a_task_receipt.v1")
    content_hash = str(receipt.get("content_hash") or "")
    if content_hash and content_hash != _content_hash(receipt):
        errors.append("content_hash does not match receipt payload")

    receipt_status = str(receipt.get("status") or "").lower()
    if receipt_status and receipt_status not in VALID_CLOSE_STATUSES:
        errors.append(f"receipt status must be one of {sorted(VALID_CLOSE_STATUSES)}")
    if receipt_status in {"failed", "blocked"} and not receipt.get("failure_reason"):
        errors.append("failure_reason is required for failed or blocked receipts")
    if status is not None and receipt_status != status:
        errors.append(f"receipt status {receipt_status!r} does not match expected {status!r}")
    if task_id is not None and str(receipt.get("task_id") or "") != task_id:
        errors.append(f"receipt task_id does not match {task_id}")
    if agent_uid is not None and str(receipt.get("agent_uid") or "") != agent_uid:
        errors.append(f"receipt agent_uid does not match {agent_uid}")

    return_address = receipt.get("return_address")
    if not isinstance(return_address, dict):
        errors.append("return_address must be an object")
    else:
        missing = sorted(RETURN_ADDRESS_REQUIRED_KEYS - set(return_address))
        if missing:
            errors.append(f"return_address missing required keys: {', '.join(missing)}")
        depth = return_address.get("depth", 0)
        if not isinstance(depth, int):
            errors.append("return_address.depth must be an integer")
        elif depth < 0 or depth > 8:
            errors.append("return_address.depth must be between 0 and 8")

    artifacts = receipt.get("artifacts") or []
    if not isinstance(artifacts, list):
        errors.append("artifacts must be a list")
        artifacts = []
    missing_artifacts: list[str] = []
    for item in artifacts:
        artifact = _artifact_path(item)
        if not artifact:
            warnings.append("artifact entry has no path-like value")
            continue
        if artifact.startswith(("http://", "https://")):
            continue
        if not Path(artifact).expanduser().exists():
            missing_artifacts.append(artifact)
    if missing_artifacts:
        errors.append(f"artifact path(s) do not exist: {', '.join(missing_artifacts)}")

    has_evidence = bool(receipt.get("evidence") or receipt.get("evaluation"))
    if require_artifact_or_evidence and not artifacts and not has_evidence:
        errors.append("receipt must include at least one artifact, evidence, or evaluation block")

    return {"valid": not errors, "errors": errors, "warnings": warnings}


def _mirror_claimed_task(
    task: dict[str, Any],
    agent_uid: str,
    state_root: Path | str | None,
    delivered_at: str,
) -> Path:
    task_id = str(task.get("id") or short_hash(json.dumps(task, sort_keys=True, default=str)))
    payload = dict(task)
    payload["delivered_to_inbox_at"] = payload.get("delivered_to_inbox_at") or delivered_at
    payload["delivery_via"] = payload.get("delivery_via") or "dharma_swarm.operator_core.a2a_task_lifecycle"
    payload["delivery_note"] = payload.get("delivery_note") or (
        "Task was claimed on the A2A task queue and mirrored into the agent inbox for action."
    )
    path = inbox_dir(agent_uid, state_root) / f"claimed_{task_id}.json"
    if not path.exists():
        _write_json(path, payload)
    return path


def _mirror_receipt(
    task: dict[str, Any],
    receipt: dict[str, Any],
    agent_uid: str,
    state_root: Path | str | None,
) -> list[str]:
    task_id = str(task.get("id") or receipt.get("task_id"))
    written: list[str] = []
    actor_path = inbox_dir(agent_uid, state_root) / f"receipt_{task_id}.json"
    _write_json(actor_path, receipt)
    written.append(str(actor_path))

    sender = str(task.get("from") or "")
    if sender and sender != agent_uid:
        sender_path = inbox_dir(sender, state_root) / f"receipt_{task_id}_from_{agent_uid}.json"
        _write_json(sender_path, receipt)
        written.append(str(sender_path))
    return written


def claim_task(
    task_id: str,
    *,
    agent_uid: str,
    state_root: Path | str | None = None,
    claimed_via: str = "dharma_swarm.operator_core.a2a_task_lifecycle",
    now: str | None = None,
) -> dict[str, Any]:
    """Claim an open task idempotently and mirror it into the agent inbox."""

    path = queue_path(state_root)
    with _queue_lock(path):
        entries = _read_queue_entries(path)
        task = _find_task(entries, task_id)
        current_status = _status(task)
        claimed_by = str(task.get("claimed_by") or "")
        if current_status in CLOSED_STATUSES:
            raise A2ATaskLifecycleError(f"cannot claim closed task {task_id} with status {current_status}")
        if claimed_by and claimed_by != agent_uid:
            raise A2ATaskLifecycleError(f"task {task_id} is already claimed by {claimed_by}")

        ts = now or iso_now()
        task["status"] = "claimed"
        task["claimed_by"] = agent_uid
        task["claimed_at"] = task.get("claimed_at") or ts
        task["claimed_via"] = task.get("claimed_via") or claimed_via
        task["return_address"] = task.get("return_address") or make_return_address(
            agent_uid=agent_uid,
            resume_ref=f"a2a_task:{task_id}",
        )
        _write_queue_entries(path, entries)
    inbox_path = _mirror_claimed_task(task, agent_uid, state_root, ts)
    result = dict(task)
    result["inbox_path"] = str(inbox_path)
    return result


def close_task(
    task_id: str,
    *,
    agent_uid: str,
    status: CloseStatus,
    receipt: dict[str, Any],
    state_root: Path | str | None = None,
    closed_via: str = "dharma_swarm.operator_core.a2a_task_lifecycle",
    require_artifact_or_evidence: bool = False,
    allow_supervisor_block: bool = False,
    now: str | None = None,
) -> dict[str, Any]:
    """Close a task with a validated receipt."""

    if status not in VALID_CLOSE_STATUSES:
        raise A2ATaskLifecycleError(f"invalid close status: {status}")
    validation = validate_task_receipt(
        receipt,
        task_id=task_id,
        agent_uid=agent_uid,
        status=status,
        require_artifact_or_evidence=require_artifact_or_evidence,
    )
    if not validation["valid"]:
        raise A2ATaskLifecycleError("; ".join(validation["errors"]))

    path = queue_path(state_root)
    with _queue_lock(path):
        entries = _read_queue_entries(path)
        task = _find_task(entries, task_id)
        current_status = _status(task)
        if current_status in CLOSED_STATUSES:
            raise A2ATaskLifecycleError(f"cannot close terminal task {task_id} with status {current_status}")
        claimed_by = str(task.get("claimed_by") or "")
        supervisor_block = (
            bool(claimed_by)
            and claimed_by != agent_uid
            and allow_supervisor_block
            and status == "blocked"
        )
        if claimed_by and claimed_by != agent_uid and not supervisor_block:
            raise A2ATaskLifecycleError(f"task {task_id} is claimed by {claimed_by}, not {agent_uid}")
        if supervisor_block:
            if not receipt.get("authority"):
                raise A2ATaskLifecycleError("supervisor block requires receipt.authority")
            if not isinstance(receipt.get("evidence"), dict) or not receipt.get("evidence"):
                raise A2ATaskLifecycleError("supervisor block requires receipt.evidence")

        ts = now or iso_now()
        task["status"] = status
        task["closed_at"] = ts
        task["closed_by"] = agent_uid
        task["closed_via"] = closed_via
        task["receipt_id"] = receipt.get("receipt_id")
        task["receipt"] = receipt
        task["receipt_validation"] = validation
        if status == "completed":
            task["completed"] = ts
            task["completed_at"] = ts
            task["completed_by"] = agent_uid
        elif status == "failed":
            task["failed_at"] = ts
            task["failed_by"] = agent_uid
            task["failure_reason"] = receipt.get("failure_reason")
        elif status == "blocked":
            task["blocked_at"] = ts
            task["blocked_by"] = agent_uid
            task["failure_reason"] = receipt.get("failure_reason")
            if supervisor_block:
                task["supervisor_blocked_claimed_by"] = claimed_by
                task["supervisor_blocked_by"] = agent_uid
        _write_queue_entries(path, entries)
    mirrored = _mirror_receipt(task, receipt, agent_uid, state_root)
    result = dict(task)
    result["receipt_mirrors"] = mirrored
    return result


def complete_task(
    task_id: str,
    *,
    agent_uid: str,
    receipt: dict[str, Any],
    state_root: Path | str | None = None,
    require_artifact_or_evidence: bool = False,
) -> dict[str, Any]:
    return close_task(
        task_id,
        agent_uid=agent_uid,
        status="completed",
        receipt=receipt,
        state_root=state_root,
        require_artifact_or_evidence=require_artifact_or_evidence,
    )


def fail_task(
    task_id: str,
    *,
    agent_uid: str,
    receipt: dict[str, Any],
    state_root: Path | str | None = None,
) -> dict[str, Any]:
    return close_task(task_id, agent_uid=agent_uid, status="failed", receipt=receipt, state_root=state_root)


def block_task(
    task_id: str,
    *,
    agent_uid: str,
    receipt: dict[str, Any],
    state_root: Path | str | None = None,
    allow_supervisor_block: bool = False,
) -> dict[str, Any]:
    return close_task(
        task_id,
        agent_uid=agent_uid,
        status="blocked",
        receipt=receipt,
        state_root=state_root,
        allow_supervisor_block=allow_supervisor_block,
    )


def task_lifecycle_state(task: dict[str, Any], *, require_artifact_or_evidence: bool = False) -> dict[str, Any]:
    """Classify a queue row for objective dashboards and watch towers."""

    task_id = str(task.get("id") or "")
    status = _status(task)
    if status in VALID_CLOSE_STATUSES:
        receipt = task.get("receipt")
        validation = validate_task_receipt(
            receipt,
            task_id=task_id,
            agent_uid=str(task.get("closed_by") or task.get("completed_by") or task.get("claimed_by") or ""),
            status=status,  # type: ignore[arg-type]
            require_artifact_or_evidence=require_artifact_or_evidence,
        )
        return {
            "state": f"{status}_{'verified' if validation['valid'] else 'unverified'}",
            "closed": True,
            "verified": validation["valid"],
            "validation": validation,
        }
    if status == "claimed":
        return {"state": "claimed_open", "closed": False, "verified": False, "validation": None}
    if status in OPEN_STATUSES:
        return {"state": "open_unclaimed", "closed": False, "verified": False, "validation": None}
    return {"state": f"{status}_unknown", "closed": False, "verified": False, "validation": None}


def reconcile_inbox_task_receipts(
    *,
    agent_uid: str,
    state_root: Path | str | None = None,
    require_artifact_or_evidence: bool = False,
) -> list[dict[str, Any]]:
    """Close queue rows from receipt files an agent wrote into its inbox.

    This lets a wake script remain simple: if the agent updates a claimed task
    file or writes ``receipt_<task_id>.json``, the next LLM-free tick can close
    the canonical queue row.
    """

    reconciled: list[dict[str, Any]] = []
    inbox = inbox_dir(agent_uid, state_root)
    if not inbox.exists():
        return reconciled
    candidates = list(inbox.glob("claimed_*.json")) + list(inbox.glob("receipt_*.json"))
    for path in sorted(candidates):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if not isinstance(payload, dict):
            continue
        receipt = payload.get("receipt") if isinstance(payload.get("receipt"), dict) else payload
        if not isinstance(receipt, dict) or receipt.get("schema_version") != "dharma_a2a_task_receipt.v1":
            continue
        task_id = str(receipt.get("task_id") or payload.get("id") or "")
        status = str(receipt.get("status") or payload.get("status") or "").lower()
        if not task_id or status not in VALID_CLOSE_STATUSES:
            continue
        try:
            closed = close_task(
                task_id,
                agent_uid=agent_uid,
                status=status,  # type: ignore[arg-type]
                receipt=receipt,
                state_root=state_root,
                require_artifact_or_evidence=require_artifact_or_evidence,
                closed_via=f"reconcile_inbox_task_receipts:{path.name}",
            )
        except A2ATaskLifecycleError as exc:
            reconciled.append({"path": str(path), "task_id": task_id, "status": "error", "error": str(exc)})
            continue
        reconciled.append({"path": str(path), "task_id": task_id, "status": "closed", "queue_row": closed})
    return reconciled


def read_queue(state_root: Path | str | None = None) -> list[dict[str, Any]]:
    return [row for _, row in _read_queue_entries(queue_path(state_root)) if row is not None]


def _load_receipt_arg(value: str | None) -> dict[str, Any]:
    if not value:
        return {}
    path = Path(value).expanduser()
    return json.loads(path.read_text(encoding="utf-8"))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Claim or close existing Dharma A2A queue tasks.")
    parser.add_argument("--state-root", default=None)
    sub = parser.add_subparsers(dest="command", required=True)

    claim = sub.add_parser("claim")
    claim.add_argument("task_id")
    claim.add_argument("--agent-uid", required=True)

    close = sub.add_parser("close")
    close.add_argument("task_id")
    close.add_argument("--agent-uid", required=True)
    close.add_argument("--status", choices=sorted(VALID_CLOSE_STATUSES), required=True)
    close.add_argument("--receipt", required=True, help="Path to dharma_a2a_task_receipt.v1 JSON")
    close.add_argument(
        "--allow-supervisor-block",
        action="store_true",
        help="Allow a non-claiming supervisor to block, not complete, a stale claimed task.",
    )

    args = parser.parse_args(argv)
    if args.command == "claim":
        result = claim_task(args.task_id, agent_uid=args.agent_uid, state_root=args.state_root)
    else:
        receipt = _load_receipt_arg(args.receipt)
        result = close_task(
            args.task_id,
            agent_uid=args.agent_uid,
            status=args.status,
            receipt=receipt,
            state_root=args.state_root,
            allow_supervisor_block=args.allow_supervisor_block,
        )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
