from __future__ import annotations

import os
import subprocess

import pytest

from dharma_swarm import claude_cli
from dharma_swarm.providers import ClaudeCodeProvider, CodexProvider

_KEY = "ANTHROPIC_API_KEY"
_FORCE = "DHARMA_FORCE_ANTHROPIC_API"
_UNFUNDED = "sk-ant-unfunded-test"


@pytest.fixture
def unfunded_key(monkeypatch):
    monkeypatch.setenv(_KEY, _UNFUNDED)
    monkeypatch.setenv("CLAUDECODE", "1")
    monkeypatch.delenv(_FORCE, raising=False)
    return _UNFUNDED


def test_claude_code_build_env_strips_api_key_and_nesting_marker(unfunded_key):
    env = ClaudeCodeProvider()._build_env()

    assert _KEY not in env
    assert "CLAUDECODE" not in env


def test_claude_code_build_env_keeps_api_key_when_forced(unfunded_key, monkeypatch):
    monkeypatch.setenv(_FORCE, "1")

    env = ClaudeCodeProvider()._build_env()

    assert env[_KEY] == unfunded_key


def test_claude_code_build_env_never_mutates_os_environ(unfunded_key):
    ClaudeCodeProvider()._build_env()

    assert os.environ[_KEY] == unfunded_key
    assert os.environ["CLAUDECODE"] == "1"


def test_codex_build_env_keeps_api_key(unfunded_key):
    assert CodexProvider()._build_env()[_KEY] == unfunded_key


def _capture_run_env(monkeypatch) -> dict[str, dict[str, str]]:
    seen: dict[str, dict[str, str]] = {}

    def fake_run(command, **kwargs):
        seen["env"] = dict(kwargs["env"])
        return subprocess.CompletedProcess(command, 0, stdout="PONG", stderr="")

    monkeypatch.setattr(claude_cli.subprocess, "run", fake_run)
    return seen


def test_run_claude_headless_non_bare_strips_api_key(unfunded_key, monkeypatch):
    seen = _capture_run_env(monkeypatch)

    assert claude_cli.run_claude_headless("ping", bare=False) == "PONG"
    assert _KEY not in seen["env"]
    assert "CLAUDECODE" not in seen["env"]
    assert os.environ[_KEY] == unfunded_key


def test_run_claude_headless_non_bare_keeps_api_key_when_forced(unfunded_key, monkeypatch):
    monkeypatch.setenv(_FORCE, "1")
    seen = _capture_run_env(monkeypatch)

    claude_cli.run_claude_headless("ping", bare=False)

    assert seen["env"][_KEY] == unfunded_key


def test_run_claude_headless_bare_keeps_api_key(unfunded_key, monkeypatch):
    seen = _capture_run_env(monkeypatch)

    claude_cli.run_claude_headless("ping", bare=True)

    assert seen["env"][_KEY] == unfunded_key


def test_strip_helper_lives_in_api_keys_and_is_shared():
    from dharma_swarm import api_keys, providers

    # One helper, one truthiness rule: claude_cli and providers must both
    # resolve to api_keys' implementation (no second copy, no new import edge
    # from providers into claude_cli — that edge tripped the blast-radius guard).
    assert claude_cli.strip_metered_anthropic_key is api_keys.strip_metered_anthropic_key
    assert providers.strip_metered_anthropic_key is api_keys.strip_metered_anthropic_key
    assert "strip_metered_anthropic_key" in api_keys.__all__
