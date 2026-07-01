"""Durable Learning Spine consolidation loop for long Forge scheduler runs.

The Forge scheduler is intentionally expensive: one campaign can include live
model calls and SWE-bench Docker grading. This sidecar keeps the Learning Spine
turning at a higher cadence without pretending to produce new benchmark results.
Each tick ingests the latest available campaign meta report through the same
shadow-only spine entry point and records an audit row, including duplicate
ingests. New campaign hashes create new signals; unchanged reports still leave
an auditable "no new signal" learning receipt.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import time
from pathlib import Path
from typing import Any, Callable

from dharma_swarm.daemon_config import dharma_state_dir

from .ingest_learning import META_NAME, ingest_run

RUN_ROOT = dharma_state_dir() / "forge_v1" / "forge_v2" / "scheduler"
LOOP_ROOT = dharma_state_dir() / "forge_v1" / "forge_v2" / "spine_loops"


def now_stamp() -> str:
    return time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")


def append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(payload, sort_keys=True, default=str) + "\n")


def sha256_file(path: Path) -> str | None:
    if not path.exists():
        return None
    return hashlib.sha256(path.read_bytes()).hexdigest()


def discover_scheduler_run(*, run_root: Path, scheduler_label: str | None) -> Path | None:
    if not run_root.exists():
        return None
    dirs = [p for p in run_root.iterdir() if p.is_dir()]
    if scheduler_label:
        dirs = [p for p in dirs if p.name.startswith(f"{scheduler_label}_")]
    if not dirs:
        return None
    return max(dirs, key=lambda p: p.stat().st_mtime)


def run_spine_loop(
    *,
    run_dir: Path | None,
    scheduler_label: str | None,
    run_root: Path,
    loop_root: Path,
    label: str,
    duration_hours: float | None,
    max_iterations: int,
    interval_seconds: float,
    store_root: Path | str | None,
    epoch_id: str,
    ingester: Callable[..., dict[str, Any]] = ingest_run,
    sleep_fn: Callable[[float], None] = time.sleep,
    time_fn: Callable[[], float] = time.time,
) -> dict[str, Any]:
    out = loop_root / f"{label}_{now_stamp()}"
    out.mkdir(parents=True, exist_ok=True)
    ledger = out / "spine_loop_ledger.jsonl"
    started = time_fn()
    deadline = None if duration_hours is None else started + duration_hours * 3600
    last_hash: str | None = None

    state: dict[str, Any] = {
        "schema": "forge_v2.learning_spine_loop.v1",
        "started_at": now_stamp(),
        "loop_dir": str(out),
        "scheduler_label": scheduler_label,
        "pinned_run_dir": str(run_dir) if run_dir else "",
        "run_root": str(run_root),
        "duration_hours": duration_hours,
        "max_iterations": max_iterations,
        "interval_seconds": interval_seconds,
        "store_root": str(store_root) if store_root else "",
        "epoch_id": epoch_id,
        "iterations": 0,
        "ingests_ok": 0,
        "ingests_error": 0,
        "new_signal_rows": 0,
        "duplicate_signal_rows": 0,
        "last_report_sha256": None,
        "last_run_dir": None,
        "stop_reason": None,
    }
    write_json(out / "state.json", state)

    while True:
        if state["iterations"] >= max_iterations:
            state["stop_reason"] = "max_iterations"
            break
        if deadline is not None and time_fn() >= deadline:
            state["stop_reason"] = "duration_hours"
            break

        state["iterations"] += 1
        selected_run = run_dir or discover_scheduler_run(run_root=run_root, scheduler_label=scheduler_label)
        row: dict[str, Any] = {
            "event": "spine_loop_tick",
            "iteration": state["iterations"],
            "at": now_stamp(),
            "run_dir": str(selected_run) if selected_run else "",
        }

        if selected_run is None:
            row["status"] = "no_scheduler_run"
        else:
            report_path = selected_run / META_NAME
            report_sha = sha256_file(report_path)
            row["source_report_sha256"] = report_sha
            row["report_changed"] = bool(report_sha and report_sha != last_hash)
            if report_sha:
                last_hash = report_sha
                try:
                    summary = ingester(selected_run, store_root=store_root, epoch_id=epoch_id)
                    row["status"] = "ok" if summary.get("ok") else "error"
                    row["summary"] = summary
                    if summary.get("ok"):
                        state["ingests_ok"] += 1
                        store = summary.get("store") or {}
                        state["new_signal_rows"] += int(store.get("n_new") or 0)
                        state["duplicate_signal_rows"] += int(store.get("n_duplicate") or 0)
                    else:
                        state["ingests_error"] += 1
                except Exception as exc:  # noqa: BLE001 - loop must receipt and continue.
                    row["status"] = "error"
                    row["error"] = f"{type(exc).__name__}: {exc}"
                    state["ingests_error"] += 1
            else:
                row["status"] = "no_campaign_meta_report"

        state["last_report_sha256"] = row.get("source_report_sha256")
        state["last_run_dir"] = row.get("run_dir")
        append_jsonl(ledger, row)
        write_json(out / "state.json", state)
        if interval_seconds > 0:
            sleep_fn(interval_seconds)

    state["finished_at"] = now_stamp()
    append_jsonl(
        ledger,
        {
            "event": "spine_loop_stop",
            "at": state["finished_at"],
            "stop_reason": state["stop_reason"],
            "iterations": state["iterations"],
            "ingests_ok": state["ingests_ok"],
            "ingests_error": state["ingests_error"],
        },
    )
    write_json(out / "state.json", state)
    return state


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run repeated Learning Spine consolidation ticks.")
    parser.add_argument("--run-dir", default=None, help="Pin a scheduler run dir; default discovers latest by label.")
    parser.add_argument("--scheduler-label", default="forge_2_1_spine_8h")
    parser.add_argument("--run-root", default=str(RUN_ROOT))
    parser.add_argument("--loop-root", default=str(LOOP_ROOT))
    parser.add_argument("--label", default="forge_2_1_spine_loop")
    parser.add_argument("--duration-hours", type=float, default=8.0)
    parser.add_argument("--max-iterations", type=int, default=500)
    parser.add_argument("--interval-seconds", type=float, default=60.0)
    parser.add_argument("--store-root", default=None)
    parser.add_argument("--epoch-id", default="epoch_0")
    args = parser.parse_args(argv)

    state = run_spine_loop(
        run_dir=Path(args.run_dir).expanduser() if args.run_dir else None,
        scheduler_label=args.scheduler_label,
        run_root=Path(args.run_root).expanduser(),
        loop_root=Path(args.loop_root).expanduser(),
        label=args.label,
        duration_hours=args.duration_hours,
        max_iterations=args.max_iterations,
        interval_seconds=args.interval_seconds,
        store_root=Path(args.store_root).expanduser() if args.store_root else None,
        epoch_id=args.epoch_id,
    )
    print(
        f"[forge_spine_loop] stop={state['stop_reason']} iterations={state['iterations']} "
        f"ok={state['ingests_ok']} errors={state['ingests_error']} dir={state['loop_dir']}",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
