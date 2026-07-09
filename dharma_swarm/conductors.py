"""Conductor agent definitions.

Two conductors that run autonomous wake loops:
- conductor_claude: Opus-class, phenomenological + oversight focus
- conductor_codex: Claude Code canonical default, infrastructure + code health focus

Both compose PersistentAgent which composes AutonomousAgent.
"""

from __future__ import annotations

from copy import deepcopy

from dharma_swarm.api_keys import ANTHROPIC_API_KEY_ENV, env_has_value
from dharma_swarm.daemon_config import V7_BASE_RULES
from dharma_swarm.model_hierarchy import default_model as canonical_default_model
from dharma_swarm.models import AgentRole, ProviderType


def _resolve_conductor_provider() -> ProviderType:
    """Pick the best available provider for conductors (Anthropic > Claude Code)."""
    if env_has_value(ANTHROPIC_API_KEY_ENV):
        return ProviderType.ANTHROPIC
    return ProviderType.CLAUDE_CODE


def materialize_conductor_config(template: dict[str, object]) -> dict[str, object]:
    """Resolve provider/model at instantiation time after runtime env bootstrap."""
    cfg = deepcopy(template)
    provider = _resolve_conductor_provider()
    cfg["provider_type"] = provider
    cfg["provider_fallbacks"] = [ProviderType.CLAUDE_CODE]
    if cfg["name"] == "conductor_codex":
        cfg["model"] = canonical_default_model(ProviderType.CLAUDE_CODE)
    elif provider == ProviderType.ANTHROPIC:
        cfg["model"] = canonical_default_model(ProviderType.ANTHROPIC)
    else:
        cfg["model"] = canonical_default_model(ProviderType.CLAUDE_CODE)
    return cfg


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
    "provider_type": ProviderType.CLAUDE_CODE,
    "model": canonical_default_model(ProviderType.ANTHROPIC),
    "wake_interval_seconds": 3600.0,
    "system_prompt": _CONDUCTOR_CLAUDE_PROMPT,
    "max_turns": 15,
}

CONDUCTOR_CODEX_CONFIG = {
    "name": "conductor_codex",
    "role": AgentRole.CONDUCTOR,
    "provider_type": ProviderType.CLAUDE_CODE,
    "model": canonical_default_model(ProviderType.CLAUDE_CODE),
    "wake_interval_seconds": 1800.0,
    "system_prompt": _CONDUCTOR_CODEX_PROMPT,
    "max_turns": 10,
}

CONDUCTOR_CONFIGS = [CONDUCTOR_CLAUDE_CONFIG, CONDUCTOR_CODEX_CONFIG]
