#!/usr/bin/env python3
"""Record one raw Helm P4 measurement for the strict composer.

The composer (``helm_perf_soak.py``) refuses to launch anything; this runner is
the operator-controlled half that drives the real launcher on an explicit
private ``CODEX_MANAGED_*`` tmux socket, samples timings and soak growth, walks
the stop -> start -> replay-valid rollback shape, and takes provider-turn
timings from the offline stub bridge only. It never dispatches a live provider
turn and never touches the default tmux socket.

Metric semantics: ``intent_parse_ms`` is a navigation-intent round trip, timed
from the Enter keypress (the draft is already typed and echoed) to the first
rendered frame change. It includes tmux input latency, so it is an upper bound
on parser latency, not a pure parser measurement.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import re
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

REPO = Path(__file__).resolve().parents[2]
SOCKET = "CODEX_MANAGED_p4perf"
STUB_SESSION = "p4stub"
LAUNCH_SESSION = "dharma_terminal_tui"
PROBE_TIMEOUT_S = 10.0


def _load_composer():
    spec = importlib.util.spec_from_file_location(
        "helm_perf_soak", Path(__file__).resolve().with_name("helm_perf_soak.py")
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _tmux(*args: str, timeout: float = 20.0) -> subprocess.CompletedProcess:
    env = {k: v for k, v in os.environ.items() if k != "TMUX"}
    env["TMUX_TMPDIR"] = "/tmp"
    return subprocess.run(
        ["tmux", "-L", SOCKET, "-f", "/dev/null", *args],
        capture_output=True, text=True, timeout=timeout, env=env,
    )


def _launcher(script: str) -> subprocess.CompletedProcess:
    env = {k: v for k, v in os.environ.items() if k not in ("TMUX", "DHARMA_TERMINAL_ROOT")}
    env["DHARMA_TERMINAL_TMUX_SOCKET"] = SOCKET
    return subprocess.run(
        ["bash", str(REPO / "scripts" / script)],
        capture_output=True, text=True, timeout=120, env=env, cwd=REPO,
    )


def _capture(target: str) -> str:
    out = _tmux("capture-pane", "-t", target, "-p")
    return out.stdout if out.returncode == 0 else ""


def _type_draft(target: str, text: str) -> None:
    _tmux("send-keys", "-t", target, "-l", text)
    time.sleep(0.3)


def _press_enter(target: str) -> None:
    _tmux("send-keys", "-t", target, "Enter")


def _send_line(target: str, text: str) -> None:
    _type_draft(target, text)
    _press_enter(target)


def _timed_intent(target: str, text: str, timeout_s: float) -> float:
    """Round trip from Enter to the first frame change; the typed draft is excluded."""
    _type_draft(target, text)
    baseline = _capture(target)
    t0 = time.perf_counter_ns()
    _press_enter(target)
    _wait_change(target, baseline, timeout_s)
    return (time.perf_counter_ns() - t0) / 1e6


def _wait_for(target: str, needle: str, timeout_s: float, absent_baseline: int = 0) -> float:
    start = time.perf_counter_ns()
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        if _capture(target).count(needle) > absent_baseline:
            return (time.perf_counter_ns() - start) / 1e6
        time.sleep(0.15)
    raise RuntimeError(f"timeout waiting for {needle!r} in {target}")


def _wait_change(target: str, baseline: str, timeout_s: float) -> float:
    """Latency until the rendered frame differs from ``baseline`` (marker-free)."""
    start = time.perf_counter_ns()
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        if _capture(target) != baseline:
            return (time.perf_counter_ns() - start) / 1e6
        time.sleep(0.12)
    raise RuntimeError(f"timeout waiting for frame change in {target}")


def _pane_pid(target: str) -> int:
    out = _tmux("display", "-pt", target, "#{pane_pid}")
    return int(out.stdout.strip())


def _probe(argv: list[str]) -> str:
    try:
        return subprocess.run(
            argv, capture_output=True, text=True, timeout=PROBE_TIMEOUT_S,
        ).stdout
    except (subprocess.TimeoutExpired, OSError):
        return ""


def _proc_stats(pid: int) -> tuple[int, int]:
    rss_kb = int(_probe(["ps", "-o", "rss=", "-p", str(pid)]).strip() or 0)
    fd_count = max(0, len(_probe(["lsof", "-p", str(pid)]).splitlines()) - 1)
    return rss_kb * 1024, fd_count


def _boot() -> float:
    start = time.perf_counter_ns()
    proc = _launcher("start_terminal_tui_tmux.sh")
    if proc.returncode != 0:
        raise RuntimeError(f"launcher failed rc={proc.returncode}: {proc.stderr[-400:]}")
    return (time.perf_counter_ns() - start) / 1e6


def _stop() -> tuple[int, float]:
    start = time.perf_counter_ns()
    proc = _launcher("stop_terminal_tui_tmux.sh")
    return proc.returncode, (time.perf_counter_ns() - start) / 1e6


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--journeys", type=int, default=24)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    composer = _load_composer()
    output = composer.validate_output_path(args.output)

    target = f"={LAUNCH_SESSION}:"
    boot_ms: list[float] = []
    intent_ms: list[float] = []
    render_ms: list[float] = []
    provider_ms: list[float] = []
    journeys: list[dict] = []
    rb: list[dict] = []
    soak_ms = 0.0

    # Clean slate on the private socket; every exit path below tears it down
    # again so a failed run never leaves a phantom seat for the doctor/census.
    _tmux("kill-server", timeout=10)
    try:
        soak_ms = _measure(
            target, boot_ms, intent_ms, render_ms, provider_ms, journeys, rb, args.journeys
        )
    finally:
        _tmux("kill-session", "-t", f"={STUB_SESSION}:", timeout=10)
        try:
            _stop()
        finally:
            _tmux("kill-server", timeout=10)

    measurement = {
        "schema_version": "dharma.helm.perf_soak_measurement.v1",
        "measurement_id": f"p4-{uuid4().hex[:12]}",
        "captured_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "clock": "perf_counter_ns",
        "tmux": {"socket": SOCKET, "session": LAUNCH_SESSION},
        "execution": {"offline": True, "network_attempted": False,
                      "provider_mode": "offline_stub"},
        "samples": {"boot_ms": boot_ms, "intent_parse_ms": intent_ms,
                    "provider_turn_ms": provider_ms, "render_ms": render_ms},
        "soak": {"duration_ms": soak_ms, "journeys": journeys},
        "rollback": {"steps": rb},
    }
    composer.parse_measurement_payload(measurement)
    output.write_text(json.dumps(measurement, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"boot_ms": boot_ms, "intent_roundtrip_ms_from_enter": intent_ms,
                      "provider_stub_ms": provider_ms, "render_ms": render_ms,
                      "soak_ms": soak_ms, "journey_failures":
                      sum(not j["ok"] for j in journeys),
                      "rollback": [s["observed_state"] for s in rb]}))
    return 0


def _measure(
    target: str,
    boot_ms: list[float],
    intent_ms: list[float],
    render_ms: list[float],
    provider_ms: list[float],
    journeys: list[dict],
    rb: list[dict],
    journey_count: int,
) -> float:
    boot_ms.append(_boot())
    rc, _ = _stop()
    if rc != 0:
        raise RuntimeError("interleaved stop failed")
    boot_ms.append(_boot())

    # Navigation intent round trip (Enter -> first frame change). The draft is
    # typed and echoed before the clock starts so harness typing latency and
    # the echo repaint never masquerade as parser time.
    for i in range(5):
        text = "open sessions" if i % 2 == 0 else "open the cockpit layout"
        intent_ms.append(_timed_intent(target, text, 15.0))

    # Render latency proxy: F2 toggles zen <-> cockpit; measure until the other
    # surface's marker paints.
    for _ in range(4):
        frame = _capture(target)
        t0 = time.perf_counter_ns()
        _tmux("send-keys", "-t", target, "F2")
        _wait_change(target, frame, 10.0)
        render_ms.append((time.perf_counter_ns() - t0) / 1e6)

    # Soak: repeated journeys with RSS/fd growth sampled from the pane process.
    # A journey is ok only when the intent itself produced a new frame after
    # Enter, so the counter measures the TUI and not the typing echo.
    pid = _pane_pid(target)
    soak_t0 = time.monotonic()
    for seq in range(1, journey_count + 1):
        ok = True
        try:
            text = "open sessions" if seq % 2 == 1 else "open the cockpit layout"
            _timed_intent(target, text, 15.0)
        except RuntimeError:
            ok = False
        rss, fd_count = _proc_stats(pid)
        journeys.append({"sequence": seq, "ok": ok, "rss_bytes": rss, "fd_count": fd_count})
    soak_ms = (time.monotonic() - soak_t0) * 1000.0

    # Rollback shape: stop (from live) -> start (from stopped) -> replay-valid.
    rc, elapsed = _stop()
    stopped = _tmux("has-session", "-t", target).returncode != 0
    rb.append({"sequence": 1, "action": "stop", "input_state": "live", "exit_code": rc,
               "elapsed_ms": elapsed, "observed_state": "stopped" if stopped else "unknown"})
    t0 = time.perf_counter_ns()
    try:
        _boot()
        rc2, live = 0, _tmux("has-session", "-t", target).returncode == 0
    except RuntimeError:
        rc2, live = 1, False
    rb.append({"sequence": 2, "action": "start", "input_state": "stopped", "exit_code": rc2,
               "elapsed_ms": (time.perf_counter_ns() - t0) / 1e6,
               "observed_state": "live" if live else "unknown"})
    t0 = time.perf_counter_ns()
    replay = "unknown"
    try:
        frame = _capture(target)
        _send_line(target, "open sessions")
        _wait_change(target, frame, 15.0)
        after = _capture(target)
        replay = (
            "replay_valid"
            if ("dgc-" in after or re.search(r"[1-9]\d*/\d+ sessions", after))
            else "replay_invalid"
        )
    except RuntimeError:
        replay = "replay_invalid"
    rb.append({"sequence": 3, "action": "replay-valid", "input_state": "live", "exit_code": 0,
               "elapsed_ms": (time.perf_counter_ns() - t0) / 1e6, "observed_state": replay})

    # Provider turns: offline stub bridge only (never a live provider).
    terminal_dir = REPO / "terminal"
    stub_cmd = (
        f"cd {terminal_dir} && COLORTERM=truecolor "
        f"STUB_BRIDGE_SCENARIO=navigator "
        f"DHARMA_PYTHON={terminal_dir}/scripts/stub_bridge.py bun run start"
    )
    _tmux("new-session", "-d", "-s", STUB_SESSION, stub_cmd)
    stub_target = f"={STUB_SESSION}:"
    _wait_for(stub_target, "bridge connected", 45.0)
    time.sleep(1.5)
    for i in range(3):
        _type_draft(stub_target, f"stub turn {i}")
        baseline = _capture(stub_target).count("■")
        t0 = time.perf_counter_ns()
        _press_enter(stub_target)
        _wait_for(stub_target, "■", 20.0, absent_baseline=baseline)
        provider_ms.append((time.perf_counter_ns() - t0) / 1e6)
    return soak_ms


if __name__ == "__main__":
    raise SystemExit(main())
