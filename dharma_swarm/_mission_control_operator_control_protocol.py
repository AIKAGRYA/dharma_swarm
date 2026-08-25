"""Authenticated SADHANA operator-control request protocol.

This private module owns canonical request/envelope types, validation, signing,
publication, and safe candidate reads.  It deliberately has no campaign state,
provider, executor, or systemd authority.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import stat
import unicodedata
from collections.abc import Mapping, Set
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
from pathlib import Path
from typing import Any

from dharma_swarm._mission_control_operator_control_fs import (
    CONTROL_FILENAME_RE as _CONTROL_FILENAME_RE,
    MAX_ENVELOPE_BYTES,
    ControlAuthenticationError,
    ControlConfigurationError,
    ControlExpiredError,
    ControlFutureRequestError,
    ControlIdempotencyConflict,
    ControlSchemaError,
    atomic_publish as _atomic_publish,
    open_directory_nofollow as _open_directory_nofollow,
    read_regular_entry as _read_regular_entry,
)

CONTROL_SCHEMA = "dharma.sadhana.operator_control.v1"
NORMAL_ACTIVATION_HMAC_DOMAIN = (
    b"dharma.sadhana.operator_control.normal.activation_key.v1\0"
)
DEFAULT_CONTROL_ROOT = Path("/run/dharma-sadhana/control")
DEFAULT_NORMAL_INBOX = DEFAULT_CONTROL_ROOT / "normal"
DEFAULT_EMERGENCY_INBOX = DEFAULT_CONTROL_ROOT / "emergency"
DEFAULT_INFLIGHT_INBOX = DEFAULT_CONTROL_ROOT / "inflight"
DEFAULT_APPLIED_INBOX = DEFAULT_CONTROL_ROOT / "applied"
DEFAULT_REJECTED_INBOX = DEFAULT_CONTROL_ROOT / "rejected"
DEFAULT_CAMPAIGN_ACTIVATION_PROOF = (
    DEFAULT_CONTROL_ROOT / "activation" / "campaign-activation.v1.json"
)
CAMPAIGN_ACTIVATION_SCHEMA = "dharma.sadhana.campaign_activation.v1"
SADHANA_CAMPAIGN_ID = "sadhana-10-20260823"
SADHANA_CAMPAIGN_STOP_UTC = "2026-09-01T17:15:12Z"
CONTROL_SEMANTICS_SHA256 = (
    "69a0eb088277882e333ac41a6fb7014f6ed9d792e6d4a4b2b8510f20de15077c"
)
CONTROL_HTTP_BINDING_SHA256 = (
    "9e1aec44c75cf6b24341389b8227f57fe4d4cf48328992f2125bffca34fcf3eb"
)
AUTHORITY_BINDING_SHA256 = (
    "495f16964248948c68f97b5ec02b7e5d3e00e006979bf283ea783127e303d52d"
)
OPERATOR_CONTROL_SEMANTICS_SHA256 = f"sha256:{CONTROL_SEMANTICS_SHA256}"
OPERATOR_CONTROL_HTTP_BINDING_SHA256 = f"sha256:{CONTROL_HTTP_BINDING_SHA256}"
OPERATOR_CONTROL_AUTHORITY_BINDING_SHA256 = f"sha256:{AUTHORITY_BINDING_SHA256}"
TERMINAL_RECEIPT_SCHEMA = "dharma.sadhana.operator_control_terminal.v1"

MAX_REASON_CHARS = 512
MAX_IDENTIFIER_CHARS = 128
MAX_OPERATOR_LOGIN_CHARS = 254
MAX_AUTHORITY_RECEIPT_REF_CHARS = 512
MAX_REQUEST_TTL = timedelta(seconds=120)
MAX_ISSUED_AT_SKEW = timedelta(seconds=15)

REQUEST_FIELDS = frozenset(
    {"action", "request_id", "idempotency_key", "issued_at", "expires_at", "reason"}
)
ENVELOPE_FIELDS = frozenset({"schema", "operator_login", "request", "hmac_sha256"})
UNSIGNED_ENVELOPE_FIELDS = frozenset({"schema", "operator_login", "request"})
UNSUPPORTED_DECISION_ACTIONS = frozenset({"approve", "reject"})

CAMPAIGN_ACTIVATION_FIELDS = frozenset(
    {
        "schema_version",
        "mission_id",
        "release_sha",
        "config_digest",
        "campaign_generation",
        "transition_sequence",
        "control_state",
        "action",
        "dispatch_enable_receipt_digest",
        "account_ui_confirmation_receipt_digest",
        "operator_login_sha256",
        "authority_receipt_ref",
        "authority_receipt_sha256",
        "activated_at",
        "external_effect_performed",
        "receipt_digest",
    }
)
MAX_CAMPAIGN_ACTIVATION_BYTES = 16 * 1024

_IDENTIFIER_RE = re.compile(r"\A[A-Za-z0-9][A-Za-z0-9._:-]{0,127}\Z")
_LOGIN_RE = re.compile(r"\A[A-Za-z0-9][A-Za-z0-9@._+:-]{0,253}\Z")
_TIMESTAMP_RE = re.compile(r"\A\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?Z\Z")
_HMAC_RE = re.compile(r"\A[0-9a-f]{64}\Z")
_SHA256_REF_RE = re.compile(r"\Asha256:[0-9a-f]{64}\Z")
_RAW_SHA256_RE = re.compile(r"\A[0-9a-f]{64}\Z")
_RELEASE_SHA_RE = re.compile(r"\A[0-9a-f]{40}\Z")
_AUTHORITY_RECEIPT_REF_RE = re.compile(
    r"\Aruntime-receipt:[A-Za-z0-9][A-Za-z0-9._:-]{0,127}\Z"
)


class ControlAction(str, Enum):
    """Operational actions admitted by the v1 request schema."""

    PAUSE = "pause"
    RESUME = "resume"
    EMERGENCY_STOP = "emergency_stop"


class InboxKind(str, Enum):
    NORMAL = "normal"
    EMERGENCY = "emergency"


class ApplicationStatus(str, Enum):
    APPLIED = "applied"
    REJECTED = "rejected"
    DEFERRED = "deferred"


class FreshnessPolicy(str, Enum):
    STRICT = "strict"
    AUTHORITY_REPLAY = "authority_replay"


class ReconcileStatus(str, Enum):
    APPLIED = "applied"
    REJECTED = "rejected"
    DEFERRED = "deferred"
    REPLAYED = "replayed"
    INVALID = "invalid"
    CONFLICT = "conflict"


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _require_aware_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ControlConfigurationError("time reference must be timezone-aware")
    return value.astimezone(timezone.utc)


def _parse_timestamp(value: Any, *, field: str) -> datetime:
    if not isinstance(value, str) or not _TIMESTAMP_RE.fullmatch(value):
        raise ControlSchemaError(f"{field} must be strict RFC3339 UTC")
    try:
        parsed = datetime.fromisoformat(f"{value[:-1]}+00:00")
    except ValueError as exc:
        raise ControlSchemaError(f"{field} is not a real UTC timestamp") from exc
    return parsed.astimezone(timezone.utc)


def _require_exact_fields(
    value: Mapping[str, Any], expected: frozenset[str], *, object_name: str
) -> None:
    actual = frozenset(value)
    if actual != expected:
        missing = sorted(expected - actual)
        extra = sorted(actual - expected)
        raise ControlSchemaError(
            f"{object_name} fields are not exact; missing={missing}, extra={extra}"
        )


def _validate_identifier(value: Any, *, field: str) -> str:
    if not isinstance(value, str) or not _IDENTIFIER_RE.fullmatch(value):
        raise ControlSchemaError(
            f"{field} must be 1-{MAX_IDENTIFIER_CHARS} safe ASCII characters"
        )
    return value


def _validate_reason(value: Any) -> str:
    if (
        not isinstance(value, str)
        or not value
        or len(value) > MAX_REASON_CHARS
        or value.strip() != value
        or unicodedata.normalize("NFC", value) != value
        or any(unicodedata.category(char).startswith("C") for char in value)
    ):
        raise ControlSchemaError(
            f"reason must be 1-{MAX_REASON_CHARS} trimmed NFC characters without controls"
        )
    return value


def _validate_authority_receipt_ref(value: Any) -> str:
    if not isinstance(value, str):
        raise ValueError("authority receipt reference must be text")
    if value and (
        len(value) > MAX_AUTHORITY_RECEIPT_REF_CHARS
        or value.strip() != value
        or unicodedata.normalize("NFC", value) != value
        or any(unicodedata.category(char).startswith("C") for char in value)
    ):
        raise ValueError("authority receipt reference is outside canonical bounds")
    return value


def validate_operator_login(value: Any) -> str:
    """Validate the exact Tailscale Serve login value without normalizing it."""

    if not isinstance(value, str) or not _LOGIN_RE.fullmatch(value):
        raise ControlSchemaError(
            "operator_login must be one exact bounded Tailscale login"
        )
    if len(value) > MAX_OPERATOR_LOGIN_CHARS:
        raise ControlSchemaError("operator_login is too long")
    return value


def _secret_bytes(secret: bytes) -> bytes:
    if (
        not isinstance(secret, bytes)
        or not 32 <= len(secret) <= 4096
        or b"\r" in secret
        or b"\n" in secret
    ):
        raise ControlConfigurationError(
            "control HMAC credential must contain 32-4096 exact bytes without CR/LF"
        )
    return secret


def derive_activation_bound_hmac_key(
    secret: bytes, activation_receipt_digest: str
) -> bytes:
    """Derive a printable normal-control epoch key for the unchanged v1 wire."""
    key = _secret_bytes(secret)
    if not isinstance(activation_receipt_digest, str) or not _SHA256_REF_RE.fullmatch(
        activation_receipt_digest
    ):
        raise ControlSchemaError("activation receipt digest is invalid")
    return hmac.new(
        key,
        NORMAL_ACTIVATION_HMAC_DOMAIN + activation_receipt_digest.encode("ascii"),
        hashlib.sha256,
    ).hexdigest().encode("ascii")


def canonical_json_bytes(value: Mapping[str, Any]) -> bytes:
    """Return the only JSON byte representation admitted by this protocol."""

    try:
        rendered = json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        )
    except (TypeError, ValueError) as exc:
        raise ControlSchemaError("control JSON is not canonicalizable") from exc
    return rendered.encode("utf-8")


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ControlSchemaError("control JSON contains a duplicate key")
        result[key] = value
    return result


def _reject_json_constant(value: str) -> None:
    raise ControlSchemaError(f"control JSON contains invalid constant {value}")


def current_immutable_release_sha() -> str:
    """Derive the frozen release identity without accepting ambient config."""
    release_sha = Path(__file__).resolve(strict=True).parents[1].name
    if not _RELEASE_SHA_RE.fullmatch(release_sha):
        raise ControlConfigurationError(
            "control process is not executing from an immutable release root"
        )
    return release_sha


def _stable_file_identity(value: os.stat_result) -> tuple[int, ...]:
    return (
        value.st_dev,
        value.st_ino,
        value.st_uid,
        value.st_gid,
        value.st_mode,
        value.st_nlink,
        value.st_size,
        value.st_mtime_ns,
        value.st_ctime_ns,
    )


def _read_campaign_activation_bytes(
    path: Path,
    *,
    expected_owner_uid: int | None,
    expected_group_gid: int | None,
) -> bytes:
    """Read one producer-owned activation proof through stable no-follow custody."""
    nofollow = getattr(os, "O_NOFOLLOW", None)
    directory = getattr(os, "O_DIRECTORY", None)
    if (
        not isinstance(nofollow, int)
        or nofollow == 0
        or not isinstance(directory, int)
        or directory == 0
    ):
        raise ControlConfigurationError(
            "campaign activation custody requires O_NOFOLLOW and O_DIRECTORY"
        )
    if not path.is_absolute() or ".." in path.parts:
        raise ControlConfigurationError(
            "campaign activation proof path must be absolute and non-traversing"
        )
    flags = os.O_RDONLY | nofollow | directory | getattr(os, "O_CLOEXEC", 0)
    try:
        parent = os.open(path.parent, flags)
    except OSError as exc:
        raise ControlSchemaError("campaign activation proof is unavailable") from exc
    descriptor = -1
    try:
        parent_identity = os.fstat(parent)
        if (
            not stat.S_ISDIR(parent_identity.st_mode)
            or stat.S_IMODE(parent_identity.st_mode) != 0o750
            or (
                expected_owner_uid is not None
                and parent_identity.st_uid != expected_owner_uid
            )
            or (
                expected_group_gid is not None
                and parent_identity.st_gid != expected_group_gid
            )
        ):
            raise ControlSchemaError("campaign activation parent custody is invalid")
        entry = os.stat(path.name, dir_fd=parent, follow_symlinks=False)
        if (
            not stat.S_ISREG(entry.st_mode)
            or stat.S_IMODE(entry.st_mode) != 0o640
            or entry.st_nlink != 1
            or not 0 < entry.st_size <= MAX_CAMPAIGN_ACTIVATION_BYTES
            or entry.st_uid != parent_identity.st_uid
            or entry.st_gid != parent_identity.st_gid
        ):
            raise ControlSchemaError("campaign activation proof custody is invalid")
        descriptor = os.open(
            path.name,
            os.O_RDONLY | nofollow | getattr(os, "O_CLOEXEC", 0),
            dir_fd=parent,
        )
        before = os.fstat(descriptor)
        if _stable_file_identity(before) != _stable_file_identity(entry):
            raise ControlSchemaError("campaign activation proof changed during open")
        chunks: list[bytes] = []
        remaining = MAX_CAMPAIGN_ACTIVATION_BYTES + 1
        while remaining:
            chunk = os.read(descriptor, min(4096, remaining))
            if not chunk:
                break
            chunks.append(chunk)
            remaining -= len(chunk)
        raw = b"".join(chunks)
        after = os.fstat(descriptor)
        final_entry = os.stat(path.name, dir_fd=parent, follow_symlinks=False)
        if (
            remaining <= 0
            or len(raw) != before.st_size
            or _stable_file_identity(before) != _stable_file_identity(after)
            or _stable_file_identity(before) != _stable_file_identity(final_entry)
        ):
            raise ControlSchemaError("campaign activation proof changed while read")
        return raw
    except FileNotFoundError as exc:
        raise ControlSchemaError("campaign activation proof is unavailable") from exc
    except OSError as exc:
        raise ControlSchemaError("campaign activation proof cannot be read") from exc
    finally:
        if descriptor >= 0:
            os.close(descriptor)
        os.close(parent)


def validate_campaign_activation_proof(
    path: Path,
    *,
    expected_release_sha: str,
    operator_login: str,
    now: datetime | None = None,
    expected_owner_uid: int | None = None,
    expected_group_gid: int | None = None,
) -> dict[str, Any]:
    """Admit the exact sequence-2 capability projection for normal controls."""
    raw = _read_campaign_activation_bytes(
        path,
        expected_owner_uid=expected_owner_uid,
        expected_group_gid=expected_group_gid,
    )
    try:
        payload = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=_reject_duplicate_keys,
            parse_constant=_reject_json_constant,
        )
    except UnicodeDecodeError as exc:
        raise ControlSchemaError("campaign activation proof must be UTF-8") from exc
    except json.JSONDecodeError as exc:
        raise ControlSchemaError("campaign activation proof is not valid JSON") from exc
    if not isinstance(payload, dict):
        raise ControlSchemaError("campaign activation proof must be an object")
    if raw != canonical_json_bytes(payload) + b"\n":
        raise ControlSchemaError("campaign activation proof bytes are not canonical")
    return validate_campaign_activation_payload(
        payload,
        expected_release_sha=expected_release_sha,
        operator_login=operator_login,
        now=now,
    )


def validate_campaign_activation_payload(
    payload: Mapping[str, Any],
    *,
    expected_release_sha: str,
    operator_login: str,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Validate producer or consumer bytes as one exact activation capability."""
    if not _RELEASE_SHA_RE.fullmatch(expected_release_sha):
        raise ControlConfigurationError("expected release SHA is invalid")
    login = validate_operator_login(operator_login)
    reference = _require_aware_utc(now or utc_now())
    stop = _parse_timestamp(SADHANA_CAMPAIGN_STOP_UTC, field="campaign_stop_utc")
    if reference >= stop:
        raise ControlSchemaError("campaign activation proof is stale")
    if not isinstance(payload, Mapping):
        raise ControlSchemaError("campaign activation proof must be an object")
    _require_exact_fields(
        payload,
        CAMPAIGN_ACTIVATION_FIELDS,
        object_name="campaign activation proof",
    )
    activated_at = _parse_timestamp(payload.get("activated_at"), field="activated_at")
    expected_login_sha256 = hashlib.sha256(login.encode("ascii")).hexdigest()
    digest = payload.get("receipt_digest")
    canonical = dict(payload)
    canonical.pop("receipt_digest", None)
    expected_digest = (
        "sha256:" + hashlib.sha256(canonical_json_bytes(canonical)).hexdigest()
    )
    sha_fields = (
        "config_digest",
        "dispatch_enable_receipt_digest",
        "account_ui_confirmation_receipt_digest",
        "authority_receipt_sha256",
        "receipt_digest",
    )
    if (
        payload.get("schema_version") != CAMPAIGN_ACTIVATION_SCHEMA
        or payload.get("mission_id") != SADHANA_CAMPAIGN_ID
        or payload.get("release_sha") != expected_release_sha
        or type(payload.get("campaign_generation")) is not int
        or payload.get("campaign_generation") != 1
        or type(payload.get("transition_sequence")) is not int
        or payload.get("transition_sequence") != 2
        or payload.get("control_state") != "RUNNING"
        or payload.get("action") != "resume"
        or payload.get("operator_login_sha256") != expected_login_sha256
        or not _RAW_SHA256_RE.fullmatch(expected_login_sha256)
        or not isinstance(digest, str)
        or digest != expected_digest
        or any(
            not isinstance(payload.get(field), str)
            or not _SHA256_REF_RE.fullmatch(payload[field])
            for field in sha_fields
        )
        or not isinstance(payload.get("authority_receipt_ref"), str)
        or not _AUTHORITY_RECEIPT_REF_RE.fullmatch(payload["authority_receipt_ref"])
        or activated_at > reference + MAX_ISSUED_AT_SKEW
        or activated_at >= stop
        or payload.get("external_effect_performed") is not False
    ):
        raise ControlSchemaError("campaign activation proof differs")
    return dict(payload)


