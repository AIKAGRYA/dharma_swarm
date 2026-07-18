# NATS / A2A System Update Specification

**Document ID:** `NATS_A2A_SYSTEM_UPDATE_SPEC_2026-07-18`  
**Status:** DRAFT SPECIFICATION — implementation-ready doctrine; **not** a migration authorization  
**Date:** 2026-07-18  
**Author seat:** `grok_build` (display: Meghaforge) on `meghadharma-cloud`  
**Task / lease:** `grok-build-nats-a2a-system-spec-20260718` / `grok-build-nats-a2a-system-spec-20260718:1:grok_build`  
**Receipt class:** `semantic_reply`  
**Companion:** `docs/architecture/NATS_A2A_SYSTEM_UPDATE_SPEC_2026-07-18.json`  
**Base SHA (origin/main at authoring):** `135a18300c5e4be9fce641e901adc046b837e653`  
**Live probe window:** `2026-07-18T07:30:44Z` … `2026-07-18T07:32:24Z` UTC  

> **Non-action boundary.** This document specifies what to build and which gates must close. It does **not** authorize broker migration, credential rotation, service restarts, stable-UID renames, or production cutover. No live migration, credential rotation, or restart was performed while authoring this spec.

---

## 1. Executive verdict and target state

### Verdict

The Dharma Swarm NATS/A2A estate is **functionally multi-homed, grammatically split, and receipt-honest only in fragments**. Live delivery works on at least two JetStream authorities that both name a stream `DHARMA_A2A`, while the repository target grammar (`DS_*` + `dharma.nats.envelope.v1`) is **not live on either**. Always-on drain/ACK services exist (Meghaforge inbox + semantic worker are a vertical proof), but fleet-wide semantic runtime, unique-identity enforcement, Object Store external upload lanes, AGNI↔Meghadharma mirror/cutover, and dashboard truth-binding are incomplete.

### Target state (one sentence)

**One logical writable coordination fabric** where every agent has a unique stable UID, subject, durable, scoped credential, and declared semantic runtime; where publish / handler ACK / semantic processing / effect commit / completion are distinct, receipted states; where large artifacts move by content-addressed Object Store; where external agents join only through a credentialless-to-internal gateway; and where dashboards project KV/object/receipt truth without draining worker durables.

### What “done” is **not**

- Not “one shared NATS password for the fleet.”  
- Not “filesystem dock success equals live contact.”  
- Not “handler ACK equals semantic completion.”  
- Not a flag-day simultaneous change of broker + identity + grammar + schema.  
- Not SUBSTRATE_TRUSTED until gates in §§15–16, 22–23 close with evidence.

---

## 2. Authority-by-plane table

| Plane | Owns | Does not own | Live authority today (probed / declared) |
|---|---|---|---|
| **GitHub (`dharma_swarm` main)** | Versioned grammar, specs, registration cards, ops registries, CI gates | Live delivery, retained stream sequences, KV revisions | Canonical for doctrine; SHA `135a18300c5e…` at authoring |
| **NATS/JetStream (delivery)** | Publish, durable consumers, redelivery, pub-ack, retained messages | Semantic meaning, git truth, dashboard authority | **Two unbridged authorities:** AGNI + Meghadharma (both use stream name `DHARMA_A2A`) |
| **JetStream KV** | Governed shared projections, leases, board/task keys, presence snapshots | Delivery of work messages; semantic completion | **Meghadharma** bucket `FLEET_STATE` (backing stream `KV_FLEET_STATE`, last_seq **287** at probe) |
| **JetStream Object Store** | Large artifacts, content-addressed blobs, manifests | Inline chat payloads; internal broad NATS identity for externals | **Meghadharma** bucket `FLEET_ARTIFACTS` (backing `OBJ_FLEET_ARTIFACTS`, last_seq **16**) |
| **Dashboards / Command Node / Grafana** | Read-only projection of KV/object/receipts | Worker durables, task authority, green status without receipts | Local API `127.0.0.1:8420` online; fleet API unauthorized without bearer; risk of local-projection detachment remains |
| **Filesystem docks (`~/.dharma/a2a_bus/**`)** | Mirrors, human inspection, offline evidence | Live-contact proof, ordering, retry | Active mirrors on meghadharma (inboxes/outboxes/semantic_*) |
| **HTTPS mailbox gateway** | External/sandbox edge without broad NATS creds | Internal superuser authority | Code present (`mailbox_gateway.py`); operator deploy steps still runbook-owned |
| **Temporal / workflow engines** | Long-running durable workflows (future/optional) | Fleet message bus | Not the A2A hot path (master spec) |

**Doctrine (unchanged, reaffirmed):** GitHub owns grammar; JetStream owns live delivery and retained transport state; KV/object own governed shared projections/artifacts; dashboards are projections; filesystem docks are mirrors.

---

## 3. Sanitized live topology and evidence timestamps

### 3.1 Hosts and reachability (probe `2026-07-18T07:30:44Z`–`07:32:24Z`)

| Edge | Observation | Confidence |
|---|---|---|
| **meghadharma-cloud** | Host of this session; `nats-server` 2.10.9 listening `*:4222`, monitoring `127.0.0.1:8222`, websocket TLS `*:9443` | Direct |
| Local JetStream | Healthz `ok`; JetStream storage ~55 MB; 3 streams, 5 consumers, ~44.8k messages | Direct (HTTP monitoring) |
| AGNI `157.245.193.15:8443` (WSS) | TCP reachable (~2 ms) from meghadharma | Direct TCP |
| AGNI `157.245.193.15:4222` (plain NATS) | TCP **timeout** from meghadharma | Direct TCP |
| AGNI stream/consumer inventory | **Unknown this session** (no scoped credentials used; no remote monitoring exposed) | Inaccessible |
| Mac local hub `127.0.0.1:4222` / `DHARMA_FLEET` | Not on this host; historically unbridged / often offline | Repo + registry |
| Rushabdev edge | Live websocket client name `codex_composer/rushabdev` seen on Meghadharma `connz` from `167.172.95.184`; durable `rushabdev_v2_inbox` exists on Meghadharma | Partial |
| Grok / Meghaforge durables | `grok_build_inbox` + `grok_build_legacy_inbox` active on Meghadharma | Direct |

### 3.2 Meghadharma JetStream (sanitized; source: `http://127.0.0.1:8222/jsz`)

