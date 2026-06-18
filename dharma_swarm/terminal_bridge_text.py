"""Terminal bridge text renderers — pure data-to-string functions extracted from TerminalBridge.

Rule 10 compliance: extracted from terminal_bridge.py to keep that file under the 2,411 LOC ceiling.
These are pure functions with zero TerminalBridge dependencies.
"""

from typing import Any


def render_working_memory(memory: dict[str, Any]) -> str:
    if not isinstance(memory, dict):
        return ""
    parts: list[str] = []
    previous = memory.get("previous", {})
    if isinstance(previous, dict) and previous:
        parts.append("[Previous turn]")
        for key, val in previous.items():
            parts.append(f"  {key}: {val}")
        parts.append("")
    running = memory.get("running_context", "")
    if isinstance(running, str) and running.strip():
        parts.append(f"[Running context]\n{running}")
    return "\n".join(parts)


def render_git_summary_lines(git_summary: dict[str, Any]) -> list[str]:
    lines: list[str] = []
    if not isinstance(git_summary, dict):
        return lines
    lines.append(f"Branch: {git_summary.get('branch', 'unknown')}")
    lines.append(f"Commits ahead: {git_summary.get('ahead', '?')}")
    lines.append(f"Commits behind: {git_summary.get('behind', '?')}")
    dirty = git_summary.get("dirty_count", 0)
    lines.append(f"Dirty files: {dirty}")
    recent = git_summary.get("recent_commits", [])
    if isinstance(recent, list) and recent:
        lines.append("Recent commits:")
        for commit in recent[:5]:
            if isinstance(commit, dict):
                sha = str(commit.get("sha", ""))[:8]
                subject = str(commit.get("subject", ""))[:80]
                lines.append(f"  {sha} {subject}")
    return lines


def render_system_prompt(
    *,
    prompt: str,
    provider: str = "codex",
    model: str = "gpt-5.4",
    repo_root: str = "/Users/dhyana/dharma_swarm",
    workspace_preview: dict[str, Any] | None = None,
    runtime_preview: dict[str, Any] | None = None,
    command_graph: dict[str, Any] | None = None,
    intent: dict[str, Any] | None = None,
) -> str:
    wsp = workspace_preview or {}
    rtp = runtime_preview or {}
    cg = command_graph or {}
    intent_kind = (intent or {}).get("intent_kind", "chat")

    branch = str(wsp.get("Branch", "unknown"))
    dirty = str(wsp.get("Dirty files", "unknown"))
    ahead = str(wsp.get("Commits ahead", "unknown"))
    behind = str(wsp.get("Commits behind", "unknown"))
    repo_risk = str(wsp.get("Repo risk", "unknown"))
    active_tab = str(wsp.get("Active tab", "chat"))
    active_track = str(wsp.get("Active track", "none"))

    runtime_activity = str(rtp.get("Runtime activity", "none"))
    agents_running = str(rtp.get("Agents running", "0"))
    cron_jobs = str(rtp.get("Cron jobs", "0"))

    lines = [
        f"You are a dharma_swarm operator intelligence running via the {provider}:{model} route.",
        "",
        "## Workspace state",
        f"- Repo root: {repo_root}",
        f"- Branch: {branch}",
        f"- Dirty: {dirty} ahead={ahead} behind={behind}",
        f"- Repo risk: {repo_risk}",
        f"- Active tab: {active_tab}",
        f"- Active track: {active_track}",
        "",
        "## Runtime state",
        f"- Activity: {runtime_activity}",
        f"- Agents running: {agents_running}",
        f"- Cron jobs: {cron_jobs}",
        "",
        "## Intent",
        f"- Kind: {intent_kind}",
        "",
        f"## Prompt",
        prompt,
    ]
    return "\n".join(lines)


def render_command_graph_text(graph: dict[str, Any]) -> str:
    lines = [
        "# Command Graph",
        f"Command count: {graph.get('count', 0)}",
        f"Async commands: {graph.get('async_count', 0)}",
        "",
        "## Categories",
    ]
    categories = graph.get("categories", {})
    if isinstance(categories, dict):
        for name, commands in categories.items():
            values = commands if isinstance(commands, list) else []
            lines.append(
                f"- {name}: {', '.join(str(item) for item in values) if values else 'none'}"
            )
    async_commands = graph.get("async_commands", [])
    if isinstance(async_commands, list):
        lines.extend(
            [
                "",
                "## Async lanes",
                ", ".join(str(item) for item in async_commands) if async_commands else "none",
            ]
        )
    return "\n".join(lines)


