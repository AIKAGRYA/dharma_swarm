"""Credential-free model-role activation for the versioned RSI Lab.

This module is an activation profile over the canonical ``model_pool``.  It is
deliberately *not* a provider registry: only exact provider/model routes that
already exist in source may be selected.  Planning is pure and never probes a
provider.  Applying or rolling back changes only host-owned Forge Lab state,
with compare-and-swap protection, immutable profiles, and append-only receipts.

An active profile grants role-selection authority only.  It does not attest
availability or quality, change weights, load credentials, edit source, call a
provider, or authorize candidate promotion.
"""

from __future__ import annotations

import fcntl
from collections.abc import Mapping
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

from dharma_swarm.forge_lab.model_onboarding_contract import (
    CATALOG_SCHEMA,
    CLAIM_BOUNDARY,
    PLAN_SCHEMA,
    PROFILE_SCHEMA,
    RECEIPT_SCHEMA,
    RESULT_SCHEMA,
    ROLE_ORDER,
    STATUS_SCHEMA,
    ModelOnboardingError,
    ModelRole,
    RoleBinding,
    _signed,
    _unsigned,
    _validate_plan,
    _validate_profile,
    list_supported_routes,
    plan_activation,
)
from dharma_swarm.forge_lab.state_io import (
    atomic_json,
    content_digest,
    forge_state_root,
    now_utc,
    safe_json,
    validate_digest,
    validate_safe_id,
    write_json_exclusive,
)
from dharma_swarm.forge_lab.version import (
    PACKAGE_VERSION,
    source_commit,
    source_tree_state,
)


def _activation_root() -> Path:
    return forge_state_root() / "model_onboarding"


def _current_path() -> Path:
    return _activation_root() / "current.json"


def _profile_path(digest: str) -> Path:
    validate_digest(digest)
    return _activation_root() / "profiles" / f"{digest.removeprefix('sha256:')}.json"


def _receipt_path(request_id: str) -> Path:
    validate_safe_id(request_id, field="request_id")
    return _activation_root() / "receipts" / f"{request_id}.json"


def _load_profile(digest: str) -> dict[str, Any]:
    path = _profile_path(digest)
    payload = safe_json(path)
    if payload is None:
        raise ModelOnboardingError("PROFILE_NOT_FOUND", f"profile not found: {digest}")
    profile = _validate_profile(payload)
    if profile["profile_digest"] != digest:
        raise ModelOnboardingError("PROFILE_INVALID", "profile path/digest mismatch")
    return profile


def _load_current() -> dict[str, Any] | None:
    path = _current_path()
    if not path.exists():
        return None
    payload = safe_json(path)
    if payload is None:
        raise ModelOnboardingError("CURRENT_PROFILE_INVALID", "current profile is unreadable")
    return _validate_profile(payload)


@contextmanager
def _activation_lock() -> Iterator[None]:
    path = _activation_root() / "control.lock"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+", encoding="utf-8") as handle:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            raise ModelOnboardingError(
                "ACTIVATION_BUSY", "another model-role activation holds the lock"
            ) from exc
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def _request_receipt(request_id: str) -> dict[str, Any] | None:
    path = _receipt_path(request_id)
    if not path.exists():
        return None
    receipt = safe_json(path)
    if receipt is None or receipt.get("schema") != RECEIPT_SCHEMA:
        raise ModelOnboardingError("RECEIPT_INVALID", "request receipt is unreadable")
    if receipt.get("receipt_digest") != content_digest(_unsigned(receipt, "receipt_digest")):
        raise ModelOnboardingError("RECEIPT_INVALID", "request receipt digest mismatch")
    return receipt


def _idempotent_result(
    receipt: Mapping[str, Any],
    *,
    action: str,
    intent_digest: str | None,
) -> dict[str, Any]:
    if receipt.get("action") != action or receipt.get("intent_digest") != intent_digest:
        raise ModelOnboardingError(
            "REQUEST_ID_REUSED", "request_id already belongs to another activation intent"
        )
    current = _load_current()
    if current is None or current.get("profile_digest") != receipt.get("result_profile_digest"):
        raise ModelOnboardingError(
            "REQUEST_STATE_MISMATCH", "request receipt does not match the current profile"
        )
    return _result_payload(current, receipt, idempotent=True)


