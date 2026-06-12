#!/usr/bin/env python3
"""Mechanical preflight gate for Forge Swarm Evolution Arena v0."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


TASK_GATE_SCHEMA = "forge_task_pack_gate.v1"
ROSTER_GATE_SCHEMA = "forge_roster_gate.v1"
ROI_SCHEMA = "forge_roi_governor.v1"
SCHEMA_VERSION = "forge_swarm_evolution_arena_v0_preflight.v1"
DEFAULT_OUTPUT_ROOT = Path("reports/forge/swarm-evolution-arena-v0-measurement")
TERMINAL_CLOSEOUT_STATES = {
    "positive_lift_candidate",
    "measured_negative",
    "inconclusive_low_power",
    "contaminated_quarantine",
    "blocked_with_evidence",
}


def utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def default_run_id() -> str:
    return datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ-preflight")


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha_ok(value: Any) -> bool:
    text = str(value or "")
    if text.startswith("sha256:"):
        text = text.removeprefix("sha256:")
    return len(text) == 64 and all(char in "0123456789abcdefABCDEF" for char in text)


def resolve_ref(ref: str, run_dir: Path, repo_root: Path) -> Path:
    path = Path(ref)
    if path.is_absolute():
        return path
    if (run_dir / path).exists():
        return run_dir / path
    return repo_root / path


def issue(code: str, message: str, severity: str = "red") -> dict[str, str]:
    return {"code": code, "message": message, "severity": severity}


def validate_task_pack_gate(run_dir: Path, repo_root: Path) -> dict[str, Any]:
    path = run_dir / "task_pack_gate.json"
    issues: list[dict[str, str]] = []
    payload: dict[str, Any] = {}
    if not path.exists():
        issues.append(issue("TASK_PACK_GATE_MISSING", "task_pack_gate.json is missing"))
    else:
        payload = read_json(path)
    if payload.get("schema_version") != TASK_GATE_SCHEMA:
        issues.append(issue("TASK_GATE_SCHEMA_MISMATCH", "schema_version must be forge_task_pack_gate.v1"))
    if payload.get("task_quality_tier") not in {"measurement_candidate", "external_benchmark"}:
        issues.append(issue("TASK_TIER_NOT_MEASUREMENT_ELIGIBLE", "task tier is not measurement eligible"))
    if int(payload.get("task_count") or 0) < 3:
        issues.append(issue("TASK_COUNT_BELOW_MINIMUM", "task_count must be at least 3", "yellow"))
    if int(payload.get("rubric_item_count") or 0) < 30:
        issues.append(issue("RUBRIC_COUNT_LOW_POWER", "rubric_item_count must be at least 30", "yellow"))
    manifest_ref = str(payload.get("task_manifest_path") or "")
    manifest_path = resolve_ref(manifest_ref, run_dir, repo_root) if manifest_ref else None
    if not manifest_path or not manifest_path.exists():
        issues.append(issue("TASK_MANIFEST_MISSING", "task manifest is missing", "yellow"))
    elif sha_ok(payload.get("task_manifest_sha256")):
        expected = str(payload["task_manifest_sha256"]).removeprefix("sha256:").lower()
        if sha256_file(manifest_path) != expected:
            issues.append(issue("TASK_MANIFEST_HASH_MISMATCH", "task manifest hash does not match"))
    else:
        issues.append(issue("TASK_MANIFEST_HASH_MISSING", "task manifest hash missing", "yellow"))
    for field in ("scorer_hashes", "hidden_split_hashes", "closed_book_prompt_hashes"):
        values = payload.get(field)
        if not isinstance(values, list) or not values or not all(sha_ok(value) for value in values):
            issues.append(issue(f"{field.upper()}_INVALID", f"{field} must contain sha256 hashes", "yellow"))
    if not payload.get("discard_policy_path"):
        issues.append(issue("DISCARD_POLICY_MISSING", "discard_policy_path is missing", "yellow"))
    reviews = payload.get("independent_review_receipts")
    if not isinstance(reviews, list) or not reviews:
        issues.append(issue("INDEPENDENT_REVIEW_MISSING", "independent review receipt missing", "yellow"))
    elif any(str(row.get("status") or "").lower() != "pass" for row in reviews if isinstance(row, dict)):
        issues.append(issue("INDEPENDENT_REVIEW_FAILED", "independent review receipt reports failure"))
    if payload.get("hidden_tests_inspected_by_candidate_arms") is not False:
        issues.append(issue("HIDDEN_TESTS_INSPECTED", "candidate arms inspected hidden tests"))
    if payload.get("scorer_or_holdout_changed_after_results") is not False:
        issues.append(issue("SCORER_OR_HOLDOUT_CHANGED_AFTER_RESULTS", "scorer/holdout changed after results"))
    status = "red" if any(row["severity"] == "red" for row in issues) else "yellow" if issues else "green"
    return {
        "gate": "task_pack_gate",
        "path": str(path),
        "status": status,
        "measurement_mode_allowed": status == "green",
        "issues": issues,
        "evidence": {
            "task_quality_tier": payload.get("task_quality_tier", ""),
            "task_count": int(payload.get("task_count") or 0),
            "rubric_item_count": int(payload.get("rubric_item_count") or 0),
            "scorer_hash_count": len(payload.get("scorer_hashes") or []),
            "hidden_split_hash_count": len(payload.get("hidden_split_hashes") or []),
            "closed_book_prompt_hash_count": len(payload.get("closed_book_prompt_hashes") or []),
            "independent_review_count": len(reviews or []) if isinstance(reviews, list) else 0,
        },
        "normalized_payload": {**payload, "status": status, "measurement_mode_allowed": status == "green", "reason": reason(issues)},
    }


def validate_roster_gate(run_dir: Path) -> dict[str, Any]:
    path = run_dir / "roster_gate.json"
    issues: list[dict[str, str]] = []
    payload: dict[str, Any] = {}
    if not path.exists():
        issues.append(issue("ROSTER_GATE_MISSING", "roster_gate.json is missing"))
    else:
        payload = read_json(path)
    if payload.get("schema_version") != ROSTER_GATE_SCHEMA:
        issues.append(issue("ROSTER_GATE_SCHEMA_MISMATCH", "schema_version must be forge_roster_gate.v1"))
    roles = payload.get("roles")
    if not isinstance(roles, list) or len(roles) < 3:
        issues.append(issue("ROSTER_ROLE_COUNT_BELOW_MINIMUM", "at least 3 roles required"))
        roles = roles if isinstance(roles, list) else []
    identities = {(role.get("runner"), role.get("session_or_process")) for role in roles if isinstance(role, dict)}
    if len(roles) > 1 and len(identities) == 1:
        issues.append(issue("LABELS_ONLY_SHAM_ROSTER", "all roles share one runner/session"))
    for role in roles:
        for field in ("role", "runner", "provider", "model", "session_or_process", "budget_cap", "tool_permissions", "expected_diversity_reason"):
            if not role.get(field):
                issues.append(issue("ROSTER_ROLE_FIELD_MISSING", f"role missing {field}", "yellow"))
        if str(role.get("liveness_check") or "").lower() != "pass":
            issues.append(issue("ROSTER_ROLE_LIVENESS_NOT_PASS", "role liveness is not pass", "yellow"))
    checks = payload.get("provider_key_checks")
    if not isinstance(checks, list) or not checks:
        issues.append(issue("PROVIDER_KEY_CHECKS_MISSING", "provider key checks missing", "yellow"))
    elif any(str(row.get("status") or "").lower() != "pass" for row in checks if isinstance(row, dict)):
        issues.append(issue("PROVIDER_KEY_CHECK_FAILED", "provider key check failed"))
    if not str(payload.get("decorrelation_rationale") or "").strip():
        issues.append(issue("DECORRELATION_RATIONALE_MISSING", "decorrelation rationale missing", "yellow"))
    if payload.get("low_decorrelation_warning") is True:
        issues.append(issue("LOW_DECORRELATION_WARNING", "low decorrelation roster", "yellow"))
    status = "red" if any(row["severity"] == "red" for row in issues) else "yellow" if issues else "green"
    providers = {role.get("provider") for role in roles if isinstance(role, dict) and role.get("provider")}
    models = {role.get("model") for role in roles if isinstance(role, dict) and role.get("model")}
    return {
        "gate": "roster_gate",
        "path": str(path),
        "status": status,
        "measurement_mode_allowed": status == "green",
        "issues": issues,
        "evidence": {
            "role_count": len(roles),
            "provider_count": len(providers),
            "model_count": len(models),
            "provider_key_check_count": len(checks or []) if isinstance(checks, list) else 0,
            "decorrelation_rationale_present": bool(str(payload.get("decorrelation_rationale") or "").strip()),
            "low_decorrelation_warning": bool(payload.get("low_decorrelation_warning")),
        },
        "normalized_payload": {**payload, "status": status, "measurement_mode_allowed": status == "green", "reason": reason(issues)},
    }


def validate_roi_governor(run_dir: Path) -> dict[str, Any]:
    path = run_dir / "roi_governor.jsonl"
    rows = read_jsonl(path)
    issues: list[dict[str, str]] = []
    if len(rows) >= 3:
        blockers = [str(row.get("blocker_signature") or "") for row in rows[-3:]]
        if blockers[0] and blockers.count(blockers[0]) == 3:
            issues.append(issue("ROI_REPEATED_BLOCKER_THREE_TIMES", "same blocker repeated 3 times"))
    if len(rows) >= 2 and all(row.get("new_evidence_kind") == "none" and row.get("continue_decision") == "continue" for row in rows[-2:]):
        issues.append(issue("ROI_NO_NEW_EVIDENCE_TWO_ROWS", "two no-evidence continues"))
    status = "red" if issues else "green"
    return {
        "gate": "roi_governor",
        "path": str(path),
        "status": status,
        "measurement_mode_allowed": status == "green",
        "issues": issues,
        "evidence": {
            "row_count": len(rows),
            "latest_state": rows[-1].get("state") if rows else "",
            "latest_continue_decision": rows[-1].get("continue_decision") if rows else "",
        },
        "normalized_payload": {"rows": rows},
    }


def reason(issues: list[dict[str, str]]) -> str:
    if not issues:
        return "all required gate evidence is present"
    return ", ".join(row["code"] for row in issues[:8])


def build_roi_row(generated_at: str, task_report: dict[str, Any], roster_report: dict[str, Any]) -> dict[str, Any]:
    allowed = task_report["measurement_mode_allowed"] and roster_report["measurement_mode_allowed"]
    return {
        "schema_version": ROI_SCHEMA,
        "ts": generated_at,
        "cycle": 0,
        "elapsed_minutes": 0,
        "state": "green" if allowed else "red",
        "decision_changing_artifact": "preflight gate validation packet",
        "new_evidence_kind": "liveness" if allowed else "blocker",
        "blocker_signature": "" if allowed else f"task_pack_gate:{task_report['status']};roster_gate:{roster_report['status']}",
        "same_blocker_count": 0 if allowed else 1,
        "task_changed": False,
        "intervention_changed": False,
        "hypothesis_changed": False,
        "next_action_changed": True,
        "promotion_path_still_possible": allowed,
        "budget_spent": "0",
        "budget_remaining": "preflight only; measurement budget not opened",
        "skeptical_reviewer_summary": "A reviewer can decide whether measurement mode is allowed from the two gate files.",
        "continue_decision": "continue" if allowed else "stop",
        "reason": "measurement mode allowed" if allowed else "measurement mode forbidden until both gates are green",
    }


def write_gate_files(run_dir: Path, generated_at: str, report: dict[str, Any]) -> None:
    write_json(run_dir / "task_pack_gate.json", report["task_pack_gate"]["normalized_payload"])
    write_json(run_dir / "roster_gate.json", report["roster_gate"]["normalized_payload"])
    write_jsonl(run_dir / "roi_governor.jsonl", [build_roi_row(generated_at, report["task_pack_gate"], report["roster_gate"])])


def write_readiness_packet(run_dir: Path, generated_at: str, report: dict[str, Any]) -> None:
    write_json(run_dir / "readiness_packet.json", report)
    decision_path = run_dir / "decision_packet.md"
    if terminal_closeout_exists(run_dir):
        decision_path = run_dir / "preflight_decision_packet.md"
    write_text(
        decision_path,
        "\n".join(
            [
                "# Forge Swarm Evolution Arena v0 Preflight Decision",
                "",
                f"- generated_at: {generated_at}",
                f"- closeout_state: {report['closeout_state']}",
                f"- measurement_mode_allowed: {str(report['measurement_mode_allowed']).lower()}",
                f"- task_pack_gate: {report['task_pack_gate']['status']}",
                f"- roster_gate: {report['roster_gate']['status']}",
                "",
            ]
        ),
    )


def terminal_closeout_exists(run_dir: Path) -> bool:
    report_path = run_dir / "swarm_lift_report.json"
    if not report_path.exists():
        return False
    try:
        status = str(read_json(report_path).get("status") or "")
    except Exception:
        return False
    return status in TERMINAL_CLOSEOUT_STATES


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text + ("" if text.endswith("\n") else "\n"), encoding="utf-8")


def run_preflight(
    *,
    run_dir: Path,
    repo_root: Path,
    generated_at: str | None = None,
    write_packet: bool = False,
    task_gate_path: Path | None = None,
    roster_gate_path: Path | None = None,
) -> dict[str, Any]:
    del task_gate_path, roster_gate_path
    generated = generated_at or utc_now()
    task_report = validate_task_pack_gate(run_dir, repo_root)
    roster_report = validate_roster_gate(run_dir)
    roi_report = validate_roi_governor(run_dir)
    allowed = task_report["measurement_mode_allowed"] and roster_report["measurement_mode_allowed"] and roi_report["measurement_mode_allowed"]
    terminal_closed = terminal_closeout_exists(run_dir)
    report = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": generated,
        "run_dir": str(run_dir),
        "mode_decision": "measurement_mode" if allowed else "preflight_mode",
        "measurement_mode_allowed": allowed,
        "terminal_closeout_present": terminal_closed,
        "closeout_state": "preflight_ready" if allowed else "preflight_blocked",
        "task_pack_gate": task_report,
        "roster_gate": roster_report,
        "roi_governor": roi_report,
        "next_action": (
            "terminal closeout exists; preserve measurement decision packet"
            if terminal_closed
            else "enter measurement mode with required controls"
            if allowed
            else "finish preflight evidence; do not run measurement mode or claim swarm_lift"
        ),
    }
    if write_packet:
        if not terminal_closed:
            write_gate_files(run_dir, generated, report)
            task_report = validate_task_pack_gate(run_dir, repo_root)
            roster_report = validate_roster_gate(run_dir)
            roi_report = validate_roi_governor(run_dir)
            allowed = task_report["measurement_mode_allowed"] and roster_report["measurement_mode_allowed"] and roi_report["measurement_mode_allowed"]
            report = {
                "schema_version": SCHEMA_VERSION,
                "generated_at": generated,
                "run_dir": str(run_dir),
                "mode_decision": "measurement_mode" if allowed else "preflight_mode",
                "measurement_mode_allowed": allowed,
                "terminal_closeout_present": False,
                "closeout_state": "preflight_ready" if allowed else "preflight_blocked",
                "task_pack_gate": task_report,
                "roster_gate": roster_report,
                "roi_governor": roi_report,
                "next_action": "enter measurement mode with required controls" if allowed else "finish preflight evidence; do not run measurement mode or claim swarm_lift",
            }
        write_readiness_packet(run_dir, generated, report)
    return report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    parser.add_argument("--run-dir", type=Path, default=None)
    parser.add_argument("--write-readiness-packet", action="store_true")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--strict-exit", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    repo_root = args.repo_root.resolve()
    run_dir = args.run_dir or DEFAULT_OUTPUT_ROOT / default_run_id()
    if not run_dir.is_absolute():
        run_dir = repo_root / run_dir
    report = run_preflight(
        run_dir=run_dir,
        repo_root=repo_root,
        write_packet=args.write_readiness_packet,
    )
    text = json.dumps(report, sort_keys=True) if args.json else json.dumps(report, indent=2, sort_keys=True)
    print(text)
    if args.strict_exit and not report["measurement_mode_allowed"]:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
