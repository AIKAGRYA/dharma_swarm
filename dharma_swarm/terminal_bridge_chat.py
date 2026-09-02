"""Conversational provider lanes for the terminal bridge."""

from __future__ import annotations

import asyncio
from dataclasses import asdict
import json
from typing import Any

from dharma_swarm import terminal_bridge_chat_policy as _chat_policy
from dharma_swarm.terminal_bridge_external_preview import (
    external_preview_route,
    sanitize_external_preview_event,
)
from dharma_swarm.terminal_bridge_chat_membrane import (
    chat_event_contains_tool_evidence as _chat_event_contains_tool_evidence,
    failure_events as _failure_events,
    chat_event_is_forbidden as _chat_event_is_forbidden,
    chat_session_start_has_tool_authority as _chat_session_start_has_tool_authority,
)
from dharma_swarm.terminal_bridge_session_types import _ActiveSessionRun
from dharma_swarm.tui.engine.events import (
    CanonicalEventType,
    ContextReceipt,
    ErrorEvent,
    SessionEnd,
    SessionStart,
    TextComplete,
)

_MAX_PREVIEW_BUFFER_BYTES = 8 * 1024 * 1024
_MAX_PREVIEW_ASSISTANT_BYTES = 4 * 1024 * 1024
# Compatibility projections; policy authority lives in the extracted helper.
_SLICE1_CHAT_PROVIDER_IDS = _chat_policy._SLICE1_CHAT_PROVIDER_IDS
_DEDICATED_PREVIEW_PROVIDER_IDS = _chat_policy._DEDICATED_PREVIEW_PROVIDER_IDS


