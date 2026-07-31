#!/usr/bin/env python3
"""Run a governed local AgentOps work packet.

AgentOps v0 is deliberately small: it validates a machine-readable work
packet, prepares an isolated git worktree, runs declared gates, enforces a
file-scope contract, writes structured reports, and optionally creates a
local commit candidate. It never merges or pushes.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import re
import shutil
import stat
import subprocess
import sys
import sysconfig
import tempfile
import time
import types
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
sys.dont_write_bytecode = True

# The parent package eagerly imports the optional Textual UI.  AgentOps needs
# only the dependency-light onboarding contract, so give importlib a namespace
# parent instead of executing that unrelated initializer on minimal hosts.
_bootstrapped_operator_core = "dharma_swarm.operator_core" not in sys.modules
_operator_core_stub: types.ModuleType | None = None
if _bootstrapped_operator_core:
    _operator_core_stub = types.ModuleType("dharma_swarm.operator_core")
    _operator_core_stub.__path__ = [str(REPO_ROOT / "dharma_swarm/operator_core")]
    sys.modules[_operator_core_stub.__name__] = _operator_core_stub

from dharma_swarm.operator_core.onboarding.models import (  # noqa: E402, F401
    AgentOpsError,
    ApprovalPolicy,
    CommitPolicy,
    GateSpec,
    ScopeState,
    WorkPacket,
)
from dharma_swarm.operator_core.onboarding.contract import (  # noqa: E402, F401
    build_gate_environment,
    detect_surface_collisions,
    matching_patterns,
    packet_digest,
    parse_gate,
    parse_work_packet,
    path_matches_pattern,
    resolve_external_dir,
)

if _bootstrapped_operator_core:
    sys.modules.pop("dharma_swarm.operator_core", None)
    root_package = sys.modules.get("dharma_swarm")
    if getattr(root_package, "operator_core", None) is _operator_core_stub:
        delattr(root_package, "operator_core")

REPORT_ROOT = Path("reports") / "agentops"
_TRUSTED_HOST_PATH = "/usr/sbin:/usr/bin:/sbin:/bin"
_DARWIN_USER_TEMP_PARENT = Path("/private/var/folders")
_MAX_GATE_TIMEOUT_SECONDS = 300
_MAX_ADMISSION_TIMEOUT_SECONDS = 480
_MAX_BINDING_BYTES = 1_000_000
_LIVE_TRACK_STATUSES = frozenset({"ACTIVE", "SHIPPABLE"})


def _has_live_track_authority(row: Mapping[str, Any] | None) -> bool:
    return row is not None and str(row.get("status", "")).upper() in _LIVE_TRACK_STATUSES


# --- Positive command-family allowlist ---------------------------------------
# One authoritative table. Positive gates are admitted ONLY when
# their argv matches an enumerated family below; everything else fails closed
# BEFORE subprocess execution. This is command-family confinement, not a
# semantic proof about trusted code — pytest and an allowlisted repository
# script can themselves perform I/O; syscall/no-network evidence is the
# terminal oracle. Direct-Git token normalization and grammar remain
# owned by the Session Entry contract module and its lexical helpers; this
# table only decides execution admission. Negative controls are exempt: they
# rejection and run jailed. Extending this table is a governance-reviewed
# admission change, never a drive-by edit.

_PYTHON_EXECUTABLES = frozenset({"python", "python3"})
_TRUSTED_GIT_EXECUTABLES = frozenset({"git", "git.exe", "/usr/bin/git"})
_ALLOWED_REPO_SCRIPT_ARGV = {
    "scripts/governance/orientation_graph.py": {
        (),
        ("--json",),
        ("--graph",),
        ("--graph-json",),
    },
    "scripts/docops/check_docops_integrity.py": {()},
}
# Only no-argument, read-only Make recipes are admitted. The runner supplies
# trusted interpreter variables after admission so repo-local `.venv` shims
# cannot become a transitive executable route.
_SAFE_GATE_TARGET = re.compile(r"^[A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]+)*$")
_SAFE_PYTEST_SELECTOR = re.compile(r"^[A-Za-z0-9_ ()-]+$")
_ALLOWED_MAKE_TARGETS = frozenset({
    "docops-integrity", "hygiene-check", "module-budget",
})


def _admit_make_argv(argv: list[str]) -> bool:
    return len(argv) == 1 and argv[0] in _ALLOWED_MAKE_TARGETS


def _is_trusted_python(token: str) -> bool:
    """A bare `python`/`python3`, or the exact running interpreter path.

    Resolving arbitrary aliases here creates an admission/execution race: a
    symlink can point at the running interpreter during admission and be
    replaced before execution.  It also erases virtual-environment identity.
    Keep the admitted path set lexical and finite; execution normalizes the
    bare forms to this process's exact ``sys.executable`` spelling.
    """
    return token in _PYTHON_EXECUTABLES or token == sys.executable


def _is_trusted_git(token: str) -> bool:
    """Mirror the exact trusted executable forms admitted by the O1R parser.

    Gate normalization replaces every admitted form with the trusted host Git,
    so the Windows spelling is safe to accept even when CI runs on Linux.  No
    other path-qualified executable is admitted.
    """
    normalized = token.lower().replace("\\", "/")
    return normalized in _TRUSTED_GIT_EXECUTABLES or re.fullmatch(
        r"c:/program files/git/cmd/git\.exe", normalized
    ) is not None


def _safe_gate_target(value: str, *, pytest: bool = False) -> bool:
    path = value.split("::", 1)[0] if pytest else value
    if not path or path.startswith(("/", "-")) or "\\" in path:
        return False
    if any(part in {"", ".", ".."} for part in path.split("/")):
        return False
    if not _SAFE_GATE_TARGET.fullmatch(path):
        return False
    return not pytest or path == "tests" or path.startswith("tests/")


def _admit_pytest_argv(argv: list[str]) -> bool:
    index = 0
    while index < len(argv):
        token = argv[index]
        if token == "-q":
            index += 1
            continue
        if token == "-k":
            if index + 1 >= len(argv) or not _SAFE_PYTEST_SELECTOR.fullmatch(
                argv[index + 1]
            ):
                return False
            index += 2
            continue
        if not _safe_gate_target(token, pytest=True):
            return False
        index += 1
    return True


def _admit_python_argv(argv: list[str]) -> bool:
    if argv[:2] == ["-m", "pytest"]:
        return _admit_pytest_argv(argv[2:])
    if argv[:3] == ["-m", "ruff", "check"]:
        targets = argv[3:]
        return bool(targets) and all(_safe_gate_target(target) for target in targets)
    if not argv or not argv[0].startswith("scripts/"):
        return False
    allowed = _ALLOWED_REPO_SCRIPT_ARGV.get(argv[0])
    if allowed is not None and tuple(argv[1:]) in allowed:
        return True
    return (
        argv[0] == "scripts/docops/check_docops_integrity.py"
        and len(argv) == 3
        and argv[1] == "--changed-from"
        and re.fullmatch(r"[0-9a-fA-F]{40}", argv[2]) is not None
    )


def admit_gate_command(gate: GateSpec) -> None:
    """Fail closed unless the positive gate matches an enumerated family.

    Packet-supplied environment is empty by default and no family enumerates
    an allowed key, so any env-carrying gate is rejected outright."""
    argv, command = gate.argv, gate.command
    if gate.env:
        raise AgentOpsError(
            f"gate command may not carry packet-supplied environment: {command}")
    head = argv[0]
    if _is_trusted_git(head):
        # Shape + executable identity are already validated by the O1R direct-
        # Git grammar in parse_gate.  B11 admits the same exact executable
        # spellings, then execution normalizes all of them to trusted host Git.
        return
    if _is_trusted_python(head):
        if _admit_python_argv(argv[1:]):
            return
        raise AgentOpsError(
            f"gate command is outside the positive interpreter allowlist: {command}")
    if head == "make":
        if _admit_make_argv(argv[1:]):
            return
        raise AgentOpsError(
            f"gate command is outside the positive make-target allowlist: {command}")
    raise AgentOpsError(
        f"gate command executable is not in the positive command-family allowlist: {command}")


def run_command(
    argv: list[str],
    *,
    cwd: Path,
    env: dict[str, str] | None = None,
    input_text: str | None = None,
    timeout_seconds: int | None = None,
    preexec_fn: Callable[[], None] | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        argv, cwd=cwd, env=env, input=input_text, capture_output=True, text=True,
        timeout=timeout_seconds, check=False, preexec_fn=preexec_fn,
    )

def trusted_git_environment(
    inherited: Mapping[str, str] | None = None,
) -> dict[str, str]:
    del inherited  # inherited loader/Python/Make/Git injection is never trusted
    environment = {
        "PATH": _TRUSTED_HOST_PATH,
        # Disable implicit per-user ignore/attribute discovery as well as Git
        # configuration.  GIT_CONFIG_GLOBAL alone does not suppress the
        # default $XDG_CONFIG_HOME/git/ignore path.
        "HOME": os.devnull,
        "XDG_CONFIG_HOME": os.devnull,
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
    }
    environment["GIT_CONFIG_GLOBAL"] = os.devnull
    environment["GIT_CONFIG_NOSYSTEM"] = "1"
    environment["GIT_ATTR_NOSYSTEM"] = "1"
    environment["GIT_NO_REPLACE_OBJECTS"] = "1"
    environment["GIT_OPTIONAL_LOCKS"] = "0"
    return environment


def trusted_git_identity_probe_environment(
    inherited: Mapping[str, str] | None = None,
) -> dict[str, str]:
    """Allow only the user's global config while discovering commit identity.

    Every inherited ``GIT_*`` control remains stripped and system config stays
    disabled.  The probe runs only ``git config --global --get user.*``; the
    actual commit still runs with global and system config disabled.
    """

    home = _os_account_home()
    environment = trusted_git_environment(inherited)
    environment.pop("GIT_CONFIG_GLOBAL", None)
    environment.pop("EMAIL", None)
    environment["HOME"] = str(home)
    environment["XDG_CONFIG_HOME"] = str(home / ".config")
    return environment


def run_git(args: list[str], *, cwd: Path, check: bool = True) -> subprocess.CompletedProcess[str]:
    result = run_command(
        [
            "git",
            "-c", "core.fsmonitor=false",
            "-c", f"core.hooksPath={os.devnull}",
            *args,
        ],
        cwd=cwd,
        env=trusted_git_environment(),
    )
    if check and result.returncode != 0:
        detail = (result.stderr or result.stdout).strip()
        raise AgentOpsError(f"git {' '.join(args)} failed: {detail}")
    return result


def run_git_bytes(
    args: list[str], *, cwd: Path, check: bool = True,
) -> subprocess.CompletedProcess[bytes]:
    result = subprocess.run(
        [
            "git",
            "-c", "core.fsmonitor=false",
            "-c", f"core.hooksPath={os.devnull}",
            *args,
        ],
        cwd=cwd,
        env=trusted_git_environment(),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if check and result.returncode != 0:
        detail = (result.stderr or result.stdout).decode(
            "utf-8", errors="surrogateescape"
        ).strip()
        raise AgentOpsError(f"git {' '.join(args)} failed: {detail}")
    return result


def _os_account_home() -> Path:
    """Return the OS account database home, never an inherited env redirect."""

    try:
        import pwd

        home = Path(pwd.getpwuid(os.getuid()).pw_dir).resolve(strict=True)
    except (AttributeError, ImportError, KeyError, OSError) as exc:
        raise AgentOpsError(
            "cannot resolve a trusted OS-account home for Git identity"
        ) from exc
    if not home.is_dir() or home.stat().st_uid != os.getuid():
        raise AgentOpsError("trusted OS-account home has invalid ownership")
    return home


def _identity_config_value(repo_root: Path, key: str) -> str | None:
    result = run_command(
        ["git", "config", "--global", "--no-includes", "--get-all", key],
        cwd=repo_root,
        env=trusted_git_identity_probe_environment(),
    )
    if result.returncode not in (0, 1):
        detail = (result.stderr or result.stdout).strip()
        raise AgentOpsError(f"cannot read trusted Git {key}: {detail}")
    values = result.stdout.splitlines() if result.returncode == 0 else []
    if not values:
        return None
    if len(values) != 1:
        raise AgentOpsError(
            f"trusted global Git {key} must contain exactly one value; "
            f"observed {len(values)}"
        )
    value = values[0].strip()
    if not value or any(character in value for character in "\x00\r\n<>"):
        raise AgentOpsError(f"trusted global Git {key} contains an invalid value")
    if key == "user.email" and (
        "@" not in value or any(character.isspace() for character in value)
    ):
        raise AgentOpsError("trusted global Git user.email is not a plain email")
    return value


def trusted_git_commit_environment(repo_root: Path) -> dict[str, str]:
    environment = trusted_git_environment()
    name = _identity_config_value(repo_root, "user.name")
    email = _identity_config_value(repo_root, "user.email")
    if not name or not email:
        raise AgentOpsError("trusted global Git identity must be a complete pair")
    home = _os_account_home()
    environment.pop("EMAIL", None)
    environment["HOME"] = str(home)
    environment["XDG_CONFIG_HOME"] = str(home / ".config")
    environment["GIT_AUTHOR_NAME"] = name
    environment["GIT_AUTHOR_EMAIL"] = email
    environment["GIT_COMMITTER_NAME"] = name
    environment["GIT_COMMITTER_EMAIL"] = email
    environment["GIT_CONFIG"] = os.devnull
    environment["GIT_PAGER"] = ""
    return environment

def repo_root_from(path: Path) -> Path:
    return Path(run_git(["rev-parse", "--show-toplevel"], cwd=path).stdout.strip()).resolve()

def require_repo_root(path: Path) -> Path:
    root = repo_root_from(path)
    if root != path.resolve():
        raise AgentOpsError(f"run from repo root; got {path.resolve()}, repo root is {root}")
    return root


def _is_within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def _git_admin_roots(repo_root: Path) -> set[Path]:
    roots = {(repo_root / ".git").resolve(strict=False)}
    for flag in ("--git-dir", "--git-common-dir"):
        raw = run_git(["rev-parse", flag], cwd=repo_root).stdout.strip()
        candidate = Path(raw).expanduser()
        if not candidate.is_absolute():
            candidate = repo_root / candidate
        roots.add(candidate.resolve(strict=False))
    return roots


def _validate_external_packet_path(repo_root: Path, packet_path: Path) -> None:
    raw = packet_path.expanduser()
    lexical = raw if raw.is_absolute() else Path(os.path.abspath(raw))
    resolved = raw.resolve(strict=False)
    for boundary in {repo_root.resolve(), *_git_admin_roots(repo_root)}:
        boundary = boundary.resolve(strict=False)
        if _is_within(lexical, boundary) or _is_within(resolved, boundary):
            raise AgentOpsError(
                f"Session Entry Packet must be external to source and Git state: {packet_path}"
            )


def _probe_tool_version(name: str, repo_root: Path) -> str:
    if name == "python":
        return platform.python_version()
    if name == "git":
        result = run_git(["--version"], cwd=repo_root, check=False)
    elif name == "make":
        result = run_command([_trusted_host_tool("make"), "--version"], cwd=repo_root)
    else:
        raise AgentOpsError(f"session_entry declares unsupported tool: {name}")
    if result.returncode != 0:
        raise AgentOpsError(f"could not probe declared tool {name}")
    first_line = result.stdout.splitlines()[0] if result.stdout.splitlines() else ""
    match = re.search(r"\b(\d+(?:\.\d+)+)\b", first_line)
    if match is None:
        raise AgentOpsError(f"could not parse {name} version from {first_line!r}")
    return match.group(1)

def load_raw_packet(
    path: Path,
    *,
    content: bytes | None = None,
) -> dict[str, Any]:
    try:
        raw = path.read_bytes() if content is None else content
        text = raw.decode("utf-8")
    except (OSError, UnicodeError) as exc:
        raise AgentOpsError(f"cannot read UTF-8 work packet {path}: {exc}") from exc
    suffix = path.suffix.lower()
    if suffix == ".json":
        data = json.loads(text)
    elif suffix in {".yaml", ".yml"}:
        try:
            import yaml  # type: ignore[import-not-found]
        except ImportError as exc:
            raise AgentOpsError("YAML packets require PyYAML; use JSON instead") from exc
        data = yaml.safe_load(text)
    else:
        raise AgentOpsError("work packet must end in .json, .yaml, or .yml")
    if not isinstance(data, dict):
        raise AgentOpsError("work packet root must be an object")
    return data

def load_work_packet(
    path: Path,
    *,
    content: bytes | None = None,
) -> WorkPacket:
    return parse_work_packet(load_raw_packet(path, content=content))


def _read_packet_bytes(path: Path) -> bytes:
    try:
        return path.read_bytes()
    except OSError as exc:
        raise AgentOpsError(f"cannot read work packet {path}: {exc}") from exc

def git_nul_records(repo_root: Path, args: list[str]) -> list[str]:
    """Return exact NUL-delimited Git records without pathname normalization."""
    output = run_git_bytes(args, cwd=repo_root).stdout
    if not output:
        return []
    if not output.endswith(b"\0"):
        raise AgentOpsError("Git pathname output was not NUL terminated")
    records = output[:-1].split(b"\0")
    if any(not record for record in records):
        raise AgentOpsError("Git pathname output contained an empty record")
    return [os.fsdecode(record) for record in records]


def _validate_observed_git_paths(paths: Iterable[str]) -> None:
    for path in paths:
        try:
            path.encode("utf-8", errors="strict")
        except UnicodeEncodeError as exc:
            raise AgentOpsError("Git path is not valid UTF-8") from exc
        components = path.split("/")
        if (
            not path
            or path.startswith("/")
            or "\0" in path
            or any(component in {"", ".", ".."} for component in components)
        ):
            raise AgentOpsError(f"Git reported a non-relative governed path: {path!r}")
        if "\\" in path:
            raise AgentOpsError(
                f"Git path contains an ambiguous backslash spelling: {path!r}"
            )


def git_status(repo_root: Path) -> str:
    _reject_local_repository_controls(repo_root, base_ref=None)
    return run_git(["status", "--short"], cwd=repo_root).stdout


def git_object_id_for_bytes(
    repo_root: Path, content: bytes, *, write: bool = False,
) -> str:
    result = subprocess.run(
        [
            "git", "hash-object", *(["-w"] if write else []),
            "--no-filters", "--stdin",
        ],
        cwd=repo_root,
        env=trusted_git_environment(),
        input=content,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if result.returncode != 0:
        detail = result.stderr.decode("utf-8", errors="replace").strip()
        action = "write" if write else "hash"
        raise AgentOpsError(f"could not {action} exact Git blob: {detail}")
    return result.stdout.decode("ascii").strip()


def _reject_hidden_index_flags(repo_root: Path) -> None:
    hidden = sorted(
        row
        for row in git_nul_records(repo_root, ["ls-files", "-v", "-z"])
        if not row.startswith("H ")
    )
    if hidden:
        raise AgentOpsError(
            "governed scope rejects hidden, sparse, or special index flags: "
            f"{hidden}"
        )


def _local_git_info_text(repo_root: Path, relative: str) -> str:
    raw_path = run_git(
        ["rev-parse", "--git-path", relative], cwd=repo_root
    ).stdout.strip()
    control_path = Path(raw_path).expanduser()
    if not control_path.is_absolute():
        control_path = repo_root / control_path
    try:
        parent = control_path.parent.resolve(strict=True)
    except FileNotFoundError:
        return ""
    except OSError as exc:
        raise AgentOpsError(f"cannot inspect local Git {relative}: {exc}") from exc
    if not any(_is_within(parent, root) for root in _git_admin_roots(repo_root)):
        raise AgentOpsError(f"local Git {relative} escapes Git administration state")
    if not hasattr(os, "O_NOFOLLOW") or not hasattr(os, "O_DIRECTORY"):
        raise AgentOpsError("local Git control inspection requires no-follow reads")
    directory_flags = (
        os.O_RDONLY
        | os.O_DIRECTORY
        | os.O_NOFOLLOW
        | getattr(os, "O_CLOEXEC", 0)
    )
    descriptors: list[int] = []
    descriptor: int | None = None
    try:
        descriptors.append(os.open(parent.anchor, directory_flags))
        for component in parent.parts[1:]:
            descriptors.append(
                os.open(component, directory_flags, dir_fd=descriptors[-1])
            )
        file_flags = (
            os.O_RDONLY
            | os.O_NOFOLLOW
            | getattr(os, "O_CLOEXEC", 0)
            | getattr(os, "O_NONBLOCK", 0)
        )
        try:
            descriptor = os.open(
                control_path.name,
                file_flags,
                dir_fd=descriptors[-1],
            )
        except FileNotFoundError:
            return ""
        identity = os.fstat(descriptor)
        if (
            not stat.S_ISREG(identity.st_mode)
            or identity.st_size > _MAX_BINDING_BYTES
        ):
            raise AgentOpsError(
                f"local Git {relative} must be a bounded regular file"
            )
        chunks: list[bytes] = []
        remaining = _MAX_BINDING_BYTES + 1
        while remaining:
            chunk = os.read(descriptor, min(65_536, remaining))
            if not chunk:
                break
            chunks.append(chunk)
            remaining -= len(chunk)
        if remaining == 0:
            raise AgentOpsError(f"local Git {relative} exceeds the read limit")
        current = os.stat(
            control_path.name,
            dir_fd=descriptors[-1],
            follow_symlinks=False,
        )
        if current.st_dev != identity.st_dev or current.st_ino != identity.st_ino:
            raise AgentOpsError(f"local Git {relative} custody changed during read")
        verification = parent.resolve(strict=True)
        verified = os.stat(verification, follow_symlinks=False)
        held_parent = os.fstat(descriptors[-1])
        if (
            verified.st_dev != held_parent.st_dev
            or verified.st_ino != held_parent.st_ino
        ):
            raise AgentOpsError(
                f"local Git {relative} directory changed during read"
            )
        return b"".join(chunks).decode("utf-8")
    except (OSError, UnicodeError) as exc:
        raise AgentOpsError(f"cannot read UTF-8 local Git {relative}: {exc}") from exc
    finally:
        if descriptor is not None:
            os.close(descriptor)
        for item in reversed(descriptors):
            os.close(item)


def _reject_config_values(repo_root: Path, key: str) -> None:
    configured = run_git(
        ["config", "--includes", "--get-all", key],
        cwd=repo_root,
        check=False,
    )
    if configured.returncode not in (0, 1):
        detail = (configured.stderr or configured.stdout).strip()
        raise AgentOpsError(f"cannot inspect local Git {key}: {detail}")
    if configured.returncode == 0 and configured.stdout.splitlines():
        raise AgentOpsError(f"governed scope rejects repository-local {key}")


def _reject_mutable_gitattributes(
    repo_root: Path, *, base_ref: str | None,
) -> None:
    def attribute_paths(paths: Iterable[str]) -> list[str]:
        return sorted(
            path for path in paths if path.rsplit("/", 1)[-1] == ".gitattributes"
        )

    indexed_paths = set(git_nul_records(repo_root, ["ls-files", "-z"]))
    untracked = attribute_paths(
        path for path in _filesystem_leaf_paths(repo_root) if path not in indexed_paths
    )
    if untracked:
        raise AgentOpsError(
            f"governed scope rejects untracked .gitattributes controls: {untracked}"
        )
    staged = attribute_paths(
        git_nul_records(
            repo_root,
            [
                "diff", "--cached", "--no-ext-diff", "--no-textconv",
                "--no-renames", "--name-only", "-z", "--",
            ],
        )
    )
    if staged:
        raise AgentOpsError(
            f"governed scope requires stable staged .gitattributes policy: {staged}"
        )
    tracked = attribute_paths(git_nul_records(repo_root, ["ls-files", "-z"]))
    for path in tracked:
        index_rows = git_nul_records(
            repo_root,
            [
                "--literal-pathspecs", "ls-files", "--stage", "-z", "--", path,
            ],
        )
        index_meta = index_rows[0].split("\t", 1)[0].split() if len(index_rows) == 1 else []
        if len(index_meta) != 3 or index_meta[0] not in {"100644", "100755"} or index_meta[2] != "0":
            raise AgentOpsError(f"tracked .gitattributes has unsafe index custody: {path}")
        index_oid = index_meta[1]
        head_rows = git_nul_records(
            repo_root,
            ["--literal-pathspecs", "ls-tree", "-z", "HEAD", "--", path],
        )
        head_meta = head_rows[0].split("\t", 1)[0].split() if len(head_rows) == 1 else []
        if len(head_meta) != 3 or head_meta[2] != index_oid:
            raise AgentOpsError(f"tracked .gitattributes is staged or HEAD-ambiguous: {path}")
        snapshot = _read_regular_worktree_file(repo_root, path)
        if snapshot is None:
            raise AgentOpsError(f"tracked .gitattributes is absent: {path}")
        worktree_mode, content = snapshot
        if worktree_mode != index_meta[0]:
            raise AgentOpsError(f"tracked .gitattributes has mode drift: {path}")
        if git_object_id_for_bytes(repo_root, content) != index_oid:
            raise AgentOpsError(f"tracked .gitattributes has working-tree drift: {path}")
    if base_ref is not None:
        committed = attribute_paths(
            git_nul_records(
                repo_root,
                [
                    "diff", "--no-ext-diff", "--no-textconv", "--no-renames",
                    "--name-only", "-z", f"{base_ref}...HEAD", "--",
                ],
            )
        )
        if committed:
            raise AgentOpsError(
                f"governed scope requires stable .gitattributes policy: {committed}"
            )


def _reject_local_repository_controls(
    repo_root: Path, *, base_ref: str | None,
) -> None:
    """Reject local filters/ignore state that can falsify Git scope evidence."""
    _reject_config_values(repo_root, "core.excludesFile")
    _reject_config_values(repo_root, "core.attributesFile")
    filters = run_git(
        ["config", "--includes", "--get-regexp", r"^filter\."],
        cwd=repo_root,
        check=False,
    )
    if filters.returncode not in (0, 1):
        detail = (filters.stderr or filters.stdout).strip()
        raise AgentOpsError(f"cannot inspect local Git filter configuration: {detail}")
    if filters.returncode == 0 and filters.stdout.splitlines():
        raise AgentOpsError("governed scope rejects repository-local filter.* config")
    for relative in ("info/exclude", "info/attributes", "info/grafts"):
        text = _local_git_info_text(repo_root, relative)
        active = [
            line for line in text.splitlines()
            if line.strip() and not line.startswith("#")
        ]
        if active:
            raise AgentOpsError(
                f"governed scope rejects active repository-local .git/{relative} entries"
            )
    _reject_mutable_gitattributes(repo_root, base_ref=base_ref)


def _index_entries(repo_root: Path) -> dict[str, tuple[str, str]]:
    """Return the exact stage-0 index map as path -> (mode, object id)."""
    entries: dict[str, tuple[str, str]] = {}
    records = git_nul_records(repo_root, ["ls-files", "--stage", "-z"])
    for record in records:
        metadata, separator, path = record.partition("\t")
        fields = metadata.split()
        if not separator or len(fields) != 3 or fields[2] != "0":
            raise AgentOpsError("governed scope rejects ambiguous Git index stages")
        if path in entries:
            raise AgentOpsError(f"governed scope rejects duplicate index path: {path!r}")
        entries[path] = (fields[0], fields[1])
    _validate_observed_git_paths(entries)
    return entries


def _tree_entries(repo_root: Path, ref: str) -> dict[str, tuple[str, str]]:
    """Return an exact recursive tree map without attributes or diff drivers."""
    entries: dict[str, tuple[str, str]] = {}
    records = git_nul_records(
        repo_root, ["ls-tree", "-r", "--full-tree", "-z", ref]
    )
    for record in records:
        metadata, separator, path = record.partition("\t")
        fields = metadata.split()
        if not separator or len(fields) != 3:
            raise AgentOpsError(f"cannot parse governed Git tree entry at {ref}")
        if path in entries:
            raise AgentOpsError(f"governed tree contains duplicate path: {path!r}")
        entries[path] = (fields[0], fields[2])
    _validate_observed_git_paths(entries)
    return entries


def _git_blob_oid(content: bytes, *, object_format: str) -> str:
    """Hash raw bytes using Git's blob framing, without filters or subprocesses."""
    if object_format not in {"sha1", "sha256"}:
        raise AgentOpsError(f"unsupported Git object format: {object_format!r}")
    digest = hashlib.new(object_format)
    digest.update(f"blob {len(content)}\0".encode("ascii"))
    digest.update(content)
    return digest.hexdigest()


