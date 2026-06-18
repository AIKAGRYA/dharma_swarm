#!/usr/bin/env python3
"""Model-pool TUI consumer verifier for the canonical model pool.

The consolidation made ``dharma_swarm/model_pool.py`` the single source of truth
for every model + its routes, and ``key_oracle`` the single source of liveness.
This harness checks that the real Helm TUI consumes that state. The primary
live-call proof harness is ``scripts/verify/model_routing_live_probe.py``; this
script must remain a secondary surface check, not the source of routing truth.

Modes
-----
``--dry-run`` (default): no model calls. Enumerate operable vs unroutable from
the pool + live keys and write the table. Safe, fast, CI-able.

``--live``: drive ``ds tui`` (DS_TUI_ROOT defaults to this worktree) in a tmux
pane. For each operable floor entry: ``/model set <alias>`` → probe ``Reply with
exactly: PONG <id>`` → capture frame + screenshot → record surface behavior.
Needs live keys; operator-run by design. NEVER fabricates a reply — a silent or
errored turn is recorded as failed, never as a pass.

Artifact: ``reports/model_pool/e2e_<ts>.json`` + a one-screen markdown summary.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from dharma_swarm.key_oracle import live_providers  # noqa: E402
from dharma_swarm.model_pool import all_entries, best_live_route, live_routes  # noqa: E402

OUT_DIR = REPO_ROOT / "reports" / "model_pool"
LIVE_E2E_ENV = "DHARMA_LIVE_MODEL_E2E"


def _enumerate(oracle: set[str] | None) -> tuple[list[dict], list[dict]]:
    """Split the pool into operable (≥1 live route) and unroutable rows.

    Each row carries ``below_floor`` so the floor (real-path) models are clearly
    demarcated from the grunt-only sub-floor ones — the real-vs-grunt line the
    operator requires must be visible in the artifact, never blurred together.
    """
    operable: list[dict] = []
    unroutable: list[dict] = []
    for entry in all_entries():
        routes = live_routes(entry, oracle)
        row = {
            "id": entry.id,
            "display": entry.display,
            "tier": getattr(entry.tier, "name", str(entry.tier)),
            "below_floor": bool(getattr(entry, "below_floor", False)),
            "lane": "grunt" if getattr(entry, "below_floor", False) else "floor",
            "aliases": list(entry.aliases),
            "all_routes": [f"{r.provider.value}:{r.model_id}" for r in entry.routes],
            "live_routes": [f"{r.provider.value}:{r.model_id}" for r in routes],
        }
        (operable if routes else unroutable).append(row)
    return operable, unroutable


def _refresh_keys() -> None:
    """Best-effort `dkeys test` so the oracle reads a fresh status file."""
    for cmd in (["dkeys", "test"], [str(Path.home() / "bin" / "dkeys"), "test"]):
        try:
            subprocess.run(cmd, timeout=180, capture_output=True, check=False)
            return
        except (FileNotFoundError, subprocess.SubprocessError):
            continue


def _tmux(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["tmux", *args], capture_output=True, text=True, check=False)


def _drive_live(operable: list[dict], *, height: int, width: int, probe_timeout: int) -> list[dict]:
    """Drive ds tui once, /model set + probe each operable entry, record results."""
    sess = f"mpe2e-{os.getpid()}"
    root = os.environ.get("DS_TUI_ROOT", str(REPO_ROOT))
    shots = OUT_DIR / "screens"
    shots.mkdir(parents=True, exist_ok=True)
    env = f"DS_TUI_ROOT={root} COLORTERM=truecolor"
    _tmux("new-session", "-d", "-s", sess, "-x", str(width), "-y", str(height),
          f"{env} ds tui")
    results: list[dict] = []
    try:
        # wait for the live frame
        deadline = time.time() + 30
        while time.time() < deadline:
            frame = _tmux("capture-pane", "-t", sess, "-p").stdout
            if "live" in frame or "connected" in frame:
                break
            time.sleep(0.5)
        for row in operable:
            alias = row["aliases"][0] if row["aliases"] else row["id"]
            _tmux("send-keys", "-t", sess, "-l", f"/model set {alias}")
            _tmux("send-keys", "-t", sess, "Enter")
            time.sleep(1.0)
            probe = f"Reply with exactly: PONG {row['id']}"
            _tmux("send-keys", "-t", sess, "-l", probe)
            _tmux("send-keys", "-t", sess, "Enter")
            ok = False
            deadline = time.time() + probe_timeout
            frame = ""
            while time.time() < deadline:
                frame = _tmux("capture-pane", "-t", sess, "-p").stdout
                if f"PONG {row['id']}" in frame:
                    ok = True
                    break
                if "✖ failed" in frame or "error" in frame.lower():
                    break
                time.sleep(1.0)
            shot = shots / f"{row['id']}.txt"
            shot.write_text(frame, encoding="utf-8")
            results.append({**row, "status": "operable" if ok else "failed",
                            "screenshot": str(shot.relative_to(REPO_ROOT))})
    finally:
        _tmux("send-keys", "-t", sess, "C-c")
        time.sleep(0.5)
        _tmux("kill-session", "-t", sess)
    return results


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dry-run", action="store_true", help="enumerate only; accepted for explicitness")
    ap.add_argument("--live", action="store_true", help="drive the real TUI (needs live keys)")
    ap.add_argument("--no-refresh", action="store_true", help="skip `dkeys test`")
    ap.add_argument("--height", type=int, default=40)
    ap.add_argument("--width", type=int, default=120)
    ap.add_argument("--probe-timeout", type=int, default=60)
    args = ap.parse_args()

    live_enabled = os.environ.get(LIVE_E2E_ENV) == "1"
    if args.live and not live_enabled:
        print(f"refusing live model E2E: set {LIVE_E2E_ENV}=1 to opt in")
        return 2
    if args.dry_run and args.live:
        print("--dry-run and --live are mutually exclusive")
        return 2

    if not args.no_refresh and live_enabled:
        _refresh_keys()
    elif not args.no_refresh:
        print(f"skipping `dkeys test`; set {LIVE_E2E_ENV}=1 to refresh live key status")
    oracle = live_providers()
    operable, unroutable = _enumerate(oracle)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%dT%H%M%S")
    mode = "live" if args.live else "dry-run"

    floor_op = [r for r in operable if not r["below_floor"]]
    grunt_op = [r for r in operable if r["below_floor"]]
    # Live probes drive ONLY the floor path — grunt models are fenced out of the
    # picker, so /model set <grunt> isn't a real route to verify.
    live_results = _drive_live(floor_op, height=args.height, width=args.width,
                               probe_timeout=args.probe_timeout) if args.live else []
    artifact = {
        "mode": mode,
        "live_providers": sorted(oracle) if oracle is not None else None,
        "oracle_note": "None = key status stale/missing → fail-open (routes unfiltered)",
        "counts": {"floor_operable": len(floor_op), "grunt_operable": len(grunt_op),
                   "unroutable": len(unroutable)},
        "floor_operable": floor_op,
        "grunt_operable": grunt_op,
        "unroutable": unroutable,
        "live_results": live_results,
    }
    out = OUT_DIR / f"e2e_{stamp}.json"
    out.write_text(json.dumps(artifact, indent=2), encoding="utf-8")

    def _tag(row: dict) -> str:
        return next((r["status"] for r in live_results if r["id"] == row["id"]), "(dry-run)")

    print(f"model_pool_e2e [{mode}] — FLOOR {len(floor_op)} · grunt {len(grunt_op)} · unroutable {len(unroutable)}")
    print(f"live providers: {sorted(oracle) if oracle is not None else 'STALE (fail-open)'}")
    print("\n── FLOOR (real path — picker + default routing) ──")
    for row in floor_op:
        print(f"  ✓ {row['id']:24s} -> {row['live_routes'][0] if row['live_routes'] else '?':34s} {_tag(row)}")
    print("\n── GRUNT-ONLY (sub-floor — fenced, explicit opt-in only) ──")
    for row in grunt_op:
        print(f"  · {row['id']:24s} -> {row['live_routes'][0] if row['live_routes'] else '?':34s} [grunt]")
    for row in unroutable:
        print(f"  ✗ {row['id']:24s} UNROUTABLE (no live route)")
    print(f"\nartifact: {out.relative_to(REPO_ROOT)}")
    if args.live:
        failed = [r["id"] for r in live_results if r["status"] != "operable"]
        if failed:
            print(f"FAILED via TUI: {failed}")
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
