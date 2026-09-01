from __future__ import annotations

from types import SimpleNamespace

from dharma_swarm.forge_lab import grade_explore
from dharma_swarm.forge_lab.genome_spec import check_genome, merged_with_defaults


class _Budget:
    def __init__(self, cap_tokens: int, cap_usd: float):
        self.cap_tokens = cap_tokens
        self.cap_usd = cap_usd
        self.spent = 0
        self.invalid = False
        self.invalid_reason = None

    def charge(self, _component: str, tokens: int, **_kwargs: object) -> int:
        self.spent += int(tokens)
        return self.spent

    def to_dict(self) -> dict[str, object]:
        return {"spent_tokens": self.spent, "invalid": False}


def _seams(
    grade_result: grade_explore.GraderResult | tuple[bool, float, str | None],
    *,
    patch: str = "diff",
) -> grade_explore.GradeSeams:
    return grade_explore.GradeSeams(
        slot_for_id=lambda model_id: SimpleNamespace(model_id=model_id),
        propose_slot=lambda *_args, **_kwargs: {"patch": patch, "tokens": 10},
        self_moa_arm=lambda *_args, **_kwargs: {"final_patch": "diff"},
        verify_chain_arm=lambda *_args, **_kwargs: {"final_patch": "diff"},
        mixed_moa_arm=lambda *_args, **_kwargs: {"final_patch": "diff"},
        grade_task=lambda *_args, **_kwargs: grade_result,
        budget_factory=_Budget,
    )


def _grade(
    result: grade_explore.GraderResult | tuple[bool, float, str | None],
    *,
    patch: str = "diff",
) -> grade_explore.GradeOutcome:
    return grade_explore.grade_genome_explore(
        {
            "arm_kind": "freeform_single",
            "generator_model": "offline-fixture",
            "per_call_tokens": 10,
            "window_chars": 100,
        },
        {"task-1": ({"instance_id": "task-1"}, {"f.py": "x"})},
        seams=_seams(result, patch=patch),
        budget_cap_tokens=100,
        budget_cap_usd=0.0,
    )


def test_infrastructure_failure_is_not_measured_negative() -> None:
    outcome = _grade(
        grade_explore.GraderResult.infrastructure("isolated_grader_unavailable")
    )
    assert outcome.evidence_class == grade_explore.INCONCLUSIVE_INFRASTRUCTURE
    assert outcome.comparable_observations == 0
    assert outcome.pass_rate == 0.0
    assert outcome.per_task[0]["evidence_class"] == (
        grade_explore.INCONCLUSIVE_INFRASTRUCTURE
    )
    assert outcome.budget["inconclusive_infrastructure_observations"] == 1


def test_real_false_verdict_is_measured_negative() -> None:
    outcome = _grade(grade_explore.GraderResult.executed_verdict(False, 1.0))
    assert outcome.evidence_class == grade_explore.MEASURED_NEGATIVE
    assert outcome.comparable_observations == 1
    assert outcome.pass_rate == 0.0
    assert outcome.per_task[0]["evidence_class"] == grade_explore.MEASURED_NEGATIVE


def test_empty_model_patch_is_noncomparable_generation_not_negative() -> None:
    outcome = _grade(
        grade_explore.GraderResult.executed_verdict(False, 0.0),
        patch="",
    )
    assert outcome.evidence_class == grade_explore.INCONCLUSIVE_GENERATION
    assert outcome.comparable_observations == 0
    assert outcome.per_task[0]["error"] == "empty_patch"