def _filesystem_leaf_paths(repo_root: Path) -> list[str]:
    """Enumerate source leaves without Git ignore or case-folding policy."""
    root = repo_root.resolve()
    if not hasattr(os, "O_NOFOLLOW") or not hasattr(os, "O_DIRECTORY"):
        raise AgentOpsError("governed scope requires no-follow directory enumeration")
    directory_flags = (
        os.O_RDONLY
        | os.O_DIRECTORY
        | os.O_NOFOLLOW
        | getattr(os, "O_CLOEXEC", 0)
    )
    leaves: list[str] = []
    try:
        root_descriptor = os.open(root, directory_flags)
    except OSError as exc:
        raise AgentOpsError(f"cannot open governed source root: {exc}") from exc
    pending: list[tuple[int, str]] = [(root_descriptor, "")]

    def close_pending() -> None:
        while pending:
            descriptor, _ = pending.pop()
            try:
                os.close(descriptor)
            except OSError:
                pass

    while pending:
        directory_descriptor, prefix = pending.pop()
        try:
            with os.scandir(directory_descriptor) as iterator:
                entries = list(iterator)
        except OSError as exc:
            os.close(directory_descriptor)
            close_pending()
            raise AgentOpsError(f"cannot enumerate governed source tree: {exc}") from exc
        try:
            for entry in entries:
                relative = f"{prefix}/{entry.name}" if prefix else entry.name
                if relative == ".git":
                    continue
                try:
                    is_directory = entry.is_dir(follow_symlinks=False)
                except OSError as exc:
                    close_pending()
                    raise AgentOpsError(
                        f"cannot inspect governed source path {relative!r}: {exc}"
                    ) from exc
                if is_directory:
                    try:
                        child_descriptor = os.open(
                            entry.name,
                            directory_flags,
                            dir_fd=directory_descriptor,
                        )
                    except OSError as exc:
                        close_pending()
                        raise AgentOpsError(
                            f"governed source directory changed during enumeration: "
                            f"{relative!r}: {exc}"
                        ) from exc
                    pending.append((child_descriptor, relative))
                else:
                    # Regular files, symlinks, FIFOs, sockets, and devices all
                    # affect the executable source surface and are leaves.
                    leaves.append(relative)
        finally:
            os.close(directory_descriptor)
    _validate_observed_git_paths(leaves)
    return sorted(set(leaves))


