"""eslint adapter — JS/TS lint findings, AI-slop-relevant rules surfaced.

Routes rule IDs into DetectorFamily by category. Rules tagged with
'security' go to SECURITY; broad-catch / no-empty / no-unused-vars-style
go to AI_SLOP; complexity-related rules (cyclomatic, max-depth) go to
COMPLEXITY. Everything else defaults to AI_SLOP since most ESLint
findings on AI-shipped code surface slop fingerprints.
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

TOOL = "eslint"
PRIMARY_FAMILY = DetectorFamily.AI_SLOP

_SECURITY_RULE_PREFIXES = ("security/", "no-eval", "no-implied-eval", "no-script-url")
_COMPLEXITY_RULE_NAMES = frozenset(
    {
        "complexity",
        "max-depth",
        "max-lines",
        "max-lines-per-function",
        "max-nested-callbacks",
        "max-params",
        "max-statements",
    }
)
_DEAD_CODE_RULES = frozenset(
    {
        "no-unreachable",
        "no-unused-expressions",
        "no-unused-vars",
        "@typescript-eslint/no-unused-vars",
        "no-empty",
        "no-empty-function",
        "@typescript-eslint/no-empty-function",
    }
)
_AI_SLOP_RULES = frozenset(
    {
        "no-empty-pattern",
        "no-useless-catch",
        "no-useless-return",
        "no-useless-concat",
        "no-implicit-coercion",
        "@typescript-eslint/no-explicit-any",
        "@typescript-eslint/no-non-null-assertion",
        "@typescript-eslint/ban-ts-comment",
    }
)


def _family_for_rule(rule_id: str | None) -> DetectorFamily:
    if not rule_id:
        return PRIMARY_FAMILY
    rid = rule_id.lower()
    if any(rid.startswith(p) for p in _SECURITY_RULE_PREFIXES):
        return DetectorFamily.SECURITY
    if rule_id in _COMPLEXITY_RULE_NAMES:
        return DetectorFamily.COMPLEXITY
    if rule_id in _DEAD_CODE_RULES:
        return DetectorFamily.DEAD_CODE
    return PRIMARY_FAMILY


def _severity_for(level: int) -> Severity:
    return {2: Severity.HIGH, 1: Severity.MEDIUM}.get(level, Severity.LOW)


def _confidence_for(rule_id: str | None, level: int) -> float:
    if rule_id in _AI_SLOP_RULES:
        return 0.80
    if rule_id in _DEAD_CODE_RULES:
        return 0.75
    if level == 2:
        return 0.70
    return 0.50


def _parse_eslint_json(payload: str, repo_root: Path) -> list[Finding]:
    try:
        data = json.loads(payload)
    except json.JSONDecodeError:
        return []
    if not isinstance(data, list):
        return []
    findings: list[Finding] = []
    for file_report in data:
        if not isinstance(file_report, dict):
            continue
        file_path = file_report.get("filePath") or ""
        if not file_path:
            continue
        for msg in file_report.get("messages") or []:
            if not isinstance(msg, dict):
                continue
            rule_id = msg.get("ruleId")
            severity_int = msg.get("severity") if isinstance(msg.get("severity"), int) else 1
            severity = _severity_for(severity_int)
            family = _family_for_rule(rule_id if isinstance(rule_id, str) else None)
            findings.append(
                Finding(
                    tool=TOOL,
                    family=family,
                    issue_type=str(rule_id or "eslint_issue"),
                    path=normalize_path(file_path, repo_root),
                    line=msg.get("line") if isinstance(msg.get("line"), int) else None,
                    symbol=None,
                    severity=severity,
                    confidence=_confidence_for(
                        rule_id if isinstance(rule_id, str) else None, severity_int
                    ),
                    evidence=str(msg.get("message") or ""),
                    suggested_action=str(msg.get("fix", {}).get("text") or "") if isinstance(msg.get("fix"), dict) else "",
                )
            )
    return findings


def run_eslint(
    paths: Iterable[Path],
    *,
    repo_root: Path | None = None,
    timeout: float = 90.0,
) -> DetectorResult:
    repo_root = repo_root or Path.cwd()
    js_paths = filter_js_ts_paths(list(paths))
    if not js_paths:
        return empty_result(TOOL, PRIMARY_FAMILY, "no JS/TS paths in scope")
    projects = find_js_projects(js_paths, repo_root=repo_root)
    if not projects:
        return empty_result(TOOL, PRIMARY_FAMILY, "no package.json-rooted project found")

    all_findings: list[Finding] = []
    total_duration = 0.0
    last_exit = 0
    last_error: str | None = None
    for project in projects:
        files_in_project = [
            str(p) for p in js_paths
            if str(p.resolve()).startswith(str(project))
        ] or ["."]
        local_eslint = project / "node_modules" / ".bin" / "eslint"
        if local_eslint.is_file():
            argv = [str(local_eslint), "--format", "json", *files_in_project]
        elif (project / "node_modules").is_dir():
            argv = ["npx", "--no-install", "eslint", "--format", "json", *files_in_project]
        else:
            last_error = (
                f"node_modules not installed in {project.name}; run `npm install` "
                f"to enable eslint scanning"
            )
            continue
        exit_code, stdout, stderr, duration = run_subprocess(
            argv, cwd=project, timeout=timeout
        )
        total_duration += duration
        last_exit = exit_code
        if exit_code == 127:
            return empty_result(
                TOOL, PRIMARY_FAMILY, stderr or "npx/eslint not installed", total_duration
            )
        if stdout.strip():
            all_findings.extend(_parse_eslint_json(stdout, repo_root))
        if exit_code not in (0, 1, 2):
            last_error = stderr.strip()
    return DetectorResult(
        tool=TOOL,
        family=PRIMARY_FAMILY,
        findings=all_findings,
        duration_sec=total_duration,
        exit_code=last_exit if last_exit in (0, 1, 2) else last_exit,
        error=last_error,
    )


__all__ = ["PRIMARY_FAMILY", "TOOL", "run_eslint"]
