"""Arena v1 tests (spec §3, §10a): budget parity logged for candidate + controls;
candidate cannot read sealed labels; closeout-state selection; replayable scorer;
contaminated input -> quarantine; frozen-slice boundary."""

from __future__ import annotations

import json

import pytest

from dharma_swarm.coordination.arena import ArenaRunner, Taskpack
from dharma_swarm.coordination.arena.curator import TaskCurator
from dharma_swarm.coordination.arena.runner import CLOSEOUT_STATES, render_decision_packet
from dharma_swarm.coordination.arena.scorer import (
    score_submission,
    scorecard_hash,
    scorer_hash,
)
from dharma_swarm.coordination.genome import OrchestrationGenome


def _router_genome() -> OrchestrationGenome:
    """All three specialists + route-by-family: should beat best-single at parity."""
    return OrchestrationGenome(
        roster=[
            {"role_id": "r1", "member_id": "alpha-math", "kind": "model"},
            {"role_id": "r2", "member_id": "beta-code", "kind": "model"},
            {"role_id": "r3", "member_id": "gamma-logic", "kind": "model"},
        ],
        adjudication_rule="synthesize",
    )


def _single_genome(model_id: str = "alpha-math") -> OrchestrationGenome:
    return OrchestrationGenome(
        roster=[{"role_id": "r1", "member_id": model_id, "kind": "model"}],
        adjudication_rule="single",
    )


def test_positive_lift_candidate_beats_best_single_at_parity():
    run = ArenaRunner().run(_router_genome())
    assert run["closeout_state"] == "positive_lift_candidate"
    assert run["arm_scores"]["candidate"] > run["arm_scores"]["best_single_full_budget"]
    assert run["budget_parity"]["candidate"]["within_parity"] is True
    assert run["significance"]["significant"] is True
    assert run["council_verdict"] == "corroborated"


def test_budget_parity_logged_for_candidate_and_every_control():
    run = ArenaRunner().run(_router_genome())
    bp = run["budget_parity"]
    for arm in (
        "candidate",
        "best_single_full_budget",
        "same_budget_self_moa",
        "random_or_static_ensemble",
    ):
        assert arm in bp
        assert "total_compute" in bp[arm]
        assert "within_parity" in bp[arm]
        assert bp[arm]["budget_ref"] == run["budget_ref"]


def test_measured_negative_for_degenerate_single_genome():
    # A single-model genome cannot beat the best single model -> no honest lift.
    run = ArenaRunner().run(_single_genome("gamma-logic"))
    assert run["closeout_state"] == "measured_negative"
    assert run["arm_scores"]["candidate"] <= run["arm_scores"]["best_single_full_budget"]


def test_overspending_ensemble_is_not_a_pass():
    """Beating best-single by spending MORE than parity is theater (spec §3)."""
    run = ArenaRunner().run(
        OrchestrationGenome(
            roster=[
                {"role_id": "r1", "member_id": "alpha-math", "kind": "model"},
                {"role_id": "r2", "member_id": "beta-code", "kind": "model"},
                {"role_id": "r3", "member_id": "gamma-logic", "kind": "model"},
            ],
            adjudication_rule="vote",  # all 3 vote on every task -> 3x compute
        )
    )
    assert run["budget_parity"]["candidate"]["within_parity"] is False
    assert run["closeout_state"] != "positive_lift_candidate"


def test_contaminated_candidate_quarantined():
    """A candidate that reads sealed labels trips the tripwire -> quarantine."""
    cheater = OrchestrationGenome(
        roster=[{"role_id": "r1", "member_id": "alpha-math", "kind": "model"}],
        adjudication_rule="single",
        permissions={"r1": ["read_sealed_labels"]},
    )
    run = ArenaRunner().run(cheater)
    assert run["contaminated"] is True
    assert run["council_verdict"] == "quarantined"
    assert run["closeout_state"] == "contaminated_quarantine"


def test_clean_candidate_never_reads_sealed_labels():
    """The candidate worker path must not touch sealed labels — only the scorer."""
    tp = Taskpack()
    runner = ArenaRunner(taskpack=tp)
    cand = runner.run_arm("candidate", _router_genome())
    # The candidate WORKER path (dispatch + aggregation) reads zero sealed labels.
    assert cand.sealed_access_during_run == 0
    # The scorer (the sole correctness authority) is the ONLY reader of labels —
    # exactly one read per scored task, and never from the worker path.
    assert len(tp.sealed_access_log) == len(tp.task_ids())


