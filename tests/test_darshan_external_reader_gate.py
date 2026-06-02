from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from dharma_swarm.chetana import staging as chetana_staging
from dharma_swarm.venture_cell.darshan.bundle import (
    create_bundle,
    validate_bundle,
    validate_bundle_for_done,
)
from dharma_swarm.venture_cell.darshan.external_reader_gate import (
    stage_accepted_external_reader_events,
    validate_external_reader_gate,
)
from dharma_swarm.venture_cell.darshan.schema import (
    DecisionDelta,
    ExternalReaderEvent,
    GoEvidenceReceiptRef,
)
from dharma_swarm.operator_core.control_surface_go import (
    _darshan_external_reader_gate_rows,
)


OBSERVED_AT = "2026-06-02T00:00:00Z"


def _bundle(tmp_path: Path, artifact_id: str = "darshan-artifact-001") -> Path:
    return create_bundle(
        title="External Reader Gate Fixture",
        root=tmp_path / "artifacts",
        artifact_id=artifact_id,
        overwrite=True,
    )


def _receipt(
    path: Path,
    *,
    artifact_id: str = "darshan-artifact-001",
    event_type: str = "reply",
    source: str = "darshan_external_reader",
    status: str = "accepted",
    rejected_reason: str = "",
    source_url: str = "fixture://darshan/external-reader/reply-001",
    privacy_redacted: bool = True,
    human_approved_contact: bool = True,
) -> Path:
    payload: dict[str, Any] = {
        "artifact_id": artifact_id,
        "event_type": event_type,
        "reader_label": "external_reader_001",
        "contact_surface": "email",
        "summary": "Reader replied with substantive inspection.",
        "human_approved_contact": human_approved_contact,
        "privacy_redacted": privacy_redacted,
        "consent_public": False,
    }
    raw = {
        "receipt_id": f"goev_{event_type}_001",
        "correlation_id": "darshan-artifact-001",
        "source": source,
        "source_url": source_url,
        "observed_at": OBSERVED_AT,
        "content_hash": f"sha256:{event_type}",
        "event_uid": f"evt_{event_type}_001",
        "schema_version": "go_evidence_receipt.v0",
        "status": status,
        "payload": payload,
    }
    if rejected_reason:
        raw["rejected_reason"] = rejected_reason
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(raw, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _attach_event(
    bundle_path: Path,
    receipt_path: Path | str,
    *,
    artifact_id: str = "darshan-artifact-001",
    event_type: str = "reply",
    receipt_id: str | None = None,
) -> None:
    decision_path = bundle_path / "decision_delta.json"
    decision = DecisionDelta.model_validate(json.loads(decision_path.read_text()))
    event = ExternalReaderEvent(
        artifact_id=artifact_id,
        event_type=event_type,
        reader_label="external_reader_001",
        contact_surface="email",
        summary="Reader replied with substantive inspection.",
        human_approved_contact=True,
        go_receipt=GoEvidenceReceiptRef(
            receipt_path=str(receipt_path),
            receipt_id=receipt_id if receipt_id is not None else f"goev_{event_type}_001",
            source="darshan_external_reader",
            source_url="fixture://darshan/external-reader/reply-001",
            observed_at=OBSERVED_AT,
            content_hash=f"sha256:{event_type}",
            event_uid=f"evt_{event_type}_001",
            status="accepted",
        ),
    )
    updated = decision.model_copy(update={"external_reader_events": [event]})
    decision_path.write_text(
        json.dumps(updated.model_dump(mode="json"), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def test_draft_bundle_valid_but_done_gate_fails_without_reader(tmp_path: Path) -> None:
    bundle = _bundle(tmp_path)

    draft = validate_bundle(bundle)
    done = validate_bundle_for_done(bundle)
    gate = validate_external_reader_gate(bundle)

    assert draft.valid is True
    assert done.valid is False
    assert gate.pass_gate is False
    assert "external_reader_event_missing" in gate.errors


def test_url_only_without_go_receipt_fails_done_gate(tmp_path: Path) -> None:
    bundle = _bundle(tmp_path)
    _attach_event(bundle, "")

    gate = validate_external_reader_gate(bundle)

    assert gate.pass_gate is False
    assert any(error.startswith("go_receipt_missing") for error in gate.errors)


def test_missing_go_receipt_file_fails_done_gate(tmp_path: Path) -> None:
    bundle = _bundle(tmp_path)
    _attach_event(bundle, bundle / "receipts" / "missing.json")

    gate = validate_external_reader_gate(bundle)

    assert gate.pass_gate is False
    assert gate.missing_receipts == [str(bundle / "receipts" / "missing.json")]
    assert any(error.startswith("go_receipt_missing") for error in gate.errors)


def test_rejected_go_receipt_fails_with_reason(tmp_path: Path) -> None:
    bundle = _bundle(tmp_path)
    receipt = _receipt(
        bundle / "receipts" / "reader.json",
        status="rejected",
        rejected_reason="redaction_missing",
    )
    _attach_event(bundle, receipt)

    gate = validate_external_reader_gate(bundle)

    assert gate.pass_gate is False
    assert gate.rejected_receipts == ["goev_reply_001"]
    assert any("redaction_missing" in error for error in gate.errors)


def test_wrong_source_go_receipt_fails(tmp_path: Path) -> None:
    bundle = _bundle(tmp_path)
    receipt = _receipt(bundle / "receipts" / "reader.json", source="world_signal")
    _attach_event(bundle, receipt)

    gate = validate_external_reader_gate(bundle)

    assert gate.pass_gate is False
    assert any(error.startswith("wrong_go_receipt_source") for error in gate.errors)


def test_artifact_mismatch_go_receipt_fails(tmp_path: Path) -> None:
    bundle = _bundle(tmp_path)
    receipt = _receipt(bundle / "receipts" / "reader.json", artifact_id="wrong-artifact")
    _attach_event(bundle, receipt)

    gate = validate_external_reader_gate(bundle)

    assert gate.pass_gate is False
    assert any(error.startswith("artifact_id_mismatch") for error in gate.errors)


def test_contact_attempt_is_not_countable(tmp_path: Path) -> None:
    bundle = _bundle(tmp_path)
    receipt = _receipt(
        bundle / "receipts" / "reader.json",
        event_type="contact_attempt",
    )
    _attach_event(bundle, receipt, event_type="contact_attempt")

    gate = validate_external_reader_gate(bundle)

    assert gate.pass_gate is False
    assert gate.countable_events == 0
    assert any("contact_attempt_not_countable" in warning for warning in gate.warnings)


def test_accepted_countable_go_receipt_passes_done_gate(tmp_path: Path) -> None:
    bundle = _bundle(tmp_path)
    receipt = _receipt(bundle / "receipts" / "reader.json")
    _attach_event(bundle, receipt)

    gate = validate_external_reader_gate(bundle)
    done = validate_bundle_for_done(bundle)

    assert gate.pass_gate is True
    assert gate.countable_events == 1
    assert gate.accepted_receipts == ["goev_reply_001"]
    assert done.valid is True


def test_control_surface_projects_external_reader_gate(tmp_path: Path) -> None:
    bundle = _bundle(tmp_path)
    receipt = _receipt(bundle / "receipts" / "reader.json")
    _attach_event(bundle, receipt)

    rows = _darshan_external_reader_gate_rows(bundle)
    row = rows[0]

    assert row.id == "darshan.external_reader_go_receipts"
    assert row.kind == "venture_cell_gate"
    assert row.observed_state == "external reader accepted"
    assert row.coherence_state == "bound"
    assert row.raw["accepted_receipts"] == ["goev_reply_001"]


def test_passing_gate_stages_chetana_receipt_atom(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(chetana_staging, "STAGING_ROOT", tmp_path / "staging")
    monkeypatch.setattr(chetana_staging, "WIKI_ROOT", tmp_path / "wiki")
    monkeypatch.setattr(chetana_staging, "TRUSTED_DEFAULT", tmp_path / "wiki" / "concepts")

    bundle = _bundle(tmp_path)
    receipt = _receipt(bundle / "receipts" / "reader.json")
    _attach_event(bundle, receipt)
    gate = validate_external_reader_gate(bundle)

    staged = stage_accepted_external_reader_events(bundle, result=gate)

    assert len(staged) == 1
    text = staged[0].read_text(encoding="utf-8")
    assert "Darshan external reader event: darshan-artifact-001" in text
    assert "go-receipt" in text
    assert str(receipt) in text
