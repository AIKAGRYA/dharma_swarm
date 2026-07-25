"""RFC 8785 JCS conformance and round-trip properties."""
from __future__ import annotations

import json
import math

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from telos_kernel.canonical import MAX_DEPTH, canonicalize


class TestJcsBasics:
    def test_null(self):
        assert canonicalize(None) == b"null"

    def test_bools(self):
        assert canonicalize(True) == b"true"
        assert canonicalize(False) == b"false"

    def test_ints(self):
        assert canonicalize(0) == b"0"
        assert canonicalize(-1) == b"-1"
        assert canonicalize(123456789) == b"123456789"

    def test_string_escapes(self):
        assert canonicalize("hello") == b'"hello"'
        assert canonicalize('a"b') == b'"a\\"b"'
        assert canonicalize("a\\b") == b'"a\\\\b"'
        assert canonicalize("a\nb") == b'"a\\nb"'
        assert canonicalize("a\tb") == b'"a\\tb"'

    def test_control_char_escape(self):
        # 0x01 must be escaped as \u0001
        assert canonicalize("\x01") == b'"\\u0001"'

    def test_empty_containers(self):
        assert canonicalize([]) == b"[]"
        assert canonicalize({}) == b"{}"

    def test_key_sort(self):
        # Keys must sort by codepoint. Alphabetical for ASCII.
        assert canonicalize({"b": 1, "a": 2}) == b'{"a":2,"b":1}'

    def test_nested(self):
        assert canonicalize({"z": [1, 2], "a": {"n": None}}) == \
            b'{"a":{"n":null},"z":[1,2]}'

    def test_rejects_nan_inf(self):
        with pytest.raises(ValueError):
            canonicalize(float("nan"))
        with pytest.raises(ValueError):
            canonicalize(float("inf"))
        with pytest.raises(ValueError):
            canonicalize(float("-inf"))

    def test_float_ecmascript_thresholds(self):
        assert canonicalize(1e-6) == b"0.000001"
        assert canonicalize(-1e-6) == b"-0.000001"
        assert canonicalize(1.234e-5) == b"0.00001234"
        assert canonicalize(1e-7) == b"1e-7"
        assert canonicalize(1e20) == b"100000000000000000000"
        assert canonicalize(1e21) == b"1e+21"
        assert canonicalize(1.23e21) == b"1.23e+21"

    def test_rejects_non_string_key(self):
        with pytest.raises(ValueError):
            canonicalize({1: "x"})

    def test_rejects_bytes(self):
        with pytest.raises(ValueError):
            canonicalize(b"raw")

    def test_rejects_set(self):
        with pytest.raises(ValueError):
            canonicalize({1, 2, 3})

    def test_deep_nesting_rejected(self):
        # Build a chain deeper than MAX_DEPTH.
        v = 0
        for _ in range(MAX_DEPTH + 1):
            v = [v]
        with pytest.raises(RecursionError):
            canonicalize(v)


class TestJcsDeterminism:
    """Two calls with the same input must produce the same bytes."""

    @given(st.recursive(
        st.one_of(
            st.none(), st.booleans(),
            st.integers(min_value=-(2**53), max_value=2**53),
            st.text(alphabet=st.characters(min_codepoint=32, max_codepoint=126), max_size=20),
        ),
        lambda children: st.one_of(
            st.lists(children, max_size=6),
            st.dictionaries(
                st.text(alphabet=st.characters(min_codepoint=32, max_codepoint=126),
                        min_size=1, max_size=8),
                children, max_size=6,
            ),
        ),
        max_leaves=20,
    ))
    @settings(max_examples=200, deadline=None)
    def test_repeatable(self, value):
        assert canonicalize(value) == canonicalize(value)

    @given(st.dictionaries(
        st.text(alphabet=st.characters(min_codepoint=97, max_codepoint=122),
                min_size=1, max_size=5),
        st.integers(min_value=-1000, max_value=1000),
        min_size=1, max_size=8,
    ))
    @settings(max_examples=100, deadline=None)
    def test_key_order_independent(self, d):
        # Building a dict with different insertion orders must yield the same
        # canonical form.
        keys = list(d.keys())
        d1 = {k: d[k] for k in keys}
        d2 = {k: d[k] for k in reversed(keys)}
        assert canonicalize(d1) == canonicalize(d2)


class TestJcsAgainstJsonModule:
    """For simple objects, canonical form must remain parseable JSON."""

    @given(st.dictionaries(
        st.text(alphabet=st.characters(min_codepoint=97, max_codepoint=122),
                min_size=1, max_size=6),
        st.one_of(
            st.integers(min_value=-1000, max_value=1000),
            st.booleans(),
            st.none(),
        ),
        max_size=6,
    ))
    @settings(max_examples=100, deadline=None)
    def test_reparses(self, d):
        canonical = canonicalize(d)
        reparsed = json.loads(canonical.decode("utf-8"))
        assert reparsed == d
