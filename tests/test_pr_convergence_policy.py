"""Tests for the deterministic PR convergence policy (advisory ordering).

These pin the four rules + determinism so the policy can be diffed and audited —
the same discipline the rigor gate applies to evidence, applied to PR ordering.
"""
from __future__ import annotations

import hashlib
import json

import pytest

from scripts.runtime.pr_convergence_policy import (
    HUMAN_EXCEPTION,
    MERGED,
    OPERATOR_CANCELLED,
    PLAN_SCHEMA,
    QUEUE_CANDIDATE,
    REFRESH_STRANDED,
    REPAIR_CODE,
    REQUEST_REVIEW,
    RERUN_TRANSIENT,
    TRUSTED_POLICY_DIGEST,
    TRUSTED_OWNED_SURFACES_SHA256,
    WAIT,
    compute_convergence_order,
    is_decision_pr,
    main,
    overlapping_surface,
    plan_convergence_actions,
    plan_from_payload,
)

SHA_A = "a" * 40
SHA_B = "b" * 40
DIGEST_D = "d" * 64
REPO = "AIKAGRYA/dharma_swarm"


def _pr(n, draft=False):
    return {"number": n, "isDraft": draft}


def _canonical_digest(payload) -> str:
    return hashlib.sha256(
        json.dumps(
            payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False
        ).encode("utf-8")
    ).hexdigest()


def _authorization_report(row):
    warrant = None
    if row["operator_warrant"]:
        warrant = {
            "kind": row["operator_warrant_kind"],
            "id": row["operator_warrant_id"],
            "actor": str(row["operator_warrant_actor"]).lower(),
            "head_sha": row["head_sha"],
        }
    evidence = {
        "schema": "dharma.merge_authorization_evidence.v1",
        "repo": REPO,
        "pr": row["number"],
        "head_sha": row["head_sha"],
        "base_sha": row["base_sha"],
        "base_ref": row["base_ref"],
        "policy_sha256": TRUSTED_POLICY_DIGEST,
        "intent_sha256": _canonical_digest(row["title"]),
        "authority_class": row["policy_class"],
        "ai_evidence_ids": [row["ai_evidence_id"]] if row["ai_evidence"] else [],
        "operator_warrant": warrant,
        "provenance": "unsigned-github-snapshot",
        "actuation_eligible": False,
    }
    evidence["digest"] = _canonical_digest(evidence)
    return {
        "schema": "dharma.automerge_tier_policy_report.v2",
        "passed": True,
        "violations": [],
        "authorization_evidence": evidence,
    }


def _native_queue_merge_observation(row):
    observation = {
        "schema": "dharma.native_queue_merge_observation.v1",
        "pr": row["number"],
        "pr_head_sha": row["head_sha"],
        "base_sha": row["base_sha"],
        "merge_group_sha": "c" * 40,
        "merge_commit_sha": "c" * 40,
        "merge_method": "SQUASH",
        "queue_entry_event_id": "queue-entry-event:1",
        "merge_event_id": "merge-event:1",
        "queue_removal_event_id": "queue-removal-event:1",
        "queue_removal_reason": "MERGED",
        "timeline_complete": True,
    }
    observation["digest"] = _canonical_digest(observation)
    return observation


