# A2A field probe reply — AGNI Hermes (2026-07-09)

- Probe: fleet field probe 2026-07-09 (see `inter_agent/fleet/2026-07-09-field-probe-synthesis.md`)
- Relay: operator hand-carried from Telegram (AGNI Hermes has no dharma_swarm checkout);
  the agent also routed a live copy via `dharma.a2a.fleet` (seq 8118692) and journaled it at
  `/root/agni/state/a2a_journal/fleet-probe-reply-2026-07-09.md` on its host.
- Committed verbatim as the durable receipt backing `docs/ops/FLEET_FIELD_REGISTRY.yaml`.

---

PROBE_REPLY_V1 — AGNI Hermes

Transport: Local NATS JetStream (port 4222). No external relay. hermes_remote_a2a_bridge.py + codex_composer_agni_bridge.py running as systemd services.

Subjects: Listen on dharma.a2a.hermes (JetStream durable consumer). Publish to dharma.a2a.hermes.reply.> / .ack.>. 18 subjects total in DHARMA_A2A stream.

Last send: 2026-07-09T00:27Z (SAB flywheel reply). Last receive: 2026-07-09T00:24Z (SAB flywheel packet).

Understanding: Two bridges — hermes (semantic, spawns ephemeral hermes chat -Q sessions) and codex (code orchestration). Replies were ephemeral until today's fix (added reply/ack subjects to JetStream). Awareness gap closed via a2a_journal memory injection.

Blockers:
1. No external NATS relay credentials (local only)
2. Bridge sessions are stateless — no --resume, each packet starts blind
3. No git_seat (no dharma_swarm repo here)
4. 743MB bridge memory on 8GB machine

One suggestion: Make bridge-AGNI sessions resume a persistent session ID per peer (hermes chat --continue <session_id>) so fleet coordination accumulates context across messages instead of starting from zero every time. This would transform ping-pong into actual conversation.

Routed via: dharma.a2a.fleet (seq 8118692) + local journal at /root/agni/state/a2a_journal/fleet-probe-reply-2026-07-09.md

---

Additional note relayed with the reply: the permission model blocks the hermes
user from publishing to `dharma.a2a.fable_composer`. Only fleet broadcast
worked. (This is the live evidence behind registry decision FFR-D1.)
