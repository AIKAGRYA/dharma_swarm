"""DHARMA SWARM — Darwin-Heuristic Autonomous Recursive Meta-Agent Swarm."""

from typing import TYPE_CHECKING

__version__ = "0.1.0"

# Public re-exports are lazy (PEP 562). Importing models eagerly makes every
# dependency-light leaf import require pydantic, while eager providers create
# a load-time import cycle through the package root:
#   dharma_swarm/__init__ -> providers -> provider_policy -> smart_router
#   -> router_v1 -> `from dharma_swarm import model_pool` (back into this package
#   while __init__ is still executing) — a latent half-initialized-module boot
#   fragility. Deferring the binding breaks the cycle at its source; the public
#   `from dharma_swarm import ClaudeCodeProvider` API is unchanged.
if TYPE_CHECKING:
    from dharma_swarm.models import ProviderType  # noqa: F401
    from dharma_swarm.providers import (  # noqa: F401
        ClaudeCodeProvider,
        CodexProvider,
        OpenRouterFreeProvider,
    )

_LAZY_EXPORTS = {
    "ProviderType": "dharma_swarm.models",
    "ClaudeCodeProvider": "dharma_swarm.providers",
    "CodexProvider": "dharma_swarm.providers",
    "OpenRouterFreeProvider": "dharma_swarm.providers",
}


def __getattr__(name: str):
    module_path = _LAZY_EXPORTS.get(name)
    if module_path is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    import importlib

    value = getattr(importlib.import_module(module_path), name)
    globals()[name] = value
    return value


def __dir__():
    return sorted([*globals().keys(), *_LAZY_EXPORTS])
