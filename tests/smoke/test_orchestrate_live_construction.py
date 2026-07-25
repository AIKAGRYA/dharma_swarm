"""Smoke tests: every loop's main agent class must construct with the args
``orchestrate_live.py`` actually passes.

These tests do NOT execute loops or call methods. They only verify that the
constructor signatures match between the orchestrator and the agent classes.

This catches:
  - Constructor signature drift (orchestrator passes args the class no longer accepts)
  - Missing required args (class added a required param the orchestrator doesn't pass)
  - Wrong arg names (e.g. ``state_dir=`` when class wants ``store=``)
  - Loops whose main agent has never actually been runnable

These bugs otherwise hide because ``orchestrate_live.py`` wraps each loop in
a broad ``except Exception`` that logs and continues — so a constructor that
raises ``TypeError`` produces a silent dead loop in production.

One test per loop. Each test replicates the *exact* construction call from
``orchestrate_live.py`` at the line number cited in the docstring.

If a test fails, the fix lives in either ``orchestrate_live.py`` (wrong call)
or the agent class (signature drift). Do not "fix" the test.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

# All loop agent classes used by orchestrate_live.py. Imports at module level
# so an ImportError surfaces as a collection error (also a real finding).
from dharma_swarm.archaeology_ingestion import ArchaeologyIngestionDaemon
from dharma_swarm.consolidation import ConsolidationCycle
from dharma_swarm.meta_daemon import RecognitionEngine
from dharma_swarm.orchestrate_live import STATE_DIR, WITNESS_INTERVAL
from dharma_swarm.replication_protocol import ReplicationProtocol
from dharma_swarm.revenue.scout_daemon import RevenueScoutDaemon
from dharma_swarm.s4.internal_pressure import InternalPressureScanner
from dharma_swarm.witness import WitnessAuditor
from dharma_swarm.world_model import WorldModelAgent
from dharma_swarm.zeitgeist import ZeitgeistScanner


# ---------------------------------------------------------------------------
# Recognition loop  (orchestrate_live.py:972)
# ---------------------------------------------------------------------------
def test_recognition_engine_constructs() -> None:
    """orchestrate_live.py:973 ``engine = RecognitionEngine()``"""
    engine = RecognitionEngine()
    assert engine is not None


# ---------------------------------------------------------------------------
# Witness loop  (orchestrate_live.py:1031)
# ---------------------------------------------------------------------------
def test_witness_auditor_constructs() -> None:
    """orchestrate_live.py:1032 ``auditor = WitnessAuditor(cycle_seconds=WITNESS_INTERVAL)``"""
    auditor = WitnessAuditor(cycle_seconds=WITNESS_INTERVAL)
    assert auditor is not None


# ---------------------------------------------------------------------------
# Consolidation loop  (orchestrate_live.py:1074)
# ---------------------------------------------------------------------------
def test_consolidation_cycle_constructs() -> None:
    """orchestrate_live.py:1075 ``cycle = ConsolidationCycle(state_dir=STATE_DIR)``"""
    cycle = ConsolidationCycle(state_dir=STATE_DIR)
    assert cycle is not None


def test_neural_consolidator_constructs() -> None:
    """orchestrate_live.py constructs NeuralConsolidator inside the consolidation
    loop. Defer the import to runtime to match orchestrate_live's lazy import
    pattern, then call with no args (all params are Optional).
    """
    from dharma_swarm.neural_consolidator import NeuralConsolidator

    consolidator = NeuralConsolidator()
    assert consolidator is not None


# ---------------------------------------------------------------------------
# Replication monitor loop  (orchestrate_live.py:1409)
# ---------------------------------------------------------------------------
def test_replication_protocol_constructs() -> None:
    """orchestrate_live.py:1410 ``protocol = ReplicationProtocol(state_dir=STATE_DIR)``"""
    protocol = ReplicationProtocol(state_dir=STATE_DIR)
    assert protocol is not None


# ---------------------------------------------------------------------------
# Zeitgeist loop  (orchestrate_live.py:1534)
# ---------------------------------------------------------------------------
def test_zeitgeist_scanner_constructs() -> None:
    """orchestrate_live.py:1535 ``scanner = ZeitgeistScanner(state_dir=STATE_DIR)``"""
    scanner = ZeitgeistScanner(state_dir=STATE_DIR)
    assert scanner is not None


# ---------------------------------------------------------------------------
# Internal-pressure loop  (orchestrate_live.py:1577)
# ---------------------------------------------------------------------------
def test_internal_pressure_scanner_constructs() -> None:
    """orchestrate_live.py:1578 ``scanner = InternalPressureScanner(state_dir=STATE_DIR)``"""
    scanner = InternalPressureScanner(state_dir=STATE_DIR)
    assert scanner is not None


# ---------------------------------------------------------------------------
# World-model loop  (orchestrate_live.py:1654)
# ---------------------------------------------------------------------------
@pytest.mark.xfail(
    strict=True,
    reason=(
        "FINDING (construction defect): orchestrate_live.py:1663 calls "
        "WorldModelAgent(state_dir=STATE_DIR) but the real signature "
        "(world_model.py:265) is WorldModelAgent(store, search_tool, arxiv_tool) "
        "and it exposes boot(), not initialize(). The world-model loop has never "
        "been constructable; the broad except in _run_world_model_loop hides it as "
        "a silent dead loop. Fix lives in orchestrate_live.py (real wiring: build a "
        "WorldModelStore + tools, call boot()) — owned by the loop-closure track "
        "(overlaps #590), not in this test. Strict xfail flips the moment the loop "
        "is wired, forcing this marker's removal."
    ),
)
def test_world_model_agent_constructs_as_orchestrate_live_calls_it() -> None:
    """orchestrate_live.py:1663 currently calls ``WorldModelAgent(state_dir=STATE_DIR)``.

    The real signature at world_model.py:265 is::

        WorldModelAgent(store, search_tool, arxiv_tool)

    There is no ``state_dir`` keyword. This test replicates the orchestrator's
    actual call so the signature mismatch is surfaced explicitly.

    This is a tracked finding (strict xfail): the world-model loop is not
    constructable as written. The fix lives in orchestrate_live.py (use the real
    API) — not in this test. When the loop is wired, this xfail xpasses and the
    strict marker fails, forcing the marker's removal.
    """
    agent = WorldModelAgent(state_dir=STATE_DIR)  # type: ignore[call-arg]
    assert agent is not None


# ---------------------------------------------------------------------------
# Archaeology loop  (orchestrate_live.py:1843)
# ---------------------------------------------------------------------------
def test_archaeology_ingestion_daemon_constructs() -> None:
    """orchestrate_live.py:1850 ``daemon = ArchaeologyIngestionDaemon(state_dir=STATE_DIR, interval_seconds=1800)``"""
    daemon = ArchaeologyIngestionDaemon(state_dir=STATE_DIR, interval_seconds=1800)
    assert daemon is not None


# ---------------------------------------------------------------------------
# Revenue scout loop  (orchestrate_live.py:1974)
# ---------------------------------------------------------------------------
def test_revenue_scout_daemon_constructs() -> None:
    """orchestrate_live.py:1981 ``daemon = RevenueScoutDaemon()``"""
    daemon = RevenueScoutDaemon()
    assert daemon is not None


# ---------------------------------------------------------------------------
# Persistent agents (multiple instances spawned by internal_pressure loop)
# ---------------------------------------------------------------------------
def test_persistent_agent_constructs_with_minimal_config() -> None:
    """orchestrate_live.py constructs PersistentAgent from a config dict.

    Use the smallest viable config that matches the kwargs the orchestrator
    passes (name, role, provider_type, model, state_dir, wake_interval_seconds,
    system_prompt, max_turns).

    This test only verifies construction. It does NOT start the agent's wake
    loop. If required dependencies (provider, etc.) cannot be resolved without
    network/credentials, the test will surface that as a real finding.
    """
    from dharma_swarm.models import AgentRole, ProviderType
    from dharma_swarm.persistent_agent import PersistentAgent

    agent = PersistentAgent(
        name="smoke-test-agent",
        role=AgentRole.RESEARCHER,
        provider_type=ProviderType.ANTHROPIC,
        model="claude-3-5-sonnet-20241022",
        state_dir=STATE_DIR,
        wake_interval_seconds=3600,
        system_prompt="smoke test",
        max_turns=1,
    )
    assert agent is not None


# ---------------------------------------------------------------------------
# Meta sanity: ensure we covered every loop with a top-level _run_*_loop
# ---------------------------------------------------------------------------
def test_smoke_suite_covers_known_loops() -> None:
    """Read orchestrate_live.py and assert each ``async def _run_*_loop`` has
    at least one corresponding smoke test in this file.

    This is a guard: if a new loop is added to orchestrate_live, this test
    fails until a smoke test is added here too.

    Loops with no constructable main agent (e.g. gauntlet_loop calls
    ``run_gauntlet()`` directly, guardian_loop calls ``start_guardian_loop()``,
    room_health_loop operates on injected registries) are listed in the
    expected-exempt set with a reason.
    """
    import re

    orch = (Path(__file__).resolve().parents[2] / "dharma_swarm" / "orchestrate_live.py").read_text()
    loop_names = set(re.findall(r"^async def (_run_\w+_loop)\b", orch, flags=re.MULTILINE))
    loop_names.discard("_run_recognition_loop_UNUSED")

    # Loops we deliberately don't smoke-construct (they have no single main agent class)
    exempt = {
        "_run_gauntlet_loop": "calls run_gauntlet() function, no class to construct",
        "_run_guardian_loop": "calls start_guardian_loop() function, no class to construct",
        "_run_room_health_loop": "operates on injected registry+bridge, no class constructed inside",
    }

    covered_by_this_file = {
        "_run_recognition_loop",
        "_run_witness_loop",
        "_run_consolidation_loop",
        "_run_replication_monitor_loop",
        "_run_zeitgeist_loop",
        "_run_internal_pressure_loop",
        "_run_world_model_loop",
        "_run_archaeology_loop",
        "_run_revenue_scout_loop",
    }

    uncovered = loop_names - covered_by_this_file - set(exempt.keys())
    assert not uncovered, (
        f"New loops added to orchestrate_live.py without smoke tests: {sorted(uncovered)}. "
        f"Either add a smoke test above, or add to the exempt set with a reason."
    )
