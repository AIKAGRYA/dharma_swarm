"""Operator autonomy dial (operator ruling 2026-07-30).

The load-bearing properties: missing env means the ruling's first-boot
default (propose); an INVALID value fails closed to shadow, never to the
default; the dial is a total order and never widens the reversibility gate.
"""

from __future__ import annotations

from dharma_swarm.operator_core.autonomy_dial import (
    DEFAULT_LEVEL,
    ENV_VAR,
    AutonomyLevel,
    at_least,
    current_autonomy_level,
    may_arm_automerge,
    may_dispatch_work,
    may_write_proposals,
    parse_level,
)


def test_missing_env_is_first_boot_default_propose() -> None:
    assert current_autonomy_level({}) is AutonomyLevel.PROPOSE
    assert DEFAULT_LEVEL is AutonomyLevel.PROPOSE
    assert parse_level(None) is AutonomyLevel.PROPOSE
    assert parse_level("   ") is AutonomyLevel.PROPOSE


def test_invalid_value_fails_closed_to_shadow_not_default() -> None:
    # A garbled instruction must never grant more autonomy than a missing one.
    for raw in ("fulll", "yes", "1", "SHADOW_MODE", "propose;full"):
        assert parse_level(raw) is AutonomyLevel.SHADOW


def test_valid_values_parse_case_insensitively() -> None:
    assert current_autonomy_level({ENV_VAR: "FULL"}) is AutonomyLevel.FULL
    assert current_autonomy_level({ENV_VAR: " dispatch "}) is AutonomyLevel.DISPATCH
    assert current_autonomy_level({ENV_VAR: "shadow"}) is AutonomyLevel.SHADOW


def test_capability_ladder_is_monotonic() -> None:
    grants = {
        AutonomyLevel.SHADOW: (False, False, False),
        AutonomyLevel.PROPOSE: (True, False, False),
        AutonomyLevel.DISPATCH: (True, True, False),
        AutonomyLevel.FULL: (True, True, True),
    }
    for level, (proposals, dispatch, automerge) in grants.items():
        assert may_write_proposals(level) is proposals
        assert may_dispatch_work(level) is dispatch
        assert may_arm_automerge(level) is automerge


def test_at_least_is_the_dial_order() -> None:
    assert at_least(AutonomyLevel.FULL, AutonomyLevel.SHADOW)
    assert at_least(AutonomyLevel.PROPOSE, AutonomyLevel.PROPOSE)
    assert not at_least(AutonomyLevel.SHADOW, AutonomyLevel.PROPOSE)
    assert not at_least(AutonomyLevel.DISPATCH, AutonomyLevel.FULL)
