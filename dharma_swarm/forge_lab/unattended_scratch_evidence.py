"""Typed evidence validation for unattended scratch custody."""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

from dharma_swarm.forge_lab.state_io import content_digest, validate_safe_id

SCRATCH_PROOF_SCHEMA = "rsi_lab.unattended_scratch_proof.v1"

_DIGEST_RE = re.compile(r"^sha256:[0-9a-f]{64}$")


def exact_root_identity(value: Any) -> bool:
    """Return whether *value* is one exact filesystem root identity."""

    return bool(
        isinstance(value, dict)
        and set(value) == {"device", "inode"}
        and type(value.get("device")) is int
        and type(value.get("inode")) is int
        and value.get("device", -1) >= 0
        and value.get("inode", 0) > 0
    )


def run_root(state_root: Path, run_id: str) -> Path:
    """Return the deterministic lexical run root without creating it."""

    try:
        safe_run_id = validate_safe_id(run_id, field="run_id")
    except ValueError as exc:
        raise ValueError(str(exc)) from exc
    raw_state = state_root.expanduser()
    if not raw_state.is_absolute() or raw_state == Path("/"):
        raise ValueError("state_root must be an absolute non-root path")
    return raw_state / ".dharma" / "evolution_worktrees" / "unattended" / safe_run_id


def validate_scratch_proof(
    proof: Any,
    *,
    operation: str,
    scratch_root: Path,
    run_id: str,
    expected_root_identity: dict[str, int] | None = None,
    expected_marker_digest: str | None = None,
) -> bool:
    """Validate one exact typed scratch authority proof."""

    if not isinstance(proof, dict):
        return False
    expected_keys = {
        "schema",
        "operation",
        "ok",
        "scratch_root",
        "run_id",
        "root_identity",
        "marker_digest",
        "inventory",
        "code",
        "message",
        "proof_digest",
    }
    identity = proof.get("root_identity")
    marker_digest = proof.get("marker_digest")
    if (
        set(proof) != expected_keys
        or proof.get("schema") != SCRATCH_PROOF_SCHEMA
        or proof.get("operation") != operation
        or proof.get("ok") is not True
        or proof.get("scratch_root") != str(scratch_root)
        or proof.get("run_id") != run_id
        or not exact_root_identity(identity)
        or (expected_root_identity is not None and identity != expected_root_identity)
        or not isinstance(marker_digest, str)
        or not _DIGEST_RE.fullmatch(marker_digest)
        or (
            expected_marker_digest is not None
            and marker_digest != expected_marker_digest
        )
        or proof.get("code") is not None
        or proof.get("message") is not None
        or proof.get("proof_digest")
        != content_digest(
            {key: value for key, value in proof.items() if key != "proof_digest"}
        )
    ):
        return False
    inventory = proof.get("inventory")
    if operation in {"create", "attest"}:
        return inventory is None
    if operation != "cleanup" or not isinstance(inventory, dict):
        return False
    expected_inventory_keys = {
        "entries",
        "directories",
        "regular_files",
        "symlinks",
        "bytes",
        "inventory_digest",
        "run_id",
    }
    return bool(
        set(inventory) == expected_inventory_keys
        and inventory.get("run_id") == run_id
        and all(
            type(inventory.get(key)) is int and inventory.get(key, -1) >= 0
            for key in (
                "entries",
                "directories",
                "regular_files",
                "symlinks",
                "bytes",
            )
        )
        and inventory.get("entries")
        == inventory.get("directories")
        + inventory.get("regular_files")
        + inventory.get("symlinks")
        and inventory.get("regular_files", 0) >= 1
        and isinstance(inventory.get("inventory_digest"), str)
        and _DIGEST_RE.fullmatch(inventory["inventory_digest"])
    )


def validate_parent_scratch_proofs(
    create_proof: Any,
    cleanup_proof: Any,
    *,
    state_root: Path,
    run_id: str,
    require_absent: bool = True,
) -> bool:
    """Require one inode-bound create→cleanup authority chain."""

    scratch_root = run_root(state_root, run_id)
    if not validate_scratch_proof(
        create_proof,
        operation="create",
        scratch_root=scratch_root,
        run_id=run_id,
    ):
        return False
    return bool(
        validate_scratch_proof(
            cleanup_proof,
            operation="cleanup",
            scratch_root=scratch_root,
            run_id=run_id,
            expected_root_identity=create_proof["root_identity"],
            expected_marker_digest=create_proof["marker_digest"],
        )
        and (not require_absent or not os.path.lexists(scratch_root))
    )


__all__ = [
    "SCRATCH_PROOF_SCHEMA",
    "exact_root_identity",
    "run_root",
    "validate_parent_scratch_proofs",
    "validate_scratch_proof",
]
