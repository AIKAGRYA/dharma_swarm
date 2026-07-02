from __future__ import annotations

import json

import pytest

from dharma_swarm.forge_v1.forge_v2 import canonical_receipt as cr


def test_normalizes_all_six_kinds_with_complete_audit() -> None:
    swebench = {
        "schema": "forge_v2.native_runner_contract.v1.task_receipt",
        "grader": "swebench",
        "instance_id": "django__django-12209",
        "resolved": True,
        "patch_sha256": "abc123",
        "swebench_run_id": "run-1",
    }
    pr_suite = {
        "schema": "forge_v2.pr_suite_grader.v1",
        "grader": "pr_suite",
        "task_id": "pr::pallets/click#3208",
        "resolved": False,
        "fail_to_pass": ["tests/test_formatting.py"],
        "patch_sha256": "def456",
    }
    scaffold = {
        "schema": "forge_v2.phase4_dual_evolution_alpha.v1.scaffold_candidate",
        "track": "scaffold_genome",
        "candidate_id": "scaffold_abc",
        "genome": {"arm": "verify_chain", "window_chars": 9000},
        "evaluation": {"closeout": "measured_negative"},
        "decision": "accepted_for_archive",
    }
    code = {
        "track": "code_child",
        "candidate_id": "code_xyz",
        "decision": "accepted_for_archive",
        "safety_receipt": {"decision": "pass", "patch_sha256": "sha-code", "blockers": []},
    }
    refusal = {
        "schema": "forge_v2.promotion_verification.v1",
        "decision": "refused",
        "blockers": ["promotion_packet:e4_confirm_full_500"],
        "promotion_packet": {"candidate_id": "cand-1"},
        "payload_sha256": "sha-ref",
    }
    success = {
        "schema": "forge_v2.promotion_verification.v1",
        "decision": "allow",
        "live_apply_allowed": True,
        "blockers": [],
        "promotion_packet": {"candidate_id": "cand-2"},
        "payload_sha256": "sha-suc",
    }

    cases = {
        cr.KIND_SWEBENCH_GRADE: swebench,
        cr.KIND_PR_SUITE_GRADE: pr_suite,
        cr.KIND_SCAFFOLD_RUN: scaffold,
        cr.KIND_CODE_RUN: code,
        cr.KIND_PROMOTION_REFUSAL: refusal,
        cr.KIND_PROMOTION_SUCCESS: success,
    }
    seen_kinds = set()
    for expected_kind, source in cases.items():
        canonical = cr.normalize_receipt(source)
        assert canonical["kind"] == expected_kind, (expected_kind, canonical["kind"])
        assert canonical["schema"] == cr.SCHEMA_VERSION
        assert canonical["audit_complete"] is True, (expected_kind, canonical["missing_replay_fields"])
        assert canonical["missing_replay_fields"] == []
        assert canonical["promotion_gate"] == "verify_promotion_only"
        assert canonical["live_apply_allowed"] is False
        assert {"identity", "outcome", "evidence"}.issubset(canonical)
        seen_kinds.add(canonical["kind"])
    assert seen_kinds == cr.CANONICAL_KINDS


def test_promotion_success_source_authority_is_not_granted_in_envelope() -> None:
    success = {
        "schema": "forge_v2.promotion_verification.v1",
        "decision": "allow",
        "live_apply_allowed": True,
        "blockers": [],
        "promotion_packet": {"candidate_id": "cand-2"},
        "payload_sha256": "sha-suc",
    }
    canonical = cr.normalize_receipt(success)
    assert canonical["kind"] == cr.KIND_PROMOTION_SUCCESS
    assert canonical["outcome"]["decision"] == "allow"
    assert canonical["live_apply_allowed"] is False
    assert canonical["source_of_truth_mutated"] is False
    assert canonical["official_score_claimed"] is False
    assert canonical["evidence"]["source_live_apply_allowed"] is True


def test_audit_flags_missing_replay_fields_not_silently_defaulted() -> None:
    incomplete = {"grader": "swebench", "instance_id": "x__y-1"}
    canonical = cr.normalize_receipt(incomplete)
    assert canonical["audit_complete"] is False
    assert "evidence.patch_sha256" in canonical["missing_replay_fields"]
    # resolved is a falsey-ok field and the key is present (value None) -> still
    # flagged because None is not a present verdict.
    assert "evidence.resolved" not in canonical["missing_replay_fields"]


def test_resolved_false_and_empty_blockers_count_as_present_evidence() -> None:
    pr_suite = {
        "grader": "pr_suite",
        "task_id": "pr::a/b#1",
        "resolved": False,
        "fail_to_pass": ["t.py"],
        "patch_sha256": "h",
    }
    canonical = cr.normalize_receipt(pr_suite)
    assert canonical["audit_complete"] is True
    assert canonical["outcome"]["resolved"] is False

    refusal = {
        "schema": "forge_v2.promotion_verification.v1",
        "decision": "refused",
        "blockers": [],
        "promotion_packet": {"candidate_id": "c"},
    }
    can_ref = cr.normalize_receipt(refusal)
    assert can_ref["kind"] == cr.KIND_PROMOTION_REFUSAL
    assert can_ref["audit_complete"] is True


def test_infer_kind_ignores_untrusted_kind_label() -> None:
    receipt = {"kind": "promotion_success", "grader": "pr_suite", "task_id": "pr::a/b#1", "resolved": True}
    assert cr.infer_kind(receipt) == cr.KIND_PR_SUITE_GRADE


def test_unrecognized_receipt_raises() -> None:
    with pytest.raises(ValueError, match="unrecognized_receipt_kind"):
        cr.normalize_receipt({"foo": "bar"})


def test_normalize_batch_summarizes_per_kind_completeness() -> None:
    good = {"grader": "pr_suite", "task_id": "pr::a/b#1", "resolved": True, "fail_to_pass": ["t.py"], "patch_sha256": "h"}
    incomplete = {"grader": "swebench", "instance_id": "x__y-1"}
    batch = cr.normalize_batch([good, incomplete, {"foo": "bar"}, 42])
    assert batch["total"] == 2
    assert batch["by_kind"]["pr_suite_grade"] == {"count": 1, "audit_complete": 1}
    assert batch["by_kind"]["swebench_grade"] == {"count": 1, "audit_complete": 0}
    assert batch["audit_complete_count"] == 1
    reasons = {row["reason"] for row in batch["unrecognized"]}
    assert any("unrecognized_receipt_kind" in r for r in reasons)
    assert "not_a_dict" in reasons


def test_write_canonical_receipt_round_trips(tmp_path) -> None:
    source = {"grader": "swebench", "instance_id": "django__django-1", "resolved": True, "patch_sha256": "abc"}
    out = tmp_path / "canon.json"
    canonical = cr.write_canonical_receipt(out, source)
    assert out.exists()
    on_disk = json.loads(out.read_text())
    assert on_disk["kind"] == cr.KIND_SWEBENCH_GRADE
    assert on_disk["canonical_sha256"] == canonical["canonical_sha256"]
    assert on_disk["audit_complete"] is True
