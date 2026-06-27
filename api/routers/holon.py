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

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from dharma_swarm import holon_bridge
from dharma_swarm.conversation_log import log_exchange
from dharma_swarm.holon_persistence import append_talk_receipt, load_talk_receipts

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


def _context_refs(name: str) -> list[str]:
    root = holon_bridge.AGENTS_ROOT / name
    candidates = [
        root / "identity.json",
        root / "living_agent.json",
        root / "service_heartbeats.jsonl",
        root / "transport_heartbeats.jsonl",
        root / "dialogue" / "operator_sessions.jsonl",
        root / "dialogue" / "relationship_memory.jsonl",
        root / "dialogue" / "conversation_receipts",
        root / "sanctum",
    ]
    return [str(path) for path in candidates if path.exists()]


@router.post("/holon/{name}/chat")
async def holon_chat(name: str, req: HolonChatRequest):
    """Stream a reply from the holon's OWN model. Never delegates to _agentic_stream."""
    if not _HOLON_NAME_RE.fullmatch(name):
        raise HTTPException(status_code=404, detail="no registered holon by that name")
    # replace() chain after the regex gate: the sanitizer shape CodeQL's
    # log-injection taint tracking recognizes (the fullmatch guard alone is not).
    name = name.replace("\r", "").replace("\n", "")
    try:
        holon = holon_bridge.load_holon(name)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=f"no registered holon: {name}") from exc
    except ValueError as exc:  # malformed identity.json / no model
        logger.error("[holon] %s: identity load failed: %s", name, exc)
        raise HTTPException(status_code=500, detail="holon identity is malformed") from exc

    try:
        dialogue_context = holon_bridge.build_livingdock_dialogue_context(holon)
        provider = holon_bridge.get_holon_dialogue_provider(holon)
    except holon_bridge.HolonDialogueProviderError as exc:
        logger.warning(
            "[holon] %s read-only chat provider refused: %s",
            name,
            exc,
        )
        raise HTTPException(
            status_code=409,
            detail="holon read-only chat has no safe non-agentic provider",
        ) from exc
    served_provider = str(getattr(provider, "runtime_provider_type", "") or "")
    served_model = str(getattr(provider, "runtime_default_model", "") or holon.model)
    session_id = f"holon-{name}"
    meta = {"holon": name, "model": holon.model, "served_provider": served_provider, "served_model": served_model}
    log_exchange("user", req.message, interface="holon", session_id=session_id, metadata=meta)

    async def stream():
        yield _sse({"session_id": session_id, "holon": name, "model": holon.model})
        collected: list[str] = []
        provider_error = ""
        try:
            async for chunk in holon_bridge.holon_reply(
                holon,
                req.message,
                provider,
                req.history,
                livingdock_context=dialogue_context.content,
                request_model=served_model or holon.model,
            ):
                collected.append(chunk)
                yield _sse({"content": chunk})
        except Exception as exc:  # provider failure mid-stream — surface, don't crash the conn
            logger.warning("[holon] %s reply error: %s", name, exc, exc_info=True)
            provider_error = type(exc).__name__
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
        receipt: dict[str, Any] = {}
        try:
            receipt = append_talk_receipt(
                name,
                {
                    "session_id": session_id,
                    "routing_mode": "holon_route",
                    "model": holon.model,
                    "served_provider": served_provider,
                    "served_model": served_model,
                    "dialogue_provider_override": bool(
                        getattr(provider, "holon_dialogue_provider_override", False)
                    ),
                    "you": req.message,
                    "reply": reply_text,
                    "context_refs": dialogue_context.evidence_paths or _context_refs(name),
                    "policy_ceiling": "read_only_dialogue_no_privileged_action",
                    "provider_error": provider_error,
                    "follow_up_mission_refs": [],
                    "protected_action_claim": False,
                },
                agents_root=holon_bridge.AGENTS_ROOT,
            )
        except Exception:
            logger.debug("[holon] conversation receipt skipped", exc_info=True)
        yield _sse({"done": True, "conversation_receipt": receipt.get("receipt_path", "")})

    return StreamingResponse(stream(), media_type="text/event-stream")


@router.get("/holon/{name}/chat/history")
async def holon_chat_history(
    name: str,
    limit: int = Query(50, ge=1, le=200),
) -> dict[str, Any]:
    """Return recent LivingDock direct-dialogue receipts for one holon."""
    if not _HOLON_NAME_RE.fullmatch(name):
        raise HTTPException(status_code=404, detail="no registered holon by that name")
    name = name.replace("\r", "").replace("\n", "")
    receipts = load_talk_receipts(name, agents_root=holon_bridge.AGENTS_ROOT, limit=limit)
    return {
        "schema_version": "dharma.holon_chat_history.v1",
        "holon": name,
        "receipt_count": len(receipts),
        "receipts": receipts,
    }
