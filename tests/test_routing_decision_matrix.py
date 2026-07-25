from __future__ import annotations

import json
from pathlib import Path

from dharma_swarm.routing_decision_matrix import (
    ROUTING_DECISION_MATRIX_SCHEMA_VERSION,
    build_routing_decision_matrix,
    write_routing_decision_matrix,
)


def test_routing_decision_matrix_is_hermetic_and_passing() -> None:
    payload = build_routing_decision_matrix()

    assert payload["schema_version"] == ROUTING_DECISION_MATRIX_SCHEMA_VERSION
    assert payload["hermetic"] is True
    assert payload["live_calls_attempted"] == 0
    assert payload["status"] == "passed"
    assert payload["counts"]["policy_cases"] >= 4
    assert payload["counts"]["execution_cases"] >= 4
    assert payload["counts"]["failed"] == 0

    execution_by_name = {case["name"]: case for case in payload["execution_cases"]}
    assert execution_by_name["empty_response_falls_through"]["observed"]["selected_provider"] == "openrouter"
    assert execution_by_name["long_structured_quota_fast_trips"]["checks"]["open_breakers"] is True
    assert execution_by_name["key_liveness_prunes_dead_primary"]["observed"]["calls"]["openai"] == 0


def test_write_routing_decision_matrix_round_trips_json(tmp_path: Path) -> None:
    output = tmp_path / "routing_decision_matrix.json"
    payload = write_routing_decision_matrix(output)

    assert output.exists()
    loaded = json.loads(output.read_text(encoding="utf-8"))
    assert loaded["schema_version"] == payload["schema_version"]
    assert loaded["status"] == "passed"
