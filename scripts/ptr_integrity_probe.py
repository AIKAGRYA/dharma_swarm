#!/usr/bin/env python3
"""Out-of-band integrity probe for PTR.

This script may run expensive checks and write small JSON artifacts. The PTR
runtime scorer must only read those artifacts; it must not run this probe.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Write PTR integrity artifacts")
    parser.add_argument("--repo-root", type=Path, default=_default_repo_root())
    parser.add_argument("--state-dir", type=Path, default=Path.home() / ".dharma")
    parser.add_argument("--pytest-target", action="append", default=[])
    parser.add_argument("--skip-compileall", action="store_true")
    parser.add_argument("--include-governance-all", action="store_true")
    parser.add_argument("--json", action="store_true", help="Print artifact summary as JSON")
    args = parser.parse_args(argv)

    repo_root = args.repo_root.resolve()
    meta_dir = args.state_dir / "meta"

    repo_checks = [
        _check_git_status(repo_root),
    ]
    if not args.skip_compileall:
        repo_checks.append(
            _run_check(
                "compileall",
                [sys.executable, "-m", "compileall", "-q", "dharma_swarm", "scripts"],
                repo_root,
                timeout=180,
            )
        )
    if args.pytest_target:
        repo_checks.append(
            _run_check(
                "pytest",
                [sys.executable, "-m", "pytest", "-q", *args.pytest_target],
                repo_root,
                timeout=300,
            )
        )
    else:
        repo_checks.append(_skipped_check("pytest", "no --pytest-target supplied"))

    repo_artifact = _artifact("repo_integrity", repo_checks)
    repo_path = meta_dir / "repo_integrity.json"
    _write_json(repo_path, repo_artifact)

    if args.include_governance_all:
        governance_checks = [
            _run_check("governance-all", ["make", "governance-all"], repo_root, timeout=600)
        ]
    else:
        governance_checks = [
            _skipped_check(
                "governance-all",
                "not run; pass --include-governance-all for full governance probe",
            )
        ]
    governance_artifact = _artifact("governance_integrity", governance_checks)
    governance_path = meta_dir / "governance_integrity.json"
    _write_json(governance_path, governance_artifact)

    summary = {
        "repo_integrity": repo_artifact["score"],
        "governance_integrity": governance_artifact["score"],
        "repo_path": str(repo_path),
        "governance_path": str(governance_path),
    }
    if args.json:
        print(json.dumps(summary, indent=2))
    else:
        print(
            "PTR integrity artifacts written: "
            f"repo={repo_artifact['score']:.3f} "
            f"governance={governance_artifact['score']:.3f}"
        )

    return 1 if repo_artifact["hard_failures"] or governance_artifact["hard_failures"] else 0


def _default_repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _check_git_status(repo_root: Path) -> dict[str, Any]:
    result = _run_check("git-status", ["git", "status", "--short"], repo_root, timeout=30)
    if result["returncode"] == 0 and result["stdout"].strip():
        result["status"] = "warn"
        result["warning"] = "worktree has uncommitted changes"
    return result


def _run_check(
    name: str,
    cmd: list[str],
    cwd: Path,
    *,
    timeout: int,
) -> dict[str, Any]:
    try:
        completed = subprocess.run(
            cmd,
            cwd=cwd,
            text=True,
            capture_output=True,
            timeout=timeout,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {
            "name": name,
            "cmd": cmd,
            "status": "fail",
            "returncode": -1,
            "stdout": "",
            "stderr": str(exc),
        }

    return {
        "name": name,
        "cmd": cmd,
        "status": "pass" if completed.returncode == 0 else "fail",
        "returncode": completed.returncode,
        "stdout": completed.stdout[-4000:],
        "stderr": completed.stderr[-4000:],
    }


def _skipped_check(name: str, reason: str) -> dict[str, Any]:
    return {
        "name": name,
        "cmd": [],
        "status": "skipped",
        "returncode": None,
        "stdout": "",
        "stderr": "",
        "reason": reason,
    }


def _artifact(kind: str, checks: list[dict[str, Any]]) -> dict[str, Any]:
    hard_failures = [c for c in checks if c["status"] == "fail"]
    warnings = [c for c in checks if c["status"] == "warn"]
    skipped = [c for c in checks if c["status"] == "skipped"]
    flags = ["low_coverage"] if skipped else []

    score = 1.0
    score -= 0.25 * len(hard_failures)
    score -= 0.05 * len(warnings)
    score -= 0.10 * len(skipped)
    if hard_failures:
        score = min(score, 0.49)
    score = max(0.0, min(1.0, score))

    observed = len([c for c in checks if c["status"] != "skipped"])
    confidence = observed / max(1, len(checks))

    return {
        "kind": kind,
        "score": round(score, 4),
        "confidence": round(confidence, 4),
        "computed_at": datetime.now(timezone.utc).isoformat(),
        "checks": checks,
        "hard_failures": [c["name"] for c in hard_failures],
        "warnings": [c["name"] for c in warnings],
        "skipped": [c["name"] for c in skipped],
        "flags": flags,
        "evidence_refs": [f"check:{c['name']}" for c in checks],
        "notes": [
            "out-of-band PTR integrity probe",
            "skipped checks lower confidence and score",
        ],
    }


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
