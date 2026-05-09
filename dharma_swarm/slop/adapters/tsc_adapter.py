"""tsc adapter — TypeScript compiler type-drift detection.

Runs `tsc --noEmit --pretty false` at each tsconfig.json-rooted project
and parses the diagnostic lines into TYPE_DRIFT findings. tsc's output
is line-based, not JSON, so we parse with a stable regex.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from pathlib import Path

from dharma_swarm.slop.adapters._js_helpers import (
    filter_js_ts_paths,
    find_ts_projects,
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

TOOL = "tsc"
FAMILY = DetectorFamily.TYPE_DRIFT

_DIAG_RE = re.compile(
    r"^(?P<path>[^()]+)\((?P<line>\d+),(?P<col>\d+)\):\s+"
    r"(?P<level>error|warning)\s+(?P<code>TS\d+):\s*(?P<msg>.+)$"
)


def _severity_for(level: str, code: str) -> Severity:
    if level == "error":
        if code in {"TS2322", "TS2345", "TS2531", "TS2532", "TS2538", "TS2741"}:
            return Severity.HIGH
        return Severity.MEDIUM
    return Severity.LOW


def _confidence_for(level: str) -> float:
    return 0.85 if level == "error" else 0.55


def _parse_tsc_output(text: str, project_root: Path, repo_root: Path) -> list[Finding]:
    findings: list[Finding] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        match = _DIAG_RE.match(line)
        if not match:
            continue
        rel = match.group("path")
        full = (project_root / rel).resolve() if not Path(rel).is_absolute() else Path(rel)
        level = match.group("level").lower()
        code = match.group("code")
        severity = _severity_for(level, code)
        findings.append(
            Finding(
                tool=TOOL,
                family=FAMILY,
                issue_type=code,
                path=normalize_path(str(full), repo_root),
                line=int(match.group("line")),
                symbol=None,
                severity=severity,
                confidence=_confidence_for(level),
                evidence=match.group("msg"),
                suggested_action="Fix the type error or add an explicit type annotation; do not use 'any' to silence",
            )
        )
    return findings


def run_tsc(
    paths: Iterable[Path],
    *,
    repo_root: Path | None = None,
    timeout: float = 120.0,
) -> DetectorResult:
    repo_root = repo_root or Path.cwd()
    js_paths = filter_js_ts_paths(list(paths))
    if not js_paths:
        return empty_result(TOOL, FAMILY, "no JS/TS paths in scope")
    projects = find_ts_projects(js_paths, repo_root=repo_root)
    if not projects:
        return empty_result(TOOL, FAMILY, "no tsconfig.json-rooted project found")

    all_findings: list[Finding] = []
    total_duration = 0.0
    last_exit = 0
    last_error: str | None = None
    for project in projects:
        argv = ["npx", "--yes", "tsc", "--noEmit", "--pretty", "false"]
        exit_code, stdout, stderr, duration = run_subprocess(
            argv, cwd=project, timeout=timeout
        )
        total_duration += duration
        last_exit = exit_code
        if exit_code == 127:
            return empty_result(
                TOOL, FAMILY, stderr or "npx/tsc not installed", total_duration
            )
        all_findings.extend(_parse_tsc_output(stdout, project, repo_root))
        all_findings.extend(_parse_tsc_output(stderr, project, repo_root))
        if exit_code not in (0, 1, 2):
            last_error = stderr.strip() or stdout.strip()
    return DetectorResult(
        tool=TOOL,
        family=FAMILY,
        findings=all_findings,
        duration_sec=total_duration,
        exit_code=last_exit if last_exit in (0, 1, 2) else last_exit,
        error=last_error,
    )


__all__ = ["FAMILY", "TOOL", "run_tsc"]
