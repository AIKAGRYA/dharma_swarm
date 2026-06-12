"""Read-only sovereign holon bridge — load a registered agent and talk to it AS ITSELF.

v1 is READ-ONLY: no tool calls, no governance enforcement (that is Step 3). It loads the
agent's OWN model + system prompt from the canonical agent home and streams replies from
*that* model, token-by-token.

Canonical agent home: ``~/.dharma/agents/`` (operator-decided 2026-06-09 — see
``docs/sovereign_holons/AGENT_HOME_RECONCILIATION.md``). NOT ``ginko/agents``.

Deliberately does NOT import ``living_agent_kernel`` (the governance organ, Step 3 only)
and never calls ``_agentic_stream`` — the read-only talk path is independent of both.

NOTE on the anti-narration guard (``guard_outcome_claim``): it is a Step-3 *tool-boundary*
utility, NOT applied to the read-only talk path. A read-only surface has no tools, so it
cannot falsely claim work — applying the guard here would refuse normal conversation
("I've created a mental model…") and force non-streaming. See ``holon_reply``.
"""
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, AsyncIterator

from dharma_swarm.models import LLMRequest

logger = logging.getLogger(__name__)

AGENTS_ROOT = Path.home() / ".dharma" / "agents"

# Provider string -> canonical ProviderType *value* (lowercase, matching the enum). Per
# MODEL_KEY_ROUTING "THE ONE WAY", Anthropic/Claude routes to the Max plan (claude_code).
# ``anthropic_max`` is NOT a ProviderType value, so it must be coerced + validated.
_PROVIDER_COERCE = {
    "anthropic_max": "claude_code",
    "claude_code": "claude_code",
    "anthropic": "anthropic",
}

# Step-3 anti-narration guard (NOT used on the read-only path). Outcome words that, when an
# acting agent emits them without a verifier_artifact, indicate an unbacked work-claim.
_OUTCOME_RE = re.compile(
    r"\b(done|updated|committed|passed|created|fixed|deployed|merged|shipped)\b",
    re.IGNORECASE,
)


@dataclass
class RunningHolon:
    """A registered agent loaded as *itself* — its own model, prompt, and identity.

    ``provider_type`` is a canonical ProviderType *value* (lowercase), safe to pass to
    ``ProviderType(holon.provider_type)``.
    """

    name: str
    model: str
    system_prompt: str
    provider_type: str
    identity: dict[str, Any] = field(default_factory=dict)


def _coerce_provider(raw: str | None) -> str:
    """Map an identity 'provider' string to a valid ProviderType value (lowercase).

    ``anthropic_max`` -> ``claude_code`` (Max plan). The result is validated against the
    real ProviderType enum; anything invalid falls back to ``claude_code`` with a warning,
    so ``ProviderType(holon.provider_type)`` downstream never raises.
    """
    lowered = (raw or "claude_code").lower()
    candidate = _PROVIDER_COERCE.get(lowered, lowered)
    try:
        from dharma_swarm.runtime_provider import ProviderType

        ProviderType(candidate)  # validates membership
    except Exception:
        logger.warning(
            "[holon] provider %r -> %r is not a valid ProviderType; defaulting to claude_code",
            raw,
            candidate,
        )
        candidate = "claude_code"
    return candidate


_AGENT_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_\-.]{0,63}$")


def load_holon(name: str, agents_root: Path | None = None) -> RunningHolon:
    """Load a registered agent from ``~/.dharma/agents/<name>/`` as a RunningHolon.

    ``system_prompt`` is the agent's own ``prompt_variants/active.txt`` (byte-for-byte,
    BOM-stripped), falling back to ``identity['system_prompt']`` (logged) when absent.
    ``name`` must be a registry directory slug — anything else is rejected before any
    path is built (path-traversal + log-injection defense at the record→runtime door).
    """
    if not _AGENT_NAME_RE.fullmatch(name or ""):
        raise FileNotFoundError("no registered agent (invalid name)")
    name = name.replace("\r", "").replace("\n", "")
    root = agents_root or AGENTS_ROOT
    agent_dir = root / name
    identity_path = agent_dir / "identity.json"
    if not identity_path.exists():
        raise FileNotFoundError(f"no registered agent at {identity_path}")
    try:
        identity = json.loads(identity_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"agent {name}: malformed identity.json ({exc})") from exc

    active = agent_dir / "prompt_variants" / "active.txt"
    if active.exists():
        # utf-8-sig strips a leading BOM if present (otherwise U+FEFF pollutes the prompt).
        system_prompt = active.read_text(encoding="utf-8-sig")
    else:
        system_prompt = identity.get("system_prompt", "")
        logger.info(
            "[holon] %s: no active.txt, using identity system_prompt (%d chars)",
            name,
            len(system_prompt),
        )

    model = identity.get("model")
    if not model:
        raise ValueError(f"agent {name} identity.json has no 'model'")

    return RunningHolon(
        name=name,
        model=model,
        system_prompt=system_prompt,
        provider_type=_coerce_provider(identity.get("provider")),
        identity=identity,
    )


def get_holon_provider(holon: RunningHolon, env: dict[str, str] | None = None) -> Any:
    """Turn a RunningHolon into a LIVE provider (name → running provider).

    Composes the canonical model door: ``ProviderType(holon.provider_type)`` →
    ``resolve_runtime_provider_config`` → ``create_runtime_provider``. provider_type is
    already a valid lowercase ProviderType value (see ``_coerce_provider``), so this never
    raises on the enum. Anthropic auto-routes to the Max plan inside resolve().
    """
    from dharma_swarm.runtime_provider import (
        ProviderType,
        create_runtime_provider,
        resolve_runtime_provider_config,
    )

    ptype = ProviderType(holon.provider_type)
    config = resolve_runtime_provider_config(ptype, model=holon.model, env=env)
    return create_runtime_provider(config)


def build_request(
    holon: RunningHolon,
    user_message: str,
    history: list[dict[str, Any]] | None = None,
) -> LLMRequest:
    """Build an LLMRequest that routes through the HOLON's OWN model + prompt. No tools (read-only)."""
    messages = list(history or [])
    messages.append({"role": "user", "content": user_message})
    return LLMRequest(
        model=holon.model,
        messages=messages,
        system=holon.system_prompt,
        tools=[],
    )


async def holon_reply(
    holon: RunningHolon,
    user_message: str,
    provider: Any,
    history: list[dict[str, Any]] | None = None,
) -> AsyncIterator[str]:
    """Stream a reply from the holon's OWN model, token-by-token (true streaming).

    ``provider`` exposes ``stream(LLMRequest) -> AsyncIterator[str]``. Read-only: no tools,
    never ``_agentic_stream``, and NO outcome-claim guard (see module docstring — the guard
    is a Step-3 tool-boundary concern, not a conversation filter).
    """
    request = build_request(holon, user_message, history)
    async for chunk in provider.stream(request):
        yield chunk


def guard_outcome_claim(text: str, has_artifact: bool) -> str:
    """STEP-3 tool-boundary utility (NOT used on the read-only talk path).

    When an *acting* agent emits an outcome claim (done/updated/...) without a
    ``verifier_artifact``, replace it with a logged refusal. Belongs at the tool-execution
    boundary where the agent can actually produce (or falsely claim) an outcome.
    """
    if has_artifact:
        return text
    if _OUTCOME_RE.search(text):
        logger.warning("[holon] outcome-claim without verifier_artifact refused")
        return (
            "[refused: this reply claimed an outcome (done/updated/...) without a "
            "verifier_artifact.]"
        )
    return text
