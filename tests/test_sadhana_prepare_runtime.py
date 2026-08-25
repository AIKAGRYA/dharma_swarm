from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from api.mission_snapshot_validation import canonical_digest
from dharma_swarm import mission_control_bootstrap as bootstrap
from dharma_swarm import mission_control_service as campaign_service
from dharma_swarm.mission_control_roster import (
    CampaignAgentRoster,
    CampaignAgentSeat,
    CampaignRosterError,
)
from dharma_swarm.mission_control_contract import MissionControlError
from dharma_swarm.mission_control_runtime_manifests import RuntimeManifestPins
from dharma_swarm.models import AgentRole, ProviderType
from dharma_swarm.task_board import TaskBoard
from scripts.runtime import sadhana_prepare_runtime as preparation
from tests.test_mission_control_bootstrap import _observed_source, _pinned_portfolio


class InjectedCrash(RuntimeError):
    pass


def _roster(campaign_id: str, campaign_deadline: str) -> CampaignAgentRoster:
    now = datetime.now(timezone.utc)
    seats = tuple(
        CampaignAgentSeat(
            name=f"sadhana-seat-{index}",
            role=AgentRole.VALIDATOR if index == 6 else AgentRole.CODER,
            provider=ProviderType.OLLAMA,
            model=f"model-{index}:cloud",
            family=f"family-{index}",
            thread=f"thread-{index}",
            system_prompt=f"Bounded seat {index}.",
        )
        for index in range(7)
    )
    return CampaignAgentRoster(
        campaign_id=campaign_id,
        objective_sha256="a" * 64,
        activation_at=now - timedelta(minutes=1),
        expires_at=datetime.fromisoformat(campaign_deadline),
        catalog_observed_at=now,
        catalog_models=tuple(f"model-{index}" for index in range(7)),
        seats=seats,
        manifest_sha256="b" * 64,
    )


def _inputs(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    state_name: str,
) -> preparation.RuntimePreparationInputs:
    portfolio, contract_path = _pinned_portfolio(tmp_path, monkeypatch)
    source = tmp_path / "observed-inputs.source.json"
    if not source.exists():
        _observed_source(source, portfolio)
    roster = _roster(portfolio.campaign_id, portfolio.campaign_deadline)
    monkeypatch.setattr(
        preparation,
        "load_campaign_agent_roster",
        lambda *args, **kwargs: roster,
    )
    release_sha = "93b33eeb78fce133ef0e4e1ad6d81099d8b80344"
    release_root = tmp_path / "opt" / "dharma-sadhana" / "releases" / release_sha
    release_root.mkdir(parents=True, exist_ok=True)
    release_input_set_digest = "f" * 64
    release_admission = {
        "schema_version": "dharma.sadhana.staged_release_admission.v1",
        "release_sha": release_sha,
        "release_root": str(release_root),
        "tracked_source_manifest_digest": "1" * 64,
        "tracked_source_manifest_sha256": "2" * 64,
        "tracked_entry_count": 200,
        "tracked_bytes": 1_000_000,
        "isolated_build_receipt_sha256": "3" * 64,
        "release_input_set_digest": release_input_set_digest,
        "git_metadata_present": False,
        "frozen_tree": True,
        "candidate_code_executed_as_root": False,
    }
    release_admission["receipt_digest"] = preparation._digest(release_admission)
    release_admission_path = tmp_path / "staged-release-admission.v1.json"
    release_admission_path.write_bytes(preparation._canonical_bytes(release_admission))
    release_admission_path.chmod(0o600)
    runtime_root = tmp_path / state_name
    runtime_root.mkdir(mode=0o700, exist_ok=True)
    state_dir = runtime_root / "state"
    return preparation.RuntimePreparationInputs(
        release_root=release_root,
        release_sha=release_sha,
        release_input_set_digest=release_input_set_digest,
        release_admission_receipt=release_admission_path,
        contracts=contract_path,
        observed_source=source,
        roster=tmp_path / "agent-roster.json",
        roster_sha256=roster.manifest_sha256,
        objective_sha256=roster.objective_sha256,
        state_dir=state_dir,
        output_root=state_dir / "prepared-runtime-manifests",
        projection_path=(
            runtime_root / "projection-source" / preparation.INITIAL_PROJECTION_NAME
        ),
        operator_id="operator",
        verifier_seat="sadhana-seat-6",
        pins=RuntimeManifestPins(
            evaluator_path=tmp_path / "held-out" / "g10-evaluator.py",
            evaluator_sha256="sha256:" + "1" * 64,
            policy_path=tmp_path / "held-out" / "g10-policy.json",
            policy_sha256="sha256:" + "2" * 64,
            operator_control_semantics_sha256="sha256:" + "3" * 64,
            operator_control_authority_binding_sha256="sha256:" + "4" * 64,
            deployment_authority_topology_sha256="sha256:" + "5" * 64,
            deployment_authority_credential_clarification_sha256=("sha256:" + "6" * 64),
        ),
    )


