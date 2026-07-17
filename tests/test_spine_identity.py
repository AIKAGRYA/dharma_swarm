from __future__ import annotations

from dharma_swarm.spine import intent_idempotency_key as exported_intent_idempotency_key
from dharma_swarm.spine.identity import ExecutionIdentity, intent_idempotency_key


def test_default_idempotency_key_is_stable_across_retry_attempt_identity() -> None:
    first = ExecutionIdentity.new(
        task_id="task-intent-1",
        run_id="run-attempt-1",
        claim_id="claim-attempt-1",
        trace_id="trace-attempt-1",
        agent_id="agent-a",
        session_id="session-a",
        metadata={"task_content_hash": "sha256:content-a", "origin_event_id": "evt-1"},
    )
    retry = ExecutionIdentity.new(
        task_id="task-intent-1",
        run_id="run-attempt-2",
        claim_id="claim-attempt-2",
        trace_id="trace-attempt-2",
        agent_id="agent-b",
        session_id="session-b",
        metadata={"task_content_hash": "sha256:content-a", "origin_event_id": "evt-1"},
    )

    assert first.run_id != retry.run_id
    assert first.claim_id != retry.claim_id
    assert first.trace_id != retry.trace_id
    assert first.idempotency_key == retry.idempotency_key
    assert first.idempotency_key.startswith("idem_intent_")
    assert first.idempotency_key != f"idem_{first.run_id}"
    assert retry.idempotency_key != f"idem_{retry.run_id}"


def test_default_idempotency_key_changes_when_intent_material_changes() -> None:
    base = intent_idempotency_key(
        task_id="task-intent-2",
        metadata={"task_content_hash": "sha256:content-a", "origin_event_id": "evt-2"},
    )
    changed_content = intent_idempotency_key(
        task_id="task-intent-2",
        metadata={"task_content_hash": "sha256:content-b", "origin_event_id": "evt-2"},
    )
    changed_origin = intent_idempotency_key(
        task_id="task-intent-2",
        metadata={"task_content_hash": "sha256:content-a", "origin_event_id": "evt-3"},
    )
    changed_task = intent_idempotency_key(
        task_id="task-intent-3",
        metadata={"task_content_hash": "sha256:content-a", "origin_event_id": "evt-2"},
    )

    assert base != changed_content
    assert base != changed_origin
    assert base != changed_task


def test_intent_idempotency_helper_is_exported_from_spine_package() -> None:
    assert exported_intent_idempotency_key(task_id="task-export") == intent_idempotency_key(task_id="task-export")


def test_explicit_idempotency_key_is_preserved_for_existing_callers() -> None:
    identity = ExecutionIdentity.new(
        task_id="task-explicit",
        run_id="run-explicit-a",
        claim_id="claim-explicit-a",
        idempotency_key="idem-explicit-preserved",
        metadata={"task_content_hash": "sha256:ignored"},
    )

    assert identity.idempotency_key == "idem-explicit-preserved"
