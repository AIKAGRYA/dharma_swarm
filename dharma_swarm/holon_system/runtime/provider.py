"""Facade: provider/model resolution for holon wakes.

Canonical owner: dharma_swarm/runtime_provider.py. This facade exists so the
holon_system package exposes the model-agnostic wake resolver without creating a
second model router.
"""

from __future__ import annotations

from dharma_swarm.runtime_provider import (
    RuntimeProviderConfig,
    preferred_runtime_provider_configs,
    resolve_runtime_provider_config,
    resolve_top_available_at_wake,
)

__all__ = [
    "RuntimeProviderConfig",
    "preferred_runtime_provider_configs",
    "resolve_runtime_provider_config",
    "resolve_top_available_at_wake",
]
