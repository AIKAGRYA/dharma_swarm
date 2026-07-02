from __future__ import annotations

import asyncio
import hashlib
import json
import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path

from dharma_swarm.holon_truth_projection import (
    CANONICAL_STATE_SCHEMA_VERSION,
    PROJECTION_SCHEMA_VERSION,
    build_codex_composer_canonical_state,
    project_holon_receipt,
    write_codex_composer_canonical_state,
)
from dharma_swarm.holon_service_liveness import record_service_heartbeat
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


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, sort_keys=True) + "\n", encoding="utf-8")


def _write_codex_identity(agents_root: Path) -> None:
    _write_json(
        agents_root / "codex_composer" / "identity.json",
        {
            "agent_uid": "codex_composer",
            "model": "gpt-5.5",
            "model_route": {
                "model": "gpt-5.5",
                "provider": "codex",
                "route_status": "seeded_from_capability_card",
            },
            "provider": "codex",
        },
    )


def _write_bridge_heartbeat(
    path: Path,
    *,
    observed_at: datetime,
    status: str = "IDLE",
) -> None:
    _write_json(
        path,
        {
            "agent_uid": "codex_composer",
            "consumer": "codex_composer_inbox",
            "cycle": 7,
            "last_receipt_path": "/tmp/delivery.json",
            "schema_version": "dharma.a2a.inbox_bridge_heartbeat.v1",
            "status": status,
            "stream": "DHARMA_FLEET",
            "subject": "dharma.agent.codex_composer.inbox",
            "timestamp": observed_at.isoformat().replace("+00:00", "Z"),
        },
    )


def _write_responder_receipt(path: Path, *, observed_at: datetime) -> None:
    _write_json(
        path,
        {
            "agent_uid": "codex_composer",
            "domain_receipt_claim": True,
            "handler_ack_is_semantic_cognition": False,
            "packet_id": "packet-1",
            "reply_subject": "dharma.agent.codex_composer.inbox.reply.packet-1",
            "schema_version": "dharma.a2a.codex_composer_semantic_responder.v1",
            "semantic_reply_claim": True,
            "status": "DOMAIN_REPLY_PUBLISHED",
            "timestamp": observed_at.isoformat().replace("+00:00", "Z"),
        },
    )


def _write_l4_artifact(path: Path, *, live_model_call_claimed: bool = False) -> None:
    _write_json(
        path,
        {
            "artifact": {
                "artifact_id": "holon_l4_artifact:test",
                "digest": "sha256:l4artifact",
                "path": str(path),
            },
            "holon": "codex_composer",
            "model_probe": {
                "attempted": False,
                "responsive": False,
                "status": "skipped",
            },
            "orchestration_probe": {
                "live_model_call_claimed": live_model_call_claimed,
                "orchestrated": True,
                "status": "ok",
                "synthesis_source": "deterministic_default",
            },
            "routing_decision": {
                "live_model_call": live_model_call_claimed,
                "model": "gpt-5.5",
                "provider_type": "codex",
            },
            "schema_version": "dharma.holon_l4_artifact.v1",
        },
    )


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