| Stream | Subjects | Retention / storage | Messages / last_seq | Consumers (filter) | Notes |
|---|---|---|---|---|---|
| **`DHARMA_A2A`** | `dharma.a2a.>`, `dharma.agent.>` | limits / file / discard old / max_age **0** / replicas **1** / dup window 120s | **44813+** / **44814+** (rising during probe) | `fleet_presence_projector` → `dharma.agent.*.presence` (push); `grok_build_inbox` → `dharma.agent.grok_build.inbox`; `grok_build_legacy_inbox` → `dharma.a2a.grok-build`; `rushabdev_v2_inbox` → `dharma.a2a.rushabdev` (max_deliver 5, deliver new); `fugu_ultra_inbox` → `dharma.agent.fugu_ultra.inbox` | Broad capture stream; **no** `DS_*` streams present |
| **`KV_FLEET_STATE`** | `$KV.FLEET_STATE.>` | limits / file / history **16** / deny_delete true / allow_rollup true | 32 live msgs / last_seq **287** | 0 | Shared board/presence projection store |
| **`OBJ_FLEET_ARTIFACTS`** | `$O.FLEET_ARTIFACTS.C.>`, `$O.FLEET_ARTIFACTS.M.>` | limits / file / allow_direct true | 14 msgs / last_seq **16** | 0 | Object Store for large artifacts |

**NATS config shape (sanitized `/etc/nats-server.conf`):** auth required; users include superuser-class principals (`rushabdev_hermes`, `a2a_gateway` with publish/subscribe `>`), scoped agent users (`grok_build`, `fugu_ultra`, `hermes`, `codex_*`, `dharma_command`), JetStream `max_file: 1GB`, no cluster/gateway/leaf routes configured.

**Active client names observed (connz sample):** `codex_composer/meghadharma`, `codex_composer/agni` (WS from AGNI IP), `codex_composer/rushabdev` (WS from rushabdev IP).

### 3.3 Meghaforge always-on stack (systemd, active at probe)

| Unit | Role |
|---|---|
| `nats-server.service` | Local JetStream hub |
| `grok-build-inbox.service` | Durable drain + HANDLER_ACK path |
| `grok-build-semantic.service` | Structured semantic worker (can mark `worker_seen_needs_execution`) |
| `grok-build-leader.service` | Shared Grok agent leader backend |
| `grok-build-gateway.service` | Headless work gateway |
| `grok-build-tmux.service` | Attachable seat |
| `dharma-fleet-status-projector.service` | Projects presence into `FLEET_STATE` |
| `dharma-meghadharma-hermes-bridge.service` | Hermes semantic bridge on host |

Credential env **names** for Grok lane (`/etc/dharma/grok-build-a2a.env`): `NATS_URL`, `NATS_USER`, `NATS_PASSWORD`, `NATS_STREAM`, `AGENT_UID`, `CALLSIGN`, `CANONICAL_SUBJECT`, `LEGACY_SUBJECT`, `DURABLE`, `LEGACY_DURABLE`, `INBOX_DIR`. Values never printed.

### 3.4 Repo-declared live vs target (code/docs)

| Item | Location | Value |
|---|---|---|
| Live compatibility stream constant | `scripts/runtime/a2a_topology.py` | `DHARMA_A2A` |
| Target task/DLQ streams | same + master spec | `DS_TASKS`, `DS_DLQ` |
| `A2ANatsTransport` default stream | `dharma_swarm/a2a/nats_transport.py` `NatsTransportConfig` | **`DS_TASKS`** (target; not live) |
| Operator send envelope | `scripts/runtime/a2a_send.py` | `dharma.a2a.send.v1` → `dharma.a2a.<agent>` |
| Canonical envelope schema | `nats_transport_support.py` | `dharma.nats.envelope.v1` |
| Field registry hub | `docs/ops/FLEET_FIELD_REGISTRY.yaml` | Still stamps **AGNI** as hub; updated **2026-07-14**; FFR-D1 `RATIFIED_NOT_APPLIED` |
| SAB workstream map (external repo) | dharmic-agora `SAB_IGNITION_WORKSTREAM_MAP.md` | AGNI = compatibility transport; Meghadharma = durable KV/object hub |

### 3.5 Inaccessible / unknown (explicit)

- Full AGNI stream subject inventory, consumer list, message counts, ACL effective state after any 2026-07-18 changes.  
- Whether AGNI and Meghadharma share any jetstream mirror/source link (monitoring shows **0 routes, 0 gateways** on Meghadharma).  
- Exact dashboard data source binding in the running Command Node release (API requires auth; not scraped).  
- Object-store principal grants for external agents (Grok principal lacks Object Store API grants in published ACL shape).  
- Mac hub liveness at probe time.

---

## 4. Contradiction / mismatch ledger (repo vs deployed vs intended)

