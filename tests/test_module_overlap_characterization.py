from __future__ import annotations

from dataclasses import asdict
import importlib
import json
from pathlib import Path

import pytest

from dharma_swarm.operator_core.permissions import (
    GovernanceFilter as OperatorGovernanceFilter,
    GovernancePolicy as OperatorGovernancePolicy,
    sanitize_control_chars,
)
from dharma_swarm.operator_core.session_store import (
    SessionStore as OperatorSessionStore,
    cwd_matches,
)
from dharma_swarm.tui.engine.governance import (
    GovernanceFilter as TuiGovernanceFilter,
    GovernancePolicy as TuiGovernancePolicy,
    _sanitize_control_chars,
)
from dharma_swarm.tui.engine.session_store import (
    SessionStore as TuiSessionStore,
    _cwd_matches,
)
from dharma_swarm.tui.engine.events import (
    TextComplete,
    ThinkingComplete,
    ToolCallComplete,
    ToolResult,
)
from dharma_swarm.tui.engine.adapters.base import CompletionRequest, ProviderConfig
from dharma_swarm.tui.engine.adapters.claude import ClaudeAdapter


REPO_ROOT = Path(__file__).resolve().parents[1]
TERMINAL_CLAUDE = REPO_ROOT / "dharma_swarm" / "terminal_adapters" / "claude.py"


@pytest.mark.parametrize(
    "store_cls",
    [OperatorSessionStore, TuiSessionStore],
    ids=["operator_core", "tui_engine"],
)
def test_session_stores_share_core_lifecycle_contract(
    tmp_path: Path,
    store_cls: type[OperatorSessionStore] | type[TuiSessionStore],
) -> None:
    root = tmp_path / store_cls.__module__.replace(".", "_")
    cwd = str(tmp_path / "repo")
    store = store_cls(root=root)

    session_id = store.create_session(
        session_id="session-1",
        provider_id="claude",
        model_id="claude-sonnet-4-5",
        cwd=cwd,
        title="Characterization",
        provider_session_id="provider-1",
    )
    store.append_event(
        session_id,
        TextComplete(
            provider_id="claude",
            session_id=session_id,
            content="hello from characterization",
            role="assistant",
            raw={"kept": False},
        ),
    )
    store.append_audit(session_id, {"domain": "characterization", "action": "seen"})
    store.finalize_session(
        session_id,
        status="completed",
        total_turns=2,
        total_input_tokens=11,
        total_output_tokens=13,
        total_cost_usd=0.25,
        provider_session_id="provider-2",
    )

    meta = store.load_meta(session_id)
    assert meta["session_id"] == session_id
    assert meta["provider_id"] == "claude"
    assert meta["model_id"] == "claude-sonnet-4-5"
    assert meta["provider_session_id"] == "provider-2"
    assert meta["status"] == "completed"
    assert meta["total_turns"] == 2

    events = store.load_transcript(session_id, include_types={"text_complete"})
    assert len(events) == 1
    assert isinstance(events[0], TextComplete)
    assert events[0].content == "hello from characterization"
    assert events[0].raw is None

    audit_lines = (root / session_id / "audit.jsonl").read_text().splitlines()
    assert len(audit_lines) >= 1
    audit_entry = json.loads(audit_lines[0])
    assert audit_entry["session_id"] == session_id
    assert audit_entry["action"] == "seen"
    assert "timestamp" in audit_entry

    latest = store.latest_session(cwd=str(Path(cwd) / "."), provider_id="claude")
    assert latest is not None
    assert latest["session_id"] == session_id

    ok, errors = store.verify_session_replay(session_id)
    assert ok is True
    assert errors == []


def test_session_store_import_surfaces_are_converged() -> None:
    common_methods = {
        "create_session",
        "append_event",
        "append_audit",
        "load_audit",
        "prune_audit_domains",
        "finalize_session",
        "latest_session",
        "list_sessions",
        "load_meta",
        "load_transcript",
        "set_provider_session_id",
        "verify_session_replay",
    }

    for method in common_methods:
        assert callable(getattr(OperatorSessionStore, method))
        assert callable(getattr(TuiSessionStore, method))

    assert TuiSessionStore is OperatorSessionStore

    assert cwd_matches("~/repo/../repo", str(Path("~/repo").expanduser()))
    assert _cwd_matches is cwd_matches
    assert _cwd_matches("~/repo/../repo", str(Path("~/repo").expanduser()))


def test_governance_policy_defaults_match_between_surfaces() -> None:
    assert TuiGovernancePolicy is OperatorGovernancePolicy
    assert TuiGovernanceFilter is OperatorGovernanceFilter
    assert _sanitize_control_chars is sanitize_control_chars
    assert asdict(OperatorGovernancePolicy()) == asdict(TuiGovernancePolicy())


