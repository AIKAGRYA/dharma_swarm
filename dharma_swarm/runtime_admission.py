"""Fail-closed provenance admission for the live swarm runtime.

The live daemon may run only from a clean tracked checkout that is either
exactly ``origin/main`` or an explicitly pinned descendant of the current
local ``origin/main``.  The pin is intended for immutable release worktrees;
ordinary development checkouts receive no branch-ahead exception.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Mapping, Sequence


_FULL_GIT_SHA = re.compile(r"^[0-9a-f]{40}$")
_FULL_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_DEFAULT_BASE_REF = "origin/main"
_EXPECTED_COMMIT_ENV = "DHARMA_RUNTIME_EXPECTED_COMMIT"
_PROVENANCE_MODE_ENV = "DHARMA_RUNTIME_PROVENANCE_MODE"
_CONTAINER_PROVENANCE_MODE = "container-image"
_CONTAINER_SOURCE_ROOT_ENV = "DHARMA_RUNTIME_SOURCE_ROOT"
_CONTAINER_MANIFEST_ENV = "DHARMA_RUNTIME_SOURCE_MANIFEST"
_CONTAINER_DIGEST_ENV = "DHARMA_RUNTIME_SOURCE_DIGEST"
_CONTAINER_MANIFEST_NAME = ".dharma-runtime-source.sha256"
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


@dataclass(frozen=True)
class ContainerRuntimeAdmission:
    """Successful provenance for one image-baked, manifest-bound source tree."""

    source_root: Path
    manifest: Path
    source_digest: str


RuntimeAdmissionResult = RuntimeAdmission | ContainerRuntimeAdmission


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


def _require_full_sha256(value: str, *, label: str) -> str:
    normalized = value.strip().lower()
    if not _FULL_SHA256.fullmatch(normalized):
        raise RuntimeAdmissionError(f"{label} must be a full 64-character SHA-256")
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


def _parse_source_manifest(manifest: Path) -> dict[PurePosixPath, str]:
    entries: dict[PurePosixPath, str] = {}
    try:
        lines = manifest.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise RuntimeAdmissionError(
            f"container source manifest is unreadable: {manifest}"
        ) from exc
    if not lines:
        raise RuntimeAdmissionError("container source manifest is empty")

    for line in lines:
        match = re.fullmatch(r"([0-9a-f]{64})  (\./.+)", line)
        if match is None:
            raise RuntimeAdmissionError("container source manifest is malformed")
        relative = PurePosixPath(match.group(2)[2:])
        if relative.is_absolute() or ".." in relative.parts or relative in entries:
            raise RuntimeAdmissionError("container source manifest has an unsafe path")
        entries[relative] = match.group(1)
    return entries


def assess_container_runtime_admission(
    source_root: Path,
    *,
    manifest: Path,
    expected_digest: str,
) -> ContainerRuntimeAdmission:
    """Verify an image-baked source tree without treating it as Git authority."""
    root = source_root.expanduser().resolve()
    manifest_path = manifest.expanduser().resolve()
    digest = _require_full_sha256(
        expected_digest,
        label=_CONTAINER_DIGEST_ENV,
    )
    if not root.is_dir():
        raise RuntimeAdmissionError(f"container source root is not a directory: {root}")
    if manifest_path.name != _CONTAINER_MANIFEST_NAME:
        raise RuntimeAdmissionError("container source manifest name is not canonical")
    if manifest_path.parent != root.parent:
        raise RuntimeAdmissionError(
            "container source manifest must be adjacent to the source root"
        )
    try:
        manifest_digest = hashlib.sha256(manifest_path.read_bytes()).hexdigest()
    except OSError as exc:
        raise RuntimeAdmissionError(
            f"container source manifest is unreadable: {manifest_path}"
        ) from exc
    if manifest_digest != digest:
        raise RuntimeAdmissionError("container source manifest digest does not match")

    expected_entries = _parse_source_manifest(manifest_path)
    observed_entries: dict[PurePosixPath, str] = {}
    for path in sorted(root.rglob("*")):
        if path.is_symlink():
            raise RuntimeAdmissionError(
                f"container source tree contains a symlink: {path.relative_to(root)}"
            )
        if not path.is_file():
            continue
        relative = PurePosixPath(path.relative_to(root).as_posix())
        try:
            observed_entries[relative] = hashlib.sha256(path.read_bytes()).hexdigest()
        except OSError as exc:
            raise RuntimeAdmissionError(
                f"container source path is unreadable: {relative}"
            ) from exc

    if observed_entries != expected_entries:
        raise RuntimeAdmissionError(
            "container source tree does not match its image-baked manifest"
        )
    return ContainerRuntimeAdmission(
        source_root=root,
        manifest=manifest_path,
        source_digest=digest,
    )


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


def _loaded_package_root() -> Path:
    """Return the directory supplying the running ``dharma_swarm`` package."""
    module_root = Path(__file__).resolve().parent
    package = sys.modules.get(__package__ or "dharma_swarm")
    package_file = getattr(package, "__file__", None)
    if package_file is None:
        raise RuntimeAdmissionError(
            "loaded dharma_swarm package has no file origin"
        )
    package_root = Path(package_file).resolve().parent
    if package_root != module_root:
        raise RuntimeAdmissionError(
            "loaded dharma_swarm package is split across directories: "
            f"{package_root} != {module_root}"
        )
    return module_root


def require_runtime_admission(
    repo_root: Path | None = None,
    *,
    expected_commit: str | None = None,
    environ: Mapping[str, str] | None = None,
) -> RuntimeAdmissionResult:
    """Require admission using the release pin from the environment by default.

    Container-image admission is execution-bound: the verified source root
    must be the directory supplying the loaded ``dharma_swarm`` package, so a
    valid manifest tree elsewhere on disk cannot vouch for unverified code.
    """
    environment = os.environ if environ is None else environ
    provenance_mode = environment.get(_PROVENANCE_MODE_ENV, "").strip()
    if provenance_mode:
        if provenance_mode != _CONTAINER_PROVENANCE_MODE:
            raise RuntimeAdmissionError(
                f"unsupported runtime provenance mode: {provenance_mode}"
            )
        if expected_commit is not None or _EXPECTED_COMMIT_ENV in environment:
            raise RuntimeAdmissionError(
                "container-image provenance cannot be combined with a Git commit pin"
            )
        source_root = environment.get(_CONTAINER_SOURCE_ROOT_ENV)
        manifest = environment.get(_CONTAINER_MANIFEST_ENV)
        source_digest = environment.get(_CONTAINER_DIGEST_ENV)
        if source_root is None or manifest is None or source_digest is None:
            raise RuntimeAdmissionError(
                "container-image provenance requires source root, manifest, and digest"
            )
        admission = assess_container_runtime_admission(
            Path(source_root),
            manifest=Path(manifest),
            expected_digest=source_digest,
        )
        loaded_root = _loaded_package_root()
        if loaded_root != admission.source_root:
            raise RuntimeAdmissionError(
                "verified container source root does not supply the loaded "
                f"runtime: {admission.source_root} != {loaded_root}"
            )
        return admission

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
) -> RuntimeAdmissionResult:
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
    if isinstance(admission, ContainerRuntimeAdmission):
        print(
            "runtime admission passed: "
            f"provenance=container-image source_digest={admission.source_digest}"
        )
    else:
        print(
            "runtime admission passed: "
            f"provenance=git-checkout head={admission.head} "
            f"origin_main={admission.origin_main} "
            f"ahead={admission.ahead} behind={admission.behind}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
