"""Compatibility text renderers for terminal bridge payloads."""

from __future__ import annotations

from pathlib import Path
from typing import Any


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
            lines.append(f"- {name}: {', '.join(str(item) for item in values) if values else 'none'}")
    async_commands = graph.get("async_commands", [])
    if isinstance(async_commands, list):
        lines.extend(["", "## Async lanes", ", ".join(str(item) for item in async_commands) if async_commands else "none"])
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


def render_operator_snapshot_text(snapshot: dict[str, Any], *, default_runtime_db: Path) -> str:
    overview = snapshot.get("overview", {})
    runs = snapshot.get("runs", [])
    actions = snapshot.get("actions", [])
    lines = [
        "# Operator Snapshot",
        f"Runtime DB: {snapshot.get('runtime_db', str(default_runtime_db))}",
    ]
    error = str(snapshot.get("error", "") or "").strip()
    if error:
        lines.append(f"Error: {error}")
        return "\n".join(lines)
    if isinstance(overview, dict):
        lines.extend(
            [
                f"Sessions: {overview.get('sessions', 0)}",
                f"Claims: {overview.get('claims', 0)} | active {overview.get('active_claims', 0)} | acked {overview.get('acknowledged_claims', 0)}",
                f"Runs: {overview.get('runs', 0)} | active {overview.get('active_runs', 0)}",
                f"Artifacts: {overview.get('artifacts', 0)} | promoted facts {overview.get('promoted_facts', 0)}",
                f"Context bundles: {overview.get('context_bundles', 0)} | operator actions {overview.get('operator_actions', 0)}",
            ]
        )
    lines.extend(["", "## Active runs"])
    if isinstance(runs, list) and runs:
        for run in runs[:8]:
            if not isinstance(run, dict):
                continue
            lines.append(
                "- {assigned_to} | {status} | task {task_id} | run {run_id}".format(
                    assigned_to=str(run.get("assigned_to", "?")),
                    status=str(run.get("status", "?")),
                    task_id=str(run.get("task_id", ""))[:18],
                    run_id=str(run.get("run_id", ""))[:12],
                )
            )
    else:
        lines.append("none")
    lines.extend(["", "## Recent operator actions"])
    if isinstance(actions, list) and actions:
        for action in actions[:8]:
            if not isinstance(action, dict):
                continue
            lines.append(
                "- {action_name} by {actor} | task {task_id} | {reason}".format(
                    action_name=str(action.get("action_name", "?")),
                    actor=str(action.get("actor", "?")),
                    task_id=str(action.get("task_id", ""))[:18] or "-",
                    reason=str(action.get("reason", "") or "").strip() or "no reason",
                )
            )
    else:
        lines.append("none")
    return "\n".join(lines)


def render_model_policy_text(policy: dict[str, Any]) -> str:
    lines = [
        "# Model Policy",
        f"Active: {policy.get('active_label', policy.get('selected_model', 'unknown'))}",
        f"Route: {policy.get('selected_route', 'unknown')}",
        f"Strategy: {policy.get('strategy', 'responsive')}",
        f"Default route: {policy.get('default_route', 'unknown')}",
        "",
        "Available models:",
        "",
        "## Fallback chain",
    ]
    chain = policy.get("fallback_chain", [])
    if isinstance(chain, list) and chain:
        for item in chain[:6]:
            if not isinstance(item, dict):
                continue
            lines.append(f"- {item.get('label', item.get('alias', '?'))} [{item.get('provider', '?')}]")
    else:
        lines.append("none")
    lines.extend(["", "## Targets"])
    targets = policy.get("targets", [])
    if isinstance(targets, list):
        for item in targets:
            if not isinstance(item, dict):
                continue
            lines.append(f"- {item.get('alias', '?')} -> {item.get('label', '?')}")
    return "\n".join(lines)


def render_agent_routes_text(routes: dict[str, Any] | list[dict[str, Any]]) -> str:
    lines = ["# Agent Routes", "", "## Route profiles"]
    route_items = routes if isinstance(routes, list) else routes.get("routes", [])
    if isinstance(route_items, list):
        for item in route_items:
            if not isinstance(item, dict):
                continue
            primary = item.get("primary", {})
            if isinstance(primary, dict):
                provider = primary.get("provider", item.get("provider", "?"))
                model_alias = primary.get("model", item.get("model_alias", "?"))
            else:
                provider = item.get("provider", "?")
                model_alias = item.get("model_alias", "?")
            lines.append(
                "- {intent} -> {provider}:{model_alias} | effort {reasoning} | role {role}".format(
                    intent=str(item.get("intent", "?")),
                    provider=str(provider),
                    model_alias=str(model_alias),
                    reasoning=str(item.get("reasoning", "?")),
                    role=str(item.get("role", "?")),
                )
            )
    openclaw = routes.get("openclaw", {}) if isinstance(routes, dict) else {}
    if isinstance(openclaw, dict):
        lines.extend(
            [
                "",
                "## OpenClaw",
                f"Present: {openclaw.get('present', False)}",
                f"Readable: {openclaw.get('readable', False)}",
                f"Agents: {openclaw.get('agents_count', 0)}",
                f"Providers: {', '.join(str(item) for item in openclaw.get('providers', [])) if openclaw.get('providers') else 'none'}",
            ]
        )
    return "\n".join(lines)


