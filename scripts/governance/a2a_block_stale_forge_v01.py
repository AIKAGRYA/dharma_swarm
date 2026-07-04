#!/usr/bin/env python3
"""Block the stale Forge v0.1 A2A row when its work packet is absent."""
from __future__ import annotations
import argparse
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
from dharma_swarm.daemon_config import dharma_state_dir  # noqa: E402
from dharma_swarm.operator_core.a2a_task_lifecycle import (  # noqa: E402
    OPEN_STATUSES,
    build_task_receipt,
    close_task,
    queue_path,
    read_queue,
    task_lifecycle_state,
    validate_task_receipt,
)
from scripts.governance.check_a2a_readiness import evaluate_a2a_readiness  # noqa: E402
DEFAULT_AGENT_UID = "a2a_supervisor"
DEFAULT_TASK_ID = "forge-v0.1-001"
DEFAULT_TARGET_AGENT = "codex_forgewright"
DEFAULT_MISSION_ID = "20260531T172816Z-dharma-reward-forge-v0-1-x-chain-forge-council-v-97f649"
DEFAULT_STALE_HOURS = 24.0
DEFAULT_HEARTBEAT_STALE_HOURS = 24.0
SPEC_RELATIVE_PATH = Path("docs/specs/forge_packets/v0.1.1-transfer-gate.md")
HANDOFF_NAME = "20260601T172816Z_forge_v0_1_handoff.json"
PARALLEL_FORGE_PR_URL = "https://github.com/AmitabhainArunachala/dharma_swarm/pull/734"
def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()
def _safe_timestamp(value: str) -> str:
    return value.replace("+00:00", "Z").replace(":", "").replace("-", "").replace(".", "")
def _parse_time(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    candidate = value.strip()
    if candidate.endswith("Z"):
        candidate = f"{candidate[:-1]}+00:00"
    try:
        parsed = datetime.fromisoformat(candidate)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)
def _age_hours_from_value(value: Any, now: datetime) -> float | None:
    parsed = _parse_time(value)
    if parsed is None:
        return None
    return round(max((now - parsed).total_seconds(), 0.0) / 3600.0, 3)
def _age_hours(row: dict[str, Any], now: datetime) -> float | None:
    for key in ("created", "created_at", "submitted_at", "updated_at"):
        age = _age_hours_from_value(row.get(key), now)
        if age is not None:
            return age
    return None
def _row_status(row: dict[str, Any]) -> str:
    return str(row.get("status") or "pending").lower()
def _body_excerpt(row: dict[str, Any], limit: int = 420) -> str:
    body = " ".join(str(row.get("body") or "").split())
    return body if len(body) <= limit else f"{body[:limit]}..."
def _state_base(state_root: Path | None) -> Path:
    return state_root if state_root is not None else dharma_state_dir("DHARMA_STATE_DIR", "DHARMA_HOME")
def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}
def _first_mapping(*values: Any) -> dict[str, Any]:
    for value in values:
        if isinstance(value, dict):
            return value
    return {}
def _missing(paths: list[dict[str, Any]]) -> bool:
    return all(not item.get("exists") for item in paths)
def _spec_paths(repo_root: Path, canonical_repo: Path | None) -> list[dict[str, Any]]:
    roots = [repo_root]
    if canonical_repo is not None and canonical_repo != repo_root:
        roots.append(canonical_repo)
    result: list[dict[str, Any]] = []
    seen: set[str] = set()
    for root in roots:
        path = root / SPEC_RELATIVE_PATH
        if str(path) not in seen:
            seen.add(str(path))
            result.append({"path": str(path), "exists": path.exists()})
    return result
def _handoff_paths(state_root: Path | None, target_agent: str, mission_id: str) -> list[dict[str, Any]]:
    base = _state_base(state_root)
    candidates = [
        base / "a2a_bus" / "inboxes" / target_agent / HANDOFF_NAME,
        base / "a2a_bus" / "inboxes" / target_agent / "archive" / HANDOFF_NAME,
        base / "autonomy_spine" / mission_id / HANDOFF_NAME,
        base / "autonomy_spine" / mission_id / "inbox" / HANDOFF_NAME,
    ]
    return [{"path": str(path), "exists": path.exists()} for path in candidates]
