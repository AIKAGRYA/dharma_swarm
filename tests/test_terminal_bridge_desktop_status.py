"""Desktop snapshots are bounded observations of real bridge lifecycle events."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
import io
import json
import os
from pathlib import Path
import stat
import sys
import threading
from types import SimpleNamespace

import pytest
import yaml

from dharma_swarm import terminal_bridge_desktop_status as desktop


@pytest.fixture(autouse=True)
def isolated_desktop_environment(monkeypatch):
    for key in (desktop.STATUS_FILE_ENV, "DHARMA_TERMINAL_TMUX_SOCKET", "DHARMA_TERMINAL_TMUX_SESSION"):
        monkeypatch.delenv(key, raising=False)


def make_writer(path: Path, *, owner_id: str = "test-owner") -> desktop.DesktopStatusWriter:
    return desktop.DesktopStatusWriter(path, owner_id=owner_id, owner_pid=os.getpid(), repo_root=path.parent)


async def wait_snapshot(path: Path, predicate, *, timeout: float = 2.0):
    async with asyncio.timeout(timeout):
        while True:
            status = desktop.read_status(path)
            if status["snapshot"] is not None and predicate(status["snapshot"]):
                return status
            await asyncio.sleep(0.005)


def write_private(path: Path, payload: object):
    path.write_text(json.dumps(payload), encoding="utf-8")
    path.chmod(0o600)


@pytest.fixture
def valid_snapshot(tmp_path):
    now = datetime.now(timezone.utc)
    return {
        "schema_version": desktop.STATUS_SCHEMA,
        "owner": {"id": "bridge:fixture", "pid": os.getpid(), "epoch": "fixture-epoch"},
        "sequence": 1,
        "observed_at": now.isoformat(),
        "expires_at": (now + timedelta(seconds=3)).isoformat(),
        "phase": "idle", "session_id": None, "request_id": None,
        "route": {"requested_provider_id": None, "requested_model_id": None},
        "pending_approvals": None, "repo_root": str(tmp_path),
        "seat": {"tmux_socket": None, "tmux_session": None},
        "authority": "observation_only",
    }


def test_missing_and_unset_status_have_no_side_effects(tmp_path):
    path = tmp_path / "missing" / "status.json"
    assert desktop.read_status(path) == {
        "availability": "unavailable", "reason": "status_missing", "snapshot": None,
    }
    assert desktop.DesktopStatusWriter.from_environment(owner_id="owner", owner_pid=os.getpid(), repo_root=tmp_path) is None
    assert not path.parent.exists()


async def test_declared_desktop_contract_matches_optional_publisher_and_consumer(tmp_path, monkeypatch):
    from dharma_swarm.helm_desktop.config import DesktopConfig
    from dharma_swarm.helm_desktop.runtime import observe

    repo_root = Path(__file__).resolve().parents[1]
    manifest = yaml.safe_load((repo_root / "ACTIVE_SURFACE_MANIFEST.yaml").read_text(encoding="utf-8"))
    declaration = manifest["helm_operational_surfaces"]["desktop"]
    config = DesktopConfig(repo_root=repo_root, state_dir=tmp_path / "desktop-state")
    environment = config.environment()
    status_env = declaration["status_file_env"]
    assert config.status_path == config.state_dir / declaration["status_file"]
    assert environment[status_env] == str(config.status_path)

    owner = {"owner_id": "terminal-bridge:manifest-contract", "owner_pid": os.getpid(), "repo_root": repo_root}
    monkeypatch.delenv(status_env, raising=False)
    disabled = await desktop.start_desktop_status(**owner)
    assert declaration["optional"] is True
    assert disabled is None
    assert observe(config)["availability"] == "unavailable"
    assert not config.state_dir.exists()

    for name in (status_env, "DHARMA_TERMINAL_TMUX_SOCKET", "DHARMA_TERMINAL_TMUX_SESSION"):
        monkeypatch.setenv(name, environment[name])
    publisher = await desktop.start_desktop_status(**owner)
    assert publisher is not None
    try:
        publisher.observe({"type": "bridge.ready"})
        publisher.observe({"type": "assistant", "authority": "execution_allowed", "content": "untrusted grant"})
        await wait_snapshot(config.status_path, lambda s: s["phase"] == "idle")
        observed = observe(config)
        snapshot = observed["snapshot"]
        assert observed["availability"] == "fresh"
        assert snapshot["schema_version"] == declaration["status_schema"]
        assert snapshot["authority"] == observed["authority"] == declaration["status_authority"]
        assert snapshot["owner"]["id"] == owner["owner_id"]
        assert snapshot["owner"]["pid"] == owner["owner_pid"]
        assert snapshot["seat"] == config.seat()
        assert declaration["status_grants_effect_authority"] is False
        assert "untrusted grant" not in config.status_path.read_text(encoding="utf-8")
    finally:
        await publisher.close()

    assert observe(config)["reason"] == "owner_closed"
    # A forged authority value cannot turn this declared observation into a
    # consumable grant, even when the remaining owner metadata is valid.
    write_private(config.status_path, {**snapshot, "authority": "execution_allowed"})
    rejected = observe(config)
    assert rejected["availability"] == "invalid"
    assert rejected["snapshot"] is None


@pytest.mark.parametrize("socket,session", [("default", "helm"), ("CODEX_MANAGED_ok", None), (None, "helm"), ("CODEX_MANAGED_a/../b", "helm"), ("CODEX_MANAGED_ok", "helm:1")])
def test_invalid_seat_cannot_publish(tmp_path, monkeypatch, socket, session):
    path = tmp_path / "status.json"
    monkeypatch.setenv(desktop.STATUS_FILE_ENV, str(path))
    if socket is not None:
        monkeypatch.setenv("DHARMA_TERMINAL_TMUX_SOCKET", socket)
    if session is not None:
        monkeypatch.setenv("DHARMA_TERMINAL_TMUX_SESSION", session)
    assert asyncio.run(desktop.start_desktop_status(owner_id="owner", owner_pid=os.getpid(), repo_root=tmp_path)) is None
    assert not path.exists()


def test_relative_status_path_is_rejected_without_creation(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv(desktop.STATUS_FILE_ENV, "relative/status.json")
    assert asyncio.run(desktop.start_desktop_status(owner_id="owner", owner_pid=os.getpid(), repo_root=tmp_path)) is None
    assert not (tmp_path / "relative").exists()


async def test_atomic_private_lifecycle_and_restart(tmp_path):
    path = tmp_path / "nested" / "status.json"
    writer = make_writer(path)
    await writer.start()
    first = desktop.read_status(path)
    assert first["availability"] == "fresh"
    assert first["snapshot"]["phase"] == "starting"
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    writer.observe({"type": "bridge.ready"})
    await wait_snapshot(path, lambda s: s["phase"] == "idle")
    writer.begin_session(session_id="session-1", request_id="request-1", requested_provider_id="provider", requested_model_id="requested-model")
    await wait_snapshot(path, lambda s: s["phase"] == "starting" and s["session_id"] == "session-1")
    writer.observe({"type": "session.ack", "request_id": "request-1", "session_id": "session-1", "model": "unproven-served"})
    running = await wait_snapshot(path, lambda s: s["phase"] == "running")
    assert running["snapshot"]["route"]["requested_model_id"] == "requested-model"
    writer.cancel_session()
    writer.observe({"type": "session_start", "request_id": "request-1", "session_id": "session-1"})
    await wait_snapshot(path, lambda s: s["phase"] == "cancelling")
    writer.clear_session()
    await wait_snapshot(path, lambda s: s["phase"] == "idle" and s["session_id"] is None)
    await writer.close()
    assert desktop.read_status(path)["reason"] == "owner_closed"
    replacement = make_writer(path, owner_id="replacement-owner")
    await replacement.start()
    try:
        updated = desktop.read_status(path)["snapshot"]
        assert updated["owner"]["id"] == "replacement-owner"
        assert updated["owner"]["epoch"] != first["snapshot"]["owner"]["epoch"]
        assert updated["sequence"] == 1
    finally:
        await replacement.close()


async def test_duplicate_writer_cannot_replace_owner_snapshot(tmp_path):
    path = tmp_path / "status.json"
    first, duplicate = make_writer(path), make_writer(path, owner_id="duplicate")
    await first.start()
    before = path.read_bytes()
    try:
        with pytest.raises(BlockingIOError):
            await duplicate.start()
        assert path.read_bytes() == before
        assert desktop.read_status(path)["snapshot"]["owner"]["id"] == "test-owner"
    finally:
        await first.close()


async def test_cancelled_start_releases_lock_after_acquisition_thread_finishes(tmp_path, monkeypatch):
    path = tmp_path / "status.json"
    writer = make_writer(path)
    acquired, release = threading.Event(), threading.Event()
    acquire = writer._acquire

    def blocked_acquire():
        acquire()
        acquired.set()
        assert release.wait(timeout=2)

    monkeypatch.setattr(writer, "_acquire", blocked_acquire)
    task = asyncio.create_task(writer.start())
    try:
        assert await asyncio.to_thread(acquired.wait, 2)
        task.cancel()
        await asyncio.sleep(0)
        assert not task.done()
    finally:
        release.set()
    with pytest.raises(asyncio.CancelledError):
        await task
    replacement = make_writer(path)
    await replacement.start()
    await replacement.close()


async def test_write_failure_expires_observation_and_releases_ownership(tmp_path, monkeypatch):
    path = tmp_path / "status.json"
    writer = make_writer(path)
    await writer.start()
    snapshot = desktop.read_status(path)["snapshot"]
    monkeypatch.setattr(writer, "_write", lambda _: (_ for _ in ()).throw(OSError("test write failed")))
    writer.observe({"type": "bridge.ready"})
    await asyncio.wait_for(asyncio.shield(writer._task), timeout=2)
    assert desktop.read_status(path, now=datetime.fromisoformat(snapshot["expires_at"]))["reason"] == "status_expired"
    replacement = make_writer(path)
    await replacement.start()
    await replacement.close()


async def test_callbacks_coalesce_and_never_persist_narration_or_tool_payloads(tmp_path, monkeypatch):
    path = tmp_path / "status.json"
    writer = make_writer(path)
    writes = []
    write = writer._write
    monkeypatch.setattr(writer, "_write", lambda snapshot: (writes.append(snapshot), write(snapshot)))
    await writer.start()
    try:
        for index in range(1000):
            writer.begin_session(session_id="session", request_id=f"request-{index}", requested_provider_id="provider", requested_model_id="model")
            writer.observe({"type": "text_delta", "content": "SECRET PROMPT", "api_key": "SECRET KEY"})
            writer.observe({"type": "tool_call_complete", "arguments": "SECRET TOOL"})
            writer.observe({"type": "permission.history.result", "payload": {"entries": [], "count": 0}})
        assert len(writes) == 1  # Calls did no disk I/O and did not start per-event tasks.
        latest = await wait_snapshot(path, lambda s: s["request_id"] == "request-999")
        assert len(writes) == 2
        assert latest["snapshot"]["pending_approvals"] is None
        assert "SECRET" not in path.read_text()
        assert not list(path.parent.glob("*.tmp"))
        previous = latest["snapshot"]["sequence"]
        heartbeat = await wait_snapshot(path, lambda s: s["sequence"] > previous)
        assert heartbeat["availability"] == "fresh"
    finally:
        await writer.close()


@pytest.mark.parametrize("patch,reason", [
    ({"authority": "execution_allowed"}, "invalid_status_authority"),
    ({"phase": "complete"}, "invalid_phase"),
    ({"sequence": True}, "invalid_sequence"),
    ({"sequence": -1}, "invalid_sequence"),
    ({"owner": {"id": "owner", "epoch": "epoch", "pid": True}}, "invalid_owner_pid"),
    ({"pending_approvals": False}, "invalid_approval_count"),
    ({"request_id": "secret\ntext"}, "invalid_identifier"),
    ({"repo_root": "relative"}, "invalid_repo_root"),
    ({"prompt": "secret"}, "invalid_snapshot_shape"),
    ({"route": {"served_model_id": "claimed"}}, "invalid_snapshot_shape"),
    ({"seat": {"tmux_socket": "default", "tmux_session": "operator"}}, "invalid_managed_seat"),
    ({"phase": []}, "invalid_status_json"),
])
def test_reader_rejects_invalid_or_authority_bearing_snapshot(tmp_path, valid_snapshot, patch, reason):
    path = tmp_path / "status.json"
    write_private(path, {**valid_snapshot, **patch})
    assert desktop.read_status(path) == {"availability": "invalid", "reason": reason, "snapshot": None}


def test_reader_clock_expiry_and_dead_owner(tmp_path, valid_snapshot, monkeypatch):
    path = tmp_path / "status.json"
    write_private(path, valid_snapshot)
    observed = datetime.fromisoformat(valid_snapshot["observed_at"])
    assert desktop.read_status(path, now=observed - timedelta(microseconds=1))["reason"] == "future_observation"
    assert desktop.read_status(path, now=observed + timedelta(seconds=3))["reason"] == "status_expired"
    monkeypatch.setattr(desktop.os, "kill", lambda *_: (_ for _ in ()).throw(ProcessLookupError()))
    assert desktop.read_status(path, now=observed)["reason"] == "owner_not_running"
    write_private(path, {**valid_snapshot, "expires_at": (observed + timedelta(seconds=4)).isoformat()})
    assert desktop.read_status(path, now=observed)["reason"] == "invalid_expiry"


@pytest.mark.parametrize("raw", [b"{broken", b"{\"owner\":{},\"owner\":{}}", b"\xff\xfe\x00", b" " * (desktop.MAX_STATUS_BYTES + 1)])
def test_reader_rejects_corrupt_duplicate_and_oversized_json(tmp_path, raw):
    path = tmp_path / "status.json"
    path.write_bytes(raw)
    path.chmod(0o600)
    assert desktop.read_status(path)["availability"] == "invalid"


@pytest.mark.parametrize("target", ["status", "parent", "lock", "hardlink"])
async def test_symlinks_and_hardlinks_are_never_written(tmp_path, target):
    actual = tmp_path / "actual"
    actual.mkdir()
    sensitive = actual / "sensitive"
    sensitive.write_text("original")
    sensitive.chmod(0o600)
    path = tmp_path / "status.json"
    if target == "parent":
        parent = tmp_path / "linked"
        parent.symlink_to(actual, target_is_directory=True)
        path = parent / "status.json"
    elif target == "hardlink":
        os.link(sensitive, path)
    else:
        linked = path if target == "status" else tmp_path / ".status.json.lock"
        linked.symlink_to(sensitive)
    writer = make_writer(path)
    with pytest.raises((OSError, ValueError)):
        await writer.start()
    assert sensitive.read_text() == "original"
    if target != "lock":
        assert desktop.read_status(path)["availability"] == "invalid"


def test_reader_rejects_public_files_and_fifo(tmp_path, valid_snapshot):
    path = tmp_path / "status.json"
    write_private(path, valid_snapshot)
    path.chmod(0o644)
    assert desktop.read_status(path)["reason"] == "status_not_private"
    path.unlink()
    os.mkfifo(path, mode=0o600)
    assert desktop.read_status(path)["reason"] == "status_not_regular_file"


async def test_real_stdio_bridge_start_run_cancel_idle_and_close(tmp_path, monkeypatch):
    from dharma_swarm import terminal_bridge
    from dharma_swarm.operator_core.session_store import SessionStore
    from dharma_swarm.tui.engine.events import SessionEnd, SessionStart

    class Adapter:
        def __init__(self):
            self.started, self.release = asyncio.Event(), asyncio.Event()
            self.cancelling, self.cancel_release = asyncio.Event(), asyncio.Event()

        def get_profile(self, _):
            return SimpleNamespace(model_id="requested-model")

        async def stream(self, completion, *, session_id):
            self.started.set()
            yield SessionStart(provider_id="primary", session_id=session_id, model="requested-model", tools_available=[])
            await self.release.wait()
            yield SessionEnd(provider_id="primary", session_id=session_id, success=False)

        async def cancel(self):
            self.cancelling.set()
            await self.cancel_release.wait()
            self.release.set()

        async def close(self):
            self.cancel_release.set()
            self.release.set()

    path = tmp_path / "status.json"
    monkeypatch.setenv(desktop.STATUS_FILE_ENV, str(path))
    monkeypatch.setenv("DHARMA_TERMINAL_TMUX_SOCKET", "CODEX_MANAGED_helm_test")
    monkeypatch.setenv("DHARMA_TERMINAL_TMUX_SESSION", "helm_test")
    monkeypatch.setattr(terminal_bridge, "SystemCommandHandler", None)
    monkeypatch.setattr(terminal_bridge.TerminalBridge, "_ensure_adapters", lambda self: None)
    monkeypatch.setattr(terminal_bridge.TerminalBridge, "_initialize_helm_context", lambda self, **kw: None)
    bridge = terminal_bridge.TerminalBridge(session_store=SessionStore(root=tmp_path / "sessions"))
    bridge._repo_root, bridge._state_dir = tmp_path, tmp_path / "terminal"
    adapter = Adapter()
    bridge._adapters = {"primary": adapter}
    bridge._completion_request_cls = lambda **kw: SimpleNamespace(**kw)
    bridge._chat_lanes = lambda *_: [("primary", "requested-model", {}, "test route")]
    monkeypatch.setattr(bridge, "_resolve_prompt_intent", lambda _: {"kind": "chat", "auto_execute": False})
    monkeypatch.setattr(bridge, "_resolve_session_route", lambda *_: ("primary", "requested-model", None, None))
    read_fd, write_fd = os.pipe()
    reader, input_writer = os.fdopen(read_fd, "r"), os.fdopen(write_fd, "w")
    monkeypatch.setattr(sys, "stdin", reader)
    monkeypatch.setattr(sys, "stdout", io.StringIO())
    task = asyncio.create_task(bridge.run_stdio())
    try:
        idle = await wait_snapshot(path, lambda s: s["phase"] == "idle")
        assert idle["snapshot"]["owner"]["id"] == bridge._runtime_owner_id
        assert idle["snapshot"]["seat"] == {"tmux_socket": "CODEX_MANAGED_helm_test", "tmux_session": "helm_test"}
        input_writer.write(json.dumps({"type": "session.start", "id": "start-1", "provider": "primary", "model": "requested-model", "prompt": "PRIVATE USER PROMPT"}) + "\n")
        input_writer.flush()
        await asyncio.wait_for(adapter.started.wait(), timeout=2)
        active = await wait_snapshot(path, lambda s: s["phase"] == "running")
        assert active["snapshot"]["request_id"] == "start-1"
        assert active["snapshot"]["session_id"] is not None
        input_writer.write(json.dumps({"type": "session.cancel", "id": "cancel-1", "target_request_id": "start-1"}) + "\n")
        input_writer.flush()
        await asyncio.wait_for(adapter.cancelling.wait(), timeout=2)
        await wait_snapshot(path, lambda s: s["phase"] == "cancelling")
        adapter.cancel_release.set()
        await wait_snapshot(path, lambda s: s["phase"] == "idle" and s["session_id"] is None)
        assert "PRIVATE USER PROMPT" not in path.read_text()
    finally:
        adapter.cancel_release.set()
        input_writer.close()
        await asyncio.wait_for(task, timeout=2)
        await bridge.close()
        reader.close()
    assert desktop.read_status(path)["reason"] == "owner_closed"
