#!/usr/bin/env python3
"""Loopback-only authenticated ingress for SADHANA operator controls.

The filesystem Next bridge is the immediate loopback proxy.  Tailscale Serve
injects ``Tailscale-User-Login`` into that bridge, which forwards only the exact
allowlisted headers.  This service separately requires one credential-bound
login, exact Origin, a campaign-bound CSRF header, and a bearer credential.  It
writes signed filesystem candidates only.  It never opens a database or invokes
a runtime, provider, tool, service manager, proposal effect, or external system.
"""

from __future__ import annotations

import fcntl
import hashlib
import hmac
import ipaddress
import json
import os
import pwd
import re
import stat
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from dharma_swarm.mission_control_operator_control import (
    DEFAULT_EMERGENCY_INBOX,
    DEFAULT_CAMPAIGN_ACTIVATION_PROOF,
    DEFAULT_NORMAL_INBOX,
    OPERATOR_CONTROL_HTTP_BINDING_SHA256 as _HTTP_BINDING_SHA256,
    UNSUPPORTED_DECISION_ACTIONS,
    ControlExpiredError,
    ControlAction,
    ControlFutureRequestError,
    ControlIdempotencyConflict,
    ControlInboxPublisher,
    ControlSchemaError,
    InboxUnavailable,
    OperatorControlRequest,
    UnsafeInboxEntry,
    current_immutable_release_sha,
    derive_activation_bound_hmac_key,
    utc_now,
    validate_campaign_activation_proof,
    validate_operator_login,
)

CONTROL_HOST = "127.0.0.1"
CONTROL_PORT = 18421
CONTROL_ENDPOINT = "/v1/operator-control/requests"
ACCOUNT_UI_CONFIRMATION_ENDPOINT = "/v1/account-ui-confirmations"
TAILSCALE_LOGIN_HEADER = b"tailscale-user-login"
ORIGIN_HEADER = b"origin"
AUTHORIZATION_HEADER = b"authorization"
CSRF_HEADER = b"x-sadhana-csrf"
CSRF_VALUE = b"sadhana-10-20260823"
CONTENT_TYPE_HEADER = b"content-type"
RELEASE_SHA_HEADER = b"x-sadhana-release-sha"
MAX_HTTP_BODY_BYTES = 4096
MAX_BEARER_BYTES = 512
MAX_HMAC_CREDENTIAL_BYTES = 4096
OPERATOR_BEARER_CREDENTIAL = "operator_bearer"
CONTROL_HMAC_CREDENTIAL = "control_hmac_key"
TAILSCALE_LOGIN_CREDENTIAL = "tailscale_operator_login"
OPERATOR_CONTROL_HTTP_BINDING_SHA256 = _HTTP_BINDING_SHA256
ACCOUNT_UI_CONFIRMATION_HTTP_BINDING_SHA256 = (
    "60996ccfa8de0db715d26ecf062d13604e09ab019c51d9047cb250e39652dad1"
)
ACCOUNT_UI_CONFIRMATION_HTTP_BINDING_CANONICAL = (
    "schema=dharma.sadhana.account_ui_confirmation_http_binding.v1;method=POST;"
    "browser_route=/dharma-internal/account-ui-confirmation;internal_url="
    "http://127.0.0.1:18421/v1/account-ui-confirmations;headers=authorization,"
    "content-type,origin,tailscale-user-login,x-sadhana-csrf,x-sadhana-release-sha;"
    "request_schema=dharma.sadhana.authenticated_account_ui_confirmation_request.v1;"
    "request_fields=campaign_id,client_request_id,coarse_pointer_reported,"
    "dashboard_rendered_reported,document_width_css_px_reported,expires_at,"
    "explicit_confirmation_gesture_reported,issued_at,schema_version,"
    "touch_capability_reported,trusted_browser_event_reported,"
    "viewport_width_css_px_reported,visual_viewport_width_css_px_reported;"
    "response_fields=account_authenticated,authority_applied,candidate_recorded,"
    "dispatch_authorized,human_identity_attested,physical_device_attested,replayed,"
    "status;http_202=CandidateRecorded<NoAuthority,NoDispatch>;"
    "candidate=fixed-path-o_excl;mac=derived-domain-separated-hmac-sha256"
)
if (
    hashlib.sha256(ACCOUNT_UI_CONFIRMATION_HTTP_BINDING_CANONICAL.encode()).hexdigest()
    != ACCOUNT_UI_CONFIRMATION_HTTP_BINDING_SHA256
):
    raise RuntimeError("account UI confirmation HTTP binding digest differs")
MISSION_ID = "sadhana-10-20260823"
CAMPAIGN_STOP_UTC = datetime(2026, 9, 1, 17, 15, 12, tzinfo=timezone.utc)
ACCOUNT_UI_CONFIRMATION_REQUEST_SCHEMA = (
    "dharma.sadhana.authenticated_account_ui_confirmation_request.v1"
)
ACCOUNT_UI_CONFIRMATION_CANDIDATE_SCHEMA = (
    "dharma.sadhana.authenticated_account_ui_confirmation_candidate.v2"
)
ACCOUNT_UI_CONFIRMATION_MAC_DOMAIN = (
    b"dharma.sadhana.authenticated_account_ui_confirmation_candidate.v2\x00"
)
ACCOUNT_UI_CONFIRMATION_KEY_DOMAIN = (
    b"dharma.sadhana.authenticated_account_ui_confirmation_key.v2\x00"
)
ACCOUNT_UI_CONFIRMATION_ROOT = Path(
    "/run/dharma-sadhana/control/account-ui-confirmation"
)
ACCOUNT_UI_CONFIRMATION_CANDIDATE = (
    ACCOUNT_UI_CONFIRMATION_ROOT / "candidate.v2.json"
)
PREDISPATCH_ACCOUNT_UI_GATE_ROOT = Path(
    "/run/dharma-sadhana/control/account-ui-gate"
)
PREDISPATCH_ACCOUNT_UI_GATE = (
    PREDISPATCH_ACCOUNT_UI_GATE_ROOT / "predispatch-gate.v1.json"
)
_UUID4_RE = re.compile(
    r"[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}"
)
_ACCOUNT_UI_REQUEST_FIELDS = {
    "schema_version",
    "campaign_id",
    "client_request_id",
    "issued_at",
    "expires_at",
    "viewport_width_css_px_reported",
    "document_width_css_px_reported",
    "visual_viewport_width_css_px_reported",
    "coarse_pointer_reported",
    "touch_capability_reported",
    "trusted_browser_event_reported",
    "explicit_confirmation_gesture_reported",
    "dashboard_rendered_reported",
}
_ACCOUNT_UI_CANDIDATE_FIELDS = _ACCOUNT_UI_REQUEST_FIELDS | {
    "release_sha",
    "origin",
    "operator_login_sha256",
    "private_tailnet_https",
    "identity_header_injected",
    "operator_account_allowlist_match",
    "normal_control_request_sent",
    "external_message_sent",
    "physical_device_attested",
    "human_identity_attested",
    "predispatch_gate_receipt_digest",
    "normal_inbox_empty_ledger_sha256",
    "emergency_inbox_empty_ledger_sha256",
    "control_inboxes_empty_at_last_prepublication_scan",
    "observed_at",
    "hmac_sha256",
}
_PREDISPATCH_ACCOUNT_UI_GATE_FIELDS = {
    "schema_version",
    "campaign_id",
    "release_sha",
    "activated_at",
    "predispatch_activation_receipt_digest",
    "dispatch_marker_absent",
    "dispatch_target_inactive",
    "supervisor_main_pid",
    "provider_dispatch",
    "receipt_digest",
}


