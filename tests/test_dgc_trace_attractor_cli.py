"""Tests for ``dgc trace-attractor`` CLI command.

Verifies the CLI entry point produces correct JSON and human-readable output
using the pure projector API (build_packet with empty events when stores
are unavailable).
"""

from __future__ import annotations

import json
import sys

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


def test_dgc_dispatch_wires_trace_attractor(monkeypatch, capsys):
    """Public dgc command dispatches to the Trace Attractor CLI runner."""
    from dharma_swarm import dgc_cli

    called = {}

    def fake_run_trace_attractor(**kwargs):
        called.update(kwargs)
        return "trace output"

    monkeypatch.setattr(
        "dharma_swarm.trace_attractor.cli.run_trace_attractor",
        fake_run_trace_attractor,
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "dgc",
            "trace-attractor",
            "--trace-id",
            "trc-cli",
            "--json",
            "--runtime-db",
            "/tmp/runtime.db",
        ],
    )

    dgc_cli.main()

    assert called["trace_id"] == "trc-cli"
    assert called["as_json"] is True
    assert called["runtime_db"] == "/tmp/runtime.db"
    assert capsys.readouterr().out.strip() == "trace output"
