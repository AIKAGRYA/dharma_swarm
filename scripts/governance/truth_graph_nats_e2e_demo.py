#!/usr/bin/env python3
"""Live local NATS proof for truth-graph receipted A2A exchange."""
from __future__ import annotations

import json
import socket
import sys
import uuid
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from dharma_swarm.a2a.task_receipt import validate_task_receipt

REPORT = REPO_ROOT / "reports/orientation/nats_e2e_receipt.json"
SERVER = "nats://127.0.0.1:4222"
SUBJECT = "dharma.a2a.truth_graph_platform.e2e_receipt"
SERVER_HOST = "127.0.0.1"
SERVER_PORT = 4222


def _receipt(agent: str, verdict: str, claim: str) -> dict[str, object]:
    return {
        "schema": "dharma_a2a_task_receipt.v1",
        "claim": claim,
        "evidence": [
            {
                "kind": "command",
                "value": "stdlib NATS protocol request/reply over nats://127.0.0.1:4222",
                "verdict": verdict,
            }
        ],
        "verdict": verdict,
        "next_action": "Render reports/orientation/repo_context.json and verify this receipt appears in the tail.",
        "files_changed": ["reports/orientation/nats_e2e_receipt.json"],
        "agent": agent,
        "exchange_id": "truth-graph-nats-e2e-v1",
    }


def _line(conn: socket.socket) -> bytes:
    chunks: list[bytes] = []
    while True:
        chunk = conn.recv(1)
        if not chunk:
            raise RuntimeError("NATS connection closed")
        chunks.append(chunk)
        if b"".join(chunks).endswith(b"\r\n"):
            return b"".join(chunks)


def _recv_exact(conn: socket.socket, size: int) -> bytes:
    chunks: list[bytes] = []
    remaining = size
    while remaining:
        chunk = conn.recv(remaining)
        if not chunk:
            raise RuntimeError("NATS connection closed while reading payload")
        chunks.append(chunk)
        remaining -= len(chunk)
    return b"".join(chunks)


def _connect(name: str) -> socket.socket:
    conn = socket.create_connection((SERVER_HOST, SERVER_PORT), timeout=5)
    conn.settimeout(5)
    info = _line(conn)
    if not info.startswith(b"INFO "):
        raise RuntimeError(f"unexpected NATS greeting: {info!r}")
    connect_payload = json.dumps(
        {"lang": "python-stdlib", "name": name, "protocol": 1, "verbose": False},
        sort_keys=True,
    )
    conn.sendall(f"CONNECT {connect_payload}\r\nPING\r\n".encode("utf-8"))
    while True:
        line = _line(conn)
        if line == b"PONG\r\n":
            return conn
        if line.startswith(b"-ERR"):
            raise RuntimeError(line.decode("utf-8", "replace").strip())


def _flush(conn: socket.socket) -> None:
    conn.sendall(b"PING\r\n")
    while True:
        line = _line(conn)
        if line == b"PONG\r\n":
            return
        if line.startswith(b"PING"):
            conn.sendall(b"PONG\r\n")
        elif line.startswith(b"-ERR"):
            raise RuntimeError(line.decode("utf-8", "replace").strip())


def _subscribe(conn: socket.socket, subject: str, sid: str) -> None:
    conn.sendall(f"SUB {subject} {sid}\r\n".encode("utf-8"))
    _flush(conn)


def _publish(
    conn: socket.socket,
    subject: str,
    payload: dict[str, object],
    *,
    reply_to: str | None = None,
) -> None:
    body = json.dumps(payload, sort_keys=True).encode("utf-8")
    reply = f" {reply_to}" if reply_to else ""
    conn.sendall(f"PUB {subject}{reply} {len(body)}\r\n".encode("utf-8") + body + b"\r\n")
    _flush(conn)


def _next_message(conn: socket.socket) -> tuple[str, str | None, dict[str, object]]:
    while True:
        line = _line(conn)
        if line.startswith(b"PING"):
            conn.sendall(b"PONG\r\n")
            continue
        if line.startswith(b"-ERR"):
            raise RuntimeError(line.decode("utf-8", "replace").strip())
        if not line.startswith(b"MSG "):
            continue
        parts = line.decode("utf-8", "replace").strip().split()
        if len(parts) == 4:
            _, subject, _sid, size_text = parts
            reply_to = None
        elif len(parts) == 5:
            _, subject, _sid, reply_to, size_text = parts
        else:
            raise RuntimeError(f"unexpected NATS MSG line: {line!r}")
        size = int(size_text)
        body = _recv_exact(conn, size)
        trailer = _recv_exact(conn, 2)
        if trailer != b"\r\n":
            raise RuntimeError("malformed NATS payload trailer")
        payload = json.loads(body.decode("utf-8"))
        if not isinstance(payload, dict):
            raise RuntimeError("NATS payload must be a JSON object")
        return subject, reply_to, payload


def run_exchange() -> dict[str, object]:
    request = _receipt("codex_composer", "verified", "Codex sent a receipted A2A NATS request.")
    response = _receipt("fable_composer", "verified", "Fable replied with a receipted A2A NATS response.")
    for payload in (request, response):
        validation = validate_task_receipt(payload)
        if not validation.valid:
            raise RuntimeError(f"invalid demo receipt: {validation.errors}")

    requester = _connect("truth_graph_codex_requester")
    responder = _connect("truth_graph_fable_responder")
    try:
        inbox = f"_INBOX.truth_graph_platform.{uuid.uuid4().hex}"
        _subscribe(responder, SUBJECT, "responder")
        _subscribe(requester, inbox, "requester")
        _publish(requester, SUBJECT, request, reply_to=inbox)

        received_subject, reply_to, received_request = _next_message(responder)
        if received_subject != SUBJECT or reply_to != inbox:
            raise RuntimeError(f"unexpected request route: {received_subject} reply={reply_to}")
        request_validation = validate_task_receipt(received_request)
        if not request_validation.valid:
            raise RuntimeError(f"invalid NATS request receipt: {request_validation.errors}")
        _publish(responder, reply_to, response)

        received: dict[str, object] | None = None
        for _ in range(5):
            response_subject, _unused_reply, candidate = _next_message(requester)
            if response_subject != inbox:
                continue
            validation = validate_task_receipt(candidate)
            if validation.valid and candidate.get("exchange_id") == response["exchange_id"]:
                received = candidate
                break
        if received is None:
            raise RuntimeError("expected NATS response receipt was not observed")
    finally:
        requester.close()
        responder.close()
    return {
        "schema": "dharma_truth_graph_nats_e2e_receipt.v1",
        "exchange_id": "truth-graph-nats-e2e-v1",
        "server": SERVER,
        "subject": SUBJECT,
        "subject_scope": "dedicated truth-graph proof subject; does not consume live agent inbox subjects",
        "request": request,
        "response": received,
        "ack_tiers": ["request_sent", "broker_reply_received", "receipt_schema_verified"],
        "broker_round_trip": True,
        "idempotency": "single deterministic report path overwritten on rerun",
        "stray_reply_filter": "enabled; ignores non-matching replies until expected exchange_id",
        "transport": "stdlib NATS protocol sockets",
    }


def main() -> int:
    try:
        report = run_exchange()
    except Exception as exc:
        print(f"NATS_E2E_FAIL: {exc}", file=sys.stderr)
        return 1
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    content = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if not REPORT.exists() or REPORT.read_text(encoding="utf-8") != content:
        REPORT.write_text(content, encoding="utf-8")
    print(f"NATS_E2E_OK {REPORT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
