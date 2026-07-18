"""Canonical provider hierarchy and model defaults."""

from __future__ import annotations

from enum import Enum
import logging
import re
from typing import TYPE_CHECKING, Mapping

from dharma_swarm.models import LLMResponse, ProviderType
from dharma_swarm.model_defaults import default_for_provider

# Re-export the roster/pool power-floor line for provider-grain callers.
__all_floor__ = ("MODEL_POWER_FLOOR",)

if TYPE_CHECKING:
    from dharma_swarm.resilience import CircuitBreakerRegistry
    from dharma_swarm.routing_memory import RoutingMemoryStore

logger = logging.getLogger(__name__)


def _ordered_unique(values: tuple[ProviderType, ...]) -> tuple[ProviderType, ...]:
    seen: set[ProviderType] = set()
    out: list[ProviderType] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        out.append(value)
    return tuple(out)


class LaneRole(str, Enum):
    PRIMARY_DRIVER = "primary_driver"
    RESEARCH_DELEGATE = "research_delegate"
    CHALLENGER = "challenger"
    BULK_BUILDER = "bulk_builder"
    VALIDATOR = "validator"
    GENERAL_SUPPORT = "general_support"


# Tier order is the Day-1 seed; EWMA scores refine after enough routing events.
# Defaults stay power-first. Small models are explicit local/fast-path fallbacks,
# never lane defaults.
TIER_FREE: tuple[ProviderType, ...] = (
    ProviderType.OLLAMA,         # GLM-5 744B, DeepSeek-v3.2, Kimi-K2.5 (cloud)
    ProviderType.GROQ,           # Kimi K2 1T (fast inference)
    ProviderType.CEREBRAS,       # Qwen3 235B / GPT-OSS 120B (3000 tok/s)
    ProviderType.SAMBANOVA,      # DeepSeek V3 671B
    ProviderType.SILICONFLOW,    # Qwen3-Coder 480B
    ProviderType.TOGETHER,       # Qwen3-Coder 480B
    ProviderType.FIREWORKS,      # Qwen3-Coder 480B
    ProviderType.NVIDIA_NIM,     # Nemotron Ultra 253B (50 req/day — quota-poor, so late)
)

TIER_CHEAP: tuple[ProviderType, ...] = (
    ProviderType.KIMI_CODE,      # Kimi Code membership API (K3)
    ProviderType.MOONSHOT,       # Kimi Open Platform / Moonshot global API
    ProviderType.ZHIPU,          # glm-5.2 direct (z.ai/Zhipu first-party lane)
    ProviderType.GOOGLE_AI,      # gemini-2.5-pro (free tier, 1M ctx)
    ProviderType.CHUTES,         # DeepSeek-R1 (community)
    ProviderType.MISTRAL,        # mistral-large (1B tok/mo free tier)
    ProviderType.OPENROUTER_FREE,  # Nemotron 120B, GLM-4.5-Air, etc.
)

TIER_SUBSCRIPTION: tuple[ProviderType, ...] = (
    ProviderType.CLAUDE_CODE,    # Claude Max/Pro subscription (unlimited, via `claude -p`)
    ProviderType.CODEX,          # OpenAI subscription (via `codex exec`)
)

TIER_PAID_API: tuple[ProviderType, ...] = (
    ProviderType.ANTHROPIC,      # Opus 4.6 API (credit-limited — last resort)
    ProviderType.OPENAI,         # GPT-5 API (credit-limited — last resort)
    ProviderType.OPENROUTER,     # Paid OR models (credit-limited)
)

# Legacy alias
TIER_PAID: tuple[ProviderType, ...] = TIER_SUBSCRIPTION + TIER_PAID_API

ALL_TIERS: dict[str, tuple[ProviderType, ...]] = {
    "free": TIER_FREE,
    "cheap": TIER_CHEAP,
    "subscription": TIER_SUBSCRIPTION,
    "paid_api": TIER_PAID_API,
    "paid": TIER_PAID,
}

# Canonical provider registry. ProviderPolicyRouter applies power-first
# reranking; this seed is the historical fallback and EWMA starting point.
CANONICAL_SEED_ORDER: tuple[ProviderType, ...] = (
    TIER_FREE + TIER_CHEAP + TIER_SUBSCRIPTION + TIER_PAID_API
)