def _fact(n: int, **overrides):
    row = {
        "number": n,
        "head_sha": SHA_A,
        "base_sha": SHA_B,
        "base_ref": "main",
        "title": f"PR {n}",
        "head_observed_current": True,
        "base_observed_current": True,
        "operator_queue_intent": "NONE",
        "operator_queue_intent_head_sha": None,
        "operator_queue_intent_event_id": None,
        "operator_queue_intent_actor": None,
        "queue_timeline_complete": True,
        "is_draft": False,
        "is_cross_repository": False,
        "mergeable": "MERGEABLE",
        "queue_state": "NONE",
        "queue_entry_provenance": "NONE",
        "queue_entry_id": None,
        "queue_entry_head_sha": None,
        "queue_entry_actor": None,
        "policy_class": "docs_low",
        "risk": "LOW",
        "ci_state": "green",
        "review_state": "clean",
        "pr_state": "OPEN",
        "merge_provenance": "NONE",
        "merge_observation": None,
        "unresolved_threads": 0,
        "ai_evidence": True,
        "ai_evidence_id": 1,
        "ai_evidence_head_sha": SHA_A,
        "ai_evidence_actor": "chatgpt-codex-connector[bot]",
        "ai_evidence_state": "COMMENTED",
        "operator_warrant": False,
        "operator_warrant_id": None,
        "operator_warrant_head_sha": None,
        "operator_warrant_actor": None,
        "owned_surfaces_digest": TRUSTED_OWNED_SURFACES_SHA256,
        "operator_warrant_kind": None,
        "operator_warrant_state": None,
        "repairable_threads": False,
        "repair_attempts": 0,
        "behind_by": 0,
        "policy_digest": TRUSTED_POLICY_DIGEST,
        "policy_gate_observed": True,
        "policy_gate_passed": True,
        "policy_gate_check_id": 3,
        "policy_gate_head_sha": SHA_A,
        "policy_gate_base_sha": SHA_B,
        "policy_gate_app_id": 15368,
        "gate_fingerprint": DIGEST_D,
        "authorization_report": None,
    }
    row.update(overrides)
    if row["operator_queue_intent"] != "NONE":
        row["operator_queue_intent_head_sha"] = overrides.get(
            "operator_queue_intent_head_sha", SHA_A
        )
        row["operator_queue_intent_event_id"] = overrides.get(
            "operator_queue_intent_event_id", "queue-event:1"
        )
        row["operator_queue_intent_actor"] = overrides.get(
            "operator_queue_intent_actor", "AmitabhainArunachala"
        )
    if row["queue_state"] != "NONE":
        row["queue_entry_id"] = overrides.get("queue_entry_id", "queue-entry:1")
        row["queue_entry_head_sha"] = overrides.get("queue_entry_head_sha", SHA_A)
        row["queue_entry_actor"] = overrides.get(
            "queue_entry_actor", "AmitabhainArunachala"
        )
    if not row["ai_evidence"]:
        row["ai_evidence_id"] = overrides.get("ai_evidence_id")
        row["ai_evidence_head_sha"] = overrides.get("ai_evidence_head_sha")
        row["ai_evidence_actor"] = overrides.get("ai_evidence_actor")
        row["ai_evidence_state"] = overrides.get("ai_evidence_state")
    if row["operator_warrant"]:
        row["operator_warrant_id"] = overrides.get("operator_warrant_id", 2)
        row["operator_warrant_head_sha"] = overrides.get("operator_warrant_head_sha", SHA_A)
        row["operator_warrant_actor"] = overrides.get(
            "operator_warrant_actor", "AmitabhainArunachala"
        )
        row["operator_warrant_kind"] = overrides.get(
            "operator_warrant_kind", "github_review"
        )
        row["operator_warrant_state"] = overrides.get(
            "operator_warrant_state", "APPROVED"
        )
    else:
        row["operator_warrant_id"] = overrides.get("operator_warrant_id")
        row["operator_warrant_head_sha"] = overrides.get("operator_warrant_head_sha")
        row["operator_warrant_actor"] = overrides.get("operator_warrant_actor")
        row["operator_warrant_kind"] = overrides.get("operator_warrant_kind")
        row["operator_warrant_state"] = overrides.get("operator_warrant_state")
    if "authorization_report" not in overrides:
        row["authorization_report"] = _authorization_report(row)
    if (
        row["pr_state"] == "MERGED"
        and row["merge_provenance"] == "NATIVE_QUEUE"
        and "merge_observation" not in overrides
    ):
        row["merge_observation"] = _native_queue_merge_observation(row)
    return row


