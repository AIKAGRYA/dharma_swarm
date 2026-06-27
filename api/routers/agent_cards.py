"""Agent Card meishi index endpoints."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter
from fastapi.responses import Response

from api.models import ApiResponse
from dharma_swarm.a2a.agent_card_exports import export_agent_card, public_agent_card
from dharma_swarm.a2a.agent_card_index import build_agent_card_index
from dharma_swarm.daemon_config import dharma_state_dir

router = APIRouter(prefix="/api", tags=["agent-cards"])

REPO_ROOT = Path(__file__).resolve().parents[2]


def _build_index() -> dict[str, Any]:
    return build_agent_card_index(
        repo_root=REPO_ROOT,
        dharma_home=dharma_state_dir("DHARMA_HOME"),
    )


def _matches_agent(agent: dict[str, Any], lookup: str) -> bool:
    normalized = lookup.strip().lower().replace("-", "_")
    values = [
        str(agent.get("agent_uid") or ""),
        str(agent.get("display_name") or ""),
        str(agent.get("callsign") or ""),
        *[str(item) for item in agent.get("card_names", []) if item],
    ]
    for value in values:
        clean = value.strip().lower()
        if clean == lookup.strip().lower() or clean.replace("-", "_") == normalized:
            return True
    return False


def _find_agent(index: dict[str, Any], agent_uid: str) -> dict[str, Any] | None:
    for agent in index.get("agents", []):
        if isinstance(agent, dict) and _matches_agent(agent, agent_uid):
            return agent
    return None


@router.get("/agent-cards")
async def list_agent_cards() -> ApiResponse:
    try:
        index = _build_index()
        return ApiResponse(data={"summary": index["summary"], "agents": index["agents"]})
    except Exception as exc:
        return ApiResponse(status="error", error=str(exc), data={})


@router.get("/agent-cards/{agent_uid}")
async def get_agent_card(agent_uid: str) -> ApiResponse:
    try:
        index = _build_index()
        agent = _find_agent(index, agent_uid)
        if agent is not None:
            return ApiResponse(data=agent)
        return ApiResponse(status="error", error=f"Agent card not found: {agent_uid}", data={})
    except Exception as exc:
        return ApiResponse(status="error", error=str(exc), data={})


@router.get("/agent-cards/{agent_uid}/public")
async def get_public_agent_card(agent_uid: str) -> ApiResponse:
    try:
        index = _build_index()
        agent = _find_agent(index, agent_uid)
        if agent is not None:
            return ApiResponse(data=public_agent_card(agent))
        return ApiResponse(status="error", error=f"Agent card not found: {agent_uid}", data={})
    except Exception as exc:
        return ApiResponse(status="error", error=str(exc), data={})


@router.get("/agent-cards/{agent_uid}/exports/{export_format}")
async def export_agent_card_endpoint(agent_uid: str, export_format: str) -> Response:
    try:
        index = _build_index()
        agent = _find_agent(index, agent_uid)
        if agent is None:
            return Response(
                content=f"Agent card not found: {agent_uid}\n",
                status_code=404,
                media_type="text/plain; charset=utf-8",
            )
        body, media_type, extension = export_agent_card(agent, export_format)
        safe_uid = str(agent.get("agent_uid") or agent_uid).replace("/", "_")
        return Response(
            content=body,
            media_type=media_type,
            headers={
                "Content-Disposition": f'attachment; filename="{safe_uid}.{extension}"'
            },
        )
    except ValueError as exc:
        return Response(
            content=str(exc) + "\n",
            status_code=400,
            media_type="text/plain; charset=utf-8",
        )
    except Exception as exc:
        return Response(
            content=str(exc) + "\n",
            status_code=500,
            media_type="text/plain; charset=utf-8",
        )