def _safe_json(
    status_code: int, status: str, *, error_code: str = "", **fields: Any
) -> JSONResponse:
    content: dict[str, Any] = {"status": status, **fields}
    if error_code:
        content["error_code"] = error_code
    return JSONResponse(
        status_code=status_code,
        content=content,
        headers={
            "Cache-Control": "no-store",
            "Pragma": "no-cache",
            "Referrer-Policy": "no-referrer",
            "X-Content-Type-Options": "nosniff",
        },
    )


def _read_credential(
    path: Path,
    *,
    name: str,
    minimum_bytes: int = 32,
    maximum_bytes: int = MAX_HMAC_CREDENTIAL_BYTES,
    printable_ascii: bool = False,
) -> bytes:
    nofollow = getattr(os, "O_NOFOLLOW", None)
    if not isinstance(nofollow, int) or nofollow == 0:
        raise ValueError(
            f"required no-follow credential support is unavailable: {name}"
        )
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | nofollow
    try:
        descriptor = os.open(path, flags)
    except OSError as exc:
        raise ValueError(f"required systemd credential is unavailable: {name}") from exc
    try:
        before = os.fstat(descriptor)
        if (
            not stat.S_ISREG(before.st_mode)
            or before.st_nlink != 1
            or not minimum_bytes <= before.st_size <= maximum_bytes
        ):
            raise ValueError(f"systemd credential has unsafe custody: {name}")
        chunks: list[bytes] = []
        remaining = maximum_bytes + 1
        while remaining:
            chunk = os.read(descriptor, min(remaining, 4096))
            if not chunk:
                break
            chunks.append(chunk)
            remaining -= len(chunk)
        payload = b"".join(chunks)
        after = os.fstat(descriptor)
        stable_fields = (
            "st_dev",
            "st_ino",
            "st_mode",
            "st_nlink",
            "st_size",
            "st_mtime_ns",
            "st_ctime_ns",
        )
        if any(
            getattr(before, field) != getattr(after, field) for field in stable_fields
        ):
            raise ValueError(f"systemd credential changed while reading: {name}")
        if len(payload) != before.st_size:
            raise ValueError(f"systemd credential changed while reading: {name}")
    finally:
        os.close(descriptor)
    if b"\r" in payload or b"\n" in payload:
        raise ValueError(f"systemd credential contains a forbidden line break: {name}")
    if not minimum_bytes <= len(payload) <= maximum_bytes:
        raise ValueError(f"systemd credential is outside bounds: {name}")
    if printable_ascii and any(byte < 0x21 or byte > 0x7E for byte in payload):
        raise ValueError(f"systemd credential is not printable ASCII: {name}")
    return payload


def _validate_origin(value: str) -> str:
    if not value or any(character < "!" or character > "~" for character in value):
        raise ValueError("SADHANA_CONTROL_EXPECTED_ORIGIN must be visible ASCII")
    try:
        parsed = urlsplit(value)
        hostname = parsed.hostname
        port = parsed.port
    except ValueError as exc:
        raise ValueError(
            "SADHANA_CONTROL_EXPECTED_ORIGIN must be one exact HTTPS origin"
        ) from exc
    if (
        parsed.scheme != "https"
        or not parsed.netloc
        or not hostname
        or parsed.path
        or parsed.query
        or parsed.fragment
        or parsed.username is not None
        or parsed.password is not None
    ):
        raise ValueError(
            "SADHANA_CONTROL_EXPECTED_ORIGIN must be one exact HTTPS origin"
        )
    try:
        address = ipaddress.ip_address(hostname)
    except ValueError:
        if all(character in "0123456789." for character in hostname):
            raise ValueError(
                "SADHANA_CONTROL_EXPECTED_ORIGIN must be one exact HTTPS origin"
            )
        labels = hostname.split(".")
        if any(
            not label
            or len(label) > 63
            or label[0] == "-"
            or label[-1] == "-"
            or any(
                not (character.isascii() and (character.isalnum() or character == "-"))
                for character in label
            )
            for label in labels
        ):
            raise ValueError(
                "SADHANA_CONTROL_EXPECTED_ORIGIN must be one exact HTTPS origin"
            )
        canonical_host = hostname.lower()
    else:
        canonical_host = (
            f"[{address.compressed}]" if address.version == 6 else str(address)
        )
    canonical = f"https://{canonical_host}"
    if port is not None:
        if port == 443:
            raise ValueError(
                "SADHANA_CONTROL_EXPECTED_ORIGIN must be one exact HTTPS origin"
            )
        canonical += f":{port}"
    if canonical != value:
        raise ValueError(
            "SADHANA_CONTROL_EXPECTED_ORIGIN must be one exact HTTPS origin"
        )
    return value


