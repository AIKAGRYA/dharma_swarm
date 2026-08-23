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

import hmac
import ipaddress
import json
import os
import stat
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from dharma_swarm.mission_control_operator_control import (
    DEFAULT_EMERGENCY_INBOX,
    DEFAULT_NORMAL_INBOX,
    OPERATOR_CONTROL_HTTP_BINDING_SHA256 as _HTTP_BINDING_SHA256,
    UNSUPPORTED_DECISION_ACTIONS,
    ControlExpiredError,
    ControlFutureRequestError,
    ControlIdempotencyConflict,
    ControlInboxPublisher,
    ControlSchemaError,
    InboxUnavailable,
    OperatorControlRequest,
    UnsafeInboxEntry,
    utc_now,
    validate_operator_login,
)

CONTROL_HOST = "127.0.0.1"
CONTROL_PORT = 18421
CONTROL_ENDPOINT = "/v1/operator-control/requests"
TAILSCALE_LOGIN_HEADER = b"tailscale-user-login"
ORIGIN_HEADER = b"origin"
AUTHORIZATION_HEADER = b"authorization"
CSRF_HEADER = b"x-sadhana-csrf"
CSRF_VALUE = b"sadhana-10-20260823"
CONTENT_TYPE_HEADER = b"content-type"
MAX_HTTP_BODY_BYTES = 4096
MAX_BEARER_BYTES = 512
MAX_HMAC_CREDENTIAL_BYTES = 4096
OPERATOR_BEARER_CREDENTIAL = "operator_bearer"
CONTROL_HMAC_CREDENTIAL = "control_hmac_key"
TAILSCALE_LOGIN_CREDENTIAL = "tailscale_operator_login"
OPERATOR_CONTROL_HTTP_BINDING_SHA256 = _HTTP_BINDING_SHA256


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
    normal_inbox: Path = DEFAULT_NORMAL_INBOX
    emergency_inbox: Path = DEFAULT_EMERGENCY_INBOX

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
        for path, name in (
            (self.normal_inbox, "normal_inbox"),
            (self.emergency_inbox, "emergency_inbox"),
        ):
            if not path.is_absolute() or ".." in path.parts:
                raise ValueError(f"{name} must be an absolute non-traversing path")
        if self.normal_inbox == self.emergency_inbox:
            raise ValueError("normal and emergency inboxes must be distinct")

    @classmethod
    def from_environment(
        cls, environ: Mapping[str, str] | None = None
    ) -> ControlApiConfig:
        values = os.environ if environ is None else environ
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
        return cls(
            allowed_tailscale_login=allowed_login,
            expected_origin=origin,
            bearer_token=bearer,
            hmac_secret=hmac_secret,
            normal_inbox=normal,
            emergency_inbox=emergency,
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


def create_app(
    config: ControlApiConfig,
    *,
    publisher: ControlInboxPublisher | None = None,
    now_fn=utc_now,
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
            publication = control_publisher.publish(
                control,
                operator_login=login,
                secret=config.hmac_secret,
                now=now_fn(),
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
