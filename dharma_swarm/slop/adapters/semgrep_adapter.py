"""semgrep adapter — pattern-based AI-slop / security / dead-handler detection.

Consumes the existing .semgrep/dharma-anti-slop.yml rules in the repo
plus a built-in pack of AI-slop signature patterns (broad-except,
silent-pass, useless-try, debug prints in production paths). Emits
findings tagged AI_SLOP or SECURITY based on rule metadata.

Closes SUBAGENT 6 (Error Handling Cleanup) by detecting broad-except
patterns statically without needing Spotlight envelopes.
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

TOOL = "semgrep"
PRIMARY_FAMILY = DetectorFamily.AI_SLOP

_BUILTIN_RULES = {
    "rules": [
        {
            "id": "ai-slop.broad-except-pass",
            "message": "Bare `except` (or `except Exception`) followed by `pass` swallows errors silently — classic AI fingerprint",
            "severity": "WARNING",
            "languages": ["python"],
            "metadata": {"family": "ai_slop", "category": "error_handling"},
            "patterns": [
                {"pattern-either": [
                    {"pattern": "try:\n  ...\nexcept:\n  pass"},
                    {"pattern": "try:\n  ...\nexcept Exception:\n  pass"},
                    {"pattern": "try:\n  ...\nexcept BaseException:\n  pass"},
                ]},
            ],
        },
        {
            "id": "ai-slop.broad-except-silent",
            "message": "Bare `except` with no logging hides failures — masks real problems per SUBAGENT 6 discipline",
            "severity": "WARNING",
            "languages": ["python"],
            "metadata": {"family": "ai_slop", "category": "error_handling"},
            "pattern-either": [
                {"pattern": "try:\n  ...\nexcept:\n  return $X"},
                {"pattern": "try:\n  ...\nexcept Exception:\n  return $X"},
                {"pattern": "try:\n  ...\nexcept Exception as $E:\n  return None"},
            ],
        },
        {
            "id": "ai-slop.useless-try",
            "message": "Try/except that just re-raises is dead ceremony",
            "severity": "INFO",
            "languages": ["python"],
            "metadata": {"family": "ai_slop", "category": "ceremonial"},
            "pattern": "try:\n  ...\nexcept $E:\n  raise",
        },
        {
            "id": "ai-slop.debug-print-in-prod",
            "message": "print() in non-CLI module — likely AI debug residue",
            "severity": "INFO",
            "languages": ["python"],
            "metadata": {"family": "ai_slop", "category": "debug_residue"},
            "patterns": [
                {"pattern": "print($X)"},
                {"pattern-not-inside": "if __name__ == '__main__':\n  ..."},
                {"pattern-not-inside": "def main(...):\n  ..."},
            ],
            "paths": {"exclude": ["scripts/**", "tests/**", "**/*_cli.py", "**/cli.py"]},
        },
    ]
}

_SEVERITY_MAP = {
    "ERROR": Severity.HIGH,
    "WARNING": Severity.MEDIUM,
    "INFO": Severity.LOW,
}


def _family_for(metadata: dict | None) -> DetectorFamily:
    if not isinstance(metadata, dict):
        return PRIMARY_FAMILY
    fam = str(metadata.get("family", "")).lower()
    return {
        "security": DetectorFamily.SECURITY,
        "ai_slop": DetectorFamily.AI_SLOP,
        "dead_code": DetectorFamily.DEAD_CODE,
        "complexity": DetectorFamily.COMPLEXITY,
        "boundary": DetectorFamily.BOUNDARY,
    }.get(fam, PRIMARY_FAMILY)


def _confidence_for(severity: Severity, category: str) -> float:
    base = {Severity.HIGH: 0.80, Severity.MEDIUM: 0.65, Severity.LOW: 0.45}[severity]
    if category in {"error_handling", "ceremonial"}:
        base += 0.05
    return min(0.92, base)


def _parse_semgrep_json(payload: str, repo_root: Path) -> list[Finding]:
    try:
        data = json.loads(payload)
    except json.JSONDecodeError:
        return []
    if not isinstance(data, dict):
        return []
    results = data.get("results") or []
    findings: list[Finding] = []
    for r in results:
        if not isinstance(r, dict):
            continue
        path = r.get("path")
        if not path:
            continue
        check_id = r.get("check_id") or "semgrep_issue"
        extra = r.get("extra") or {}
        severity_label = str(extra.get("severity") or r.get("severity") or "WARNING").upper()
        severity = _SEVERITY_MAP.get(severity_label, Severity.MEDIUM)
        metadata = extra.get("metadata") if isinstance(extra, dict) else None
        category = str((metadata or {}).get("category", "general"))
        family = _family_for(metadata)
        start = r.get("start") or {}
        line = start.get("line") if isinstance(start, dict) else None
        message = str(extra.get("message") or r.get("message") or check_id)
        findings.append(
            Finding(
                tool=TOOL,
                family=family,
                issue_type=str(check_id),
                path=normalize_path(path, repo_root),
                line=int(line) if isinstance(line, int) else None,
                symbol=None,
                severity=severity,
                confidence=_confidence_for(severity, category),
                evidence=message,
                suggested_action=str((metadata or {}).get("fix", "")),
            )
        )
    return findings


def _resolve_config_args(repo_root: Path, extra_configs: list[str] | None) -> list[str]:
    args: list[str] = []
    repo_config = repo_root / ".semgrep"
    if repo_config.is_dir():
        for cfg in sorted(repo_config.glob("*.yml")):
            args.extend(["--config", str(cfg)])
    for c in extra_configs or []:
        args.extend(["--config", c])
    return args


def run_semgrep(
    paths: Iterable[Path],
    *,
    repo_root: Path | None = None,
    extra_configs: list[str] | None = None,
    use_builtin: bool = True,
    timeout: float = 90.0,
) -> DetectorResult:
    repo_root = repo_root or Path.cwd()
    paths_list = [str(p) for p in paths]
    if not paths_list:
        return empty_result(TOOL, PRIMARY_FAMILY, "no paths supplied")

    config_args = _resolve_config_args(repo_root, extra_configs)
    builtin_path: Path | None = None
    if use_builtin:
        builtin_path = repo_root / ".dharma" / "slop_semgrep_builtin.yml"
        builtin_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            import yaml  # type: ignore
            builtin_path.write_text(
                yaml.safe_dump(_BUILTIN_RULES, sort_keys=False), encoding="utf-8"
            )
        except ImportError:
            builtin_path.write_text(json.dumps(_BUILTIN_RULES, indent=2), encoding="utf-8")
        config_args.extend(["--config", str(builtin_path)])

    if not config_args:
        return empty_result(
            TOOL, PRIMARY_FAMILY,
            "no semgrep config found (no .semgrep/*.yml and use_builtin=False)",
        )

    argv = [
        "semgrep",
        "scan",
        "--json",
        "--quiet",
        "--no-git-ignore",
        "--disable-version-check",
        *config_args,
        *paths_list,
    ]
    exit_code, stdout, stderr, duration = run_subprocess(
        argv, cwd=repo_root, timeout=timeout
    )
    if exit_code == 127:
        return empty_result(TOOL, PRIMARY_FAMILY, stderr or "semgrep not installed", duration)

    findings = _parse_semgrep_json(stdout, repo_root) if stdout.strip() else []

    return DetectorResult(
        tool=TOOL,
        family=PRIMARY_FAMILY,
        findings=findings,
        duration_sec=duration,
        exit_code=exit_code if exit_code in (0, 1, 2) else exit_code,
        error=stderr.strip() if exit_code > 2 else None,
    )


__all__ = ["PRIMARY_FAMILY", "TOOL", "run_semgrep"]
