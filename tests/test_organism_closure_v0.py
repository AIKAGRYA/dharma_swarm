"""Organism Closure v0 — single proof test.

The closure proof: replaying the loop with success-evidence vs failure-evidence
yields different NextDecision rows. Specifically, chosen_packet_id and reason
differ. That difference IS the proof.

All four pure functions (record_evidence_receipt, project_vsm, kaizen_link,
decide_next) plus contract validators are exercised. Module-private; nothing
imports closure_v0 outside this file.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from dharma_swarm.operator_core.closure_v0 import (
    ClosureContractError,
    DarwinProposalCandidate,
    EvidenceInconsistentError,
    EvidenceReceipt,
    KaizenReviewLink,
    NextDecision,
    TelosObjective,
    VSMProjection,
    VentureCellRef,
    WorkPacket,
    decide_next,
    kaizen_link,
    load_fixture,
    project_vsm,
    record_evidence_receipt,
    to_jsonable,
    validate_darwin_candidate,
    write_json,
)
from dharma_swarm.operator_core.operating_facts import (
    AgentOpsRunFact,
    OperatingFactBundle,
)

FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures" / "organism_closure_v0"
CORRELATION_ID = "corr_v0_test_001"
CREATED_AT = "2026-05-08T00:00:00+00:00"
CAPTURED_AT = "2026-05-08T00:00:01+00:00"
DECIDED_AT = "2026-05-08T00:00:02+00:00"
EXPIRES_AT = "2026-05-08T01:00:00+00:00"


def _load_packet() -> WorkPacket:
    raw = load_fixture("fixture_work_packet.json")
    return WorkPacket(
        packet_id=raw["packet_id"],
        correlation_id=raw["correlation_id"],
        title=raw["title"],
        allowed_paths=tuple(raw["allowed_paths"]),
        acceptance_test=raw["acceptance_test"],
        rollback_plan=raw["rollback_plan"],
        objective_id=raw["objective_id"],
        cell_id=raw["cell_id"],
        forbidden_paths=tuple(raw["forbidden_paths"]),
        review_tier=raw["review_tier"],
    )


def _load_agentops(name: str) -> AgentOpsRunFact:
    raw = load_fixture(name)
    return AgentOpsRunFact(
        source_path=raw["source_path"],
        job_id=raw["job_id"],
        status=raw["status"],
        branch=raw["branch"],
        worktree=raw["worktree"],
        gate_state=raw["gate_state"],
        scope_state=raw["scope_state"],
        commit_state=raw["commit_state"],
        approval_state=raw["approval_state"],
        changed_files=tuple(raw["changed_files"]),
        scope_violations=tuple(raw["scope_violations"]),
        failed_gates=tuple(raw["failed_gates"]),
        commit_hash=raw["commit_hash"],
    )


def _empty_bundle() -> OperatingFactBundle:
    raw = load_fixture("fixture_operating_bundle.json")
    return OperatingFactBundle(missing_sources=tuple(raw["missing_sources"]))


def _run_loop(variant: str, *, truth_stale_override: bool = False):
    """Run the four-step closure loop. Returns (evidence, vsm, kaizen, decision)."""
    packet = _load_packet()
    agentops = _load_agentops(f"fixture_agentops_{variant}.json")
    bundle = _empty_bundle()

    evidence = record_evidence_receipt(
        packet, agentops,
        correlation_id=CORRELATION_ID,
        created_at=CREATED_AT,
        duration_ms=1234.5,
    )
    vsm = project_vsm(
        bundle, evidence,
        correlation_id=CORRELATION_ID,
        captured_at=CAPTURED_AT,
        recognition_seed_age_hours=72.0 if truth_stale_override else 2.0,
        algedonic_unique_values_last_200=1 if truth_stale_override else 5,
        kernel_signature_match=not truth_stale_override,
    )
    review = kaizen_link(evidence)
    decision = decide_next(
        vsm, [packet], review,
        decided_at=DECIDED_AT, expires_at=EXPIRES_AT,
    )
    return evidence, vsm, review, decision


# ---------------------------------------------------------------------------
# T1–T2 — EvidenceReceipt invariants
# ---------------------------------------------------------------------------

def test_t1_evidence_inconsistent_success_with_failing_exit() -> None:
    with pytest.raises(EvidenceInconsistentError):
        EvidenceReceipt(
            receipt_id="ev_x", correlation_id=CORRELATION_ID,
            work_packet_id="wp_x", agentops_source="src",
            test_exit_code=1, files_changed=(), duration_ms=0.0,
            replay_command="pytest x", success=True, created_at=CREATED_AT,
        )


def test_t2_evidence_requires_correlation_and_replay() -> None:
    with pytest.raises(ClosureContractError):
        EvidenceReceipt(
            receipt_id="ev_x", correlation_id="",
            work_packet_id="wp_x", agentops_source="src",
            test_exit_code=0, files_changed=(), duration_ms=0.0,
            replay_command="pytest x", success=True, created_at=CREATED_AT,
        )
    with pytest.raises(ClosureContractError):
        EvidenceReceipt(
            receipt_id="ev_x", correlation_id=CORRELATION_ID,
            work_packet_id="wp_x", agentops_source="src",
            test_exit_code=0, files_changed=(), duration_ms=0.0,
            replay_command="", success=True, created_at=CREATED_AT,
        )


# ---------------------------------------------------------------------------
# T3–T4 — VSMProjection truth_stale gate
# ---------------------------------------------------------------------------

def test_t3_vsm_flags_truth_stale_when_seed_old() -> None:
    _, vsm, _, _ = _run_loop("success", truth_stale_override=True)
    assert vsm.truth_stale is True
    assert vsm.s4_recognition_seed_age_hours == 72.0


def test_t4_vsm_fresh_when_inputs_fresh() -> None:
    _, vsm, _, _ = _run_loop("success")
    assert vsm.truth_stale is False
    assert vsm.s4_recognition_seed_age_hours == 2.0


# ---------------------------------------------------------------------------
# T5 — KaizenReviewLink shape
# ---------------------------------------------------------------------------

def test_t5_kaizen_link_recommends_promote_on_success() -> None:
    _, _, review, _ = _run_loop("success")
    assert "Promote" in review.next_recommendation
    assert review.has_human_yds is False


# ---------------------------------------------------------------------------
# T6–T7 — decide_next branches
# ---------------------------------------------------------------------------

def test_t6_decide_next_chooses_packet_on_success() -> None:
    _, _, _, dec = _run_loop("success")
    assert dec.chosen_packet_id == "wp_v0_test_001"
    assert "evidence_accepted" in dec.reason
    assert dec.confidence == pytest.approx(0.7)


def test_t7_decide_next_holds_on_failure() -> None:
    _, _, _, dec = _run_loop("failure")
    assert dec.chosen_packet_id is None
    assert "evidence_failed" in dec.reason


def test_t7b_decide_next_blocks_on_truth_stale() -> None:
    _, _, _, dec = _run_loop("success", truth_stale_override=True)
    assert dec.chosen_packet_id is None
    assert "truth_stale" in dec.reason
    assert dec.confidence == 0.0


# ---------------------------------------------------------------------------
# T8 — THE CLOSURE PROOF
# ---------------------------------------------------------------------------

def test_t8_closure_proof_success_differs_from_failure() -> None:
    _, _, _, success = _run_loop("success")
    _, _, _, failure = _run_loop("failure")
    assert success != failure
    assert success.chosen_packet_id != failure.chosen_packet_id
    assert success.reason != failure.reason
    # Cross-check: identical correlation + decided_at hash (not timing) means
    # the only thing that flipped is the evidence path. That IS the proof.


# ---------------------------------------------------------------------------
# T9 — Replay determinism
# ---------------------------------------------------------------------------

def test_t9_replay_determinism() -> None:
    a = _run_loop("success")
    b = _run_loop("success")
    for x, y in zip(a, b):
        assert x == y


# ---------------------------------------------------------------------------
# T10–T11 — DarwinProposalCandidate validation
# ---------------------------------------------------------------------------

def test_t10_darwin_candidate_rejects_empty_evidence_refs() -> None:
    cand = DarwinProposalCandidate(
        candidate_id="dc_x", correlation_id=CORRELATION_ID,
        component="dharma_swarm/operator_core/closure_v0.py",
        description="trivial",
    )
    ok, failures = validate_darwin_candidate(cand)
    assert ok is False
    assert "evidence_missing" in failures
    assert "kaizen_review_missing" in failures


def test_t11_darwin_candidate_accepted_when_refs_present() -> None:
    cand = DarwinProposalCandidate(
        candidate_id="dc_x", correlation_id=CORRELATION_ID,
        component="dharma_swarm/operator_core/closure_v0.py",
        description="evidence-backed",
        evidence_refs=("ev_xyz",),
        kaizen_review_refs=("kz_xyz",),
    )
    ok, failures = validate_darwin_candidate(cand)
    assert ok is True
    assert failures == []


# ---------------------------------------------------------------------------
# T12 — Frozen-fixture regression lock
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "variant,evidence_file,vsm_file,kaizen_file,decision_file",
    [
        ("success",
         "expected_evidence_success.json",
         "expected_vsm_success.json",
         "expected_kaizen_success.json",
         "expected_next_decision_success.json"),
        ("failure",
         "expected_evidence_failure.json",
         "expected_vsm_failure.json",
         "expected_kaizen_failure.json",
         "expected_next_decision_failure.json"),
    ],
)
def test_t12_frozen_fixtures_match(
    variant: str, evidence_file: str, vsm_file: str,
    kaizen_file: str, decision_file: str,
) -> None:
    evidence, vsm, review, decision = _run_loop(variant)
    expected_ev = load_fixture(evidence_file)
    expected_vsm = load_fixture(vsm_file)
    expected_kz = load_fixture(kaizen_file)
    expected_nd = load_fixture(decision_file)
    assert to_jsonable(evidence) == expected_ev
    assert to_jsonable(vsm) == expected_vsm
    assert to_jsonable(review) == expected_kz
    assert to_jsonable(decision) == expected_nd


# ---------------------------------------------------------------------------
# Closure-proof one-liner used by replay.sh
# ---------------------------------------------------------------------------

def test_t13_expected_decision_files_differ_on_disk() -> None:
    a = json.loads((FIXTURE_DIR / "expected_next_decision_success.json").read_text())
    b = json.loads((FIXTURE_DIR / "expected_next_decision_failure.json").read_text())
    assert a != b
    assert a["chosen_packet_id"] != b["chosen_packet_id"]
    assert a["reason"] != b["reason"]


# ---------------------------------------------------------------------------
# WorkPacket / TelosObjective / VentureCellRef sanity
# ---------------------------------------------------------------------------

def test_t14_work_packet_rejects_overlap_and_bad_review_tier() -> None:
    base = dict(
        packet_id="wp", correlation_id=CORRELATION_ID, title="t",
        allowed_paths=("a.py",), acceptance_test="tests/test_x.py",
        rollback_plan="git checkout HEAD -- a.py",
    )
    with pytest.raises(ClosureContractError):
        WorkPacket(**base, forbidden_paths=("a.py",))
    with pytest.raises(ClosureContractError):
        WorkPacket(**base, review_tier="banana")


def test_t15_stub_telos_and_venture_defaults() -> None:
    assert TelosObjective().objective_id == "jagat_kalyan"
    assert VentureCellRef().cell_id == ""


# ---------------------------------------------------------------------------
# write_json round-trip (atomic)
# ---------------------------------------------------------------------------

def test_t16_write_json_atomic_round_trip(tmp_path: Path) -> None:
    target = tmp_path / "sub" / "out.json"
    payload = {"k": [1, 2, ("x", "y")]}
    write_json(target, payload)
    assert json.loads(target.read_text()) == {"k": [1, 2, ["x", "y"]]}
