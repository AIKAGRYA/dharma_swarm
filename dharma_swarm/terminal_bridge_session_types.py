"""Shared state types for the terminal bridge session lanes."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass

from dharma_swarm.operator_core.session_lifecycle import SessionLifecycleRecorder


@dataclass
class _ActiveSessionRun:
    """Correlated identity and lifecycle for the one in-flight session turn."""

    request_id: str
    session_id: str
    provider_id: str
    model_id: str
    lifecycle: SessionLifecycleRecorder
    task: asyncio.Task[None] | None = None
    phase: str = "starting"
    cancel_requested: bool = False
    cancel_request_id: str | None = None
    cancel_reason: str | None = None
    terminal_emitted: bool = False
