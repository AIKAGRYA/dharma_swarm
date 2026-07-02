#!/usr/bin/env python3
"""Emit an algedonic P0 signal when provider delegation failures dominate."""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

FAILURE_SQL = (
    "SELECT substr(started_at,1,10) d, COUNT(*), "
    "COALESCE(SUM(CASE WHEN receipt_json LIKE '%ProviderChainExecutionError%' "
    "OR receipt_json LIKE '%429%' THEN 1 ELSE 0 END), 0) fails "
    "FROM delegation_runs WHERE started_at>=? GROUP BY d"
)
FAILURE_QUERY_FOR_RECEIPTS = (
    "SELECT substr(started_at,1,10) d, COUNT(*), "
    "SUM(receipt_json LIKE '%ProviderChainExecutionError%' OR receipt_json LIKE '%429%') fails "
    "FROM delegation_runs WHERE started_at>='2026-07-02' GROUP BY d;"
)
DEFAULT_THRESHOLD = 0.50


@dataclass(frozen=True)
class StarvationWindow:
    since_date: str
    total: int
    failures: int
    failure_fraction: float
    daily: list[dict[str, Any]]


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _state_dir(raw: str | None) -> Path:
    if raw:
        return Path(raw).expanduser()
    return Path(os.environ.get("DHARMA_STATE_DIR") or "~/.dharma").expanduser()


def _today_local() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def _read_previous(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def query_starvation_window(db_path: Path, *, since_date: str) -> StarvationWindow:
    if not db_path.exists():
        raise FileNotFoundError(f"runtime db not found: {db_path}")

    with sqlite3.connect(str(db_path)) as db:
        rows = db.execute(FAILURE_SQL, (since_date,)).fetchall()

    daily: list[dict[str, Any]] = []
    total = 0
    failures = 0
    for day, count, fail_count in rows:
        count_i = int(count or 0)
        fail_i = int(fail_count or 0)
        total += count_i
        failures += fail_i
        daily.append(
            {
                "date": str(day or ""),
                "total": count_i,
                "failures": fail_i,
                "failure_fraction": (fail_i / count_i) if count_i else 0.0,
            }
        )
    fraction = (failures / total) if total else 0.0
    return StarvationWindow(
        since_date=since_date,
        total=total,
        failures=failures,
        failure_fraction=fraction,
        daily=daily,
    )


def _signal(window: StarvationWindow, *, threshold: float, db_path: Path) -> dict[str, Any]:
    return {
        "ts": _utc_now(),
        "kind": "provider_starvation",
        "severity": "critical",
        "value": round(window.failure_fraction, 6),
        "action": "restore_live_provider_routing",
        "summary": (
            "delegation_runs provider-chain failures exceed threshold: "
            f"{window.failures}/{window.total} "
            f"({window.failure_fraction:.1%}) since {window.since_date}"
        ),
        "metadata": {
            "runtime_db": str(db_path),
            "since_date": window.since_date,
            "total": window.total,
            "failures": window.failures,
            "failure_fraction": window.failure_fraction,
            "threshold": threshold,
            "daily": window.daily,
            "query": FAILURE_QUERY_FOR_RECEIPTS,
        },
    }


def evaluate_and_emit(
    *,
    state_dir: Path,
    db_path: Path | None = None,
    since_date: str | None = None,
    threshold: float = DEFAULT_THRESHOLD,
    min_count: int = 1,
    suppress_unchanged: bool = True,
) -> dict[str, Any]:
    state_dir = state_dir.expanduser()
    runtime_db = (db_path or (state_dir / "state" / "runtime.db")).expanduser()
    since = since_date or _today_local()
    window = query_starvation_window(runtime_db, since_date=since)
    alert = window.total >= min_count and window.failure_fraction > threshold

    logs_dir = state_dir / "logs"
    latest_path = logs_dir / "provider_starvation_latest.json"
    stream_path = state_dir / "algedonic_signals.jsonl"
    signature = {
        "since_date": window.since_date,
        "total": window.total,
        "failures": window.failures,
        "threshold": threshold,
        "min_count": min_count,
    }
    previous = _read_previous(latest_path)
    previous_signature = previous.get("signature") if isinstance(previous.get("signature"), dict) else {}
    emitted = False
    signal: dict[str, Any] | None = None

    if alert:
        signal = _signal(window, threshold=threshold, db_path=runtime_db)
        if not suppress_unchanged or previous_signature != signature:
            stream_path.parent.mkdir(parents=True, exist_ok=True)
            with stream_path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(signal, sort_keys=True) + "\n")
            emitted = True

    status = {
        "schema_version": "dharma.runtime.provider_starvation_alert.v1",
        "checked_at": _utc_now(),
        "alert": alert,
        "emitted": emitted,
        "threshold": threshold,
        "min_count": min_count,
        "signature": signature,
        "window": asdict(window),
        "runtime_db": str(runtime_db),
        "algedonic_stream": str(stream_path),
    }
    if signal is not None:
        status["signal"] = signal
    _write_json(latest_path, status)
    return status


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--state-dir", default="")
    parser.add_argument("--db-path", default="")
    parser.add_argument("--since-date", default="")
    parser.add_argument("--threshold", type=float, default=DEFAULT_THRESHOLD)
    parser.add_argument("--min-count", type=int, default=1)
    parser.add_argument("--no-suppress-unchanged", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    try:
        status = evaluate_and_emit(
            state_dir=_state_dir(args.state_dir or None),
            db_path=Path(args.db_path).expanduser() if args.db_path else None,
            since_date=args.since_date or None,
            threshold=args.threshold,
            min_count=max(1, args.min_count),
            suppress_unchanged=not args.no_suppress_unchanged,
        )
    except Exception as exc:
        print(f"provider_starvation_alert ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps(status, indent=2, sort_keys=True))
    else:
        window = status["window"]
        print(
            "provider_starvation: "
            f"total={window['total']} failures={window['failures']} "
            f"fraction={window['failure_fraction']:.3f} "
            f"alert={status['alert']} emitted={status['emitted']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
