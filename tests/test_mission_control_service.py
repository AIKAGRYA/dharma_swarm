from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pytest

import dharma_swarm.mission_control_service as service_module
from dharma_swarm.mission_control_campaign import CampaignConfig
from dharma_swarm.mission_control_service import (
    CAMPAIGN_PROJECTION_SCHEMA_VERSION,
    CAMPAIGN_WRITER_IDENTITY_SCHEMA_VERSION,
    CampaignControlGate,
    CampaignProjectionError,
    CampaignService,
    CampaignWriterBusy,
    CampaignWriterLock,
    MAX_CAMPAIGN_PROJECTION_BYTES,
    materialize_projection_liveness,
    projection_confirms_start,
    publish_campaign_projection,
    read_campaign_projection,
    read_writer_lock_identity,
    writer_lock_is_held,
)
from scripts.runtime import mission_control_campaign as campaign_cli


@dataclass(frozen=True)
class _Config:
    cycle_interval_seconds: float = 0.001


@dataclass(frozen=True)
class _Snapshot:
    latest_cycle_at: datetime
    mission_id: str = "mission-alpha"
    session_id: str = "mission_campaign:mission-alpha"
    config_digest: str = "sha256:config-alpha"
    generation: int = 1
    cycle_sequence: int = 1
    mission_marker: str = "cycle-one"
    freshness_seconds: float = 30.0
    campaign_status: str = "active"
    supervisor_state: str = "running"
    writer_lock_held: bool = True
    observed_at: datetime = datetime(2026, 8, 23, tzinfo=timezone.utc)
    proves_process_liveness: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "mission_id": self.mission_id,
            "session_id": self.session_id,
            "config_digest": self.config_digest,
            "generation": self.generation,
            "cycle_sequence": self.cycle_sequence,
            "mission_snapshot": {"marker": self.mission_marker},
            "freshness_seconds": self.freshness_seconds,
            "campaign_status": self.campaign_status,
            "supervisor_state": self.supervisor_state,
            "writer_lock_held": self.writer_lock_held,
            "latest_cycle_at": self.latest_cycle_at.isoformat(),
            "transport_state": "unobserved",
            "model_execution_state": "unobserved",
            "acceptance_state": "unobserved",
        }


def _writer_identity(
    *, mission_id: str = "mission-alpha", generation: int = 1
) -> dict[str, Any]:
    return {
        "schema_version": CAMPAIGN_WRITER_IDENTITY_SCHEMA_VERSION,
        "mission_id": mission_id,
        "session_id": f"mission_campaign:{mission_id}",
        "config_digest": "sha256:config-alpha",
        "generation": generation,
    }


class _BlockingSupervisor:
    config = _Config()

    def __init__(self, entered: asyncio.Event, release: asyncio.Event) -> None:
        self.entered = entered
        self.release = release
        self.starts = 0
        self.cycles = 0

    async def start(self) -> None:
        self.starts += 1

    async def cycle(self, *, writer_lock_held: bool):
        assert writer_lock_held is True
        self.cycles += 1
        self.entered.set()
        await self.release.wait()
        return _Snapshot(datetime.now(timezone.utc))


def test_writer_lock_identity_is_exact_and_malformed_data_fails_closed(
    tmp_path: Path,
) -> None:
    path = tmp_path / "campaign.lock"
    cycle = datetime(2026, 8, 23, tzinfo=timezone.utc)
    with CampaignWriterLock(path) as writer:
        expected = writer.bind(_Snapshot(cycle))  # type: ignore[arg-type]
        assert read_writer_lock_identity(path) == expected
    assert read_writer_lock_identity(path) == expected

    projection = {
        **_Snapshot(cycle).to_dict(),
        "projection_schema_version": CAMPAIGN_PROJECTION_SCHEMA_VERSION,
        "fresh_until": (cycle + timedelta(seconds=30)).isoformat(),
    }
    with CampaignWriterLock(path):
        assert read_writer_lock_identity(path) is None
        stale_owner = materialize_projection_liveness(
            projection,
            now=cycle + timedelta(seconds=1),
            writer_lock_held=True,
            writer_lock_identity=read_writer_lock_identity(path),
            expected_mission_id="mission-alpha",
        )
        assert stale_owner["supervisor_state"] == "lock_identity_mismatch"
        assert stale_owner["proves_process_liveness"] is False

    path.write_text('{"mission_id":"foreign"}', encoding="utf-8")
    assert read_writer_lock_identity(path) is None