def _target_policy(state_root: Path | None, target_agent: str, now: datetime) -> dict[str, Any]:
    base = _state_base(state_root)
    living_path = base / "agents" / target_agent / "living_agent.json"
    registration_path = base / "external_agents" / target_agent / "registration.json"
    living = _load_json(living_path)
    registration = _load_json(registration_path)
    embodiment = living.get("current_embodiment") if isinstance(living.get("current_embodiment"), dict) else {}
    living_meta = living.get("metadata") if isinstance(living.get("metadata"), dict) else {}
    embodiment_meta = embodiment.get("metadata") if isinstance(embodiment.get("metadata"), dict) else {}
    autonomy = _first_mapping(
        living.get("autonomy_policy"),
        living_meta.get("autonomy_policy"),
        embodiment_meta.get("autonomy_policy"),
        registration.get("autonomy_policy"),
    )
    workspace = _first_mapping(
        living_meta.get("workspace_policy"),
        embodiment_meta.get("workspace_policy"),
        registration.get("workspace_policy"),
    )
    last_seen_at = str(living.get("last_seen_at") or registration.get("last_seen_at") or registration.get("updated_at") or "")
    age_hours = _age_hours_from_value(last_seen_at, now)
    authority = living_meta.get("authority") or embodiment_meta.get("authority") or registration.get("authority") or ""
    return {
        "agent_uid": target_agent,
        "living_agent_path": str(living_path),
        "living_agent_exists": living_path.exists(),
        "registration_path": str(registration_path),
        "registration_exists": registration_path.exists(),
        "status": str(living.get("status") or registration.get("status") or ""),
        "last_seen_at": last_seen_at,
        "age_hours": age_hours,
        "heartbeat_status": "RED" if age_hours is None or age_hours >= DEFAULT_HEARTBEAT_STALE_HOURS else "GREEN",
        "authority": str(authority),
        "requires_approval": bool(autonomy.get("requires_approval")),
        "repo_writes_allowed": bool(workspace.get("repo_writes_allowed")),
        "can_write_source": bool(autonomy.get("can_write_source")),
    }
def _target_is_stale_or_gated(policy: dict[str, Any], heartbeat_stale_hours: float) -> bool:
    age = policy.get("age_hours")
    stale = age is None or float(age) >= heartbeat_stale_hours
    gated = (
        bool(policy.get("requires_approval"))
        or not bool(policy.get("repo_writes_allowed"))
        or not bool(policy.get("can_write_source"))
    )
    return stale and gated
def _mission_evidence(state_root: Path | None, mission_id: str) -> dict[str, Any]:
    mission_dir = _state_base(state_root) / "autonomy_spine" / mission_id
    brief_path = mission_dir / "brief.md"
    tasks_path = mission_dir / "tasks.jsonl"
    tasks: list[dict[str, Any]] = []
    if tasks_path.exists():
        for line in tasks_path.read_text(encoding="utf-8").splitlines():
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(payload, dict):
                tasks.append(payload)
    builder_tasks = [task for task in tasks if str(task.get("role") or "") == "builder"]
    return {
        "mission_dir": str(mission_dir),
        "mission_dir_exists": mission_dir.exists(),
        "brief_path": str(brief_path),
        "brief_exists": brief_path.exists(),
        "tasks_path": str(tasks_path),
        "tasks_exists": tasks_path.exists(),
        "task_counts": {
            "total": len(tasks),
            "open": sum(1 for task in tasks if str(task.get("status") or "") == "open"),
            "completed": sum(1 for task in tasks if str(task.get("status") or "") == "completed"),
            "blocked": sum(1 for task in tasks if str(task.get("status") or "") == "blocked"),
        },
        "builder_tasks": [
            {
                "task_id": str(task.get("task_id") or ""),
                "status": str(task.get("status") or ""),
                "receipt_id": str(task.get("receipt_id") or ""),
                "claimed_by": str((task.get("lease") or {}).get("claimed_by") or "")
                if isinstance(task.get("lease"), dict)
                else "",
            }
            for task in builder_tasks
        ],
    }
