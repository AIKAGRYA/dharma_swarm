"""Guard tests for the keyless-provider discoverability fix (key_oracle).

The recurring "we have no provider" lie had a precise mechanism: callers
confused provider keys with the Claude Code login lane. The opposite lie is also
dangerous: a `claude` binary on PATH is not enough if headless `claude -p`
cannot actually complete.

These tests pin the fix so it can never silently un-instill:
  * when the `claude` binary is present and headless smoke succeeds, claude_code
    is LIVE regardless of any status file, and dispatchable_now() includes it;
  * when the binary is present but headless smoke fails, claude_code is NOT
    dispatchable;
  * live_providers() keeps its fail-open None semantics for KEYED providers.
"""

from __future__ import annotations

import subprocess

import pytest

from dharma_swarm import key_oracle


@pytest.fixture(autouse=True)
def _clear_claude_smoke_cache():
    key_oracle._claude_code_smoke_cache = None
    yield
    key_oracle._claude_code_smoke_cache = None


def _completed(returncode: int, stdout: str = "", stderr: str = ""):
    return subprocess.CompletedProcess(
        args=["claude", "-p"],
        returncode=returncode,
        stdout=stdout,
        stderr=stderr,
    )


def test_claude_code_is_live_when_headless_smoke_succeeds(monkeypatch, tmp_path):
    # No status file at all (fresh session) — the historical trigger of the lie.
    monkeypatch.setattr(key_oracle.shutil, "which",
                        lambda name: "/usr/bin/claude" if name == "claude" else None)
    monkeypatch.setattr(
        key_oracle.subprocess,
        "run",
        lambda *a, **kw: _completed(0, stdout="OK_DHARMA_CLAUDE_CODE_SMOKE\n"),
    )
    monkeypatch.delenv("OLLAMA_HOST", raising=False)

    assert "claude_code" in key_oracle._detect_keyless_live()
    # LIVE even with no status file and no keys.
    assert key_oracle.is_provider_live("claude_code", home=tmp_path) is True
    assert "claude_code" in key_oracle.dispatchable_now(home=tmp_path)


def test_claude_binary_without_headless_smoke_is_not_dispatchable(monkeypatch, tmp_path):
    monkeypatch.setattr(key_oracle.shutil, "which",
                        lambda name: "/usr/bin/claude" if name == "claude" else None)
    monkeypatch.setattr(
        key_oracle.subprocess,
        "run",
        lambda *a, **kw: _completed(
            1,
            stdout="Failed to authenticate. API Error: 401 Invalid authentication credentials",
        ),
    )
    monkeypatch.delenv("OLLAMA_HOST", raising=False)

    assert "claude_code" not in key_oracle._detect_keyless_live()
    assert key_oracle.is_provider_live("claude_code", home=tmp_path) is None
    assert key_oracle.dispatchable_now(home=tmp_path) == set()


def test_no_keyless_lane_when_nothing_present(monkeypatch, tmp_path):
    monkeypatch.setattr(key_oracle.shutil, "which", lambda name: None)
    monkeypatch.delenv("OLLAMA_HOST", raising=False)

    assert key_oracle._detect_keyless_live() == set()
    # claude_code is not live, and (no status file) liveness is unknown -> None.
    assert key_oracle.is_provider_live("claude_code", home=tmp_path) is None
    # dispatchable_now never returns None and is honestly empty here.
    assert key_oracle.dispatchable_now(home=tmp_path) == set()


def test_ollama_detected_as_local(monkeypatch, tmp_path):
    monkeypatch.setattr(key_oracle.shutil, "which",
                        lambda name: "/usr/bin/ollama" if name == "ollama" else None)
    monkeypatch.delenv("OLLAMA_HOST", raising=False)
    detected = key_oracle._detect_keyless_live()
    assert "local" in detected and "ollama" in detected


def test_live_providers_keeps_fail_open_none_for_keyed(monkeypatch, tmp_path):
    """The keyless fix must NOT change the fail-open contract: with no status
    file, live_providers() still returns None (unknown) so keyed providers are
    not filtered out of routing."""
    monkeypatch.setattr(key_oracle.shutil, "which",
                        lambda name: "/usr/bin/claude" if name == "claude" else None)
    monkeypatch.setattr(
        key_oracle.subprocess,
        "run",
        lambda *a, **kw: _completed(0, stdout="OK_DHARMA_CLAUDE_CODE_SMOKE\n"),
    )
    assert key_oracle.live_providers(home=tmp_path) is None


def test_dispatchable_now_unions_keyless_and_keyed(monkeypatch, tmp_path):
    import json
    import time

    # A fresh, live status file marking openrouter live.
    status = {
        "last_test_ts": time.time(),
        "rows": {"openrouter": {"glyph": "✓", "status": "live"}},
    }
    dpath = tmp_path / ".dharma"
    dpath.mkdir(parents=True)
    (dpath / "keys_status.json").write_text(json.dumps(status))
    monkeypatch.setattr(key_oracle.shutil, "which",
                        lambda name: "/usr/bin/claude" if name == "claude" else None)
    monkeypatch.setattr(
        key_oracle.subprocess,
        "run",
        lambda *a, **kw: _completed(0, stdout="OK_DHARMA_CLAUDE_CODE_SMOKE\n"),
    )

    now = key_oracle.dispatchable_now(home=tmp_path)
    assert "claude_code" in now   # keyless lane
    assert "openrouter" in now    # keyed, proven live
