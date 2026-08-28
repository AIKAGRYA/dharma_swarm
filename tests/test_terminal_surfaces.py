from __future__ import annotations

import subprocess
from types import SimpleNamespace

import pytest

from dharma_swarm.models import ProviderType
from dharma_swarm.runtime_provider import RuntimeProviderConfig
from dharma_swarm.terminal_commands import surfaces


def _runtime(
    *,
    provider: ProviderType = ProviderType.CLAUDE_CODE,
    available: bool = True,
    binary_path: str | None = "/opt/dgc/bin/claude",
) -> RuntimeProviderConfig:
    return RuntimeProviderConfig(
        provider=provider,
        default_model="resolved-default-model",
        working_dir="/resolved/cwd",
        binary_path=binary_path,
        available=available,
        source="test",
    )


def test_cmd_tui_stops_cleanly_on_bun_keyboard_interrupt(
    monkeypatch,
    tmp_path,
    capsys,
) -> None:
    terminal_dir = tmp_path / "terminal"
    terminal_dir.mkdir()
    (terminal_dir / "package.json").write_text("{}", encoding="utf-8")
    calls: list[list[str]] = []

    def _fake_run(cmd, **kwargs):
        del kwargs
        calls.append([str(part) for part in cmd])
        if cmd[:2] == ["/bin/zsh", "-lc"]:
            return subprocess.CompletedProcess(cmd, 0, stdout="{}", stderr="")
        raise KeyboardInterrupt

    monkeypatch.setattr(surfaces, "DHARMA_SWARM", tmp_path)
    monkeypatch.setattr(surfaces.shutil, "which", lambda name: "/usr/local/bin/bun")
    monkeypatch.setattr(surfaces.subprocess, "run", _fake_run)

    surfaces.cmd_tui()

    out = capsys.readouterr().out
    assert "DGC dashboard stopped." in out
    assert calls[-1] == ["/usr/local/bin/bun", "run", "start"]


def test_cmd_tui_stops_cleanly_on_legacy_keyboard_interrupt(
    monkeypatch,
    capsys,
) -> None:
    import dharma_swarm.tui as tui

    def _raise_keyboard_interrupt() -> None:
        raise KeyboardInterrupt

    monkeypatch.setenv("DGC_USE_LEGACY_TUI", "1")
    monkeypatch.setattr(tui, "run", _raise_keyboard_interrupt)

    surfaces.cmd_tui()

    out = capsys.readouterr().out
    assert "DGC dashboard stopped." in out