@dataclass(frozen=True)
class OperatorControlRequest:
    action: ControlAction
    request_id: str
    idempotency_key: str
    issued_at: str
    expires_at: str
    reason: str

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> OperatorControlRequest:
        if not isinstance(value, Mapping):
            raise ControlSchemaError("request must be an object")
        _require_exact_fields(value, REQUEST_FIELDS, object_name="request")
        try:
            action = ControlAction(value["action"])
        except (TypeError, ValueError) as exc:
            raise ControlSchemaError(
                "action is not an admitted operational action"
            ) from exc
        request = cls(
            action=action,
            request_id=_validate_identifier(value["request_id"], field="request_id"),
            idempotency_key=_validate_identifier(
                value["idempotency_key"], field="idempotency_key"
            ),
            issued_at=str(value["issued_at"]),
            expires_at=str(value["expires_at"]),
            reason=_validate_reason(value["reason"]),
        )
        issued_at = _parse_timestamp(request.issued_at, field="issued_at")
        expires_at = _parse_timestamp(request.expires_at, field="expires_at")
        if expires_at <= issued_at:
            raise ControlSchemaError("expires_at must be after issued_at")
        if expires_at - issued_at > MAX_REQUEST_TTL:
            raise ControlSchemaError("request lifetime exceeds 120 seconds")
        return request

    def as_dict(self) -> dict[str, str]:
        return {**asdict(self), "action": self.action.value}

    def validate_time_window(self, *, now: datetime | None = None) -> None:
        reference = _require_aware_utc(now or utc_now())
        issued_at = _parse_timestamp(self.issued_at, field="issued_at")
        expires_at = _parse_timestamp(self.expires_at, field="expires_at")
        if issued_at > reference + MAX_ISSUED_AT_SKEW:
            raise ControlFutureRequestError("request was issued too far in the future")
        if reference >= expires_at:
            raise ControlExpiredError("request has expired")