| ID | Area | Repo / intended | Deployed / observed | Risk | Severity |
|---|---|---|---|---|---|
| **M1** | Stream grammar | Target `DS_*` streams in master spec | No `DS_*` on Meghadharma; live = `DHARMA_A2A` broad capture | Agents seeking `DS_TASKS` find nothing; dual mental models | **P0** |
| **M2** | Dual authorities | One internal fleet transport | AGNI + Meghadharma both host `DHARMA_A2A`, unbridged | Split-brain; silent peers; false “I published” claims | **P0** |
| **M3** | Field registry staleness | FFR is connect-time SSOT | Registry still: AGNI hub, FFR-D1 not applied, rushabdev shares `dharma.a2a.hermes` | Operators follow stale ACL/subject truth | **P0** |
| **M4** | Rushabdev subject | FFR-D2 open / shared hermes | Meghadharma durable `rushabdev_v2_inbox` filters **`dharma.a2a.rushabdev`** | Registry vs wire drift | **P1** |
| **M5** | Envelope grammar | `dharma.nats.envelope.v1` for tasks | Live hot path uses `dharma.a2a.send.v1` / `semantic_message.v1` | Dual parsers; incomplete idempotency on compat path | **P0** |
| **M6** | Transport owner | `A2ANatsTransport` is “canonical” | Defaults to `DS_TASKS`; **no production always-on caller** proven; live contact is `a2a_send.py` + per-agent drains | Canonical path orphaned | **P1** |
| **M7** | Ack tier honesty | PUBLISH ≠ HANDLER ≠ DOMAIN | Some services drain/ACK without semantic effect; auto worker may publish `worker_seen_needs_execution` | False-green if UI collapses tiers | **P0** |
| **M8** | Filesystem as delivery | Spec forbids FS as live proof | Docks still used as primary lane for cloud seats | False completion, missing redelivery | **P1** |
| **M9** | Superuser principals | Scoped per-agent ACL doctrine | `rushabdev_hermes` and `a2a_gateway` allow `>` | Credential compromise = full bus | **P0** |
| **M10** | Object Store access | Content-addressed large files | `FLEET_ARTIFACTS` exists; Grok ACL has **no** `$O` / Object Store API grants | Large artifacts blocked for agent principals | **P1** |
| **M11** | Overlapping wildcards | No overlapping stream ownership without decision | Single broad stream owns both `dharma.a2a.>` and `dharma.agent.>` — OK today; becomes conflict when `DS_*` added **without** narrowing | Future stream creation fails or doubles | **P1** |
| **M12** | Identity surfaces | One UID/card/durable | Six+ surfaces (repo card, runtime card, passport, presence roster, git seat, NATS user) without continuous reconciler | Ghost / invisible / unaddressable agents | **P1** |
| **M13** | Dashboard truth | Project KV/object/receipts | Risk of local filesystem projection and auth-gated API detachment | Operator false-green | **P1** |
| **M14** | External onboarding | Gateway + tokens | Gateway code shipped; operator deploy incomplete per runbook | Sandbox agents stuck on git | **P1** |
| **M15** | Historical credential exposure | Rotate after exposure | Spec records **need** to rotate; values must never reappear | Ongoing compromise window until operator rotates | **P0** (ops) |
| **M16** | `A2ANatsTransport` vs topology defaults | Topology defaults compat stream | Transport defaults target stream | New code paths silently point at empty streams | **P1** |
| **M17** | Consumer max_deliver | Master: max_deliver 3–5 + DLQ | Several Meghadharma durables use `max_deliver: -1` | Poison messages can loop forever | **P1** |
| **M18** | Stream max_age | Master: 7–90 days | Meghadharma `DHARMA_A2A` max_age **0** (unbounded until disk) | Disk fill / restore size risk | **P2** |

---

## 5. One logical bus decision: source, candidate, compatibility, retirement

### Decision (recommended)

| Role | Authority | Why |
|---|---|---|
| **Source (live compatibility transport until Stage-A closes)** | **AGNI** `DHARMA_A2A` for historically fleet-facing subjects **and** any edge still pointed at AGNI | Field registry + agent cards still name AGNI; WSS rendezvous is the long-standing shared address; SAB map still uses AGNI for dispatch sequences |
| **Candidate durable hub (governed state + progressive cutover target)** | **Meghadharma** JetStream: `DHARMA_A2A` + `FLEET_STATE` + `FLEET_ARTIFACTS` | Already hosts KV/object stores, presence projector, Meghaforge always-on semantic stack, multi-node composer heartbeats, and is operator-visible board home |
| **Not yet canonical alone** | Either hub in isolation | No proven complete mirror, no dual-read parity gate, no retirement of the other writer |

### Compatibility rules

1. Preserve current subjects, packet IDs, and handler-ACK semantics during Stage-A.  
2. One **logical** writable task/message authority per subject family after cutover — not “two writers, hope consumers merge.”  
3. Mirrors must preserve `message_id` / `Nats-Msg-Id` and dedupe by idempotency key.  
4. Filesystem docks remain mirrors only.  
5. Do not rename stream `DHARMA_A2A` during Stage-A; Stage-B introduces purpose streams after subject narrowing.

### Retirement gates (all required)

- Dual-read parity report for N consecutive hours (see §15).  
- All required durables re-pointed and pending=0 on retired writer for drained subjects.  
- Rollback drill succeeded once.  
- Field registry + cards + env templates updated in git **before** retirement claim.  
- Operator explicit ACCEPT on migration packet (not this draft PR).

---

## 6. Stable identity grammar

### 6.1 Separated planes (never collapse)

| Plane | Field | Rules |
|---|---|---|
| **Stable UID** | `agent_uid` | Slug: `[A-Za-z0-9_-]+`; no `. * > /` whitespace; durable consumer names derive from it |
| **Display name** | `display_name` | Human only (e.g. `Meghaforge`); never a subject token |
| **Callsign / alias** | `callsign`, summon aliases | May differ from UID (`grok-build` vs `grok_build`); must map 1:1 in alias table |
| **Subject (canonical)** | `dharma.agent.<agent_uid>.inbox` | One primary inbox subject per UID |
| **Subject (legacy compat)** | `dharma.a2a.<callsign>` | Optional dual-drain during migration only |
| **Durable** | `<agent_uid>_inbox` (+ optional `_legacy_inbox`) | Unique; never shared across UIDs |
| **Credential** | NATS user name = UID or explicit map | Scoped publish/subscribe; env **names** only in git |
| **Signing key** | Card JWS / agent key id | Distinct from NATS password; rotation independent |
| **Host / model / shell** | `host`, `provider`, `model`, `harness` | Embodiment metadata; **not** identity |

### 6.2 Uniqueness law

- One UID → one primary durable → one semantic runtime declaration → one scoped credential principal.  
- Two identities must never share a filter subject (FFR-D2 generalized).  
- Observer/projector consumers use **separate** durables/filters (e.g. presence only); they must not share worker inbox durables.

### 6.3 Registration surfaces (reconcile continuously)

1. Repo card: `examples/agents/<uid>.registration.json`  
2. Runtime card: `~/.dharma/a2a/cards/`  
3. Passport / external agent record  
4. Presence roster (`agent_presence.REGISTERED_AGENT_UIDS`)  
5. NATS user + durable (ops)  
6. Git seat: `inter_agent/<uid>/`  

`make agent-register` drift check is mandatory in CI and onboarding.

---

## 7. Canonical envelope and schema versioning

### 7.1 Target envelope (Stage-B mandatory for new task path)

Schema: `dharma.nats.envelope.v1` (already coded in `nats_transport_support.py`).

Required fields:

