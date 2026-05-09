"""knip adapter — dead exports / unused files / unused dependencies for TS/JS."""

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

TOOL = "knip"
FAMILY = DetectorFamily.DEAD_CODE


def _emit_section(
    section_key: str,
    items: list,
    project_root: Path,
    repo_root: Path,
    *,
    issue_type: str,
    confidence: float,
    severity: Severity,
    suggestion: str,
) -> list[Finding]:
    findings: list[Finding] = []
    for item in items:
        if isinstance(item, str):
            target = item
            symbol = None
            line = None
        elif isinstance(item, dict):
            target = item.get("file") or item.get("path") or item.get("name") or ""
            symbol = item.get("symbol") or item.get("name") or item.get("identifier")
            raw_line = item.get("line") or item.get("col")
            line = int(raw_line) if isinstance(raw_line, int) else None
        else:
            continue
        if not target:
            continue
        full = (project_root / target).resolve() if not Path(target).is_absolute() else Path(target)
        findings.append(
            Finding(
                tool=TOOL,
                family=FAMILY,
                issue_type=issue_type,
                path=normalize_path(str(full), repo_root),
                line=line,
                symbol=symbol if isinstance(symbol, str) else None,
                severity=severity,
                confidence=confidence,
                evidence=f"knip flagged {section_key}: {symbol or target}",
                suggested_action=suggestion,
            )
        )
    return findings


_SECTION_SPECS: list[tuple[str, str, float, Severity, str]] = [
    ("files", "unused_file", 0.80, Severity.HIGH, "Remove unused file or import it where intended"),
    ("dependencies", "unused_dependency", 0.85, Severity.HIGH, "Remove unused dep from package.json or wire it"),
    ("devDependencies", "unused_dev_dependency", 0.70, Severity.MEDIUM, "Remove unused devDependency"),
    ("optionalPeerDependencies", "unused_peer_dependency", 0.55, Severity.LOW, "Review peer dependency usage"),
    ("unlisted", "unlisted_dependency", 0.75, Severity.MEDIUM, "Add missing dep to package.json or remove import"),
    ("binaries", "unused_binary", 0.60, Severity.LOW, "Remove or wire unused binary"),
    ("exports", "unused_export", 0.70, Severity.MEDIUM, "Remove or stop exporting unused symbol"),
    ("types", "unused_type", 0.70, Severity.MEDIUM, "Remove unused type export"),
    ("nsExports", "unused_namespace_export", 0.60, Severity.LOW, "Remove unused namespace export"),
    ("nsTypes", "unused_namespace_type", 0.60, Severity.LOW, "Remove unused namespace type"),
    ("classMembers", "unused_class_member", 0.65, Severity.MEDIUM, "Remove or use unused class member"),
    ("enumMembers", "unused_enum_member", 0.60, Severity.LOW, "Remove unused enum member"),
    ("duplicates", "duplicate_export", 0.60, Severity.LOW, "Resolve duplicate export"),
]


def _parse_knip_json(payload: str, project_root: Path, repo_root: Path) -> list[Finding]:
    try:
        data = json.loads(payload)
    except json.JSONDecodeError:
        return []
    if not isinstance(data, dict):
        return []
    findings: list[Finding] = []
    for section_key, issue_type, confidence, severity, suggestion in _SECTION_SPECS:
        items = data.get(section_key) or []
        if isinstance(items, dict):
            flat = []
            for v in items.values():
                if isinstance(v, list):
                    flat.extend(v)
            items = flat
        if not isinstance(items, list):
            continue
        findings.extend(
            _emit_section(
                section_key,
                items,
                project_root,
                repo_root,
                issue_type=issue_type,
                confidence=confidence,
                severity=severity,
                suggestion=suggestion,
            )
        )
    return findings


def run_knip(
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
        return empty_result(TOOL, FAMILY, "no package.json-rooted JS/TS project found")

    all_findings: list[Finding] = []
    total_duration = 0.0
    last_exit = 0
    last_error: str | None = None
    for project in projects:
        argv = ["npx", "--yes", "knip", "--reporter", "json", "--no-exit-code"]
        exit_code, stdout, stderr, duration = run_subprocess(
            argv, cwd=project, timeout=timeout
        )
        total_duration += duration
        last_exit = exit_code
        if exit_code == 127:
            return empty_result(
                TOOL, FAMILY, stderr or "npx not installed", total_duration
            )
        if stderr.strip():
            last_error = stderr.strip()
        all_findings.extend(_parse_knip_json(stdout, project, repo_root))
    return DetectorResult(
        tool=TOOL,
        family=FAMILY,
        findings=all_findings,
        duration_sec=total_duration,
        exit_code=last_exit if last_exit in (0, 1, 2) else last_exit,
        error=last_error if last_exit > 2 else None,
    )


__all__ = ["FAMILY", "TOOL", "run_knip"]
