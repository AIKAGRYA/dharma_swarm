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
sys.path.insert(0, str(REPO_ROOT))

from dharma_swarm.operator_core.a2a_task_lifecycle import task_lifecycle_state  # noqa: E402

REPORT_SCHEMA_VERSION = "control_watch_tower_report.v0"
GENERATED_BY = "CONTROL_WATCH_TOWER cwt_report.v0"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _source_status(
    name: str,
    status: str,
    severity: str,
    summary: str,
    evidence_paths: list[str] | None = None,
    metrics: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "source": name,
        "status": status,
        "severity": severity,
        "summary": summary,
        "evidence_paths": evidence_paths or [],
        "metrics": metrics or {},
        "checked_at": _now(),
    }


def read_jsonl_safe(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    try:
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
    except Exception:
        return []
    return rows


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

    # CWT v1 watch events
    cwt = state_root / "control_watch_tower"
    watch_events = cwt / "watch_events.jsonl"
    incidents = cwt / "incidents.jsonl"
    aotams = cwt / "aotams.jsonl"
    for name, path in (
        ("cwt_watch_events", watch_events),
        ("cwt_incidents", incidents),
        ("cwt_aotams", aotams),
    ):
        if path.exists():
            try:
                with path.open(encoding="utf-8") as handle:
                    lines = sum(1 for line in handle if line.strip())
                statuses.append(_source_status(
                    name, "ok", "INFO",
                    f"{lines} records present",
                    [str(path)], {"record_count": lines},
                ))
            except Exception as e:
                statuses.append(_source_status(
                    name, "fail", "WARNING",
                    f"{name} read error: {type(e).__name__}",
                    [str(path)],
                ))
        else:
            statuses.append(_source_status(
                name, "missing", "INFO",
                f"{path.name} does not exist yet",
                [str(path)],
            ))

    return statuses


def aggregate_agent_summaries(scorecards_dir: Path) -> tuple[list[dict[str, Any]], dict[str, int]]:
    summaries: list[dict[str, Any]] = []
    counts = {
        "registered": 0,
        "active": 0,
        "blocked": 0,
        "lost_comms": 0,
        "quarantined": 0,
        "retired": 0,
        "unknown": 0,
        "incident": 0,
        "promotion_candidate": 0,
    }
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
            "incident_count": len(sc.get("incidents", [])),
            "aotam_count": len(sc.get("aotams", [])),
        })
        counts["incident"] += len(sc.get("incidents", []))
        rec = sc.get("promotion_recommendation", {}).get("recommendation", "hold")
        if rec in ("promote_candidate", "promote_scoped"):
            counts["promotion_candidate"] += 1
    return summaries, counts


def collect_identity_invariant_mismatches(scorecards_dir: Path) -> list[dict[str, Any]]:
    mismatches: list[dict[str, Any]] = []
    for sc_path in sorted(scorecards_dir.glob("scorecard_*.json")):
        try:
            sc = json.loads(sc_path.read_text())
        except Exception:
            continue
        invariant = sc.get("identity_invariant") or {}
        if invariant.get("valid") is True:
            continue
        errors = invariant.get("errors") or []
        mismatches.append(
            {
                "agent_uid": sc.get("agent_uid"),
                "callsign": sc.get("callsign"),
                "errors": errors or ["identity invariant missing or invalid"],
                "scorecard_ref": str(sc_path),
            }
        )
    return mismatches


