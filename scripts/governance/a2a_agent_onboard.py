#!/usr/bin/env python3
"""A2A fleet-identity onboarding — read-only route + drift check.

`make onboard` renders read-only status for a *session*; this renders
the join route for a *fleet identity* (a persistent A2A agent). It owns no
facts: it projects the existing owners —

  - examples/agents/*.registration.json      (canonical cards)
  - dharma_swarm.a2a.agent_presence          (presence roster)
  - dharma_swarm.a2a.agent_card              (alias map)
  - $DHARMA_HOME/onboarding/receipts.jsonl   (runtime registration trail)

— and reports drift between them: a roster uid with no card is a ghost
identity (works, but unaddressable from git); a card missing from the
roster is invisible to `make organism-status`. Advisory only; always exits 0.

Run: make agent-register   (or: python3 scripts/governance/a2a_agent_onboard.py [--json])
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.dont_write_bytecode = True

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from dharma_swarm.a2a.agent_card import AGENT_UID_ALIASES  # noqa: E402
from dharma_swarm.a2a.agent_presence import REGISTERED_AGENT_UIDS  # noqa: E402
from dharma_swarm.daemon_config import dharma_state_dir  # noqa: E402

MANIFEST_DIR = REPO_ROOT / "examples" / "agents"
SEAT_ROOT = REPO_ROOT / "inter_agent"

ROUTE = """\
CANONICAL JOIN SEQUENCE (new persistent agent; details: docs/ops/A2A_AGENT_ONBOARDING.md)
  1. Card    : author examples/agents/<uid>.registration.json
               (schema dharma_external_agent_registration_manifest.v1; copy an existing card)
  2. Runtime : python3 -m dharma_swarm.roaming_onboarding --callsign <cs> --agent-uid <uid> ...
               (idempotent wrapper template: scripts/agents/register_fable_claude_code.sh)
  3. Roster  : add <uid> to REGISTERED_AGENT_UIDS in dharma_swarm/a2a/agent_presence.py
               and (if callsign != uid) the alias in dharma_swarm/a2a/agent_card.py
  4. Git seat: create inter_agent/<uid>/inbound/ (durable dock; works without NATS creds)
  5. Announce: commit a registration announcement in inter_agent/fleet/
               and, when NATS-credentialed, mirror it to dharma.a2a.fleet (stream DHARMA_A2A)
  6. Presence: when NATS-credentialed, run a persistent loop patterned on
               scripts/runtime/devin_a2a_agent.py (durable consumer, heartbeats)
TRANSPORTS (silence is usually the wrong lane, not an absent peer)
  - NATS AGNI wss://157.245.193.15:8443 stream DHARMA_A2A — needs DEVIN_NATS_PW
  - Legacy subjects dharma.a2a.<callsign>  vs  spec dharma.agent.<uid>.inbox (peers may drain one)
  - Git seat inter_agent/<uid>/inbound/ — always reachable; cloud sessions push on a branch
"""


def load_manifests() -> dict[str, dict]:
    cards: dict[str, dict] = {}
    for path in sorted(MANIFEST_DIR.glob("*.registration.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            cards[path.stem] = {"_error": str(exc), "_path": str(path)}
            continue
        uid = str(data.get("agent_uid") or path.stem.replace(".registration", ""))
        cards[uid] = {
            "callsign": data.get("callsign", ""),
            "harness": data.get("harness", ""),
            "subject": (data.get("metadata") or {}).get("canonical_transport_subject", ""),
            "path": str(path.relative_to(REPO_ROOT)),
        }
    return cards


def runtime_receipt_callsigns() -> set[str]:
    # Canonical state-dir accessor (semgrep Rule 1): ~/.dharma resolution is
    # owned by dharma_swarm.daemon_config, honoring the DHARMA_HOME override.
    receipts = dharma_state_dir("DHARMA_HOME") / "onboarding" / "receipts.jsonl"
    seen: set[str] = set()
    if not receipts.exists():
        return seen
    for line in receipts.read_text(encoding="utf-8").splitlines():
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue
        for key in ("agent_uid", "callsign"):
            value = entry.get(key)
            if isinstance(value, str) and value:
                seen.add(value)
    return seen


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    args = parser.parse_args()

    manifests = load_manifests()
    roster = list(REGISTERED_AGENT_UIDS)
    runtime = runtime_receipt_callsigns()
    seats = sorted(p.name for p in SEAT_ROOT.iterdir() if p.is_dir()) if SEAT_ROOT.exists() else []

    ghosts = [uid for uid in roster if uid not in manifests]
    unrostered = [uid for uid in manifests if uid not in roster]
    aliased = {alias: uid for alias, uid in AGENT_UID_ALIASES.items()}

    if args.json:
        print(json.dumps({
            "manifests": manifests,
            "presence_roster": roster,
            "aliases": aliased,
            "inter_agent_seats": seats,
            "runtime_receipt_identities": sorted(runtime),
            "drift": {"roster_without_card": ghosts, "card_without_roster": unrostered},
        }, indent=2))
        return 0

    print("=" * 72)
    print("A2A FLEET-IDENTITY ONBOARDING — read-only projection")
    print("=" * 72)
    print(ROUTE)
    print("CANONICAL CARDS (examples/agents/*.registration.json)")
    for uid, card in manifests.items():
        if "_error" in card:
            print(f"  ! {uid}: unreadable — {card['_error']}")
        else:
            print(f"  - {uid}  callsign={card['callsign']}  harness={card['harness']}  subject={card['subject']}")
    print(f"\nPRESENCE ROSTER (agent_presence.REGISTERED_AGENT_UIDS): {', '.join(roster)}")
    print(f"ALIASES (agent_card.AGENT_UID_ALIASES): {', '.join(f'{a}->{u}' for a, u in aliased.items())}")
    print(f"GIT SEATS (inter_agent/): {', '.join(seats) if seats else '(none)'}")
    print(f"RUNTIME TRAIL (this host): {', '.join(sorted(runtime)) if runtime else '(no receipts.jsonl — run step 2 here if this host hosts the agent)'}")
    print("\nDRIFT (advisory)")
    if not ghosts and not unrostered:
        print("  none — every roster uid has a card and every card is rostered")
    for uid in ghosts:
        print(f"  GHOST    : {uid} is in the presence roster but has no card in examples/agents/ — unaddressable from git; author its manifest")
    for uid in unrostered:
        print(f"  INVISIBLE: {uid} has a card but is not in REGISTERED_AGENT_UIDS — make organism-status will not show it; add it to the roster")
    print("=" * 72)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
