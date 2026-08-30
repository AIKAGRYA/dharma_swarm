"""Pre-spend admission gates for the bounded unattended EXPLORE runner.

Split out of ``unattended_explore`` to keep both modules under the repo's
500-line budget (CLAUDE.md law; SOVEREIGN_MANIFEST axiom A5). The parent
module re-exports every name defined here.
"""

from __future__ import annotations

import os
import stat
from pathlib import Path
from typing import Any

from dharma_swarm.forge_lab.model_onboarding import activation_status
from dharma_swarm.forge_lab.operator_views import doctor
from dharma_swarm.forge_lab.provider_selftest import validate_provider_receipt
from dharma_swarm.forge_lab.reconciliation_view import (
    composite_reconciliation_status as reconciliation_status,
)
from dharma_swarm.forge_lab.source_guard import require_execution_source
from dharma_swarm.forge_lab.state_io import safe_json
from dharma_swarm.forge_lab.unattended_child_support import (
    lexists as _lexists,
)
from dharma_swarm.forge_lab.unattended_context import (
    UnattendedContextError,
    load_admitted_task_context,
    sanitize_unattended_docker_env,
)
from dharma_swarm.forge_lab.unattended_model_evidence import (
    ModelEvidenceError,
    selected_model_evidence,
)
from dharma_swarm.forge_lab.unattended_policy import (
    MODEL_ROLES,
    PROVIDER_TTL_SECONDS,
    UnattendedError,
)


def _selected_model_evidence(provider_check: dict[str, Any]) -> dict[str, Any]:
    """Bind active role assignments to one fresh, exact provider receipt."""

    try:
        return selected_model_evidence(
            provider_check,
            model_roles=MODEL_ROLES,
            activation_status_fn=activation_status,
            validate_provider_receipt_fn=validate_provider_receipt,
            safe_json_fn=safe_json,
        )
    except ModelEvidenceError as exc:
        raise UnattendedError(exc.code, str(exc)) from exc


def _validated_state_root(value: Path) -> Path:
    raw = value.expanduser()
    if not raw.is_absolute() or raw == Path("/"):
        raise UnattendedError(
            "STATE_ROOT_UNSAFE", "state root must be a non-root absolute path"
        )
    for label, path in (
        ("state_root", raw),
        ("dharma_home", raw / ".dharma"),
        ("forge_root", raw / ".dharma" / "forge_lab"),
    ):
        try:
            metadata = path.lstat()
        except FileNotFoundError:
            if label == "state_root":
                raise UnattendedError("STATE_ROOT_UNSAFE", f"state root is missing: {raw}")
            continue
        except OSError as exc:
            raise UnattendedError("STATE_ROOT_UNSAFE", f"cannot inspect {path}") from exc
        if (
            stat.S_ISLNK(metadata.st_mode)
            or not stat.S_ISDIR(metadata.st_mode)
            or metadata.st_uid != os.geteuid()
            or stat.S_IMODE(metadata.st_mode) & 0o022
        ):
            raise UnattendedError(
                "STATE_ROOT_UNSAFE",
                f"{label} must be an owner-controlled real directory: {path}",
            )
    try:
        resolved = raw.resolve(strict=True)
    except OSError as exc:
        raise UnattendedError("STATE_ROOT_UNSAFE", f"cannot resolve {raw}") from exc
    if resolved != raw:
        raise UnattendedError("STATE_ROOT_UNSAFE", f"state root is not canonical: {raw}")
    forge_root = (resolved / ".dharma" / "forge_lab").resolve(strict=False)
    if forge_root != resolved and not forge_root.is_relative_to(resolved):
        raise UnattendedError("STATE_ROOT_UNSAFE", "forge root escaped state root")
    return resolved


def admission_status(state_root: Path) -> dict[str, Any]:
    """Evaluate all pre-spend gates and return selected redacted route IDs."""

    reasons: list[str] = []
    try:
        state_root = _validated_state_root(state_root)
    except UnattendedError as exc:
        return {
            "ready": False,
            "reasons": [f"{exc.code}:{exc}"],
            "halt_path": None,
            "source": {},
            "doctor": {},
            "reconciliation": {},
            "routes": [],
            "role_bindings": {},
            "model_profile_digest": None,
            "provider_receipt_digest": None,
            "task_id": None,
            "task_context_binding": None,
        }
    sanitize_unattended_docker_env()
    halt = state_root / ".dharma" / "forge_lab" / "HALT"
    if _lexists(halt):
        reasons.append(f"HALT_present:{halt}")
    if os.environ.get("RSI_LAB_DEV_SOURCE") == "1":
        reasons.append("development_source_forbidden")
    configured_state = os.environ.get("RSI_LAB_STATE", "").strip()
    try:
        configured_state_root = (
            Path(configured_state).expanduser().resolve(strict=True)
            if configured_state
            else None
        )
    except OSError:
        configured_state_root = None
    if configured_state_root != state_root:
        reasons.append("explicit_state_root_not_anchored")
    try:
        source = require_execution_source()
    except RuntimeError as exc:
        source = {"ready": False, "reasons": [str(exc)]}
        reasons.append("immutable_source_gate_failed")
    try:
        report = doctor()
    except Exception as exc:
        report = {"ok": False, "error": f"{type(exc).__name__}:{exc}"[:500]}
        reasons.append("doctor_unavailable")
    if not report.get("ok"):
        reasons.append("doctor_not_ready")
    try:
        reconciliation = reconciliation_status()
    except Exception as exc:
        reconciliation = {
            "ok": False,
            "error": f"{type(exc).__name__}:{exc}"[:500],
        }
        reasons.append("reconciliation_unavailable")
    if not reconciliation.get("ok"):
        reasons.append("control_plane_reconciliation_required")
    provider_check = ((report.get("checks") or {}).get("providers") or {})
    if int(provider_check.get("ttl_seconds") or 0) > PROVIDER_TTL_SECONDS:
        reasons.append("provider_ttl_policy_too_weak")
    try:
        model_evidence = (
            _selected_model_evidence(provider_check) if provider_check.get("ready") else {}
        )
    except UnattendedError as exc:
        reasons.append(f"{exc.code}:{exc}")
        model_evidence = {}
    routes = model_evidence.get("routes") or []
    role_bindings = model_evidence.get("role_bindings") or {}
    grader = ((report.get("checks") or {}).get("grader") or {})
    if not grader.get("ready") or not grader.get("docker_daemon_reachable"):
        reasons.append("isolated_docker_grader_not_ready")
    taskbed = ((report.get("checks") or {}).get("taskbed") or {})
    task_id = str(taskbed.get("next_explore_task_id") or "").strip()
    if not taskbed.get("ready") or not task_id:
        reasons.append("state_anchored_isolated_task_unavailable")
    task_context_binding: dict[str, Any] | None = None
    if task_id:
        try:
            _task, _context, task_context_binding = load_admitted_task_context(
                task_id,
                state_root=state_root,
            )
        except UnattendedContextError as exc:
            reasons.append(f"{exc.code}:{exc}")
    return {
        "ready": not reasons and set(role_bindings) == set(MODEL_ROLES) and len(routes) >= 2,
        "reasons": reasons,
        "halt_path": str(halt),
        "source": source,
        "doctor": report,
        "reconciliation": reconciliation,
        "routes": routes,
        "role_bindings": role_bindings,
        "model_profile_digest": model_evidence.get("model_profile_digest"),
        "provider_receipt_digest": model_evidence.get("provider_receipt_digest"),
        "task_id": task_id or None,
        "task_context_binding": task_context_binding,
    }
