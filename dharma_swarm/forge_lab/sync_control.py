"""Content-addressed synchronization for the Forge RSI Lab.

GitHub owns code identity.  Mac and Meghadharma consume immutable releases of
that identity.  Mutable lab state, archives, credentials, and SQLite/WAL files
are stable host-owned anchors and are never copied by this module.

The file deliberately imports only the Python standard library.  The local
orchestrator streams this exact source to ``python3 -`` on Meghadharma, which
lets a new release bootstrap itself without trusting an unversioned updater on
the remote host.
"""

from __future__ import annotations

import base64
import contextlib
import hashlib
import json
import os
import platform
import re
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator, Sequence
from uuid import uuid4


PLAN_SCHEMA = "rsi_lab.sync_plan.v1"
RELEASE_SCHEMA = "rsi_lab.release_manifest.v1"
RECEIPT_SCHEMA = "rsi_lab.sync_receipt.v1"
STATUS_SCHEMA = "rsi_lab.sync_status.v1"

CANONICAL_REPOSITORY = "https://github.com/AmitabhainArunachala/dharma_swarm.git"
CANONICAL_REF = "refs/heads/rsi-lab/canonical"
DEFAULT_REMOTE = "meghadharma"
DEFAULT_REMOTE_ROOT = Path("/root/rsi-lab")

CRITICAL_FILES = (
    "uv.lock",
    "dharma_swarm/forge_lab/version.py",
    "dharma_swarm/forge_lab/rsi_cli.py",
    "dharma_swarm/forge_lab/sync_control.py",
    "dharma_swarm/forge_lab/sync_orchestrator.py",
    "dharma_swarm/forge_lab/operator_history.py",
    "dharma_swarm/forge_lab/operator_history_sources.py",
    "dharma_swarm/forge_lab/operator_history_projection.py",
    "dharma_swarm/forge_v1/canonical.py",
    "dharma_swarm/forge_v1/providers.py",
    "dharma_swarm/forge_v1/forge_v2/runner_slots.py",
    "scripts/forge_lab/rsi",
    "scripts/forge_lab/rsi-env",
    "scripts/forge_lab/rsi-sync-retired",
    "scripts/forge_lab/operator-history",
    "examples/agents/codex_rsi_lab_manager.registration.json",
    "specs/FORGE_LAB_V0_1_0_SPEC.md",
    "docs/ops/FORGE_LAB_V0_1_RUNBOOK.md",
)

VERIFICATION_TESTS = (
    "tests/forge_lab_v1/test_cli_contract.py",
    "tests/forge_lab_v1/test_manager_registration.py",
    "tests/forge_lab_v1/test_code_sync.py",
    "tests/test_forge_lab_operator_history.py",
)

SSH_OPTIONS = (
    "-o",
    "BatchMode=yes",
    "-o",
    "StrictHostKeyChecking=yes",
    "-o",
    "IdentitiesOnly=yes",
    "-o",
    "PasswordAuthentication=no",
    "-o",
    "KbdInteractiveAuthentication=no",
    "-o",
    "ForwardAgent=no",
    "-o",
    "ConnectTimeout=10",
)

_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
_DIGEST_RE = re.compile(r"^sha256:([0-9a-f]{64})$")
_REQUEST_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{2,95}$")
_REMOTE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9.-]{0,63}$")
_PACKAGE_VERSION_RE = re.compile(rb'^PACKAGE_VERSION\s*=\s*["\']([^"\']+)["\']', re.M)