def test_cmd_chat_uses_resolved_binary_after_resolve_and_route(
    monkeypatch,
) -> None:
    events: list[str] = []
    resolved: dict[str, object] = {}
    routed: dict[str, object] = {}
    launched: dict[str, object] = {}

    def _resolve(provider, **kwargs):
        events.append("resolve")
        resolved.update(provider=provider, **kwargs)
        return _runtime()

    class _Policy:
        def __init__(self, *, config):
            routed["config"] = config

        def route(self, request, *, available_providers=None):
            events.append("policy")
            routed.update(
                request=request,
                available_providers=available_providers,
            )
            return SimpleNamespace(
                selected_provider=ProviderType.CLAUDE_CODE,
                selected_model_hint=request.context.get("preferred_model"),
            )

    def _exec(file, command, env):
        events.append("exec")
        launched.update(file=file, command=command, env=env)

    monkeypatch.setenv("CLAUDECODE", "nested-session")
    monkeypatch.setenv("CLAUDE_CODE_ENTRYPOINT", "nested-entrypoint")
    monkeypatch.setenv("CLAUDE_CODE_INCLUDE_PARTIAL_MESSAGES", "1")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "metered-key-sentinel")
    monkeypatch.setenv("ANTHROPIC_AUTH_TOKEN", "metered-token-sentinel")
    monkeypatch.setenv("CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC", "old")
    monkeypatch.setenv("DGC_CHAT_TEST_MARKER", "preserved")
    monkeypatch.setattr(surfaces, "resolve_runtime_provider_config", _resolve)
    monkeypatch.setattr(surfaces, "ProviderPolicyRouter", _Policy)
    monkeypatch.setattr(surfaces, "_build_chat_context_snapshot", lambda: "snapshot")
    monkeypatch.setattr(surfaces.os, "execvpe", _exec)

    surfaces.cmd_chat(
        continue_last=True,
        offline=True,
        model="claude-test-model",
        effort="high",
        include_context=True,
    )

    assert events == ["resolve", "policy", "exec"]
    assert resolved["provider"] == ProviderType.CLAUDE_CODE
    assert resolved["model"] == "claude-test-model"
    assert resolved["working_dir"] == surfaces.os.getcwd()
    resolved_env = resolved["env"]
    assert isinstance(resolved_env, dict)
    assert resolved_env is launched["env"]
    assert "CLAUDECODE" not in resolved_env
    assert "CLAUDE_CODE_ENTRYPOINT" not in resolved_env
    assert "CLAUDE_CODE_INCLUDE_PARTIAL_MESSAGES" not in resolved_env
    assert "ANTHROPIC_API_KEY" not in resolved_env
    assert "ANTHROPIC_AUTH_TOKEN" not in resolved_env
    assert resolved_env["CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC"] == "1"
    assert resolved_env["DGC_CHAT_TEST_MARKER"] == "preserved"

    request = routed["request"]
    assert request.action_name == "dgc.chat.interactive"
    assert request.context == {
        "preferred_provider": "claude_code",
        "preferred_model": "claude-test-model",
        "requires_tooling": True,
        "operator_invoked": True,
    }
    assert routed["available_providers"] == [ProviderType.CLAUDE_CODE]
    assert routed["config"].default_model_hints == {}
    assert launched["file"] == "/opt/dgc/bin/claude"
    assert launched["command"] == [
        "/opt/dgc/bin/claude",
        "--continue",
        "--model",
        "claude-test-model",
        "--effort",
        "high",
        "--append-system-prompt",
        "DGC mission-control context snapshot. Treat as hints and verify.\n\nsnapshot",
    ]


def test_cmd_chat_does_not_inject_resolved_default_model(
    monkeypatch,
) -> None:
    routed: dict[str, object] = {}
    launched: dict[str, object] = {}

    monkeypatch.setattr(
        surfaces,
        "resolve_runtime_provider_config",
        lambda provider, **kwargs: _runtime(),
    )

    class _Policy:
        def __init__(self, *, config):
            routed["config"] = config

        def route(self, request, *, available_providers=None):
            routed["request"] = request
            return SimpleNamespace(
                selected_provider=ProviderType.CLAUDE_CODE,
                selected_model_hint=None,
            )

    monkeypatch.setattr(surfaces, "ProviderPolicyRouter", _Policy)
    monkeypatch.setattr(
        surfaces.os,
        "execvpe",
        lambda file, command, env: launched.update(command=command),
    )

    surfaces.cmd_chat(model=None, include_context=False)

    assert "preferred_model" not in routed["request"].context
    assert routed["config"].default_model_hints == {}
    assert "--model" not in launched["command"]
    assert "resolved-default-model" not in launched["command"]


@pytest.mark.parametrize(
    ("available", "binary_path"),
    [(False, "/opt/dgc/bin/claude"), (True, None)],
)
def test_cmd_chat_unavailable_runtime_never_execs(
    monkeypatch,
    capsys,
    available: bool,
    binary_path: str | None,
) -> None:
    policy_calls: list[bool] = []
    exec_calls: list[bool] = []
    monkeypatch.setattr(
        surfaces,
        "resolve_runtime_provider_config",
        lambda provider, **kwargs: _runtime(
            available=available,
            binary_path=binary_path,
        ),
    )
    monkeypatch.setattr(
        surfaces,
        "ProviderPolicyRouter",
        lambda: policy_calls.append(True),
    )
    monkeypatch.setattr(
        surfaces.os,
        "execvpe",
        lambda *args: exec_calls.append(True),
    )

    with pytest.raises(SystemExit) as exc_info:
        surfaces.cmd_chat(include_context=False)

    assert exc_info.value.code == 1
    assert policy_calls == []
    assert exec_calls == []
    assert "claude CLI not found" in capsys.readouterr().out


