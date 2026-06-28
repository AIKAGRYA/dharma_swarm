#!/usr/bin/env python3
"""One-command A2A doctor for the Devin lane.

Connects to the AGNI NATS JetStream hub and prints everything a session needs
to know to start collaborating, so the address/card/hub never have to be
re-derived by hand:

  * canonical Devin identity (from examples/agents/devin.registration.json)
  * hub liveness (stream DHARMA_A2A: messages, seq range)
  * Devin inbox consumer state (devin_inbox: filter, pending, ack floor)
  * live fleet roster (who has published recently, by lane + kind)

The bundled CA at dharma_swarm/a2a/nats/agni-ws-ca.pem is loaded automatically
when no DEVIN_NATS_CA_PEM is exported, so TLS works with zero env juggling. The
only secret required is DEVIN_NATS_PW.

Usage:
    make a2a-status
    python3 scripts/runtime/a2a_doctor.py
    python3 scripts/runtime/a2a_doctor.py --scan 200   # deeper roster scan
    python3 scripts/runtime/a2a_doctor.py --json       # machine-readable
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import ssl
import sys
from collections import Counter
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
REGISTRATION_FILE = REPO_ROOT / "examples" / "agents" / "devin.registration.json"
BUNDLED_CA = REPO_ROOT / "dharma_swarm" / "a2a" / "nats" / "agni-ws-ca.pem"

DEFAULT_URL = "wss://157.245.193.15:8443"
STREAM = "DHARMA_A2A"
CONSUMER = "devin_inbox"


def _load_registration() -> dict[str, Any]:
    try:
        return json.loads(REGISTRATION_FILE.read_text())
    except FileNotFoundError:
        return {}


def _ca_pem() -> str:
    pem = (
        os.environ.get("DEVIN_NATS_CA_PEM")
        or os.environ.get("DHARMA_NATS_CA_PEM")
        or os.environ.get("NATS_CA_PEM")
        or ""
    ).strip()
    if not pem and BUNDLED_CA.exists():
        pem = BUNDLED_CA.read_text().strip()
    if "\\n" in pem and "\n" not in pem:
        pem = pem.replace("\\n", "\n")
    return pem


def _tls_context() -> ssl.SSLContext:
    pem = _ca_pem()
    ctx = ssl.create_default_context(purpose=ssl.Purpose.SERVER_AUTH)
    if pem:
        ctx.load_verify_locations(cadata=pem if pem.endswith("\n") else pem + "\n")
    return ctx


def _creds() -> tuple[str, str, str]:
    url = os.environ.get("DEVIN_NATS_URL", DEFAULT_URL)
    user = os.environ.get("DEVIN_NATS_USER", "devin")
    pw = os.environ.get("DEVIN_NATS_PW", "")
    return url, user, pw


async def _gather(scan: int) -> dict[str, Any]:
    import nats

    url, user, pw = _creds()
    out: dict[str, Any] = {"hub": {"url": url, "user": user, "stream": STREAM}}

    nc = await nats.connect(
        servers=[url], user=user, password=pw, tls=_tls_context(), connect_timeout=10
    )
    try:
        js = nc.jetstream()
        si = await js.stream_info(STREAM)
        out["hub"].update(
            messages=si.state.messages,
            first_seq=si.state.first_seq,
            last_seq=si.state.last_seq,
        )

        try:
            ci = await js.consumer_info(STREAM, CONSUMER)
            out["inbox"] = {
                "consumer": CONSUMER,
                "filter_subject": ci.config.filter_subject,
                "num_pending": ci.num_pending,
                "delivered_stream_seq": ci.delivered.stream_seq,
                "ack_floor_stream_seq": ci.ack_floor.stream_seq,
            }
        except Exception as exc:  # noqa: BLE001
            out["inbox"] = {"consumer": CONSUMER, "error": str(exc)}

        roster: Counter[str] = Counter()
        last_seen: dict[str, str] = {}
        seq = si.state.last_seq
        scanned = 0
        while seq >= si.state.first_seq and scanned < scan:
            try:
                msg = await js.get_msg(STREAM, seq)
            except Exception:  # noqa: BLE001
                seq -= 1
                continue
            scanned += 1
            seq -= 1
            try:
                data = json.loads(msg.data.decode())
            except Exception:  # noqa: BLE001
                continue
            frm = str(data.get("from") or "?")
            kind = str(data.get("kind") or "?")
            roster[f"{frm}/{kind}"] += 1
            last_seen.setdefault(frm, str(data.get("timestamp") or ""))
        out["scanned"] = scanned
        out["roster"] = dict(roster.most_common())
        out["last_seen"] = last_seen
    finally:
        await nc.close()
    return out


def _print_human(reg: dict[str, Any], live: dict[str, Any] | None, err: str | None) -> None:
    md = reg.get("metadata", {})
    print("=== Devin A2A identity (canonical) ===")
    print(f"  source        : {REGISTRATION_FILE.relative_to(REPO_ROOT)}")
    print(f"  agent_uid     : {reg.get('agent_uid', '?')}")
    print(f"  callsign      : {reg.get('callsign', '?')}")
    print(f"  lane          : {md.get('canonical_transport_subject', '?')}")
    print(f"  durable       : {md.get('durable_consumer', CONSUMER)}")
    hub = md.get("nats_hub", {})
    print(f"  hub           : {hub.get('name', '?')} {hub.get('url', '?')} ({hub.get('stream', '?')})")

    if err:
        print(f"\n[!] could not reach the hub: {err}")
        if not os.environ.get("DEVIN_NATS_PW"):
            print("    DEVIN_NATS_PW is not set — export the repo NATS secret and retry.")
        return
    if not live:
        return

    h = live["hub"]
    print("\n=== Hub (live) ===")
    print(f"  {h['stream']}: {h.get('messages', '?')} msgs, seq {h.get('first_seq', '?')}–{h.get('last_seq', '?')}")
    ib = live.get("inbox", {})
    if "error" in ib:
        print(f"  inbox {ib['consumer']}: ERROR {ib['error']}")
    else:
        print(
            f"  inbox {ib.get('consumer')}: filter={ib.get('filter_subject')} "
            f"pending={ib.get('num_pending')} delivered={ib.get('delivered_stream_seq')} "
            f"ack_floor={ib.get('ack_floor_stream_seq')}"
        )

    print(f"\n=== Live fleet roster (last {live.get('scanned', 0)} msgs) ===")
    roster = live.get("roster", {})
    if not roster:
        print("  (no messages scanned)")
    for key, count in roster.items():
        print(f"  {count:5d}  {key}")
    print("\n  tip: send a packet with `make a2a-send TO=<agent> FILE=<packet.md>`")


def main() -> int:
    parser = argparse.ArgumentParser(description="A2A doctor for the Devin lane")
    parser.add_argument("--scan", type=int, default=120, help="how many recent stream msgs to scan for the roster")
    parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    args = parser.parse_args()

    reg = _load_registration()

    try:
        import nats  # noqa: F401
    except ImportError:
        print("[error] nats-py not installed. Install with: pip install nats-py", file=sys.stderr)
        return 1

    live: dict[str, Any] | None = None
    err: str | None = None
    try:
        live = asyncio.run(_gather(args.scan))
    except Exception as exc:  # noqa: BLE001
        err = str(exc)

    if args.json:
        print(json.dumps({"registration": reg, "live": live, "error": err}, indent=2))
    else:
        _print_human(reg, live, err)
    return 0 if err is None else 2


if __name__ == "__main__":
    raise SystemExit(main())
