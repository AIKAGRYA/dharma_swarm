"""Centralized runtime provider resolution and factory helpers.

Keeps environment/auth/model/base-url resolution in one place while leaving
ModelRouter policy and provider implementations unchanged.
"""

from __future__ import annotations

import asyncio
import hashlib
import os
import shutil
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Iterable, Mapping
from urllib.parse import urlsplit, urlunsplit

from dharma_swarm.api_keys import (
    ANTHROPIC_API_KEY_ENV,
    CEREBRAS_API_KEY_ENV,
    CEREBRAS_BASE_URL_ENV,
    CHUTES_API_KEY_ENV,
    CHUTES_BASE_URL_ENV,
    FIREWORKS_API_KEY_ENV,
    FIREWORKS_BASE_URL_ENV,
    GOOGLE_AI_API_KEY_ENV,
    GOOGLE_AI_BASE_URL_ENV,
    GROQ_API_KEY_ENV,
    GROQ_BASE_URL_ENV,
    KIMI_API_KEY_ENV,
    KIMI_BASE_URL_ENV,
    MISTRAL_API_KEY_ENV,
    MISTRAL_BASE_URL_ENV,
    MOONSHOT_API_KEY_ENV,
    MOONSHOT_BASE_URL_ENV,
    NVIDIA_NIM_API_KEY_ENV,
    NVIDIA_NIM_BASE_URL_ENV,
    OLLAMA_API_KEY_ENV,
    OPENAI_API_KEY_ENV,
    OPENROUTER_API_KEY_ENV,
    SAMBANOVA_API_KEY_ENV,
    SAMBANOVA_BASE_URL_ENV,
    SILICONFLOW_API_KEY_ENV,
    SILICONFLOW_BASE_URL_ENV,
    TOGETHER_API_KEY_ENV,
    TOGETHER_BASE_URL_ENV,
    ZHIPU_API_KEY_ENV,
    ZHIPU_BASE_URL_ENV,
    env_value,
    normalize_env_aliases,
)
from dharma_swarm.model_hierarchy import (
    CANONICAL_SEED_ORDER,
    default_model,
)
from dharma_swarm.models import LLMRequest, LLMResponse, ProviderType
from dharma_swarm.provider_deadpool import ProviderDeadpool, is_connection_dead_error
from dharma_swarm.ollama_config import (
    build_ollama_headers,
    ollama_transport_mode,
    resolve_ollama_base_url,
    resolve_ollama_model,
)

OPENAI_BASE_URL = "https://api.openai.com/v1"
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
NVIDIA_NIM_BASE_URL = "https://integrate.api.nvidia.com/v1"
GROQ_BASE_URL = "https://api.groq.com/openai/v1"
CEREBRAS_BASE_URL = "https://api.cerebras.ai/v1"
SILICONFLOW_BASE_URL = "https://api.siliconflow.cn/v1"
TOGETHER_BASE_URL = "https://api.together.xyz/v1"
FIREWORKS_BASE_URL = "https://api.fireworks.ai/inference/v1"
GOOGLE_AI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"
SAMBANOVA_BASE_URL = "https://api.sambanova.ai/v1"
MISTRAL_BASE_URL = "https://api.mistral.ai/v1"
CHUTES_BASE_URL = "https://api.chutes.ai/v1"
# z.ai / Zhipu coding-plan OpenAI-compatible endpoint. The generic Z.ai
# endpoint can reject coding-plan keys as out of funds even when coding quota is
# live, so this default is intentionally the coding endpoint.
ZHIPU_BASE_URL = "https://api.z.ai/api/coding/paas/v4"
KIMI_BASE_URL = "https://api.kimi.com/coding/v1"
MOONSHOT_BASE_URL = "https://api.moonshot.ai/v1"

# Default models — sourced from model_hierarchy.py (the single source of truth)
DEFAULT_CLAUDE_MODEL = default_model(ProviderType.ANTHROPIC)
DEFAULT_OPENAI_MODEL = default_model(ProviderType.OPENAI)
DEFAULT_OPENROUTER_MODEL = default_model(ProviderType.OPENROUTER)
DEFAULT_GROQ_MODEL = default_model(ProviderType.GROQ)
DEFAULT_CEREBRAS_MODEL = default_model(ProviderType.CEREBRAS)
DEFAULT_SILICONFLOW_MODEL = default_model(ProviderType.SILICONFLOW)
DEFAULT_TOGETHER_MODEL = default_model(ProviderType.TOGETHER)
DEFAULT_FIREWORKS_MODEL = default_model(ProviderType.FIREWORKS)
DEFAULT_NIM_MODEL = default_model(ProviderType.NVIDIA_NIM)
DEFAULT_SAMBANOVA_MODEL = default_model(ProviderType.SAMBANOVA)
DEFAULT_MISTRAL_MODEL = default_model(ProviderType.MISTRAL)
DEFAULT_CHUTES_MODEL = default_model(ProviderType.CHUTES)
DEFAULT_GOOGLE_AI_MODEL = default_model(ProviderType.GOOGLE_AI)
DEFAULT_ZHIPU_MODEL = default_model(ProviderType.ZHIPU)
DEFAULT_KIMI_CODE_MODEL = default_model(ProviderType.KIMI_CODE)
DEFAULT_MOONSHOT_MODEL = default_model(ProviderType.MOONSHOT)
DEFAULT_CODEX_MODEL = default_model(ProviderType.CODEX)
DEFAULT_PROVIDER_TIMEOUT_SECONDS = 300


