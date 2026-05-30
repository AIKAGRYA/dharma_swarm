"""Unit tests for dharma_swarm.provider_registry.

The registry is purely additive scaffolding. These tests prove:

  - register_provider decorator returns the class unchanged
  - duplicate registration raises ProviderAlreadyRegisteredError
  - invalid provider_id values are rejected at decoration time
  - get_registered_provider raises KeyError for unknown ids
  - registered_provider_ids() returns sorted ids
  - clear_registry_for_tests() does what it says

These tests must NOT depend on any provider in providers.py being registered.
The registry starts empty and stays empty unless tests opt in.
"""

from __future__ import annotations

import pytest

from dharma_swarm.provider_registry import (
    PROVIDER_REGISTRY,
    ProviderAlreadyRegisteredError,
    ProviderFactory,
    clear_registry_for_tests,
    get_registered_provider,
    register_provider,
    registered_provider_ids,
    render_registry_summary,
)


@pytest.fixture(autouse=True)
def _isolate_registry():
    """Snapshot and restore the global registry around every test."""
    snapshot = dict(PROVIDER_REGISTRY)
    clear_registry_for_tests()
    try:
        yield
    finally:
        clear_registry_for_tests()
        PROVIDER_REGISTRY.update(snapshot)


def test_register_provider_returns_class_unchanged() -> None:
    @register_provider("alpha", default_model="alpha-v1", requires_env_vars=("ALPHA_KEY",))
    class Alpha:
        marker = "alpha"

    assert Alpha.marker == "alpha"
    assert "alpha" in PROVIDER_REGISTRY
    f = PROVIDER_REGISTRY["alpha"]
    assert isinstance(f, ProviderFactory)
    assert f.cls is Alpha
    assert f.default_model == "alpha-v1"
    assert f.requires_env_vars == ("ALPHA_KEY",)


def test_register_provider_duplicate_raises() -> None:
    @register_provider("dup")
    class First:
        pass

    with pytest.raises(ProviderAlreadyRegisteredError) as exc_info:
        @register_provider("dup")
        class Second:
            pass

    assert "already registered" in str(exc_info.value)


def test_register_provider_rejects_empty_id() -> None:
    with pytest.raises(ValueError):
        @register_provider("")
        class Bad:
            pass


def test_register_provider_rejects_whitespace_id() -> None:
    with pytest.raises(ValueError):
        @register_provider("with space")
        class Bad:
            pass


def test_get_registered_provider_returns_factory() -> None:
    @register_provider("beta")
    class Beta:
        pass

    f = get_registered_provider("beta")
    assert f.cls is Beta
    assert f.provider_id == "beta"


def test_get_registered_provider_unknown_raises() -> None:
    with pytest.raises(KeyError) as exc_info:
        get_registered_provider("nonexistent")
    assert "nonexistent" in str(exc_info.value)


def test_registered_provider_ids_is_sorted() -> None:
    @register_provider("zeta")
    class Zeta:
        pass

    @register_provider("alpha")
    class Alpha:
        pass

    @register_provider("mu")
    class Mu:
        pass

    assert registered_provider_ids() == ["alpha", "mu", "zeta"]


def test_clear_registry_for_tests_clears() -> None:
    @register_provider("temp")
    class Temp:
        pass

    assert "temp" in PROVIDER_REGISTRY
    clear_registry_for_tests()
    assert PROVIDER_REGISTRY == {}


def test_render_registry_summary_empty() -> None:
    assert "empty registry" in render_registry_summary()


def test_render_registry_summary_populated() -> None:
    @register_provider("alpha", default_model="m1", requires_env_vars=("K",))
    class Alpha:
        pass

    s = render_registry_summary()
    assert "alpha" in s
    assert "default_model=m1" in s
    assert "env=K" in s


def test_provider_factory_is_frozen() -> None:
    @register_provider("gamma")
    class Gamma:
        pass

    f = PROVIDER_REGISTRY["gamma"]
    with pytest.raises(Exception):  # FrozenInstanceError, but subclass varies
        f.provider_id = "other"  # type: ignore[misc]