def _plan(*facts, files=None, max_operator_items=5, owned_surfaces_complete=True):
    prs = [_pr(row["number"], draft=row.get("is_draft", False)) for row in facts]
    if files is None:
        paths = {}
        for row in facts:
            if row["policy_class"] == "operator_only":
                path = f"docs/governance/item-{row['number']}.md"
            elif row["policy_class"] == "code":
                path = f"dharma_swarm/item_{row['number']}.py"
            else:
                path = f"docs/item-{row['number']}.md"
            paths[row["number"]] = [path]
    else:
        paths = files
    return plan_convergence_actions(
        prs,
        paths,
        {row["number"]: row for row in facts},
        repo=REPO,
        max_operator_items=max_operator_items,
        owned_surfaces_complete=owned_surfaces_complete,
    )


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


def test_r3_overlap_component_elects_one_global_canonical() -> None:
    prs = [_pr(32), _pr(30), _pr(31)]
    files = {number: ["dharma_swarm/shared.py"] for number in (30, 31, 32)}

    out = compute_convergence_order(prs, files, grades={30: 3, 31: 2, 32: 1})

    assert out["canonical"] == {"overlap:30-31-32": 30}
    assert out["dependent"] == [31, 32]
    assert "behind #30" in out["rationale"][31]
    assert "behind #30" in out["rationale"][32]


def test_r3_transitive_overlap_keeps_noncolliding_winners_parallel() -> None:
    prs = [_pr(30), _pr(31), _pr(32)]
    files = {
        30: ["dharma_swarm/x.py"],
        31: ["dharma_swarm/x.py", "dharma_swarm/y.py"],
        32: ["dharma_swarm/y.py"],
    }

    out = compute_convergence_order(prs, files, grades={30: 3, 31: 2, 32: 1})

    assert out["canonical"] == {"overlap:30-31": 30}
    assert out["dependent"] == [31]
    assert "behind #30" in out["rationale"][31]
    assert "dependent" not in out["rationale"][32]


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


def test_action_key_is_stable_per_exact_state_and_changes_with_head() -> None:
    first = _plan(_fact(63, ai_evidence=False))["items"][0]
    repeated = _plan(_fact(63, ai_evidence=False))["items"][0]
    moved = _plan(
        _fact(
            63,
            head_sha="e" * 40,
            ai_evidence=False,
            ai_evidence_head_sha=None,
        )
    )["items"][0]

    assert first["action_key"] == repeated["action_key"]
    assert first["action_key"] != moved["action_key"]


def test_action_key_distinguishes_bounded_retry_ordinal() -> None:
    first = _plan(_fact(64, ci_state="transient", repair_attempts=0))["items"][0]
    second = _plan(_fact(64, ci_state="transient", repair_attempts=1))["items"][0]

    assert first["action"] == RERUN_TRANSIENT
    assert second["action"] == RERUN_TRANSIENT
    assert first["action_key"] != second["action_key"]


def test_action_key_distinguishes_rebound_queue_evidence() -> None:
    first = _plan(_fact(65, title="first title"))["items"][0]
    second = _plan(_fact(65, title="second title"))["items"][0]

    assert first["action"] == QUEUE_CANDIDATE
    assert second["action"] == QUEUE_CANDIDATE
    assert first["action_key"] != second["action_key"]


def test_docs_low_green_is_only_a_head_bound_queue_candidate() -> None:
    fact = _fact(70)
    out = _plan(fact)
    item = out["items"][0]

    assert item["action"] == QUEUE_CANDIDATE
    assert item["authority"] == {
        "planner_modality": "advisory_only",
        "can_merge": False,
        "can_approve": False,
        "can_bypass": False,
        "can_resolve_threads": False,
    }
    assert item["queue_candidate"] == {
        "schema": "dharma.pr_convergence.queue_candidate.v1",
        "repo": REPO,
        "number": 70,
        "head_sha": SHA_A,
        "base_sha": SHA_B,
        "policy_digest": TRUSTED_POLICY_DIGEST,
        "gate_fingerprint": DIGEST_D,
        "authorization_evidence_digest": fact["authorization_report"][
            "authorization_evidence"
        ]["digest"],
        "ai_evidence_id": 1,
        "ai_evidence_actor": "chatgpt-codex-connector[bot]",
        "operator_warrant_id": None,
        "operator_warrant_actor": None,
        "owned_surfaces_digest": TRUSTED_OWNED_SURFACES_SHA256,
        "effect": "request_native_queue_admission_after_live_revalidation",
        "not_a_merge_permit": True,
    }


