"""Model-slot and roster helpers for Forge v2 runner."""
from __future__ import annotations

import asyncio
import os
import time

from dharma_swarm.forge_v1.canonical import KIMI_TEMP1, _call, _provider_for_slot, pool_slots
from dharma_swarm.forge_v1.providers import _complete_and_close
from dharma_swarm.model_pool import (
    default_for_provider,
    forge_default_high_slot_verifier_id,
    forge_high_slot_model_ids,
)
from dharma_swarm.models import ProviderType

from .critic import _family

_TIER = {"frontier": 0, "strong": 1, "fast": 2, "free": 3, "local": 4}
FORGE_HIGH_SLOT_MIN_RELEASE_DATE = "2026-04-01"
DEFAULT_FORGE_HIGH_SLOT_PROBE_TIMEOUT_S = 20
DEFAULT_FORGE_GENERATOR_MODEL = default_for_provider(ProviderType.ZHIPU)
DEFAULT_FORGE_VERIFIER_MODEL = forge_default_high_slot_verifier_id()
FORGE_HIGH_SLOT_MODEL_IDS = forge_high_slot_model_ids()


class _SimpleSlot:
    """Minimal ModelSlot stand-in so a pinned model id (reproducible first slice)
    can be used directly, without depending on a stochastic pool draw."""

    def __init__(self, model_id, provider, tier="strong"):
        self.model_id = model_id
        self.provider = provider
        self.tier = tier


def _prefix_provider(model_id: str):
    """Prefix routing for capable models that are NOT discrete model_pool entries
    (mirrors providers._provider_for_model). Lets a capable model — e.g. gemini-* —
    be CHAMPIONED as generator/verifier instead of being locked out of the roster."""
    from dharma_swarm.model_hierarchy import ProviderType

    mid = (model_id or "").strip().lower()
    if mid.startswith("gemini"):
        return ProviderType.GOOGLE_AI
    if mid.startswith("gpt") or mid.startswith("o1") or mid.startswith("o3"):
        return ProviderType.OPENAI
    if mid.startswith("claude") or mid.startswith("opus") or mid.startswith("sonnet"):
        return ProviderType.ANTHROPIC
    if mid.startswith("glm-5.2") or mid.startswith("zai/") or mid.startswith("z-ai/"):
        return ProviderType.ZHIPU
    if mid.startswith("moonshot:"):
        return ProviderType.MOONSHOT  # RSI-LAB travel route: api.moonshot.ai lane
    if mid in {"k3", "kimi-for-coding", "kimi-code"} or mid.startswith("kimi_code/") or mid.startswith("kimi-code/"):
        return ProviderType.KIMI_CODE
    if mid.startswith("nvidia/") or mid.startswith("meta/") or "llama" in mid:
        return ProviderType.NVIDIA_NIM
    if "/" in mid:
        return ProviderType.OPENROUTER
    return None


def _slot_for_id(model_id: str):
    """Resolve a pinned model id to a (model_id, provider) slot. Prefer the model
    pool (hierarchy-true); fall back to PREFIX routing so a capable model that is
    not a discrete pool entry (e.g. gemini-2.5-flash) can still be pinned."""
    from dharma_swarm.model_pool import entry_for_model_id

    entry = entry_for_model_id(model_id)
    if entry is not None and entry.routes:
        route = next((r for r in entry.routes if r.model_id == model_id), entry.routes[0])
        return _SimpleSlot(route.model_id, route.provider, getattr(entry, "tier", "strong"))
    prov = _prefix_provider(model_id)
    if prov is not None:
        wire = model_id.split(":", 1)[1] if model_id.startswith("moonshot:") else model_id
        return _SimpleSlot(wire, prov, "frontier")
    return None


