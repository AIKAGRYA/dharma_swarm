#!/usr/bin/env python3
"""CONTROL_WATCH_TOWER v0 collector — read-only census of registered agents to scorecards.

Read-only against live runtime state. Writes only the scorecard JSON files under
the chosen output directory. Each scorecard conforms to:
    schemas/control_watch_tower_agent_scorecard.v0.json

Scope per operator-issued work packet (2026-05-21):
    registered agents -> evidence paths -> scorecard skeleton -> report JSON

What this collector intentionally does NOT do:
    - mutate any agent file, runtime.db, kaizen/ops.db, stigmergy marks
    - emit kaizen/stigmergy events
    - read or print secrets
    - score performance beyond structural evidence (presence of files, line counts)
    - render the report (use cwt_report.py for that)
    - propose promotion (all scorecards return recommendation=hold in v0)

Discovers agents from two surfaces:
    ~/.dharma/external_agents/{uid}/  (external workers like Hermes, Claude Code CLI)
    ~/.dharma/agents/{uid}/           (canonical living agents like opus_composer)

Outputs:
    {out-dir}/scorecard_{agent_uid}.json   (one per agent, schema-conformant)
    {out-dir}/scorecards_index.json        (collector summary + scorecard list)
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from dharma_swarm.operator_core.identity_invariant import validate_identity_invariant  # noqa: E402

HOME = Path.home()
DEFAULT_STATE_ROOT = HOME / ".dharma"

SCORECARD_SCHEMA_VERSION = "control_watch_tower_agent_scorecard.v0"

DIMENSION_NAMES = [
    "identity_continuity",
    "wake_persistence",
    "work_capacity",
    "comms_reliability",
    "memory_evolution",
    "operational_value",
    "safety_discipline",
    "cost_discipline",
    "collaboration",
    "promotion_readiness",
]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _count_lines(p: Path) -> int:
    if not p.exists() or not p.is_file():
        return 0
    try:
        with open(p) as f:
            return sum(1 for _ in f)
    except Exception:
        return 0


def _file_last_mtime_iso(p: Path) -> str | None:
    if not p.exists() or not p.is_file():
        return None
    return datetime.fromtimestamp(p.stat().st_mtime, tz=timezone.utc).isoformat()


def _read_json_safe(p: Path) -> dict[str, Any] | None:
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text())
    except Exception:
        return None


def _read_jsonl_safe(p: Path) -> list[dict[str, Any]]:
    if not p.exists() or not p.is_file():
        return []
    rows: list[dict[str, Any]] = []
    try:
        with p.open(encoding="utf-8") as handle:
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
    except Exception:
        return []
    return rows


def _cwt_events(state_root: Path, uid: str) -> list[dict[str, Any]]:
    return [
        row
        for row in _read_jsonl_safe(state_root / "control_watch_tower" / "watch_events.jsonl")
        if row.get("agent_uid") == uid
    ]


def _cwt_incidents(state_root: Path, uid: str) -> list[dict[str, Any]]:
    return [
        row
        for row in _read_jsonl_safe(state_root / "control_watch_tower" / "incidents.jsonl")
        if row.get("agent_uid") == uid and row.get("status", "open") != "closed"
    ]


def _cwt_aotams(state_root: Path, uid: str) -> list[dict[str, Any]]:
    now = datetime.now(timezone.utc)
    out: list[dict[str, Any]] = []
    for row in _read_jsonl_safe(state_root / "control_watch_tower" / "aotams.jsonl"):
        affected = row.get("affected_agents") or []
        if affected and uid not in affected:
            continue
        expires = str(row.get("expires_at") or "")
        if expires:
            try:
                parsed = datetime.fromisoformat(expires.replace("Z", "+00:00"))
                if parsed.tzinfo is None:
                    parsed = parsed.replace(tzinfo=timezone.utc)
                if parsed < now:
                    continue
            except ValueError:
                pass
        if row.get("status", "active") == "active":
            out.append(row)
    return out


def _cwt_reputation(state_root: Path, uid: str) -> dict[str, Any] | None:
    db = state_root / "state" / "runtime.db"
    if not db.exists():
        return None
    try:
        con = sqlite3.connect(db)
        con.row_factory = sqlite3.Row
        cols = {
            row["name"]
            for row in con.execute("PRAGMA table_info(agent_reputation)").fetchall()
        }
        if "agent_id" in cols:
            row = con.execute(
                "SELECT * FROM agent_reputation WHERE agent_id = ?",
                (uid,),
            ).fetchone()
        else:
            row = con.execute(
                "SELECT * FROM agent_reputation WHERE agent_uid = ?",
                (uid,),
            ).fetchone()
        con.close()
        return dict(row) if row else None
    except Exception:
        return None


def _latest_event_type(events: list[dict[str, Any]]) -> str:
    if not events:
        return ""
    ordered = sorted(events, key=lambda row: str(row.get("timestamp", "")), reverse=True)
    return str(ordered[0].get("event_type") or "")


@dataclass
class AgentInventory:
    """All evidence-path locations for one agent, regardless of surface."""

    uid: str
    callsign: str
    surface: str  # "external" or "canonical"
    sandbox_root: Path
    registration: Path
    living_agent: Path
    a2a_card: Path
    action_log: Path
    wake_receipts: Path
    self_model: Path
    agentops_contract: Path
    watch_contract: Path
    authority_passport: Path
    identity_invariant: Path
    soul_md: Path | None
    raw_authority: str


def _build_callsign_from_registration(reg_path: Path, default: str) -> str:
    r = _read_json_safe(reg_path) or {}
    # registration.json has fields at top level; some receipt variants nest under "worker"
    return r.get("callsign") or (r.get("worker") or {}).get("callsign") or default


def _authority_from_registration(reg_path: Path) -> str:
    r = _read_json_safe(reg_path) or {}
    return r.get("authority") or (r.get("worker") or {}).get("authority") or "unknown"


def discover_agents(state_root: Path) -> list[AgentInventory]:
    out: list[AgentInventory] = []
    seen: set[str] = set()

    # 1. External agents (have a dedicated sandbox)
    ext_root = state_root / "external_agents"
    if ext_root.exists():
        for d in sorted(ext_root.iterdir()):
            if not d.is_dir():
                continue
            uid = d.name
            reg = d / "registration.json"
            living_agent = state_root / "agents" / uid / "living_agent.json"
            action_log = d / "logs" / "action_log.jsonl"
            if not reg.exists() and not living_agent.exists():
                continue
            callsign = _build_callsign_from_registration(reg, uid)
            authority = _authority_from_registration(reg)
            out.append(
                AgentInventory(
                    uid=uid,
                    callsign=callsign,
                    surface="external",
                    sandbox_root=d,
                    registration=reg,
                    living_agent=living_agent,
                    a2a_card=state_root / "a2a" / "cards" / f"{callsign}.json",
                    action_log=action_log,
                    wake_receipts=d / "logs" / "wake_receipts.jsonl",
                    self_model=d / "self_model" / "system_interpretation.md",
                    agentops_contract=d / "agentops" / "contract.json",
                    watch_contract=d / "watch" / "contract.json",
                    authority_passport=d / "authority" / "passport.json",
                    identity_invariant=d / "identity_invariant.json",
                    soul_md=None,
                    raw_authority=authority,
                )
            )
            seen.add(uid)

    # 2. Canonical living agents that have no external sandbox (e.g. opus_composer, codex_composer)
    agents_root = state_root / "agents"
    if agents_root.exists():
        for d in sorted(agents_root.iterdir()):
            if not d.is_dir():
                continue
            uid = d.name
            if uid in seen:
                continue
            identity = d / "identity.json"
            iden = _read_json_safe(identity) or {}
            callsign = iden.get("callsign") or uid
            authority = iden.get("authority") or iden.get("authority_mode") or "unknown"
            out.append(
                AgentInventory(
                    uid=uid,
                    callsign=callsign,
                    surface="canonical",
                    sandbox_root=d,
                    registration=identity,
                    living_agent=d / "living_agent.json",
                    a2a_card=state_root / "a2a" / "cards" / f"{callsign}.json",
                    action_log=d / "task_log.jsonl",
                    wake_receipts=Path("/dev/null"),
                    self_model=d / "SOUL.md",
                    agentops_contract=Path("/dev/null"),
                    watch_contract=Path("/dev/null"),
                    authority_passport=state_root / "agent_passports" / f"{uid}.json",
                    identity_invariant=d / "identity_invariant.json",
                    soul_md=d / "SOUL.md",
                    raw_authority=authority,
                )
            )

    return out


def _dim(
    score: float,
    status: str,
    summary: str,
    evidence: list[str],
    last_observed: str | None = None,
) -> dict[str, Any]:
    d: dict[str, Any] = {
        "score": max(0.0, min(1.0, float(score))),
        "status": status,
        "summary": summary,
        "evidence_refs": evidence,
    }
    if last_observed is not None:
        d["last_observed_at"] = last_observed
    return d


def _kaizen_event_count(state_root: Path, uid: str) -> int:
    db = state_root / "kaizen" / "ops.db"
    if not db.exists():
        return 0
    try:
        con = sqlite3.connect(db)
        cur = con.cursor()
        cur.execute("SELECT COUNT(*) FROM events WHERE source = ?", (uid,))
        n = cur.fetchone()[0]
        con.close()
        return int(n)
    except Exception:
        return 0


def _stigmergy_marks_for(state_root: Path, uid: str) -> int:
    marks_path = state_root / "stigmergy" / "marks.jsonl"
    if not marks_path.exists():
        return 0
    n = 0
    try:
        with open(marks_path) as f:
            for line in f:
                if uid in line:
                    n += 1
    except Exception:
        return 0
    return n


def _telemetry_present(state_root: Path, uid: str) -> bool:
    db = state_root / "state" / "runtime.db"
    if not db.exists():
        return False
    try:
        con = sqlite3.connect(db)
        cur = con.cursor()
        cur.execute("SELECT COUNT(*) FROM agent_identity WHERE agent_id = ?", (uid,))
        n = cur.fetchone()[0]
        con.close()
        return n > 0
    except Exception:
        return False


def _identity_invariant_observations(inv: AgentInventory) -> dict[str, Any]:
    observations: list[dict[str, Any]] = []
    for label, path in (
        ("identity_invariant", inv.identity_invariant),
        ("registration", inv.registration),
        ("living_agent", inv.living_agent),
        ("a2a_card", inv.a2a_card),
    ):
        payload = _read_json_safe(path)
        if not payload:
            continue
        if label == "identity_invariant":
            value = payload
        elif label == "a2a_card":
            value = (payload.get("metadata") or {}).get("identity_invariant")
        else:
            value = payload.get("identity_invariant")
        if not isinstance(value, dict):
            continue
        validation = validate_identity_invariant(value)
        errors = list(validation["errors"])
        if value.get("agent_uid") != inv.uid:
            errors.append(
                f"identity_invariant.agent_uid {value.get('agent_uid')!r} does not match {inv.uid!r}"
            )
        observations.append(
            {
                "surface": label,
                "path": str(path),
                "digest": value.get("digest", ""),
                "valid": not errors,
                "errors": errors,
            }
        )
    digests = {row["digest"] for row in observations if row.get("digest")}
    errors = [
        f"{row['surface']}: {', '.join(row['errors'])}"
        for row in observations
        if row.get("errors")
    ]
    if len(digests) > 1:
        errors.append("identity invariant digest mismatch across surfaces")
    return {
        "present_count": len(observations),
        "digests": sorted(digests),
        "observations": observations,
        "valid": bool(observations) and not errors,
        "errors": errors,
        "evidence_refs": [row["path"] for row in observations],
    }


def build_scorecard(inv: AgentInventory, state_root: Path) -> dict[str, Any]:
    evidence_all: list[str] = []
    watch_events = _cwt_events(state_root, inv.uid)
    incidents = _cwt_incidents(state_root, inv.uid)
    aotams = _cwt_aotams(state_root, inv.uid)
    reputation = _cwt_reputation(state_root, inv.uid)
    watch_event_types = {str(event.get("event_type") or "") for event in watch_events}
    cwt_events_path = state_root / "control_watch_tower" / "watch_events.jsonl"
    incidents_file = state_root / "control_watch_tower" / "incidents.jsonl"
    aotams_file = state_root / "control_watch_tower" / "aotams.jsonl"
    reputation_db = state_root / "state" / "runtime.db"

    # D1: identity_continuity — five canonical files
    id_files = [
        inv.registration,
        inv.living_agent,
        inv.a2a_card,
        inv.self_model,
        inv.authority_passport,
    ]
    id_present = sum(1 for f in id_files if f.exists())
    id_evidence = [str(f) for f in id_files if f.exists()]
    invariant = _identity_invariant_observations(inv)
    id_evidence.extend(invariant["evidence_refs"])
    evidence_all.extend(id_evidence)
    id_status = "ok" if id_present >= 4 and invariant["valid"] else ("warn" if id_present >= 2 else "fail")
    d_identity = _dim(
        min(1.0, (id_present / 5) * (1.0 if invariant["valid"] else 0.7)),
        id_status,
        (
            f"{id_present}/5 identity files present; "
            f"{invariant['present_count']} identity invariant surfaces observed"
        ),
        id_evidence,
    )

    # D2: wake_persistence — count of wake_receipts entries
    wake_count = _count_lines(inv.wake_receipts)
    wake_last = _file_last_mtime_iso(inv.wake_receipts)
    if inv.wake_receipts == Path("/dev/null"):
        d_wake = _dim(0.0, "unknown", "canonical agent — wake_receipts not applicable", [])
    else:
        wake_status = "ok" if wake_count >= 5 else ("warn" if wake_count >= 1 else "fail")
        d_wake = _dim(
            min(1.0, wake_count / 10),
            wake_status,
            f"{wake_count} wake receipts on file",
            [str(inv.wake_receipts)] if wake_count else [],
            wake_last,
        )

    # D3: work_capacity — action_log entries
    action_count = _count_lines(inv.action_log)
    cwt_work_events = sum(
        1
        for event in watch_events
        if event.get("event_type")
        in {
            "task_claimed",
            "task_started",
            "gate_passed",
            "gate_failed",
            "artifact_produced",
            "collaboration_packet_registered",
        }
    )
    action_last = _file_last_mtime_iso(inv.action_log)
    work_status = "ok" if action_count >= 3 else ("warn" if action_count >= 1 else "fail")
    d_work = _dim(
        min(1.0, (action_count + cwt_work_events) / 5),
        work_status,
        f"{action_count} action_log/task_log entries, {cwt_work_events} CWT work events",
        ([str(inv.action_log)] if action_count else [])
        + ([str(cwt_events_path)] if cwt_work_events else []),
        action_last,
    )

    # D4: comms_reliability — A2A card present
    a2a_present = inv.a2a_card.exists()
    d_comms = _dim(
        1.0 if a2a_present else 0.0,
        "ok" if a2a_present else "fail",
        "A2A card present (discoverable)" if a2a_present else "A2A card MISSING — not discoverable",
        [str(inv.a2a_card)] if a2a_present else [],
    )

    # D5: memory_evolution — self_model exists and is non-placeholder (>500 bytes)
    if inv.self_model.exists():
        size = inv.self_model.stat().st_size
        mem_ok = size > 500
        d_memory = _dim(
            1.0 if mem_ok else 0.3,
            "ok" if mem_ok else "warn",
            f"self_model size = {size} bytes ({'authored' if mem_ok else 'placeholder or stub'})",
            [str(inv.self_model)],
            _file_last_mtime_iso(inv.self_model),
        )
    else:
        d_memory = _dim(0.0, "fail", "self_model missing", [])

    # D6: operational_value — material work beyond registration. Heuristic: action_count > 2 means
    #     non-registration entries are present (registration alone is ~1, plus self-registration ~1)
    op_ratio = max(0.0, (action_count - 2) / 8) if action_count > 2 else 0.0
    op_status = "ok" if action_count > 5 else ("warn" if action_count > 2 else "unknown")
    d_op = _dim(
        min(1.0, op_ratio),
        op_status,
        f"{action_count} action entries (>2 implies work beyond registration)",
        [str(inv.action_log)] if action_count else [],
    )

    # D7: safety_discipline — live CWT incidents and AOTAMs
    mandatory_or_critical = [
        row
        for row in incidents
        if row.get("kind") == "mandatory" or row.get("severity") in {"high", "critical"}
    ]
    if mandatory_or_critical:
        d_safety = _dim(
            0.0,
            "fail",
            f"{len(incidents)} open incidents, {len(aotams)} active AOTAMs",
            [str(incidents_file)] + ([str(aotams_file)] if aotams else []),
        )
    elif incidents or aotams:
        d_safety = _dim(
            0.5,
            "warn",
            f"{len(incidents)} open incidents, {len(aotams)} active AOTAMs",
            ([str(incidents_file)] if incidents else []) + ([str(aotams_file)] if aotams else []),
        )
    else:
        d_safety = _dim(1.0, "ok", "no open CWT incidents or active AOTAMs", [])

    # D8: cost_discipline — KaizenOps event count proxy
    kz_count = _kaizen_event_count(state_root, inv.uid)
    cost_evidence = [str(state_root / "kaizen" / "ops.db")] if kz_count else []
    d_cost = _dim(
        0.5,
        "unknown",
        f"{kz_count} KaizenOps events (cost dimension deferred to v1)",
        cost_evidence,
    )

    # D9: collaboration — stigmergy mark presence
    stig_count = _stigmergy_marks_for(state_root, inv.uid)
    collaboration_events = sum(
        1 for event in watch_events if event.get("event_type") == "collaboration_packet_registered"
    )
    d_collab = _dim(
        1.0 if (stig_count or collaboration_events) else 0.0,
        "ok" if (stig_count or collaboration_events) else "warn",
        f"{stig_count} stigmergy marks and {collaboration_events} collaboration packet events reference this agent",
        ([str(state_root / "stigmergy" / "marks.jsonl")] if stig_count else [])
        + ([str(cwt_events_path)] if collaboration_events else []),
    )

    # D10: promotion_readiness — passport + watch_contract presence
    has_passport = inv.authority_passport.exists()
    has_watch = inv.watch_contract.exists()
    promo_evidence = []
    if has_passport:
        promo_evidence.append(str(inv.authority_passport))
    if has_watch:
        promo_evidence.append(str(inv.watch_contract))
    has_reputation = reputation is not None
    promo_score = (int(has_passport) + int(has_watch) + int(has_reputation)) / 3
    promo_status = "ok" if promo_score >= 0.8 else ("warn" if promo_score >= 0.4 else "fail")
    d_promo = _dim(
        promo_score,
        promo_status,
        (
            f"passport={'yes' if has_passport else 'no'}, "
            f"watch_contract={'yes' if has_watch else 'no'}, "
            f"reputation={'yes' if has_reputation else 'no'}"
        ),
        promo_evidence + ([str(reputation_db)] if has_reputation else []),
    )

    dims = {
        "identity_continuity": d_identity,
        "wake_persistence": d_wake,
        "work_capacity": d_work,
        "comms_reliability": d_comms,
        "memory_evolution": d_memory,
        "operational_value": d_op,
        "safety_discipline": d_safety,
        "cost_discipline": d_cost,
        "collaboration": d_collab,
        "promotion_readiness": d_promo,
    }

    overall = sum(d["score"] for d in dims.values()) / len(dims)

    # Determine status (matches scorecard.v0 enum)
    if _latest_event_type(watch_events) == "lost_comms":
        agent_status = "lost_comms"
    elif mandatory_or_critical:
        agent_status = "incident"
    elif action_count >= 3 and id_present >= 4:
        agent_status = "active"
    elif id_present >= 2:
        agent_status = "registered"
    else:
        agent_status = "unknown"

    # Blockers
    blockers: list[str] = []
    if not inv.registration.exists():
        blockers.append("registration.json missing")
    if not inv.living_agent.exists():
        blockers.append("living_agent.json missing — not discoverable in canonical registry")
    if not inv.a2a_card.exists():
        blockers.append("a2a card missing — not discoverable via A2A")
    if invariant["errors"]:
        blockers.extend(f"identity invariant: {error}" for error in invariant["errors"])
    elif not invariant["valid"]:
        blockers.append("identity invariant missing across registration/living_agent/A2A surfaces")
    if action_count == 0:
        blockers.append("no action_log entries — agent has not logged any material actions")
    if not _telemetry_present(state_root, inv.uid):
        blockers.append("runtime.db agent_identity row missing — telemetry identity not present")
    if _latest_event_type(watch_events) == "lost_comms":
        blockers.append("CWT lost_comms is latest watch event")
    for incident in mandatory_or_critical:
        blockers.append(
            f"CWT incident {incident.get('incident_id', 'unknown')}: {incident.get('summary', '')}"
        )

    # Promotion recommendation — v0 always 'hold' per operator directive
    recommendation = {
        "recommendation": "hold",
        "reason": (
            "v0 collector — structural-evidence scorecard only; human review and "
            "live-collector consumption are required before any promotion."
        ),
        "required_human_decision": True,
        "required_next_evidence": [
            "human review of scorecard",
            "operator decision on authority rank",
            "live-collector incident/AOTAM data (v1)",
        ],
    }

    scorecard_id = hashlib.sha256(
        f"{inv.uid}:{_now()}:{SCORECARD_SCHEMA_VERSION}".encode()
    ).hexdigest()[:24]

    return {
        "schema_version": SCORECARD_SCHEMA_VERSION,
        "scorecard_id": scorecard_id,
        "agent_uid": inv.uid,
        "callsign": inv.callsign,
        "evaluated_at": _now(),
        "authority": inv.raw_authority,
        "status": agent_status,
        "overall_score": round(overall, 4),
        "trust_band": str(reputation.get("trust_band") or "evidence_only")
        if reputation
        else "evidence_only",
        "dimensions": dims,
        "identity_invariant": invariant,
        "clearance_state": "none",
        "current_flight_plan": None,
        "evidence_refs": evidence_all,
        "blockers": blockers,
        "warnings": [],
        "incidents": incidents,
        "aotams": aotams,
        "promotion_recommendation": recommendation,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="CWT v0 read-only collector: registered agents -> scorecards"
    )
    parser.add_argument(
        "--state-root", type=Path, default=DEFAULT_STATE_ROOT,
        help="State root (default: ~/.dharma)",
    )
    parser.add_argument(
        "--out-dir", type=Path, default=None,
        help="Output directory; if omitted, prints index JSON to stdout",
    )
    args = parser.parse_args()

    inventories = discover_agents(args.state_root)
    scorecards = [build_scorecard(inv, args.state_root) for inv in inventories]

    index = {
        "schema_version": "cwt_collector_output.v0",
        "generated_at": _now(),
        "state_root": str(args.state_root),
        "scorecard_count": len(scorecards),
        "scorecards": [
            {
                "agent_uid": sc["agent_uid"],
                "callsign": sc["callsign"],
                "overall_score": sc["overall_score"],
                "status": sc["status"],
                "blocker_count": len(sc["blockers"]),
            }
            for sc in scorecards
        ],
    }

    if args.out_dir:
        args.out_dir.mkdir(parents=True, exist_ok=True)
        for sc in scorecards:
            (args.out_dir / f"scorecard_{sc['agent_uid']}.json").write_text(
                json.dumps(sc, indent=2, sort_keys=True) + "\n"
            )
        (args.out_dir / "scorecards_index.json").write_text(
            json.dumps(index, indent=2, sort_keys=True) + "\n"
        )
        print(f"Wrote {len(scorecards)} scorecards to {args.out_dir}")
        for sc in scorecards:
            print(
                f"  {sc['agent_uid']:<48} score={sc['overall_score']:.3f}  "
                f"status={sc['status']}  blockers={len(sc['blockers'])}"
            )
    else:
        print(json.dumps(index, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
