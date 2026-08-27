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
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.runtime.pr_merge_control import (  # noqa: E402
    _is_publish_permission_violation,
    _resolve_nats_ca_pem,
)

REGISTRATION_FILE = REPO_ROOT / "examples" / "agents" / "devin.registration.json"

DEFAULT_URL = "wss://157.245.193.15:8443"
STREAM = "DHARMA_A2A"
CONSUMER = "devin_inbox"
DEFAULT_PROBE_TIMEOUT_S = 5.0
_PROBE_SUBJECT_BY_LANE = {
    "devin": "dharma.a2a.devin",
    "devin-roaming-2987d222": "dharma.a2a.devin",
    "merge_master_mike": "dharma.a2a.merge_master_mike",
    "codex": "dharma.a2a.codex",
    "codex_composer": "dharma.a2a.codex",
    "hermes": "dharma.a2a.hermes",
    "hermes-m5": "dharma.a2a.hermes",
    "perplexity": "dharma.a2a.perplexity",
    # perplexity-computer's canonical subject (dharma.a2a.perplexity-computer)
    # is reserved-but-NOT-live until the FFR-D1 ACL rework provisions it
    # (FLEET_FIELD_REGISTRY.yaml); the doctor probes the live field, so it
    # targets the historical live lane until then. Flip after FFR-D1 applies.
    "perplexity-computer": "dharma.a2a.perplexity",
    "fleet": "dharma.a2a.fleet",
    "fable_5_cursor": "dharma.a2a.fable_5_cursor",
    "fable_composer": "dharma.a2a.fable_composer",
    "warp_oz": "dharma.a2a.warp_oz",
}


def _load_registration() -> dict[str, Any]:
    try:
        return json.loads(REGISTRATION_FILE.read_text())
    except FileNotFoundError:
        return {}


def _ca_pem() -> str:
    return _resolve_nats_ca_pem(
        dict(os.environ),
        "DEVIN_NATS_CA_PEM",
        "DHARMA_NATS_CA_PEM",
        "NATS_CA_PEM",
        endpoint=os.environ.get("DEVIN_NATS_URL", DEFAULT_URL),
    )


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


def _probe_targets(reg: dict[str, Any]) -> list[dict[str, str]]:
    metadata = reg.get("metadata", {})
    peers = metadata.get("coordination_peers", [])
    if not isinstance(peers, list):
        return []

    grouped: dict[str, dict[str, list[str] | str]] = {}
    order: list[str] = []
    for peer in peers:
        lane = str(peer).strip()
        if not lane:
            continue
        subject = _PROBE_SUBJECT_BY_LANE.get(lane, f"dharma.a2a.{lane}")
        if subject not in grouped:
            grouped[subject] = {"lane": [], "subject": subject}
            order.append(subject)
        lanes = grouped[subject]["lane"]
        assert isinstance(lanes, list)
        if lane not in lanes:
            lanes.append(lane)

    return [
        {
            "lane": ", ".join(grouped[subject]["lane"]),  # type: ignore[index]
            "subject": subject,
        }
        for subject in order
    ]


def _require_ws_transport_deps(url: str) -> None:
    """Fail honestly (not with nats-py traceback spew) when the hub URL is a
    websocket endpoint but aiohttp — required by nats-py's ws/wss transport
    but not supplied by the minimal locked ``a2a-runtime`` extra — is not
    installed. find_spec keeps this probe out of the import-provenance ratchet.
    """
    if not url.startswith(("ws://", "wss://")):
        return
    import importlib.util

    if importlib.util.find_spec("aiohttp") is None:
        raise RuntimeError(
            f"hub URL {url} is a websocket endpoint but aiohttp is not "
            "installed — nats-py needs it for ws/wss transports. "
            "Install with: pip install aiohttp"
        )


