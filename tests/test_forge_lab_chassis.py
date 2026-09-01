"""Forge v3 chassis unit tests — deterministic, no network/git/model calls."""

from __future__ import annotations

import random

import pytest

from dharma_swarm.archive import ArchiveEntry, FitnessScore
from dharma_swarm.forge_lab import grade_explore, ids, mutation, selection
from dharma_swarm.forge_lab.candidate_store import BLOCKED, GRADED, CandidateStore
from dharma_swarm.forge_lab.freeform_explore import FreeformExploreEnvelope, MEMBRANE_REQUIREMENTS
from dharma_swarm.forge_lab.genome_spec import DEFAULT_GENOME, check_genome, merged_with_defaults

# ---------------------------------------------------------------- ids


def test_candidate_id_is_content_addressed_and_order_insensitive():
    a = ids.candidate_id({"x": 1, "y": [1, 2]})
    b = ids.candidate_id({"y": [1, 2], "x": 1})
    assert a == b and a.startswith("cand_") and len(a) == 21


def test_candidate_id_ignores_nothing_but_genome():
    assert ids.candidate_id({"x": 1}) != ids.candidate_id({"x": 2})


# ---------------------------------------------------------------- genome


def test_default_genome_needs_only_a_generator_to_execute():
    genome = merged_with_defaults({"generator_model": "m"})
    checked = check_genome(genome)
    assert checked.executable and not checked.reasons


def test_default_genome_has_swebench_repair_headroom():
    assert DEFAULT_GENOME["per_call_tokens"] >= 16000
    assert DEFAULT_GENOME["window_chars"] >= 24000


def test_malformed_genomes_block_with_reasons_not_exceptions():
    for genome, expected in (
        ("not a dict", "genome_not_a_dict"),
        ({"arm_kind": "quantum_leap", "generator_model": "m"}, "unknown_arm_kind"),
        ({"arm_kind": "verify_chain", "generator_model": "m"}, "missing_verifier_model"),
        ({"arm_kind": "self_moa", "generator_model": "m", "k": 99}, "k_out_of_range"),
    ):
        checked = check_genome(genome if isinstance(genome, dict) else genome)
        assert not checked.executable
        assert any(r.startswith(expected) for r in checked.reasons)


def test_unknown_keys_are_compost_not_errors():
    genome = merged_with_defaults({"generator_model": "m", "mycelium": {"spore": 1}})
    checked = check_genome(genome)
    assert checked.executable and "mycelium" in checked.ignored_fields


# ---------------------------------------------------------------- selection


def _entry(eid: str, fitness: float) -> ArchiveEntry:
    return ArchiveEntry(id=eid, fitness=FitnessScore(correctness=fitness), status="shadow")


def test_selection_p0_is_pure_fitness():
    rng = random.Random(7)
    entries = [_entry("weak", 0.0), _entry("strong", 1.0)]
    picks = {selection.sample_parent(entries, {}, novelty_pressure=0.0, rng=rng).id for _ in range(50)}
    assert picks == {"strong"}


def test_selection_p1_ignores_fitness_entirely():
    rng = random.Random(7)
    entries = [_entry("weak", 0.0), _entry("strong", 1.0)]
    picks = {selection.sample_parent(entries, {}, novelty_pressure=1.0, rng=rng).id for _ in range(200)}
    assert picks == {"weak", "strong"}


def test_stepping_stone_stays_sampleable_and_cold_start_is_uniform():
    rng = random.Random(3)
    entries = [_entry("zero_a", 0.0), _entry("zero_b", 0.0)]
    picks = {selection.sample_parent(entries, {"zero_a": 5}, novelty_pressure=0.7, rng=rng).id for _ in range(100)}
    assert picks == {"zero_a", "zero_b"}  # uniform fallback: nothing unreachable


def test_novelty_pressure_penalizes_overused_parents():
    w_fresh = selection.parent_weight(0.5, 0, 0.7)
    w_used = selection.parent_weight(0.5, 9, 0.7)
    assert w_fresh > w_used > 0


