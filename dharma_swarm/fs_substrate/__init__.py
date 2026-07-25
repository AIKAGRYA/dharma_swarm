"""Filesystem-Native Context Substrate.

Slice A: turn an on-disk numbered-folder workspace + per-stage CONTEXT.md
contracts (Van Clief's ICM/MWP) into the swarm's existing primitives — Task
objects with depends_on edges, dispatched through spine.invoke_agent(), with
stage output handed off via handoff.py.

This package adds NO orchestrator, NO receipt type, and NO truth store. It
projects an on-disk declaration onto existing owners (spine, TaskBoard, handoff,
skills). The folder DECLARES the pipeline; the swarm EXECUTES it.

See docs/research/FILESYSTEM_AS_AGENT_SUBSTRATE_RESEARCH.md (the four powers +
the organism tie) and docs/research/FILESYSTEM_SUBSTRATE_SLICE_A_SPEC.md.
"""

from __future__ import annotations

from dharma_swarm.fs_substrate.stage_contracts import (
    StageContract,
    StageInput,
    StageOutput,
    StageWorkspace,
    WorkspaceError,
    load_workspace,
    parse_context_md,
    to_tasks,
)

__all__ = [
    "StageContract",
    "StageInput",
    "StageOutput",
    "StageWorkspace",
    "WorkspaceError",
    "load_workspace",
    "parse_context_md",
    "to_tasks",
]
