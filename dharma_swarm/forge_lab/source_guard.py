"""Immutable-source admission for any RSI command that can execute work."""

from __future__ import annotations

import json
import os
import re
import stat
import subprocess
from pathlib import Path
from typing import Any

CANONICAL_REPOSITORY = "https://github.com/AIKAGRYA/dharma_swarm.git"
_SHA_RE = re.compile(r"^[0-9a-f]{40}$")


def _sealed_digest(payload: dict[str, Any], field: str) -> str:
    from dharma_swarm.forge_lab.sync_identity import _canonical_json, _sha256_bytes

    unsigned = {key: value for key, value in payload.items() if key != field}
    return "sha256:" + _sha256_bytes(_canonical_json(unsigned))


def _regular_json(path: Path) -> dict[str, Any] | None:
    try:
        info = path.lstat()
        if (
            path.is_symlink()
            or not stat.S_ISREG(info.st_mode)
            or info.st_uid != os.geteuid()
            or info.st_mode & 0o022
            or info.st_size > 4 * 1024 * 1024
        ):
            return None
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def _git(repo: Path, *args: str) -> tuple[int, str]:
    try:
        result = subprocess.run(
            ["git", "--no-optional-locks", "-C", str(repo), *args],
            capture_output=True,
            check=False,
            text=True,
            timeout=10,
            env={
                "PATH": "/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin",
                "GIT_CONFIG_NOSYSTEM": "1",
                "GIT_OPTIONAL_LOCKS": "0",
            },
        )
    except (OSError, subprocess.SubprocessError):
        return 127, ""
    return result.returncode, result.stdout.strip()


def _release_manifest(repo: Path) -> dict[str, Any] | None:
    path = repo.parent / "RELEASE_MANIFEST.json"
    return _regular_json(path)


def _activation_receipt(
    root: Path,
    *,
    commit: str,
    plan_digest: str,
    release: Path,
    identity: dict[str, Any],
) -> tuple[dict[str, Any] | None, str | None]:
    from dharma_swarm.forge_lab.sync_identity import RECEIPT_SCHEMA

    receipt_root = root / "receipts"
    if not receipt_root.is_dir() or receipt_root.is_symlink():
        return None, "activation_receipt_root_missing_or_unsafe"
    for path in sorted(receipt_root.glob("*.json"), reverse=True):
        payload = _regular_json(path)
        if payload is None:
            continue
        if payload.get("target_commit") != commit:
            continue
        if (
            payload.get("schema") != RECEIPT_SCHEMA
            or payload.get("plan_digest") != plan_digest
            or payload.get("target_release") != str(release)
            or payload.get("readback_identity") != identity
            or payload.get("receipt_path") != str(path)
            or payload.get("receipt_digest") != _sealed_digest(payload, "receipt_digest")
            or payload.get("synced_mutable_state") is not False
            or payload.get("provider_calls") is not False
            or not isinstance(payload.get("guard"), dict)
            or payload["guard"].get("ok") is not True
        ):
            return None, "activation_receipt_invalid"
        return payload, None
    return None, "activation_receipt_missing"


