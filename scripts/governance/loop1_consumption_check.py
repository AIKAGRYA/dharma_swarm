#!/usr/bin/env python3
"""WP-LC4 disjoint checker: validate receipt-grounded provider consumption.

Reads `delegation_runs.receipt_json` from `runtime.db` (or a synthetic test
store), applies the four Loop-1 closure properties P1..P4, and emits a typed
receipt under `~/.dharma/loop_closure/loop1_consumption_receipt.json`.

With `--check` the checker replays the last committed receipt if one exists;
on a fresh host with no receipt it exits `0` with a `needs_host` typed gap.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sqlite3
import sys
import tempfile
from collections.abc import Mapping
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dharma_swarm.models import ProviderType
from dharma_swarm.receipt_consumption import (
    MAX_RECEIPT_DEMOTIONS,
    RECEIPT_CONSUMPTION_WINDOW,
    ReceiptConsumptionEvidence,
    apply_receipt_consumption_ranking,
)

RECEIPT_SCHEMA = "dharma.loop1_consumption_check.v1"
DEFAULT_DB = Path.home() / ".dharma" / "state" / "runtime.db"
DEFAULT_RECEIPT = Path.home() / ".dharma" / "loop_closure" / "loop1_consumption_receipt.json"


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _default_chain() -> list[ProviderType]:
    return [
        ProviderType.ANTHROPIC,
        ProviderType.OPENAI,
        ProviderType.OPENROUTER,
        ProviderType.OLLAMA,
    ]


def _receipt_row(
    trace_id: str,
    provider: ProviderType,
    *,
    status: str = "error",
    error_source: str = "provider",
    boot_id: str = "producer-boot",
) -> dict[str, Any]:
    return {
        "trace_id": trace_id,
        "provider": provider.value,
        "status": status,
        "error_source": error_source,
        "attributes": {"boot_id": boot_id},
    }


def _write_test_db(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS delegation_runs (
            started_at TEXT NOT NULL,
            receipt_json TEXT
        )
        """
    )
    conn.execute("DELETE FROM delegation_runs")
    for index, row in enumerate(rows):
        conn.execute(
            "INSERT INTO delegation_runs(started_at, receipt_json) VALUES (?, ?)",
            (f"2026-07-15T00:00:{index:02d}Z", json.dumps(row)),
        )
    conn.commit()
    conn.close()


