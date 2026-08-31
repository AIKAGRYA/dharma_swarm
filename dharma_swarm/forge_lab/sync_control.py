"""Content-addressed synchronization for the Forge RSI Lab.

GitHub owns code identity. Mac and Meghadharma consume immutable code releases;
mutable state, archives, credentials, and SQLite/WAL files remain host-owned.
The remote bootstrap streams this facade with its exact helper modules.
"""

from __future__ import annotations

import base64
import contextlib
import json
import os
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator
from uuid import uuid4

from dharma_swarm.forge_lab.sync_identity import (
    CANONICAL_REF as CANONICAL_REF,
    CANONICAL_REPOSITORY as CANONICAL_REPOSITORY,
    CRITICAL_FILES as CRITICAL_FILES,
    DEFAULT_REMOTE as DEFAULT_REMOTE,
    DEFAULT_REMOTE_ROOT as DEFAULT_REMOTE_ROOT,
    PLAN_SCHEMA as PLAN_SCHEMA,
    RECEIPT_SCHEMA as RECEIPT_SCHEMA,
    RELEASE_SCHEMA as RELEASE_SCHEMA,
    SSH_OPTIONS as SSH_OPTIONS,
    STATUS_SCHEMA as STATUS_SCHEMA,
    VERIFICATION_TESTS as VERIFICATION_TESTS,
    SyncError as SyncError,
    _DIGEST_RE as _DIGEST_RE,
    _atomic_json as _atomic_json,
    _cache_path as _cache_path,
    _canonical_json as _canonical_json,
    _checkout_identity as _checkout_identity,
    _fetch_canonical as _fetch_canonical_impl,
    _identity_mismatches as _identity_mismatches,
    _now as _now,
    _object_identity as _object_identity,
    _remote_head as _remote_head,
    _run as _run,
    _run_bytes as _run_bytes,
    _sha256_bytes as _sha256_bytes,
    _sha256_file as _sha256_file,
    _validate_remote as _validate_remote,
    _validate_request_id as _validate_request_id,
    _validate_sha as _validate_sha,
    default_local_root as default_local_root,
    plan_digest as plan_digest,
    validate_plan as _validate_plan_impl,
)
from dharma_swarm.forge_lab.sync_campaign_guard import (
    _campaign_guard as _campaign_guard,
    _foreground_campaign_argv as _foreground_campaign_argv,
)
from dharma_swarm.forge_lab.sync_node import (
    _current_commit as _current_commit,
    _current_target as _current_target,
    _ensure_release_links as _ensure_release_links,
    _path_present as _path_present,
    _run_offline_verification as _run_offline_verification,
    _runtime_fingerprint as _runtime_fingerprint,
    _safe_symlink as _safe_symlink,
    _stabilize_anchors as _stabilize_anchors,
    _verify_release as _verify_release,
    node_status as node_status,
)


def _fetch_canonical(root: Path, expected_commit: str | None = None) -> Path:
    return _fetch_canonical_impl(
        root,
        expected_commit,
        repository=CANONICAL_REPOSITORY,
    )


def validate_plan(plan: dict[str, Any]) -> dict[str, Any]:
    return _validate_plan_impl(
        plan,
        repository=CANONICAL_REPOSITORY,
        ref=CANONICAL_REF,
        critical_files=CRITICAL_FILES,
        verification_tests=VERIFICATION_TESTS,
    )


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
        raise SyncError(
            "STALE_PLAN", "canonical branch moved after this plan was created"
        )
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
                    "--no-checkout",
                    "--branch",
                    "rsi-lab-canonical",
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
        "previous_target": str(_current_target(root))
        if _current_target(root)
        else None,
        "reused": reused,
        "verification": manifest["verification"],
    }


def _atomic_symlink(target: Path, link: Path) -> None:
    if _path_present(link) and not link.is_symlink():
        raise SyncError(
            "CURRENT_NOT_ATOMIC", f"refusing to replace non-symlink path: {link}"
        )
    link.parent.mkdir(parents=True, exist_ok=True)
    temp = link.with_name(f".{link.name}.tmp-{os.getpid()}-{uuid4().hex[:8]}")
    try:
        os.symlink(str(target), str(temp), target_is_directory=True)
        os.replace(temp, link)
    finally:
        temp.unlink(missing_ok=True)


def _entrypoint_dir(root: Path, node: str) -> Path:
    if node == "mac" and root == default_local_root().expanduser().resolve():
        # This module is exec'd on the remote node as a stdlib-only SSH bundle
        # (sync_orchestrator._node_source), so it cannot import the canonical
        # state-dir owner; expanduser keeps the anchor without a
        # ``Path.home() / ".dharma"`` substrate reference (ANTI_SLOP Rule 1).
        return Path(os.path.expanduser("~/.dharma")) / "bin"
    return root / "bin"


def _install_wrappers(root: Path, release: Path, *, node: str) -> dict[str, str]:
    bin_dir = _entrypoint_dir(root, node)
    bin_dir.mkdir(parents=True, exist_ok=True)
    targets = {
        "rsi": release / "repo" / "scripts" / "forge_lab" / "rsi",
        "RSILAB": release / "repo" / "scripts" / "forge_lab" / "RSILAB",
        "rsi-lab-env": release / "repo" / "scripts" / "forge_lab" / "rsi-env",
        "rsi-operator-history": release
        / "repo"
        / "scripts"
        / "forge_lab"
        / "operator-history",
        "rsi-provider-refresh": release
        / "repo"
        / "scripts"
        / "forge_lab"
        / "rsi-provider-refresh",
        "rsi-provider-refresh-install": release
        / "repo"
        / "scripts"
        / "forge_lab"
        / "rsi-provider-refresh-install",
        "rsi-unattended-explore": release
        / "repo"
        / "scripts"
        / "forge_lab"
        / "rsi-unattended-explore",
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
            correct = link.is_symlink() and link.resolve(
                strict=False
            ) == target.resolve(strict=False)
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
    path = (
        root
        / "receipts"
        / f"{stamp}__{safe_request}__{payload['action']}__{nonce}.json"
    )
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
        raise SyncError(
            "RELEASE_MANIFEST_MISMATCH", f"release manifest is invalid: {exc}"
        ) from exc
    if (
        manifest.get("schema") != RELEASE_SCHEMA
        or manifest.get("plan_digest") != plan["plan_digest"]
        or embedded_plan != plan
    ):
        raise SyncError(
            "RELEASE_MANIFEST_MISMATCH", "release manifest does not match the plan"
        )
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
            raise SyncError(
                "SYNC_LOCKED", f"another synchronization holds {path}"
            ) from exc
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
                raise SyncError(
                    "INVALID_NODE_ACTION", f"unsupported node action: {action!r}"
                )
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
