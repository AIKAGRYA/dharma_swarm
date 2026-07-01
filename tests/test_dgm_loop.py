from __future__ import annotations

from pathlib import Path

import pytest

from dharma_swarm.dgm_loop import (
    DGM_PROTECTED_FILES,
    DGM_TARGET_FILES,
    DGMLoop,
    _is_protected_dgm_target,
)
from dharma_swarm.forge_v1.forge_v2.forge_fitness import ForgeGenomeFitness


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
async def test_dgm_forge_genome_generation_uses_forge_grade_not_auto_evolve() -> None:
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