def _bytes(
    inputs: preparation.RuntimePreparationInputs,
) -> tuple[dict[str, bytes], bytes]:
    manifests = {
        path.name: path.read_bytes() for path in sorted(inputs.output_root.iterdir())
    }
    receipt = (
        inputs.state_dir / "receipts" / preparation.PREPARATION_RECEIPT_NAME
    ).read_bytes()
    return manifests, receipt


def _projection(inputs: preparation.RuntimePreparationInputs) -> dict[str, object]:
    return json.loads(inputs.projection_path.read_text(encoding="utf-8"))


def _rewrite_projection(
    inputs: preparation.RuntimePreparationInputs,
    payload: dict[str, object],
) -> bytes:
    payload["projection_content_digest"] = canonical_digest(payload)
    raw = preparation._canonical_bytes(payload)
    inputs.projection_path.write_bytes(raw)
    inputs.projection_path.chmod(0o600)
    return raw


async def _task_ids(inputs: preparation.RuntimePreparationInputs) -> set[str]:
    board = TaskBoard(inputs.state_dir / "db" / "tasks.db")
    await board.init_db()
    return {task.id for task in await board.list_tasks(limit=20)}


_LEGACY_EFFECT_AT = datetime(2026, 8, 25, tzinfo=timezone.utc)
_LEGACY_EFFECT_METADATA = {
    "legacy_no_identity_allowed": True,
    "runtime_spine_status": "legacy_no_identity",
}


def _insert_foreign_legacy_effect(
    runtime: preparation.RuntimeStateStore,
    effect_kind: str,
    *,
    suffix: str,
) -> tuple[str, str, dict[str, object]]:
    session_id = f"foreign-session-{suffix}"
    task_id = f"foreign-task-{suffix}"
    timestamp = _LEGACY_EFFECT_AT.isoformat()
    with sqlite3.connect(runtime.db_path) as db:
        if effect_kind == "claim":
            row_id = f"foreign-claim-{suffix}"
            db.execute(
                "INSERT INTO task_claims (claim_id, task_id, session_id, agent_id,"
                " status, claimed_at, metadata_json) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    row_id,
                    task_id,
                    session_id,
                    f"foreign-agent-{suffix}",
                    "running",
                    timestamp,
                    json.dumps(_LEGACY_EFFECT_METADATA, sort_keys=True),
                ),
            )
            semantic = {
                "claim_id": row_id,
                "task_id": task_id,
                "agent_id": f"foreign-agent-{suffix}",
                "status": "running",
                "session_id": session_id,
                "claimed_at": _LEGACY_EFFECT_AT,
                "acked_at": None,
                "heartbeat_at": None,
                "stale_after": None,
                "recovered_at": None,
                "retry_count": 0,
                "metadata": dict(_LEGACY_EFFECT_METADATA),
            }
            collection = "claims"
        elif effect_kind == "run":
            row_id = f"foreign-run-{suffix}"
            db.execute(
                "INSERT INTO delegation_runs (run_id, session_id, task_id, claim_id,"
                " assigned_to, status, started_at, metadata_json)"
                " VALUES (?, ?, ?, '', ?, ?, ?, ?)",
                (
                    row_id,
                    session_id,
                    task_id,
                    f"foreign-agent-{suffix}",
                    "running",
                    timestamp,
                    json.dumps(_LEGACY_EFFECT_METADATA, sort_keys=True),
                ),
            )
            semantic = {
                "run_id": row_id,
                "task_id": task_id,
                "assigned_to": f"foreign-agent-{suffix}",
                "status": "running",
                "session_id": session_id,
                "claim_id": "",
                "parent_run_id": "",
                "assigned_by": "",
                "requested_output": [],
                "current_artifact_id": "",
                "started_at": _LEGACY_EFFECT_AT,
                "completed_at": None,
                "failure_code": "",
                "metadata": dict(_LEGACY_EFFECT_METADATA),
            }
            collection = "runs"
        else:  # pragma: no cover - test helper misuse
            raise AssertionError(f"unsupported effect kind: {effect_kind}")
        db.commit()
    return collection, row_id, semantic


async def _semantic_effect_rows(
    runtime: preparation.RuntimeStateStore,
) -> dict[str, dict[str, dict[str, object]]]:
    claims = await runtime.list_task_claims(limit=10_000)
    runs = await runtime.list_delegation_runs(limit=10_000)
    return {
        "claims": {row.claim_id: asdict(row) for row in claims},
        "runs": {row.run_id: asdict(row) for row in runs},
    }


