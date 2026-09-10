"""Claude Code provider adapter (subprocess + NDJSON -> canonical events)."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import AsyncIterator

from dharma_swarm import model_pool as _model_pool
from dharma_swarm.model_catalog import HELM_PREVIEW_CLAUDE_SONNET_5_MODEL_ID
from dharma_swarm.models import ProviderType

from .base import (
    Capability,
    CompletionRequest,
    ModelProfile,
    ProviderAdapter,
    ProviderConfig,
)
from .claude_cli import build_claude_command, build_claude_env, build_claude_prompt
from .claude_events import capability_names, normalize_claude_line
from .claude_process import drain_stderr_tail, terminate_process
from .claude_stream import stream_claude
from ..events import CanonicalEventType

DHARMA_SWARM = Path(__file__).resolve().parents[4]

CLAUDE_CAPABILITIES = (
    Capability.STREAMING
    | Capability.TOOL_USE
    | Capability.THINKING
    | Capability.VISION
    | Capability.PARALLEL_TOOLS
    | Capability.RESUME
    | Capability.COST_TRACKING
    | Capability.CONTEXT_USAGE
    | Capability.SYSTEM_PROMPT
    | Capability.CANCEL
)


def _canonical_claude_model() -> str:
    configured = _model_pool.default_for_provider(ProviderType.CLAUDE_CODE)
    entry = _model_pool.get_entry(configured)
    if entry is not None:
        for provider in (ProviderType.CLAUDE_CODE, ProviderType.ANTHROPIC):
            for route in entry.routes:
                if route.provider is provider:
                    return route.model_id
    raise AssertionError(f"model_pool has no Claude route for {configured}")


CLAUDE_DEFAULT_MODEL = _canonical_claude_model()


def _capability_names(caps: Capability) -> list[str]:
    """Compatibility seam for callers that inspect adapter capabilities."""

    return capability_names(caps)


class ClaudeAdapter(ProviderAdapter):
    """ProviderAdapter implementation for Claude Code CLI."""

    provider_id = "claude"

    def __init__(
        self,
        config: ProviderConfig | None = None,
        cli_path: str = "claude",
        workdir: Path | None = None,
    ) -> None:
        self._config = config or ProviderConfig(
            provider_id=self.provider_id,
            default_model=CLAUDE_DEFAULT_MODEL,
        )
        self._cli_path = cli_path
        self._workdir = workdir or DHARMA_SWARM
        self._proc: asyncio.subprocess.Process | None = None
        self._profiles: dict[str, ModelProfile] = {
            CLAUDE_DEFAULT_MODEL: ModelProfile(
                provider_id=self.provider_id,
                model_id=CLAUDE_DEFAULT_MODEL,
                display_name="Claude Opus 5.0",
                capabilities=CLAUDE_CAPABILITIES,
            ),
            "claude-sonnet-4-5": ModelProfile(
                provider_id=self.provider_id,
                model_id="claude-sonnet-4-5",
                display_name="Claude Sonnet 4.5",
                capabilities=CLAUDE_CAPABILITIES,
            ),
            HELM_PREVIEW_CLAUDE_SONNET_5_MODEL_ID: ModelProfile(
                provider_id=self.provider_id,
                model_id=HELM_PREVIEW_CLAUDE_SONNET_5_MODEL_ID,
                display_name="Claude Sonnet 5",
                capabilities=CLAUDE_CAPABILITIES,
            ),
            "claude-opus-4": ModelProfile(
                provider_id=self.provider_id,
                model_id="claude-opus-4",
                display_name="Claude Opus 4",
                capabilities=CLAUDE_CAPABILITIES,
            ),
            "claude-opus-4-6": ModelProfile(
                provider_id=self.provider_id,
                model_id="claude-opus-4-6",
                display_name="Claude Opus 4.6",
                capabilities=CLAUDE_CAPABILITIES,
            ),
            "claude-haiku-4-5": ModelProfile(
                provider_id=self.provider_id,
                model_id="claude-haiku-4-5",
                display_name="Claude Haiku 4.5",
                capabilities=CLAUDE_CAPABILITIES,
            ),
        }

    async def list_models(self) -> list[ModelProfile]:
        return list(self._profiles.values())

    def get_profile(self, model_id: str | None = None) -> ModelProfile:
        model = model_id or self._config.default_model or CLAUDE_DEFAULT_MODEL
        profile = self._profiles.get(model)
        if profile is not None:
            return profile
        return ModelProfile(
            provider_id=self.provider_id,
            model_id=model,
            display_name=model,
            capabilities=CLAUDE_CAPABILITIES,
        )

    async def stream(
        self,
        request: CompletionRequest,
        session_id: str,
    ) -> AsyncIterator[CanonicalEventType]:
        async for event in stream_claude(
            self,
            request,
            session_id,
            drain_stderr=drain_stderr_tail,
            terminate=terminate_process,
        ):
            yield event

    async def cancel(self) -> None:
        proc = self._proc
        if proc is None or proc.returncode is not None:
            return
        try:
            await terminate_process(proc)
        finally:
            if self._proc is proc:
                self._proc = None

    async def close(self) -> None:
        await self.cancel()

    async def _spawn_process(
        self,
        cmd: list[str],
        env: dict[str, str],
    ) -> asyncio.subprocess.Process:
        # Increase StreamReader line limit to tolerate large NDJSON tool-result
        # events (default is 64 KiB and can fail on large file reads).
        stream_limit = int(self._config.extra.get("stream_reader_limit", 2_000_000))
        return await asyncio.create_subprocess_exec(
            *cmd,
            stdin=asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(self._workdir),
            env=env,
            limit=stream_limit,
        )

    def _build_env(self, request: CompletionRequest) -> dict[str, str]:
        return build_claude_env(request)

    def _build_command(self, request: CompletionRequest) -> list[str]:
        return build_claude_command(
            self._cli_path,
            request,
            default_model=self._config.default_model,
            prompt=self._build_prompt(request),
        )

    def _build_prompt(self, request: CompletionRequest) -> str:
        return build_claude_prompt(request)

    def _normalize_line(
        self,
        raw_line: str,
        session_id: str,
        profile: ModelProfile,
    ) -> list[CanonicalEventType]:
        return normalize_claude_line(
            self.provider_id,
            raw_line,
            session_id,
            profile,
        )


__all__ = [
    "CLAUDE_CAPABILITIES",
    "CLAUDE_DEFAULT_MODEL",
    "ClaudeAdapter",
]