def _stable_json(payload: Mapping[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def _digest(payload: Mapping[str, Any]) -> str:
    return hashlib.sha256(_stable_json(payload).encode("utf-8")).hexdigest()


def p1_failing_receipt_reorders(db_path: Path, chain: list[ProviderType]) -> dict[str, Any]:
    """P1: one failing provider receipt moves that provider to the end."""
    _write_test_db(
        db_path,
        [_receipt_row("p1-trace", ProviderType.ANTHROPIC)],
    )
    reordered, applied, evidence = apply_receipt_consumption_ranking(
        list(chain),
        db_path=db_path,
        boot_id="consumer-boot",
    )
    ok = (
        applied
        and reordered[-1] == ProviderType.ANTHROPIC
        and set(reordered) == set(chain)
        and evidence.consumed_trace_ids == ("p1-trace",)
        and "reordered_order" in evidence.decision_delta
    )
    return {
        "property": "P1",
        "ok": ok,
        "detail": "failing anthropic receipt demoted to end and cites trace_id",
        "consumed_trace_ids": list(evidence.consumed_trace_ids),
        "reordered_order": [p.value for p in reordered],
    }


def p2_no_failures_keep_default(db_path: Path, chain: list[ProviderType]) -> dict[str, Any]:
    """P2: with only successful receipts, the default order is preserved."""
    _write_test_db(
        db_path,
        [
            _receipt_row(
                "p2-trace",
                ProviderType.ANTHROPIC,
                status="ok",
                error_source="none",
            )
        ],
    )
    reordered, applied, evidence = apply_receipt_consumption_ranking(
        list(chain),
        db_path=db_path,
        boot_id="consumer-boot",
    )
    ok = not applied and reordered == chain and evidence.consumed_trace_ids == ()
    return {
        "property": "P2",
        "ok": ok,
        "detail": "successful receipt leaves default order unchanged",
        "consumed_trace_ids": list(evidence.consumed_trace_ids),
        "reordered_order": [p.value for p in reordered],
    }


def p3_cross_boot_consumes_prior(db_path: Path, chain: list[ProviderType]) -> dict[str, Any]:
    """P3: consumer boot_id differs from producer boot_id and chain verifies."""
    _write_test_db(
        db_path,
        [_receipt_row("p3-trace", ProviderType.OPENAI, boot_id="boot-a")],
    )
    reordered, applied, evidence = apply_receipt_consumption_ranking(
        list(chain),
        db_path=db_path,
        boot_id="boot-b",
    )
    ok = (
        applied
        and "boot-a" not in evidence.boot_id
        and evidence.boot_id == "boot-b"
        and "p3-trace" in evidence.consumed_trace_ids
        and set(reordered) == set(chain)
    )
    return {
        "property": "P3",
        "ok": ok,
        "detail": "consumer boot_id differs from producer boot_id and consumes prior trace",
        "consumer_boot_id": evidence.boot_id,
        "consumed_trace_ids": list(evidence.consumed_trace_ids),
    }


def p4_poisoning_bound(db_path: Path, chain: list[ProviderType]) -> dict[str, Any]:
    """P4: all providers failing still demotes at most MAX and excludes none."""
    _write_test_db(
        db_path,
        [_receipt_row(f"p4-{p.value}", p) for p in chain],
    )
    reordered, applied, evidence = apply_receipt_consumption_ranking(
        list(chain),
        db_path=db_path,
        boot_id="consumer-boot",
    )
    demoted = evidence.decision_delta.get("demoted_providers", [])
    ok = (
        applied
        and len(reordered) == len(chain)
        and set(reordered) == set(chain)
        and len(demoted) <= MAX_RECEIPT_DEMOTIONS
        and len(evidence.consumed_trace_ids) <= MAX_RECEIPT_DEMOTIONS
    )
    return {
        "property": "P4",
        "ok": ok,
        "detail": f"all providers failing demotes at most {MAX_RECEIPT_DEMOTIONS} and excludes none",
        "demoted_count": len(demoted),
        "demoted_providers": demoted,
        "reordered_order": [p.value for p in reordered],
    }


def _run_p1_p4(db_path: Path | None = None) -> dict[str, Any]:
    chain = _default_chain()
    with tempfile.TemporaryDirectory() as tmp:
        path = db_path or Path(tmp) / "runtime.db"
        if db_path:
            path.parent.mkdir(parents=True, exist_ok=True)
        results = [
            p1_failing_receipt_reorders(path, chain),
            p2_no_failures_keep_default(path, chain),
            p3_cross_boot_consumes_prior(path, chain),
            p4_poisoning_bound(path, chain),
        ]
    all_ok = all(r["ok"] for r in results)
    return {
        "schema": RECEIPT_SCHEMA,
        "observed_at": _now(),
        "outcome": "ok" if all_ok else "fail",
        "properties": results,
        "window": RECEIPT_CONSUMPTION_WINDOW,
        "max_demotions": MAX_RECEIPT_DEMOTIONS,
    }


def _write_receipt(receipt: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    receipt["digest"] = _digest({k: v for k, v in receipt.items() if k != "digest"})
    path.write_text(json.dumps(receipt, indent=2, sort_keys=True), encoding="utf-8")


def _read_receipt(path: Path) -> dict[str, Any] | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def _receipts_equivalent(a: dict[str, Any], b: dict[str, Any]) -> bool:
    return a.get("outcome") == b.get("outcome") and a.get("properties") == b.get("properties")


def _typed_gap(reason: str) -> dict[str, Any]:
    return {
        "schema": RECEIPT_SCHEMA,
        "observed_at": _now(),
        "outcome": "needs_host",
        "reason": reason,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="replay the committed receipt")
    parser.add_argument("--db", type=Path, default=None, help="runtime.db to read")
    parser.add_argument(
        "--receipt",
        type=Path,
        default=DEFAULT_RECEIPT,
        help="path to the receipt to write or replay",
    )
    parser.add_argument(
        "--stdout",
        action="store_true",
        help="print the receipt to stdout instead of writing it",
    )
    args = parser.parse_args(argv)

    db_path = args.db or (
        Path(os.environ["DGC_ROUTER_RECEIPT_DB"])
        if os.environ.get("DGC_ROUTER_RECEIPT_DB")
        else None
    )

    if args.check:
        prior = _read_receipt(args.receipt)
        if prior is None:
            gap = _typed_gap(f"no committed receipt at {args.receipt}")
            print(json.dumps(gap, indent=2, sort_keys=True))
            return 0
        current = _run_p1_p4(db_path)
        if not _receipts_equivalent(prior, current):
            print(
                json.dumps(
                    {
                        "schema": RECEIPT_SCHEMA,
                        "observed_at": _now(),
                        "outcome": "fail",
                        "reason": "replayed P1..P4 do not match committed receipt",
                        "prior": prior,
                        "current": current,
                    },
                    indent=2,
                    sort_keys=True,
                )
            )
            return 1
        print(json.dumps(current, indent=2, sort_keys=True))
        return 0

    receipt = _run_p1_p4(db_path)
    if args.stdout:
        print(json.dumps(receipt, indent=2, sort_keys=True))
    else:
        _write_receipt(receipt, args.receipt)
        print(args.receipt)
    return 0 if receipt["outcome"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
