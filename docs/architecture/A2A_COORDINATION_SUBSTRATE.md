# A2A Coordination Substrate — world-class anti-sprawl coordination over NATS + git-main

> **STATUS (2026-07-01): DORMANT / ADVISORY — do not deploy.** An 8-expert
> web-grounded adversarial panel (§8) verified against the code that this design is
> a *sound primitive, unwired, aimed at a collision problem we don't yet have,
> validated against a fleet that doesn't exist*. Three claims below were code-verified
> as overclaims and are corrected inline:
> 1. **The fence is unenforced** — `validate_fencing_at_merge` has **0 production
>    callers** (test-only). An unenforced fence is not a safety property.
> 2. **The token is bucket-global, not per-surface** — `fencing_token = int(entry.revision)`
>    cannot distinguish a stale holder of surface A from a fresh writer of surface B.
> 3. **The TTL is application-clock fiction** — the NATS bucket (`history=8`, no `max_age`)
>    never expires the key; expiry is a Python `now`-vs-`acquired_at` compare. This one
>    line is the *entire* clock-skew hole.
>
> The one load-bearing truth to build on: **git main is the single ordering authority.**
> The corrected route (§8) is *enforce one mandatory idempotent merge gate + solve
> convergence, not collision*; keep this lease library dormant behind a real-fleet
> trigger. Sections 1–7 are preserved as the original design record; read them through
> the §8 correction.
>
> **SUPERSEDED (2026-07-01, §8.6): every "corrected summit" capability already exists
> in the repo, wired and tested.** A surface scan found `a2a/agent_card.py` (AgentCard),
> `a2a/task_receipt.py` (the exact ingress schema this doc proposes as new),
> `a2a/nats_transport.py` (`A2ANatsTransport`, idempotency-guarded), `runtime_state.py`
> `IdempotencyRecord` (wired at the write boundary — the panel's #1 fix, *already done*),
> and `scripts/runtime/pr_merge_control.py` (the merge gate). **This `coordination_substrate`
> package is a parallel reinvention of wired infrastructure.** Do not build on it; build on
> the existing `a2a/` stack. See §8.6 for the file:line map. The single lesson: **scan the
> `a2a/` surface before adding coordination code — this doc's whole design was already shipped.**

**Role:** architecture spec. **Authority:** subordinate to `SOVEREIGN_MANIFEST.md` and the
North Star §9 canon-metabolism rule (*git main is the single ordering authority*). This
doc owns the design; it owns no runtime state.

**Provenance:** synthesized from an 18-agent deep research pass over Antonio Gulli's
*Agentic Design Patterns* (21 patterns) mapped onto dharma_swarm's constraints. The
research validated the bicameral/lease/git-main spine **and** caught three traps a naive
build would have shipped (fencing-token, CRDT-vs-CAS, supervisor-as-agent). A later
8-expert panel (§8) then caught the traps *this* build shipped — read §8 first.

---

## 0. The problem and the thesis

**Sprawl** = uncoordinated parallel work on many branches that never reconciles (this
session's lived symptom: 126 dirty files across three machines, colliding edits to the
same surfaces, WIP at max). It is *not* caused by parallelism — parallelism is doctrine
(Transcendence Principle). It is caused by **parallelism that works blind and never
metabolizes to main.**

**Thesis:** borrow the schemas and the reliability floor from the agentic-design-pattern
canon; **refuse its authority.** Nearly every pattern that vests ordering/truth in an
agent or a durable side-store is a landmine, because git-main is already the sole
ordering authority. The whole design reduces to one invariant:

> **Leases arbitrate write access; only merged git-main records what is true.**
> Coordinate the writes, never the thinking.

---

## 1. The keystone: a bicameral system

| | THINK side | WRITE side |
|---|---|---|
| Topology | network / fan-out / debate | strict lease → gate → merge |
| Coordination tax | **zero** — no supervisor, no lease, no gate | full — mutual exclusion + gates |
| Purpose | diversity / exploration (Transcendence lives here) | collision-free convergence to main |
| "Supervisor" | none | **machinery, never an agent** |

The boundary between the two chambers is the **lease**. An agent may think, explore, and
propose with total freedom; it may only *write* to a surface it holds a lease on, and only
*merge* through the gates. An LLM supervisor with commit authority is forbidden (it
recreates a second consensus and reproduces the MAST unilateral-decision failure).

---

## 2. The layer stack (canon → our substrate)

Read bottom-up. The dependency arrow is L0→L10; a higher layer's convenience (a durable
checkpoint, a "COMPLETED" flag, a shared scratchpad) must **never** reach down and become
authority.

