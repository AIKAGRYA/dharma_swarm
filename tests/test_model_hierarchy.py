"""Tests for dharma_swarm.model_hierarchy — canonical provider hierarchy.

Validates:
- Tier membership and ordering
- _ordered_unique deduplication
- Lane role assignments
- default_model / get_tier / is_free lookups
- heuristic_score edge cases (empty, refusal, code, JSON, latency)
- get_live_order with seed fallback, EWMA ranking, circuit breaker filtering
- provider_tier_label / dump_hierarchy convenience formatters
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from dharma_swarm.model_hierarchy import (
    ALL_TIERS,
    CANONICAL_SEED_ORDER,
    DEFAULT_MODELS,
    TIER_CHEAP,
    TIER_FREE,
    TIER_PAID,
    TIER_PAID_API,
    TIER_SUBSCRIPTION,
    LaneRole,
    _ordered_unique,
    default_model,
    dump_hierarchy,
    get_live_order,
    get_tier,
    heuristic_score,
    is_free,
    provider_lane_role,
    provider_tier_label,
)
from dharma_swarm.models import LLMResponse, ProviderType


# ---------------------------------------------------------------------------
# Tier definitions
# ---------------------------------------------------------------------------


class TestTierDefinitions:
    def test_free_tier_not_empty(self):
        assert len(TIER_FREE) > 0

    def test_cheap_tier_not_empty(self):
        assert len(TIER_CHEAP) > 0

    def test_subscription_tier_contains_claude_code(self):
        assert ProviderType.CLAUDE_CODE in TIER_SUBSCRIPTION

    def test_paid_api_contains_anthropic(self):
        assert ProviderType.ANTHROPIC in TIER_PAID_API

    def test_paid_is_subscription_plus_api(self):
        assert TIER_PAID == TIER_SUBSCRIPTION + TIER_PAID_API

    def test_canonical_seed_order_covers_all_tiers(self):
        all_providers = set(TIER_FREE) | set(TIER_CHEAP) | set(TIER_SUBSCRIPTION) | set(TIER_PAID_API)
        seed_set = set(CANONICAL_SEED_ORDER)
        assert all_providers == seed_set

    def test_canonical_seed_order_no_duplicates(self):
        assert len(CANONICAL_SEED_ORDER) == len(set(CANONICAL_SEED_ORDER))

    def test_all_tiers_dict_keys(self):
        assert set(ALL_TIERS.keys()) == {"free", "cheap", "subscription", "paid_api", "paid"}


# ---------------------------------------------------------------------------
# _ordered_unique
# ---------------------------------------------------------------------------


class TestOrderedUnique:
    def test_removes_duplicates_preserves_order(self):
        result = _ordered_unique((ProviderType.OLLAMA, ProviderType.GROQ, ProviderType.OLLAMA))
        assert result == (ProviderType.OLLAMA, ProviderType.GROQ)

    def test_empty_input(self):
        assert _ordered_unique(()) == ()

    def test_no_duplicates_unchanged(self):
        result = _ordered_unique((ProviderType.OLLAMA, ProviderType.GROQ))
        assert result == (ProviderType.OLLAMA, ProviderType.GROQ)


# ---------------------------------------------------------------------------
# Lane roles
# ---------------------------------------------------------------------------


class TestLaneRoles:
    def test_codex_is_primary_driver(self):
        assert provider_lane_role(ProviderType.CODEX) == LaneRole.PRIMARY_DRIVER

    def test_openrouter_is_research_delegate(self):
        assert provider_lane_role(ProviderType.OPENROUTER) == LaneRole.RESEARCH_DELEGATE

    def test_nvidia_nim_is_challenger(self):
        assert provider_lane_role(ProviderType.NVIDIA_NIM) == LaneRole.CHALLENGER

    def test_unknown_provider_defaults_to_general_support(self):
        # If a new ProviderType is added but not in _LANE_ROLES, it should default
        for p in ProviderType:
            role = provider_lane_role(p)
            assert isinstance(role, LaneRole)


# ---------------------------------------------------------------------------
# Lookups: get_tier, is_free, default_model
# ---------------------------------------------------------------------------


class TestLookups:
    def test_get_tier_free(self):
        assert get_tier(ProviderType.OLLAMA) == "free"

    def test_get_tier_cheap(self):
        assert get_tier(ProviderType.MISTRAL) == "cheap"

    def test_get_tier_subscription(self):
        assert get_tier(ProviderType.CLAUDE_CODE) == "subscription"

    def test_get_tier_paid_api(self):
        assert get_tier(ProviderType.ANTHROPIC) == "paid_api"

    def test_is_free_true(self):
        assert is_free(ProviderType.OLLAMA) is True

    def test_is_free_false(self):
        assert is_free(ProviderType.ANTHROPIC) is False

    def test_default_model_known_provider(self):
        model = default_model(ProviderType.OLLAMA)
        assert isinstance(model, str)
        assert len(model) > 0

    def test_default_model_every_provider_has_entry(self):
        for p in ProviderType:
            model = default_model(p)
            assert isinstance(model, str)

    def test_default_models_dict_matches_all_seed_order(self):
        for p in CANONICAL_SEED_ORDER:
            assert p in DEFAULT_MODELS, f"{p} missing from DEFAULT_MODELS"


# ---------------------------------------------------------------------------
# heuristic_score
# ---------------------------------------------------------------------------


class TestHeuristicScore:
    def _make_response(self, content: str) -> LLMResponse:
        return LLMResponse(content=content, model="test", provider="test")

    def test_empty_content_returns_zero(self):
        assert heuristic_score(self._make_response("")) == 0.0

    def test_whitespace_only_returns_zero(self):
        assert heuristic_score(self._make_response("   ")) == 0.0

    def test_normal_content_positive_score(self):
        score = heuristic_score(self._make_response(
            "Here is a detailed analysis. First, we consider the architecture. "
            "However, there are trade-offs to note. Therefore we recommend approach B."
        ))
        assert 0.0 < score <= 1.0

    def test_refusal_heavily_penalized(self):
        refusal = heuristic_score(self._make_response(
            "I cannot help with that request. As an AI, I must decline."
        ))
        normal = heuristic_score(self._make_response(
            "Here is the answer to your question with detailed reasoning."
        ))
        assert refusal < normal

    def test_expected_code_with_code_blocks(self):
        score = heuristic_score(
            self._make_response("```python\nprint('hello')\n```\nThis code prints hello."),
            expected_code=True,
        )
        assert score > 0.3

    def test_expected_code_without_code_blocks(self):
        with_code = heuristic_score(
            self._make_response("```python\nprint('hello')\n```\nExplanation follows."),
            expected_code=True,
        )
        without_code = heuristic_score(
            self._make_response("The function prints hello to stdout."),
            expected_code=True,
        )
        assert with_code > without_code

    def test_expected_json_valid(self):
        score = heuristic_score(
            self._make_response('{"key": "value", "count": 42}'),
            expected_json=True,
        )
        assert score > 0.3

    def test_expected_json_invalid(self):
        valid = heuristic_score(
            self._make_response('{"key": "value"}'),
            expected_json=True,
        )
        invalid = heuristic_score(
            self._make_response("This is not JSON at all"),
            expected_json=True,
        )
        assert valid > invalid

    def test_latency_bonus_fast(self):
        fast = heuristic_score(
            self._make_response("Good answer with some depth and reasoning."),
            latency_ms=100.0,
            max_latency_ms=30000.0,
        )
        slow = heuristic_score(
            self._make_response("Good answer with some depth and reasoning."),
            latency_ms=29000.0,
            max_latency_ms=30000.0,
        )
        assert fast > slow

    def test_score_always_in_range(self):
        for content in [
            "x",
            "a " * 1000,
            "I cannot help. As an AI, I apologize.",
            '{"valid": true}',
            "```python\ncode\n```",
        ]:
            score = heuristic_score(self._make_response(content))
            assert 0.0 <= score <= 1.0

    def test_zero_max_latency_neutral(self):
        score = heuristic_score(
            self._make_response("Test content for scoring."),
            latency_ms=100.0,
            max_latency_ms=0.0,
        )
        assert 0.0 <= score <= 1.0


# ---------------------------------------------------------------------------
# get_live_order
# ---------------------------------------------------------------------------


class TestGetLiveOrder:
    def test_seed_order_fallback(self):
        order = get_live_order()
        assert order == list(CANONICAL_SEED_ORDER)

    def test_custom_candidates(self):
        candidates = (ProviderType.OLLAMA, ProviderType.GROQ)
        order = get_live_order(candidates=candidates)
        assert set(order) == set(candidates)

    def test_with_routing_memory_reranks(self):
        mock_memory = MagicMock()
        mock_memory.rank_candidates.return_value = (
            [ProviderType.GROQ, ProviderType.OLLAMA],
            {},
        )
        order = get_live_order(
            routing_memory=mock_memory,
            candidates=(ProviderType.OLLAMA, ProviderType.GROQ),
        )
        assert order[0] == ProviderType.GROQ

    def test_with_routing_memory_empty_ranked_uses_seed(self):
        mock_memory = MagicMock()
        mock_memory.rank_candidates.return_value = ([], {})
        order = get_live_order(routing_memory=mock_memory)
        assert order == list(CANONICAL_SEED_ORDER)

    def test_circuit_breaker_moves_open_to_end(self):
        mock_cb = MagicMock()

        def mock_get(key):
            breaker = MagicMock()
            if key == f"provider:{ProviderType.OLLAMA.value}":
                breaker.state.value = "open"
            else:
                breaker.state.value = "closed"
            return breaker

        mock_cb.get = mock_get
        candidates = (ProviderType.OLLAMA, ProviderType.GROQ, ProviderType.CEREBRAS)
        order = get_live_order(circuit_breakers=mock_cb, candidates=candidates)
        assert order[-1] == ProviderType.OLLAMA
        assert order[0] != ProviderType.OLLAMA


# ---------------------------------------------------------------------------
# Convenience formatters
# ---------------------------------------------------------------------------


class TestConvenience:
    def test_provider_tier_label_format(self):
        label = provider_tier_label(ProviderType.OLLAMA)
        assert "[FREE" in label.upper()
        assert ProviderType.OLLAMA.value in label

    def test_dump_hierarchy_contains_all_tiers(self):
        output = dump_hierarchy()
        for tier_name in ALL_TIERS:
            assert tier_name.upper() in output


class TestModelIntelligence:
    def test_every_default_model_lane_has_score(self):
        from dharma_swarm.model_hierarchy import DEFAULT_MODELS, MODEL_INTELLIGENCE

        for provider in DEFAULT_MODELS:
            assert provider in MODEL_INTELLIGENCE, provider

    def test_tier_free_listed_most_intelligent_first(self):
        from dharma_swarm.model_hierarchy import TIER_FREE, intelligence_score

        scores = [intelligence_score(p) for p in TIER_FREE]
        assert scores == sorted(scores, reverse=True)

    def test_intelligence_order_respects_cost_ladder(self):
        from dharma_swarm.model_hierarchy import intelligence_order

        ordered = intelligence_order(
            [ProviderType.ANTHROPIC, ProviderType.MISTRAL, ProviderType.OLLAMA]
        )
        assert ordered == [
            ProviderType.OLLAMA,     # free frontier first
            ProviderType.MISTRAL,    # cheap second
            ProviderType.ANTHROPIC,  # paid API last
        ]

    def test_intelligence_order_raw_mode_picks_smartest(self):
        from dharma_swarm.model_hierarchy import intelligence_order

        ordered = intelligence_order(
            [ProviderType.OPENROUTER_FREE, ProviderType.OLLAMA, ProviderType.ANTHROPIC],
            respect_cost_tiers=False,
        )
        assert ordered[0] == ProviderType.ANTHROPIC
        assert ordered[1] == ProviderType.OLLAMA

    def test_get_live_order_seed_fallback_is_intelligence_ordered(self):
        from dharma_swarm.model_hierarchy import get_live_order, intelligence_order

        assert get_live_order() == intelligence_order()
