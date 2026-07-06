"""CLI for the Forge PR-suite harvest loop."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import taskbed_ledger
from .pr_suite_harvest_loop import DEFAULT_REPOS, DEFAULT_ROOT, run_harvest_loop

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
    parser.add_argument(
        "--setup-command-template",
        default="",
        help=(
            "Optional per-checkout provisioning command forwarded to the validator, "
            "e.g. '{python} -m pip install -e .'. Empty preserves bare-clone behaviour."
        ),
    )
    parser.add_argument(
        "--setup-timeout-seconds",
        type=int,
        default=0,
        help="Timeout for the validator setup command; 0 lets the validator choose.",
    )
    parser.add_argument("--python", default=sys.executable)
    parser.add_argument(
        "--validator-python",
        default="",
        help=(
            "Python executable used by the validator for target-project setup/tests. "
            "When empty, defaults to --python. Use this to run loop/oracle code with "
            "the repo interpreter while test checkouts use an isolated venv."
        ),
    )
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
        setup_command_template=args.setup_command_template,
        setup_timeout_seconds=args.setup_timeout_seconds,
        python=args.python,
        validator_python=args.validator_python,
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
