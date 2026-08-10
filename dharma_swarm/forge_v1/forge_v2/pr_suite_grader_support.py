"""Git, receipt-binding, and test-materialization support for PR-suite grading."""
from __future__ import annotations

import shlex
from pathlib import Path
from typing import Any

from . import pr_suite_execution as execution
from .pr_suite_execution import CommandExecutor, CommandResult


DEFAULT_TEST_COMMAND_TEMPLATE = "{python} -m pytest -q {targets}"


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
    stdin: str | None = None,
    executor: CommandExecutor,
) -> CommandResult:
    return _run(
        ["git", *args],
        cwd=checkout,
        timeout_seconds=timeout_seconds,
        stdin=stdin,
        executor=executor,
    )


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    execution.atomic_write_json(path, payload)


def _repo_url_for_row(row: dict[str, Any]) -> str:
    for key in ("repo_path", "clone_url", "repo_url", "local_repo"):
        value = str(row.get(key) or "").strip()
        if value:
            return (
                str(Path(value).expanduser())
                if key in {"repo_path", "local_repo"}
                else value
            )
    repo = str(row.get("repo") or row.get("repository") or "").strip().strip("/")
    if not repo:
        raise ValueError(
            "PR-suite task row must include repo, repo_path, clone_url, repo_url, or local_repo"
        )
    expanded = Path(repo).expanduser()
    if expanded.exists():
        return str(expanded)
    return f"https://github.com/{repo}.git"


def _clone_repo(
    repo_url: str,
    checkout: Path,
    *,
    timeout_seconds: int,
    executor: CommandExecutor | None = None,
) -> CommandResult:
    checkout.parent.mkdir(parents=True, exist_ok=True)
    if executor is None:
        sources = [Path(repo_url)] if Path(repo_url).expanduser().exists() else []
        executor = execution.build_executor(
            profile=None,
            workspace_root=checkout.parent,
            source_roots=sources,
            total_timeout_seconds=timeout_seconds,
        )
    return _run(
        ["git", "clone", "--quiet", "--no-hardlinks", "--", repo_url, str(checkout)],
        cwd=checkout.parent,
        timeout_seconds=timeout_seconds,
        executor=executor,
    )


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
        raise RuntimeError(
            f"could not resolve git ref {ref!r}: {result.stderr or result.stdout}"
        )
    return result.stdout.strip()


def _resolve_refs(
    checkout: Path,
    row: dict[str, Any],
    *,
    timeout_seconds: int,
    executor: CommandExecutor | None = None,
) -> dict[str, str]:
    if executor is None:
        executor = execution.build_executor(
            profile=None,
            workspace_root=checkout.parent,
            total_timeout_seconds=timeout_seconds,
        )
    fixed_ref = str(
        row.get("validated_fixed_sha")
        or row.get("merge_commit_sha")
        or row.get("head_sha")
        or row.get("fixed_sha")
        or ""
    ).strip()
    base_ref = str(
        row.get("validated_base_sha")
        or row.get("validation_base_sha")
        or row.get("base_sha")
        or ""
    ).strip()
    if not fixed_ref:
        raise ValueError(
            "PR-suite task row must include validated_fixed_sha, merge_commit_sha, or head_sha"
        )
    if not base_ref:
        merge = str(row.get("merge_commit_sha") or "").strip()
        if merge:
            base_ref = (
                f"{_rev_parse(checkout, merge, timeout_seconds=timeout_seconds, executor=executor)}^1"
            )
    if not base_ref:
        raise ValueError(
            "PR-suite task row must include validated_base_sha/base_sha or merge_commit_sha"
        )
    return {
        "base_ref": base_ref,
        "fixed_ref": fixed_ref,
        "base_sha": _rev_parse(
            checkout,
            base_ref,
            timeout_seconds=timeout_seconds,
            executor=executor,
        ),
        "fixed_sha": _rev_parse(
            checkout,
            fixed_ref,
            timeout_seconds=timeout_seconds,
            executor=executor,
        ),
    }


def _checkout_ref(
    checkout: Path,
    ref: str,
    *,
    timeout_seconds: int,
    executor: CommandExecutor | None = None,
) -> list[CommandResult]:
    if executor is None:
        executor = execution.build_executor(
            profile=None,
            workspace_root=checkout.parent,
            total_timeout_seconds=timeout_seconds,
        )
    return [
        _git(
            checkout,
            "reset",
            "--hard",
            timeout_seconds=timeout_seconds,
            executor=executor,
        ),
        _git(
            checkout,
            "clean",
            "-ffdx",
            timeout_seconds=timeout_seconds,
            executor=executor,
        ),
        _git(
            checkout,
            "checkout",
            "--force",
            "--detach",
            ref,
            timeout_seconds=timeout_seconds,
            executor=executor,
        ),
    ]


