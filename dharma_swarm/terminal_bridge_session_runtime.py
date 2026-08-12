"""Session launch and provider-stream execution for the terminal bridge."""

from __future__ import annotations

import asyncio
from dataclasses import asdict, dataclass, replace
from datetime import datetime, timezone
import hashlib
import json
import os
import stat
from typing import Any

from dharma_swarm import model_status
from dharma_swarm.operator_core.session_lifecycle import SessionLifecycleRecorder
from dharma_swarm.terminal_bridge_session_types import _ActiveSessionRun
from dharma_swarm.tui import model_routing
from dharma_swarm.tui.engine.events import (
    CanonicalEventType,
    EVENT_TYPES,
    SCHEMA_VERSION,
    SessionEnd,
    SessionStart,
    TextComplete,
    UserPrompt,
)

_NARRATION_EVENT_TYPES = frozenset(
    {"text_delta", "text_complete", "thinking_delta", "thinking_complete"}
)
_COMMAND_OUTCOMES = frozenset({"completed", "accepted", "unsupported", "failed"})
_ROUTE_PROVIDER_IDS = {
    "claude": "claude_code",
    "openrouter": "openrouter",
}
_FORBIDDEN_ROUTE_RECEIPT_EVENT_PREFIXES = (
    "command.",
    "command_",
    "permission.",
    "permission_",
    "task.",
    "task_",
    "tool.",
    "tool_",
)


@dataclass(frozen=True, slots=True)
class _DurableRouteEvidenceSource:
    """Server-owned inputs required to reproduce one route-evidence row."""

    session_id: str
    requested_provider_id: str
    requested_model_id: str
    expected_prompt: str
    terminal_timestamp: float
    adapter: object
    receipt_ref: str | None = None
    receipt_sha256: str | None = None


def _reject_duplicate_json_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    decoded: dict[str, Any] = {}
    for key, value in pairs:
        if key in decoded:
            raise ValueError(f"duplicate JSON key: {key}")
        decoded[key] = value
    return decoded


def _reject_non_finite_json_constant(value: str) -> None:
    raise ValueError(f"non-finite JSON constant: {value}")


