"""Receipt-shaped A2A message validation.

This module is a thin gate for file-inbox and NATS adapters. It does not own
truth; it only rejects unstructured messages before they enter A2A handling.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dharma_swarm.daemon_config import dharma_state_dir

RECEIPT_SCHEMA = "dharma_a2a_task_receipt.v1"
BOUNCE_SCHEMA = "dharma_a2a_task_receipt_bounce.v1"
VALID_VERDICTS = {"verified", "refuted", "unknown"}


@dataclass(frozen=True)
class ReceiptValidation:
    valid: bool
    errors: list[str]


@dataclass(frozen=True)
class InboxReceipt:
    path: Path
    payload: dict[str, Any]
    schema_version: str = RECEIPT_SCHEMA


def validate_task_receipt(payload: dict[str, Any]) -> ReceiptValidation:
    """Validate the operator-facing receipt shape.

    Required fields are intentionally plain:
    claim, evidence, verdict, next_action, files_changed.
    """
    errors: list[str] = []
    if payload.get("schema") != RECEIPT_SCHEMA:
        errors.append(f"schema must be {RECEIPT_SCHEMA}")
    for key in ("claim", "next_action"):
        if not isinstance(payload.get(key), str) or not payload.get(key, "").strip():
            errors.append(f"{key} must be a non-empty string")
    verdict = payload.get("verdict")
    if verdict not in VALID_VERDICTS:
        errors.append(f"verdict must be one of {sorted(VALID_VERDICTS)}")
    evidence = payload.get("evidence")
    if not isinstance(evidence, list) or not evidence:
        errors.append("evidence must be a non-empty list")
    else:
        for index, item in enumerate(evidence):
            if not isinstance(item, dict):
                errors.append(f"evidence[{index}] must be an object")
                continue
            if item.get("kind") not in {"command", "path"}:
                errors.append(f"evidence[{index}].kind must be command or path")
            if not isinstance(item.get("value"), str) or not item.get("value", "").strip():
                errors.append(f"evidence[{index}].value must be a non-empty string")
    files_changed = payload.get("files_changed")
    if not isinstance(files_changed, list):
        errors.append("files_changed must be a list")
    elif not all(isinstance(item, str) for item in files_changed):
        errors.append("files_changed entries must be strings")
    return ReceiptValidation(valid=not errors, errors=errors)


def bounce_payload(errors: list[str]) -> dict[str, Any]:
    """Return the standard bounce payload for non-receipt essays."""
    return {
        "schema": BOUNCE_SCHEMA,
        "verdict": "refuted",
        "message": "receipt or it didn't happen.",
        "errors": errors,
        "next_action": (
            "Resubmit as dharma_a2a_task_receipt.v1 with claim, evidence, "
            "verdict, next_action, and files_changed."
        ),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }


def default_quarantine_dir() -> Path:
    return dharma_state_dir("DHARMA_HOME") / "a2a_bus" / "quarantine"


def validate_or_quarantine_file(
    path: Path,
    *,
    quarantine_dir: Path | None = None,
) -> ReceiptValidation:
    """Validate a JSON inbox file and copy invalid payloads to quarantine.

    The source file is left untouched; adapters can decide whether to delete or
    move it after their own acknowledgement semantics.
    """
    qdir = quarantine_dir or default_quarantine_dir()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        validation = ReceiptValidation(False, [f"invalid json: {type(exc).__name__}: {exc}"])
        _write_quarantine(path, {"raw_path": str(path)}, validation, qdir)
        return validation
    if not isinstance(payload, dict):
        validation = ReceiptValidation(False, ["payload must be a JSON object"])
        _write_quarantine(path, {"payload": payload}, validation, qdir)
        return validation
    validation = validate_task_receipt(payload)
    if not validation.valid:
        _write_quarantine(path, payload, validation, qdir)
    return validation


def read_receipted_inbox(
    inbox_dir: Path,
    *,
    quarantine_dir: Path | None = None,
) -> list[InboxReceipt]:
    """Return receipt-shaped inbox messages and quarantine everything else."""
    if not inbox_dir.is_dir():
        return []

    receipts: list[InboxReceipt] = []
    qdir = quarantine_dir or default_quarantine_dir()
    for path in sorted(inbox_dir.glob("*.json")):
        validation = validate_or_quarantine_file(path, quarantine_dir=qdir)
        if not validation.valid:
            continue
        payload = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(payload, dict):
            receipts.append(InboxReceipt(path=path, payload=payload))
    return receipts


def _write_quarantine(
    source: Path,
    payload: dict[str, Any],
    validation: ReceiptValidation,
    quarantine_dir: Path,
) -> None:
    quarantine_dir.mkdir(parents=True, exist_ok=True)
    stem = source.stem or "message"
    suffix = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    record = {
        "schema": "dharma_a2a_quarantine_record.v1",
        "source_path": str(source),
        "payload": payload,
        "validation_errors": validation.errors,
        "bounce": bounce_payload(validation.errors),
    }
    out = quarantine_dir / f"{stem}.{suffix}.quarantine.json"
    out.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
