"""DGC TUI Engine — pure Python stream parsing, no Textual dependency."""

from typing import Any

from .events import (
    EVENT_TYPES,
    CanonicalEvent,
    ErrorEvent,
    RateLimitEvent as CanonicalRateLimitEvent,
    SessionEnd,
    SessionStart,
    TaskComplete,
    TaskProgress as CanonicalTaskProgress,
    TaskStarted as CanonicalTaskStarted,
    TextComplete,
    TextDelta,
    ThinkingComplete,
    ThinkingDelta,
    ToolArgumentsDelta,
    ToolCallComplete,
    ToolCallStart,
    ToolProgress as CanonicalToolProgress,
    ToolResult as CanonicalToolResult,
    UsageReport,
)
from .governance import GovernanceFilter, GovernancePolicy
from .event_types import (
    AssistantMessage,
    RateLimitEvent,
    ResultMessage,
    StreamDelta,
    SystemInit,
    TaskProgress,
    TaskStarted,
    ToolProgress,
    ToolResult,
)
from .session_state import SessionState
from .stream_parser import parse_ndjson_line


def __getattr__(name: str) -> Any:
    """Load cycle-forming compatibility exports only when requested."""

    if name == "ProviderRunner":
        from .provider_runner import ProviderRunner

        return ProviderRunner
    if name == "SessionStore":
        from .session_store import SessionStore

        return SessionStore
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "AssistantMessage",
    "CanonicalEvent",
    "CanonicalRateLimitEvent",
    "CanonicalTaskProgress",
    "CanonicalTaskStarted",
    "CanonicalToolProgress",
    "CanonicalToolResult",
    "ErrorEvent",
    "EVENT_TYPES",
    "GovernanceFilter",
    "GovernancePolicy",
    "ProviderRunner",
    "RateLimitEvent",
    "ResultMessage",
    "SessionEnd",
    "SessionState",
    "SessionStart",
    "StreamDelta",
    "SystemInit",
    "TaskComplete",
    "TaskProgress",
    "TaskStarted",
    "TextComplete",
    "TextDelta",
    "ThinkingComplete",
    "ThinkingDelta",
    "ToolArgumentsDelta",
    "ToolCallComplete",
    "ToolCallStart",
    "ToolProgress",
    "ToolResult",
    "UsageReport",
    "SessionStore",
    "parse_ndjson_line",
]
