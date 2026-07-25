"""Property-based tests for the onboarding readiness policy.

Laws under test over generated condition sets:

1.  Lossless retention: the winning scalar never deletes a condition —
    every observed condition survives into the result, unchanged.
2.  READY exactness: an all-pass set is READY/exit 0, and any mandatory
    nonpass condition makes READY impossible (no nonpass→pass promotion).
3.  Usage dominance: a usage-class condition forces USAGE_ERROR/exit 2
    over everything else.
4.  Scalar precedence: usage > config-fail > toolchain-fail > mandatory
    nonpass (BLOCKED) > needs_host, exactly the scalar-verdict precedence.
5.  Exit mapping: exit_code is EXIT_BY_VERDICT[verdict], with the one
    documented exception — NEEDS_HOST without require_live exits 0 (typed,
    never pass-like) and exits 4 under require_live.
6.  Order invariance: evaluate() is a pure function of the condition SET;
    permuting the input changes nothing.
7.  Monotone escalation: adding a condition can hold or worsen the
    verdict, never improve it.
8.  Duplicate condition ids are a contract violation, always.
9.  Optional info conditions never block: non-mandatory, info-class,
    non-host conditions cannot take READY away.
10. Bookkeeping: host_gaps are exactly the needs_host ids; READY implies
    zero blockers; blockers only name observed conditions.

NOTE — deliberate deviation from sibling property files: hypothesis is
imported directly, NOT via pytest.importorskip. This file backs the
readiness property battery, and an all-skipped run exits 0 — a
false pass. A missing dev dependency must fail loud here, not skip quiet.
"""

from __future__ import annotations

import pytest
from hypothesis import given, settings, strategies as st

from dharma_swarm.operator_core.onboarding.models import OnboardingContractError
from dharma_swarm.operator_core.onboarding.readiness import (
    CHECK_STATES,
    CONDITION_CLASSES,
    EXIT_BY_VERDICT,
    Condition,
    VERDICT_BLOCKED,
    VERDICT_CONFIG_ERROR,
    VERDICT_NEEDS_HOST,
    VERDICT_READY,
    VERDICT_TOOLCHAIN_MISSING,
    VERDICT_USAGE_ERROR,
    evaluate,
)

# Severity rank for the monotone-escalation law: READY is best; the rest
# follow scalar-verdict precedence from weakest to strongest override.
_SEVERITY = {
    VERDICT_READY: 0,
    VERDICT_NEEDS_HOST: 1,
    VERDICT_BLOCKED: 2,
    VERDICT_TOOLCHAIN_MISSING: 3,
    VERDICT_CONFIG_ERROR: 4,
    VERDICT_USAGE_ERROR: 5,
}

_NONPASS = ("fail", "warn", "skipped", "not_observed")

_ids = st.text(alphabet="abcdefghijklmnopqrstuvwxyz_", min_size=1, max_size=16)
_states = st.sampled_from(CHECK_STATES)
_classes = st.sampled_from(CONDITION_CLASSES)


@st.composite
def _conditions(draw, min_size=0, max_size=8, states=_states, classes=_classes,
                mandatory=st.booleans()):
    """A list of Conditions with unique ids (reason always provided)."""
    spec = draw(st.dictionaries(
        _ids, st.tuples(states, classes, mandatory),
        min_size=min_size, max_size=max_size,
    ))
    return [
        Condition(id=cid, state=state, condition_class=cclass,
                  reason="generated", mandatory=is_mandatory)
        for cid, (state, cclass, is_mandatory) in spec.items()
    ]


@given(_conditions())
def test_lossless_condition_retention(conditions):
    result = evaluate(conditions)
    assert sorted(c.id for c in conditions) == list(result.condition_ids())
    by_id = {c.id: c for c in conditions}
    for kept in result.conditions:
        original = by_id[kept.id]
        assert (kept.state, kept.condition_class, kept.reason, kept.mandatory) == (
            original.state, original.condition_class, original.reason,
            original.mandatory)


@given(_conditions(states=st.just("pass"),
                   classes=st.sampled_from([c for c in CONDITION_CLASSES
                                            if c != "usage"])))
