"""Darshan external-reader gate backed by Go evidence receipts."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from pydantic import Field, ValidationError

from dharma_swarm.chetana.ingest import ingest
from dharma_swarm.operator_core.go_evidence_bridge import (
    GO_EVIDENCE_SCHEMA_V0,
    GoEvidenceBridgeError,
    GoEvidenceReceipt,
    load_go_evidence_receipt,
)
from dharma_swarm.venture_cell.darshan.bundle import default_artifact_root, validate_bundle
from dharma_swarm.venture_cell.darshan.schema import (
    DarshanBaseModel,
    DecisionDelta,
    ExternalReaderEvent,
    ExternalReaderEventType,
)


DARSHAN_READER_RECEIPT_SOURCE = "darshan_external_reader"
COUNTABLE_EVENT_TYPES = {
    ExternalReaderEventType.READ,
    ExternalReaderEventType.REPLY,
    ExternalReaderEventType.INSPECTION,
    ExternalReaderEventType.DECISION,
}
OUTREACH_SURFACES = {"email", "dm", "direct_message", "social", "linkedin", "outreach"}


class ExternalReaderGateResult(DarshanBaseModel):
    artifact_id: str = ""
    bundle_path: str = ""
    pass_gate: bool = False
    countable_events: int = 0
    checked_events: int = 0
    accepted_receipts: list[str] = Field(default_factory=list)
    rejected_receipts: list[str] = Field(default_factory=list)
    missing_receipts: list[str] = Field(default_factory=list)
    event_uids: list[str] = Field(default_factory=list)
    receipt_paths: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


def validate_external_reader_gate(bundle_path: Path) -> ExternalReaderGateResult:
    bundle_path = bundle_path.expanduser().resolve()
    bundle_result = validate_bundle(bundle_path)
    artifact_id = bundle_result.manifest.artifact_id if bundle_result.manifest else ""
    result = ExternalReaderGateResult(
        artifact_id=artifact_id,
        bundle_path=str(bundle_path),
        errors=list(bundle_result.errors),
        warnings=list(bundle_result.warnings),
    )
    if not bundle_result.valid:
        return result

    try:
        decision_delta = _load_decision_delta(bundle_path)
    except (OSError, json.JSONDecodeError, ValidationError) as exc:
        result.errors.append(f"decision_delta_invalid:{exc}")
        return result

    if not decision_delta.external_reader_events:
        result.errors.append("external_reader_event_missing")
        return result

    for event in decision_delta.external_reader_events:
        _check_event(bundle_path, decision_delta.artifact_id, event, result)

    result.pass_gate = result.countable_events > 0 and not result.errors
    if not result.pass_gate and result.countable_events == 0:
        result.warnings.append("no_countable_external_reader_event")
    return result


def validate_external_reader_gate_summary(bundle_path: Path | None = None) -> dict[str, Any]:
    selected = bundle_path or latest_darshan_bundle_path()
    if selected is None:
        return {
            "exists": False,
            "bundle_path": "",
            "artifact_id": "",
            "pass_gate": False,
            "observed_state": "no reader events",
            "coherence_state": "declared_only",
            "gap_codes": ["darshan_external_reader_event_missing"],
            "accepted_receipts": [],
            "rejected_receipts": [],
            "missing_receipts": [],
            "event_uids": [],
            "receipt_paths": [],
            "errors": ["external_reader_event_missing"],
            "warnings": [],
            "freshest_observed_at": "",
        }

    result = validate_external_reader_gate(selected)
    return _summary_from_result(result)


def latest_darshan_bundle_path(root: Path | None = None) -> Path | None:
    artifact_root = (root or default_artifact_root()).expanduser()
    if not artifact_root.exists():
        return None
    candidates = sorted(
        (path for path in artifact_root.rglob("decision_delta.json") if path.is_file()),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    return candidates[0].parent if candidates else None


def stage_accepted_external_reader_events(
    bundle_path: Path,
    *,
    result: ExternalReaderGateResult | None = None,
) -> list[Path]:
    gate = result or validate_external_reader_gate(bundle_path)
    if not gate.pass_gate:
        raise ValueError("external reader gate has not passed")

    bundle = Path(gate.bundle_path).expanduser().resolve()
    decision_delta = _load_decision_delta(bundle)
    accepted = set(gate.accepted_receipts)
    staged: list[Path] = []
    for event in decision_delta.external_reader_events:
        if event.go_receipt.receipt_id not in accepted:
            continue
        if event.event_type not in COUNTABLE_EVENT_TYPES:
            continue
        receipt_path = _resolve_receipt_path(bundle, event.go_receipt.receipt_path)
        body = _privacy_redacted_atom_body(event, receipt_path)
        ingest_result = ingest(
            source=body,
            source_kind="receipt",
            title=f"Darshan external reader event: {event.artifact_id}",
            atom_type="atomic",
            confidence=0.74,
            captured_by="dharma_swarm.venture_cell.darshan.external_reader_gate",
            tags=[
                "darshan",
                "venture-cell",
                "external-reader",
                "go-receipt",
                "contact-gate",
            ],
            related=[
                str(bundle),
                str(bundle / "decision_delta.json"),
                str(bundle / "source_pack.json"),
                str(receipt_path),
            ],
        )
        staged.extend(ingest_result.atoms)
    return staged


def _load_decision_delta(bundle_path: Path) -> DecisionDelta:
    payload = json.loads((bundle_path / "decision_delta.json").read_text(encoding="utf-8"))
    return DecisionDelta.model_validate(payload)


def _check_event(
    bundle_path: Path,
    artifact_id: str,
    event: ExternalReaderEvent,
    result: ExternalReaderGateResult,
) -> None:
    result.checked_events += 1
    if event.artifact_id != artifact_id:
        result.errors.append(f"event_artifact_id_mismatch:{event.event_id}")
        return

    if not event.go_receipt.receipt_path:
        result.errors.append(f"go_receipt_missing:{event.event_id}")
        result.missing_receipts.append(event.event_id)
        return

    receipt_path = _resolve_receipt_path(bundle_path, event.go_receipt.receipt_path)
    result.receipt_paths.append(str(receipt_path))
    if not receipt_path.exists():
        result.errors.append(f"go_receipt_missing:{event.event_id}")
        result.missing_receipts.append(str(receipt_path))
        return

    try:
        raw = json.loads(receipt_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        result.errors.append(f"go_receipt_invalid:{event.event_id}:{exc}")
        result.missing_receipts.append(str(receipt_path))
        return

    receipt_id = str(raw.get("receipt_id", ""))
    status = str(raw.get("status", ""))
    if status == "rejected":
        reason = str(raw.get("rejected_reason", ""))
        result.errors.append(f"go_receipt_rejected:{event.event_id}:{reason}")
        result.rejected_receipts.append(receipt_id or str(receipt_path))
        return

    try:
        receipt = load_go_evidence_receipt(receipt_path)
    except GoEvidenceBridgeError as exc:
        result.errors.append(f"go_receipt_invalid:{event.event_id}:{exc}")
        return

    if not _accepted_reader_receipt(receipt, artifact_id, event, result):
        return

    result.accepted_receipts.append(receipt.receipt_id)
    result.event_uids.append(receipt.event_uid)
    if event.event_type in COUNTABLE_EVENT_TYPES:
        result.countable_events += 1
    else:
        result.warnings.append(f"contact_attempt_not_countable:{event.event_id}")


def _accepted_reader_receipt(
    receipt: GoEvidenceReceipt,
    artifact_id: str,
    event: ExternalReaderEvent,
    result: ExternalReaderGateResult,
) -> bool:
    payload = receipt.payload
    ok = True
    if receipt.schema_version != GO_EVIDENCE_SCHEMA_V0:
        result.errors.append(f"go_receipt_invalid_schema:{event.event_id}")
        ok = False
    if receipt.source != DARSHAN_READER_RECEIPT_SOURCE:
        result.errors.append(f"wrong_go_receipt_source:{event.event_id}:{receipt.source}")
        ok = False
    if not receipt.source_url:
        result.errors.append(f"go_receipt_source_url_missing:{event.event_id}")
        ok = False
    if str(payload.get("artifact_id", "")) != artifact_id:
        result.errors.append(f"artifact_id_mismatch:{event.event_id}")
        ok = False
    if str(payload.get("event_type", "")) != event.event_type.value:
        result.errors.append(f"event_type_mismatch:{event.event_id}")
        ok = False
    if _requires_human_approval(event, payload) and not bool(
        payload.get("human_approved_contact", event.human_approved_contact)
    ):
        result.errors.append(f"human_approved_contact_missing:{event.event_id}")
        ok = False
    if not bool(payload.get("privacy_redacted", False)):
        result.errors.append(f"privacy_leak_risk:{event.event_id}")
        ok = False
    if _payload_contains_private_material(payload):
        result.errors.append(f"privacy_leak_risk:{event.event_id}")
        ok = False
    return ok


def _requires_human_approval(event: ExternalReaderEvent, payload: dict[str, Any]) -> bool:
    surface = str(payload.get("contact_surface") or event.contact_surface).lower()
    return surface in OUTREACH_SURFACES


def _payload_contains_private_material(payload: dict[str, Any]) -> bool:
    text = json.dumps(payload, sort_keys=True)
    return bool(
        re.search(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", text)
        or re.search(r"\b(?:\+?\d[\d .-]{7,}\d)\b", text)
        or re.search(r"\b(?:sk|pk|ghp|xoxb)-[A-Za-z0-9_-]{8,}\b", text)
    )


def _resolve_receipt_path(bundle_path: Path, value: str) -> Path:
    path = Path(value).expanduser()
    if path.is_absolute():
        return path.resolve()
    return (bundle_path / path).resolve()


def _summary_from_result(result: ExternalReaderGateResult) -> dict[str, Any]:
    observed_state = "external reader accepted"
    coherence_state = "bound"
    gaps: list[str] = []
    if not result.checked_events:
        observed_state = "no reader events"
        coherence_state = "declared_only"
        gaps.append("darshan_external_reader_event_missing")
    elif result.pass_gate:
        observed_state = "external reader accepted"
    elif result.rejected_receipts:
        observed_state = "receipt rejected"
        coherence_state = "partial"
        gaps.append("darshan_go_receipt_rejected")
    elif result.missing_receipts:
        observed_state = "receipt missing"
        coherence_state = "partial"
        gaps.append("darshan_go_receipt_missing")
    elif result.errors:
        observed_state = "receipt invalid"
        coherence_state = "partial"
        gaps.append("darshan_go_receipt_invalid")
    elif result.countable_events == 0:
        observed_state = "contact attempt only"
        coherence_state = "partial"
        gaps.append("darshan_external_reader_not_countable")
    else:
        observed_state = "receipt invalid"
        coherence_state = "partial"
        gaps.append("darshan_go_receipt_invalid")

    return {
        "exists": bool(result.bundle_path),
        "bundle_path": result.bundle_path,
        "artifact_id": result.artifact_id,
        "pass_gate": result.pass_gate,
        "observed_state": observed_state,
        "coherence_state": coherence_state,
        "gap_codes": gaps,
        "accepted_receipts": result.accepted_receipts,
        "rejected_receipts": result.rejected_receipts,
        "missing_receipts": result.missing_receipts,
        "event_uids": result.event_uids,
        "receipt_paths": result.receipt_paths,
        "errors": result.errors,
        "warnings": result.warnings,
        "freshest_observed_at": "",
    }


def _privacy_redacted_atom_body(event: ExternalReaderEvent, receipt_path: Path) -> str:
    return "\n".join(
        [
            f"# Darshan external reader event: {event.artifact_id}",
            "",
            f"- event_id: {event.event_id}",
            f"- event_type: {event.event_type.value}",
            f"- reader_label: {event.reader_label}",
            f"- contact_surface: {event.contact_surface}",
            f"- occurred_at: {event.occurred_at}",
            f"- consent_public: {event.consent_public}",
            f"- go_receipt: {receipt_path}",
            "",
            "## Privacy-redacted summary",
            "",
            event.summary or "External reader event recorded with privacy redaction.",
        ]
    )
