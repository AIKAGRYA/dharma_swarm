"""Hermetic tests for the offline Helm seven-seat matrix harness."""

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timedelta, timezone
import importlib.util
import json
from pathlib import Path
import sys

import pytest

from dharma_swarm.helm_route_truth_types import (
    ACCEPTED_ROUTE_VERIFIER_ID,
    ACCEPTED_ROUTE_VERIFIER_VERSION,
    HELM_SLICE1_SEATS,
    RouteEvidence,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "verify" / "helm_seat_matrix.py"
NOW = datetime(2026, 9, 2, 4, 0, tzinfo=timezone.utc)
EPOCH = "helm-seat-matrix:test-epoch"


def _load_module():
    spec = importlib.util.spec_from_file_location("helm_seat_matrix", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def matrix():
    return _load_module()


def _evidence(index: int, *, receipt_ref: str | None = None) -> RouteEvidence:
    seat = HELM_SLICE1_SEATS[index]
    provider, model = seat.admissible_served_identities[0]
    return RouteEvidence(
        seat_id=seat.seat_id,
        logical_lineage=seat.logical_lineage,
        requested_provider=provider,
        requested_model=model,
        served_provider=provider,
        served_model=model,
        success=True,
        synthetic=False,
        observed_at=NOW - timedelta(minutes=1),
        expires_at=NOW + timedelta(hours=1),
        verifier_id=ACCEPTED_ROUTE_VERIFIER_ID,
        verifier_version=ACCEPTED_ROUTE_VERIFIER_VERSION,
        verifier_accepted=True,
        receipt_ref=receipt_ref or f"receipt://helm/{seat.seat_id}",
        receipt_sha256=f"{index + 1:064x}",
        runtime_epoch=EPOCH,
    )


def _raw_row(evidence: RouteEvidence) -> dict[str, object]:
    row = asdict(evidence)
    for field in ("observed_at", "expires_at"):
        value = row[field]
        assert isinstance(value, datetime)
        row[field] = value.isoformat().replace("+00:00", "Z")
    return row


def test_default_run_is_honest_ordered_zero_of_seven(matrix) -> None:
    report = matrix.build_report(
        evidences=(),
        blocker_map=None,
        now=NOW,
        runtime_epoch=EPOCH,
    )

    rows = report["route_verifications"]
    assert len(rows) == 7
    assert [row["seat_id"] for row in rows] == [seat.seat_id for seat in HELM_SLICE1_SEATS]
    assert {row["verdict"] for row in rows} == {"UNKNOWN"}
    assert {row["reason"] for row in rows} == {"missing_evidence"}
    assert report["on_call_count"] == 0
    assert report["total"] == 7
    assert len(report["blockers"]) == 7
    assert {item["blocker"] for item in report["blockers"]} == {"identity_unproven"}


def test_raw_evidence_is_evaluated_in_one_epoch(matrix) -> None:
    report = matrix.build_report(
        evidences=tuple(_evidence(index) for index in range(7)),
        blocker_map=None,
        now=NOW,
        runtime_epoch=EPOCH,
    )

    assert report["on_call_count"] == 7
    assert [row["verdict"] for row in report["route_verifications"]] == ["ON_CALL"] * 7
    assert report["blockers"] == []
    assert {row["runtime_epoch"] for row in report["route_verifications"]} == {EPOCH}


def test_forged_serialized_positive_verdict_is_rejected(matrix, tmp_path: Path) -> None:
    forged = {
        "schema_version": "dharma.helm.route_verification.v1",
        "seat_id": HELM_SLICE1_SEATS[0].seat_id,
        "display_label": HELM_SLICE1_SEATS[0].display_label,
        "logical_lineage": HELM_SLICE1_SEATS[0].logical_lineage,
        "verdict": "ON_CALL",
        "reason": "verified",
        "evaluated_at": "2026-09-02T04:00:00Z",
        "runtime_epoch": EPOCH,
        "evidence": None,
    }
    path = tmp_path / "forged.json"
    path.write_text(json.dumps([forged]), encoding="utf-8")

    with pytest.raises(matrix.MatrixInputError, match="raw RouteEvidence"):
        matrix.load_evidence(path)


@pytest.mark.parametrize(
    "mutation",
    [
        lambda blockers: blockers.pop(HELM_SLICE1_SEATS[-1].seat_id),
        lambda blockers: blockers.__setitem__(HELM_SLICE1_SEATS[0].seat_id, "network_error"),
    ],
)
def test_incomplete_or_open_vocabulary_blocker_map_is_rejected(matrix, mutation) -> None:
    blockers = {seat.seat_id: "identity_unproven" for seat in HELM_SLICE1_SEATS}
    mutation(blockers)

    with pytest.raises(matrix.MatrixInputError):
        matrix.validate_blocker_map(blockers)


def test_duplicate_receipt_fails_closed_without_aborting_honest_run(matrix) -> None:
    evidences = [_evidence(index) for index in range(7)]
    duplicate_ref = "receipt://helm/reused"
    evidences[0] = _evidence(0, receipt_ref=duplicate_ref)
    evidences[1] = _evidence(1, receipt_ref=duplicate_ref)

    report = matrix.build_report(
        evidences=tuple(evidences),
        blocker_map=None,
        now=NOW,
        runtime_epoch=EPOCH,
    )

    rows = report["route_verifications"]
    assert [row["reason"] for row in rows[:2]] == ["receipt_duplicated"] * 2
    assert [row["verdict"] for row in rows[:2]] == ["REJECTED"] * 2
    assert report["on_call_count"] == 5
    assert [item["seat_id"] for item in report["blockers"]] == [
        HELM_SLICE1_SEATS[0].seat_id,
        HELM_SLICE1_SEATS[1].seat_id,
    ]


def test_cli_requires_runtime_artifact_beneath_dharma(matrix, tmp_path: Path, monkeypatch) -> None:
    fake_home = tmp_path / "home"
    safe_output = fake_home / ".dharma" / "campaign" / "seat-matrix.json"
    unsafe_output = tmp_path / "inside-repo.json"
    monkeypatch.setattr(matrix.Path, "home", classmethod(lambda cls: fake_home))

    assert matrix.main(["--output", str(unsafe_output), "--runtime-epoch", EPOCH]) == 2
    assert not unsafe_output.exists()
    assert matrix.main(["--output", str(safe_output), "--runtime-epoch", EPOCH]) == 0
    payload = json.loads(safe_output.read_text(encoding="utf-8"))
    assert len(payload["route_verifications"]) == 7


def test_strict_raw_evidence_loader_accepts_only_a_json_array(matrix, tmp_path: Path) -> None:
    valid = tmp_path / "valid.json"
    valid.write_text(json.dumps([_raw_row(_evidence(0))]), encoding="utf-8")
    assert matrix.load_evidence(valid) == (_evidence(0),)

    invalid = tmp_path / "object.json"
    invalid.write_text(json.dumps({"evidence": [_raw_row(_evidence(0))]}), encoding="utf-8")
    with pytest.raises(matrix.MatrixInputError, match="JSON array"):
        matrix.load_evidence(invalid)