def _ollama_runtime_available(*, base_url: str, token: str | None) -> bool:
    """Return whether the resolved Ollama endpoint is configured for dispatch.

    This resolver is used by no-network CI and hot routing paths, so it must not
    perform an inline smoke. Actual liveness belongs to dkeys/provider-status
    refresh and provider failure fallback.
    """
    if ollama_transport_mode(base_url=base_url, api_key=token) == "cloud_api":
        return bool(token)
    return bool(base_url)

# Provider ordering sourced from model_hierarchy.py — the single source of truth.
# All free providers first, then cheap, then paid.
DEFAULT_RUNTIME_PROVIDERS: tuple[ProviderType, ...] = CANONICAL_SEED_ORDER

# Canonical low-cost provider chain.  Matches CANONICAL_SEED_ORDER from
# model_hierarchy.py: Ollama Cloud frontier FIRST, then free tiers by
# capability, then cheap, then paid.
PREFERRED_LOW_COST_RUNTIME_PROVIDERS: tuple[ProviderType, ...] = (
    ProviderType.OLLAMA,          # FREE frontier: GLM-5 744B, DeepSeek-v3.2, Kimi-K2.5
    ProviderType.NVIDIA_NIM,      # FREE: Llama 3.3 70B (50 req/day)
    ProviderType.GROQ,            # FREE: Qwen3-32B (3000 tok/s)
    ProviderType.CEREBRAS,        # FREE: Qwen3 235B (3000 tok/s)
    ProviderType.SILICONFLOW,     # FREE: Qwen3-Coder 480B
    ProviderType.SAMBANOVA,       # FREE: Llama 3.3 70B
    ProviderType.TOGETHER,        # FREE: Qwen3-Coder 480B
    ProviderType.FIREWORKS,       # FREE: Qwen3-Coder 480B
    ProviderType.OPENROUTER_FREE, # FREE: auto-discovered
    ProviderType.KIMI_CODE,       # CHEAP: Kimi API Platform coding lane
    ProviderType.MOONSHOT,        # CHEAP: Kimi API Platform / Moonshot global API
    ProviderType.ZHIPU,           # CHEAP: Z.ai coding-plan GLM-5.2 direct API
    ProviderType.MISTRAL,         # CHEAP
    ProviderType.GOOGLE_AI,       # CHEAP
    ProviderType.CHUTES,          # CHEAP
    ProviderType.OPENROUTER,      # PAID (default: moonshotai/kimi-k2.5)
    ProviderType.CLAUDE_CODE,     # FALLBACK: always available if claude binary installed
)

PREFERRED_LOW_COST_WITH_ANTHROPIC_RUNTIME_PROVIDERS: tuple[ProviderType, ...] = (
    ProviderType.OLLAMA,          # FREE frontier first
    ProviderType.NVIDIA_NIM,
    ProviderType.GROQ,
    ProviderType.CEREBRAS,
    ProviderType.OPENROUTER_FREE,
    ProviderType.TOGETHER,
    ProviderType.FIREWORKS,
    ProviderType.KIMI_CODE,
    ProviderType.MOONSHOT,
    ProviderType.ZHIPU,
    ProviderType.OPENROUTER,      # PAID (moonshotai/kimi-k2.5)
    ProviderType.ANTHROPIC,
    ProviderType.CLAUDE_CODE,     # FALLBACK: always available if claude binary installed
)


@dataclass(frozen=True, slots=True)
class RuntimeProviderConfig:
    provider: ProviderType
    api_key: str | None = None
    base_url: str | None = None
    default_model: str | None = None
    transport_mode: str | None = None
    working_dir: str | None = None
    timeout_seconds: int | None = None
    binary_path: str | None = None
    available: bool = False
    source: str = "env"
    metadata: dict[str, Any] | None = None