def _exact_live_scope_paths(
    repo_root: Path,
) -> tuple[list[str], list[str], list[str]]:
    """Return raw worktree, staged, and all-untracked path classes.

    This deliberately does not trust ``git status`` or worktree ``git diff``:
    clean filters, autocrlf, stat-cache tricks, and core.fileMode can otherwise
    make changed executable bytes or modes appear clean.  Every tracked regular
    file is read no-follow and hashed using Git's raw blob framing.
    """
    index = _index_entries(repo_root)
    head = _tree_entries(repo_root, "HEAD")
    staged = sorted(
        path for path in set(index) | set(head) if index.get(path) != head.get(path)
    )
    object_format = run_git(
        ["rev-parse", "--show-object-format"], cwd=repo_root
    ).stdout.strip()
    working: list[str] = []
    for path, (index_mode, index_oid) in sorted(index.items()):
        if index_mode in {"100644", "100755"}:
            snapshot = _read_regular_worktree_file(repo_root, path)
            if snapshot is None:
                working.append(path)
                continue
            worktree_mode, content = snapshot
            if (
                worktree_mode != index_mode
                or _git_blob_oid(content, object_format=object_format) != index_oid
            ):
                working.append(path)
            continue
        if index_mode == "120000":
            link_bytes = _read_symlink_worktree_file(repo_root, path)
            if link_bytes is None:
                working.append(path)
                continue
            if _git_blob_oid(link_bytes, object_format=object_format) != index_oid:
                working.append(path)
            continue
        raise AgentOpsError(
            f"governed scope rejects unsupported tracked mode {index_mode}: {path}"
        )
    # Do not ask Git which files are untracked: core.ignoreCase and ignore
    # controls can omit executable leaves.  Compare an independent no-follow
    # filesystem enumeration with the exact index instead.
    untracked = sorted(set(_filesystem_leaf_paths(repo_root)) - set(index))
    _validate_observed_git_paths([*working, *staged, *untracked])
    return sorted(set(working)), staged, untracked



def _changed_path_mode_violations(
    repo_root: Path,
    *,
    committed_paths: list[str],
    staged_paths: list[str],
    working_paths: list[str],
) -> list[dict[str, Any]]:
    findings: dict[str, list[str]] = {}

    def record(path: str, layer: str, mode: str) -> None:
        findings.setdefault(path, []).append(f"{layer}:{mode}")

    for path in sorted(set(committed_paths)):
        rows = git_nul_records(
            repo_root,
            ["--literal-pathspecs", "ls-tree", "-z", "HEAD", "--", path],
        )
        if not rows:  # deletion at HEAD is allowed
            continue
        mode = rows[0].split(maxsplit=1)[0]
        if len(rows) != 1 or mode not in {"100644", "100755"}:
            record(path, "HEAD", mode or "ambiguous")

    for path in sorted(set(staged_paths)):
        rows = git_nul_records(
            repo_root,
            ["--literal-pathspecs", "ls-files", "--stage", "-z", "--", path],
        )
        if not rows:  # staged deletion is allowed
            continue
        fields = rows[0].split(maxsplit=3) if len(rows) == 1 else []
        mode = fields[0] if fields else "ambiguous"
        stage = fields[2] if len(fields) == 4 else "ambiguous"
        if len(rows) != 1 or mode not in {"100644", "100755"} or stage != "0":
            record(path, "index", f"{mode}/stage-{stage}")

    for path in sorted(set(working_paths)):
        try:
            metadata = os.lstat(repo_root / path)
        except FileNotFoundError:  # working deletion is allowed
            continue
        except OSError as exc:
            raise AgentOpsError(f"cannot inspect governed worktree path {path}: {exc}") from exc
        if not stat.S_ISREG(metadata.st_mode):
            record(path, "worktree", oct(stat.S_IFMT(metadata.st_mode)))

    return [
        {
            "path": path,
            "reason": "non_regular_mode",
            "patterns": sorted(layers),
        }
        for path, layers in sorted(findings.items())
    ]


def inspect_scope(
    repo_root: Path,
    packet: WorkPacket,
    *,
    base_ref: str | None = None,
) -> ScopeState:
    """Inspect the complete packet diff with one forbidden-first matcher.

    ``base_ref`` turns on closeout semantics: committed ``base...HEAD`` paths
    are folded into the same tracked bucket as unstaged paths.  Staged and
    untracked paths remain separately visible, while ``changed_files`` is the
    de-duplicated union used by the existing scope policy.
    """
    _reject_hidden_index_flags(repo_root)
    _reject_local_repository_controls(repo_root, base_ref=base_ref)
    unstaged, staged, untracked = _exact_live_scope_paths(repo_root)
    if base_ref is not None:
        base = _tree_entries(repo_root, base_ref)
        head = _tree_entries(repo_root, "HEAD")
        committed = sorted(
            path
            for path in set(base) | set(head)
            if base.get(path) != head.get(path)
        )
    else:
        committed = []
    tracked = sorted(set(committed + unstaged))
    _validate_observed_git_paths([*committed, *unstaged, *staged, *untracked])
    changed = sorted(set(tracked + staged + untracked))
    violations: list[dict[str, Any]] = []
    for path in changed:
        forbidden = matching_patterns(path, packet.forbidden_files)
        allowed = matching_patterns(path, packet.allowed_files)
        if forbidden:
            violations.append({"path": path, "reason": "forbidden", "patterns": forbidden})
        elif not allowed:
            violations.append({"path": path, "reason": "outside_allowed_scope", "patterns": []})
    violations.extend(
        _changed_path_mode_violations(
            repo_root,
            committed_paths=committed,
            staged_paths=staged,
            working_paths=sorted(set(unstaged + untracked)),
        )
    )
    return ScopeState(
        tracked_changed_files=tracked,
        staged_files=staged,
        untracked_files=untracked,
        changed_files=changed,
        violations=violations,
    )


def resolve_base_ref(source_root: Path, base_ref: str) -> str:
    return run_git(["rev-parse", base_ref], cwd=source_root).stdout.strip()


def branch_for(repo_root: Path) -> str:
    return run_git(["branch", "--show-current"], cwd=repo_root).stdout.strip()


def head_for(repo_root: Path) -> str:
    return run_git(["rev-parse", "HEAD"], cwd=repo_root).stdout.strip()


def verify_base_is_ancestor(repo_root: Path, base_hash: str) -> None:
    result = run_git(["merge-base", "--is-ancestor", base_hash, "HEAD"], cwd=repo_root, check=False)
    if result.returncode != 0:
        raise AgentOpsError(f"target worktree HEAD does not contain base_ref {base_hash}")


def _require_portable_session_worktree(packet: WorkPacket) -> None:
    if packet.session_entry is not None:
        if packet.worktree != Path("."):
            raise AgentOpsError('session_entry packets require portable worktree "."')


def _packet_target(source_root: Path, packet: WorkPacket) -> Path:
    _require_portable_session_worktree(packet)
    if packet.session_entry is not None:
        return source_root
    return packet.worktree.expanduser().resolve()


def prepare_worktree(source_root: Path, packet: WorkPacket) -> Path:
    base_hash = resolve_base_ref(source_root, packet.base_ref)
    worktree = _packet_target(source_root, packet)
    if worktree.exists():
        target_root = repo_root_from(worktree)
        if target_root != worktree:
            raise AgentOpsError(f"worktree path is not a repo root: {worktree}")
        actual_branch = branch_for(target_root)
        if actual_branch != packet.branch:
            raise AgentOpsError(f"worktree branch expected {packet.branch}, got {actual_branch}")
        verify_base_is_ancestor(target_root, base_hash)
        return target_root

    worktree.parent.mkdir(parents=True, exist_ok=True)
    result = run_git(
        ["worktree", "add", "-b", packet.branch, str(worktree), packet.base_ref],
        cwd=source_root,
        check=False,
    )
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip()
        raise AgentOpsError(f"could not create worktree {worktree}: {detail}")
    target_root = repo_root_from(worktree)
    if branch_for(target_root) != packet.branch:
        raise AgentOpsError(f"created worktree is not on expected branch {packet.branch}")
    return target_root


def _parse_active_tracks_document(text: str, *, source: str) -> list[dict[str, Any]]:
    try:
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            import yaml  # type: ignore[import-not-found]

            try:
                data = yaml.safe_load(text)
            except Exception as exc:
                raise AgentOpsError(f"invalid YAML work packet: {exc}") from exc
    except Exception as exc:
        # PyYAML exposes parser/scanner errors outside ValueError. Keep the
        # owner-policy boundary fail-closed without leaking parser tracebacks.
        raise AgentOpsError(
            f"cannot parse active-track owner config {source}: {exc}"
        ) from exc
    rows = data.get("active_tracks") if isinstance(data, dict) else None
    if not isinstance(rows, list):
        raise AgentOpsError("ACTIVE_TRACK.yaml active_tracks must be a list")
    result: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            raise AgentOpsError(f"ACTIVE_TRACK.yaml row {index} must be an object")
        track_id = row.get("id")
        status_value = row.get("status")
        owner = row.get("owner")
        surfaces = row.get("owned_surfaces")
        if not isinstance(track_id, str) or not track_id.strip():
            raise AgentOpsError(f"ACTIVE_TRACK.yaml row {index} has invalid id")
        if track_id in seen_ids:
            raise AgentOpsError(f"ACTIVE_TRACK.yaml contains duplicate id: {track_id}")
        if not isinstance(status_value, str) or not status_value.strip():
            raise AgentOpsError(f"ACTIVE_TRACK.yaml {track_id} has invalid status")
        if not isinstance(owner, str) or not owner.strip():
            raise AgentOpsError(f"ACTIVE_TRACK.yaml {track_id} has invalid owner")
        if not isinstance(surfaces, list) or not surfaces or not all(
            isinstance(surface, str) and surface.strip() for surface in surfaces
        ):
            raise AgentOpsError(
                f"ACTIVE_TRACK.yaml {track_id} has invalid owned_surfaces"
            )
        if len(set(surfaces)) != len(surfaces):
            raise AgentOpsError(
                f"ACTIVE_TRACK.yaml {track_id} repeats an owned surface"
            )
        seen_ids.add(track_id)
        result.append(dict(row))
    return result


def _active_tracks(repo_root: Path) -> list[dict[str, Any]]:
    path = repo_root / "docs/governance/ACTIVE_TRACK.yaml"
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise AgentOpsError(f"cannot read active-track owner config: {exc}") from exc
    return _parse_active_tracks_document(text, source=str(path))


def _validate_session_envelope(
    repo_root: Path,
    packet_path: Path,
    packet: WorkPacket,
    *,
    inspect: bool,
    require_tracked_copy: bool,
    candidate_bytes: bytes | None = None,
    allow_tracked_input: bool = False,
    scope_base_ref: str | None = None,
) -> str:
    entry = packet.session_entry
    if entry is None:
        return "not_session_entry"
    _require_portable_session_worktree(packet)
    if inspect == require_tracked_copy:
        raise AgentOpsError(
            "internal session envelope mode must choose either inspect or tracked custody"
        )
    candidate = _read_packet_bytes(packet_path) if candidate_bytes is None else candidate_bytes
    if _read_packet_bytes(packet_path) != candidate:
        raise AgentOpsError("external Session Entry Packet changed during validation")
    tracked = repo_root / "reports/agentops/work_packets" / f"{packet.id}.json"
    packet_raw = packet_path.expanduser()
    packet_lexical = (
        packet_raw if packet_raw.is_absolute() else Path(os.path.abspath(packet_raw))
    )
    canonical = tracked.resolve(strict=False)
    is_canonical_tracked_input = (
        allow_tracked_input
        and packet_lexical == canonical
        and packet_raw.resolve(strict=False) == canonical
    )
    if not is_canonical_tracked_input:
        _validate_external_packet_path(repo_root, packet_path)
    base_hash = resolve_base_ref(repo_root, packet.base_ref)
    if packet.base_ref != base_hash:
        raise AgentOpsError("session_entry base_ref must be the exact 40-character HEAD SHA")
    if entry.collision.checked_at_sha != base_hash:
        raise AgentOpsError("session_entry.collision.checked_at_sha must equal base_ref")
    for tool, declared in sorted(entry.tool_versions.items()):
        actual = _probe_tool_version(tool, repo_root)
        if declared != actual:
            raise AgentOpsError(
                f"session_entry tool version mismatch for {tool}: "
                f"declared {declared}, actual {actual}"
            )
    selected = next((row for row in _active_tracks(repo_root) if row.get("id") == entry.active_track), None)
    if not _has_live_track_authority(selected):
        raise AgentOpsError(
            "session_entry active_track is not ACTIVE or SHIPPABLE: "
            f"{entry.active_track}"
        )
    if selected.get("owner") != entry.owner:
        raise AgentOpsError("session_entry owner does not match ACTIVE_TRACK.yaml")
    siblings = {
        str(row.get("id")): [str(value) for value in row.get("owned_surfaces") or []]
        for row in _active_tracks(repo_root)
        if row.get("id") != entry.active_track
    }
    live_scope = inspect_scope(repo_root, packet, base_ref=scope_base_ref)
    # forbidden_files completeness is owed only for sibling patterns that match
    # a path this session actually changes, mirroring the CI checker
    # (check_agentops_packet_scope._validate_track_binding). Ownership safety
    # for touched paths stays with detect_surface_collisions below, which
    # grades the real paths against live sibling ownership regardless of the
    # packet's declaration; demanding the full sibling union forced a packet
    # re-bind whenever an unrelated surface entered the portfolio after
    # base_ref (campaign item 2b follow-up, Codex P2 on #1052).
    required_forbidden = {
        pattern
        for patterns in siblings.values()
        for pattern in patterns
        if any(matching_patterns(path, [pattern]) for path in live_scope.changed_files)
    }
    missing = sorted(required_forbidden - set(packet.forbidden_files))
    if missing:
        raise AgentOpsError(f"forbidden_files omit sibling owned surfaces: {missing}")
    actual = sorted(
        set(
            git_nul_records(repo_root, ["ls-files", "-z"])
            + live_scope.changed_files
        )
    )
    _validate_observed_git_paths(actual)
    collisions = detect_surface_collisions(
        allowed_patterns=packet.allowed_files,
        sibling_patterns=siblings,
        actual_paths=actual,
    )
    if collisions:
        raise AgentOpsError(f"session_entry ownership collision: {collisions}")
    if entry.collision.status != "clear" or entry.collision.details:
        raise AgentOpsError("session_entry collision declaration disagrees with recomputation")
    relative = tracked.relative_to(repo_root).as_posix()
    if relative not in packet.allowed_files:
        raise AgentOpsError(
            f"allowed_files must name the exact canonical tracked packet path: {relative}"
        )
    forbidden = matching_patterns(relative, packet.forbidden_files)
    if forbidden:
        raise AgentOpsError(
            f"canonical tracked packet path is forbidden by packet envelope: {forbidden}"
        )
    if tracked.is_symlink():
        raise AgentOpsError(f"tracked copy must be a regular non-symlink file: {relative}")

    indexed = run_git(
        ["ls-files", "--error-unmatch", "--", relative],
        cwd=repo_root,
        check=False,
    )
    tracked_state = "absent"
    if tracked.exists():
        if not tracked.is_file():
            raise AgentOpsError(f"tracked copy must be a regular file: {relative}")
        if indexed.returncode != 0:
            raise AgentOpsError(f"existing tracked copy is not in the Git index: {relative}")
        tracked_state = (
            "identical" if tracked.read_bytes() == candidate else "present_nonidentical"
        )

    if require_tracked_copy:
        if tracked_state == "absent":
            raise AgentOpsError(f"tracked copy is missing: {relative}")
        if tracked_state != "identical":
            raise AgentOpsError(
                "tracked copy must be byte-identical to external Session Entry Packet"
            )
        index_flags = git_nul_records(
            repo_root,
            ["--literal-pathspecs", "ls-files", "-v", "-z", "--", relative],
        )
        if len(index_flags) != 1 or not index_flags[0].startswith("H "):
            raise AgentOpsError(
                f"tracked packet custody rejects hidden or special index flags: {relative}"
            )
        index_rows = git_nul_records(
            repo_root,
            [
                "--literal-pathspecs", "ls-files", "--stage", "-z", "--",
                relative,
            ],
        )
        if len(index_rows) != 1:
            raise AgentOpsError(f"tracked packet has ambiguous Git index custody: {relative}")
        index_fields = index_rows[0].split(maxsplit=3)
        if len(index_fields) != 4 or index_fields[0] != "100644" or index_fields[2] != "0":
            raise AgentOpsError(f"tracked packet is not a regular stage-0 index blob: {relative}")
        if index_fields[1] != git_object_id_for_bytes(repo_root, candidate):
            raise AgentOpsError(
                f"tracked packet custody must be staged byte-identically in the Git index: {relative}"
            )
    if inspect:
        if head_for(repo_root) != base_hash:
            raise AgentOpsError("inspect requires exact HEAD == packet.base_ref")
        if branch_for(repo_root) != packet.branch:
            raise AgentOpsError("inspect branch does not match packet.branch")
        if live_scope.changed_files:
            raise AgentOpsError("inspect requires an exact clean HEAD")
    if _read_packet_bytes(packet_path) != candidate:
        raise AgentOpsError("external Session Entry Packet changed during validation")
    return tracked_state