def render_command_registry_text(registry: dict[str, Any]) -> str:
    lines = ["# Command Registry", f"Commands: {registry.get('count', 0)}", "", "## Commands"]
    commands = registry.get("commands", [])
    if isinstance(commands, list):
        for item in commands[:24]:
            if not isinstance(item, dict):
                continue
            sync_state = "async" if item.get("async") else "sync"
            lines.append(
                "- /{name} [{sync_state}] -> {target_pane} | {description}".format(
                    name=str(item.get("name", "?")),
                    sync_state=sync_state,
                    target_pane=str(item.get("target_pane", "control")),
                    description=str(item.get("description", "command")),
                )
            )
    return "\n".join(lines)


def render_operator_snapshot_text(snapshot: dict[str, Any]) -> str:
    overview = snapshot.get("overview", {})
    runs = snapshot.get("runs", [])
    actions = snapshot.get("actions", [])
    lines = [
        "# Operator Snapshot",
        f"Agent: {overview.get('agent', 'unknown')}",
        f"Started: {overview.get('started', 'unknown')}",
        f"Uptime: {overview.get('uptime', 'unknown')}",
        f"Active sessions: {overview.get('active_sessions', 0)}",
        f"Actions taken: {overview.get('actions_taken', 0)}",
        "",
        "## Recent runs",
    ]
    if isinstance(runs, list):
        for run in runs[:10]:
            if isinstance(run, dict):
                lines.append(
                    f"- {run.get('timestamp', '?')} [{run.get('intent_kind', '?')}] "
                    f"{run.get('summary', '')[:80]}"
                )
    lines.append("")
    lines.append("## Recent actions")
    if isinstance(actions, list):
        for action in actions[:10]:
            if isinstance(action, dict):
                lines.append(
                    f"- {action.get('timestamp', '?')} [{action.get('type', '?')}] "
                    f"{action.get('summary', '')[:80]}"
                )
    return "\n".join(lines)


def render_model_policy_text(policy: dict[str, Any]) -> str:
    targets = policy.get("targets", [])
    fallback_chain = policy.get("fallback_chain", [])
    lines = [
        "# Model Policy",
        f"Provider: {policy.get('selected_provider', 'unknown')}",
        f"Model: {policy.get('selected_model', 'unknown')}",
        f"Strategy: {policy.get('strategy', 'unknown')}",
        f"Route: {policy.get('selected_route', 'unknown')}",
        f"Oracle: {policy.get('oracle_state', 'unknown')}",
        "",
        "## Targets",
    ]
    if isinstance(targets, list):
        for target in targets:
            if not isinstance(target, dict):
                continue
            route = target.get("route_id") or f"{target.get('provider', '?')}:{target.get('model', '?')}"
            state = target.get("route_state", "unknown")
            reason = target.get("availability_reason")
            suffix = f" [{state}]"
            if reason:
                suffix += f" {reason}"
            lines.append(
                f"- {target.get('alias', '?')} -> {target.get('label', '?')} "
                f"({route}){suffix}"
            )
    if isinstance(fallback_chain, list):
        lines.extend(["", "## Fallbacks"])
        for item in fallback_chain:
            if isinstance(item, dict):
                route = item.get("route_id") or f"{item.get('provider', '?')}:{item.get('model', '?')}"
                lines.append(f"- {item.get('label', route)} ({route})")
    return "\n".join(lines)


def render_agent_routes_text(routes: dict[str, Any]) -> str:
    lines = [
        "# Agent Routes",
        f"Total routes: {routes.get('count', 0)}",
        f"Active: {routes.get('active_count', 0)}",
        "",
        "## Routes",
    ]
    route_list = routes.get("routes", [])
    if isinstance(route_list, list):
        for item in route_list[:16]:
            if isinstance(item, dict):
                status = "active" if item.get("active") else "inactive"
                lines.append(
                    f"- {item.get('path', '?')} [{status}] -> "
                    f"agent={item.get('agent', '?')} model={item.get('model', '?')}"
                )
    return "\n".join(lines)


