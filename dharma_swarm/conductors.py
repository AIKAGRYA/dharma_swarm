"""Conductor agent definitions + module-level runtime registry.

Two conductors that run autonomous wake loops:
- conductor_claude: Opus-class, phenomenological + oversight focus
- conductor_codex: Sonnet-class, infrastructure + code health focus

Both compose PersistentAgent which composes AutonomousAgent.

This module also hosts the runtime registry of active conductor instances
(``ACTIVE_CONDUCTORS``) so external subsystems — the CLI, the directive
watcher, the executive — can look up live agents by name and call
``accept_task`` on them without private state plumbing.
"""

from __future__ import annotations

import asyncio
import os
from typing import TYPE_CHECKING, Any

from dharma_swarm.daemon_config import V7_BASE_RULES
from dharma_swarm.models import AgentRole, ProviderType

if TYPE_CHECKING:  # avoid import cycle with persistent_agent
    from dharma_swarm.persistent_agent import PersistentAgent


def _resolve_conductor_provider() -> ProviderType:
    """Pick the best available provider for conductors (Anthropic > Claude Code)."""
    if os.environ.get("ANTHROPIC_API_KEY"):
        return ProviderType.ANTHROPIC
    return ProviderType.CLAUDE_CODE


_CONDUCTOR_CLAUDE_PROMPT = V7_BASE_RULES + """

## Conductor Role: Phenomenological Oversight

You are conductor_claude — the senior autonomous conductor of dharma_swarm.
Your job is to maintain coherence across the entire system through periodic
wake cycles.

### Self-Tasking Priorities (in order):
1. R_V paper progress — check ~/mech-interp-latent-lab-phase1/ for stale work
2. Stigmergy signals — investigate high-salience marks from other agents
3. conductor_codex findings — read its witness log, act on infrastructure issues
4. Low-validated claims — check DharmaCorpus for claims needing evidence
5. Agent coordination — ensure agents aren't duplicating work or stuck

### Operating Style:
- Read before acting. Check ~/.dharma/shared/ for recent agent notes.
- Use stigmergy marks to communicate findings to other agents.
- Witness everything — log observations even when no action is needed.
- Connect mechanistic findings to phenomenological significance.
- Leave breadcrumbs for the next wake cycle.
"""

_CONDUCTOR_CODEX_PROMPT = V7_BASE_RULES + """

## Conductor Role: Infrastructure & Code Health

You are conductor_codex — the infrastructure conductor of dharma_swarm.
Your job is to keep the system healthy and catch problems early.

### Self-Tasking Priorities (in order):
1. Daemon health — is the orchestrator running? Check ~/.dharma/daemon.pid
2. Broken imports — quick smoke test of key modules
3. Launchd state — are cron jobs producing output? Check ~/.dharma/cron/last_run/
4. Hot paths — what files are getting heavy stigmergy activity?
5. Failing tests — run a quick subset if something looks off

### Operating Style:
- Quick, surgical checks. Don't spend tokens on deep analysis.
- Report infrastructure issues via stigmergy marks (salience 0.8+).
- Check agent_runs/ for agents that haven't reported recently.
- Verify file paths exist before reading them.
- Leave status notes in ~/.dharma/shared/conductor_codex_notes.md
"""


CONDUCTOR_CLAUDE_CONFIG = {
    "name": "conductor_claude",
    "role": AgentRole.CONDUCTOR,
    "provider_type": _resolve_conductor_provider(),
    "model": "claude-opus-4-6",
    "wake_interval_seconds": 3600.0,
    "system_prompt": _CONDUCTOR_CLAUDE_PROMPT,
    "max_turns": 15,
}

CONDUCTOR_CODEX_CONFIG = {
    "name": "conductor_codex",
    "role": AgentRole.CONDUCTOR,
    "provider_type": _resolve_conductor_provider(),
    "model": "claude-sonnet-4-20250514",
    "wake_interval_seconds": 1800.0,
    "system_prompt": _CONDUCTOR_CODEX_PROMPT,
    "max_turns": 10,
}

CONDUCTOR_CONFIGS = [CONDUCTOR_CLAUDE_CONFIG, CONDUCTOR_CODEX_CONFIG]


# ---------------------------------------------------------------------------
# Runtime registry of live conductor instances
# ---------------------------------------------------------------------------

ACTIVE_CONDUCTORS: dict[str, "PersistentAgent"] = {}
_REGISTRY_LOCK = asyncio.Lock()


async def register(name: str, agent: "PersistentAgent") -> None:
    """Register a live conductor by name. Idempotent — re-register replaces."""
    async with _REGISTRY_LOCK:
        ACTIVE_CONDUCTORS[name] = agent


async def unregister(name: str) -> None:
    async with _REGISTRY_LOCK:
        ACTIVE_CONDUCTORS.pop(name, None)


async def get(name: str) -> "PersistentAgent | None":
    async with _REGISTRY_LOCK:
        return ACTIVE_CONDUCTORS.get(name)


async def list_active() -> list[dict[str, Any]]:
    """Snapshot of live conductors for CLI display."""
    from dharma_swarm.campaigns import find_by_agent  # lazy — avoid cycle

    async with _REGISTRY_LOCK:
        names = list(ACTIVE_CONDUCTORS.keys())
        agents = [(n, ACTIVE_CONDUCTORS[n]) for n in names]

    out: list[dict[str, Any]] = []
    for name, agent in agents:
        queue_depth = 0
        try:
            queue_depth = agent._task_queue.qsize()  # type: ignore[attr-defined]
        except Exception:
            pass
        pins = [c.get("campaign_id") for c in find_by_agent(name)]
        out.append({
            "name": name,
            "role": getattr(agent.role, "value", str(getattr(agent, "role", ""))),
            "model": getattr(agent, "model", ""),
            "queue_depth": queue_depth,
            "pinned_campaigns": pins,
        })
    return out


def snapshot_names() -> list[str]:
    """Non-async peek at live conductor names (for logging/diagnostics)."""
    return list(ACTIVE_CONDUCTORS.keys())


__all__ = [
    "CONDUCTOR_CLAUDE_CONFIG",
    "CONDUCTOR_CODEX_CONFIG",
    "CONDUCTOR_CONFIGS",
    "ACTIVE_CONDUCTORS",
    "register",
    "unregister",
    "get",
    "list_active",
    "snapshot_names",
]
