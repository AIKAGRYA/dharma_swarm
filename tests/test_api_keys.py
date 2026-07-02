from __future__ import annotations

import builtins
import importlib
import sys

from dharma_swarm.api_keys import (
    ALL_API_KEY_ENV_KEYS,
    CHAT_PROVIDER_API_KEY_ENV_KEYS,
    DASHBOARD_API_KEY_ENV,
    DGC_DATA_FLYWHEEL_API_KEY_ENV,
    DGC_KAIZENOPS_API_KEY_ENV,
    DGC_RECIPROCITY_COMMONS_API_KEY_ENV,
    FINNHUB_API_KEY_ENV,
    FRED_API_KEY_ENV,
    GINKO_API_KEY_ENV_VARS,
    OPENROUTER_API_KEY_ENV,
    RUNTIME_PROVIDER_API_KEY_ENV_KEYS,
    env_has_value,
    env_value,
    has_any_llm,
    provider_api_key_env,
)
from dharma_swarm.models import ProviderType


def test_package_registry_imports_without_root_api_keys(monkeypatch) -> None:
    original_import = builtins.__import__

    def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "api_keys" and name not in sys.modules:
            raise ModuleNotFoundError("No module named 'api_keys'")
        return original_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    sys.modules.pop("api_keys", None)
    sys.modules.pop("dharma_swarm.api_keys", None)

    module = importlib.import_module("dharma_swarm.api_keys")

    assert module.DASHBOARD_API_KEY_ENV == "DASHBOARD_API_KEY"
    assert module.RUNTIME_PROVIDER_API_KEY_ENV_KEYS
    assert module.provider_api_key_env(ProviderType.ANTHROPIC) == "ANTHROPIC_API_KEY"


def test_provider_registry_covers_runtime_providers() -> None:
    assert provider_api_key_env(ProviderType.ANTHROPIC) == "ANTHROPIC_API_KEY"
    assert provider_api_key_env(ProviderType.OPENROUTER_FREE) == OPENROUTER_API_KEY_ENV
    assert provider_api_key_env(ProviderType.OLLAMA) == "OLLAMA_API_KEY"
    assert provider_api_key_env(ProviderType.CHUTES) == "CHUTES_API_KEY"
    assert provider_api_key_env(ProviderType.KIMI_CODE) == "KIMI_API_KEY"


def test_runtime_provider_registry_is_unique() -> None:
    assert len(RUNTIME_PROVIDER_API_KEY_ENV_KEYS) == len(set(RUNTIME_PROVIDER_API_KEY_ENV_KEYS))
    assert OPENROUTER_API_KEY_ENV in RUNTIME_PROVIDER_API_KEY_ENV_KEYS


def test_ginko_registry_uses_canonical_env_names() -> None:
    assert GINKO_API_KEY_ENV_VARS == {
        "openrouter": OPENROUTER_API_KEY_ENV,
        "fred": FRED_API_KEY_ENV,
        "finnhub": FINNHUB_API_KEY_ENV,
        "ollama": "OLLAMA_API_KEY",
    }


def test_all_api_key_registry_contains_system_services() -> None:
    for env_var in (
        DASHBOARD_API_KEY_ENV,
        DGC_DATA_FLYWHEEL_API_KEY_ENV,
        DGC_KAIZENOPS_API_KEY_ENV,
        DGC_RECIPROCITY_COMMONS_API_KEY_ENV,
    ):
        assert env_var in ALL_API_KEY_ENV_KEYS


def test_chat_provider_registry_matches_dashboard_surface() -> None:
    assert CHAT_PROVIDER_API_KEY_ENV_KEYS[ProviderType.OPENROUTER.value] == OPENROUTER_API_KEY_ENV
    assert CHAT_PROVIDER_API_KEY_ENV_KEYS[ProviderType.NVIDIA_NIM.value] == "NVIDIA_NIM_API_KEY"
    assert CHAT_PROVIDER_API_KEY_ENV_KEYS[ProviderType.KIMI_CODE.value] == "KIMI_API_KEY"


def test_env_value_empty_mapping_does_not_read_real_shell(monkeypatch) -> None:
    monkeypatch.setenv(OPENROUTER_API_KEY_ENV, "real-shell-key")

    assert env_value(OPENROUTER_API_KEY_ENV, {}) is None


def test_has_any_llm_uses_canonical_runtime_keys() -> None:
    assert has_any_llm({}) is False
    assert has_any_llm({OPENROUTER_API_KEY_ENV: "or-key"}) is True


def test_env_helpers_trim_and_detect_presence() -> None:
    env = {"OPENAI_API_KEY": "  test-key  ", "EMPTY_API_KEY": "   "}
    assert env_value("OPENAI_API_KEY", env) == "test-key"
    assert env_value("EMPTY_API_KEY", env) is None
    assert env_has_value("OPENAI_API_KEY", env) is True
    assert env_has_value("EMPTY_API_KEY", env) is False
