"""Structured backend protocol models for Deep Agent local tools."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from pydantic import BaseModel, Field


class BackendToolResult(BaseModel):
    """Common structured result contract for local tool execution."""

    ok: bool
    content: str | None = None
    result: str | list[str] | dict[str, Any] | None = None
    error: str | None = None
    path: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    truncated: bool = False
    bytes_read: int | None = None
    side_effect_id: str | None = None
    rendered_text: str


class ReadResult(BackendToolResult):
    offset: int = 1
    limit: int = 0


class WriteResult(BackendToolResult):
    bytes_written: int = 0


class EditResult(BackendToolResult):
    replacements: int = 0


class LsResult(BackendToolResult):
    entries: list[str] = Field(default_factory=list)


class GlobResult(BackendToolResult):
    matches: list[str] = Field(default_factory=list)


class GrepResult(BackendToolResult):
    matches: list[str] = Field(default_factory=list)


class ExecuteResult(BackendToolResult):
    exit_code: int | None = None
    stdout: str = ""
    stderr: str = ""
    duration_seconds: float | None = None
    timed_out: bool = False


class FetchUrlResult(BackendToolResult):
    url: str | None = None


class WebSearchResult(BackendToolResult):
    query: str | None = None
    backend: str | None = None


def stable_side_effect_id(tool_name: str, payload: dict[str, Any]) -> str:
    """Derive a deterministic id for side-effecting tool requests."""

    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    digest = hashlib.sha256(f"{tool_name}:{canonical}".encode("utf-8")).hexdigest()
    return f"{tool_name}-{digest[:16]}"
