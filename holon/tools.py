"""Tool registry for standalone Holon."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from holon.contracts import ArtifactRef, ToolCallRecord


ToolHandler = Callable[[dict[str, Any]], Any]


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    handler: ToolHandler
    schema: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ToolResult:
    record: ToolCallRecord
    artifact: ArtifactRef | None = None


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, ToolSpec] = {}

    def register(self, spec: ToolSpec) -> None:
        self._tools[spec.name] = spec

    def list_specs(self) -> list[dict[str, Any]]:
        return [
            {"name": spec.name, "description": spec.description, "schema": spec.schema}
            for spec in self._tools.values()
        ]

    def run(self, name: str, arguments: dict[str, Any]) -> ToolResult:
        spec = self._tools.get(name)
        if spec is None:
            return ToolResult(ToolCallRecord(name=name, status="failed", arguments=arguments, error="tool not registered"))
        try:
            result = spec.handler(arguments)
            artifact = _artifact_from_result(result)
            return ToolResult(ToolCallRecord(name=name, status="success", arguments=arguments, result=result), artifact)
        except Exception as exc:
            return ToolResult(
                ToolCallRecord(
                    name=name,
                    status="failed",
                    arguments=arguments,
                    error=f"{type(exc).__name__}: {exc}"[:300],
                )
            )


def default_tool_registry(*, artifact_root: Path | None = None) -> ToolRegistry:
    registry = ToolRegistry()
    root = artifact_root

    def write_artifact(arguments: dict[str, Any]) -> dict[str, str]:
        if root is None:
            raise RuntimeError("artifact_root is required for write_artifact")
        name = str(arguments.get("name") or "artifact.json")
        content = arguments.get("content", "")
        path = root / _safe_name(name)
        path.parent.mkdir(parents=True, exist_ok=True)
        text = content if isinstance(content, str) else json.dumps(content, sort_keys=True, indent=2)
        path.write_text(text, encoding="utf-8")
        digest = "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()
        return {"path": str(path), "digest": digest}

    registry.register(
        ToolSpec(
            name="write_artifact",
            description="Write a bounded artifact into the Holon artifact directory.",
            handler=write_artifact,
            schema={"name": "string", "content": "string|object"},
        )
    )
    return registry


def _safe_name(name: str) -> str:
    cleaned = "".join(ch if ch.isalnum() or ch in "._-/" else "_" for ch in name)
    cleaned = cleaned.strip("/.") or "artifact.json"
    parts = [part for part in cleaned.split("/") if part not in {"", ".", ".."}]
    return "/".join(parts)


def _artifact_from_result(result: Any) -> ArtifactRef | None:
    if not isinstance(result, dict):
        return None
    path = str(result.get("path") or "")
    digest = str(result.get("digest") or "")
    if not path or not digest:
        return None
    return ArtifactRef(kind=str(result.get("kind") or "file"), path=path, digest=digest)
