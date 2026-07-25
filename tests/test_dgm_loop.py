from __future__ import annotations

from pathlib import Path

import pytest

import dharma_swarm.dgm_loop as dgm_loop_mod
from dharma_swarm.dgm_loop import (
    DGM_PROTECTED_FILES,
    DGM_TARGET_FILES,
    DGMLoop,
    _is_protected_dgm_target,
    run_dgm_evolution_task,
)
def test_dgm_targets_exclude_dharma_boundary_files() -> None:
    assert DGM_PROTECTED_FILES.isdisjoint(set(DGM_TARGET_FILES))
    assert _is_protected_dgm_target("telos_gates.py")
    assert _is_protected_dgm_target(Path("dharma_swarm") / "dharma_kernel.py")


@pytest.mark.asyncio
async def test_dgm_rejects_explicit_protected_source_file_before_evolution() -> None:
    class ExplodingEngine:
        async def auto_evolve(self, **_kwargs):
            raise AssertionError("auto_evolve must not run for protected targets")

    loop = DGMLoop(engine=ExplodingEngine(), shadow_mode=True)

    result = await loop.run_one_generation(source_file="telos_gates.py")

    assert result.error is not None
    assert "Protected DGM target rejected" in result.error
    assert result.source_file == ""


@pytest.mark.asyncio
async def test_agent_callable_dgm_task_refuses_legacy_local_fitness_by_default(tmp_path) -> None:
    result = await run_dgm_evolution_task(
        source_file="agent_runner.py",
        state_dir=tmp_path,
    )

    assert result["success"] is False
    assert result["shadow_mode"] is True
    assert result["forge_required"] is True
    assert "run_dgm_forge_genome_task" in result["error"]
    assert "grade_genome" in result["error"]


@pytest.mark.asyncio
async def test_dgm_forge_genome_generation_uses_forge_grade_not_auto_evolve() -> None:
    # forge_fitness lands with U2 (join cluster); until then this test skips.
    forge_fitness = pytest.importorskip("dharma_swarm.forge_v1.forge_v2.forge_fitness")
    ForgeGenomeFitness = forge_fitness.ForgeGenomeFitness

    class ExplodingEngine:
        async def auto_evolve(self, **_kwargs):
            raise AssertionError("Forge genome DGM path must not use local Darwin auto_evolve")

    captured = {}

    def fake_grade(genome, instance_ids, *, split):
        captured["genome"] = genome
        captured["instance_ids"] = instance_ids
        captured["split"] = split
        return ForgeGenomeFitness(
            genome={"arm": "verify_chain"},
            split="confirm",
            fitness=0.06,
            ci={"n": 500, "mean": 0.06, "lower": 0.02, "upper": 0.1},
            closeout="positive_lift_candidate",
            real_grade=True,
            promote_eligible=False,
            runner_receipt={"source": "fake_forge_runner"},
            blockers=["missing_signed_receipts"],
        )

    loop = DGMLoop(engine=ExplodingEngine(), shadow_mode=True)

    result = await loop.run_forge_genome_generation(
        {"arm": "verify_chain"},
        ["fresh-task-1"],
        split="confirm",
        grade_fn=fake_grade,
    )

    assert captured == {
        "genome": {"arm": "verify_chain"},
        "instance_ids": ["fresh-task-1"],
        "split": "confirm",
    }
    assert result.error is None
    assert result.source_file == "forge_scaffold::verify_chain"
    assert result.fitness_after == pytest.approx(0.06)
    assert result.forge_grade["real_grade"] is True
    assert result.promote_eligible is False
    assert result.promotion_blockers == ["missing_signed_receipts"]
    assert result.applied is False
    assert result.shadow_mode is True


@pytest.mark.asyncio
async def test_dgm_forge_genome_generation_defaults_to_subprocess_bridge(monkeypatch) -> None:
    class ExplodingEngine:
        async def auto_evolve(self, **_kwargs):
            raise AssertionError("Forge genome DGM path must not use local Darwin auto_evolve")

    captured = {}

    async def fake_subprocess_grade(genome, instance_ids, *, split):
        captured["genome"] = genome
        captured["instance_ids"] = instance_ids
        captured["split"] = split
        return {
            "genome": {"arm": "verify_chain"},
            "split": "confirm",
            "fitness": 0.07,
            "ci": {"n": 500, "mean": 0.07, "lower": 0.02, "upper": 0.12},
            "closeout": "positive_lift_candidate",
            "real_grade": True,
            "promote_eligible": False,
            "runner_receipt": {"source": "subprocess_forge_runner"},
            "blockers": ["missing_signed_receipts"],
        }

    monkeypatch.setattr(dgm_loop_mod, "_grade_forge_genome_in_subprocess", fake_subprocess_grade)
    loop = DGMLoop(engine=ExplodingEngine(), shadow_mode=True)

    result = await loop.run_forge_genome_generation(
        {"arm": "verify_chain"},
        ["fresh-task-1"],
        split="confirm",
    )

    assert captured == {
        "genome": {"arm": "verify_chain"},
        "instance_ids": ["fresh-task-1"],
        "split": "confirm",
    }
    assert result.error is None
    assert result.fitness_after == pytest.approx(0.07)
    assert result.forge_grade["runner_receipt"]["source"] == "subprocess_forge_runner"
    assert result.applied is False
    assert result.shadow_mode is True


@pytest.mark.asyncio
async def test_dgm_forge_genome_generation_fails_closed_until_forge_fitness_lands(monkeypatch) -> None:
    class ExplodingEngine:
        async def auto_evolve(self, **_kwargs):
            raise AssertionError("Forge genome DGM path must not use local Darwin auto_evolve")

    monkeypatch.setattr(dgm_loop_mod, "_forge_fitness_available", lambda: False)
    loop = DGMLoop(engine=ExplodingEngine(), shadow_mode=True)

    result = await loop.run_forge_genome_generation(
        {"arm": "verify_chain"},
        ["fresh-task-1"],
        split="confirm",
    )

    assert result.error is not None
    assert "Forge genome subprocess grader is unavailable" in result.error
    assert dgm_loop_mod.FORGE_FITNESS_MODULE in result.error
    assert result.applied is False
    assert result.shadow_mode is True
