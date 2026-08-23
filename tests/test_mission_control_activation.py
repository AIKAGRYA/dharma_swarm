from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

import pytest

import dharma_swarm.mission_control_activation as activation_module
from dharma_swarm.mission_control_activation import (
    OBSERVER_HEALTH_ENDPOINT,
    OBSERVER_HEALTH_SCHEMA_VERSION,
    OBSERVER_HEALTH_UNIT,
    SADHANA_ACTIVATION_CAMPAIGN_ID,
    activation_barrier_from_config,
    load_observer_health_acceptance,
)
from dharma_swarm.mission_control_contract import MissionControlError


def _canonical(payload: object, *, newline: bool = True) -> bytes:
    raw = json.dumps(
        payload,
        allow_nan=False,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("ascii")
    return raw + (b"\n" if newline else b"")


def _payload() -> dict:
    release = "a" * 40
    payload = {
        "schema_version": OBSERVER_HEALTH_SCHEMA_VERSION,
        "campaign_id": SADHANA_ACTIVATION_CAMPAIGN_ID,
        "release_sha": release,
        "service_unit_digest": "b" * 64,
        "endpoint": OBSERVER_HEALTH_ENDPOINT,
        "probe_started_at": "2026-08-23T01:00:00Z",
        "probe_finished_at": "2026-08-23T01:00:01Z",
        "consecutive_successes": 20,
        "response_sha256_sequence": [f"{index:064x}" for index in range(20)],
        "listener_process_identity": {
            "unit": OBSERVER_HEALTH_UNIT,
            "main_pid": 4242,
            "proc_start_ticks": 12345,
            "cmdline_sha256": "c" * 64,
            "socket_inode": 555,
            "uid": 991,
            "gid": 991,
            "forbidden_path_count": 9,
            "canonical_path_visible": False,
            "release_sha": release,
        },
        "dispatch_enabled_during_probe": False,
        "observer_identity_separated": True,
        "projection_source_separated": True,
        "canonical_paths_inaccessible": True,
        "health_is_work_evidence": False,
        "verdict": "PASS",
    }
    payload["receipt_digest"] = "sha256:" + hashlib.sha256(
        _canonical(payload, newline=False)
    ).hexdigest()
    return payload


def _write(path: Path, payload: dict) -> str:
    raw = _canonical(payload)
    path.write_bytes(raw)
    path.chmod(0o600)
    return hashlib.sha256(raw).hexdigest()


def test_observer_health_credential_is_exact_activation_not_work(tmp_path: Path) -> None:
    path = tmp_path / "observer_health_acceptance"
    digest = _write(path, _payload())

    accepted = load_observer_health_acceptance(
        path,
        expected_file_sha256=digest,
        expected_campaign_id=SADHANA_ACTIVATION_CAMPAIGN_ID,
    )

    assert accepted.file_sha256 == digest
    assert accepted.listener_main_pid == 4242
    assert accepted.release_sha == "a" * 40


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("dispatch_enabled_during_probe", True),
        ("health_is_work_evidence", True),
        ("observer_identity_separated", False),
        ("canonical_paths_inaccessible", False),
        ("consecutive_successes", 19),
    ],
)
def test_observer_health_claim_drift_fails_closed(
    tmp_path: Path,
    field: str,
    value: object,
) -> None:
    payload = _payload()
    payload[field] = value
    canonical = dict(payload)
    canonical.pop("receipt_digest")
    payload["receipt_digest"] = "sha256:" + hashlib.sha256(
        _canonical(canonical, newline=False)
    ).hexdigest()
    path = tmp_path / "observer_health_acceptance"
    digest = _write(path, payload)

    with pytest.raises(MissionControlError, match="claims conflict"):
        load_observer_health_acceptance(
            path,
            expected_file_sha256=digest,
            expected_campaign_id=SADHANA_ACTIVATION_CAMPAIGN_ID,
        )


def test_observer_health_digest_duplicate_and_link_attacks_fail(
    tmp_path: Path,
) -> None:
    path = tmp_path / "observer_health_acceptance"
    digest = _write(path, _payload())
    with pytest.raises(MissionControlError, match="file digest conflicts"):
        load_observer_health_acceptance(
            path,
            expected_file_sha256="f" * 64,
            expected_campaign_id=SADHANA_ACTIVATION_CAMPAIGN_ID,
        )

    linked = tmp_path / "linked"
    os.link(path, linked)
    with pytest.raises(MissionControlError, match="custody is invalid"):
        load_observer_health_acceptance(
            linked,
            expected_file_sha256=digest,
            expected_campaign_id=SADHANA_ACTIVATION_CAMPAIGN_ID,
        )
    linked.unlink()
    symlink = tmp_path / "symlink"
    symlink.symlink_to(path)
    with pytest.raises(MissionControlError, match="could not be opened"):
        load_observer_health_acceptance(
            symlink,
            expected_file_sha256=digest,
            expected_campaign_id=SADHANA_ACTIVATION_CAMPAIGN_ID,
        )


@pytest.mark.parametrize("flag", ["O_NOFOLLOW", "O_DIRECTORY"])
def test_observer_health_requires_secure_open_flags(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    flag: str,
) -> None:
    path = tmp_path / "observer_health_acceptance"
    digest = _write(path, _payload())
    monkeypatch.delattr(activation_module.os, flag)

    with pytest.raises(MissionControlError, match="O_NOFOLLOW and O_DIRECTORY"):
        load_observer_health_acceptance(
            path,
            expected_file_sha256=digest,
            expected_campaign_id=SADHANA_ACTIVATION_CAMPAIGN_ID,
        )


def test_production_campaign_requires_both_activation_pins(tmp_path: Path) -> None:
    with pytest.raises(MissionControlError, match="requires the exact"):
        activation_barrier_from_config(SADHANA_ACTIVATION_CAMPAIGN_ID, None, "")
    assert activation_barrier_from_config("generic-campaign", None, "") is None
    with pytest.raises(MissionControlError, match="partial"):
        activation_barrier_from_config("generic-campaign", tmp_path / "receipt", "")