def _absolute_path(value: str, *, field_name: str) -> Path:
    path = Path(value)
    if not path.is_absolute() or ".." in path.parts:
        raise ValueError(f"{field_name} must be an absolute non-traversing path")
    return path


@dataclass(frozen=True)
class ControlApiConfig:
    allowed_tailscale_login: str = field(repr=False)
    expected_origin: str
    bearer_token: bytes = field(repr=False)
    hmac_secret: bytes = field(repr=False)
    release_sha: str
    normal_inbox: Path = DEFAULT_NORMAL_INBOX
    emergency_inbox: Path = DEFAULT_EMERGENCY_INBOX
    activation_proof_path: Path = DEFAULT_CAMPAIGN_ACTIVATION_PROOF
    activation_owner_uid: int | None = None
    activation_group_gid: int | None = None
    account_ui_candidate_path: Path = ACCOUNT_UI_CONFIRMATION_CANDIDATE
    predispatch_gate_path: Path = PREDISPATCH_ACCOUNT_UI_GATE
    predispatch_owner_uid: int = 0
    predispatch_owner_gid: int | None = None
    candidate_directory_owner_uid: int = 0
    candidate_owner_uid: int | None = None
    candidate_owner_gid: int | None = None

    def __post_init__(self) -> None:
        validate_operator_login(self.allowed_tailscale_login)
        _validate_origin(self.expected_origin)
        if (
            not isinstance(self.bearer_token, bytes)
            or not 32 <= len(self.bearer_token) <= MAX_BEARER_BYTES
            or any(byte <= 0x20 or byte >= 0x7F for byte in self.bearer_token)
        ):
            raise ValueError(
                "operator bearer credential must be 32-512 visible ASCII bytes"
            )
        if (
            not isinstance(self.hmac_secret, bytes)
            or not 32 <= len(self.hmac_secret) <= 4096
            or b"\r" in self.hmac_secret
            or b"\n" in self.hmac_secret
        ):
            raise ValueError("control HMAC credential has an invalid byte contract")
        if (
            not isinstance(self.release_sha, str)
            or len(self.release_sha) != 40
            or any(
                character not in "0123456789abcdef" for character in self.release_sha
            )
        ):
            raise ValueError("control release SHA must be one lowercase full commit")
        for path, name in (
            (self.normal_inbox, "normal_inbox"),
            (self.emergency_inbox, "emergency_inbox"),
            (self.activation_proof_path, "activation_proof_path"),
            (self.account_ui_candidate_path, "account_ui_candidate_path"),
            (self.predispatch_gate_path, "predispatch_gate_path"),
        ):
            if not path.is_absolute() or ".." in path.parts:
                raise ValueError(f"{name} must be an absolute non-traversing path")
        if self.normal_inbox == self.emergency_inbox:
            raise ValueError("normal and emergency inboxes must be distinct")
        for value, name in (
            (self.activation_owner_uid, "activation_owner_uid"),
            (self.activation_group_gid, "activation_group_gid"),
            (self.predispatch_owner_uid, "predispatch_owner_uid"),
            (self.predispatch_owner_gid, "predispatch_owner_gid"),
            (self.candidate_directory_owner_uid, "candidate_directory_owner_uid"),
            (self.candidate_owner_uid, "candidate_owner_uid"),
            (self.candidate_owner_gid, "candidate_owner_gid"),
        ):
            if value is not None and (
                isinstance(value, bool) or not isinstance(value, int) or value < 0
            ):
                raise ValueError(f"{name} must be a nonnegative integer")

    @classmethod
    def from_environment(
        cls, environ: Mapping[str, str] | None = None
    ) -> ControlApiConfig:
        values = os.environ if environ is None else environ
        if (
            values.get("SADHANA_ACCOUNT_UI_CONFIRMATION_HTTP_BINDING_SHA256")
            != ACCOUNT_UI_CONFIRMATION_HTTP_BINDING_SHA256
        ):
            raise ValueError("account UI confirmation HTTP binding differs")
        if (
            values.get("SADHANA_ACCOUNT_UI_CONFIRMATION_ENDPOINT")
            != ACCOUNT_UI_CONFIRMATION_ENDPOINT
        ):
            raise ValueError("account UI confirmation endpoint differs")
        credential_directory_raw = values.get("CREDENTIALS_DIRECTORY", "")
        if not credential_directory_raw:
            raise ValueError("CREDENTIALS_DIRECTORY is required")
        credential_directory = _absolute_path(
            credential_directory_raw, field_name="CREDENTIALS_DIRECTORY"
        )
        bearer = _read_credential(
            credential_directory / OPERATOR_BEARER_CREDENTIAL,
            name=OPERATOR_BEARER_CREDENTIAL,
            maximum_bytes=MAX_BEARER_BYTES,
            printable_ascii=True,
        )
        hmac_secret = _read_credential(
            credential_directory / CONTROL_HMAC_CREDENTIAL,
            name=CONTROL_HMAC_CREDENTIAL,
            maximum_bytes=MAX_HMAC_CREDENTIAL_BYTES,
        )
        try:
            origin = _validate_origin(values["SADHANA_CONTROL_EXPECTED_ORIGIN"])
            login_file = _absolute_path(
                values["SADHANA_CONTROL_TAILSCALE_LOGIN_FILE"],
                field_name="SADHANA_CONTROL_TAILSCALE_LOGIN_FILE",
            )
        except KeyError as exc:
            raise ValueError(
                f"required control configuration is missing: {exc.args[0]}"
            ) from exc
        login_raw = _read_credential(
            login_file,
            name=TAILSCALE_LOGIN_CREDENTIAL,
            minimum_bytes=1,
            maximum_bytes=254,
            printable_ascii=True,
        )
        try:
            allowed_login = validate_operator_login(login_raw.decode("ascii"))
        except (UnicodeDecodeError, ControlSchemaError) as exc:
            raise ValueError("Tailscale login credential is invalid") from exc
        normal = _absolute_path(
            values.get("SADHANA_CONTROL_NORMAL_INBOX", str(DEFAULT_NORMAL_INBOX)),
            field_name="SADHANA_CONTROL_NORMAL_INBOX",
        )
        emergency = _absolute_path(
            values.get("SADHANA_CONTROL_EMERGENCY_INBOX", str(DEFAULT_EMERGENCY_INBOX)),
            field_name="SADHANA_CONTROL_EMERGENCY_INBOX",
        )
        try:
            writer = pwd.getpwnam("dharma-sadhana")
            control = pwd.getpwnam("dharma-sadhana-control")
        except KeyError as exc:
            raise ValueError(
                "required control service identities are unavailable"
            ) from exc
        if (
            writer.pw_uid == 0
            or writer.pw_gid == 0
            or control.pw_uid == 0
            or control.pw_gid == 0
            or writer.pw_uid == control.pw_uid
            or writer.pw_gid == control.pw_gid
        ):
            raise ValueError("control service identities are not separated")
        immutable_release_sha = current_immutable_release_sha()
        if values.get("SADHANA_RELEASE_SHA") != immutable_release_sha:
            raise ValueError("control release environment differs")
        return cls(
            allowed_tailscale_login=allowed_login,
            expected_origin=origin,
            bearer_token=bearer,
            hmac_secret=hmac_secret,
            release_sha=immutable_release_sha,
            normal_inbox=normal,
            emergency_inbox=emergency,
            activation_proof_path=DEFAULT_CAMPAIGN_ACTIVATION_PROOF,
            activation_owner_uid=writer.pw_uid,
            activation_group_gid=control.pw_gid,
            predispatch_owner_gid=control.pw_gid,
            candidate_owner_uid=control.pw_uid,
            candidate_owner_gid=control.pw_gid,
        )


