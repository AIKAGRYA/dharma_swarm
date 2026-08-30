"""Canonical API key and endpoint env registry for DHARMA SWARM.

This package-local module is the single source of truth for every named
external API credential and provider endpoint env var used by first-party
code.
"""

from __future__ import annotations

import os
import re
import shlex
from pathlib import Path
from typing import Iterable, Mapping

ANTHROPIC_API_KEY_ENV = "ANTHROPIC_API_KEY"
OPENAI_API_KEY_ENV = "OPENAI_API_KEY"
OPENROUTER_API_KEY_ENV = "OPENROUTER_API_KEY"
NVIDIA_NIM_API_KEY_ENV = "NVIDIA_NIM_API_KEY"
OLLAMA_API_KEY_ENV = "OLLAMA_API_KEY"
GROQ_API_KEY_ENV = "GROQ_API_KEY"
CEREBRAS_API_KEY_ENV = "CEREBRAS_API_KEY"
SILICONFLOW_API_KEY_ENV = "SILICONFLOW_API_KEY"
TOGETHER_API_KEY_ENV = "TOGETHER_API_KEY"
FIREWORKS_API_KEY_ENV = "FIREWORKS_API_KEY"
GOOGLE_AI_API_KEY_ENV = "GOOGLE_AI_API_KEY"
SAMBANOVA_API_KEY_ENV = "SAMBANOVA_API_KEY"
MISTRAL_API_KEY_ENV = "MISTRAL_API_KEY"
CHUTES_API_KEY_ENV = "CHUTES_API_KEY"
ZHIPU_API_KEY_ENV = "ZHIPU_API_KEY"
KIMI_API_KEY_ENV = "KIMI_API_KEY"
MOONSHOT_API_KEY_ENV = "MOONSHOT_API_KEY"
NGC_API_KEY_ENV = "NGC_API_KEY"
NVIDIA_API_KEY_ENV = "NVIDIA_API_KEY"
SAKANA_API_KEY_ENV = "SAKANA_API_KEY"  # Fugu Ultra seat, ticket #1405 (no live client yet)

DASHBOARD_API_KEY_ENV = "DASHBOARD_API_KEY"
FRED_API_KEY_ENV = "FRED_API_KEY"
FINNHUB_API_KEY_ENV = "FINNHUB_API_KEY"

# Dashboard API ingress mode (WP-0S, TIT-010). Explicit production values
# select production-shaped fail-closed enforcement; explicit local values
# select the loopback-bound development lane; anything else is ambiguous and
# the ingress layer must pick the safer behavior.
DASHBOARD_API_MODE_ENV = "DHARMA_API_MODE"
API_MODE_PRODUCTION = "production"
API_MODE_LOCAL_DEV = "local-development"
API_MODE_AMBIGUOUS = "ambiguous"
_API_MODE_PRODUCTION_VALUES = frozenset({"production", "production-shaped", "prod"})
_API_MODE_LOCAL_DEV_VALUES = frozenset({"local-development", "local-dev", "dev"})


def dashboard_api_mode(env: Mapping[str, str] | None = None) -> str:
    """Resolve the declared dashboard API ingress mode.

    Returns API_MODE_PRODUCTION, API_MODE_LOCAL_DEV, or API_MODE_AMBIGUOUS.
    Unset, blank, and unrecognized values are ambiguous by design so the
    consumer cannot mistake a typo for an explicit mode selection.
    """
    source = os.environ if env is None else env
    raw = str(source.get(DASHBOARD_API_MODE_ENV, "") or "").strip().lower()
    if raw in _API_MODE_PRODUCTION_VALUES:
        return API_MODE_PRODUCTION
    if raw in _API_MODE_LOCAL_DEV_VALUES:
        return API_MODE_LOCAL_DEV
    return API_MODE_AMBIGUOUS

# Search backends
EXA_API_KEY_ENV = "EXA_API_KEY"
BRAVE_API_KEY_ENV = "BRAVE_API_KEY"
PPLX_API_KEY_ENV = "PPLX_API_KEY"  # also PERPLEXITY_API_KEY
JINA_API_KEY_ENV = "JINA_API_KEY"
FIRECRAWL_API_KEY_ENV = "FIRECRAWL_API_KEY"
DGC_DATA_FLYWHEEL_API_KEY_ENV = "DGC_DATA_FLYWHEEL_API_KEY"
DGC_KAIZENOPS_API_KEY_ENV = "DGC_KAIZENOPS_API_KEY"
DGC_RECIPROCITY_COMMONS_API_KEY_ENV = "DGC_RECIPROCITY_COMMONS_API_KEY"

