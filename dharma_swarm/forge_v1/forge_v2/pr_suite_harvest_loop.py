"""Bounded PR-suite harvest/validate/import loop for Forge v2.

This module is the repo-native replacement for one-off VPS scripts that harvest
post-cutoff pull-request candidates, validate real FAIL_TO_PASS targets, and
import only eligible rows into the durable taskbed ledger.

Authority boundary:
* may write harvest artifacts under ``root``;
* may import validated fresh tasks into the configured taskbed DB;
* must not mutate source code, live routing, archive fitness, or promotion
  state.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Sequence

from dharma_swarm.daemon_config import dharma_state_dir

from . import taskbed_ledger
from .signals import canonical_sha256

SCHEMA_VERSION = "forge_v2.pr_suite_harvest_loop.v1"
DEFAULT_ROOT = dharma_state_dir() / "forge_v1" / "task_harvests"
DEFAULT_REPOS = (
    "pallets/click",
    "pallets/werkzeug",
    "pallets/flask",
    "pytest-dev/pytest",
    "django/django",
)


@dataclass(frozen=True)
class CommandResult:
    """Small subprocess result shape for deterministic tests and receipts."""

    argv: list[str]
    returncode: int
    stdout: str = ""
    stderr: str = ""
    timed_out: bool = False


CommandRunner = Callable[[Sequence[str], Path, int], CommandResult]


def utc_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _safe_run_id(text: str) -> str:
    run_id = "".join(ch if ch.isalnum() or ch in {"-", "_", "."} else "_" for ch in text.strip())
    return run_id or time.strftime("pr_suite_harvest_%Y%m%dT%H%M%SZ", time.gmtime())


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
    tmp.replace(path)


def _append_log(log_path: Path, row: dict[str, Any]) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(row, sort_keys=True, default=str)
    print(line, flush=True)
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(line + "\n")


def _line_count(path: Path) -> int:
    if not path.exists():
        return 0
    return sum(1 for line in path.read_text(encoding="utf-8").splitlines() if line.strip())


def _json_from_stdout(stdout: str) -> dict[str, Any]:
    text = stdout.strip()
    if not text:
        return {}
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def run_command(argv: Sequence[str], cwd: Path, timeout_seconds: int) -> CommandResult:
    """Run a loop subprocess and capture output without raising on non-zero."""

    try:
        completed = subprocess.run(
            list(argv),
            cwd=str(cwd),
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout_seconds,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        return CommandResult(
            argv=list(argv),
            returncode=124,
            stdout=exc.stdout if isinstance(exc.stdout, str) else "",
            stderr=exc.stderr if isinstance(exc.stderr, str) else "",
            timed_out=True,
        )
    return CommandResult(
        argv=list(argv),
        returncode=int(completed.returncode),
        stdout=completed.stdout or "",
        stderr=completed.stderr or "",
    )


def _command_event(event: str, cycle: int, result: CommandResult, **extra: Any) -> dict[str, Any]:
    return {
        "schema": f"{SCHEMA_VERSION}.event",
        "ts": utc_now(),
        "event": event,
        "cycle": cycle,
        "returncode": result.returncode,
        "timed_out": result.timed_out,
        "argv": result.argv,
        "stdout_tail": result.stdout[-2000:],
        "stderr_tail": result.stderr[-1000:],
        **extra,
    }


def loop_authority() -> dict[str, Any]:
    """Return the explicit authority envelope recorded in every closeout."""

    return {
        "source_code_mutation_allowed": False,
        "source_of_truth_mutated": False,
        "live_apply_allowed": False,
        "live_apply_performed": False,
        "archive_fitness_mutated": False,
        "official_score_claimed": False,
        "promotion_gate": "verify_promotion_only",
        "taskbed_import_allowed": True,
    }


def run_harvest_loop(
    *,
    root: Path | str,
    repo_root: Path | str,
    db_path: Path | str = taskbed_ledger.DEFAULT_DB,
    run_id: str | None = None,
    repos: Sequence[str] = DEFAULT_REPOS,
    since: str = "2026-04-01T00:00:00Z",
    model_cutoff: str = "2026-04-01T00:00:00Z",
    duration_seconds: int = 2 * 3600,
    max_cycles: int = 8,
    sleep_seconds: int = 600,
    limit_per_repo: int = 2,
    max_pages: int = 1,
    validation_timeout_seconds: int = 900,
    command_timeout_seconds: int = 3600,
    github_token_env: str = "GITHUB_TOKEN,GH_TOKEN",
    python: str = sys.executable,
    command_runner: CommandRunner = run_command,
    sleep_fn: Callable[[float], None] = time.sleep,
) -> dict[str, Any]:
    """Run a bounded harvest/validate/import loop and write a closeout receipt."""

    repo_root = Path(repo_root).expanduser().resolve()
    db_path = Path(db_path).expanduser()
    repos = [str(repo).strip() for repo in repos if str(repo).strip()]
    if not repos:
        raise ValueError("repos must be non-empty")
    if max_cycles <= 0:
        raise ValueError("max_cycles must be positive")
    if duration_seconds <= 0:
        raise ValueError("duration_seconds must be positive")
    if sleep_seconds < 0:
        raise ValueError("sleep_seconds must be non-negative")

    run_id = _safe_run_id(run_id or time.strftime("loop_%Y%m%dT%H%M%SZ", time.gmtime()))
    root = Path(root).expanduser() / run_id
    root.mkdir(parents=True, exist_ok=True)
    log_path = root / "loop.log"
    started = time.time()
    deadline = started + duration_seconds
    events: list[dict[str, Any]] = []
    import_summaries: list[dict[str, Any]] = []

    start_event = {
        "schema": f"{SCHEMA_VERSION}.event",
        "ts": utc_now(),
        "event": "harvest_loop_start",
        "run_id": run_id,
        "root": str(root),
        "repo_root": str(repo_root),
        "db": str(db_path),
        "repos": repos,
        "since": since,
        "deadline_epoch": deadline,
        "authority": loop_authority(),
    }
    _append_log(log_path, start_event)
    events.append(start_event)

    cycle = 0
    while time.time() < deadline and cycle < max_cycles:
        stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
        candidates_path = root / f"candidates_c{cycle:02d}_{stamp}.jsonl"
        validated_path = root / f"validated_c{cycle:02d}_{stamp}.jsonl"

        harvest_cmd = [
            python,
            str(repo_root / "scripts/runtime/forge_pr_suite_harvester.py"),
        ]
        for repo in repos:
            harvest_cmd.extend(["--repo", repo])
        harvest_cmd.extend(
            [
                "--since",
                since,
                "--limit-per-repo",
                str(limit_per_repo),
                "--max-pages",
                str(max_pages),
                "--github-token-env",
                github_token_env,
                "--out",
                str(candidates_path),
                "--json",
            ]
        )
        harvest = command_runner(harvest_cmd, repo_root, min(command_timeout_seconds, 900))
        harvest_event = _command_event(
            "harvest_done",
            cycle,
            harvest,
            out=str(candidates_path),
            candidate_count=_line_count(candidates_path),
            summary=_json_from_stdout(harvest.stdout),
        )
        _append_log(log_path, harvest_event)
        events.append(harvest_event)

        if candidates_path.exists() and candidates_path.stat().st_size > 0:
            validation_cmd = [
                python,
                str(repo_root / "scripts/runtime/forge_pr_suite_validator.py"),
                "--manifest",
                str(candidates_path),
                "--out",
                str(validated_path),
                "--receipt-root",
                str(root / "validation_receipts"),
                "--timeout-seconds",
                str(validation_timeout_seconds),
                "--json",
            ]
            validation = command_runner(validation_cmd, repo_root, command_timeout_seconds)
            validation_summary = _json_from_stdout(validation.stdout)
            validation_event = _command_event(
                "validation_done",
                cycle,
                validation,
                out=str(validated_path),
                validated_count=_line_count(validated_path),
                summary=validation_summary,
                nonzero_is_fatal=validation.returncode not in {0, 1},
            )
            _append_log(log_path, validation_event)
            events.append(validation_event)

            if validated_path.exists() and validated_path.stat().st_size > 0:
                import_cmd = [
                    python,
                    str(repo_root / "scripts/runtime/forge_fresh_task_oracle.py"),
                    "--manifest",
                    str(validated_path),
                    "--model-cutoff",
                    model_cutoff,
                    "--taskbed-db",
                    str(db_path),
                    "--json",
                ]
                imported = command_runner(import_cmd, repo_root, min(command_timeout_seconds, 900))
                import_summary = _json_from_stdout(imported.stdout)
                import_summaries.append(import_summary)
                import_event = _command_event(
                    "import_done",
                    cycle,
                    imported,
                    imported_count=int(import_summary.get("imported_count", 0) or 0),
                    skipped_count=int(import_summary.get("skipped_count", 0) or 0),
                    summary=import_summary,
                )
                _append_log(log_path, import_event)
                events.append(import_event)

        cycle += 1
        if time.time() < deadline and cycle < max_cycles and sleep_seconds:
            sleep_fn(sleep_seconds)

    finished_event = {
        "schema": f"{SCHEMA_VERSION}.event",
        "ts": utc_now(),
        "event": "harvest_loop_finished",
        "run_id": run_id,
        "cycle": cycle,
    }
    _append_log(log_path, finished_event)
    events.append(finished_event)

    closeout = {
        "schema": f"{SCHEMA_VERSION}.closeout",
        "run_id": run_id,
        "started_at": start_event["ts"],
        "finished_at": finished_event["ts"],
        "root": str(root),
        "repo_root": str(repo_root),
        "db": str(db_path),
        "repos": repos,
        "since": since,
        "model_cutoff": model_cutoff,
        "cycle_count": cycle,
        "candidate_files": sorted(str(path) for path in root.glob("candidates_c*.jsonl")),
        "validated_files": sorted(str(path) for path in root.glob("validated_c*.jsonl")),
        "validation_receipt_count": len(list((root / "validation_receipts").glob("*.json"))),
        "candidate_count": sum(_line_count(path) for path in root.glob("candidates_c*.jsonl")),
        "validated_count": sum(_line_count(path) for path in root.glob("validated_c*.jsonl")),
        "imported_count": sum(int(summary.get("imported_count", 0) or 0) for summary in import_summaries),
        "skipped_count": sum(int(summary.get("skipped_count", 0) or 0) for summary in import_summaries),
        "event_count": len(events),
        "events": events,
        "authority": loop_authority(),
    }
    closeout["closeout_sha256"] = canonical_sha256(closeout)
    _write_json(root / "closeout.json", closeout)
    return closeout


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run a bounded Forge PR-suite harvest/validate/import loop")
    parser.add_argument("--run-id", default="", help="Run id / output directory name")
    parser.add_argument("--root", default=str(DEFAULT_ROOT), help="Parent directory for loop artifacts")
    parser.add_argument("--repo-root", default=str(Path.cwd()), help="dharma_swarm checkout containing scripts/runtime")
    parser.add_argument("--taskbed-db", default=str(taskbed_ledger.DEFAULT_DB))
    parser.add_argument("--repo", action="append", default=[], help="GitHub repo owner/name; repeatable")
    parser.add_argument("--repos-file", default="", help="Optional newline-delimited repo list")
    parser.add_argument("--since", default="2026-04-01T00:00:00Z")
    parser.add_argument("--model-cutoff", default="2026-04-01T00:00:00Z")
    parser.add_argument("--duration-seconds", type=int, default=2 * 3600)
    parser.add_argument("--max-cycles", type=int, default=8)
    parser.add_argument("--sleep-seconds", type=int, default=600)
    parser.add_argument("--limit-per-repo", type=int, default=2)
    parser.add_argument("--max-pages", type=int, default=1)
    parser.add_argument("--validation-timeout-seconds", type=int, default=900)
    parser.add_argument("--command-timeout-seconds", type=int, default=3600)
    parser.add_argument(
        "--github-token-env",
        default="GITHUB_TOKEN,GH_TOKEN",
        help="Comma-separated env var names checked for a GitHub API token.",
    )
    parser.add_argument("--python", default=sys.executable)
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    repos = list(args.repo)
    if args.repos_file:
        repos.extend(
            line.strip()
            for line in Path(args.repos_file).expanduser().read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.lstrip().startswith("#")
        )
    if not repos:
        repos = list(DEFAULT_REPOS)
    closeout = run_harvest_loop(
        root=args.root,
        repo_root=args.repo_root,
        db_path=args.taskbed_db,
        run_id=args.run_id or None,
        repos=repos,
        since=args.since,
        model_cutoff=args.model_cutoff,
        duration_seconds=args.duration_seconds,
        max_cycles=args.max_cycles,
        sleep_seconds=args.sleep_seconds,
        limit_per_repo=args.limit_per_repo,
        max_pages=args.max_pages,
        validation_timeout_seconds=args.validation_timeout_seconds,
        command_timeout_seconds=args.command_timeout_seconds,
        github_token_env=args.github_token_env,
        python=args.python,
    )
    if args.json:
        print(json.dumps(closeout, indent=2, sort_keys=True, default=str))
    else:
        print(
            "FORGE_PR_SUITE_HARVEST_LOOP_CLOSEOUT "
            f"run_id={closeout['run_id']} candidates={closeout['candidate_count']} "
            f"validated={closeout['validated_count']} imported={closeout['imported_count']} "
            f"root={closeout['root']}"
        )
    return 0


__all__ = [
    "CommandResult",
    "DEFAULT_REPOS",
    "DEFAULT_ROOT",
    "SCHEMA_VERSION",
    "build_parser",
    "loop_authority",
    "main",
    "run_command",
    "run_harvest_loop",
]


if __name__ == "__main__":
    raise SystemExit(main())
