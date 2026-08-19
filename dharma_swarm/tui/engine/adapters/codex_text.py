"""Sealed text-only Codex CLI adapter backed by ChatGPT subscription auth.

This adapter is deliberately separate from :mod:`.codex`.  The regular Codex
adapter exposes agent tools; this lane disables every known tool surface and
then treats any tool-shaped provider event as a protocol violation.  Successful
events are buffered until the process exits cleanly, so an unverified request
model is never promoted merely because the CLI started a thread.
"""

from __future__ import annotations

import asyncio
import contextlib
import os
from pathlib import Path
from typing import AsyncIterator

from dharma_swarm.api_keys import ALL_API_KEY_ENV_KEYS, PROVIDER_BASE_URL_ENV_KEYS

from .base import (
    Capability,
    CompletionRequest,
    ModelProfile,
    ProviderAdapter,
    ProviderConfig,
)
from .codex_text_codec import (
    _SAFE_ITEM_TYPES,
    _SAFE_TOP_LEVEL_EVENTS,
    _contains_structural_tool_evidence,
    _decode_provider_event,
    _extract_message_text,
    _looks_tool_shaped,
    _safe_usage as _coerce_usage,
)
from .codex_text_process import CodexTextProcessMixin
from ..events import ErrorEvent, SessionEnd, SessionStart, TextComplete, UsageReport


DHARMA_SWARM = Path(__file__).resolve().parents[4]

CODEX_TEXT_CAPABILITIES = Capability.CANCEL | Capability.CONTEXT_USAGE

# Keep this explicit.  ``--ignore-user-config`` removes workstation feature
# drift, while these switches physically remove known tool-bearing surfaces.
CODEX_TEXT_DISABLED_FEATURES = (
    "shell_tool",
    "unified_exec",
    "code_mode",
    "code_mode_buffered_exec",
    "code_mode_host",
    "apps",
    "enable_mcp_apps",
    "browser_use",
    "browser_use_external",
    "browser_use_full_cdp_access",
    "in_app_browser",
    "computer_use",
    "image_generation",
    "view_image",
    "goals",
    "multi_agent",
    "multi_agent_v2",
    "plugins",
    "plugin_sharing",
    "remote_plugin",
    "skill_search",
    "skill_mcp_dependency_install",
    "memories",
    "tool_call_mcp_elicitation",
    "standalone_web_search",
    "artifact",
    "auth_elicitation",
    "request_permissions_tool",
    "tool_suggest",
    "hooks",
    "shell_snapshot",
    "workspace_dependencies",
)

_METERED_AUTH_ENV_KEYS = frozenset(
    {
        "CODEX_API_KEY",
        "OPENAI_API_KEY",
        "OPENAI_API_BASE",
        "OPENAI_BASE_URL",
        "OPENAI_ORGANIZATION",
        "OPENAI_ORG_ID",
        "OPENAI_PROJECT",
        "OPENAI_PROJECT_ID",
    }
)
_PROVIDER_AUTH_TOKEN_KEYS = frozenset(
    {
        "ANTHROPIC_AUTH_TOKEN",
        "CLAUDE_CODE_OAUTH_TOKEN",
        "GOOGLE_APPLICATION_CREDENTIALS",
        "KIMI_ACCESS_TOKEN",
        "MOONSHOT_AUTH_TOKEN",
        "OPENROUTER_AUTH_TOKEN",
        "XAI_API_KEY",
    }
)
_SUBSCRIPTION_CHILD_ENV_ALLOWLIST = frozenset(
    {
        "CODEX_HOME",
        "COLORTERM",
        "HOME",
        "LANG",
        "LC_ALL",
        "LC_CTYPE",
        "LOGNAME",
        "NO_COLOR",
        "PATH",
        "SHELL",
        "SSL_CERT_DIR",
        "SSL_CERT_FILE",
        "TERM",
        "TMPDIR",
        "USER",
        "XDG_CACHE_HOME",
        "XDG_CONFIG_HOME",
        "XDG_DATA_HOME",
    }
)


class _RequestRejected(ValueError):
    """Internal marker for a request outside the sealed text-only contract."""


def _capability_names(capabilities: Capability) -> list[str]:
    return [
        capability.name.lower()
        for capability in Capability
        if capabilities & capability
    ]


