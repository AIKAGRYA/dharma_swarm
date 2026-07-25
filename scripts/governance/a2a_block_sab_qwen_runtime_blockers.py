#!/usr/bin/env python3
"""Block stale SAB Qwen First Spark rows with verified runtime blocker receipts."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from dharma_swarm.operator_core.a2a_task_lifecycle import (  # noqa: E402
    OPEN_STATUSES,
    build_task_receipt,
    close_task,
    queue_path,
    read_queue,
    task_lifecycle_state,
    validate_task_receipt,
)
from scripts.governance.check_a2a_readiness import evaluate_a2a_readiness  # noqa: E402

SAB_SEMANTIC_SCHEMA = "sab.semantic_receipt.v1"
DEFAULT_TASK_ID = "sab-flywheel-d01-qwen-code-first-spark"
DEFAULT_AGENT_UID = "a2a_supervisor"
DEFAULT_STALE_HOURS = 24.0
RECEIPTS_DIR = "reports/sab_first_six_agent_flywheel/receipts"


@dataclass(frozen=True)
class SourceReceipt:
    kind: str
    path: str
    task_id: str
    receipt_id: str
    claim: str


@dataclass(frozen=True)
class SabRuntimeBlockAction:
    row_index: int
    task_id: str
    age_hours: float | None
    a2a_receipt_id: str
    source_receipts: list[SourceReceipt]
    reason: str


@dataclass(frozen=True)
class SabRuntimeBlockSkip:
    row_index: int
    task_id: str
    reason: str
    detail: str


def _safe_timestamp(value: str) -> str:
    return value.replace("+00:00", "Z").replace(":", "").replace("-", "").replace(".", "")


def _parse_time(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    candidate = value.strip()
    if candidate.endswith("Z"):
        candidate = f"{candidate[:-1]}+00:00"
    try:
        parsed = datetime.fromisoformat(candidate)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _age_hours(row: dict[str, Any], now: datetime) -> float | None:
    for key in ("created", "created_at", "submitted_at", "updated_at"):
        parsed = _parse_time(row.get(key))
        if parsed is not None:
            return round(max((now - parsed).total_seconds(), 0.0) / 3600.0, 3)
    return None


def _default_artifact_roots() -> list[Path]:
    roots = [Path.cwd()]
    home_repo = Path.home() / "dharma_swarm"
    if home_repo.exists() and home_repo not in roots:
        roots.append(home_repo)
    return roots


def _resolve_existing(path_value: str, roots: list[Path]) -> Path | None:
    candidate = Path(path_value).expanduser()
    if candidate.is_absolute():
        return candidate if candidate.exists() else None
    for root in roots:
        resolved = root / candidate
        if resolved.exists():
            return resolved
    return None


def _text_blob(payload: dict[str, Any]) -> str:
    parts: list[str] = []
    for key in ("claim", "action_taken", "next_request"):
        parts.append(str(payload.get(key) or ""))
    evidence = payload.get("evidence")
    if isinstance(evidence, list):
        parts.extend(str(item) for item in evidence)
    return " ".join(parts).lower()


def _source_kind(payload: dict[str, Any], *, original_task_id: str) -> str:
    task_id = str(payload.get("task_id") or "")
    related_task_id = str(payload.get("related_task_id") or "")
    if task_id.startswith(f"{original_task_id}-runtime-blocked"):
        return "runtime_blocked"
    if task_id.startswith(f"{original_task_id}-capture-gate") or related_task_id == original_task_id:
        return "capture_gate"
    return ""


def _validate_source_receipt(
    payload: Any,
    *,
    path: Path,
    original_task_id: str,
) -> SourceReceipt | SabRuntimeBlockSkip:
    if not isinstance(payload, dict):
        return SabRuntimeBlockSkip(-1, original_task_id, "source_receipt_invalid", f"{path}: payload must be object")
    errors: list[str] = []
    if payload.get("schema") != SAB_SEMANTIC_SCHEMA:
        errors.append(f"schema must be {SAB_SEMANTIC_SCHEMA}")
    kind = _source_kind(payload, original_task_id=original_task_id)
    if not kind:
        errors.append("receipt task_id is not related to the original Qwen First Spark task")
    if str(payload.get("semantic_action") or "") != "refusal":
        errors.append("semantic_action must be refusal")
    if not str(payload.get("claim") or ""):
        errors.append("claim is required")
    if not str(payload.get("action_taken") or ""):
        errors.append("action_taken is required")
    if not str(payload.get("next_request") or ""):
        errors.append("next_request is required")
    evidence = payload.get("evidence")
    if not isinstance(evidence, list) or not evidence:
        errors.append("evidence must be a non-empty list")

    text = _text_blob(payload)
    if kind == "runtime_blocked" and not (
        "qwen" in text and ("auth" in text or "provider" in text or "api_key" in text or "oauth" in text)
    ):
        errors.append("runtime-blocked receipt must prove Qwen auth/provider/runtime unavailability")
    if kind == "capture_gate":
        gate = payload.get("qwen_first_spark_gate")
        approval_required = isinstance(gate, dict) and bool(gate.get("approval_required"))
        if not approval_required and "approval" not in text:
            errors.append("capture-gate receipt must prove approval gating")

    if errors:
        return SabRuntimeBlockSkip(-1, original_task_id, "source_receipt_invalid", f"{path}: {'; '.join(errors)}")
    return SourceReceipt(
        kind=kind,
        path=str(path),
        task_id=str(payload.get("task_id") or ""),
        receipt_id=str(payload.get("receipt_id") or f"{SAB_SEMANTIC_SCHEMA}:{Path(path).stem}"),
        claim=str(payload.get("claim") or ""),
    )


def _load_source(path: Path, *, original_task_id: str) -> SourceReceipt | SabRuntimeBlockSkip:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return SabRuntimeBlockSkip(-1, original_task_id, "source_receipt_unreadable", f"{path}: {exc}")
    return _validate_source_receipt(payload, path=path, original_task_id=original_task_id)


def _candidate_source_paths(roots: list[Path], *, task_id: str) -> list[Path]:
    patterns = (
        f"{task_id}-runtime-blocked*.semantic_receipt.json",
        f"{task_id}-capture-gate*.semantic_receipt.json",
    )
    paths: list[Path] = []
    seen: set[Path] = set()
    for root in roots:
        receipt_dir = root / RECEIPTS_DIR
        if not receipt_dir.exists():
            continue
        for pattern in patterns:
            for path in sorted(receipt_dir.glob(pattern)):
                resolved = path.resolve()
                if resolved not in seen:
                    seen.add(resolved)
                    paths.append(path)
    return paths


def _source_receipts(
    roots: list[Path],
    *,
    task_id: str,
) -> tuple[list[SourceReceipt], list[SabRuntimeBlockSkip]]:
    receipts: list[SourceReceipt] = []
    skips: list[SabRuntimeBlockSkip] = []
    for path in _candidate_source_paths(roots, task_id=task_id):
        loaded = _load_source(path, original_task_id=task_id)
        if isinstance(loaded, SourceReceipt):
            receipts.append(loaded)
        else:
            skips.append(loaded)
    return receipts, skips


def _build_receipt(
    row: dict[str, Any],
    *,
    agent_uid: str,
    source_receipts: list[SourceReceipt],
    expected_receipt_path: str,
    age_hours: float | None,
    timestamp: str,
) -> dict[str, Any]:
    task_id = str(row.get("id") or "")
    runtime_sources = [receipt for receipt in source_receipts if receipt.kind == "runtime_blocked"]
    primary = runtime_sources[0] if runtime_sources else source_receipts[0]
    source_paths = [receipt.path for receipt in source_receipts]
    return build_task_receipt(
        task_id=task_id,
        agent_uid=agent_uid,
        status="blocked",
        summary=(
            "Blocked stale SAB Qwen First Spark row because related SAB semantic "
            "refusal receipts prove the Qwen-owned lane could not produce the "
            "required target-owned receipt with the available approval/provider runtime."
        ),
        artifacts=source_paths,
        authority="sab_first_spark_runtime_block_supervisor_block",
        completion_via="a2a_block_sab_qwen_runtime_blockers",
        failure_reason="target_qwen_runtime_unavailable_without_target_owned_receipt",
        evidence={
            "age_hours": age_hours,
            "expected_receipt_path": expected_receipt_path,
            "expected_receipt_exists": False,
            "original_status": str(row.get("status") or ""),
            "original_to": str(row.get("to") or ""),
            "required_receipt_schema": str(row.get("required_receipt_schema") or ""),
            "source_receipt_count": len(source_receipts),
            "source_receipts": [asdict(receipt) for receipt in source_receipts],
            "primary_source_kind": primary.kind,
            "primary_source_claim": primary.claim,
            "supervisor_scope": "block_only_no_qwen_completion_or_post_claimed",
        },
        evaluation={
            "overall_verdict": "blocked_by_related_sab_semantic_refusal",
            "criteria_results": [
                {"criterion": "row_is_open_unclaimed", "passed": True},
                {"criterion": "required_receipt_schema_is_sab_semantic", "passed": True},
                {"criterion": "exact_expected_qwen_receipt_absent", "passed": True},
                {"criterion": "related_refusal_receipt_present", "passed": bool(source_receipts)},
                {
                    "criterion": "runtime_or_capture_gate_blocker_present",
                    "passed": any(receipt.kind in {"runtime_blocked", "capture_gate"} for receipt in source_receipts),
                },
                {"criterion": "no_completion_or_visibility_claimed", "passed": True},
            ],
            "gate_results": [],
        },
        timestamp=timestamp,
    )


def _candidate_for_row(
    row: dict[str, Any],
    *,
    row_index: int,
    task_id: str,
    agent_uid: str,
    artifact_roots: list[Path],
    stale_after_hours: float,
    now: datetime,
    timestamp: str,
) -> tuple[SabRuntimeBlockAction | None, SabRuntimeBlockSkip | None, dict[str, Any] | None]:
    row_task_id = str(row.get("id") or "")
    if row_task_id != task_id:
        return None, None, None
    lifecycle = task_lifecycle_state(row)
    if lifecycle.get("closed"):
        return None, SabRuntimeBlockSkip(row_index, row_task_id, "already_closed", str(row.get("status") or "")), None
    status = str(row.get("status") or "pending").lower()
    if status not in OPEN_STATUSES:
        return None, SabRuntimeBlockSkip(row_index, row_task_id, "not_open_unclaimed", status), None
    if str(row.get("to") or "") != "qwen_code":
        return None, SabRuntimeBlockSkip(row_index, row_task_id, "not_qwen_code_target", str(row.get("to") or "")), None
    if str(row.get("required_receipt_schema") or "") != SAB_SEMANTIC_SCHEMA:
        return (
            None,
            SabRuntimeBlockSkip(row_index, row_task_id, "wrong_required_receipt_schema", str(row.get("required_receipt_schema") or "")),
            None,
        )
    expected_receipt_path = str(row.get("expected_receipt_path") or "")
    if not expected_receipt_path:
        return None, SabRuntimeBlockSkip(row_index, row_task_id, "missing_expected_receipt_path", ""), None
    if _resolve_existing(expected_receipt_path, artifact_roots) is not None:
        return None, SabRuntimeBlockSkip(row_index, row_task_id, "exact_expected_receipt_present", expected_receipt_path), None
    age = _age_hours(row, now)
    if age is not None and age < stale_after_hours:
        return None, SabRuntimeBlockSkip(row_index, row_task_id, "not_stale", str(age)), None

    sources, source_skips = _source_receipts(artifact_roots, task_id=task_id)
    if not sources:
        detail = "; ".join(skip.detail for skip in source_skips) or "no related semantic refusal receipts found"
        return None, SabRuntimeBlockSkip(row_index, row_task_id, "no_valid_related_refusal_receipt", detail), None
    receipt = _build_receipt(
        row,
        agent_uid=agent_uid,
        source_receipts=sources,
        expected_receipt_path=expected_receipt_path,
        age_hours=age,
        timestamp=timestamp,
    )
    validation = validate_task_receipt(
        receipt,
        task_id=task_id,
        agent_uid=agent_uid,
        status="blocked",
        require_artifact_or_evidence=True,
    )
    if not validation["valid"]:
        return None, SabRuntimeBlockSkip(row_index, row_task_id, "a2a_receipt_invalid", "; ".join(validation["errors"])), None
    return (
        SabRuntimeBlockAction(
            row_index=row_index,
            task_id=task_id,
            age_hours=age,
            a2a_receipt_id=str(receipt.get("receipt_id") or ""),
            source_receipts=sources,
            reason="related_sab_semantic_refusal_receipt_proves_runtime_blocker",
        ),
        None,
        receipt,
    )


def find_actions(
    rows: list[dict[str, Any]],
    *,
    task_id: str,
    agent_uid: str,
    artifact_roots: list[Path],
    stale_after_hours: float,
    now: datetime,
    timestamp: str,
) -> tuple[list[SabRuntimeBlockAction], list[SabRuntimeBlockSkip], dict[int, dict[str, Any]]]:
    actions: list[SabRuntimeBlockAction] = []
    skips: list[SabRuntimeBlockSkip] = []
    receipts_by_index: dict[int, dict[str, Any]] = {}
    for index, row in enumerate(rows):
        action, skip, receipt = _candidate_for_row(
            row,
            row_index=index,
            task_id=task_id,
            agent_uid=agent_uid,
            artifact_roots=artifact_roots,
            stale_after_hours=stale_after_hours,
            now=now,
            timestamp=timestamp,
        )
        if action is not None and receipt is not None:
            actions.append(action)
            receipts_by_index[index] = receipt
        if skip is not None:
            skips.append(skip)
    return actions, skips, receipts_by_index


def build_report(
    state_root: Path | str | None = None,
    *,
    artifact_roots: list[Path] | None = None,
    apply: bool = False,
    task_id: str = DEFAULT_TASK_ID,
    agent_uid: str = DEFAULT_AGENT_UID,
    stale_after_hours: float = DEFAULT_STALE_HOURS,
    timestamp: str | None = None,
    output: Path | None = None,
) -> dict[str, Any]:
    ts = timestamp or datetime.now(timezone.utc).isoformat()
    now = _parse_time(ts) or datetime.now(timezone.utc)
    roots = artifact_roots or _default_artifact_roots()
    state = Path(state_root) if state_root is not None else None
    queue = queue_path(state)
    rows = read_queue(state)
    actions, skips, receipts_by_index = find_actions(
        rows,
        task_id=task_id,
        agent_uid=agent_uid,
        artifact_roots=roots,
        stale_after_hours=stale_after_hours,
        now=now,
        timestamp=ts,
    )

    backup_path = ""
    applied: list[dict[str, Any]] = []
    if apply and actions:
        backup = queue.with_name(f"{queue.name}.a2a-sab-qwen-runtime-block-{_safe_timestamp(ts)}.bak")
        shutil.copy2(queue, backup)
        backup_path = str(backup)
        for action in actions:
            receipt = receipts_by_index[action.row_index]
            closed = close_task(
                action.task_id,
                agent_uid=agent_uid,
                status="blocked",
                receipt=receipt,
                state_root=state,
                closed_via="a2a_block_sab_qwen_runtime_blockers",
                require_artifact_or_evidence=True,
                now=ts,
            )
            applied.append(
                {
                    "task_id": action.task_id,
                    "status": closed.get("status"),
                    "receipt_id": closed.get("receipt_id"),
                }
            )

    readiness = evaluate_a2a_readiness(state)
    report = {
        "schema_version": 1,
        "generated_at": ts,
        "queue_path": str(queue),
        "applied": apply,
        "backup_path": backup_path,
        "candidate_count": len(actions),
        "applied_count": len(applied),
        "skip_count": len(skips),
        "actions": [asdict(action) for action in actions],
        "skips": [asdict(skip) for skip in skips],
        "applied_rows": applied,
        "post_readiness": {
            "ready": readiness.ready,
            "open_tasks": readiness.open_tasks,
            "unknown_status_tasks": readiness.unknown_status_tasks,
            "unverified_closed_tasks": readiness.unverified_closed_tasks,
            "reasons": list(readiness.reasons),
        },
    }
    if output is not None:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="Mutate the live queue after writing a backup.")
    parser.add_argument("--state-root", type=Path, default=None, help="Override DHARMA state root.")
    parser.add_argument("--artifact-root", action="append", default=None)
    parser.add_argument("--task-id", default=DEFAULT_TASK_ID)
    parser.add_argument("--agent-uid", default=DEFAULT_AGENT_UID)
    parser.add_argument("--stale-after-hours", type=float, default=DEFAULT_STALE_HOURS)
    parser.add_argument("--timestamp", default=None, help="Receipt/report timestamp.")
    parser.add_argument("--output", type=Path, default=None, help="Optional report JSON path.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    artifact_roots = (
        [Path(root).expanduser() for root in args.artifact_root]
        if args.artifact_root
        else None
    )
    report = build_report(
        state_root=args.state_root,
        artifact_roots=artifact_roots,
        apply=args.apply,
        task_id=args.task_id,
        agent_uid=args.agent_uid,
        stale_after_hours=args.stale_after_hours,
        timestamp=args.timestamp,
        output=args.output,
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
