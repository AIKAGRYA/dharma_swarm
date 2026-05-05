"""Tests for dharma_swarm.structured_predicate — deterministic predicates + hash-embed.

Validates:
- StructuredPredicate and CompoundPredicate Pydantic models
- evaluate_predicate for all 8 comparison operators
- evaluate_compound AND/OR modes
- _tokenize text splitting
- _hash_embed determinism and normalization
- cosine_similarity edge cases
- semantic_similarity identical/different/similar texts
- _numeric coercion and error handling
"""

from __future__ import annotations

import math

import pytest

from dharma_swarm.structured_predicate import (
    CompoundPredicate,
    StructuredPredicate,
    _hash_embed,
    _numeric,
    _tokenize,
    cosine_similarity,
    evaluate_compound,
    evaluate_predicate,
    semantic_similarity,
)


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------


class TestModels:
    def test_structured_predicate_frozen(self):
        p = StructuredPredicate(field="x", op="eq", value=1)
        with pytest.raises(Exception):
            p.field = "y"

    def test_compound_predicate_defaults(self):
        c = CompoundPredicate()
        assert c.mode == "all"
        assert c.predicates == []


# ---------------------------------------------------------------------------
# evaluate_predicate — all operators
# ---------------------------------------------------------------------------


class TestEvaluatePredicate:
    def test_eq_match(self):
        p = StructuredPredicate(field="status", op="eq", value="active")
        assert evaluate_predicate(p, {"status": "active"}) is True

    def test_eq_no_match(self):
        p = StructuredPredicate(field="status", op="eq", value="active")
        assert evaluate_predicate(p, {"status": "inactive"}) is False

    def test_lt(self):
        p = StructuredPredicate(field="count", op="lt", value=10)
        assert evaluate_predicate(p, {"count": 5}) is True
        assert evaluate_predicate(p, {"count": 10}) is False
        assert evaluate_predicate(p, {"count": 15}) is False

    def test_gt(self):
        p = StructuredPredicate(field="count", op="gt", value=10)
        assert evaluate_predicate(p, {"count": 15}) is True
        assert evaluate_predicate(p, {"count": 10}) is False

    def test_lte(self):
        p = StructuredPredicate(field="count", op="lte", value=10)
        assert evaluate_predicate(p, {"count": 10}) is True
        assert evaluate_predicate(p, {"count": 5}) is True
        assert evaluate_predicate(p, {"count": 15}) is False

    def test_gte(self):
        p = StructuredPredicate(field="confidence", op="gte", value=0.95)
        assert evaluate_predicate(p, {"confidence": 0.95}) is True
        assert evaluate_predicate(p, {"confidence": 1.0}) is True
        assert evaluate_predicate(p, {"confidence": 0.5}) is False

    def test_contains(self):
        p = StructuredPredicate(field="action_type", op="contains", value="destruct")
        assert evaluate_predicate(p, {"action_type": "destructive"}) is True
        assert evaluate_predicate(p, {"action_type": "constructive"}) is False

    def test_contains_case_insensitive(self):
        p = StructuredPredicate(field="name", op="contains", value="TEST")
        assert evaluate_predicate(p, {"name": "my test case"}) is True

    def test_not_contains(self):
        p = StructuredPredicate(field="action", op="not_contains", value="delete")
        assert evaluate_predicate(p, {"action": "create"}) is True
        assert evaluate_predicate(p, {"action": "delete_all"}) is False

    def test_matches_regex(self):
        p = StructuredPredicate(field="path", op="matches", value=r"^/api/v\d+")
        assert evaluate_predicate(p, {"path": "/api/v2/users"}) is True
        assert evaluate_predicate(p, {"path": "/web/page"}) is False

    def test_matches_invalid_regex(self):
        p = StructuredPredicate(field="x", op="matches", value="[invalid")
        assert evaluate_predicate(p, {"x": "anything"}) is False

    def test_missing_field_returns_false(self):
        p = StructuredPredicate(field="missing", op="eq", value=42)
        assert evaluate_predicate(p, {"other": 42}) is False


# ---------------------------------------------------------------------------
# evaluate_compound
# ---------------------------------------------------------------------------