def _canonical_transport_base_url(base_url: str | None) -> str:
    """Return a secret-free, path-sensitive network-endpoint identity.

    URL paths can themselves carry credentials or opaque tenant identifiers, so
    the identity never emits a raw path.  A full SHA-256 token preserves the
    distinction between otherwise-identical endpoints without treating query
    strings, fragments, or userinfo as transport identity.
    """
    raw_url = str(base_url or "").strip()
    if not raw_url:
        return ""

    try:
        parsed = urlsplit(
            raw_url if "://" in raw_url or raw_url.startswith("//") else f"//{raw_url}"
        )
        hostname = parsed.hostname
        port = parsed.port
    except ValueError:
        return ""
    if not parsed.netloc or not hostname:
        return ""

    normalized_host = hostname.lower()
    if ":" in normalized_host:
        normalized_host = f"[{normalized_host}]"
    scheme = parsed.scheme.lower()
    if port is not None and not (
        (scheme == "https" and port == 443)
        or (scheme == "http" and port == 80)
    ):
        normalized_host = f"{normalized_host}:{port}"
    normalized_path = parsed.path.rstrip("/")
    path_digest = hashlib.sha256(normalized_path.encode("utf-8")).hexdigest()
    path_token = f"/.path-sha256-{path_digest}"
    return urlunsplit((scheme, normalized_host, path_token, "", ""))


def runtime_provider_transport_identity(
    config: RuntimeProviderConfig | None = None,
    *,
    logical_provider: ProviderType | None = None,
    provider_instance: Any | None = None,
) -> str:
    """Return a secret-free identity for one physical dispatch transport.

    Logical provider labels remain authoritative for policy and provenance.
    This identity exists only to prevent a fallback chain from treating two
    aliases of the same executable transport as independent attempts. Unknown
    provider implementations fail open to their logical lane rather than being
    collapsed speculatively.
    """
    runtime_config = config or getattr(provider_instance, "runtime_config", None)
    provider = (
        getattr(runtime_config, "provider", None)
        or logical_provider
    )
    transport_mode = str(
        getattr(runtime_config, "transport_mode", "") or ""
    ).strip()
    instance_command = str(
        getattr(provider_instance, "_cli_command", "") or ""
    ).strip()

    command = ""
    if transport_mode == "claude_code" or provider == ProviderType.CLAUDE_CODE:
        command = "claude"
    elif transport_mode == "codex" or provider == ProviderType.CODEX:
        command = "codex"
    elif instance_command:
        command = instance_command

    if command:
        endpoint = str(
            getattr(runtime_config, "binary_path", "")
            or getattr(provider_instance, "_resolved_command", "")
            or command
        )
        if Path(endpoint).is_absolute() or "/" in endpoint:
            endpoint = str(Path(endpoint).expanduser().resolve())
        return f"cli:{command}:{endpoint}"

    base_url = _canonical_transport_base_url(
        getattr(runtime_config, "base_url", None)
    )
    if base_url:
        # A concrete endpoint is the authority for physical-transport
        # independence.  Logical aliases that hit it are one attempt, even if
        # they select different models or pricing labels.
        return f"provider:{base_url}"
    if provider is None:
        return "provider:unknown"
    # Missing endpoint information is insufficient evidence of shared
    # transport, so fail open to the logical provider rather than collapsing.
    return f"provider:{provider.value}"


def deduplicate_runtime_provider_configs(
    configs: Iterable[RuntimeProviderConfig],
) -> list[RuntimeProviderConfig]:
    """Keep the first logical lane for each physical transport.

    When aliases collapse, the retained immutable config records all logical
    labels plus the canonical transport identity in metadata. No credentials
    participate in or are emitted by the identity.
    """
    deduplicated: list[RuntimeProviderConfig] = []
    indices: dict[str, int] = {}
    for config in configs:
        identity = runtime_provider_transport_identity(config)
        existing_index = indices.get(identity)
        if existing_index is None:
            indices[identity] = len(deduplicated)
            deduplicated.append(config)
            continue

        retained = deduplicated[existing_index]
        metadata = dict(retained.metadata or {})
        aliases = list(
            metadata.get("logical_provider_aliases")
            or [retained.provider.value]
        )
        if config.provider.value not in aliases:
            aliases.append(config.provider.value)
        metadata.update(
            {
                "physical_transport_identity": identity,
                "logical_provider_aliases": aliases,
            }
        )
        deduplicated[existing_index] = replace(retained, metadata=metadata)
    return deduplicated


def _env_value(env: Mapping[str, str], key: str) -> str | None:
    return env_value(key, env)


def _resolve_cli_binary(name: str) -> str | None:
    found = shutil.which(name)
    if found:
        return found

    for candidate in (
        Path.home() / ".npm-global" / "bin" / name,
        Path("/opt/homebrew/bin") / name,
        Path("/usr/local/bin") / name,
    ):
        if candidate.exists():
            return str(candidate)
    return None


