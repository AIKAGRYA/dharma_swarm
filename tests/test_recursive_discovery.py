"""Tests for recursive discovery shadow receipts and projection."""

from __future__ import annotations

from pathlib import Path
import sys

import pytest
import yaml

from dharma_swarm.evaluation_registry import EvaluationRegistry
from dharma_swarm.event_log import EventLog
from dharma_swarm.memory_lattice import MemoryLattice
from dharma_swarm.operator_core.control_surface import build_control_surface_rows
from dharma_swarm.recursive_discovery import (
    CandidateDiffReceipt,
    EVENT_STREAM,
    RECEIPT_TYPES,
    RecursiveDiscoveryRecorder,
    load_recursive_receipts,
    run_recursive_discovery_shadow_demo,
    run_shadow_evolution_foundry,
    receipt_counts_by_type,
    shadow_fixture_receipts,
    validate_minimum_receipt_chain,
)
from dharma_swarm.runtime_state import RuntimeStateStore, SessionState


def test_shadow_fixture_receipts_cover_minimum_loop() -> None:
    receipts = shadow_fixture_receipts()
    counts = receipt_counts_by_type(receipts)

    assert len(receipts) == len(RECEIPT_TYPES)
    assert all(counts[receipt_type] == 1 for receipt_type in RECEIPT_TYPES)
    assert all(receipt.schema_version == "recursive_discovery.v0" for receipt in receipts)
    assert all(len(receipt.content_hash()) == 64 for receipt in receipts)


def test_candidate_diff_receipt_rejects_unsafe_paths() -> None:
    with pytest.raises(ValueError, match="unsafe repo path"):
        CandidateDiffReceipt(
            limitation_id="lim-1",
            candidate_id="cand-1",
            files_touched=["/tmp/not-repo-relative.py"],
        )


def test_recorder_writes_valid_runtime_event(tmp_path: Path) -> None:
    event_log = EventLog(tmp_path / "events")
    receipt = shadow_fixture_receipts()[1]

    result = RecursiveDiscoveryRecorder(event_log).record(
        receipt,
        session_id="session-recursive-shadow",
        agent_id="test-agent",
    )

    assert result.stream == EVENT_STREAM
    assert result.event["payload"]["receipt_type"] == "generated_eval"
    assert result.event["payload"]["receipt_hash"] == receipt.content_hash()
    ok, errors = event_log.verify_stream(stream=EVENT_STREAM)
    assert ok, errors
    loaded = load_recursive_receipts(event_log)
    assert len(loaded) == 1
    assert loaded[0].receipt_id == receipt.receipt_id


def test_control_surface_projects_recursive_discovery_event_rows(tmp_path: Path) -> None:
    manifest = {
        "schema_version": 2,
        "last_updated": "2026-05-14",
        "api_routers": [],
        "dashboard_surfaces": [],
        "agents": [],
        "integrations": [],
        "loops": [],
        "recursive_discovery_surfaces": [
            {
                "id": "limitations",
                "label": "Recursive Limitations",
                "receipt_type": "limitation",
                "status": "shadow",
                "owner_module": "dharma_swarm/recursive_discovery.py",
                "priority": "p0",
            },
            {
                "id": "promotion_queue",
                "label": "Recursive Promotion Queue",
                "receipt_type": "promotion_decision",
                "status": "shadow",
                "owner_module": "dharma_swarm/recursive_discovery.py",
                "priority": "p0",
            },
        ],
    }
    (tmp_path / "ACTIVE_SURFACE_MANIFEST.yaml").write_text(
        yaml.dump(manifest, default_flow_style=False),
        encoding="utf-8",
    )
    event_log = EventLog(tmp_path / "events")
    recorder = RecursiveDiscoveryRecorder(event_log)
    for receipt in shadow_fixture_receipts():
        recorder.record(receipt, session_id="session-control-surface")

    rows = build_control_surface_rows(
        repo_root=tmp_path,
        event_log_dir=tmp_path / "events",
    )
    recursive_rows = [row for row in rows if row.kind == "recursive_discovery"]

    assert {row.id for row in recursive_rows} == {
        "recursive.limitations",
        "recursive.promotion_queue",
    }
    assert all(row.coherence_state == "partial" for row in recursive_rows)
    assert all("shadow_only" in row.gap_codes for row in recursive_rows)
    assert all(row.observed_state == "event_log:1" for row in recursive_rows)

    promotion = [row for row in recursive_rows if row.id == "recursive.promotion_queue"][0]
    assert promotion.human_decision_required is True
    assert promotion.human_decision is not None
    assert "human PR" in promotion.human_decision.recommended_action


def test_control_surface_reports_missing_recursive_evidence_without_fixture_claim(
    tmp_path: Path,
) -> None:
    manifest = {
        "schema_version": 2,
        "last_updated": "2026-05-14",
        "api_routers": [],
        "dashboard_surfaces": [],
        "agents": [],
        "integrations": [],
        "loops": [],
        "recursive_discovery_surfaces": [
            {
                "id": "generated_evals",
                "label": "Recursive Generated Evals",
                "receipt_type": "generated_eval",
                "status": "shadow",
                "owner_module": "dharma_swarm/recursive_discovery.py",
                "priority": "p0",
            },
        ],
    }
    (tmp_path / "ACTIVE_SURFACE_MANIFEST.yaml").write_text(
        yaml.dump(manifest, default_flow_style=False),
        encoding="utf-8",
    )

    rows = build_control_surface_rows(
        repo_root=tmp_path,
        event_log_dir=tmp_path / "events",
    )
    recursive_row = [row for row in rows if row.kind == "recursive_discovery"][0]

    assert recursive_row.observed_state == "no_persisted_evidence"
    assert recursive_row.coherence_state == "declared_only"
    assert "recursive_discovery_evidence_missing" in recursive_row.gap_codes
    assert recursive_row.raw["fixture_available"] == 1