def trim_output(output: str, max_chars: int) -> str:
    if len(output) <= max_chars:
        return output
    omitted = len(output) - max_chars
    return f"{output[:max_chars]}\n...[truncated {omitted} chars]"


def _jail_path(jail: Path, absolute: Path) -> Path:
    return jail / absolute.as_posix().lstrip("/")


def _copy_file_into_jail(source: Path, jail: Path, lexical: Path | None = None) -> None:
    target = _jail_path(jail, lexical or source)
    if target.exists():
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source.resolve(), target)


def _copy_elf_dependencies(source: Path, jail: Path) -> None:
    result = run_command(
        [_trusted_host_tool("ldd"), str(source.resolve())], cwd=source.parent
    )
    if result.returncode != 0:
        return
    for line in result.stdout.splitlines():
        match = re.search(r"(?:=>\s+)?(/[^\s()]+)", line)
        if match:
            dependency = Path(match.group(1))
            if dependency.is_file():
                _copy_file_into_jail(dependency, jail)


def _copy_executable_into_jail(command: str, jail: Path) -> None:
    lexical = Path(command).expanduser()
    if not lexical.is_absolute():
        resolved = shutil.which(command, path=_TRUSTED_HOST_PATH)
        if resolved is None:
            raise AgentOpsError(f"negative-control executable is unavailable: {command}")
        lexical = Path(resolved)
    if not lexical.exists():
        raise AgentOpsError(f"negative-control executable is unavailable: {command}")
    _copy_file_into_jail(lexical.resolve(), jail, lexical)
    _copy_elf_dependencies(lexical.resolve(), jail)


def _copy_python_runtime(jail: Path) -> None:
    executable = Path(getattr(sys, "_base_executable", sys.executable))
    _copy_executable_into_jail(str(executable), jail)
    stdlib = Path(sysconfig.get_path("stdlib")).resolve()
    target = _jail_path(jail, stdlib)
    shutil.copytree(
        stdlib,
        target,
        symlinks=False,
        dirs_exist_ok=True,
        ignore=shutil.ignore_patterns("site-packages", "__pycache__", "*.pyc"),
    )
    for extension in stdlib.rglob("*.so"):
        _copy_elf_dependencies(extension, jail)


def _copy_pythonpath_entry(
    raw: str, *, repo_root: Path, fixture: Path, jail: Path,
    index: int, jailed: bool,
) -> str:
    if raw in {"", "."}:
        return "/fixture" if jailed else str(fixture)
    candidate = Path(raw).expanduser()
    if candidate.is_absolute():
        source = candidate.resolve(strict=False)
    else:
        copied = (fixture / candidate).resolve(strict=False)
        if copied.exists():
            relative = copied.relative_to(fixture.resolve()).as_posix()
            return f"/fixture/{relative}" if jailed else str(copied)
        choices = (Path.cwd() / candidate, REPO_ROOT / candidate, repo_root / candidate)
        source = next(
            (choice.resolve(strict=False) for choice in choices if choice.exists()),
            (repo_root / candidate).resolve(strict=False),
        )
    if os.environ.get("DHARMA_AGENTOPS_JAILED") == "1" and source == Path("/fixture"):
        return "/fixture"
    if source == repo_root.resolve():
        return "/fixture" if jailed else str(fixture)
    if _is_within(source, repo_root.resolve()):
        copied = fixture / source.relative_to(repo_root.resolve())
        if copied.exists():
            relative = copied.relative_to(fixture.resolve()).as_posix()
            return f"/fixture/{relative}" if jailed else str(copied)
    if not source.exists():
        return f"/missing/{index}" if jailed else str(fixture / ".missing" / str(index))
    if not jailed:
        return str(source)
    target = jail / "deps" / str(index)
    if source.is_dir():
        shutil.copytree(source, target, symlinks=False, dirs_exist_ok=True)
        if os.environ.get("DHARMA_AGENTOPS_JAILED") != "1":
            for pattern in ("pydantic_core/*.so", "yaml/*.so"):
                for extension in source.glob(pattern):
                    _copy_elf_dependencies(extension, jail)
    else:
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        if source.suffix == ".so":
            _copy_elf_dependencies(source, jail)
    return f"/deps/{index}"


def _negative_environment(
    repo_root: Path, fixture: Path, jail: Path, declared: dict[str, str], *,
    jailed: bool,
) -> dict[str, str]:
    safe = {
        "PATH": (
            f"{Path(getattr(sys, '_base_executable', sys.executable)).parent}:"
            f"{_TRUSTED_HOST_PATH}"
        ),
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
        "TZ": "UTC",
    }
    home, tmp, pycache = fixture / ".home", fixture / ".tmp", fixture / ".pycache"
    for path in (home, tmp, pycache):
        path.mkdir(parents=True, exist_ok=True)
    def inside(path: Path) -> str:
        relative = path.relative_to(fixture).as_posix()
        return f"/fixture/{relative}" if jailed else str(path)
    safe.update({
        "HOME": inside(home),
        "TMPDIR": inside(tmp),
        "PWD": "/fixture" if jailed else str(fixture),
        "OLDPWD": "/fixture" if jailed else str(fixture),
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONPYCACHEPREFIX": inside(pycache),
        "PYTHONNOUSERSITE": "1",
        "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1",
        "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_ATTR_NOSYSTEM": "1",
        "GIT_NO_REPLACE_OBJECTS": "1",
        "GIT_OPTIONAL_LOCKS": "0",
    })
    if jailed:
        safe["DHARMA_AGENTOPS_JAILED"] = "1"
    pythonpath = declared.get("PYTHONPATH", "")
    entries = [
        _copy_pythonpath_entry(
            item, repo_root=repo_root, fixture=fixture, jail=jail,
            index=index, jailed=jailed,
        )
        for index, item in enumerate(pythonpath.split(os.pathsep))
    ]
    safe["PYTHONPATH"] = os.pathsep.join(entries)
    for key, value in declared.items():
        if not key or "=" in key or "\x00" in key or "\x00" in value:
            raise AgentOpsError(
                "negative-control env keys must be non-empty names without '=' or NUL"
            )
        upper = key.upper()
        if upper == "PYTHONPATH":
            continue
        if upper in {
            "GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_OBJECT_DIRECTORY",
            "GIT_ALTERNATE_OBJECT_DIRECTORIES", "HOME", "OLDPWD", "PWD", "TMPDIR",
            "TEMP", "TMP", "VIRTUAL_ENV", "PATH", "PATHEXT", "BASH_ENV", "ENV",
        } or upper.startswith(("GIT_", "LD_", "DYLD_", "PYTHON", "PYTEST", "MAKE")):
            raise AgentOpsError(f"negative-control env may not override {key}")
        if str(repo_root.resolve()) in value:
            raise AgentOpsError(f"negative-control env {key} points into source")
        safe[key] = value
    return safe


def _environment_argv(env: dict[str, str]) -> list[str]:
    assignments: list[str] = []
    for key, value in sorted(env.items()):
        if not key or "=" in key or "\x00" in key or "\x00" in value:
            raise AgentOpsError("negative-control environment cannot be encoded safely")
        assignments.append(f"{key}={value}")
    return assignments


def _negative_confinement(
    jail: Path, fixture: Path
) -> tuple[Callable[[], None] | None, list[str], bool, bool]:
    if sys.platform == "darwin":
        try:
            sandbox_exec = _trusted_host_tool("sandbox-exec")
        except AgentOpsError as exc:
            raise AgentOpsError(
                "negative-control write confinement is unavailable"
            ) from exc
        escaped = str(fixture.resolve()).replace("\\", "\\\\").replace('"', '\\"')
        profile = (
            '(version 1) (allow default) (deny file-write*) '
            f'(allow file-write* (subpath "{escaped}") (literal "/dev/null"))'
        )
        return None, [sandbox_exec, "-p", profile, "--"], False, False
    if sys.platform != "linux":
        raise AgentOpsError("negative-control write confinement is unavailable")
    if os.geteuid() == 0:
        def enter_jail() -> None:
            os.chroot(jail)
            os.chdir("/fixture")
            os.umask(0o077)
        return enter_jail, [], True, False
    unshare = shutil.which("unshare", path=_TRUSTED_HOST_PATH)
    chroot = shutil.which("chroot", path=_TRUSTED_HOST_PATH)
    if unshare and chroot:
        probe = run_command(
            [unshare, "--user", "--map-root-user", "true"],
            cwd=fixture,
            env={"PATH": _TRUSTED_HOST_PATH},
        )
        if probe.returncode == 0:
            prefix = [
                unshare, "--user", "--map-root-user", "--", chroot, str(jail),
                "/bin/sh", "-c", 'cd /fixture && exec "$@"', "agentops",
            ]
            return None, prefix, True, False
    sudo = shutil.which("sudo", path=_TRUSTED_HOST_PATH)
    env_executable = shutil.which("env", path=_TRUSTED_HOST_PATH)
    uid, gid = os.getuid(), os.getgid()
    if sudo and chroot and env_executable and uid > 0 and gid > 0:
        trusted_host_env = {"PATH": _TRUSTED_HOST_PATH}
        probe = run_command(
            [sudo, "-n", "--", chroot, "--version"],
            cwd=fixture,
            env=trusted_host_env,
        )
        if probe.returncode == 0:
            prefix = [
                sudo,
                "-n",
                "--",
                chroot,
                f"--userspec={uid}:{gid}",
                f"--groups={gid}",
                str(jail),
                env_executable,
                "-i",
                "--",
            ]
            return None, prefix, True, True
    raise AgentOpsError(
        "negative controls require root chroot, unprivileged user namespaces, "
        "passwordless sudo chroot with a uid/gid drop, or macOS sandbox-exec; "
        "confinement is unavailable"
    )


def _prepare_jail(jail: Path, gate: GateSpec) -> None:
    if os.environ.get("DHARMA_AGENTOPS_JAILED") == "1":
        for root in (Path("/lib"), Path("/lib64"), Path("/usr/lib")):
            if root.exists():
                shutil.copytree(
                    root, _jail_path(jail, root), symlinks=False, dirs_exist_ok=True
                )
    _copy_python_runtime(jail)
    executables = {gate.argv[0], "python3", "git", "ldd", "/bin/bash", "/bin/sh"}
    trusted_env = shutil.which("env", path=_TRUSTED_HOST_PATH)
    if trusted_env:
        executables.add(trusted_env)
    for executable in executables:
        _copy_executable_into_jail(executable, jail)
    dev = jail / "dev"
    dev.mkdir(parents=True, exist_ok=True)
    (dev / "null").touch()
    inherited_entropy = Path("/dev/urandom")
    entropy = (
        inherited_entropy.read_bytes()
        if os.environ.get("DHARMA_AGENTOPS_JAILED") == "1"
        and inherited_entropy.is_file()
        else os.urandom(1024 * 1024)
    )
    (dev / "urandom").write_bytes(entropy)
    (dev / "random").write_bytes(entropy)


def _reject_fixture_symlink_escapes(fixture: Path) -> None:
    root = fixture.resolve()
    for path in fixture.rglob("*"):
        if path.is_symlink() and not _is_within(path.resolve(strict=False), root):
            raise AgentOpsError(f"negative-control fixture symlink escapes isolation: {path}")


def _trusted_host_tool(name: str) -> str:
    resolved = shutil.which(name, path=_TRUSTED_HOST_PATH)
    if resolved is None:
        raise AgentOpsError(f"trusted host executable is unavailable: {name}")
    path = Path(resolved).resolve()
    if not path.is_file():
        raise AgentOpsError(f"trusted host executable is not a file: {name}")
    return str(path)