PRIMARY_DRIVER_LANES: tuple[ProviderType, ...] = (
    ProviderType.CLAUDE_CODE,    # Subscription-backed (unlimited)
    ProviderType.CODEX,          # Subscription-backed (unlimited)
    ProviderType.OLLAMA,         # Free frontier (GLM-5, DeepSeek-v3.2)
    ProviderType.ANTHROPIC,      # API credits (last resort)
)

DELEGATED_RESEARCH_PRIORITY: tuple[ProviderType, ...] = (
    ProviderType.KIMI_CODE,      # Kimi Code direct API
    ProviderType.MOONSHOT,       # Kimi Open Platform direct API
    ProviderType.OPENROUTER,     # Kimi / GLM / Qwen router
    ProviderType.OLLAMA,         # GLM-5 / Kimi cloud
    ProviderType.NVIDIA_NIM,     # MiniMax / Nemotron frontier support
    ProviderType.OPENROUTER_FREE,
    ProviderType.SILICONFLOW,
    ProviderType.TOGETHER,
    ProviderType.FIREWORKS,
    ProviderType.GROQ,
    ProviderType.CEREBRAS,
    ProviderType.GOOGLE_AI,
    ProviderType.MISTRAL,
    ProviderType.CHUTES,
    ProviderType.SAMBANOVA,
)

CHALLENGER_PRIORITY: tuple[ProviderType, ...] = (
    ProviderType.KIMI_CODE,
    ProviderType.MOONSHOT,
    ProviderType.NVIDIA_NIM,
    ProviderType.OPENROUTER,
    ProviderType.OLLAMA,
    ProviderType.OPENROUTER_FREE,
    ProviderType.OPENAI,
)

DELEGATED_BUILDER_PRIORITY: tuple[ProviderType, ...] = (
    ProviderType.KIMI_CODE,
    ProviderType.MOONSHOT,
    ProviderType.OPENROUTER,
    ProviderType.OPENROUTER_FREE,
    ProviderType.OLLAMA,
    ProviderType.SILICONFLOW,
    ProviderType.TOGETHER,
    ProviderType.FIREWORKS,
    ProviderType.GROQ,
    ProviderType.GOOGLE_AI,
    ProviderType.MISTRAL,
    ProviderType.CHUTES,
    ProviderType.CEREBRAS,
    ProviderType.SAMBANOVA,
)

VALIDATOR_PRIORITY: tuple[ProviderType, ...] = (
    ProviderType.NVIDIA_NIM,
    ProviderType.OPENROUTER,
    ProviderType.GROQ,
    ProviderType.OLLAMA,
    ProviderType.OPENAI,
    ProviderType.ANTHROPIC,
    ProviderType.CODEX,
)

PRIMARY_TOOLING_PRIORITY: tuple[ProviderType, ...] = (
    ProviderType.CLAUDE_CODE,    # Subscription (unlimited)
    ProviderType.CODEX,          # Subscription (unlimited)
    ProviderType.OLLAMA,         # Free frontier
    ProviderType.CEREBRAS,       # Free (Qwen3 235B)
    ProviderType.ANTHROPIC,      # API credits (last resort)
    ProviderType.OPENAI,         # API credits (last resort)
    ProviderType.OPENROUTER,     # API credits (last resort)
)

PRIMARY_REASONING_PRIORITY: tuple[ProviderType, ...] = (
    ProviderType.CLAUDE_CODE,    # Subscription (unlimited, Opus-class)
    ProviderType.OLLAMA,         # Free frontier (GLM-5 744B, DeepSeek-v3.2)
    ProviderType.CODEX,          # Subscription (unlimited)
    ProviderType.CEREBRAS,       # Free (Qwen3 235B)
    ProviderType.ANTHROPIC,      # API credits (last resort)
    ProviderType.OPENAI,         # API credits (last resort)
    ProviderType.OPENROUTER,     # API credits (last resort)
)

DELIBERATIVE_REASONING_PRIORITY: tuple[ProviderType, ...] = _ordered_unique(
    DELEGATED_RESEARCH_PRIORITY + PRIMARY_REASONING_PRIORITY + CHALLENGER_PRIORITY
)

