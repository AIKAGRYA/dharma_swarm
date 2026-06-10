from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from dharma_swarm.dgm_loop import (
    DGM_PROTECTED_FILES,
    DGM_TARGET_FILES,
    DGMLoop,
    _is_protected_dgm_target,
)
from dharma_swarm.evolution import DarwinEngine
from dharma_swarm.models import LLMResponse


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
async def test_dgm_non_shadow_uses_injected_tmp_workspace_provider_and_test_command(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    source_root = tmp_path / "workspace"
    source_root.mkdir()
    source_path = source_root / "agent_runner.py"
    source_path.write_text("def run() -> str:\n    return 'tmp'\n", encoding="utf-8")
    fake_provider = object()
    test_command = "python3 -m pytest tests/test_tmp_agent_runner.py -q"

    class FakeEngine:
        def __init__(self) -> None:
            self.archive = SimpleNamespace(_entries={})
            self.calls: list[dict[str, object]] = []

        async def auto_evolve(self, **kwargs):
            self.calls.append(kwargs)
            child = SimpleNamespace(
                id="child-1",
                parent_id=None,
                timestamp="2026-05-28T00:00:00Z",
                status="applied",
            )
            self.archive._entries[child.id] = child
            return SimpleNamespace(
                proposals_submitted=1,
                proposals_gated=1,
                best_fitness=0.42,
            )

    engine = FakeEngine()
    loop = DGMLoop(
        engine=engine,
        shadow_mode=False,
        source_root=source_root,
        provider=fake_provider,
        test_command=test_command,
    )

    result = await loop.run_one_generation(source_file="agent_runner.py", timeout=3.0)

    assert result.error is None
    assert result.shadow_mode is False
    assert result.source_file == "agent_runner.py"
    assert result.child_id == "child-1"
    assert result.applied is True
    assert result.archive_size_before == 0
    assert result.archive_size_after == 1
    assert result.fitness_after == 0.42
    assert result.fitness_delta == 0.42

    assert len(engine.calls) == 1
    call = engine.calls[0]
    assert call["provider"] is fake_provider
    assert call["source_files"] == [source_path]
    assert call["shadow"] is False
    assert call["timeout"] == 3.0
    assert call["test_command"] == test_command


@pytest.mark.asyncio
async def test_dgm_non_shadow_applies_and_archives_in_tmp_workspace(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    workspace = tmp_path / "workspace"
    source_root = workspace / "dharma_swarm"
    source_root.mkdir(parents=True)
    (source_root / "__init__.py").write_text("", encoding="utf-8")
    source_path = source_root / "dgm_probe.py"
    source_path.write_text(
        "def run() -> str:\n"
        "    return \"before\"\n",
        encoding="utf-8",
    )
    test_script = (
        "from dharma_swarm.dgm_probe import run; "
        "assert run() == 'after'"
    )
    test_command = f"{sys.executable} -c {test_script!r}"

    class FakeProvider:
        async def complete(self, request):
            del request
            return LLMResponse(
                model="fake-dgm",
                provider="test",
                usage={"total_tokens": 12},
                content=(
                    "COMPONENT: dharma_swarm/dgm_probe.py\n"
                    "CHANGE_TYPE: mutation\n"
                    "DESCRIPTION: Improve probe mechanism with witness "
                    "observation and resilience feedback in bounded "
                    "temp-workspace proof; risk: minimal; rollback: restore "
                    "the previous literal; alternatives: keep current value.\n"
                    "THINK: Risk: temp workspace only. Rollback: single-line "
                    "literal restore. Alternatives considered: no-op. "
                    "Expected: deterministic proof command passes.\n"
                    "```diff\n"
                    "--- a/dharma_swarm/dgm_probe.py\n"
                    "+++ b/dharma_swarm/dgm_probe.py\n"
                    "@@ -1,2 +1,2 @@\n"
                    " def run() -> str:\n"
                    "-    return \"before\"\n"
                    "+    return \"after\"\n"
                    "```\n"
                ),
            )

    engine = DarwinEngine(
        archive_path=tmp_path / "archive.jsonl",
        traces_path=tmp_path / "traces",
        predictor_path=tmp_path / "predictor.jsonl",
        probe_targets=[
            {
                "component_pattern": "dharma_swarm/dgm_probe.py",
                "workspace": str(workspace),
                "test_command": test_command,
                "timeout": 5.0,
            }
        ],
    )
    await engine.init()
    try:
        loop = DGMLoop(
            engine=engine,
            shadow_mode=False,
            source_root=source_root,
            provider=FakeProvider(),
            test_command=test_command,
        )

        result = await loop.run_one_generation(
            source_file="dgm_probe.py",
            timeout=5.0,
        )
        latest = await engine.archive.get_latest(n=1)
    finally:
        await engine.close()

    assert result.error is None
    assert result.shadow_mode is False
    assert result.applied is True
    assert result.archive_size_before == 0
    assert result.archive_size_after == 1
    assert result.child_id is not None
    assert "return \"after\"" in source_path.read_text(encoding="utf-8")
    assert latest
    assert latest[0].component == "dharma_swarm/dgm_probe.py"
    assert latest[0].test_results["execution_target"]["workspace"] == str(
        workspace.resolve()
    )
