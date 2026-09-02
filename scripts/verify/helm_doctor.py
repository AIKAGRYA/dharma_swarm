#!/usr/bin/env python3
"""Read-only Helm health doctor: sockets, bridge, key freshness, seat truth.

Observes and reports; changes nothing. Exit 0 always in observe mode; with
``--strict`` exit 1 only when a check reports ``down``. ``unknown`` and a
``stale`` key cache are informational: absence or age of evidence is typed,
never punished.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import time
from pathlib import Path
from typing import Any

_SOCKET_DIR = Path("/tmp/tmux-{uid}".format(uid=os.getuid()))
_SOCKET_RE = re.compile(r"^CODEX_MANAGED_[A-Za-z0-9][A-Za-z0-9_-]*$")


_PROBE_TIMEOUT_S = 5.0


def _probe(argv: list[str], *, env: dict[str, str] | None = None) -> subprocess.CompletedProcess:
    """Run one read-only probe; a hang or missing binary reads as not-ok, never a crash."""
    try:
        return subprocess.run(
            argv, capture_output=True, text=True, timeout=_PROBE_TIMEOUT_S, env=env,
        )
    except (subprocess.TimeoutExpired, OSError) as exc:
        return subprocess.CompletedProcess(argv, returncode=124, stdout="", stderr=str(exc))


def _tmux(socket: str, *args: str) -> subprocess.CompletedProcess:
    env = {k: v for k, v in os.environ.items() if k != "TMUX"}
    env["TMUX_TMPDIR"] = "/tmp"
    return _probe(["tmux", "-L", socket, "-f", "/dev/null", *args], env=env)


def _descendants(pid: int) -> list[str]:
    rows: list[str] = []
    queue = [pid]
    seen: set[int] = set()
    while queue:
        parent = queue.pop()
        if parent in seen:
            continue
        seen.add(parent)
        out = _probe(["pgrep", "-P", str(parent)])
        for child in out.stdout.split():
            if not child.isdigit():
                continue
            queue.append(int(child))
            cmd = _probe(["ps", "-o", "command=", "-p", child]).stdout.strip()
            if cmd:
                rows.append(cmd)
    return rows


def observe_sessions() -> list[dict[str, Any]]:
    """Enumerate helm sessions on private CODEX_MANAGED_* sockets, read-only."""
    found: list[dict[str, Any]] = []
    if not _SOCKET_DIR.is_dir():
        return found
    for entry in sorted(_SOCKET_DIR.iterdir()):
        name = entry.name
        if not _SOCKET_RE.fullmatch(name):
            continue
        listing = _tmux(name, "list-panes", "-a", "-F",
                        "#{session_name}|#{pane_pid}|#{pane_dead}")
        if listing.returncode != 0:
            continue
        for row in listing.stdout.splitlines():
            session, pid, dead = (row.split("|") + ["", ""])[:3]
            if "terminal_tui" not in session and "helm" not in session:
                continue
            bridge = any(
                "dharma_swarm.terminal_bridge" in cmd
                for cmd in _descendants(int(pid or 0))
            ) if pid.isdigit() and dead == "0" else False
            found.append({
                "socket": name, "session": session,
                "pane_alive": dead == "0",
                "bridge": "live" if bridge else ("down" if dead == "0" else "unknown"),
            })
    return found


_LIVE_GLYPHS = frozenset({"✓", "oauth"})
_DEAD_GLYPHS = frozenset({"✗", "~", "·", "$"})


def _row_is_live(row: dict[str, Any]) -> bool:
    """Mirror dkeys' own verdict: the glyph is authoritative, status text is a fallback."""
    glyph = str(row.get("glyph", "")).strip()
    if glyph in _LIVE_GLYPHS:
        return True
    if glyph in _DEAD_GLYPHS:
        return False
    status = str(row.get("status", "")).strip().lower()
    return status.startswith("live") or "oauth" in status


