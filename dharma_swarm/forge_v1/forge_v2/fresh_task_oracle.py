"""Fresh task oracle intake for RSI Lab taskbed ledgers.

The oracle is an intake/sealing layer, not a grader.  It converts harvested
post-cutoff PR-suite manifests into taskbed ledger rows with provenance-derived
contamination state.  Caller-provided contamination labels are recorded as
claims, but never trusted as the authority.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from . import taskbed_ledger
from .signals import canonical_sha256

CLEAN_ORACLE_STATES = frozenset({"fresh_post_cutoff", "fresh_private_local_generated"})
DEFAULT_SOURCE = "post_cutoff_pr_suite"
SCHEMA_VERSION = "forge_v2.fresh_task_oracle.v1"


def parse_timestamp(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def parse_cutoff(value: str) -> datetime:
    parsed = parse_timestamp(value)
    if parsed is None:
        raise ValueError("model_cutoff must be an ISO timestamp or date")
    return parsed


def read_manifest(path: Path) -> list[dict[str, Any]]:
    text = path.expanduser().read_text(encoding="utf-8")
    stripped = text.strip()
    if not stripped:
        return []
    if stripped.startswith("["):
        data = json.loads(stripped)
        if not isinstance(data, list):
            raise ValueError("JSON manifest must be a list")
        return [dict(row) for row in data if isinstance(row, dict)]
    rows: list[dict[str, Any]] = []
    for line in stripped.splitlines():
        if line.strip():
            row = json.loads(line)
            if isinstance(row, dict):
                rows.append(dict(row))
    return rows


def _list_field(row: dict[str, Any], *names: str) -> list[Any]:
    for name in names:
        value = row.get(name)
        if isinstance(value, list):
            return value
        if isinstance(value, str) and value.strip():
            return [value.strip()]
    return []


def fail_to_pass_count(row: dict[str, Any]) -> int:
    return len(_list_field(row, "fail_to_pass", "FAIL_TO_PASS"))


def evidence_timestamp(row: dict[str, Any]) -> datetime | None:
    candidates = (
        row.get("created_at"),
        row.get("merged_at"),
        row.get("closed_at"),
        (row.get("provenance") or {}).get("created_at") if isinstance(row.get("provenance"), dict) else None,
    )
    parsed = [ts for ts in (parse_timestamp(value) for value in candidates) if ts is not None]
    return max(parsed) if parsed else None


def task_id_for_row(row: dict[str, Any]) -> str:
    explicit = str(row.get("task_id") or row.get("instance_id") or "").strip()
    if explicit:
        return explicit
    repo = str(row.get("repo") or row.get("repository") or "").strip()
    pr_number = str(row.get("pr_number") or row.get("pull_number") or row.get("number") or "").strip()
    if repo and pr_number:
        return f"pr::{repo}#{pr_number}"
    return "fresh_task::" + canonical_sha256(row)[:16]


def derive_task_provenance(
    row: dict[str, Any],
    *,
    model_cutoff: datetime,
    source: str = DEFAULT_SOURCE,
) -> dict[str, Any]:
    """Derive contamination state from task evidence, never from caller labels."""
    ts = evidence_timestamp(row)
    after_cutoff = bool(ts and ts > model_cutoff)
    ftp_count = fail_to_pass_count(row)
    source_kind = str(row.get("source_kind") or row.get("benchmark") or source or "").lower()
    generated_after_freeze = bool(row.get("generated_after_candidate_freeze"))
    freeze_ts = parse_timestamp(
        row.get("candidate_freeze_timestamp")
        or row.get("candidate_frozen_at")
        or row.get("candidate_freeze_time")
    )
    freeze_receipt = str(
        row.get("candidate_freeze_receipt_sha256")
        or row.get("candidate_freeze_receipt")
        or ""
    ).strip()
    self_mod_clean_attested = bool(
        generated_after_freeze
        and freeze_ts is not None
        and ts is not None
        and ts > freeze_ts
        and freeze_receipt
    )

    blockers: list[str] = []
    state = "possible_pretrain"
    basis = "insufficient post-cutoff sealed task evidence"
    if generated_after_freeze and not self_mod_clean_attested:
        blockers.append("unattested_generated_after_candidate_freeze")
    if self_mod_clean_attested and ftp_count > 0:
        state = "fresh_private_local_generated"
        basis = "attested task suite was generated after the candidate was frozen"
    elif after_cutoff and ftp_count > 0:
        state = "fresh_post_cutoff"
        basis = "PR/test-suite timestamp is after the configured model cutoff"
    else:
        if not after_cutoff:
            blockers.append("not_after_model_cutoff")
        if ftp_count <= 0:
            blockers.append("missing_fail_to_pass_suite")
        if "swe-bench" in source_kind or "swebench" in source_kind:
            blockers.append("public_swebench_possible_pretrain")

    return {
        "schema": SCHEMA_VERSION,
        "contamination_state": state,
        "basis": basis,
        "model_cutoff": model_cutoff.isoformat().replace("+00:00", "Z"),
        "evidence_timestamp": ts.isoformat().replace("+00:00", "Z") if ts else "",
        "after_model_cutoff": after_cutoff,
        "fail_to_pass_count": ftp_count,
        "source": source,
        "source_kind": source_kind,
        "caller_claimed_contamination_state": row.get("contamination_state"),
        "generated_after_candidate_freeze": generated_after_freeze,
        "candidate_freeze_timestamp": freeze_ts.isoformat().replace("+00:00", "Z") if freeze_ts else "",
        "candidate_freeze_receipt_sha256": freeze_receipt,
        "self_mod_clean_attested": self_mod_clean_attested,
        "blockers": blockers,
        "task_sha256": canonical_sha256(row),
    }


def prepare_task_row(
    row: dict[str, Any],
    *,
    model_cutoff: datetime,
    source: str = DEFAULT_SOURCE,
    taskbed: str = "",
    max_uses_per_epoch: int = 1,
) -> dict[str, Any]:
    task_id = task_id_for_row(row)
    provenance = derive_task_provenance(row, model_cutoff=model_cutoff, source=source)
    payload = dict(row)
    payload["task_id"] = task_id
    payload["provenance"] = provenance
    payload["sealed_provenance"] = provenance
    payload["contamination_state"] = provenance["contamination_state"]
    payload["taskbed"] = taskbed
    payload["source"] = source
    payload["max_uses_per_epoch"] = int(row.get("max_uses_per_epoch") or max_uses_per_epoch)
    return payload


def import_fresh_tasks(
    rows: Iterable[dict[str, Any]],
    *,
    model_cutoff: str | datetime,
    db_path: Path | str = taskbed_ledger.DEFAULT_DB,
    source: str = DEFAULT_SOURCE,
    taskbed: str = "fresh_pr_suite",
    include_ineligible: bool = False,
    max_uses_per_epoch: int = 1,
) -> dict[str, Any]:
    cutoff = parse_cutoff(model_cutoff) if isinstance(model_cutoff, str) else model_cutoff
    if cutoff.tzinfo is None:
        cutoff = cutoff.replace(tzinfo=timezone.utc)
    cutoff = cutoff.astimezone(timezone.utc)

    imported: list[str] = []
    skipped: list[dict[str, Any]] = []
    by_state: dict[str, int] = {}
    for raw in rows:
        task = prepare_task_row(
            dict(raw),
            model_cutoff=cutoff,
            source=source,
            taskbed=taskbed,
            max_uses_per_epoch=max_uses_per_epoch,
        )
        provenance = dict(task["provenance"])
        state = str(provenance["contamination_state"])
        by_state[state] = by_state.get(state, 0) + 1
        if state not in CLEAN_ORACLE_STATES and not include_ineligible:
            skipped.append(
                {
                    "task_id": task["task_id"],
                    "contamination_state": state,
                    "blockers": provenance.get("blockers", []),
                }
            )
            continue
        taskbed_ledger.register_task(
            task,
            db_path=db_path,
            task_id=task["task_id"],
            source=source,
            taskbed=taskbed,
            contamination_state=state,
            provenance=provenance,
            created_at=str(raw.get("created_at") or raw.get("merged_at") or ""),
            max_uses_per_epoch=task["max_uses_per_epoch"],
        )
        imported.append(str(task["task_id"]))

    return {
        "schema": SCHEMA_VERSION,
        "source": source,
        "taskbed": taskbed,
        "model_cutoff": cutoff.isoformat().replace("+00:00", "Z"),
        "input_count": sum(by_state.values()),
        "imported_count": len(imported),
        "skipped_count": len(skipped),
        "imported_task_ids": imported,
        "skipped": skipped,
        "derived_state_counts": by_state,
        "ledger_state_counts": taskbed_ledger.task_counts(db_path=db_path),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Import sealed fresh tasks into the Forge taskbed ledger")
    parser.add_argument("--manifest", required=True, help="JSON or JSONL harvested task manifest")
    parser.add_argument("--model-cutoff", required=True, help="ISO timestamp/date for the model cutoff")
    parser.add_argument("--taskbed-db", default=str(taskbed_ledger.DEFAULT_DB))
    parser.add_argument("--source", default=DEFAULT_SOURCE)
    parser.add_argument("--taskbed", default="fresh_pr_suite")
    parser.add_argument("--include-ineligible", action="store_true")
    parser.add_argument("--max-uses-per-epoch", type=int, default=1)
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    summary = import_fresh_tasks(
        read_manifest(Path(args.manifest)),
        model_cutoff=args.model_cutoff,
        db_path=args.taskbed_db,
        source=args.source,
        taskbed=args.taskbed,
        include_ineligible=args.include_ineligible,
        max_uses_per_epoch=args.max_uses_per_epoch,
    )
    if args.json:
        print(json.dumps(summary, indent=2, sort_keys=True))
    else:
        print(
            "FORGE_FRESH_TASK_ORACLE_IMPORTED "
            f"imported={summary['imported_count']} skipped={summary['skipped_count']} "
            f"db={args.taskbed_db}"
        )
    return 0


__all__ = [
    "CLEAN_ORACLE_STATES",
    "DEFAULT_SOURCE",
    "SCHEMA_VERSION",
    "derive_task_provenance",
    "import_fresh_tasks",
    "prepare_task_row",
    "read_manifest",
    "task_id_for_row",
]
