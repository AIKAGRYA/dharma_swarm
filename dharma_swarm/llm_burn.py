"""Local-first LLM burn normalization.

The repo already records LLM activity in a few JSONL formats:
``cost_log.jsonl``, ``traces/cost_ledger.jsonl``, and daily trace files.  This
module turns those local records into a small OpenInference-style shape without
requiring OpenInference, OpenTelemetry, Langfuse, or LiteLLM at runtime.
"""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable

from dharma_swarm.cost_tracker import _estimate_cost as _estimate_model_cost
from dharma_swarm.observability import _estimate_cost as _estimate_provider_cost

FREE_PROVIDERS = {
    "local",
    "nvidia_nim",
    "ollama",
    "ollama_cloud",
    "openrouter_free",
}

FREE_MODEL_MARKERS = (
    ":free",
    "glm-5",
    "kimi-k2.5",
    "minimax-m2.7",
)


@dataclass(frozen=True)
class LLMUsageSpan:
    """Normalized LLM usage record with OpenInference-style attributes."""

    trace_id: str
    span_id: str
    parent_span_id: str = ""
    name: str = ""
    kind: str = "llm_call"
    status: str = "ok"
    timestamp: str = ""
    duration_ms: float = 0.0
    provider: str = ""
    model: str = ""
    input_tokens: int = 0
    output_tokens: int = 0
    logged_cost_usd: float = 0.0
    estimated_cost_usd: float = 0.0
    cost_source: str = "unknown"
    error: str = ""
    source: str = ""
    attributes: dict[str, Any] = field(default_factory=dict)

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens

    @property
    def effective_cost_usd(self) -> float:
        return self.logged_cost_usd or self.estimated_cost_usd

    def to_openinference_attributes(self) -> dict[str, Any]:
        """Return a dependency-free OpenInference-style attribute dict."""
        attrs = dict(self.attributes)
        attrs.update(
            {
                "openinference.span.kind": "LLM",
                "llm.provider": self.provider,
                "llm.model_name": self.model,
                "llm.token_count.prompt": self.input_tokens,
                "llm.token_count.completion": self.output_tokens,
                "llm.token_count.total": self.total_tokens,
                "llm.cost.usd": round(self.effective_cost_usd, 6),
                "llm.cost.logged_usd": round(self.logged_cost_usd, 6),
                "llm.cost.estimated_usd": round(self.estimated_cost_usd, 6),
                "dharma.cost_source": self.cost_source,
                "dharma.source": self.source,
                "dharma.status": self.status,
                "dharma.trace_id": self.trace_id,
                "dharma.span_id": self.span_id,
            }
        )
        if self.error:
            attrs["exception.message"] = self.error
        return attrs


@dataclass(frozen=True)
class LLMBurnRollup:
    spans: int = 0
    error_spans: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    logged_cost_usd: float = 0.0
    estimated_cost_usd: float = 0.0
    zero_token_spans: int = 0
    unpriced_spans: int = 0
    by_provider: dict[str, int] = field(default_factory=dict)
    by_model: dict[str, int] = field(default_factory=dict)
    by_source: dict[str, int] = field(default_factory=dict)
    by_cost_source: dict[str, int] = field(default_factory=dict)
    top_failure_provider: str = ""
    top_failure_model: str = ""

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens

    @property
    def total_cost_usd(self) -> float:
        return round(self.logged_cost_usd + self.estimated_cost_usd, 6)


def load_llm_usage_spans(
    state_dir: str | Path,
    *,
    now: datetime,
    since_hours: float = 24.0,
) -> list[LLMUsageSpan]:
    """Load normalized LLM spans from local Dharma state."""
    state = Path(state_dir).expanduser()
    cutoff = now.timestamp() - (since_hours * 3600)
    spans: list[LLMUsageSpan] = []

    for row in _read_jsonl(state / "cost_log.jsonl"):
        span = span_from_cost_log(row, source="cost_log")
        if span is not None and _span_in_window(span, cutoff):
            spans.append(span)

    for row in _read_jsonl(state / "traces" / "cost_ledger.jsonl"):
        span = span_from_trace_cost_ledger(row, source="trace_cost_ledger")
        if span is not None and _span_in_window(span, cutoff):
            spans.append(span)

    for path in _trace_files_for_window(state / "traces", now=now, since_hours=since_hours):
        for row in _read_jsonl(path):
            span = span_from_trace_row(row, source="trace_dispatch")
            if span is not None and _span_in_window(span, cutoff):
                spans.append(span)

    return spans


