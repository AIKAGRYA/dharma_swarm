"""Security and composition contracts for the SADHANA JSON read model."""

from __future__ import annotations

import ast
import asyncio
import copy
import hashlib
import json
import os
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import api.main as api_main
import api.mission_snapshot_provider as provider_module
import api.mission_snapshot_validation as validation_module
from api.mission_snapshot_provider import (
    CAMPAIGN_PROJECTION_SCHEMA_VERSION,
    ImmutableCampaignSnapshotProvider,
    MissionSnapshotConfigurationError,
    MissionSnapshotProviderConfig,
    MissionSnapshotReadError,
    mission_snapshot_provider_from_environment,
)
from api.routers.control_surface import router as control_surface_router


MISSION_ID = "sadhana-10-20260823"
CONFIG_DIGEST = "sha256:" + "a" * 64
NOW = datetime(2026, 8, 23, 3, 0, tzinfo=timezone.utc)


def _payload(
    *, generation: int = 3, cycle_sequence: int = 7, now: datetime = NOW
) -> dict[str, Any]:
    latest = now - timedelta(seconds=5)
    payload: dict[str, Any] = {
        "projection_schema_version": CAMPAIGN_PROJECTION_SCHEMA_VERSION,
        "projection_kind": "derived_read_model",
        "canonical_state_copied": False,
        "mission_id": MISSION_ID,
        "session_id": f"mission_campaign:{MISSION_ID}",
        "config_digest": CONFIG_DIGEST,
        "generation": generation,
        "cycle_sequence": cycle_sequence,
        "freshness_seconds": 30.0,
        "campaign_status": "active",
        "supervisor_state": "running",
        "writer_lock_held": True,
        "latest_cycle_at": latest.isoformat(),
        "observed_at": (now - timedelta(seconds=2)).isoformat(),
        "published_at": (now - timedelta(seconds=1)).isoformat(),
        "fresh_until": (latest + timedelta(seconds=30)).isoformat(),
        "transport_state": "unobserved",
        "model_execution_state": "unobserved",
        "acceptance_state": "unobserved",
        "owner_executions": [],
        "candidate_task_ids": [],
        "accepted_task_ids": [],
        "rejected_task_ids": [],
        "conflicting_acceptance_task_ids": [],
        "invalid_acceptance_receipts": 0,
        "authority": "TaskBoard+RuntimeStateStore+owner execution projection",
        "proves_semantic_acceptance": False,
        "mission_snapshot": {
            "mission": {
                "mission_id": MISSION_ID,
                "session_id": f"mission:{MISSION_ID}",
                "title": "SADHANA-10",
                "goal": "Ten evidence-backed goals",
                "operator_id": "operator",
                "status": "active",
                "metadata": {},
                "created_at": (now - timedelta(hours=1)).isoformat(),
                "updated_at": (now - timedelta(seconds=10)).isoformat(),
            },
            "tasks": [],
            "attempts": [],
            "leases": [],
            "receipts": [],
            "reconciliation": "coherent",
            "observed_at": (now - timedelta(seconds=10)).isoformat(),
            "authority": "TaskBoard+RuntimeStateStore",
            "proves_executor_liveness": False,
        },
    }
    payload["projection_content_digest"] = provider_module._canonical_digest(payload)
    return payload


def _task_row(*, mission_id: str = MISSION_ID) -> dict[str, Any]:
    return {
        "task_id": "task-one",
        "mission_id": mission_id,
        "title": "Task one",
        "description": "Do useful work",
        "status": "pending",
        "priority": "high",
        "assigned_to": "",
        "result": "",
        "metadata": {},
        "created_at": NOW.isoformat(),
        "updated_at": NOW.isoformat(),
    }


def _attempt_row(
    *, mission_id: str = MISSION_ID, session_id: str | None = None
) -> dict[str, Any]:
    return {
        "attempt_id": "attempt-one",
        "mission_id": mission_id,
        "session_id": session_id or f"mission:{mission_id}",
        "task_id": "task-one",
        "claim_id": "claim-one",
        "assigned_to": "agent-one",
        "assigned_by": "supervisor",
        "status": "succeeded",
        "failure_code": "",
        "idempotency_key": "attempt-key",
        "metadata": {},
        "started_at": NOW.isoformat(),
        "completed_at": NOW.isoformat(),
    }


