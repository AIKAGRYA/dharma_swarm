"""Read-only Helm context transport for the terminal bridge.

The terminal process owns the request boundary.  A client may report the six
bounded UI coordinates, but it cannot submit an envelope, authority stamp,
runtime epoch, or owner projection.  Those values are constructed here from
the bridge and injected canonical owners.
"""

from __future__ import annotations

import asyncio
from collections.abc import Mapping
from dataclasses import replace
from datetime import datetime, timedelta, timezone
import re
import subprocess
from typing import Any
import unicodedata
from urllib.parse import urlsplit

from dharma_swarm.operator_core.helm_context import HelmContextError, format_rfc3339, looks_like_secret
from dharma_swarm.operator_core.helm_context_projection import (
    HelmContextSources,
    HelmUIState,
    _issue_helm_bridge_snapshot,
    build_helm_context,
    run_bounded_sync,
)

_REQUEST_KEYS = frozenset({"id", "type", "ui"})
_UI_KEYS = frozenset(
    {
        "face",
        "place",
        "facet",
        "overlay",
        "keyboard_focus",
        "available_navigation",
    }
)
_REQUEST_ID_MAX_CHARS = 128
_REQUEST_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:@/-]{0,127}$")
_FACE_VALUES = frozenset({"zen", "cockpit", "scroll"})
_PLACE_VALUES = frozenset({"home", "conversation", "activity", "evidence", "system"})
_FACET_VALUES = frozenset(
    {
        "chat",
        "commands",
        "agents",
        "models",
        "evolution",
        "thinking",
        "tools",
        "timeline",
        "sessions",
        "approvals",
        "mission",
        "runtime",
        "repo",
        "ontology",
        "control",
    }
)
_OVERLAY_VALUES = frozenset({"none", "modelPicker", "paneSwitcher", "tour"})
_KEYBOARD_FOCUS_VALUES = frozenset({"composer", "navigation"})
_CANONICAL_NAVIGATION = ("home", "conversation", "activity", "evidence", "system")
_REPOSITORY_IDENTITY = re.compile(r"^[A-Za-z0-9._-]+(?:/[A-Za-z0-9._-]+){1,3}$")
_REMOTE_HOST = re.compile(r"^[A-Za-z0-9.-]+$")
_PROVEN_NONSYNTHETIC_REASONS = frozenset({
    "requested_identity_missing", "served_identity_missing", "served_identity_mismatch",
    "timestamp_not_timezone_aware", "timestamp_in_future", "expiry_not_after_observation",
    "ttl_exceeds_24_hours", "evidence_expired", "verifier_identity_rejected",
    "verifier_decision_rejected", "receipt_reference_missing", "receipt_hash_invalid",
    "receipt_duplicated", "receipt_replayed", "verified",
})


def _route_identity_now() -> datetime:
    """Return the observation time used to re-check cached route evidence."""

    return datetime.now(timezone.utc)


