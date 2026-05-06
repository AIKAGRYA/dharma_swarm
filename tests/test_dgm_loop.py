from __future__ import annotations

from pathlib import Path

import pytest

from dharma_swarm.dgm_loop import (
    DGM_PROTECTED_FILES,
    DGM_TARGET_FILES,
    DGMLoop,
    _is_protected_dgm_target,
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