def _receipt_row(*, mission_id: str = MISSION_ID) -> dict[str, Any]:
    return {
        "receipt_id": "receipt-one",
        "mission_id": mission_id,
        "task_id": "task-one",
        "attempt_id": "attempt-one",
        "agent_id": "agent-one",
        "receipt_type": "mission_attempt_terminal",
        "status": "succeeded",
        "idempotency_key": "receipt-key",
        "payload": {},
        "created_at": NOW.isoformat(),
    }


def _stable_id(prefix: str, *parts: str) -> str:
    encoded = "\x1f".join(parts).encode("utf-8")
    return f"{prefix}_{hashlib.sha256(encoded).hexdigest()[:24]}"


def _owner_execution(
    task: dict[str, Any],
    *,
    observed_at: datetime | None = None,
) -> dict[str, Any]:
    task_id = str(task["task_id"])
    dispatch_key = "default"
    run_id = _stable_id("owner_run", MISSION_ID, task_id, dispatch_key)
    idempotency_key = _stable_id(
        "owner_dispatch", MISSION_ID, task_id, dispatch_key
    )
    task["status"] = "completed"
    task["assigned_to"] = "agent-one"
    task["result"] = "Useful checked result"
    task["metadata"] = {
        "mission_control_owner_execution": {
            "schema_version": "dharma.mission_control.owner_execution.v1",
            "backend": "orchestrator",
            "mission_id": MISSION_ID,
            "task_id": task_id,
            "dispatch_key": dispatch_key,
            "run_id": run_id,
            "idempotency_key": idempotency_key,
        },
        "runtime_run_id": run_id,
        "run_id": run_id,
        "idempotency_key": idempotency_key,
    }
    return {
        "ref": {
            "backend": "orchestrator",
            "mission_id": MISSION_ID,
            "task_id": task_id,
            "dispatch_key": dispatch_key,
            "run_id": run_id,
            "claim_id": "claim-one",
            "agent_id": "agent-one",
            "idempotency_key": idempotency_key,
            "owner_session_id": "orchestrator-session-one",
        },
        "task_status": "completed",
        "run_status": "completed",
        "claim_status": "completed",
        "stale": False,
        "receipt_ids": ["receipt-owner-one"],
        "terminal": True,
        "succeeded": True,
        "result": "Useful checked result",
        "failure_code": "",
        "observed_at": (observed_at or NOW - timedelta(seconds=3)).isoformat(),
        "proves_executor_liveness": False,
    }


