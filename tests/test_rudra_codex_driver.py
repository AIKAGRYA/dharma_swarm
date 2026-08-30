"""Layer C: app-server protocol framing attacks against the narrow driver.

Normative source: docs/plans/rudra_v0/TEST_AND_BURNIN_PLAN.md section 2C.
Every fixture fails honestly: malformed, partial, oversized, wrong-ID,
EOF, hostile server requests, and unreachable forbidden methods.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from dharma_swarm.rudra.codex_driver import (
    JsonRpcPeer,
    ProtocolError,
    ServerRequestDenied,
    deterministic_message_id,
)
from tests.fixtures.rudra.stub_driver import StubCodexDriver, StubTurn

FAKE_SERVER = Path(__file__).parent / "fixtures" / "rudra" / "fake_app_server.py"


class FakeAppServer:
    """A scripted stdio peer. The *test* owns the process, not the driver."""

    def __init__(self, tmp_path: Path, steps: list[dict]) -> None:
        script = tmp_path / "script.json"
        script.write_text(json.dumps(steps))
        self.proc = subprocess.Popen(
            [sys.executable, str(FAKE_SERVER), str(script)],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        assert self.proc.stdin and self.proc.stdout
        self.peer = JsonRpcPeer(self.proc.stdout, self.proc.stdin)

    def stop(self) -> None:
        try:
            self.proc.stdin.close()
        except (BrokenPipeError, OSError):
            pass
        try:
            self.proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self.proc.kill()
            self.proc.wait(timeout=5)


def test_happy_path_call(tmp_path: Path) -> None:
    server = FakeAppServer(
        tmp_path,
        [{"expect_method": "initialize", "result": {"server": "fake"}}],
    )
    result, notifications = server.peer.call(
        "initialize", {"client": "rudra"}, timeout_seconds=10
    )
    assert result == {"server": "fake"}
    assert notifications == []
    server.stop()


def test_partial_coalesced_frames(tmp_path: Path) -> None:
    response = json.dumps(
        {"jsonrpc": "2.0", "id": "rudra-rpc-0", "result": {"ok": True}}
    ) + "\n"
    server = FakeAppServer(
        tmp_path,
        [
            {"read_request": True},
            {"send_raw": response, "chunks": 5, "delay": 0.02},
        ],
    )
    result, _ = server.peer.call("initialize", {}, timeout_seconds=10)
    assert result == {"ok": True}
    server.stop()


def test_malformed_frame_fails_closed(tmp_path: Path) -> None:
    server = FakeAppServer(
        tmp_path,
        [{"read_request": True}, {"send_raw": "{not json\n"}],
    )
    with pytest.raises(ProtocolError, match="malformed"):
        server.peer.call("initialize", {}, timeout_seconds=10)
    server.stop()


def test_oversized_frame_fails_closed(tmp_path: Path) -> None:
    server = FakeAppServer(
        tmp_path,
        [{"read_request": True}, {"send_raw": "x" * 4096 + "\n"}],
    )
    server.peer.max_line_bytes = 1024
    with pytest.raises(ProtocolError, match="oversized"):
        server.peer.call("initialize", {}, timeout_seconds=10)
    server.stop()


def test_wrong_response_id_fails_closed(tmp_path: Path) -> None:
    server = FakeAppServer(
        tmp_path,
        [
            {"read_request": True},
            {"send": {"jsonrpc": "2.0", "id": "someone-else", "result": {}}},
        ],
    )
    with pytest.raises(ProtocolError, match="response id"):
        server.peer.call("initialize", {}, timeout_seconds=10)
    server.stop()


def test_eof_fails_closed(tmp_path: Path) -> None:
    server = FakeAppServer(tmp_path, [{"exit": True}])
    with pytest.raises(ProtocolError, match="EOF"):
        server.peer.call("initialize", {}, timeout_seconds=10)
    server.stop()


def test_unexpected_server_request_denied(tmp_path: Path) -> None:
    """Approval/permission/user-input requests are denied and stop the run."""
    server = FakeAppServer(
        tmp_path,
        [
            {"read_request": True},
            {
                "send": {
                    "jsonrpc": "2.0",
                    "id": "srv-1",
                    "method": "item/tool/requestUserInput",
                    "params": {},
                }
            },
            {"read_error_response": True},
        ],
    )
    with pytest.raises(ServerRequestDenied):
        server.peer.call("thread/start", {}, timeout_seconds=10)
    server.stop()


def test_conflicting_terminal_notifications_fail_closed(tmp_path: Path) -> None:
    server = FakeAppServer(
        tmp_path,
        [
            {"read_request": True},
            {"send": {"jsonrpc": "2.0", "method": "turn/completed",
                      "params": {"turn": 1}}},
            {"send": {"jsonrpc": "2.0", "method": "turn/completed",
                      "params": {"turn": 2}}},
        ],
    )
    with pytest.raises(ProtocolError, match="conflicting terminal"):
        server.peer.call("turn/start", {}, timeout_seconds=10)
    server.stop()


def test_duplicate_identical_terminal_tolerated(tmp_path: Path) -> None:
    server = FakeAppServer(
        tmp_path,
        [
            {"read_request": True},
            {"send": {"jsonrpc": "2.0", "method": "turn/completed",
                      "params": {"turn": 1}}},
            {"send": {"jsonrpc": "2.0", "method": "turn/completed",
                      "params": {"turn": 1}}},
            {"send": {"jsonrpc": "2.0", "id": "rudra-rpc-0",
                      "result": {"turn": {"id": "t1"}}}},
        ],
    )
    result, notifications = server.peer.call("turn/start", {}, timeout_seconds=10)
    assert result == {"turn": {"id": "t1"}}
    assert len(notifications) == 2
    server.stop()


@pytest.mark.parametrize(
    "forbidden",
    [
        "thread/shellCommand",
        "command/exec",
        "fs/readFile",
        "config/set",
        "account/login",
        "mcp/add",
        "plugin/install",
        "app/marketplace",
        "attestation/sign",
    ],
)
def test_forbidden_methods_unreachable(tmp_path: Path, forbidden: str) -> None:
    server = FakeAppServer(tmp_path, [])
    with pytest.raises(ProtocolError, match="allowlist"):
        server.peer.send_request(forbidden, {}, "x")
    assert server.peer.bytes_written == 0, "forbidden method left the host"
    server.stop()


def test_deterministic_message_id() -> None:
    first = deterministic_message_id("c", "a", "turn/start", 3)
    again = deterministic_message_id("c", "a", "turn/start", 3)
    other = deterministic_message_id("c", "a", "turn/start", 4)
    assert first == again
    assert first != other
    assert first.startswith("rudra-")


def test_mutation_rpc_no_transport_retry(tmp_path: Path) -> None:
    """After any request byte may have been written, a transport failure is
    reconcile-only: the caller sees the failure and must not blind resend."""
    server = FakeAppServer(tmp_path, [{"exit": True}])
    with pytest.raises(ProtocolError):
        server.peer.call("turn/start", {}, timeout_seconds=10)
    assert server.peer.bytes_written > 0
    server.stop()


# ---------------------------------------------------------------------------
# Stub executor boundary
# ---------------------------------------------------------------------------


def test_stub_refuses_write_outside_admitted_set(tmp_path: Path) -> None:
    stub = StubCodexDriver(
        tmp_path, [StubTurn({"tests/evil.py": "pass"})],
        allowed_changed_paths=["src/**"],
    )
    stub.start_or_resume()
    with pytest.raises(ProtocolError, match="outside admitted"):
        stub.start_turn(prompt="p", logical_seq=0, deadline_seconds=10)


def test_stub_refuses_workcell_escape(tmp_path: Path) -> None:
    stub = StubCodexDriver(
        tmp_path, [StubTurn({"../escape.txt": "x"})],
        allowed_changed_paths=["**"],
    )
    stub.start_or_resume()
    with pytest.raises(ProtocolError, match="escapes workcell"):
        stub.start_turn(prompt="p", logical_seq=0, deadline_seconds=10)


def test_stub_turn_requires_thread(tmp_path: Path) -> None:
    stub = StubCodexDriver(tmp_path, [])
    with pytest.raises(ProtocolError, match="thread"):
        stub.start_turn(prompt="p", logical_seq=0, deadline_seconds=10)
