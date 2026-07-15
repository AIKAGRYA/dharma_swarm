"""Mac-side orchestration for exact RSI Lab code releases."""

from __future__ import annotations

import base64
import json
import os
import subprocess
from pathlib import Path
from typing import Any

from dharma_swarm.forge_lab import sync_control as core


SyncError = core.SyncError
DEFAULT_REMOTE = core.DEFAULT_REMOTE


def create_plan(root: Path | None = None) -> tuple[dict[str, Any], Path]:
    """Resolve the canonical ref once and persist its content-addressed plan."""

    root = (root or core.default_local_root()).expanduser().resolve()
    commit = core._remote_head()
    cache = core._fetch_canonical(root, commit)
    identity = core._object_identity(cache, commit)
    plan: dict[str, Any] = {
        "schema": core.PLAN_SCHEMA,
        "created_at": core._now(),
        "canonical_repository": core.CANONICAL_REPOSITORY,
        "canonical_ref": core.CANONICAL_REF,
        **identity,
        "targets": {
            "mac": str(root),
            "meghadharma": str(core.DEFAULT_REMOTE_ROOT),
        },
        "exactness_contract": {
            "equal": [
                "commit",
                "tree",
                "uv_lock_sha256",
                "critical_files",
                "forge_package_version",
                "repo_clean",
            ],
            "host_specific": [
                "os",
                "machine",
                "python_executable",
                "python_version",
            ],
            "excluded_from_sync": [
                "state",
                "archives",
                "sqlite",
                "wal",
                "secrets",
                "oauth",
                "provider_credentials",
            ],
        },
        "verification_tests": list(core.VERIFICATION_TESTS),
    }
    plan["plan_digest"] = core.plan_digest(plan)
    digest = plan["plan_digest"].split(":", 1)[1]
    path = root / "plans" / f"{digest}.json"
    core._atomic_json(path, plan)
    return plan, path


def load_plan(reference: str, root: Path | None = None) -> tuple[dict[str, Any], Path]:
    root = (root or core.default_local_root()).expanduser().resolve()
    digest_match = core._DIGEST_RE.fullmatch(reference)
    if digest_match:
        path = root / "plans" / f"{digest_match.group(1)}.json"
    else:
        path = Path(reference).expanduser().resolve()
    try:
        plan = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SyncError(
            "PLAN_UNREADABLE", f"could not read plan {path}: {exc}"
        ) from exc
    if not isinstance(plan, dict):
        raise SyncError("INVALID_PLAN", "plan root must be a JSON object")
    core.validate_plan(plan)
    return plan, path


def _local_venv() -> Path:
    configured = os.environ.get("RSI_LAB_LOCAL_VENV")
    candidates = [
        Path(configured).expanduser() if configured else None,
        Path.home() / "dharma_swarm" / ".venv",
    ]
    for candidate in candidates:
        if candidate and (candidate / "bin" / "python").exists():
            return candidate.resolve()
    raise SyncError(
        "RUNTIME_MISSING",
        "set RSI_LAB_LOCAL_VENV to a Python 3.11+ environment for the Mac release",
    )


def _encode_plan(plan: dict[str, Any]) -> str:
    return base64.urlsafe_b64encode(core._canonical_json(plan)).decode("ascii")


def _node_source() -> str:
    """Bundle the exact stdlib-only node modules into one SSH stdin program."""

    package = "dharma_swarm.forge_lab"
    module_paths = (
        (f"{package}.sync_identity", Path(core.__file__).with_name("sync_identity.py")),
        (f"{package}.sync_node", Path(core.__file__).with_name("sync_node.py")),
    )
    lines = ["import sys", "import types"]
    for module_name, path in module_paths:
        source = path.read_text(encoding="utf-8")
        lines.extend(
            (
                f"_module = types.ModuleType({module_name!r})",
                f"_module.__file__ = {str(path)!r}",
                f"_module.__package__ = {package!r}",
                f"sys.modules[{module_name!r}] = _module",
                f"exec(compile({source!r}, _module.__file__, 'exec'), _module.__dict__)",
            )
        )
    control_path = Path(core.__file__)
    control_source = control_path.read_text(encoding="utf-8")
    lines.append(
        f"exec(compile({control_source!r}, {str(control_path)!r}, 'exec'), globals())"
    )
    return "\n".join(lines) + "\n"