def _write(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, allow_nan=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    path.chmod(0o600)


def _config(path: Path, *, minimum_generation: int = 1) -> MissionSnapshotProviderConfig:
    return MissionSnapshotProviderConfig(
        path=path,
        mission_id=MISSION_ID,
        config_digest=CONFIG_DIGEST,
        minimum_generation=minimum_generation,
        max_age_seconds=60.0,
    )


def _provider(path: Path, *, minimum_generation: int = 1):
    return ImmutableCampaignSnapshotProvider(
        _config(path, minimum_generation=minimum_generation),
        now=lambda: NOW,
    )


def _environment(path: Path) -> dict[str, str]:
    return {
        "DHARMA_MISSION_SNAPSHOT_PATH": str(path),
        "DHARMA_MISSION_SNAPSHOT_MISSION_ID": MISSION_ID,
        "DHARMA_MISSION_SNAPSHOT_CONFIG_DIGEST": CONFIG_DIGEST,
        "DHARMA_MISSION_SNAPSHOT_MIN_GENERATION": "1",
        "DHARMA_MISSION_SNAPSHOT_MAX_AGE_SECONDS": "60",
    }


def _redigest(payload: dict[str, Any]) -> dict[str, Any]:
    updated = copy.deepcopy(payload)
    updated["projection_content_digest"] = provider_module._canonical_digest(updated)
    return updated


def _accepted_payload() -> dict[str, Any]:
    payload = _payload()
    task = _task_row()
    owner = _owner_execution(task)
    payload["mission_snapshot"]["tasks"].append(task)
    payload["owner_executions"].append(owner)
    payload["accepted_task_ids"] = [task["task_id"]]
    payload["acceptance_state"] = "accepted"
    payload["proves_semantic_acceptance"] = True
    return _redigest(payload)


def _isolate_api_lifespan(monkeypatch: pytest.MonkeyPatch) -> None:
    """Replace unrelated API subsystems without weakening lifespan composition."""

    class Traces:
        async def init(self) -> None:
            return None

    class Swarm:
        async def init(self) -> None:
            return None

    monkeypatch.setattr(api_main, "dashboard_api_mode", lambda: "local_dev")
    monkeypatch.setattr(api_main, "_publish_operator_pid", lambda *_: None)
    monkeypatch.setattr(api_main, "_clear_operator_pid", lambda *_: None)
    monkeypatch.setattr(api_main, "normalize_env_aliases", lambda: [])
    monkeypatch.setattr(api_main, "get_trace_store", lambda: Traces())
    monkeypatch.setattr(api_main, "get_swarm", lambda: Swarm())
    monkeypatch.setattr(api_main, "_initialize_boardstore_shadow", lambda *_: None)
    monkeypatch.setattr(api_main, "_initialize_node_gateway", lambda: None)
    monkeypatch.setattr(api_main, "_initialize_agent_directory", lambda *_: None)
    monkeypatch.setattr(api_main, "_log_auth_mode", lambda: None)
    import dharma_swarm.ontology_runtime as ontology_runtime

    monkeypatch.setattr(ontology_runtime, "get_shared_registry", lambda: object())


def test_environment_requires_all_or_none_and_canonical_values(tmp_path: Path) -> None:
    assert mission_snapshot_provider_from_environment({}) is None
    with pytest.raises(MissionSnapshotConfigurationError, match="partial"):
        mission_snapshot_provider_from_environment(
            {"DHARMA_MISSION_SNAPSHOT_PATH": str(tmp_path / "status.json")}
        )
    values = _environment(tmp_path / "status.json")
    values["DHARMA_MISSION_SNAPSHOT_MIN_GENERATION"] = "01"
    with pytest.raises(MissionSnapshotConfigurationError, match="canonical"):
        mission_snapshot_provider_from_environment(values)
    values = _environment(tmp_path / "status.json")
    values["DHARMA_MISSION_SNAPSHOT_CONFIG_DIGEST"] = "a" * 64
    with pytest.raises(MissionSnapshotConfigurationError, match="canonical sha256"):
        mission_snapshot_provider_from_environment(values)
    for noncanonical in (" 60", "+60", "060", "6e1"):
        values = _environment(tmp_path / "status.json")
        values["DHARMA_MISSION_SNAPSHOT_MAX_AGE_SECONDS"] = noncanonical
        with pytest.raises(MissionSnapshotConfigurationError, match="canonical"):
            mission_snapshot_provider_from_environment(values)
    for invalid_id in (
        "mission/child",
        "mission:child",
        "mission with space",
        "~campaign",
        ".campaign",
        "_campaign",
        "-campaign",
        "a~b",
        "x" * 201,
    ):
        values = _environment(tmp_path / "status.json")
        values["DHARMA_MISSION_SNAPSHOT_MISSION_ID"] = invalid_id
        with pytest.raises(MissionSnapshotConfigurationError, match="identifier"):
            mission_snapshot_provider_from_environment(values)
    for valid_id in ("campaign", "a.campaign", "a_campaign", "a-campaign", "a" * 200):
        values = _environment(tmp_path / "status.json")
        values["DHARMA_MISSION_SNAPSHOT_MISSION_ID"] = valid_id
        assert mission_snapshot_provider_from_environment(values) is not None


@pytest.mark.asyncio
async def test_valid_projection_returns_only_a_fresh_nested_copy(tmp_path: Path) -> None:
    path = tmp_path / "campaign" / "status.json"
    payload = _payload()
    payload["mission_snapshot"]["tasks"].append(_task_row())
    payload = _redigest(payload)
    _write(path, payload)
    provider = _provider(path)

    first = await provider.get_snapshot(MISSION_ID)
    assert first is not None
    assert first["mission"]["mission_id"] == MISSION_ID
    assert "projection_content_digest" not in first
    first["tasks"][0]["task_id"] = "mutated-client-copy"
    second = await provider.get_snapshot(MISSION_ID)
    assert second is not None
    assert second["tasks"][0]["task_id"] == "task-one"
    assert provider.runtime_projection_mode == "unavailable"


@pytest.mark.asyncio
async def test_owner_execution_and_acceptance_projection_are_typed_and_copied(
    tmp_path: Path,
) -> None:
    path = tmp_path / "campaign" / "status.json"
    _write(path, _accepted_payload())
    provider = _provider(path)

    first = await provider.get_snapshot(MISSION_ID)
    assert first is not None
    evidence = first["campaign_evidence"]
    assert evidence == {
        "schema_version": "dharma.mission_control.campaign_evidence.v1",
        "authority": "TaskBoard+RuntimeStateStore+owner execution projection",
        "observed_at": (NOW - timedelta(seconds=2)).isoformat(),
        "owner_executions": [_accepted_payload()["owner_executions"][0]],
        "candidate_task_ids": [],
        "accepted_task_ids": ["task-one"],
        "rejected_task_ids": [],
        "conflicting_acceptance_task_ids": [],
        "invalid_acceptance_receipts": 0,
        "acceptance_state": "accepted",
        "proves_executor_liveness": False,
        "proves_semantic_acceptance": True,
    }
    evidence["accepted_task_ids"].append("client-forgery")
    evidence["owner_executions"][0]["ref"]["agent_id"] = "client-forgery"
    second = await provider.get_snapshot(MISSION_ID)
    assert second is not None
    assert second["campaign_evidence"]["accepted_task_ids"] == ["task-one"]
    assert (
        second["campaign_evidence"]["owner_executions"][0]["ref"]["agent_id"]
        == "agent-one"
    )
    assert provider.runtime_projection_mode == "unavailable"


@pytest.mark.asyncio
async def test_owner_execution_mutations_fail_closed(tmp_path: Path) -> None:
    path = tmp_path / "campaign" / "status.json"

    def wrong_run(value: dict[str, Any]) -> None:
        value["owner_executions"][0]["ref"]["run_id"] = "owner_run_forged"

    def foreign_agent_stamp(value: dict[str, Any]) -> None:
        value["mission_snapshot"]["tasks"][0]["metadata"][
            "mission_control_owner_execution"
        ]["run_id"] = "owner_run_forged"

    def duplicate_owner(value: dict[str, Any]) -> None:
        value["owner_executions"].append(copy.deepcopy(value["owner_executions"][0]))

    def false_terminal(value: dict[str, Any]) -> None:
        value["owner_executions"][0]["terminal"] = False

    def claimed_liveness(value: dict[str, Any]) -> None:
        value["owner_executions"][0]["proves_executor_liveness"] = True

    def stale_observation(value: dict[str, Any]) -> None:
        value["owner_executions"][0]["observed_at"] = (
            NOW - timedelta(minutes=5)
        ).isoformat()

    def foreign_field(value: dict[str, Any]) -> None:
        value["owner_executions"][0]["self_certified"] = True

    for mutate in (
        wrong_run,
        foreign_agent_stamp,
        duplicate_owner,
        false_terminal,
        claimed_liveness,
        stale_observation,
        foreign_field,
    ):
        payload = _accepted_payload()
        mutate(payload)
        _write(path, _redigest(payload))
        with pytest.raises(MissionSnapshotReadError, match="owner"):
            await _provider(path).get_snapshot(MISSION_ID)


@pytest.mark.asyncio
async def test_acceptance_projection_semantic_claims_fail_closed(
    tmp_path: Path,
) -> None:
    path = tmp_path / "campaign" / "status.json"

    def unknown_accepted_task(value: dict[str, Any]) -> None:
        value["accepted_task_ids"] = ["unknown-task"]

    def overlapping_verdict(value: dict[str, Any]) -> None:
        value["rejected_task_ids"] = ["task-one"]

    def false_state(value: dict[str, Any]) -> None:
        value["acceptance_state"] = "candidate_only"

    def false_promotion(value: dict[str, Any]) -> None:
        value["proves_semantic_acceptance"] = False

    def duplicate_verdict(value: dict[str, Any]) -> None:
        value["accepted_task_ids"] = ["task-one", "task-one"]

    def boolean_invalid_count(value: dict[str, Any]) -> None:
        value["invalid_acceptance_receipts"] = True

    for mutate in (
        unknown_accepted_task,
        overlapping_verdict,
        false_state,
        false_promotion,
        duplicate_verdict,
        boolean_invalid_count,
    ):
        payload = _accepted_payload()
        mutate(payload)
        _write(path, _redigest(payload))
        with pytest.raises(MissionSnapshotReadError, match="accept|semantic"):
            await _provider(path).get_snapshot(MISSION_ID)


@pytest.mark.asyncio
async def test_foreign_request_performs_no_file_io(tmp_path: Path) -> None:
    missing = tmp_path / "does-not-exist.json"
    assert await _provider(missing).get_snapshot("foreign-mission") is None


@pytest.mark.asyncio
async def test_cycle_position_allows_envelope_rewrite_but_rejects_replay_or_equivocation(
    tmp_path: Path,
) -> None:
    path = tmp_path / "campaign" / "status.json"
    first = _payload(generation=3)
    first["mission_snapshot"]["mission"]["title"] = "first"
    _write(path, _redigest(first))
    provider = _provider(path)
    assert (await provider.get_snapshot(MISSION_ID))["mission"]["title"] == "first"  # type: ignore[index]

    terminal = copy.deepcopy(first)
    terminal["supervisor_state"] = "not_running"
    terminal["writer_lock_held"] = False
    _write(path, _redigest(terminal))
    assert (await provider.get_snapshot(MISSION_ID))["mission"]["title"] == "first"  # type: ignore[index]

    equivocation = copy.deepcopy(first)
    equivocation["mission_snapshot"]["mission"]["title"] = "equivocated"
    _write(path, _redigest(equivocation))
    with pytest.raises(MissionSnapshotReadError, match="equivocated"):
        await provider.get_snapshot(MISSION_ID)

    newer = _payload(generation=3, cycle_sequence=8)
    newer["mission_snapshot"]["mission"]["title"] = "newer"
    _write(path, _redigest(newer))
    assert (await provider.get_snapshot(MISSION_ID))["mission"]["title"] == "newer"  # type: ignore[index]
    _write(path, _payload(generation=4, cycle_sequence=1))
    assert await provider.get_snapshot(MISSION_ID) is not None
    _write(path, _payload(generation=3, cycle_sequence=99))
    with pytest.raises(MissionSnapshotReadError, match="moved backwards"):
        await provider.get_snapshot(MISSION_ID)


@pytest.mark.asyncio
async def test_invalid_higher_generation_does_not_poison_high_water(tmp_path: Path) -> None:
    path = tmp_path / "campaign" / "status.json"
    _write(path, _payload(generation=3))
    provider = _provider(path)
    await provider.get_snapshot(MISSION_ID)
    invalid = _payload(generation=99)
    invalid["mission_id"] = "forged"
    _write(path, _redigest(invalid))
    with pytest.raises(MissionSnapshotReadError, match="identity"):
        await provider.get_snapshot(MISSION_ID)
    _write(path, _payload(generation=4))
    assert await provider.get_snapshot(MISSION_ID) is not None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("projection_schema_version", "foreign", "schema"),
        ("projection_kind", "canonical_ledger", "schema"),
        ("canonical_state_copied", True, "schema"),
        ("mission_id", "foreign", "identity"),
        ("session_id", "mission_campaign:foreign", "identity"),
        ("config_digest", "sha256:" + "b" * 64, "identity"),
        ("generation", True, "generation"),
        ("cycle_sequence", -1, "cycle sequence"),
    ],
)
async def test_recomputed_self_hash_cannot_override_exact_bindings(
    tmp_path: Path,
    field: str,
    value: Any,
    message: str,
) -> None:
    path = tmp_path / "campaign" / "status.json"
    payload = _payload()
    payload[field] = value
    _write(path, _redigest(payload))
    with pytest.raises(MissionSnapshotReadError, match=message):
        await _provider(path).get_snapshot(MISSION_ID)