def _single_header(request: Request, name: bytes) -> bytes | None:
    values = [
        value for key, value in request.scope.get("headers", []) if key.lower() == name
    ]
    if len(values) != 1:
        return None
    return values[0]


def _loopback_peer(request: Request) -> bool:
    client = request.client
    if client is None:
        return False
    candidate = client.host.split("%", 1)[0]
    try:
        return ipaddress.ip_address(candidate).is_loopback
    except ValueError:
        return False


def _authenticate(
    request: Request, config: ControlApiConfig
) -> tuple[str | None, JSONResponse | None]:
    if not _loopback_peer(request):
        return None, _safe_json(403, "request_rejected", error_code="loopback_required")

    login_raw = _single_header(request, TAILSCALE_LOGIN_HEADER)
    if login_raw is None:
        return None, _safe_json(
            403, "request_rejected", error_code="tailscale_identity_required"
        )
    try:
        login = login_raw.decode("ascii")
        validate_operator_login(login)
    except (UnicodeDecodeError, ControlSchemaError):
        return None, _safe_json(
            403, "request_rejected", error_code="tailscale_identity_invalid"
        )
    if not hmac.compare_digest(login, config.allowed_tailscale_login):
        return None, _safe_json(
            403, "request_rejected", error_code="tailscale_identity_not_allowed"
        )

    origin = _single_header(request, ORIGIN_HEADER)
    if origin is None or not hmac.compare_digest(
        origin, config.expected_origin.encode("ascii")
    ):
        return None, _safe_json(403, "request_rejected", error_code="origin_mismatch")

    csrf = _single_header(request, CSRF_HEADER)
    if csrf is None or not hmac.compare_digest(csrf, CSRF_VALUE):
        return None, _safe_json(403, "request_rejected", error_code="csrf_required")

    authorization = _single_header(request, AUTHORIZATION_HEADER)
    expected = b"Bearer " + config.bearer_token
    if authorization is None or not hmac.compare_digest(authorization, expected):
        return None, _safe_json(401, "request_rejected", error_code="bearer_invalid")
    return login, None


async def _bounded_body(request: Request) -> bytes:
    body = bytearray()
    async for chunk in request.stream():
        body.extend(chunk)
        if len(body) > MAX_HTTP_BODY_BYTES:
            raise ValueError("request_body_too_large")
    if not body:
        raise ValueError("request_body_empty")
    return bytes(body)


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise ValueError("request_body_duplicate_key")
        value[key] = item
    return value


def _decode_request_body(raw: bytes) -> dict[str, Any]:
    try:
        value = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=_reject_duplicate_keys,
            parse_constant=lambda _: (_ for _ in ()).throw(
                ValueError("request_body_invalid_constant")
            ),
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("request_body_invalid_json") from exc
    if not isinstance(value, dict):
        raise ValueError("request_body_must_be_object")
    return value


def _canonical_bytes(value: Mapping[str, Any]) -> bytes:
    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def _parse_ui_timestamp(value: Any, *, field_name: str) -> datetime:
    if not isinstance(value, str) or re.fullmatch(
        r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}\.[0-9]{3}Z",
        value,
    ) is None:
        raise ValueError(f"{field_name}_invalid")
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exc:
        raise ValueError(f"{field_name}_invalid") from exc
    if parsed.tzinfo is None or parsed.utcoffset() != timedelta(0):
        raise ValueError(f"{field_name}_invalid")
    return parsed.astimezone(timezone.utc)


