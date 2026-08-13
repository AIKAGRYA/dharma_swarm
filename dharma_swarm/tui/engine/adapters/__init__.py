"""Provider adapter registry exports for the DGC TUI engine."""

from .base import (
    Capability,
    CompletionRequest,
    ModelProfile,
    ProviderAdapter,
    ProviderConfig,
)
from .claude import ClaudeAdapter, CLAUDE_CAPABILITIES
from .codex import CODEX_CAPABILITIES, CodexAdapter
from .ollama import (
    OLLAMA_LOCAL_PREVIEW_BASE_URL,
    OLLAMA_LOCAL_PREVIEW_CAPABILITIES,
    OLLAMA_LOCAL_PREVIEW_ENV,
    OllamaAdapter,
)
from .openrouter import OpenRouterAdapter, OPENROUTER_CAPABILITIES

__all__ = [
    "Capability",
    "CompletionRequest",
    "ModelProfile",
    "ProviderAdapter",
    "ProviderConfig",
    "ClaudeAdapter",
    "CLAUDE_CAPABILITIES",
    "CodexAdapter",
    "CODEX_CAPABILITIES",
    "OllamaAdapter",
    "OLLAMA_LOCAL_PREVIEW_BASE_URL",
    "OLLAMA_LOCAL_PREVIEW_CAPABILITIES",
    "OLLAMA_LOCAL_PREVIEW_ENV",
    "OpenRouterAdapter",
    "OPENROUTER_CAPABILITIES",
]
