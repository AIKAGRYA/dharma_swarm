from __future__ import annotations

import base64
import copy
import errno
import hashlib
import inspect
import json
import os
import re
import shutil
import socket
import stat
import subprocess
import sys
import tempfile
import threading
import zipfile
from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from pathlib import Path, PurePosixPath
from types import SimpleNamespace

import pytest

from scripts.runtime import sadhana_release as release


@pytest.fixture(autouse=True)
def _stable_private_tmp_group(tmp_path: Path) -> None:
    """Keep custody fixtures portable across macOS private-tmp group inheritance."""
    os.chown(tmp_path, -1, os.getegid())


def _payload() -> dict[str, object]:
    return release._manifest_payload(
        release_sha="1" * 40,
        integration_base_sha="9" * 40,
        bundle_file="candidate.bundle",
        bundle_sha256="2" * 64,
        work_packet_path="reports/agentops/work_packets/organism-rewire-WP-SADHANA-VPS-RELEASE-P0.json",
        work_packet_sha256="3" * 64,
        work_packet_digest="4" * 64,
        receipt_file="closeout.json",
        receipt_sha256="5" * 64,
        input_set_manifest_sha256="6" * 64,
        input_set_archive_sha256="7" * 64,
        input_set_digest="8" * 64,
        deployment_known_hosts_sha256=release.DEPLOYMENT_KNOWN_HOSTS_SHA256,
        tracked_source_manifest_sha256="a" * 64,
        tracked_source_digest="b" * 64,
        tracked_source_entry_count=1,
    )


def _reseal(payload: dict[str, object]) -> dict[str, object]:
    payload["manifest_digest"] = release.manifest_digest(payload)
    return payload


def _write_self_digest_receipt(
    path: Path,
    payload: dict[str, object],
    *,
    digest_field: str = "receipt_digest",
) -> dict[str, object]:
    """Write one exact private canonical receipt for a boundary fixture."""
    payload[digest_field] = release._canonical_self_digest(payload, digest_field)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(release._canonical_bytes(payload) + b"\n")
    path.chmod(0o600)
    return payload


def _positive_bearer_probe_payload() -> dict[str, object]:
    return {
        "probe_kind": "unsupported_action_501_no_inbox_write",
        "authenticated_unsupported_response_observed": True,
        "connected_dashboard_peer_identity_proven": True,
        "normal_and_emergency_inboxes_unchanged": True,
        "request_accepted": False,
        "decision_or_effect_state_proven": False,
    }


def _account_ui_confirmation_fixture(
    *,
    release_sha: str,
    operator_login_sha256: str,
    observed_at: str = "2026-08-23T01:00:00Z",
) -> dict[str, object]:
    empty_ledger_digest = release._empty_account_ui_inbox_ledger_sha256()
    payload: dict[str, object] = {
        "schema_version": release.ACCOUNT_UI_CONFIRMATION_SCHEMA_VERSION,
        "campaign_id": release.MISSION_ID,
        "release_sha": release_sha,
        "client_request_id_sha256": "1" * 64,
        "source_candidate_sha256": "2" * 64,
        "viewport_width_css_px_reported": 390,
        "document_width_css_px_reported": 390,
        "visual_viewport_width_css_px_reported": 390,
        "coarse_pointer_reported": True,
        "touch_capability_reported": True,
        "trusted_browser_event_reported": True,
        "explicit_confirmation_gesture_reported": True,
        "dashboard_rendered_reported": True,
        "private_tailnet_https": True,
        "identity_header_injected": True,
        "operator_account_allowlist_match": True,
        "operator_login_sha256": operator_login_sha256,
        "normal_control_request_sent": False,
        "external_message_sent": False,
        "physical_device_attested": False,
        "human_identity_attested": False,
        "predispatch_gate_receipt_digest": "sha256:" + "3" * 64,
        "normal_and_emergency_inbox_ledger_sha256_before": empty_ledger_digest,
        "normal_and_emergency_inbox_ledger_sha256_after": empty_ledger_digest,
        "normal_and_emergency_inboxes_unchanged": True,
        "observed_at": observed_at,
        "receipt_digest": "",
    }
    payload["receipt_digest"] = release._canonical_self_digest(
        payload, "receipt_digest"
    )
    return payload


def _account_ui_candidate_fixture(
    *,
    release_sha: str,
    operator_login_sha256: str,
    gate_digest: str,
    hmac_secret: bytes,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "schema_version": release.ACCOUNT_UI_CONFIRMATION_CANDIDATE_SCHEMA_VERSION,
        "campaign_id": release.MISSION_ID,
        "release_sha": release_sha,
        "client_request_id": "4b2d7f48-14a5-4eed-a814-62d08cb8d4b0",
        "issued_at": "2026-08-23T00:59:30Z",
        "expires_at": "2026-08-23T01:01:00Z",
        "viewport_width_css_px_reported": 390,
        "document_width_css_px_reported": 390,
        "visual_viewport_width_css_px_reported": 390,
        "coarse_pointer_reported": True,
        "touch_capability_reported": True,
        "trusted_browser_event_reported": True,
        "explicit_confirmation_gesture_reported": True,
        "dashboard_rendered_reported": True,
        "origin": "https://sadhana.example.ts.net",
        "operator_login_sha256": operator_login_sha256,
        "private_tailnet_https": True,
        "identity_header_injected": True,
        "operator_account_allowlist_match": True,
        "normal_control_request_sent": False,
        "external_message_sent": False,
        "physical_device_attested": False,
        "human_identity_attested": False,
        "predispatch_gate_receipt_digest": gate_digest,
        "normal_inbox_empty_ledger_sha256": (
            release._empty_account_ui_inbox_ledger_sha256()
        ),
        "emergency_inbox_empty_ledger_sha256": (
            release._empty_account_ui_inbox_ledger_sha256()
        ),
        "control_inboxes_empty_at_last_prepublication_scan": True,
        "observed_at": "2026-08-23T00:59:40Z",
        "hmac_sha256": "",
    }
    payload["hmac_sha256"] = release._account_ui_candidate_mac(
        payload, hmac_secret
    )
    return payload


def _standby_activation_harness(
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[
    dict[str, bool],
    list[tuple[str, ...]],
    Callable[..., subprocess.CompletedProcess[str]],
]:
    state = {
        "target_active": False,
        "target_enabled": False,
        "timer_active": False,
        "timer_enabled": False,
        "campaign_masked": False,
        "serve_active": False,
    }

    def active(unit, **_kwargs):  # noqa: ANN001, ANN202
        return (
            state["target_active"]
            if unit == release.STANDBY_TARGET
            else state["timer_active"]
            if unit == release.STANDBY_STOP_TIMER
            else state["serve_active"]
            if unit == release.STANDBY_REPLICATION_SERVE_UNIT
            else False
        )

    def enabled(unit, **_kwargs):  # noqa: ANN001, ANN202
        return (
            state["target_enabled"]
            if unit == release.STANDBY_TARGET
            else state["timer_enabled"]
            if unit == release.STANDBY_STOP_TIMER
            else False
        )

    monkeypatch.setattr(release, "_unit_active", active)
    monkeypatch.setattr(
        release,
        "_unit_inactive",
        lambda unit, **kwargs: not active(unit, **kwargs),
    )
    monkeypatch.setattr(release, "_unit_enabled", enabled)
    monkeypatch.setattr(
        release,
        "_unit_disabled",
        lambda unit, **kwargs: not enabled(unit, **kwargs),
    )
    monkeypatch.setattr(
        release,
        "_unit_masked",
        lambda unit, **_kwargs: state["campaign_masked"]
        and unit in release.CAMPAIGN_UNITS,
    )
    monkeypatch.setattr(
        release,
        "_validate_installed_standby_replication_route",
        lambda **_kwargs: None,
    )
    monkeypatch.setattr(
        release,
        "_require_standby_tailscale_route_absent",
        lambda **_kwargs: None,
    )
    monkeypatch.setattr(
        release,
        "_load_standby_tailscale_ownership_receipt",
        lambda *_args, **_kwargs: {
            "receipt_digest": "sha256:" + "9" * 64,
            "config": release.STANDBY_TAILSCALE_STATUS,
            "config_sha256": release._tailscale_config_digest(
                release.STANDBY_TAILSCALE_STATUS
            ),
        },
    )
    monkeypatch.setattr(
        release,
        "_read_tailscale_config",
        lambda **_kwargs: release.TAILSCALE_EMPTY_CONFIG,
    )
    monkeypatch.setattr(
        release,
        "_read_tailscale_status",
        lambda **_kwargs: release.STANDBY_TAILSCALE_STATUS,
    )
    monkeypatch.setattr(
        release,
        "_stop_standby_serve_for_compensation",
        lambda **_kwargs: state.update(serve_active=False),
    )
    calls: list[tuple[str, ...]] = []

    def runner(argv, **_kwargs):  # noqa: ANN001, ANN202
        command = tuple(argv)
        calls.append(command)
        if command[1:3] == ("mask", "--now"):
            state["campaign_masked"] = True
        elif command[1:3] == ("enable", "--now"):
            if command[3:] != (
                release.STANDBY_STOP_TIMER,
                release.STANDBY_TARGET,
            ):
                raise AssertionError(f"unexpected standby enable: {command!r}")
            state.update(
                target_active=True,
                target_enabled=True,
                timer_active=True,
                timer_enabled=True,
                serve_active=True,
            )
        elif command[1:3] == ("disable", "--now"):
            if command[3] == release.STANDBY_TARGET:
                state.update(
                    target_active=False,
                    target_enabled=False,
                    serve_active=False,
                )
            elif command[3] == release.STANDBY_STOP_TIMER:
                state.update(timer_active=False, timer_enabled=False)
        return subprocess.CompletedProcess(argv, 0, "", "")

    return state, calls, runner


def _input_fixture(
    root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[dict[str, object], dict[str, bytes]]:
    contents = {
        release.OBJECTIVE_INPUT_PATH: b"exact objective fixture\n",
        "receipts/evidence.v1.json": b'{"claim":"observed, not authority"}\n',
    }
    objective_sha = hashlib.sha256(contents[release.OBJECTIVE_INPUT_PATH]).hexdigest()
    monkeypatch.setattr(release, "OBJECTIVE_SHA256", objective_sha)
    monkeypatch.setattr(release, "REQUIRED_INPUT_TARGETS", frozenset(contents))
    monkeypatch.setattr(
        release,
        "REQUIRED_INPUT_SHA256",
        {release.OBJECTIVE_INPUT_PATH: objective_sha},
    )
    monkeypatch.setattr(
        release,
        "REQUIRED_INPUT_CONSUMERS",
        {
            release.OBJECTIVE_INPUT_PATH: "observed_input_loader",
            "receipts/evidence.v1.json": "immutable_evidence",
        },
    )
    entries: list[dict[str, object]] = []
    for relative, raw in contents.items():
        source = root.joinpath(*PurePosixPath(relative).parts)
        source.parent.mkdir(parents=True, exist_ok=True)
        source.write_bytes(raw)
        source.chmod(0o600)
        loader = relative == release.OBJECTIVE_INPUT_PATH
        entries.append(
            {
                "source_relative_path": relative,
                "target_relative_path": relative,
                "sha256": hashlib.sha256(raw).hexdigest(),
                "bytes": len(raw),
                "custody": ("service_hash_pinned" if loader else "root_immutable"),
                "consumer": (
                    "observed_input_loader" if loader else "immutable_evidence"
                ),
            }
        )
    entries.sort(key=lambda entry: str(entry["target_relative_path"]))
    payload: dict[str, object] = {
        "schema_version": release.INPUT_SET_SCHEMA_VERSION,
        "mission_id": release.MISSION_ID,
        "objective_sha256": objective_sha,
        "target_root": str(release.INPUT_SET_TARGET_ROOT),
        "entries": entries,
        "input_set_digest": "1" * 64,
    }
    payload["input_set_digest"] = release._input_set_digest(payload)
    return payload, contents


def _reject(field: str, value: object) -> None:
    payload = _payload()
    payload[field] = value
    _reseal(payload)
    with pytest.raises(release.ReleaseContractError):
        release.validate_manifest(payload)


def test_manifest_is_explicitly_noncanonical_unmerged_and_zero_cash() -> None:
    payload = release.validate_manifest(_payload())
    assert payload["release_class"] == "unmerged-deployment-candidate"
    assert payload["canonical_or_merged"] is False
    assert payload["cash_budget_usd"] == 0
    assert payload["automatic_failover"] is False
    assert payload["standby_writer_enabled"] is False


def test_deployment_known_hosts_is_pinned_public_input_without_tofu(
    tmp_path: Path,
) -> None:
    admitted = tmp_path / "known-hosts"
    admitted.write_bytes(b"meghadharma-cloud ssh-ed25519 AAAAfixture\n")
    admitted.chmod(0o600)
    assert release._read_deployment_known_hosts(admitted) == admitted.read_bytes()

    linked = tmp_path / "known-hosts-link"
    linked.symlink_to(admitted)
    with pytest.raises(release.ReleaseContractError, match="custody"):
        release._read_deployment_known_hosts(linked)

    admitted.write_bytes(b"-----BEGIN OPEN" + b"SSH PRIVATE KEY-----\n")
    with pytest.raises(release.ReleaseContractError, match="secret material"):
        release._read_deployment_known_hosts(admitted)


def test_input_set_archive_is_closed_hash_pinned_and_secret_free(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source_root = tmp_path / "source"
    source_root.mkdir(mode=0o700)
    payload, contents = _input_fixture(source_root, monkeypatch)
    archive = tmp_path / release.INPUT_SET_ARCHIVE_FILE
    release.build_input_set_archive(
        payload,
        source_root=source_root,
        destination=archive,
    )
    admitted = release.validate_input_set_archive(payload, archive)
    assert admitted == contents
    assert stat.S_IMODE(archive.stat().st_mode) == 0o600

    objective = source_root / release.OBJECTIVE_INPUT_PATH
    objective.write_bytes(b"mutated objective fixture\n")
    objective.chmod(0o600)
    destination = tmp_path / "second" / release.INPUT_SET_ARCHIVE_FILE
    destination.parent.mkdir()
    with pytest.raises(release.ReleaseContractError, match="source"):
        release.build_input_set_archive(
            payload,
            source_root=source_root,
            destination=destination,
        )
    assert not destination.exists()

    objective.write_bytes(contents[release.OBJECTIVE_INPUT_PATH])
    secret = source_root / "receipts/evidence.v1.json"
    secret.write_bytes(b"OLLAMA_API_KEY=must-never-enter-input-set\n")
    secret.chmod(0o600)
    forged = copy.deepcopy(payload)
    evidence_entry = forged["entries"][1]
    evidence_entry["bytes"] = secret.stat().st_size
    evidence_entry["sha256"] = hashlib.sha256(secret.read_bytes()).hexdigest()
    forged["input_set_digest"] = release._input_set_digest(forged)
    with pytest.raises(release.ReleaseContractError, match="secret material"):
        release.validate_input_set_sources(forged, source_root)


def test_static_input_manifest_renderer_maps_exact_sources_and_custody(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source_root = tmp_path / "source"
    source_root.mkdir(mode=0o700)
    expected, _contents = _input_fixture(source_root, monkeypatch)
    rendered = release.render_static_input_set_manifest(source_root)
    assert rendered == expected

    output_root = tmp_path / "output"
    output_root.mkdir(mode=0o700)
    output = output_root / release.INPUT_SET_MANIFEST_FILE
    release.write_static_input_set_manifest(
        source_root=source_root,
        destination=output,
    )
    assert stat.S_IMODE(output.stat().st_mode) == 0o600
    assert release._secure_json(output, require_private=True) == expected


def test_input_manifest_rejects_explicitly_revoked_source_digest(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source_root = tmp_path / "source"
    source_root.mkdir(mode=0o700)
    payload, _contents = _input_fixture(source_root, monkeypatch)
    objective_sha = str(payload["entries"][0]["sha256"])
    monkeypatch.setattr(
        release,
        "REVOKED_INPUT_SHA256",
        {release.OBJECTIVE_INPUT_PATH: frozenset({objective_sha})},
    )
    with pytest.raises(release.ReleaseContractError, match="revoked campaign input"):
        release.validate_input_set_manifest(payload)


def test_runtime_preparation_env_is_derived_from_sealed_inputs_and_unique_verifier(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    input_root = tmp_path / "etc/dharma-sadhana/inputs"
    input_root.mkdir(parents=True, mode=0o700)
    service_uid = os.geteuid() if os.geteuid() > 0 else 1
    service_gid = os.getegid() if os.getegid() > 0 else 1
    account = SimpleNamespace(
        pw_name="dharma-sadhana",
        pw_uid=service_uid,
        pw_gid=service_gid,
    )
    objective = b"sealed objective\n"
    objective_sha = hashlib.sha256(objective).hexdigest()
    roster_payload = {
        "schema": "dharma.sadhana.agent_roster.v1",
        "campaign_id": release.MISSION_ID,
        "objective_sha256": objective_sha,
        "agents": [
            {
                "name": "sadhana-seat-6",
                "role": "validator",
                "provider": "ollama",
            }
        ],
    }
    contents: dict[str, bytes] = {
        relative: f"sealed {label}\n".encode("ascii")
        for label, relative in release.RUNTIME_PREPARATION_INPUT_PATHS.items()
    }
    contents[release.OBJECTIVE_INPUT_PATH] = objective
    roster_relative = release.RUNTIME_PREPARATION_INPUT_PATHS["roster"]
    contents[roster_relative] = release._canonical_bytes(roster_payload) + b"\n"
    consumers = {target: "immutable_evidence" for target in contents}
    consumers.update(
        {
            release.RUNTIME_PREPARATION_INPUT_PATHS["contracts"]: (
                "bootstrap_goal_loader"
            ),
            roster_relative: "roster_loader",
            release.RUNTIME_PREPARATION_INPUT_PATHS["observed_source"]: (
                "observed_input_loader"
            ),
            release.RUNTIME_PREPARATION_INPUT_PATHS["evaluator"]: "oracle_loader",
            release.RUNTIME_PREPARATION_INPUT_PATHS["policy"]: "oracle_loader",
        }
    )
    entries: list[dict[str, object]] = []
    for relative, raw in sorted(contents.items()):
        target = input_root.joinpath(*PurePosixPath(relative).parts)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(raw)
        target.chmod(0o600)
        if relative == roster_relative:
            os.chown(target, service_uid, service_gid)
        consumer = consumers[relative]
        entries.append(
            {
                "source_relative_path": relative,
                "target_relative_path": relative,
                "sha256": hashlib.sha256(raw).hexdigest(),
                "bytes": len(raw),
                "custody": (
                    "root_immutable"
                    if consumer == "immutable_evidence"
                    else "service_hash_pinned"
                ),
                "consumer": consumer,
            }
        )
    monkeypatch.setattr(release, "INPUT_SET_TARGET_ROOT", input_root)
    monkeypatch.setattr(release, "OBJECTIVE_SHA256", objective_sha)
    monkeypatch.setattr(release, "REQUIRED_INPUT_TARGETS", frozenset(contents))
    monkeypatch.setattr(
        release,
        "REQUIRED_INPUT_SHA256",
        {release.OBJECTIVE_INPUT_PATH: objective_sha},
    )
    monkeypatch.setattr(release, "REVOKED_INPUT_SHA256", {})
    monkeypatch.setattr(release, "REQUIRED_INPUT_CONSUMERS", consumers)
    state_dir = tmp_path / "var/lib/dharma-sadhana/state"
    state_dir.mkdir(parents=True, mode=0o700)
    admission_projection = (
        state_dir / "release-admission/staged-release-admission.v1.json"
    )
    prepared_root = state_dir / "prepared-runtime-manifests"
    monkeypatch.setattr(release, "STATE_ROOT", str(state_dir))
    monkeypatch.setattr(
        release,
        "PREPARED_RELEASE_ADMISSION_PROJECTION",
        admission_projection,
    )
    monkeypatch.setattr(release, "PREPARED_RUNTIME_MANIFEST_ROOT", prepared_root)
    manifest: dict[str, object] = {
        "schema_version": release.INPUT_SET_SCHEMA_VERSION,
        "mission_id": release.MISSION_ID,
        "objective_sha256": objective_sha,
        "target_root": str(input_root),
        "entries": entries,
        "input_set_digest": "1" * 64,
    }
    manifest["input_set_digest"] = release._input_set_digest(manifest)
    release_sha = "a" * 40
    release_path = tmp_path / "opt/dharma-sadhana/releases" / release_sha
    release_path.mkdir(parents=True)
    admission = {
        "release_sha": release_sha,
        "release_root": str(release_path.resolve()),
        "release_input_set_digest": manifest["input_set_digest"],
    }
    supervisor_env = tmp_path / "supervisor.env"
    _write_private_env(
        supervisor_env,
        {
            "SADHANA_WRITER_LOCK_PATH": str(state_dir / "writer.lock"),
            "SADHANA_PROJECTION_PATH": str(state_dir / "projection.json"),
            "SADHANA_OPERATOR_ID": "operator",
            "SADHANA_MAX_DISPATCH_PER_CYCLE": "1",
            "SADHANA_CYCLE_INTERVAL_SECONDS": "30",
            "SADHANA_FRESHNESS_SECONDS": "120",
            "SADHANA_LEASE_ROOT": str(state_dir / "leases"),
            "SADHANA_AGENT_ROSTER_PATH": str(
                input_root.joinpath(*PurePosixPath(roster_relative).parts)
            ),
            "SADHANA_AGENT_ROSTER_SHA256": hashlib.sha256(
                contents[roster_relative]
            ).hexdigest(),
            "SADHANA_OBJECTIVE_SHA256": objective_sha,
        },
    )
    bindings = release._runtime_preparation_environment_bindings(
        manifest,
        admission=admission,
        release_sha=release_sha,
        release_path=release_path,
        account=account,
        input_root=input_root,
        admission_projection=admission_projection,
        state_dir=state_dir,
        prepared_root=prepared_root,
        supervisor_env_path=supervisor_env,
    )
    assert set(bindings) == release._RUNTIME_PREPARATION_ENV_FIELDS
    assert bindings["SADHANA_PREP_VERIFIER_SEAT"] == "sadhana-seat-6"
    assert bindings["SADHANA_PREP_ROSTER_SHA256"] == hashlib.sha256(
        contents[roster_relative]
    ).hexdigest()
    assert bindings["SADHANA_PREP_EVALUATOR_PATH"] == str(
        input_root.joinpath(
            *PurePosixPath(
                release.RUNTIME_PREPARATION_INPUT_PATHS["evaluator"]
            ).parts
        )
    )
    assert bindings["SADHANA_PREP_EVALUATOR_SHA256"].startswith("sha256:")
    assert bindings["SADHANA_PREP_MAX_DISPATCH_PER_CYCLE"] == "1"
    assert bindings["SADHANA_PREP_CYCLE_INTERVAL_SECONDS"] == "30"
    assert bindings["SADHANA_PREP_FRESHNESS_SECONDS"] == "120"
    assert bindings["SADHANA_PREP_PROJECTION_PATH"] == str(
        release.WRITER_PROJECTION_PATH
    )

    ambiguous_roster = dict(roster_payload)
    ambiguous_roster["agents"] = [
        *roster_payload["agents"],
        {
            "name": "sadhana-seat-7",
            "role": "validator",
            "provider": "ollama",
        },
    ]
    ambiguous_raw = release._canonical_bytes(ambiguous_roster) + b"\n"
    roster_path = Path(bindings["SADHANA_PREP_ROSTER"])
    roster_path.write_bytes(ambiguous_raw)
    roster_path.chmod(0o600)
    os.chown(roster_path, service_uid, service_gid)
    ambiguous_manifest = json.loads(json.dumps(manifest))
    roster_entry = next(
        entry
        for entry in ambiguous_manifest["entries"]
        if entry["target_relative_path"] == roster_relative
    )
    roster_entry["sha256"] = hashlib.sha256(ambiguous_raw).hexdigest()
    roster_entry["bytes"] = len(ambiguous_raw)
    ambiguous_manifest["input_set_digest"] = release._input_set_digest(
        ambiguous_manifest
    )
    ambiguous_admission = dict(admission)
    ambiguous_admission["release_input_set_digest"] = ambiguous_manifest[
        "input_set_digest"
    ]
    with pytest.raises(release.ReleaseContractError, match="verifier seat"):
        release._runtime_preparation_environment_bindings(
            ambiguous_manifest,
            admission=ambiguous_admission,
            release_sha=release_sha,
            release_path=release_path,
            account=account,
            input_root=input_root,
            admission_projection=admission_projection,
            state_dir=state_dir,
            prepared_root=prepared_root,
            supervisor_env_path=supervisor_env,
        )


def test_deploy_starts_static_preparation_unit_and_root_validates_result(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(release, "RUNTIME_BINDING_RECEIPT_TARGET", tmp_path / "binding")
    monkeypatch.setattr(release, "WRITER_MARKER", tmp_path / "writer")
    monkeypatch.setattr(release, "DISPATCH_ENABLE_MARKER", tmp_path / "dispatch")
    validated: list[dict[str, object]] = []
    monkeypatch.setattr(
        release,
        "_validate_root_preparation",
        lambda **kwargs: validated.append(kwargs),
    )
    calls: list[tuple[str, ...]] = []

    def runner(
        argv: tuple[str, ...], **_kwargs: object
    ) -> subprocess.CompletedProcess[str]:
        calls.append(argv)
        if argv[1:] == ("daemon-reload",):
            return subprocess.CompletedProcess(argv, 0, "", "")
        if argv[1:] == ("is-enabled", release.RUNTIME_PREPARATION_UNIT):
            return subprocess.CompletedProcess(argv, 0, "static\n", "")
        if argv[1:] == ("start", release.RUNTIME_PREPARATION_UNIT):
            return subprocess.CompletedProcess(argv, 0, "", "")
        if argv[1:3] == ("show", "--property=LoadState"):
            return subprocess.CompletedProcess(
                argv,
                0,
                "LoadState=loaded\nActiveState=active\n",
                "",
            )
        raise AssertionError(argv)

    account = SimpleNamespace(pw_name="dharma-sadhana", pw_uid=501, pw_gid=501)
    release._start_runtime_preparation_unit(
        release_sha="a" * 40,
        account=account,
        runner=runner,
    )
    assert (release.SYSTEMCTL_PATH, "start", release.RUNTIME_PREPARATION_UNIT) in calls
    assert not any("enable" in argv for argv in calls)
    assert len(validated) == 1
    assert validated[0]["release_sha"] == "a" * 40

    def enableable(
        argv: tuple[str, ...], **_kwargs: object
    ) -> subprocess.CompletedProcess[str]:
        if argv[1:] == ("daemon-reload",):
            return subprocess.CompletedProcess(argv, 0, "", "")
        if argv[1:] == ("is-enabled", release.RUNTIME_PREPARATION_UNIT):
            return subprocess.CompletedProcess(argv, 0, "enabled\n", "")
        raise AssertionError(argv)

    with pytest.raises(release.ReleaseContractError, match="enableable"):
        release._start_runtime_preparation_unit(
            release_sha="a" * 40,
            account=account,
            runner=enableable,
        )
    assert inspect.getsource(release._finalize_staged_candidate_host).count(
        "_start_runtime_preparation_unit("
    ) == 1
    assert inspect.getsource(release.stage_candidate).count(
        "_finalize_staged_candidate_host("
    ) == 2


def test_runtime_binding_receipt_admits_only_three_exact_service_files(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root_uid = os.geteuid()
    root_gid = os.getegid()
    service_uid = max(root_uid, 1)
    service_gid = max(root_gid, 1)
    account = SimpleNamespace(
        pw_name="dharma-sadhana",
        pw_uid=service_uid,
        pw_gid=service_gid,
    )
    runtime_root = tmp_path / "inputs/runtime/sadhana-10-20260823"
    runtime_root.mkdir(parents=True, mode=0o700)
    prepared_root = tmp_path / "prepared-runtime-manifests"
    prepared_root.mkdir(mode=0o700)
    receipt_path = (
        tmp_path
        / "receipts/runtime/sadhana-10-20260823/runtime-binding-activation.v2.json"
    )
    receipt_path.parent.mkdir(parents=True, mode=0o700)
    supervisor_runtime_env = tmp_path / "supervisor-runtime.env"
    prepared: dict[str, tuple[dict[str, object], bytes]] = {}
    for name, schema in release.RUNTIME_INPUT_SCHEMAS.items():
        assert isinstance(schema, str)
        payload: dict[str, object] = {
            "schema_version": schema,
            "mission_id": release.MISSION_ID,
            "manifest_digest": "",
        }
        payload["manifest_digest"] = release._canonical_self_digest(
            payload, "manifest_digest"
        )
        raw = release._canonical_bytes(payload) + b"\n"
        prepared[name] = (payload, raw)
    parameters = {
        "campaign_id": release.MISSION_ID,
        "release_sha": "a" * 40,
        "release_input_set_digest": "1" * 64,
        "preparation_input_digest": "sha256:" + "2" * 64,
        "config_digest": "sha256:" + "3" * 64,
        "task_set_digest": "sha256:" + "4" * 64,
        "manifest_set_digest": "sha256:" + "5" * 64,
        "session_generation": 1,
        "session_status": "paused",
    }
    preparation = {
        "proof": {
            "type": "Prepared<Mission,Release,InputSet,Config,TaskSet>",
            "effect": "NoEffect",
            "parameters": parameters,
        },
        "input_set": {
            "release_admission_receipt_digest": "sha256:" + "6" * 64,
        },
        "config": {
            "canary_task_id": "canary",
            "held_out_oracle_digest": "sha256:" + "8" * 64,
        },
        "receipt_digest": "sha256:" + "7" * 64,
    }
    monkeypatch.setattr(
        release,
        "_validate_root_preparation",
        lambda **_kwargs: (preparation, prepared),
    )

    admitted = release.publish_runtime_binding_activation(
        role="writer",
        release_sha="a" * 40,
        account=account,
        receipt_path=receipt_path,
        runtime_root=runtime_root,
        prepared_root=prepared_root,
        supervisor_runtime_env_path=supervisor_runtime_env,
        now=datetime(2026, 8, 23, 1, tzinfo=timezone.utc),
        observed_node=release.WRITER_NODE,
        expected_root_uid=root_uid,
        expected_root_gid=root_gid,
    )
    assert admitted["prepared_effect"] == "NoEffect"
    assert admitted["root_verification_type"].startswith("RootVerified<Prepared<")
    assert admitted["release_sha"] == "a" * 40
    expected_runtime_env = release._supervisor_runtime_environment_bytes(
        preparation["config"]
    )
    assert supervisor_runtime_env.read_bytes() == expected_runtime_env
    assert admitted["supervisor_runtime_env_sha256"] == hashlib.sha256(
        expected_runtime_env
    ).hexdigest()
    assert set(admitted["files"]) == set(release.RUNTIME_INPUT_SCHEMAS)
    for name, entry in admitted["files"].items():
        assert entry["prepared_source_path"] == str(prepared_root / name)
        assert entry["prepared_file_sha256"] == entry["file_sha256"]

    # A crash after the three exact copies but before/after receipt publication
    # replays to the same typed binding rather than replacing any bytes.
    assert (
        release.publish_runtime_binding_activation(
            role="writer",
            release_sha="a" * 40,
            account=account,
            receipt_path=receipt_path,
            runtime_root=runtime_root,
            prepared_root=prepared_root,
            supervisor_runtime_env_path=supervisor_runtime_env,
            now=datetime(2026, 8, 23, 1, 0, 1, tzinfo=timezone.utc),
            observed_node=release.WRITER_NODE,
            expected_root_uid=root_uid,
            expected_root_gid=root_gid,
        )
        == admitted
    )

    with pytest.raises(release.ReleaseContractError, match="release differs"):
        release.publish_runtime_binding_activation(
            role="writer",
            release_sha="b" * 40,
            account=account,
            receipt_path=receipt_path,
            runtime_root=runtime_root,
            prepared_root=prepared_root,
            supervisor_runtime_env_path=supervisor_runtime_env,
            now=datetime(2026, 8, 23, 1, 0, 1, tzinfo=timezone.utc),
            observed_node=release.WRITER_NODE,
            expected_root_uid=root_uid,
            expected_root_gid=root_gid,
        )

    supervisor_runtime_env.write_text(
        "SADHANA_CANARY_TASK_ID=substituted\n"
        f"SADHANA_HELD_OUT_ORACLE_DIGEST={'sha256:' + '8' * 64}\n",
        encoding="ascii",
    )
    with pytest.raises(
        release.ReleaseContractError, match="runtime environment differs"
    ):
        release.publish_runtime_binding_activation(
            role="writer",
            release_sha="a" * 40,
            account=account,
            receipt_path=receipt_path,
            runtime_root=runtime_root,
            prepared_root=prepared_root,
            supervisor_runtime_env_path=supervisor_runtime_env,
            now=datetime(2026, 8, 23, 1, 0, 1, tzinfo=timezone.utc),
            observed_node=release.WRITER_NODE,
            expected_root_uid=root_uid,
            expected_root_gid=root_gid,
        )
    supervisor_runtime_env.write_bytes(expected_runtime_env)
    supervisor_runtime_env.chmod(0o600)

    # Once the binding receipt exists, replay is verification-only. Missing
    # installed bytes are drift, not a license to reconstruct mutable state.
    missing = runtime_root / "observed-inputs.json"
    missing_raw = prepared[missing.name][1]
    missing.unlink()
    with pytest.raises(release.ReleaseContractError, match="unavailable"):
        release.publish_runtime_binding_activation(
            role="writer",
            release_sha="a" * 40,
            account=account,
            receipt_path=receipt_path,
            runtime_root=runtime_root,
            prepared_root=prepared_root,
            supervisor_runtime_env_path=supervisor_runtime_env,
            now=datetime(2026, 8, 23, 1, 0, 1, tzinfo=timezone.utc),
            observed_node=release.WRITER_NODE,
            expected_root_uid=root_uid,
            expected_root_gid=root_gid,
        )
    assert not missing.exists()
    missing.write_bytes(missing_raw)
    missing.chmod(0o600)

    authority, _authority_raw = prepared["authority-manifest.json"]
    forged_authority = dict(authority)
    forged_authority["mission_id"] = "substituted"
    forged_authority["manifest_digest"] = release._canonical_self_digest(
        forged_authority, "manifest_digest"
    )
    forged_raw = release._canonical_bytes(forged_authority) + b"\n"
    prepared["authority-manifest.json"] = (forged_authority, forged_raw)
    with pytest.raises(release.ReleaseContractError, match="file receipt differs"):
        release.publish_runtime_binding_activation(
            role="writer",
            release_sha="a" * 40,
            account=account,
            receipt_path=receipt_path,
            runtime_root=runtime_root,
            prepared_root=prepared_root,
            supervisor_runtime_env_path=supervisor_runtime_env,
            now=datetime(2026, 8, 23, 1, tzinfo=timezone.utc),
            observed_node=release.WRITER_NODE,
            expected_root_uid=root_uid,
            expected_root_gid=root_gid,
        )


@pytest.mark.parametrize(
    ("crash_point", "published"),
    (
        ("private_bytes_pre_publish", False),
        ("private_bytes_post_publish", True),
    ),
)
def test_private_byte_publication_crash_replay_has_no_link_or_temp_wedge(
    tmp_path: Path,
    crash_point: str,
    published: bool,
) -> None:
    target = tmp_path / "runtime-binding.json"
    raw = b'{"prepared":"no-effect"}\n'

    def crash(point: str) -> None:
        if point == crash_point:
            raise RuntimeError("injected publication crash")

    with pytest.raises(RuntimeError, match="injected publication crash"):
        release._atomic_private_bytes(
            target,
            raw,
            uid=os.geteuid(),
            gid=os.getegid(),
            checkpoint=crash,
        )
    assert target.exists() is published
    assert sorted(path.name for path in tmp_path.iterdir()) == (
        [target.name] if published else []
    )
    if published:
        identity = target.lstat()
        assert identity.st_nlink == 1
        assert stat.S_IMODE(identity.st_mode) == 0o600
        release._publish_or_replay_exact_bytes(
            target,
            raw,
            expected_uid=os.geteuid(),
            expected_gid=os.getegid(),
        )


def test_runtime_binding_seals_campaign_authority_schema_v4() -> None:
    assert (
        release.RUNTIME_INPUT_SCHEMAS["authority-manifest.json"]
        == "dharma.sadhana.campaign_authority_manifest.v4"
    )


@pytest.mark.asyncio
async def test_root_semantics_reject_service_substituted_goal_contract_digest(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    try:
        from scripts.runtime import sadhana_prepare_runtime as preparation
        from tests.test_sadhana_prepare_runtime import _inputs
    except ImportError:
        pytest.skip("runtime preparation implementation lands in integration parent")

    inputs = _inputs(tmp_path, monkeypatch, state_name="root-semantic-validation")
    receipt = await preparation.prepare_runtime(inputs)
    prepared: dict[str, tuple[dict[str, object], bytes]] = {}
    for path in inputs.output_root.iterdir():
        raw = path.read_bytes()
        prepared[path.name] = (json.loads(raw), raw)
    release._validate_prepared_runtime_semantics(
        receipt,
        prepared,
        contracts_raw=inputs.contracts.read_bytes(),
    )

    substituted = json.loads(json.dumps(receipt))
    substituted["input_set"]["goal_contract_digest"] = "sha256:" + "0" * 64
    with pytest.raises(release.ReleaseContractError, match="lineage differs"):
        release._validate_prepared_runtime_semantics(
            substituted,
            prepared,
            contracts_raw=inputs.contracts.read_bytes(),
        )


def test_gitless_staged_release_admission_persists_ledger_and_rejects_substitution(
    tmp_path: Path,
) -> None:
    release_sha: str
    release_path = tmp_path / "candidate"
    release_path.mkdir(mode=0o700)
    _git(release_path, "init")
    _git(release_path, "config", "user.email", "test@example.invalid")
    _git(release_path, "config", "user.name", "Verifier")
    source = release_path / "campaign.py"
    source.write_text("print('prepared, no effect')\n", encoding="ascii")
    _git(release_path, "add", "campaign.py")
    _git(release_path, "commit", "-m", "candidate")
    release_sha = _git(release_path, "rev-parse", "HEAD")
    _git(release_path, "remote", "add", "origin", release.CANONICAL_ORIGIN)
    tracked = release.render_tracked_source_manifest(release_path, release_sha)
    shutil.rmtree(release_path / ".git")
    for output in release.TRACKED_SOURCE_BUILD_OUTPUT_ROOTS:
        (release_path / output).mkdir(parents=True, exist_ok=True)
    tracked_modes = {
        entry["path"]: entry["git_mode"] for entry in tracked["entries"]
    }
    for directory, names, files in os.walk(release_path, topdown=False):
        directory_path = Path(directory)
        for name in files:
            candidate = directory_path / name
            relative = candidate.relative_to(release_path).as_posix()
            candidate.chmod(0o555 if tracked_modes[relative] == "100755" else 0o444)
        for name in names:
            (directory_path / name).chmod(0o555)
        directory_path.chmod(0o555)

    root_uid = os.geteuid()
    root_gid = os.getegid()
    service_uid = max(root_uid, 1)
    service_gid = max(root_gid, 1)
    account = SimpleNamespace(
        pw_name="dharma-sadhana",
        pw_uid=service_uid,
        pw_gid=service_gid,
    )
    receipts_parent = tmp_path / "receipts"
    receipts_parent.mkdir(mode=0o700)
    receipt_root = receipts_parent / "releases"
    projection_parent = tmp_path / "state"
    projection_parent.mkdir(mode=0o700)
    os.chown(projection_parent, service_uid, service_gid)
    projection = projection_parent / release.STAGED_RELEASE_ADMISSION_FILE
    build_receipt = {
        "schema_version": "dharma.sadhana.isolated_build.v1",
        "release_sha": release_sha,
        "build_uid": service_uid,
        "build_gid": service_gid,
        "no_new_privileges": True,
        "solo_cgroup_process": True,
        "build_process_dumpable": False,
        "runtime_max_seconds": 1800,
        "tasks_max": 256,
        "memory_max_bytes": 4_294_967_296,
        "commands": [
            "uv-version",
            "git-clone",
            "git-checkout",
            "git-origin",
            "python-venv",
            "uv-sync",
            "npm-ci",
            "next-build",
            "venv-python-version",
            "git-verify-checkout",
            "git-verify-tracked",
            "git-metadata-removed",
        ],
        "manifest_sha256": "a" * 64,
        "build_driver_sha256": "b" * 64,
        "candidate_code_executed_as_root": False,
        "post_exit_build_uid_process_count": 0,
    }
    admitted = release.publish_staged_release_admission(
        release_sha=release_sha,
        release_path=release_path,
        tracked_source=tracked,
        build_receipt=build_receipt,
        release_input_set_digest="c" * 64,
        account=account,
        receipt_root=receipt_root,
        projection_path=projection,
        expected_root_uid=root_uid,
        expected_root_gid=root_gid,
    )
    release_receipts, ledger_path, build_path, admission_path = (
        release._staged_release_receipt_paths(
            release_sha,
            receipt_root=receipt_root,
        )
    )
    assert release_receipts.is_dir()
    assert ledger_path.exists() and build_path.exists() and admission_path.exists()
    assert projection.read_bytes() == admission_path.read_bytes()
    assert admitted["git_metadata_present"] is False
    assert admitted["frozen_tree"] is True
    assert admitted["candidate_code_executed_as_root"] is False
    assert admitted["receipt_digest"] == release._canonical_newline_self_digest(
        admitted,
        "receipt_digest",
    )

    substituted_build = dict(build_receipt)
    substituted_build["build_driver_sha256"] = "d" * 64
    build_path.write_bytes(release._canonical_bytes(substituted_build) + b"\n")
    build_path.chmod(0o600)
    with pytest.raises(release.ReleaseContractError, match="evidence ledger"):
        release.verify_staged_release_admission(
            release_sha=release_sha,
            release_path=release_path,
            expected_release_input_set_digest="c" * 64,
            account=account,
            receipt_root=receipt_root,
            projection_path=projection,
            expected_root_uid=root_uid,
            expected_root_gid=root_gid,
        )


def test_input_set_install_rehashes_and_rejects_mismatch_before_target_mutation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source_root = tmp_path / "source"
    source_root.mkdir(mode=0o700)
    payload, _contents = _input_fixture(source_root, monkeypatch)
    manifest_path = tmp_path / "input-set.manifest.json"
    manifest_path.write_bytes(release._canonical_bytes(payload) + b"\n")
    manifest_path.chmod(0o600)
    archive = tmp_path / release.INPUT_SET_ARCHIVE_FILE
    release.build_input_set_archive(
        payload,
        source_root=source_root,
        destination=archive,
    )

    etc_root = tmp_path / "etc-dharma-sadhana"
    etc_root.mkdir(mode=0o750)
    target_root = etc_root / "inputs"
    installed_manifest = etc_root / "input-set.manifest.json"
    installed_receipt = etc_root / "input-set.receipt.json"
    monkeypatch.setattr(release, "INPUT_SET_TARGET_ROOT", target_root)
    monkeypatch.setattr(release, "INPUT_SET_MANIFEST_TARGET", installed_manifest)
    monkeypatch.setattr(release, "INPUT_SET_RECEIPT_TARGET", installed_receipt)
    payload["target_root"] = str(target_root)
    payload["input_set_digest"] = release._input_set_digest(payload)
    manifest_path.write_bytes(release._canonical_bytes(payload) + b"\n")
    manifest_path.chmod(0o600)
    account = SimpleNamespace(
        pw_name="dharma-sadhana",
        pw_uid=os.geteuid(),
        pw_gid=os.getegid(),
    )

    forged = copy.deepcopy(payload)
    forged["entries"][1]["sha256"] = "f" * 64
    forged["input_set_digest"] = release._input_set_digest(forged)
    manifest_path.write_bytes(release._canonical_bytes(forged) + b"\n")
    manifest_path.chmod(0o600)
    with pytest.raises(release.ReleaseContractError, match="member hash"):
        release.install_input_set(
            manifest_path=manifest_path,
            archive_path=archive,
            account=account,
            observed_node=release.WRITER_NODE,
            target_root=target_root,
            installed_manifest=installed_manifest,
            installed_receipt=installed_receipt,
            expected_root_uid=os.geteuid(),
            expected_root_gid=os.getegid(),
        )
    assert not target_root.exists()
    assert not installed_manifest.exists()
    assert not installed_receipt.exists()

    manifest_path.write_bytes(release._canonical_bytes(payload) + b"\n")
    manifest_path.chmod(0o600)
    receipt = release.install_input_set(
        manifest_path=manifest_path,
        archive_path=archive,
        account=account,
        observed_node=release.WRITER_NODE,
        now=datetime(2026, 8, 23, tzinfo=timezone.utc),
        target_root=target_root,
        installed_manifest=installed_manifest,
        installed_receipt=installed_receipt,
        expected_root_uid=os.geteuid(),
        expected_root_gid=os.getegid(),
    )
    assert receipt["verifier_secret_included"] is False
    assert receipt["runtime_database_is_canonical"] is True
    assert len(receipt["entries"]) == 2
    assert installed_manifest.is_file()
    assert installed_receipt.is_file()
    (target_root / "receipts/extra.json").write_text("{}\n", encoding="utf-8")
    (target_root / "receipts/extra.json").chmod(0o600)
    with pytest.raises(release.ReleaseContractError, match="extra file"):
        release.install_input_set(
            manifest_path=manifest_path,
            archive_path=archive,
            account=account,
            observed_node=release.WRITER_NODE,
            target_root=target_root,
            installed_manifest=installed_manifest,
            installed_receipt=installed_receipt,
            expected_root_uid=os.geteuid(),
            expected_root_gid=os.getegid(),
        )


@pytest.mark.parametrize("value", [1, -1, False, 0.0, "0"])
def test_cash_budget_must_be_integer_zero(value: object) -> None:
    _reject("cash_budget_usd", value)


def test_automatic_failover_and_standby_writer_are_rejected() -> None:
    _reject("automatic_failover", True)
    _reject("standby_writer_enabled", True)


def test_wrong_origin_and_wrong_sha_are_rejected() -> None:
    _reject("canonical_origin", "https://github.com/elsewhere/dharma_swarm.git")
    _reject("release_sha", "a" * 39)
    _reject("integration_base_sha", "a" * 39)
    _reject("integration_base_sha", "1" * 40)
    _reject("deployment_known_hosts_sha256", "b" * 64)


@pytest.mark.parametrize(
    "stop",
    ["2026-09-01T17:15:11Z", "2026-09-01T17:15:13Z"],
)
def test_stop_time_early_or_late_is_rejected(stop: str) -> None:
    _reject("campaign_stop_utc", stop)


@pytest.mark.parametrize(
    "calendar",
    ["2026-09-01 17:15:11 UTC", "2026-09-01 17:15:13 UTC"],
)
def test_stop_timer_early_or_late_is_rejected(calendar: str) -> None:
    with pytest.raises(release.ReleaseContractError, match="exact end"):
        release.validate_unit_text(
            "dharma-sadhana-campaign-stop.timer",
            f"OnCalendar={calendar}\nAccuracySec=1s\nPersistent=true\n",
            rendered=True,
        )


def test_stop_service_cannot_depend_on_the_writer_marker() -> None:
    with pytest.raises(release.ReleaseContractError, match="independent cessation"):
        release.validate_unit_text(
            "dharma-sadhana-campaign-stop.service.in",
            "\n".join(
                (
                    "ConditionPathExists=/etc/dharma-sadhana/writer-enabled",
                    "ExecStartPre=sadhana_release.py guard-stop --role writer",
                    "ExecStart=+/usr/bin/systemctl stop dharma-sadhana.target",
                    "ExecStart=sadhana_release.py persist-stop --role writer",
                    "WorkingDirectory=@RELEASE_SHA@",
                )
            ),
            rendered=False,
        )


def test_supervisor_cannot_drop_observed_context_with_fast_boot() -> None:
    with pytest.raises(release.ReleaseContractError, match="observed context"):
        release.validate_unit_text(
            "dharma-sadhana-supervisor.service.in",
            "WorkingDirectory=@RELEASE_SHA@\nExecStart=mission_control_campaign.py run --fast-boot\n",
            rendered=False,
        )


def test_activation_rejects_before_start_and_at_or_after_stop() -> None:
    payload = _payload()
    with pytest.raises(release.ReleaseContractError, match="before"):
        release.validate_manifest(
            payload,
            now=datetime(2026, 8, 22, 17, 15, 11, tzinfo=timezone.utc),
            for_activation=True,
        )
    with pytest.raises(release.ReleaseContractError, match="at or after"):
        release.validate_manifest(
            payload,
            now=datetime(2026, 9, 1, 17, 15, 12, tzinfo=timezone.utc),
            for_activation=True,
        )


def test_deploy_cannot_activate_before_governed_authority_binding(
    capsys: pytest.CaptureFixture[str],
) -> None:
    parser = release._parser()
    with pytest.raises(SystemExit):
        parser.parse_args(
            [
                "deploy",
                "--manifest",
                "/tmp/manifest",
                "--bundle",
                "/tmp/bundle",
                "--receipt",
                "/tmp/receipt",
                "--uv-wheel",
                "/tmp/uv",
                "--tracked-source-manifest",
                "/tmp/tracked",
                "--role",
                "writer",
                "--activate",
            ]
        )
    assert "unrecognized arguments: --activate" in capsys.readouterr().err
    assert parser.parse_args(
        ["publish-runtime-binding", "--role", "writer", "--release-sha", "a" * 40]
    ).command == "publish-runtime-binding"
    assert parser.parse_args(
        ["activate-predispatch", "--role", "writer", "--release-sha", "a" * 40]
    ).command == "activate-predispatch"
    assert parser.parse_args(
        ["refresh-predispatch", "--role", "writer", "--release-sha", "a" * 40]
    ).command == "refresh-predispatch"
    assert parser.parse_args(
        [
            "activate-campaign-session",
            "--role",
            "writer",
            "--release-sha",
            "a" * 40,
            "--dispatch-activation-receipt",
            "/run/credentials/unit/dispatch",
            "--dashboard-identity-receipt",
            "/run/credentials/unit/dashboard",
            "--runtime-binding-receipt",
            "/run/credentials/unit/binding",
            "--operator-login-file",
            "/run/credentials/unit/login",
            "--control-hmac-key-file",
            "/run/credentials/unit/hmac",
            "--control-gate-path",
            "/var/lib/dharma-sadhana/state/writer.lock.control",
        ]
    ).command == "activate-campaign-session"
    assert parser.parse_args(
        ["activate-standby", "--role", "standby", "--release-sha", "a" * 40]
    ).command == "activate-standby"


@pytest.mark.parametrize(
    "observed",
    [
        datetime(2026, 8, 22, 17, 15, 11, tzinfo=timezone.utc),
        datetime(2026, 9, 1, 17, 15, 12, tzinfo=timezone.utc),
        datetime(2026, 9, 1, 17, 15, 13, tzinfo=timezone.utc),
    ],
)
def test_process_start_guard_rejects_early_or_late(observed: datetime) -> None:
    with pytest.raises(release.ReleaseContractError, match="timebox"):
        release.guard_campaign_clock(
            role="writer",
            now=observed,
            observed_node=release.WRITER_NODE,
        )


def test_stop_guard_rejects_early_and_admits_exact_or_late() -> None:
    with pytest.raises(release.ReleaseContractError, match="before"):
        release.guard_campaign_stop(
            role="writer",
            now=datetime(2026, 9, 1, 17, 15, 11, tzinfo=timezone.utc),
            observed_node=release.WRITER_NODE,
        )
    for observed in (
        datetime(2026, 9, 1, 17, 15, 12, tzinfo=timezone.utc),
        datetime(2026, 9, 2, tzinfo=timezone.utc),
    ):
        assert (
            release.guard_campaign_stop(
                role="writer",
                now=observed,
                observed_node=release.WRITER_NODE,
            )
            == observed
        )


def test_stop_persistence_receipts_failure_without_command_output(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state = tmp_path / "state"
    workspace = tmp_path / "workspace"
    projection_root = tmp_path / "projection-source"
    projection = projection_root / "mission-projection.json"
    root = tmp_path / "release"
    (root / ".venv/bin").mkdir(parents=True)
    (root / "scripts/runtime").mkdir(parents=True)
    (root / ".venv/bin/python").write_text("fixture", encoding="utf-8")
    (root / "scripts/runtime/mission_control_campaign.py").write_text(
        "fixture", encoding="utf-8"
    )
    state.mkdir()
    workspace.mkdir()
    projection_root.mkdir(mode=0o700)
    projection.write_bytes(b"{}\n")
    projection.chmod(0o600)
    monkeypatch.setattr(release, "STATE_ROOT", str(state))
    monkeypatch.setattr(release, "WORKSPACE_ROOT", str(workspace))
    monkeypatch.setattr(release, "PROJECTION_SOURCE_ROOT", projection_root)
    monkeypatch.setattr(release, "WRITER_PROJECTION_PATH", projection)
    monkeypatch.setattr(
        release,
        "_require_static_service_identity",
        lambda: SimpleNamespace(pw_uid=os.geteuid(), pw_gid=os.getegid()),
    )
    receipt = state / "stop-enforcement-receipt.json"
    calls: list[tuple[str, ...]] = []

    def runner(argv, **kwargs):  # noqa: ANN001, ANN202
        calls.append(tuple(argv))
        return subprocess.CompletedProcess(
            argv,
            7,
            "secret-output-must-not-be-recorded",
            "secret-error-must-not-be-recorded",
        )

    payload = release.persist_campaign_stop(
        writer_lock_path=state / "writer.lock",
        projection_path=projection,
        runner=runner,
        receipt_path=receipt,
        release_root=root,
        now=datetime(2026, 9, 1, 17, 15, 12, tzinfo=timezone.utc),
        observed_node=release.WRITER_NODE,
    )
    assert calls and calls[0][-2:] == (
        "--projection-path",
        str(projection),
    )
    assert payload["target_stop_completed"] is True
    assert payload["durable_marker_persisted"] is False
    assert payload["persistence_exit_code"] == 7
    raw = receipt.read_text(encoding="ascii")
    assert "secret-output" not in raw
    assert stat.S_IMODE(receipt.stat().st_mode) == 0o600


def test_stop_persistence_receipts_subprocess_launch_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state = tmp_path / "state"
    workspace = tmp_path / "workspace"
    projection_root = tmp_path / "projection-source"
    projection = projection_root / "mission-projection.json"
    root = tmp_path / "release"
    (root / ".venv/bin").mkdir(parents=True)
    (root / "scripts/runtime").mkdir(parents=True)
    (root / ".venv/bin/python").write_text("fixture", encoding="utf-8")
    (root / "scripts/runtime/mission_control_campaign.py").write_text(
        "fixture", encoding="utf-8"
    )
    state.mkdir()
    workspace.mkdir()
    projection_root.mkdir(mode=0o700)
    projection.write_bytes(b"{}\n")
    projection.chmod(0o600)
    monkeypatch.setattr(release, "STATE_ROOT", str(state))
    monkeypatch.setattr(release, "WORKSPACE_ROOT", str(workspace))
    monkeypatch.setattr(release, "PROJECTION_SOURCE_ROOT", projection_root)
    monkeypatch.setattr(release, "WRITER_PROJECTION_PATH", projection)
    monkeypatch.setattr(
        release,
        "_require_static_service_identity",
        lambda: SimpleNamespace(pw_uid=os.geteuid(), pw_gid=os.getegid()),
    )
    receipt = state / "stop-enforcement-receipt.json"

    def unavailable(*args, **kwargs):  # noqa: ANN002, ANN003, ANN202
        raise release.ReleaseContractError("secret launch detail")

    payload = release.persist_campaign_stop(
        writer_lock_path=state / "writer.lock",
        projection_path=projection,
        runner=unavailable,
        receipt_path=receipt,
        release_root=root,
        now=datetime(2026, 9, 1, 17, 15, 12, tzinfo=timezone.utc),
        observed_node=release.WRITER_NODE,
    )
    assert payload["target_stop_completed"] is True
    assert payload["durable_marker_persisted"] is False
    assert payload["persistence_exit_code"] == -1
    assert "secret launch detail" not in receipt.read_text(encoding="ascii")


def test_stop_persistence_rejects_state_root_projection_before_io(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state = tmp_path / "state"
    state.mkdir()
    monkeypatch.setattr(release, "STATE_ROOT", str(state))
    with pytest.raises(release.ReleaseContractError, match="projection path differs"):
        release.persist_campaign_stop(
            writer_lock_path=state / "writer.lock",
            projection_path=state / "mission-projection.json",
            receipt_path=state / "stop-enforcement-receipt.json",
            now=datetime(2026, 9, 1, 17, 15, 12, tzinfo=timezone.utc),
            observed_node=release.WRITER_NODE,
        )


def test_private_manifest_reader_rejects_symlink_and_nonprivate_mode(
    tmp_path: Path,
) -> None:
    manifest = tmp_path / "release-manifest.json"
    manifest.write_text(json.dumps(_payload()), encoding="utf-8")
    manifest.chmod(0o600)
    assert release.load_manifest(manifest)["mission_id"] == release.MISSION_ID
    link = tmp_path / "manifest-link.json"
    link.symlink_to(manifest)
    with pytest.raises(release.ReleaseContractError, match="custody"):
        release.load_manifest(link)
    manifest.chmod(0o644)
    with pytest.raises(release.ReleaseContractError, match="custody"):
        release.load_manifest(manifest)


def test_custodied_reader_ignores_nonwritable_inherited_group_metadata(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    private_parent = tmp_path / "owner-private"
    private_parent.mkdir(mode=0o700)
    target = private_parent / "receipt.json"
    target.write_bytes(b'{}\n')
    target.chmod(0o600)
    os.chown(target, os.geteuid(), os.getegid())
    actual_lstat = Path.lstat
    inherited_gid = os.getegid() + 1

    def inherited_group_lstat(path: Path):  # noqa: ANN202
        identity = actual_lstat(path)
        if path == private_parent:
            return SimpleNamespace(
                st_mode=identity.st_mode,
                st_uid=identity.st_uid,
                st_gid=inherited_gid,
            )
        return identity

    monkeypatch.setattr(Path, "lstat", inherited_group_lstat)
    raw, _identity = release._read_exact_custodied_bytes(
        target,
        expected_uid=os.geteuid(),
        expected_gid=os.getegid(),
    )
    assert raw == b'{}\n'

    private_parent.chmod(0o710)
    raw, _identity = release._read_exact_custodied_bytes(
        target,
        expected_uid=os.geteuid(),
        expected_gid=os.getegid(),
    )
    assert raw == b'{}\n'

    private_parent.chmod(0o730)
    with pytest.raises(release.ReleaseContractError, match="parent lacks private"):
        release._read_exact_custodied_bytes(
            target,
            expected_uid=os.geteuid(),
            expected_gid=os.getegid(),
        )


def test_public_unit_mutations_are_rejected() -> None:
    with pytest.raises(release.ReleaseContractError, match="public"):
        release.validate_unit_text(
            "api.service", "ExecStart=uvicorn --host 0.0.0.0", rendered=True
        )
    with pytest.raises(release.ReleaseContractError, match="public"):
        release.validate_unit_text(
            "dharma-sadhana-private-serve.service",
            "ExecStart=/usr/bin/tailscale funnel 3000",
            rendered=True,
        )


def test_all_units_render_to_exact_release_and_private_loopback(
    tmp_path: Path,
) -> None:
    repo = Path(__file__).resolve().parents[1]
    rendered = release.render_units(repo, "a" * 40, tmp_path)
    assert len(rendered) == 36
    combined = "\n".join(path.read_text(encoding="utf-8") for path in rendered)
    assert "@RELEASE_SHA@" not in combined
    assert "0.0.0.0" not in combined
    assert (
        f"sadhana_release.py tailscale-start --role writer --release-sha {'a' * 40}"
        in combined
    )
    assert (
        f"sadhana_release.py tailscale-stop --role writer --release-sha {'a' * 40}"
        in combined
    )
    assert (
        "SADHANA_CONTROL_INTERNAL_URL="
        "http://127.0.0.1:18421/v1/operator-control/requests" in combined
    )
    assert "--host 127.0.0.1 --port ${SADHANA_API_PORT}" in combined
    assert "--no-proxy-headers" in combined
    dashboard_server = (
        repo / "deploy/sadhana/sadhana-dashboard-server.mjs"
    ).read_text(encoding="utf-8")
    assert "/run/dharma-sadhana/dashboard/constellation.sock" in dashboard_server
    assert "--port 3000" not in combined
    assert "OnCalendar=2026-09-01 17:15:12 UTC" in combined
    assert combined.count("sadhana_release.py guard-start --role writer") == 14
    assert combined.count("PartOf=dharma-sadhana.target") == 22
    assert "sadhana_oracle_sandbox.py probe --release-sha " in combined
    assert "sadhana_oracle_sandbox.py reconcile --release-sha " in combined
    assert "PrivateNetwork=true" in combined
    assert "TemporaryFileSystem=/tmp:ro /var/tmp:ro /dev/shm:ro" in combined
    assert "PathChanged=/run/dharma-sadhana/oracle/requests" in combined
    assert "DirectoryNotEmpty=/run/dharma-sadhana/oracle/requests" not in combined
    assert "/var/lib/dharma-sadhana/oracle-inputs" in combined
    assert "/run/dharma-sadhana/oracle/terminals" in combined
    health_barrier = (tmp_path / release.OBSERVER_HEALTH_UNIT).read_text(
        encoding="utf-8"
    )
    supervisor = (tmp_path / release.SUPERVISOR_UNIT).read_text(encoding="utf-8")
    target = (tmp_path / "dharma-sadhana.target").read_text(encoding="utf-8")
    assert "Requires=dharma-sadhana-api.service" in health_barrier
    assert "After=dharma-sadhana-api.service" in health_barrier
    assert (
        f"Before={release.DISPATCH_ENABLE_UNIT} {release.SUPERVISOR_UNIT}"
        in health_barrier
    )
    assert "probe-observer-health --role writer --release-sha " in health_barrier
    assert f"Requires={release.OBSERVER_HEALTH_UNIT}" not in health_barrier
    assert release.OBSERVER_HEALTH_UNIT in supervisor
    assert (
        "LoadCredential=control_hmac_key:/etc/dharma-sadhana/credentials/"
        "control_hmac_key" in supervisor
    )
    assert "LoadCredential=dispatch_activation_receipt:" in supervisor
    assert "LoadCredential=observer_health_receipt:" in supervisor
    assert "LoadCredential=runtime_binding_activation:" in supervisor
    assert "--operator-control-hmac-credential" not in supervisor
    assert "--operator-control-hmac-sha256" not in supervisor
    assert release.OBSERVER_HEALTH_UNIT in target
    assert release.SUPERVISOR_UNIT not in target
    dispatch_target = (tmp_path / release.DISPATCH_TARGET).read_text(encoding="utf-8")
    dispatch_gate = (tmp_path / release.DISPATCH_ENABLE_UNIT).read_text(
        encoding="utf-8"
    )
    assert release.SUPERVISOR_UNIT in dispatch_target
    assert release.DISPATCH_ENABLE_UNIT in dispatch_target
    assert "WantedBy=" not in dispatch_target
    assert (
        "/run/credentials/dharma-sadhana-dashboard.service/operator_bearer"
        in dispatch_gate
    )
    assert (
        "/run/credentials/dharma-sadhana-control.service/operator_bearer"
        in dispatch_gate
    )
    assert "/run/dharma-sadhana/control/normal" in dispatch_gate
    assert "/run/dharma-sadhana/control/emergency" in dispatch_gate
    assert (
        "InaccessiblePaths=/etc/dharma-sadhana/credentials/control_hmac_key "
        in dispatch_gate
    )
    assert (
        "/run/credentials/dharma-sadhana-control.service/control_hmac_key"
        in dispatch_gate
    )
    assert "ReadWritePaths=/run/dharma-sadhana/control" not in dispatch_gate
    assert "LoadCredential=" not in dispatch_gate
    assert "CapabilityBoundingSet=CAP_SYS_PTRACE" in dispatch_gate
    assert "CAP_DAC_READ_SEARCH" not in dispatch_gate
    assert "CAP_DAC_OVERRIDE" not in dispatch_gate
    assert "PrivateNetwork=true" not in health_barrier
    assert "EnvironmentFile=" not in health_barrier
    assert "LoadCredential=" not in health_barrier


def test_production_unit_write_namespaces_cover_only_exact_runtime_paths() -> None:
    unit_root = Path(__file__).resolve().parents[1] / "deploy/sadhana/systemd"

    def unit(name: str) -> str:
        text = (unit_root / name).read_text(encoding="utf-8")
        release.validate_unit_text(name, text, rendered=False)
        return text

    runtime_prepare = unit("dharma-sadhana-runtime-prepare.service.in")
    api = unit("dharma-sadhana-api.service.in")
    projection_sync = unit("dharma-sadhana-projection-sync.service.in")
    oracle_directories = unit("dharma-sadhana-oracle-directories.service.in")
    supervisor = unit("dharma-sadhana-supervisor.service.in")
    campaign_stop = unit("dharma-sadhana-campaign-stop.service.in")
    dispatch_enable = unit("dharma-sadhana-dispatch-enable.service.in")
    control_directories = unit("dharma-sadhana-control-directories.service.in")
    dashboard = unit("dharma-sadhana-dashboard.service.in")

    assert "--projection-path ${SADHANA_PREP_PROJECTION_PATH}" in runtime_prepare
    assert "ConditionPathExists=!/etc/dharma-sadhana/writer-enabled" not in (
        runtime_prepare
    )
    assert (
        "ReadWritePaths=/var/lib/dharma-sadhana/state "
        "/var/lib/dharma-sadhana/projection-source"
    ) in runtime_prepare
    assert (
        "InaccessiblePaths=-/etc/dharma-sadhana/credentials "
        "-/etc/dharma-sadhana/verifier.env -/run/credentials "
        "-/run/dharma-sadhana/control -/run/dharma-sadhana/oracle"
    ) in runtime_prepare
    assert "runtime-binding-activation.v2.json" not in runtime_prepare
    required_api_roots = (
        "dharma-sadhana-projection-sync.service "
        "dharma-sadhana-control-directories.service "
        "dharma-sadhana-oracle-directories.service"
    )
    assert f"Requires={required_api_roots}" in api
    assert f"After={required_api_roots}" in api
    for text in (supervisor, campaign_stop):
        assert "/var/lib/dharma-sadhana/projection-source" in text
    assert "guard-standby-capacity" not in supervisor
    assert supervisor.splitlines().count("Environment=DHARMA_READ_ONLY_BOOT=1") == 1
    assert (
        "LoadCredential=dashboard_identity_receipt:/etc/dharma-sadhana/"
            "receipts/preactivation/dashboard-identity.v5.json"
    ) in supervisor
    assert (
        "LoadCredential=tailscale_operator_login:/etc/dharma-sadhana/"
        "credentials/tailscale_operator_login"
    ) in supervisor
    assert "activate-campaign-session" not in supervisor
    activation_line = next(
        line for line in supervisor.splitlines() if line.startswith("ExecStart=")
    )
    assert "mission_control_campaign.py run" in activation_line
    for credential in (
        "%d/dispatch_activation_receipt",
        "%d/dashboard_identity_receipt",
        "%d/runtime_binding_activation",
        "%d/tailscale_operator_login",
        "%d/control_hmac_key",
        "--activation-evidence-path /run/dharma-sadhana/control/activation/"
        "campaign-activation.v1.json",
    ):
        assert credential in activation_line
    assert (
        "EnvironmentFile=/etc/dharma-sadhana/receipts/preactivation/"
        "supervisor-activation.env"
    ) in supervisor
    assert "/etc/dharma-sadhana/supervisor-activation.env" not in supervisor
    assert (
        "ReadWritePaths=/etc/dharma-sadhana/receipts/preactivation"
        in dispatch_enable
    )
    assert "ReadWritePaths=/etc/dharma-sadhana\n" not in dispatch_enable
    assert "/var/lib/dharma-sadhana/state" in dispatch_enable.split(
        "ReadOnlyPaths=", 1
    )[1].splitlines()[0]
    assert "/var/lib/dharma-sadhana/projection-source" in dispatch_enable.split(
        "ReadOnlyPaths=", 1
    )[1].splitlines()[0]
    assert "/var/lib/dharma-sadhana/state" not in dispatch_enable.split(
        "InaccessiblePaths=", 1
    )[1].splitlines()[0]
    assert "RuntimeDirectory=dharma-sadhana\n" in control_directories
    assert "RuntimeDirectoryMode=0711" in control_directories
    exact_capabilities = "CapabilityBoundingSet=CAP_CHOWN CAP_DAC_OVERRIDE CAP_FOWNER"
    assert exact_capabilities in control_directories
    assert exact_capabilities in projection_sync
    assert (
        "Requires=dharma-sadhana-control-directories.service"
        in oracle_directories
    )
    assert "After=dharma-sadhana-control-directories.service" in oracle_directories
    assert (
        "ReadWritePaths=/run/dharma-sadhana "
        "/var/lib/dharma-sadhana/oracle-inputs "
        "/var/lib/dharma-sadhana/oracle-claims "
        "/var/lib/dharma-sadhana/oracle-runs "
        "/var/lib/dharma-sadhana/oracle-quarantine "
        "/etc/dharma-sadhana/receipts/oracle"
    ) in oracle_directories
    assert "ReadWritePaths=-/var/lib/dharma-sadhana/oracle" not in oracle_directories
    assert "RuntimeDirectory=dharma-sadhana/dashboard" in dashboard
    assert "RuntimeDirectoryMode=0700" in dashboard


@pytest.mark.parametrize(
    ("name", "old", "hostile", "error"),
    (
        (
            "dharma-sadhana-runtime-prepare.service.in",
            "ConditionPathExists=!/etc/dharma-sadhana/receipts/preactivation/"
            "dispatch-enabled.v1.json",
            "ConditionPathExists=!/etc/dharma-sadhana/writer-enabled\n"
            "ConditionPathExists=!/etc/dharma-sadhana/receipts/preactivation/"
            "dispatch-enabled.v1.json",
            "runtime preparation unit authority differs",
        ),
        (
            "dharma-sadhana-runtime-prepare.service.in",
            "ReadWritePaths=/var/lib/dharma-sadhana/state "
            "/var/lib/dharma-sadhana/projection-source",
            "ReadWritePaths=/var/lib/dharma-sadhana",
            "runtime preparation unit authority differs",
        ),
        (
            "dharma-sadhana-runtime-prepare.service.in",
            "InaccessiblePaths=-/etc/dharma-sadhana/credentials "
            "-/etc/dharma-sadhana/verifier.env -/run/credentials "
            "-/run/dharma-sadhana/control -/run/dharma-sadhana/oracle",
            "InaccessiblePaths=/etc/dharma-sadhana/credentials "
            "/etc/dharma-sadhana/verifier.env /run/credentials "
            "/run/dharma-sadhana/control /run/dharma-sadhana/oracle",
            "runtime preparation unit authority differs",
        ),
        (
            "dharma-sadhana-api.service.in",
            "Requires=dharma-sadhana-projection-sync.service "
            "dharma-sadhana-control-directories.service "
            "dharma-sadhana-oracle-directories.service",
            "Requires=dharma-sadhana-projection-sync.timer",
            "API observer isolation differs",
        ),
        (
            "dharma-sadhana-supervisor.service.in",
            "/var/lib/dharma-sadhana/projection-source ",
            "/var/lib/dharma-sadhana ",
            "supervisor dispatch authority differs",
        ),
        (
            "dharma-sadhana-supervisor.service.in",
            "EnvironmentFile=/etc/dharma-sadhana/receipts/preactivation/"
            "supervisor-activation.env",
            "EnvironmentFile=/etc/dharma-sadhana/supervisor-activation.env",
            "supervisor oracle membrane differs",
        ),
        (
            "dharma-sadhana-supervisor.service.in",
            "Environment=DHARMA_READ_ONLY_BOOT=1",
            "Environment=DHARMA_READ_ONLY_BOOT=0",
            "supervisor oracle membrane differs",
        ),
        (
            "dharma-sadhana-supervisor.service.in",
            "EnvironmentFile=/etc/dharma-sadhana/verifier.env",
            "EnvironmentFile=/etc/dharma-sadhana/verifier.env\n"
            "EnvironmentFile=/tmp/hostile.env",
            "supervisor dispatch authority differs",
        ),
        (
            "dharma-sadhana-supervisor.service.in",
            "LoadCredential=control_hmac_key:/etc/dharma-sadhana/credentials/"
            "control_hmac_key",
            "LoadCredential=control_hmac_key:/etc/dharma-sadhana/credentials/"
            "control_hmac_key\nLoadCredential=foreign:/tmp/foreign",
            "supervisor dispatch authority differs",
        ),
        (
            "dharma-sadhana-supervisor.service.in",
            "Environment=DHARMA_READ_ONLY_BOOT=1",
            "Environment=DHARMA_READ_ONLY_BOOT=1\nPassEnvironment=HOSTILE_IMPORT",
            "supervisor dispatch authority differs",
        ),
        (
            "dharma-sadhana-campaign-stop.service.in",
            " /var/lib/dharma-sadhana/projection-source",
            " /var/lib/dharma-sadhana",
            "campaign stop service lacks independent cessation",
        ),
        (
            "dharma-sadhana-dispatch-enable.service.in",
            "ReadWritePaths=/etc/dharma-sadhana/receipts/preactivation",
            "ReadWritePaths=/etc/dharma-sadhana",
            "dispatch enable unit binding differs",
        ),
        (
            "dharma-sadhana-dispatch-enable.service.in",
            "InaccessiblePaths=/etc/dharma-sadhana/credentials/control_hmac_key ",
            "InaccessiblePaths=/var/lib/dharma-sadhana/state "
            "/etc/dharma-sadhana/credentials/control_hmac_key ",
            "dispatch enable unit binding differs",
        ),
        (
            "dharma-sadhana-control-directories.service.in",
            "ReadWritePaths=/run/dharma-sadhana ",
            "ReadWritePaths=-/run/dharma-sadhana ",
            "control directory write namespace differs",
        ),
        (
            "dharma-sadhana-control-directories.service.in",
            "CapabilityBoundingSet=CAP_CHOWN CAP_DAC_OVERRIDE CAP_FOWNER",
            "CapabilityBoundingSet=CHOWN DAC_OVERRIDE FOWNER",
            "control directory write namespace differs",
        ),
        (
            "dharma-sadhana-projection-sync.service.in",
            "CapabilityBoundingSet=CAP_CHOWN CAP_DAC_OVERRIDE CAP_FOWNER",
            "CapabilityBoundingSet=CHOWN DAC_OVERRIDE FOWNER",
            "observer projection sync binding differs",
        ),
        (
            "dharma-sadhana-oracle-directories.service.in",
            "Requires=dharma-sadhana-control-directories.service",
            "Requires=network-online.target",
            "oracle directory unit binding differs",
        ),
        (
            "dharma-sadhana-oracle-directories.service.in",
            "ReadWritePaths=/run/dharma-sadhana "
            "/var/lib/dharma-sadhana/oracle-inputs "
            "/var/lib/dharma-sadhana/oracle-claims "
            "/var/lib/dharma-sadhana/oracle-runs "
            "/var/lib/dharma-sadhana/oracle-quarantine "
            "/etc/dharma-sadhana/receipts/oracle",
            "ReadWritePaths=/run/dharma-sadhana "
            "/var/lib/dharma-sadhana/oracle-inputs "
            "/var/lib/dharma-sadhana/oracle-claims "
            "/var/lib/dharma-sadhana/oracle-runs "
            "/var/lib/dharma-sadhana/oracle-quarantine "
            "/etc/dharma-sadhana/receipts",
            "oracle directory unit binding differs",
        ),
        (
            "dharma-sadhana-oracle-directories.service.in",
            "ReadWritePaths=/run/dharma-sadhana "
            "/var/lib/dharma-sadhana/oracle-inputs "
            "/var/lib/dharma-sadhana/oracle-claims "
            "/var/lib/dharma-sadhana/oracle-runs "
            "/var/lib/dharma-sadhana/oracle-quarantine "
            "/etc/dharma-sadhana/receipts/oracle",
            "ReadWritePaths=/run/dharma-sadhana "
            "/var/lib/dharma-sadhana/oracle-inputs "
            "/var/lib/dharma-sadhana/oracle-claims "
            "/var/lib/dharma-sadhana/oracle-runs "
            "/var/lib/dharma-sadhana/oracle-quarantine "
            "/etc/dharma-sadhana/receipts/oracle\n"
            "ReadWritePaths=/etc/dharma-sadhana/receipts/preactivation",
            "oracle directory unit binding differs",
        ),
        (
            "dharma-sadhana-dashboard.service.in",
            "ReadWritePaths=/run/dharma-sadhana/dashboard",
            "ReadWritePaths=-/run/dharma-sadhana/dashboard",
            "dashboard control bridge binding differs",
        ),
    ),
)
def test_supervisor_import_and_unit_validator_reject_broader_runtime_namespaces(
    name: str,
    old: str,
    hostile: str,
    error: str,
) -> None:
    path = Path(__file__).resolve().parents[1] / "deploy/sadhana/systemd" / name
    text = path.read_text(encoding="utf-8")
    assert text.count(old) == 1
    with pytest.raises(release.ReleaseContractError, match=error):
        release.validate_unit_text(
            name,
            text.replace(old, hostile),
            rendered=False,
        )


def test_supervisor_validator_rejects_expiring_capacity_gate_on_restart() -> None:
    unit = Path(__file__).resolve().parents[1] / (
        "deploy/sadhana/systemd/dharma-sadhana-supervisor.service.in"
    )
    text = unit.read_text(encoding="utf-8")
    hostile = text.replace(
        "ExecStart=/opt/dharma-sadhana/releases/",
        "ExecStartPre=+/opt/dharma-sadhana/releases/@RELEASE_SHA@/.venv/bin/python "
        "/opt/dharma-sadhana/releases/@RELEASE_SHA@/scripts/runtime/"
        "sadhana_release.py guard-standby-capacity --role writer "
        "--release-sha @RELEASE_SHA@ --projection-path "
        "${SADHANA_PROJECTION_PATH}\nExecStart=/opt/dharma-sadhana/releases/",
        1,
    )
    with pytest.raises(release.ReleaseContractError, match="expiring"):
        release.validate_unit_text(unit.name, hostile, rendered=False)


def test_supervisor_activation_transition_runs_inside_locked_campaign_process() -> None:
    unit = Path(__file__).resolve().parents[1] / (
        "deploy/sadhana/systemd/dharma-sadhana-supervisor.service.in"
    )
    text = unit.read_text(encoding="utf-8")
    assert "activate-campaign-session" not in text
    activation = next(line for line in text.splitlines() if line.startswith("ExecStart="))
    assert "mission_control_campaign.py run" in activation
    hostile = text.replace(
        "--activation-evidence-path /run/dharma-sadhana/control/activation/"
        "campaign-activation.v1.json",
        "--activation-evidence-path /run/dharma-sadhana/control/foreign.json",
        1,
    )
    with pytest.raises(release.ReleaseContractError, match="supervisor"):
        release.validate_unit_text(unit.name, hostile, rendered=False)


def test_clock_proof_requires_ntp_bounded_skew_and_exact_installed_timer(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    release_sha = "a" * 40
    release_root = tmp_path / "releases"
    systemd_root = tmp_path / "systemd"
    timer = (
        release_root
        / release_sha
        / release.SYSTEMD_TEMPLATE_ROOT
        / release.CAMPAIGN_STOP_TIMER
    )
    installed = systemd_root / release.CAMPAIGN_STOP_TIMER
    timer_bytes = (
        Path(__file__).resolve().parents[1]
        / "deploy/sadhana/systemd/dharma-sadhana-campaign-stop.timer"
    ).read_bytes()
    for path in (timer, installed):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(timer_bytes)
        path.chmod(0o600)
    receipt_path = tmp_path / "preactivation-clock-proof.json"
    monkeypatch.setattr(release, "PREACTIVATION_CLOCK_RECEIPT", receipt_path)
    monkeypatch.setattr(release, "DEPLOYMENT_KNOWN_HOSTS_SHA256", "b" * 64)
    monkeypatch.setattr(release, "RELEASE_ROOT", str(release_root))
    monkeypatch.setattr(release, "SYSTEMD_OUTPUT_ROOT", systemd_root)
    observed = datetime(2026, 8, 23, 0, 0, 5, tzinfo=timezone.utc)

    def synchronized(argv, **_kwargs):  # noqa: ANN001, ANN202
        return subprocess.CompletedProcess(argv, 0, "yes\n", "")

    proof = release.record_preactivation_clock_proof(
        role="writer",
        release_sha=release_sha,
        controller_utc="2026-08-23T00:00:00Z",
        known_hosts_sha256="b" * 64,
        strict_host_key_channel=True,
        staged_release_admission_receipt_digest="sha256:" + "c" * 64,
        release_timer_path=timer,
        installed_timer_path=installed,
        receipt_path=receipt_path,
        runner=synchronized,
        now=observed,
        observed_node=release.WRITER_NODE,
        ssh_connection_observed=True,
        expected_root_uid=os.geteuid(),
        expected_root_gid=os.getegid(),
    )
    assert proof["ntp_synchronized"] is True
    assert proof["skew_seconds"] == 5
    assert proof["installed_timer_match"] is True
    assert stat.S_IMODE(receipt_path.stat().st_mode) == 0o600
    admitted = release.validate_preactivation_clock_proof(
        release_sha=release_sha,
        role="writer",
        known_hosts_sha256="b" * 64,
        staged_release_admission_receipt_digest="sha256:" + "c" * 64,
        receipt_path=receipt_path,
        now=observed + timedelta(seconds=30),
        observed_node=release.WRITER_NODE,
        expected_root_uid=os.geteuid(),
        expected_root_gid=os.getegid(),
    )
    assert admitted["timer_on_calendar"] == "2026-09-01 17:15:12 UTC"
    installed.write_bytes(timer_bytes + b"# post-proof drift\n")
    with pytest.raises(release.ReleaseContractError, match="stop timer drifted"):
        release.validate_preactivation_clock_proof(
            release_sha=release_sha,
            role="writer",
            known_hosts_sha256="b" * 64,
            staged_release_admission_receipt_digest="sha256:" + "c" * 64,
            receipt_path=receipt_path,
            now=observed + timedelta(seconds=30),
            observed_node=release.WRITER_NODE,
            expected_root_uid=os.geteuid(),
            expected_root_gid=os.getegid(),
        )
    installed.write_bytes(timer_bytes)
    with pytest.raises(release.ReleaseContractError, match="not fresh"):
        release.validate_preactivation_clock_proof(
            release_sha=release_sha,
            role="writer",
            known_hosts_sha256="b" * 64,
            staged_release_admission_receipt_digest="sha256:" + "c" * 64,
            receipt_path=receipt_path,
            now=observed + timedelta(seconds=121),
            observed_node=release.WRITER_NODE,
            expected_root_uid=os.geteuid(),
            expected_root_gid=os.getegid(),
        )
    with pytest.raises(release.ReleaseContractError, match="exact bindings"):
        release.validate_preactivation_clock_proof(
            release_sha=release_sha,
            role="standby",
            known_hosts_sha256="b" * 64,
            staged_release_admission_receipt_digest="sha256:" + "c" * 64,
            receipt_path=receipt_path,
            now=observed + timedelta(seconds=30),
            observed_node=release.STANDBY_NODE,
            expected_root_uid=os.geteuid(),
            expected_root_gid=os.getegid(),
        )
    receipt_path.unlink()
    with pytest.raises(release.ReleaseContractError, match="unavailable"):
        release.validate_preactivation_clock_proof(
            release_sha=release_sha,
            role="writer",
            known_hosts_sha256="b" * 64,
            staged_release_admission_receipt_digest="sha256:" + "c" * 64,
            receipt_path=receipt_path,
            now=observed + timedelta(seconds=30),
            observed_node=release.WRITER_NODE,
            expected_root_uid=os.geteuid(),
            expected_root_gid=os.getegid(),
        )

    def unsynchronized(argv, **_kwargs):  # noqa: ANN001, ANN202
        return subprocess.CompletedProcess(argv, 0, "no\n", "")

    with pytest.raises(release.ReleaseContractError, match="NTP-synchronized"):
        release.record_preactivation_clock_proof(
            role="writer",
            release_sha=release_sha,
            controller_utc="2026-08-23T00:00:00Z",
            known_hosts_sha256="b" * 64,
            strict_host_key_channel=True,
            staged_release_admission_receipt_digest="sha256:" + "c" * 64,
            release_timer_path=timer,
            installed_timer_path=installed,
            receipt_path=receipt_path,
            runner=unsynchronized,
            now=observed,
            observed_node=release.WRITER_NODE,
            ssh_connection_observed=True,
            expected_root_uid=os.geteuid(),
            expected_root_gid=os.getegid(),
        )
    with pytest.raises(release.ReleaseContractError, match="skew bound"):
        release.record_preactivation_clock_proof(
            role="writer",
            release_sha="a" * 40,
            controller_utc="2026-08-23T00:00:00Z",
            known_hosts_sha256="b" * 64,
            strict_host_key_channel=True,
            staged_release_admission_receipt_digest="sha256:" + "c" * 64,
            release_timer_path=timer,
            installed_timer_path=installed,
            receipt_path=receipt_path,
            runner=synchronized,
            now=observed + timedelta(seconds=31),
            observed_node=release.WRITER_NODE,
            ssh_connection_observed=True,
            expected_root_uid=os.geteuid(),
            expected_root_gid=os.getegid(),
        )


@pytest.mark.parametrize(
    ("role", "timer_unit"),
    [
        ("writer", release.CAMPAIGN_STOP_TIMER),
        ("standby", release.STANDBY_STOP_TIMER),
    ],
)
def test_clock_proof_cli_selects_the_role_specific_timer(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    role: str,
    timer_unit: str,
) -> None:
    release_sha = "a" * 40
    release_root = tmp_path / "releases"
    systemd_root = tmp_path / "systemd"
    monkeypatch.setattr(release, "RELEASE_ROOT", str(release_root))
    monkeypatch.setattr(release, "SYSTEMD_OUTPUT_ROOT", systemd_root)
    monkeypatch.setattr(
        release,
        "_verify_activation_staged_release",
        lambda **_kwargs: (
            {"receipt_digest": "sha256:" + "7" * 64},
            SimpleNamespace(),
        ),
    )
    captured: dict[str, object] = {}

    def record(**kwargs):  # noqa: ANN003, ANN202
        captured.update(kwargs)
        return {
            "hostname": f"{role}-fixture",
            "skew_seconds": 0,
            "valid_until": "2026-08-23T00:02:00Z",
        }

    monkeypatch.setattr(release, "record_preactivation_clock_proof", record)
    assert (
        release.main(
            [
                "clock-proof",
                "--role",
                role,
                "--release-sha",
                release_sha,
                "--controller-utc",
                "2026-08-23T00:00:00Z",
                "--known-hosts-sha256",
                release.DEPLOYMENT_KNOWN_HOSTS_SHA256,
                "--strict-host-key-channel",
            ]
        )
        == 0
    )
    assert captured["role"] == role
    assert captured["release_timer_path"] == (
        release_root
        / release_sha
        / release.SYSTEMD_TEMPLATE_ROOT
        / timer_unit
    )
    assert captured["installed_timer_path"] == systemd_root / timer_unit
    assert captured["staged_release_admission_receipt_digest"] == (
        "sha256:" + "7" * 64
    )
    assert json.loads(capsys.readouterr().out)["role"] == role


@pytest.mark.parametrize("phase", ["predispatch", "dispatch", "standby"])
@pytest.mark.parametrize("failure", ["missing", "stale", "wrong"])
def test_bad_clock_proof_precedes_every_activation_effect(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    phase: str,
    failure: str,
) -> None:
    os.chmod(tmp_path, 0o700)
    release_sha = "a" * 40
    paths = {
        "writer": tmp_path / "writer-enabled",
        "predispatch": tmp_path / "predispatch.json",
        "predispatch_intent": tmp_path / "predispatch-intent.json",
        "dispatch": tmp_path / "dispatch.json",
        "rollback": tmp_path / "rollback.json",
        "standby": tmp_path / "standby.json",
        "standby_intent": tmp_path / "standby-intent.json",
        "activation_env": tmp_path / "supervisor-activation.env",
    }
    for name, constant in (
        ("writer", "WRITER_MARKER"),
        ("predispatch", "PREDISPATCH_ACTIVATION_RECEIPT"),
        ("predispatch_intent", "PREDISPATCH_ACTIVATION_INTENT"),
        ("dispatch", "DISPATCH_ENABLE_MARKER"),
        ("rollback", "ROLLBACK_RECEIPT"),
        ("standby", "STANDBY_ACTIVATION_RECEIPT"),
        ("standby_intent", "STANDBY_ACTIVATION_INTENT"),
        ("activation_env", "SUPERVISOR_ACTIVATION_ENV"),
    ):
        monkeypatch.setattr(release, constant, paths[name])
    monkeypatch.setattr(release, "guard_campaign_clock", lambda **_kwargs: None)
    monkeypatch.setattr(
        release,
        "_verify_activation_staged_release",
        lambda **_kwargs: (
            {"receipt_digest": "sha256:" + "7" * 64},
            SimpleNamespace(),
        ),
    )
    monkeypatch.setattr(
        release,
        "_load_predispatch_activation_for_dispatch",
        lambda **_kwargs: {
            "staged_release_admission_receipt_digest": "sha256:" + "7" * 64
        },
    )
    effects: list[str] = []
    monkeypatch.setattr(
        release,
        "publish_runtime_binding_activation",
        lambda **_kwargs: effects.append("runtime-binding"),
    )
    monkeypatch.setattr(
        release,
        "finalize_disabled_runtime_staging",
        lambda **_kwargs: effects.append("runtime-staging"),
    )
    monkeypatch.setattr(
        release,
        "_publish_supervisor_activation_env",
        lambda **_kwargs: effects.append("activation-env"),
    )

    def rejected_clock(**_kwargs):  # noqa: ANN202
        if failure == "missing":
            raise FileNotFoundError("clock proof missing")
        if failure == "stale":
            raise release.ReleaseContractError("clock proof is not fresh")
        raise release.ReleaseContractError("clock-proof exact bindings differ")

    monkeypatch.setattr(release, "validate_preactivation_clock_proof", rejected_clock)
    systemctl_mutations: list[tuple[str, ...]] = []

    def runner(argv, **_kwargs):  # noqa: ANN001, ANN202
        command = tuple(argv)
        if len(command) > 1 and command[1] in {
            "daemon-reload",
            "disable",
            "enable",
            "mask",
            "start",
            "stop",
            "unmask",
        }:
            systemctl_mutations.append(command)
        if command[1:3] == ("show", "--property=MainPID"):
            return subprocess.CompletedProcess(argv, 0, "0\n", "")
        return subprocess.CompletedProcess(argv, 0, "", "")

    observed = datetime(2026, 8, 23, 1, tzinfo=timezone.utc)
    with pytest.raises((OSError, release.ReleaseContractError)):
        if phase == "predispatch":
            release.activate_predispatch(
                role="writer",
                release_sha=release_sha,
                receipt_path=paths["predispatch"],
                intent_path=paths["predispatch_intent"],
                runner=runner,
                now=observed,
                observed_node=release.WRITER_NODE,
                expected_root_uid=os.geteuid(),
                expected_root_gid=os.getegid(),
            )
        elif phase == "dispatch":
            release.enable_dispatch(
                role="writer",
                release_sha=release_sha,
                marker_path=paths["dispatch"],
                runner=runner,
                now=observed,
                observed_node=release.WRITER_NODE,
                expected_root_uid=os.geteuid(),
                expected_root_gid=os.getegid(),
            )
        else:
            release.activate_standby(
                role="standby",
                release_sha=release_sha,
                receipt_path=paths["standby"],
                intent_path=paths["standby_intent"],
                runner=runner,
                now=observed,
                observed_node=release.STANDBY_NODE,
                expected_root_uid=os.geteuid(),
                expected_root_gid=os.getegid(),
            )
    assert effects == []
    assert systemctl_mutations == []
    assert not any(path.exists() or path.is_symlink() for path in paths.values())


def test_observer_health_acceptance_proves_twenty_responses_before_dispatch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    release_sha = "a" * 40
    unit = tmp_path / release.OBSERVER_UNIT
    unit.write_text(
        "\n".join(
            (
                f"ReadOnlyPaths=/opt/dharma-sadhana/releases/{release_sha}/",
                "EnvironmentFile=/etc/dharma-sadhana/api.env",
                "ExecStart=/python -m uvicorn app --host 127.0.0.1 "
                "--port ${SADHANA_API_PORT}",
            )
        )
        + "\n",
        encoding="utf-8",
    )
    unit.chmod(0o600)
    receipt = tmp_path / "observer-health.json"
    monkeypatch.setattr(release, "OBSERVER_UNIT_PATH", unit)
    monkeypatch.setattr(release, "OBSERVER_HEALTH_RECEIPT", receipt)

    pid = 4242
    process = tmp_path / "proc" / str(pid)
    (process / "fd").mkdir(parents=True)
    (process / "root").mkdir()
    uid = os.geteuid()
    gid = os.getegid()
    monkeypatch.setattr(
        release,
        "_require_observer_identity",
        lambda: SimpleNamespace(pw_uid=uid, pw_gid=gid),
    )
    expected_argv = (
        f"{release.RELEASE_ROOT}/{release_sha}/.venv/bin/python",
        "-m",
        "uvicorn",
        "scripts.runtime.sadhana_immutable_api:app",
        "--host",
        "127.0.0.1",
        "--port",
        "18420",
        "--workers",
        "1",
        "--no-access-log",
        "--no-proxy-headers",
    )
    (process / "cmdline").write_bytes(
        b"\0".join(value.encode() for value in expected_argv) + b"\0"
    )
    (process / "status").write_text(
        f"Uid:\t{uid}\t{uid}\t{uid}\t{uid}\n"
        f"Gid:\t{gid}\t{gid}\t{gid}\t{gid}\n"
        f"Groups:\t{gid}\nNoNewPrivs:\t1\n",
        encoding="ascii",
    )
    stat_fields = ["0"] * 20
    stat_fields[0] = "S"
    stat_fields[19] = "12345"
    (process / "stat").write_text(
        f"{pid} (uvicorn) " + " ".join(stat_fields) + "\n",
        encoding="utf-8",
    )
    (process / "net").mkdir()
    (process / "net/tcp").write_text(
        "  sl  local_address rem_address st tx_queue rx_queue tr tm->when "
        "retrnsmt uid timeout inode\n"
        "  0: 0100007F:47F4 00000000:0000 0A 0:0 00:0 0 0 0 555\n",
        encoding="ascii",
    )
    (process / "fd/7").symlink_to("socket:[555]")

    def runner(argv, **_kwargs):  # noqa: ANN001, ANN202
        unit_name = argv[-1]
        value = str(pid) if unit_name == release.OBSERVER_UNIT else "0"
        return subprocess.CompletedProcess(argv, 0, value + "\n", "")

    health = release._canonical_bytes(
        {
            "status": "ok",
            "mode": "immutable_observer",
            "runtime_projection_mode": "unavailable",
            "proves_executor_liveness": False,
            "write_routes": 0,
        }
    )
    clock_values = iter(
        (
            datetime(2026, 8, 23, 1, tzinfo=timezone.utc),
            datetime(2026, 8, 23, 1, 0, 1, tzinfo=timezone.utc),
        )
    )
    ticks = iter(float(value) for value in range(20))
    payload = release.probe_observer_health(
        role="writer",
        release_sha=release_sha,
        receipt_path=receipt,
        unit_path=unit,
        runner=runner,
        fetcher=lambda _endpoint: health,
        proc_root=tmp_path / "proc",
        now=lambda: next(clock_values),
        monotonic=lambda: next(ticks),
        observed_node=release.WRITER_NODE,
        expected_root_uid=os.geteuid(),
        expected_root_gid=os.getegid(),
    )
    assert payload["consecutive_successes"] == 20
    assert payload["dispatch_enabled_during_probe"] is False
    assert payload["listener_process_identity"]["socket_inode"] == 555
    assert payload["listener_process_identity"]["canonical_path_visible"] is False
    assert len(payload["response_sha256_sequence"]) == 20
    assert release._secure_json(receipt, require_private=True) == payload


def test_observer_health_rejects_any_existing_supervisor_before_first_probe(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fetches = 0

    def fetcher(_endpoint: str) -> bytes:
        nonlocal fetches
        fetches += 1
        return b"{}"

    monkeypatch.setattr(release, "_require_host_role", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(release, "guard_campaign_clock", lambda **_kwargs: None)
    monkeypatch.setattr(release, "_systemd_main_pid", lambda *_args, **_kwargs: 17)
    with pytest.raises(release.ReleaseContractError, match="dispatch process exists"):
        release.probe_observer_health(
            role="writer",
            release_sha="a" * 40,
            runner=lambda *_args, **_kwargs: subprocess.CompletedProcess([], 0, "", ""),
            fetcher=fetcher,
            observed_node=release.WRITER_NODE,
            expected_root_uid=os.geteuid(),
            expected_root_gid=os.getegid(),
        )
    assert fetches == 0


def test_dashboard_v5_acceptance_binds_account_ui_confirmation_and_login(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    release_sha = "a" * 40
    observed = datetime(2026, 8, 23, 1, tzinfo=timezone.utc)
    operator_login = b"operator@example.test"
    operator_login_sha256 = hashlib.sha256(operator_login).hexdigest()
    credential_root = tmp_path / "credentials"
    credential_root.mkdir(mode=0o700)
    login_source = credential_root / "tailscale_operator_login"
    login_source.write_bytes(operator_login)
    login_source.chmod(0o600)
    monkeypatch.setattr(release, "CONTROL_LOGIN_SOURCE", login_source)
    systemd_root = tmp_path / "systemd"
    systemd_root.mkdir(mode=0o700)
    dashboard_unit = systemd_root / release.DASHBOARD_UNIT
    dashboard_unit.write_text("[Service]\nUser=dharma-sadhana-dashboard\n")
    dashboard_unit.chmod(0o600)
    monkeypatch.setattr(release, "SYSTEMD_OUTPUT_ROOT", systemd_root)
    ownership_path = tmp_path / "tailscale" / "ownership.json"
    ownership_path.parent.mkdir(mode=0o700)
    monkeypatch.setattr(release, "TAILSCALE_OWNERSHIP_RECEIPT", ownership_path)
    intent_path = ownership_path.parent / "intent.json"
    monkeypatch.setattr(release, "TAILSCALE_INTENT_RECEIPT", intent_path)
    owned = _owned_tailscale_config()
    intent = _write_tailscale_intent(intent_path, release_sha)
    release._write_tailscale_ownership_receipt(
        ownership_path,
        owned,
        release_sha=release_sha,
        intent=intent,
        expected_root_uid=os.geteuid(),
        expected_root_gid=os.getegid(),
    )

    rollback_path = tmp_path / "dashboard-rollback.json"
    rollback = _write_self_digest_receipt(
        rollback_path,
        {
            "schema_version": release.DASHBOARD_ROLLBACK_SCHEMA_VERSION,
            "campaign_id": release.MISSION_ID,
            "release_sha": release_sha,
            "supervisor_main_pid": 0,
            "verdict": "PASS",
            "receipt_digest": "",
        },
    )
    authenticated_path = tmp_path / "authenticated-account-ui-confirmation.json"
    empty_ledger_digest = release._empty_account_ui_inbox_ledger_sha256()
    authenticated = _write_self_digest_receipt(
        authenticated_path,
        {
            "schema_version": release.ACCOUNT_UI_CONFIRMATION_SCHEMA_VERSION,
            "campaign_id": release.MISSION_ID,
            "release_sha": release_sha,
            "client_request_id_sha256": "1" * 64,
            "source_candidate_sha256": "2" * 64,
            "viewport_width_css_px_reported": 390,
            "document_width_css_px_reported": 390,
            "visual_viewport_width_css_px_reported": 390,
            "coarse_pointer_reported": True,
            "touch_capability_reported": True,
            "trusted_browser_event_reported": True,
            "explicit_confirmation_gesture_reported": True,
            "dashboard_rendered_reported": True,
            "private_tailnet_https": True,
            "identity_header_injected": True,
            "operator_account_allowlist_match": True,
            "operator_login_sha256": operator_login_sha256,
            "normal_control_request_sent": False,
            "external_message_sent": False,
            "physical_device_attested": False,
            "human_identity_attested": False,
            "predispatch_gate_receipt_digest": "sha256:" + "3" * 64,
            "normal_and_emergency_inbox_ledger_sha256_before": (
                empty_ledger_digest
            ),
            "normal_and_emergency_inbox_ledger_sha256_after": (
                empty_ledger_digest
            ),
            "normal_and_emergency_inboxes_unchanged": True,
            "observed_at": observed.isoformat().replace("+00:00", "Z"),
            "receipt_digest": "",
        },
    )
    monkeypatch.setattr(
        release, "ACCOUNT_UI_CONFIRMATION_RECEIPT", authenticated_path
    )
    receipt_path = tmp_path / "dashboard-identity.json"
    uid = os.geteuid()
    gid = os.getegid()
    process_identity = {
        "unit": release.DASHBOARD_UNIT,
        "main_pid": 4123,
        "uid": uid,
        "gid": gid,
        "cmdline_sha256": "b" * 64,
        "socket_path": str(release.DASHBOARD_SOCKET_PATH),
        "socket_dev": 10,
        "socket_ino": 11,
        "listener_inode": 12,
        "tcp_listener_count": 0,
        "release_sha": release_sha,
    }
    account = SimpleNamespace(pw_name="dharma-sadhana", pw_uid=uid, pw_gid=gid)
    monkeypatch.setattr(release, "guard_campaign_clock", lambda **_kwargs: None)
    monkeypatch.setattr(
        release,
        "_systemd_main_pid",
        lambda unit, **_kwargs: 0 if unit == release.SUPERVISOR_UNIT else 4123,
    )
    monkeypatch.setattr(
        release, "_dashboard_listener_identity", lambda **_kwargs: process_identity
    )
    monkeypatch.setattr(release, "_require_tailscale_version", lambda **_kwargs: None)
    monkeypatch.setattr(release, "_read_tailscale_status", lambda **_kwargs: owned)
    monkeypatch.setattr(release, "_listener_count", lambda *_args, **_kwargs: 0)
    monkeypatch.setattr(release, "_require_static_service_identity", lambda: account)
    monkeypatch.setattr(
        release,
        "_publish_predispatch_account_ui_gate",
        lambda *_args, **_kwargs: {},
    )
    monkeypatch.setattr(release.pwd, "getpwnam", lambda _name: account)

    payload = release.record_dashboard_identity_acceptance(
        role="writer",
        release_sha=release_sha,
        rollback_receipt_path=rollback_path,
        receipt_path=receipt_path,
        now=observed + timedelta(seconds=1),
        observed_node=release.WRITER_NODE,
        expected_root_uid=uid,
        expected_root_gid=gid,
        access_probe=lambda *_args, **_kwargs: True,
    )
    assert payload["authenticated_account_ui_confirmation"] == authenticated
    assert payload["operator_login_sha256"] == operator_login_sha256
    assert payload["rollback_probe"] == rollback
    assert (
        payload["authenticated_account_ui_confirmation"][
            "viewport_width_css_px_reported"
        ]
        == 390
    )
    assert (
        payload["authenticated_account_ui_confirmation"][
            "normal_control_request_sent"
        ]
        is False
    )
    assert (
        payload["authenticated_account_ui_confirmation"][
            "physical_device_attested"
        ]
        is False
    )
    assert payload["tcp_listener_inventory"] == {
        "dashboard_process": 0,
        "host_port_3000": 0,
    }
    assert all(payload["negative_access_matrix"].values())

    authenticated["viewport_width_css_px_reported"] = 391
    _write_self_digest_receipt(authenticated_path, authenticated)
    with pytest.raises(release.ReleaseContractError, match="account UI confirmation"):
        release.record_dashboard_identity_acceptance(
            role="writer",
            release_sha=release_sha,
            rollback_receipt_path=rollback_path,
            receipt_path=tmp_path / "rejected-dashboard-identity.json",
            now=observed + timedelta(seconds=1),
            observed_node=release.WRITER_NODE,
            expected_root_uid=uid,
            expected_root_gid=gid,
            access_probe=lambda *_args, **_kwargs: True,
        )


def test_v4_operator_bearer_acceptance_records_only_equality_and_denials(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    release_sha = "a" * 40
    secret = b"operator-bearer-fixture-with-enough-entropy"
    credential_root = tmp_path / "credentials"
    credential_root.mkdir(mode=0o700)
    source = credential_root / "operator_bearer"
    hmac_source = credential_root / "control_hmac_key"
    login_source = credential_root / "tailscale_operator_login"
    copy_root = tmp_path / "copies"
    copy_root.mkdir(mode=0o700)
    dashboard_copy = copy_root / "dashboard-copy"
    control_copy = copy_root / "control-copy"
    source.write_bytes(secret)
    source.chmod(0o600)
    hmac_source.write_bytes(b"h" * 32)
    login_source.write_bytes(b"operator@example.com")
    for path in (hmac_source, login_source):
        path.chmod(0o600)
    for path in (dashboard_copy, control_copy):
        path.write_bytes(secret)
        path.chmod(0o400)

    systemd_root = tmp_path / "systemd"
    systemd_root.mkdir(mode=0o700)
    for unit in (release.DASHBOARD_UNIT, "dharma-sadhana-control.service"):
        path = systemd_root / unit
        path.write_text("[Service]\nLoadCredential=operator_bearer:/root/source\n")
        path.chmod(0o600)
    monkeypatch.setattr(release, "SYSTEMD_OUTPUT_ROOT", systemd_root)
    uid = os.geteuid()
    gid = os.getegid()
    account = SimpleNamespace(pw_name="dharma-sadhana", pw_uid=uid, pw_gid=gid)
    monkeypatch.setattr(release, "_require_static_service_identity", lambda: account)
    monkeypatch.setattr(release.pwd, "getpwnam", lambda _name: account)
    monkeypatch.setattr(
        release,
        "_systemd_main_pid",
        lambda unit, **_kwargs: {
            release.DASHBOARD_UNIT: 4101,
            "dharma-sadhana-control.service": 4102,
            }.get(unit, 0),
    )
    control_identity = {
        "unit": "dharma-sadhana-control.service",
        "main_pid": 4102,
        "proc_start_ticks": 100,
        "cmdline_sha256": "c" * 64,
        "socket_inode": 18421,
        "listen_address": "127.0.0.1:18421",
        "uid": uid,
        "gid": gid,
        "no_new_privileges": True,
        "release_sha": release_sha,
    }
    monkeypatch.setattr(
        release,
        "_control_listener_identity",
        lambda **_kwargs: control_identity,
    )
    dashboard_identity = {
        "unit": release.DASHBOARD_UNIT,
        "main_pid": 4101,
        "uid": uid,
        "gid": gid,
        "socket_ino": 18422,
        "listener_inode": 18422,
        "release_sha": release_sha,
    }
    monkeypatch.setattr(
        release,
        "_dashboard_listener_identity",
        lambda **_kwargs: dashboard_identity,
    )
    sink_result = {
        "process_environment_and_argv": True,
        "unit_files": True,
        "service_journal": True,
        "release_source": True,
        "browser_public_environment_forbidden": True,
        "receipt_secret_fields_forbidden": True,
    }
    receipt_path = tmp_path / "credential-receipt.json"
    payload = release.record_operator_credential_acceptance(
        role="writer",
        release_sha=release_sha,
        receipt_path=receipt_path,
        source_path=source,
        dashboard_copy=dashboard_copy,
        control_copy=control_copy,
        observed_node=release.WRITER_NODE,
        expected_root_uid=uid,
        expected_root_gid=gid,
        access_probe=lambda *_args, **_kwargs: True,
        sink_scan=lambda *_args, **_kwargs: sink_result,
        positive_read_probe=lambda **_kwargs: _positive_bearer_probe_payload(),
    )
    assert payload["credential_copies_equal"] is True
    assert all(payload["negative_reader_matrix"].values())
    assert all(payload["secret_sink_scan"].values())
    raw = receipt_path.read_bytes()
    assert secret not in raw
    assert hashlib.sha256(secret).hexdigest().encode() not in raw
    assert payload["dashboard_credential_custody"]["positive_read_proven"] is True
    assert (
        payload["dashboard_credential_custody"][
            "connected_peer_identity_proven"
        ]
        is True
    )
    assert payload["control_credential_custody"]["positive_read_proven"] is True
    assert (
        payload["control_credential_custody"]["listener_process_identity"]
        == control_identity
    )
    assert (
        payload["control_credential_custody"]["decision_or_effect_state_proven"]
        is False
    )
    assert payload["source_file_custody"]["source_root_exact_three_entries"] is True

    extra = credential_root / "future_provider_token"
    extra.write_bytes(b"x" * 32)
    extra.chmod(0o600)
    with pytest.raises(release.ReleaseContractError, match="root inventory"):
        release.record_operator_credential_acceptance(
            role="writer",
            release_sha=release_sha,
            receipt_path=tmp_path / "credential-extra-rejected.json",
            source_path=source,
            dashboard_copy=dashboard_copy,
            control_copy=control_copy,
            observed_node=release.WRITER_NODE,
            expected_root_uid=uid,
            expected_root_gid=gid,
            access_probe=lambda *_args, **_kwargs: True,
            sink_scan=lambda *_args, **_kwargs: sink_result,
            positive_read_probe=lambda **_kwargs: _positive_bearer_probe_payload(),
        )
    extra.unlink()
    extra.symlink_to(source)
    with pytest.raises(release.ReleaseContractError, match="root inventory"):
        release.record_operator_credential_acceptance(
            role="writer",
            release_sha=release_sha,
            receipt_path=tmp_path / "credential-symlink-rejected.json",
            source_path=source,
            dashboard_copy=dashboard_copy,
            control_copy=control_copy,
            observed_node=release.WRITER_NODE,
            expected_root_uid=uid,
            expected_root_gid=gid,
            access_probe=lambda *_args, **_kwargs: True,
            sink_scan=lambda *_args, **_kwargs: sink_result,
            positive_read_probe=lambda **_kwargs: _positive_bearer_probe_payload(),
        )
    extra.unlink()

    control_copy.chmod(0o600)
    control_copy.write_bytes(b"different-operator-bearer-fixture-value")
    control_copy.chmod(0o400)
    with pytest.raises(release.ReleaseContractError, match="copies differ"):
        release.record_operator_credential_acceptance(
            role="writer",
            release_sha=release_sha,
            receipt_path=tmp_path / "credential-rejected.json",
            source_path=source,
            dashboard_copy=dashboard_copy,
            control_copy=control_copy,
            observed_node=release.WRITER_NODE,
            expected_root_uid=uid,
            expected_root_gid=gid,
            access_probe=lambda *_args, **_kwargs: True,
            sink_scan=lambda *_args, **_kwargs: sink_result,
            positive_read_probe=lambda **_kwargs: _positive_bearer_probe_payload(),
        )


def test_dispatch_inventory_requires_exact_masked_hmac_overlay_and_no_extra(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "credentials"
    root.mkdir(mode=0o700)
    bearer = root / "operator_bearer"
    hmac_source = root / "control_hmac_key"
    login = root / "tailscale_operator_login"
    bearer.write_bytes(b"b" * 32)
    login.write_bytes(b"operator@example.test")
    hmac_source.write_bytes(b"")
    bearer.chmod(0o600)
    login.chmod(0o600)
    hmac_source.chmod(0o000)
    real_open = release.os.open

    def namespace_open(path, flags, *args, **kwargs):  # noqa: ANN001, ANN202
        if path == "control_hmac_key" and kwargs.get("dir_fd") is not None:
            raise PermissionError(errno.EACCES, "systemd inaccessible overlay")
        return real_open(path, flags, *args, **kwargs)

    monkeypatch.setattr(release.os, "open", namespace_open)
    uid = os.geteuid()
    gid = os.getegid()
    assert release._control_credential_source_inventory(
        root,
        expected_root_uid=uid,
        expected_root_gid=gid,
        hmac_masked=True,
    ) == (
        "control_hmac_key",
        "operator_bearer",
        "tailscale_operator_login",
    )
    with pytest.raises(release.ReleaseContractError, match="inventory custody"):
        release._control_credential_source_inventory(
            root,
            expected_root_uid=uid,
            expected_root_gid=gid,
            hmac_masked=False,
        )
    extra = root / "future_provider_token"
    extra.write_bytes(b"never-read")
    extra.chmod(0o600)
    with pytest.raises(release.ReleaseContractError, match="root inventory"):
        release._control_credential_source_inventory(
            root,
            expected_root_uid=uid,
            expected_root_gid=gid,
            hmac_masked=True,
        )


def test_control_reader_identity_rejects_a_foreign_loopback_501_listener(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    release_sha = "a" * 40
    uid = os.geteuid()
    gid = os.getegid()
    if uid == 0 or gid == 0:
        uid, gid = 501, 502
    monkeypatch.setattr(
        release.pwd,
        "getpwnam",
        lambda _name: SimpleNamespace(pw_uid=uid, pw_gid=gid),
    )
    pid = 4102
    process = tmp_path / "proc" / str(pid)
    (process / "fd").mkdir(parents=True)
    (process / "net").mkdir()
    expected_argv = (
        f"{release.RELEASE_ROOT}/{release_sha}/.venv/bin/python",
        "-m",
        "scripts.runtime.sadhana_control_api",
    )
    (process / "cmdline").write_bytes(
        b"\0".join(item.encode("utf-8") for item in expected_argv) + b"\0"
    )
    (process / "status").write_text(
        f"Uid:\t{uid}\t{uid}\t{uid}\t{uid}\n"
        f"Gid:\t{gid}\t{gid}\t{gid}\t{gid}\n"
        f"Groups:\t{gid}\nNoNewPrivs:\t1\n",
        encoding="ascii",
    )
    (process / "stat").write_text(
        f"{pid} (python) " + " ".join(["S", *(["0"] * 18), "123"]) + "\n",
        encoding="utf-8",
    )
    header = (
        "sl local_address rem_address st tx_queue rx_queue tr tm->when "
        "retrnsmt uid timeout inode\n"
    )
    admitted = "0: 0100007F:47F5 00000000:0000 0A 0:0 00:0 0 0 0 777\n"
    (process / "net/tcp").write_text(header + admitted, encoding="ascii")
    (process / "net/tcp6").write_text(header, encoding="ascii")
    (process / "fd/7").symlink_to("socket:[777]")

    def runner(argv, **_kwargs):  # noqa: ANN001, ANN202
        return subprocess.CompletedProcess(argv, 0, f"{pid}\n", "")

    identity = release._control_listener_identity(
        release_sha=release_sha,
        runner=runner,
        proc_root=tmp_path / "proc",
    )
    assert identity["socket_inode"] == 777
    assert identity["main_pid"] == pid
    assert identity["no_new_privileges"] is True

    foreign = "1: 0100007F:47F5 00000000:0000 0A 0:0 00:0 0 0 0 888\n"
    (process / "net/tcp").write_text(
        header + admitted + foreign,
        encoding="ascii",
    )
    with pytest.raises(release.ReleaseContractError, match="listener ownership"):
        release._control_listener_identity(
            release_sha=release_sha,
            runner=runner,
            proc_root=tmp_path / "proc",
        )


def test_positive_reader_probe_uses_only_the_dashboard_uds_and_public_headers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Bind a short relative UDS name while keeping the directory inside the
    # harness-provided TMPDIR.  This works both in the hostile chroot and when
    # the positive-gate TMPDIR exceeds the platform's AF_UNIX path limit.
    with tempfile.TemporaryDirectory(prefix="sdp-") as raw_root:
        with monkeypatch.context() as local_patch:
            local_patch.chdir(raw_root)
            socket_path = Path("dashboard.sock")
            local_patch.setattr(release, "DASHBOARD_SOCKET_PATH", socket_path)
            _assert_positive_reader_probe(socket_path)


def _assert_positive_reader_probe(socket_path: Path) -> None:
    listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    listener.bind(str(socket_path))
    listener.listen(1)
    observed: list[bytes] = []
    response_body = release._canonical_bytes(
        {
            "status": "unsupported_action",
            "error_code": "proposal_effect_warrant_contract_unavailable",
            "request_accepted": False,
            "decision_applied": False,
            "effect_executed": False,
        }
    )

    def serve_once() -> None:
        connection, _address = listener.accept()
        try:
            raw = bytearray()
            while b"\r\n\r\n" not in raw:
                raw.extend(connection.recv(4096))
            header, body = bytes(raw).split(b"\r\n\r\n", 1)
            length_match = re.search(
                rb"(?im)^Content-Length: ([0-9]+)\r?$", header
            )
            assert length_match is not None
            content_length = int(length_match.group(1))
            while len(body) < content_length:
                body += connection.recv(4096)
            observed.append(header + b"\r\n\r\n" + body)
            connection.sendall(
                b"HTTP/1.1 501 Not Implemented\r\n"
                b"Content-Type: application/json\r\n"
                + f"Content-Length: {len(response_body)}\r\n".encode("ascii")
                + b"Connection: close\r\n\r\n"
                + response_body
            )
        finally:
            connection.close()

    worker = threading.Thread(target=serve_once, daemon=True)
    worker.start()
    try:
        response = release._request_positive_bearer_read_probe(
            socket_path=socket_path,
            origin="https://megh.example.ts.net",
            operator_login="operator@example.com",
            expected_dashboard_pid=os.getpid(),
            expected_dashboard_uid=os.geteuid(),
            expected_dashboard_gid=os.getegid(),
            peer_identity_reader=lambda _socket: (
                os.getpid(),
                os.geteuid(),
                os.getegid(),
            ),
        )
    finally:
        worker.join(timeout=5)
        listener.close()
    assert not worker.is_alive()
    assert response["request_accepted"] is False
    assert len(observed) == 1
    request = observed[0]
    assert request.endswith(b'\r\n\r\n{"action":"approve"}')
    assert b"Authorization:" not in request
    assert b"Tailscale-User-Login: operator@example.com\r\n" in request
    assert b"X-Sadhana-CSRF: sadhana-10-20260823\r\n" in request


@pytest.mark.skipif(
    not sys.platform.startswith("linux") or not hasattr(socket, "SO_PEERCRED"),
    reason="Linux SO_PEERCRED is the production connected-peer gate",
)
def test_positive_reader_probe_rejects_aba_socket_substitution_by_peer_pid(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    socket_path = tmp_path / "constellation.sock"
    saved_path = tmp_path / "constellation.saved"
    monkeypatch.setattr(release, "DASHBOARD_SOCKET_PATH", socket_path)
    admitted = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    admitted.bind(str(socket_path))
    admitted.listen(1)
    admitted_inode = socket_path.lstat().st_ino
    socket_path.rename(saved_path)
    ready_read, ready_write = os.pipe()
    child = os.fork()
    if child == 0:
        os.close(ready_read)
        counterfeit = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        try:
            counterfeit.bind(str(socket_path))
            counterfeit.listen(1)
            os.write(ready_write, b"1")
            connection, _address = counterfeit.accept()
            connection.close()
        finally:
            counterfeit.close()
            os.close(ready_write)
        os._exit(0)
    os.close(ready_write)
    try:
        assert os.read(ready_read, 1) == b"1"
        with pytest.raises(
            release.ReleaseContractError,
            match="connected dashboard peer identity",
        ):
            release._request_positive_bearer_read_probe(
                socket_path=socket_path,
                origin="https://megh.example.ts.net",
                operator_login="operator@example.com",
                expected_dashboard_pid=os.getpid(),
                expected_dashboard_uid=os.geteuid(),
                expected_dashboard_gid=os.getegid(),
            )
    finally:
        os.close(ready_read)
        _pid, status = os.waitpid(child, 0)
        assert os.waitstatus_to_exitcode(status) == 0
        socket_path.unlink(missing_ok=True)
        saved_path.rename(socket_path)
        admitted.close()
    assert socket_path.lstat().st_ino == admitted_inode


@pytest.mark.parametrize(
    "drift", ["credential-copy", "control-identity", "dashboard-identity"]
)
def test_positive_reader_proof_rejects_mid_probe_drift(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    drift: str,
) -> None:
    release_sha = "a" * 40
    secret = b"operator-bearer-fixture-with-enough-entropy"
    credential_root = tmp_path / "credentials"
    credential_root.mkdir(mode=0o700)
    source = credential_root / "operator_bearer"
    hmac_source = credential_root / "control_hmac_key"
    login_source = credential_root / "tailscale_operator_login"
    copy_root = tmp_path / "copies"
    copy_root.mkdir(mode=0o700)
    dashboard_copy = copy_root / "dashboard-copy"
    control_copy = copy_root / "control-copy"
    source.write_bytes(secret)
    source.chmod(0o600)
    hmac_source.write_bytes(b"h" * 32)
    login_source.write_bytes(b"operator@example.com")
    for path in (hmac_source, login_source):
        path.chmod(0o600)
    for path in (dashboard_copy, control_copy):
        path.write_bytes(secret)
        path.chmod(0o400)
    identities = [
        {"main_pid": 4102, "socket_inode": 777, "release_sha": release_sha},
        {"main_pid": 4102, "socket_inode": 778, "release_sha": release_sha},
    ]
    identity_calls = 0
    dashboard_identities = [
        {
            "main_pid": 4101,
            "uid": os.geteuid(),
            "gid": os.getegid(),
            "socket_ino": 900,
            "listener_inode": 901,
        },
        {
            "main_pid": 4101,
            "uid": os.geteuid(),
            "gid": os.getegid(),
            "socket_ino": 902,
            "listener_inode": 903,
        },
    ]
    dashboard_calls = 0

    def control_identity(**_kwargs):  # noqa: ANN202
        nonlocal identity_calls
        selected = identities[min(identity_calls, len(identities) - 1)]
        identity_calls += 1
        return identities[0] if drift == "credential-copy" else selected

    monkeypatch.setattr(release, "_control_listener_identity", control_identity)

    def dashboard_identity(**_kwargs):  # noqa: ANN202
        nonlocal dashboard_calls
        selected = dashboard_identities[
            min(dashboard_calls, len(dashboard_identities) - 1)
        ]
        dashboard_calls += 1
        return dashboard_identities[0] if drift != "dashboard-identity" else selected

    monkeypatch.setattr(release, "_dashboard_listener_identity", dashboard_identity)
    monkeypatch.setattr(
        release,
        "_systemd_main_pid",
        lambda unit, **_kwargs: 4101 if unit == release.DASHBOARD_UNIT else 4102,
    )

    def probe(**_kwargs):  # noqa: ANN202
        if drift == "credential-copy":
            replacement = b"x" * len(secret)
            control_copy.chmod(0o600)
            control_copy.write_bytes(replacement)
            control_copy.chmod(0o400)
        return _positive_bearer_probe_payload()

    with pytest.raises(
        release.ReleaseContractError,
        match="copies differ|readers changed during proof",
    ):
        release._stable_operator_bearer_probe(
            release_sha=release_sha,
            source_path=source,
            dashboard_copy=dashboard_copy,
            control_copy=control_copy,
            runner=lambda *_args, **_kwargs: subprocess.CompletedProcess([], 0, "", ""),
            proc_root=tmp_path / "proc",
            expected_root_uid=os.geteuid(),
            expected_root_gid=os.getegid(),
            positive_read_probe=probe,
        )


def test_disabled_runtime_staging_calls_both_custody_gates_before_receipt(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    release_sha = "a" * 40
    marker = tmp_path / "dispatch-enabled.json"
    monkeypatch.setattr(release, "DISPATCH_ENABLE_MARKER", marker)
    monkeypatch.setattr(release, "guard_campaign_clock", lambda **_kwargs: None)
    monkeypatch.setattr(release, "_systemd_main_pid", lambda *_args, **_kwargs: 0)
    account = SimpleNamespace(pw_name="dharma-sadhana", pw_uid=501, pw_gid=502)
    monkeypatch.setattr(release, "_require_static_service_identity", lambda: account)
    calls: list[str] = []
    parsed = {"supervisor.env": {}, "replication.env": {}}

    def env_gate(_paths):  # noqa: ANN001, ANN202
        calls.append("env")
        return parsed

    monkeypatch.setattr(release, "_ensure_private_env_files", env_gate)
    monkeypatch.setattr(
        release,
        "_ensure_scoped_runtime_files",
        lambda admitted, **_kwargs: calls.append(
            "scoped" if admitted is parsed else "wrong"
        ),
    )
    monkeypatch.setattr(
        release,
        "verify_runtime_binding_activation",
        lambda **_kwargs: {"receipt_digest": "sha256:" + "b" * 64},
    )
    monkeypatch.setattr(
        release, "_read_control_credential", lambda *_args, **_kwargs: b"present"
    )
    receipt = release.finalize_disabled_runtime_staging(
        role="writer",
        release_sha=release_sha,
        receipt_path=tmp_path / "runtime-staging.json",
        env_files=("one", "two"),
        observed_node=release.WRITER_NODE,
        expected_root_uid=os.geteuid(),
        expected_root_gid=os.getegid(),
    )
    assert calls == ["env", "scoped", "env"]
    assert receipt["dispatch_process_count"] == 0
    assert receipt["scoped_runtime_files_verified"] is True

    marker.write_text("must remain immutable\n")
    with pytest.raises(release.ReleaseContractError, match="dispatch authority"):
        release.finalize_disabled_runtime_staging(
            role="writer",
            release_sha=release_sha,
            receipt_path=tmp_path / "should-not-exist.json",
            env_files=("one", "two"),
            observed_node=release.WRITER_NODE,
            expected_root_uid=os.geteuid(),
            expected_root_gid=os.getegid(),
        )
    assert calls == ["env", "scoped", "env"]


def test_scoped_runtime_files_are_fully_admitted_before_first_mutation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    roster = tmp_path / "roster.json"
    key = tmp_path / "replication_ed25519"
    known_hosts = tmp_path / "known_hosts"
    for path in (roster, key, known_hosts):
        path.write_text("fixture\n")
        path.chmod(0o600)
    monkeypatch.setattr(release, "sha256_file", lambda *_args, **_kwargs: "a" * 64)
    validations: list[Path] = []
    mutations: list[Path] = []

    def validate(path: Path, **_kwargs: object) -> None:
        validations.append(path)
        if path == key:
            raise release.ReleaseContractError("injected key custody failure")

    monkeypatch.setattr(release, "_validate_runtime_file_scope", validate)
    monkeypatch.setattr(
        release,
        "_scope_runtime_file",
        lambda path, **_kwargs: mutations.append(path),
    )
    parsed = {
        "supervisor.env": {
            "SADHANA_AGENT_ROSTER_PATH": str(roster),
            "SADHANA_AGENT_ROSTER_SHA256": "a" * 64,
        },
        "replication.env": {"SADHANA_REPLICATION_SSH_KEY": str(key)},
    }
    # The production known-hosts path is pinned; redirect that one constructor
    # through a minimal callable without weakening the path admission sequence.
    real_path = release.Path

    def mapped_path(raw):  # noqa: ANN001, ANN202
        if raw == "/etc/dharma-sadhana/known_hosts":
            return known_hosts
        return real_path(raw)

    monkeypatch.setattr(release, "Path", mapped_path)
    with pytest.raises(release.ReleaseContractError, match="key custody"):
        release._ensure_scoped_runtime_files(
            parsed,
            account=SimpleNamespace(pw_uid=501, pw_gid=502),
        )
    assert validations == [roster, key]
    assert mutations == []


def test_wrong_known_hosts_bytes_are_rejected_before_any_custody_mutation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    roster = tmp_path / "roster.json"
    key = tmp_path / "replication_ed25519"
    known_hosts = tmp_path / "known_hosts"
    roster.write_bytes(b"roster\n")
    key.write_bytes(b"key\n")
    known_hosts.write_bytes(b"wrong authenticated host envelope\n")
    parsed = {
        "supervisor.env": {
            "SADHANA_AGENT_ROSTER_PATH": str(roster),
            "SADHANA_AGENT_ROSTER_SHA256": release.sha256_file(roster),
        },
        "replication.env": {"SADHANA_REPLICATION_SSH_KEY": str(key)},
    }
    real_path = release.Path

    def mapped_path(raw):  # noqa: ANN001, ANN202
        if raw == "/etc/dharma-sadhana/known_hosts":
            return known_hosts
        return real_path(raw)

    monkeypatch.setattr(release, "Path", mapped_path)
    monkeypatch.setattr(
        release,
        "_validate_runtime_file_scope",
        lambda *_args, **_kwargs: None,
    )
    mutations: list[Path] = []
    monkeypatch.setattr(
        release,
        "_scope_runtime_file",
        lambda path, **_kwargs: mutations.append(path),
    )
    with pytest.raises(release.ReleaseContractError, match="pinned deployment"):
        release._ensure_scoped_runtime_files(
            parsed,
            account=SimpleNamespace(pw_uid=501, pw_gid=502),
        )
    assert mutations == []


def test_known_hosts_digest_is_rechecked_after_custody_transition(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    roster = tmp_path / "roster.json"
    key = tmp_path / "replication_ed25519"
    known_hosts = tmp_path / "known_hosts"
    roster.write_bytes(b"roster\n")
    key.write_bytes(b"key\n")
    known_hosts.write_bytes(
        b"178.128.87.170 ssh-ed25519 "
        b"AAAAC3NzaC1lZDI1NTE5AAAAIJ3h+J/3jUWbAvgGZhfHTrU/BtNu+bz1KeVvQCc5Ho4r\n"
        b"157.245.193.15 ssh-ed25519 "
        b"AAAAC3NzaC1lZDI1NTE5AAAAIHkJLL+DPOv8vi4//pbrEqF0HMsqWK/GLjCzErMeWd5A\n"
        b"100.79.111.89 ssh-ed25519 "
        b"AAAAC3NzaC1lZDI1NTE5AAAAIHkJLL+DPOv8vi4//pbrEqF0HMsqWK/GLjCzErMeWd5A\n"
        b"[100.79.111.89]:2222 ssh-ed25519 "
        b"AAAAC3NzaC1lZDI1NTE5AAAAIHkJLL+DPOv8vi4//pbrEqF0HMsqWK/GLjCzErMeWd5A\n"
    )
    assert release.sha256_file(known_hosts) == release.DEPLOYMENT_KNOWN_HOSTS_SHA256
    parsed = {
        "supervisor.env": {
            "SADHANA_AGENT_ROSTER_PATH": str(roster),
            "SADHANA_AGENT_ROSTER_SHA256": release.sha256_file(roster),
        },
        "replication.env": {"SADHANA_REPLICATION_SSH_KEY": str(key)},
    }
    real_path = release.Path

    def mapped_path(raw):  # noqa: ANN001, ANN202
        if raw == "/etc/dharma-sadhana/known_hosts":
            return known_hosts
        return real_path(raw)

    monkeypatch.setattr(release, "Path", mapped_path)
    monkeypatch.setattr(
        release,
        "_validate_runtime_file_scope",
        lambda *_args, **_kwargs: None,
    )
    mutations: list[Path] = []

    def drift_after_scope(path: Path, **_kwargs: object) -> None:
        mutations.append(path)
        if path == known_hosts:
            path.write_bytes(b"drifted after precheck\n")

    monkeypatch.setattr(release, "_scope_runtime_file", drift_after_scope)
    with pytest.raises(release.ReleaseContractError, match="changed during custody"):
        release._ensure_scoped_runtime_files(
            parsed,
            account=SimpleNamespace(pw_uid=501, pw_gid=502),
        )
    assert mutations == [roster, key, known_hosts]


def test_scoped_runtime_file_rejects_path_substitution_before_root_mutation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    candidate = tmp_path / "roster.json"
    displaced = tmp_path / "displaced.json"
    candidate.write_text("first\n")
    candidate.chmod(0o640)
    real_open = os.open
    swapped = False

    def racing_open(path, flags, *args, **kwargs):  # noqa: ANN001, ANN202
        nonlocal swapped
        if Path(path) == candidate and not swapped:
            swapped = True
            candidate.rename(displaced)
            candidate.write_text("replacement\n")
            candidate.chmod(0o640)
        return real_open(path, flags, *args, **kwargs)

    monkeypatch.setattr(release.os, "open", racing_open)
    with pytest.raises(release.ReleaseContractError, match="changed before custody"):
        release._scope_runtime_file(
            candidate,
            uid=os.geteuid(),
            gid=os.getegid(),
            mode=0o640,
        )
    assert swapped is True
    assert displaced.read_text() == "first\n"
    assert candidate.read_text() == "replacement\n"


def test_dispatch_enable_is_distinct_fail_closed_and_has_no_effect(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    release_sha = "a" * 40
    marker = tmp_path / "dispatch-enabled.json"
    monkeypatch.setattr(release, "DISPATCH_ENABLE_MARKER", marker)
    monkeypatch.setattr(release, "guard_campaign_clock", lambda **_kwargs: None)
    monkeypatch.setattr(
        release,
        "_require_live_writer_service_units",
        lambda **_kwargs: None,
    )
    monkeypatch.setattr(
        release,
        "_load_predispatch_activation_for_dispatch",
        lambda **_kwargs: {
            "staged_release_admission_receipt_digest": "sha256:" + "7" * 64
        },
    )
    monkeypatch.setattr(
        release,
        "validate_preactivation_clock_proof",
        lambda **_kwargs: {"receipt_digest": "sha256:" + "8" * 64},
    )
    monkeypatch.setattr(
        release,
        "validate_predispatch_refresh_receipt",
        lambda **_kwargs: {"receipt_digest": "sha256:" + "9" * 64},
    )
    monkeypatch.setattr(
        release,
        "guard_standby_capacity",
        lambda **_kwargs: {"receipt_digest": "sha256:" + "a" * 64},
    )
    monkeypatch.setattr(release, "_fence_runtime_preparation", lambda **_kwargs: None)
    active = False
    monkeypatch.setattr(
        release,
        "_unit_active",
        lambda unit, **_kwargs: active and unit == release.PREDISPATCH_TARGET,
    )
    monkeypatch.setattr(
        release,
        "_unit_inactive",
        lambda unit, **_kwargs: unit == release.RUNTIME_PREPARATION_UNIT,
    )
    monkeypatch.setattr(release, "_unit_static", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(
        release,
        "_systemd_main_pid",
        lambda unit, **_kwargs: {
            release.DASHBOARD_UNIT: 4101,
            "dharma-sadhana-control.service": 4102,
        }.get(unit, 0),
    )
    with pytest.raises(release.ReleaseContractError, match="predispatch"):
        release.enable_dispatch(
            role="writer",
            release_sha=release_sha,
            marker_path=marker,
            now=datetime(2026, 8, 23, 1, tzinfo=timezone.utc),
            observed_node=release.WRITER_NODE,
            expected_root_uid=os.geteuid(),
            expected_root_gid=os.getegid(),
        )
    assert not marker.exists()

    active = True
    identity = {key: 0 for key in release._DASHBOARD_PROCESS_FIELDS}
    identity.update(
        {
            "unit": release.DASHBOARD_UNIT,
            "main_pid": 4101,
            "uid": 501,
            "gid": 502,
            "cmdline_sha256": "b" * 64,
            "socket_path": str(release.DASHBOARD_SOCKET_PATH),
            "release_sha": release_sha,
        }
    )
    systemd_root = tmp_path / "systemd"
    systemd_root.mkdir(mode=0o700)
    for unit in (release.DASHBOARD_UNIT, "dharma-sadhana-control.service"):
        (systemd_root / unit).write_text("fixture\n")
    monkeypatch.setattr(release, "SYSTEMD_OUTPUT_ROOT", systemd_root)
    monkeypatch.setattr(
        release,
        "validate_observer_health_receipt",
        lambda **_kwargs: {"receipt_digest": "sha256:" + "1" * 64},
    )
    operator_login_sha256 = hashlib.sha256(b"operator@example.test").hexdigest()
    account_confirmation = _account_ui_confirmation_fixture(
        release_sha=release_sha,
        operator_login_sha256=operator_login_sha256,
    )
    dashboard = {
        "dashboard_unit_digest": release.sha256_file(systemd_root / release.DASHBOARD_UNIT),
        "dashboard_process_identity": identity,
        "operator_login_sha256": operator_login_sha256,
        "authenticated_account_ui_confirmation": account_confirmation,
        "receipt_digest": "sha256:" + "2" * 64,
    }
    credentials = {
        "credential_copies_equal": True,
        "negative_reader_matrix": {"forbidden": True},
        "secret_sink_scan": {"sink": True},
        "dashboard_unit_digest": dashboard["dashboard_unit_digest"],
        "control_unit_digest": release.sha256_file(
            systemd_root / "dharma-sadhana-control.service"
        ),
        "dashboard_credential_custody": {"service_main_pid": 4101},
        "control_credential_custody": {"service_main_pid": 4102},
        "receipt_digest": "sha256:" + "3" * 64,
    }
    staging = {
        "runtime_binding_receipt_digest": "sha256:" + "5" * 64,
        "receipt_digest": "sha256:" + "4" * 64,
    }
    accepted = {
        release.DASHBOARD_IDENTITY_RECEIPT: dashboard,
        release.OPERATOR_CREDENTIAL_RECEIPT: credentials,
        release.RUNTIME_STAGING_RECEIPT: staging,
    }
    monkeypatch.setattr(
        release,
        "_validate_preactivation_acceptance",
        lambda path, **_kwargs: accepted[path],
    )
    monkeypatch.setattr(
        release, "_dashboard_listener_identity", lambda **_kwargs: identity
    )
    monkeypatch.setattr(
        release,
        "_require_static_service_identity",
        lambda: SimpleNamespace(pw_uid=501, pw_gid=502),
    )
    monkeypatch.setattr(
        release,
        "verify_runtime_binding_activation",
        lambda **_kwargs: {"receipt_digest": "sha256:" + "5" * 64},
    )
    monkeypatch.setattr(
        release,
        "_revalidate_live_tailscale_binding",
        lambda *_args, **_kwargs: {"funnel_absent": True},
    )
    monkeypatch.setattr(
        release,
        "_revalidate_live_operator_credentials",
        lambda *_args, **_kwargs: {
            "dashboard_service_main_pid": 4101,
            "control_service_main_pid": 4102,
            "credential_copies_equal": True,
            "positive_read_proven": True,
            "request_accepted": False,
            "normal_and_emergency_inboxes_unchanged": True,
            "decision_or_effect_state_proven": False,
        },
    )
    monkeypatch.setattr(
        release,
        "_read_exact_custodied_json",
        lambda *_args, **_kwargs: ({}, b"observer-health\n", None),
    )
    monkeypatch.setattr(
        release,
        "_load_oracle_sandbox_evidence",
        lambda _release_sha: (
            {"receipt_digest": "sha256:" + "6" * 64},
            b"oracle-evidence\n",
        ),
    )
    monkeypatch.setattr(
        release,
        "_load_standby_replication_route_probe",
        lambda **_kwargs: {"receipt_digest": "sha256:" + "d" * 64},
    )
    activation_env = b"SADHANA_OBSERVER_HEALTH_RECEIPT_SHA256=fixture\n"
    monkeypatch.setattr(
        release,
        "_publish_supervisor_activation_env",
        lambda **_kwargs: activation_env,
    )
    stale_clock = iter(
        (
            datetime(2026, 8, 23, 1, tzinfo=timezone.utc),
            datetime(2026, 8, 23, 1, 11, tzinfo=timezone.utc),
        )
    )
    with pytest.raises(
        release.ReleaseContractError, match="account UI confirmation is not fresh"
    ):
        release.enable_dispatch(
            role="writer",
            release_sha=release_sha,
            marker_path=marker,
            clock=lambda: next(stale_clock),
            observed_node=release.WRITER_NODE,
            expected_root_uid=os.geteuid(),
            expected_root_gid=os.getegid(),
        )
    assert not marker.exists()
    payload = release.enable_dispatch(
        role="writer",
        release_sha=release_sha,
        marker_path=marker,
        now=datetime(2026, 8, 23, 1, tzinfo=timezone.utc),
        observed_node=release.WRITER_NODE,
        expected_root_uid=os.geteuid(),
        expected_root_gid=os.getegid(),
    )
    assert payload["dispatch_authorized"] is True
    assert payload["effect_executed"] is False
    assert payload["supervisor_main_pid_before_enable"] == 0
    assert payload["predispatch_refresh_receipt_digest"] == "sha256:" + "9" * 64
    assert payload["standby_capacity_receipt_digest"] == "sha256:" + "a" * 64
    assert payload["oracle_sandbox_evidence_digest"] == "sha256:" + "6" * 64
    assert payload["standby_replication_route_probe_receipt_digest"] == (
        "sha256:" + "d" * 64
    )
    assert payload["supervisor_activation_env_sha256"] == hashlib.sha256(
        activation_env
    ).hexdigest()
    assert release._secure_json(marker, require_private=True) == payload
    assert (
        release.enable_dispatch(
            role="writer",
            release_sha=release_sha,
            marker_path=marker,
            now=datetime(2026, 8, 23, 1, tzinfo=timezone.utc),
            observed_node=release.WRITER_NODE,
            expected_root_uid=os.geteuid(),
            expected_root_gid=os.getegid(),
        )
        == payload
    )
    active = False
    with pytest.raises(release.ReleaseContractError, match="predispatch"):
        release.enable_dispatch(
            role="writer",
            release_sha=release_sha,
            marker_path=marker,
            now=datetime(2026, 8, 23, 1, tzinfo=timezone.utc),
            observed_node=release.WRITER_NODE,
            expected_root_uid=os.geteuid(),
            expected_root_gid=os.getegid(),
        )
    assert release._secure_json(marker, require_private=True) == payload
    active = True
    dashboard["receipt_digest"] = "sha256:" + "9" * 64
    with pytest.raises(release.ReleaseContractError, match="marker differs"):
        release.enable_dispatch(
            role="writer",
            release_sha=release_sha,
            marker_path=marker,
            now=datetime(2026, 8, 23, 1, tzinfo=timezone.utc),
            observed_node=release.WRITER_NODE,
            expected_root_uid=os.geteuid(),
            expected_root_gid=os.getegid(),
        )
    assert release._secure_json(marker, require_private=True) == payload


def test_predispatch_activation_is_replayable_and_compensates_failed_start(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    release_sha = "a" * 40
    receipt_path = tmp_path / "predispatch-activation.json"
    writer_marker = tmp_path / "writer-enabled"
    dispatch_marker = tmp_path / "dispatch-enabled.json"
    rollback_receipt = tmp_path / "rollback.json"
    activation_intent = tmp_path / "predispatch-activation-intent.json"
    monkeypatch.setattr(release, "PREDISPATCH_ACTIVATION_RECEIPT", receipt_path)
    monkeypatch.setattr(release, "PREDISPATCH_ACTIVATION_INTENT", activation_intent)
    monkeypatch.setattr(release, "WRITER_MARKER", writer_marker)
    monkeypatch.setattr(release, "DISPATCH_ENABLE_MARKER", dispatch_marker)
    monkeypatch.setattr(release, "ROLLBACK_RECEIPT", rollback_receipt)
    monkeypatch.setattr(release, "guard_campaign_clock", lambda **_kwargs: None)
    monkeypatch.setattr(
        release,
        "validate_preactivation_clock_proof",
        lambda **_kwargs: {"receipt_digest": "sha256:" + "8" * 64},
    )
    account = SimpleNamespace(
        pw_name="dharma-sadhana",
        pw_uid=max(os.geteuid(), 1),
        pw_gid=max(os.getegid(), 1),
    )
    monkeypatch.setattr(release, "_require_static_service_identity", lambda: account)
    monkeypatch.setattr(
        release,
        "_publish_predispatch_account_ui_gate",
        lambda *_args, **_kwargs: {},
    )
    admission = {
        "release_input_set_digest": "1" * 64,
        "receipt_digest": "sha256:" + "2" * 64,
    }
    monkeypatch.setattr(
        release,
        "_staged_release_receipt_paths",
        lambda *_args, **_kwargs: (
            tmp_path,
            tmp_path / "tracked.json",
            tmp_path / "build.json",
            tmp_path / "admission.json",
        ),
    )
    monkeypatch.setattr(
        release,
        "_read_exact_custodied_json",
        lambda *_args, **_kwargs: (admission, b"admission\n", None),
    )
    monkeypatch.setattr(
        release,
        "verify_staged_release_admission",
        lambda **_kwargs: admission,
    )
    monkeypatch.setattr(
        release,
        "publish_runtime_binding_activation",
        lambda **_kwargs: {"receipt_digest": "sha256:" + "3" * 64},
    )
    monkeypatch.setattr(
        release,
        "verify_runtime_binding_activation",
        lambda **_kwargs: {"receipt_digest": "sha256:" + "3" * 64},
    )
    monkeypatch.setattr(
        release,
        "finalize_disabled_runtime_staging",
        lambda **_kwargs: {"receipt_digest": "sha256:" + "4" * 64},
    )
    monkeypatch.setattr(
        release,
        "_validate_preactivation_acceptance",
        lambda *_args, **_kwargs: {
            "runtime_binding_receipt_digest": "sha256:" + "3" * 64,
            "receipt_digest": "sha256:" + "4" * 64,
        },
    )
    monkeypatch.setattr(
        release,
        "refresh_predispatch",
        lambda **_kwargs: {},
    )
    monkeypatch.setattr(
        release,
        "_load_tailscale_intent_receipt",
        lambda *_args, **_kwargs: {"receipt_digest": "sha256:" + "5" * 64},
    )
    monkeypatch.setattr(
        release,
        "_revalidate_owned_tailscale_release",
        lambda **_kwargs: {
            "ownership": {"receipt_digest": "sha256:" + "6" * 64},
            "config_sha256": "7" * 64,
            "funnel_absent": True,
        },
    )
    unit_state = {
        unit: {"active": False, "enabled": False}
        for unit in release.PREDISPATCH_ACTIVATION_UNITS
    }
    calls: list[tuple[str, ...]] = []
    live_unit_gate_checks: list[int] = []

    def admit_live_units(**_kwargs: object) -> None:
        live_unit_gate_checks.append(
            len(
                [
                    command
                    for command in calls
                    if command[1:3] == ("enable", "--now")
                ]
            )
        )

    monkeypatch.setattr(
        release,
        "_require_live_writer_service_units",
        admit_live_units,
    )

    def runner(argv, **_kwargs):  # noqa: ANN001, ANN202
        command = tuple(argv)
        calls.append(command)
        if command[1:3] == ("enable", "--now"):
            unit_state[command[3]] = {"active": True, "enabled": True}
        elif command[1:3] == ("disable", "--now"):
            unit_state[command[3]] = {"active": False, "enabled": False}
        return subprocess.CompletedProcess(argv, 0, "", "")

    monkeypatch.setattr(
        release,
        "_unit_active",
        lambda unit, **_kwargs: unit_state.get(unit, {}).get("active", False),
    )
    monkeypatch.setattr(
        release,
        "_unit_inactive",
        lambda unit, **_kwargs: (
            not unit_state.get(unit, {}).get("active", False)
            if unit in unit_state
            else unit == release.DISPATCH_TARGET
        ),
    )
    monkeypatch.setattr(
        release,
        "_unit_enabled",
        lambda unit, **_kwargs: unit_state[unit]["enabled"],
    )
    monkeypatch.setattr(
        release,
        "_unit_disabled",
        lambda unit, **_kwargs: not unit_state[unit]["enabled"],
    )
    monkeypatch.setattr(release, "_systemd_main_pid", lambda *_args, **_kwargs: 0)
    port_gate_calls: list[bool] = []

    def loopback_port_gate() -> None:
        port_gate_calls.append(receipt_path.exists())
        if receipt_path.exists():
            raise release.ReleaseContractError("live predispatch port is occupied")

    monkeypatch.setattr(release, "_require_loopback_ports_free", loopback_port_gate)
    observed = datetime(2026, 8, 23, 1, tzinfo=timezone.utc)
    proof_checks = 0

    def expiring_clock_proof(**_kwargs: object) -> dict[str, str]:
        nonlocal proof_checks
        proof_checks += 1
        if proof_checks == 2:
            raise release.ReleaseContractError("clock proof is not fresh")
        return {"receipt_digest": "sha256:" + "8" * 64}

    monkeypatch.setattr(
        release,
        "validate_preactivation_clock_proof",
        expiring_clock_proof,
    )
    crossing_clock = iter((observed, observed + timedelta(seconds=121)))
    with pytest.raises(release.ReleaseContractError, match="not fresh"):
        release.activate_predispatch(
            role="writer",
            release_sha=release_sha,
            receipt_path=receipt_path,
            intent_path=activation_intent,
            runner=runner,
            clock=lambda: next(crossing_clock),
            observed_node=release.WRITER_NODE,
            expected_root_uid=os.geteuid(),
            expected_root_gid=os.getegid(),
        )
    assert not activation_intent.exists()
    assert not writer_marker.exists()
    assert not receipt_path.exists()
    assert not [command for command in calls if command[1:3] == ("enable", "--now")]
    calls.clear()
    port_gate_calls.clear()
    monkeypatch.setattr(
        release,
        "validate_preactivation_clock_proof",
        lambda **_kwargs: {"receipt_digest": "sha256:" + "8" * 64},
    )
    payload = release.activate_predispatch(
        role="writer",
        release_sha=release_sha,
        receipt_path=receipt_path,
        intent_path=activation_intent,
        runner=runner,
        now=observed,
        observed_node=release.WRITER_NODE,
        expected_root_uid=os.geteuid(),
        expected_root_gid=os.getegid(),
    )
    assert payload["proof_type"].startswith("PredispatchAuthority<")
    assert payload["effect"] == "InfrastructureEffect"
    assert payload["provider_dispatch"] == "NoProviderDispatch"
    assert payload["campaign_stop_timer_active"] is True
    assert payload["campaign_stop_timer_enabled"] is True
    assert payload["emergency_recovery_path_active"] is True
    assert payload["emergency_recovery_path_enabled"] is True
    assert payload["predispatch_target_active"] is True
    assert payload["predispatch_target_enabled"] is True
    assert writer_marker.read_bytes() == b"writer\n"
    assert [
        command[3]
        for command in calls
        if command[1:3] == ("enable", "--now")
    ] == list(release.PREDISPATCH_ACTIVATION_UNITS)
    enable_calls = calls.count(
        (release.SYSTEMCTL_PATH, "enable", "--now", release.PREDISPATCH_TARGET)
    )
    assert (
        release.activate_predispatch(
            role="writer",
            release_sha=release_sha,
            receipt_path=receipt_path,
            intent_path=activation_intent,
            runner=runner,
            now=observed + timedelta(seconds=1),
            observed_node=release.WRITER_NODE,
            expected_root_uid=os.geteuid(),
            expected_root_gid=os.getegid(),
        )
        == payload
    )
    assert calls.count(
        (release.SYSTEMCTL_PATH, "enable", "--now", release.PREDISPATCH_TARGET)
    ) == enable_calls
    assert port_gate_calls == [False]
    assert live_unit_gate_checks[:3] == [0, 3, 3]

    receipt_path.unlink()
    writer_marker.unlink()
    for unit in unit_state:
        unit_state[unit] = {"active": False, "enabled": False}

    enable_count_before_rejection = len(
        [command for command in calls if command[1:3] == ("enable", "--now")]
    )

    def reject_live_units(**_kwargs: object) -> None:
        raise release.ReleaseContractError("effective systemd unit binding differs")

    monkeypatch.setattr(
        release,
        "_require_live_writer_service_units",
        reject_live_units,
    )
    with pytest.raises(
        release.ReleaseContractError,
        match="effective systemd unit binding differs",
    ):
        release.activate_predispatch(
            role="writer",
            release_sha=release_sha,
            receipt_path=receipt_path,
            intent_path=activation_intent,
            runner=runner,
            now=observed + timedelta(seconds=2),
            observed_node=release.WRITER_NODE,
            expected_root_uid=os.geteuid(),
            expected_root_gid=os.getegid(),
        )
    assert len(
        [command for command in calls if command[1:3] == ("enable", "--now")]
    ) == enable_count_before_rejection
    assert not writer_marker.exists()
    assert not receipt_path.exists()
    monkeypatch.setattr(
        release,
        "_require_live_writer_service_units",
        admit_live_units,
    )

    def failed_runner(argv, **_kwargs):  # noqa: ANN001, ANN202
        command = tuple(argv)
        if command[1:3] == ("enable", "--now"):
            return subprocess.CompletedProcess(argv, 1, "", "failed")
        if command[1:3] == ("disable", "--now"):
            unit_state[command[3]] = {"active": False, "enabled": False}
        return subprocess.CompletedProcess(argv, 0, "", "")

    with pytest.raises(release.ReleaseContractError, match="activation failed"):
        release.activate_predispatch(
            role="writer",
            release_sha=release_sha,
            receipt_path=receipt_path,
            intent_path=activation_intent,
            runner=failed_runner,
            now=observed + timedelta(seconds=3),
            observed_node=release.WRITER_NODE,
            expected_root_uid=os.geteuid(),
            expected_root_gid=os.getegid(),
        )
    assert not writer_marker.exists()
    assert not receipt_path.exists()


@pytest.mark.parametrize("clock_failure", ("stale", "tampered"))
def test_failed_predispatch_intent_replay_only_compensates_to_quiet(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    clock_failure: str,
) -> None:
    os.chmod(tmp_path, 0o700)
    release_sha = "a" * 40
    receipt_path = tmp_path / "predispatch.json"
    intent_path = tmp_path / "predispatch-intent.json"
    writer_marker = tmp_path / "writer-enabled"
    dispatch_marker = tmp_path / "dispatch.json"
    rollback = tmp_path / "rollback.json"
    for name, value in (
        ("PREDISPATCH_ACTIVATION_RECEIPT", receipt_path),
        ("PREDISPATCH_ACTIVATION_INTENT", intent_path),
        ("WRITER_MARKER", writer_marker),
        ("DISPATCH_ENABLE_MARKER", dispatch_marker),
        ("ROLLBACK_RECEIPT", rollback),
    ):
        monkeypatch.setattr(release, name, value)
    state = {
        unit: {"active": False, "enabled": False}
        for unit in release.PREDISPATCH_ACTIVATION_UNITS
    }
    monkeypatch.setattr(
        release,
        "_unit_active",
        lambda unit, **_kwargs: state.get(unit, {}).get("active", False),
    )
    monkeypatch.setattr(
        release,
        "_unit_inactive",
        lambda unit, **_kwargs: (
            not state[unit]["active"]
            if unit in state
            else unit == release.DISPATCH_TARGET
        ),
    )
    monkeypatch.setattr(
        release,
        "_unit_enabled",
        lambda unit, **_kwargs: state[unit]["enabled"],
    )
    monkeypatch.setattr(
        release,
        "_unit_disabled",
        lambda unit, **_kwargs: not state[unit]["enabled"],
    )
    monkeypatch.setattr(release, "_systemd_main_pid", lambda *_args, **_kwargs: 0)
    observed = datetime(2026, 8, 23, 1, tzinfo=timezone.utc)
    intent, created = release._predispatch_activation_intent(
        release_sha=release_sha,
        preactivation_clock_proof_receipt_digest="sha256:" + "8" * 64,
        path=intent_path,
        runner=lambda *_args, **_kwargs: subprocess.CompletedProcess([], 0, "", ""),
        observed=observed,
        expected_root_uid=os.geteuid(),
        expected_root_gid=os.getegid(),
    )
    assert created is True
    assert intent["effect_intent"] == "InfrastructureEffect"
    for unit in state:
        state[unit] = {"active": True, "enabled": True}
    writer_marker.write_bytes(b"writer\n")
    writer_marker.chmod(0o600)
    calls: list[tuple[str, ...]] = []

    def runner(argv, **_kwargs):  # noqa: ANN001, ANN202
        command = tuple(argv)
        calls.append(command)
        if command[1:3] == ("disable", "--now"):
            state[command[3]] = {"active": False, "enabled": False}
        return subprocess.CompletedProcess(argv, 0, "", "")

    monkeypatch.setattr(release, "guard_campaign_clock", lambda **_kwargs: None)
    monkeypatch.setattr(
        release,
        "_verify_activation_staged_release",
        lambda **_kwargs: (
            {"receipt_digest": "sha256:" + "7" * 64},
            SimpleNamespace(),
        ),
    )
    monkeypatch.setattr(
        release,
        "validate_preactivation_clock_proof",
        lambda **_kwargs: (_ for _ in ()).throw(
            release.ReleaseContractError(
                "clock proof is not fresh"
                if clock_failure == "stale"
                else "clock-proof exact bindings differ"
            )
        ),
    )
    later_effects: list[str] = []
    monkeypatch.setattr(
        release,
        "publish_runtime_binding_activation",
        lambda **_kwargs: later_effects.append("runtime-binding"),
    )
    monkeypatch.setattr(
        release,
        "finalize_disabled_runtime_staging",
        lambda **_kwargs: later_effects.append("runtime-staging"),
    )
    with pytest.raises(
        release.ReleaseContractError,
        match="not fresh|exact bindings",
    ):
        release.activate_predispatch(
            role="writer",
            release_sha=release_sha,
            receipt_path=receipt_path,
            intent_path=intent_path,
            runner=runner,
            now=observed + timedelta(seconds=121),
            observed_node=release.WRITER_NODE,
            expected_root_uid=os.geteuid(),
            expected_root_gid=os.getegid(),
        )
    assert calls == [
        (release.SYSTEMCTL_PATH, "disable", "--now", unit)
        for unit in reversed(release.PREDISPATCH_ACTIVATION_UNITS)
    ]
    assert all(not item["active"] and not item["enabled"] for item in state.values())
    assert later_effects == []
    assert intent_path.exists()
    assert not receipt_path.exists()
    assert not writer_marker.exists()


def test_standby_activation_is_receipted_replayable_and_live_fenced(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    os.chmod(tmp_path, 0o700)
    release_sha = "a" * 40
    receipt_path = tmp_path / "standby.json"
    intent_path = tmp_path / "standby-intent.json"
    writer_marker = tmp_path / "writer-enabled"
    monkeypatch.setattr(release, "STANDBY_ACTIVATION_RECEIPT", receipt_path)
    monkeypatch.setattr(release, "STANDBY_ACTIVATION_INTENT", intent_path)
    monkeypatch.setattr(release, "WRITER_MARKER", writer_marker)
    state, calls, runner = _standby_activation_harness(monkeypatch)

    monkeypatch.setattr(release, "guard_campaign_clock", lambda **_kwargs: None)
    monkeypatch.setattr(
        release,
        "_verify_activation_staged_release",
        lambda **_kwargs: (
            {"receipt_digest": "sha256:" + "7" * 64},
            SimpleNamespace(),
        ),
    )
    monkeypatch.setattr(
        release,
        "validate_preactivation_clock_proof",
        lambda **_kwargs: {"receipt_digest": "sha256:" + "8" * 64},
    )
    observed = datetime(2026, 8, 23, 1, tzinfo=timezone.utc)
    proof_checks = 0

    def expiring_clock_proof(**_kwargs: object) -> dict[str, str]:
        nonlocal proof_checks
        proof_checks += 1
        if proof_checks == 2:
            raise release.ReleaseContractError("clock proof is not fresh")
        return {"receipt_digest": "sha256:" + "8" * 64}

    monkeypatch.setattr(
        release,
        "validate_preactivation_clock_proof",
        expiring_clock_proof,
    )
    crossing_clock = iter((observed, observed + timedelta(seconds=121)))
    with pytest.raises(release.ReleaseContractError, match="not fresh"):
        release.activate_standby(
            role="standby",
            release_sha=release_sha,
            receipt_path=receipt_path,
            intent_path=intent_path,
            runner=runner,
            clock=lambda: next(crossing_clock),
            observed_node=release.STANDBY_NODE,
            expected_root_uid=os.geteuid(),
            expected_root_gid=os.getegid(),
        )
    assert calls == []
    assert state == {
        "target_active": False,
        "target_enabled": False,
        "timer_active": False,
        "timer_enabled": False,
        "campaign_masked": False,
        "serve_active": False,
    }
    assert intent_path.exists()
    assert not receipt_path.exists()
    monkeypatch.setattr(
        release,
        "validate_preactivation_clock_proof",
        lambda **_kwargs: {"receipt_digest": "sha256:" + "8" * 64},
    )
    payload = release.activate_standby(
        role="standby",
        release_sha=release_sha,
        receipt_path=receipt_path,
        intent_path=intent_path,
        runner=runner,
        now=observed,
        observed_node=release.STANDBY_NODE,
        expected_root_uid=os.geteuid(),
        expected_root_gid=os.getegid(),
    )
    enable = (
        release.SYSTEMCTL_PATH,
        "enable",
        "--now",
        release.STANDBY_STOP_TIMER,
        release.STANDBY_TARGET,
    )
    assert calls == [
        (release.SYSTEMCTL_PATH, "daemon-reload"),
        (release.SYSTEMCTL_PATH, "mask", "--now", *release.CAMPAIGN_UNITS),
        enable,
    ]
    assert release.CAMPAIGN_STOP_TIMER not in enable[3:]
    assert payload["standby_stop_timer_active"] is True
    assert payload["standby_target_active"] is True
    assert payload["campaign_units_masked_and_inactive"] is True
    effect_count = len(calls)
    assert (
        release.activate_standby(
            role="standby",
            release_sha=release_sha,
            receipt_path=receipt_path,
            intent_path=intent_path,
            runner=runner,
            now=observed + timedelta(seconds=1),
            observed_node=release.STANDBY_NODE,
            expected_root_uid=os.geteuid(),
            expected_root_gid=os.getegid(),
        )
        == payload
    )
    assert len(calls) == effect_count
    state["target_active"] = False
    with pytest.raises(release.ReleaseContractError, match="live fence"):
        release.activate_standby(
            role="standby",
            release_sha=release_sha,
            receipt_path=receipt_path,
            intent_path=intent_path,
            runner=runner,
            now=observed + timedelta(seconds=2),
            observed_node=release.STANDBY_NODE,
            expected_root_uid=os.geteuid(),
            expected_root_gid=os.getegid(),
        )
    assert len(calls) == effect_count


@pytest.mark.parametrize("replay", (False, True))
def test_standby_activation_and_replay_require_exact_forced_replication_route(
    replay: bool,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    os.chmod(tmp_path, 0o700)
    release_sha = "a" * 40
    receipt_path = tmp_path / "standby.json"
    intent_path = tmp_path / "standby-intent.json"
    writer_marker = tmp_path / "writer-enabled"
    monkeypatch.setattr(release, "STANDBY_ACTIVATION_RECEIPT", receipt_path)
    monkeypatch.setattr(release, "STANDBY_ACTIVATION_INTENT", intent_path)
    monkeypatch.setattr(release, "WRITER_MARKER", writer_marker)
    _state, calls, runner = _standby_activation_harness(monkeypatch)
    monkeypatch.setattr(release, "guard_campaign_clock", lambda **_kwargs: None)
    monkeypatch.setattr(
        release,
        "_verify_activation_staged_release",
        lambda **_kwargs: (
            {"receipt_digest": "sha256:" + "7" * 64},
            SimpleNamespace(),
        ),
    )
    monkeypatch.setattr(
        release,
        "validate_preactivation_clock_proof",
        lambda **_kwargs: {"receipt_digest": "sha256:" + "8" * 64},
    )
    route_checks: list[bool] = []

    def reject_drift(**_kwargs: object) -> None:
        route_checks.append(True)
        raise release.ReleaseContractError("standby forced replication route is absent")

    monkeypatch.setattr(
        release,
        "_validate_installed_standby_replication_route",
        reject_drift,
    )
    if replay:
        receipt_path.write_bytes(b"{}\n")
        receipt_path.chmod(0o600)
    with pytest.raises(release.ReleaseContractError, match="route is absent"):
        release.activate_standby(
            role="standby",
            release_sha=release_sha,
            receipt_path=receipt_path,
            intent_path=intent_path,
            runner=runner,
            now=datetime(2026, 8, 23, 1, tzinfo=timezone.utc),
            observed_node=release.STANDBY_NODE,
            expected_root_uid=os.geteuid(),
            expected_root_gid=os.getegid(),
        )
    assert route_checks == [True]
    assert calls == []
    assert not intent_path.exists()


@pytest.mark.parametrize("clock_failure", ("stale", "tampered"))
def test_failed_standby_intent_replay_only_compensates_to_quiet(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    clock_failure: str,
) -> None:
    os.chmod(tmp_path, 0o700)
    release_sha = "a" * 40
    receipt_path = tmp_path / "standby.json"
    intent_path = tmp_path / "standby-intent.json"
    writer_marker = tmp_path / "writer-enabled"
    monkeypatch.setattr(release, "STANDBY_ACTIVATION_RECEIPT", receipt_path)
    monkeypatch.setattr(release, "STANDBY_ACTIVATION_INTENT", intent_path)
    monkeypatch.setattr(release, "WRITER_MARKER", writer_marker)
    state, calls, runner = _standby_activation_harness(monkeypatch)
    observed = datetime(2026, 8, 23, 1, tzinfo=timezone.utc)
    intent, created = release._standby_activation_intent(
        release_sha=release_sha,
        staged_release_admission_receipt_digest="sha256:" + "7" * 64,
        preactivation_clock_proof_receipt_digest="sha256:" + "8" * 64,
        path=intent_path,
        runner=lambda *_args, **_kwargs: subprocess.CompletedProcess([], 0, "", ""),
        observed=observed,
        expected_root_uid=os.geteuid(),
        expected_root_gid=os.getegid(),
    )
    assert created is True
    assert intent["writer_authority_transferred"] is False
    state.update(
        target_active=True,
        target_enabled=True,
        timer_active=True,
        timer_enabled=True,
        campaign_masked=True,
        serve_active=True,
    )

    monkeypatch.setattr(release, "guard_campaign_clock", lambda **_kwargs: None)
    monkeypatch.setattr(
        release,
        "_verify_activation_staged_release",
        lambda **_kwargs: (
            {"receipt_digest": "sha256:" + "7" * 64},
            SimpleNamespace(),
        ),
    )
    monkeypatch.setattr(
        release,
        "validate_preactivation_clock_proof",
        lambda **_kwargs: (_ for _ in ()).throw(
            release.ReleaseContractError(
                "clock proof is not fresh"
                if clock_failure == "stale"
                else "clock-proof exact bindings differ"
            )
        ),
    )
    with pytest.raises(
        release.ReleaseContractError,
        match="not fresh|exact bindings",
    ):
        release.activate_standby(
            role="standby",
            release_sha=release_sha,
            receipt_path=receipt_path,
            intent_path=intent_path,
            runner=runner,
            now=observed + timedelta(seconds=121),
            observed_node=release.STANDBY_NODE,
            expected_root_uid=os.geteuid(),
            expected_root_gid=os.getegid(),
        )
    assert calls == [
        (release.SYSTEMCTL_PATH, "disable", "--now", release.STANDBY_TARGET),
        (release.SYSTEMCTL_PATH, "disable", "--now", release.STANDBY_STOP_TIMER),
        (release.SYSTEMCTL_PATH, "mask", "--now", *release.CAMPAIGN_UNITS),
    ]
    assert state == {
        "target_active": False,
        "target_enabled": False,
        "timer_active": False,
        "timer_enabled": False,
        "campaign_masked": True,
        "serve_active": False,
    }
    assert intent_path.exists()
    assert not receipt_path.exists()
    assert not writer_marker.exists()


def test_predispatch_intent_rejects_preexisting_enabled_lifecycle_unit(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    enabled = release.CAMPAIGN_STOP_TIMER
    monkeypatch.setattr(
        release,
        "_unit_active",
        lambda _unit, **_kwargs: False,
    )
    monkeypatch.setattr(
        release,
        "_unit_inactive",
        lambda _unit, **_kwargs: True,
    )
    monkeypatch.setattr(
        release,
        "_unit_enabled",
        lambda unit, **_kwargs: unit == enabled,
    )
    monkeypatch.setattr(
        release,
        "_unit_disabled",
        lambda unit, **_kwargs: unit != enabled,
    )
    monkeypatch.setattr(release, "_systemd_main_pid", lambda *_args, **_kwargs: 0)
    intent_path = tmp_path / "predispatch-intent.json"
    with pytest.raises(release.ReleaseContractError, match="active or enabled"):
        release._predispatch_activation_intent(
            release_sha="a" * 40,
            preactivation_clock_proof_receipt_digest="sha256:" + "8" * 64,
            path=intent_path,
            runner=lambda *_args, **_kwargs: subprocess.CompletedProcess(
                [], 0, "", ""
            ),
            observed=datetime(2026, 8, 23, 1, tzinfo=timezone.utc),
            expected_root_uid=os.geteuid(),
            expected_root_gid=os.getegid(),
        )
    assert not intent_path.exists()


@pytest.mark.parametrize("failure", ["changed-pid", "serve-funnel", "source-copy"])
def test_shared_live_dispatch_gate_leaves_no_marker_on_drift(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    failure: str,
) -> None:
    release_sha = "a" * 40
    marker = tmp_path / f"dispatch-{failure}.json"
    monkeypatch.setattr(release, "DISPATCH_ENABLE_MARKER", marker)
    monkeypatch.setattr(release, "guard_campaign_clock", lambda **_kwargs: None)
    monkeypatch.setattr(
        release,
        "_load_predispatch_activation_for_dispatch",
        lambda **_kwargs: {
            "staged_release_admission_receipt_digest": "sha256:" + "7" * 64
        },
    )
    monkeypatch.setattr(
        release,
        "validate_preactivation_clock_proof",
        lambda **_kwargs: {"receipt_digest": "sha256:" + "8" * 64},
    )
    monkeypatch.setattr(release, "_unit_active", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(release, "_systemd_main_pid", lambda *_args, **_kwargs: 0)
    monkeypatch.setattr(
        release,
        "validate_observer_health_receipt",
        lambda **_kwargs: {"receipt_digest": "sha256:" + "1" * 64},
    )
    systemd_root = tmp_path / "systemd"
    systemd_root.mkdir(mode=0o700)
    dashboard_unit = systemd_root / release.DASHBOARD_UNIT
    dashboard_unit.write_text("fixture\n")
    monkeypatch.setattr(release, "SYSTEMD_OUTPUT_ROOT", systemd_root)
    admitted_identity = {
        "unit": release.DASHBOARD_UNIT,
        "main_pid": 4101,
        "release_sha": release_sha,
    }
    current_identity = dict(admitted_identity)
    if failure == "changed-pid":
        current_identity["main_pid"] = 4201
    dashboard = {
        "dashboard_unit_digest": release.sha256_file(dashboard_unit),
        "dashboard_process_identity": admitted_identity,
        "receipt_digest": "sha256:" + "2" * 64,
    }
    credentials = {"receipt_digest": "sha256:" + "3" * 64}
    staging = {
        "runtime_binding_receipt_digest": "sha256:" + "5" * 64,
        "receipt_digest": "sha256:" + "4" * 64,
    }
    accepted = {
        release.DASHBOARD_IDENTITY_RECEIPT: dashboard,
        release.OPERATOR_CREDENTIAL_RECEIPT: credentials,
        release.RUNTIME_STAGING_RECEIPT: staging,
    }
    monkeypatch.setattr(
        release,
        "_validate_preactivation_acceptance",
        lambda path, **_kwargs: accepted[path],
    )
    monkeypatch.setattr(
        release,
        "_dashboard_listener_identity",
        lambda **_kwargs: current_identity,
    )

    def tailscale_gate(*_args, **_kwargs):  # noqa: ANN202
        if failure == "serve-funnel":
            raise release.ReleaseContractError("live Serve/Funnel drift")
        return {"funnel_absent": True}

    def credential_gate(*_args, **_kwargs):  # noqa: ANN202
        if failure == "source-copy":
            raise release.ReleaseContractError("live credential copies differ")
        return {"credential_copies_equal": True, "positive_read_proven": True}

    monkeypatch.setattr(release, "_revalidate_live_tailscale_binding", tailscale_gate)
    monkeypatch.setattr(
        release,
        "_revalidate_live_operator_credentials",
        credential_gate,
    )
    monkeypatch.setattr(
        release,
        "_require_static_service_identity",
        lambda: SimpleNamespace(pw_uid=501, pw_gid=502),
    )
    monkeypatch.setattr(
        release,
        "verify_runtime_binding_activation",
        lambda **_kwargs: {"receipt_digest": "sha256:" + "5" * 64},
    )
    with pytest.raises(release.ReleaseContractError):
        release.enable_dispatch(
            role="writer",
            release_sha=release_sha,
            marker_path=marker,
            now=datetime(2026, 8, 23, 1, tzinfo=timezone.utc),
            observed_node=release.WRITER_NODE,
            expected_root_uid=os.geteuid(),
            expected_root_gid=os.getegid(),
            positive_read_probe=lambda **_kwargs: _positive_bearer_probe_payload(),
        )
    assert not marker.exists()


def test_live_tailscale_revalidation_rejects_funnel_and_proxy_drift(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    host_port = f"{release.WRITER_NODE}.fixture.ts.net:443"
    owned = {
        "TCP": {"443": {"HTTPS": True}},
        "Web": {host_port: {"Handlers": {"/": {"Proxy": release.TAILSCALE_ROUTE}}}},
    }
    before_digest = release._tailscale_config_digest({})
    owned_digest = release._tailscale_config_digest(owned)
    dashboard = {
        "release_sha": "a" * 40,
        "tailscale_version": release.TAILSCALE_VERSION,
        "serve_status_before_sha256": before_digest,
        "serve_status_after_sha256": owned_digest,
        "serve_upstream": release.TAILSCALE_ROUTE,
        "funnel_absence": True,
    }
    current = owned
    monkeypatch.setattr(release, "_require_tailscale_version", lambda **_kwargs: None)
    monkeypatch.setattr(
        release,
        "_read_tailscale_config",
        lambda **_kwargs: release.TAILSCALE_EMPTY_CONFIG,
    )
    monkeypatch.setattr(release, "_read_tailscale_status", lambda **_kwargs: current)
    monkeypatch.setattr(
        release,
        "_load_tailscale_ownership_receipt",
        lambda _path, **_kwargs: {
            "config": owned,
            "config_sha256": owned_digest,
            "serve_status_before_sha256": before_digest,
        },
    )
    assert release._revalidate_live_tailscale_binding(
        dashboard,
        runner=lambda *_args, **_kwargs: subprocess.CompletedProcess([], 0, "", ""),
    )["funnel_absent"] is True

    current = {**owned, "AllowFunnel": {host_port: True}}
    with pytest.raises(release.ReleaseContractError, match="campaign-exclusive"):
        release._revalidate_live_tailscale_binding(
            dashboard,
            runner=lambda *_args, **_kwargs: subprocess.CompletedProcess([], 0, "", ""),
        )
    current = {
        "TCP": owned["TCP"],
        "Web": {host_port: {"Handlers": {"/": {"Proxy": "http://127.0.0.1:3000"}}}},
    }
    with pytest.raises(release.ReleaseContractError, match="pinned proxy"):
        release._revalidate_live_tailscale_binding(
            dashboard,
            runner=lambda *_args, **_kwargs: subprocess.CompletedProcess([], 0, "", ""),
        )


def test_executable_rollback_is_immutable_and_retains_evidence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    receipt_path = tmp_path / "rollback.json"
    monkeypatch.setattr(release, "ROLLBACK_RECEIPT", receipt_path)
    monkeypatch.setattr(release, "_unit_inactive", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(release, "_unit_disabled", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(release, "_unit_static", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(
        release, "_campaign_listeners_absent", lambda *_args, **_kwargs: True
    )
    monkeypatch.setattr(release, "_require_empty_tailscale_serve", lambda **_kwargs: None)
    monkeypatch.setattr(
        release,
        "TAILSCALE_OWNERSHIP_RECEIPT",
        tmp_path / "absent-tailscale-ownership.json",
    )
    release_sha = "a" * 40
    release_root = tmp_path / "releases"
    (release_root / release_sha).mkdir(parents=True, mode=0o700)
    snapshot_root = tmp_path / "snapshots"
    snapshot_root.mkdir(mode=0o700)
    writer_marker = tmp_path / "writer-enabled"
    writer_marker.write_bytes(b"writer\n")
    writer_marker.chmod(0o600)
    monkeypatch.setattr(release, "RELEASE_ROOT", str(release_root))
    monkeypatch.setattr(release, "SNAPSHOT_ROOT", str(snapshot_root))
    monkeypatch.setattr(release, "WRITER_MARKER", writer_marker)
    monkeypatch.setattr(
        release,
        "_remove_exact_writer_marker",
        lambda **_kwargs: writer_marker.unlink(),
    )
    calls: list[tuple[str, ...]] = []

    def runner(argv, **_kwargs):  # noqa: ANN001, ANN202
        calls.append(tuple(argv))
        return subprocess.CompletedProcess(argv, 0, "", "")

    payload = release.execute_release_rollback(
        role="writer",
        release_sha=release_sha,
        receipt_path=receipt_path,
        runner=runner,
        now=datetime(2026, 8, 23, 1, tzinfo=timezone.utc),
        observed_node=release.WRITER_NODE,
        expected_root_uid=os.geteuid(),
        expected_root_gid=os.getegid(),
    )
    assert calls == [
        (release.SYSTEMCTL_PATH, "stop", release.DISPATCH_TARGET),
        (release.SYSTEMCTL_PATH, "disable", "--now", release.PREDISPATCH_TARGET),
        (release.SYSTEMCTL_PATH, "disable", "--now", release.EMERGENCY_RECOVERY_PATH),
        (release.SYSTEMCTL_PATH, "disable", "--now", release.CAMPAIGN_STOP_TIMER),
        (release.SYSTEMCTL_PATH, "stop", release.RUNTIME_PREPARATION_UNIT),
    ]
    assert payload["release_tree_retained"] is True
    assert payload["snapshots_retained"] is True
    assert payload["writer_marker_removed"] is True
    assert not writer_marker.exists()
    assert payload["authority_transferred"] is False
    first_calls = tuple(calls)
    assert (
        release.execute_release_rollback(
            role="writer",
            release_sha=release_sha,
            receipt_path=receipt_path,
            runner=runner,
            observed_node=release.WRITER_NODE,
            expected_root_uid=os.geteuid(),
            expected_root_gid=os.getegid(),
        )
        == payload
    )
    assert tuple(calls) == first_calls
    monkeypatch.setattr(
        release,
        "_unit_inactive",
        lambda unit, **_kwargs: unit != release.PREDISPATCH_TARGET,
    )
    with pytest.raises(release.ReleaseContractError, match="live quiet"):
        release.execute_release_rollback(
            role="writer",
            release_sha=release_sha,
            receipt_path=receipt_path,
            runner=runner,
            observed_node=release.WRITER_NODE,
            expected_root_uid=os.geteuid(),
            expected_root_gid=os.getegid(),
        )
    monkeypatch.setattr(
        release,
        "_unit_inactive",
        lambda unit, **_kwargs: unit != release.RUNTIME_PREPARATION_UNIT,
    )
    with pytest.raises(release.ReleaseContractError, match="live quiet"):
        release.execute_release_rollback(
            role="writer",
            release_sha=release_sha,
            receipt_path=receipt_path,
            runner=runner,
            observed_node=release.WRITER_NODE,
            expected_root_uid=os.geteuid(),
            expected_root_gid=os.getegid(),
        )
    monkeypatch.setattr(release, "_unit_inactive", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(
        release, "_unit_static", lambda *_args, **_kwargs: False
    )
    with pytest.raises(release.ReleaseContractError, match="live quiet"):
        release.execute_release_rollback(
            role="writer",
            release_sha=release_sha,
            receipt_path=receipt_path,
            runner=runner,
            observed_node=release.WRITER_NODE,
            expected_root_uid=os.geteuid(),
            expected_root_gid=os.getegid(),
        )
    with pytest.raises(release.ReleaseContractError, match="rollback receipt"):
        release.guard_campaign_clock(
            role="writer",
            now=datetime(2026, 8, 23, 1, tzinfo=timezone.utc),
            observed_node=release.WRITER_NODE,
        )


def test_rollback_requires_runner_observed_static_dispatch_on_initial_and_replay(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    os.chmod(tmp_path, 0o700)
    release_sha = "a" * 40
    receipt_path = tmp_path / "rollback.json"
    release_root = tmp_path / "releases"
    snapshot_root = tmp_path / "snapshots"
    (release_root / release_sha).mkdir(parents=True, mode=0o700)
    snapshot_root.mkdir(mode=0o700)
    monkeypatch.setattr(release, "ROLLBACK_RECEIPT", receipt_path)
    monkeypatch.setattr(release, "RELEASE_ROOT", str(release_root))
    monkeypatch.setattr(release, "SNAPSHOT_ROOT", str(snapshot_root))
    monkeypatch.setattr(release, "WRITER_MARKER", tmp_path / "writer-enabled")
    monkeypatch.setattr(
        release,
        "TAILSCALE_OWNERSHIP_RECEIPT",
        tmp_path / "tailscale-ownership-absent.json",
    )
    monkeypatch.setattr(
        release, "_campaign_listeners_absent", lambda *_args, **_kwargs: True
    )
    monkeypatch.setattr(release, "_require_empty_tailscale_serve", lambda **_kwargs: None)
    dispatch_state = {"value": "static"}
    effects: list[tuple[str, ...]] = []
    successful_states = {"static", "enabled", "indirect", "alias", "generated"}

    def runner(argv, **_kwargs):  # noqa: ANN001, ANN202
        command = tuple(argv)
        if command[1] in {"disable", "stop"}:
            effects.append(command)
            return subprocess.CompletedProcess(argv, 0, "", "")
        if command[1] == "show":
            return subprocess.CompletedProcess(
                argv,
                0,
                "LoadState=loaded\nActiveState=inactive\nMainPID=0\n",
                "",
            )
        if command[1] == "is-enabled":
            state = (
                dispatch_state["value"]
                if command[2] == release.DISPATCH_TARGET
                else "disabled"
            )
            return subprocess.CompletedProcess(
                argv,
                0 if state in successful_states else 1,
                f"{state}\n",
                "" if state != "not-found" else "unit not found\n",
            )
        raise AssertionError(f"unexpected rollback command: {command!r}")

    observed = datetime(2026, 8, 23, 1, tzinfo=timezone.utc)
    payload = release.execute_release_rollback(
        role="writer",
        release_sha=release_sha,
        receipt_path=receipt_path,
        runner=runner,
        now=observed,
        observed_node=release.WRITER_NODE,
        expected_root_uid=os.geteuid(),
        expected_root_gid=os.getegid(),
    )
    assert payload["dispatch_target_static_and_inactive"] is True
    effect_count = len(effects)
    assert (
        release.execute_release_rollback(
            role="writer",
            release_sha=release_sha,
            receipt_path=receipt_path,
            runner=runner,
            now=observed,
            observed_node=release.WRITER_NODE,
            expected_root_uid=os.geteuid(),
            expected_root_gid=os.getegid(),
        )
        == payload
    )
    assert len(effects) == effect_count
    receipt_raw = receipt_path.read_bytes()

    rejected_states = (
        "enabled",
        "disabled",
        "indirect",
        "alias",
        "generated",
        "masked",
        "not-found",
    )
    for state in rejected_states:
        receipt_path.unlink()
        dispatch_state["value"] = state
        before_initial = len(effects)
        with pytest.raises(release.ReleaseContractError, match="live quiet"):
            release.execute_release_rollback(
                role="writer",
                release_sha=release_sha,
                receipt_path=receipt_path,
                runner=runner,
                now=observed,
                observed_node=release.WRITER_NODE,
                expected_root_uid=os.geteuid(),
                expected_root_gid=os.getegid(),
            )
        assert len(effects) == before_initial + 5
        assert not receipt_path.exists()

        receipt_path.write_bytes(receipt_raw)
        receipt_path.chmod(0o600)
        before_replay = len(effects)
        with pytest.raises(release.ReleaseContractError, match="live quiet"):
            release.execute_release_rollback(
                role="writer",
                release_sha=release_sha,
                receipt_path=receipt_path,
                runner=runner,
                now=observed,
                observed_node=release.WRITER_NODE,
                expected_root_uid=os.geteuid(),
                expected_root_gid=os.getegid(),
            )
        assert len(effects) == before_replay


def test_standby_deadline_receipt_keeps_receiver_quiet_without_failover(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    marker = tmp_path / "standby-stopped.json"
    monkeypatch.setattr(release, "STANDBY_STOP_MARKER", marker)
    stopped = datetime(2026, 9, 1, 17, 15, 12, tzinfo=timezone.utc)
    monkeypatch.setattr(release, "guard_campaign_stop", lambda **_kwargs: stopped)
    monkeypatch.setattr(release, "_unit_inactive", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(release, "_unit_active", lambda *_args, **_kwargs: False)
    monkeypatch.setattr(
        release,
        "standby_tailscale_stop",
        lambda **_kwargs: {"receipt_digest": "sha256:" + "c" * 64},
    )
    monkeypatch.setattr(
        release,
        "_require_standby_tailscale_route_absent",
        lambda **_kwargs: None,
    )
    payload = release.persist_standby_deadline_stop(
        role="standby",
        release_sha="a" * 40,
        receipt_path=marker,
        observed_node=release.STANDBY_NODE,
        expected_root_uid=os.geteuid(),
        expected_root_gid=os.getegid(),
    )
    assert payload["standby_target_disabled"] is True
    assert payload["receiver_path_inactive"] is True
    assert payload["receiver_timer_inactive"] is True
    assert payload["receiver_service_inactive"] is True
    assert payload["replication_serve_unit_inactive"] is True
    assert payload["replication_route_absent"] is True
    assert payload["replication_serve_stop_receipt_digest"] == (
        "sha256:" + "c" * 64
    )
    assert payload["writer_authority_transferred"] is False
    assert release._secure_json(marker, require_private=True) == payload


def test_dashboard_ingress_is_exact_uds_identity_with_no_tcp_listener(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    release_sha = "a" * 40
    uid = os.geteuid()
    gid = os.getegid()
    account = SimpleNamespace(pw_uid=uid, pw_gid=gid)
    monkeypatch.setattr(release, "_require_dashboard_identity", lambda: account)
    with tempfile.TemporaryDirectory(prefix="sdu-", dir="/tmp") as raw_root:
        outer = Path(raw_root) / "r"
        directory = outer / "d"
        socket_path = directory / "c.sock"
        outer.mkdir(mode=0o711)
        directory.mkdir(mode=0o700)
        os.chown(outer, uid, gid)
        os.chown(directory, uid, gid)
        monkeypatch.setattr(release, "RUNTIME_ROOT", outer)
        monkeypatch.setattr(release, "DASHBOARD_SOCKET_DIRECTORY", directory)
        monkeypatch.setattr(release, "DASHBOARD_SOCKET_PATH", socket_path)

        listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        listener.bind(str(socket_path))
        listener.listen(1)
        socket_path.chmod(0o600)
        try:
            pid = 5151
            process = Path(raw_root) / "proc" / str(pid)
            (process / "fd").mkdir(parents=True)
            (process / "net").mkdir()
            expected_argv = (
                "/usr/bin/node",
                f"{release.RELEASE_ROOT}/{release_sha}/deploy/sadhana/"
                "sadhana-dashboard-server.mjs",
            )
            (process / "cmdline").write_bytes(
                b"\0".join(value.encode() for value in expected_argv) + b"\0"
            )
            (process / "status").write_text(
                f"Uid:\t{uid}\t{uid}\t{uid}\t{uid}\n"
                f"Gid:\t{gid}\t{gid}\t{gid}\t{gid}\n"
                f"Groups:\t{gid}\nNoNewPrivs:\t1\n",
                encoding="ascii",
            )
            tcp_header = (
                "sl local_address rem_address st tx_queue rx_queue tr tm->when "
                "retrnsmt uid timeout inode\n"
            )
            (process / "net/tcp").write_text(tcp_header, encoding="ascii")
            (process / "net/tcp6").write_text(tcp_header, encoding="ascii")
            (process / "net/unix").write_text(
                "Num RefCount Protocol Flags Type St Inode Path\n"
                f"0: 1 0 00010000 0001 01 555 {socket_path}\n",
                encoding="utf-8",
            )
            (process / "fd/7").symlink_to("socket:[555]")

            def runner(argv, **_kwargs):  # noqa: ANN001, ANN202
                return subprocess.CompletedProcess(argv, 0, f"{pid}\n", "")

            identity = release._dashboard_listener_identity(
                release_sha=release_sha,
                runner=runner,
                proc_root=Path(raw_root) / "proc",
                expected_root_uid=uid,
                expected_root_gid=gid,
            )
            assert identity["tcp_listener_count"] == 0
            assert identity["listener_inode"] == 555

            (process / "net/tcp").write_text(
                tcp_header + "0: 0100007F:0BB8 00000000:0000 0A 0:0 00:0 0 0 0 555\n",
                encoding="ascii",
            )
            with pytest.raises(release.ReleaseContractError, match="TCP listener"):
                release._dashboard_listener_identity(
                    release_sha=release_sha,
                    runner=runner,
                    proc_root=Path(raw_root) / "proc",
                    expected_root_uid=uid,
                    expected_root_gid=gid,
                )
        finally:
            listener.close()


def test_dashboard_socket_cleanup_rejects_live_or_substituted_paths(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    account = SimpleNamespace(pw_uid=os.geteuid(), pw_gid=os.getegid())
    monkeypatch.setattr(release, "_uid_process_ids", lambda _uid: ())
    with tempfile.TemporaryDirectory(prefix="sdc-", dir="/tmp") as raw_root:
        directory = Path(raw_root) / "d"
        directory.mkdir(mode=0o700)
        os.chown(directory, account.pw_uid, account.pw_gid)
        socket_path = directory / "c.sock"
        monkeypatch.setattr(release, "DASHBOARD_SOCKET_DIRECTORY", directory)
        monkeypatch.setattr(release, "DASHBOARD_SOCKET_PATH", socket_path)

        listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        listener.bind(str(socket_path))
        listener.listen(1)
        socket_path.chmod(0o600)
        with pytest.raises(release.ReleaseContractError, match="already live"):
            release._remove_stale_dashboard_socket(account=account)
        assert socket_path.exists()
        listener.close()

        release._remove_stale_dashboard_socket(account=account)
        assert not socket_path.exists()
        socket_path.write_bytes(b"not a socket")
        socket_path.chmod(0o600)
        with pytest.raises(release.ReleaseContractError, match="custody differs"):
            release._remove_stale_dashboard_socket(account=account)
        assert socket_path.read_bytes() == b"not a socket"


def test_observer_projection_sync_copies_only_validated_disposable_bytes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    uid = os.geteuid()
    gid = os.getegid()
    source_root = tmp_path / "projection-source"
    destination_root = tmp_path / "api-state"
    snapshot_root = tmp_path / "snapshots"
    for path, mode in (
        (source_root, 0o700),
        (destination_root, 0o750),
        (snapshot_root, 0o700),
    ):
        path.mkdir(mode=mode)
        os.chown(path, uid, gid)
    source = source_root / "mission-projection.json"
    destination = destination_root / "mission-projection.json"
    readiness_source = snapshot_root / "snapshot-readiness.v1.json"
    readiness_destination = destination_root / "snapshot-readiness.v1.json"
    projection_raw = b'{"projection":"validated-derived-only"}\n'
    source.write_bytes(projection_raw)
    source.chmod(0o600)
    api_env = tmp_path / "api.env"
    _write_private_env(
        api_env,
        {
            "DHARMA_MISSION_SNAPSHOT_CONFIG_DIGEST": "sha256:" + "a" * 64,
            "DHARMA_MISSION_SNAPSHOT_MIN_GENERATION": "1",
            "DHARMA_MISSION_SNAPSHOT_MAX_AGE_SECONDS": "60",
        },
    )
    monkeypatch.setattr(release, "PROJECTION_SOURCE_ROOT", source_root)
    monkeypatch.setattr(release, "WRITER_PROJECTION_PATH", source)
    monkeypatch.setattr(release, "API_STATE_ROOT", str(destination_root))
    monkeypatch.setattr(release, "OBSERVER_PROJECTION_PATH", destination)
    monkeypatch.setattr(release, "SNAPSHOT_READINESS_SOURCE_PATH", readiness_source)
    monkeypatch.setattr(
        release,
        "OBSERVER_SNAPSHOT_READINESS_PATH",
        readiness_destination,
    )
    account = SimpleNamespace(pw_uid=uid, pw_gid=gid)
    monkeypatch.setattr(release, "_require_static_service_identity", lambda: account)
    monkeypatch.setattr(release, "_require_observer_identity", lambda: account)
    validated: list[bytes] = []

    def validator(raw: bytes, **_kwargs: object) -> None:
        validated.append(raw)

    result = release.sync_observer_projection(
        role="writer",
        projection_source=source,
        projection_destination=destination,
        readiness_source=readiness_source,
        readiness_destination=readiness_destination,
        api_env_path=api_env,
        now=datetime(2026, 8, 23, tzinfo=timezone.utc),
        observed_node=release.WRITER_NODE,
        expected_root_uid=uid,
        expected_root_gid=gid,
        projection_validator=validator,
    )
    assert validated == [projection_raw]
    assert destination.read_bytes() == projection_raw
    assert stat.S_IMODE(destination.stat().st_mode) == 0o600
    assert result["canonical_state_visible_to_observer"] is False
    assert result["readiness_copied"] is False

    source.write_bytes(b"corrupt projection\n")
    source.chmod(0o600)

    def reject(*_args: object, **_kwargs: object) -> None:
        raise RuntimeError("invalid projection")

    with pytest.raises(release.ReleaseContractError, match="validation failed"):
        release.sync_observer_projection(
            role="writer",
            projection_source=source,
            projection_destination=destination,
            readiness_source=readiness_source,
            readiness_destination=readiness_destination,
            api_env_path=api_env,
            now=datetime(2026, 8, 23, tzinfo=timezone.utc),
            observed_node=release.WRITER_NODE,
            expected_root_uid=uid,
            expected_root_gid=gid,
            projection_validator=reject,
        )
    assert destination.read_bytes() == projection_raw


def test_campaign_build_overrides_existing_dashboard_default_proxy() -> None:
    repo = Path(__file__).resolve().parents[1]
    config = (repo / "dashboard/next.config.ts").read_text(encoding="utf-8")
    release_source = (repo / "scripts/runtime/sadhana_release.py").read_text(
        encoding="utf-8"
    )
    assert '"http://127.0.0.1:8420"' in config
    assert release.DASHBOARD_PROXY_URL == "http://127.0.0.1:18420"
    assert '"DHARMA_API_PROXY_URL": DASHBOARD_PROXY_URL' in release_source
    assert '"DHARMA_API_INTERNAL_URL": DASHBOARD_PROXY_URL' in release_source


def test_dashboard_build_gate_rejects_occupied_or_public_proxy(tmp_path: Path) -> None:
    manifest = tmp_path / ".next/routes-manifest.json"
    manifest.parent.mkdir()

    def write(destination: str) -> None:
        manifest.write_text(
            json.dumps(
                {
                    "rewrites": {
                        "beforeFiles": [],
                        "afterFiles": [
                            {
                                "source": "/api/:path*",
                                "destination": f"{destination}/api/:path*",
                            },
                            {
                                "source": "/ws/:path*",
                                "destination": f"{destination}/ws/:path*",
                            },
                        ],
                        "fallback": [],
                    }
                }
            ),
            encoding="utf-8",
        )

    write(release.DASHBOARD_PROXY_URL)
    release.verify_dashboard_build(tmp_path)
    write("http://127.0.0.1:8420")
    with pytest.raises(release.ReleaseContractError, match="loopback 18420"):
        release.verify_dashboard_build(tmp_path)
    write("https://public.example")
    with pytest.raises(release.ReleaseContractError, match="loopback 18420"):
        release.verify_dashboard_build(tmp_path)


def _write_private_env(path: Path, bindings: dict[str, str]) -> None:
    path.write_text(
        "".join(f"{key}={value}\n" for key, value in bindings.items()),
        encoding="utf-8",
    )
    path.chmod(0o600)


def test_env_files_bind_api_proxy_and_projection_without_logging_values(
    tmp_path: Path,
) -> None:
    writer_projection = str(release.WRITER_PROJECTION_PATH)
    observer_projection = str(release.OBSERVER_PROJECTION_PATH)
    supervisor = tmp_path / "supervisor.env"
    api = tmp_path / "api.env"
    dashboard = tmp_path / "dashboard.env"
    control = tmp_path / "control.env"
    replication = tmp_path / "replication.env"
    verifier = tmp_path / "verifier.env"
    _write_private_env(
        supervisor,
        {
            "SADHANA_WRITER_LOCK_PATH": "/var/lib/dharma-sadhana/state/writer.lock",
            "SADHANA_PROJECTION_PATH": writer_projection,
            "SADHANA_OPERATOR_ID": "operator",
            "SADHANA_MAX_DISPATCH_PER_CYCLE": "1",
            "SADHANA_CYCLE_INTERVAL_SECONDS": "30",
            "SADHANA_FRESHNESS_SECONDS": "120",
            "SADHANA_LEASE_ROOT": "/var/lib/dharma-sadhana/leases",
            "SADHANA_AGENT_ROSTER_PATH": "/etc/dharma-sadhana/roster.json",
            "SADHANA_AGENT_ROSTER_SHA256": "a" * 64,
            "SADHANA_OBJECTIVE_SHA256": "b" * 64,
        },
    )
    _write_private_env(
        api,
        {
            "SADHANA_API_PORT": "18420",
            "DHARMA_STATE_DIR": release.API_STATE_ROOT,
            "DHARMA_MISSION_SNAPSHOT_PATH": observer_projection,
            "DHARMA_MISSION_SNAPSHOT_MISSION_ID": release.MISSION_ID,
            "DHARMA_MISSION_SNAPSHOT_CONFIG_DIGEST": "sha256:" + "c" * 64,
            "DHARMA_MISSION_SNAPSHOT_MIN_GENERATION": "1",
            "DHARMA_MISSION_SNAPSHOT_MAX_AGE_SECONDS": "60",
        },
    )
    _write_private_env(
        dashboard,
        {
            "DHARMA_API_PROXY_URL": "http://127.0.0.1:18420",
            "DHARMA_API_INTERNAL_URL": "http://127.0.0.1:18420",
            "SADHANA_CONTROL_EXPECTED_ORIGIN": "https://megh.example.ts.net",
        },
    )
    _write_private_env(
        control,
        {"SADHANA_CONTROL_EXPECTED_ORIGIN": "https://megh.example.ts.net"},
    )
    _write_private_env(
        replication,
        {"SADHANA_REPLICATION_SSH_KEY": "/etc/dharma-sadhana/replication_ed25519"},
    )
    verifier_secret = "secret-fixture-never-log"
    _write_private_env(verifier, {"OLLAMA_API_KEY": verifier_secret})
    files = tuple(
        str(path)
        for path in (supervisor, api, dashboard, control, replication, verifier)
    )
    release._ensure_private_env_files(files)
    supervisor_bindings = release._private_env_bindings(supervisor)
    _write_private_env(
        supervisor,
        {
            **supervisor_bindings,
            "SADHANA_CANARY_TASK_ID": "preclaimed-canary",
        },
    )
    with pytest.raises(
        release.ReleaseContractError,
        match="post-preparation runtime outputs",
    ):
        release._ensure_private_env_files(files)
    _write_private_env(supervisor, supervisor_bindings)
    _write_private_env(
        supervisor,
        {**supervisor_bindings, "PYTHONPATH": "/tmp/untrusted"},
    )
    with pytest.raises(release.ReleaseContractError, match="fields differ"):
        release._ensure_private_env_files(files)
    _write_private_env(supervisor, supervisor_bindings)
    _write_private_env(verifier, {"OLLAMA_API_KEY": ""})
    with pytest.raises(release.ReleaseContractError) as blocked:
        release._ensure_private_env_files(files)
    assert verifier_secret not in str(blocked.value)
    _write_private_env(verifier, {"OLLAMA_API_KEY": verifier_secret})
    verifier.write_text(
        f"# comments are not an exact secret handle\nOLLAMA_API_KEY={verifier_secret}\n",
        encoding="utf-8",
    )
    verifier.chmod(0o600)
    with pytest.raises(release.ReleaseContractError, match="exactly one"):
        release._ensure_private_env_files(files)
    _write_private_env(verifier, {"OLLAMA_API_KEY": verifier_secret})
    _write_private_env(
        dashboard,
        {
            "DHARMA_API_PROXY_URL": "http://127.0.0.1:18420",
            "DHARMA_API_INTERNAL_URL": "http://127.0.0.1:18420",
            "SADHANA_CONTROL_EXPECTED_ORIGIN": "https://drift.example.ts.net",
        },
    )
    with pytest.raises(release.ReleaseContractError, match="EXPECTED_ORIGIN"):
        release._ensure_private_env_files(files)
    _write_private_env(
        dashboard,
        {
            "DHARMA_API_PROXY_URL": "http://127.0.0.1:18420",
            "DHARMA_API_INTERNAL_URL": "http://127.0.0.1:18420",
            "SADHANA_CONTROL_EXPECTED_ORIGIN": "https://megh.example.ts.net",
        },
    )
    _write_private_env(api, {"SADHANA_API_PORT": "8420"})
    with pytest.raises(release.ReleaseContractError, match="SADHANA_API_PORT"):
        release._ensure_private_env_files(files)


def test_writer_activation_plan_cannot_bypass_predispatch_transaction() -> None:
    with pytest.raises(
        release.ReleaseContractError,
        match="requires activate-predispatch",
    ):
        release.activation_commands("writer")


def test_standby_activation_plan_cannot_bypass_receipted_transaction() -> None:
    with pytest.raises(
        release.ReleaseContractError,
        match="requires activate-standby",
    ):
        release.activation_commands("standby")


def test_role_binding_rejects_deployment_on_the_wrong_host() -> None:
    assert (
        release._require_host_role("writer", observed_node=release.WRITER_NODE)
        == release.WRITER_NODE
    )
    assert (
        release._require_host_role("writer", observed_node="meghadharma-cloud.example")
        == release.WRITER_NODE
    )
    with pytest.raises(release.ReleaseContractError, match="host identity"):
        release._require_host_role("writer", observed_node="megh")
    with pytest.raises(release.ReleaseContractError, match="host identity"):
        release._require_host_role("writer", observed_node=release.STANDBY_NODE)


def test_prepare_host_binds_role_before_creating_any_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mutations: list[str] = []
    monkeypatch.setattr(release.os, "geteuid", lambda: 0)
    monkeypatch.setattr(
        release,
        "_prepare_service_identity_and_paths",
        lambda **_kwargs: mutations.append("prepared"),
    )
    with pytest.raises(release.ReleaseContractError, match="host identity"):
        release.prepare_host(
            "writer",
            observed_node=release.STANDBY_NODE,
        )
    assert mutations == []


def test_prepare_host_creates_oracle_roots_after_identity_before_build(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    order: list[str] = []
    service = SimpleNamespace(pw_uid=101, pw_gid=201)
    control = SimpleNamespace(pw_uid=102, pw_gid=202)
    observer = SimpleNamespace(pw_uid=103, pw_gid=203)
    dashboard = SimpleNamespace(pw_uid=104, pw_gid=204)
    oracle = SimpleNamespace(pw_uid=105, pw_gid=205)
    monkeypatch.setattr(release.os, "geteuid", lambda: 0)
    monkeypatch.setattr(
        release, "_require_host_role", lambda role, **_kwargs: release.WRITER_NODE
    )
    monkeypatch.setattr(release, "_validate_existing_writer_marker", lambda: False)

    def service_identity(**_kwargs: object) -> SimpleNamespace:
        order.append("service")
        return service

    def identity(name: str, value: SimpleNamespace) -> Callable[..., SimpleNamespace]:
        def prepare(**_kwargs: object) -> SimpleNamespace:
            order.append(name)
            return value

        return prepare

    monkeypatch.setattr(release, "_prepare_service_identity_and_paths", service_identity)
    monkeypatch.setattr(
        release,
        "_prepare_control_identity_and_paths",
        identity("control", control),
    )
    monkeypatch.setattr(
        release,
        "_prepare_observer_identity",
        identity("observer", observer),
    )
    monkeypatch.setattr(
        release,
        "_prepare_dashboard_identity",
        identity("dashboard", dashboard),
    )
    monkeypatch.setattr(
        release,
        "_prepare_oracle_identity",
        identity("oracle-identity", oracle),
    )
    monkeypatch.setattr(
        release,
        "_prepare_oracle_custody_roots",
        lambda **_kwargs: order.append("oracle-roots"),
    )
    monkeypatch.setattr(
        release,
        "_prepare_build_identity",
        lambda **_kwargs: order.append("build"),
    )
    assert release.prepare_host("writer", observed_node=release.WRITER_NODE) is service
    assert order == [
        "service",
        "control",
        "observer",
        "dashboard",
        "oracle-identity",
        "oracle-roots",
        "build",
    ]


def test_oracle_clean_host_persistent_roots_are_exact_replay_only(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    uid = os.geteuid()
    gid = os.getegid()
    persistent_parent = tmp_path / "var/lib/dharma-sadhana"
    receipt_parent = tmp_path / "etc/dharma-sadhana/receipts"
    for parent, mode in ((persistent_parent, 0o755), (receipt_parent, 0o700)):
        parent.mkdir(parents=True, mode=mode)
        parent.chmod(mode)
    roots = {
        "ORACLE_INPUT_ROOT": persistent_parent / "oracle-inputs",
        "ORACLE_CLAIM_ROOT": persistent_parent / "oracle-claims",
        "ORACLE_RUN_ROOT": persistent_parent / "oracle-runs",
        "ORACLE_QUARANTINE_ROOT": persistent_parent / "oracle-quarantine",
        "ORACLE_RECEIPT_ROOT": receipt_parent / "oracle",
    }
    for name, path in roots.items():
        monkeypatch.setattr(release, name, path)
    service = SimpleNamespace(pw_uid=uid, pw_gid=gid)
    oracle = SimpleNamespace(pw_uid=uid, pw_gid=gid)
    original_umask = os.umask(0o077)
    try:
        release._prepare_oracle_custody_roots(
            service_account=service,
            oracle_account=oracle,
            root_uid=uid,
            root_gid=gid,
        )
    finally:
        os.umask(original_umask)
    expected_modes = {
        roots["ORACLE_INPUT_ROOT"]: 0o700,
        roots["ORACLE_CLAIM_ROOT"]: 0o700,
        roots["ORACLE_RUN_ROOT"]: 0o710,
        roots["ORACLE_QUARANTINE_ROOT"]: 0o700,
        roots["ORACLE_RECEIPT_ROOT"]: 0o700,
    }
    first_inodes = {}
    for path, mode in expected_modes.items():
        identity = path.lstat()
        assert identity.st_uid == uid
        assert identity.st_gid == gid
        assert stat.S_IMODE(identity.st_mode) == mode
        first_inodes[path] = identity.st_ino
    release._prepare_oracle_custody_roots(
        service_account=service,
        oracle_account=oracle,
        root_uid=uid,
        root_gid=gid,
    )
    assert {path: path.lstat().st_ino for path in expected_modes} == first_inodes

    claim = roots["ORACLE_CLAIM_ROOT"]
    claim.chmod(0o755)
    with pytest.raises(release.ReleaseContractError, match="custody differs"):
        release._prepare_oracle_custody_roots(
            service_account=service,
            oracle_account=oracle,
            root_uid=uid,
            root_gid=gid,
        )
    assert stat.S_IMODE(claim.lstat().st_mode) == 0o755


def test_exact_oracle_host_root_rejects_symlink_and_foreign_custody(
    tmp_path: Path,
) -> None:
    uid = os.geteuid()
    gid = os.getegid()
    parent = tmp_path / "persistent"
    parent.mkdir(mode=0o755)
    parent.chmod(0o755)
    destination = parent / "destination"
    destination.mkdir(mode=0o700)
    link = parent / "oracle-inputs"
    link.symlink_to(destination, target_is_directory=True)
    with pytest.raises(release.ReleaseContractError, match="unavailable"):
        release._ensure_exact_host_directory(
            link,
            parent_uid=uid,
            parent_gid=gid,
            parent_mode=0o755,
            uid=uid,
            gid=gid,
            mode=0o700,
        )
    assert link.is_symlink()

    foreign = parent / "foreign"
    foreign.mkdir(mode=0o700)
    foreign.chmod(0o700)
    with pytest.raises(release.ReleaseContractError, match="custody differs"):
        release._ensure_exact_host_directory(
            foreign,
            parent_uid=uid,
            parent_gid=gid,
            parent_mode=0o755,
            uid=uid + 1,
            gid=gid,
            mode=0o700,
        )
    assert foreign.lstat().st_uid == uid


@pytest.mark.parametrize("failure_point", ("stat", "open"))
def test_oracle_clean_host_post_mkdir_failure_is_retryable(
    failure_point: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    uid = os.geteuid()
    gid = os.getegid()
    parent = tmp_path / "persistent"
    parent.mkdir(mode=0o755)
    parent.chmod(0o755)
    target = parent / f"oracle-{failure_point}"
    real_open = os.open
    real_stat = os.stat
    failed = False

    def injected_open(path, *args, **kwargs):  # noqa: ANN001, ANN002, ANN003, ANN202
        nonlocal failed
        if failure_point == "open" and path == target.name and not failed:
            failed = True
            raise OSError("injected post-mkdir open failure")
        return real_open(path, *args, **kwargs)

    def injected_stat(path, *args, **kwargs):  # noqa: ANN001, ANN002, ANN003, ANN202
        nonlocal failed
        if (
            failure_point == "stat"
            and path == target.name
            and kwargs.get("follow_symlinks") is False
            and not failed
        ):
            failed = True
            raise OSError("injected post-mkdir stat failure")
        return real_stat(path, *args, **kwargs)

    monkeypatch.setattr(release.os, "open", injected_open)
    monkeypatch.setattr(release.os, "stat", injected_stat)
    with pytest.raises(release.ReleaseContractError, match="unavailable"):
        release._ensure_exact_host_directory(
            target,
            parent_uid=uid,
            parent_gid=gid,
            parent_mode=0o755,
            uid=uid,
            gid=gid,
            mode=0o710,
        )
    assert failed is True
    assert not target.exists()

    monkeypatch.setattr(release.os, "open", real_open)
    monkeypatch.setattr(release.os, "stat", real_stat)
    release._ensure_exact_host_directory(
        target,
        parent_uid=uid,
        parent_gid=gid,
        parent_mode=0o755,
        uid=uid,
        gid=gid,
        mode=0o710,
    )
    assert stat.S_IMODE(target.lstat().st_mode) == 0o710


def _host_scaffold_fixture(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[SimpleNamespace, list[Path], Path, int, int]:
    root_uid = os.geteuid()
    root_gid = os.getegid()
    service_uid = root_uid if root_uid != 0 else 23145
    service_gid = root_gid if root_gid != 0 else 23145
    application_root = tmp_path / "opt/dharma-sadhana"
    data_root = tmp_path / "var/lib/dharma-sadhana"
    for parent in (application_root.parent, data_root.parent):
        parent.mkdir(parents=True, exist_ok=True, mode=0o755)
        os.chown(parent, root_uid, root_gid)
        parent.chmod(0o755)
    scaffold = [
        application_root,
        application_root / "releases",
        data_root,
        data_root / "leases",
        data_root / "snapshots",
        data_root / "state",
        data_root / "workspace",
    ]
    for path in scaffold:
        path.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.chown(path, root_uid, root_gid)
        path.chmod(0o700)
    etc_root = tmp_path / "etc/dharma-sadhana"
    receipt = etc_root / "receipts/host-scaffold-admission.v1.json"
    monkeypatch.setattr(release, "RELEASE_ROOT", str(application_root / "releases"))
    monkeypatch.setattr(release, "STATE_ROOT", str(data_root / "state"))
    monkeypatch.setattr(release, "WRITER_MARKER", etc_root / "writer-enabled")
    monkeypatch.setattr(release, "HOST_SCAFFOLD_RECEIPT", receipt)

    def ensure(path: Path, *, uid: int, gid: int, mode: int) -> None:
        path.mkdir(parents=True, exist_ok=True, mode=mode)
        os.chown(path, uid, gid)
        path.chmod(mode)

    monkeypatch.setattr(release, "_ensure_host_directory", ensure)
    account = SimpleNamespace(
        pw_name="dharma-sadhana",
        pw_uid=service_uid,
        pw_gid=service_gid,
        pw_dir="/var/lib/dharma-sadhana",
        pw_shell="/bin/sh",
    )
    return account, scaffold, receipt, root_uid, root_gid


@pytest.mark.parametrize("role", ("writer", "standby"))
def test_exact_live_host_scaffold_is_receipted_and_replayable(
    role: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    account, scaffold, receipt_path, root_uid, root_gid = _host_scaffold_fixture(
        tmp_path, monkeypatch
    )
    observed = datetime(2026, 8, 25, 3, 0, tzinfo=timezone.utc)
    receipt = release._admit_preexisting_host_scaffolding(
        role=role,
        account=account,
        observed_node=(
            release.WRITER_NODE if role == "writer" else release.STANDBY_NODE
        ),
        now=observed,
        expected_root_uid=root_uid,
        expected_root_gid=root_gid,
    )
    data_root = Path(release.STATE_ROOT).parent
    assert receipt["prestate"][str(data_root)]["children"] == [
        "leases",
        "snapshots",
        "state",
        "workspace",
    ]
    assert receipt["preexisting_empty_scaffolding"] is True
    assert receipt["data_deleted"] is False
    assert receipt_path.exists()
    replay = release._admit_preexisting_host_scaffolding(
        role=role,
        account=account,
        observed_node=(
            release.WRITER_NODE if role == "writer" else release.STANDBY_NODE
        ),
        now=observed + timedelta(seconds=1),
        expected_root_uid=root_uid,
        expected_root_gid=root_gid,
    )
    assert replay == receipt
    assert set(receipt["prestate"]) == {str(path) for path in scaffold}


@pytest.mark.parametrize("deviation", ("content", "symlink", "writable_mode"))
def test_host_scaffold_rejects_every_live_prestate_deviation_without_transition(
    deviation: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    account, scaffold, receipt_path, root_uid, root_gid = _host_scaffold_fixture(
        tmp_path, monkeypatch
    )
    data_root = Path(release.STATE_ROOT).parent
    if deviation == "content":
        unexpected = data_root / "leases/unexpected"
        unexpected.write_bytes(b"must-not-be-deleted\n")
        unexpected.chmod(0o600)
    elif deviation == "symlink":
        workspace = data_root / "workspace"
        workspace.rmdir()
        workspace.symlink_to(data_root / "state", target_is_directory=True)
    else:
        (data_root / "state").chmod(0o755)
    with pytest.raises(release.ReleaseContractError, match="scaffolding differs"):
        release._admit_preexisting_host_scaffolding(
            role="standby",
            account=account,
            observed_node=release.STANDBY_NODE,
            now=datetime(2026, 8, 25, 3, 0, tzinfo=timezone.utc),
            expected_root_uid=root_uid,
            expected_root_gid=root_gid,
        )
    assert not receipt_path.exists()
    assert stat.S_IMODE(scaffold[0].lstat().st_mode) == 0o700


def test_host_scaffold_transition_rolls_back_if_receipt_publication_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    account, scaffold, receipt_path, root_uid, root_gid = _host_scaffold_fixture(
        tmp_path, monkeypatch
    )

    def fail_publication(*_args: object, **_kwargs: object) -> None:
        raise OSError("simulated receipt failure")

    monkeypatch.setattr(release, "_atomic_private_bytes", fail_publication)
    with pytest.raises(OSError, match="receipt failure"):
        release._admit_preexisting_host_scaffolding(
            role="writer",
            account=account,
            observed_node=release.WRITER_NODE,
            now=datetime(2026, 8, 25, 3, 0, tzinfo=timezone.utc),
            expected_root_uid=root_uid,
            expected_root_gid=root_gid,
        )
    assert not receipt_path.exists()
    for path in scaffold:
        identity = path.lstat()
        assert identity.st_uid == root_uid
        assert identity.st_gid == root_gid
        assert stat.S_IMODE(identity.st_mode) == 0o700


def test_verifier_env_stdin_install_is_atomic_private_and_exact(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    os.chmod(tmp_path, 0o700)
    destination = tmp_path / "verifier.env"
    monkeypatch.setattr(release, "VERIFIER_ENV_PATH", destination)
    secret = b"OLLAMA_API_KEY=secret-fixture-never-log\n"
    installed = release.install_verifier_env_from_stdin(
        secret,
        destination=destination,
        observed_node=release.WRITER_NODE,
        expected_uid=os.geteuid(),
        expected_gid=os.getegid(),
    )
    assert installed == destination
    assert destination.read_bytes() == secret
    identity = destination.lstat()
    assert stat.S_IMODE(identity.st_mode) == 0o600
    assert identity.st_nlink == 1
    assert not list(tmp_path.glob(".verifier.env.*"))

    with pytest.raises(release.ReleaseContractError) as blocked:
        release.install_verifier_env_from_stdin(
            b"OLLAMA_API_KEY=secret-fixture-never-log\nSECOND=value\n",
            destination=destination,
            observed_node=release.WRITER_NODE,
            expected_uid=os.geteuid(),
            expected_gid=os.getegid(),
        )
    assert "secret-fixture-never-log" not in str(blocked.value)


def test_control_credential_stdin_install_is_exact_idempotent_and_private(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    os.chmod(tmp_path, 0o700)
    root = tmp_path / "credentials"
    root.mkdir(mode=0o700)
    destinations = {
        name: root / name
        for name in (
            "operator_bearer",
            "control_hmac_key",
            "tailscale_operator_login",
        )
    }
    monkeypatch.setattr(release, "CONTROL_CREDENTIAL_DESTINATIONS", destinations)

    class ControlSchemaError(ValueError):
        pass

    def validate_operator_login(value: object) -> str:
        if not isinstance(value, str) or not re.fullmatch(
            r"[A-Za-z0-9][A-Za-z0-9@._+:-]{0,253}", value
        ):
            raise ControlSchemaError("invalid login fixture")
        return value

    monkeypatch.setitem(
        sys.modules,
        "dharma_swarm.mission_control_operator_control",
        SimpleNamespace(
            ControlSchemaError=ControlSchemaError,
            validate_operator_login=validate_operator_login,
        ),
    )
    values = {
        "operator_bearer": b"bearer-fixture-0123456789-ABCDEFGH",
        "control_hmac_key": b"\x00binary-hmac-fixture-0123456789ABCDEF",
        "tailscale_operator_login": b"operator@example.test",
    }
    for name, value in values.items():
        destination = release.install_control_credential_from_stdin(
            value,
            credential=name,
            observed_node=release.WRITER_NODE,
            expected_uid=os.geteuid(),
            expected_gid=os.getegid(),
        )
        assert destination == destinations[name]
        assert destination.read_bytes() == value
        identity = destination.lstat()
        assert stat.S_IMODE(identity.st_mode) == 0o600
        assert identity.st_nlink == 1
        release.install_control_credential_from_stdin(
            value,
            credential=name,
            observed_node=release.WRITER_NODE,
            expected_uid=os.geteuid(),
            expected_gid=os.getegid(),
        )

    with pytest.raises(release.ReleaseContractError, match="conflicts"):
        release.install_control_credential_from_stdin(
            b"different-bearer-fixture-0123456789AB",
            credential="operator_bearer",
            observed_node=release.WRITER_NODE,
            expected_uid=os.geteuid(),
            expected_gid=os.getegid(),
        )
    assert destinations["operator_bearer"].read_bytes() == values["operator_bearer"]
    for bad in (b"short", b"x" * 32 + b"\n", b"x" * 31 + b"\r"):
        with pytest.raises(release.ReleaseContractError):
            release.install_control_credential_from_stdin(
                bad,
                credential="control_hmac_key",
                observed_node=release.WRITER_NODE,
                expected_uid=os.geteuid(),
                expected_gid=os.getegid(),
            )
    for bad_login in (b"!operator", b"operator login", b"a" * 255):
        with pytest.raises(release.ReleaseContractError):
            release.install_control_credential_from_stdin(
                bad_login,
                credential="tailscale_operator_login",
                observed_node=release.WRITER_NODE,
                expected_uid=os.geteuid(),
                expected_gid=os.getegid(),
            )
    with pytest.raises(release.ReleaseContractError):
        release.install_control_credential_from_stdin(
            b"b" * 513,
            credential="operator_bearer",
            observed_node=release.WRITER_NODE,
            expected_uid=os.geteuid(),
            expected_gid=os.getegid(),
        )


def test_failed_systemd_unit_with_zero_main_pid_is_proven_stopped() -> None:
    def runner(
        _command: tuple[str, ...],
        **_kwargs: object,
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(
            [],
            0,
            stdout="LoadState=loaded\nActiveState=failed\nMainPID=0\n",
            stderr="",
        )

    assert release._unit_inactive("example.service", runner=runner)

    def running(
        _command: tuple[str, ...],
        **_kwargs: object,
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(
            [],
            0,
            stdout="LoadState=loaded\nActiveState=active\nMainPID=123\n",
            stderr="",
        )

    assert not release._unit_inactive("example.service", runner=running)


def test_predispatch_refresh_expiry_stop_boundary_restarts_and_expires_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    receipt = tmp_path / "receipts/predispatch-refresh.v1.json"
    receipt.parent.mkdir(parents=True, mode=0o700)
    receipt.parent.chmod(0o700)
    monkeypatch.setattr(release, "PREDISPATCH_REFRESH_RECEIPT", receipt)
    monkeypatch.setattr(release, "ROLLBACK_RECEIPT", tmp_path / "rollback.json")
    monkeypatch.setattr(
        release, "DISPATCH_ENABLE_MARKER", tmp_path / "dispatch-enabled.json"
    )
    monkeypatch.setattr(release, "WRITER_MARKER", tmp_path / "writer-enabled")
    monkeypatch.setattr(release, "guard_campaign_clock", lambda **_kwargs: None)
    monkeypatch.setattr(
        release, "_validate_existing_writer_marker", lambda **_kwargs: False
    )
    monkeypatch.setattr(release, "_unit_inactive", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(release, "_unit_active", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(release, "_unit_static", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(release, "_systemd_main_pid", lambda *_args, **_kwargs: 0)
    account = SimpleNamespace(pw_uid=os.geteuid(), pw_gid=os.getegid())
    admission = {"receipt_digest": "sha256:" + "1" * 64}
    monkeypatch.setattr(
        release,
        "_verify_activation_staged_release",
        lambda **_kwargs: (admission, account),
    )
    contract = {
        "schema_version": "dharma.sadhana.prepared_projection_contract.v1",
        "path": str(release.WRITER_PROJECTION_PATH),
        "projection_schema_version": "dharma.mission_control.read_model.v1",
        "mission_id": release.MISSION_ID,
        "session_id": f"mission_campaign:{release.MISSION_ID}",
        "config_digest": "sha256:" + "2" * 64,
        "generation": 1,
        "minimum_cycle_sequence": 1,
        "campaign_status": "paused",
        "supervisor_state": "not_running",
        "writer_lock_held": False,
        "proves_process_liveness": False,
        "provider_dispatch": "NoProviderDispatch",
    }
    contract_digest = "sha256:" + hashlib.sha256(
        release._canonical_bytes(contract) + b"\n"
    ).hexdigest()
    preparation = {
        "proof": {
            "parameters": {
                "projection_contract_digest": contract_digest,
                "config_digest": contract["config_digest"],
            }
        },
        "projection": contract,
        "global_dispatch_rows": {
            "before": {"task_claim_ids": [], "delegation_run_ids": []},
            "after": {"task_claim_ids": [], "delegation_run_ids": []},
        },
        "receipt_digest": "sha256:" + "3" * 64,
    }
    binding = {
        "receipt_digest": "sha256:" + "4" * 64,
        "preparation_receipt_digest": preparation["receipt_digest"],
        "config_digest": contract["config_digest"],
    }
    monkeypatch.setattr(
        release, "verify_runtime_binding_activation", lambda **_kwargs: binding
    )
    monkeypatch.setattr(
        release,
        "_validate_root_preparation",
        lambda **_kwargs: (preparation, {}),
    )
    copied: list[str] = []
    monkeypatch.setattr(
        release,
        "_validate_refreshed_projection_bytes",
        lambda digest: copied.append(digest),
    )
    systemd_calls: list[tuple[str, ...]] = []

    def runner(argv, **_kwargs):  # noqa: ANN001, ANN202
        systemd_calls.append(tuple(argv))
        return subprocess.CompletedProcess(argv, 0, "", "")

    projection_sha256 = "5" * 64
    synchronized: list[datetime] = []

    def syncer(**kwargs):  # noqa: ANN003, ANN202
        synchronized.append(kwargs["now"])
        return {
            "status": "observer_projection_synced",
            "projection_sha256": projection_sha256,
        }

    observed = datetime(2026, 8, 23, 1, 30, tzinfo=timezone.utc)
    clock_samples: list[datetime] = []

    def crossing_campaign_guard(*, now: datetime, **_kwargs: object) -> None:
        clock_samples.append(now)
        if len(clock_samples) == 2:
            raise release.ReleaseContractError("outside the exact timebox")

    monkeypatch.setattr(release, "guard_campaign_clock", crossing_campaign_guard)
    crossing = iter((observed, observed + timedelta(seconds=121)))
    with pytest.raises(release.ReleaseContractError, match="outside the exact timebox"):
        release.refresh_predispatch(
            role="writer",
            release_sha="a" * 40,
            receipt_path=receipt,
            runner=runner,
            clock=lambda: next(crossing),
            observed_node=release.WRITER_NODE,
            expected_root_uid=os.geteuid(),
            expected_root_gid=os.getegid(),
            projection_syncer=syncer,
        )
    assert not receipt.exists()
    assert clock_samples == [observed, observed + timedelta(seconds=121)]
    monkeypatch.setattr(release, "guard_campaign_clock", lambda **_kwargs: None)
    systemd_calls.clear()
    synchronized.clear()
    copied.clear()
    first = release.refresh_predispatch(
        role="writer",
        release_sha="a" * 40,
        receipt_path=receipt,
        runner=runner,
        now=observed,
        observed_node=release.WRITER_NODE,
        expected_root_uid=os.geteuid(),
        expected_root_gid=os.getegid(),
        projection_syncer=syncer,
    )
    assert first["provider_dispatch"] == "NoProviderDispatch"
    assert first["global_dispatch_rows_empty"] is True
    assert first["valid_until"] == "2026-08-23T01:32:00Z"
    assert copied == [projection_sha256, projection_sha256]
    assert (
        release.SYSTEMCTL_PATH,
        "restart",
        release.RUNTIME_PREPARATION_UNIT,
    ) in systemd_calls

    second = release.refresh_predispatch(
        role="writer",
        release_sha="a" * 40,
        receipt_path=receipt,
        runner=runner,
        now=observed + timedelta(seconds=30),
        observed_node=release.WRITER_NODE,
        expected_root_uid=os.geteuid(),
        expected_root_gid=os.getegid(),
        projection_syncer=syncer,
    )
    assert second["receipt_digest"] != first["receipt_digest"]
    assert release._secure_json(receipt, require_private=True) == second
    monkeypatch.setattr(
        release,
        "_read_exact_custodied_json",
        lambda *_args, **_kwargs: (preparation, b"preparation\n", None),
    )
    admitted = release.validate_predispatch_refresh_receipt(
        role="writer",
        release_sha="a" * 40,
        receipt_path=receipt,
        runner=runner,
        now=observed + timedelta(seconds=60),
        observed_node=release.WRITER_NODE,
        expected_root_uid=os.geteuid(),
        expected_root_gid=os.getegid(),
    )
    assert admitted == second
    with pytest.raises(release.ReleaseContractError, match="receipt differs"):
        release.validate_predispatch_refresh_receipt(
            role="writer",
            release_sha="a" * 40,
            receipt_path=receipt,
            runner=runner,
            now=observed + timedelta(seconds=150),
            observed_node=release.WRITER_NODE,
            expected_root_uid=os.geteuid(),
            expected_root_gid=os.getegid(),
        )

    prior_raw = receipt.read_bytes()
    preparation["global_dispatch_rows"]["after"]["task_claim_ids"] = ["foreign"]
    with pytest.raises(release.ReleaseContractError, match="refresh contract"):
        release.refresh_predispatch(
            role="writer",
            release_sha="a" * 40,
            receipt_path=receipt,
            runner=runner,
            now=observed + timedelta(seconds=70),
            observed_node=release.WRITER_NODE,
            expected_root_uid=os.geteuid(),
            expected_root_gid=os.getegid(),
            projection_syncer=syncer,
        )
    assert receipt.read_bytes() == prior_raw


@pytest.mark.asyncio
async def test_campaign_activation_preflight_principal_binding_is_typed_seq2(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from dharma_swarm.mission_control import MissionControl
    from dharma_swarm.mission_control_campaign import (
        CampaignConfig,
        CampaignSupervisor,
    )
    from dharma_swarm.runtime_state import RuntimeStateStore, TaskClaim
    from dharma_swarm.task_board import TaskBoard
    from scripts.runtime.sadhana_prepare_runtime import _PreparationPauseRequest

    release_sha = "a" * 40
    observed = datetime(2026, 8, 25, 3, 0, tzinfo=timezone.utc)
    state_root = tmp_path / "state-root"
    (state_root / "state").mkdir(parents=True)
    (state_root / "db").mkdir(parents=True)
    runtime = RuntimeStateStore(
        state_root / "state/runtime.db",
        include_memory_plane=False,
    )
    board = TaskBoard(state_root / "db/tasks.db")
    await board.init_db()
    await runtime.init_db()
    control = MissionControl(board, runtime)
    await control.create_mission(release.MISSION_ID, title="SADHANA")
    config = CampaignConfig(release.MISSION_ID)
    supervisor = CampaignSupervisor(
        config,
        control,
        board,
        runtime,
        SimpleNamespace(),
        dispatcher=None,
    )
    await supervisor.start()
    pause = await supervisor.apply_operator_control_result(
        _PreparationPauseRequest(),
        "sadhana-runtime-preparation",
        "sha256:" + "1" * 64,
    )
    assert pause.status == "applied"
    assert await supervisor.effects_enabled() is False

    service = SimpleNamespace(
        pw_name="dharma-sadhana",
        pw_uid=os.geteuid(),
        pw_gid=os.getegid(),
        pw_dir="/var/lib/dharma-sadhana",
        pw_shell="/bin/sh",
    )
    monkeypatch.setattr(release, "_require_static_service_identity", lambda: service)
    control = SimpleNamespace(
        pw_name="dharma-sadhana-control",
        pw_uid=os.geteuid(),
        pw_gid=os.getegid(),
    )
    monkeypatch.setattr(release.pwd, "getpwnam", lambda _name: control)
    monkeypatch.setattr(release, "ROLLBACK_RECEIPT", tmp_path / "rollback.json")
    control_root = tmp_path / "control"
    control_root.mkdir(mode=0o750)
    normal = control_root / "normal"
    normal.mkdir(mode=0o770)
    normal.chmod(0o770)
    inflight = control_root / "inflight"
    inflight.mkdir(mode=0o700)
    emergency = control_root / "emergency"
    emergency.mkdir(mode=0o770)
    emergency.chmod(0o770)
    emergency_inflight = tmp_path / "emergency-inflight"
    emergency_inflight.mkdir(mode=0o700)
    activation_root = control_root / "activation"
    activation_root.mkdir(mode=0o750)
    activation_root.chmod(0o750)
    activation_proof = activation_root / "campaign-activation.v1.json"
    monkeypatch.setattr(release, "CONTROL_NORMAL_INBOX", normal)
    monkeypatch.setattr(release, "CONTROL_INFLIGHT_ROOT", inflight)
    monkeypatch.setattr(release, "CONTROL_EMERGENCY_INBOX", emergency)
    monkeypatch.setattr(release, "EMERGENCY_INFLIGHT_ROOT", emergency_inflight)
    monkeypatch.setattr(release, "EMERGENCY_STOP_MARKER", tmp_path / "emergency-stop")
    monkeypatch.setattr(release, "CONTROL_ACTIVATION_ROOT", activation_root)
    monkeypatch.setattr(release, "CAMPAIGN_ACTIVATION_PROOF", activation_proof)
    credentials = tmp_path / "credentials"
    credentials.mkdir(mode=0o700)
    credentials.chmod(0o700)

    def seal(payload: dict[str, object]) -> dict[str, object]:
        payload["receipt_digest"] = release._canonical_self_digest(
            payload, "receipt_digest"
        )
        return payload

    def publish(name: str, payload: dict[str, object] | bytes) -> Path:
        path = credentials / name
        path.unlink(missing_ok=True)
        raw = (
            payload
            if isinstance(payload, bytes)
            else release._canonical_bytes(payload) + b"\n"
        )
        path.write_bytes(raw)
        path.chmod(0o400)
        return path

    account_confirmation = _account_ui_confirmation_fixture(
        release_sha=release_sha,
        operator_login_sha256=hashlib.sha256(
            b"operator@example.test"
        ).hexdigest(),
        observed_at="2026-08-25T02:59:00Z",
    )
    dashboard = seal(
        {
            "schema_version": release.DASHBOARD_IDENTITY_SCHEMA_VERSION,
            "campaign_id": release.MISSION_ID,
            "release_sha": release_sha,
            "dashboard_unit_digest": "2" * 64,
            "tailscale_version": release.TAILSCALE_VERSION,
            "serve_status_before_sha256": "3" * 64,
            "serve_status_after_sha256": "4" * 64,
            "serve_upstream": release.TAILSCALE_ROUTE,
            "socket_stat": {},
            "dashboard_process_identity": {},
            "negative_access_matrix": {},
            "tcp_listener_inventory": {},
            "funnel_absence": True,
            "operator_login_sha256": hashlib.sha256(
                b"operator@example.test"
            ).hexdigest(),
            "authenticated_account_ui_confirmation": account_confirmation,
            "rollback_probe": {},
            "verdict": "PASS",
            "receipt_digest": "",
        }
    )
    binding = seal(
        {
            "schema_version": release.RUNTIME_BINDING_SCHEMA_VERSION,
            "campaign_id": release.MISSION_ID,
            "mission_id": release.MISSION_ID,
            "release_sha": release_sha,
            "created_at": "2026-08-25T02:58:00Z",
            "service_uid": service.pw_uid,
            "service_gid": service.pw_gid,
            "release_admission_receipt_digest": "sha256:" + "5" * 64,
            "release_input_set_digest": "6" * 64,
            "preparation_receipt_digest": "sha256:" + "7" * 64,
            "preparation_input_digest": "sha256:" + "8" * 64,
            "config_digest": config.digest,
            "supervisor_runtime_env_sha256": "9" * 64,
            "task_set_digest": "sha256:" + "a" * 64,
            "manifest_set_digest": "sha256:" + "b" * 64,
            "session_generation": 1,
            "session_status": "paused",
            "prepared_proof_type": (
                "Prepared<Mission,Release,InputSet,Config,TaskSet,"
                "ProjectionContract>"
            ),
            "prepared_effect": "NoEffect",
            "root_verification_type": (
                "RootVerified<Prepared<Mission,Release,InputSet,Config,TaskSet,"
                "ProjectionContract>>"
            ),
            "files": {},
            "receipt_digest": "",
        }
    )

    def marker(*, dashboard_digest: str) -> dict[str, object]:
        return seal(
            {
                "schema_version": release.DISPATCH_ENABLE_SCHEMA_VERSION,
                "campaign_id": release.MISSION_ID,
                "release_sha": release_sha,
                "enabled_at": "2026-08-25T02:59:30Z",
                "predispatch_target_active": True,
                "supervisor_main_pid_before_enable": 0,
                "observer_health_receipt_digest": "sha256:" + "c" * 64,
                "dashboard_identity_receipt_digest": dashboard_digest,
                "operator_credential_receipt_digest": "sha256:" + "d" * 64,
                "runtime_staging_receipt_digest": "sha256:" + "e" * 64,
                "runtime_binding_receipt_digest": binding["receipt_digest"],
                "predispatch_refresh_receipt_digest": "sha256:" + "f" * 64,
                "standby_capacity_receipt_digest": "sha256:" + "0" * 64,
                "preactivation_clock_proof_receipt_digest": "sha256:" + "1" * 64,
                "oracle_sandbox_evidence_digest": "sha256:" + "2" * 64,
                "standby_replication_route_probe_receipt_digest": (
                    "sha256:" + "4" * 64
                ),
                "supervisor_activation_env_sha256": "3" * 64,
                "dispatch_authorized": True,
                "effect_executed": False,
                "receipt_digest": "",
            }
        )

    dispatch_path = credentials / "dispatch_activation_receipt"
    dashboard_path = publish("dashboard_identity_receipt", dashboard)
    binding_path = publish("runtime_binding_activation", binding)
    login_path = publish("tailscale_operator_login", b"operator@example.test")
    hmac_path = publish("control_hmac_key", b"h" * 32)
    activation_kwargs = {
        "role": "writer",
        "release_sha": release_sha,
        "dispatch_receipt_path": dispatch_path,
        "dashboard_receipt_path": dashboard_path,
        "runtime_binding_path": binding_path,
        "operator_login_path": login_path,
        "control_hmac_path": hmac_path,
        "credential_root": credentials,
        "state_root": state_root,
        "runtime_store": runtime,
        "control_gate_path": state_root / "writer.lock.control",
        "activation_evidence_path": activation_proof,
        "now": observed,
        "observed_node": release.WRITER_NODE,
        "expected_root_uid": os.geteuid(),
        "expected_root_gid": os.getegid(),
    }

    with pytest.raises(release.ReleaseContractError, match="unavailable"):
        await release.activate_campaign_session(**activation_kwargs)
    paused = await runtime.get_session(config.session_id)
    assert paused is not None and paused.status == "paused"
    publish(
        "dispatch_activation_receipt",
        marker(dashboard_digest="sha256:" + "4" * 64),
    )
    with pytest.raises(release.ReleaseContractError, match="credential binding"):
        await release.activate_campaign_session(**activation_kwargs)
    still_paused = await runtime.get_session(config.session_id)
    assert still_paused == paused
    assert await runtime.list_task_claims(session_id=config.session_id) == []
    assert await runtime.list_delegation_runs(session_id=config.session_id) == []

    good_marker = marker(dashboard_digest=str(dashboard["receipt_digest"]))
    publish("dispatch_activation_receipt", good_marker)

    for blocked in (normal, inflight, emergency, emergency_inflight):
        candidate = blocked / "pending"
        candidate.write_bytes(b"pending")
        with pytest.raises(release.ReleaseContractError, match="not stably empty"):
            await release.activate_campaign_session(**activation_kwargs)
        candidate.unlink()
        assert await runtime.get_session(config.session_id) == paused
        assert not activation_proof.exists()

    publish("tailscale_operator_login", b"different@example.test")
    with pytest.raises(release.ReleaseContractError, match="principal differs"):
        await release.activate_campaign_session(**activation_kwargs)
    assert await runtime.get_session(config.session_id) == paused
    assert not activation_proof.exists()
    publish("tailscale_operator_login", b"operator@example.test")

    stale_confirmation = copy.deepcopy(account_confirmation)
    stale_confirmation["observed_at"] = "2026-08-25T02:49:00Z"
    stale_confirmation["receipt_digest"] = release._canonical_self_digest(
        stale_confirmation,
        "receipt_digest",
    )
    stale_dashboard = copy.deepcopy(dashboard)
    stale_dashboard["authenticated_account_ui_confirmation"] = stale_confirmation
    stale_dashboard["receipt_digest"] = release._canonical_self_digest(
        stale_dashboard,
        "receipt_digest",
    )
    publish("dashboard_identity_receipt", stale_dashboard)
    publish(
        "dispatch_activation_receipt",
        marker(dashboard_digest=str(stale_dashboard["receipt_digest"])),
    )
    with pytest.raises(
        release.ReleaseContractError, match="account UI confirmation is not fresh"
    ):
        await release.activate_campaign_session(**activation_kwargs)
    assert await runtime.get_session(config.session_id) == paused
    assert await runtime.list_task_claims(session_id=config.session_id) == []
    assert await runtime.list_delegation_runs(session_id=config.session_id) == []
    assert not activation_proof.exists()
    publish("dashboard_identity_receipt", dashboard)
    publish("dispatch_activation_receipt", good_marker)

    crossing = iter(
        (
            observed,
            observed + timedelta(seconds=121),
        )
    )
    crossing_kwargs = {
        **activation_kwargs,
        "now": None,
        "clock": lambda: next(crossing),
    }
    with pytest.raises(release.ReleaseContractError, match="marker is not timely"):
        await release.activate_campaign_session(**crossing_kwargs)
    assert await runtime.get_session(config.session_id) == paused
    assert not activation_proof.exists()

    stop_crossing = iter(
        (
            observed,
            release._parse_utc(release.CAMPAIGN_STOP_UTC, "campaign stop"),
        )
    )
    with pytest.raises(release.ReleaseContractError, match="outside the exact timebox"):
        await release.activate_campaign_session(
            **{
                **activation_kwargs,
                "now": None,
                "clock": lambda: next(stop_crossing),
            }
        )
    assert await runtime.get_session(config.session_id) == paused
    assert not activation_proof.exists()

    activated = await release.activate_campaign_session(**activation_kwargs)
    assert activated["transition_sequence"] == 2
    assert activated["prior_control_state"] == "PAUSED"
    assert activated["next_control_state"] == "RUNNING"
    assert activated["external_effect_performed"] is False
    assert activated["activation_evidence_path"] == str(activation_proof)
    assert activation_proof.is_file()
    assert stat.S_IMODE(activation_proof.stat().st_mode) == 0o640
    active = await runtime.get_session(config.session_id)
    assert active is not None and active.status == "active"
    assert active.metadata["operator_control_state"]["transition_sequence"] == 2
    assert active.metadata["operator_control_state"]["action"] == "resume"
    assert await supervisor.effects_enabled() is True
    assert await runtime.list_task_claims(session_id=config.session_id) == []
    assert await runtime.list_delegation_runs(session_id=config.session_id) == []

    await runtime.record_task_claim(
        TaskClaim(
            claim_id="claim-after-typed-activation",
            task_id="task-after-typed-activation",
            agent_id="agent-after-typed-activation",
            status="claimed",
            session_id=config.session_id,
            claimed_at=observed + timedelta(minutes=1),
            heartbeat_at=observed + timedelta(minutes=1),
            metadata={"mission_id": release.MISSION_ID},
        )
    )

    publish("tailscale_operator_login", b"different@example.test")
    with pytest.raises(release.ReleaseContractError, match="principal differs"):
        await release.activate_campaign_session(**activation_kwargs)
    assert await runtime.get_session(config.session_id) == active
    publish("tailscale_operator_login", b"operator@example.test")
    activation_kwargs["now"] = observed + timedelta(minutes=10)
    replay = await release.activate_campaign_session(**activation_kwargs)
    assert replay == activated
    assert await runtime.get_session(config.session_id) == active
    assert [
        claim.claim_id
        for claim in await runtime.list_task_claims(session_id=config.session_id)
    ] == ["claim-after-typed-activation"]


def test_runtime_preparation_fence_stops_exact_static_unit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    active = True
    calls: list[tuple[str, ...]] = []

    def runner(argv, **_kwargs):  # noqa: ANN001, ANN202
        nonlocal active
        calls.append(tuple(argv))
        if tuple(argv)[1:] == ("stop", release.RUNTIME_PREPARATION_UNIT):
            active = False
        return subprocess.CompletedProcess(argv, 0, "", "")

    monkeypatch.setattr(release, "_unit_active", lambda *_args, **_kwargs: active)
    monkeypatch.setattr(
        release, "_unit_inactive", lambda *_args, **_kwargs: not active
    )
    monkeypatch.setattr(release, "_unit_static", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(release, "_systemd_main_pid", lambda *_args, **_kwargs: 0)
    release._fence_runtime_preparation(runner=runner)
    assert calls == [
        (release.SYSTEMCTL_PATH, "stop", release.RUNTIME_PREPARATION_UNIT)
    ]


def test_standby_capacity_proof_renews_over_one_frozen_snapshot(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    snapshot_root = tmp_path / "snapshots"
    snapshot_root.mkdir(mode=0o700)
    snapshot = snapshot_root / ("20260823T013000Z-" + "a" * 12)
    snapshot.mkdir(mode=0o500)
    snapshot.chmod(0o500)
    monkeypatch.setattr(release, "SNAPSHOT_ROOT", str(snapshot_root))

    class Capacity:
        f_bavail = 30 * 1024 * 1024 * 1024
        f_frsize = 1

    validated: list[tuple[Path, str]] = []
    frozen: list[Path] = []

    def validate(path: Path, **kwargs: object) -> tuple[dict[str, str], str]:
        validated.append((path, str(kwargs["expected_release_sha"])))
        return {"snapshot_digest": "b" * 64}, "c" * 64

    def validate_frozen(path: Path, **_kwargs: object) -> None:
        frozen.append(path)

    observed = datetime(2026, 8, 23, 1, 31, tzinfo=timezone.utc)
    proof = release.emit_standby_capacity_proof(
        release_sha="a" * 40,
        runtime_db_bytes=1024 * 1024,
        tasks_db_bytes=1024 * 1024,
        projection_bytes=1024 * 1024,
        snapshot_root=snapshot_root,
        strict_host_key_channel=True,
        ssh_connection_observed=True,
        statvfs=lambda _path: Capacity(),
        now=observed,
        observed_node=release.STANDBY_NODE,
        expected_root_uid=os.geteuid(),
        expected_root_gid=os.getegid(),
        snapshot_validator=validate,
        frozen_validator=validate_frozen,
    )
    assert proof["existing_snapshot_entries"] == 1
    assert proof["zero_existing_snapshot_directories"] is False
    assert proof["snapshot_ledger"] == [
        {
            "snapshot_id": snapshot.name,
            "snapshot_digest": "b" * 64,
            "tree_digest": "c" * 64,
        }
    ]
    assert validated == [(snapshot, "a" * 40)]
    assert frozen == [snapshot]

    forged = dict(proof)
    forged["zero_existing_snapshot_directories"] = True
    forged["receipt_digest"] = release._canonical_self_digest(
        forged, "receipt_digest"
    )
    with pytest.raises(release.ReleaseContractError, match="bindings"):
        release._validate_standby_capacity_payload(
            forged,
            release_sha="a" * 40,
            now=observed,
        )

    from scripts.runtime import sadhana_snapshot

    def not_frozen(*_args: object, **_kwargs: object) -> None:
        raise sadhana_snapshot.SnapshotError("not frozen")

    with pytest.raises(release.ReleaseContractError, match="series is invalid"):
        release.emit_standby_capacity_proof(
            release_sha="a" * 40,
            runtime_db_bytes=1,
            tasks_db_bytes=1,
            projection_bytes=1,
            snapshot_root=snapshot_root,
            strict_host_key_channel=True,
            ssh_connection_observed=True,
            statvfs=lambda _path: Capacity(),
            now=observed,
            observed_node=release.STANDBY_NODE,
            expected_root_uid=os.geteuid(),
            expected_root_gid=os.getegid(),
            snapshot_validator=validate,
            frozen_validator=not_frozen,
        )


def test_standby_capacity_snapshot_ledger_renewal_is_append_only(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from scripts.runtime import sadhana_snapshot

    snapshot_root = tmp_path / "snapshots"
    snapshot_root.mkdir(mode=0o700)
    snapshot_root.chmod(0o700)
    destination = tmp_path / "receipts" / "standby-capacity.v2.json"
    monkeypatch.setattr(release, "SNAPSHOT_ROOT", str(snapshot_root))
    monkeypatch.setattr(release, "STANDBY_CAPACITY_RECEIPT_TARGET", destination)
    monkeypatch.setattr(
        release,
        "_ensure_host_directory",
        lambda path, **kwargs: path.chmod(kwargs["mode"]),
    )

    class Capacity:
        f_bavail = 30 * 1024 * 1024 * 1024
        f_frsize = 1

    observed = datetime(2026, 8, 23, 1, 30, tzinfo=timezone.utc)
    base = release.emit_standby_capacity_proof(
        release_sha="a" * 40,
        runtime_db_bytes=1024,
        tasks_db_bytes=1024,
        projection_bytes=1024,
        snapshot_root=snapshot_root,
        strict_host_key_channel=True,
        ssh_connection_observed=True,
        statvfs=lambda _path: Capacity(),
        now=observed,
        observed_node=release.STANDBY_NODE,
        expected_root_uid=os.geteuid(),
        expected_root_gid=os.getegid(),
    )

    first_entry = {
        "snapshot_id": "20260822T171512Z-aaaaaaaaaaaa",
        "snapshot_digest": "b" * 64,
        "tree_digest": "c" * 64,
    }
    second_entry = {
        "snapshot_id": "20260822T172012Z-aaaaaaaaaaaa",
        "snapshot_digest": "d" * 64,
        "tree_digest": "e" * 64,
    }

    def renewal(
        ledger: list[dict[str, str]],
        at: datetime,
    ) -> dict[str, object]:
        payload = copy.deepcopy(base)
        payload["observed_at"] = at.isoformat().replace("+00:00", "Z")
        payload["valid_until"] = min(
            at + timedelta(seconds=release.STANDBY_CAPACITY_PROOF_FRESHNESS_SECONDS),
            release._parse_utc(release.CAMPAIGN_STOP_UTC, "campaign_stop_utc"),
        ).isoformat().replace("+00:00", "Z")
        payload["snapshot_ledger"] = ledger
        payload["existing_snapshot_entries"] = len(ledger)
        payload["zero_existing_snapshot_directories"] = not ledger
        capacity = sadhana_snapshot.snapshot_capacity_formula(
            source_bytes=int(payload["source_bytes"]),
            existing_snapshot_count=len(ledger),
            free_bytes=int(payload["free_bytes"]),
        )
        payload["estimated_bytes_per_snapshot"] = capacity[
            "estimated_bytes_per_snapshot"
        ]
        payload["required_free_bytes_for_remaining_series"] = capacity[
            "required_free_bytes_for_remaining_series"
        ]
        payload["receipt_digest"] = release._canonical_self_digest(
            payload,
            "receipt_digest",
        )
        return payload

    first = renewal([first_entry], observed)
    release.install_standby_capacity_proof_from_stdin(
        release._canonical_bytes(first) + b"\n",
        release_sha="a" * 40,
        destination=destination,
        now=observed,
        observed_node=release.WRITER_NODE,
        expected_root_uid=os.geteuid(),
        expected_root_gid=os.getegid(),
    )
    for hostile_ledger in (
        [],
        [{**first_entry, "snapshot_digest": "f" * 64}],
        [{**first_entry, "tree_digest": "f" * 64}],
    ):
        hostile = renewal(hostile_ledger, observed + timedelta(seconds=1))
        with pytest.raises(release.ReleaseContractError, match="not newer"):
            release.install_standby_capacity_proof_from_stdin(
                release._canonical_bytes(hostile) + b"\n",
                release_sha="a" * 40,
                destination=destination,
                now=observed + timedelta(seconds=1),
                observed_node=release.WRITER_NODE,
                expected_root_uid=os.geteuid(),
                expected_root_gid=os.getegid(),
            )

    appended = renewal(
        [first_entry, second_entry],
        observed + timedelta(seconds=2),
    )
    release.install_standby_capacity_proof_from_stdin(
        release._canonical_bytes(appended) + b"\n",
        release_sha="a" * 40,
        destination=destination,
        now=observed + timedelta(seconds=2),
        observed_node=release.WRITER_NODE,
        expected_root_uid=os.geteuid(),
        expected_root_gid=os.getegid(),
    )
    installed = json.loads(destination.read_text(encoding="utf-8"))
    assert installed["snapshot_ledger"] == [first_entry, second_entry]

    late_ledger = [first_entry, second_entry]
    first_late_stamp = datetime(2026, 8, 22, 17, 25, 12, tzinfo=timezone.utc)
    for index in range(sadhana_snapshot.MAX_CAMPAIGN_SNAPSHOTS - 3):
        stamp = first_late_stamp + timedelta(minutes=5 * index)
        late_ledger.append(
            {
                "snapshot_id": (
                    stamp.strftime("%Y%m%dT%H%M%SZ-") + "a" * 12
                ),
                "snapshot_digest": hashlib.sha256(
                    f"snapshot-{index}".encode()
                ).hexdigest(),
                "tree_digest": hashlib.sha256(f"tree-{index}".encode()).hexdigest(),
            }
        )
    assert len(late_ledger) == 2_879
    assert len(late_ledger) == sadhana_snapshot.MAX_CAMPAIGN_SNAPSHOTS - 1
    assert len(release._canonical_bytes(late_ledger[0])) == (
        release._STANDBY_CAPACITY_LEDGER_ENTRY_BYTES
    )
    provisioned_bytes = (
        release._STANDBY_CAPACITY_FIXED_ENVELOPE_ALLOWANCE_BYTES
        + release._STANDBY_CAPACITY_LEDGER_ENTRY_BYTES
        * sadhana_snapshot.MAX_CAMPAIGN_SNAPSHOTS
    )
    assert provisioned_bytes == 620_416
    assert provisioned_bytes <= release._MAX_STANDBY_CAPACITY_PROOF_BYTES
    late_observed = datetime(2026, 9, 1, 17, 10, 12, tzinfo=timezone.utc)
    late = renewal(late_ledger, late_observed)
    late_raw = release._canonical_bytes(late) + b"\n"
    assert 64 * 1024 < len(late_raw) <= provisioned_bytes
    assert provisioned_bytes <= release._MAX_STANDBY_CAPACITY_PROOF_BYTES

    prior_read_bounds: list[int | None] = []
    original_reader = release._read_exact_canonical_json

    def bounded_reader(*args: object, **kwargs: object):  # noqa: ANN202
        prior_read_bounds.append(kwargs.get("maximum_bytes"))
        return original_reader(*args, **kwargs)

    monkeypatch.setattr(release, "_read_exact_canonical_json", bounded_reader)
    release.install_standby_capacity_proof_from_stdin(
        late_raw,
        release_sha="a" * 40,
        destination=destination,
        now=late_observed,
        observed_node=release.WRITER_NODE,
        expected_root_uid=os.geteuid(),
        expected_root_gid=os.getegid(),
    )
    assert prior_read_bounds == [release._MAX_STANDBY_CAPACITY_PROOF_BYTES]
    installed = json.loads(destination.read_text(encoding="utf-8"))
    assert installed["snapshot_ledger"] == late_ledger


def test_standby_capacity_proof_is_read_only_exact_and_formula_bound(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    snapshot_root = tmp_path / "snapshots"
    snapshot_root.mkdir(mode=0o700)
    snapshot_root.chmod(0o700)
    monkeypatch.setattr(release, "SNAPSHOT_ROOT", str(snapshot_root))

    class Capacity:
        f_bavail = 30 * 1024 * 1024 * 1024
        f_frsize = 1

    observed = datetime(2026, 8, 23, 1, 30, tzinfo=timezone.utc)
    proof = release.emit_standby_capacity_proof(
        release_sha="a" * 40,
        runtime_db_bytes=1024 * 1024,
        tasks_db_bytes=1024 * 1024,
        projection_bytes=1024 * 1024,
        snapshot_root=snapshot_root,
        strict_host_key_channel=True,
        ssh_connection_observed=True,
        statvfs=lambda _path: Capacity(),
        now=observed,
        observed_node=release.STANDBY_NODE,
        expected_root_uid=os.geteuid(),
        expected_root_gid=os.getegid(),
    )
    assert proof["verdict"] == "PASS"
    assert proof["standby_capacity_proven"] is True
    assert proof["existing_snapshot_entries"] == 0
    assert proof["source_bytes"] == 3 * 1024 * 1024
    assert proof["receipt_digest"].startswith("sha256:")
    assert list(snapshot_root.iterdir()) == []

    drift = copy.deepcopy(proof)
    drift["estimated_bytes_per_snapshot"] += 1
    drift["receipt_digest"] = release._canonical_self_digest(drift, "receipt_digest")
    with pytest.raises(release.ReleaseContractError, match="formula"):
        release._validate_standby_capacity_payload(
            drift,
            release_sha="a" * 40,
            now=observed,
        )
    (snapshot_root / "unexpected").mkdir()
    with pytest.raises(release.ReleaseContractError, match="foreign entry"):
        release.emit_standby_capacity_proof(
            release_sha="a" * 40,
            runtime_db_bytes=1,
            tasks_db_bytes=1,
            projection_bytes=1,
            snapshot_root=snapshot_root,
            strict_host_key_channel=True,
            ssh_connection_observed=True,
            statvfs=lambda _path: Capacity(),
            now=observed,
            observed_node=release.STANDBY_NODE,
            expected_root_uid=os.geteuid(),
            expected_root_gid=os.getegid(),
        )

    proof_bytes = release._canonical_bytes(proof) + b"\n"
    monkeypatch.setattr(
        release,
        "_MAX_STANDBY_CAPACITY_PROOF_BYTES",
        len(proof_bytes) - 1,
    )
    with pytest.raises(release.ReleaseContractError, match="size bound"):
        release._validate_standby_capacity_payload(
            proof,
            release_sha="a" * 40,
            now=observed,
        )


def test_standby_capacity_installer_and_cli_use_dedicated_one_mib_cap(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert release._MAX_STANDBY_CAPACITY_PROOF_BYTES == 1024 * 1024
    destination = tmp_path / "receipts" / "standby-capacity.v2.json"
    monkeypatch.setattr(release, "STANDBY_CAPACITY_RECEIPT_TARGET", destination)
    over_cap = b"x" * release._MAX_STANDBY_CAPACITY_PROOF_BYTES + b"\n"
    with pytest.raises(release.ReleaseContractError, match="framing"):
        release.install_standby_capacity_proof_from_stdin(
            over_cap,
            release_sha="a" * 40,
            destination=destination,
            observed_node=release.WRITER_NODE,
            expected_root_uid=os.geteuid(),
            expected_root_gid=os.getegid(),
        )

    original_json_loads = release.json.loads
    for error_type in (ValueError, RecursionError):
        def reject_json(*_args: object, **_kwargs: object) -> object:
            raise error_type("hostile capacity JSON")

        monkeypatch.setattr(release.json, "loads", reject_json)
        with pytest.raises(release.ReleaseContractError, match="JSON differs"):
            release.install_standby_capacity_proof_from_stdin(
                b"{}\n",
                release_sha="a" * 40,
                destination=destination,
                observed_node=release.WRITER_NODE,
                expected_root_uid=os.geteuid(),
                expected_root_gid=os.getegid(),
            )
    monkeypatch.setattr(release.json, "loads", original_json_loads)

    read_bounds: list[int] = []

    class BoundedInput:
        def read(self, maximum_bytes: int) -> bytes:
            read_bounds.append(maximum_bytes)
            return b"{}\n"

    installed_raw: list[bytes] = []

    def install(raw: bytes, **_kwargs: object) -> Path:
        installed_raw.append(raw)
        return destination

    monkeypatch.setattr(release.sys, "stdin", SimpleNamespace(buffer=BoundedInput()))
    monkeypatch.setattr(release, "install_standby_capacity_proof_from_stdin", install)
    assert (
        release.main(
            [
                "install-standby-capacity-proof",
                "--role",
                "writer",
                "--release-sha",
                "a" * 40,
            ]
        )
        == 0
    )
    assert read_bounds == [release._MAX_STANDBY_CAPACITY_PROOF_BYTES + 1]
    assert installed_raw == [b"{}\n"]
    assert json.loads(capsys.readouterr().out)["status"] == (
        "standby_capacity_proof_installed"
    )


def test_standby_capacity_existing_receipt_is_bounded_for_renewal_and_guard(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    destination = tmp_path / "receipts" / "standby-capacity.v2.json"
    destination.parent.mkdir(mode=0o700)
    destination.write_bytes(
        b"x" * (release._MAX_STANDBY_CAPACITY_PROOF_BYTES + 1)
    )
    destination.chmod(0o600)
    monkeypatch.setattr(release, "STANDBY_CAPACITY_RECEIPT_TARGET", destination)
    monkeypatch.setattr(
        release,
        "_ensure_host_directory",
        lambda path, **kwargs: path.chmod(kwargs["mode"]),
    )

    candidate = {
        "schema_version": release.STANDBY_CAPACITY_SCHEMA_VERSION,
        "receipt_digest": "sha256:" + "a" * 64,
    }
    candidate_raw = release._canonical_bytes(candidate) + b"\n"

    def admit_candidate(
        payload: dict[str, object],
        **_kwargs: object,
    ) -> dict[str, object]:
        return payload

    monkeypatch.setattr(
        release,
        "_validate_standby_capacity_payload",
        admit_candidate,
    )
    with pytest.raises(release.ReleaseContractError, match="lacks exact custody"):
        release.install_standby_capacity_proof_from_stdin(
            candidate_raw,
            release_sha="a" * 40,
            destination=destination,
            now=datetime(2026, 8, 25, 12, tzinfo=timezone.utc),
            observed_node=release.WRITER_NODE,
            expected_root_uid=os.geteuid(),
            expected_root_gid=os.getegid(),
        )

    with pytest.raises(release.ReleaseContractError, match="lacks exact custody"):
        release.guard_standby_capacity(
            role="writer",
            release_sha="a" * 40,
            projection_path=release.WRITER_PROJECTION_PATH,
            receipt_path=destination,
            now=datetime(2026, 8, 25, 12, tzinfo=timezone.utc),
            observed_node=release.WRITER_NODE,
            expected_root_uid=os.geteuid(),
            expected_root_gid=os.getegid(),
        )

    with pytest.raises(release.ReleaseContractError, match="size bound differs"):
        release._read_exact_canonical_json(
            destination,
            expected_uid=os.geteuid(),
            expected_gid=os.getegid(),
            expected_schema=release.STANDBY_CAPACITY_SCHEMA_VERSION,
            digest_field="receipt_digest",
            maximum_bytes=release._MAX_JSON_BYTES + 1,
        )


def test_writer_capacity_gate_binds_installed_proof_to_exact_source_sizes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state = tmp_path / "state"
    runtime_db = state / "state/runtime.db"
    tasks_db = state / "db/tasks.db"
    projection_root = tmp_path / "projection-source"
    projection = projection_root / "mission-projection.json"
    for path, raw in (
        (runtime_db, b"runtime-db"),
        (tasks_db, b"tasks-db-bytes"),
        (projection, b'{"projection":true}\n'),
    ):
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        path.parent.chmod(0o700)
        path.write_bytes(raw)
        path.chmod(0o600)
    snapshot_root = tmp_path / "snapshots"
    snapshot_root.mkdir(mode=0o700)
    snapshot_root.chmod(0o700)
    receipt = tmp_path / "receipts/preactivation/standby-capacity.v2.json"
    monkeypatch.setattr(release, "SNAPSHOT_ROOT", str(snapshot_root))
    monkeypatch.setattr(release, "STATE_ROOT", str(state))
    monkeypatch.setattr(release, "PROJECTION_SOURCE_ROOT", projection_root)
    monkeypatch.setattr(release, "WRITER_PROJECTION_PATH", projection)
    monkeypatch.setattr(release, "STANDBY_CAPACITY_RECEIPT_TARGET", receipt)
    monkeypatch.setattr(
        release,
        "_ensure_host_directory",
        lambda path, **kwargs: path.chmod(kwargs["mode"]),
    )
    monkeypatch.setattr(
        release,
        "_require_static_service_identity",
        lambda: SimpleNamespace(pw_uid=os.geteuid(), pw_gid=os.getegid()),
    )
    api_env = tmp_path / "api.env"
    _write_private_env(
        api_env,
        {
            "DHARMA_MISSION_SNAPSHOT_CONFIG_DIGEST": "sha256:" + "b" * 64,
            "DHARMA_MISSION_SNAPSHOT_MIN_GENERATION": "1",
            "DHARMA_MISSION_SNAPSHOT_MAX_AGE_SECONDS": "60",
        },
    )
    validated: list[bytes] = []

    def validate_projection(raw: bytes, **_kwargs: object) -> None:
        validated.append(raw)

    class Capacity:
        f_bavail = 30 * 1024 * 1024 * 1024
        f_frsize = 1

    observed = datetime(2026, 8, 23, 1, 30, tzinfo=timezone.utc)
    proof = release.emit_standby_capacity_proof(
        release_sha="a" * 40,
        runtime_db_bytes=runtime_db.stat().st_size,
        tasks_db_bytes=tasks_db.stat().st_size,
        projection_bytes=projection.stat().st_size,
        snapshot_root=snapshot_root,
        strict_host_key_channel=True,
        ssh_connection_observed=True,
        statvfs=lambda _path: Capacity(),
        now=observed,
        observed_node=release.STANDBY_NODE,
        expected_root_uid=os.geteuid(),
        expected_root_gid=os.getegid(),
    )
    raw = release._canonical_bytes(proof) + b"\n"
    release.install_standby_capacity_proof_from_stdin(
        raw,
        release_sha="a" * 40,
        destination=receipt,
        now=observed + timedelta(seconds=1),
        observed_node=release.WRITER_NODE,
        expected_root_uid=os.geteuid(),
        expected_root_gid=os.getegid(),
    )
    capacity_read_bounds: list[int | None] = []
    original_reader = release._read_exact_canonical_json

    def bounded_reader(*args: object, **kwargs: object):  # noqa: ANN202
        capacity_read_bounds.append(kwargs.get("maximum_bytes"))
        return original_reader(*args, **kwargs)

    monkeypatch.setattr(release, "_read_exact_canonical_json", bounded_reader)
    admitted = release.guard_standby_capacity(
        role="writer",
        release_sha="a" * 40,
        projection_path=projection,
        receipt_path=receipt,
        now=observed + timedelta(seconds=2),
        observed_node=release.WRITER_NODE,
        expected_root_uid=os.geteuid(),
        expected_root_gid=os.getegid(),
        api_env_path=api_env,
        projection_validator=validate_projection,
    )
    assert admitted["standby_capacity_proven"] is True
    assert capacity_read_bounds == [release._MAX_STANDBY_CAPACITY_PROOF_BYTES]
    assert validated == [b'{"projection":true}\n']

    def reject_projection(*_args: object, **_kwargs: object) -> None:
        raise RuntimeError("invalid projection fixture")

    with pytest.raises(release.ReleaseContractError, match="projection validation"):
        release.guard_standby_capacity(
            role="writer",
            release_sha="a" * 40,
            projection_path=projection,
            receipt_path=receipt,
            now=observed + timedelta(seconds=3),
            observed_node=release.WRITER_NODE,
            expected_root_uid=os.geteuid(),
            expected_root_gid=os.getegid(),
            api_env_path=api_env,
            projection_validator=reject_projection,
        )
    projection.write_bytes(projection.read_bytes() + b"drift")
    with pytest.raises(release.ReleaseContractError, match="source bytes drifted"):
        release.guard_standby_capacity(
            role="writer",
            release_sha="a" * 40,
            projection_path=projection,
            receipt_path=receipt,
            now=observed + timedelta(seconds=4),
            observed_node=release.WRITER_NODE,
            expected_root_uid=os.geteuid(),
            expected_root_gid=os.getegid(),
            api_env_path=api_env,
            projection_validator=validate_projection,
        )


def test_writer_capacity_gate_rejects_state_root_projection_constant_before_io(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert release.PROJECTION_SOURCE_ROOT == Path(
        "/var/lib/dharma-sadhana/projection-source"
    )
    assert release.WRITER_PROJECTION_PATH == (
        release.PROJECTION_SOURCE_ROOT / "mission-projection.json"
    )
    monkeypatch.setattr(release.os, "geteuid", lambda: 0)
    with pytest.raises(release.ReleaseContractError, match="projection path differs"):
        release.guard_standby_capacity(
            role="writer",
            release_sha="a" * 40,
            projection_path=Path(release.STATE_ROOT) / "mission-projection.json",
            observed_node=release.WRITER_NODE,
        )


def _emergency_test_topology(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> dict[str, object]:
    os.chmod(tmp_path, 0o700)
    control_root = tmp_path / "control"
    control_root.mkdir(mode=0o700)
    inbox = control_root / "emergency"
    inbox.mkdir(mode=0o770)
    inbox.chmod(0o770)
    quarantine = tmp_path / "emergency-quarantine"
    quarantine.mkdir(mode=0o700)
    inflight = tmp_path / "emergency-inflight"
    inflight.mkdir(mode=0o700)
    receipts = tmp_path / "receipts"
    receipts.mkdir(mode=0o700)
    lock = tmp_path / "emergency-apply.lock"
    hmac_key = tmp_path / "control_hmac_key"
    hmac_key.write_bytes(b"h" * 32)
    hmac_key.chmod(0o600)
    login = tmp_path / "tailscale_operator_login"
    login.write_bytes(b"operator@example.test")
    login.chmod(0o600)
    valid = inbox / f"{'a' * 64}.control.json"
    valid.write_bytes(b"valid fixture delegated to shared decoder")
    valid.chmod(0o640)
    request = SimpleNamespace(
        request_id="request-1",
        idempotency_key="idempotency-1",
        action="emergency_stop",
    )
    envelope = SimpleNamespace(request=request)

    def decode(path: Path, **_kwargs: object) -> tuple[object, str, dict[str, int]]:
        return (
            envelope,
            f"sha256:{'b' * 64}",
            release._candidate_identity(path.lstat()),
        )

    monkeypatch.setattr(release, "CONTROL_EMERGENCY_INBOX", inbox)
    monkeypatch.setattr(release, "EMERGENCY_QUARANTINE_ROOT", quarantine)
    monkeypatch.setattr(release, "EMERGENCY_INFLIGHT_ROOT", inflight)
    monkeypatch.setattr(release, "EMERGENCY_APPLY_LOCK", lock)
    monkeypatch.setattr(release, "EMERGENCY_RECEIPT_ROOT", receipts)
    monkeypatch.setattr(release, "EMERGENCY_STOP_MARKER", receipts / "stopped")
    monkeypatch.setattr(release, "_read_emergency_envelope", decode)
    monkeypatch.setattr(
        release.pwd,
        "getpwnam",
        lambda _name: SimpleNamespace(pw_uid=os.geteuid(), pw_gid=os.getegid()),
    )
    return {
        "inbox": inbox,
        "inflight": inflight,
        "receipts": receipts,
        "marker": receipts / "stopped",
        "valid": valid,
        "hmac_key": hmac_key,
        "login": login,
    }


def test_prepare_host_precreates_exact_empty_emergency_lock_and_rejects_drift(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    os.chmod(tmp_path, 0o700)
    lock = tmp_path / "emergency-apply.lock"
    monkeypatch.setattr(release, "EMERGENCY_APPLY_LOCK", lock)
    release._ensure_emergency_apply_lock(
        expected_root_uid=os.geteuid(),
        expected_root_gid=os.getegid(),
    )
    first = lock.lstat()
    assert lock.read_bytes() == b""
    assert stat.S_IMODE(first.st_mode) == 0o600
    assert first.st_uid == os.geteuid()
    assert first.st_gid == os.getegid()
    release._ensure_emergency_apply_lock(
        expected_root_uid=os.geteuid(),
        expected_root_gid=os.getegid(),
    )
    assert lock.lstat().st_ino == first.st_ino
    lock.write_bytes(b"hostile content")
    with pytest.raises(release.ReleaseContractError, match="lock custody differs"):
        release._ensure_emergency_apply_lock(
            expected_root_uid=os.geteuid(),
            expected_root_gid=os.getegid(),
        )


def test_poison_entry_is_quarantined_before_valid_emergency_is_applied(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    os.chmod(tmp_path, 0o700)
    control_root = tmp_path / "control"
    control_root.mkdir(mode=0o700)
    inbox = control_root / "emergency"
    inbox.mkdir(mode=0o770)
    inbox.chmod(0o770)
    quarantine = tmp_path / "emergency-quarantine"
    quarantine.mkdir(mode=0o700)
    inflight = tmp_path / "emergency-inflight"
    inflight.mkdir(mode=0o700)
    apply_lock = tmp_path / "emergency-apply.lock"
    receipts = tmp_path / "receipts"
    receipts.mkdir(mode=0o700)
    hmac_key = tmp_path / "control_hmac_key"
    hmac_key.write_bytes(b"h" * 32)
    hmac_key.chmod(0o600)
    login = tmp_path / "tailscale_operator_login"
    login.write_bytes(b"operator@example.test")
    login.chmod(0o600)
    poison = inbox / "000-poison"
    poison.write_bytes(b"not an envelope")
    poison.chmod(0o640)
    valid = inbox / f"{'a' * 64}.control.json"
    valid.write_bytes(b"valid fixture delegated to shared decoder")
    valid.chmod(0o640)

    monkeypatch.setattr(release, "CONTROL_EMERGENCY_INBOX", inbox)
    monkeypatch.setattr(release, "EMERGENCY_QUARANTINE_ROOT", quarantine)
    monkeypatch.setattr(release, "EMERGENCY_INFLIGHT_ROOT", inflight)
    monkeypatch.setattr(release, "EMERGENCY_APPLY_LOCK", apply_lock)
    monkeypatch.setattr(release, "EMERGENCY_RECEIPT_ROOT", receipts)
    monkeypatch.setattr(release, "EMERGENCY_STOP_MARKER", receipts / "stopped")
    monkeypatch.setattr(
        release.pwd,
        "getpwnam",
        lambda _name: SimpleNamespace(pw_uid=os.geteuid(), pw_gid=os.getegid()),
    )

    request = SimpleNamespace(
        request_id="request-1",
        idempotency_key="idempotency-1",
        action="emergency_stop",
    )
    envelope = SimpleNamespace(request=request)

    def decode(path: Path, **_kwargs: object) -> tuple[object, str, dict[str, int]]:
        if path.name == poison.name:
            raise release.InvalidEmergencyCandidate("poison fixture")
        return (
            envelope,
            f"sha256:{'b' * 64}",
            release._candidate_identity(path.lstat()),
        )

    monkeypatch.setattr(release, "_read_emergency_envelope", decode)
    monkeypatch.setattr(release, "_unit_inactive", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(
        release, "_campaign_listeners_absent", lambda *_args, **_kwargs: True
    )
    stop_calls: list[tuple[str, ...]] = []

    def runner(
        command: tuple[str, ...],
        **_kwargs: object,
    ) -> subprocess.CompletedProcess[str]:
        stop_calls.append(command)
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    now = datetime(2026, 8, 23, 1, 30, tzinfo=timezone.utc)
    applied = release.apply_emergency_controls(
        role="writer",
        hmac_key_file=hmac_key,
        operator_login_file=login,
        inbox=inbox,
        runner=runner,
        now=lambda: now,
        observed_node=release.WRITER_NODE,
        expected_root_uid=os.geteuid(),
        expected_root_gid=os.getegid(),
    )
    assert len(applied) == 1
    assert applied[0]["status"] == "applied"
    assert len(stop_calls) == 1
    assert not poison.exists()
    assert not valid.exists()
    assert len(list(quarantine.iterdir())) == 1
    rejection = next(receipts.glob("*.rejected.json"))
    assert json.loads(rejection.read_text())["status"] == "rejected"

    infrastructure_fault = inbox / f"{'c' * 64}.control.json"
    infrastructure_fault.write_bytes(b"valid bytes but decoder unavailable")
    infrastructure_fault.chmod(0o640)

    def unavailable(
        *_args: object, **_kwargs: object
    ) -> tuple[object, str, dict[str, int]]:
        raise release.ReleaseContractError("shared decoder unavailable")

    monkeypatch.setattr(release, "_read_emergency_envelope", unavailable)
    with pytest.raises(release.ReleaseContractError, match="decoder unavailable"):
        release.apply_emergency_controls(
            role="writer",
            hmac_key_file=hmac_key,
            operator_login_file=login,
            inbox=inbox,
            runner=runner,
            now=lambda: now,
            observed_node=release.WRITER_NODE,
            expected_root_uid=os.geteuid(),
            expected_root_gid=os.getegid(),
        )
    assert infrastructure_fault.exists()


@pytest.mark.parametrize(
    ("boundary", "expected_stop_calls", "marker_expected"),
    (
        ("stop", 1, False),
        ("postcondition", 1, False),
        ("terminal", 1, True),
    ),
)
def test_emergency_fault_boundaries_never_consume_an_unfinished_claim(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    boundary: str,
    expected_stop_calls: int,
    marker_expected: bool,
) -> None:
    topology = _emergency_test_topology(tmp_path, monkeypatch)
    marker = topology["marker"]
    assert isinstance(marker, Path)
    original_persist = release._persist_emergency_stop_marker
    original_terminal = release._write_emergency_terminal
    if boundary == "terminal":

        def terminal_failure(*_args: object, **_kwargs: object) -> None:
            raise release.ReleaseContractError("injected terminal failure")

        monkeypatch.setattr(release, "_write_emergency_terminal", terminal_failure)
    monkeypatch.setattr(
        release,
        "_unit_inactive",
        lambda *_args, **_kwargs: boundary != "postcondition",
    )
    monkeypatch.setattr(
        release, "_campaign_listeners_absent", lambda *_args, **_kwargs: True
    )
    stop_calls = 0

    def runner(
        command: tuple[str, ...],
        **_kwargs: object,
    ) -> subprocess.CompletedProcess[str]:
        nonlocal stop_calls
        assert command == (
            release.SYSTEMCTL_PATH,
            "stop",
            "dharma-sadhana.target",
        )
        assert not marker.exists(), "durable marker must follow proven cessation"
        stop_calls += 1
        return subprocess.CompletedProcess(
            command,
            1 if boundary == "stop" else 0,
            stdout="",
            stderr="",
        )

    now = datetime(2026, 8, 23, 1, 30, tzinfo=timezone.utc)
    with pytest.raises(release.ReleaseContractError, match=boundary):
        release.apply_emergency_controls(
            role="writer",
            hmac_key_file=topology["hmac_key"],
            operator_login_file=topology["login"],
            inbox=topology["inbox"],
            runner=runner,
            now=lambda: now,
            observed_node=release.WRITER_NODE,
            expected_root_uid=os.geteuid(),
            expected_root_gid=os.getegid(),
        )
    assert stop_calls == expected_stop_calls
    assert marker.exists() is marker_expected
    assert not topology["valid"].exists()
    assert len(list(topology["inflight"].glob("*.claim"))) == 1
    assert not list(topology["receipts"].glob("*.terminal.json"))
    # Keep references live so monkeypatch restores the trusted implementations
    # even in the two injected-function lanes.
    assert callable(original_persist)
    assert callable(original_terminal)


def test_emergency_marker_failure_cannot_delay_stop_and_recovery_repairs_barrier(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    topology = _emergency_test_topology(tmp_path, monkeypatch)
    monkeypatch.setattr(release, "_unit_inactive", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(
        release, "_campaign_listeners_absent", lambda *_args, **_kwargs: True
    )
    original_persist = release._persist_emergency_stop_marker
    marker_attempts = 0

    def flaky_marker(**kwargs: object) -> dict[str, object]:
        nonlocal marker_attempts
        marker_attempts += 1
        if marker_attempts == 1:
            raise release.EmergencyMarkerPersistenceError(
                "injected post-cessation marker failure"
            )
        return original_persist(**kwargs)

    monkeypatch.setattr(release, "_persist_emergency_stop_marker", flaky_marker)
    stop_calls = 0

    def runner(
        command: tuple[str, ...],
        **_kwargs: object,
    ) -> subprocess.CompletedProcess[str]:
        nonlocal stop_calls
        assert command == (
            release.SYSTEMCTL_PATH,
            "stop",
            "dharma-sadhana.target",
        )
        stop_calls += 1
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    arguments = {
        "role": "writer",
        "hmac_key_file": topology["hmac_key"],
        "operator_login_file": topology["login"],
        "inbox": topology["inbox"],
        "runner": runner,
        "now": lambda: datetime(2026, 8, 23, 1, 30, tzinfo=timezone.utc),
        "observed_node": release.WRITER_NODE,
        "expected_root_uid": os.geteuid(),
        "expected_root_gid": os.getegid(),
    }
    first = release.apply_emergency_controls(**arguments)
    assert stop_calls == 1
    assert first[0]["status"] == "applied"
    assert first[0]["target_inactive"] is True
    assert first[0]["partof_units_inactive"] is True
    assert first[0]["campaign_listeners_absent"] is True
    assert first[0]["durable_stop_marker_persisted"] is False
    assert first[0]["error_code"] == "durable_stop_marker_not_persisted"
    assert not topology["marker"].exists()
    assert len(list(topology["inflight"].glob("*.claim"))) == 1

    terminal_path = next(topology["receipts"].glob("*.terminal.json"))
    immutable_terminal = terminal_path.read_bytes()
    replay = release.apply_emergency_controls(**arguments)
    assert replay == first
    assert stop_calls == 2
    assert marker_attempts == 2
    assert topology["marker"].exists()
    assert terminal_path.read_bytes() == immutable_terminal
    assert not list(topology["inflight"].iterdir())


def test_emergency_terminal_failure_replays_the_root_claim(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    topology = _emergency_test_topology(tmp_path, monkeypatch)
    monkeypatch.setattr(release, "_unit_inactive", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(
        release, "_campaign_listeners_absent", lambda *_args, **_kwargs: True
    )
    original_terminal = release._write_emergency_terminal
    terminal_attempts = 0

    def flaky_terminal(*args: object, **kwargs: object) -> None:
        nonlocal terminal_attempts
        terminal_attempts += 1
        if terminal_attempts == 1:
            raise release.ReleaseContractError("injected terminal failure")
        original_terminal(*args, **kwargs)

    monkeypatch.setattr(release, "_write_emergency_terminal", flaky_terminal)
    stop_calls = 0

    def runner(
        command: tuple[str, ...],
        **_kwargs: object,
    ) -> subprocess.CompletedProcess[str]:
        nonlocal stop_calls
        assert topology["marker"].exists() is (stop_calls > 0)
        stop_calls += 1
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    arguments = {
        "role": "writer",
        "hmac_key_file": topology["hmac_key"],
        "operator_login_file": topology["login"],
        "inbox": topology["inbox"],
        "runner": runner,
        "now": lambda: datetime(2026, 8, 23, 1, 30, tzinfo=timezone.utc),
        "observed_node": release.WRITER_NODE,
        "expected_root_uid": os.geteuid(),
        "expected_root_gid": os.getegid(),
    }
    with pytest.raises(release.ReleaseContractError, match="terminal failure"):
        release.apply_emergency_controls(**arguments)
    assert len(list(topology["inflight"].glob("*.claim"))) == 1
    applied = release.apply_emergency_controls(**arguments)
    assert applied[0]["status"] == "applied"
    assert stop_calls == 2
    assert terminal_attempts == 2
    assert not list(topology["inflight"].iterdir())


def test_emergency_claim_detects_substitution_before_any_effect(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    topology = _emergency_test_topology(tmp_path, monkeypatch)
    candidate = topology["valid"]
    assert isinstance(candidate, Path)
    expected_identity = release._candidate_identity(candidate.lstat())
    reservation = topology["inflight"] / f"{'c' * 64}.claim"
    reservation.mkdir(mode=0o700)
    original_move = release._rename_noreplace_at

    def substitute_then_move(
        source_directory_fd: int,
        source_name: str,
        destination_directory_fd: int,
        destination_name: str,
    ) -> None:
        candidate.unlink()
        candidate.write_bytes(b"substituted after admission")
        candidate.chmod(0o640)
        original_move(
            source_directory_fd,
            source_name,
            destination_directory_fd,
            destination_name,
        )

    monkeypatch.setattr(release, "_rename_noreplace_at", substitute_then_move)
    with pytest.raises(release.ReleaseContractError, match="claimed inode differs"):
        release._move_emergency_candidate_into_claim(
            original_filename=candidate.name,
            expected_identity=expected_identity,
            reservation=reservation,
        )
    assert not topology["marker"].exists()
    assert (reservation / "entry").read_bytes() == b"substituted after admission"


def test_emergency_stop_marker_is_immutable_and_conflict_denying(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    os.chmod(tmp_path, 0o700)
    marker = tmp_path / "emergency-stopped"
    monkeypatch.setattr(release, "EMERGENCY_STOP_MARKER", marker)
    claim = {
        "envelope_sha256": f"sha256:{'a' * 64}",
        "request_id": "request-1",
        "idempotency_key": "idempotency-1",
        "claimed_at": "2026-08-23T01:30:00Z",
    }
    first = release._persist_emergency_stop_marker(
        claim=claim,
        expected_root_uid=os.geteuid(),
        expected_root_gid=os.getegid(),
    )
    original = marker.read_bytes()
    replay = release._persist_emergency_stop_marker(
        claim=claim,
        expected_root_uid=os.geteuid(),
        expected_root_gid=os.getegid(),
    )
    assert replay == first
    conflicting = dict(claim, request_id="request-2")
    with pytest.raises(
        release.EmergencyMarkerPersistenceError, match="not persisted"
    ):
        release._persist_emergency_stop_marker(
            claim=conflicting,
            expected_root_uid=os.geteuid(),
            expected_root_gid=os.getegid(),
        )
    assert marker.read_bytes() == original


def test_bad_roster_hash_is_rejected_before_any_custody_mutation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mutations: list[Path] = []
    monkeypatch.setattr(
        release,
        "sha256_file",
        lambda *_args, **_kwargs: "b" * 64,
    )
    monkeypatch.setattr(
        release,
        "_scope_runtime_file",
        lambda path, **_kwargs: mutations.append(path),
    )
    parsed_env = {
        "supervisor.env": {
            "SADHANA_AGENT_ROSTER_PATH": "/etc/dharma-sadhana/roster.json",
            "SADHANA_AGENT_ROSTER_SHA256": "a" * 64,
        },
        "replication.env": {
            "SADHANA_REPLICATION_SSH_KEY": "/etc/dharma-sadhana/replication_ed25519",
        },
    }
    account = SimpleNamespace(pw_uid=1234, pw_gid=1234)
    with pytest.raises(release.ReleaseContractError, match="roster bytes"):
        release._ensure_scoped_runtime_files(parsed_env, account=account)
    assert mutations == []


def test_loopback_port_preflight_checks_only_the_two_campaign_ports() -> None:
    observed: list[tuple[str, int]] = []

    class Probe:
        def bind(self, address: tuple[str, int]) -> None:
            observed.append(address)

        def close(self) -> None:
            return None

    release._require_loopback_ports_free(socket_factory=lambda *_: Probe())
    assert observed == [
        ("127.0.0.1", 18420),
        ("127.0.0.1", 18421),
    ]

    class Occupied(Probe):
        def bind(self, address: tuple[str, int]) -> None:
            if address[1] == 18420:
                raise OSError("fixture secret must not escape")

    with pytest.raises(release.ReleaseContractError, match="18420 is already occupied"):
        release._require_loopback_ports_free(socket_factory=lambda *_: Occupied())


@pytest.mark.parametrize("replay", (False, True))
def test_predispatch_occupied_port_fails_before_intent_marker_or_unit_effect(
    replay: bool,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    os.chmod(tmp_path, 0o700)
    receipt = tmp_path / "predispatch.json"
    intent = tmp_path / "predispatch-intent.json"
    writer = tmp_path / "writer-enabled"
    dispatch = tmp_path / "dispatch-enabled.json"
    rollback = tmp_path / "rollback.json"
    monkeypatch.setattr(release, "PREDISPATCH_ACTIVATION_RECEIPT", receipt)
    monkeypatch.setattr(release, "PREDISPATCH_ACTIVATION_INTENT", intent)
    monkeypatch.setattr(release, "WRITER_MARKER", writer)
    monkeypatch.setattr(release, "DISPATCH_ENABLE_MARKER", dispatch)
    monkeypatch.setattr(release, "ROLLBACK_RECEIPT", rollback)
    if replay:
        receipt.write_bytes(b"{}\n")
        receipt.chmod(0o600)
    monkeypatch.setattr(release, "guard_campaign_clock", lambda **_kwargs: None)
    monkeypatch.setattr(release, "_systemd_main_pid", lambda *_args, **_kwargs: 0)
    monkeypatch.setattr(
        release,
        "_verify_activation_staged_release",
        lambda **_kwargs: (
            {"receipt_digest": "sha256:" + "7" * 64},
            SimpleNamespace(),
        ),
    )
    monkeypatch.setattr(
        release,
        "validate_preactivation_clock_proof",
        lambda **_kwargs: {"receipt_digest": "sha256:" + "8" * 64},
    )
    no_effect_preparation: list[str] = []
    monkeypatch.setattr(
        release,
        "publish_runtime_binding_activation",
        lambda **_kwargs: no_effect_preparation.append("runtime-binding") or {},
    )
    monkeypatch.setattr(
        release,
        "finalize_disabled_runtime_staging",
        lambda **_kwargs: no_effect_preparation.append("runtime-staging") or {},
    )
    monkeypatch.setattr(
        release,
        "refresh_predispatch",
        lambda **_kwargs: no_effect_preparation.append("predispatch-refresh") or {},
    )
    monkeypatch.setattr(
        release,
        "_require_loopback_ports_free",
        lambda: (_ for _ in ()).throw(
            release.ReleaseContractError(
                "campaign loopback port 18420 is already occupied"
            )
        ),
    )
    systemd_calls: list[tuple[str, ...]] = []

    def runner(argv, **_kwargs):  # noqa: ANN001, ANN202
        systemd_calls.append(tuple(argv))
        return subprocess.CompletedProcess(argv, 0, "", "")

    if replay:
        with pytest.raises(release.ReleaseContractError, match="schema differs"):
            release.activate_predispatch(
                role="writer",
                release_sha="a" * 40,
                receipt_path=receipt,
                intent_path=intent,
                runner=runner,
                now=datetime(2026, 8, 23, 1, tzinfo=timezone.utc),
                observed_node=release.WRITER_NODE,
                expected_root_uid=os.geteuid(),
                expected_root_gid=os.getegid(),
            )
        assert no_effect_preparation == []
        assert systemd_calls == []
        assert not intent.exists()
        assert not writer.exists()
        return

    with pytest.raises(release.ReleaseContractError, match="18420.*occupied"):
        release.activate_predispatch(
            role="writer",
            release_sha="a" * 40,
            receipt_path=receipt,
            intent_path=intent,
            runner=runner,
            now=datetime(2026, 8, 23, 1, tzinfo=timezone.utc),
            observed_node=release.WRITER_NODE,
            expected_root_uid=os.geteuid(),
            expected_root_gid=os.getegid(),
        )
    assert no_effect_preparation == [
        "runtime-binding",
        "runtime-staging",
        "predispatch-refresh",
    ]
    assert systemd_calls == []
    assert not intent.exists()
    assert not writer.exists()


def test_activation_refuses_to_replace_existing_tailscale_serve() -> None:
    def empty(argv, **kwargs):  # noqa: ANN001, ANN202
        if tuple(argv)[1:] == ("version",):
            return subprocess.CompletedProcess(
                argv, 0, f"{release.TAILSCALE_VERSION}\n", ""
            )
        payload = (
            release.TAILSCALE_EMPTY_CONFIG
            if tuple(argv)[1:3] == ("serve", "get-config")
            else {}
        )
        return subprocess.CompletedProcess(argv, 0, json.dumps(payload), "")

    release._require_empty_tailscale_serve(runner=empty)

    def wrong_version(argv, **kwargs):  # noqa: ANN001, ANN202
        if tuple(argv)[1:] == ("version",):
            return subprocess.CompletedProcess(argv, 0, "1.102.3\n", "")
        return empty(argv, **kwargs)

    with pytest.raises(release.ReleaseContractError, match="version differs"):
        release._require_empty_tailscale_serve(runner=wrong_version)

    def occupied(argv, **kwargs):  # noqa: ANN001, ANN202
        if tuple(argv)[1:] == ("version",):
            return subprocess.CompletedProcess(
                argv, 0, f"{release.TAILSCALE_VERSION}\n", ""
            )
        payload = (
            release.TAILSCALE_EMPTY_CONFIG
            if tuple(argv)[1:3] == ("serve", "get-config")
            else {"Web": {}}
        )
        return subprocess.CompletedProcess(argv, 0, json.dumps(payload), "")

    with pytest.raises(release.ReleaseContractError, match="preserving"):
        release._require_empty_tailscale_serve(runner=occupied)


def _owned_tailscale_config(proxy: str = release.TAILSCALE_ROUTE) -> dict:
    return {
        "TCP": {"443": {"HTTPS": True}},
        "Web": {
            "meghadharma-cloud.example.ts.net:443": {
                "Handlers": {"/": {"Proxy": proxy}}
            }
        },
    }


def _write_tailscale_intent(path: Path, release_sha: str) -> dict[str, object]:
    return _write_self_digest_receipt(
        path,
        {
            "schema_version": release.TAILSCALE_INTENT_SCHEMA_VERSION,
            "campaign_id": release.MISSION_ID,
            "release_sha": release_sha,
            "route": release.TAILSCALE_ROUTE,
            "tailscale_version": release.TAILSCALE_VERSION,
            "serve_status_before_sha256": release._tailscale_config_digest({}),
            "named_config_before_sha256": release._tailscale_config_digest(
                release.TAILSCALE_EMPTY_CONFIG
            ),
            "effect_intent": "InfrastructureEffect",
            "receipt_digest": "",
        },
    )


def test_tailscale_start_records_exact_owned_config(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    os.chmod(tmp_path, 0o700)
    release_sha = "a" * 40
    receipt = tmp_path / "owned.json"
    intent_path = tmp_path / "intent.json"
    stop_receipt = tmp_path / "stopped.json"
    owned = _owned_tailscale_config()
    statuses = iter(({}, owned))
    calls: list[tuple[str, ...]] = []

    def runner(argv, **kwargs):  # noqa: ANN001, ANN202
        command = tuple(argv)
        calls.append(command)
        if command[1:] == ("version",):
            return subprocess.CompletedProcess(
                argv, 0, f"{release.TAILSCALE_VERSION}\n", ""
            )
        if command[1:3] == ("serve", "get-config"):
            payload = release.TAILSCALE_EMPTY_CONFIG
        elif command[1:3] == ("serve", "status"):
            payload = next(statuses)
        else:
            if command[1:3] == ("serve", "--bg"):
                assert intent_path.exists()
                assert not receipt.exists()
            return subprocess.CompletedProcess(argv, 0, "", "")
        return subprocess.CompletedProcess(argv, 0, json.dumps(payload), "")

    monkeypatch.setattr(
        release,
        "_wait_for_dashboard_ingress",
        lambda **_kwargs: {"status": "ready"},
    )
    digest = release.tailscale_start(
        release_sha=release_sha,
        runner=runner,
        receipt_path=receipt,
        intent_path=intent_path,
        stop_receipt_path=stop_receipt,
        now=datetime(2026, 8, 23, tzinfo=timezone.utc),
        observed_node=release.WRITER_NODE,
        expected_root_uid=os.geteuid(),
        expected_root_gid=os.getegid(),
    )
    payload = json.loads(receipt.read_text(encoding="ascii"))
    assert digest == payload["config_sha256"]
    assert payload["config"] == owned
    assert payload["intent_receipt_digest"] == json.loads(
        intent_path.read_text(encoding="ascii")
    )["receipt_digest"]
    assert stat.S_IMODE(receipt.stat().st_mode) == 0o600
    assert (
        release.TAILSCALE_PATH,
        "serve",
        "--bg",
        "--https=443",
        release.TAILSCALE_ROUTE,
    ) in calls


def test_tailscale_start_finalizes_intended_effect_after_crash(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    os.chmod(tmp_path, 0o700)
    release_sha = "a" * 40
    intent_path = tmp_path / "intent.json"
    receipt = tmp_path / "owned.json"
    stop_receipt = tmp_path / "stopped.json"
    _write_tailscale_intent(intent_path, release_sha)
    owned = _owned_tailscale_config()
    calls: list[tuple[str, ...]] = []

    def runner(argv, **_kwargs):  # noqa: ANN001, ANN202
        command = tuple(argv)
        calls.append(command)
        if command[1:] == ("version",):
            return subprocess.CompletedProcess(
                argv, 0, f"{release.TAILSCALE_VERSION}\n", ""
            )
        payload = (
            release.TAILSCALE_EMPTY_CONFIG
            if command[1:3] == ("serve", "get-config")
            else owned
        )
        return subprocess.CompletedProcess(argv, 0, json.dumps(payload), "")

    monkeypatch.setattr(
        release,
        "_wait_for_dashboard_ingress",
        lambda **_kwargs: {"status": "ready"},
    )
    digest = release.tailscale_start(
        release_sha=release_sha,
        runner=runner,
        receipt_path=receipt,
        intent_path=intent_path,
        stop_receipt_path=stop_receipt,
        now=datetime(2026, 8, 23, tzinfo=timezone.utc),
        observed_node=release.WRITER_NODE,
        expected_root_uid=os.geteuid(),
        expected_root_gid=os.getegid(),
    )
    assert digest == release._tailscale_config_digest(owned)
    assert receipt.exists()
    assert not any(command[1:3] == ("serve", "--bg") for command in calls)


def test_tailscale_stop_resets_only_exact_owned_config(tmp_path: Path) -> None:
    os.chmod(tmp_path, 0o700)
    release_sha = "a" * 40
    receipt = tmp_path / "owned.json"
    intent_path = tmp_path / "intent.json"
    stop_receipt = tmp_path / "stopped.json"
    owned = _owned_tailscale_config()
    intent = _write_tailscale_intent(intent_path, release_sha)
    ownership = release._write_tailscale_ownership_receipt(
        receipt,
        owned,
        release_sha=release_sha,
        intent=intent,
        expected_root_uid=os.geteuid(),
        expected_root_gid=os.getegid(),
    )
    statuses = iter((owned, {}))
    calls: list[tuple[str, ...]] = []

    def runner(argv, **kwargs):  # noqa: ANN001, ANN202
        command = tuple(argv)
        calls.append(command)
        if command[1:] == ("version",):
            return subprocess.CompletedProcess(
                argv, 0, f"{release.TAILSCALE_VERSION}\n", ""
            )
        if command[1:3] == ("serve", "get-config"):
            payload = release.TAILSCALE_EMPTY_CONFIG
        elif command[1:3] == ("serve", "status"):
            payload = next(statuses)
        else:
            return subprocess.CompletedProcess(argv, 0, "", "")
        return subprocess.CompletedProcess(argv, 0, json.dumps(payload), "")

    release.tailscale_stop(
        release_sha=release_sha,
        runner=runner,
        receipt_path=receipt,
        intent_path=intent_path,
        stop_receipt_path=stop_receipt,
        observed_node=release.WRITER_NODE,
        expected_root_uid=os.geteuid(),
        expected_root_gid=os.getegid(),
    )
    assert (release.TAILSCALE_PATH, "serve", "reset") in calls
    assert receipt.exists()
    stopped = json.loads(stop_receipt.read_text(encoding="ascii"))
    assert stopped["ownership_receipt_digest"] == ownership["receipt_digest"]

    def replay_runner(argv, **_kwargs):  # noqa: ANN001, ANN202
        command = tuple(argv)
        if command[1:] == ("version",):
            return subprocess.CompletedProcess(
                argv, 0, f"{release.TAILSCALE_VERSION}\n", ""
            )
        payload = (
            release.TAILSCALE_EMPTY_CONFIG
            if command[1:3] == ("serve", "get-config")
            else {}
        )
        return subprocess.CompletedProcess(argv, 0, json.dumps(payload), "")

    release.tailscale_stop(
        release_sha=release_sha,
        runner=replay_runner,
        receipt_path=receipt,
        intent_path=intent_path,
        stop_receipt_path=stop_receipt,
        observed_node=release.WRITER_NODE,
        expected_root_uid=os.geteuid(),
        expected_root_gid=os.getegid(),
    )
    assert json.loads(stop_receipt.read_text(encoding="ascii")) == stopped


def test_tailscale_stop_preserves_drifted_or_public_config(tmp_path: Path) -> None:
    os.chmod(tmp_path, 0o700)
    release_sha = "a" * 40
    receipt = tmp_path / "owned.json"
    intent_path = tmp_path / "intent.json"
    stop_receipt = tmp_path / "stopped.json"
    owned = _owned_tailscale_config()
    intent = _write_tailscale_intent(intent_path, release_sha)
    release._write_tailscale_ownership_receipt(
        receipt,
        owned,
        release_sha=release_sha,
        intent=intent,
        expected_root_uid=os.geteuid(),
        expected_root_gid=os.getegid(),
    )
    drifted = _owned_tailscale_config("http://127.0.0.1:3001")
    calls: list[tuple[str, ...]] = []

    def runner(argv, **kwargs):  # noqa: ANN001, ANN202
        calls.append(tuple(argv))
        if tuple(argv)[1:] == ("version",):
            return subprocess.CompletedProcess(
                argv, 0, f"{release.TAILSCALE_VERSION}\n", ""
            )
        payload = (
            release.TAILSCALE_EMPTY_CONFIG
            if tuple(argv)[1:3] == ("serve", "get-config")
            else drifted
        )
        return subprocess.CompletedProcess(argv, 0, json.dumps(payload), "")

    with pytest.raises(release.ReleaseContractError, match="pinned proxy"):
        release.tailscale_stop(
            release_sha=release_sha,
            runner=runner,
            receipt_path=receipt,
            intent_path=intent_path,
            stop_receipt_path=stop_receipt,
            observed_node=release.WRITER_NODE,
            expected_root_uid=os.geteuid(),
            expected_root_gid=os.getegid(),
        )
    assert not any(command[1:3] == ("serve", "reset") for command in calls)
    assert receipt.exists()

    calls.clear()

    def named_service(argv, **kwargs):  # noqa: ANN001, ANN202
        calls.append(tuple(argv))
        if tuple(argv)[1:] == ("version",):
            return subprocess.CompletedProcess(
                argv, 0, f"{release.TAILSCALE_VERSION}\n", ""
            )
        payload = (
            {
                "version": "0.0.1",
                "services": {
                    "svc:foreign": {"endpoints": {"tcp:443": "http://127.0.0.1:9999"}}
                },
            }
            if tuple(argv)[1:3] == ("serve", "get-config")
            else owned
        )
        return subprocess.CompletedProcess(argv, 0, json.dumps(payload), "")

    with pytest.raises(release.ReleaseContractError, match="named Tailscale"):
        release.tailscale_stop(
            release_sha=release_sha,
            runner=named_service,
            receipt_path=receipt,
            intent_path=intent_path,
            stop_receipt_path=stop_receipt,
            observed_node=release.WRITER_NODE,
            expected_root_uid=os.geteuid(),
            expected_root_gid=os.getegid(),
        )
    assert not any(command[1:3] == ("serve", "reset") for command in calls)

    public = dict(owned)
    public["AllowFunnel"] = {"meghadharma-cloud.example.ts.net:443": True}
    with pytest.raises(release.ReleaseContractError, match="campaign-exclusive"):
        release._validate_owned_tailscale_config(public)

    foreign_host = _owned_tailscale_config()
    foreign_host["Web"] = {
        "foreign-node.example.ts.net:443": {
            "Handlers": {"/": {"Proxy": release.TAILSCALE_ROUTE}}
        }
    }
    with pytest.raises(release.ReleaseContractError, match="pinned proxy"):
        release._validate_owned_tailscale_config(foreign_host)


def _standby_serve_runner() -> tuple[
    dict[str, object],
    list[tuple[str, ...]],
    Callable[..., subprocess.CompletedProcess[str]],
]:
    state: dict[str, object] = {"status": {}}
    calls: list[tuple[str, ...]] = []

    def runner(argv, **_kwargs):  # noqa: ANN001, ANN202
        command = tuple(argv)
        calls.append(command)
        if command[1:] == ("version",):
            return subprocess.CompletedProcess(
                argv, 0, f"{release.TAILSCALE_VERSION}\n", ""
            )
        if command[1:3] == ("serve", "get-config"):
            return subprocess.CompletedProcess(
                argv, 0, json.dumps(release.TAILSCALE_EMPTY_CONFIG), ""
            )
        if command[1:3] == ("serve", "status"):
            return subprocess.CompletedProcess(
                argv, 0, json.dumps(state["status"]), ""
            )
        if command[1:] == (
            "serve",
            "--bg",
            "--tcp=2222",
            "tcp://localhost:22",
        ):
            state["status"] = copy.deepcopy(release.STANDBY_TAILSCALE_STATUS)
            return subprocess.CompletedProcess(argv, 0, "", "")
        if command[1:] == ("serve", "--tcp=2222", "off"):
            state["status"] = {}
            return subprocess.CompletedProcess(argv, 0, "", "")
        raise AssertionError(f"unexpected Serve command: {command!r}")

    return state, calls, runner


def test_standby_serve_owns_and_removes_only_tcp_2222_handler(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    os.chmod(tmp_path, 0o700)
    intent = tmp_path / "intent.json"
    ownership = tmp_path / "owned.json"
    stopped = tmp_path / "stopped.json"
    monkeypatch.setattr(release, "guard_campaign_clock", lambda **_kwargs: None)
    state, calls, runner = _standby_serve_runner()
    owned = release.standby_tailscale_start(
        role="standby",
        release_sha="a" * 40,
        runner=runner,
        receipt_path=ownership,
        intent_path=intent,
        stop_receipt_path=stopped,
        observed_node=release.STANDBY_NODE,
        expected_root_uid=os.geteuid(),
        expected_root_gid=os.getegid(),
    )
    assert owned["config"] == release.STANDBY_TAILSCALE_STATUS
    assert owned["end_to_end_route_verified"] is False
    assert state["status"] == release.STANDBY_TAILSCALE_STATUS
    assert (
        release.TAILSCALE_PATH,
        "serve",
        "--bg",
        "--tcp=2222",
        "tcp://localhost:22",
    ) in calls
    stop_receipt = release.standby_tailscale_stop(
        role="standby",
        release_sha="a" * 40,
        runner=runner,
        receipt_path=ownership,
        intent_path=intent,
        stop_receipt_path=stopped,
        observed_node=release.STANDBY_NODE,
        expected_root_uid=os.geteuid(),
        expected_root_gid=os.getegid(),
    )
    assert state["status"] == {}
    assert stop_receipt["owned_handler_removed"] is True
    assert (release.TAILSCALE_PATH, "serve", "--tcp=2222", "off") in calls
    assert not any(command[1:] == ("serve", "reset") for command in calls)
    effect_count = len(calls)
    assert (
        release.standby_tailscale_stop(
            role="standby",
            release_sha="a" * 40,
            runner=runner,
            receipt_path=ownership,
            intent_path=intent,
            stop_receipt_path=stopped,
            observed_node=release.STANDBY_NODE,
            expected_root_uid=os.geteuid(),
            expected_root_gid=os.getegid(),
        )
        == stop_receipt
    )
    assert not any(
        command[1:] == ("serve", "reset") for command in calls[effect_count:]
    )


def test_standby_serve_stop_preserves_drift_without_node_reset(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    os.chmod(tmp_path, 0o700)
    intent = tmp_path / "intent.json"
    ownership = tmp_path / "owned.json"
    stopped = tmp_path / "stopped.json"
    monkeypatch.setattr(release, "guard_campaign_clock", lambda **_kwargs: None)
    state, calls, runner = _standby_serve_runner()
    release.standby_tailscale_start(
        role="standby",
        release_sha="a" * 40,
        runner=runner,
        receipt_path=ownership,
        intent_path=intent,
        stop_receipt_path=stopped,
        observed_node=release.STANDBY_NODE,
        expected_root_uid=os.geteuid(),
        expected_root_gid=os.getegid(),
    )
    state["status"] = {"TCP": {"2222": {"TCPForward": "localhost:23"}}}
    with pytest.raises(release.ReleaseContractError, match="owned TCP bridge"):
        release.standby_tailscale_stop(
            role="standby",
            release_sha="a" * 40,
            runner=runner,
            receipt_path=ownership,
            intent_path=intent,
            stop_receipt_path=stopped,
            observed_node=release.STANDBY_NODE,
            expected_root_uid=os.geteuid(),
            expected_root_gid=os.getegid(),
        )
    assert not any(command[1:] == ("serve", "reset") for command in calls)
    assert not any(command[1:] == ("serve", "--tcp=2222", "off") for command in calls)


def test_root_route_probe_binds_bracketed_pin_and_forced_key_negatives(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    os.chmod(tmp_path, 0o700)
    key = tmp_path / "replication_ed25519"
    known_hosts = tmp_path / "known_hosts"
    receipt = tmp_path / "route-probe.json"
    dispatch_marker = tmp_path / "dispatch-enabled.json"
    key.write_bytes(b"private-key-fixture\n")
    key.chmod(0o600)
    bracketed = (
        b"[100.79.111.89]:2222 ssh-ed25519 "
        b"AAAAC3NzaC1lZDI1NTE5AAAAIHkJLL+DPOv8vi4//pbrEqF0HMsqWK/GLjCzErMeWd5A\n"
    )
    known_hosts.write_bytes(
        b"178.128.87.170 ssh-ed25519 "
        b"AAAAC3NzaC1lZDI1NTE5AAAAIJ3h+J/3jUWbAvgGZhfHTrU/BtNu+bz1KeVvQCc5Ho4r\n"
        b"157.245.193.15 ssh-ed25519 "
        b"AAAAC3NzaC1lZDI1NTE5AAAAIHkJLL+DPOv8vi4//pbrEqF0HMsqWK/GLjCzErMeWd5A\n"
        b"100.79.111.89 ssh-ed25519 "
        b"AAAAC3NzaC1lZDI1NTE5AAAAIHkJLL+DPOv8vi4//pbrEqF0HMsqWK/GLjCzErMeWd5A\n"
        + bracketed
    )
    known_hosts.chmod(0o600)
    monkeypatch.setattr(release, "STANDBY_REPLICATION_SSH_KEY", key)
    monkeypatch.setattr(release, "STANDBY_REPLICATION_KNOWN_HOSTS", known_hosts)
    monkeypatch.setattr(
        release, "STANDBY_REPLICATION_ROUTE_PROBE_RECEIPT", receipt
    )
    monkeypatch.setattr(release, "DISPATCH_ENABLE_MARKER", dispatch_marker)
    monkeypatch.setattr(release, "_require_secure_parent_chain", lambda _path: None)
    monkeypatch.setattr(release, "guard_campaign_clock", lambda **_kwargs: None)
    calls: list[tuple[str, ...]] = []
    ssh_transport_failure = [False]
    publish_dispatch_marker_during_probe = [False]

    def runner(argv, **_kwargs):  # noqa: ANN001, ANN202
        command = tuple(argv)
        calls.append(command)
        if command[0] == release.SSH_KEYSCAN_PATH:
            if publish_dispatch_marker_during_probe[0]:
                dispatch_marker.write_bytes(b"{}\n")
                dispatch_marker.chmod(0o600)
            return subprocess.CompletedProcess(argv, 0, bracketed.decode("ascii"), "")
        if command[0] == release.RSYNC_CLIENT_PATH:
            return subprocess.CompletedProcess(argv, 0, "", "")
        if command[0] == release.SSH_PATH:
            if ssh_transport_failure[0]:
                return subprocess.CompletedProcess(
                    argv, 255, "", "ssh: connect to host failed\n"
                )
            if command[-1] == "/usr/bin/true":
                stderr = (
                    "/usr/bin/rrsync error: SSH_ORIGINAL_COMMAND does not run rsync\n"
                )
            elif command[-1] == "rsync --server . ../escape":
                stderr = (
                    "/usr/bin/rrsync error: do not use .. in arg "
                    "(anchor the path at the root of your restricted dir)\n"
                )
            else:
                stderr = "/usr/bin/rrsync error: Not invoked via sshd\n"
            return subprocess.CompletedProcess(argv, 1, "", stderr)
        raise AssertionError(f"unexpected route probe command: {command!r}")

    observed = datetime(2026, 8, 25, 1, tzinfo=timezone.utc)
    proof = release.probe_standby_replication_route(
        role="writer",
        release_sha="a" * 40,
        standby_serve_ownership_receipt_digest="sha256:" + "b" * 64,
        ssh_key=key,
        known_hosts=known_hosts,
        receipt_path=receipt,
        runner=runner,
        now=observed,
        observed_node=release.WRITER_NODE,
        expected_root_uid=os.geteuid(),
        expected_root_gid=os.getegid(),
    )
    assert proof["route_verified"] is True
    assert proof["probe_sequence"] == 1
    assert proof["previous_receipt_digest"] is None
    assert proof["remote_state_mutation_performed"] is False
    assert proof["tailnet_port"] == 2222
    assert all(
        proof[field] is True
        for field in (
            "keyscan_host_pin_exact",
            "dry_run_rsync_succeeded",
            "arbitrary_command_rejected",
            "interactive_shell_rejected",
            "out_of_root_rsync_rejected",
        )
    )
    assert any(command[0] == release.SSH_KEYSCAN_PATH for command in calls)
    assert any("-p" in command and "2222" in command for command in calls)
    assert all("--protect-args" not in command for command in calls)
    assert any(command[-1] == "rsync --server . ../escape" for command in calls)
    assert (
        release._load_standby_replication_route_probe(
            release_sha="a" * 40,
            now=observed + timedelta(seconds=1),
            path=receipt,
            expected_root_uid=os.geteuid(),
            expected_root_gid=os.getegid(),
        )
        == proof
    )
    first_call_count = len(calls)
    renewed = release.probe_standby_replication_route(
        role="writer",
        release_sha="a" * 40,
        standby_serve_ownership_receipt_digest="sha256:" + "b" * 64,
        ssh_key=key,
        known_hosts=known_hosts,
        receipt_path=receipt,
        runner=runner,
        now=observed + timedelta(seconds=601),
        observed_node=release.WRITER_NODE,
        expected_root_uid=os.geteuid(),
        expected_root_gid=os.getegid(),
    )
    assert renewed["probe_sequence"] == 2
    assert renewed["previous_receipt_digest"] == proof["receipt_digest"]
    assert renewed["receipt_digest"] != proof["receipt_digest"]
    assert len(calls) > first_call_count

    dispatch_marker.write_bytes(b"{}\n")
    dispatch_marker.chmod(0o600)
    replay_call_count = len(calls)
    assert (
        release.probe_standby_replication_route(
            role="writer",
            release_sha="a" * 40,
            standby_serve_ownership_receipt_digest="sha256:" + "b" * 64,
            ssh_key=key,
            known_hosts=known_hosts,
            receipt_path=receipt,
            runner=runner,
            now=observed + timedelta(seconds=602),
            observed_node=release.WRITER_NODE,
            expected_root_uid=os.geteuid(),
            expected_root_gid=os.getegid(),
        )
        == renewed
    )
    assert len(calls) == replay_call_count

    marker_guard_call_count = len(calls)
    with pytest.raises(
        release.ReleaseContractError,
        match="cannot renew after dispatch authority",
    ):
        release.probe_standby_replication_route(
            role="writer",
            release_sha="a" * 40,
            standby_serve_ownership_receipt_digest="sha256:" + "b" * 64,
            ssh_key=key,
            known_hosts=known_hosts,
            receipt_path=receipt,
            runner=runner,
            now=observed + timedelta(seconds=1202),
            observed_node=release.WRITER_NODE,
            expected_root_uid=os.geteuid(),
            expected_root_gid=os.getegid(),
        )
    assert len(calls) == marker_guard_call_count
    assert json.loads(receipt.read_text(encoding="utf-8")) == renewed
    dispatch_marker.unlink()

    ssh_transport_failure[0] = True
    with pytest.raises(
        release.ReleaseContractError,
        match="forced-key policy rejection proof differs",
    ):
        release.probe_standby_replication_route(
            role="writer",
            release_sha="a" * 40,
            standby_serve_ownership_receipt_digest="sha256:" + "b" * 64,
            ssh_key=key,
            known_hosts=known_hosts,
            receipt_path=receipt,
            runner=runner,
            now=observed + timedelta(seconds=1202),
            observed_node=release.WRITER_NODE,
            expected_root_uid=os.geteuid(),
            expected_root_gid=os.getegid(),
        )
    installed_after_failure = json.loads(receipt.read_text(encoding="utf-8"))
    assert installed_after_failure == renewed

    ssh_transport_failure[0] = False
    publish_dispatch_marker_during_probe[0] = True
    with pytest.raises(
        release.ReleaseContractError,
        match="cannot renew after dispatch authority",
    ):
        release.probe_standby_replication_route(
            role="writer",
            release_sha="a" * 40,
            standby_serve_ownership_receipt_digest="sha256:" + "b" * 64,
            ssh_key=key,
            known_hosts=known_hosts,
            receipt_path=receipt,
            runner=runner,
            now=observed + timedelta(seconds=1202),
            observed_node=release.WRITER_NODE,
            expected_root_uid=os.geteuid(),
            expected_root_gid=os.getegid(),
        )
    assert json.loads(receipt.read_text(encoding="utf-8")) == renewed


def _standby_public_key_fixture() -> str:
    algorithm = b"ssh-ed25519"
    key_blob = (
        len(algorithm).to_bytes(4, "big")
        + algorithm
        + (32).to_bytes(4, "big")
        + b"x" * 32
    )
    return (
        "ssh-ed25519 " + base64.b64encode(key_blob).decode("ascii") + " snapshot-key"
    )


def test_standby_key_is_forced_to_write_only_snapshot_rrsync() -> None:
    public_key = _standby_public_key_fixture()
    rendered = release._restricted_authorized_key_bytes(public_key).decode("ascii")
    assert rendered.startswith(
        'restrict,command="/usr/bin/python3.12 /usr/bin/rrsync -wo -no-del '
        '/var/lib/dharma-sadhana/snapshot-incoming" ssh-ed25519 '
    )
    with pytest.raises(release.ReleaseContractError, match="exact ed25519"):
        release._restricted_authorized_key_bytes(
            "command=/bin/sh ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIFixture"
        )


def test_pinned_known_hosts_admits_exact_agni_tailscale_replication_target(
    tmp_path: Path,
) -> None:
    raw = (
        b"178.128.87.170 ssh-ed25519 "
        b"AAAAC3NzaC1lZDI1NTE5AAAAIJ3h+J/3jUWbAvgGZhfHTrU/BtNu+bz1KeVvQCc5Ho4r\n"
        b"157.245.193.15 ssh-ed25519 "
        b"AAAAC3NzaC1lZDI1NTE5AAAAIHkJLL+DPOv8vi4//pbrEqF0HMsqWK/GLjCzErMeWd5A\n"
        b"100.79.111.89 ssh-ed25519 "
        b"AAAAC3NzaC1lZDI1NTE5AAAAIHkJLL+DPOv8vi4//pbrEqF0HMsqWK/GLjCzErMeWd5A\n"
        b"[100.79.111.89]:2222 ssh-ed25519 "
        b"AAAAC3NzaC1lZDI1NTE5AAAAIHkJLL+DPOv8vi4//pbrEqF0HMsqWK/GLjCzErMeWd5A\n"
    )
    assert hashlib.sha256(raw).hexdigest() == release.DEPLOYMENT_KNOWN_HOSTS_SHA256
    known_hosts = tmp_path / release.DEPLOYMENT_KNOWN_HOSTS_FILE
    known_hosts.write_bytes(raw)
    known_hosts.chmod(0o600)
    assert release._read_deployment_known_hosts(known_hosts) == raw
    entries = {
        fields[0]: fields[1:]
        for line in raw.decode("ascii").splitlines()
        if (fields := line.split(" "))
    }
    assert entries["100.79.111.89"] == entries["157.245.193.15"]
    assert entries["[100.79.111.89]:2222"] == entries["157.245.193.15"]
    snapshot_unit = (
        Path(__file__).resolve().parents[1]
        / "deploy/sadhana/systemd/dharma-sadhana-snapshot-finalize.service.in"
    ).read_text(encoding="utf-8")
    assert "--standby dharma-sadhana@100.79.111.89 " in snapshot_unit
    assert "--standby-port 2222 " in snapshot_unit


def _standby_key_install_fixture(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[SimpleNamespace, Path, int]:
    root_uid = os.geteuid()
    root_gid = os.getegid()
    service_uid = root_uid if root_uid != 0 else 23145
    service_gid = root_gid if root_gid != 0 else 23145
    service_home = tmp_path / "service-home"
    service_home.mkdir(mode=0o755)
    os.chown(service_home, root_uid, root_gid)
    ssh_root = service_home / ".ssh"
    tool_root = tmp_path / "tools"
    tool_root.mkdir(mode=0o755)
    python = tool_root / "python3.12"
    rrsync = tool_root / "rrsync"
    for tool in (python, rrsync):
        tool.write_bytes(b"#!/bin/sh\nexit 0\n")
        tool.chmod(0o755)
        os.chown(tool, root_uid, root_gid)
    monkeypatch.setattr(release, "PYTHON312_PATH", str(python))
    monkeypatch.setattr(release, "RRSYNC_PATH", rrsync)
    monkeypatch.setattr(release, "STANDBY_SSH_ROOT", ssh_root)

    def ensure(path: Path, *, uid: int, gid: int, mode: int) -> None:
        path.mkdir(mode=mode, exist_ok=True)
        os.chown(path, uid, gid)
        path.chmod(mode)

    monkeypatch.setattr(release, "_ensure_host_directory", ensure)
    account = SimpleNamespace(
        pw_name="dharma-sadhana",
        pw_uid=service_uid,
        pw_gid=service_gid,
        pw_dir="/var/lib/dharma-sadhana",
        pw_shell="/bin/sh",
    )
    return account, ssh_root, root_uid


def test_standby_key_install_is_atomic_idempotent_and_writer_denied(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    account, ssh_root, root_uid = _standby_key_install_fixture(tmp_path, monkeypatch)
    public_key = _standby_public_key_fixture()
    release._install_restricted_standby_key(
        public_key,
        role="standby",
        account=account,
        expected_root_uid=root_uid,
    )
    authorized_keys = ssh_root / "authorized_keys"
    first_identity = authorized_keys.lstat()
    assert authorized_keys.read_bytes() == release._restricted_authorized_key_bytes(
        public_key
    )
    assert stat.S_IMODE(first_identity.st_mode) == 0o600
    assert first_identity.st_uid == account.pw_uid
    assert first_identity.st_gid == account.pw_gid

    release._install_restricted_standby_key(
        public_key,
        role="standby",
        account=account,
        expected_root_uid=root_uid,
    )
    assert authorized_keys.lstat().st_ino == first_identity.st_ino

    writer_root = tmp_path / "writer-home/.ssh"
    monkeypatch.setattr(release, "STANDBY_SSH_ROOT", writer_root)
    with pytest.raises(release.ReleaseContractError, match="only on standby"):
        release._install_restricted_standby_key(
            public_key,
            role="writer",
            account=account,
            expected_root_uid=root_uid,
        )
    assert not writer_root.exists()


def test_standby_key_install_rolls_back_post_publish_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    account, ssh_root, root_uid = _standby_key_install_fixture(tmp_path, monkeypatch)

    def fail_after_publish(phase: str) -> None:
        if phase == "private_bytes_post_publish":
            raise RuntimeError("simulated post-publish crash")

    with pytest.raises(RuntimeError, match="post-publish crash"):
        release._install_restricted_standby_key(
            _standby_public_key_fixture(),
            role="standby",
            account=account,
            expected_root_uid=root_uid,
            checkpoint=fail_after_publish,
        )
    assert not ssh_root.exists()


def test_deploy_finalizer_installs_route_only_for_standby(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    account = SimpleNamespace(pw_name="dharma-sadhana")
    calls: list[str] = []
    monkeypatch.setattr(
        release,
        "_install_rendered_release_units",
        lambda **_kwargs: calls.append("units"),
    )
    monkeypatch.setattr(
        release,
        "_install_restricted_standby_key",
        lambda *_args, **_kwargs: calls.append("standby-key"),
    )
    monkeypatch.setattr(
        release,
        "_start_runtime_preparation_unit",
        lambda **_kwargs: calls.append("writer-preparation"),
    )

    def runner(*_args: object, **_kwargs: object) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess([], 0, "", "")

    release._finalize_staged_candidate_host(
        target=tmp_path / "release",
        release_sha="a" * 40,
        role="standby",
        unit_root=tmp_path / "units",
        account=account,
        standby_public_key=_standby_public_key_fixture(),
        runner=runner,
    )
    assert calls == ["units", "standby-key"]

    calls.clear()
    release._finalize_staged_candidate_host(
        target=tmp_path / "release",
        release_sha="a" * 40,
        role="writer",
        unit_root=tmp_path / "units",
        account=account,
        standby_public_key=None,
        runner=runner,
    )
    assert calls == ["units", "writer-preparation"]

    calls.clear()
    with pytest.raises(release.ReleaseContractError, match="writer cannot receive"):
        release._finalize_staged_candidate_host(
            target=tmp_path / "release",
            release_sha="a" * 40,
            role="writer",
            unit_root=tmp_path / "units",
            account=account,
            standby_public_key=_standby_public_key_fixture(),
            runner=runner,
        )
    assert calls == []
    stage_source = inspect.getsource(release.stage_candidate)
    assert "standby_public_key = _read_standby_public_key()" in stage_source
    assert stage_source.count("_finalize_staged_candidate_host(") == 2


def _write_minimal_venv(root: Path) -> Path:
    venv = root / "venv"
    (venv / "bin").mkdir(parents=True)
    python = venv / "bin" / "python"
    python.write_text("#!/bin/sh\nprintf 'Python 3.12.9\\n'\n", encoding="utf-8")
    python.chmod(0o755)
    return venv


def _force_linux_symlink_lstat(
    monkeypatch: pytest.MonkeyPatch,
    *,
    foreign_path: Path | None = None,
) -> None:
    """Expose Linux's 0777 symlink mode even when tests run on macOS."""
    actual_lstat = Path.lstat

    def linux_symlink_lstat(path: Path) -> os.stat_result:
        identity = actual_lstat(path)
        if not stat.S_ISLNK(identity.st_mode):
            return identity
        fields = list(identity)
        fields[stat.ST_MODE] = stat.S_IFLNK | 0o777
        if path == foreign_path:
            fields[stat.ST_UID] = identity.st_uid + 1
        return os.stat_result(fields)

    monkeypatch.setattr(Path, "lstat", linux_symlink_lstat)


def test_venv_accepts_internal_relative_links_with_linux_symlink_modes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    venv = _write_minimal_venv(tmp_path)
    package = venv / "lib" / "package"
    package.mkdir(parents=True)
    resource = package / "resource.txt"
    resource.write_text("inside\n", encoding="utf-8")
    file_link = venv / "resource-link"
    file_link.symlink_to(Path("lib") / "package" / "resource.txt")
    directory_link = venv / "lib-current"
    directory_link.symlink_to("lib", target_is_directory=True)
    _force_linux_symlink_lstat(monkeypatch)

    assert stat.S_IMODE(file_link.lstat().st_mode) == 0o777
    assert stat.S_IMODE(directory_link.lstat().st_mode) == 0o777
    release.verify_venv(venv, execute_version=False)


@pytest.mark.parametrize("target_kind", ("escaping", "broken"))
def test_venv_rejects_escaping_and_broken_links_with_containment_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    target_kind: str,
) -> None:
    venv = _write_minimal_venv(tmp_path)
    target = Path("missing")
    if target_kind == "escaping":
        outside = tmp_path / "outside"
        outside.write_text("outside\n", encoding="utf-8")
        target = Path("..") / outside.name
    hostile_link = venv / "hostile-link"
    hostile_link.symlink_to(target)
    _force_linux_symlink_lstat(monkeypatch)

    with pytest.raises(
        release.ReleaseContractError,
        match=r"venv link escapes or is broken: hostile-link",
    ):
        release.verify_venv(venv, execute_version=False)


def test_venv_rejects_group_writable_regular_file(tmp_path: Path) -> None:
    venv = _write_minimal_venv(tmp_path)
    group_writable = venv / "mutable.txt"
    group_writable.write_text("mutable\n", encoding="utf-8")
    group_writable.chmod(0o660)

    with pytest.raises(
        release.ReleaseContractError,
        match="venv tree lacks owner-only write custody",
    ):
        release.verify_venv(venv, execute_version=False)


def test_uv_venv_lock_custody_normalizes_exact_empty_lock_and_replays(
    tmp_path: Path,
) -> None:
    venv = tmp_path / ".venv"
    venv.mkdir(mode=0o700)
    lock = venv / ".lock"
    lock.write_bytes(b"")
    lock.chmod(0o666)

    release._normalize_uv_venv_lock_custody(
        venv,
        expected_uid=os.geteuid(),
        expected_gid=os.getegid(),
    )
    identity = lock.lstat()
    assert stat.S_ISREG(identity.st_mode)
    assert stat.S_IMODE(identity.st_mode) == 0o600
    assert identity.st_nlink == 1
    assert identity.st_size == 0

    release._normalize_uv_venv_lock_custody(
        venv,
        expected_uid=os.geteuid(),
        expected_gid=os.getegid(),
    )
    replayed = lock.lstat()
    assert (replayed.st_dev, replayed.st_ino) == (identity.st_dev, identity.st_ino)
    assert stat.S_IMODE(replayed.st_mode) == 0o600


@pytest.mark.parametrize(
    "hostile_kind",
    (
        "nonempty",
        "unexpected-mode",
        "hardlink",
        "symlink",
        "missing",
        "special-file",
        "foreign-owner",
        "foreign-group",
        "unexpected-root-mode",
    ),
)
def test_uv_venv_lock_custody_rejects_hostile_entries_without_normalizing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    hostile_kind: str,
) -> None:
    venv = tmp_path / ".venv"
    venv.mkdir(mode=0o700)
    lock = venv / ".lock"
    external: Path | None = None
    if hostile_kind == "missing":
        pass
    elif hostile_kind == "special-file":
        os.mkfifo(lock, mode=0o666)
    elif hostile_kind == "symlink":
        external = tmp_path / "outside-lock"
        external.write_bytes(b"")
        external.chmod(0o666)
        lock.symlink_to(external)
    elif hostile_kind == "hardlink":
        external = tmp_path / "outside-lock"
        external.write_bytes(b"")
        external.chmod(0o666)
        os.link(external, lock)
    else:
        lock.write_bytes(b"occupied" if hostile_kind == "nonempty" else b"")
        lock.chmod(0o644 if hostile_kind == "unexpected-mode" else 0o666)
    if hostile_kind == "unexpected-root-mode":
        venv.chmod(0o755)
    if hostile_kind in {"foreign-owner", "foreign-group"}:
        actual_lstat = Path.lstat

        def foreign_lock_lstat(path: Path) -> os.stat_result:
            identity = actual_lstat(path)
            if path != lock:
                return identity
            fields = list(identity)
            field = stat.ST_UID if hostile_kind == "foreign-owner" else stat.ST_GID
            fields[field] = fields[field] + 1
            return os.stat_result(fields)

        monkeypatch.setattr(Path, "lstat", foreign_lock_lstat)

    with pytest.raises(
        release.ReleaseContractError,
        match=(
            "uv venv lock is unavailable"
            if hostile_kind == "missing"
            else "uv venv lock lacks exact generated custody"
        ),
    ):
        release._normalize_uv_venv_lock_custody(
            venv,
            expected_uid=os.geteuid(),
            expected_gid=os.getegid(),
        )

    if hostile_kind == "nonempty":
        assert lock.read_bytes() == b"occupied"
    elif hostile_kind == "unexpected-mode":
        assert stat.S_IMODE(lock.lstat().st_mode) == 0o644
    elif hostile_kind == "hardlink":
        assert external is not None
        assert lock.lstat().st_nlink == 2
        assert stat.S_IMODE(external.lstat().st_mode) == 0o666
    elif hostile_kind == "symlink":
        assert external is not None
        assert lock.is_symlink()
        assert stat.S_IMODE(external.lstat().st_mode) == 0o666
    elif hostile_kind == "special-file":
        assert stat.S_ISFIFO(lock.lstat().st_mode)


def test_uv_venv_lock_custody_rejects_post_fsync_path_swap(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    venv = tmp_path / ".venv"
    venv.mkdir(mode=0o700)
    lock = venv / ".lock"
    lock.write_bytes(b"")
    lock.chmod(0o666)
    original_fsync = os.fsync
    swapped = False

    def swap_after_fsync(descriptor: int) -> None:
        nonlocal swapped
        original_fsync(descriptor)
        if swapped:
            return
        swapped = True
        lock.rename(venv / ".lock.retired")
        lock.write_bytes(b"")
        lock.chmod(0o600)

    monkeypatch.setattr(release.os, "fsync", swap_after_fsync)
    with pytest.raises(
        release.ReleaseContractError,
        match="uv venv lock normalization was not retained",
    ):
        release._normalize_uv_venv_lock_custody(
            venv,
            expected_uid=os.geteuid(),
            expected_gid=os.getegid(),
        )
    assert swapped is True


def test_uv_venv_lock_custody_rejects_busy_lock_without_normalizing(
    tmp_path: Path,
) -> None:
    venv = tmp_path / ".venv"
    venv.mkdir(mode=0o700)
    lock = venv / ".lock"
    lock.write_bytes(b"")
    lock.chmod(0o666)
    descriptor = os.open(lock, os.O_RDWR | os.O_NOFOLLOW | os.O_CLOEXEC)
    try:
        release.fcntl.flock(descriptor, release.fcntl.LOCK_EX | release.fcntl.LOCK_NB)
        with pytest.raises(
            release.ReleaseContractError,
            match="uv venv lock custody transition failed",
        ):
            release._normalize_uv_venv_lock_custody(
                venv,
                expected_uid=os.geteuid(),
                expected_gid=os.getegid(),
            )
    finally:
        release.fcntl.flock(descriptor, release.fcntl.LOCK_UN)
        os.close(descriptor)
    assert stat.S_IMODE(lock.lstat().st_mode) == 0o666


def _write_pinned_next_declaration(tmp_path: Path) -> tuple[Path, Path, Path]:
    repo = tmp_path / "repo"
    dashboard = repo / "dashboard"
    dashboard.mkdir(parents=True, mode=0o700)
    repo.chmod(0o700)
    dashboard.chmod(0o700)
    declaration = dashboard / "next-env.d.ts"
    declaration.write_bytes(release._NEXT_16_3_0_ENV_DTS)
    declaration.chmod(0o600)
    sentinel = dashboard / "sentinel"
    sentinel.write_bytes(b"retained\n")
    sentinel.chmod(0o600)
    return repo, declaration, sentinel


def test_pinned_next_declaration_removal_is_exact_and_missing_replay_rejects(
    tmp_path: Path,
) -> None:
    repo, declaration, sentinel = _write_pinned_next_declaration(tmp_path)
    dashboard = declaration.parent
    repo_before = repo.lstat()
    dashboard_before = dashboard.lstat()
    sentinel_before = sentinel.lstat()
    assert len(release._NEXT_16_3_0_ENV_DTS) == 288
    assert hashlib.sha256(release._NEXT_16_3_0_ENV_DTS).hexdigest() == (
        "1862ac4bbbc5192d4bf562161df66ea547ed3e67173100656ab606ae9797db2b"
    )

    release._remove_pinned_next_env_declaration(
        repo,
        expected_uid=os.geteuid(),
        expected_gid=os.getegid(),
    )

    assert not declaration.exists()
    assert (repo.lstat().st_dev, repo.lstat().st_ino) == (
        repo_before.st_dev,
        repo_before.st_ino,
    )
    assert (dashboard.lstat().st_dev, dashboard.lstat().st_ino) == (
        dashboard_before.st_dev,
        dashboard_before.st_ino,
    )
    assert sentinel.read_bytes() == b"retained\n"
    assert (sentinel.lstat().st_dev, sentinel.lstat().st_ino) == (
        sentinel_before.st_dev,
        sentinel_before.st_ino,
    )
    assert stat.S_IMODE(sentinel.lstat().st_mode) == 0o600

    with pytest.raises(
        release.ReleaseContractError,
        match="pinned Next declaration is unavailable",
    ):
        release._remove_pinned_next_env_declaration(
            repo,
            expected_uid=os.geteuid(),
            expected_gid=os.getegid(),
        )
    assert sentinel.read_bytes() == b"retained\n"


def test_pinned_next_declaration_rejects_post_fsync_reappearance(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo, declaration, sentinel = _write_pinned_next_declaration(tmp_path)
    original_fsync = os.fsync
    recreated = False

    def recreate_after_fsync(descriptor: int) -> None:
        nonlocal recreated
        original_fsync(descriptor)
        if recreated:
            return
        recreated = True
        declaration.write_bytes(release._NEXT_16_3_0_ENV_DTS)
        declaration.chmod(0o600)

    monkeypatch.setattr(release.os, "fsync", recreate_after_fsync)
    with pytest.raises(
        release.ReleaseContractError,
        match="pinned Next declaration removal was not retained",
    ):
        release._remove_pinned_next_env_declaration(
            repo,
            expected_uid=os.geteuid(),
            expected_gid=os.getegid(),
        )

    assert recreated is True
    assert declaration.read_bytes() == release._NEXT_16_3_0_ENV_DTS
    assert stat.S_IMODE(declaration.lstat().st_mode) == 0o600
    assert declaration.lstat().st_nlink == 1
    assert sentinel.read_bytes() == b"retained\n"


@pytest.mark.parametrize(
    "hostile_kind",
    (
        "missing",
        "symlink",
        "fifo",
        "hardlink",
        "extra-bytes",
        "altered-bytes",
        "wrong-mode",
        "foreign-owner",
        "foreign-group",
        "repo-mode",
        "dashboard-mode",
    ),
)
def test_pinned_next_declaration_rejects_hostile_entry_without_removal(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    hostile_kind: str,
) -> None:
    repo, declaration, sentinel = _write_pinned_next_declaration(tmp_path)
    dashboard = declaration.parent
    outside = tmp_path / "outside-next-env.d.ts"
    if hostile_kind == "missing":
        declaration.unlink()
    elif hostile_kind == "symlink":
        declaration.unlink()
        outside.write_bytes(release._NEXT_16_3_0_ENV_DTS)
        outside.chmod(0o600)
        declaration.symlink_to(outside)
    elif hostile_kind == "fifo":
        declaration.unlink()
        os.mkfifo(declaration, mode=0o600)
    elif hostile_kind == "hardlink":
        declaration.rename(outside)
        os.link(outside, declaration)
    elif hostile_kind == "extra-bytes":
        declaration.write_bytes(release._NEXT_16_3_0_ENV_DTS + b"x")
        declaration.chmod(0o600)
    elif hostile_kind == "altered-bytes":
        raw = bytearray(release._NEXT_16_3_0_ENV_DTS)
        raw[0] ^= 1
        declaration.write_bytes(raw)
        declaration.chmod(0o600)
    elif hostile_kind == "wrong-mode":
        declaration.chmod(0o640)
    elif hostile_kind == "repo-mode":
        repo.chmod(0o750)
    elif hostile_kind == "dashboard-mode":
        dashboard.chmod(0o750)
    elif hostile_kind in {"foreign-owner", "foreign-group"}:
        actual_lstat = Path.lstat

        def foreign_declaration_lstat(path: Path) -> os.stat_result:
            identity = actual_lstat(path)
            if path != declaration:
                return identity
            fields = list(identity)
            field = stat.ST_UID if hostile_kind == "foreign-owner" else stat.ST_GID
            fields[field] += 1
            return os.stat_result(fields)

        monkeypatch.setattr(Path, "lstat", foreign_declaration_lstat)

    sentinel_before = sentinel.lstat()
    with pytest.raises(release.ReleaseContractError):
        release._remove_pinned_next_env_declaration(
            repo,
            expected_uid=os.geteuid(),
            expected_gid=os.getegid(),
        )

    assert sentinel.read_bytes() == b"retained\n"
    assert (sentinel.lstat().st_dev, sentinel.lstat().st_ino) == (
        sentinel_before.st_dev,
        sentinel_before.st_ino,
    )
    if hostile_kind == "missing":
        assert not declaration.exists()
    elif hostile_kind == "symlink":
        assert declaration.is_symlink()
        assert outside.read_bytes() == release._NEXT_16_3_0_ENV_DTS
    elif hostile_kind == "fifo":
        assert stat.S_ISFIFO(declaration.lstat().st_mode)
    elif hostile_kind == "hardlink":
        assert declaration.lstat().st_nlink == 2
        assert outside.read_bytes() == release._NEXT_16_3_0_ENV_DTS
    else:
        assert declaration.exists()


@pytest.mark.parametrize("swap_kind", ("declaration", "dashboard"))
def test_pinned_next_declaration_rejects_named_path_swap_before_removal(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    swap_kind: str,
) -> None:
    repo, declaration, _sentinel = _write_pinned_next_declaration(tmp_path)
    dashboard = declaration.parent
    retired_declaration = dashboard / "next-env.d.ts.retired"
    retired_dashboard = repo / "dashboard.retired"
    actual_stat = os.stat
    declaration_stats = 0
    dashboard_stats = 0

    def swap_on_last_named_stat(
        path: str | bytes | os.PathLike[str] | os.PathLike[bytes],
        *args: object,
        **kwargs: object,
    ) -> os.stat_result:
        nonlocal declaration_stats, dashboard_stats
        if path == "next-env.d.ts" and kwargs.get("dir_fd") is not None:
            declaration_stats += 1
            if swap_kind == "declaration" and declaration_stats == 2:
                declaration.rename(retired_declaration)
                declaration.write_bytes(release._NEXT_16_3_0_ENV_DTS)
                declaration.chmod(0o600)
        if path == "dashboard" and kwargs.get("dir_fd") is not None:
            dashboard_stats += 1
            if swap_kind == "dashboard" and dashboard_stats == 2:
                dashboard.rename(retired_dashboard)
                dashboard.mkdir(mode=0o700)
                replacement = dashboard / "next-env.d.ts"
                replacement.write_bytes(release._NEXT_16_3_0_ENV_DTS)
                replacement.chmod(0o600)
        return actual_stat(path, *args, **kwargs)

    monkeypatch.setattr(release.os, "stat", swap_on_last_named_stat)
    with pytest.raises(
        release.ReleaseContractError,
        match="pinned Next declaration changed before removal",
    ):
        release._remove_pinned_next_env_declaration(
            repo,
            expected_uid=os.geteuid(),
            expected_gid=os.getegid(),
        )

    if swap_kind == "declaration":
        assert declaration.exists()
        assert retired_declaration.exists()
    else:
        assert (dashboard / "next-env.d.ts").exists()
        assert (retired_dashboard / "next-env.d.ts").exists()


_PINNED_UV_PKG_INFO_HEADER = (
    b"Metadata-Version: 2.4\n"
    b"Name: dharma-swarm\n"
    b"Version: 0.1.0\n"
    b"Summary: Darwin-Heuristic Autonomous Recursive Meta-Agent Swarm\n"
    b"Author-email: John Shrader <dhyana@example.com>\n"
    b"License-Expression: MIT\n"
    b"Requires-Python: >=3.11\n"
    b"Description-Content-Type: text/markdown\n"
    b"Requires-Dist: pydantic>=2.0\n"
    b"Requires-Dist: typer>=0.9\n"
    b"Requires-Dist: rich>=13.0\n"
    b"Requires-Dist: anthropic>=0.40\n"
    b"Requires-Dist: openai>=1.0\n"
    b"Requires-Dist: httpx>=0.25\n"
    b"Requires-Dist: aiosqlite>=0.19\n"
    b"Requires-Dist: aiofiles>=23.0\n"
    b"Requires-Dist: scipy>=1.11\n"
    b"Requires-Dist: textual>=0.40\n"
    b"Requires-Dist: fastapi>=0.104\n"
    b"Requires-Dist: uvicorn>=0.24\n"
    b"Requires-Dist: numpy>=1.24\n"
    b"Requires-Dist: pyyaml>=6.0\n"
    b"Requires-Dist: cryptography>=50.0.0\n"
    b"Requires-Dist: icontract>=2.6\n"
    b"Requires-Dist: croniter>=2.0\n"
    b"Provides-Extra: mcp\n"
    b'Requires-Dist: mcp>=1.28.1; extra == "mcp"\n'
    b"Provides-Extra: ingest\n"
    b'Requires-Dist: markitdown>=0.1.6; extra == "ingest"\n'
    b"Provides-Extra: dev\n"
    b'Requires-Dist: pytest>=7.0; extra == "dev"\n'
    b'Requires-Dist: pytest-asyncio>=0.21; extra == "dev"\n'
    b'Requires-Dist: pytest-cov>=4.0; extra == "dev"\n'
    b'Requires-Dist: pytest-timeout>=2.3; extra == "dev"\n'
    b'Requires-Dist: pytest-rerunfailures>=14.0; extra == "dev"\n'
    b'Requires-Dist: ruff==0.15.16; extra == "dev"\n'
    b'Requires-Dist: hypothesis>=6.100; extra == "dev"\n'
    b'Requires-Dist: mutmut>=3.5; extra == "dev"\n'
    b'Requires-Dist: scikit-learn>=1.3; extra == "dev"\n'
    b"Provides-Extra: router\n"
    b'Requires-Dist: fasttext-wheel>=0.9.2; extra == "router"\n'
    b'Requires-Dist: redis>=5.0.0; extra == "router"\n'
    b"Provides-Extra: infra\n"
    b'Requires-Dist: langgraph>=0.2.0; extra == "infra"\n'
    b'Requires-Dist: temporalio>=1.8.0; extra == "infra"\n'
    b'Requires-Dist: qdrant-client>=1.11.0; extra == "infra"\n'
    b'Requires-Dist: neo4j>=5.25.0; extra == "infra"\n'
    b"Provides-Extra: ginko\n"
    b'Requires-Dist: hmmlearn>=0.3; extra == "ginko"\n'
    b'Requires-Dist: arch>=6.0; extra == "ginko"\n'
    b'Requires-Dist: yfinance>=0.2; extra == "ginko"\n'
    b"Provides-Extra: test-oracle\n"
    b'Requires-Dist: langgraph==1.2.4; extra == "test-oracle"\n'
    b'Requires-Dist: langgraph-checkpoint==4.1.1; extra == "test-oracle"\n'
    b'Requires-Dist: langgraph-checkpoint-sqlite==3.1.0; extra == "test-oracle"\n'
    b"Provides-Extra: test-oracle-vocab\n"
    b'Requires-Dist: langchain-core==1.4.4; extra == "test-oracle-vocab"\n'
    b"\n"
)
_PINNED_UV_REQUIRES = (
    b"pydantic>=2.0\ntyper>=0.9\nrich>=13.0\nanthropic>=0.40\n"
    b"openai>=1.0\nhttpx>=0.25\naiosqlite>=0.19\naiofiles>=23.0\n"
    b"scipy>=1.11\ntextual>=0.40\nfastapi>=0.104\nuvicorn>=0.24\n"
    b"numpy>=1.24\npyyaml>=6.0\ncryptography>=50.0.0\nicontract>=2.6\n"
    b"croniter>=2.0\n\n[dev]\npytest>=7.0\npytest-asyncio>=0.21\n"
    b"pytest-cov>=4.0\npytest-timeout>=2.3\npytest-rerunfailures>=14.0\n"
    b"ruff==0.15.16\nhypothesis>=6.100\nmutmut>=3.5\nscikit-learn>=1.3\n"
    b"\n[ginko]\nhmmlearn>=0.3\narch>=6.0\nyfinance>=0.2\n"
    b"\n[infra]\nlanggraph>=0.2.0\ntemporalio>=1.8.0\n"
    b"qdrant-client>=1.11.0\nneo4j>=5.25.0\n"
    b"\n[ingest]\nmarkitdown>=0.1.6\n\n[mcp]\nmcp>=1.28.1\n"
    b"\n[router]\nfasttext-wheel>=0.9.2\nredis>=5.0.0\n"
    b"\n[test-oracle]\nlanggraph==1.2.4\nlanggraph-checkpoint==4.1.1\n"
    b"langgraph-checkpoint-sqlite==3.1.0\n"
    b"\n[test-oracle-vocab]\nlangchain-core==1.4.4\n"
)
_PINNED_UV_EGG_INFO_SPECS = {
    "PKG-INFO": (
        0o644,
        7195,
        "e00f05deb287e778feeca546a6eedddcee1118fb88327b6a460d6f6f67208a7f",
    ),
    "SOURCES.txt": (
        0o600,
        77815,
        "0d129f9b098ea385dc25e14034b69f5a893bddb22949da85d6d419a15ea7a0b7",
    ),
    "dependency_links.txt": (
        0o600,
        1,
        "01ba4719c80b6fe911b091a7c05124b64eeece964e09c058ef8f9805daca546b",
    ),
    "entry_points.txt": (
        0o600,
        86,
        "527d7eff9970fb0b5836add9c512e5d5534b0995184c01715dde354cd6c0af78",
    ),
    "requires.txt": (
        0o600,
        758,
        "e2e500aed400f5b87def500fa5d088803fc5c78e741a7bb01681aa3ec3338b60",
    ),
    "top_level.txt": (
        0o600,
        13,
        "b5fe4879c9717208fed00941fe78f2b626ec0d30a7106199fc54ad22b0f1e6d7",
    ),
}


def _pinned_uv_egg_info_bytes() -> dict[str, bytes]:
    source_root = Path(__file__).resolve().parent.parent
    readme = (source_root / "README.md").read_bytes()
    assert len(readme) == 5016
    assert hashlib.sha256(readme).hexdigest() == (
        "fe7a5e59ef2dbe04b2186faf3c5064d5fabdd6e18d8d675eddf9f7cedf5ab96c"
    )
    package_sources = [
        path.relative_to(source_root).as_posix()
        for path in (source_root / "dharma_swarm").rglob("*.py")
    ]
    test_sources = [
        path.relative_to(source_root).as_posix()
        for path in (source_root / "tests").glob("test*.py")
    ]
    assert (len(package_sources), len(test_sources)) == (1170, 998)
    source_paths = [
        "README.md",
        "pyproject.toml",
        *package_sources,
        *(f"dharma_swarm.egg-info/{name}" for name in _PINNED_UV_EGG_INFO_SPECS),
        *test_sources,
    ]
    sources = "\n".join(sorted(source_paths, key=os.path.split)).encode("ascii")
    return {
        "PKG-INFO": _PINNED_UV_PKG_INFO_HEADER + readme,
        "SOURCES.txt": sources,
        "dependency_links.txt": b"\n",
        "entry_points.txt": (
            b"[console_scripts]\n"
            b"dgc = dharma_swarm.dgc_cli:main\n"
            b"dharma-swarm = dharma_swarm.cli:app\n"
        ),
        "requires.txt": _PINNED_UV_REQUIRES,
        "top_level.txt": b"dharma_swarm\n",
    }


def _write_pinned_uv_egg_info(tmp_path: Path) -> tuple[Path, Path, Path]:
    repo = tmp_path / "repo"
    egg_root = repo / "dharma_swarm.egg-info"
    egg_root.mkdir(parents=True, mode=0o700)
    repo.chmod(0o700)
    egg_root.chmod(0o700)
    for name, raw in _pinned_uv_egg_info_bytes().items():
        path = egg_root / name
        path.write_bytes(raw)
        path.chmod(_PINNED_UV_EGG_INFO_SPECS[name][0])
    sentinel = repo / "sentinel"
    sentinel.write_bytes(b"retained\n")
    sentinel.chmod(0o600)
    return repo, egg_root, sentinel


def _identity_tree_snapshot(root: Path) -> dict[str, tuple[object, ...]]:
    snapshot: dict[str, tuple[object, ...]] = {}
    for path in (root, *root.rglob("*")):
        identity = os.lstat(path)
        payload: object = None
        if stat.S_ISREG(identity.st_mode):
            payload = path.read_bytes()
        elif stat.S_ISLNK(identity.st_mode):
            payload = os.readlink(path)
        snapshot[path.relative_to(root).as_posix()] = (
            identity.st_mode,
            identity.st_uid,
            identity.st_gid,
            identity.st_nlink,
            identity.st_size,
            identity.st_dev,
            identity.st_ino,
            payload,
        )
    return snapshot


def _force_linux_directory_nlinks(monkeypatch: pytest.MonkeyPatch) -> None:
    """APFS counts child entries in directory nlink; Linux counts child dirs."""
    actual_lstat = Path.lstat
    actual_stat = os.stat
    actual_fstat = os.fstat

    def linux_identity(identity: os.stat_result) -> os.stat_result:
        if not stat.S_ISDIR(identity.st_mode):
            return identity
        fields = list(identity)
        fields[stat.ST_NLINK] = 2
        return os.stat_result(fields)

    def linux_lstat(path: Path) -> os.stat_result:
        return linux_identity(actual_lstat(path))

    def linux_stat(
        path: str | bytes | os.PathLike[str] | os.PathLike[bytes],
        *args: object,
        **kwargs: object,
    ) -> os.stat_result:
        return linux_identity(actual_stat(path, *args, **kwargs))

    def linux_fstat(descriptor: int) -> os.stat_result:
        return linux_identity(actual_fstat(descriptor))

    monkeypatch.setattr(Path, "lstat", linux_lstat)
    monkeypatch.setattr(release.os, "stat", linux_stat)
    monkeypatch.setattr(release.os, "fstat", linux_fstat)


def test_pinned_uv_egg_info_removal_is_exact_and_missing_replay_rejects(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo, egg_root, sentinel = _write_pinned_uv_egg_info(tmp_path)
    _force_linux_directory_nlinks(monkeypatch)
    expected_specs = tuple(
        (name, *spec) for name, spec in _PINNED_UV_EGG_INFO_SPECS.items()
    )
    assert release._UV_0_11_2_EGG_INFO_FILES == expected_specs
    for name, raw in _pinned_uv_egg_info_bytes().items():
        mode, size, digest = _PINNED_UV_EGG_INFO_SPECS[name]
        assert (mode, len(raw), hashlib.sha256(raw).hexdigest()) == (
            mode,
            size,
            digest,
        )
    repo_before = repo.lstat()
    sentinel_before = sentinel.lstat()

    release._remove_pinned_uv_egg_info(
        repo,
        expected_uid=os.geteuid(),
        expected_gid=os.getegid(),
    )

    assert not egg_root.exists()
    assert (repo.lstat().st_dev, repo.lstat().st_ino) == (
        repo_before.st_dev,
        repo_before.st_ino,
    )
    assert sentinel.read_bytes() == b"retained\n"
    assert (sentinel.lstat().st_dev, sentinel.lstat().st_ino) == (
        sentinel_before.st_dev,
        sentinel_before.st_ino,
    )
    with pytest.raises(
        release.ReleaseContractError,
        match="pinned uv egg-info is unavailable",
    ):
        release._remove_pinned_uv_egg_info(
            repo,
            expected_uid=os.geteuid(),
            expected_gid=os.getegid(),
        )
    assert sentinel.read_bytes() == b"retained\n"


def test_pinned_uv_egg_info_rejects_post_parent_fsync_reappearance(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo, egg_root, sentinel = _write_pinned_uv_egg_info(tmp_path)
    _force_linux_directory_nlinks(monkeypatch)
    original_fsync = os.fsync
    fsync_calls = 0

    def recreate_after_parent_fsync(descriptor: int) -> None:
        nonlocal fsync_calls
        original_fsync(descriptor)
        fsync_calls += 1
        if fsync_calls != 2:
            return
        egg_root.mkdir(mode=0o700)
        replacement = egg_root / "replacement"
        replacement.write_bytes(b"hostile\n")
        replacement.chmod(0o600)

    monkeypatch.setattr(release.os, "fsync", recreate_after_parent_fsync)
    with pytest.raises(
        release.ReleaseContractError,
        match="pinned uv egg-info removal was not retained",
    ):
        release._remove_pinned_uv_egg_info(
            repo,
            expected_uid=os.geteuid(),
            expected_gid=os.getegid(),
        )

    assert fsync_calls == 2
    assert (egg_root / "replacement").read_bytes() == b"hostile\n"
    assert sentinel.read_bytes() == b"retained\n"


@pytest.mark.parametrize(
    "hostile_kind",
    (
        "missing-dir",
        "dir-symlink",
        "extra-file",
        "extra-dir",
        "missing-file",
        "file-symlink",
        "fifo",
        "hardlink",
        "altered-bytes",
        "wrong-mode",
        "foreign-owner",
        "repo-mode",
    ),
)
def test_pinned_uv_egg_info_rejects_hostile_tree_without_mutation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    hostile_kind: str,
) -> None:
    repo, egg_root, _sentinel = _write_pinned_uv_egg_info(tmp_path)
    _force_linux_directory_nlinks(monkeypatch)
    target = egg_root / "dependency_links.txt"
    outside = tmp_path / "outside"
    if hostile_kind == "missing-dir":
        for child in egg_root.iterdir():
            child.unlink()
        egg_root.rmdir()
    elif hostile_kind == "dir-symlink":
        egg_root.rename(outside)
        egg_root.symlink_to(outside, target_is_directory=True)
    elif hostile_kind == "extra-file":
        (egg_root / "unexpected").write_bytes(b"hostile\n")
    elif hostile_kind == "extra-dir":
        (egg_root / "unexpected").mkdir(mode=0o700)
    elif hostile_kind == "missing-file":
        target.unlink()
    elif hostile_kind == "file-symlink":
        target.unlink()
        outside.write_bytes(b"\n")
        outside.chmod(0o600)
        target.symlink_to(outside)
    elif hostile_kind == "fifo":
        target.unlink()
        os.mkfifo(target, mode=0o600)
    elif hostile_kind == "hardlink":
        target.rename(outside)
        os.link(outside, target)
    elif hostile_kind == "altered-bytes":
        target.write_bytes(b"x")
        target.chmod(0o600)
    elif hostile_kind == "wrong-mode":
        target.chmod(0o640)
    elif hostile_kind == "repo-mode":
        repo.chmod(0o750)
    elif hostile_kind == "foreign-owner":
        actual_lstat = Path.lstat

        def foreign_target_lstat(path: Path) -> os.stat_result:
            identity = actual_lstat(path)
            if path != target:
                return identity
            fields = list(identity)
            fields[stat.ST_UID] += 1
            return os.stat_result(fields)

        monkeypatch.setattr(Path, "lstat", foreign_target_lstat)

    before = _identity_tree_snapshot(tmp_path)
    with pytest.raises(release.ReleaseContractError):
        release._remove_pinned_uv_egg_info(
            repo,
            expected_uid=os.geteuid(),
            expected_gid=os.getegid(),
        )
    assert _identity_tree_snapshot(tmp_path) == before


@pytest.mark.parametrize("swap_kind", ("file", "directory"))
def test_pinned_uv_egg_info_rejects_named_path_swap_before_removal(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    swap_kind: str,
) -> None:
    repo, egg_root, sentinel = _write_pinned_uv_egg_info(tmp_path)
    _force_linux_directory_nlinks(monkeypatch)
    target = egg_root / "dependency_links.txt"
    retired_target = egg_root / "dependency_links.txt.retired"
    retired_egg = repo / "dharma_swarm.egg-info.retired"
    actual_stat = os.stat
    file_stats = 0
    directory_stats = 0

    def swap_on_last_named_stat(
        path: str | bytes | os.PathLike[str] | os.PathLike[bytes],
        *args: object,
        **kwargs: object,
    ) -> os.stat_result:
        nonlocal file_stats, directory_stats
        if path == "dependency_links.txt" and kwargs.get("dir_fd") is not None:
            file_stats += 1
            if swap_kind == "file" and file_stats == 2:
                target.rename(retired_target)
                target.write_bytes(b"\n")
                target.chmod(0o600)
        if path == "dharma_swarm.egg-info" and kwargs.get("dir_fd") is not None:
            directory_stats += 1
            if swap_kind == "directory" and directory_stats == 2:
                egg_root.rename(retired_egg)
                egg_root.mkdir(mode=0o700)
                (egg_root / "hostile").write_bytes(b"retained\n")
        return actual_stat(path, *args, **kwargs)

    monkeypatch.setattr(release.os, "stat", swap_on_last_named_stat)
    with pytest.raises(
        release.ReleaseContractError,
        match="pinned uv egg-info changed before removal",
    ):
        release._remove_pinned_uv_egg_info(
            repo,
            expected_uid=os.geteuid(),
            expected_gid=os.getegid(),
        )

    if swap_kind == "file":
        assert target.read_bytes() == b"\n"
        assert retired_target.read_bytes() == b"\n"
    else:
        assert (egg_root / "hostile").read_bytes() == b"retained\n"
        assert (retired_egg / "dependency_links.txt").read_bytes() == b"\n"
    assert sentinel.read_bytes() == b"retained\n"


def test_venv_rejects_foreign_owned_contained_symlink(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    venv = _write_minimal_venv(tmp_path)
    target = venv / "inside.txt"
    target.write_text("inside\n", encoding="utf-8")
    link = venv / "inside-link"
    link.symlink_to(target.name)
    _force_linux_symlink_lstat(monkeypatch, foreign_path=link)

    with pytest.raises(
        release.ReleaseContractError,
        match="venv tree lacks owner-only write custody",
    ):
        release.verify_venv(
            venv,
            expected_uid=os.geteuid(),
            execute_version=False,
        )


def test_venv_rejects_copied_python_symlink_and_root_symlink(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    venv = tmp_path / "venv"
    (venv / "bin").mkdir(parents=True)
    external = tmp_path / "python"
    external.write_text("#!/bin/sh\nprintf 'Python 3.12.9\\n'\n", encoding="utf-8")
    external.chmod(0o755)
    (venv / "bin" / "python").symlink_to(external)
    _force_linux_symlink_lstat(monkeypatch)

    with pytest.raises(release.ReleaseContractError, match="copied"):
        release.verify_venv(venv, execute_version=False)

    (venv / "bin" / "python").unlink()
    (venv / "bin" / "python").write_bytes(external.read_bytes())
    (venv / "bin" / "python").chmod(0o755)
    root_link = tmp_path / "linked-venv"
    root_link.symlink_to(venv, target_is_directory=True)
    with pytest.raises(release.ReleaseContractError, match="root cannot be a symlink"):
        release.verify_venv(root_link, execute_version=False)


def _write_synthetic_uv_wheel(path: Path) -> str:
    executable = bytearray(128)
    executable[:4] = b"\x7fELF"
    executable[18:20] = b">\x00"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr(release.UV_BINARY_MEMBER, bytes(executable))
    path.chmod(0o600)
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _uv_version_runner(
    argv: tuple[str, ...], **_: object
) -> subprocess.CompletedProcess[str]:
    assert argv[-1] == "--version"
    return subprocess.CompletedProcess(argv, 0, "uv 0.11.2 (x86_64-linux)\n", "")


@pytest.mark.parametrize("hostile_umask", (0o027, 0o077))
def test_hash_pinned_uv_is_copied_from_wheel_without_path_or_pip(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    hostile_umask: int,
) -> None:
    wheel = tmp_path / release.UV_WHEEL_FILE
    digest = _write_synthetic_uv_wheel(wheel)
    monkeypatch.setattr(release, "UV_WHEEL_SHA256", digest)
    previous_umask = os.umask(hostile_umask)
    try:
        binary = release.provision_pinned_uv(
            wheel,
            tooling_root=tmp_path / "tooling",
            runner=_uv_version_runner,
            execution_uid=os.geteuid(),
            execution_gid=os.getegid(),
            execute_version=True,
            system_name="Linux",
            machine="x86_64",
        )
    finally:
        os.umask(previous_umask)
    assert binary.is_file()
    assert not binary.is_symlink()
    assert binary.read_bytes().startswith(b"\x7fELF")
    assert "uv-0.11.2" in str(binary)
    assert stat.S_IMODE(binary.parent.parent.stat().st_mode) == 0o755
    assert stat.S_IMODE(binary.parent.stat().st_mode) == 0o755
    assert stat.S_IMODE(binary.stat().st_mode) == 0o755
    assert stat.S_IMODE((binary.parent.parent / "INSTALL.json").stat().st_mode) == 0o644
    assert list((tmp_path / "tooling").glob(".uv-staging-*")) == []


def test_pinned_uv_reuse_normalizes_legacy_private_modes_without_replacement(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    wheel = tmp_path / release.UV_WHEEL_FILE
    digest = _write_synthetic_uv_wheel(wheel)
    monkeypatch.setattr(release, "UV_WHEEL_SHA256", digest)
    tooling = tmp_path / "tooling"
    binary = release.provision_pinned_uv(
        wheel,
        tooling_root=tooling,
        runner=_uv_version_runner,
        system_name="Linux",
        machine="x86_64",
    )
    version_root = binary.parent.parent
    marker = version_root / "INSTALL.json"
    identities = {
        path: (path.stat().st_dev, path.stat().st_ino)
        for path in (version_root, binary.parent, binary, marker)
    }
    binary_bytes = binary.read_bytes()
    marker_bytes = marker.read_bytes()
    version_root.chmod(0o700)
    binary.parent.chmod(0o700)
    binary.chmod(0o700)
    marker.chmod(0o600)

    observed: dict[str, object] = {}

    def runner(
        argv: tuple[str, ...], **kwargs: object
    ) -> subprocess.CompletedProcess[str]:
        observed.update(kwargs)
        return subprocess.CompletedProcess(argv, 0, "uv 0.11.2\n", "")

    reused = release.provision_pinned_uv(
        wheel,
        tooling_root=tooling,
        runner=runner,
        execution_uid=os.geteuid(),
        execution_gid=os.getegid(),
        execute_version=True,
        system_name="Linux",
        machine="x86_64",
    )

    assert reused == binary
    assert binary.read_bytes() == binary_bytes
    assert marker.read_bytes() == marker_bytes
    assert {
        path: (path.stat().st_dev, path.stat().st_ino)
        for path in (version_root, binary.parent, binary, marker)
    } == identities
    assert stat.S_IMODE(version_root.stat().st_mode) == 0o755
    assert stat.S_IMODE(binary.parent.stat().st_mode) == 0o755
    assert stat.S_IMODE(binary.stat().st_mode) == 0o755
    assert stat.S_IMODE(marker.stat().st_mode) == 0o644
    assert observed["run_uid"] == os.geteuid()
    assert observed["run_gid"] == os.getegid()
    assert observed["no_new_privileges"] is True


def test_pinned_uv_reuse_rejects_hardlinked_marker_before_mode_transition(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    wheel = tmp_path / release.UV_WHEEL_FILE
    digest = _write_synthetic_uv_wheel(wheel)
    monkeypatch.setattr(release, "UV_WHEEL_SHA256", digest)
    tooling = tmp_path / "tooling"
    binary = release.provision_pinned_uv(
        wheel,
        tooling_root=tooling,
        runner=_uv_version_runner,
        system_name="Linux",
        machine="x86_64",
    )
    version_root = binary.parent.parent
    marker = version_root / "INSTALL.json"
    version_root.chmod(0o700)
    os.link(marker, tmp_path / "marker-hardlink")
    called = False

    def runner(*_args: object, **_kwargs: object) -> subprocess.CompletedProcess[str]:
        nonlocal called
        called = True
        return subprocess.CompletedProcess([], 0, "uv 0.11.2\n", "")

    with pytest.raises(release.ReleaseContractError, match="regular directory"):
        release.provision_pinned_uv(
            wheel,
            tooling_root=tooling,
            runner=runner,
            execution_uid=os.geteuid(),
            execution_gid=os.getegid(),
            execute_version=True,
            system_name="Linux",
            machine="x86_64",
        )

    assert called is False
    assert stat.S_IMODE(version_root.stat().st_mode) == 0o700


def test_pinned_uv_version_probe_is_bound_to_nonroot_identity(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    wheel = tmp_path / release.UV_WHEEL_FILE
    digest = _write_synthetic_uv_wheel(wheel)
    monkeypatch.setattr(release, "UV_WHEEL_SHA256", digest)
    observed: dict[str, object] = {}

    def runner(
        argv: tuple[str, ...], **kwargs: object
    ) -> subprocess.CompletedProcess[str]:
        observed.update(kwargs)
        return subprocess.CompletedProcess(argv, 0, "uv 0.11.2\n", "")

    release.provision_pinned_uv(
        wheel,
        tooling_root=tmp_path / "tooling",
        runner=runner,
        execution_uid=os.geteuid(),
        execution_gid=os.getegid(),
        execute_version=True,
        system_name="Linux",
        machine="x86_64",
    )
    assert observed["run_uid"] == os.geteuid()
    assert observed["run_gid"] == os.getegid()
    assert observed["no_new_privileges"] is True


def test_build_commands_and_freeze_reject_root_links_and_lingering_processes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    called = False

    def runner(*_args: object, **_kwargs: object) -> subprocess.CompletedProcess[str]:
        nonlocal called
        called = True
        return subprocess.CompletedProcess([], 0, "", "")

    root_account = SimpleNamespace(pw_uid=0, pw_gid=0)
    with pytest.raises(release.ReleaseContractError, match="cannot run as root"):
        release._run_build_command(
            runner,
            ("/usr/bin/true",),
            cwd=tmp_path,
            account=root_account,
            env={},
        )
    assert called is False

    tree = tmp_path / "tree"
    tree.mkdir(mode=0o700)
    os.chown(tree, -1, os.getegid())
    external = tmp_path / "external"
    external.write_bytes(b"outside")
    os.chown(external, -1, os.getegid())
    os.link(external, tree / "hardlink")
    with pytest.raises(release.ReleaseContractError, match="hardlinked"):
        release._freeze_release_tree(
            tree,
            build_uid=os.geteuid(),
            build_gid=os.getegid(),
            build_processes_proven_absent=True,
        )
    assert external.read_bytes() == b"outside"
    assert external.stat().st_uid == os.geteuid()

    (tree / "hardlink").unlink()
    (tree / "escape").symlink_to(external)
    with pytest.raises(release.ReleaseContractError, match="escaping"):
        release._freeze_release_tree(
            tree,
            build_uid=os.geteuid(),
            build_gid=os.getegid(),
            build_processes_proven_absent=True,
        )

    monkeypatch.setattr(release.os, "geteuid", lambda: 0)
    monkeypatch.setattr(release, "_uid_process_ids", lambda _uid: (4242,))
    build_account = SimpleNamespace(pw_uid=987, pw_gid=987)
    with pytest.raises(release.ReleaseContractError, match="live process"):
        release._invoke_isolated_build_plan(
            staging=tmp_path,
            build_account=build_account,
            uv_binary=Path("/opt/dharma-sadhana/tooling/uv-0.11.2/bin/uv"),
            build_driver=Path(
                f"/opt/dharma-sadhana/tooling/sadhana-build-driver-{'a' * 40}.py"
            ),
            manifest_path=tmp_path / "release-manifest.json",
            expected_manifest_sha256="b" * 64,
            release_sha="a" * 40,
            runner=runner,
        )
    assert called is False


def test_isolated_build_binds_precomputed_manifest_without_root_path_read(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    release_sha = "a" * 40
    manifest_digest = "b" * 64
    driver_digest = "c" * 64
    manifest_path = tmp_path / "release-manifest.json"
    systemd_run = tmp_path / "systemd-run"
    build_driver = tmp_path / f"sadhana-build-driver-{release_sha}.py"
    build_account = SimpleNamespace(pw_uid=23145, pw_gid=23146)
    expected_commands = [
        "uv-version",
        "git-clone",
        "git-checkout",
        "git-origin",
        "python-venv",
        "uv-sync",
        "npm-ci",
        "next-build",
        "venv-python-version",
        "git-verify-checkout",
        "git-verify-tracked",
        "git-metadata-removed",
    ]
    child_receipt = {
        "schema_version": "dharma.sadhana.isolated_build.v1",
        "release_sha": release_sha,
        "build_uid": build_account.pw_uid,
        "build_gid": build_account.pw_gid,
        "no_new_privileges": True,
        "solo_cgroup_process": True,
        "build_process_dumpable": False,
        "runtime_max_seconds": 1800,
        "tasks_max": 256,
        "memory_max_bytes": 4_294_967_296,
        "commands": expected_commands,
        "manifest_sha256": manifest_digest,
        "build_driver_sha256": driver_digest,
        "candidate_code_executed_as_root": False,
    }

    monkeypatch.setattr(release.os, "geteuid", lambda: 0)
    monkeypatch.setattr(release, "_uid_process_ids", lambda _uid: ())
    monkeypatch.setattr(release, "SYSTEMD_RUN_PATH", str(systemd_run))
    monkeypatch.setattr(release, "UV_TOOLING_ROOT", tmp_path)
    actual_lstat = Path.lstat

    def root_tool_lstat(path: Path) -> os.stat_result:
        if path in {systemd_run, build_driver}:
            return os.stat_result(
                (stat.S_IFREG | 0o555, 1, 1, 1, 0, 0, 1, 0, 0, 0)
            )
        return actual_lstat(path)

    monkeypatch.setattr(Path, "lstat", root_tool_lstat)
    hashed: list[Path] = []

    def admitted_hash(path: Path, *, max_bytes: int) -> str:
        hashed.append(path)
        if path == manifest_path:
            raise AssertionError("root traversed the build-owned manifest parent")
        assert path == build_driver
        assert max_bytes == release._MAX_JSON_BYTES
        return driver_digest

    monkeypatch.setattr(release, "sha256_file", admitted_hash)
    calls: list[tuple[str, ...]] = []

    def runner(
        argv: tuple[str, ...], **_kwargs: object
    ) -> subprocess.CompletedProcess[str]:
        calls.append(argv)
        return subprocess.CompletedProcess(argv, 0, json.dumps(child_receipt), "")

    receipt = release._invoke_isolated_build_plan(
        staging=tmp_path,
        build_account=build_account,
        uv_binary=Path("/opt/dharma-sadhana/tooling/uv-0.11.2/bin/uv"),
        build_driver=build_driver,
        manifest_path=manifest_path,
        expected_manifest_sha256=manifest_digest,
        release_sha=release_sha,
        runner=runner,
    )

    assert len(calls) == 1
    assert hashed == [build_driver]
    assert receipt["manifest_sha256"] == manifest_digest
    assert receipt["post_exit_build_uid_process_count"] == 0

    child_receipt["manifest_sha256"] = "d" * 64
    with pytest.raises(release.ReleaseContractError, match="receipt binding differs"):
        release._invoke_isolated_build_plan(
            staging=tmp_path,
            build_account=build_account,
            uv_binary=Path("/opt/dharma-sadhana/tooling/uv-0.11.2/bin/uv"),
            build_driver=build_driver,
            manifest_path=manifest_path,
            expected_manifest_sha256=manifest_digest,
            release_sha=release_sha,
            runner=runner,
        )
    assert len(calls) == 2
    assert hashed == [build_driver]


def test_isolated_build_manifest_custody_admits_0400_without_relaxing_private_json(
    tmp_path: Path,
) -> None:
    manifest_path = tmp_path / "release-manifest.json"
    raw = b'{"kind":"read-only-build-manifest"}\n'
    manifest_path.write_bytes(raw)
    manifest_path.chmod(0o400)

    payload, admitted_raw, _identity = release._read_exact_custodied_json(
        manifest_path,
        expected_uid=os.geteuid(),
        expected_gid=os.getegid(),
        expected_mode=0o400,
    )
    assert payload == {"kind": "read-only-build-manifest"}
    assert admitted_raw == raw
    with pytest.raises(release.ReleaseContractError, match="required custody"):
        release._secure_json(manifest_path, require_private=True)


def test_isolated_build_rejects_invalid_0400_manifest_before_lifecycle_command(
    tmp_path: Path,
) -> None:
    staging = tmp_path / "staging"
    staging.mkdir(mode=0o700)
    bundle = staging / "candidate.bundle"
    bundle.write_bytes(b"invalid bundle bytes are not reached\n")
    bundle.chmod(0o400)
    manifest_path = staging / "release-manifest.json"
    manifest_path.write_bytes(b'{"schema_version":"invalid"}\n')
    manifest_path.chmod(0o400)
    calls: list[tuple[str, ...]] = []

    def runner(
        argv: tuple[str, ...], **_kwargs: object
    ) -> subprocess.CompletedProcess[str]:
        calls.append(argv)
        return subprocess.CompletedProcess(argv, 0, "", "")

    with pytest.raises(release.ReleaseContractError, match="manifest fields differ"):
        release.execute_isolated_build_plan(
            staging=staging,
            bundle=bundle,
            manifest_path=manifest_path,
            uv_binary=Path(
                f"/opt/dharma-sadhana/tooling/uv-{release.UV_VERSION}/bin/uv"
            ),
            release_sha="a" * 40,
            expected_uid=os.geteuid(),
            expected_gid=os.getegid(),
            runner=runner,
        )

    assert calls == []


def test_isolated_build_uses_stdlib_copied_venv_and_exact_ledger(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    staging = tmp_path / "staging"
    staging.mkdir(mode=0o700)
    bundle = staging / "candidate.bundle"
    bundle.write_bytes(b"runner fixture\n")
    bundle.chmod(0o400)
    manifest_path = staging / "release-manifest.json"
    manifest_path.write_bytes(release._canonical_bytes(_payload()) + b"\n")
    manifest_path.chmod(0o400)
    for name in ("build-home", "uv-cache", "npm-cache"):
        (staging / name).mkdir(mode=0o700)

    monkeypatch.setattr(release, "_make_build_process_undumpable", lambda: None)
    lifecycle_events: list[object] = []
    monkeypatch.setattr(
        release,
        "_require_solo_hardened_build_process",
        lambda: lifecycle_events.append("solo-process-proof"),
    )
    venv_roots: list[Path] = []

    def verify_dashboard(_root: Path) -> None:
        lifecycle_events.append("trusted-dashboard-read")

    def normalize_venv_lock(root: Path, **_kwargs: object) -> None:
        lifecycle_events.append("normalize-lock")
        venv_roots.append(root)

    def remove_next_declaration(root: Path, **_kwargs: object) -> None:
        lifecycle_events.append("remove-next-declaration")
        assert root == staging / "repo"

    def remove_egg_info(root: Path, **_kwargs: object) -> None:
        lifecycle_events.append("remove-egg-info")
        assert root == staging / "repo"

    def verify_venv(root: Path, **_kwargs: object) -> None:
        lifecycle_events.append("trusted-venv-read")
        venv_roots.append(root)

    def verify_checkout(*_args: object, **_kwargs: object) -> None:
        lifecycle_events.append("trusted-checkout-read")

    def verify_tracked_checkout(*_args: object, **_kwargs: object) -> None:
        lifecycle_events.append("trusted-tracked-read")

    def hash_driver(*_args: object, **_kwargs: object) -> str:
        lifecycle_events.append("trusted-driver-hash")
        return "a" * 64

    actual_rmtree = shutil.rmtree

    def remove_git_metadata(path: Path) -> None:
        lifecycle_events.append("git-metadata-rmtree")
        actual_rmtree(path)

    monkeypatch.setattr(release, "verify_dashboard_build", verify_dashboard)
    monkeypatch.setattr(
        release, "_normalize_uv_venv_lock_custody", normalize_venv_lock
    )
    monkeypatch.setattr(
        release,
        "_remove_pinned_next_env_declaration",
        remove_next_declaration,
    )
    monkeypatch.setattr(release, "_remove_pinned_uv_egg_info", remove_egg_info)
    monkeypatch.setattr(release, "verify_venv", verify_venv)
    monkeypatch.setattr(release, "verify_checkout", verify_checkout)
    monkeypatch.setattr(release, "verify_tracked_checkout", verify_tracked_checkout)
    monkeypatch.setattr(release, "sha256_file", hash_driver)
    monkeypatch.setattr(release.shutil, "rmtree", remove_git_metadata)

    uv_binary = Path(
        f"/opt/dharma-sadhana/tooling/uv-{release.UV_VERSION}/bin/uv"
    )
    calls: list[tuple[str, ...]] = []

    def runner(
        argv: tuple[str, ...], **_kwargs: object
    ) -> subprocess.CompletedProcess[str]:
        command = tuple(argv)
        calls.append(command)
        lifecycle_events.append(command)
        if command[:3] == (release.GIT_PATH, "clone", "--no-checkout"):
            repo = staging / "repo"
            repo.mkdir()
            (repo / ".git").mkdir()
        stdout = ""
        if command == (str(uv_binary), "--version"):
            stdout = f"uv {release.UV_VERSION}\n"
        elif command == (str(staging / "repo/.venv/bin/python"), "--version"):
            stdout = "Python 3.12.3\n"
        return subprocess.CompletedProcess(command, 0, stdout, "")

    receipt = release.execute_isolated_build_plan(
        staging=staging,
        bundle=bundle,
        manifest_path=manifest_path,
        uv_binary=uv_binary,
        release_sha="1" * 40,
        expected_uid=os.geteuid(),
        expected_gid=os.getegid(),
        runner=runner,
    )

    python_venv = (
        release.PYTHON312_PATH,
        "-m",
        "venv",
        "--copies",
        ".venv",
    )
    assert calls.count(python_venv) == 1
    assert not any(command[:2] == (str(uv_binary), "venv") for command in calls)
    assert calls[-4:] == [
        (str(uv_binary), "sync", "--active", "--frozen", "--no-dev"),
        (
            release.NPM_PATH,
            "ci",
            "--legacy-peer-deps",
            "--no-audit",
            "--no-fund",
        ),
        (release.NPM_PATH, "run", "build"),
        (str(staging / "repo/.venv/bin/python"), "--version"),
    ]
    assert lifecycle_events == [
        *calls,
        "solo-process-proof",
        "normalize-lock",
        "trusted-dashboard-read",
        "trusted-venv-read",
        "trusted-driver-hash",
        "trusted-driver-hash",
        "trusted-checkout-read",
        "trusted-tracked-read",
        "solo-process-proof",
        "remove-next-declaration",
        "remove-egg-info",
        "git-metadata-rmtree",
        "trusted-driver-hash",
        "trusted-driver-hash",
    ]
    assert venv_roots == [staging / "repo/.venv"] * 2
    assert receipt["commands"] == [
        "uv-version",
        "git-clone",
        "git-checkout",
        "git-origin",
        "python-venv",
        "uv-sync",
        "npm-ci",
        "next-build",
        "venv-python-version",
        "git-verify-checkout",
        "git-verify-tracked",
        "git-metadata-removed",
    ]


def test_artifact_hash_custody_still_rejects_a_foreign_owned_parent(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    foreign = tmp_path / "foreign"
    foreign.mkdir(mode=0o700)
    artifact = foreign / "artifact.json"
    artifact.write_bytes(b"{}\n")
    artifact.chmod(0o600)
    actual_lstat = Path.lstat

    def foreign_parent_lstat(path: Path) -> os.stat_result:
        identity = actual_lstat(path)
        if path != foreign:
            return identity
        fields = list(identity)
        fields[stat.ST_UID] = os.geteuid() + 1
        return os.stat_result(fields)

    monkeypatch.setattr(Path, "lstat", foreign_parent_lstat)
    with pytest.raises(release.ReleaseContractError, match="parent lacks secure custody"):
        release.sha256_file(artifact)


def test_build_manifest_is_revalidated_only_after_root_custody_barrier(
    tmp_path: Path,
) -> None:
    staging = tmp_path / "staging"
    staging.mkdir(mode=0o700)
    manifest = staging / "release-manifest.json"
    expected_raw = b'{"release_sha":"' + (b"a" * 40) + b'"}\n'
    expected_sha256 = hashlib.sha256(expected_raw).hexdigest()
    manifest.write_bytes(expected_raw)
    manifest.chmod(0o400)
    uid = os.geteuid()
    gid = os.getegid()

    release._admit_build_manifest_after_custody_barrier(
        manifest,
        expected_raw=expected_raw,
        expected_sha256=expected_sha256,
        build_uid=uid,
        build_gid=gid,
        expected_root_uid=uid,
        expected_root_gid=gid,
    )

    manifest.chmod(0o600)
    manifest.write_bytes(expected_raw.replace(b"a", b"b"))
    manifest.chmod(0o400)
    with pytest.raises(release.ReleaseContractError, match="differs after"):
        release._admit_build_manifest_after_custody_barrier(
            manifest,
            expected_raw=expected_raw,
            expected_sha256=expected_sha256,
            build_uid=uid,
            build_gid=gid,
            expected_root_uid=uid,
            expected_root_gid=gid,
        )

    manifest.chmod(0o600)
    manifest.write_bytes(expected_raw)
    manifest.chmod(0o400)
    staging.chmod(0o755)
    with pytest.raises(release.ReleaseContractError, match="root custody barrier"):
        release._admit_build_manifest_after_custody_barrier(
            manifest,
            expected_raw=expected_raw,
            expected_sha256=expected_sha256,
            build_uid=uid,
            build_gid=gid,
            expected_root_uid=uid,
            expected_root_gid=gid,
        )

    staging.chmod(0o700)
    os.link(manifest, staging / "manifest-hardlink")
    with pytest.raises(release.ReleaseContractError, match="file scope differs"):
        release._admit_build_manifest_after_custody_barrier(
            manifest,
            expected_raw=expected_raw,
            expected_sha256=expected_sha256,
            build_uid=uid,
            build_gid=gid,
            expected_root_uid=uid,
            expected_root_gid=gid,
        )


def test_failed_build_staging_custody_is_preserved_until_process_absence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    staging = tmp_path / "failed-staging"
    staging.mkdir(mode=0o700)
    uid = os.geteuid()
    gid = os.getegid()

    monkeypatch.setattr(release, "_uid_process_ids", lambda _uid: (4242,))
    with pytest.raises(release.ReleaseContractError, match="process remains"):
        release._cleanup_build_staging(
            staging,
            build_uid=uid,
            build_gid=gid,
            expected_root_uid=uid,
            expected_root_gid=gid,
        )
    assert staging.is_dir()

    monkeypatch.setattr(release, "_uid_process_ids", lambda _uid: ())
    staging.chmod(0o755)
    with pytest.raises(release.ReleaseContractError, match="custody changed"):
        release._cleanup_build_staging(
            staging,
            build_uid=uid,
            build_gid=gid,
            expected_root_uid=uid,
            expected_root_gid=gid,
        )
    assert staging.is_dir()

    staging.chmod(0o700)
    release._cleanup_build_staging(
        staging,
        build_uid=uid,
        build_gid=gid,
        expected_root_uid=uid,
        expected_root_gid=gid,
    )
    assert not staging.exists()


def test_candidate_git_helpers_and_staging_custody_never_execute_as_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init")
    marker = tmp_path / "helper-ran"
    helper = tmp_path / "hostile-fsmonitor"
    helper.write_text(f"#!/bin/sh\ntouch '{marker}'\nexit 0\n", encoding="utf-8")
    helper.chmod(0o700)
    _git(repo, "config", "core.fsmonitor", str(helper))

    assert release._git(repo, "status", "--porcelain=v1") == ""
    assert not marker.exists()

    monkeypatch.setattr(release.os, "geteuid", lambda: 0)
    with pytest.raises(release.ReleaseContractError, match="Git execution as root"):
        release._git(repo, "status", "--porcelain=v1")
    with pytest.raises(release.ReleaseContractError, match="cannot run as root"):
        release.verify_bundle_checkout(tmp_path / "candidate.bundle", _payload())
    assert not marker.exists()

    stage_source = inspect.getsource(release.stage_candidate)
    assert "verify_checkout(repo" not in stage_source
    assert "verify_tracked_checkout(repo" not in stage_source
    manifest_write = stage_source.index("_atomic_private_bytes(")
    handoff = stage_source.index("os.chown(staging, build_account.pw_uid")
    isolated_build = stage_source.index("_invoke_isolated_build_plan(")
    custody_barrier = stage_source.index("_retake_build_staging_custody(")
    post_barrier_admission = stage_source.index(
        "_admit_build_manifest_after_custody_barrier("
    )
    assert (
        manifest_write
        < handoff
        < isolated_build
        < custody_barrier
        < post_barrier_admission
    )
    assert "_cleanup_build_staging(" in stage_source
    assert "_rename_noreplace_at(" in stage_source
    assert "execution_uid=build_account.pw_uid" in stage_source
    assert "execution_gid=build_account.pw_gid" in stage_source
    assert "execute_version=True" in stage_source
    build_plan_source = inspect.getsource(release.execute_isolated_build_plan)
    assert "load_manifest(" not in build_plan_source
    assert "_read_exact_custodied_json(" in build_plan_source
    assert "expected_mode=0o400" in build_plan_source
    isolated_source = inspect.getsource(release._invoke_isolated_build_plan)
    assert "sha256_file(manifest_path" not in isolated_source
    assert '"--property=RuntimeMaxSec=1800"' in isolated_source
    assert '"--property=TasksMax=256"' in isolated_source
    assert '"--property=MemoryMax=4294967296"' in isolated_source
    assert "SystemCallFilter=~ptrace process_vm_readv process_vm_writev" in isolated_source
    assert "os.fsync(file_descriptor)" in inspect.getsource(
        release._freeze_release_tree
    )


@pytest.mark.parametrize(
    "index_flag",
    ("--assume-unchanged", "--skip-worktree"),
)
def test_commit_object_ledger_rejects_index_hidden_tracked_byte_changes(
    tmp_path: Path, index_flag: str
) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init")
    _git(repo, "config", "user.email", "test@example.invalid")
    _git(repo, "config", "user.name", "Verifier")
    tracked = repo / "deploy/sadhana/systemd/critical.service.in"
    tracked.parent.mkdir(parents=True)
    tracked.write_text("ExecStart=/usr/bin/true\n", encoding="ascii")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "trusted source")
    head = _git(repo, "rev-parse", "HEAD")
    manifest = release.render_tracked_source_manifest(repo, head)
    assert manifest["entries"][0]["sha256"] == hashlib.sha256(
        b"ExecStart=/usr/bin/true\n"
    ).hexdigest()

    _git(repo, "update-index", index_flag, str(tracked.relative_to(repo)))
    tracked.write_text("ExecStart=/tmp/attacker\n", encoding="ascii")
    assert _git(repo, "status", "--porcelain=v1", "--untracked-files=no") == ""
    shutil.rmtree(repo / ".git")
    # Normalize fixture group custody because macOS private tmp roots may carry
    # wheel while this process has a different effective gid.
    for directory, names, files in os.walk(repo):
        os.chown(directory, -1, os.getegid())
        for name in (*names, *files):
            os.chown(Path(directory) / name, -1, os.getegid())
    with pytest.raises(release.ReleaseContractError, match="file hash differs"):
        release.verify_tracked_source_tree(
            repo,
            manifest,
            expected_uid=os.geteuid(),
            expected_gid=os.getegid(),
            frozen=False,
            require_build_outputs=False,
        )


def test_pinned_uv_rejects_wrong_hash_and_wrong_platform(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    wheel = tmp_path / release.UV_WHEEL_FILE
    digest = _write_synthetic_uv_wheel(wheel)
    with pytest.raises(release.ReleaseContractError, match="digest"):
        release.provision_pinned_uv(
            wheel,
            tooling_root=tmp_path / "wrong-hash",
            runner=_uv_version_runner,
            system_name="Linux",
            machine="x86_64",
        )
    monkeypatch.setattr(release, "UV_WHEEL_SHA256", digest)
    with pytest.raises(release.ReleaseContractError, match="Linux x86_64"):
        release.provision_pinned_uv(
            wheel,
            tooling_root=tmp_path / "wrong-platform",
            runner=_uv_version_runner,
            system_name="Darwin",
            machine="arm64",
        )


def _git(cwd: Path, *args: str) -> str:
    return subprocess.run(
        ("git", *args), cwd=cwd, check=True, capture_output=True, text=True
    ).stdout.strip()


def test_verify_checkout_binds_sha_origin_ancestry_and_packet(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init")
    _git(repo, "config", "user.email", "test@example.invalid")
    _git(repo, "config", "user.name", "Verifier")
    _git(repo, "commit", "--allow-empty", "-m", "integration base")
    integration_base = _git(repo, "rev-parse", "HEAD")
    packet_path = (
        repo
        / "reports/agentops/work_packets/organism-rewire-WP-SADHANA-VPS-RELEASE-P0.json"
    )
    packet_path.parent.mkdir(parents=True)
    packet_path.write_text(
        json.dumps({"session_entry": {"packet_digest": "4" * 64}}) + "\n",
        encoding="utf-8",
    )
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "base")
    head = _git(repo, "rev-parse", "HEAD")
    _git(repo, "remote", "add", "origin", release.CANONICAL_ORIGIN)
    monkeypatch.setattr(release, "ACCEPTED_BASE_SHA", integration_base)
    payload = _payload()
    payload["release_sha"] = head
    payload["accepted_base_sha"] = integration_base
    payload["integration_base_sha"] = integration_base
    payload["work_packet_sha256"] = release.sha256_file(packet_path)
    _reseal(payload)
    release.verify_checkout(repo, payload)
    release.verify_tracked_checkout(repo, head)
    packet_path.write_text("mutated\n", encoding="utf-8")
    with pytest.raises(release.ReleaseContractError, match="tracked source"):
        release.verify_tracked_checkout(repo, head)
    _git(repo, "restore", str(packet_path.relative_to(repo)))
    wrong = copy.deepcopy(payload)
    wrong["release_sha"] = "f" * 40
    _reseal(wrong)
    with pytest.raises(release.ReleaseContractError, match="HEAD"):
        release.verify_checkout(repo, wrong)
    wrong_parent = copy.deepcopy(payload)
    wrong_parent["integration_base_sha"] = "a" * 40
    _reseal(wrong_parent)
    with pytest.raises(release.ReleaseContractError, match="sole parent"):
        release.verify_checkout(repo, wrong_parent)
    _git(repo, "remote", "set-url", "origin", "https://example.invalid/repo.git")
    with pytest.raises(release.ReleaseContractError, match="canonical"):
        release.verify_checkout(repo, payload)


def test_manifest_digest_is_not_a_placeholder() -> None:
    payload = _payload()
    assert payload["manifest_digest"] != "0" * 64
    forged = copy.deepcopy(payload)
    forged["manifest_digest"] = "f" * 64
    with pytest.raises(release.ReleaseContractError, match="self-digest"):
        release.validate_manifest(forged)


def test_seal_then_verify_full_bundle_packet_and_closeout_receipt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init")
    _git(repo, "config", "user.email", "test@example.invalid")
    _git(repo, "config", "user.name", "Verifier")
    _git(repo, "commit", "--allow-empty", "-m", "integration base")
    integration_base = _git(repo, "rev-parse", "HEAD")
    relative_packet = (
        "reports/agentops/work_packets/organism-rewire-WP-SADHANA-VPS-RELEASE-P0.json"
    )
    packet = repo / relative_packet
    packet.parent.mkdir(parents=True)
    packet.write_text(
        json.dumps({"session_entry": {"packet_digest": "7" * 64}}) + "\n",
        encoding="utf-8",
    )
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "candidate")
    head = _git(repo, "rev-parse", "HEAD")
    _git(repo, "remote", "add", "origin", release.CANONICAL_ORIGIN)
    monkeypatch.setattr(release, "ACCEPTED_BASE_SHA", integration_base)
    receipt = tmp_path / "closeout-source.json"
    receipt.write_text(
        json.dumps(
            {
                "status": "passed",
                "phase": "closeout",
                "packet_digest": "7" * 64,
                "packet_bytes_sha256": release.sha256_file(packet),
                "target_head": head,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    receipt.chmod(0o600)
    uv_wheel_source = tmp_path / f"source-{release.UV_WHEEL_FILE}"
    uv_digest = _write_synthetic_uv_wheel(uv_wheel_source)
    monkeypatch.setattr(release, "UV_WHEEL_SHA256", uv_digest)
    input_source_root = tmp_path / "input-source"
    input_source_root.mkdir(mode=0o700)
    input_payload, _contents = _input_fixture(input_source_root, monkeypatch)
    input_manifest = tmp_path / release.INPUT_SET_MANIFEST_FILE
    input_manifest.write_text(
        json.dumps(input_payload, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    input_manifest.chmod(0o600)
    deployment_known_hosts = tmp_path / "authorized-deployment-known-hosts"
    deployment_known_hosts.write_text(
        "meghadharma-cloud ssh-ed25519 AAAAfixture\n"
        "agni-openclaw ssh-ed25519 AAAAfixture\n",
        encoding="ascii",
    )
    deployment_known_hosts.chmod(0o600)
    monkeypatch.setattr(
        release,
        "DEPLOYMENT_KNOWN_HOSTS_SHA256",
        release.sha256_file(deployment_known_hosts),
    )
    monkeypatch.setattr(
        release,
        "scan_static_input_set",
        lambda *_args, **_kwargs: {"finding_count": 0},
    )
    envelope = tmp_path / "envelope"
    (
        manifest_path,
        bundle,
        receipt_copy,
        uv_wheel,
        input_manifest_copy,
        input_archive,
        deployment_known_hosts_copy,
        tracked_source_manifest_copy,
    ) = release.seal_envelope(
        repo_root=repo,
        integration_base_sha=integration_base,
        work_packet_path=relative_packet,
        closeout_receipt=receipt,
        input_set_manifest=input_manifest,
        input_set_source_root=input_source_root,
        deployment_known_hosts=deployment_known_hosts,
        output_root=envelope,
        uv_wheel_source=uv_wheel_source,
    )
    manifest = release.load_manifest(manifest_path)
    release.verify_envelope(
        manifest,
        repo_root=repo,
        bundle_path=bundle,
        receipt_path=receipt_copy,
        uv_wheel_path=uv_wheel,
        input_set_manifest_path=input_manifest_copy,
        input_set_archive_path=input_archive,
        deployment_known_hosts_path=deployment_known_hosts_copy,
        tracked_source_manifest_path=tracked_source_manifest_copy,
        expected_role="writer",
        now=datetime(2026, 8, 23, 0, 0, tzinfo=timezone.utc),
        observed_node=release.WRITER_NODE,
    )
    assert manifest["release_sha"] == head
    assert manifest["canonical_or_merged"] is False


@pytest.mark.parametrize(
    ("fence_failure_call", "candidate_frozen"),
    [(1, False), (2, False), (3, True)],
)
def test_account_ui_consumer_rechecks_fences_before_and_after_freeze(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    fence_failure_call: int,
    candidate_frozen: bool,
) -> None:
    release_sha = "a" * 40
    operator_login = b"operator@example.test"
    hmac_secret = b"h" * 32
    gate_digest = "sha256:" + "7" * 64
    candidate = _account_ui_candidate_fixture(
        release_sha=release_sha,
        operator_login_sha256=hashlib.sha256(operator_login).hexdigest(),
        gate_digest=gate_digest,
        hmac_secret=hmac_secret,
    )
    candidate_raw = release._canonical_bytes(candidate) + b"\n"
    receipt_path = tmp_path / "authenticated-account-ui-confirmation.v1.json"
    login_path = tmp_path / "login"
    hmac_path = tmp_path / "hmac"
    monkeypatch.setattr(release, "ACCOUNT_UI_CONFIRMATION_RECEIPT", receipt_path)
    monkeypatch.setattr(release, "CONTROL_LOGIN_SOURCE", login_path)
    monkeypatch.setattr(release, "CONTROL_HMAC_SOURCE", hmac_path)
    monkeypatch.setattr(release, "_require_host_role", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        release,
        "_read_control_credential",
        lambda path, **_kwargs: operator_login if path == login_path else hmac_secret,
    )
    control = SimpleNamespace(pw_uid=os.geteuid(), pw_gid=os.getegid())
    monkeypatch.setattr(release.pwd, "getpwnam", lambda _name: control)
    monkeypatch.setattr(
        release,
        "_load_predispatch_account_ui_gate",
        lambda **_kwargs: {"receipt_digest": gate_digest},
    )
    monkeypatch.setattr(release, "_control_inbox_ledger", lambda **_kwargs: ())
    monkeypatch.setattr(
        release,
        "_read_account_ui_candidate",
        lambda **_kwargs: (candidate, candidate_raw, None, None),
    )
    monkeypatch.setattr(
        release, "_control_expected_origin", lambda: "https://sadhana.example.ts.net"
    )
    frozen = False

    def freeze(**_kwargs: object) -> None:
        nonlocal frozen
        frozen = True

    monkeypatch.setattr(release, "_freeze_account_ui_candidate", freeze)
    fence_calls = 0

    def fences(**_kwargs: object) -> None:
        nonlocal fence_calls
        fence_calls += 1
        if fence_calls == fence_failure_call:
            raise release.ReleaseContractError("injected dispatch marker race")

    monkeypatch.setattr(release, "_require_account_ui_predispatch_fences", fences)
    with pytest.raises(release.ReleaseContractError, match="dispatch marker race"):
        release.consume_account_ui_confirmation(
            role="writer",
            release_sha=release_sha,
            now=datetime(2026, 8, 23, 1, tzinfo=timezone.utc),
            observed_node=release.WRITER_NODE,
            expected_root_uid=os.geteuid(),
            expected_root_gid=os.getegid(),
        )
    assert frozen is candidate_frozen
    assert fence_calls == fence_failure_call
    assert not receipt_path.exists()


@pytest.mark.parametrize(
    "mutation",
    [
        "hmac",
        "release",
        "principal",
        "float_width",
        "integer_boolean",
        "nonempty_ledger",
        "expired",
        "extra_field",
    ],
)
def test_account_ui_consumer_rejects_hostile_candidate_before_freeze(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mutation: str,
) -> None:
    release_sha = "a" * 40
    operator_login = b"operator@example.test"
    hmac_secret = b"h" * 32
    gate_digest = "sha256:" + "7" * 64
    candidate = _account_ui_candidate_fixture(
        release_sha=release_sha,
        operator_login_sha256=hashlib.sha256(operator_login).hexdigest(),
        gate_digest=gate_digest,
        hmac_secret=hmac_secret,
    )
    if mutation == "hmac":
        candidate["hmac_sha256"] = "hmac-sha256:" + "0" * 64
    elif mutation == "release":
        candidate["release_sha"] = "b" * 40
    elif mutation == "principal":
        candidate["operator_login_sha256"] = hashlib.sha256(b"attacker").hexdigest()
    elif mutation == "float_width":
        candidate["viewport_width_css_px_reported"] = 390.0
    elif mutation == "integer_boolean":
        candidate["trusted_browser_event_reported"] = 1
    elif mutation == "nonempty_ledger":
        candidate["normal_inbox_empty_ledger_sha256"] = "sha256:" + "f" * 64
    elif mutation == "expired":
        candidate["expires_at"] = "2026-08-23T00:59:59Z"
    else:
        candidate["unsupported_authority"] = True
    if mutation != "hmac":
        candidate["hmac_sha256"] = release._account_ui_candidate_mac(
            candidate, hmac_secret
        )
    candidate_raw = release._canonical_bytes(candidate) + b"\n"
    receipt_path = tmp_path / "authenticated-account-ui-confirmation.v1.json"
    login_path = tmp_path / "login"
    hmac_path = tmp_path / "hmac"
    monkeypatch.setattr(release, "ACCOUNT_UI_CONFIRMATION_RECEIPT", receipt_path)
    monkeypatch.setattr(release, "CONTROL_LOGIN_SOURCE", login_path)
    monkeypatch.setattr(release, "CONTROL_HMAC_SOURCE", hmac_path)
    monkeypatch.setattr(release, "_require_host_role", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        release,
        "_read_control_credential",
        lambda path, **_kwargs: operator_login if path == login_path else hmac_secret,
    )
    monkeypatch.setattr(
        release.pwd,
        "getpwnam",
        lambda _name: SimpleNamespace(pw_uid=os.geteuid(), pw_gid=os.getegid()),
    )
    monkeypatch.setattr(
        release,
        "_load_predispatch_account_ui_gate",
        lambda **_kwargs: {"receipt_digest": gate_digest},
    )
    monkeypatch.setattr(release, "_control_inbox_ledger", lambda **_kwargs: ())
    monkeypatch.setattr(
        release,
        "_read_account_ui_candidate",
        lambda **_kwargs: (candidate, candidate_raw, None, None),
    )
    monkeypatch.setattr(
        release, "_control_expected_origin", lambda: "https://sadhana.example.ts.net"
    )
    monkeypatch.setattr(
        release, "_require_account_ui_predispatch_fences", lambda **_kwargs: None
    )
    frozen = False

    def freeze(**_kwargs: object) -> None:
        nonlocal frozen
        frozen = True

    monkeypatch.setattr(release, "_freeze_account_ui_candidate", freeze)
    with pytest.raises(release.ReleaseContractError, match="candidate binding differs"):
        release.consume_account_ui_confirmation(
            role="writer",
            release_sha=release_sha,
            now=datetime(2026, 8, 23, 1, tzinfo=timezone.utc),
            observed_node=release.WRITER_NODE,
            expected_root_uid=os.geteuid(),
            expected_root_gid=os.getegid(),
        )
    assert frozen is False
    assert not receipt_path.exists()


@pytest.mark.parametrize("failure_step", [None, 1, 2, 3, 4, 5, 6])
def test_frozen_or_partially_frozen_candidate_can_never_be_reopened(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    failure_step: int | None,
) -> None:
    supplementary_groups = [group for group in os.getgroups() if group != os.getegid()]
    if not supplementary_groups:
        pytest.skip("no distinct supplementary group for custody transition")
    control_gid = supplementary_groups[0]
    candidate_root = tmp_path / "account-ui-confirmation"
    candidate_root.mkdir(mode=0o770)
    os.chown(candidate_root, -1, control_gid)
    candidate_root.chmod(0o770)
    candidate_path = candidate_root / "candidate.v2.json"
    raw = b"{}\n"
    candidate_path.write_bytes(raw)
    candidate_path.chmod(0o600)
    os.chown(candidate_path, -1, control_gid)
    source_inode = candidate_path.stat().st_ino
    monkeypatch.setattr(release, "ACCOUNT_UI_CONFIRMATION_ROOT", candidate_root)
    monkeypatch.setattr(release, "ACCOUNT_UI_CONFIRMATION_CANDIDATE", candidate_path)
    original_fchown = release.os.fchown
    original_fchmod = release.os.fchmod
    original_fsync = release.os.fsync
    step = 0

    def checkpoint() -> None:
        nonlocal step
        step += 1
        if step == failure_step:
            raise OSError("injected freeze boundary failure")

    def fchown(descriptor: int, uid: int, gid: int) -> None:
        original_fchown(descriptor, uid, gid)
        checkpoint()

    def fchmod(descriptor: int, mode: int) -> None:
        original_fchmod(descriptor, mode)
        checkpoint()

    def fsync(descriptor: int) -> None:
        original_fsync(descriptor)
        checkpoint()

    monkeypatch.setattr(release.os, "fchown", fchown)
    monkeypatch.setattr(release.os, "fchmod", fchmod)
    monkeypatch.setattr(release.os, "fsync", fsync)
    if failure_step is None:
        release._freeze_account_ui_candidate(
            control_uid=os.geteuid(),
            control_gid=control_gid,
            expected_root_uid=os.geteuid(),
            expected_root_gid=os.getegid(),
        )
    else:
        with pytest.raises(OSError, match="freeze boundary"):
            release._freeze_account_ui_candidate(
                control_uid=os.geteuid(),
                control_gid=control_gid,
                expected_root_uid=os.geteuid(),
                expected_root_gid=os.getegid(),
            )
    terminal_directory = candidate_root.stat()
    terminal_candidate = candidate_path.stat()
    monkeypatch.setattr(release, "_require_host_role", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        release,
        "_require_static_service_identity",
        lambda: SimpleNamespace(pw_uid=os.geteuid(), pw_gid=os.getegid()),
    )
    monkeypatch.setattr(
        release.pwd,
        "getpwnam",
        lambda _name: SimpleNamespace(pw_uid=os.geteuid(), pw_gid=control_gid),
    )
    with pytest.raises(release.ReleaseContractError, match="cannot be reopened"):
        release.prepare_control_runtime(
            role="writer",
            observed_node=release.WRITER_NODE,
            expected_root_uid=os.geteuid(),
        )
    after_directory = candidate_root.stat()
    after_candidate = candidate_path.stat()
    assert candidate_path.read_bytes() == raw
    assert after_candidate.st_ino == source_inode
    assert (
        after_directory.st_uid,
        after_directory.st_gid,
        stat.S_IMODE(after_directory.st_mode),
        after_candidate.st_uid,
        after_candidate.st_gid,
        stat.S_IMODE(after_candidate.st_mode),
    ) == (
        terminal_directory.st_uid,
        terminal_directory.st_gid,
        stat.S_IMODE(terminal_directory.st_mode),
        terminal_candidate.st_uid,
        terminal_candidate.st_gid,
        stat.S_IMODE(terminal_candidate.st_mode),
    )


def test_account_ui_root_receipt_rejects_type_and_nonempty_ledger_overclaims() -> None:
    release_sha = "a" * 40
    operator_login_sha256 = hashlib.sha256(b"operator@example.test").hexdigest()
    base = _account_ui_confirmation_fixture(
        release_sha=release_sha,
        operator_login_sha256=operator_login_sha256,
    )
    release._validate_account_ui_confirmation_payload(
        base,
        release_sha=release_sha,
        now=datetime(2026, 8, 23, 1, tzinfo=timezone.utc),
        operator_login_sha256=operator_login_sha256,
    )
    mutations = (
        ("viewport_width_css_px_reported", 390.0),
        ("trusted_browser_event_reported", 1),
        ("physical_device_attested", 0),
        ("normal_and_emergency_inbox_ledger_sha256_before", "sha256:" + "f" * 64),
    )
    for field, value in mutations:
        hostile = copy.deepcopy(base)
        hostile[field] = value
        if field == "normal_and_emergency_inbox_ledger_sha256_before":
            hostile["normal_and_emergency_inbox_ledger_sha256_after"] = value
        hostile["receipt_digest"] = release._canonical_self_digest(
            hostile, "receipt_digest"
        )
        with pytest.raises(release.ReleaseContractError, match="binding differs"):
            release._validate_account_ui_confirmation_payload(
                hostile,
                release_sha=release_sha,
                now=datetime(2026, 8, 23, 1, tzinfo=timezone.utc),
                operator_login_sha256=operator_login_sha256,
            )


def test_account_ui_cli_has_no_path_or_boolean_fabrication_surface() -> None:
    parser = release._parser()
    valid = parser.parse_args(
        [
            "record-account-ui-confirmation",
            "--role",
            "writer",
            "--release-sha",
            "a" * 40,
        ]
    )
    assert vars(valid) == {
        "command": "record-account-ui-confirmation",
        "role": "writer",
        "release_sha": "a" * 40,
    }
    for extra in (
        ("--candidate", "/tmp/forged.json"),
        ("--authenticated-probe", "/tmp/forged.json"),
        ("--operator-confirmed", "true"),
        ("--physical-device-attested", "true"),
    ):
        with pytest.raises(SystemExit):
            parser.parse_args(
                [
                    "record-account-ui-confirmation",
                    "--role",
                    "writer",
                    "--release-sha",
                    "a" * 40,
                    *extra,
                ]
            )
    with pytest.raises(SystemExit):
        parser.parse_args(
            [
                "record-dashboard-identity",
                "--role",
                "writer",
                "--release-sha",
                "a" * 40,
                "--authenticated-probe",
                "/tmp/forged.json",
            ]
        )


def test_control_and_dashboard_units_reject_secret_or_binding_widening() -> None:
    unit_root = Path(__file__).resolve().parents[1] / "deploy/sadhana/systemd"
    mutations = {
        "dharma-sadhana-control.service.in": (
            "EnvironmentFile=/etc/dharma-sadhana/extra.env\n",
            "LoadCredential=extra:/etc/dharma-sadhana/credentials/extra\n",
            "Environment=SADHANA_RELEASE_SHA=" + "b" * 40 + "\n",
            "Environment=SADHANA_ACCOUNT_UI_CONFIRMATION_ENDPOINT=/v1/other\n",
            "ReadWritePaths=/run/dharma-sadhana/control/account-ui-gate\n",
        ),
        "dharma-sadhana-dashboard.service.in": (
            "EnvironmentFile=/etc/dharma-sadhana/control.env\n",
            "LoadCredential=control_hmac_key:/etc/dharma-sadhana/credentials/"
            "control_hmac_key\n",
            "SetCredential=control_hmac_key:forged\n",
            "Environment=SADHANA_RELEASE_SHA=" + "b" * 40 + "\n",
            "Environment=SADHANA_ACCOUNT_UI_CONFIRMATION_INTERNAL_URL="
            "http://127.0.0.1:18421/v1/other\n",
        ),
    }
    for name, additions in mutations.items():
        source = (unit_root / name).read_text(encoding="utf-8")
        release.validate_unit_text(name, source, rendered=False)
        for addition in additions:
            with pytest.raises(release.ReleaseContractError):
                release.validate_unit_text(
                    name,
                    source + addition,
                    rendered=False,
                )


def test_control_and_dashboard_units_reject_effective_service_overrides() -> None:
    unit_root = Path(__file__).resolve().parents[1] / "deploy/sadhana/systemd"
    appended_assignments = {
        "dharma-sadhana-control.service.in": (
            "Environment=SADHANA_CONTROL_NORMAL_INBOX=/tmp/empty",
            "Environment=SADHANA_CONTROL_EXPECTED_ORIGIN=https://evil.example",
            "ProtectSystem=false",
            "User=root",
            "Group=root",
            "BindPaths=/tmp:/run/dharma-sadhana/control",
            "StateDirectory=escape",
        ),
        "dharma-sadhana-dashboard.service.in": (
            "Environment=SADHANA_CONTROL_BEARER_FILE=/tmp/readable",
            "Environment=SADHANA_CONTROL_EXPECTED_ORIGIN=https://evil.example",
            "ProtectSystem=false",
            "User=root",
            "Group=root",
            "BindPaths=/tmp:/run/dharma-sadhana/dashboard",
            "StateDirectory=escape",
        ),
    }
    removed_assignments = {
        "dharma-sadhana-control.service.in": (
            "User=dharma-sadhana-control",
            "Group=dharma-sadhana-control",
            "Environment=SADHANA_CONTROL_NORMAL_INBOX="
            "/run/dharma-sadhana/control/normal",
            "ProtectSystem=strict",
            "RestrictNamespaces=true",
        ),
        "dharma-sadhana-dashboard.service.in": (
            "User=dharma-sadhana-dashboard",
            "Group=dharma-sadhana-dashboard",
            "Environment=SADHANA_CONTROL_BEARER_FILE=%d/operator_bearer",
            "ProtectSystem=strict",
            "RestrictNamespaces=true",
        ),
    }
    duplicated_assignments = {
        "dharma-sadhana-control.service.in": (
            "User=dharma-sadhana-control",
            "ProtectSystem=strict",
            "Environment=SADHANA_CONTROL_NORMAL_INBOX="
            "/run/dharma-sadhana/control/normal",
        ),
        "dharma-sadhana-dashboard.service.in": (
            "User=dharma-sadhana-dashboard",
            "ProtectSystem=strict",
            "Environment=SADHANA_CONTROL_BEARER_FILE=%d/operator_bearer",
        ),
    }

    for name in appended_assignments:
        source = (unit_root / name).read_text(encoding="utf-8")
        for rendered, admitted in (
            (False, source),
            (True, source.replace("@RELEASE_SHA@", "a" * 40)),
        ):
            release.validate_unit_text(name, admitted, rendered=rendered)
            for assignment in appended_assignments[name]:
                hostile = admitted.replace(
                    "\n[Install]\n",
                    f"\n{assignment}\n\n[Install]\n",
                    1,
                )
                assert hostile != admitted
                with pytest.raises(release.ReleaseContractError):
                    release.validate_unit_text(name, hostile, rendered=rendered)
            for assignment in removed_assignments[name]:
                hostile = admitted.replace(f"{assignment}\n", "", 1)
                assert hostile != admitted
                with pytest.raises(release.ReleaseContractError):
                    release.validate_unit_text(name, hostile, rendered=rendered)
            for assignment in duplicated_assignments[name]:
                hostile = admitted.replace(
                    f"{assignment}\n",
                    f"{assignment}\n{assignment}\n",
                    1,
                )
                assert hostile != admitted
                with pytest.raises(release.ReleaseContractError):
                    release.validate_unit_text(name, hostile, rendered=rendered)


def _live_writer_unit_roots(
    tmp_path: Path,
    *,
    release_sha: str,
) -> tuple[Path, Path]:
    repo = Path(__file__).resolve().parents[1]
    release_root = tmp_path / "releases"
    template_root = (
        release_root / release_sha / release.SYSTEMD_TEMPLATE_ROOT
    )
    unit_root = tmp_path / "systemd"
    template_root.mkdir(parents=True)
    unit_root.mkdir()
    for unit in (release.CONTROL_UNIT, release.DASHBOARD_UNIT):
        source = repo / release.SYSTEMD_TEMPLATE_ROOT / f"{unit}.in"
        raw = source.read_bytes()
        template = template_root / f"{unit}.in"
        template.write_bytes(raw)
        template.chmod(0o444)
        installed = unit_root / unit
        installed.write_bytes(raw.replace(b"@RELEASE_SHA@", release_sha.encode()))
        installed.chmod(0o644)
    return release_root, unit_root


def _fake_live_unit_properties(unit_root: Path, unit: str) -> dict[str, str]:
    text = (unit_root / unit).read_text(encoding="utf-8")
    assignments = release._unit_section_assignments(text, "Service")

    def one(key: str) -> str:
        prefix = f"{key}="
        values = [
            line.removeprefix(prefix)
            for line in assignments
            if line.startswith(prefix)
        ]
        assert len(values) == 1
        return values[0]

    def exec_property(key: str) -> str:
        prefix = f"{key}="
        records: list[str] = []
        for original in (
            line.removeprefix(prefix)
            for line in assignments
            if line.startswith(prefix)
        ):
            flags: list[str] = []
            command = original
            while command and command[0] in "-+!:@":
                marker, command = command[0], command[1:]
                if marker == "-":
                    flags.append("ignore-failure")
                elif marker == "+":
                    flags.append("privileged")
                else:
                    raise AssertionError("fixture encountered an unsupported prefix")
            path = command.split(" ", 1)[0]
            records.append(
                "{ path="
                f"{path} ; argv[]={command} ; flags={','.join(flags)} ; "
                "start_time=[n/a] ; stop_time=[n/a] ; pid=0 ; "
                "code=(null) ; status=0/0 }"
            )
        assert records
        return " ; ".join(records)

    environments = [
        line.removeprefix("Environment=")
        for line in assignments
        if line.startswith("Environment=")
    ]
    credential_directory = f"/run/credentials/{unit}"
    environment_file = one("EnvironmentFile")
    return {
        "FragmentPath": str(unit_root / unit),
        "DropInPaths": "",
        "User": one("User"),
        "Group": one("Group"),
        "NoNewPrivileges": "yes",
        "CapabilityBoundingSet": one("CapabilityBoundingSet").lower(),
        "ProtectSystem": one("ProtectSystem"),
        "ReadWritePaths": one("ReadWritePaths"),
        "ExecStartEx": exec_property("ExecStart"),
        "ExecStartPreEx": exec_property("ExecStartPre"),
        "Environment": " ".join(
            value.replace("%d", credential_directory) for value in environments
        ),
        "EnvironmentFiles": f"{environment_file} (ignore_errors=no)",
        "NeedDaemonReload": "no",
    }


def _fake_live_systemd_runner(
    unit_root: Path,
    *,
    initial_overrides: dict[str, dict[str, str]] | None = None,
    post_reload_overrides: dict[str, dict[str, str]] | None = None,
    duplicate_property: str | None = None,
) -> tuple[
    Callable[..., subprocess.CompletedProcess[str]],
    list[tuple[str, ...]],
]:
    safe = {
        unit: _fake_live_unit_properties(unit_root, unit)
        for unit in (release.CONTROL_UNIT, release.DASHBOARD_UNIT)
    }
    loaded = copy.deepcopy(safe)
    for unit, overrides in (initial_overrides or {}).items():
        loaded[unit].update(overrides)
    calls: list[tuple[str, ...]] = []

    def runner(argv, **_kwargs):  # noqa: ANN001, ANN202
        command = tuple(argv)
        calls.append(command)
        if command == (release.SYSTEMCTL_PATH, "daemon-reload"):
            loaded.clear()
            loaded.update(copy.deepcopy(safe))
            for unit, overrides in (post_reload_overrides or {}).items():
                loaded[unit].update(overrides)
            return subprocess.CompletedProcess(argv, 0, "", "")
        assert command[0:2] == (release.SYSTEMCTL_PATH, "show")
        unit = command[-1]
        if command[-2] == "--value":
            property_name = command[2].removeprefix("--property=")
            assert property_name in release._LIVE_WRITER_EXEC_PROPERTY_NAMES
            value = loaded[unit][property_name]
            # systemd emits one value row per command for list-valued Exec*Ex.
            value = value.replace(" } ; { ", " }\n{ ")
            return subprocess.CompletedProcess(argv, 0, value + "\n", "")
        names = tuple(
            value.removeprefix("--property=") for value in command[2:-1]
        )
        assert names == release._LIVE_WRITER_UNIT_PROPERTY_NAMES
        rows = [f"{name}={loaded[unit][name]}" for name in names]
        if duplicate_property is not None:
            rows.append(
                f"{duplicate_property}={loaded[unit][duplicate_property]}"
            )
        return subprocess.CompletedProcess(argv, 0, "\n".join(rows) + "\n", "")

    return runner, calls


def test_live_writer_unit_gate_accepts_exact_loaded_units_before_and_after_reload(
    tmp_path: Path,
) -> None:
    release_sha = "a" * 40
    release_root, unit_root = _live_writer_unit_roots(
        tmp_path,
        release_sha=release_sha,
    )
    runner, calls = _fake_live_systemd_runner(unit_root)
    release._require_live_writer_service_units(
        release_sha=release_sha,
        runner=runner,
        unit_root=unit_root,
        release_root=release_root,
        expected_root_uid=os.geteuid(),
        expected_root_gid=os.getegid(),
    )
    assert calls.count((release.SYSTEMCTL_PATH, "daemon-reload")) == 1
    assert len([call for call in calls if call[1] == "show"]) == 12


@pytest.mark.parametrize(
    ("unit", "property_name", "hostile_value"),
    (
        (release.CONTROL_UNIT, "FragmentPath", "/tmp/hostile.service"),
        (
            release.CONTROL_UNIT,
            "DropInPaths",
            "/run/systemd/system/dharma-sadhana-control.service.d/evil.conf",
        ),
        (release.CONTROL_UNIT, "User", "root"),
        (release.CONTROL_UNIT, "Group", "root"),
        (release.CONTROL_UNIT, "NoNewPrivileges", "no"),
        (release.CONTROL_UNIT, "CapabilityBoundingSet", "chown"),
        (release.CONTROL_UNIT, "ProtectSystem", "no"),
        (release.CONTROL_UNIT, "ReadWritePaths", "/"),
        (release.CONTROL_UNIT, "EnvironmentFiles", "/tmp/evil (ignore_errors=no)"),
        (release.CONTROL_UNIT, "NeedDaemonReload", "yes"),
    ),
)
def test_live_writer_unit_gate_rejects_stale_effective_property_before_reload(
    tmp_path: Path,
    unit: str,
    property_name: str,
    hostile_value: str,
) -> None:
    release_sha = "a" * 40
    release_root, unit_root = _live_writer_unit_roots(
        tmp_path,
        release_sha=release_sha,
    )
    runner, calls = _fake_live_systemd_runner(
        unit_root,
        initial_overrides={unit: {property_name: hostile_value}},
    )
    with pytest.raises(release.ReleaseContractError):
        release._require_live_writer_service_units(
            release_sha=release_sha,
            runner=runner,
            unit_root=unit_root,
            release_root=release_root,
            expected_root_uid=os.geteuid(),
            expected_root_gid=os.getegid(),
        )
    assert (release.SYSTEMCTL_PATH, "daemon-reload") not in calls


def test_live_writer_unit_gate_rejects_stale_environment_and_exec_prefix_cache(
    tmp_path: Path,
) -> None:
    release_sha = "a" * 40
    release_root, unit_root = _live_writer_unit_roots(
        tmp_path,
        release_sha=release_sha,
    )
    safe_control = _fake_live_unit_properties(unit_root, release.CONTROL_UNIT)
    safe_dashboard = _fake_live_unit_properties(unit_root, release.DASHBOARD_UNIT)
    hostile_cases = (
        {
            release.CONTROL_UNIT: {
                "Environment": safe_control["Environment"]
                + " SADHANA_CONTROL_EXPECTED_ORIGIN=https://evil.example"
            }
        },
        {
            release.DASHBOARD_UNIT: {
                "Environment": safe_dashboard["Environment"].replace(
                    "/run/credentials/dharma-sadhana-dashboard.service/"
                    "operator_bearer",
                    "/tmp/readable",
                )
            }
        },
        {
            release.CONTROL_UNIT: {
                "ExecStartEx": safe_control["ExecStartEx"].replace(
                    "flags= ;",
                    "flags=privileged ;",
                    1,
                )
            }
        },
        {
            release.DASHBOARD_UNIT: {
                "ExecStartPreEx": safe_dashboard["ExecStartPreEx"].replace(
                    "flags=privileged ;",
                    "flags= ;",
                    1,
                )
            }
        },
    )
    for initial_overrides in hostile_cases:
        runner, calls = _fake_live_systemd_runner(
            unit_root,
            initial_overrides=initial_overrides,
        )
        with pytest.raises(release.ReleaseContractError):
            release._require_live_writer_service_units(
                release_sha=release_sha,
                runner=runner,
                unit_root=unit_root,
                release_root=release_root,
                expected_root_uid=os.geteuid(),
                expected_root_gid=os.getegid(),
            )
        assert (release.SYSTEMCTL_PATH, "daemon-reload") not in calls


def test_live_writer_unit_gate_rechecks_manager_and_fragment_after_reload(
    tmp_path: Path,
) -> None:
    release_sha = "a" * 40
    release_root, unit_root = _live_writer_unit_roots(
        tmp_path,
        release_sha=release_sha,
    )
    runner, calls = _fake_live_systemd_runner(
        unit_root,
        post_reload_overrides={
            release.CONTROL_UNIT: {"ProtectSystem": "no"}
        },
    )
    with pytest.raises(release.ReleaseContractError):
        release._require_live_writer_service_units(
            release_sha=release_sha,
            runner=runner,
            unit_root=unit_root,
            release_root=release_root,
            expected_root_uid=os.geteuid(),
            expected_root_gid=os.getegid(),
        )
    assert calls.count((release.SYSTEMCTL_PATH, "daemon-reload")) == 1

    installed = unit_root / release.CONTROL_UNIT
    installed.chmod(0o644)
    installed.write_bytes(installed.read_bytes() + b"# hostile drift\n")
    installed.chmod(0o644)
    safe_runner, safe_calls = _fake_live_systemd_runner(unit_root)
    with pytest.raises(release.ReleaseContractError, match="fragment differs"):
        release._require_live_writer_service_units(
            release_sha=release_sha,
            runner=safe_runner,
            unit_root=unit_root,
            release_root=release_root,
            expected_root_uid=os.geteuid(),
            expected_root_gid=os.getegid(),
        )
    assert safe_calls == []


def test_live_writer_unit_gate_rejects_duplicate_systemctl_property(
    tmp_path: Path,
) -> None:
    release_sha = "a" * 40
    release_root, unit_root = _live_writer_unit_roots(
        tmp_path,
        release_sha=release_sha,
    )
    runner, calls = _fake_live_systemd_runner(
        unit_root,
        duplicate_property="ProtectSystem",
    )
    with pytest.raises(release.ReleaseContractError, match="property set differs"):
        release._require_live_writer_service_units(
            release_sha=release_sha,
            runner=runner,
            unit_root=unit_root,
            release_root=release_root,
            expected_root_uid=os.geteuid(),
            expected_root_gid=os.getegid(),
        )
    assert (release.SYSTEMCTL_PATH, "daemon-reload") not in calls
