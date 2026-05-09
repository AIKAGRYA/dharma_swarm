"""Fallow adapter — JS/TS codebase intelligence (THE benchmark tool).

Fallow is Rust-native, sub-second, covers Fallow's namesake dimensions:
unused code, duplication, circular deps, complexity hotspots,
architecture boundaries. CRAP score combines complexity with test
coverage. Drop-in for the JS/TS surfaces (dashboard/, terminal/,
desktop-shell/, codex_skills/).

The adapter discovers package.json-rooted projects in scope, runs
Fallow at each root, emits findings tagged with the appropriate
DetectorFamily based on the issue type. Findings span multiple
families because Fallow is a multi-dimensional tool.
"""

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

TOOL = "fallow"
PRIMARY_FAMILY = DetectorFamily.STRUCTURE

_FAMILY_BY_KIND: dict[str, DetectorFamily] = {
    "dead": DetectorFamily.DEAD_CODE,
    "unused": DetectorFamily.DEAD_CODE,
    "duplication": DetectorFamily.DUPLICATION,
    "duplicate": DetectorFamily.DUPLICATION,
    "circular": DetectorFamily.STRUCTURE,
    "complexity": DetectorFamily.COMPLEXITY,
    "crap": DetectorFamily.COMPLEXITY,
    "architecture": DetectorFamily.BOUNDARY,
    "boundary": DetectorFamily.BOUNDARY,
}

_SEVERITY_BY_LABEL: dict[str, Severity] = {
    "critical": Severity.CRITICAL,
    "high": Severity.HIGH,
    "medium": Severity.MEDIUM,
    "low": Severity.LOW,
    "info": Severity.INFO,
    "warning": Severity.MEDIUM,
    "error": Severity.HIGH,
}


def _family_for_issue(issue: dict) -> DetectorFamily:
    raw = " ".join(
        str(issue.get(k, "")).lower()
        for k in ("kind", "category", "rule", "rule_id", "type")
    )
    for key, fam in _FAMILY_BY_KIND.items():
        if key in raw:
            return fam
    return PRIMARY_FAMILY


def _severity_for_issue(issue: dict) -> Severity:
    label = str(issue.get("severity") or issue.get("level") or "medium").lower()
    return _SEVERITY_BY_LABEL.get(label, Severity.MEDIUM)


def _confidence_for_issue(issue: dict, severity: Severity) -> float:
    raw = issue.get("confidence")
    if isinstance(raw, (int, float)):
        c = float(raw)
        if c > 1.0:
            c /= 100.0
        return max(0.0, min(1.0, c))
    return {
        Severity.CRITICAL: 0.90,
        Severity.HIGH: 0.78,
        Severity.MEDIUM: 0.62,
        Severity.LOW: 0.45,
        Severity.INFO: 0.25,
    }[severity]


def _parse_fallow_json(payload: str, repo_root: Path, project_root: Path) -> list[Finding]:
    try:
        data = json.loads(payload)
    except json.JSONDecodeError:
        return []
    if isinstance(data, dict):
        items = data.get("issues") or data.get("findings") or data.get("results") or []
    elif isinstance(data, list):
        items = data
    else:
        return []
    findings: list[Finding] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        rel_path = item.get("path") or item.get("file") or item.get("filename")
        if not rel_path:
            continue
        full = (project_root / rel_path).resolve() if not Path(rel_path).is_absolute() else Path(rel_path)
        family = _family_for_issue(item)
        severity = _severity_for_issue(item)
        confidence = _confidence_for_issue(item, severity)
        line = item.get("line") or item.get("line_number") or item.get("lineno")
        if isinstance(line, str) and line.isdigit():
            line = int(line)
        elif not isinstance(line, int):
            line = None
        symbol = item.get("symbol") or item.get("function") or item.get("name")
        issue_type = str(
            item.get("kind")
            or item.get("rule_id")
            or item.get("rule")
            or item.get("category")
            or "fallow_issue"
        )
        message = str(
            item.get("message") or item.get("description") or item.get("details") or ""
        )
        suggestion = str(item.get("suggestion") or item.get("fix") or "")
        findings.append(
            Finding(
                tool=TOOL,
                family=family,
                issue_type=issue_type,
                path=normalize_path(str(full), repo_root),
                line=line,
                symbol=symbol if isinstance(symbol, str) else None,
                severity=severity,
                confidence=confidence,
                evidence=message,
                suggested_action=suggestion,
            )
        )
    return findings


def run_fallow(
    paths: Iterable[Path],
    *,
    repo_root: Path | None = None,
    timeout: float = 60.0,
) -> DetectorResult:
    repo_root = repo_root or Path.cwd()
    js_paths = filter_js_ts_paths(list(paths))
    if not js_paths:
        return empty_result(TOOL, PRIMARY_FAMILY, "no JS/TS paths in scope")
    projects = find_js_projects(js_paths, repo_root=repo_root)
    if not projects:
        return empty_result(TOOL, PRIMARY_FAMILY, "no package.json-rooted JS/TS project found")

    all_findings: list[Finding] = []
    total_duration = 0.0
    last_error: str | None = None
    last_exit = 0
    for project in projects:
        argv = ["fallow", "scan", "--format", "json"]
        exit_code, stdout, stderr, duration = run_subprocess(
            argv, cwd=project, timeout=timeout
        )
        total_duration += duration
        last_exit = exit_code
        if exit_code == 127:
            return empty_result(
                TOOL,
                PRIMARY_FAMILY,
                stderr or "fallow not installed (cargo install fallow)",
                total_duration,
            )
        if stderr.strip():
            last_error = stderr.strip()
        all_findings.extend(_parse_fallow_json(stdout, repo_root, project))
    return DetectorResult(
        tool=TOOL,
        family=PRIMARY_FAMILY,
        findings=all_findings,
        duration_sec=total_duration,
        exit_code=last_exit if last_exit in (0, 1) else last_exit,
        error=last_error if last_exit > 1 else None,
    )


__all__ = ["PRIMARY_FAMILY", "TOOL", "run_fallow"]
