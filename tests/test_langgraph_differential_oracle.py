"""Differential oracle: dharma langgraph_parity clone vs REAL langgraph 1.2.4.

dharmagraph-engine-2026-07, spec §3 Phase 1. The parity harness under
``dharma_swarm/langgraph_parity/`` is a self-graded clone ("intentionally
avoids importing LangGraph"); this suite is the first real oracle: every
scenario runs through BOTH engines and the SEMANTIC outcomes (final active
agent, receipt sequence, message-visibility sets, final state shape) are
diffed — never text. A machine-readable diff report is written per run
(DHARMA_ORACLE_REPORT_PATH, default under ~/.dharma/oracle/).

Divergences are findings, not failures to hide: an adjudicated deviation
(documented in docs/langgraph_parity/LANGGRAPH_PARITY_CONTRACT.md) passes
and is recorded in the report; an UNDOCUMENTED divergence fails the test.

Requires the ``test-oracle`` extra (langgraph==1.2.4); the module skips
cleanly when it is not installed so the default suite stays hermetic.
"""

from __future__ import annotations

from importlib.metadata import version

import pytest

pytest.importorskip("langgraph", reason="test-oracle extra not installed")

# The adjudicated deviations and the diff report are specific to the pinned
# oracle version — running against whatever the `infra` extra resolved would
# produce false parity/divergence results. Skip loudly on any other version.
_ORACLE_PIN = "1.2.4"
if version("langgraph") != _ORACLE_PIN:
    pytest.skip(
        f"oracle pinned to langgraph=={_ORACLE_PIN} (test-oracle extra);"
        f" found {version('langgraph')}",
        allow_module_level=True,
    )

from tests.oracle_support.langgraph_arm import (  # noqa: E402
    run_langgraph_supervisor,
    run_langgraph_swarm,
)
from tests.oracle_support.outcomes import diff_outcomes, write_report  # noqa: E402
from tests.oracle_support.scenarios import (  # noqa: E402
    SUPERVISOR_SCENARIOS,
    SWARM_SCENARIOS,
    run_dharma_supervisor,
    run_dharma_swarm,
)

_ENTRIES: list[dict] = []

# Phase-1 acceptance floor: the oracle must exercise >= 12 scenarios.
_SCENARIO_FLOOR = 12


@pytest.fixture(scope="module", autouse=True)
def _report_artifact():
    """Write the machine-readable diff report after the module runs."""
    yield
    if _ENTRIES:
        path = write_report(_ENTRIES, langgraph_version=version("langgraph"))
        print(f"\noracle diff report: {path}")


def _record(spec, dharma, langgraph_outcome):
    diff = diff_outcomes(spec, dharma, langgraph_outcome)
    _ENTRIES.append(
        {
            "scenario": spec.name,
            "kind": spec.kind,
            "dharma": dharma,
            "langgraph": langgraph_outcome,
            "diff": diff.to_dict(),
        }
    )
    return diff


def test_scenario_inventory_meets_phase1_floor():
    assert len(SWARM_SCENARIOS) + len(SUPERVISOR_SCENARIOS) >= _SCENARIO_FLOOR


@pytest.mark.parametrize(
    "scenario", SWARM_SCENARIOS, ids=[s.spec.name for s in SWARM_SCENARIOS]
)
def test_swarm_scenarios_semantic_parity(scenario, tmp_path):
    dharma = run_dharma_swarm(scenario, tmp_path)
    langgraph_outcome = run_langgraph_swarm(scenario, tmp_path)
    diff = _record(scenario.spec, dharma, langgraph_outcome)
    assert diff.is_parity, (
        f"UNDOCUMENTED divergence in {scenario.spec.name}: "
        f"{diff.unexpected_divergences} — adjudicate it (spec bug or deliberate"
        " deviation) in docs/langgraph_parity/LANGGRAPH_PARITY_CONTRACT.md"
    )


@pytest.mark.parametrize(
    "scenario", SUPERVISOR_SCENARIOS, ids=[s.spec.name for s in SUPERVISOR_SCENARIOS]
)
def test_supervisor_scenarios_semantic_parity(scenario, tmp_path):
    dharma = run_dharma_supervisor(scenario, tmp_path)
    langgraph_outcome = run_langgraph_supervisor(scenario, tmp_path)
    diff = _record(scenario.spec, dharma, langgraph_outcome)
    assert diff.is_parity, (
        f"UNDOCUMENTED divergence in {scenario.spec.name}: "
        f"{diff.unexpected_divergences} — adjudicate it (spec bug or deliberate"
        " deviation) in docs/langgraph_parity/LANGGRAPH_PARITY_CONTRACT.md"
    )


def test_rejection_receipt_deviation_is_found_and_adjudicated(tmp_path):
    """Phase-1 acceptance: >=1 REAL divergence found and adjudicated.

    The receipts-first deviation must actually SHOW UP in the diff (dharma
    records a rejected TransferReceipt; langgraph-native tool dispatch
    records nothing durable) — if the two engines ever agree here, the
    documented deviation is stale and must be removed from the contract.
    """
    scenario = next(
        s
        for s in SWARM_SCENARIOS
        if s.spec.name == "swarm_rejected_transfer_tool_not_visible"
    )
    dharma = run_dharma_swarm(scenario, tmp_path)
    langgraph_outcome = run_langgraph_swarm(scenario, tmp_path)
    diff = diff_outcomes(scenario.spec, dharma, langgraph_outcome)
    assert diff.is_parity
    assert "receipts" in diff.adjudicated_deviations, (
        "expected the documented receipts deviation to be observed; if parity"
        " now holds, delete the stale adjudication from the contract doc"
    )
    assert dharma["receipts"] and dharma["receipts"][0]["status"] == "rejected"
    assert langgraph_outcome["receipts"] == []
    # The deviation is bounded: activation state stays identical.
    assert dharma["final_active_agent"] == langgraph_outcome["final_active_agent"]
