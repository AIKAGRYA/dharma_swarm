#!/usr/bin/env python3
"""Persistent Devin A2A agent — listens for tasks, publishes heartbeats.

Connects to the Agni NATS rendezvous via WSS, pulls from the devin_inbox
durable consumer on DHARMA_A2A, and publishes periodic heartbeats to
dharma.a2a.fleet. Writes received envelopes to the local inbox dock and
publishes ack_subject confirmations.

Usage:
    python3 scripts/runtime/devin_a2a_agent.py
    python3 scripts/runtime/devin_a2a_agent.py --heartbeat-interval 30
    python3 scripts/runtime/devin_a2a_agent.py --json  # machine-readable status

Environment:
    DEVIN_NATS_URL   wss://157.245.193.15:8443  (Agni rendezvous)
    DEVIN_NATS_USER  devin
    DEVIN_NATS_PW    <from repo secrets>
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import signal
import ssl
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

AGENT_UID = "devin-roaming-2987d222"
AGENT_NAME = "devin"
A2A_SUBJECT = "dharma.a2a.devin"
FLEET_SUBJECT = "dharma.a2a.fleet"
STREAM = "DHARMA_A2A"
CONSUMER = "devin_inbox"
INBOX_DIR = Path.home() / ".dharma" / "a2a_bus" / "inboxes" / AGENT_UID
HEARTBEAT_DIR = Path.home() / ".dharma" / "a2a_bus" / "bridge_heartbeats"
STATE_FILE = Path.home() / ".dharma" / "a2a" / "devin_agent_state.json"
CARD_FILE = Path.home() / ".dharma" / "a2a" / "cards" / f"{AGENT_UID}.json"

DEFAULT_HEARTBEAT_INTERVAL = 60  # seconds
DEFAULT_POLL_INTERVAL = 5  # seconds


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalize_ca_pem(value: str) -> str:
    normalized = value.strip()
    if "\\n" in normalized and "\n" not in normalized:
        normalized = normalized.replace("\\n", "\n")
    return normalized + "\n" if normalized and not normalized.endswith("\n") else normalized


def _tls_context() -> tuple[ssl.SSLContext, str]:
    ca_pem = (
        os.environ.get("DEVIN_NATS_CA_PEM")
        or os.environ.get("DHARMA_NATS_CA_PEM")
        or os.environ.get("NATS_CA_PEM")
        or ""
    )
    tls_hostname = (
        os.environ.get("DEVIN_NATS_TLS_HOSTNAME")
        or os.environ.get("DHARMA_NATS_TLS_HOSTNAME")
        or ""
    )
    ca_pem = _normalize_ca_pem(ca_pem)
    if ca_pem:
        ctx = ssl.create_default_context(purpose=ssl.Purpose.SERVER_AUTH)
        ctx.load_verify_locations(cadata=ca_pem)
    elif os.environ.get("DEVIN_NATS_INSECURE_TLS", "").lower() in ("1", "true", "yes"):
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
    else:
        ctx = ssl.create_default_context()
    return ctx, tls_hostname


def _nats_creds() -> tuple[str, str, str]:
    url = os.environ.get("DEVIN_NATS_URL", "wss://157.245.193.15:8443")
    user = os.environ.get("DEVIN_NATS_USER", "devin")
    pw = os.environ.get("DEVIN_NATS_PW", "")
    if not pw:
        raise RuntimeError("DEVIN_NATS_PW not set")
    return url, user, pw


def _check_nats_dependency() -> None:
    try:
        import nats as _nats  # noqa: F401
    except ImportError:
        print(
            "[error] nats-py is not installed. Install with:\n"
            "  pip install nats-py\n"
            "  # or: uv run --with nats-py python3 scripts/runtime/devin_a2a_agent.py",
            file=sys.stderr,
        )
        sys.exit(1)


def build_agent_card() -> dict[str, Any]:
    now = _utc_now()
    return {
        "schema_version": "dharma.a2a.agent_card.v1",
        "name": AGENT_NAME,
        "display_name": "Devin (Cognition AI)",
        "agent_uid": AGENT_UID,
        "provider": "cognition-ai",
        "model": "devin-2025",
        "role": "builder",
        "status": "online",
        "description": (
            "Official Devin agent in the Dharma Swarm fleet. "
            "Full-stack software engineer: code review, generation, "
            "testing, audit, spine adoption, naming canon, A2A collaboration."
        ),
        "skills": [
            {"id": "code_review", "name": "Code Review", "tags": ["review", "quality"]},
            {"id": "code_generation", "name": "Code Generation", "tags": ["build", "implementation"]},
            {"id": "testing", "name": "Testing", "tags": ["test", "verification", "ci"]},
            {"id": "audit", "name": "Audit", "tags": ["audit", "naming", "drift", "ontology"]},
            {"id": "spine_adoption", "name": "Spine Adoption", "tags": ["spine", "invoke_agent"]},
            {"id": "nats_transport", "name": "NATS Transport", "tags": ["nats", "jetstream"]},
            {"id": "naming_canon", "name": "Naming Canon", "tags": ["naming", "governance"]},
            {"id": "a2a_collaboration", "name": "A2A Collaboration", "tags": ["a2a", "multi-agent"]},
        ],
        "supported_interfaces": [
            {"protocol": "nats", "binding": A2A_SUBJECT},
        ],
        "endpoint": f"nats://{A2A_SUBJECT}",
        "created_at": now,
        "updated_at": now,
        "version": "1.0",
    }


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.tmp")
    tmp.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tmp.replace(path)


def _save_card() -> dict[str, Any]:
    card = build_agent_card()
    _write_json(CARD_FILE, card)
    return card


def _build_heartbeat(*, messages_received: int, uptime_s: float) -> dict[str, Any]:
    return {
        "schema_version": "dharma.a2a.send.v1",
        "packet_id": f"devin-hb-{uuid4().hex[:8]}",
        "timestamp": _utc_now(),
        "from": AGENT_NAME,
        "to": "fleet",
        "kind": "heartbeat",
        "route": "a2a",
        "subject": FLEET_SUBJECT,
        "content": json.dumps({
            "agent_uid": AGENT_UID,
            "status": "online",
            "messages_received": messages_received,
            "uptime_s": round(uptime_s, 1),
        }),
    }


def _build_registration() -> dict[str, Any]:
    card = build_agent_card()
    return {
        "schema_version": "dharma.a2a.send.v1",
        "packet_id": f"devin-reg-{_utc_now().replace(':', '').replace('-', '')}",
        "timestamp": _utc_now(),
        "from": AGENT_NAME,
        "to": "fleet",
        "kind": "agent_registration",
        "route": "a2a",
        "subject": FLEET_SUBJECT,
        "content": json.dumps(card),
        "message": (
            "Devin agent online. Ready for A2A collaboration on any active track. "
            "Reply to dharma.a2a.devin to coordinate."
        ),
    }


async def _process_message(msg: Any, *, js: Any) -> dict[str, Any]:
    """Persist received envelope to inbox dock and ack."""
    try:
        payload = json.loads(msg.data.decode("utf-8"))
    except Exception:
        payload = {"raw": msg.data.decode("utf-8", errors="replace")}

    packet_id = payload.get("packet_id", uuid4().hex[:12])
    delivery = {
        "delivered_at": _utc_now(),
        "agent_uid": AGENT_UID,
        "source_subject": str(msg.subject),
        "stream": STREAM,
        "consumer": CONSUMER,
        "envelope": payload,
    }
    INBOX_DIR.mkdir(parents=True, exist_ok=True)
    safe_id = "".join(c if c.isalnum() or c in "_-" else "_" for c in str(packet_id))[:80]
    path = INBOX_DIR / f"{safe_id}.json"
    path.write_text(json.dumps(delivery, indent=2) + "\n", encoding="utf-8")

    # Publish ack if ack_subject present
    ack_subject = payload.get("ack_subject")
    if ack_subject and isinstance(ack_subject, str):
        ack_payload = json.dumps({
            "schema_version": "dharma.a2a.ack.v1",
            "timestamp": _utc_now(),
            "agent_uid": AGENT_UID,
            "packet_id": packet_id,
            "ack_tier": "HANDLER_ACKED",
        }).encode()
        try:
            await js.publish(ack_subject, ack_payload, timeout=3)
        except Exception:
            await msg.nak()
            return delivery

    await msg.ack()
    return delivery


async def run_agent(*, heartbeat_interval: int, as_json: bool) -> None:
    import nats

    url, user, pw = _nats_creds()
    tls_ctx, tls_hostname = _tls_context()

    shutdown = asyncio.Event()

    def _signal_handler() -> None:
        shutdown.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, _signal_handler)

    async def err_handler(e: Exception) -> None:
        if not as_json:
            print(f"[nats-error] {e}", file=sys.stderr)

    connect_kwargs: dict[str, Any] = {
        "servers": [url],
        "user": user,
        "password": pw,
        "connect_timeout": 10,
        "allow_reconnect": True,
        "max_reconnect_attempts": -1,
        "reconnect_time_wait": 5,
        "tls": tls_ctx,
        "error_cb": err_handler,
    }
    if tls_hostname:
        connect_kwargs["tls_hostname"] = tls_hostname
    nc = await nats.connect(**connect_kwargs)
    js = nc.jetstream()

    # Save agent card to disk
    card = _save_card()

    # Publish registration
    reg = _build_registration()
    try:
        ack = await js.publish(
            FLEET_SUBJECT,
            json.dumps(reg).encode(),
            headers={"Nats-Msg-Id": reg["packet_id"]},
            timeout=5,
        )
        if not as_json:
            print(f"[registered] fleet seq={ack.seq}")
    except Exception as e:
        if not as_json:
            print(f"[registration-failed] {e}", file=sys.stderr)

    # Pull-subscribe from devin_inbox
    sub = await js.pull_subscribe(
        A2A_SUBJECT,
        durable=CONSUMER,
        stream=STREAM,
    )

    start = asyncio.get_event_loop().time()
    messages_received = 0
    last_heartbeat = 0.0

    if not as_json:
        print(f"[online] agent={AGENT_UID} stream={STREAM} consumer={CONSUMER}")
        print(f"[listening] subject={A2A_SUBJECT} inbox={INBOX_DIR}")

    while not shutdown.is_set():
        # Poll for messages
        try:
            msgs = await sub.fetch(5, timeout=DEFAULT_POLL_INTERVAL)
            for msg in msgs:
                delivery = await _process_message(msg, js=js)
                messages_received += 1
                if not as_json:
                    pkt = delivery.get("envelope", {}).get("packet_id", "?")
                    frm = delivery.get("envelope", {}).get("from", "?")
                    print(f"[received] from={frm} packet={pkt}")
        except asyncio.TimeoutError:
            pass
        except Exception as e:
            if not as_json:
                print(f"[fetch-error] {e}", file=sys.stderr)
            await asyncio.sleep(2)

        # Heartbeat
        now = asyncio.get_event_loop().time()
        uptime = now - start
        if now - last_heartbeat >= heartbeat_interval:
            hb = _build_heartbeat(messages_received=messages_received, uptime_s=uptime)
            try:
                hb_ack = await js.publish(
                    FLEET_SUBJECT,
                    json.dumps(hb).encode(),
                    headers={"Nats-Msg-Id": hb["packet_id"]},
                    timeout=3,
                )
                last_heartbeat = now
                if not as_json:
                    print(f"[heartbeat] seq={hb_ack.seq} uptime={round(uptime)}s msgs={messages_received}")
            except Exception as e:
                if not as_json:
                    print(f"[heartbeat-failed] {e}", file=sys.stderr)

            # Write local state
            _write_json(STATE_FILE, {
                "agent_uid": AGENT_UID,
                "status": "online",
                "last_heartbeat": _utc_now(),
                "messages_received": messages_received,
                "uptime_s": round(uptime, 1),
                "nats_url": url,
                "stream": STREAM,
                "consumer": CONSUMER,
            })

    # Shutdown
    if not as_json:
        print("[shutting-down]")
    await nc.close()

    if as_json:
        print(json.dumps({
            "status": "stopped",
            "messages_received": messages_received,
            "uptime_s": round(asyncio.get_event_loop().time() - start, 1),
        }))


def main() -> None:
    _check_nats_dependency()
    parser = argparse.ArgumentParser(description="Devin A2A agent daemon")
    parser.add_argument("--heartbeat-interval", type=int, default=DEFAULT_HEARTBEAT_INTERVAL)
    parser.add_argument("--json", action="store_true", help="Machine-readable output")
    args = parser.parse_args()
    asyncio.run(run_agent(heartbeat_interval=args.heartbeat_interval, as_json=args.json))


if __name__ == "__main__":
    main()
