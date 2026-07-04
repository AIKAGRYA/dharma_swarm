from __future__ import annotations

import pytest

from scripts.verify.runtime_live_cockpit_probe import run_probe


@pytest.mark.asyncio
async def test_runtime_live_cockpit_probe_observes_running_graph(tmp_path) -> None:
    output_path = tmp_path / "live_cockpit_probe.json"

    proof = await run_probe(
        runtime_db=tmp_path / "runtime.db",
        ledger_dir=tmp_path / "ledgers",
        output_path=output_path,
    )

    assert output_path.exists()
    assert proof["schema_version"] == (
        "dharma.langgraph_parity.phase7_live_cockpit_probe.v1"
    )
    assert proof["observed_while_runner_blocked"] is True
    assert proof["api_running_summary"]["active_run_count"] >= 1
    assert proof["running_graph_assertions"]["active_agent"] == "lead"
    assert proof["running_graph_assertions"]["run_status"] == "running"
    assert proof["running_graph_assertions"]["topology_state_status"] == "running"
    assert proof["running_graph_assertions"]["event_count"] >= 1
    assert proof["completed_summary"]["run_status"] == "completed"
