"""RUDRA Codex app-server driver: narrow protocol framing (spec section 11).

Normative source: docs/plans/rudra_v0/RUDRA_BUILD_SPEC.md section 11.

The driver owns protocol framing only. It never spawns, signals, kills, or
reaps an OS process; channels arrive from the Workcell's ProcessOwner. The
outgoing method surface is hard-allowlisted; ``thread/shellCommand``,
``command/exec``, filesystem RPCs, MCP, auth, config, and account methods are
unreachable from this module. The deterministic offline executor used by the
smoke suite lives in ``tests/fixtures/rudra/stub_driver.py``.
"""

from __future__ import annotations

import hashlib
import json
import select
import time
from typing import IO, Any, Protocol

from dharma_swarm.rudra.contracts import TurnObservation, sha256_json

# Mutation-capable RPCs: never transport-retried after any byte may have
# been written; recovery reconciles the deterministic message ID instead.
MUTATION_METHODS = frozenset({"thread/start", "thread/resume", "turn/start"})
READ_ONLY_METHODS = frozenset({"initialize", "turn/interrupt", "thread/read"})
ALLOWED_METHODS = MUTATION_METHODS | READ_ONLY_METHODS
# Client notifications carry no id and no response; only the protocol
# handshake notice is ever legitimate from this driver.
ALLOWED_NOTIFICATIONS = frozenset({"initialized"})

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
        # Framing runs over the raw stream with our own byte buffer: a
        # BufferedReader prefetches frames into userspace where select(2)
        # can never see them, which deadlocks back-to-back frames.
        self._raw: IO[bytes] = getattr(reader, "raw", reader)
        self._buffer = bytearray()
        self.bytes_written = 0
        self.seq = 0
        # Witness log for undeliverable error replies (dead peer); recorded,
        # never swallowed silently.
        self.error_response_failures: list[str] = []

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

    def send_notification(self, method: str, params: dict[str, Any]) -> None:
        """One id-less client notification; the same allowlist posture."""
        if method not in ALLOWED_NOTIFICATIONS:
            raise ProtocolError(f"notification {method!r} not in RUDRA allowlist")
        line = (
            json.dumps(
                {"jsonrpc": "2.0", "method": method, "params": params},
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
        except (BrokenPipeError, OSError) as exc:
            # The peer is already gone, so the error reply is undeliverable;
            # keep the failure as evidence instead of dropping it.
            self.error_response_failures.append(f"{msg_id!r}: {exc!r}")

    def read_message(self, deadline: float) -> dict[str, Any]:
        while True:
            newline = self._buffer.find(b"\n")
            if newline >= 0:
                line = bytes(self._buffer[: newline + 1])
                del self._buffer[: newline + 1]
                break
            if len(self._buffer) > self.max_line_bytes:
                raise ProtocolError("oversized protocol frame")
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise ProtocolError("protocol deadline exceeded")
            ready, _, _ = select.select([self._raw.fileno()], [], [], remaining)
            if not ready:
                raise ProtocolError("protocol read timeout")
            chunk = self._raw.read(
                min(1 << 16, self.max_line_bytes + 1 - len(self._buffer))
            )
            if chunk == b"":
                if self._buffer:
                    raise ProtocolError("partial frame at EOF")
                raise ProtocolError("EOF on protocol channel")
            self._buffer += chunk
        if len(line) > self.max_line_bytes:
            raise ProtocolError("oversized protocol frame")
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


class TurnState:
    """Accumulates protocol observations for one in-flight turn.

    Telemetry handlers accept only events correlated to the active
    thread+turn; uncorrelated counts stay None so the supervisor charges
    its conservative ceiling instead of a foreign measurement."""

    def __init__(self) -> None:
        self.input_tokens: int | None = None
        self.output_tokens: int | None = None
        self.diff_sha256: str | None = None
        self.response_parts: list[str] = []
        self.response_chars = 0
        self.terminal_status: str | None = None

    def response_sha256(self) -> str | None:
        if not self.response_parts:
            return None
        digest = hashlib.sha256()
        for part in self.response_parts:
            digest.update(part.encode())
        return digest.hexdigest()

    def response_text(self) -> str | None:
        return "".join(self.response_parts) or None


# --- Driver interface (spec 7 frozen seam) ----------------------------------


class CodexDriver(Protocol):
    """start_or_resume/start_turn/interrupt/close. Framing only; the
    ProcessOwner owns every OS process the channel belongs to."""

    def start_or_resume(self, *, thread_id: str | None = None) -> str: ...

    def start_turn(
        self, *, prompt: str, logical_seq: int, deadline_seconds: float
    ) -> TurnObservation: ...

    def interrupt(self) -> None: ...

    def close(self) -> None: ...
