from __future__ import annotations

import importlib.util
import json

import pytest

from dharma_swarm.memory_kernel.write_receipts import stable_digest
from scripts.governance import dharmagraph_parity_gauntlet as cli
from tests.oracle_support.dharmagraph_gauntlet import (
    langgraph_public_surface_manifest,
    run_capability_probes,
)


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


def test_public_surface_manifest_normalizes_process_addresses() -> None:
    first = langgraph_public_surface_manifest()
    second = langgraph_public_surface_manifest()

    assert first == second
    assert not any("0x" in entry and "0xADDR" not in entry for entry in first)


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


def test_self_declared_na_is_rejected_without_frozen_ratification() -> None:
    row = {
        "id": "X",
        "name": "x",
        "class": "core",
        "weight": 1,
        "gap_card": "gap-x",
        "facets": ["a"],
    }
    observation = {
        "points": "N/A",
        "verdict": "not_applicable",
        "operator_ratified_non_goal": "builder says this row is a non-goal now",
        "facets": {
            "a": {
                "status": "missing",
                "evidence": [
                    {
                        "kind": "probe",
                        "id": "probe-x",
                        "command_or_probe": "execute probe-x",
                        "outcome": "observed",
                        "dharma": {"value": 1},
                        "langgraph": {"value": 1},
                        "citations": ["tests/test_dharmagraph_parity_gauntlet.py:1"],
                    }
                ],
            }
        },
    }

    with pytest.raises(cli.GauntletError, match="na_rule"):
        cli._normalize_capability(row, observation, ratified_ids=frozenset())

    ratified = cli._normalize_capability(
        row, observation, ratified_ids=frozenset({"X"})
    )
    assert ratified["points"] == "N/A"

    assert cli._ratified_exclusion_ids(None) == frozenset()
    assert cli._ratified_exclusion_ids(["X", {"capability_id": "Y"}]) == frozenset(
        {"X", "Y"}
    )


def test_presentation_findings_catch_forged_grade_fields() -> None:
    stable_core = {
        "score": "31.00",
        "gap_ids": ["LG01"],
        "closeout_blocked": True,
    }
    honest = {
        "score": {"earned": "31.00", "display": "31.00/100"},
        "verdict": "NOT_FINISHED",
        "closeout_blocked": True,
        "gaps": [{"capability_id": "LG01"}],
        "stable_core": stable_core,
    }
    assert cli._presentation_findings(honest) == []

    forged = json.loads(json.dumps(honest))
    forged["score"]["display"] = "100.00/100"
    forged["score"]["earned"] = "100.00"
    forged["verdict"] = "FINISHED"
    forged["closeout_blocked"] = False
    forged["gaps"] = []
    findings = cli._presentation_findings(forged)
    assert "presented earned score diverges from sealed core" in findings
    assert "presented verdict diverges from sealed core" in findings
    assert "presented closeout_blocked diverges from sealed core" in findings
    assert "presented gap list diverges from sealed core" in findings


def test_judge_findings_require_binding_and_match() -> None:
    builder_core = {"score": "31.00"}
    builder = {
        "score": {"earned": "31.00"},
        "stable_core": builder_core,
        "stable_digest": stable_digest(builder_core),
    }
    builder["digest"] = cli._receipt_digest(builder)

    judge_core = {"score": "31.00"}
    judge = {
        "score": {"earned": "31.00"},
        "stable_core": judge_core,
        "stable_digest": builder["stable_digest"],
        "judge": {
            "builder_receipt_digest": builder["digest"],
            "reconciliation": "MATCH",
        },
    }
    judge["digest"] = cli._receipt_digest(judge)
    assert cli._judge_findings(builder, judge) == []

    discrepant = json.loads(json.dumps(judge))
    discrepant["judge"]["reconciliation"] = "DISCREPANCY"
    discrepant["digest"] = cli._receipt_digest(discrepant)
    assert "judge reconciliation is not MATCH" in cli._judge_findings(
        builder, discrepant
    )

    unbound = json.loads(json.dumps(judge))
    unbound["judge"]["builder_receipt_digest"] = "0" * 64
    unbound["digest"] = cli._receipt_digest(unbound)
    assert "judge receipt does not bind the stored builder receipt" in (
        cli._judge_findings(builder, unbound)
    )

    tampered = json.loads(json.dumps(judge))
    tampered["score"]["earned"] = "100.00"
    assert cli._judge_findings(builder, tampered) == ["judge receipt digest invalid"]


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
                    },
                    "alpha": {
                        "status": "missing",
                        "evidence": [{"id": "probe-alpha", "kind": "probe"}],
                    },
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
    assert matrix == cli.render_matrix(json.loads(json.dumps(receipt, sort_keys=True)))


@pytest.mark.skipif(
    importlib.util.find_spec("langgraph") is None,
    reason="test-oracle extra not installed; the oracle CI lane runs this",
)
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

    # The persistence kernel must prove native identity/journal behavior rather
    # than relabel explicit checkpoints or atomic rollback.
    assert result["capabilities"]["LG15"]["facets"]["thread_resume"]["status"] == "pass"
    assert result["capabilities"]["LG15"]["points"] == 2
    assert (
        result["capabilities"]["LG35"]["facets"]["graph_drained"]["status"] == "missing"
    )
    assert result["capabilities"]["LG35"]["points"] == 0
    assert (
        result["capabilities"]["LG18"]["facets"]["pending_write_recovery"]["status"]
        == "pass"
    )
    assert result["capabilities"]["LG18"]["points"] == 2
    assert (
        result["capabilities"]["PERF01"]["facets"]["environment_metadata"]["status"]
        == "pass"
    )
    assert result["capabilities"]["PB01"]["points"] == 0
    assert result["capabilities"]["PB01"]["facets"]["tool_node"]["status"] == "missing"
    assert result["completeness_control"]["id"] == "COMPLETE01"

    restart = result["raw_evidence"]["process_restart"]
    assert restart["dharma"]["persistence"] == "native_graph_persistence_kernel"
    for arm in ("dharma", "langgraph"):
        assert restart[arm]["fresh_process_count"] == 2
        assert restart[arm]["phases"][0]["log"] == ["a"]
        assert restart[arm]["resumed"]["log"] == ["a", "b", "c"]
