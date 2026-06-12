from __future__ import annotations

import json
from pathlib import Path

from scripts.runtime import a2a_prod_readiness_quorum


def _write_record(
    root: Path,
    name: str,
    *,
    agent_id: str,
    model_family: str,
    role: str,
    readiness_percent: float,
    red_blockers: list[str] | None = None,
    evidence_refs: list[str] | None = None,
) -> None:
    evidence_path = root / "evidence" / "receipt.json"
    evidence_path.parent.mkdir(parents=True, exist_ok=True)
    evidence_path.write_text(json.dumps({"status": "ok"}), encoding="utf-8")
    payload = {
        "schema_version": "dharma.a2a.prod_readiness_reviewer.v1",
        "agent_id": agent_id,
        "model_family": model_family,
        "role": role,
        "readiness_percent": readiness_percent,
        "verdict": "ready",
        "red_blockers": red_blockers or [],
        "evidence_refs": evidence_refs
        if evidence_refs is not None
        else [str(evidence_path)],
        "created_at": "2026-06-13T00:00:00+00:00",
    }
    root.mkdir(parents=True, exist_ok=True)
    (root / name).write_text(json.dumps(payload), encoding="utf-8")


def test_ready_quorum_requires_two_agents_three_models_and_median_80(tmp_path: Path) -> None:
    records = tmp_path / "2026-06-13"
    _write_record(
        records,
        "codex_openai.json",
        agent_id="codex_composer",
        model_family="openai",
        role="ops_verifier",
        readiness_percent=84,
    )
    _write_record(
        records,
        "fable_anthropic.json",
        agent_id="fable_composer",
        model_family="anthropic",
        role="adversarial_security_reviewer",
        readiness_percent=82,
    )
    _write_record(
        records,
        "hermes_gemini.json",
        agent_id="hermes_m5",
        model_family="gemini",
        role="agent_harness_reviewer",
        readiness_percent=86,
    )

    aggregate = a2a_prod_readiness_quorum.aggregate_quorum(records)

    assert aggregate["status"] == "READY"
    assert aggregate["agent_ids"] == ["codex_composer", "fable_composer", "hermes_m5"]
    assert aggregate["model_families"] == ["anthropic", "gemini", "openai"]
    assert aggregate["readiness_percent_median"] == 84.0


def test_red_blocker_prevents_ready_status(tmp_path: Path) -> None:
    records = tmp_path / "2026-06-13"
    _write_record(
        records,
        "codex_openai.json",
        agent_id="codex_composer",
        model_family="openai",
        role="ops_verifier",
        readiness_percent=90,
    )
    _write_record(
        records,
        "fable_anthropic.json",
        agent_id="fable_composer",
        model_family="anthropic",
        role="adversarial_security_reviewer",
        readiness_percent=90,
        red_blockers=["unbounded retention"],
    )
    _write_record(
        records,
        "hermes_gemini.json",
        agent_id="hermes_m5",
        model_family="gemini",
        role="agent_harness_reviewer",
        readiness_percent=90,
    )

    aggregate = a2a_prod_readiness_quorum.aggregate_quorum(records)

    assert aggregate["status"] == "NOT_READY"
    assert "zero red blockers" in aggregate["missing_requirements"]
    assert aggregate["red_blocker_records"] == ["fable_composer"]


def test_insufficient_model_diversity_is_not_ready(tmp_path: Path) -> None:
    records = tmp_path / "2026-06-13"
    _write_record(
        records,
        "codex_openai.json",
        agent_id="codex_composer",
        model_family="openai",
        role="ops_verifier",
        readiness_percent=90,
    )
    _write_record(
        records,
        "fable_anthropic.json",
        agent_id="fable_composer",
        model_family="anthropic",
        role="adversarial_security_reviewer",
        readiness_percent=90,
    )

    aggregate = a2a_prod_readiness_quorum.aggregate_quorum(records)

    assert aggregate["status"] == "NOT_READY"
    assert "at least three model families" in aggregate["missing_requirements"]


def test_empty_evidence_refs_are_schema_errors(tmp_path: Path) -> None:
    records = tmp_path / "2026-06-13"
    _write_record(
        records,
        "codex_openai.json",
        agent_id="codex_composer",
        model_family="openai",
        role="ops_verifier",
        readiness_percent=90,
        evidence_refs=[],
    )

    aggregate = a2a_prod_readiness_quorum.aggregate_quorum(records)

    assert aggregate["status"] == "NOT_READY"
    assert "valid reviewer record schema" in aggregate["missing_requirements"]
    assert any("evidence_refs must be a non-empty list" in error for error in aggregate["errors"])