@dataclass(frozen=True)
class OperatorControlEnvelope:
    schema: str
    operator_login: str
    request: OperatorControlRequest
    hmac_sha256: str

    @classmethod
    def sign(
        cls,
        request: OperatorControlRequest,
        *,
        operator_login: str,
        secret: bytes,
        now: datetime | None = None,
    ) -> OperatorControlEnvelope:
        request.validate_time_window(now=now)
        login = validate_operator_login(operator_login)
        key = _secret_bytes(secret)
        unsigned = {
            "schema": CONTROL_SCHEMA,
            "operator_login": login,
            "request": request.as_dict(),
        }
        signature = hmac.new(
            key, canonical_json_bytes(unsigned), hashlib.sha256
        ).hexdigest()
        return cls(
            schema=CONTROL_SCHEMA,
            operator_login=login,
            request=request,
            hmac_sha256=signature,
        )

    def unsigned_dict(self) -> dict[str, Any]:
        return dict(
            schema=self.schema,
            operator_login=self.operator_login,
            request=self.request.as_dict(),
        )

    def as_dict(self) -> dict[str, Any]:
        return {**self.unsigned_dict(), "hmac_sha256": self.hmac_sha256}

    def canonical_bytes(self) -> bytes:
        return canonical_json_bytes(self.as_dict())

    @property
    def envelope_sha256(self) -> str:
        return f"sha256:{hashlib.sha256(self.canonical_bytes()).hexdigest()}"