def load_llm_burn_rollup(
    state_dir: str | Path,
    *,
    now: datetime,
    since_hours: float = 24.0,
) -> LLMBurnRollup:
    return rollup_llm_usage(load_llm_usage_spans(state_dir, now=now, since_hours=since_hours))


def span_from_cost_log(row: dict[str, Any], *, source: str = "cost_log") -> LLMUsageSpan | None:
    if not isinstance(row, dict):
        return None
    provider = _string(row.get("provider"))
    model = _string(row.get("model"))
    input_tokens = _int(row.get("input_tokens"))
    output_tokens = _int(row.get("output_tokens"))
    estimate = _float(row.get("estimated_cost_usd")) or _estimate_cost(provider, model, input_tokens, output_tokens)
    return _make_span(
        trace_id=_string(row.get("trace_id")) or _string(row.get("task_id")) or "cost_log",
        span_id=(
            _string(row.get("span_id"))
            or _string(row.get("task_id"))
            or _string(row.get("timestamp"))
            or "cost_log"
        ),
        name=_string(row.get("task_title")) or "cost_log",
        kind="llm_call",
        status="ok",
        timestamp=_iso_timestamp(row, "timestamp"),
        provider=provider,
        model=model,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        logged_cost_usd=0.0,
        estimated_cost_usd=estimate,
        cost_source=_cost_source(
            logged_cost=0.0,
            estimated_cost=estimate,
            provider=provider,
            model=model,
            total_tokens=input_tokens + output_tokens,
            recorded_estimate=bool(row.get("estimated_cost_usd") is not None),
        ),
        source=source,
        attributes={k: v for k, v in row.items() if k not in {"timestamp"}},
    )


def span_from_trace_cost_ledger(
    row: dict[str, Any],
    *,
    source: str = "trace_cost_ledger",
) -> LLMUsageSpan | None:
    if not isinstance(row, dict):
        return None
    provider = _string(row.get("provider"))
    model = _string(row.get("model"))
    input_tokens = _int(row.get("prompt_tokens") or row.get("input_tokens"))
    output_tokens = _int(row.get("completion_tokens") or row.get("output_tokens"))
    recorded = _float(row.get("actual_cost_usd") or row.get("billed_cost_usd")) or 0.0
    estimate = _float(row.get("cost_usd") or row.get("estimated_cost_usd")) or _estimate_cost(
        provider,
        model,
        input_tokens,
        output_tokens,
    )
    return _make_span(
        trace_id=_string(row.get("trace_id")) or _string(row.get("task_id")) or "trace_cost_ledger",
        span_id=(
            _string(row.get("span_id"))
            or _string(row.get("task_id"))
            or _string(row.get("timestamp"))
            or "trace_cost_ledger"
        ),
        name=_string(row.get("agent")) or "trace_cost_ledger",
        kind="llm_call",
        status="ok",
        timestamp=_iso_timestamp(row, "timestamp"),
        provider=provider,
        model=model,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        logged_cost_usd=recorded,
        estimated_cost_usd=0.0 if recorded else estimate,
        cost_source=_cost_source(
            logged_cost=recorded,
            estimated_cost=estimate,
            provider=provider,
            model=model,
            total_tokens=input_tokens + output_tokens,
            recorded_estimate=bool(row.get("cost_usd") is not None or row.get("estimated_cost_usd") is not None),
        ),
        source=source,
        attributes={k: v for k, v in row.items() if k not in {"timestamp"}},
    )


