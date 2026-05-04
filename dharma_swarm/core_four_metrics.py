"""DX Core Four metric helpers for the TelicSeam ontology path."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from dharma_swarm.ontology import OntologyObj, OntologyRegistry

CORE_FOUR_DIMENSIONS = ("speed", "effectiveness", "quality", "impact")
CORE_FOUR_SIGNAL_SOURCES = {
    "speed": "duration_efficiency",
    "effectiveness": "behavioral_signal",
    "quality": "fitness_or_success",
    "impact": "composite_value",
}


@dataclass(frozen=True)
class CoreFourMetricSpec:
    dimension: str
    score: float
    signal_source: str


def clamp01(value: Any) -> float:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        numeric = 0.0
    return max(0.0, min(1.0, numeric))


def core_four_scores(
    value_event: OntologyObj,
    outcome: OntologyObj,
) -> list[CoreFourMetricSpec]:
    quality_source = outcome.properties.get("fitness_score")
    if not isinstance(quality_source, (int, float)) or quality_source <= 0:
        quality_source = value_event.properties.get("success_value")

    scores = {
        "speed": clamp01(value_event.properties.get("duration_efficiency")),
        "effectiveness": clamp01(value_event.properties.get("behavioral_signal")),
        "quality": clamp01(quality_source),
        "impact": clamp01(value_event.properties.get("composite_value")),
    }
    return [
        CoreFourMetricSpec(
            dimension=dimension,
            score=scores[dimension],
            signal_source=CORE_FOUR_SIGNAL_SOURCES[dimension],
        )
        for dimension in CORE_FOUR_DIMENSIONS
    ]


def core_four_metric_sort_key(metric: OntologyObj) -> int:
    dimension = str(metric.properties.get("dimension") or "")
    try:
        return CORE_FOUR_DIMENSIONS.index(dimension)
    except ValueError:
        return 99


def existing_core_four_metric(
    registry: OntologyRegistry,
    value_event_id: str,
    dimension: str,
) -> OntologyObj | None:
    for metric in registry.get_objects_by_type("CoreFourMetric"):
        if (
            metric.properties.get("value_event_id") == value_event_id
            and metric.properties.get("dimension") == dimension
        ):
            return metric
    return None


def ensure_core_four_linkage(
    registry: OntologyRegistry,
    value_event_id: str,
    outcome_id: str,
    metric: OntologyObj,
) -> list[str]:
    errors: list[str] = []
    if not registry.get_links(
        source_id=value_event_id,
        target_id=metric.id,
        link_name="has_core_four_metric",
    ):
        link, link_errors = registry.create_link(
            "has_core_four_metric",
            source_id=value_event_id,
            target_id=metric.id,
            created_by="telic_seam",
        )
        if link is None:
            errors.extend(link_errors)

    if not registry.get_links(
        source_id=metric.id,
        target_id=outcome_id,
        link_name="measures_outcome",
    ):
        link, link_errors = registry.create_link(
            "measures_outcome",
            source_id=metric.id,
            target_id=outcome_id,
            created_by="telic_seam",
        )
        if link is None:
            errors.extend(link_errors)

    return errors


def query_core_four_metrics(
    registry: OntologyRegistry,
    *,
    value_event_id: str = "",
    outcome_id: str = "",
) -> list[OntologyObj]:
    metrics = registry.get_objects_by_type("CoreFourMetric")
    if value_event_id:
        metrics = [
            metric for metric in metrics
            if metric.properties.get("value_event_id") == value_event_id
        ]
    if outcome_id:
        metrics = [
            metric for metric in metrics
            if metric.properties.get("outcome_id") == outcome_id
        ]
    return sorted(metrics, key=core_four_metric_sort_key)


def record_core_four_metrics(
    registry: OntologyRegistry,
    value_event_id: str,
    *,
    measured_at: str,
    evidence_summary: str = "",
    measurement_method: str = "dx_core4_from_value_event_v1",
) -> tuple[list[str], int, list[str], bool]:
    value_event = registry.get_object(value_event_id)
    if value_event is None or value_event.type_name != "ValueEvent":
        return [], 0, [], False

    outcome_id = str(value_event.properties.get("outcome_id") or "")
    outcome = registry.get_object(outcome_id)
    if outcome is None or outcome.type_name != "Outcome":
        return [], 0, [], False

    metric_ids: list[str] = []
    duplicate_count = 0
    errors: list[str] = []

    for spec in core_four_scores(value_event, outcome):
        existing = existing_core_four_metric(registry, value_event_id, spec.dimension)
        if existing is not None:
            duplicate_count += 1
            errors.extend(
                ensure_core_four_linkage(registry, value_event_id, outcome_id, existing)
            )
            metric_ids.append(existing.id)
            continue

        obj, create_errors = registry.create_object(
            "CoreFourMetric",
            properties={
                "metric_id": f"core4_{value_event_id}_{spec.dimension}",
                "value_event_id": value_event_id,
                "outcome_id": outcome_id,
                "task_id": str(value_event.properties.get("task_id") or ""),
                "agent_id": str(value_event.properties.get("agent_id") or ""),
                "dimension": spec.dimension,
                "score": spec.score,
                "signal_source": spec.signal_source,
                "measurement_method": measurement_method,
                "evidence_summary": evidence_summary[:500],
                "measured_at": measured_at,
            },
            created_by="telic_seam",
        )
        if obj is None:
            errors.extend(create_errors)
            continue

        errors.extend(ensure_core_four_linkage(registry, value_event_id, outcome_id, obj))
        metric_ids.append(obj.id)

    return metric_ids, duplicate_count, errors, True


def core_four_integrity_report(
    registry: OntologyRegistry,
    core_four_metrics: list[OntologyObj],
    value_events_by_id: dict[str, OntologyObj],
    outcomes_by_id: dict[str, OntologyObj],
) -> dict[str, list[Any]]:
    report: dict[str, list[Any]] = {
        "value_core_four_agent_mismatches": [],
        "orphan_core_four_metrics": [],
        "core_four_scope_mismatches": [],
    }

    for metric in core_four_metrics:
        value_event_id = str(metric.properties.get("value_event_id") or "")
        outcome_id = str(metric.properties.get("outcome_id") or "")
        value_event = value_events_by_id.get(value_event_id)
        outcome = outcomes_by_id.get(outcome_id)
        linked_to_value = registry.get_links(
            source_id=value_event_id,
            target_id=metric.id,
            link_name="has_core_four_metric",
        )
        linked_to_outcome = registry.get_links(
            source_id=metric.id,
            target_id=outcome_id,
            link_name="measures_outcome",
        )
        if value_event is None or outcome is None or not linked_to_value or not linked_to_outcome:
            report["orphan_core_four_metrics"].append(metric.id)
            continue

        if outcome_id != str(value_event.properties.get("outcome_id") or ""):
            report["core_four_scope_mismatches"].append(
                {
                    "value_event_id": value_event_id,
                    "metric_id": metric.id,
                    "metric_outcome_id": outcome_id,
                    "value_event_outcome_id": value_event.properties.get("outcome_id"),
                }
            )
        if value_event.properties.get("agent_id") != metric.properties.get("agent_id"):
            report["value_core_four_agent_mismatches"].append(
                {
                    "value_event_id": value_event_id,
                    "metric_id": metric.id,
                    "value_event_agent_id": value_event.properties.get("agent_id"),
                    "metric_agent_id": metric.properties.get("agent_id"),
                }
            )

    return report
