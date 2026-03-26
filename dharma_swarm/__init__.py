"""DHARMA SWARM — Darwin-Heuristic Autonomous Recursive Meta-Agent Swarm."""

__version__ = "0.1.0"

# Lazy imports to support lightweight workers without full dependencies
def __getattr__(name):
    if name == "ProviderType":
        from dharma_swarm.models import ProviderType
        return ProviderType
    if name in ("ClaudeCodeProvider", "CodexProvider", "OpenRouterFreeProvider"):
        from dharma_swarm.providers import (
            ClaudeCodeProvider,
            CodexProvider,
            OpenRouterFreeProvider,
        )
        return locals()[name]
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")
