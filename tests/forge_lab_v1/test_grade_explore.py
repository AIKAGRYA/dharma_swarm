from __future__ import annotations

from types import SimpleNamespace

from dharma_swarm.forge_lab import grade_explore


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
