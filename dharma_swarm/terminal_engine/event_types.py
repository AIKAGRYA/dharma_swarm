"""Typed dataclasses for all Claude Code NDJSON stream events.

Pure stdlib — no Pydantic, no Textual. These map 1:1 to the event types
emitted by ``claude --output-format stream-json``.

Event taxonomy mirrors the Claude Code CLI stream protocol.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class SystemInit:
    """Initial system event with session metadata."""

    type: str = "system"
    subtype: str = "init"
    session_id: str = ""
    model: str = ""
    cwd: str = ""
    permission_mode: str = ""
    claude_code_version: str = ""
    tools: list[str] = field(default_factory=list)
    mcp_servers: list[str] = field(default_factory=list)


@dataclass
class AssistantMessage:
    """Assistant text response with usage info."""

    type: str = "assistant"
    message: str = ""
    content_blocks: list[dict[str, Any]] = field(default_factory=list)
    usage: dict[str, Any] | None = None
    stop_reason: str = ""


@dataclass
class ToolResult:
    """Result returned by a tool invocation."""

    type: str = "tool_result"
    tool_use_id: str = ""
    tool_name: str = ""
    content: str = ""
    is_error: bool = False
    structured_result: Any = None
    duration_ms: float = 0.0


@dataclass
class StreamDelta:
    """Incremental streaming delta."""

    type: str = "content_block_delta"
    index: int = 0
    delta_type: str = ""
    text: str = ""
    content: str = ""
    block_index: int = 0
    parent_tool_use_id: str = ""


@dataclass
class ResultMessage:
    """Final result message with aggregated output."""

    type: str = "result"
    subtype: str = ""
    result_text: str = ""
    is_error: bool = False
    total_cost_usd: float = 0.0
    errors: list[str] = field(default_factory=list)
    model_usage: dict[str, Any] = field(default_factory=dict)


@dataclass
class ToolProgress:
    """Progress update for a running tool."""

    type: str = "tool_progress"
    tool_use_id: str = ""
    tool_name: str = ""
    elapsed_seconds: float = 0.0


@dataclass
class TaskStarted:
    """Agent task lifecycle start."""

    type: str = "task_started"
    task_id: str = ""
    description: str = ""
    tool_use_id: str = ""


@dataclass
class TaskProgress:
    """Agent task progress update."""

    type: str = "task_progress"
    task_id: str = ""
    summary: str = ""
    last_tool_name: str = ""
    usage: dict[str, Any] | None = None


@dataclass
class RateLimitEvent:
    """Rate limit status update."""

    type: str = "rate_limit"
    status: str = ""
    resets_at: str = ""
    utilization: float = 0.0