def _new_profile(
    *,
    bindings: list[dict[str, Any]],
    staged_models: list[str],
    generation: int,
    previous_profile_digest: str | None,
    request_id: str,
    action: str,
    plan_digest: str | None,
    rollback_target_digest: str | None,
) -> dict[str, Any]:
    return _signed(
        {
            "schema": PROFILE_SCHEMA,
            "generation": generation,
            "bindings": bindings,
            "staged_models": staged_models,
            "previous_profile_digest": previous_profile_digest,
            "rollback_target_digest": rollback_target_digest,
            "activation": {
                "action": action,
                "request_id": request_id,
                "plan_digest": plan_digest,
                "activated_at": now_utc(),
            },
            "source": {
                "package_version": PACKAGE_VERSION,
                "commit": source_commit(),
                "tree_state": source_tree_state(),
            },
            "claim_boundary": dict(CLAIM_BOUNDARY),
        },
        "profile_digest",
    )


def _write_transition(
    *,
    profile: dict[str, Any],
    previous: dict[str, Any] | None,
    request_id: str,
    action: str,
    intent_digest: str | None,
    expected_current_digest: str | None,
    target_profile_digest: str | None,
) -> dict[str, Any]:
    profile_path = _profile_path(str(profile["profile_digest"]))
    try:
        write_json_exclusive(profile_path, profile)
    except FileExistsError:
        if safe_json(profile_path) != profile:
            raise ModelOnboardingError("PROFILE_COLLISION", "profile digest collision")

    atomic_json(_current_path(), profile)
    receipt = _signed(
        {
            "schema": RECEIPT_SCHEMA,
            "created_at": now_utc(),
            "request_id": request_id,
            "action": action,
            "intent_digest": intent_digest,
            "expected_current_digest": expected_current_digest,
            "previous_profile_digest": previous.get("profile_digest") if previous else None,
            "result_profile_digest": profile["profile_digest"],
            "target_profile_digest": target_profile_digest,
            "generation": profile["generation"],
            "bindings": profile["bindings"],
            "staged_models": profile["staged_models"],
            "claim_boundary": dict(CLAIM_BOUNDARY),
        },
        "receipt_digest",
    )
    receipt_path = _receipt_path(request_id)
    try:
        write_json_exclusive(receipt_path, receipt)
    except Exception:
        if previous is None:
            _current_path().unlink(missing_ok=True)
        else:
            atomic_json(_current_path(), previous)
        raise
    return _result_payload(profile, receipt, idempotent=False)


def _result_payload(
    profile: Mapping[str, Any],
    receipt: Mapping[str, Any],
    *,
    idempotent: bool,
) -> dict[str, Any]:
    return {
        "schema": RESULT_SCHEMA,
        "action": receipt["action"],
        "request_id": receipt["request_id"],
        "idempotent": idempotent,
        "profile_digest": profile["profile_digest"],
        "generation": profile["generation"],
        "role_bindings": profile["bindings"],
        "staged_models": profile["staged_models"],
        "receipt": str(_receipt_path(str(receipt["request_id"]))),
        "claim_boundary": dict(CLAIM_BOUNDARY),
    }


def apply_activation(
    plan: Mapping[str, Any],
    *,
    request_id: str,
    expected_current_digest: str | None,
) -> dict[str, Any]:
    """Atomically activate one ready plan with explicit CAS protection."""

    try:
        validate_safe_id(request_id, field="request_id")
        if expected_current_digest is not None:
            validate_digest(expected_current_digest)
    except ValueError as exc:
        raise ModelOnboardingError("INVALID_REQUEST", str(exc)) from exc
    validated = _validate_plan(plan)
    if validated["outcome"] != "ready":
        raise ModelOnboardingError(
            "PLAN_NOT_APPLICABLE", f"activation plan outcome is {validated['outcome']}"
        )

    with _activation_lock():
        existing = _request_receipt(request_id)
        if existing is not None:
            return _idempotent_result(
                existing, action="apply", intent_digest=validated["plan_digest"]
            )
        current = _load_current()
        actual = current.get("profile_digest") if current else None
        if actual != expected_current_digest:
            raise ModelOnboardingError(
                "CONCURRENT_ACTIVATION",
                f"current profile changed: expected {expected_current_digest}, found {actual}",
            )
        if validated["base_profile_digest"] != actual:
            raise ModelOnboardingError(
                "STALE_PLAN", "activation plan was built against another current profile"
            )
        profile = _new_profile(
            bindings=list(validated["bindings"]),
            staged_models=list(validated["staged_models"]),
            generation=int(current["generation"]) + 1 if current else 1,
            previous_profile_digest=actual,
            request_id=request_id,
            action="apply",
            plan_digest=validated["plan_digest"],
            rollback_target_digest=None,
        )
        return _write_transition(
            profile=profile,
            previous=current,
            request_id=request_id,
            action="apply",
            intent_digest=validated["plan_digest"],
            expected_current_digest=expected_current_digest,
            target_profile_digest=None,
        )


