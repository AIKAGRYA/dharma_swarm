"""Shell-neutral command graph and registry payload builders."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

COMMAND_CATEGORIES: dict[str, list[str]] = {
    "chat": ["cancel", "chat", "clear", "copy", "copylast", "paste", "reset", "thread"],
    "repo": ["git"],
    "runtime": ["runtime"],
    "control": ["health", "pulse", "self", "status"],
    "ontology": ["context", "corpus", "dharma", "evidence", "foundations", "telos"],
    "memory": ["archive", "darwin", "logs", "memory", "notes", "stigmergy", "truth"],
    "swarm": ["agni", "gates", "hum", "swarm", "witness"],
}

COMMAND_DESCRIPTIONS: dict[str, str] = {
    "archive": "Evolution archive",
    "chat": "Native chat continuation control",
    "context": "Show agent context layers",
    "darwin": "Darwin experiment memory and trust ladder",
    "dharma": "Dharma doctrine and operator orientation",
    "evolve": "Darwin Engine evolution",
    "foundations": "Foundational pillars",
    "gates": "Test telos gates",
    "git": "Repo branch/head/dirty counts",
    "health": "Ecosystem health check",
    "memory": "Strange loop memory and latent gold",
    "model": "Model routing control",
    "notes": "Shared agent notes",
    "plan": "Plan-mode control",
    "pulse": "Run heartbeat",
    "runtime": "Live process and runtime matrix",
    "self": "System self-map",
    "status": "Full system status panel",
    "swarm": "Swarm operations and report lanes",
    "telos": "Telos Engine research docs",
    "thread": "Show or set research thread",
}

COMMAND_TARGET_PANES: dict[str, str] = {
    "chat": "chat",
    "repo": "repo",
    "runtime": "runtime",
    "control": "control",
    "ontology": "ontology",
    "memory": "sessions",
    "swarm": "agents",
}


def build_command_graph_summary(
    all_commands: Iterable[str],
    async_commands: Iterable[str],
) -> dict[str, Any]:
    """Build the canonical command graph summary consumed by operator shells."""

    commands = sorted(set(all_commands))
    async_command_names = sorted(set(async_commands))
    return {
        "count": len(commands),
        "async_count": len(async_command_names),
        "commands": commands,
        "async_commands": async_command_names,
        "categories": {name: sorted(values) for name, values in COMMAND_CATEGORIES.items()},
    }


def build_command_registry_payload(
    all_commands: Iterable[str],
    async_commands: Iterable[str],
) -> dict[str, Any]:
    """Build the canonical command registry payload consumed by operator shells."""

    async_command_names = set(async_commands)
    categories = build_command_graph_summary(all_commands, async_command_names)["categories"]
    records: list[dict[str, Any]] = []
    for name in sorted(set(all_commands)):
        category = next((category_name for category_name, commands in categories.items() if name in commands), "control")
        records.append(
            {
                "name": name,
                "async": name in async_command_names,
                "category": category,
                "target_pane": COMMAND_TARGET_PANES.get(category, "control"),
                "description": COMMAND_DESCRIPTIONS.get(name, "Dharma operator command"),
            }
        )
    return {
        "count": len(records),
        "commands": records,
    }