@pytest.mark.asyncio
async def test_recomputed_hash_cannot_promote_nested_claims_or_foreign_tasks(
    tmp_path: Path,
) -> None:
    path = tmp_path / "campaign" / "status.json"
    mutations = (
        lambda value: value["mission_snapshot"].__setitem__(
            "authority", "self-asserted-supervisor"
        ),
        lambda value: value["mission_snapshot"].__setitem__(
            "proves_executor_liveness", True
        ),
        lambda value: value["mission_snapshot"].__setitem__(
            "reconciliation", "coherent-because-i-say-so"
        ),
        lambda value: value["mission_snapshot"]["tasks"].append(
            _task_row(mission_id="other-mission")
        ),
        lambda value: value["mission_snapshot"]["tasks"].append("not-an-object"),
        lambda value: value["mission_snapshot"]["tasks"].append(
            _task_row() | {"proves_model_execution": True}
        ),
        lambda value: value["mission_snapshot"]["tasks"].append(
            {key: item for key, item in _task_row().items() if key != "mission_id"}
        ),
        lambda value: value["mission_snapshot"]["tasks"].append(
            _task_row() | {"status": True}
        ),
        lambda value: value["mission_snapshot"].__setitem__(
            "proves_model_execution", True
        ),
    )
    for mutate in mutations:
        payload = _payload()
        mutate(payload)
        _write(path, _redigest(payload))
        with pytest.raises(MissionSnapshotReadError, match="nested MissionSnapshot"):
            await _provider(path).get_snapshot(MISSION_ID)


