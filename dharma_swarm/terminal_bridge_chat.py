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
    chat_event_is_forbidden as _chat_event_is_forbidden,
    chat_session_start_has_tool_authority as _chat_session_start_has_tool_authority,
)
from dharma_swarm.terminal_bridge_session_types import _ActiveSessionRun
from dharma_swarm.tui.engine.events import (
    CanonicalEventType,
    ErrorEvent,
    SessionEnd,
    SessionStart,
    TextComplete,
)

# Chat-lane sizing: messages sent per turn / retained per bridge process.
CHAT_HISTORY_SEND_LIMIT = 24
CHAT_HISTORY_RETAIN = 48
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
        active_tab = str(request.get("active_tab", "") or "chat")
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
        self._emit(
            {
                "type": "session.ack",
                "request_id": request_id,
                "session_id": session_id,
                "provider": lanes[0][0],
                "model": lanes[0][1],
                "mode": "chat",
                "execution_mode": "read_only_no_tools",
                "tools_enabled": False,
                "authority": "NONE",
            }
        )

        lane_queue = list(lanes)
        lane_failures: list[str] = []
        last_buffer: list[CanonicalEventType] = []
        last_route: tuple[str, str] | None = None
        index = 0
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
            self._set_active_provider(
                run,
                provider_id,
                model_id,
                update_selection=True,
            )
            run.phase = "streaming"
            messages = base_messages
            system_prompt: str | None = self._render_chat_system_prompt(
                provider_id=provider_id,
                model_id=model_id,
                active_tab=active_tab,
                note=note,
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
            completion = self._completion_request_cls(
                messages=messages,
                model=model_id,
                system_prompt=system_prompt,
                tools=[],
                tool_choice="none",
                resume_session_id=resume_id,
                provider_options=dict(options),
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
                raise
            except Exception as exc:
                success = False
                failure_text = f"{type(exc).__name__}: {exc}"
            if run.cancel_requested:
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
                buffer = [
                    ErrorEvent(
                        provider_id=provider_id,
                        session_id=session_id,
                        code=code,
                        message=failure_text,
                        retryable=False,
                    ),
                    SessionEnd(
                        provider_id=provider_id,
                        session_id=session_id,
                        success=False,
                        error_code=code,
                        error_message=failure_text,
                    ),
                ]
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
                for event in buffer:
                    accepted = self._record_and_emit_session_event(run, event)
                    if isinstance(accepted, SessionEnd) and accepted.success:
                        if preview_route is not None:
                            self._emit(
                                {
                                    "type": "route.receipt",
                                    "request_id": run.request_id,
                                    "session_id": run.session_id,
                                    "provider_id": provider_id,
                                    "model_id": model_id,
                                    "requested_model_id": model_id,
                                    "served_model_id": preview_served_model,
                                    "route_id": preview_route.route_id,
                                    "evidence_kind": "preview_provider_completion",
                                    "success": True,
                                    "preview_only": True,
                                    "helm_on_call_eligible": False,
                                    "exact_model_proven": preview_exact_model_proven,
                                }
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

    def _build_model_policy_summary(
        self,
        *,
        selected_provider: str,
        selected_model: str,
        strategy: str,
    ) -> dict[str, Any]:
        return _chat_policy._build_model_policy_summary(
            self,
            selected_provider=selected_provider,
            selected_model=selected_model,
            strategy=strategy,
        )

    def _chat_lanes(
        self,
        requested_provider: str,
        requested_model: str,
    ) -> list[tuple[str, str, dict[str, Any], str]]:
        return _chat_policy._chat_lanes(
            self,
            requested_provider,
            requested_model,
        )

    def _is_enabled_external_preview_route(
        self,
        provider_id: str,
        model_id: str,
    ) -> bool:
        return _chat_policy._is_enabled_external_preview_route(
            self,
            provider_id,
            model_id,
        )

    def _sealed_chat_options(
        self,
        provider_id: str,
        options: dict[str, Any],
    ) -> dict[str, Any]:
        return _chat_policy._sealed_chat_options(self, provider_id, options)

    def _chat_claude_model(self) -> str:
        return _chat_policy._chat_claude_model(self)

    def _chat_claude_options(self) -> dict[str, Any]:
        return _chat_policy._chat_claude_options(self)

    def _build_chat_messages(self, request: dict[str, Any], prompt: str) -> list[dict[str, str]]:
        ts_messages: list[dict[str, str]] = []
        raw = request.get("messages")
        if isinstance(raw, list):
            for item in raw:
                if not isinstance(item, dict):
                    continue
                role = str(item.get("role", "") or "").strip().lower()
                content = item.get("content")
                if role not in {"user", "assistant"} or not isinstance(content, str):
                    continue
                if content.strip():
                    ts_messages.append({"role": role, "content": content})
        history = [dict(item) for item in self._chat_history]
        if not history and ts_messages:
            # Bridge restarted mid-conversation: seed from the history the TS
            # already sends (user turns at minimum).
            history = ts_messages
            if history and history[-1]["role"] == "user" and history[-1]["content"] == prompt:
                history = history[:-1]
        history = history[-(CHAT_HISTORY_SEND_LIMIT - 1):]
        return [*history, {"role": "user", "content": prompt}]

    def _remember_chat_exchange(self, prompt: str, reply: str) -> None:
        self._chat_history.append({"role": "user", "content": prompt})
        if reply.strip():
            self._chat_history.append({"role": "assistant", "content": reply.strip()})
        self._chat_history = self._chat_history[-CHAT_HISTORY_RETAIN:]

    def _render_chat_system_prompt(self, *, provider_id: str, model_id: str, active_tab: str, note: str) -> str:
        lines = [
            "You are the Dharma Helm — the conversational operator assistant of the dharma_swarm terminal, speaking in its chat pane.",
            f"Route: {provider_id}:{model_id} ({note}). Active tab: {active_tab}.",
            "Stay conversational and concise; keep continuity with the conversation history provided.",
            "Slice 1 is physically read-only and no-tools. You cannot execute commands, create tasks, dispatch agents, mutate runtime or workspace state, or cause external effects.",
            "All of your prose is unverified narration with authority NONE. Never claim that requested work was completed or promote task, project, route, organism, or effect state.",
            "Do not emit Helm directives or machine-action sentinels; respond with narration only.",
        ]
        return "\n".join(lines)[:1400]
