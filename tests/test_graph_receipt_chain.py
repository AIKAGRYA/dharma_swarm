"""Receipt-unification rung 0: dispatch receipts enter a hash chain."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from dharma_swarm.graph.receipt_chain import (
    DISPATCH_CHAIN_SCHEMA_VERSION,
    append_dispatch_receipt_to_machine_chain,
    dispatch_machine_receipt,
)
from dharma_swarm.spine.receipt import EvidenceReceipt


def _receipt(task_id: str = "task-1") -> EvidenceReceipt:
    return EvidenceReceipt(
        trace_id="trace-1",
        context_id="ctx-1",
        task_id=task_id,
        claim_id="claim-1",
        agent_id="agent-1",
        provider="anthropic",
        model="claude-fable-5",
        operation="invoke_agent",
        provider_attempted=True,
        status="ok",
        started_at=datetime(2026, 7, 6, 4, 0, tzinfo=timezone.utc),
        finished_at=datetime(2026, 7, 6, 4, 1, tzinfo=timezone.utc),
        attributes={"side_effect_key": f"invoke_agent:{task_id}:agent-1"},
    )


def test_dispatch_receipt_projection_uses_hash_uris_and_z_timestamps():
    machine = dispatch_machine_receipt(_receipt(), operation_hash="a" * 64)

    assert machine.claim_id == "claim-1"
    assert machine.command == "invoke_agent"
    assert machine.actor == "agent-1"
    assert machine.exit_code == 0
    assert machine.started_at == "2026-07-06T04:00:00Z"
    assert machine.finished_at == "2026-07-06T04:01:00Z"
    assert machine.stdout_stderr_hash.startswith("sha256:")
    assert machine.artifact_hashes["evidence_receipt"].startswith("sha256:")
    assert machine.artifact_hashes["operation"] == f"sha256:{'a' * 64}"
    assert machine.attributes["schema_version"] == DISPATCH_CHAIN_SCHEMA_VERSION
    assert machine.attributes["receipt_hash"].startswith("sha256:")
    assert machine.attributes["side_effect_key_hash"].startswith("sha256:")


def test_dispatch_receipts_append_to_existing_machine_chain(tmp_path: Path):
    log = tmp_path / "claim_evidence_receipts.jsonl"
    first = append_dispatch_receipt_to_machine_chain(_receipt("task-1"), path=log)
    second = append_dispatch_receipt_to_machine_chain(_receipt("task-2"), path=log)

    assert first.verify()
    assert second.verify()
    assert first.prev_digest == ""
    assert second.prev_digest == first.digest

    rows = [json.loads(line) for line in log.read_text().splitlines() if line.strip()]
    assert [row["attributes"]["task_id"] for row in rows] == ["task-1", "task-2"]