def _ssh_node(
    action: str,
    *,
    remote: str,
    plan: dict[str, Any] | None = None,
    request_id: str = "",
    expected_current: str | None = None,
    require_canonical_head: bool = True,
) -> dict[str, Any]:
    remote = core._validate_remote(remote)
    assignments = [
        f"RSI_SYNC_NODE_ACTION={action}",
        f"RSI_SYNC_ROOT={core.DEFAULT_REMOTE_ROOT}",
        "RSI_SYNC_NODE=meghadharma",
        f"RSI_SYNC_REQUIRE_HEAD={'1' if require_canonical_head else '0'}",
    ]
    if plan is not None:
        assignments.append(f"RSI_SYNC_PLAN_B64={_encode_plan(plan)}")
    if request_id:
        assignments.append(
            f"RSI_SYNC_REQUEST_ID={core._validate_request_id(request_id)}"
        )
    if expected_current:
        assignments.append(
            f"RSI_SYNC_EXPECTED_CURRENT={core._validate_sha(expected_current)}"
        )
    source = _node_source()
    command = [
        "ssh",
        *core.SSH_OPTIONS,
        remote,
        "env",
        *assignments,
        "python3",
        "-",
    ]
    try:
        result = subprocess.run(
            command,
            input=source,
            capture_output=True,
            check=False,
            text=True,
            timeout=1200,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise SyncError(
            "REMOTE_UNAVAILABLE", f"could not execute on {remote}: {exc}"
        ) from exc
    try:
        envelope = json.loads(result.stdout.strip())
    except json.JSONDecodeError as exc:
        detail = (result.stderr or result.stdout).strip()[-1200:]
        raise SyncError(
            "REMOTE_PROTOCOL_ERROR", f"invalid response from {remote}: {detail}"
        ) from exc
    if result.returncode != 0 or not envelope.get("ok"):
        error = envelope.get("error", {})
        raise SyncError(
            str(error.get("code", "REMOTE_FAILED")),
            str(error.get("message", result.stderr.strip() or "remote action failed")),
        )
    return envelope["result"]


def sync_status(
    *,
    root: Path | None = None,
    remote: str = DEFAULT_REMOTE,
) -> dict[str, Any]:
    root = (root or core.default_local_root()).expanduser().resolve()
    remote = core._validate_remote(remote)
    canonical_commit: str | None = None
    failures: list[str] = []
    try:
        canonical_commit = core._remote_head()
    except SyncError as exc:
        failures.append(f"github:{exc.code}:{exc}")
    local = core.node_status(root, node="mac")
    try:
        remote_status = _ssh_node("status", remote=remote)
    except SyncError as exc:
        remote_status = {"node": "meghadharma", "ready": False, "errors": [str(exc)]}
        failures.append(f"meghadharma:{exc.code}:{exc}")

    local_identity = local.get("identity") or {}
    remote_identity = remote_status.get("identity") or {}
    for node, status in (("mac", local), ("meghadharma", remote_status)):
        if not status.get("ready"):
            failures.append(f"{node}:not_ready")
    if canonical_commit and local_identity.get("commit") != canonical_commit:
        failures.append("mac:commit_differs_from_github")
    if canonical_commit and remote_identity.get("commit") != canonical_commit:
        failures.append("meghadharma:commit_differs_from_github")
    for field in (
        "commit",
        "tree",
        "uv_lock_sha256",
        "critical_files",
        "forge_package_version",
        "repo_clean",
    ):
        if local_identity.get(field) != remote_identity.get(field):
            failures.append(f"nodes:{field}_mismatch")
    if local.get("release_manifest_digest") != remote_status.get(
        "release_manifest_digest"
    ):
        failures.append("nodes:release_manifest_digest_mismatch")
    failures = list(dict.fromkeys(failures))
    return {
        "schema": core.STATUS_SCHEMA,
        "checked_at": core._now(),
        "canonical": {
            "repository": core.CANONICAL_REPOSITORY,
            "ref": core.CANONICAL_REF,
            "commit": canonical_commit,
        },
        "mac": local,
        "meghadharma": remote_status,
        "in_sync": not failures,
        "failures": failures,
        "claim": (
            "exact code identity only; platform runtimes are separately attested and "
            "mutable state/secrets are excluded"
        ),
    }


def apply_plan(
    plan: dict[str, Any],
    *,
    request_id: str,
    root: Path | None = None,
    remote: str = DEFAULT_REMOTE,
) -> dict[str, Any]:
    plan = core.validate_plan(plan)
    request_id = core._validate_request_id(request_id)
    root = (root or core.default_local_root()).expanduser().resolve()
    remote = core._validate_remote(remote)
    if core._remote_head() != plan["commit"]:
        raise SyncError("STALE_PLAN", "canonical branch moved; create a fresh plan")

    with core._file_lock(root):
        local_prepared = core.prepare_release(
            plan, root, node="mac", local_venv=_local_venv()
        )
        remote_prepared = _ssh_node("prepare", remote=remote, plan=plan)
        remote_activated = _ssh_node(
            "activate",
            remote=remote,
            plan=plan,
            request_id=request_id,
            expected_current=remote_prepared.get("previous_commit"),
        )
        local_activated = core.activate_release(
            plan,
            root,
            node="mac",
            request_id=request_id,
            expected_current=local_prepared.get("previous_commit"),
        )

    status = sync_status(root=root, remote=remote)
    if not status["in_sync"]:
        raise SyncError(
            "POST_APPLY_DRIFT",
            "activation completed but cross-host readback is not exact: "
            + ", ".join(status["failures"]),
        )
    orchestration = {
        "schema": core.RECEIPT_SCHEMA,
        "created_at": core._now(),
        "request_id": request_id,
        "action": "orchestrate-apply",
        "node": "mac",
        "plan_digest": plan["plan_digest"],
        "target_commit": plan["commit"],
        "local_prepare": local_prepared,
        "remote_prepare": remote_prepared,
        "local_activation_receipt": local_activated["receipt"],
        "remote_activation_receipt": remote_activated["receipt"],
        "post_apply_in_sync": True,
        "synced_mutable_state": False,
        "provider_calls": False,
    }
    receipt = core._write_receipt(root, orchestration)
    return {
        "commit": plan["commit"],
        "plan_digest": plan["plan_digest"],
        "mac": local_activated,
        "meghadharma": remote_activated,
        "receipt": str(receipt),
        "status": status,
    }


def converge(
    *,
    request_id: str,
    root: Path | None = None,
    remote: str = DEFAULT_REMOTE,
) -> dict[str, Any]:
    plan, path = create_plan(root)
    result = apply_plan(plan, request_id=request_id, root=root, remote=remote)
    result["plan_path"] = str(path)
    return result


def rollback(
    commit: str,
    *,
    request_id: str,
    root: Path | None = None,
    remote: str = DEFAULT_REMOTE,
) -> dict[str, Any]:
    commit = core._validate_sha(commit)
    request_id = core._validate_request_id(request_id)
    root = (root or core.default_local_root()).expanduser().resolve()
    remote = core._validate_remote(remote)
    manifest_path = root / "releases" / commit / "RELEASE_MANIFEST.json"
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        plan = core.validate_plan(manifest["plan"])
    except (OSError, KeyError, json.JSONDecodeError) as exc:
        raise SyncError(
            "ROLLBACK_RELEASE_MISSING", f"rollback release is unavailable: {exc}"
        ) from exc
    with core._file_lock(root):
        remote_before = _ssh_node("status", remote=remote).get("identity") or {}
        local_before = core._current_commit(root)
        remote_result = _ssh_node(
            "activate",
            remote=remote,
            plan=plan,
            request_id=request_id,
            expected_current=remote_before.get("commit"),
            require_canonical_head=False,
        )
        local_result = core.activate_release(
            plan,
            root,
            node="mac",
            request_id=request_id,
            expected_current=local_before,
            action="rollback",
            require_canonical_head=False,
        )
    return {
        "commit": commit,
        "plan_digest": plan["plan_digest"],
        "mac": local_result,
        "meghadharma": remote_result,
        "intentional_github_drift": commit != core._remote_head(),
    }
