"""Report and runtime receipt helpers for the LangGraph parity benchmark."""

from __future__ import annotations

import asyncio
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from dharma_swarm.langgraph_parity.benchmark_runner import format_markdown_report
from dharma_swarm.langgraph_parity.benchmark_types import (
    BENCHMARK_AGENT_ID,
    BENCHMARK_MODES,
    BENCHMARK_OPERATION,
    BenchmarkReport,
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


def write_report(report: BenchmarkReport, output_dir: str | Path) -> tuple[Path, Path]:
    """Write JSON, Markdown, and receipt artifacts."""

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
        artifact_id=stable_payload_hash(report_payload),
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


def stable_payload_hash(payload: object) -> str:
    raw = json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def _benchmark_trace_id(report: BenchmarkReport, artifact_id: str) -> str:
    return stable_payload_hash(
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
    prefix = BENCHMARK_OPERATION.replace(".", "_")
    return f"rr_{prefix}_{_benchmark_id_suffix(report, artifact_id)}"


def _benchmark_execution_identity(
    report: BenchmarkReport,
    artifact_id: str,
) -> ExecutionIdentity:
    suffix = _benchmark_id_suffix(report, artifact_id)
    trace_id = _benchmark_trace_id(report, artifact_id)
    prefix = BENCHMARK_OPERATION.replace(".", "_")
    return ExecutionIdentity.new(
        task_id=report.suite_name,
        run_id=f"run_{prefix}_{suffix}",
        claim_id=f"claim_{prefix}_{suffix}",
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
    lifecycle_metadata = {**metadata, **identity.to_metadata()}
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