class CodexTextAdapter(CodexTextProcessMixin, ProviderAdapter):
    """Run one exact model through Codex CLI with no executable authority."""

    provider_id = "codex_text"
    _safe_usage = staticmethod(_coerce_usage)

    def __init__(
        self,
        config: ProviderConfig,
        *,
        cli_path: str = "codex",
        workdir: Path | None = None,
    ) -> None:
        if config.provider_id != self.provider_id:
            raise ValueError("Codex text adapter requires provider_id=codex_text")
        configured_model = str(config.default_model or "").strip()
        if not configured_model:
            raise ValueError("Codex text adapter requires one exact default model")
        self._config = config
        self._model = configured_model
        self._cli_path = cli_path
        self._workdir = workdir or DHARMA_SWARM
        self._proc: asyncio.subprocess.Process | None = None
        self._profile = ModelProfile(
            provider_id=self.provider_id,
            model_id=self._model,
            display_name=self._model,
            capabilities=CODEX_TEXT_CAPABILITIES,
            extra={
                "served_identity_source": "request.model_unverified",
                "exact_model_proven": False,
                "authority": "NONE",
            },
        )

    async def list_models(self) -> list[ModelProfile]:
        return [self._profile]

    def get_profile(self, model_id: str | None = None) -> ModelProfile:
        if model_id is not None and model_id != self._model:
            raise ValueError("Codex text adapter rejects model substitution")
        return self._profile

    async def stream(
        self,
        request: CompletionRequest,
        session_id: str,
    ) -> AsyncIterator[
        SessionStart | TextComplete | UsageReport | ErrorEvent | SessionEnd
    ]:
        try:
            prompt = self._raw_prompt(request)
            profile = self.get_profile(request.model)
            command = self._build_command(request)
        except (TypeError, ValueError):
            async for event in self._failure_events(
                session_id,
                code="invalid_text_request",
                message="Codex text lane requires one raw user message and its exact configured model.",
            ):
                yield event
            return

        try:
            process = await self._spawn_process(command, self._build_env())
        except Exception:
            async for event in self._failure_events(
                session_id,
                code="codex_text_spawn_failed",
                message="Codex text lane could not start the local subscription client.",
            ):
                yield event
            return

        self._proc = process
        stderr_task = asyncio.create_task(self._discard_stderr(process))
        provider_session_id: str | None = None
        assistant_parts: list[str] = []
        assistant_bytes = 0
        usage: dict[str, int] | None = None
        turn_completed = False
        failure: tuple[str, str] | None = None

        try:
            await self._write_prompt(process, prompt)
            async for raw_line in self._iter_stdout_lines(process):
                if not raw_line:
                    continue
                try:
                    raw = _decode_provider_event(raw_line)
                except (TypeError, ValueError):
                    failure = (
                        "malformed_provider_event",
                        "Codex text lane rejected malformed provider output.",
                    )
                    await self._terminate_process(process)
                    break

                if _contains_structural_tool_evidence(raw):
                    failure = (
                        "no_tools_contract_violation",
                        "Codex text lane rejected unexpected tool activity.",
                    )
                    await self._terminate_process(process)
                    break

                event_type = str(raw.get("type", "") or "")
                item = raw.get("item")
                item_type = (
                    str(item.get("type", "") or "") if isinstance(item, dict) else ""
                )
                if _looks_tool_shaped(event_type) or _looks_tool_shaped(item_type):
                    failure = (
                        "no_tools_contract_violation",
                        "Codex text lane rejected unexpected tool activity.",
                    )
                    await self._terminate_process(process)
                    break
                if event_type not in _SAFE_TOP_LEVEL_EVENTS or (
                    event_type in {"item.started", "item.completed"}
                    and (
                        not isinstance(item, dict) or item_type not in _SAFE_ITEM_TYPES
                    )
                ):
                    failure = (
                        "unexpected_provider_event",
                        "Codex text lane rejected unexpected provider output.",
                    )
                    await self._terminate_process(process)
                    break

                if event_type == "thread.started":
                    thread_id = raw.get("thread_id")
                    if isinstance(thread_id, str) and thread_id:
                        provider_session_id = thread_id
                elif event_type == "item.completed" and isinstance(item, dict):
                    if item_type in {"agent_message", "message"}:
                        content = _extract_message_text(item)
                        if content:
                            assistant_bytes += len(content.encode("utf-8"))
                            if assistant_bytes > self._MAX_ASSISTANT_BYTES:
                                failure = (
                                    "provider_response_too_large",
                                    "Codex text lane rejected an oversized provider response.",
                                )
                                await self._terminate_process(process)
                                break
                            assistant_parts.append(content)
                    elif item_type == "error":
                        # Codex reports some fail-closed feature/config notices
                        # as error items even when the model turn subsequently
                        # completes successfully.  Never expose their text, but
                        # let the terminal conditions below decide the turn:
                        # clean exit + turn.completed + assistant content.  A
                        # diagnostic-only stream therefore still fails closed.
                        continue
                elif event_type == "turn.completed":
                    turn_completed = True
                    usage = self._safe_usage(raw.get("usage"))
                elif event_type == "error":
                    failure = (
                        "codex_text_provider_error",
                        "Codex text lane failed inside the subscription client.",
                    )
                    await self._terminate_process(process)
                    break

            exit_code = await process.wait()
            if failure is None and exit_code != 0:
                failure = (
                    "codex_text_process_failed",
                    "Codex text lane exited without a successful subscription response.",
                )
            if failure is None and (not turn_completed or not assistant_parts):
                failure = (
                    "codex_text_incomplete_response",
                    "Codex text lane ended before a complete assistant response.",
                )

            if failure is not None:
                async for event in self._failure_events(
                    session_id,
                    code=failure[0],
                    message=failure[1],
                ):
                    yield event
                return

            yield SessionStart(
                provider_id=self.provider_id,
                session_id=session_id,
                model=profile.model_id,
                provider_session_id=provider_session_id,
                capabilities=_capability_names(profile.capabilities),
                tools_available=[],
                system_info={
                    "transport": "codex_cli_subscription",
                    "auth_mode": "chatgpt_subscription",
                    "authority": "NONE",
                    "served_identity_source": "request.model_unverified",
                    "exact_model_proven": False,
                    "no_tools_contract": "physical_disable_and_event_rejection",
                },
            )
            yield TextComplete(
                provider_id=self.provider_id,
                session_id=session_id,
                content="".join(assistant_parts),
                role="assistant",
            )
            if usage is not None:
                yield UsageReport(
                    provider_id=self.provider_id,
                    session_id=session_id,
                    input_tokens=usage["input_tokens"],
                    output_tokens=usage["output_tokens"],
                    cache_read_tokens=usage["cache_read_tokens"],
                    model_breakdown={
                        "requested_model": profile.model_id,
                        "served_identity_source": "request.model_unverified",
                        "exact_model_proven": False,
                    },
                )
            yield SessionEnd(
                provider_id=self.provider_id,
                session_id=session_id,
                success=True,
            )
        except asyncio.CancelledError:
            await self._terminate_process(process)
            raise
        except Exception:
            await self._terminate_process(process)
            async for event in self._failure_events(
                session_id,
                code="codex_text_transport_failed",
                message="Codex text lane failed while reading the subscription response.",
            ):
                yield event
        finally:
            if self._proc is process:
                self._proc = None
            if not stderr_task.done():
                stderr_task.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await stderr_task

    async def cancel(self) -> None:
        process = self._proc
        if process is None:
            return
        await self._terminate_process(process)
        if self._proc is process:
            self._proc = None

    async def close(self) -> None:
        await self.cancel()

    def _raw_prompt(self, request: CompletionRequest) -> bytes:
        if request.model != self._model:
            raise _RequestRejected("model mismatch")
        if request.system_prompt is not None or request.resume_session_id is not None:
            raise _RequestRejected("context injection is not supported")
        if request.tools or request.tool_choice not in (None, "none"):
            raise _RequestRejected("tools are not supported")
        if len(request.messages) != 1:
            raise _RequestRejected("exactly one message is required")
        message = request.messages[0]
        if not isinstance(message, dict):
            raise _RequestRejected("one message object is required")
        if message.get("role") != "user" or not isinstance(message.get("content"), str):
            raise _RequestRejected("one string user message is required")
        return message["content"].encode("utf-8")

    def _build_command(self, request: CompletionRequest) -> list[str]:
        model = self.get_profile(request.model).model_id
        command = [
            self._cli_path,
            "exec",
            "--ephemeral",
            "--ignore-user-config",
            "--ignore-rules",
            "--skip-git-repo-check",
            "--sandbox",
            "read-only",
            "--json",
            "--color",
            "never",
            "-C",
            str(self._workdir),
            "-c",
            "mcp_servers={}",
            "-c",
            "project_doc_max_bytes=0",
        ]
        command.extend(("--disable", "shell_tool"))
        for feature in CODEX_TEXT_DISABLED_FEATURES:
            if feature == "shell_tool":
                continue
            command.extend(("--disable", feature))
        command.extend(("-m", model, "-"))
        return command

    def _build_env(self) -> dict[str, str]:
        environment = dict(os.environ)
        scrubbed = (
            set(ALL_API_KEY_ENV_KEYS)
            | set(PROVIDER_BASE_URL_ENV_KEYS.values())
            | set(_METERED_AUTH_ENV_KEYS)
            | set(_PROVIDER_AUTH_TOKEN_KEYS)
        )
        for key in scrubbed:
            environment.pop(key, None)
        return {
            key: value
            for key, value in environment.items()
            if key in _SUBSCRIPTION_CHILD_ENV_ALLOWLIST
        }

    async def _failure_events(
        self,
        session_id: str,
        *,
        code: str,
        message: str,
    ) -> AsyncIterator[ErrorEvent | SessionEnd]:
        yield ErrorEvent(
            provider_id=self.provider_id,
            session_id=session_id,
            code=code,
            message=message,
            retryable=False,
        )
        yield SessionEnd(
            provider_id=self.provider_id,
            session_id=session_id,
            success=False,
            error_code=code,
            error_message=message,
        )
