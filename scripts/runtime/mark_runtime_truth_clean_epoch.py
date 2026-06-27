#!/usr/bin/env python3
"""Mark an append-only clean epoch for runtime truth active-head checks."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_REPO_ROOT_FOR_IMPORT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT_FOR_IMPORT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT_FOR_IMPORT))

from dharma_swarm.operator_core.live_ops_census_contract import (  # noqa: E402
    DEFAULT_STATE_ROOT,
)
from dharma_swarm.runtime_state import RuntimeReceipt, RuntimeStateStore  # noqa: E402


SCHEMA_VERSION = "runtime_truth_clean_epoch.v1"
RECEIPT_TYPE = "runtime_truth_clean_epoch"
EPOCH_FILENAME = "runtime_truth_clean_epoch.json"
DEFAULT_REASON = "operator marked active-head runtime truth clean epoch"
HISTORICAL_DIRT_POLICY = (
    "historical dirty receipts are not rewritten; active-head readiness is scoped "
    "to receipts created at or after since_created_at"
)


def _utc_now() -> datetime:
    return datetime.now(UTC).replace(microsecond=0)


def _parse_iso_datetime(raw: str) -> datetime:
    value = str(raw or "").strip()
    if not value:
        raise ValueError("timestamp is empty")
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC).replace(microsecond=0)


def _runtime_db_path(state_root: Path, explicit_db: Path | None) -> Path:
    if explicit_db is not None:
        return explicit_db.expanduser()
    env_path = str(os.environ.get("DHARMA_RUNTIME_DB") or "").strip()
    if env_path:
        return Path(env_path).expanduser()
    return state_root / "state" / "runtime.db"


def _epoch_path(state_root: Path) -> Path:
    return state_root / "state" / EPOCH_FILENAME


def _stable_suffix(*parts: str) -> str:
    digest = hashlib.sha256("\n".join(parts).encode("utf-8")).hexdigest()
    return digest[:16]


def build_epoch_payload(
    *,
    state_root: Path,
    db_path: Path,
    since_created_at: datetime,
    reason: str,
    created_at: datetime | None = None,
) -> dict[str, Any]:
    created = created_at or _utc_now()
    since_text = since_created_at.isoformat()
    suffix = _stable_suffix(since_text, reason)
    receipt_id = f"rr_runtime_truth_clean_epoch_{suffix}"
    run_id = f"run_runtime_truth_clean_epoch_{suffix}"
    idempotency_key = f"runtime_truth_clean_epoch:{suffix}"
    side_effect_key = f"runtime_truth_clean_epoch:{since_text}"
    return {
        "schema_version": SCHEMA_VERSION,
        "created_at": created.isoformat(),
        "since_created_at": since_text,
        "reason": reason,
        "historical_dirt_policy": HISTORICAL_DIRT_POLICY,
        "state_root": str(state_root),
        "db_path": str(db_path),
        "receipt_id": receipt_id,
        "receipt_type": RECEIPT_TYPE,
        "run_id": run_id,
        "task_id": "runtime-truth-clean-epoch",
        "agent_id": "operator.runtime_truth",
        "trace_id": f"trace_runtime_truth_clean_epoch_{suffix}",
        "correlation_id": f"corr_runtime_truth_clean_epoch_{suffix}",
        "idempotency_key": idempotency_key,
        "side_effect_key": side_effect_key,
    }


def _write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(f".{path.name}.tmp")
    tmp_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    tmp_path.replace(path)


def record_clean_epoch(payload: dict[str, Any], *, db_path: Path) -> RuntimeReceipt:
    receipt = RuntimeReceipt(
        receipt_id=str(payload["receipt_id"]),
        receipt_type=RECEIPT_TYPE,
        status="active",
        run_id=str(payload["run_id"]),
        task_id=str(payload["task_id"]),
        trace_id=str(payload["trace_id"]),
        correlation_id=str(payload["correlation_id"]),
        agent_id=str(payload["agent_id"]),
        idempotency_key=str(payload["idempotency_key"]),
        side_effect_key=str(payload["side_effect_key"]),
        payload={
            "schema_version": SCHEMA_VERSION,
            "since_created_at": str(payload["since_created_at"]),
            "reason": str(payload["reason"]),
            "historical_dirt_policy": HISTORICAL_DIRT_POLICY,
            "epoch_file": str(_epoch_path(Path(str(payload["state_root"])))),
        },
        created_at=_parse_iso_datetime(str(payload["created_at"])),
    )
    store = RuntimeStateStore(db_path, include_memory_plane=False)
    return store.record_runtime_receipt_sync(receipt)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state-root", type=Path, default=DEFAULT_STATE_ROOT)
    parser.add_argument("--db", type=Path, default=None, help="runtime.db path")
    parser.add_argument(
        "--since-created-at",
        default="",
        help="epoch boundary timestamp; defaults to current UTC time",
    )
    parser.add_argument("--reason", default=DEFAULT_REASON)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    state_root = args.state_root.expanduser()
    db_path = _runtime_db_path(state_root, args.db)
    since = (
        _parse_iso_datetime(args.since_created_at)
        if str(args.since_created_at or "").strip()
        else _utc_now()
    )
    payload = build_epoch_payload(
        state_root=state_root,
        db_path=db_path,
        since_created_at=since,
        reason=str(args.reason or DEFAULT_REASON),
    )
    record_clean_epoch(payload, db_path=db_path)
    _write_json_atomic(_epoch_path(state_root), payload)

    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(f"runtime truth clean epoch: {payload['since_created_at']}")
        print(f"receipt: {payload['receipt_id']}")
        print(f"file: {_epoch_path(state_root)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
