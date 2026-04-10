"""Context and prompt helpers for the Dharma terminal bridge."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any


def load_repo_guidance(repo_root: Path, limit_chars: int = 2400) -> str:
    guidance_path = repo_root / "CLAUDE.md"
    try:
        text = guidance_path.read_text(encoding="utf-8").strip()
    except OSError:
        return ""
    if not text:
        return ""
    sections = summarize_repo_guidance(text)
    text = sections or text
    if len(text) <= limit_chars:
        return text
    return text[: limit_chars - 1].rstrip() + "…"


def summarize_repo_guidance(text: str) -> str:
    lines = text.splitlines()
    kept: list[str] = []
    current_heading = ""
    allowed_headings = {
        "## Behavioral Rules (Always Enforced)",
        "## File Organization",
        "## Project Architecture",
        "## CLI Entry Points",
        "## Security Rules",
    }
    for line in lines:
        stripped = line.rstrip()
        if stripped.startswith("## "):
            current_heading = stripped
            if current_heading in allowed_headings:
                kept.append(stripped)
            continue
        if current_heading not in allowed_headings:
            continue
        if (
            stripped.startswith("- ")
            or stripped.startswith("```")
            or stripped.startswith("dgc ")
            or stripped.startswith("uvicorn ")
            or stripped.startswith("bash ")
        ):
            kept.append(stripped)
    return "\n".join(line for line in kept if line)


def load_session_context_hint() -> str:
    try:
        from dharma_swarm.claude_hooks import session_context

        return session_context().strip()
    except Exception:
        return ""


def memory_path(state_dir: Path) -> Path:
    return state_dir / "working_memory.json"


def load_working_memory(state_dir: Path) -> dict[str, Any]:
    path = memory_path(state_dir)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {
            "recent_turns": [],
            "recent_actions": [],
            "active_mission": "",
            "preferred_route": "",
            "updated_at": "",
        }
    if not isinstance(payload, dict):
        return {
            "recent_turns": [],
            "recent_actions": [],
            "active_mission": "",
            "preferred_route": "",
            "updated_at": "",
        }
    payload.setdefault("recent_turns", [])
    payload.setdefault("recent_actions", [])
    payload.setdefault("active_mission", "")
    payload.setdefault("preferred_route", "")
    payload.setdefault("updated_at", "")
    return payload


def save_working_memory(state_dir: Path, payload: dict[str, Any]) -> None:
    state_dir.mkdir(parents=True, exist_ok=True)
    payload["updated_at"] = datetime.now(timezone.utc).isoformat()
    memory_path(state_dir).write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8")


def apply_turn_to_memory(
    memory: dict[str, Any],
    *,
    prompt: str,
    intent: dict[str, Any],
    route: str,
    active_tab: str,
) -> dict[str, Any]:
    turns = memory.get("recent_turns", [])
    if not isinstance(turns, list):
        turns = []
    turns.append(
        {
            "prompt": prompt,
            "intent": str(intent.get("kind", "chat")),
            "route": route,
            "active_tab": active_tab,
        }
    )
    memory["recent_turns"] = turns[-8:]
    if str(intent.get("kind", "")) in {"agent", "evolution", "command"}:
        memory["active_mission"] = prompt[:200]
    memory["preferred_route"] = route
    return memory


def remember_turn(
    state_dir: Path,
    *,
    prompt: str,
    intent: dict[str, Any],
    route: str,
    active_tab: str,
) -> None:
    memory = load_working_memory(state_dir)
    apply_turn_to_memory(memory, prompt=prompt, intent=intent, route=route, active_tab=active_tab)
    save_working_memory(state_dir, memory)


def remember_action(state_dir: Path, summary: str) -> None:
    memory = load_working_memory(state_dir)
    actions = memory.get("recent_actions", [])
    if not isinstance(actions, list):
        actions = []
    actions.append(summary)
    memory["recent_actions"] = [str(item) for item in actions][-8:]
    save_working_memory(state_dir, memory)


def render_working_memory(memory: dict[str, Any]) -> str:
    turns = memory.get("recent_turns", [])
    actions = memory.get("recent_actions", [])
    active_mission = str(memory.get("active_mission", "") or "").strip() or "none"
    preferred_route = str(memory.get("preferred_route", "") or "").strip() or "none"
    lines = [
        f"Active mission: {active_mission}",
        f"Preferred route: {preferred_route}",
    ]
    if isinstance(turns, list) and turns:
        lines.append("Recent turns:")
        for item in turns[-4:]:
            if not isinstance(item, dict):
                continue
            lines.append(
                "- {intent} | {route} | {prompt}".format(
                    intent=str(item.get("intent", "chat")),
                    route=str(item.get("route", "unknown")),
                    prompt=str(item.get("prompt", ""))[:100],
                )
            )
    if isinstance(actions, list) and actions:
        lines.append("Recent actions:")
        for action in actions[-4:]:
            lines.append(f"- {str(action)[:120]}")
    return "\n".join(lines)


def render_system_prompt(
    *,
    prompt: str,
    active_tab: str,
    intent: dict[str, Any],
    selected_provider: str,
    selected_model: str,
    routing_strategy: str,
    command_graph: dict[str, Any],
    model_policy: dict[str, Any],
    orientation_packet: dict[str, Any],
    workspace_snapshot: str,
    ontology_snapshot: str,
    runtime_snapshot: str,
    repo_guidance: str,
    session_context_hint: str,
    working_memory: str,
) -> str:
    command_categories = command_graph.get("categories", {})
    command_lines = []
    for name, commands in command_categories.items():
        if isinstance(commands, list) and commands:
            command_lines.append(f"- {name}: {', '.join(str(item) for item in commands[:8])}")

    lines = [
        "# Dharma Terminal Bootstrap",
        "",
        "Identity:",
        "- You are not a detached chatbot. You are the Dharma Swarm operator intelligence speaking from inside the repo and control plane.",
        "- Treat the repo, ontology, runtime state, command graph, model policy, and swarm routes as your own appendages.",
        "- When the user asks what you can do, answer in terms of Dharma-native commands, panes, agents, models, and repo actions available right now.",
        "- If a native command, pane refresh, model switch, or operator action is the right move, prefer it over generic prose.",
        "- Your tone should feel like the system itself: specific, grounded, operational, and aware of local topology.",
        "",
        "Turn context:",
        f"- Prompt: {prompt}",
        f"- Active tab: {active_tab}",
        f"- Intent: {intent.get('kind', 'chat')}",
        f"- Selected route: {selected_provider}:{selected_model}",
        f"- Routing strategy: {routing_strategy}",
        "",
        "Model policy:",
        f"- Default route: {model_policy.get('default_route', 'unknown')}",
        f"- Strategies: {', '.join(str(item) for item in model_policy.get('strategies', []))}",
        f"- Available model targets: {', '.join(str(item.get('alias', '?')) for item in model_policy.get('targets', [])[:10])}",
        "",
        "Command graph:",
        *command_lines,
        "",
        "Behavioral rules:",
        "- If the user asks for a model change, perform the switch and explain the new route briefly.",
        "- If the user asks for status, topology, runtime, memory, agents, or evolution state, prefer the corresponding Dharma surface over generic explanation.",
        "- If the user asks who you are, answer as Dharma Swarm's operator intelligence for this repo, not as an abstract assistant.",
        "- When helpful, restate the available command or pane that matches the request.",
        "",
        "Repo guidance (always-loaded doctrine):",
        repo_guidance or "(no CLAUDE.md guidance found)",
        "",
        "Session context hint:",
        session_context_hint or "(no session context hint available)",
        "",
        "Working memory:",
        working_memory or "(no working memory yet)",
        "",
        "Orientation packet:",
        json.dumps(orientation_packet, indent=2, ensure_ascii=True),
        "",
        "Workspace snapshot:",
        workspace_snapshot,
        "",
        "Ontology snapshot:",
        ontology_snapshot,
        "",
        "Runtime snapshot:",
        runtime_snapshot,
    ]
    return "\n".join(lines)
