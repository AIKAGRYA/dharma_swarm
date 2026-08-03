#!/usr/bin/env python3
"""Organism liveness sentinel: a dead organism must fail loudly.

Context (receipt): between 2026-07-25 and 2026-08-01 the `com.dharma.swarm`
launchd service was booted out without a receipt while the doctor lane kept
citing a stale PID file and filing WARN. The organism was dead for ~7 days
and nothing screamed. This sentinel is the scream.

Three independent checks, all of which must pass:

1. launchd service presence — ``launchctl print gui/<uid>/com.dharma.swarm``
   must succeed. An absent service is a FAIL, never a WARN.
2. orchestrate-live process — a live process matching
   ``dharma_swarm.dgc_cli orchestrate-live`` must exist AND answer
   ``kill -0``. A PID read from any file is never trusted on its own.
3. admission-denial growth — the count of ``admission denied`` lines in
   ``~/.dharma/logs/swarm.err`` must not have grown since the previous run.
   Growth means launchd is thrashing in a fail-closed denial loop: the
   organism is "loaded" but effectively dead (588 such denials preceded the
   unrecorded 2026-07-28 bootout).

On any failure the sentinel writes a loud receipt
(``~/.dharma/witness/liveness_sentinel/ORGANISM_DOWN_<utc>.json``) and exits
nonzero. On success it updates the denial-count baseline and exits 0.

``--dry-run`` runs every check and prints the verdict but writes nothing
(no receipt, no baseline update). The exit code still reflects the verdict
so the flag is usable as a manual probe.

OPERATOR WIRING (do not automate — ``~/.dharma/cron/jobs.json`` is operator
authority; a human adds this object to the ``jobs`` array by hand):

  {"id": "organism_liveness_sentinel", "name": "Organism Liveness Sentinel",
   "handler": "shell", "enabled": true, "deliver": "local",
   "shell_command": "/Users/dhyana/dharma_swarm/.venv/bin/python /Users/dhyana/dharma_swarm/scripts/runtime/organism_liveness_sentinel.py",
   "schedule": {"kind": "interval", "minutes": 30, "display": "every 30m"},
   "timeout_sec": 60, "urgent": true,
   "prompt": "Fail loudly if the organism launchd service, orchestrate-live process, or admission lane is dead."}

Known blind spot, accepted: the sentinel rides the existing cron lane
(``com.dharma.cron-daemon``); if the cron daemon itself dies, nothing fires.
Cross-daemon watching is an operator decision, not this script's job.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

SERVICE_LABEL = "com.dharma.swarm"
ORCHESTRATE_PATTERN = "dharma_swarm.dgc_cli orchestrate-live"
DENIAL_PATTERN = re.compile(r"admission denied", re.IGNORECASE)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _state_root(raw: str | None) -> Path:
    if raw:
        return Path(raw).expanduser()
    return Path(os.environ.get("DHARMA_STATE_DIR") or "~/.dharma").expanduser()


@dataclass
class CheckResult:
    name: str
    ok: bool
    detail: str
    evidence: dict[str, object] = field(default_factory=dict)


def check_launchd_service(label: str = SERVICE_LABEL) -> CheckResult:
    target = f"gui/{os.getuid()}/{label}"
    try:
        proc = subprocess.run(
            ["launchctl", "print", target],
            capture_output=True,
            text=True,
            timeout=15,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return CheckResult(
            name="launchd_service",
            ok=False,
            detail=f"launchctl probe failed to execute: {exc}",
            evidence={"target": target},
        )
    if proc.returncode != 0:
        return CheckResult(
            name="launchd_service",
            ok=False,
            detail=f"service {target} is NOT loaded (launchctl rc={proc.returncode})",
            evidence={"target": target, "stderr": proc.stderr.strip()[:400]},
        )
    pid: int | None = None
    state: str | None = None
    for line in proc.stdout.splitlines():
        stripped = line.strip()
        if pid is None and stripped.startswith("pid ="):
            try:
                pid = int(stripped.split("=", 1)[1].strip())
            except ValueError:
                pass
        elif state is None and stripped.startswith("state ="):
            state = stripped.split("=", 1)[1].strip()
    return CheckResult(
        name="launchd_service",
        ok=True,
        detail=f"service {target} loaded (state={state}, pid={pid})",
        evidence={"target": target, "pid": pid, "state": state},
    )


def _pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False
    return True


def check_orchestrate_process(launchd_pid: int | None) -> CheckResult:
    try:
        proc = subprocess.run(
            ["pgrep", "-f", ORCHESTRATE_PATTERN],
            capture_output=True,
            text=True,
            timeout=15,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return CheckResult(
            name="orchestrate_process",
            ok=False,
            detail=f"pgrep probe failed to execute: {exc}",
        )
    pids = [int(p) for p in proc.stdout.split() if p.strip().isdigit()]
    live = [p for p in pids if _pid_alive(p)]
    if not live:
        return CheckResult(
            name="orchestrate_process",
            ok=False,
            detail=f"no live process matches '{ORCHESTRATE_PATTERN}'",
            evidence={"pgrep_pids": pids},
        )
    evidence: dict[str, object] = {"live_pids": live}
    if launchd_pid is not None and launchd_pid not in live:
        evidence["launchd_pid_mismatch"] = launchd_pid
        return CheckResult(
            name="orchestrate_process",
            ok=False,
            detail=(
                f"launchd claims pid {launchd_pid} but live orchestrate-live pids are "
                f"{live} — split-brain, treat as down"
            ),
            evidence=evidence,
        )
    return CheckResult(
        name="orchestrate_process",
        ok=True,
        detail=f"orchestrate-live alive (pids={live}, kill -0 verified)",
        evidence=evidence,
    )


def _count_denials(err_log: Path) -> int:
    if not err_log.exists():
        return 0
    count = 0
    with err_log.open("r", errors="replace") as fh:
        for line in fh:
            if DENIAL_PATTERN.search(line):
                count += 1
    return count


def check_admission_denials(err_log: Path, baseline_path: Path) -> CheckResult:
    current = _count_denials(err_log)
    previous: int | None = None
    if baseline_path.exists():
        try:
            previous = int(json.loads(baseline_path.read_text()).get("denial_count"))
        except (ValueError, TypeError, json.JSONDecodeError, OSError):
            previous = None
    evidence: dict[str, object] = {
        "err_log": str(err_log),
        "denial_count": current,
        "previous_count": previous,
    }
    if previous is not None and current > previous:
        return CheckResult(
            name="admission_denials",
            ok=False,
            detail=(
                f"admission-denial count grew {previous} -> {current}; launchd is "
                "thrashing in a fail-closed denial loop"
            ),
            evidence=evidence,
        )
    detail = (
        f"denial count stable at {current}"
        if previous is not None
        else f"denial count {current} (no baseline yet; recording)"
    )
    return CheckResult(name="admission_denials", ok=True, detail=detail, evidence=evidence)


def run_sentinel(
    *,
    state_root: Path,
    dry_run: bool,
    err_log: Path | None = None,
) -> int:
    sentinel_dir = state_root / "witness" / "liveness_sentinel"
    baseline_path = sentinel_dir / "denial_baseline.json"
    log_path = err_log if err_log is not None else state_root / "logs" / "swarm.err"

    service = check_launchd_service()
    launchd_pid = service.evidence.get("pid") if service.ok else None
    process = check_orchestrate_process(
        launchd_pid if isinstance(launchd_pid, int) else None
    )
    denials = check_admission_denials(log_path, baseline_path)

    checks = [service, process, denials]
    ok = all(c.ok for c in checks)
    verdict = {
        "sentinel": "organism_liveness_sentinel",
        "timestamp_utc": _utc_now(),
        "verdict": "OK" if ok else "ORGANISM_DOWN",
        "dry_run": dry_run,
        "checks": [asdict(c) for c in checks],
    }
    print(json.dumps(verdict, indent=2))

    if dry_run:
        return 0 if ok else 1

    sentinel_dir.mkdir(parents=True, exist_ok=True)
    if ok:
        baseline_path.write_text(
            json.dumps(
                {
                    "denial_count": denials.evidence.get("denial_count", 0),
                    "updated_at": verdict["timestamp_utc"],
                }
            )
            + "\n"
        )
        return 0

    stamp = verdict["timestamp_utc"].replace(":", "").replace("-", "")
    receipt_path = sentinel_dir / f"ORGANISM_DOWN_{stamp}.json"
    receipt_path.write_text(json.dumps(verdict, indent=2) + "\n")
    print(f"LOUD FAIL: receipt written to {receipt_path}", file=sys.stderr)
    return 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run every check and print the verdict; write no receipt or baseline.",
    )
    parser.add_argument(
        "--state-root",
        default=None,
        help="Override the ~/.dharma state root (default: $DHARMA_STATE_DIR or ~/.dharma).",
    )
    parser.add_argument(
        "--err-log",
        type=Path,
        default=None,
        help="Override the swarm stderr log scanned for admission denials.",
    )
    args = parser.parse_args(argv)
    return run_sentinel(
        state_root=_state_root(args.state_root),
        dry_run=args.dry_run,
        err_log=args.err_log,
    )


if __name__ == "__main__":
    raise SystemExit(main())