@pytest.mark.asyncio
async def test_foreign_runtime_view_requires_and_preserves_diagnostic_state(
    tmp_path: Path,
) -> None:
    path = tmp_path / "campaign" / "status.json"
    payload = _payload()
    payload["mission_snapshot"]["attempts"].append(
        _attempt_row(
            mission_id="other-mission", session_id="mission:other-mission"
        )
    )
    _write(path, _redigest(payload))
    with pytest.raises(MissionSnapshotReadError, match="not reconciled"):
        await _provider(path).get_snapshot(MISSION_ID)

    payload["mission_snapshot"]["reconciliation"] = "foreign_runtime_record"
    _write(path, _redigest(payload))
    snapshot = await _provider(path).get_snapshot(MISSION_ID)
    assert snapshot is not None
    assert snapshot["reconciliation"] == "foreign_runtime_record"


@pytest.mark.asyncio
async def test_foreign_receipt_is_never_a_publishable_campaign_snapshot(
    tmp_path: Path,
) -> None:
    path = tmp_path / "campaign" / "status.json"
    payload = _payload()
    payload["mission_snapshot"]["receipts"].append(
        _receipt_row(mission_id="other-mission")
    )
    for reconciliation in (
        "coherent",
        "foreign_runtime_record",
        "conflicting_terminal_evidence",
    ):
        payload["mission_snapshot"]["reconciliation"] = reconciliation
        _write(path, _redigest(payload))
        with pytest.raises(MissionSnapshotReadError, match="receipt is foreign"):
            await _provider(path).get_snapshot(MISSION_ID)