async def _probe_outbound_reachability(
    reg: dict[str, Any],
    live_subjects: list[str] | set[str] | tuple[str, ...],
    *,
    timeout_s: float = DEFAULT_PROBE_TIMEOUT_S,
) -> list[dict[str, Any]]:
    import nats

    url, user, pw = _creds()
    _require_ws_transport_deps(url)
    live_subject_set = {str(subject) for subject in live_subjects if str(subject)}
    probe_from = str(reg.get("callsign") or reg.get("agent_uid") or "devin")
    probes: list[dict[str, Any]] = []
    for target in _probe_targets(reg):
        subject = target["subject"]
        if subject not in live_subject_set:
            probes.append(
                {
                    "lane": target["lane"],
                    "subject": subject,
                    "status": "NO_STREAM",
                    "detail": "subject is not present in the live DHARMA_A2A stream",
                }
            )
            continue

        permission_detail: str | None = None
        permission_seen = asyncio.Event()
        permission_wait_guard_error: str | None = None
        close_guard_error: str | None = None

        async def error_cb(exc: Exception) -> None:
            nonlocal permission_detail
            message = str(exc)
            if _is_publish_permission_violation(message, subject):
                permission_detail = message
                permission_seen.set()

        nc = await nats.connect(
            servers=[url],
            user=user,
            password=pw,
            tls=_tls_context(),
            connect_timeout=timeout_s,
            allow_reconnect=False,
            max_reconnect_attempts=0,
            error_cb=error_cb,
        )
        try:
            payload = {
                "kind": "reachability_probe",
                "from": probe_from,
                "note": "a2a_doctor --probe-send authorization probe",
                "subject": subject,
            }
            try:
                await nc.jetstream().publish(
                    subject,
                    json.dumps(payload, sort_keys=True).encode("utf-8"),
                    timeout=timeout_s,
                )
            except Exception as exc:  # noqa: BLE001
                message = str(exc)
                if permission_detail is None:
                    try:
                        await asyncio.wait_for(permission_seen.wait(), timeout=0.5)
                    except Exception as wait_exc:
                        permission_wait_guard_error = type(wait_exc).__name__
                if permission_detail is not None:
                    row = {
                        "lane": target["lane"],
                        "subject": subject,
                        "status": "DENIED(permissions)",
                        "detail": permission_detail or message,
                    }
                    if permission_wait_guard_error:
                        row["debug"] = {"permission_wait_guard_error": permission_wait_guard_error}
                    probes.append(row)
                elif "no response from stream" in message.lower() or type(exc).__name__ == "NoStreamResponseError":
                    probes.append(
                        {
                            "lane": target["lane"],
                            "subject": subject,
                            "status": "NO_STREAM",
                            "detail": message,
                        }
                    )
                else:
                    probes.append(
                        {
                            "lane": target["lane"],
                            "subject": subject,
                            "status": "PUBLISH_FAILED",
                            "detail": message,
                        }
                    )
                continue
        finally:
            try:
                await asyncio.wait_for(nc.close(), timeout=2.0)
            except Exception as close_exc:
                close_guard_error = type(close_exc).__name__

        probes.append(
            {
                "lane": target["lane"],
                "subject": subject,
                "status": "ALLOWED",
                "detail": "",
                **(
                    {"debug": {"close_guard_error": close_guard_error}}
                    if close_guard_error
                    else {}
                ),
            }
        )
    return probes


async def _gather(scan: int) -> dict[str, Any]:
    import nats

    url, user, pw = _creds()
    _require_ws_transport_deps(url)
    out: dict[str, Any] = {"hub": {"url": url, "user": user, "stream": STREAM}}

    nc = await nats.connect(
        servers=[url], user=user, password=pw, tls=_tls_context(), connect_timeout=10
    )
    try:
        js = nc.jetstream()
        si = await js.stream_info(STREAM)
        subjects = [str(subject) for subject in (si.config.subjects or [])]
        out["hub"].update(
            messages=si.state.messages,
            first_seq=si.state.first_seq,
            last_seq=si.state.last_seq,
            subjects=subjects,
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


def _print_outbound_reachability(rows: list[dict[str, Any]]) -> None:
    print("\n=== Outbound reachability ===")
    if not rows:
        print("  (probe-send not requested)")
        return
    for row in rows:
        lane = str(row.get("lane") or "?")
        status = str(row.get("status") or "?")
        detail = str(row.get("detail") or "")
        if detail:
            print(f"  {lane:32s}  {status}  {detail}")
        else:
            print(f"  {lane:32s}  {status}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="A2A doctor for the Devin lane")
    parser.add_argument("--scan", type=int, default=120, help="how many recent stream msgs to scan for the roster")
    parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    parser.add_argument(
        "--probe-send",
        action="store_true",
        help="probe outbound publish authorization for known peer lanes with a small probe packet",
    )
    args = parser.parse_args(argv)

    reg = _load_registration()

    try:
        import nats  # noqa: F401
    except ImportError:
        print(
            "[error] locked nats-py is absent from this interpreter. "
            "Run: uv sync --frozen --extra a2a-runtime",
            file=sys.stderr,
        )
        return 1

    live: dict[str, Any] | None = None
    err: str | None = None
    outbound: list[dict[str, Any]] = []
    try:
        live = asyncio.run(_gather(args.scan))
    except Exception as exc:  # noqa: BLE001
        err = str(exc)
    if err is None and args.probe_send:
        try:
            live_subjects: list[str] = []
            if live is not None:
                hub = live.get("hub", {})
                if isinstance(hub, dict):
                    subjects = hub.get("subjects", [])
                    if isinstance(subjects, list):
                        live_subjects = [str(subject) for subject in subjects]
            outbound = asyncio.run(_probe_outbound_reachability(reg, live_subjects))
        except Exception as exc:  # noqa: BLE001
            outbound = [{"lane": "probe", "subject": "", "status": "ERROR", "detail": str(exc)}]

    if args.json:
        print(
            json.dumps(
                {"registration": reg, "live": live, "error": err, "outbound_reachability": outbound},
                indent=2,
            )
        )
    else:
        _print_human(reg, live, err)
        if args.probe_send:
            _print_outbound_reachability(outbound)
    return 0 if err is None else 2


if __name__ == "__main__":
    raise SystemExit(main())
