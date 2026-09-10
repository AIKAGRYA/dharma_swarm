"""Read-only OpenCode transport over the existing Mission Control and MemoryKernel owners.

No runtime is started, no credentials are read, and no model is invoked here.
Mission Control retains its immutable snapshot behavior. Memory reads retain
the canonical adapter's manifest checks and context admission/redaction rules.
"""

from __future__ import annotations

import argparse
from collections.abc import Callable
from pathlib import Path
from typing import Any

from .config import local_path

MEMORY_SURFACE_ID = "home.knowledge_wiki"
MAX_CANDIDATES = 24
MAX_ADMITTED = 8
MAX_CONTEXT_CHARS = 4000


def _memory_kernel(repo_root: Path, *, home: Path | None = None) -> Any:
    from dharma_swarm.memory_kernel.adapters import ReadOnlyAdapterConfig
    from dharma_swarm.memory_kernel.census import CensusConfig
    from dharma_swarm.memory_kernel.facade import MemoryKernel, MemoryKernelConfig
    from dharma_swarm.memory_kernel.surfaces import default_surface_specs

    specs = tuple(spec for spec in default_surface_specs() if spec.surface_id == MEMORY_SURFACE_ID)
    return MemoryKernel(MemoryKernelConfig(
        census=CensusConfig(
            repo_root=repo_root, home=home or Path.home(), specs=specs, include_discovered=False,
        ),
        adapter=ReadOnlyAdapterConfig(
            default_limit=MAX_CANDIDATES, max_files=64,
            max_content_chars=2000, max_metadata_chars=600,
        ),
    ))


class WorkbenchMemory:
    """Lazy bounded knowledge observations, with no ingestion or retrieval feedback."""

    def __init__(
        self, repo_root: Path, *, kernel_factory: Callable[[Path], Any] | None = None
    ) -> None:
        self.repo_root = local_path(repo_root, directory=True)
        self._kernel_factory = kernel_factory or _memory_kernel

    def memory_context(self, query: str = "", limit: int = MAX_ADMITTED) -> dict[str, Any]:
        """Read matching knowledge from a bounded preview; never a complete index search."""
        from dharma_swarm.memory_kernel.atoms import MemoryLane, MemoryQuery, MemoryScope, TruthState
        from dharma_swarm.memory_kernel.context_admission import MemoryContextBudget

        if len(query) > 512 or any(char in query for char in "\0\r"):
            raise ValueError("query must be at most 512 characters with no NUL or carriage return")
        if isinstance(limit, bool) or not 1 <= limit <= MAX_ADMITTED:
            raise ValueError(f"limit must be between 1 and {MAX_ADMITTED}")
        kernel = self._kernel_factory(self.repo_root)
        available = MEMORY_SURFACE_ID in kernel.list_adapter_ids()
        pack = kernel.preview_memory_pack(
            surface_ids=(MEMORY_SURFACE_ID,),
            query=MemoryQuery(
                text_query=query.strip() or None,
                limit_total=MAX_CANDIDATES, limit_per_surface=MAX_CANDIDATES,
                include_content=True, include_high_risk=False,
                include_projections=False, include_unsafe=False,
                require_source_digest=True, require_source_row_key=True,
            ),
            budget=MemoryContextBudget(
                max_candidate_atoms=MAX_CANDIDATES, max_admitted_atoms=limit,
                max_total_chars=MAX_CONTEXT_CHARS, max_atom_chars=600,
                include_content=True, require_context_admissible=False,
                allow_projections=False, allow_high_risk=False,
                require_source_digest=True, require_source_row_key=True,
                block_tool_exposure=True, isolation_mode="scoped",
                allowed_scopes=(MemoryScope.PROJECT,),
                allowed_memory_lanes=(MemoryLane.SEMANTIC, MemoryLane.PROCEDURAL),
                allowed_truth_states=(
                    TruthState.OBSERVED, TruthState.CLAIMED,
                    TruthState.CURATED, TruthState.CANONICAL,
                ),
            ),
        )
        return {
            "schema": "dharma.helm.workbench_memory.v1",
            "available": available,
            "repo_root": str(self.repo_root),
            "scope": "local Dharma knowledge wiki; not filtered by repository",
            "read_only": True,
            "coverage": "bounded manifest-checked lexical preview; an empty result is not an exhaustive absence claim",
            "pack": pack.to_json(),
        }


def create_workbench_mcp(
    repo_root: Path, *, kernel_factory: Callable[[Path], Any] | None = None
) -> Any:
    """Expose only reads; the default owner factory never receives mutation authority."""
    from mcp.types import ToolAnnotations

    from dharma_swarm.mission_control_mcp import (
        MUTATION_TOOL_NAMES,
        create_default_mission_control_mcp,
    )

    memory = WorkbenchMemory(repo_root, kernel_factory=kernel_factory)
    server = create_default_mission_control_mcp()
    for name in MUTATION_TOOL_NAMES:
        server.remove_tool(name)
    server.add_tool(
        memory.memory_context,
        name="memory_context",
        description=(
            "Read a bounded, manifest-checked MemoryKernel knowledge preview. "
            "Preserves truth states and redacts secrets; does not write memory or grant authority. "
            "Search is local Dharma knowledge, not exhaustive or repository-filtered."
        ),
        annotations=ToolAnnotations(
            readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False,
        ),
        structured_output=True,
    )
    return server


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", required=True, type=Path)
    args = parser.parse_args()
    create_workbench_mcp(args.repo_root).run(transport="stdio")


if __name__ == "__main__":  # pragma: no cover - invoked by the OpenCode MCP client
    main()
