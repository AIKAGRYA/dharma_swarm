"""Provider registry — opt-in scaffold for the eventual providers/ package split.

Purpose
-------
`dharma_swarm/providers.py` is currently a 3,005-LOC single-file module hosting
14 LLM provider classes (Anthropic, OpenAI, OpenRouter, NVIDIANIM, Groq,
Cerebras, SiliconFlow, Together, Fireworks, GoogleAI, SambaNova, Mistral,
Chutes, Ollama, OpenRouterFree, ClaudeCode subprocess, Codex subprocess) plus
a 1,200-LOC ModelRouter. 40 import sites across tests and runtime.

This module introduces, purely additively, two things:

  1. ``PROVIDER_REGISTRY`` — a dict mapping a stable provider-id string to a
     ProviderFactory descriptor.
  2. ``register_provider(...)`` — a decorator that LLMProvider subclasses can
     adopt to register themselves at import time.

Nothing in ``providers.py`` is required to change to make this module work,
and no existing import site is affected. Code that wants the registry asks
for it explicitly. Code that doesn't, keeps working as before.

Why scaffold first
------------------
Splitting providers.py into a ``providers/`` subpackage requires renaming
``providers.py`` (a Python module and a same-name subpackage cannot coexist
in the same parent package). That rename touches 40 import sites and is its
own surgical PR. This registry module is the *contract* the eventual split
will use. Providers can adopt ``@register_provider(...)`` one-by-one, each
adoption being independently testable.

Design constraints
------------------
- **Doctrine-safe:** zero new substrate, zero meta-framework. One file, one
  dict, one decorator. The registry is data; ``create_default_router()`` and
  routing logic remain authoritative.
- **Frozen surfaces:** none touched. Imports stdlib only.
- **Backward compatibility:** an LLMProvider subclass without
  ``@register_provider`` continues to work exactly as today. The registry
  starts empty and only grows by explicit opt-in.
- **Idempotent:** registering the same provider id twice raises a clear
  ``ProviderAlreadyRegisteredError`` rather than silently shadowing.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, TypeVar

__all__ = [
    "ProviderRegistryError",
    "ProviderAlreadyRegisteredError",
    "ProviderFactory",
    "PROVIDER_REGISTRY",
    "register_provider",
    "get_registered_provider",
    "registered_provider_ids",
    "clear_registry_for_tests",
]


class ProviderRegistryError(RuntimeError):
    """Base for provider-registry-specific errors."""


class ProviderAlreadyRegisteredError(ProviderRegistryError):
    """Raised when two providers attempt to register the same provider_id."""


@dataclass(frozen=True)
class ProviderFactory:
    """Descriptor for one registered provider class.

    Attributes
    ----------
    provider_id:
        Stable, lowercase, hyphen-or-underscore-free identifier
        (e.g. ``"anthropic"``, ``"openrouter_free"``). Used as the registry
        key and as the wire-level provider identifier in routing decisions
        and EvidenceReceipts.
    cls:
        The LLMProvider subclass.
    default_model:
        Optional default model id this provider should be invoked with when
        no explicit model is given.
    requires_env_vars:
        Tuple of environment-variable names the provider needs at use-time.
        Empty for subprocess-style providers (ClaudeCode, Codex) that resolve
        credentials through other channels.
    notes:
        Free-form comment for the registry inspector — never load-bearing.
    """

    provider_id: str
    cls: type
    default_model: str | None = None
    requires_env_vars: tuple[str, ...] = ()
    notes: str = ""


# The registry itself. Mutated only by ``register_provider`` and
# ``clear_registry_for_tests``. Read by anyone who wants to enumerate
# available providers.
PROVIDER_REGISTRY: dict[str, ProviderFactory] = {}


_T = TypeVar("_T", bound=type)


def register_provider(
    provider_id: str,
    *,
    default_model: str | None = None,
    requires_env_vars: tuple[str, ...] = (),
    notes: str = "",
) -> Callable[[_T], _T]:
    """Class decorator that registers an LLMProvider subclass into the registry.

    Usage::

        from dharma_swarm.provider_registry import register_provider

        @register_provider(
            "anthropic",
            default_model="claude-sonnet-4-5",
            requires_env_vars=("ANTHROPIC_API_KEY",),
        )
        class AnthropicProvider(LLMProvider):
            ...

    The decorator returns the class unchanged. Its only side effect is
    populating ``PROVIDER_REGISTRY``. Decorated classes remain importable
    and usable through every existing pathway.

    Raises
    ------
    ProviderAlreadyRegisteredError
        If ``provider_id`` is already present in the registry.
    ValueError
        If ``provider_id`` is empty or contains whitespace.
    """
    if not provider_id or any(ch.isspace() for ch in provider_id):
        raise ValueError(
            f"provider_id must be a non-empty, whitespace-free string; "
            f"got {provider_id!r}"
        )

    def _decorator(cls: _T) -> _T:
        if provider_id in PROVIDER_REGISTRY:
            existing = PROVIDER_REGISTRY[provider_id]
            raise ProviderAlreadyRegisteredError(
                f"provider_id {provider_id!r} already registered to "
                f"{existing.cls.__module__}.{existing.cls.__qualname__}; "
                f"refusing to shadow with "
                f"{cls.__module__}.{cls.__qualname__}"
            )
        PROVIDER_REGISTRY[provider_id] = ProviderFactory(
            provider_id=provider_id,
            cls=cls,
            default_model=default_model,
            requires_env_vars=tuple(requires_env_vars),
            notes=notes,
        )
        return cls

    return _decorator


def get_registered_provider(provider_id: str) -> ProviderFactory:
    """Look up a registered provider by id.

    Raises
    ------
    KeyError
        If ``provider_id`` is not in the registry.
    """
    try:
        return PROVIDER_REGISTRY[provider_id]
    except KeyError as exc:
        raise KeyError(
            f"provider_id {provider_id!r} not in registry; "
            f"known: {sorted(PROVIDER_REGISTRY)}"
        ) from exc


def registered_provider_ids() -> list[str]:
    """Return the sorted list of currently registered provider ids."""
    return sorted(PROVIDER_REGISTRY)


def clear_registry_for_tests() -> None:
    """Clear the registry. Intended ONLY for unit tests that build their own.

    Production code must never call this. Tests that want isolation should
    snapshot the registry, call this, and restore the snapshot in teardown.
    """
    PROVIDER_REGISTRY.clear()


# ---------------------------------------------------------------------------
# Inspector helpers — for the manifest checker and for human review.
# ---------------------------------------------------------------------------


def render_registry_summary() -> str:
    """Return a human-readable single-string summary of the registry."""
    if not PROVIDER_REGISTRY:
        return "(empty registry — no providers have opted in yet)"
    lines = []
    for pid in registered_provider_ids():
        f = PROVIDER_REGISTRY[pid]
        env = ", ".join(f.requires_env_vars) or "—"
        lines.append(
            f"  {pid:<22s}  {f.cls.__module__}.{f.cls.__qualname__:<28s}  "
            f"default_model={f.default_model or '—'}  env={env}"
        )
    return "\n".join(lines)
