# Dharma A2A Fleet Full Audit — Mobile-First Control Plane

**Date:** 2026-07-11  
**Auditor vantage:** `rushabdev` Hermes on openclaw23 VPS  
**Shared-truth baseline:** `origin/main@802ed21cbba1d47c7b34ab2e344796acb6cccb56`  
**Scope:** live NATS/JetStream, all known agent lanes, identities/cards, repo and git seats, BoardStore/mobile board, holons, receipts, memory/graph roles, security, model continuity, and mobile operations.

## Executive verdict

The fleet has a working nervous-system prototype, not a seamless organism.

- **Proven live:** AGNI NATS/JetStream, AGNI semantic bridge, rushabdev bridge, durable Hermes reply/ack subjects, Tailscale between iPhone/rushabdev/Megha/Mac when Mac is awake, and a private auth-gated Mac board when Mac is online.
- **Not yet seamless:** only AGNI and rushabdev are genuinely live on the hub; identity routing collides on `dharma.a2a.hermes`; cloud agents rely on git/operator relay; the mailbox gateway is coded but undeployed; the mobile board lives on a Mac that is now offline; receipts and memories are fragmented across machine-local stores; AGNI model/auth and public HTTPS are degraded.
- **Repo design is ahead of deployment:** current `main` already contains a good target NATS contract, fleet field registry, mailbox gateway, onboarding path, BoardStore projection, and receipt taxonomy. The primary work is controlled cutover, deployment, and live failure testing—not another architecture rewrite.

## Scorecard

| Layer | Score | Evidence-based judgment |
|---|---:|---|
| Broker/transport availability | 70/100 | AGNI `4222` and `8443` reachable; stream healthy; replies durable for 72h. No cluster/replica and public HTTPS is down. |
| Identity and routing | 25/100 | AGNI, rushabdev, and `hermes` collide on `dharma.a2a.hermes`; FFR-D2 not applied; peer ACLs remain incomplete. |
| Persistent agent presence | 30/100 | AGNI + rushabdev live. Mac offline. Megha online in Tailscale but not A2A. Most cloud seats are relay/git only. |
| Shared board / operator SSOT | 25/100 | Mac board was reachable and fail-closed, but is now offline. Repo BoardStore facade is still in-memory with local SQLite event log. |
| Receipt integrity | 55/100 | Strong tier taxonomy and local receipts exist; no canonical live `DS_RECEIPTS`; many receipts remain machine-local. |
| Repo/build truth | 65/100 | GitHub `main` is active and now has field registry/runbook; openclaw working clone was 211 commits behind with dirty/local-only state. |
| Mobile control | 35/100 | Telegram direct chat and iPhone Tailscale work; board and Mac agent disappear when Mac sleeps/offlines. |
| Memory/graph coherence | 35/100 | Rich MemoryKernel/graph code exists, but no shared runtime projection or fleet-wide retrieval contract is live. |
| Model continuity | 30/100 | rushabdev has strong hosted models; AGNI reports expired/invalid model paths; Mac is offline; Megha is unverified. |
| Security/governance | 55/100 | Auth-gated Mac board and secret-free registry are good. ACL drift, plain NATS 4222, missing gateway identity, and inconsistent permissions remain. |

**Whole-system operational readiness: 40/100.** The pieces are substantial; the organism is not yet closed-loop.

## Live field evidence

### Transport

Live stream: `DHARMA_A2A` on AGNI.

- Broker: `nats://157.245.193.15:4222`
- WSS: `wss://157.245.193.15:8443`
- Messages at audit: 105
- Consumers: 19
- Retention: 259200 seconds / 72 hours
- Storage: file
- Reply/ack subjects are included for Hermes, fleet, Codex, and Perplexity.
- `rushabdev_hermes` can read stream info but is denied consumer-list and arbitrary sequence-get APIs.

Hub semantic audit receipt:

- packet: `a2a-full-audit-hub-1783734136-4e03f7`
- publish seq: `8118744`
- AGNI semantic session: `20260711_014219_ece18e`
- tier: `SEMANTIC_REPLY`

### Hub consumer problems

AGNI reported:

