"""Fail-closed fixed-state contract for the systemd RSI entrypoint."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from dharma_swarm.forge_lab.scheduled_run import (
    ATTEMPT_SCHEMA,
    MAX_UNATTENDED_LOAD_PER_CPU,
    MIN_UNATTENDED_MEM_AVAILABLE_BYTES,
    MIN_UNATTENDED_SWAP_FREE_BYTES,
    SCHEDULE_SCHEMA,
    ScheduledRunError,
    run_unattended,
)
from dharma_swarm.forge_lab.run_guard import HostResources, RunGuard


@pytest.fixture(autouse=True)
def _healthy_scheduled_host(monkeypatch) -> None:
    monkeypatch.setattr(
        "dharma_swarm.forge_lab.scheduled_run.host_resources",
        lambda: HostResources(
            mem_available_bytes=MIN_UNATTENDED_MEM_AVAILABLE_BYTES * 2,
            swap_free_bytes=MIN_UNATTENDED_SWAP_FREE_BYTES * 2,
            cpu_count=4,
            load_1m=1.0,
        ),
    )


def _private_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")
    path.chmod(0o600)


def _schedule(root: Path, *, enabled: bool = True) -> dict:
    evidence = root / "evidence"
    envelope, identity, provider = (
        evidence / "envelope.json",
        evidence / "identity.json",
        evidence / "provider.json",
    )
    for path in (envelope, identity, provider):
        _private_json(path, {})
    return {
        "schema": SCHEDULE_SCHEMA,
        "enabled": enabled,
        "manifest_digest": "sha256:" + "a" * 64,
        "operator_envelope_path": str(envelope),
        "identity_receipt_path": str(identity),
        "provider_receipt_path": str(provider),
        "min_mem_available_bytes": MIN_UNATTENDED_MEM_AVAILABLE_BYTES,
        "min_swap_free_bytes": MIN_UNATTENDED_SWAP_FREE_BYTES,
        "max_load_per_cpu": MAX_UNATTENDED_LOAD_PER_CPU,
    }


def _install_manifest(monkeypatch) -> None:
    monkeypatch.setattr(
        "dharma_swarm.forge_lab.campaign_control.load_manifest",
        lambda *_args, **_kwargs: {
            "campaign_name": "forge-lab-test",
            "source": {"release_commit": "b" * 40},
        },
    )


def test_missing_schedule_fails_and_writes_private_attempt(tmp_path: Path) -> None:
    with pytest.raises(ScheduledRunError) as raised:
        run_unattended(state_root=tmp_path)
    assert raised.value.code == "SCHEDULE_EVIDENCE_MISSING"
    attempt = raised.value.result["attempt"]
    receipt = Path(attempt["receipt_path"])
    assert json.loads(receipt.read_text())["schema"] == ATTEMPT_SCHEMA
    assert os.stat(receipt).st_mode & 0o777 == 0o600


def test_disabled_schedule_never_reaches_campaign(monkeypatch, tmp_path: Path) -> None:
    path = tmp_path / ".dharma" / "forge_lab" / "schedule" / "active.json"
    _private_json(path, _schedule(tmp_path, enabled=False))
    monkeypatch.setattr(
        "dharma_swarm.forge_lab.campaign_control.run_campaign",
        lambda *args, **kwargs: pytest.fail("campaign dispatch must stay closed"),
    )
    with pytest.raises(ScheduledRunError) as raised:
        run_unattended(state_root=tmp_path)
    assert raised.value.code == "SCHEDULE_DISABLED"


def test_schedule_rejects_evidence_outside_state(tmp_path: Path) -> None:
    value = _schedule(tmp_path)
    outside = tmp_path.parent / f"outside-{tmp_path.name}.json"
    _private_json(outside, {})
    value["provider_receipt_path"] = str(outside)
    path = tmp_path / ".dharma" / "forge_lab" / "schedule" / "active.json"
    _private_json(path, value)
    with pytest.raises(ScheduledRunError) as raised:
        run_unattended(state_root=tmp_path)
    assert raised.value.code == "SCHEDULE_EVIDENCE_OUTSIDE_STATE"


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("min_mem_available_bytes", MIN_UNATTENDED_MEM_AVAILABLE_BYTES - 1),
        ("min_swap_free_bytes", MIN_UNATTENDED_SWAP_FREE_BYTES - 1),
        ("max_load_per_cpu", MAX_UNATTENDED_LOAD_PER_CPU + 0.01),
    ),
)
def test_schedule_cannot_weaken_compiled_resource_boundary(
    monkeypatch, tmp_path: Path, field: str, value: int | float
) -> None:
    assert MIN_UNATTENDED_MEM_AVAILABLE_BYTES > 0
    assert MIN_UNATTENDED_SWAP_FREE_BYTES > 0
    schedule = _schedule(tmp_path)
    schedule[field] = value
    path = tmp_path / ".dharma" / "forge_lab" / "schedule" / "active.json"
    _private_json(path, schedule)
    monkeypatch.setattr(
        "dharma_swarm.forge_lab.campaign_control.run_campaign",
        lambda *_args, **_kwargs: pytest.fail("weak schedule must not dispatch"),
    )

    with pytest.raises(ScheduledRunError) as raised:
        run_unattended(state_root=tmp_path)

    assert raised.value.code == "INVALID_SCHEDULE"


def test_blocked_campaign_is_non_success_and_idempotent_request(monkeypatch, tmp_path: Path) -> None:
    value = _schedule(tmp_path)
    path = tmp_path / ".dharma" / "forge_lab" / "schedule" / "active.json"
    _private_json(path, value)
    seen: list[dict] = []
    _install_manifest(monkeypatch)

    def blocked(_manifest, **kwargs):
        seen.append(kwargs)
        return {"disposition": "BLOCKED", "receipt_path": "/state/blocked.json"}

    monkeypatch.setattr("dharma_swarm.forge_lab.campaign_control.run_campaign", blocked)
    with pytest.raises(ScheduledRunError) as raised:
        run_unattended(state_root=tmp_path)
    assert raised.value.code == "SCHEDULED_CAMPAIGN_BLOCKED"
    assert seen[0]["request_id"] == "scheduled-aaaaaaaaaaaaaaaa"
    assert raised.value.result["attempt"]["campaign_receipt"] == "/state/blocked.json"


def test_schedule_respects_global_single_flight_before_campaign_dispatch(
    monkeypatch, tmp_path: Path
) -> None:
    value = _schedule(tmp_path)
    path = tmp_path / ".dharma" / "forge_lab" / "schedule" / "active.json"
    _private_json(path, value)
    _install_manifest(monkeypatch)
    monkeypatch.setattr(
        "dharma_swarm.forge_lab.campaign_control.run_campaign",
        lambda *_args, **_kwargs: pytest.fail("second scheduler must not dispatch"),
    )

    with RunGuard(
        tmp_path,
        campaign_id="already-running",
        request_id="first-request",
        release_commit="b" * 40,
        config_digest="sha256:" + "c" * 64,
        wall_seconds=60,
    ):
        with pytest.raises(ScheduledRunError) as raised:
            run_unattended(state_root=tmp_path)

    assert raised.value.code == "RUN_ALREADY_ACTIVE"
    assert raised.value.result["attempt"]["status"] == "blocked"