def test_code_candidate_requires_exact_head_operator_warrant() -> None:
    missing = _plan(_fact(71, policy_class="code", risk="MEDIUM"))["items"][0]
    present = _plan(
        _fact(71, policy_class="code", risk="MEDIUM", operator_warrant=True)
    )["items"][0]

    assert missing["action"] == HUMAN_EXCEPTION
    assert missing["reason_code"] == "OPERATOR_WARRANT_REQUIRED"
    assert present["action"] == QUEUE_CANDIDATE


def test_high_risk_never_becomes_a_queue_candidate() -> None:
    item = _plan(
        _fact(
            72,
            policy_class="operator_only",
            risk="HIGH",
            operator_warrant=True,
        )
    )["items"][0]

    assert item["action"] == HUMAN_EXCEPTION
    assert item["reason_code"] == "OPERATOR_ONLY"
    assert item["queue_candidate"] is None


def test_manual_dequeue_is_terminal_and_not_repromoted_to_inbox() -> None:
    out = _plan(
        _fact(
            73,
            operator_queue_intent="DEQUEUED",
            operator_queue_intent_head_sha=SHA_A,
            policy_class="operator_only",
            risk="HIGH",
        )
    )
    item = out["items"][0]

    assert item["action"] == OPERATOR_CANCELLED
    assert item["reason_code"] == "CANCELLED_BY_OPERATOR"
    assert item["terminal_for_head"] is False
    assert item["terminal_key"] == {
        "head_sha": SHA_A,
        "queue_intent_event_id": "queue-event:1",
    }
    assert out["operator_inbox"] == []


def test_terminal_dequeue_cannot_block_a_live_overlapping_pr() -> None:
    facts = {
        96: _fact(96, operator_queue_intent="DEQUEUED"),
        97: _fact(97),
    }
    out = plan_convergence_actions(
        [_pr(96), _pr(97)],
        {96: ["docs/shared.md"], 97: ["docs/shared.md"]},
        facts,
        repo=REPO,
        grades={96: 8, 97: 4},
        owned_surfaces_complete=True,
    )

    by_pr = {item["number"]: item for item in out["items"]}
    assert out["order"]["canonical"] == {}
    assert out["order"]["dependent"] == []
    assert by_pr[96]["action"] == OPERATOR_CANCELLED
    assert by_pr[97]["action"] == QUEUE_CANDIDATE


def test_manual_dequeue_from_another_head_fails_closed() -> None:
    item = _plan(
        _fact(
            73,
            operator_queue_intent="DEQUEUED",
            operator_queue_intent_head_sha="e" * 40,
        )
    )["items"][0]

    assert item["action"] == HUMAN_EXCEPTION
    assert item["reason_code"] == "STATE_UNKNOWN"


def test_manual_dequeue_requires_a_complete_timeline_reduction() -> None:
    item = _plan(
        _fact(
            73,
            operator_queue_intent="DEQUEUED",
            queue_timeline_complete=False,
        )
    )["items"][0]

    assert item["action"] == HUMAN_EXCEPTION
    assert item["reason_code"] == "STATE_UNKNOWN"


def test_stale_dequeue_cannot_override_a_later_live_queue_entry() -> None:
    item = _plan(
        _fact(
            73,
            operator_queue_intent="DEQUEUED",
            operator_queue_intent_head_sha=SHA_A,
            queue_state="AWAITING_CHECKS",
            queue_entry_provenance="OPERATOR",
        )
    )["items"][0]

    assert item["action"] == HUMAN_EXCEPTION
    assert item["reason_code"] == "STATE_UNKNOWN"


