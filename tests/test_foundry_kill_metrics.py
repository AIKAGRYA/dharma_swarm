"""Tests for the standing kill-metrics."""

from __future__ import annotations

from dharma_swarm.foundry.kill_metrics import (
    KILL,
    OK,
    WARN,
    evaluate_kill_metrics,
    render_walking_brief,
)


def _status(snapshot, metric):
    return next(v.status for v in snapshot.verdicts if v.metric == metric)


def test_healthy_snapshot_has_no_kill():
    snap = evaluate_kill_metrics(cohort_survival=0.7, verified_improvements=3)
    assert not snap.any_kill()
    assert _status(snap, "survival_collapse") == OK


def test_survival_collapse_kills_on_two_bad_cohorts():
    snap = evaluate_kill_metrics(
        cohort_survival=0.1, prior_cohort_survival=0.2, verified_improvements=3
    )
    assert _status(snap, "survival_collapse") == KILL
    assert snap.any_kill()


def test_survival_warns_on_single_bad_cohort():
    snap = evaluate_kill_metrics(cohort_survival=0.1, verified_improvements=3)
    assert _status(snap, "survival_collapse") == WARN
    assert not snap.any_kill()


def test_discovery_starved_warns():
    snap = evaluate_kill_metrics(cohort_survival=0.7, verified_improvements=0)
    assert _status(snap, "discovery_starved") == WARN


def test_replication_failure_is_fatal():
    snap = evaluate_kill_metrics(
        cohort_survival=0.7, verified_improvements=3, replication_failures=1
    )
    assert _status(snap, "replication_failure") == KILL
    assert snap.any_kill()


def test_target_ban_freezes():
    snap = evaluate_kill_metrics(
        cohort_survival=0.7, verified_improvements=3, banned_targets=["vllm"]
    )
    assert _status(snap, "target_banned") == KILL


def test_commoditization_kills():
    snap = evaluate_kill_metrics(
        cohort_survival=0.7, verified_improvements=3, commoditized=True
    )
    assert _status(snap, "commoditized") == KILL


def test_walking_brief_renders_status():
    snap = evaluate_kill_metrics(cohort_survival=0.7, verified_improvements=3)
    brief = render_walking_brief(snap)
    assert "Sublimation Foundry" in brief
    assert "STATUS" in brief
