from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from dharma_swarm.context_compiler import ContextCompiler
from dharma_swarm.memory_kernel import CensusConfig, MemoryKernel, MemoryKernelConfig
from dharma_swarm.memory_kernel.adapters import ReadOnlyAdapterConfig


def _compiler(memory_kernel: object) -> ContextCompiler:
    runtime = MagicMock()
    runtime.init_db = AsyncMock()
    runtime.get_session = AsyncMock(return_value=None)
    runtime.list_delegation_runs = AsyncMock(return_value=[])
    runtime.list_memory_facts = AsyncMock(return_value=[])
    runtime.list_artifacts = AsyncMock(return_value=[])
    runtime.list_workspace_leases = AsyncMock(return_value=[])
    runtime.new_bundle_id = MagicMock(return_value="bnd_memory_kernel")
    runtime.record_context_bundle = AsyncMock(side_effect=lambda bundle: bundle)

    lattice = MagicMock()
    lattice.init_db = AsyncMock()
    lattice.replay_session = AsyncMock(return_value=[])
    lattice.recall = AsyncMock(return_value=[])
    lattice.always_on_context = AsyncMock(return_value="")

    return ContextCompiler(
        runtime_state=runtime,
        memory_lattice=lattice,
        memory_kernel=memory_kernel,  # type: ignore[arg-type]
    )


def _pack() -> SimpleNamespace:
    admitted = SimpleNamespace(
        admitted=True,
        rank=1,
        surface_id="home.witness",
        atom_type="witness_event",
        truth_state="observed",
        authority_level="medium",
        content_snippet="safe witness note",
        selection_reasons=("context_admissible_override", "truth_state:observed"),
        source_refs=("memory_kernel:home.witness",),
    )
    omitted = SimpleNamespace(
        admitted=False,
        rank=None,
        surface_id="home.lancedb",
        atom_type="source_chunk",
        truth_state="derived",
        authority_level="none",
        content_snippet=None,
        selection_reasons=(),
        omission_reasons=("truth_state_not_allowed", "projection_blocked"),
        source_refs=(),
    )
    return SimpleNamespace(
        pack_id="memory_context_pack:test",
        candidate_count=2,
        admitted_count=1,
        omitted_count=1,
        candidate_truncated=False,
        warnings=("preview_only_no_runtime_prompt_injection",),
        items=(admitted, omitted),
    )


class _FakeMemoryKernel:
    def __init__(self, pack: SimpleNamespace | None = None, error: Exception | None = None) -> None:
        self.pack = pack
        self.error = error
        self.kwargs: dict[str, object] = {}

    def preview_memory_pack(self, **kwargs: object) -> SimpleNamespace:
        self.kwargs = kwargs
        if self.error is not None:
            raise self.error
        assert self.pack is not None
        return self.pack


@pytest.mark.asyncio
async def test_context_compiler_adds_memory_kernel_default_section() -> None:
    kernel = _FakeMemoryKernel(_pack())
    compiler = _compiler(kernel)

    bundle = await compiler.compile_bundle(
        session_id="sess_memory_kernel",
        task_id="task_memory_kernel",
        task_description="Use governed memory.",
        query="governed memory",
        token_budget=1200,
    )

    assert "## Memory Kernel" in bundle.rendered_text
    assert "safe witness note" in bundle.rendered_text
    assert "projection_blocked" in bundle.rendered_text
    metadata = bundle.metadata["memory_kernel_default"]
    assert metadata["status"] == "used"
    assert metadata["text_query_applied"] is True
    assert metadata["pack_id"] == "memory_context_pack:test"
    assert metadata["admitted_count"] == 1
    assert metadata["omitted_count"] == 1
    query = kernel.kwargs["query"]
    assert getattr(query, "text_query") == "governed memory"
    budget = kernel.kwargs["budget"]
    assert getattr(budget, "require_context_admissible") is False
    assert getattr(budget, "allow_projections") is False
    assert getattr(budget, "allow_high_risk") is False


@pytest.mark.asyncio
async def test_context_compiler_uses_memory_kernel_text_query_for_live_context(
    tmp_path: Path,
) -> None:
    home = tmp_path / "home"
    repo = tmp_path / "repo"
    witness = home / ".dharma/witness/2026-05-12.jsonl"
    witness.parent.mkdir(parents=True, exist_ok=True)
    witness.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "content": "alpha governed memory for live graph context",
                        "timestamp": "2026-05-12T01:00:00Z",
                    }
                ),
                json.dumps(
                    {
                        "content": "unrelated operational note",
                        "timestamp": "2026-05-12T01:01:00Z",
                    }
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    kernel = MemoryKernel(
        MemoryKernelConfig(
            census=CensusConfig(repo_root=repo, home=home, include_discovered=False),
            adapter=ReadOnlyAdapterConfig(default_limit=10),
        )
    )
    compiler = _compiler(kernel)

    bundle = await compiler.compile_bundle(
        session_id="sess_memory_kernel_live",
        task_id="task_memory_kernel_live",
        task_description="Use governed memory.",
        query="alpha governed memory",
        token_budget=1200,
    )

    assert "## Memory Kernel" in bundle.rendered_text
    assert "alpha governed memory for live graph context" in bundle.rendered_text
    assert "unrelated operational note" not in bundle.rendered_text
    assert "memory_kernel:home.witness" in bundle.source_refs
    metadata = bundle.metadata["memory_kernel_default"]
    assert metadata["status"] == "used"
    assert metadata["text_query_applied"] is True
    assert metadata["admitted_count"] == 1


@pytest.mark.asyncio
async def test_context_compiler_falls_back_when_memory_kernel_fails() -> None:
    compiler = _compiler(_FakeMemoryKernel(error=RuntimeError("kernel unavailable")))

    bundle = await compiler.compile_bundle(
        session_id="sess_memory_kernel_fail",
        task_description="Continue with legacy context.",
        token_budget=1200,
    )

    assert "# DGC Context Bundle" in bundle.rendered_text
    assert "## Memory Kernel" not in bundle.rendered_text
    metadata = bundle.metadata["memory_kernel_default"]
    assert metadata["status"] == "failed"
    assert metadata["error_type"] == "RuntimeError"
