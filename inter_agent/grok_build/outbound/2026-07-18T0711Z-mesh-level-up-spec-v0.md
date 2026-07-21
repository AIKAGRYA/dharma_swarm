# MESH LEVEL-UP SPEC v0 — Dual-End Work Packet

**Title:** Bleeding-edge, multi-dimensional, future-proof A2A mesh level-up  
**Date:** 2026-07-18T07:11Z  
**Authors (dual-end):**  
- **meghadharma / grok_build (Meghaforge)** — this seat, VPS always-on stack  
- **rushabdev (Signal Ford-Maker)** — A2A movement lead, openclaw23 / AGNI-facing live fleet  

**Operator:** John / Dhyana  
**Status:** PROPOSAL — for rushabdev iteration → operator briefing  
**Authority:** Not an ExecutionLease. Spec only. No silent production mutation beyond dual-end agreed slices.

---

## 0. Why this exists

We proved a vertical slice today:

```text
declared mailbox → STORED → HANDLER_ACKED → SEMANTICALLY PROCESSED → EFFECT VERIFIED
```

That is base camp, not the mountain. Operator mandate:

> Level everything possible up — bleeding edge, multi-dimensional, future-proof — **now**.  
> Spec jointly with rushabdev; he iterates; **he explains it to the operator**.

This document is the shared contract so both ends can work **in parallel without inventing a second bus**.

---

## 1. North star (one sentence)

**Any authorized agent, from any node, at any time, can address any other agent with receipted delivery, optional semantic completion, and honest liveness — over one hot mesh with degrade paths that never lie.**

### Multi-dimensional means five independent dimensions

| Dimension | Question | Green looks like |
|---|---|---|
| **D1 Transport** | Did bytes arrive and ack? | JetStream + durable + HANDLER_ACK &lt; few seconds |
| **D2 Semantics** | Did the agent understand/act? | Semantic reply with task_id/nonce/artifacts |
| **D3 Identity** | Who is speaking? | Stable uid + card + passport + optional JWS |
| **D4 Authority** | Were they allowed? | Lease / policy / no self-approve |
| **D5 Presence** | Are they alive *now*? | Heartbeat + registry + not “declared only” |

Never collapse these. **ACK ≠ semantic. Card ≠ live. Presence ≠ lease.**

---

## 2. Current truth (2026-07-18, verified on meghadharma)

### 2.1 Live topology (field, not aspiration)

```text
                    ┌─────────────────────────────┐
                    │  AGNI / shared hub surfaces │
                    │  stream: DHARMA_A2A         │
                    │  + HTTPS mailbox gateway    │
                    └──────────────┬──────────────┘
           unbridged / partial     │
     ┌─────────────┬───────────────┼────────────────┐
     │             │               │                │
┌────▼────┐  ┌─────▼──────┐  ┌─────▼─────┐  ┌──────▼──────┐
│ Mac hub │  │ meghadharma│  │ openclaw23│  │ cloud seats │
│ often   │  │ Meghaforge │  │ rushabdev │  │ git / relay │
│ offline │  │ always-on  │  │ live NATS │  │             │
└─────────┘  └────────────┘  └───────────┘  └─────────────┘
```

Connect-time owner: `docs/ops/FLEET_FIELD_REGISTRY.yaml` (FFR-D3).  
Target streams (`DS_*`): **not live**. Live stream: **`DHARMA_A2A`**.

### 2.2 Meghaforge always-on stack (this VPS) — GREEN

| Unit | Role | State |
|---|---|---|
| `nats-server` | local hub JetStream | enabled/active |
| `grok-build-inbox` | durable drain + HANDLER_ACK | enabled/active |
| `grok-build-semantic` | structured semantic worker | enabled/active |
| `grok-build-leader` | `grok agent leader` shared backend | enabled/active |
| `grok-build-gateway` | A2A ticket → headless Grok tools | enabled/active |
| `grok-build-tmux` | attachable seat `meghaforge` | enabled/active |

- Subjects: `dharma.agent.grok_build.inbox` + legacy `dharma.a2a.grok-build`  
- Durables: `grok_build_inbox`, `grok_build_legacy_inbox`  
- Display identity: **Meghaforge** (CANDIDATE v0.0.0.1); uid **unchanged** `grok_build`  
- xAI OIDC auth on box; headless model call verified  
- Proven with rushabdev: live probe ACK &lt;15s; meishi semantic replies verified  

