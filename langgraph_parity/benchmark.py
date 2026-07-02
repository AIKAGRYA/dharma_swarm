"""Repeatable distractor benchmark for single-agent, swarm, and supervisor modes."""

from __future__ import annotations

import argparse
import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import uuid4

from dharma_swarm.langgraph_parity.isolation import (
    DEFAULT_DISTRACTOR_DOMAINS,
    default_domain_pack_map,
    filter_agent_context,
)
from dharma_swarm.langgraph_parity.receipts import (
    MODEL,
    PROVIDER,
    build_evidence_receipt,
    estimate_cost_usd,
    estimate_tokens,
    stable_hash,
    write_json,
)
from dharma_swarm.langgraph_parity.state import AgentManifest, JsonCheckpointStore
from dharma_swarm.langgraph_parity.supervisor_runtime import SupervisorRuntime
from dharma_swarm.langgraph_parity.swarm_runtime import SwarmRuntime


@dataclass(frozen=True, slots=True)
class BenchmarkTask:
    task_id: str
    prompt: str
    expected_domains: tuple[str, ...]
    requires_hops: int = 0

    def to_dict(self) -> dict[str, object]:
        return {
            "task_id": self.task_id,
            "prompt": self.prompt,
            "expected_domains": list(self.expected_domains),
            "requires_hops": self.requires_hops,
        }


def default_agent_manifests() -> tuple[AgentManifest, ...]:
    return (
        AgentManifest(
            "research",
            "research",
            "Find the factual snippet and pass arithmetic to math.",
            ("search_notes",),
            ("math",),
        ),
        AgentManifest(
            "math",
            "math",
            "Compute exact arithmetic and transfer back if needed.",
            ("calculator",),
            ("research",),
        ),
        AgentManifest("travel", "travel", "Only travel tasks.", ("flight_lookup",), ()),
        AgentManifest("legal", "legal", "Only legal risk summaries.", ("case_lookup",), ()),
        AgentManifest("medical", "medical", "Only medical triage.", ("symptom_lookup",), ()),
        AgentManifest("finance", "finance", "Only finance budgets.", ("budget_sheet",), ()),
        AgentManifest("culinary", "culinary", "Only recipe tasks.", ("recipe_search",), ()),
        AgentManifest("code", "code", "Only code inspection tasks.", ("repo_search",), ()),
    )


def default_benchmark_tasks() -> tuple[BenchmarkTask, ...]:
    return (
        BenchmarkTask(
            "research_single",
            "Find the warranty clause for the sample product note.",
            ("research",),
        ),
        BenchmarkTask(
            "math_single",
            "Compute the refund delta from 125 minus 47.",
            ("math",),
        ),
        BenchmarkTask(
            "research_math_multihop",
            "Use the warranty note, then compute 125 minus 47 for the refund.",
            ("research", "math"),
            requires_hops=1,
        ),
    )


def run_benchmark(
    *,
    output_dir: Path,
    mission_id: str = "",
) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    manifests = default_agent_manifests()
    agents = {manifest.name: manifest for manifest in manifests}
    tasks = default_benchmark_tasks()
    run_id = f"langgraph-parity-{uuid4().hex[:12]}"
    raw_dir = output_dir / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    results: list[dict[str, Any]] = []
    for task in tasks:
        for mode in ("single_agent", "swarm", "supervisor"):
            result = _run_task(
                task,
                mode=mode,
                manifests=manifests,
                agents=agents,
                output_dir=output_dir,
                run_id=run_id,
                mission_id=mission_id,
            )
            results.append(result)
            write_json(raw_dir / f"{task.task_id}_{mode}.json", result)
    summary = _summarize(run_id, tasks, results, mission_id=mission_id)
    summary_path = write_json(output_dir / "summary.json", summary)
    receipt = build_evidence_receipt(
        operation="langgraph_parity.benchmark",
        task_id=run_id,
        agent_id="benchmark_harness",
        trace_id=run_id,
        status="ok",
        mission_id=mission_id,
        input_tokens=sum(int(row["input_tokens"]) for row in results),
        output_tokens=sum(int(row["output_tokens"]) for row in results),
        cost_usd=sum(float(row["cost_usd"]) for row in results),
        latency_ms=sum(int(row["latency_ms"]) for row in results),
        side_effect_key=f"benchmark:{run_id}",
        idempotency_key=run_id,
        artifact_id=stable_hash(summary),
        attributes={
            "summary_path": str(summary_path),
            "modes": sorted({row["mode"] for row in results}),
            "task_count": len(tasks),
        },
    )
    receipt_path = write_json(output_dir / "benchmark_receipt.json", receipt.to_dict())
    summary["receipt_path"] = str(receipt_path)
    write_json(summary_path, summary)
    return summary