@pytest.mark.asyncio
async def test_zero_cycle_is_observable_but_cannot_satisfy_startup_admission(
    tmp_path: Path,
) -> None:
    path = tmp_path / "campaign" / "status.json"
    payload = _payload(cycle_sequence=0)
    payload["latest_cycle_at"] = None
    payload["fresh_until"] = None
    _write(path, _redigest(payload))
    provider = _provider(path)

    snapshot = await provider.get_snapshot(MISSION_ID)
    assert snapshot is not None
    with pytest.raises(MissionSnapshotReadError, match="no completed durable cycle"):
        await provider.admit()


@pytest.mark.asyncio
async def test_secure_read_and_validation_are_both_off_event_loop(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "campaign" / "status.json"
    _write(path, _payload())
    provider = _provider(path)
    event_loop_thread = threading.get_ident()
    validation_threads: list[int] = []
    original = provider._validate

    def observed_validation(content: bytes):
        validation_threads.append(threading.get_ident())
        return original(content)

    monkeypatch.setattr(provider, "_validate", observed_validation)
    assert await provider.get_snapshot(MISSION_ID) is not None
    assert validation_threads and validation_threads[0] != event_loop_thread


@pytest.mark.asyncio
async def test_cancellation_drains_validator_before_next_request(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "campaign" / "status.json"
    _write(path, _payload())
    provider = _provider(path)
    entered = threading.Event()
    release = threading.Event()
    state_lock = threading.Lock()
    active = 0
    peak = 0
    original = provider._read_and_validate

    def blocked_validation():
        nonlocal active, peak
        with state_lock:
            active += 1
            peak = max(peak, active)
        entered.set()
        assert release.wait(timeout=5)
        try:
            return original()
        finally:
            with state_lock:
                active -= 1

    monkeypatch.setattr(provider, "_read_and_validate", blocked_validation)
    first = asyncio.create_task(provider.get_snapshot(MISSION_ID))
    assert await asyncio.to_thread(entered.wait, 2)
    first.cancel()
    second = asyncio.create_task(provider.get_snapshot(MISSION_ID))
    await asyncio.sleep(0.05)
    assert peak == 1
    assert second.done() is False
    first.cancel()
    await asyncio.sleep(0.05)
    assert peak == 1
    assert second.done() is False

    release.set()
    with pytest.raises(asyncio.CancelledError):
        await first
    assert await second is not None
    assert peak == 1


@pytest.mark.asyncio
async def test_raw_tamper_and_duplicate_or_nonfinite_json_fail(tmp_path: Path) -> None:
    path = tmp_path / "campaign" / "status.json"
    payload = _payload()
    _write(path, payload)
    path.write_text(path.read_text().replace(MISSION_ID, "tampered", 1), encoding="utf-8")
    path.chmod(0o600)
    with pytest.raises(MissionSnapshotReadError, match="digest"):
        await _provider(path).get_snapshot(MISSION_ID)

    path.write_text('{"duplicate":1,"duplicate":2}', encoding="utf-8")
    path.chmod(0o600)
    with pytest.raises(MissionSnapshotReadError, match="duplicate"):
        await _provider(path).get_snapshot(MISSION_ID)

    path.write_text('{"value":NaN}', encoding="utf-8")
    path.chmod(0o600)
    with pytest.raises(MissionSnapshotReadError, match="non-finite"):
        await _provider(path).get_snapshot(MISSION_ID)


@pytest.mark.asyncio
async def test_stale_naive_future_and_inconsistent_windows_fail(tmp_path: Path) -> None:
    path = tmp_path / "campaign" / "status.json"
    stale = _payload(now=NOW - timedelta(minutes=5))
    _write(path, stale)
    with pytest.raises(MissionSnapshotReadError, match="stale"):
        await _provider(path).get_snapshot(MISSION_ID)

    naive = _payload()
    naive["published_at"] = "2026-08-23T02:59:59"
    _write(path, _redigest(naive))
    with pytest.raises(MissionSnapshotReadError, match="timezone-aware"):
        await _provider(path).get_snapshot(MISSION_ID)

    future = _payload()
    future["observed_at"] = (NOW + timedelta(minutes=1)).isoformat()
    _write(path, _redigest(future))
    with pytest.raises(MissionSnapshotReadError, match="future"):
        await _provider(path).get_snapshot(MISSION_ID)

    inconsistent = _payload()
    inconsistent["fresh_until"] = (NOW + timedelta(minutes=5)).isoformat()
    _write(path, _redigest(inconsistent))
    with pytest.raises(MissionSnapshotReadError, match="ordering"):
        await _provider(path).get_snapshot(MISSION_ID)

    old_nested_snapshot = _payload()
    old_nested_snapshot["mission_snapshot"]["observed_at"] = (
        NOW - timedelta(minutes=5)
    ).isoformat()
    _write(path, _redigest(old_nested_snapshot))
    with pytest.raises(MissionSnapshotReadError, match="stale"):
        await _provider(path).get_snapshot(MISSION_ID)


@pytest.mark.asyncio
async def test_file_type_mode_and_symlink_admission_fail_closed(tmp_path: Path) -> None:
    path = tmp_path / "campaign" / "status.json"
    _write(path, _payload())
    path.chmod(0o644)
    with pytest.raises(MissionSnapshotReadError, match="private regular"):
        await _provider(path).get_snapshot(MISSION_ID)

    path.chmod(0o600)
    os.truncate(path, provider_module._MAX_PROJECTION_BYTES + 1)
    with pytest.raises(MissionSnapshotReadError, match="bounded private regular"):
        await _provider(path).get_snapshot(MISSION_ID)

    _write(path, _payload())
    target = tmp_path / "target.json"
    _write(target, _payload())
    path.unlink()
    path.symlink_to(target)
    with pytest.raises(MissionSnapshotReadError, match="private regular"):
        await _provider(path).get_snapshot(MISSION_ID)

    path.unlink()
    os.mkfifo(path, mode=0o600)
    with pytest.raises(MissionSnapshotReadError, match="private regular"):
        await _provider(path).get_snapshot(MISSION_ID)

    path.unlink()
    real_parent = tmp_path / "real-parent"
    real_path = real_parent / "status.json"
    _write(real_path, _payload())
    linked_parent = tmp_path / "linked-parent"
    linked_parent.symlink_to(real_parent, target_is_directory=True)
    with pytest.raises(MissionSnapshotReadError, match="directory"):
        await _provider(linked_parent / "status.json").get_snapshot(MISSION_ID)

    hardlink = real_parent / "status-hardlink.json"
    os.link(real_path, hardlink)
    with pytest.raises(MissionSnapshotReadError, match="private regular"):
        await _provider(real_path).get_snapshot(MISSION_ID)

    unsafe_parent = tmp_path / "unsafe-parent"
    unsafe_path = unsafe_parent / "status.json"
    _write(unsafe_path, _payload())
    unsafe_parent.chmod(0o777)
    with pytest.raises(MissionSnapshotReadError, match="private custody"):
        await _provider(unsafe_path).get_snapshot(MISSION_ID)


@pytest.mark.asyncio
async def test_endpoint_observes_snapshot_but_never_enables_runtime_db_reads(
    tmp_path: Path,
) -> None:
    path = tmp_path / "campaign" / "status.json"
    _write(path, _payload())
    provider = _provider(path)
    app = FastAPI()
    app.state.mission_snapshot_provider = provider
    app.include_router(control_surface_router)

    response = TestClient(app).get(
        f"/api/control-surface/missions/{MISSION_ID}/snapshot"
    )

    assert response.status_code == 200
    projection = response.json()["data"]
    assert projection["state"] == "observed"
    assert projection["snapshot"]["mission"]["mission_id"] == MISSION_ID
    assert projection["runtime_projection_ready"] is False
    assert projection["runtime_projection_mode"] == "unavailable"


def test_provider_modules_have_no_application_or_database_imports() -> None:
    paths = [
        Path(module.__file__ or "")
        for module in (provider_module, validation_module)
    ]
    for path in paths:
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source)
        imported = {
            alias.name
            for node in ast.walk(tree)
            if isinstance(node, ast.Import)
            for alias in node.names
        }
        imported.update(
            node.module or ""
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom)
        )
        assert not any(
            name.startswith(("dharma_swarm", "sqlite3", "aiosqlite"))
            for name in imported
        )
        for forbidden in (
            "MissionControl(",
            "TaskBoard(",
            "RuntimeStateStore(",
            "sqlite3.connect",
            "aiosqlite.connect",
        ):
            assert forbidden not in source