# ---------------------------------------------------------------- mutation


def test_parametric_mutation_is_deterministic_under_seed():
    parent = merged_with_defaults({"generator_model": "m"})
    a = mutation.parametric_mutation(parent, rng=random.Random(11)).genome
    b = mutation.parametric_mutation(parent, rng=random.Random(11)).genome
    assert a == b and a != parent


def test_llm_propose_parses_json_from_noisy_reply():
    reply = 'Sure! Here is the child:\n```json\n{"arm_kind": "freeform_single", "generator_model": "m", "extra_instruction": "be bold", "notes": "why"}\n```'
    result = mutation.llm_propose_genome(
        {"generator_model": "m"}, complete_fn=lambda p: (reply, 42)
    )
    assert result.genome and result.genome["extra_instruction"] == "be bold"
    assert result.tokens_used == 42 and result.operator == "llm_propose"


def test_llm_propose_non_json_reply_is_salvaged_as_freeform_compost():
    parent = merged_with_defaults({"generator_model": "m", "extra_instruction": "prior"})
    result = mutation.llm_propose_genome(parent, complete_fn=lambda p: ("try a smaller patch first", 5))
    assert result.genome is not None
    assert result.parse_issues == ("salvaged_non_json_as_freeform",)
    assert result.genome["mutation_parse_salvage"] is True
    assert "try a smaller patch first" in result.genome["extra_instruction"]
    assert result.genome["generator_model"] == "m"


def test_llm_propose_empty_reply_is_evidence_not_crash():
    result = mutation.llm_propose_genome({"g": 1}, complete_fn=lambda p: ("   ", 5))
    assert result.genome is None and result.parse_issues == ("no_json_object_found",)


def test_llm_provider_error_is_captured():
    def boom(prompt: str):
        raise RuntimeError("provider down")

    result = mutation.llm_propose_genome({"g": 1}, complete_fn=boom)
    assert result.genome is None and "provider_error" in result.parse_issues


def test_crossover_prompt_carries_both_parents():
    prompts: list[str] = []

    def capture(prompt: str):
        prompts.append(prompt)
        return ("{}", 1)

    mutation.llm_propose_genome({"a": 1}, complete_fn=capture, second_parent={"b": 2})
    assert "SECOND PARENT" in prompts[0]


# ---------------------------------------------------------------- store


@pytest.fixture
def store(tmp_path):
    return CandidateStore(tmp_path / "archive.jsonl", experiment_id="exp_test")


def _envelope(cid: str) -> FreeformExploreEnvelope:
    return FreeformExploreEnvelope(
        candidate_id=cid, parent_id=None, experiment_id="exp_test",
        category="agent_evolution", membrane={name: True for name in MEMBRANE_REQUIREMENTS},
    )


async def test_store_graded_rows_are_fitness_bearing_and_deduped(store):
    await store.load()
    cid = ids.candidate_id({"g": 1})
    await store.append_graded(
        candidate_id=cid, genome={"g": 1, "arm_kind": "freeform_single"}, parent_id=None,
        generation=0, loop_iteration=0, role="seed_baseline", pass_rate=0.5,
        per_task=[{"task_id": "t1", "resolved": True}], budget={}, tier="explore-fast-host-pytest",
        executed_fields=("arm_kind",), ignored_fields=(), envelope=_envelope(cid),
    )
    assert await store.has(cid)
    graded = await store.graded_entries()
    assert len(graded) == 1 and graded[0].fitness.correctness == 0.5
    row = CandidateStore._row(graded[0])
    assert row["state"] == GRADED and row["behavior"]["solved_task_ids"] == ["t1"]


async def test_store_blocked_rows_are_invisible_to_selection_but_persist(store):
    await store.load()
    await store.append_blocked(
        candidate_id="blk_1", genome=None, parent_id=None, generation=1,
        loop_iteration=1, reasons=["no_json_object_found"], raw_output="garbage",
    )
    assert await store.has("blk_1")
    assert await store.graded_entries() == []
    entry = await store.archive.get_entry("blk_1")
    assert CandidateStore._row(entry)["state"] == BLOCKED


