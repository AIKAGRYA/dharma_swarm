"""WebSocket connection manager + event broadcaster."""

from __future__ import annotations

import asyncio
import base64
import hashlib
import hmac
import json
import logging
import os
import time
from dataclasses import dataclass
from typing import Any

from fastapi import WebSocket

from dharma_swarm.api_keys import DASHBOARD_API_KEY_ENV

logger = logging.getLogger(__name__)

DASHBOARD_WS_AUTH_PROTOCOL = "dharma-auth"
DASHBOARD_WS_BEARER_PROTOCOL_PREFIX = "dharma-bearer."
DASHBOARD_WS_SESSION_COOKIE = "dharma_ws_session"
DASHBOARD_WS_SESSION_CONTEXT = "dharma-dashboard-ws-session.v1"
DASHBOARD_WS_SESSION_MAX_TTL_SECONDS = 300
_DEFAULT_DASHBOARD_WS_ORIGINS = (
    "http://127.0.0.1:3000",
    "http://localhost:3000",
    "http://[::1]:3000",
    "http://127.0.0.1:3420",
    "http://localhost:3420",
    "http://[::1]:3420",
)


@dataclass(frozen=True, slots=True)
class DashboardWebSocketAuth:
    authorized: bool
    selected_subprotocol: str | None = None


def _dashboard_websocket_offered_protocols(websocket: WebSocket) -> tuple[str, ...]:
    return tuple(
        protocol.strip()
        for protocol in websocket.headers.get("sec-websocket-protocol", "").split(",")
        if protocol.strip()
    )


def _dashboard_websocket_subprotocol_credential(
    offered_protocols: tuple[str, ...],
) -> str:
    """Decode a bearer offer only when the fixed public marker is present."""
    if DASHBOARD_WS_AUTH_PROTOCOL not in offered_protocols:
        return ""
    for protocol in offered_protocols:
        if not protocol.startswith(DASHBOARD_WS_BEARER_PROTOCOL_PREFIX):
            continue
        encoded = protocol.removeprefix(DASHBOARD_WS_BEARER_PROTOCOL_PREFIX)
        if not encoded:
            return ""
        try:
            padding = "=" * (-len(encoded) % 4)
            return base64.urlsafe_b64decode(encoded + padding).decode("utf-8")
        except (ValueError, UnicodeDecodeError):
            return ""
    return ""


def _dashboard_websocket_credential_matches(candidate: str, expected: str) -> bool:
    return bool(candidate) and hmac.compare_digest(
        candidate.encode("utf-8"),
        expected.encode("utf-8"),
    )


def _dashboard_websocket_allowed_origins() -> frozenset[str]:
    configured = os.environ.get("DASHBOARD_WS_ORIGINS")
    values = (
        configured.split(",")
        if configured is not None
        else _DEFAULT_DASHBOARD_WS_ORIGINS
    )
    return frozenset(value.strip().rstrip("/") for value in values if value.strip())


def _dashboard_websocket_origin_allowed(origin: str) -> bool:
    return not origin or origin.rstrip("/") in _dashboard_websocket_allowed_origins()


def _dashboard_websocket_session_matches(
    token: str,
    expected: str,
    *,
    now: int | None = None,
) -> bool:
    """Validate a short-lived HttpOnly browser session without exposing the key."""
    if not isinstance(expected, str) or not expected.strip():
        return False
    try:
        version, expires_text, signature = token.split(".", 2)
        expires = int(expires_text)
    except (AttributeError, TypeError, ValueError):
        return False
    if (
        version != "v1"
        or not expires_text.isdigit()
        or not signature
        or not signature.isascii()
    ):
        return False
    observed_now = int(time.time()) if now is None else now
    if expires < observed_now:
        return False
    if expires > observed_now + DASHBOARD_WS_SESSION_MAX_TTL_SECONDS:
        return False
    payload = f"{version}.{expires_text}"
    digest = hmac.new(
        expected.encode("utf-8"),
        f"{DASHBOARD_WS_SESSION_CONTEXT}:{payload}".encode("utf-8"),
        hashlib.sha256,
    ).digest()
    wanted = base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")
    return hmac.compare_digest(signature, wanted)