DELIBERATIVE_EXECUTION_PRIORITY: tuple[ProviderType, ...] = _ordered_unique(
    DELEGATED_BUILDER_PRIORITY
    + DELEGATED_RESEARCH_PRIORITY
    + PRIMARY_TOOLING_PRIORITY
    + TIER_CHEAP
    + TIER_FREE
    + TIER_PAID
)

ESCALATION_PRIORITY: tuple[ProviderType, ...] = _ordered_unique(
    PRIMARY_REASONING_PRIORITY
    + CHALLENGER_PRIORITY
    + DELEGATED_RESEARCH_PRIORITY
    + TIER_PAID
    + TIER_CHEAP
    + TIER_FREE
)


_LANE_ROLES: dict[ProviderType, LaneRole] = {
    ProviderType.CODEX: LaneRole.PRIMARY_DRIVER,
    ProviderType.CLAUDE_CODE: LaneRole.PRIMARY_DRIVER,
    ProviderType.ANTHROPIC: LaneRole.PRIMARY_DRIVER,
    ProviderType.OPENROUTER: LaneRole.RESEARCH_DELEGATE,
    ProviderType.KIMI_CODE: LaneRole.RESEARCH_DELEGATE,
    ProviderType.MOONSHOT: LaneRole.RESEARCH_DELEGATE,
    ProviderType.OLLAMA: LaneRole.RESEARCH_DELEGATE,
    ProviderType.OPENROUTER_FREE: LaneRole.RESEARCH_DELEGATE,
    ProviderType.NVIDIA_NIM: LaneRole.CHALLENGER,
    ProviderType.SILICONFLOW: LaneRole.BULK_BUILDER,
    ProviderType.TOGETHER: LaneRole.BULK_BUILDER,
    ProviderType.FIREWORKS: LaneRole.BULK_BUILDER,
    ProviderType.GROQ: LaneRole.VALIDATOR,
    ProviderType.CEREBRAS: LaneRole.BULK_BUILDER,
    ProviderType.GOOGLE_AI: LaneRole.GENERAL_SUPPORT,
    ProviderType.MISTRAL: LaneRole.GENERAL_SUPPORT,
    ProviderType.CHUTES: LaneRole.GENERAL_SUPPORT,
    ProviderType.SAMBANOVA: LaneRole.GENERAL_SUPPORT,
    ProviderType.OPENAI: LaneRole.GENERAL_SUPPORT,
}


def provider_lane_role(provider: ProviderType) -> LaneRole:
    """Return the canonical operating role for a provider lane."""
    return _LANE_ROLES.get(provider, LaneRole.GENERAL_SUPPORT)


# ─── Default Models ──────────────────────────────────────────────────────
# Default model per provider (used when request.model is empty).
#
# STEP 3 of the model-pool consolidation: the per-provider default STRINGS now
# live in exactly ONE place — ``model_pool._PROVIDER_DEFAULTS`` — and this dict
# is a thin PROJECTION of the pool (``model_pool.default_for_provider``). This
# file keeps the PROVIDER-grain authority (tiers, lane roles, priority tuples);
# only the model-id literals moved to the pool. Every provider in
# ``CANONICAL_SEED_ORDER`` is projected, so the seed-order coverage invariant
# (``test_default_models_dict_matches_all_seed_order``) holds without literals.

# Doctrine: the default per lane is the most powerful model the lane offers
# at $0/near-$0 — see MODEL PREFERENCE DOCTRINE above the tier definitions.
DEFAULT_MODELS: dict[ProviderType, str] = {
    p: default_for_provider(p) for p in CANONICAL_SEED_ORDER
}


def get_tier(provider: ProviderType) -> str:
    """Return the tier name ('free', 'cheap', 'paid') for a provider."""
    for name, members in ALL_TIERS.items():
        if provider in members:
            return name
    return "paid"


def is_free(provider: ProviderType) -> bool:
    """True if provider is in the free tier."""
    return provider in TIER_FREE


def default_model(provider: ProviderType) -> str:
    """Return the default model string for a provider."""
    return DEFAULT_MODELS.get(provider, "")


# ─── Model Intelligence Seed ──────────────────────────────────────────
# Relative capability of each lane's DEFAULT model (0–100, ordinal seed —
# the RANKING matters, not the absolute number). Grounded in public
# benchmark standings of the model classes the lanes serve. This is the
# Day 1 prior only: EWMA scores from routing_memory override it with real
# measured quality after ~100 events. Update this table when a lane's
# DEFAULT_MODELS entry changes — nowhere else.

