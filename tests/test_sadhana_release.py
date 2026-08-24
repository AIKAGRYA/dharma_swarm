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
    }

    def active(unit, **_kwargs):  # noqa: ANN001, ANN202
        return (
            state["target_active"]
            if unit == release.STANDBY_TARGET
            else state["timer_active"]
            if unit == release.STANDBY_STOP_TIMER
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
            )
        elif command[1:3] == ("disable", "--now"):
            if command[3] == release.STANDBY_TARGET:
                state.update(target_active=False, target_enabled=False)
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
    assert inspect.getsource(release.stage_candidate).count(
        "_start_runtime_preparation_unit("
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
            "uv-venv",
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
    root = tmp_path / "release"
    (root / ".venv/bin").mkdir(parents=True)
    (root / "scripts/runtime").mkdir(parents=True)
    (root / ".venv/bin/python").write_text("fixture", encoding="utf-8")
    (root / "scripts/runtime/mission_control_campaign.py").write_text(
        "fixture", encoding="utf-8"
    )
    state.mkdir()
    workspace.mkdir()
    monkeypatch.setattr(release, "STATE_ROOT", str(state))
    monkeypatch.setattr(release, "WORKSPACE_ROOT", str(workspace))
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
        projection_path=state / "projection.json",
        runner=runner,
        receipt_path=receipt,
        release_root=root,
        now=datetime(2026, 9, 1, 17, 15, 12, tzinfo=timezone.utc),
        observed_node=release.WRITER_NODE,
    )
    assert calls and calls[0][-2:] == (
        "--projection-path",
        str(state / "projection.json"),
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
    root = tmp_path / "release"
    (root / ".venv/bin").mkdir(parents=True)
    (root / "scripts/runtime").mkdir(parents=True)
    (root / ".venv/bin/python").write_text("fixture", encoding="utf-8")
    (root / "scripts/runtime/mission_control_campaign.py").write_text(
        "fixture", encoding="utf-8"
    )
    state.mkdir()
    workspace.mkdir()
    monkeypatch.setattr(release, "STATE_ROOT", str(state))
    monkeypatch.setattr(release, "WORKSPACE_ROOT", str(workspace))
    receipt = state / "stop-enforcement-receipt.json"

    def unavailable(*args, **kwargs):  # noqa: ANN002, ANN003, ANN202
        raise release.ReleaseContractError("secret launch detail")

    payload = release.persist_campaign_stop(
        writer_lock_path=state / "writer.lock",
        projection_path=state / "projection.json",
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
    assert len(rendered) == 35
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


def test_dashboard_v3_acceptance_binds_real_private_390px_observation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    release_sha = "a" * 40
    observed = datetime(2026, 8, 23, 1, tzinfo=timezone.utc)
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
    authenticated_path = tmp_path / "authenticated-tailnet.json"
    authenticated = _write_self_digest_receipt(
        authenticated_path,
        {
            "schema_version": "dharma.sadhana.authenticated_tailnet_probe.v1",
            "campaign_id": release.MISSION_ID,
            "release_sha": release_sha,
            "viewport_width_css_px": 390,
            "private_tailnet_https": True,
            "identity_header_injected": True,
            "operator_login_allowlist_match": True,
            "dashboard_rendered": True,
            "control_request_sent": False,
            "external_message_sent": False,
            "operator_confirmed": True,
            "observed_at": observed.isoformat().replace("+00:00", "Z"),
            "receipt_digest": "",
        },
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
    monkeypatch.setattr(release.pwd, "getpwnam", lambda _name: account)

    payload = release.record_dashboard_identity_acceptance(
        role="writer",
        release_sha=release_sha,
        authenticated_probe_path=authenticated_path,
        rollback_receipt_path=rollback_path,
        receipt_path=receipt_path,
        now=observed + timedelta(seconds=1),
        observed_node=release.WRITER_NODE,
        expected_root_uid=uid,
        expected_root_gid=gid,
        access_probe=lambda *_args, **_kwargs: True,
    )
    assert payload["authenticated_tailnet_probe"] == authenticated
    assert payload["rollback_probe"] == rollback
    assert payload["authenticated_tailnet_probe"]["viewport_width_css_px"] == 390
    assert payload["authenticated_tailnet_probe"]["control_request_sent"] is False
    assert payload["tcp_listener_inventory"] == {
        "dashboard_process": 0,
        "host_port_3000": 0,
    }
    assert all(payload["negative_access_matrix"].values())

    authenticated["viewport_width_css_px"] = 391
    _write_self_digest_receipt(authenticated_path, authenticated)
    with pytest.raises(release.ReleaseContractError, match="tailnet probe"):
        release.record_dashboard_identity_acceptance(
            role="writer",
            release_sha=release_sha,
            authenticated_probe_path=authenticated_path,
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
    active = False
    monkeypatch.setattr(
        release,
        "_unit_active",
        lambda unit, **_kwargs: active and unit == release.PREDISPATCH_TARGET,
    )
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
    dashboard = {
        "dashboard_unit_digest": release.sha256_file(systemd_root / release.DASHBOARD_UNIT),
        "dashboard_process_identity": identity,
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
    activation_env = b"SADHANA_OBSERVER_HEALTH_RECEIPT_SHA256=fixture\n"
    monkeypatch.setattr(
        release,
        "_publish_supervisor_activation_env",
        lambda **_kwargs: activation_env,
    )
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
    assert payload["oracle_sandbox_evidence_digest"] == "sha256:" + "6" * 64
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
        "finalize_disabled_runtime_staging",
        lambda **_kwargs: {"receipt_digest": "sha256:" + "4" * 64},
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
    observed = datetime(2026, 8, 23, 1, tzinfo=timezone.utc)
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

    receipt_path.unlink()
    writer_marker.unlink()
    for unit in unit_state:
        unit_state[unit] = {"active": False, "enabled": False}

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
            now=observed + timedelta(seconds=2),
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
        release._require_host_role("writer", observed_node="meghadharma-cloud.example")
        == release.WRITER_NODE
    )
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
    with pytest.raises(release.ReleaseContractError, match="not exactly empty"):
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


def test_writer_capacity_gate_binds_installed_proof_to_exact_source_sizes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state = tmp_path / "state"
    runtime_db = state / "state/runtime.db"
    tasks_db = state / "db/tasks.db"
    projection = state / "mission/status.json"
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
    receipt = tmp_path / "receipts/preactivation/standby-capacity.v1.json"
    monkeypatch.setattr(release, "SNAPSHOT_ROOT", str(snapshot_root))
    monkeypatch.setattr(release, "STATE_ROOT", str(state))
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
    admitted = release.guard_standby_capacity(
        role="writer",
        release_sha="a" * 40,
        projection_path=projection,
        receipt_path=receipt,
        now=observed + timedelta(seconds=2),
        observed_node=release.WRITER_NODE,
        expected_root_uid=os.geteuid(),
        expected_root_gid=os.getegid(),
    )
    assert admitted["standby_capacity_proven"] is True
    projection.write_bytes(projection.read_bytes() + b"drift")
    with pytest.raises(release.ReleaseContractError, match="source bytes drifted"):
        release.guard_standby_capacity(
            role="writer",
            release_sha="a" * 40,
            projection_path=projection,
            receipt_path=receipt,
            now=observed + timedelta(seconds=3),
            observed_node=release.WRITER_NODE,
            expected_root_uid=os.geteuid(),
            expected_root_gid=os.getegid(),
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


def test_standby_key_is_forced_to_write_only_snapshot_rrsync() -> None:
    algorithm = b"ssh-ed25519"
    key_blob = (
        len(algorithm).to_bytes(4, "big")
        + algorithm
        + (32).to_bytes(4, "big")
        + b"x" * 32
    )
    public_key = (
        "ssh-ed25519 " + base64.b64encode(key_blob).decode("ascii") + " snapshot-key"
    )
    rendered = release._restricted_authorized_key_bytes(public_key).decode("ascii")
    assert rendered.startswith(
        'restrict,command="/usr/bin/python3.12 /usr/bin/rrsync -wo -no-del '
        '/var/lib/dharma-sadhana/snapshot-incoming" ssh-ed25519 '
    )
    with pytest.raises(release.ReleaseContractError, match="exact ed25519"):
        release._restricted_authorized_key_bytes(
            "command=/bin/sh ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIFixture"
        )


def test_venv_rejects_copied_python_symlink_and_escaping_link(tmp_path: Path) -> None:
    venv = tmp_path / "venv"
    (venv / "bin").mkdir(parents=True)
    external = tmp_path / "python"
    external.write_text("#!/bin/sh\nprintf 'Python 3.12.9\\n'\n", encoding="utf-8")
    external.chmod(0o755)
    (venv / "bin" / "python").symlink_to(external)
    with pytest.raises(release.ReleaseContractError, match="copied"):
        release.verify_venv(venv)
    (venv / "bin" / "python").unlink()
    (venv / "bin" / "python").write_bytes(external.read_bytes())
    (venv / "bin" / "python").chmod(0o755)
    (venv / "escape").symlink_to(external)
    with pytest.raises(release.ReleaseContractError, match="escapes"):
        release.verify_venv(venv)

    root_link = tmp_path / "linked-venv"
    root_link.symlink_to(venv, target_is_directory=True)
    with pytest.raises(release.ReleaseContractError, match="root cannot be a symlink"):
        release.verify_venv(root_link)


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


def test_hash_pinned_uv_is_copied_from_wheel_without_path_or_pip(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    wheel = tmp_path / release.UV_WHEEL_FILE
    digest = _write_synthetic_uv_wheel(wheel)
    monkeypatch.setattr(release, "UV_WHEEL_SHA256", digest)
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
    assert binary.is_file()
    assert not binary.is_symlink()
    assert binary.read_bytes().startswith(b"\x7fELF")
    assert "uv-0.11.2" in str(binary)


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
            release_sha="a" * 40,
            runner=runner,
        )
    assert called is False


def test_candidate_git_helpers_never_execute_as_root(
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
    assert "os.fchown(staging_descriptor, 0, 0)" in stage_source
    assert "_rename_noreplace_at(" in stage_source
    isolated_source = inspect.getsource(release._invoke_isolated_build_plan)
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
