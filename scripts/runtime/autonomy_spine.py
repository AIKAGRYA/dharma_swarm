#!/usr/bin/env python3
"""Compatibility CLI for ds-goal missions backed by LivingAgentKernel wakes.

This is intentionally a bounded bridge. It creates mission/task ledgers that
can be projected into operator boards, enqueues ds_goal wakes, and runs a
finite kernel control tick. It does not start a standing daemon or replace the
existing LivingAgentKernel control loop.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dharma_swarm.operator_core.living_agent_kernel import KernelRunStore, LivingAgentKernel  # noqa: E402
from dharma_swarm.operator_core.runtime_truth import stable_payload_hash, utc_now  # noqa: E402
from dharma_swarm.board.adapters.ds_goal_adapter import load_ds_goal_cards  # noqa: E402

DEFAULT_STATE_ROOT = Path.home() / ".dharma" / "ds_goals"
DEFAULT_KERNEL_STORE = Path.home() / ".dharma" / "living_agent_kernel"
SCHEMA_VERSION = "dharma.ds_goal_spine.v1"


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


def _mission_dir(state_root: Path, mission_id: str) -> Path:
    return state_root.expanduser().resolve() / mission_id


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
    parser.add_argument("--agent-uid", default="codex_composer")
    parser.add_argument("--json", action="store_true")


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
    }
    if args.board_cards:
        payload["board_cards"] = [
            card.model_dump(mode="json")
            for card in load_ds_goal_cards(args.state_root, mission_id=args.mission_id)
        ]
    _print(payload, as_json=args.json)
    return 0


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

    kernel = LivingAgentKernel(
        store=KernelRunStore(args.kernel_store),
        workspace_root=ROOT,
    )
    wake_id = f"dsgoal-{args.mission_id}-{uuid4().hex[:8]}"
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
    _print(
        {
            "status": tick.status,
            "mission_id": args.mission_id,
            "task_id": receipt_base["task_id"],
            "wake_id": wake_id,
            "mission_dir": str(mission_dir),
            "receipt_hash": receipt["record_hash"],
            "tick": tick_payload,
        },
        as_json=args.json,
    )
    return 0 if tick.status in {"idle", "completed", "review", "blocked"} else 1


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "init":
        return cmd_init(args)
    if args.command == "status":
        return cmd_status(args)
    if args.command == "run":
        return cmd_run(args)
    raise AssertionError(f"unhandled command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
