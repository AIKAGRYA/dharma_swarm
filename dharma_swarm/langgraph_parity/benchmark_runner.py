"""Deterministic benchmark execution for LangGraph parity."""

from __future__ import annotations

import re
from collections.abc import Sequence

from dharma_swarm.langgraph_parity.benchmark_types import (
    BENCHMARK_MODES,
    BenchmarkMode,
    BenchmarkReport,
    BenchmarkResult,
    BenchmarkTask,
    ProviderProfile,
)
from dharma_swarm.langgraph_parity.benchmark_tasks import default_benchmark_tasks
from dharma_swarm.langgraph_parity.isolation import (
    AgentIsolationView,
    IsolationPolicy,
    SimulatedMemoryKernel,
    SimulatedSemanticCommons,
    collect_isolation_failures,
    default_distractor_packs,
    default_isolation_policy,
    default_memory_kernel,
    default_semantic_commons,
)


def run_benchmark(
    tasks: Sequence[BenchmarkTask] | None = None,
    *,
    policy: IsolationPolicy | None = None,
    semantic_commons: SimulatedSemanticCommons | None = None,
    memory_kernel: SimulatedMemoryKernel | None = None,
    provider_profile: ProviderProfile | None = None,
    mission_id: str = "",
) -> BenchmarkReport:
    """Run the deterministic local benchmark across all comparison modes."""

    selected_tasks = tuple(tasks or default_benchmark_tasks())
    selected_policy = policy or default_isolation_policy()
    commons = semantic_commons or default_semantic_commons()
    memory = memory_kernel or default_memory_kernel()
    provider = provider_profile or ProviderProfile()

    results: list[BenchmarkResult] = []
    for task in selected_tasks:
        for mode in BENCHMARK_MODES:
            results.append(
                _run_task_mode(
                    task,
                    mode=mode,
                    policy=selected_policy,
                    semantic_commons=commons,
                    memory_kernel=memory,
                    provider_profile=provider,
                )
            )

    return BenchmarkReport(
        suite_name="langgraph_parity_isolation_distractors",
        provider_profile=provider,
        tasks=selected_tasks,
        results=tuple(results),
        distractor_domain_count=len(default_distractor_packs()),
        mission_id=mission_id,
    )


def format_markdown_report(report: BenchmarkReport) -> str:
    lines = [
        "# LangGraph Parity Isolation Benchmark",
        "",
        f"Suite: `{report.suite_name}`",
        f"Provider/model: `{report.provider_profile.provider}` / `{report.provider_profile.model}`",
        f"Distractor domains: {report.distractor_domain_count}",
        f"Tasks: {len(report.tasks)}",
        "",
        "## Summary",
        "",
        "| Mode | Avg score | Tokens | Cost USD | Failure classes |",
        "| --- | ---: | ---: | ---: | --- |",
    ]
    mode_summary = report.summary["modes"]
    assert isinstance(mode_summary, dict)
    for mode in BENCHMARK_MODES:
        row = mode_summary[mode]
        failures = ", ".join(row["failure_classes"]) or "none"
        lines.append(
            "| {mode} | {score:.3f} | {tokens} | {cost:.6f} | {failures} |".format(
                mode=mode,
                score=row["average_score"],
                tokens=row["token_estimate"],
                cost=row["cost_estimate_usd"],
                failures=failures,
            )
        )

    lines.extend(
        [
            "",
            "## Results",
            "",
            "| Task | Mode | Score | Tokens | Cost USD | Latency ms | Handoffs | Agents | Failures |",
            "| --- | --- | ---: | ---: | ---: | ---: | ---: | --- | --- |",
        ]
    )
    for result in report.results:
        failures = ", ".join(result.failure_classes) or "none"
        agents = ", ".join(result.agents) or "none"
        lines.append(
            "| {task} | {mode} | {score:.3f} | {tokens} | {cost:.6f} | "
            "{latency} | {handoffs} | {agents} | {failures} |".format(
                task=result.task_id,
                mode=result.mode,
                score=result.score,
                tokens=result.token_estimate,
                cost=result.cost_estimate_usd,
                latency=result.latency_ms,
                handoffs=result.handoff_count,
                agents=agents,
                failures=failures,
            )
        )
    lines.append("")
    return "\n".join(lines)


