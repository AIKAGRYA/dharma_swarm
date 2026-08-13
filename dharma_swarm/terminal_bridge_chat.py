"""Conversational provider lanes for the terminal bridge."""

from __future__ import annotations

import asyncio
from dataclasses import asdict
import json
import os
import re
from typing import Any

from dharma_swarm import model_status
from dharma_swarm.terminal_bridge_external_preview import (
    explicit_external_preview_lane,
    external_preview_route,
    external_preview_targets,
    external_preview_tool_usage_is_zero,
    sanitize_external_preview_event,
)
from dharma_swarm.terminal_bridge_session_types import _ActiveSessionRun
from dharma_swarm.tui import model_routing
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
_SLICE1_CHAT_PROVIDER_IDS = frozenset(
    {"claude", "codex_text", "grok_oauth", "kimi_code", "ollama", "openrouter"}
)
_DEDICATED_PREVIEW_PROVIDER_IDS = frozenset({"codex_text", "grok_oauth", "kimi_code"})
_ALLOWED_CHAT_EVENT_TYPES = frozenset(
    {
        "error",
        "rate_limit",
        "session_end",
        "session_start",
        "text_complete",
        "text_delta",
        "thinking_complete",
        "thinking_delta",
        "usage",
    }
)
_FORBIDDEN_CHAT_EVENT_TYPES = frozenset(
    {
        "permission_decision",
        "permission_outcome",
        "permission_resolution",
        "task_complete",
        "task_progress",
        "task_started",
        "tool_args_delta",
        "tool_call_complete",
        "tool_call_start",
        "tool_progress",
        "tool_result",
    }
)
_FORBIDDEN_CHAT_EVENT_PREFIXES = (
    "command.",
    "command_",
    "permission.",
    "permission_",
    "task.",
    "task_",
    "tool.",
    "tool_",
)
_CHAT_TOOL_STRUCTURAL_KEYS = frozenset(
    {
        "function_call",
        "function_calls",
        "image_generation_call",
        "image_generation_calls",
        "mcp_call",
        "mcp_calls",
        "server_tool_use",
        "server_tool_use_details",
        "shell_call",
        "shell_calls",
        "tool",
        "tool_call",
        "tool_calls",
        "tool_use",
        "tool_uses",
        "web_search_call",
        "web_search_calls",
    }
)
_CHAT_TOOL_TYPE_MARKERS = (
    "code_interpreter",
    "computer_call",
    "computer_use",
    "code_interpreter_call",
    "file_search",
    "function_call",
    "image_generation_call",
    "mcp_call",
    "server_tool_use",
    "shell_call",
    "tool_call",
    "tool_use",
    "web_search",
)
_CHAT_TOOL_KEY_MARKERS = (
    "code_interpreter",
    "computer_call",
    "computer_use",
    "file_search",
    "function_call",
    "image_generation",
    "mcp",
    "server_tool_use",
    "shell_call",
    "tool",
    "web_search",
)
_CHAT_TOOL_CAPABILITIES = frozenset({
    "code_interpreter", "computer_use", "function_call", "mcp",
    "parallel_tools", "shell", "tool_use", "web_search",
})


def _chat_event_is_forbidden(event_type: object) -> bool:
    normalized = str(event_type or "").strip().lower()
    return (
        normalized not in _ALLOWED_CHAT_EVENT_TYPES
        or normalized in _FORBIDDEN_CHAT_EVENT_TYPES
        or normalized.startswith(_FORBIDDEN_CHAT_EVENT_PREFIXES)
    )


def _chat_event_contains_tool_evidence(value: object) -> bool:
    """Bounded structural scan; ordinary narration strings are never parsed."""

    pending: list[object] = [value]
    seen = 0
    while pending:
        current = pending.pop()
        seen += 1
        if seen > 4096:
            return True
        if isinstance(current, dict):
            for raw_key, item in current.items():
                key = _normalize_chat_structural_label(raw_key)
                if key == "tools":
                    if item not in (None, []):
                        return True
                    continue
                if key == "parallel_tool_calls":
                    if item not in (None, False):
                        return True
                    continue
                if key == "tool_choice":
                    if item not in (None, "none"):
                        return True
                    continue
                if key in {"server_tool_use", "server_tool_use_details"}:
                    if not external_preview_tool_usage_is_zero(item):
                        return True
                    continue
                if key in _CHAT_TOOL_STRUCTURAL_KEYS and item not in (
                    None,
                    "",
                    [],
                    {},
                ):
                    return True
                if (
                    any(marker in key for marker in _CHAT_TOOL_KEY_MARKERS)
                    and item not in (None, "", [], {})
                ):
                    return True
                if key in {
                    "event",
                    "finish_reason",
                    "finishreason",
                    "kind",
                    "native_finish_reason",
                    "nativefinishreason",
                    "object",
                    "stop_reason",
                    "stopreason",
                    "type",
                }:
                    normalized = _normalize_chat_structural_label(item)
                    if any(marker in normalized for marker in _CHAT_TOOL_TYPE_MARKERS):
                        return True
                if isinstance(item, (dict, list)):
                    pending.append(item)
        elif isinstance(current, list):
            pending.extend(current)
    return False