def decode_untrusted_canonical_envelope(raw: bytes) -> OperatorControlEnvelope:
    """Parse exact v1 bytes for key selection; this does not authenticate them."""
    if not isinstance(raw, bytes) or not raw or len(raw) > MAX_ENVELOPE_BYTES:
        raise ControlSchemaError("control envelope size is outside bounds")
    try:
        decoded = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=_reject_duplicate_keys,
            parse_constant=_reject_json_constant,
        )
    except UnicodeDecodeError as exc:
        raise ControlSchemaError("control envelope must be UTF-8") from exc
    except json.JSONDecodeError as exc:
        raise ControlSchemaError("control envelope is not valid JSON") from exc
    if not isinstance(decoded, dict):
        raise ControlSchemaError("control envelope must be an object")
    _require_exact_fields(decoded, ENVELOPE_FIELDS, object_name="envelope")
    if decoded.get("schema") != CONTROL_SCHEMA:
        raise ControlSchemaError("control envelope schema is not supported")
    login = validate_operator_login(decoded["operator_login"])
    request_raw = decoded["request"]
    if not isinstance(request_raw, dict):
        raise ControlSchemaError("request must be an object")
    request = OperatorControlRequest.from_mapping(request_raw)
    signature = decoded["hmac_sha256"]
    if not isinstance(signature, str) or not _HMAC_RE.fullmatch(signature):
        raise ControlAuthenticationError("control HMAC has an invalid shape")
    envelope = OperatorControlEnvelope(
        schema=CONTROL_SCHEMA,
        operator_login=login,
        request=request,
        hmac_sha256=signature,
    )
    if raw != envelope.canonical_bytes():
        raise ControlSchemaError("control envelope bytes are not canonical")
    return envelope