MODEL_INTELLIGENCE: dict[ProviderType, int] = {
    # Paid / subscription frontier
    ProviderType.ANTHROPIC: 72,        # Opus-class
    ProviderType.OPENAI: 71,           # GPT-5
    ProviderType.CLAUDE_CODE: 70,      # Opus-class via subscription
    ProviderType.CODEX: 70,            # GPT-5-class via subscription
    # Free / cheap frontier
    ProviderType.OLLAMA: 68,           # GLM-5 744B (cloud)
    ProviderType.KIMI_CODE: 72,        # Kimi K3 coding membership lane
    ProviderType.MOONSHOT: 71,         # Kimi K3 global API
    ProviderType.ZHIPU: 67,            # glm-5.2 direct (z.ai/Zhipu)
    ProviderType.GOOGLE_AI: 65,        # Gemini 2.5 Pro
    ProviderType.GROQ: 64,             # Kimi K2 1T MoE
    ProviderType.CEREBRAS: 63,         # Qwen3 235B
    ProviderType.SAMBANOVA: 62,        # DeepSeek V3 671B
    ProviderType.CHUTES: 61,           # DeepSeek-R1
    ProviderType.SILICONFLOW: 60,      # Qwen3-Coder 480B
    ProviderType.TOGETHER: 60,         # Qwen3-Coder 480B
    ProviderType.FIREWORKS: 60,        # Qwen3-Coder 480B
    ProviderType.OPENROUTER: 59,       # paid OR default
    ProviderType.NVIDIA_NIM: 58,       # Nemotron Ultra 253B
    ProviderType.MISTRAL: 56,          # Mistral Large
    ProviderType.OPENROUTER_FREE: 55,  # Nemotron 120B
}


def intelligence_score(provider: ProviderType) -> int:
    """Seed intelligence score for a provider's default model (0–100)."""
    return MODEL_INTELLIGENCE.get(provider, 0)


def intelligence_order(
    candidates: tuple[ProviderType, ...] | list[ProviderType] | None = None,
    *,
    respect_cost_tiers: bool = True,
) -> list[ProviderType]:
    """Order providers most-intelligent-first.

    With respect_cost_tiers=True (default), the cost ladder picks the tier
    (free → cheap → subscription → paid API) and intelligence ranks within
    each tier — powerful free frontier before anything paid. With
    respect_cost_tiers=False, raw intelligence wins regardless of cost.
    """
    pool = list(candidates if candidates is not None else CANONICAL_SEED_ORDER)
    if not respect_cost_tiers:
        return sorted(pool, key=lambda p: -intelligence_score(p))
    tier_rank = {"free": 0, "cheap": 1, "subscription": 2, "paid_api": 3, "paid": 3}
    return sorted(
        pool,
        key=lambda p: (tier_rank.get(get_tier(p), 4), -intelligence_score(p)),
    )


# ─── Live Ordering (EWMA + Circuit Breakers) ─────────────────────────────

def get_live_order(
    *,
    routing_memory: RoutingMemoryStore | None = None,
    circuit_breakers: CircuitBreakerRegistry | None = None,
    task_signature: str = "*",
    candidates: tuple[ProviderType, ...] | None = None,
) -> list[ProviderType]:
    """Return provider ordering based on EWMA scores + health.

    If routing_memory has scores, providers are ranked by blended EWMA
    quality (60%), success rate (20%), pheromone (4%), minus penalties
    for latency, token usage, and failure pheromone.

    Providers with open circuit breakers are moved to the end.

    Falls back to intelligence_order() of the candidates (most intelligent
    available model first within the cost ladder) if no EWMA data exists.

    Args:
        routing_memory: EWMA score store. If None, returns seed order.
        circuit_breakers: Health tracker. If None, no filtering.
        task_signature: Routing bucket for EWMA lookup.
        candidates: Override candidate set. Defaults to CANONICAL_SEED_ORDER.

    Returns:
        Ordered list of ProviderType, best first.
    """
    pool = intelligence_order(candidates or CANONICAL_SEED_ORDER)

    # Phase 1: EWMA ranking (if data exists)
    if routing_memory is not None:
        model_hints: Mapping[ProviderType, str | None] = {
            p: DEFAULT_MODELS.get(p, "") for p in pool
        }
        ranked, _ = routing_memory.rank_candidates(
            task_signature=task_signature,
            candidates=pool,
            model_hints=model_hints,
        )
        if ranked:
            pool = ranked

    # Phase 2: Circuit breaker filtering — move unhealthy to end
    if circuit_breakers is not None:
        healthy: list[ProviderType] = []
        unhealthy: list[ProviderType] = []
        for p in pool:
            breaker_key = f"provider:{p.value}"
            breaker = circuit_breakers.get(breaker_key)
            if breaker.state.value == "open":
                unhealthy.append(p)
            else:
                healthy.append(p)
        pool = healthy + unhealthy

    return pool


