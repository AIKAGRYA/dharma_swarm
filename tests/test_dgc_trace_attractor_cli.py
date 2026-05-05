"""Tests for ``dgc trace-attractor`` CLI command.

Verifies the CLI entry point produces correct JSON and human-readable output.
"""

from __future__ import annotations

import json

import pytest

from dharma_swarm.trace_attractor.cli import run_trace_attractor


def test_cli_json_output_empty_trace(tmp_path):
    """CLI with --json on empty trace produces valid JSON."""
    result = run_trace_attractor(
        trace_id="trc_nonexistent",
        as_json=True,
        registry_path=str(tmp_path / "ontology.db"),
        runtime_db=str(tmp_path / "runtime.db"),
        telemetry_db=str(tmp_path / "telemetry.db"),
    )

    data = json.loads(result)
    assert data["schema_version"] == 1
    assert data["trace_id"] == "trc_nonexistent"
    assert data["proposal_ids"] == []
    assert data["fourfold_warrant"]["status"] == "unknown"


def test_cli_human_output_empty_trace(tmp_path):
    """CLI without --json produces human-readable summary."""
    result = run_trace_attractor(
        trace_id="trc_abc",
        as_json=False,
        registry_path=str(tmp_path / "ontology.db"),
        runtime_db=str(tmp_path / "runtime.db"),
        telemetry_db=str(tmp_path / "telemetry.db"),
    )

    assert "trc_abc" in result
    assert "proposals:" in result


def test_cli_deterministic_json(tmp_path):
    """Two identical calls produce identical JSON (minus generated_at)."""
    kwargs = dict(
        trace_id="trc_det",
        as_json=True,
        registry_path=str(tmp_path / "ontology.db"),
        runtime_db=str(tmp_path / "runtime.db"),
        telemetry_db=str(tmp_path / "telemetry.db"),
    )
    r1 = json.loads(run_trace_attractor(**kwargs))
    r2 = json.loads(run_trace_attractor(**kwargs))
    r1.pop("generated_at")
    r2.pop("generated_at")
    assert r1 == r2
