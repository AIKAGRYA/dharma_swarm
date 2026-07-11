from __future__ import annotations

import pytest

from dharma_swarm.memory_kernel.write_receipts import stable_digest
from scripts.governance import dharmagraph_parity_gauntlet as cli
from tests.oracle_support.dharmagraph_gauntlet import run_capability_probes


def _rubric() -> dict:
    return cli._load_materialized_rubric()


def test_frozen_rubric_is_complete_weighted_and_void_old_scores() -> None:
    rubric = _rubric()
    rows = rubric["capabilities"]

    assert rubric["status"] == "FROZEN_BEFORE_V2_RESULTS"
    assert rubric["prior_scores"]["status"] == "VOID"
    assert rubric["prior_scores"]["v1_provisional"].startswith("VOID_")
    assert len(rows) == 41
    assert len({row["id"] for row in rows}) == len(rows)
    assert sum(row["weight"] for row in rows) == 100
    assert {"LG15", "LG17", "LG18"} <= {
        row_id
        for row_id, floor in rubric["weighting"]["claim_critical_floors"].items()
        if floor >= 8
    }
    assert rubric["corpus"]["june_task_count"] == 26
    assert rubric["corpus"]["june_multi_hop_subset_count"] == 12
    assert rubric["corpus"]["broken_control"]["id"] == "CTRL01"
    assert rubric["corpus"]["completeness_control"]["id"] == "COMPLETE01"
    assert rows[-1]["id"] == "PB01"
    assert "delta_channel" in next(row for row in rows if row["id"] == "LG10")["facets"]
    assert (
        "typed_v2_invoke" in next(row for row in rows if row["id"] == "LG12")["facets"]
    )


def test_capability_points_are_derived_from_facet_statuses() -> None:
    row = {
        "id": "X",
        "name": "x",
        "class": "core",
        "weight": 1,
        "gap_card": "gap-x",
        "facets": ["a", "b"],
    }
    evidence = [
        {
            "kind": "probe",
            "id": "probe-x",
            "command_or_probe": "execute probe-x",
            "outcome": "observed",
            "dharma": {"value": 1},
            "langgraph": {"value": 1},
            "citations": ["tests/test_dharmagraph_parity_gauntlet.py:24"],
        }
    ]

    with pytest.raises(cli.GauntletError, match="disagree with frozen facet rule"):
        cli._normalize_capability(
            row,
            {
                "points": 2,
                "verdict": "incorrect",
                "facets": {
                    "a": {"status": "pass", "evidence": evidence},
                    "b": {"status": "missing", "evidence": evidence},
                },
            },
        )


def test_capability_requires_executed_evidence_for_every_facet() -> None:
    row = {
        "id": "X",
        "name": "x",
        "class": "core",
        "weight": 1,
        "gap_card": "gap-x",
        "facets": ["a"],
    }

    with pytest.raises(cli.GauntletError, match="no executed evidence"):
        cli._normalize_capability(
            row,
            {
                "points": 0,
                "verdict": "missing",
                "facets": {"a": {"status": "missing", "evidence": []}},
            },
        )


def test_two_digest_receipt_validation_detects_tampering() -> None:
    stable_core = {"score": "12.00", "gap_ids": ["LG01"]}
    receipt = {
        "observed_at": "2026-07-11T00:00:00Z",
        "stable_core": stable_core,
        "stable_digest": stable_digest(stable_core),
    }
    receipt["digest"] = cli._receipt_digest(receipt)

    cli._validate_receipt_digest(receipt)
    receipt["observed_at"] = "2026-07-12T00:00:00Z"
    with pytest.raises(cli.GauntletError, match="receipt digest mismatch"):
        cli._validate_receipt_digest(receipt)


def test_matrix_leads_with_number_and_named_gap() -> None:
    receipt = {
        "score": {"display": "12.00/100"},
        "verdict": "NOT_FINISHED",
        "closeout_blocked": True,
        "environment": {"langgraph_version": "1.2.4"},
        "shas": {"langgraph_git_sha": "a", "dharma_git_sha": "b"},
        "rubric": {"rubric_commit_sha": "c"},
        "gaps": [
            {
                "capability_id": "LG01",
                "name": "Schemas",
                "points": 1,
                "weight": 4,
                "gap_card": "parity-gap-lg01-schemas",
            }
        ],
        "capabilities": [
            {
                "id": "LG01",
                "name": "Schemas",
                "weight": 4,
                "points": 1,
                "facets": {
                    "schema": {
                        "status": "pass",
                        "evidence": [{"id": "probe-schema", "kind": "probe"}],
                    }
                },
                "caveats": ["partial"],
            }
        ],
        "control": {
            "id": "CTRL01",
            "comparison_verdict": "mismatch",
            "expected_failure_observed": True,
        },
        "performance": {},
        "stable_digest": "d",
    }

    matrix = cli.render_matrix(receipt)

    assert matrix.startswith("# DharmaGraph x LangGraph parity: 12.00/100")
    assert "parity-gap-lg01-schemas" in matrix
    assert "NOT_FINISHED" in matrix


def test_full_harness_covers_every_frozen_row_and_broken_control() -> None:
    rubric = _rubric()

    result = run_capability_probes(rubric, seed=20260711, performance_iterations=1)

    assert set(result["capabilities"]) == {row["id"] for row in rubric["capabilities"]}
    assert result["control"]["id"] == "CTRL01"
    assert result["control"]["comparison_verdict"] != "parity"
    assert result["control"]["expected_failure_observed"] is True
    for row in rubric["capabilities"]:
        observation = result["capabilities"][row["id"]]
        assert set(observation["facets"]) == set(row["facets"])
        for cell in observation["facets"].values():
            assert cell["status"] in {"pass", "partial", "missing", "fail"}
            assert cell["evidence"]
        integration = observation["facets"].get("neutral_engine_integration")
        if integration and integration["status"] != "pass":
            assert observation["points"] < 2

    # Guard against three attractive but false equivalences discovered in
    # adversarial review: explicit checkpoint objects are not thread-scoped
    # continuity, ordinary completion is not cooperative drain, and atomic
    # rollback is not pending-write recovery.
    assert (
        result["capabilities"]["LG15"]["facets"]["thread_resume"]["status"] == "missing"
    )
    assert result["capabilities"]["LG15"]["points"] == 0
    assert (
        result["capabilities"]["LG35"]["facets"]["graph_drained"]["status"] == "missing"
    )
    assert result["capabilities"]["LG35"]["points"] == 0
    assert (
        result["capabilities"]["LG18"]["facets"]["pending_write_recovery"]["status"]
        == "missing"
    )
    assert (
        result["capabilities"]["PERF01"]["facets"]["environment_metadata"]["status"]
        == "pass"
    )
    assert result["capabilities"]["PB01"]["points"] == 0
    assert result["capabilities"]["PB01"]["facets"]["tool_node"]["status"] == "missing"
    assert result["completeness_control"]["id"] == "COMPLETE01"

    restart = result["raw_evidence"]["process_restart"]
    for arm in ("dharma", "langgraph"):
        assert restart[arm]["fresh_process_count"] == 2
        assert restart[arm]["phases"][0]["log"] == ["a"]
        assert restart[arm]["resumed"]["log"] == ["a", "b", "c"]
