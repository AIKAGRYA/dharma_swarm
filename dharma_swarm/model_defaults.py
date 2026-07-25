"""Per-provider default model ids — the ONE place these strings live (STEP 3).

This is the leaf that owns the per-provider default literals. It imports ONLY
:mod:`dharma_swarm.models` (for :class:`ProviderType`), so every higher layer can
project from it without an import cycle:

* :data:`model_pool.MODEL_POOL` is the model-grain route table (seeded from the
  evolution roster); it re-exports :func:`default_for_provider` so the pool stays
  the public model-grain surface described by the consolidation goal.
* :data:`model_hierarchy.DEFAULT_MODELS` is a thin projection of this map.
* :data:`runtime_provider.DEFAULT_*` read it via ``model_hierarchy.default_model``.
* :mod:`ollama_config` reads its Ollama default straight from here.

Why a dedicated leaf and not ``model_pool`` itself: ``model_pool`` imports the
evolution roster, which (transitively, via ``ollama_config``) reaches back into
``model_hierarchy`` — so the per-provider default literals must sit BELOW that
cycle. ``model_pool`` re-exports the function, preserving the goal's "pool is the
one model-grain owner" contract at the public boundary.

THE ONE WAY / FAIL-OPEN: no key strings live here; an unknown provider (e.g.
``LOCAL``) returns "" rather than raising — callers keep their existing
"no default configured" behaviour.
"""

from __future__ import annotations

from dharma_swarm.models import ProviderType

# Floor marker re-stated for locality (the pool owns the doctrine; this is the
# grade the per-provider defaults must respect): never default a provider to a
# model below Kimi K2.6-class. ``MODEL_POWER_FLOOR`` is the documented-line
# alias (same string), re-exported by ``model_hierarchy`` and ``model_pool`` so
# every layer reads ONE constant.
K2_FLOOR_ID = "kimi-k2.6"
MODEL_POWER_FLOOR = K2_FLOOR_ID

# ---------------------------------------------------------------------------
# The ONE per-provider default map. The string is the EXACT id a given provider
# expects when ``request.model`` is empty. Collapsing the old ~17 scattered
# literals (model_hierarchy.DEFAULT_MODELS, runtime_provider DEFAULT_*,
# ollama_config) into this single owner is the keystone of the consolidation.
# ---------------------------------------------------------------------------
_PROVIDER_DEFAULTS: dict[ProviderType, str] = {
    # Free tier — frontier. FLOOR-compliant (>= MODEL_POWER_FLOOR / K2.6): the
    # Ollama default is the GLM-5.1 floor lane, not the superseded sub-floor
    # GLM-5 — so an empty-model request on this provider never routes sub-floor.
    ProviderType.OLLAMA: "glm-5.1:cloud",
    ProviderType.NVIDIA_NIM: "meta/llama-3.3-70b-instruct",
    ProviderType.GROQ: "qwen/qwen3-32b",
    ProviderType.CEREBRAS: "qwen-3-235b-a22b-instruct-2507",
    ProviderType.SILICONFLOW: "Qwen/Qwen3-Coder-480B-A35B-Instruct",
    ProviderType.SAMBANOVA: "Meta-Llama-3.3-70B-Instruct",
    ProviderType.TOGETHER: "Qwen/Qwen3-Coder-480B-A35B-Instruct-FP8",
    ProviderType.FIREWORKS: "accounts/fireworks/models/qwen3-coder-480b-a35b-instruct",
    # Cheap tier
    ProviderType.MISTRAL: "mistral-small-latest",
    ProviderType.GOOGLE_AI: "gemini-2.5-flash",
    ProviderType.CHUTES: "deepseek-ai/DeepSeek-R1",
    # z.ai / Zhipu direct — first-party GLM lane (not routed via OpenRouter).
    # glm-5.2 is the current frontier GLM (mid-2026).
    ProviderType.ZHIPU: "glm-5.2",
    # Kimi Code membership lane. K3 is exposed as the short provider-specific
    # id ``k3`` on https://api.kimi.com/coding/v1.
    ProviderType.KIMI_CODE: "k3",
    # Moonshot global OpenAI-compatible lane uses its own model namespace.
    ProviderType.MOONSHOT: "kimi-k3",
    ProviderType.OPENROUTER_FREE: "meta-llama/llama-3.3-70b-instruct:free",
    # Paid / subscription tier
    # K3 on OpenRouter uses the fully-qualified vendor namespace. OpenRouter is
    # still a secondary aggregator route behind the first-party Kimi providers.
    ProviderType.OPENROUTER: "moonshotai/kimi-k3",
    ProviderType.OPENAI: "gpt-5",
    ProviderType.ANTHROPIC: "claude-opus-4-6",
    ProviderType.CLAUDE_CODE: "claude-opus-4-6",
    ProviderType.CODEX: "gpt-5.4",
}


def default_for_provider(provider: ProviderType) -> str:
    """Return the pool's default provider-specific model id for ``provider``.

    The ONE owner of the per-provider default string. Unknown providers (e.g.
    ``LOCAL``) return "" — never raises (FAIL-OPEN).
    """
    return _PROVIDER_DEFAULTS.get(provider, "")


__all__ = [
    "K2_FLOOR_ID",
    "MODEL_POWER_FLOOR",
    "default_for_provider",
]
