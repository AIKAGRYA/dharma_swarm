#!/usr/bin/env python3
"""Slim server entrypoint for the A2A mailbox gateway.

Runs ONLY the mailbox router + health — not the full api.main app — so the
always-on host (the AGNI/VPS droplet, next to the broker) can serve the fleet
door with a minimal surface:

    NATS_URL=nats://127.0.0.1:4222 \
    uvicorn scripts.runtime.a2a_gateway_server:app --host 0.0.0.0 --port 8422

Auth: bearer tokens minted by scripts/ops/mint_a2a_gateway_token.py.
Broker: connects lazily per request-burst to $NATS_URL (default local), with
NATS_USER/NATS_PASSWORD if set — on the hub host itself, a local no-auth or
gateway-account connection is expected.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from fastapi import FastAPI  # noqa: E402
from fastapi.responses import JSONResponse  # noqa: E402

from dharma_swarm.a2a.mailbox_gateway import (  # noqa: E402
    STREAM_NAME,
    init_mailbox_gateway,
    router,
)


class _LiveBroker:
    """MailboxBrokerLike over a real nats-py connection.

    One instance per request. The connection stays open across
    fetch_inbox() AND the router's subsequent msg.ack() calls — acks travel
    over this same connection, so closing early would strand them (Codex P1,
    2026-07-09). The router calls close() after the drain completes.
    """

    def __init__(self, url: str, user: str, password: str) -> None:
        self._url, self._user, self._password = url, user, password
        self._nc: Any = None

    async def _js(self):
        if self._nc is None or self._nc.is_closed:
            import nats

            kwargs: dict[str, Any] = {"servers": [self._url], "allow_reconnect": False}
            if self._user:
                kwargs["user"] = self._user
                kwargs["password"] = self._password
            self._nc = await nats.connect(**kwargs)
        return self._nc.jetstream()

    async def publish(self, subject: str, payload: bytes) -> Any:
        js = await self._js()
        return await js.publish(subject, payload, timeout=5.0)

    async def fetch_inbox(self, subject: str, durable: str, batch: int) -> list[Any]:
        import asyncio

        js = await self._js()
        sub = await js.pull_subscribe(subject, durable=durable, stream=STREAM_NAME)
        try:
            return list(await sub.fetch(batch, timeout=3.0))
        except asyncio.TimeoutError:
            # nats-py signals an empty pull with TimeoutError; anything
            # else (permission violation, wrong stream, durable conflict)
            # must propagate so the HTTP layer returns an honest 502.
            return []

    async def close(self) -> None:
        if self._nc is not None and not self._nc.is_closed:
            await self._nc.close()


async def _broker_factory() -> _LiveBroker:
    return _LiveBroker(
        os.environ.get("NATS_URL", "nats://127.0.0.1:4222"),
        os.environ.get("NATS_USER", ""),
        os.environ.get("NATS_PASSWORD", ""),
    )


app = FastAPI(title="dharma a2a mailbox gateway")
app.include_router(router)
init_mailbox_gateway(_broker_factory)


@app.get("/health")
async def health() -> JSONResponse:
    return JSONResponse({"ok": True, "service": "a2a-mailbox-gateway", "stream": STREAM_NAME})
