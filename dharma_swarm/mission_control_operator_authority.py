"""Atomic campaign-owned authority for authenticated pause and resume requests."""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Protocol

from dharma_swarm.mission_control_contract import MissionControlError, stable_id, utc_now
from dharma_swarm.mission_control_operator_state import (
    OPERATOR_CONTROL_RECEIPT_REF_PREFIX,
    OPERATOR_CONTROL_RECEIPT_SCHEMA,
    OPERATOR_CONTROL_RECEIPT_TYPE,
    canonical_utc_timestamp,
    initial_operator_control_state,
    runtime_receipt_content_digest,
    validate_operator_control_state,
)
from dharma_swarm.runtime_state import RuntimeReceipt, RuntimeStateStore, SessionState

_IDENTIFIER_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}")
_LOGIN_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9@._+:-]{0,253}")
_SHA256_RE = re.compile(r"sha256:[0-9a-f]{64}")


class OperatorControlRequestLike(Protocol):
    action: Any
    request_id: str
    idempotency_key: str
    issued_at: str
    expires_at: str
    reason: str

    def validate_time_window(self, *, now: datetime | None = None) -> None: ...


@dataclass(frozen=True, slots=True)
class CampaignOperatorApplication:
    request_id: str
    idempotency_key: str
    envelope_sha256: str
    status: str
    authority_receipt_ref: str = ""
    authority_receipt_sha256: str = ""
    effect_observed: bool = False

    def as_mobile_application(self) -> Any:
        """Construct the concrete adapter value only after that slice is installed."""
        from dharma_swarm.mission_control_operator_control import (  # noqa: PLC0415
            ApplicationStatus,
            AuthorityApplication,
        )

        return AuthorityApplication(
            request_id=self.request_id,
            idempotency_key=self.idempotency_key,
            envelope_sha256=self.envelope_sha256,
            status=ApplicationStatus(self.status),
            authority_receipt_ref=self.authority_receipt_ref,
            authority_receipt_sha256=self.authority_receipt_sha256,
            effect_observed=False,
        )


class CampaignOperatorAuthority:
    """Apply one exact request to the campaign session or replay its receipt."""

    def __init__(
        self,
        runtime: RuntimeStateStore,
        *,
        mission_id: str,
        session_id: str,
        config_digest: str,
        now: Callable[[], datetime] = utc_now,
    ) -> None:
        self._runtime = runtime
        self._mission_id = mission_id
        self._session_id = session_id
        self._config_digest = config_digest
        self._now = now

    async def apply(
        self,
        request: OperatorControlRequestLike,
        operator_login: str,
        source_envelope_sha256: str,
    ) -> CampaignOperatorApplication:
        request_id, idempotency_key, action = _request_identity(request)
        _validate_private_carrier(operator_login, source_envelope_sha256)
        receipt_id = _receipt_id(self._mission_id, idempotency_key)
        existing = await self._runtime.get_runtime_receipt(receipt_id)
        if existing is not None:
            return _application_from_receipt(existing)

        session = await self._require_session()
        now = self._now().astimezone(timezone.utc)
        prior_state = _session_control_state(session)
        rejection_reason = _rejection_reason(request, action=action, session=session, now=now)
        if rejection_reason:
            receipt = _control_receipt(
                mission_id=self._mission_id,
                config_digest=self._config_digest,
                session=session,
                request=request,
                request_id=request_id,
                idempotency_key=idempotency_key,
                action=action,
                operator_login=operator_login,
                source_envelope_sha256=source_envelope_sha256,
                prior_control_state=prior_state["control_state"],
                next_control_state=prior_state["control_state"],
                transition_sequence=prior_state["transition_sequence"],
                application_status="rejected",
                rejection_reason=rejection_reason,
                now=now,
            )
            try:
                stored = await self._runtime.insert_runtime_receipt_exact(receipt)
            except ValueError:
                raced = await self._runtime.get_runtime_receipt(receipt_id)
                if raced is None:
                    raise
                stored = raced
            return _application_from_receipt(stored)

        next_control_state = "PAUSED" if action == "pause" else "RUNNING"
        sequence = prior_state["transition_sequence"] + 1
        applied_at = max(now, session.updated_at + timedelta(microseconds=1))
        receipt = _control_receipt(
            mission_id=self._mission_id,
            config_digest=self._config_digest,
            session=session,
            request=request,
            request_id=request_id,
            idempotency_key=idempotency_key,
            action=action,
            operator_login=operator_login,
            source_envelope_sha256=source_envelope_sha256,
            prior_control_state=prior_state["control_state"],
            next_control_state=next_control_state,
            transition_sequence=sequence,
            application_status="applied",
            rejection_reason="",
            now=applied_at,
        )
        receipt_digest = runtime_receipt_content_digest(receipt)
        state = {
            "schema_version": "dharma.sadhana.operator_control_state.v1",
            "control_state": next_control_state,
            "campaign_generation": prior_state["campaign_generation"],
            "transition_sequence": sequence,
            "request_id": request_id,
            "idempotency_key": idempotency_key,
            "action": action,
            "source_envelope_sha256": source_envelope_sha256,
            "authority_receipt_ref": OPERATOR_CONTROL_RECEIPT_REF_PREFIX + receipt.receipt_id,
            "authority_receipt_sha256": receipt_digest,
            "authority_applied_at": canonical_utc_timestamp(applied_at),
            "effect_state": "unobserved",
            "effect_receipt_ref": "",
            "effect_receipt_sha256": "",
            "effect_observed_at": None,
        }
        validate_operator_control_state(
            state,
            expected_generation=prior_state["campaign_generation"],
        )
        replacement = SessionState(
            session_id=session.session_id,
            operator_id=session.operator_id,
            status="paused" if next_control_state == "PAUSED" else "active",
            current_task_id=session.current_task_id,
            active_bundle_id=session.active_bundle_id,
            metadata={**session.metadata, "operator_control_state": state},
            created_at=session.created_at,
            updated_at=applied_at,
        )
        stored = await self._runtime.compare_and_swap_session(
            session,
            replacement,
            atomic_receipt=receipt,
        )
        if stored is not None:
            return _application_from_receipt(receipt)
        raced = await self._runtime.get_runtime_receipt(receipt_id)
        if raced is not None:
            return _application_from_receipt(raced)
        return CampaignOperatorApplication(
            request_id=request_id,
            idempotency_key=idempotency_key,
            envelope_sha256=source_envelope_sha256,
            status="deferred",
        )

    async def _require_session(self) -> SessionState:
        session = await self._runtime.get_session(self._session_id)
        if session is None:
            raise MissionControlError("campaign has not been started")
        if (
            session.metadata.get("mission_id") != self._mission_id
            or session.metadata.get("config_digest") != self._config_digest
        ):
            raise MissionControlError("campaign session has a foreign identity")
        return session


