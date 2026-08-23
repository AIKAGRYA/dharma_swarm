from __future__ import annotations

import ast
import json
import os
from types import SimpleNamespace
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import scripts.runtime.sadhana_control_api as api_module
from dharma_swarm.mission_control_operator_control import (
    CONTROL_SCHEMA,
    decode_and_verify_envelope,
)
from scripts.runtime.sadhana_control_api import (
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
LOGIN = "operator@example.com"
ORIGIN = "https://sadhana.example.ts.net"
BEARER = b"operator-bearer-test-value-with-32-bytes"
HMAC_SECRET = b"operator-control-hmac-test-value-32-bytes"
CSRF_VALUE = "sadhana-10-20260823"


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


@pytest.fixture
def api(tmp_path: Path) -> tuple[TestClient, Path, Path]:
    normal = tmp_path / "control" / "normal"
    emergency = tmp_path / "control" / "emergency"
    normal.mkdir(parents=True)
    emergency.mkdir()
    config = ControlApiConfig(
        allowed_tailscale_login=LOGIN,
        expected_origin=ORIGIN,
        bearer_token=BEARER,
        hmac_secret=HMAC_SECRET,
        normal_inbox=normal,
        emergency_inbox=emergency,
    )
    app = create_app(config, now_fn=lambda: NOW)
    return TestClient(app, client=("127.0.0.1", 50000)), normal, emergency


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
    envelope = decode_and_verify_envelope(
        candidate.read_bytes(), secret=HMAC_SECRET, now=NOW
    )
    assert envelope.schema == CONTROL_SCHEMA
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
        normal_inbox=normal,
        emergency_inbox=emergency,
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
) -> None:
    credentials = tmp_path / "credentials"
    credentials.mkdir()
    (credentials / "operator_bearer").write_bytes(BEARER)
    (credentials / "control_hmac_key").write_bytes(HMAC_SECRET)
    login = credentials / "tailscale_operator_login"
    login.write_text(LOGIN, encoding="ascii")
    normal = tmp_path / "normal"
    emergency = tmp_path / "emergency"
    config = ControlApiConfig.from_environment(
        {
            "CREDENTIALS_DIRECTORY": str(credentials),
            "SADHANA_CONTROL_TAILSCALE_LOGIN_FILE": str(login),
            "SADHANA_CONTROL_EXPECTED_ORIGIN": ORIGIN,
            "SADHANA_CONTROL_NORMAL_INBOX": str(normal),
            "SADHANA_CONTROL_EMERGENCY_INBOX": str(emergency),
        }
    )
    rendered = repr(config)
    assert config.allowed_tailscale_login == LOGIN
    assert config.bearer_token == BEARER
    assert config.hmac_secret == HMAC_SECRET
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
        )


def test_bearer_maximum_is_exactly_512_bytes() -> None:
    ControlApiConfig(
        allowed_tailscale_login=LOGIN,
        expected_origin=ORIGIN,
        bearer_token=b"x" * MAX_BEARER_BYTES,
        hmac_secret=HMAC_SECRET,
    )
    with pytest.raises(ValueError, match="32-512"):
        ControlApiConfig(
            allowed_tailscale_login=LOGIN,
            expected_origin=ORIGIN,
            bearer_token=b"x" * (MAX_BEARER_BYTES + 1),
            hmac_secret=HMAC_SECRET,
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
        normal_inbox=normal,
        emergency_inbox=emergency,
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
