"""Provider adapter base abstractions for the DGC TUI engine."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Flag, auto
from typing import Any, AsyncIterator

from dharma_swarm.terminal_engine.events import CanonicalEventType


class Capability(Flag):
    STREAMING = auto()
    TOOL_USE = auto()
    THINKING = auto()
    VISION = auto()
    JSON_SCHEMA = auto()
    PARALLEL_TOOLS = auto()
    RESUME = auto()
    COST_TRACKING = auto()
    CONTEXT_USAGE = auto()
    SYSTEM_PROMPT = auto()
    CANCEL = auto()


@dataclass
class ModelProfile:
    """Static metadata for a model available through this provider."""

    provider_id: str = ""
    model_id: str = ""
    display_name: str = ""
    capabilities: Capability = Capability(0)
    max_input_tokens: int = 0
    max_output_tokens: int = 0
    cost_per_input_mtok: float = 0.0
    cost_per_output_mtok: float = 0.0
    extra: dict[str, Any] = field(default_factory=dict)

    def supports(self, cap: Capability) -> bool:
        return bool(self.capabilities & cap)


@dataclass
class ProviderConfig:
    """Provider connection settings."""

    provider_id: str = ""
    api_key: str = ""
    base_url: str = ""
    default_model: str = ""
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class CompletionRequest:
    """Provider-agnostic completion request envelope."""

    prompt: str = ""
    model: str = ""
    system_prompt: str = ""
    messages: list[dict[str, Any]] = field(default_factory=list)
    tools: list[dict[str, Any]] = field(default_factory=list)
    tool_choice: str = ""
    temperature: float = 0.7
    max_tokens: int = 4096
    stop_sequences: list[str] = field(default_factory=list)
    enable_thinking: bool = False
    resume_session_id: str = ""
    provider_options: dict[str, Any] = field(default_factory=dict)


class ProviderAdapter(ABC):
    """Abstract adapter that normalizes a provider's wire protocol to canonical events."""

    @property
    @abstractmethod
    def provider_id(self) -> str: ...

    @abstractmethod
    def list_models(self) -> list[str]: ...

    @abstractmethod
    def get_profile(self, model_id: str) -> ModelProfile | None: ...

    @abstractmethod
    async def stream(
        self, request: CompletionRequest, session_id: str
    ) -> AsyncIterator[CanonicalEventType]: ...

    @abstractmethod
    async def cancel(self) -> None: ...

    @abstractmethod
    async def close(self) -> None: ...
