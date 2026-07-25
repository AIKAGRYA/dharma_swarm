"""Fail-closed provenance admission for the live swarm runtime.

The live daemon may run only from a clean tracked checkout that is either
exactly ``origin/main`` or an explicitly pinned descendant of the current
local ``origin/main``.  The pin is intended for immutable release worktrees;
ordinary development checkouts receive no branch-ahead exception.
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Sequence


_FULL_GIT_SHA = re.compile(r"^[0-9a-f]{40}$")
_DEFAULT_BASE_REF = "origin/main"
_EXPECTED_COMMIT_ENV = "DHARMA_RUNTIME_EXPECTED_COMMIT"
_GIT_TIMEOUT_SECONDS = 10.0
_FALSE_VALUES = frozenset({"0", "false", "no", "off"})
_IGNORED_IMPORT_PATHS = (
    ":(top,glob)sitecustomize.py[co]",
    ":(top,glob)usercustomize.py[co]",
    ":(top,glob)dharma_swarm/**/*.py[co]",
)


class RuntimeAdmissionError(RuntimeError):
    """Raised when runtime code provenance cannot be admitted."""


@dataclass(frozen=True)
class RuntimeAdmission:
    """Successful, fully observed runtime provenance."""

    repo_root: Path
    head: str
    origin_main: str
    expected_commit: str | None
    ahead: int
    behind: int


def runtime_control_enabled(
    name: str,
    environ: Mapping[str, str] | None = None,
) -> bool:
    """Treat an unset runtime control as enabled and false-like values as off."""
    environment = os.environ if environ is None else environ
    raw = environment.get(name)
    return raw is None or raw.strip().lower() not in _FALSE_VALUES


def _git_environment(environ: Mapping[str, str] | None = None) -> dict[str, str]:
    """Return a Git environment without ambient repository/config overrides."""
    inherited = dict(os.environ if environ is None else environ)
    environment = {
        key: value
        for key, value in inherited.items()
        if not key.upper().startswith("GIT_")
    }
    environment.update(
        {
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_OPTIONAL_LOCKS": "0",
        }
    )
    return environment


def _git(
    repo_root: Path,
    *args: str,
    environ: Mapping[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            ["git", "-c", "core.fsmonitor=false", "-C", str(repo_root), *args],
            capture_output=True,
            text=True,
            timeout=_GIT_TIMEOUT_SECONDS,
            env=_git_environment(environ),
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise RuntimeAdmissionError(
            f"git provenance probe unavailable: {type(exc).__name__}"
        ) from exc


def _git_output(
    repo_root: Path,
    *args: str,
    environ: Mapping[str, str] | None = None,
) -> str:
    result = _git(repo_root, *args, environ=environ)
    if result.returncode != 0:
        raise RuntimeAdmissionError(
            f"git provenance probe failed: {' '.join(args)}"
        )
    return result.stdout.strip()


def _canonical_repo_root(
    repo_root: Path,
    *,
    environ: Mapping[str, str] | None = None,
) -> Path:
    candidate = repo_root.expanduser().resolve()
    if not candidate.is_dir():
        raise RuntimeAdmissionError(f"runtime root is not a directory: {candidate}")
    observed = _git_output(
        candidate,
        "rev-parse",
        "--show-toplevel",
        environ=environ,
    )
    observed_root = Path(observed).resolve()
    if observed_root != candidate:
        raise RuntimeAdmissionError(
            f"runtime root must be the git toplevel: {candidate}"
        )
    return candidate


def _require_full_sha(value: str, *, label: str) -> str:
    normalized = value.strip().lower()
    if not _FULL_GIT_SHA.fullmatch(normalized):
        raise RuntimeAdmissionError(f"{label} must be a full 40-character commit SHA")
    return normalized


def _ignored_import_artifacts(
    repo_root: Path,
    *,
    environ: Mapping[str, str] | None = None,
) -> tuple[str, ...]:
    """Return ignored bytecode that can alter imports from the runtime root."""
    output = _git_output(
        repo_root,
        "ls-files",
        "--others",
        "--ignored",
        "--exclude-standard",
        "--",
        *_IGNORED_IMPORT_PATHS,
        environ=environ,
    )
    return tuple(line for line in output.splitlines() if line.strip())


def assess_runtime_admission(
    repo_root: Path,
    *,
    expected_commit: str | None = None,
    base_ref: str = _DEFAULT_BASE_REF,
    environ: Mapping[str, str] | None = None,
) -> RuntimeAdmission:
    """Evaluate one checkout and return its admitted provenance.

    Ignored files such as the dedicated release virtualenv remain outside
    Git's reported surface. Every visible tracked, submodule, or untracked
    path is a hard denial because an untracked Python file can alter imports.
    """
    root = _canonical_repo_root(repo_root, environ=environ)
    expected = (
        _require_full_sha(expected_commit, label=_EXPECTED_COMMIT_ENV)
        if expected_commit is not None
        else None
    )
    head = _require_full_sha(
        _git_output(root, "rev-parse", "--verify", "HEAD", environ=environ),
        label="HEAD",
    )
    origin_main = _require_full_sha(
        _git_output(root, "rev-parse", "--verify", base_ref, environ=environ),
        label=base_ref,
    )

    tracked_status = _git_output(
        root,
        "status",
        "--porcelain=v1",
        "--untracked-files=normal",
        "--ignore-submodules=none",
        environ=environ,
    )
    tracked_changes = tuple(
        line for line in tracked_status.splitlines() if line.strip()
    )
    if tracked_changes:
        raise RuntimeAdmissionError(
            f"checkout has uncommitted paths ({len(tracked_changes)} path(s))"
        )
    ignored_imports = _ignored_import_artifacts(root, environ=environ)
    if ignored_imports:
        raise RuntimeAdmissionError(
            "checkout has ignored import bytecode "
            f"({len(ignored_imports)} path(s))"
        )

    counts = _git_output(
        root,
        "rev-list",
        "--left-right",
        "--count",
        f"HEAD...{base_ref}",
        environ=environ,
    ).split()
    if len(counts) != 2:
        raise RuntimeAdmissionError("git ahead/behind probe returned malformed output")
    try:
        ahead, behind = (int(value) for value in counts)
    except ValueError as exc:
        raise RuntimeAdmissionError(
            "git ahead/behind probe returned non-integer output"
        ) from exc

    if expected is None:
        if head != origin_main:
            raise RuntimeAdmissionError(
                "unpinned runtime must equal origin/main "
                f"(ahead={ahead}, behind={behind})"
            )
    else:
        if head != expected:
            raise RuntimeAdmissionError(
                f"runtime HEAD {head} does not match pinned commit {expected}"
            )
        ancestor = _git(
            root,
            "merge-base",
            "--is-ancestor",
            base_ref,
            "HEAD",
            environ=environ,
        )
        if ancestor.returncode not in {0, 1}:
            raise RuntimeAdmissionError("git ancestry probe failed")
        if ancestor.returncode != 0 or behind != 0:
            raise RuntimeAdmissionError(
                f"pinned runtime is not a current-main descendant (behind={behind})"
            )

    return RuntimeAdmission(
        repo_root=root,
        head=head,
        origin_main=origin_main,
        expected_commit=expected,
        ahead=ahead,
        behind=behind,
    )


def require_runtime_admission(
    repo_root: Path | None = None,
    *,
    expected_commit: str | None = None,
    environ: Mapping[str, str] | None = None,
) -> RuntimeAdmission:
    """Require admission using the release pin from the environment by default."""
    environment = os.environ if environ is None else environ
    expected = (
        environment.get(_EXPECTED_COMMIT_ENV)
        if expected_commit is None
        else expected_commit
    )
    root = (
        Path(__file__).resolve().parents[1]
        if repo_root is None
        else repo_root
    )
    return assess_runtime_admission(
        root,
        expected_commit=expected,
        environ=environment,
    )


def runtime_admission_or_exit(
    repo_root: Path | None = None,
    *,
    expected_commit: str | None = None,
    environ: Mapping[str, str] | None = None,
) -> RuntimeAdmission:
    """Command-boundary adapter with a stable configuration-error exit code."""
    try:
        return require_runtime_admission(
            repo_root,
            expected_commit=expected_commit,
            environ=environ,
        )
    except RuntimeAdmissionError as exc:
        print(f"orchestrate-live admission denied: {exc}", file=sys.stderr)
        raise SystemExit(78) from exc


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--repo",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help="exact runtime git toplevel",
    )
    parser.add_argument(
        "--expected-commit",
        default=None,
        help=f"full release commit (defaults to {_EXPECTED_COMMIT_ENV})",
    )
    args = parser.parse_args(argv)
    admission = runtime_admission_or_exit(
        args.repo,
        expected_commit=args.expected_commit,
    )
    print(
        "runtime admission passed: "
        f"provenance=git-checkout head={admission.head} "
        f"origin_main={admission.origin_main} "
        f"ahead={admission.ahead} behind={admission.behind}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