def _receipt(
    row: dict[str, Any],
    *,
    agent_uid: str,
    age_hours: float | None,
    stale_after_hours: float,
    heartbeat_stale_hours: float,
    spec_paths: list[dict[str, Any]],
    handoff_paths: list[dict[str, Any]],
    target_policy: dict[str, Any],
    mission_evidence: dict[str, Any],
    timestamp: str,
) -> dict[str, Any]:
    task_id = str(row.get("id") or "")
    body = str(row.get("body") or "")
    return build_task_receipt(
        task_id=task_id,
        agent_uid=agent_uid,
        status="blocked",
        summary=(
            "Blocked stale Forge v0.1 A2A row because the required source spec and "
            "handoff are absent, while the assigned external worker seat is stale or manual-gated."
        ),
        authority="stale_forge_v01_supervisor_block",
        completion_via="a2a_block_stale_forge_v01",
        failure_reason="forge_work_packet_missing_and_target_stale_or_external_gated",
        evidence={
            "age_hours": age_hours,
            "body_excerpt": _body_excerpt(row),
            "created": str(row.get("created") or row.get("created_at") or ""),
            "heartbeat_stale_hours": heartbeat_stale_hours,
            "handoff_name": HANDOFF_NAME,
            "handoff_paths": handoff_paths,
            "mission_evidence": mission_evidence,
            "mission_id": str(row.get("mission_id") or ""),
            "original_from": str(row.get("from") or ""),
            "original_status": _row_status(row),
            "original_to": str(row.get("to") or ""),
            "original_type": str(row.get("type") or ""),
            "parallel_forge_pr_url": PARALLEL_FORGE_PR_URL,
            "required_spec_relative_path": str(SPEC_RELATIVE_PATH),
            "spec_paths": spec_paths,
            "stale_after_hours": stale_after_hours,
            "supervisor_scope": "block_only_no_forge_build_or_lane_selection_claimed",
            "target_policy": target_policy,
        },
        evaluation={
            "overall_verdict": "blocked_stale_forge_row_missing_work_packet_external_gated",
            "criteria_results": [
                {"criterion": "row_is_known_forge_v01_task", "passed": task_id == DEFAULT_TASK_ID},
                {"criterion": "row_is_open_unclaimed", "passed": True},
                {"criterion": "row_is_stale", "passed": age_hours is None or age_hours >= stale_after_hours},
                {"criterion": "assigned_target_matches_task", "passed": str(row.get("to") or "") == DEFAULT_TARGET_AGENT},
                {
                    "criterion": "body_references_required_spec_and_handoff",
                    "passed": str(SPEC_RELATIVE_PATH) in body and HANDOFF_NAME in body,
                },
                {"criterion": "required_spec_missing_from_checked_roots", "passed": _missing(spec_paths)},
                {"criterion": "handoff_missing_from_target_paths", "passed": _missing(handoff_paths)},
                {
                    "criterion": "target_presence_stale_or_manual_gated",
                    "passed": _target_is_stale_or_gated(target_policy, heartbeat_stale_hours),
                },
                {"criterion": "supervisor_does_not_claim_forge_build", "passed": True},
                {"criterion": "supervisor_does_not_choose_parallel_forge_lane", "passed": True},
            ],
            "gate_results": [],
        },
        timestamp=timestamp,
    )