def resolve_runtime_provider_config(
    provider: ProviderType,
    *,
    model: str | None = None,
    api_key: str | None = None,
    base_url: str | None = None,
    working_dir: str | None = None,
    timeout_seconds: int | None = None,
    env: Mapping[str, str] | None = None,
) -> RuntimeProviderConfig:
    """Resolve runtime config for a provider from args + environment."""

    if env is None:
        normalize_env_aliases()
        env_map: Mapping[str, str] = os.environ
    else:
        copied_env = dict(env)
        normalize_env_aliases(copied_env)
        env_map = copied_env
    timeout = int(timeout_seconds or DEFAULT_PROVIDER_TIMEOUT_SECONDS)
    cwd = str(Path(working_dir or os.getcwd()))

    if provider == ProviderType.ANTHROPIC:
        # Preserve the requested logical provider identity even when the
        # default transport is the flat-fee Claude Code CLI.  Callers can now
        # distinguish two logical lanes while the factory selects transport.
        if not _env_value(env_map, "DHARMA_FORCE_ANTHROPIC_API"):
            binary = _resolve_cli_binary("claude")
            return RuntimeProviderConfig(
                provider=provider,
                default_model=model or DEFAULT_CLAUDE_MODEL,
                transport_mode="claude_code",
                working_dir=cwd,
                timeout_seconds=timeout,
                binary_path=binary,
                available=bool(binary),
                source="binary",
            )
        token = api_key or _env_value(env_map, ANTHROPIC_API_KEY_ENV)
        return RuntimeProviderConfig(
            provider=provider,
            api_key=token,
            default_model=model or DEFAULT_CLAUDE_MODEL,
            available=bool(token),
        )

    if provider == ProviderType.OPENAI:
        token = api_key or _env_value(env_map, OPENAI_API_KEY_ENV)
        return RuntimeProviderConfig(
            provider=provider,
            api_key=token,
            base_url=(base_url or OPENAI_BASE_URL).rstrip("/"),
            default_model=model or DEFAULT_OPENAI_MODEL,
            available=bool(token),
        )

    if provider == ProviderType.OPENROUTER:
        token = api_key or _env_value(env_map, OPENROUTER_API_KEY_ENV)
        return RuntimeProviderConfig(
            provider=provider,
            api_key=token,
            base_url=(base_url or OPENROUTER_BASE_URL).rstrip("/"),
            default_model=model or DEFAULT_OPENROUTER_MODEL,
            available=bool(token),
        )

    if provider == ProviderType.OPENROUTER_FREE:
        token = api_key or _env_value(env_map, OPENROUTER_API_KEY_ENV)
        return RuntimeProviderConfig(
            provider=provider,
            api_key=token,
            base_url=(base_url or OPENROUTER_BASE_URL).rstrip("/"),
            default_model=model,
            available=bool(token),
        )

    if provider == ProviderType.NVIDIA_NIM:
        token = api_key or _env_value(env_map, NVIDIA_NIM_API_KEY_ENV)
        resolved_base = (
            base_url
            or _env_value(env_map, NVIDIA_NIM_BASE_URL_ENV)
            or NVIDIA_NIM_BASE_URL
        ).rstrip("/")
        return RuntimeProviderConfig(
            provider=provider,
            api_key=token,
            base_url=resolved_base,
            default_model=model or DEFAULT_NIM_MODEL,
            available=bool(token),
        )

    if provider == ProviderType.OLLAMA:
        token = api_key or _env_value(env_map, OLLAMA_API_KEY_ENV)
        resolved_base = resolve_ollama_base_url(base_url=base_url, api_key=token)
        resolved_model = resolve_ollama_model(
            model,
            base_url=resolved_base,
            api_key=token,
        )
        transport_mode = ollama_transport_mode(
            base_url=resolved_base,
            api_key=token,
        )
        available = bool(resolved_base) and _ollama_runtime_available(
            base_url=resolved_base,
            token=token,
        )
        metadata: dict[str, Any] = {}
        try:
            metadata["headers"] = build_ollama_headers(
                base_url=resolved_base,
                api_key=token,
            )
        except Exception:
            metadata["headers"] = {}
        return RuntimeProviderConfig(
            provider=provider,
            api_key=token,
            base_url=resolved_base,
            default_model=resolved_model,
            transport_mode=transport_mode,
            available=available,
            metadata=metadata,
        )

    if provider == ProviderType.CLAUDE_CODE:
        binary = _resolve_cli_binary("claude")
        return RuntimeProviderConfig(
            provider=provider,
            default_model=model or DEFAULT_CLAUDE_MODEL,
            working_dir=cwd,
            timeout_seconds=timeout,
            binary_path=binary,
            available=bool(binary),
            source="binary",
        )

    if provider == ProviderType.CODEX:
        binary = _resolve_cli_binary("codex")
        return RuntimeProviderConfig(
            provider=provider,
            default_model=model or _env_value(env_map, "DGC_DIRECTOR_CODEX_MODEL") or DEFAULT_CODEX_MODEL,
            working_dir=cwd,
            timeout_seconds=timeout,
            binary_path=binary,
            available=bool(binary),
            source="binary",
        )

    if provider == ProviderType.GROQ:
        token = api_key or _env_value(env_map, GROQ_API_KEY_ENV)
        resolved_base = (
            base_url
            or _env_value(env_map, GROQ_BASE_URL_ENV)
            or GROQ_BASE_URL
        ).rstrip("/")
        return RuntimeProviderConfig(
            provider=provider,
            api_key=token,
            base_url=resolved_base,
            default_model=model or DEFAULT_GROQ_MODEL,
            available=bool(token),
        )

    if provider == ProviderType.CEREBRAS:
        token = api_key or _env_value(env_map, CEREBRAS_API_KEY_ENV)
        resolved_base = (
            base_url
            or _env_value(env_map, CEREBRAS_BASE_URL_ENV)
            or CEREBRAS_BASE_URL
        ).rstrip("/")
        return RuntimeProviderConfig(
            provider=provider,
            api_key=token,
            base_url=resolved_base,
            default_model=model or DEFAULT_CEREBRAS_MODEL,
            available=bool(token),
        )

    if provider == ProviderType.SILICONFLOW:
        token = api_key or _env_value(env_map, SILICONFLOW_API_KEY_ENV)
        resolved_base = (
            base_url
            or _env_value(env_map, SILICONFLOW_BASE_URL_ENV)
            or SILICONFLOW_BASE_URL
        ).rstrip("/")
        return RuntimeProviderConfig(
            provider=provider,
            api_key=token,
            base_url=resolved_base,
            default_model=model or DEFAULT_SILICONFLOW_MODEL,
            available=bool(token),
        )

    if provider == ProviderType.TOGETHER:
        token = api_key or _env_value(env_map, TOGETHER_API_KEY_ENV)
        resolved_base = (
            base_url
            or _env_value(env_map, TOGETHER_BASE_URL_ENV)
            or TOGETHER_BASE_URL
        ).rstrip("/")
        return RuntimeProviderConfig(
            provider=provider,
            api_key=token,
            base_url=resolved_base,
            default_model=model or DEFAULT_TOGETHER_MODEL,
            available=bool(token),
        )

    if provider == ProviderType.FIREWORKS:
        token = api_key or _env_value(env_map, FIREWORKS_API_KEY_ENV)
        resolved_base = (
            base_url
            or _env_value(env_map, FIREWORKS_BASE_URL_ENV)
            or FIREWORKS_BASE_URL
        ).rstrip("/")
        return RuntimeProviderConfig(
            provider=provider,
            api_key=token,
            base_url=resolved_base,
            default_model=model or DEFAULT_FIREWORKS_MODEL,
            available=bool(token),
        )

    if provider == ProviderType.GOOGLE_AI:
        token = api_key or _env_value(env_map, GOOGLE_AI_API_KEY_ENV)
        resolved_base = (
            base_url
            or _env_value(env_map, GOOGLE_AI_BASE_URL_ENV)
            or GOOGLE_AI_BASE_URL
        ).rstrip("/")
        return RuntimeProviderConfig(
            provider=provider,
            api_key=token,
            base_url=resolved_base,
            default_model=model or DEFAULT_GOOGLE_AI_MODEL,
            available=bool(token),
        )

    if provider == ProviderType.SAMBANOVA:
        token = api_key or _env_value(env_map, SAMBANOVA_API_KEY_ENV)
        resolved_base = (
            base_url
            or _env_value(env_map, SAMBANOVA_BASE_URL_ENV)
            or SAMBANOVA_BASE_URL
        ).rstrip("/")
        return RuntimeProviderConfig(
            provider=provider,
            api_key=token,
            base_url=resolved_base,
            default_model=model or DEFAULT_SAMBANOVA_MODEL,
            available=bool(token),
        )

    if provider == ProviderType.MISTRAL:
        token = api_key or _env_value(env_map, MISTRAL_API_KEY_ENV)
        resolved_base = (
            base_url
            or _env_value(env_map, MISTRAL_BASE_URL_ENV)
            or MISTRAL_BASE_URL
        ).rstrip("/")
        return RuntimeProviderConfig(
            provider=provider,
            api_key=token,
            base_url=resolved_base,
            default_model=model or DEFAULT_MISTRAL_MODEL,
            available=bool(token),
        )

    if provider == ProviderType.CHUTES:
        token = api_key or _env_value(env_map, CHUTES_API_KEY_ENV)
        resolved_base = (
            base_url
            or _env_value(env_map, CHUTES_BASE_URL_ENV)
            or CHUTES_BASE_URL
        ).rstrip("/")
        return RuntimeProviderConfig(
            provider=provider,
            api_key=token,
            base_url=resolved_base,
            default_model=model or DEFAULT_CHUTES_MODEL,
            available=bool(token),
        )

    if provider == ProviderType.ZHIPU:
        token = api_key or _env_value(env_map, ZHIPU_API_KEY_ENV)
        resolved_base = (
            base_url
            or _env_value(env_map, ZHIPU_BASE_URL_ENV)
            or ZHIPU_BASE_URL
        ).rstrip("/")
        return RuntimeProviderConfig(
            provider=provider,
            api_key=token,
            base_url=resolved_base,
            default_model=model or DEFAULT_ZHIPU_MODEL,
            timeout_seconds=timeout,
            available=bool(token),
        )

    if provider == ProviderType.KIMI_CODE:
        # Kimi Code subscription keys and Moonshot Platform keys are distinct
        # authorities. Never silently send a Moonshot key to the coding API.
        token = api_key or _env_value(env_map, KIMI_API_KEY_ENV)
        resolved_base = (
            base_url
            or _env_value(env_map, KIMI_BASE_URL_ENV)
            or KIMI_BASE_URL
        ).rstrip("/")
        return RuntimeProviderConfig(
            provider=provider,
            api_key=token,
            base_url=resolved_base,
            default_model=model or DEFAULT_KIMI_CODE_MODEL,
            timeout_seconds=timeout,
            available=bool(token),
        )

    if provider == ProviderType.MOONSHOT:
        token = api_key or _env_value(env_map, MOONSHOT_API_KEY_ENV)
        resolved_base = (
            base_url
            or _env_value(env_map, MOONSHOT_BASE_URL_ENV)
            or MOONSHOT_BASE_URL
        ).rstrip("/")
        return RuntimeProviderConfig(
            provider=provider,
            api_key=token,
            base_url=resolved_base,
            default_model=model or DEFAULT_MOONSHOT_MODEL,
            timeout_seconds=timeout,
            available=bool(token),
        )

    raise ValueError(f"Unsupported runtime provider: {provider.value}")


