"""Internal raw-observation history and comparison-identity utilities.

Public reading models and typed compatibility entry points remain in rv.
"""

from __future__ import annotations

import copy
import hashlib
import math
from datetime import datetime, timezone
from collections.abc import Iterable
from typing import Any, Literal, get_args

MeasurementKind = Literal[
    "unknown",
    "attention_value",
    "residual_hidden",
    "colony_density",
    "behavioral_proxy",
]


def _historical_values_equal(left: Any, right: Any) -> bool:
    if isinstance(left, bool) or isinstance(right, bool):
        return type(left) is bool and type(right) is bool and left is right
    if (
        type(left) is float
        and type(right) is float
        and math.isnan(left)
        and math.isnan(right)
    ):
        return True
    if isinstance(left, dict) and isinstance(right, dict):
        return left.keys() == right.keys() and all(
            _historical_values_equal(left[key], right[key]) for key in left
        )
    if isinstance(left, list) and isinstance(right, list):
        return len(left) == len(right) and all(
            _historical_values_equal(left_item, right_item)
            for left_item, right_item in zip(left, right)
        )
    return left == right


def _preserve_historical_classification(data: Any) -> Any:
    if not isinstance(data, dict):
        return data
    data = copy.deepcopy(data)
    historical = data.get("historical_classification", {})
    conflicts = data.get("historical_classification_conflicts", [])
    if not isinstance(historical, dict):
        historical = {"raw_historical_classification": historical}
    if not isinstance(conflicts, list):
        conflicts = [
            {
                "field": "historical_classification_conflicts",
                "existing_source": "historical_classification_conflicts",
                "existing_value": conflicts,
            }
        ]
    had_historical = "historical_classification" in data
    had_conflicts = "historical_classification_conflicts" in data
    for key in ("is_contracted", "contraction_strength"):
        value = data.get(key)
        data[key] = None
        if value is None:
            continue
        if key not in historical:
            historical[key] = value
        elif not _historical_values_equal(historical[key], value):
            conflict = {
                "field": key,
                "existing_source": "historical_classification",
                "existing_value": historical[key],
                "legacy_source": "legacy_top_level",
                "legacy_value": value,
            }
            if not any(
                _historical_values_equal(conflict, existing) for existing in conflicts
            ):
                conflicts.append(conflict)
    if historical or had_historical:
        data["historical_classification"] = historical
    if conflicts or had_conflicts:
        data["historical_classification_conflicts"] = conflicts
    return data


def _accepted_reading_projection(reading: Any) -> dict[str, Any]:
    return {
        "rv": reading.rv,
        "pr_early": reading.pr_early,
        "pr_late": reading.pr_late,
        "rv_source": "geometric",
        "measurement_kind": reading.measurement_kind,
        "measurement_details": dict(reading.measurement_details),
        "model_name": reading.model_name,
        "early_layer": reading.early_layer,
        "late_layer": reading.late_layer,
        "historical_classification": copy.deepcopy(reading.historical_classification),
        "historical_classification_conflicts": copy.deepcopy(
            reading.historical_classification_conflicts
        ),
    }


def _measurement_identity(measurement: Any) -> tuple[Any, ...] | None:
    def field(name: str) -> Any:
        if isinstance(measurement, dict):
            return measurement.get(name)
        return getattr(measurement, name, None)

    kind = field("measurement_kind") or "unknown"
    if kind not in get_args(MeasurementKind) or kind == "unknown":
        return None
    details = field("measurement_details")
    if not isinstance(details, dict):
        return None
    cohort = details.get("cohort")
    if (
        not isinstance(cohort, str)
        or not cohort.strip()
        or cohort.strip().lower() == "unknown"
    ):
        return None

    identity: list[Any] = [kind, cohort.strip()]
    if kind in {"attention_value", "residual_hidden"}:
        model_name = field("model_name")
        early_layer = field("early_layer")
        late_layer = field("late_layer")
        if (
            not isinstance(model_name, str)
            or not model_name.strip()
            or model_name.strip().lower() == "unknown"
        ):
            return None
        if any(
            isinstance(layer, bool) or not isinstance(layer, int) or layer < 0
            for layer in (early_layer, late_layer)
        ):
            return None
        identity.extend((model_name.strip(), early_layer, late_layer))
        for name in ("tensor", "centering", "participation_ratio", "window"):
            if name not in details:
                identity.append((name, None))
                continue
            declaration = details[name]
            if not isinstance(declaration, str):
                return None
            identity.append((name, declaration))
    if kind in {"behavioral_proxy", "colony_density"}:
        formula = details.get("formula")
        if (
            not isinstance(formula, str)
            or not formula.strip()
            or formula.strip().lower() == "unknown"
        ):
            return None
        identity.append(formula.strip())
    return tuple(identity)


def comparable_measurement_identity(
    measurements: Iterable[Any],
) -> tuple[Any, ...] | None:
    """Return one explicit shared measurement identity, or None when pooling is invalid."""
    identities = [_measurement_identity(measurement) for measurement in measurements]
    if not identities or any(identity is None for identity in identities):
        return None
    if len(set(identities)) != 1:
        return None
    return identities[0]


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _prompt_hash(prompt: str) -> str:
    """SHA-256 of prompt text, first 16 hex characters."""
    return hashlib.sha256(prompt.encode("utf-8")).hexdigest()[:16]
