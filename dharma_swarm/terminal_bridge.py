"""JSON stdio bridge for a future Bun/Ink terminal frontend.

This module keeps Python as the runtime/core layer while exposing a narrow
provider-agnostic event protocol to a terminal UI implemented elsewhere.
It is intentionally independent of Textual so the operator shell can be
replaced without rewriting provider adapters and command handling.
"""

from __future__ import annotations

import argparse
import asyncio
from dataclasses import asdict, is_dataclass
import importlib.util
import json
from datetime import datetime, timezone
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import uuid
from typing import Any
from dharma_swarm.terminal_bridge_text import (
    render_working_memory,
    render_git_summary_lines,
    render_command_graph_text,
    render_command_registry_text,
    render_operator_snapshot_text,
    render_model_policy_text,
    render_agent_routes_text,
    render_evolution_surface_text,
    render_session_catalog_text,
    render_session_detail_text,
    render_identity_response,
    render_memory_response,
)


from dharma_swarm.context import build_orientation_packet
from dharma_swarm.cascade import get_registered_domains
from dharma_swarm.operator_views import OperatorViews
from dharma_swarm.operator_core import (
    build_permission_history_payload,
    build_permission_decision_payload,
    build_agent_routes_payload,
    build_routing_decision_payload,
    build_runtime_snapshot_payload,
    build_workspace_snapshot_payload,
)
from dharma_swarm.orientation_packet import DirectiveSummary, RuntimeStateSummary
from dharma_swarm import model_status
from dharma_swarm.runtime_state import DEFAULT_RUNTIME_DB, RuntimeStateStore
from dharma_swarm.tui import model_routing
try:
    from dharma_swarm.tui.commands import system_commands as system_commands_module
    from dharma_swarm.tui.commands.system_commands import SystemCommandHandler
except ImportError:
    system_commands_module = None  # type: ignore[assignment]
    SystemCommandHandler = None  # type: ignore[assignment,misc]
from dharma_swarm.tui_helpers import build_runtime_status_text
from dharma_swarm.workspace_topology import build_workspace_topology
from dharma_swarm.operator_core import build_session_catalog, build_session_detail
from dharma_swarm.operator_core.session_store import SessionStore
from dharma_swarm.terminal_bridge_chat import TerminalBridgeChatMixin
from dharma_swarm.terminal_bridge_external_preview import (
    GPT_5_6_SOL_MODEL_ID,
    KIMI_K3_MODEL_ID,
    default_external_preview_route,
)
from dharma_swarm.terminal_bridge_helm_context import TerminalBridgeHelmContextMixin
from dharma_swarm.terminal_bridge_route_truth import TerminalBridgeRouteTruthMixin
from dharma_swarm.terminal_bridge_session_runtime import (
    TerminalBridgeSessionRuntimeMixin,
    _UNSUPPORTED_BRIDGE_COMMANDS,
    _command_name,
    _is_registered_command,
    _is_unconsumed_command_action,
    _validated_command_envelope,
)
from dharma_swarm.terminal_bridge_session_types import _ActiveSessionRun
from dharma_swarm.terminal_control import load_terminal_control_state
from dharma_swarm.tui.engine.events import (
    PermissionDecisionEvent,
    PermissionOutcomeEvent,
    PermissionResolutionEvent,
    ToolCallComplete,
)

_HELM_LOCAL_PREVIEW_MODEL_ENV = "DHARMA_HELM_LOCAL_PREVIEW_MODEL"


def _json_default(value: object) -> object:
    if is_dataclass(value):
        return asdict(value)
    if isinstance(value, set):
        return sorted(value)
    return str(value)