def _normalize_chat_structural_label(value: object) -> str:
    label = str(value or "").strip()
    label = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "_", label)
    label = re.sub(r"(?<=[A-Z])(?=[A-Z][a-z])", "_", label)
    return re.sub(r"[^a-z0-9]+", "_", label.lower()).strip("_")


def _chat_session_start_has_tool_authority(event: SessionStart) -> bool:
    capabilities = {_normalize_chat_structural_label(item) for item in event.capabilities}
    return bool(event.tools_available) or bool(capabilities & _CHAT_TOOL_CAPABILITIES)


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

    def _build_model_policy_summary(self, *, selected_provider: str, selected_model: str, strategy: str) -> dict[str, Any]:
        strategy = model_routing.resolve_strategy(strategy) or "responsive"
        projection = model_status.floor_model_status()
        status_by_model_id: dict[str, Any] = {}
        for projected in projection.models:
            status_by_model_id[projected.id] = projected
            for route_status in projected.route_statuses:
                status_by_model_id[route_status.model_id] = projected

        terminal_providers = self._available_provider_ids()
        local_attempt_cache: dict[str, bool] = {}
        seen_routes: set[tuple[str, str]] = set()
        targets: list[dict[str, Any]] = []
        for target in model_routing.all_targets():
            provider_id = target.provider_id
            route = (provider_id, target.model_id)
            if route in seen_routes:
                continue
            seen_routes.add(route)
            projected = status_by_model_id.get(target.model_id)
            provider_values = {provider.value for provider in target.pool_providers}
            route_statuses = (
                [
                    route_status
                    for route_status in projected.route_statuses
                    if route_status.provider in provider_values
                ]
                if projected is not None
                else []
            )
            model_available = any(
                route_status.status == "live_routable"
                for route_status in route_statuses
            )
            exact_model_proven = bool(
                projected is not None
                and getattr(projected.verification, "status", None) == "verified"
            )
            adapter_available = provider_id in terminal_providers
            oracle_unverified = bool(route_statuses) and all(
                route_status.status == "unverified"
                and route_status.reason == "key_status_unknown"
                for route_status in route_statuses
            )
            local_attempt_authorized = False
            if adapter_available and oracle_unverified:
                if provider_id not in local_attempt_cache:
                    local_attempt_cache[provider_id] = (
                        self._local_cli_attempt_authorized(provider_id)
                    )
                local_attempt_authorized = local_attempt_cache[provider_id]
            chat_executable = provider_id in {"claude", "openrouter"}
            selectable = adapter_available and chat_executable and (
                model_available or local_attempt_authorized
            )
            if (
                adapter_available
                and not chat_executable
                and (model_available or local_attempt_authorized)
            ):
                route_state = "unavailable"
                availability_reason = "terminal_chat_transport_unsupported"
            elif model_available and adapter_available:
                route_state = "ready" if exact_model_proven else "unverified"
                availability_reason = (
                    None if exact_model_proven else "exact_model_unproven"
                )
            elif local_attempt_authorized:
                route_state = "unverified"
                availability_reason = "local_cli_auth_unverified"
            elif model_available and not adapter_available:
                route_state = "unavailable"
                availability_reason = "terminal_adapter_missing"
            else:
                route_state = "unavailable"
                availability_reason = (
                    getattr(projected, "unavailable_reason", None)
                    or "no_live_route"
                    if projected is not None
                    else "model_status_missing"
                )
            targets.append(
                {
                    "alias": target.alias,
                    "provider": provider_id,
                    "model": target.model_id,
                    "label": target.label,
                    "route_id": f"{provider_id}:{target.model_id}",
                    "route_state": route_state,
                    "picker_visible": selectable,
                    "selectable": selectable,
                    "chat_executable": chat_executable,
                    "exact_model_proven": exact_model_proven,
                    "available": model_available,
                    "availability_reason": availability_reason,
                    "pool_id": getattr(projected, "id", None),
                    "tier": getattr(projected, "tier", "unknown"),
                    "lane": getattr(projected, "lane", "floor"),
                    "status": getattr(projected, "status", "unavailable"),
                    "available_routes": list(getattr(projected, "available_routes", [])),
                }
            )

        preview_model = self._local_preview_model()
        preview_selectable = bool(
            preview_model and "ollama" in terminal_providers
        )
        if preview_model:
            targets.append(
                {
                    "alias": "local-preview",
                    "provider": "ollama",
                    "model": preview_model,
                    "label": (
                        f"{preview_model} (local preview; not a Helm OnCall seat)"
                    ),
                    "route_id": f"ollama:{preview_model}",
                    "route_state": "unverified",
                    "picker_visible": preview_selectable,
                    "selectable": preview_selectable,
                    "chat_executable": preview_selectable,
                    "exact_model_proven": False,
                    "preview_only": True,
                    "helm_on_call_eligible": False,
                    "available": False,
                    "availability_reason": (
                        "local_preview_exact_model_unproven"
                        if preview_selectable
                        else "terminal_adapter_missing"
                    ),
                    "pool_id": None,
                    "tier": "preview",
                    "lane": "local_preview",
                    "status": "unverified",
                    "available_routes": [],
                }
            )

        preview_targets = external_preview_targets(terminal_providers)
        preview_route_ids = {
            str(target["route_id"])
            for target in preview_targets
        }
        # A preview route can intentionally reuse a canonical provider/model
        # identity (Kimi K3 does).  Its narrower authority must win instead of
        # leaving two contradictory picker rows where the first silently
        # regains fallback or Helm-promotion semantics.
        targets = [
            target
            for target in targets
            if str(target.get("route_id", "")) not in preview_route_ids
        ]
        targets.extend(preview_targets)

        selected_available = any(
            target["provider"] == selected_provider and target["model"] == selected_model
            and bool(target.get("selectable"))
            for target in targets
        )
        if not selected_available and targets:
            selectable_targets = [target for target in targets if bool(target.get("selectable"))]
            fallback_target = selectable_targets[0] if selectable_targets else targets[0]
            selected_provider = str(fallback_target["provider"])
            selected_model = str(fallback_target["model"])

        active_target = next(
            (
                target
                for target in targets
                if target["provider"] == selected_provider and target["model"] == selected_model
            ),
            None,
        )
        selected_is_preview = bool(
            active_target and active_target.get("preview_only")
        )
        fallback_chain = [] if selected_is_preview else [
            {
                "alias": str(target["alias"]),
                "provider": str(target["provider"]),
                "model": str(target["model"]),
                "label": str(target["label"]),
                "route_id": str(target["route_id"]),
                "route_state": str(target["route_state"]),
                "availability_reason": target.get("availability_reason"),
            }
            for target in targets
            if not (target["provider"] == selected_provider and target["model"] == selected_model)
            and bool(target.get("selectable"))
        ][:6]
        provider_counts: dict[str, int] = {}
        attemptable_provider_counts: dict[str, int] = {}
        for target in targets:
            provider = str(target["provider"])
            if bool(target.get("available")):
                provider_counts[provider] = provider_counts.get(provider, 0) + 1
            if bool(target.get("selectable")):
                attemptable_provider_counts[provider] = (
                    attemptable_provider_counts.get(provider, 0) + 1
                )
        default_provider, default_model = self._terminal_default_route()
        return {
            "schema_version": model_status.MODEL_STATUS_SCHEMA_VERSION,
            "oracle_state": projection.oracle_state,
            "live_providers": projection.live_providers,
            "selected_provider": selected_provider,
            "selected_model": selected_model,
            "selected_route": f"{selected_provider}:{selected_model}",
            "strategy": strategy,
            "strategies": list(model_routing.ROUTING_STRATEGIES),
            "default_route": f"{default_provider}:{default_model}",
            "active_label": str(active_target["label"]) if active_target else selected_model,
            "fallback_chain": fallback_chain,
            "targets": targets,
            "available_providers": [
                {"id": provider, "model_count": count}
                for provider, count in sorted(provider_counts.items())
            ],
            "attemptable_providers": [
                {"id": provider, "model_count": count}
                for provider, count in sorted(attemptable_provider_counts.items())
            ],
        }

    def _chat_lanes(self, requested_provider: str, requested_model: str) -> list[tuple[str, str, dict[str, Any], str]]:
        lanes: list[tuple[str, str, dict[str, Any], str]] = []
        seen: set[tuple[str, str]] = set()

        preview_model = self._local_preview_model()
        if requested_provider == "ollama":
            if (
                preview_model
                and requested_model == preview_model
                and "ollama" in self._adapters
            ):
                return [
                    (
                        "ollama",
                        preview_model,
                        {},
                        "explicit local preview; no external fallback",
                    )
                ]
            # An Ollama request is never rewritten onto a metered or unrelated
            # external provider. A missing/mismatched opt-in fails closed.
            return []

        preview_route = external_preview_route(requested_provider, requested_model)
        if preview_route is not None:
            explicit_lane = explicit_external_preview_lane(
                requested_provider,
                requested_model,
                self._adapters,
            )
            return [explicit_lane] if explicit_lane is not None else []
        if requested_provider in _DEDICATED_PREVIEW_PROVIDER_IDS:
            # These namespaces have exactly one governed route each. A typo,
            # stale served alias, or forged picker value must never fall back
            # onto a different account/provider.
            return []

        def add(provider_id: str, model_id: str, options: dict[str, Any], note: str) -> None:
            if (
                provider_id not in _SLICE1_CHAT_PROVIDER_IDS
                or provider_id not in self._adapters
                or not model_id
            ):
                return
            key = (provider_id, model_id)
            if key in seen:
                return
            seen.add(key)
            lanes.append((provider_id, model_id, options, note))

        requested_target = model_routing.target_for_route(requested_provider, requested_model)
        if requested_target is None:
            requested_target = model_routing.default_target()
        policy = self._build_model_policy_summary(
            selected_provider=requested_target.provider_id,
            selected_model=requested_target.model_id,
            strategy="responsive",
        )
        policy_targets = {
            (str(target.get("provider", "")), str(target.get("model", ""))): target
            for target in policy.get("targets", [])
            if isinstance(target, dict)
        }
        ordered_routes = [
            (
                str(policy.get("selected_provider", "")),
                str(policy.get("selected_model", "")),
            )
        ]
        ordered_routes.extend(
            (str(target.get("provider", "")), str(target.get("model", "")))
            for target in policy.get("fallback_chain", [])
            if isinstance(target, dict)
        )
        for provider_id, model_id in ordered_routes:
            projected = policy_targets.get((provider_id, model_id))
            target = model_routing.target_for_route(provider_id, model_id)
            if (
                projected is None
                or not bool(projected.get("selectable"))
                or target is None
                or not model_routing.is_routable(target)
            ):
                continue
            options = self._chat_claude_options() if provider_id == "claude" else {}
            note = (
                "configured canonical route"
                if provider_id == requested_provider and model_id == requested_model
                else "canonical live fallback"
            )
            add(provider_id, model_id, options, note)
        return lanes

    def _is_enabled_external_preview_route(
        self,
        provider_id: str,
        model_id: str,
    ) -> bool:
        return explicit_external_preview_lane(
            provider_id,
            model_id,
            self._adapters,
        ) is not None

    def _sealed_chat_options(
        self,
        provider_id: str,
        options: dict[str, Any],
    ) -> dict[str, Any]:
        """Return provider options that caller input cannot weaken."""

        if provider_id == "claude":
            return self._chat_claude_options()
        if provider_id == "openrouter":
            timeout = options.get("timeout_sec")
            sealed: dict[str, Any] = {"require_served_identity": True}
            if timeout is not None:
                sealed["timeout_sec"] = timeout
            return sealed
        return dict(options)

    def _chat_claude_model(self) -> str:
        # Genius strategy => Claude Opus 4.8 leads (the master lane). On the Max
        # plan every Claude tier costs the same, so cost-ranking to the cheapest
        # (Haiku, sub-floor) was pure downside — it picked a banished model.
        for target in model_routing.fallback_chain("", "", strategy="genius"):
            if target.provider_id == "claude":
                return target.model_id
        adapter = self._adapters.get("claude")
        if adapter is None:
            return ""
        return str(adapter.get_profile(None).model_id)

    def _chat_claude_options(self) -> dict[str, Any]:
        try:
            budget = float(os.environ.get("DHARMA_CHAT_MAX_BUDGET_USD", "") or 0.25)
        except ValueError:
            budget = 0.25
        return {
            "permission_mode": "plan",
            "tools": "",
            "max_budget_usd": budget,
            "strict_mcp_config": True,
            "max_turns": 1,
            "raw_single_user_prompt": True,
            "scrub_metered_keys": True,
            "subscription_auth_only": True,
            "strict_preview_protocol": True,
            "setting_sources": "",
        }

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
