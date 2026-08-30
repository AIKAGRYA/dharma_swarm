"""Swarm lifecycle commands (up, down, swarm, stress, probe)."""

from __future__ import annotations

from pathlib import Path
import argparse
import asyncio
import json
import os
import signal
import subprocess
import sys

from dharma_swarm.runtime_admission import runtime_admission_or_exit
from dharma_swarm.terminal_commands._helpers import (
    DGC_CORE,
    DHARMA_STATE,
    DHARMA_SWARM,
    _first_daemon_like_process,
    _pid_alive,
    _tail,
)


def cmd_up(background: bool = False) -> None:
    """Start the dharma_swarm daemon (pulse heartbeat loop)."""
    pid_file = DHARMA_STATE / "daemon.pid"
    if pid_file.exists():
        try:
            pid = int(pid_file.read_text().strip())
            os.kill(pid, 0)  # Check if running
            print(f"Daemon already running (PID {pid})")
            return
        except (ValueError, OSError):
            pid_file.unlink(missing_ok=True)

    live_process = _first_daemon_like_process()
    if live_process is not None:
        pid, _command = live_process
        print(f"Daemon already running (PID {pid})")
        return

    # parents[2] = the repo root; parent.parent is the *package* dir
    # (dharma_swarm/), which made daemon_script a nonexistent path and
    # `dgc up --background` print success while launching nothing.
    repo_root = Path(__file__).resolve().parents[2]
    daemon_script = repo_root / "run_daemon.sh"
    if not daemon_script.exists():
        raise SystemExit(f"run_daemon.sh not found at {daemon_script}")
    env = os.environ.copy()
    env["MISSION_PREFLIGHT"] = "0"  # Skip preflight for direct launch

    if background:
        import subprocess
        proc = subprocess.Popen(
            ["bash", str(daemon_script)],
            env=env,
            cwd=str(repo_root),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        print(f"Daemon started in background (PID {proc.pid})")
    else:
        os.execvpe("bash", ["bash", str(daemon_script)], env)


def cmd_down() -> None:
    """Stop the daemon."""
    pid_file = DHARMA_STATE / "daemon.pid"
    if pid_file.exists():
        try:
            pid = int(pid_file.read_text().strip())
        except ValueError:
            print("Corrupted PID file, removing")
            pid_file.unlink()
            return
        try:
            os.kill(pid, signal.SIGTERM)
            print(f"Sent SIGTERM to daemon (PID {pid})")
        except OSError:
            print(f"Daemon PID {pid} not found (stale)")
            pid_file.unlink()
    else:
        print("Daemon not running (no PID file)")


def cmd_orchestrate_live(background: bool = False) -> None:
    """Run all DGC systems concurrently (live orchestrator)."""

    pid_file = DHARMA_STATE / "daemon.pid"
    legacy_pid_file = DHARMA_STATE / "orchestrator.pid"
    for candidate in (pid_file, legacy_pid_file):
        if not candidate.exists():
            continue
        try:
            pid = int(candidate.read_text().strip())
            os.kill(pid, 0)
            print(f"Orchestrator already running (PID {pid})")
            return
        except (ValueError, OSError):
            candidate.unlink(missing_ok=True)

    live_process = _first_daemon_like_process()
    if live_process is not None:
        pid, _command = live_process
        print(f"Orchestrator already running (PID {pid})")
        return

    runtime_admission_or_exit()

    if background:
        import subprocess as sp
        legacy_pid_file.unlink(missing_ok=True)
        proc = sp.Popen(
            [sys.executable, "-m", "dharma_swarm.orchestrate_live", "--background"],
            stdout=sp.DEVNULL,
            stderr=sp.DEVNULL,
            start_new_session=True,
        )
        print(f"Orchestrator started in background (PID {proc.pid})")
    else:
        from dharma_swarm.orchestrate_live import orchestrate
        asyncio.run(orchestrate())


# ---------------------------------------------------------------------------
# Swarm command (with overnight / yolo / live subcommands)
# ---------------------------------------------------------------------------

def cmd_swarm(extra_args: list[str]) -> None:
    """Run the dharma_swarm orchestrator with subcommands."""
    scripts = DHARMA_SWARM / "scripts"
    start_script = scripts / "start_overnight.sh"
    stop_script = scripts / "stop_overnight.sh"
    codex_start_script = scripts / "start_codex_overnight_tmux.sh"
    codex_status_script = scripts / "status_codex_overnight_tmux.sh"
    codex_stop_script = scripts / "stop_codex_overnight_tmux.sh"
    run_file = DHARMA_STATE / "overnight_run_dir.txt"
    codex_run_file = DHARMA_STATE / "codex_overnight_run_dir.txt"
    pid_files = {
        "overnight": DHARMA_STATE / "overnight.pid",
        "daemon": DHARMA_STATE / "daemon.pid",
        "sentinel": DHARMA_STATE / "sentinel.pid",
    }

    def _overnight(args: list[str]) -> None:
        action = args[0] if args else "status"

        if action == "start":
            hours = "8"
            aggressive = False
            for a in args[1:]:
                if a in ("--aggressive", "--yolo", "--caffeine"):
                    aggressive = True
                    continue
                try:
                    float(a)
                    hours = a
                except ValueError:
                    pass

            env = os.environ.copy()
            if aggressive:
                env.update({
                    "POLL_SECONDS": "120",
                    "MIN_PENDING": "12",
                    "TASKS_PER_LOOP": "5",
                    "QUALITY_EVERY_LOOPS": "10",
                })
                if hours == "8":
                    hours = "10"

            proc = subprocess.run(
                ["bash", str(start_script), hours],
                capture_output=True, text=True, env=env,
            )
            if proc.stdout:
                print(proc.stdout.strip())
            if proc.stderr:
                print(proc.stderr.strip(), file=sys.stderr)
            if proc.returncode != 0:
                sys.exit(proc.returncode)
            return

        if action == "stop":
            proc = subprocess.run(
                ["bash", str(stop_script)], capture_output=True, text=True,
            )
            if proc.stdout:
                print(proc.stdout.strip())
            if proc.stderr:
                print(proc.stderr.strip(), file=sys.stderr)
            if proc.returncode != 0:
                sys.exit(proc.returncode)
            return

        if action in ("status", "state"):
            print("=== Swarm Overnight Status ===")
            if run_file.exists():
                run_dir = Path(run_file.read_text().strip())
                print(f"run_dir: {run_dir}")
                report = run_dir / "report.md"
                if report.exists():
                    print("\n--- report tail ---")
                    print(_tail(report, lines=40))
            else:
                print("run_dir: n/a")

            print("\n--- processes ---")
            for label, pf in pid_files.items():
                if not pf.exists():
                    print(f"{label}: missing pid file")
                    continue
                try:
                    pid = int(pf.read_text().strip())
                except Exception:
                    print(f"{label}: invalid pid file")
                    continue
                alive = _pid_alive(pid)
                print(f"{label}: pid={pid} alive={alive}")
                if alive:
                    ps = subprocess.run(
                        ["ps", "-p", str(pid), "-o", "pid=,etime=,command="],
                        capture_output=True, text=True,
                    )
                    if ps.stdout.strip():
                        print("  " + ps.stdout.strip())
            return

        if action in ("report", "logs"):
            if not run_file.exists():
                print("No overnight run metadata found.")
                return
            run_dir = Path(run_file.read_text().strip())
            report = run_dir / "report.md"
            log = run_dir / "autopilot.log"
            print(f"run_dir: {run_dir}\n")
            if report.exists():
                print("--- report tail ---")
                print(_tail(report, lines=80))
            if log.exists():
                print("\n--- autopilot log tail ---")
                print(_tail(log, lines=80))
            return

        print(
            "Usage:\n"
            "  dgc swarm overnight start [HOURS] [--aggressive]\n"
            "  dgc swarm overnight stop\n"
            "  dgc swarm overnight status\n"
            "  dgc swarm overnight report\n"
        )

    def _codex_night(args: list[str]) -> None:
        action = args[0] if args else "status"

        if action in ("start", "yolo"):
            parser = argparse.ArgumentParser(add_help=False)
            parser.add_argument("hours", nargs="?", default="10" if action == "yolo" else "8")
            parser.add_argument("--yolo", action="store_true")
            parser.add_argument("--model", default="")
            parser.add_argument("--mission-file", default="")
            parser.add_argument("--max-cycles", type=int, default=0)
            parser.add_argument("--poll-seconds", type=int, default=0)
            parser.add_argument("--cycle-timeout", type=int, default=0)
            parser.add_argument("--state-dir", default="")
            parser.add_argument("--label", default="")
            parsed = parser.parse_args(args[1:])

            env = os.environ.copy()
            if action == "yolo" or parsed.yolo:
                env["DGC_CODEX_NIGHT_YOLO"] = "1"
            if parsed.model:
                env["DGC_CODEX_NIGHT_MODEL"] = parsed.model
            if parsed.mission_file:
                env["DGC_CODEX_NIGHT_MISSION_FILE"] = parsed.mission_file
            if parsed.max_cycles > 0:
                env["MAX_CYCLES"] = str(parsed.max_cycles)
            if parsed.poll_seconds > 0:
                env["POLL_SECONDS"] = str(parsed.poll_seconds)
            if parsed.cycle_timeout > 0:
                env["CYCLE_TIMEOUT"] = str(parsed.cycle_timeout)
            if parsed.state_dir:
                env["DGC_CODEX_NIGHT_STATE_DIR"] = parsed.state_dir
            if parsed.label:
                env["DGC_CODEX_NIGHT_LABEL"] = parsed.label

            proc = subprocess.run(
                ["bash", str(codex_start_script), parsed.hours],
                capture_output=True,
                text=True,
                env=env,
            )
            if proc.stdout:
                print(proc.stdout.strip())
            if proc.stderr:
                print(proc.stderr.strip(), file=sys.stderr)
            if proc.returncode != 0:
                sys.exit(proc.returncode)
            return

        if action == "stop":
            proc = subprocess.run(
                ["bash", str(codex_stop_script)],
                capture_output=True,
                text=True,
            )
            if proc.stdout:
                print(proc.stdout.strip())
            if proc.stderr:
                print(proc.stderr.strip(), file=sys.stderr)
            if proc.returncode != 0:
                sys.exit(proc.returncode)
            return

        if action in ("status", "state"):
            proc = subprocess.run(
                ["bash", str(codex_status_script)],
                capture_output=True,
                text=True,
            )
            if proc.stdout:
                print(proc.stdout.strip())
            if proc.stderr:
                print(proc.stderr.strip(), file=sys.stderr)
            if proc.returncode != 0:
                sys.exit(proc.returncode)
            return

        if action in ("report", "logs"):
            if not codex_run_file.exists():
                print("No Codex overnight run metadata found.")
                return
            run_dir = Path(codex_run_file.read_text().strip())
            report = run_dir / "report.md"
            latest_output = run_dir / "latest_last_message.txt"
            manifest = run_dir / "run_manifest.json"
            handoff = run_dir / "morning_handoff.md"
            print(f"run_dir: {run_dir}\n")
            if manifest.exists():
                print("--- run manifest ---")
                print(_tail(manifest, lines=80))
            if report.exists():
                print("\n--- report tail ---")
                print(_tail(report, lines=80))
            if latest_output.exists():
                print("\n--- latest last message ---")
                print(_tail(latest_output, lines=80))
            if handoff.exists():
                print("\n--- morning handoff ---")
                print(_tail(handoff, lines=80))
            return

        print(
            "Usage:\n"
            "  dgc swarm codex-night start [HOURS] [--yolo] [--mission-file PATH] [--model MODEL]\n"
            "  dgc swarm codex-night yolo [HOURS]\n"
            "  dgc swarm codex-night stop\n"
            "  dgc swarm codex-night status\n"
            "  dgc swarm codex-night report\n"
        )

    # --- Dispatch subcommands ---

    if extra_args and extra_args[0] == "yolo":
        _codex_night(["yolo"])
        return

    if extra_args and extra_args[0] in ("codex-night", "codex-overnight"):
        _codex_night(extra_args[1:])
        return

    if extra_args and extra_args[0] in ("overnight", "autopilot"):
        _overnight(extra_args[1:])
        return

    if "--status" in extra_args or (extra_args and extra_args[0] in ("status", "state")):
        state_file = DHARMA_STATE / "orchestrator_state.json"
        if state_file.exists():
            state = json.loads(state_file.read_text())
            print("=== DHARMA SWARM Orchestrator State ===")
            for k, v in state.items():
                print(f"  {k}: {v}")
        else:
            print("No orchestrator state yet. Run: dgc swarm")
        return

    if "live" in extra_args:
        live_script = DHARMA_SWARM / "swarm_live.sh"
        num = "3"
        for a in extra_args:
            if a.isdigit():
                num = a
        os.execvp("bash", ["bash", str(live_script), num])
        return

    # Default: run orchestrator with optional plan name
    from dharma_swarm.orchestrate import run as orchestrate_run

    plan_name = None
    for a in extra_args:
        if a in ("build", "research", "maintenance", "deploy"):
            plan_name = a
    orchestrate_run(plan_name)


def cmd_stress(
    profile: str,
    state_dir: str,
    provider_mode: str,
    agents: int,
    tasks: int,
    evolutions: int,
    evolution_concurrency: int,
    cli_rounds: int,
    cli_concurrency: int,
    orchestration_timeout_sec: int,
    external_research: bool,
    external_timeout_sec: int,
) -> None:
    """Run the max-capacity stress harness."""
    harness = DHARMA_SWARM / "scripts" / "dgc_max_stress.py"
    if not harness.exists():
        print(f"Stress harness not found: {harness}")
        raise SystemExit(2)

    cmd = [
        sys.executable,
        str(harness),
        "--profile",
        profile,
        "--state-dir",
        state_dir,
        "--provider-mode",
        provider_mode,
        "--agents",
        str(agents),
        "--tasks",
        str(tasks),
        "--evolutions",
        str(evolutions),
        "--evolution-concurrency",
        str(evolution_concurrency),
        "--cli-rounds",
        str(cli_rounds),
        "--cli-concurrency",
        str(cli_concurrency),
        "--orchestration-timeout-sec",
        str(orchestration_timeout_sec),
        "--external-timeout-sec",
        str(external_timeout_sec),
    ]
    if external_research:
        cmd.append("--external-research")

    print("Running DGC max stress harness...")
    proc = subprocess.run(cmd, cwd=str(DHARMA_SWARM))
    if proc.returncode != 0:
        raise SystemExit(proc.returncode)


def cmd_full_power_probe(
    route_task: str,
    context_search_query: str,
    compose_task: str,
    autonomy_action: str,
    skip_sprint_probe: bool,
    skip_stress: bool,
    skip_pytest: bool,
) -> None:
    """Run the operator-facing full-power probe and emit artifact paths."""
    from dharma_swarm.full_power_probe import run_full_power_probe

    payload = run_full_power_probe(
        python_executable=sys.executable,
        route_task=route_task,
        context_search_query=context_search_query,
        compose_task=compose_task,
        autonomy_action=autonomy_action,
        include_sprint_probe=not skip_sprint_probe,
        run_stress=not skip_stress,
        run_pytest=not skip_pytest,
    )
    print(f"Report: {payload['report_markdown_path']}")
    print(f"JSON:   {payload['report_json_path']}")


# ---------------------------------------------------------------------------
# Commands from dharma_swarm Typer CLI
# ---------------------------------------------------------------------------


def cmd_setup() -> None:
    """Install dependencies and configure."""
    setup_script = DGC_CORE / "setup.sh"
    if setup_script.exists():
        os.execvp("bash", ["bash", str(setup_script)])
    else:
        print(f"Setup script not found: {setup_script}")


# ---------------------------------------------------------------------------
# Swarm command (with overnight / yolo / live subcommands)
# ---------------------------------------------------------------------------


def cmd_migrate() -> None:
    """Migrate old DGC memory to new system."""
    sys.path.insert(0, str(DGC_CORE / "memory"))
    try:
        from strange_loop import migrate_from_old_dgc  # type: ignore[import-untyped]
        migrate_from_old_dgc()
    except ImportError:
        print("Migration module not available.")
    finally:
        sys.path.pop(0)