def test_missing_evidence_ref_is_schema_error(tmp_path: Path) -> None:
    records = tmp_path / "2026-06-13"
    _write_record(
        records,
        "codex_openai.json",
        agent_id="codex_composer",
        model_family="openai",
        role="ops_verifier",
        readiness_percent=90,
        evidence_refs=["missing/receipt.json"],
    )

    aggregate = a2a_prod_readiness_quorum.aggregate_quorum(records)

    assert aggregate["status"] == "NOT_READY"
    assert "valid reviewer record schema" in aggregate["missing_requirements"]
    assert any("evidence_ref does not exist" in error for error in aggregate["errors"])


def test_url_evidence_ref_is_schema_error(tmp_path: Path) -> None:
    records = tmp_path / "2026-06-13"
    _write_record(
        records,
        "codex_openai.json",
        agent_id="codex_composer",
        model_family="openai",
        role="ops_verifier",
        readiness_percent=90,
        evidence_refs=["https://example.invalid/receipt.json"],
    )

    aggregate = a2a_prod_readiness_quorum.aggregate_quorum(records)

    assert aggregate["status"] == "NOT_READY"
    assert "valid reviewer record schema" in aggregate["missing_requirements"]
    assert any("local path, not URL" in error for error in aggregate["errors"])


def test_solicitation_receipts_are_not_loaded_as_reviewer_records(tmp_path: Path) -> None:
    records = tmp_path / "2026-06-13"
    _write_record(
        records,
        "codex_openai.json",
        agent_id="codex_composer",
        model_family="openai",
        role="ops_verifier",
        readiness_percent=84,
    )
    records.mkdir(parents=True, exist_ok=True)
    (records / "SOLICITATION_RECEIPT.json").write_text(
        json.dumps(
            {"schema_version": "dharma.a2a.prod_readiness_solicitation_receipt.v1"}
        ),
        encoding="utf-8",
    )
    (records / "FABLE_COMPOSER_SOLICITATION_NATS_SEND.json").write_text(
        json.dumps(
            {"schema_version": "dharma.a2a.prod_readiness_solicitation_send_receipt.v1"}
        ),
        encoding="utf-8",
    )

    aggregate = a2a_prod_readiness_quorum.aggregate_quorum(records)

    assert aggregate["reviewer_count"] == 1
    assert not aggregate["errors"]


def test_delivery_status_receipt_is_not_loaded_as_reviewer_record(tmp_path: Path) -> None:
    records = tmp_path / "2026-06-13"
    _write_record(
        records,
        "codex_openai.json",
        agent_id="codex_composer",
        model_family="openai",
        role="ops_verifier",
        readiness_percent=84,
    )
    records.mkdir(parents=True, exist_ok=True)
    (records / "QUORUM_DELIVERY_STATUS.json").write_text(
        json.dumps(
            {
                "schema_version": "dharma.a2a.prod_readiness_delivery_status.v1",
                "status": "PENDING_REVIEWER_RECORDS",
                "targets": [],
            }
        ),
        encoding="utf-8",
    )

    aggregate = a2a_prod_readiness_quorum.aggregate_quorum(records)

    assert aggregate["reviewer_count"] == 1
    assert aggregate["reviewers"][0]["agent_id"] == "codex_composer"
    assert not aggregate["errors"]


def test_blocker_status_receipt_is_not_loaded_as_reviewer_record(tmp_path: Path) -> None:
    records = tmp_path / "2026-06-13"
    _write_record(
        records,
        "codex_openai.json",
        agent_id="codex_composer",
        model_family="openai",
        role="ops_verifier",
        readiness_percent=84,
    )
    records.mkdir(parents=True, exist_ok=True)
    (records / "QUORUM_BLOCKER_STATUS.json").write_text(
        json.dumps(
            {
                "schema_version": "dharma.a2a.quorum_blocker_status.v1",
                "status": "BLOCKED_BY_CURRENT_EVIDENCE",
                "reviewer_records": [],
            }
        ),
        encoding="utf-8",
    )

    aggregate = a2a_prod_readiness_quorum.aggregate_quorum(records)

    assert aggregate["reviewer_count"] == 1
    assert aggregate["reviewers"][0]["agent_id"] == "codex_composer"
    assert not aggregate["errors"]


def test_route_health_receipt_is_not_loaded_as_reviewer_record(tmp_path: Path) -> None:
    records = tmp_path / "2026-06-13"
    _write_record(
        records,
        "codex_openai.json",
        agent_id="codex_composer",
        model_family="openai",
        role="ops_verifier",
        readiness_percent=84,
    )
    records.mkdir(parents=True, exist_ok=True)
    (records / "REVIEWER_ROUTE_HEALTH.json").write_text(
        json.dumps(
            {
                "schema_version": "dharma.a2a.reviewer_route_health.v1",
                "status": "ROUTE_HEALTH_BLOCKED",
                "routes": [],
            }
        ),
        encoding="utf-8",
    )

    aggregate = a2a_prod_readiness_quorum.aggregate_quorum(records)

    assert aggregate["reviewer_count"] == 1
    assert aggregate["reviewers"][0]["agent_id"] == "codex_composer"
    assert not aggregate["errors"]
