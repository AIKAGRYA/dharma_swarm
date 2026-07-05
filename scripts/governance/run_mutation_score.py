#!/usr/bin/env python3
"""Run mutmut and emit a stable governance mutation-score report.

`check_track_status.py` intentionally does not run mutation testing inline.
This script is the explicit, local-first producer for the S6 evidence artifact:

    reports/governance/mutation_score.json

The mutmut output file is treated as raw tool output; this script projects it
into the small schema the governance gate reads.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_REPORT_PATH = REPO_ROOT / "reports/governance/mutation_score.json"
DEFAULT_MUTMUT_STATS_PATH = REPO_ROOT / "mutants/mutmut-cicd-stats.json"


def utc_now() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def run_command(cmd: list[str], *, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)


def git_context(repo_root: Path) -> tuple[str, bool]:
    try:
        sha = run_command(["git", "rev-parse", "HEAD"], cwd=repo_root)
        status = run_command(["git", "status", "--porcelain"], cwd=repo_root)
    except OSError:
        return "", False
    git_sha = sha.stdout.strip() if sha.returncode == 0 else ""
    git_dirty = bool(status.stdout.strip()) if status.returncode == 0 else False
    return git_sha, git_dirty


def _int(stats: dict[str, Any], key: str) -> int:
    try:
        return int(stats.get(key, 0) or 0)
    except (TypeError, ValueError):
        return 0


def build_report(stats: dict[str, Any], *, threshold: float, command: str) -> dict[str, Any]:
    killed = _int(stats, "killed")
    caught_by_type_check = _int(stats, "caught_by_type_check")
    survived = _int(stats, "survived")
    no_tests = _int(stats, "no_tests")
    timeout = _int(stats, "timeout")
    suspicious = _int(stats, "suspicious")
    segfault = _int(stats, "segfault")
    interrupted = _int(stats, "check_was_interrupted_by_user")
    skipped = _int(stats, "skipped")
    raw_total = _int(stats, "total")

    observed_total = (
        killed
        + caught_by_type_check
        + survived
        + no_tests
        + timeout
        + suspicious
        + segfault
        + interrupted
    )
    total = raw_total - skipped if raw_total > skipped else observed_total
    if total <= 0:
        score = 0.0
    else:
        score = (killed + caught_by_type_check) / total

    git_sha, git_dirty = git_context(REPO_ROOT)
    return {
        "schema_version": "mutation_score.v1",
        "produced_at": utc_now(),
        "tool": "mutmut",
        "command": command,
        "git_sha": git_sha,
        "git_dirty": git_dirty,
        "threshold": threshold,
        "score": round(score, 6),
        "passed": score >= threshold,
        "killed": killed + caught_by_type_check,
        "total": total,
        "raw_counts": {
            "killed": killed,
            "caught_by_type_check": caught_by_type_check,
            "survived": survived,
            "no_tests": no_tests,
            "timeout": timeout,
            "suspicious": suspicious,
            "segfault": segfault,
            "check_was_interrupted_by_user": interrupted,
            "skipped": skipped,
            "total": raw_total,
        },
    }


def read_stats(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise SystemExit(f"{path} missing; run mutmut before exporting stats") from exc
    except json.JSONDecodeError as exc:
        raise SystemExit(f"{path} is not valid JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise SystemExit(f"{path} is not a JSON object")
    return data


def write_report(report: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def run(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--threshold", type=float, default=0.60)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT_PATH)
    parser.add_argument("--stats-file", type=Path, default=DEFAULT_MUTMUT_STATS_PATH)
    parser.add_argument("--skip-mutmut-run", action="store_true",
                        help="Only normalize an existing mutmut-cicd-stats.json file.")
    parser.add_argument("--max-children", type=int, default=None,
                        help="Passed through to `mutmut run --max-children`.")
    args = parser.parse_args(argv)

    # Invoke mutmut through its cli() entry point, NOT `python -m mutmut`. Under
    # `-m`, the module loads as `__main__`; the mutant trampoline then re-imports
    # it as `mutmut.__main__`, re-running that module's top-level
    # `set_start_method('fork')` and crashing every instrumented test with
    # "context has already been set". Importing cli() loads the module once under
    # its real name, so the trampoline's re-import is cached.
    mutmut_cmd = [sys.executable, "-c", "from mutmut.__main__ import cli; cli()"]
    run_cmd = [*mutmut_cmd, "run"]
    if args.max_children is not None:
        run_cmd.extend(["--max-children", str(args.max_children)])
    export_cmd = [*mutmut_cmd, "export-cicd-stats"]

    if not args.skip_mutmut_run:
        res = run_command(run_cmd, cwd=REPO_ROOT)
        if res.returncode != 0:
            sys.stderr.write(res.stdout)
            sys.stderr.write(res.stderr)
            return res.returncode
        res = run_command(export_cmd, cwd=REPO_ROOT)
        if res.returncode != 0:
            sys.stderr.write(res.stdout)
            sys.stderr.write(res.stderr)
            return res.returncode

    stats = read_stats(args.stats_file)
    command = " ".join(run_cmd if not args.skip_mutmut_run else ["normalize-mutmut-stats"])
    report = build_report(stats, threshold=args.threshold, command=command)
    write_report(report, args.report)
    print(
        f"mutation score {report['score']:.2f} "
        f"({'PASS' if report['passed'] else 'FAIL'}; "
        f"{report['killed']}/{report['total']} mutants killed) -> {args.report}"
    )
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(run())
