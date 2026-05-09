"""jscpd adapter — cross-language code duplication detection.

Polyglot — handles Python, TS/JS, Java, etc. Runs at scope root and
emits per-clone findings. Each duplicate clone produces two findings
(one per occurrence) so both sites are blamed.
"""

from __future__ import annotations

import json
import tempfile
from collections.abc import Iterable
from pathlib import Path

from dharma_swarm.slop.adapters._js_helpers import EXCLUDE_DIRS
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

TOOL = "jscpd"
FAMILY = DetectorFamily.DUPLICATION


def _scope_root(paths: list[Path], repo_root: Path) -> Path:
    if not paths:
        return repo_root
    if len(paths) == 1:
        p = paths[0]
        return p if p.is_dir() else (p.parent if p.parent.is_dir() else repo_root)
    parts_list = [list(p.resolve().parts) for p in paths]
    common: list[str] = []
    for column in zip(*parts_list, strict=False):
        if len(set(column)) == 1:
            common.append(column[0])
        else:
            break
    if not common:
        return repo_root
    return Path(*common)


def _parse_jscpd_json(payload: str, repo_root: Path) -> list[Finding]:
    try:
        data = json.loads(payload)
    except json.JSONDecodeError:
        return []
    if not isinstance(data, dict):
        return []
    duplicates = data.get("duplicates") or []
    if not isinstance(duplicates, list):
        return []
    findings: list[Finding] = []
    for clone in duplicates:
        if not isinstance(clone, dict):
            continue
        firstFile = clone.get("firstFile") or {}
        secondFile = clone.get("secondFile") or {}
        lines = clone.get("lines") or 0
        format_lang = str(clone.get("format") or "")
        confidence = min(0.95, 0.40 + (lines / 200.0))
        severity = Severity.HIGH if lines >= 50 else Severity.MEDIUM if lines >= 20 else Severity.LOW
        for site in (firstFile, secondFile):
            if not isinstance(site, dict):
                continue
            site_path = site.get("name") or site.get("file") or ""
            if not site_path:
                continue
            start = site.get("start") or {}
            line_no = start.get("line") if isinstance(start, dict) else None
            if not isinstance(line_no, int):
                line_no = None
            findings.append(
                Finding(
                    tool=TOOL,
                    family=FAMILY,
                    issue_type=f"duplicate_block_{format_lang or 'mixed'}",
                    path=normalize_path(str(site_path), repo_root),
                    line=line_no,
                    symbol=None,
                    severity=severity,
                    confidence=confidence,
                    evidence=f"{lines}-line duplicate; counterpart at {firstFile.get('name') if site is secondFile else secondFile.get('name')}",
                    suggested_action="Extract shared code into a function/module; replace duplicates with single import",
                )
            )
    return findings


def run_jscpd(
    paths: Iterable[Path],
    *,
    repo_root: Path | None = None,
    min_lines: int = 8,
    min_tokens: int = 50,
    timeout: float = 120.0,
) -> DetectorResult:
    repo_root = repo_root or Path.cwd()
    paths_list = [
        p if p.is_absolute() else (repo_root / p).resolve()
        for p in paths
    ]
    if not paths_list:
        return empty_result(TOOL, FAMILY, "no paths supplied")
    scope = _scope_root(paths_list, repo_root)
    ignore_globs = [f"**/{d}/**" for d in EXCLUDE_DIRS]
    with tempfile.TemporaryDirectory(prefix="jscpd-") as tmpdir:
        argv = [
            "npx", "--yes", "jscpd",
            "--silent",
            "--reporters", "json",
            "--output", str(tmpdir),
            "--min-lines", str(min_lines),
            "--min-tokens", str(min_tokens),
            "--ignore", ",".join(ignore_globs),
            str(scope),
        ]
        exit_code, _, stderr, duration = run_subprocess(
            argv, cwd=repo_root, timeout=timeout
        )
        if exit_code == 127:
            return empty_result(
                TOOL, FAMILY, stderr or "npx not installed", duration
            )
        report_path = Path(tmpdir) / "jscpd-report.json"
        if not report_path.exists():
            return DetectorResult(
                tool=TOOL,
                family=FAMILY,
                findings=[],
                duration_sec=duration,
                exit_code=exit_code if exit_code in (0, 1) else exit_code,
                error=stderr.strip() if exit_code > 1 else None,
            )
        try:
            payload = report_path.read_text(encoding="utf-8")
        except OSError as exc:
            return DetectorResult(
                tool=TOOL, family=FAMILY, findings=[], duration_sec=duration,
                exit_code=1, error=f"jscpd report unreadable: {exc}",
            )
        findings = _parse_jscpd_json(payload, repo_root)
    return DetectorResult(
        tool=TOOL,
        family=FAMILY,
        findings=findings,
        duration_sec=duration,
        exit_code=exit_code if exit_code in (0, 1) else exit_code,
        error=stderr.strip() if exit_code > 1 else None,
    )


__all__ = ["FAMILY", "TOOL", "run_jscpd"]
