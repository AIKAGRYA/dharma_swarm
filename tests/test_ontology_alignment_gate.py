"""Tests for the schema-alignment governance gate."""

from __future__ import annotations

import subprocess
import sys

import pytest

import scripts.governance.check_ontology_alignment as gate
from scripts.governance.check_ontology_alignment import (
    _check_api_name_discipline,
    _detect_conflicts,
    _extract_ontology_snapshot,
    _list_open_ontology_prs,
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


def test_open_pr_scan_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    def fail_run(*_args: object, **_kwargs: object) -> subprocess.CompletedProcess:
        raise subprocess.CalledProcessError(1, ["gh", "pr", "list"])

    monkeypatch.setattr(gate.subprocess, "run", fail_run)

    with pytest.raises(RuntimeError, match="could not list open ontology PRs"):
        _list_open_ontology_prs(limit=1)


def test_main_fails_closed_without_origin_main(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "argv", ["check_ontology_alignment.py", "--limit", "1"])
    monkeypatch.setattr(gate, "_read_file_at_ref", lambda *_args: None)

    assert gate.main() == 1


def test_action_input_params_conflict_is_detected() -> None:
    snapshots = [
        {
            "actions": [{
                "name": "approve",
                "object_type": "ActionProposal",
                "param_signature": ["target_id:str"],
                "source_pr": "PR#1",
            }]
        },
        {
            "actions": [{
                "name": "approve",
                "object_type": "ActionProposal",
                "param_signature": ["target_id:int"],
                "source_pr": "PR#2",
            }]
        },
    ]

    conflicts = _detect_conflicts(snapshots)

    assert [conflict.rule for conflict in conflicts] == ["ALIGN-005"]


def test_action_extraction_reads_input_params_field() -> None:
    snapshot = _extract_ontology_snapshot(
        """
_ACTION_PROPOSAL = ObjectType(
    name="ActionProposal",
    actions=[
        ActionDef(
            name="Approve",
            object_type="ActionProposal",
            input_params={"target_id": "str"},
        ),
    ],
)
""",
        source_pr="PR#input",
    )

    assert snapshot["actions"][0]["param_signature"] == ["target_id:str"]


def test_action_extraction_keeps_enum_typed_input_params() -> None:
    snapshot = _extract_ontology_snapshot(
        """
_ACTION_PROPOSAL = ObjectType(
    name="ActionProposal",
    actions=[
        ActionDef(
            name="Approve",
            object_type="ActionProposal",
            input_params={"target_id": PropertyType.STRING},
        ),
    ],
)
""",
        source_pr="PR#enum-input",
    )

    assert snapshot["actions"][0]["param_signature"] == ["target_id:string"]


def test_object_properties_and_security_conflicts_are_detected() -> None:
    snapshots = [
        {
            "types": [{
                "name": "AuditFinding",
                "properties": "properties:v1",
                "security": "security:internal",
                "source_pr": "PR#1",
            }]
        },
        {
            "types": [{
                "name": "AuditFinding",
                "properties": "properties:v2",
                "security": "security:dharmic",
                "source_pr": "PR#2",
            }]
        },
    ]

    conflicts = _detect_conflicts(snapshots)

    assert [conflict.rule for conflict in conflicts] == ["ALIGN-001"]
    assert set(conflicts[0].field_diffs) == {"properties", "security"}


def test_object_extraction_fingerprints_properties_and_security() -> None:
    snapshot = _extract_ontology_snapshot(
        """
_AUDIT_FINDING = ObjectType(
    name="AuditFinding",
    api_name="dharma.audit.AuditFinding",
    properties={
        "title": PropertyDef(name="title", property_type=PropertyType.STRING),
    },
    security=SecurityPolicy(classification=SecurityLevel.INTERNAL),
)
""",
        source_pr="PR#properties",
    )

    type_spec = snapshot["types"][0]
    assert type_spec["properties"] != {}
    assert type_spec["security"] is not None


def test_promoted_type_absence_is_detected() -> None:
    snapshots = [
        {
            "source": "origin/main",
            "types": [{
                "name": "StableType",
                "api_name": "dharma.core.StableType",
                "status": "promoted",
                "source_pr": "origin/main",
            }],
        },
        {
            "source": "PR#removal",
            "types": [],
        },
    ]

    conflicts = _detect_conflicts(snapshots)

    assert [conflict.rule for conflict in conflicts] == ["ALIGN-006"]
    assert "deprecation marker" not in conflicts[0].summary