OPENAI_BASE_URL_ENV = "OPENAI_BASE_URL"
OPENROUTER_BASE_URL_ENV = "OPENROUTER_BASE_URL"
NVIDIA_NIM_BASE_URL_ENV = "NVIDIA_NIM_BASE_URL"
OLLAMA_BASE_URL_ENV = "OLLAMA_BASE_URL"
GROQ_BASE_URL_ENV = "GROQ_BASE_URL"
CEREBRAS_BASE_URL_ENV = "CEREBRAS_BASE_URL"
SILICONFLOW_BASE_URL_ENV = "SILICONFLOW_BASE_URL"
TOGETHER_BASE_URL_ENV = "TOGETHER_BASE_URL"
FIREWORKS_BASE_URL_ENV = "FIREWORKS_BASE_URL"
GOOGLE_AI_BASE_URL_ENV = "GOOGLE_AI_BASE_URL"
SAMBANOVA_BASE_URL_ENV = "SAMBANOVA_BASE_URL"
MISTRAL_BASE_URL_ENV = "MISTRAL_BASE_URL"
CHUTES_BASE_URL_ENV = "CHUTES_BASE_URL"
ZHIPU_BASE_URL_ENV = "ZHIPU_BASE_URL"
KIMI_BASE_URL_ENV = "KIMI_BASE_URL"
MOONSHOT_BASE_URL_ENV = "MOONSHOT_BASE_URL"


def _unique_in_order(values: Iterable[str]) -> tuple[str, ...]:
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        ordered.append(value)
    return tuple(ordered)


PROVIDER_API_KEY_ENV_KEYS: dict[str, str] = {
    "anthropic": ANTHROPIC_API_KEY_ENV,
    "openai": OPENAI_API_KEY_ENV,
    "openrouter": OPENROUTER_API_KEY_ENV,
    "openrouter_free": OPENROUTER_API_KEY_ENV,
    "nvidia_nim": NVIDIA_NIM_API_KEY_ENV,
    "ollama": OLLAMA_API_KEY_ENV,
    "groq": GROQ_API_KEY_ENV,
    "cerebras": CEREBRAS_API_KEY_ENV,
    "siliconflow": SILICONFLOW_API_KEY_ENV,
    "together": TOGETHER_API_KEY_ENV,
    "fireworks": FIREWORKS_API_KEY_ENV,
    "google_ai": GOOGLE_AI_API_KEY_ENV,
    "sambanova": SAMBANOVA_API_KEY_ENV,
    "mistral": MISTRAL_API_KEY_ENV,
    "chutes": CHUTES_API_KEY_ENV,
    "zhipu": ZHIPU_API_KEY_ENV,
    "kimi_code": KIMI_API_KEY_ENV,
    "moonshot": MOONSHOT_API_KEY_ENV,
    "sakana": SAKANA_API_KEY_ENV,
}

CHAT_PROVIDER_API_KEY_ENV_KEYS: dict[str, str] = {
    "openrouter": OPENROUTER_API_KEY_ENV,
    "openrouter_free": OPENROUTER_API_KEY_ENV,
    "openai": OPENAI_API_KEY_ENV,
    "groq": GROQ_API_KEY_ENV,
    "siliconflow": SILICONFLOW_API_KEY_ENV,
    "together": TOGETHER_API_KEY_ENV,
    "fireworks": FIREWORKS_API_KEY_ENV,
    "nvidia_nim": NVIDIA_NIM_API_KEY_ENV,
    "zhipu": ZHIPU_API_KEY_ENV,
    "kimi_code": KIMI_API_KEY_ENV,
    "moonshot": MOONSHOT_API_KEY_ENV,
}

PROVIDER_BASE_URL_ENV_KEYS: dict[str, str] = {
    "openai": OPENAI_BASE_URL_ENV,
    "openrouter": OPENROUTER_BASE_URL_ENV,
    "openrouter_free": OPENROUTER_BASE_URL_ENV,
    "nvidia_nim": NVIDIA_NIM_BASE_URL_ENV,
    "ollama": OLLAMA_BASE_URL_ENV,
    "groq": GROQ_BASE_URL_ENV,
    "cerebras": CEREBRAS_BASE_URL_ENV,
    "siliconflow": SILICONFLOW_BASE_URL_ENV,
    "together": TOGETHER_BASE_URL_ENV,
    "fireworks": FIREWORKS_BASE_URL_ENV,
    "google_ai": GOOGLE_AI_BASE_URL_ENV,
    "sambanova": SAMBANOVA_BASE_URL_ENV,
    "mistral": MISTRAL_BASE_URL_ENV,
    "chutes": CHUTES_BASE_URL_ENV,
    "zhipu": ZHIPU_BASE_URL_ENV,
    "kimi_code": KIMI_BASE_URL_ENV,
    "moonshot": MOONSHOT_BASE_URL_ENV,
}