def test_cmd_chat_runtime_provider_mismatch_never_execs(
    monkeypatch,
    capsys,
) -> None:
    exec_calls: list[bool] = []
    monkeypatch.setattr(
        surfaces,
        "resolve_runtime_provider_config",
        lambda provider, **kwargs: _runtime(provider=ProviderType.CODEX),
    )
    monkeypatch.setattr(
        surfaces.os,
        "execvpe",
        lambda *args: exec_calls.append(True),
    )

    with pytest.raises(SystemExit) as exc_info:
        surfaces.cmd_chat(include_context=False)

    assert exc_info.value.code == 1
    assert exec_calls == []
    assert "runtime provider mismatch" in capsys.readouterr().out


def test_cmd_chat_policy_provider_mismatch_never_execs(
    monkeypatch,
    capsys,
) -> None:
    exec_calls: list[bool] = []
    monkeypatch.setattr(
        surfaces,
        "resolve_runtime_provider_config",
        lambda provider, **kwargs: _runtime(),
    )

    class _Policy:
        def __init__(self, *, config):
            pass

        def route(self, request, *, available_providers=None):
            return SimpleNamespace(
                selected_provider=ProviderType.CODEX,
                selected_model_hint=None,
            )

    monkeypatch.setattr(surfaces, "ProviderPolicyRouter", _Policy)
    monkeypatch.setattr(
        surfaces.os,
        "execvpe",
        lambda *args: exec_calls.append(True),
    )

    with pytest.raises(SystemExit) as exc_info:
        surfaces.cmd_chat(include_context=False)

    assert exc_info.value.code == 1
    assert exec_calls == []
    assert "policy provider mismatch" in capsys.readouterr().out


def test_cmd_chat_policy_model_mismatch_never_execs(monkeypatch, capsys) -> None:
    exec_calls: list[bool] = []
    monkeypatch.setattr(
        surfaces,
        "resolve_runtime_provider_config",
        lambda provider, **kwargs: _runtime(),
    )

    class _Policy:
        def __init__(self, *, config):
            pass

        def route(self, request, *, available_providers=None):
            return SimpleNamespace(
                selected_provider=ProviderType.CLAUDE_CODE,
                selected_model_hint="different-model",
            )

    monkeypatch.setattr(surfaces, "ProviderPolicyRouter", _Policy)
    monkeypatch.setattr(
        surfaces.os,
        "execvpe",
        lambda *args: exec_calls.append(True),
    )

    with pytest.raises(SystemExit) as exc_info:
        surfaces.cmd_chat(model="operator-model", include_context=False)

    assert exc_info.value.code == 1
    assert exec_calls == []
    assert "policy model mismatch" in capsys.readouterr().out


def test_cmd_chat_continue_preserves_native_session_model(monkeypatch) -> None:
    launched: dict[str, object] = {}
    monkeypatch.setattr(
        surfaces,
        "resolve_runtime_provider_config",
        lambda provider, **kwargs: _runtime(),
    )

    class _Policy:
        def __init__(self, *, config):
            assert config.default_model_hints == {}

        def route(self, request, *, available_providers=None):
            return SimpleNamespace(
                selected_provider=ProviderType.CLAUDE_CODE,
                selected_model_hint=None,
            )

    monkeypatch.setattr(surfaces, "ProviderPolicyRouter", _Policy)
    monkeypatch.setattr(
        surfaces.os,
        "execvpe",
        lambda file, command, env: launched.update(command=command),
    )

    surfaces.cmd_chat(
        continue_last=True,
        model=None,
        include_context=False,
    )

    assert launched["command"] == ["/opt/dgc/bin/claude", "--continue"]
