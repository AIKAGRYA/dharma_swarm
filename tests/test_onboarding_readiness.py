"""Session readiness policy: lossless precedence, nonpass states, host scope."""

from __future__ import annotations

import pytest

from dharma_swarm.operator_core.onboarding.models import OnboardingContractError
from dharma_swarm.operator_core.onboarding.readiness import (
    VERDICT_CONFIG_ERROR,
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


def test_generated_projection_is_diagnostic_not_a_session_gate() -> None:
    """A sterile clone has no generated projection and must still be usable."""
    from dharma_swarm.operator_core.onboarding import cli

    conditions = cli._collect_conditions(
        {"dirty": False, "conflicted": False},
        {"git": "git version test", "make": "GNU Make test"},
        {"broken_register": {"total": 0, "open_like": 0, "closed_like": 0}},
        net=False,
    )
    outcome = evaluate(conditions)
    assert outcome.verdict == "READY"
    assert outcome.exit_code == 0
    assert "active_track_projection_fresh" not in outcome.condition_ids()


def test_repository_identity_condition_preserves_cutover_semantics(
    tmp_path,
) -> None:
    from dharma_swarm.operator_core.onboarding import cli
    from dharma_swarm.operator_core.onboarding.repository_identity import (
        CANONICAL_ORIGIN_URL,
        RepositoryIdentityStatus,
        observe_repository_identity,
    )

    repo = tmp_path / "repo"
    repo.mkdir()
    import subprocess

    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)

    def condition_for(origin: str | None, now: str):
        subprocess.run(
            ["git", "config", "--local", "--unset-all", "remote.origin.url"],
            cwd=repo,
            check=False,
        )
        if origin is not None:
            subprocess.run(
                ["git", "config", "--local", "--add", "remote.origin.url", origin],
                cwd=repo,
                check=True,
            )
        observation = observe_repository_identity(repo, now=now)
        conditions = cli._collect_conditions(
            {"dirty": False, "conflicted": False},
            {"git": "git version test", "make": "GNU Make test"},
            {"broken_register": {}},
            net=False,
            repository_observation=observation,
        )
        return observation, next(
            row for row in conditions if row.id == "repository_identity"
        ), evaluate(conditions)

    canonical, canonical_condition, canonical_outcome = condition_for(
        CANONICAL_ORIGIN_URL, "2026-08-15T14:59:59Z"
    )
    assert canonical.status is RepositoryIdentityStatus.CANONICAL
    assert canonical_condition.state == "pass"
    assert canonical_outcome.verdict == "READY"

    legacy_url = "https://github.com/AmitabhainArunachala/dharma_swarm.git"
    compatible, warning, compatible_outcome = condition_for(
        legacy_url, "2026-08-15T14:59:59Z"
    )
    assert compatible.status is RepositoryIdentityStatus.LEGACY_COMPATIBLE
    assert warning.state == "warn" and warning.mandatory is False
    assert compatible_outcome.verdict == "READY"

    expired, failure, expired_outcome = condition_for(
        legacy_url, "2026-08-15T15:00:00Z"
    )
    assert expired.status is RepositoryIdentityStatus.LEGACY_EXPIRED
    assert failure.state == "fail" and failure.condition_class == "config"
    assert expired_outcome.verdict == "CONFIG_ERROR"
    assert expired_outcome.exit_code == 3

    wrong, wrong_condition, wrong_outcome = condition_for(
        "https://github.com/shakti-saraswati/dharma_swarm.git",
        "2026-08-15T14:59:59Z",
    )
    assert wrong.status is RepositoryIdentityStatus.WRONG_TARGET
    assert wrong_condition.state == "fail"
    assert wrong_outcome.verdict == "CONFIG_ERROR"

    sterile, sterile_condition, sterile_outcome = condition_for(
        None, "2026-08-15T15:00:00Z"
    )
    assert sterile.status is RepositoryIdentityStatus.STERILE
    assert sterile_condition.state == "skipped"
    assert sterile_condition.mandatory is False
    assert sterile_outcome.verdict == "READY"


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


def test_git_probe_failures_are_typed_config_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """O3R-B1: an unobservable worktree is CONFIG_ERROR, never false-clean.

    The simultaneous base-distance error remains visible but is not what
    makes the verdict blocking.
    """
    from dharma_swarm.operator_core.onboarding import cli, evidence

    def broken_probe(*args: str, cwd=None) -> tuple[str, str]:
        return "", f"exit 128: git {' '.join(args)}"

    monkeypatch.setattr(evidence, "_git_probe", broken_probe)
    live_state, probe_errors = evidence.observe_repo_live_state()
    assert live_state["dirty"] is True  # fail-closed raw view, not false clean
    assert set(probe_errors) == {"status", "ahead_behind"}

    conditions = cli._collect_conditions(
        live_state,
        {"git": "git version test", "make": "GNU Make test"},
        {"broken_register": {"total": 0, "open_like": 0, "closed_like": 0, "unknown": 0}},
        net=False,
        probe_errors=probe_errors,
    )
    by_id = {condition.id: condition for condition in conditions}
    assert by_id["git_state_observed"].state == "fail"
    assert by_id["git_state_observed"].condition_class == "config"
    assert by_id["git_base_distance_observed"].state == "warn"
    assert by_id["git_base_distance_observed"].mandatory is False
    assert by_id["repo_clean"].state == "not_observed"
    assert by_id["repo_unconflicted"].state == "not_observed"

    outcome = evaluate(conditions)
    assert outcome.verdict == VERDICT_CONFIG_ERROR
    assert outcome.exit_code == 3

    def malformed_probe(*args: str, cwd=None) -> tuple[str, str]:
        if args[0] == "status":
            return "", ""
        return "not-numbers", ""

    monkeypatch.setattr(evidence, "_git_probe", malformed_probe)
    state, errors = evidence.observe_repo_live_state()
    assert state["ahead"] == 0 and state["behind"] == 0
    assert "ahead_behind" in errors and "malformed" in errors["ahead_behind"]

    def healthy_probe(*args: str, cwd=None) -> tuple[str, str]:
        if args[0] == "status":
            return "", ""
        return "0\t0", ""

    monkeypatch.setattr(evidence, "_git_probe", healthy_probe)
    state, errors = evidence.observe_repo_live_state()
    assert errors == {}
    assert state["dirty"] is False


def test_missing_base_ref_is_visible_but_does_not_block_clean_status() -> None:
    """A detached checkout can prove cleanliness without ``origin/main``."""
    from dharma_swarm.operator_core.onboarding import cli

    conditions = cli._collect_conditions(
        {"dirty": False, "conflicted": False, "ahead": 0, "behind": 0},
        {"git": "git version test", "make": "GNU Make test"},
        {"broken_register": {}},
        net=False,
        probe_errors={
            "ahead_behind": "exit 128: git rev-list origin/main...HEAD",
        },
    )
    by_id = {condition.id: condition for condition in conditions}
    assert "git_state_observed" not in by_id
    assert by_id["git_base_distance_observed"].state == "warn"
    assert by_id["git_base_distance_observed"].mandatory is False

    outcome = evaluate(conditions)
    assert outcome.verdict == "READY"
    assert outcome.exit_code == 0


def test_duplicate_condition_ids_are_rejected() -> None:
    with pytest.raises(OnboardingContractError):
        evaluate([_c("dup"), _c("dup")])
