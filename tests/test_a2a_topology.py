from __future__ import annotations

from scripts.runtime import a2a_topology


def test_compatibility_and_target_a2a_topologies_remain_explicitly_distinct() -> None:
    assert a2a_topology.LIVE_COMPATIBILITY_STREAM == "DHARMA_A2A"
    assert a2a_topology.TARGET_TASK_STREAM == "DS_TASKS"
    assert a2a_topology.TARGET_DLQ_STREAM == "DS_DLQ"
    assert a2a_topology.DEFAULT_COMPATIBILITY_STREAM != a2a_topology.TARGET_TASK_STREAM
