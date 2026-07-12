"""Internal package-owned runtime for sovereign-holon talk and run commands."""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from dharma_swarm import holon_persistence, holon_runtime
from dharma_swarm.holon_bridge import get_holon_provider, load_holon
from dharma_swarm.models import LLMRequest
from dharma_swarm.runtime_provider import (
    ProviderType,
    create_runtime_provider,
    preferred_runtime_provider_configs,
)

# Free-first mode deliberately excludes the Claude/Max door: declared-first owns
# that route, and a sovereign agent's cheap mode must not silently use it.
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

SELF_TASK = (
    "You are awake for one autonomous work cycle. In ONE sentence: name the single most "
    "important next action toward your telos right now, and why."
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
        choices = ", ".join(ROUTING_MODE_CHOICES)
        raise ValueError(f"routing mode must be one of: {choices}")
    return mode


def _looks_like_provider_failure(reply: str) -> bool:
    lowered = (reply or "").lower()
    return any(marker in lowered for marker in _PROVIDER_FAILURE_MARKERS)


def _resolve_free_provider():
    """Resolve the first available provider in the canonical free chain."""
    last_err = "no providers available"
    for cfg in preferred_runtime_provider_configs():
        if cfg.provider in _FREE_CHAIN_EXCLUDES:
            continue
        try:
            provider = create_runtime_provider(cfg)
            return provider, cfg.provider.value, cfg.default_model
        except Exception as exc:  # noqa: BLE001
            last_err = f"{cfg.provider.value}: {type(exc).__name__}: {exc}"
    raise RuntimeError(f"no free provider available (last: {last_err})")


def _resolve_declared_provider(holon):
    """Resolve the provider and model declared by a holon's identity."""
    return get_holon_provider(holon), holon.provider_type, holon.model


def _resolve_provider(holon, routing_mode: str):
    """Resolve a route as ``(provider, provider_name, model, mode)``."""
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
    """Talk to a registered holon and persist an inspectable receipt."""
    holon = load_holon(name)
    provider, pname, model, mode = _resolve_provider(holon, routing_mode)
    route_label = f"{pname}/{model}"
    print(
        f"[holon] {name} · soul={len(holon.system_prompt)} chars · "
        f"mode={mode} · model: {route_label}\n"
    )
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
        print(
            f"\n[warn] declared route failed ({type(exc).__name__}: {exc}); "
            "falling back to free-first"
        )
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
    status = "LIVE — the holon spoke as itself" if ok else "EMPTY/provider-failure reply"
    print(f"\n[receipt] {status} · {rpath}")
    return 0 if ok else 1


def _make_free_runner(holon, provider, model, routing_mode: str):
    async def runner(name: str):
        async def _reply(active_provider, active_model: str) -> str:
            req = LLMRequest(
                model=active_model,
                messages=[{"role": "user", "content": SELF_TASK}],
                system=holon.system_prompt,
                max_tokens=600,
            )
            chunks = []
            async for chunk in active_provider.stream(req):
                chunks.append(chunk)
            return "".join(chunks).strip()

        try:
            reply = await _reply(provider, model)
        except Exception:
            if routing_mode != "declared-first":
                raise
            fallback_provider, _, fallback_model = _resolve_free_provider()
            reply = await _reply(fallback_provider, fallback_model)
        if routing_mode == "declared-first" and _looks_like_provider_failure(reply):
            fallback_provider, _, fallback_model = _resolve_free_provider()
            reply = await _reply(fallback_provider, fallback_model)
        return SELF_TASK, reply

    return runner


async def run(name: str, cycles: int, *, routing_mode: str = "free-first") -> int:
    """Run governed wake cycles for a registered holon."""
    holon = load_holon(name)
    provider, pname, model, mode = _resolve_provider(holon, routing_mode)
    print(
        f"[holon] {name} waking · soul={len(holon.system_prompt)} chars · "
        f"mode={mode} · {pname}/{model} · {cycles} cycles\n"
    )
    runner = _make_free_runner(holon, provider, model, mode)

    results = await holon_runtime.run_holon_loop(
        name,
        runner,
        max_cycles=cycles,
        cap_usd=0.0,
    )
    for i, result in enumerate(results):
        print(f"--- cycle {i}: {result['status']} ---")
        if result["status"] == "ran":
            print(f"  {name}> {result['reply'][:240]}")
            if "signal" in result:
                print(f"  [compass] telos_alignment={result['signal'].get('telos_alignment')}")
        else:
            print(f"  {result}")

    events = holon_persistence.load_session(name)
    ran = sum(1 for result in results if result["status"] == "ran")
    print(
        f"\n[result] {ran}/{cycles} cycles ran LIVE & governed · "
        f"{len(events)} persisted events (survives restart)"
    )
    return 0 if ran else 1


__all__ = ["ROUTING_MODE_CHOICES", "SELF_TASK", "run", "talk"]
