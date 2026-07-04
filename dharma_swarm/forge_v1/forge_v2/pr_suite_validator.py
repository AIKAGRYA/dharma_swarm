"""FAIL_TO_PASS validator for harvested post-cutoff PR-suite candidates.

The harvester is intentionally weak: it only says "this merged PR changed test
files after the model cutoff."  This module is the narrow falsification bridge
between that weak candidate and the fresh task oracle.  A row becomes useful
only when an isolated checkout proves that a changed test target fails on the
pre-fix base and passes on the fixed merge/head revision.

The validator deliberately does *not* derive or bless contamination state.  It
records any caller claim in the receipt, but leaves freshness/held-out
derivation to ``fresh_task_oracle``.
"""
from __future__ import annotations

import argparse
import json
import shlex
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from dharma_swarm.daemon_config import dharma_state_dir

from .fresh_task_oracle import read_manifest
from .signals import canonical_sha256

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


@dataclass(frozen=True)
class CommandResult:
    argv: list[str]
    cwd: str
    returncode: int
    stdout: str
    stderr: str
    timed_out: bool = False

    @property
    def passed(self) -> bool:
        return self.returncode == 0 and not self.timed_out

    def to_receipt(self, *, max_output_chars: int = 4000) -> dict[str, Any]:
        return {
            "argv": self.argv,
            "cwd": self.cwd,
            "returncode": self.returncode,
            "passed": self.passed,
            "timed_out": self.timed_out,
            "stdout_tail": self.stdout[-max_output_chars:],
            "stderr_tail": self.stderr[-max_output_chars:],
        }


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


def _run(argv: list[str], *, cwd: Path, timeout_seconds: int) -> CommandResult:
    try:
        proc = subprocess.run(  # noqa: S603 - argv is constructed without shell=True.
            argv,
            cwd=str(cwd),
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout_seconds,
            check=False,
        )
        return CommandResult(
            argv=list(argv),
            cwd=str(cwd),
            returncode=int(proc.returncode),
            stdout=proc.stdout or "",
            stderr=proc.stderr or "",
        )
    except subprocess.TimeoutExpired as exc:
        return CommandResult(
            argv=list(argv),
            cwd=str(cwd),
            returncode=124,
            stdout=(exc.stdout or "") if isinstance(exc.stdout, str) else "",
            stderr=(exc.stderr or "") if isinstance(exc.stderr, str) else "",
            timed_out=True,
        )


def _git(checkout: Path, *args: str, timeout_seconds: int = 120) -> CommandResult:
    return _run(["git", *args], cwd=checkout, timeout_seconds=timeout_seconds)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True, default=str) + "\n" for row in rows), encoding="utf-8")


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


def _clean_checkout(checkout: Path, *, timeout_seconds: int) -> list[CommandResult]:
    return [
        _git(checkout, "reset", "--hard", timeout_seconds=timeout_seconds),
        _git(checkout, "clean", "-ffdx", timeout_seconds=timeout_seconds),
    ]


def _checkout_ref(checkout: Path, ref: str, *, timeout_seconds: int) -> list[CommandResult]:
    commands = _clean_checkout(checkout, timeout_seconds=timeout_seconds)
    commands.append(_git(checkout, "checkout", "--force", ref, timeout_seconds=timeout_seconds))
    return commands


def _rev_parse(checkout: Path, ref: str, *, timeout_seconds: int) -> str:
    result = _git(checkout, "rev-parse", "--verify", ref, timeout_seconds=timeout_seconds)
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
) -> CommandResult:
    """Copy the fixed revision's changed test file into the current checkout.

    Running a newly-added PR test directly on the base commit would fail with
    "file not found," which is not honest FAIL_TO_PASS evidence.  Instead we run
    the fixed revision's test artifact against the base code, then against the
    fixed code.
    """

    test_path = _test_path_from_target(target)
    result = _git(checkout, "show", f"{fixed_ref}:{test_path}", timeout_seconds=timeout_seconds)
    if result.passed:
        destination = checkout / test_path
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(result.stdout, encoding="utf-8")
    return result


