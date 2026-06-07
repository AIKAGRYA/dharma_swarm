#!/usr/bin/env python3
"""Audit CashClaw lease-ready packets for source-backed specificity."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


GENERIC_TITLES = {"fetched text source", "fetched json source", "local markdown source"}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-root", required=True)
    args = parser.parse_args(argv)

    run_root = Path(args.run_root).expanduser().resolve()
    audit = build_quality_audit(run_root)
    write_quality_audit(run_root, audit)
    return 0 if audit.get("passed") else 1


def build_quality_audit(run_root: Path) -> dict[str, Any]:
    lease_requests = _read_json(run_root / "operator_revenue_lease_requests.json")
    summaries = _read_json(run_root / "summaries.json")
    requests = lease_requests.get("requests") if isinstance(lease_requests, dict) else []
    if not isinstance(requests, list):
        requests = []
    packet_results = [_audit_request(request) for request in requests if isinstance(request, dict)]
    reasons: list[str] = []
    if not requests:
        reasons.append("no_lease_ready_requests")
    if lease_requests.get("status") != "draft_only_not_granted":
        reasons.append("lease_status_not_draft_only")
    if lease_requests.get("external_side_effects_performed") is not False:
        reasons.append("external_side_effects_not_false")
    failed_packets = [packet for packet in packet_results if not packet.get("passed")]
    if failed_packets:
        reasons.append("one_or_more_packets_failed_quality_audit")
    latest_summary = summaries[-1] if isinstance(summaries, list) and summaries else {}
    return {
        "generated_at": utc_now_iso(),
        "run_root": str(run_root),
        "passed": not reasons,
        "status": "pass" if not reasons else "hold",
        "reasons": reasons,
        "lease_status": lease_requests.get("status", "missing") if isinstance(lease_requests, dict) else "missing",
        "external_side_effects_performed": lease_requests.get("external_side_effects_performed")
        if isinstance(lease_requests, dict)
        else None,
        "lease_request_count": len(requests),
        "latest_cycle": latest_summary.get("cycle"),
        "latest_cycle_timestamp": latest_summary.get("timestamp", ""),
        "packet_results": packet_results,
        "no_external_side_effects": True,
    }


def write_quality_audit(run_root: Path, audit: dict[str, Any]) -> None:
    (run_root / "lease_packet_quality_audit.json").write_text(
        json.dumps(audit, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (run_root / "lease_packet_quality_audit.md").write_text(quality_audit_markdown(audit), encoding="utf-8")


def quality_audit_markdown(audit: dict[str, Any]) -> str:
    reasons = audit.get("reasons") or []
    reason_lines = "\n".join(f"- {reason}" for reason in reasons) if reasons else "- none"
    rows = [
        "| Packet | Status | Price | Source State | Acceptance Clues | Reasons |",
        "|---|---|---:|---|---:|---|",
    ]
    for packet in audit.get("packet_results", []):
        rows.append(
            "| "
            f"{_md(packet.get('title', ''))} | "
            f"{'PASS' if packet.get('passed') else 'HOLD'} | "
            f"${float(packet.get('price_usd') or 0):,.0f} | "
            f"{_md(packet.get('source_state', 'unknown'))} | "
            f"{int(packet.get('acceptance_clues_count') or 0)} | "
            f"{_md(', '.join(packet.get('reasons') or []) or 'none')} |"
        )
    return (
        "# CashClaw Lease Packet Quality Audit\n\n"
        f"- Generated: {audit.get('generated_at', '')}\n"
        f"- Run root: `{audit.get('run_root', '')}`\n"
        f"- Status: `{audit.get('status', '')}`\n"
        f"- Passed: {audit.get('passed')}\n"
        f"- Lease status: `{audit.get('lease_status', '')}`\n"
        f"- Lease request count: {audit.get('lease_request_count', 0)}\n"
        f"- External side effects performed: {audit.get('external_side_effects_performed')}\n"
        f"- Latest cycle: {audit.get('latest_cycle')}\n"
        f"- Latest cycle timestamp: {audit.get('latest_cycle_timestamp', '')}\n\n"
        "## Reasons\n\n"
        f"{reason_lines}\n\n"
        "## Packet Audit\n\n"
        + "\n".join(rows)
        + "\n\n"
        "## Boundary\n\n"
        "This quality audit is local-only. It does not claim, comment, bid, submit, request payment, use credentials, or mutate external systems.\n"
    )


def _audit_request(request: dict[str, Any]) -> dict[str, Any]:
    reasons: list[str] = []
    title = str(request.get("title") or "")
    source_url = str(request.get("source_url") or "")
    delivery_plan = Path(str(request.get("delivery_plan") or ""))
    preflight_path = Path(str(request.get("lease_preflight") or ""))
    snapshot_md_path = Path(str(request.get("source_scope_snapshot") or ""))
    snapshot_json_path = snapshot_md_path.with_suffix(".json")
    preflight = _read_json(preflight_path)
    snapshot = _read_json(snapshot_json_path)
    preflight_checks = preflight.get("checks") if isinstance(preflight, dict) else {}
    if not delivery_plan.exists():
        reasons.append("delivery_plan_missing")
    if not snapshot_md_path.exists():
        reasons.append("source_scope_snapshot_missing")
    if not snapshot_json_path.exists():
        reasons.append("source_scope_snapshot_json_missing")
    if preflight.get("lease_preflight_passed") is not True:
        reasons.append("lease_preflight_not_passed")
    if preflight.get("no_external_side_effects") is not True:
        reasons.append("preflight_side_effect_invariant_missing")
    if preflight.get("reasons"):
        reasons.append("preflight_has_reasons")
    if request.get("risk_flags"):
        reasons.append("request_has_risk_flags")
    if preflight_checks.get("source_hard_risk_flags"):
        reasons.append("source_has_hard_risk_flags")
    price_usd = _request_price_usd(request)
    if price_usd <= 0:
        reasons.append("missing_positive_cash_price")
    if not source_url.startswith("https://"):
        reasons.append("source_url_not_https")
    snapshot_title = str(snapshot.get("title") or title)
    if _is_generic_title(title) or _is_generic_title(snapshot_title):
        reasons.append("source_title_not_specific_paid_task")
    if snapshot.get("source_item_found") is not True:
        reasons.append("source_item_not_found")
    source_state = str(snapshot.get("state") or "unknown").lower()
    if "github.com/" in source_url and source_state != "open":
        reasons.append(f"github_source_not_open:{source_state}")
    acceptance_clues = snapshot.get("acceptance_clues") if isinstance(snapshot, dict) else []
    if not isinstance(acceptance_clues, list) or not acceptance_clues:
        reasons.append("source_lacks_acceptance_clues")
        acceptance_count = 0
    else:
        acceptance_count = len(acceptance_clues)
    return {
        "lease_id": request.get("lease_id", ""),
        "title": title,
        "source_url": source_url,
        "price_usd": price_usd,
        "source_state": source_state,
        "acceptance_clues_count": acceptance_count,
        "delivery_plan": str(delivery_plan),
        "lease_preflight": str(preflight_path),
        "source_scope_snapshot": str(snapshot_md_path),
        "passed": not reasons,
        "status": "pass" if not reasons else "hold",
        "reasons": reasons,
    }


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {}


def _request_price_usd(request: dict[str, Any]) -> float:
    for key in ("proposed_price_usd", "price_usd", "price"):
        try:
            value = float(request.get(key) or 0)
        except (TypeError, ValueError):
            value = 0.0
        if value > 0:
            return value
    return 0.0


def _is_generic_title(title: str) -> bool:
    return title.strip().lower() in GENERIC_TITLES


def _md(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ").strip()


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


if __name__ == "__main__":
    raise SystemExit(main())