| Layer | Gulli ch. | What it is here | Authority |
|---|---|---|---|
| **L0 ordering** | *(ours)* | **git main** — the only thing that decides write order and truth | **sole** |
| **L1 reliability floor** | Ch12 | NATS JetStream durable consumers; idempotency de-duped at the single write boundary; **fencing tokens (KV revision)**; MaxDeliver+BackOff+DLQ | mechanism |
| **L2 mutual-exclusion** | Ch8 (CAS≠CRDT) | **surface leases in NATS KV**, auto-expiring, linearizable compare-and-set; `no lease → no write` | mechanism |
| **L3 coordination wire** | Ch15 A2A | A2A type-system + Task lifecycle as NATS payloads; required versioned DataPart `{claim,evidence,verdict,next_action,files_changed}`; prose confined to a TextPart | schema only |
| **L4 shared world-model** | Ch7/8 | NATS KV/JetStream **blackboard**: leases, claims, in-flight receipts, presence — eventually-consistent, provenance-tagged, **projection only** | never authority |
| **L5 capability plane** | Ch10 MCP | signed MCP tools (`acquire_lease`/`write_to_lease`/`submit_receipt`/`request_merge`); write-tool schema *requires* a live lease token | mechanism |
| **L6 routing / planning** | Ch2/6 | two-stage lease-coupled dispatcher; planner emits a **surface-scoped task DAG**; router grants leases, never merges | mechanism |
| **L7 admission / prioritization** | Ch20/16 | **WIP = held leases** (the warn-5/max-10 track law); two lanes (tight merge / generous exploration); aging | mechanism |
| **L8 safety gates** | Ch18/11 | deterministic-first, fail-closed battery: ingress schema rail → lease auth → **pramāṇa** → **telos** → distance-from-main monitor | proposes |
| **L9 human/quorum merge gate** | Ch13 | durable NATS interrupt; structured MergeProposal; reviewer-agent quorum (Merge Master Mike), **reject-safe on timeout** | ratifies, not orders |
| **L10 learning / eval** | Ch4/9/19/21 | Reflexion-over-receipts (coordination facts only); Voyager library promoted only after a merged receipt; OTel trace_id everywhere; MAP-Elites: lease-space = behavior grid | read-model + gated |

The spine threading all layers: **every action emits an EvidenceReceipt; nothing is a new
store.** We already own most of this (idempotency substrate, EvidenceReceipt, pramāṇa gate,
telos, Mike quorum, WIP law, truth-graph read-models). The substrate is assembly + five new
primitives (§4).

---

## 3. Adopt / Adapt / Reject

