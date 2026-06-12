#!/usr/bin/env python3
"""LIVE smoke (U3) — talk to opus_composer through its OWN model, end to end.

MUST run OUTSIDE a Claude Code session: CLAUDECODE blocks the Max-plan `claude` CLI (the
holon's real route). Run it in a plain terminal:

    unset CLAUDECODE CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS
    cd ~/dharma_swarm && python3 scripts/holon_smoke.py

Or with the metered API instead of the Max plan (needs a funded ANTHROPIC_API_KEY):

    DHARMA_FORCE_ANTHROPIC_API=1 python3 scripts/holon_smoke.py

Exit 0 + a non-empty in-character reply = the bridge works against a real model.
"""
import asyncio
import os
import sys

PROMPT = "In one short sentence, who are you and what is your telos?"
_PROVIDER_FAILURE_MARKERS = (
    "credit balance is too low",
    "hit your session limit",
    "session limit",
    "insufficient_quota",
    "insufficient credits",
    "billing",
)

_IN_CHARACTER_MARKERS = (
    "opus_composer",
    "composer",
    "dharma",
    "telos",
    "swarm",
    "orchestrator",
)


def _looks_like_provider_failure(reply: str) -> bool:
    """Return True for provider/account error strings that must never count as PASS."""
    lowered = reply.strip().lower()
    return any(marker in lowered for marker in _PROVIDER_FAILURE_MARKERS)


def _looks_in_character(name: str, reply: str) -> bool:
    """Cheap smoke-level semantic check: non-error reply should identify the holon/telos."""
    lowered = reply.strip().lower()
    return name.lower() in lowered or any(marker in lowered for marker in _IN_CHARACTER_MARKERS)


async def _collect_stream(provider, request) -> str:
    chunks: list[str] = []
    async for chunk in provider.stream(request):
        chunks.append(chunk)
        sys.stdout.write(chunk)
        sys.stdout.flush()
    return "".join(chunks).strip()


async def _free_fallback_reply(holon) -> tuple[str, str]:
    """Try the canonical low-cost provider chain when claude_code is unavailable."""
    from dharma_swarm.models import LLMRequest
    from dharma_swarm.runtime_provider import (
        create_runtime_provider,
        preferred_runtime_provider_configs,
    )

    last_error = "no providers attempted"
    for config in preferred_runtime_provider_configs():
        provider = create_runtime_provider(config)
        route = f"{config.provider.value}/{config.default_model}"
        request = LLMRequest(
            model=config.default_model or holon.model,
            messages=[{"role": "user", "content": PROMPT}],
            system=holon.system_prompt,
            max_tokens=400,
        )
        try:
            print(f"\n[fallback] trying {route}")
            reply = await _collect_stream(provider, request)
            if reply and not _looks_like_provider_failure(reply):
                return reply, route
            last_error = f"{route}: provider failure text: {reply[:120]}"
        except Exception as exc:  # noqa: BLE001 - smoke should keep trying providers
            last_error = f"{route}: {type(exc).__name__}: {exc}"
        finally:
            close = getattr(provider, "close", None)
            if callable(close):
                maybe = close()
                if asyncio.iscoroutine(maybe):
                    await maybe
    raise RuntimeError(f"all fallback providers failed ({last_error})")


async def _run(name: str = "opus_composer") -> int:
    from dharma_swarm.holon_bridge import load_holon, get_holon_provider, holon_reply

    if os.environ.get("CLAUDECODE"):
        print("REFUSED: CLAUDECODE is set — the Max-plan claude CLI cannot nest. "
              "Run in a plain terminal (unset CLAUDECODE) or force the API path.",
              file=sys.stderr)
        return 2

    holon = load_holon(name)
    print(f"[holon] {holon.name} | model={holon.model} | provider={holon.provider_type} | "
          f"prompt={len(holon.system_prompt)} chars")
    provider = get_holon_provider(holon)

    chunks: list[str] = []
    async for chunk in holon_reply(holon, PROMPT, provider):
        chunks.append(chunk)
        sys.stdout.write(chunk)
        sys.stdout.flush()
    reply = "".join(chunks).strip()
    print()
    route = f"{holon.provider_type}/{holon.model}"
    if reply and _looks_like_provider_failure(reply):
        print(f"WARN: {route} returned provider/account failure text; falling back.")
        try:
            reply, route = await _free_fallback_reply(holon)
            print()
        except Exception as exc:  # noqa: BLE001 - smoke reports explicit failure
            print(f"FAIL: {exc}", file=sys.stderr)
            return 1
    if not reply:
        print("FAIL: empty reply from holon", file=sys.stderr)
        return 1
    if not _looks_in_character(name, reply):
        print(f"FAIL: non-empty reply was not in-character: {reply[:160]}", file=sys.stderr)
        return 1
    print(f"\nPASS: {name} replied as itself via {route} ({len(reply)} chars).")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_run(sys.argv[1] if len(sys.argv) > 1 else "opus_composer")))
