"""Tests for the schema-alignment governance gate."""

from __future__ import annotations

from scripts.governance.check_ontology_alignment import (
    _check_api_name_discipline,
    _detect_conflicts,
    _extract_ontology_snapshot,
)


def test_extract_ontology_snapshot_reads_enum_status() -> None:
    snapshot = _extract_ontology_snapshot(
        """
from dharma_swarm.ontology import ObjectType, TypeStatus

_EXAMPLE = ObjectType(
    name="ExampleType",
    api_name="dharma.example.ExampleType",
    status=TypeStatus.ACTIVE,
)
""",
        source_pr="branch:test",
    )

    assert snapshot["types"][0]["status"] == "active"


def test_api_name_discipline_accepts_adr008_shape() -> None:
    snapshot = {
        "types": [{
            "name": "ExampleType",
            "api_name": "dharma.example.ExampleType",
            "source_pr": "branch:test",
        }]
    }

    assert _check_api_name_discipline([snapshot], warn_only=False) == []


def test_api_name_discipline_rejects_version_suffix() -> None:
    snapshot = {
        "types": [{
            "name": "ExampleType",
            "api_name": "dharma.example.ExampleType.v1",
            "source_pr": "branch:test",
        }]
    }

    issues = _check_api_name_discipline([snapshot], warn_only=False)

    assert len(issues) == 1
    assert issues[0].rule == "ALIGN-007"
    assert issues[0].severity == "error"


def test_api_name_discipline_rejects_type_name_underscore() -> None:
    snapshot = {
        "types": [{
            "name": "Bad_Type",
            "api_name": "dharma.example.Bad_Type",
            "source_pr": "branch:test",
        }]
    }

    issues = _check_api_name_discipline([snapshot], warn_only=False)

    assert len(issues) == 1
    assert issues[0].rule == "ALIGN-007"


def test_missing_api_name_on_pre_oms_branch_is_not_name_conflict() -> None:
    snapshots = [
        {
            "types": [{
                "name": "ResearchThread",
                "api_name": "dharma.research.ResearchThread",
                "source_pr": "origin/main",
            }]
        },
        {
            "types": [{
                "name": "ResearchThread",
                "api_name": None,
                "source_pr": "PR#stale-pre-oms",
            }]
        },
    ]

    assert _detect_conflicts(snapshots) == []