def _trusted_gate_interpreter(repo_root: Path) -> str:
    raw = sys.executable
    if not re.fullmatch(r"/[A-Za-z0-9_./+-]+", raw):
        raise AgentOpsError(
            "gate interpreter must be an absolute Make-safe executable path"
        )
    lexical = Path(raw)
    try:
        resolved = lexical.resolve(strict=True)
    except OSError as exc:
        raise AgentOpsError(f"gate interpreter is unavailable: {raw}") from exc
    if not resolved.is_file():
        raise AgentOpsError(f"gate interpreter is not a regular file: {raw}")
    for boundary in {repo_root.resolve(), *_git_admin_roots(repo_root)}:
        if _is_within(lexical, boundary) or _is_within(resolved, boundary):
            raise AgentOpsError(
                "gate interpreter must be external to source and Git state"
            )
    return raw


def _trusted_positive_gate_argv(argv: list[str], *, repo_root: Path) -> list[str]:
    result = list(argv)
    interpreter = _trusted_gate_interpreter(repo_root)
    if _is_trusted_python(result[0]):
        # Preserve the lexical venv executable.  Resolving this symlink to the
        # base interpreter drops the venv's installed gate dependencies.
        result[0] = interpreter
    elif _is_trusted_git(result[0]):
        git_args = result[1:]
        if git_args[:1] == ["diff"]:
            git_args[1:1] = ["--no-ext-diff", "--no-textconv"]
        result = [
            _trusted_host_tool("git"),
            "-c", "core.fsmonitor=false",
            "-c", f"core.hooksPath={os.devnull}",
            *git_args,
        ]
    elif result[0] == "make":
        result[0] = _trusted_host_tool("make")
        result.extend(
            [
                f"AGENTOPS_PYTHON={interpreter}",
                f"PYTHON={interpreter}",
                f"VENV_PYTHON={interpreter}",
                f"PYTEST={interpreter} -m pytest",
                f"REPO_PYTHON=PYTHONPATH=. {interpreter}",
            ]
        )
    else:
        # Admission and execution are intentionally separate checks.  Never
        # fall through to a packet path if the executable identity changed in
        # between (for example through a mutable argv or swapped alias).
        raise AgentOpsError(
            f"gate executable lost trusted identity before execution: {result[0]}"
        )
    return result


def _bounded_gate(gate: GateSpec, *, deadline: float) -> GateSpec:
    remaining = int(deadline - time.monotonic())
    if remaining <= 0:
        raise AgentOpsError(
            f"AgentOps aggregate gate timeout exceeded {_MAX_ADMISSION_TIMEOUT_SECONDS}s"
        )
    return replace(
        gate,
        timeout_seconds=min(
            gate.timeout_seconds,
            _MAX_GATE_TIMEOUT_SECONDS,
            remaining,
        ),
    )


def run_gate(
    repo_root: Path,
    gate: GateSpec,
    *,
    base_env: dict[str, str] | None = None,
    preexec_fn: Callable[[], None] | None = None,
    argv_prefix: list[str] | None = None,
    normalize_positive_executable: bool = False,
) -> dict[str, Any]:
    started = time.monotonic()
    inherited = os.environ if base_env is None else base_env
    env = build_gate_environment(gate, inherited)
    if _is_trusted_git(gate.argv[0]):
        # The dependency-light contract strips hostile inherited Git state;
        # the packet runner additionally requires actual object identities for
        # every direct Git gate, never repository-local replace refs or
        # implicit user/system ignore and attribute state.
        env["HOME"] = os.devnull
        env["XDG_CONFIG_HOME"] = os.devnull
        env["GIT_CONFIG_GLOBAL"] = os.devnull
        env["GIT_CONFIG_NOSYSTEM"] = "1"
        env["GIT_ATTR_NOSYSTEM"] = "1"
        env["GIT_NO_REPLACE_OBJECTS"] = "1"
        env["GIT_OPTIONAL_LOCKS"] = "0"
    try:
        gate_argv = (
            _trusted_positive_gate_argv(gate.argv, repo_root=repo_root)
            if normalize_positive_executable
            else gate.argv
        )
        result = run_command(
            [*(argv_prefix or []), *gate_argv],
            cwd=repo_root,
            env=env,
            timeout_seconds=gate.timeout_seconds,
            preexec_fn=preexec_fn,
        )
        exit_code = result.returncode
        combined_output = result.stdout
        if result.stderr:
            combined_output += result.stderr
        timed_out = False
    except subprocess.TimeoutExpired as exc:
        exit_code = 124
        timed_out = True
        stdout = exc.stdout if isinstance(exc.stdout, str) else ""
        stderr = exc.stderr if isinstance(exc.stderr, str) else ""
        combined_output = f"{stdout}{stderr}\ncommand timed out after {gate.timeout_seconds}s"

    return {
        "name": gate.name,
        "command": gate.command,
        "expected_exit": gate.expected_exit,
        "exit_code": exit_code,
        "passed": not timed_out and exit_code == gate.expected_exit,
        "timed_out": timed_out,
        "duration_seconds": round(time.monotonic() - started, 3),
        "output": trim_output(combined_output, gate.max_output_chars),
    }


_PYTHON_SETUP_FAILURE = re.compile(
    r"(?m)^(?:\S*python[\w.]*: No module named \S+"
    r"|ModuleNotFoundError: No module named .+"
    r"|ImportError: .+)\s*$"
)


def _python_module_target(argv: list[str]) -> str | None:
    """Top-level module of a ``python -m <module>`` control, if unambiguous.

    Only the plain ``python [-m] module`` spelling is recognized; any other
    interpreter option before ``-m`` skips the probe and leaves detection to
    the post-run setup-failure guard.
    """
    if len(argv) >= 3 and argv[1] == "-m":
        top = argv[2].split(".", 1)[0]
        if top.isidentifier():
            return top
    return None


def run_negative_control(
    repo_root: Path,
    gate: GateSpec,
    *,
    temp_root: Path,
) -> dict[str, Any]:
    ignored_names = {".git", ".venv", "node_modules", "__pycache__", ".pytest_cache"}
    ignored = shutil.ignore_patterns(*ignored_names)
    temp_root = resolve_external_dir(
        temp_root, repo_root=repo_root, field="negative-control temp root"
    )
    if not temp_root.is_dir():
        raise AgentOpsError(f"negative-control temp root is not a directory: {temp_root}")
    with tempfile.TemporaryDirectory(
        prefix="dharma-agentops-negative-", dir=temp_root
    ) as raw:
        jail = Path(raw) / "jail"
        fixture = jail / "fixture"
        fixture.parent.mkdir(parents=True)
        source_git = repo_root / ".git"
        if source_git.is_dir():
            fixture.mkdir()
            shutil.copytree(source_git, fixture / ".git", symlinks=False)
        else:
            clone = run_command(
                [_trusted_host_tool("git"), "-c", "core.fsmonitor=false", "clone",
                 "--no-checkout", "--no-hardlinks", str(repo_root), str(fixture)],
                cwd=repo_root,
                env=trusted_git_environment(),
            )
            if clone.returncode != 0:
                detail = (clone.stderr or clone.stdout).strip()
                raise AgentOpsError(
                    f"could not isolate negative-control git metadata: {detail}"
                )
        for source in repo_root.iterdir():
            if source.name in ignored_names:
                continue
            target = fixture / source.name
            if source.is_dir():
                shutil.copytree(source, target, ignore=ignored, symlinks=True, dirs_exist_ok=True)
            else:
                shutil.copy2(source, target, follow_symlinks=False)
        _reject_fixture_symlink_escapes(fixture)
        control_gate = gate
        if _is_trusted_python(gate.argv[0]):
            control_gate = replace(
                gate,
                argv=[
                    str(
                        Path(
                            getattr(sys, "_base_executable", sys.executable)
                        ).resolve()
                    ),
                    *gate.argv[1:],
                ],
            )
        preexec_fn, argv_prefix, jailed, env_via_argv = _negative_confinement(
            jail, fixture
        )
        control_env = _negative_environment(
            repo_root, fixture, jail, control_gate.env, jailed=jailed
        )
        if jailed:
            _prepare_jail(jail, control_gate)
        host_env = control_env
        if env_via_argv:
            control_env = build_gate_environment(
                replace(control_gate, env={}), control_env
            )
            if _is_trusted_git(control_gate.argv[0]):
                control_env["HOME"] = os.devnull
                control_env["XDG_CONFIG_HOME"] = os.devnull
                control_env["GIT_CONFIG_GLOBAL"] = os.devnull
                control_env["GIT_CONFIG_NOSYSTEM"] = "1"
                control_env["GIT_ATTR_NOSYSTEM"] = "1"
                control_env["GIT_NO_REPLACE_OBJECTS"] = "1"
                control_env["GIT_OPTIONAL_LOCKS"] = "0"
            argv_prefix = [
                *argv_prefix,
                *_environment_argv(control_env),
                "/bin/sh",
                "-c",
                'cd /fixture && exec "$@"',
                "agentops",
            ]
            host_env = {"PATH": _TRUSTED_HOST_PATH}
        python_control = _is_trusted_python(gate.argv[0])
        probe_module = (
            _python_module_target(control_gate.argv) if python_control else None
        )
        if probe_module is not None:
            # A `python -m <module>` control whose module is missing in the
            # jail exits 1 from the interpreter bootstrap without running at
            # all; that collides with an expected non-zero exit and would be
            # recorded as a hollow PASS. Prove the module imports under the
            # identical confinement before trusting the control's exit code.
            probe = replace(
                control_gate,
                name=f"{gate.name}::import-probe",
                command=f"import probe for module {probe_module}",
                argv=[control_gate.argv[0], "-c", f"import {probe_module}"],
                expected_exit=0,
                env={},
            )
            probe_result = run_gate(
                fixture,
                probe,
                base_env=host_env,
                preexec_fn=preexec_fn,
                argv_prefix=argv_prefix,
            )
            if not probe_result["passed"]:
                raise AgentOpsError(
                    f"negative control {gate.name!r} depends on module "
                    f"{probe_module!r} which is not importable in the jail; "
                    "a missing-tool exit would collide with the expected "
                    f"exit {gate.expected_exit} and pass without running "
                    f"(probe output: {probe_result['output'].strip()!r})"
                )
        result = run_gate(
            fixture,
            replace(control_gate, env={}),
            base_env=host_env,
            preexec_fn=preexec_fn,
            argv_prefix=argv_prefix,
        )
        if (
            python_control
            and result["passed"]
            and gate.expected_exit != 0
            and _PYTHON_SETUP_FAILURE.search(result["output"])
        ):
            raise AgentOpsError(
                f"negative control {gate.name!r} exited {result['exit_code']} "
                "on a setup/import failure instead of running its detection "
                "logic; refusing to count the exit-code collision as PASSED. "
                "Map setup failures to a distinct exit code (see the "
                "WP-SCOPEBASE2 reference control)"
            )
        return result


def timestamp_slug(now: datetime | None = None) -> str:
    value = now or datetime.now(timezone.utc)
    return value.strftime("%Y%m%dT%H%M%S%fZ")


def report_paths(repo_root: Path, job_id: str, timestamp: str) -> tuple[Path, Path]:
    report_dir = repo_root / REPORT_ROOT / job_id / timestamp
    return report_dir / "report.json", report_dir / "report.md"


def _darwin_account_temp_root() -> Path:
    """Resolve the OS-account temp root without trusting ``TMPDIR``.

    Darwin's ``getconf DARWIN_USER_TEMP_DIR`` reads the account-scoped value
    from the operating system.  Invoke the fixed host tool under a minimal
    environment so a caller cannot redirect report-root admission through an
    inherited temporary-directory variable or executable search path.
    """

    getconf = _trusted_host_tool("getconf")
    try:
        result = run_command(
            [getconf, "DARWIN_USER_TEMP_DIR"],
            cwd=Path("/"),
            env={"PATH": _TRUSTED_HOST_PATH, "LANG": "C", "LC_ALL": "C"},
            timeout_seconds=5,
        )
    except (OSError, subprocess.SubprocessError, UnicodeError) as exc:
        raise AgentOpsError("cannot resolve trusted Darwin account temp root") from exc
    lines = result.stdout.splitlines()
    if result.returncode != 0 or len(lines) != 1:
        detail = (result.stderr or result.stdout).strip()
        raise AgentOpsError(
            f"cannot resolve trusted Darwin account temp root: {detail or 'invalid output'}"
        )
    raw = lines[0].strip()
    if not raw or raw != lines[0] or "\x00" in raw or not Path(raw).is_absolute():
        raise AgentOpsError("trusted Darwin account temp root is not an absolute path")
    try:
        root = Path(raw).resolve(strict=True)
        parent = _DARWIN_USER_TEMP_PARENT.resolve(strict=True)
    except OSError as exc:
        raise AgentOpsError("trusted Darwin account temp root is unavailable") from exc
    try:
        relative = root.relative_to(parent)
    except ValueError as exc:
        raise AgentOpsError(
            "trusted Darwin account temp root escapes /private/var/folders"
        ) from exc
    if (
        len(relative.parts) != 3
        or len(relative.parts[0]) != 2
        or re.fullmatch(r"[A-Za-z0-9_]+", relative.parts[1]) is None
        or relative.parts[2] != "T"
    ):
        raise AgentOpsError("trusted Darwin account temp root has an invalid shape")
    return root


def _private_report_anchor(target: Path) -> tuple[Path, bool]:
    candidates: list[tuple[Path, bool]] = []
    if os.name == "posix":
        candidates.append((Path("/tmp").resolve(), True))
    else:  # pragma: no cover - Windows fallback
        candidates.append((Path(tempfile.gettempdir()).resolve(), True))
    try:
        candidates.append((_os_account_home(), False))
    except AgentOpsError:
        pass
    matches = [item for item in candidates if _is_within(target, item[0])]
    if matches:
        return max(matches, key=lambda item: len(item[0].parts))
    if os.name == "posix" and sys.platform == "darwin":
        # GitHub/macOS runners use a private per-account root rather than /tmp.
        # Consult it only when the established /tmp and account-home anchors do
        # not already cover the target. Its authority comes from Darwin
        # getconf, never TMPDIR.
        # The fixed parent is only a cheap rejection prefilter; admission still
        # requires the strict OS-account root returned by getconf. This avoids
        # changing the canonical error (or spawning a probe) for unrelated
        # targets such as /opt/reports.
        darwin_parent = _DARWIN_USER_TEMP_PARENT.resolve(strict=False)
        if _is_within(target, darwin_parent):
            account_temp = _darwin_account_temp_root()
            if _is_within(target, account_temp):
                return account_temp, False
    raise AgentOpsError(
        "report_root must be beneath the trusted temp anchor or OS-account home"
    )


def _validate_private_directory(path: Path, *, allow_shared_anchor: bool = False) -> None:
    try:
        metadata = os.lstat(path)
    except OSError as exc:
        raise AgentOpsError(f"cannot inspect report directory {path}: {exc}") from exc
    if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISDIR(metadata.st_mode):
        raise AgentOpsError(f"report directory must be a non-symlink directory: {path}")
    if allow_shared_anchor:
        return
    if metadata.st_uid != os.geteuid():
        raise AgentOpsError(f"report directory is not owned by the current euid: {path}")
    if stat.S_IMODE(metadata.st_mode) & 0o022:
        raise AgentOpsError(f"report directory is group/world writable: {path}")


