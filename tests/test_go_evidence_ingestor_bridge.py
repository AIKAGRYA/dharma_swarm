"""Go evidence sense-organ bridge tests.

The Go sidecar only emits evidence. Python remains responsible for projecting
that evidence into closure_v0 and deciding what happens next.
"""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest

from dharma_swarm.world_radar.go_invoke import go_toolchain_capable

from dharma_swarm.operator_core.closure_v0 import (
    WorkPacket,
    decide_next,
    kaizen_link,
    load_fixture,
    project_vsm,
)
from dharma_swarm.operator_core.go_evidence_bridge import (
    closure_evidence_from_go_receipt,
    load_go_evidence_receipt,
)
from dharma_swarm.operator_core.operating_facts import OperatingFactBundle


FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures" / "organism_closure_v0"
GO_MODULE = Path(__file__).resolve().parents[1] / "tools" / "evidence_ingestor_go"
CORRELATION_ID = "corr_v0_test_001"
CREATED_AT = "2026-05-08T00:00:00+00:00"
CAPTURED_AT = "2026-05-08T00:00:01+00:00"
DECIDED_AT = "2026-05-08T00:00:02+00:00"
EXPIRES_AT = "2026-05-08T01:00:00+00:00"
GO_OBSERVED_AT = "2026-05-09T00:00:00Z"


def _load_packet() -> WorkPacket:
    raw = load_fixture("fixture_work_packet.json")
    return WorkPacket(
        packet_id=raw["packet_id"],
        correlation_id=raw["correlation_id"],
        title=raw["title"],
        allowed_paths=tuple(raw["allowed_paths"]),
        acceptance_test=raw["acceptance_test"],
        rollback_plan=raw["rollback_plan"],
        objective_id=raw["objective_id"],
        cell_id=raw["cell_id"],
        forbidden_paths=tuple(raw["forbidden_paths"]),
        review_tier=raw["review_tier"],
    )


def _empty_bundle() -> OperatingFactBundle:
    raw = load_fixture("fixture_operating_bundle.json")
    return OperatingFactBundle(missing_sources=tuple(raw["missing_sources"]))


def _run_go_ingestor(input_name: str, output_path: Path, source_url: str) -> None:
    if not go_toolchain_capable(GO_MODULE):
        pytest.skip("no Go toolchain satisfying evidence_ingestor_go/go.mod")
    env = dict(os.environ)
    env["GOCACHE"] = "/tmp/dharma-swarm-go-build"
    env["GOMODCACHE"] = "/tmp/dharma-swarm-go-mod"
    subprocess.run(
        [
            "go", "run", ".",
            "--input", str(FIXTURE_DIR / input_name),
            "--output", str(output_path),
            "--source", "agentops_fixture",
            "--source-url", source_url,
            "--correlation-id", CORRELATION_ID,
            "--observed-at", GO_OBSERVED_AT,
        ],
        cwd=GO_MODULE,
        env=env,
        check=True,
    )


def _decision_from_go_receipt(path: Path):
    packet = _load_packet()
    receipt = load_go_evidence_receipt(path)
    evidence = closure_evidence_from_go_receipt(
        packet,
        receipt,
        created_at=CREATED_AT,
        duration_ms=1234.5,
    )
    projection = project_vsm(
        _empty_bundle(),
        evidence,
        correlation_id=CORRELATION_ID,
        captured_at=CAPTURED_AT,
        recognition_seed_age_hours=2.0,
        algedonic_unique_values_last_200=5,
        kernel_signature_match=True,
    )
    review = kaizen_link(evidence)
    return decide_next(
        projection,
        [packet],
        review,
        decided_at=DECIDED_AT,
        expires_at=EXPIRES_AT,
    )


def test_go_receipts_drive_closure_v0_success_failure_diff(tmp_path: Path) -> None:
    success_path = tmp_path / "success.json"
    failure_path = tmp_path / "failure.json"

    _run_go_ingestor(
        "fixture_agentops_success.json",
        success_path,
        "fixture://agentops/success",
    )
    _run_go_ingestor(
        "fixture_agentops_failure.json",
        failure_path,
        "fixture://agentops/failure",
    )

    success_receipt = json.loads(success_path.read_text(encoding="utf-8"))
    failure_receipt = json.loads(failure_path.read_text(encoding="utf-8"))
    assert success_receipt["schema_version"] == "go_evidence_receipt.v0"
    assert success_receipt["correlation_id"] == CORRELATION_ID
    assert success_receipt["event_uid"] != failure_receipt["event_uid"]

    success_decision = _decision_from_go_receipt(success_path)
    failure_decision = _decision_from_go_receipt(failure_path)

    assert success_decision != failure_decision
    assert success_decision.chosen_packet_id == "wp_v0_test_001"
    assert failure_decision.chosen_packet_id is None
    assert success_decision.reason != failure_decision.reason
