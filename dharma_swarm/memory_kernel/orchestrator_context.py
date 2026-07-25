"""Orchestrator helpers for Memory Kernel-backed context bundles."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

MEMORY_KERNEL_DISPATCH_KEYS = (
    "memory_kernel_status",
    "memory_kernel_pack_id",
    "memory_kernel_admitted_count",
    "memory_kernel_omitted_count",
    "memory_kernel_warnings",
    "memory_kernel_isolation_applied",
    "memory_kernel_isolation_agent_id",
    "memory_kernel_allowed_agent_ids",
    "memory_kernel_allowed_scopes",
    "memory_kernel_allowed_memory_lanes",
)


def build_orchestrator_memory_kernel(*, repo_root: Path) -> Any:
    from dharma_swarm.memory_kernel import CensusConfig, MemoryKernel, MemoryKernelConfig

    memory_kernel_home = Path(
        os.getenv("DHARMA_MEMORY_KERNEL_HOME") or Path.home()
    ).expanduser()
    return MemoryKernel(
        MemoryKernelConfig(
            census=CensusConfig(
                repo_root=repo_root,
                home=memory_kernel_home,
                include_discovered=False,
            )
        )
    )


def memory_kernel_dispatch_metadata(
    bundle_metadata: dict[str, Any],
) -> dict[str, Any]:
    kernel_meta = dict(bundle_metadata.get("memory_kernel_default") or {})
    if not kernel_meta:
        return {}
    return {
        "memory_kernel_status": kernel_meta.get("status", "unknown"),
        "memory_kernel_pack_id": kernel_meta.get("pack_id", ""),
        "memory_kernel_admitted_count": kernel_meta.get("admitted_count", 0),
        "memory_kernel_omitted_count": kernel_meta.get("omitted_count", 0),
        "memory_kernel_warnings": kernel_meta.get("warnings", []),
        "memory_kernel_isolation_applied": bool(kernel_meta.get("isolation_applied")),
        "memory_kernel_isolation_agent_id": kernel_meta.get("isolation_agent_id", ""),
        "memory_kernel_allowed_agent_ids": kernel_meta.get("allowed_agent_ids", []),
        "memory_kernel_allowed_scopes": kernel_meta.get("allowed_scopes", []),
        "memory_kernel_allowed_memory_lanes": kernel_meta.get("allowed_memory_lanes", []),
    }