def test_all_pass_is_ready_exit_zero(conditions):
    result = evaluate(conditions)
    assert result.verdict == VERDICT_READY
    assert result.exit_code == 0
    assert result.ready


@given(_conditions(), _ids)
def test_mandatory_nonpass_never_promotes_to_ready(conditions, extra_id):
    for state in _NONPASS:
        blocked = [c for c in conditions if c.id != extra_id]
        blocked.append(Condition(id=extra_id, state=state,
                                 condition_class="blocking",
                                 reason="generated", mandatory=True))
        result = evaluate(blocked)
        assert result.verdict != VERDICT_READY
        assert result.exit_code != 0


@given(_conditions(), _ids, _states)
def test_usage_class_dominates_everything(conditions, extra_id, state):
    rest = [c for c in conditions if c.id != extra_id]
    rest.append(Condition(id=extra_id, state=state, condition_class="usage",
                          reason="generated", mandatory=True))
    result = evaluate(rest)
    assert result.verdict == VERDICT_USAGE_ERROR
    assert result.exit_code == 2


@given(_conditions())
def test_scalar_precedence_matches_spec_table(conditions):
    result = evaluate(conditions)
    has_usage = any(c.condition_class == "usage" for c in conditions)
    has_host = any(c.state == "needs_host" for c in conditions)
    has_config_fail = any(
        c.condition_class == "config" and c.state == "fail" for c in conditions)
    has_toolchain_fail = any(
        c.condition_class == "toolchain" and c.state == "fail"
        for c in conditions)
    has_mandatory_nonpass = any(
        c.mandatory and c.state in _NONPASS for c in conditions)
    if has_usage:
        expected = VERDICT_USAGE_ERROR
    elif has_config_fail:
        expected = VERDICT_CONFIG_ERROR
    elif has_toolchain_fail:
        expected = VERDICT_TOOLCHAIN_MISSING
    elif has_mandatory_nonpass:
        expected = VERDICT_BLOCKED
    elif has_host:
        expected = VERDICT_NEEDS_HOST
    else:
        expected = VERDICT_READY
    assert result.verdict == expected


@given(_conditions(), st.booleans())
def test_exit_mapping_with_needs_host_exception(conditions, require_live):
    result = evaluate(conditions, require_live=require_live)
    if result.verdict == VERDICT_NEEDS_HOST and not require_live:
        assert result.exit_code == 0
    else:
        assert result.exit_code == EXIT_BY_VERDICT[result.verdict]


@given(_conditions(min_size=1), st.randoms())
def test_order_invariance(conditions, rng):
    shuffled = list(conditions)
    rng.shuffle(shuffled)
    assert evaluate(conditions) == evaluate(shuffled)


@settings(max_examples=50)
@given(_conditions(), _conditions(min_size=1))
def test_adding_conditions_never_improves_the_verdict(base, extra):
    taken = {c.id for c in base}
    additions = [c for c in extra if c.id not in taken]
    before = evaluate(base)
    after = evaluate(base + additions)
    assert _SEVERITY[after.verdict] >= _SEVERITY[before.verdict]


@given(_conditions(min_size=1))
def test_duplicate_condition_ids_are_rejected(conditions):
    with pytest.raises(OnboardingContractError):
        evaluate(conditions + [conditions[0]])


@given(_conditions(classes=st.just("info"), mandatory=st.just(False),
                   states=st.sampled_from(
                       [s for s in CHECK_STATES if s != "needs_host"])))
def test_optional_info_conditions_never_block(conditions):
    result = evaluate(conditions)
    assert result.verdict == VERDICT_READY
    assert result.exit_code == 0


@given(_conditions())
def test_host_gap_and_blocker_bookkeeping(conditions):
    result = evaluate(conditions)
    assert set(result.host_gaps) == {
        c.id for c in conditions if c.state == "needs_host"}
    assert set(result.blockers) <= {c.id for c in conditions}
    if result.verdict == VERDICT_READY:
        assert result.blockers == ()