def _target_path(target: str) -> str:
    return str(target).split("::", 1)[0].strip()


def _is_test_path(path: str) -> bool:
    lowered = path.lower()
    name = lowered.rsplit("/", 1)[-1]
    return (
        lowered.startswith("tests/")
        or "/tests/" in lowered
        or lowered.startswith("testing/")
        or "/testing/" in lowered
        or name == "conftest.py"
        or name.startswith("test_")
        or name.endswith("_test.py")
        or name.endswith(".test.ts")
        or name.endswith(".test.tsx")
        or name.endswith(".spec.ts")
        or name.endswith(".spec.tsx")
    )


def _list_field(row: dict[str, Any], *names: str) -> list[str]:
    for name in names:
        value = row.get(name)
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()]
        if isinstance(value, str) and value.strip():
            return [value.strip()]
    return []


def fail_to_pass_targets(row: dict[str, Any]) -> list[str]:
    return _list_field(row, "fail_to_pass", "FAIL_TO_PASS")


def _command_template(row: dict[str, Any]) -> str:
    """Legacy observer retained for imports; rows no longer select commands."""

    del row
    return DEFAULT_TEST_COMMAND_TEMPLATE


def _command_for_targets(
    template: str,
    *,
    python: str,
    targets: list[str],
    checkout: Path,
) -> list[str]:
    if not targets:
        raise ValueError("no FAIL_TO_PASS targets supplied")
    quoted_targets = " ".join(shlex.quote(target) for target in targets)
    command = template.format(
        python=shlex.quote(python),
        target=shlex.quote(targets[0]),
        targets=quoted_targets,
        checkout=shlex.quote(str(checkout)),
    )
    argv = shlex.split(command)
    if not argv:
        raise ValueError("test command template rendered to an empty command")
    return argv


def _setup_command(
    template: str,
    *,
    python: str,
    checkout: Path,
) -> list[str] | None:
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


def _changed_files(
    checkout: Path,
    refs: dict[str, str],
    *,
    timeout_seconds: int,
    executor: CommandExecutor | None = None,
) -> list[str]:
    if executor is None:
        executor = execution.build_executor(
            profile=None,
            workspace_root=checkout.parent,
            total_timeout_seconds=timeout_seconds,
        )
    result = _git(
        checkout,
        "diff",
        "--name-only",
        refs["base_sha"],
        refs["fixed_sha"],
        timeout_seconds=timeout_seconds,
        executor=executor,
    )
    if not result.passed:
        return []
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def _model_changed_files(
    checkout: Path,
    *,
    timeout_seconds: int,
    executor: CommandExecutor,
) -> tuple[list[str], list[CommandResult]]:
    """Enumerate every tracked or untracked path created by a model patch."""

    results = [
        _git(
            checkout,
            "diff",
            "--name-only",
            "-z",
            "--no-ext-diff",
            "--relative",
            "HEAD",
            "--",
            timeout_seconds=timeout_seconds,
            executor=executor,
        ),
        _git(
            checkout,
            "ls-files",
            "--others",
            "--exclude-standard",
            "-z",
            "--",
            timeout_seconds=timeout_seconds,
            executor=executor,
        ),
    ]
    if not all(result.passed for result in results):
        raise RuntimeError("could not enumerate model-patch paths")
    paths: list[str] = []
    for result in results:
        for raw in result.stdout.split("\x00"):
            path = raw.strip()
            if path and path not in paths:
                paths.append(path)
    return paths, results


def _materialize_fixed_tests(
    checkout: Path,
    *,
    fixed_ref: str,
    targets: list[str],
    timeout_seconds: int,
    executor: CommandExecutor,
) -> list[CommandResult]:
    commands: list[CommandResult] = []
    paths = {execution.validated_target_path(target, checkout) for target in targets}
    for path in sorted(paths):
        result = _git(
            checkout,
            "show",
            f"{fixed_ref}:{path}",
            timeout_seconds=timeout_seconds,
            executor=executor,
        )
        commands.append(result)
        if result.passed:
            execution.materialize_text(checkout, path, result.stdout)
    return commands
