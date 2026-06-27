"""Provider routing for standalone Holon."""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, AsyncIterator, Protocol

from holon.contracts import LLMRequest, ProviderAttempt


@dataclass(frozen=True)
class ProviderResponse:
    content: str
    provider: str
    model: str
    finish_reason: str
    cost_usd: float
    attempts: list[ProviderAttempt]
    artifacts: list[object] | None = None
    tool_calls: list[object] | None = None
    usage: dict[str, Any] | None = None


class Provider(Protocol):
    name: str
    model: str

    async def stream(self, request: LLMRequest) -> AsyncIterator[str]:
        ...


class EchoProvider:
    name = "echo"

    def __init__(self, model: str = "holon-echo-v1") -> None:
        self.model = model

    async def stream(self, request: LLMRequest) -> AsyncIterator[str]:
        response = await self.complete(request)
        yield response.content

    async def complete(self, request: LLMRequest) -> ProviderResponse:
        prompt = request.messages[-1].get("content", "") if request.messages else ""
        return ProviderResponse(
            content=f"[echo:{request.model or self.model}] {prompt}",
            provider=self.name,
            model=request.model or self.model,
            finish_reason="stop",
            cost_usd=0.0,
            attempts=[],
        )


class OpenAICompatibleProvider:
    def __init__(
        self,
        *,
        name: str,
        api_key: str,
        base_url: str,
        model: str,
        timeout_seconds: float = 30.0,
        input_cost_per_mtok: float = 0.0,
        output_cost_per_mtok: float = 0.0,
        total_cost_per_mtok: float = 0.0,
    ) -> None:
        self.name = name
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout_seconds = timeout_seconds
        self.input_cost_per_mtok = max(0.0, float(input_cost_per_mtok or 0.0))
        self.output_cost_per_mtok = max(0.0, float(output_cost_per_mtok or 0.0))
        self.total_cost_per_mtok = max(0.0, float(total_cost_per_mtok or 0.0))

    async def stream(self, request: LLMRequest) -> AsyncIterator[str]:
        response = await self.complete(request)
        yield response.content

    async def complete(self, request: LLMRequest) -> ProviderResponse:
        payload = {
            "model": request.model or self.model,
            "messages": _messages_with_system(request),
            "stream": False,
        }
        if request.tools:
            payload["tools"] = [_openai_tool_spec(tool) for tool in request.tools]
            payload["tool_choice"] = "auto"
        body = json.dumps(payload).encode("utf-8")
        http_request = urllib.request.Request(
            f"{self.base_url}/chat/completions",
            data=body,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(http_request, timeout=self.timeout_seconds) as response:
                data = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:300]
            raise RuntimeError(f"{self.name} HTTP {exc.code}: {detail}") from exc
        choices = data.get("choices") or []
        if not choices:
            raise RuntimeError(f"{self.name} returned no choices")
        choice = choices[0]
        message = choice.get("message", {}) or {}
        content = str(message.get("content") or "")
        tool_calls = _normalize_openai_tool_calls(message.get("tool_calls") or [])
        usage = dict(data.get("usage") or {})
        cost_usd = estimate_usage_cost_usd(
            usage,
            input_cost_per_mtok=self.input_cost_per_mtok,
            output_cost_per_mtok=self.output_cost_per_mtok,
            total_cost_per_mtok=self.total_cost_per_mtok,
        )
        if tool_calls:
            content = json.dumps(
                {"content": content, "tool_calls": tool_calls},
                sort_keys=True,
                ensure_ascii=True,
            )
        return ProviderResponse(
            content=content,
            provider=self.name,
            model=request.model or self.model,
            finish_reason=str(choice.get("finish_reason") or "stop"),
            cost_usd=cost_usd,
            attempts=[],
            usage=usage,
        )