def _run_task_mode(
    task: BenchmarkTask,
    *,
    mode: BenchmarkMode,
    policy: IsolationPolicy,
    semantic_commons: SimulatedSemanticCommons,
    memory_kernel: SimulatedMemoryKernel,
    provider_profile: ProviderProfile,
) -> BenchmarkResult:
    if mode == "single_agent":
        return _run_single_agent(
            task,
            policy=policy,
            semantic_commons=semantic_commons,
            memory_kernel=memory_kernel,
            provider_profile=provider_profile,
        )
    if mode == "swarm":
        return _run_swarm(
            task,
            policy=policy,
            semantic_commons=semantic_commons,
            memory_kernel=memory_kernel,
            provider_profile=provider_profile,
        )
    return _run_supervisor(
        task,
        policy=policy,
        semantic_commons=semantic_commons,
        memory_kernel=memory_kernel,
        provider_profile=provider_profile,
    )


def _run_single_agent(
    task: BenchmarkTask,
    *,
    policy: IsolationPolicy,
    semantic_commons: SimulatedSemanticCommons,
    memory_kernel: SimulatedMemoryKernel,
    provider_profile: ProviderProfile,
) -> BenchmarkResult:
    first_domain = task.required_domains[0]
    first_agent = policy.agent_for_domain(first_domain)
    view = _prepare_view(
        policy,
        first_agent,
        first_domain,
        task.prompt,
        semantic_commons,
        memory_kernel,
    )
    return _build_result(
        task,
        mode="single_agent",
        views=(view,),
        covered_domains=(first_domain,),
        handoff_count=0,
        provider_profile=provider_profile,
    )


def _run_swarm(
    task: BenchmarkTask,
    *,
    policy: IsolationPolicy,
    semantic_commons: SimulatedSemanticCommons,
    memory_kernel: SimulatedMemoryKernel,
    provider_profile: ProviderProfile,
) -> BenchmarkResult:
    views: list[AgentIsolationView] = []
    covered_domains: list[str] = []
    failures: list[str] = []

    for index, domain in enumerate(task.required_domains):
        agent_name = policy.agent_for_domain(domain)
        if index:
            previous_agent = views[-1].agent_name
            if agent_name not in policy.allowed_targets(previous_agent):
                failures.append("handoff_not_allowed")
                break
        views.append(
            _prepare_view(
                policy,
                agent_name,
                domain,
                task.prompt,
                semantic_commons,
                memory_kernel,
            )
        )
        covered_domains.append(domain)

    return _build_result(
        task,
        mode="swarm",
        views=tuple(views),
        covered_domains=tuple(covered_domains),
        handoff_count=max(0, len(views) - 1),
        provider_profile=provider_profile,
        extra_failures=tuple(failures),
    )


def _run_supervisor(
    task: BenchmarkTask,
    *,
    policy: IsolationPolicy,
    semantic_commons: SimulatedSemanticCommons,
    memory_kernel: SimulatedMemoryKernel,
    provider_profile: ProviderProfile,
) -> BenchmarkResult:
    views = tuple(
        _prepare_view(
            policy,
            policy.agent_for_domain(domain),
            domain,
            task.prompt,
            semantic_commons,
            memory_kernel,
        )
        for domain in task.required_domains
    )
    return _build_result(
        task,
        mode="supervisor",
        views=views,
        covered_domains=task.required_domains,
        handoff_count=len(views),
        provider_profile=provider_profile,
    )


def _prepare_view(
    policy: IsolationPolicy,
    agent_name: str,
    selected_domain: str,
    prompt: str,
    semantic_commons: SimulatedSemanticCommons,
    memory_kernel: SimulatedMemoryKernel,
) -> AgentIsolationView:
    return policy.prepare_agent_view(
        agent_name=agent_name,
        prompt=prompt,
        selected_domains=(selected_domain,),
        semantic_commons=semantic_commons,
        memory_kernel=memory_kernel,
    )


