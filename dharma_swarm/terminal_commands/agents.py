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


def _cmd_agent_wake(name: str, task: str, model: str | None) -> None:
    """Wake an autonomous agent with a task."""
    from dharma_swarm.autonomous_agent import cli_wake
    asyncio.run(cli_wake(name, task, model=model))


def _cmd_agent_list() -> None:
    """List available preset agents."""
    from dharma_swarm.autonomous_agent import PRESET_AGENTS
    print("Available autonomous agents:")
    print()
    for name, identity in PRESET_AGENTS.items():
        tools = ", ".join(identity.allowed_tools)
        print(f"  {name:<12} role={identity.role:<12} model={identity.model}")
        print(f"  {'':12} cwd={identity.working_directory}")
        print(f"  {'':12} tools=[{tools}]")
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