class SyncError(RuntimeError):
    """A fail-closed synchronization error with a stable machine code."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def default_local_root() -> Path:
    return Path(os.environ.get("RSI_LAB_LOCAL_ROOT", Path.home() / ".dharma/rsi-lab"))


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace(
        "+00:00", "Z"
    )


def _canonical_json(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _plan_payload(plan: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in plan.items() if key != "plan_digest"}


def plan_digest(plan: dict[str, Any]) -> str:
    return f"sha256:{_sha256_bytes(_canonical_json(_plan_payload(plan)))}"


def _atomic_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(f".{path.name}.tmp-{os.getpid()}-{uuid4().hex[:8]}")
    try:
        with temp.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp, path)
    finally:
        temp.unlink(missing_ok=True)


def _run(
    command: Sequence[str],
    *,
    cwd: Path | None = None,
    input_text: str | None = None,
    env: dict[str, str] | None = None,
    timeout: int = 300,
) -> subprocess.CompletedProcess[str]:
    try:
        result = subprocess.run(
            list(command),
            cwd=str(cwd) if cwd else None,
            input=input_text,
            env=env,
            capture_output=True,
            check=False,
            text=True,
            timeout=timeout,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise SyncError("COMMAND_UNAVAILABLE", f"command failed to run: {command[0]}: {exc}") from exc
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip()[-1200:]
        raise SyncError(
            "COMMAND_FAILED",
            f"{command[0]} exited {result.returncode}: {detail or 'no diagnostic'}",
        )
    return result


def _run_bytes(command: Sequence[str], *, timeout: int = 300) -> bytes:
    try:
        result = subprocess.run(
            list(command), capture_output=True, check=False, timeout=timeout
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise SyncError("COMMAND_UNAVAILABLE", f"command failed to run: {command[0]}: {exc}") from exc
    if result.returncode != 0:
        detail = result.stderr.decode("utf-8", errors="replace").strip()[-1200:]
        raise SyncError(
            "COMMAND_FAILED",
            f"{command[0]} exited {result.returncode}: {detail or 'no diagnostic'}",
        )
    return result.stdout


def _validate_sha(value: str, *, field: str = "commit") -> str:
    if not _SHA_RE.fullmatch(value):
        raise SyncError("INVALID_IDENTITY", f"{field} must be a full lowercase 40-character SHA")
    return value


def _validate_request_id(value: str) -> str:
    if not _REQUEST_RE.fullmatch(value):
        raise SyncError(
            "INVALID_REQUEST_ID",
            "request id must be 3-96 safe characters (letters, digits, dot, underscore, hyphen)",
        )
    return value


def _validate_remote(remote: str) -> str:
    allowed = {DEFAULT_REMOTE}
    configured = os.environ.get("RSI_LAB_ALLOWED_REMOTES", "")
    allowed.update(item for item in configured.split(",") if item)
    if not _REMOTE_RE.fullmatch(remote) or remote not in allowed:
        raise SyncError("REMOTE_NOT_ALLOWED", f"remote host is not allowlisted: {remote!r}")
    return remote


def _remote_head() -> str:
    result = _run(
        ["git", "ls-remote", "--exit-code", CANONICAL_REPOSITORY, CANONICAL_REF],
        timeout=60,
    )
    fields = result.stdout.strip().split()
    if len(fields) != 2 or fields[1] != CANONICAL_REF:
        raise SyncError("CANONICAL_REF_MISSING", f"could not resolve {CANONICAL_REF}")
    return _validate_sha(fields[0])


def _cache_path(root: Path) -> Path:
    return root / "cache" / "dharma_swarm.git"


def _fetch_canonical(root: Path, expected_commit: str | None = None) -> Path:
    cache = _cache_path(root)
    cache.parent.mkdir(parents=True, exist_ok=True)
    if not (cache / "HEAD").is_file():
        _run(["git", "init", "--bare", str(cache)])
    _run(
        [
            "git",
            "--git-dir",
            str(cache),
            "fetch",
            "--no-tags",
            "--depth=1",
            CANONICAL_REPOSITORY,
            CANONICAL_REF,
        ],
        timeout=300,
    )
    fetched = _run(
        ["git", "--git-dir", str(cache), "rev-parse", "FETCH_HEAD^{commit}"]
    ).stdout.strip()
    _validate_sha(fetched)
    if expected_commit and fetched != expected_commit:
        raise SyncError(
            "STALE_PLAN",
            f"canonical ref moved: expected {expected_commit}, fetched {fetched}",
        )
    _run(
        [
            "git",
            "--git-dir",
            str(cache),
            "update-ref",
            f"refs/rsi-lab/releases/{fetched}",
            fetched,
        ]
    )
    return cache


def _object_identity(cache: Path, commit: str) -> dict[str, Any]:
    commit = _validate_sha(commit)
    tree = _run(
        ["git", "--git-dir", str(cache), "rev-parse", f"{commit}^{{tree}}"]
    ).stdout.strip()
    _validate_sha(tree, field="tree")
    critical: dict[str, str] = {}
    blobs: dict[str, bytes] = {}
    for relative in CRITICAL_FILES:
        blob = _run_bytes(
            ["git", "--git-dir", str(cache), "show", f"{commit}:{relative}"]
        )
        blobs[relative] = blob
        critical[relative] = _sha256_bytes(blob)
    version_match = _PACKAGE_VERSION_RE.search(
        blobs["dharma_swarm/forge_lab/version.py"]
    )
    if version_match is None:
        raise SyncError("VERSION_UNREADABLE", "Forge package version is not parseable")
    return {
        "commit": commit,
        "tree": tree,
        "uv_lock_sha256": critical["uv.lock"],
        "critical_files": critical,
        "forge_package_version": version_match.group(1).decode("utf-8"),
    }


def validate_plan(plan: dict[str, Any]) -> dict[str, Any]:
    if plan.get("schema") != PLAN_SCHEMA:
        raise SyncError("INVALID_PLAN", f"unsupported plan schema: {plan.get('schema')!r}")
    if plan.get("canonical_repository") != CANONICAL_REPOSITORY:
        raise SyncError("INVALID_PLAN", "plan repository is not the canonical RSI repository")
    if plan.get("canonical_ref") != CANONICAL_REF:
        raise SyncError("INVALID_PLAN", "plan ref is not the canonical RSI branch")
    _validate_sha(str(plan.get("commit", "")))
    _validate_sha(str(plan.get("tree", "")), field="tree")
    expected_digest = plan_digest(plan)
    if plan.get("plan_digest") != expected_digest:
        raise SyncError("PLAN_TAMPERED", "plan content does not match its SHA-256 digest")
    critical = plan.get("critical_files")
    if not isinstance(critical, dict) or set(critical) != set(CRITICAL_FILES):
        raise SyncError("INVALID_PLAN", "plan critical-file set is incomplete or unexpected")
    if any(not re.fullmatch(r"[0-9a-f]{64}", str(value)) for value in critical.values()):
        raise SyncError("INVALID_PLAN", "plan contains an invalid critical-file digest")
    if plan.get("uv_lock_sha256") != critical.get("uv.lock"):
        raise SyncError("INVALID_PLAN", "uv.lock identity is internally inconsistent")
    if plan.get("verification_tests") != list(VERIFICATION_TESTS):
        raise SyncError("INVALID_PLAN", "verification test contract is not canonical")
    return plan


def _checkout_identity(repo: Path) -> dict[str, Any]:
    if not (repo / ".git").exists():
        raise SyncError("RELEASE_INVALID", f"release checkout has no Git metadata: {repo}")
    commit = _run(["git", "-C", str(repo), "rev-parse", "HEAD^{commit}"]).stdout.strip()
    tree = _run(["git", "-C", str(repo), "rev-parse", "HEAD^{tree}"]).stdout.strip()
    status = _run(
        [
            "git",
            "--no-optional-locks",
            "-C",
            str(repo),
            "status",
            "--porcelain",
            "--untracked-files=all",
        ]
    ).stdout.strip()
    critical: dict[str, str] = {}
    for relative in CRITICAL_FILES:
        path = repo / relative
        critical[relative] = _sha256_file(path) if path.is_file() else "missing"
    version_bytes = (repo / "dharma_swarm/forge_lab/version.py").read_bytes()
    version_match = _PACKAGE_VERSION_RE.search(version_bytes)
    return {
        "commit": commit,
        "tree": tree,
        "repo_clean": not bool(status),
        "status_porcelain": status[:1000],
        "uv_lock_sha256": critical["uv.lock"],
        "critical_files": critical,
        "forge_package_version": (
            version_match.group(1).decode("utf-8") if version_match else "unknown"
        ),
    }


def _identity_mismatches(actual: dict[str, Any], plan: dict[str, Any]) -> list[str]:
    mismatches: list[str] = []
    for field in (
        "commit",
        "tree",
        "uv_lock_sha256",
        "critical_files",
        "forge_package_version",
    ):
        if actual.get(field) != plan.get(field):
            mismatches.append(field)
    if actual.get("repo_clean") is not True:
        mismatches.append("repo_clean")
    return mismatches


def _path_present(path: Path) -> bool:
    return path.exists() or path.is_symlink()


def _current_target(root: Path) -> Path | None:
    current = root / "current"
    if not current.is_symlink():
        return None
    try:
        return current.resolve(strict=True)
    except OSError:
        return None


def _current_commit(root: Path) -> str | None:
    target = _current_target(root)
    if target is None or not (target / "repo" / ".git").exists():
        return None
    try:
        return _checkout_identity(target / "repo")["commit"]
    except SyncError:
        return None


def _runtime_fingerprint(release: Path | None) -> dict[str, Any]:
    result: dict[str, Any] = {
        "node_python_version": platform.python_version(),
        "os": platform.system().lower(),
        "machine": platform.machine().lower(),
    }
    if release is None:
        result.update(
            {
                "python_executable": None,
                "python_version": None,
                "python_compatible": False,
            }
        )
        return result
    python = release / ".venv" / "bin" / "python"
    result["python_executable"] = str(python.resolve()) if python.exists() else None
    if not python.exists():
        result.update({"python_version": None, "python_compatible": False})
        return result
    try:
        version = _run(
            [str(python), "-c", "import platform; print(platform.python_version())"],
            timeout=15,
        ).stdout.strip()
    except SyncError as exc:
        result.update(
            {
                "python_version": None,
                "python_compatible": False,
                "runtime_error": str(exc),
            }
        )
        return result
    parts = tuple(int(item) for item in version.split(".")[:2])
    result.update({"python_version": version, "python_compatible": parts >= (3, 11)})
    return result


def node_status(root: Path, *, node: str) -> dict[str, Any]:
    root = root.expanduser().resolve()
    target = _current_target(root)
    identity: dict[str, Any] | None = None
    release_manifest: dict[str, Any] | None = None
    errors: list[str] = []
    if target is None:
        errors.append("current release is missing or is not an atomic symlink")
    else:
        try:
            identity = _checkout_identity(target / "repo")
        except (OSError, SyncError) as exc:
            errors.append(str(exc))
        manifest_path = target / "RELEASE_MANIFEST.json"
        if manifest_path.is_file():
            try:
                loaded = json.loads(manifest_path.read_text(encoding="utf-8"))
                if not isinstance(loaded, dict) or loaded.get("schema") != RELEASE_SCHEMA:
                    raise SyncError("RELEASE_MANIFEST_MISMATCH", "unsupported release manifest")
                embedded = validate_plan(loaded.get("plan", {}))
                if loaded.get("plan_digest") != embedded["plan_digest"]:
                    raise SyncError("RELEASE_MANIFEST_MISMATCH", "release plan digest disagrees")
                if identity and embedded["commit"] != identity["commit"]:
                    raise SyncError("RELEASE_MANIFEST_MISMATCH", "release commit disagrees")
                release_manifest = loaded
            except (OSError, json.JSONDecodeError, SyncError) as exc:
                errors.append(f"release manifest unreadable: {exc}")
        else:
            errors.append("release manifest is absent")
    anchors = {
        "state": _path_present(root / "state"),
        "runtime_venv": _path_present(root / "runtime" / ".venv"),
        "runtime_pydeps": _path_present(root / "runtime" / "pydeps"),
        "secrets": _path_present(root / "secrets"),
    }
    return {
        "schema": "rsi_lab.node_status.v1",
        "node": node,
        "root": str(root),
        "current_target": str(target) if target else None,
        "identity": identity,
        "release_manifest_digest": (
            release_manifest.get("plan_digest") if release_manifest else None
        ),
        "anchors": anchors,
        "runtime": _runtime_fingerprint(target),
        "ready": bool(
            target
            and identity
            and release_manifest
            and identity.get("repo_clean")
            and anchors["state"]
            and anchors["runtime_venv"]
            and anchors["runtime_pydeps"]
        ),
        "errors": errors,
    }


def _safe_symlink(target: Path, link: Path) -> None:
    if _path_present(link):
        if link.is_symlink() and link.resolve(strict=False) == target.resolve(strict=False):
            return
        raise SyncError("ANCHOR_CONFLICT", f"refusing to replace existing anchor: {link}")
    link.parent.mkdir(parents=True, exist_ok=True)
    os.symlink(str(target), str(link), target_is_directory=True)


def _stabilize_anchors(root: Path, *, node: str, local_venv: Path | None) -> None:
    root.mkdir(parents=True, exist_ok=True)
    previous = _current_target(root)

    state = root / "state"
    if not _path_present(state):
        previous_state = previous / "state" if previous else None
        if previous_state and previous_state.exists():
            _safe_symlink(previous_state.resolve(), state)
        else:
            state.mkdir(parents=True)

    runtime = root / "runtime"
    runtime.mkdir(parents=True, exist_ok=True)
    venv = runtime / ".venv"
    if not _path_present(venv):
        previous_venv = previous / ".venv" if previous else None
        source = local_venv if local_venv and local_venv.exists() else previous_venv
        if source is None or not source.exists():
            raise SyncError("RUNTIME_MISSING", "no compatible Python environment is available")
        _safe_symlink(source.resolve(), venv)
    if not (venv / "bin" / "python").exists():
        raise SyncError("RUNTIME_MISSING", f"runtime Python is absent under {venv}")

    pydeps = runtime / "pydeps"
    if not _path_present(pydeps):
        previous_pydeps = previous / "pydeps" if previous else None
        if previous_pydeps and previous_pydeps.exists():
            _safe_symlink(previous_pydeps.resolve(), pydeps)
        else:
            pydeps.mkdir(parents=True)

    if node == "meghadharma" and not _path_present(root / "secrets"):
        recovery_secrets = root / "current-main" / "secrets"
        if recovery_secrets.exists():
            _safe_symlink(recovery_secrets.resolve(), root / "secrets")


def _ensure_release_links(release: Path, root: Path) -> None:
    for name, target in (
        ("state", root / "state"),
        (".venv", root / "runtime" / ".venv"),
        ("pydeps", root / "runtime" / "pydeps"),
    ):
        link = release / name
        if _path_present(link):
            if link.is_symlink() and link.resolve(strict=False) == target.resolve(strict=False):
                continue
            raise SyncError("RELEASE_INVALID", f"release runtime link conflicts: {link}")
        os.symlink(str(target), str(link), target_is_directory=True)
    if _path_present(root / "secrets"):
        _safe_symlink(root / "secrets", release / "secrets")


def _verify_release(release: Path, plan: dict[str, Any]) -> dict[str, Any]:
    identity = _checkout_identity(release / "repo")
    mismatches = _identity_mismatches(identity, plan)
    if mismatches:
        raise SyncError(
            "RELEASE_IDENTITY_MISMATCH",
            f"release does not match plan fields: {', '.join(mismatches)}",
        )
    runtime = _runtime_fingerprint(release)
    if not runtime.get("python_compatible"):
        raise SyncError("RUNTIME_INCOMPATIBLE", "release requires Python 3.11 or newer")
    return {"identity": identity, "runtime": runtime}


def _run_offline_verification(release: Path, root: Path, plan: dict[str, Any]) -> dict[str, Any]:
    python = release / ".venv" / "bin" / "python"
    repo = release / "repo"
    pydeps = release / "pydeps"
    env = os.environ.copy()
    env.update(
        {
            "DHARMA_HOME": str(root / "state" / ".dharma"),
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTHONPATH": os.pathsep.join(
                item
                for item in (str(repo), str(pydeps), env.get("PYTHONPATH", ""))
                if item
            ),
            "RSI_LAB_BASE": str(release),
            "RSI_LAB_REPO": str(repo),
            "RSI_LAB_PYTHON": str(python),
            "RSI_LAB_PYDEPS": str(pydeps),
            "RSI_LAB_STATE": str(root / "state"),
        }
    )
    started = _now()
    result = _run(
        [
            str(python),
            "-m",
            "pytest",
            "-q",
            "-p",
            "no:cacheprovider",
            *plan["verification_tests"],
        ],
        cwd=repo,
        env=env,
        timeout=900,
    )
    final_identity = _checkout_identity(repo)
    if not final_identity["repo_clean"]:
        raise SyncError("VERIFICATION_DIRTIED_RELEASE", "offline tests changed the immutable checkout")
    return {
        "started_at": started,
        "completed_at": _now(),
        "command": "python -m pytest -q -p no:cacheprovider "
        + " ".join(plan["verification_tests"]),
        "stdout_tail": result.stdout.strip()[-1200:],
        "network_or_provider_calls": False,
    }


def prepare_release(
    plan: dict[str, Any],
    root: Path,
    *,
    node: str,
    local_venv: Path | None = None,
) -> dict[str, Any]:
    plan = validate_plan(plan)
    root = root.expanduser().resolve()
    if _remote_head() != plan["commit"]:
        raise SyncError("STALE_PLAN", "canonical branch moved after this plan was created")
    cache = _fetch_canonical(root, plan["commit"])
    _stabilize_anchors(root, node=node, local_venv=local_venv)
    release = root / "releases" / plan["commit"]
    release.parent.mkdir(parents=True, exist_ok=True)
    reused = release.is_dir()
    if not reused:
        release.mkdir()
        try:
            _run(
                [
                    "git",
                    "clone",
                    "--local",
                    "--no-checkout",
                    str(cache),
                    str(release / "repo"),
                ],
                timeout=600,
            )
            _run(
                [
                    "git",
                    "-C",
                    str(release / "repo"),
                    "checkout",
                    "--detach",
                    plan["commit"],
                ],
                timeout=300,
            )
            _run(
                [
                    "git",
                    "-C",
                    str(release / "repo"),
                    "remote",
                    "set-url",
                    "origin",
                    CANONICAL_REPOSITORY,
                ]
            )
            _ensure_release_links(release, root)
        except Exception:
            shutil.rmtree(release, ignore_errors=True)
            raise
    else:
        _ensure_release_links(release, root)
    verified = _verify_release(release, plan)
    offline = _run_offline_verification(release, root, plan)
    manifest = {
        "schema": RELEASE_SCHEMA,
        "plan_digest": plan["plan_digest"],
        "plan": plan,
        "prepared_at": _now(),
        "node": node,
        "release": str(release),
        "reused": reused,
        "verification": {**verified, "offline": offline},
    }
    _atomic_json(release / "RELEASE_MANIFEST.json", manifest)
    return {
        "node": node,
        "release": str(release),
        "commit": plan["commit"],
        "previous_commit": _current_commit(root),
        "previous_target": str(_current_target(root)) if _current_target(root) else None,
        "reused": reused,
        "verification": manifest["verification"],
    }


def _campaign_guard(root: Path) -> dict[str, Any]:
    reasons: list[str] = []
    evidence: dict[str, Any] = {}
    block = root / "DEPLOYMENT_BLOCK"
    if block.exists():
        reasons.append(f"operator deployment block exists: {block}")

    active_manifest = root / "state" / ".dharma" / "forge_lab" / "active_campaign.json"
    if active_manifest.is_file():
        try:
            payload = json.loads(active_manifest.read_text(encoding="utf-8"))
            state = str(payload.get("state", "unknown")).lower()
            evidence["active_campaign_manifest_state"] = state
            if state in {"active", "running", "pausing", "resuming", "stopping"}:
                reasons.append(f"campaign manifest reports active state: {state}")
        except (OSError, json.JSONDecodeError) as exc:
            reasons.append(f"active campaign manifest is unreadable: {exc}")

    try:
        tmux = subprocess.run(
            ["tmux", "list-sessions", "-F", "#{session_name}"],
            capture_output=True,
            check=False,
            text=True,
            timeout=10,
        )
        sessions = [line.strip() for line in tmux.stdout.splitlines() if line.strip()]
    except (OSError, subprocess.SubprocessError):
        sessions = []
    active_sessions = [
        name
        for name in sessions
        if re.search(r"(^|[-_])(rsi|forge[-_]lab)([-_]|$)", name, re.I)
    ]
    evidence["tmux_sessions"] = sessions
    if active_sessions:
        reasons.append(f"active RSI tmux sessions: {', '.join(active_sessions)}")

    try:
        processes = subprocess.run(
            ["ps", "-eo", "pid=,args="],
            capture_output=True,
            check=False,
            text=True,
            timeout=10,
        ).stdout.splitlines()
    except (OSError, subprocess.SubprocessError):
        processes = []
    patterns = (
        "dharma_swarm.forge_lab.experiment",
        "rsi-manager-",
        "rsi-overnight",
        "forge_lab_v1_run",
    )
    active_processes = [
        line.strip()
        for line in processes
        if any(pattern in line for pattern in patterns) and "sync_control" not in line
    ]
    evidence["active_process_count"] = len(active_processes)
    if active_processes:
        reasons.append(f"active RSI process count: {len(active_processes)}")
    return {"ok": not reasons, "reasons": reasons, "evidence": evidence}


def _atomic_symlink(target: Path, link: Path) -> None:
    if _path_present(link) and not link.is_symlink():
        raise SyncError("CURRENT_NOT_ATOMIC", f"refusing to replace non-symlink path: {link}")
    link.parent.mkdir(parents=True, exist_ok=True)
    temp = link.with_name(f".{link.name}.tmp-{os.getpid()}-{uuid4().hex[:8]}")
    try:
        os.symlink(str(target), str(temp), target_is_directory=True)
        os.replace(temp, link)
    finally:
        temp.unlink(missing_ok=True)


def _entrypoint_dir(root: Path, node: str) -> Path:
    if node == "mac" and root == default_local_root().expanduser().resolve():
        return Path.home() / ".dharma" / "bin"
    return root / "bin"


def _install_wrappers(root: Path, release: Path, *, node: str) -> dict[str, str]:
    bin_dir = _entrypoint_dir(root, node)
    bin_dir.mkdir(parents=True, exist_ok=True)
    targets = {
        "rsi": release / "repo" / "scripts" / "forge_lab" / "rsi",
        "rsi-lab-env": release / "repo" / "scripts" / "forge_lab" / "rsi-env",
        "rsi-operator-history": release
        / "repo"
        / "scripts"
        / "forge_lab"
        / "operator-history",
    }
    if node != "meghadharma":
        targets["rsi-env"] = targets["rsi-lab-env"]
    if node == "meghadharma":
        targets["rsi-update-main"] = (
            release / "repo" / "scripts" / "forge_lab" / "rsi-sync-retired"
        )
    installed: dict[str, str] = {}
    for name, target in targets.items():
        if not target.is_file():
            raise SyncError("WRAPPER_MISSING", f"release wrapper is missing: {target}")
        link = bin_dir / name
        if _path_present(link):
            correct = link.is_symlink() and link.resolve(strict=False) == target.resolve(
                strict=False
            )
            if not correct:
                stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
                backup = bin_dir / f"{name}.legacy-{stamp}-{uuid4().hex[:8]}"
                os.replace(link, backup)
                installed[f"{name}_backup"] = str(backup)
        _atomic_symlink(target, link)
        installed[name] = str(link)
    return installed


def _write_receipt(root: Path, payload: dict[str, Any]) -> Path:
    safe_request = re.sub(r"[^A-Za-z0-9._-]+", "-", str(payload["request_id"]))
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    nonce = uuid4().hex[:8]
    path = root / "receipts" / f"{stamp}__{safe_request}__{payload['action']}__{nonce}.json"
    _atomic_json(path, payload)
    return path


def activate_release(
    plan: dict[str, Any],
    root: Path,
    *,
    node: str,
    request_id: str,
    expected_current: str | None,
    action: str = "apply",
    require_canonical_head: bool = True,
) -> dict[str, Any]:
    plan = validate_plan(plan)
    request_id = _validate_request_id(request_id)
    root = root.expanduser().resolve()
    release = root / "releases" / plan["commit"]
    manifest_path = release / "RELEASE_MANIFEST.json"
    if not manifest_path.is_file():
        raise SyncError("RELEASE_NOT_PREPARED", f"release is not prepared: {release}")
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        embedded_plan = validate_plan(manifest.get("plan", {}))
    except (OSError, json.JSONDecodeError, SyncError) as exc:
        raise SyncError("RELEASE_MANIFEST_MISMATCH", f"release manifest is invalid: {exc}") from exc
    if (
        manifest.get("schema") != RELEASE_SCHEMA
        or manifest.get("plan_digest") != plan["plan_digest"]
        or embedded_plan != plan
    ):
        raise SyncError("RELEASE_MANIFEST_MISMATCH", "release manifest does not match the plan")
    _verify_release(release, plan)
    if require_canonical_head and _remote_head() != plan["commit"]:
        raise SyncError("STALE_PLAN", "canonical branch moved before activation")
    guard = _campaign_guard(root)
    if not guard["ok"]:
        raise SyncError("ACTIVE_CAMPAIGN", "; ".join(guard["reasons"]))

    before_target = _current_target(root)
    before_commit = _current_commit(root)
    if expected_current is not None and before_commit != expected_current:
        raise SyncError(
            "CONCURRENT_SWITCH",
            f"current release changed concurrently: expected {expected_current}, found {before_commit}",
        )
    _atomic_symlink(release, root / "current")
    try:
        wrappers = _install_wrappers(root, release, node=node)
        readback = _checkout_identity((root / "current" / "repo").resolve())
        mismatches = _identity_mismatches(readback, plan)
        if mismatches:
            raise SyncError("ACTIVATION_READBACK_FAILED", ", ".join(mismatches))
    except Exception:
        if before_target is not None:
            _atomic_symlink(before_target, root / "current")
        else:
            (root / "current").unlink(missing_ok=True)
        raise
    receipt_payload = {
        "schema": RECEIPT_SCHEMA,
        "created_at": _now(),
        "request_id": request_id,
        "action": action,
        "node": node,
        "plan_digest": plan["plan_digest"],
        "previous_commit": before_commit,
        "previous_target": str(before_target) if before_target else None,
        "target_commit": plan["commit"],
        "target_release": str(release),
        "readback_identity": readback,
        "runtime": _runtime_fingerprint(release),
        "guard": guard,
        "wrappers": wrappers,
        "synced_mutable_state": False,
        "provider_calls": False,
    }
    receipt = _write_receipt(root, receipt_payload)
    return {
        "node": node,
        "commit": plan["commit"],
        "previous_commit": before_commit,
        "release": str(release),
        "receipt": str(receipt),
        "wrappers": wrappers,
    }


@contextlib.contextmanager
def _file_lock(root: Path) -> Iterator[None]:
    import fcntl

    root.mkdir(parents=True, exist_ok=True)
    path = root / "sync.lock"
    with path.open("a+", encoding="utf-8") as handle:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            raise SyncError("SYNC_LOCKED", f"another synchronization holds {path}") from exc
        yield


def _decode_plan(value: str) -> dict[str, Any]:
    try:
        decoded = base64.urlsafe_b64decode(value.encode("ascii"))
        plan = json.loads(decoded)
    except (ValueError, UnicodeError, json.JSONDecodeError) as exc:
        raise SyncError("INVALID_PLAN", "remote plan encoding is invalid") from exc
    if not isinstance(plan, dict):
        raise SyncError("INVALID_PLAN", "remote plan is not an object")
    return validate_plan(plan)


def _node_entry() -> int:
    action = os.environ.get("RSI_SYNC_NODE_ACTION", "")
    root = Path(os.environ.get("RSI_SYNC_ROOT", str(DEFAULT_REMOTE_ROOT)))
    node = os.environ.get("RSI_SYNC_NODE", "meghadharma")
    try:
        if action == "status":
            result = node_status(root, node=node)
        else:
            plan = _decode_plan(os.environ.get("RSI_SYNC_PLAN_B64", ""))
            if action == "prepare":
                with _file_lock(root):
                    result = prepare_release(plan, root, node=node)
            elif action == "activate":
                expected = os.environ.get("RSI_SYNC_EXPECTED_CURRENT") or None
                require_head = os.environ.get("RSI_SYNC_REQUIRE_HEAD", "1") == "1"
                with _file_lock(root):
                    result = activate_release(
                        plan,
                        root,
                        node=node,
                        request_id=os.environ.get("RSI_SYNC_REQUEST_ID", ""),
                        expected_current=expected,
                        action="apply" if require_head else "rollback",
                        require_canonical_head=require_head,
                    )
            else:
                raise SyncError("INVALID_NODE_ACTION", f"unsupported node action: {action!r}")
        print(json.dumps({"ok": True, "result": result}, sort_keys=True))
        return 0
    except SyncError as exc:
        print(
            json.dumps(
                {"ok": False, "error": {"code": exc.code, "message": str(exc)}},
                sort_keys=True,
            )
        )
        return 1
    except Exception as exc:  # pragma: no cover - last-resort remote protocol guard
        print(
            json.dumps(
                {
                    "ok": False,
                    "error": {"code": "UNEXPECTED_NODE_ERROR", "message": str(exc)},
                },
                sort_keys=True,
            )
        )
        return 1


if __name__ == "__main__" and os.environ.get("RSI_SYNC_NODE_ACTION"):
    raise SystemExit(_node_entry())
