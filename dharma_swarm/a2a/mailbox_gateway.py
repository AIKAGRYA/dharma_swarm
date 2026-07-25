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

from dharma_swarm.daemon_config import dharma_state_dir

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
    """The minimal JetStream surface this gateway needs; fakes implement it.

    close() is called by the router AFTER message acks complete — a broker
    must keep its connection open across fetch_inbox() + ack() or acks fail.
    """

    async def publish(self, subject: str, payload: bytes) -> Any: ...

    async def fetch_inbox(
        self, subject: str, durable: str, batch: int
    ) -> list[PulledMessageLike]: ...

    async def close(self) -> None: ...


BrokerFactory = Callable[[], Awaitable[MailboxBrokerLike]]

_broker_factory: BrokerFactory | None = None
_tokens_path: Path | None = None
_receipts_path: Path | None = None
# token_sha256 -> (agent_uid, legacy_callsign or "")
_token_index: dict[str, tuple[str, str]] = {}
_tokens_mtime_ns: int | None = None
# receipt appends that failed since process start (surfaced for ops visibility)
_receipt_write_failures = 0


def _state_dir() -> Path:
    override = os.environ.get("DHARMA_A2A_GATEWAY_DIR")
    if override:
        return Path(override).expanduser()
    return dharma_state_dir() / "a2a_gateway"


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
        "mailbox gateway initialized: %d registered agent identity(ies), index at %s",
        len(_token_index),
        _tokens_path,
    )


def reload_tokens() -> None:
    """(Re)load the hashed-token index. Missing/invalid file -> empty index
    (fail-closed: every request is then rejected)."""
    global _token_index, _tokens_mtime_ns  # noqa: PLW0603
    index: dict[str, tuple[str, str]] = {}
    path = _tokens_path
    if path is not None and path.exists():
        try:
            _tokens_mtime_ns = path.stat().st_mtime_ns
            data = json.loads(path.read_text(encoding="utf-8"))
            for row in data.get("tokens", []):
                digest = str(row.get("token_sha256", "")).lower()
                uid = str(row.get("agent_uid", ""))
                callsign = str(row.get("legacy_callsign", "") or "")
                if callsign and not _SUBJECT_TOKEN_RE.match(callsign):
                    callsign = ""
                if len(digest) == 64 and _SUBJECT_TOKEN_RE.match(uid):
                    index[digest] = (uid, callsign)
        except Exception as exc:  # noqa: BLE001 — fail closed, never crash the app
            logger.warning("identity index %s unreadable (%s); rejecting all requests", path, exc)
            index = {}
            _tokens_mtime_ns = None
    else:
        _tokens_mtime_ns = None
    _token_index = index


def _maybe_reload_tokens() -> None:
    """Re-read the token file when its mtime changes, so a mint or REVOKE
    takes effect on the running gateway without a process restart."""
    path = _tokens_path
    if path is None:
        return
    try:
        current = path.stat().st_mtime_ns if path.exists() else None
    except OSError:
        current = None
    if current != _tokens_mtime_ns:
        reload_tokens()


def _authenticate(request: Request) -> tuple[str, str]:
    """Resolve the bearer token to (agent_uid, legacy_callsign) or raise 401/403."""
    _maybe_reload_tokens()
    if not _token_index:
        raise HTTPException(status_code=403, detail="no agent tokens configured on gateway")
    auth = request.headers.get("Authorization", "")
    token = auth.removeprefix("Bearer ").strip() if auth.startswith("Bearer ") else ""
    if not token:
        raise HTTPException(status_code=401, detail="missing Authorization: Bearer <token>")
    digest = hashlib.sha256(token.encode("utf-8")).hexdigest()
    identity = _token_index.get(digest)
    if identity is None:
        raise HTTPException(status_code=401, detail="unknown token")
    return identity


def _subject_for_peer(to: str, route: str) -> str:
    if not _SUBJECT_TOKEN_RE.match(to):
        raise HTTPException(status_code=400, detail=f"invalid peer name: {to!r}")
    if route == "agent-inbox":
        return INBOX_SUBJECT_TEMPLATE.format(uid=to)
    if route == "a2a":
        return f"{LEGACY_SUBJECT_PREFIX}.{to}"
    raise HTTPException(status_code=400, detail=f"unknown route: {route!r} (use 'a2a' or 'agent-inbox')")