def _request_identity(request: OperatorControlRequestLike) -> tuple[str, str, str]:
    request_id = getattr(request, "request_id", None)
    idempotency_key = getattr(request, "idempotency_key", None)
    action_value = getattr(getattr(request, "action", None), "value", None)
    if action_value is None:
        action_value = getattr(request, "action", None)
    if (
        not isinstance(request_id, str)
        or not _IDENTIFIER_RE.fullmatch(request_id)
        or not isinstance(idempotency_key, str)
        or not _IDENTIFIER_RE.fullmatch(idempotency_key)
        or not isinstance(action_value, str)
    ):
        raise MissionControlError("operator control identity is invalid")
    return request_id, idempotency_key, action_value


def _validate_private_carrier(operator_login: str, envelope_sha256: str) -> None:
    if not isinstance(operator_login, str) or not _LOGIN_RE.fullmatch(operator_login):
        raise MissionControlError("operator login is invalid")
    if not isinstance(envelope_sha256, str) or not _SHA256_RE.fullmatch(
        envelope_sha256
    ):
        raise MissionControlError("operator envelope digest is invalid")


def _session_control_state(session: SessionState) -> dict[str, Any]:
    generation = session.metadata.get("generation")
    if isinstance(generation, bool) or not isinstance(generation, int) or generation < 1:
        raise MissionControlError("campaign session generation is invalid")
    raw = session.metadata.get("operator_control_state")
    if raw is None:
        if session.status not in {"active", "stopped"}:
            raise MissionControlError("campaign session lacks its control-state binding")
        state = initial_operator_control_state(generation)
    else:
        try:
            state = validate_operator_control_state(raw, expected_generation=generation)
        except ValueError as exc:
            raise MissionControlError("campaign operator control state is invalid") from exc
    expected = {"active": "RUNNING", "paused": "PAUSED"}.get(session.status)
    if session.status not in {"active", "paused", "stopped"} or (
        expected is not None and state["control_state"] != expected
    ):
        raise MissionControlError("campaign status and operator control state conflict")
    return state


