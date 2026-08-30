"""Agent and task management commands."""

from __future__ import annotations

import asyncio
import json
import sys


# ---------------------------------------------------------------------------
# Commands from dharma_swarm Typer CLI
# ---------------------------------------------------------------------------


from dharma_swarm.terminal_commands._helpers import (
    DHARMA_STATE,
    _get_swarm,
    _get_task_board,
    _run,
    dharma_state_dir,
)

def cmd_spawn(name: str, role: str, model: str) -> None:
    """Spawn a new agent."""
    async def _spawn():
        from dharma_swarm.models import AgentRole

        swarm = await _get_swarm()
        try:
            agent_role = AgentRole(role)
        except ValueError:
            print(f"Invalid role: {role}. Choose from: {[r.value for r in AgentRole]}")
            await swarm.shutdown()
            sys.exit(1)
        state = await swarm.spawn_agent(name=name, role=agent_role, model=model)
        print(f"Spawned agent: {state.name} ({state.role.value}) -- ID: {state.id}")
        await swarm.shutdown()

    _run(_spawn())


def _cmd_agent_wake(
    name: str, task: str, model: str | None, provider: str | None = None,
) -> None:
    """Wake an autonomous agent with a task; process exit code = wake exit code."""
    from dharma_swarm.autonomous_agent import cli_wake
    sys.exit(asyncio.run(cli_wake(name, task, model=model, provider=provider)))


def _cmd_agent_list() -> None:
    """List available preset agents and registered sovereign holons."""
    from dharma_swarm.autonomous_agent import PRESET_AGENTS
    print("Available autonomous agents:")
    print()
    for name, identity in PRESET_AGENTS.items():
        tools = ", ".join(identity.allowed_tools)
        print(
            f"  {name:<12} role={identity.role:<12} "
            f"provider={identity.provider:<12} model={identity.model}"
        )
        print(f"  {'':12} cwd={identity.working_directory}")
        print(f"  {'':12} tools=[{tools}]")
        print()

    try:
        from dharma_swarm.holon_health import holon_health_rows
        rows = holon_health_rows()
    except Exception:  # noqa: BLE001 — listing presets must not fail on holon issues
        rows = []
    if rows:
        print("Registered sovereign holons (~/.dharma/agents — dgc agent talk/run/status/kill):")
        for row in rows:
            kill = "  KILL-REQUESTED" if row.get("kill_requested") else ""
            print(
                f"  {row.get('name', '-'):<24} model={row.get('model') or '-':<24} "
                f"compass_signals={row.get('compass_signal_count', 0)}{kill}"
            )
        print()


def _cmd_agent_runs() -> None:
    """Show recent agent run reports."""
    report_dir = dharma_state_dir() / "agent_runs"
    if not report_dir.exists():
        print("No agent runs yet.")
        return
    for report_file in sorted(report_dir.glob("*_latest.json")):
        try:
            data = json.loads(report_file.read_text())
            print(
                f"  {data['agent']:<12} {data['turns']} turns, "
                f"{data.get('tokens_in', 0) + data.get('tokens_out', 0)} tokens, "
                f"{data['tool_calls']} tools, {data['duration_s']:.1f}s"
            )
            print(f"  {'':12} task: {data['task'][:80]}")
            if data.get("errors"):
                print(f"  {'':12} errors: {data['errors']}")
            print()
        except Exception:
            pass


def _ensure_repo_root_on_path() -> None:
    # scripts/ is a plain directory at the repo root, so `from scripts...`
    # only resolves when the repo root is on sys.path. Interactive runs from
    # the repo root get that for free; the installed `dgc` console script does
    # not (its sys.path[0] is the venv bin dir), which made every
    # `dgc agent talk|run` die with ModuleNotFoundError: scripts.
    from pathlib import Path

    repo_root = str(Path(__file__).resolve().parents[2])
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)


def _cmd_agent_talk(
    name: str,
    message: str,
    *,
    routing_mode: str = "declared-first",
    max_tokens: int = 400,
) -> None:
    """Talk to a registered sovereign holon through the explicit routing mode."""
    _ensure_repo_root_on_path()
    from scripts.holon_talk import talk

    rc = asyncio.run(
        talk(name, message, routing_mode=routing_mode, max_tokens=max_tokens)
    )
    if rc != 0:
        raise SystemExit(rc)


def _cmd_agent_run(
    name: str,
    *,
    cycles: int = 1,
    routing_mode: str = "declared-first",
) -> None:
    """Run governed cycles for a registered sovereign holon."""
    _ensure_repo_root_on_path()
    from scripts.holon_run import run

    rc = asyncio.run(run(name, cycles, routing_mode=routing_mode))
    if rc != 0:
        raise SystemExit(rc)


def _cmd_agent_kill(name: str, *, reason: str = "", clear: bool = False) -> None:
    """Raise (or clear) the durable kill signal for a registered holon (U7).

    The governed wake loop checks this signal at the top of every cycle and halts.
    Pure file signaling via ``holon_killswitch`` — animates nothing.
    """
    from dharma_swarm import holon_killswitch

    if clear:
        existed = holon_killswitch.clear_kill(name)
        print(f"{'Cleared' if existed else 'No'} kill signal for {name}.")
        return
    path = holon_killswitch.request_kill(name, reason=reason)
    print(f"Kill requested for {name} (wake loop halts at next cycle): {path}")


def _cmd_agent_status(name: str | None, *, as_json: bool = False) -> None:
    """Show read-only health for one holon or all registered holons."""
    from dharma_swarm.holon_health import holon_health_rows, holon_status

    payload: dict | list[dict]
    payload = holon_status(name) if name else holon_health_rows()
    if as_json:
        print(json.dumps(payload, indent=2, sort_keys=True))
        return

    rows = [payload] if name else payload
    if not rows:
        print("No registered holons.")
        return

    print("Holon health (read-only):")
    for row in rows:
        registered = "yes" if row.get("registered") else "no"
        kill = "yes" if row.get("kill_requested") else "no"
        print(
            f"  {row.get('name', '-'):<24} "
            f"registered={registered:<3} "
            f"model={row.get('model') or '-'} "
            f"kill={kill:<3} "
            f"compass_signals={row.get('compass_signal_count', 0)}"
        )

# ---------------------------------------------------------------------------
# Main dispatch
# ---------------------------------------------------------------------------


def cmd_task_create(title: str, description: str, priority: str) -> None:
    """Create a new task (thin path — no full swarm boot)."""
    async def _create():
        from dharma_swarm.models import TaskPriority

        try:
            p = TaskPriority(priority)
        except ValueError:
            print(f"Invalid priority: {priority}")
            sys.exit(1)
        tb = await _get_task_board(state_dir=str(DHARMA_STATE))
        task = await tb.create(title=title, description=description, priority=p)
        print(f"Created task: {task.title} -- ID: {task.id}")

    _run(_create())


def cmd_task_list(status_filter: str | None) -> None:
    """List tasks (thin path — no full swarm boot)."""
    async def _list():
        from dharma_swarm.models import TaskStatus

        tb = await _get_task_board(state_dir=str(DHARMA_STATE))
        s = TaskStatus(status_filter) if status_filter else None
        tasks = await tb.list_tasks(status=s)
        if not tasks:
            print("No tasks.")
        else:
            print(f"{'ID':>8}  {'STATUS':<10}  {'PRI':<8}  {'ASSIGNED':<10}  TITLE")
            print("-" * 70)
            for t in tasks:
                print(f"{t.id[:8]}  {t.status.value:<10}  {t.priority.value:<8}  {(t.assigned_to or '-'):<10}  {t.title}")

    _run(_list())