def _build_result(
    task: BenchmarkTask,
    *,
    mode: BenchmarkMode,
    views: tuple[AgentIsolationView, ...],
    covered_domains: tuple[str, ...],
    handoff_count: int,
    provider_profile: ProviderProfile,
    extra_failures: tuple[str, ...] = (),
) -> BenchmarkResult:
    failures: list[str] = list(extra_failures)
    covered_set = set(covered_domains)
    required_set = set(task.required_domains)
    if required_set - covered_set:
        failures.append("missing_required_domain")

    view_by_domain = {view.domain: view for view in views}
    for domain in covered_domains:
        expected_tools = task.expected_tools.get(domain, ())
        visible_tools = set(view_by_domain[domain].tool_names)
        if any(tool not in visible_tools for tool in expected_tools):
            failures.append("missing_required_tool")
            break

    for view in views:
        failures.extend(collect_isolation_failures(view))

    failure_classes = _ordered_unique(failures)
    token_estimate = _estimate_tokens(task.prompt, views, mode, handoff_count)
    return BenchmarkResult(
        task_id=task.id,
        mode=mode,
        score=_score(
            required_domains=task.required_domains,
            covered_domains=covered_domains,
            failure_classes=failure_classes,
        ),
        token_estimate=token_estimate,
        cost_estimate_usd=round(
            (token_estimate / 1000.0) * provider_profile.cost_per_1k_tokens,
            6,
        ),
        latency_ms=_estimate_latency_ms(mode, token_estimate, len(views), handoff_count),
        handoff_count=handoff_count,
        provider=provider_profile.provider,
        model=provider_profile.model,
        failure_classes=failure_classes,
        agents=tuple(view.agent_name for view in views),
        selected_domains=task.required_domains,
        visible_tools_by_agent={view.agent_name: view.tool_names for view in views},
        admitted_memory_domains_by_agent={
            view.agent_name: tuple(fact.domain for fact in view.memory_facts)
            for view in views
        },
    )


def _score(
    *,
    required_domains: tuple[str, ...],
    covered_domains: tuple[str, ...],
    failure_classes: tuple[str, ...],
) -> float:
    coverage = len(set(covered_domains) & set(required_domains)) / len(required_domains)
    penalty = 0.0
    if "missing_required_tool" in failure_classes:
        penalty += 0.2
    if "handoff_not_allowed" in failure_classes:
        penalty += 0.4
    if "isolation_leak" in failure_classes:
        penalty += 1.0
    return round(max(0.0, min(1.0, coverage - penalty)), 3)


def _estimate_tokens(
    prompt: str,
    views: tuple[AgentIsolationView, ...],
    mode: BenchmarkMode,
    handoff_count: int,
) -> int:
    chunks: list[str] = [prompt]
    for view in views:
        chunks.extend(view.instructions)
        chunks.extend(f"{tool.name} {tool.description}" for tool in view.tools)
        chunks.extend(fact.content for fact in view.memory_facts)
    mode_overhead = {"single_agent": 8, "swarm": 18, "supervisor": 32}[mode]
    return sum(_rough_token_count(chunk) for chunk in chunks) + mode_overhead + handoff_count * 6


def _estimate_latency_ms(
    mode: BenchmarkMode,
    token_estimate: int,
    agent_count: int,
    handoff_count: int,
) -> int:
    mode_base = {"single_agent": 10, "swarm": 16, "supervisor": 24}[mode]
    return mode_base + agent_count * 7 + handoff_count * 4 + token_estimate // 35


def _rough_token_count(text: str) -> int:
    return len(re.findall(r"\w+|[^\w\s]", text))


def _ordered_unique(values: Sequence[str]) -> tuple[str, ...]:
    seen: set[str] = set()
    unique: list[str] = []
    for value in values:
        if value not in seen:
            seen.add(value)
            unique.append(value)
    return tuple(unique)
