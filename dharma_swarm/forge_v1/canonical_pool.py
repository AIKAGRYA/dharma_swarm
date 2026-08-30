"""Pool access layer for the Forge v1 canonical measurement core.

Leaf module of ``canonical``: owns the roster draw, the hierarchy-true
provider construction, the single-call primitive with 429 backoff, and the
reachability census. It never imports ``canonical`` — the dependency direction
is ``canonical`` → ``canonical_pool`` only, with ``canonical`` re-exporting
these names for its historical import surface.
"""
from __future__ import annotations

import asyncio
import time

from dharma_swarm.forge_v1.providers import _complete_and_close, _usage_tokens
from dharma_swarm.forge_v1.run_real import _rate_limit_wait_s
from dharma_swarm.model_pool import (
    FORGE_KIMI_CODE_MODEL_ID,
    FORGE_KIMI_K3_LOGICAL_ID,
    FORGE_KIMI_K3_OPENROUTER_MODEL_ID,
)

# K3 has a 1M-token Kimi Code context window, so it no longer inherits the old
# K2.7 windowing workaround. It still requires temperature=1 on Kimi endpoints.
WINDOW_MODELS: frozenset[str] = frozenset()
KIMI_TEMP1 = {
    FORGE_KIMI_CODE_MODEL_ID,
    FORGE_KIMI_K3_LOGICAL_ID,
    FORGE_KIMI_K3_OPENROUTER_MODEL_ID,
}


# --------------------------------------------------------------------------- #
# Roster from the FULL pool, routed via each slot's OWN provider (hierarchy-true)
# --------------------------------------------------------------------------- #
def pool_slots(n: int, strategy: str = "explore"):
    from dharma_swarm.evolution_roster import select_models_for_cycle

    return select_models_for_cycle(n=n, strategy=strategy)


def _provider_for_slot(slot, *, timeout_s: int):
    """Build a live provider from a ModelSlot using its OWN provider type (not
    prefix-matching) — the hierarchy-true path. Raises if no live key/config."""
    from dharma_swarm.runtime_provider import (
        create_runtime_provider,
        resolve_runtime_provider_config,
    )

    cfg = resolve_runtime_provider_config(slot.provider, model=slot.model_id, timeout_seconds=timeout_s)
    if not cfg.available:
        raise RuntimeError(f"provider {slot.provider.value} has no live key/config")
    return create_runtime_provider(cfg), (cfg.default_model or slot.model_id)


def _call(provider, wire: str, prompt_or_messages, *, max_tokens: int, temperature: float,
          timeout_s: int) -> tuple[str, int, str | None]:
    """One live call with hard timeout + 429 backoff. Returns (text, tokens, stop_reason)."""
    from dharma_swarm.models import LLMRequest

    messages = ([{"role": "user", "content": prompt_or_messages}]
                if isinstance(prompt_or_messages, str) else prompt_or_messages)
    req = LLMRequest(model=wire, messages=messages, max_tokens=max_tokens, temperature=temperature)

    async def _c():
        return await _complete_and_close(provider, req, timeout_s=timeout_s)

    for attempt in range(4):
        try:
            r = asyncio.run(_c())
            return (r.content or ""), _usage_tokens(r.usage), getattr(r, "stop_reason", None)
        except Exception as e:
            w = _rate_limit_wait_s(e)
            if w is None or attempt >= 3:
                raise
            time.sleep(w)
    return "", 0, None


# --------------------------------------------------------------------------- #
# Census: which of the full pool is callable from HERE (the honest answer)
# --------------------------------------------------------------------------- #
def census(strategy: str = "explore", n: int = 12, *, timeout_s: int = 40) -> dict:
    slots = pool_slots(n=n, strategy=strategy)
    # dedupe by model_id, preserve order
    seen, uniq = set(), []
    for s in slots:
        if s.model_id in seen:
            continue
        seen.add(s.model_id)
        uniq.append(s)
    rows = []
    for s in uniq:
        row = {"model_id": s.model_id, "provider": s.provider.value, "tier": getattr(s.tier, "value", str(s.tier))}
        try:
            prov, wire = _provider_for_slot(s, timeout_s=timeout_s)
        except Exception as e:
            row["status"] = "no_route"
            row["detail"] = f"{type(e).__name__}: {str(e)[:60]}"
            rows.append(row)
            continue
        temp = 1.0 if s.model_id in KIMI_TEMP1 else 0.2
        t0 = time.time()
        try:
            text, toks, _ = _call(prov, wire, "Reply with the single word OK.",
                                   max_tokens=16, temperature=temp, timeout_s=timeout_s)
            row["seconds"] = round(time.time() - t0, 1)
            row["status"] = "callable" if (text or "").strip() else "empty"
            row["sample"] = (text or "").strip()[:24]
        except Exception as e:
            row["seconds"] = round(time.time() - t0, 1)
            row["status"] = "error"
            row["detail"] = f"{type(e).__name__}: {str(e)[:60]}"
        rows.append(row)
    callable_ids = [r["model_id"] for r in rows if r.get("status") == "callable"]
    return {"strategy": strategy, "n_requested": n, "n_pool_unique": len(uniq),
            "n_callable": len(callable_ids), "callable": callable_ids, "rows": rows}
