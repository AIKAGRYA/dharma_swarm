"""Centralized API key resolution for the entire swarm.

**Every** module that needs an LLM API key MUST go through this module
instead of calling ``os.getenv("OPENROUTER_API_KEY")`` directly.

This is the single source of truth for:
  - Which env vars to check for each provider
  - Fallback chain ordering (free → cheap → frontier)
  - Availability checking (is any LLM provider reachable at all?)
  - Future: keychain / vault / secrets-manager integration

Usage::

    from dharma_swarm.api_keys import get_llm_key, best_available_provider, has_any_llm

    # Get a specific provider's key (returns None if missing)
    key = get_llm_key("openrouter")

    # Get the best available provider + key for an ad-hoc LLM call
    provider, key, model = best_available_provider()

    # Check if we can call any LLM at all
    if not has_any_llm():
        logger.warning("No LLM keys configured")
"""

from __future__ import annotations

import os
import shutil
from typing import Mapping, NamedTuple

from dharma_swarm.models import ProviderType


# ── Canonical env var map ──────────────────────────────────────────────

PROVIDER_ENV_KEYS: dict[ProviderType, str] = {
    ProviderType.ANTHROPIC: "ANTHROPIC_API_KEY",
    ProviderType.OPENAI: "OPENAI_API_KEY",
    ProviderType.OPENROUTER: "OPENROUTER_API_KEY",
    ProviderType.OPENROUTER_FREE: "OPENROUTER_API_KEY",
    ProviderType.NVIDIA_NIM: "NVIDIA_NIM_API_KEY",
    ProviderType.GROQ: "GROQ_API_KEY",
    ProviderType.CEREBRAS: "CEREBRAS_API_KEY",
    ProviderType.SILICONFLOW: "SILICONFLOW_API_KEY",
    ProviderType.TOGETHER: "TOGETHER_API_KEY",
    ProviderType.FIREWORKS: "FIREWORKS_API_KEY",
    ProviderType.SAMBANOVA: "SAMBANOVA_API_KEY",
    ProviderType.MISTRAL: "MISTRAL_API_KEY",
    ProviderType.GOOGLE_AI: "GOOGLE_AI_API_KEY",
    ProviderType.MOONSHOT: "MOONSHOT_API_KEY",
    ProviderType.ZAI: "ZAI_API_KEY",
    ProviderType.DEEPSEEK: "DEEPSEEK_API_KEY",
    ProviderType.MINIMAX: "MINIMAX_API_KEY",
    ProviderType.HYPERBOLIC: "HYPERBOLIC_API_KEY",
    ProviderType.REPLICATE: "REPLICATE_API_TOKEN",
    ProviderType.DEEPINFRA: "DEEPINFRA_API_KEY",
    ProviderType.AZURE: "AZURE_OPENAI_API_KEY",
    ProviderType.BEDROCK: "AWS_SECRET_ACCESS_KEY",
}

# Shorthand aliases so callers don't need to import ProviderType
_ALIAS_MAP: dict[str, ProviderType] = {
    "anthropic": ProviderType.ANTHROPIC,
    "openai": ProviderType.OPENAI,
    "openrouter": ProviderType.OPENROUTER,
    "openrouter_free": ProviderType.OPENROUTER_FREE,
    "nvidia_nim": ProviderType.NVIDIA_NIM,
    "nvidia": ProviderType.NVIDIA_NIM,
    "ollama": ProviderType.OLLAMA,
    "claude_code": ProviderType.CLAUDE_CODE,
    "codex": ProviderType.CODEX,
    "groq": ProviderType.GROQ,
    "cerebras": ProviderType.CEREBRAS,
    "siliconflow": ProviderType.SILICONFLOW,
    "together": ProviderType.TOGETHER,
    "fireworks": ProviderType.FIREWORKS,
    "sambanova": ProviderType.SAMBANOVA,
    "mistral": ProviderType.MISTRAL,
    "google": ProviderType.GOOGLE_AI,
    "google_ai": ProviderType.GOOGLE_AI,
    "moonshot": ProviderType.MOONSHOT,
    "kimi": ProviderType.MOONSHOT,
    "zai": ProviderType.ZAI,
    "zhipu": ProviderType.ZAI,
    "deepseek": ProviderType.DEEPSEEK,
    "minimax": ProviderType.MINIMAX,
    "hyperbolic": ProviderType.HYPERBOLIC,
    "replicate": ProviderType.REPLICATE,
    "deepinfra": ProviderType.DEEPINFRA,
    "azure": ProviderType.AZURE,
    "bedrock": ProviderType.BEDROCK,
    "aws": ProviderType.BEDROCK,
}