def test_later_same_head_enqueue_supersedes_a_dequeue_event() -> None:
    dequeued = _plan(
        _fact(73, operator_queue_intent="DEQUEUED")
    )["items"][0]
    re_enqueued = _plan(
        _fact(
            73,
            operator_queue_intent="ENQUEUED",
            operator_queue_intent_event_id="queue-event:2",
            queue_state="AWAITING_CHECKS",
            queue_entry_provenance="OPERATOR",
        )
    )["items"][0]

    assert dequeued["action"] == OPERATOR_CANCELLED
    assert dequeued["terminal_for_head"] is False
    assert re_enqueued["action"] == WAIT
    assert re_enqueued["reason_code"] == "IN_NATIVE_QUEUE"


def test_closed_pr_is_neutral_and_not_attributed_to_the_operator() -> None:
    item = _plan(_fact(73, pr_state="CLOSED"))["items"][0]

    assert item["action"] == WAIT
    assert item["reason_code"] == "PR_CLOSED"
    assert item["terminal_for_head"] is False


def test_merged_pr_is_terminal_and_not_repromoted() -> None:
    out = _plan(_fact(73, pr_state="MERGED", merge_provenance="NATIVE_QUEUE"))
    item = out["items"][0]

    assert item["action"] == MERGED
    assert item["reason_code"] == "MERGED_BY_NATIVE_QUEUE"
    assert item["terminal_for_head"] is True
    assert item["terminal_key"]["merge_observation_digest"]
    assert out["operator_inbox"] == []


def test_scalar_native_queue_provenance_without_timeline_proof_fails_closed() -> None:
    item = _plan(
        _fact(
            73,
            pr_state="MERGED",
            merge_provenance="NATIVE_QUEUE",
            merge_observation=None,
        )
    )["items"][0]

    assert item["action"] == HUMAN_EXCEPTION
    assert item["reason_code"] == "STATE_UNKNOWN"


def test_merged_outside_queue_is_not_mislabelled() -> None:
    item = _plan(
        _fact(73, pr_state="MERGED", merge_provenance="DIRECT_OR_UNKNOWN")
    )["items"][0]

    assert item["action"] == HUMAN_EXCEPTION
    assert item["reason_code"] == "MERGED_OUTSIDE_NATIVE_QUEUE"


def test_stale_terminal_fact_fails_closed() -> None:
    item = _plan(
        _fact(
            73,
            pr_state="MERGED",
            merge_provenance="NATIVE_QUEUE",
            head_observed_current=False,
        )
    )["items"][0]

    assert item["action"] == HUMAN_EXCEPTION
    assert item["reason_code"] == "STATE_UNKNOWN"


def test_existing_native_queue_entry_is_wait_even_for_operator_only() -> None:
    item = _plan(
        _fact(
            74,
            queue_state="AWAITING_CHECKS",
            queue_entry_provenance="OPERATOR",
            policy_class="operator_only",
            risk="HIGH",
        )
    )["items"][0]

    assert item["action"] == WAIT
    assert item["reason_code"] == "IN_NATIVE_QUEUE"


def test_unconfigured_trusted_loop_queue_provenance_is_uninhabited() -> None:
    item = _plan(
        _fact(
            74,
            queue_state="AWAITING_CHECKS",
            queue_entry_provenance="TRUSTED_LOOP",
            policy_class="operator_only",
            risk="HIGH",
        )
    )["items"][0]

    assert item["action"] == HUMAN_EXCEPTION
    assert item["reason_code"] == "STATE_UNKNOWN"


def test_transient_ci_is_bounded_then_escalates() -> None:
    retry = _plan(_fact(75, ci_state="transient", repair_attempts=1))["items"][0]
    exhausted = _plan(_fact(75, ci_state="transient", repair_attempts=2))["items"][0]

    assert retry["action"] == RERUN_TRANSIENT
    assert exhausted["action"] == HUMAN_EXCEPTION
    assert exhausted["reason_code"] == "ATTEMPTS_EXHAUSTED"


