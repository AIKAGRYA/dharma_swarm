"""Contract tests for the foreground RSI single-flight/resource guard."""

from __future__ import annotations

import json
import multiprocessing
import os
from pathlib import Path

import pytest

from dharma_swarm.forge_lab.run_guard import (
    HostResources,
    RunGuard,
    RunGuardError,
    RunLimits,
    require_host_resources,
    run_state_identity_digest,
)


_RELEASE = "a" * 40
_DIGEST = "sha256:" + "b" * 64


def _hold_guard(state: str, ready, release) -> None:
    with RunGuard(
        Path(state),
        campaign_id="campaign-one",
        request_id="request-one",
        release_commit=_RELEASE,
        config_digest=_DIGEST,
        wall_seconds=60,
    ):
        ready.set()
        release.wait(10)


def test_limits_reject_oversized_shape_before_dispatch() -> None:
    with pytest.raises(RunGuardError) as raised:
        RunLimits(1_000, 64, 2_000, 64, 1, 1, 1, 1).validate()
    assert raised.value.code == "RUN_SHAPE_TOO_LARGE"

    valid = RunLimits(2, 2, 4, 3, 100_000, 2_000_000, 100, 600)
    assert valid.validate() is valid


def test_host_gate_is_explicit_and_fail_closed() -> None:
    snapshot = HostResources(
        mem_available_bytes=400,
        swap_free_bytes=0,
        cpu_count=2,
        load_1m=5.0,
    )
    with pytest.raises(RunGuardError) as raised:
        require_host_resources(
            snapshot,
            min_mem_available_bytes=900,
            min_swap_free_bytes=100,
        )
    assert raised.value.code == "HOST_RESOURCE_GATE_FAILED"
    assert {row["resource"] for row in raised.value.detail} == {
        "mem_available_bytes",
        "swap_free_bytes",
        "load_1m",
    }


def test_single_flight_metadata_is_private_and_terminal(tmp_path: Path) -> None:
    context = multiprocessing.get_context("fork")
    ready, release = context.Event(), context.Event()
    process = context.Process(target=_hold_guard, args=(str(tmp_path), ready, release))
    process.start()
    assert ready.wait(10)
    try:
        with pytest.raises(RunGuardError) as raised:
            with RunGuard(
                tmp_path,
                campaign_id="campaign-two",
                request_id="request-two",
                release_commit=_RELEASE,
                config_digest=_DIGEST,
                wall_seconds=60,
            ):
                pass
        assert raised.value.code == "RUN_ALREADY_ACTIVE"
        assert raised.value.detail["campaign_id"] == "campaign-one"
    finally:
        release.set()
        process.join(10)
    assert process.exitcode == 0

    state_path = tmp_path / ".dharma" / "forge_lab" / "run_guard" / "run_state.json"
    payload = json.loads(state_path.read_text(encoding="utf-8"))
    assert payload["status"] == "succeeded"
    assert payload["release_commit"] == _RELEASE
    assert payload["config_digest"] == _DIGEST
    assert "identity_digest" in payload
    assert payload["identity_digest"] == run_state_identity_digest(payload)
    assert os.stat(state_path).st_mode & 0o777 == 0o600
    assert os.stat(state_path.parent).st_mode & 0o777 == 0o700


def test_deadline_is_checked_before_next_operation(tmp_path: Path) -> None:
    ticks = iter((10.0, 11.2, 11.2))
    with pytest.raises(RunGuardError) as raised:
        with RunGuard(
            tmp_path,
            campaign_id="campaign",
            request_id="request",
            release_commit=_RELEASE,
            config_digest=_DIGEST,
            wall_seconds=1,
            clock=lambda: next(ticks),
        ) as guard:
            guard.checkpoint()
    assert raised.value.code == "CAMPAIGN_WALL_DEADLINE_REACHED"
    state = json.loads(
        (tmp_path / ".dharma" / "forge_lab" / "run_guard" / "run_state.json").read_text()
    )
    assert state["status"] == "wall_timeout"


def test_context_cannot_report_success_after_wall_deadline(tmp_path: Path) -> None:
    ticks = iter((10.0, 11.2, 11.2))

    with pytest.raises(RunGuardError) as raised:
        with RunGuard(
            tmp_path,
            campaign_id="campaign",
            request_id="request",
            release_commit=_RELEASE,
            config_digest=_DIGEST,
            wall_seconds=1,
            clock=lambda: next(ticks),
        ):
            # Simulates one bounded operation returning after the deadline
            # without having called an intermediate checkpoint.
            pass

    assert raised.value.code == "CAMPAIGN_WALL_DEADLINE_REACHED"
    state = json.loads(
        (tmp_path / ".dharma" / "forge_lab" / "run_guard" / "run_state.json").read_text()
    )
    assert state["status"] == "wall_timeout"
    assert state["elapsed_seconds"] >= 1.0


def test_failed_context_releases_lock_and_records_failure(tmp_path: Path) -> None:
    with pytest.raises(RuntimeError):
        with RunGuard(
            tmp_path,
            campaign_id="campaign",
            request_id="request",
            release_commit=_RELEASE,
            config_digest=_DIGEST,
            wall_seconds=60,
        ):
            raise RuntimeError("boom")
    with RunGuard(
        tmp_path,
        campaign_id="campaign",
        request_id="retry",
        release_commit=_RELEASE,
        config_digest=_DIGEST,
        wall_seconds=60,
    ):
        pass


def test_single_flight_lock_symlink_is_rejected(tmp_path: Path) -> None:
    guard_root = tmp_path / ".dharma" / "forge_lab" / "run_guard"
    guard_root.mkdir(parents=True, mode=0o700)
    guard_root.chmod(0o700)
    outside = tmp_path / "outside.lock"
    outside.write_text("do-not-follow", encoding="utf-8")
    (guard_root / "single-flight.lock").symlink_to(outside)

    with pytest.raises(RunGuardError) as raised:
        with RunGuard(
            tmp_path,
            campaign_id="campaign",
            request_id="request",
            release_commit=_RELEASE,
            config_digest=_DIGEST,
            wall_seconds=60,
        ):
            pass

    assert raised.value.code == "RUN_GUARD_LOCK_UNTRUSTED"
    assert outside.read_text(encoding="utf-8") == "do-not-follow"
