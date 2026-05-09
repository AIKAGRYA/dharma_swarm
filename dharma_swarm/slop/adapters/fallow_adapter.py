"""Fallow adapter — JS/TS codebase intelligence (THE benchmark tool).

Wraps the real `fallow` CLI (fallow-rs/fallow). Runs `fallow dead-code
--format json` at each package.json-rooted project in scope. Fallow's
output is a single top-level dict where each issue category is its own
key (unused_files, unused_exports, circular_dependencies,
boundary_violations, etc.). The adapter routes each category into the
appropriate DetectorFamily, so a single Fallow run produces multi-family
findings.
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


_CATEGORY_SPECS: list[tuple[str, str, DetectorFamily, Severity, float, str]] = [
    ("unused_files", "unused_file", DetectorFamily.DEAD_CODE, Severity.HIGH, 0.85,
     "Delete the file or wire it into an entry point"),
    ("unused_exports", "unused_export", DetectorFamily.DEAD_CODE, Severity.MEDIUM, 0.75,
     "Stop exporting or remove the unused symbol"),
    ("unused_types", "unused_type", DetectorFamily.DEAD_CODE, Severity.MEDIUM, 0.70,
     "Remove unused type export"),
    ("unused_class_members", "unused_class_member", DetectorFamily.DEAD_CODE, Severity.LOW, 0.60,
     "Remove unused class member"),
    ("unused_enum_members", "unused_enum_member", DetectorFamily.DEAD_CODE, Severity.LOW, 0.55,
     "Remove unused enum member"),
    ("unused_dependencies", "unused_dependency", DetectorFamily.DEAD_CODE, Severity.HIGH, 0.85,
     "Remove unused dependency from package.json"),
    ("unused_dev_dependencies", "unused_dev_dependency", DetectorFamily.DEAD_CODE, Severity.MEDIUM, 0.70,
     "Remove unused devDependency"),
    ("unused_optional_dependencies", "unused_optional_dependency", DetectorFamily.DEAD_CODE, Severity.LOW, 0.55,
     "Review optional dependency usage"),
    ("unresolved_imports", "unresolved_import", DetectorFamily.STRUCTURE, Severity.HIGH, 0.85,
     "Resolve the missing import or remove the dead reference"),
    ("unlisted_dependencies", "unlisted_dependency", DetectorFamily.STRUCTURE, Severity.MEDIUM, 0.75,
     "Add the dependency to package.json or remove the import"),
    ("duplicate_exports", "duplicate_export", DetectorFamily.DUPLICATION, Severity.LOW, 0.60,
     "Resolve duplicate export"),
    ("circular_dependencies", "circular_dependency", DetectorFamily.STRUCTURE, Severity.HIGH, 0.85,
     "Break the cycle (lazy import, refactor, or extract shared module)"),
    ("boundary_violations", "boundary_violation", DetectorFamily.BOUNDARY, Severity.HIGH, 0.85,
     "Honor architecture boundaries; route through proper interface"),
    ("private_type_leaks", "private_type_leak", DetectorFamily.BOUNDARY, Severity.MEDIUM, 0.65,
     "Stop exposing private type through public API"),
    ("type_only_dependencies", "type_only_dependency", DetectorFamily.DEAD_CODE, Severity.INFO, 0.30,
     "Move dependency to devDependencies (type-only at runtime)"),
    ("test_only_dependencies", "test_only_dependency", DetectorFamily.DEAD_CODE, Severity.INFO, 0.30,
     "Move dependency to devDependencies (test-only)"),
]


def _extract_path_and_line(item: dict) -> tuple[str | None, int | None, str | None]:
    if isinstance(item, str):
        return item, None, None
    if not isinstance(item, dict):
        return None, None, None
    path = item.get("path") or item.get("file") or item.get("filename")
    line_raw = item.get("line") or item.get("line_number") or item.get("lineno")
    line = int(line_raw) if isinstance(line_raw, int) else None
    symbol = item.get("name") or item.get("symbol") or item.get("export")
    if not path:
        return None, line, symbol if isinstance(symbol, str) else None
    return str(path), line, symbol if isinstance(symbol, str) else None


def _parse_fallow_json(payload: str, project_root: Path, repo_root: Path) -> list[Finding]:
    try:
        data = json.loads(payload)
    except json.JSONDecodeError:
        return []
    if not isinstance(data, dict):
        return []
    findings: list[Finding] = []
    for category, issue_type, family, severity, confidence, suggestion in _CATEGORY_SPECS:
        items = data.get(category)
        if not isinstance(items, list):
            continue
        for item in items:
            raw_path, line, symbol = _extract_path_and_line(item)
            if not raw_path:
                if isinstance(item, dict) and category in {"unused_dependencies", "unused_dev_dependencies", "unused_optional_dependencies"}:
                    raw_path = "package.json"
                    symbol = item.get("name") or item.get("dependency") or symbol
                else:
                    continue
            full = (project_root / raw_path).resolve() if not Path(raw_path).is_absolute() else Path(raw_path)
            evidence = (
                f"fallow {category}: {symbol}" if symbol else f"fallow {category}"
            )
            findings.append(
                Finding(
                    tool=TOOL,
                    family=family,
                    issue_type=issue_type,
                    path=normalize_path(str(full), repo_root),
                    line=line,
                    symbol=symbol,
                    severity=severity,
                    confidence=confidence,
                    evidence=evidence,
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
        argv = ["fallow", "dead-code", "--format", "json", "--quiet"]
        exit_code, stdout, stderr, duration = run_subprocess(
            argv, cwd=project, timeout=timeout
        )
        total_duration += duration
        last_exit = exit_code
        if exit_code == 127:
            return empty_result(
                TOOL,
                PRIMARY_FAMILY,
                stderr or "fallow not installed (npm i -g fallow OR cargo install fallow)",
                total_duration,
            )
        if stderr.strip() and exit_code not in (0, 1):
            last_error = stderr.strip()
        if stdout.strip():
            all_findings.extend(_parse_fallow_json(stdout, project, repo_root))
    return DetectorResult(
        tool=TOOL,
        family=PRIMARY_FAMILY,
        findings=all_findings,
        duration_sec=total_duration,
        exit_code=last_exit if last_exit in (0, 1, 2) else last_exit,
        error=last_error,
    )


__all__ = ["PRIMARY_FAMILY", "TOOL", "run_fallow"]