def _prepare_private_report_root(candidate: Path, *, repo_root: Path) -> Path:
    root = resolve_external_dir(candidate, repo_root=repo_root, field="report_root")
    anchor, shared_anchor = _private_report_anchor(root)
    _validate_private_directory(anchor, allow_shared_anchor=shared_anchor)
    if root == anchor:
        raise AgentOpsError("report_root may not be the shared output anchor itself")
    cursor = anchor
    for part in root.relative_to(anchor).parts:
        cursor = cursor / part
        if cursor.exists() or cursor.is_symlink():
            _validate_private_directory(cursor)
        else:
            try:
                cursor.mkdir(mode=0o700)
            except OSError as exc:
                raise AgentOpsError(
                    f"cannot create private report directory {cursor}: {exc}"
                ) from exc
            _validate_private_directory(cursor)
    try:
        root.chmod(0o700)
    except OSError as exc:
        raise AgentOpsError(f"cannot secure report_root {root}: {exc}") from exc
    return root


def _prepare_private_report_children(
    report_root: Path,
    children: list[str],
    *,
    repo_root: Path,
) -> list[Path]:
    """Create and verify declared relative output/cache roots in one pass."""
    prepared: list[Path] = []
    for child in children:
        if (
            not child
            or child.startswith("/")
            or "\\" in child
            or not _SAFE_GATE_TARGET.fullmatch(child)
            or any(part in {"", ".", ".."} for part in child.split("/"))
        ):
            raise AgentOpsError(
                f"report child must be a safe relative path beneath report_root: {child}"
            )
        destination = report_root.joinpath(*child.split("/"))
        sentinel = destination / ".agentops-report-child-boundary"
        # Validate the lexical chain before creating anything.  This rejects
        # an existing child symlink even when it resolves back into the source
        # checkout (or to a different location under the report root).
        _validate_report_destination(report_root, sentinel, repo_root)
        _ensure_private_report_directory(report_root, destination)
        _validate_report_destination(report_root, sentinel, repo_root)
        prepared.append(destination)
    return prepared


def _ensure_private_report_directory(report_root: Path, directory: Path) -> None:
    root = report_root.resolve()
    target = directory.resolve(strict=False)
    if not _is_within(target, root):
        raise AgentOpsError(f"report directory escapes report_root: {directory}")
    _validate_private_directory(root)
    cursor = root
    for part in target.relative_to(root).parts:
        cursor = cursor / part
        if cursor.exists() or cursor.is_symlink():
            _validate_private_directory(cursor)
        else:
            try:
                cursor.mkdir(mode=0o700)
            except OSError as exc:
                raise AgentOpsError(
                    f"cannot create private report directory {cursor}: {exc}"
                ) from exc
            _validate_private_directory(cursor)
        try:
            cursor.chmod(0o700)
        except OSError as exc:
            raise AgentOpsError(f"cannot secure report directory {cursor}: {exc}") from exc


def _validate_report_destination(
    report_root: Path, report_path: Path, source_root: Path
) -> None:
    root = report_root.resolve()
    lexical = Path(os.path.abspath(report_path))
    resolved = report_path.resolve(strict=False)
    if not _is_within(lexical, root) or not _is_within(resolved, root):
        raise AgentOpsError(f"report destination escapes external report_root: {report_path}")
    relative_parent = lexical.parent.relative_to(root)
    cursor = root
    for part in relative_parent.parts:
        cursor = cursor / part
        if cursor.is_symlink():
            raise AgentOpsError(f"report destination contains a symlink: {cursor}")
        if cursor.exists():
            _validate_private_directory(cursor)
    if report_path.exists() or report_path.is_symlink():
        try:
            metadata = os.lstat(report_path)
        except OSError as exc:
            raise AgentOpsError(f"cannot inspect report destination {report_path}: {exc}") from exc
        if (
            stat.S_ISLNK(metadata.st_mode)
            or not stat.S_ISREG(metadata.st_mode)
            or metadata.st_uid != os.geteuid()
            or stat.S_IMODE(metadata.st_mode) & 0o022
        ):
            raise AgentOpsError(f"report destination is not a private regular file: {report_path}")
    resolve_external_dir(
        report_path.parent,
        repo_root=source_root,
        field="report destination",
    )


def scope_to_dict(scope: ScopeState) -> dict[str, Any]:
    return {
        "tracked_changed_files": scope.tracked_changed_files,
        "staged_files": scope.staged_files,
        "untracked_files": scope.untracked_files,
        "changed_files": scope.changed_files,
        "violations": scope.violations,
        "passed": scope.passed,
    }


def _open_report_directory_chain(report_root: Path, directory: Path) -> list[int]:
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
    descriptors: list[int] = []
    try:
        descriptors.append(os.open(report_root, flags))
        for part in directory.relative_to(report_root).parts:
            descriptors.append(os.open(part, flags, dir_fd=descriptors[-1]))
        return descriptors
    except (OSError, ValueError) as exc:
        for descriptor in reversed(descriptors):
            os.close(descriptor)
        raise AgentOpsError(
            f"cannot open no-follow report directory chain {directory}: {exc}"
        ) from exc


def _atomic_report_write_at(
    parent_descriptor: int,
    name: str,
    text: str,
    *,
    display_path: Path,
) -> None:
    """Atomically publish one report file through an already-custodied dirfd."""
    if not name or name in {".", ".."} or Path(name).name != name:
        raise AgentOpsError(f"invalid report publication name: {name!r}")
    temporary = f".{name}.{os.getpid()}.{time.time_ns()}.tmp"
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    flags |= getattr(os, "O_NOFOLLOW", 0)
    descriptor: int | None = None
    published = False
    parent_identity = os.fstat(parent_descriptor)
    if (
        parent_identity.st_uid != os.geteuid()
        or not stat.S_ISDIR(parent_identity.st_mode)
        or stat.S_IMODE(parent_identity.st_mode) & 0o022
    ):
        raise AgentOpsError("report parent directory lost private custody")
    try:
        descriptor = os.open(temporary, flags, 0o600, dir_fd=parent_descriptor)
        with os.fdopen(descriptor, "wb") as handle:
            descriptor = None
            handle.write(text.encode("utf-8"))
            handle.flush()
            os.fchmod(handle.fileno(), 0o600)
            os.fsync(handle.fileno())
        os.replace(
            temporary,
            name,
            src_dir_fd=parent_descriptor,
            dst_dir_fd=parent_descriptor,
        )
        published = True
        metadata = os.stat(name, dir_fd=parent_descriptor, follow_symlinks=False)
        if (
            not stat.S_ISREG(metadata.st_mode)
            or stat.S_ISLNK(metadata.st_mode)
            or metadata.st_uid != os.geteuid()
            or stat.S_IMODE(metadata.st_mode) != 0o600
        ):
            raise OSError("published report is not a private current-euid regular file")
        os.fsync(parent_descriptor)
    except (OSError, AgentOpsError) as exc:
        if descriptor is not None:
            os.close(descriptor)
        try:
            os.unlink(temporary, dir_fd=parent_descriptor)
        except FileNotFoundError:
            pass
        except OSError:
            pass
        if published:
            try:
                os.unlink(name, dir_fd=parent_descriptor)
                os.fsync(parent_descriptor)
            except FileNotFoundError:
                pass
            except OSError:
                pass
        raise AgentOpsError(
            f"cannot atomically publish report {display_path}: {exc}"
        ) from exc


def _atomic_report_write(report_root: Path, path: Path, text: str) -> None:
    directory_descriptors = _open_report_directory_chain(report_root, path.parent)
    parent_descriptor = directory_descriptors[-1]
    parent_identity = os.fstat(parent_descriptor)
    published = False
    try:
        _atomic_report_write_at(
            parent_descriptor,
            path.name,
            text,
            display_path=path,
        )
        published = True
        verification = _open_report_directory_chain(report_root, path.parent)
        try:
            verified_identity = os.fstat(verification[-1])
            if (
                verified_identity.st_dev != parent_identity.st_dev
                or verified_identity.st_ino != parent_identity.st_ino
            ):
                raise AgentOpsError(
                    "report directory custody changed during publication"
                )
        finally:
            for item in reversed(verification):
                os.close(item)
    except Exception:
        if published:
            _unlink_report_names(parent_descriptor, (path.name,))
        raise
    finally:
        for item in reversed(directory_descriptors):
            os.close(item)


def _unlink_report_names(parent_descriptor: int, names: Iterable[str]) -> None:
    failures: list[str] = []
    for name in names:
        try:
            os.unlink(name, dir_fd=parent_descriptor)
        except FileNotFoundError:
            continue
        except OSError as exc:
            failures.append(f"{name}: {exc}")
    try:
        os.fsync(parent_descriptor)
    except OSError as exc:
        failures.append(f"directory fsync: {exc}")
    if failures:
        raise AgentOpsError(
            f"cannot invalidate incomplete report pair: {failures}"
        )


def write_report(
    repo_root: Path,
    report: dict[str, Any],
    timestamp: str,
    *,
    source_root: Path | None = None,
    before_json: Callable[[], None] | None = None,
) -> tuple[Path, Path]:
    json_path, md_path = report_paths(repo_root, report["job_id"], timestamp)
    if source_root is not None:
        _validate_report_destination(repo_root, json_path, source_root)
        _validate_report_destination(repo_root, md_path, source_root)
    _ensure_private_report_directory(repo_root, json_path.parent)
    if source_root is not None:
        _validate_report_destination(repo_root, json_path, source_root)
        _validate_report_destination(repo_root, md_path, source_root)
    custody = _open_report_directory_chain(repo_root, json_path.parent)
    parent_descriptor = custody[-1]
    parent_identity = os.fstat(parent_descriptor)
    names = (json_path.name, md_path.name)

    def verify_canonical_parent() -> None:
        verification = _open_report_directory_chain(repo_root, json_path.parent)
        try:
            current = os.fstat(verification[-1])
            if (
                current.st_dev != parent_identity.st_dev
                or current.st_ino != parent_identity.st_ino
            ):
                _unlink_report_names(verification[-1], names)
                raise AgentOpsError(
                    "report directory custody changed during publication"
                )
        finally:
            for descriptor in reversed(verification):
                os.close(descriptor)

    try:
        _atomic_report_write_at(
            parent_descriptor,
            md_path.name,
            render_markdown_report(report),
            display_path=md_path,
        )
        if before_json is not None:
            before_json()
        verify_canonical_parent()
        _atomic_report_write_at(
            parent_descriptor,
            json_path.name,
            json.dumps(report, indent=2, sort_keys=True) + "\n",
            display_path=json_path,
        )
        verify_canonical_parent()
    except Exception as exc:
        try:
            _unlink_report_names(parent_descriptor, names)
        except AgentOpsError as cleanup_exc:
            raise AgentOpsError(
                f"report publication failed and pair invalidation failed: {cleanup_exc}"
            ) from exc
        raise
    finally:
        for descriptor in reversed(custody):
            os.close(descriptor)
    return json_path, md_path


def render_markdown_report(report: dict[str, Any]) -> str:
    lines = [
        f"# AgentOps Report: {report['job_id']}",
        "",
        f"- Status: {report['status']}",
        f"- Base ref: `{report['base_ref']}`",
        f"- Branch: `{report['branch']}`",
        f"- Worktree: `{report['worktree']}`",
        f"- Commit hash: `{report.get('commit_hash') or ''}`",
        "", "## Intent", "", report["intent"], "", "## Scope", "",
        f"- Scope passed: `{report['scope']['passed']}`",
        f"- Changed files: `{len(report['scope']['changed_files'])}`",
        f"- Violations: `{len(report['scope']['violations'])}`",
        "", "## Gates", "", "| Gate | Expected | Actual | Result |", "|---|---:|---:|---|",
    ]
    for gate in report["gates"]:
        result = "PASS" if gate["passed"] else "FAIL"
        lines.append(f"| {gate['name']} | {gate['expected_exit']} | {gate['exit_code']} | {result} |")
    lines.extend(["", "## Negative Controls", "", "| Control | Expected | Actual | Result |",
                  "|---|---:|---:|---|"])
    for control in report.get("negative_controls", []):
        result = "PASS" if control["passed"] else "FAIL"
        lines.append(f"| {control['name']} | {control['expected_exit']} | {control['exit_code']} | {result} |")
    lines.extend(["", "## Final Git Status", "", "```",
                  report.get("final_git_status", "").rstrip(), "```", ""])
    return "\n".join(lines)


def should_commit(report: dict[str, Any], packet: WorkPacket, final_scope: ScopeState) -> tuple[bool, str]:
    if not packet.commit.allowed:
        return False, "commit.allowed is false"
    if packet.approval.before_commit:
        return False, "human approval required before commit"
    if not all(gate["passed"] for gate in report["gates"]):
        return False, "one or more gates failed"
    if not all(control["passed"] for control in report["negative_controls"]):
        return False, "one or more negative controls failed"
    if not final_scope.passed:
        return False, "scope gate failed"
    if not final_scope.changed_files:
        return False, "no changes to commit"
    return True, "commit permitted"


def _open_governed_parent_chain(
    repo_root: Path, relative: str,
) -> tuple[list[int], str] | None:
    """Open every parent component no-follow; return held dirfds + basename."""
    rel_path = Path(relative)
    if (
        rel_path.is_absolute()
        or not rel_path.parts
        or "\\" in relative
        or any(part in {"", ".", ".."} for part in rel_path.parts)
    ):
        raise AgentOpsError(f"governed commit path is not repo-relative: {relative}")
    if not hasattr(os, "O_NOFOLLOW") or not hasattr(os, "O_DIRECTORY"):
        raise AgentOpsError("governed scope requires no-follow file reads")
    flags = (
        os.O_RDONLY
        | os.O_DIRECTORY
        | os.O_NOFOLLOW
        | getattr(os, "O_CLOEXEC", 0)
    )
    descriptors: list[int] = []
    try:
        descriptors.append(os.open(repo_root.resolve(), flags))
        for component in rel_path.parts[:-1]:
            descriptors.append(os.open(component, flags, dir_fd=descriptors[-1]))
    except FileNotFoundError:
        for descriptor in reversed(descriptors):
            os.close(descriptor)
        return None
    except OSError as exc:
        for descriptor in reversed(descriptors):
            os.close(descriptor)
        raise AgentOpsError(
            f"governed commit path has a symlink or non-directory ancestor: "
            f"{relative}: {exc}"
        ) from exc
    return descriptors, rel_path.name


