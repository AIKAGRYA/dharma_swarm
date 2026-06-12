"""Runtime warrant gate for side-effecting spine surfaces.

A warrant is not a new truth store. It is a small permission receipt recorded
in the existing RuntimeStateStore before a command performs a side effect.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field, replace
from typing import TYPE_CHECKING, Any

from dharma_swarm.spine.identity import ExecutionIdentity, MissingExecutionIdentity

if TYPE_CHECKING:
    from dharma_swarm.runtime_state import RuntimeStateStore

_CLAIM_TOKEN_RE = re.compile(r"[^a-z0-9]+")

PROHIBITED_PRE_ACTION_CLAIMS = frozenset(
    {
        "completed",
        "done",
        "domain_receipted",
        "external_human_served",
        "live_contact",
        "live_trading",
        "revenue_live",
        "runtime_fully_saturated",
        "self_evolution_autonomous",
        "semantic_reply",
    }
)

SURFACE_PRE_ACTION_CLAIMS = {
    ("scripts/runtime/a2a_send.py", "publish"): frozenset(
        {
            "a2a_publish_attempt",
            "broker_publish_attempt",
            "publish_only",
            "runtime_receipt_pending",
        }
    ),
    ("scripts/runtime/autonomy_spine.py", "kernel_wake"): frozenset(
        {
            "kernel_wake_attempt",
            "kernel_closeback_pending",
            "runtime_receipt_pending",
        }
    ),
}


class RuntimeWarrantDenied(PermissionError):
    """Raised when a side effect lacks permission to proceed."""

    def __init__(self, reason: str, *, warrant: "RuntimeWarrant | None" = None) -> None:
        super().__init__(reason)
        self.warrant = warrant


@dataclass(frozen=True, slots=True)
class RuntimeWarrant:
    warrant_id: str
    status: str
    surface: str
    action: str
    side_effect_key: str
    allowed_claims: tuple[str, ...]
    requested_claims: tuple[str, ...]
    blocked_claims: tuple[str, ...] = ()
    reason: str = ""
    receipt_id: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_ref(self) -> dict[str, Any]:
        return {
            "warrant_id": self.warrant_id,
            "receipt_id": self.receipt_id,
            "status": self.status,
            "surface": self.surface,
            "action": self.action,
            "side_effect_key": self.side_effect_key,
            "idempotency_record_ref": str(self.metadata.get("idempotency_record_ref") or ""),
            "allowed_claims": list(self.allowed_claims),
            "blocked_claims": list(self.blocked_claims),
        }


def _normalize_claim(value: Any) -> str:
    raw = str(value or "").strip().lower()
    return re.sub(r"_+", "_", _CLAIM_TOKEN_RE.sub("_", raw)).strip("_")


def _clean_claims(values: tuple[str, ...] | list[str] | set[str] | frozenset[str]) -> tuple[str, ...]:
    return tuple(sorted({claim for value in values if (claim := _normalize_claim(value))}))


def _warrant_id(identity: ExecutionIdentity, *, surface: str, action: str, side_effect_key: str) -> str:
    digest = hashlib.sha256(
        json.dumps(
            {
                "run_id": identity.run_id,
                "surface": surface,
                "action": action,
                "side_effect_key": side_effect_key,
            },
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()
    return f"warrant_{digest[:24]}"


def _record_warrant_receipt(
    *,
    store: "RuntimeStateStore",
    identity: ExecutionIdentity,
    warrant: RuntimeWarrant,
) -> RuntimeWarrant:
    from dharma_swarm.runtime_state import RuntimeReceipt

    receipt_id = f"rr_{identity.run_id}_{warrant.warrant_id}_{warrant.status}"
    payload = {
        **dict(warrant.metadata),
        "warrant_id": warrant.warrant_id,
        "surface": warrant.surface,
        "action": warrant.action,
        "requested_claims": list(warrant.requested_claims),
        "allowed_claims": list(warrant.allowed_claims),
        "blocked_claims": list(warrant.blocked_claims),
        "reason": warrant.reason,
    }
    store.record_runtime_receipt_sync(
        RuntimeReceipt(
            receipt_id=receipt_id,
            receipt_type="runtime_warrant",
            status=warrant.status,
            run_id=identity.run_id,
            task_id=identity.task_id,
            trace_id=identity.trace_id,
            correlation_id=identity.correlation_id,
            causation_id=identity.causation_id,
            parent_run_id=identity.parent_run_id,
            agent_id=identity.agent_id,
            idempotency_key=identity.idempotency_key,
            side_effect_key=warrant.side_effect_key,
            payload=payload,
        )
    )
    return RuntimeWarrant(
        warrant_id=warrant.warrant_id,
        status=warrant.status,
        surface=warrant.surface,
        action=warrant.action,
        side_effect_key=warrant.side_effect_key,
        allowed_claims=warrant.allowed_claims,
        requested_claims=warrant.requested_claims,
        blocked_claims=warrant.blocked_claims,
        reason=warrant.reason,
        receipt_id=receipt_id,
        metadata=warrant.metadata,
    )


def _idempotency_record_ref(identity: ExecutionIdentity, side_effect_key: str) -> str:
    return f"idempotency_records:{identity.idempotency_key}:{side_effect_key}"


def _idempotency_record_mismatches(record: Any, identity: ExecutionIdentity) -> tuple[str, ...]:
    mismatches: list[str] = []
    for field_name in ("run_id", "task_id", "trace_id", "correlation_id"):
        if str(getattr(record, field_name, "") or "") != str(getattr(identity, field_name, "") or ""):
            mismatches.append(field_name)
    if str(getattr(record, "status", "") or "") != "started":
        mismatches.append("status")
    return tuple(mismatches)


def issue_runtime_warrant(
    *,
    store: "RuntimeStateStore",
    identity: ExecutionIdentity,
    surface: str,
    action: str,
    side_effect_key: str,
    idempotency_inserted: bool,
    requested_claims: tuple[str, ...] | list[str] | set[str] | frozenset[str],
    metadata: dict[str, Any] | None = None,
) -> RuntimeWarrant:
    """Record and return a permission warrant, or fail closed before action."""
    try:
        identity = identity.require_for_dispatch()
    except MissingExecutionIdentity as exc:
        raise RuntimeWarrantDenied(str(exc)) from exc

    clean_surface = str(surface or "").strip()
    clean_action = _normalize_claim(action)
    clean_side_effect_key = str(side_effect_key or "").strip()
    allowed = SURFACE_PRE_ACTION_CLAIMS.get((clean_surface, clean_action))
    requested = _clean_claims(requested_claims)
    prohibited = tuple(claim for claim in requested if claim in PROHIBITED_PRE_ACTION_CLAIMS)
    unknown = tuple(claim for claim in requested if allowed is not None and claim not in allowed)
    blocked = tuple(sorted(set(prohibited + unknown)))
    warrant_id = _warrant_id(
        identity,
        surface=clean_surface,
        action=clean_action,
        side_effect_key=clean_side_effect_key,
    )
    base = RuntimeWarrant(
        warrant_id=warrant_id,
        status="granted",
        surface=clean_surface,
        action=clean_action,
        side_effect_key=clean_side_effect_key,
        allowed_claims=tuple(sorted(allowed or ())),
        requested_claims=requested,
        metadata=dict(metadata or {}),
    )

    if not clean_side_effect_key:
        denied = replace(
            base,
            status="blocked",
            blocked_claims=requested,
            reason="runtime warrant requires side_effect_key before side effect",
        )
        recorded = _record_warrant_receipt(store=store, identity=identity, warrant=denied)
        raise RuntimeWarrantDenied(recorded.reason, warrant=recorded)

    if allowed is None:
        denied = replace(
            base,
            status="blocked",
            blocked_claims=requested,
            reason="no runtime warrant policy for surface/action",
        )
        recorded = _record_warrant_receipt(store=store, identity=identity, warrant=denied)
        raise RuntimeWarrantDenied(recorded.reason, warrant=recorded)

    if not requested:
        denied = replace(
            base,
            status="blocked",
            reason="runtime warrant requires at least one requested claim",
        )
        recorded = _record_warrant_receipt(store=store, identity=identity, warrant=denied)
        raise RuntimeWarrantDenied(recorded.reason, warrant=recorded)

    if not idempotency_inserted:
        denied = replace(
            base,
            status="blocked",
            blocked_claims=requested,
            reason="idempotency was not claimed before side effect",
        )
        recorded = _record_warrant_receipt(store=store, identity=identity, warrant=denied)
        raise RuntimeWarrantDenied(recorded.reason, warrant=recorded)

    idempotency_record = store.get_idempotency_record_sync(identity.idempotency_key, clean_side_effect_key)
    if idempotency_record is None:
        denied = replace(
            base,
            status="blocked",
            blocked_claims=requested,
            reason="idempotency record missing before side effect",
        )
        recorded = _record_warrant_receipt(store=store, identity=identity, warrant=denied)
        raise RuntimeWarrantDenied(recorded.reason, warrant=recorded)

    idempotency_mismatches = _idempotency_record_mismatches(idempotency_record, identity)
    if idempotency_mismatches:
        denied = replace(
            base,
            status="blocked",
            blocked_claims=requested,
            reason="idempotency record does not match execution identity",
            metadata={
                **base.metadata,
                "idempotency_record_ref": _idempotency_record_ref(identity, clean_side_effect_key),
                "idempotency_mismatches": list(idempotency_mismatches),
                "idempotency_record_status": str(getattr(idempotency_record, "status", "") or ""),
            },
        )
        recorded = _record_warrant_receipt(store=store, identity=identity, warrant=denied)
        raise RuntimeWarrantDenied(recorded.reason, warrant=recorded)

    base = replace(
        base,
        metadata={
            **base.metadata,
            "idempotency_record_ref": _idempotency_record_ref(identity, clean_side_effect_key),
        },
    )

    if blocked:
        denied = replace(
            base,
            status="blocked",
            blocked_claims=blocked,
            reason="requested claim is not allowed before side effect",
        )
        recorded = _record_warrant_receipt(store=store, identity=identity, warrant=denied)
        raise RuntimeWarrantDenied(recorded.reason, warrant=recorded)

    return _record_warrant_receipt(store=store, identity=identity, warrant=base)