class TerminalBridge(
    TerminalBridgeSessionRuntimeMixin,
    TerminalBridgeRouteTruthMixin,
    TerminalBridgeChatMixin,
    TerminalBridgeHelmContextMixin,
):
    """Minimal stdio protocol server for a terminal frontend."""

    def __init__(
        self,
        *,
        session_store: SessionStore | None = None,
        helm_context_sources: object | None = None,
    ) -> None:
        self._commands = SystemCommandHandler() if SystemCommandHandler is not None else None
        self._adapters: dict[str, Any] = {}
        self._adapter_boot_error: str | None = None
        self._completion_request_cls: Any | None = None
        self._active_session_id: str | None = None
        self._active_provider_id: str | None = None
        self._active_model_id: str | None = None
        self._active_run: _ActiveSessionRun | None = None
        self._completed_session_request_ids: list[str] = []
        self._selected_provider_id: str | None = None
        self._selected_model_id: str | None = None
        self._closing = False
        self._repo_root = Path.cwd().resolve()
        self._package_root = Path(__file__).resolve().parent
        self._state_dir = Path.home() / ".dharma" / "terminal"
        self._runtime_owner_id = f"terminal-bridge:{uuid.uuid4()}"
        self._runtime_owner_pid = os.getpid()
        self._helm_route_evidence_by_seat: dict[str, model_status.RouteEvidence] = {}
        self._helm_route_sources_by_seat: dict[str, Any] = {}
        self._helm_on_call_projection = model_status.unknown_helm_on_call_projection(
            now=datetime.now(timezone.utc),
            current_runtime_epoch=self._runtime_owner_id,
        )
        self._session_recovery_complete = False
        self._session_store = session_store if session_store is not None else SessionStore()
        self._initialize_helm_context(helm_context_sources=helm_context_sources)
        self._chat_history: list[dict[str, str]] = []
        self._ensure_adapters()

    def _load_repo_guidance(self, limit_chars: int = 2400) -> str:
        guidance_path = self._repo_root / "CLAUDE.md"
        try:
            text = guidance_path.read_text(encoding="utf-8").strip()
        except OSError:
            return ""
        if not text:
            return ""
        sections = self._summarize_repo_guidance(text)
        text = sections or text
        if len(text) <= limit_chars:
            return text
        return text[: limit_chars - 1].rstrip() + "…"

    def _summarize_repo_guidance(self, text: str) -> str:
        lines = text.splitlines()
        kept: list[str] = []
        current_heading = ""
        allowed_headings = {
            "## Behavioral Rules (Always Enforced)",
            "## File Organization",
            "## Project Architecture",
            "## CLI Entry Points",
            "## Security Rules",
        }
        for line in lines:
            stripped = line.rstrip()
            if stripped.startswith("## "):
                current_heading = stripped
                if current_heading in allowed_headings:
                    kept.append(stripped)
                continue
            if current_heading not in allowed_headings:
                continue
            if stripped.startswith("- ") or stripped.startswith("```") or stripped.startswith("dgc ") or stripped.startswith("uvicorn ") or stripped.startswith("bash "):
                kept.append(stripped)
        return "\n".join(line for line in kept if line)

    def _load_session_context_hint(self) -> str:
        try:
            from dharma_swarm.claude_hooks import session_context

            return session_context().strip()
        except Exception:
            return ""

    def _memory_path(self) -> Path:
        return self._state_dir / "working_memory.json"

    def _load_working_memory(self) -> dict[str, Any]:
        path = self._memory_path()
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {
                "recent_turns": [],
                "recent_actions": [],
                "active_mission": "",
                "preferred_route": "",
                "updated_at": "",
            }
        if not isinstance(payload, dict):
            return {"recent_turns": [], "recent_actions": [], "active_mission": "", "preferred_route": "", "updated_at": ""}
        payload.setdefault("recent_turns", [])
        payload.setdefault("recent_actions", [])
        payload.setdefault("active_mission", "")
        payload.setdefault("preferred_route", "")
        payload.setdefault("updated_at", "")
        return payload

    def _save_working_memory(self, payload: dict[str, Any]) -> None:
        self._state_dir.mkdir(parents=True, exist_ok=True)
        payload["updated_at"] = datetime.now(timezone.utc).isoformat()
        self._memory_path().write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8")

    def _remember_turn(self, *, prompt: str, intent: dict[str, Any], route: str, active_tab: str) -> None:
        memory = self._load_working_memory()
        self._apply_turn_to_memory(memory, prompt=prompt, intent=intent, route=route, active_tab=active_tab)
        self._save_working_memory(memory)

    def _apply_turn_to_memory(self, memory: dict[str, Any], *, prompt: str, intent: dict[str, Any], route: str, active_tab: str) -> dict[str, Any]:
        turns = memory.get("recent_turns", [])
        if not isinstance(turns, list):
            turns = []
        turns.append(
            {
                "prompt": prompt,
                "intent": str(intent.get("kind", "chat")),
                "route": route,
                "active_tab": active_tab,
            }
        )
        memory["recent_turns"] = turns[-8:]
        if str(intent.get("kind", "")) in {"agent", "evolution", "command"}:
            memory["active_mission"] = prompt[:200]
        memory["preferred_route"] = route
        return memory

    def _remember_action(self, summary: str) -> None:
        memory = self._load_working_memory()
        actions = memory.get("recent_actions", [])
        if not isinstance(actions, list):
            actions = []
        actions.append(summary)
        memory["recent_actions"] = [str(item) for item in actions][-8:]
        self._save_working_memory(memory)

    def _render_working_memory(self, memory: dict[str, Any]) -> str:
        return render_working_memory(memory)

    def _ensure_adapters(self) -> None:
        if self._adapters or self._adapter_boot_error is not None:
            return
        try:
            from dharma_swarm.tui.engine.adapters import (
                ClaudeAdapter,
                CodexAdapter,
                CodexTextAdapter,
                CompletionRequest,
                GrokOAuthResponsesAdapter,
                KimiCodeAdapter,
                OllamaAdapter,
                OpenRouterAdapter,
                ProviderConfig,
            )

            adapters = {
                "claude": ClaudeAdapter(),
                "codex": CodexAdapter(),
                "codex_text": CodexTextAdapter(
                    config=ProviderConfig(
                        provider_id="codex_text",
                        default_model=GPT_5_6_SOL_MODEL_ID,
                    )
                ),
                "kimi_code": KimiCodeAdapter(
                    config=ProviderConfig(
                        provider_id="kimi_code",
                        default_model=KIMI_K3_MODEL_ID,
                    )
                ),
                "grok_oauth": GrokOAuthResponsesAdapter(),
                "openrouter": OpenRouterAdapter(),
            }
            preview_model = self._local_preview_model()
            if preview_model:
                adapters["ollama"] = OllamaAdapter(model_id=preview_model)
            self._adapters = adapters
            self._completion_request_cls = CompletionRequest
        except Exception as exc:
            self._adapter_boot_error = f"{type(exc).__name__}: {exc}"

    def _available_provider_ids(self) -> set[str]:
        return set(self._adapters)

    @staticmethod
    def _local_preview_model() -> str:
        """Return the explicit local-preview model, or disable the lane.

        This opt-in is intentionally separate from the canonical model roster:
        a locally installed model can execute a preview chat turn without
        claiming a Helm OnCall seat or exact-model route proof.
        """

        return os.environ.get(_HELM_LOCAL_PREVIEW_MODEL_ENV, "").strip()

    def _terminal_default_route(self) -> tuple[str, str]:
        preview_model = self._local_preview_model()
        if self._is_enabled_local_preview_route("ollama", preview_model):
            return "ollama", preview_model
        account_preview = default_external_preview_route(self._adapters)
        if account_preview is not None:
            return account_preview
        target = model_routing.default_target()
        return target.provider_id, target.model_id

    def _is_enabled_local_preview_route(
        self,
        provider_id: str,
        model_id: str,
    ) -> bool:
        preview_model = self._local_preview_model()
        adapter = self._adapters.get("ollama")
        return bool(
            preview_model
            and provider_id == "ollama"
            and model_id == preview_model
            and adapter is not None
            and getattr(adapter, "provider_id", None) == "ollama"
        )

    def _is_server_owned_chat_transport(self, provider_id: str, adapter: object) -> bool:
        """Return the non-forgeable in-process provenance fact for a chat lane."""

        return (
            provider_id
            in {"claude", "codex_text", "grok_oauth", "kimi_code", "openrouter"}
            and self._adapters.get(provider_id) is adapter
        )

    def _local_cli_attempt_authorized(self, provider_id: str) -> bool:
        """Whether an unverified local CLI lane may be attempted.

        This is deliberately weaker than model availability. It grants only
        execution authority while the canonical key oracle is unknown; the
        route remains ``unverified`` until a real provider event succeeds.
        Keyed HTTP adapters never receive this exception.
        """

        adapter = self._adapters.get(provider_id)
        if adapter is None or provider_id not in {"claude", "codex"}:
            return False
        cli_path = str(getattr(adapter, "_cli_path", provider_id) or provider_id)
        binary = shutil.which(cli_path)
        if binary is None:
            return False

        if provider_id == "claude":
            # Claude auth presence is insufficient: a logged-in Max client can
            # still fail every headless request. Reuse the smoke-proven oracle.
            from dharma_swarm import key_oracle

            return key_oracle.is_provider_live("claude_code") is True

        try:
            result = subprocess.run(
                [binary, "login", "status"],
                capture_output=True,
                text=True,
                timeout=5,
                stdin=subprocess.DEVNULL,
                check=False,
            )
        except (OSError, subprocess.SubprocessError):
            return False
        # A successful local OAuth-status command permits an attempt, not a
        # liveness claim. The first actual completion is still the proof.
        return result.returncode == 0

    async def close(self) -> None:
        if self._closing:
            active = self._active_run
            if active is not None and active.task is not None:
                await asyncio.gather(active.task, return_exceptions=True)
            return
        self._closing = True
        active = self._active_run
        if active is not None and active.task is not None:
            await self._cancel_active_run(active, reason="bridge_closed")
        for adapter in self._adapters.values():
            await adapter.close()

    async def run_stdio(self) -> int:
        if not self._session_recovery_complete:
            self._session_store.recover_orphaned_sessions(
                cwd=str(self._repo_root),
                active_owner_id=self._runtime_owner_id,
                active_owner_pid=self._runtime_owner_pid,
            )
            self._session_recovery_complete = True
        self._emit(
            {
                "type": "bridge.ready",
                "schema_version": 1,
                "protocol": "dharma-terminal-bridge",
            }
        )

        while True:
            raw_line = await asyncio.to_thread(sys.stdin.readline)
            if raw_line == "":
                break
            line = raw_line.strip()
            if not line:
                continue
            try:
                request = json.loads(line)
            except json.JSONDecodeError as exc:
                self._emit(
                    {
                        "type": "bridge.error",
                        "code": "invalid_json",
                        "message": exc.msg,
                    }
                )
                continue
            if not isinstance(request, dict):
                self._emit(
                    {
                        "type": "bridge.error",
                        "code": "invalid_request",
                        "message": "request must be a JSON object",
                    }
                )
                continue
            try:
                await self._handle_request(request)
            except Exception as exc:
                # A handler crash must never kill the bridge silently: emit an
                # explicit failure tied to the request and keep serving.
                self._emit(
                    {
                        "type": "bridge.error",
                        "request_id": str(request.get("id", "") or ""),
                        "code": "handler_exception",
                        "message": f"{type(exc).__name__}: {exc}",
                    }
                )
        return 0

    async def _handle_request(self, request: dict[str, Any]) -> None:
        request_id = str(request.get("id", "") or "")
        request_type = str(request.get("type", "") or "")

        if request_type == "handshake":
            await self._handle_handshake(request_id)
            return
        if request_type == "command.run":
            await self._handle_command(request_id, request)
            return
        if request_type == "action.run":
            await self._handle_action_run(request_id, request)
            return
        if request_type == "command.graph":
            await self._handle_command_graph(request_id)
            return
        if request_type == "command.registry":
            await self._handle_command_registry(request_id)
            return
        if request_type == "intent.resolve":
            await self._handle_intent_resolve(request_id, request)
            return
        if request_type == "model.policy":
            await self._handle_model_policy(request_id, request)
            return
        if request_type == "helm.on_call.request":
            self._emit_helm_on_call_projection(request_id)
            return
        if request_type == "helm.context.request":
            await self._handle_helm_context_request(request_id, request)
            return
        if request_type == "operator.snapshot":
            await self._handle_operator_snapshot(request_id)
            return
        if request_type == "agent.routes":
            await self._handle_agent_routes(request_id)
            return
        if request_type == "evolution.surface":
            await self._handle_evolution_surface(request_id)
            return
        if request_type == "session.bootstrap":
            await self._handle_session_bootstrap(request_id, request)
            return
        if request_type == "session.start":
            self._launch_session_start(request_id, request)
            return
        if request_type == "session.catalog":
            await self._handle_session_catalog(request_id, request)
            return
        if request_type == "session.detail":
            await self._handle_session_detail(request_id, request)
            return
        if request_type == "session.cancel":
            await self._handle_session_cancel(request_id, request)
            return
        if request_type == "status":
            self._emit(
                {
                    "type": "status.result",
                    "request_id": request_id,
                    "active_session_id": self._active_session_id,
                    "active_provider": self._active_provider_id,
                    "active_request_id": self._active_run.request_id if self._active_run else None,
                    "active_phase": self._active_run.phase if self._active_run else None,
                    "providers": sorted(self._adapters),
                }
            )
            return
        if request_type == "workspace.snapshot":
            await self._handle_workspace_snapshot(request_id)
            return
        if request_type == "ontology.snapshot":
            await self._handle_ontology_snapshot(request_id)
            return
        if request_type == "runtime.snapshot":
            await self._handle_runtime_snapshot(request_id)
            return
        if request_type == "permission.history":
            await self._handle_permission_history(request_id, request)
            return

        self._emit(
            {
                "type": "bridge.error",
                "request_id": request_id,
                "code": "unknown_request_type",
                "message": request_type or "missing request type",
            }
        )

    async def _handle_handshake(self, request_id: str) -> None:
        providers: list[dict[str, Any]] = []
        adapter_error = self._adapter_boot_error
        default_provider, default_model = self._terminal_default_route()
        policy = self._build_model_policy_summary(
            selected_provider=default_provider,
            selected_model=default_model,
            strategy="responsive",
        )
        selected_provider = str(policy.get("selected_provider", ""))
        selected_model = str(policy.get("selected_model", ""))
        policy_targets = [
            target for target in policy.get("targets", []) if isinstance(target, dict)
        ]
        if adapter_error is None:
            for provider_id, adapter in self._adapters.items():
                models = []
                for profile in await adapter.list_models():
                    models.append(
                        {
                            "id": profile.model_id,
                            "display_name": profile.display_name,
                            "capabilities": sorted(cap.name.lower() for cap in type(profile.capabilities) if profile.supports(cap)),
                        }
                    )
                known_model_ids = {str(model.get("id", "")) for model in models}
                for target in policy_targets:
                    if str(target.get("provider", "")) != provider_id:
                        continue
                    model_id = str(target.get("model", ""))
                    if not model_id or model_id in known_model_ids:
                        continue
                    models.append(
                        {
                            "id": model_id,
                            "display_name": str(target.get("label", model_id)),
                            "capabilities": [],
                        }
                    )
                    known_model_ids.add(model_id)
                provider_default = next(
                    (
                        str(target.get("model", ""))
                        for target in policy_targets
                        if str(target.get("provider", "")) == provider_id
                        and bool(target.get("selectable"))
                    ),
                    str(adapter.get_profile(None).model_id),
                )
                if provider_id == selected_provider:
                    provider_default = selected_model
                providers.append(
                    {
                        "provider_id": provider_id,
                        "default_model": provider_default,
                        "models": models,
                    }
                )
        self._selected_provider_id = selected_provider or None
        self._selected_model_id = selected_model or None
        self._emit(
            {
                "type": "handshake.result",
                "request_id": request_id,
                "providers": providers,
                "default_provider": selected_provider,
                "default_model": selected_model,
                "legacy_terminal": {
                    "stack": "python-textual",
                    "replacement_target": "bun-ink",
                },
                # Adapter inventory proves transport shape only. Ship the
                # independently typed route policy in the same handshake so a
                # connected bridge can never be rendered as a provider-ready
                # claim before model.policy refresh completes.
                "payload": build_routing_decision_payload(policy),
                "policy": policy,
                "adapter_boot_error": adapter_error,
            }
        )

    async def _handle_workspace_snapshot(self, request_id: str) -> None:
        summary = await asyncio.to_thread(self._load_repo_xray)
        git_summary = await asyncio.to_thread(self._build_git_summary)
        topology = await asyncio.to_thread(build_workspace_topology, self._repo_root.parent)
        payload = build_workspace_snapshot_payload(
            repo_root=str(self._repo_root),
            git_summary=git_summary,
            topology=topology,
            summary=summary,
        )
        self._emit_payload_result(
            "workspace.snapshot.result",
            request_id=request_id,
            payload=payload,
        )

    async def _handle_ontology_snapshot(self, request_id: str) -> None:
        content = await asyncio.to_thread(self._build_ontology_snapshot)
        self._emit(
            {
                "type": "ontology.snapshot.result",
                "request_id": request_id,
                "content": content,
            }
        )

    async def _handle_runtime_snapshot(self, request_id: str) -> None:
        operator_snapshot = await self._build_operator_snapshot()
        runtime_payload = build_runtime_snapshot_payload(
            operator_snapshot,
            repo_root=str(self._repo_root),
            bridge_status="connected",
            supervisor_preview=load_terminal_control_state(self._repo_root),
        )
        self._emit_payload_result(
            "runtime.snapshot.result",
            request_id=request_id,
            payload=runtime_payload,
        )

    async def _handle_permission_history(self, request_id: str, request: dict[str, Any]) -> None:
        limit = int(request.get("limit", 50) or 50)
        payload = await asyncio.to_thread(build_permission_history_payload, self._session_store, limit=limit)
        self._emit_payload_result(
            "permission.history.result",
            request_id=request_id,
            payload=payload,
        )

    async def _handle_command(
        self,
        request_id: str,
        request: dict[str, Any],
    ) -> dict[str, Any]:
        supplied_command = request.get("command")
        raw_command = _validated_command_envelope(supplied_command)
        if raw_command is None:
            result = {
                "type": "command.result",
                "request_id": request_id,
                "command": supplied_command if isinstance(supplied_command, str) else "",
                "target_pane": "control",
                "output": "Command rejected: command.run requires one exact command line.",
                "action": None,
                "outcome": "failed",
                "ok": False,
                "supported": False,
                "completed": False,
            }
            self._emit(result)
            return result
        if self._commands is None:
            result = {
                "type": "command.result",
                "request_id": request_id,
                "command": raw_command,
                "target_pane": self._command_target_pane(raw_command),
                "output": "System commands unavailable (terminal_commands not installed)",
                "action": None,
                "outcome": "failed",
                "ok": False,
                "supported": False,
                "completed": False,
            }
            self._emit(result)
            return result
        try:
            output, action, outcome = self._evaluate_command(raw_command)
            result = {
                "type": "command.result",
                "request_id": request_id,
                "command": raw_command,
                "target_pane": self._command_target_pane(raw_command),
                "output": output,
                "action": action,
                "outcome": outcome,
                "ok": outcome == "completed",
                "supported": _is_registered_command(raw_command)
                and outcome != "unsupported",
                "completed": outcome == "completed",
            }
        except Exception as exc:
            result = {
                "type": "command.result",
                "request_id": request_id,
                **self._failed_command_fields(raw_command, exc),
            }
        self._emit(result)
        return result

    async def _handle_action_run(self, request_id: str, request: dict[str, Any]) -> None:
        action_type = str(request.get("action_type", "") or "").strip().lower()
        result = await asyncio.to_thread(self._run_action, action_type, request)
        if action_type == "model.set" and not bool(result.get("ok")):
            # A failed route switch must render in the conversation, not just
            # in the models pane: the assistant wire shape (F-173) lands on
            # the open chat turn.
            self._emit(
                {
                    "type": "assistant",
                    "request_id": request_id,
                    "message": f"✖ {result.get('summary', 'route change failed')}. {result.get('output', '')}".strip(),
                }
            )
        result.update(
            {
                "type": "action.result",
                "request_id": request_id,
                "action_type": action_type,
            }
        )
        self._emit(result)

    async def _handle_intent_resolve(self, request_id: str, request: dict[str, Any]) -> None:
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
            return
        intent = await asyncio.to_thread(self._resolve_prompt_intent, prompt)
        self._emit(
            {
                "type": "intent.result",
                "request_id": request_id,
                "intent": intent,
            }
        )

    async def _handle_command_graph(self, request_id: str) -> None:
        graph = await asyncio.to_thread(self._build_command_graph_summary)
        self._emit(
            {
                "type": "command.graph.result",
                "request_id": request_id,
                "graph": graph,
                "content": self._render_command_graph_text(graph),
            }
        )

    async def _handle_command_registry(self, request_id: str) -> None:
        registry = await asyncio.to_thread(self._build_command_registry)
        self._emit(
            {
                "type": "command.registry.result",
                "request_id": request_id,
                "registry": registry,
                "content": self._render_command_registry_text(registry),
            }
        )

    async def _handle_operator_snapshot(self, request_id: str) -> None:
        snapshot = await self._build_operator_snapshot()
        self._emit(
            {
                "type": "operator.snapshot.result",
                "request_id": request_id,
                "snapshot": snapshot,
                "content": self._render_operator_snapshot_text(snapshot),
            }
        )

    async def _handle_model_policy(self, request_id: str, request: dict[str, Any]) -> None:
        default_provider, default_model = self._terminal_default_route()
        selected_provider = str(request.get("provider", "") or default_provider).strip().lower()
        selected_model = str(request.get("model", "") or "").strip() or default_model
        strategy = model_routing.resolve_strategy(str(request.get("strategy", "") or "")) or "responsive"
        policy = await asyncio.to_thread(
            self._build_model_policy_summary,
            selected_provider=selected_provider,
            selected_model=selected_model,
            strategy=strategy,
        )
        self._emit_payload_result(
            "model.policy.result",
            request_id=request_id,
            payload=build_routing_decision_payload(policy),
            policy=policy,
        )

    async def _handle_agent_routes(self, request_id: str) -> None:
        routes = await asyncio.to_thread(self._build_agent_routes)
        self._emit_payload_result(
            "agent.routes.result",
            request_id=request_id,
            payload=build_agent_routes_payload(routes),
            routes=routes,
        )

    async def _handle_evolution_surface(self, request_id: str) -> None:
        surface = await asyncio.to_thread(self._build_evolution_surface)
        self._emit(
            {
                "type": "evolution.surface.result",
                "request_id": request_id,
                "surface": surface,
                "content": self._render_evolution_surface_text(surface),
            }
        )

    async def _handle_session_bootstrap(self, request_id: str, request: dict[str, Any]) -> None:
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
            return
        payload = await asyncio.to_thread(self._build_session_bootstrap, request)
        payload.update(
            {
                "type": "session.bootstrap.result",
                "request_id": request_id,
            }
        )
        self._emit(payload)

    def _navigator_manifest(self) -> str:
        # The agent drives the Helm by emitting directives in its reply. The TS
        # parses them, executes the VIEW action, strips the sentinel, narrates.
        return (
            "NAVIGATOR — you can DRIVE this cockpit for the operator, who is watching live. "
            "To act, put a directive on its own at the start of a line: ⟦helm:VERB ARG⟧. "
            "Verbs: ⟦helm:open PANE⟧ where PANE is one of "
            "chat|mission|repo|commands|models|ontology|runtime|sessions|approvals|control|agents|evolution; "
            "⟦helm:zen⟧ ⟦helm:cockpit⟧ ⟦helm:scroll⟧ to change the face; "
            "⟦helm:dock⟧ / ⟦helm:undock⟧ for the chat rail; "
            "⟦helm:model ALIAS⟧ to switch the route. "
            "NARRATE-THEN-ACT: before a directive, say in one plain sentence what you are about to show and why; after, tell them how to undo it. "
            "Never move two surfaces in one turn without naming both. "
            "You may NOT resolve approvals or run evolution — narrate a refusal and point at /approval. "
            "The operator steers in plain language; you are the hands, they are the eyes and the judge."
        )

    async def _handle_session_catalog(self, request_id: str, request: dict[str, Any]) -> None:
        # The Helm is a workspace control surface. A missing filter must mean
        # "this workspace", never the operator's entire global session store.
        cwd = str(request.get("cwd", "") or "").strip() or str(self._repo_root)
        limit = int(request.get("limit", 20) or 20)
        catalog = await asyncio.to_thread(
            build_session_catalog,
            self._session_store,
            cwd=cwd,
            limit=limit,
        )
        self._emit_payload_result(
            "session.catalog.result",
            request_id=request_id,
            payload=catalog,
        )

    async def _handle_session_detail(self, request_id: str, request: dict[str, Any]) -> None:
        session_id = str(request.get("session_id", "") or "").strip()
        if not session_id:
            self._emit(
                {
                    "type": "bridge.error",
                    "request_id": request_id,
                    "code": "missing_session_id",
                    "message": "session.detail requires a session_id",
                }
            )
            return
        try:
            detail = await asyncio.to_thread(
                build_session_detail,
                self._session_store,
                session_id,
                transcript_limit=int(request.get("transcript_limit", 80) or 80),
            )
        except Exception as exc:
            self._emit(
                {
                    "type": "bridge.error",
                    "request_id": request_id,
                    "code": "session_detail_failed",
                    "message": f"{type(exc).__name__}: {exc}",
                }
            )
            return
        self._emit_payload_result(
            "session.detail.result",
            request_id=request_id,
            payload=detail,
            session_id=session_id,
        )

    async def _handle_session_cancel(
        self,
        request_id: str,
        request: dict[str, Any],
    ) -> None:
        target_request_id = str(request.get("target_request_id", "") or "").strip()
        active = self._active_run
        if not target_request_id:
            self._emit_cancel_ack(
                request_id=request_id,
                target_request_id="",
                cancelled=False,
                reason="missing_target_request_id",
                active=active,
            )
            return
        if active is None:
            reason = (
                "stale"
                if target_request_id in self._completed_session_request_ids
                else "idle"
            )
            self._emit_cancel_ack(
                request_id=request_id,
                target_request_id=target_request_id,
                cancelled=False,
                reason=reason,
                active=None,
            )
            return
        if target_request_id != active.request_id:
            self._emit_cancel_ack(
                request_id=request_id,
                target_request_id=target_request_id,
                cancelled=False,
                reason="target_mismatch",
                active=active,
            )
            return
        if active.terminal_emitted or active.phase in {"finalizing", "complete"}:
            self._emit_cancel_ack(
                request_id=request_id,
                target_request_id=target_request_id,
                cancelled=False,
                reason="stale",
                active=active,
            )
            return
        if active.cancel_requested:
            self._emit_cancel_ack(
                request_id=request_id,
                target_request_id=target_request_id,
                cancelled=False,
                reason="already_cancelling",
                active=active,
            )
            return

        target_phase = active.phase
        active.cancel_request_id = request_id
        cancel_error = await self._cancel_active_run(active, reason="cancelled_by_operator")
        self._emit_cancel_ack(
            request_id=request_id,
            target_request_id=target_request_id,
            cancelled=True,
            reason="cancel_requested",
            active=active,
            target_phase=target_phase,
            provider_cancel_error=cancel_error,
        )

    async def _cancel_active_run(
        self,
        run: _ActiveSessionRun,
        *,
        reason: str,
    ) -> str | None:
        run.cancel_requested = True
        run.cancel_reason = reason
        run.phase = "cancelling"
        provider_cancel_error: str | None = None
        adapter = self._adapters.get(run.provider_id)
        if adapter is not None:
            try:
                await adapter.cancel()
            except Exception:
                provider_cancel_error = "provider_cancel_failed"

        task = run.task
        if task is not None and task is not asyncio.current_task() and not task.done():
            task.cancel()
        if task is not None and task is not asyncio.current_task():
            await asyncio.gather(task, return_exceptions=True)
        return provider_cancel_error

    def _set_active_run(self, run: _ActiveSessionRun) -> None:
        self._active_run = run
        self._active_session_id = run.session_id
        self._active_provider_id = run.provider_id
        self._active_model_id = run.model_id
        self._selected_provider_id = run.provider_id
        self._selected_model_id = run.model_id

    def _set_active_provider(
        self,
        run: _ActiveSessionRun,
        provider_id: str,
        model_id: str,
        *,
        update_selection: bool = False,
    ) -> None:
        run.lifecycle.bind_route(provider_id=provider_id, model_id=model_id)
        run.provider_id = provider_id
        run.model_id = model_id
        if self._active_run is run:
            self._active_provider_id = provider_id
            self._active_model_id = model_id
            if update_selection:
                self._selected_provider_id = provider_id
                self._selected_model_id = model_id

    def _clear_active_run(self, run: _ActiveSessionRun) -> None:
        if self._active_run is not run:
            return
        self._active_run = None
        self._active_session_id = None
        self._active_provider_id = None
        self._active_model_id = None

    def _mark_terminal_emitted(self, run: _ActiveSessionRun) -> None:
        run.phase = "finalizing"
        run.terminal_emitted = True

    def _emit_cancelled_terminal(self, run: _ActiveSessionRun) -> None:
        if run.terminal_emitted:
            return
        run.phase = "finalizing"
        error_message = (
            "bridge closed"
            if run.cancel_reason == "bridge_closed"
            else "cancelled by operator"
        )
        try:
            terminal = run.lifecycle.cancel(error_message)
        except Exception as exc:
            self._emit(
                {
                    "type": "bridge.error",
                    "request_id": run.request_id,
                    "code": "session_persistence_failed",
                    "message": f"{type(exc).__name__}: {exc}",
                }
            )
            terminal = run.lifecycle.terminal_event
        if terminal is not None and not run.terminal_emitted:
            self._mark_terminal_emitted(run)
            self._emit(
                {
                    "type": "session_end",
                    "request_id": run.request_id,
                    "session_id": terminal.session_id,
                    "provider_id": terminal.provider_id or run.provider_id,
                    "success": False,
                    "cancelled": True,
                    "error_code": "cancelled",
                    "error_message": terminal.error_message or error_message,
                }
            )

    def _emit_cancel_ack(
        self,
        *,
        request_id: str,
        target_request_id: str,
        cancelled: bool,
        reason: str,
        active: _ActiveSessionRun | None,
        target_phase: str | None = None,
        provider_cancel_error: str | None = None,
    ) -> None:
        payload: dict[str, Any] = {
            "type": "session.cancelled",
            "request_id": request_id,
            "target_request_id": target_request_id,
            "cancelled": cancelled,
            "reason": reason,
            "session_id": active.session_id if active is not None else None,
            "provider": active.provider_id if active is not None else None,
        }
        if active is not None:
            payload.update(
                {
                    "active_request_id": active.request_id,
                    "active_phase": active.phase,
                }
            )
        if target_phase is not None:
            payload["target_phase"] = target_phase
        if provider_cancel_error is not None:
            payload["provider_cancel_error"] = provider_cancel_error
        self._emit(payload)

    def _remember_completed_session_request(self, request_id: str) -> None:
        if not request_id:
            return
        self._completed_session_request_ids = [
            item for item in self._completed_session_request_ids if item != request_id
        ]
        self._completed_session_request_ids.append(request_id)
        self._completed_session_request_ids = self._completed_session_request_ids[-64:]

    def _emit(self, payload: dict[str, Any]) -> None:
        sys.stdout.write(json.dumps(payload, default=_json_default) + "\n")
        sys.stdout.flush()

    def _emit_payload_result(
        self,
        event_type: str,
        *,
        request_id: str,
        payload: dict[str, Any],
        content: str | None = None,
        **extra: Any,
    ) -> None:
        event: dict[str, Any] = {
            "type": event_type,
            "request_id": request_id,
            "payload": payload,
        }
        if content is not None:
            event["content"] = content
        if extra:
            event.update(extra)
        self._emit(event)

    def _emit_permission_decision(self, request_id: str, event: ToolCallComplete) -> None:
        payload = build_permission_decision_payload(event)
        if payload.get("decision") == "allow" and not bool(payload.get("requires_confirmation")):
            return
        self._record_permission_payload(payload)
        self._emit_payload_result("permission.decision", request_id=request_id, payload=payload)

    def _record_permission_payload(self, payload: dict[str, Any]) -> None:
        metadata = payload.get("metadata")
        metadata_record = metadata if isinstance(metadata, dict) else {}
        session_id = str(metadata_record.get("session_id", "") or "").strip()
        if not session_id:
            return
        created_at = str(payload.get("resolved_at", "") or datetime.now(timezone.utc).isoformat())
        domain = str(payload.get("domain", "") or "")
        if domain == "permission_decision":
            self._append_permission_event(
                session_id,
                PermissionDecisionEvent(
                    session_id=session_id,
                    provider_id=str(metadata_record.get("provider_id", "") or ""),
                    action_id=str(payload.get("action_id", "") or ""),
                    tool_name=str(payload.get("tool_name", "") or ""),
                    risk=str(payload.get("risk", "") or ""),
                    decision=str(payload.get("decision", "") or ""),
                    rationale=str(payload.get("rationale", "") or ""),
                    policy_source=str(payload.get("policy_source", "") or ""),
                    requires_confirmation=bool(payload.get("requires_confirmation")),
                    command_prefix=str(payload.get("command_prefix", "") or "") or None,
                    metadata=dict(metadata_record),
                ),
            )
            return
        if domain == "permission_resolution":
            self._append_permission_event(
                session_id,
                PermissionResolutionEvent(
                    session_id=session_id,
                    provider_id=str(metadata_record.get("provider_id", "") or ""),
                    action_id=str(payload.get("action_id", "") or ""),
                    resolution=str(payload.get("resolution", "") or ""),
                    resolved_at=created_at,
                    actor=str(payload.get("actor", "") or "operator"),
                    summary=str(payload.get("summary", "") or ""),
                    note=str(payload.get("note", "") or "") or None,
                    enforcement_state=str(payload.get("enforcement_state", "") or "recorded_only"),
                    metadata=dict(metadata_record),
                ),
            )
            return
        if domain == "permission_outcome":
            self._append_permission_event(
                session_id,
                PermissionOutcomeEvent(
                    session_id=session_id,
                    provider_id=str(metadata_record.get("provider_id", "") or ""),
                    action_id=str(payload.get("action_id", "") or ""),
                    outcome=str(payload.get("outcome", "") or ""),
                    outcome_at=str(payload.get("outcome_at", "") or created_at),
                    source=str(payload.get("source", "") or "runtime"),
                    summary=str(payload.get("summary", "") or ""),
                    metadata=dict(metadata_record),
                ),
            )
            return

    def _append_permission_event(self, session_id: str, event: Any) -> None:
        try:
            self._session_store.append_event(session_id, event)
        except FileNotFoundError:
            return

    def _build_workspace_snapshot(self) -> str:
        summary = self._load_repo_xray()
        topology = build_workspace_topology(self._repo_root.parent)
        git_summary = self._build_git_summary()
        return self._build_workspace_snapshot_from_parts(summary, git_summary, topology)

    def _build_workspace_snapshot_from_parts(
        self,
        summary: Any | None,
        git_summary: dict[str, Any],
        topology: dict[str, Any],
    ) -> str:
        git_summary_lines = self._render_git_summary_lines(git_summary)
        if summary is None:
            return "\n".join(
                [
                    "# Workspace",
                    f"Repo root: {self._repo_root}",
                    *git_summary_lines,
                    "Repo x-ray unavailable",
                ]
            )

        top_files = summary.largest_python_files[:5]
        top_imports = summary.most_imported_modules[:5]
        lines = [
            "# Workspace X-Ray",
            f"Repo root: {summary.repo_root}",
            *git_summary_lines,
            f"Python modules: {summary.python_modules}",
            f"Python tests: {summary.python_tests}",
            f"Scripts: {summary.shell_scripts}",
            f"Docs: {summary.markdown_docs}",
            f"Workflows: {len(summary.workflows)}",
            "",
            "## Topology",
        ]
        for warning in topology.get("warnings", [])[:5]:
            lines.append(f"- warning: {warning}")
        dgc = topology.get("dgc", {})
        for repo in dgc.get("repos", [])[:4]:
            lines.append(
                "- {name} | role {role} | branch {branch} | dirty {dirty} | modified {modified} | untracked {untracked}".format(
                    name=repo.get("name", "repo"),
                    role=repo.get("role", "unknown"),
                    branch=repo.get("branch") or "n/a",
                    dirty=repo.get("dirty"),
                    modified=repo.get("modified_count", 0),
                    untracked=repo.get("untracked_count", 0),
                )
            )
        lines.extend(
            [
                "",
                "## Language mix",
            ]
        )
        for suffix, count in list(summary.language_mix.items())[:8]:
            lines.append(f"- {suffix}: {count}")
        lines.extend(["", "## Largest Python files"])
        for item in top_files:
            lines.append(f"- {item.path} | {item.lines} lines | defs {item.defs} | imports {item.imports}")
        lines.extend(["", "## Most imported local modules"])
        for item in top_imports:
            lines.append(f"- {item.module} | inbound {item.count}")
        return "\n".join(lines)

    def _build_git_summary(self) -> dict[str, Any]:
        try:
            branch = subprocess.run(
                ["git", "--no-optional-locks", "-C", str(self._repo_root), "branch", "--show-current"],
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            ).stdout.strip() or "(detached)"
            head = subprocess.run(
                ["git", "--no-optional-locks", "-C", str(self._repo_root), "rev-parse", "--short", "HEAD"],
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            ).stdout.strip() or "unknown"
            porcelain = subprocess.run(
                ["git", "--no-optional-locks", "-C", str(self._repo_root), "status", "--porcelain"],
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            ).stdout
            upstream_process = subprocess.run(
                ["git", "--no-optional-locks", "-C", str(self._repo_root), "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{upstream}"],
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )
        except Exception as exc:
            return {
                "branch": "unavailable",
                "head": "unknown",
                "staged": None,
                "unstaged": None,
                "untracked": None,
                "changed_hotspots": [],
                "changed_paths": [],
                "sync_summary": f"unavailable ({type(exc).__name__}: {exc})",
                "sync_status": "unavailable",
                "upstream": None,
                "ahead": None,
                "behind": None,
            }

        staged = 0
        unstaged = 0
        untracked = 0
        changed_areas: dict[str, int] = {}
        changed_paths: list[str] = []
        for line in porcelain.splitlines():
            if len(line) < 2:
                continue
            x = line[0]
            y = line[1]
            path_text = line[3:].strip() if len(line) > 3 else ""
            if " -> " in path_text:
                path_text = path_text.split(" -> ")[-1].strip()
            if path_text:
                area = path_text.split("/", 1)[0] or "."
                changed_areas[area] = changed_areas.get(area, 0) + 1
                changed_paths.append(path_text)
            if x == "?" and y == "?":
                untracked += 1
                continue
            if x not in {" ", "?"}:
                staged += 1
            if y != " ":
                unstaged += 1
        hotspots = [
            {"name": name, "count": count}
            for name, count in sorted(changed_areas.items(), key=lambda item: (-item[1], item[0]))[:4]
        ]
        unique_paths = sorted(set(changed_paths), key=lambda value: (-(changed_areas.get(value.split("/", 1)[0] or ".", 0)), value))[:5]

        if branch == "(detached)":
            return {
                "branch": branch,
                "head": head,
                "staged": staged,
                "unstaged": unstaged,
                "untracked": untracked,
                "changed_hotspots": hotspots,
                "changed_paths": unique_paths,
                "sync_summary": "detached HEAD",
                "sync_status": "detached",
                "upstream": "detached HEAD",
                "ahead": None,
                "behind": None,
            }

        upstream = upstream_process.stdout.strip()
        if upstream_process.returncode != 0 or not upstream:
            return {
                "branch": branch,
                "head": head,
                "staged": staged,
                "unstaged": unstaged,
                "untracked": untracked,
                "changed_hotspots": hotspots,
                "changed_paths": unique_paths,
                "sync_summary": "no upstream configured",
                "sync_status": "no_upstream",
                "upstream": None,
                "ahead": None,
                "behind": None,
            }

        try:
            ahead_behind = subprocess.run(
                ["git", "--no-optional-locks", "-C", str(self._repo_root), "rev-list", "--left-right", "--count", f"HEAD...{upstream}"],
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            ).stdout.strip()
            ahead_text, behind_text = ahead_behind.split()
            ahead = int(ahead_text)
            behind = int(behind_text)
            sync_summary = f"{upstream} | ahead {ahead} | behind {behind}"
        except Exception:
            ahead = None
            behind = None
            sync_summary = f"{upstream} | ahead/behind unavailable"
        return {
            "branch": branch,
            "head": head,
            "staged": staged,
            "unstaged": unstaged,
            "untracked": untracked,
            "changed_hotspots": hotspots,
            "changed_paths": unique_paths,
            "sync_summary": sync_summary,
            "sync_status": "tracking",
            "upstream": upstream,
            "ahead": ahead,
            "behind": behind,
        }

    def _render_git_summary_lines(self, git_summary: dict[str, Any]) -> list[str]:
        return render_git_summary_lines(git_summary)

    def _build_ontology_snapshot(self) -> str:
        concepts_path = self._package_root / "dharma_concepts.json"
        try:
            payload = json.loads(concepts_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            return "\n".join(
                [
                    "# Ontology",
                    f"Seed concepts unavailable: {type(exc).__name__}: {exc}",
                ]
            )

        concepts = payload.get("concepts", [])
        if not isinstance(concepts, list):
            concepts = []
        top_concepts = sorted(
            [concept for concept in concepts if isinstance(concept, dict)],
            key=lambda item: int(item.get("codebase_frequency", 0) or 0),
            reverse=True,
        )[:6]
        lines = [
            "# Ontology Surface",
            f"Version: {payload.get('version', 'unknown')}",
            f"Generated: {payload.get('generated', 'unknown')}",
            f"Concept count: {len(concepts)}",
            "",
            "## Dominant concepts",
        ]
        for concept in top_concepts:
            related = concept.get("related_concepts", [])
            related_text = ", ".join(str(item) for item in related[:4]) if isinstance(related, list) else ""
            lines.append(
                "- {name} | freq {freq} | files {files} | {domain}".format(
                    name=concept.get("canonical_name", concept.get("id", "concept")),
                    freq=concept.get("codebase_frequency", 0),
                    files=concept.get("codebase_files", 0),
                    domain=concept.get("domain", "unknown"),
                )
            )
            if related_text:
                lines.append(f"  related: {related_text}")
        lines.extend(
            [
                "",
                "## Identity",
                "The terminal should present DHARMA SWARM as a repo with concepts, gates, stigmergic traces, and runtime state.",
                "Chat is only one pane in that system, not the system itself.",
            ]
        )
        return "\n".join(lines)

    def _build_runtime_snapshot(self) -> str:
        runtime_text = build_runtime_status_text(limit=5)
        normalized = runtime_text.replace("[bold #9C7444]", "").replace("[/bold #9C7444]", "")
        normalized = normalized.replace("[#9C7444]", "").replace("[/#9C7444]", "")
        normalized = normalized.replace("[dim]", "").replace("[/dim]", "")
        terminal_control = load_terminal_control_state(self._repo_root)
        if terminal_control:
            terminal_lines = [
                f"Active task: {terminal_control.get('active_task_id', 'none') or 'none'}",
                f"Loop decision: {terminal_control.get('loop_decision', 'unknown') or 'unknown'}",
                f"Verification status: {terminal_control.get('verification_status', 'unknown') or 'unknown'}",
                f"Next task: {terminal_control.get('next_task', 'none') or 'none'}",
                f"Updated: {terminal_control.get('updated_at', 'unknown') or 'unknown'}",
            ]
            normalized = "\n".join([normalized.rstrip(), "", "--- Terminal Control ---", *terminal_lines])
        return normalized

    def _build_session_bootstrap(self, request: dict[str, Any]) -> dict[str, Any]:
        prompt, error_code, error_message = self._validated_request_prompt(request)
        if prompt is None:
            raise ValueError(f"{error_code}: {error_message}")
        active_tab = str(request.get("active_tab", "") or "chat")
        default_provider, default_model = self._terminal_default_route()
        selected_provider = str(
            request.get("provider", "") or default_provider
        ).strip().lower()
        selected_model = str(request.get("model", "") or "").strip()
        intent = self._resolve_prompt_intent(prompt)
        explicit_strategy = model_routing.resolve_strategy(
            str(request.get("strategy", "") or "")
        )
        if not selected_model:
            selected_provider = selected_provider or default_provider
            selected_model = default_model
        elif not selected_provider:
            selected_provider = default_provider

        workspace_snapshot = self._build_workspace_snapshot()
        ontology_snapshot = self._build_ontology_snapshot()
        runtime_snapshot = self._build_runtime_snapshot()
        repo_guidance = self._load_repo_guidance()
        session_context_hint = self._load_session_context_hint()
        working_memory = self._load_working_memory()
        workspace_preview = self._build_workspace_preview(workspace_snapshot)
        runtime_preview = self._build_runtime_preview(runtime_snapshot)
        command_graph = self._build_command_graph_summary()
        model_policy = self._build_model_policy_summary(
            selected_provider=selected_provider,
            selected_model=selected_model,
            strategy=explicit_strategy or "responsive",
        )
        selected_provider = str(model_policy.get("selected_provider", selected_provider))
        selected_model = str(model_policy.get("selected_model", selected_model))
        orientation_packet = build_orientation_packet(
            role="operator",
            claims=[],
            directives=[
                DirectiveSummary(
                    directive_id="terminal-v3",
                    title="Repo-native operator turn",
                    summary="Ground every turn in repo topology, ontology, runtime truth, and model policy.",
                    source_ref="terminal_v3_spec",
                    priority="high",
                )
            ],
            runtime_state=RuntimeStateSummary(
                mode="terminal",
                active_tasks=0,
                running_agents=0,
                pending_tasks=0,
                status_notes=[
                    f"active_tab={active_tab}",
                    f"selected_provider={selected_provider}",
                    f"selected_model={selected_model}",
                    f"intent={intent.get('kind', 'chat')}",
                ],
            ),
            role_context=(
                "You are operating inside the Dharma terminal. Prefer repo-native commands and operator actions when "
                "they satisfy the user's request more directly than generic prose."
            ),
            task=prompt,
            provenance=["workspace.snapshot", "ontology.snapshot", "runtime.snapshot", "terminal.model_policy"],
        )
        route = f"{selected_provider}:{selected_model}"
        if intent.get("kind") != "chat":
            working_memory = self._apply_turn_to_memory(
                working_memory,
                prompt=prompt,
                intent=intent,
                route=route,
                active_tab=active_tab,
            )
        rendered_working_memory = self._render_working_memory(working_memory)
        system_prompt = self._render_system_prompt(
            prompt=prompt,
            active_tab=active_tab,
            intent=intent,
            selected_provider=selected_provider,
            selected_model=selected_model,
            routing_strategy=explicit_strategy or "responsive",
            command_graph=command_graph,
            model_policy=model_policy,
            orientation_packet=orientation_packet.model_dump(mode="json"),
            workspace_snapshot=workspace_snapshot,
            ontology_snapshot=ontology_snapshot,
            runtime_snapshot=runtime_snapshot,
            repo_guidance=repo_guidance,
            session_context_hint=session_context_hint,
            working_memory=rendered_working_memory,
        )
        if intent.get("kind") != "chat":
            self._save_working_memory(working_memory)
        return {
            "prompt": prompt,
            "active_tab": active_tab,
            "intent": intent,
            "selected_provider": selected_provider,
            "selected_model": selected_model,
            "routing_strategy": explicit_strategy or "responsive",
            "command_graph": command_graph,
            "model_policy": model_policy,
            "orientation_packet": orientation_packet.model_dump(mode="json"),
            "workspace_preview": workspace_preview,
            "runtime_preview": runtime_preview,
            "workspace_snapshot": workspace_snapshot,
            "ontology_snapshot": ontology_snapshot,
            "runtime_snapshot": runtime_snapshot,
            "repo_guidance": repo_guidance,
            "session_context_hint": session_context_hint,
            "working_memory": rendered_working_memory,
            "system_prompt": system_prompt,
        }

    def _build_command_graph_summary(self) -> dict[str, Any]:
        commands = sorted(system_commands_module._ALL_COMMANDS)
        async_commands = sorted(system_commands_module._ASYNC_COMMANDS)
        categories = {
            "chat": sorted(["chat", "clear", "reset", "cancel", "paste", "copy", "copylast", "thread"]),
            "repo": sorted(["git"]),
            "runtime": sorted(["runtime"]),
            "control": sorted(["status", "health", "pulse", "self"]),
            "ontology": sorted(["context", "foundations", "telos", "dharma", "corpus", "evidence"]),
            "memory": sorted(["memory", "notes", "archive", "darwin", "logs", "truth", "stigmergy"]),
            "swarm": sorted(["swarm", "agni", "gates", "witness", "hum"]),
        }
        return {
            "count": len(commands),
            "async_count": len(async_commands),
            "commands": commands,
            "async_commands": async_commands,
            "categories": categories,
        }

    def _build_command_registry(self) -> dict[str, Any]:
        descriptions = {
            "status": "Full system status panel",
            "health": "Ecosystem health check",
            "pulse": "Run heartbeat",
            "self": "System self-map",
            "context": "Show agent context layers",
            "memory": "Strange loop memory and latent gold",
            "notes": "Shared agent notes",
            "archive": "Evolution archive",
            "darwin": "Darwin experiment memory and trust ladder",
            "swarm": "Swarm operations and report lanes",
            "gates": "Test telos gates",
            "evolve": "Darwin Engine evolution",
            "runtime": "Live process and runtime matrix",
            "git": "Repo branch/head/dirty counts",
            "foundations": "Foundational pillars",
            "telos": "Telos Engine research docs",
            "thread": "Show or set research thread",
            "plan": "Plan-mode control",
            "model": "Model routing control",
            "chat": "Native chat continuation control",
        }
        categories = self._build_command_graph_summary()["categories"]
        records = []
        for name in sorted(system_commands_module._ALL_COMMANDS):
            target_pane = "control"
            for category_name, commands in categories.items():
                if name in commands:
                    if category_name == "repo":
                        target_pane = "repo"
                    elif category_name == "runtime":
                        target_pane = "runtime"
                    elif category_name == "ontology":
                        target_pane = "ontology"
                    elif category_name == "memory":
                        target_pane = "sessions"
                    elif category_name == "swarm":
                        target_pane = "agents"
                    elif category_name == "chat":
                        target_pane = "chat"
            records.append(
                {
                    "name": name,
                    "async": name in system_commands_module._ASYNC_COMMANDS,
                    "category": next((category for category, commands in categories.items() if name in commands), "control"),
                    "target_pane": target_pane,
                    "description": descriptions.get(name, "Dharma operator command"),
                }
            )
        return {
            "count": len(records),
            "commands": records,
        }

    async def _build_operator_snapshot(self) -> dict[str, Any]:
        runtime_state = RuntimeStateStore(db_path=DEFAULT_RUNTIME_DB)
        views = OperatorViews(runtime_state)
        try:
            overview = await views.runtime_overview()
            runs = await views.active_runs(limit=8)
            actions = await views.recent_operator_actions(limit=8)
        except Exception as exc:
            return {
                "runtime_db": str(DEFAULT_RUNTIME_DB),
                "error": f"{type(exc).__name__}: {exc}",
                "overview": {},
                "runs": [],
                "actions": [],
            }
        return {
            "runtime_db": str(runtime_state.db_path),
            "overview": {
                "sessions": overview.sessions,
                "claims": overview.claims,
                "active_claims": overview.active_claims,
                "acknowledged_claims": overview.acknowledged_claims,
                "runs": overview.runs,
                "active_runs": overview.active_runs,
                "artifacts": overview.artifacts,
                "promoted_facts": overview.promoted_facts,
                "context_bundles": overview.context_bundles,
                "operator_actions": overview.operator_actions,
            },
            "runs": [
                {
                    "run_id": run.run_id,
                    "task_id": run.task_id,
                    "assigned_to": run.assigned_to,
                    "status": run.status,
                    "current_artifact_id": run.current_artifact_id,
                    "failure_code": run.failure_code,
                    "started_at": run.started_at.isoformat(),
                }
                for run in runs
            ],
            "actions": actions,
        }

    def _build_agent_routes(self) -> dict[str, Any]:
        openclaw = self._read_openclaw_summary()
        routes = [
            {
                "intent": "fast_repo_scan",
                "provider": "claude",
                "model_alias": "haiku-4.5",
                "reasoning": "low",
                "role": "scanner",
            },
            {
                "intent": "deep_code_work",
                "provider": "codex",
                "model_alias": "codex-5.4",
                "reasoning": "high",
                "role": "builder",
            },
            {
                "intent": "architecture_research",
                "provider": "claude",
                "model_alias": "opus-4.6",
                "reasoning": "high",
                "role": "architect",
            },
            {
                "intent": "budget_parallelism",
                "provider": "ollama",
                "model_alias": "glm-5",
                "reasoning": "medium",
                "role": "swarm_worker",
            },
        ]
        return {
            "routes": routes,
            "openclaw": openclaw,
            "subagent_capabilities": [
                "route by task type",
                "select provider/model family",
                "assign reasoning effort",
                "preserve repo-native context envelope",
            ],
        }

    def _build_evolution_surface(self) -> dict[str, Any]:
        domains = []
        for name, domain in get_registered_domains().items():
            domains.append(
                {
                    "name": name,
                    "fitness_threshold": getattr(domain, "fitness_threshold", None),
                    "max_iterations": getattr(domain, "max_iterations", None),
                    "max_duration_seconds": getattr(domain, "max_duration_seconds", None),
                }
            )
        return {
            "domains": domains,
            "entry_commands": ["/cascade <domain>", "/evolve <candidate> <direction>", "/loops"],
            "principles": [
                "self-improvement should stay inspectable",
                "operator approval remains available at gate boundaries",
                "evolution updates should feed future terminal context",
            ],
        }

    def _render_system_prompt(
        self,
        *,
        prompt: str,
        active_tab: str,
        intent: dict[str, Any],
        selected_provider: str,
        selected_model: str,
        routing_strategy: str,
        command_graph: dict[str, Any],
        model_policy: dict[str, Any],
        orientation_packet: dict[str, Any],
        workspace_snapshot: str,
        ontology_snapshot: str,
        runtime_snapshot: str,
        repo_guidance: str,
        session_context_hint: str,
        working_memory: str,
    ) -> str:
        command_categories = command_graph.get("categories", {})
        command_lines = []
        for name, commands in command_categories.items():
            if isinstance(commands, list) and commands:
                command_lines.append(f"- {name}: {', '.join(str(item) for item in commands[:8])}")

        lines = [
            "# Dharma Terminal Bootstrap",
            "",
            "Identity:",
            "- You are not a detached chatbot. You are the Dharma Swarm operator intelligence speaking from inside the repo and control plane.",
            "- Treat the repo, ontology, runtime state, command graph, model policy, and swarm routes as your own appendages.",
            "- When the user asks what you can do, answer in terms of Dharma-native commands, panes, agents, models, and repo actions available right now.",
            "- If a native command, pane refresh, model switch, or operator action is the right move, prefer it over generic prose.",
            "- Your tone should feel like the system itself: specific, grounded, operational, and aware of local topology.",
            "",
            "Turn context:",
            f"- Prompt: {prompt}",
            f"- Active tab: {active_tab}",
            f"- Intent: {intent.get('kind', 'chat')}",
            f"- Selected route: {selected_provider}:{selected_model}",
            f"- Routing strategy: {routing_strategy}",
            "",
            "Model policy:",
            f"- Default route: {model_policy.get('default_route', 'unknown')}",
            f"- Strategies: {', '.join(str(item) for item in model_policy.get('strategies', []))}",
            f"- Available model targets: {', '.join(str(item.get('alias', '?')) for item in model_policy.get('targets', [])[:10])}",
            "",
            "Command graph:",
            *command_lines,
            "",
            "Behavioral rules:",
            "- If the user asks for a model change, perform the switch and explain the new route briefly.",
            "- If the user asks for status, topology, runtime, memory, agents, or evolution state, prefer the corresponding Dharma surface over generic explanation.",
            "- If the user asks who you are, answer as Dharma Swarm's operator intelligence for this repo, not as an abstract assistant.",
            "- When helpful, restate the available command or pane that matches the request.",
            "",
            "Repo guidance (always-loaded doctrine):",
            repo_guidance or "(no CLAUDE.md guidance found)",
            "",
            "Session context hint:",
            session_context_hint or "(no session context hint available)",
            "",
            "Working memory:",
            working_memory or "(no working memory yet)",
            "",
            "Orientation packet:",
            json.dumps(orientation_packet, indent=2, ensure_ascii=True),
            "",
            "Workspace snapshot:",
            workspace_snapshot,
            "",
            "Ontology snapshot:",
            ontology_snapshot,
            "",
            "Runtime snapshot:",
            runtime_snapshot,
        ]
        return "\n".join(lines)

    def _render_command_graph_text(self, graph: dict[str, Any]) -> str:
        return render_command_graph_text(graph)

    def _render_command_registry_text(self, registry: dict[str, Any]) -> str:
        return render_command_registry_text(registry)

    def _render_operator_snapshot_text(self, snapshot: dict[str, Any]) -> str:
        return render_operator_snapshot_text(snapshot)

    def _render_model_policy_text(self, policy: dict[str, Any]) -> str:
        return render_model_policy_text(policy)

    def _render_agent_routes_text(self, routes: dict[str, Any]) -> str:
        return render_agent_routes_text(routes)

    def _render_evolution_surface_text(self, surface: dict[str, Any]) -> str:
        return render_evolution_surface_text(surface)

    def _render_session_catalog_text(self, catalog: dict[str, Any]) -> str:
        return render_session_catalog_text(catalog)

    def _render_session_detail_text(self, detail: dict[str, Any]) -> str:
        return render_session_detail_text(detail)

    def _build_workspace_preview(self, content: str) -> dict[str, str]:
        return {
            "Repo root": self._find_line_value(content, "Repo root", fallback=str(self._repo_root)),
            "Branch": self._extract_git_branch(content),
            "Dirty": self._extract_git_dirty(content),
            "Repo risk": self._extract_repo_risk(content),
        }

    def _build_runtime_preview(self, content: str) -> dict[str, str]:
        return {
            "Runtime activity": self._find_prefixed_line(content, "Sessions=", fallback="none"),
            "Artifact state": self._find_prefixed_line(content, "Artifacts=", fallback="none"),
            "Verification status": self._find_line_value(content, "Verification status", fallback="unknown"),
            "Loop decision": self._find_line_value(content, "Loop decision", fallback="unknown"),
            "Next task": self._find_line_value(content, "Next task", fallback="none"),
        }

    def _find_line_value(self, content: str, label: str, *, fallback: str) -> str:
        match = re.search(rf"^{re.escape(label)}:\s*(.+)$", content, re.MULTILINE)
        return match.group(1).strip() if match else fallback

    def _find_prefixed_line(self, content: str, prefix: str, *, fallback: str) -> str:
        for line in content.splitlines():
            stripped = line.strip()
            if stripped.startswith(prefix):
                return stripped
        return fallback

    def _extract_git_branch(self, content: str) -> str:
        match = re.search(r"^Git:\s*(.+?)@", content, re.MULTILINE)
        return match.group(1).strip() if match else "unavailable"

    def _extract_git_dirty(self, content: str) -> str:
        match = re.search(
            r"^Git:\s*.+?\|\s*staged\s*(\d+)\s*\|\s*unstaged\s*(\d+)\s*\|\s*untracked\s*(\d+)$",
            content,
            re.MULTILINE,
        )
        if not match:
            return "unavailable"
        return f"{match.group(1)} staged, {match.group(2)} unstaged, {match.group(3)} untracked"

    def _extract_repo_risk(self, content: str) -> str:
        warnings = re.findall(r"^\s*-\s*warning:\s*(.+)$", content, re.MULTILINE)
        if warnings:
            return warnings[0].strip()
        dirty = self._extract_git_dirty(content)
        return "stable" if dirty == "0 staged, 0 unstaged, 0 untracked" else dirty

    def _resolve_prompt_intent(self, prompt: str) -> dict[str, Any]:
        """Classify only exact registered command forms; preserve all else."""

        if not isinstance(prompt, str) or not prompt.strip():
            raise ValueError("prompt must contain non-whitespace text")
        if "\x00" in prompt:
            raise ValueError("prompt must not contain NUL bytes")

        registered = (
            frozenset(system_commands_module._ALL_COMMANDS)
            if system_commands_module is not None
            else frozenset()
        )
        command_text = (
            _validated_command_envelope(prompt) if prompt.startswith("/") else None
        )
        if command_text is not None:
            command_name = command_text.split(None, 1)[0].lower() if command_text else ""
            if command_name in registered:
                return {
                    "kind": "command",
                    "auto_execute": True,
                    "confidence": "high",
                    "command": command_text,
                    "reason": "explicit registered slash command",
                }

        bare = prompt.strip()
        if prompt == bare and len(bare.split()) == 1 and bare.lower() in registered:
            return {
                "kind": "command",
                "auto_execute": True,
                "confidence": "high",
                "command": bare.lower(),
                "reason": "exact registered bare command",
            }

        return {
            "kind": "chat",
            "auto_execute": False,
            "confidence": "high",
            "reason": "byte-preserved conversational turn",
        }

    def _looks_like_tool_capable_work(self, lowered_prompt: str) -> bool:
        action = re.search(
            r"\b(add|analyze|build|check|debug|edit|execute|fix|grep|implement|inspect|lint|list|modify|patch|read|refactor|run|scan|search|test|typecheck|update|write)\b",
            lowered_prompt,
        )
        if action is None:
            return False
        return bool(
            re.search(
                r"(/|\.py\b|\.ts\b|\.tsx\b|\.js\b|\.jsx\b|\.json\b|\.md\b|\bbug\b|\bcode\b|\bcommand\b|\bdashboard\b|\bdiff\b|\berror\b|\bfailing\b|\bfile\b|\bfiles\b|\bgit\b|\bpytest\b|\brepo\b|\brepository\b|\bshell\b|\bterminal\b|\btest\b|\btests\b|\btool\b|\btools\b|\btui\b)",
                lowered_prompt,
            )
        )

    def _render_identity_response(self, bootstrap: dict[str, Any]) -> str:
        return render_identity_response(bootstrap, repo_root=self._repo_root)

    def _render_memory_response(self, bootstrap: dict[str, Any] | None = None) -> str:
        return render_memory_response(bootstrap)

    def _read_openclaw_summary(self) -> dict[str, Any]:
        oc_path = Path.home() / ".openclaw" / "openclaw.json"
        if not oc_path.exists():
            return {"present": False, "readable": False, "agents_count": 0, "providers": []}
        try:
            payload = json.loads(oc_path.read_text())
        except Exception:
            return {"present": True, "readable": False, "agents_count": 0, "providers": []}
        providers: list[str] = []
        models = payload.get("models", {})
        if isinstance(models, dict):
            provider_map = models.get("providers", {})
            if isinstance(provider_map, dict):
                providers = sorted(str(key) for key in provider_map.keys())
        agents_count = 0
        agents = payload.get("agents", {})
        if isinstance(agents, dict):
            listing = agents.get("list", [])
            if isinstance(listing, list):
                agents_count = len(listing)
        return {
            "present": True,
            "readable": True,
            "agents_count": agents_count,
            "providers": providers,
        }

    def _materialize_async_command(self, raw_command: str, action: str) -> str:
        command = raw_command.split(None, 1)[0].lower()
        if command in {"runtime", "status", "health", "pulse", "self"}:
            return self._build_runtime_snapshot()
        if command == "git":
            return self._build_workspace_snapshot()
        if command in {"context", "foundations", "telos", "dharma", "corpus", "evidence"}:
            return self._build_ontology_snapshot()
        if command in {"swarm", "gates", "witness", "agni", "evolve"}:
            return "\n".join(
                [
                    "# Swarm Control",
                    f"Command: /{command}",
                    "The operator bridge and runtime spine are available, but this command is not yet fully materialized in the Bun terminal.",
                    "Use the Control and Timeline panes for current runtime truth.",
                ]
            )
        if command == "memory":
            from dharma_swarm.memory_common import render_memory_common_command

            _, _, arg = raw_command.partition(" ")
            return render_memory_common_command(arg or "status", state_dir=self._state_dir)
        if command in {"archive", "truth", "stigmergy", "darwin", "hum"}:
            return "\n".join(
                [
                    "# Memory Surface",
                    f"Command: /{command}",
                    "The terminal has not yet bound this memory surface into a dedicated live pane.",
                    "Use the Notes pane as the current landing zone while the bridge grows richer memory bindings.",
                ]
            )
        return f"Command /{command} resolved to {action}."

    def _materialize_model_command(self, raw_command: str, action: str) -> str:
        remainder = action.split(":", 1)[1] if ":" in action else "status"
        mode, _, arg = remainder.partition(" ")
        mode = mode.strip().lower() or "status"
        arg = arg.strip()
        current_provider = (
            self._active_provider_id
            or self._selected_provider_id
            or model_routing.default_target().provider_id
        )
        current_model = (
            self._active_model_id
            or self._selected_model_id
            or model_routing.default_target().model_id
        )

        if mode in {"status", "list", "metrics"}:
            return self._render_model_policy_text(
                self._build_model_policy_summary(
                    selected_provider=current_provider,
                    selected_model=current_model,
                    strategy="responsive",
                )
            )
        if mode == "set":
            target = model_routing.resolve_model_target(arg)
            if target is None and arg.isdigit():
                target = model_routing.target_by_index(int(arg))
            if target is None:
                return f"Unknown model target: {arg or 'missing'}"
            if not model_routing.is_routable(target):
                return (
                    f"Model '{target.alias}' is unroutable "
                    f"(no live key for {target.provider_id}). "
                    "Run `dkeys test` or pick a live model with /model list."
                )
            return self._render_model_policy_text(
                self._build_model_policy_summary(
                    selected_provider=target.provider_id,
                    selected_model=target.model_id,
                    strategy="responsive",
                )
            )
        if mode == "auto":
            strategy = model_routing.resolve_strategy(arg) or "responsive"
            return self._render_model_policy_text(
                self._build_model_policy_summary(
                    selected_provider=current_provider,
                    selected_model=current_model,
                    strategy=strategy,
                )
            )
        return self._render_model_policy_text(
            self._build_model_policy_summary(
                selected_provider=current_provider,
                selected_model=current_model,
                strategy="responsive",
            )
        )

    def _classify_command_outcome(
        self,
        raw_command: str,
        output: object,
        action: object,
    ) -> str:
        """Translate the legacy command tuple into a fail-closed wire outcome."""

        command = _command_name(raw_command)
        registered = (
            frozenset(system_commands_module._ALL_COMMANDS)
            if system_commands_module is not None
            else frozenset()
        )
        if not command:
            return "failed"
        if command not in registered or command in _UNSUPPORTED_BRIDGE_COMMANDS:
            return "unsupported"

        action_text = str(action or "").strip()
        if _is_unconsumed_command_action(action_text):
            return "unsupported"

        rendered = str(output or "").strip().lower()
        if "unknown command:" in rendered:
            return "unsupported"
        if "unsupported in helm slice 1" in rendered:
            return "unsupported"
        if any(
            marker in rendered
            for marker in (
                "unknown model target:",
                " is unroutable ",
                "usage: /",
            )
        ):
            return "failed"

        if not rendered and action_text:
            return "failed"
        return "completed"

    def _evaluate_command(self, raw_command: str) -> tuple[object, object, str]:
        """Run one legacy command tuple and turn it into truthful wire state."""

        if self._commands is None:
            raise RuntimeError("system commands unavailable")
        output, action = self._commands.handle(raw_command)
        if not str(output).strip() and isinstance(action, str) and action.startswith("model:"):
            output = self._materialize_model_command(raw_command, action)
        if not str(output).strip() and isinstance(action, str) and action.startswith("async:"):
            output = self._materialize_async_command(raw_command, action)
        outcome = self._classify_command_outcome(raw_command, output, action)
        if outcome == "unsupported" and _is_unconsumed_command_action(action):
            output = (
                f"Unsupported in Helm Slice 1: /{raw_command or '<empty>'} has no "
                "bound Bun runtime consumer."
            )
        return output, action, outcome

    def _failed_command_fields(
        self,
        raw_command: str,
        exc: BaseException,
    ) -> dict[str, Any]:
        """Build a fail-closed command result without exposing exception contents."""

        label = f"/{raw_command}" if raw_command else "an empty command"
        return {
            "command": raw_command,
            "target_pane": self._command_target_pane(raw_command),
            "output": f"Command {label} failed before completion ({type(exc).__name__}).",
            "action": None,
            "outcome": "failed",
            "ok": False,
            "supported": _is_registered_command(raw_command),
            "completed": False,
            "error_type": type(exc).__name__,
        }

    def _run_action(self, action_type: str, request: dict[str, Any]) -> dict[str, Any]:
        if action_type == "surface.refresh":
            surface = str(request.get("surface", "") or "").strip().lower()
            output, target_pane = self._refresh_surface(surface)
            self._remember_action(f"surface.refresh -> {surface or target_pane}")
            result: dict[str, Any] = {
                "ok": True,
                "summary": f"refreshed {surface or target_pane}",
                "surface": surface or target_pane,
                "target_pane": target_pane,
            }
            if surface in {"repo", "workspace"}:
                summary = self._load_repo_xray()
                git_summary = self._build_git_summary()
                topology = build_workspace_topology(self._repo_root.parent)
                result["payload"] = build_workspace_snapshot_payload(
                    repo_root=str(self._repo_root),
                    git_summary=git_summary,
                    topology=topology,
                    summary=summary,
                )
            elif surface in {"sessions", "session"}:
                result["payload"] = build_session_catalog(
                    self._session_store,
                    cwd=str(self._repo_root),
                    limit=12,
                )
            elif surface in {"models", "model"}:
                default_provider, default_model = self._terminal_default_route()
                policy = self._build_model_policy_summary(
                    selected_provider=self._selected_provider_id or default_provider,
                    selected_model=self._selected_model_id or default_model,
                    strategy="responsive",
                )
                result["payload"] = build_routing_decision_payload(policy)
                result["policy"] = policy
            elif surface in {"control", "runtime"}:
                operator_snapshot = asyncio.run(self._build_operator_snapshot())
                result["payload"] = build_runtime_snapshot_payload(
                    operator_snapshot,
                    repo_root=str(self._repo_root),
                    bridge_status="connected",
                    supervisor_preview=load_terminal_control_state(self._repo_root),
                )
            elif surface in {"agents", "agent"}:
                routes = self._build_agent_routes()
                result["payload"] = build_agent_routes_payload(routes)
                result["routes"] = routes
            else:
                result["output"] = output
            return result
        if action_type == "model.set":
            provider = str(request.get("provider", "") or model_routing.default_target().provider_id).strip().lower()
            model = str(request.get("model", "") or model_routing.default_target().model_id).strip()
            strategy = model_routing.resolve_strategy(str(request.get("strategy", "") or "")) or "responsive"
            requested_route = f"{provider}:{model}"
            target = model_routing.target_for_route(provider, model)
            canonical_route = target is not None and model_routing.is_routable(target)
            local_preview_route = self._is_enabled_local_preview_route(
                provider,
                model,
            )
            external_preview_route = self._is_enabled_external_preview_route(
                provider,
                model,
            )
            if not canonical_route and not local_preview_route and not external_preview_route:
                self._remember_action(f"model.set REFUSED {requested_route} (unroutable)")
                return {
                    "ok": False,
                    "summary": f"route change failed: {requested_route} is unroutable",
                    "target_pane": "models",
                    "output": f"Route {requested_route} has no canonical live route.",
                    "requested_route": requested_route,
                }
            try:
                policy = self._build_model_policy_summary(selected_provider=provider, selected_model=model, strategy=strategy)
            except Exception as exc:
                self._remember_action(f"model.set FAILED {requested_route} ({type(exc).__name__})")
                return {
                    "ok": False,
                    "summary": f"route change failed: {requested_route}",
                    "target_pane": "models",
                    "output": f"Route change to {requested_route} failed: {type(exc).__name__}: {exc}",
                    "requested_route": requested_route,
                }
            if str(policy.get("selected_route", "")) != requested_route:
                # The policy builder silently rewrites unavailable routes to a
                # fallback; surfacing that as success is the silent
                # route-switch failure the operator hit. Refuse honestly.
                active_provider = (
                    self._active_provider_id
                    or self._selected_provider_id
                    or str(policy.get("selected_provider", ""))
                )
                active_model = (
                    self._active_model_id
                    or self._selected_model_id
                    or str(policy.get("selected_model", ""))
                )
                self._remember_action(f"model.set REFUSED {requested_route} (unavailable)")
                return {
                    "ok": False,
                    "summary": f"route change failed: {requested_route} is not available",
                    "target_pane": "models",
                    "output": (
                        f"Route {requested_route} is not available on this bridge "
                        f"(providers: {', '.join(sorted(self._adapters)) or 'none'}). "
                        f"Staying on {active_provider}:{active_model}."
                    ),
                    "requested_route": requested_route,
                }
            self._selected_provider_id = provider
            self._selected_model_id = model
            self._remember_action(f"model.set -> {provider}:{model} ({strategy})")
            return {
                "ok": True,
                "summary": f"model policy set to {provider}:{model} ({strategy})",
                "target_pane": "models",
                "output": self._render_model_policy_text(policy),
                "policy": policy,
                "payload": build_routing_decision_payload(policy),
            }
        if action_type == "agent.route":
            intent = str(request.get("intent", "") or "").strip().lower()
            routes = self._build_agent_routes()
            route_records = routes.get("routes", [])
            selected = None
            if isinstance(route_records, list):
                selected = next(
                    (
                        item
                        for item in route_records
                        if isinstance(item, dict) and str(item.get("intent", "")).strip().lower() == intent
                    ),
                    None,
                )
            output_lines = [self._render_agent_routes_text(routes), "", "## Selected route"]
            if isinstance(selected, dict):
                output_lines.extend(
                    [
                        "Intent: {intent}".format(intent=str(selected.get("intent", "?"))),
                        "Provider: {provider}".format(provider=str(selected.get("provider", "?"))),
                        "Model alias: {model_alias}".format(model_alias=str(selected.get("model_alias", "?"))),
                        "Reasoning: {reasoning}".format(reasoning=str(selected.get("reasoning", "?"))),
                        "Role: {role}".format(role=str(selected.get("role", "?"))),
                        "Use this route when a prompt implies this task profile or when you want to hand off directly.",
                    ]
                )
            else:
                output_lines.append(f"Unknown route intent: {intent or 'missing'}")
            self._remember_action(f"agent.route -> {intent or 'missing'}")
            return {
                "ok": isinstance(selected, dict),
                "summary": f"agent route {intent or 'missing'}",
                "target_pane": "agents",
                "output": "\n".join(output_lines),
                "route": selected,
            }
        if action_type == "evolution.run":
            raw_command = str(request.get("command", "") or "").strip()
            normalized = raw_command.lstrip("/").split(None, 1)[0].lower()
            surface = self._build_evolution_surface()
            lines = [self._render_evolution_surface_text(surface), "", "## Requested action", raw_command or "/loops"]
            if normalized in {"evolve", "loops", "cascade"}:
                lines.append(
                    "Unsupported in Helm Slice 1: no evolution execution handler is available."
                )
            else:
                lines.append("Unknown evolution entry. Known unsupported lanes: /evolve, /loops, /cascade <domain>.")
            self._remember_action(f"evolution.run -> {raw_command or '/loops'}")
            return {
                "ok": False,
                "outcome": "unsupported",
                "completed": False,
                "summary": f"unsupported evolution action {raw_command or '/loops'}",
                "target_pane": "evolution",
                "output": "\n".join(lines),
            }
        if action_type == "command.run":
            supplied_command = request.get("command")
            raw_command = _validated_command_envelope(supplied_command)
            if raw_command is None:
                return {
                    "ok": False,
                    "outcome": "failed",
                    "completed": False,
                    "supported": False,
                    "command": supplied_command if isinstance(supplied_command, str) else "",
                    "summary": "rejected non-exact command envelope",
                    "target_pane": "control",
                    "output": "Command rejected: command.run requires one exact command line.",
                }
            if self._commands is None:
                return {
                    "ok": False,
                    "outcome": "failed",
                    "completed": False,
                    "supported": False,
                    "command": raw_command,
                    "summary": "System commands unavailable",
                    "output": "terminal_commands not installed",
                }
            try:
                output, action, outcome = self._evaluate_command(raw_command)
                self._remember_action(f"command.run -> /{raw_command}")
                return {
                    "ok": outcome == "completed",
                    "outcome": outcome,
                    "completed": outcome == "completed",
                    "supported": _is_registered_command(raw_command)
                    and outcome != "unsupported",
                    "command": raw_command,
                    "summary": f"{outcome} /{raw_command}",
                    "target_pane": self._command_target_pane(raw_command),
                    "output": output,
                    "action": action,
                }
            except Exception as exc:
                return {
                    **self._failed_command_fields(raw_command, exc),
                    "summary": f"failed /{raw_command or '<empty>'}",
                }
        if action_type == "approval.resolve":
            return {
                "ok": False,
                "outcome": "unsupported",
                "completed": False,
                "supported": False,
                "summary": "approval resolution is unavailable in read-only Helm",
                "target_pane": "approvals",
                "output": (
                    "Unsupported in Helm Slice 1: approval.resolve requires an "
                    "effectful authority that this read-only terminal does not own."
                ),
            }
        return {
            "ok": False,
            "outcome": "failed",
            "completed": False,
            "summary": f"unknown action: {action_type or 'missing'}",
            "target_pane": "control",
            "output": f"Unknown action type: {action_type or 'missing'}",
        }

    def _refresh_surface(self, surface: str) -> tuple[str, str]:
        normalized = surface.strip().lower()
        if normalized in {"repo", "workspace"}:
            return self._build_workspace_snapshot(), "repo"
        if normalized in {"ontology"}:
            return self._build_ontology_snapshot(), "ontology"
        if normalized in {"control", "runtime"}:
            return self._build_runtime_snapshot(), "control"
        if normalized in {"commands", "command", "registry"}:
            registry = self._build_command_registry()
            return self._render_command_registry_text(registry), "commands"
        if normalized in {"models", "model"}:
            default_provider, default_model = self._terminal_default_route()
            policy = self._build_model_policy_summary(
                selected_provider=self._selected_provider_id or default_provider,
                selected_model=self._selected_model_id or default_model,
                strategy="responsive",
            )
            return self._render_model_policy_text(policy), "models"
        if normalized in {"agents", "agent"}:
            routes = self._build_agent_routes()
            return self._render_agent_routes_text(routes), "agents"
        if normalized in {"evolution", "evolve"}:
            surface_payload = self._build_evolution_surface()
            return self._render_evolution_surface_text(surface_payload), "evolution"
        if normalized in {"notes", "memory", "sessions", "session"}:
            catalog = build_session_catalog(self._session_store, cwd=str(self._repo_root), limit=12)
            return self._render_session_catalog_text(catalog), "sessions"
        return self._build_runtime_snapshot(), "control"

    def _command_target_pane(self, raw_command: str) -> str:
        parts = raw_command.split(None, 1)
        command = parts[0].lower() if parts else ""
        if command in {"chat", "clear", "reset", "cancel", "paste", "copy", "copylast", "thread"}:
            return "chat"
        if command == "runtime":
            return "runtime"
        if command == "git":
            return "repo"
        if command in {"model", "models"}:
            return "models"
        if command in {"swarm", "agni", "gates", "witness", "openclaw", "hum"}:
            return "agents"
        if command in {"evolve", "loops", "cascade"}:
            return "evolution"
        if command in {"context", "foundations", "telos", "dharma", "corpus", "evidence", "moltbook"}:
            return "ontology"
        if command == "trishula":
            return "agents"
        if command in {"notes", "memory", "archive", "darwin", "logs", "truth", "stigmergy", "sessions", "session"}:
            return "sessions"
        if command in {"approval", "approvals", "permission", "permissions"}:
            return "approvals"
        return "control"

    def _load_repo_xray(self) -> Any | None:
        script_path = self._repo_root / "scripts" / "repo_xray.py"
        if not script_path.exists():
            return None
        spec = importlib.util.spec_from_file_location("dharma_repo_xray", script_path)
        if spec is None or spec.loader is None:
            return None
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        build_xray = getattr(module, "build_xray", None)
        if build_xray is None:
            return None
        return build_xray(self._repo_root)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Dharma terminal JSON bridge")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("stdio", help="Run the JSON bridge over stdin/stdout")
    return parser


async def _async_main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    bridge = TerminalBridge()
    try:
        if args.command == "stdio":
            return await bridge.run_stdio()
    finally:
        await bridge.close()
    parser.error(f"unknown command: {args.command}")
    return 2


def main(argv: list[str] | None = None) -> int:
    return asyncio.run(_async_main(argv))


if __name__ == "__main__":
    raise SystemExit(main())
