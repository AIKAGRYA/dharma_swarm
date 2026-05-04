"""ValueEvent aggregation read for the ``dgc value-events`` CLI command.

Queries the ontology registry for ``ValueEvent`` objects whose
``task_type == "operator_brief"``, filters by ``created_at >= --since``,
and groups results by ``Contribution.agent_id`` (the ``attributed_to``
field in the TODO spec).

See ``docs/plans/NEXT_10_SUBSTRATE_TODO.md`` item 9.
"""

from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

from dharma_swarm.ontology import OntologyObj, OntologyRegistry
from dharma_swarm.ontology_runtime import get_shared_registry


def _parse_since(raw: str) -> datetime:
    """Parse a --since value into a timezone-aware datetime."""
    for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%S%z"):
        try:
            dt = datetime.strptime(raw, fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except ValueError:
            continue
    raise ValueError(
        f"Cannot parse date '{raw}'. Expected YYYY-MM-DD or ISO-8601."
    )


def query_value_events(
    registry: OntologyRegistry,
    *,
    since: datetime | None = None,
    task_type: str = "operator_brief",
) -> list[OntologyObj]:
    """Return ValueEvent objects filtered by task_type and created_at."""
    events = registry.get_objects_by_type("ValueEvent")
    filtered: list[OntologyObj] = []
    for ev in events:
        if task_type and ev.properties.get("task_type") != task_type:
            continue
        if since is not None and ev.created_at < since:
            continue
        filtered.append(ev)
    return filtered


def _contributions_for_events(
    registry: OntologyRegistry,
    event_ids: set[str],
) -> dict[str, list[OntologyObj]]:
    """Map value_event_id → list of Contribution objects."""
    result: dict[str, list[OntologyObj]] = defaultdict(list)
    for contrib in registry.get_objects_by_type("Contribution"):
        ve_id = str(contrib.properties.get("value_event_id") or "")
        if ve_id in event_ids:
            result[ve_id].append(contrib)
    return result


def group_by_agent(
    events: list[OntologyObj],
    contributions: dict[str, list[OntologyObj]],
) -> dict[str, dict[str, Any]]:
    """Group ValueEvents by agent_id via Contributions.

    Returns ``{agent_id: {count, total_value, avg_value, events: [...]}}``
    sorted by ``total_value`` descending.
    """
    agent_data: dict[str, dict[str, Any]] = defaultdict(
        lambda: {"count": 0, "total_value": 0.0, "events": []}
    )

    for ev in events:
        contribs = contributions.get(ev.id, [])
        if contribs:
            for c in contribs:
                agent_id = str(c.properties.get("agent_id") or "unknown")
                attributed = float(c.properties.get("attributed_value") or 0.0)
                agent_data[agent_id]["count"] += 1
                agent_data[agent_id]["total_value"] += attributed
                agent_data[agent_id]["events"].append(
                    {
                        "value_event_id": ev.id,
                        "composite_value": ev.properties.get("composite_value"),
                        "attributed_value": attributed,
                        "created_at": ev.created_at.isoformat(),
                    }
                )
        else:
            agent_id = str(ev.properties.get("agent_id") or "unknown")
            composite = float(ev.properties.get("composite_value") or 0.0)
            agent_data[agent_id]["count"] += 1
            agent_data[agent_id]["total_value"] += composite
            agent_data[agent_id]["events"].append(
                {
                    "value_event_id": ev.id,
                    "composite_value": composite,
                    "attributed_value": None,
                    "created_at": ev.created_at.isoformat(),
                }
            )

    for data in agent_data.values():
        data["avg_value"] = (
            data["total_value"] / data["count"] if data["count"] else 0.0
        )

    return dict(
        sorted(agent_data.items(), key=lambda kv: kv[1]["total_value"], reverse=True)
    )


def format_table(grouped: dict[str, dict[str, Any]], *, since: str) -> str:
    """Render grouped ValueEvent data as a human-readable table."""
    if not grouped:
        return f"No operator_brief ValueEvents found since {since}."

    lines: list[str] = []
    total_events = sum(d["count"] for d in grouped.values())
    total_value = sum(d["total_value"] for d in grouped.values())

    lines.append(f"ValueEvents (operator_brief) since {since}")
    lines.append(f"  Total events: {total_events}  |  Total value: {total_value:.3f}")
    lines.append("")
    lines.append(f"{'Agent':<30} {'Count':>6} {'Total':>8} {'Avg':>8}")
    lines.append("-" * 56)

    for agent_id, data in grouped.items():
        display_id = agent_id[:28] if len(agent_id) > 28 else agent_id
        lines.append(
            f"{display_id:<30} {data['count']:>6} "
            f"{data['total_value']:>8.3f} {data['avg_value']:>8.3f}"
        )

    return "\n".join(lines)


def format_json(grouped: dict[str, dict[str, Any]], *, since: str) -> str:
    """Render grouped ValueEvent data as JSON."""
    output = {
        "since": since,
        "by_agent": grouped,
        "summary": {
            "total_events": sum(d["count"] for d in grouped.values()),
            "total_value": sum(d["total_value"] for d in grouped.values()),
            "agent_count": len(grouped),
        },
    }
    return json.dumps(output, indent=2, default=str)


def run_value_events(
    *,
    since: str,
    as_json: bool = False,
    registry_path: str | None = None,
) -> str:
    """Main entrypoint for ``dgc value-events --since <date>``.

    Returns formatted output string (table or JSON).
    """
    since_dt = _parse_since(since)
    registry = get_shared_registry(registry_path)

    events = query_value_events(registry, since=since_dt)
    event_ids = {ev.id for ev in events}
    contributions = _contributions_for_events(registry, event_ids)
    grouped = group_by_agent(events, contributions)

    if as_json:
        return format_json(grouped, since=since)
    return format_table(grouped, since=since)
