"""Runtime diversity governor for model and work-mix balance.

Applies lightweight, read-only policy pressure from recent daemon activity:
- demote provider monoculture when one lane dominates the recent window
- demote inward-only background tasks when internal work already dominates

This is intentionally small. It does not replace routing policy or task
selection. It overlays pressure when recent behavior is obviously imbalanced.
"""

from __future__ import annotations

from dataclasses import dataclass
import os
from typing import Any, Iterable

from dharma_swarm.cost_tracker import summarize_costs
from dharma_swarm.models import ProviderType, Task


def _env_float(name: str, default: float) -> float:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        return float(raw)
    except Exception:
        return default


def _safe_ratio(numerator: float, denominator: float) -> float:
    if denominator <= 0:
        return 0.0
    return numerator / denominator


@dataclass(frozen=True, slots=True)
class DiversitySnapshot:
    window_hours: float
    total_calls: int
    top_model: str
    top_model_share: float
    top_provider: str
    top_provider_share: float
    inward_share: float
    unknown_share: float
    active_sources: tuple[str, ...]

    @property
    def model_monoculture(self) -> bool:
        return self.top_model_share >= _env_float("DGC_DIVERSITY_MAX_MODEL_SHARE", 0.55)

    @property
    def inward_heavy(self) -> bool:
        return self.inward_share >= _env_float("DGC_DIVERSITY_MAX_INWARD_SHARE", 0.5)


class DiversityGovernor:
    """Compute simple runtime diversity pressure from recent activity."""

    _INWARD_SOURCES = {
        "sleep_time_agent",
        "swarm.coordination_synthesis",
        "pulse",
        "consolidation",
        "context_agent",
        "unknown",
    }

    _INTERNAL_TASK_MARKERS = (
        "knowledge extraction",
        "synthesize disagreement",
        "coordination",
        "archive",
        "consolidation",
        "latent gold",
        "pulse:",
        "context distillation",
    )

    _OUTWARD_TASK_MARKERS = (
        "publish",
        "artifact",
        "report",
        "website",
        "github",
        "commit",
        "benchmark",
        "paper",
        "proposal",
        "deploy",
        "ship",
    )

    def __init__(self, *, window_hours: float = 1.0) -> None:
        self.window_hours = window_hours

    def snapshot(self) -> DiversitySnapshot:
        rollup = summarize_costs(self.window_hours)
        total_calls = int(rollup.get("calls", 0) or 0)
        by_model = rollup.get("by_model", {}) or {}
        by_provider = rollup.get("by_provider", {}) or {}
        by_source = rollup.get("by_source", {}) or {}

        top_model = ""
        top_model_calls = 0
        for model, stats in by_model.items():
            calls = int((stats or {}).get("calls", 0) or 0)
            if calls > top_model_calls:
                top_model = str(model)
                top_model_calls = calls

        top_provider = ""
        top_provider_calls = 0
        for provider, stats in by_provider.items():
            calls = int((stats or {}).get("calls", 0) or 0)
            if calls > top_provider_calls:
                top_provider = str(provider)
                top_provider_calls = calls

        inward_calls = 0
        unknown_calls = 0
        active_sources: list[str] = []
        for source, stats in by_source.items():
            calls = int((stats or {}).get("calls", 0) or 0)
            if calls <= 0:
                continue
            source_name = str(source)
            active_sources.append(source_name)
            if source_name in self._INWARD_SOURCES:
                inward_calls += calls
            if source_name == "unknown":
                unknown_calls += calls

        return DiversitySnapshot(
            window_hours=self.window_hours,
            total_calls=total_calls,
            top_model=top_model,
            top_model_share=round(_safe_ratio(top_model_calls, total_calls), 6),
            top_provider=top_provider,
            top_provider_share=round(_safe_ratio(top_provider_calls, total_calls), 6),
            inward_share=round(_safe_ratio(inward_calls, total_calls), 6),
            unknown_share=round(_safe_ratio(unknown_calls, total_calls), 6),
            active_sources=tuple(active_sources),
        )

    def reorder_providers(
        self,
        candidates: Iterable[ProviderType],
        *,
        default_model_hints: dict[ProviderType, str] | None = None,
    ) -> tuple[list[ProviderType], list[str]]:
        ordered = list(candidates)
        if not ordered:
            return (ordered, [])

        snapshot = self.snapshot()
        reasons: list[str] = []
        if snapshot.total_calls <= 0:
            return (ordered, reasons)

        hints = default_model_hints or {}

        if snapshot.model_monoculture and snapshot.top_provider == ProviderType.OLLAMA.value:
            ollama = [p for p in ordered if p == ProviderType.OLLAMA]
            alternatives = [p for p in ordered if p != ProviderType.OLLAMA]
            if ollama and alternatives:
                ordered = alternatives + ollama
                reasons.append(f"diversity_demote_provider:{ProviderType.OLLAMA.value}")
                reasons.append(f"diversity_top_model:{snapshot.top_model}:{snapshot.top_model_share:.3f}")

        if snapshot.inward_heavy:
            preferred: list[ProviderType] = []
            rest: list[ProviderType] = []
            for provider in ordered:
                hint = str(hints.get(provider, "") or "").lower()
                if "minimax" in hint or "kimi" in hint or provider in {ProviderType.OPENROUTER, ProviderType.NVIDIA_NIM}:
                    preferred.append(provider)
                else:
                    rest.append(provider)
            if preferred:
                ordered = preferred + [p for p in rest if p not in preferred]
                reasons.append(f"diversity_inward_heavy:{snapshot.inward_share:.3f}")
                reasons.append("diversity_promote_challenger_lanes")

        deduped: list[ProviderType] = []
        seen: set[ProviderType] = set()
        for provider in ordered:
            if provider in seen:
                continue
            seen.add(provider)
            deduped.append(provider)
        return (deduped, reasons)

    def reorder_ready_tasks(self, tasks: Iterable[Task]) -> tuple[list[Task], list[str]]:
        ordered = list(tasks)
        snapshot = self.snapshot()
        if not ordered or not snapshot.inward_heavy:
            return (ordered, [])

        outward: list[Task] = []
        neutral: list[Task] = []
        inward: list[Task] = []
        for task in ordered:
            bucket = self._task_bucket(task)
            if bucket == "outward":
                outward.append(task)
            elif bucket == "inward":
                inward.append(task)
            else:
                neutral.append(task)

        reordered = outward + neutral + inward
        if reordered == ordered:
            return (ordered, [])
        return (
            reordered,
            [
                f"diversity_inward_heavy:{snapshot.inward_share:.3f}",
                "diversity_demote_internal_tasks",
            ],
        )

    def _task_bucket(self, task: Task) -> str:
        meta = task.metadata if isinstance(task.metadata, dict) else {}
        title = str(getattr(task, "title", "") or "")
        description = str(getattr(task, "description", "") or "")
        haystack = f"{title}\n{description}".lower()
        source = str(meta.get("source", "") or "").lower()
        task_title = str(meta.get("task_title", "") or "").lower()
        artifact_contract = bool(meta.get("artifact_contract") or meta.get("world_facing") or meta.get("publish"))

        if artifact_contract or any(marker in haystack for marker in self._OUTWARD_TASK_MARKERS):
            return "outward"
        if (
            source in self._INWARD_SOURCES
            or any(marker in haystack for marker in self._INTERNAL_TASK_MARKERS)
            or any(marker in task_title for marker in self._INTERNAL_TASK_MARKERS)
        ):
            return "inward"
        return "neutral"


__all__ = ["DiversityGovernor", "DiversitySnapshot"]
