"""Restriction-only provider guards for authenticated SADHANA campaign work.

This module is deliberately an import leaf: it never imports the provider
implementation module.  Generic provider routing remains owned by
``dharma_swarm.providers``; the helpers here only narrow an already-authenticated
campaign call to one provider object, one logical model, and one physical
request.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass, field as dataclass_field
from typing import Any

from dharma_swarm.models import LLMRequest, LLMResponse, ProviderType
from dharma_swarm.ollama_config import OLLAMA_CLOUD_BASE_URL
from dharma_swarm.provider_policy import ProviderRouteDecision, ProviderRouteRequest


CAMPAIGN_EXACT_PROVIDER_CALL_KEY = "campaign_exact_provider_call"
CAMPAIGN_EXACT_PROVIDER_CALL_SCHEMA = (
    "dharma.sadhana.campaign_exact_provider_call.v1"
)
CAMPAIGN_EXACT_PROVIDER_CALL_FIELDS = frozenset(
    {
        "schema_version",
        "task_id",
        "principal_id",
        "provider",
        "model",
        "max_provider_attempts",
        "fallback_allowed",
    }
)
@dataclass(frozen=True, slots=True)
class CampaignProviderBoundary:
    """Process-local identity and mutable coordinates captured before an await."""

    provider_type: ProviderType
    provider: object
    default_model: object
    transport_mode: object
    base_url: object
    normalized_base_url: object


@dataclass(slots=True)
class CampaignProviderEffectBoundary:
    """One-shot two-phase authority for the final provider-effect transition.

    The durable fence must finish before this object becomes ``fenced``.  The
    caller may mark the effect ready only after every post-fence identity and
    route recheck has succeeded.  A failed recheck therefore remains visibly
    pre-effect and eligible for the orchestrator's exact recovery path.
    """

    _await_fence_callback: Callable[[], Awaitable[None]]
    _mark_ready_callback: Callable[[], None]
    _phase: str = dataclass_field(default="pending", init=False)

    @property
    def started(self) -> bool:
        return self._phase == "started"

    async def await_fence(self) -> None:
        if self._phase != "pending":
            raise RuntimeError("campaign provider fence is not pending")
        await self._await_fence_callback()
        if self._phase != "pending":
            raise RuntimeError("campaign provider fence changed while awaiting")
        self._phase = "fenced"

    def mark_ready(self) -> None:
        if self._phase != "fenced":
            raise RuntimeError("campaign provider effect is not fenced")
        self._mark_ready_callback()
        self._phase = "started"


def effect_started(boundary: CampaignProviderEffectBoundary | None) -> bool:
    """Return whether the final ready transition happened for this attempt."""
    return boundary is not None and boundary.started


@dataclass(frozen=True, slots=True)
class RoutedCampaignInvocation:
    """Immutable process-local effect coordinates captured before telemetry."""

    provider_type: ProviderType
    model: str
    provider: object
    provider_boundary: CampaignProviderBoundary
    source_request: LLMRequest
    source_request_dump: dict[str, Any]
    request: LLMRequest
    complete: Callable[[LLMRequest], Awaitable[LLMResponse]]


def _exact_text(value: object) -> bool:
    return (
        isinstance(value, str)
        and bool(value)
        and value == value.strip()
        and not any(char.isspace() for char in value)
    )


def _normalized_origin(value: object) -> object:
    if not isinstance(value, str):
        return value
    return value.strip().rstrip("/")


def capture_campaign_provider_boundary(
    provider_type: ProviderType,
    provider: object,
) -> CampaignProviderBoundary:
    """Capture the exact provider instance and all mutable Ollama coordinates."""
    if provider_type is not ProviderType.OLLAMA:
        raise RuntimeError("SADHANA campaign execution requires the Ollama lane")
    return CampaignProviderBoundary(
        provider_type=provider_type,
        provider=provider,
        default_model=getattr(provider, "_model", None),
        transport_mode=getattr(provider, "_transport_mode", None),
        base_url=getattr(provider, "_base_url", None),
        normalized_base_url=_normalized_origin(getattr(provider, "_base_url", None)),
    )


def require_campaign_provider_boundary(
    boundary: CampaignProviderBoundary,
    *,
    provider_type: ProviderType,
    provider: object,
) -> None:
    """Reject provider substitution or coordinate drift across an awaited fence."""
    current = capture_campaign_provider_boundary(provider_type, provider)
    if (
        current.provider is not boundary.provider
        or current.provider_type is not boundary.provider_type
        or current.default_model != boundary.default_model
        or current.transport_mode != boundary.transport_mode
        or current.base_url != boundary.base_url
        or current.normalized_base_url != boundary.normalized_base_url
    ):
        raise RuntimeError("campaign provider boundary changed before effect")


def build_campaign_exact_provider_call(
    *,
    task_id: str,
    principal_id: str,
    provider: str,
    model: str,
) -> dict[str, Any]:
    """Build a closed, restriction-only carrier for one provider invocation."""
    coordinates = (task_id, principal_id, provider, model)
    if not all(_exact_text(value) for value in coordinates):
        raise ValueError("campaign provider coordinates must be exact text")
    return {
        "schema_version": CAMPAIGN_EXACT_PROVIDER_CALL_SCHEMA,
        "task_id": task_id,
        "principal_id": principal_id,
        "provider": provider,
        "model": model,
        "max_provider_attempts": 1,
        "fallback_allowed": False,
    }


def campaign_exact_provider_call(
    route_request: ProviderRouteRequest,
    request: LLMRequest,
    available_provider_types: list[ProviderType] | None,
    effect_boundary: CampaignProviderEffectBoundary | None,
) -> dict[str, Any] | None:
    """Validate and return the exact campaign carrier, if present."""
    value = route_request.context.get(CAMPAIGN_EXACT_PROVIDER_CALL_KEY)
    if (value is None) != (effect_boundary is None):
        raise RuntimeError(
            "campaign provider-call fence and final effect boundary are inseparable"
        )
    if value is None:
        return None
    if type(effect_boundary) is not CampaignProviderEffectBoundary:
        raise RuntimeError("campaign provider effect boundary is not audited")
    if not isinstance(value, dict) or set(value) != CAMPAIGN_EXACT_PROVIDER_CALL_FIELDS:
        raise RuntimeError("campaign provider-call fence is malformed")
    provider_raw = value.get("provider")
    try:
        provider = ProviderType(provider_raw)
    except (TypeError, ValueError) as exc:
        raise RuntimeError("campaign provider-call fence names an invalid provider") from exc
    model = value.get("model")
    if not all(
        _exact_text(item)
        for item in (
            value.get("task_id"),
            value.get("principal_id"),
            provider_raw,
            model,
        )
    ):
        raise RuntimeError("campaign provider-call fence coordinates are not exact")
    if (
        provider is not ProviderType.OLLAMA
        or value.get("schema_version") != CAMPAIGN_EXACT_PROVIDER_CALL_SCHEMA
        or type(value.get("max_provider_attempts")) is not int
        or value.get("max_provider_attempts") != 1
        or value.get("fallback_allowed") is not False
        or request.model != model
        or available_provider_types != [provider]
        or route_request.context.get("task_id") != value.get("task_id")
        or route_request.context.get("agent_id") != value.get("principal_id")
        or route_request.context.get("available_provider_types") != [provider.value]
        or route_request.context.get("preferred_provider") != provider.value
        or route_request.context.get("preferred_model") != model
        or route_request.context.get("preserve_requested_model") is not True
    ):
        raise RuntimeError("campaign provider-call fence conflicts with routing request")
    return value


def require_exact_campaign_route(
    fence: dict[str, Any],
    decision: ProviderRouteDecision,
    chain: list[ProviderType],
    model_hints: dict[ProviderType, str | None],
) -> None:
    """Reject every routed fallback or model overlay before provider selection."""
    provider = ProviderType(fence["provider"])
    if (
        decision.selected_provider is not provider
        or decision.selected_model_hint != fence["model"]
        or decision.fallback_providers != []
        or decision.fallback_model_hints != []
        or chain != [provider]
        or model_hints != {provider: fence["model"]}
    ):
        raise RuntimeError("campaign provider route is not exact and fallback-free")


def capture_routed_campaign_invocation(
    fence: dict[str, Any] | None,
    *,
    decision: ProviderRouteDecision,
    chain: list[ProviderType],
    model_hints: dict[ProviderType, str | None],
    providers: Mapping[ProviderType, object],
    request: LLMRequest,
    inject_request: Callable[[LLMRequest], LLMRequest],
) -> RoutedCampaignInvocation | None:
    """Freeze the sole routed provider effect before an awaited telemetry seam."""
    if fence is None:
        return None
    require_exact_campaign_route(fence, decision, chain, model_hints)
    provider_type = ProviderType(fence["provider"])
    provider = providers.get(provider_type)
    if provider is None:
        raise RuntimeError("campaign exact provider is unavailable")
    complete = getattr(provider, "complete_exact_model", None)
    if not callable(complete):
        raise RuntimeError(
            f"Provider {provider_type.value!r} lacks exact-model execution"
        )
    model = fence["model"]
    request_for_provider = (
        request
        if request.model == model
        else request.model_copy(update={"model": model})
    )
    frozen_request = inject_request(request_for_provider).model_copy(deep=True)
    return RoutedCampaignInvocation(
        provider_type=provider_type,
        model=model,
        provider=provider,
        provider_boundary=capture_campaign_provider_boundary(provider_type, provider),
        source_request=request,
        source_request_dump=request.model_dump(mode="python"),
        request=frozen_request,
        complete=complete,
    )


def require_routed_campaign_invocation(
    invocation: RoutedCampaignInvocation | None,
    *,
    providers: Mapping[ProviderType, object],
    chain: list[ProviderType],
    model_hints: dict[ProviderType, str | None],
) -> None:
    """Fail closed on registry, provider-coordinate, route, or request drift."""
    if invocation is None:
        return
    current_provider = providers.get(invocation.provider_type)
    if current_provider is None:
        raise RuntimeError("campaign exact provider disappeared before effect")
    require_campaign_provider_boundary(
        invocation.provider_boundary,
        provider_type=invocation.provider_type,
        provider=current_provider,
    )
    if (
        chain != [invocation.provider_type]
        or model_hints != {invocation.provider_type: invocation.model}
        or invocation.source_request.model_dump(mode="python")
        != invocation.source_request_dump
    ):
        raise RuntimeError("campaign routed coordinates changed before effect")


async def execute_routed_campaign_invocation(
    invocation: RoutedCampaignInvocation,
    boundary: CampaignProviderEffectBoundary,
    *,
    providers: Mapping[ProviderType, object],
    chain: list[ProviderType],
    model_hints: dict[ProviderType, str | None],
    on_provider_error: Callable[[Exception, int], None],
) -> LLMResponse:
    """Fence, recheck, mark ready, and immediately enter the captured provider."""
    require_routed_campaign_invocation(
        invocation,
        providers=providers,
        chain=chain,
        model_hints=model_hints,
    )
    await boundary.await_fence()
    require_routed_campaign_invocation(
        invocation,
        providers=providers,
        chain=chain,
        model_hints=model_hints,
    )
    boundary.mark_ready()
    try:
        response = await invocation.complete(invocation.request)
        if getattr(response, "provider", None) != invocation.provider_type.value:
            raise RuntimeError(
                "campaign response provider conflicts with exact routed invocation"
            )
        if getattr(response, "model", None) != invocation.model:
            raise RuntimeError(
                "campaign response model conflicts with exact routed invocation"
            )
        return response
    except Exception as exc:
        on_provider_error(exc, 1)
        raise


def ollama_cloud_wire_model(model: str) -> str:
    """Map one explicit logical ``:cloud`` identity to its exact wire ID."""
    stripped = (model or "").strip()
    if stripped.endswith(":cloud"):
        return stripped[:-6]
    return stripped


def ollama_cloud_completion_limit(model: str, max_tokens: int) -> int:
    """Preserve the generic cloud endpoint's bounded model token floor."""
    normalized = ollama_cloud_wire_model(model).lower()
    if normalized.startswith("glm-5"):
        return max(max_tokens, 4096)
    if normalized.startswith("kimi-k2.5") or normalized.startswith("minimax-m2.7"):
        return max(max_tokens, 4096)
    return max(max_tokens, 2048)


