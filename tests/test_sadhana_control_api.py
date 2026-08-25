from __future__ import annotations

import ast
import hashlib
import json
import os
import stat
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import scripts.runtime.sadhana_control_api as api_module
from scripts.runtime import sadhana_release as release_module
from dharma_swarm.mission_control_operator_control import (
    CAMPAIGN_ACTIVATION_SCHEMA,
    CONTROL_SCHEMA,
    ControlAuthenticationError,
    decode_and_verify_envelope,
    derive_activation_bound_hmac_key,
)
from scripts.runtime.sadhana_control_api import (
    ACCOUNT_UI_CONFIRMATION_ENDPOINT,
    ACCOUNT_UI_CONFIRMATION_HTTP_BINDING_SHA256,
    CONTROL_ENDPOINT,
    CONTROL_HOST,
    CONTROL_PORT,
    MAX_BEARER_BYTES,
    MAX_HTTP_BODY_BYTES,
    OPERATOR_CONTROL_HTTP_BINDING_SHA256,
    ControlApiConfig,
    create_app,
)

NOW = datetime(2026, 8, 23, 0, 1, tzinfo=timezone.utc)
RELEASE_SHA = "a" * 40
LOGIN = "operator@example.com"
ORIGIN = "https://sadhana.example.ts.net"
BEARER = b"operator-bearer-test-value-with-32-bytes"
HMAC_SECRET = b"operator-control-hmac-test-value-32-bytes"
CSRF_VALUE = "sadhana-10-20260823"
ACTIVATION_PROOF_NAME = "campaign-activation.v1.json"


def _timestamp(value: datetime) -> str:
    return value.isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _request(
    action: str = "pause",
    *,
    request_id: str = "request-api-001",
    idempotency_key: str = "idempotency-api-001",
    reason: str = "Pause requested from authenticated mobile control",
    issued_at: datetime | None = None,
    expires_at: datetime | None = None,
) -> dict[str, object]:
    return {
        "action": action,
        "request_id": request_id,
        "idempotency_key": idempotency_key,
        "issued_at": _timestamp(issued_at or NOW - timedelta(seconds=5)),
        "expires_at": _timestamp(expires_at or NOW + timedelta(seconds=55)),
        "reason": reason,
    }


def _headers(**overrides: str) -> dict[str, str]:
    headers = {
        "Tailscale-User-Login": LOGIN,
        "Origin": ORIGIN,
        "X-Sadhana-CSRF": CSRF_VALUE,
        "Authorization": f"Bearer {BEARER.decode('ascii')}",
        "Content-Type": "application/json",
    }
    headers.update(overrides)
    return headers


def _account_ui_headers(**overrides: str) -> dict[str, str]:
    headers = _headers(**{"X-Sadhana-Release-SHA": RELEASE_SHA})
    headers.update(overrides)
    return headers


def _account_ui_request(
    *,
    client_request_id: str = "4b2d7f48-14a5-4eed-a814-62d08cb8d4b0",
    issued_at: datetime | None = None,
) -> dict[str, object]:
    issued = issued_at or NOW - timedelta(seconds=5)
    return {
        "schema_version": (
            "dharma.sadhana.authenticated_account_ui_confirmation_request.v1"
        ),
        "campaign_id": "sadhana-10-20260823",
        "client_request_id": client_request_id,
        "issued_at": _timestamp(issued),
        "expires_at": _timestamp(issued + timedelta(seconds=90)),
        "viewport_width_css_px_reported": 390,
        "document_width_css_px_reported": 390,
        "visual_viewport_width_css_px_reported": 390,
        "coarse_pointer_reported": True,
        "touch_capability_reported": True,
        "trusted_browser_event_reported": True,
        "explicit_confirmation_gesture_reported": True,
        "dashboard_rendered_reported": True,
    }


