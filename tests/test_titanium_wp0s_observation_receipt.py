from __future__ import annotations

import copy
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
VALIDATOR_PATH = (
    ROOT / "scripts" / "governance" / "validate_titanium_wp0s_observation_receipt.py"
)
RECEIPT_PATH = (
    ROOT
    / "reports"
    / "governance"
    / "titanium"
    / "wp0s_observation_receipt_20260801.json"
)


def _load_validator():
    spec = importlib.util.spec_from_file_location("wp0s_receipt_validator", VALIDATOR_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_receipt() -> dict[str, object]:
    return json.loads(RECEIPT_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def validator():
    return _load_validator()


def test_committed_receipt_validates(validator) -> None:
    assert validator.validate_receipt(_load_receipt()) == []


def test_receipt_is_bounded_and_operator_blocked() -> None:
    receipt = _load_receipt()

    assert receipt["authority"] == "implementation_observer"
    assert receipt["inventory_complete"] is False
    assert receipt["status"] == "BLOCKED_OPERATOR"
    assert receipt["operator_attestation"] == {
        "present": False,
        "attestor": None,
        "attested_at": None,
        "exact_host_scope": [],
    }
    assert receipt["verdict"] == {
        "classification": "BLOCKED_OPERATOR",
        "live_exposure": "observed",
        "operator_action": "required",
        "phase0_promotion": "forbidden",
    }
    assert receipt["secret_policy"]["secret_values_accessed"] is False


def test_evidence_modalities_remain_distinct_and_populated() -> None:
    receipt = _load_receipt()
    evidence = receipt["evidence"]

    assert set(evidence) == {"live_host", "listener", "public_http", "code_version"}
    assert all(evidence[modality] for modality in evidence)


def test_meghadharma_runtime_secret_name_presence_is_not_collapsed() -> None:
    receipt = _load_receipt()
    observations = {
        item["runtime_id"]: item["names_present"]
        for item in receipt["secret_name_observations"]
        if item["host_id"] == "meghadharma"
    }

    assert observations["legacy-command-backend"] == {
        "DASHBOARD_API_KEY": True,
        "DHARMA_VERIFY_WEBHOOK_SECRET": False,
        "DHARMA_API_MODE": False,
    }
    assert observations["dharmic-quant-web"] == {
        "DASHBOARD_API_KEY": False,
        "DHARMA_VERIFY_WEBHOOK_SECRET": False,
        "DHARMA_API_MODE": False,
    }


@pytest.mark.parametrize("promotion", ["PASS", "CLOSED", "CLOSED_NOT_PROD", "CLOSED_LIVE"])
def test_promotional_status_without_attestation_is_rejected(validator, promotion) -> None:
    receipt = _load_receipt()
    receipt["status"] = promotion
    receipt["verdict"]["classification"] = promotion

    errors = validator.validate_receipt(receipt)

    assert any("operator attestation" in error for error in errors)


def test_complete_inventory_requires_exact_attested_host_scope(validator) -> None:
    receipt = _load_receipt()
    receipt["inventory_complete"] = True
    receipt["status"] = "PASS"
    receipt["verdict"]["classification"] = "PASS"
    receipt["operator_attestation"] = {
        "present": True,
        "attestor": "operator-fixture",
        "attested_at": "2026-08-01T07:00:00Z",
        "exact_host_scope": ["local_mac", "agni", "rushabdev"],
    }

    errors = validator.validate_receipt(receipt)

    assert any("exact host scope" in error for error in errors)


@pytest.mark.parametrize(
    "leak",
    [
        "api_key=fixture-secret-material",
        "Authorization: Bearer fixture-token-material",
        "password=fixture-password-material",
        "github_pat_fixture123456789",
    ],
)
def test_secret_looking_values_are_rejected(validator, leak) -> None:
    receipt = _load_receipt()
    receipt["claim_boundary"] += f" {leak}"

    errors = validator.validate_receipt(receipt)

    assert any("secret-like value" in error for error in errors)


def test_secret_presence_claims_must_be_booleans(validator) -> None:
    receipt = _load_receipt()
    receipt["secret_name_observations"][0]["names_present"]["DASHBOARD_API_KEY"] = (
        "not-observed"
    )

    errors = validator.validate_receipt(receipt)

    assert any("boolean" in error for error in errors)


@pytest.mark.parametrize("modality", ["live_host", "listener", "public_http", "code_version"])
def test_empty_evidence_modality_is_rejected(validator, modality) -> None:
    receipt = _load_receipt()
    receipt["evidence"][modality] = []

    errors = validator.validate_receipt(receipt)

    assert any(modality in error for error in errors)


def test_host_scope_must_be_exact_and_unique(validator) -> None:
    receipt = _load_receipt()
    receipt["exact_host_scope"].append("agni")

    duplicate_errors = validator.validate_receipt(receipt)

    assert any("unique" in error for error in duplicate_errors)

    receipt = _load_receipt()
    receipt["exact_host_scope"].remove("meghadharma")

    incomplete_errors = validator.validate_receipt(receipt)

    assert any("evidence host scope" in error for error in incomplete_errors)


@pytest.mark.parametrize(
    ("field", "value", "expected_error"),
    [
        ("active_track", "shadow-track", "active_track must equal"),
        ("base_ref", "deadbeef", "sealed packet base"),
    ],
)
def test_track_and_base_are_pinned(validator, field, value, expected_error) -> None:
    receipt = _load_receipt()
    receipt[field] = value

    errors = validator.validate_receipt(receipt)

    assert any(expected_error in error for error in errors)


@pytest.mark.parametrize("shadow", ["effective_authority", "effective_status"])
def test_unknown_top_level_shadow_fields_are_rejected(validator, shadow) -> None:
    receipt = _load_receipt()
    receipt[shadow] = "operator"

    errors = validator.validate_receipt(receipt)

    assert any("top-level keys must be exact" in error for error in errors)


def test_cli_json_success() -> None:
    result = subprocess.run(
        [sys.executable, str(VALIDATOR_PATH), str(RECEIPT_PATH), "--json"],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert json.loads(result.stdout) == {
        "error_count": 0,
        "receipt_is_operator_blocked": True,
        "validation_status": "VALID",
    }


def test_cli_failure_does_not_log_receipt_derived_diagnostics(tmp_path: Path) -> None:
    receipt = _load_receipt()
    marker = "fixture-secret-material"
    receipt["claim_boundary"] += f" api_key={marker}"
    invalid_path = tmp_path / "invalid-receipt.json"
    invalid_path.write_text(json.dumps(receipt), encoding="utf-8")

    result = subprocess.run(
        [sys.executable, str(VALIDATOR_PATH), str(invalid_path), "--json"],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert marker not in result.stdout
    assert marker not in result.stderr
    assert json.loads(result.stdout) == {
        "error_count": 1,
        "receipt_is_operator_blocked": False,
        "validation_status": "INVALID",
    }


def test_validator_does_not_mutate_input(validator) -> None:
    receipt = _load_receipt()
    before = copy.deepcopy(receipt)

    validator.validate_receipt(receipt)

    assert receipt == before