def test_failed_ci_routes_to_bounded_code_repair() -> None:
    item = _plan(_fact(76, ci_state="failed"))["items"][0]

    assert item["action"] == REPAIR_CODE
    assert item["reason_code"] == "REAL_TEST_OR_LINT_FAILURE"


@pytest.mark.parametrize("ci_state", ["failed", "transient", "missing"])
def test_side_effecting_ci_actions_require_a_stable_base_snapshot(ci_state) -> None:
    item = _plan(
        _fact(
            76,
            ci_state=ci_state,
            behind_by=3,
            base_observed_current=False,
        )
    )["items"][0]

    assert item["action"] == HUMAN_EXCEPTION
    assert item["reason_code"] == "STATE_UNKNOWN"


def test_repairable_review_feedback_routes_to_patch_without_thread_authority() -> None:
    item = _plan(
        _fact(76, unresolved_threads=1, repairable_threads=True)
    )["items"][0]

    assert item["action"] == REPAIR_CODE
    assert item["reason_code"] == "REVIEW_FEEDBACK_REPAIR"
    assert item["authority"]["can_resolve_threads"] is False


def test_unrepairable_or_exhausted_review_feedback_escalates() -> None:
    unrepairable = _plan(_fact(76, unresolved_threads=1))["items"][0]
    exhausted = _plan(
        _fact(
            76,
            unresolved_threads=1,
            repairable_threads=True,
            repair_attempts=2,
        )
    )["items"][0]

    assert unrepairable["action"] == HUMAN_EXCEPTION
    assert unrepairable["reason_code"] == "UNRESOLVED_THREADS"
    assert exhausted["action"] == HUMAN_EXCEPTION
    assert exhausted["reason_code"] == "ATTEMPTS_EXHAUSTED"


def test_stranded_missing_ci_refreshes_only_a_behind_same_repo_head() -> None:
    refresh = _plan(_fact(77, ci_state="missing", behind_by=3))["items"][0]
    current = _plan(_fact(77, ci_state="missing", behind_by=0))["items"][0]

    assert refresh["action"] == REFRESH_STRANDED
    assert current["action"] == HUMAN_EXCEPTION
    assert current["reason_code"] == "CI_NEVER_RAN"


def test_stranded_refresh_is_single_attempt_per_head() -> None:
    item = _plan(
        _fact(77, ci_state="missing", behind_by=3, repair_attempts=1)
    )["items"][0]

    assert item["action"] == HUMAN_EXCEPTION
    assert item["reason_code"] == "REFRESH_ATTEMPT_EXHAUSTED"


def test_missing_ai_evidence_requests_review_before_queue() -> None:
    item = _plan(_fact(78, ai_evidence=False))["items"][0]

    assert item["action"] == REQUEST_REVIEW
    assert item["reason_code"] == "AI_EVIDENCE_REQUIRED"


def test_stale_review_or_warrant_evidence_fails_closed() -> None:
    stale_ai = _plan(_fact(78, ai_evidence_head_sha="e" * 40))["items"][0]
    stale_warrant = _plan(
        _fact(
            78,
            policy_class="code",
            risk="MEDIUM",
            operator_warrant=True,
            operator_warrant_head_sha="e" * 40,
        )
    )["items"][0]

    assert stale_ai["reason_code"] == "STATE_UNKNOWN"
    assert stale_warrant["reason_code"] == "STATE_UNKNOWN"


