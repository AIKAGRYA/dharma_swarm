#!/usr/bin/env python3
"""version_metrics_rollup.py — read-only per-version metrics regenerator.

Folds the existing truth stores (the evolution archive JSONL + the runtime.db
delegation_runs table) into one per-build_id tracking file. It is an
OBSERVATION surface: it never writes the archive, never mutates runtime.db,
never touches the live daemon. It operates on COPIES only.

Verified/heuristic split (load-bearing honesty rule):
  - verified_metrics gate promotion: correctness (real pytest pass_rate),
    gate_allow_rate (telos gate outcomes), rollback_rate (DiffApplier),
    receipt_ok_rate / cost / latency (from delegation_runs.receipt_json).
  - heuristic_metrics (dharmic_alignment, elegance, swabhaav_alignment) are
    recorded for MAP-Elites diversity but carry ZERO promotion authority.
  - Cost comes from receipt_json.cost_usd, NEVER FitnessScore.economic_value.

Back-compat: the ~11k existing archive entries have no daemon_version tag. When
a version filter is requested but entries are untagged, the rollup falls back to
the timestamp window (so historical data still rolls up under "untagged").

Usage:
    python3 scripts/runtime/version_metrics_rollup.py \
        --archive /tmp/copy_archive.jsonl \
        --runtime-db /tmp/copy_runtime.db \
        --build-id 0.1.0+9c76b2106 \
        --out ~/.dharma/evolution/version_metrics/0.1.0+9c76b2106.json

Always copy the source files first; never point --runtime-db at the live db.
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import statistics
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 1
DEFAULT_STATE_ROOT = Path(os.environ.get("DHARMA_STATE_DIR", "~/.dharma")).expanduser()
DEFAULT_MAX_AGE_HOURS = 24.0


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


def _pct(num: int, den: int) -> float:
    return round(num / den, 4) if den else 0.0


def _entry_daemon_version(entry: dict[str, Any]) -> str | None:
    """daemon_version lives in the entry's free-form fields (test_results,
    feature_coords metadata, or a top-level tag once H3 lands). Probe all."""
    for key in ("daemon_version", "build_id"):
        if entry.get(key):
            return str(entry[key])
    tr = entry.get("test_results") or {}
    if isinstance(tr, dict) and tr.get("daemon_version"):
        return str(tr["daemon_version"])
    return None


def load_archive_entries(
    archive_path: Path,
    build_id: str | None,
    window_start: str | None,
    window_end: str | None,
) -> tuple[list[dict[str, Any]], bool]:
    """Return (matching_entries, used_timestamp_fallback)."""
    if not archive_path.exists():
        return [], False
    tagged: list[dict[str, Any]] = []
    untagged: list[dict[str, Any]] = []
    with archive_path.open("r", encoding="utf-8", errors="ignore") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            tag = _entry_daemon_version(entry)
            if build_id and tag == build_id:
                tagged.append(entry)
            elif tag is None:
                untagged.append(entry)

    if build_id and tagged:
        return tagged, False

    # Fallback: no tagged entries for this build_id -> use timestamp window over
    # untagged entries (back-compat for the historical corpus).
    if window_start or window_end:
        windowed = [
            e
            for e in untagged
            if (not window_start or str(e.get("timestamp", "")) >= window_start)
            and (not window_end or str(e.get("timestamp", "")) <= window_end)
        ]
        return windowed, True
    if not build_id:
        return untagged, True
    return [], True


def _archive_metrics(entries: list[dict[str, Any]]) -> dict[str, Any]:
    n = len(entries)
    applied = [e for e in entries if str(e.get("status", "")) == "applied"]
    rolled = [e for e in entries if e.get("rollback_reason")]
    gate_block = [e for e in entries if e.get("gates_failed")]
    correctness = [
        float((e.get("test_results") or {}).get("pass_rate", 0.0) or 0.0)
        for e in entries
        if isinstance(e.get("test_results"), dict)
        and "pass_rate" in (e.get("test_results") or {})
    ]
    promotion_hist = {"CANDIDATE": 0, "LOCAL_PASS": 0, "SYSTEM_PASS": 0, "PROMOTED": 0}
    for e in entries:
        ps = str(e.get("promotion_state", "")).upper()
        if ps in promotion_hist:
            promotion_hist[ps] += 1

    def _mean(field: str) -> float:
        vals = [
            float((e.get("fitness") or {}).get(field, 0.0) or 0.0)
            for e in entries
            if isinstance(e.get("fitness"), dict)
        ]
        return round(statistics.fmean(vals), 4) if vals else 0.0

    timestamps = sorted(str(e.get("timestamp", "")) for e in entries if e.get("timestamp"))
    return {
        "n_entries": n,
        "n_applied": len(applied),
        "correctness_mean": round(statistics.fmean(correctness), 4) if correctness else 0.0,
        "rollback_rate": _pct(len(rolled), len(applied) or n),
        "gate_allow_rate": round(1.0 - _pct(len(gate_block), n), 4),
        "promotion_state_hist": promotion_hist,
        "heuristic_metrics": {
            "dharmic_alignment": _mean("dharmic_alignment"),
            "elegance": _mean("elegance"),
            "swabhaav_alignment": _mean("swabhaav_alignment"),
        },
        "first_seen": timestamps[0] if timestamps else None,
        "last_seen": timestamps[-1] if timestamps else None,
    }


def _runtime_metrics(
    db_path: Path,
    build_id: str | None,
    window_start: str | None,
    window_end: str | None,
) -> dict[str, Any]:
    out: dict[str, Any] = {
        "receipt_ok_rate": 0.0,
        "cost_usd_per_applied": 0.0,
        "latency_ms_p50": 0,
        "latency_ms_p95": 0,
        "n_runs": 0,
        "cost_observed": False,
    }
    if not db_path.exists():
        return out
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            "SELECT status, started_at, metadata_json, receipt_json "
            "FROM delegation_runs"
        ).fetchall()
    except sqlite3.OperationalError:
        conn.close()
        return out
    conn.close()

    matched: list[sqlite3.Row] = []
    for r in rows:
        meta = {}
        try:
            meta = json.loads(r["metadata_json"] or "{}")
        except (json.JSONDecodeError, TypeError):
            meta = {}
        tag = meta.get("daemon_version") or meta.get("build_id")
        if build_id and tag == build_id:
            matched.append(r)
        elif build_id is None or (tag is None and (window_start or window_end)):
            ts = str(r["started_at"] or "")
            if (not window_start or ts >= window_start) and (
                not window_end or ts <= window_end
            ):
                matched.append(r)

    if not matched:
        return out

    ok = 0
    latencies: list[float] = []
    costs: list[float] = []
    for r in matched:
        rec = {}
        try:
            rec = json.loads(r["receipt_json"] or "{}")
        except (json.JSONDecodeError, TypeError):
            rec = {}
        if str(rec.get("status", "")) == "ok" or str(r["status"]) == "completed":
            ok += 1
        lat = rec.get("latency_ms")
        if isinstance(lat, (int, float)):
            latencies.append(float(lat))
        cost = rec.get("cost_usd")
        if isinstance(cost, (int, float)):
            costs.append(float(cost))

    out["n_runs"] = len(matched)
    out["receipt_ok_rate"] = _pct(ok, len(matched))
    if latencies:
        latencies.sort()
        out["latency_ms_p50"] = int(statistics.median(latencies))
        out["latency_ms_p95"] = int(latencies[min(len(latencies) - 1, int(len(latencies) * 0.95))])
    if costs:
        out["cost_observed"] = True
        out["cost_usd_per_applied"] = round(sum(costs) / max(ok, 1), 6)
    return out


def build_rollup(
    archive_path: Path,
    db_path: Path,
    build_id: str | None,
    daemon_version: str | None = None,
    git_sha: str | None = None,
    window_start: str | None = None,
    window_end: str | None = None,
) -> dict[str, Any]:
    entries, used_fallback = load_archive_entries(
        archive_path, build_id, window_start, window_end
    )
    arch = _archive_metrics(entries)
    rt = _runtime_metrics(db_path, build_id, window_start, window_end)

    first, last = arch["first_seen"], arch["last_seen"]
    soak_hours = 0.0
    if first and last:
        try:
            soak_hours = round(
                (datetime.fromisoformat(last) - datetime.fromisoformat(first)).total_seconds()
                / 3600.0,
                3,
            )
        except ValueError:
            soak_hours = 0.0

    return {
        "schema_version": SCHEMA_VERSION,
        "build_id": build_id or "untagged",
        "daemon_version": daemon_version,
        "git_sha": git_sha,
        "generated_at": _utc_now(),
        "max_age_hours": DEFAULT_MAX_AGE_HOURS,
        "source_owners": ["archive.jsonl", "runtime.db:delegation_runs"],
        "used_timestamp_fallback": used_fallback,
        "window": {
            "first_seen": first,
            "last_seen": last,
            "soak_hours": soak_hours,
            "n_entries": arch["n_entries"],
            "n_runs": rt["n_runs"],
        },
        "verified_metrics": {
            "correctness_mean": arch["correctness_mean"],
            "gate_allow_rate": arch["gate_allow_rate"],
            "rollback_rate": arch["rollback_rate"],
            "receipt_ok_rate": rt["receipt_ok_rate"],
            "cost_usd_per_applied": rt["cost_usd_per_applied"],
            "cost_observed": rt["cost_observed"],
            "latency_ms_p50": rt["latency_ms_p50"],
            "latency_ms_p95": rt["latency_ms_p95"],
        },
        "heuristic_metrics": arch["heuristic_metrics"],
        "promotion_state_hist": arch["promotion_state_hist"],
        "circuit_breaker_trips": 0,
        "verdict": "HOLD",
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--archive", required=True, type=Path, help="COPIED archive.jsonl")
    ap.add_argument("--runtime-db", required=True, type=Path, help="COPIED runtime.db")
    ap.add_argument("--build-id", default=None)
    ap.add_argument("--daemon-version", default=None)
    ap.add_argument("--git-sha", default=None)
    ap.add_argument("--window-start", default=None)
    ap.add_argument("--window-end", default=None)
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args(argv)

    rollup = build_rollup(
        args.archive,
        args.runtime_db,
        args.build_id,
        args.daemon_version,
        args.git_sha,
        args.window_start,
        args.window_end,
    )
    text = json.dumps(rollup, indent=2)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