async def authenticate_dashboard_websocket(
    websocket: WebSocket,
) -> DashboardWebSocketAuth:
    """Validate the shared dashboard credential before any WS acceptance.

    Browser clients use a short-lived HttpOnly session minted by the same-origin
    dashboard server. Non-browser callers may use an Authorization header or
    fixed-marker subprotocol. Query credentials are intentionally rejected so
    secrets do not enter URLs or access logs; the server only echoes the fixed
    public marker.
    """
    offered_protocols = _dashboard_websocket_offered_protocols(websocket)
    origin = websocket.headers.get("origin", "")
    if not _dashboard_websocket_origin_allowed(origin):
        await websocket.close(code=4403, reason="origin not allowed")
        return DashboardWebSocketAuth(authorized=False)

    expected = os.environ.get(DASHBOARD_API_KEY_ENV)
    if expected is not None:
        if not expected.strip():
            logger.error(
                "DASHBOARD_API_KEY is set but blank; dashboard WebSocket auth "
                "is fail-closed"
            )
            await websocket.close(code=1011, reason="dashboard auth misconfigured")
            return DashboardWebSocketAuth(authorized=False)
        auth_header = websocket.headers.get("authorization", "")
        bearer = auth_header[7:] if auth_header.startswith("Bearer ") else ""
        subprotocol_bearer = _dashboard_websocket_subprotocol_credential(
            offered_protocols
        )
        credential_matches = any(
            _dashboard_websocket_credential_matches(candidate, expected)
            for candidate in (bearer, subprotocol_bearer)
        )
        session_matches = bool(origin) and _dashboard_websocket_session_matches(
            websocket.cookies.get(DASHBOARD_WS_SESSION_COOKIE, ""),
            expected,
        )
        if not credential_matches and not session_matches:
            await websocket.close(code=4401, reason="unauthorized")
            return DashboardWebSocketAuth(authorized=False)

    selected = (
        DASHBOARD_WS_AUTH_PROTOCOL
        if DASHBOARD_WS_AUTH_PROTOCOL in offered_protocols
        else None
    )
    return DashboardWebSocketAuth(
        authorized=True,
        selected_subprotocol=selected,
    )


class ConnectionManager:
    """Manages WebSocket connections grouped by channel."""

    def __init__(self) -> None:
        self._connections: dict[str, list[WebSocket]] = {}
        self._lock = asyncio.Lock()

    async def connect(
        self,
        websocket: WebSocket,
        channel: str = "default",
        *,
        subprotocol: str | None = None,
    ) -> None:
        await websocket.accept(subprotocol=subprotocol)
        async with self._lock:
            if channel not in self._connections:
                self._connections[channel] = []
            self._connections[channel].append(websocket)
        logger.info("WS connected: channel=%s, total=%d", channel, self.count(channel))

    async def disconnect(self, websocket: WebSocket, channel: str = "default") -> None:
        async with self._lock:
            if channel in self._connections:
                try:
                    self._connections[channel].remove(websocket)
                except ValueError:
                    pass
                if not self._connections[channel]:
                    del self._connections[channel]
        logger.info("WS disconnected: channel=%s", channel)

    def count(self, channel: str = "default") -> int:
        return len(self._connections.get(channel, []))

    async def broadcast(self, channel: str, data: dict[str, Any]) -> None:
        """Send data to all connections on a channel."""
        connections = self._connections.get(channel, [])
        if not connections:
            return

        message = json.dumps(data, default=str)
        dead: list[WebSocket] = []

        for ws in connections:
            try:
                await ws.send_text(message)
            except Exception:
                logger.debug(
                    "Failed to send broadcast to WebSocket on channel %s",
                    channel,
                    exc_info=True,
                )
                dead.append(ws)

        if dead:
            async with self._lock:
                for ws in dead:
                    try:
                        self._connections[channel].remove(ws)
                    except (ValueError, KeyError):
                        pass

    async def send_personal(self, websocket: WebSocket, data: dict[str, Any]) -> bool:
        try:
            await websocket.send_text(json.dumps(data, default=str))
            return True
        except Exception:
            logger.debug("Failed to send personal WebSocket message", exc_info=True)
            return False


# Singleton
manager = ConnectionManager()