def test_codex_composer_canonical_state_writer_projects_component_truth(
    tmp_path: Path,
) -> None:
    now = datetime(2026, 6, 30, 0, 0, tzinfo=UTC)
    dharma_home = tmp_path / ".dharma"
    repo_root = tmp_path / "repo"
    agents_root = dharma_home / "agents"
    state_root = dharma_home / "a2a_bus" / "state"
    codex_state = state_root / "codex_composer.json"
    hermes_state = state_root / "hermes-m5.json"
    hermes_raw = json.dumps({"agent": "hermes-m5", "status": "operational"}) + "\n"
    _write_json(
        codex_state,
        {
            "agent": "codex_composer",
            "last_heartbeat": "2026-06-20T03:40:25Z",
            "legacy_field": "preserve-me",
            "status": "legacy_stale",
        },
    )
    hermes_state.parent.mkdir(parents=True, exist_ok=True)
    hermes_state.write_text(hermes_raw, encoding="utf-8")
    _write_codex_identity(agents_root)
    _write_bridge_heartbeat(
        dharma_home / "a2a_bus" / "bridge_heartbeats" / "codex_composer.json",
        observed_at=now - timedelta(seconds=10),
    )
    record_service_heartbeat(
        "codex_composer",
        agents_root=agents_root,
        session_id="semantic-responder",
        service_id="codex-composer-semantic-responder",
        status="idle",
        observed_at=now - timedelta(seconds=20),
        claim_scope={
            "handler_ack_is_semantic_cognition": False,
            "live_model_call_claimed": False,
            "semantic_responder_fresh": True,
        },
    )
    _write_responder_receipt(
        dharma_home
        / "external_agents"
        / "codex_composer"
        / "nest"
        / "semantic_responder"
        / "receipts"
        / "latest.json",
        observed_at=now - timedelta(seconds=30),
    )
    _write_responder_receipt(
        repo_root / "reports" / "a2a" / "domain_reply_receipts" / "latest.json",
        observed_at=now - timedelta(seconds=30),
    )
    l4_artifact = agents_root / "codex_composer" / "artifacts" / "l4-proof.json"
    _write_l4_artifact(l4_artifact)
    record_service_heartbeat(
        "codex_composer",
        agents_root=agents_root,
        session_id="l4-service",
        service_id="holon-l4-service",
        status="idle",
        observed_at=now - timedelta(seconds=40),
        proof_ref={
            "artifact": {
                "artifact_id": "holon_l4_artifact:test",
                "digest": "sha256:l4artifact",
                "path": str(l4_artifact),
            },
            "kind": "l4_service_cycle",
            "proof_digest": "sha256:l4proof",
        },
        claim_scope={
            "live_specialist_execution": True,
            "model_responsive": False,
            "orchestration_proven": True,
            "transport_reachable": True,
        },
    )

    state = write_codex_composer_canonical_state(
        dharma_home=dharma_home,
        repo_root=repo_root,
        now=now,
        launchd_pid=1234,
    )
    written = json.loads(codex_state.read_text(encoding="utf-8"))

    assert written == state
    assert written["schema_version"] == CANONICAL_STATE_SCHEMA_VERSION
    assert written["agent_uid"] == "codex_composer"
    assert written["status"] == "operational"
    assert written["last_heartbeat"] == "2026-06-30T00:00:00Z"
    assert written["legacy_field"] == "preserve-me"
    assert (
        written["launchd_label"]
        == "com.dharma.codex-composer-semantic-responder"
    )
    assert written["pid"] == 1234
    assert written["launchd"] == {
        "label": "com.dharma.codex-composer-semantic-responder",
        "pid": 1234,
        "pid_known": True,
    }
    assert written["bridge_transport_reachable"] is True
    assert written["responder_alive"] is True
    assert written["l4_service_alive"] is True
    assert written["freshness"] == {
        "bridge": "fresh",
        "semantic_responder": "fresh",
        "l4_service": "fresh",
    }
    assert written["component_freshness"] == written["freshness"]
    assert written["latest_semantic_responder_receipt"]["semantic_reply_claim"] is True
    assert (
        written["latest_semantic_responder_receipt"][
            "handler_ack_is_semantic_cognition"
        ]
        is False
    )
    assert written["latest_l4_proof_artifact"] == str(l4_artifact)
    assert written["latest_l4_proof_digest"] == "sha256:l4artifact"
    assert (
        written["components"]["l4_service"]["latest_proof"]["proof_digest"]
        == "sha256:l4proof"
    )
    assert written["provider_model_route"]["provider"] == "codex"
    assert written["provider_model_route"]["model"] == "gpt-5.5"
    assert written["live_model_call_claimed"] is False
    assert hermes_state.read_text(encoding="utf-8") == hermes_raw


def test_codex_composer_canonical_state_marks_stale_without_live_model_claim(
    tmp_path: Path,
) -> None:
    now = datetime(2026, 6, 30, 0, 0, tzinfo=UTC)
    dharma_home = tmp_path / ".dharma"
    repo_root = tmp_path / "repo"
    agents_root = dharma_home / "agents"
    _write_codex_identity(agents_root)
    _write_bridge_heartbeat(
        dharma_home / "a2a_bus" / "bridge_heartbeats" / "codex_composer.json",
        observed_at=now - timedelta(hours=2),
    )
    l4_artifact = agents_root / "codex_composer" / "artifacts" / "l4-proof.json"
    _write_l4_artifact(l4_artifact, live_model_call_claimed=False)
    record_service_heartbeat(
        "codex_composer",
        agents_root=agents_root,
        session_id="old-l4-service",
        service_id="holon-l4-service",
        status="idle",
        observed_at=now - timedelta(hours=2),
        proof_ref={
            "artifact": {
                "artifact_id": "holon_l4_artifact:test",
                "digest": "sha256:l4artifact",
                "path": str(l4_artifact),
            },
            "kind": "l4_service_cycle",
            "proof_digest": "sha256:l4proof",
        },
        claim_scope={
            "model_responsive": False,
            "orchestration_proven": True,
            "transport_reachable": True,
        },
    )

    state = build_codex_composer_canonical_state(
        dharma_home=dharma_home,
        repo_root=repo_root,
        now=now,
        bridge_fresh_after_seconds=60,
        responder_fresh_after_seconds=60,
        l4_fresh_after_seconds=60,
    )

    assert state["status"] == "stale"
    assert state["freshness"] == {
        "bridge": "stale",
        "semantic_responder": "missing",
        "l4_service": "stale",
    }
    assert (
        state["components"]["l4_service"]["latest_proof"]["orchestration_proven"]
        is True
    )
    assert state["live_model_call_claimed"] is False