def execution_source_status(repo: Path | None = None) -> dict[str, Any]:
    """Return immutable-release evidence without changing the checkout."""

    configured_text = os.environ.get("RSI_LAB_REPO", "").strip()
    configured = repo or (Path(configured_text) if configured_text else None)
    if configured is None:
        base = Path(os.environ.get("RSI_LAB_BASE", Path.home() / ".dharma/rsi-lab/current"))
        configured = base / "repo"
    source = configured.expanduser().resolve(strict=False)
    reasons: list[str] = []

    base_text = os.environ.get("RSI_LAB_BASE", "").strip()
    expected = (
        (Path(base_text).expanduser().resolve(strict=False) / "repo").resolve(strict=False)
        if base_text
        else source
    )
    if source != expected:
        reasons.append("source_not_under_resolved_RSI_LAB_BASE")
    if not source.is_dir():
        reasons.append("source_checkout_missing")

    head_code, head = _git(source, "rev-parse", "HEAD")
    if head_code != 0 or not _SHA_RE.fullmatch(head):
        reasons.append("source_commit_unavailable")
    status_code, dirty = _git(source, "status", "--porcelain", "--untracked-files=normal")
    if status_code != 0:
        reasons.append("source_cleanliness_unavailable")
    elif dirty:
        reasons.append("source_checkout_dirty")
    remote_code, remote = _git(source, "config", "--get", "remote.origin.url")
    if remote_code != 0 or remote != CANONICAL_REPOSITORY:
        reasons.append("source_remote_not_canonical_AIKAGRYA")

    manifest = _release_manifest(source)
    plan: dict[str, Any] | None = None
    manifest_commit = str((((manifest or {}).get("plan") or {}).get("commit") or ""))
    release = source.parent
    root = release.parent.parent if release.parent.name == "releases" else None
    identity: dict[str, Any] | None = None
    receipt: dict[str, Any] | None = None
    if manifest is None:
        reasons.append("release_manifest_missing")
    else:
        try:
            from dharma_swarm.forge_lab.sync_identity import (
                CANONICAL_REF,
                RELEASE_SCHEMA,
                _checkout_identity,
                _identity_mismatches,
                validate_plan,
            )

            raw_plan = manifest.get("plan")
            if not isinstance(raw_plan, dict):
                raise ValueError("embedded plan missing")
            plan = validate_plan(raw_plan)
            if (
                set(manifest)
                != {
                    "schema",
                    "plan_digest",
                    "plan",
                    "prepared_at",
                    "node",
                    "release",
                    "reused",
                    "verification",
                    "manifest_digest",
                }
                or manifest.get("schema") != RELEASE_SCHEMA
                or manifest.get("plan_digest") != plan["plan_digest"]
                or manifest.get("manifest_digest")
                != _sealed_digest(manifest, "manifest_digest")
                or manifest.get("release") != str(release)
                or plan.get("canonical_repository") != CANONICAL_REPOSITORY
                or plan.get("canonical_ref") != CANONICAL_REF
            ):
                reasons.append("release_manifest_contract_invalid")
            identity = _checkout_identity(source)
            if _identity_mismatches(identity, plan):
                reasons.append("release_checkout_identity_mismatch")
            verification = manifest.get("verification")
            offline = (
                verification.get("offline")
                if isinstance(verification, dict)
                else None
            )
            expected_command = "python -m pytest -q -p no:cacheprovider " + " ".join(
                plan["verification_tests"]
            )
            if (
                not isinstance(verification, dict)
                or verification.get("identity") != identity
                or not isinstance(verification.get("runtime"), dict)
                or verification["runtime"].get("python_compatible") is not True
                or not isinstance(offline, dict)
                or offline.get("network_or_provider_calls") is not False
                or offline.get("command") != expected_command
            ):
                reasons.append("release_verification_evidence_invalid")
        except Exception:
            reasons.append("release_manifest_or_identity_invalid")
    if manifest is not None and manifest_commit != head:
        reasons.append("release_manifest_commit_mismatch")
    if head and release.name != head:
        reasons.append("release_directory_not_full_commit")
    if root is None:
        reasons.append("release_not_under_versioned_root")
    elif head and plan is not None and identity is not None:
        current = root / "current"
        if not current.is_symlink() or current.resolve(strict=False) != release:
            reasons.append("release_not_current_atomic_target")
        cache = root / "cache" / "dharma_swarm.git"
        # ``_git`` always injects -C, so use a direct bounded invocation for a
        # bare repository instead of trusting checkout-local refs.
        try:
            cached = subprocess.run(
                [
                    "git",
                    "--no-optional-locks",
                    "--git-dir",
                    str(cache),
                    "rev-parse",
                    "refs/heads/rsi-lab-canonical^{commit}",
                ],
                capture_output=True,
                check=False,
                text=True,
                timeout=10,
                env={
                    "PATH": "/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin",
                    "GIT_CONFIG_NOSYSTEM": "1",
                    "GIT_OPTIONAL_LOCKS": "0",
                },
            )
            cached_ref = cached.stdout.strip()
            ref_code = cached.returncode
        except (OSError, subprocess.SubprocessError):
            ref_code, cached_ref = 127, ""
        if ref_code != 0 or cached_ref != head:
            reasons.append("canonical_ref_cache_proof_missing_or_mismatch")
        receipt, receipt_error = _activation_receipt(
            root,
            commit=head,
            plan_digest=str(plan["plan_digest"]),
            release=release,
            identity=identity,
        )
        if receipt_error:
            reasons.append(receipt_error)

    return {
        "ready": not reasons,
        "repo": str(source),
        "expected_repo": str(expected),
        "commit": head or None,
        "remote": remote or None,
        "canonical_repository": CANONICAL_REPOSITORY,
        "release_manifest_present": manifest is not None,
        "release_manifest_commit": manifest_commit or None,
        "release_manifest_digest": (manifest or {}).get("manifest_digest"),
        "canonical_ref": ((plan or {}).get("canonical_ref")),
        "plan_digest": ((plan or {}).get("plan_digest")),
        "activation_receipt": receipt.get("receipt_path") if receipt else None,
        "activation_receipt_digest": receipt.get("receipt_digest") if receipt else None,
        "reasons": reasons,
    }


def require_execution_source(repo: Path | None = None) -> dict[str, Any]:
    status = execution_source_status(repo)
    if not status["ready"]:
        raise RuntimeError("noncanonical execution source: " + ",".join(status["reasons"]))
    return status


__all__ = ["CANONICAL_REPOSITORY", "execution_source_status", "require_execution_source"]