class TerminalBridgeChatMixin:
    """Own lightweight chat routing, fallback, and process-local continuity."""

    async def _run_chat_turn(
        self,
        run: _ActiveSessionRun,
        request: dict[str, Any],
    ) -> None:
        """Lightweight conversational turn: history, slim prompt, no tools.

        Lanes are tried in canon order (configured-if-cheap, then the
        model_hierarchy free-first choice, then the claude Max-plan no-tools
        lane). Each lane's events are buffered; only the winning lane (or the
        final failing lane) is emitted, so the TS sees exactly one coherent
        session lifecycle per request.
        """
        request_id = run.request_id
        prompt, error_code, error_message = self._validated_request_prompt(request)
        if prompt is None:
            terminal = run.lifecycle.fail(
                error_message or "invalid prompt",
                error_code=error_code or "invalid_prompt",
            )
            if terminal is not None:
                self._emit_recorded_session_event(run, terminal)
            return
        active_tab = self._canonical_active_tab(request.get("active_tab"))
        requested_provider = str(request.get("provider", "") or "").strip().lower()
        requested_model = str(request.get("model", "") or "").strip()
        requested_resume_id = str(request.get("resume_session_id", "") or "").strip()
        lanes = [
            lane
            for lane in self._chat_lanes(requested_provider, requested_model)
            if lane[0] != "codex"
        ]
        session_id = run.session_id
        if not lanes:
            message = "no chat-capable provider adapter is available"
            self._record_and_emit_session_event(
                run,
                ErrorEvent(
                    provider_id=run.provider_id,
                    session_id=session_id,
                    code="no_chat_route",
                    message=message,
                ),
            )
            terminal = run.lifecycle.fail(message, error_code="no_chat_route")
            if terminal is not None:
                self._emit_recorded_session_event(run, terminal)
            return

        base_messages = self._build_chat_messages(request, prompt)

        lane_queue = list(lanes)
        lane_failures: list[str] = []
        last_buffer: list[CanonicalEventType] = []
        last_route: tuple[str, str] | None = None
        last_context_receipt: ContextReceipt | None = None
        last_context_disposition = "missing"
        index = 0
        acknowledgement_emitted = False
        while index < len(lane_queue):
            if run.cancel_requested:
                raise asyncio.CancelledError
            provider_id, model_id, options, note = lane_queue[index]
            index += 1
            adapter = self._adapters.get(provider_id)
            if adapter is None:
                continue
            options = self._sealed_chat_options(provider_id, options)
            preview_route = external_preview_route(provider_id, model_id)
            run.phase = "streaming"
            messages = base_messages
            server_owned_context = self._server_owned_chat_context_for_lane(
                request,
                provider_id=provider_id,
                model_id=model_id,
            )
            context_receipt = self._server_owned_chat_context_receipt_for_lane(
                request,
                provider_id=provider_id,
                model_id=model_id,
            )
            advertised_context_disposition = str(
                context_receipt.get("disposition", "") or "missing"
            )
            system_prompt: str | None = self._render_chat_system_prompt(
                provider_id=provider_id,
                model_id=model_id,
                active_tab=active_tab,
                note=note,
                server_owned_context=server_owned_context,
            )
            resume_id: str | None = None
            if provider_id in {"claude", "codex_text"}:
                # Slice 1 uses the dedicated raw-single-user serializer. Keep
                # history in the durable transcript; the subprocess prompt is
                # exactly the newest operator utterance.
                messages = base_messages[-1:]
                # Provider-native continuity is an explicit operator action.
                # Never leak the last Claude process session into a fresh turn.
                resume_id = requested_resume_id or None if provider_id == "claude" else None
                if provider_id == "codex_text":
                    system_prompt = None
                elif resume_id:
                    # The CLI session already holds the conversation; send only
                    # the newest user message and skip re-appending the prompt.
                    messages = base_messages[-1:]
                    system_prompt = None
            if server_owned_context and system_prompt is None:
                context_receipt = {
                    **context_receipt,
                    "disposition": "omitted_for_native_continuity",
                }
                advertised_context_disposition = "omitted_for_native_continuity"
            pending_context_disposition = (
                "offered_unconfirmed"
                if advertised_context_disposition in {"attached", "attached_redacted"}
                else advertised_context_disposition
            )
            if not acknowledgement_emitted:
                acknowledgement_emitted = True
                self._emit_chat_ack(
                    request_id=request_id,
                    session_id=session_id,
                    provider_id=provider_id,
                    model_id=model_id,
                    context_disposition=pending_context_disposition,
                    context_receipt=context_receipt,
                )
            completion = self._completion_request_cls(
                messages=messages,
                model=model_id,
                system_prompt=system_prompt,
                tools=[],
                tool_choice="none",
                resume_session_id=resume_id,
                provider_options=dict(options),
            )
            pending_context_receipt = self._stage_pending_chat_context(
                run,
                provider_id=provider_id,
                model_id=model_id,
                context_receipt=context_receipt,
                pending_disposition=pending_context_disposition,
            )
            self._set_active_provider(
                run,
                provider_id,
                model_id,
                update_selection=True,
            )
            buffer: list[CanonicalEventType] = []
            reply_parts: list[str] = []
            success: bool | None = None
            failure_text = ""
            membrane_violation = False
            session_start_seen = False
            session_end_seen = False
            preview_buffer_bytes = 0
            preview_assistant_bytes = 0
            try:
                async for event in adapter.stream(completion, session_id=session_id):
                    if run.cancel_requested:
                        raise asyncio.CancelledError
                    if preview_route is not None:
                        preview_buffer_bytes += len(
                            json.dumps(
                                asdict(event),
                                ensure_ascii=False,
                                separators=(",", ":"),
                                default=str,
                            ).encode("utf-8")
                        )
                        if isinstance(event, TextComplete):
                            preview_assistant_bytes += len(
                                event.content.encode("utf-8")
                            )
                        if (
                            preview_buffer_bytes > _MAX_PREVIEW_BUFFER_BYTES
                            or preview_assistant_bytes
                            > _MAX_PREVIEW_ASSISTANT_BYTES
                        ):
                            success = False
                            membrane_violation = True
                            failure_text = (
                                "slice1 membrane rejected oversized provider response"
                            )
                            buffer = []
                            try:
                                await adapter.cancel()
                            except Exception:
                                failure_text = (
                                    f"{failure_text}; provider cancellation failed"
                                )
                            break
                    lifecycle_violation = session_end_seen or (
                        isinstance(event, SessionStart) and session_start_seen
                    )
                    if _chat_event_is_forbidden(event.type) or lifecycle_violation or (
                        isinstance(event, SessionStart)
                        and _chat_session_start_has_tool_authority(event)
                    ) or (
                        preview_route is not None and isinstance(event, ErrorEvent)
                    ) or (
                        preview_route is not None
                        and _chat_event_contains_tool_evidence(event.raw)
                    ):
                        success = False
                        membrane_violation = True
                        failure_text = (
                            f"slice1 membrane rejected provider event {event.type}"
                        )
                        buffer = []
                        try:
                            await adapter.cancel()
                        except Exception:
                            failure_text = (
                                f"{failure_text}; provider cancellation failed"
                            )
                        break
                    if preview_route is not None:
                        event = sanitize_external_preview_event(event)
                    if isinstance(event, SessionStart):
                        event.system_info = {
                            **event.system_info,
                            "helm_context": dict(context_receipt),
                        }
                        session_start_seen = True
                    if isinstance(event, TextComplete) and event.role == "assistant" and event.content.strip():
                        reply_parts.append(event.content)
                    if isinstance(event, ErrorEvent) and not failure_text:
                        failure_text = event.message
                    if isinstance(event, SessionEnd):
                        session_end_seen = True
                        success = bool(event.success)
                        if not event.success and not failure_text:
                            failure_text = str(event.error_message or event.error_code or "provider failed")
                    buffer.append(event)
            except asyncio.CancelledError:
                self._record_cancelled_chat_lane(
                    run,
                    pending_context_receipt,
                    buffer,
                    session_start_seen=session_start_seen,
                    advertised_disposition=advertised_context_disposition,
                    pending_disposition=pending_context_disposition,
                )
                raise
            except Exception as exc:
                success = False
                failure_text = f"{type(exc).__name__}: {exc}"
            if run.cancel_requested:
                self._record_cancelled_chat_lane(
                    run,
                    pending_context_receipt,
                    buffer,
                    session_start_seen=session_start_seen,
                    advertised_disposition=advertised_context_disposition,
                    pending_disposition=pending_context_disposition,
                )
                raise asyncio.CancelledError
            preview_start = (
                next(
                    (
                        event
                        for event in buffer
                        if isinstance(event, SessionStart)
                    ),
                    None,
                )
                if preview_route is not None
                else None
            )
            preview_identity_mismatch = bool(
                preview_route is not None
                and provider_id in {"claude", "kimi_code"}
                and (
                    preview_start is None
                    or preview_start.model != model_id
                    or not bool(
                        preview_start.system_info.get("exact_model_proven", False)
                    )
                )
            )
            if membrane_violation:
                run.phase = "finalizing"
                run.lifecycle.bind_route(provider_id=provider_id, model_id=model_id)
                self._record_final_context_receipt(
                    run,
                    pending_context_receipt,
                    lane_outcome="membrane_rejected",
                    disposition=(
                        advertised_context_disposition
                        if session_start_seen
                        else pending_context_disposition
                    ),
                )
                self._record_and_emit_session_event(
                    run,
                    ErrorEvent(
                        provider_id=provider_id,
                        session_id=session_id,
                        code="chat_membrane_violation",
                        message=failure_text,
                        retryable=False,
                    ),
                )
                terminal = run.lifecycle.fail(
                    failure_text,
                    error_code="chat_membrane_violation",
                )
                if terminal is not None:
                    self._emit_recorded_session_event(run, terminal)
                return
            if preview_route is not None and (
                not (success is True and session_start_seen and bool(reply_parts))
                or preview_identity_mismatch
            ):
                # Preview receipts are evidence-bearing operator diagnostics.
                # A transport exit alone is never a completion, and raw
                # provider errors (including CLI stderr) must not cross this
                # boundary because they may contain credentials or host data.
                code = (
                    "preview_identity_mismatch"
                    if preview_identity_mismatch
                    else (
                        "preview_incomplete_response"
                        if success is True
                        else "preview_provider_failed"
                    )
                )
                failure_text = "preview route produced no usable sealed response"
                success = False
                buffer = _failure_events(
                    provider_id=provider_id,
                    session_id=session_id,
                    code=code,
                    message=failure_text,
                    retryable=False,
                )
            if preview_route is None and success is True and not session_start_seen:
                # A clean provider exit is transport evidence only. Without an
                # accepted start boundary, neither the staged context nor the
                # requested route can truthfully be promoted to completed.
                failure_text = (
                    "provider stream ended successfully without session_start"
                )
                success = False
                buffer = _failure_events(
                    provider_id=provider_id,
                    session_id=session_id,
                    code="missing_session_start",
                    message=failure_text,
                    retryable=True,
                )
            if success:
                run.phase = "finalizing"
                run.lifecycle.bind_route(provider_id=provider_id, model_id=model_id)
                preview_served_model = model_id
                preview_exact_model_proven = False
                if preview_route is not None:
                    if preview_start is not None:
                        preview_served_model = preview_start.model
                        preview_exact_model_proven = bool(
                            preview_start.system_info.get("exact_model_proven", False)
                        )
                self._record_final_context_receipt(
                    run,
                    pending_context_receipt,
                    lane_outcome="completed",
                    disposition=advertised_context_disposition,
                )
                for event in buffer:
                    accepted = self._record_and_emit_session_event(run, event)
                    if isinstance(accepted, SessionEnd) and accepted.success:
                        if preview_route is not None:
                            self._emit_preview_route_receipt(
                                run,
                                provider_id=provider_id,
                                model_id=model_id,
                                route_id=preview_route.route_id,
                                served_model_id=preview_served_model,
                                exact_model_proven=preview_exact_model_proven,
                            )
                        else:
                            self._emit_provider_route_receipt(
                                run,
                                accepted,
                                requested_provider_id=provider_id,
                                requested_model_id=model_id,
                                expected_prompt=prompt,
                                adapter=adapter,
                            )
                self._remember_chat_exchange(prompt, "\n\n".join(reply_parts).strip())
                return
            lane_failures.append(f"{provider_id}:{model_id} — {failure_text or 'failed'}")
            last_buffer = buffer
            last_route = (provider_id, model_id)
            last_context_receipt = pending_context_receipt
            last_context_disposition = (
                advertised_context_disposition
                if session_start_seen
                else pending_context_disposition
            )
            if provider_id == "claude" and resume_id is not None:
                # A stale resume id must not burn the lane: retry once fresh.
                requested_resume_id = ""
                lane_queue.insert(index, (provider_id, model_id, options, f"{note} (fresh session retry)"))
        emitted_session_end = False
        run.phase = "finalizing"
        if last_route is not None:
            run.lifecycle.bind_route(
                provider_id=last_route[0],
                model_id=last_route[1],
            )
        if last_route is not None:
            if last_context_receipt is None:
                raise RuntimeError("final chat lane is missing its pending context receipt")
            self._record_final_context_receipt(
                run,
                last_context_receipt,
                lane_outcome="failed",
                disposition=last_context_disposition,
            )
        for event in last_buffer:
            accepted = self._record_and_emit_session_event(run, event)
            if isinstance(accepted, SessionEnd):
                emitted_session_end = True
        if not emitted_session_end:
            message = "; ".join(lane_failures) or "no chat lane produced a response"
            self._record_and_emit_session_event(
                run,
                ErrorEvent(
                    provider_id=last_route[0] if last_route else run.provider_id,
                    session_id=session_id,
                    code="chat_lanes_exhausted",
                    message=message,
                    retryable=True,
                ),
            )
            terminal = run.lifecycle.fail(
                message,
                error_code="chat_lanes_exhausted",
            )
            if terminal is not None:
                self._emit_recorded_session_event(run, terminal)