def create_runtime_provider(config: RuntimeProviderConfig) -> Any:
    """Instantiate a provider from centralized runtime config."""

    from dharma_swarm.providers import (
        AnthropicProvider,
        CerebrasProvider,
        ChutesProvider,
        ClaudeCodeProvider,
        CodexProvider,
        FireworksProvider,
        GoogleAIProvider,
        GroqProvider,
        KimiCodeProvider,
        MistralProvider,
        NVIDIANIMProvider,
        OllamaProvider,
        OpenAIProvider,
        OpenRouterFreeProvider,
        OpenRouterProvider,
        SambaNovaProvider,
        SiliconFlowProvider,
        TogetherProvider,
        ZhipuProvider,
    )
    from dharma_swarm.moonshot_provider import MoonshotProvider

    if config.provider == ProviderType.ANTHROPIC:
        if config.transport_mode == "claude_code":
            kwargs = {"timeout": config.timeout_seconds or DEFAULT_PROVIDER_TIMEOUT_SECONDS}
            if config.working_dir is not None:
                kwargs["working_dir"] = config.working_dir
            return ClaudeCodeProvider(**kwargs)
        kwargs: dict[str, Any] = {}
        if config.api_key is not None:
            kwargs["api_key"] = config.api_key
        return AnthropicProvider(**kwargs)
    if config.provider == ProviderType.OPENAI:
        kwargs = {}
        if config.api_key is not None:
            kwargs["api_key"] = config.api_key
        return OpenAIProvider(**kwargs)
    if config.provider == ProviderType.OPENROUTER:
        kwargs = {}
        if config.api_key is not None:
            kwargs["api_key"] = config.api_key
        return OpenRouterProvider(**kwargs)
    if config.provider == ProviderType.OPENROUTER_FREE:
        kwargs = {}
        if config.api_key is not None:
            kwargs["api_key"] = config.api_key
        if config.default_model is not None:
            kwargs["model"] = config.default_model
        return OpenRouterFreeProvider(**kwargs)
    if config.provider == ProviderType.NVIDIA_NIM:
        kwargs = {"default_model": config.default_model or DEFAULT_NIM_MODEL}
        if config.api_key is not None:
            kwargs["api_key"] = config.api_key
        if config.base_url is not None:
            kwargs["base_url"] = config.base_url
        return NVIDIANIMProvider(**kwargs)
    if config.provider == ProviderType.OLLAMA:
        kwargs = {}
        if config.base_url is not None:
            kwargs["base_url"] = config.base_url
        if config.default_model is not None:
            kwargs["model"] = config.default_model
        if config.api_key is not None:
            kwargs["api_key"] = config.api_key
        return OllamaProvider(**kwargs)
    if config.provider == ProviderType.CLAUDE_CODE:
        kwargs = {"timeout": config.timeout_seconds or DEFAULT_PROVIDER_TIMEOUT_SECONDS}
        if config.working_dir is not None:
            kwargs["working_dir"] = config.working_dir
        return ClaudeCodeProvider(**kwargs)
    if config.provider == ProviderType.CODEX:
        kwargs = {"timeout": config.timeout_seconds or DEFAULT_PROVIDER_TIMEOUT_SECONDS}
        if config.working_dir is not None:
            kwargs["working_dir"] = config.working_dir
        return CodexProvider(**kwargs)
    if config.provider == ProviderType.GROQ:
        kwargs = {}
        if config.api_key is not None:
            kwargs["api_key"] = config.api_key
        if config.base_url is not None:
            kwargs["base_url"] = config.base_url
        return GroqProvider(**kwargs)
    if config.provider == ProviderType.CEREBRAS:
        kwargs = {}
        if config.api_key is not None:
            kwargs["api_key"] = config.api_key
        return CerebrasProvider(**kwargs)
    if config.provider == ProviderType.SILICONFLOW:
        kwargs = {}
        if config.api_key is not None:
            kwargs["api_key"] = config.api_key
        return SiliconFlowProvider(**kwargs)
    if config.provider == ProviderType.TOGETHER:
        kwargs = {}
        if config.api_key is not None:
            kwargs["api_key"] = config.api_key
        return TogetherProvider(**kwargs)
    if config.provider == ProviderType.FIREWORKS:
        kwargs = {}
        if config.api_key is not None:
            kwargs["api_key"] = config.api_key
        return FireworksProvider(**kwargs)
    if config.provider == ProviderType.GOOGLE_AI:
        kwargs = {}
        if config.api_key is not None:
            kwargs["api_key"] = config.api_key
        return GoogleAIProvider(**kwargs)
    if config.provider == ProviderType.SAMBANOVA:
        kwargs = {}
        if config.api_key is not None:
            kwargs["api_key"] = config.api_key
        return SambaNovaProvider(**kwargs)
    if config.provider == ProviderType.MISTRAL:
        kwargs = {}
        if config.api_key is not None:
            kwargs["api_key"] = config.api_key
        return MistralProvider(**kwargs)
    if config.provider == ProviderType.CHUTES:
        kwargs = {}
        if config.api_key is not None:
            kwargs["api_key"] = config.api_key
        return ChutesProvider(**kwargs)
    if config.provider == ProviderType.ZHIPU:
        kwargs = {
            "default_model": config.default_model or DEFAULT_ZHIPU_MODEL,
            "timeout": config.timeout_seconds or DEFAULT_PROVIDER_TIMEOUT_SECONDS,
        }
        if config.api_key is not None:
            kwargs["api_key"] = config.api_key
        if config.base_url is not None:
            kwargs["base_url"] = config.base_url
        return ZhipuProvider(**kwargs)
    if config.provider == ProviderType.KIMI_CODE:
        kwargs = {
            "default_model": config.default_model or DEFAULT_KIMI_CODE_MODEL,
            "timeout": config.timeout_seconds or DEFAULT_PROVIDER_TIMEOUT_SECONDS,
        }
        if config.api_key is not None:
            kwargs["api_key"] = config.api_key
        if config.base_url is not None:
            kwargs["base_url"] = config.base_url
        return KimiCodeProvider(**kwargs)
    if config.provider == ProviderType.MOONSHOT:
        kwargs = {
            "default_model": config.default_model or DEFAULT_MOONSHOT_MODEL,
            "timeout": config.timeout_seconds or DEFAULT_PROVIDER_TIMEOUT_SECONDS,
        }
        if config.api_key is not None:
            kwargs["api_key"] = config.api_key
        if config.base_url is not None:
            kwargs["base_url"] = config.base_url
        return MoonshotProvider(**kwargs)
    raise ValueError(f"Unsupported runtime provider: {config.provider.value}")


