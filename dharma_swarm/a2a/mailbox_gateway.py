"""HTTPS mailbox gateway — the repo-agnostic fleet door for sandboxed agents.

FastAPI router exposing the two operations the git-seat lane was standing in
for, over plain HTTPS (the one egress every sandbox allows):

    POST /a2a/mailbox/send    publish a message to a peer's hub subject
    GET  /a2a/mailbox/inbox   drain the caller's own durable consumer
    GET  /a2a/mailbox/whoami  cheap authenticated connectivity test

Identity model (FFR-D1-aligned): each bearer token maps to exactly ONE
agent_uid. A caller may publish to ANY peer subject (publish-to-peer,
operator-ratified 2026-07-09) but may only drain its OWN inbox. Tokens are
stored as SHA-256 hashes in ``~/.dharma/a2a_gateway/agent_tokens.json``
(mint with ``scripts/ops/mint_a2a_gateway_token.py``); plaintext tokens never
touch disk on the gateway host.

The JetStream connection is injected via ``init_mailbox_gateway`` so tests
run against fakes and the live entrypoint (``scripts/runtime/
a2a_gateway_server.py``) wires the real broker. Runtime receipts append to
``~/.dharma/a2a_gateway/receipts.jsonl`` — never to git.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Awaitable, Callable, Protocol

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)

router = APIRouter(tags=["a2a-mailbox-gateway"])

STREAM_NAME = "DHARMA_A2A"
MESSAGE_KIND = "a2a_gateway_message.v1"
LEGACY_SUBJECT_PREFIX = "dharma.a2a"
INBOX_SUBJECT_TEMPLATE = "dharma.agent.{uid}.inbox"
_SUBJECT_TOKEN_RE = re.compile(r"^[A-Za-z0-9_-]+$")
_MAX_BODY_BYTES = 64 * 1024
_MAX_BATCH = 25


class PulledMessageLike(Protocol):
    subject: str
    data: bytes

    async def ack(self) -> None: ...


class MailboxBrokerLike(Protocol):
    """The minimal JetStream surface this gateway needs; fakes implement it."""

    async def publish(self, subject: str, payload: bytes) -> Any: ...

    async def fetch_inbox(
        self, subject: str, durable: str, batch: int
    ) -> list[PulledMessageLike]: ...


BrokerFactory = Callable[[], Awaitable[MailboxBrokerLike]]

_broker_factory: BrokerFactory | None = None
_tokens_path: Path | None = None
_receipts_path: Path | None = None
# token_sha256 -> agent_uid
_token_index: dict[str, str] = {}


def _state_dir() -> Path:
    return Path(os.environ.get("DHARMA_A2A_GATEWAY_DIR", "~/.dharma/a2a_gateway")).expanduser()


def init_mailbox_gateway(
    broker_factory: BrokerFactory,
    *,
    tokens_path: Path | None = None,
    receipts_path: Path | None = None,
) -> None:
    """Wire the gateway. Called from the server entrypoint (or tests)."""
    global _broker_factory, _tokens_path, _receipts_path  # noqa: PLW0603
    _broker_factory = broker_factory
    _tokens_path = tokens_path or _state_dir() / "agent_tokens.json"
    _receipts_path = receipts_path or _state_dir() / "receipts.jsonl"
    reload_tokens()
    logger.info(
        "mailbox gateway initialized: %d agent token(s) from %s",
        len(_token_index),
        _tokens_path,
    )


def reload_tokens() -> None:
    """(Re)load the hashed-token index. Missing/invalid file -> empty index
    (fail-closed: every request is then rejected)."""
    global _token_index  # noqa: PLW0603
    index: dict[str, str] = {}
    path = _tokens_path
    if path is not None and path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            for row in data.get("tokens", []):
                digest = str(row.get("token_sha256", "")).lower()
                uid = str(row.get("agent_uid", ""))
                if len(digest) == 64 and _SUBJECT_TOKEN_RE.match(uid):
                    index[digest] = uid
        except Exception as exc:  # noqa: BLE001 — fail closed, never crash the app
            logger.warning("token file %s unreadable (%s); rejecting all requests", path, exc)
            index = {}
    _token_index = index


def _authenticate(request: Request) -> str:
    """Resolve the bearer token to an agent_uid or raise 401/403."""
    if not _token_index:
        raise HTTPException(status_code=403, detail="no agent tokens configured on gateway")
    auth = request.headers.get("Authorization", "")
    token = auth.removeprefix("Bearer ").strip() if auth.startswith("Bearer ") else ""
    if not token:
        raise HTTPException(status_code=401, detail="missing Authorization: Bearer <token>")
    digest = hashlib.sha256(token.encode("utf-8")).hexdigest()
    uid = _token_index.get(digest)
    if uid is None:
        raise HTTPException(status_code=401, detail="unknown token")
    return uid


def _subject_for_peer(to: str, route: str) -> str:
    if not _SUBJECT_TOKEN_RE.match(to):
        raise HTTPException(status_code=400, detail=f"invalid peer name: {to!r}")
    if route == "agent-inbox":
        return INBOX_SUBJECT_TEMPLATE.format(uid=to)
    if route == "a2a":
        return f"{LEGACY_SUBJECT_PREFIX}.{to}"
    raise HTTPException(status_code=400, detail=f"unknown route: {route!r} (use 'a2a' or 'agent-inbox')")


def _own_subjects(uid: str) -> list[str]:
    return [f"{LEGACY_SUBJECT_PREFIX}.{uid}", INBOX_SUBJECT_TEMPLATE.format(uid=uid)]


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _record_receipt(kind: str, payload: dict[str, Any]) -> None:
    path = _receipts_path
    if path is None:
        return
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps({"kind": kind, "at": _utc_now(), **payload}) + "\n")
    except Exception as exc:  # noqa: BLE001 — receipts must not break delivery
        logger.warning("gateway receipt write failed: %s", exc)


async def _broker() -> MailboxBrokerLike:
    if _broker_factory is None:
        raise HTTPException(status_code=503, detail="mailbox gateway not initialized")
    try:
        return await _broker_factory()
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"hub unreachable: {exc}") from exc


@router.get("/a2a/mailbox/whoami")
async def whoami(request: Request) -> JSONResponse:
    uid = _authenticate(request)
    return JSONResponse(
        {
            "agent_uid": uid,
            "stream": STREAM_NAME,
            "own_subjects": _own_subjects(uid),
            "gateway_time": _utc_now(),
        }
    )


@router.post("/a2a/mailbox/send")
async def send(request: Request) -> JSONResponse:
    sender_uid = _authenticate(request)
    try:
        body = await request.json()
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail="body must be JSON") from exc
    if not isinstance(body, dict):
        raise HTTPException(status_code=400, detail="body must be a JSON object")

    to = str(body.get("to", ""))
    route = str(body.get("route", "a2a"))
    message = body.get("body")
    if message is None:
        raise HTTPException(status_code=400, detail="missing 'body' field")
    subject = _subject_for_peer(to, route)

    envelope = {
        "kind": MESSAGE_KIND,
        "from": sender_uid,  # identity comes from the token, never the payload
        "to": to,
        "subject": subject,
        "sent_at": _utc_now(),
        "body": message,
    }
    encoded = json.dumps(envelope, sort_keys=True).encode("utf-8")
    if len(encoded) > _MAX_BODY_BYTES:
        raise HTTPException(status_code=413, detail=f"message exceeds {_MAX_BODY_BYTES} bytes")

    broker = await _broker()
    try:
        ack = await broker.publish(subject, encoded)
    except Exception as exc:  # noqa: BLE001
        _record_receipt("send_failed", {"from": sender_uid, "subject": subject, "error": str(exc)})
        raise HTTPException(status_code=502, detail=f"publish failed: {exc}") from exc

    seq = getattr(ack, "seq", None)
    _record_receipt("send", {"from": sender_uid, "subject": subject, "seq": seq})
    return JSONResponse({"ok": True, "subject": subject, "seq": seq, "from": sender_uid})


@router.get("/a2a/mailbox/inbox")
async def inbox(request: Request, batch: int = 10, route: str = "a2a") -> JSONResponse:
    uid = _authenticate(request)
    batch = max(1, min(int(batch), _MAX_BATCH))
    subject = _subject_for_peer(uid, route)  # own subject only — uid comes from the token
    durable = f"gw_{uid}".replace("-", "_")

    broker = await _broker()
    try:
        pulled = await broker.fetch_inbox(subject, durable, batch)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"inbox fetch failed: {exc}") from exc

    messages: list[dict[str, Any]] = []
    for msg in pulled:
        try:
            decoded: Any = json.loads(msg.data.decode("utf-8"))
        except Exception:  # noqa: BLE001 — non-JSON traffic is surfaced, not dropped
            decoded = {"raw": msg.data.decode("utf-8", errors="replace")}
        messages.append({"subject": msg.subject, "payload": decoded})
        await msg.ack()

    _record_receipt("inbox_drain", {"agent_uid": uid, "subject": subject, "count": len(messages)})
    return JSONResponse(
        {"agent_uid": uid, "subject": subject, "durable": durable, "messages": messages}
    )
