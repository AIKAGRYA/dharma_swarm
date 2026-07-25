"""Identity, plan, and Git primitives for RSI Lab release synchronization."""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence
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
    "dharma_swarm/forge_lab/cli.py",
    "dharma_swarm/forge_lab/campaign_actions.py",
    "dharma_swarm/forge_lab/campaign_attempts.py",
    "dharma_swarm/forge_lab/campaign_authority.py",
    "dharma_swarm/forge_lab/campaign_cli.py",
    "dharma_swarm/forge_lab/campaign_contract.py",
    "dharma_swarm/forge_lab/campaign_envelope.py",
    "dharma_swarm/forge_lab/campaign_control.py",
    "dharma_swarm/forge_lab/campaign_gates.py",
    "dharma_swarm/forge_lab/campaign_profile.py",
    "dharma_swarm/forge_lab/campaign_reconcile.py",
    "dharma_swarm/forge_lab/campaign_reconcile_db.py",
    "dharma_swarm/forge_lab/campaign_receipts.py",
    "dharma_swarm/forge_lab/campaign_store.py",
    "dharma_swarm/forge_lab/campaign_store_schema.py",
    "dharma_swarm/forge_lab/campaign_usage.py",
    "dharma_swarm/forge_lab/campaign_watchdog.py",
    "dharma_swarm/forge_lab/campaign_watchdog_cli.py",
    "dharma_swarm/forge_lab/newrun.py",
    "dharma_swarm/forge_lab/provider_selftest.py",
    "dharma_swarm/forge_lab/provider_selftest_cli.py",
    "dharma_swarm/forge_lab/sync_control.py",
    "dharma_swarm/forge_lab/sync_identity.py",
    "dharma_swarm/forge_lab/sync_node.py",
    "dharma_swarm/forge_lab/sync_orchestrator.py",
    "dharma_swarm/forge_lab/operator_history.py",
    "dharma_swarm/forge_lab/operator_history_discovery.py",
    "dharma_swarm/forge_lab/operator_history_sources.py",
    "dharma_swarm/forge_lab/operator_history_values.py",
    "dharma_swarm/forge_lab/operator_history_projection.py",
    "dharma_swarm/forge_lab/operator_history_native_scorecard.py",
    "dharma_swarm/forge_lab/operator_history_rendering.py",
    "dharma_swarm/forge_lab/operator_history_run_scorecard.py",
    "dharma_swarm/forge_lab/operator_history_scorecards.py",
    "dharma_swarm/forge_v1/canonical.py",
    "dharma_swarm/forge_v1/providers.py",
    "dharma_swarm/forge_v1/forge_v2/runner_slots.py",
    "scripts/forge_lab/rsi",
    "scripts/forge_lab/RSILAB",
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
    "tests/forge_lab_v1/test_campaign_admission.py",
    "tests/forge_lab_v1/test_campaign_lifecycle.py",
    "tests/forge_lab_v1/test_campaign_reconcile.py",
    "tests/forge_lab_v1/test_campaign_store_contract.py",
    "tests/forge_lab_v1/test_campaign_store_safety.py",
    "tests/forge_lab_v1/test_campaign_watchdog.py",
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
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
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
        raise SyncError(
            "COMMAND_UNAVAILABLE", f"command failed to run: {command[0]}: {exc}"
        ) from exc
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
        raise SyncError(
            "COMMAND_UNAVAILABLE", f"command failed to run: {command[0]}: {exc}"
        ) from exc
    if result.returncode != 0:
        detail = result.stderr.decode("utf-8", errors="replace").strip()[-1200:]
        raise SyncError(
            "COMMAND_FAILED",
            f"{command[0]} exited {result.returncode}: {detail or 'no diagnostic'}",
        )
    return result.stdout


def _validate_sha(value: str, *, field: str = "commit") -> str:
    if not _SHA_RE.fullmatch(value):
        raise SyncError(
            "INVALID_IDENTITY", f"{field} must be a full lowercase 40-character SHA"
        )
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
        raise SyncError(
            "REMOTE_NOT_ALLOWED", f"remote host is not allowlisted: {remote!r}"
        )
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


def _fetch_canonical(
    root: Path,
    expected_commit: str | None = None,
    *,
    repository: str = CANONICAL_REPOSITORY,
) -> Path:
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
            repository,
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
            "refs/heads/rsi-lab-canonical",
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


def validate_plan(
    plan: dict[str, Any],
    *,
    repository: str = CANONICAL_REPOSITORY,
    ref: str = CANONICAL_REF,
    critical_files: Sequence[str] = CRITICAL_FILES,
    verification_tests: Sequence[str] = VERIFICATION_TESTS,
) -> dict[str, Any]:
    if plan.get("schema") != PLAN_SCHEMA:
        raise SyncError(
            "INVALID_PLAN", f"unsupported plan schema: {plan.get('schema')!r}"
        )
    if plan.get("canonical_repository") != repository:
        raise SyncError(
            "INVALID_PLAN", "plan repository is not the canonical RSI repository"
        )
    if plan.get("canonical_ref") != ref:
        raise SyncError("INVALID_PLAN", "plan ref is not the canonical RSI branch")
    _validate_sha(str(plan.get("commit", "")))
    _validate_sha(str(plan.get("tree", "")), field="tree")
    expected_digest = plan_digest(plan)
    if plan.get("plan_digest") != expected_digest:
        raise SyncError(
            "PLAN_TAMPERED", "plan content does not match its SHA-256 digest"
        )
    critical = plan.get("critical_files")
    if not isinstance(critical, dict) or set(critical) != set(critical_files):
        raise SyncError(
            "INVALID_PLAN", "plan critical-file set is incomplete or unexpected"
        )
    if any(
        not re.fullmatch(r"[0-9a-f]{64}", str(value)) for value in critical.values()
    ):
        raise SyncError("INVALID_PLAN", "plan contains an invalid critical-file digest")
    if plan.get("uv_lock_sha256") != critical.get("uv.lock"):
        raise SyncError("INVALID_PLAN", "uv.lock identity is internally inconsistent")
    if plan.get("verification_tests") != list(verification_tests):
        raise SyncError("INVALID_PLAN", "verification test contract is not canonical")
    return plan


def _checkout_identity(repo: Path) -> dict[str, Any]:
    if not (repo / ".git").exists():
        raise SyncError(
            "RELEASE_INVALID", f"release checkout has no Git metadata: {repo}"
        )
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
