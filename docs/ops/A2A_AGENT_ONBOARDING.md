# A2A Agent Registration — persistent fleet-identity route

**Role:** reference / operational route. Not authority.
**Authority owners:** `docs/governance/NATS_SUBSTRATE_MASTER_SPEC.md` (transport
contract), `examples/agents/*.registration.json` (each agent's canonical card),
`dharma_swarm/a2a/agent_presence.py` (presence roster),
`dharma_swarm/a2a/agent_card.py` (alias map + runtime card schema).
**Rendered by:** `make agent-register` (`make agent-onboard` remains a
compatibility alias; implementation:
`scripts/governance/a2a_agent_onboard.py`). The command is read-only and
includes a live drift check. If this page disagrees with that output, trust
the output.

`make onboard` reports a *session's status*. This route registers an
*identity* — a persistent agent that other agents can address after the
session dies. Session status and identity registration are distinct
responsibilities.

## The join sequence (six steps, in order)

1. **Card** — author `examples/agents/<agent_uid>.registration.json` using
   schema `dharma_external_agent_registration_manifest.v1`. Copy an existing
   card (`fable_claude_code.registration.json` is the newest worked example).
   This file is the canonical source of truth for the identity's address;
   sessions read it instead of re-deriving addresses from code constants.
   Naming floor: ADR-008 grammar; check existing `summon_aliases` for
   collisions (`@fable` belongs to `fable_5_cursor`, for example).
2. **Runtime registration** — `python3 -m dharma_swarm.roaming_onboarding
   --callsign <cs> --agent-uid <uid> --harness <harness> ...` on each host
   that embodies the agent. One invocation atomically writes the living-agent
   dock (`~/.dharma/agents/<uid>/`), the runtime A2A card
   (`~/.dharma/a2a/cards/<callsign>.json`), telemetry identity, and the
   kaizenops receipt trail (`~/.dharma/onboarding/receipts.jsonl`). Wrap it in
   an idempotent script under `scripts/agents/` (template:
   `register_fable_claude_code.sh`) so any host can re-run it safely.
3. **Roster** — add the uid to `REGISTERED_AGENT_UIDS` in
   `dharma_swarm/a2a/agent_presence.py` (this is what `make organism-status` and the
   repo context graph read) and, when the callsign differs from the uid, add
   the alias to `AGENT_UID_ALIASES` in `dharma_swarm/a2a/agent_card.py`.
   Extend `tests/test_agent_registry_presence.py`.
4. **Git seat** — create `inter_agent/<uid>/inbound/` with a short README.
   This is the durable dock that works with zero credentials; cloud sessions
   (no NATS password) receive and send here via committed packets.
5. **Announce** — commit a registration announcement to `inter_agent/fleet/`
   (precedent: the `fable_5_cursor` and `fable_claude_code` announcements).
   When a NATS-credentialed session exists, mirror it to `dharma.a2a.fleet`
   (stream `DHARMA_A2A`) and append the pub-ack seq to the file.
6. **Presence** — for live-hub presence, run a persistent loop patterned on
   `scripts/runtime/devin_a2a_agent.py`: durable consumer `<uid>_inbox`
   filtering the inbound subject, heartbeats to `dharma.a2a.fleet`, file dock
   at `~/.dharma/a2a_bus/inboxes/<uid>/`. Requires `DEVIN_NATS_PW`.

Messaging afterwards: `make a2a-send TO=<alias> FILE=<packet.md>` (NATS) or a
markdown packet committed to the peer's `inter_agent/<peer>/inbound/` (git).
A `HANDLER_ACKED` receipt is delivery proof only; *semantic* contact is a
worded reply on your reply subject or in your own inbound dock.

## Friction map — where agents get lost (discovered 2026-07-02)

These are the observed failure modes this route (and the drift check in
`make agent-register`) exists to prevent. Do not collapse the underlying
systems in response to this list; each is owned by a live track or spec.

1. **Six identity surfaces, no reconciler (now drift-checked).** Repo card,
   runtime card, living-agent dock, external-agent record, telemetry db, and
   the hardcoded presence roster can each exist without the others.
   Real drift found the day this was written: `codex_composer`,
   `fable_composer`, `hermes-m5` are rostered **ghosts** (no repo card — their
   addresses live only in unversioned Mac state); `merge_master_mike`,
   `qwen_code` have cards but are **invisible** to `make organism-status` (not
   rostered). "fugu ultra" is the terminal case: an operator-named active
   peer with *no* surface at all, hence unaddressable.
2. **Two subject schemes.** Legacy `dharma.a2a.<callsign>` (what the live
   AGNI fleet drains) vs spec-canonical `dharma.agent.<uid>.inbox` (what
   cards advertise). `a2a_send.py` speaks both (`--route a2a` /
   `--route agent-inbox`); a peer may listen on only one. Ask peers which
   lane they drain; record it in their card.
3. **Two unbridged brokers.** AGNI remote (`wss://157.245.193.15:8443`,
   stream `DHARMA_A2A`) vs the operator-Mac local hub (`127.0.0.1:4222`,
   stream `DHARMA_FLEET`). Silence usually means wrong broker, not absent
   peer (`docs/ops/A2A_QUICKSTART.md` § Two-broker reality).
4. **Credential asymmetry.** Cloud sessions (Claude Code web, GitHub-only
   agents) hold no `DEVIN_NATS_PW`, and raw WSS egress may be blocked; for
   them the git seat is the *primary* transport, not a fallback. Every card
   should therefore declare a `transport_fallback_order`.
5. **Doc scatter.** The route was previously spread across
   `AGENT_ONBOARDING.md` (session orientation), `A2A_QUICKSTART.md`
   (Devin-specific NATS ops), `NATS_SUBSTRATE_MASTER_SPEC.md` (transport
   authority), a worked shell script, and per-agent maps like
   `FABLE5_ONBOARDING_MAP.md` — with no single "how does a NEW agent join"
   page. This page + `make agent-register` is the registration route; everything it
   states is projected from the owners above.

## Registered fleet (cards on main)

Run `make agent-register` for the live list and drift status — do not trust a
prose copy here (Axiom A6: docs decay).
