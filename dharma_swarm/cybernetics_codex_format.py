"""Markdown rendering for the Cybernetics Codex audit packet."""

from __future__ import annotations

from typing import Any


def format_markdown(report: dict[str, Any]) -> str:
    """Render a compact human-readable audit packet."""
    lines = [
        "# cybernetics_codex Audit",
        "",
        f"- observed_at: `{report['observed_at']}`",
        f"- mode: `{report['agent']['mode']}`",
        f"- manifest_registered: `{report['manifest_registration'].get('registered')}`",
        f"- loop_track_found: `{report['active_track'].get('loop_track_found')}`",
        f"- seed_registered: `{report['seed_registration'].get('registered')}`",
        f"- live_registration: `{report['live_registration'].get('registered')}`",
        f"- nats_runtime_status: `{report['live_registration'].get('nats_runtime_status')}`",
        "",
        "## Runtime",
        "",
    ]
    runtime = report["runtime"]
    delegation = runtime.get("delegation_runs") or {}
    receipt = runtime.get("receipt_json") or {}
    provider_truth = runtime.get("provider_truth") or {}
    delegation_truth = provider_truth.get("delegation_runs") or {}
    runtime_receipt_truth = provider_truth.get("runtime_receipts") or {}
    lines.extend([
        f"- runtime_db: `{runtime.get('path')}`",
        f"- read_ok: `{runtime.get('read_ok')}`",
        f"- scope_since: `{(runtime.get('scope') or {}).get('since')}`",
        f"- delegation_runs: `{delegation.get('total', 0)}` total, "
        f"`{delegation.get('completed', 0)}` completed, "
        f"`{delegation.get('failed', 0)}` failed",
        f"- receipt_json: `{receipt.get('rows_with_receipt_json', 0)}` rows "
        "`(orchestrator surface; A2A empty is success)`",
        f"- served_provider_truth: delegation completed "
        f"`{delegation_truth.get('completed_with_served_provider_model', 0)}/"
        f"{delegation_truth.get('completed', 0)}`, runtime_receipts "
        f"`{runtime_receipt_truth.get('rows_with_served_provider_model', 0)}` rows",
        "",
        "## Harness Replays",
        "",
    ])
    loop1_replay = ((report.get("bounded_replays") or {}).get("loop1") or {})
    lines.extend([
        f"- loop1_report: `{loop1_replay.get('path')}`",
        f"- loop1_closed: `{loop1_replay.get('closed')}`",
        f"- loop1_tasks: `{loop1_replay.get('tasks_completed', 0)}/"
        f"{loop1_replay.get('tasks_requested', 0)}`",
        f"- loop1_dispatch_dropoffs: `{loop1_replay.get('dispatch_dropoffs', 0)}`",
        f"- loop1_evidence_receipts_ok: `{loop1_replay.get('evidence_receipts_ok', 0)}`",
        "",
        "## Verdict Tiers",
        "",
        "- `HARNESS_PROVEN`: bounded replay/regression evidence passed; not production-live closure.",
        "- `CLOSED_LIVE`: declared live owner-surface evidence passed.",
        "",
        "## Loop Statuses",
        "",
        "| # | Loop | Verdict | Boundary | Live Owner-Surface Criterion |",
        "|---|---|---|---|---|",
    ])
    for row in report["loop_statuses"]:
        lines.append(
            f"| {row['number']} | {row['label']} | {row['verdict']} | "
            f"{str(row['blocker']).replace('|', '/')} | "
            f"{str(row.get('live_owner_surface_criterion', '')).replace('|', '/')} |"
        )
    lines.extend([
        "",
        "## Verifier Commands",
        "",
        *[f"- `{cmd}`" for cmd in report["verifier_commands"]],
    ])
    return "\n".join(lines)