def collect_recursive_control_projection(state_root: Path, scorecards_dir: Path) -> dict[str, Any]:
    queue_path = state_root / "a2a_bus" / "tasks" / "queue.jsonl"
    queue_rows = read_jsonl_safe(queue_path)
    open_frames: list[dict[str, Any]] = []
    claimed_without_receipt: list[dict[str, Any]] = []
    completed_unverified: list[dict[str, Any]] = []
    missing_return_address: list[dict[str, Any]] = []
    for row in queue_rows:
        lifecycle = task_lifecycle_state(row)
        item = {
            "task_id": row.get("id"),
            "from": row.get("from"),
            "to": row.get("to"),
            "status": row.get("status") or "pending",
            "lifecycle_state": lifecycle["state"],
            "claimed_by": row.get("claimed_by"),
        }
        if not lifecycle["closed"]:
            open_frames.append(item)
        if lifecycle["state"] == "claimed_open":
            claimed_without_receipt.append(item)
        if lifecycle["state"] == "completed_unverified":
            validation = lifecycle.get("validation") or {}
            completed_unverified.append(item | {"errors": validation.get("errors", [])})
        receipt = row.get("receipt") if isinstance(row.get("receipt"), dict) else {}
        if not row.get("return_address") and not receipt.get("return_address"):
            missing_return_address.append(item)

    self_evolution_candidates: list[dict[str, Any]] = []
    for review_path in sorted((state_root / "gepa_lite").glob("*/promotion_reviews/*.json")):
        try:
            review = json.loads(review_path.read_text())
        except Exception:
            continue
        self_evolution_candidates.append(
            {
                "experiment_id": review.get("experiment_id"),
                "candidate_id": review.get("candidate_id"),
                "status": review.get("status"),
                "path": str(review_path),
            }
        )

    benchmark_runs = [
        str(path)
        for root in (state_root / "benchmarks", REPO_ROOT / "reports" / "benchmarks")
        if root.exists()
        for path in sorted(root.rglob("*.json"))
    ][:50]
    revenue_trials = [
        str(path)
        for root in (state_root / "revenue_packets", state_root / "economics")
        if root.exists()
        for path in sorted(root.rglob("*.json"))
    ][:50]

    return {
        "open_recursive_frames": open_frames,
        "claimed_without_receipt": claimed_without_receipt,
        "completed_unverified": completed_unverified,
        "missing_return_address": missing_return_address,
        "identity_invariant_mismatches": collect_identity_invariant_mismatches(scorecards_dir),
        "self_evolution_candidates": self_evolution_candidates,
        "benchmark_runs": benchmark_runs,
        "revenue_autonomy_trials": revenue_trials,
    }


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
        raise RuntimeError(
            f"cwt_collect.py failed (exit {collector_result.returncode}): "
            f"{collector_result.stderr[:500]}"
        )

    # 2. Source statuses
    sources = collect_source_statuses(state_root)

    # 3. Agent summaries
    summaries, counts = aggregate_agent_summaries(scorecards_dir)
    recursive_control = collect_recursive_control_projection(state_root, scorecards_dir)
    cwt_root = state_root / "control_watch_tower"
    incidents = [
        row
        for row in read_jsonl_safe(cwt_root / "incidents.jsonl")
        if row.get("status", "open") != "closed"
    ]
    aotams = [
        row
        for row in read_jsonl_safe(cwt_root / "aotams.jsonl")
        if row.get("status", "active") == "active"
    ]

    # 4. Common operational picture
    cop = {
        "summary": (
            f"v0 read-only collector pass. {counts['active']} active, "
            f"{counts['registered']} registered, {counts['unknown']} unknown. "
            f"{counts['promotion_candidate']} promotion candidates."
        ),
        "registered_agents": sum(
            [counts["registered"], counts["active"], counts["blocked"]]
        ),
        "active_agents": counts["active"],
        "lost_comms_agents": counts["lost_comms"],
        "blocked_agents": counts["blocked"],
        "incident_count": counts["incident"],
        "promotion_candidates": counts["promotion_candidate"],
    }

    # 5. Blockers + warnings (collected from sources, scorecards, recursive control)
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
    for frame in recursive_control["claimed_without_receipt"]:
        blockers_list.append(f"A2A claimed without receipt: {frame['task_id']} -> {frame['to']}")
    for frame in recursive_control["completed_unverified"]:
        errors = "; ".join(frame.get("errors") or [])
        detail = f" ({errors})" if errors else ""
        blockers_list.append(
            f"A2A completed unverified: {frame['task_id']} -> {frame['to']}{detail}"
        )
    for frame in recursive_control["missing_return_address"]:
        blockers_list.append(f"A2A missing return address: {frame['task_id']} -> {frame['to']}")
    for mismatch in recursive_control["identity_invariant_mismatches"]:
        blockers_list.append(
            f"{mismatch['agent_uid']}: identity invariant invalid/missing"
        )

    # 6. Overall status must reflect every blocker surface, not only source health.
    if blockers_list:
        overall = "fail"
    elif warnings_list:
        overall = "warn"
    else:
        overall = "ok"

    next_actions = [
        "Review per-agent scorecards under reports/control_watch_tower/<ts>/scorecards/",
        (
            "For agents with 'no action_log entries' blocker — verify they have "
            "a real wake/work loop or accept registered-only status."
        ),
        (
            "For agents missing a2a card or telemetry identity — re-register via "
            "scripts/register_external_agent.py."
        ),
        (
            "CWT v1 now ingests watch events, incidents, AOTAMs, lost-comms scans, "
            "and reputation upserts; remaining v1 work is true cost and heartbeat metrics."
        ),
        (
            "Use scripts/runtime/cwt_watch.py for append-only watch events, incidents, "
            "AOTAMs, lost-comms scans, and reputation upserts."
        ),
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
        "aotams": aotams,
        "incidents": incidents,
        "recursive_control": recursive_control,
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
        f"- open_recursive_frames: **{len(report['recursive_control']['open_recursive_frames'])}**",
        f"- claimed_without_receipt: **{len(report['recursive_control']['claimed_without_receipt'])}**",
        f"- self_evolution_candidates: **{len(report['recursive_control']['self_evolution_candidates'])}**",
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
        "| agent_uid | callsign | authority | status | blockers | incidents | AOTAMs |",
        "|---|---|---|---|---|---|---|",
    ])
    for a in report["agents"]:
        lines.append(
            f"| `{a['agent_uid']}` | `{a['callsign']}` | {a['authority']} | "
            f"{a['status']} | {len(a['blockers'])} | {a.get('incident_count', 0)} | "
            f"{a.get('aotam_count', 0)} |"
        )
    recursive = report["recursive_control"]
    lines.extend(
        [
            "",
            "## Recursive Control",
            "",
            f"- open_recursive_frames: `{len(recursive['open_recursive_frames'])}`",
            f"- claimed_without_receipt: `{len(recursive['claimed_without_receipt'])}`",
            f"- completed_unverified: `{len(recursive['completed_unverified'])}`",
            f"- missing_return_address: `{len(recursive['missing_return_address'])}`",
            f"- identity_invariant_mismatches: `{len(recursive['identity_invariant_mismatches'])}`",
            f"- self_evolution_candidates: `{len(recursive['self_evolution_candidates'])}`",
            f"- benchmark_runs: `{len(recursive['benchmark_runs'])}`",
            f"- revenue_autonomy_trials: `{len(recursive['revenue_autonomy_trials'])}`",
        ]
    )
    if recursive["claimed_without_receipt"]:
        lines.extend(["", "### Claimed Without Receipt", ""])
        for frame in recursive["claimed_without_receipt"][:20]:
            lines.append(
                f"- `{frame['task_id']}` from `{frame['from']}` to `{frame['to']}` "
                f"claimed_by `{frame.get('claimed_by') or ''}`"
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