def create_default_provider_map(
    *,
    working_dir: str | None = None,
    timeout_seconds: int | None = None,
    env: Mapping[str, str] | None = None,
) -> dict[ProviderType, Any]:
    """Instantiate the default provider map for ModelRouter."""

    providers: dict[ProviderType, Any] = {}
    for provider in DEFAULT_RUNTIME_PROVIDERS:
        cfg = resolve_runtime_provider_config(
            provider,
            working_dir=working_dir,
            timeout_seconds=timeout_seconds,
            env=env,
        )
        provider_instance = create_runtime_provider(cfg)
        setattr(provider_instance, "available", cfg.available)
        setattr(provider_instance, "runtime_config", cfg)
        providers[provider] = provider_instance
    return providers


def preferred_runtime_provider_configs(
    *,
    model: str | None = None,
    provider_order: tuple[ProviderType, ...] | None = None,
    model_overrides: Mapping[ProviderType, str | None] | None = None,
    working_dir: str | None = None,
    timeout_seconds: int | None = None,
    env: Mapping[str, str] | None = None,
) -> list[RuntimeProviderConfig]:
    """Resolve the preferred cheap/runtime provider chain in fixed order.

    This is the canonical helper for direct-call sites that should prefer
    Ollama and NVIDIA NIM before any OpenRouter lane.
    """

    order = provider_order or PREFERRED_LOW_COST_RUNTIME_PROVIDERS
    overrides = model_overrides or {}
    configs: list[RuntimeProviderConfig] = []
    for provider in order:
        cfg = resolve_runtime_provider_config(
            provider,
            model=overrides.get(provider, model),
            working_dir=working_dir,
            timeout_seconds=timeout_seconds,
            env=env,
        )
        if cfg.available:
            configs.append(cfg)
    return deduplicate_runtime_provider_configs(configs)


