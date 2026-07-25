"""Property-based tests for the quality ratchet's algebra.

Laws under test, over generated (baseline, reading, direction) triples:

1. Exclusivity: a comparison is never both regressed and improved, and
   equal values are neither.
2. Monotonicity: tighten() never loosens — every tightened bound is at
   least as strict as the old one, in the counter's own direction.
3. Idempotence: tighten(tighten(b, m), m) == tighten(b, m).
4. Fixpoint: after tightening, re-comparing the same readings yields
   zero improvements and zero regressions (the ratchet has fully bitten).
5. Persistence: save_baselines/load_baselines round-trips any valid
   counter mapping exactly.

These laws are what make "one-way" a property of the system rather than
a hope: 2-4 together prove repeated green runs converge to a fixpoint
and never walk a bound backwards.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

hypothesis = pytest.importorskip("hypothesis", reason="hypothesis not installed")
from hypothesis import given, strategies as st

REPO_ROOT = Path(__file__).resolve().parents[2]
HYGIENE_DIR = REPO_ROOT / "scripts" / "governance" / "hygiene"


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, HYGIENE_DIR / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


counters_mod = _load("ratchet_counters")
ratchet = _load("ratchet")

Direction = counters_mod.Direction

values = st.integers(min_value=0, max_value=10_000)
directions = st.sampled_from([Direction.DOWN, Direction.UP])
names = st.text(
    alphabet="abcdefghijklmnopqrstuvwxyz_", min_size=1, max_size=20
).filter(lambda s: not s.startswith("_"))


@st.composite
def comparison_sets(draw):
    """A baseline dict plus matching comparisons with arbitrary readings."""
    mapping = draw(
        st.dictionaries(names, st.tuples(values, values, directions), min_size=1, max_size=8)
    )
    baselines = {name: baseline for name, (baseline, _, _) in mapping.items()}
    comparisons = [
        ratchet.Comparison(
            name=name,
            direction=direction,
            baseline=baseline,
            value=value,
            end_target=0,
            evidence=(),
        )
        for name, (baseline, value, direction) in mapping.items()
    ]
    return baselines, comparisons


def _stricter_or_equal(new: int, old: int, direction: Direction) -> bool:
    return new <= old if direction is Direction.DOWN else new >= old


@given(baseline=values, value=values, direction=directions)
def test_regressed_and_improved_are_exclusive(baseline, value, direction):
    comparison = ratchet.Comparison(
        name="c", direction=direction, baseline=baseline, value=value,
        end_target=0, evidence=(),
    )
    assert not (comparison.regressed and comparison.improved)
    if value == baseline:
        assert not comparison.regressed and not comparison.improved
        assert comparison.verdict == "OK"


@given(comparison_sets())
def test_tighten_never_loosens(data):
    baselines, comparisons = data
    tightened = ratchet.tighten(baselines, comparisons)
    by_name = {c.name: c for c in comparisons}
    for name, old in baselines.items():
        assert _stricter_or_equal(tightened[name], old, by_name[name].direction)


@given(comparison_sets())
def test_tighten_is_idempotent(data):
    baselines, comparisons = data
    once = ratchet.tighten(baselines, comparisons)
    twice = ratchet.tighten(
        once,
        [
            ratchet.Comparison(
                name=c.name, direction=c.direction, baseline=once[c.name],
                value=c.value, end_target=c.end_target, evidence=c.evidence,
            )
            for c in comparisons
        ],
    )
    assert twice == once


@given(comparison_sets())
def test_tightened_baselines_are_a_fixpoint_for_the_same_readings(data):
    baselines, comparisons = data
    tightened = ratchet.tighten(baselines, comparisons)
    recompared = [
        ratchet.Comparison(
            name=c.name, direction=c.direction, baseline=tightened[c.name],
            value=c.value, end_target=c.end_target, evidence=c.evidence,
        )
        for c in comparisons
    ]
    assert not any(c.improved for c in recompared)
    # Readings that were regressions stay regressions (tighten must not
    # absorb them); readings that were green are now exactly at baseline.
    for before, after in zip(comparisons, recompared):
        assert after.regressed == before.regressed


@given(st.dictionaries(names, values, min_size=1, max_size=8))
def test_save_load_round_trip(tmp_path_factory, counters):
    path = tmp_path_factory.mktemp("ratchet") / "baselines.json"
    fake = tuple(
        counters_mod.Counter(
            name=name, direction=Direction.DOWN, end_target=0,
            definition="fake", measure=lambda root: counters_mod.Reading(0),
        )
        for name in counters
    )
    original = ratchet.COUNTERS
    ratchet.COUNTERS = fake
    try:
        ratchet.save_baselines(path, dict(counters), "2026-06-13")
        assert ratchet.load_baselines(path) == counters
    finally:
        ratchet.COUNTERS = original