GINKO_API_KEY_ENV_VARS: dict[str, str] = {
    "openrouter": OPENROUTER_API_KEY_ENV,
    "fred": FRED_API_KEY_ENV,
    "finnhub": FINNHUB_API_KEY_ENV,
    "ollama": OLLAMA_API_KEY_ENV,
}

SERVICE_API_KEY_ENV_KEYS: dict[str, str] = {
    "dashboard": DASHBOARD_API_KEY_ENV,
    "fred": FRED_API_KEY_ENV,
    "finnhub": FINNHUB_API_KEY_ENV,
    "data_flywheel": DGC_DATA_FLYWHEEL_API_KEY_ENV,
    "kaizen_ops": DGC_KAIZENOPS_API_KEY_ENV,
    "reciprocity_commons": DGC_RECIPROCITY_COMMONS_API_KEY_ENV,
    "moonshot": MOONSHOT_API_KEY_ENV,
    "ngc": NGC_API_KEY_ENV,
    "nvidia": NVIDIA_API_KEY_ENV,
}

RUNTIME_PROVIDER_API_KEY_ENV_KEYS: tuple[str, ...] = _unique_in_order(
    PROVIDER_API_KEY_ENV_KEYS.values()
)

ALL_API_KEY_ENV_KEYS: tuple[str, ...] = _unique_in_order(
    (
        DASHBOARD_API_KEY_ENV,
        *PROVIDER_API_KEY_ENV_KEYS.values(),
        *SERVICE_API_KEY_ENV_KEYS.values(),
    )
)


# ---------------------------------------------------------------------------
# dkeys ↔ dharma_swarm env alias normalization
# ---------------------------------------------------------------------------
# External tools (dkeys, keychain helpers, CI) may export credentials under
# names that differ from the canonical names used by dharma_swarm.  The table
# below maps each known alias to the canonical env var so that
# `normalize_env_aliases()` can bridge the gap at process start.  Direction:
# alias (source) → canonical (target); we never overwrite an existing
# canonical value.

ENV_ALIASES: dict[str, str] = {
    # dkeys exports GEMINI_API_KEY; dharma runtime expects GOOGLE_AI_API_KEY
    "GEMINI_API_KEY": GOOGLE_AI_API_KEY_ENV,
    # dkeys exports NVIDIA_API_KEY; dharma runtime expects NVIDIA_NIM_API_KEY
    "NVIDIA_API_KEY": NVIDIA_NIM_API_KEY_ENV,
    # keychain / older scripts export NIM_API_KEY
    "NIM_API_KEY": NVIDIA_NIM_API_KEY_ENV,
    # some tools use PERPLEXITY_API_KEY; dharma expects PPLX_API_KEY
    "PERPLEXITY_API_KEY": PPLX_API_KEY_ENV,
    # z.ai / Zhipu / GLM export under several names; dharma expects ZHIPU_API_KEY
    "GLM_API_KEY": ZHIPU_API_KEY_ENV,
    "ZAI_API_KEY": ZHIPU_API_KEY_ENV,
    "ZHIPUAI_API_KEY": ZHIPU_API_KEY_ENV,
    "BIGMODEL_API_KEY": ZHIPU_API_KEY_ENV,
    # Kimi Code membership API. This is not the pay-as-you-go Moonshot
    # Platform lane; callers should prefer KIMI_API_KEY for Kimi Code.
    "MOONSHOT_KIMI_API_KEY": KIMI_API_KEY_ENV,
    # dkeys may export DEEPSEEK_API_KEY; no first-class provider yet but
    # OpenRouter is the canonical lane — alias for forward-compat
    "DEEPSEEK_API_KEY": "DEEPSEEK_API_KEY",
}


_SHELL_VAR_REF_PATTERN = re.compile(r"""^\$(?:\{?[A-Za-z_][A-Za-z0-9_]*\}?)$""")
_RUNTIME_ENV_BOOTSTRAPPED = False


def _is_unresolved_shell_ref(value: str) -> bool:
    return bool(_SHELL_VAR_REF_PATTERN.match(value.strip()))


def _usable_env_value(value: object) -> str | None:
    text = str(value or "").strip()
    if not text or _is_unresolved_shell_ref(text):
        return None
    return text


def _valid_env_name(name: str) -> bool:
    return bool(name) and (name[0].isalpha() or name[0] == "_") and all(
        ch.isalnum() or ch == "_" for ch in name
    )