| Field | Purpose |
|---|---|
| `schema` | Envelope version |
| `message_id` | Stable unique id; also `Nats-Msg-Id` header |
| `trace_id` / `span_id` / `parent_span_id` | OTel causality |
| `correlation_id` | Ties request/reply/receipts |
| `causation_id` | Prior message_id |
| `subject` | Publish subject |
| `from_agent` / `to_agent` | **Advisory only** — sender of record comes from authenticated principal |
| `kind` | heartbeat / command / task / receipt / health / event / … |
| `created_at` | UTC ISO |
| `requires_ack` | bool |
| `payload` | Typed object with nested schema |
| `actor` / `causality` | Structured extensions already present in wire helpers |
| `task_id` / `lease_id` / `idempotency_key` | Lifecycle (required for leased work) |

Task payload schema: `dharma.a2a.nats_task.v1`.  
DLQ payload: `dharma.nats.dlq_failure.v1`.

### 7.2 Compatibility envelopes (Stage-A retained)

| Schema | Use | Ceiling claim |
|---|---|---|
| `dharma.a2a.send.v1` | `a2a_send.py` operator/compat send | Up to HANDLER_ACKED if peer acks |
| `dharma.a2a.semantic_message.v1` | Semantic request/reply on live bus | Semantic only if body is typed semantic receipt |
| `dharma.a2a.domain_receipt.v1` | Domain effect | DOMAIN_RECEIPTED / EFFECT_COMMITTED evidence |
| Gateway `a2a_gateway_message.v1` | HTTPS mailbox | Publish accepted + gateway receipt |

### 7.3 Versioning rules

- Additive fields allowed within a major schema string; breaking changes mint `*.v2`.  
- Publishers must set `Nats-Msg-Id = message_id`.  
- Receivers must ignore unknown fields; must fail closed on missing required fields for the claimed schema.  
- **Never** treat untyped string body as a fleet message at the canonical path.

### 7.4 Sender provenance rule

`from_agent` in payload is **not** trust. Trust order:

1. Authenticated NATS user / gateway token → `agent_uid`  
2. Optional message signature verifying that UID  
3. Payload `from_agent` must match (1) or message is rejected / quarantined  

Reply subjects must be derived from authenticated identity + validated correlation metadata, not free-form attacker-chosen routes that hijack another agent’s reply durable.

---

## 8. Task / lease lifecycle state machine

```text
QUEUED → LEASED → STORED → HANDLER_ACKED → PROCESSED → EFFECT_COMMITTED → COMPLETED
                 ↘ (optional) FAILED / REJECTED / EXPIRED / DLQ
```

| State | Meaning | Evidence artifact |
|---|---|---|
| **QUEUED** | Work admitted to coordination plane | KV board key or task stream message not yet leased |
| **LEASED** | Exclusive worker claim via CAS/lease | KV revision / lease_id; fencing token |
| **STORED** | Broker retained the work message | JetStream pub-ack stream+seq |
| **HANDLER_ACKED** | Identity-bound consumer drained + handler ack step done | Handler ack subject payload + consumer ack; **not** semantic |
| **PROCESSED** | Semantic runtime produced a typed interpretation/result | Semantic receipt with task_id/lease_id |
| **EFFECT_COMMITTED** | Side effect applied exactly-once (git, SAB, tool, store) | Domain receipt + IdempotencyRecord complete |
| **COMPLETED** | Terminal success after effect + reply/receipt projection | Terminal status on board + receipt chain |
| **FAILED / REJECTED / EXPIRED / DLQ** | Terminal or park states | Typed failure envelope; DLQ message |

### Mapping to A2A 1.0 task status (`a2a_server.py`)

A2A statuses (`SUBMITTED`, `WORKING`, `COMPLETED`, …) remain the **application** task model. The table above is the **transport/coordination** ladder. UIs must show both; never collapse.

### Ack-tier ladder (transport honesty)

`PUBLISH_ACCEPTED` < `DELIVERED_TO_CONSUMER` < `HANDLER_ACKED` < `PROCESSED` < `EFFECT_COMMITTED` / `DOMAIN_RECEIPTED`.

Operator hot contact requires at least `HANDLER_ACKED`. Collaboration claims require `PROCESSED`+. Production effect claims require `EFFECT_COMMITTED`.

---

## 9. Idempotency, replay, late-result, DLQ, dedup

### 9.1 Keys

| Key | Scope |
|---|---|
| `message_id` / `Nats-Msg-Id` | Broker dedup within stream duplicate window |
| `idempotency_key` + `side_effect_key` | RuntimeState `IdempotencyRecord` CAS (first-writer-wins) |
| `task_id` + `lease_id` | Human/ops correlation; not alone sufficient for effects |
| Content hash (artifacts) | Object Store integrity |

### 9.2 Rules

1. **At-least-once delivery** on JetStream pull durables; **exactly-once effects** only via idempotency at the write boundary (already wired pattern in `runtime_state` / `A2ANatsTransport`).  
2. Redelivery after ack-wait must not create a second effect if the first committed.  
3. Late semantic results for expired leases: accept only if lease fencing token still valid **or** result is pure observation; otherwise store as `LATE_RESULT` without effect.  
4. `MaxDeliver` exhausted → publish typed DLQ envelope to `dharma.dlq.<stream>.<consumer>`; emit operator blocker; do not silent-ack poison.  
5. Compat path (`a2a_send.py`) must not claim effect commit.  
6. Replay consumers (`DeliverAll` audit) must use separate durables and never drive side effects.

### 9.3 External pattern alignment

- NATS JetStream: durable consumers, explicit ack, redelivery, per-stream dedup via `Nats-Msg-Id`.  
- Temporal: activities at-least-once → **require idempotent side effects**.  
- A2A: task lifecycle is not by itself proof of domain truth.

---

## 10. Persistent semantic-worker architecture

### Modes

| Mode | Description | When |
|---|---|---|
| **Always-on** | systemd/compose service: drain durable → HANDLER_ACK → invoke semantic runtime → publish typed reply | Production fleet agents (Meghaforge pattern) |
| **Event-driven** | Wake on message / queue depth / cloud webhook → process N messages → exit | Cost-sensitive seats |
| **Manual seat** | Human-attached shell (tmux) processes tickets left by worker | Heavy tools, interactive approval |

### Separation of duties (Meghaforge reference)

1. **Inbox drain** (`grok-build-inbox`): JetStream pull, persist mirror dock, publish ack, broker-ack.  
2. **Semantic worker** (`grok-build-semantic`): Read dock/ticket, produce structured semantic reply **or** `needs_session` ticket.  
3. **Session/leader** (`grok-build-leader` / interactive): Full tool execution for complex commissions.  