class TerminalBridgeSessionRuntimeMixin:
    """Own session admission, lifecycle recording, and provider streaming."""

    def _launch_session_start(
        self,
        request_id: str,
        request: dict[str, Any],
    ) -> asyncio.Task[None] | None:
        active = self._active_run
        if active is not None:
            self._emit(
                {
                    "type": "bridge.error",
                    "request_id": request_id,
                    "code": "session_busy",
                    "message": f"session request {active.request_id or '<missing>'} is still active",
                    "active_request_id": active.request_id,
                    "active_session_id": active.session_id,
                    "active_provider": active.provider_id,
                    "active_phase": active.phase,
                }
            )
            return None
        if self._closing:
            self._emit(
                {
                    "type": "bridge.error",
                    "request_id": request_id,
                    "code": "bridge_closing",
                    "message": "the bridge is closing and cannot start a session",
                }
            )
            return None
        if self._adapter_boot_error is not None or self._completion_request_cls is None:
            self._emit(
                {
                    "type": "bridge.error",
                    "request_id": request_id,
                    "code": "adapter_boot_failed",
                    "message": self._adapter_boot_error or "adapter runtime unavailable",
                }
            )
            return None
        prompt, error_code, error_message = self._validated_request_prompt(request)
        if prompt is None:
            self._emit(
                {
                    "type": "bridge.error",
                    "request_id": request_id,
                    "code": error_code,
                    "message": error_message,
                }
            )
            return None

        owned_request = dict(request)
        canonical_intent = self._resolve_prompt_intent(prompt)
        supplied_bootstrap = request.get("bootstrap")
        bootstrap = dict(supplied_bootstrap) if isinstance(supplied_bootstrap, dict) else {}
        bootstrap["intent"] = canonical_intent
        owned_request["bootstrap"] = bootstrap
        default_target = model_routing.default_target()
        provider_id = str(request.get("provider", "") or default_target.provider_id).strip().lower()
        model_id = str(request.get("model", "") or "").strip()
        adapter = self._adapters.get(provider_id)
        if not model_id and adapter is not None:
            model_id = str(adapter.get_profile(None).model_id)
        if not model_id:
            model_id = default_target.model_id
        if str(canonical_intent.get("kind", "chat")) == "chat":
            lanes = self._chat_lanes(provider_id, model_id)
            if lanes:
                provider_id, model_id, _, _ = lanes[0]
        adapter = self._adapters.get(provider_id)
        if adapter is None:
            self._emit(
                {
                    "type": "bridge.error",
                    "request_id": request_id,
                    "code": "unknown_provider",
                    "message": provider_id,
                }
            )
            return None
        owned_request["provider"] = provider_id
        owned_request["model"] = model_id
        try:
            lifecycle = SessionLifecycleRecorder.begin(
                self._session_store,
                provider_id=provider_id,
                model_id=model_id,
                cwd=str(self._repo_root),
                prompt=prompt,
                runtime_owner_id=self._runtime_owner_id,
                runtime_owner_pid=self._runtime_owner_pid,
            )
        except Exception as exc:
            self._emit(
                {
                    "type": "bridge.error",
                    "request_id": request_id,
                    "code": "session_persistence_failed",
                    "message": f"{type(exc).__name__}: {exc}",
                }
            )
            return None
        session_id = lifecycle.session_id
        owned_request["session_id"] = session_id
        run = _ActiveSessionRun(
            request_id=request_id,
            session_id=session_id,
            provider_id=provider_id,
            model_id=model_id,
            lifecycle=lifecycle,
        )
        self._set_active_run(run)
        task = asyncio.create_task(
            self._run_active_session(run, owned_request),
            name=f"terminal-session:{request_id or session_id}",
        )
        run.task = task
        return task

    async def _handle_session_start(self, request_id: str, request: dict[str, Any]) -> None:
        """Compatibility entry point that waits for a launched session turn."""

        task = self._launch_session_start(request_id, request)
        if task is not None:
            await task

    def _emit_recorded_session_event(
        self,
        run: _ActiveSessionRun,
        event: CanonicalEventType,
        *,
        extra: dict[str, Any] | None = None,
    ) -> None:
        payload = asdict(event)
        payload["request_id"] = run.request_id
        if event.type in _NARRATION_EVENT_TYPES:
            payload.update(
                {
                    "authority": "NONE",
                    "narration_verified": False,
                    "state_promotion_allowed": False,
                }
            )
        if extra:
            payload.update(extra)
        if isinstance(event, SessionEnd):
            self._mark_terminal_emitted(run)
        self._emit(payload)

    def _record_and_emit_session_event(
        self,
        run: _ActiveSessionRun,
        event: CanonicalEventType,
    ) -> CanonicalEventType | None:
        accepted = run.lifecycle.record(event)
        if accepted is None:
            return None
        if isinstance(accepted, SessionStart):
            self._set_active_provider(
                run,
                run.lifecycle.provider_id,
                run.lifecycle.model_id,
            )
        self._emit_recorded_session_event(run, accepted)
        return accepted

    def _emit_provider_route_receipt(
        self,
        run: _ActiveSessionRun,
        terminal: SessionEnd,
        *,
        requested_provider_id: str,
        requested_model_id: str,
        expected_prompt: str,
        adapter: object,
    ) -> None:
        """Emit a diagnostic receipt, then evaluate independently owned truth.

        ``session_end`` is also used by local identity, memory, and command
        paths, so it cannot itself prove that a model route executed.  This
        method is called only by the sealed adapter-stream loop.  The legacy
        receipt remains diagnostic; only the Python RouteVerification
        projection below can promote a Helm seat.
        """

        if not terminal.success:
            return
        provider_id = run.lifecycle.provider_id
        model_id = run.lifecycle.model_id
        self._emit(
            {
                "type": "route.receipt",
                "request_id": run.request_id,
                "session_id": run.session_id,
                "provider_id": provider_id,
                "model_id": model_id,
                "route_id": f"{provider_id}:{model_id}",
                "evidence_kind": "provider_completion",
                "success": True,
            }
        )
        try:
            terminal_timestamp = float(terminal.timestamp)
        except (TypeError, ValueError):
            terminal_timestamp = float("nan")
        source = _DurableRouteEvidenceSource(
            session_id=run.session_id,
            requested_provider_id=requested_provider_id,
            requested_model_id=requested_model_id,
            expected_prompt=expected_prompt,
            terminal_timestamp=terminal_timestamp,
            adapter=adapter,
        )
        evidence = self._route_evidence_from_durable_session(source)
        if (
            evidence is not None
            and evidence.seat_id is not None
            and evidence.receipt_ref is not None
            and evidence.receipt_sha256 is not None
        ):
            self._helm_route_sources_by_seat[evidence.seat_id] = replace(
                source,
                receipt_ref=evidence.receipt_ref,
                receipt_sha256=evidence.receipt_sha256,
            )
            self._helm_route_evidence_by_seat[evidence.seat_id] = evidence
        self._emit_helm_on_call_projection(run.request_id)

    @staticmethod
    def _canonical_route_provider(provider_id: str) -> str | None:
        return _ROUTE_PROVIDER_IDS.get(str(provider_id or "").strip().lower())

    @staticmethod
    def _helm_seat_for_route(
        provider_id: str,
        model_id: str,
    ) -> model_status.HelmSeat | None:
        identity = (provider_id, model_id)
        return next(
            (
                seat
                for seat in model_status.HELM_SLICE1_SEATS
                if identity in seat.admissible_served_identities
            ),
            None,
        )

    def _read_durable_transcript(
        self,
        session_id: str,
    ) -> tuple[bytes | None, str | None, str | None]:
        """Read and hash one root-confined regular transcript from one file handle."""

        if (
            not session_id
            or session_id in {".", ".."}
            or "/" in session_id
            or "\\" in session_id
        ):
            return None, None, None
        try:
            store_root = self._session_store.root.resolve()
            session_path = store_root / session_id
            if session_path.is_symlink():
                return None, None, None
            session_dir = session_path.resolve(strict=True)
            transcript_path = session_dir / "transcript.jsonl"
            if transcript_path.is_symlink():
                return None, None, None
            resolved_transcript = transcript_path.resolve(strict=True)
        except OSError:
            return None, None, None
        if (
            session_dir.parent != store_root
            or session_dir.name != session_id
            or resolved_transcript.parent != session_dir
        ):
            return None, None, None

        descriptor = -1
        try:
            flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
            descriptor = os.open(transcript_path, flags)
            before = os.fstat(descriptor)
            if not stat.S_ISREG(before.st_mode):
                return None, None, None
            chunks: list[bytes] = []
            while True:
                chunk = os.read(descriptor, 1024 * 1024)
                if not chunk:
                    break
                chunks.append(chunk)
            after = os.fstat(descriptor)
        except OSError:
            return None, None, None
        finally:
            if descriptor >= 0:
                os.close(descriptor)
        identity_before = (
            before.st_dev,
            before.st_ino,
            before.st_size,
            before.st_mtime_ns,
        )
        identity_after = (
            after.st_dev,
            after.st_ino,
            after.st_size,
            after.st_mtime_ns,
        )
        transcript_bytes = b"".join(chunks)
        if identity_before != identity_after or len(transcript_bytes) != after.st_size:
            return None, None, None
        try:
            if transcript_path.is_symlink() or transcript_path.resolve(strict=True) != resolved_transcript:
                return None, None, None
        except OSError:
            return None, None, None
        return (
            transcript_bytes,
            str(resolved_transcript),
            hashlib.sha256(transcript_bytes).hexdigest(),
        )

    @staticmethod
    def _strict_transcript_from_bytes(
        transcript_bytes: bytes,
        *,
        session_id: str,
    ) -> list[CanonicalEventType] | None:
        """Decode every persisted byte; malformed or skipped rows reject the receipt."""

        if not transcript_bytes or not transcript_bytes.endswith(b"\n"):
            return None
        try:
            decoded = transcript_bytes.decode("utf-8", errors="strict")
        except UnicodeDecodeError:
            return None

        transcript: list[CanonicalEventType] = []
        for raw_line in decoded.splitlines():
            if not raw_line.strip():
                return None
            try:
                payload = json.loads(
                    raw_line,
                    object_pairs_hook=_reject_duplicate_json_keys,
                    parse_constant=_reject_non_finite_json_constant,
                )
            except (TypeError, ValueError, json.JSONDecodeError):
                return None
            if not isinstance(payload, dict):
                return None
            event_type = payload.get("type")
            if not isinstance(event_type, str):
                return None
            event_cls = EVENT_TYPES.get(event_type)
            if event_cls is None:
                return None
            try:
                event = event_cls(**payload)
            except (TypeError, ValueError):
                return None
            if (
                event.schema_version != SCHEMA_VERSION
                or event.session_id != session_id
                or event.raw is not None
                or asdict(event) != payload
            ):
                return None
            transcript.append(event)
        return transcript

    def _route_evidence_from_durable_session(
        self,
        source: _DurableRouteEvidenceSource,
    ) -> model_status.RouteEvidence | None:
        requested_provider = self._canonical_route_provider(source.requested_provider_id)
        if requested_provider is None:
            return None
        seat = self._helm_seat_for_route(requested_provider, source.requested_model_id)
        if seat is None:
            return None

        first_read = self._read_durable_transcript(source.session_id)
        try:
            replay_ok, replay_issues = self._session_store.verify_session_replay(
                source.session_id
            )
        except Exception:
            replay_ok, replay_issues = False, ["session_replay_verifier_failed"]
        second_read = self._read_durable_transcript(source.session_id)
        transcript_stable = first_read == second_read
        transcript_bytes, receipt_ref, receipt_sha256 = second_read
        transcript = (
            self._strict_transcript_from_bytes(
                transcript_bytes,
                session_id=source.session_id,
            )
            if transcript_bytes is not None
            else None
        )
        receipt_identity_ok = (
            source.receipt_ref is None
            and source.receipt_sha256 is None
            or source.receipt_ref == receipt_ref
            and source.receipt_sha256 == receipt_sha256
        )
        decoded_transcript = transcript or []

        starts = [event for event in decoded_transcript if isinstance(event, SessionStart)]
        prompts = [event for event in decoded_transcript if isinstance(event, UserPrompt)]
        replies = [
            event
            for event in decoded_transcript
            if isinstance(event, TextComplete)
            and event.role == "assistant"
            and bool(event.content.strip())
        ]
        terminals = [event for event in decoded_transcript if isinstance(event, SessionEnd)]
        start = starts[0] if len(starts) == 1 else None
        durable_terminal = terminals[0] if len(terminals) == 1 else None
        start_positions = [
            index
            for index, event in enumerate(decoded_transcript)
            if isinstance(event, SessionStart)
        ]
        terminal_positions = [
            index
            for index, event in enumerate(decoded_transcript)
            if isinstance(event, SessionEnd)
        ]
        canonical_event_order = (
            len(prompts) == 1
            and bool(decoded_transcript)
            and isinstance(decoded_transcript[0], UserPrompt)
            and start_positions == [1]
            and terminal_positions == [len(decoded_transcript) - 1]
        )
        served_provider = (
            self._canonical_route_provider(start.provider_id) if start is not None else None
        )
        served_model = str(start.model or "").strip() or None if start is not None else None

        forbidden_event = any(
            str(event.type or "").lower().startswith(
                _FORBIDDEN_ROUTE_RECEIPT_EVENT_PREFIXES
            )
            for event in decoded_transcript
        )
        adapter_event_providers_ok = all(
            event.provider_id == source.requested_provider_id
            for event in decoded_transcript[1:]
        )
        transport_provenance_ok = self._is_server_owned_chat_transport(
            source.requested_provider_id,
            source.adapter,
        )
        provider_provenance_ok = False
        if start is not None and source.requested_provider_id == "claude":
            provider_provenance_ok = (
                start.provider_id == "claude"
                and start.system_info.get("permission_mode") == "plan"
                and not start.system_info.get("mcp_servers")
            )
        elif start is not None and source.requested_provider_id == "openrouter":
            provider_provenance_ok = (
                start.provider_id == "openrouter"
                and start.system_info.get("served_identity_source") == "response.model"
            )

        terminal_matches = (
            durable_terminal is not None
            and durable_terminal.success is True
            and durable_terminal.error_code is None
            and durable_terminal.timestamp == source.terminal_timestamp
        )
        verifier_accepted = all(
            (
                transcript is not None,
                bool(transcript_bytes),
                receipt_ref is not None,
                receipt_sha256 is not None,
                receipt_identity_ok,
                transcript_stable,
                replay_ok,
                not replay_issues,
                canonical_event_order,
                len(prompts) == 1,
                (
                    prompts[0].content == source.expected_prompt
                    if len(prompts) == 1
                    else False
                ),
                len(replies) >= 1,
                terminal_matches,
                start is not None,
                not start.tools_available if start is not None else False,
                not forbidden_event,
                adapter_event_providers_ok,
                transport_provenance_ok,
                provider_provenance_ok,
            )
        )

        try:
            observed_at = datetime.fromtimestamp(source.terminal_timestamp, timezone.utc)
        except (OSError, OverflowError, TypeError, ValueError):
            observed_at = None
        expires_at = (
            observed_at + model_status.MAX_ROUTE_VERIFICATION_TTL
            if observed_at is not None
            else None
        )
        return model_status.RouteEvidence(
            seat_id=seat.seat_id,
            logical_lineage=seat.logical_lineage,
            requested_provider=requested_provider,
            requested_model=source.requested_model_id,
            served_provider=served_provider,
            served_model=served_model,
            success=durable_terminal.success if durable_terminal is not None else None,
            synthetic=not transport_provenance_ok,
            observed_at=observed_at,
            expires_at=expires_at,
            verifier_id=model_status.ACCEPTED_ROUTE_VERIFIER_ID,
            verifier_version=model_status.ACCEPTED_ROUTE_VERIFIER_VERSION,
            verifier_accepted=verifier_accepted,
            receipt_ref=source.receipt_ref or receipt_ref,
            receipt_sha256=source.receipt_sha256 or receipt_sha256,
            runtime_epoch=self._runtime_owner_id,
        )

    def _emit_helm_projection_wire(self, request_id: str) -> None:
        self._emit(
            {
                "type": "helm.on_call_projection",
                "request_id": request_id,
                "projection": model_status.helm_on_call_projection_to_dict(
                    self._helm_on_call_projection
                ),
            }
        )

    def _emit_helm_on_call_baseline(self, request_id: str) -> None:
        """Emit the server-owned UNKNOWN census for a new bridge epoch."""

        self._helm_on_call_projection = model_status.unknown_helm_on_call_projection(
            now=datetime.now(timezone.utc),
            current_runtime_epoch=self._runtime_owner_id,
        )
        self._emit_helm_projection_wire(request_id)

    def _emit_helm_on_call_projection(self, request_id: str) -> None:
        """Re-read every durable receipt before emitting the render-only wire."""

        evidences: list[model_status.RouteEvidence] = []
        for seat in model_status.HELM_SLICE1_SEATS:
            source = self._helm_route_sources_by_seat.get(seat.seat_id)
            if source is None:
                self._helm_route_evidence_by_seat.pop(seat.seat_id, None)
                continue
            evidence = self._route_evidence_from_durable_session(source)
            if evidence is None:
                self._helm_route_evidence_by_seat.pop(seat.seat_id, None)
                continue
            self._helm_route_evidence_by_seat[seat.seat_id] = evidence
            evidences.append(evidence)
        self._helm_on_call_projection = model_status.project_helm_on_call(
            evidences,
            now=datetime.now(timezone.utc),
            current_runtime_epoch=self._runtime_owner_id,
        )
        self._emit_helm_projection_wire(request_id)

    async def _run_active_session(
        self,
        run: _ActiveSessionRun,
        request: dict[str, Any],
    ) -> None:
        try:
            await self._handle_session_start_body(run, request)
            if run.cancel_requested:
                self._emit_cancelled_terminal(run)
            elif not run.terminal_emitted:
                terminal = run.lifecycle.fail(
                    "provider stream ended without session_end",
                    error_code="missing_session_end",
                )
                if terminal is not None:
                    self._emit_recorded_session_event(run, terminal)
        except asyncio.CancelledError:
            if not run.cancel_requested:
                run.cancel_requested = True
                run.cancel_reason = "task_cancelled"
            self._emit_cancelled_terminal(run)
        except Exception as exc:
            self._emit(
                {
                    "type": "bridge.error",
                    "request_id": run.request_id,
                    "code": "handler_exception",
                    "message": f"{type(exc).__name__}: {exc}",
                }
            )
            terminal: SessionEnd | None = None
            try:
                terminal = run.lifecycle.fail(exc)
            except Exception as persistence_exc:
                self._emit(
                    {
                        "type": "bridge.error",
                        "request_id": run.request_id,
                        "code": "session_persistence_failed",
                        "message": f"{type(persistence_exc).__name__}: {persistence_exc}",
                    }
                )
                terminal = run.lifecycle.terminal_event
            if terminal is not None and not run.terminal_emitted:
                self._emit_recorded_session_event(run, terminal)
        finally:
            run.phase = "complete"
            self._remember_completed_session_request(run.request_id)
            self._clear_active_run(run)

    async def _handle_session_start_body(
        self,
        run: _ActiveSessionRun,
        request: dict[str, Any],
    ) -> None:
        request_id = run.request_id
        provider_id = run.provider_id
        prompt, error_code, error_message = self._validated_request_prompt(request)
        if prompt is None:
            terminal = run.lifecycle.fail(
                error_message or "invalid prompt",
                error_code=error_code or "invalid_prompt",
            )
            if terminal is not None:
                self._emit_recorded_session_event(run, terminal)
            return
        bootstrap = request.get("bootstrap")
        bootstrap = dict(bootstrap) if isinstance(bootstrap, dict) else {}
        if run.cancel_requested:
            raise asyncio.CancelledError
        intent = self._resolve_prompt_intent(prompt)
        bootstrap["intent"] = intent
        if intent.get("kind") == "command" and intent.get("auto_execute"):
            self._emit(
                {
                    "type": "intent.result",
                    "request_id": request_id,
                    "intent": intent,
                }
            )
            result = await self._handle_command(
                request_id,
                {
                    "command": str(intent.get("command", "")),
                },
            )
            outcome = str(result.get("outcome", "failed"))
            if outcome not in _COMMAND_OUTCOMES:
                outcome = "failed"
            success = outcome in {"completed", "accepted"}
            self._record_and_emit_session_event(
                run,
                SessionEnd(
                    provider_id=provider_id,
                    session_id=run.session_id,
                    success=success,
                    error_code=None if success else f"command_{outcome}",
                    error_message=(
                        None
                        if success
                        else f"command /{intent.get('command', '')} ended as {outcome}"
                    ),
                ),
            )
            return

        # Slice 1 has exactly one provider execution mode: byte-preserved chat
        # through the physical no-tools membrane. No inferred agent/evolution
        # path may regain the former tool-capable provider loop.
        await self._run_chat_turn(run, request)
