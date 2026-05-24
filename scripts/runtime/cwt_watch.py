#!/usr/bin/env python3
"""CONTROL_WATCH_TOWER v1 append-only watch primitives.

This is the live edge for CWT: events, incidents, AOTAMs, lost-comms scans,
and reputation score upserts. It does not promote agents, dispatch work,
merge branches, push code, or grant authority.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


DEFAULT_STATE_ROOT = Path.home() / ".dharma"
WATCH_EVENT_SCHEMA = "control_watch_tower_watch_event.v1"
INCIDENT_SCHEMA = "control_watch_tower_incident.v1"
AOTAM_SCHEMA = "control_watch_tower_aotam.v1"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def parse_time(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        normalized = value.replace("Z", "+00:00")
        parsed = datetime.fromisoformat(normalized)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except ValueError:
        return None


def short_hash(value: str, length: int = 16) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:length]


def append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=True, sort_keys=True, default=str) + "\n")


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            stripped = line.strip()
            if not stripped:
                continue
            try:
                value = json.loads(stripped)
            except json.JSONDecodeError:
                continue
            if isinstance(value, dict):
                rows.append(value)
    return rows


def cwt_root(state_root: Path) -> Path:
    return state_root / "control_watch_tower"


def global_events_path(state_root: Path) -> Path:
    return cwt_root(state_root) / "watch_events.jsonl"


def incidents_path(state_root: Path) -> Path:
    return cwt_root(state_root) / "incidents.jsonl"


def aotams_path(state_root: Path) -> Path:
    return cwt_root(state_root) / "aotams.jsonl"


def per_agent_events_path(state_root: Path, agent_uid: str) -> Path | None:
    external = state_root / "external_agents" / agent_uid
    if external.exists():
        return external / "watch" / "events.jsonl"
    canonical = state_root / "agents" / agent_uid
    if canonical.exists():
        return canonical / "watch" / "events.jsonl"
    return None


def emit_kaizen_event(
    *,
    state_root: Path,
    category: str,
    source: str,
    status: str,
    metadata: dict[str, Any],
) -> None:
    db_path = state_root / "kaizen" / "ops.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    now = utc_now()
    con = sqlite3.connect(db_path)
    try:
        con.execute(
            "CREATE TABLE IF NOT EXISTS events ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, timestamp TEXT NOT NULL, "
            "category TEXT NOT NULL, source TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'ok', "
            "duration_sec REAL DEFAULT 0.0, metadata TEXT DEFAULT '{}', created_at TEXT NOT NULL)"
        )
        con.execute(
            "INSERT INTO events (timestamp, category, source, status, duration_sec, metadata, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                now,
                category,
                source,
                status,
                0.0,
                json.dumps(metadata, ensure_ascii=True, sort_keys=True, default=str),
                now,
            ),
        )
        con.commit()
    finally:
        con.close()


def append_watch_event(
    *,
    state_root: Path,
    agent_uid: str,
    event_type: str,
    status: str = "ok",
    summary: str,
    source: str = "control_watch_tower",
    trace_id: str = "",
    metadata: dict[str, Any] | None = None,
    kaizen: bool = True,
) -> dict[str, Any]:
    now = utc_now()
    event = {
        "schema_version": WATCH_EVENT_SCHEMA,
        "event_id": short_hash(f"{agent_uid}:{event_type}:{now}:{summary}"),
        "timestamp": now,
        "agent_uid": agent_uid,
        "event_type": event_type,
        "status": status,
        "summary": summary,
        "source": source,
        "trace_id": trace_id,
        "metadata": metadata or {},
    }
    append_jsonl(global_events_path(state_root), event)
    per_agent_path = per_agent_events_path(state_root, agent_uid)
    if per_agent_path is not None:
        append_jsonl(per_agent_path, event)
    if kaizen:
        emit_kaizen_event(
            state_root=state_root,
            category="external_agent_watch",
            source=agent_uid,
            status=status,
            metadata={
                "event_id": event["event_id"],
                "event_type": event_type,
                "trace_id": trace_id,
                "summary": summary,
            },
        )
    return event


def append_incident(
    *,
    state_root: Path,
    agent_uid: str,
    severity: str,
    summary: str,
    kind: str = "near_miss",
    status: str = "open",
    trace_id: str = "",
    evidence_refs: list[str] | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    now = utc_now()
    incident = {
        "schema_version": INCIDENT_SCHEMA,
        "incident_id": short_hash(f"incident:{agent_uid}:{severity}:{now}:{summary}"),
        "opened_at": now,
        "updated_at": now,
        "agent_uid": agent_uid,
        "kind": kind,
        "severity": severity,
        "status": status,
        "summary": summary,
        "trace_id": trace_id,
        "evidence_refs": evidence_refs or [],
        "metadata": metadata or {},
    }
    append_jsonl(incidents_path(state_root), incident)
    append_watch_event(
        state_root=state_root,
        agent_uid=agent_uid,
        event_type="incident_opened",
        status="warn" if severity in {"low", "medium"} else "critical",
        summary=summary,
        source="control_watch_tower.incident",
        trace_id=trace_id,
        metadata={"incident_id": incident["incident_id"], "severity": severity, "kind": kind},
    )
    return incident


def append_aotam(
    *,
    state_root: Path,
    aotam_id: str,
    issuer: str,
    scope: str,
    hazard: str,
    required_agent_action: str,
    affected_agents: list[str] | None = None,
    expires_at: str = "",
    evidence_refs: list[str] | None = None,
) -> dict[str, Any]:
    now = utc_now()
    aotam = {
        "schema_version": AOTAM_SCHEMA,
        "aotam_id": aotam_id,
        "issued_at": now,
        "issuer": issuer,
        "scope": scope,
        "affected_agents": affected_agents or [],
        "hazard": hazard,
        "effective_from": now,
        "expires_at": expires_at,
        "required_agent_action": required_agent_action,
        "evidence_refs": evidence_refs or [],
        "status": "active",
    }
    append_jsonl(aotams_path(state_root), aotam)
    for agent_uid in affected_agents or []:
        append_watch_event(
            state_root=state_root,
            agent_uid=agent_uid,
            event_type="aotam_issued",
            status="warn",
            summary=hazard,
            source="control_watch_tower.aotam",
            metadata={"aotam_id": aotam_id, "required_agent_action": required_agent_action},
        )
    return aotam


def upsert_reputation(
    *,
    state_root: Path,
    agent_uid: str,
    overall_score: float,
    trust_band: str,
    dimensions: dict[str, float] | None = None,
    source: str = "control_watch_tower",
) -> dict[str, Any]:
    db_path = state_root / "state" / "runtime.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    now = utc_now()
    evidence_json = json.dumps(
        [
            {
                "source": source,
                "dimensions": dimensions or {},
                "updated_at": now,
            }
        ],
        ensure_ascii=True,
        sort_keys=True,
    )
    con = sqlite3.connect(db_path)
    try:
        con.execute(
            "CREATE TABLE IF NOT EXISTS agent_reputation ("
            "agent_id TEXT PRIMARY KEY, reputation REAL NOT NULL DEFAULT 0.0, "
            "trust_band TEXT NOT NULL DEFAULT 'unknown', last_reason TEXT NOT NULL DEFAULT '', "
            "evidence_json TEXT NOT NULL DEFAULT '[]', updated_at TEXT NOT NULL)"
        )
        cols = {row[1] for row in con.execute("PRAGMA table_info(agent_reputation)").fetchall()}
        if "agent_id" in cols:
            con.execute(
                "INSERT INTO agent_reputation (agent_id, reputation, trust_band, last_reason, evidence_json, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?) "
                "ON CONFLICT(agent_id) DO UPDATE SET reputation=excluded.reputation, "
                "trust_band=excluded.trust_band, last_reason=excluded.last_reason, "
                "evidence_json=excluded.evidence_json, updated_at=excluded.updated_at",
                (
                    agent_uid,
                    float(overall_score),
                    trust_band,
                    source,
                    evidence_json,
                    now,
                ),
            )
        else:
            con.execute(
                "INSERT INTO agent_reputation (agent_uid, overall_score, trust_band, dimensions_json, source, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?) "
                "ON CONFLICT(agent_uid) DO UPDATE SET overall_score=excluded.overall_score, "
                "trust_band=excluded.trust_band, dimensions_json=excluded.dimensions_json, "
                "source=excluded.source, updated_at=excluded.updated_at",
                (
                    agent_uid,
                    float(overall_score),
                    trust_band,
                    json.dumps(dimensions or {}, ensure_ascii=True, sort_keys=True),
                    source,
                    now,
                ),
            )
        con.commit()
    finally:
        con.close()
    event = append_watch_event(
        state_root=state_root,
        agent_uid=agent_uid,
        event_type="reputation_upserted",
        status="ok",
        summary=f"reputation={overall_score:.3f}, trust_band={trust_band}",
        source=source,
        metadata={"overall_score": float(overall_score), "trust_band": trust_band, "dimensions": dimensions or {}},
    )
    return {"agent_uid": agent_uid, "overall_score": float(overall_score), "trust_band": trust_band, "event_id": event["event_id"]}


def latest_agent_event(state_root: Path, agent_uid: str) -> dict[str, Any] | None:
    rows = [
        row
        for row in read_jsonl(global_events_path(state_root))
        if row.get("agent_uid") == agent_uid
    ]
    if not rows:
        return None
    rows.sort(key=lambda row: str(row.get("timestamp", "")), reverse=True)
    return rows[0]


def latest_agent_activity_time(state_root: Path, agent_uid: str) -> datetime | None:
    paths = [
        state_root / "external_agents" / agent_uid / "logs" / "action_log.jsonl",
        state_root / "external_agents" / agent_uid / "logs" / "wake_receipts.jsonl",
        state_root / "agents" / agent_uid / "task_log.jsonl",
    ]
    per_agent = per_agent_events_path(state_root, agent_uid)
    if per_agent is not None:
        paths.append(per_agent)
    latest: datetime | None = None
    for path in paths:
        if not path.exists() or not path.is_file():
            continue
        stamp = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
        if latest is None or stamp > latest:
            latest = stamp
    return latest


def discover_watched_agents(state_root: Path) -> list[str]:
    agents: set[str] = set()
    for root in (state_root / "external_agents", state_root / "agents"):
        if not root.exists():
            continue
        for path in root.iterdir():
            if path.is_dir():
                agents.add(path.name)
    return sorted(agents)


def lost_comms_scan(
    *,
    state_root: Path,
    max_age_hours: float,
    now: datetime | None = None,
) -> list[dict[str, Any]]:
    current = now or datetime.now(timezone.utc)
    cutoff = current - timedelta(hours=max_age_hours)
    emitted: list[dict[str, Any]] = []
    for agent_uid in discover_watched_agents(state_root):
        activity = latest_agent_activity_time(state_root, agent_uid)
        latest_event = latest_agent_event(state_root, agent_uid)
        latest_type = str((latest_event or {}).get("event_type", ""))
        if activity is None or activity < cutoff:
            if latest_type != "lost_comms":
                age = "never" if activity is None else activity.isoformat()
                emitted.append(
                    append_watch_event(
                        state_root=state_root,
                        agent_uid=agent_uid,
                        event_type="lost_comms",
                        status="warn",
                        summary=f"no observed activity since {age}",
                        source="control_watch_tower.lost_comms_scan",
                        metadata={"max_age_hours": max_age_hours, "last_activity_at": age},
                    )
                )
        elif latest_type == "lost_comms":
            emitted.append(
                append_watch_event(
                    state_root=state_root,
                    agent_uid=agent_uid,
                    event_type="comms_restored",
                    status="ok",
                    summary=f"activity observed at {activity.isoformat()}",
                    source="control_watch_tower.lost_comms_scan",
                    metadata={"max_age_hours": max_age_hours, "last_activity_at": activity.isoformat()},
                )
            )
    return emitted


def parse_metadata(raw: str) -> dict[str, Any]:
    if not raw:
        return {}
    value = json.loads(raw)
    if not isinstance(value, dict):
        raise SystemExit("--metadata-json must be a JSON object")
    return value


def parse_dimensions(raw: list[str]) -> dict[str, float]:
    out: dict[str, float] = {}
    for item in raw:
        if "=" not in item:
            raise SystemExit("--dimension entries must use name=value")
        key, value = item.split("=", 1)
        out[key.strip()] = float(value)
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description="CONTROL_WATCH_TOWER v1 append-only watch CLI")
    parser.add_argument("--state-root", type=Path, default=DEFAULT_STATE_ROOT)
    sub = parser.add_subparsers(dest="command", required=True)

    event = sub.add_parser("event")
    event.add_argument("--agent-uid", required=True)
    event.add_argument("--event-type", required=True)
    event.add_argument("--status", default="ok")
    event.add_argument("--summary", required=True)
    event.add_argument("--source", default="control_watch_tower.cli")
    event.add_argument("--trace-id", default="")
    event.add_argument("--metadata-json", default="")

    incident = sub.add_parser("incident")
    incident.add_argument("--agent-uid", required=True)
    incident.add_argument("--severity", choices=["low", "medium", "high", "critical"], required=True)
    incident.add_argument("--summary", required=True)
    incident.add_argument("--kind", choices=["near_miss", "mandatory"], default="near_miss")
    incident.add_argument("--trace-id", default="")

    aotam = sub.add_parser("aotam")
    aotam.add_argument("--aotam-id", required=True)
    aotam.add_argument("--issuer", required=True)
    aotam.add_argument("--scope", required=True)
    aotam.add_argument("--hazard", required=True)
    aotam.add_argument("--required-agent-action", required=True)
    aotam.add_argument("--affected-agent", action="append", default=[])
    aotam.add_argument("--expires-at", default="")

    reputation = sub.add_parser("reputation")
    reputation.add_argument("--agent-uid", required=True)
    reputation.add_argument("--overall-score", type=float, required=True)
    reputation.add_argument("--trust-band", required=True)
    reputation.add_argument("--dimension", action="append", default=[])
    reputation.add_argument("--source", default="control_watch_tower.cli")

    lost = sub.add_parser("lost-comms-scan")
    lost.add_argument("--max-age-hours", type=float, default=24.0)

    args = parser.parse_args()
    state_root = args.state_root.expanduser()
    if args.command == "event":
        result = append_watch_event(
            state_root=state_root,
            agent_uid=args.agent_uid,
            event_type=args.event_type,
            status=args.status,
            summary=args.summary,
            source=args.source,
            trace_id=args.trace_id,
            metadata=parse_metadata(args.metadata_json),
        )
    elif args.command == "incident":
        result = append_incident(
            state_root=state_root,
            agent_uid=args.agent_uid,
            severity=args.severity,
            summary=args.summary,
            kind=args.kind,
            trace_id=args.trace_id,
        )
    elif args.command == "aotam":
        result = append_aotam(
            state_root=state_root,
            aotam_id=args.aotam_id,
            issuer=args.issuer,
            scope=args.scope,
            hazard=args.hazard,
            required_agent_action=args.required_agent_action,
            affected_agents=args.affected_agent,
            expires_at=args.expires_at,
        )
    elif args.command == "reputation":
        result = upsert_reputation(
            state_root=state_root,
            agent_uid=args.agent_uid,
            overall_score=args.overall_score,
            trust_band=args.trust_band,
            dimensions=parse_dimensions(args.dimension),
            source=args.source,
        )
    else:
        result = {"emitted": lost_comms_scan(state_root=state_root, max_age_hours=args.max_age_hours)}
    print(json.dumps(result, indent=2, ensure_ascii=True, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