def _own_subjects(uid: str, callsign: str) -> list[str]:
    # The live fleet drains legacy dharma.a2a.<callsign> subjects; an agent
    # whose stable uid differs from its callsign (e.g. devin-roaming-… vs
    # devin) must drain the callsign subject or it misses its real traffic.
    return [
        f"{LEGACY_SUBJECT_PREFIX}.{callsign or uid}",
        INBOX_SUBJECT_TEMPLATE.format(uid=uid),
    ]


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
    except (OSError, TypeError, ValueError) as exc:  # receipts must not break delivery
        global _receipt_write_failures  # noqa: PLW0603
        _receipt_write_failures += 1
        logger.warning("gateway receipt write failed (%d total): %s", _receipt_write_failures, exc)


async def _broker() -> MailboxBrokerLike:
    if _broker_factory is None:
        raise HTTPException(status_code=503, detail="mailbox gateway not initialized")
    try:
        return await _broker_factory()
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"hub unreachable: {exc}") from exc


async def _read_bounded_json(request: Request) -> dict[str, Any]:
    """Enforce the byte limit BEFORE parsing so an oversized request body
    cannot spike memory/CPU on the public HTTPS process."""
    declared = request.headers.get("content-length", "")
    if declared.isdigit() and int(declared) > _MAX_BODY_BYTES:
        raise HTTPException(status_code=413, detail=f"body exceeds {_MAX_BODY_BYTES} bytes")
    raw = await request.body()
    if len(raw) > _MAX_BODY_BYTES:
        raise HTTPException(status_code=413, detail=f"body exceeds {_MAX_BODY_BYTES} bytes")
    try:
        body = json.loads(raw)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail="body must be JSON") from exc
    if not isinstance(body, dict):
        raise HTTPException(status_code=400, detail="body must be a JSON object")
    return body


@router.get("/a2a/mailbox/whoami")
async def whoami(request: Request) -> JSONResponse:
    uid, callsign = _authenticate(request)
    return JSONResponse(
        {
            "agent_uid": uid,
            "legacy_callsign": callsign or None,
            "stream": STREAM_NAME,
            "own_subjects": _own_subjects(uid, callsign),
            "gateway_time": _utc_now(),
        }
    )


@router.post("/a2a/mailbox/send")
async def send(request: Request) -> JSONResponse:
    sender_uid, _ = _authenticate(request)
    body = await _read_bounded_json(request)

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
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        _record_receipt("send_failed", {"from": sender_uid, "subject": subject, "error": str(exc)})
        raise HTTPException(status_code=502, detail=f"publish failed: {exc}") from exc
    finally:
        await broker.close()

    seq = getattr(ack, "seq", None)
    _record_receipt("send", {"from": sender_uid, "subject": subject, "seq": seq})
    return JSONResponse({"ok": True, "subject": subject, "seq": seq, "from": sender_uid})


@router.get("/a2a/mailbox/inbox")
async def inbox(request: Request, batch: int = 10, route: str = "a2a") -> JSONResponse:
    uid, callsign = _authenticate(request)
    batch = max(1, min(int(batch), _MAX_BATCH))
    # Own subjects only — identity comes from the token. The a2a route drains
    # the LEGACY callsign subject when one is registered (that is where the
    # live fleet actually sends); durables stay keyed by the stable uid.
    if route == "a2a":
        subject = _subject_for_peer(callsign or uid, route)
    else:
        subject = _subject_for_peer(uid, route)
    # A durable is bound to its filter subject, so each route needs its own
    # durable — one shared name would stick to whichever subject came first.
    durable = f"gw_{uid}_{route}".replace("-", "_")

    broker = await _broker()
    messages: list[dict[str, Any]] = []
    try:
        try:
            pulled = await broker.fetch_inbox(subject, durable, batch)
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(status_code=502, detail=f"inbox fetch failed: {exc}") from exc
        # Acks run while the broker connection is still open; close() only
        # after the whole drain completes (MailboxBrokerLike contract).
        for msg in pulled:
            try:
                decoded: Any = json.loads(msg.data.decode("utf-8"))
            except Exception as exc:  # noqa: BLE001 — non-JSON traffic is surfaced, not dropped
                logger.debug("non-JSON message on %s surfaced raw: %s", msg.subject, exc)
                decoded = {"raw": msg.data.decode("utf-8", errors="replace")}
            messages.append({"subject": msg.subject, "payload": decoded})
            await msg.ack()
    finally:
        await broker.close()

    _record_receipt("inbox_drain", {"agent_uid": uid, "subject": subject, "count": len(messages)})
    return JSONResponse(
        {"agent_uid": uid, "subject": subject, "durable": durable, "messages": messages}
    )
