"""Tests for TUI session store helpers."""

from __future__ import annotations

import ast
import json
import subprocess
import sys
from pathlib import Path

import dharma_swarm.tui.engine.session_store as tui_session_store_module
from dharma_swarm.runtime_contract import validate_envelope
from dharma_swarm.tui.engine.events import (
    PermissionDecisionEvent,
    PermissionResolutionEvent,
    SessionEnd,
    SessionStart,
    TextComplete,
    UserPrompt,
)
from dharma_swarm.tui.engine.session_store import SessionStore


def test_tui_session_store_imports_resolve_to_one_canonical_class():
    from dharma_swarm.operator_core.session_store import (
        SessionStore as CanonicalSessionStore,
    )
    from dharma_swarm.tui.engine import ProviderRunner as PackageProviderRunner
    from dharma_swarm.tui.engine import SessionStore as PackageSessionStore
    from dharma_swarm.tui.engine.provider_runner import ProviderRunner

    assert SessionStore is CanonicalSessionStore
    assert PackageSessionStore is CanonicalSessionStore
    assert PackageProviderRunner is ProviderRunner


def test_session_store_import_orders_are_cycle_free():
    repo_root = Path(__file__).resolve().parents[1]
    import_orders = (
        """
from dharma_swarm.operator_core.session_store import SessionStore as canonical
from dharma_swarm.tui.engine.session_store import SessionStore as legacy
from dharma_swarm.tui.engine import SessionStore as package
assert canonical is legacy is package
""",
        """
from dharma_swarm.tui.engine.session_store import SessionStore as legacy
from dharma_swarm.operator_core.session_store import SessionStore as canonical
from dharma_swarm.tui.engine import SessionStore as package
assert canonical is legacy is package
""",
        """
from dharma_swarm.tui.engine import SessionStore as package
from dharma_swarm.operator_core.session_store import SessionStore as canonical
from dharma_swarm.tui.engine.session_store import SessionStore as legacy
assert canonical is legacy is package
""",
        """
from dharma_swarm.tui.engine import ProviderRunner as package_runner
from dharma_swarm.tui.engine.provider_runner import ProviderRunner as direct_runner
from dharma_swarm.operator_core.session_store import SessionStore as canonical
from dharma_swarm.tui.engine.session_store import SessionStore as legacy
assert package_runner is direct_runner
assert canonical is legacy
""",
    )

    for script in import_orders:
        result = subprocess.run(
            [sys.executable, "-c", script],
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 0, result.stderr


def test_tui_session_store_compatibility_module_has_no_persistence_implementation():
    module_path = Path(tui_session_store_module.__file__).resolve()
    source = module_path.read_text(encoding="utf-8")
    tree = ast.parse(source)

    assert not any(
        isinstance(node, ast.ClassDef) and node.name == "SessionStore"
        for node in ast.walk(tree)
    )

    imported_modules = {
        alias.name.split(".", 1)[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    imported_modules.update(
        node.module.split(".", 1)[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module
    )
    assert imported_modules.isdisjoint({"aiosqlite", "json", "sqlite3"})

    persistence_calls = {
        node.func.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }
    persistence_calls.update(
        node.func.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    )
    assert persistence_calls.isdisjoint(
        {"connect", "open", "touch", "write_bytes", "write_text"}
    )
    assert not any(
        isinstance(node, ast.Constant)
        and isinstance(node.value, str)
        and ".jsonl" in node.value.casefold()
        for node in ast.walk(tree)
    )

    module_doc = ast.get_docstring(tree) or ""
    assert (
        "Canonical owner: dharma_swarm.operator_core.session_store.SessionStore."
        in module_doc
    )
    assert "Compatibility expiry: 2026-11-01." in module_doc


def test_session_store_list_and_latest_filters(tmp_path):
    store = SessionStore(root=tmp_path)
    s1 = store.create_session(
        session_id="s1",
        provider_id="claude",
        model_id="claude-sonnet-4-5",
        cwd="/repo/a",
        provider_session_id="prov-1",
    )
    s2 = store.create_session(
        session_id="s2",
        provider_id="claude",
        model_id="claude-sonnet-4-5",
        cwd="/repo/b",
        provider_session_id="prov-2",
    )
    s3 = store.create_session(
        session_id="s3",
        provider_id="openai",
        model_id="gpt-5",
        cwd="/repo/a",
        provider_session_id="prov-3",
    )
    assert s1 == "s1"
    assert s2 == "s2"
    assert s3 == "s3"

    # Touch s1 after s3 so it's latest within (/repo/a, claude).
    store.set_provider_session_id("s1", "prov-1b")

    sessions = store.list_sessions()
    assert len(sessions) == 3

    latest = store.latest_session(cwd="/repo/a", provider_id="claude")
    assert latest is not None
    assert latest["session_id"] == "s1"
    assert latest["provider_session_id"] == "prov-1b"


def test_session_store_latest_returns_none_when_no_match(tmp_path):
    store = SessionStore(root=tmp_path)
    store.create_session(
        session_id="s1",
        provider_id="claude",
        model_id="claude-sonnet-4-5",
        cwd="/repo/a",
    )
    latest = store.latest_session(cwd="/repo/z", provider_id="claude")
    assert latest is None


def test_session_store_latest_respects_min_turns(tmp_path):
    store = SessionStore(root=tmp_path)
    store.create_session(
        session_id="s1",
        provider_id="claude",
        model_id="claude-sonnet-4-5",
        cwd="/repo/a",
    )
    store.create_session(
        session_id="s2",
        provider_id="claude",
        model_id="claude-sonnet-4-5",
        cwd="/repo/a",
    )
    # Make s2 the latest but trivial (1 turn), s1 meaningful (3 turns).
    m1 = store.load_meta("s1")
    m1["total_turns"] = 3
    store._write_meta("s1", m1)  # test-only use of helper
    m2 = store.load_meta("s2")
    m2["total_turns"] = 1
    store._write_meta("s2", m2)  # test-only use of helper
    # Touch s2 timestamp to ensure it would win without min_turns.
    store.set_provider_session_id("s2", "prov-s2")

    latest_any = store.latest_session(cwd="/repo/a", provider_id="claude")
    assert latest_any is not None
    assert latest_any["session_id"] == "s2"

    latest_meaningful = store.latest_session(
        cwd="/repo/a",
        provider_id="claude",
        min_turns=2,
    )
    assert latest_meaningful is not None
    assert latest_meaningful["session_id"] == "s1"


def test_session_store_latest_matches_path_equivalence(tmp_path):
    store = SessionStore(root=tmp_path)
    canonical = str((tmp_path / "repo").resolve())
    alias = str(Path(canonical) / "." / "subdir" / "..")
    store.create_session(
        session_id="s1",
        provider_id="claude",
        model_id="claude-sonnet-4-5",
        cwd=canonical,
        provider_session_id="prov-1",
    )

    latest = store.latest_session(cwd=alias, provider_id="claude")
    assert latest is not None
    assert latest["session_id"] == "s1"


def test_session_store_emits_runtime_events_and_verified_snapshots(tmp_path):
    store = SessionStore(root=tmp_path)
    store.create_session(
        session_id="s1",
        provider_id="claude",
        model_id="claude-sonnet-4-5",
        cwd="/repo/a",
        provider_session_id="prov-1",
    )
    store.append_event(
        "s1",
        SessionStart(
            provider_id="claude",
            session_id="s1",
            model="claude-sonnet-4-5",
            provider_session_id="prov-1",
        ),
    )
    store.append_event(
        "s1",
        UserPrompt(
            provider_id="claude",
            session_id="s1",
            content="Give a concise runtime status.",
        ),
    )
    store.append_event(
        "s1",
        TextComplete(
            provider_id="claude",
            session_id="s1",
            content=(
                "Assistant response with enough substance to count as a "
                "significant runtime interaction."
            ),
            role="assistant",
        ),
    )
    store.append_event(
        "s1",
        SessionEnd(
            provider_id="claude",
            session_id="s1",
            success=True,
        ),
    )
    store.finalize_session(
        "s1",
        status="completed",
        total_turns=1,
        total_input_tokens=10,
        total_output_tokens=20,
        total_cost_usd=0.12,
        provider_session_id="prov-1",
    )

    runtime_rows = [
        validate_envelope(json.loads(line))
        for line in (tmp_path / "s1" / "runtime.jsonl").read_text().splitlines()
        if line.strip()
    ]
    assert len(runtime_rows) >= 3
    assert all(ok is True and errors == [] for ok, errors in runtime_rows)

    ok, errors = store.verify_session_replay("s1")
    assert ok is True
    assert errors == []


def test_session_store_load_transcript_round_trips_events(tmp_path):
    store = SessionStore(root=tmp_path)
    store.create_session(
        session_id="s1",
        provider_id="codex",
        model_id="gpt-5.4",
        cwd="/repo/a",
    )
    user = TextComplete(
        provider_id="codex",
        session_id="s1",
        content="hello",
        role="user",
    )
    assistant = TextComplete(
        provider_id="codex",
        session_id="s1",
        content="hi there",
        role="assistant",
    )
    store.append_event("s1", user)
    store.append_event("s1", assistant)

    events = store.load_transcript("s1", include_types={"text_complete"})

    assert len(events) == 2
    assert isinstance(events[0], TextComplete)
    assert events[0].role == "user"
    assert events[1].content == "hi there"


def test_session_store_round_trips_permission_events(tmp_path):
    store = SessionStore(root=tmp_path)
    store.create_session(
        session_id="s1",
        provider_id="codex",
        model_id="gpt-5.4",
        cwd="/repo/a",
    )
    store.append_event(
        "s1",
        PermissionDecisionEvent(
            provider_id="codex",
            session_id="s1",
            action_id="perm-1",
            tool_name="Bash",
            risk="shell_or_network",
            decision="require_approval",
            rationale="gated",
            policy_source="legacy-governance",
            requires_confirmation=True,
            metadata={"session_id": "s1"},
        ),
    )
    store.append_event(
        "s1",
        PermissionResolutionEvent(
            provider_id="codex",
            session_id="s1",
            action_id="perm-1",
            resolution="approved",
            resolved_at="2026-04-02T00:10:00Z",
            actor="operator",
            summary="approved perm-1",
            enforcement_state="recorded_only",
            metadata={"session_id": "s1"},
        ),
    )

    events = store.load_transcript("s1", include_types={"permission_decision", "permission_resolution"})

    assert len(events) == 2
    assert isinstance(events[0], PermissionDecisionEvent)
    assert events[0].action_id == "perm-1"
    assert isinstance(events[1], PermissionResolutionEvent)
    assert events[1].resolution == "approved"
