#!/usr/bin/env python3
"""`talk <agent>` — the sovereign-holon talk surface (organ 7).

Loads a registered agent's OWN soul (identity + active.txt), routes either through the
identity-declared model first or through the explicit free-first live model chain, streams
the reply, and writes an inspectable receipt. Runs live in-session because free models are
HTTP APIs, not the nesting-blocked claude CLI.

    python3 scripts/holon_talk.py opus_composer "who are you and what is your telos?"
    python3 scripts/holon_talk.py opus_composer --mode declared-first "who are you?"
"""
import argparse
import asyncio
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from dharma_swarm.holon_bridge import get_holon_provider, load_holon
from dharma_swarm.models import LLMRequest
from dharma_swarm.runtime_provider import (
    ProviderType,
    create_runtime_provider,
    preferred_runtime_provider_configs,
)

# Free-first mode deliberately excludes the Claude/Max door: the declared-first mode
# owns that route, and a local sovereign agent's cheap mode must never silently route
# to claude_code (05_RECONCILED_PLAN non-negotiables).
_FREE_CHAIN_EXCLUDES = frozenset({ProviderType.CLAUDE_CODE})
ROUTING_MODE_CHOICES = ("free-first", "declared-first")
_PROVIDER_FAILURE_MARKERS = (
    "credit balance is too low",
    "hit your session limit",
    "session limit",
    "insufficient_quota",
    "insufficient credits",
    "billing",
)


def _normalize_routing_mode(routing_mode: str) -> str:
    """Normalize user-facing routing aliases into the explicit supported modes."""
    aliases = {
        "free": "free-first",
        "local-free": "free-first",
        "declared": "declared-first",
        "identity": "declared-first",
        "identity-first": "declared-first",
    }
    raw = (routing_mode or "").strip().lower()
    mode = aliases.get(raw, raw)
    if mode not in ROUTING_MODE_CHOICES:
        raise ValueError(f"routing mode must be one of: {', '.join(ROUTING_MODE_CHOICES)}")
    return mode


def _looks_like_provider_failure(reply: str) -> bool:
    lowered = (reply or "").lower()
    return any(marker in lowered for marker in _PROVIDER_FAILURE_MARKERS)


def _resolve_free_provider():
    """Free-first provider resolution via the canonical low-cost chain.

    Walks ``preferred_runtime_provider_configs()`` — the single source of provider
    ordering (Ollama and NVIDIA NIM before any OpenRouter lane) — instead of a
    hand-rolled list, skipping the claude_code fallback door. Returns
    ``(provider, ptype_value, model)``.
    """
    last_err = "no providers available"
    for cfg in preferred_runtime_provider_configs():
        if cfg.provider in _FREE_CHAIN_EXCLUDES:
            continue
        try:
            return create_runtime_provider(cfg), cfg.provider.value, cfg.default_model
        except Exception as exc:  # noqa: BLE001
            last_err = f"{cfg.provider.value}: {type(exc).__name__}: {exc}"
            continue
    raise RuntimeError(f"no free provider available (last: {last_err})")


def _resolve_declared_provider(holon):
    """Identity-declared provider resolution. Returns (provider, ptype, model)."""
    return get_holon_provider(holon), holon.provider_type, holon.model


def _resolve_provider(holon, routing_mode: str):
    """Resolve the requested explicit routing mode. Returns (provider, ptype, model, mode)."""
    mode = _normalize_routing_mode(routing_mode)
    if mode == "declared-first":
        provider, pname, model = _resolve_declared_provider(holon)
    else:
        provider, pname, model = _resolve_free_provider()
    return provider, pname, model, mode


async def _stream_request(provider, request: LLMRequest) -> str:
    chunks: list[str] = []
    async for chunk in provider.stream(request):
        chunks.append(chunk)
        sys.stdout.write(chunk)
        sys.stdout.flush()
    return "".join(chunks).strip()


async def talk(
    name: str,
    message: str,
    *,
    routing_mode: str = "free-first",
    max_tokens: int = 400,
) -> int:
    holon = load_holon(name)  # the agent's OWN soul + identity
    provider, pname, model, mode = _resolve_provider(holon, routing_mode)
    route_label = f"{pname}/{model}"
    print(f"[holon] {name} · soul={len(holon.system_prompt)} chars · mode={mode} · model: {route_label}\n")
    print(f"you> {message}\n{name}> ", end="", flush=True)

    def _request(active_model: str) -> LLMRequest:
        return LLMRequest(
            model=active_model,
            messages=[{"role": "user", "content": message}],
            system=holon.system_prompt,
            max_tokens=max_tokens,
        )

    fallback_from: str | None = None
    try:
        reply = await _stream_request(provider, _request(model))
    except Exception as exc:  # noqa: BLE001
        if mode != "declared-first":
            raise
        print(f"\n[warn] declared route failed ({type(exc).__name__}: {exc}); falling back to free-first")
        fallback_from = route_label
        provider, pname, model = _resolve_free_provider()
        route_label = f"{pname}/{model}"
        print(f"{name} [fallback {route_label}]> ", end="", flush=True)
        reply = await _stream_request(provider, _request(model))
    if mode == "declared-first" and fallback_from is None and _looks_like_provider_failure(reply):
        print("\n[warn] declared route returned provider/account failure; falling back to free-first")
        fallback_from = route_label
        provider, pname, model = _resolve_free_provider()
        route_label = f"{pname}/{model}"
        print(f"{name} [fallback {route_label}]> ", end="", flush=True)
        reply = await _stream_request(provider, _request(model))
    print()

    # inspectable receipt (organ: witness/receipt) — reuse the canonical agent home
    receipt = {
        "holon": name,
        "routing_mode": mode,
        "model": route_label,
        "fallback_from": fallback_from,
        "at": datetime.now(timezone.utc).isoformat(),
        "you": message,
        "reply": reply,
        "reply_chars": len(reply),
    }
    rpath = Path.home() / ".dharma" / "agents" / name / "talk_receipts.jsonl"
    rpath.parent.mkdir(parents=True, exist_ok=True)
    with rpath.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(receipt, ensure_ascii=False) + "\n")
    ok = bool(reply) and not _looks_like_provider_failure(reply)
    print(f"\n[receipt] {'LIVE — the holon spoke as itself' if ok else 'EMPTY/provider-failure reply'} · {rpath}")
    return 0 if ok else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Talk to a registered sovereign holon.")
    parser.add_argument("agent", nargs="?", default="opus_composer")
    parser.add_argument("message", nargs="*")
    parser.add_argument("--mode", choices=ROUTING_MODE_CHOICES, default="free-first")
    parser.add_argument("--max-tokens", type=int, default=400)
    args = parser.parse_args()
    msg = " ".join(args.message) or "In two sentences, who are you and what is your telos?"
    raise SystemExit(asyncio.run(talk(args.agent, msg, routing_mode=args.mode, max_tokens=args.max_tokens)))