@pytest.mark.asyncio
@pytest.mark.parametrize("effect_kind", ("claim", "run"))
async def test_preexisting_foreign_legacy_effect_rejects_before_owner_creation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    effect_kind: str,
) -> None:
    inputs = _inputs(tmp_path, monkeypatch, state_name=f"foreign-{effect_kind}")
    runtime = preparation.RuntimeStateStore(
        inputs.state_dir / "state" / "runtime.db",
        include_memory_plane=False,
    )
    await runtime.init_db()
    collection, row_id, expected = _insert_foreign_legacy_effect(
        runtime,
        effect_kind,
        suffix=effect_kind,
    )
    before = await _semantic_effect_rows(runtime)
    assert before[collection][row_id] == expected

    owner_calls: list[str] = []

    def forbidden_board(*args: object, **kwargs: object) -> None:
        owner_calls.append("TaskBoard")
        raise AssertionError("TaskBoard must not be constructed")

    async def forbidden_bootstrap(*args: object, **kwargs: object) -> None:
        owner_calls.append("bootstrap")
        raise AssertionError("bootstrap must not be called")

    monkeypatch.setattr(preparation, "TaskBoard", forbidden_board)
    monkeypatch.setattr(
        preparation,
        "initialize_sadhana_campaign",
        forbidden_bootstrap,
    )

    with pytest.raises(MissionControlError, match="effect-free runtime state"):
        await preparation.prepare_runtime(inputs)

    assert owner_calls == []
    assert await _semantic_effect_rows(runtime) == before
    assert await runtime.list_runtime_receipts(limit=10_000) == []
    assert not (inputs.state_dir / "db").exists()
    assert not inputs.output_root.exists()
    assert not (inputs.state_dir / "preparation-scratch").exists()
    assert not (
        inputs.state_dir / "receipts" / preparation.PREPARATION_RECEIPT_NAME
    ).exists()