def _read_symlink_worktree_file(repo_root: Path, relative: str) -> bytes | None:
    opened = _open_governed_parent_chain(repo_root, relative)
    if opened is None:
        return None
    descriptors, name = opened
    try:
        try:
            identity = os.stat(
                name, dir_fd=descriptors[-1], follow_symlinks=False
            )
        except FileNotFoundError:
            return None
        except OSError as exc:
            raise AgentOpsError(
                f"cannot inspect governed symlink {relative}: {exc}"
            ) from exc
        if not stat.S_ISLNK(identity.st_mode):
            return None
        try:
            target = os.readlink(name, dir_fd=descriptors[-1])
            current = os.stat(
                name, dir_fd=descriptors[-1], follow_symlinks=False
            )
        except OSError as exc:
            raise AgentOpsError(
                f"cannot read governed symlink {relative}: {exc}"
            ) from exc
        if (
            current.st_dev != identity.st_dev
            or current.st_ino != identity.st_ino
            or not stat.S_ISLNK(current.st_mode)
        ):
            raise AgentOpsError(
                f"governed symlink custody changed during read: {relative}"
            )
        return os.fsencode(target)
    finally:
        for descriptor in reversed(descriptors):
            os.close(descriptor)


def _read_regular_worktree_file(repo_root: Path, relative: str) -> tuple[str, bytes] | None:
    opened = _open_governed_parent_chain(repo_root, relative)
    if opened is None:
        return None
    directory_descriptors, name = opened
    flags = (
        os.O_RDONLY
        | os.O_NOFOLLOW
        | getattr(os, "O_CLOEXEC", 0)
        | getattr(os, "O_NONBLOCK", 0)
    )
    try:
        descriptor = os.open(name, flags, dir_fd=directory_descriptors[-1])
    except FileNotFoundError:
        for item in reversed(directory_descriptors):
            os.close(item)
        return None
    except OSError as exc:
        for item in reversed(directory_descriptors):
            os.close(item)
        raise AgentOpsError(
            f"governed commit path must be a regular non-symlink file: {relative}"
        ) from exc
    try:
        metadata = os.fstat(descriptor)
        if not stat.S_ISREG(metadata.st_mode):
            raise AgentOpsError(
                f"governed commit path must be a regular file: {relative}"
            )
        chunks: list[bytes] = []
        while True:
            chunk = os.read(descriptor, 1024 * 1024)
            if not chunk:
                break
            chunks.append(chunk)
        try:
            current = os.stat(
                name,
                dir_fd=directory_descriptors[-1],
                follow_symlinks=False,
            )
        except OSError as exc:
            raise AgentOpsError(
                f"cannot revalidate governed commit path {relative}: {exc}"
            ) from exc
        if (
            current.st_dev != metadata.st_dev
            or current.st_ino != metadata.st_ino
            or not stat.S_ISREG(current.st_mode)
        ):
            raise AgentOpsError(
                f"governed commit path custody changed during read: {relative}"
            )
    finally:
        os.close(descriptor)
        for item in reversed(directory_descriptors):
            os.close(item)
    mode = "100755" if metadata.st_mode & 0o111 else "100644"
    return mode, b"".join(chunks)


def _core_filemode_enabled(repo_root: Path) -> bool:
    result = run_git(
        ["config", "--bool", "--get", "core.fileMode"],
        cwd=repo_root,
        check=False,
    )
    if result.returncode == 1:
        return True
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip()
        raise AgentOpsError(f"cannot read core.fileMode: {detail}")
    value = result.stdout.strip()
    if value not in {"true", "false"}:
        raise AgentOpsError(f"core.fileMode returned an invalid boolean: {value!r}")
    return value == "true"


def _tracked_regular_index_mode(repo_root: Path, relative: str) -> str | None:
    result = run_git(
        ["ls-files", "--stage", "-z", "--", relative],
        cwd=repo_root,
    )
    rows = [row for row in result.stdout.split("\x00") if row]
    if not rows:
        return None
    if len(rows) != 1:
        raise AgentOpsError(f"governed commit path has ambiguous index stages: {relative}")
    metadata, separator, indexed_path = rows[0].partition("\t")
    fields = metadata.split()
    if (
        not separator
        or indexed_path != relative
        or len(fields) != 3
        or fields[2] != "0"
    ):
        raise AgentOpsError(f"governed commit path has invalid index metadata: {relative}")
    mode = fields[0]
    if mode not in {"100644", "100755"}:
        raise AgentOpsError(
            f"governed commit path has unsupported tracked mode {mode}: {relative}"
        )
    return mode


def _stage_exact_files(repo_root: Path, files: list[str]) -> None:
    """Stage exact worktree bytes without Git clean/process filters."""

    filemode_enabled = _core_filemode_enabled(repo_root)
    for relative in files:
        unmerged = run_git(
            ["-c", "core.fsmonitor=false", "ls-files", "-u", "--", relative],
            cwd=repo_root,
        )
        if unmerged.stdout.strip():
            raise AgentOpsError(f"cannot govern an unmerged index path: {relative}")
        snapshot = _read_regular_worktree_file(repo_root, relative)
        if snapshot is None:
            run_git(
                [
                    "-c", f"core.hooksPath={os.devnull}",
                    "-c", "core.fsmonitor=false", "update-index",
                    "--force-remove", "--", relative,
                ],
                cwd=repo_root,
            )
            continue
        mode, content = snapshot
        if not filemode_enabled:
            mode = _tracked_regular_index_mode(repo_root, relative) or mode
        object_id = git_object_id_for_bytes(repo_root, content, write=True)
        run_git(
            [
                "-c", f"core.hooksPath={os.devnull}",
                "-c", "core.fsmonitor=false", "update-index", "--add",
                "--cacheinfo", mode, object_id, relative,
            ],
            cwd=repo_root,
        )


def create_commit(repo_root: Path, files: list[str], message: str) -> str:
    commit_environment = trusted_git_commit_environment(repo_root)
    parent = head_for(repo_root)
    branch = run_git(
        ["symbolic-ref", "--quiet", "HEAD"], cwd=repo_root, check=False
    )
    branch_ref = branch.stdout.strip()
    if branch.returncode != 0 or not branch_ref.startswith("refs/heads/"):
        raise AgentOpsError("governed commit requires an attached branch HEAD")
    _stage_exact_files(repo_root, files)
    tree = run_git(
        [
            "-c", f"core.hooksPath={os.devnull}",
            "-c", "core.fsmonitor=false", "write-tree",
        ],
        cwd=repo_root,
    ).stdout.strip()
    result = run_command(
        [
            "git", "-c", "commit.gpgSign=false",
            "commit-tree", tree, "-p", parent,
        ],
        cwd=repo_root,
        env=commit_environment,
        input_text=f"{message}\n",
    )
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip()
        raise AgentOpsError(f"git commit-tree failed: {detail}")
    commit_hash = result.stdout.strip()
    if not re.fullmatch(r"[0-9a-f]{40,64}", commit_hash):
        raise AgentOpsError("git commit-tree returned an invalid object id")
    ref_result = run_command(
        [
            "git", "-c", f"core.hooksPath={os.devnull}",
            "-c", "core.logAllRefUpdates=true",
            "update-ref", "-m", message, branch_ref, commit_hash, parent,
        ],
        cwd=repo_root,
        env=commit_environment,
    )
    if ref_result.returncode != 0:
        detail = (ref_result.stderr or ref_result.stdout).strip()
        raise AgentOpsError(f"git update-ref failed: {detail}")
    if head_for(repo_root) != commit_hash:
        raise AgentOpsError("governed commit ref update did not reach the new object")
    return commit_hash


def base_report(packet: WorkPacket, target_root: Path, *, dry_run: bool) -> dict[str, Any]:
    empty_scope = {
        "tracked_changed_files": [], "staged_files": [], "untracked_files": [],
        "changed_files": [], "violations": [], "passed": True,
    }
    return {
        "job_id": packet.id, "base_ref": packet.base_ref, "branch": packet.branch,
        "worktree": str(packet.worktree), "intent": packet.intent,
        "allowed_files": packet.allowed_files, "forbidden_files": packet.forbidden_files,
        "approval": {"before_commit": packet.approval.before_commit,
                     "before_merge": packet.approval.before_merge},
        "dry_run": dry_run,
        "target_head": head_for(target_root) if target_root.exists() else None,
        "scope": empty_scope, "gates": [], "negative_controls": [],
        "commit_hash": None, "commit_decision": "not evaluated",
        "final_git_status": "", "status": "pending",
    }


def _require_session_entry(packet: WorkPacket, *, phase: str) -> None:
    if packet.session_entry is None:
        raise AgentOpsError(f"{phase} requires a Session Entry Packet")


def _preflight_timestamp(packet: WorkPacket) -> str:
    return f"preflight-{packet.base_ref}"


def preflight_binding_path(report_root: Path, packet: WorkPacket) -> Path:
    """Return the one deterministic external preflight binding path."""
    return report_paths(report_root, packet.id, _preflight_timestamp(packet))[0]


def _validate_preflight_binding(
    report_root: Path,
    source_root: Path,
    packet: WorkPacket,
    candidate_bytes: bytes,
) -> dict[str, Any]:
    entry = packet.session_entry
    assert entry is not None
    path = preflight_binding_path(report_root, packet)
    _validate_report_destination(report_root, path, source_root)
    try:
        binding = json.loads(_read_private_report_file(report_root, path))
    except (AgentOpsError, UnicodeError, json.JSONDecodeError) as exc:
        raise AgentOpsError(f"cannot read deterministic preflight binding: {exc}") from exc
    expected = {
        "phase": "preflight",
        "status": "passed",
        "job_id": packet.id,
        "base_ref": packet.base_ref,
        "branch": packet.branch,
        "target_head": packet.base_ref,
        "packet_digest": entry.packet_digest,
        "packet_bytes_sha256": hashlib.sha256(candidate_bytes).hexdigest(),
    }
    mismatches = {
        key: {"expected": value, "actual": binding.get(key)}
        for key, value in expected.items()
        if binding.get(key) != value
    }
    if mismatches:
        raise AgentOpsError(
            f"closeout preflight binding or packet digest mismatch: {mismatches}"
        )
    return binding


def _read_private_report_file(report_root: Path, path: Path) -> bytes:
    """Read a bounded private report through a no-follow directory chain."""
    directory_descriptors = _open_report_directory_chain(report_root, path.parent)
    parent_descriptor = directory_descriptors[-1]
    parent_identity = os.fstat(parent_descriptor)
    descriptor: int | None = None
    try:
        flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
        descriptor = os.open(path.name, flags, dir_fd=parent_descriptor)
        identity = os.fstat(descriptor)
        if (
            not stat.S_ISREG(identity.st_mode)
            or identity.st_uid != os.geteuid()
            or stat.S_IMODE(identity.st_mode) != 0o600
            or identity.st_size > _MAX_BINDING_BYTES
        ):
            raise AgentOpsError("preflight binding is not a bounded private regular file")
        chunks: list[bytes] = []
        remaining = _MAX_BINDING_BYTES + 1
        while remaining:
            chunk = os.read(descriptor, min(65_536, remaining))
            if not chunk:
                break
            chunks.append(chunk)
            remaining -= len(chunk)
        if remaining == 0:
            raise AgentOpsError("preflight binding exceeds the read limit")
        current = os.stat(path.name, dir_fd=parent_descriptor, follow_symlinks=False)
        if current.st_dev != identity.st_dev or current.st_ino != identity.st_ino:
            raise AgentOpsError("preflight binding custody changed during read")
        verification = _open_report_directory_chain(report_root, path.parent)
        try:
            verified_parent = os.fstat(verification[-1])
            if (
                verified_parent.st_dev != parent_identity.st_dev
                or verified_parent.st_ino != parent_identity.st_ino
            ):
                raise AgentOpsError("preflight binding directory changed during read")
        finally:
            for item in reversed(verification):
                os.close(item)
        return b"".join(chunks)
    except OSError as exc:
        raise AgentOpsError(f"cannot open deterministic preflight binding: {exc}") from exc
    finally:
        if descriptor is not None:
            os.close(descriptor)
        for item in reversed(directory_descriptors):
            os.close(item)


def _admission_gate_environment(
    report_root: Path,
    source_root: Path,
    packet_id: str,
) -> dict[str, str]:
    """Route known Python/pytest/Hypothesis/Ruff/TMP caches outside the source tree."""
    _trusted_gate_interpreter(source_root)
    _reject_local_repository_controls(source_root, base_ref=None)
    cache_root = report_root / REPORT_ROOT / packet_id / "tool-cache"
    cache_directories = {
        "pycache": cache_root / "pycache",
        "hypothesis": cache_root / "hypothesis",
        "xdg": cache_root / "xdg",
        "ruff": cache_root / "ruff",
        "tmp": cache_root / "tmp",
        "ops": report_root / "ops" / packet_id,
        "home": report_root / "home" / packet_id,
    }
    for directory in cache_directories.values():
        sentinel = directory / ".agentops-cache-boundary"
        _validate_report_destination(report_root, sentinel, source_root)
        _ensure_private_report_directory(report_root, directory)
        _validate_report_destination(report_root, sentinel, source_root)
    environment = {
        # Positive gate argv normalization pins Python to ``sys.executable``
        # and resolves Git/Make from the trusted host path.  Do not add the
        # interpreter's sibling directory here: a repository-local venv may
        # contain untracked executables (for example ``.venv/bin/git``) that a
        # transitive Make or DocOps child could otherwise resolve first.
        "PATH": _TRUSTED_HOST_PATH,
        "HOME": str(cache_directories["home"]),
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
        "TZ": "UTC",
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONHASHSEED": "0",
        "PYTHONNOUSERSITE": "1",
        "PYTHONPYCACHEPREFIX": str(cache_directories["pycache"]),
        "HYPOTHESIS_STORAGE_DIRECTORY": str(cache_directories["hypothesis"]),
        "PYTEST_ADDOPTS": "-p no:cacheprovider",
        "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1",
        "XDG_CACHE_HOME": str(cache_directories["xdg"]),
        "RUFF_CACHE_DIR": str(cache_directories["ruff"]),
        "TMPDIR": str(cache_directories["tmp"]),
        "TEMP": str(cache_directories["tmp"]),
        "TMP": str(cache_directories["tmp"]),
        "DHARMA_OPS_DIR": str(cache_directories["ops"]),
        "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_ATTR_NOSYSTEM": "1",
        "GIT_NO_REPLACE_OBJECTS": "1",
        "GIT_OPTIONAL_LOCKS": "0",
        "GIT_CONFIG_COUNT": "2",
        "GIT_CONFIG_KEY_0": "core.fsmonitor",
        "GIT_CONFIG_VALUE_0": "false",
        "GIT_CONFIG_KEY_1": "core.hooksPath",
        "GIT_CONFIG_VALUE_1": os.devnull,
    }
    return environment


def _write_phase_report(
    output_root: Path,
    source_root: Path,
    report: dict[str, Any],
    timestamp: str,
    *,
    before_json: Callable[[], None] | None = None,
) -> None:
    for destination in report_paths(output_root, report["job_id"], timestamp):
        _validate_report_destination(output_root, destination, source_root)
    write_report(
        output_root,
        report,
        timestamp,
        source_root=source_root,
        before_json=before_json,
    )