@pytest.mark.asyncio
async def test_cli_initializes_campaign_from_fresh_state_root(tmp_path: Path) -> None:
    state_dir = tmp_path / "fresh-state"
    state_dir.mkdir()
    board = await campaign_cli._board(state_dir)
    runtime = campaign_cli._runtime_store(state_dir)
    await runtime.init_db()
    control = campaign_cli.MissionControl(board, runtime)
    await control.create_mission("mission-alpha", title="Mission Alpha")

    session = await campaign_cli._initialize_campaign(
        state_dir,
        CampaignConfig("mission-alpha"),
        state_dir / "mission_control" / "campaign-supervisor.lock.control",
    )

    assert session.session_id == "mission_campaign:mission-alpha"
    assert (state_dir / "db" / "tasks.db").is_file()
    assert (state_dir / "state" / "runtime.db").is_file()


@pytest.mark.asyncio
async def test_second_writer_fails_nonblocking_and_start_never_treats_pid_as_success(
    tmp_path: Path,
) -> None:
    lock_path = tmp_path / "campaign.lock"
    entered = asyncio.Event()
    release = asyncio.Event()
    first = CampaignService(
        _BlockingSupervisor(entered, release),  # type: ignore[arg-type]
        lock_path=lock_path,
        projection_path=tmp_path / "first.json",
    )
    second = CampaignService(
        _BlockingSupervisor(asyncio.Event(), asyncio.Event()),  # type: ignore[arg-type]
        lock_path=lock_path,
        projection_path=tmp_path / "second.json",
    )
    first_run = asyncio.create_task(first.run(max_cycles=1))
    await asyncio.wait_for(entered.wait(), timeout=1)
    assert writer_lock_is_held(lock_path) is True

    with pytest.raises(CampaignWriterBusy, match="already held"):
        await asyncio.wait_for(second.run(max_cycles=1), timeout=0.1)

    requested_at = datetime.now(timezone.utc)
    pid_only = {
        "pid": 424242,
        "projection_schema_version": CAMPAIGN_PROJECTION_SCHEMA_VERSION,
        "writer_lock_held": True,
        "supervisor_state": "running",
        "latest_cycle_at": (requested_at - timedelta(seconds=1)).isoformat(),
    }
    assert projection_confirms_start(
        pid_only,
        requested_at=requested_at,
        writer_lock_held=True,
        writer_lock_identity=_writer_identity(),
        expected_mission_id="mission-alpha",
        expected_config_digest="sha256:config-alpha",
        expected_generation=1,
    ) is False
    fresh = {
        **pid_only,
        "latest_cycle_at": (requested_at + timedelta(milliseconds=1)).isoformat(),
    }
    assert projection_confirms_start(
        fresh,
        requested_at=requested_at,
        writer_lock_held=False,
        writer_lock_identity=_writer_identity(),
        expected_mission_id="mission-alpha",
        expected_config_digest="sha256:config-alpha",
        expected_generation=1,
    ) is False

    release.set()
    result = await asyncio.wait_for(first_run, timeout=1)
    assert result.completed_cycles == 1
    assert result.snapshot.cycle_sequence == 1
    assert result.snapshot.supervisor_state == "not_running"
    assert result.snapshot.writer_lock_held is False
    assert result.snapshot.proves_process_liveness is False
    assert writer_lock_is_held(lock_path) is False


def test_atomic_projection_is_a_read_model_not_a_second_ledger(tmp_path: Path) -> None:
    path = tmp_path / "read-model" / "campaign.json"
    first = _Snapshot(datetime(2026, 8, 23, 1, tzinfo=timezone.utc))
    second = _Snapshot(
        datetime(2026, 8, 23, 2, tzinfo=timezone.utc), cycle_sequence=2
    )

    publish_campaign_projection(first, path)  # type: ignore[arg-type]
    publish_campaign_projection(second, path)  # type: ignore[arg-type]
    payload = read_campaign_projection(path)

    assert payload is not None
    assert payload["latest_cycle_at"] == second.latest_cycle_at.isoformat()
    assert payload["cycle_sequence"] == 2
    assert payload["projection_kind"] == "derived_read_model"
    assert payload["canonical_state_copied"] is False
    assert str(payload["projection_content_digest"]).startswith("sha256:")
    assert payload["mission_id"] == "mission-alpha"
    assert payload["fresh_until"] == (
        second.latest_cycle_at + timedelta(seconds=30)
    ).isoformat()
    assert list(path.parent.glob("*.tmp")) == []

    tampered = dict(payload)
    tampered["mission_id"] = "mission-forged"
    path.write_text(json.dumps(tampered), encoding="utf-8")
    with pytest.raises(CampaignProjectionError, match="content digest"):
        read_campaign_projection(path)

    path.write_text("not-json", encoding="utf-8")
    with pytest.raises(CampaignProjectionError, match="valid JSON"):
        read_campaign_projection(path)


