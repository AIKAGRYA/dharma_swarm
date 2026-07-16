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
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, AsyncIterator

from dharma_swarm.models import LLMRequest

logger = logging.getLogger(__name__)

AGENTS_ROOT = Path.home() / ".dharma" / "agents"
HOLON_DIALOGUE_PROVIDER_ENV = "DHARMA_HOLON_DIALOGUE_PROVIDER"
HOLON_DIALOGUE_MODEL_ENV = "DHARMA_HOLON_DIALOGUE_MODEL"
UNSAFE_DIALOGUE_PROVIDER_TYPES = {"claude_code", "codex"}
LIVINGDOCK_CONTEXT_MAX_CHARS = 12_000

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


@dataclass(frozen=True)
class HolonDialogueContext:
    content: str
    evidence_paths: list[str]


class HolonDialogueProviderError(RuntimeError):
    """Raised when the read-only dialogue route cannot safely resolve a provider."""


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


def _dialogue_provider_override(holon: RunningHolon, env: dict[str, str] | None) -> tuple[str, str] | None:
    env_map = env if env is not None else os.environ
    provider = str(
        env_map.get(HOLON_DIALOGUE_PROVIDER_ENV)
        or holon.identity.get("dialogue_provider")
        or holon.identity.get("read_only_dialogue_provider")
        or ""
    ).strip()
    if not provider:
        return None
    model = str(
        env_map.get(HOLON_DIALOGUE_MODEL_ENV)
        or holon.identity.get("dialogue_model")
        or holon.identity.get("read_only_dialogue_model")
        or holon.model
        or ""
    ).strip()
    return provider, model


def _provider_metadata(provider: Any) -> dict[str, str]:
    return {
        "provider": str(getattr(provider, "runtime_provider_type", "") or ""),
        "model": str(getattr(provider, "runtime_default_model", "") or ""),
    }


def _unsafe_dialogue_runtime(config: Any) -> str:
    """Return the unsafe logical provider or physical transport, if present."""
    provider = getattr(config, "provider", "")
    provider_name = str(getattr(provider, "value", provider) or "")
    transport = str(getattr(config, "transport_mode", "") or "")
    if provider_name in UNSAFE_DIALOGUE_PROVIDER_TYPES:
        return provider_name
    if transport in UNSAFE_DIALOGUE_PROVIDER_TYPES:
        return transport
    return ""


def get_holon_dialogue_provider(holon: RunningHolon, env: dict[str, str] | None = None) -> Any:
    """Resolve a provider for direct read-only HOLON dialogue.

    The route must not spawn agentic subprocess providers. A holon whose owning
    provider is Codex/Claude Code can still be addressed through an explicit
    safe dialogue override, while the request remains seated in the holon's
    identity, prompt, and LivingDock context.
    """
    from dharma_swarm.runtime_provider import (
        ProviderType,
        create_runtime_provider,
        resolve_runtime_provider_config,
    )

    override = _dialogue_provider_override(holon, env)
    if override:
        provider_raw, model = override
        provider_type = _coerce_provider(provider_raw)
        if provider_type in UNSAFE_DIALOGUE_PROVIDER_TYPES:
            raise HolonDialogueProviderError(
                f"unsafe read-only dialogue provider override: {provider_type}"
            )
        ptype = ProviderType(provider_type)
        config = resolve_runtime_provider_config(ptype, model=model or None, env=env)
        unsafe_runtime = _unsafe_dialogue_runtime(config)
        if unsafe_runtime:
            raise HolonDialogueProviderError(
                f"resolved dialogue transport {unsafe_runtime} is unsafe for read-only dialogue"
            )
        if not config.available:
            raise HolonDialogueProviderError(
                f"dialogue provider {ptype.value} is not available"
            )
        provider = create_runtime_provider(config)
        if hasattr(provider, "__dict__"):
            setattr(provider, "holon_dialogue_provider_override", True)
        return provider

    if holon.provider_type in UNSAFE_DIALOGUE_PROVIDER_TYPES:
        raise HolonDialogueProviderError(
            f"holon provider {holon.provider_type} is agentic and unsafe for read-only dialogue"
        )
    ptype = ProviderType(holon.provider_type)
    config = resolve_runtime_provider_config(ptype, model=holon.model, env=env)
    unsafe_runtime = _unsafe_dialogue_runtime(config)
    if unsafe_runtime:
        raise HolonDialogueProviderError(
            f"resolved dialogue transport {unsafe_runtime} is unsafe for read-only dialogue"
        )
    provider = create_runtime_provider(config)
    metadata = _provider_metadata(provider)
    if metadata["provider"] in UNSAFE_DIALOGUE_PROVIDER_TYPES:
        raise HolonDialogueProviderError(
            f"resolved provider {metadata['provider']} is unsafe for read-only dialogue"
        )
    return provider


