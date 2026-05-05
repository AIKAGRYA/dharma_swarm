from __future__ import annotations

import ast
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


REPO_ROOT = Path(__file__).resolve().parents[1]
TERMINAL_CLAUDE = REPO_ROOT / "dharma_swarm" / "terminal_adapters" / "claude.py"
TUI_CLAUDE = REPO_ROOT / "dharma_swarm" / "tui" / "engine" / "adapters" / "claude.py"


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


def test_session_store_delta_marks_operator_core_as_superset() -> None:
    common_methods = {
        "create_session",
        "append_event",
        "append_audit",
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

    assert callable(getattr(OperatorSessionStore, "load_audit"))
    assert callable(getattr(OperatorSessionStore, "prune_audit_domains"))
    assert not hasattr(TuiSessionStore, "load_audit")
    assert not hasattr(TuiSessionStore, "prune_audit_domains")

    assert cwd_matches("~/repo/../repo", str(Path("~/repo").expanduser()))
    assert _cwd_matches("~/repo/../repo", str(Path("~/repo").expanduser()))


def test_governance_policy_defaults_match_between_surfaces() -> None:
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


def _class_methods(path: Path, class_name: str) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            return {
                item.name
                for item in node.body
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef))
            }
    return set()


def _import_sources(path: Path) -> set[tuple[int, str]]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    sources: set[tuple[int, str]] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            sources.add((node.level, node.module or ""))
    return sources


def test_claude_adapter_convergence_audit_marks_tui_as_live_surface() -> None:
    tui_module = importlib.import_module("dharma_swarm.tui.engine.adapters.claude")
    assert hasattr(tui_module, "ClaudeAdapter")

    with pytest.raises(ModuleNotFoundError) as exc_info:
        importlib.import_module("dharma_swarm.terminal_adapters.claude")
    assert "dharma_swarm.terminal_adapters.base" in str(exc_info.value)

    assert not (REPO_ROOT / "dharma_swarm" / "terminal_adapters" / "base.py").exists()
    assert not (REPO_ROOT / "dharma_swarm" / "terminal_engine").exists()


def test_claude_adapter_static_overlap_and_drift_are_explicit() -> None:
    terminal_methods = _class_methods(TERMINAL_CLAUDE, "ClaudeAdapter")
    tui_methods = _class_methods(TUI_CLAUDE, "ClaudeAdapter")

    shared_runtime_contract = {
        "list_models",
        "get_profile",
        "stream",
        "cancel",
        "close",
        "_spawn_process",
        "_build_env",
        "_build_command",
        "_build_prompt",
        "_normalize_line",
    }
    assert shared_runtime_contract <= terminal_methods
    assert shared_runtime_contract <= tui_methods

    assert {"auth_status", "prefers_subscription_auth"} <= terminal_methods - tui_methods
    terminal_imports = _import_sources(TERMINAL_CLAUDE)
    assert (1, "base") in terminal_imports
    assert (0, "dharma_swarm.terminal_engine.events") in terminal_imports
    assert (0, "dharma_swarm.terminal_engine.stream_parser") in terminal_imports
