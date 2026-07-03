#!/usr/bin/env python3
"""Loop 5b (World Radar — external Go chain) closure run — bounded replay.

Loop 5's external arm is the Go sense-organ chain: raw world observations flow
through ``dharma_swarm/world_radar/go_bridge.py`` into
``tools/world_signal_ingestor_go``, which emits one ``go_evidence_receipt.v0``
per accepted signal; the receipt bridge then projects accepted receipts back
into the world-signal feed/board the operator surfaces consume. This run
proves that chain end-to-end on a committed fixture observation — a REAL Go
process run, no mocks, no network (scout_fetch stays off):

  sense      : the bridge reads the committed fixture observations
               (tests/fixtures/world_radar_go/loop5b_observations.jsonl)
               dropped into the run's isolated state dir.
  interpret  : world_signal_ingestor_go (prebuilt binary or `go run .`)
               normalizes observations into scored signals.
  constrain  : the --min-score gate drops the low-signal fixture row
               (emitted_signals < raw_observations).
  act        : exactly one EvidenceReceipt per emitted signal lands in the
               sidecar receipt dir; summarize + feed projection read them back
               (receipt_count == emitted == projected rows for this run id).
  adapt      : the receipt store grows across cycles and the NEXT pass's
               board/health are rebuilt from receipt-projected rows —
               health.ingest_run_id before != after, fed forward into the
               operator-facing world-radar health surface.

HOST-AWARE (organism-rewire doctrine): if this host has neither a prebuilt
world_signal_ingestor_go binary (see `make go-build`) nor a Go toolchain, the
check reports NEEDS_HOST and exits 0 — missing operator state is not a
failure.

Emits a closure receipt in the schema the cybernetics-codex audit recomputes
(cycles>0, real_data, all five transitions receipted, adapt before!=after fed
forward, no tick errors). The receipt's own "closed" is advisory; the audit
recomputes it from the evidence.

Usage:
    python3 scripts/loop5b_world_radar_closure_run.py --cycles 2 [--report PATH]
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

TRANSITIONS = ("sense", "interpret", "constrain", "act", "adapt")
FIXTURE_PATH = REPO_ROOT / "tests" / "fixtures" / "world_radar_go" / "loop5b_observations.jsonl"
INGESTOR_MODULE = REPO_ROOT / "tools" / "world_signal_ingestor_go"


def _host_status() -> tuple[str, str]:
    """Return (status, detail). NEEDS_HOST when neither binary nor toolchain exists."""
    binary = INGESTOR_MODULE / INGESTOR_MODULE.name
    if binary.is_file() and os.access(binary, os.X_OK):
        return "OK", f"prebuilt binary present: {binary}"
    go = shutil.which("go")
    if go:
        return "OK", f"go toolchain present: {go}"
    return (
        "NEEDS_HOST",
        "no prebuilt world_signal_ingestor_go binary (run `make go-build`) "
        "and no Go toolchain on PATH",
    )


def run(args: argparse.Namespace) -> dict:
    from dharma_swarm.operator_core.world_radar.receipt_bridge import (
        project_world_signal_receipts,
        receipt_paths,
        summarize_go_world_receipts,
        world_receipts_dir,
    )
    from dharma_swarm.world_radar.go_bridge import run_world_radar_go_once
    from dharma_swarm.world_radar.io_utils import read_json, read_jsonl

    observed_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    base = {
        "loop": "5b",
        "loop_id": "world_radar_go_chain",
        "arm": "external",
        "fixture": str(FIXTURE_PATH.relative_to(REPO_ROOT)),
        "observed_at": observed_at,
    }

    host_status, host_detail = _host_status()
    if host_status == "NEEDS_HOST":
        return {
            **base,
            "host_status": host_status,
            "host_detail": host_detail,
            "cycles": 0,
            "real_data": False,
            "transitions_receipted": {t: False for t in TRANSITIONS},
            "adapt_proof": {"before": "", "after": "", "fed_forward": False},
            "tick_errors": [],
            "cycle_detail": [],
        }

    fixture_rows = read_jsonl(FIXTURE_PATH)
    state = Path(tempfile.mkdtemp(prefix="loop5b_world_radar_"))
    transitions_seen = {t: False for t in TRANSITIONS}
    tick_errors: list[str] = []
    cycle_rows: list[dict] = []
    invocation_mode = ""
    total_accepted = 0
    run_id_before = ""
    run_id_after = ""
    fed_forward = False

    try:
        # Drop the committed fixture into the isolated state dir (sense input).
        drops = state / "meta" / "world_operator_drops.jsonl"
        drops.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(FIXTURE_PATH, drops)
        receipt_dir = world_receipts_dir(state)
        health_path = state / "meta" / "world_radar" / "world_radar_health.json"

        for i in range(args.cycles):
            try:
                before_summary = summarize_go_world_receipts(receipt_dir)
                health_before = read_json(health_path, default={})
                run_id_cycle_before = str(
                    (health_before or {}).get("ingest_run_id", "")
                    if isinstance(health_before, dict)
                    else ""
                )
                if i == 0:
                    run_id_before = run_id_cycle_before

                result = run_world_radar_go_once(state_dir=state, scout_fetch=False)
                invocation_mode = result.ingestor_invocation_mode or invocation_mode

                # SENSE: the bridge read the committed fixture observations.
                sensed = result.raw_observations >= len(fixture_rows)
                transitions_seen["sense"] |= sensed

                # INTERPRET: the real Go ingestor ran and emitted scored signals.
                interpreted = (
                    result.emitted_signals >= 1
                    and result.ingestor_invocation_mode in {"binary", "go_run"}
                    and not result.errors
                )
                transitions_seen["interpret"] |= interpreted

                # CONSTRAIN: min-score gate dropped the low-signal fixture row.
                constrained = 0 < result.emitted_signals < result.raw_observations
                transitions_seen["constrain"] |= constrained

                # ACT: exactly one receipt per emitted signal for this run id,
                # and summarize + feed projection read them back.
                after_summary = summarize_go_world_receipts(receipt_dir)
                summary = read_json(Path(result.ingest_summary_path), default={})
                receipt_count = int((summary or {}).get("receipt_count", 0) or 0)
                projected = [
                    row
                    for row in project_world_signal_receipts(receipt_paths(receipt_dir))
                    if isinstance(row.get("metadata"), dict)
                    and row["metadata"].get("correlation_id") == result.ingest_run_id
                ]
                acted = (
                    receipt_count == result.emitted_signals
                    and len(projected) == result.emitted_signals
                    and after_summary["accepted"] >= 1
                )
                transitions_seen["act"] |= acted
                total_accepted = int(after_summary["accepted"])

                # ADAPT: the receipt store grew and the run id the health
                # surface carries changed — fed forward into the next pass.
                health_after = read_json(health_path, default={})
                run_id_after = str(
                    (health_after or {}).get("ingest_run_id", "")
                    if isinstance(health_after, dict)
                    else ""
                )
                adapted = (
                    after_summary["total"] > before_summary["total"]
                    and run_id_after != run_id_cycle_before
                    and bool(run_id_after)
                )
                if i > 0 and adapted:
                    # Cycle >1 proves feed-forward: this pass's board/health were
                    # rebuilt on top of the receipt store the previous pass grew.
                    fed_forward = True
                    transitions_seen["adapt"] = True

                cycle_rows.append(
                    {
                        "cycle": i + 1,
                        "raw_observations": result.raw_observations,
                        "emitted_signals": result.emitted_signals,
                        "receipt_count": receipt_count,
                        "projected_feed_rows": len(projected),
                        "receipts_total_before": before_summary["total"],
                        "receipts_total_after": after_summary["total"],
                        "ingest_run_id": result.ingest_run_id,
                        "invocation_mode": result.ingestor_invocation_mode,
                        "errors": list(result.errors),
                        "source_errors": list(result.source_errors),
                    }
                )
                if result.errors:
                    tick_errors.append(f"cycle {i}: bridge errors: {list(result.errors)}")
            except Exception as exc:  # noqa: BLE001
                tick_errors.append(f"cycle {i}: {type(exc).__name__}: {exc}")
    finally:
        shutil.rmtree(state, ignore_errors=True)

    return {
        **base,
        "host_status": host_status,
        "host_detail": host_detail,
        "invocation_mode": invocation_mode,
        "cycles": len(cycle_rows),
        "real_data": total_accepted >= 1 and invocation_mode in {"binary", "go_run"},
        "transitions_receipted": transitions_seen,
        "adapt_proof": {
            "field": "world_radar_health.ingest_run_id + go receipt store total "
            "(each pass's board/feed are rebuilt from receipt-projected rows)",
            "before": run_id_before,
            "after": run_id_after,
            "fed_forward": fed_forward,
            "accepted_receipts_total": total_accepted,
        },
        "tick_errors": tick_errors,
        "cycle_detail": cycle_rows,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cycles", type=int, default=2)
    parser.add_argument("--report", default=None)
    args = parser.parse_args()

    report = run(args)
    print(json.dumps(report, indent=2, default=str))

    default_path = (
        REPO_ROOT
        / "reports/loop_closure/cybernetics_codex"
        / f"{datetime.now(timezone.utc):%Y-%m-%d}_loop5b_world_radar_closure.json"
    )
    out = Path(args.report) if args.report else default_path
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, default=str) + "\n", encoding="utf-8")
    print(f"\nwrote closure receipt: {out}")

    if report["host_status"] == "NEEDS_HOST":
        print("LOOP5B_CLOSED=NEEDS_HOST")
        return 0

    closed = (
        report["cycles"] > 0
        and report["real_data"]
        and all(report["transitions_receipted"].values())
        and report["adapt_proof"]["fed_forward"]
        and report["adapt_proof"]["before"] != report["adapt_proof"]["after"]
        and not report["tick_errors"]
    )
    print(f"LOOP5B_CLOSED={'yes' if closed else 'no'}")
    return 0 if closed else 1


if __name__ == "__main__":
    raise SystemExit(main())