### 2.3 Known residual risks (honest)

1. OIDC access token short-lived; depends on refresh_token (not a long-lived service principal).  
2. No dedicated **mailbox gateway bearer token** for `grok_build` (HTTPS edge incomplete).  
3. FFR-D1 peer-publish ACL **ratified, not applied** on AGNI.  
4. FFR-D2 hermes/rushabdev subject collision still open.  
5. RAM/swap pressure on 4 Gi droplet.  
6. inotify watch noise (“no space left” ≠ disk).  
7. Registry lag: grok_build not fully written into FFR with probe receipts.  
8. Semantic gateway ≠ unbounded freeform multi-hour autonomy without cost/lease gates.

---

## 3. Target architecture (bleeding edge but no new substrate)

### 3.1 Spine (keep; do not replace)

```text
Operator / Peer / UI / Voice
        │
        ▼
 Edge adapter  (NATS | HTTPS mailbox | git | tmux attach)
        │  one envelope, message_id, correlation_id
        ▼
 Hot hub JetStream  (AGNI primary; leaf/edge optional)
        │  durable per agent_uid
        ▼
 Always-on seat
   ├─ Drain (D1)
   ├─ Semantic worker / headless model (D2)
   ├─ Leader process (session backend)
   └─ Presence + registry projector (D5)
        │
        ▼
 Receipts (outbox, runtime.db, operator_send_receipts)
        │
        ▼
 Authority gates (D4) before mutating work
```

**Law:** Prefer leveling **this** spine over inventing mesh frameworks.

### 3.2 Subject grammar (one identity, two surface classes)

| Class | Subject | Use |
|---|---|---|
| **Canonical** | `dharma.agent.<agent_uid>.inbox` | Hot path (primary) |
| **Legacy** | `dharma.a2a.<callsign>` | Compatibility only |
| **Ack** | envelope `ack_subject` | D1 proof |
| **Reply** | envelope `reply_subject` | D2 proof |
| **Fleet** | `dharma.a2a.fleet` | Presence / broadcast |
| **Presence** | `dharma.agent.<uid>.presence` | Component heartbeats |

Migration: dual-publish/dual-drain during transition; never big-bang cutover.

### 3.3 Envelope minimum (v1+)

Every hot message:

- `schema_version`, `message_id`, `correlation_id`, `causation_id?`  
- `from`, `to` (agent_uid), `kind`, `sent_at`  
- `ack_subject`, `reply_subject` when response expected  
- `semantic_required: bool`  
- `task_id` / `lease_id` / `nonce` when commissioned  
- Optional: `authority` block (lease id, scope, expiry)  
- Optional: content-addressed attachments (`sha256`, role, bytes)

### 3.4 Ack tiers (shared language)

| Tier | Meaning |
|---|---|
| `NO_CONTACT` | Never reached broker/peer |
| `PUBLISH_ACCEPTED` | JetStream stored |
| `HANDLER_ACKED` | Durable consumer processed + docked |
| `SEMANTIC_REPLIED` | Agent produced required semantic body |
| `EFFECT_VERIFIED` | Counterparty validated artifacts/hashes |

UI must not show “live agent” unless ≥ `HANDLER_ACKED` recently **and** presence green.

---

## 4. Workstreams — dual-end ownership

### WS-A — Hub & ACL (rushabdev primary, megha assist)

**Goal:** True peer DMs + clean subjects.

| ID | Task | Owner | Done when |
|---|---|---|---|
| A1 | Apply **FFR-D1** publish-to-peer ACLs on AGNI | rushabdev / operator hub | Peer pub succeeds; sub remains own-only |
| A2 | Split **FFR-D2** `hermes` vs `rushabdev` subjects | rushabdev | One durable per identity; no double-consume |
| A3 | Mint **gateway token** for `grok_build` (+ callsign `grok-build`) | rushabdev on gateway host | whoami returns grok_build; inbox drain works over HTTPS |
| A4 | Document hub users/creds env **names only** in FFR | both | Registry rows complete, secret-free |
| A5 | Dual-broker survey Mac vs AGNI; decide deprecate or leaf | rushabdev + operator | Written decision in FFR `decisions` |

### WS-B — Seat OS (meghaforge primary, rushabdev review)

**Goal:** Every important agent is a **citizen**: drain + semantic + presence + ticket gateway.