@pytest.mark.parametrize(
    "policy_cls,filter_cls,sanitize",
    [
        (OperatorGovernancePolicy, OperatorGovernanceFilter, sanitize_control_chars),
        (TuiGovernancePolicy, TuiGovernanceFilter, _sanitize_control_chars),
    ],
    ids=["operator_core", "tui_engine"],
)
def test_governance_filters_share_core_policy_behavior(
    policy_cls: type[OperatorGovernancePolicy] | type[TuiGovernancePolicy],
    filter_cls: type[OperatorGovernanceFilter] | type[TuiGovernanceFilter],
    sanitize,
) -> None:
    entries: list[dict[str, object]] = []
    governance = filter_cls(
        policy=policy_cls(blocked_tools={"Write"}, max_tool_output_chars=5),
        session_id="session-1",
        audit_writer=entries.append,
    )

    blocked = ToolCallComplete(
        provider_id="codex",
        session_id="session-1",
        tool_call_id="blocked",
        tool_name="Write",
        arguments="{}",
    )
    assert governance.process(blocked) is None

    gated = ToolCallComplete(
        provider_id="codex",
        session_id="session-1",
        tool_call_id="gated",
        tool_name="Bash",
        arguments="git status",
        raw={"drop": True},
    )
    filtered_gated = governance.process(gated)
    assert filtered_gated is not None
    assert filtered_gated.provider_options["requires_confirmation"] is True
    assert filtered_gated.raw is None

    result = ToolResult(
        provider_id="codex",
        session_id="session-1",
        tool_call_id="tool-result",
        tool_name="Read",
        content="ok\x01" + ("x" * 20),
    )
    filtered_result = governance.process(result)
    assert filtered_result is not None
    assert "\x01" not in filtered_result.content
    assert "truncated" in filtered_result.content
    assert sanitize("a\x01\nb") == "a\nb"

    thinking_entries: list[dict[str, object]] = []
    thinking_governance = filter_cls(
        policy=policy_cls(),
        session_id="session-1",
        audit_writer=thinking_entries.append,
    )
    thinking = ThinkingComplete(
        provider_id="codex",
        session_id="session-1",
        content="private reasoning",
    )
    thinking_governance.process(thinking)
    thinking_audits = [entry for entry in thinking_entries if "thinking_hash" in entry]
    assert len(thinking_audits) == 1
    assert thinking_audits[0]["thinking_len"] == len("private reasoning")


def test_claude_adapter_import_surfaces_are_converged() -> None:
    tui_module = importlib.import_module("dharma_swarm.tui.engine.adapters.claude")
    terminal_module = importlib.import_module("dharma_swarm.terminal_adapters.claude")
    terminal_package = importlib.import_module("dharma_swarm.terminal_adapters")

    assert terminal_module.ClaudeAdapter is tui_module.ClaudeAdapter
    assert terminal_package.ClaudeAdapter is tui_module.ClaudeAdapter
    assert terminal_package.CompletionRequest is CompletionRequest


def test_claude_adapter_terminal_shim_has_no_missing_engine_imports() -> None:
    text = TERMINAL_CLAUDE.read_text(encoding="utf-8")

    assert "terminal_engine" not in text
    assert "terminal_adapters.base" not in text
    assert "from dharma_swarm.tui.engine.adapters.claude import" in text
    assert not (REPO_ROOT / "dharma_swarm" / "terminal_engine").exists()


def test_claude_adapter_auth_helpers_survived_in_canonical_adapter(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    adapter = ClaudeAdapter(
        config=ProviderConfig(provider_id="claude", default_model="claude-opus-4")
    )
    monkeypatch.setenv("ANTHROPIC_API_KEY", "secret")
    monkeypatch.setattr(
        adapter,
        "auth_status",
        lambda: {"loggedIn": True, "authMethod": "oauth"},
    )

    assert adapter.prefers_subscription_auth("claude-opus-4") is True
    assert adapter.prefers_subscription_auth(
        "claude-opus-4", explicit_mode="api_key"
    ) is False

    api_key_env = adapter._build_env(
        CompletionRequest(
            messages=[{"role": "user", "content": "hello"}],
            provider_options={"auth_mode": "api_key"},
        )
    )
    subscription_env = adapter._build_env(
        CompletionRequest(
            messages=[{"role": "user", "content": "hello"}],
            provider_options={"auth_mode": "subscription"},
        )
    )

    assert api_key_env["ANTHROPIC_API_KEY"] == "secret"
    assert "ANTHROPIC_API_KEY" not in subscription_env
