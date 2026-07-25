"""Registered agent presence projection for the repo context graph."""
from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dharma_swarm.daemon_config import dharma_state_dir

logger = logging.getLogger(__name__)

REGISTERED_AGENT_UIDS = [
    "codex_composer",
    "fable_composer",
    "fable_claude_code",
    "hermes-m5",
    "devin-roaming-2987d222",
    "fable_5_cursor",
    "perplexity-computer",
    "kestrel",
]

_ALIASES = {
    "hermes-m5": ["hermes-m5", "hermes_m5", "hermes"],
    "devin": ["devin-roaming-2987d222"],
}


@dataclass(frozen=True)
class AgentPresence:
    agent_uid: str
    status: str
    heartbeat_status: str
    last_seen_at: str
    age_hours: float | None
    source_path: str
    callsign: str = ""
    harness: str = ""
    model: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def list_agent_presence(
    *,
    agents_root: Path | None = None,
    a2a_bus_root: Path | None = None,
    now: datetime | None = None,
) -> list[AgentPresence]:
    root = agents_root or (dharma_state_dir("DHARMA_HOME") / "agents")
    bus = a2a_bus_root or (dharma_state_dir("DHARMA_HOME") / "a2a_bus")
    current = now or datetime.now(timezone.utc)
    roster = _load_agents_json(bus / "agents.json")
    heartbeats = _load_agents_json(bus / "heartbeats.json")
    uids = sorted(set(REGISTERED_AGENT_UIDS) | set(roster) | set(heartbeats))
    return [_read_presence(uid, root, current, roster.get(uid, {}), heartbeats.get(uid, {})) for uid in uids]


def _read_presence(
    uid: str,
    root: Path,
    now: datetime,
    roster_entry: dict[str, Any] | None = None,
    heartbeat_entry: dict[str, Any] | None = None,
) -> AgentPresence:
    roster_entry = roster_entry or {}
    heartbeat_entry = heartbeat_entry or {}
    agent_dir = _resolve_agent_dir(uid, root)
    if agent_dir is None:
        last_seen = str(heartbeat_entry.get("last_seen") or roster_entry.get("last_seen") or "")
        age = _age_hours(last_seen, now)
        return AgentPresence(
            agent_uid=uid,
            status=str(heartbeat_entry.get("status") or roster_entry.get("status") or "missing"),
            heartbeat_status="RED" if age is None or age > 2 else "GREEN",
            last_seen_at=last_seen,
            age_hours=round(age, 3) if age is not None else None,
            source_path=str(root / uid if not roster_entry else "a2a_bus/agents.json"),
            callsign=str(roster_entry.get("callsign") or uid),
            harness=str(roster_entry.get("harness") or roster_entry.get("type") or ""),
            model=str(roster_entry.get("model") or roster_entry.get("model_identity") or ""),
        )
    payload, source = _load_first_json(
        [agent_dir / "living_agent.json", agent_dir / "identity.json", agent_dir / "last_receipt.json"]
    )
    last_seen = str(heartbeat_entry.get("last_seen") or roster_entry.get("last_seen") or "") or _first_str(
        payload,
        ["last_seen_at", "updated_at", "last_active", "created_at", "timestamp"],
    )
    if not last_seen:
        last_seen = _mtime_iso(source)
    age = _age_hours(last_seen, now)
    heartbeat = "GREEN"
    if age is None or age > 2:
        heartbeat = "RED"
    status = str(heartbeat_entry.get("status") or payload.get("status") or roster_entry.get("status") or payload.get("l4_status") or "registered")
    current_embodiment = payload.get("current_embodiment") if isinstance(payload.get("current_embodiment"), dict) else {}
    return AgentPresence(
        agent_uid=uid,
        status=status,
        heartbeat_status=heartbeat,
        last_seen_at=last_seen,
        age_hours=round(age, 3) if age is not None else None,
        source_path=str(source),
        callsign=str(payload.get("callsign") or roster_entry.get("callsign") or current_embodiment.get("callsign") or uid),
        harness=str(payload.get("harness") or roster_entry.get("harness") or roster_entry.get("type") or current_embodiment.get("harness") or ""),
        model=str(payload.get("model") or roster_entry.get("model_identity") or current_embodiment.get("model") or ""),
    )


def _load_agents_json(path: Path) -> dict[str, dict[str, Any]]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        logger.warning("failed to read agent roster JSON from %s: %s", path, exc)
        return {}
    agents = payload.get("agents") if isinstance(payload, dict) else None
    if not isinstance(agents, dict):
        return {}
    return {str(uid): entry for uid, entry in agents.items() if isinstance(entry, dict)}


def _resolve_agent_dir(uid: str, root: Path) -> Path | None:
    for name in _ALIASES.get(uid, [uid]):
        candidate = root / name
        if candidate.exists():
            return candidate
    return None


def _load_first_json(paths: list[Path]) -> tuple[dict[str, Any], Path]:
    for path in paths:
        if not path.exists():
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            logger.warning("failed to read agent presence JSON from %s: %s", path, exc)
            payload = {}
        return (payload if isinstance(payload, dict) else {}, path)
    return {}, paths[0]


def _first_str(payload: dict[str, Any], keys: list[str]) -> str:
    for key in keys:
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value
    return ""


def _mtime_iso(path: Path) -> str:
    try:
        return datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).isoformat()
    except OSError:
        return ""


def _age_hours(value: str, now: datetime) -> float | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return max(0.0, (now - parsed.astimezone(timezone.utc)).total_seconds() / 3600.0)
