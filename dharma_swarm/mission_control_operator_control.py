"""Signed filesystem protocol for bounded SADHANA operator controls.

This module is deliberately an application adapter, not a state owner.  It
does not import Mission Control, TaskBoard, RuntimeStateStore, a provider, or
an executor.  The HTTP ingress publishes authenticated request *candidates*;
the supervisor applies normal controls through the callbacks defined here.

Emergency stop uses a separate inbox.  A release-owned root path unit must
validate that request and stop the supervisor before it records application.
Ordinary reconciliation therefore accepts only ``pause`` and ``resume``.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import unicodedata
from collections.abc import Awaitable, Callable, Mapping, Set
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
from pathlib import Path
from typing import Any

from dharma_swarm._mission_control_operator_control_fs import (
    CONTROL_CLAIM_FILENAME_RE as _CONTROL_CLAIM_FILENAME_RE,
    CONTROL_FILE_MODE,
    CONTROL_FILENAME_RE as _CONTROL_FILENAME_RE,
    CONTROL_QUARANTINE_FILENAME_RE as _CONTROL_QUARANTINE_FILENAME_RE,
    CONTROL_QUARANTINE_RECEIPT_FILENAME_RE as _CONTROL_QUARANTINE_RECEIPT_FILENAME_RE,
    MAX_ENVELOPE_BYTES,
    TERMINAL_FILENAME_RE as _TERMINAL_FILENAME_RE,
    ControlAuthenticationError,
    ControlConfigurationError,
    ControlExpiredError,
    ControlFutureRequestError,
    ControlIdempotencyConflict,
    ControlSchemaError,
    InboxUnavailable,
    OperatorControlError,
    UnsafeInboxEntry,
    atomic_move_regular as _atomic_move_regular,
    atomic_publish as _atomic_publish,
    claimed_control_filename as _claimed_control_filename,
    open_directory_nofollow as _open_directory_nofollow,
    promote_claimed_regular as _promote_claimed_regular,
    quarantine_receipt_filename as _quarantine_receipt_filename,
    quarantine_unsafe as _quarantine_unsafe,
    quarantined_control_identity as _quarantined_control_identity,
    read_regular_entry as _read_regular_entry,
)

CONTROL_SCHEMA = "dharma.sadhana.operator_control.v1"
DEFAULT_CONTROL_ROOT = Path("/run/dharma-sadhana/control")
DEFAULT_NORMAL_INBOX = DEFAULT_CONTROL_ROOT / "normal"
DEFAULT_EMERGENCY_INBOX = DEFAULT_CONTROL_ROOT / "emergency"
DEFAULT_INFLIGHT_INBOX = DEFAULT_CONTROL_ROOT / "inflight"
DEFAULT_APPLIED_INBOX = DEFAULT_CONTROL_ROOT / "applied"
DEFAULT_REJECTED_INBOX = DEFAULT_CONTROL_ROOT / "rejected"
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

_IDENTIFIER_RE = re.compile(r"\A[A-Za-z0-9][A-Za-z0-9._:-]{0,127}\Z")
_LOGIN_RE = re.compile(r"\A[A-Za-z0-9][A-Za-z0-9@._+:-]{0,253}\Z")
_TIMESTAMP_RE = re.compile(r"\A\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?Z\Z")
_HMAC_RE = re.compile(r"\A[0-9a-f]{64}\Z")
_SHA256_REF_RE = re.compile(r"\Asha256:[0-9a-f]{64}\Z")


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


def decode_and_verify_envelope(
    raw: bytes,
    *,
    secret: bytes,
    now: datetime | None = None,
    expected_actions: Set[ControlAction] | None = None,
    freshness_policy: FreshnessPolicy = FreshnessPolicy.STRICT,
) -> OperatorControlEnvelope:
    """Verify canonical bytes/HMAC and, by default, current freshness.

    ``AUTHORITY_REPLAY`` is only for normal inflight custody.  Its callback must
    durably look up an exact prior application before rejecting an expired new
    request and must never newly apply an out-of-window request.
    """

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
    if decoded["schema"] != CONTROL_SCHEMA:
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
    key = _secret_bytes(secret)
    expected_hmac = hmac.new(
        key, canonical_json_bytes(envelope.unsigned_dict()), hashlib.sha256
    ).hexdigest()
    if not hmac.compare_digest(signature, expected_hmac):
        raise ControlAuthenticationError("control HMAC verification failed")
    if not isinstance(freshness_policy, FreshnessPolicy):
        raise ControlConfigurationError("control freshness policy is invalid")
    if freshness_policy is FreshnessPolicy.STRICT:
        request.validate_time_window(now=now)
    if expected_actions is not None and request.action not in expected_actions:
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


def read_control_candidate(
    path: Path,
    *,
    secret: bytes,
    now: datetime | None = None,
    expected_actions: Set[ControlAction] | None = None,
    freshness_policy: FreshnessPolicy = FreshnessPolicy.STRICT,
) -> OperatorControlEnvelope:
    """Safely read one candidate for supervisor or root-unit validation."""

    if not _CONTROL_FILENAME_RE.fullmatch(path.name):
        raise ControlSchemaError("control candidate filename is invalid")
    directory_descriptor = _open_directory_nofollow(path.parent)
    try:
        payload = _read_regular_entry(directory_descriptor, path.name)
    finally:
        os.close(directory_descriptor)
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


@dataclass(frozen=True)
class AuthorityApplication:
    request_id: str
    idempotency_key: str
    envelope_sha256: str
    status: ApplicationStatus
    authority_receipt_ref: str = ""
    authority_receipt_sha256: str = ""
    effect_observed: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.status, ApplicationStatus):
            raise ValueError("authority application status is invalid")
        _validate_identifier(self.request_id, field="request_id")
        _validate_identifier(self.idempotency_key, field="idempotency_key")
        if not _SHA256_REF_RE.fullmatch(self.envelope_sha256):
            raise ValueError("authority application requires an envelope sha256 ref")
        _validate_authority_receipt_ref(self.authority_receipt_ref)
        if self.status is ApplicationStatus.DEFERRED:
            if self.authority_receipt_ref or self.authority_receipt_sha256:
                raise ValueError(
                    "deferred control cannot claim a persisted authority receipt"
                )
        else:
            if not self.authority_receipt_ref:
                raise ValueError(
                    "terminal control requires an authority receipt reference"
                )
            if not _SHA256_REF_RE.fullmatch(self.authority_receipt_sha256):
                raise ValueError(
                    "terminal control requires a canonical receipt sha256 ref"
                )
        if self.effect_observed is not False:
            raise ValueError(
                "authority application cannot self-claim an observed effect"
            )


@dataclass(frozen=True)
class SupervisorControlCallbacks:
    """Single atomic authority seam; exact lookup precedes TTL/CAS rejection."""

    apply: Callable[[OperatorControlRequest, str, str], Awaitable[AuthorityApplication]]


@dataclass(frozen=True)
class ReconcileResult:
    filename: str
    status: ReconcileStatus
    request_id: str = ""
    idempotency_key: str = ""
    action: str = ""
    envelope_sha256: str = ""
    authority_receipt_ref: str = ""
    authority_receipt_sha256: str = ""
    inbox_acknowledged: bool = False
    applied: bool = False
    effect_observed: bool = False
    terminal_receipt_path: str = ""
    terminal_candidate_path: str = ""
    error_code: str = ""


def _terminal_receipt_bytes(
    *,
    envelope: OperatorControlEnvelope | None,
    envelope_sha256: str,
    status: str,
    error_code: str,
    application: AuthorityApplication | None = None,
) -> bytes:
    request = envelope.request if envelope else None
    return canonical_json_bytes(
        {
            "schema": TERMINAL_RECEIPT_SCHEMA,
            "control_semantics_sha256": CONTROL_SEMANTICS_SHA256,
            "control_http_binding_sha256": CONTROL_HTTP_BINDING_SHA256,
            "control_authority_binding_sha256": AUTHORITY_BINDING_SHA256,
            "request_id": request.request_id if request else "",
            "idempotency_key": request.idempotency_key if request else "",
            "action": request.action.value if request else "",
            "operator_login": envelope.operator_login if envelope else "",
            "envelope_sha256": envelope_sha256,
            "status": status,
            "error_code": error_code,
            "authority_receipt_ref": application.authority_receipt_ref
            if application
            else "",
            "authority_receipt_sha256": (
                application.authority_receipt_sha256 if application else ""
            ),
            "authority_applied": bool(
                application and application.status is ApplicationStatus.APPLIED
            ),
            "effect_observed": False,
        }
    )


def _envelope_result(
    filename: str,
    status: ReconcileStatus,
    envelope: OperatorControlEnvelope,
    **fields: Any,
) -> ReconcileResult:
    request = envelope.request
    return ReconcileResult(
        filename=filename,
        status=status,
        request_id=request.request_id,
        idempotency_key=request.idempotency_key,
        action=request.action.value,
        envelope_sha256=envelope.envelope_sha256,
        inbox_acknowledged=True,
        **fields,
    )


def terminal_filename(control_candidate_filename: str) -> str:
    if not _CONTROL_FILENAME_RE.fullmatch(control_candidate_filename):
        raise ControlSchemaError("control candidate filename is invalid")
    return control_candidate_filename.removesuffix(".control.json") + ".terminal.json"


class OperatorControlInboxReconciler:
    """Async normal-inbox custody adapter for the sole campaign writer."""

    def __init__(
        self,
        *,
        normal_inbox: Path,
        inflight_inbox: Path = DEFAULT_INFLIGHT_INBOX,
        applied_inbox: Path = DEFAULT_APPLIED_INBOX,
        rejected_inbox: Path = DEFAULT_REJECTED_INBOX,
        secret: bytes,
        max_candidates_per_cycle: int = 128,
    ) -> None:
        if not 1 <= max_candidates_per_cycle <= 1024:
            raise ValueError("max_candidates_per_cycle must be between 1 and 1024")
        self._normal_inbox = normal_inbox
        self._inflight_inbox = inflight_inbox
        self._applied_inbox = applied_inbox
        self._rejected_inbox = rejected_inbox
        self._secret = _secret_bytes(secret)
        self._max_candidates = max_candidates_per_cycle
        self._max_scan = min(4096, max(64, max_candidates_per_cycle * 4))
        directories = {
            normal_inbox,
            inflight_inbox,
            applied_inbox,
            rejected_inbox,
        }
        if len(directories) != 4:
            raise ValueError("normal custody directories must be distinct")

    @staticmethod
    def _matching_names(
        directory: Path, *, pattern: re.Pattern[str], limit: int
    ) -> list[str]:
        directory_descriptor = _open_directory_nofollow(directory)
        try:
            names = sorted(
                name
                for name in os.listdir(directory_descriptor)
                if pattern.fullmatch(name)
            )
        finally:
            os.close(directory_descriptor)
        return names[:limit]

    @classmethod
    def _candidate_names(cls, directory: Path, *, limit: int) -> list[str]:
        return cls._matching_names(
            directory, pattern=_CONTROL_FILENAME_RE, limit=limit
        )

    @classmethod
    def _claim_names(cls, directory: Path, *, limit: int) -> list[str]:
        return cls._matching_names(
            directory, pattern=_CONTROL_CLAIM_FILENAME_RE, limit=limit
        )

    @classmethod
    def _quarantine_names(cls, directory: Path, *, limit: int) -> list[str]:
        return cls._matching_names(
            directory, pattern=_CONTROL_QUARANTINE_FILENAME_RE, limit=limit
        )

    @classmethod
    def _quarantine_receipt_names(
        cls, directory: Path, *, limit: int
    ) -> set[str]:
        return set(
            cls._matching_names(
                directory,
                pattern=_CONTROL_QUARANTINE_RECEIPT_FILENAME_RE,
                limit=limit,
            )
        )

    async def reconcile_once(
        self,
        callbacks: SupervisorControlCallbacks,
        *,
        now: datetime | None = None,
    ) -> list[ReconcileResult]:
        results = self._recover_quarantine_evidence()
        processed = 0

        for claim_directory in (
            self._inflight_inbox,
            self._applied_inbox,
            self._rejected_inbox,
        ):
            for claim_name in self._claim_names(
                claim_directory, limit=self._max_scan
            ):
                claim_path = claim_directory / claim_name
                control_name = _claimed_control_filename(claim_name)
                try:
                    _promote_claimed_regular(claim_path)
                except OperatorControlError as exc:
                    results.append(
                        self._resolve_claim_failure(
                            claim_path,
                            control_filename=control_name,
                            error=exc,
                        )
                    )

        for destination, expected_status in (
            (self._applied_inbox, ApplicationStatus.APPLIED),
            (self._rejected_inbox, ApplicationStatus.REJECTED),
        ):
            for filename in self._unterminated_candidate_names(destination):
                if processed >= self._max_candidates:
                    return results
                results.append(
                    await self._recover_terminal_candidate(
                        destination / filename,
                        expected_status=expected_status,
                        callbacks=callbacks,
                        now=now,
                    )
                )
                processed += 1

        inflight_names = self._candidate_names(
            self._inflight_inbox, limit=self._max_scan
        )
        for filename in inflight_names:
            if processed >= self._max_candidates:
                break
            results.append(
                await self._reconcile_inflight(filename, callbacks=callbacks, now=now)
            )
            processed += 1

        if processed >= self._max_candidates:
            return results
        normal_names = self._candidate_names(self._normal_inbox, limit=self._max_scan)
        for filename in normal_names:
            if processed >= self._max_candidates:
                break
            try:
                _atomic_move_regular(
                    self._normal_inbox / filename, self._inflight_inbox
                )
            except OperatorControlError as exc:
                results.append(
                    self._resolve_move_failure(
                        source=self._normal_inbox / filename,
                        error=exc,
                    )
                )
                continue
            results.append(
                await self._reconcile_inflight(filename, callbacks=callbacks, now=now)
            )
            processed += 1
        return results

    def _recover_quarantine_evidence(self) -> list[ReconcileResult]:
        """Finish sidecars only after their exact quarantine carrier exists."""

        receipts = self._quarantine_receipt_names(
            self._rejected_inbox, limit=self._max_scan
        )
        results: list[ReconcileResult] = []
        for quarantine_name in self._quarantine_names(
            self._rejected_inbox, limit=self._max_scan
        ):
            if _quarantine_receipt_filename(quarantine_name) in receipts:
                continue
            results.append(
                self._record_quarantine_evidence(
                    self._rejected_inbox / quarantine_name
                )
            )
        return results

    def _unterminated_candidate_names(self, directory: Path) -> list[str]:
        directory_descriptor = _open_directory_nofollow(directory)
        try:
            names = set(os.listdir(directory_descriptor))
        finally:
            os.close(directory_descriptor)
        return [
            name
            for name in sorted(names)
            if _CONTROL_FILENAME_RE.fullmatch(name)
            and terminal_filename(name) not in names
        ][: self._max_scan]

    async def _recover_terminal_candidate(
        self,
        path: Path,
        *,
        expected_status: ApplicationStatus,
        callbacks: SupervisorControlCallbacks,
        now: datetime | None,
    ) -> ReconcileResult:
        """Complete a candidate-first terminal transition after a crash."""

        try:
            envelope = read_control_candidate(
                path,
                secret=self._secret,
                now=now,
                expected_actions=frozenset({ControlAction.PAUSE, ControlAction.RESUME}),
                freshness_policy=FreshnessPolicy.AUTHORITY_REPLAY,
            )
        except OperatorControlError as exc:
            return self._terminalize_invalid(path, error=exc)

        try:
            application = await callbacks.apply(
                envelope.request,
                envelope.operator_login,
                envelope.envelope_sha256,
            )
        except Exception:
            return _envelope_result(
                path.name,
                ReconcileStatus.DEFERRED,
                envelope,
                terminal_candidate_path=str(path),
                error_code="authority_callback_failed",
            )
        try:
            self._validate_application(application, envelope)
        except (TypeError, ValueError, ControlIdempotencyConflict):
            return _envelope_result(
                path.name,
                ReconcileStatus.CONFLICT,
                envelope,
                terminal_candidate_path=str(path),
                error_code="idempotency_conflict",
            )
        if application.status is not expected_status:
            return _envelope_result(
                path.name,
                ReconcileStatus.CONFLICT,
                envelope,
                authority_receipt_ref=application.authority_receipt_ref,
                authority_receipt_sha256=application.authority_receipt_sha256,
                terminal_candidate_path=str(path),
                error_code="idempotency_conflict",
            )

        error_code = (
            "" if expected_status is ApplicationStatus.APPLIED else "authority_rejected"
        )
        receipt = _terminal_receipt_bytes(
            envelope=envelope,
            envelope_sha256=envelope.envelope_sha256,
            status=expected_status.value,
            error_code=error_code,
            application=application,
        )
        receipt_path = path.parent / terminal_filename(path.name)
        try:
            _atomic_publish(
                path.parent,
                receipt_path.name,
                receipt,
                filename_pattern=_TERMINAL_FILENAME_RE,
            )
        except OperatorControlError as exc:
            return _envelope_result(
                path.name,
                ReconcileStatus.CONFLICT,
                envelope,
                authority_receipt_ref=application.authority_receipt_ref,
                authority_receipt_sha256=application.authority_receipt_sha256,
                terminal_candidate_path=str(path),
                error_code=exc.code,
            )
        return _envelope_result(
            path.name,
            ReconcileStatus(expected_status.value),
            envelope,
            authority_receipt_ref=application.authority_receipt_ref,
            authority_receipt_sha256=application.authority_receipt_sha256,
            applied=expected_status is ApplicationStatus.APPLIED,
            terminal_receipt_path=str(receipt_path),
            terminal_candidate_path=str(path),
            error_code=error_code,
        )

    def _resolve_move_failure(
        self, *, source: Path, error: OperatorControlError
    ) -> ReconcileResult:
        claim_path = error.claim_path
        control_name = error.control_filename or source.name
        if isinstance(claim_path, Path):
            return self._resolve_claim_failure(
                claim_path,
                control_filename=control_name,
                error=error,
            )
        return ReconcileResult(
            filename=source.name,
            status=ReconcileStatus.DEFERRED,
            error_code=error.code,
        )

    def _resolve_claim_failure(
        self,
        claim_path: Path,
        *,
        control_filename: str,
        error: OperatorControlError,
    ) -> ReconcileResult:
        if isinstance(error, InboxUnavailable):
            return ReconcileResult(
                filename=control_filename,
                status=ReconcileStatus.DEFERRED,
                inbox_acknowledged=True,
                terminal_candidate_path=str(claim_path),
                error_code=error.code,
            )
        return self._quarantine_candidate(
            claim_path,
            control_filename=control_filename,
            error=error,
        )

    async def _reconcile_inflight(
        self,
        filename: str,
        *,
        callbacks: SupervisorControlCallbacks,
        now: datetime | None,
    ) -> ReconcileResult:
        path = self._inflight_inbox / filename
        try:
            envelope = read_control_candidate(
                path,
                secret=self._secret,
                now=now,
                expected_actions=frozenset({ControlAction.PAUSE, ControlAction.RESUME}),
                freshness_policy=FreshnessPolicy.AUTHORITY_REPLAY,
            )
        except OperatorControlError as exc:
            return self._terminalize_invalid(path, error=exc)

        request = envelope.request
        digest = envelope.envelope_sha256
        try:
            application = await callbacks.apply(
                request, envelope.operator_login, digest
            )
        except Exception:
            return _envelope_result(
                filename,
                ReconcileStatus.DEFERRED,
                envelope,
                error_code="authority_callback_failed",
            )
        try:
            self._validate_application(application, envelope)
        except (TypeError, ValueError, ControlIdempotencyConflict) as exc:
            protocol_error = ControlIdempotencyConflict(
                "authority application does not echo the exact request envelope"
            )
            protocol_error.__cause__ = exc
            return self._terminalize_verified_rejection(
                path, envelope=envelope, error=protocol_error
            )

        if application.status is ApplicationStatus.DEFERRED:
            return _envelope_result(
                filename,
                ReconcileStatus.DEFERRED,
                envelope,
                authority_receipt_ref=application.authority_receipt_ref,
                authority_receipt_sha256=application.authority_receipt_sha256,
                error_code="authority_deferred",
            )

        destination = (
            self._applied_inbox
            if application.status is ApplicationStatus.APPLIED
            else self._rejected_inbox
        )
        error_code = (
            ""
            if application.status is ApplicationStatus.APPLIED
            else "authority_rejected"
        )
        receipt = _terminal_receipt_bytes(
            envelope=envelope,
            envelope_sha256=digest,
            status=application.status.value,
            error_code=error_code,
            application=application,
        )
        try:
            receipt_path, candidate_path = self._terminalize(
                path, destination, receipt
            )
        except OperatorControlError as exc:
            return self._terminal_move_failure(
                source=path,
                destination=destination,
                envelope=envelope,
                application=application,
                error=exc,
            )
        return _envelope_result(
            filename,
            ReconcileStatus(application.status.value),
            envelope,
            authority_receipt_ref=application.authority_receipt_ref,
            authority_receipt_sha256=application.authority_receipt_sha256,
            applied=application.status is ApplicationStatus.APPLIED,
            terminal_receipt_path=str(receipt_path),
            terminal_candidate_path=str(candidate_path),
            error_code=error_code,
        )

    @staticmethod
    def _validate_application(
        application: AuthorityApplication,
        envelope: OperatorControlEnvelope,
    ) -> None:
        if not isinstance(application, AuthorityApplication):
            raise TypeError("authority callback returned an unsupported value")
        request = envelope.request
        if (
            application.request_id != request.request_id
            or application.idempotency_key != request.idempotency_key
            or application.envelope_sha256 != envelope.envelope_sha256
            or application.effect_observed
        ):
            raise ControlIdempotencyConflict("authority application identity mismatch")

    def _terminalize(
        self,
        source: Path,
        destination: Path,
        receipt: bytes,
    ) -> tuple[Path, Path]:
        # The canonical terminal receipt is the final commit marker.  Moving the
        # exact candidate first makes a crash recoverable without ever leaving a
        # receipt that claims a carrier which failed to enter terminal custody.
        _atomic_move_regular(source, destination)
        receipt_path = destination / terminal_filename(source.name)
        _atomic_publish(
            destination,
            receipt_path.name,
            receipt,
            filename_pattern=_TERMINAL_FILENAME_RE,
        )
        return receipt_path, destination / source.name

    def _terminalize_invalid(
        self, source: Path, *, error: OperatorControlError
    ) -> ReconcileResult:
        return self._quarantine_candidate(
            source,
            control_filename=source.name,
            error=error,
        )

    def _terminalize_verified_rejection(
        self,
        source: Path,
        *,
        envelope: OperatorControlEnvelope,
        error: OperatorControlError,
    ) -> ReconcileResult:
        quarantined = self._quarantine_candidate(
            source,
            control_filename=source.name,
            error=error,
        )
        return _envelope_result(
            source.name,
            ReconcileStatus.CONFLICT,
            envelope,
            terminal_receipt_path=quarantined.terminal_receipt_path,
            terminal_candidate_path=quarantined.terminal_candidate_path,
            error_code=error.code,
        )

    def _terminal_move_failure(
        self,
        *,
        source: Path,
        destination: Path,
        envelope: OperatorControlEnvelope,
        application: AuthorityApplication | None,
        error: OperatorControlError,
    ) -> ReconcileResult:
        claim_path = error.claim_path
        if isinstance(claim_path, Path) and not isinstance(error, InboxUnavailable):
            quarantined = self._quarantine_candidate(
                claim_path,
                control_filename=source.name,
                error=error,
            )
            return _envelope_result(
                source.name,
                ReconcileStatus.CONFLICT,
                envelope,
                authority_receipt_ref=(
                    application.authority_receipt_ref if application else ""
                ),
                authority_receipt_sha256=(
                    application.authority_receipt_sha256 if application else ""
                ),
                terminal_receipt_path=quarantined.terminal_receipt_path,
                terminal_candidate_path=quarantined.terminal_candidate_path,
                error_code=error.code,
            )
        durable_candidate = destination / source.name
        return _envelope_result(
            source.name,
            (
                ReconcileStatus.CONFLICT
                if isinstance(error, ControlIdempotencyConflict)
                else ReconcileStatus.DEFERRED
            ),
            envelope,
            authority_receipt_ref=(
                application.authority_receipt_ref if application else ""
            ),
            authority_receipt_sha256=(
                application.authority_receipt_sha256 if application else ""
            ),
            terminal_candidate_path=(
                str(durable_candidate) if durable_candidate.exists() else ""
            ),
            error_code=error.code,
        )

    def _quarantine_candidate(
        self,
        source: Path,
        *,
        control_filename: str,
        error: OperatorControlError,
    ) -> ReconcileResult:
        quarantine_path = _quarantine_unsafe(
            source,
            self._rejected_inbox,
            control_filename=control_filename,
            error_code=error.code,
        )
        return self._record_quarantine_evidence(quarantine_path)

    def _record_quarantine_evidence(
        self, quarantine_path: Path
    ) -> ReconcileResult:
        control_name, error_code = _quarantined_control_identity(
            quarantine_path.name
        )
        digest = ""
        try:
            directory_descriptor = _open_directory_nofollow(quarantine_path.parent)
            try:
                raw = _read_regular_entry(
                    directory_descriptor,
                    quarantine_path.name,
                    require_mode=False,
                )
            finally:
                os.close(directory_descriptor)
            digest = f"sha256:{hashlib.sha256(raw).hexdigest()}"
        except OperatorControlError:
            pass
        receipt = _terminal_receipt_bytes(
            envelope=None,
            envelope_sha256=digest,
            status="rejected",
            error_code=error_code,
        )
        receipt_path = self._rejected_inbox / _quarantine_receipt_filename(
            quarantine_path.name
        )
        _atomic_publish(
            self._rejected_inbox,
            receipt_path.name,
            receipt,
            filename_pattern=_CONTROL_QUARANTINE_RECEIPT_FILENAME_RE,
        )
        return ReconcileResult(
            filename=control_name,
            status=(
                ReconcileStatus.CONFLICT
                if error_code == ControlIdempotencyConflict.code
                else ReconcileStatus.INVALID
            ),
            envelope_sha256=digest,
            inbox_acknowledged=True,
            terminal_receipt_path=str(receipt_path),
            terminal_candidate_path=str(quarantine_path),
            error_code=error_code,
        )

__all__ = (
    "ApplicationStatus",
    "AUTHORITY_BINDING_SHA256",
    "AuthorityApplication",
    "CONTROL_FILE_MODE",
    "CONTROL_HTTP_BINDING_SHA256",
    "CONTROL_SCHEMA",
    "CONTROL_SEMANTICS_SHA256",
    "ControlAction",
    "ControlAuthenticationError",
    "ControlConfigurationError",
    "ControlExpiredError",
    "ControlFutureRequestError",
    "ControlIdempotencyConflict",
    "ControlInboxPublisher",
    "ControlSchemaError",
    "FreshnessPolicy",
    "InboxKind",
    "InboxPublication",
    "InboxUnavailable",
    "MAX_ENVELOPE_BYTES",
    "OPERATOR_CONTROL_SEMANTICS_SHA256",
    "OPERATOR_CONTROL_HTTP_BINDING_SHA256",
    "OPERATOR_CONTROL_AUTHORITY_BINDING_SHA256",
    "OperatorControlEnvelope",
    "OperatorControlError",
    "OperatorControlInboxReconciler",
    "OperatorControlRequest",
    "ReconcileResult",
    "ReconcileStatus",
    "SupervisorControlCallbacks",
    "UNSUPPORTED_DECISION_ACTIONS",
    "UnsafeInboxEntry",
    "canonical_json_bytes",
    "control_filename",
    "decode_and_verify_envelope",
    "read_control_candidate",
    "terminal_filename",
    "utc_now",
    "validate_operator_login",
)