def _rows(status: dict[str, Any]) -> dict[str, dict[str, Any]]:
    rows = status.get("rows")
    if isinstance(rows, dict):
        return {str(k): v for k, v in rows.items() if isinstance(v, dict)}
    if isinstance(rows, list):
        return {
            str(row.get("name") or row.get("provider") or row.get("id") or ""): row
            for row in rows
            if isinstance(row, dict) and (row.get("name") or row.get("provider") or row.get("id"))
        }
    return {}


def key_freshness(status: dict[str, Any] | None, *, now: float, ttl_s: float = 900.0) -> dict[str, Any]:
    """Classify the key oracle cache (dkeys keys_status.json): fresh / stale / unknown.

    ``stale`` is informational: dkeys only rewrites the cache on ``dkeys test``,
    so age past ``ttl_s`` means "re-test to be sure", not "down".
    """
    if not status or not isinstance(status.get("last_test_ts"), (int, float)):
        return {"state": "unknown", "detail": "no readable keys_status snapshot"}
    age = now - float(status["last_test_ts"])
    live = [name for name, row in _rows(status).items() if _row_is_live(row)]
    state = "fresh" if age <= ttl_s else "stale"
    return {"state": state, "age_seconds": round(age, 1),
            "live_providers": sorted(live),
            "detail": "run `dkeys test` to refresh" if state == "stale" else "within ttl"}


def _load_key_status() -> dict[str, Any] | None:
    path = Path.home() / ".dharma" / "keys_status.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else None
    except (OSError, ValueError):
        return None


def seat_truth(receipt_path: Path | None) -> dict[str, Any]:
    """Report the newest evaluator seat receipt, typed — never inferred."""
    if receipt_path is None or not receipt_path.is_file():
        return {"state": "unknown",
                "detail": "no evaluator seat receipt supplied; seats unverified"}
    try:
        data = json.loads(receipt_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"state": "unknown", "detail": "seat receipt unreadable"}
    verified = data.get("on_call_count")
    rows = data.get("route_verifications")
    total = len(rows) if isinstance(rows, list) else None
    if not isinstance(verified, int) or not isinstance(total, int):
        return {"state": "unknown", "detail": "seat receipt lacks typed counts"}
    return {"state": "reported", "verified": verified, "total": total,
            "evaluator_state": data.get("state"), "receipt": str(receipt_path)}


def build_report(*, sessions: list[dict[str, Any]], keys: dict[str, Any],
                 seats: dict[str, Any]) -> dict[str, Any]:
    checks_down = any(s["bridge"] == "down" for s in sessions)
    return {
        "schema_version": "dharma.helm.doctor.v1",
        "observed_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "authority": "READ_ONLY_OBSERVATION",
        "sessions": sessions,
        "key_oracle": keys,
        "seats": seats,
        "attention_needed": bool(checks_down),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seat-receipt", type=Path, default=None)
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args(argv)

    report = build_report(
        sessions=observe_sessions(),
        keys=key_freshness(_load_key_status(), now=time.time()),
        seats=seat_truth(args.seat_receipt),
    )
    if args.as_json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        for s in report["sessions"] or [{"socket": "-", "session": "none found",
                                         "pane_alive": False, "bridge": "unknown"}]:
            print(f"session {s['session']} @ {s['socket']}: "
                  f"pane={'live' if s['pane_alive'] else 'dead'} bridge={s['bridge']}")
        k = report["key_oracle"]
        print(f"keys: {k['state']} ({k.get('detail', '')})")
        st = report["seats"]
        label = (f"{st.get('verified')}/{st.get('total')} verified"
                 if st["state"] == "reported" else st["detail"])
        print(f"seats: {label}")
        print(f"attention_needed: {report['attention_needed']}")
    return 1 if (args.strict and report["attention_needed"]) else 0


if __name__ == "__main__":
    raise SystemExit(main())
