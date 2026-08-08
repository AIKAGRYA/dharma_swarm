"""Session launch and provider-stream execution for the terminal bridge."""

from __future__ import annotations

import asyncio
from dataclasses import asdict
from typing import Any

from dharma_swarm.operator_core.session_lifecycle import SessionLifecycleRecorder
from dharma_swarm.terminal_bridge_session_types import _ActiveSessionRun
from dharma_swarm.tui import model_routing
from dharma_swarm.tui.engine.events import (
    CanonicalEventType,
    SessionEnd,
    SessionStart,
    ToolCallComplete,
)


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
        prompt = str(request.get("prompt", "") or "").strip()
        if not prompt:
            self._emit(
                {
                    "type": "bridge.error",
                    "request_id": request_id,
                    "code": "missing_prompt",
                    "message": "session.start requires a prompt",
                }
            )
            return None

        owned_request = dict(request)
        default_target = model_routing.default_target()
        provider_id = str(request.get("provider", "") or default_target.provider_id).strip().lower()
        model_id = str(request.get("model", "") or "").strip()
        adapter = self._adapters.get(provider_id)
        if not model_id and adapter is not None:
            model_id = str(adapter.get_profile(None).model_id)
        if not model_id:
            model_id = default_target.model_id
        bootstrap = request.get("bootstrap")
        intent = bootstrap.get("intent") if isinstance(bootstrap, dict) else None
        if isinstance(intent, dict) and str(intent.get("kind", "chat")) == "chat":
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
        requested_session_id = str(request.get("session_id", "") or "").strip() or None
        parent_session_id = str(request.get("parent_session_id", "") or "").strip() or None
        try:
            lifecycle = SessionLifecycleRecorder.begin(
                self._session_store,
                session_id=requested_session_id,
                provider_id=provider_id,
                model_id=model_id,
                cwd=str(self._repo_root),
                prompt=prompt,
                parent_session_id=parent_session_id,
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
    ) -> None:
        """Emit liveness authority only for a real provider completion.

        ``session_end`` is also used by local identity, memory, and command
        paths, so it cannot itself prove that a model route executed.  This
        receipt is emitted only by the two adapter-stream loops below.
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
        adapter = self._adapters[provider_id]
        prompt = str(request.get("prompt", "") or "").strip()
        bootstrap = request.get("bootstrap")
        if not isinstance(bootstrap, dict):
            bootstrap = await asyncio.to_thread(self._build_session_bootstrap, request)
        if run.cancel_requested:
            raise asyncio.CancelledError
        intent = bootstrap.get("intent") if isinstance(bootstrap, dict) else None
        if isinstance(intent, dict) and intent.get("kind") == "command" and intent.get("auto_execute"):
            self._emit(
                {
                    "type": "intent.result",
                    "request_id": request_id,
                    "intent": intent,
                }
            )
            await self._handle_command(
                request_id,
                {
                    "command": str(intent.get("command", "")),
                },
            )
            self._record_and_emit_session_event(
                run,
                SessionEnd(
                    provider_id=provider_id,
                    session_id=run.session_id,
                    success=True,
                ),
            )
            return
        if isinstance(intent, dict) and intent.get("kind") == "identity":
            self._emit(
                {
                    "type": "assistant",
                    "request_id": request_id,
                    "message": self._render_identity_response(bootstrap if isinstance(bootstrap, dict) else {}),
                }
            )
            self._record_and_emit_session_event(
                run,
                SessionEnd(
                    provider_id=provider_id,
                    session_id=run.session_id,
                    success=True,
                ),
            )
            return
        if isinstance(intent, dict) and intent.get("kind") == "memory":
            self._emit(
                {
                    "type": "assistant",
                    "request_id": request_id,
                    "message": self._render_memory_response(bootstrap if isinstance(bootstrap, dict) else None),
                }
            )
            self._record_and_emit_session_event(
                run,
                SessionEnd(
                    provider_id=provider_id,
                    session_id=run.session_id,
                    success=True,
                ),
            )
            return

        intent_kind = str(intent.get("kind", "chat")) if isinstance(intent, dict) else "chat"
        if intent_kind == "chat":
            # Conversational turns ride the lightweight completion path:
            # conversation history, slim system prompt, no tools, no agentic
            # session boot. Operational intents (command/agent/evolution)
            # keep the rich path below.
            await self._run_chat_turn(run, request)
            return

        session_id = run.session_id
        run.phase = "streaming"
        self._emit(
            {
                "type": "session.ack",
                "request_id": request_id,
                "session_id": session_id,
                "provider": provider_id,
                "model": run.model_id,
            }
        )

        provider_options = dict(request.get("provider_options", {}) or {})
        if provider_id == "claude":
            provider_options.setdefault("scrub_metered_keys", True)
            provider_options.setdefault("permission_mode", "default")
        elif provider_id == "codex":
            provider_options.setdefault("sandbox", "read-only")

        completion = self._completion_request_cls(
            messages=[{"role": "user", "content": prompt}],
            model=str(request.get("model", "") or adapter.get_profile(None).model_id),
            system_prompt=str(request.get("system_prompt", "") or bootstrap.get("system_prompt", "") or "") or None,
            enable_thinking=bool(request.get("enable_thinking", False)),
            resume_session_id=str(request.get("resume_session_id", "") or "") or None,
            provider_options=provider_options,
        )

        async for event in adapter.stream(completion, session_id=session_id):
            if run.cancel_requested:
                raise asyncio.CancelledError
            if isinstance(event, ToolCallComplete):
                self._emit_permission_decision(request_id, event)
            accepted = self._record_and_emit_session_event(run, event)
            if isinstance(accepted, SessionEnd) and accepted.success:
                self._emit_provider_route_receipt(run, accepted)
