"""Vulture adapter — dead code detection."""

from __future__ import annotations

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

TOOL = "vulture"
FAMILY = DetectorFamily.DEAD_CODE


def _severity_from_confidence(pct: int) -> Severity:
    if pct >= 90:
        return Severity.HIGH
    if pct >= 70:
        return Severity.MEDIUM
    if pct >= 50:
        return Severity.LOW
    return Severity.INFO


def _parse_vulture_line(line: str, repo_root: Path) -> Finding | None:
    if ":" not in line or "unused" not in line.lower():
        return None
    try:
        path_line, rest = line.split(": unused ", 1)
        path, lineno_str = path_line.rsplit(":", 1)
        lineno = int(lineno_str)
    except ValueError:
        return None
    parts = rest.split(" ", 1)
    kind = parts[0]
    symbol = None
    pct = 60
    if len(parts) > 1:
        tail = parts[1]
        if "'" in tail:
            try:
                symbol = tail.split("'")[1]
            except IndexError:
                pass
        if "(" in tail and "%" in tail:
            try:
                pct = int(tail.rsplit("(", 1)[-1].split("%", 1)[0])
            except ValueError:
                pct = 60
    return Finding(
        tool=TOOL,
        family=FAMILY,
        issue_type=f"unused_{kind}",
        path=normalize_path(path, repo_root),
        line=lineno,
        symbol=symbol,
        severity=_severity_from_confidence(pct),
        confidence=pct / 100.0,
        evidence=line.strip(),
        suggested_action=f"Remove unused {kind} '{symbol}' or mark as intentional with #vulture: ignore",
    )


def run_vulture(
    paths: Iterable[Path],
    *,
    repo_root: Path | None = None,
    min_confidence: int = 60,
    timeout: float = 60.0,
) -> DetectorResult:
    repo_root = repo_root or Path.cwd()
    target_paths = [str(p) for p in paths]
    if not target_paths:
        return empty_result(TOOL, FAMILY, "no paths supplied")
    argv = [
        "vulture",
        f"--min-confidence={min_confidence}",
        *target_paths,
    ]
    exit_code, stdout, stderr, duration = run_subprocess(
        argv, cwd=repo_root, timeout=timeout
    )
    if exit_code == 127:
        return empty_result(TOOL, FAMILY, stderr or "vulture not installed", duration)
    findings: list[Finding] = []
    for line in stdout.splitlines():
        f = _parse_vulture_line(line, repo_root)
        if f is not None:
            findings.append(f)
    error = stderr.strip() if exit_code not in (0, 3) else None
    return DetectorResult(
        tool=TOOL,
        family=FAMILY,
        findings=findings,
        duration_sec=duration,
        exit_code=exit_code if exit_code != 3 else 0,
        error=error,
    )