def render_evolution_surface_text(surface: dict[str, Any]) -> str:
    lines = ["# Evolution Surface", "", "## Cascade domains"]
    domains = surface.get("domains", [])
    if isinstance(domains, list):
        for item in domains:
            if not isinstance(item, dict):
                continue
            lines.append(
                "- {name} | threshold {fitness_threshold} | max_iter {max_iterations} | max_duration {max_duration_seconds}s".format(
                    name=str(item.get("name", "?")),
                    fitness_threshold=str(item.get("fitness_threshold", "?")),
                    max_iterations=str(item.get("max_iterations", "?")),
                    max_duration_seconds=str(item.get("max_duration_seconds", "?")),
                )
            )
    lines.extend(["", "## Entry commands"])
    entries = surface.get("entry_commands", [])
    if isinstance(entries, list):
        for entry in entries:
            lines.append(f"- {entry}")
    lines.extend(["", "## Principles"])
    principles = surface.get("principles", [])
    if isinstance(principles, list):
        for principle in principles:
            lines.append(f"- {principle}")
    return "\n".join(lines)


def render_session_catalog_text(catalog: dict[str, Any]) -> str:
    lines = ["# Session Catalog", f"Sessions: {catalog.get('count', 0)}", "", "## Recent sessions"]
    sessions = catalog.get("sessions", [])
    if isinstance(sessions, list) and sessions:
        for item in sessions[:12]:
            if not isinstance(item, dict):
                continue
            session = item.get("session")
            if session is None:
                continue
            metadata = session.get("metadata", {}) if isinstance(session, dict) else {}
            lines.append(
                "- {session_id} | {provider_id}:{model_id} | {status} | turns {turns} | replay {replay}".format(
                    session_id=session.get("session_id", "?") if isinstance(session, dict) else getattr(session, "session_id", "?"),
                    provider_id=session.get("provider_id", "?") if isinstance(session, dict) else getattr(session, "provider_id", "?"),
                    model_id=session.get("model_id", "?") if isinstance(session, dict) else getattr(session, "model_id", "?"),
                    status=session.get("status", "?") if isinstance(session, dict) else getattr(session, "status", "?"),
                    turns=str(metadata.get("total_turns", item.get("total_turns", 0))),
                    replay="ok" if bool(item.get("replay_ok")) else "issues",
                )
            )
    else:
        lines.append("none")
    return "\n".join(lines)


def render_session_detail_text(detail: dict[str, Any]) -> str:
    session = detail.get("session")
    compact = detail.get("compaction_preview", {})
    session_id = session.get("session_id", "?") if isinstance(session, dict) else getattr(session, "session_id", "?")
    provider_id = session.get("provider_id", "?") if isinstance(session, dict) else getattr(session, "provider_id", "?")
    model_id = session.get("model_id", "?") if isinstance(session, dict) else getattr(session, "model_id", "?")
    status = session.get("status", "?") if isinstance(session, dict) else getattr(session, "status", "?")
    cwd = session.get("cwd", "?") if isinstance(session, dict) else getattr(session, "cwd", "?")
    lines = [
        "# Session Detail",
        f"Session: {session_id}",
        f"Route: {provider_id}:{model_id}",
        f"Status: {status}",
        f"CWD: {cwd}",
        f"Replay: {'ok' if detail.get('replay_ok') else 'issues'}",
        "",
        "## Compaction preview",
        f"Events: {compact.get('event_count', 0)}",
        f"Compactable ratio: {compact.get('compactable_ratio', 0.0)}",
        f"Protected: {', '.join(str(item) for item in compact.get('protected_event_types', [])) or 'none'}",
        "",
        "## Recent event types",
        ", ".join(str(item) for item in compact.get("recent_event_types", [])) or "none",
    ]
    issues = detail.get("replay_issues", [])
    lines.extend(["", "## Replay issues"])
    if isinstance(issues, list) and issues:
        for issue in issues[:8]:
            lines.append(f"- {issue}")
    else:
        lines.append("none")
    return "\n".join(lines)
