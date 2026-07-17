import json

import pytest

from scripts.runtime import ci_truth


def _contract():
    return {
        "schema": "dharma.ci_truth_contract.v1",
        "version": 1,
        "required": [
            {
                "id": "docops",
                "names": ["DocOps integrity gate"],
                "owner": "docops",
                "local_command": "make docops-integrity",
                "failure_category": "doc_drift",
                "autofix": "limited",
            }
        ],
        "advisory": [
            {
                "id": "tests",
                "names": ["pytest (3.11)", "pytest (3.12)"],
                "owner": "runtime",
                "local_command": "make test",
                "failure_category": "test_failure",
                "autofix": "manual",
            }
        ],
    }


def test_ci_truth_blocks_missing_required_check():
    result = ci_truth.evaluate_rollup([], _contract())

    assert result["verdict"] == "FAIL"
    assert result["required"][0]["status"] == "MISSING"
    assert "required CI docops is MISSING" in result["merge_blockers"][0]


def test_ci_truth_degrades_missing_advisory_check():
    result = ci_truth.evaluate_rollup(
        [
            {
                "name": "DocOps integrity gate",
                "status": "COMPLETED",
                "conclusion": "SUCCESS",
            }
        ],
        _contract(),
    )

    assert result["verdict"] == "DEGRADED"
    assert result["merge_blockers"] == []
    assert result["advisory"][0]["status"] == "MISSING"


def test_ci_truth_passes_latest_matching_required_and_advisory_checks():
    result = ci_truth.evaluate_rollup(
        [
            {
                "name": "DocOps integrity gate",
                "status": "COMPLETED",
                "conclusion": "FAILURE",
                "completedAt": "2026-06-05T00:00:00Z",
            },
            {
                "name": "DocOps integrity gate",
                "status": "COMPLETED",
                "conclusion": "SUCCESS",
                "completedAt": "2026-06-05T00:01:00Z",
            },
            {
                "name": "pytest (3.12)",
                "status": "COMPLETED",
                "conclusion": "SUCCESS",
            },
        ],
        _contract(),
    )

    assert result["verdict"] == "PASS"
    assert result["required"][0]["status"] == "PASS"
    assert result["advisory"][0]["matched_name"] == "pytest (3.12)"
    assert result["raw_total"] == 3
    assert result["observed_total"] == 2


def test_ci_truth_records_uncontracted_checks_as_warnings():
    result = ci_truth.evaluate_rollup(
        [
            {
                "name": "DocOps integrity gate",
                "status": "COMPLETED",
                "conclusion": "SUCCESS",
            },
            {
                "name": "pytest (3.11)",
                "status": "COMPLETED",
                "conclusion": "SUCCESS",
            },
            {
                "name": "surprise-check",
                "status": "COMPLETED",
                "conclusion": "SUCCESS",
            },
        ],
        _contract(),
    )

    assert result["verdict"] == "PASS"
    assert result["unknown_checks"] == ["surprise-check"]
    assert any("uncontracted GitHub checks observed" in warning for warning in result["warnings"])


def test_default_ci_truth_required_set_equals_parity_manifest() -> None:
    contract = ci_truth.load_contract()
    manifest = ci_truth.load_json(ci_truth.DEFAULT_PARITY_MANIFEST_PATH)

    assert set(ci_truth.required_context_names(contract)) == set(
        ci_truth.manifest_required_context_names(manifest)
    )


def test_ci_truth_contract_fails_closed_when_required_set_drifts(tmp_path) -> None:
    contract = json.loads(ci_truth.DEFAULT_CONTRACT_PATH.read_text(encoding="utf-8"))
    manifest = json.loads(
        ci_truth.DEFAULT_PARITY_MANIFEST_PATH.read_text(encoding="utf-8")
    )
    manifest["required_contexts"] = manifest["required_contexts"][:-1]
    manifest_path = tmp_path / "parity.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    contract["required_contexts_manifest"] = str(manifest_path)
    contract_path = tmp_path / "contract.json"
    contract_path.write_text(json.dumps(contract), encoding="utf-8")

    with pytest.raises(ci_truth.CITruthError, match="disagree"):
        ci_truth.load_contract(contract_path)
