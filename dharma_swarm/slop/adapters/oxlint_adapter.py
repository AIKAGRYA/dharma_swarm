"""oxlint adapter — Rust-native, 50-100x faster than ESLint, pre-commit-ready.

Drop-in alternative to ESLint for the pre-commit lane. Same JSON
diagnostic shape (mostly), much faster, no Node.js startup overhead
on cold paths.
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

TOOL = "oxlint"
FAMILY = DetectorFamily.AI_SLOP


def _severity_for(label: str) -> Severity:
    label = (label or "").lower()
    if label in {"error"}:
        return Severity.HIGH
    if label in {"warning", "warn"}:
        return Severity.MEDIUM
    return Severity.LOW


def _parse_oxlint_json(payload: str, repo_root: Path) -> list[Finding]:
    try:
        data = json.loads(payload)
    except json.JSONDecodeError:
        return []
    diagnostics = []
    if isinstance(data, dict):
        diagnostics = data.get("diagnostics") or data.get("items") or []
    elif isinstance(data, list):
        diagnostics = data
    findings: list[Finding] = []
    for diag in diagnostics:
        if not isinstance(diag, dict):
            continue
        file_path = diag.get("filename") or diag.get("file") or diag.get("source_id")
        if not file_path:
            continue
        line = None
        column = None
        labels = diag.get("labels") or []
        if labels and isinstance(labels[0], dict):
            line = labels[0].get("line")
            column = labels[0].get("column")
        elif "line" in diag:
            line = diag.get("line")
            column = diag.get("column")
        severity = _severity_for(str(diag.get("severity") or diag.get("level") or "warn"))
        rule = diag.get("code") or diag.get("rule") or diag.get("id") or "oxlint_issue"
        findings.append(
            Finding(
                tool=TOOL,
                family=FAMILY,
                issue_type=str(rule),
                path=normalize_path(str(file_path), repo_root),
                line=int(line) if isinstance(line, int) else None,
                symbol=None,
                severity=severity,
                confidence=0.75 if severity is Severity.HIGH else 0.55,
                evidence=str(diag.get("message") or diag.get("title") or ""),
                suggested_action=str(diag.get("help") or diag.get("note") or ""),
            )
        )
    return findings


def run_oxlint(
    paths: Iterable[Path],
    *,
    repo_root: Path | None = None,
    timeout: float = 30.0,
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
        files_in_project = [
            str(p) for p in js_paths
            if str(p.resolve()).startswith(str(project))
        ] or [str(project)]
        argv = ["npx", "--yes", "oxlint", "--format", "json", *files_in_project]
        exit_code, stdout, stderr, duration = run_subprocess(
            argv, cwd=project, timeout=timeout
        )
        total_duration += duration
        last_exit = exit_code
        if exit_code == 127:
            return empty_result(
                TOOL, FAMILY, stderr or "npx/oxlint not installed", total_duration
            )
        if stdout.strip():
            all_findings.extend(_parse_oxlint_json(stdout, repo_root))
        if exit_code not in (0, 1, 2):
            last_error = stderr.strip()
    return DetectorResult(
        tool=TOOL,
        family=FAMILY,
        findings=all_findings,
        duration_sec=total_duration,
        exit_code=last_exit if last_exit in (0, 1, 2) else last_exit,
        error=last_error,
    )


__all__ = ["FAMILY", "TOOL", "run_oxlint"]