def _stable_read_json(
    path: Path,
    *,
    expected_uid: int,
    expected_gid: int,
    expected_mode: int,
    maximum_bytes: int = 64 * 1024,
) -> tuple[dict[str, Any], bytes]:
    nofollow = getattr(os, "O_NOFOLLOW", 0)
    if not nofollow:
        raise ValueError("filesystem_nofollow_unavailable")
    try:
        descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | nofollow)
    except OSError as exc:
        raise ValueError("required_predispatch_state_unavailable") from exc
    try:
        before = os.fstat(descriptor)
        if (
            not stat.S_ISREG(before.st_mode)
            or before.st_uid != expected_uid
            or before.st_gid != expected_gid
            or stat.S_IMODE(before.st_mode) != expected_mode
            or before.st_nlink != 1
            or not 0 < before.st_size <= maximum_bytes
        ):
            raise ValueError("required_predispatch_state_custody_invalid")
        chunks: list[bytes] = []
        remaining = maximum_bytes + 1
        while remaining:
            chunk = os.read(descriptor, min(remaining, 4096))
            if not chunk:
                break
            chunks.append(chunk)
            remaining -= len(chunk)
        raw = b"".join(chunks)
        after = os.fstat(descriptor)
    finally:
        os.close(descriptor)
    stable = (
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
    if len(raw) != before.st_size or any(
        getattr(before, name) != getattr(after, name) for name in stable
    ):
        raise ValueError("required_predispatch_state_changed")
    payload = _decode_request_body(raw[:-1] if raw.endswith(b"\n") else raw)
    expected_raw = _canonical_bytes(payload) + (b"\n" if raw.endswith(b"\n") else b"")
    if raw != expected_raw:
        raise ValueError("required_predispatch_state_noncanonical")
    return payload, raw


def _self_digest(payload: Mapping[str, Any], field_name: str) -> str:
    unsigned = dict(payload)
    unsigned.pop(field_name, None)
    return "sha256:" + hashlib.sha256(_canonical_bytes(unsigned)).hexdigest()


def _validate_predispatch_for_account_confirmation(
    config: ControlApiConfig,
    *,
    observed: datetime,
) -> dict[str, Any]:
    if observed.tzinfo is None:
        raise ValueError("predispatch_clock_invalid")
    observed = observed.astimezone(timezone.utc)
    if observed >= CAMPAIGN_STOP_UTC:
        raise ValueError("campaign_timebox_closed")
    if config.activation_proof_path.exists() or config.activation_proof_path.is_symlink():
        raise ValueError("predispatch_state_not_quiet")
    expected_uid = (
        os.geteuid()
        if config.predispatch_owner_uid is None
        else config.predispatch_owner_uid
    )
    expected_gid = (
        os.getegid()
        if config.predispatch_owner_gid is None
        else config.predispatch_owner_gid
    )
    payload, _raw = _stable_read_json(
        config.predispatch_gate_path,
        expected_uid=expected_uid,
        expected_gid=expected_gid,
        expected_mode=0o640,
    )
    exact = {
        "schema_version": "dharma.sadhana.account_ui_predispatch_gate.v1",
        "campaign_id": MISSION_ID,
        "release_sha": config.release_sha,
        "dispatch_marker_absent": True,
        "dispatch_target_inactive": True,
        "supervisor_main_pid": 0,
        "provider_dispatch": "NoProviderDispatch",
    }
    if (
        set(payload) != _PREDISPATCH_ACCOUNT_UI_GATE_FIELDS
        or any(payload.get(key) != expected for key, expected in exact.items())
        or payload.get("receipt_digest") != _self_digest(payload, "receipt_digest")
    ):
        raise ValueError("predispatch_state_binding_invalid")
    return payload


def _validate_account_ui_request(
    payload: Mapping[str, Any],
    *,
    observed: datetime,
) -> dict[str, Any]:
    if set(payload) != _ACCOUNT_UI_REQUEST_FIELDS:
        raise ValueError("account_ui_confirmation_fields_invalid")
    exact = {
        "schema_version": ACCOUNT_UI_CONFIRMATION_REQUEST_SCHEMA,
        "campaign_id": MISSION_ID,
        "viewport_width_css_px_reported": 390,
        "document_width_css_px_reported": 390,
        "visual_viewport_width_css_px_reported": 390,
        "coarse_pointer_reported": True,
        "touch_capability_reported": True,
        "trusted_browser_event_reported": True,
        "explicit_confirmation_gesture_reported": True,
        "dashboard_rendered_reported": True,
    }
    if any(payload.get(key) != expected for key, expected in exact.items()):
        raise ValueError("account_ui_confirmation_binding_invalid")
    if not _account_ui_report_types_exact(payload):
        raise ValueError("account_ui_confirmation_binding_invalid")
    request_id = payload.get("client_request_id")
    if not isinstance(request_id, str) or _UUID4_RE.fullmatch(request_id) is None:
        raise ValueError("client_request_id_invalid")
    issued = _parse_ui_timestamp(payload.get("issued_at"), field_name="issued_at")
    expires = _parse_ui_timestamp(payload.get("expires_at"), field_name="expires_at")
    observed = observed.astimezone(timezone.utc)
    if (
        issued > observed + timedelta(seconds=15)
        or observed - issued > timedelta(seconds=60)
        or expires <= observed
        or expires - issued != timedelta(seconds=90)
    ):
        raise ValueError("account_ui_confirmation_not_fresh")
    return dict(payload)


def _account_ui_report_types_exact(payload: Mapping[str, Any]) -> bool:
    return not any(
        type(payload.get(field_name)) is not int
        for field_name in (
            "viewport_width_css_px_reported",
            "document_width_css_px_reported",
            "visual_viewport_width_css_px_reported",
        )
    ) and not any(
        type(payload.get(field_name)) is not bool
        for field_name in (
            "coarse_pointer_reported",
            "touch_capability_reported",
            "trusted_browser_event_reported",
            "explicit_confirmation_gesture_reported",
            "dashboard_rendered_reported",
        )
    )


def _account_ui_candidate_mac(payload: Mapping[str, Any], secret: bytes) -> str:
    unsigned = dict(payload)
    unsigned.pop("hmac_sha256", None)
    derived_key = hmac.new(
        secret,
        ACCOUNT_UI_CONFIRMATION_KEY_DOMAIN,
        hashlib.sha256,
    ).digest()
    return "hmac-sha256:" + hmac.new(
        derived_key,
        ACCOUNT_UI_CONFIRMATION_MAC_DOMAIN + _canonical_bytes(unsigned),
        hashlib.sha256,
    ).hexdigest()


def _validate_account_ui_candidate(
    payload: Mapping[str, Any],
    *,
    config: ControlApiConfig,
    expected_request: Mapping[str, Any],
    operator_login: str,
    observed: datetime,
    predispatch_receipt_digest: str,
) -> None:
    exact = {
        **expected_request,
        "schema_version": ACCOUNT_UI_CONFIRMATION_CANDIDATE_SCHEMA,
        "release_sha": config.release_sha,
        "origin": config.expected_origin,
        "operator_login_sha256": hashlib.sha256(
            operator_login.encode("ascii")
        ).hexdigest(),
        "private_tailnet_https": True,
        "identity_header_injected": True,
        "operator_account_allowlist_match": True,
        "normal_control_request_sent": False,
        "external_message_sent": False,
        "physical_device_attested": False,
        "human_identity_attested": False,
        "predispatch_gate_receipt_digest": predispatch_receipt_digest,
    }
    exact["schema_version"] = ACCOUNT_UI_CONFIRMATION_CANDIDATE_SCHEMA
    if (
        set(payload) != _ACCOUNT_UI_CANDIDATE_FIELDS
        or any(payload.get(key) != value for key, value in exact.items())
        or not _account_ui_report_types_exact(payload)
        or any(
            type(payload.get(field_name)) is not bool
            for field_name in (
                "private_tailnet_https",
                "identity_header_injected",
                "operator_account_allowlist_match",
                "normal_control_request_sent",
                "external_message_sent",
                "physical_device_attested",
                "human_identity_attested",
                "control_inboxes_empty_at_last_prepublication_scan",
            )
        )
        or payload.get("hmac_sha256")
        != _account_ui_candidate_mac(payload, config.hmac_secret)
        or payload.get("control_inboxes_empty_at_last_prepublication_scan") is not True
        or any(
            re.fullmatch(r"sha256:[0-9a-f]{64}", str(payload.get(field, "")))
            is None
            for field in (
                "normal_inbox_empty_ledger_sha256",
                "emergency_inbox_empty_ledger_sha256",
            )
        )
        or payload.get("normal_inbox_empty_ledger_sha256")
        != _empty_inbox_ledger_sha256()
        or payload.get("emergency_inbox_empty_ledger_sha256")
        != _empty_inbox_ledger_sha256()
    ):
        raise ValueError("account_ui_confirmation_candidate_conflict")
    candidate_observed = _parse_ui_timestamp(
        payload.get("observed_at"), field_name="observed_at"
    )
    if candidate_observed > observed or observed - candidate_observed > timedelta(seconds=90):
        raise ValueError("account_ui_confirmation_candidate_stale")


def _publish_account_ui_candidate(
    candidate: Mapping[str, Any],
    *,
    config: ControlApiConfig,
    expected_request: Mapping[str, Any],
    operator_login: str,
    observed: datetime,
    predispatch_receipt_digest: str,
) -> bool:
    directory = config.account_ui_candidate_path.parent
    expected_uid = (
        os.geteuid() if config.candidate_owner_uid is None else config.candidate_owner_uid
    )
    expected_gid = (
        os.getegid() if config.candidate_owner_gid is None else config.candidate_owner_gid
    )
    nofollow = getattr(os, "O_NOFOLLOW", 0)
    if not nofollow or config.account_ui_candidate_path.name != "candidate.v2.json":
        raise ValueError("account_ui_confirmation_candidate_path_invalid")
    directory_identity = directory.lstat()
    if (
        directory.is_symlink()
        or not stat.S_ISDIR(directory_identity.st_mode)
        or directory_identity.st_uid != config.candidate_directory_owner_uid
        or directory_identity.st_gid != expected_gid
        or stat.S_IMODE(directory_identity.st_mode) != 0o770
    ):
        raise ValueError("account_ui_confirmation_directory_custody_invalid")
    directory_fd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY | nofollow)
    raw = _canonical_bytes(candidate) + b"\n"
    try:
        fcntl.flock(directory_fd, fcntl.LOCK_EX)
        opened_directory = os.fstat(directory_fd)
        if (
            opened_directory.st_dev != directory_identity.st_dev
            or opened_directory.st_ino != directory_identity.st_ino
        ):
            raise ValueError("account_ui_confirmation_directory_changed")
        try:
            os.stat(
                config.account_ui_candidate_path.name,
                dir_fd=directory_fd,
                follow_symlinks=False,
            )
        except FileNotFoundError:
            pass
        else:
            existing, _existing_raw = _stable_read_json(
                config.account_ui_candidate_path,
                expected_uid=expected_uid,
                expected_gid=expected_gid,
                expected_mode=0o600,
            )
            _validate_account_ui_candidate(
                existing,
                config=config,
                expected_request=expected_request,
                operator_login=operator_login,
                observed=observed,
                predispatch_receipt_digest=predispatch_receipt_digest,
            )
            return True

        staging_name = ".candidate.v2.json.pending"
        try:
            staging_fd = os.open(
                staging_name,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL | nofollow,
                0o600,
                dir_fd=directory_fd,
            )
        except OSError as exc:
            raise ValueError("account_ui_confirmation_candidate_unavailable") from exc
        linked = False
        try:
            try:
                offset = 0
                while offset < len(raw):
                    written = os.write(staging_fd, raw[offset:])
                    if written <= 0:
                        raise ValueError(
                            "account_ui_confirmation_candidate_write_failed"
                        )
                    offset += written
                os.fsync(staging_fd)
                identity = os.fstat(staging_fd)
                if (
                    not stat.S_ISREG(identity.st_mode)
                    or identity.st_uid != expected_uid
                    or identity.st_gid != expected_gid
                    or stat.S_IMODE(identity.st_mode) != 0o600
                    or identity.st_nlink != 1
                    or identity.st_size != len(raw)
                ):
                    raise ValueError(
                        "account_ui_confirmation_candidate_custody_invalid"
                    )
            finally:
                os.close(staging_fd)
            try:
                os.link(
                    staging_name,
                    config.account_ui_candidate_path.name,
                    src_dir_fd=directory_fd,
                    dst_dir_fd=directory_fd,
                    follow_symlinks=False,
                )
                linked = True
            except OSError as exc:
                raise ValueError(
                    "account_ui_confirmation_candidate_unavailable"
                ) from exc
        finally:
            try:
                os.unlink(staging_name, dir_fd=directory_fd)
            except FileNotFoundError:
                pass
        os.fsync(directory_fd)
        if not linked:
            raise ValueError("account_ui_confirmation_candidate_unavailable")
        final_identity = os.stat(
            config.account_ui_candidate_path.name,
            dir_fd=directory_fd,
            follow_symlinks=False,
        )
        if (
            not stat.S_ISREG(final_identity.st_mode)
            or final_identity.st_uid != expected_uid
            or final_identity.st_gid != expected_gid
            or stat.S_IMODE(final_identity.st_mode) != 0o600
            or final_identity.st_nlink != 1
            or final_identity.st_size != len(raw)
        ):
            raise ValueError("account_ui_confirmation_candidate_custody_invalid")
    finally:
        try:
            fcntl.flock(directory_fd, fcntl.LOCK_UN)
        except OSError:
            pass
        os.close(directory_fd)
    return False