def test_untrusted_review_warrant_and_queue_actors_fail_closed() -> None:
    untrusted_ai = _plan(
        _fact(78, ai_evidence_actor="lookalike-codex[bot]")
    )["items"][0]
    untrusted_warrant = _plan(
        _fact(
            78,
            policy_class="code",
            risk="MEDIUM",
            operator_warrant=True,
            operator_warrant_actor="attacker",
        )
    )["items"][0]
    untrusted_dequeue = _plan(
        _fact(
            78,
            operator_queue_intent="DEQUEUED",
            operator_queue_intent_actor="github-actions[bot]",
        )
    )["items"][0]

    assert untrusted_ai["reason_code"] == "STATE_UNKNOWN"
    assert untrusted_warrant["reason_code"] == "STATE_UNKNOWN"
    assert untrusted_dequeue["reason_code"] == "STATE_UNKNOWN"


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("repo", "other/repo"),
        ("pr", 999),
        ("head_sha", "e" * 40),
        ("base_sha", "f" * 40),
        ("base_ref", "release"),
        ("policy_sha256", "e" * 64),
        ("intent_sha256", "f" * 64),
        ("authority_class", "code"),
        ("ai_evidence_ids", [999]),
    ],
)
def test_full_authorization_evidence_bindings_are_required(field, value) -> None:
    fact = _fact(78)
    evidence = fact["authorization_report"]["authorization_evidence"]
    evidence[field] = value
    evidence["digest"] = _canonical_digest(
        {key: item for key, item in evidence.items() if key != "digest"}
    )

    item = _plan(fact)["items"][0]

    assert item["action"] == HUMAN_EXCEPTION
    assert item["reason_code"] == "STATE_UNKNOWN"
    assert item["queue_candidate"] is None


def test_authorization_evidence_digest_and_current_title_are_bound() -> None:
    bad_digest = _fact(78)
    bad_digest["authorization_report"]["authorization_evidence"]["digest"] = "f" * 64
    changed_title = _fact(79)
    changed_title["title"] = "new title after the policy check"

    rows = [_plan(bad_digest)["items"][0], _plan(changed_title)["items"][0]]

    assert all(row["reason_code"] == "STATE_UNKNOWN" for row in rows)
    assert all(row["queue_candidate"] is None for row in rows)


def test_draft_sources_must_agree() -> None:
    fact = _fact(78, is_draft=False)
    out = plan_convergence_actions(
        [_pr(78, draft=True)],
        {78: ["docs/safe.md"]},
        {78: fact},
        repo=REPO,
    )

    assert out["items"][0]["reason_code"] == "STATE_UNKNOWN"


def test_unknown_or_moved_state_fails_closed() -> None:
    malformed = _fact(79)
    malformed.pop("review_state")
    unknown = _plan(malformed)["items"][0]
    moved = _plan(_fact(79, head_observed_current=False))["items"][0]

    assert unknown["action"] == HUMAN_EXCEPTION
    assert unknown["reason_code"] == "STATE_UNKNOWN"
    assert moved["action"] == HUMAN_EXCEPTION
    assert moved["reason_code"] == "STATE_UNKNOWN"


def test_integer_sha_and_stale_queue_entry_fail_closed() -> None:
    integer_sha = _plan(_fact(79, head_sha=int("1" * 40)))["items"][0]
    stale_queue = _plan(
        _fact(
            79,
            queue_state="AWAITING_CHECKS",
            queue_entry_provenance="OPERATOR",
            queue_entry_head_sha="e" * 40,
        )
    )["items"][0]

    assert integer_sha["reason_code"] == "STATE_UNKNOWN"
    assert stale_queue["reason_code"] == "STATE_UNKNOWN"


def test_changed_files_and_trusted_path_policy_are_fail_closed() -> None:
    empty = _plan(_fact(79), files={79: []})["items"][0]
    lied_about_code = _plan(
        _fact(79, policy_class="docs_low"),
        files={79: ["dharma_swarm/telos_gates.py"]},
    )["items"][0]
    incomplete_collision_scan = _plan(
        _fact(79), owned_surfaces_complete=False
    )["items"][0]

    assert empty["reason_code"] == "STATE_UNKNOWN"
    assert lied_about_code["reason_code"] == "STATE_UNKNOWN"
    assert incomplete_collision_scan["reason_code"] == "STATE_UNKNOWN"