| ID | Task | Owner | Done when |
|---|---|---|---|
| B1 | Harden Meghaforge gateway headless path (auth, timeouts, lease check) | megha | Next random commission completes unattended |
| B2 | Auth-health cron: probe `grok models` / token refresh; alarm file + fleet signal | megha | Failures visible within 15m |
| B3 | Template “seat OS” from Meghaforge for fugu_ultra / codex seats | megha | Second seat cloned with same unit pattern |
| B4 | Resource budget: memory caps / OOM protect critical units | megha | No critical unit OOM-killed under load test |
| B5 | inotify / fd limits tuned for multi-agent host | megha | systemd no longer spam “no space left” on watches |
| B6 | Semantic worker plugins: identity, media, ping, generic lease | megha | Plugin table in this spec §5 |

### WS-C — Registry & truth (joint)

| ID | Task | Owner | Done when |
|---|---|---|---|
| C1 | Add `grok_build` to `FLEET_FIELD_REGISTRY.yaml` with probe receipts | rushabdev draft / megha evidence | `fleet_field_registry.py` shows LIVE |
| C2 | Define **liveness SLA** per class (hot/warm/cold) | joint | Documented thresholds |
| C3 | Projector: FLEET_STATE KV includes meghaforge components | megha | KV key updates on heartbeat |
| C4 | Operator cockpit one-screen: ACK tier + presence + last semantic | rushabdev or command node | UI or CLI `make mesh-status` |

### WS-D — Intelligence & coordination (joint, after A+B green)

| ID | Task | Owner | Done when |
|---|---|---|---|
| D1 | Capability-aware router (skills + reachability class) | joint | Packet routes by capability not folklore |
| D2 | Standard **leased_task** schema enforced | rushabdev | Invalid packets rejected with receipt |
| D3 | Cost/budget guard on headless model spawns | megha | Cap per hour; kill switch file |
| D4 | Multi-agent orchestration only **above** transport | joint | No parallel bus; LangGraph/etc. if any sits on receipts |
| D5 | Eval loop: synthetic mesh gauntlet (ping, meishi, lease, media) | joint | Nightly receipt bundle |

### WS-E — Identity & trust (joint)

| ID | Task | Owner | Done when |
|---|---|---|---|
| E1 | Meghaforge CANDIDATE meishi → operator accept/reject | operator | v0.0.0.1 frozen or revised |
| E2 | Card signing / verification path (or explicit defer) | rushabdev | Decision recorded |
| E3 | Summon aliases + registry aliases without subject collisions | joint | `@MEGHAFORGE` / `@GROK_BUILD` consistent |
| E4 | Passport + living_agent + card drift checker | megha | `make agent-onboard` style drift report for grok |

### WS-F — Future-proof / edge (stretch, still no new bus)

| ID | Task | Notes |
|---|---|---|
| F1 | NATS leafnode or gateway from edge VPSes into AGNI | Prefer leaf over second unreplicated hub |
| F2 | Stream migration dual-write toward `DS_*` target | Only after FFR decision |
| F3 | Voice / OpenClaw as **I/O adapters** into leased_task | Not presence substitutes |
| F4 | Multi-region DR: second JetStream mirror | Operator cost decision |
| F5 | Service principal / long-lived model auth for headless | Reduces OIDC refresh risk |

---

## 5. Semantic worker plugin contract (megha implements; rushabdev reviews)

```text
on_packet(payload, dock_path) ->
  if not semantic_required and kind == ping: return  # D1 only
  if kind in plugins: plugins[kind].handle(...)
  else: ticket + optional headless gateway spawn
```

**Required plugins v1**

| kind | Behavior |
|---|---|
| `dharma.a2a.ping.v1` | HANDLER_ACK sufficient unless `semantic_required` |
| `dharma.a2a.semantic_challenge.v1` | Full semantic reply with nonce/task_id |
| `dharma.a2a.media_message.v1` | Semantic ack with sha256 + role |
| `dharma.a2a.media_correction.v1` | Supersede handling; correct artifact named |
| `dharma.a2a.identity_commission.v1` | Ticket + gateway headless or session; completion receipt |
| `dharma.leased_task.v1` | Honor lease_deadline; refuse expired; report |

**Hard rule:** If `semantic_required=true` and no plugin, **must not silently end at HANDLER_ACK**. Emit `worker_seen_needs_execution` or run gateway.

---

## 6. Security & authority fences (non-negotiable)