def test_projection_rejects_more_than_32_mib_before_replace(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = tmp_path / "campaign.json"
    snapshot = _Snapshot(datetime(2026, 8, 23, tzinfo=timezone.utc))
    publish_campaign_projection(snapshot, path)  # type: ignore[arg-type]
    preserved = path.read_bytes()
    monkeypatch.setattr(
        service_module,
        "_projection_payload",
        lambda _: {"oversized": "x" * MAX_CAMPAIGN_PROJECTION_BYTES},
    )

    with pytest.raises(CampaignProjectionError, match="exceeds 32 MiB"):
        publish_campaign_projection(
            snapshot,
            path,
        )  # type: ignore[arg-type]

    assert path.read_bytes() == preserved


def test_projection_rejects_overflowing_freshness(tmp_path: Path) -> None:
    with pytest.raises(CampaignProjectionError, match="freshness"):
        publish_campaign_projection(
            _Snapshot(
                datetime(2026, 8, 23, tzinfo=timezone.utc),
                freshness_seconds=float("inf"),
            ),
            tmp_path / "campaign.json",
        )  # type: ignore[arg-type]


def test_equal_cycle_position_pins_nested_mission_snapshot(tmp_path: Path) -> None:
    path = tmp_path / "campaign.json"
    cycle = datetime(2026, 8, 23, 1, tzinfo=timezone.utc)
    first = _Snapshot(cycle, mission_marker="durable-cycle")
    stopped = _Snapshot(
        cycle,
        mission_marker="post-stop-reobservation",
        campaign_status="stopped",
        supervisor_state="stopped",
    )

    publish_campaign_projection(first, path)  # type: ignore[arg-type]
    publish_campaign_projection(stopped, path)  # type: ignore[arg-type]
    payload = read_campaign_projection(path)

    assert payload is not None
    assert (payload["generation"], payload["cycle_sequence"]) == (1, 1)
    assert payload["campaign_status"] == "stopped"
    assert payload["mission_snapshot"] == {"marker": "durable-cycle"}


def test_projection_liveness_is_recomputed_from_clock_lock_and_identity() -> None:
    cycle = datetime(2026, 8, 23, 1, tzinfo=timezone.utc)
    projection = {
        **_Snapshot(cycle).to_dict(),
        "projection_schema_version": CAMPAIGN_PROJECTION_SCHEMA_VERSION,
        "fresh_until": (cycle + timedelta(seconds=30)).isoformat(),
        "proves_process_liveness": True,
    }

    current = materialize_projection_liveness(
        projection,
        now=cycle + timedelta(seconds=1),
        writer_lock_held=True,
        writer_lock_identity=_writer_identity(),
        expected_mission_id="mission-alpha",
    )
    assert current["status"] == "running"
    assert current["proves_process_liveness"] is True

    exited = materialize_projection_liveness(
        projection,
        now=cycle + timedelta(seconds=1),
        writer_lock_held=False,
        writer_lock_identity=None,
        expected_mission_id="mission-alpha",
    )
    assert exited["supervisor_state"] == "not_running"
    assert exited["proves_process_liveness"] is False

    stale = materialize_projection_liveness(
        projection,
        now=cycle + timedelta(minutes=1),
        writer_lock_held=True,
        writer_lock_identity=_writer_identity(),
        expected_mission_id="mission-alpha",
    )
    assert stale["supervisor_state"] == "stale_lock"
    assert stale["proves_process_liveness"] is False

    foreign = materialize_projection_liveness(
        projection,
        now=cycle,
        writer_lock_held=True,
        writer_lock_identity=_writer_identity(mission_id="mission-beta"),
        expected_mission_id="mission-beta",
    )
    assert foreign["supervisor_state"] == "foreign_projection"
    assert foreign["proves_process_liveness"] is False

    wrong_lock = materialize_projection_liveness(
        projection,
        now=cycle,
        writer_lock_held=True,
        writer_lock_identity=_writer_identity(mission_id="mission-beta"),
        expected_mission_id="mission-alpha",
    )
    assert wrong_lock["supervisor_state"] == "lock_identity_mismatch"
    assert wrong_lock["proves_process_liveness"] is False


@pytest.mark.asyncio
async def test_control_gate_serializes_stop_with_inflight_cycle(tmp_path: Path) -> None:
    entered = asyncio.Event()
    release = asyncio.Event()
    supervisor = _BlockingSupervisor(entered, release)
    gate_path = tmp_path / "campaign.control.lock"
    service = CampaignService(
        supervisor,  # type: ignore[arg-type]
        lock_path=tmp_path / "campaign.lock",
        control_gate_path=gate_path,
        projection_path=tmp_path / "status.json",
    )
    run = asyncio.create_task(service.run(max_cycles=1, start_campaign=False))
    await asyncio.wait_for(entered.wait(), timeout=1)
    stop_entered = asyncio.Event()

    async def _stop_side() -> None:
        async with CampaignControlGate(gate_path):
            stop_entered.set()

    stop = asyncio.create_task(_stop_side())
    await asyncio.sleep(0.02)
    assert stop_entered.is_set() is False
    release.set()
    await asyncio.wait_for(run, timeout=1)
    await asyncio.wait_for(stop, timeout=1)
    assert stop_entered.is_set() is True


@pytest.mark.asyncio
async def test_cancelled_control_gate_waiter_never_leaks_lock(tmp_path: Path) -> None:
    gate_path = tmp_path / "campaign.control.lock"
    owner = CampaignControlGate(gate_path)
    owner.acquire()

    async def _wait() -> None:
        async with CampaignControlGate(gate_path):
            raise AssertionError("cancelled waiter must not enter its body")

    waiter = asyncio.create_task(_wait())
    await asyncio.sleep(0.02)
    waiter.cancel()
    waiter.cancel()
    with pytest.raises(asyncio.CancelledError):
        await asyncio.wait_for(waiter, timeout=1)
    owner.release()

    entered = False
    async with CampaignControlGate(gate_path):
        entered = True
    assert entered is True


@pytest.mark.asyncio
async def test_service_rejects_fractional_cycles_and_path_aliases(tmp_path: Path) -> None:
    supervisor = _BlockingSupervisor(asyncio.Event(), asyncio.Event())
    with pytest.raises(ValueError, match="paths must be different"):
        CampaignService(
            supervisor,  # type: ignore[arg-type]
            lock_path=tmp_path / "campaign.lock",
            control_gate_path=tmp_path / "same.json",
            projection_path=tmp_path / "same.json",
        )
    service = CampaignService(
        supervisor,  # type: ignore[arg-type]
        lock_path=tmp_path / "campaign.lock",
        projection_path=tmp_path / "status.json",
    )
    with pytest.raises(ValueError, match="positive integer"):
        await service.run(max_cycles=1.5)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "field",
    [
        "start_timeout",
        "poll_interval",
        "shutdown_timeout",
        "writer_handoff_timeout",
    ],
)
def test_cli_start_rejects_nonfinite_timeouts_before_side_effects(
    tmp_path: Path,
    field: str,
) -> None:
    state_dir = tmp_path / "uncreated-state"
    args = campaign_cli.build_parser().parse_args(
        ["start", "--state-dir", str(state_dir), "--mission-id", "mission-alpha"]
    )
    setattr(args, field, float("nan"))

    with pytest.raises(ValueError, match="positive finite"):
        campaign_cli.start_campaign_process(
            args,
            popen=lambda *args, **kwargs: pytest.fail("must not spawn"),
        )

    assert state_dir.exists() is False


def test_campaign_paths_are_pairwise_distinct(tmp_path: Path) -> None:
    same = tmp_path / "same"
    with pytest.raises(ValueError, match="must differ"):
        campaign_cli.CampaignPaths(same, same, tmp_path / "status", tmp_path / "log")