_PREFERRED_CHAIN_DEADPOOL: ProviderDeadpool[ProviderType] = ProviderDeadpool()


async def complete_via_preferred_runtime_providers(
    *,
    messages: list[dict[str, str]],
    system: str = "",
    openrouter_model: str | None = None,
    anthropic_model: str | None = None,
    max_tokens: int = 4096,
    temperature: float = 0.7,
    provider_order: tuple[ProviderType, ...] | None = None,
    working_dir: str | None = None,
    timeout_seconds: float | None = None,
    env: Mapping[str, str] | None = None,
) -> tuple[LLMResponse, RuntimeProviderConfig]:
    """Complete an LLM request via the canonical cheap-first runtime stack."""

    overrides: dict[ProviderType, str | None] = {
        ProviderType.OPENROUTER_FREE: openrouter_model,
        ProviderType.OPENROUTER: openrouter_model,
    }
    if anthropic_model is not None:
        overrides[ProviderType.ANTHROPIC] = anthropic_model

    configs = preferred_runtime_provider_configs(
        provider_order=provider_order or PREFERRED_LOW_COST_RUNTIME_PROVIDERS,
        model_overrides=overrides,
        working_dir=working_dir,
        timeout_seconds=int(timeout_seconds) if timeout_seconds is not None else None,
        env=env,
    )
    if not configs:
        raise RuntimeError(
            "No dispatchable provider in the preferred chain. Dispatch is normally "
            "keyless via claude_code when headless `claude -p` smokes green — "
            "check key_oracle.dispatchable_now(); add Ollama/NVIDIA NIM/OpenRouter "
            "keys only to widen the roster."
        )

    active_configs = [
        config for config in configs
        if not _PREFERRED_CHAIN_DEADPOOL.active(config.provider)
    ]
    if active_configs:
        # Fail open when every lane is deadpooled: re-probe rather than refuse.
        configs = active_configs

    last_exc: Exception | None = None
    for config in configs:
        provider = create_runtime_provider(config)
        try:
            request = LLMRequest(
                model=config.default_model or anthropic_model or openrouter_model or DEFAULT_NIM_MODEL,
                messages=messages,
                system=system,
                max_tokens=max_tokens,
                temperature=temperature,
            )
            if timeout_seconds is not None:
                response = await asyncio.wait_for(
                    provider.complete(request),
                    timeout=timeout_seconds,
                )
            else:
                response = await provider.complete(request)
            _PREFERRED_CHAIN_DEADPOOL.clear(config.provider)
            return response, config
        except Exception as exc:
            last_exc = exc
            if is_connection_dead_error(exc):
                _PREFERRED_CHAIN_DEADPOOL.record(config.provider, error=str(exc)[:120])
        finally:
            close = getattr(provider, "close", None)
            if callable(close):
                await close()

    if last_exc is not None:
        raise last_exc
    raise RuntimeError("Preferred provider chain exhausted without an explicit error")


