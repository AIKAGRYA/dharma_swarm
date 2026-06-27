from __future__ import annotations

import asyncio
import hashlib
import json
import sqlite3
from pathlib import Path

from dharma_swarm.holon_truth_projection import (
    PROJECTION_SCHEMA_VERSION,
    project_holon_receipt,
)
from dharma_swarm.operator_core.runtime_truth import (
    runtime_truth_packets_from_runtime_db,
    summarize_runtime_truth_packets,
)
from dharma_swarm.runtime_state import RuntimeStateStore
from holon.contracts import ArtifactRef, HolonCycleResult
from holon.receipts import build_receipt, write_receipt


def _agent(root: Path, name: str = "h") -> Path:
    dock = root / name
    dock.mkdir(parents=True)
    (dock / "identity.json").write_text(
        json.dumps({"name": name, "model": "holon-echo-v1"}) + "\n",
        encoding="utf-8",
    )
    (dock / "living_agent.json").write_text("{}\n", encoding="utf-8")
    return dock


def _source_receipt(root: Path, *, name: str = "h", status: str = "ran") -> Path:
    dock = _agent(root, name)
    artifact = dock / "artifacts" / "result.json"
    artifact.parent.mkdir(parents=True)
    artifact.write_text(json.dumps({"ok": True}) + "\n", encoding="utf-8")
    digest = "sha256:" + hashlib.sha256(artifact.read_bytes()).hexdigest()
    result = HolonCycleResult(
        status=status,
        reply="created report",
        task="make report",
        provider="echo",
        model="holon-echo-v1",
        cost_usd=0.0,
        finish_reason="stop",
        artifacts=[ArtifactRef(kind="file", path=str(artifact), digest=digest)],
    )
    receipt = build_receipt(
        kind="holon_cycle",
        subject=name,
        status=status,
        side_effect_key=f"cycle:{name}:1",
        payload=result.to_dict(),
        artifact_refs=[str(artifact)],
    )
    return Path(write_receipt(receipt, agents_root=root, holon_name=name)["path"])


def test_holon_receipt_projects_into_runtime_truth_spine(tmp_path: Path) -> None:
    agents_root = tmp_path / "agents"
    db_path = tmp_path / "runtime.db"
    receipt_path = _source_receipt(agents_root)
    store = RuntimeStateStore(db_path)

    projection = project_holon_receipt(
        receipt_path,
        runtime_state=store,
        agents_root=agents_root,
        session_id="sess-holon",
        mission_id="mission-holon",
        require_living_dock=True,
    )

    assert projection.status == "completed"
    assert projection.source_digest_verified is True
    assert projection.living_dock_status == "warn"
    assert store.get_execution_identity_sync(projection.run_id) is not None

    receipts = asyncio.run(store.list_runtime_receipts(run_id=projection.run_id, limit=20))
    by_type = {receipt.receipt_type for receipt in receipts}
    assert {"task_claim", "delegation_run", "side_effect_complete"} <= by_type
    parent = next(receipt for receipt in receipts if receipt.receipt_id == projection.parent_receipt_id)
    assert parent.payload["schema_version"] == PROJECTION_SCHEMA_VERSION
    assert parent.payload["source_receipt_id"] == projection.source_receipt_id
    assert parent.payload["source_digest_verified"] is True

    artifacts = asyncio.run(store.list_artifacts(run_id=projection.run_id))
    assert [artifact.artifact_id for artifact in artifacts] == projection.artifact_ids
    assert Path(artifacts[0].payload_path).exists()

    summary = summarize_runtime_truth_packets(
        runtime_truth_packets_from_runtime_db(db_path, observed_at="2026-06-26T00:00:00Z")
    )
    assert summary["latest_receipt"] == f"runtime_receipts:{projection.parent_receipt_id}"
    assert summary["run_id"] == projection.run_id
    assert summary["task_id"] == projection.task_id
    assert summary["mission_id"] == "mission-holon"
    assert summary["completion"] == "completed_by_receipt"
    assert "idempotency_record" not in summary["missing"]
    assert "task_claim" not in summary["missing"]
    assert "delegation_run" not in summary["missing"]
    assert summary["artifact_refs"]


def test_holon_projection_is_idempotent_by_parent_receipt_id(tmp_path: Path) -> None:
    agents_root = tmp_path / "agents"
    db_path = tmp_path / "runtime.db"
    receipt_path = _source_receipt(agents_root)
    store = RuntimeStateStore(db_path)

    first = project_holon_receipt(receipt_path, runtime_state=store, agents_root=agents_root)
    second = project_holon_receipt(receipt_path, runtime_state=store, agents_root=agents_root)

    assert first.parent_receipt_id == second.parent_receipt_id
    assert first.already_projected is False
    assert second.already_projected is True
    with sqlite3.connect(db_path) as db:
        receipt_count = db.execute(
            "SELECT COUNT(*) FROM runtime_receipts WHERE receipt_id = ?",
            (first.parent_receipt_id,),
        ).fetchone()[0]
        artifact_count = db.execute(
            "SELECT COUNT(*) FROM artifact_records WHERE run_id = ?",
            (first.run_id,),
        ).fetchone()[0]
    assert receipt_count == 1
    assert artifact_count == 1


def test_holon_projection_blocks_when_required_living_dock_fails(tmp_path: Path) -> None:
    agents_root = tmp_path / "agents"
    db_path = tmp_path / "runtime.db"
    receipt_path = _source_receipt(agents_root)
    (agents_root / "h" / "living_agent.json").unlink()

    projection = project_holon_receipt(
        receipt_path,
        runtime_db_path=db_path,
        agents_root=agents_root,
        require_living_dock=True,
    )

    receipts = asyncio.run(
        RuntimeStateStore(db_path).list_runtime_receipts(
            run_id=projection.run_id,
            receipt_type="side_effect_complete",
            limit=20,
        )
    )
    parent = next(receipt for receipt in receipts if receipt.receipt_id == projection.parent_receipt_id)
    assert projection.status == "blocked"
    assert projection.living_dock_status == "fail"
    assert parent.status == "blocked"
    assert parent.payload["projection_block_reason"] == "living_dock_verifier_failed"