# Default models per provider for ad-hoc calls
_DEFAULT_MODELS: dict[ProviderType, str] = {
    ProviderType.OPENROUTER: "meta-llama/llama-3.3-70b-instruct",
    ProviderType.OPENROUTER_FREE: "meta-llama/llama-3.3-70b-instruct",
    ProviderType.ANTHROPIC: "claude-sonnet-4-20250514",
    ProviderType.OPENAI: "gpt-5.4",
    ProviderType.NVIDIA_NIM: "meta/llama-3.3-70b-instruct",
    ProviderType.MOONSHOT: "kimi-k2.5",
    ProviderType.ZAI: "glm-5-turbo",
    ProviderType.DEEPSEEK: "deepseek-chat",
    ProviderType.MINIMAX: "minimax-m2.7",
    ProviderType.HYPERBOLIC: "deepseek-ai/DeepSeek-V3.2",
    ProviderType.REPLICATE: "meta/llama-3.3-70b",
}

# Fallback ordering: cheapest/free first → paid last
_FALLBACK_CHAIN: tuple[ProviderType, ...] = (
    ProviderType.OLLAMA,
    ProviderType.NVIDIA_NIM,
    ProviderType.OPENROUTER_FREE,
    ProviderType.OPENROUTER,
    ProviderType.DEEPSEEK,       # $0.55/$2.19 - best value
    ProviderType.MINIMAX,        # $0.30/$1.20 - fast agentic
    ProviderType.MOONSHOT,
    ProviderType.ZAI,
    ProviderType.HYPERBOLIC,     # $2/$2 - good pricing
    ProviderType.FIREWORKS,
    ProviderType.SILICONFLOW,
    ProviderType.TOGETHER,
    ProviderType.GROQ,
    ProviderType.CEREBRAS,
    ProviderType.OPENAI,
    ProviderType.ANTHROPIC,
    ProviderType.CLAUDE_CODE,
    ProviderType.CODEX,
)


# ── Core functions ─────────────────────────────────────────────────────

def _resolve_provider(provider: str | ProviderType) -> ProviderType:
    """Normalize a string or enum to ProviderType."""
    if isinstance(provider, ProviderType):
        return provider
    key = str(provider).strip().lower().replace("-", "_")
    if key in _ALIAS_MAP:
        return _ALIAS_MAP[key]
    # Try direct enum match
    for pt in ProviderType:
        if pt.value == key:
            return pt
    raise ValueError(f"Unknown provider: {provider!r}")


def get_llm_key(
    provider: str | ProviderType,
    *,
    env: Mapping[str, str] | None = None,
) -> str | None:
    """Get the API key for a provider, or None if not configured.

    This is the **only** function modules should use to resolve API keys.
    """
    pt = _resolve_provider(provider)
    env_map = env or os.environ
    env_var = PROVIDER_ENV_KEYS.get(pt)
    if env_var is None:
        # Providers that don't need API keys (Ollama, Claude Code, Codex)
        return None
    value = str(env_map.get(env_var, "")).strip()
    return value or None


def provider_available(
    provider: str | ProviderType,
    *,
    env: Mapping[str, str] | None = None,
) -> bool:
    """Check if a provider is usable (key set or no key needed)."""
    pt = _resolve_provider(provider)

    # Keyless providers — check binary existence
    if pt == ProviderType.CLAUDE_CODE:
        return shutil.which("claude") is not None
    if pt == ProviderType.CODEX:
        return shutil.which("codex") is not None
    if pt == ProviderType.OLLAMA:
        # Ollama availability depends on whether the server is reachable,
        # but for key-checking purposes, consider it available if configured.
        env_map = env or os.environ
        base = str(env_map.get("OLLAMA_BASE_URL", "")).strip()
        key = str(env_map.get("OLLAMA_API_KEY", "")).strip()
        return bool(base or key)

    # Key-based providers
    return get_llm_key(pt, env=env) is not None