def decode_and_verify_envelope(
    raw: bytes,
    *,
    secret: bytes,
    now: datetime | None = None,
    expected_actions: Set[ControlAction] | None = None,
    freshness_policy: FreshnessPolicy = FreshnessPolicy.STRICT,
) -> OperatorControlEnvelope:
    """Verify exact v1 bytes/HMAC and, by default, current freshness.

    ``AUTHORITY_REPLAY`` is only for normal inflight custody.  Its callback must
    durably look up an exact prior application before rejecting an expired new
    request and must never newly apply an out-of-window request.
    """
    envelope = decode_untrusted_canonical_envelope(raw)
    key = _secret_bytes(secret)
    expected_hmac = hmac.new(
        key, canonical_json_bytes(envelope.unsigned_dict()), hashlib.sha256
    ).hexdigest()
    if not hmac.compare_digest(envelope.hmac_sha256, expected_hmac):
        raise ControlAuthenticationError("control HMAC verification failed")
    if not isinstance(freshness_policy, FreshnessPolicy):
        raise ControlConfigurationError("control freshness policy is invalid")
    if freshness_policy is FreshnessPolicy.STRICT:
        envelope.request.validate_time_window(now=now)
    if expected_actions is not None and envelope.request.action not in expected_actions:
        raise ControlSchemaError("control action reached the wrong inbox")
    return envelope