| Consumer | Filter | State |
|---|---|---|
| `agni_hermes_inbox` | `dharma.a2a.hermes` | healthy |
| `rushabdev_hermes_inbox` | `dharma.a2a.hermes` | healthy but identity-colliding |
| `hermes_inbox` | `dharma.a2a.hermes` | 41 pending |
| `claude_from_hermes` | `dharma.a2a.hermes` | 41 pending; never consumed |
| `test_reply_check` | one durable test reply subject | 1 ack-pending stale test |
| historical drill/fable consumers | historical filters | stale/idle |

### ACL truth

The field registry says FFR-D1 is ratified-not-applied. Live tests support that cautious status:

- direct publish from rushabdev to `dharma.a2a.fable_claude_code` was denied;
- subscription to `dharma.a2a.fleet.reply.>` and `.ack.>` was denied;
- a fleet rollcall publish succeeded at seq `8118747`, but rushabdev could not receive its replies;
- AGNI's hub report called FFR-D1 "applied" based on reply durability, but its own ACL listing shows rushabdev can publish only to fleet/Hermes subjects, not arbitrary peer inboxes. Therefore **reply durability is applied; publish-to-peer is not fully applied**.

FFR-D2 is definitely not applied. There is no unique live `dharma.a2a.rushabdev` subject.

### Node and agent presence

| Identity/node | Actual state |
|---|---|
| AGNI Hermes | Live hub semantic bridge; NATS/SAB infra anchor. |
| rushabdev Hermes | Live persistent bridge + Telegram gateway process. |
| hermes-m5 / Mac | Tailscale currently offline; registry stale; board offline. |
| meghadharma-cloud | Tailscale online; SSH port reachable previously; no verified A2A card/consumer/bridge. |
| Devin | Registry says operator relay; WSS egress blocked; live NATS never verified. |
| Fable Claude Code | Ephemeral git-seat/operator relay; no NATS credentials. |
| Codex/Megha seat | Operator relay only; no NATS daemon. |
| Perplexity Computer | Operator relay/git seat; no credentials. |
| Mike/Fable Cursor/Fable Composer/Qwen/SIS/etc. | cards/seats/consumers may exist; no fresh field receipt means not live. |

### Mobile board

When first probed, the Mac board at `100.74.45.73:9119` was reachable and correctly fail-closed:

- `/kanban` and `/chat` redirected to login;
- `/api/board` returned `401` without a cookie;
- no unauthenticated board data leaked.

At this audit, the Mac is offline and ports `9119`, `4222`, and `22` are unreachable. This proves the board cannot be the mobile operational SSOT while it is Mac-resident.

### AGNI service state

Running: NATS, AGNI Hermes bridge, Codex compatibility bridge, nodal ops, OpenClaw, SAB Agora.  
Failed/degraded: Caddy (port-80 conflict), `sab-app`, `codex-claude-sync`, and AGNI model routes (reported expired/unknown provider/model paths).  
Mailbox gateway port `8422`: closed / undeployed.

### Repository truth drift

The openclaw working clone was:

```text
main...origin/main [ahead 1, behind 211]
```

with multiple modified/untracked operational files. The field-probe commit `750b360f` was initially local-only, proving that local git receipts are not shared truth. It was later pushed and PR'd. Audit work was therefore performed in a detached worktree at current `origin/main@802ed21c`.

## Existing design that should be adopted, not replaced

Current shared `main` already defines:

1. `docs/governance/NATS_SUBSTRATE_MASTER_SPEC.md` — target subject/stream/ack contract.
2. `docs/ops/FLEET_FIELD_REGISTRY.yaml` — live connect-time registry, validated and secret-free.
3. `docs/ops/A2A_LIVE_WIRE_RUNBOOK.md` — exact ACL/gateway/daemon deployment steps.
4. `dharma_swarm/a2a/mailbox_gateway.py` — bearer-authenticated HTTPS send/drain gateway.
5. `scripts/governance/a2a_agent_onboard.py` — card/roster/seat/presence drift projection.
6. `dharma_swarm/board/*` — BoardStore facade, local event log, and receipt projections.
7. `dharma_swarm/operator_core/a2a_task_lifecycle.py` — typed task closure receipts.

Registry validation passed:

```text
[registry-check] OK — 6 probed agents, secret policy holds
```

