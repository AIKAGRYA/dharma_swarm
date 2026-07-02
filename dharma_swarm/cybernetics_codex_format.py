"""Markdown rendering for the Cybernetics Codex audit packet."""

from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any


def _loop_sort_key(value: str) -> int:
    try:
        return int(str(value).removeprefix("loop"))
    except ValueError:
        return 999


def format_markdown(report: dict[str, Any]) -> str:
    """Render a compact human-readable audit packet."""
    lines = [
        "# cybernetics_codex Audit",
        "",
        "> **READ-ONLY VERIFIER -- NOT LIVE RE-EXECUTION.** This report reads "
        "receipts and bounded replay outputs. It does not dispatch agents, "
        "rerun live owner-surface checks, or prove production-live closure.",
        "",
        f"- observed_at: `{report['observed_at']}`",
        f"- mode: `{report['agent']['mode']}`",
        f"- manifest_registered: `{report['manifest_registration'].get('registered')}`",
        f"- loop_track_found: `{report['active_track'].get('loop_track_found')}`",
        f"- seed_registered: `{report['seed_registration'].get('registered')}`",
        f"- live_registration: `{report['live_registration'].get('registered')}`",
        f"- nats_runtime_status: `{report['live_registration'].get('nats_runtime_status')}`",
        "",
        "## Field Semantics",
        "",
        "- `manifest_registered` means the steward is declared in the repo manifest; "
        "it is not loop closure evidence.",
        "- `live_registration` means local registration/onboarding surfaces exist; "
        "it is not proof that live owner-surface checks ran.",
        "- `mode: read_only_verifier` means this audit reads receipts and bounded "
        "replay outputs; it does not re-execute live owner-surface checks.",
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
    verdict_counts = Counter(row.get("verdict") for row in report["loop_statuses"])
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
    bounded_replays = report.get("bounded_replays") or {}
    loop1_replay = (bounded_replays.get("loop1") or {})
    loop1_harness_proven = bool(loop1_replay.get("harness_proven") or loop1_replay.get("closed"))
    lines.extend([
        f"- loop1_report: `{loop1_replay.get('path')}`",
        f"- loop1_harness_proven: `{loop1_harness_proven}`",
        f"- loop1_closed_live: `{loop1_replay.get('closed_live', False)}`",
        f"- loop1_tasks: `{loop1_replay.get('tasks_completed', 0)}/"
        f"{loop1_replay.get('tasks_requested', 0)}`",
        f"- loop1_dispatch_dropoffs: `{loop1_replay.get('dispatch_dropoffs', 0)}`",
        f"- loop1_evidence_receipts_ok: `{loop1_replay.get('evidence_receipts_ok', 0)}`",
        "",
        "| Replay | Harness Proven | Closed Live | Evidence | Source |",
        "|---|---|---|---|---|",
    ])
    for key in sorted(bounded_replays, key=_loop_sort_key):
        replay = bounded_replays.get(key) or {}
        evidence = []
        if "cycles" in replay:
            evidence.append(f"cycles={replay.get('cycles')}")
        if "tasks_completed" in replay:
            evidence.append(
                f"tasks={replay.get('tasks_completed')}/{replay.get('tasks_requested')}"
            )
        if "transitions_ok" in replay:
            evidence.append(f"transitions_ok={replay.get('transitions_ok')}")
        if "adapt_real" in replay:
            evidence.append(f"adapt_real={replay.get('adapt_real')}")
        path = replay.get("path")
        source = Path(path).name if path else ""
        lines.append(
            f"| {key} | {replay.get('harness_proven')} | "
            f"{replay.get('closed_live')} | {', '.join(evidence) or 'n/a'} | "
            f"`{source}` |"
        )
    lines.extend([
        "",
        "## Verdict Tiers",
        "",
        "- `HARNESS_PROVEN`: bounded replay/regression evidence passed; not production-live closure.",
        "- `CLOSED_LIVE`: declared live owner-surface evidence passed.",
        "",
        "## Verdict Counts",
        "",
        f"- `CLOSED_LIVE`: `{verdict_counts.get('CLOSED_LIVE', 0)}`",
        f"- `HARNESS_PROVEN`: `{verdict_counts.get('HARNESS_PROVEN', 0)}`",
        f"- `BLOCKED`: `{verdict_counts.get('BLOCKED', 0)}`",
        "",
        "## Live Owner-Surface Criteria",
        "",
    ])
    criteria = report.get("live_owner_surface_criteria") or {}
    for key in sorted(criteria, key=_loop_sort_key):
        lines.append(f"- `{key}`: {criteria[key]}")
    lines.extend([
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
        "## Reference Commands",
        "",
        "These commands describe the relevant operator surfaces. This audit did "
        "not execute them during markdown rendering.",
        "",
        *[f"- `{cmd}`" for cmd in report["verifier_commands"]],
    ])
    return "\n".join(lines)
