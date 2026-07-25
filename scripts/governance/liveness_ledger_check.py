#!/usr/bin/env python3
"""Read-only replay verifier for the durable loop-liveness ledger.

Incident this gate names: the runtime's only liveness surface,
``~/.dharma/ops/loop_liveness.json``, is overwritten in place by
``dharma_swarm/orchestrate_live.py::_write_loop_liveness`` (tmp.replace), so
an unattended multi-day run leaves zero replayable uptime evidence and any
"it ran for N days" claim is unfalsifiable. The durable producer
(``dharma_swarm/orchestrate_live.py::append_liveness_ledger_row``) appends
digest-chained ``VerifiedMachineReceipt`` rows carrying ``boot_id``, pid,
running loops, restart counts, and abandoned loops to
``~/.dharma/ops/liveness_ledger.jsonl``; this checker replays that chain and
grades window coverage without ever writing.

Host-aware doctrine (mirrors ``scripts/runtime/github_ingestor_runner.py``):
an absent ledger means the organism has never booted on this seat — the
checker reports ``status=needs_host`` and exits 0. A broken chain, a tampered
row, or a failed coverage assertion exits 1.

Example (the 7-day A-gate shape: full window, hourly coverage, exactly one
deliberate restart):

    python3 scripts/governance/liveness_ledger_check.py \
        --window-hours 168 --min-rows 160 --expect-boot-ids 2 --max-gap-hours 2
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

# One digest formula, one chain walk: the leading-underscore import is
# deliberate — the failure mode this checker exists to prevent is a second,
# subtly different implementation of the receipt chain.
from dharma_swarm.spine.receipt import (  # noqa: E402
    _read_verified_machine_receipt_chain,
)

DEFAULT_LEDGER = Path.home() / ".dharma" / "ops" / "liveness_ledger.jsonl"
SCHEMA = "dharma.liveness_ledger_check.v1"


def _parse_stamp(row: dict[str, Any]) -> datetime | None:
    for key in ("produced_at", "started_at"):
        raw = str(row.get(key, "")).strip()
        if not raw:
            continue
        try:
            return datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except ValueError:
            continue
    return None


def evaluate(
    ledger: Path,
    *,
    window_hours: float = 168.0,
    min_rows: int = 0,
    expect_boot_ids: int | None = None,
    max_gap_hours: float | None = None,
    max_age_hours: float | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    moment = now or datetime.now(timezone.utc)
    report: dict[str, Any] = {
        "schema": SCHEMA,
        "claim": (
            "chain replay + window coverage grading only; read-only — attests "
            "nothing about loop health beyond what the producer recorded"
        ),
        "ledger": str(ledger),
        "window_hours": window_hours,
        "observed_at": moment.isoformat(),
        "errors": [],
    }
    if not ledger.exists():
        report.update(
            {
                "status": "needs_host",
                "reason": (
                    "ledger absent — the organism has never booted on this "
                    "seat; run the daemon on a host to produce rows"
                ),
            }
        )
        return report
    try:
        raw_rows = _read_verified_machine_receipt_chain(ledger)
    except (ValueError, OSError) as exc:
        report.update({"status": "fail", "errors": [f"chain replay failed: {exc}"]})
        return report

    rows = [
        row
        for row in raw_rows
        if isinstance(row.get("attributes"), dict)
        and row["attributes"].get("kind") == "loop_liveness"
    ]
    report["rows_total"] = len(raw_rows)
    report["rows_liveness"] = len(rows)

    cutoff = moment - timedelta(hours=window_hours)
    windowed: list[tuple[datetime, dict[str, Any]]] = []
    for row in rows:
        stamp = _parse_stamp(row)
        if stamp is not None and stamp >= cutoff:
            windowed.append((stamp, row))
    windowed.sort(key=lambda pair: pair[0])

    boot_sequence: list[str] = []
    for _, row in windowed:
        boot_id = str(row["attributes"].get("boot_id", ""))
        if not boot_sequence or boot_sequence[-1] != boot_id:
            boot_sequence.append(boot_id)
    distinct_boot_ids = sorted(set(boot_sequence))
    gaps_seconds = [
        (later - earlier).total_seconds()
        for (earlier, _), (later, _) in zip(windowed, windowed[1:])
    ]

    report.update(
        {
            "rows_in_window": len(windowed),
            "boot_ids_in_window": distinct_boot_ids,
            "boot_id_transitions": max(0, len(boot_sequence) - 1),
            "max_gap_seconds": max(gaps_seconds) if gaps_seconds else None,
            "last_row_age_seconds": (
                (moment - windowed[-1][0]).total_seconds() if windowed else None
            ),
            "abandoned_now": (
                windowed[-1][1]["attributes"].get("abandoned") if windowed else None
            ),
        }
    )

    errors: list[str] = []
    if min_rows and len(windowed) < min_rows:
        errors.append(
            f"coverage: {len(windowed)} liveness rows in the last "
            f"{window_hours}h, need >= {min_rows}"
        )
    if expect_boot_ids is not None and len(distinct_boot_ids) != expect_boot_ids:
        errors.append(
            f"boot identity: {len(distinct_boot_ids)} distinct boot_ids in "
            f"window, expected exactly {expect_boot_ids}"
        )
    if max_gap_hours is not None:
        limit = max_gap_hours * 3600.0
        oversized = [gap for gap in gaps_seconds if gap > limit]
        if oversized:
            errors.append(
                f"gap: {len(oversized)} inter-row gap(s) exceed "
                f"{max_gap_hours}h (worst {max(oversized):.0f}s) — the "
                "producer went dark inside the window"
            )
        if not windowed:
            errors.append("gap: no liveness rows inside the window at all")
    if max_age_hours is not None:
        if not windowed:
            errors.append("staleness: no liveness rows inside the window")
        elif (moment - windowed[-1][0]).total_seconds() > max_age_hours * 3600.0:
            errors.append(
                f"staleness: newest row is older than {max_age_hours}h — the "
                "producer is not currently alive"
            )

    report["errors"] = errors
    report["status"] = "fail" if errors else "ok"
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--ledger",
        type=Path,
        default=DEFAULT_LEDGER,
        help=f"ledger path (default: {DEFAULT_LEDGER})",
    )
    parser.add_argument("--window-hours", type=float, default=168.0)
    parser.add_argument(
        "--min-rows",
        type=int,
        default=0,
        help="fail unless at least this many liveness rows fall in the window",
    )
    parser.add_argument(
        "--expect-boot-ids",
        type=int,
        default=None,
        help="fail unless the window holds exactly this many distinct boot_ids",
    )
    parser.add_argument(
        "--max-gap-hours",
        type=float,
        default=None,
        help="fail when any inter-row gap in the window exceeds this",
    )
    parser.add_argument(
        "--max-age-hours",
        type=float,
        default=None,
        help="fail when the newest row is older than this",
    )
    args = parser.parse_args(argv)
    report = evaluate(
        args.ledger,
        window_hours=args.window_hours,
        min_rows=args.min_rows,
        expect_boot_ids=args.expect_boot_ids,
        max_gap_hours=args.max_gap_hours,
        max_age_hours=args.max_age_hours,
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    # needs_host is not a failure (host-aware doctrine); fail is.
    return 0 if report["status"] in {"ok", "needs_host"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