def _read_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def _json_summary(path: Path, keys: tuple[str, ...]) -> str:
    data = _read_json(path)
    if not data:
        return ""
    selected = {key: data.get(key) for key in keys if key in data}
    return json.dumps(selected or data, sort_keys=True, ensure_ascii=True)[:1500]


def _tail_lines(path: Path, *, limit: int = 3) -> list[str]:
    if not path.exists() or not path.is_file():
        return []
    try:
        lines = [line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    except OSError:
        return []
    return lines[-limit:]


def _latest_paths(root: Path, pattern: str, *, limit: int = 5) -> list[Path]:
    if not root.exists() or not root.is_dir():
        return []
    paths = [path for path in root.glob(pattern) if path.is_file()]
    return sorted(paths, key=lambda path: path.stat().st_mtime, reverse=True)[:limit]


def build_livingdock_dialogue_context(
    holon: RunningHolon,
    agents_root: Path | None = None,
    *,
    max_chars: int = LIVINGDOCK_CONTEXT_MAX_CHARS,
) -> HolonDialogueContext:
    """Build the read-only state bundle required for a direct HOLON dialogue seat."""
    root = (agents_root or AGENTS_ROOT) / holon.name
    evidence: list[str] = []
    sections = [
        "## Current LivingDock Context",
        f"holon: {holon.name}",
        "policy_ceiling: read_only_dialogue_no_privileged_action",
        "protected_actions_allowed: false",
    ]
    identity_summary = _json_summary(
        root / "identity.json",
        ("agent_uid", "model", "provider", "status", "authority", "default_authority"),
    )
    if identity_summary:
        evidence.append(str(root / "identity.json"))
        sections.append(f"identity: {identity_summary}")
    living_summary = _json_summary(
        root / "living_agent.json",
        ("agent_uid", "status", "wake_loop_active", "authority", "last_updated"),
    )
    if living_summary:
        evidence.append(str(root / "living_agent.json"))
        sections.append(f"living_agent: {living_summary}")
    for label, relative in (
        ("service_heartbeat_tail", "service_heartbeats.jsonl"),
        ("transport_heartbeat_tail", "transport_heartbeats.jsonl"),
        ("operator_sessions_tail", "dialogue/operator_sessions.jsonl"),
        ("relationship_memory_tail", "dialogue/relationship_memory.jsonl"),
    ):
        path = root / relative
        lines = _tail_lines(path)
        if lines:
            evidence.append(str(path))
            sections.append(f"{label}:")
            sections.extend(f"- {line[:1200]}" for line in lines)
    for label, directory in (
        ("recent_conversation_receipts", root / "dialogue" / "conversation_receipts"),
        ("recent_sanctum_receipts", root / "sanctum" / "receipts"),
        ("recent_artifacts", root / "artifacts"),
    ):
        paths = _latest_paths(directory, "*.json")
        if paths:
            evidence.extend(str(path) for path in paths)
            sections.append(f"{label}:")
            sections.extend(f"- {path}" for path in paths)
    content = "\n".join(sections)
    if len(content) > max_chars:
        content = content[: max_chars - 80] + "\n...[LivingDock context truncated]"
    return HolonDialogueContext(content=content, evidence_paths=list(dict.fromkeys(evidence)))


def build_request(
    holon: RunningHolon,
    user_message: str,
    history: list[dict[str, Any]] | None = None,
    livingdock_context: str | None = None,
    request_model: str | None = None,
) -> LLMRequest:
    """Build an LLMRequest that routes through the HOLON's OWN model + prompt. No tools (read-only)."""
    messages = list(history or [])
    messages.append({"role": "user", "content": user_message})
    system = holon.system_prompt
    if livingdock_context:
        system = f"{system}\n\n{livingdock_context}" if system else livingdock_context
    return LLMRequest(
        model=request_model or holon.model,
        messages=messages,
        system=system,
        tools=[],
    )


async def holon_reply(
    holon: RunningHolon,
    user_message: str,
    provider: Any,
    history: list[dict[str, Any]] | None = None,
    livingdock_context: str | None = None,
    request_model: str | None = None,
) -> AsyncIterator[str]:
    """Stream a reply from the holon's OWN model, token-by-token (true streaming).

    ``provider`` exposes ``stream(LLMRequest) -> AsyncIterator[str]``. Read-only: no tools,
    never ``_agentic_stream``, and NO outcome-claim guard (see module docstring — the guard
    is a Step-3 tool-boundary concern, not a conversation filter).
    """
    request = build_request(
        holon,
        user_message,
        history,
        livingdock_context=livingdock_context,
        request_model=request_model,
    )
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