class ProviderRouter:
    def __init__(self, providers: list[Provider], *, retries: int = 1, max_cost_usd: float = 0.0) -> None:
        self.providers = providers or [EchoProvider()]
        self.retries = max(1, int(retries))
        self.max_cost_usd = max_cost_usd

    async def complete(self, request: LLMRequest) -> ProviderResponse:
        attempts: list[ProviderAttempt] = []
        spent = 0.0
        for provider in self.providers:
            for _ in range(self.retries):
                started = time.perf_counter()
                try:
                    completion = await _complete_provider(provider, request)
                    latency_ms = int((time.perf_counter() - started) * 1000)
                    spent += float(completion.cost_usd or 0.0)
                    if self.max_cost_usd > 0 and spent > self.max_cost_usd:
                        raise RuntimeError(
                            f"provider cost cap exceeded: spent={spent:.6f} cap={self.max_cost_usd:.6f}"
                        )
                    attempt = ProviderAttempt(
                        provider=provider.name,
                        model=completion.model or request.model or provider.model,
                        status="success",
                        latency_ms=latency_ms,
                        cost_usd=float(completion.cost_usd or 0.0),
                        finish_reason=completion.finish_reason,
                    )
                    attempts.append(attempt)
                    return ProviderResponse(
                        content=completion.content,
                        provider=completion.provider or provider.name,
                        model=completion.model or request.model or provider.model,
                        finish_reason=completion.finish_reason,
                        cost_usd=spent,
                        attempts=attempts,
                        artifacts=completion.artifacts,
                        tool_calls=completion.tool_calls,
                        usage=completion.usage,
                    )
                except Exception as exc:
                    latency_ms = int((time.perf_counter() - started) * 1000)
                    attempts.append(
                        ProviderAttempt(
                            provider=getattr(provider, "name", "unknown"),
                            model=request.model or getattr(provider, "model", ""),
                            status="failed",
                            latency_ms=latency_ms,
                            error=f"{type(exc).__name__}: {exc}"[:300],
                        )
                    )
                if self.max_cost_usd > 0 and spent >= self.max_cost_usd:
                    break
        errors = "; ".join(attempt.error for attempt in attempts if attempt.error)
        raise RuntimeError(f"all providers failed: {errors}")

    async def stream(self, request: LLMRequest) -> AsyncIterator[str]:
        response = await self.complete(request)
        yield response.content


def build_provider_router(
    env: dict[str, str] | None = None,
    *,
    preferred_provider: str = "auto",
    model: str = "",
) -> ProviderRouter:
    env_map = env if env is not None else os.environ
    preferred = (preferred_provider or "auto").strip().lower()
    providers: list[Provider] = []

    def add_openai() -> None:
        openai_key = env_map.get("OPENAI_API_KEY")
        if not openai_key:
            return
        providers.append(
            OpenAICompatibleProvider(
                name="openai",
                api_key=openai_key,
                base_url=env_map.get("OPENAI_BASE_URL", "https://api.openai.com/v1"),
                model=model or env_map.get("OPENAI_MODEL", "gpt-4.1-mini"),
                **_pricing_from_env(env_map, provider="OPENAI"),
            )
        )

    def add_openrouter() -> None:
        openrouter_key = env_map.get("OPENROUTER_API_KEY")
        if not openrouter_key:
            return
        providers.append(
            OpenAICompatibleProvider(
                name="openrouter",
                api_key=openrouter_key,
                base_url=env_map.get("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"),
                model=model or env_map.get("OPENROUTER_MODEL", "openai/gpt-4.1-mini"),
                **_pricing_from_env(env_map, provider="OPENROUTER"),
            )
        )

    if preferred == "echo":
        providers.append(EchoProvider(model=model or env_map.get("HOLON_ECHO_MODEL", "holon-echo-v1")))
    elif preferred == "openai":
        add_openai()
    elif preferred == "openrouter":
        add_openrouter()
    else:
        add_openai()
        add_openrouter()
    if not providers or preferred != "echo":
        providers.append(EchoProvider(model=model or env_map.get("HOLON_ECHO_MODEL", "holon-echo-v1")))
    return ProviderRouter(
        providers,
        retries=int(env_map.get("HOLON_PROVIDER_RETRIES", "1") or "1"),
        max_cost_usd=float(env_map.get("HOLON_MAX_COST_USD", "0") or "0"),
    )


async def _complete_provider(provider: Provider, request: LLMRequest) -> ProviderResponse:
    complete = getattr(provider, "complete", None)
    if callable(complete):
        return await complete(request)
    chunks = [chunk async for chunk in provider.stream(request)]
    return ProviderResponse(
        content="".join(chunks),
        provider=getattr(provider, "name", "unknown"),
        model=request.model or getattr(provider, "model", ""),
        finish_reason="stop",
        cost_usd=0.0,
        attempts=[],
    )


def _messages_with_system(request: LLMRequest) -> list[dict[str, str]]:
    messages: list[dict[str, str]] = []
    if request.system:
        messages.append({"role": "system", "content": request.system})
    for message in request.messages:
        messages.append(
            {
                "role": str(message.get("role", "user")),
                "content": str(message.get("content", "")),
            }
        )
    return messages


