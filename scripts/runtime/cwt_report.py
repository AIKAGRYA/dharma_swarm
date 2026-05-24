#!/usr/bin/env python3
"""CONTROL_WATCH_TOWER v0 report renderer.

Builds a top-level report conforming to:
    schemas/control_watch_tower_report.v0.json

Pipeline:
    1. Run cwt_collect.py to generate scorecards under {out-dir}/
    2. Assemble report.json with common_operational_picture, source statuses,
       per-agent summaries (referencing scorecard files), blockers, warnings,
       next_operator_actions.
    3. Write to:
         reports/control_watch_tower/{timestamp}/report.json
         reports/control_watch_tower/{timestamp}/scorecards/scorecard_{uid}.json (via collector)
         reports/control_watch_tower/{timestamp}/scorecards/scorecards_index.json (via collector)
         reports/control_watch_tower/{timestamp}/REPORT.md (human-readable summary)

Read-only against live state. Only writes under the report directory.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

HOME = Path.home()
REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_STATE_ROOT = HOME / ".dharma"
DEFAULT_REPORTS_BASE = REPO_ROOT / "reports" / "control_watch_tower"
COLLECTOR_PATH = REPO_ROOT / "scripts" / "runtime" / "cwt_collect.py"

REPORT_SCHEMA_VERSION = "control_watch_tower_report.v0"
GENERATED_BY = "CONTROL_WATCH_TOWER cwt_report.v0"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _source_status(name: str, status: str, severity: str, summary: str, evidence_paths: list[str] | None = None, metrics: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "source": name,
        "status": status,
        "severity": severity,
        "summary": summary,
        "evidence_paths": evidence_paths or [],
        "metrics": metrics or {},
        "checked_at": _now(),
    }


def collect_source_statuses(state_root: Path) -> list[dict[str, Any]]:
    statuses: list[dict[str, Any]] = []

    # external_agents
    ext = state_root / "external_agents"
    if ext.exists():
        n = sum(1 for p in ext.iterdir() if p.is_dir())
        statuses.append(_source_status(
            "external_agents_dir", "ok", "INFO",
            f"{n} external agent sandboxes present",
            [str(ext)], {"agent_dir_count": n},
        ))
    else:
        statuses.append(_source_status(
            "external_agents_dir", "missing", "WARNING",
            "external agent root does not exist", [str(ext)],
        ))

    # canonical agents
    ag = state_root / "agents"
    if ag.exists():
        n = sum(1 for p in ag.iterdir() if p.is_dir())
        statuses.append(_source_status(
            "agents_dir", "ok", "INFO",
            f"{n} canonical agent dirs present",
            [str(ag)], {"agent_dir_count": n},
        ))
    else:
        statuses.append(_source_status(
            "agents_dir", "missing", "WARNING",
            "canonical agents root does not exist", [str(ag)],
        ))

    # a2a cards
    a2a = state_root / "a2a" / "cards"
    if a2a.exists():
        n = sum(1 for p in a2a.iterdir() if p.suffix == ".json")
        statuses.append(_source_status(
            "a2a_cards_dir", "ok", "INFO",
            f"{n} A2A discovery cards present",
            [str(a2a)], {"card_count": n},
        ))
    else:
        statuses.append(_source_status(
            "a2a_cards_dir", "missing", "WARNING",
            "A2A cards root does not exist", [str(a2a)],
        ))

    # runtime.db (telemetry identity)
    rt = state_root / "state" / "runtime.db"
    if rt.exists():
        try:
            con = sqlite3.connect(rt)
            cur = con.cursor()
            cur.execute("SELECT COUNT(*) FROM agent_identity")
            n_id = cur.fetchone()[0]
            con.close()
            statuses.append(_source_status(
                "runtime_db_agent_identity", "ok", "INFO",
                f"{n_id} telemetry identity rows present",
                [str(rt)], {"agent_identity_rows": n_id},
            ))
        except Exception as e:
            statuses.append(_source_status(
                "runtime_db_agent_identity", "fail", "BLOCKER",
                f"runtime.db query error: {type(e).__name__}",
                [str(rt)],
            ))
    else:
        statuses.append(_source_status(
            "runtime_db_agent_identity", "missing", "WARNING",
            "runtime.db does not exist", [str(rt)],
        ))

    # kaizen ops.db
    kz = state_root / "kaizen" / "ops.db"
    if kz.exists():
        try:
            con = sqlite3.connect(kz)
            cur = con.cursor()
            cur.execute("SELECT COUNT(*) FROM events WHERE category = 'external_agent_registration'")
            n = cur.fetchone()[0]
            con.close()
            statuses.append(_source_status(
                "kaizen_ops_db_events", "ok", "INFO",
                f"{n} external_agent_registration events on file",
                [str(kz)], {"registration_event_count": n},
            ))
        except Exception as e:
            statuses.append(_source_status(
                "kaizen_ops_db_events", "fail", "WARNING",
                f"kaizen/ops.db query error: {type(e).__name__}",
                [str(kz)],
            ))
    else:
        statuses.append(_source_status(
            "kaizen_ops_db_events", "missing", "INFO",
            "kaizen/ops.db does not exist", [str(kz)],
        ))

    # stigmergy marks
    stig = state_root / "stigmergy" / "marks.jsonl"
    if stig.exists():
        try:
            with open(stig) as f:
                lines = sum(1 for _ in f)
            statuses.append(_source_status(
                "stigmergy_marks", "ok", "INFO",
                f"{lines} stigmergy marks recorded",
                [str(stig)], {"mark_line_count": lines},
            ))
        except Exception as e:
            statuses.append(_source_status(
                "stigmergy_marks", "fail", "WARNING",
                f"stigmergy read error: {type(e).__name__}",
                [str(stig)],
            ))
    else:
        statuses.append(_source_status(
            "stigmergy_marks", "missing", "INFO",
            "stigmergy/marks.jsonl does not exist", [str(stig)],
        ))

    # passports
    pp = state_root / "agent_passports"
    if pp.exists():
        n = sum(1 for p in pp.iterdir() if p.suffix == ".json")
        statuses.append(_source_status(
            "agent_passports_dir", "ok", "INFO",
            f"{n} agent passports present",
            [str(pp)], {"passport_count": n},
        ))
    else:
        statuses.append(_source_status(
            "agent_passports_dir", "missing", "INFO",
            "agent_passports root does not exist", [str(pp)],
        ))

    return statuses


def aggregate_agent_summaries(scorecards_dir: Path) -> tuple[list[dict[str, Any]], dict[str, int]]:
    summaries: list[dict[str, Any]] = []
    counts = {"registered": 0, "active": 0, "blocked": 0, "lost_comms": 0, "quarantined": 0, "retired": 0, "unknown": 0, "incident": 0, "promotion_candidate": 0}
    for sc_path in sorted(scorecards_dir.glob("scorecard_*.json")):
        try:
            sc = json.loads(sc_path.read_text())
        except Exception:
            continue
        status = sc.get("status", "unknown")
        if status in counts:
            counts[status] += 1
        else:
            counts["unknown"] += 1
        summaries.append({
            "agent_uid": sc["agent_uid"],
            "callsign": sc["callsign"],
            "authority": sc.get("authority", "unknown"),
            "status": status,
            "scorecard_ref": str(sc_path.relative_to(scorecards_dir.parent.parent)),
            "blockers": sc.get("blockers", []),
        })
        rec = sc.get("promotion_recommendation", {}).get("recommendation", "hold")
        if rec in ("promote_candidate", "promote_scoped"):
            counts["promotion_candidate"] += 1
    return summaries, counts


def build_report(state_root: Path, report_dir: Path) -> dict[str, Any]:
    scorecards_dir = report_dir / "scorecards"
    scorecards_dir.mkdir(parents=True, exist_ok=True)

    # 1. Run collector with output directory
    collector_cmd = [
        sys.executable, str(COLLECTOR_PATH),
        "--state-root", str(state_root),
        "--out-dir", str(scorecards_dir),
    ]
    collector_result = subprocess.run(collector_cmd, capture_output=True, text=True)
    if collector_result.returncode != 0:
        raise RuntimeError(f"cwt_collect.py failed (exit {collector_result.returncode}): {collector_result.stderr[:500]}")

    # 2. Source statuses
    sources = collect_source_statuses(state_root)

    # 3. Agent summaries
    summaries, counts = aggregate_agent_summaries(scorecards_dir)

    # 4. Common operational picture
    cop = {
        "summary": (
            f"v0 read-only collector pass. {counts['active']} active, "
            f"{counts['registered']} registered, {counts['unknown']} unknown. "
            f"{counts['promotion_candidate']} promotion candidates."
        ),
        "registered_agents": sum([counts["registered"], counts["active"], counts["blocked"]]),
        "active_agents": counts["active"],
        "lost_comms_agents": counts["lost_comms"],
        "blocked_agents": counts["blocked"],
        "incident_count": counts["incident"],
        "promotion_candidates": counts["promotion_candidate"],
    }

    # 5. Overall status from source severities
    overall = "ok"
    if any(s["severity"] == "BLOCKER" for s in sources):
        overall = "fail"
    elif any(s["severity"] == "WARNING" for s in sources):
        overall = "warn"

    # 6. Blockers + warnings (collected from sources + scorecards)
    blockers_list: list[str] = []
    warnings_list: list[str] = []
    for s in sources:
        if s["severity"] == "BLOCKER":
            blockers_list.append(f"{s['source']}: {s['summary']}")
        elif s["severity"] == "WARNING":
            warnings_list.append(f"{s['source']}: {s['summary']}")
    for summ in summaries:
        for b in summ.get("blockers", []):
            blockers_list.append(f"{summ['agent_uid']}: {b}")

    next_actions = [
        "Review per-agent scorecards under reports/control_watch_tower/<ts>/scorecards/",
        "For agents with 'no action_log entries' blocker — verify they have a real wake/work loop or accept registered-only status.",
        "For agents missing a2a card or telemetry identity — re-register via scripts/register_external_agent.py.",
        "v1 collector should add: incident tracking, AOTAM ingestion, cost-discipline real metrics, true comms_reliability via heartbeat checks.",
    ]

    report_id = hashlib.sha256(f"cwt_report:{_now()}".encode()).hexdigest()[:20]

    report = {
        "schema_version": REPORT_SCHEMA_VERSION,
        "report_id": report_id,
        "generated_at": _now(),
        "repo_root": str(REPO_ROOT),
        "state_dir": str(state_root),
        "generated_by": GENERATED_BY,
        "battle_rhythm_window": {
            "from": _now(),
            "to": _now(),
            "cadence": "on_demand_v0",
        },
        "overall_status": overall,
        "common_operational_picture": cop,
        "sources": sources,
        "agents": summaries,
        "aotams": [],
        "incidents": [],
        "blockers": blockers_list,
        "warnings": warnings_list,
        "next_operator_actions": next_actions,
        "evidence_paths": [
            str(state_root / "external_agents"),
            str(state_root / "agents"),
            str(state_root / "a2a" / "cards"),
            str(state_root / "state" / "runtime.db"),
            str(state_root / "kaizen" / "ops.db"),
            str(state_root / "stigmergy" / "marks.jsonl"),
            str(state_root / "agent_passports"),
        ],
    }
    return report


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        f"# CONTROL_WATCH_TOWER Report — {report['generated_at']}",
        "",
        f"- **report_id:** `{report['report_id']}`",
        f"- **overall_status:** `{report['overall_status']}`",
        f"- **schema_version:** `{report['schema_version']}`",
        "",
        "## Common Operational Picture",
        "",
        f"> {report['common_operational_picture']['summary']}",
        "",
        f"- registered_agents: **{report['common_operational_picture']['registered_agents']}**",
        f"- active_agents: **{report['common_operational_picture']['active_agents']}**",
        f"- blocked_agents: **{report['common_operational_picture']['blocked_agents']}**",
        f"- lost_comms_agents: **{report['common_operational_picture']['lost_comms_agents']}**",
        f"- promotion_candidates: **{report['common_operational_picture']['promotion_candidates']}**",
        f"- incident_count: **{report['common_operational_picture']['incident_count']}**",
        "",
        "## Sources",
        "",
        "| Source | Status | Severity | Summary |",
        "|---|---|---|---|",
    ]
    for s in report["sources"]:
        lines.append(f"| `{s['source']}` | {s['status']} | {s['severity']} | {s['summary']} |")
    lines.extend([
        "",
        "## Agents",
        "",
        "| agent_uid | callsign | authority | status | blockers |",
        "|---|---|---|---|---|",
    ])
    for a in report["agents"]:
        lines.append(
            f"| `{a['agent_uid']}` | `{a['callsign']}` | {a['authority']} | {a['status']} | {len(a['blockers'])} |"
        )
    if report["blockers"]:
        lines.extend(["", "## Blockers", ""])
        for b in report["blockers"]:
            lines.append(f"- {b}")
    if report["warnings"]:
        lines.extend(["", "## Warnings", ""])
        for w in report["warnings"]:
            lines.append(f"- {w}")
    if report["next_operator_actions"]:
        lines.extend(["", "## Next Operator Actions", ""])
        for a in report["next_operator_actions"]:
            lines.append(f"- {a}")
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="CWT v0 report renderer")
    parser.add_argument(
        "--state-root", type=Path, default=DEFAULT_STATE_ROOT,
        help="State root (default: ~/.dharma)",
    )
    parser.add_argument(
        "--reports-base", type=Path, default=DEFAULT_REPORTS_BASE,
        help="Reports base dir (default: reports/control_watch_tower under repo root)",
    )
    parser.add_argument(
        "--timestamp", type=str, default=None,
        help="Override timestamp dir (default: current UTC stamp)",
    )
    args = parser.parse_args()

    stamp = args.timestamp or _stamp()
    report_dir = args.reports_base / stamp
    report_dir.mkdir(parents=True, exist_ok=True)

    report = build_report(args.state_root, report_dir)

    (report_dir / "report.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n"
    )
    (report_dir / "REPORT.md").write_text(render_markdown(report))

    print(f"CWT v0 report written:")
    print(f"  {report_dir / 'report.json'}")
    print(f"  {report_dir / 'REPORT.md'}")
    print(f"  {report_dir / 'scorecards'}/  ({len(report['agents'])} scorecards)")
    print(f"")
    print(f"overall_status: {report['overall_status']}")
    print(f"agents: {len(report['agents'])}  blockers: {len(report['blockers'])}  warnings: {len(report['warnings'])}")


if __name__ == "__main__":
    main()
