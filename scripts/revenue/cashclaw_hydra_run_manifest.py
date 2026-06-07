#!/usr/bin/env python3
"""Write a local launch manifest for a CashClaw Revenue Hydra run."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any
from datetime import datetime, timezone


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-root", required=True)
    parser.add_argument("--source-config", default="")
    parser.add_argument("--process-substring", default="cashclaw_revenue_hydra.py")
    args = parser.parse_args(argv)

    run_root = Path(args.run_root).expanduser().resolve()
    source_config = Path(args.source_config).expanduser().resolve() if args.source_config else None
    manifest = build_run_manifest(
        run_root=run_root,
        source_config=source_config,
        process_substring=args.process_substring,
    )
    write_run_manifest(run_root, manifest)
    return 0


def build_run_manifest(*, run_root: Path, source_config: Path | None, process_substring: str) -> dict[str, Any]:
    audit = _read_json(run_root / "objective_audit.json")
    lease_requests = _read_json(run_root / "operator_revenue_lease_requests.json")
    watchdog = _read_json(run_root / "watchdog_status.json")
    summaries = _read_json(run_root / "summaries.json")
    source_config_payload = _read_json(source_config) if source_config is not None else {}
    active_processes = _matching_processes(process_substring)
    if not active_processes and isinstance(watchdog.get("matching_processes"), list):
        active_processes = [str(item) for item in watchdog.get("matching_processes", []) if str(item).strip()]
    latest_summary = summaries[-1] if isinstance(summaries, list) and summaries else {}
    return {
        "generated_at": utc_now_iso(),
        "schema": "cashclaw_hydra_run_manifest.v1",
        "run_root": str(run_root),
        "source_config": str(source_config) if source_config is not None else "",
        "source_config_sha256": _sha256_file(source_config) if source_config is not None else "",
        "source_count": len(source_config_payload.get("sources", [])) if isinstance(source_config_payload, dict) else 0,
        "hydra_process_running": bool(active_processes),
        "active_processes": active_processes,
        "latest_cycle": latest_summary.get("cycle"),
        "latest_cycle_timestamp": latest_summary.get("timestamp", ""),
        "objective_status": audit.get("status", "missing"),
        "objective_complete": audit.get("complete") is True,
        "objective_holds": [
            item.get("requirement")
            for item in audit.get("requirements", [])
            if isinstance(item, dict) and not item.get("passed")
        ],
        "lease_status": lease_requests.get("status", "missing"),
        "lease_request_count": len(lease_requests.get("requests", [])) if isinstance(lease_requests.get("requests"), list) else 0,
        "watchdog_alerts": watchdog.get("alerts", []),
        "no_external_side_effects": True,
        "allowed_actions": [
            "Read allowlisted public sources only when DHARMA_CASHCLAW_ALLOW_LIVE_INTAKE=1 and --allow-network are present.",
            "Score and rank local opportunity packets.",
            "Write local-only reports, preflight receipts, source-scope snapshots, and operator lease requests.",
            "Continue sleeping between cycles and refreshing local artifacts.",
        ],
        "forbidden_actions": [
            "Do not send outreach, comments, bids, claims, PRs, emails, DMs, or submissions.",
            "Do not request, accept, move, custody, or configure payment.",
            "Do not use credentials, private accounts, private repositories, secrets, or non-public data.",
            "Do not perform regulated, security-sensitive, exploit, biometric, credential, or payment-rail work.",
            "Do not treat a draft operator lease request as approval.",
        ],
        "completion_criteria": [
            "objective_audit.complete is true.",
            "objective_audit overnight_duration requirement passes with at least 8 observed hours.",
            "Live market scanning, ranked paid opportunities, delivery packets, source-scope snapshots, and lease preflights pass.",
            "lease_packet_quality_audit passes when lease-ready packets exist.",
            "external_side_effects_performed remains false.",
            "lease_status remains draft_only_not_granted unless the operator explicitly grants a bounded revenue lease.",
        ],
        "artifact_map": {
            "morning_report": str(run_root / "morning_report.md"),
            "objective_audit": str(run_root / "objective_audit.md"),
            "operator_revenue_lease_requests": str(run_root / "operator_revenue_lease_requests.md"),
            "watchdog_status": str(run_root / "watchdog_status.md"),
            "cash_memory": str(run_root / "cash_memory.json"),
            "best_ready_packets": str(run_root / "best_ready_packets.md"),
            "lease_packet_quality_audit": str(run_root / "lease_packet_quality_audit.md"),
            "summaries": str(run_root / "summaries.json"),
        },
    }


def write_run_manifest(run_root: Path, manifest: dict[str, Any]) -> None:
    (run_root / "run_manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (run_root / "run_manifest.md").write_text(run_manifest_markdown(manifest), encoding="utf-8")


def run_manifest_markdown(manifest: dict[str, Any]) -> str:
    allowed = "\n".join(f"- {item}" for item in manifest.get("allowed_actions", []))
    forbidden = "\n".join(f"- {item}" for item in manifest.get("forbidden_actions", []))
    criteria = "\n".join(f"- {item}" for item in manifest.get("completion_criteria", []))
    holds = "\n".join(f"- {item}" for item in manifest.get("objective_holds", [])) or "- none"
    alerts = "\n".join(f"- {item}" for item in manifest.get("watchdog_alerts", [])) or "- none"
    artifacts = "\n".join(f"- {name}: `{path}`" for name, path in manifest.get("artifact_map", {}).items())
    processes = "\n".join(f"- `{item}`" for item in manifest.get("active_processes", [])) or "- none"
    return (
        "# CashClaw Hydra Run Manifest\n\n"
        f"- Generated: {manifest.get('generated_at', '')}\n"
        f"- Run root: `{manifest.get('run_root', '')}`\n"
        f"- Source config: `{manifest.get('source_config', '')}`\n"
        f"- Source config sha256: `{manifest.get('source_config_sha256', '')}`\n"
        f"- Source count: {manifest.get('source_count', 0)}\n"
        f"- Hydra process running: {manifest.get('hydra_process_running')}\n"
        f"- Latest cycle: {manifest.get('latest_cycle')}\n"
        f"- Objective status: `{manifest.get('objective_status', '')}`\n"
        f"- Objective complete: {manifest.get('objective_complete')}\n"
        f"- Lease status: `{manifest.get('lease_status', '')}`\n"
        f"- Lease request count: {manifest.get('lease_request_count', 0)}\n"
        f"- External side effects allowed/performed: false\n\n"
        "## Objective Holds\n\n"
        f"{holds}\n\n"
        "## Watchdog Alerts\n\n"
        f"{alerts}\n\n"
        "## Allowed Actions\n\n"
        f"{allowed}\n\n"
        "## Forbidden Actions\n\n"
        f"{forbidden}\n\n"
        "## Completion Criteria\n\n"
        f"{criteria}\n\n"
        "## Artifacts\n\n"
        f"{artifacts}\n\n"
        "## Active Processes\n\n"
        f"{processes}\n"
    )


def _read_json(path: Path | None) -> Any:
    if path is None:
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {}


def _sha256_file(path: Path | None) -> str:
    if path is None:
        return ""
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return ""


def _matching_processes(process_substring: str) -> list[str]:
    try:
        proc = subprocess.run(
            ["pgrep", "-fl", process_substring],
            check=False,
            text=True,
            capture_output=True,
        )
    except OSError:
        return []
    rows = [line.strip() for line in proc.stdout.splitlines() if line.strip()]
    return [row for row in rows if "cashclaw_hydra_run_manifest.py" not in row]


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


if __name__ == "__main__":
    raise SystemExit(main())