@pytest.mark.asyncio
async def test_invalid_configured_source_fails_before_existing_api_writes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class InvalidProvider:
        async def admit(self) -> None:
            raise MissionSnapshotReadError("invalid configured source")

    published: list[bool] = []
    monkeypatch.setattr(
        provider_module,
        "mission_snapshot_provider_from_environment",
        lambda: InvalidProvider(),
    )
    monkeypatch.setattr(api_main, "dashboard_api_mode", lambda: "local_dev")
    monkeypatch.setattr(api_main, "_publish_operator_pid", lambda *_: published.append(True))
    app = FastAPI()

    with pytest.raises(MissionSnapshotReadError, match="invalid configured"):
        async with api_main.lifespan(app):
            pytest.fail("invalid projection must prevent lifespan entry")
    assert published == []


@pytest.mark.asyncio
async def test_valid_provider_is_identity_safely_installed_and_removed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class Provider:
        admitted = False

        async def admit(self) -> None:
            self.admitted = True

    provider = Provider()
    monkeypatch.setattr(
        provider_module,
        "mission_snapshot_provider_from_environment",
        lambda: provider,
    )
    _isolate_api_lifespan(monkeypatch)
    app = FastAPI()

    async with api_main.lifespan(app):
        assert provider.admitted is True
        assert app.state.mission_snapshot_provider is provider
    assert getattr(app.state, "mission_snapshot_provider", None) is None


@pytest.mark.asyncio
async def test_no_configuration_preserves_an_existing_injected_provider(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    existing = object()
    app = FastAPI()
    app.state.mission_snapshot_provider = existing
    monkeypatch.setattr(
        provider_module,
        "mission_snapshot_provider_from_environment",
        lambda: None,
    )
    _isolate_api_lifespan(monkeypatch)

    async with api_main.lifespan(app):
        assert app.state.mission_snapshot_provider is existing
    assert app.state.mission_snapshot_provider is existing