def has_any_llm(*, env: Mapping[str, str] | None = None) -> bool:
    """Return True if at least one LLM provider is available."""
    return any(provider_available(pt, env=env) for pt in _FALLBACK_CHAIN)


class ProviderSelection(NamedTuple):
    """Result of best_available_provider()."""
    provider: ProviderType
    api_key: str | None
    model: str
    base_url: str | None


def best_available_provider(
    *,
    env: Mapping[str, str] | None = None,
    prefer: str | ProviderType | None = None,
) -> ProviderSelection | None:
    """Return the best available provider for an ad-hoc LLM call.

    Walks the fallback chain (cheapest first), returns the first provider
    that has credentials. If ``prefer`` is given and available, it wins.

    Returns None if no provider is available.
    """
    if prefer is not None:
        pt = _resolve_provider(prefer)
        if provider_available(pt, env=env):
            return ProviderSelection(
                provider=pt,
                api_key=get_llm_key(pt, env=env),
                model=_DEFAULT_MODELS.get(pt, ""),
                base_url=_base_url_for(pt, env=env),
            )

    for pt in _FALLBACK_CHAIN:
        if provider_available(pt, env=env):
            return ProviderSelection(
                provider=pt,
                api_key=get_llm_key(pt, env=env),
                model=_DEFAULT_MODELS.get(pt, ""),
                base_url=_base_url_for(pt, env=env),
            )

    return None


def _base_url_for(
    provider: ProviderType,
    env: Mapping[str, str] | None = None,
) -> str | None:
    """Return the base URL for providers that need one."""
    env_map = env or os.environ
    if provider in (ProviderType.OPENROUTER, ProviderType.OPENROUTER_FREE):
        return "https://openrouter.ai/api/v1"
    if provider == ProviderType.NVIDIA_NIM:
        return str(env_map.get("NVIDIA_NIM_BASE_URL", "")).strip() or "https://integrate.api.nvidia.com/v1"
    if provider == ProviderType.OLLAMA:
        return str(env_map.get("OLLAMA_BASE_URL", "")).strip() or "http://localhost:11434"
    if provider == ProviderType.MOONSHOT:
        return str(env_map.get("MOONSHOT_BASE_URL", "")).strip() or "https://api.kimi.com/coding/v1"
    if provider == ProviderType.ZAI:
        return str(env_map.get("ZAI_BASE_URL", "")).strip() or "https://api.z.ai/api/paas/v4"
    return None


def openai_client_for_best_provider(
    *,
    env: Mapping[str, str] | None = None,
    prefer: str | ProviderType | None = None,
):
    """Create an AsyncOpenAI client pointed at the best available provider.

    Most ad-hoc callers in the codebase (ginko_agents, hypnagogic,
    subconscious_v2, etc.) just need a simple OpenAI-compatible client.
    This gives them one without hardcoding API keys.

    Returns (client, model) or raises RuntimeError if nothing is available.
    """
    from openai import AsyncOpenAI

    sel = best_available_provider(env=env, prefer=prefer)
    if sel is None:
        raise RuntimeError(
            "No LLM provider available. Set at least one of: "
            + ", ".join(sorted(set(PROVIDER_ENV_KEYS.values())))
        )

    if sel.provider == ProviderType.ANTHROPIC:
        # Anthropic doesn't use OpenAI client; route through OpenRouter
        # or fall back to Anthropic SDK
        from anthropic import AsyncAnthropic
        client = AsyncAnthropic(api_key=sel.api_key)
        return client, sel.model, "anthropic"

    kwargs: dict = {"api_key": sel.api_key}
    if sel.base_url:
        kwargs["base_url"] = sel.base_url

    return AsyncOpenAI(**kwargs), sel.model, sel.provider.value


__all__ = [
    "PROVIDER_ENV_KEYS",
    "ProviderSelection",
    "best_available_provider",
    "get_llm_key",
    "has_any_llm",
    "openai_client_for_best_provider",
    "provider_available",
]