def _candidate(
    row: dict[str, Any],
    *,
    row_index: int,
    agent_uid: str,
    task_id: str,
    stale_after_hours: float,
    heartbeat_stale_hours: float,
    now: datetime,
    timestamp: str,
    state_root: Path | None,
    repo_root: Path,
    canonical_repo: Path | None,
) -> tuple[dict[str, Any] | None, dict[str, Any] | None, dict[str, Any] | None]:
    row_task_id = str(row.get("id") or "")
    status = _row_status(row)
    target_agent = str(row.get("to") or "")
    if task_lifecycle_state(row).get("closed") or row_task_id != task_id:
        return None, None, None
    if status not in OPEN_STATUSES:
        return None, _skip(row_index, row_task_id, target_agent, status, "unsupported_status", status), None
    if target_agent != DEFAULT_TARGET_AGENT:
        return None, _skip(row_index, row_task_id, target_agent, status, "target_agent_mismatch", DEFAULT_TARGET_AGENT), None
    if str(row.get("mission_id") or "") != DEFAULT_MISSION_ID:
        return None, _skip(row_index, row_task_id, target_agent, status, "mission_id_mismatch", DEFAULT_MISSION_ID), None
    age = _age_hours(row, now)
    if age is not None and age < stale_after_hours:
        return None, _skip(row_index, row_task_id, target_agent, status, "row_not_stale", str(age)), None
    body = str(row.get("body") or "")
    if str(SPEC_RELATIVE_PATH) not in body or HANDOFF_NAME not in body:
        return None, _skip(row_index, row_task_id, target_agent, status, "body_missing_spec_or_handoff", ""), None
    spec_paths = _spec_paths(repo_root, canonical_repo)
    if not _missing(spec_paths):
        return None, _skip(row_index, row_task_id, target_agent, status, "required_spec_present", json.dumps(spec_paths)), None
    handoff_paths = _handoff_paths(state_root, target_agent, DEFAULT_MISSION_ID)
    if not _missing(handoff_paths):
        return None, _skip(row_index, row_task_id, target_agent, status, "handoff_present", json.dumps(handoff_paths)), None
    target_policy = _target_policy(state_root, target_agent, now)
    if not _target_is_stale_or_gated(target_policy, heartbeat_stale_hours):
        return None, _skip(row_index, row_task_id, target_agent, status, "target_not_stale_or_gated", json.dumps(target_policy, sort_keys=True)), None
    mission = _mission_evidence(state_root, DEFAULT_MISSION_ID)
    receipt = _receipt(
        row,
        agent_uid=agent_uid,
        age_hours=age,
        stale_after_hours=stale_after_hours,
        heartbeat_stale_hours=heartbeat_stale_hours,
        spec_paths=spec_paths,
        handoff_paths=handoff_paths,
        target_policy=target_policy,
        mission_evidence=mission,
        timestamp=timestamp,
    )
    validation = validate_task_receipt(
        receipt,
        task_id=row_task_id,
        agent_uid=agent_uid,
        status="blocked",
        require_artifact_or_evidence=True,
    )
    if not validation["valid"]:
        return None, _skip(row_index, row_task_id, target_agent, status, "block_receipt_invalid", "; ".join(validation["errors"])), None
    return (
        {
            "row_index": row_index,
            "task_id": row_task_id,
            "target_agent": target_agent,
            "mission_id": str(row.get("mission_id") or ""),
            "age_hours": age,
            "spec_paths": spec_paths,
            "handoff_paths": handoff_paths,
            "target_policy": target_policy,
            "mission_evidence": mission,
            "a2a_receipt_id": str(receipt.get("receipt_id") or ""),
            "validation": validation,
            "reason": "stale_forge_v01_missing_source_packet_and_external_target_gated",
        },
        None,
        receipt,
    )
def _skip(row_index: int, task_id: str, target_agent: str, status: str, reason: str, detail: str) -> dict[str, Any]:
    return {
        "row_index": row_index,
        "task_id": task_id,
        "target_agent": target_agent,
        "status": status,
        "reason": reason,
        "detail": detail,
    }
def build_report(
    state_root: Path | str | None = None,
    *,
    apply: bool = False,
    agent_uid: str = DEFAULT_AGENT_UID,
    task_id: str = DEFAULT_TASK_ID,
    stale_after_hours: float = DEFAULT_STALE_HOURS,
    heartbeat_stale_hours: float = DEFAULT_HEARTBEAT_STALE_HOURS,
    timestamp: str | None = None,
    output: Path | None = None,
    repo_root: Path = REPO_ROOT,
    canonical_repo: Path | None = Path("/Users/dhyana/dharma_swarm"),
) -> dict[str, Any]:
    ts = timestamp or _utc_now()
    now = _parse_time(ts) or datetime.now(timezone.utc)
    state = Path(state_root) if state_root is not None else None
    rows = read_queue(state)
    actions: list[dict[str, Any]] = []
    skips: list[dict[str, Any]] = []
    receipts_by_index: dict[int, dict[str, Any]] = {}
    for index, row in enumerate(rows):
        action, skip, receipt = _candidate(
            row,
            row_index=index,
            agent_uid=agent_uid,
            task_id=task_id,
            stale_after_hours=stale_after_hours,
            heartbeat_stale_hours=heartbeat_stale_hours,
            now=now,
            timestamp=ts,
            state_root=state,
            repo_root=repo_root,
            canonical_repo=canonical_repo,
        )
        if action is not None and receipt is not None:
            actions.append(action)
            receipts_by_index[index] = receipt
        if skip is not None:
            skips.append(skip)
    report = _report(
        state,
        apply=apply,
        agent_uid=agent_uid,
        task_id=task_id,
        stale_after_hours=stale_after_hours,
        heartbeat_stale_hours=heartbeat_stale_hours,
        timestamp=ts,
        actions=actions,
        skips=skips,
        receipts_by_index=receipts_by_index,
    )
    if output is not None:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report
