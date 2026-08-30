"""RUDRA Codex app-server driver: protocol framing and the v0 stub executor.

Normative source: docs/plans/rudra_v0/RUDRA_BUILD_SPEC.md section 11.

The driver owns protocol framing only. It never spawns, signals, kills, or
reaps an OS process; channels arrive from the Workcell's ProcessOwner. The
outgoing method surface is hard-allowlisted; ``thread/shellCommand``,
``command/exec``, filesystem RPCs, MCP, auth, config, and account methods are
unreachable from this module.

v0 ships the interface plus ``StubCodexDriver``, a deterministic offline
executor used by the smoke suite. The live app-server binding is a later,
separately gated step and performs no network I/O here.
"""

from __future__ import annotations

import hashlib
import json
import select
import time
from fnmatch import fnmatchcase
from pathlib import Path
from typing import IO, Any, Protocol, Sequence

from dharma_swarm.rudra.contracts import TurnObservation, sha256_json

# Mutation-capable RPCs: never transport-retried after any byte may have
# been written; recovery reconciles the deterministic message ID instead.
MUTATION_METHODS = frozenset({"thread/start", "thread/resume", "turn/start"})
READ_ONLY_METHODS = frozenset({"initialize", "turn/interrupt", "thread/read"})
ALLOWED_METHODS = MUTATION_METHODS | READ_ONLY_METHODS

MAX_LINE_BYTES = 1 << 20  # 1 MiB protocol frame ceiling


class ProtocolError(RuntimeError):
    """Malformed, oversized, reordered, or hostile protocol input. Fails closed."""


class ServerRequestDenied(ProtocolError):
    """The server asked for approval/input/tools; denied and the run stops."""


def deterministic_message_id(
    contract_digest: str, attempt_key: str, method: str, logical_seq: int
) -> str:
    """Stable clientUserMessageId / effect key for crash reconciliation."""
    digest = hashlib.sha256(
        f"rudra-msg\x00{contract_digest}\x00{attempt_key}\x00{method}\x00{logical_seq}".encode()
    ).hexdigest()
    return f"rudra-{digest[:32]}"


class JsonRpcPeer:
    """Bounded stdio JSON-RPC framing over ProcessOwner-supplied streams."""

    def __init__(
        self,
        reader: IO[bytes],
        writer: IO[bytes],
        *,
        max_line_bytes: int = MAX_LINE_BYTES,
    ) -> None:
        self.reader = reader
        self.writer = writer
        self.max_line_bytes = max_line_bytes
        self.bytes_written = 0
        self.seq = 0

    def send_request(self, method: str, params: dict[str, Any], msg_id: str) -> None:
        if method not in ALLOWED_METHODS:
            raise ProtocolError(f"method {method!r} not in RUDRA allowlist")
        line = (
            json.dumps(
                {"jsonrpc": "2.0", "id": msg_id, "method": method, "params": params},
                separators=(",", ":"),
            )
            + "\n"
        ).encode()
        if len(line) > self.max_line_bytes:
            raise ProtocolError("outgoing frame exceeds line ceiling")
        self.writer.write(line)
        self.writer.flush()
        self.bytes_written += len(line)

    def send_error_response(self, msg_id: Any, message: str) -> None:
        line = (
            json.dumps(
                {"jsonrpc": "2.0", "id": msg_id,
                 "error": {"code": -32601, "message": message}},
                separators=(",", ":"),
            )
            + "\n"
        ).encode()
        try:
            self.writer.write(line)
            self.writer.flush()
        except (BrokenPipeError, OSError):
            pass

    def read_message(self, deadline: float) -> dict[str, Any]:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise ProtocolError("protocol deadline exceeded")
        fd = self.reader.fileno()
        ready, _, _ = select.select([fd], [], [], remaining)
        if not ready:
            raise ProtocolError("protocol read timeout")
        line = self.reader.readline(self.max_line_bytes + 1)
        if line == b"":
            raise ProtocolError("EOF on protocol channel")
        if len(line) > self.max_line_bytes:
            raise ProtocolError("oversized protocol frame")
        if not line.endswith(b"\n"):
            raise ProtocolError("partial frame at deadline")
        try:
            message = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ProtocolError(f"malformed JSON frame: {exc}") from exc
        if not isinstance(message, dict):
            raise ProtocolError("protocol frame is not an object")
        return message

    def call(
        self,
        method: str,
        params: dict[str, Any],
        *,
        timeout_seconds: float,
        msg_id: str | None = None,
    ) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        """Send one request and await its response.

        Returns (result, notifications). Any unexpected server request is
        explicitly denied and stops the run; wrong IDs, duplicates, and
        conflicting terminal notifications fail closed.
        """
        msg_id = msg_id or f"rudra-rpc-{self.seq}"
        self.seq += 1
        self.send_request(method, params, msg_id)
        deadline = time.monotonic() + timeout_seconds
        notifications: list[dict[str, Any]] = []
        terminal_events: set[str] = set()
        while True:
            message = self.read_message(deadline)
            is_response = "result" in message or "error" in message
            if "method" in message and not is_response:
                if "id" in message:
                    # Unexpected server request: deny and stop the run.
                    self.send_error_response(
                        message["id"], "RUDRA denies server-initiated requests"
                    )
                    raise ServerRequestDenied(
                        f"server request {message.get('method')!r} denied"
                    )
                notifications.append(message)
                if message.get("method", "").endswith("/completed"):
                    marker = sha256_json(message.get("params", {}))
                    if terminal_events and marker not in terminal_events:
                        raise ProtocolError("conflicting terminal notifications")
                    terminal_events.add(marker)
                continue
            if not is_response:
                raise ProtocolError(f"unknown protocol variant: {message!r}")
            if message.get("id") != msg_id:
                raise ProtocolError(
                    f"response id {message.get('id')!r} != expected {msg_id!r}"
                )
            if "error" in message:
                raise ProtocolError(f"RPC error: {message['error']}")
            result = message["result"]
            if not isinstance(result, dict):
                raise ProtocolError("RPC result is not an object")
            return result, notifications


