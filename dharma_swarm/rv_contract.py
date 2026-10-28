"""Internal raw-observation history and comparison-identity utilities.

Public reading models and typed compatibility entry points remain in rv.
"""

from __future__ import annotations

import copy
from collections.abc import Iterable
from typing import Any, Literal, get_args

MeasurementKind = Literal[
    "unknown",
    "attention_value",
    "residual_hidden",
    "colony_density",
    "behavioral_proxy",
]


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
        elif historical[key] != value:
            conflict = {
                "field": key,
                "existing_source": "historical_classification",
                "existing_value": historical[key],
                "legacy_source": "legacy_top_level",
                "legacy_value": value,
            }
            if conflict not in conflicts:
                conflicts.append(conflict)
    if historical or had_historical:
        data["historical_classification"] = historical
    if conflicts or had_conflicts:
        data["historical_classification_conflicts"] = conflicts
    return data


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
