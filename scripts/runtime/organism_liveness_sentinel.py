#!/usr/bin/env python3
"""Organism liveness sentinel: a dead organism must fail loudly.

Context (receipt): between 2026-07-25 and 2026-08-01 the `com.dharma.swarm`
launchd service was booted out without a receipt while the doctor lane kept
citing a stale PID file and filing WARN. The organism was dead for ~7 days
and nothing screamed. This sentinel is the scream.

Three independent checks, all of which must pass:

1. launchd service presence — ``launchctl print gui/<uid>/com.dharma.swarm``.
   Three states, exactly as ``dharma_swarm/doctor.py:_launchd_service_state``:
     ``loaded``  rc=0.
     ``absent``  the probe answered "no such service" (measured: rc=113,
                 ``Could not find service "..." in domain for user gui: 501``).
                 A FAIL, never a WARN — this is the 2026-07-28 bootout shape.
     ``unknown`` the probe could not run (no ``launchctl`` binary on any
                 non-macOS host, or a timeout), OR it answered about the
                 DOMAIN rather than the service (measured: rc=112, ``Could
                 not find domain for user gui: 99999`` — what a caller
                 outside the GUI session gets over ssh). Carries no evidence
                 either way; checks 2 and 3 decide.
   Reporting a dead service on the strength of a probe that never executed,
   or that was answering a different question, is a lie — and a watchdog
   nobody believes is not a watchdog.
2. orchestrate-live process — a live process matching ANY of the organism's
   real launch spellings (``ORCHESTRATE_COMMAND_FORMS``: the plist's console
   script ``dgc orchestrate-live``, the release runner's module form
   ``dharma_swarm.runtime_release_entrypoint orchestrate-live``, the container entrypoint
   ``dharma_swarm.orchestrate_live``) must exist AND answer ``kill -0``.
   A PID read from any file is never trusted on its own.
   Deliberately NOT symmetric with check 1: if the ``ps`` probe fails, that
   is a loud FAIL, not ``unknown``. Check 1 going blind is tolerable because
   launchd is not the organism; check 2 going blind means the sentinel
   cannot see the organism at all, and blindness is not health. The comment
   in ``check_orchestrate_process`` carries the receipt.

This script is a macOS-hub probe. It is wired only through the operator's
``~/.dharma/cron/jobs.json``; the container command form appears in
``ORCHESTRATE_COMMAND_FORMS`` for needle parity with the doctor and the
census (pinned by ``tests/test_runtime_command_forms.py``), NOT because the
sentinel is deployed there — ``python:3.12-slim`` ships neither
``launchctl`` nor ``ps``.
3. admission-denial growth — the count of ``admission denied`` lines in
   ``~/.dharma/logs/swarm.err`` must not have grown since the previous run.
   Growth means launchd is thrashing in a fail-closed denial loop: the
   organism is "loaded" but effectively dead (588 such denials preceded the
   unrecorded 2026-07-28 bootout).

On any failure the sentinel writes a loud receipt
(``~/.dharma/witness/liveness_sentinel/ORGANISM_DOWN_<utc>.json``) and exits
nonzero.

The denial baseline records the LAST OBSERVED count on every non-dry run,
pass or fail, so check 3 compares consecutive observations. Gating the
baseline write on the overall verdict froze it at the pre-incident value and
turned one denial burst into an alarm that could never clear — a permanently
screaming sentinel is an ignored sentinel. Recovery is automatic: once the
denial count stops growing, check 3 goes green. It never launders a real
outage, because checks 1 and 2 (service loaded, process alive) are
independent and unaffected by the baseline.

``--dry-run`` runs every check and prints the verdict but writes nothing
(no receipt, no baseline update). The exit code still reflects the verdict
so the flag is usable as a manual probe.

OPERATOR WIRING (do not automate — ``~/.dharma/cron/jobs.json`` is operator
authority; a human adds this object to the ``jobs`` array by hand):

  {"id": "organism_liveness_sentinel", "name": "Organism Liveness Sentinel",
   "handler": "shell", "enabled": true, "deliver": "local",
   "shell_command": "python3 scripts/runtime/organism_liveness_sentinel.py",
   "schedule": {"kind": "interval", "minutes": 30, "display": "every 30m"},
   "timeout_sec": 60, "urgent": true,
   "prompt": "Fail loudly if the organism launchd service, orchestrate-live process, or admission lane is dead."}

The ``shell_command`` above is the exact string the cron shell handler
allowlists (``cron_runner._ALLOWED_SHELL_COMMAND_PREFIXES``); it is run with
cwd=repo root, hence the relative path. An absolute-interpreter spelling is
rejected before launch, so do not "improve" it into one.
``tests/test_cron_runner.py`` parses this docstring and runs the command
through the real handler, so the documented wiring cannot rot.

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

# Every spelling the organism is actually launched under. Sources:
#   com.dharma.swarm.plist            -> exec env ... dgc orchestrate-live
#   dharma_swarm_release_runner.sh    -> python -B -I -m dharma_swarm.runtime_release_entrypoint orchestrate-live
#   Dockerfile.swarm / container CMD  -> python -m dharma_swarm.orchestrate_live
# Matching only the module form made a plist-started (i.e. the normal) host
# scan as dead, which would have made this sentinel a liar on the very
# machine it was written for. tests/test_runtime_command_forms.py pins these
# against the real launch definitions.
#
# This script stays stdlib-only and imports nothing from dharma_swarm on
# purpose: a watchdog that cannot start when the package it watches is broken
# is not a watchdog. The mirrored constant in
# dharma_swarm/runtime_process_identity.py is kept honest by that test.
ORCHESTRATE_COMMAND_FORMS: tuple[str, ...] = (
    "dgc orchestrate-live",
    "dharma_swarm.runtime_release_entrypoint orchestrate-live",
    "dharma_swarm.dgc_cli orchestrate-live",
    "dharma_swarm.orchestrate_live",
)
_SKIP_MARKERS: tuple[str, ...] = (
    "organism_liveness_sentinel",
    "ps -axo",
    "pgrep",
    "grep ",
    "pytest",
    "dgc doctor",
)
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
    ok: bool | None
    detail: str
    evidence: dict[str, object] = field(default_factory=dict)


def _verdict_ok(checks: list[CheckResult]) -> bool:
    """True only when every EVIDENCE-BEARING check passed.

    ``ok is None`` means the probe could not run, which is not proof of
    health and not proof of death — it is excluded from the verdict. The
    no-evidence-at-all case is fail-closed on purpose: silence about every
    check is exactly the quiet PASS this sentinel exists to abolish.
    """
    evidence = [c for c in checks if c.ok is not None]
    if not evidence:
        return False
    return all(c.ok for c in evidence)


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
        # The probe never ran: no launchctl (Linux/container) or it stalled.
        # Not evidence of a dead service — see the module docstring.
        return CheckResult(
            name="launchd_service",
            ok=None,
            detail=f"launchctl probe could not run ({exc}) — no evidence either way",
            evidence={"target": target, "state": "unknown"},
        )
    stderr = (proc.stderr or "").strip()
    if proc.returncode != 0 and "could not find service" in stderr.lower():
        # The probe RAN and answered "that service is not here". This is the
        # 2026-07-28 bootout shape and stays a loud FAIL. Measured on macOS:
        #   launchctl print gui/501/com.dharma.swarm
        #     -> rc=113  Could not find service "..." in domain for user gui: 501
        return CheckResult(
            name="launchd_service",
            ok=False,
            detail=f"service {target} is NOT loaded (launchctl rc={proc.returncode})",
            evidence={
                "target": target,
                "state": "absent",
                "stderr": stderr[:400],
            },
        )
    if proc.returncode != 0:
        # A nonzero rc that is NOT "no such service" is an answer about the
        # DOMAIN, not about the organism. Measured on macOS:
        #   launchctl print gui/99999/com.dharma.swarm
        #     -> rc=112  Could not find domain for user gui: 99999
        # A caller outside the GUI session (ssh, system-context daemon) gets
        # exactly this, and reading it as "the service is gone" was a false
        # death certificate. Non-evidence; check 2 is the authority on
        # liveness and stays fail-closed.
        return CheckResult(
            name="launchd_service",
            ok=None,
            detail=(
                f"launchctl rc={proc.returncode} for {target}: {stderr[:200]} "
                "— probe answered about the domain, not the service; no evidence either way"
            ),
            evidence={"target": target, "state": "unknown", "stderr": stderr[:400]},
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
        evidence={
            "target": target,
            "pid": pid,
            "state": "loaded",
            "launchd_state": state,
        },
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


def scan_orchestrate_processes() -> tuple[list[tuple[int, str]], str | None]:
    """Return ([(pid, command)], error) for every orchestrate-live spelling.

    ``ps -axo pid=,command=`` with substring matching rather than
    ``pgrep -f <regex>``: the alternation needed to cover all launch forms is
    not portable across pgrep's regex flavours, and the full command line is
    itself the evidence a receipt should carry.
    """
    try:
        proc = subprocess.run(
            ["ps", "-axo", "pid=,command="],
            capture_output=True,
            text=True,
            timeout=15,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return [], f"ps probe failed to execute: {exc}"
    if proc.returncode != 0:
        return [], f"ps probe returned rc={proc.returncode}"

    current_pid = os.getpid()
    matches: list[tuple[int, str]] = []
    for raw in proc.stdout.splitlines():
        parts = raw.strip().split(maxsplit=1)
        if len(parts) != 2:
            continue
        try:
            pid = int(parts[0])
        except ValueError:
            continue
        command = parts[1]
        if pid == current_pid:
            continue
        if not any(form in command for form in ORCHESTRATE_COMMAND_FORMS):
            continue
        if any(marker in command for marker in _SKIP_MARKERS):
            continue
        matches.append((pid, command))
    return matches, None


def check_orchestrate_process(launchd_pid: int | None) -> CheckResult:
    found, error = scan_orchestrate_processes()
    if error is not None:
        # DELIBERATE ASYMMETRY with check 1, do not "make this consistent".
        # A missing launchctl is a structural property of a non-macOS host and
        # says nothing about the organism, so it is `unknown`. An unreadable
        # PROCESS TABLE is different: it is the single fact this sentinel
        # exists to establish, and being blind to it is not health. If this
        # branch were also `unknown`, a host with neither launchctl nor ps
        # (verified: `python:3.12-slim` ships neither) would leave only the
        # denial counter — which passes on an empty log — and the sentinel
        # would report OK while knowing nothing at all. Fail closed.
        # test_ps_probe_failure_is_fail_closed_not_unknown pins this.
        return CheckResult(
            name="orchestrate_process",
            ok=False,
            detail=f"{error} — cannot see the process table, refusing to report health",
        )
    live = [pid for pid, _ in found if _pid_alive(pid)]
    if not live:
        return CheckResult(
            name="orchestrate_process",
            ok=False,
            detail=(
                "no live process matches any orchestrate-live command form "
                f"{list(ORCHESTRATE_COMMAND_FORMS)}"
            ),
            evidence={"scanned_pids": [pid for pid, _ in found]},
        )
    evidence: dict[str, object] = {
        "live_pids": live,
        "commands": [cmd for pid, cmd in found if pid in live][:4],
    }
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


def _record_denial_baseline(
    baseline_path: Path,
    *,
    denial_count: object,
    observed_at: str,
    verdict: str,
) -> None:
    """Persist the last observed denial count (pass or fail)."""
    baseline_path.write_text(
        json.dumps(
            {
                "denial_count": denial_count,
                "updated_at": observed_at,
                "observed_under_verdict": verdict,
            }
        )
        + "\n"
    )


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
    # `ok is True` only: an unknown (ok is None) probe carries no pid to
    # cross-check against, and neither does an absent service.
    launchd_pid = service.evidence.get("pid") if service.ok is True else None
    process = check_orchestrate_process(
        launchd_pid if isinstance(launchd_pid, int) else None
    )
    denials = check_admission_denials(log_path, baseline_path)

    checks = [service, process, denials]
    ok = _verdict_ok(checks)
    non_evidence = [c.name for c in checks if c.ok is None]
    verdict = {
        "sentinel": "organism_liveness_sentinel",
        "timestamp_utc": _utc_now(),
        "verdict": "OK" if ok else "ORGANISM_DOWN",
        "dry_run": dry_run,
        "non_evidence_checks": non_evidence,
        "checks": [asdict(c) for c in checks],
    }
    print(json.dumps(verdict, indent=2))
    if non_evidence:
        # Visible without being fatal: a probe that cannot run is a real gap
        # in coverage, just not a death certificate.
        print(
            "SENTINEL NOTICE: no evidence from " + ", ".join(non_evidence),
            file=sys.stderr,
        )

    if dry_run:
        return 0 if ok else 1

    sentinel_dir.mkdir(parents=True, exist_ok=True)
    # Record the last OBSERVED denial count on every non-dry run, pass or
    # fail. Gating this on `ok` froze the baseline at the pre-incident value,
    # so one burst re-fired forever and the sentinel could never return to
    # green on its own. The comparison is between consecutive observations:
    # a still-growing denial loop fails again next run, a stopped one clears.
    _record_denial_baseline(
        baseline_path,
        denial_count=denials.evidence.get("denial_count", 0),
        observed_at=str(verdict["timestamp_utc"]),
        verdict=str(verdict["verdict"]),
    )
    if ok:
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
