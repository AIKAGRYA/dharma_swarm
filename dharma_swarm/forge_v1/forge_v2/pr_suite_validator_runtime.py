"""Runtime helpers for the PR-suite FAIL_TO_PASS validator."""
from __future__ import annotations

import json
import shlex
import time
from pathlib import Path
from typing import Any

from dharma_swarm.daemon_config import dharma_state_dir

from .pr_suite_execution import (
    CommandExecutor,
    CommandResult,
    atomic_write_json,
    atomic_write_text,
    materialize_text,
    validated_target_path,
)


SCHEMA_VERSION = "forge_v2.pr_suite_fail_to_pass_validator.v1"
DEFAULT_TEST_COMMAND_TEMPLATE = "{python} -m pytest -q {targets}"
DEFAULT_RECEIPT_ROOT = dharma_state_dir() / "forge_v1" / "task_harvests" / "pr_suite_validation_receipts"

# pytest exit-code semantics (documented contract, verified empirically):
#   0 = all selected tests passed
#   1 = tests ran and at least one FAILED
#   2 = collection / internal error (e.g. ImportError because a new API/helper
#       introduced by the PR does not exist on the base commit)
#   3 = internal error while running tests
#   4 = usage error / no tests were selected (e.g. a bad ``file::node`` id)
#   5 = no tests were collected
# Only exit 1 (a real test failure) and exit 2 (a real collection error that the
# fix removes) count as an honest FAIL on the base commit.  Exit 4/5, a timeout
# (our sentinel 124), or exit 3 mean "the test never really ran" -- treating any
# of those as a base failure would mint FAIL_TO_PASS tasks that never observed a
# regression, which is exactly the self-deception the Honest Loop must refuse.
PYTEST_PASSED = 0
PYTEST_BASE_FAILING_CODES = frozenset({1, 2})

BASE_OUTCOME_FAILED = "failed_on_base"
BASE_OUTCOME_PASSED = "passed_on_base"
BASE_OUTCOME_INCONCLUSIVE_TIMEOUT = "inconclusive_timeout_on_base"
BASE_OUTCOME_INCONCLUSIVE_NO_RUN = "inconclusive_no_real_run_on_base"


def now_stamp() -> str:
    return time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())


def classify_base_outcome(result: "CommandResult") -> str:
    """Classify a base-commit test run into an honest outcome bucket.

    A FAIL_TO_PASS candidate is only real when the base commit *ran the test and
    it genuinely failed*.  We therefore separate a real failure (exit 1/2) from
    "the test never really ran" (timeout, no-tests-selected, no-tests-collected,
    internal harness error), so the latter can never be counted as a regression.
    """

    if result.timed_out:
        return BASE_OUTCOME_INCONCLUSIVE_TIMEOUT
    if result.returncode == PYTEST_PASSED:
        return BASE_OUTCOME_PASSED
    if result.returncode in PYTEST_BASE_FAILING_CODES:
        return BASE_OUTCOME_FAILED
    return BASE_OUTCOME_INCONCLUSIVE_NO_RUN


def _run(
    argv: list[str],
    *,
    cwd: Path,
    timeout_seconds: int,
    executor: CommandExecutor,
    stdin: str | None = None,
) -> CommandResult:
    """Run only through the explicit evaluator isolation boundary."""

    return executor.run(argv, cwd=cwd, timeout_seconds=timeout_seconds, stdin=stdin)


def _git(
    checkout: Path,
    *args: str,
    timeout_seconds: int = 120,
    executor: CommandExecutor,
    stdin: str | None = None,
) -> CommandResult:
    return _run(
        ["git", *args],
        cwd=checkout,
        timeout_seconds=timeout_seconds,
        executor=executor,
        stdin=stdin,
    )


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    atomic_write_json(path, payload)


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    atomic_write_text(
        path,
        "".join(json.dumps(row, sort_keys=True, default=str) + "\n" for row in rows),
    )


def _list_field(row: dict[str, Any], *names: str) -> list[str]:
    for name in names:
        value = row.get(name)
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()]
        if isinstance(value, str) and value.strip():
            return [value.strip()]
    return []


def candidate_targets(row: dict[str, Any]) -> list[str]:
    """Return candidate test targets; these are *not* trusted as FAIL_TO_PASS."""

    # Explicit validator_targets lets a preparatory tool narrow files to pytest
    # node IDs without pretending they were already FAIL_TO_PASS evidence.
    return _list_field(row, "validator_targets", "test_targets", "test_files")


def _repo_url_for_row(row: dict[str, Any], *, local_repo_root: Path | None = None) -> str:
    for key in ("repo_path", "clone_url", "repo_url", "local_repo"):
        value = str(row.get(key) or "").strip()
        if value:
            return str(Path(value).expanduser()) if key in {"repo_path", "local_repo"} else value

    repo = str(row.get("repo") or row.get("repository") or "").strip().strip("/")
    if not repo:
        raise ValueError("candidate row must include repo, repo_path, clone_url, repo_url, or local_repo")
    expanded = Path(repo).expanduser()
    if expanded.exists():
        return str(expanded)
    if local_repo_root is not None:
        candidate = local_repo_root.expanduser() / repo
        if candidate.exists():
            return str(candidate)
    return f"https://github.com/{repo}.git"


def _command_for_target(template: str, *, python: str, target: str, checkout: Path) -> list[str]:
    quoted_target = shlex.quote(target)
    command = template.format(
        python=shlex.quote(python),
        target=quoted_target,
        targets=quoted_target,
        checkout=shlex.quote(str(checkout)),
    )
    argv = shlex.split(command)
    if not argv:
        raise ValueError("test command template rendered to an empty command")
    return argv