def span_from_trace_row(row: dict[str, Any], *, source: str = "trace_dispatch") -> LLMUsageSpan | None:
    if not isinstance(row, dict):
        return None
    attrs = row.get("attributes") if isinstance(row.get("attributes"), dict) else {}
    kind = _string(row.get("kind"))
    provider = _string(attrs.get("provider"))
    model = _string(attrs.get("model"))
    input_tokens = _int(attrs.get("prompt_tokens") or attrs.get("input_tokens"))
    output_tokens = _int(attrs.get("completion_tokens") or attrs.get("output_tokens"))
    cost = _float(attrs.get("actual_cost_usd") or attrs.get("billed_cost_usd")) or 0.0
    estimate = _float(attrs.get("cost_usd") or attrs.get("estimated_cost_usd")) or _estimate_cost(
        provider,
        model,
        input_tokens,
        output_tokens,
    )
    has_usage_signal = bool(provider or model or input_tokens or output_tokens or cost or estimate)
    if kind not in {"agent_dispatch", "llm_call"} and not has_usage_signal:
        return None
    status = _string(row.get("status")).lower() or ("ok" if attrs.get("success") is not False else "error")
    error = _string(attrs.get("error"))
    if attrs.get("success") is False:
        status = "error"
    return _make_span(
        trace_id=_string(row.get("trace_id")) or "trace",
        span_id=_string(row.get("span_id")) or _string(row.get("trace_id")) or "span",
        parent_span_id=_string(row.get("parent_span_id")),
        name=_string(row.get("name")) or kind or "trace_span",
        kind=kind or "llm_call",
        status=status,
        timestamp=_iso_timestamp(row, "end_time", "start_time"),
        duration_ms=_float(row.get("duration_ms")) or 0.0,
        provider=provider,
        model=model,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        logged_cost_usd=cost,
        estimated_cost_usd=0.0 if cost else estimate,
        cost_source=_cost_source(
            logged_cost=cost,
            estimated_cost=estimate,
            provider=provider,
            model=model,
            total_tokens=input_tokens + output_tokens,
            recorded_estimate=bool(attrs.get("cost_usd") is not None or attrs.get("estimated_cost_usd") is not None),
        ),
        error=error,
        source=source,
        attributes=attrs,
    )


def rollup_llm_usage(spans: Iterable[LLMUsageSpan]) -> LLMBurnRollup:
    span_list = list(spans)
    by_provider: Counter[str] = Counter()
    by_model: Counter[str] = Counter()
    by_source: Counter[str] = Counter()
    by_cost_source: Counter[str] = Counter()
    failure_providers: Counter[str] = Counter()
    failure_models: Counter[str] = Counter()
    for span in span_list:
        provider = span.provider or "unknown"
        model = span.model or "unknown"
        by_provider[provider] += 1
        by_model[model] += 1
        by_source[span.source or "unknown"] += 1
        by_cost_source[span.cost_source] += 1
        if _is_error(span):
            failure_providers[provider] += 1
            failure_models[model] += 1
    return LLMBurnRollup(
        spans=len(span_list),
        error_spans=sum(1 for span in span_list if _is_error(span)),
        input_tokens=sum(span.input_tokens for span in span_list),
        output_tokens=sum(span.output_tokens for span in span_list),
        logged_cost_usd=round(sum(span.logged_cost_usd for span in span_list), 6),
        estimated_cost_usd=round(sum(span.estimated_cost_usd for span in span_list), 6),
        zero_token_spans=sum(1 for span in span_list if span.total_tokens == 0),
        unpriced_spans=sum(
            1
            for span in span_list
            if span.cost_source in {"unknown_provider", "unknown", "zero_tokens"}
        ),
        by_provider=dict(sorted(by_provider.items())),
        by_model=dict(sorted(by_model.items())),
        by_source=dict(sorted(by_source.items())),
        by_cost_source=dict(sorted(by_cost_source.items())),
        top_failure_provider=_top(failure_providers),
        top_failure_model=_top(failure_models),
    )


def spans_to_openinference_dicts(spans: Iterable[LLMUsageSpan]) -> list[dict[str, Any]]:
    return [
        {
            "trace_id": span.trace_id,
            "span_id": span.span_id,
            "parent_span_id": span.parent_span_id,
            "name": span.name,
            "kind": span.kind,
            "status": span.status,
            "timestamp": span.timestamp,
            "duration_ms": span.duration_ms,
            "attributes": span.to_openinference_attributes(),
        }
        for span in spans
    ]


