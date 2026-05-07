"""Intent-plan payload builder — wires IntentRouter, KnowledgeStore,
and MissionState into a single inspectable intent-to-work-packet.

Usage:
    dgc intent-plan "add dark mode to the dashboard" --json

This is a read-only, non-executing command.  It shows what the system
*would* do with a prompt: intent classification, skill routing, task
decomposition, matched prescriptions, and active mission context.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

INTENT_PLAN_VERSION = "v1"
INTENT_PLAN_DOMAIN = "intent_plan"

_KNOWLEDGE_DB = Path.home() / ".dharma" / "state" / "knowledge.db"


def build_intent_plan(
    prompt: str,
    *,
    knowledge_db: str | Path | None = None,
    mission_path: str | Path | None = None,
) -> dict[str, Any]:
    """Build a structured intent-plan packet from a raw operator prompt.

    Calls existing pieces without executing any work:
      1. terminal_bridge intent classification (kind, confidence)
      2. IntentRouter decomposition (skill, complexity, risk, sub-tasks)
      3. KnowledgeStore prescription lookup (learned skills)
      4. Active mission/campaign context loading

    Returns a JSON-serializable dict.
    """
    result: dict[str, Any] = {
        "version": INTENT_PLAN_VERSION,
        "domain": INTENT_PLAN_DOMAIN,
        "prompt": prompt,
    }

    # 1. Bridge-level intent classification
    result["bridge_intent"] = _classify_bridge_intent(prompt)

    # 2. IntentRouter decomposition
    result["routing"] = _route_and_decompose(prompt)

    # 3. Prescription lookup
    result["prescriptions"] = _lookup_prescriptions(
        prompt,
        result["routing"].get("tags", []),
        knowledge_db=knowledge_db,
    )

    # 4. Mission context
    result["mission"] = _load_mission_context(mission_path=mission_path)

    return result


def _classify_bridge_intent(prompt: str) -> dict[str, Any]:
    """Classify prompt using bridge-style heuristics (standalone).

    Reproduces the key intent classification from
    TerminalBridge._resolve_prompt_intent without needing a live bridge.
    """
    import re

    text = prompt.strip()
    lowered = text.lower()

    if not text:
        return {"kind": "chat", "confidence": "low", "reason": "empty prompt"}
    if text.startswith("/"):
        cmd = text[1:].split(None, 1)[0].lower()
        return {"kind": "command", "confidence": "high", "command": cmd,
                "reason": "explicit slash command"}
    if re.search(r"\b(who are you|what are you|what can you do)\b", lowered):
        return {"kind": "identity", "confidence": "high",
                "reason": "identity-orientation request"}
    if re.search(r"\b(compact|summarize session|save session|checkpoint)\b", lowered):
        return {"kind": "memory", "confidence": "medium",
                "reason": "session memory request"}
    if any(t in lowered for t in ("subagent", "delegate", "agent swarm")):
        return {"kind": "agent", "confidence": "medium",
                "reason": "agent-orchestration request"}
    if any(t in lowered for t in ("evolve", "improve yourself", "cascade")):
        return {"kind": "evolution", "confidence": "medium",
                "reason": "self-improvement request"}

    command_map = {
        "runtime": ("runtime", "control plane", "runtime status"),
        "status": ("status", "health", "pulse", "doctor"),
        "git": ("git", "repo status", "branch", "diff"),
        "memory": ("memory", "archive", "notes", "remember"),
        "foundations": ("ontology", "foundations", "telos", "dharma concepts"),
        "swarm": ("swarm", "agents", "delegation", "subagent"),
        "context": ("context", "orientation", "brief me"),
    }
    if re.match(r"^(show|run|open|check|view|inspect|brief)\b", lowered):
        for cmd, phrases in command_map.items():
            if any(p in lowered for p in phrases):
                return {"kind": "command", "confidence": "medium",
                        "command": cmd, "reason": "plain-language operator command"}

    return {"kind": "chat", "confidence": "medium",
            "reason": "default conversational turn"}


def _route_and_decompose(prompt: str) -> dict[str, Any]:
    """Run IntentRouter analysis + decomposition."""
    try:
        from dharma_swarm.intent_router import IntentRouter

        router = IntentRouter(enable_semantic=True)
        decomposed = router.decompose(prompt)
        return decomposed.model_dump()
    except Exception as exc:
        return {"error": str(exc)}


def _lookup_prescriptions(
    prompt: str,
    tags: list[str],
    *,
    knowledge_db: str | Path | None = None,
) -> list[dict[str, Any]]:
    """Find matching prescriptions (learned skills) for the prompt."""
    db_path = str(knowledge_db or _KNOWLEDGE_DB)
    try:
        from dharma_swarm.knowledge_units import KnowledgeStore

        if not Path(db_path).exists():
            return []
        with KnowledgeStore(db_path) as store:
            concepts = tags if tags else prompt.lower().split()[:10]
            prescriptions = store.get_prescriptions_for_intent(prompt, concepts)
            return [p.to_dict() for p in prescriptions]
    except Exception as exc:
        return [{"error": str(exc)}]


def _load_mission_context(
    *,
    mission_path: str | Path | None = None,
) -> dict[str, Any]:
    """Load active mission and campaign state."""
    try:
        from dharma_swarm.mission_contract import (
            load_active_campaign_state,
            load_active_mission_state,
        )

        mission_ctx: dict[str, Any] = {}

        mission_art = load_active_mission_state(path=mission_path)
        if mission_art:
            mission_ctx["mission"] = mission_art.state.model_dump()
            mission_ctx["mission_source"] = mission_art.source_kind

        campaign_art = load_active_campaign_state()
        if campaign_art:
            mission_ctx["campaign"] = campaign_art.state.model_dump()
            mission_ctx["campaign_source"] = campaign_art.source_kind

        return mission_ctx if mission_ctx else {"active": False}
    except Exception as exc:
        return {"error": str(exc)}
