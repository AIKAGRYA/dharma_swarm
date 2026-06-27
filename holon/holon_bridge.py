"""Standalone Holon identity loading and dialogue bridge."""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, AsyncIterator

from holon.contracts import LLMRequest
from holon.providers import Provider, ProviderRouter, build_provider_router

logger = logging.getLogger(__name__)

AGENTS_ROOT = Path.home() / ".dharma" / "agents"
_AGENT_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,95}$")
_OUTCOME_RE = re.compile(
    r"\b(done|updated|committed|passed|created|fixed|deployed|merged|shipped)\b",
    re.IGNORECASE,
)


@dataclass
class RunningHolon:
    name: str
    model: str
    system_prompt: str
    provider_type: str
    identity: dict[str, Any] = field(default_factory=dict)


def _coerce_provider(raw: str | None) -> str:
    value = str(raw or "echo").strip().lower()
    aliases = {"anthropic_max": "claude_code", "open_router": "openrouter"}
    return aliases.get(value, value or "echo")


def load_holon(name: str, agents_root: Path | None = None) -> RunningHolon:
    if not _AGENT_NAME_RE.fullmatch(name or ""):
        raise FileNotFoundError("no registered agent (invalid name)")
    root = agents_root or AGENTS_ROOT
    agent_dir = root / name
    identity_path = agent_dir / "identity.json"
    if not identity_path.exists():
        raise FileNotFoundError(f"no registered agent at {identity_path}")
    try:
        identity = json.loads(identity_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"agent {name}: malformed identity.json ({exc})") from exc
    if not isinstance(identity, dict):
        raise ValueError(f"agent {name}: identity.json must contain an object")
    active = agent_dir / "prompt_variants" / "active.txt"
    if active.exists():
        system_prompt = active.read_text(encoding="utf-8-sig")
    else:
        system_prompt = str(identity.get("system_prompt", ""))
        logger.info("[holon] %s: no active.txt, using identity system_prompt", name)
    model = str(identity.get("model") or "holon-echo-v1")
    return RunningHolon(
        name=name,
        model=model,
        system_prompt=system_prompt,
        provider_type=_coerce_provider(identity.get("provider")),
        identity=identity,
    )


def get_holon_provider(holon: RunningHolon, env: dict[str, str] | None = None) -> ProviderRouter:
    return build_provider_router(env=env, preferred_provider=holon.provider_type, model=holon.model)


def build_request(
    holon: RunningHolon,
    user_message: str,
    history: list[dict[str, Any]] | None = None,
    livingdock_context: str | None = None,
    request_model: str | None = None,
    tools: list[dict[str, Any]] | None = None,
) -> LLMRequest:
    messages = list(history or [])
    messages.append({"role": "user", "content": user_message})
    system = holon.system_prompt
    if livingdock_context:
        system = f"{system}\n\n{livingdock_context}" if system else livingdock_context
    return LLMRequest(model=request_model or holon.model, messages=messages, system=system, tools=list(tools or []))


async def holon_reply(
    holon: RunningHolon,
    user_message: str,
    provider: Provider,
    history: list[dict[str, Any]] | None = None,
    livingdock_context: str | None = None,
    request_model: str | None = None,
) -> AsyncIterator[str]:
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
    if has_artifact:
        return text
    if _OUTCOME_RE.search(text):
        logger.warning("[holon] outcome claim without verifier artifact refused")
        return "[refused: outcome claim without verifier_artifact]"
    return text


__all__ = [
    "AGENTS_ROOT",
    "RunningHolon",
    "_OUTCOME_RE",
    "build_request",
    "get_holon_provider",
    "guard_outcome_claim",
    "holon_reply",
    "load_holon",
]
