from pathlib import Path

import pytest

from dharma_swarm.evolution import Proposal
from dharma_swarm.orchestrate_live import _generate_grind_probe_proposal


class _DummyEngine:
    def __init__(self, proposal: Proposal | None) -> None:
        self._proposal = proposal
        self.calls: list[dict] = []

    async def generate_proposal(self, **kwargs):
        self.calls.append(kwargs)
        return self._proposal


@pytest.mark.asyncio
async def test_generate_grind_probe_proposal_requires_real_diff(tmp_path: Path) -> None:
    source_root = tmp_path
    target = "alpha.py"
    (source_root / target).write_text("def alpha():\n    return 1\n", encoding="utf-8")
    proposal = Proposal(
        component=target,
        change_type="mutation",
        description="tighten alpha return path",
        diff="--- a/alpha.py\n+++ b/alpha.py\n@@ -1,2 +1,2 @@\n def alpha():\n-    return 1\n+    return 2\n",
    )
    engine = _DummyEngine(proposal)

    result = await _generate_grind_probe_proposal(
        engine,
        source_root=source_root,
        target=target,
        hunger=0.62,
        provider=object(),
        model="qwen/qwen3-coder:free",
    )

    assert result is proposal
    assert result is not None
    assert result.spec_ref == "grind_probe"
    assert result.diff.startswith("--- a/alpha.py")
    assert engine.calls[0]["source_file"] == source_root / target
    assert "Hunger=0.62" in engine.calls[0]["context"]


@pytest.mark.asyncio
async def test_generate_grind_probe_proposal_drops_empty_diff(tmp_path: Path) -> None:
    source_root = tmp_path
    target = "beta.py"
    (source_root / target).write_text("def beta():\n    return 1\n", encoding="utf-8")
    proposal = Proposal(
        component=target,
        change_type="mutation",
        description="placeholder",
        diff="",
    )
    engine = _DummyEngine(proposal)

    result = await _generate_grind_probe_proposal(
        engine,
        source_root=source_root,
        target=target,
        hunger=0.41,
        provider=object(),
        model="qwen/qwen3-coder:free",
    )

    assert result is None


@pytest.mark.asyncio
async def test_generate_grind_probe_proposal_drops_noop(tmp_path: Path) -> None:
    source_root = tmp_path
    target = "gamma.py"
    (source_root / target).write_text("def gamma():\n    return 1\n", encoding="utf-8")
    engine = _DummyEngine(None)

    result = await _generate_grind_probe_proposal(
        engine,
        source_root=source_root,
        target=target,
        hunger=0.33,
        provider=object(),
        model="qwen/qwen3-coder:free",
    )

    assert result is None
