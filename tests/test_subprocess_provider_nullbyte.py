"""Regression: a NUL byte in an assembled prompt must never reach
asyncio.create_subprocess_exec, which raises ValueError("embedded null byte")
and was the long-standing "claude_code embedded null byte" dispatch-killer.
_build_prompt is the shared chokepoint for every CLI subprocess provider, so it
must strip NUL bytes before the prompt becomes a subprocess arg.
"""
from __future__ import annotations

import pytest

from dharma_swarm.models import LLMRequest
from dharma_swarm.providers import ClaudeCodeProvider


def _provider():
    try:
        return ClaudeCodeProvider()
    except Exception as exc:  # pragma: no cover - CLI binary absent in some envs
        pytest.skip(f"claude CLI not resolvable here: {exc}")


def test_build_prompt_strips_nul_bytes():
    provider = _provider()
    request = LLMRequest(
        model="claude-opus-4-6",
        messages=[{"role": "user", "content": "before\x00after"}],
        system="sys\x00tem",
    )
    prompt = provider._build_prompt(request)
    assert "\x00" not in prompt
    # The surrounding text must survive — only the NUL is removed.
    assert "beforeafter" in prompt
    assert "system" in prompt
