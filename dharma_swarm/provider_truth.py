"""Provider truth normalization for dispatch EvidenceReceipts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple


@dataclass(frozen=True)
class ProviderTruthSnapshot:
    requested_provider: str
    requested_model: str
    planned_provider: str
    planned_model: str
    actual_provider: str
    actual_model: str
    route_path: str
    route_confidence: Any
    route_reasons: List[str]
    route_fallback_plan: List[Dict[str, str]]
    route_requires_human: bool
    provider_truth_source: str
    fallback_used: bool
    actual_differs_from_requested: bool
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None

    def receipt_attributes(self) -> Dict[str, Any]:
        return {
            "requested_provider": self.requested_provider,
            "requested_model": self.requested_model,
            "planned_provider": self.planned_provider,
            "actual_provider": self.actual_provider,
            "served_provider": self.actual_provider,
            "planned_model": self.planned_model,
            "actual_model": self.actual_model,
            "served_model": self.actual_model,
            "route_path": self.route_path,
            "route_confidence": self.route_confidence,
            "route_reasons": self.route_reasons,
            "route_fallback_plan": self.route_fallback_plan,
            "route_requires_human": self.route_requires_human,
            "provider_truth_source": self.provider_truth_source,
            "fallback_used": self.fallback_used,
            "actual_differs_from_requested": self.actual_differs_from_requested,
        }


def _provider_value(value: Any) -> str:
    if value is None:
        return ""
    raw = getattr(value, "value", value)
    return str(raw or "")


def _route_context(runner: Any) -> Dict[str, Any]:
    route_request = getattr(runner, "_last_route_request", None)
    context = getattr(route_request, "context", None)
    return dict(context) if isinstance(context, dict) else {}


def _route_reasons(route_decision: Any) -> List[str]:
    reasons = getattr(route_decision, "reasons", None)
    if not isinstance(reasons, list):
        return []
    return [str(item) for item in reasons]


def _route_fallback_plan(route_decision: Any) -> List[Dict[str, str]]:
    providers = list(getattr(route_decision, "fallback_providers", []) or [])
    models = list(getattr(route_decision, "fallback_model_hints", []) or [])
    plan: List[Dict[str, str]] = []
    for index, item in enumerate(providers):
        plan.append(
            {
                "provider": _provider_value(item),
                "model": str(models[index] if index < len(models) else ""),
            }
        )
    return plan


def _usage_tokens(runner: Any) -> Tuple[Optional[int], Optional[int]]:
    usage = getattr(runner, "_last_usage", None)
    if not isinstance(usage, dict):
        return (None, None)
    input_tokens = usage.get("input_tokens") or usage.get("prompt_tokens")
    output_tokens = usage.get("output_tokens") or usage.get("completion_tokens")
    return (input_tokens, output_tokens)


def build_provider_truth_snapshot(
    runner: Any,
    *,
    requested_provider: str,
    requested_model: str,
) -> ProviderTruthSnapshot:
    """Build receipt-ready provider/model truth from runner telemetry.

    The precedence is deliberately narrow: actual LLM response first, provider
    route decision second, and runner config only as the fallback for direct
    providers or no-network test shims.
    """

    route_decision = getattr(runner, "_last_route_decision", None)
    response = getattr(runner, "_last_response", None)
    route_context = _route_context(runner)
    route_reasons = _route_reasons(route_decision)
    routed_provider = _provider_value(getattr(route_decision, "selected_provider", None))
    routed_model = str(getattr(route_decision, "selected_model_hint", "") or "")
    response_provider = str(getattr(response, "provider", "") or "")
    response_model = str(getattr(response, "model", "") or "")
    actual_provider = response_provider or routed_provider or requested_provider
    actual_model = response_model or routed_model or requested_model
    truth_source = "runner_config"
    if response_provider or response_model:
        truth_source = "llm_response"
    elif routed_provider or routed_model:
        truth_source = "provider_route_decision"
    route_path = getattr(getattr(route_decision, "path", None), "value", None)
    input_tokens, output_tokens = _usage_tokens(runner)

    return ProviderTruthSnapshot(
        requested_provider=requested_provider,
        requested_model=requested_model,
        planned_provider=str(route_context.get("preferred_provider") or requested_provider),
        planned_model=str(route_context.get("preferred_model") or requested_model),
        actual_provider=actual_provider,
        actual_model=actual_model,
        route_path=str(route_path or ""),
        route_confidence=getattr(route_decision, "confidence", None),
        route_reasons=route_reasons,
        route_fallback_plan=_route_fallback_plan(route_decision),
        route_requires_human=bool(getattr(route_decision, "requires_human", False)),
        provider_truth_source=truth_source,
        fallback_used="fallback_provider_selected" in route_reasons,
        actual_differs_from_requested=actual_provider != requested_provider,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
    )
