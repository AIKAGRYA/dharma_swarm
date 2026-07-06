"""Wild EXPLORE path tests: prove the LLM proposer is REACHABLE by the loop.

The first chassis shipped the frontier operator as dormant code the loop could
never invoke. These tests fail if the wild path regresses back to unreachable.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from dharma_swarm.forge_lab import experiment as experiment_mod
from dharma_swarm.forge_lab.experiment import ExperimentConfig, run_experiment
from dharma_swarm.forge_lab.mutation import default_operators, mutate_genome
from dharma_swarm.forge_lab.providers import _extract_json_object


def test_extract_json_object_handles_raw_fenced_and_embedded() -> None:
    assert _extract_json_object('{"a": 1}') == {"a": 1}
    assert _extract_json_object("```json\n{\"a\": 2}\n```") == {"a": 2}
    assert _extract_json_object("here you go: {\"a\": 3} thanks") == {"a": 3}
    assert _extract_json_object("no json here") is None
    assert _extract_json_object("") is None


def test_default_operators_is_wild_first_with_proposer() -> None:
    ops = default_operators(proposer=lambda parent, ctx: dict(parent), second_parent={"x": 1})
    assert ops[0] == "llm_propose_genome"
    assert "llm_crossover" in ops
    assert "parametric" in ops


def test_default_operators_falls_back_without_proposer() -> None:
    assert default_operators(proposer=None) == ["parametric"]


def test_mutate_genome_records_proposer_exception_as_blocked() -> None:
    import random

    def boom(parent, ctx):
        raise RuntimeError("provider on fire")

    result = mutate_genome(
        {"strategy": "seed"},
        rng=random.Random(0),
        operators=["llm_propose_genome"],
        proposer=boom,
    )
    assert result.blocked is True
    assert result.operator == "llm_propose_genome"
    assert "RuntimeError" in result.blocker


@pytest.mark.asyncio
async def test_run_experiment_wild_path_reachable_with_fake_proposer(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Inject a fake frontier proposer and assert LLM children are archived."""
    root = tmp_path / "wt"
    archive_root = tmp_path / "arch"
    monkeypatch.setenv("DHARMA_EVOLUTION_WORKTREE_ROOT", str(root))

    calls = {"n": 0}

    def fake_proposer(parent, context):
        calls["n"] += 1
        child = dict(parent)
        child["strategy"] = f"llm_variant_{calls['n']}"
        child["k_candidates"] = (calls["n"] % 5) + 1
        child.setdefault("notes", [])
        child["notes"] = [*list(child["notes"]), "from_fake_frontier"]
        # Prove context is actually threaded to the proposer.
        child["saw_failures"] = len(context.get("failure_transcripts") or [])
        child["saw_archive"] = len(context.get("archive_context") or [])
        return child

    def fake_build(**kwargs):
        report = {"proposer": "active", "dispatchable_slots": ["fake/frontier"], **kwargs}
        return fake_proposer, report

    monkeypatch.setattr(experiment_mod, "build_frontier_proposer", fake_build)

    closeout = await run_experiment(
        ExperimentConfig(
            experiment_id="exp_wild_reachable",
            generations=2,
            children=3,
            source_repo=Path.cwd(),
            base_ref="HEAD",
            archive_root=archive_root,
            worktree_root=root,
            allow_model_calls=True,
        )
    )

    assert closeout["closeout_state"] == "inconclusive_low_power"
    assert closeout["positive_lift_claim"] is False
    # The wild operator was actually exercised by the loop.
    assert closeout["operator_histogram"].get("llm_propose_genome", 0) >= 1
    assert calls["n"] >= 1

    archive_dir = archive_root / "agent_evolution" / "exp_wild_reachable"
    records = [
        json.loads(line)
        for line in (archive_dir / "candidate_records.jsonl").read_text().splitlines()
        if line.strip()
    ]
    llm_children = [r for r in records if r["operator"] == "llm_propose_genome"]
    assert llm_children, "no llm_propose_genome children were archived"
    # At least one later child saw prior archive context (mycelial soil).
    assert any(r["genome"].get("saw_archive", 0) >= 1 for r in llm_children)

    manifest = json.loads((archive_dir / "run_manifest.json").read_text())
    assert manifest["proposer"]["proposer"] == "active"


@pytest.mark.asyncio
async def test_run_experiment_offline_falls_back_to_parametric(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """With model calls off, the loop must not fake a frontier call."""
    root = tmp_path / "wt2"
    archive_root = tmp_path / "arch2"
    monkeypatch.setenv("DHARMA_EVOLUTION_WORKTREE_ROOT", str(root))

    closeout = await run_experiment(
        ExperimentConfig(
            experiment_id="exp_offline_fallback",
            generations=1,
            children=2,
            source_repo=Path.cwd(),
            base_ref="HEAD",
            archive_root=archive_root,
            worktree_root=root,
            allow_model_calls=False,
        )
    )

    assert closeout["proposer"] == "disabled"
    assert closeout["operator_histogram"].get("llm_propose_genome", 0) == 0
    assert closeout["operator_histogram"].get("parametric", 0) >= 1


@pytest.mark.asyncio
async def test_blocked_child_colliding_with_seed_keeps_honest_state(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A malformed proposal that falls back to the parent genome must be recorded
    as ``blocked`` with its real blocker, NOT silently relabeled ``duplicate``.
    """
    from dharma_swarm.forge_lab.candidate_store import CandidateStore
    from dharma_swarm.forge_lab.mutation import seed_genome

    store = CandidateStore(tmp_path / "arch")
    await store.load()
    seed = seed_genome()
    await store.append(
        genome=seed,
        parent_id=None,
        experiment_id="exp",
        category="agent_evolution",
        generation=0,
        loop_iteration=0,
        state="graded",
        role="seed_baseline",
        fitness={"weighted": 0.4},
    )
    # A blocked child whose genome collides with the seed (parent fallback).
    record = await store.append(
        genome=seed,
        parent_id="cand_parent",
        experiment_id="exp",
        category="agent_evolution",
        generation=1,
        loop_iteration=1,
        state="blocked",
        operator="llm_propose_genome",
        notes="ValueError:proposer returned unparseable genome",
    )
    assert record.state == "blocked"
    assert "unparseable" in record.notes
    assert record.candidate_id != "cand_09fe99e391365795219bc546"
