"""Read-only sovereign holon chat route — talk to a registered agent AS ITSELF.

Unlike the cosmetic ``/agents/{id}/chat`` (which runs the operator's global model with a
persona string and delegates to ``_agentic_stream``), this route loads the agent's OWN
model + prompt + identity via ``holon_bridge`` and streams from THAT model. It never imports
or calls ``_agentic_stream``. Read-only: no tools, no governance enforcement (Step 3).

Persistence reuses existing owners: ``conversation_log.log_exchange(interface="holon")`` —
no new ``holon_witness/`` tree (active-track non-goal). See AGENT_HOME_RECONCILIATION.md.
"""
from __future__ import annotations

import json
import logging
import re
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from dharma_swarm import holon_bridge
from dharma_swarm.conversation_log import log_exchange

logger = logging.getLogger(__name__)
router = APIRouter()

# System-boundary validation: holon names are registry directory names. Rejecting
# anything else here cuts the user-controlled taint for every downstream logger
# (router, holon_bridge, holon_compass) and blocks path traversal into the registry.
_HOLON_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_\-.]{0,63}$")


class HolonChatRequest(BaseModel):
    message: str
    history: list[dict[str, Any]] = []


def _sse(obj: dict) -> str:
    return f"data: {json.dumps(obj, ensure_ascii=False)}\n\n"


@router.post("/holon/{name}/chat")
async def holon_chat(name: str, req: HolonChatRequest):
    """Stream a reply from the holon's OWN model. Never delegates to _agentic_stream."""
    if not _HOLON_NAME_RE.fullmatch(name):
        raise HTTPException(status_code=404, detail="no registered holon by that name")
    try:
        holon = holon_bridge.load_holon(name)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=f"no registered holon: {name}") from exc
    except ValueError as exc:  # malformed identity.json / no model
        logger.error("[holon] %s: identity load failed: %s", name, exc)
        raise HTTPException(status_code=500, detail="holon identity is malformed") from exc

    provider = holon_bridge.get_holon_provider(holon)
    session_id = f"holon-{name}"
    meta = {"holon": name, "model": holon.model}
    log_exchange("user", req.message, interface="holon", session_id=session_id, metadata=meta)

    async def stream():
        yield _sse({"session_id": session_id, "holon": name, "model": holon.model})
        collected: list[str] = []
        try:
            async for chunk in holon_bridge.holon_reply(holon, req.message, provider, req.history):
                collected.append(chunk)
                yield _sse({"content": chunk})
        except Exception as exc:  # provider failure mid-stream — surface, don't crash the conn
            logger.warning("[holon] %s reply error: %s", name, exc, exc_info=True)
            # Generic client-facing error: exception text can carry provider URLs,
            # key names, or stack fragments (CodeQL py/stack-trace-exposure).
            yield _sse({"error": "provider error — see server logs"})
        reply_text = "".join(collected)
        log_exchange(
            "assistant", reply_text, interface="holon",
            session_id=session_id, metadata=meta,
        )
        # Step 3a compass: non-binding telos signal (best-effort; never blocks the chat).
        try:
            from dharma_swarm.holon_compass import log_signal
            log_signal(name, req.message, reply_text)
        except Exception:
            logger.debug("[holon] compass signal skipped", exc_info=True)
        yield _sse({"done": True})

    return StreamingResponse(stream(), media_type="text/event-stream")
