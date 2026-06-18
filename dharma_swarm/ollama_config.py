"""Canonical Ollama endpoint and model resolution helpers."""

from __future__ import annotations

import os

from dharma_swarm.api_keys import OLLAMA_API_KEY_ENV, env_value
from dharma_swarm.model_defaults import default_for_provider
from dharma_swarm.models import ProviderType


OLLAMA_LOCAL_BASE_URL = "http://localhost:11434"
OLLAMA_CLOUD_BASE_URL = "https://ollama.com"
# Default to a model that is actually pulled locally. llama3.2 was the old
# default but is frequently not pulled (-> Ollama 404). Override with
# OLLAMA_LOCAL_MODEL=<name> per machine. (2026-06-06: "available" must mean serveable.)
OLLAMA_DEFAULT_LOCAL_MODEL = os.getenv("OLLAMA_LOCAL_MODEL", "mistral:latest")
OLLAMA_DEFAULT_CLOUD_MODEL = default_for_provider(ProviderType.OLLAMA)


def _ollama_cloud_frontier_from_roster() -> tuple[str, ...]:
    """Fail-open fallback for the Ollama Cloud frontier chain, with NO literals.

    Used ONLY if the model pool cannot be imported at populate time (mid
    import-cycle / partial init). The model-id strings live in exactly one place
    — ``evolution_roster.EVOLUTION_ROSTER`` (the pool's seed, and the sanctioned
    home for model-id literals). This derives the Ollama-Cloud routes directly
    from that seed so the chain stays non-empty without re-typing any model-id.

    Lazy import inside the function: at call time (bottom-of-module populate, or
    a later degenerate retry) the roster is fully initialised even though the
    ``model_pool`` projection may not be. Returns pool-equivalent order
    (roster order), deduped, K2.6 floor included.
    """
    try:
        from dharma_swarm.evolution_roster import EVOLUTION_ROSTER  # noqa: PLC0415 (lazy: cycle break)
    except Exception:  # pragma: no cover - degenerate mid-cycle import
        return ()
    out: list[str] = []
    for slot in EVOLUTION_ROSTER:
        mid = slot.model_id
        if (mid.endswith(":cloud") or mid.endswith("-cloud")) and mid not in out:
            out.append(mid)
    return tuple(out)


def _generate_ollama_cloud_frontier_models() -> tuple[str, ...]:
    """Derive the Ollama Cloud frontier chain from the ONE model pool.

    STEP 6 of the model-routing consolidation: this REPLACES the hand-typed
    frontier tuple. The chain is every Ollama route the pool serves over the
    cloud endpoint (``:cloud`` / ``-cloud`` serving tag), in pool order
    (best-route-first), deduped. The K2.6 floor model is included because the
    pool carries it as an Ollama-Cloud route.

    Lazy import: ``model_pool`` -> ``evolution_roster`` -> this module form an
    import cycle. We import the pool *inside* the function so ``ollama_config``
    stays importable on its own. FAIL-OPEN: any import/parse failure falls back
    to the roster-derived chain (still no literals here) so the chain is never
    empty.
    """
    try:
        from dharma_swarm.model_pool import ollama_cloud_model_ids  # noqa: PLC0415 (lazy: cycle break)
    except Exception:  # pragma: no cover - degenerate mid-cycle import
        return _ollama_cloud_frontier_from_roster()

    return ollama_cloud_model_ids() or _ollama_cloud_frontier_from_roster()


#: Ollama Cloud frontier chain — a SNAPSHOT of the pool generator (no longer a
#: hand-typed literal). Initialised empty and populated at the BOTTOM of this
#: module (after the helper functions evolution_roster needs are defined) so the
#: model_pool import cycle resolves cleanly. Consumers (providers.py hot path,
#: startup_crew, smoke tests) keep reading this module constant unchanged.
OLLAMA_CLOUD_FRONTIER_MODELS: tuple[str, ...] = ()

_LOCAL_BASE_URLS = {
    OLLAMA_LOCAL_BASE_URL,
    "http://127.0.0.1:11434",
    "http://0.0.0.0:11434",
}


def _normalize_base_url(base_url: str | None) -> str:
    return (base_url or "").strip().rstrip("/")