def _dedupe_model_ids(model_ids: list[str] | tuple[str, ...]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for model_id in model_ids:
        mid = (model_id or "").strip()
        key = mid.lower()
        if not mid or key in seen:
            continue
        seen.add(key)
        out.append(mid)
    return out


def _is_high_slot_model_id(model_id: str) -> bool:
    """True iff ``model_id`` is allowed for Forge generator/verifier slots.

    Forge high slots are deliberately stricter than the general Dharma router:
    they may use only the operator-curated post-2026-04 frontier ladder. Older or
    sub-floor models can still be used as delegated workhorses elsewhere, but not
    as the top-level evolution grader/generator unless explicitly overridden.
    """
    if os.environ.get("FORGE_ALLOW_LEGACY_HIGH_SLOT") == "1":
        return True
    mid = (model_id or "").strip()
    if mid in FORGE_HIGH_SLOT_MODEL_IDS:
        return True
    return False


def _high_slot_candidate_ids(*preferred_ids: str | None) -> list[str]:
    preferred = [model_id for model_id in preferred_ids if model_id]
    return _dedupe_model_ids([*preferred, *FORGE_HIGH_SLOT_MODEL_IDS])


def _high_slot_probe_timeout_s(timeout_s: int) -> int:
    configured = int(
        os.environ.get(
            "FORGE_HIGH_SLOT_PROBE_TIMEOUT_S",
            str(DEFAULT_FORGE_HIGH_SLOT_PROBE_TIMEOUT_S),
        )
    )
    return max(1, min(int(timeout_s), configured))


def _probe_model_identity(model_id: str) -> str:
    """Normalize only serving suffixes; never collapse different model families."""
    normalized = (model_id or "").strip().casefold()
    if normalized.endswith(":cloud"):
        normalized = normalized[:-6]
    elif normalized.endswith("-cloud"):
        normalized = normalized[:-6]
    return normalized


def _probe_with_receipt(slot, timeout_s=40) -> dict:
    """Return a typed, redacted reachability receipt for one exact model route.

    A non-empty response is insufficient: some providers transparently fall
    back across model families.  Forge high-slot authority requires the served
    model identity to match the requested route before it can contribute to a
    cross-family pair.
    """
    started = time.monotonic()
    requested_model = str(slot.model_id)
    receipt = {
        "outcome": "unavailable",
        "callable": False,
        "requested_model": requested_model,
        "requested_family": _family(requested_model),
    }

    def finish(**fields) -> dict:
        receipt.update(fields)
        receipt["latency_ms"] = round((time.monotonic() - started) * 1000)
        return receipt

    try:
        prov, wire = _provider_for_slot(slot, timeout_s=timeout_s)
    except Exception as exc:
        return finish(stage="config", error_type=type(exc).__name__)

    temp = 1.0 if slot.model_id in KIMI_TEMP1 else 0.2
    # 256 (not 16): reasoning models can spend tokens on internal thinking
    # before visible output; 16 creates false empty-response negatives.
    from dharma_swarm.models import LLMRequest

    req = LLMRequest(
        model=wire,
        messages=[{"role": "user", "content": "Reply with the single word OK."}],
        max_tokens=256,
        temperature=temp,
    )
    receipt["wire_model"] = wire
    try:
        response = asyncio.run(_complete_and_close(prov, req, timeout_s=timeout_s))
    except TimeoutError as exc:
        return finish(stage="timeout", error_type=type(exc).__name__)
    except Exception as exc:
        return finish(stage="call", error_type=type(exc).__name__)

    served_model = str(getattr(response, "model", "") or "").strip()
    content = str(getattr(response, "content", "") or "").strip()
    if not served_model:
        return finish(stage="response", error_type="missing_served_model")

    served_family = _family(served_model)
    identity_matches = (
        _probe_model_identity(requested_model) == _probe_model_identity(served_model)
    )
    if not identity_matches:
        return finish(
            stage="response",
            error_type="served_model_mismatch",
            served_model=served_model,
            served_family=served_family,
        )
    if not content:
        return finish(
            stage="response",
            error_type="empty_content",
            served_model=served_model,
            served_family=served_family,
        )
    return finish(
        outcome="callable",
        callable=True,
        stage="complete",
        served_model=served_model,
        served_family=served_family,
    )


def _probe(slot, timeout_s=40) -> bool:
    """Compatibility boolean over the typed probe receipt."""
    return bool(_probe_with_receipt(slot, timeout_s=timeout_s)["callable"])


def _resolve_high_slot_pair(gen_id: str | None, ver_id: str | None, *, timeout_s: int):
    """Resolve Forge's generator/verifier through the recent-frontier ladder.

    This is not the general Dharma Swarm fallback router. It is the stricter
    Forge high-slot policy: exact pins are tried first only if they satisfy the
    recent-frontier floor; then the curated >=2026-04 ladder is probed. The first
    callable model becomes generator, and the first callable cross-family model
    becomes verifier.
    """
    callable_slots: list = []
    callable_rows: list[dict] = []
    rows: list[dict] = []
    probe_timeout_s = _high_slot_probe_timeout_s(timeout_s)
    for model_id in _high_slot_candidate_ids(gen_id, ver_id):
        slot = _slot_for_id(model_id)
        row = {
            "role": "forge_high_slot_candidate",
            "model_id": model_id,
            "high_slot_min_release_date": FORGE_HIGH_SLOT_MIN_RELEASE_DATE,
            "probe_timeout_s": probe_timeout_s,
        }
        if slot is None:
            row.update(
                {
                    "outcome": "unavailable",
                    "callable": False,
                    "stage": "config",
                    "error_type": "unresolved_model_id",
                }
            )
            rows.append(row)
            continue
        row["provider"] = getattr(slot.provider, "value", str(slot.provider))
        if not _is_high_slot_model_id(slot.model_id):
            row.update(
                {
                    "outcome": "unavailable",
                    "callable": False,
                    "stage": "policy",
                    "error_type": "below_recent_high_slot_floor",
                }
            )
            rows.append(row)
            continue
        probe_receipt = _probe_with_receipt(slot, timeout_s=probe_timeout_s)
        row.update(probe_receipt)
        rows.append(row)
        if row["callable"]:
            callable_slots.append(slot)
            callable_rows.append(row)
            if len({candidate["served_family"] for candidate in callable_rows}) >= 2:
                break

    gen = callable_slots[0] if callable_slots else None
    ver = None
    if gen is not None:
        gfam = callable_rows[0]["served_family"]
        ver = next(
            (
                slot
                for slot, row in zip(callable_slots[1:], callable_rows[1:])
                if row["served_family"] != gfam
            ),
            None,
        )
    return gen, ver, callable_slots, rows


def _callable_roster(n: int, strategy: str, timeout_s: int = 40) -> tuple[list, list]:
    """pool_slots -> probe reachable. Returns (callable_slots, probe_rows)."""
    slots = pool_slots(n=n, strategy=strategy)
    seen, uniq = set(), []
    for s in slots:
        if s.model_id in seen:
            continue
        seen.add(s.model_id)
        uniq.append(s)
    callable_slots, rows = [], []
    for s in uniq:
        try:
            prov, wire = _provider_for_slot(s, timeout_s=timeout_s)
            temp = 1.0 if s.model_id in KIMI_TEMP1 else 0.2
            text, _, _ = _call(prov, wire, "Reply with the single word OK.",
                               max_tokens=256, temperature=temp, timeout_s=timeout_s)
            ok = bool((text or "").strip())
            rows.append({"model_id": s.model_id, "provider": s.provider.value, "callable": ok})
            if ok:
                callable_slots.append(s)
        except Exception as e:
            rows.append({"model_id": s.model_id, "provider": s.provider.value, "callable": False,
                         "error": f"{type(e).__name__}"})
    return callable_slots, rows


def _pick_generator_verifier(callable_slots, gen_id=None, ver_id=None):
    if not callable_slots:
        return None, None
    by_id = {s.model_id: s for s in callable_slots}
    if gen_id and gen_id in by_id:
        gen = by_id[gen_id]
    else:
        gen = min(callable_slots, key=lambda s: _TIER.get(getattr(s.tier, "value", str(s.tier)), 9))
    gfam = _family(gen.model_id)
    if ver_id and ver_id in by_id and _family(by_id[ver_id].model_id) != gfam:
        ver = by_id[ver_id]
    else:
        ver = next((s for s in callable_slots if _family(s.model_id) != gfam), None)
    return gen, ver


def _resolve_pinned_slots(model_ids: list[str], *, timeout_s: int) -> tuple[list, list[dict]]:
    slots, probe_rows = [], []
    for model_id in model_ids:
        slot = _slot_for_id(model_id)
        receipt = (
            _probe_with_receipt(slot, timeout_s=timeout_s)
            if slot is not None
            else {
                "outcome": "unavailable",
                "callable": False,
                "requested_model": model_id,
                "requested_family": _family(model_id),
                "stage": "config",
                "error_type": "unresolved_model_id",
            }
        )
        ok = bool(receipt["callable"])
        probe_rows.append({"role": "mixed_moa", "model_id": model_id, **receipt})
        if ok:
            slots.append(slot)
    return slots, probe_rows


def _pick_mix_slots(callable_slots, gen, *, mix_ids: list[str] | None, timeout_s: int) -> tuple[list, list[dict]]:
    if mix_ids:
        slots, rows = _resolve_pinned_slots(mix_ids, timeout_s=timeout_s)
    else:
        rows = []
        slots = list(callable_slots)
    by_id = {s.model_id: s for s in slots}
    by_id.setdefault(gen.model_id, gen)
    slots = list(by_id.values())
    families, selected = set(), []
    for slot in sorted(slots, key=lambda s: _TIER.get(getattr(s.tier, "value", str(s.tier)), 9)):
        fam = _family(slot.model_id)
        if fam in families and len(selected) >= 2:
            continue
        families.add(fam)
        selected.append(slot)
        if len(selected) >= 4:
            break
    return selected, rows