# ---------------------------------------------------------------------------
# Driver interface (spec 7 frozen seam)
# ---------------------------------------------------------------------------


class CodexDriver(Protocol):
    """start_or_resume/start_turn/interrupt/close. Framing only; the
    ProcessOwner owns every OS process the channel belongs to."""

    def start_or_resume(self, *, thread_id: str | None = None) -> str: ...

    def start_turn(
        self, *, prompt: str, logical_seq: int, deadline_seconds: float
    ) -> TurnObservation: ...

    def interrupt(self) -> None: ...

    def close(self) -> None: ...


# ---------------------------------------------------------------------------
# Deterministic offline executor (v0 smoke lane)
# ---------------------------------------------------------------------------


class StubTurn:
    """One scripted deterministic turn: file writes inside the workcell."""

    def __init__(
        self,
        writes: dict[str, str] | None = None,
        *,
        reported_complete: bool = False,
        input_tokens: int = 1000,
        output_tokens: int = 500,
    ) -> None:
        self.writes = writes or {}
        self.reported_complete = reported_complete
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens


class StubCodexDriver:
    """Deterministic executor for offline tests. No process, no network.

    The stub applies scripted writes only inside the admitted workcell and
    only to paths matching the admitted allowed set — but GoalGate never
    trusts it; the gate independently re-verifies every byte.
    """

    def __init__(
        self,
        workcell_root: Path,
        plan: Sequence[StubTurn],
        *,
        allowed_changed_paths: Sequence[str] = ("**",),
        attempt_key: str = "stub",
        contract_digest: str = "stub",
    ) -> None:
        self.workcell_root = Path(workcell_root)
        self.plan = list(plan)
        self.allowed = list(allowed_changed_paths)
        self.attempt_key = attempt_key
        self.contract_digest = contract_digest
        self.thread_id: str | None = None
        self.turns_taken = 0
        self.closed = False

    def start_or_resume(self, *, thread_id: str | None = None) -> str:
        if self.closed:
            raise ProtocolError("driver closed")
        self.thread_id = thread_id or f"stub-thread-{self.attempt_key}"
        return self.thread_id

    def start_turn(
        self, *, prompt: str, logical_seq: int, deadline_seconds: float
    ) -> TurnObservation:
        if self.thread_id is None:
            raise ProtocolError("turn before thread start")
        # The plan is indexed by the supervisor's logical sequence so a
        # restarted driver replays deterministically (writes are idempotent).
        if logical_seq >= len(self.plan):
            self.turns_taken += 1
            return TurnObservation(
                thread_id=self.thread_id,
                turn_id=f"stub-turn-{logical_seq}",
                terminal_event="turn/completed",
                input_tokens=0,
                output_tokens=0,
                aggregate_diff_sha256=None,
                response_sha256=None,
                reported_complete=True,
            )
        turn = self.plan[logical_seq]
        self.turns_taken += 1
        digest = hashlib.sha256()
        for rel_path, content in sorted(turn.writes.items()):
            if not any(fnmatchcase(rel_path, pat) for pat in self.allowed):
                raise ProtocolError(
                    f"stub write outside admitted set: {rel_path}"
                )
            target = self.workcell_root / rel_path
            if target.is_symlink() or not target.resolve().is_relative_to(
                self.workcell_root.resolve()
            ):
                raise ProtocolError(f"stub write escapes workcell: {rel_path}")
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content)
            digest.update(rel_path.encode() + b"\x00" + content.encode())
        turn_id = deterministic_message_id(
            self.contract_digest, self.attempt_key, "turn/start", logical_seq
        )
        return TurnObservation(
            thread_id=self.thread_id,
            turn_id=turn_id,
            terminal_event="turn/completed",
            input_tokens=turn.input_tokens,
            output_tokens=turn.output_tokens,
            aggregate_diff_sha256=digest.hexdigest() if turn.writes else None,
            response_sha256=sha256_json({"prompt": prompt, "seq": logical_seq}),
            reported_complete=turn.reported_complete,
        )

    def interrupt(self) -> None:
        pass

    def close(self) -> None:
        self.closed = True