def _canonical_bytes(payload: object) -> bytes:
    return json.dumps(
        payload,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode()


def _write_account_ui_gate(
    path: Path,
    *,
    release_sha: str = RELEASE_SHA,
    activated_at: datetime = NOW - timedelta(minutes=1),
    predispatch_activation_receipt_digest: str = "sha256:" + "8" * 64,
) -> dict[str, object]:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload: dict[str, object] = {
        "schema_version": "dharma.sadhana.account_ui_predispatch_gate.v1",
        "campaign_id": "sadhana-10-20260823",
        "release_sha": release_sha,
        "activated_at": _timestamp(activated_at),
        "predispatch_activation_receipt_digest": (
            predispatch_activation_receipt_digest
        ),
        "dispatch_marker_absent": True,
        "dispatch_target_inactive": True,
        "supervisor_main_pid": 0,
        "provider_dispatch": "NoProviderDispatch",
        "receipt_digest": "",
    }
    unsigned = dict(payload)
    unsigned.pop("receipt_digest")
    payload["receipt_digest"] = (
        "sha256:" + hashlib.sha256(_canonical_bytes(unsigned)).hexdigest()
    )
    path.write_bytes(_canonical_bytes(payload) + b"\n")
    os.chown(path, -1, os.getegid())
    path.chmod(0o640)
    return payload


def _build_account_ui_api(
    tmp_path: Path,
    *,
    now_fn=None,
    before_publish=None,
    candidate_owner_uid: int | None = None,
    predispatch_owner_uid: int | None = None,
) -> tuple[TestClient, Path, Path, Path, Path, Path]:
    control = tmp_path / "account-control"
    normal = control / "normal"
    emergency = control / "emergency"
    candidate = control / "account-ui-confirmation" / "candidate.v2.json"
    gate = control / "account-ui-gate" / "predispatch-gate.v1.json"
    activation = control / "activation" / ACTIVATION_PROOF_NAME
    for directory in (normal, emergency, candidate.parent):
        directory.mkdir(parents=True, exist_ok=True)
        os.chown(directory, -1, os.getegid())
        directory.chmod(0o770)
    _write_account_ui_gate(gate)
    config = ControlApiConfig(
        allowed_tailscale_login=LOGIN,
        expected_origin=ORIGIN,
        bearer_token=BEARER,
        hmac_secret=HMAC_SECRET,
        release_sha=RELEASE_SHA,
        normal_inbox=normal,
        emergency_inbox=emergency,
        activation_proof_path=activation,
        account_ui_candidate_path=candidate,
        predispatch_gate_path=gate,
        predispatch_owner_uid=(
            os.geteuid()
            if predispatch_owner_uid is None
            else predispatch_owner_uid
        ),
        predispatch_owner_gid=os.getegid(),
        candidate_directory_owner_uid=os.geteuid(),
        candidate_owner_uid=(
            os.geteuid() if candidate_owner_uid is None else candidate_owner_uid
        ),
        candidate_owner_gid=os.getegid(),
    )
    app = create_app(
        config,
        now_fn=now_fn or (lambda: NOW),
        before_account_ui_publish=before_publish,
    )
    return (
        TestClient(app, client=("127.0.0.1", 50000)),
        normal,
        emergency,
        candidate,
        gate,
        activation,
    )


def _write_activation_proof(
    path: Path,
    *,
    release_sha: str = RELEASE_SHA,
    transition_sequence: int = 2,
    activated_at: datetime = NOW,
    operator_login: str = LOGIN,
    raw: bytes | None = None,
) -> dict[str, object] | None:
    path.parent.mkdir(mode=0o750, parents=True, exist_ok=True)
    path.parent.chmod(0o750)
    if raw is not None:
        path.write_bytes(raw)
        path.chmod(0o640)
        return None
    payload: dict[str, object] = {
        "schema_version": CAMPAIGN_ACTIVATION_SCHEMA,
        "mission_id": "sadhana-10-20260823",
        "release_sha": release_sha,
        "config_digest": "sha256:" + "1" * 64,
        "campaign_generation": 1,
        "transition_sequence": transition_sequence,
        "control_state": "RUNNING",
        "action": "resume",
        "dispatch_enable_receipt_digest": "sha256:" + "2" * 64,
        "account_ui_confirmation_receipt_digest": "sha256:" + "3" * 64,
        "operator_login_sha256": hashlib.sha256(
            operator_login.encode("ascii")
        ).hexdigest(),
        "authority_receipt_ref": "runtime-receipt:activation-receipt-001",
        "authority_receipt_sha256": "sha256:" + "4" * 64,
        "activated_at": _timestamp(activated_at),
        "external_effect_performed": False,
        "receipt_digest": "",
    }
    canonical = dict(payload)
    canonical.pop("receipt_digest")
    payload["receipt_digest"] = (
        "sha256:"
        + hashlib.sha256(
            json.dumps(
                canonical,
                allow_nan=False,
                ensure_ascii=False,
                separators=(",", ":"),
                sort_keys=True,
            ).encode()
        ).hexdigest()
    )
    path.write_bytes(
        json.dumps(
            payload,
            allow_nan=False,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode()
        + b"\n"
    )
    path.chmod(0o640)
    return payload


def _build_api(
    tmp_path: Path,
    *,
    activation_sequence: int = 2,
    activation_raw: bytes | None = None,
    now: datetime = NOW,
) -> tuple[TestClient, Path, Path, Path]:
    normal = tmp_path / "control" / "normal"
    emergency = tmp_path / "control" / "emergency"
    activation = tmp_path / "control" / "activation" / ACTIVATION_PROOF_NAME
    normal.mkdir(parents=True)
    emergency.mkdir()
    _write_activation_proof(
        activation,
        transition_sequence=activation_sequence,
        raw=activation_raw,
    )
    activation_parent = activation.parent.stat()
    config = ControlApiConfig(
        allowed_tailscale_login=LOGIN,
        expected_origin=ORIGIN,
        bearer_token=BEARER,
        hmac_secret=HMAC_SECRET,
        release_sha=RELEASE_SHA,
        normal_inbox=normal,
        emergency_inbox=emergency,
        activation_proof_path=activation,
        activation_owner_uid=activation_parent.st_uid,
        activation_group_gid=activation_parent.st_gid,
    )
    app = create_app(config, now_fn=lambda: now)
    return (
        TestClient(app, client=("127.0.0.1", 50000)),
        normal,
        emergency,
        activation,
    )


@pytest.fixture
def api(tmp_path: Path) -> tuple[TestClient, Path, Path]:
    client, normal, emergency, _activation = _build_api(tmp_path)
    return client, normal, emergency


def test_account_ui_confirmation_records_only_fixed_non_authoritative_candidate(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    client, normal, emergency, candidate, _gate, _activation = (
        _build_account_ui_api(tmp_path)
    )
    before = (
        tuple((item.name, item.stat().st_ino) for item in normal.iterdir()),
        tuple((item.name, item.stat().st_ino) for item in emergency.iterdir()),
    )
    response = client.post(
        ACCOUNT_UI_CONFIRMATION_ENDPOINT,
        headers=_account_ui_headers(),
        json=_account_ui_request(),
    )

    assert response.status_code == 202
    assert response.json() == {
        "status": "account_ui_confirmation_accepted",
        "replayed": False,
        "account_authenticated": True,
        "candidate_recorded": True,
        "authority_applied": False,
        "dispatch_authorized": False,
        "physical_device_attested": False,
        "human_identity_attested": False,
    }
    assert response.headers["cache-control"] == "no-store"
    raw = candidate.read_bytes()
    payload = json.loads(raw)
    assert raw == _canonical_bytes(payload) + b"\n"
    assert payload["schema_version"] == (
        "dharma.sadhana.authenticated_account_ui_confirmation_candidate.v2"
    )
    assert payload["operator_login_sha256"] == hashlib.sha256(
        LOGIN.encode("ascii")
    ).hexdigest()
    assert payload["normal_inbox_empty_ledger_sha256"] == (
        api_module._empty_inbox_ledger_sha256()
    )
    assert payload["emergency_inbox_empty_ledger_sha256"] == (
        api_module._empty_inbox_ledger_sha256()
    )
    assert "control_inboxes_empty_at_candidate_commit" not in payload
    assert payload["control_inboxes_empty_at_last_prepublication_scan"] is True
    assert payload["physical_device_attested"] is False
    assert payload["human_identity_attested"] is False
    assert payload["hmac_sha256"] == api_module._account_ui_candidate_mac(
        payload, HMAC_SECRET
    )
    assert payload["hmac_sha256"].startswith("hmac-sha256:")
    assert set(item.name for item in candidate.parent.iterdir()) == {candidate.name}
    after = (
        tuple((item.name, item.stat().st_ino) for item in normal.iterdir()),
        tuple((item.name, item.stat().st_ino) for item in emergency.iterdir()),
    )
    assert before == after == ((), ())
    rendered = raw.decode() + response.text + caplog.text
    assert LOGIN not in rendered
    assert BEARER.decode() not in rendered
    assert HMAC_SECRET.decode() not in rendered


@pytest.mark.parametrize(
    "late_control_write",
    [False, True],
    ids=("quiet-inboxes-promote", "post-scan-control-write-rejected"),
)
def test_account_ui_producer_and_root_consumer_interoperate_byte_for_byte(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    late_control_write: bool,
) -> None:
    client, normal, emergency, candidate, gate, _activation = (
        _build_account_ui_api(tmp_path)
    )
    root_custody = tmp_path / "root-custody"
    root_custody.mkdir(mode=0o700)
    activation_receipt = root_custody / "predispatch-activation.v1.json"
    activation_payload = {
        field: None for field in release_module._PREDISPATCH_ACTIVATION_FIELDS
    }
    activation_payload.update(
        {
            "schema_version": release_module.PREDISPATCH_ACTIVATION_SCHEMA_VERSION,
            "campaign_id": release_module.MISSION_ID,
            "release_sha": RELEASE_SHA,
            "activated_at": _timestamp(NOW - timedelta(minutes=1)),
            "dispatch_marker_absent": True,
            "dispatch_target_inactive": True,
            "supervisor_main_pid": 0,
            "provider_dispatch": "NoProviderDispatch",
            "receipt_digest": "",
        }
    )
    activation_payload["receipt_digest"] = release_module._canonical_self_digest(
        activation_payload, "receipt_digest"
    )
    activation_receipt.write_bytes(
        release_module._canonical_bytes(activation_payload) + b"\n"
    )
    os.chown(activation_receipt, -1, os.getegid())
    activation_receipt.chmod(0o600)
    activation_identity = activation_receipt.stat()
    assert (
        activation_identity.st_uid,
        activation_identity.st_gid,
        stat.S_IMODE(activation_identity.st_mode),
        activation_identity.st_nlink,
    ) == (os.geteuid(), os.getegid(), 0o600, 1)
    assert stat.S_ISREG(activation_identity.st_mode)
    assert not activation_receipt.is_symlink()
    assert 0 < activation_identity.st_size <= release_module._MAX_JSON_BYTES
    _write_account_ui_gate(
        gate,
        predispatch_activation_receipt_digest=str(
            activation_payload["receipt_digest"]
        ),
    )
    late_request = normal / "late-control-request.json"
    if late_control_write:
        original_inbox_scan = api_module._inbox_ledger_sha256
        scan_count = 0

        def inject_after_last_prepublication_scan(
            path: Path, *, config: ControlApiConfig
        ) -> str:
            nonlocal scan_count
            digest = original_inbox_scan(path, config=config)
            scan_count += 1
            if scan_count == 4:
                late_request.write_bytes(b"late control request remains\n")
            return digest

        monkeypatch.setattr(
            api_module,
            "_inbox_ledger_sha256",
            inject_after_last_prepublication_scan,
        )
    produced = client.post(
        ACCOUNT_UI_CONFIRMATION_ENDPOINT,
        headers=_account_ui_headers(),
        json=_account_ui_request(),
    )
    assert produced.status_code == 202
    produced_raw = candidate.read_bytes()
    produced_candidate = json.loads(produced_raw)
    assert "control_inboxes_empty_at_candidate_commit" not in produced_candidate
    assert (
        produced_candidate["control_inboxes_empty_at_last_prepublication_scan"]
        is True
    )

    login_source = root_custody / "tailscale_operator_login"
    hmac_source = root_custody / "control_hmac_key"
    login_source.write_text(LOGIN, encoding="ascii")
    hmac_source.write_bytes(HMAC_SECRET)
    os.chown(login_source, -1, os.getegid())
    os.chown(hmac_source, -1, os.getegid())
    login_source.chmod(0o600)
    hmac_source.chmod(0o600)
    receipt_root = root_custody / "receipts"
    receipt_root.mkdir(mode=0o700)
    final_receipt = receipt_root / "authenticated-account-ui-confirmation.v1.json"
    absent_root = root_custody / "absent"
    monkeypatch.setattr(release_module, "ACCOUNT_UI_CONFIRMATION_ROOT", candidate.parent)
    monkeypatch.setattr(release_module, "ACCOUNT_UI_CONFIRMATION_CANDIDATE", candidate)
    monkeypatch.setattr(release_module, "PREDISPATCH_ACCOUNT_UI_GATE", gate)
    monkeypatch.setattr(
        release_module,
        "PREDISPATCH_ACTIVATION_RECEIPT",
        activation_receipt,
    )
    monkeypatch.setattr(
        release_module, "ACCOUNT_UI_CONFIRMATION_RECEIPT", final_receipt
    )
    monkeypatch.setattr(release_module, "CONTROL_LOGIN_SOURCE", login_source)
    monkeypatch.setattr(release_module, "CONTROL_HMAC_SOURCE", hmac_source)
    monkeypatch.setattr(release_module, "CONTROL_NORMAL_INBOX", normal)
    monkeypatch.setattr(release_module, "CONTROL_EMERGENCY_INBOX", emergency)
    for name in (
        "DISPATCH_ENABLE_MARKER",
        "ROLLBACK_RECEIPT",
        "EMERGENCY_STOP_MARKER",
        "CAMPAIGN_ACTIVATION_PROOF",
    ):
        monkeypatch.setattr(release_module, name, absent_root / name.lower())
    monkeypatch.setattr(
        release_module,
        "_require_account_ui_predispatch_fences",
        lambda **_kwargs: None,
    )
    monkeypatch.setattr(release_module, "_control_expected_origin", lambda: ORIGIN)
    control_account = SimpleNamespace(pw_uid=os.geteuid(), pw_gid=os.getegid())
    monkeypatch.setattr(
        release_module.pwd,
        "getpwnam",
        lambda name: control_account
        if name == "dharma-sadhana-control"
        else (_ for _ in ()).throw(KeyError(name)),
    )

    if late_control_write:
        assert produced.json()["authority_applied"] is False
        assert produced.json()["dispatch_authorized"] is False
        with pytest.raises(
            release_module.ReleaseContractError,
            match="account UI confirmation found a control request",
        ):
            release_module.consume_account_ui_confirmation(
                role="writer",
                release_sha=RELEASE_SHA,
                now=NOW,
                observed_node=release_module.WRITER_NODE,
                expected_root_uid=os.geteuid(),
                expected_root_gid=os.getegid(),
            )
        assert late_request.read_bytes() == b"late control request remains\n"
        assert stat.S_IMODE(candidate.stat().st_mode) == 0o600
        assert stat.S_IMODE(candidate.parent.stat().st_mode) == 0o770
        assert not final_receipt.exists()
        return

    consumed = release_module.consume_account_ui_confirmation(
        role="writer",
        release_sha=RELEASE_SHA,
        now=NOW,
        observed_node=release_module.WRITER_NODE,
        expected_root_uid=os.geteuid(),
        expected_root_gid=os.getegid(),
    )
    replayed = release_module.consume_account_ui_confirmation(
        role="writer",
        release_sha=RELEASE_SHA,
        now=NOW,
        observed_node=release_module.WRITER_NODE,
        expected_root_uid=os.geteuid(),
        expected_root_gid=os.getegid(),
    )

    assert replayed == consumed
    assert consumed["source_candidate_sha256"] == hashlib.sha256(
        produced_raw
    ).hexdigest()
    assert consumed["physical_device_attested"] is False
    assert consumed["human_identity_attested"] is False
    assert consumed["normal_and_emergency_inboxes_unchanged"] is True
    assert candidate.read_bytes() == produced_raw
    assert stat.S_IMODE(candidate.stat().st_mode) == 0o400
    assert stat.S_IMODE(candidate.parent.stat().st_mode) == 0o700
    final_raw = final_receipt.read_bytes()
    assert final_raw == release_module._canonical_bytes(consumed) + b"\n"
    assert LOGIN.encode() not in final_raw
    assert HMAC_SECRET not in final_raw
    assert not list(normal.iterdir())
    assert not list(emergency.iterdir())


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("schema_version", "dharma.sadhana.wrong.v1"),
        ("campaign_id", "foreign-campaign"),
        ("client_request_id", "not-a-uuid4"),
        ("viewport_width_css_px_reported", 389),
        ("viewport_width_css_px_reported", 391),
        ("viewport_width_css_px_reported", 390.0),
        ("document_width_css_px_reported", 391),
        ("visual_viewport_width_css_px_reported", 389.999),
        ("coarse_pointer_reported", False),
        ("touch_capability_reported", False),
        ("trusted_browser_event_reported", False),
        ("explicit_confirmation_gesture_reported", False),
        ("dashboard_rendered_reported", False),
    ],
)
def test_account_ui_confirmation_rejects_false_or_inexact_client_reports(
    tmp_path: Path, field: str, value: object
) -> None:
    client, normal, emergency, candidate, _gate, _activation = (
        _build_account_ui_api(tmp_path)
    )
    payload = _account_ui_request()
    payload[field] = value

    response = client.post(
        ACCOUNT_UI_CONFIRMATION_ENDPOINT,
        headers=_account_ui_headers(),
        json=payload,
    )

    assert response.status_code == 422
    assert not candidate.exists()
    assert not list(normal.iterdir())
    assert not list(emergency.iterdir())


@pytest.mark.parametrize(
    ("header", "value", "status"),
    [
        ("Authorization", "", 401),
        ("Authorization", "Bearer wrong-wrong-wrong-wrong-wrong", 401),
        ("Tailscale-User-Login", "attacker@example.com", 403),
        ("Origin", "https://evil.example", 403),
        ("X-Sadhana-CSRF", "wrong", 403),
        ("X-Sadhana-Release-SHA", "b" * 40, 403),
        ("Content-Type", "application/json; charset=utf-8", 415),
    ],
)
def test_account_ui_confirmation_rejects_forged_bridge_headers(
    tmp_path: Path, header: str, value: str, status: int
) -> None:
    client, normal, emergency, candidate, _gate, _activation = (
        _build_account_ui_api(tmp_path)
    )
    headers = _account_ui_headers()
    headers[header] = value
    response = client.post(
        ACCOUNT_UI_CONFIRMATION_ENDPOINT,
        headers=headers,
        content=_canonical_bytes(_account_ui_request()),
    )

    assert response.status_code == status
    assert not candidate.exists()
    assert not list(normal.iterdir())
    assert not list(emergency.iterdir())


def test_account_ui_confirmation_direct_internal_post_without_bearer_is_denied(
    tmp_path: Path,
) -> None:
    client, normal, emergency, candidate, _gate, _activation = (
        _build_account_ui_api(tmp_path)
    )
    headers = _account_ui_headers()
    headers.pop("Authorization")
    response = client.post(
        ACCOUNT_UI_CONFIRMATION_ENDPOINT,
        headers=headers,
        json=_account_ui_request(),
    )
    assert response.status_code == 401
    assert response.json()["error_code"] == "bearer_invalid"
    assert not candidate.exists()
    assert not list(normal.iterdir())
    assert not list(emergency.iterdir())


@pytest.mark.parametrize(
    "issued_at",
    [NOW - timedelta(seconds=61), NOW + timedelta(seconds=16)],
)
def test_account_ui_confirmation_rejects_stale_or_future_request(
    tmp_path: Path, issued_at: datetime
) -> None:
    client, normal, emergency, candidate, _gate, _activation = (
        _build_account_ui_api(tmp_path)
    )
    response = client.post(
        ACCOUNT_UI_CONFIRMATION_ENDPOINT,
        headers=_account_ui_headers(),
        json=_account_ui_request(issued_at=issued_at),
    )
    assert response.status_code == 422
    assert response.json()["error_code"] == "account_ui_confirmation_not_fresh"
    assert not candidate.exists()
    assert not list(normal.iterdir())
    assert not list(emergency.iterdir())


def test_account_ui_confirmation_rejects_extra_and_duplicate_fields(
    tmp_path: Path,
) -> None:
    client, normal, emergency, candidate, _gate, _activation = (
        _build_account_ui_api(tmp_path)
    )
    extra = _account_ui_request()
    extra["physical_device_attested"] = True
    extra_response = client.post(
        ACCOUNT_UI_CONFIRMATION_ENDPOINT,
        headers=_account_ui_headers(),
        json=extra,
    )
    duplicate = _canonical_bytes(_account_ui_request())[:-1] + (
        b',"coarse_pointer_reported":true}'
    )
    duplicate_response = client.post(
        ACCOUNT_UI_CONFIRMATION_ENDPOINT,
        headers=_account_ui_headers(),
        content=duplicate,
    )
    assert extra_response.status_code == 422
    assert duplicate_response.status_code == 400
    assert duplicate_response.json()["error_code"] == "request_body_duplicate_key"
    assert not candidate.exists()
    assert not list(normal.iterdir())
    assert not list(emergency.iterdir())


def test_account_ui_confirmation_revalidates_gate_and_freshness_after_hook(
    tmp_path: Path,
) -> None:
    activation_holder: dict[str, Path] = {}

    def marker_race() -> None:
        activation = activation_holder["path"]
        activation.parent.mkdir(parents=True, exist_ok=True)
        activation.write_bytes(b"marker")

    client, normal, emergency, candidate, _gate, activation = _build_account_ui_api(
        tmp_path,
        before_publish=marker_race,
    )
    activation_holder["path"] = activation
    response = client.post(
        ACCOUNT_UI_CONFIRMATION_ENDPOINT,
        headers=_account_ui_headers(),
        json=_account_ui_request(),
    )
    assert response.status_code == 423
    assert response.json()["error_code"] == "predispatch_state_not_quiet"
    assert not candidate.exists()
    assert not list(normal.iterdir())
    assert not list(emergency.iterdir())

    later = NOW + timedelta(seconds=90)
    samples = iter((NOW, later))
    fresh_client, fresh_normal, fresh_emergency, fresh_candidate, _gate, _activation = (
        _build_account_ui_api(
            tmp_path / "freshness",
            now_fn=lambda: next(samples),
        )
    )
    stale_after_hook = fresh_client.post(
        ACCOUNT_UI_CONFIRMATION_ENDPOINT,
        headers=_account_ui_headers(),
        json=_account_ui_request(),
    )
    assert stale_after_hook.status_code == 503
    assert not fresh_candidate.exists()
    assert not list(fresh_normal.iterdir())
    assert not list(fresh_emergency.iterdir())


@pytest.mark.parametrize("mutation", ["release", "campaign", "digest"])
def test_account_ui_confirmation_rejects_wrong_or_tampered_predispatch_gate(
    tmp_path: Path, mutation: str
) -> None:
    client, normal, emergency, candidate, gate, _activation = _build_account_ui_api(
        tmp_path
    )
    payload = json.loads(gate.read_text(encoding="utf-8"))
    if mutation == "release":
        payload["release_sha"] = "b" * 40
    elif mutation == "campaign":
        payload["campaign_id"] = "foreign-campaign"
    else:
        payload["receipt_digest"] = "sha256:" + "0" * 64
    if mutation != "digest":
        unsigned = dict(payload)
        unsigned.pop("receipt_digest")
        payload["receipt_digest"] = (
            "sha256:" + hashlib.sha256(_canonical_bytes(unsigned)).hexdigest()
        )
    gate.write_bytes(_canonical_bytes(payload) + b"\n")
    gate.chmod(0o640)
    response = client.post(
        ACCOUNT_UI_CONFIRMATION_ENDPOINT,
        headers=_account_ui_headers(),
        json=_account_ui_request(),
    )
    assert response.status_code == 423
    assert response.json()["error_code"] == "predispatch_state_binding_invalid"
    assert not candidate.exists()
    assert not list(normal.iterdir())
    assert not list(emergency.iterdir())


def test_account_ui_confirmation_requires_empty_last_prepublication_scan(
    tmp_path: Path,
) -> None:
    normal_holder: dict[str, Path] = {}

    def control_race() -> None:
        (normal_holder["path"] / "raced.control.json").write_text(
            "raced", encoding="ascii"
        )

    client, normal, emergency, candidate, _gate, _activation = _build_account_ui_api(
        tmp_path,
        before_publish=control_race,
    )
    normal_holder["path"] = normal
    response = client.post(
        ACCOUNT_UI_CONFIRMATION_ENDPOINT,
        headers=_account_ui_headers(),
        json=_account_ui_request(),
    )
    assert response.status_code == 503
    assert response.json()["error_code"] == "control_inbox_not_empty"
    assert not candidate.exists()
    assert not list(emergency.iterdir())


def test_account_ui_confirmation_exact_replay_and_concurrent_replay_are_stable(
    tmp_path: Path,
) -> None:
    client, normal, emergency, candidate, _gate, _activation = (
        _build_account_ui_api(tmp_path)
    )
    second_client = TestClient(client.app, client=("127.0.0.1", 50001))
    payload = _account_ui_request()

    def submit(test_client: TestClient):
        return test_client.post(
            ACCOUNT_UI_CONFIRMATION_ENDPOINT,
            headers=_account_ui_headers(),
            json=payload,
        )

    with ThreadPoolExecutor(max_workers=2) as executor:
        responses = list(executor.map(submit, (client, second_client)))
    identity = candidate.stat()
    replay = submit(client)
    different = submit(
        TestClient(client.app, client=("127.0.0.1", 50002))
    )
    # Replace only the client request id to prove a second one-shot cannot win.
    conflict = client.post(
        ACCOUNT_UI_CONFIRMATION_ENDPOINT,
        headers=_account_ui_headers(),
        json=_account_ui_request(
            client_request_id="34cc8281-e68d-4a26-82fd-66e01281255d"
        ),
    )
    after = candidate.stat()

    assert [response.status_code for response in responses] == [202, 202]
    assert sorted(response.json()["replayed"] for response in responses) == [False, True]
    assert replay.status_code == 202 and replay.json()["replayed"] is True
    assert different.status_code == 202 and different.json()["replayed"] is True
    assert conflict.status_code == 409
    assert conflict.json()["error_code"] == (
        "account_ui_confirmation_candidate_conflict"
    )
    assert (identity.st_ino, identity.st_mtime_ns) == (
        after.st_ino,
        after.st_mtime_ns,
    )
    assert not list(normal.iterdir())
    assert not list(emergency.iterdir())


@pytest.mark.parametrize("custody", ["symlink", "hardlink", "mode", "owner"])
def test_account_ui_confirmation_rejects_unsafe_candidate_custody(
    tmp_path: Path, custody: str
) -> None:
    client, normal, emergency, candidate, _gate, _activation = (
        _build_account_ui_api(
            tmp_path,
            candidate_owner_uid=(os.geteuid() + 1 if custody == "owner" else None),
        )
    )
    if custody == "symlink":
        foreign = tmp_path / "foreign-candidate"
        foreign.write_bytes(b"foreign")
        candidate.symlink_to(foreign)
    elif custody == "hardlink":
        foreign = tmp_path / "foreign-candidate"
        foreign.write_bytes(b"{}\n")
        foreign.chmod(0o600)
        os.link(foreign, candidate)
    elif custody == "mode":
        candidate.write_bytes(b"{}\n")
        candidate.chmod(0o644)
    response = client.post(
        ACCOUNT_UI_CONFIRMATION_ENDPOINT,
        headers=_account_ui_headers(),
        json=_account_ui_request(),
    )
    assert response.status_code == 503
    assert not list(normal.iterdir())
    assert not list(emergency.iterdir())


@pytest.mark.parametrize("custody", ["symlink", "hardlink", "mode", "owner"])
def test_account_ui_confirmation_rejects_unsafe_gate_custody(
    tmp_path: Path, custody: str
) -> None:
    client, normal, emergency, candidate, gate, _activation = _build_account_ui_api(
        tmp_path,
        predispatch_owner_uid=(os.geteuid() + 1 if custody == "owner" else None),
    )
    if custody == "symlink":
        foreign = tmp_path / "foreign-gate"
        foreign.write_bytes(gate.read_bytes())
        gate.unlink()
        gate.symlink_to(foreign)
    elif custody == "hardlink":
        foreign = tmp_path / "foreign-gate"
        gate.replace(foreign)
        os.link(foreign, gate)
    elif custody == "mode":
        gate.chmod(0o600)
    response = client.post(
        ACCOUNT_UI_CONFIRMATION_ENDPOINT,
        headers=_account_ui_headers(),
        json=_account_ui_request(),
    )
    assert response.status_code == 423
    assert not candidate.exists()
    assert not list(normal.iterdir())
    assert not list(emergency.iterdir())


def test_valid_pause_is_only_request_accepted_and_writes_canonical_candidate(
    api: tuple[TestClient, Path, Path],
) -> None:
    client, normal, emergency = api
    response = client.post(CONTROL_ENDPOINT, headers=_headers(), json=_request())

    assert response.status_code == 202
    payload = response.json()
    digest = payload.pop("source_envelope_sha256")
    assert digest.startswith("sha256:") and len(digest) == 71
    assert payload == {
        "status": "request_accepted",
        "request_id": "request-api-001",
        "idempotency_key": "idempotency-api-001",
        "action": "pause",
        "inbox": "normal",
        "replayed": False,
        "request_accepted": True,
        "applied": False,
        "decision_applied": False,
        "effect_executed": False,
    }
    assert response.headers["cache-control"] == "no-store"
    [candidate] = normal.glob("*.control.json")
    proof = json.loads(
        (normal.parent / "activation" / ACTIVATION_PROOF_NAME).read_text()
    )
    epoch_key = derive_activation_bound_hmac_key(HMAC_SECRET, proof["receipt_digest"])
    envelope = decode_and_verify_envelope(
        candidate.read_bytes(), secret=epoch_key, now=NOW
    )
    assert envelope.schema == CONTROL_SCHEMA
    assert set(envelope.as_dict()) == {
        "schema",
        "operator_login",
        "request",
        "hmac_sha256",
    }
    with pytest.raises(ControlAuthenticationError, match="verification"):
        decode_and_verify_envelope(candidate.read_bytes(), secret=HMAC_SECRET, now=NOW)
    assert envelope.operator_login == LOGIN
    assert envelope.request.request_id == "request-api-001"
    assert not candidate.read_bytes().endswith(b"\n")
    assert not list(emergency.iterdir())


def test_emergency_stop_uses_distinct_emergency_transport(
    api: tuple[TestClient, Path, Path],
) -> None:
    client, normal, emergency = api
    response = client.post(
        CONTROL_ENDPOINT,
        headers=_headers(),
        json=_request(
            "emergency_stop",
            request_id="request-stop",
            idempotency_key="idempotency-stop",
            reason="Emergency stop requested by operator",
        ),
    )
    assert response.status_code == 202
    assert response.json()["inbox"] == "emergency"
    assert response.json()["applied"] is False
    assert not list(normal.iterdir())
    [candidate] = emergency.glob("*.control.json")
    envelope = decode_and_verify_envelope(
        candidate.read_bytes(), secret=HMAC_SECRET, now=NOW
    )
    assert envelope.schema == CONTROL_SCHEMA


def test_predispatch_direct_post_without_activation_proof_creates_no_queue(
    tmp_path: Path,
) -> None:
    client, normal, emergency, activation = _build_api(tmp_path)
    activation.unlink()

    response = client.post(CONTROL_ENDPOINT, headers=_headers(), json=_request())

    assert response.status_code == 423
    assert response.json()["error_code"] == "normal_control_not_activated"
    assert not list(normal.iterdir())
    assert not list(emergency.iterdir())


@pytest.mark.parametrize("action", ["pause", "resume"])
def test_sequence_two_activation_admits_normal_pause_and_resume(
    tmp_path: Path,
    action: str,
) -> None:
    client, normal, emergency, activation = _build_api(tmp_path)
    proof = json.loads(activation.read_text(encoding="utf-8"))
    response = client.post(
        CONTROL_ENDPOINT,
        headers=_headers(),
        json=_request(
            action,
            request_id=f"request-seq2-{action}",
            idempotency_key=f"idempotency-seq2-{action}",
            reason=f"{action.title()} after typed sequence two activation",
        ),
    )

    assert response.status_code == 202
    [candidate] = normal.glob("*.control.json")
    epoch_key = derive_activation_bound_hmac_key(HMAC_SECRET, proof["receipt_digest"])
    envelope = decode_and_verify_envelope(
        candidate.read_bytes(), secret=epoch_key, now=NOW
    )
    assert envelope.schema == CONTROL_SCHEMA
    assert set(envelope.as_dict()) == {
        "schema",
        "operator_login",
        "request",
        "hmac_sha256",
    }
    assert not list(emergency.iterdir())


@pytest.mark.parametrize(
    ("sequence", "raw"),
    [
        (1, None),
        (2, b'{"schema_version":"malformed"'),
    ],
)
def test_activation_proof_sequence_one_or_malformed_rejects_normal_controls(
    tmp_path: Path,
    sequence: int,
    raw: bytes | None,
) -> None:
    client, normal, emergency, _activation = _build_api(
        tmp_path,
        activation_sequence=sequence,
        activation_raw=raw,
    )

    response = client.post(CONTROL_ENDPOINT, headers=_headers(), json=_request())

    assert response.status_code == 423
    assert response.json()["error_code"] == "normal_control_not_activated"
    assert not list(normal.iterdir())
    assert not list(emergency.iterdir())


def test_stale_foreign_release_activation_proof_rejects_normal_controls(
    tmp_path: Path,
) -> None:
    client, normal, emergency, activation = _build_api(tmp_path)
    _write_activation_proof(activation, release_sha="b" * 40)

    response = client.post(CONTROL_ENDPOINT, headers=_headers(), json=_request())

    assert response.status_code == 423
    assert not list(normal.iterdir())
    assert not list(emergency.iterdir())


def test_wrong_principal_activation_proof_rejects_normal_controls(
    tmp_path: Path,
) -> None:
    client, normal, emergency, activation = _build_api(tmp_path)
    _write_activation_proof(activation, operator_login="foreign@example.com")

    response = client.post(CONTROL_ENDPOINT, headers=_headers(), json=_request())

    assert response.status_code == 423
    assert not list(normal.iterdir())
    assert not list(emergency.iterdir())


def test_activation_proof_is_stale_at_campaign_stop_and_writes_nothing(
    tmp_path: Path,
) -> None:
    stopped = datetime(2026, 9, 1, 17, 15, 12, tzinfo=timezone.utc)
    client, normal, emergency, _activation = _build_api(tmp_path, now=stopped)

    response = client.post(CONTROL_ENDPOINT, headers=_headers(), json=_request())

    assert response.status_code == 423
    assert not list(normal.iterdir())
    assert not list(emergency.iterdir())


def test_activation_proof_metadata_toctou_rejects_before_normal_publication(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, normal, emergency, _activation = _build_api(tmp_path)
    original_fstat = api_module.os.fstat
    file_reads = 0

    def changing_fstat(descriptor: int):
        nonlocal file_reads
        identity = original_fstat(descriptor)
        if stat.S_ISREG(identity.st_mode):
            file_reads += 1
            if file_reads == 2:
                values = {
                    field: getattr(identity, field)
                    for field in (
                        "st_dev",
                        "st_ino",
                        "st_uid",
                        "st_gid",
                        "st_mode",
                        "st_nlink",
                        "st_size",
                        "st_mtime_ns",
                        "st_ctime_ns",
                    )
                }
                values["st_mtime_ns"] += 1
                return SimpleNamespace(**values)
        return identity

    monkeypatch.setattr(api_module.os, "fstat", changing_fstat)
    response = client.post(CONTROL_ENDPOINT, headers=_headers(), json=_request())

    assert response.status_code == 423
    assert not list(normal.iterdir())
    assert not list(emergency.iterdir())


def test_emergency_at_sequence_one_bypasses_only_the_normal_activation_gate(
    tmp_path: Path,
) -> None:
    client, normal, emergency, _activation = _build_api(
        tmp_path,
        activation_sequence=1,
    )
    response = client.post(
        CONTROL_ENDPOINT,
        headers=_headers(),
        json=_request(
            "emergency_stop",
            request_id="request-seq1-stop",
            idempotency_key="idempotency-seq1-stop",
            reason="Emergency stop requested before normal activation",
        ),
    )

    assert response.status_code == 202
    assert not list(normal.iterdir())
    assert len(list(emergency.glob("*.control.json"))) == 1


@pytest.mark.parametrize(
    ("headers", "status", "error_code"),
    [
        ({}, 403, "tailscale_identity_required"),
        (
            {"Tailscale-User-Login": "attacker@example.com"},
            403,
            "tailscale_identity_not_allowed",
        ),
        (
            {"Tailscale-User-Login": "tagged-node"},
            403,
            "tailscale_identity_not_allowed",
        ),
        ({"Origin": "https://evil.example"}, 403, "origin_mismatch"),
        ({"Origin": ""}, 403, "origin_mismatch"),
        ({"X-Sadhana-CSRF": "1"}, 403, "csrf_required"),
        ({"X-Sadhana-CSRF": " sadhana-10-20260823"}, 403, "csrf_required"),
        (
            {"Authorization": "Bearer wrong-wrong-wrong-wrong-wrong"},
            401,
            "bearer_invalid",
        ),
        ({"Authorization": ""}, 401, "bearer_invalid"),
        (
            {"Content-Type": "application/json; charset=utf-8"},
            415,
            "content_type_required",
        ),
    ],
)
def test_authentication_origin_bearer_csrf_and_content_type_fail_closed(
    api: tuple[TestClient, Path, Path],
    headers: dict[str, str],
    status: int,
    error_code: str,
) -> None:
    client, normal, emergency = api
    request_headers = _headers()
    if not headers:
        request_headers.pop("Tailscale-User-Login")
    else:
        request_headers.update(headers)
    response = client.post(
        CONTROL_ENDPOINT,
        headers=request_headers,
        content=json.dumps(_request()).encode(),
    )
    assert response.status_code == status
    assert response.json()["error_code"] == error_code
    assert not list(normal.iterdir())
    assert not list(emergency.iterdir())


@pytest.mark.parametrize(
    "duplicate_name",
    [
        "Tailscale-User-Login",
        "Origin",
        "X-Sadhana-CSRF",
        "Authorization",
        "Content-Type",
    ],
)
def test_duplicate_security_headers_are_rejected(
    api: tuple[TestClient, Path, Path], duplicate_name: str
) -> None:
    client, normal, emergency = api
    headers = list(_headers().items())
    original = dict(headers)[duplicate_name]
    headers.append((duplicate_name, original))
    response = client.post(
        CONTROL_ENDPOINT, headers=headers, content=json.dumps(_request()).encode()
    )
    assert response.status_code in {401, 403, 415}
    assert not list(normal.iterdir())
    assert not list(emergency.iterdir())


def test_non_loopback_peer_is_rejected_before_identity(
    api: tuple[TestClient, Path, Path],
) -> None:
    _, normal, emergency = api
    config = ControlApiConfig(
        allowed_tailscale_login=LOGIN,
        expected_origin=ORIGIN,
        bearer_token=BEARER,
        hmac_secret=HMAC_SECRET,
        release_sha=RELEASE_SHA,
        normal_inbox=normal,
        emergency_inbox=emergency,
        activation_proof_path=normal.parent / "activation" / ACTIVATION_PROOF_NAME,
        activation_owner_uid=os.geteuid(),
        activation_group_gid=os.getegid(),
    )
    client = TestClient(
        create_app(config, now_fn=lambda: NOW), client=("203.0.113.7", 50000)
    )
    headers = _headers(**{"X-Forwarded-For": "127.0.0.1", "X-Real-IP": "127.0.0.1"})
    response = client.post(CONTROL_ENDPOINT, headers=headers, json=_request())
    assert response.status_code == 403
    assert response.json()["error_code"] == "loopback_required"
    assert not list(normal.iterdir())


def test_forwarded_remote_address_does_not_override_loopback_peer(
    api: tuple[TestClient, Path, Path],
) -> None:
    client, normal, _ = api
    headers = _headers(**{"X-Forwarded-For": "203.0.113.9", "X-Real-IP": "203.0.113.9"})
    response = client.post(CONTROL_ENDPOINT, headers=headers, json=_request())
    assert response.status_code == 202
    assert len(list(normal.glob("*.control.json"))) == 1


def test_replay_is_accepted_without_rewrite_and_conflict_is_409(
    api: tuple[TestClient, Path, Path],
) -> None:
    client, normal, _ = api
    first = client.post(CONTROL_ENDPOINT, headers=_headers(), json=_request())
    [candidate] = normal.glob("*.control.json")
    before = candidate.stat()
    replay = client.post(CONTROL_ENDPOINT, headers=_headers(), json=_request())
    conflict = client.post(
        CONTROL_ENDPOINT,
        headers=_headers(),
        json=_request(reason="A different request under the same idempotency key"),
    )
    after = candidate.stat()

    assert first.status_code == 202
    assert replay.status_code == 202
    assert replay.json()["replayed"] is True
    assert conflict.status_code == 409
    assert conflict.json()["error_code"] == "idempotency_conflict"
    assert before.st_ino == after.st_ino
    assert before.st_mtime_ns == after.st_mtime_ns


@pytest.mark.parametrize("action", ["approve", "reject"])
def test_approval_actions_are_typed_unsupported_and_write_nothing(
    api: tuple[TestClient, Path, Path], action: str
) -> None:
    client, normal, emergency = api
    response = client.post(
        CONTROL_ENDPOINT,
        headers=_headers(),
        json={
            "action": action,
            "proposal_id": "proposal-1",
            "proposal_sha256": "sha256:" + "a" * 64,
            "requested_effect": {"kind": "publish"},
            "warrant": {"ref": "missing-authority-contract"},
        },
    )
    assert response.status_code == 501
    assert response.json() == {
        "status": "unsupported_action",
        "error_code": "proposal_effect_warrant_contract_unavailable",
        "action": action,
        "request_accepted": False,
        "decision_applied": False,
        "effect_executed": False,
    }
    assert not list(normal.iterdir())
    assert not list(emergency.iterdir())


def test_extra_fields_expiry_future_and_body_bound_are_rejected_without_write(
    api: tuple[TestClient, Path, Path],
) -> None:
    client, normal, _ = api
    extra = _request()
    extra["unexpected"] = True
    expired = _request(issued_at=NOW - timedelta(seconds=60), expires_at=NOW)
    future = _request(
        issued_at=NOW + timedelta(seconds=16),
        expires_at=NOW + timedelta(seconds=60),
    )
    for payload in (extra, expired, future):
        response = client.post(CONTROL_ENDPOINT, headers=_headers(), json=payload)
        assert response.status_code == 422
    oversize = b"{" + b'"padding":"' + b"x" * MAX_HTTP_BODY_BYTES + b'"}'
    response = client.post(CONTROL_ENDPOINT, headers=_headers(), content=oversize)
    assert response.status_code == 413
    assert not list(normal.iterdir())


def test_duplicate_json_field_and_non_post_method_write_nothing(
    api: tuple[TestClient, Path, Path],
) -> None:
    client, normal, _ = api
    body = b'{"action":"pause","action":"resume"}'
    duplicate = client.post(CONTROL_ENDPOINT, headers=_headers(), content=body)
    get = client.get(CONTROL_ENDPOINT, headers=_headers())
    assert duplicate.status_code == 400
    assert duplicate.json()["error_code"] == "request_body_duplicate_key"
    assert get.status_code == 405
    assert not list(normal.iterdir())


def test_environment_loads_three_nofollow_credentials_and_hides_values(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    credentials = tmp_path / "credentials"
    credentials.mkdir()
    (credentials / "operator_bearer").write_bytes(BEARER)
    (credentials / "control_hmac_key").write_bytes(HMAC_SECRET)
    login = credentials / "tailscale_operator_login"
    login.write_text(LOGIN, encoding="ascii")
    normal = tmp_path / "normal"
    emergency = tmp_path / "emergency"
    accounts = {
        "dharma-sadhana": SimpleNamespace(pw_uid=1201, pw_gid=1201),
        "dharma-sadhana-control": SimpleNamespace(pw_uid=1202, pw_gid=1202),
    }
    monkeypatch.setattr(api_module.pwd, "getpwnam", accounts.__getitem__)
    monkeypatch.setattr(
        api_module, "current_immutable_release_sha", lambda: RELEASE_SHA
    )
    config = ControlApiConfig.from_environment(
        {
            "CREDENTIALS_DIRECTORY": str(credentials),
            "SADHANA_CONTROL_TAILSCALE_LOGIN_FILE": str(login),
            "SADHANA_CONTROL_EXPECTED_ORIGIN": ORIGIN,
            "SADHANA_CONTROL_NORMAL_INBOX": str(normal),
            "SADHANA_CONTROL_EMERGENCY_INBOX": str(emergency),
            "SADHANA_ACCOUNT_UI_CONFIRMATION_HTTP_BINDING_SHA256": (
                ACCOUNT_UI_CONFIRMATION_HTTP_BINDING_SHA256
            ),
            "SADHANA_ACCOUNT_UI_CONFIRMATION_ENDPOINT": (
                ACCOUNT_UI_CONFIRMATION_ENDPOINT
            ),
            "SADHANA_RELEASE_SHA": RELEASE_SHA,
        }
    )
    rendered = repr(config)
    assert config.allowed_tailscale_login == LOGIN
    assert config.bearer_token == BEARER
    assert config.hmac_secret == HMAC_SECRET
    assert config.release_sha == RELEASE_SHA
    assert config.activation_owner_uid == 1201
    assert config.activation_group_gid == 1202
    assert LOGIN not in rendered
    assert BEARER.decode() not in rendered
    assert HMAC_SECRET.decode() not in rendered


@pytest.mark.parametrize(
    "origin",
    [
        "https://:",
        "https://sadhana.example.ts.net:443",
        "https://SADHANA.example.ts.net",
        "https://sadhana.example.ts.net/",
        "https://sadhana.example.ts.net/path",
        "https://sadhana.example.ts.net\n",
        "https://127.1",
        "https://01.2.3.4",
        "http://sadhana.example.ts.net",
    ],
)
def test_expected_origin_must_be_exact_canonical_https_origin(origin: str) -> None:
    with pytest.raises(ValueError, match="exact HTTPS origin|visible ASCII"):
        ControlApiConfig(
            allowed_tailscale_login=LOGIN,
            expected_origin=origin,
            bearer_token=BEARER,
            hmac_secret=HMAC_SECRET,
            release_sha=RELEASE_SHA,
        )


def test_bearer_maximum_is_exactly_512_bytes() -> None:
    ControlApiConfig(
        allowed_tailscale_login=LOGIN,
        expected_origin=ORIGIN,
        bearer_token=b"x" * MAX_BEARER_BYTES,
        hmac_secret=HMAC_SECRET,
        release_sha=RELEASE_SHA,
    )
    with pytest.raises(ValueError, match="32-512"):
        ControlApiConfig(
            allowed_tailscale_login=LOGIN,
            expected_origin=ORIGIN,
            bearer_token=b"x" * (MAX_BEARER_BYTES + 1),
            hmac_secret=HMAC_SECRET,
            release_sha=RELEASE_SHA,
        )


@pytest.mark.parametrize("credential_name", ["operator_bearer", "control_hmac_key"])
def test_symlink_or_hardlink_credential_is_rejected(
    tmp_path: Path, credential_name: str
) -> None:
    credentials = tmp_path / "credentials"
    credentials.mkdir()
    foreign = tmp_path / "foreign"
    foreign.write_bytes(BEARER if credential_name == "operator_bearer" else HMAC_SECRET)
    os.link(foreign, credentials / credential_name)
    other_name = (
        "control_hmac_key"
        if credential_name == "operator_bearer"
        else "operator_bearer"
    )
    (credentials / other_name).write_bytes(
        HMAC_SECRET if other_name == "control_hmac_key" else BEARER
    )
    login = credentials / "tailscale_operator_login"
    login.write_text(LOGIN, encoding="ascii")
    with pytest.raises(ValueError, match="unsafe custody"):
        ControlApiConfig.from_environment(
            {
                "CREDENTIALS_DIRECTORY": str(credentials),
                "SADHANA_CONTROL_TAILSCALE_LOGIN_FILE": str(login),
                "SADHANA_CONTROL_EXPECTED_ORIGIN": ORIGIN,
                "SADHANA_ACCOUNT_UI_CONFIRMATION_HTTP_BINDING_SHA256": (
                    ACCOUNT_UI_CONFIRMATION_HTTP_BINDING_SHA256
                ),
                "SADHANA_ACCOUNT_UI_CONFIRMATION_ENDPOINT": (
                    ACCOUNT_UI_CONFIRMATION_ENDPOINT
                ),
                "SADHANA_RELEASE_SHA": RELEASE_SHA,
            }
        )


def test_login_credential_symlink_is_rejected(tmp_path: Path) -> None:
    credentials = tmp_path / "credentials"
    credentials.mkdir()
    (credentials / "operator_bearer").write_bytes(BEARER)
    (credentials / "control_hmac_key").write_bytes(HMAC_SECRET)
    foreign = tmp_path / "login"
    foreign.write_text(LOGIN, encoding="ascii")
    login_link = credentials / "tailscale_operator_login"
    login_link.symlink_to(foreign)
    with pytest.raises(ValueError, match="unavailable"):
        ControlApiConfig.from_environment(
            {
                "CREDENTIALS_DIRECTORY": str(credentials),
                "SADHANA_CONTROL_TAILSCALE_LOGIN_FILE": str(login_link),
                "SADHANA_CONTROL_EXPECTED_ORIGIN": ORIGIN,
                "SADHANA_ACCOUNT_UI_CONFIRMATION_HTTP_BINDING_SHA256": (
                    ACCOUNT_UI_CONFIRMATION_HTTP_BINDING_SHA256
                ),
                "SADHANA_ACCOUNT_UI_CONFIRMATION_ENDPOINT": (
                    ACCOUNT_UI_CONFIRMATION_ENDPOINT
                ),
                "SADHANA_RELEASE_SHA": RELEASE_SHA,
            }
        )


@pytest.mark.parametrize("line_break", [b"\n", b"\r\n", b"\r"])
def test_credential_line_breaks_are_rejected_exactly(
    tmp_path: Path, line_break: bytes
) -> None:
    credential = tmp_path / "operator_bearer"
    credential.write_bytes(BEARER + line_break)
    with pytest.raises(ValueError, match="forbidden line break"):
        api_module._read_credential(
            credential, name="operator_bearer", printable_ascii=True
        )


def test_credential_reader_fails_when_nofollow_is_unavailable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    credential = tmp_path / "operator_bearer"
    credential.write_bytes(BEARER)
    monkeypatch.delattr(api_module.os, "O_NOFOLLOW")
    with pytest.raises(ValueError, match="no-follow"):
        api_module._read_credential(
            credential, name="operator_bearer", printable_ascii=True
        )


def test_credential_reader_rejects_same_size_metadata_mutation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    credential = tmp_path / "operator_bearer"
    credential.write_bytes(BEARER)
    original_fstat = api_module.os.fstat
    calls = 0

    def changing_fstat(descriptor: int):
        nonlocal calls
        identity = original_fstat(descriptor)
        calls += 1
        if calls == 1:
            return identity
        values = {
            field: getattr(identity, field)
            for field in (
                "st_dev",
                "st_ino",
                "st_mode",
                "st_nlink",
                "st_size",
                "st_mtime_ns",
                "st_ctime_ns",
            )
        }
        values["st_mtime_ns"] += 1
        return SimpleNamespace(**values)

    monkeypatch.setattr(api_module.os, "fstat", changing_fstat)
    with pytest.raises(ValueError, match="changed while reading"):
        api_module._read_credential(
            credential, name="operator_bearer", printable_ascii=True
        )


def test_response_and_source_do_not_log_or_expose_body_tokens_or_login(
    api: tuple[TestClient, Path, Path], caplog: pytest.LogCaptureFixture
) -> None:
    client, _, _ = api
    sensitive_reason = "private reason must not enter logs"
    response = client.post(
        CONTROL_ENDPOINT,
        headers=_headers(),
        json=_request(reason=sensitive_reason),
    )
    rendered = response.text + caplog.text
    assert response.status_code == 202
    assert sensitive_reason not in rendered
    assert BEARER.decode() not in rendered
    assert HMAC_SECRET.decode() not in rendered
    assert LOGIN not in rendered

    invalid_body = b'{"private":"body-token-must-not-return"'
    rejected = client.post(CONTROL_ENDPOINT, headers=_headers(), content=invalid_body)
    assert rejected.status_code == 400
    assert "body-token-must-not-return" not in rejected.text + caplog.text


def test_main_fixes_loopback_port_and_disables_access_logging(
    api: tuple[TestClient, Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    _, normal, emergency = api
    config = ControlApiConfig(
        allowed_tailscale_login=LOGIN,
        expected_origin=ORIGIN,
        bearer_token=BEARER,
        hmac_secret=HMAC_SECRET,
        release_sha=RELEASE_SHA,
        normal_inbox=normal,
        emergency_inbox=emergency,
        activation_proof_path=normal.parent / "activation" / ACTIVATION_PROOF_NAME,
        activation_owner_uid=os.geteuid(),
        activation_group_gid=os.getegid(),
    )
    call: dict[str, object] = {}

    monkeypatch.setattr(
        api_module.ControlApiConfig,
        "from_environment",
        classmethod(lambda cls: config),
    )

    def record_run(app, **kwargs):
        call.update({"app": app, **kwargs})

    monkeypatch.setattr(api_module.uvicorn, "run", record_run)
    api_module.main()
    assert call["host"] == "127.0.0.1"
    assert call["port"] == 18421
    assert call["access_log"] is False
    assert call["log_level"] == "warning"
    assert call["proxy_headers"] is False
    assert call["server_header"] is False
    assert call["date_header"] is False


def test_http_binding_hash_host_port_and_import_boundary_are_pinned() -> None:
    assert OPERATOR_CONTROL_HTTP_BINDING_SHA256 == (
        "sha256:9e1aec44c75cf6b24341389b8227f57fe4d4cf48328992f2125bffca34fcf3eb"
    )
    assert (CONTROL_HOST, CONTROL_PORT, CONTROL_ENDPOINT) == (
        "127.0.0.1",
        18421,
        "/v1/operator-control/requests",
    )
    source = Path("scripts/runtime/sadhana_control_api.py").read_text(encoding="utf-8")
    assert "X-Sadhana-Control" not in source
    imported: set[str] = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)
    forbidden = {
        "sqlite3",
        "aiosqlite",
        "subprocess",
        "logging",
        "dharma_swarm.mission_control_campaign",
        "dharma_swarm.mission_control_lifecycle",
        "dharma_swarm.runtime_state",
        "dharma_swarm.task_board",
        "dharma_swarm.providers",
        "dharma_swarm.tool_registry",
    }
    assert imported.isdisjoint(forbidden)
