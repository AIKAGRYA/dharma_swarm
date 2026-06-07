#!/usr/bin/env python3
"""Watch a CashClaw Revenue Hydra run without taking external actions."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-root", required=True)
    parser.add_argument("--process-substring", default="cashclaw_revenue_hydra.py")
    parser.add_argument("--hours", type=float, default=10.0)
    parser.add_argument("--interval", type=int, default=300)
    parser.add_argument("--max-checks", type=int, default=0)
    args = parser.parse_args(argv)

    run_root = Path(args.run_root).expanduser().resolve()
    run_root.mkdir(parents=True, exist_ok=True)
    deadline = time.time() + max(0.0, args.hours) * 3600
    checks = 0
    while time.time() < deadline:
        checks += 1
        quality_refresh = refresh_quality_audit(run_root)
        status = build_watchdog_status(
            run_root=run_root,
            process_substring=args.process_substring,
            check_number=checks,
            quality_refresh=quality_refresh,
        )
        write_watchdog_status(run_root, status)
        if status["objective_complete"] or (args.max_checks and checks >= args.max_checks):
            break
        remaining = deadline - time.time()
        if remaining <= 0:
            break
        time.sleep(min(max(1, args.interval), max(1, int(remaining))))
    return 0


def build_watchdog_status(
    *,
    run_root: Path,
    process_substring: str,
    check_number: int,
    quality_refresh: dict[str, Any] | None = None,
) -> dict[str, Any]:
    audit = _read_json(run_root / "objective_audit.json")
    summaries = _read_json(run_root / "summaries.json")
    lease_requests = _read_json(run_root / "operator_revenue_lease_requests.json")
    quality_audit = _read_json(run_root / "lease_packet_quality_audit.json")
    processes = _matching_processes(process_substring)
    cycle_dirs = sorted(path.name for path in run_root.glob("cycle_*") if path.is_dir())
    source_signal_summary = _source_signal_summary(run_root, cycle_dirs)
    overnight_progress = _overnight_progress(summaries)
    latest_summary = summaries[-1] if isinstance(summaries, list) and summaries else {}
    objective_complete = bool(audit.get("complete") is True)
    side_effects = bool(lease_requests.get("external_side_effects_performed") is True)
    stale_minutes = _minutes_since_timestamp(str(latest_summary.get("timestamp") or ""))
    lease_request_count = len(lease_requests.get("requests", [])) if isinstance(lease_requests.get("requests"), list) else 0
    lease_packet_quality = _lease_packet_quality_status(
        quality_audit=quality_audit,
        latest_summary=latest_summary,
        lease_request_count=lease_request_count,
        quality_refresh=quality_refresh or {},
    )
    alerts: list[str] = []
    if not objective_complete and not processes:
        alerts.append("hydra_process_missing_before_objective_complete")
    if side_effects:
        alerts.append("external_side_effects_reported")
    if stale_minutes is not None and stale_minutes > 45 and not objective_complete:
        alerts.append("latest_cycle_stale_over_45m")
    if not audit:
        alerts.append("objective_audit_missing")
    if source_signal_summary["source_items"] == 0:
        alerts.append("no_live_source_items_seen")
    if source_signal_summary["source_type_count"] < 2 and source_signal_summary["source_items"] > 0:
        alerts.append("low_source_diversity")
    if lease_packet_quality.get("alert"):
        alerts.append(str(lease_packet_quality["alert"]))
    return {
        "generated_at": utc_now_iso(),
        "check_number": check_number,
        "run_root": str(run_root),
        "process_substring": process_substring,
        "matching_processes": processes,
        "hydra_process_running": bool(processes),
        "cycle_count": len(cycle_dirs),
        "cycle_dirs": cycle_dirs,
        "latest_cycle_timestamp": latest_summary.get("timestamp", ""),
        "latest_cycle_age_minutes": stale_minutes,
        "objective_status": audit.get("status", "missing"),
        "objective_complete": objective_complete,
        "objective_holds": [
            item.get("requirement")
            for item in audit.get("requirements", [])
            if isinstance(item, dict) and not item.get("passed")
        ],
        "lease_status": lease_requests.get("status", "missing"),
        "lease_request_count": lease_request_count,
        "lease_packet_quality": lease_packet_quality,
        "overnight_progress": overnight_progress,
        "source_signal_summary": source_signal_summary,
        "external_side_effects_performed": side_effects,
        "alerts": alerts,
        "no_external_side_effects": True,
    }


def write_watchdog_status(run_root: Path, status: dict[str, Any]) -> None:
    (run_root / "watchdog_status.json").write_text(json.dumps(status, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (run_root / "overnight_progress.json").write_text(
        json.dumps(status.get("overnight_progress", {}), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    history_path = run_root / "watchdog_history.jsonl"
    with history_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(status, sort_keys=True) + "\n")
    (run_root / "watchdog_status.md").write_text(watchdog_markdown(status), encoding="utf-8")
    (run_root / "overnight_progress.md").write_text(overnight_progress_markdown(status), encoding="utf-8")


def watchdog_markdown(status: dict[str, Any]) -> str:
    alerts = status.get("alerts") or []
    alert_lines = "\n".join(f"- {item}" for item in alerts) if alerts else "- none"
    processes = status.get("matching_processes") or []
    process_lines = "\n".join(f"- `{item}`" for item in processes) if processes else "- none"
    holds = status.get("objective_holds") or []
    hold_lines = "\n".join(f"- {item}" for item in holds) if holds else "- none"
    progress = status.get("overnight_progress") or {}
    source_summary = status.get("source_signal_summary") or {}
    quality = status.get("lease_packet_quality") or {}
    source_type_lines = _counter_lines(source_summary.get("source_types", {}))
    source_config_lines = _counter_lines(source_summary.get("top_source_configs", {}))
    build_lines = _counter_lines(source_summary.get("top_build_patterns", {}))
    risk_lines = _counter_lines(source_summary.get("risk_flags", {}))
    return (
        "# CashClaw Hydra Watchdog\n\n"
        f"- Generated: {status.get('generated_at', '')}\n"
        f"- Check: {status.get('check_number', 0)}\n"
        f"- Run root: `{status.get('run_root', '')}`\n"
        f"- Hydra process running: {status.get('hydra_process_running')}\n"
        f"- Cycle count: {status.get('cycle_count', 0)}\n"
        f"- Latest cycle timestamp: {status.get('latest_cycle_timestamp', '')}\n"
        f"- Latest cycle age minutes: {status.get('latest_cycle_age_minutes')}\n"
        f"- Objective status: `{status.get('objective_status', '')}`\n"
        f"- Objective complete: {status.get('objective_complete')}\n"
        f"- Wall-clock hours since first cycle: {progress.get('wallclock_since_first_cycle_hours')}\n"
        f"- Completed-cycle observed span hours: {progress.get('completed_cycle_span_hours')}\n"
        f"- Overnight target percent: {progress.get('target_percent')}\n"
        f"- Projected audit-ready at UTC: {progress.get('projected_audit_ready_at_utc', '')}\n"
        f"- Lease status: `{status.get('lease_status', '')}`\n"
        f"- Lease request count: {status.get('lease_request_count', 0)}\n"
        f"- Lease packet quality status: `{quality.get('status', 'missing')}`\n"
        f"- Lease packet quality passed: {quality.get('passed')}\n"
        f"- Lease packet quality latest cycle: {quality.get('latest_cycle')}\n"
        f"- Source items: {source_summary.get('source_items', 0)}\n"
        f"- Pattern cards: {source_summary.get('pattern_cards', 0)}\n"
        f"- Source type count: {source_summary.get('source_type_count', 0)}\n"
        f"- Agent-market signal count: {source_summary.get('agent_market_signal_count', 0)}\n"
        f"- AI-employee signal count: {source_summary.get('ai_employee_signal_count', 0)}\n"
        f"- External side effects performed: {status.get('external_side_effects_performed')}\n"
        f"- Watchdog side effects: local status files only\n\n"
        "## Objective Holds\n\n"
        f"{hold_lines}\n\n"
        "## Alerts\n\n"
        f"{alert_lines}\n\n"
        "## Source Signals\n\n"
        "### Source Types\n\n"
        f"{source_type_lines}\n\n"
        "### Source Configs\n\n"
        f"{source_config_lines}\n\n"
        "### Top Build Patterns\n\n"
        f"{build_lines}\n\n"
        "### Risk Flags\n\n"
        f"{risk_lines}\n\n"
        "## Matching Processes\n\n"
        f"{process_lines}\n"
    )


def overnight_progress_markdown(status: dict[str, Any]) -> str:
    progress = status.get("overnight_progress") or {}
    return (
        "# CashClaw Overnight Progress\n\n"
        f"- Generated: {status.get('generated_at', '')}\n"
        f"- Run root: `{status.get('run_root', '')}`\n"
        f"- Hydra process running: {status.get('hydra_process_running')}\n"
        f"- Objective status: `{status.get('objective_status', '')}`\n"
        f"- Objective complete: {status.get('objective_complete')}\n"
        f"- First cycle timestamp: {progress.get('first_cycle_timestamp', '')}\n"
        f"- Latest cycle timestamp: {progress.get('latest_cycle_timestamp', '')}\n"
        f"- Completed cycles: {progress.get('completed_cycles', 0)}\n"
        f"- Target hours: {progress.get('target_hours')}\n"
        f"- Wall-clock hours since first cycle: {progress.get('wallclock_since_first_cycle_hours')}\n"
        f"- Completed-cycle observed span hours: {progress.get('completed_cycle_span_hours')}\n"
        f"- Remaining wall-clock hours to target: {progress.get('remaining_wallclock_hours_to_target')}\n"
        f"- Target percent: {progress.get('target_percent')}\n"
        f"- Projected audit-ready at UTC: {progress.get('projected_audit_ready_at_utc', '')}\n"
        f"- Audit duration requirement passed: {progress.get('audit_duration_requirement_passed')}\n"
        f"- External side effects performed: {status.get('external_side_effects_performed')}\n"
        f"- Lease status: `{status.get('lease_status', '')}`\n"
        f"- Alerts: {', '.join(status.get('alerts') or []) or 'none'}\n"
    )


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {}


def refresh_quality_audit(run_root: Path) -> dict[str, Any]:
    script = Path(__file__).with_name("cashclaw_lease_packet_quality_audit.py")
    if not script.exists():
        return {
            "attempted": False,
            "ok": False,
            "returncode": None,
            "error": "quality_audit_script_missing",
        }
    try:
        proc = subprocess.run(
            [sys.executable, str(script), "--run-root", str(run_root)],
            check=False,
            text=True,
            capture_output=True,
        )
    except OSError as exc:
        return {
            "attempted": True,
            "ok": False,
            "returncode": None,
            "error": f"quality_audit_refresh_failed:{exc}",
        }
    return {
        "attempted": True,
        "ok": proc.returncode == 0,
        "returncode": proc.returncode,
        "stdout": proc.stdout.strip()[:500],
        "stderr": proc.stderr.strip()[:500],
    }


def _lease_packet_quality_status(
    *,
    quality_audit: Any,
    latest_summary: dict[str, Any],
    lease_request_count: int,
    quality_refresh: dict[str, Any],
) -> dict[str, Any]:
    if lease_request_count <= 0:
        return {
            "status": "not_required",
            "passed": True,
            "lease_request_count": lease_request_count,
            "latest_cycle": latest_summary.get("cycle"),
            "latest_cycle_timestamp": latest_summary.get("timestamp", ""),
            "audit_latest_cycle": None,
            "audit_latest_cycle_timestamp": "",
            "refresh": quality_refresh,
            "alert": "",
        }
    if not isinstance(quality_audit, dict) or not quality_audit:
        return {
            "status": "missing",
            "passed": False,
            "lease_request_count": lease_request_count,
            "latest_cycle": latest_summary.get("cycle"),
            "latest_cycle_timestamp": latest_summary.get("timestamp", ""),
            "audit_latest_cycle": None,
            "audit_latest_cycle_timestamp": "",
            "refresh": quality_refresh,
            "alert": "lease_packet_quality_audit_missing",
        }
    latest_cycle = latest_summary.get("cycle")
    latest_timestamp = str(latest_summary.get("timestamp") or "")
    audit_cycle = quality_audit.get("latest_cycle")
    audit_timestamp = str(quality_audit.get("latest_cycle_timestamp") or "")
    alert = ""
    if quality_audit.get("passed") is not True or quality_audit.get("status") != "pass":
        alert = "lease_packet_quality_audit_not_passed"
    elif latest_cycle is not None and audit_cycle != latest_cycle:
        alert = "lease_packet_quality_audit_stale_cycle"
    elif latest_timestamp and audit_timestamp != latest_timestamp:
        alert = "lease_packet_quality_audit_stale_timestamp"
    return {
        "status": quality_audit.get("status", "missing"),
        "passed": quality_audit.get("passed") is True,
        "lease_request_count": quality_audit.get("lease_request_count", lease_request_count),
        "latest_cycle": latest_cycle,
        "latest_cycle_timestamp": latest_timestamp,
        "audit_latest_cycle": audit_cycle,
        "audit_latest_cycle_timestamp": audit_timestamp,
        "packet_count": len(quality_audit.get("packet_results", []))
        if isinstance(quality_audit.get("packet_results"), list)
        else 0,
        "refresh": quality_refresh,
        "alert": alert,
    }


def _matching_processes(process_substring: str) -> list[str]:
    rows = _process_rows(["pgrep", "-fl", process_substring])
    if not rows:
        rows = [
            row
            for row in _process_rows(["ps", "-axo", "pid=,command="])
            if process_substring in row
        ]
    if not rows and process_substring == "cashclaw_revenue_hydra.py":
        for session_name in ("cashclaw-scrappy-v2-hydra", "cashclaw_revenue_hydra"):
            if _command_success(["tmux", "has-session", "-t", session_name]):
                rows = [f"tmux session {session_name} active; process table unavailable"]
                break
    return [row for row in rows if "cashclaw_hydra_watchdog.py" not in row]


def _process_rows(command: list[str]) -> list[str]:
    try:
        proc = subprocess.run(
            command,
            check=False,
            text=True,
            capture_output=True,
        )
    except OSError:
        return []
    rows = [line.strip() for line in proc.stdout.splitlines() if line.strip()]
    return rows


def _command_success(command: list[str]) -> bool:
    try:
        proc = subprocess.run(command, check=False, text=True, capture_output=True)
    except OSError:
        return False
    return proc.returncode == 0


def _overnight_progress(summaries: Any, *, target_hours: float = 8.0) -> dict[str, Any]:
    if not isinstance(summaries, list) or not summaries:
        return {
            "target_hours": target_hours,
            "completed_cycles": 0,
            "first_cycle_timestamp": "",
            "latest_cycle_timestamp": "",
            "wallclock_since_first_cycle_hours": 0.0,
            "completed_cycle_span_hours": 0.0,
            "remaining_wallclock_hours_to_target": target_hours,
            "target_percent": 0.0,
            "projected_audit_ready_at_utc": "",
            "audit_duration_requirement_passed": False,
        }
    stamps: list[datetime] = []
    for summary in summaries:
        if not isinstance(summary, dict):
            continue
        try:
            stamps.append(datetime.fromisoformat(str(summary.get("timestamp") or "")))
        except ValueError:
            continue
    if not stamps:
        return {
            "target_hours": target_hours,
            "completed_cycles": len(summaries),
            "first_cycle_timestamp": "",
            "latest_cycle_timestamp": "",
            "wallclock_since_first_cycle_hours": 0.0,
            "completed_cycle_span_hours": 0.0,
            "remaining_wallclock_hours_to_target": target_hours,
            "target_percent": 0.0,
            "projected_audit_ready_at_utc": "",
            "audit_duration_requirement_passed": False,
        }
    first = min(stamps)
    latest = max(stamps)
    now = datetime.now(timezone.utc)
    wallclock_hours = round(max(0.0, (now - first).total_seconds() / 3600), 3)
    span_hours = round(max(0.0, (latest - first).total_seconds() / 3600), 3) if len(stamps) >= 2 else 0.0
    remaining = round(max(0.0, target_hours - wallclock_hours), 3)
    target_percent = round(min(100.0, (wallclock_hours / target_hours) * 100), 2) if target_hours > 0 else 100.0
    projected = first.timestamp() + target_hours * 3600
    return {
        "target_hours": target_hours,
        "completed_cycles": len(summaries),
        "first_cycle_timestamp": first.isoformat(),
        "latest_cycle_timestamp": latest.isoformat(),
        "wallclock_since_first_cycle_hours": wallclock_hours,
        "completed_cycle_span_hours": span_hours,
        "remaining_wallclock_hours_to_target": remaining,
        "target_percent": target_percent,
        "projected_audit_ready_at_utc": datetime.fromtimestamp(projected, tz=timezone.utc).isoformat(),
        "audit_duration_requirement_passed": span_hours >= target_hours,
    }


def _source_signal_summary(run_root: Path, cycle_dirs: list[str]) -> dict[str, Any]:
    if not cycle_dirs:
        return _empty_source_signal_summary()
    latest_cycle = run_root / cycle_dirs[-1] / "live_intake"
    source_items = _read_json(latest_cycle / "source_items.json")
    pattern_cards = _read_json(latest_cycle / "pattern_cards.json")
    if not isinstance(source_items, list):
        source_items = []
    if not isinstance(pattern_cards, list):
        pattern_cards = []
    source_types = Counter(str(item.get("source_type") or "unknown") for item in source_items if isinstance(item, dict))
    source_configs = Counter(str(item.get("source_config_id") or "unknown") for item in source_items if isinstance(item, dict))
    build_patterns = Counter(str(card.get("what_is_being_built") or "unknown") for card in pattern_cards if isinstance(card, dict))
    risk_flags = Counter(
        str(flag)
        for card in pattern_cards
        if isinstance(card, dict)
        for flag in card.get("risks", [])
    )
    all_text = " ".join(
        " ".join(
            [
                str(card.get("what_is_being_built") or ""),
                str(card.get("buyer_pain") or ""),
                str(card.get("buyer_segment") or ""),
                " ".join(str(item) for item in card.get("tool_stack", [])),
            ]
        ).lower()
        for card in pattern_cards
        if isinstance(card, dict)
    )
    agent_market_signal_count = sum(
        1
        for card in pattern_cards
        if isinstance(card, dict)
        and _contains_any(
            " ".join(
                [
                    str(card.get("what_is_being_built") or ""),
                    str(card.get("buyer_pain") or ""),
                    " ".join(str(item) for item in card.get("tool_stack", [])),
                ]
            ).lower(),
            ("agent", "automation", "workflow", "claude", "openclaw", "mcp", "marketplace"),
        )
    )
    ai_employee_signal_count = sum(
        1
        for needle in ("ai employee", "openclaw", "hermes", "agent install", "cron agent", "daily briefing")
        if needle in all_text
    )
    return {
        "source_items": len(source_items),
        "pattern_cards": len(pattern_cards),
        "source_type_count": len(source_types),
        "source_types": dict(source_types.most_common()),
        "top_source_configs": dict(source_configs.most_common(10)),
        "top_build_patterns": dict(build_patterns.most_common(10)),
        "risk_flags": dict(risk_flags.most_common()),
        "agent_market_signal_count": agent_market_signal_count,
        "ai_employee_signal_count": ai_employee_signal_count,
    }


def _empty_source_signal_summary() -> dict[str, Any]:
    return {
        "source_items": 0,
        "pattern_cards": 0,
        "source_type_count": 0,
        "source_types": {},
        "top_source_configs": {},
        "top_build_patterns": {},
        "risk_flags": {},
        "agent_market_signal_count": 0,
        "ai_employee_signal_count": 0,
    }


def _contains_any(text: str, needles: tuple[str, ...]) -> bool:
    return any(needle in text for needle in needles)


def _counter_lines(counter: Any) -> str:
    if not isinstance(counter, dict) or not counter:
        return "- none"
    return "\n".join(f"- {key}: {value}" for key, value in counter.items())


def _minutes_since_timestamp(timestamp: str) -> float | None:
    if not timestamp:
        return None
    try:
        then = datetime.fromisoformat(timestamp)
    except ValueError:
        return None
    return round(max(0.0, (datetime.now(timezone.utc) - then).total_seconds() / 60), 2)


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


if __name__ == "__main__":
    raise SystemExit(main())
