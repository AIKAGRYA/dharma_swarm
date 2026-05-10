"""dependency-cruiser adapter — architecture boundary violations for JS/TS."""

from __future__ import annotations

import json
from collections.abc import Iterable
from pathlib import Path

from dharma_swarm.slop.adapters._js_helpers import (
    filter_js_ts_paths,
    find_js_projects,
)
from dharma_swarm.slop.adapters.base import (
    empty_result,
    normalize_path,
    run_subprocess,
)
from dharma_swarm.slop.models import (
    DetectorFamily,
    DetectorResult,
    Finding,
    Severity,
)

TOOL = "dependency-cruiser"
FAMILY = DetectorFamily.BOUNDARY


def _severity_for(violation: dict) -> Severity:
    level = str(violation.get("severity") or "warn").lower()
    return {
        "error": Severity.HIGH,
        "warn": Severity.MEDIUM,
        "info": Severity.LOW,
    }.get(level, Severity.MEDIUM)


def _parse_depcruise_json(payload: str, project_root: Path, repo_root: Path) -> list[Finding]:
    try:
        data = json.loads(payload)
    except json.JSONDecodeError:
        return []
    if not isinstance(data, dict):
        return []
    summary = data.get("summary") or {}
    violations = summary.get("violations") if isinstance(summary, dict) else None
    if not isinstance(violations, list):
        violations = data.get("violations") or []
    findings: list[Finding] = []
    for v in violations:
        if not isinstance(v, dict):
            continue
        from_path = v.get("from") or v.get("source")
        to_path = v.get("to") or v.get("target") or ""
        if not from_path:
            continue
        full = (project_root / from_path).resolve() if not Path(from_path).is_absolute() else Path(from_path)
        rule = v.get("rule") or {}
        rule_name = rule.get("name") if isinstance(rule, dict) else None
        rule_severity = rule.get("severity") if isinstance(rule, dict) else None
        severity = _severity_for(
            {"severity": rule_severity} if rule_severity else v
        )
        comment = rule.get("comment") if isinstance(rule, dict) else None
        findings.append(
            Finding(
                tool=TOOL,
                family=FAMILY,
                issue_type=str(rule_name or "boundary_violation"),
                path=normalize_path(str(full), repo_root),
                line=None,
                symbol=None,
                severity=severity,
                confidence=0.85 if severity is Severity.HIGH else 0.65,
                evidence=f"{from_path} → {to_path} violates rule '{rule_name}'"
                + (f": {comment}" if comment else ""),
                suggested_action="Resolve cycle or remove the cross-boundary import; route through the proper interface",
            )
        )
    return findings


def run_dependency_cruiser(
    paths: Iterable[Path],
    *,
    repo_root: Path | None = None,
    timeout: float = 90.0,
) -> DetectorResult:
    repo_root = repo_root or Path.cwd()
    js_paths = filter_js_ts_paths(list(paths))
    if not js_paths:
        return empty_result(TOOL, FAMILY, "no JS/TS paths in scope")
    projects = find_js_projects(js_paths, repo_root=repo_root)
    if not projects:
        return empty_result(TOOL, FAMILY, "no package.json-rooted project found")

    all_findings: list[Finding] = []
    total_duration = 0.0
    last_exit = 0
    last_error: str | None = None
    for project in projects:
        argv = [
            "npx", "--yes", "dependency-cruiser",
            "--output-type", "json",
            "--exclude", "node_modules|dist|build|.next",
            "src",
        ]
        exit_code, stdout, stderr, duration = run_subprocess(
            argv, cwd=project, timeout=timeout
        )
        total_duration += duration
        last_exit = exit_code
        if exit_code == 127:
            return empty_result(
                TOOL, FAMILY, stderr or "npx/dependency-cruiser not installed",
                total_duration,
            )
        if exit_code not in (0, 1):
            last_error = stderr.strip()
        if stdout.strip():
            all_findings.extend(_parse_depcruise_json(stdout, project, repo_root))
    return DetectorResult(
        tool=TOOL,
        family=FAMILY,
        findings=all_findings,
        duration_sec=total_duration,
        exit_code=last_exit if last_exit in (0, 1) else last_exit,
        error=last_error,
    )


__all__ = ["FAMILY", "TOOL", "run_dependency_cruiser"]