def test_trusted_owner_registry_cannot_be_omitted_by_the_caller() -> None:
    facts = [
        _fact(79, policy_class="code", risk="MEDIUM", operator_warrant=True),
        _fact(80, policy_class="code", risk="MEDIUM", operator_warrant=True),
    ]
    files = {
        79: ["dharma_swarm/coordination/a.py"],
        80: ["dharma_swarm/coordination/b.py"],
    }

    out = _plan(*facts, files=files)

    assert out["owned_surface_policy"]["sha256"] == TRUSTED_OWNED_SURFACES_SHA256
    assert set(out["order"]["escalate"]) == {79, 80}
    assert all(row["action"] == HUMAN_EXCEPTION for row in out["items"])


def test_malformed_snapshot_number_fails_closed_instead_of_raising() -> None:
    fact = _fact(79)
    fact["number"] = "not-a-number"

    item = plan_convergence_actions(
        [_pr(79)],
        {79: ["docs/safe.md"]},
        {79: fact},
        repo=REPO,
    )["items"][0]

    assert item["action"] == HUMAN_EXCEPTION
    assert item["reason_code"] == "STATE_UNKNOWN"


def test_ambiguous_overlap_is_never_queueable_and_inbox_is_capped() -> None:
    facts = [
        _fact(number, policy_class="operator_only", risk="HIGH")
        for number in range(80, 87)
    ]
    files = {number: ["docs/governance/shared.md"] for number in range(80, 87)}
    out = _plan(*facts, files=files, max_operator_items=5)

    assert all(row["action"] == HUMAN_EXCEPTION for row in out["items"])
    assert all(row["reason_code"] == "AMBIGUOUS_OVERLAP" for row in out["items"])
    assert len(out["operator_inbox"]) == 5
    assert out["operator_inbox_overflow"] == 2


def test_plan_from_payload_normalizes_json_object_keys() -> None:
    payload = {
        "repo": REPO,
        "open_prs": [_pr(90)],
        "pr_files": {"90": ["docs/safe.md"]},
        "facts": {"90": _fact(90)},
        "grades": {"90": 4},
        "owned_surfaces_complete": True,
    }

    out = plan_from_payload(payload)

    assert out["items"][0]["action"] == QUEUE_CANDIDATE
    assert out["order"]["order"] == [90]


def test_snapshot_cli_emits_machine_readable_plan(tmp_path, capsys) -> None:
    payload = {
        "repo": REPO,
        "open_prs": [_pr(90)],
        "pr_files": {"90": ["docs/safe.md"]},
        "facts": {"90": _fact(90)},
        "owned_surfaces_complete": True,
    }
    snapshot = tmp_path / "snapshot.json"
    snapshot.write_text(json.dumps(payload), encoding="utf-8")

    assert main(["--snapshot-json", str(snapshot)]) == 0

    emitted = json.loads(capsys.readouterr().out)
    assert emitted["schema"] == PLAN_SCHEMA
    assert emitted["items"][0]["action"] == QUEUE_CANDIDATE


def test_non_object_snapshot_root_is_rejected_cleanly() -> None:
    with pytest.raises(ValueError, match="root must be an object"):
        plan_from_payload([])  # type: ignore[arg-type]


@pytest.mark.parametrize("grade", [-1, 9])
def test_evidence_grades_are_bounded_to_the_rigor_ladder(grade) -> None:
    payload = {
        "repo": REPO,
        "open_prs": [_pr(90)],
        "pr_files": {"90": ["docs/safe.md"]},
        "facts": {"90": _fact(90)},
        "grades": {"90": grade},
        "owned_surfaces_complete": True,
    }

    with pytest.raises(ValueError, match="0 to 8"):
        plan_from_payload(payload)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("pr_files", {}),
        ("facts", {"090": _fact(90)}),
        ("max_operator_items", True),
        ("max_operator_items", 6),
    ],
)
def test_snapshot_shape_mismatch_fails_closed_at_the_boundary(field, value) -> None:
    payload = {
        "repo": REPO,
        "open_prs": [_pr(90)],
        "pr_files": {"90": ["docs/safe.md"]},
        "facts": {"90": _fact(90)},
        "owned_surfaces_complete": True,
    }
    payload[field] = value

    with pytest.raises(ValueError):
        plan_from_payload(payload)