def _coerce_json_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, list):
        return "\n".join(filter(None, (_coerce_json_text(item) for item in value)))
    if isinstance(value, dict):
        for key in ("text", "content", "output_text"):
            text = _coerce_json_text(value.get(key))
            if text:
                return text
    return ""


def _extract_json_message_text(message: dict[str, Any]) -> str:
    for field in ("content", "reasoning", "reasoning_content", "reasoning_details"):
        text = _coerce_json_text(message.get(field))
        if text:
            return text
    return ""


async def complete_exact_ollama_cloud(
    provider: object,
    request: LLMRequest,
) -> LLMResponse:
    """Issue exactly one physical request for one authenticated logical model.

    Origin, transport, and logical-model checks deliberately precede message
    building, header construction, client construction, and the sole await.
    """
    model = request.model
    origin = _normalized_origin(getattr(provider, "_base_url", None))
    if (
        not _exact_text(model)
        or not model.endswith(":cloud")
        or not ollama_cloud_wire_model(model)
        or getattr(provider, "_transport_mode", None) != "cloud_api"
        or origin != OLLAMA_CLOUD_BASE_URL
    ):
        raise RuntimeError(
            "exact Ollama campaign execution requires the exact trusted Ollama "
            "Cloud origin and an explicit :cloud model"
        )

    messages: list[dict[str, str]] = []
    if request.system:
        messages.append({"role": "system", "content": request.system})
    messages.extend(request.messages)
    get_client = getattr(provider, "_get_client", None)
    headers_or_raise = getattr(provider, "_headers_or_raise", None)
    if not callable(get_client) or not callable(headers_or_raise):
        raise RuntimeError("Ollama exact-model provider surface is incomplete")
    client = get_client()
    headers = headers_or_raise()
    headers["Content-Type"] = "application/json"
    wire_model = ollama_cloud_wire_model(model)
    payload: dict[str, Any] = {
        "model": wire_model,
        "messages": messages,
        "max_tokens": ollama_cloud_completion_limit(wire_model, request.max_tokens),
        "temperature": request.temperature,
        "stream": False,
    }
    if request.tools:
        payload["tools"] = request.tools
    try:
        response = await client.post(
            f"{origin}/v1/chat/completions",
            json=payload,
            headers=headers,
        )
    except Exception as exc:
        raise RuntimeError(f"Ollama exact cloud request failed: {exc}") from exc
    if response.status_code != 200:
        raise RuntimeError(
            "Ollama exact cloud error: "
            f"{response.status_code}: {response.text[:300]}"
        )
    data = response.json()
    if data.get("model") != wire_model:
        raise RuntimeError(
            "Ollama exact-model response did not attest the requested wire model"
        )
    choice = (data.get("choices") or [{}])[0]
    message = choice.get("message") or {}
    usage = data.get("usage") or {}
    tool_calls: list[dict[str, Any]] = []
    for item in message.get("tool_calls") or []:
        function = item.get("function") or {}
        tool_calls.append(
            {
                "id": item.get("id", ""),
                "name": function.get("name", ""),
                "arguments": function.get("arguments", "{}"),
            }
        )
    return LLMResponse(
        content=_extract_json_message_text(message),
        model=model,
        provider=ProviderType.OLLAMA.value,
        usage={
            "prompt_tokens": int(usage.get("prompt_tokens") or 0),
            "completion_tokens": int(usage.get("completion_tokens") or 0),
            "total_tokens": int(usage.get("total_tokens") or 0),
        },
        tool_calls=tool_calls,
        stop_reason=str(choice.get("finish_reason") or "stop"),
    )
