"""Deterministic distractor benchmark for LangGraph parity isolation."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal
from uuid import uuid4

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
from dharma_swarm.runtime_state import (
    ArtifactRecord,
    DelegationRun,
    RuntimeReceipt,
    RuntimeStateStore,
    TaskClaim,
)
from dharma_swarm.spine.identity import ExecutionIdentity
from dharma_swarm.spine.receipt import EvidenceReceipt


BenchmarkMode = Literal["single_agent", "swarm", "supervisor"]
BENCHMARK_MODES: tuple[BenchmarkMode, ...] = (
    "single_agent",
    "swarm",
    "supervisor",
)
BENCHMARK_AGENT_ID = "langgraph_parity_benchmark"
BENCHMARK_OPERATION = "langgraph_parity.benchmark"


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

        return {
            "suite_name": self.suite_name,
            "task_count": len(self.tasks),
            "multi_hop_task_count": sum(task.requires_multi_hop for task in self.tasks),
            "distractor_domain_count": self.distractor_domain_count,
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


def default_benchmark_tasks() -> tuple[BenchmarkTask, ...]:
    """Return a stable suite with distractors and one two-agent multi-hop task."""

    return (
        BenchmarkTask(
            id="climate_finance_multihop",
            prompt=(
                "Estimate welfare-ton upside for a mangrove restoration pilot, "
                "then convert that into a risk-bounded deployment cash budget."
            ),
            required_domains=("climate_ops", "finance_risk"),
            expected_tools={
                "climate_ops": (
                    "carbon_project_lookup",
                    "welfare_ton_calculator",
                ),
                "finance_risk": (
                    "risk_budget_calculator",
                    "cashflow_projection",
                ),
            },
        ),
        BenchmarkTask(
            id="security_patch_review",
            prompt=(
                "Review a dependency patch for CVE exposure and static-analysis "
                "regression risk."
            ),
            required_domains=("code_security",),
            expected_tools={
                "code_security": (
                    "dependency_cve_lookup",
                    "patch_diff_reader",
                )
            },
        ),
        BenchmarkTask(
            id="contract_policy_check",
            prompt=(
                "Check a cancellation clause against jurisdiction and compliance "
                "policy constraints."
            ),
            required_domains=("legal_policy",),
            expected_tools={
                "legal_policy": (
                    "contract_clause_search",
                    "jurisdiction_check",
                )
            },
        ),
        BenchmarkTask(
            id="supply_eta_risk",
            prompt=(
                "Assess vendor lead time, customs delay risk, and inventory buffer "
                "for a fulfillment lane."
            ),
            required_domains=("supply_chain",),
            expected_tools={
                "supply_chain": (
                    "vendor_eta_lookup",
                    "inventory_buffer_model",
                )
            },
        ),
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


def write_report(report: BenchmarkReport, output_dir: str | Path) -> tuple[Path, Path]:
    """Write JSON and Markdown report artifacts."""

    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    json_path = destination / "benchmark_report.json"
    markdown_path = destination / "benchmark_report.md"
    report_payload = report.to_dict()
    json_path.write_text(
        json.dumps(report_payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    markdown_path.write_text(format_markdown_report(report), encoding="utf-8")
    receipt = build_benchmark_receipt(
        report,
        artifact_id=_stable_payload_hash(report_payload),
        artifact_path=json_path,
    )
    (destination / "benchmark_receipt.json").write_text(
        json.dumps(receipt.to_dict(), indent=2, sort_keys=True, default=str) + "\n",
        encoding="utf-8",
    )
    return json_path, markdown_path


def build_benchmark_receipt(
    report: BenchmarkReport,
    *,
    artifact_id: str,
    artifact_path: Path,
) -> EvidenceReceipt:
    """Build the runtime-style receipt for one benchmark report write."""

    trace_id = _benchmark_trace_id(report, artifact_id)
    side_effect_key = _benchmark_side_effect_key(artifact_id)
    idempotency_key = _benchmark_idempotency_key(report, artifact_id)
    metrics = _benchmark_runtime_metrics(report)
    return EvidenceReceipt(
        trace_id=trace_id,
        span_id=uuid4().hex[:16],
        context_id=trace_id,
        task_id=report.suite_name,
        agent_id=BENCHMARK_AGENT_ID,
        provider=report.provider_profile.provider,
        model=report.provider_profile.model,
        operation=BENCHMARK_OPERATION,
        provider_attempted=False,
        status="ok",
        error_source="none",
        started_at=datetime.now(timezone.utc),
        finished_at=datetime.now(timezone.utc),
        latency_ms=metrics["latency_ms"],
        input_tokens=metrics["input_tokens"],
        output_tokens=0,
        cost_usd=metrics["cost_estimate_usd"],
        attributes={
            "mission_id": report.mission_id,
            "side_effect_key": side_effect_key,
            "idempotency_key": idempotency_key,
            "artifact_id": artifact_id,
            "artifact_path": str(artifact_path),
            "task_count": len(report.tasks),
            "mode_count": len(BENCHMARK_MODES),
        },
    )


def record_benchmark_runtime_receipt(
    report: BenchmarkReport,
    *,
    artifact_id: str,
    artifact_path: Path,
    runtime_db_path: str | Path | None = None,
) -> RuntimeReceipt:
    """Record the benchmark run in the canonical runtime receipt store."""

    identity = _benchmark_execution_identity(report, artifact_id)
    side_effect_key = _benchmark_side_effect_key(artifact_id)
    payload = _benchmark_runtime_payload(
        report,
        artifact_id=artifact_id,
        artifact_path=artifact_path,
        side_effect_key=side_effect_key,
        idempotency_key=identity.idempotency_key,
    )
    receipt = RuntimeReceipt(
        receipt_id=_benchmark_runtime_receipt_id(report, artifact_id),
        receipt_type="delegation_run",
        status="completed",
        run_id=identity.run_id,
        task_id=identity.task_id,
        trace_id=identity.trace_id,
        correlation_id=identity.correlation_id,
        causation_id=identity.causation_id,
        parent_run_id=identity.parent_run_id,
        agent_id=identity.agent_id,
        idempotency_key=identity.idempotency_key,
        side_effect_key=side_effect_key,
        payload=payload,
    )
    store = RuntimeStateStore(runtime_db_path)
    store.record_execution_identity_sync(
        identity,
        source=BENCHMARK_OPERATION,
        metadata=payload,
    )
    _record_benchmark_lifecycle_state(
        store,
        identity=identity,
        report=report,
        artifact_id=artifact_id,
        artifact_path=artifact_path,
        metadata=payload,
    )
    existing_idempotency = store.get_idempotency_record_sync(
        identity.idempotency_key,
        side_effect_key,
    )
    inserted = False
    if existing_idempotency is None:
        inserted = store.try_begin_idempotent_side_effect_sync(
            identity,
            side_effect_key,
            metadata=payload,
        )
    recorded = store.record_runtime_receipt_sync(receipt)
    if inserted or (
        existing_idempotency is not None
        and not existing_idempotency.result_receipt_id
    ):
        store.complete_idempotent_side_effect_sync(
            identity,
            side_effect_key,
            status="completed",
            result_receipt_id=recorded.receipt_id,
            metadata={**payload, "idempotency_inserted": inserted},
        )
    return recorded


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

    result = _build_result(
        task,
        mode="swarm",
        views=tuple(views),
        covered_domains=tuple(covered_domains),
        handoff_count=max(0, len(views) - 1),
        provider_profile=provider_profile,
        extra_failures=tuple(failures),
    )
    return result


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
    missing_domains = required_set - covered_set
    if missing_domains:
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
    score = _score(
        required_domains=task.required_domains,
        covered_domains=covered_domains,
        failure_classes=failure_classes,
    )
    token_estimate = _estimate_tokens(task.prompt, views, mode, handoff_count)
    cost_estimate = round(
        (token_estimate / 1000.0) * provider_profile.cost_per_1k_tokens,
        6,
    )
    latency_ms = _estimate_latency_ms(mode, token_estimate, len(views), handoff_count)
    return BenchmarkResult(
        task_id=task.id,
        mode=mode,
        score=score,
        token_estimate=token_estimate,
        cost_estimate_usd=cost_estimate,
        latency_ms=latency_ms,
        handoff_count=handoff_count,
        provider=provider_profile.provider,
        model=provider_profile.model,
        failure_classes=failure_classes,
        agents=tuple(view.agent_name for view in views),
        selected_domains=task.required_domains,
        visible_tools_by_agent={
            view.agent_name: view.tool_names for view in views
        },
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
    token_count = sum(_rough_token_count(chunk) for chunk in chunks)
    mode_overhead = {
        "single_agent": 8,
        "swarm": 18,
        "supervisor": 32,
    }[mode]
    return token_count + mode_overhead + handoff_count * 6


def _estimate_latency_ms(
    mode: BenchmarkMode,
    token_estimate: int,
    agent_count: int,
    handoff_count: int,
) -> int:
    mode_base = {
        "single_agent": 10,
        "swarm": 16,
        "supervisor": 24,
    }[mode]
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


def _stable_payload_hash(payload: object) -> str:
    raw = json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def _benchmark_trace_id(report: BenchmarkReport, artifact_id: str) -> str:
    return _stable_payload_hash(
        {
            "suite_name": report.suite_name,
            "mission_id": report.mission_id,
            "artifact_id": artifact_id,
        }
    )


def _benchmark_id_suffix(report: BenchmarkReport, artifact_id: str) -> str:
    return _benchmark_trace_id(report, artifact_id).removeprefix("sha256:")[:16]


def _benchmark_side_effect_key(artifact_id: str) -> str:
    return f"{BENCHMARK_OPERATION}:{artifact_id}"


def _benchmark_idempotency_key(report: BenchmarkReport, artifact_id: str) -> str:
    return f"{report.suite_name}:{artifact_id}"


def _benchmark_runtime_receipt_id(report: BenchmarkReport, artifact_id: str) -> str:
    return f"rr_{BENCHMARK_OPERATION.replace('.', '_')}_{_benchmark_id_suffix(report, artifact_id)}"


def _benchmark_execution_identity(
    report: BenchmarkReport,
    artifact_id: str,
) -> ExecutionIdentity:
    suffix = _benchmark_id_suffix(report, artifact_id)
    trace_id = _benchmark_trace_id(report, artifact_id)
    return ExecutionIdentity.new(
        task_id=report.suite_name,
        run_id=f"run_{BENCHMARK_OPERATION.replace('.', '_')}_{suffix}",
        claim_id=f"claim_{BENCHMARK_OPERATION.replace('.', '_')}_{suffix}",
        trace_id=trace_id,
        correlation_id=trace_id,
        idempotency_key=_benchmark_idempotency_key(report, artifact_id),
        agent_id=BENCHMARK_AGENT_ID,
        session_id=f"mission:{report.mission_id}" if report.mission_id else "",
        artifact_id=artifact_id,
        metadata={
            "mission_id": report.mission_id,
            "operation": BENCHMARK_OPERATION,
        },
    )


def _benchmark_runtime_metrics(report: BenchmarkReport) -> dict[str, int | float]:
    summary = report.summary["modes"]
    assert isinstance(summary, dict)
    input_tokens = sum(
        int(row["token_estimate"])
        for row in summary.values()
        if isinstance(row, dict)
    )
    cost_usd = sum(
        float(row["cost_estimate_usd"])
        for row in summary.values()
        if isinstance(row, dict)
    )
    return {
        "input_tokens": input_tokens,
        "output_tokens": 0,
        "cost_estimate_usd": round(cost_usd, 6),
        "latency_ms": sum(result.latency_ms for result in report.results),
    }


def _benchmark_runtime_payload(
    report: BenchmarkReport,
    *,
    artifact_id: str,
    artifact_path: Path,
    side_effect_key: str,
    idempotency_key: str,
) -> dict[str, object]:
    metrics = _benchmark_runtime_metrics(report)
    return {
        "schema_version": "langgraph_parity.benchmark.runtime_receipt.v1",
        "mission_id": report.mission_id,
        "operation": BENCHMARK_OPERATION,
        "suite_name": report.suite_name,
        "artifact_id": artifact_id,
        "artifact_refs": [artifact_id],
        "artifact_path": str(artifact_path),
        "side_effect_key": side_effect_key,
        "idempotency_key": idempotency_key,
        "provider": report.provider_profile.provider,
        "model": report.provider_profile.model,
        "provider_execution": False,
        "provider_model_truth_source": "runtime_control.no_provider_execution",
        "provider_model_applicability": "not_applicable",
        "no_provider_model_reason": (
            "deterministic_local_benchmark_no_external_provider_call"
        ),
        "task_count": len(report.tasks),
        "mode_count": len(BENCHMARK_MODES),
        "result_count": len(report.results),
        **metrics,
    }


def _record_benchmark_lifecycle_state(
    store: RuntimeStateStore,
    *,
    identity: ExecutionIdentity,
    report: BenchmarkReport,
    artifact_id: str,
    artifact_path: Path,
    metadata: dict[str, object],
) -> None:
    created_at = datetime.now(timezone.utc)
    lifecycle_metadata = {
        **metadata,
        **identity.to_metadata(),
    }
    if store.get_task_claim_sync(identity.claim_id) is None:
        store.create_task_claim_sync(
            TaskClaim(
                claim_id=identity.claim_id,
                task_id=identity.task_id,
                agent_id=identity.agent_id,
                status="completed",
                session_id=identity.session_id,
                claimed_at=created_at,
                acked_at=created_at,
                heartbeat_at=created_at,
                metadata=lifecycle_metadata,
            )
        )
    if store.get_delegation_run_sync(identity.run_id) is None:
        store.create_delegation_run_sync(
            DelegationRun(
                run_id=identity.run_id,
                task_id=identity.task_id,
                assigned_to=identity.agent_id,
                status="completed",
                session_id=identity.session_id,
                claim_id=identity.claim_id,
                assigned_by=BENCHMARK_OPERATION,
                requested_output=[
                    "langgraph_parity_benchmark_report",
                    "langgraph_parity_runtime_receipt",
                ],
                current_artifact_id=artifact_id,
                started_at=created_at,
                completed_at=created_at,
                metadata=lifecycle_metadata,
            )
        )
    _record_benchmark_artifact(
        store,
        identity=identity,
        report=report,
        artifact_id=artifact_id,
        artifact_path=artifact_path,
        metadata=metadata,
        created_at=created_at,
    )


def _record_benchmark_artifact(
    store: RuntimeStateStore,
    *,
    identity: ExecutionIdentity,
    report: BenchmarkReport,
    artifact_id: str,
    artifact_path: Path,
    metadata: dict[str, object],
    created_at: datetime,
) -> None:
    artifact = ArtifactRecord(
        artifact_id=artifact_id,
        artifact_kind="langgraph_parity_benchmark_report",
        session_id=identity.session_id,
        task_id=identity.task_id,
        run_id=identity.run_id,
        trace_id=identity.trace_id,
        manifest_path=str(artifact_path.with_name("benchmark_receipt.json")),
        payload_path=str(artifact_path),
        checksum=artifact_id,
        promotion_state="ephemeral",
        created_at=created_at,
        metadata={
            **metadata,
            "suite_name": report.suite_name,
            "artifact_role": "benchmark_report",
        },
    )
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        asyncio.run(store.record_artifact(artifact))
        return
    raise RuntimeError("cannot record benchmark artifact inside a running event loop")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run the deterministic LangGraph parity isolation benchmark."
    )
    parser.add_argument(
        "--output-dir",
        default="reports/langgraph_parity/benchmark",
        help="Directory for benchmark_report.json and benchmark_report.md.",
    )
    parser.add_argument("--provider", default="local")
    parser.add_argument("--model", default="deterministic-isolation-harness-v1")
    parser.add_argument("--cost-per-1k-tokens", type=float, default=0.0002)
    parser.add_argument("--mission-id", default="")
    parser.add_argument(
        "--runtime-db",
        default="",
        help="Runtime DB path for the canonical receipt; defaults to the live runtime DB.",
    )
    parser.add_argument(
        "--no-runtime-receipt",
        action="store_true",
        help="Write report artifacts without recording a canonical runtime receipt.",
    )
    args = parser.parse_args(argv)

    report = run_benchmark(
        provider_profile=ProviderProfile(
            provider=args.provider,
            model=args.model,
            cost_per_1k_tokens=args.cost_per_1k_tokens,
        ),
        mission_id=args.mission_id,
    )
    json_path, markdown_path = write_report(report, args.output_dir)
    runtime_receipt = None
    if not args.no_runtime_receipt:
        artifact_id = _stable_payload_hash(report.to_dict())
        runtime_receipt = record_benchmark_runtime_receipt(
            report,
            artifact_id=artifact_id,
            artifact_path=json_path,
            runtime_db_path=args.runtime_db or None,
        )
    print(f"wrote {json_path}")
    print(f"wrote {markdown_path}")
    if runtime_receipt is not None:
        print(f"runtime_receipt_id={runtime_receipt.receipt_id}")
        print(f"runtime_run_id={runtime_receipt.run_id}")
    print(json.dumps(report.summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
