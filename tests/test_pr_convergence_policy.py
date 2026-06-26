"""Tests for the deterministic PR convergence policy (advisory ordering).

These pin the four rules + determinism so the policy can be diffed and audited —
the same discipline the rigor gate applies to evidence, applied to PR ordering.
"""
from __future__ import annotations

from scripts.runtime.pr_convergence_policy import (
    compute_convergence_order,
    is_decision_pr,
    overlapping_surface,
)


def _pr(n, draft=False):
    return {"number": n, "isDraft": draft}


def test_r1_drafts_rank_last() -> None:
    prs = [_pr(10, draft=True), _pr(11)]
    files = {10: ["dharma_swarm/x.py"], 11: ["dharma_swarm/y.py"]}
    out = compute_convergence_order(prs, files)
    assert out["order"][-1] == 10  # the draft is last
    assert "draft" in out["rationale"][10]


def test_r2_decision_outranks_implementation() -> None:
    prs = [_pr(20), _pr(21)]
    files = {20: ["dharma_swarm/impl.py"], 21: ["docs/governance/ACTIVE_TRACK.yaml"]}
    out = compute_convergence_order(prs, files)
    assert out["order"][0] == 21  # governance/decision lane leads
    assert is_decision_pr(files[21]) and not is_decision_pr(files[20])


def test_r3_surface_overlap_elects_one_canonical() -> None:
    # two non-draft PRs touch the SAME hand-edited gate file; higher grade wins.
    prs = [_pr(30), _pr(31)]
    files = {30: ["scripts/governance/check_track_status.py"],
             31: ["scripts/governance/check_track_status.py"]}
    out = compute_convergence_order(prs, files, grades={30: 6, 31: 3})
    assert out["order"][0] == 30 and out["order"][1] == 31      # grade-6 canonical first
    assert 31 in out["rationale"] and "converge behind #30" in out["rationale"][31]
    assert not out["escalate"]                                  # grade signal => deterministic, no escalate


def test_r3_regenerable_overlap_is_not_a_collision() -> None:
    # both touch only a regenerated report -> NOT a real overlap, no dependent.
    prs = [_pr(40), _pr(41)]
    files = {40: ["reports/governance/track_portfolio.json", "dharma_swarm/a.py"],
             41: ["reports/governance/track_portfolio.json", "dharma_swarm/b.py"]}
    out = compute_convergence_order(prs, files)
    assert out["canonical"] == {}                               # no canonical election
    assert not out["escalate"]


def test_r4_equal_grade_no_signal_escalates() -> None:
    prs = [_pr(50), _pr(51)]
    files = {50: ["docs/governance/SOVEREIGN_MANIFEST.md"],
             51: ["docs/governance/SOVEREIGN_MANIFEST.md"]}
    out = compute_convergence_order(prs, files)               # no grades -> 0/0, no signal
    assert set(out["escalate"]) == {50, 51}                     # undefined -> escalate, don't guess


def test_overlapping_surface_via_owned_glob() -> None:
    assert overlapping_surface(["dharma_swarm/spine/a.py"], ["dharma_swarm/spine/b.py"],
                               owned_surfaces=["dharma_swarm/spine/**"])
    assert not overlapping_surface(["dharma_swarm/spine/a.py"], ["dharma_swarm/a2a/b.py"],
                                   owned_surfaces=["dharma_swarm/spine/**"])


def test_determinism_same_input_same_output() -> None:
    prs = [_pr(60), _pr(61, draft=True), _pr(62)]
    files = {60: ["docs/governance/x.md"], 61: ["a.py"], 62: ["b.py"]}
    a = compute_convergence_order(prs, files, grades={60: 2})
    b = compute_convergence_order(prs, files, grades={60: 2})
    assert a == b