async def test_store_lineage_and_children_counts(store):
    await store.load()
    parent_cid = ids.candidate_id({"p": 1})
    await store.append_graded(
        candidate_id=parent_cid, genome={"p": 1}, parent_id=None, generation=0,
        loop_iteration=0, role="seed_baseline", pass_rate=0.0, per_task=[], budget={},
        tier="t", executed_fields=(), ignored_fields=(), envelope=_envelope(parent_cid),
    )
    child_cid = ids.candidate_id({"c": 1})
    await store.append_graded(
        candidate_id=child_cid, genome={"c": 1}, parent_id=parent_cid, generation=1,
        loop_iteration=1, role="candidate", pass_rate=0.0, per_task=[], budget={},
        tier="t", executed_fields=(), ignored_fields=(), envelope=_envelope(child_cid),
    )
    assert store.n_children_map() == {parent_cid: 1}
    lineage = await store.archive.get_lineage(child_cid)
    assert [e.id for e in lineage] == [child_cid, parent_cid]


# ---------------------------------------------------------------- grading adapter


class _FakeBudget:
    def __init__(self, cap_tokens: int, cap_usd: float | None = None):
        self.cap_tokens, self.cap_usd = cap_tokens, cap_usd
        self.spent, self.invalid, self.invalid_reason = 0, False, None

    def charge(self, component, tokens, **kw):
        self.spent += tokens
        if self.spent > self.cap_tokens:
            self.invalid, self.invalid_reason = True, "cap_tokens"
        return tokens

    def to_dict(self):
        return {"cap_tokens": self.cap_tokens, "spent_tokens": self.spent, "invalid": self.invalid}


def _fake_seams(patch: str = "diff --git a/f b/f", resolve: bool = True) -> grade_explore.GradeSeams:
    return grade_explore.GradeSeams(
        slot_for_id=lambda mid: object() if mid else None,
        propose_slot=lambda slot, inst, ctx, **kw: {"patch": patch, "tokens": 10},
        self_moa_arm=lambda *a, **kw: {"final_patch": patch},
        verify_chain_arm=lambda *a, **kw: {"final_patch": patch},
        mixed_moa_arm=lambda *a, **kw: {"final_patch": patch},
        grade_task=lambda inst, p, timeout: (resolve, 1.5, None),
        budget_factory=_FakeBudget,
    )


def test_grade_explore_freeform_single_resolves():
    genome = merged_with_defaults({"generator_model": "m", "extra_instruction": "wild"})
    outcome = grade_explore.grade_genome_explore(
        genome, {"t1": ({}, {}), "t2": ({}, {})},
        seams=_fake_seams(), budget_cap_tokens=1000, budget_cap_usd=1.0,
    )
    assert outcome.pass_rate == 1.0 and len(outcome.per_task) == 2
    assert all(r["resolved"] for r in outcome.per_task)


def test_grade_explore_empty_patch_and_failures_are_rows_not_raises():
    genome = merged_with_defaults({"generator_model": "m"})
    outcome = grade_explore.grade_genome_explore(
        genome, {"t1": ({}, {})},
        seams=_fake_seams(patch=""), budget_cap_tokens=1000, budget_cap_usd=1.0,
    )
    assert outcome.pass_rate == 0.0 and outcome.per_task[0]["error"] == "empty_patch"
    assert outcome.failures


def test_grade_explore_unresolvable_model_is_a_row():
    genome = merged_with_defaults({"generator_model": ""})
    genome["generator_model"] = ""  # slot_for_id returns None
    outcome = grade_explore.grade_genome_explore(
        genome, {"t1": ({}, {})},
        seams=_fake_seams(), budget_cap_tokens=1000, budget_cap_usd=1.0,
    )
    assert "error" in outcome.per_task[0]
