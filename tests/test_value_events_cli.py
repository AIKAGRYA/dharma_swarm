"""Tests for ``dgc value-events --since`` (NEXT_10_SUBSTRATE_TODO item 9).

Covers:
1. ``_parse_since`` date parsing
2. ``query_value_events`` filtering by task_type and since
3. ``_contributions_for_events`` mapping
4. ``group_by_agent`` aggregation
5. ``format_table`` / ``format_json`` output
6. ``run_value_events`` end-to-end with a fresh registry
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pytest

from dharma_swarm.ontology import OntologyRegistry
from dharma_swarm.operator_brief.value_events import (
    _contributions_for_events,
    _parse_since,
    format_json,
    format_table,
    group_by_agent,
    query_value_events,
    run_value_events,
)


@pytest.fixture
def registry() -> OntologyRegistry:
    return OntologyRegistry.create_dharma_registry()


def _make_value_event(
    registry: OntologyRegistry,
    *,
    outcome_id: str = "out_1",
    agent_id: str = "agent_a",
    task_type: str = "operator_brief",
    composite_value: float = 0.5,
    created_at: datetime | None = None,
) -> str:
    obj, errors = registry.create_object(
        "ValueEvent",
        properties={
            "outcome_id": outcome_id,
            "agent_id": agent_id,
            "cell_id": "",
            "task_id": f"operator_brief::{outcome_id}",
            "task_type": task_type,
            "behavioral_signal": 0.5,
            "success_value": 1.0,
            "duration_efficiency": 0.5,
            "composite_value": composite_value,
            "scoring_method": "operator_brief_v0_estimated",
        },
        created_by="test",
    )
    assert obj is not None, f"ValueEvent creation failed: {errors}"
    if created_at is not None:
        obj.created_at = created_at
    return obj.id


def _make_contribution(
    registry: OntologyRegistry,
    *,
    value_event_id: str,
    agent_id: str = "agent_a",
    attributed_value: float = 0.5,
) -> str:
    obj, errors = registry.create_object(
        "Contribution",
        properties={
            "value_event_id": value_event_id,
            "agent_id": agent_id,
            "cell_id": "",
            "task_type": "operator_brief",
            "credit_share": 1.0,
            "attributed_value": attributed_value,
        },
        created_by="test",
    )
    assert obj is not None, f"Contribution creation failed: {errors}"
    return obj.id


# ── _parse_since ──────────────────────────────────────────────────────


class TestParseSince:
    def test_date_only(self) -> None:
        dt = _parse_since("2025-06-15")
        assert dt == datetime(2025, 6, 15, tzinfo=timezone.utc)

    def test_iso_no_tz(self) -> None:
        dt = _parse_since("2025-06-15T10:30:00")
        assert dt == datetime(2025, 6, 15, 10, 30, 0, tzinfo=timezone.utc)

    def test_iso_with_tz(self) -> None:
        dt = _parse_since("2025-06-15T10:30:00+00:00")
        assert dt.tzinfo is not None

    def test_invalid(self) -> None:
        with pytest.raises(ValueError, match="Cannot parse"):
            _parse_since("not-a-date")


# ── query_value_events ────────────────────────────────────────────────


class TestQueryValueEvents:
    def test_filters_by_task_type(self, registry: OntologyRegistry) -> None:
        _make_value_event(registry, outcome_id="ob1", task_type="operator_brief")
        _make_value_event(registry, outcome_id="ob2", task_type="general")

        events = query_value_events(registry, task_type="operator_brief")
        assert len(events) == 1
        assert events[0].properties["task_type"] == "operator_brief"

    def test_filters_by_since(self, registry: OntologyRegistry) -> None:
        old = datetime(2024, 1, 1, tzinfo=timezone.utc)
        recent = datetime(2026, 1, 1, tzinfo=timezone.utc)

        _make_value_event(registry, outcome_id="old1", created_at=old)
        _make_value_event(registry, outcome_id="new1", created_at=recent)

        since = datetime(2025, 6, 1, tzinfo=timezone.utc)
        events = query_value_events(registry, since=since)
        assert len(events) == 1

    def test_returns_all_when_no_filter(self, registry: OntologyRegistry) -> None:
        _make_value_event(registry, outcome_id="a1")
        _make_value_event(registry, outcome_id="a2")
        events = query_value_events(registry, since=None, task_type="operator_brief")
        assert len(events) == 2


# ── _contributions_for_events ─────────────────────────────────────────


class TestContributionsForEvents:
    def test_maps_contributions(self, registry: OntologyRegistry) -> None:
        ve_id = _make_value_event(registry, outcome_id="c1")
        _make_contribution(registry, value_event_id=ve_id, agent_id="agent_x")

        result = _contributions_for_events(registry, {ve_id})
        assert ve_id in result
        assert len(result[ve_id]) == 1
        assert result[ve_id][0].properties["agent_id"] == "agent_x"

    def test_ignores_unrelated(self, registry: OntologyRegistry) -> None:
        ve_id = _make_value_event(registry, outcome_id="c2")
        _make_contribution(registry, value_event_id="unrelated_ve", agent_id="agent_y")

        result = _contributions_for_events(registry, {ve_id})
        assert ve_id not in result


# ── group_by_agent ────────────────────────────────────────────────────


class TestGroupByAgent:
    def test_groups_via_contributions(self, registry: OntologyRegistry) -> None:
        ve1 = _make_value_event(registry, outcome_id="g1", agent_id="agent_a")
        ve2 = _make_value_event(registry, outcome_id="g2", agent_id="agent_a")
        _make_contribution(registry, value_event_id=ve1, agent_id="agent_a", attributed_value=0.5)
        _make_contribution(registry, value_event_id=ve2, agent_id="agent_b", attributed_value=0.3)

        events = registry.get_objects_by_type("ValueEvent")
        contribs = _contributions_for_events(registry, {ev.id for ev in events})
        grouped = group_by_agent(events, contribs)

        assert "agent_a" in grouped
        assert "agent_b" in grouped
        assert grouped["agent_a"]["count"] == 1
        assert grouped["agent_b"]["count"] == 1

    def test_fallback_to_event_agent(self, registry: OntologyRegistry) -> None:
        _make_value_event(registry, outcome_id="f1", agent_id="agent_solo")

        events = registry.get_objects_by_type("ValueEvent")
        grouped = group_by_agent(events, {})

        assert "agent_solo" in grouped
        assert grouped["agent_solo"]["count"] == 1

    def test_sorted_by_total_value(self, registry: OntologyRegistry) -> None:
        ve1 = _make_value_event(registry, outcome_id="s1", agent_id="low_agent", composite_value=0.1)
        ve2 = _make_value_event(registry, outcome_id="s2", agent_id="high_agent", composite_value=0.9)
        _make_contribution(registry, value_event_id=ve1, agent_id="low_agent", attributed_value=0.1)
        _make_contribution(registry, value_event_id=ve2, agent_id="high_agent", attributed_value=0.9)

        events = registry.get_objects_by_type("ValueEvent")
        contribs = _contributions_for_events(registry, {ev.id for ev in events})
        grouped = group_by_agent(events, contribs)

        agents = list(grouped.keys())
        assert agents[0] == "high_agent"
        assert agents[1] == "low_agent"


# ── format_table ──────────────────────────────────────────────────────


class TestFormatTable:
    def test_empty(self) -> None:
        output = format_table({}, since="2025-01-01")
        assert "No operator_brief ValueEvents" in output

    def test_header_and_rows(self) -> None:
        grouped = {
            "agent_x": {
                "count": 3,
                "total_value": 1.5,
                "avg_value": 0.5,
                "events": [],
            }
        }
        output = format_table(grouped, since="2025-01-01")
        assert "agent_x" in output
        assert "Total events: 3" in output
        assert "1.500" in output


# ── format_json ───────────────────────────────────────────────────────


class TestFormatJson:
    def test_valid_json(self) -> None:
        grouped = {
            "agent_y": {
                "count": 2,
                "total_value": 1.0,
                "avg_value": 0.5,
                "events": [],
            }
        }
        raw = format_json(grouped, since="2025-01-01")
        data = json.loads(raw)
        assert data["since"] == "2025-01-01"
        assert data["summary"]["total_events"] == 2
        assert "agent_y" in data["by_agent"]


# ── run_value_events (integration) ────────────────────────────────────


class TestRunValueEvents:
    def test_end_to_end(self, tmp_path, monkeypatch) -> None:
        """Full end-to-end: create registry, add events, run command."""
        from dharma_swarm import ontology_runtime

        db_path = tmp_path / "ontology.db"
        registry = OntologyRegistry.create_dharma_registry()

        ve_id = _make_value_event(
            registry,
            outcome_id="e2e_1",
            agent_id="agent_e2e",
            composite_value=0.7,
        )
        _make_contribution(
            registry,
            value_event_id=ve_id,
            agent_id="agent_e2e",
            attributed_value=0.7,
        )

        monkeypatch.setattr(ontology_runtime, "_SHARED_REGISTRY", registry)
        monkeypatch.setattr(ontology_runtime, "_SHARED_REGISTRY_PATH", db_path)

        output = run_value_events(since="2020-01-01", registry_path=str(db_path))
        assert "agent_e2e" in output
        assert "0.700" in output

    def test_json_output(self, tmp_path, monkeypatch) -> None:
        from dharma_swarm import ontology_runtime

        db_path = tmp_path / "ontology.db"
        registry = OntologyRegistry.create_dharma_registry()

        _make_value_event(
            registry,
            outcome_id="j1",
            agent_id="json_agent",
        )

        monkeypatch.setattr(ontology_runtime, "_SHARED_REGISTRY", registry)
        monkeypatch.setattr(ontology_runtime, "_SHARED_REGISTRY_PATH", db_path)

        output = run_value_events(
            since="2020-01-01", as_json=True, registry_path=str(db_path),
        )
        data = json.loads(output)
        assert data["summary"]["total_events"] == 1
        assert "json_agent" in data["by_agent"]

    def test_no_events(self, tmp_path, monkeypatch) -> None:
        from dharma_swarm import ontology_runtime

        db_path = tmp_path / "ontology.db"
        registry = OntologyRegistry.create_dharma_registry()

        monkeypatch.setattr(ontology_runtime, "_SHARED_REGISTRY", registry)
        monkeypatch.setattr(ontology_runtime, "_SHARED_REGISTRY_PATH", db_path)

        output = run_value_events(since="2020-01-01", registry_path=str(db_path))
        assert "No operator_brief ValueEvents" in output
