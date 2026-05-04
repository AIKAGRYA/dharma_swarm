#!/usr/bin/env python3
"""Build a KaizenReview from AgentOps report.json files.

KaizenReview v0 is a read-only improvement bridge over completed AgentOps
runs. It reads AgentOps reports, classifies gate/scope/commit/approval
outcomes, and writes JSON plus Markdown review artifacts. It never runs git,
never merges or pushes, and never assigns an authoritative YDS rating.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class KaizenReviewError(RuntimeError):
    """Raised when inputs cannot produce a useful KaizenReview."""


@dataclass(frozen=True)
class ReportReview:
    source_path: str
    job_id: str
    status: str
    gate_classification: str
    scope_classification: str
    commit_classification: str
    approval_classification: str
    failed_gates: list[str]
    scope_violations: list[dict[str, Any]]
    changed_file_count: int
    commit_hash: str | None
    commit_decision: str
    missing_fields: list[str]
    waste_patterns: list[str]


REQUIRED_REPORT_FIELDS = {
    "job_id",
    "status",
    "gates",
    "scope",
    "approval",
    "commit_decision",
}

YDS_PROMPT = (
    "Human-only: if this review produced a useful artifact, assign an "
    "authoritative YDS rating outside this tool and record it in the future "
    "YDS ledger. AI suggestions are advisory only."
)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _gate_state(gate: Any) -> str:
    if not isinstance(gate, dict):
        return "unknown"
    passed = gate.get("passed")
    if isinstance(passed, bool):
        return "green" if passed else "red"
    exit_code = gate.get("exit_code")
    if isinstance(exit_code, int):
        return "green" if exit_code == 0 else "red"
    return "unknown"


def _gate_name(gate: Any, index: int) -> str:
    if isinstance(gate, dict) and str(gate.get("name") or "").strip():
        return str(gate["name"]).strip()
    return f"gate-{index + 1}"


def classify_gates(report: dict[str, Any]) -> tuple[str, list[str]]:
    gates = report.get("gates")
    if not isinstance(gates, list) or not gates:
        return "unknown", []
    states = [_gate_state(gate) for gate in gates]
    failed = [
        _gate_name(gate, index)
        for index, gate in enumerate(gates)
        if _gate_state(gate) == "red"
    ]
    if all(state == "green" for state in states):
        return "all green", []
    if any(state == "red" for state in states):
        return "some red", failed
    return "unknown", []


def classify_scope(report: dict[str, Any]) -> tuple[str, list[dict[str, Any]], int]:
    scope = report.get("scope")
    if not isinstance(scope, dict):
        return "unknown", [], 0
    violations = [
        item for item in _as_list(scope.get("violations"))
        if isinstance(item, dict)
    ]
    changed_files = _as_list(scope.get("changed_files"))
    if violations:
        return "scope violation", violations, len(changed_files)
    passed = scope.get("passed")
    if passed is True:
        return "scope clean", [], len(changed_files)
    if passed is False:
        return "scope violation", violations, len(changed_files)
    return "unknown", violations, len(changed_files)


def classify_commit(report: dict[str, Any]) -> tuple[str, str | None, str]:
    commit_hash_raw = report.get("commit_hash")
    commit_hash = str(commit_hash_raw).strip() if commit_hash_raw else None
    decision = str(report.get("commit_decision") or "").strip()
    lowered = decision.lower()
    if commit_hash:
        return "commit created", commit_hash, decision
    if "human approval" in lowered or "approval required" in lowered:
        return "blocked by approval", None, decision
    if decision and decision != "not evaluated":
        return "no commit", None, decision
    return "unknown", None, decision


def classify_approval(report: dict[str, Any]) -> str:
    approval = report.get("approval")
    if not isinstance(approval, dict):
        return "unknown"
    if approval.get("before_commit") is True or approval.get("before_merge") is True:
        return "human approval needed"
    return "not needed"


def report_waste_patterns(
    *,
    report: dict[str, Any],
    gate_classification: str,
    scope_classification: str,
    commit_classification: str,
    changed_file_count: int,
    missing_fields: list[str],
) -> list[str]:
    decision = str(report.get("commit_decision") or "").lower()
    patterns: list[str] = []
    if "target worktree dirty" in decision or "dirty before gates" in decision:
        patterns.append("dirty worktree start")
    if gate_classification == "some red":
        patterns.append("failed gate")
    if scope_classification == "scope violation":
        patterns.append("out-of-scope files")
    if commit_classification == "blocked by approval":
        patterns.append("approval blocked")
    if changed_file_count == 0 or "no changes to commit" in decision:
        patterns.append("no changed files")
    if missing_fields:
        patterns.append("missing report fields")
    return sorted(set(patterns))


def classify_report(path: Path, report: dict[str, Any]) -> ReportReview:
    gate_classification, failed_gates = classify_gates(report)
    scope_classification, violations, changed_count = classify_scope(report)
    commit_classification, commit_hash, decision = classify_commit(report)
    approval_classification = classify_approval(report)
    missing_fields = sorted(REQUIRED_REPORT_FIELDS - set(report))
    waste = report_waste_patterns(
        report=report,
        gate_classification=gate_classification,
        scope_classification=scope_classification,
        commit_classification=commit_classification,
        changed_file_count=changed_count,
        missing_fields=missing_fields,
    )
    return ReportReview(
        source_path=path.as_posix(),
        job_id=str(report.get("job_id") or "unknown"),
        status=str(report.get("status") or "unknown"),
        gate_classification=gate_classification,
        scope_classification=scope_classification,
        commit_classification=commit_classification,
        approval_classification=approval_classification,
        failed_gates=failed_gates,
        scope_violations=violations,
        changed_file_count=changed_count,
        commit_hash=commit_hash,
        commit_decision=decision,
        missing_fields=missing_fields,
        waste_patterns=waste,
    )


def find_report_paths(inputs: list[Path]) -> list[Path]:
    paths: list[Path] = []
    for item in inputs:
        if not item.exists():
            raise KaizenReviewError(f"input does not exist: {item}")
        if item.is_dir():
            paths.extend(sorted(item.rglob("report.json")))
        elif item.is_file():
            paths.append(item)
        else:
            raise KaizenReviewError(f"input is neither file nor directory: {item}")
    unique: dict[str, Path] = {}
    for path in paths:
        unique[path.resolve().as_posix()] = path
    if not unique:
        raise KaizenReviewError("no AgentOps report.json files found")
    return [unique[key] for key in sorted(unique)]


def load_report(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise KaizenReviewError(f"invalid JSON in {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise KaizenReviewError(f"report root must be an object: {path}")
    return data


def _count(reviews: list[ReportReview], attr: str, value: str) -> int:
    return sum(1 for review in reviews if getattr(review, attr) == value)


def summarize_gates(reviews: list[ReportReview]) -> dict[str, Any]:
    failed_counts: dict[str, int] = {}
    for review in reviews:
        for gate in review.failed_gates:
            failed_counts[gate] = failed_counts.get(gate, 0) + 1
    return {
        "all_green": _count(reviews, "gate_classification", "all green"),
        "some_red": _count(reviews, "gate_classification", "some red"),
        "unknown": _count(reviews, "gate_classification", "unknown"),
        "failed_gates": dict(sorted(failed_counts.items())),
    }


def summarize_scope(reviews: list[ReportReview]) -> dict[str, Any]:
    violation_files: list[str] = []
    for review in reviews:
        for violation in review.scope_violations:
            path = str(violation.get("path") or "").strip()
            if path:
                violation_files.append(path)
    return {
        "clean": _count(reviews, "scope_classification", "scope clean"),
        "violations": _count(reviews, "scope_classification", "scope violation"),
        "unknown": _count(reviews, "scope_classification", "unknown"),
        "violation_files": sorted(set(violation_files)),
    }


def summarize_commits(reviews: list[ReportReview]) -> dict[str, Any]:
    return {
        "created": _count(reviews, "commit_classification", "commit created"),
        "blocked_by_approval": _count(reviews, "commit_classification", "blocked by approval"),
        "no_commit": _count(reviews, "commit_classification", "no commit"),
        "unknown": _count(reviews, "commit_classification", "unknown"),
        "commit_hashes": sorted(
            review.commit_hash for review in reviews if review.commit_hash
        ),
    }


def summarize_approval(reviews: list[ReportReview]) -> dict[str, Any]:
    return {
        "human_approval_needed": _count(
            reviews, "approval_classification", "human approval needed"
        ),
        "not_needed": _count(reviews, "approval_classification", "not needed"),
        "unknown": _count(reviews, "approval_classification", "unknown"),
    }


def collect_waste_patterns(reviews: list[ReportReview]) -> list[str]:
    counts: dict[str, int] = {}
    for review in reviews:
        for pattern in review.waste_patterns:
            counts[pattern] = counts.get(pattern, 0) + 1
    for gate, count in summarize_gates(reviews)["failed_gates"].items():
        if count > 1:
            counts[f"failed gate repeated: {gate}"] = count
    return [
        f"{name} ({count} report{'s' if count != 1 else ''})"
        for name, count in sorted(counts.items())
    ]


def build_what_worked(reviews: list[ReportReview]) -> list[str]:
    worked: list[str] = []
    if _count(reviews, "gate_classification", "all green"):
        worked.append("At least one AgentOps run completed with all gates green.")
    if _count(reviews, "scope_classification", "scope clean"):
        worked.append("At least one AgentOps run stayed inside its declared file scope.")
    if _count(reviews, "commit_classification", "commit created"):
        worked.append("At least one AgentOps run produced a local commit candidate.")
    if all(review.gate_classification == "all green" for review in reviews):
        worked.append("All reviewed AgentOps runs had green gates.")
    return worked or ["No reliable success pattern was present in the reviewed reports."]


def build_what_failed(reviews: list[ReportReview]) -> list[str]:
    failed: list[str] = []
    if _count(reviews, "gate_classification", "some red"):
        failed.append("One or more AgentOps runs had failing gates.")
    if _count(reviews, "scope_classification", "scope violation"):
        failed.append("One or more AgentOps runs changed files outside allowed scope.")
    if any(review.missing_fields for review in reviews):
        failed.append("One or more reports were missing expected AgentOps fields.")
    if _count(reviews, "commit_classification", "blocked by approval"):
        failed.append("One or more commit candidates were blocked by human approval policy.")
    return failed


def build_stop_doing_items(waste_patterns: list[str]) -> list[str]:
    joined = "\n".join(waste_patterns)
    items: list[str] = []
    if "dirty worktree start" in joined:
        items.append("Do not start AgentOps runs from dirty worktrees without explicit review.")
    if "failed gate" in joined:
        items.append("Do not rerun the same failing gate without changing the packet or fixing the failure.")
    if "out-of-scope files" in joined:
        items.append("Do not widen scope after out-of-scope changes; split or narrow the packet.")
    if "approval blocked" in joined:
        items.append("Do not ask AgentOps to commit when approval.before_commit is true.")
    if "no changed files" in joined:
        items.append("Do not create build packets with no expected file delta unless the run is verification-only.")
    if "missing report fields" in joined:
        items.append("Do not consume incomplete AgentOps reports as authoritative run evidence.")
    return items


def build_playbook_candidates(waste_patterns: list[str], reviews: list[ReportReview]) -> list[str]:
    joined = "\n".join(waste_patterns)
    candidates: list[str] = []
    if "dirty worktree start" in joined:
        candidates.append("Add a pre-run clean-status check to the work-packet template.")
    if "failed gate" in joined:
        candidates.append("Add a gate-failure triage step before rerunning similar packets.")
    if "out-of-scope files" in joined:
        candidates.append("Add an allowed_files review checkpoint before agent execution starts.")
    if any(review.gate_classification == "all green" for review in reviews):
        candidates.append("Promote the green packet shape into an AgentOps example after human review.")
    if not candidates:
        candidates.append("Keep collecting AgentOps reports before changing the playbook.")
    return candidates


def choose_next_recommendation(reviews: list[ReportReview]) -> str:
    if any(review.missing_fields for review in reviews):
        return "repair AgentOps report schema"
    if any(review.gate_classification == "some red" for review in reviews):
        return "fix failed gate"
    if any(review.scope_classification == "scope violation" for review in reviews):
        return "repeat with narrower allowed_files"
    if any(review.commit_classification == "blocked by approval" for review in reviews):
        return "request human approval for commit candidate"
    if all(review.gate_classification == "all green" for review in reviews):
        return "request human YDS rating"
    if any(review.commit_classification == "commit created" for review in reviews):
        return "promote successful packet to playbook"
    return "run another AgentOps packet with complete gates"


def review_to_dict(review: ReportReview) -> dict[str, Any]:
    return {
        "source_path": review.source_path,
        "job_id": review.job_id,
        "status": review.status,
        "gate_classification": review.gate_classification,
        "scope_classification": review.scope_classification,
        "commit_classification": review.commit_classification,
        "approval_classification": review.approval_classification,
        "failed_gates": review.failed_gates,
        "scope_violations": review.scope_violations,
        "changed_file_count": review.changed_file_count,
        "commit_hash": review.commit_hash,
        "commit_decision": review.commit_decision,
        "missing_fields": review.missing_fields,
        "waste_patterns": review.waste_patterns,
    }


def build_kaizen_review(report_paths: list[Path], *, generated_at: str | None = None) -> dict[str, Any]:
    reviews = [
        classify_report(path, load_report(path))
        for path in report_paths
    ]
    waste_patterns = collect_waste_patterns(reviews)
    return {
        "source_reports": [review_to_dict(review) for review in reviews],
        "generated_at": generated_at or _utc_now_iso(),
        "jobs_reviewed": len(reviews),
        "gate_summary": summarize_gates(reviews),
        "scope_summary": summarize_scope(reviews),
        "commit_summary": summarize_commits(reviews),
        "approval_summary": summarize_approval(reviews),
        "what_worked": build_what_worked(reviews),
        "what_failed": build_what_failed(reviews),
        "waste_patterns": waste_patterns,
        "stop_doing_items": build_stop_doing_items(waste_patterns),
        "playbook_update_candidates": build_playbook_candidates(waste_patterns, reviews),
        "next_work_packet_recommendation": choose_next_recommendation(reviews),
        "human_yds_rating": None,
        "yds_prompt_for_human": YDS_PROMPT,
    }


def _escape_md(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ").strip()


def render_markdown(review: dict[str, Any]) -> str:
    lines = [
        "# KaizenReview",
        "",
        f"- Generated at: `{review['generated_at']}`",
        f"- Jobs reviewed: `{review['jobs_reviewed']}`",
        f"- Next work packet recommendation: `{review['next_work_packet_recommendation']}`",
        f"- Human YDS rating: `{review['human_yds_rating']}`",
        "",
        "## Source Reports",
        "",
        "| Job | Gates | Scope | Commit | Approval |",
        "|---|---|---|---|---|",
    ]
    for source in review["source_reports"]:
        lines.append(
            "| "
            + " | ".join(
                [
                    _escape_md(source["job_id"]),
                    _escape_md(source["gate_classification"]),
                    _escape_md(source["scope_classification"]),
                    _escape_md(source["commit_classification"]),
                    _escape_md(source["approval_classification"]),
                ]
            )
            + " |"
        )

    sections = [
        ("What Worked", "what_worked"),
        ("What Failed", "what_failed"),
        ("Waste Patterns", "waste_patterns"),
        ("Stop Doing Items", "stop_doing_items"),
        ("Playbook Update Candidates", "playbook_update_candidates"),
    ]
    for title, key in sections:
        lines.extend(["", f"## {title}", ""])
        values = review.get(key) or []
        if values:
            lines.extend(f"- {item}" for item in values)
        else:
            lines.append("- None")

    lines.extend(
        [
            "",
            "## YDS Boundary",
            "",
            YDS_PROMPT,
            "",
        ]
    )
    return "\n".join(lines)


def write_review(review: dict[str, Any], output_dir: Path) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "kaizen_review.json"
    md_path = output_dir / "kaizen_review.md"
    json_path.write_text(json.dumps(review, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    md_path.write_text(render_markdown(review), encoding="utf-8")
    return json_path, md_path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build a KaizenReview from AgentOps report.json files"
    )
    parser.add_argument(
        "--input",
        required=True,
        type=Path,
        nargs="+",
        action="append",
        help="AgentOps report.json path(s), or directory/directories containing reports",
    )
    parser.add_argument(
        "--output",
        required=True,
        type=Path,
        help="Output directory for kaizen_review.json and kaizen_review.md",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    inputs = [path for group in args.input for path in group]
    try:
        report_paths = find_report_paths(inputs)
        review = build_kaizen_review(report_paths)
        json_path, md_path = write_review(review, args.output)
    except KaizenReviewError as exc:
        print(f"KaizenReview error: {exc}")
        return 2

    print(f"Wrote {json_path}")
    print(f"Wrote {md_path}")
    print(f"Reviewed {review['jobs_reviewed']} AgentOps report(s)")
    print(f"Next: {review['next_work_packet_recommendation']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