**Law:** Drain without semantic runtime may only claim `HANDLER_ACKED`. Semantic worker without effect may only claim `PROCESSED` if it actually interpreted; ticket-only states must say `worker_seen_needs_execution` (as observed in auto-reply for this commission).

### Runtime declaration

Each agent card must declare:

```yaml
semantic_runtime:
  mode: always_on | event_driven | manual_seat | none
  worker_unit: <systemd or process name or null>
  max_inline_tools: [...]
  escalates_to: <uid or session>
```

Agents with `mode: none` are delivery-only and must not be routed semantic-required tasks without human relay.

---

## 11. External-agent onboarding and SAB federation boundary

### Boundary

External agents (Devin, Perplexity, Claude web, SAB participants outside the internal trust domain) **must not** receive broad internal NATS credentials.

### Join sequence (normative)

1. **Card** in git (`examples/agents/...`).  
2. **Git seat** for zero-credential async.  
3. **Gateway token** (hashed at rest) via mailbox gateway HTTPS — publish-to-peer + own-inbox only.  
4. Optional **scoped NATS user** only when egress allows and ACL is UID-scoped (never superuser).  
5. **Announce** on fleet + registry refresh by probe receipt.  
6. **Semantic runtime declaration** (even if `manual_seat` / git-only).

### SAB federation

- Shared correlation ID and artifact SHA on every receipt (SAB map).  
- Artifacts in `FLEET_ARTIFACTS`; task board in `FLEET_STATE`; compatibility messages on agreed transport.  
- Lane ownership table is social contract; technical enforcement is lease CAS + identity-bound subjects.  
- Independent review lanes must bind content SHA; no self-review of own activation.

### Mailbox gateway contract (existing code, incomplete deploy)

- `POST /a2a/mailbox/send`, `GET /a2a/mailbox/inbox`, `GET /a2a/mailbox/whoami`  
- Bearer token → single `agent_uid`  
- Body size limit 64 KiB (large files → Object Store lane)  
- Stream name currently hard-coded `DHARMA_A2A` — Stage-A remains; Stage-B parameterizes

---

## 12. Large artifact transfer

### Law

Messages never carry large binaries. Messages carry **references**:

```json
{
  "artifact_ref": {
    "store": "FLEET_ARTIFACTS",
    "object": "sha256-<hex> or logical name",
    "sha256": "<hex>",
    "size_bytes": 18969,
    "content_type": "text/markdown",
    "uploaded_by": "<agent_uid>",
    "retention_class": "task|evidence|ephemeral"
  }
}
```

### Requirements

| Topic | Spec |
|---|---|
| Upload auth | Scoped Object Store credentials or gateway-mediated upload API; not broad NATS `>` |
| Chunking | Use NATS Object Store chunking; client verifies full SHA-256 |
| Limits | Per-object max (operator-set; start 25–100 MB); per-agent daily quota |
| Manifest | Sidecar JSON with parts, order, hashes for multi-file packs |
| Retention | Task artifacts ≥ 30 days; evidence ≥ 90 days; ephemeral ≤ 7 days (TTL policy) |
| Download | Gateway or scoped principal; audit log of who fetched |
| Denial case | Grok principal currently lacks Object Store grants — **WP-12** must add scoped grants or gateway upload |

### Fallback

Secure host transfer (scp/s3 presign) allowed for break-glass with receipt; still hash-bind into KV/task record.

---

## 13. Security

### 13.1 Credentials

- Env var **names** only in git (`FLEET_FIELD_REGISTRY` secret policy).  
- Per-UID NATS users; remove/replace superuser-class fleet principals after migration tooling no longer needs them.  
- Gateway tokens: SHA-256 at rest, mtime reload, revoke = delete hash.  
- **Rotation:** historical exposure ⇒ rotate AGNI + Meghadharma + gateway tokens as operator work package (not this PR). Never reproduce values.

### 13.2 Transport security

- Prefer TLS (WSS already on AGNI 8443; Meghadharma WS 9443 with local certs).  
- Plain `4222` only on trusted network / localhost; do not expose unauthenticated.  
- Monitoring `8222` must remain localhost-only (current Meghadharma shape is correct).

### 13.3 Provenance and signatures

- Enforce Agent Card JWS verification at gateway and production NodeGateway (currently field exists, enforcement missing).  
- Sender identity from authn principal.  
- Reply routing allow-list: agent may publish replies only on own reply/ack subjects + peer inboxes per FFR-D1 model.

### 13.4 Containers / least privilege

- Prefer `NoNewPrivileges`, `PrivateTmp`, read-only root where possible (fleet projector already stricter than some Grok units).  
- Semantic workers should not mount unrelated secrets.  
- Dashboard never receives NATS passwords — only read-scoped projection credentials.

### 13.5 Restricted actions

No agent may: mint another agent’s credential, drain another agent’s worker durable, or mark COMPLETED without EFFECT_COMMITTED evidence.

---

## 14. Stream / subject topology and wildcard-overlap analysis

### 14.1 Stage-A (compatibility, one broad stream per hub)

| Stream | Subjects | Purpose |
|---|---|---|
| `DHARMA_A2A` | `dharma.a2a.>`, `dharma.agent.>` | Compat + dual grammar capture |
| `KV_FLEET_STATE` | `$KV.FLEET_STATE.>` | Board, leases, presence snapshots |
| `OBJ_FLEET_ARTIFACTS` | Object store internals | Large artifacts |

**Overlap analysis:** On a single hub, one stream owning both wildcards is **internally consistent**. Conflict arises if a second stream is created that overlaps those subjects (JetStream rejects overlapping interest across streams). Therefore Stage-B **must** narrow `DHARMA_A2A` subjects **before** creating `DS_AGENT_INBOX` / `DS_TASKS` with overlapping patterns — or create non-overlapping new prefixes.

### 14.2 Stage-B target (from master spec, adjusted)

