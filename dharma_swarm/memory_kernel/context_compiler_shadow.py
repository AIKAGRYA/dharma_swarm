"""MemoryKernel shadow parity hook for ContextCompiler."""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Callable

from dharma_swarm.runtime_state import ContextBundleRecord

logger = logging.getLogger(__name__)


def _truthy_env(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in {"1", "true", "yes", "on"}


def _csv_env(name: str) -> tuple[str, ...]:
    value = os.environ.get(name, "")
    return tuple(item.strip() for item in value.split(",") if item.strip())


def _path_env(name: str) -> Path | None:
    value = os.environ.get(name, "").strip()
    return Path(value).expanduser() if value else None


def _shadow_atom_budget(token_budget: int) -> int:
    return max(1, min(50, max(1, int(token_budget)) // 100))


async def run_memory_kernel_context_compiler_shadow(
    bundle: ContextBundleRecord,
    *,
    query: str | None,
    token_budget: int,
    enabled: bool,
    home: Path | None,
    surface_ids: tuple[str, ...],
    callback: Callable[[object], object] | None,
) -> None:
    """Run MemoryKernel context parity without altering compiled context."""

    env_enabled = _truthy_env("DHARMA_MEMORY_KERNEL_CONTEXT_COMPILER_SHADOW")
    global_env_enabled = _truthy_env("DHARMA_MEMORY_KERNEL_CONTEXT_SHADOW")
    if not enabled and not env_enabled and not global_env_enabled:
        return
    try:
        from dharma_swarm.memory_kernel import (
            CensusConfig,
            MemoryContextBudget,
            MemoryKernel,
            MemoryKernelConfig,
            run_context_parity_eval,
        )

        resolved_surfaces = (
            surface_ids
            or _csv_env("DHARMA_MEMORY_KERNEL_CONTEXT_COMPILER_SURFACES")
            or _csv_env("DHARMA_MEMORY_KERNEL_CONTEXT_SURFACES")
        )
        resolved_home = home or _path_env("DHARMA_MEMORY_KERNEL_HOME")
        kernel = None
        if resolved_home is not None and resolved_surfaces:
            kernel = MemoryKernel(
                MemoryKernelConfig(
                    census=CensusConfig(
                        repo_root=Path.cwd(),
                        home=resolved_home,
                        include_discovered=False,
                    )
                )
            )
        atom_budget = _shadow_atom_budget(token_budget)
        report = run_context_parity_eval(
            query=query,
            current_context_text=bundle.rendered_text,
            state_dir=None,
            memory_kernel=kernel,
            memory_surface_ids=resolved_surfaces,
            budget=MemoryContextBudget(
                max_candidate_atoms=atom_budget,
                max_admitted_atoms=max(1, min(atom_budget, 8)),
                include_content=False,
            ),
            allow_current_semantic_search=False,
        )
        if callback:
            callback_result = callback(report)
            if hasattr(callback_result, "__await__"):
                await callback_result
        logger.debug(
            "MemoryKernel context compiler shadow parity: bundle_id=%s hard_failures=%s warnings=%s metrics=%s",
            bundle.bundle_id,
            report.hard_failure_count,
            report.warning_count,
            report.metric_count,
        )
    except Exception:
        logger.debug("MemoryKernel context compiler shadow failed", exc_info=True)
