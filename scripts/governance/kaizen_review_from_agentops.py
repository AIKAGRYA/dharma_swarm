#!/usr/bin/env python3
"""Build a minimal KaizenReview artifact from AgentOps report(s).

This script is intentionally local and file-oriented. It reads AgentOps
`report.json` files, classifies basic operational signals, and writes:

- `kaizen_review.json`
- `kaizen_review.md`

It does not assign authoritative YDS ratings. `human_yds_rating` is always
null and remains a human-only boundary.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


VALID_GATE_STATES = {"green", "red", "unknown"}
VALID_SCOPE_STATES = {"clean", "violation", "unknown"}
VALID_COMMIT_STATES = {"created", "no_commit", "approval_blocked"}


@dataclass(frozen=True)
class AgentOpsSnapshot:
    report_path: Path
    job_id: str
    status: str
    gate_state: str
    scope_state: str
    commit_state: str
    changed_files: list[str]
    failed_gates: list[str]
    commit_hash: str | None


class KaizenBridgeError(Exception):
    """Raised when input data is invalid or insufficient."""


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _discover_report_paths(inputs: list[Path]) -> list[Path]:
    discovered: list[Path] = []
    for input_path in inputs:
        resolved = input_path.expanduser().resolve()
        if resolved.is_dir():
            discovered.extend(sorted(resolved.glob("**/report.json")))
        elif resolved.is_file():
            discovered.append(resolved)
    # Keep deterministic order and remove duplicates.
    unique: dict[str, Path] = {}
    for path in discovered:
        unique[str(path)] = path
    return sorted(unique.values(), key=lambda p: str(p))


def _gate_state(report: dict[str, Any]) -> tuple[str, list[str]]:
    gates = report.get("gates")
    if not isinstance(gates, list) or not gates:
        return "unknown", []

    failed: list[str] = []
    for gate in gates:
        if not isinstance(gate, dict):
            continue
        if bool(gate.get("passed")):
            continue
        name = str(gate.get("name") or "unnamed")
        exit_code = gate.get("exit_code")
        failed.append(f"{name} (exit {exit_code})")
    return ("red", failed) if failed else ("green", [])


def _scope_state(report: dict[str, Any]) -> tuple[str, list[str]]:
    scope = report.get("scope")
    if not isinstance(scope, dict):
        return "unknown", []
    changed = scope.get("changed_files")
    changed_files = [str(item) for item in changed] if isinstance(changed, list) else []
    passed = scope.get("passed")
    if passed is True:
        return "clean", changed_files
    if passed is False:
        return "violation", changed_files
    return "unknown", changed_files


def _commit_state(report: dict[str, Any]) -> tuple[str, str | None]:
    commit_hash_raw = report.get("commit_hash")
    commit_hash = str(commit_hash_raw).strip() if commit_hash_raw else None
    if commit_hash:
        return "created", commit_hash

    decision = str(report.get("commit_decision") or "").lower()
    if "approval" in decision:
        return "approval_blocked", None
    return "no_commit", None


def _to_snapshot(report_path: Path, report: dict[str, Any]) -> AgentOpsSnapshot:
    gate_state, failed_gates = _gate_state(report)
    scope_state, changed_files = _scope_state(report)
    commit_state, commit_hash = _commit_state(report)
    if gate_state not in VALID_GATE_STATES:
        raise KaizenBridgeError(f"invalid gate state for {report_path}")
    if scope_state not in VALID_SCOPE_STATES:
        raise KaizenBridgeError(f"invalid scope state for {report_path}")
    if commit_state not in VALID_COMMIT_STATES:
        raise KaizenBridgeError(f"invalid commit state for {report_path}")

    job_id = str(report.get("job_id") or report_path.parent.parent.name or "unknown-job")
    status = str(report.get("status") or "unknown")
    return AgentOpsSnapshot(
        report_path=report_path,
        job_id=job_id,
        status=status,
        gate_state=gate_state,
        scope_state=scope_state,
        commit_state=commit_state,
        changed_files=changed_files,
        failed_gates=failed_gates,
        commit_hash=commit_hash,
    )


def _waste_patterns(snapshots: list[AgentOpsSnapshot]) -> list[str]:
    patterns: list[str] = []
    if any(s.gate_state == "red" for s in snapshots):
        patterns.append("Gate failures consumed cycles without merge-ready output.")
    if any(s.scope_state == "violation" for s in snapshots):
        patterns.append("Scope violations produced rework and blocked safe integration.")
    if any(s.commit_state == "approval_blocked" for s in snapshots):
        patterns.append("Commit-ready work paused at approval boundary; batch approvals to reduce latency.")
    if not patterns:
        patterns.append("No dominant waste pattern detected in this review window.")
    return patterns


def _stop_doing_items(snapshots: list[AgentOpsSnapshot]) -> list[str]:
    items: list[str] = []
    if any(s.gate_state == "red" for s in snapshots):
        items.append("Stop promoting packets with unresolved red gates.")
    if any(s.scope_state == "violation" for s in snapshots):
        items.append("Stop running packets with broad file scope until allowed_files/forbidden_files are tightened.")
    if not items:
        items.append("Stop ad-hoc clipboard orchestration when packet evidence is available.")
    return items


def _playbook_candidates(snapshots: list[AgentOpsSnapshot]) -> list[str]:
    candidates: list[str] = []
    if any(s.gate_state == "green" and s.scope_state == "clean" for s in snapshots):
        candidates.append("Pre-flight packet lint: verify gate commands and scope before execution.")
    if any(s.commit_state == "approval_blocked" for s in snapshots):
        candidates.append("Approval SLA lane: human commit-approval turn-around target under one review cycle.")
    if not candidates:
        candidates.append("Packet hygiene checklist for repeatable AgentOps execution.")
    return candidates


def _what_worked(snapshots: list[AgentOpsSnapshot]) -> list[str]:
    worked: list[str] = []
    if any(s.gate_state == "green" for s in snapshots):
        worked.append("At least one packet completed with green gates.")
    if any(s.scope_state == "clean" for s in snapshots):
        worked.append("At least one packet stayed within its declared file scope.")
    if any(s.commit_state == "created" for s in snapshots):
        worked.append("At least one packet produced a local commit candidate.")
    if not worked:
        worked.append("No repeatable success pattern detected yet.")
    return worked


def _what_failed(snapshots: list[AgentOpsSnapshot]) -> list[str]:
    failed: list[str] = []
    if any(s.gate_state == "red" for s in snapshots):
        failed.append("One or more packets had red gates.")
    if any(s.scope_state == "violation" for s in snapshots):
        failed.append("One or more packets changed files outside the declared scope.")
    if any(s.gate_state == "unknown" or s.scope_state == "unknown" for s in snapshots):
        failed.append("One or more reports were missing classification fields.")
    if not failed:
        failed.append("No hard failure pattern detected in this review window.")
    return failed


def _next_packet_recommendation(snapshots: list[AgentOpsSnapshot]) -> str:
    if any(s.gate_state == "red" for s in snapshots):
        return "Create a focused work packet that fixes the first red gate and reruns only that gate set."
    if any(s.scope_state == "violation" for s in snapshots):
        return "Create a scope-hardening work packet that narrows allowed_files and reruns the blocked job."
    if any(s.commit_state == "approval_blocked" for s in snapshots):
        return "Create an approval-resolution work packet to capture commit decision and close review latency."
    return "Create a daily-brief evidence packet that links latest AgentOps and Kaizen outputs into operator review."


def build_kaizen_review(report_paths: list[Path], *, review_id: str) -> dict[str, Any]:
    if not report_paths:
        raise KaizenBridgeError("no AgentOps report.json inputs found")

    snapshots: list[AgentOpsSnapshot] = []
    for report_path in report_paths:
        data = _read_json(report_path)
        if not isinstance(data, dict):
            continue
        snapshots.append(_to_snapshot(report_path, data))
    if not snapshots:
        raise KaizenBridgeError("no readable AgentOps report.json inputs found")

    gate_green = sum(1 for s in snapshots if s.gate_state == "green")
    gate_red = sum(1 for s in snapshots if s.gate_state == "red")
    gate_unknown = len(snapshots) - gate_green - gate_red
    scope_clean = sum(1 for s in snapshots if s.scope_state == "clean")
    scope_violation = sum(1 for s in snapshots if s.scope_state == "violation")
    scope_unknown = len(snapshots) - scope_clean - scope_violation
    commit_created = sum(1 for s in snapshots if s.commit_state == "created")
    commit_no_commit = sum(1 for s in snapshots if s.commit_state == "no_commit")
    commit_approval_blocked = sum(1 for s in snapshots if s.commit_state == "approval_blocked")
    source_reports = [str(s.report_path) for s in snapshots]
    gate_summary = {"green": gate_green, "red": gate_red, "unknown": gate_unknown}
    scope_summary = {"clean": scope_clean, "violation": scope_violation, "unknown": scope_unknown}
    commit_summary = {
        "created": commit_created,
        "no_commit": commit_no_commit,
        "approval_blocked": commit_approval_blocked,
    }
    approval_summary = {
        "human_approval_needed": commit_approval_blocked,
        "human_approval_not_needed": len(snapshots) - commit_approval_blocked,
    }
    playbook_candidates = _playbook_candidates(snapshots)

    return {
        "id": review_id,
        "title": f"KaizenReview for {review_id}",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": "agentops-report-bridge-v0",
        "source_reports": source_reports,
        "input_reports": source_reports,
        "jobs_reviewed": len(snapshots),
        "gate_summary": gate_summary,
        "scope_summary": scope_summary,
        "commit_summary": commit_summary,
        "approval_summary": approval_summary,
        "summary": {
            "jobs": len(snapshots),
            "gate_counts": gate_summary,
            "scope_counts": scope_summary,
            "commit_counts": commit_summary,
        },
        "jobs": [
            {
                "job_id": s.job_id,
                "status": s.status,
                "gate_state": s.gate_state,
                "scope_state": s.scope_state,
                "commit_state": s.commit_state,
                "failed_gates": s.failed_gates,
                "changed_files": s.changed_files,
                "commit_hash": s.commit_hash,
            }
            for s in snapshots
        ],
        "what_worked": _what_worked(snapshots),
        "what_failed": _what_failed(snapshots),
        "waste_patterns": _waste_patterns(snapshots),
        "stop_doing_items": _stop_doing_items(snapshots),
        "playbook_update_candidates": playbook_candidates,
        "playbook_candidates": playbook_candidates,
        "next_work_packet_recommendation": _next_packet_recommendation(snapshots),
        "human_yds_rating": None,
        "yds_prompt_for_human": "Human: rate this run with an explicit YDS score and short reason.",
        "ai_yds_recommendation": "non-authoritative: human-only boundary maintained",
    }


def render_markdown(review: dict[str, Any]) -> str:
    summary = review.get("summary", {})
    gates = summary.get("gate_counts", {})
    scopes = summary.get("scope_counts", {})
    commits = summary.get("commit_counts", {})
    lines = [
        f"# {review.get('title', 'KaizenReview')}",
        "",
        f"- Review ID: `{review.get('id', 'unknown')}`",
        f"- Generated at: `{review.get('generated_at', '')}`",
        f"- Jobs reviewed: `{summary.get('jobs', 0)}`",
        "",
        "## Classification Summary",
        "",
        f"- Gates: green={gates.get('green', 0)}, red={gates.get('red', 0)}, unknown={gates.get('unknown', 0)}",
        f"- Scope: clean={scopes.get('clean', 0)}, violation={scopes.get('violation', 0)}, unknown={scopes.get('unknown', 0)}",
        f"- Commit: created={commits.get('created', 0)}, no_commit={commits.get('no_commit', 0)}, approval_blocked={commits.get('approval_blocked', 0)}",
        "",
        "## Waste Patterns",
        "",
    ]
    lines.extend(f"- {item}" for item in review.get("waste_patterns", []))
    lines.extend(["", "## Stop Doing", ""])
    lines.extend(f"- {item}" for item in review.get("stop_doing_items", []))
    lines.extend(["", "## Playbook Candidates", ""])
    lines.extend(f"- {item}" for item in review.get("playbook_candidates", []))
    lines.extend(
        [
            "",
            "## Next Work Packet Recommendation",
            "",
            f"- {review.get('next_work_packet_recommendation', '')}",
            "",
            "## Human YDS Boundary",
            "",
            f"- human_yds_rating: `{review.get('human_yds_rating')}`",
            "- AI does not assign authoritative YDS ratings.",
            "",
        ]
    )
    return "\n".join(lines)


def write_outputs(review: dict[str, Any], output_dir: Path) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "kaizen_review.json"
    md_path = output_dir / "kaizen_review.md"
    json_path.write_text(json.dumps(review, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    md_path.write_text(render_markdown(review), encoding="utf-8")
    return json_path, md_path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build KaizenReview from AgentOps reports")
    parser.add_argument(
        "inputs",
        nargs="+",
        help="One or more AgentOps report.json files or directories containing report.json files",
    )
    parser.add_argument(
        "--id",
        dest="review_id",
        default=None,
        help="Optional review id (default: kaizen-<utc timestamp>)",
    )
    parser.add_argument(
        "--output-root",
        default="reports/kaizen",
        help="Output root directory (default: reports/kaizen)",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    review_id = args.review_id or f"kaizen-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
    report_paths = _discover_report_paths([Path(item) for item in args.inputs])
    try:
        review = build_kaizen_review(report_paths, review_id=review_id)
    except KaizenBridgeError as exc:
        print(f"Kaizen bridge error: {exc}")
        return 2

    output_dir = Path(args.output_root).expanduser().resolve() / review_id
    json_path, md_path = write_outputs(review, output_dir)
    print(f"Wrote: {json_path}")
    print(f"Wrote: {md_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
