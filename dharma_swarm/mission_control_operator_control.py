"""Signed filesystem protocol and bounded SADHANA control reconciler.

Protocol authentication/publication lives in a private dependency module while
this stable public module retains the authority seam and custody reconciler.
It imports no Mission Control store, provider, executor, tool, or systemd API.
"""

from __future__ import annotations

import hashlib
import os
import re
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from dharma_swarm._mission_control_operator_control_fs import (
    CONTROL_CLAIM_FILENAME_RE as _CONTROL_CLAIM_FILENAME_RE,
    CONTROL_FILE_MODE,
    CONTROL_FILENAME_RE as _CONTROL_FILENAME_RE,
    CONTROL_QUARANTINE_FILENAME_RE as _CONTROL_QUARANTINE_FILENAME_RE,
    CONTROL_QUARANTINE_RECEIPT_FILENAME_RE as _CONTROL_QUARANTINE_RECEIPT_FILENAME_RE,
    TERMINAL_FILENAME_RE as _TERMINAL_FILENAME_RE,
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
from dharma_swarm._mission_control_operator_control_protocol import (
    AUTHORITY_BINDING_SHA256,
    CONTROL_HTTP_BINDING_SHA256,
    CONTROL_SCHEMA,
    CONTROL_SEMANTICS_SHA256,
    DEFAULT_APPLIED_INBOX,
    DEFAULT_CONTROL_ROOT as DEFAULT_CONTROL_ROOT,
    DEFAULT_EMERGENCY_INBOX as DEFAULT_EMERGENCY_INBOX,
    DEFAULT_INFLIGHT_INBOX,
    DEFAULT_NORMAL_INBOX as DEFAULT_NORMAL_INBOX,
    DEFAULT_REJECTED_INBOX,
    ENVELOPE_FIELDS as ENVELOPE_FIELDS,
    MAX_AUTHORITY_RECEIPT_REF_CHARS as MAX_AUTHORITY_RECEIPT_REF_CHARS,
    MAX_ENVELOPE_BYTES,
    MAX_IDENTIFIER_CHARS as MAX_IDENTIFIER_CHARS,
    MAX_ISSUED_AT_SKEW as MAX_ISSUED_AT_SKEW,
    MAX_OPERATOR_LOGIN_CHARS as MAX_OPERATOR_LOGIN_CHARS,
    MAX_REASON_CHARS as MAX_REASON_CHARS,
    MAX_REQUEST_TTL as MAX_REQUEST_TTL,
    OPERATOR_CONTROL_AUTHORITY_BINDING_SHA256,
    OPERATOR_CONTROL_HTTP_BINDING_SHA256,
    OPERATOR_CONTROL_SEMANTICS_SHA256,
    REQUEST_FIELDS as REQUEST_FIELDS,
    TERMINAL_RECEIPT_SCHEMA,
    UNSIGNED_ENVELOPE_FIELDS as UNSIGNED_ENVELOPE_FIELDS,
    UNSUPPORTED_DECISION_ACTIONS,
    ApplicationStatus,
    ControlAction,
    ControlAuthenticationError,
    ControlConfigurationError,
    ControlExpiredError,
    ControlFutureRequestError,
    ControlIdempotencyConflict,
    ControlInboxPublisher,
    ControlSchemaError,
    FreshnessPolicy,
    InboxKind,
    InboxPublication,
    OperatorControlEnvelope,
    OperatorControlRequest,
    ReconcileStatus,
    _secret_bytes,
    _SHA256_REF_RE,
    _validate_authority_receipt_ref,
    _validate_identifier,
    canonical_json_bytes,
    control_filename,
    decode_and_verify_envelope,
    read_control_candidate,
    utc_now,
    validate_operator_login,
)


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