def _rejection_reason(
    request: OperatorControlRequestLike,
    *,
    action: str,
    session: SessionState,
    now: datetime,
) -> str:
    if action not in {"pause", "resume"}:
        return "action_not_admitted"
    if session.status == "stopped" or session.metadata.get("stop_requested") is True:
        return "campaign_stopped_terminal"
    try:
        request.validate_time_window(now=now)
    except Exception as exc:
        return f"time_window_{type(exc).__name__}"
    return ""


def _receipt_id(mission_id: str, idempotency_key: str) -> str:
    return stable_id("mission_campaign_operator_control", mission_id, idempotency_key)


def _control_receipt(
    *,
    mission_id: str,
    config_digest: str,
    session: SessionState,
    request: OperatorControlRequestLike,
    request_id: str,
    idempotency_key: str,
    action: str,
    operator_login: str,
    source_envelope_sha256: str,
    prior_control_state: str,
    next_control_state: str,
    transition_sequence: int,
    application_status: str,
    rejection_reason: str,
    now: datetime,
) -> RuntimeReceipt:
    generation = session.metadata["generation"]
    return RuntimeReceipt(
        receipt_id=_receipt_id(mission_id, idempotency_key),
        receipt_type=OPERATOR_CONTROL_RECEIPT_TYPE,
        status=application_status,
        run_id=stable_id("mission_campaign_run", mission_id, str(generation)),
        correlation_id=session.session_id,
        agent_id="mission-control-supervisor",
        idempotency_key=idempotency_key,
        side_effect_key=f"mission_campaign_operator_control:{idempotency_key}",
        payload={
            "schema_version": OPERATOR_CONTROL_RECEIPT_SCHEMA,
            "campaign_schema_version": session.metadata["schema_version"],
            "mission_id": mission_id,
            "config_digest": config_digest,
            "campaign_generation": generation,
            "transition_sequence": transition_sequence,
            "request_id": request_id,
            "idempotency_key": idempotency_key,
            "action": action,
            "issued_at": getattr(request, "issued_at", ""),
            "expires_at": getattr(request, "expires_at", ""),
            "reason": getattr(request, "reason", ""),
            "operator_login": operator_login,
            "source_envelope_sha256": source_envelope_sha256,
            "prior_control_state": prior_control_state,
            "next_control_state": next_control_state,
            "application_status": application_status,
            "rejection_reason": rejection_reason,
            "authority_applied_at": canonical_utc_timestamp(now),
            "preserves_queued_work": True,
            "external_effect_performed": False,
        },
        created_at=now,
    )


def _application_from_receipt(receipt: RuntimeReceipt) -> CampaignOperatorApplication:
    payload = receipt.payload
    expected_fields = {
        "schema_version",
        "campaign_schema_version",
        "mission_id",
        "config_digest",
        "campaign_generation",
        "transition_sequence",
        "request_id",
        "idempotency_key",
        "action",
        "issued_at",
        "expires_at",
        "reason",
        "operator_login",
        "source_envelope_sha256",
        "prior_control_state",
        "next_control_state",
        "application_status",
        "rejection_reason",
        "authority_applied_at",
        "preserves_queued_work",
        "external_effect_performed",
    }
    status = payload.get("application_status")
    if (
        receipt.receipt_type != OPERATOR_CONTROL_RECEIPT_TYPE
        or set(payload) != expected_fields
        or status not in {"applied", "rejected"}
        or receipt.status != status
        or payload.get("schema_version") != OPERATOR_CONTROL_RECEIPT_SCHEMA
        or receipt.idempotency_key != payload.get("idempotency_key")
        or receipt.side_effect_key
        != f"mission_campaign_operator_control:{receipt.idempotency_key}"
        or receipt.receipt_id
        != _receipt_id(str(payload.get("mission_id")), receipt.idempotency_key)
        or payload.get("authority_applied_at")
        != canonical_utc_timestamp(receipt.created_at)
        or payload.get("preserves_queued_work") is not True
        or payload.get("external_effect_performed") is not False
    ):
        raise MissionControlError("operator control receipt is invalid")
    return CampaignOperatorApplication(
        request_id=str(payload["request_id"]),
        idempotency_key=str(payload["idempotency_key"]),
        envelope_sha256=str(payload["source_envelope_sha256"]),
        status=str(status),
        authority_receipt_ref=OPERATOR_CONTROL_RECEIPT_REF_PREFIX + receipt.receipt_id,
        authority_receipt_sha256=runtime_receipt_content_digest(receipt),
    )


__all__ = [
    "CampaignOperatorApplication",
    "CampaignOperatorAuthority",
    "OperatorControlRequestLike",
]
