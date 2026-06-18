"""Evolution Model Roster — multi-provider, multi-tier model selection.

Instead of always using a single OpenRouter model, the Darwin Engine now
draws from a diverse roster of models across providers.  Selection is
strategy-aware:

* **exploit** — frontier models for polishing winning solutions
* **explore** — diverse mid-tier models for creative proposals
* **restart** — cheap/fast models to rapidly escape local optima
* **backtrack** — strong models for careful analysis of regressions

The roster degrades gracefully: if a provider is unavailable (no API key,
Ollama not running, etc.) those slots are simply skipped.
"""

from __future__ import annotations

import logging
import os
import random
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

import httpx

from dharma_swarm.api_keys import PROVIDER_API_KEY_ENV_KEYS
from dharma_swarm.models import ProviderType
from dharma_swarm.ollama_config import (
    build_ollama_headers,
    ollama_transport_mode,
    resolve_ollama_base_url,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Model slot
# ---------------------------------------------------------------------------


class ModelTier(str, Enum):
    """Cost / capability tier for a model slot."""

    FRONTIER = "frontier"  # Opus, GPT-4o, o3 — expensive, best quality
    STRONG = "strong"      # DeepSeek V3, Qwen 72B, Llama 70B — good balance
    FAST = "fast"          # Groq-hosted, NIM-hosted — speed optimised
    FREE = "free"          # OpenRouter free tier — zero cost
    LOCAL = "local"        # Ollama — zero cost, variable speed


# ---------------------------------------------------------------------------
# THE POWER FLOOR — the unmistakable demarcation (operator word 2026-06-17:
# "sub-floor models can exist just for real grunt work only but ONLY with a
# very clear demarcation").
#
# The floor is Kimi K2.6-class. Models GREATER-THAN-OR-EQUAL to the floor serve
# the REAL path (default chat brain, frontier, the model picker's main list).
# Models BELOW the floor are old / weak / local weights that the K2.6 floor
# banishes from the real path. They are kept ONLY for genuine grunt work and
# MUST carry ``below_floor=True`` so the demarcation lives in the DATA, not in
# prose — every consumer can read one boolean and never accidentally route a
# sub-floor model onto the frontier.
#
# ``model_hierarchy`` and ``model_pool`` re-export :data:`MODEL_POWER_FLOOR` so
# the documented line has exactly one home.
# ---------------------------------------------------------------------------
MODEL_POWER_FLOOR = "kimi-k2.6"


@dataclass(frozen=True)
class ModelSlot:
    """A single model available for evolution proposals.

    ``below_floor`` is the operator's UNMISTAKABLE demarcation: ``True`` marks a
    sub-floor (old / weak / genuinely-local) model that the :data:`MODEL_POWER_FLOOR`
    (Kimi K2.6) banishes from the REAL path. Such a slot is kept for grunt work
    ONLY — the pool carries the marker into :class:`~dharma_swarm.model_pool.ModelEntry`
    and the default / frontier / picker projections skip it.
    """

    provider: ProviderType
    model_id: str
    display_name: str
    tier: ModelTier
    strengths: tuple[str, ...] = ()  # e.g. ("code", "reasoning", "speed")
    max_context: int = 128_000
    notes: str = ""
    below_floor: bool = False  # True == sub-floor, grunt-work-only (demarcation)


# ---------------------------------------------------------------------------
# The Roster
# ---------------------------------------------------------------------------

EVOLUTION_ROSTER: tuple[ModelSlot, ...] = (
    # ══════════════════════════════════════════════════════════════════
    # FLOOR FRONTIER — the REAL path (>= MODEL_POWER_FLOOR / Kimi K2.6).
    # These serve the default chat brain, frontier work, and the model
    # picker's main list. Live providers first (THE ONE WAY): claude_code
    # oauth (Max plan), codex oauth, ollama_cloud, GLM-zai, deepseek,
    # nvidia_nim, openai. openrouter + anthropic-API are DEAD — never a
    # primary floor route. below_floor stays False (default).
    # ══════════════════════════════════════════════════════════════════
    # Default chat brain: a FLOOR Claude on the Max-plan oauth lane.
    ModelSlot(
        ProviderType.CLAUDE_CODE,
        "claude-opus-4.8",
        "Claude Opus 4.8 (Claude Max)",
        ModelTier.FRONTIER,
        ("reasoning", "code", "architecture"),
        200_000,
        "Floor default chat brain — Opus via Claude-Max oauth (THE ONE WAY)",
    ),
    ModelSlot(
        ProviderType.CLAUDE_CODE,
        "claude-sonnet-4.6",
        "Claude Sonnet 4.6 (Claude Max)",
        ModelTier.FRONTIER,
        ("code", "reasoning", "speed"),
        200_000,
        "Floor fast-frontier Claude via Claude-Max oauth",
    ),
    # GPT-5.5 floor lane: codex oauth subscription (live) ahead of metered API.
    ModelSlot(
        ProviderType.CODEX,
        "gpt-5.5",
        "GPT-5.5 (Codex)",
        ModelTier.FRONTIER,
        ("code", "reasoning", "architecture"),
        256_000,
        "Floor GPT lane via codex oauth subscription (THE ONE WAY)",
    ),
    ModelSlot(
        ProviderType.OPENAI,
        "gpt-5.5",
        "GPT-5.5 (direct)",
        ModelTier.FRONTIER,
        ("code", "reasoning", "architecture"),
        256_000,
        "Same weights via the OpenAI direct API (secondary route)",
    ),
    # ── Strong floor tier (Ollama Cloud frontier, keyless) ─────────────
    # ── Frontier tier ──────────────────────────────────────────────────
    # BELOW FLOOR — old direct/router Claude/GPT-4o weights. Kept for grunt
    # work ONLY; the K2.6 floor banishes them from the real path.
    ModelSlot(
        ProviderType.ANTHROPIC,
        "claude-opus-4-20250514",
        "Claude Opus 4 (direct)",
        ModelTier.FRONTIER,
        ("reasoning", "code", "architecture"),
        200_000,
        "Sub-floor (old Opus 4) — grunt work only",
        below_floor=True,
    ),
    ModelSlot(
        ProviderType.ANTHROPIC,
        "claude-sonnet-4-20250514",
        "Claude Sonnet 4 (direct)",
        ModelTier.FRONTIER,
        ("code", "reasoning", "speed"),
        200_000,
        "Sub-floor (old Sonnet 4) — grunt work only",
        below_floor=True,
    ),
    ModelSlot(
        ProviderType.OPENAI,
        "gpt-4o",
        "GPT-4o (direct)",
        ModelTier.FRONTIER,
        ("code", "reasoning"),
        128_000,
        "Sub-floor (GPT-4o) — grunt work only",
        below_floor=True,
    ),
    # Same frontier models via OpenRouter (when direct keys aren't set)
    ModelSlot(
        ProviderType.OPENROUTER,
        "anthropic/claude-opus-4",
        "Claude Opus 4",
        ModelTier.FRONTIER,
        ("reasoning", "code", "architecture"),
        200_000,
        "Sub-floor (old Opus 4 via OpenRouter) — grunt work only",
        below_floor=True,
    ),
    ModelSlot(
        ProviderType.OPENROUTER,
        "anthropic/claude-sonnet-4",
        "Claude Sonnet 4",
        ModelTier.FRONTIER,
        ("code", "reasoning", "speed"),
        200_000,
        "Sub-floor (old Sonnet 4 via OpenRouter) — grunt work only",
        below_floor=True,
    ),
    ModelSlot(
        ProviderType.OPENROUTER,
        "openai/gpt-4o",
        "GPT-4o",
        ModelTier.FRONTIER,
        ("code", "reasoning"),
        128_000,
        "Sub-floor (GPT-4o via OpenRouter) — grunt work only",
        below_floor=True,
    ),
    ModelSlot(
        ProviderType.OPENROUTER,
        "openai/gpt-5-codex",
        "GPT-5 Codex",
        ModelTier.FRONTIER,
        ("code", "reasoning", "architecture"),
        200_000,
        "High-agency coding and technical synthesis via OpenRouter",
    ),
    # ── Strong tier (via OpenRouter) ───────────────────────────────────
    # BELOW FLOOR — old/weak open-weight router lanes. Grunt work only.
    ModelSlot(
        ProviderType.OPENROUTER,
        "moonshotai/kimi-k2.5",
        "Kimi K2.5",
        ModelTier.STRONG,
        ("reasoning", "long_context", "synthesis"),
        128_000,
        "Sub-floor (K2.5, superseded by K2.6 floor) — grunt work only",
        below_floor=True,
    ),
    ModelSlot(
        ProviderType.OPENROUTER,
        "z-ai/glm-5",
        "GLM 5",
        ModelTier.STRONG,
        ("reasoning", "synthesis", "multilingual"),
        128_000,
        "Sub-floor (GLM-5, superseded by GLM-5.1 floor) — grunt work only",
        below_floor=True,
    ),
    ModelSlot(
        ProviderType.OPENROUTER,
        "deepseek/deepseek-chat-v3-0324",
        "DeepSeek V3",
        ModelTier.STRONG,
        ("code", "reasoning", "chinese"),
        128_000,
        "Sub-floor (DeepSeek V3) — grunt work only",
        below_floor=True,
    ),
    ModelSlot(
        ProviderType.OPENROUTER,
        "qwen/qwen-2.5-coder-32b-instruct",
        "Qwen 2.5 Coder 32B",
        ModelTier.STRONG,
        ("code",),
        32_768,
        "Sub-floor (Qwen 2.5 Coder 32B) — grunt work only",
        below_floor=True,
    ),
    ModelSlot(
        ProviderType.OPENROUTER,
        "qwen/qwen3-235b-a22b",
        "Qwen 3 235B (MoE)",
        ModelTier.STRONG,
        ("reasoning", "code", "chinese"),
        128_000,
        "Massive MoE — deep reasoning with efficient inference",
    ),
    ModelSlot(
        ProviderType.OPENROUTER,
        "mistralai/mistral-large-2411",
        "Mistral Large",
        ModelTier.STRONG,
        ("code", "reasoning"),
        128_000,
        "Sub-floor (Mistral Large 2411) — grunt work only",
        below_floor=True,
    ),
    # Gemini frontier-class lane via the OpenRouter aggregator. The TUI/openrouter
    # adapter used to hand-type ``google/gemini-2.5-pro`` (sub-floor); the floor is
    # gemini-3-pro, so the pool owns the route here and the surfaces project it.
    ModelSlot(
        ProviderType.OPENROUTER,
        "google/gemini-3-pro",
        "Gemini 3 Pro",
        ModelTier.STRONG,
        ("reasoning", "long_context", "multimodal"),
        1_000_000,
        "Gemini 3 class via OpenRouter — large-context multimodal reasoning lane",
    ),
    ModelSlot(
        ProviderType.OPENROUTER,
        "meta-llama/llama-3.3-70b-instruct",
        "Llama 3.3 70B",
        ModelTier.STRONG,
        ("code", "reasoning"),
        128_000,
        "Sub-floor (Llama 3.3 70B) — grunt work only",
        below_floor=True,
    ),
    # ── Fast tier (dedicated inference) ────────────────────────────────
    ModelSlot(
        ProviderType.NVIDIA_NIM,
        "meta/llama-3.3-70b-instruct",
        "Llama 3.3 70B (NIM)",
        ModelTier.FAST,
        ("code", "speed"),
        128_000,
        "Sub-floor (Llama 3.3 70B NIM) — grunt work only",
        below_floor=True,
    ),
    # REMOVED 2026-06-18: nvidia/llama-3.1-nemotron-ultra-253b-v1 returned
    # HTTP 404 "Function not found for account" on a live receipt-grade probe
    # with this account's NVIDIA key — the function is not provisioned for our
    # account, so it is not a real route. The working Nemotron weights this
    # account CAN serve are added as live floor/grunt routes below
    # (nemotron-3-ultra-550b, nemotron-3-super-120b, nemotron-super-49b,
    # nemotron-nano-9b). Keeping the 253b slot let the key-oracle advertise a
    # dead route as routable until a contradicting receipt landed.
    ModelSlot(
        ProviderType.OPENROUTER,
        "deepseek/deepseek-r1",
        "DeepSeek R1",
        ModelTier.STRONG,
        ("reasoning", "code"),
        64_000,
        "Sub-floor (DeepSeek R1) — grunt work only",
        below_floor=True,
    ),
    ModelSlot(
        ProviderType.OLLAMA,
        "kimi-k2.5:cloud",
        "Kimi K2.5 (Ollama Cloud)",
        ModelTier.STRONG,
        ("reasoning", "long_context", "synthesis"),
        128_000,
        "Sub-floor (K2.5, superseded by K2.6 floor) — grunt work only",
        below_floor=True,
    ),
    ModelSlot(
        ProviderType.OLLAMA,
        "glm-5:cloud",
        "GLM 5 (Ollama Cloud)",
        ModelTier.STRONG,
        ("reasoning", "synthesis", "multilingual"),
        128_000,
        "Sub-floor (GLM-5, superseded by GLM-5.1 floor) — grunt work only",
        below_floor=True,
    ),
    # K2.6 is the operator's floor model. Same weights served by Ollama Cloud
    # (keyless cloud route) and OpenRouter (aggregator) — ONE logical model in
    # the pool, best-route-first puts Ollama ahead of the flappy OpenRouter id
    # that caused the kimi flapping bug the consolidation goal names.
    ModelSlot(
        ProviderType.OLLAMA,
        "kimi-k2.6:cloud",
        "Kimi K2.6 (Ollama Cloud)",
        ModelTier.STRONG,
        ("reasoning", "long_context", "synthesis"),
        256_000,
        "Floor model — long-context semantic lane via Ollama Cloud",
    ),
    ModelSlot(
        ProviderType.OPENROUTER,
        "moonshotai/kimi-k2.6",
        "Kimi K2.6",
        ModelTier.STRONG,
        ("reasoning", "long_context", "synthesis"),
        256_000,
        "Floor model via OpenRouter (deprioritised aggregator route)",
    ),
    ModelSlot(
        ProviderType.NVIDIA_NIM,
        "moonshotai/kimi-k2.6",
        "Kimi K2.6 (NIM)",
        ModelTier.STRONG,
        ("reasoning", "long_context", "synthesis"),
        256_000,
        "Floor model via NVIDIA NIM hosted catalog (paced secondary route)",
    ),
    # ── NEW floor frontier (>= K2.6) — Ollama-Cloud lanes, keyless ─────
    # The K2.6 floor the roster must SERVE. Live providers first: each rides
    # the Ollama-Cloud keyless route ahead of any paid aggregator.
    ModelSlot(
        ProviderType.OLLAMA,
        "kimi-k2.7-code:cloud",
        "Kimi K2.7 Code (Ollama Cloud)",
        ModelTier.STRONG,
        ("reasoning", "long_context", "code", "synthesis"),
        256_000,
        "Floor — next K2 generation, long-context coder lane via Ollama Cloud",
    ),
    ModelSlot(
        ProviderType.OLLAMA,
        "deepseek-v4-pro:cloud",
        "DeepSeek V4 Pro (Ollama Cloud)",
        ModelTier.STRONG,
        ("code", "reasoning", "chinese"),
        256_000,
        "Floor — DeepSeek V4 Pro bulk-build lane via Ollama Cloud",
    ),
    ModelSlot(
        ProviderType.NVIDIA_NIM,
        "deepseek-ai/deepseek-v4-pro",
        "DeepSeek V4 Pro (NIM)",
        ModelTier.STRONG,
        ("code", "reasoning", "chinese"),
        256_000,
        "Floor — DeepSeek V4 Pro on NVIDIA NIM (live receipt 2026-06-18). "
        "Fixes the bogus 3-part id deepseek-ai/deepseek-v4-pro/flash (HTTP 404).",
    ),
    ModelSlot(
        ProviderType.SAMBANOVA,
        "DeepSeek-V4-Pro",
        "DeepSeek V4 Pro (SambaNova)",
        ModelTier.STRONG,
        ("code", "reasoning", "chinese"),
        256_000,
        "Floor — DeepSeek V4 Pro on SambaNova (secondary route)",
    ),
    ModelSlot(
        ProviderType.FIREWORKS,
        "accounts/fireworks/models/deepseek-v4-pro",
        "DeepSeek V4 Pro (Fireworks)",
        ModelTier.STRONG,
        ("code", "reasoning", "chinese"),
        256_000,
        "Floor — DeepSeek V4 Pro on Fireworks (secondary route)",
    ),
    ModelSlot(
        ProviderType.OLLAMA,
        "glm-5.1:cloud",
        "GLM 5.1 (Ollama Cloud)",
        ModelTier.STRONG,
        ("reasoning", "synthesis", "multilingual"),
        256_000,
        "Floor — GLM-5.1 reasoning lane via Ollama Cloud (GLM-zai live)",
    ),
    ModelSlot(
        ProviderType.NVIDIA_NIM,
        "z-ai/glm-5.1",
        "GLM 5.1 (NIM)",
        ModelTier.STRONG,
        ("reasoning", "synthesis", "multilingual"),
        256_000,
        "Floor — GLM-5.1 on NVIDIA NIM (live receipt 2026-06-18, secondary route)",
    ),
    ModelSlot(
        ProviderType.OLLAMA,
        "minimax-m3:cloud",
        "MiniMax M3 (Ollama Cloud)",
        ModelTier.STRONG,
        ("reasoning", "synthesis"),
        256_000,
        "Floor — MiniMax M3 challenger lane via Ollama Cloud",
    ),
    ModelSlot(
        ProviderType.NVIDIA_NIM,
        "minimaxai/minimax-m3",
        "MiniMax M3 (NIM)",
        ModelTier.STRONG,
        ("reasoning", "synthesis"),
        256_000,
        "Floor — MiniMax M3 on NVIDIA NIM (secondary route)",
    ),
    # ══════════════════════════════════════════════════════════════════
    # NVIDIA NIM bleeding-edge + NVIDIA-native lanes (live receipts
    # 2026-06-18 against integrate.api.nvidia.com with this account's key).
    # Operator directive: a WIDE, diverse selection of the bleeding edge and
    # the models UNIQUE to NVIDIA's system (the Nemotron-3 family). Each id
    # below returned HTTP 200 on a paced pong probe; ids that 404'd for this
    # account (nemotron-ultra-253b, deepseek-v4-pro/flash, codestral-22b,
    # gemma-3-12b) are deliberately NOT added.
    # ══════════════════════════════════════════════════════════════════
    ModelSlot(
        ProviderType.NVIDIA_NIM,
        "deepseek-ai/deepseek-v4-flash",
        "DeepSeek V4 Flash (NIM)",
        ModelTier.FAST,
        ("code", "reasoning", "speed", "chinese"),
        256_000,
        "Floor — DeepSeek V4 Flash fast frontier lane on NVIDIA NIM (live)",
    ),
    ModelSlot(
        ProviderType.NVIDIA_NIM,
        "qwen/qwen3.5-397b-a17b",
        "Qwen3.5 397B (NIM)",
        ModelTier.FRONTIER,
        ("reasoning", "code", "chinese", "synthesis"),
        256_000,
        "Floor — Qwen3.5 397B MoE flagship on NVIDIA NIM (live, bleeding edge)",
    ),
    ModelSlot(
        ProviderType.NVIDIA_NIM,
        "qwen/qwen3-next-80b-a3b-instruct",
        "Qwen3-Next 80B-A3B (NIM)",
        ModelTier.FAST,
        ("reasoning", "code", "speed"),
        256_000,
        "Floor — Qwen3-Next 80B (3B active MoE) fast lane on NVIDIA NIM (live)",
    ),
    ModelSlot(
        ProviderType.NVIDIA_NIM,
        "openai/gpt-oss-120b",
        "GPT-OSS 120B (NIM)",
        ModelTier.STRONG,
        ("reasoning", "code", "synthesis"),
        128_000,
        "Floor — GPT-OSS 120B open-weight on NVIDIA NIM (live)",
    ),
    ModelSlot(
        ProviderType.NVIDIA_NIM,
        "nvidia/nemotron-3-ultra-550b-a55b",
        "Nemotron-3 Ultra 550B (NIM)",
        ModelTier.FRONTIER,
        ("reasoning", "synthesis", "architecture"),
        128_000,
        "Floor — NVIDIA Nemotron-3 Ultra 550B MoE, NVIDIA-native frontier (live)",
    ),
    ModelSlot(
        ProviderType.NVIDIA_NIM,
        "nvidia/nemotron-3-super-120b-a12b",
        "Nemotron-3 Super 120B (NIM)",
        ModelTier.STRONG,
        ("reasoning", "synthesis", "code"),
        128_000,
        "Floor — NVIDIA Nemotron-3 Super 120B MoE, NVIDIA-native (live)",
    ),
    ModelSlot(
        ProviderType.NVIDIA_NIM,
        "mistralai/mistral-large-3-675b-instruct-2512",
        "Mistral Large 3 675B (NIM)",
        ModelTier.FRONTIER,
        ("reasoning", "code", "multilingual"),
        128_000,
        "Floor — Mistral Large 3 675B on NVIDIA NIM (live, bleeding edge)",
    ),
    ModelSlot(
        ProviderType.NVIDIA_NIM,
        "mistralai/mistral-medium-3.5-128b",
        "Mistral Medium 3.5 128B (NIM)",
        ModelTier.STRONG,
        ("reasoning", "code", "multilingual"),
        128_000,
        "Floor — Mistral Medium 3.5 128B on NVIDIA NIM (live)",
    ),
    ModelSlot(
        ProviderType.NVIDIA_NIM,
        "meta/llama-4-maverick-17b-128e-instruct",
        "Llama 4 Maverick (NIM)",
        ModelTier.STRONG,
        ("reasoning", "code", "multimodal"),
        1_000_000,
        "Floor — Llama 4 Maverick 128-expert MoE on NVIDIA NIM (live)",
    ),
    # ── NVIDIA NIM sub-floor (smaller/faster) — grunt work only ────────
    ModelSlot(
        ProviderType.NVIDIA_NIM,
        "openai/gpt-oss-20b",
        "GPT-OSS 20B (NIM)",
        ModelTier.FAST,
        ("code", "speed"),
        128_000,
        "Sub-floor (GPT-OSS 20B) — fast grunt lane on NVIDIA NIM (live)",
        below_floor=True,
    ),
    ModelSlot(
        ProviderType.NVIDIA_NIM,
        "nvidia/llama-3.3-nemotron-super-49b-v1.5",
        "Nemotron Super 49B (NIM)",
        ModelTier.STRONG,
        ("reasoning", "code"),
        128_000,
        "Sub-floor (Nemotron Super 49B) — NVIDIA-native grunt lane (live)",
        below_floor=True,
    ),
    ModelSlot(
        ProviderType.NVIDIA_NIM,
        "nvidia/nvidia-nemotron-nano-9b-v2",
        "Nemotron Nano 9B (NIM)",
        ModelTier.FAST,
        ("speed", "code"),
        128_000,
        "Sub-floor (Nemotron Nano 9B) — fast NVIDIA-native grunt lane (live)",
        below_floor=True,
    ),
    ModelSlot(
        ProviderType.OLLAMA,
        "qwen3-coder:480b-cloud",
        "Qwen3 Coder 480B (Ollama Cloud)",
        ModelTier.STRONG,
        ("code", "reasoning"),
        256_000,
        "Floor — high-capacity coder lane via Ollama Cloud",
    ),
    # ── BELOW FLOOR — superseded Ollama-cloud lanes. Grunt work only. ──
    ModelSlot(
        ProviderType.OLLAMA,
        "deepseek-v3.2:cloud",
        "DeepSeek V3.2 (Ollama Cloud)",
        ModelTier.STRONG,
        ("code", "reasoning", "chinese"),
        128_000,
        "Sub-floor (DeepSeek V3.2, superseded by V4 Pro) — grunt work only",
        below_floor=True,
    ),
    ModelSlot(
        ProviderType.OLLAMA,
        "minimax-m2.7:cloud",
        "MiniMax M2.7 (Ollama Cloud)",
        ModelTier.STRONG,
        ("reasoning", "synthesis"),
        128_000,
        "Sub-floor (MiniMax M2.7, superseded by M3) — grunt work only",
        below_floor=True,
    ),
    # ── Free tier (OpenRouter free) ────────────────────────────────────
    # All free-tier router lanes are BELOW FLOOR — grunt work only.
    ModelSlot(
        ProviderType.OPENROUTER_FREE,
        "meta-llama/llama-3.3-70b-instruct:free",
        "Llama 3.3 70B (free)",
        ModelTier.FREE,
        ("code",),
        128_000,
        "Sub-floor (Llama 3.3 70B free) — grunt work only",
        below_floor=True,
    ),
    ModelSlot(
        ProviderType.OPENROUTER_FREE,
        "google/gemma-3-27b-it:free",
        "Gemma 3 27B (free)",
        ModelTier.FREE,
        ("speed",),
        8_192,
        "Sub-floor (Gemma 3) — grunt work only",
        below_floor=True,
    ),
    ModelSlot(
        ProviderType.OPENROUTER_FREE,
        "mistralai/mistral-small-3.1-24b-instruct:free",
        "Mistral Small 3.1 (free)",
        ModelTier.FREE,
        ("code", "speed"),
        32_768,
        "Sub-floor (Mistral Small 3.1) — grunt work only",
        below_floor=True,
    ),
    # ── Local tier (Ollama) — genuine LOCAL weights, all BELOW FLOOR ───
    ModelSlot(
        ProviderType.OLLAMA,
        "qwen2.5-coder:14b",
        "Qwen 2.5 Coder 14B (local)",
        ModelTier.LOCAL,
        ("code", "speed"),
        32_768,
        "Sub-floor LOCAL — zero cost, grunt work only",
        below_floor=True,
    ),
    ModelSlot(
        ProviderType.OLLAMA,
        "deepseek-coder-v2:16b",
        "DeepSeek Coder V2 16B (local)",
        ModelTier.LOCAL,
        ("code",),
        16_384,
        "Sub-floor LOCAL — grunt work only",
        below_floor=True,
    ),
    ModelSlot(
        ProviderType.OLLAMA,
        "llama3.2",
        "Llama 3.2 (local)",
        ModelTier.LOCAL,
        ("speed",),
        128_000,
        "Sub-floor LOCAL — grunt work only",
        below_floor=True,
    ),
)


# ---------------------------------------------------------------------------
# Provider availability checking
# ---------------------------------------------------------------------------

_ENV_KEYS_FOR_PROVIDER: dict[ProviderType, str] = {
    provider: PROVIDER_API_KEY_ENV_KEYS[provider.value]
    for provider in (
        ProviderType.ANTHROPIC,
        ProviderType.OPENAI,
        ProviderType.OPENROUTER,
        ProviderType.OPENROUTER_FREE,
        ProviderType.NVIDIA_NIM,
        ProviderType.GROQ,
        ProviderType.SILICONFLOW,
        ProviderType.TOGETHER,
        ProviderType.FIREWORKS,
        # SambaNova is a keyed secondary route (DeepSeek-V4-Pro floor fan-out),
        # not a subscription lane — gate it on its API key, not keyless.
        ProviderType.SAMBANOVA,
    )
}


def _provider_has_key(provider: ProviderType) -> bool:
    """Check if the env var for a provider is set (non-empty)."""
    env_key = _ENV_KEYS_FOR_PROVIDER.get(provider)
    if env_key is None:
        # Ollama, Claude Code, Codex don't need API keys
        return True
    return bool(os.environ.get(env_key, "").strip())


def _ollama_reachable() -> bool:
    """Quick synchronous check if Ollama is responding."""
    base = resolve_ollama_base_url()
    headers = build_ollama_headers(base_url=base)
    try:
        resp = httpx.get(f"{base.rstrip('/')}/api/tags", headers=headers, timeout=2.0)
        return resp.status_code == 200
    except Exception:
        return False


_ollama_status: bool | None = None  # cached per process


def _is_ollama_available() -> bool:
    global _ollama_status
    if _ollama_status is None:
        _ollama_status = _ollama_reachable()
        if _ollama_status:
            if ollama_transport_mode() == "cloud_api":
                logger.info("Ollama Cloud detected — cloud models available")
            else:
                logger.info("Ollama detected — local models available")
        else:
            logger.debug("Ollama not reachable — skipping local models")
    return _ollama_status


def reset_ollama_cache() -> None:
    """Force re-check of Ollama availability (e.g. after user starts it)."""
    global _ollama_status
    _ollama_status = None


# ---------------------------------------------------------------------------
# Available roster (filtered by what's actually reachable)
# ---------------------------------------------------------------------------


# Direct providers that should suppress OpenRouter duplicates of the same model.
_DIRECT_PROVIDERS = {ProviderType.ANTHROPIC, ProviderType.OPENAI}


def get_available_roster(
    roster: tuple[ModelSlot, ...] | None = None,
) -> list[ModelSlot]:
    """Filter the roster to models whose provider is currently available.

    When the same model is available both directly (e.g. Anthropic) and
    via OpenRouter, prefer the direct route and skip the OpenRouter
    duplicate.  Models at different tiers (free vs paid) or on different
    infra (NIM vs OpenRouter) are NOT deduped.
    """
    roster = roster or EVOLUTION_ROSTER
    available: list[ModelSlot] = []
    # Track model IDs we've already added via a direct provider
    direct_model_ids: set[str] = set()
    ollama_checked = False
    ollama_ok = False

    for slot in roster:
        if slot.provider == ProviderType.OLLAMA:
            if not ollama_checked:
                ollama_ok = _is_ollama_available()
                ollama_checked = True
            if not ollama_ok:
                continue
        elif not _provider_has_key(slot.provider):
            continue

        # Dedup: skip OpenRouter slots that mirror a direct provider model
        if slot.provider in (ProviderType.OPENROUTER, ProviderType.OPENROUTER_FREE):
            # e.g. "anthropic/claude-opus-4" → "claude-opus-4"
            base_id = slot.model_id.split("/")[-1].removesuffix(":free")
            if base_id in direct_model_ids:
                continue
        elif slot.provider in _DIRECT_PROVIDERS:
            # Normalize: strip date suffix (e.g. -20250514) for cross-provider dedup
            normalized = re.sub(r"-\d{8}$", "", slot.model_id)
            direct_model_ids.add(normalized)

        available.append(slot)

    return available


# ---------------------------------------------------------------------------
# Strategy-aware model selection
# ---------------------------------------------------------------------------


# How many models to select per strategy
_STRATEGY_PROFILES: dict[str, dict[str, Any]] = {
    "exploit": {
        # Polish winners — use the best models
        "tier_weights": {
            ModelTier.FRONTIER: 0.50,
            ModelTier.STRONG: 0.35,
            ModelTier.FAST: 0.10,
            ModelTier.FREE: 0.03,
            ModelTier.LOCAL: 0.02,
        },
        "strength_bonus": "reasoning",
    },
    "explore": {
        # Maximise diversity — spread across tiers and models
        "tier_weights": {
            ModelTier.FRONTIER: 0.15,
            ModelTier.STRONG: 0.35,
            ModelTier.FAST: 0.15,
            ModelTier.FREE: 0.20,
            ModelTier.LOCAL: 0.15,
        },
        "strength_bonus": "code",
    },
    "restart": {
        # Escape local optima — cheap and fast, many attempts
        "tier_weights": {
            ModelTier.FRONTIER: 0.05,
            ModelTier.STRONG: 0.15,
            ModelTier.FAST: 0.25,
            ModelTier.FREE: 0.40,
            ModelTier.LOCAL: 0.15,
        },
        "strength_bonus": "speed",
    },
    "backtrack": {
        # Careful analysis — strong reasoning models
        "tier_weights": {
            ModelTier.FRONTIER: 0.40,
            ModelTier.STRONG: 0.40,
            ModelTier.FAST: 0.10,
            ModelTier.FREE: 0.05,
            ModelTier.LOCAL: 0.05,
        },
        "strength_bonus": "reasoning",
    },
}


def select_models_for_cycle(
    n: int,
    strategy: str = "explore",
    roster: tuple[ModelSlot, ...] | None = None,
    *,
    ensure_diversity: bool = True,
) -> list[ModelSlot]:
    """Select *n* models for an evolution cycle, weighted by strategy.

    Args:
        n: Number of model slots to return (one per source file).
        strategy: The current adaptive strategy from DarwinEngine.
        roster: Override the default roster (for testing).
        ensure_diversity: If True, avoid picking the same model twice
            (when possible).

    Returns:
        A list of *n* ModelSlots, possibly with duplicates if the
        available roster is smaller than *n*.
    """
    available = get_available_roster(roster)
    if not available:
        logger.warning("No models available in roster — falling back to OpenRouter default")
        return [
            ModelSlot(
                ProviderType.OPENROUTER,
                "meta-llama/llama-3.3-70b-instruct",
                "Llama 3.3 70B (fallback)",
                ModelTier.STRONG,
                ("code",),
            )
        ] * n

    profile = _STRATEGY_PROFILES.get(strategy, _STRATEGY_PROFILES["explore"])
    tier_weights: dict[ModelTier, float] = profile["tier_weights"]
    strength_bonus: str = profile["strength_bonus"]

    # Build weighted probability for each available slot
    weights: list[float] = []
    for slot in available:
        w = tier_weights.get(slot.tier, 0.1)
        if strength_bonus in slot.strengths:
            w *= 1.5
        weights.append(w)

    # Normalize
    total = sum(weights)
    if total <= 0:
        weights = [1.0] * len(available)
        total = float(len(available))
    probs = [w / total for w in weights]

    selected: list[ModelSlot] = []
    used_indices: set[int] = set()

    for _ in range(n):
        if ensure_diversity and len(used_indices) < len(available):
            # Zero out already-used slots for this draw
            adj_probs = [
                p if i not in used_indices else 0.0
                for i, p in enumerate(probs)
            ]
            adj_total = sum(adj_probs)
            if adj_total > 0:
                adj_probs = [p / adj_total for p in adj_probs]
            else:
                # All used up — allow repeats
                adj_probs = probs
        else:
            adj_probs = probs

        idx = random.choices(range(len(available)), weights=adj_probs, k=1)[0]
        selected.append(available[idx])
        used_indices.add(idx)

    return selected


def roster_summary(roster: tuple[ModelSlot, ...] | None = None) -> str:
    """Human-readable summary of available models."""
    available = get_available_roster(roster)
    if not available:
        return "No models available"

    lines = ["Available evolution models:"]
    by_tier: dict[ModelTier, list[ModelSlot]] = {}
    for slot in available:
        by_tier.setdefault(slot.tier, []).append(slot)

    for tier in ModelTier:
        slots = by_tier.get(tier, [])
        if not slots:
            continue
        lines.append(f"\n  {tier.value.upper()} ({len(slots)}):")
        for s in slots:
            strengths = ", ".join(s.strengths) if s.strengths else "general"
            lines.append(f"    {s.display_name:<35s} [{strengths}]")

    return "\n".join(lines)