def runtime_env_paths(home: Path | None = None) -> tuple[Path, ...]:
    root = home or Path.home()
    return (
        root / ".zshrc",
        root / ".env",
        root / ".dharma" / ".env",
        root / ".dharma" / "daemon.env",
        root / ".dharma" / "agent_keys.env",
    )


def _expand_simple_env_ref(value: str, env: Mapping[str, str]) -> str | None:
    raw = value.strip()
    if not _is_unresolved_shell_ref(raw):
        return raw
    name = raw[1:]
    if name.startswith("{") and name.endswith("}"):
        name = name[1:-1]
    return _usable_env_value(env.get(name, ""))


def apply_env_assignment(line: str, env: dict[str, str] | None = None) -> bool:
    """Apply one simple shell-style env assignment without executing shell code."""
    target = env if env is not None else os.environ
    raw = line.strip()
    if not raw or raw.startswith("#"):
        return False
    if raw.startswith("export "):
        raw = raw[len("export "):].strip()
    elif "export " in raw:
        return False
    try:
        parts = shlex.split(raw, comments=True, posix=True)
    except ValueError:
        return False
    if len(parts) != 1 or "=" not in parts[0]:
        return False
    name, value = parts[0].split("=", 1)
    if not _valid_env_name(name):
        return False
    if _usable_env_value(target.get(name, "")):
        return False
    resolved_value = _expand_simple_env_ref(value, target)
    if not resolved_value:
        return False
    target[name] = resolved_value
    return True


def load_runtime_env_files(
    paths: Iterable[Path],
    env: dict[str, str] | None = None,
) -> int:
    """Load simple export assignments from local runtime env files."""
    loaded = 0
    for path in paths:
        if not path.exists() or not path.is_file():
            continue
        try:
            lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
        except Exception:
            continue
        for line in lines:
            if apply_env_assignment(line, env):
                loaded += 1
    return loaded


def bootstrap_runtime_env(
    *,
    env: dict[str, str] | None = None,
    env_paths: Iterable[Path] | None = None,
    include_files: bool = True,
    force: bool = False,
) -> list[tuple[str, str]]:
    """Load local runtime env once and normalize canonical provider aliases."""
    global _RUNTIME_ENV_BOOTSTRAPPED

    target = env if env is not None else os.environ
    if env is not None:
        if include_files:
            load_runtime_env_files(env_paths or runtime_env_paths(), target)
        return normalize_env_aliases(target)

    if force or not _RUNTIME_ENV_BOOTSTRAPPED:
        _RUNTIME_ENV_BOOTSTRAPPED = True
        os.environ["DHARMA_RUNTIME_ENV_LOADED"] = "1"
        if include_files:
            load_runtime_env_files(env_paths or runtime_env_paths())
        # Unified-loader steps (keychain fallback, split-key-store guard).
        # Late import breaks the module cycle; failure here must never take
        # down provider resolution.
        try:
            from dharma_swarm.runtime_env_loader import post_file_bootstrap_hook

            post_file_bootstrap_hook()
        except Exception:  # pragma: no cover - defensive
            import logging

            logging.getLogger(__name__).debug(
                "runtime_env_loader post-bootstrap hook failed", exc_info=True
            )

    return normalize_env_aliases()


def normalize_env_aliases(
    env: dict[str, str] | None = None,
    *,
    dry_run: bool = False,
) -> list[tuple[str, str]]:
    """Copy alias env vars to their canonical dharma_swarm names.

    Only sets the canonical name when it is absent/empty **and** the alias is
    present.  Returns a list of ``(alias, canonical)`` tuples for every
    variable that was (or would be, in *dry_run* mode) propagated.

    When *env* is ``None`` the real ``os.environ`` is mutated in-place.
    """
    target = env if env is not None else os.environ
    applied: list[tuple[str, str]] = []

    for alias, canonical in ENV_ALIASES.items():
        if alias == canonical:
            continue
        alias_val = _usable_env_value(target.get(alias, ""))
        canonical_val = _usable_env_value(target.get(canonical, ""))
        if alias_val and not canonical_val:
            if not dry_run:
                target[canonical] = alias_val
            applied.append((alias, canonical))

    return applied


def _provider_key(provider: object) -> str:
    value = getattr(provider, "value", provider)
    return str(value)


def provider_api_key_env(provider: object) -> str | None:
    return PROVIDER_API_KEY_ENV_KEYS.get(_provider_key(provider))


def provider_base_url_env(provider: object) -> str | None:
    return PROVIDER_BASE_URL_ENV_KEYS.get(_provider_key(provider))