def _inbox_ledger_sha256(path: Path, *, config: ControlApiConfig) -> str:
    nofollow = getattr(os, "O_NOFOLLOW", 0)
    expected_gid = (
        os.getegid() if config.candidate_owner_gid is None else config.candidate_owner_gid
    )
    if not nofollow:
        raise ValueError("filesystem_nofollow_unavailable")
    identity = path.lstat()
    if (
        path.is_symlink()
        or not stat.S_ISDIR(identity.st_mode)
        or identity.st_uid != config.candidate_directory_owner_uid
        or identity.st_gid != expected_gid
        or stat.S_IMODE(identity.st_mode) != 0o770
    ):
        raise ValueError("control_inbox_custody_invalid")
    descriptor = os.open(path, os.O_RDONLY | os.O_DIRECTORY | nofollow)
    try:
        opened = os.fstat(descriptor)
        if (opened.st_dev, opened.st_ino) != (identity.st_dev, identity.st_ino):
            raise ValueError("control_inbox_changed")
        rows: list[tuple[str, int, int]] = []
        for name in sorted(os.listdir(descriptor)):
            item = os.stat(name, dir_fd=descriptor, follow_symlinks=False)
            rows.append((name, item.st_dev, item.st_ino))
        after = os.fstat(descriptor)
    finally:
        os.close(descriptor)
    if (after.st_dev, after.st_ino, after.st_mtime_ns) != (
        opened.st_dev,
        opened.st_ino,
        opened.st_mtime_ns,
    ):
        raise ValueError("control_inbox_changed")
    return "sha256:" + hashlib.sha256(_canonical_bytes({"rows": rows})).hexdigest()