def _safe_origin_identity(repo_root: object) -> tuple[str | None, str]:
    """Read Git's owner-issued origin while discarding credentials and metadata."""

    fallback = getattr(repo_root, "name", "") or "workspace"
    try:
        result = subprocess.run(
            ["git", "--no-optional-locks", "-C", str(repo_root), "config", "--get", "remote.origin.url"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None, fallback
    if result.returncode != 0:
        return None, fallback
    raw = result.stdout.strip()
    if not raw or any(unicodedata.category(character) in {"Cc", "Cf"} for character in raw):
        return None, fallback
    host = ""
    path = ""
    if "://" in raw:
        parsed = urlsplit(raw)
        host = parsed.hostname or ""
        path = parsed.path.lstrip("/")
    else:
        match = re.fullmatch(r"(?:[^@/\s]+@)?([^:/\s]+):([^\s?#]+)", raw)
        if match:
            host, path = match.groups()
    path = path.removesuffix(".git").strip("/")
    recognized = bool(
        host
        and _REMOTE_HOST.fullmatch(host)
        and _REPOSITORY_IDENTITY.fullmatch(path)
        and all(segment not in {".", ".."} for segment in path.split("/"))
    )
    repository = path if recognized else fallback
    remote = f"{host}/{path}" if recognized else None
    if remote is not None and looks_like_secret(remote):
        return None, fallback
    return remote, repository


class _HelmContextRequestError(ValueError):
    """A bounded error whose text is safe to return over the bridge."""


def _validated_request_id(value: object) -> str:
    if not isinstance(value, str):
        raise _HelmContextRequestError("request id must be a string")
    if not value or value != value.strip() or len(value) > _REQUEST_ID_MAX_CHARS:
        raise _HelmContextRequestError("request id is missing or out of bounds")
    if _REQUEST_ID.fullmatch(value) is None:
        raise _HelmContextRequestError("request id contains unsupported characters")
    if looks_like_secret(value):
        raise _HelmContextRequestError("request id contains protected content")
    return value


def _required_enum(ui: Mapping[str, object], key: str, allowed: frozenset[str]) -> str:
    value = ui.get(key)
    if not isinstance(value, str) or value not in allowed:
        raise _HelmContextRequestError(f"ui.{key} is invalid")
    return value


def _required_face(ui: Mapping[str, object]) -> str:
    value = ui.get("face")
    if isinstance(value, str) and (
        value in _FACE_VALUES
        or value.startswith("deck-focus:") and value.removeprefix("deck-focus:") in _FACET_VALUES
    ):
        return value
    raise _HelmContextRequestError("ui.face is invalid")


def _validated_ui(request: Mapping[str, object]) -> HelmUIState:
    if set(request) != _REQUEST_KEYS:
        raise _HelmContextRequestError("helm context request contains unsupported fields")
    if request.get("type") != "helm.context.request":
        raise _HelmContextRequestError("helm context request type is invalid")
    raw_ui = request.get("ui")
    if not isinstance(raw_ui, Mapping) or set(raw_ui) != _UI_KEYS:
        raise _HelmContextRequestError("ui must contain exactly the six Helm coordinates")

    navigation = raw_ui.get("available_navigation")
    if not isinstance(navigation, list) or tuple(navigation) != _CANONICAL_NAVIGATION:
        raise _HelmContextRequestError("ui.available_navigation is invalid")

    return HelmUIState(
        face=_required_face(raw_ui),
        place=_required_enum(raw_ui, "place", _PLACE_VALUES),
        facet=_required_enum(raw_ui, "facet", _FACET_VALUES),
        overlay=_required_enum(raw_ui, "overlay", _OVERLAY_VALUES),
        keyboard_focus=_required_enum(raw_ui, "keyboard_focus", _KEYBOARD_FOCUS_VALUES),
        available_navigation=_CANONICAL_NAVIGATION,
    )


class TerminalBridgeHelmContextMixin:
    """Build and emit one owner-projected, side-effect-free context envelope."""

    def _initialize_helm_context(self, *, helm_context_sources: object | None) -> None:
        if helm_context_sources is not None and not isinstance(
            helm_context_sources,
            HelmContextSources,
        ):
            raise TypeError("helm_context_sources must be HelmContextSources or None")
        self._helm_context_injected_sources = helm_context_sources

    async def _current_helm_context_sources(
        self,
        *,
        now: datetime | None = None,
    ) -> HelmContextSources:
        injected = self._helm_context_injected_sources or HelmContextSources()
        git_summary, repository_identity = await asyncio.gather(
            run_bounded_sync(self._build_git_summary),
            run_bounded_sync(_safe_origin_identity, self._repo_root),
        )
        remote, canonical_repository = repository_identity
        workspace_state = {
            "workspace_path": str(self._repo_root),
            "workspace": self._repo_root.name,
            "repository": self._package_root.name,
            "repository_identity": canonical_repository,
            "remote": remote,
            "branch": git_summary.get("branch"),
            "head": git_summary.get("head"),
            "upstream": git_summary.get("upstream"),
            "ahead": git_summary.get("ahead"),
            "behind": git_summary.get("behind"),
            "staged": git_summary.get("staged"),
            "unstaged": git_summary.get("unstaged"),
            "untracked": git_summary.get("untracked"),
        }

        served_identity = self._current_response_owned_identity(now=now)
        bridge_session_data = {
            "bridge_status": "connected",
            "active_session_id": self._active_session_id,
            "active_phase": self._active_run.phase if self._active_run else None,
            "requested_provider_id": self._selected_provider_id,
            "requested_model_id": self._selected_model_id,
            **served_identity,
        }
        route_proof = None
        if served_identity["route_exact_model_proven"] is True:
            route_proof = next(
                (
                    row for row in self._helm_on_call_projection.seats
                    if row.seat_id == served_identity["route_seat_id"]
                    and row.runtime_epoch == self._runtime_owner_id
                ),
                None,
            )
        canonical_requested_provider = self._canonical_route_provider(
            self._selected_provider_id or "",
        )
        bridge_session_state = _issue_helm_bridge_snapshot(
            "bridge_session", bridge_session_data,
            route_proof,
            canonical_requested_provider,
        )
        return replace(
            injected,
            workspace_state=_issue_helm_bridge_snapshot("workspace", workspace_state),
            bridge_session_state=bridge_session_state,
            session_store=self._session_store,
        )

    def _current_response_owned_identity(
        self,
        *,
        now: datetime | None = None,
    ) -> dict[str, object]:
        """Return served identity only through the Python route evaluator."""

        observed_now = now or _route_identity_now()
        if observed_now.tzinfo is None or observed_now.utcoffset() is None:
            raise ValueError("route identity observation time must be timezone-aware")
        observed_now = observed_now.astimezone(timezone.utc)
        unavailable: dict[str, object] = {
            "served_provider_id": None,
            "served_model_id": None,
            "served_identity_source": "unavailable",
            "served_identity_observed_at": None,
            "route_evidence_expires_at": None,
            "route_evidence_freshness": "unavailable",
            "route_receipt_ref": None,
            "route_receipt_sha256": None,
            "route_verifier_id": None,
            "route_verifier_version": None,
            "route_evidence_synthetic": None,
            "route_verdict": "UNKNOWN",
            "route_verdict_reason": "route_not_evaluated",
            "route_exact_model_proven": False,
            "route_seat_id": None,
            "route_verification_evaluated_at": None,
        }
        projection = self._helm_on_call_projection
        if getattr(projection, "runtime_epoch", None) != self._runtime_owner_id:
            unavailable["route_verdict_reason"] = "route_projection_epoch_mismatch"
            return unavailable

        selected_provider = self._selected_provider_id
        selected_model = self._selected_model_id
        canonical_provider = (
            self._canonical_route_provider(selected_provider or "") or selected_provider
        )
        seat = self._helm_seat_for_route(canonical_provider or "", selected_model or "")
        if seat is None:
            unavailable["route_verdict_reason"] = "selected_route_has_no_helm_seat"
            return unavailable
        verification = next(
            (
                row
                for row in projection.seats
                if row.seat_id == seat.seat_id
                and row.runtime_epoch == self._runtime_owner_id
            ),
            None,
        )
        if verification is None:
            unavailable["route_verdict_reason"] = "route_verification_unavailable"
            return unavailable

        verdict = getattr(verification.verdict, "value", str(verification.verdict))
        evaluated_at = verification.evaluated_at
        if (
            not isinstance(evaluated_at, datetime)
            or evaluated_at.tzinfo is None
            or evaluated_at.utcoffset() is None
        ):
            unavailable["route_verdict_reason"] = "route_evaluation_timestamp_invalid"
            return unavailable
        evaluated_at = evaluated_at.astimezone(timezone.utc)
        if evaluated_at > observed_now:
            unavailable["route_verdict_reason"] = "route_evaluation_timestamp_in_future"
            return unavailable
        unavailable.update(
            {
                "route_verdict": verdict,
                "route_verdict_reason": verification.reason,
                "route_seat_id": verification.seat_id,
                "route_verification_evaluated_at": format_rfc3339(evaluated_at),
            }
        )
        evidence = verification.evidence
        if evidence is None:
            return unavailable
        if evidence.runtime_epoch != self._runtime_owner_id:
            unavailable.update(
                {
                    "route_verdict": "UNKNOWN",
                    "route_verdict_reason": "route_evidence_epoch_mismatch",
                }
            )
            return unavailable
        if (
            evidence.requested_provider != canonical_provider
            or evidence.requested_model != selected_model
        ):
            unavailable.update(
                {
                    "route_evidence_freshness": "selected_route_mismatch",
                    "route_verdict": "UNKNOWN",
                    "route_verdict_reason": "selected_route_mismatch",
                }
            )
            return unavailable
        if not evidence.served_provider or not evidence.served_model:
            return unavailable

        observed_at = evidence.observed_at
        if (
            not isinstance(observed_at, datetime)
            or observed_at.tzinfo is None
            or observed_at.utcoffset() is None
        ):
            unavailable.update(
                {
                    "route_evidence_freshness": "invalid",
                    "route_verdict": "UNKNOWN",
                    "route_verdict_reason": "route_evidence_observation_invalid",
                }
            )
            return unavailable

        expires_at = evidence.expires_at
        if (
            not isinstance(expires_at, datetime)
            or expires_at.tzinfo is None
            or expires_at.utcoffset() is None
        ):
            unavailable.update(
                {
                    "route_evidence_freshness": "invalid",
                    "route_verdict": "UNKNOWN",
                    "route_verdict_reason": "route_evidence_expiry_invalid",
                }
            )
            return unavailable
        observed_at = observed_at.astimezone(timezone.utc)
        expires_at = expires_at.astimezone(timezone.utc)
        if observed_at > observed_now or observed_at > evaluated_at:
            unavailable.update(
                {
                    "route_evidence_freshness": "invalid",
                    "route_verdict": "UNKNOWN",
                    "route_verdict_reason": "route_evidence_observation_in_future",
                }
            )
            return unavailable
        if expires_at <= observed_at or expires_at - observed_at > timedelta(hours=24):
            unavailable.update(
                {
                    "route_evidence_freshness": "invalid",
                    "route_verdict": "UNKNOWN",
                    "route_verdict_reason": "route_evidence_expiry_invalid",
                }
            )
            return unavailable

        unavailable.update(
            {
                "served_provider_id": evidence.served_provider,
                "served_model_id": evidence.served_model,
                "served_identity_source": "provider_response_via_route_evaluator",
                "served_identity_observed_at": format_rfc3339(observed_at),
                "route_evidence_expires_at": format_rfc3339(expires_at),
                "route_receipt_ref": evidence.receipt_ref,
                "route_receipt_sha256": evidence.receipt_sha256,
                "route_verifier_id": evidence.verifier_id,
                "route_verifier_version": evidence.verifier_version,
                "route_evidence_synthetic": (
                    False if verification.reason in _PROVEN_NONSYNTHETIC_REASONS
                    else True if verification.reason == "synthetic_evidence"
                    else None
                ),
            }
        )
        if observed_now >= expires_at.astimezone(timezone.utc):
            unavailable.update(
                {
                    "route_evidence_freshness": "expired",
                    "route_verdict": "UNKNOWN",
                    "route_verdict_reason": "cached_route_evidence_expired",
                }
            )
            return unavailable

        unavailable.update(
            {
                "route_evidence_freshness": "fresh",
                "route_exact_model_proven": verdict == "ON_CALL",
            }
        )
        return unavailable

    async def _handle_helm_context_request(
        self,
        request_id: str,
        request: dict[str, Any],
    ) -> None:
        safe_request_id = ""
        try:
            correlated_id = _validated_request_id(request.get("id"))
            if correlated_id != request_id:
                raise _HelmContextRequestError("request id correlation is invalid")
            safe_request_id = correlated_id
            ui = _validated_ui(request)
        except (_HelmContextRequestError, HelmContextError) as exc:
            self._emit(
                {
                    "type": "bridge.error",
                    "request_id": safe_request_id,
                    "code": "invalid_helm_context_request",
                    "message": str(exc),
                }
            )
            return

        try:
            loop = asyncio.get_running_loop()
            started = loop.time()
            observed_now = _route_identity_now()
            sources = await self._current_helm_context_sources(now=observed_now)
            build_now = observed_now + timedelta(seconds=loop.time() - started)
            envelope = await build_helm_context(
                sources,
                ui=ui,
                runtime_epoch=self._runtime_owner_id,
                now=build_now,
                advance_clock=True,
            )
        except Exception:
            self._emit(
                {
                    "type": "bridge.error",
                    "request_id": request_id,
                    "code": "helm_context_unavailable",
                    "message": "the bounded Helm context could not be projected",
                }
            )
            return

        self._emit(
            {
                "type": "helm.context.result",
                "request_id": correlated_id,
                "envelope": envelope.to_dict(),
            }
        )