def test_scorer_is_replayable():
    tp = Taskpack()
    submission = {tid: "x" for tid in tp.task_ids()}
    s1 = score_submission(tp, submission, arm="candidate")
    s2 = score_submission(tp, submission, arm="candidate")
    assert scorecard_hash(s1) == scorecard_hash(s2)
    assert scorer_hash() == scorer_hash()


def test_full_run_replayable():
    r1 = ArenaRunner().run(_router_genome())
    r2 = ArenaRunner().run(_router_genome())
    assert r1["scorecard_hash"] == r2["scorecard_hash"]
    assert r1["closeout_state"] == r2["closeout_state"]
    assert r1["significance"] == r2["significance"]


def test_outputs_written(tmp_path):
    run = ArenaRunner().run(_router_genome(), output_dir=tmp_path)
    expected = [
        "arena_run.json",
        "scorecard.json",
        "trace_receipts.jsonl",
        "route_receipts.jsonl",
        "council_receipts.jsonl",
        "power_index.json",
        "decision_packet.md",
    ]
    for name in expected:
        assert (tmp_path / name).exists(), f"missing output {name}"
    # arena_run.json is valid + carries the frozen hashes
    run_json = json.loads((tmp_path / "arena_run.json").read_text())
    assert run_json["closeout_state"] in CLOSEOUT_STATES
    assert run_json["scorer_hash"]
    assert run_json["task_manifest_hash"]
    packet = (tmp_path / "decision_packet.md").read_text()
    assert "Decision Packet" in packet
    assert "best_single_full_budget" in packet


def test_closeout_state_is_always_valid():
    for g in (_router_genome(), _single_genome("alpha-math")):
        assert ArenaRunner().run(g)["closeout_state"] in CLOSEOUT_STATES


def test_decision_packet_renders_gate_result():
    run = ArenaRunner().run(_router_genome())
    packet = render_decision_packet(run, run["_power_index"])
    assert "Best-single gate" in packet
    assert "POSITIVE LIFT" in packet


def test_frozen_slice_boundary_holds():
    tp = Taskpack()
    curator = TaskCurator(tp)
    from dharma_swarm.coordination.arena.taskpack import ArenaTask

    curator.propose(ArenaTask("new1", "math", "Compute 2+2.", "4"))
    # curator pool grows, frozen slice stays byte-stable
    assert len(curator.candidate_pool) == 1
    curator.assert_frozen_slice_intact()
    assert len(tp.tasks) == 24


def test_non_corroborating_council_blocks_promotion():
    """A high-scoring candidate must NOT be promoted if the Council does not
    corroborate it (Codex P2 — require corroboration before promotion)."""
    from dharma_swarm.council import Council, CouncilReceipt

    class RefutingCouncil(Council):
        def verify_orchestration_trace(self, request):
            base = super().verify_orchestration_trace(request)
            if base.quarantined:
                return base
            return CouncilReceipt(
                profile=base.profile,
                genome_id=base.genome_id,
                verdict="insufficient",
                inputs_hash=base.inputs_hash,
                evaluator_families=base.evaluator_families,
                source_families=base.source_families,
                findings=base.findings,
                quarantined=False,
            )

    run = ArenaRunner(council=RefutingCouncil()).run(_router_genome())
    assert run["council_verdict"] == "insufficient"
    assert run["closeout_state"] == "blocked_with_evidence"


def test_sealed_oracle_hash_detects_label_drift():
    """task_manifest_hash omits labels (candidates never see them), so a sealed
    answer changing under an unchanged prompt is invisible to it — the
    sealed_oracle_hash catches it (Codex P2 fix)."""
    from dharma_swarm.coordination.arena.taskpack import ArenaTask

    tp = Taskpack()
    base_manifest = tp.task_manifest_hash()
    base_oracle = tp.sealed_oracle_hash()
    drifted_tasks = list(tp.tasks)
    t0 = drifted_tasks[0]
    drifted_tasks[0] = ArenaTask(t0.task_id, t0.family, t0.prompt, "DRIFTED")
    drifted = Taskpack(tasks=tuple(drifted_tasks))
    assert drifted.task_manifest_hash() == base_manifest  # prompt unchanged
    assert drifted.sealed_oracle_hash() != base_oracle  # label drift caught
    assert "DRIFTED" not in drifted.sealed_oracle_hash()  # never leaks a label


def test_curator_next_epoch_is_a_documented_seam():
    with pytest.raises(NotImplementedError, match="throat"):
        TaskCurator(Taskpack()).promote_next_epoch()