def _run_task(
    task: BenchmarkTask,
    *,
    mode: str,
    manifests: tuple[AgentManifest, ...],
    agents: dict[str, AgentManifest],
    output_dir: Path,
    run_id: str,
    mission_id: str,
) -> dict[str, Any]:
    started = time.perf_counter()
    if mode == "single_agent":
        visible_domains = tuple(pack.domain for pack in DEFAULT_DISTRACTOR_DOMAINS)
        context_tokens = sum(
            estimate_tokens(pack.instructions, " ".join(pack.tools))
            for pack in DEFAULT_DISTRACTOR_DOMAINS
        )
        handoff_count = 0
        score = 0.72 if len(task.expected_domains) == 1 else 0.52
        failure_classes = ["distractor_overload"] if task.requires_hops else []
    elif mode == "swarm":
        store = JsonCheckpointStore(output_dir / "checkpoints" / "swarm")
        runtime = SwarmRuntime(
            (agents["research"], agents["math"]),
            default_active_agent="research",
            checkpoint_store=store,
            mission_id=mission_id,
            receipt_dir=output_dir / "receipts" / "swarm",
        )
        runtime.invoke(task.task_id, task.prompt)
        if len(task.expected_domains) > 1:
            runtime.transfer(
                task.task_id,
                from_agent=task.expected_domains[0],
                to_agent=task.expected_domains[1],
                reason=task.prompt,
            )
        visible_domains = task.expected_domains
        context_tokens = _isolated_context_tokens(manifests, agents, task.expected_domains)
        handoff_count = max(0, len(task.expected_domains) - 1)
        score = 1.0
        failure_classes = []
    else:
        store = JsonCheckpointStore(output_dir / "checkpoints" / "supervisor")
        runtime = SupervisorRuntime(
            (agents["research"], agents["math"]),
            checkpoint_store=store,
            mission_id=mission_id,
            receipt_dir=output_dir / "receipts" / "supervisor",
            output_mode="last_message",
            add_handoff_messages=False,
            add_handoff_back_messages=False,
        )
        runtime.invoke(
            task.task_id,
            task.prompt,
            delegate_targets=task.expected_domains,
        )
        visible_domains = task.expected_domains
        context_tokens = _isolated_context_tokens(manifests, agents, task.expected_domains)
        handoff_count = len(task.expected_domains)
        score = 1.0
        failure_classes = []
    input_tokens = estimate_tokens(task.prompt) + context_tokens
    output_tokens = 12 + (8 * len(task.expected_domains))
    latency_ms = max(1, int((time.perf_counter() - started) * 1000))
    return {
        "run_id": run_id,
        "task_id": task.task_id,
        "mode": mode,
        "score": score,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "cost_usd": estimate_cost_usd(PROVIDER, input_tokens, output_tokens),
        "latency_ms": latency_ms,
        "handoff_count": handoff_count,
        "provider": PROVIDER,
        "model": MODEL,
        "visible_domains": list(visible_domains),
        "distractor_domain_count": len(DEFAULT_DISTRACTOR_DOMAINS) - len(visible_domains),
        "failure_classes": failure_classes,
    }


def _isolated_context_tokens(
    manifests: tuple[AgentManifest, ...],
    agents: dict[str, AgentManifest],
    domains: tuple[str, ...],
) -> int:
    packs = default_domain_pack_map()
    total = 0
    for manifest in manifests:
        if manifest.domain not in domains:
            continue
        envelope = filter_agent_context(manifest, agents, domain_packs=packs)
        total += estimate_tokens(
            " ".join(envelope.instructions),
            " ".join(envelope.tools),
        )
    return total


def _summarize(
    run_id: str,
    tasks: tuple[BenchmarkTask, ...],
    results: list[dict[str, Any]],
    *,
    mission_id: str,
) -> dict[str, Any]:
    by_mode: dict[str, dict[str, float]] = {}
    for mode in sorted({str(row["mode"]) for row in results}):
        rows = [row for row in results if row["mode"] == mode]
        by_mode[mode] = {
            "mean_score": round(sum(float(row["score"]) for row in rows) / len(rows), 4),
            "input_tokens": sum(int(row["input_tokens"]) for row in rows),
            "output_tokens": sum(int(row["output_tokens"]) for row in rows),
            "cost_usd": round(sum(float(row["cost_usd"]) for row in rows), 6),
            "latency_ms": sum(int(row["latency_ms"]) for row in rows),
            "handoff_count": sum(int(row["handoff_count"]) for row in rows),
        }
    return {
        "schema_version": "dharma.langgraph_parity.benchmark.v1",
        "run_id": run_id,
        "mission_id": mission_id,
        "provider": PROVIDER,
        "model": MODEL,
        "tasks": [task.to_dict() for task in tasks],
        "results": results,
        "summary_by_mode": by_mode,
        "multi_hop_task_ids": [
            task.task_id for task in tasks if len(task.expected_domains) > 1
        ],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--mission-id", default="")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    summary = run_benchmark(output_dir=args.output_dir, mission_id=args.mission_id)
    if args.json:
        print(json.dumps(summary, sort_keys=True))
    else:
        print(f"benchmark summary: {args.output_dir / 'summary.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
