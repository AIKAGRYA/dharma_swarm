#!/usr/bin/env python3
"""Run a governed local AgentOps work packet.

AgentOps v0 is deliberately small: it validates a machine-readable work
packet, prepares an isolated git worktree, runs declared gates, enforces a
file-scope contract, writes structured reports, and optionally creates a
local commit candidate. It never merges or pushes.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import sysconfig
import tempfile
import time
import types
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

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

# --- O4-B11: positive command-family allowlist -------------------------------
# One authoritative table (spec §WP-O4). Positive gates are admitted ONLY when
# their argv matches an enumerated family below; everything else fails closed
# BEFORE subprocess execution. This is command-family confinement, not a
# semantic proof about trusted code — pytest and an allowlisted repository
# script can themselves perform I/O; WP-O6's syscall/no-network evidence is
# the terminal oracle. Direct-Git token normalization and grammar remain
# owned by the contract module and its private WP-O1R lexical helper; this
# table only decides execution admission. Negative controls are exempt: they
# rejection and run jailed. Extending this table is a governance-reviewed
# admission change, never a drive-by edit.

_PYTHON_EXECUTABLES = frozenset({"python", "python3"})
_ALLOWED_PYTHON_MODULE_PREFIXES = (
    ("-m", "pytest"),
    ("-m", "ruff", "check"),
)
_ALLOWED_REPO_SCRIPTS = frozenset({
    "scripts/governance/agent_onboard.py",
    "scripts/governance/check_track_status.py",
    "scripts/governance/orientation_graph.py",
    "scripts/governance/repo_status.py",
    "scripts/governance/spine_bypass_report.py",
    "scripts/governance/trust_gate_status.py",
    "scripts/docops/check_docops_integrity.py",
})
# Long options that must never reach an allowlisted script, including every
# argparse prefix-abbreviation of them (default abbreviation turns `--write`
# into `--write-context`).
_FORBIDDEN_SCRIPT_FLAGS = ("--write-context",)
_ALLOWED_MAKE_VARIABLES = frozenset({"PACKET", "ARGS"})
# Make expands `$(ARGS)`/`$(PACKET)` unquoted in a shell and runs `$(shell …)`
# during recipe expansion, so a variable VALUE is executable surface. Confine
# it to a conservative positive charset that excludes every shell/make
# metacharacter (`$`, backtick, `;`, `|`, `&`, redirects, parens, glob, …).
_SAFE_MAKE_VALUE = re.compile(r"^[A-Za-z0-9 _./=:,+-]*$")
_ALLOWED_MAKE_TARGETS = frozenset({
    "onboard", "orient", "test", "test-fast", "docops-integrity",
    "hygiene-check", "module-budget", "agent-build-preflight",
    "agent-build-closeout",
})


def _is_trusted_python(token: str) -> bool:
    """A bare `python`/`python3`, or the exact running interpreter path.

    A path-qualified shim (`./python3`, `/tmp/python3`) whose basename merely
    looks trusted is rejected: ``subprocess.run`` executes the literal path,
    not the basename."""
    if token in _PYTHON_EXECUTABLES:
        return True
    try:
        return Path(token).resolve() == Path(sys.executable).resolve()
    except OSError:
        return False


def _has_forbidden_script_flag(script_args: list[str]) -> bool:
    for arg in script_args:
        if not arg.startswith("--"):
            continue
        # arg is an abbreviation of a forbidden flag iff the forbidden flag
        # starts with it (argparse admits any unambiguous prefix).
        if any(forbidden.startswith(arg) for forbidden in _FORBIDDEN_SCRIPT_FLAGS):
            return True
    return False


def admit_gate_command(gate: GateSpec) -> None:
    """Fail closed unless the positive gate matches an enumerated family.

    Packet-supplied environment is empty by default and no family enumerates
    an allowed key, so any env-carrying gate is rejected outright."""
    argv, command = gate.argv, gate.command
    if gate.env:
        raise AgentOpsError(
            f"gate command may not carry packet-supplied environment: {command}")
    head = argv[0]
    if head == "git":
        # Bare `git` only; shape + executable identity (incl. path-qualified
        # shim rejection) are already validated by the O1R direct-Git grammar
        # in parse_gate. A path-qualified git falls through to the final raise.
        return
    if _is_trusted_python(head):
        rest = tuple(argv[1:])
        for prefix in _ALLOWED_PYTHON_MODULE_PREFIXES:
            if rest[: len(prefix)] == prefix:
                return
        if argv[1:2] and argv[1].startswith("scripts/"):
            script, script_args = argv[1], argv[2:]
            if script in _ALLOWED_REPO_SCRIPTS and not _has_forbidden_script_flag(
                script_args
            ):
                return
        raise AgentOpsError(
            f"gate command is outside the positive interpreter allowlist: {command}")
    if head == "make":
        targets = [token for token in argv[1:] if "=" not in token]
        for token in argv[1:]:
            if "=" not in token:
                continue
            key, _, value = token.partition("=")
            if key not in _ALLOWED_MAKE_VARIABLES:
                raise AgentOpsError(
                    f"gate command uses a non-allowlisted make variable {key!r}: {command}")
            if not _SAFE_MAKE_VALUE.fullmatch(value):
                raise AgentOpsError(
                    f"gate command make variable {key!r} value carries shell/make "
                    f"metacharacters: {command}")
        if len(targets) == 1 and targets[0] in _ALLOWED_MAKE_TARGETS:
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
    timeout_seconds: int | None = None,
    preexec_fn: Callable[[], None] | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        argv, cwd=cwd, env=env, capture_output=True, text=True,
        timeout=timeout_seconds, check=False, preexec_fn=preexec_fn,
    )

def run_git(args: list[str], *, cwd: Path, check: bool = True) -> subprocess.CompletedProcess[str]:
    result = run_command(["git", *args], cwd=cwd)
    if check and result.returncode != 0:
        detail = (result.stderr or result.stdout).strip()
        raise AgentOpsError(f"git {' '.join(args)} failed: {detail}")
    return result

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
    commands = {"git": ["git", "--version"], "make": ["make", "--version"]}
    if name not in commands:
        raise AgentOpsError(f"session_entry declares unsupported tool: {name}")
    result = run_command(commands[name], cwd=repo_root)
    if result.returncode != 0:
        raise AgentOpsError(f"could not probe declared tool {name}")
    first_line = result.stdout.splitlines()[0] if result.stdout.splitlines() else ""
    match = re.search(r"\b(\d+(?:\.\d+)+)\b", first_line)
    if match is None:
        raise AgentOpsError(f"could not parse {name} version from {first_line!r}")
    return match.group(1)

def load_raw_packet(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
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

def load_work_packet(path: Path) -> WorkPacket:
    return parse_work_packet(load_raw_packet(path))

def git_lines(repo_root: Path, args: list[str]) -> list[str]:
    output = run_git(args, cwd=repo_root).stdout
    return [line.strip().replace("\\", "/") for line in output.splitlines() if line.strip()]

def git_status(repo_root: Path) -> str:
    return run_git(["status", "--short"], cwd=repo_root).stdout


def inspect_scope(repo_root: Path, packet: WorkPacket) -> ScopeState:
    tracked = sorted(set(git_lines(repo_root, ["diff", "--name-only"])))
    staged = sorted(set(git_lines(repo_root, ["diff", "--name-only", "--cached"])))
    untracked = sorted(set(git_lines(repo_root, ["ls-files", "--others", "--exclude-standard"])))
    changed = sorted(set(tracked + staged + untracked))
    violations: list[dict[str, Any]] = []
    for path in changed:
        forbidden = matching_patterns(path, packet.forbidden_files)
        allowed = matching_patterns(path, packet.allowed_files)
        if forbidden:
            violations.append({"path": path, "reason": "forbidden", "patterns": forbidden})
        elif not allowed:
            violations.append({"path": path, "reason": "outside_allowed_scope", "patterns": []})
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


def _packet_target(source_root: Path, packet: WorkPacket) -> Path:
    if packet.session_entry is not None:
        if packet.worktree != Path("."):
            raise AgentOpsError('session_entry packets require portable worktree "."')
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


def _active_tracks(repo_root: Path) -> list[dict[str, Any]]:
    path = repo_root / "docs/governance/ACTIVE_TRACK.yaml"
    try:
        text = path.read_text(encoding="utf-8")
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            import yaml  # type: ignore[import-not-found]

            data = yaml.safe_load(text)
    except (OSError, ValueError) as exc:
        raise AgentOpsError(f"cannot read active-track owner config: {exc}") from exc
    rows = data.get("active_tracks") if isinstance(data, dict) else None
    if not isinstance(rows, list):
        raise AgentOpsError("ACTIVE_TRACK.yaml active_tracks must be a list")
    return [row for row in rows if isinstance(row, dict)]


def _validate_session_envelope(
    repo_root: Path,
    packet_path: Path,
    packet: WorkPacket,
    *,
    inspect: bool,
    require_tracked_copy: bool,
) -> None:
    entry = packet.session_entry
    if entry is None:
        return
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
    if selected is None or selected.get("status") != "ACTIVE":
        raise AgentOpsError(f"session_entry active_track is not ACTIVE: {entry.active_track}")
    if selected.get("owner") != entry.owner:
        raise AgentOpsError("session_entry owner does not match ACTIVE_TRACK.yaml")
    siblings = {
        str(row.get("id")): [str(value) for value in row.get("owned_surfaces") or []]
        for row in _active_tracks(repo_root)
        if row.get("id") != entry.active_track
    }
    missing = sorted({p for patterns in siblings.values() for p in patterns} - set(packet.forbidden_files))
    if missing:
        raise AgentOpsError(f"forbidden_files omit sibling owned surfaces: {missing}")
    actual = sorted(set(git_lines(repo_root, ["ls-files"]) + inspect_scope(repo_root, packet).changed_files))
    collisions = detect_surface_collisions(
        allowed_patterns=packet.allowed_files,
        sibling_patterns=siblings,
        actual_paths=actual,
    )
    if collisions:
        raise AgentOpsError(f"session_entry ownership collision: {collisions}")
    if entry.collision.status != "clear" or entry.collision.details:
        raise AgentOpsError("session_entry collision declaration disagrees with recomputation")
    tracked = repo_root / "reports/agentops/work_packets" / f"{packet.id}.json"
    if tracked.exists() and tracked.read_bytes() != packet_path.read_bytes():
        raise AgentOpsError("tracked copy must be byte-identical to external Session Entry Packet")
    if require_tracked_copy and not tracked.exists():
        raise AgentOpsError(f"tracked copy is missing: {tracked.relative_to(repo_root)}")
    if require_tracked_copy:
        relative = tracked.relative_to(repo_root).as_posix()
        indexed = run_git(
            ["ls-files", "--error-unmatch", "--", relative],
            cwd=repo_root,
            check=False,
        )
        if indexed.returncode != 0:
            raise AgentOpsError(f"tracked copy is not in the Git index: {relative}")
    if inspect:
        if head_for(repo_root) != base_hash:
            raise AgentOpsError("inspect requires exact HEAD == packet.base_ref")
        if branch_for(repo_root) != packet.branch:
            raise AgentOpsError("inspect branch does not match packet.branch")
        if git_status(repo_root):
            raise AgentOpsError("inspect requires an exact clean HEAD")


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
    result = run_command(["ldd", str(source.resolve())], cwd=source.parent)
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
        resolved = shutil.which(command)
        if resolved is None:
            raise AgentOpsError(f"negative-control executable is unavailable: {command}")
        lexical = Path(resolved)
    if not lexical.exists():
        raise AgentOpsError(f"negative-control executable is unavailable: {command}")
    _copy_file_into_jail(lexical.resolve(), jail, lexical)
    _copy_elf_dependencies(lexical.resolve(), jail)


def _copy_python_runtime(jail: Path) -> None:
    executable = Path(sys.executable)
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
        key: value
        for key, value in os.environ.items()
        if key in {"LANG", "LC_ALL", "PATH", "PATHEXT", "SYSTEMROOT", "TZ", "WINDIR"}
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
        "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1",
        "GIT_CONFIG_NOSYSTEM": "1",
    })
    if jailed:
        safe["DHARMA_AGENTOPS_JAILED"] = "1"
    pythonpath = declared.get("PYTHONPATH", os.environ.get("PYTHONPATH", ""))
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
            "VIRTUAL_ENV", "PYTHONPYCACHEPREFIX",
        }:
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
    if sys.platform == "darwin" and shutil.which("sandbox-exec"):
        escaped = str(fixture.resolve()).replace("\\", "\\\\").replace('"', '\\"')
        profile = (
            '(version 1) (deny file-write*) '
            f'(allow file-write* (subpath "{escaped}") (literal "/dev/null"))'
        )
        return None, ["sandbox-exec", "-p", profile, "--"], False, False
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
        probe = run_command([unshare, "--user", "--map-root-user", "true"], cwd=fixture)
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


def run_gate(
    repo_root: Path,
    gate: GateSpec,
    *,
    base_env: dict[str, str] | None = None,
    preexec_fn: Callable[[], None] | None = None,
    argv_prefix: list[str] | None = None,
) -> dict[str, Any]:
    started = time.monotonic()
    inherited = os.environ if base_env is None else base_env
    env = build_gate_environment(gate, inherited)
    try:
        result = run_command(
            [*(argv_prefix or []), *gate.argv],
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


def run_negative_control(repo_root: Path, gate: GateSpec) -> dict[str, Any]:
    ignored_names = {".git", ".venv", "node_modules", "__pycache__", ".pytest_cache"}
    ignored = shutil.ignore_patterns(*ignored_names)
    candidate = next(
        (os.environ[name] for name in ("TMPDIR", "TEMP", "TMP") if os.environ.get(name)),
        "/tmp" if os.name == "posix" else str(Path.cwd()),
    )
    temp_root = resolve_external_dir(
        candidate, repo_root=repo_root, field="negative-control temp root"
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
                ["git", "clone", "--no-checkout", "--no-hardlinks",
                 str(repo_root), str(fixture)], cwd=repo_root,
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
        preexec_fn, argv_prefix, jailed, env_via_argv = _negative_confinement(
            jail, fixture
        )
        control_env = _negative_environment(
            repo_root, fixture, jail, gate.env, jailed=jailed
        )
        if jailed:
            _prepare_jail(jail, gate)
        host_env = control_env
        if env_via_argv:
            control_env = build_gate_environment(replace(gate, env={}), control_env)
            argv_prefix = [
                *argv_prefix,
                *_environment_argv(control_env),
                "/bin/sh",
                "-c",
                'cd /fixture && exec "$@"',
                "agentops",
            ]
            host_env = {"PATH": _TRUSTED_HOST_PATH}
        return run_gate(
            fixture,
            replace(gate, env={}),
            base_env=host_env,
            preexec_fn=preexec_fn,
            argv_prefix=argv_prefix,
        )


def timestamp_slug(now: datetime | None = None) -> str:
    value = now or datetime.now(timezone.utc)
    return value.strftime("%Y%m%dT%H%M%S%fZ")


def report_paths(repo_root: Path, job_id: str, timestamp: str) -> tuple[Path, Path]:
    report_dir = repo_root / REPORT_ROOT / job_id / timestamp
    return report_dir / "report.json", report_dir / "report.md"


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


def write_report(
    repo_root: Path,
    report: dict[str, Any],
    timestamp: str,
    *,
    source_root: Path | None = None,
) -> tuple[Path, Path]:
    json_path, md_path = report_paths(repo_root, report["job_id"], timestamp)
    if source_root is not None:
        _validate_report_destination(repo_root, json_path, source_root)
        _validate_report_destination(repo_root, md_path, source_root)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    if source_root is not None:
        _validate_report_destination(repo_root, json_path, source_root)
        _validate_report_destination(repo_root, md_path, source_root)
    json_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    md_path.write_text(render_markdown_report(report), encoding="utf-8")
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


def create_commit(repo_root: Path, files: list[str], message: str) -> str:
    run_git(["add", "--", *files], cwd=repo_root)
    result = run_git(["commit", "-m", message], cwd=repo_root, check=False)
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip()
        raise AgentOpsError(f"git commit failed: {detail}")
    return head_for(repo_root)


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


def execute_packet(
    packet_path: Path,
    *,
    source_root: Path | None = None,
    dry_run: bool = False,
    allow_existing_changes: bool = False,
    report_root: Path | None = None,
) -> tuple[int, dict[str, Any] | None]:
    source = require_repo_root((source_root or Path.cwd()).resolve())
    packet = load_work_packet(packet_path)
    if packet.session_entry is not None and packet_path.suffix.lower() != ".json":
        raise AgentOpsError("Session Entry Packet must use JSON")
    external_reports = (
        resolve_external_dir(report_root, repo_root=source)
        if report_root is not None
        else None
    )
    if packet.session_entry is not None and not dry_run and external_reports is None:
        raise AgentOpsError("session_entry execution requires an explicit external report_root")

    if dry_run:
        _validate_session_envelope(
            source, packet_path, packet, inspect=True, require_tracked_copy=False
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
            "gates": [gate.command for gate in packet.gates],
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
        source, packet_path, packet, inspect=False, require_tracked_copy=True
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

    for gate in packet.gates:
        admit_gate_command(gate)  # O4-B11: fail closed before execution
        gate_result = run_gate(target_root, gate)
        report["gates"].append(gate_result)
    for control in packet.negative_controls:
        report["negative_controls"].append(run_negative_control(target_root, control))

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
    parser.add_argument("--packet", required=True, type=Path, help="Path to JSON/YAML work packet")
    parser.add_argument(
        "--dry-run",
        "--inspect",
        action="store_true",
        help="Validate and print intended actions without creating a worktree, running gates, or committing",
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
    try:
        exit_code, report = execute_packet(
            args.packet,
            dry_run=args.dry_run,
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