def _execute_preflight(
    source: Path,
    packet_path: Path,
    packet: WorkPacket,
    candidate_bytes: bytes,
    report_root: Path | None,
) -> tuple[int, dict[str, Any]]:
    # Reject a repository-local bootstrap interpreter before any packet or
    # report operation.  Startup-time sitecustomize has already run by this
    # point, so the Make entrypoint independently enforces the same boundary
    # before launching this process.
    _trusted_gate_interpreter(source)
    _require_session_entry(packet, phase="preflight")
    if report_root is None:
        raise AgentOpsError("preflight requires an explicit external report_root")
    tracked_copy_state = _validate_session_envelope(
        source,
        packet_path,
        packet,
        inspect=True,
        require_tracked_copy=False,
        candidate_bytes=candidate_bytes,
    )
    for gate in packet.gates:
        admit_gate_command(gate)
    entry = packet.session_entry
    assert entry is not None
    report = base_report(packet, source, dry_run=True)
    report.update(
        {
            "phase": "preflight",
            "packet_digest": entry.packet_digest,
            "packet_bytes_sha256": hashlib.sha256(candidate_bytes).hexdigest(),
            "tracked_copy_state": tracked_copy_state,
            "commit_decision": "preflight is validation-only",
            "status": "passed",
        }
    )

    def revalidate_before_binding_publish() -> None:
        _validate_session_envelope(
            source,
            packet_path,
            packet,
            inspect=True,
            require_tracked_copy=False,
            candidate_bytes=candidate_bytes,
        )

    _write_phase_report(
        report_root,
        source,
        report,
        _preflight_timestamp(packet),
        before_json=revalidate_before_binding_publish,
    )
    return 0, report


def _execute_closeout(
    source: Path,
    packet_path: Path,
    packet: WorkPacket,
    candidate_bytes: bytes,
    report_root: Path | None,
) -> tuple[int, dict[str, Any]]:
    _require_session_entry(packet, phase="closeout")
    if report_root is None:
        raise AgentOpsError("closeout requires an explicit external report_root")
    _validate_session_envelope(
        source,
        packet_path,
        packet,
        inspect=False,
        require_tracked_copy=True,
        candidate_bytes=candidate_bytes,
        allow_tracked_input=True,
        scope_base_ref=packet.base_ref,
    )
    target_root = prepare_worktree(source, packet)
    expected_head = head_for(target_root)
    _validate_preflight_binding(
        report_root, source, packet, candidate_bytes
    )
    entry = packet.session_entry
    assert entry is not None
    timestamp = timestamp_slug()
    report = base_report(packet, target_root, dry_run=False)
    report.update(
        {
            "phase": "closeout",
            "packet_digest": entry.packet_digest,
            "packet_bytes_sha256": hashlib.sha256(candidate_bytes).hexdigest(),
            "commit_decision": "closeout is read-only; commit disabled",
        }
    )
    for destination in report_paths(report_root, packet.id, timestamp):
        _validate_report_destination(report_root, destination, source)

    initial_scope = inspect_scope(target_root, packet, base_ref=packet.base_ref)
    report["scope"] = scope_to_dict(initial_scope)
    if not initial_scope.passed:
        report["final_git_status"] = git_status(target_root)
        report["status"] = "failed"
        _write_phase_report(report_root, source, report, timestamp)
        return 1, report

    gate_environment = _admission_gate_environment(
        report_root, source, packet.id
    )
    deadline = time.monotonic() + _MAX_ADMISSION_TIMEOUT_SECONDS
    for gate in packet.gates:
        admit_gate_command(gate)
        report["gates"].append(
            run_gate(
                target_root,
                _bounded_gate(gate, deadline=deadline),
                base_env=gate_environment,
                normalize_positive_executable=True,
            )
        )
    for control in packet.negative_controls:
        report["negative_controls"].append(
            run_negative_control(
                target_root,
                _bounded_gate(control, deadline=deadline),
                temp_root=Path(gate_environment["TMPDIR"]),
            )
        )

    if branch_for(target_root) != packet.branch:
        raise AgentOpsError("closeout branch changed during gate execution")
    verify_base_is_ancestor(target_root, packet.base_ref)
    if head_for(target_root) != expected_head:
        raise AgentOpsError("closeout HEAD changed during gate execution")
    _validate_session_envelope(
        source,
        packet_path,
        packet,
        inspect=False,
        require_tracked_copy=True,
        candidate_bytes=candidate_bytes,
        allow_tracked_input=True,
        scope_base_ref=packet.base_ref,
    )
    _validate_preflight_binding(
        report_root, source, packet, candidate_bytes
    )
    final_scope = inspect_scope(target_root, packet, base_ref=packet.base_ref)
    report["scope"] = scope_to_dict(final_scope)
    report["final_git_status"] = git_status(target_root)
    checks_passed = all(
        row["passed"]
        for key in ("gates", "negative_controls")
        for row in report[key]
    )
    report["status"] = "passed" if checks_passed and final_scope.passed else "failed"
    if branch_for(target_root) != packet.branch or head_for(target_root) != expected_head:
        raise AgentOpsError("closeout branch or HEAD changed before report publication")
    verify_base_is_ancestor(target_root, packet.base_ref)
    _validate_session_envelope(
        source,
        packet_path,
        packet,
        inspect=False,
        require_tracked_copy=True,
        candidate_bytes=candidate_bytes,
        allow_tracked_input=True,
        scope_base_ref=packet.base_ref,
    )
    _validate_preflight_binding(
        report_root, source, packet, candidate_bytes
    )

    def revalidate_before_closeout_publish() -> None:
        if branch_for(target_root) != packet.branch or head_for(target_root) != expected_head:
            raise AgentOpsError("closeout branch or HEAD changed during report publication")
        verify_base_is_ancestor(target_root, packet.base_ref)
        _validate_session_envelope(
            source,
            packet_path,
            packet,
            inspect=False,
            require_tracked_copy=True,
            candidate_bytes=candidate_bytes,
            allow_tracked_input=True,
            scope_base_ref=packet.base_ref,
        )
        _validate_preflight_binding(
            report_root, source, packet, candidate_bytes
        )
        current_scope = inspect_scope(target_root, packet, base_ref=packet.base_ref)
        if scope_to_dict(current_scope) != report["scope"]:
            raise AgentOpsError("closeout scope changed during report publication")
        if git_status(target_root) != report["final_git_status"]:
            raise AgentOpsError("closeout Git status changed during report publication")

    _write_phase_report(
        report_root,
        source,
        report,
        timestamp,
        before_json=revalidate_before_closeout_publish,
    )
    return (0 if report["status"] == "passed" else 1), report


def execute_packet(
    packet_path: Path,
    *,
    source_root: Path | None = None,
    dry_run: bool = False,
    preflight: bool = False,
    closeout: bool = False,
    allow_existing_changes: bool = False,
    report_root: Path | None = None,
) -> tuple[int, dict[str, Any] | None]:
    source = require_repo_root((source_root or Path.cwd()).resolve())
    if sum((dry_run, preflight, closeout)) > 1:
        raise AgentOpsError("choose exactly one of inspect, preflight, or closeout")
    if (preflight or closeout) and allow_existing_changes:
        raise AgentOpsError(
            "preflight/closeout compute the complete envelope and do not allow "
            "--allow-existing-changes"
        )
    candidate_bytes = _read_packet_bytes(packet_path)
    packet = load_work_packet(packet_path, content=candidate_bytes)
    if packet.session_entry is not None and packet_path.suffix.lower() != ".json":
        raise AgentOpsError("Session Entry Packet must use JSON")
    external_reports = (
        _prepare_private_report_root(report_root, repo_root=source)
        if report_root is not None
        else None
    )
    if packet.session_entry is not None and not dry_run and external_reports is None:
        raise AgentOpsError("session_entry execution requires an explicit external report_root")

    if preflight:
        return _execute_preflight(
            source,
            packet_path,
            packet,
            candidate_bytes,
            external_reports,
        )
    if closeout:
        return _execute_closeout(
            source,
            packet_path,
            packet,
            candidate_bytes,
            external_reports,
        )

    if dry_run:
        tracked_copy_state = _validate_session_envelope(
            source,
            packet_path,
            packet,
            inspect=True,
            require_tracked_copy=False,
            candidate_bytes=candidate_bytes,
        )
        for gate in packet.gates:
            admit_gate_command(gate)  # O4-B11 fails closed at preflight too
        target = _packet_target(source, packet)
        summary = {
            "job_id": packet.id,
            "base_ref": packet.base_ref,
            "branch": packet.branch,
            "worktree": str(packet.worktree),
            "intent": packet.intent,
            "allowed_files": packet.allowed_files,
            "forbidden_files": packet.forbidden_files,
            "packet_digest": (
                packet.session_entry.packet_digest
                if packet.session_entry is not None
                else None
            ),
            "tracked_copy_state": tracked_copy_state,
            "gates": [
                {
                    "name": gate.name,
                    "command": gate.command,
                    "expected_exit": gate.expected_exit,
                }
                for gate in packet.gates
            ],
            "negative_controls": [
                {
                    "name": control.name,
                    "command": control.command,
                    "expected_exit": control.expected_exit,
                }
                for control in packet.negative_controls
            ],
            "commit_allowed": packet.commit.allowed,
            "approval": {
                "before_commit": packet.approval.before_commit,
                "before_merge": packet.approval.before_merge,
            },
            "dry_run": True,
            "would_create_worktree": not target.exists(),
            "would_run_gates": False,
            "would_commit": False,
        }
        print(json.dumps(summary, indent=2, sort_keys=True))
        return 0, None

    _validate_session_envelope(
        source,
        packet_path,
        packet,
        inspect=False,
        require_tracked_copy=True,
        candidate_bytes=candidate_bytes,
    )
    target_root = prepare_worktree(source, packet)
    output_root = external_reports or target_root  # legacy v0 compatibility only
    report_source = source if packet.session_entry is not None else None
    timestamp = timestamp_slug()
    report = base_report(packet, target_root, dry_run=False)
    if report_source is not None:
        for destination in report_paths(output_root, packet.id, timestamp):
            _validate_report_destination(output_root, destination, report_source)
    initial_scope = inspect_scope(target_root, packet)
    if initial_scope.changed_files and not allow_existing_changes:
        report["scope"] = scope_to_dict(initial_scope)
        report["final_git_status"] = git_status(target_root)
        report["status"] = "failed"
        report["commit_decision"] = "target worktree dirty before gates; rerun with --allow-existing-changes after human review"
        write_report(output_root, report, timestamp, source_root=report_source)
        return 1, report

    legacy_gate_root = (
        output_root
        if packet.session_entry is not None
        else _prepare_private_report_root(
            Path("/tmp") / f"dharma-agentops-legacy-{os.geteuid()}",
            repo_root=source,
        )
    )
    legacy_gate_environment = _admission_gate_environment(
        legacy_gate_root, source, packet.id
    )
    deadline = time.monotonic() + _MAX_ADMISSION_TIMEOUT_SECONDS
    for gate in packet.gates:
        admit_gate_command(gate)  # O4-B11: fail closed before execution
        gate_result = run_gate(
            target_root,
            _bounded_gate(gate, deadline=deadline),
            base_env=legacy_gate_environment,
            normalize_positive_executable=True,
        )
        report["gates"].append(gate_result)
    for control in packet.negative_controls:
        report["negative_controls"].append(
            run_negative_control(
                target_root,
                _bounded_gate(control, deadline=deadline),
                temp_root=Path(legacy_gate_environment["TMPDIR"]),
            )
        )

    _validate_session_envelope(
        source,
        packet_path,
        packet,
        inspect=False,
        require_tracked_copy=True,
        candidate_bytes=candidate_bytes,
    )

    final_scope = inspect_scope(target_root, packet)
    report["scope"] = scope_to_dict(final_scope)
    commit_allowed, commit_reason = should_commit(report, packet, final_scope)
    report["commit_decision"] = commit_reason
    if commit_allowed:
        report["commit_hash"] = create_commit(target_root, final_scope.changed_files, packet.commit.message)
        final_scope = inspect_scope(target_root, packet)
        report["scope"] = scope_to_dict(final_scope)

    report["final_git_status"] = git_status(target_root)
    checks_passed = all(
        row["passed"] for key in ("gates", "negative_controls") for row in report[key]
    )
    report["status"] = "passed" if checks_passed and final_scope.passed else "failed"
    write_report(output_root, report, timestamp, source_root=report_source)
    return (0 if report["status"] == "passed" else 1), report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run a governed AgentOps work packet")
    parser.add_argument("--packet", type=Path, help="Path to JSON/YAML work packet")
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument(
        "--dry-run",
        "--inspect",
        action="store_true",
        help="Validate and print intended actions without creating a worktree, running gates, or committing",
    )
    modes.add_argument(
        "--preflight",
        action="store_true",
        help="Bind an external packet to an exact clean baseline and external report",
    )
    modes.add_argument(
        "--closeout",
        action="store_true",
        help="Evaluate base...HEAD plus working state against the preflight binding",
    )
    modes.add_argument(
        "--validate-report-root",
        type=Path,
        help="Validate one external report root without loading a packet",
    )
    parser.add_argument(
        "--validate-report-child",
        action="append",
        default=[],
        metavar="RELATIVE",
        help=(
            "Prepare and validate a relative cache/output child beneath "
            "--validate-report-root; repeat for multiple children"
        ),
    )
    parser.add_argument(
        "--allow-existing-changes",
        action="store_true",
        help="Allow an already-dirty target worktree after explicit human review; scope still fails closed",
    )
    parser.add_argument(
        "--report-root",
        type=Path,
        help="Explicit external root for reports; required for Session Entry execution",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.validate_report_child and args.validate_report_root is None:
        parser.error("--validate-report-child requires --validate-report-root")
    if args.validate_report_root is not None:
        if args.packet is not None or args.report_root is not None:
            parser.error("--validate-report-root accepts no packet or --report-root")
        if args.allow_existing_changes:
            parser.error("--validate-report-root accepts no execution flags")
    elif args.packet is None:
        parser.error("--packet is required")
    try:
        if args.validate_report_root is not None:
            source = require_repo_root(Path.cwd().resolve())
            validated = _prepare_private_report_root(
                args.validate_report_root,
                repo_root=source,
            )
            children = _prepare_private_report_children(
                validated,
                args.validate_report_child,
                repo_root=source,
            )
            print(f"Validated external report root: {validated}")
            for child in children:
                print(f"Validated external report child: {child}")
            return 0
        assert args.packet is not None
        if not (args.dry_run or args.preflight or args.closeout):
            candidate = load_work_packet(args.packet)
            if candidate.session_entry is not None:
                raise AgentOpsError(
                    "Session Entry Packet requires --inspect, --preflight, or --closeout"
                )
        exit_code, report = execute_packet(
            args.packet,
            dry_run=args.dry_run,
            preflight=args.preflight,
            closeout=args.closeout,
            allow_existing_changes=args.allow_existing_changes,
            report_root=args.report_root,
        )
    except AgentOpsError as exc:
        print(f"AgentOps error: {exc}", file=sys.stderr)
        return 2
    except json.JSONDecodeError as exc:
        print(f"AgentOps error: invalid JSON packet: {exc}", file=sys.stderr)
        return 2

    if report is not None:
        print(f"Status: {report['status']}")
        print(f"Commit: {report.get('commit_hash') or ''}")
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