def control_filename(idempotency_key: str) -> str:
    key = _validate_identifier(idempotency_key, field="idempotency_key")
    digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
    return f"{digest}.control.json"


@dataclass(frozen=True)
class InboxPublication:
    request_id: str
    idempotency_key: str
    action: ControlAction
    inbox: InboxKind
    path: Path
    replayed: bool
    source_envelope_sha256: str
    applied: bool = False
    decision_applied: bool = False
    effect_executed: bool = False


@dataclass(frozen=True)
class ControlInboxPublisher:
    normal_inbox: Path = DEFAULT_NORMAL_INBOX
    emergency_inbox: Path = DEFAULT_EMERGENCY_INBOX

    def publish(
        self,
        request: OperatorControlRequest,
        *,
        operator_login: str,
        secret: bytes,
        now: datetime | None = None,
    ) -> InboxPublication:
        envelope = OperatorControlEnvelope.sign(
            request,
            operator_login=operator_login,
            secret=secret,
            now=now,
        )
        if request.action is ControlAction.EMERGENCY_STOP:
            inbox = InboxKind.EMERGENCY
            directory = self.emergency_inbox
        else:
            inbox = InboxKind.NORMAL
            directory = self.normal_inbox
        filename = control_filename(request.idempotency_key)
        replayed = _atomic_publish(directory, filename, envelope.canonical_bytes())
        return InboxPublication(
            request_id=request.request_id,
            idempotency_key=request.idempotency_key,
            action=request.action,
            inbox=inbox,
            path=directory / filename,
            replayed=replayed,
            source_envelope_sha256=envelope.envelope_sha256,
        )


def read_control_candidate_bytes(path: Path) -> bytes:
    """Read one stable regular candidate without granting it authenticity."""
    if not _CONTROL_FILENAME_RE.fullmatch(path.name):
        raise ControlSchemaError("control candidate filename is invalid")
    directory_descriptor = _open_directory_nofollow(path.parent)
    try:
        return _read_regular_entry(directory_descriptor, path.name)
    finally:
        os.close(directory_descriptor)


def read_control_candidate(
    path: Path,
    *,
    secret: bytes,
    now: datetime | None = None,
    expected_actions: Set[ControlAction] | None = None,
    freshness_policy: FreshnessPolicy = FreshnessPolicy.STRICT,
) -> OperatorControlEnvelope:
    """Safely read one candidate for supervisor or root-unit validation."""

    payload = read_control_candidate_bytes(path)
    envelope = decode_and_verify_envelope(
        payload,
        secret=secret,
        now=now,
        expected_actions=expected_actions,
        freshness_policy=freshness_policy,
    )
    if path.name != control_filename(envelope.request.idempotency_key):
        raise ControlIdempotencyConflict(
            "candidate filename does not bind its idempotency key"
        )
    return envelope
