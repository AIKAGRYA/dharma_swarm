#!/usr/bin/env python3
"""`run <agent>` — the holon RUNS ITSELF: the governed wake loop wired to an explicit route.

This is the proof that the holon doesn't just talk but *runs autonomously, live*: it plugs a
real runner into ``holon_runtime.run_holon_loop`` so each cycle is kill-checked,
budget-checked, does one unit of self-work, compass-scored, and persisted.

    python3 scripts/holon_run.py opus_composer 2     # 2 governed live cycles
    python3 scripts/holon_run.py opus_composer 2 --mode declared-first
"""
import argparse
import asyncio

from dharma_swarm import holon_persistence, holon_runtime
from dharma_swarm.holon_bridge import load_holon
from dharma_swarm.models import LLMRequest
try:
    from scripts.holon_talk import (
        ROUTING_MODE_CHOICES,
        _looks_like_provider_failure,
        _resolve_free_provider,
        _resolve_provider,
    )
except ModuleNotFoundError:  # direct `python3 scripts/holon_run.py`
    from holon_talk import (  # type: ignore[no-redef]
        ROUTING_MODE_CHOICES,
        _looks_like_provider_failure,
        _resolve_free_provider,
        _resolve_provider,
    )

SELF_TASK = (
    "You are awake for one autonomous work cycle. In ONE sentence: name the single most "
    "important next action toward your telos right now, and why."
)


def _make_free_runner(holon, provider, model, routing_mode: str):
    async def runner(name: str):
        async def _reply(active_provider, active_model: str) -> str:
            req = LLMRequest(
                model=active_model,
                messages=[{"role": "user", "content": SELF_TASK}],
                system=holon.system_prompt,
                max_tokens=600,  # reasoning models (glm-5) need headroom past internal thinking, else empty
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
    holon = load_holon(name)
    provider, pname, model, mode = _resolve_provider(holon, routing_mode)
    print(f"[holon] {name} waking · soul={len(holon.system_prompt)} chars · mode={mode} · {pname}/{model} · {cycles} cycles\n")
    runner = _make_free_runner(holon, provider, model, mode)

    # governed loop: kill -> budget -> work(live model) -> compass -> persist, each cycle.
    results = await holon_runtime.run_holon_loop(
        name, runner, max_cycles=cycles, cap_usd=0.0,  # free/fallback path is expected low-cost
    )
    for i, r in enumerate(results):
        print(f"--- cycle {i}: {r['status']} ---")
        if r["status"] == "ran":
            print(f"  {name}> {r['reply'][:240]}")
            if "signal" in r:
                print(f"  [compass] telos_alignment={r['signal'].get('telos_alignment')}")
        else:
            print(f"  {r}")

    events = holon_persistence.load_session(name)
    ran = sum(1 for r in results if r["status"] == "ran")
    print(f"\n[result] {ran}/{cycles} cycles ran LIVE & governed · {len(events)} persisted events (survives restart)")
    return 0 if ran else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run governed cycles for a registered sovereign holon.")
    parser.add_argument("agent", nargs="?", default="opus_composer")
    parser.add_argument("cycles", nargs="?", type=int, default=2)
    parser.add_argument("--mode", choices=ROUTING_MODE_CHOICES, default="free-first")
    args = parser.parse_args()
    raise SystemExit(asyncio.run(run(args.agent, args.cycles, routing_mode=args.mode)))
