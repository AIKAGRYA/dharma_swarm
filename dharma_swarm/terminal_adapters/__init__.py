"""Provider adapter registry for the Bun terminal runtime."""

from .base import (
    Capability,
    CompletionRequest,
    ModelProfile,
    ProviderAdapter,
    ProviderConfig,
)
from .claude import ClaudeAdapter, CLAUDE_CAPABILITIES

# Graceful imports for adapters with missing source files (M3→M5 migration gap).
# The bridge boots with whatever adapters are available.
try:
    from .codex import CodexAdapter, CODEX_CAPABILITIES
except ImportError:
    CodexAdapter = None  # type: ignore[assignment,misc]
    CODEX_CAPABILITIES = Capability(0)

try:
    from .ollama import OllamaAdapter, OLLAMA_CAPABILITIES
except ImportError:
    OllamaAdapter = None  # type: ignore[assignment,misc]
    OLLAMA_CAPABILITIES = Capability(0)

try:
    from .openrouter import OpenRouterAdapter, OPENROUTER_CAPABILITIES
except ImportError:
    OpenRouterAdapter = None  # type: ignore[assignment,misc]
    OPENROUTER_CAPABILITIES = Capability(0)

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
    "OLLAMA_CAPABILITIES",
    "OpenRouterAdapter",
    "OPENROUTER_CAPABILITIES",
]