def render_evolution_surface_text(surface: dict[str, Any]) -> str:
    lines = [
        "# Evolution Surface",
        f"Epoch: {surface.get('epoch', 'unknown')}",
        f"Generations: {surface.get('generations', '?')}",
        f"Active experiments: {surface.get('active_experiments', 0)}",
        "",
        "## Recent mutations",
    ]
    mutations = surface.get("recent_mutations", [])
    if isinstance(mutations, list):
        for m in mutations[:8]:
            if isinstance(m, dict):
                lines.append(
                    f"- {m.get('timestamp', '?')} [{m.get('kind', '?')}] "
                    f"{m.get('summary', '')[:80]}"
                )
    return "\n".join(lines)


def render_session_catalog_text(catalog: dict[str, Any]) -> str:
    lines = [
        "# Session Catalog",
        f"Total sessions: {catalog.get('total', 0)}",
        f"Active: {catalog.get('active', 0)}",
        "",
        "## Sessions",
    ]
    sessions = catalog.get("sessions", [])
    if isinstance(sessions, list):
        for s in sessions[:12]:
            if isinstance(s, dict):
                lines.append(
                    f"- {s.get('id', '?')} [{s.get('status', '?')}] "
                    f"started={s.get('started', '?')} model={s.get('model', '?')}"
                )
    return "\n".join(lines)


def render_session_detail_text(detail: dict[str, Any]) -> str:
    lines = [
        "# Session Detail",
        f"ID: {detail.get('id', 'unknown')}",
        f"Status: {detail.get('status', 'unknown')}",
        f"Provider: {detail.get('provider', 'unknown')}",
        f"Model: {detail.get('model', 'unknown')}",
        f"Started: {detail.get('started', 'unknown')}",
        f"Messages: {detail.get('message_count', 0)}",
        f"Active tab: {detail.get('active_tab', 'chat')}",
        "",
    ]
    intent = detail.get("last_intent")
    if isinstance(intent, dict) and intent:
        lines.append(
            "## Last intent\n"
            f"  kind={intent.get('intent_kind', '?')} "
            f"confidence={intent.get('confidence', '?')}"
        )
    return "\n".join(lines)


def render_identity_response(bootstrap: dict[str, Any], *, repo_root: str) -> str:
    workspace_preview = bootstrap.get("workspace_preview", {})
    runtime_preview = bootstrap.get("runtime_preview", {})
    if not isinstance(workspace_preview, dict):
        workspace_preview = {}
    if not isinstance(runtime_preview, dict):
        runtime_preview = {}
    route = (
        f"{bootstrap.get('selected_provider', 'codex')}:"
        f"{bootstrap.get('selected_model', 'gpt-5.4')}"
    )
    active_tab = str(bootstrap.get("active_tab", "chat"))
    commands = bootstrap.get("command_graph", {})
    categories = commands.get("categories", {}) if isinstance(commands, dict) else {}
    repo_root_val = str(workspace_preview.get("Repo root", repo_root))
    branch = str(workspace_preview.get("Branch", "unknown"))
    repo_risk = str(workspace_preview.get("Repo risk", "unknown"))
    runtime_activity = str(runtime_preview.get("Runtime activity", "none"))
    available = (
        ", ".join(str(name) for name in categories.keys())
        if isinstance(categories, dict)
        else "chat, repo, control"
    )
    return "\n".join(
        [
            "I am Dharma Swarm's operator intelligence for this workspace.",
            f"Route: {route}",
            f"Repo: {repo_root_val}",
            f"Branch: {branch}",
            f"Active tab: {active_tab}",
            f"Repo risk: {repo_risk}",
            f"Runtime: {runtime_activity}",
            f"Native surfaces: {available}",
            "I can answer in plain language, switch models, invoke Dharma-native commands, "
            "and work against repo/runtime/ontology state directly.",
        ]
    )


def render_memory_response(bootstrap: dict[str, Any] | None = None) -> str:
    if isinstance(bootstrap, dict):
        rendered = str(bootstrap.get("working_memory", "") or "").strip()
        if rendered:
            return f"# Working memory\n\n{rendered}"
    return "# Working memory\n\nNo memory data available."
