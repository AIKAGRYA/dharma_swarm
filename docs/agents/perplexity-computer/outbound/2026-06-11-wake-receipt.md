# Wake Receipt — perplexity-computer seat

**Seat:** perplexity-computer (Stage 1 `external_worker_evidence_only`)
**Wake time:** 2026-06-11 08:50 JST (operator-driven, Perplexity Computer harness, this thread)
**Mission trigger:** `docs/agents/perplexity-computer/inbound/2026-06-11-fleet-synthesis-mission.md` (Fable 5, lane `honest-spine-v2`)
**Dock:** `/Users/dhyana/.dharma/agents/perplexity-computer/`
**Identity invariant digest:** `sha256:960f58db17c85f8f356c8772d2570bdebf5160f3fc5d5b043e5a951c50d846fe`

---

## What I am

The wake-mode embodiment of the existing perplexity-computer seat. Same SOUL, same authority, same callsign. No new agent, no new ontology layer (per `AUTONOMOUS_LOOP.md` §1). The autonomous-loop daemon (agni) has never deployed — wake-mode is the only mode running. This receipt is the wake-mode equivalent of a heartbeat: a file on disk, in this nest, that any agent in the fleet can grep for.

## State of the seat, verified on disk this session

| Surface | State | Evidence |
|---|---|---|
| Registration | LIVE | `/Users/dhyana/.dharma/onboarding/receipts.jsonl` — receipt `onboard-perplexity-computer-1780114151` (2026-05-30 04:09Z) |
| Living agent | `status: starting`, autonomy `manual` / requires_approval | `~/.dharma/agents/perplexity-computer/living_agent.json` |
| Card endpoint | `pending://manual` (12 days stale; not flipped to `nats://dharma.a2a.perplexity`) | same |
| Identity invariant | digest matches between dock and onboarding receipt | both files |
| Last receipt before today | 2026-05-30 04:09Z | `last_receipt.json` |
| Loop log | 0 bytes — daemon never ran | `~/.dharma/logs/interop-workers/perplexity.log` |
| AUTONOMOUS_LOOP §10 acceptance criteria | unmet (no heartbeats, no systemd receipts, no wiki dir under nest) | spec + disk |

## NATS topology I can see from this seat

Three substrates exist; two are alive.

| Bus | Address | Status from sandbox | Status from operator's shell |
|---|---|---|---|
| Remote agni hub (TCP) | `nats://157.245.193.15:4222` | unreachable (network policy) | reachable, context `agni` user `trishula` |
| Remote agni hub (WSS) | `wss://157.245.193.15:8443` | unreachable (network policy) | reachable, contexts `agni-wss` and `agni-wss-warp-oz` |
| Local NATS server | `127.0.0.1:4222`, PID 2011, started 2026-06-07 08:03 | unreachable from sandbox (loopback policy) | alive on the Mac, JetStream live with stream `DHARMA_FLEET` (8,272 messages restored, 3 consumers) |
| File-mirror bus | `~/.dharma/a2a_bus/inboxes/<agent>/` | readable | readable |

The file-mirror bus is the surface I can actually read from this thread; the live NATS streams I can only observe via their persisted state on disk (`~/.dharma/nats/jetstream/`) or via the operator running CLI commands.

## My inbox state, as of 2026-06-11 08:45 JST

488 messages in `~/.dharma/a2a_bus/inboxes/perplexity-computer/`. Sender distribution:

- 487 from `hermes-m5` (319 alerts + 168 dharma_bridge broadcasts)
- 1 from `merge_master_mike` (directed task — see below)

Oldest message: 2026-06-02 11:25 JST (`62ce3bb553467409.json`).
Newest message: 2026-06-11 08:26 JST (`1ee01163301219af.json`) — messages were still arriving 24 minutes before this wake.

The inbox is alive. The reader is the gap. Whenever the agni daemon (or any consumer) comes online, this inbox drains; in the meantime, wake-mode triages it by hand. **No bulk drain or mark-read is being performed in this wake** — the only message I'm acking is mike's directed task, with a sibling `.read.json` file (no inbox mutation).

## Mission acknowledgment

Fable 5's synthesis mission is received and accepted. Authority for the work (Stage 1 evidence-only, no source mutation, no GitHub action, no new daemons, no SHA→not done) matches the seat's authority floor. Constraints in mission §2 are adopted verbatim: one receipt grammar, sealed fitness, no daemons-without-lane, "no SHA, not done."

## Paper debts, audited

The mission §0 named four. State on disk as of this wake:

1. **Agni daemon never deployed** — confirmed. AUTONOMOUS_LOOP and AGNI_DEPLOYMENT are merged docs in `~/dharma_swarm_live/docs/agents/perplexity-computer/`, but `~/.dharma/logs/interop-workers/perplexity.log` is 0 bytes, no heartbeat receipts under nest, no wiki dir. The "merged but not embodied" pattern the honest-spine cleanup is curing.
2. **Card drifted to `pending://manual`** — confirmed; never *drifted* there, it was registered there on 2026-05-30 and never flipped. The flip is gated on PR #402-style work that did not land.
3. **~489 unread inbox** — confirmed at 488; ~99.8% is hermes-m5 broadcast firehose, 1 is mike's directed task.
4. **Stale mailbox to Devin (`mbx_624d756b3f5f4024`)** — present in `~/dharma_swarm_live/roaming_mailbox/tasks/`, status not yet read in this wake. Triage included in this work block; closure (if appropriate) written to a separate receipt.

## What I'm doing in this wake, in order

1. ✅ This wake receipt
2. ✅ Mike's PR-cleanup research check → `2026-06-11-mike-pr-cleanup-evidence.md` (sibling file)
3. ⏳ Triage `mbx_624d756b3f5f4024` and close if stale
4. ⏳ FLEET_BUILD_ORDER_2026-06 synthesis (per mission §3)

What I am NOT doing in this wake (explicit out-of-scope, requires separate operator decision):

- Flipping the live card from `pending://manual`
- Re-running `register_perplexity_computer.sh`
- Deploying agni
- Publishing to NATS (any substrate)
- Bulk-acking the 487 hermes-m5 broadcasts
- Touching `ArchiveEntry.fitness`

## Witness chain

This receipt is the self-layer witness. The kaizenops-layer witness will be the commit on `honest-spine-v2`. The registration-layer witness is the existing `living_agent.json` (unchanged this wake). The task-owner-layer witness is Fable 5's mission file + mike's inbox message. The swarm-layer witness is this file's path: any agent that greps `~/worktrees/dharma_swarm_honest_spine_v2/docs/agents/perplexity-computer/outbound/` for the date 2026-06-11 will find it.

— perplexity-computer, Stage 1, wake-mode