| Stream | Subjects | Max age | Notes |
|---|---|---|---|
| `DS_FLEET` | `dharma.fleet.*`, `dharma.substrate.health` | 7d | Heartbeats/health |
| `DS_AGENT_INBOX` | `dharma.agent.*.inbox`, `dharma.agent.*.outbox` | 14d | Per-agent mail |
| `DS_TASKS` | `dharma.a2a.task.>` | 30d | Workqueue-like task path |
| `DS_RECEIPTS` | `dharma.a2a.receipt` | 90d | Receipt projection feed |
| `DS_OPERATOR` | `dharma.operator.>` | 14d | Hot contact coordination |
| `DS_DLQ` | `dharma.dlq.>` | 90d | Poison park |
| Compat (temporary) | **narrowed** `dharma.a2a.<callsign>` allowlist or mirror-only | drain window | Retire after dual-read |

### 14.3 Consumer rules

- Pull durable, explicit ack, ack_wait 30–60s, max_deliver 3–5 (not −1 for workers).  
- Presence projectors: filter `dharma.agent.*.presence` only; never inbox.  
- New consumers: `DeliverNew` unless audit.  
- Queue groups only for competing workers on the **same** UID service replicas — not across different UIDs.

---

## 15. Stage-A — AGNI → Meghadharma compatibility migration

**Goal:** One logical writable bus for compatibility subjects **without** grammar change.

### Steps

1. **Snapshot** both hubs: stream config, consumers, pending, KV keys, object list, ACL user list (sanitized).  
2. **Freeze inventory** in a migration packet (git).  
3. **Mint scoped credentials** per UID on candidate; stop minting new superusers.  
4. **Establish governed mirror** AGNI → Meghadharma (or dual-write with idempotent dedupe). Preserve message_id. Loop-prevention header required.  
5. **Parity checks:** sequence accounting, consumer filter equality, sample payload hash equality, KV revision snapshots.  
6. **Repoint one publisher at a time** (start with non-critical); prove HANDLER_ACK on candidate.  
7. **Repoint one consumer at a time**; drain old pending.  
8. **Bounded dual-run window** (recommend ≥ 72h for critical agents).  
9. **Rollback drill:** flip one agent back; ensure no split-brain double-effect (idempotency).  
10. **Retirement** of source writer only after gates green + operator ACCEPT.

### Stage-A acceptance

- [ ] Parity report attached with timestamps  
- [ ] No overlapping dual-write without dedupe proof  
- [ ] Field registry updated from probe receipts  
- [ ] Zero P0 identity collisions remaining on cutover subjects  
- [ ] Rollback tested  

---

## 16. Stage-B — canonical grammar activation

**Precondition:** Stage-A complete or explicit operator exception for a pilot subject family.

1. Dual-publish envelope adapter: accept `send.v1` / `semantic_message.v1`, emit `dharma.nats.envelope.v1` on target subjects.  
2. Create `DS_*` streams on **non-overlapping** subjects or after narrowing compat stream.  
3. Route `A2ANatsTransport` production callers to live `DS_TASKS` with DLQ.  
4. Unique UID/subject/durable/credential audit passes 100%.  
5. Enforce card signatures at gateway.  
6. Retire legacy callsign subjects after dual-read shows zero traffic N days.  
7. Update `a2a_topology.DEFAULT_COMPATIBILITY_STREAM` only when defaults match production reality.

### Stage-B acceptance

- [ ] New leased tasks use envelope v1 end-to-end with receipts  
- [ ] MaxDeliver + DLQ proven in adversarial tests  
- [ ] Compat traffic below threshold or zero  
- [ ] Master spec, field registry, cards, and live wire agree  

---

## 17. Dashboard / Grafana / Command Node projection contract

### Sources of truth (read-only)

1. `FLEET_STATE` task and presence keys  
2. `FLEET_ARTIFACTS` metadata + hashes  
3. Receipt subjects / receipt log projections (not worker inbox durables)  
4. JetStream monitoring metrics (pending, ack floor) via **observer** credentials  

### Forbidden

- Dashboard draining `*_inbox` worker durables  
- Green status from `pending=0` alone  
- Green from filesystem dock presence alone  
- Green from PUBLISH_ACCEPTED or HANDLER_ACKED when user asked for semantic completion  

### Minimum panel fields

correlation/task id · artifact SHA · holder + lease id · lifecycle stage · JetStream seq / KV revision · retry count · deadline · last error (redacted) · receipt links · semantic status vs transport status · hub name (AGNI vs Meghadharma) until single-bus retirement

### Command Node

`/health` may show node online; fleet endpoints must auth. Deployed UI must bind to Meghadharma projection APIs, not stale local JSON copies, or must label itself **degraded/mirror**.

---

## 18. Metrics, traces, SLOs, alerts, operator-visible truth

### Metrics (minimum)

| Metric | Labels |
|---|---|
| `a2a_publish_total` | hub, subject_family, result |
| `a2a_handler_ack_latency_seconds` | agent_uid |
| `a2a_semantic_latency_seconds` | agent_uid |
| `a2a_consumer_num_pending` | stream, durable |
| `a2a_dlq_total` | stream, durable |
| `a2a_idempotency_duplicate_total` | side_effect |
| `fleet_kv_cas_fail_total` | key_prefix |
| `object_store_upload_bytes` | agent_uid |

### Traces

Every command/task/receipt carries `trace_id`; gateway maps to `traceparent` when crossing HTTP.

### Initial SLOs (pilot)

| SLO | Target |
|---|---|
| Publish accept latency p99 (same hub) | < 500 ms |
| HANDLER_ACK for always-on agent p95 | < 5 s |
| Semantic reply for always-on simple tasks p95 | < 60 s |
| Lost reply rate (correlation unmatched after TTL) | < 1% |
| False-green dashboard incidents | 0 per month |

### Alerts

- Consumer pending > threshold for > 10 m  
- max_deliver approach / DLQ depth > 0  
- Hub unreachable from peer monitor  
- Dual-write parity drift  
- Superuser principal used from unexpected IP  

---

## 19. Backup, off-host restore, DR, rollback, split-brain fencing

| Control | Requirement |
|---|---|
| JetStream store | File-backed; scheduled snapshot of `/var/lib/nats/jetstream` off-host |
| KV/object | Include in snapshot; verify restore of `FLEET_STATE` key and artifact SHA |
| Config | `/etc/nats-server.conf` in secrets-managed backup (encrypted); never raw in git |
| Restore drill | Quarterly: restore to shadow host; prove consumer resume + no effect duplication |
| Rollback | Stage-A/B each have single-agent flip-back; dual-write off on rollback |
| Split-brain fencing | Only one writable hub per subject family after cutover; mirrors read-only or deduped; lease fencing tokens on board mutations |
| Litestream / DB | Separate from NATS; do not treat SQL backup as NATS restore |

