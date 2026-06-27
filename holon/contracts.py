"""Standalone Holon runtime contracts."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class LLMRequest:
    model: str
    messages: list[dict[str, Any]]
    system: str = ""
    tools: list[dict[str, Any]] = field(default_factory=list)


@dataclass(frozen=True)
class ProviderAttempt:
    provider: str
    model: str
    status: str
    latency_ms: int = 0
    cost_usd: float = 0.0
    finish_reason: str = ""
    error: str = ""


@dataclass(frozen=True)
class ArtifactRef:
    kind: str
    path: str
    digest: str


@dataclass(frozen=True)
class ToolCallRecord:
    name: str
    status: str
    arguments: dict[str, Any] = field(default_factory=dict)
    result: Any = None
    error: str = ""


@dataclass
class HolonCycleResult:
    status: str
    reply: str
    task: str = ""
    cycle: int | None = None
    provider: str = ""
    model: str = ""
    cost_usd: float = 0.0
    finish_reason: str = ""
    artifacts: list[ArtifactRef] = field(default_factory=list)
    receipt_refs: list[str] = field(default_factory=list)
    verifier_refs: list[str] = field(default_factory=list)
    provider_attempts: list[ProviderAttempt] = field(default_factory=list)
    tool_calls: list[ToolCallRecord] = field(default_factory=list)
    error: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["artifacts"] = [asdict(item) for item in self.artifacts]
        data["provider_attempts"] = [asdict(item) for item in self.provider_attempts]
        data["tool_calls"] = [asdict(item) for item in self.tool_calls]
        return data


def result_from_dict(data: dict[str, Any]) -> HolonCycleResult:
    return HolonCycleResult(
        status=str(data.get("status", "")),
        reply=str(data.get("reply", "")),
        task=str(data.get("task", "")),
        cycle=data.get("cycle"),
        provider=str(data.get("provider", "")),
        model=str(data.get("model", "")),
        cost_usd=float(data.get("cost_usd", 0.0) or 0.0),
        finish_reason=str(data.get("finish_reason", "")),
        artifacts=[
            ArtifactRef(
                kind=str(item.get("kind", "")),
                path=str(item.get("path", "")),
                digest=str(item.get("digest", "")),
            )
            for item in data.get("artifacts", [])
            if isinstance(item, dict)
        ],
        receipt_refs=[str(item) for item in data.get("receipt_refs", [])],
        verifier_refs=[str(item) for item in data.get("verifier_refs", [])],
        provider_attempts=[
            ProviderAttempt(
                provider=str(item.get("provider", "")),
                model=str(item.get("model", "")),
                status=str(item.get("status", "")),
                latency_ms=int(item.get("latency_ms", 0) or 0),
                cost_usd=float(item.get("cost_usd", 0.0) or 0.0),
                finish_reason=str(item.get("finish_reason", "")),
                error=str(item.get("error", "")),
            )
            for item in data.get("provider_attempts", [])
            if isinstance(item, dict)
        ],
        tool_calls=[
            ToolCallRecord(
                name=str(item.get("name", "")),
                status=str(item.get("status", "")),
                arguments=dict(item.get("arguments") or {}),
                result=item.get("result"),
                error=str(item.get("error", "")),
            )
            for item in data.get("tool_calls", [])
            if isinstance(item, dict)
        ],
        error=str(data.get("error", "")),
        metadata=dict(data.get("metadata") or {}),
    )