class TestEvaluateCompound:
    def test_all_mode_all_true(self):
        c = CompoundPredicate(
            mode="all",
            predicates=[
                StructuredPredicate(field="a", op="eq", value=1),
                StructuredPredicate(field="b", op="gt", value=0),
            ],
        )
        assert evaluate_compound(c, {"a": 1, "b": 5}) is True

    def test_all_mode_one_false(self):
        c = CompoundPredicate(
            mode="all",
            predicates=[
                StructuredPredicate(field="a", op="eq", value=1),
                StructuredPredicate(field="b", op="gt", value=10),
            ],
        )
        assert evaluate_compound(c, {"a": 1, "b": 5}) is False

    def test_any_mode_one_true(self):
        c = CompoundPredicate(
            mode="any",
            predicates=[
                StructuredPredicate(field="a", op="eq", value=999),
                StructuredPredicate(field="b", op="gt", value=0),
            ],
        )
        assert evaluate_compound(c, {"a": 1, "b": 5}) is True

    def test_any_mode_all_false(self):
        c = CompoundPredicate(
            mode="any",
            predicates=[
                StructuredPredicate(field="a", op="eq", value=999),
                StructuredPredicate(field="b", op="gt", value=100),
            ],
        )
        assert evaluate_compound(c, {"a": 1, "b": 5}) is False

    def test_empty_predicates_returns_false(self):
        c = CompoundPredicate(mode="all", predicates=[])
        assert evaluate_compound(c, {"a": 1}) is False


# ---------------------------------------------------------------------------
# _tokenize
# ---------------------------------------------------------------------------


class TestTokenize:
    def test_basic(self):
        tokens = _tokenize("Hello World 123")
        assert tokens == {"hello", "world", "123"}

    def test_punctuation_stripped(self):
        tokens = _tokenize("foo-bar_baz! @qux")
        assert "foo" in tokens
        assert "bar_baz" in tokens
        assert "qux" in tokens

    def test_empty_string(self):
        assert _tokenize("") == set()

    def test_case_folded(self):
        assert _tokenize("FOO") == {"foo"}


# ---------------------------------------------------------------------------
# _hash_embed
# ---------------------------------------------------------------------------


class TestHashEmbed:
    def test_deterministic(self):
        v1 = _hash_embed("test input")
        v2 = _hash_embed("test input")
        assert v1 == v2

    def test_dimension(self):
        vec = _hash_embed("some text", dim=64)
        assert len(vec) == 64

    def test_normalized(self):
        vec = _hash_embed("hello world")
        norm = math.sqrt(sum(v * v for v in vec))
        assert abs(norm - 1.0) < 1e-6

    def test_empty_string_returns_zero_vec(self):
        vec = _hash_embed("")
        assert all(v == 0.0 for v in vec)

    def test_different_texts_different_vectors(self):
        v1 = _hash_embed("quantum computing research")
        v2 = _hash_embed("chocolate cake recipe")
        assert v1 != v2


# ---------------------------------------------------------------------------
# cosine_similarity
# ---------------------------------------------------------------------------


class TestCosineSimilarity:
    def test_identical_vectors(self):
        v = [1.0, 0.0, 0.5]
        assert math.isclose(cosine_similarity(v, v), 1.0, abs_tol=1e-9)

    def test_orthogonal_vectors(self):
        a = [1.0, 0.0]
        b = [0.0, 1.0]
        assert math.isclose(cosine_similarity(a, b), 0.0, abs_tol=1e-9)

    def test_opposite_vectors(self):
        a = [1.0, 0.0]
        b = [-1.0, 0.0]
        assert math.isclose(cosine_similarity(a, b), -1.0, abs_tol=1e-9)

    def test_different_lengths_returns_zero(self):
        assert cosine_similarity([1.0], [1.0, 2.0]) == 0.0

    def test_zero_vector_returns_zero(self):
        assert cosine_similarity([0.0, 0.0], [1.0, 0.0]) == 0.0


# ---------------------------------------------------------------------------
# semantic_similarity
# ---------------------------------------------------------------------------


class TestSemanticSimilarity:
    def test_identical_texts(self):
        sim = semantic_similarity("hello world", "hello world")
        assert math.isclose(sim, 1.0, abs_tol=1e-6)

    def test_similar_texts_higher_than_different(self):
        sim_close = semantic_similarity(
            "machine learning classification",
            "machine learning prediction",
        )
        sim_far = semantic_similarity(
            "machine learning classification",
            "chocolate cake recipe",
        )
        assert sim_close > sim_far

    def test_empty_strings(self):
        sim = semantic_similarity("", "")
        assert sim == 0.0

    def test_symmetric(self):
        a, b = "quantum computing", "quantum physics"
        assert math.isclose(
            semantic_similarity(a, b),
            semantic_similarity(b, a),
            abs_tol=1e-9,
        )


# ---------------------------------------------------------------------------
# _numeric helper
# ---------------------------------------------------------------------------


class TestNumeric:
    def test_int(self):
        assert _numeric(5) == 5.0

    def test_float(self):
        assert _numeric(3.14) == 3.14

    def test_string_number(self):
        assert _numeric("42") == 42.0

    def test_non_numeric_raises(self):
        with pytest.raises(TypeError, match="Cannot compare"):
            _numeric("hello")