def _make_span(**kwargs: Any) -> LLMUsageSpan:
    kwargs["logged_cost_usd"] = round(_float(kwargs.get("logged_cost_usd")) or 0.0, 6)
    kwargs["estimated_cost_usd"] = round(_float(kwargs.get("estimated_cost_usd")) or 0.0, 6)
    return LLMUsageSpan(**kwargs)


def _estimate_cost(provider: str, model: str, input_tokens: int, output_tokens: int) -> float:
    if input_tokens + output_tokens <= 0:
        return 0.0
    model_cost = _estimate_model_cost(model, input_tokens, output_tokens) if model else 0.0
    if model_cost or _looks_free(provider, model):
        return model_cost
    if provider:
        return round(_estimate_provider_cost(provider, input_tokens, output_tokens), 6)
    return 0.0


def _cost_source(
    *,
    logged_cost: float,
    estimated_cost: float,
    provider: str,
    model: str,
    total_tokens: int,
    recorded_estimate: bool,
) -> str:
    if logged_cost > 0:
        return "logged"
    if total_tokens <= 0:
        return "zero_tokens"
    if estimated_cost > 0:
        return "recorded_estimate" if recorded_estimate else "estimated"
    if _looks_free(provider, model):
        return "free_provider"
    if not provider and not model:
        return "unknown_provider"
    return "unknown"


def _looks_free(provider: str, model: str) -> bool:
    provider_key = provider.lower().replace("-", "_").replace(" ", "_")
    model_key = model.lower()
    return provider_key in FREE_PROVIDERS or any(marker in model_key for marker in FREE_MODEL_MARKERS)


def _span_in_window(span: LLMUsageSpan, cutoff: float) -> bool:
    timestamp = _timestamp_seconds(span.timestamp)
    return timestamp is None or timestamp >= cutoff


def _trace_files_for_window(traces_dir: Path, *, now: datetime, since_hours: float) -> list[Path]:
    if not traces_dir.exists():
        return []
    cutoff = datetime.fromtimestamp(now.timestamp() - (since_hours * 3600), tz=now.tzinfo)
    dates: set[str] = set()
    cursor = cutoff.date()
    while cursor <= now.date():
        dates.add(cursor.isoformat())
        cursor += timedelta(days=1)
    cursor = cutoff.astimezone(timezone.utc).date()
    end = now.astimezone(timezone.utc).date()
    while cursor <= end:
        dates.add(cursor.isoformat())
        cursor += timedelta(days=1)
    return [path for date in sorted(dates) if (path := traces_dir / f"traces_{date}.jsonl").exists()]


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    rows: list[dict[str, Any]] = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        try:
            row = json.loads(stripped)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict):
            rows.append(row)
    return rows


def _iso_timestamp(row: dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = row.get(key)
        if value is None or value == "":
            continue
        if isinstance(value, (int, float)):
            return datetime.fromtimestamp(float(value), tz=timezone.utc).isoformat()
        if isinstance(value, str):
            return value
    return ""


def _timestamp_seconds(value: str) -> float | None:
    numeric = _float(value)
    if numeric is not None:
        return numeric
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.timestamp()


def _is_error(span: LLMUsageSpan) -> bool:
    return span.status.lower() == "error" or bool(span.error)


def _top(counter: Counter[str]) -> str:
    if not counter:
        return ""
    value, count = counter.most_common(1)[0]
    return f"{value}={count}"


def _float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _int(value: Any) -> int:
    return int(_float(value) or 0)


def _string(value: Any) -> str:
    return str(value or "").strip()


__all__ = [
    "LLMBurnRollup",
    "LLMUsageSpan",
    "load_llm_burn_rollup",
    "load_llm_usage_spans",
    "rollup_llm_usage",
    "span_from_cost_log",
    "span_from_trace_cost_ledger",
    "span_from_trace_row",
    "spans_to_openinference_dicts",
]