**Adopt wholesale (canon is right and safe here):** idempotency keyed at the single write
boundary; DLQ with bounded MaxDeliver+BackOff; A2A AgentCard + typed Parts; deterministic-
first fail-closed guardrails; Panel-of-LLM-judges (disjoint families, off the hot path);
WIP-as-primary-lever (Little's Law); OTel trace_id on every receipt.

**Adapt (right idea, wrong transport/authority — keep schema, change substrate):**
- **A2A** — take the type-system + lifecycle; reject its HTTP/JSON-RPC/SSE transport (that
  is the forbidden second transport). Bind Task-WORKING to a live lease: *no lease → Task
  REJECTED* (a lifecycle invariant, not a side check).
- **MCP** — capability plane only; the write tool validates a lease token, never mints
  authority. Do not use MCP to pass tasks between agents.
- **Blackboard** — read-only projection for stigmergic anti-collision; provenance-tag every
  record; carries write-coordination facts only, never opinions.
- **Routing** — output is a lease *grant*, not a work order; cheap deterministic match, LLM
  only on ambiguity; prefer fan-out over single-argmax so routing isn't convergence pressure.
- **Planning** — decompose along the *write-surface* axis so plan-parallelism == lease-
  parallelism == real collision-freedom; freeze the write-plan before execution (executors
  still ReAct internally).
- **HITL** — durable NATS interrupt + reviewer quorum; the human ratifies an already-green
  receipt chain (Anthropic: 93% of prompts approved unread), never does the review.

**Reject (with reason):**
- Supervisor/hierarchical topology with an **agent** holding commit authority (second
  consensus; MAST failure). The supervisor is *machinery*.
- Peer-to-peer swarm **write** paths / OpenAI-Swarm handoffs-as-transport (N agents → N
  dirty branches = the literal sprawl we prevent). Fine on the think side.
- AutoGen shared-history GroupChat / any shared in-flight scratchpad (correlates thinking →
  transcendence death — the most tempting, most fatal borrow).
- A2A registries / "Task COMPLETED" as truth (a completed Task is an unverified proposal).
- LangGraph durable checkpoints as an ordering authority (borrow the reducer-merge schema
  for the read-model; git-main stays sole authority).
- Unbounded debate (~15× token tax; hard-bound ≤3 rounds; consensus is an *input* to
  pramāṇa, never a bypass).
- **CRDT for the lease grant** — CRDTs deliberately don't give mutual exclusion; the grant
  needs linearizable revision-CAS. (CRDT is fine for the *observation* tier.)
- Any new durable store (saga DB, cost DB, approval store, second receipt type) — project
  over EvidenceReceipt; author nothing.

---

## 4. The five anti-sprawl mechanisms the canon LACKS — our differentiator

No framework in the canon (A2A, ADK, LangGraph, CrewAI, AutoGen, Swarm) has a native
anti-collision write primitive — **A2A explicitly assumes opaque agents with zero conflict
detection.** These are ours:

1. **Surface leases** — `no lease → no write`. The primitive A2A rides *on top of*.
2. **Fencing token (KV revision) enforced at the merge gate.** The trap a naive lease design
   hits: an auto-expiring lease alone is unsafe (Kleppmann) — a GC-paused / clock-skewed
   *zombie* holder writes after expiry. TTL bounds zombies; the fencing token *would* make
   exclusivity a correctness guarantee **iff it is checked at the write path**.
   **CORRECTED (§8): it is not.** `validate_fencing_at_merge` has 0 production callers, so
   today the token is a comment, not a fence — exclusivity is advisory only. Worse, the
   token is bucket-*global* (`int(entry.revision)`), not per-surface monotonic, so even if
   wired it cannot distinguish a stale holder of A from a fresh writer of B. To earn this
   claim: (a) wire the check as a hard blocker in the real merge path with a test that a
   stale/absent token is *rejected*, and (b) make the token per-surface. Until then this is
   an unpaid correctness debt, not a differentiator.
3. **Metabolism SLA** — bind lease expiry to *"distance-from-main not shrinking,"* not raw
   wall-clock, so it doesn't amputate legitimate deep research. Non-convergence is receipted.
4. **Split-brain doctrine** — read-models project truth, never become authority. The canon's
   blackboards/registries/checkpoints all silently drift into a second truth; provenance on
   every shared record makes the drift detectable.
5. **Distance-from-main as a first-class sprawl vital sign** — commits-behind, age of oldest
   un-reconciled leased surface, dispatch-receipt-with-no-downstream-merge-past-TTL alarm.
   The canon measures agent quality; nobody measures *sprawl*.

---

## 5. The Transcendence guardrail (made real, not a slogan)

**Coordinate the writes, never the thinking** — enforced at the lease boundary.

- **Permitted coordination (write side):** lease acquire/release; the typed handoff that
  crosses the lease boundary; the gate battery; merge ordering among gate-passers; the
  write-coordination blackboard; canalized *write-protocol* lessons (lease etiquette, quorum
  thresholds, receipt schema).
- **Forbidden coordination (think side):** which agents explore and how they reason; model
  family / prompt / reasoning path; any shared in-flight scratchpad or opinion-sharing; any
  "lesson" that would make agents reason alike (a governance violation, not an optimization).

Instrumentation that makes it real: a **runtime diversity vital sign** (mean pairwise cosine
/ effective-rank over concurrently-dispatched proposals) projected into `make onboard`, with
a collapse alarm; **re-measure diversity after every canalization step — if it falls, the
ratchet leaked into the think-path, roll back**; diversity-aware selection *before* quorum so
correlated same-family proposals can't fake consensus. Honest failure mode: diversity can
collapse silently while every receipt still looks green — the metric plus a competence floor
is the only defense.

---

## 6. Phased build (each shippable, gated)

- **Phase 0 — fencing floor** *(correctness bug; everything else is sand without it)*:
  idempotency de-dup at the single write boundary; **fencing token = KV revision, enforced
  at the merge gate**; DLQ. → **shipped as the first code slice, `dharma_swarm/coordination_substrate/leases.py`.**
- **Phase 1 — lease primitive**: surface leases via linearizable revision-CAS (not CRDT);
  acquire/renew/release/auto-expiry; WIP cap as a hard admission gate; receipt per grant.
- **Phase 2 — typed wire**: A2A Task bound to a live lease; essays rejected at ingress;
  AgentCard as a JWS-signed short-TTL read-model.
- **Phase 3 — gate battery + merge path**: ingress rail → lease auth → pramāṇa → telos →
  durable-NATS quorum → write-to-main (reuse `make pramana-probe` + Merge Master Mike).
- **Phase 4 — MCP capability plane + surface-scoped planner**.
- **Phase 5 — observability + diversity instrumentation** (distance-from-main + diversity
  vital sign in `make onboard`).
- **Phase 6 — outer learning loop** (write-protocol lessons only, hard-gated).

**Sequencing rule:** borrow the schema and the floor; refuse the authority. Leases arbitrate
write access; only merged git-main records what is true.

---

## 7. Live-load smoke tests — evidence (2026-07-01)

> **Renamed from "adversarial validation" per §8.** These are nondeterministic live-load
> smoke tests on lucky interleavings, **not** checked-history linearizability proofs.
> `peak_simultaneous_holders == 1 observed once` is an assertion about one schedule, not a
> verdict. The 3-node RAFT run validates a topology (>1 host, quorum) that does not exist on
> the real one-VPS deployment. Treat this table as "the code did not obviously break under
> load," not "the design is correct." A real correctness bar needs DST + a history checker
> (Elle/Porcupine) + the fault that actually matters (partition-without-death / GC-pause-past
> -TTL), none of which was run. See §8.

The lease primitive (`nats_kv_leases.py`) was hill-climbed against a **live broker and a
real 3-node cluster**, hunting for breaks — not shown holding. Single-node cases are
reproducible via `tests/test_coordination_substrate_live.py` (skips without a broker).

| Attack | Setup | Result |
|---|---|---|
| Multi-client exclusion | 32 **independent** NATS connections race one surface, 15 rounds | **HELD** — exactly 1 winner/round |
| Clock skew | agent B's fast clock treats a live lease as expired and steals it | **FINDING** (below) |
| Renew vs steal | concurrent renew + steal on the same revision, 30 trials | **HELD** — CAS serializes; no lost/double lease |
| Sustained hammer | 40 agents × 40 rounds, peak-simultaneous-holder counter | **HELD** — peak holders = 1 (an apparent break was a too-strong test invariant: serial release→re-acquire is correct) |
| Crash durability | `kill -9` the broker mid-lease, restart on the same store | **HELD** — lease + fencing + token-monotonicity recovered from disk |
| Cluster failover | 3-node RAFT cluster, R=3 KV, kill the stream **leader** | **HELD** — new leader elected, lease survived, exclusivity held under 2/3 quorum |

**THE FINDING (clock skew).** When agents' clocks disagree, TTL-based *work*-exclusion can
be violated — two agents can both *believe* they hold a surface. **But the fencing token
still guarantees SAFETY:** only the current-token holder passes the merge gate; the stale
(zombie) writer is rejected. This validates the core design decision — **TTL is a
liveness/efficiency property that depends on clock sync; the fencing token is the safety
guarantee that holds regardless of clocks.** Operational requirement: run agents under NTP
so skew doesn't waste work; *correctness never depends on it.*

**Remaining boundary (honestly not yet tested):** a true network partition *without* node
death (RAFT makes the minority side unavailable — correct CP behavior, but untested here);
multi-hour soak / leak testing; and the **git-merge integration** that would structurally
*force* `validate_fencing_at_merge` on a real write (today it is a function call, not
enforced by the write path). Those are the next real climbs.

---

## 8. Expert-panel verdict — the corrected route (2026-07-01)

An 8-seat, web-grounded, adversarial expert panel (NATS/JetStream internals, distributed-
coordination theory, merge-queue/CI-at-scale, durable execution, DST/reliability testing,
security/capability-auth, A2A/MCP standards, and a right-size skeptic) reviewed this
substrate. Every load-bearing claim was **verified against the code**, not asserted. The
panel was unanimous on the core findings.

### 8.1 The verdict
> **A sound primitive, unwired, aimed at a collision problem we don't have, validated
> against a fleet that doesn't exist.** Base camp — on the wrong mountain. The `create` /
> `update(last=rev)`-CAS acquire idiom is textbook-correct in isolation; the *placement,
> enforcement, target problem, and scale posture* are all wrong.

### 8.2 Code-verified findings
| # | Finding | Verified at |
|---|---|---|
| 1 | **The fence is unenforced.** `validate_fencing_at_merge` has 0 production callers. An unenforced token check is a comment, not a safety property — and it is the *only* thing that makes the design Kleppmann-correct. | `leases.py:207`, `nats_kv_leases.py:186` — grep: test-only callers |
| 2 | **The token is bucket-global, not per-surface.** Kleppmann's fence must be per-resource monotonic. | `nats_kv_leases.py:74` (`int(entry.revision)`) |
| 3 | **The TTL is application-clock fiction.** Bucket is `history=8`, no `max_age`/`Nats-TTL`, R1 — the broker never expires the key; expiry is a Python compare. This one line is the entire clock-skew hole. | `nats_kv_leases.py:66`; `leases.py:65-69` |
| 4 | **Redundant with git + the merge queue we already have.** `git update-ref` is atomic CAS; three-way merge already rejects same-file edits; `pr_merge_control.py` + Merge Master Mike already serialize writes to main. The lease is a second, weaker, clock-dependent CAS in front of a stronger one. | `scripts/runtime/pr_merge_control.py` (present) |
| 5 | **`create`/`update` "linearizable" is config-and-fault-conditional.** Jepsen NATS 2.12.1 (Dec 2025): default lazy fsync (~2-min flush, ack-before-durable) can lose acked writes and cause persistent split-brain on a single OS-crash+pause. | jepsen.io/analyses/nats-2.12.1 |
| 6 | **The CAS-on-expired branch is a lost-update path.** On local expiry, `acquire()` does `try_update` on the stale revision instead of a clean purge-aware create race; server-side `max_age` gives this correctly for free. | `nats_kv_leases.py:172` |

### 8.3 What is genuinely right (keep, lean on harder)
**"git main is the single ordering authority" + the bicameral THINK-free / WRITE-gated
split.** This is CALM-correct (monotonic thinking needs zero coordination; only the
non-monotonic merge-to-main does) and matches merge-queue practice. Everything sound in
this spec descends from it; everything wrong contradicts it by adding a second authority.
The `create`/CAS idiom and the honest clock-skew finding are also kept — the finding just
gets promoted from footnote to the whole conclusion (TTL-lease mutual exclusion is
*advisory only*, full stop, per Kleppmann).

### 8.4 The corrected summit (right-sized for one operator, one VPS)
Five layers; build only two this quarter.

| Layer | Concern | Right-size tech | Build now? |
|---|---|---|---|
| L1 identity/trust | who is this agent; is the message authentic | NATS decentralized JWT/nkey + signed A2A AgentCard (JWS) | thin |
| L2 THINK (free) | reasoning, proposals | existing swarm, **zero coordination** (CALM) | keep |
| L3 durable execution | crash-safe runs, retries, idempotency, HITL | DBOS-style in-process lib over existing SQLite/Postgres (no cluster) | **yes** |
| L4 write serialization | the ONE non-monotonic gate | git ref-CAS + merge queue (Mike / GitHub merge queue). **Lease dormant behind a flag.** | **yes (queue) / dormant (lease)** |
| L5 transport | move A2A tasks fast | NATS JetStream **as an A2A custom binding** (not a rejection of A2A) | keep, re-frame |

**Correctness bar — pick ONE and mean it:**
- *(preferred, cheap)* delete `validate_fencing_at_merge` + the correctness claim; rely on
  git ref-CAS + merge-conflict + an **idempotency key at the merge boundary** (strictly
  stronger than the unwired lease, and needs no clock); or
- *(only if kept)* wire the check as a **hard blocker in `pr_merge_control.py`** with a test
  that a stale/absent token is rejected, and make the token per-surface. Optional-fence is
  not an option.

**Solve convergence, not collision.** The observed sprawl (126 dirty files) was branches
that never metabolize to main — a liveness problem a per-file lease cannot fix (a WIP-cap can
make it *worse* by wedging progress). Build a **branch-metabolism SLA** (distance-from-main /
branch-age alarm) + **auto-rebase-or-eject** in the merge queue. "Distance-from-main" is
promoted from "differentiator" to the core.

**Trigger to resurrect the heavy substrate (need ≥2 of 3):** (a) ≥8–10 agents contending the
*same* surfaces concurrently, (b) >1 host, (c) same-file merge conflicts at a rate the queue
can't absorb. When it fires, wire the fence into the merge gate **first**.

### 8.5 Skill gaps to close (honest)
1. **Enforced (not advisory) gates on the write path** — a safety function nothing calls.
2. **Deterministic-seam discipline / DST** — the async store binds a live connection + takes
   wall-clock `now`, so no history checker or fault injector can drive it. Refactor behind a
   sync `KV(get/create/CAS-update)` + `Clock` port; swap a deterministic fake for NATS.
3. **Merge-queue / CI-at-scale engineering** — speculative execution, bisect-eject. This, not
   locking, is the real write-ordering discipline. Mike is a start.
4. **Durable-execution semantics** — idempotency keys, exactly-once *effects* vs at-least-once
   *delivery*, deterministic replay. Don't hand-roll it.
5. **Capability security (Miller)** — a guessable global integer is not a capability.
6. **A2A/MCP conformance** — serve/sign AgentCards, declare NATS as a custom binding, don't
   overload the Task lifecycle enums; that silently lies to conformant clients.
7. **Prompt-injection / confused-deputy defense at the write boundary** — the actual threat on
   an always-on VPS holding provider keys; the lease does nothing for it.

### 8.6 SUPERSEDED — the corrected-summit capabilities already exist, wired (2026-07-01)

After the panel defined the "corrected summit" (§8.4), a surface scan of the repo found
that **every layer it prescribes is already built, wired, and tested in `dharma_swarm/a2a/`
and `runtime_state.py`.** This `coordination_substrate` package is a parallel reinvention.
The real anti-sprawl act is to *not build on it* and to point future work at what exists:

| Corrected-summit layer (§8.4) | Already shipped — build on THIS | Status |
|---|---|---|
| L1 identity — signed AgentCard | `a2a/agent_card.py:198` `AgentCard` + `:468` `CardRegistry`; `SecurityScheme` `:129`; `A2AInboxRoute` `:87` | REAL, wired; JWS signature *enforcement* is the one genuine TODO (tier 2) |
| A2A task lifecycle | `a2a/a2a_server.py` `A2ATaskStatus` (8 states); `A2AServer.submit()` `:313` | REAL, wired, idempotency-guarded |
| Structured A2A ingress schema `{claim,evidence,verdict,next_action,files_changed}` | `a2a/task_receipt.py:33` `validate_task_receipt` + `:87` quarantine | REAL, wired; this doc's L3 proposal was already shipped |
| L5 transport — NATS as an A2A binding | `a2a/nats_transport.py` `A2ANatsTransport` (publish/consume on `dharma.a2a.*`) | REAL, wired, idempotency-guarded both sides |
| **Idempotency key at the write boundary (panel's #1 correctness fix)** | `runtime_state.py:659` `IdempotencyRecord`; `try_begin_idempotent_side_effect` `:3182/:3240`; wired in `nats_transport.publish_task/consume_task` and `a2a_server.submit` | REAL, wired, **tested** (`tests/test_a2a_send.py`) — unlike this doc's fence, it is actually called on the write path |
| L4 merge gate | `scripts/runtime/pr_merge_control.py:1128` `build_gate` (10+ deterministic checks) | REAL, production-active (Merge Master Mike) |
| Branch metabolism / distance-from-main (the real disease) | `scripts/governance/render_parallel_lane_map.py:269` `branch_age_days` + `:277` `build_lane_map`; and in-flight PR #737 metabolization ledger | PARTIAL (age-based) — the one genuinely thin spot, and already being worked |

**Verdict:** `dharma_swarm/coordination_substrate/**` (leases.py, nats_kv_leases.py) is
**SUPERSEDED by the wired `a2a/` stack** and should not be adopted into production. Its only
non-redundant idea — surface-level mutual exclusion between agents — is already covered for
the *only write that matters* by git three-way merge + `pr_merge_control`. Recommend: keep
this package as a dormant reference or delete it; do **not** wire it. The lasting value of
this whole exercise is this signpost: **scan `dharma_swarm/a2a/` and `runtime_state.py`
before writing any new coordination/A2A/NATS code — it is almost certainly already there.**
