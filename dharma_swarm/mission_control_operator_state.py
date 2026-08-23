"""Pure value contract for authoritative campaign pause and resume state."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping
from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any

OPERATOR_CONTROL_STATE_SCHEMA = "dharma.sadhana.operator_control_state.v1"
OPERATOR_CONTROL_RECEIPT_SCHEMA = "dharma.sadhana.operator_control_receipt.v1"
OPERATOR_CONTROL_RECEIPT_TYPE = "mission_campaign_operator_control"
OPERATOR_CONTROL_RECEIPT_REF_PREFIX = "runtime-receipt:"

OPERATOR_CONTROL_STATE_FIELDS = frozenset(
    {
        "schema_version",
        "control_state",
        "campaign_generation",
        "transition_sequence",
        "request_id",
        "idempotency_key",
        "action",
        "source_envelope_sha256",
        "authority_receipt_ref",
        "authority_receipt_sha256",
        "authority_applied_at",
        "effect_state",
        "effect_receipt_ref",
        "effect_receipt_sha256",
        "effect_observed_at",
    }
)

_CONTROL_STATES = frozenset({"RUNNING", "PAUSED", "STOPPED_TERMINAL"})
_ACTIONS = frozenset({"", "pause", "resume", "emergency_stop"})
_IDENTIFIER_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}")
_SHA256_RE = re.compile(r"sha256:[0-9a-f]{64}")
_UTC_TIMESTAMP_RE = re.compile(
    r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?Z"
)


def canonical_utc_timestamp(value: datetime) -> str:
    """Render one aware timestamp in the strict mobile/read-model UTC form."""
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("operator control timestamp must be timezone-aware")
    return value.astimezone(timezone.utc).isoformat().removesuffix("+00:00") + "Z"


def initial_operator_control_state(generation: int) -> dict[str, Any]:
    """Return the exact no-claim read-model value for one campaign generation."""
    if isinstance(generation, bool) or not isinstance(generation, int) or generation < 1:
        raise ValueError("operator control generation must be positive")
    return {
        "schema_version": OPERATOR_CONTROL_STATE_SCHEMA,
        "control_state": "RUNNING",
        "campaign_generation": generation,
        "transition_sequence": 0,
        "request_id": "",
        "idempotency_key": "",
        "action": "",
        "source_envelope_sha256": "",
        "authority_receipt_ref": "",
        "authority_receipt_sha256": "",
        "authority_applied_at": None,
        "effect_state": "unobserved",
        "effect_receipt_ref": "",
        "effect_receipt_sha256": "",
        "effect_observed_at": None,
    }


def validate_operator_control_state(
    value: Any,
    *,
    expected_generation: int,
) -> dict[str, Any]:
    """Validate and copy the closed producer-side control-state contract."""
    if not isinstance(value, Mapping) or set(value) != OPERATOR_CONTROL_STATE_FIELDS:
        raise ValueError("operator control state fields are not exact")
    state = dict(value)
    if (
        state["schema_version"] != OPERATOR_CONTROL_STATE_SCHEMA
        or state["control_state"] not in _CONTROL_STATES
        or state["campaign_generation"] != expected_generation
        or isinstance(state["transition_sequence"], bool)
        or not isinstance(state["transition_sequence"], int)
        or state["transition_sequence"] < 0
        or state["action"] not in _ACTIONS
        or state["effect_state"] not in {"unobserved", "observed", "violated"}
    ):
        raise ValueError("operator control state coordinates are invalid")
    if state["effect_state"] != "unobserved":
        raise ValueError(
            "operator effect evidence requires a separately admitted receipt transition"
        )
    for field in (
        "request_id",
        "idempotency_key",
        "action",
        "source_envelope_sha256",
        "authority_receipt_ref",
        "authority_receipt_sha256",
        "effect_receipt_ref",
        "effect_receipt_sha256",
    ):
        if not isinstance(state[field], str):
            raise ValueError(f"operator control state {field} must be text")
    for field in ("authority_applied_at", "effect_observed_at"):
        raw = state[field]
        if raw is not None:
            if not isinstance(raw, str) or not _UTC_TIMESTAMP_RE.fullmatch(raw):
                raise ValueError(
                    f"operator control state {field} must be strict UTC"
                )
            try:
                parsed = datetime.fromisoformat(raw.removesuffix("Z") + "+00:00")
            except ValueError as exc:
                raise ValueError(
                    f"operator control state {field} must be a timestamp"
                ) from exc
            if parsed.tzinfo is None:
                raise ValueError(f"operator control state {field} must be timezone-aware")
    sequence = state["transition_sequence"]
    authority_fields = (
        state["request_id"],
        state["idempotency_key"],
        state["action"],
        state["source_envelope_sha256"],
        state["authority_receipt_ref"],
        state["authority_receipt_sha256"],
        state["authority_applied_at"],
    )
    if sequence == 0:
        if state != initial_operator_control_state(expected_generation):
            raise ValueError("initial operator control state is not exact")
        return state
    if (
        not _IDENTIFIER_RE.fullmatch(state["request_id"])
        or not _IDENTIFIER_RE.fullmatch(state["idempotency_key"])
        or state["action"] not in {"pause", "resume", "emergency_stop"}
        or not _SHA256_RE.fullmatch(state["source_envelope_sha256"])
        or not state["authority_receipt_ref"]
        or len(state["authority_receipt_ref"]) > 512
        or not _SHA256_RE.fullmatch(state["authority_receipt_sha256"])
        or state["authority_applied_at"] is None
        or any(item in {"", None} for item in authority_fields)
    ):
        raise ValueError("applied operator control state is incomplete")
    expected_state = {
        "pause": "PAUSED",
        "resume": "RUNNING",
        "emergency_stop": "STOPPED_TERMINAL",
    }[state["action"]]
    if state["control_state"] != expected_state:
        raise ValueError("operator action does not bind its control state")
    effect_fields = (
        state["effect_receipt_ref"],
        state["effect_receipt_sha256"],
        state["effect_observed_at"],
    )
    if effect_fields != ("", "", None):
        raise ValueError("unobserved operator effect has claimed evidence")
    return state


def runtime_receipt_content_digest(receipt: Any) -> str:
    """Digest one immutable RuntimeReceipt without importing runtime state."""

    def json_value(item: Any) -> Any:
        if is_dataclass(item):
            return json_value(asdict(item))
        if isinstance(item, datetime):
            return item.isoformat()
        if isinstance(item, Enum):
            return item.value
        if isinstance(item, Mapping):
            return {str(key): json_value(value) for key, value in item.items()}
        if isinstance(item, (tuple, list)):
            return [json_value(value) for value in item]
        return item

    encoded = json.dumps(
        json_value(receipt),
        allow_nan=False,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode()
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


__all__ = [
    "OPERATOR_CONTROL_RECEIPT_REF_PREFIX",
    "OPERATOR_CONTROL_RECEIPT_SCHEMA",
    "OPERATOR_CONTROL_RECEIPT_TYPE",
    "OPERATOR_CONTROL_STATE_FIELDS",
    "OPERATOR_CONTROL_STATE_SCHEMA",
    "canonical_utc_timestamp",
    "initial_operator_control_state",
    "runtime_receipt_content_digest",
    "validate_operator_control_state",
]