def test_verify_chain_executes_mutation_gene_and_preserves_empty_evidence() -> None:
    observed: dict[str, object] = {}
    execution_evidence = {
        "schema": "rsi_lab.execution_evidence.v1",
        "arm": "verify_chain",
        "generator_input": {
            "schema": "rsi_lab.execution_input_receipt.v1",
            "mutation_gene_applied": True,
            "counterfactual_prompt_digest": "sha256:" + "1" * 64,
            "executed_prompt_digest": "sha256:" + "2" * 64,
            "mutation_gene_digest": "sha256:" + "3" * 64,
        },
        "generator_empty_patch": True,
        "verifier_called": True,
        "verifier_empty_patch": True,
        "final_patch_empty": True,
    }

    def verify_chain(*_args, **kwargs):
        observed.update(kwargs)
        return {
            "final_patch": "",
            "execution_evidence": {
                key: value
                for key, value in execution_evidence.items()
                if key not in {"schema", "arm"}
            },
        }

    seams = grade_explore.GradeSeams(
        slot_for_id=lambda model_id: SimpleNamespace(model_id=model_id),
        propose_slot=lambda *_args, **_kwargs: {"patch": "", "tokens": 0},
        self_moa_arm=lambda *_args, **_kwargs: {"final_patch": ""},
        verify_chain_arm=verify_chain,
        mixed_moa_arm=lambda *_args, **_kwargs: {"final_patch": ""},
        grade_task=lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("empty patch must not reach the evaluator")
        ),
        budget_factory=_Budget,
    )
    genome = merged_with_defaults(
        {
            "arm_kind": "verify_chain",
            "generator_model": "generator",
            "verifier_model": "verifier",
            "extra_instruction": "EXECUTE THIS GENE",
        }
    )

    outcome = grade_explore.grade_genome_explore(
        genome,
        {"t1": ({}, {})},
        seams=seams,
        budget_cap_tokens=1000,
        budget_cap_usd=1.0,
    )

    assert observed["extra_instruction"] == "EXECUTE THIS GENE"
    assert outcome.per_task[0]["error"] == "empty_patch"
    assert outcome.per_task[0]["execution_evidence"] == execution_evidence
    checked = check_genome(genome)
    assert "extra_instruction" in checked.executed_fields
    assert "extra_instruction" not in checked.ignored_fields


def test_resolved_verdict_is_measured_task_outcome() -> None:
    outcome = _grade(grade_explore.GraderResult.executed_verdict(True, 1.0))
    assert outcome.evidence_class == grade_explore.MEASURED_TASK_OUTCOME
    assert outcome.comparable_observations == 1
    assert outcome.pass_rate == 1.0


def test_arbitrary_note_on_typed_executed_false_does_not_become_infrastructure() -> None:
    outcome = _grade(
        grade_explore.GraderResult.executed_verdict(
            False,
            1.0,
            note="official report says tests failed; receipt=/redacted/path",
        )
    )
    assert outcome.evidence_class == grade_explore.MEASURED_NEGATIVE
    assert outcome.comparable_observations == 1
    assert outcome.per_task[0]["grade_note"].startswith("official report")


def test_untyped_legacy_error_channel_is_noncomparable_without_prose_guessing() -> None:
    outcome = _grade((False, 1.0, "ordinary note with no magic prefix"))
    assert outcome.evidence_class == grade_explore.INCONCLUSIVE_INFRASTRUCTURE
    assert outcome.comparable_observations == 0
    assert outcome.per_task[0]["grader_error_class"] == (
        "untyped_legacy_grader_error"
    )


def test_explore_closeout_vocabulary_cannot_encode_positive_lift() -> None:
    from dharma_swarm.forge_lab.run_receipts import EXPLORE_CLOSEOUTS

    assert "positive_lift_candidate" not in EXPLORE_CLOSEOUTS
    assert "inconclusive_infrastructure" in EXPLORE_CLOSEOUTS
    assert all("positive" not in state for state in EXPLORE_CLOSEOUTS)


