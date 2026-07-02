#!/usr/bin/env python3
"""Adapt verified SAB semantic terminal receipts into A2A task receipts.

This script is deliberately narrow.  It does not close open work and it does
not treat arbitrary external artifacts as A2A truth.  It only normalizes rows
that are already terminal, still unverified by the A2A strict gate, and point
at a validated ``sab.semantic_receipt.v1`` JSON artifact.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import tempfile
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from dharma_swarm.operator_core.a2a_task_lifecycle import (  # noqa: E402
    VALID_CLOSE_STATUSES,
    build_task_receipt,
    queue_path,
    task_lifecycle_state,
    validate_task_receipt,
)
from scripts.governance.check_a2a_readiness import evaluate_a2a_readiness  # noqa: E402

SAB_SEMANTIC_SCHEMA = "sab.semantic_receipt.v1"
A2A_RECEIPT_SCHEMA = "dharma_a2a_task_receipt.v1"


@dataclass(frozen=True)
class SemanticAdaptAction:
    row_index: int
    task_id: str
    terminal_status: str
    agent_uid: str
    source_receipt_id: str
    source_receipt_path: str
    resolved_source_receipt_path: str
    a2a_receipt_id: str
    validation: dict[str, Any]
    reason: str


@dataclass(frozen=True)
class SemanticAdaptSkip:
    row_index: int
    task_id: str
    reason: str
    detail: str


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_timestamp(value: str) -> str:
    return (
        value.replace("+00:00", "Z")
        .replace(":", "")
        .replace("-", "")
        .replace(".", "")
    )


def _read_rows(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        stripped = line.strip()
        if not stripped:
            continue
        try:
            row = json.loads(stripped)
        except json.JSONDecodeError as exc:
            raise ValueError(f"{path}:{line_number}: invalid JSON: {exc}") from exc
        if not isinstance(row, dict):
            raise ValueError(f"{path}:{line_number}: queue row must be an object")
        rows.append(row)
    return rows


def _write_rows(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = "\n".join(json.dumps(row, ensure_ascii=True, sort_keys=True) for row in rows)
    if payload:
        payload += "\n"
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=str(path.parent), delete=False) as handle:
        tmp = Path(handle.name)
        handle.write(payload)
    tmp.replace(path)


def _default_artifact_roots() -> list[Path]:
    roots = [Path.cwd()]
    home_repo = Path.home() / "dharma_swarm"
    if home_repo.exists() and home_repo not in roots:
        roots.append(home_repo)
    return roots


def _resolve_pointer(path_value: str, artifact_roots: list[Path]) -> Path | None:
    candidate = Path(path_value).expanduser()
    if candidate.is_absolute():
        return candidate if candidate.exists() else None
    for root in artifact_roots:
        resolved = root / candidate
        if resolved.exists():
            return resolved
    return None


def _validate_sab_semantic_receipt(
    payload: Any,
    *,
    task_id: str,
    receipt_id: str,
) -> dict[str, Any]:
    errors: list[str] = []
    if not isinstance(payload, dict):
        return {"valid": False, "errors": ["receipt payload must be an object"]}
    if payload.get("schema") != SAB_SEMANTIC_SCHEMA:
        errors.append(f"schema must be {SAB_SEMANTIC_SCHEMA}")
    if str(payload.get("task_id") or "") != task_id:
        errors.append("task_id does not match queue row")
    payload_receipt_id = str(payload.get("receipt_id") or "")
    if receipt_id and payload_receipt_id and payload_receipt_id != receipt_id:
        errors.append("receipt_id does not match queue row")
    if not str(payload.get("agent") or payload.get("agent_id") or payload.get("agent_uid") or ""):
        errors.append("agent, agent_id, or agent_uid must be present")
    required = {
        "sab_instance_id",
        "latest_post_id_seen",
        "latest_witness_hash_seen",
        "semantic_action",
        "claim",
        "action_taken",
        "next_request",
    }
    missing = sorted(key for key in required if key not in payload)
    if missing:
        errors.append(f"missing SAB semantic receipt field(s): {', '.join(missing)}")
    evidence = payload.get("evidence")
    if not isinstance(evidence, list) or not evidence:
        errors.append("evidence must be a non-empty list")
    return {"valid": not errors, "errors": errors}


def _row_semantic_schema(row: dict[str, Any]) -> str:
    validation = row.get("receipt_validation")
    validation_schema = (
        str(validation.get("schema") or "")
        if isinstance(validation, dict)
        else ""
    )
    return str(row.get("required_receipt_schema") or validation_schema or "")


def _semantic_agent(payload: dict[str, Any]) -> str:
    return str(payload.get("agent_uid") or payload.get("agent_id") or payload.get("agent") or "")


def _row_agent(row: dict[str, Any], payload: dict[str, Any]) -> str:
    return str(
        row.get("closed_by")
        or row.get("completed_by")
        or row.get("blocked_by")
        or row.get("failed_by")
        or row.get("claimed_by")
        or _semantic_agent(payload)
        or ""
    )


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _build_a2a_receipt(
    row: dict[str, Any],
    payload: dict[str, Any],
    *,
    agent_uid: str,
    status: str,
    resolved_path: Path,
    timestamp: str,
) -> dict[str, Any]:
    task_id = str(row.get("id") or "")
    source_receipt_id = str(payload.get("receipt_id") or row.get("receipt_id") or "")
    evidence_list = payload.get("evidence") if isinstance(payload.get("evidence"), list) else []
    semantic_action = str(payload.get("semantic_action") or "")
    claim = str(payload.get("claim") or "")
    summary_subject = semantic_action or "semantic receipt"
    summary = f"Adapted validated SAB {summary_subject} receipt into A2A terminal receipt."
    if claim:
        summary = f"{summary} Claim: {claim[:240]}"
    status_for_receipt = status  # already validated by caller
    return build_task_receipt(
        task_id=task_id,
        agent_uid=agent_uid,
        status=status_for_receipt,  # type: ignore[arg-type]
        summary=summary,
        artifacts=[str(resolved_path)],
        authority="semantic_receipt_adapter",
        completion_via="a2a_adapt_semantic_receipts",
        evidence={
            "source_schema": SAB_SEMANTIC_SCHEMA,
            "source_receipt_id": source_receipt_id,
            "source_receipt_path": str(resolved_path),
            "semantic_action": semantic_action,
            "semantic_claim": claim,
            "semantic_evidence_count": len(evidence_list),
            "semantic_validation": {"valid": True, "errors": []},
            "adapter_reason": "terminal row had validated SAB semantic receipt but no embedded A2A receipt",
        },
        evaluation={
            "overall_verdict": "semantic_receipt_validated_and_adapted",
            "criteria_results": [
                {"criterion": "source_semantic_receipt_valid", "passed": True},
                {"criterion": "source_artifact_exists", "passed": True},
                {"criterion": "terminal_queue_row_only", "passed": True},
            ],
            "gate_results": [],
        },
        timestamp=timestamp,
    )


def _candidate_for_row(
    row: dict[str, Any],
    *,
    row_index: int,
    artifact_roots: list[Path],
    timestamp: str,
) -> tuple[SemanticAdaptAction | None, SemanticAdaptSkip | None, dict[str, Any] | None]:
    task_id = str(row.get("id") or "")
    lifecycle = task_lifecycle_state(row)
    if not lifecycle.get("closed") or lifecycle.get("verified"):
        return None, None, None

    status = str(row.get("status") or "").lower()
    if status not in VALID_CLOSE_STATUSES:
        return None, SemanticAdaptSkip(row_index, task_id, "unsupported_terminal_status", status), None
    if isinstance(row.get("receipt"), dict):
        return None, SemanticAdaptSkip(row_index, task_id, "embedded_a2a_receipt_invalid", "manual repair required"), None
    if _row_semantic_schema(row) != SAB_SEMANTIC_SCHEMA:
        return None, None, None

    pointer = str(row.get("receipt_path") or "")
    if not pointer:
        return None, SemanticAdaptSkip(row_index, task_id, "missing_receipt_path", ""), None
    resolved = _resolve_pointer(pointer, artifact_roots)
    if resolved is None:
        return None, SemanticAdaptSkip(row_index, task_id, "receipt_path_missing", pointer), None

    try:
        payload = _load_json(resolved)
    except (OSError, json.JSONDecodeError) as exc:
        return None, SemanticAdaptSkip(row_index, task_id, "receipt_json_unreadable", str(exc)), None
    source_receipt_id = str(row.get("receipt_id") or payload.get("receipt_id") or "")
    semantic_validation = _validate_sab_semantic_receipt(
        payload,
        task_id=task_id,
        receipt_id=source_receipt_id,
    )
    if not semantic_validation["valid"]:
        return (
            None,
            SemanticAdaptSkip(
                row_index,
                task_id,
                "semantic_receipt_invalid",
                "; ".join(semantic_validation["errors"]),
            ),
            None,
        )

    agent_uid = _row_agent(row, payload)
    semantic_agent = _semantic_agent(payload)
    if semantic_agent and agent_uid != semantic_agent:
        return (
            None,
            SemanticAdaptSkip(
                row_index,
                task_id,
                "agent_identity_mismatch",
                f"row agent {agent_uid!r} != semantic agent {semantic_agent!r}",
            ),
            None,
        )

    receipt = _build_a2a_receipt(
        row,
        payload,
        agent_uid=agent_uid,
        status=status,
        resolved_path=resolved,
        timestamp=timestamp,
    )
    validation = validate_task_receipt(
        receipt,
        task_id=task_id,
        agent_uid=agent_uid,
        status=status,  # type: ignore[arg-type]
        require_artifact_or_evidence=True,
    )
    if not validation["valid"]:
        return (
            None,
            SemanticAdaptSkip(row_index, task_id, "adapted_a2a_receipt_invalid", "; ".join(validation["errors"])),
            None,
        )
    return (
        SemanticAdaptAction(
            row_index=row_index,
            task_id=task_id,
            terminal_status=status,
            agent_uid=agent_uid,
            source_receipt_id=source_receipt_id,
            source_receipt_path=pointer,
            resolved_source_receipt_path=str(resolved),
            a2a_receipt_id=str(receipt.get("receipt_id") or ""),
            validation=validation,
            reason="validated_terminal_semantic_receipt_without_embedded_a2a_receipt",
        ),
        None,
        receipt,
    )


def find_actions(
    rows: list[dict[str, Any]],
    *,
    artifact_roots: list[Path],
    timestamp: str,
) -> tuple[list[SemanticAdaptAction], list[SemanticAdaptSkip], dict[int, dict[str, Any]]]:
    actions: list[SemanticAdaptAction] = []
    skips: list[SemanticAdaptSkip] = []
    receipts_by_index: dict[int, dict[str, Any]] = {}
    for index, row in enumerate(rows):
        action, skip, receipt = _candidate_for_row(
            row,
            row_index=index,
            artifact_roots=artifact_roots,
            timestamp=timestamp,
        )
        if action is not None and receipt is not None:
            actions.append(action)
            receipts_by_index[index] = receipt
        if skip is not None:
            skips.append(skip)
    return actions, skips, receipts_by_index


def _apply_actions(
    *,
    rows: list[dict[str, Any]],
    actions: list[SemanticAdaptAction],
    receipts_by_index: dict[int, dict[str, Any]],
    timestamp: str,
) -> list[dict[str, Any]]:
    applied: list[dict[str, Any]] = []
    actions_by_index = {action.row_index: action for action in actions}
    for index, row in enumerate(rows):
        action = actions_by_index.get(index)
        receipt = receipts_by_index.get(index)
        if action is None or receipt is None:
            continue
        validation = validate_task_receipt(
            receipt,
            task_id=action.task_id,
            agent_uid=action.agent_uid,
            status=action.terminal_status,  # type: ignore[arg-type]
            require_artifact_or_evidence=True,
        )
        row["semantic_receipt_id"] = action.source_receipt_id
        row["semantic_receipt_path"] = action.source_receipt_path
        row["semantic_receipt_validation"] = row.get("receipt_validation")
        row["a2a_adapted_at"] = timestamp
        row["a2a_adapted_via"] = "scripts/governance/a2a_adapt_semantic_receipts.py"
        row["a2a_adapted_from_schema"] = SAB_SEMANTIC_SCHEMA
        row["a2a_adapted_from_receipt_id"] = action.source_receipt_id
        row["a2a_adapted_from_receipt_path"] = action.source_receipt_path
        row["receipt"] = receipt
        row["receipt_id"] = receipt.get("receipt_id")
        row["receipt_validation"] = validation
        row["required_receipt_schema"] = A2A_RECEIPT_SCHEMA
        row["closed_by"] = row.get("closed_by") or action.agent_uid
        if action.terminal_status == "completed":
            row["completed_by"] = row.get("completed_by") or action.agent_uid
        elif action.terminal_status == "blocked":
            row["blocked_by"] = row.get("blocked_by") or action.agent_uid
        elif action.terminal_status == "failed":
            row["failed_by"] = row.get("failed_by") or action.agent_uid
        applied.append(
            {
                "task_id": action.task_id,
                "status": "adapted",
                "source_receipt_id": action.source_receipt_id,
                "a2a_receipt_id": action.a2a_receipt_id,
                "validation": validation,
            }
        )
    return applied


def build_report(
    *,
    state_root: Path | str | None = None,
    artifact_roots: list[Path] | None = None,
    apply: bool = False,
    timestamp: str | None = None,
) -> dict[str, Any]:
    ts = timestamp or _utc_now()
    roots = artifact_roots or _default_artifact_roots()
    path = queue_path(state_root)
    rows = _read_rows(path)
    actions, skips, receipts_by_index = find_actions(rows, artifact_roots=roots, timestamp=ts)
    backup_path = ""
    applied: list[dict[str, Any]] = []
    if apply and actions:
        backup_path = str(path.with_name(f"{path.name}.a2a-semantic-adapter-{_safe_timestamp(ts)}.bak"))
        shutil.copy2(path, backup_path)
        applied = _apply_actions(
            rows=rows,
            actions=actions,
            receipts_by_index=receipts_by_index,
            timestamp=ts,
        )
        _write_rows(path, rows)
    readiness = evaluate_a2a_readiness(state_root)
    return {
        "schema_version": 1,
        "mode": "apply" if apply else "dry_run",
        "generated_at": ts,
        "queue_path": str(path),
        "artifact_roots": [str(root) for root in roots],
        "backup_path": backup_path,
        "candidate_count": len(actions),
        "applied_count": len(applied),
        "skip_count": len(skips),
        "candidates": [asdict(action) for action in actions],
        "skips": [asdict(skip) for skip in skips],
        "applied": applied,
        "post_readiness": asdict(readiness),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state-root", default=None)
    parser.add_argument("--artifact-root", action="append", default=None)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--timestamp", default=None)
    parser.add_argument("--output", default=None)
    args = parser.parse_args(argv)

    artifact_roots = (
        [Path(root).expanduser() for root in args.artifact_root]
        if args.artifact_root
        else None
    )
    report = build_report(
        state_root=args.state_root,
        artifact_roots=artifact_roots,
        apply=args.apply,
        timestamp=args.timestamp,
    )
    payload = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.output:
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(payload, encoding="utf-8")
    print(payload, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