def _report(
    state: Path | None,
    *,
    apply: bool,
    agent_uid: str,
    task_id: str,
    stale_after_hours: float,
    heartbeat_stale_hours: float,
    timestamp: str,
    actions: list[dict[str, Any]],
    skips: list[dict[str, Any]],
    receipts_by_index: dict[int, dict[str, Any]],
) -> dict[str, Any]:
    queue = queue_path(state)
    backup_path = ""
    applied: list[dict[str, Any]] = []
    if apply and actions:
        backup = queue.with_name(f"{queue.name}.a2a-stale-forge-v01-block-{_safe_timestamp(timestamp)}.bak")
        shutil.copy2(queue, backup)
        backup_path = str(backup)
        for action in actions:
            closed = close_task(
                action["task_id"],
                agent_uid=agent_uid,
                status="blocked",
                receipt=receipts_by_index[action["row_index"]],
                state_root=state,
                closed_via="a2a_block_stale_forge_v01",
                require_artifact_or_evidence=True,
                now=timestamp,
            )
            applied.append(
                {
                    "task_id": action["task_id"],
                    "status": closed.get("status"),
                    "receipt_id": closed.get("receipt_id"),
                    "target_agent": action["target_agent"],
                }
            )
    readiness = evaluate_a2a_readiness(state)
    return {
        "schema_version": 1,
        "generated_at": timestamp,
        "queue_path": str(queue),
        "applied": apply,
        "backup_path": backup_path,
        "agent_uid": agent_uid,
        "task_id": task_id,
        "stale_after_hours": stale_after_hours,
        "heartbeat_stale_hours": heartbeat_stale_hours,
        "candidate_count": len(actions),
        "applied_count": len(applied),
        "skip_count": len(skips),
        "actions": actions,
        "skips": skips,
        "applied_rows": applied,
        "post_readiness": {
            "ready": readiness.ready,
            "open_tasks": readiness.open_tasks,
            "unknown_status_tasks": readiness.unknown_status_tasks,
            "unverified_closed_tasks": readiness.unverified_closed_tasks,
            "reasons": list(readiness.reasons),
        },
    }
def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="Mutate the live queue after writing a backup.")
    parser.add_argument("--state-root", type=Path, default=None, help="Override DHARMA state root.")
    parser.add_argument("--agent-uid", default=DEFAULT_AGENT_UID)
    parser.add_argument("--task-id", default=DEFAULT_TASK_ID)
    parser.add_argument("--stale-after-hours", type=float, default=DEFAULT_STALE_HOURS)
    parser.add_argument("--heartbeat-stale-hours", type=float, default=DEFAULT_HEARTBEAT_STALE_HOURS)
    parser.add_argument("--timestamp", default=None)
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    parser.add_argument("--canonical-repo", type=Path, default=Path("/Users/dhyana/dharma_swarm"))
    return parser
def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    report = build_report(
        state_root=args.state_root,
        apply=args.apply,
        agent_uid=args.agent_uid,
        task_id=args.task_id,
        stale_after_hours=args.stale_after_hours,
        heartbeat_stale_hours=args.heartbeat_stale_hours,
        timestamp=args.timestamp,
        output=args.output,
        repo_root=args.repo_root,
        canonical_repo=args.canonical_repo,
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0
if __name__ == "__main__":
    raise SystemExit(main())