def _empty_inbox_ledger_sha256() -> str:
    return "sha256:" + hashlib.sha256(_canonical_bytes({"rows": []})).hexdigest()


def create_app(
    config: ControlApiConfig,
    *,
    publisher: ControlInboxPublisher | None = None,
    now_fn=utc_now,
    before_account_ui_publish=None,
) -> FastAPI:
    app = FastAPI(
        title="SADHANA operator control ingress",
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )
    control_publisher = publisher or ControlInboxPublisher(
        normal_inbox=config.normal_inbox,
        emergency_inbox=config.emergency_inbox,
    )

    @app.post(ACCOUNT_UI_CONFIRMATION_ENDPOINT)
    async def submit_account_ui_confirmation(request: Request) -> JSONResponse:
        login, rejection = _authenticate(request, config)
        if rejection is not None:
            return rejection
        assert login is not None
        release_header = _single_header(request, RELEASE_SHA_HEADER)
        if release_header is None or not hmac.compare_digest(
            release_header, config.release_sha.encode("ascii")
        ):
            return _safe_json(
                403,
                "request_rejected",
                error_code="release_binding_mismatch",
            )
        if _single_header(request, CONTENT_TYPE_HEADER) != b"application/json":
            return _safe_json(
                415, "request_rejected", error_code="content_type_required"
            )
        try:
            body = await _bounded_body(request)
            request_payload = _decode_request_body(body)
            observed = now_fn()
            if not isinstance(observed, datetime) or observed.tzinfo is None:
                raise ValueError("predispatch_clock_invalid")
            observed = observed.astimezone(timezone.utc)
            admitted_request = _validate_account_ui_request(
                request_payload,
                observed=observed,
            )
            predispatch = _validate_predispatch_for_account_confirmation(
                config,
                observed=observed,
            )
            normal_ledger_before = _inbox_ledger_sha256(
                config.normal_inbox, config=config
            )
            emergency_ledger_before = _inbox_ledger_sha256(
                config.emergency_inbox, config=config
            )
            if (
                normal_ledger_before != _empty_inbox_ledger_sha256()
                or emergency_ledger_before != _empty_inbox_ledger_sha256()
            ):
                raise ValueError("control_inbox_not_empty")
        except ValueError as exc:
            error_code = str(exc)
            if error_code == "request_body_too_large":
                status_code = 413
            elif error_code.startswith("request_body_"):
                status_code = 400
            elif error_code.startswith("account_ui_confirmation_") or error_code in {
                "client_request_id_invalid",
                "issued_at_invalid",
                "expires_at_invalid",
            }:
                status_code = 422
            else:
                status_code = 423
            return _safe_json(status_code, "request_rejected", error_code=error_code)

        try:
            if before_account_ui_publish is not None:
                before_account_ui_publish()
            publication_observed = now_fn()
            if (
                not isinstance(publication_observed, datetime)
                or publication_observed.tzinfo is None
            ):
                raise ValueError("predispatch_clock_invalid")
            publication_observed = publication_observed.astimezone(timezone.utc)
            _validate_account_ui_request(
                admitted_request,
                observed=publication_observed,
            )
            refreshed = _validate_predispatch_for_account_confirmation(
                config,
                observed=publication_observed,
            )
            if refreshed["receipt_digest"] != predispatch["receipt_digest"]:
                raise ValueError("predispatch_state_changed")
            normal_ledger_at_last_prepublication_scan = _inbox_ledger_sha256(
                config.normal_inbox, config=config
            )
            emergency_ledger_at_last_prepublication_scan = _inbox_ledger_sha256(
                config.emergency_inbox, config=config
            )
            if (
                normal_ledger_at_last_prepublication_scan
                != _empty_inbox_ledger_sha256()
                or emergency_ledger_at_last_prepublication_scan
                != _empty_inbox_ledger_sha256()
            ):
                raise ValueError("control_inbox_not_empty")
            publication_observed = now_fn()
            if (
                not isinstance(publication_observed, datetime)
                or publication_observed.tzinfo is None
            ):
                raise ValueError("predispatch_clock_invalid")
            publication_observed = publication_observed.astimezone(timezone.utc)
            _validate_account_ui_request(
                admitted_request,
                observed=publication_observed,
            )
            final_predispatch = _validate_predispatch_for_account_confirmation(
                config,
                observed=publication_observed,
            )
            if final_predispatch["receipt_digest"] != predispatch["receipt_digest"]:
                raise ValueError("predispatch_state_changed")
            candidate: dict[str, Any] = {
                **admitted_request,
                "schema_version": ACCOUNT_UI_CONFIRMATION_CANDIDATE_SCHEMA,
                "release_sha": config.release_sha,
                "origin": config.expected_origin,
                "operator_login_sha256": hashlib.sha256(
                    login.encode("ascii")
                ).hexdigest(),
                "private_tailnet_https": True,
                "identity_header_injected": True,
                "operator_account_allowlist_match": True,
                "normal_control_request_sent": False,
                "external_message_sent": False,
                "physical_device_attested": False,
                "human_identity_attested": False,
                "predispatch_gate_receipt_digest": predispatch["receipt_digest"],
                "normal_inbox_empty_ledger_sha256": (
                    normal_ledger_at_last_prepublication_scan
                ),
                "emergency_inbox_empty_ledger_sha256": (
                    emergency_ledger_at_last_prepublication_scan
                ),
                "control_inboxes_empty_at_last_prepublication_scan": True,
                "observed_at": publication_observed.isoformat(
                    timespec="milliseconds"
                ).replace("+00:00", "Z"),
                "hmac_sha256": "",
            }
            candidate["hmac_sha256"] = _account_ui_candidate_mac(
                candidate, config.hmac_secret
            )
            replayed = _publish_account_ui_candidate(
                candidate,
                config=config,
                expected_request=admitted_request,
                operator_login=login,
                observed=publication_observed,
                predispatch_receipt_digest=predispatch["receipt_digest"],
            )
        except ValueError as exc:
            error_code = str(exc)
            status_code = (
                409
                if error_code
                in {
                    "account_ui_confirmation_candidate_conflict",
                    "account_ui_confirmation_candidate_stale",
                }
                else 423
                if error_code.startswith("predispatch_")
                or error_code in {"campaign_timebox_closed"}
                else 503
            )
            return _safe_json(status_code, "request_rejected", error_code=error_code)
        return _safe_json(
            202,
            "account_ui_confirmation_accepted",
            replayed=replayed,
            account_authenticated=True,
            candidate_recorded=True,
            authority_applied=False,
            dispatch_authorized=False,
            physical_device_attested=False,
            human_identity_attested=False,
        )

    @app.post(CONTROL_ENDPOINT)
    async def submit_control(request: Request) -> JSONResponse:
        login, rejection = _authenticate(request, config)
        if rejection is not None:
            return rejection
        assert login is not None

        content_type = _single_header(request, CONTENT_TYPE_HEADER)
        if content_type != b"application/json":
            return _safe_json(
                415, "request_rejected", error_code="content_type_required"
            )
        try:
            body = await _bounded_body(request)
            payload = _decode_request_body(body)
        except ValueError as exc:
            error_code = str(exc)
            status_code = 413 if error_code == "request_body_too_large" else 400
            return _safe_json(status_code, "request_rejected", error_code=error_code)

        action = payload.get("action")
        if action in UNSUPPORTED_DECISION_ACTIONS:
            return _safe_json(
                501,
                "unsupported_action",
                error_code="proposal_effect_warrant_contract_unavailable",
                action=action,
                request_accepted=False,
                decision_applied=False,
                effect_executed=False,
            )
        try:
            control = OperatorControlRequest.from_mapping(payload)
        except (
            ControlExpiredError,
            ControlFutureRequestError,
            ControlSchemaError,
        ) as exc:
            return _safe_json(422, "request_rejected", error_code=exc.code)

        observed = now_fn()
        publication_secret = config.hmac_secret
        if control.action is not ControlAction.EMERGENCY_STOP:
            try:
                activation = validate_campaign_activation_proof(
                    config.activation_proof_path,
                    expected_release_sha=config.release_sha,
                    operator_login=login,
                    now=observed,
                    expected_owner_uid=config.activation_owner_uid,
                    expected_group_gid=config.activation_group_gid,
                )
                publication_secret = derive_activation_bound_hmac_key(
                    config.hmac_secret, activation["receipt_digest"]
                )
            except (ControlSchemaError, ValueError, OSError):
                return _safe_json(
                    423,
                    "request_rejected",
                    error_code="normal_control_not_activated",
                )

        try:
            publication = control_publisher.publish(
                control,
                operator_login=login,
                secret=publication_secret,
                now=observed,
            )
        except ControlIdempotencyConflict:
            return _safe_json(
                409, "request_rejected", error_code="idempotency_conflict"
            )
        except (
            ControlExpiredError,
            ControlFutureRequestError,
            ControlSchemaError,
        ) as exc:
            return _safe_json(422, "request_rejected", error_code=exc.code)
        except (InboxUnavailable, UnsafeInboxEntry):
            return _safe_json(503, "request_rejected", error_code="inbox_unavailable")

        return _safe_json(
            202,
            "request_accepted",
            request_id=publication.request_id,
            idempotency_key=publication.idempotency_key,
            action=publication.action.value,
            inbox=publication.inbox.value,
            replayed=publication.replayed,
            source_envelope_sha256=publication.source_envelope_sha256,
            request_accepted=True,
            applied=False,
            decision_applied=False,
            effect_executed=False,
        )

    return app


def main() -> None:
    config = ControlApiConfig.from_environment()
    uvicorn.run(
        create_app(config),
        host=CONTROL_HOST,
        port=CONTROL_PORT,
        access_log=False,
        log_level="warning",
        proxy_headers=False,
        server_header=False,
        date_header=False,
    )


if __name__ == "__main__":
    main()