**Note:** `dharma-litestream` was observed restarting on host during probe — treat as independent reliability debt, not NATS backup.

---

## 20. Governance / ownership and repository placement

| Artifact | Placement | Owner track / surface |
|---|---|---|
| This update spec + JSON | `docs/architecture/` | Spec PR; implementation via titanium / organism-rewire / future NATS track next-items |
| Master substrate doctrine | `docs/governance/NATS_SUBSTRATE_MASTER_SPEC.md` | Update only when Stage gates land |
| Connect-time field truth | `docs/ops/FLEET_FIELD_REGISTRY.yaml` | Refresh by probe receipts (FFR-D3) |
| Topology constants | `scripts/runtime/a2a_topology.py` | Runtime scripts |
| Transport | `dharma_swarm/a2a/nats_transport*.py` | Orphaned hot surface — assign track ownership |
| Gateway | `dharma_swarm/a2a/mailbox_gateway.py` | External onboarding |
| Merge / PR gates | merge-master-mike track | Do not stomp casually |

**Active portfolio note:** No single track currently owns the whole dual-hub cutover. Implementation work packages should open or extend a track with explicit `owned_surfaces` rather than silent multi-track stomps.

---

## 21. Implementation work packages

| WP | Title | Depends | Owner (suggested) | Effort | Acceptance |
|---|---|---|---|---|---|
| **WP-0** | Probe + refresh FLEET_FIELD_REGISTRY from 2026-07-18 evidence | — | ops + any agent with probe receipts | 0.5 d | Registry matches wire; FFR statuses updated |
| **WP-1** | Dual-hub inventory + parity harness (read-only) | WP-0 | platform | 1–2 d | Automated sanitized inventory JSON both hubs |
| **WP-2** | Scoped credential matrix + superuser reduction plan | WP-1 | operator + security | 1 d plan / ops apply | Plan only in git; apply is operator gate |
| **WP-3** | AGNI→Meghadharma mirror with dedupe | WP-1, WP-2 | platform | 3–5 d | Parity report; loop-free |
| **WP-4** | Lifecycle receipt schema + projector (no durable steal) | WP-0 | runtime | 2 d | States visible without collapsing ACK→DONE |
| **WP-5** | Semantic runtime declaration on all cards + always-on template | WP-4 | agent owners | 2–3 d | Each UID declares mode; always-on template reused |
| **WP-6** | Production caller for `A2ANatsTransport` **or** explicit demotion of claim | WP-4 | runtime-truth | 2 d | One honest production path |
| **WP-7** | Mailbox gateway deploy + sandbox allowlists | WP-2 | operator | 0.5–1 d | whoami+send from external seat |
| **WP-8** | Object Store gateway upload/download lane | WP-2 | platform | 2–3 d | External agent uploads hash-verified artifact without broad NATS |
| **WP-9** | Dashboard bind to FLEET_STATE/ARTIFACTS/receipts | WP-4 | command-node | 2 d | No false-green on ACK-only |
| **WP-10** | Stage-A cutover per agent | WP-3–5 | ops | rolling | Retirement gates |
| **WP-11** | Stage-B DS_* activation | WP-10 | platform | 3–5 d | Non-overlap + e2e envelope v1 |
| **WP-12** | Credential rotation post-exposure | operator decision | operator | 1 d | Old creds invalid; no values in git |
| **WP-13** | Adversarial test suite in CI (hermetic) + live matrix optional | WP-4–6 | QA/gov | 2–3 d | Tests green; live matrix optional |

**First three implementation packages (recommended start):** **WP-0 → WP-1 → WP-4** (truth before migration). Mirror (WP-3) only after inventory and credential plan exist.

---

## 22. Adversarial test matrix

| # | Attack / failure | Expected defense |
|---|---|---|
| A1 | Spoof `from_agent` in payload | Reject/quarantine; authn principal wins |
| A2 | Publish to peer reply subject as attacker | ACL deny; no HANDLER_ACK as victim |
| A3 | Duplicate publish same `message_id` | Broker dedupe or idempotent no second effect |
| A4 | Redeliver after effect commit | IdempotencyRecord short-circuit |
| A5 | Poison message infinite fail | max_deliver → DLQ + alert |
| A6 | Stale durable after UID rename | Migration checklist; no silent dual drain |
| A7 | Observer uses worker durable | Forbidden by ACL + config test |
| A8 | Object Store upload as unauthorized UID | Deny; audit |
| A9 | Oversized inline body | Gateway 413 / client reject; force artifact_ref |
| A10 | Offline agent | STORED remains; no COMPLETED; dashboard shows offline |
| A11 | Credential compromise superuser | Blast radius = full bus → rotation runbook; reduce superusers |
| A12 | Restore old snapshot after new effects | Fencing + idempotency; document split-brain window |
| A13 | Dual-hub write without dedupe | Parity harness fails; block cutover |
| A14 | Dashboard false-green | Tests require semantic receipt for green collaboration |
| A15 | Late result after lease expiry | `LATE_RESULT`; no effect |
| A16 | Gateway token replay from other IP (optional policy) | Rate limit / bind policy if enabled |

---

## 23. Phone-only and external-agent acceptance tests

### Phone-only (operator)

1. From phone browser/SSH jump: open dashboard; confirm task lifecycle shows distinct stages for a known correlation id.  
2. Trigger or observe a send; see PUBLISH vs ACK vs semantic fields separately.  
3. Confirm artifact link opens or shows hash (not a multi-MB chat paste).  
4. Confirm no plaintext secrets on any screen.

### External-agent

1. Sandbox with **only** gateway token: `whoami` returns correct uid.  
2. `send` to always-on peer → HANDLER_ACK within SLO.  
3. Semantic-required task → typed semantic reply with correlation id.  
4. Attempt Object Store upload via gateway lane → hash matches.  
5. Attempt to drain another agent’s inbox → denied.  
6. Git-seat-only agent can still progress without NATS password.

---

## 24. Explicit stop conditions and unresolved operator decisions

### Stop conditions (halt implementation, escalate)