def _resolve_base_and_fixed(
    checkout: Path,
    row: dict[str, Any],
    *,
    use_merge_parent_base: bool,
    timeout_seconds: int,
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
            base_ref = f"{_rev_parse(checkout, merge_ref, timeout_seconds=timeout_seconds)}^1"
        except RuntimeError:
            # Fall back to explicit base_sha/head pair.  The receipt will expose
            # the chosen refs and command evidence.
            base_ref = base_ref

    if not base_ref:
        raise ValueError("candidate row must include base_sha/base_ref or a resolvable merge_commit_sha")

    resolved = {
        "base_ref": base_ref,
        "fixed_ref": fixed_ref,
        "base_sha": _rev_parse(checkout, base_ref, timeout_seconds=timeout_seconds),
        "fixed_sha": _rev_parse(checkout, fixed_ref, timeout_seconds=timeout_seconds),
    }
    return base_ref, fixed_ref, resolved


def _clone_repo(repo_url: str, checkout: Path, *, timeout_seconds: int) -> CommandResult:
    checkout.parent.mkdir(parents=True, exist_ok=True)
    return _run(
        ["git", "clone", "--quiet", "--no-hardlinks", repo_url, str(checkout)],
        cwd=checkout.parent,
        timeout_seconds=timeout_seconds,
    )


def validate_candidate(
    row: dict[str, Any],
    *,
    work_root: Path,
    receipt_root: Path,
    test_command_template: str = DEFAULT_TEST_COMMAND_TEMPLATE,
    python: str = sys.executable,
    timeout_seconds: int = 120,
    local_repo_root: Path | None = None,
    keep_workdir: bool = False,
    use_merge_parent_base: bool = True,
    setup_command_template: str = "",
    setup_timeout_seconds: int | None = None,
) -> dict[str, Any]:
    """Validate one harvested PR-suite row and write a receipt."""

    raw = dict(row)
    task_hint = str(raw.get("task_id") or raw.get("instance_id") or raw.get("pr_number") or "candidate")
    row_sha = canonical_sha256(raw)
    run_id = f"pr_suite_ftp_{now_stamp()}_{time.time_ns()}_{row_sha[:12]}"
    row_work_root = work_root.expanduser() / run_id
    checkout = row_work_root / "repo"
    receipt_path = receipt_root.expanduser() / f"{run_id}.json"

    commands: list[dict[str, Any]] = []
    target_results: list[dict[str, Any]] = []
    blockers: list[str] = []
    validated_targets: list[str] = []
    resolved_refs: dict[str, str] = {}
    status = "fail_to_pass_validation_failed"
    repo_url = ""
    started_at = now_stamp()

    try:
        targets = candidate_targets(raw)
        if not targets:
            blockers.append("missing_candidate_test_targets")
            raise ValueError("candidate row has no validator_targets/test_targets/test_files")

        repo_url = _repo_url_for_row(raw, local_repo_root=local_repo_root)
        clone_result = _clone_repo(repo_url, checkout, timeout_seconds=timeout_seconds)
        commands.append({"phase": "clone", **clone_result.to_receipt()})
        if not clone_result.passed:
            blockers.append("clone_failed")
            raise RuntimeError("git clone failed")

        base_ref, fixed_ref, resolved_refs = _resolve_base_and_fixed(
            checkout,
            raw,
            use_merge_parent_base=use_merge_parent_base,
            timeout_seconds=timeout_seconds,
        )

        for target in targets:
            setup_argv = _setup_command(setup_command_template, python=python, checkout=checkout)
            effective_setup_timeout = (
                int(setup_timeout_seconds) if setup_timeout_seconds is not None else max(timeout_seconds, 600)
            )
            base_checkout_commands = _checkout_ref(checkout, base_ref, timeout_seconds=timeout_seconds)
            commands.extend({"phase": "checkout_base", **result.to_receipt()} for result in base_checkout_commands)
            if not all(result.passed for result in base_checkout_commands):
                blockers.append("base_checkout_failed")
                break
            materialize_result = _materialize_fixed_test(
                checkout,
                fixed_ref=fixed_ref,
                target=target,
                timeout_seconds=timeout_seconds,
            )
            commands.append({"phase": "materialize_fixed_test_on_base", "target": target, **materialize_result.to_receipt()})
            if not materialize_result.passed:
                blockers.append("fixed_test_materialization_failed")
                break
            if setup_argv is not None:
                base_setup = _run(setup_argv, cwd=checkout, timeout_seconds=effective_setup_timeout)
                commands.append({"phase": "setup_base", "target": target, **base_setup.to_receipt()})
                if not base_setup.passed:
                    blocker = f"base_setup_failed:{target}"
                    if blocker not in blockers:
                        blockers.append(blocker)
                    break
            base_command = _command_for_target(test_command_template, python=python, target=target, checkout=checkout)
            base_result = _run(base_command, cwd=checkout, timeout_seconds=timeout_seconds)
            commands.append({"phase": "test_base", "target": target, **base_result.to_receipt()})

            fixed_checkout_commands = _checkout_ref(checkout, fixed_ref, timeout_seconds=timeout_seconds)
            commands.extend({"phase": "checkout_fixed", **result.to_receipt()} for result in fixed_checkout_commands)
            if not all(result.passed for result in fixed_checkout_commands):
                blockers.append("fixed_checkout_failed")
                break
            if setup_argv is not None:
                fixed_setup = _run(setup_argv, cwd=checkout, timeout_seconds=effective_setup_timeout)
                commands.append({"phase": "setup_fixed", "target": target, **fixed_setup.to_receipt()})
                if not fixed_setup.passed:
                    blocker = f"fixed_setup_failed:{target}"
                    if blocker not in blockers:
                        blockers.append(blocker)
                    break
            fixed_command = _command_for_target(test_command_template, python=python, target=target, checkout=checkout)
            fixed_result = _run(fixed_command, cwd=checkout, timeout_seconds=timeout_seconds)
            commands.append({"phase": "test_fixed", "target": target, **fixed_result.to_receipt()})

            base_outcome = classify_base_outcome(base_result)
            base_failed = base_outcome == BASE_OUTCOME_FAILED
            target_state = {
                "target": target,
                "base_returncode": base_result.returncode,
                "fixed_returncode": fixed_result.returncode,
                "base_outcome": base_outcome,
                "base_failed": base_failed,
                "fixed_passed": fixed_result.passed,
                "validated_fail_to_pass": base_failed and fixed_result.passed,
            }
            target_results.append(target_state)
            if target_state["validated_fail_to_pass"]:
                validated_targets.append(target)
            elif base_outcome in {
                BASE_OUTCOME_INCONCLUSIVE_TIMEOUT,
                BASE_OUTCOME_INCONCLUSIVE_NO_RUN,
            }:
                # The base test never actually ran to a real verdict; surface it
                # explicitly so a non-run is never silently read as a regression.
                blocker = f"base_test_inconclusive:{target}:{base_outcome}"
                if blocker not in blockers:
                    blockers.append(blocker)

        if validated_targets:
            status = "fail_to_pass_validated"
        elif "base_checkout_failed" not in blockers and "fixed_checkout_failed" not in blockers:
            blockers.append("no_targets_failed_on_base_and_passed_on_fixed")
    except Exception as exc:  # noqa: BLE001 - receipt-first validator; failures become evidence.
        if not blockers:
            blockers.append(f"{type(exc).__name__}: {exc}")

    receipt = {
        "schema": SCHEMA_VERSION,
        "run_id": run_id,
        "started_at": started_at,
        "finished_at": now_stamp(),
        "status": status,
        "task_hint": task_hint,
        "row_sha256": row_sha,
        "repo": raw.get("repo") or raw.get("repository") or "",
        "repo_url": repo_url,
        "checkout_path": str(checkout) if keep_workdir else "",
        "kept_workdir": keep_workdir,
        "candidate_targets": candidate_targets(raw),
        "validated_fail_to_pass": validated_targets,
        "target_results": target_results,
        "resolved_refs": resolved_refs,
        "caller_claimed_contamination_state": raw.get("contamination_state"),
        "contamination_state_trusted": False,
        "test_command_template": test_command_template,
        "setup_command_template": str(setup_command_template or ""),
        "commands": commands,
        "blockers": blockers,
    }
    receipt["receipt_sha256"] = canonical_sha256(receipt)
    _write_json(receipt_path, receipt)

    output_row = dict(raw)
    output_row["validation_schema"] = SCHEMA_VERSION
    output_row["validation_state"] = status
    output_row["requires_fail_to_pass_validation"] = status != "fail_to_pass_validated"
    output_row["fail_to_pass"] = list(validated_targets)
    output_row["validation_receipt"] = str(receipt_path)
    output_row["validation_receipt_sha256"] = receipt["receipt_sha256"]
    output_row["validated_base_sha"] = resolved_refs.get("base_sha", "")
    output_row["validated_fixed_sha"] = resolved_refs.get("fixed_sha", "")
    output_row["validator_blockers"] = list(blockers)

    if not keep_workdir:
        shutil.rmtree(row_work_root, ignore_errors=True)

    return {
        "schema": SCHEMA_VERSION,
        "status": status,
        "row_sha256": row_sha,
        "task_hint": task_hint,
        "validated": bool(validated_targets),
        "validated_targets": validated_targets,
        "blockers": blockers,
        "receipt": str(receipt_path),
        "receipt_sha256": receipt["receipt_sha256"],
        "row": output_row,
    }


def validate_rows(
    rows: Iterable[dict[str, Any]],
    *,
    work_root: Path,
    receipt_root: Path,
    test_command_template: str = DEFAULT_TEST_COMMAND_TEMPLATE,
    python: str = sys.executable,
    timeout_seconds: int = 120,
    local_repo_root: Path | None = None,
    keep_workdir: bool = False,
    include_failed: bool = False,
    use_merge_parent_base: bool = True,
    setup_command_template: str = "",
    setup_timeout_seconds: int | None = None,
) -> dict[str, Any]:
    results: list[dict[str, Any]] = []
    output_rows: list[dict[str, Any]] = []
    for row in rows:
        result = validate_candidate(
            dict(row),
            work_root=work_root,
            receipt_root=receipt_root,
            test_command_template=test_command_template,
            python=python,
            timeout_seconds=timeout_seconds,
            local_repo_root=local_repo_root,
            keep_workdir=keep_workdir,
            use_merge_parent_base=use_merge_parent_base,
            setup_command_template=setup_command_template,
            setup_timeout_seconds=setup_timeout_seconds,
        )
        results.append({key: value for key, value in result.items() if key != "row"})
        if result["validated"] or include_failed:
            output_rows.append(dict(result["row"]))
    return {
        "schema": SCHEMA_VERSION,
        "input_count": len(results),
        "validated_count": sum(1 for result in results if result["validated"]),
        "failed_count": sum(1 for result in results if not result["validated"]),
        "output_count": len(output_rows),
        "output_rows": output_rows,
        "results": results,
        "receipt_root": str(receipt_root),
        "work_root": str(work_root),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate PR-suite candidates into explicit FAIL_TO_PASS rows")
    parser.add_argument("--manifest", required=True, help="Input JSON/JSONL candidate manifest from pr_suite_harvester")
    parser.add_argument("--out", required=True, help="Output JSONL manifest for fresh_task_oracle")
    parser.add_argument("--receipt-root", default=str(DEFAULT_RECEIPT_ROOT))
    parser.add_argument("--work-root", default="", help="Isolated checkout root; default uses a temporary directory")
    parser.add_argument("--local-repo-root", default="", help="Optional local mirror root used before GitHub clone URLs")
    parser.add_argument("--test-command-template", default=DEFAULT_TEST_COMMAND_TEMPLATE)
    parser.add_argument(
        "--setup-command-template",
        default="",
        help=(
            "Optional environment provisioning command rendered per checkout before "
            "the base and fixed test runs, e.g. '{python} -m pip install -e .'. "
            "Empty (default) preserves the historical bare-clone behaviour."
        ),
    )
    parser.add_argument(
        "--setup-timeout-seconds",
        type=int,
        default=0,
        help="Timeout for the setup command; 0 uses max(timeout_seconds, 600).",
    )
    parser.add_argument("--python", default=sys.executable)
    parser.add_argument("--timeout-seconds", type=int, default=120)
    parser.add_argument("--keep-workdir", action="store_true")
    parser.add_argument("--include-failed", action="store_true", help="Also write failed validation rows to --out")
    parser.add_argument("--no-merge-parent-base", action="store_true", help="Use row base_sha instead of merge_commit_sha^1")
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    rows = read_manifest(Path(args.manifest).expanduser())
    receipt_root = Path(args.receipt_root).expanduser()
    local_repo_root = Path(args.local_repo_root).expanduser() if args.local_repo_root else None
    setup_timeout = args.setup_timeout_seconds or None

    if args.work_root or args.keep_workdir:
        work_root = Path(args.work_root).expanduser() if args.work_root else receipt_root / "workdirs"
        work_root.mkdir(parents=True, exist_ok=True)
        summary = validate_rows(
            rows,
            work_root=work_root,
            receipt_root=receipt_root,
            test_command_template=args.test_command_template,
            python=args.python,
            timeout_seconds=args.timeout_seconds,
            local_repo_root=local_repo_root,
            keep_workdir=args.keep_workdir,
            include_failed=args.include_failed,
            use_merge_parent_base=not args.no_merge_parent_base,
            setup_command_template=args.setup_command_template,
            setup_timeout_seconds=setup_timeout,
        )
    else:
        with tempfile.TemporaryDirectory(prefix="forge-pr-suite-validator-") as temp:
            summary = validate_rows(
                rows,
                work_root=Path(temp),
                receipt_root=receipt_root,
                test_command_template=args.test_command_template,
                python=args.python,
                timeout_seconds=args.timeout_seconds,
                local_repo_root=local_repo_root,
                keep_workdir=args.keep_workdir,
                include_failed=args.include_failed,
                use_merge_parent_base=not args.no_merge_parent_base,
                setup_command_template=args.setup_command_template,
                setup_timeout_seconds=setup_timeout,
            )

    write_jsonl(Path(args.out).expanduser(), list(summary["output_rows"]))
    printable = {key: value for key, value in summary.items() if key != "output_rows"}
    printable["out"] = args.out
    if args.json:
        print(json.dumps(printable, indent=2, sort_keys=True, default=str))
    else:
        print(
            "FORGE_PR_SUITE_FAIL_TO_PASS_VALIDATED "
            f"validated={summary['validated_count']} failed={summary['failed_count']} out={args.out}"
        )
    return 0 if summary["validated_count"] > 0 or not rows else 1


__all__ = [
    "DEFAULT_TEST_COMMAND_TEMPLATE",
    "SCHEMA_VERSION",
    "candidate_targets",
    "validate_candidate",
    "validate_rows",
    "write_jsonl",
]


if __name__ == "__main__":
    raise SystemExit(main())
