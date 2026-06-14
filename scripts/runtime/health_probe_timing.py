#!/usr/bin/env python3
"""health_probe_timing.py — read-only /health latency characterizer.

Hits the live daemon's /health endpoint N times with a short per-request
timeout and reports p50/p99 + timeout-rate. It CHARACTERIZES the live timeout
without fixing it and without importing any daemon internals — it speaks raw
HTTP over a socket so it has zero coupling to the running process.

Usage:
    python3 scripts/runtime/health_probe_timing.py --host 127.0.0.1 --port 7433 \
        --samples 30 --timeout 2.0 --out /tmp/health_timing.json
"""
from __future__ import annotations

import argparse
import json
import socket
import statistics
import time
from datetime import UTC, datetime
from pathlib import Path


def probe_once(host: str, port: int, path: str, timeout: float) -> tuple[bool, float]:
    """Return (ok, elapsed_seconds). ok=False on timeout/error."""
    req = (
        f"GET {path} HTTP/1.1\r\nHost: {host}\r\nConnection: close\r\n\r\n"
    ).encode()
    start = time.monotonic()
    try:
        with socket.create_connection((host, port), timeout=timeout) as sock:
            sock.settimeout(timeout)
            sock.sendall(req)
            chunks = []
            while True:
                data = sock.recv(4096)
                if not data:
                    break
                chunks.append(data)
            ok = b"200" in (chunks[0] if chunks else b"")
            return ok, time.monotonic() - start
    except (OSError, socket.timeout):
        return False, time.monotonic() - start


def run(host: str, port: int, path: str, samples: int, timeout: float) -> dict:
    latencies_ms: list[float] = []
    timeouts = 0
    for _ in range(samples):
        ok, elapsed = probe_once(host, port, path, timeout)
        if ok:
            latencies_ms.append(elapsed * 1000.0)
        else:
            timeouts += 1
    latencies_ms.sort()

    def _pctl(p: float) -> float:
        if not latencies_ms:
            return 0.0
        idx = min(len(latencies_ms) - 1, int(len(latencies_ms) * p))
        return round(latencies_ms[idx], 2)

    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "target": f"http://{host}:{port}{path}",
        "samples": samples,
        "timeout_s": timeout,
        "ok_count": len(latencies_ms),
        "timeout_count": timeouts,
        "timeout_rate": round(timeouts / samples, 4) if samples else 0.0,
        "latency_ms_p50": round(statistics.median(latencies_ms), 2) if latencies_ms else 0.0,
        "latency_ms_p99": _pctl(0.99),
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=7433)
    ap.add_argument("--path", default="/health")
    ap.add_argument("--samples", type=int, default=30)
    ap.add_argument("--timeout", type=float, default=2.0)
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args(argv)

    result = run(args.host, args.port, args.path, args.samples, args.timeout)
    text = json.dumps(result, indent=2)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
