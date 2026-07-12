"""WP-O3 readiness policy: lossless precedence, nonpass states, host scope.

Covers O3-B2 (exit precedence retains all simultaneous conditions), O3-B3
(mandatory warn/skip/unavailable never counts pass), and the policy half of
O3-B7 (host scope: required live gaps exit 4; non-required stay typed exit 0).
"""

from __future__ import annotations

import pytest

from dharma_swarm.operator_core.onboarding.models import OnboardingContractError
from dharma_swarm.operator_core.onboarding.readiness import (
    Condition,
    evaluate,
)


def _c(cid: str, state: str = "pass", **kw) -> Condition:
    if state in {"skipped", "not_observed"} and "reason" not in kw:
        kw["reason"] = "declared for test"
    return Condition(id=cid, state=state, **kw)


# --- O3-B2: scalar precedence with lossless retention -----------------------

def test_usage_error_beats_everything_and_retains_conditions() -> None:
    out = evaluate([
        _c("usage_error", "fail", condition_class="usage"),
        _c("ownership_conflict", "fail", condition_class="blocking"),
    ])
    assert out.verdict == "USAGE_ERROR"
    assert out.exit_code == 2
    assert out.condition_ids() == ("ownership_conflict", "usage_error")


def test_config_beats_toolchain_and_both_are_retained() -> None:
    out = evaluate([
        _c("config_error", "fail", condition_class="config"),
        _c("toolchain_missing", "fail", condition_class="toolchain"),
    ])
    assert out.verdict == "CONFIG_ERROR"
    assert out.exit_code == 3
    assert set(out.condition_ids()) == {"config_error", "toolchain_missing"}


def test_toolchain_beats_blocked_and_sentinel_is_retained() -> None:
    out = evaluate([
        _c("toolchain_missing", "fail", condition_class="toolchain"),
        _c("sentinel_failed", "fail", condition_class="blocking"),
    ])
    assert out.verdict == "TOOLCHAIN_MISSING"
    assert out.exit_code == 5
    assert "sentinel_failed" in out.condition_ids()


def test_blocked_beats_needs_host_and_gap_is_retained() -> None:
    out = evaluate([
        _c("stale_cache", "fail", condition_class="blocking"),
        _c("needs_host", "needs_host", condition_class="host"),
    ], require_live=True)
    assert out.verdict == "BLOCKED"
    assert out.exit_code == 1
    assert out.host_gaps == ("needs_host",)


def test_partial_evidence_plus_nonrequired_host_gap_is_blocked() -> None:
    out = evaluate([
        _c("evidence_incomplete", "fail", condition_class="blocking"),
        _c("onboard_needs_runtime_db", "needs_host", condition_class="host"),
    ])
    assert out.verdict == "BLOCKED"
    assert out.exit_code == 1
    assert out.host_gaps == ("onboard_needs_runtime_db",)


# --- O3-B3: mandatory nonpass states can never produce READY ----------------

@pytest.mark.parametrize("state", ["fail", "warn", "skipped", "not_observed"])
def test_mandatory_nonpass_state_cannot_produce_ready(state: str) -> None:
    out = evaluate([
        _c("all_good", "pass"),
        _c("mandatory_gate", state, condition_class="blocking"),
    ])
    assert not out.ready
    assert out.verdict == "BLOCKED"


def test_optional_warn_stays_warn_and_does_not_block() -> None:
    out = evaluate([
        _c("all_good", "pass"),
        _c("advisory", "warn", mandatory=False),
    ])
    assert out.ready
    assert out.exit_code == 0
    warn = next(c for c in out.conditions if c.id == "advisory")
    assert warn.state == "warn"  # never silently counted as pass


# --- O3-B7 (policy half): host scope mapping ---------------------------------

def test_required_live_host_gap_exits_four() -> None:
    out = evaluate(
        [_c("onboard_needs_daemon_census", "needs_host", condition_class="host")],
        require_live=True,
    )
    assert out.verdict == "NEEDS_HOST"
    assert out.exit_code == 4


def test_nonrequired_host_gap_is_typed_but_exits_zero() -> None:
    out = evaluate(
        [_c("onboard_needs_daemon_census", "needs_host", condition_class="host")],
        require_live=False,
    )
    assert out.verdict == "NEEDS_HOST"
    assert out.exit_code == 0
    assert out.host_gaps == ("onboard_needs_daemon_census",)


def test_executed_live_failure_is_fail_never_needs_host() -> None:
    out = evaluate([
        _c("runtime_db_probe", "fail", condition_class="blocking",
           reason="probe executed and failed"),
    ], require_live=True)
    assert out.verdict == "BLOCKED"
    assert out.host_gaps == ()


# --- contract validation ------------------------------------------------------

def test_skipped_without_reason_is_a_contract_error() -> None:
    with pytest.raises(OnboardingContractError):
        Condition(id="x", state="skipped")


def test_unknown_state_is_a_contract_error() -> None:
    with pytest.raises(OnboardingContractError):
        Condition(id="x", state="green")


def test_duplicate_condition_ids_are_rejected() -> None:
    with pytest.raises(OnboardingContractError):
        evaluate([_c("dup"), _c("dup")])