The NATS contract checker failed because its live evidence was nine days stale. This is a freshness/projection problem, not proof that the broker is currently down.

Focused current-main tests passed when the declared async plugins were supplied:

```text
226 passed, 1 skipped in 6.19s
```

## Root architectural defects

### P0-1: Shared subject identity collision

Three identities consume/publish `dharma.a2a.hermes`. This makes routing, attribution, backlog ownership, and memory continuity ambiguous.

**Fix:** stable UID subjects only. Immediate compatibility subject:

- `dharma.a2a.rushabdev`

Target:

- `dharma.agent.<agent_uid>.inbox`
- `dharma.agent.<agent_uid>.outbox`

No two durable consumers representing different identities should share one identity subject.

### P0-2: ACLs prevent deep coordination

The fleet can publish some broadcasts but cannot reliably DM arbitrary peers or consume correlated fleet replies. Current ACLs also differ by agent and are inconsistent with the ratified model.

**Fix:** per identity:

- publish to peer inboxes + own outbox/reply/ack + fleet;
- subscribe only to own inbox/outbox/reply/ack + fleet + `_INBOX.>`;
- no broad peer subscription;
- gateway gets a dedicated least-privilege NATS user.

### P0-3: The mobile board is tied to the Mac

The board is useful but disappears when the Mac sleeps/offlines. It is a projection and collaboration surface, not a durable fleet authority.

**Fix:** deploy the board API/UI on an always-on VPS, preferably rushabdev as operator/revenue node, behind Tailscale + authentication. Mac and iPhone become clients. Board commands/events publish to NATS; the board DB is a projection/snapshot.

### P0-4: Cloud agents have no live door

Fable/Devin/Perplexity/Codex cloud seats use git/operator relay because direct broker egress or credentials are absent.

**Fix:** deploy the existing HTTPS mailbox gateway, give each agent a stable UID/token, and validate `whoami -> send -> own-inbox drain`. Git returns to code/spec evidence, not real-time messaging.

### P0-5: Live receipts are fragmented

Receipts exist in NATS reply subjects, `~/.dharma/a2a_bus`, Hermes session DBs, BoardStore SQLite, SAB, and git seats. There is no canonical live receipt stream/projector.

**Fix:** dual-publish typed receipts to `DS_RECEIPTS / dharma.a2a.receipt` while preserving filesystem mirrors. Receipt envelope must retain message, trace, correlation, causation, actor UID, authority, tier, artifact hash, and verification result.

### P1-1: Registry is declarative, not live presence

`FLEET_FIELD_REGISTRY.yaml` is excellent connect-time truth but only six agents are probed and seven known identities are unprobed. Local `agents.json` was stale despite live AGNI contact.

**Fix:** keep YAML as reviewed configuration/evidence SSOT; mirror live presence into JetStream KV with TTL heartbeats. UI must distinguish configured, transport-live, semantic-live, and domain-capable.

### P1-2: BoardStore is not yet a shared durable board

`BoardStoreFacade` explicitly uses an in-memory card dictionary. Its event log is local SQLite. Adapters are useful projections, but no single always-on shared board service owns command mutations.

**Fix:** commands enter through one authenticated board API and publish typed board command events. One durable projector owns card state/version/leases. Every node may run read projections; only the command owner mutates canonical state.

### P1-3: Model/runtime continuity is not guaranteed

AGNI reports broken model credentials/routes; Mac is offline; Megha is not onboarded. A2A transport can be alive while semantic handlers silently fail.

**Fix:** every persistent agent publishes provider/model health and has at least two remote providers or one remote + local fallback. Semantic SLOs are separate from transport SLOs.

## Canonical target architecture

```text
John/iPhone
   |
   | Tailscale + auth
   v
Always-on Mobile Board / Operator API (rushabdev VPS)
   |
   | typed commands/events
   v
AGNI NATS JetStream hub
   |-- DS_FLEET       presence/health
   |-- DS_AGENT_INBOX per-agent commands/messages
   |-- DS_TASKS       task claim/close lifecycle
   |-- DS_RECEIPTS    immutable typed receipts
   |-- DS_OPERATOR    hot-contact/operator events
   `-- DS_DLQ         exhausted failures
        |
        +-- persistent Hermes bridges/agents
        +-- Megha RSI/DGM lab agent
        +-- HTTPS mailbox gateway for cloud agents
        +-- projectors: board, graph, vector memory, telemetry
