"""Shared data models for the LangGraph parity benchmark."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Literal


BenchmarkMode = Literal["single_agent", "swarm", "supervisor"]
BENCHMARK_MODES: tuple[BenchmarkMode, ...] = (
    "single_agent",
    "swarm",
    "supervisor",
)
BENCHMARK_AGENT_ID = "langgraph_parity_benchmark"
BENCHMARK_OPERATION = "langgraph_parity.benchmark"
REQUIRED_CASE_TAGS: tuple[str, ...] = (
    "fan_out",
    "fan_in",
    "pipeline",
    "broadcast",
    "swarm",
    "supervisor",
    "subagents_as_tools",
    "retry",
    "timeout",
    "cancellation",
    "checkpoint_reload",
    "interrupt_resume",
    "provider_fallback",
    "memory_isolation",
    "a2a_blocker_semantics",
    "command_send_routing",
)


@dataclass(frozen=True, slots=True)
class ProviderProfile:
    """Provider/model metadata for benchmark accounting."""

    provider: str = "local"
    model: str = "deterministic-isolation-harness-v1"
    cost_per_1k_tokens: float = 0.0002

    def to_dict(self) -> dict[str, object]:
        return {
            "provider": self.provider,
            "model": self.model,
            "cost_per_1k_tokens": self.cost_per_1k_tokens,
        }


@dataclass(frozen=True, slots=True)
class BenchmarkTask:
    """One deterministic task in the distractor benchmark suite."""

    id: str
    prompt: str
    required_domains: tuple[str, ...]
    expected_tools: Mapping[str, tuple[str, ...]] = field(default_factory=dict)
    case_tags: tuple[str, ...] = field(default_factory=tuple)

    @property
    def requires_multi_hop(self) -> bool:
        return len(self.required_domains) > 1

    def to_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "prompt": self.prompt,
            "required_domains": list(self.required_domains),
            "expected_tools": {
                domain: list(tools) for domain, tools in self.expected_tools.items()
            },
            "case_tags": list(self.case_tags),
            "requires_multi_hop": self.requires_multi_hop,
        }


@dataclass(frozen=True, slots=True)
class BenchmarkResult:
    """One mode's deterministic result for one benchmark task."""

    task_id: str
    mode: BenchmarkMode
    score: float
    token_estimate: int
    cost_estimate_usd: float
    latency_ms: int
    handoff_count: int
    provider: str
    model: str
    failure_classes: tuple[str, ...]
    agents: tuple[str, ...]
    selected_domains: tuple[str, ...]
    visible_tools_by_agent: Mapping[str, tuple[str, ...]]
    admitted_memory_domains_by_agent: Mapping[str, tuple[str, ...]]

    def to_dict(self) -> dict[str, object]:
        return {
            "task_id": self.task_id,
            "mode": self.mode,
            "score": self.score,
            "token_estimate": self.token_estimate,
            "cost_estimate_usd": self.cost_estimate_usd,
            "latency_ms": self.latency_ms,
            "handoff_count": self.handoff_count,
            "provider": self.provider,
            "model": self.model,
            "failure_classes": list(self.failure_classes),
            "agents": list(self.agents),
            "selected_domains": list(self.selected_domains),
            "visible_tools_by_agent": {
                agent: list(tools)
                for agent, tools in self.visible_tools_by_agent.items()
            },
            "admitted_memory_domains_by_agent": {
                agent: list(domains)
                for agent, domains in self.admitted_memory_domains_by_agent.items()
            },
        }


@dataclass(frozen=True, slots=True)
class BenchmarkReport:
    """Serializable benchmark report."""

    suite_name: str
    provider_profile: ProviderProfile
    tasks: tuple[BenchmarkTask, ...]
    results: tuple[BenchmarkResult, ...]
    distractor_domain_count: int
    mission_id: str = ""

    @property
    def summary(self) -> dict[str, object]:
        by_mode: dict[str, dict[str, object]] = {}
        for mode in BENCHMARK_MODES:
            mode_results = [result for result in self.results if result.mode == mode]
            total = len(mode_results)
            score = (
                round(sum(result.score for result in mode_results) / total, 3)
                if total
                else 0.0
            )
            tokens = sum(result.token_estimate for result in mode_results)
            cost = round(sum(result.cost_estimate_usd for result in mode_results), 6)
            failures = sorted(
                {
                    failure
                    for result in mode_results
                    for failure in result.failure_classes
                }
            )
            by_mode[mode] = {
                "task_count": total,
                "average_score": score,
                "token_estimate": tokens,
                "cost_estimate_usd": cost,
                "failure_classes": failures,
            }
        case_tag_coverage = {
            tag: sum(tag in task.case_tags for task in self.tasks)
            for tag in REQUIRED_CASE_TAGS
        }

        return {
            "suite_name": self.suite_name,
            "task_count": len(self.tasks),
            "multi_hop_task_count": sum(task.requires_multi_hop for task in self.tasks),
            "distractor_domain_count": self.distractor_domain_count,
            "required_case_tags": list(REQUIRED_CASE_TAGS),
            "case_tag_coverage": case_tag_coverage,
            "case_tags_complete": all(
                count > 0 for count in case_tag_coverage.values()
            ),
            "modes": by_mode,
        }

    def to_dict(self) -> dict[str, object]:
        return {
            "suite_name": self.suite_name,
            "deterministic": True,
            "mission_id": self.mission_id,
            "provider_profile": self.provider_profile.to_dict(),
            "distractor_domain_count": self.distractor_domain_count,
            "tasks": [task.to_dict() for task in self.tasks],
            "summary": self.summary,
            "results": [result.to_dict() for result in self.results],
        }