def _ancestor_profiles(current: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    ancestors: dict[str, dict[str, Any]] = {}
    digest = current.get("previous_profile_digest")
    while digest is not None:
        digest = str(digest)
        if digest in ancestors or digest == current.get("profile_digest"):
            raise ModelOnboardingError("PROFILE_LINEAGE_INVALID", "profile lineage contains a cycle")
        profile = _load_profile(digest)
        ancestors[digest] = profile
        digest = profile.get("previous_profile_digest")
    return ancestors


def rollback_activation(
    *,
    request_id: str,
    expected_current_digest: str,
    target_profile_digest: str | None = None,
) -> dict[str, Any]:
    """Activate bindings from a prior profile as a new monotonic generation."""

    try:
        validate_safe_id(request_id, field="request_id")
        validate_digest(expected_current_digest)
        if target_profile_digest is not None:
            validate_digest(target_profile_digest)
    except ValueError as exc:
        raise ModelOnboardingError("INVALID_REQUEST", str(exc)) from exc

    with _activation_lock():
        existing = _request_receipt(request_id)
        intent_digest = target_profile_digest
        if existing is not None:
            return _idempotent_result(
                existing, action="rollback", intent_digest=intent_digest
            )
        current = _load_current()
        if current is None:
            raise ModelOnboardingError("NO_ACTIVE_PROFILE", "there is no profile to roll back")
        actual = str(current["profile_digest"])
        if actual != expected_current_digest:
            raise ModelOnboardingError(
                "CONCURRENT_ACTIVATION",
                f"current profile changed: expected {expected_current_digest}, found {actual}",
            )
        ancestors = _ancestor_profiles(current)
        target_digest = target_profile_digest or current.get("previous_profile_digest")
        if target_digest is None:
            raise ModelOnboardingError("NO_ROLLBACK_TARGET", "current profile has no predecessor")
        target_digest = str(target_digest)
        if target_digest not in ancestors:
            raise ModelOnboardingError(
                "ROLLBACK_TARGET_INVALID", "target profile is not an ancestor of current"
            )
        target = ancestors[target_digest]
        profile = _new_profile(
            bindings=list(target["bindings"]),
            staged_models=list(target["staged_models"]),
            generation=int(current["generation"]) + 1,
            previous_profile_digest=actual,
            request_id=request_id,
            action="rollback",
            plan_digest=None,
            rollback_target_digest=target_digest,
        )
        return _write_transition(
            profile=profile,
            previous=current,
            request_id=request_id,
            action="rollback",
            intent_digest=target_profile_digest,
            expected_current_digest=expected_current_digest,
            target_profile_digest=target_digest,
        )


def activation_status() -> dict[str, Any]:
    """Return current exact bindings and ordered staged model IDs, without calls."""

    current = _load_current()
    receipts_root = _activation_root() / "receipts"
    receipt_count = len(list(receipts_root.glob("*.json"))) if receipts_root.is_dir() else 0
    if current is None:
        return {
            "schema": STATUS_SCHEMA,
            "active": False,
            "integrity": "absent",
            "current_profile_digest": None,
            "generation": 0,
            "role_bindings": [],
            "staged_models": [],
            "previous_profile_digest": None,
            "rollback_target_digest": None,
            "last_action": None,
            "receipt_count": receipt_count,
            "claim_boundary": dict(CLAIM_BOUNDARY),
        }
    activation = current.get("activation") or {}
    return {
        "schema": STATUS_SCHEMA,
        "active": True,
        "integrity": "verified",
        "current_profile_digest": current["profile_digest"],
        "generation": current["generation"],
        "role_bindings": current["bindings"],
        "staged_models": current["staged_models"],
        "previous_profile_digest": current.get("previous_profile_digest"),
        "rollback_target_digest": current.get("rollback_target_digest"),
        "last_action": activation.get("action"),
        "receipt_count": receipt_count,
        "claim_boundary": dict(CLAIM_BOUNDARY),
    }


__all__ = [
    "CATALOG_SCHEMA",
    "CLAIM_BOUNDARY",
    "ModelOnboardingError",
    "ModelRole",
    "PLAN_SCHEMA",
    "PROFILE_SCHEMA",
    "RECEIPT_SCHEMA",
    "RESULT_SCHEMA",
    "ROLE_ORDER",
    "RoleBinding",
    "STATUS_SCHEMA",
    "activation_status",
    "apply_activation",
    "list_supported_routes",
    "plan_activation",
    "rollback_activation",
]