```

### Authority split

| Surface | Authority |
|---|---|
| NATS/JetStream | live ordered transport, durable delivery, replay, presence, command and receipt events |
| Board service | operator-visible task/card state projected from canonical events; authenticated mutation API |
| GitHub repo | code, schemas, reviewed decisions, cards, routing registry snapshots; never live delivery truth |
| Runtime receipts/object store | immutable detailed evidence, transcripts, artifacts, hashes |
| Vector memory | semantic retrieval projection; never command/task authority |
| Graph system | typed identity/capability/causality/provenance projection; never delivery authority |
| SAB | public/domain witness and attractor surface; not internal transport |
| Tailscale | private human/admin/node network; not sufficient for cloud/sandbox agents |
| Slack/Linear | optional notification/read projections only; not canonical coordination authority |

## Memory, vector, and graph integration

They are needed, but only as governed projections:

1. `DS_RECEIPTS`, `DS_TASKS`, and board events feed a memory/graph projector.
2. Large text/transcripts go to object storage; events carry content hashes and references.
3. Vector DB stores embeddings keyed by stable object/event IDs, trust tier, actor, event time, and valid time.
4. Graph stores agents, capabilities, tasks, artifacts, receipts, dependencies, causation, and aliases.
5. Retrieval returns citations/IDs and trust metadata. It cannot mutate board/task status.
6. Agent startup receives a compact context pack: own card, active tasks, latest receipts, unresolved dependencies, and selected semantic memory.

This solves the AGNI split-context problem without pretending one chat session is global memory.

## Phased leveling plan

### Phase 0 — Restore truth and unique identities (0–24h)

Owners: AGNI infra + rushabdev operator.

1. Apply FFR-D2: unique `rushabdev` subject, stream filter, consumer, and ACL.
2. Finish FFR-D1 rather than relabel reply durability as full peer publish.
3. Permit correlated fleet reply/ack subscriptions for the sender's own request namespace.
4. Clear/quarantine stale consumers only after exporting their state.
5. Add AGNI to the Tailscale admin plane.
6. Fix AGNI provider/model fallback and public HTTPS/Caddy conflict.
7. Refresh live NATS evidence so contract checks use current receipts.
8. Sync the openclaw checkout using a clean worktree; preserve dirty WIP into branches/PRs.

**Acceptance:** AGNI and rushabdev exchange unique-subject messages both directions, each reaches `HANDLER_ACKED` + semantic reply, no other identity consumes either inbox, and the command survives sender disconnect/reconnect exactly once.

### Phase 1 — Always-on mobile board + cloud door (24–72h)

1. Deploy Mac board service or equivalent UI/API on rushabdev VPS behind Tailscale/auth.
2. Connect board mutations to typed NATS commands; make Mac board a projection/client.
3. Deploy mailbox gateway on an HTTPS-reachable node; create dedicated gateway NATS user.
4. Mint one token per stable agent UID; cloud agents verify `whoami`, send, and drain own inbox.
5. Register/onboard `meghadharma-cloud` with card, registry entry, consumer, bridge, model health, and RSI/DGM capabilities.

**Acceptance:** from iPhone, John creates a card; a remote cloud agent receives it, comments, emits a receipt, and the mobile board updates while the Mac is powered off.

### Phase 2 — Canonical streams and receipt spine (3–7d)

1. Create `DS_FLEET`, `DS_AGENT_INBOX`, `DS_TASKS`, `DS_RECEIPTS`, `DS_OPERATOR`, and `DS_DLQ` alongside `DHARMA_A2A`.
2. Dual-publish legacy and target envelopes with `Nats-Msg-Id` idempotency.
3. Move presence to JetStream KV TTL records.
4. Run one board projector and one receipt projector on always-on VPS nodes.
5. Enforce correlation/causation fields and ack tiers at boundaries.

**Acceptance:** rebuild board state from streams into a blank DB; hashes/card versions match; repeated/replayed commands do not duplicate effects.

### Phase 3 — Deep coordination, memory, graph, and resilience (1–2w)

1. Feed canonical events into MemoryKernel/vector and DharmaGraph projectors.
2. Inject bounded cited context packs into every Hermes/holon wake.
3. Add model capability/health routing and per-node fallback.
4. Add chaos tests: agent kill, broker restart, network partition, expired token, poisoned message, stale command replay, projector rebuild.
5. Add SLO dashboard and urgent-only operator alerts; all routine automation stays local.

**Acceptance:** all persistent agents independently score >=90/100 understanding of current mission/roles using the same cited SSOT; a 24h mobile-only run completes tasks across at least three nodes with zero lost commands and complete receipt chains.

## SLOs and health gates

| Metric | Target |
|---|---:|
| JetStream publish ack | p95 < 500ms |
| Handler ack | p95 < 5s |
| Semantic reply | p95 < 90s |
| Board projection lag | < 2s |
| Presence TTL | 90s; stale after 2 missed heartbeats |
| Unacked commands | 0 older than ack wait |
| DLQ | 0 unexplained; every entry owns a card/blocker |
| Receipt completeness | 100% commands have publish + handler/domain closure chain |
| Identity collision | 0 shared durable identity subjects |
| Mobile dependency on Mac | 0 |
| Repo drift | persistent nodes fetch daily; no local-only closure claim |

## What not to do

- Do not make Slack, Linear, Telegram, Git, vector DB, graph DB, or a Mac-local app the live operational SSOT.
- Do not add another broker or board before deploying the existing gateway and target contract.
- Do not equate Tailscale visibility, a card, a stream consumer, a publish ACK, or a local receipt with semantic agent liveness.
- Do not broadcast every command to a shared subject and filter only in payloads.
- Do not replay old operator commands as fresh work after restart.
- Do not push raw runtime receipt floods into git; push reviewed registry snapshots/decisions and keep runtime evidence in durable streams/object stores.

## Immediate owner packet

| Owner | Next action |
|---|---|
| AGNI | Apply unique subjects/ACLs, expose consumer health, fix model fallback and HTTPS, prepare dedicated gateway user. |
| rushabdev | Move mobile board off Mac, update bridge to unique subject after hub change, maintain field registry and operator projection. |
| hermes-m5/Mac | Return as optional strategy/memory projection; no longer host canonical mobile board. |
| Megha | Install/register persistent Hermes bridge and declare RSI/DGM capabilities/model health. |
| cloud agents | Join via mailbox gateway stable UID/token; git seat remains code/evidence lane. |
| John | No laptop action required for design. When convenient, authorize AGNI ingress/ACL changes and Megha SSH key/onboarding. |

## Verification commands used

```bash
# live stream info from rushabdev credentials
python <nats-py stream_info audit>