@pytest.mark.asyncio
async def test_effect_inserted_between_censuses_rejects_and_is_preserved(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    inputs = _inputs(tmp_path, monkeypatch, state_name="effect-race")
    inserted: list[tuple[str, str, dict[str, object]]] = []

    def inject(phase: str) -> None:
        if phase == "owners_initialized":
            runtime = preparation.RuntimeStateStore(
                inputs.state_dir / "state" / "runtime.db",
                include_memory_plane=False,
            )
            inserted.append(
                _insert_foreign_legacy_effect(runtime, "claim", suffix="race")
            )

    with pytest.raises(MissionControlError, match="crossed an effect boundary"):
        await preparation.prepare_runtime(inputs, checkpoint=inject)

    assert len(inserted) == 1
    collection, row_id, expected = inserted[0]
    runtime = preparation.RuntimeStateStore(
        inputs.state_dir / "state" / "runtime.db",
        include_memory_plane=False,
    )
    rows = await _semantic_effect_rows(runtime)
    assert rows[collection] == {row_id: expected}
    assert rows["runs"] == {}
    assert not (
        inputs.state_dir / "receipts" / preparation.PREPARATION_RECEIPT_NAME
    ).exists()


@pytest.mark.asyncio
async def test_every_phase_crash_replays_to_identical_prepared_no_effect_proof(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    phases = (
        "validated_inputs",
        "owners_initialized",
        "mission_bootstrapped",
        "observed_manifest",
        "held_out_manifest",
        "authority_manifest",
        "session_started",
        "session_prepared",
        "projection_published",
        "projection_validated",
        "receipt_written",
    )

    for index, target in enumerate(phases):
        inputs = _inputs(tmp_path, monkeypatch, state_name=f"failure-{index}")

        def crash(phase: str) -> None:
            if phase == target:
                raise InjectedCrash(target)

        with pytest.raises(InjectedCrash, match=target):
            await preparation.prepare_runtime(inputs, checkpoint=crash)
        partial_task_ids = (
            await _task_ids(inputs)
            if target not in {"validated_inputs", "owners_initialized"}
            else set()
        )
        replayed = await preparation.prepare_runtime(inputs)
        replayed_bytes = _bytes(inputs)
        second_replay = await preparation.prepare_runtime(inputs)

        assert second_replay == replayed
        assert _bytes(inputs) == replayed_bytes
        assert len(set(replayed["tasks"].values())) == 10
        if partial_task_ids:
            assert partial_task_ids == set(replayed["tasks"].values())
        assert replayed["proof"]["effect"] == preparation.NO_EFFECT
        assert replayed["proof"]["effect_counts"] == {
            kind: 0 for kind in preparation.EFFECT_KINDS
        }
        assert replayed["session"]["status"] == "paused"
        assert replayed["session"]["generation"] == 1
        assert (
            replayed["session"]["config_digest"]
            == replayed["proof"]["parameters"]["config_digest"]
        )
        parameters = replayed["proof"]["parameters"]
        assert parameters["release_input_set_digest"] == inputs.release_input_set_digest
        assert parameters["preparation_input_digest"] == preparation._digest(
            replayed["input_set"]
        )
        assert (
            parameters["release_input_set_digest"]
            != parameters["preparation_input_digest"]
        )
        assert parameters["manifest_set_digest"] == preparation._digest(
            replayed["manifests"]
        )
        assert parameters["session_generation"] == 1
        assert parameters["session_status"] == "paused"
        projection = _projection(inputs)
        assert projection["projection_schema_version"] == (
            preparation.CAMPAIGN_PROJECTION_SCHEMA_VERSION
        )
        assert projection["mission_id"] == bootstrap.EXPECTED_CAMPAIGN_ID
        assert projection["config_digest"] == replayed["session"]["config_digest"]
        assert projection["generation"] == 1
        assert projection["cycle_sequence"] >= 1
        assert projection["campaign_status"] == "paused"
        assert projection["supervisor_state"] == "not_running"
        assert projection["writer_lock_held"] is False
        assert projection["owner_executions"] == []
        assert replayed["global_dispatch_rows"] == {
            "before": {"task_claim_ids": [], "delegation_run_ids": []},
            "after": {"task_claim_ids": [], "delegation_run_ids": []},
        }


@pytest.mark.asyncio
async def test_replay_refreshes_a_stale_projection_with_one_monotonic_no_effect_cycle(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    inputs = _inputs(tmp_path, monkeypatch, state_name="stale-projection")
    first_receipt = await preparation.prepare_runtime(inputs)
    first_projection = _projection(inputs)
    first_sequence = first_projection["cycle_sequence"]
    stale_at = datetime(2026, 1, 1, tzinfo=timezone.utc)
    first_projection["mission_snapshot"]["observed_at"] = stale_at.isoformat()
    first_projection["observed_at"] = stale_at.isoformat()
    first_projection["published_at"] = stale_at.isoformat()
    first_projection["latest_cycle_at"] = stale_at.isoformat()
    first_projection["fresh_until"] = (
        stale_at + timedelta(seconds=inputs.freshness_seconds)
    ).isoformat()
    stale_raw = _rewrite_projection(inputs, first_projection)

    replayed = await preparation.prepare_runtime(inputs)
    refreshed = _projection(inputs)

    assert replayed == first_receipt
    assert refreshed["cycle_sequence"] == first_sequence + 1
    assert refreshed["campaign_status"] == "paused"
    assert refreshed["supervisor_state"] == "not_running"
    assert refreshed["writer_lock_held"] is False
    assert refreshed["owner_executions"] == []
    assert inputs.projection_path.read_bytes() != stale_raw
    runtime = preparation.RuntimeStateStore(
        inputs.state_dir / "state" / "runtime.db",
        include_memory_plane=False,
    )
    assert await preparation._global_dispatch_rows(runtime) == {
        "task_claim_ids": [],
        "delegation_run_ids": [],
    }
    assert await preparation._effect_census(
        runtime,
        f"mission_campaign:{bootstrap.EXPECTED_CAMPAIGN_ID}",
    ) == {kind: 0 for kind in preparation.EFFECT_KINDS}


@pytest.mark.asyncio
async def test_interrupted_running_projection_is_recovered_without_dispatch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    inputs = _inputs(tmp_path, monkeypatch, state_name="interrupted-projection")
    await preparation.prepare_runtime(inputs)
    receipt_path = (
        inputs.state_dir / "receipts" / preparation.PREPARATION_RECEIPT_NAME
    )
    receipt_path.unlink()
    projection = _projection(inputs)
    previous_sequence = projection["cycle_sequence"]
    projection["supervisor_state"] = "running"
    projection["writer_lock_held"] = True
    projection["proves_process_liveness"] = True
    _rewrite_projection(inputs, projection)

    replayed = await preparation.prepare_runtime(inputs)
    recovered = _projection(inputs)

    assert receipt_path.is_file()
    assert replayed["projection"]["minimum_cycle_sequence"] == 1
    assert recovered["cycle_sequence"] == previous_sequence + 1
    assert recovered["campaign_status"] == "paused"
    assert recovered["supervisor_state"] == "not_running"
    assert recovered["writer_lock_held"] is False
    assert recovered["proves_process_liveness"] is False
    assert recovered["owner_executions"] == []


@pytest.mark.asyncio
async def test_cycle_commit_crash_recovers_from_a_lagging_projection(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    inputs = _inputs(tmp_path, monkeypatch, state_name="lagging-projection")
    receipt = await preparation.prepare_runtime(inputs)
    initial = _projection(inputs)
    original_publish = campaign_service.publish_campaign_projection

    def crash_before_projection(*args: object, **kwargs: object) -> None:
        raise InjectedCrash("cycle committed before projection publication")

    monkeypatch.setattr(
        campaign_service,
        "publish_campaign_projection",
        crash_before_projection,
    )
    with pytest.raises(InjectedCrash, match="cycle committed"):
        await preparation.prepare_runtime(inputs)
    runtime = preparation.RuntimeStateStore(
        inputs.state_dir / "state" / "runtime.db",
        include_memory_plane=False,
    )
    lagged_session = await runtime.get_session(
        f"mission_campaign:{bootstrap.EXPECTED_CAMPAIGN_ID}"
    )
    assert lagged_session is not None
    assert lagged_session.metadata["last_cycle_sequence"] == (
        initial["cycle_sequence"] + 1
    )
    assert _projection(inputs)["cycle_sequence"] == initial["cycle_sequence"]

    monkeypatch.setattr(
        campaign_service,
        "publish_campaign_projection",
        original_publish,
    )
    replayed = await preparation.prepare_runtime(inputs)
    recovered = _projection(inputs)

    assert replayed == receipt
    assert recovered["cycle_sequence"] == initial["cycle_sequence"] + 2
    assert recovered["campaign_status"] == "paused"
    assert recovered["supervisor_state"] == "not_running"
    assert recovered["owner_executions"] == []
    assert await preparation._global_dispatch_rows(runtime) == {
        "task_claim_ids": [],
        "delegation_run_ids": [],
    }


@pytest.mark.asyncio
async def test_foreign_projection_config_is_rejected_without_replacement_or_cycle(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    inputs = _inputs(tmp_path, monkeypatch, state_name="foreign-projection-config")
    await preparation.prepare_runtime(inputs)
    projection = _projection(inputs)
    previous_sequence = projection["cycle_sequence"]
    projection["config_digest"] = "sha256:" + "f" * 64
    foreign_raw = _rewrite_projection(inputs, projection)

    with pytest.raises(MissionControlError, match="projection identity conflicts"):
        await preparation.prepare_runtime(inputs)

    assert inputs.projection_path.read_bytes() == foreign_raw
    runtime = preparation.RuntimeStateStore(
        inputs.state_dir / "state" / "runtime.db",
        include_memory_plane=False,
    )
    session = await runtime.get_session(
        f"mission_campaign:{bootstrap.EXPECTED_CAMPAIGN_ID}"
    )
    assert session is not None
    assert session.metadata["last_cycle_sequence"] == previous_sequence
    assert await preparation._global_dispatch_rows(runtime) == {
        "task_claim_ids": [],
        "delegation_run_ids": [],
    }


@pytest.mark.asyncio
async def test_projection_path_must_be_the_exact_service_owned_sibling(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    inputs = _inputs(tmp_path, monkeypatch, state_name="foreign-projection-path")
    foreign = preparation.RuntimePreparationInputs(
        **{
            **{field: getattr(inputs, field) for field in inputs.__dataclass_fields__},
            "projection_path": tmp_path / "other" / "mission-projection.json",
        }
    )

    with pytest.raises(MissionControlError, match="canonical service sibling path"):
        await preparation.prepare_runtime(foreign)

    assert not inputs.state_dir.exists()
    assert not foreign.projection_path.exists()


@pytest.mark.asyncio
async def test_projection_symlink_is_rejected_without_touching_its_target(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    inputs = _inputs(tmp_path, monkeypatch, state_name="projection-symlink")
    await preparation.prepare_runtime(inputs)
    target = tmp_path / "projection-target.json"
    target.write_bytes(inputs.projection_path.read_bytes())
    target.chmod(0o600)
    inputs.projection_path.unlink()
    inputs.projection_path.symlink_to(target)
    target_before = target.read_bytes()

    with pytest.raises(MissionControlError, match="projection custody is invalid"):
        await preparation.prepare_runtime(inputs)

    assert inputs.projection_path.is_symlink()
    assert target.read_bytes() == target_before


@pytest.mark.asyncio
async def test_mid_write_crash_leaves_only_non_authoritative_temp_and_replays(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    inputs = _inputs(tmp_path, monkeypatch, state_name="mid-write")
    manifest_name = preparation.RUNTIME_MANIFEST_NAMES[0]
    final = inputs.output_root / manifest_name
    temp = inputs.output_root / preparation._publication_temp_name(manifest_name)

    def crash(phase: str) -> None:
        if phase == "publish_observed_manifest_partial":
            raise InjectedCrash(phase)

    with pytest.raises(InjectedCrash, match="publish_observed_manifest_partial"):
        await preparation.prepare_runtime(inputs, checkpoint=crash)

    assert not final.exists()
    assert temp.is_file()
    assert temp.stat().st_size > 0
    assert temp.stat().st_nlink == 1
    assert not (
        inputs.state_dir / "receipts" / preparation.PREPARATION_RECEIPT_NAME
    ).exists()

    replayed = await preparation.prepare_runtime(inputs)
    assert not temp.exists()
    assert final.is_file()
    assert (
        hashlib.sha256(final.read_bytes()).hexdigest()
        == replayed["manifests"]["files"][manifest_name]
    )


@pytest.mark.asyncio
async def test_crash_after_no_replace_link_replays_to_single_authoritative_link(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    inputs = _inputs(tmp_path, monkeypatch, state_name="linked")
    manifest_name = preparation.RUNTIME_MANIFEST_NAMES[0]
    final = inputs.output_root / manifest_name
    temp = inputs.output_root / preparation._publication_temp_name(manifest_name)

    def crash(phase: str) -> None:
        if phase == "publish_observed_manifest_linked":
            raise InjectedCrash(phase)

    with pytest.raises(InjectedCrash, match="publish_observed_manifest_linked"):
        await preparation.prepare_runtime(inputs, checkpoint=crash)

    assert final.stat().st_ino == temp.stat().st_ino
    assert final.stat().st_nlink == 2
    replayed = await preparation.prepare_runtime(inputs)
    assert not temp.exists()
    assert final.stat().st_nlink == 1
    assert (
        hashlib.sha256(final.read_bytes()).hexdigest()
        == replayed["manifests"]["files"][manifest_name]
    )


@pytest.mark.parametrize("boundary", ("partial", "fsynced", "linked"))
def test_atomic_publication_replays_every_durability_boundary(
    tmp_path: Path,
    boundary: str,
) -> None:
    root = tmp_path / boundary
    root.mkdir(mode=0o700)
    final = root / "artifact.json"
    temp = root / preparation._publication_temp_name(final.name)
    payload = preparation._canonical_bytes({"boundary": boundary})

    def crash(phase: str) -> None:
        if phase == f"publish_test_{boundary}":
            raise InjectedCrash(phase)

    with pytest.raises(InjectedCrash, match=f"publish_test_{boundary}"):
        preparation._atomic_publish_exact(
            final,
            payload,
            canonical_json=True,
            label="publish_test",
            checkpoint=crash,
        )

    assert temp.exists()
    assert final.exists() is (boundary == "linked")
    preparation._atomic_publish_exact(
        final,
        payload,
        canonical_json=True,
        label="publish_test",
        checkpoint=None,
    )
    assert final.read_bytes() == payload
    assert final.stat().st_nlink == 1
    assert not temp.exists()


@pytest.mark.asyncio
async def test_existing_mismatched_final_is_never_overwritten(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    inputs = _inputs(tmp_path, monkeypatch, state_name="mismatch")
    await preparation.prepare_runtime(inputs)
    final = inputs.output_root / preparation.RUNTIME_MANIFEST_NAMES[0]
    mismatched = b"{}\n"
    final.write_bytes(mismatched)

    with pytest.raises(MissionControlError, match="replay conflicts"):
        await preparation.prepare_runtime(inputs)
    assert final.read_bytes() == mismatched


def _valid_receipt() -> tuple[dict[str, object], dict[str, object]]:
    tasks = {
        goal_id: f"task-{index}"
        for index, goal_id in enumerate(bootstrap.EXPECTED_GOAL_IDS)
    }
    manifest_files = {
        name: str(index) * 64
        for index, name in enumerate(
            preparation.RUNTIME_MANIFEST_NAMES,
            start=1,
        )
    }
    held_out_digest = "sha256:" + "5" * 64
    manifests = {
        "files": manifest_files,
        "observed_input_manifest_digest": "sha256:" + "3" * 64,
        "held_out_oracle_manifest_digest": held_out_digest,
        "authority_manifest_digest": "sha256:" + "4" * 64,
    }
    config = preparation.CampaignConfig(
        mission_id="sadhana-10-20260823",
        operator_id="operator",
        canary_task_id="task-0",
        held_out_oracle_digest=held_out_digest,
    )
    config_digest = config.digest
    input_set = {
        "release_admission_receipt_digest": "sha256:" + "0" * 64,
        "goal_contract_digest": "sha256:" + "6" * 64,
        "observed_source_sha256": "sha256:" + "7" * 64,
        "roster_sha256": "8" * 64,
        "objective_sha256": "9" * 64,
        "verifier_seat": "sadhana-seat-6",
        "manifest_pins": {
            "evaluator_path": "/release/evaluator.py",
            "evaluator_sha256": "sha256:" + "a" * 64,
            "policy_path": "/release/policy.json",
            "policy_sha256": "sha256:" + "b" * 64,
            "operator_control_semantics_sha256": "sha256:" + "c" * 64,
            "operator_control_authority_binding_sha256": "sha256:" + "d" * 64,
            "deployment_authority_topology_sha256": "sha256:" + "e" * 64,
            "deployment_authority_credential_clarification_sha256": (
                "sha256:" + "f" * 64
            ),
        },
    }
    release_sha = "a" * 40
    release_input_set_digest = "0" * 64
    preparation_input_digest = preparation._digest(input_set)
    manifest_set_digest = preparation._digest(manifests)
    projection_path = Path(
        "/var/lib/dharma-sadhana/projection-source/mission-projection.json"
    )
    projection_contract = preparation.initial_projection_contract(
        path=projection_path,
        config=config,
        generation=1,
    )
    proof = preparation.PreparedNoEffectProof(
        campaign_id="sadhana-10-20260823",
        release_sha=release_sha,
        release_input_set_digest=release_input_set_digest,
        preparation_input_digest=preparation_input_digest,
        config_digest=config_digest,
        task_set_digest=preparation._digest(tasks),
        manifest_set_digest=manifest_set_digest,
        projection_contract_digest=preparation._digest(projection_contract),
        session_generation=1,
        session_status="paused",
    )
    payload: dict[str, object] = {
        "schema_version": preparation.PREPARATION_SCHEMA,
        "authority_state": "unbound",
        "dispatch_ready": False,
        "proof": proof.to_dict(),
        "input_set": input_set,
        "tasks": tasks,
        "manifests": manifests,
        "config": preparation.supervisor_config_projection(config),
        "session": {
            "session_id": "mission_campaign:sadhana-10-20260823",
            "generation": 1,
            "status": "paused",
            "config_digest": config_digest,
        },
        "projection": projection_contract,
        "global_dispatch_rows": {
            "before": {"task_claim_ids": [], "delegation_run_ids": []},
            "after": {"task_claim_ids": [], "delegation_run_ids": []},
        },
    }
    payload["receipt_digest"] = preparation._digest(payload)
    expected: dict[str, object] = {
        "expected_release_sha": release_sha,
        "expected_release_input_set_digest": release_input_set_digest,
        "expected_preparation_input_digest": preparation_input_digest,
        "expected_config_digest": config_digest,
        "expected_task_set_digest": preparation._digest(tasks),
        "expected_manifest_set_digest": manifest_set_digest,
        "expected_projection_path": projection_path,
        "expected_session_generation": 1,
    }
    return payload, expected


def _reseal(payload: dict[str, object]) -> None:
    payload.pop("receipt_digest", None)
    payload["receipt_digest"] = preparation._digest(payload)


def test_mutated_no_effect_proof_is_rejected() -> None:
    payload, expected = _valid_receipt()
    preparation.validate_preparation_receipt(
        payload,
        **expected,
    )

    mutated = json.loads(json.dumps(payload))
    mutated["proof"]["effect_counts"]["provider"] = 1
    _reseal(mutated)
    with pytest.raises(MissionControlError, match="nonzero effect"):
        preparation.validate_preparation_receipt(mutated)


@pytest.mark.parametrize(
    "field",
    (
        "release_sha",
        "release_input_set_digest",
        "preparation_input_digest",
        "manifest_set_digest",
        "session_generation",
        "config_digest",
    ),
)
def test_release_input_manifest_and_session_substitutions_are_rejected(
    field: str,
) -> None:
    payload, expected = _valid_receipt()
    substituted = json.loads(json.dumps(payload))
    parameters = substituted["proof"]["parameters"]
    if field == "release_sha":
        parameters[field] = "b" * 40
    elif field == "release_input_set_digest":
        parameters[field] = "b" * 64
    elif field == "preparation_input_digest":
        substituted["input_set"]["objective_sha256"] = "d" * 64
        parameters[field] = preparation._digest(substituted["input_set"])
    elif field == "manifest_set_digest":
        name = preparation.RUNTIME_MANIFEST_NAMES[0]
        substituted["manifests"]["files"][name] = "d" * 64
        parameters[field] = preparation._digest(substituted["manifests"])
    elif field == "session_generation":
        substituted["session"]["generation"] = 2
        parameters[field] = 2
    elif field == "config_digest":
        substituted["config"]["freshness_seconds"] = 31.0
        replacement = preparation.CampaignConfig(
            mission_id=substituted["config"]["mission_id"],
            operator_id=substituted["config"]["operator_id"],
            canary_task_id=substituted["config"]["canary_task_id"],
            max_dispatch_per_cycle=substituted["config"]["max_dispatch_per_cycle"],
            cycle_interval_seconds=substituted["config"]["cycle_interval_seconds"],
            freshness_seconds=substituted["config"]["freshness_seconds"],
            held_out_oracle_digest=substituted["config"]["held_out_oracle_digest"],
        ).digest
        substituted["session"]["config_digest"] = replacement
        parameters[field] = replacement
    _reseal(substituted)

    with pytest.raises(MissionControlError, match="substitution"):
        preparation.validate_preparation_receipt(
            substituted,
            **expected,
        )


def test_active_session_is_not_a_prepared_session() -> None:
    payload, _ = _valid_receipt()
    payload["session"]["status"] = "active"
    payload["proof"]["parameters"]["session_status"] = "active"
    _reseal(payload)

    with pytest.raises(MissionControlError, match="session identity"):
        preparation.validate_preparation_receipt(payload)


@pytest.mark.parametrize(
    ("field", "replacement"),
    (
        ("release_sha", "b" * 40),
        ("release_input_set_digest", "b" * 64),
        ("release_root", "/opt/dharma-sadhana/releases/foreign"),
    ),
)
def test_staged_release_admission_substitutions_are_rejected(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    field: str,
    replacement: str,
) -> None:
    inputs = _inputs(tmp_path, monkeypatch, state_name=f"release-{field}")
    payload = json.loads(inputs.release_admission_receipt.read_text(encoding="utf-8"))
    payload[field] = replacement
    _reseal(payload)
    inputs.release_admission_receipt.write_bytes(preparation._canonical_bytes(payload))

    with pytest.raises(MissionControlError, match="substitution"):
        preparation.load_staged_release_admission(
            inputs.release_admission_receipt,
            expected_release_root=inputs.release_root,
            expected_release_sha=inputs.release_sha,
            expected_release_input_set_digest=inputs.release_input_set_digest,
        )


@pytest.mark.asyncio
async def test_root_owned_promotion_target_is_rejected_before_state(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    inputs = _inputs(tmp_path, monkeypatch, state_name="foreign-output")
    foreign = preparation.RuntimePreparationInputs(
        **{
            **{field: getattr(inputs, field) for field in inputs.__dataclass_fields__},
            "output_root": tmp_path / "etc" / "dharma-sadhana" / "inputs",
        }
    )

    with pytest.raises(MissionControlError, match="service-owned state root"):
        await preparation.prepare_runtime(foreign)
    assert not inputs.state_dir.exists()


@pytest.mark.asyncio
async def test_roster_rejection_precedes_state_and_no_execution_surface_is_called(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    inputs = _inputs(tmp_path, monkeypatch, state_name="rejected")

    def reject(*args: object, **kwargs: object) -> CampaignAgentRoster:
        raise CampaignRosterError("injected roster mismatch")

    monkeypatch.setattr(preparation, "load_campaign_agent_roster", reject)
    with pytest.raises(CampaignRosterError, match="roster mismatch"):
        await preparation.prepare_runtime(inputs)
    assert not inputs.state_dir.exists()

    source = Path(preparation.__file__).read_text(encoding="utf-8")
    forbidden = (
        "OllamaProvider(",
        "create_runtime_provider(",
        "assess_runtime_admission(",
        ".dispatch(",
        ".cycle(",
        ".accept(",
        "subprocess.",
        "urllib.",
        "requests.",
        "httpx.",
    )
    assert all(token not in source for token in forbidden)


def test_receipt_digest_is_canonical_and_challengeable() -> None:
    value = {"b": 2, "a": 1}
    assert preparation._digest(value) == (
        "sha256:" + hashlib.sha256(b'{"a":1,"b":2}\n').hexdigest()
    )


def test_supervisor_config_projection_is_nonsecret_and_recomputable() -> None:
    config = preparation.CampaignConfig(
        mission_id="sadhana-10-20260823",
        operator_id="operator",
        canary_task_id="task-0",
        held_out_oracle_digest="sha256:" + "a" * 64,
    )
    projection = preparation.supervisor_config_projection(config)

    assert (
        preparation.validate_supervisor_config_projection(
            projection,
            expected_config_digest=config.digest,
            expected_held_out_oracle_digest=config.held_out_oracle_digest,
        )
        == config
    )
    assert all(
        token not in json.dumps(projection).lower()
        for token in ("credential", "environment", "hmac", "secret")
    )

    substituted = dict(projection)
    substituted["held_out_oracle_digest"] = "sha256:" + "b" * 64
    with pytest.raises(MissionControlError, match="held-out substitution"):
        preparation.validate_supervisor_config_projection(
            substituted,
            expected_config_digest=config.digest,
            expected_held_out_oracle_digest=config.held_out_oracle_digest,
        )
