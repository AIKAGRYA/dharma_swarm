"""Cost tracking for LLM calls across all providers.

Logs every call with provider, model, tokens, estimated cost, and lane context.
Appended to ~/.dharma/cost_log.jsonl for analysis.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_STATE_DIR = Path.home() / ".dharma"
_COST_LOG = _STATE_DIR / "cost_log.jsonl"

_FREE_PROVIDERS = {
    "ollama",
    "openrouter_free",
    "nvidia_nim",
    "groq",
    "cerebras",
    "siliconflow",
    "together",
    "fireworks",
    "sambanova",
}

_SUBSCRIPTION_PROVIDERS = {
    "claude_code",
    "codex",
}

_CHEAP_PROVIDERS = {
    "google_ai",
    "mistral",
    "chutes",
}

_MODEL_RATE_OVERRIDES: dict[tuple[str, str], float] = {
    ("openrouter", "moonshotai/kimi-k2.5"): 0.60,
    ("openrouter", "moonshotai/kimi-k2.5-"): 0.60,
    ("openrouter", "mistralai/mistral-small"): 0.10,
    ("openrouter", "meta-llama/llama-3.3-70b"): 0.50,
    ("anthropic", "claude-opus-4"): 15.00,
    ("anthropic", "claude-sonnet-4"): 3.00,
    ("openai", "gpt-5"): 10.00,
    ("openai", "gpt-4.1"): 2.00,
    ("openai", "gpt-4o"): 2.50,
}

_PROVIDER_DEFAULT_RATES: dict[str, float] = {
    "anthropic": 4.00,
    "openai": 3.00,
    "openrouter": 0.75,
    "google_ai": 0.30,
    "mistral": 0.20,
    "chutes": 0.20,
}


def _lane_for_provider(provider: str) -> str:
    provider_lower = (provider or "").strip().lower()
    if provider_lower in _FREE_PROVIDERS:
        return "free"
    if provider_lower in _SUBSCRIPTION_PROVIDERS:
        return "subscription"
    if provider_lower in _CHEAP_PROVIDERS:
        return "cheap"
    return "paid"


def _rate_for_provider_model(provider: str, model: str) -> float:
    provider_lower = (provider or "").strip().lower()
    model_lower = (model or "").strip().lower()
    if provider_lower in _FREE_PROVIDERS or model_lower.endswith(":free"):
        return 0.0
    if provider_lower in _SUBSCRIPTION_PROVIDERS:
        return 0.0
    for (provider_key, model_prefix), rate in _MODEL_RATE_OVERRIDES.items():
        if provider_lower == provider_key and model_lower.startswith(model_prefix):
            return rate
    return _PROVIDER_DEFAULT_RATES.get(provider_lower, 0.0)


def _estimate_cost(
    model: str,
    input_tokens: int,
    output_tokens: int,
    *,
    provider: str = "",
) -> float:
    """Estimate USD cost based on provider/model and token counts."""
    rate = _rate_for_provider_model(provider, model)
    # Output tokens typically cost 3-5x input; use 3x as conservative estimate.
    input_cost = (input_tokens / 1_000_000) * rate
    output_cost = (output_tokens / 1_000_000) * rate * 3.0
    return round(input_cost + output_cost, 6)


@dataclass
class CostEntry:
    timestamp: float
    provider: str
    model: str
    input_tokens: int
    output_tokens: int
    estimated_cost_usd: float
    lane: str = ""
    execution_mode: str = ""
    source: str = ""
    agent_id: str = ""
    task_id: str = ""
    agent_name: str = ""
    agent_role: str = ""
    task_title: str = ""
    tier: str = ""


def log_cost(
    *,
    provider: str,
    model: str,
    input_tokens: int,
    output_tokens: int,
    task_id: str = "",
    agent_name: str = "",
    agent_id: str = "",
    agent_role: str = "",
    execution_mode: str = "",
    source: str = "",
    task_title: str = "",
    tier: str = "",
) -> CostEntry:
    """Log a cost entry to the JSONL file."""
    entry = CostEntry(
        timestamp=time.time(),
        provider=provider,
        model=model,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        estimated_cost_usd=_estimate_cost(
            model,
            input_tokens,
            output_tokens,
            provider=provider,
        ),
        lane=_lane_for_provider(provider),
        execution_mode=execution_mode,
        source=source,
        agent_id=agent_id,
        task_id=task_id,
        agent_name=agent_name,
        agent_role=agent_role,
        task_title=task_title,
        tier=tier,
    )
    try:
        _COST_LOG.parent.mkdir(parents=True, exist_ok=True)
        with open(_COST_LOG, "a") as f:
            f.write(json.dumps(asdict(entry)) + "\n")
    except Exception as exc:
        logger.warning("Failed to log cost entry: %s", exc)
    return entry


def read_cost_log(since_hours: float = 24.0) -> list[CostEntry]:
    """Read cost entries from the last N hours."""
    if not _COST_LOG.exists():
        return []
    cutoff = time.time() - (since_hours * 3600)
    entries = []
    try:
        with open(_COST_LOG) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    if data.get("timestamp", 0) >= cutoff:
                        provider = str(data.get("provider", "") or "")
                        model = str(data.get("model", "") or "")
                        input_tokens = int(data.get("input_tokens", 0) or 0)
                        output_tokens = int(data.get("output_tokens", 0) or 0)
                        lane = str(data.get("lane", "") or _lane_for_provider(provider))
                        estimated_cost_usd = data.get("estimated_cost_usd")
                        if estimated_cost_usd in (None, "") or (
                            float(estimated_cost_usd or 0.0) == 0.0
                            and lane == "paid"
                        ):
                            estimated_cost_usd = _estimate_cost(
                                model,
                                input_tokens,
                                output_tokens,
                                provider=provider,
                            )
                        data["provider"] = provider
                        data["model"] = model
                        data["input_tokens"] = input_tokens
                        data["output_tokens"] = output_tokens
                        data["lane"] = lane
                        data["estimated_cost_usd"] = float(estimated_cost_usd or 0.0)
                        entries.append(CostEntry(**data))
                except (json.JSONDecodeError, TypeError):
                    continue
    except Exception as exc:
        logger.warning("Failed to read cost log: %s", exc)
    return entries


def cost_summary(since_hours: float = 24.0) -> str:
    """Return a human-readable cost summary."""
    entries = read_cost_log(since_hours=since_hours)
    if not entries:
        return f"No LLM calls in the last {since_hours:.0f}h."

    total_cost = sum(e.estimated_cost_usd for e in entries)
    total_input = sum(e.input_tokens for e in entries)
    total_output = sum(e.output_tokens for e in entries)

    # By tier
    by_tier: dict[str, list[CostEntry]] = {}
    for e in entries:
        tier = e.tier or "unknown"
        by_tier.setdefault(tier, []).append(e)

    lines = [
        f"Cost summary (last {since_hours:.0f}h): {len(entries)} calls, ${total_cost:.4f}",
        f"  Tokens: {total_input:,} in / {total_output:,} out",
        "",
        "  By tier:",
    ]
    for tier in sorted(by_tier.keys()):
        tier_entries = by_tier[tier]
        tier_cost = sum(e.estimated_cost_usd for e in tier_entries)
        pct = (len(tier_entries) / len(entries) * 100) if entries else 0
        lines.append(f"    {tier}: {len(tier_entries)} calls ({pct:.0f}%), ${tier_cost:.4f}")

    return "\n".join(lines)


def summarize_costs(since_hours: float) -> dict[str, Any]:
    """Return structured cost rollup for health/dashboards."""
    entries = read_cost_log(since_hours=since_hours)
    total_cost = round(sum(e.estimated_cost_usd for e in entries), 6)
    total_input = sum(e.input_tokens for e in entries)
    total_output = sum(e.output_tokens for e in entries)
    by_provider: dict[str, dict[str, Any]] = {}
    by_lane: dict[str, dict[str, Any]] = {}
    by_model: dict[str, dict[str, Any]] = {}
    by_execution_mode: dict[str, dict[str, Any]] = {}
    by_source: dict[str, dict[str, Any]] = {}
    by_agent: dict[str, dict[str, Any]] = {}
    for entry in entries:
        provider_bucket = by_provider.setdefault(
            entry.provider or "unknown",
            {"calls": 0, "cost_usd": 0.0, "input_tokens": 0, "output_tokens": 0},
        )
        provider_bucket["calls"] += 1
        provider_bucket["cost_usd"] = round(
            provider_bucket["cost_usd"] + entry.estimated_cost_usd,
            6,
        )
        provider_bucket["input_tokens"] += entry.input_tokens
        provider_bucket["output_tokens"] += entry.output_tokens

        lane_bucket = by_lane.setdefault(
            entry.lane or "unknown",
            {"calls": 0, "cost_usd": 0.0, "input_tokens": 0, "output_tokens": 0},
        )
        lane_bucket["calls"] += 1
        lane_bucket["cost_usd"] = round(
            lane_bucket["cost_usd"] + entry.estimated_cost_usd,
            6,
        )
        lane_bucket["input_tokens"] += entry.input_tokens
        lane_bucket["output_tokens"] += entry.output_tokens

        model_bucket = by_model.setdefault(
            entry.model or "unknown",
            {
                "provider": entry.provider or "unknown",
                "lane": entry.lane or "unknown",
                "calls": 0,
                "cost_usd": 0.0,
                "input_tokens": 0,
                "output_tokens": 0,
            },
        )
        model_bucket["calls"] += 1
        model_bucket["cost_usd"] = round(
            model_bucket["cost_usd"] + entry.estimated_cost_usd,
            6,
        )
        model_bucket["input_tokens"] += entry.input_tokens
        model_bucket["output_tokens"] += entry.output_tokens

        execution_bucket = by_execution_mode.setdefault(
            entry.execution_mode or "unknown",
            {"calls": 0, "cost_usd": 0.0, "input_tokens": 0, "output_tokens": 0},
        )
        execution_bucket["calls"] += 1
        execution_bucket["cost_usd"] = round(
            execution_bucket["cost_usd"] + entry.estimated_cost_usd,
            6,
        )
        execution_bucket["input_tokens"] += entry.input_tokens
        execution_bucket["output_tokens"] += entry.output_tokens

        source_bucket = by_source.setdefault(
            entry.source or "unknown",
            {"calls": 0, "cost_usd": 0.0, "input_tokens": 0, "output_tokens": 0},
        )
        source_bucket["calls"] += 1
        source_bucket["cost_usd"] = round(
            source_bucket["cost_usd"] + entry.estimated_cost_usd,
            6,
        )
        source_bucket["input_tokens"] += entry.input_tokens
        source_bucket["output_tokens"] += entry.output_tokens

        agent_bucket = by_agent.setdefault(
            entry.agent_name or entry.agent_id or "anonymous",
            {
                "agent_id": entry.agent_id,
                "agent_name": entry.agent_name,
                "agent_role": entry.agent_role,
                "execution_mode": entry.execution_mode or "unknown",
                "calls": 0,
                "cost_usd": 0.0,
                "input_tokens": 0,
                "output_tokens": 0,
            },
        )
        agent_bucket["calls"] += 1
        agent_bucket["cost_usd"] = round(
            agent_bucket["cost_usd"] + entry.estimated_cost_usd,
            6,
        )
        agent_bucket["input_tokens"] += entry.input_tokens
        agent_bucket["output_tokens"] += entry.output_tokens

    recent = [asdict(e) for e in entries[-10:]]
    top_agents = sorted(
        by_agent.values(),
        key=lambda item: (
            -int(item["calls"]),
            -float(item["cost_usd"]),
            -int(item["output_tokens"]),
        ),
    )[:10]
    return {
        "window_hours": since_hours,
        "calls": len(entries),
        "total_cost_usd": total_cost,
        "input_tokens": total_input,
        "output_tokens": total_output,
        "by_provider": by_provider,
        "by_lane": by_lane,
        "by_model": dict(
            sorted(
                by_model.items(),
                key=lambda item: (
                    -item[1]["calls"],
                    -item[1]["cost_usd"],
                ),
            )
        ),
        "by_execution_mode": by_execution_mode,
        "by_source": by_source,
        "top_agents": top_agents,
        "recent": recent,
    }


__all__ = [
    "CostEntry",
    "cost_summary",
    "log_cost",
    "read_cost_log",
    "summarize_costs",
]