# current shared repo
cd /home/openclaw/dharma_swarm
git fetch origin main
git worktree add --detach /tmp/hermes-verify-a2a-audit origin/main

# registry
uv run --frozen python scripts/runtime/fleet_field_registry.py --check

# focused implementation tests
uv run --frozen --with pytest --with pytest-asyncio --with pytest-timeout \
  pytest -q tests/test_a2a.py tests/test_a2a_e2e.py tests/test_a2a_gate.py \
  tests/test_a2a_send.py tests/test_a2a_reply_capture.py \
  tests/test_a2a_task_lifecycle.py tests/test_a2a_send_board_adapter.py \
  tests/test_holon_bridge.py tests/test_holon_runtime.py \
  tests/test_holon_persistence.py tests/test_control_surface_a2a_cards.py
# 226 passed, 1 skipped
```

## Conclusion

The future-proof move is not "NATS versus Linear/Slack." It is:

- NATS JetStream as the internal nervous system;
- one always-on authenticated mobile board as the operator projection;
- stable UID identities and unique inboxes;
- an HTTPS mailbox gateway for sandbox/cloud agents;
- typed receipt/event streams as operational truth;
- Git for reviewed code/config/decisions;
- vector and graph systems as cited learning projections.

Implementing the already-written Phase 0/1 contracts will create more real coordination than adding more conceptual holons. Once unique identity, delivery, board, and receipt loops are closed, holons can scale safely on top.