__all__ = [
    "CEREBRAS_BASE_URL",
    "DEFAULT_CLAUDE_MODEL",
    "DEFAULT_GROQ_MODEL",
    "DEFAULT_KIMI_CODE_MODEL",
    "DEFAULT_MOONSHOT_MODEL",
    "DEFAULT_FIREWORKS_MODEL",
    "DEFAULT_NIM_MODEL",
    "DEFAULT_OPENAI_MODEL",
    "DEFAULT_OPENROUTER_MODEL",
    "DEFAULT_PROVIDER_TIMEOUT_SECONDS",
    "DEFAULT_RUNTIME_PROVIDERS",
    "DEFAULT_SILICONFLOW_MODEL",
    "DEFAULT_TOGETHER_MODEL",
    "DEFAULT_ZHIPU_MODEL",
    "FIREWORKS_BASE_URL",
    "GOOGLE_AI_BASE_URL",
    "GROQ_BASE_URL",
    "KIMI_BASE_URL",
    "MOONSHOT_BASE_URL",
    "NVIDIA_NIM_BASE_URL",
    "OPENAI_BASE_URL",
    "OPENROUTER_BASE_URL",
    "PREFERRED_LOW_COST_RUNTIME_PROVIDERS",
    "PREFERRED_LOW_COST_WITH_ANTHROPIC_RUNTIME_PROVIDERS",
    "RuntimeProviderConfig",
    "deduplicate_runtime_provider_configs",
    "SILICONFLOW_BASE_URL",
    "TOGETHER_BASE_URL",
    "ZHIPU_BASE_URL",
    "complete_via_preferred_runtime_providers",
    "create_default_provider_map",
    "create_runtime_provider",
    "preferred_runtime_provider_configs",
    "resolve_runtime_provider_config",
    "runtime_provider_transport_identity",
]