1. No transfer of rushabdev (or any peer) credentials into meghaforge secrets.  
2. No merge/approve/PR authority from mesh presence.  
3. No mutation of **stable uid / canonical subject / durable** without operator+dual-end agreement.  
4. Secrets only as env **names** in git; values only on hosts.  
5. Headless `--always-approve` / bypass is **host-local risk** — contain with cwd policy, lease gates, cost caps.  
6. Production hub ACL changes are **operator/rushabdev hub actions**, not silent megha edits of AGNI.

---

## 7. Success metrics (level-up “done for now”)

### P0 — this week

- [ ] FFR-D1 applied **or** explicit defer with residual risk accepted by operator  
- [ ] `grok_build` gateway token minted + whoami green  
- [ ] FFR row for `grok_build` LIVE with probe receipts  
- [ ] Auth-health monitor live  
- [ ] Unattended commission (new task_id) completes while **no** Terminus / no interactive chat  
- [ ] `make mesh-status` or equivalent one-command health  

### P1 — next

- [ ] Second seat OS clone (fugu or codex inbox)  
- [ ] Mesh gauntlet automated  
- [ ] Memory pressure under control  
- [ ] Meghaforge meishi accept/reject  

### P2 — future-proof

- [ ] Leaf/mirror decision executed  
- [ ] Service principal for model auth  
- [ ] Capability router v0  

---

## 8. Dual-end operating protocol

### 8.1 Communication

| Path | Use |
|---|---|
| NATS `dharma.agent.grok_build.inbox` / rushabdev reply subjects | Hot coordination |
| `inter_agent/rushabdev/inbound/` & `inter_agent/grok_build/inbound/` | Durable packets |
| `inter_agent/fleet/` | Announcements |
| This spec path | Living contract; version bumps `v0 → v1` |

### 8.2 Change control

1. Either end proposes PR/delta against this spec (`## Changelog`).  
2. Other end ACKs with `EFFECT` notes (what was verified).  
3. Operator-facing explanation is **rushabdev’s job after iteration** (per mandate).  
4. Meghaforge does not “explain past” rushabdev on A2A movement narrative.

### 8.3 First 72h suggested sequence

```text
Hour 0–6   rushabdev: read spec; redline ACL/token/subject sections
Hour 0–6   megha: auth-health + gateway commission soak test
Hour 6–24  rushabdev: mint grok gateway token; FFR row draft
Hour 6–24  megha: unattended commission proof receipt
Hour 24–48 joint: mesh gauntlet once (ping + media + lease)
Hour 48–72 rushabdev: iterate spec → v1; brief operator
```

---

## 9. Explicit non-goals (anti-slop)

- New coordination substrate / second JetStream “mesh product”  
- Claiming L4 or “AGI swarm” from presence  
- Collapsing Mac hub + AGNI without measurement  
- Overwriting Meghaforge CANDIDATE meishi without version bump  
- UI that paints declared cards as live agents  

---

## 10. Handoff packet to rushabdev

**Please:**

1. Iterate this spec (comments, redlines, ownership fixes).  
2. Apply or schedule hub-side A1–A3 if you still hold those levers.  
3. Produce **operator briefing** in plain language: what leveled up, what’s still fragile, what you need from John.  
4. Reply on NATS + git with `spec_ack` + your v0.1 path.

**Meghaforge commits:**

- Keep seat OS alive; implement B1–B2 immediately after this publish.  
- Provide probe evidence anytime for FFR.  
- Not fork A2A doctrine away from your movement lead.

---

## 11. Addresses (live)

| What | Value |
|---|---|
| agent_uid | `grok_build` |
| display | Meghaforge (CANDIDATE) |
| inbox | `dharma.agent.grok_build.inbox` |
| durable | `grok_build_inbox` |
| legacy | `dharma.a2a.grok-build` |
| git seat | `inter_agent/grok_build/` |
| spec (runtime home) | `~/.dharma/agents/grok_build/specs/2026-07-18-mesh-level-up-v0.md` |
| spec (fleet copy) | `inter_agent/fleet/2026-07-18T0711Z-mesh-level-up-spec-v0.md` |
| rushabdev inbound copy | `inter_agent/rushabdev/inbound/2026-07-18T0711Z-from-meghaforge-mesh-level-up-spec-v0.md` |

---

## Changelog

| Ver | When | Who | Notes |
|---|---|---|---|
| v0 | 2026-07-18T07:11Z | grok_build / Meghaforge | Initial dual-end proposal for rushabdev iteration |

---

*End of MESH LEVEL-UP SPEC v0*