def service_api_key_env(name: str) -> str:
    return SERVICE_API_KEY_ENV_KEYS[name]


def env_value(env_var: str, env: Mapping[str, str] | None = None) -> str | None:
    source = os.environ if env is None else env
    return _usable_env_value(source.get(env_var, ""))


def env_has_value(env_var: str, env: Mapping[str, str] | None = None) -> bool:
    return env_value(env_var, env) is not None


def present_api_key_envs(
    env_vars: Iterable[str] | None = None,
    env: Mapping[str, str] | None = None,
) -> list[str]:
    ordered = env_vars or ALL_API_KEY_ENV_KEYS
    return [env_var for env_var in ordered if env_has_value(env_var, env)]


def has_any_llm(env: Mapping[str, str] | None = None) -> bool:
    """Return True when any canonical runtime LLM provider key is configured."""
    return bool(present_api_key_envs(RUNTIME_PROVIDER_API_KEY_ENV_KEYS, env))


def provider_available(provider: str, env: Mapping[str, str] | None = None) -> bool:
    """Return True if the named provider has a configured API key."""
    env_var = PROVIDER_API_KEY_ENV_KEYS.get(provider)
    if env_var is None:
        return False
    return env_has_value(env_var, env)


__all__ = [
    "ALL_API_KEY_ENV_KEYS",
    "ANTHROPIC_API_KEY_ENV",
    "API_MODE_AMBIGUOUS",
    "API_MODE_LOCAL_DEV",
    "API_MODE_PRODUCTION",
    "DASHBOARD_API_MODE_ENV",
    "dashboard_api_mode",
    "apply_env_assignment",
    "bootstrap_runtime_env",
    "CEREBRAS_API_KEY_ENV",
    "CEREBRAS_BASE_URL_ENV",
    "CHAT_PROVIDER_API_KEY_ENV_KEYS",
    "CHUTES_API_KEY_ENV",
    "CHUTES_BASE_URL_ENV",
    "ZHIPU_API_KEY_ENV",
    "ZHIPU_BASE_URL_ENV",
    "DASHBOARD_API_KEY_ENV",
    "ENV_ALIASES",
    "DGC_DATA_FLYWHEEL_API_KEY_ENV",
    "DGC_KAIZENOPS_API_KEY_ENV",
    "DGC_RECIPROCITY_COMMONS_API_KEY_ENV",
    "FINNHUB_API_KEY_ENV",
    "FIREWORKS_API_KEY_ENV",
    "FIREWORKS_BASE_URL_ENV",
    "FRED_API_KEY_ENV",
    "GINKO_API_KEY_ENV_VARS",
    "GOOGLE_AI_API_KEY_ENV",
    "GOOGLE_AI_BASE_URL_ENV",
    "GROQ_API_KEY_ENV",
    "GROQ_BASE_URL_ENV",
    "has_any_llm",
    "KIMI_API_KEY_ENV",
    "KIMI_BASE_URL_ENV",
    "MISTRAL_API_KEY_ENV",
    "MISTRAL_BASE_URL_ENV",
    "MOONSHOT_API_KEY_ENV",
    "MOONSHOT_BASE_URL_ENV",
    "NGC_API_KEY_ENV",
    "NVIDIA_API_KEY_ENV",
    "NVIDIA_NIM_API_KEY_ENV",
    "NVIDIA_NIM_BASE_URL_ENV",
    "OLLAMA_API_KEY_ENV",
    "OLLAMA_BASE_URL_ENV",
    "OPENAI_API_KEY_ENV",
    "OPENAI_BASE_URL_ENV",
    "OPENROUTER_API_KEY_ENV",
    "OPENROUTER_BASE_URL_ENV",
    "PROVIDER_API_KEY_ENV_KEYS",
    "PROVIDER_BASE_URL_ENV_KEYS",
    "RUNTIME_PROVIDER_API_KEY_ENV_KEYS",
    "SAMBANOVA_API_KEY_ENV",
    "SAMBANOVA_BASE_URL_ENV",
    "SERVICE_API_KEY_ENV_KEYS",
    "SILICONFLOW_API_KEY_ENV",
    "SILICONFLOW_BASE_URL_ENV",
    "TOGETHER_API_KEY_ENV",
    "TOGETHER_BASE_URL_ENV",
    "env_has_value",
    "env_value",
    "load_runtime_env_files",
    "normalize_env_aliases",
    "present_api_key_envs",
    "provider_api_key_env",
    "provider_available",
    "provider_base_url_env",
    "runtime_env_paths",
    "service_api_key_env",
]
