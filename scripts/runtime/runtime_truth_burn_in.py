#!/usr/bin/env python3
"""Repeated runtime truth closeout gate for daemon burn-in proof."""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_REPO_ROOT_FOR_IMPORT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT_FOR_IMPORT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT_FOR_IMPORT))

from dharma_swarm.operator_core.live_ops_census_contract import (  # noqa: E402
    DEFAULT_STATE_ROOT,
)
from scripts.runtime.runtime_truth_closeout import (  # noqa: E402
    _build_census,
    evaluate_closeout,
)


SCHEMA_VERSION = "runtime_truth_burn_in.v1"
DEFAULT_REPORT = DEFAULT_STATE_ROOT / "ops" / "runtime_truth_burn_in_latest.json"


def _utc_now() -> datetime:
    return datetime.now(UTC).replace(microsecond=0)


def _failed_check_ids(closeout: dict[str, Any]) -> list[str]:
    return [
        str(check.get("id"))
        for check in closeout.get("checks") or []
        if isinstance(check, dict) and check.get("passed") is not True
    ]


def build_burn_in_report(
    samples: list[dict[str, Any]],
    *,
    started_at: datetime,
    completed_at: datetime,
    allow_paused: bool,
    requested_duration_seconds: float,
    interval_seconds: float,
    min_samples: int,
) -> dict[str, Any]:
    failed_samples: list[dict[str, Any]] = []
    for index, sample in enumerate(samples, start=1):
        if sample.get("passed") is not True:
            failed_samples.append(
                {
                    "sample": index,
                    "status": sample.get("status") or "fail",
                    "failed_checks": _failed_check_ids(sample),
                }
            )
    sample_count_met = len(samples) >= min_samples
    all_samples_passed = not failed_samples and bool(samples)
    passed = sample_count_met and all_samples_passed
    mode = "paused_smoke" if allow_paused else "strict_unpaused"
    status = "pass" if passed else "fail"
    return {
        "schema_version": SCHEMA_VERSION,
        "mode": mode,
        "status": status,
        "passed": passed,
        "strict_unpaused_proven": passed and not allow_paused,
        "allow_paused": allow_paused,
        "started_at": started_at.isoformat(),
        "completed_at": completed_at.isoformat(),
        "requested_duration_seconds": requested_duration_seconds,
        "interval_seconds": interval_seconds,
        "min_samples": min_samples,
        "sample_count": len(samples),
        "sample_count_met": sample_count_met,
        "all_samples_passed": all_samples_passed,
        "failed_samples": failed_samples,
        "scope": samples[-1].get("scope") if samples else {},
        "samples": samples,
    }


def write_report(path: Path, report: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(f".{path.name}.{time.monotonic_ns()}.tmp")
    tmp_path.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    tmp_path.replace(path)


def run_burn_in(
    *,
    repo_root: Path,
    state_root: Path,
    allow_paused: bool,
    duration_seconds: float,
    interval_seconds: float,
    min_samples: int,
    stop_on_failure: bool,
    max_pending_high: int = 25,
    max_pending_total: int = 100,
    max_running: int = 25,
) -> dict[str, Any]:
    started_at = _utc_now()
    deadline = time.monotonic() + max(0.0, duration_seconds)
    samples: list[dict[str, Any]] = []
    interval = max(0.0, interval_seconds)
    required_samples = max(1, min_samples)

    while True:
        census = _build_census(repo_root.expanduser(), state_root.expanduser())
        sample = evaluate_closeout(
            census,
            state_root=state_root.expanduser(),
            allow_paused=allow_paused,
            max_pending_high=max_pending_high,
            max_pending_total=max_pending_total,
            max_running=max_running,
        )
        sample["sample_index"] = len(samples) + 1
        sample["sampled_at"] = _utc_now().isoformat()
        samples.append(sample)
        if stop_on_failure and sample.get("passed") is not True:
            break
        if time.monotonic() >= deadline and len(samples) >= required_samples:
            break
        if interval:
            time.sleep(interval)

    return build_burn_in_report(
        samples,
        started_at=started_at,
        completed_at=_utc_now(),
        allow_paused=allow_paused,
        requested_duration_seconds=max(0.0, duration_seconds),
        interval_seconds=interval,
        min_samples=required_samples,
    )


def _print_text(report: dict[str, Any]) -> None:
    print("RUNTIME TRUTH BURN-IN")
    print(f"status: {report['status']}")
    print(f"mode: {report['mode']}")
    print(f"strict_unpaused_proven: {report['strict_unpaused_proven']}")
    print(
        "samples: "
        f"{report['sample_count']}/{report['min_samples']} "
        f"all_passed={report['all_samples_passed']}"
    )
    scope = report.get("scope") or {}
    print(
        "scope: "
        f"mode={scope.get('mode') or '?'} "
        f"since={scope.get('since_created_at') or '?'} "
        f"epoch={scope.get('epoch_receipt_id') or '?'}"
    )
    for failed in report.get("failed_samples") or []:
        checks = ",".join(failed.get("failed_checks") or [])
        print(f"FAIL sample {failed.get('sample')}: {checks}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=_REPO_ROOT_FOR_IMPORT)
    parser.add_argument("--state-root", type=Path, default=DEFAULT_STATE_ROOT)
    parser.add_argument("--duration-seconds", type=float, default=300.0)
    parser.add_argument("--interval-seconds", type=float, default=60.0)
    parser.add_argument("--min-samples", type=int, default=2)
    parser.add_argument("--max-pending-high", type=int, default=25)
    parser.add_argument("--max-pending-total", type=int, default=100)
    parser.add_argument("--max-running", type=int, default=25)
    parser.add_argument(
        "--allow-paused",
        action="store_true",
        help="Run paused smoke burn-in; strict_unpaused_proven remains false.",
    )
    parser.add_argument("--no-stop-on-failure", action="store_true")
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--no-write-report", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    report = run_burn_in(
        repo_root=args.repo_root,
        state_root=args.state_root,
        allow_paused=args.allow_paused,
        duration_seconds=args.duration_seconds,
        interval_seconds=args.interval_seconds,
        min_samples=args.min_samples,
        stop_on_failure=not args.no_stop_on_failure,
        max_pending_high=max(0, args.max_pending_high),
        max_pending_total=max(0, args.max_pending_total),
        max_running=max(0, args.max_running),
    )
    if not args.no_write_report:
        write_report(args.report.expanduser(), report)
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        _print_text(report)
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
