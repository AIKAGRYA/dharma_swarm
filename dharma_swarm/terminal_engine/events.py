"""Canonical provider-agnostic event schema for DGC TUI.

This module defines the normalized event envelope and payloads used by the
provider adapter layer. Events here are intentionally decoupled from any
single provider wire format (Claude NDJSON, OpenAI SSE, Ollama NDJSON, etc.).
"""

from __future__ import annotations

from dataclasses import dataclass, field
import time
from typing import Any

SCHEMA_VERSION = "1"


@dataclass
class CanonicalEvent:
    schema_version: str = SCHEMA_VERSION
    timestamp: float = field(default_factory=time.time)
    provider_id: str = ""
    session_id: str = ""
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass
class SessionStart(CanonicalEvent):
    type: str = "session_start"
    model: str = ""
    provider_session_id: str = ""
    capabilities: list[str] = field(default_factory=list)
    tools_available: list[str] = field(default_factory=list)
    system_info: dict[str, Any] = field(default_factory=dict)


@dataclass
class SessionEnd(CanonicalEvent):
    type: str = "session_end"
    success: bool = True
    error_code: str = ""
    error_message: str = ""


@dataclass
class TextDelta(CanonicalEvent):
    type: str = "text_delta"
    content: str = ""
    content_index: int = 0
    role: str = ""


@dataclass
class TextComplete(CanonicalEvent):
    type: str = "text_complete"
    content: str = ""
    content_index: int = 0
    role: str = ""


@dataclass
class ThinkingDelta(CanonicalEvent):
    type: str = "thinking_delta"
    content: str = ""


@dataclass
class ThinkingComplete(CanonicalEvent):
    type: str = "thinking_complete"
    content: str = ""
    is_redacted: bool = False


@dataclass
class ToolCallStart(CanonicalEvent):
    type: str = "tool_call_start"
    tool_call_id: str = ""
    tool_name: str = ""
    arguments_partial: str = ""


@dataclass
class ToolArgumentsDelta(CanonicalEvent):
    type: str = "tool_args_delta"
    tool_call_id: str = ""
    delta: str = ""


@dataclass
class ToolCallComplete(CanonicalEvent):
    type: str = "tool_call_complete"
    tool_call_id: str = ""
    tool_name: str = ""
    arguments: str = ""
    provider_options: dict[str, Any] = field(default_factory=dict)


@dataclass
class ToolResult(CanonicalEvent):
    type: str = "tool_result"
    tool_call_id: str = ""
    tool_name: str = ""
    content: str = ""
    is_error: bool = False
    structured_result: Any = None
    duration_ms: float = 0.0


@dataclass
class ToolProgress(CanonicalEvent):
    type: str = "tool_progress"
    tool_call_id: str = ""
    tool_name: str = ""
    elapsed_seconds: float = 0.0


@dataclass
class TaskStarted(CanonicalEvent):
    type: str = "task_started"
    task_id: str = ""
    description: str = ""
    parent_tool_call_id: str = ""


@dataclass
class TaskProgress(CanonicalEvent):
    type: str = "task_progress"
    task_id: str = ""
    summary: str = ""


@dataclass
class TaskComplete(CanonicalEvent):
    type: str = "task_complete"
    task_id: str = ""
    success: bool = True
    summary: str = ""


@dataclass
class UsageReport(CanonicalEvent):
    type: str = "usage"
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0
    thinking_tokens: int = 0
    total_cost_usd: float = 0.0
    model_breakdown: dict[str, Any] = field(default_factory=dict)


@dataclass
class ErrorEvent(CanonicalEvent):
    type: str = "error"
    code: str = ""
    message: str = ""
    retryable: bool = False
    retry_after_seconds: float = 0.0


@dataclass
class RateLimitEvent(CanonicalEvent):
    type: str = "rate_limit"
    status: str = ""
    utilization: float = 0.0
    resets_at: str = ""


@dataclass
class PermissionDecisionEvent(CanonicalEvent):
    type: str = "permission_decision"
    action_id: str = ""
    tool_name: str = ""
    risk: str = ""
    decision: str = ""
    rationale: str = ""
    policy_source: str = ""
    requires_confirmation: bool = False
    command_prefix: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class PermissionResolutionEvent(CanonicalEvent):
    type: str = "permission_resolution"
    action_id: str = ""
    resolution: str = ""
    resolved_at: str = ""
    actor: str = ""
    summary: str = ""
    note: str = ""
    enforcement_state: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class PermissionOutcomeEvent(CanonicalEvent):
    type: str = "permission_outcome"
    action_id: str = ""
    outcome: str = ""
    outcome_at: str = ""
    source: str = ""
    summary: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


EVENT_TYPES: dict[str, type[CanonicalEvent]] = {
    "session_start": SessionStart,
    "session_end": SessionEnd,
    "text_delta": TextDelta,
    "text_complete": TextComplete,
    "thinking_delta": ThinkingDelta,
    "thinking_complete": ThinkingComplete,
    "tool_call_start": ToolCallStart,
    "tool_args_delta": ToolArgumentsDelta,
    "tool_call_complete": ToolCallComplete,
    "tool_result": ToolResult,
    "tool_progress": ToolProgress,
    "task_started": TaskStarted,
    "task_progress": TaskProgress,
    "task_complete": TaskComplete,
    "usage": UsageReport,
    "error": ErrorEvent,
    "rate_limit": RateLimitEvent,
}

CanonicalEventType = dict[str, type[CanonicalEvent]]
