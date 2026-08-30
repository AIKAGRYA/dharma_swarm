"""Agent-fast CI compiler: ruff correctness + blast-radius pytest + typed report.

This is the inner loop background agents wait on. It always writes a report
and always exits with a real status. It never becomes a required-check skip.

Fail open: if the diff cannot be trusted, lint ``dharma_swarm/`` and run
``tests/test_agent_fast.py`` so the runner itself is still proven.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from scripts.ci.classify_changed_paths import changed_paths  # noqa: E402

REPORT_SCHEMA = "dharma.ci_agent_report.v1"
RUFF_SELECT = "E9,F63,F7,F82"
SMOKE_TESTS = ("tests/test_agent_fast.py",)
MAX_PYTEST_TARGETS = 30
CLAIM_BOUNDARY = (
    "agent-fast does not replace pytest (3.11)/(3.12). A green agent-fast "
    "report does not prove the full suite, merge-queue behaviour, or that "
    "unrelated modules still pass."
)


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def select_pytest_targets(paths: list[str], root: Path) -> list[str]:
    """Map changed files onto existing test files. Missing files are skipped."""
    targets: set[str] = set(SMOKE_TESTS)
    for path in paths:
        candidate = Path(path)
        if path.startswith("tests/") and path.endswith(".py"):
            if (root / path).is_file():
                targets.add(path)
            continue
        if not path.endswith(".py"):
            continue
        stem = candidate.stem
        if stem.startswith("test_"):
            guess = f"tests/{stem}.py"
        else:
            guess = f"tests/test_{stem}.py"
        if (root / guess).is_file():
            targets.add(guess)
    ordered = sorted(targets)
    return ordered[:MAX_PYTEST_TARGETS]


def select_ruff_paths(paths: list[str], root: Path) -> list[str]:
    py_files = [
        path
        for path in paths
        if path.endswith(".py") and (root / path).is_file()
    ]
    if py_files:
        return py_files
    return ["dharma_swarm"]


def write_report(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _run(argv: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        argv,
        cwd=cwd,
        text=True,
        capture_output=True,
        check=False,
    )


def _compact_output(proc: subprocess.CompletedProcess[str], *, limit: int = 4000) -> str:
    text = (proc.stdout or "") + (proc.stderr or "")
    text = text.strip()
    if len(text) <= limit:
        return text
    return text[:limit] + "\n...[truncated]..."


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--event", default=os.environ.get("GITHUB_EVENT_NAME", ""))
    parser.add_argument("--base", default=os.environ.get("BASE_SHA", ""))
    parser.add_argument("--head", default=os.environ.get("HEAD_SHA", ""))
    parser.add_argument(
        "--report",
        default=os.environ.get("AGENT_FAST_REPORT", "ci-agent-report.json"),
    )
    parser.add_argument("--python", default=sys.executable)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    root = repo_root()
    report_path = Path(args.report)
    if not report_path.is_absolute():
        report_path = root / report_path

    event = args.event or "local"
    paths = None
    scope = "smoke"
    reason = "no trusted diff; smoke scope"
    if event in {"pull_request", "merge_group", "push"} and args.base and args.head:
        paths = changed_paths(args.base, args.head)
        if paths is None:
            reason = f"could not read diff {args.base[:12]}..{args.head[:12]}"
        elif not paths:
            reason = "empty diff"
            scope = "smoke"
        else:
            scope = "targeted"
            reason = f"classified {len(paths)} changed path(s)"
    elif event not in {"pull_request", "merge_group", "push"}:
        reason = f"event={event or '<empty>'} is not a hosted PR/push"

    ruff_paths = select_ruff_paths(paths or [], root) if scope == "targeted" else ["dharma_swarm"]
    pytest_targets = (
        select_pytest_targets(paths or [], root) if scope == "targeted" else list(SMOKE_TESTS)
    )

    ruff = _run(
        ["ruff", "check", *ruff_paths, f"--select={RUFF_SELECT}"],
        cwd=root,
    )
    pytest_proc = _run(
        [
            args.python,
            "-m",
            "pytest",
            *pytest_targets,
            "-q",
            "--tb=short",
            "--timeout=30",
            "-m",
            "not slow and not docker and not network",
        ],
        cwd=root,
    )

    status = 0
    if ruff.returncode != 0:
        status = ruff.returncode
    elif pytest_proc.returncode != 0:
        status = pytest_proc.returncode

    payload = {
        "schema": REPORT_SCHEMA,
        "ok": status == 0,
        "scope": scope,
        "reason": reason,
        "event": event,
        "changed_path_count": None if paths is None else len(paths),
        "ruff_paths": ruff_paths,
        "pytest_targets": pytest_targets,
        "ruff_exit": ruff.returncode,
        "pytest_exit": pytest_proc.returncode,
        "ruff_output": _compact_output(ruff),
        "pytest_output": _compact_output(pytest_proc),
        "local_command": "make agent-fast",
        "claim_boundary": CLAIM_BOUNDARY,
    }
    write_report(report_path, payload)

    summary = [
        f"agent-fast {'PASS' if status == 0 else 'FAIL'} scope={scope}",
        f"reason: {reason}",
        f"ruff_exit={ruff.returncode} pytest_exit={pytest_proc.returncode}",
        f"report: {report_path}",
        "",
        CLAIM_BOUNDARY,
    ]
    text = "\n".join(summary) + "\n"
    sys.stdout.write(text)
    if payload["ruff_output"]:
        sys.stdout.write("\n--- ruff ---\n" + payload["ruff_output"] + "\n")
    if payload["pytest_output"]:
        sys.stdout.write("\n--- pytest ---\n" + payload["pytest_output"] + "\n")

    step_summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if step_summary:
        Path(step_summary).open("a", encoding="utf-8").write(
            "## agent-fast\n\n```\n" + text + "```\n"
        )
    return status


if __name__ == "__main__":  # pragma: no cover - CLI entry
    raise SystemExit(main())