# ─── Heuristic Quality Scoring ───────────────────────────────────────────

_REFUSAL_PATTERNS = re.compile(
    r"I (?:cannot|can't|am unable|don't|won't)|"
    r"As an AI|"
    r"I'm not able to|"
    r"I apologize.{0,20}(?:cannot|can't)",
    re.IGNORECASE,
)


def heuristic_score(
    response: LLMResponse,
    *,
    expected_code: bool = False,
    expected_json: bool = False,
    latency_ms: float = 0.0,
    max_latency_ms: float = 30_000.0,
) -> float:
    """Score response quality 0.0–1.0 using fast heuristics.

    Signals and weights:
        Completeness (0.30): not empty, no refusals, reasonable length
        Structure    (0.30): code blocks if expected, valid JSON if expected
        Depth        (0.20): content richness (word count, reasoning markers)
        Latency      (0.20): faster = higher (normalized to max_latency_ms)

    Returns:
        Float 0.0–1.0 where higher is better.
    """
    content = (response.content or "").strip()

    # ── Completeness (0.30) ──
    if not content:
        return 0.0  # empty = total failure

    completeness = 0.0
    word_count = len(content.split())

    # Length: 0→0, 10→0.5, 50+→1.0
    length_score = min(word_count / 50.0, 1.0)
    completeness += 0.6 * length_score

    # Refusal detection
    if _REFUSAL_PATTERNS.search(content[:500]):
        completeness *= 0.2  # heavy penalty but not zero (partial answers OK)
    else:
        completeness += 0.4

    # ── Structure (0.30) ──
    structure = 0.5  # default: neutral

    if expected_code:
        has_code = "```" in content or content.count("\n    ") > 2
        structure = 0.9 if has_code else 0.2

    if expected_json:
        try:
            import json as _json
            _json.loads(content)
            structure = 0.95
        except (ValueError, TypeError):
            # Check if JSON is embedded in markdown
            if "```json" in content:
                structure = 0.7
            else:
                structure = 0.15

    # ── Depth (0.20) ──
    depth = 0.5
    reasoning_markers = sum(1 for m in (
        "because", "therefore", "however", "first", "second",
        "step", "note", "important", "consider",
    ) if m in content.lower())
    depth = min(0.3 + reasoning_markers * 0.1, 1.0)

    # ── Latency bonus (0.20) ──
    if latency_ms <= 0 or max_latency_ms <= 0:
        latency_score = 0.5
    else:
        # Lower latency = higher score.  0ms→1.0, max_latency→0.0
        latency_score = max(0.0, 1.0 - (latency_ms / max_latency_ms))

    # ── Weighted blend ──
    score = (
        0.30 * completeness
        + 0.30 * structure
        + 0.20 * depth
        + 0.20 * latency_score
    )
    return round(max(0.0, min(1.0, score)), 4)


# ─── Convenience ─────────────────────────────────────────────────────────

def provider_tier_label(provider: ProviderType) -> str:
    """Human-readable tier label for display."""
    tier = get_tier(provider)
    model = DEFAULT_MODELS.get(provider, "?")
    role = provider_lane_role(provider).value
    return f"[{tier.upper()}|{role}] {provider.value} → {model}"


def dump_hierarchy() -> str:
    """Return a human-readable dump of the full hierarchy for debugging."""
    lines = ["=== Canonical Model Hierarchy ===", ""]
    for tier_name, members in ALL_TIERS.items():
        lines.append(f"── {tier_name.upper()} ──")
        for p in members:
            lines.append(f"  {p.value:20s} → {DEFAULT_MODELS.get(p, '?')}")
        lines.append("")
    return "\n".join(lines)