@pytest.mark.asyncio
async def test_shadow_evolution_foundry_records_ten_sandbox_variants(tmp_path: Path) -> None:
    event_log = EventLog(tmp_path / "events")

    result = await run_shadow_evolution_foundry(
        session_id="sess-foundry",
        repo_root=tmp_path,
        sandbox_root=tmp_path / "sandboxes",
        archive_path=tmp_path / "archive.jsonl",
        event_log=event_log,
        variant_count=10,
        trace_id="trace-foundry",
    )
    loaded = load_recursive_receipts(event_log, session_id="sess-foundry")
    counts = receipt_counts_by_type(loaded)
    report = result.to_report()

    assert len(result.receipts) == 60
    assert len(loaded) == 60
    assert all(counts[receipt_type] == 10 for receipt_type in RECEIPT_TYPES)
    assert report["receipt_count"] == 60
    assert len(report["archive_entry_ids"]) == 10
    assert set(report["promotion_decisions"]) == {"hold"}
    assert result.proof_exit_code == 1
    assert (tmp_path / "archive.jsonl").exists()
    assert len((tmp_path / "archive.jsonl").read_text(encoding="utf-8").splitlines()) == 10

    by_parent: dict[str, list] = {}
    for receipt in loaded:
        by_parent.setdefault(receipt.parent_id or "", []).append(receipt)
    assert len(by_parent) == 10
    for chain in by_parent.values():
        ok, errors = validate_minimum_receipt_chain(chain)
        assert ok, errors


@pytest.mark.asyncio
async def test_evaluation_registry_records_recursive_discovery_receipt(tmp_path: Path) -> None:
    db_path = tmp_path / "runtime.db"
    runtime_state = RuntimeStateStore(db_path)
    memory_lattice = MemoryLattice(db_path=db_path, event_log_dir=tmp_path / "events")
    await runtime_state.init_db()
    await memory_lattice.init_db()
    await runtime_state.upsert_session(
        SessionState(
            session_id="sess-recursive",
            operator_id="operator",
            status="active",
            current_task_id="task-recursive",
        )
    )

    registry = EvaluationRegistry(
        runtime_state=runtime_state,
        memory_lattice=memory_lattice,
        workspace_root=tmp_path / "workspace" / "sessions",
        provenance_root=tmp_path / "workspace" / "sessions",
    )
    receipt = shadow_fixture_receipts()[1]
    result = await registry.record_recursive_discovery_receipt(
        receipt.model_dump(mode="json"),
        session_id="sess-recursive",
        task_id="task-recursive",
        created_by="test-agent",
    )

    persisted_artifact = await runtime_state.get_artifact(result.artifact.artifact_id)
    stream_rows = memory_lattice.event_log.read_envelopes(
        stream=EVENT_STREAM,
        session_id="sess-recursive",
    )

    assert persisted_artifact is not None
    assert persisted_artifact.artifact_kind == "recursive_discovery_receipt"
    assert {fact.fact_kind for fact in result.facts} == {
        "recursive_discovery_receipt",
        "recursive_generated_eval",
    }
    assert result.summary["receipt_type"] == "generated_eval"
    assert result.summary["eval_ids"] == receipt.eval_ids
    assert stream_rows[-1]["payload"]["action_name"] == "record_recursive_discovery_receipt"

    await memory_lattice.close()


@pytest.mark.asyncio
async def test_recursive_shadow_demo_records_event_and_registry_receipts(tmp_path: Path) -> None:
    db_path = tmp_path / "runtime.db"
    runtime_state = RuntimeStateStore(db_path)
    memory_lattice = MemoryLattice(db_path=db_path, event_log_dir=tmp_path / "events")
    await runtime_state.init_db()
    await memory_lattice.init_db()
    await runtime_state.upsert_session(
        SessionState(
            session_id="sess-shadow-demo",
            operator_id="operator",
            status="active",
            current_task_id="task-shadow-demo",
        )
    )
    registry = EvaluationRegistry(
        runtime_state=runtime_state,
        memory_lattice=memory_lattice,
        workspace_root=tmp_path / "workspace" / "sessions",
        provenance_root=tmp_path / "workspace" / "sessions",
    )

    result = await run_recursive_discovery_shadow_demo(
        session_id="sess-shadow-demo",
        task_id="task-shadow-demo",
        repo_root=tmp_path,
        event_log=memory_lattice.event_log,
        evaluation_registry=registry,
        proof_command=(sys.executable, "-c", "print('1 passed in 0.01s')"),
    )

    rows = memory_lattice.event_log.read_envelopes(stream=EVENT_STREAM)

    assert result.proof_exit_code == 0
    assert len(result.receipts) == len(RECEIPT_TYPES)
    assert len(result.recorded_events) == len(RECEIPT_TYPES)
    assert len(result.registry_summaries) == len(RECEIPT_TYPES)
    assert {receipt.receipt_type for receipt in result.receipts} == set(RECEIPT_TYPES)
    assert {row["payload"]["receipt_type"] for row in rows} >= set(RECEIPT_TYPES)

    await memory_lattice.close()