def _verify_chain_grade(generator_rec: dict, verifier_rec: dict, calls: list) -> grade_explore.GradeOutcome:
    from dharma_swarm.forge_v1.forge_v2 import arms

    def fake_propose(slot, *_args, **kwargs):
        calls.append({"model_id": slot.model_id, "extra_instruction": kwargs.get("extra_instruction", "")})
        return dict(generator_rec if len(calls) == 1 else verifier_rec)

    real_verify_chain = arms.verify_chain_arm

    def patched_verify_chain(*args, **kwargs):
        original = arms._propose_slot
        arms._propose_slot = fake_propose
        try:
            return real_verify_chain(*args, **kwargs)
        finally:
            arms._propose_slot = original

    seams = grade_explore.GradeSeams(
        slot_for_id=lambda model_id: SimpleNamespace(model_id=model_id, provider="ollama"),
        propose_slot=fake_propose,
        self_moa_arm=lambda *_args, **_kwargs: {"final_patch": ""},
        verify_chain_arm=patched_verify_chain,
        mixed_moa_arm=lambda *_args, **_kwargs: {"final_patch": ""},
        grade_task=lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("empty patch must not reach the evaluator")
        ),
        budget_factory=_Budget,
    )
    return grade_explore.grade_genome_explore(
        {
            "arm_kind": "verify_chain",
            "generator_model": "gen:cloud",
            "verifier_model": "ver:cloud",
            "per_call_tokens": 10,
            "window_chars": 100,
        },
        {"t1": ({}, {})},
        seams=seams,
        budget_cap_tokens=1000,
        budget_cap_usd=1.0,
    )


def test_generator_infra_error_empty_patch_still_verifies_and_grades_infrastructure() -> None:
    calls: list = []
    outcome = _verify_chain_grade(
        {"patch": "", "tokens": 5, "error": "route: TimeoutError: boom"},
        {"patch": "", "tokens": 5, "error": None},
        calls,
    )
    assert len(calls) == 2
    assert calls[1]["model_id"] == "ver:cloud"
    assert "<EMPTY_PATCH>" in calls[1]["extra_instruction"]
    row = outcome.per_task[0]
    evidence = row["execution_evidence"]
    assert evidence["generator_error"] == "route: TimeoutError: boom"
    assert evidence["generator_infrastructure_error"] is True
    assert evidence["verifier_called"] is True
    assert evidence["verifier_error"] is None
    assert row["evidence_class"] == grade_explore.INCONCLUSIVE_INFRASTRUCTURE
    assert outcome.evidence_class == grade_explore.INCONCLUSIVE_INFRASTRUCTURE


def test_clean_empty_patch_still_verifies_and_grades_generation() -> None:
    calls: list = []
    outcome = _verify_chain_grade(
        {"patch": "", "tokens": 5, "error": None},
        {"patch": "", "tokens": 5, "error": None},
        calls,
    )
    assert len(calls) == 2
    row = outcome.per_task[0]
    evidence = row["execution_evidence"]
    assert evidence["generator_error"] is None
    assert evidence["generator_infrastructure_error"] is False
    assert evidence["verifier_called"] is True
    assert row["error"] == "empty_patch"
    assert row["evidence_class"] == grade_explore.INCONCLUSIVE_GENERATION
    assert outcome.evidence_class == grade_explore.INCONCLUSIVE_GENERATION


def test_freeform_single_evidence_carries_generator_error() -> None:
    seams = _seams(grade_explore.GraderResult.executed_verdict(False, 0.0), patch="")
    seams = grade_explore.GradeSeams(
        slot_for_id=seams.slot_for_id,
        propose_slot=lambda *_args, **_kwargs: {
            "patch": "",
            "tokens": 3,
            "error": "no edit block",
        },
        self_moa_arm=seams.self_moa_arm,
        verify_chain_arm=seams.verify_chain_arm,
        mixed_moa_arm=seams.mixed_moa_arm,
        grade_task=seams.grade_task,
        budget_factory=_Budget,
    )
    outcome = grade_explore.grade_genome_explore(
        {
            "arm_kind": "freeform_single",
            "generator_model": "offline-fixture",
            "per_call_tokens": 10,
            "window_chars": 100,
        },
        {"task-1": ({"instance_id": "task-1"}, {"f.py": "x"})},
        seams=seams,
        budget_cap_tokens=100,
        budget_cap_usd=0.0,
    )
    row = outcome.per_task[0]
    assert row["execution_evidence"]["generator_error"] == "no edit block"
    assert row["execution_evidence"]["generator_infrastructure_error"] is True
    assert row["evidence_class"] == grade_explore.INCONCLUSIVE_INFRASTRUCTURE
    assert outcome.evidence_class == grade_explore.INCONCLUSIVE_INFRASTRUCTURE
