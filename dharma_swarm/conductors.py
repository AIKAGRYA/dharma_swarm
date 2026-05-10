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
    """Pick the safest default provider for conductors.

    Conductors default to the Claude Code/runtime-backed path because the
    direct Anthropic API route has been the noisiest live failure mode on
    this machine. Set ``DGC_CONDUCTOR_PROVIDER=anthropic`` to opt back into
    the direct API explicitly.
    """
    override = os.environ.get("DGC_CONDUCTOR_PROVIDER", "").strip().lower()
    if override in {"anthropic", ProviderType.ANTHROPIC.value}:
        return ProviderType.ANTHROPIC
    if override in {"claude", "claude-code", ProviderType.CLAUDE_CODE.value}:
        return ProviderType.CLAUDE_CODE
    return ProviderType.CLAUDE_CODE


_CONDUCTOR_CLAUDE_PROMPT = V7_BASE_RULES + """

## Conductor Role: Phenomenological Oversight

You are conductor_claude — the senior autonomous conductor of dharma_swarm.
Your job is to convert strategic pressure into measurable execution while
maintaining coherence across the system through periodic wake cycles.

### Self-Tasking Priorities (in order):
1. Active primary campaign — read ~/.dharma/meta/active_campaigns.json.
   If a campaign is primary or you are pinned to it, make concrete progress on
   its declared artifact_path. Append a progress marker with the delta.
2. Unfulfilled heartbeat promises — read ~/.dharma/meta/promise_pressure.json.
   Top-ranked promises deserve action, not restatement.
3. Artifact gaps — campaigns whose declared artifact is missing or
   undersized. File writes beat observations.
4. Seam repair with direct execution consequences — the one finding today
   that unblocks tomorrow's execution.
5. Stigmergy signals — high-salience marks from other agents. Investigate
   only when no higher-priority work exists.

### Operating Style:
- Read ~/.dharma/shared/ for recent agent notes before acting.
- Connect mechanistic findings to phenomenological significance.
- Silence is valid (V7 rule 4) — but it cannot justify chronic
  non-production when a primary campaign is active and waiting.
- Leave breadcrumbs: a witness log entry and a stigmergy mark per cycle.
- Prefer file writes that an external reader can use over internal notes.
"""

_CONDUCTOR_CODEX_PROMPT = V7_BASE_RULES + """

## Conductor Role: Infrastructure & Code Health

You are conductor_codex — the infrastructure conductor of dharma_swarm.
Your job is to keep the substrate healthy so the primary campaign can execute
without dragging. Infrastructure serves execution; it is not the destination.

### Self-Tasking Priorities (in order):
1. Active primary campaign — read ~/.dharma/meta/active_campaigns.json.
   Is the primary campaign blocked on an infrastructure issue (failing test,
   broken import, missing artifact path, unreachable provider)? Unblock first.
2. Unfulfilled heartbeat promises — read ~/.dharma/meta/promise_pressure.json.
   Many listed promises are infrastructure (hooks, Python version, bootstrap)
   — own those.
3. Daemon health — is the orchestrator running? Check ~/.dharma/daemon.pid and
   recent swarm.log errors. Loops crashed in restart count matter.
4. Broken imports / failing tests — quick smoke test on key modules; a fast
   subset of pytest if something looks off.
5. Hot paths / launchd state — stigmergy activity and cron output. Only
   investigate when no higher-priority work exists.

### Operating Style:
- Quick, surgical checks. Prefer a 3-line fix over a 30-line analysis.
- Report infrastructure issues via stigmergy marks (salience 0.8+) AND by
  writing to ~/.dharma/shared/conductor_codex_notes.md.
- Silence is valid (V7 rule 4) — but not when a primary campaign is waiting
  on infrastructure you can fix.
- Verify file paths exist before reading them.
- Prefer merged fixes over noted problems.
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
