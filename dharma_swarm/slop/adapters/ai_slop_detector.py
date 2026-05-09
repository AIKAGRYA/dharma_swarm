"""ai-slop-detector adapter — AI-generated code slop signatures.

Wraps the ai-slop-detector PyPI package. Falls back gracefully if not
installed.
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from pathlib import Path

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

TOOL = "ai-slop-detector"
FAMILY = DetectorFamily.AI_SLOP

_SEVERITY_MAP = {
    "critical": Severity.CRITICAL,
    "high": Severity.HIGH,
    "medium": Severity.MEDIUM,
    "low": Severity.LOW,
    "info": Severity.INFO,
}


def _parse_json_findings(payload: str, repo_root: Path) -> list[Finding]:
    try:
        data = json.loads(payload)
    except json.JSONDecodeError:
        return []
    if isinstance(data, dict):
        items = data.get("findings") or data.get("issues") or data.get("results") or []
    elif isinstance(data, list):
        items = data
    else:
        return []
    findings: list[Finding] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        path = item.get("path") or item.get("file") or item.get("filename") or ""
        if not path:
            continue
        line_raw = item.get("line") or item.get("line_number") or item.get("lineno")
        line = int(line_raw) if isinstance(line_raw, (int, str)) and str(line_raw).isdigit() else None
        sev_raw = str(item.get("severity") or "medium").lower()
        severity = _SEVERITY_MAP.get(sev_raw, Severity.MEDIUM)
        confidence_raw = item.get("confidence")
        if isinstance(confidence_raw, (int, float)):
            confidence = float(confidence_raw)
            if confidence > 1.0:
                confidence /= 100.0
        else:
            confidence = {
                Severity.CRITICAL: 0.95,
                Severity.HIGH: 0.85,
                Severity.MEDIUM: 0.65,
                Severity.LOW: 0.45,
                Severity.INFO: 0.25,
            }[severity]
        confidence = max(0.0, min(1.0, confidence))
        issue_type = str(
            item.get("rule")
            or item.get("rule_id")
            or item.get("category")
            or item.get("type")
            or "ai_slop"
        )
        symbol = item.get("symbol") or item.get("function") or item.get("class")
        evidence = str(
            item.get("message") or item.get("description") or item.get("snippet") or ""
        )
        suggestion = str(item.get("suggestion") or item.get("suggested_action") or "")
        findings.append(
            Finding(
                tool=TOOL,
                family=FAMILY,
                issue_type=issue_type,
                path=normalize_path(path, repo_root),
                line=line,
                symbol=symbol,
                severity=severity,
                confidence=confidence,
                evidence=evidence,
                suggested_action=suggestion,
            )
        )
    return findings


def run_ai_slop_detector(
    paths: Iterable[Path],
    *,
    repo_root: Path | None = None,
    timeout: float = 90.0,
) -> DetectorResult:
    repo_root = repo_root or Path.cwd()
    target_paths = [str(p) for p in paths]
    if not target_paths:
        return empty_result(TOOL, FAMILY, "no paths supplied")
    findings: list[Finding] = []
    duration = 0.0
    last_stderr = ""
    last_exit = 0
    for path in target_paths:
        argv = ["ai-slop-detector", "--json", path]
        exit_code, stdout, stderr, d = run_subprocess(
            argv, cwd=repo_root, timeout=timeout
        )
        duration += d
        last_stderr = stderr
        last_exit = exit_code
        if exit_code == 127:
            return empty_result(
                TOOL, FAMILY, stderr or "ai-slop-detector not installed", duration
            )
        findings.extend(_parse_json_findings(stdout, repo_root))
    return DetectorResult(
        tool=TOOL,
        family=FAMILY,
        findings=findings,
        duration_sec=duration,
        exit_code=last_exit if last_exit in (0, 1) else last_exit,
        error=last_stderr.strip() if last_exit > 1 else None,
    )