def _setup_command(template: str, *, python: str, checkout: Path) -> list[str] | None:
    """Render an optional environment-provisioning command for a checkout.

    Returns ``None`` when no template is configured so the historical
    "run pytest against a bare clone" behaviour is preserved exactly.  When a
    template is provided (for example ``{python} -m pip install -e .``) the
    validator installs the target project into the interpreter running the tests
    *before* the base and fixed test runs, so a changed test can actually import
    the project and its dependencies.  Without this, real FAIL_TO_PASS
    candidates collapse into ``no_targets_failed_on_base_and_passed_on_fixed``
    because pytest errors identically on both revisions.
    """

    text = str(template or "").strip()
    if not text:
        return None
    command = text.format(
        python=shlex.quote(python),
        checkout=shlex.quote(str(checkout)),
    )
    argv = shlex.split(command)
    if not argv:
        raise ValueError("setup command template rendered to an empty command")
    return argv


def _clean_checkout(
    checkout: Path,
    *,
    timeout_seconds: int,
    executor: CommandExecutor,
) -> list[CommandResult]:
    return [
        _git(checkout, "reset", "--hard", timeout_seconds=timeout_seconds, executor=executor),
        _git(checkout, "clean", "-ffdx", timeout_seconds=timeout_seconds, executor=executor),
    ]


def _checkout_ref(
    checkout: Path,
    ref: str,
    *,
    timeout_seconds: int,
    executor: CommandExecutor,
) -> list[CommandResult]:
    commands = _clean_checkout(checkout, timeout_seconds=timeout_seconds, executor=executor)
    commands.append(
        _git(
            checkout,
            "checkout",
            "--force",
            "--detach",
            ref,
            timeout_seconds=timeout_seconds,
            executor=executor,
        )
    )
    return commands


def _rev_parse(
    checkout: Path,
    ref: str,
    *,
    timeout_seconds: int,
    executor: CommandExecutor,
) -> str:
    result = _git(
        checkout,
        "rev-parse",
        "--verify",
        "--end-of-options",
        ref,
        timeout_seconds=timeout_seconds,
        executor=executor,
    )
    if not result.passed:
        raise RuntimeError(f"could not resolve git ref {ref!r}: {result.stderr or result.stdout}")
    return result.stdout.strip()


def _test_path_from_target(target: str) -> str:
    """Best-effort path component from a pytest-style target."""

    return target.split("::", 1)[0].strip()


def _materialize_fixed_test(
    checkout: Path,
    *,
    fixed_ref: str,
    target: str,
    timeout_seconds: int,
    executor: CommandExecutor,
) -> CommandResult:
    """Copy the fixed revision's changed test file into the current checkout.

    Running a newly-added PR test directly on the base commit would fail with
    "file not found," which is not honest FAIL_TO_PASS evidence.  Instead we run
    the fixed revision's test artifact against the base code, then against the
    fixed code.
    """

    test_path = validated_target_path(target, checkout)
    result = _git(
        checkout,
        "show",
        f"{fixed_ref}:{test_path}",
        timeout_seconds=timeout_seconds,
        executor=executor,
    )
    if result.passed:
        materialize_text(checkout, test_path, result.stdout)
    return result


def _resolve_base_and_fixed(
    checkout: Path,
    row: dict[str, Any],
    *,
    use_merge_parent_base: bool,
    timeout_seconds: int,
    executor: CommandExecutor,
) -> tuple[str, str, dict[str, str]]:
    merge_ref = str(row.get("merge_commit_sha") or row.get("merge_sha") or "").strip()
    head_ref = str(row.get("head_sha") or row.get("fixed_sha") or row.get("head_ref") or "").strip()
    base_ref = str(row.get("validation_base_sha") or row.get("base_sha") or row.get("base_ref") or "").strip()

    fixed_ref = merge_ref or head_ref
    if not fixed_ref:
        raise ValueError("candidate row must include merge_commit_sha or head_sha/fixed_sha")

    if merge_ref and use_merge_parent_base:
        # For GitHub merged PRs, the API's base.sha can drift.  The first parent
        # of the merge commit is the exact pre-fix base for merge commits.
        try:
            base_ref = f"{_rev_parse(checkout, merge_ref, timeout_seconds=timeout_seconds, executor=executor)}^1"
        except RuntimeError:
            # Fall back to explicit base_sha/head pair.  The receipt will expose
            # the chosen refs and command evidence.
            base_ref = base_ref

    if not base_ref:
        raise ValueError("candidate row must include base_sha/base_ref or a resolvable merge_commit_sha")

    resolved = {
        "base_ref": base_ref,
        "fixed_ref": fixed_ref,
        "base_sha": _rev_parse(checkout, base_ref, timeout_seconds=timeout_seconds, executor=executor),
        "fixed_sha": _rev_parse(checkout, fixed_ref, timeout_seconds=timeout_seconds, executor=executor),
    }
    return base_ref, fixed_ref, resolved


def _clone_repo(
    repo_url: str,
    checkout: Path,
    *,
    timeout_seconds: int,
    executor: CommandExecutor,
) -> CommandResult:
    checkout.parent.mkdir(parents=True, exist_ok=True)
    return _run(
        ["git", "clone", "--quiet", "--no-hardlinks", "--", repo_url, str(checkout)],
        cwd=checkout.parent,
        timeout_seconds=timeout_seconds,
        executor=executor,
    )
