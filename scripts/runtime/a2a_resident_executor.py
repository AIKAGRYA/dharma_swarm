#!/usr/bin/env python3
"""Lease-scoped local A2A resident executor for Phase A.

This adapter is deliberately narrow. It closes one existing local task from the
``~/.dharma/a2a_bus/tasks/queue.jsonl`` surface when, and only when, a matching
``dharma.execution_lease.v1`` permits the requested local artifact/close/reply
actions. Missing or invalid authority closes the task as ``blocked`` with a
typed A2A task receipt and no task artifact.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import re
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from dharma_swarm.operator_core.a2a_task_lifecycle import (  # noqa: E402
    A2ATaskLifecycleError,
    block_task,
    build_task_receipt,
    claim_task,
    complete_task,
    read_queue,
    validate_task_receipt,
)
from dharma_swarm.operator_core.execution_lease import (  # noqa: E402
    ExecutionLeaseError,
    find_execution_lease_for_task,
    load_execution_lease,
    load_revoked_lease_ids,
    validate_execution_lease,
)
from scripts.runtime.a2a_domain_reply_worker import (  # noqa: E402
    ACK_TIER_DOMAIN_RECEIPTED,
    DomainReplyTarget,
    publish_domain_reply,
)

DEFAULT_AGENT_UID = "codex_composer"
DEFAULT_DHARMA_HOME = Path("~/.dharma")
PHASE_A_RELATIVE_ROOT = Path("reports") / "a2a" / "phase_a"
OPEN_STATUSES = {"", "pending", "open", "ready", "new", "unread"}
TERMINAL_STATUSES = {"completed", "failed", "blocked", "done", "closed", "cancelled"}

FORBIDDEN_ACTION_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\bgit\s+push\b|\bpush\b", re.I), "git_push"),
    (re.compile(r"\blaunchctl\b|\blaunchd\b|\bbootstrap\b|\bkickstart\b", re.I), "launchd_install"),
    (re.compile(r"\bexternal\s+contact\b|\boutreach\b|\bemail\b|\bsend\s+to\b", re.I), "external_contact"),
    (re.compile(r"\bspend\b|\bpayment\b|\bcharge\b|\$\d", re.I), "spend"),
    (re.compile(r"\bbroker\s+topology\b|\bleaf\s+node\b|\bnats\s+cluster\b", re.I), "broker_topology_change"),
    (re.compile(r"\bsource\s+mutation\b|\bedit\s+source\b|\bpatch\s+source\b", re.I), "source_mutation"),
)


@dataclass(frozen=True)
class ExecutorPaths:
    state_root: Path
    repo_root: Path
    task_queue: Path
    lease_root: Path
    artifact_root: Path
    task_receipt_root: Path
    executor_receipt_root: Path
    domain_reply_root: Path
    domain_payload_root: Path


@dataclass(frozen=True)
class LeaseDecision:
    valid: bool
    lease: dict[str, Any] | None
    lease_path: Path | None
    lease_id: str
    errors: tuple[str, ...]
    warnings: tuple[str, ...] = ()
    matched_by: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "valid": self.valid,
            "lease_id": self.lease_id,
            "lease_path": str(self.lease_path) if self.lease_path else "",
            "errors": list(self.errors),
            "warnings": list(self.warnings),
            "matched_by": self.matched_by,
        }


class _LocalFilePublisher:
    def __init__(self, payload_path: Path) -> None:
        self.payload_path = payload_path
        self.subject = ""

    async def publish(self, subject: str, payload: bytes) -> None:
        self.subject = subject
        self.payload_path.parent.mkdir(parents=True, exist_ok=True)
        self.payload_path.write_bytes(payload)

    async def flush(self, timeout: float | None = None) -> None:
        del timeout


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _json_default(value: Any) -> str:
    if isinstance(value, Path):
        return str(value)
    return str(value)


def _write_json(path: Path, payload: Mapping[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + f".tmp.{os.getpid()}")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True, default=_json_default) + "\n", encoding="utf-8")
    tmp.replace(path)
    return path


def _write_text(path: Path, payload: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + f".tmp.{os.getpid()}")
    tmp.write_text(payload, encoding="utf-8")
    tmp.replace(path)
    return path


def _safe_token(value: object, *, fallback: str = "task") -> str:
    token = re.sub(r"[^A-Za-z0-9_.:-]+", "-", str(value or "")).strip(".:-_")
    return (token or fallback)[:96]


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return "sha256:" + h.hexdigest()


def executor_paths(
    *,
    state_root: str | Path = DEFAULT_DHARMA_HOME,
    repo_root: str | Path = REPO_ROOT,
    artifact_root: str | Path | None = None,
    lease_root: str | Path | None = None,
) -> ExecutorPaths:
    state = Path(state_root).expanduser().resolve()
    repo = Path(repo_root).expanduser().resolve()
    phase_root = Path(artifact_root).expanduser().resolve() if artifact_root else repo / PHASE_A_RELATIVE_ROOT
    leases = Path(lease_root).expanduser().resolve() if lease_root else state / "a2a_bus" / "leases"
    return ExecutorPaths(
        state_root=state,
        repo_root=repo,
        task_queue=state / "a2a_bus" / "tasks" / "queue.jsonl",
        lease_root=leases,
        artifact_root=phase_root,
        task_receipt_root=phase_root / "task_receipts",
        executor_receipt_root=phase_root / "executor_receipts",
        domain_reply_root=phase_root / "domain_reply_receipts",
        domain_payload_root=phase_root / "domain_reply_payloads",
    )


def _task_target(task: Mapping[str, Any]) -> str:
    return str(task.get("to") or task.get("agent_uid") or task.get("recipient") or "").strip()


def _task_status(task: Mapping[str, Any]) -> str:
    return str(task.get("status") or "pending").strip().lower()


def _task_text(task: Mapping[str, Any]) -> str:
    parts = []
    for key in ("body", "summary", "message", "content", "action_requested", "claim"):
        value = task.get(key)
        if value:
            parts.append(str(value))
    return " ".join(parts)


def _task_id(task: Mapping[str, Any]) -> str:
    return str(task.get("id") or task.get("task_id") or "")


def _task_correlation_id(task: Mapping[str, Any]) -> str:
    return str(task.get("correlation_id") or task.get("packet_id") or _task_id(task) or "")


def _task_reply_subject(task: Mapping[str, Any]) -> str:
    return str(task.get("reply_subject") or "")


def _infer_forbidden_actions(task: Mapping[str, Any]) -> list[str]:
    text = _task_text(task)
    actions: list[str] = []
    for pattern, action in FORBIDDEN_ACTION_PATTERNS:
        if pattern.search(text):
            actions.append(action)
    return list(dict.fromkeys(actions))


def requested_actions_for_task(task: Mapping[str, Any]) -> list[str]:
    actions = ["read", "write_artifact", "close_task", *_infer_forbidden_actions(task)]
    if _task_reply_subject(task):
        actions.append("publish_domain_reply")
    return list(dict.fromkeys(actions))


def paths_for_task(paths: ExecutorPaths, task_id: str) -> dict[str, Path]:
    token = _safe_token(task_id)
    return {
        "artifact": paths.artifact_root / f"{token}_artifact.md",
        "task_receipt": paths.task_receipt_root / f"{token}_task_receipt.json",
        "executor_receipt": paths.executor_receipt_root / f"{token}_executor_receipt.json",
        "domain_send_receipt": paths.domain_reply_root / "send_receipts" / f"{token}_send_receipt.json",
        "domain_artifact": paths.domain_reply_root / "artifacts" / f"{token}_domain_reply_artifact.json",
        "domain_payload": paths.domain_payload_root / f"{token}_domain_payload.json",
    }


def requested_paths_for_task(paths: ExecutorPaths, task: Mapping[str, Any]) -> list[Path]:
    task_paths = paths_for_task(paths, _task_id(task))
    requested = [task_paths["artifact"], task_paths["task_receipt"], task_paths["executor_receipt"]]
    if _task_reply_subject(task):
        requested.extend([task_paths["domain_send_receipt"], task_paths["domain_artifact"], task_paths["domain_payload"]])
    return requested


def find_open_task(
    *,
    state_root: str | Path,
    agent_uid: str,
    task_id: str = "",
) -> dict[str, Any] | None:
    addresses = {agent_uid, agent_uid.lower()}
    for task in read_queue(state_root):
        tid = _task_id(task)
        if task_id and tid != task_id:
            continue
        if _task_status(task) not in OPEN_STATUSES:
            continue
        target = _task_target(task)
        if target and target not in addresses and target.lower() not in addresses:
            continue
        return task
    return None


def resolve_task_lease(
    *,
    task: Mapping[str, Any],
    agent_uid: str,
    paths: ExecutorPaths,
    requested_actions: Sequence[str],
    requested_paths: Sequence[Path],
    now: str | None = None,
) -> LeaseDecision:
    task_id = _task_id(task)
    correlation_id = _task_correlation_id(task)
    revoked = load_revoked_lease_ids(paths.lease_root)
    embedded = task.get("execution_lease") or task.get("lease")
    explicit_lease_id = str(task.get("execution_lease_id") or task.get("lease_id") or "").strip()

    if isinstance(embedded, dict):
        validation = validate_execution_lease(
            embedded,
            now=now,
            agent_uid=agent_uid,
            task_id=task_id,
            requested_actions=requested_actions,
            requested_paths=requested_paths,
            revoked_lease_ids=revoked,
        )
        errors = [*validation.errors, *_phase_a_lease_hardening_errors(embedded)]
        return LeaseDecision(
            valid=validation.valid and not errors,
            lease=dict(embedded),
            lease_path=None,
            lease_id=validation.lease_id,
            errors=tuple(errors),
            warnings=tuple(validation.warnings),
            matched_by="embedded",
        )

    if explicit_lease_id:
        try:
            lease = load_execution_lease(paths.lease_root, explicit_lease_id)
            validation = validate_execution_lease(
                lease,
                now=now,
                agent_uid=agent_uid,
                task_id=task_id,
                requested_actions=requested_actions,
                requested_paths=requested_paths,
                revoked_lease_ids=revoked,
            )
            errors = [*validation.errors, *_phase_a_lease_hardening_errors(lease)]
            return LeaseDecision(
                valid=validation.valid and not errors,
                lease=lease,
                lease_path=paths.lease_root / f"{explicit_lease_id}.json",
                lease_id=validation.lease_id or explicit_lease_id,
                errors=tuple(errors),
                warnings=tuple(validation.warnings),
                matched_by="execution_lease_id",
            )
        except (ExecutionLeaseError, OSError, json.JSONDecodeError) as exc:
            return LeaseDecision(
                valid=False,
                lease=None,
                lease_path=None,
                lease_id=explicit_lease_id,
                errors=(f"lease load failed: {type(exc).__name__}: {exc}",),
                matched_by="execution_lease_id",
            )

    match = find_execution_lease_for_task(
        paths.lease_root,
        agent_uid=agent_uid,
        task_id=task_id,
        correlation_id=correlation_id,
        now=now,
    )
    if match is None:
        return LeaseDecision(
            valid=False,
            lease=None,
            lease_path=None,
            lease_id="",
            errors=("execution_lease_required",),
            matched_by="none",
        )
    lease_path, lease, _validation = match
    validation = validate_execution_lease(
        lease,
        now=now,
        agent_uid=agent_uid,
        task_id=task_id,
        requested_actions=requested_actions,
        requested_paths=requested_paths,
        revoked_lease_ids=revoked,
    )
    errors = [*validation.errors, *_phase_a_lease_hardening_errors(lease)]
    return LeaseDecision(
        valid=validation.valid and not errors,
        lease=lease,
        lease_path=lease_path,
        lease_id=validation.lease_id,
        errors=tuple(errors),
        warnings=tuple(validation.warnings),
        matched_by="task_or_correlation_id",
    )


def _phase_a_lease_hardening_errors(lease: Mapping[str, Any]) -> list[str]:
    """Executor-specific hardening above the generic lease primitive.

    The shared validator stays permissive for backwards compatibility. Phase A's
    resident executor is narrower: no implicit action/path wildcard and no spend.
    """
    errors: list[str] = []
    if not lease.get("allowed_actions"):
        errors.append("allowed_actions must be explicit for Phase A resident executor")
    if not lease.get("allowed_paths"):
        errors.append("allowed_paths must be explicit for Phase A resident executor")
    budget = lease.get("budget")
    if isinstance(budget, Mapping) and float(budget.get("max_usd") or 0) > 0:
        errors.append("max_usd must be 0 for Phase A resident executor")
    return errors


def _local_source_status(repo_root: Path) -> list[dict[str, Any]]:
    anchors = [
        Path.home() / ".dharma" / "a2a_bus" / "operator" / "handoffs" / "2026-07-02_a2a_shared_knowledge" / "PHASE_A_ENGINEERING_SPEC.md",
        Path.home() / ".dharma" / "a2a_bus" / "operator" / "handoffs" / "2026-07-02_a2a_shared_knowledge" / "CODEX_GOAL_PHASE_A_BUILD_PLAN.md",
        repo_root / "dharma_swarm" / "operator_core" / "a2a_task_lifecycle.py",
        repo_root / "dharma_swarm" / "operator_core" / "execution_lease.py",
    ]
    status = []
    for path in anchors:
        exists = path.exists()
        entry: dict[str, Any] = {"path": str(path), "exists": exists}
        if exists:
            entry["bytes"] = path.stat().st_size
            entry["sha256"] = _sha256_file(path)
        status.append(entry)
    return status


def write_boring_artifact(
    *,
    path: Path,
    task: Mapping[str, Any],
    lease: LeaseDecision,
    repo_root: Path,
) -> Path:
    task_id = _task_id(task)
    lines = [
        f"# Phase A Local Executor Artifact: {task_id}",
        "",
        f"- agent_uid: `{DEFAULT_AGENT_UID}`",
        f"- generated_at: `{utc_now()}`",
        f"- correlation_id: `{_task_correlation_id(task)}`",
        f"- lease_id: `{lease.lease_id}`",
        "- proof_mode: `local-fixture-or-local-filesystem`",
        "",
        "## Task",
        "",
        _task_text(task) or "(no task body)",
        "",
        "## Local Source Anchors",
        "",
    ]
    for item in _local_source_status(repo_root):
        lines.append(f"- `{item['path']}` exists={item['exists']} sha256={item.get('sha256', '')}")
    lines.extend(
        [
            "",
            "## Deterministic Result",
            "",
            "The resident executor validated a file-backed execution lease, claimed the task, "
            "wrote this allowed artifact, and prepared a validated A2A task receipt.",
            "",
        ]
    )
    return _write_text(path, "\n".join(lines))


async def _write_local_domain_reply(
    *,
    task: Mapping[str, Any],
    agent_uid: str,
    task_receipt_path: Path,
    task_receipt: Mapping[str, Any],
    task_paths: Mapping[str, Path],
    receipt_root: Path,
) -> dict[str, Any]:
    reply_subject = _task_reply_subject(task)
    if not reply_subject:
        return {
            "status": "DOMAIN_REPLY_UNAVAILABLE",
            "domain_reply_unavailable_reason": "task did not include reply_subject",
            "domain_receipt_claim": False,
        }

    packet_id = _task_correlation_id(task) or _task_id(task)
    send_receipt = {
        "schema_version": "dharma.a2a.synthetic_send_receipt.v1",
        "timestamp": utc_now(),
        "packet_id": packet_id,
        "reply_subject": reply_subject,
        "from": str(task.get("from") or "operator"),
        "target_uid": agent_uid,
        "task_id": _task_id(task),
        "local_phase_a_fixture": True,
        "operator_contact_note": "synthetic local send receipt for Phase A executor proof; no external contact",
    }
    artifact = {
        "schema_version": "dharma.a2a.domain_reply_artifact.v1",
        "timestamp": utc_now(),
        "authored_by": agent_uid,
        "agent_uid": agent_uid,
        "author_kind": "phase_a_resident_executor",
        "packet_id": packet_id,
        "reply_subject": reply_subject,
        "send_receipt_path": str(task_paths["domain_send_receipt"]),
        "summary": f"Resident executor closed task {_task_id(task)} with receipt {task_receipt.get('receipt_id')}.",
        "verdict": "completed",
        "semantic_reply_claim": False,
        "peer_model_processed_claim": False,
        "evidence_refs": [str(task_receipt_path)],
    }
    _write_json(task_paths["domain_send_receipt"], send_receipt)
    _write_json(task_paths["domain_artifact"], artifact)
    target = DomainReplyTarget(
        send_receipt_path=task_paths["domain_send_receipt"],
        send_receipt=send_receipt,
        reply_artifact_path=task_paths["domain_artifact"],
        reply_artifact=artifact,
        agent_uid=agent_uid,
        packet_id=packet_id,
        reply_subject=reply_subject,
    )
    publisher = _LocalFilePublisher(task_paths["domain_payload"])
    receipt = await publish_domain_reply(
        target,
        publisher=publisher,
        receipt_dir=receipt_root,
        endpoint="local-fixture://a2a_resident_executor",
        stream="LOCAL_PHASE_A_FIXTURE",
        nats={"mode": "local_file_fixture", "live_nats_publish": False},
        transport_ack={
            "transport_ack": "LOCAL_FILE_WRITE",
            "payload_path": str(task_paths["domain_payload"]),
            "contact_evidence_tier": ACK_TIER_DOMAIN_RECEIPTED,
        },
    )
    receipt["proof_mode"] = "local_fixture"
    receipt["live_nats_publish"] = False
    if receipt.get("receipt_path"):
        _write_json(Path(str(receipt["receipt_path"])), receipt)
    return receipt


def _write_executor_receipt(
    *,
    paths: ExecutorPaths,
    task: Mapping[str, Any] | None,
    status: str,
    agent_uid: str,
    lease: LeaseDecision | None = None,
    task_receipt_path: Path | None = None,
    artifact_path: Path | None = None,
    domain_reply: Mapping[str, Any] | None = None,
    failure_reason: str = "",
    safety: Mapping[str, Any] | None = None,
) -> tuple[dict[str, Any], Path]:
    task_id = _task_id(task or {}) or "no-task"
    payload = {
        "schema_version": f"dharma.{agent_uid}.resident_executor_receipt.v1",
        "timestamp": utc_now(),
        "receipt_id": f"a2a-resident-executor:{agent_uid}:{task_id}:{stamp()}",
        "agent_uid": agent_uid,
        "authority_mode": "read_only_until_execution_lease",
        "task_id": task_id,
        "status": status,
        "failure_reason": failure_reason,
        "context": {"missing": []},
        "work": {
            "observed_messages": [task_id] if task else [],
            "accepted_task_claims": [task_id] if status == "completed" else [],
            "work_requiring_execution_lease": [task_id] if status == "blocked" else [],
            "completed_read_only_analysis": [],
        },
        "lease": lease.to_dict() if lease else {},
        "artifact_path": str(artifact_path) if artifact_path else "",
        "task_receipt_path": str(task_receipt_path) if task_receipt_path else "",
        "domain_reply": dict(domain_reply or {}),
        "safety": {
            "source_mutation_performed": False,
            "launchd_install_performed": False,
            "external_contact_performed": False,
            "broker_topology_mutation_performed": False,
            "git_push_performed": False,
            "spend_performed": False,
            **dict(safety or {}),
        },
        "queue_path": str(paths.task_queue),
        "artifact_root": str(paths.artifact_root),
        "proof_mode": "local_filesystem",
    }
    receipt_path = paths.executor_receipt_root / f"{_safe_token(task_id, fallback='no-task')}_{stamp()}_executor_receipt.json"
    _write_json(receipt_path, payload)
    return payload, receipt_path


def _failure_reason(lease: LeaseDecision) -> str:
    return "; ".join(lease.errors) if lease.errors else "execution_lease_required"


def _block_for_lease(
    *,
    paths: ExecutorPaths,
    task: Mapping[str, Any],
    agent_uid: str,
    lease: LeaseDecision,
    requested_actions: Sequence[str],
    requested_paths: Sequence[Path],
    now: str | None = None,
) -> dict[str, Any]:
    task_id = _task_id(task)
    task_paths = paths_for_task(paths, task_id)
    reason = _failure_reason(lease)
    receipt = build_task_receipt(
        task_id=task_id,
        agent_uid=agent_uid,
        status="blocked",
        summary=f"Blocked resident executor task because execution lease validation failed: {reason}",
        correlation_id=_task_correlation_id(task),
        authority="read_only_until_valid_execution_lease",
        evidence={
            "lease": lease.to_dict(),
            "requested_actions": list(requested_actions),
            "requested_paths": [str(path) for path in requested_paths],
            "task_body_excerpt": _task_text(task)[:500],
            "side_effects_performed": {
                "artifact_written": False,
                "source_mutation": False,
                "launchd_install": False,
                "external_contact": False,
                "git_push": False,
                "spend": False,
            },
        },
        evaluation={
            "overall_verdict": "blocked",
            "criteria_results": [
                {"criterion": "lease_missing_or_invalid", "passed": True},
                {"criterion": "no_task_artifact_written", "passed": True},
                {"criterion": "forbidden_side_effects_absent", "passed": True},
            ],
            "gate_results": [],
        },
        replay_command=(
            f"{sys.executable} scripts/runtime/a2a_resident_executor.py once "
            f"--agent-uid {agent_uid} --task-id {task_id}"
        ),
        failure_reason=reason,
        timestamp=now,
    )
    validation = validate_task_receipt(receipt, task_id=task_id, agent_uid=agent_uid, status="blocked")
    if not validation["valid"]:
        raise A2ATaskLifecycleError("; ".join(validation["errors"]))
    task_receipt_path = _write_json(task_paths["task_receipt"], receipt)
    closed = block_task(task_id, agent_uid=agent_uid, receipt=receipt, state_root=paths.state_root)
    executor_receipt, executor_receipt_path = _write_executor_receipt(
        paths=paths,
        task=task,
        status="blocked",
        agent_uid=agent_uid,
        lease=lease,
        task_receipt_path=task_receipt_path,
        failure_reason=reason,
    )
    return {
        "status": "blocked",
        "task_id": task_id,
        "failure_reason": reason,
        "closed_task": closed,
        "task_receipt": receipt,
        "task_receipt_path": str(task_receipt_path),
        "executor_receipt": executor_receipt,
        "executor_receipt_path": str(executor_receipt_path),
        "artifact_path": "",
        "lease": lease.to_dict(),
    }


def run_once(
    *,
    agent_uid: str = DEFAULT_AGENT_UID,
    state_root: str | Path = DEFAULT_DHARMA_HOME,
    repo_root: str | Path = REPO_ROOT,
    artifact_root: str | Path | None = None,
    lease_root: str | Path | None = None,
    task_id: str = "",
    now: str | None = None,
) -> dict[str, Any]:
    paths = executor_paths(state_root=state_root, repo_root=repo_root, artifact_root=artifact_root, lease_root=lease_root)
    task = find_open_task(state_root=paths.state_root, agent_uid=agent_uid, task_id=task_id)
    if task is None:
        executor_receipt, receipt_path = _write_executor_receipt(
            paths=paths,
            task=None,
            status="no_open_task",
            agent_uid=agent_uid,
            failure_reason="no matching open task",
        )
        return {
            "status": "no_open_task",
            "agent_uid": agent_uid,
            "executor_receipt": executor_receipt,
            "executor_receipt_path": str(receipt_path),
        }

    tid = _task_id(task)
    requested_actions = requested_actions_for_task(task)
    requested_paths = requested_paths_for_task(paths, task)
    lease = resolve_task_lease(
        task=task,
        agent_uid=agent_uid,
        paths=paths,
        requested_actions=requested_actions,
        requested_paths=requested_paths,
        now=now,
    )
    if not lease.valid:
        return _block_for_lease(
            paths=paths,
            task=task,
            agent_uid=agent_uid,
            lease=lease,
            requested_actions=requested_actions,
            requested_paths=requested_paths,
            now=now,
        )

    claimed = claim_task(tid, agent_uid=agent_uid, state_root=paths.state_root, now=now)
    task_paths = paths_for_task(paths, tid)
    artifact_path = write_boring_artifact(
        path=task_paths["artifact"],
        task=task,
        lease=lease,
        repo_root=paths.repo_root,
    )
    task_receipt = build_task_receipt(
        task_id=tid,
        agent_uid=agent_uid,
        status="completed",
        summary="Resident executor completed one Phase A local task under a validated execution lease.",
        correlation_id=_task_correlation_id(task),
        artifacts=[{"path": str(artifact_path), "kind": "phase_a_local_executor_artifact"}],
        authority="validated_dharma_execution_lease_v1",
        evidence={
            "lease": lease.to_dict(),
            "claimed_task": {
                "id": claimed.get("id"),
                "claimed_by": claimed.get("claimed_by"),
                "claimed_at": claimed.get("claimed_at"),
                "inbox_path": claimed.get("inbox_path"),
            },
            "requested_actions": requested_actions,
            "requested_paths": [str(path) for path in requested_paths],
            "artifact_sha256": _sha256_file(artifact_path),
        },
        evaluation={
            "overall_verdict": "pass",
            "criteria_results": [
                {"criterion": "lease_validated", "passed": True},
                {"criterion": "artifact_exists", "passed": artifact_path.exists()},
                {"criterion": "worker_not_final_verifier", "passed": True},
            ],
            "gate_results": [],
        },
        replay_command=(
            f"{sys.executable} scripts/runtime/a2a_resident_executor.py once "
            f"--agent-uid {agent_uid} --task-id {tid}"
        ),
        timestamp=now,
    )
    validation = validate_task_receipt(task_receipt, task_id=tid, agent_uid=agent_uid, status="completed", require_artifact_or_evidence=True)
    if not validation["valid"]:
        raise A2ATaskLifecycleError("; ".join(validation["errors"]))
    task_receipt_path = _write_json(task_paths["task_receipt"], task_receipt)
    closed = complete_task(tid, agent_uid=agent_uid, receipt=task_receipt, state_root=paths.state_root, require_artifact_or_evidence=True)
    domain_reply = asyncio.run(
        _write_local_domain_reply(
            task=task,
            agent_uid=agent_uid,
            task_receipt_path=task_receipt_path,
            task_receipt=task_receipt,
            task_paths=task_paths,
            receipt_root=paths.domain_reply_root,
        )
    )
    executor_receipt, executor_receipt_path = _write_executor_receipt(
        paths=paths,
        task=task,
        status="completed",
        agent_uid=agent_uid,
        lease=lease,
        task_receipt_path=task_receipt_path,
        artifact_path=artifact_path,
        domain_reply=domain_reply,
    )
    return {
        "status": "completed",
        "task_id": tid,
        "closed_task": closed,
        "artifact_path": str(artifact_path),
        "task_receipt": task_receipt,
        "task_receipt_path": str(task_receipt_path),
        "domain_reply": domain_reply,
        "executor_receipt": executor_receipt,
        "executor_receipt_path": str(executor_receipt_path),
        "lease": lease.to_dict(),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    once = sub.add_parser("once", help="execute or refuse one matching local A2A task")
    once.add_argument("--agent-uid", default=DEFAULT_AGENT_UID)
    once.add_argument("--state-root", default=str(DEFAULT_DHARMA_HOME))
    once.add_argument("--repo-root", default=str(REPO_ROOT))
    once.add_argument("--artifact-root", default="")
    once.add_argument("--lease-root", default="")
    once.add_argument("--task-id", default="")
    once.add_argument("--now", default="")
    once.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "once":
        result = run_once(
            agent_uid=args.agent_uid,
            state_root=args.state_root,
            repo_root=args.repo_root,
            artifact_root=args.artifact_root or None,
            lease_root=args.lease_root or None,
            task_id=args.task_id,
            now=args.now or None,
        )
        if args.json:
            print(json.dumps(result, indent=2, sort_keys=True, default=_json_default))
        else:
            print(
                " ".join(
                    [
                        f"status={result['status']}",
                        f"task_id={result.get('task_id', '')}",
                        f"executor_receipt={result.get('executor_receipt_path', '')}",
                    ]
                )
            )
        return 0 if result["status"] in {"completed", "blocked", "no_open_task"} else 1
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