def _env_flag(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in {"1", "true", "yes", "on"}


def is_ollama_cloud_base_url(base_url: str | None) -> bool:
    normalized = _normalize_base_url(base_url)
    return normalized.startswith(OLLAMA_CLOUD_BASE_URL)


def ollama_prefers_cloud(
    *,
    base_url: str | None = None,
    api_key: str | None = None,
) -> bool:
    if _env_flag("OLLAMA_FORCE_LOCAL"):
        return False
    if _env_flag("OLLAMA_USE_CLOUD"):
        return True

    resolved_key = (
        api_key if api_key is not None else env_value(OLLAMA_API_KEY_ENV)
    )
    if not resolved_key:
        return False

    candidate = _normalize_base_url(
        base_url if base_url is not None else os.environ.get("OLLAMA_BASE_URL")
    )
    if not candidate or candidate in _LOCAL_BASE_URLS:
        return True
    return is_ollama_cloud_base_url(candidate)


def resolve_ollama_base_url(
    *,
    base_url: str | None = None,
    api_key: str | None = None,
) -> str:
    explicit = _normalize_base_url(base_url)
    if explicit:
        return explicit

    configured = _normalize_base_url(os.environ.get("OLLAMA_BASE_URL"))
    if ollama_prefers_cloud(base_url=configured or None, api_key=api_key):
        return OLLAMA_CLOUD_BASE_URL
    return configured or OLLAMA_LOCAL_BASE_URL


def ollama_transport_mode(
    *,
    base_url: str | None = None,
    api_key: str | None = None,
) -> str:
    resolved = resolve_ollama_base_url(base_url=base_url, api_key=api_key)
    return "cloud_api" if is_ollama_cloud_base_url(resolved) else "local_api"


def resolve_ollama_model(
    model: str | None = None,
    *,
    base_url: str | None = None,
    api_key: str | None = None,
) -> str:
    explicit = (model or "").strip()
    if explicit:
        return explicit

    configured = os.environ.get("OLLAMA_MODEL", "").strip()
    if configured:
        return configured

    if ollama_transport_mode(base_url=base_url, api_key=api_key) == "cloud_api":
        return OLLAMA_DEFAULT_CLOUD_MODEL
    return OLLAMA_DEFAULT_LOCAL_MODEL


def is_ollama_cloud_model(model: str | None) -> bool:
    """True if the model id targets Ollama Cloud (proxied by the local daemon)."""
    name = (model or "").strip()
    return name.endswith(":cloud") or name.endswith("-cloud")


def build_ollama_headers(
    *,
    base_url: str | None = None,
    api_key: str | None = None,
) -> dict[str, str]:
    resolved = resolve_ollama_base_url(base_url=base_url, api_key=api_key)
    if not is_ollama_cloud_base_url(resolved):
        return {}

    token = api_key if api_key is not None else env_value(OLLAMA_API_KEY_ENV)
    if not token:
        raise RuntimeError("OLLAMA_API_KEY not set")
    return {"Authorization": f"Bearer {token}"}


def get_ollama_cloud_frontier_chain() -> tuple[str, ...]:
    """Return Ollama Cloud frontier models in priority order for fallback rotation.

    The chain is derived from the ONE model pool (Ollama-Cloud routes,
    best-route-first). When the primary model fails, callers try the next model
    in this chain.  All models are FREE on Ollama Cloud.
    """
    return OLLAMA_CLOUD_FRONTIER_MODELS


# Populate the snapshot from the pool now that every helper evolution_roster
# needs is defined above — so the model_pool -> evolution_roster -> ollama_config
# cycle re-enters this module cleanly. Fail-open: keeps the roster-derived chain
# (no literals) on any error.
try:  # pragma: no cover - exercised by import
    OLLAMA_CLOUD_FRONTIER_MODELS = _generate_ollama_cloud_frontier_models()
except Exception:  # pragma: no cover - degenerate
    OLLAMA_CLOUD_FRONTIER_MODELS = _ollama_cloud_frontier_from_roster()


__all__ = [
    "OLLAMA_CLOUD_BASE_URL",
    "OLLAMA_CLOUD_FRONTIER_MODELS",
    "OLLAMA_DEFAULT_CLOUD_MODEL",
    "OLLAMA_DEFAULT_LOCAL_MODEL",
    "OLLAMA_LOCAL_BASE_URL",
    "build_ollama_headers",
    "get_ollama_cloud_frontier_chain",
    "is_ollama_cloud_base_url",
    "ollama_prefers_cloud",
    "ollama_transport_mode",
    "resolve_ollama_base_url",
    "resolve_ollama_model",
]