def _openai_tool_spec(tool: dict[str, Any]) -> dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": str(tool.get("name") or ""),
            "description": str(tool.get("description") or ""),
            "parameters": _json_schema(tool.get("schema") or {}),
        },
    }


def _json_schema(schema: dict[str, Any]) -> dict[str, Any]:
    if schema.get("type"):
        return dict(schema)
    properties: dict[str, Any] = {}
    for key, value in schema.items():
        if isinstance(value, dict):
            properties[str(key)] = value
            continue
        raw = str(value or "string")
        if "object" in raw:
            properties[str(key)] = {"type": "object"}
        elif "number" in raw or "float" in raw:
            properties[str(key)] = {"type": "number"}
        elif "int" in raw:
            properties[str(key)] = {"type": "integer"}
        elif "bool" in raw:
            properties[str(key)] = {"type": "boolean"}
        else:
            properties[str(key)] = {"type": "string"}
    return {"type": "object", "properties": properties}


def _normalize_openai_tool_calls(raw_calls: list[Any]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for item in raw_calls:
        if not isinstance(item, dict):
            continue
        function = item.get("function") or {}
        if not isinstance(function, dict):
            continue
        name = str(function.get("name") or "").strip()
        arguments = function.get("arguments") or {}
        if isinstance(arguments, str):
            try:
                arguments = json.loads(arguments)
            except json.JSONDecodeError:
                arguments = {"raw": arguments}
        if name:
            normalized.append({"name": name, "arguments": dict(arguments or {})})
    return normalized


def estimate_usage_cost_usd(
    usage: dict[str, Any],
    *,
    input_cost_per_mtok: float = 0.0,
    output_cost_per_mtok: float = 0.0,
    total_cost_per_mtok: float = 0.0,
) -> float:
    for key in ("cost_usd", "total_cost_usd", "total_cost", "cost"):
        value = usage.get(key)
        if value in (None, ""):
            continue
        try:
            reported = max(0.0, float(value))
            usage.setdefault("cost_usd_source", key)
            return reported
        except (TypeError, ValueError):
            continue
    input_rate = max(0.0, float(input_cost_per_mtok or 0.0))
    output_rate = max(0.0, float(output_cost_per_mtok or 0.0))
    total_rate = max(0.0, float(total_cost_per_mtok or 0.0))
    input_tokens = _usage_token_count(usage, "prompt_tokens", "input_tokens")
    output_tokens = _usage_token_count(usage, "completion_tokens", "output_tokens")
    total_tokens = _usage_token_count(usage, "total_tokens")
    estimated = 0.0
    if input_rate > 0.0 and input_tokens > 0:
        estimated += (input_tokens / 1_000_000.0) * input_rate
    if output_rate > 0.0 and output_tokens > 0:
        estimated += (output_tokens / 1_000_000.0) * output_rate
    if estimated <= 0.0 and total_rate > 0.0 and total_tokens > 0:
        estimated = (total_tokens / 1_000_000.0) * total_rate
    if estimated > 0.0:
        usage.setdefault("cost_usd_estimated", estimated)
        usage.setdefault("cost_usd_source", "configured_token_pricing")
    return estimated


def _usage_token_count(usage: dict[str, Any], *keys: str) -> int:
    for key in keys:
        value = usage.get(key)
        if value in (None, ""):
            continue
        try:
            return max(0, int(float(value)))
        except (TypeError, ValueError):
            continue
    return 0


def _pricing_from_env(env: dict[str, str], *, provider: str) -> dict[str, float]:
    return {
        "input_cost_per_mtok": _float_env(
            env,
            f"HOLON_{provider}_INPUT_USD_PER_1M_TOKENS",
            "HOLON_INPUT_USD_PER_1M_TOKENS",
        ),
        "output_cost_per_mtok": _float_env(
            env,
            f"HOLON_{provider}_OUTPUT_USD_PER_1M_TOKENS",
            "HOLON_OUTPUT_USD_PER_1M_TOKENS",
        ),
        "total_cost_per_mtok": _float_env(
            env,
            f"HOLON_{provider}_TOTAL_USD_PER_1M_TOKENS",
            "HOLON_TOTAL_USD_PER_1M_TOKENS",
        ),
    }


def _float_env(env: dict[str, str], *names: str) -> float:
    for name in names:
        value = env.get(name)
        if value in (None, ""):
            continue
        try:
            return max(0.0, float(value))
        except (TypeError, ValueError):
            continue
    return 0.0