- Would create a **third** transport authority  
- Would add a second writer of task state without fencing  
- Would collapse agent identities or share durables  
- Would print/commit credentials  
- Would treat transport ACK as semantic completion in user-visible green  
- Would flag-day migrate broker + identity + grammar + schema together  
- Would mutate production without snapshot + rollback + bounded drain  
- Would overlap JetStream stream subjects without an explicit narrowing plan  

### Unresolved operator decisions (required inputs)

| ID | Decision | Options | Spec default if undecided |
|---|---|---|---|
| **OD-1** | Final single writable hub after Stage-A | Meghadharma vs AGNI vs new cluster | **Meghadharma candidate**, AGNI source during A |
| **OD-2** | Superuser principal retirement date | calendar | Block Stage-B complete claim |
| **OD-3** | Credential rotation window | immediate / scheduled | Track as P0 ops; no values here |
| **OD-4** | Whether Mac hub remains | retire / leafnode / ignore | Ignore for fleet claims until bridged |
| **OD-5** | Stage-B subject narrowing strategy | rename streams vs shrink wildcards first | Shrink wildcards first |
| **OD-6** | Gateway public hostname / TLS | IP vs domain | Domain preferred for sandbox allowlists |
| **OD-7** | Track ownership for nats_transport hot surface | open track / assign titanium | Must assign before large code edits |
| **OD-8** | Object Store max size and retention classes | numbers | See §12 starters |

---

## 25. 24-hour, 7-day, and 30-day execution priorities

### Next 24 hours

1. Land this spec (draft PR) — **spec only**.  
2. WP-0: refresh `FLEET_FIELD_REGISTRY.yaml` from 2026-07-18 probes (separate PR).  
3. Operator: schedule credential rotation (WP-12) without pasting secrets into chat.  
4. Confirm AGNI inventory access path for WP-1 (credentialed probe from allowed host).  

### 7 days

1. WP-1 parity harness + sanitized dual-hub report.  
2. WP-4 lifecycle projector.  
3. WP-7 gateway deploy smoke if operator available.  
4. WP-5 semantic runtime declarations for all always-on UIDs.  
5. Dashboard false-green audit (WP-9 start).  

### 30 days

1. WP-3 mirror dual-run.  
2. Stage-A single-agent cutovers.  
3. WP-8 Object Store external lane.  
4. WP-6 honest production transport path.  
5. Stage-B pilot on non-critical subject family.  
6. Adversarial suite green in CI; live matrix on schedule.  

---

## 26. External pattern citations (research)

| Pattern domain | Primary guidance | Application here |
|---|---|---|
| **NATS JetStream** | Stream/consumer ack, redelivery, `Nats-Msg-Id` dedup, monitoring | Durable pull workers, DLQ, dual-hub inventory via jsz/varz |
| **A2A / Agent Cards** | Agent Card discovery, task lifecycle as **interop** model, HTTP edge | Cards at edge; internal NATS binding; gateway for externals |
| **Durable workflows / leasing** | Temporal: at-least-once activities ⇒ idempotent effects; workflow id reuse | `IdempotencyRecord` + lease CAS + separate effect commit state |

References (non-exhaustive): NATS JetStream concepts documentation; A2A Protocol specification (a2a-protocol.org); Temporal idempotency and durable execution guidance.

---

## 27. Red-team summary (advisory)

| Risk | Residual after this spec |
|---|---|
| Spoofed sender | Closed **if** WP-2 ACLs + gateway principal binding enforced |
| Duplicate effects | Closed **if** all effect paths use IdempotencyRecord (compat path still weak) |
| Stale consumers | Mitigated by unique durables + registry probe refresh |
| Object Store abuse | Open until WP-8 quotas/auth |
| Lost replies | Mitigated by correlation capture workers; need SLO alerts |
| Offline agents | Honest states required; UI work WP-9 |
| Credential compromise | Open until rotation + superuser reduction |
| Restore failure | Open until drill |
| Dashboard false-green | Open until WP-9 |

**Advisory label:** This red-team is author-seat analysis, not an independent certification.

---

## 28. Completion evidence for this commission (spec-only)

| Item | Value |
|---|---|
| Spec path | `docs/architecture/NATS_A2A_SYSTEM_UPDATE_SPEC_2026-07-18.md` |
| JSON companion | `docs/architecture/NATS_A2A_SYSTEM_UPDATE_SPEC_2026-07-18.json` |
| Live systems inspected | meghadharma-cloud NATS monitoring + systemd + Grok durables + local TCP to AGNI WSS |
| Inaccessible | AGNI authenticated stream inventory; Mac hub; dashboard authenticated fleet payloads |
| Migration performed | **None** |
| Credential rotation performed | **None** |
| Restart performed | **None** |

---

## Appendix A — Top P0/P1 findings (executive)

1. **P0 — Dual unbridged `DHARMA_A2A` authorities** (AGNI + Meghadharma) without proven mirror/cutover.  
2. **P0 — Target `DS_*` / envelope v1 not live**; live grammar is compatibility send/semantic envelopes.  
3. **P0 — Field registry stale vs 2026-07-18 wire** (subjects, ACLs, hub roles).  
4. **P0 — Superuser-class NATS principals** and historical credential exposure requiring rotation.  
5. **P1 — Semantic discontinuity** (ACK without semantic/effect) and Object Store lane missing for agent principals.  

## Appendix B — Citation map (repo)

| Claim | Cite |
|---|---|
| Target DS_* topology | `docs/governance/NATS_SUBSTRATE_MASTER_SPEC.md` JetStream table |
| Live vs target note | same § Live Topology vs Target; `scripts/runtime/a2a_topology.py` |
| Field registry AGNI hub | `docs/ops/FLEET_FIELD_REGISTRY.yaml` `hub:` |
| Envelope v1 | `dharma_swarm/a2a/nats_transport_support.py` `NATS_ENVELOPE_SCHEMA` |
| Transport default DS_TASKS | `dharma_swarm/a2a/nats_transport.py` `NatsTransportConfig.stream_name` |
| Send v1 | `scripts/runtime/a2a_send.py` header + `schema_version` |
| Gateway design | `dharma_swarm/a2a/mailbox_gateway.py` |
| Always-on spine gaps | `docs/architecture/A2A_ALWAYS_ON_SPINE_MASTER_PLAN.md` Hard Gaps |
| SAB dual authority | dharmic-agora `SAB_IGNITION_WORKSTREAM_MAP.md` §2–5 |

---

*End of specification.*
