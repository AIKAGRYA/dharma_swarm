# Codex Adversarial Response — Pre-#1004 Hardening and Whole-Swarm Sequence

**Document role:** `working_plan` — a source-derived review and sequencing
proposal. It does not replace THE KEEL, create a track, assign ownership, close a
finding, authorize implementation, or grant merge authority. It is subordinate
to `CLAUDE.md`, `docs/governance/CANONICAL_DOC_STACK.md`,
`docs/governance/ACTIVE_TRACK.yaml`, and the human operator.

**Responds to:** [PR #1004](https://github.com/AmitabhainArunachala/dharma_swarm/pull/1004)
and Claude's “Adversarial Review of the Pre-1004 Hardening Pass” handoff.

**Audit snapshots:** merged `main` at
`26ea66fd07f3fbf688b6399d34c68b9042e20686`; #1004 at
`475b9cb3c0e055318d85a71170a8d768df70144a`; #1006 at
`c4037b6ad4e6017572e5b2b666047df7e2609a71`; #1007 at
`994d45f5fee2d27bd91358bf2609578e18b3baf8`. Commands in the evidence appendix
reproduce the source boundary.

**Attachment boundary:** `PRE_1004_HARDENING_PASS.md` was not present in the
named #1004 tree, any fetched Git tree, the checkout, or the supplied Library
search. The command
`git log --all --name-only --pretty=format: | rg -i 'PRE_1004_HARDENING_PASS|1004_HARDENING|HARDENING_PASS'`
returned no path. This review therefore covers Claude's pasted handoff and the
raw source it cites. It does **not** pretend to have reviewed the missing
attachment; attach it for a follow-up delta review.

## Executive verdict

**#1004: REQUEST CHANGES, narrowly.** Its central doctrine is sound: verified
engineering quality is a permanent admission standard; model diversity is not
external independence; quality is a vector of hard floors; and implementation
must be bounded with human-only merge authority
(`#1004@475b9cb3:docs/plans/THE_KEEL_2026-07-17.md:21-37,74-106,110-128,427-445`).

The current text is not ready for operator ratification even as an inert
working-plan doctrine proposal because it makes nine load-bearing mistakes: it
calls an inert working-plan boundary “binding”; assigns packet semantics to a
CI contract that does not contain them; risks minting a second ledger; declares
an active track a slot donor; describes a proposed archive PR as automatic
archival; orders a provider gate before runtime/identity authority; omits the
already-governing Titanium Phase-0 dependency; presents a scoped reach
observation as a verified Harness fact; and retains a stale instruction to
merge already-merged #1005 first
(`#1004@475b9cb3:docs/plans/THE_KEEL_2026-07-17.md:9-17,120-128,205-228,247-276,265-268,317-341,385-413`;
`docs/plans/TITANIUM_GRADE_REPOSITORY_HARDENING_2026-07-10.md:1267-1467`).
The exact corrections are in “Required #1004 corrections.”

**A new Keel-derived pre-#1004 code campaign: DISAGREE.** Merge the corrected
one-file proposal only after its operator review gate; do not make a new runtime
campaign a prerequisite. Already-authorized Titanium Phase-0 packets continue
independently and need not wait for #1004. #1004 explicitly has no runtime
authority, while Titanium requires bounded packets, an independent Phase-0
merged-main exit, and no deferred-phase implementation before that exit
(`#1004@475b9cb3:docs/plans/THE_KEEL_2026-07-17.md:5-17,385-405`;
`docs/plans/TITANIUM_GRADE_REPOSITORY_HARDENING_2026-07-10.md:1261-1308,1331-1333`).

**Whole-system recommendation:** one runtime **authority**, not one megaprocess and
not one megadatabase. Use one write-owning Runtime Host per deployment; one
stable intent identity; one transactional operational event/outbox path; one
authority per fact; API, dashboard, agents, and fleet transports as clients or
projections. Keep SQLite for the first coherent single-host hull, measure its
contention, and move only canonical operational state to Postgres if measured
multi-writer/HA requirements cross an explicit threshold.

## Claim-by-claim re-derivation

### Claim 1 — “The organs exist but are isolated/forked, not absent”

**AGREE, with corrected wording.** A bridge exists, so “never synced” is too
absolute. The bridge projects only ontology `Outcome` objects into runtime
`ArtifactRecord` objects, in one direction, with per-record commits and
best-effort non-raising failure behavior
(`dharma_swarm/engine/store_sync.py:1-19,55-67,74-110,147-163`). It skips an
existing `ont-{outcome.id}` rather than converging later changes, and the
promised high-water mark is not implemented
(`dharma_swarm/engine/store_sync.py:18,83-110,153-163`).

Corrected claim: **bridge organs exist, but the ontology/runtime bridge is a
one-family, one-way, lossy materialization—not a consistency protocol.** The
operator-host witness currently records the sync cron disabled and zero
`ont-%` runtime artifacts, while explicitly limiting the observation to that
host (`docs/state/BROKEN_REGISTER.md:34-48`).

### Claim 2 — “Runtime is wired but fail-open; checkpoint/replay is test-only”

**PARTIAL.** The default composition ensures dispatch identity; Orchestrator
wraps the whole `runner.run_task` dispatch unit in `DurableInvoker`; and
SwarmManager attempts `GraphReconciler` at boot and tick
(`dharma_swarm/orchestrator.py:2252-2253,2427-2435,2470-2478,2525-2552`;
`dharma_swarm/swarm.py:695-709,2313-2361`). Reconciler failures are explicitly
nonfatal (`dharma_swarm/swarm.py:702-709,2316-2319,2353-2361`). The fail-open
diagnosis survives and is wider than Claude's list:

- missing store or required store methods executes the wrapped unit
  (`dharma_swarm/graph/durable_invoker.py:402-424`);
- incomplete identity executes the wrapped unit
  (`dharma_swarm/graph/durable_invoker.py:425-435`);
- idempotency-begin failure executes the wrapped unit
  (`dharma_swarm/graph/durable_invoker.py:458-480`);
- a lost begin plus failed record read can fall through without a claim
  (`dharma_swarm/graph/durable_invoker.py:481-524`);
- an unmemoizable completed result deliberately re-executes the wrapped unit
  (`dharma_swarm/graph/durable_invoker.py:630-645`);
- completion failure is swallowed after the wrapped unit returned; if that unit
  performed provider/tool effects, their outcome is already ambiguous
  (`dharma_swarm/graph/durable_invoker.py:670-707`;
  `dharma_swarm/orchestrator.py:2470-2478`); and
- `DHARMA_SPINE_DISPATCH=0|false|off|legacy|direct` bypasses the wrapper
  (`dharma_swarm/orchestrator.py:2568-2577,2627-2637`).

That outer wrapper is coarser than the effects it claims to protect. One
`invoke_agent:{task_id}:{agent_id}` claim encloses `runner.run_task`, which can
perform multiple semantic-repair provider attempts and multiple rounds of
file-write, edit, shell, web, and provider effects
(`dharma_swarm/orchestrator.py:2427-2435,2465-2478`;
`dharma_swarm/agent_runner.py:1845-2008,2321-2421`). A fail-closed outer claim
therefore does not by itself fence or deduplicate each child provider/tool
effect.

The composed default does not need absent-store behavior: `SessionLedger`
constructs `RuntimeStateStore`, the store resolves a DB path, and `SwarmManager`
passes the runtime DB into the orchestrator
(`dharma_swarm/session_ledger.py:30-50`;
`dharma_swarm/runtime_state.py:1209-1235`;
`dharma_swarm/swarm.py:632-666`). **Inference:** strict production admission
should be compatible with the healthy default, but construction does not prove
store health or that strictness will not stall. Prove it with an exact-path
regression and a degraded-store soak; legacy/test modes need an explicit
profile, not an implicit safety bypass.

“Checkpoint/replay is test-only” is too categorical. Scheduler and persistence
source exists outside tests, but the bounded lexical probe finds no non-test
Python source module outside `graph` adopting
`GraphBuilder`, `CompiledGraph`, `GraphPersistenceKernel`, or
`SimulatedEffects` (`dharma_swarm/graph/scheduler.py:104-178,190-267`; evidence
command E4). That grep cannot exclude dynamic or string-based adapters. The
accurate claim is **implemented, with no lexical production adopter found by
this probe and no organism integration demonstrated**.

### Claim 3 — “The Harness does not exist at whole-system scope”

**AGREE.** The effects module describes the seam as “deliberately minimal,” and the
ledger roots only at `dharma_swarm.graph`
(`dharma_swarm/graph/effects.py:1-11`;
`tests/antithesis_support/seam_ledger.py:56-72`). The repository's closure
report also refuses a whole-swarm determinism claim
(`docs/reports/DHARMA_ANTITHESIS_FIVE_PART_CLOSURE_2026-07-16.md:23-42,223-245`).

The existing scanner is not a sound whole-organism gate without repair. It
follows only static Python imports, scans a finite package set, has no subprocess
call pattern, classifies mediation by receiver variable name, and scans bodies
that may never be called
(`tests/antithesis_support/seam_ledger.py:68-78,101-181`;
`tests/antithesis_support/effect_scan.py:19-76,185-191,209-237`). Its claim that
static closure “never under-reports” is false
(`tests/antithesis_support/seam_ledger.py:10-18`):
`providers.py:727` uses `asyncio.create_subprocess_exec` and `swarm.py:1538`
uses `subprocess.Popen`, but neither appears as an effect in the generated
`swarm` closure (evidence command E13b).

### Claim 4 — “Two disconnected evolution systems; Darwin real-fitness is manual-only”

**PARTIAL.** The API route is structurally broken: its request model supplies
`component` and `generations`, while `SwarmManager.evolve` requires
`component`, `change_type`, and `description`
(`api/models.py:248-250`; `api/routers/commands.py:25-32`;
`dharma_swarm/swarm.py:2731-2739`; evidence command E5). The exception is
converted into an error-shaped ordinary response, not literally hidden
(`api/routers/commands.py:29-32`; `api/models.py:13-17`).

The manual terminal path is not the only real-test path; it also proposes
without a diff before sandbox evaluation, so it does not by itself establish
mutation-attributable fitness
(`dharma_swarm/terminal_commands/evolution.py:50-68`). The live free-grind
constructs `DarwinEngine` and calls `run_cycle`; `run_cycle` resolves and runs a
component-specific test target
(`dharma_swarm/orchestrate_live.py:1263-1298,1317-1371`;
`dharma_swarm/evolution.py:2192-2255`; evidence command E6). The deeper defect
is attribution: automated proposals often have no diff, and shadow mode strips
diffs before the cycle, so the test can measure the unchanged checkout rather
than a proposed mutation
(`dharma_swarm/orchestrate_live.py:1317-1367,1373-1404,2308-2310`;
`dharma_swarm/evolution.py:3386-3394`).

No bridge appears between Darwin and Arena in the main live-composition paths
covered by evidence command E7. Arena owns a frozen, hermetic,
control-relative scorer for its orchestration taskpack, budget parity,
significance checks, and quarantine
(`dharma_swarm/coordination/arena/runner.py:1-15,408-542`), while
`ZeroWeightOrchestratorV1` owns a separate orchestration-specific heuristic
mutation/archive loop that never mutates production routing
(`dharma_swarm/coordination/orchestrator_v1.py:1-12,47-78,161-238`). This proves
overlap without composition in the scanned paths; it does not prove either
domain organ is redundant.

### Claim 5 — “Idempotency is keyed too late”

**PARTIAL.** The diagnosis is right for the default live composition, but
Claude's citations are wrong. There is no `dharma_swarm/intent.py`; `TaskIntent`
is in `intent_router.py` and has no stable intent identity
(`dharma_swarm/intent_router.py:163-173`). `orchestrator.py:2466` constructs a
side-effect key; it is not the identity mint
(`dharma_swarm/orchestrator.py:2455-2467`).

`TaskBoard` already has an admission-time identity seam when passed an explicit
identity or a runtime store, but `SwarmManager.create_task` supplies neither and
the live manager constructs TaskBoard without that store
(`dharma_swarm/task_board.py:232-264,310-357`;
`dharma_swarm/swarm.py:632-637,1127-1165`). The default orchestrator instead
prepares a claim and ensures identity at dispatch
(`dharma_swarm/orchestrator.py:2235-2253`). Empty idempotency defaults to
`idem_{run_id}`, and the run ID is generated if missing
(`dharma_swarm/runtime_lifecycle_identity.py:32-65`;
`dharma_swarm/spine/identity.py:78-82`).

Retry stability is not merely absent at ingress. The identity helper injects
identity into task metadata, but `_assign_dispatch` subsequently persists its
earlier `claim_meta` copy; failure requeues from that persisted metadata
(`dharma_swarm/runtime_lifecycle_identity.py:75-77`;
`dharma_swarm/orchestrator.py:1956-2008,2252-2270,2286-2291`). A retry can
therefore lose the prior run-derived identity and mint another key.

The contract needs two identities, not one overloaded key: a stable admitted
`intent_id` that survives retries, plus unique attempt/run/claim identity. Each
external effect then derives a deterministic effect scope from the admitted
intent and canonical action semantics; identical legitimate requests must
remain distinguishable.

### Claim 6 — “~96 DBs, 368 connects, 15+ ledgers, 0 Postgres/OTel/signing”

**PARTIAL; the architectural symptom is real, the quantified bundle is not.**
On the pinned main snapshot, bounded lexical commands produce 107 distinct
`.db` names across tracked content, 30 under `dharma_swarm/` plus `api/`, 360
Python SQLite connect call-lines, 181 of those under runtime/API, and 14
non-test source filenames containing `ledger` (evidence command E8). These are
lexical observations—not live database, writer, or authority counts.

There is no verified Postgres runtime integration: core dependencies include
`aiosqlite` but no `psycopg`/`asyncpg`, and evidence command E9 finds no runtime
Postgres DSN (`pyproject.toml:15-31`). There is an OTel-shaped
`EvidenceReceipt.to_otel_span()` adapter, but no verified SDK/export pipeline
(`dharma_swarm/spine/receipt.py:1-6,81-128`; evidence command E10).

“Zero cryptographic signing” is false. Forge and Telos Kernel implement Ed25519
sign/verify paths, and `cryptography` is a core dependency
(`dharma_swarm/forge_v1/forge_v2/verify_promotion.py:59-62,78-101,174-229`;
`packages/telos-kernel/telos_kernel/receipt.py:148-206`;
`pyproject.toml:27-29`). Evidence command E11 finds no non-test caller for the
Forge signing entrypoints. Corrected claim: **signing organs exist, but runtime
episodes, general receipts, and release artifacts do not traverse one
whole-system signing policy.**

The storage registry is not a consolidation spine. It explicitly permits every
module to keep private persistence and provides a process-local module-global
registry plus versioned JSONL helpers
(`dharma_swarm/storage_schema_registry.py:1-35,139-212,278-315`). Evidence
command E12 finds no production adopter.

## Q1 — Is whole-organism H1 the highest-leverage first move?

**DISAGREE.** Re-rooting the current scanner on the pinned main snapshot yields:

| Root | Modules | Effect sites | Bypasses | Mediated |
|---|---:|---:|---:|---:|
| `dharma_swarm.organism` | 110 | 651 | 651 | 0 |
| `dharma_swarm.orchestrator` | 229 | 1,268 | 1,260 | 8 |
| `dharma_swarm.swarm` | 471 | 3,124 | 3,116 | 8 |
| `dharma_swarm.orchestrate_live` | 515 | 3,702 | 3,694 | 8 |

Evidence command E13 reproduces the table. The same scanner misses known
subprocess calls, so one organism-wide integer is simultaneously noisy and
blind. The current test requires exact equality and therefore flags any raw
count change (`tests/test_graph_seam_ledger.py:113-125`), but after a reviewed
baseline decrease it cannot mechanically distinguish genuine mediation from
lost reach, removed functionality, or detector blindness. Effect entries carry
file, line, symbol, category, classification, and scope—but no dynamic-reach or
consequence field (`tests/antithesis_support/effect_scan.py:258-267`).

Separate three moves. The first read-only packet is a bounded entrypoint and
scanner-blindness map. The first runtime code packet, after runtime/identity
authority exists, is a strict per-attempt/effect gateway. The first Harness
packet then combines the two for one real task-claim → orchestrator → one
provider/tool effect → receipt workload, consistent with #1004's slice rule
(`#1004@475b9cb3:docs/plans/THE_KEEL_2026-07-17.md:265-274`). Enumerate all
provider and consequential-tool entrypoints; classify known subprocess effects
as `process/bypass`; type only unresolved dynamic targets as `unknown`; combine
static discovery with a dynamic trace; inject missing-store, duplicate-claim,
and post-call-crash faults; assert zero provider or consequential-tool effects
without a corresponding durable child claim. Keep the global inventory
diagnostic until it is precision-tested.

## Q2 — Is fail-open → fail-closed safe?

**PARTIAL.** Strict **production admission** is correct; a blind low-level
boolean flip is not enough. The invariant should be:

> No paid, mutating, or externally consequential dispatch executes without a
> durable admitted intent, authenticated authorization, stable operation digest,
> reserved budget, and fenced claim token.

Required behavior:

1. Missing store, admitted intent, or authenticated authorization at outer
   admission returns typed `PROTECTION_UNAVAILABLE`; the wrapped unit remains
   unstarted.
2. Missing stable canonical operation digest, budget reservation, child effect
   identity, or fenced claim at a later per-effect gateway returns a typed
   failure; that child effect count remains zero and the already-started task
   fails or quarantines explicitly.
3. Test/dev uses a real temporary durable store. A separately named migration
   shadow profile may observe unprotected calls but cannot authorize production.
4. False-like `DHARMA_SPINE_DISPATCH` values are rejected in production. An
   emergency degraded profile must be separately typed by effect class; human
   authority cannot generically make paid, mutating, or non-idempotent direct
   execution safe (`dharma_swarm/orchestrator.py:2568-2577,2627-2637`).
5. A pre-call failure backs off without invocation. A post-call completion
   ambiguity becomes `OUTCOME_UNKNOWN` quarantine, not automatic re-execution
   (`dharma_swarm/graph/durable_invoker.py:670-707`).
6. Where supported, the same provider-native idempotency key crosses the
   provider boundary. Without provider dedupe or an outcome query, a crash
   during the call cannot honestly prove exactly-once behavior; Titanium already
   requires class-specific semantics and unknown-outcome quarantine
   (`docs/plans/TITANIUM_GRADE_REPOSITORY_HARDENING_2026-07-10.md:1374-1401`).
7. Canonical completion and its event/outbox record commit atomically.
   `complete_idempotent_side_effect` currently commits the canonical row before
   later reads/audit writes can still raise
   (`dharma_swarm/runtime_state.py:3573-3613`).
8. The outer task claim derives child attempt and effect keys. Every provider
   attempt and consequential tool call receives its own pre-effect admission,
   budget, authority, and outcome state; one
   `invoke_agent:{task_id}:{agent_id}` row cannot stand in for the nested effect
   loop (`dharma_swarm/orchestrator.py:2465-2478`;
   `dharma_swarm/agent_runner.py:1845-2008,2321-2421`).

A “counted unprotected-dispatch receipt” is migration telemetry, not the safety
compromise. If authoritative persistence is unavailable, that receipt cannot
establish protection; after the wrapped unit performed nested effects, counting
the gap cannot reverse their cost or consequences
(`dharma_swarm/orchestrator.py:2470-2478`;
`dharma_swarm/agent_runner.py:1845-2008`).

## Q3 — Are DB counts the problem, and should this become one Postgres?

**PARTIAL with Claude.** He is right that moving incoherent schemas into one
server does not create authority or transaction semantics. He is too quick to
call one logical Episode Ledger on SQLite sufficient.

SQLite contention is already acknowledged in source: runtime state documents
single-writer serialization, TaskBoard allows a 30-second daemon/SwarmLens lock
window, MessageBus and OperatorBridge retry `database is locked`, and TaskBoard
batching exists to reduce write-lock contention
(`dharma_swarm/runtime_state.py:437-454`;
`dharma_swarm/task_board.py:74-98,386-396`;
`dharma_swarm/message_bus.py:125-177`;
`dharma_swarm/operator_bridge.py:226-315`). A Postgres ADR must test whether its
concurrency/isolation model, network writer access, and HA options materially
improve the measured workload; choosing a product name is not that evidence.

The AGNI workflow contains a comment recording a prior observation that there
were no live peers and that messages were mirrored from a local hub; that
comment is not a current live probe. Intended fleet transport is NATS/JetStream,
not direct remote SQLite writers
(`.github/workflows/a2a-agni-live-contact.yml:43-46`;
`dharma_swarm/a2a/nats_transport.py:1-5,42-75`). Current task creation and board
projection also cross stores in separate operations, which Postgres cannot fix
without first redefining ownership and transaction boundaries
(`dharma_swarm/task_board.py:266-305,352-378`;
`dharma_swarm/board/adapters/taskboard_adapter.py:169-203`).

**Decision:** keep SQLite for the first single-host coherent hull, behind one
write-owning Runtime Host. Instrument lock wait, `SQLITE_BUSY`, queue latency,
write rejection, DB growth, restore time, and RPO/RTO. Trigger a Postgres ADR
only when a whole-system soak shows a ratified contention SLO breach, multiple
trusted runtime-host writers become a real requirement, or single-host
Litestream cannot meet the ratified HA/RPO/RTO. If triggered, migrate only
canonical operational state behind a storage protocol; retain SQLite as the
hermetic Harness backend and run dialect-differential tests.

## Q4 — Which system should own fitness?

**PARTIAL.** There should not be one universal scalar owner, and source does not
yet justify making either existing engine the other's lifecycle controller.

- Arena owns correctness evaluation only for the orchestration subjects and
  taskpack its frozen scorer covers; it is replayable, control-relative,
  budget-parity checked, and significance-aware
  (`dharma_swarm/coordination/arena/runner.py:1-15,408-542`).
- DarwinEngine owns code/runtime proposal lifecycle, gates, sandbox execution,
  archival, and promotion (`dharma_swarm/evolution.py:2150-2255,2505-2633,3245-3416`).
- `ZeroWeightOrchestratorV1` owns orchestration search/archive, a different
  domain from Darwin's code mutation; overlap with Arena needs an explicit
  boundary and parity study, not a redundancy declaration
  (`dharma_swarm/coordination/orchestrator_v1.py:47-78,161-238`).

The integration contract should be a typed evaluation result: subject and
evaluator versions/hashes; corpus/taskpack hash; metric vector; hard-floor
verdict; budget; uncertainty/significance; evidence tier; receipt references.
Arena can produce it for orchestration genomes; a domain evolution adapter or
shared protocol consumes it without reinterpreting correctness. Keep, adapt, or
retire `ZeroWeightOrchestratorV1` only after evaluator parity and caller/evidence
migration. No metric vector becomes a whole-repo scalar.

## Q5 — Is a pre-#1004 hardening pass correctly sequenced?

**DISAGREE for a new Keel-derived implementation campaign; AGREE for this
read-only correction pass.**
#1004 is an inert working plan and its waves are explicitly unauthorized
(`#1004@475b9cb3:docs/plans/THE_KEEL_2026-07-17.md:5-17,385-405`). Starting new
code from #1004 before ratification would reverse ratify → admit → implement;
already-authorized Titanium Phase-0 work continues independently.

The execution order already exists: Titanium Phase 0 ends only after every
bounded packet and an independent fresh-clone proof pass on merged main; no
deferred phase may begin first
(`docs/plans/TITANIUM_GRADE_REPOSITORY_HARDENING_2026-07-10.md:1261-1333`).
Titanium then orders security, runtime correctness, state authority/restore, and
wiring truth
(`docs/plans/TITANIUM_GRADE_REPOSITORY_HARDENING_2026-07-10.md:1335-1467`).
`ACTIVE_TRACK.yaml` still marks Titanium active, lists WP-0S through WP-0I as
blocking, and forbids Phase 1–7 implementation or a new truth store before
Phase 0 closes (`docs/governance/ACTIVE_TRACK.yaml:1703-1719,1835-1895`).

If dangerous live autonomy is actually enabled, immediate operator containment
is the exception: disable paid dispatch, live mutation, or unsafe ingress while
preserving evidence. That is incident containment, not authorization for an
unbounded pre-#1004 campaign.

## Where Claude is wrong

1. **H1 is not the best first implementation packet.** The current whole-system
   scan is 3,116 bypasses from the `swarm` root and still misses known
   subprocess effects (Q1; evidence command E13).
2. **Static import closure can under-report.** The ledger's “never
   under-reports” claim is contradicted by its finite detector and present
   subprocess call sites (`tests/antithesis_support/seam_ledger.py:10-18`;
   `tests/antithesis_support/effect_scan.py:25-76`;
   `dharma_swarm/providers.py:727`; `dharma_swarm/swarm.py:1538`).
3. **Checkpoint/replay is not literally test-only.** It is an unintegrated
   production library (`dharma_swarm/graph/scheduler.py:104-178,190-267`;
   evidence command E4).
4. **A counted unprotected-dispatch receipt is observability, not safety.** The
   external call can already have occurred before durable completion fails
   (`dharma_swarm/graph/durable_invoker.py:670-707`).
5. **The current durable wrapper is not a per-provider/effect fence.** It wraps
   an entire `runner.run_task` unit containing repair attempts and a nested
   provider/tool loop
   (`dharma_swarm/orchestrator.py:2427-2435,2465-2478`;
   `dharma_swarm/agent_runner.py:1845-2008,2321-2421`).
6. **Darwin real-test fitness is not terminal-only.** Live free-grind calls
   `run_cycle`, and its focused real-fitness test passes
   (`dharma_swarm/orchestrate_live.py:1263-1371`;
   `dharma_swarm/evolution.py:2192-2255`; evidence command E6).
7. **The more serious Darwin defect is mutation attribution.** Shadow/no-diff
   proposals can score the unchanged checkout
   (`dharma_swarm/orchestrate_live.py:1317-1367,1373-1404`;
   `dharma_swarm/evolution.py:3386-3394`).
8. **The API failure is not hidden; it is downgraded into an ordinary error
   response.** Its request/signature mismatch is still total
   (`api/routers/commands.py:25-32`; `api/models.py:13-17,248-250`;
   `dharma_swarm/swarm.py:2731-2739`).
9. **`intent.py` is the wrong file and `orchestrator.py:2466` is the wrong mint
   site.** The actual intent type and effect key are at
   `intent_router.py:163-173` and `orchestrator.py:2455-2467`.
10. **The DB/connect numbers are unscoped grep snapshots, not architecture
   facts.** Exact bounded commands produce different counts and still do not
   enumerate live writers (evidence command E8).
11. **“0 OTel” and “0 signing” are too absolute.** An OTel-shaped adapter and
    Ed25519 implementations exist; end-to-end runtime adoption does not
    (`dharma_swarm/spine/receipt.py:81-128`;
    `dharma_swarm/forge_v1/forge_v2/verify_promotion.py:174-229`;
    `packages/telos-kernel/telos_kernel/receipt.py:148-206`).
12. **`storage_schema_registry.py` is not a consolidation spine.** It is an
    optional JSONL/version registry with no production adopter
    (`dharma_swarm/storage_schema_registry.py:1-35`; evidence command E12).
13. **Fitness ownership is not a binary Darwin-versus-Arena choice.** Arena is
    authoritative only for its frozen orchestration taskpack/scorer;
    DarwinEngine and ZeroWeight have different lifecycle/search roles. A typed
    domain evaluation protocol must precede any keep/adapt/retire decision (Q4).

## Required #1004 corrections before merge

These are nine document corrections plus one PR-body refresh. They do not
require a runtime hardening PR first.

1. **Remove pseudo-authority.** Replace “Mechanical subordination (binding)”
   with “Subordination boundary.” A `working_plan` is not one of the repo-level
   authority files (`#1004@475b9cb3:docs/plans/THE_KEEL_2026-07-17.md:9-17`;
   `docs/AGENTS.md:13-27`).
2. **Make the CI home prospective.** Lines 120–128 should say applicability
   semantics are a candidate contract for Titanium WP-0F1/0F2. The current CI
   contract has `required` and `advisory` check arrays but no packet-dimension
   or applicability schema (`docs/governance/CI_TRUTH_CONTRACT.json:1-6,55-67`).
   Delete “it has no field for an aggregate number, so none can exist”; a JSON
   omission is neither an invariant nor enforcement.
3. **Reconcile Episode Ledger with existing operational event families.** Name
   the records and transaction boundaries it would reuse, migrate, or retire
   from `session_events`, `execution_identities`, `runtime_receipts`, and
   `idempotency_records`; prohibit a new store before the Phase-3 state-authority
   ADR. `runtime.db` is a candidate host, not a pre-ratified destination or a
   universal truth owner
   (`dharma_swarm/runtime_state.py:198-283`;
   `#1004@475b9cb3:docs/plans/THE_KEEL_2026-07-17.md:205-228,439-440`). Ontology,
   memory, governance, and payload bytes retain separately ratified fact owners.
4. **Delete the Helm slot-donor assertion.** The authoritative portfolio marks
   Helm `ACTIVE`, serving `substrate-nativeness`, with an explicit blocker
   (`docs/governance/ACTIVE_TRACK.yaml:1264-1279,1325-1333`). A working plan may
   propose an operator decision; it cannot pre-adjudicate a slot donor
   (`#1004@475b9cb3:docs/plans/THE_KEEL_2026-07-17.md:247-276`).
5. **Preserve human merge in the dated trigger.** Replace “allocation
   auto-archives” with “the workflow opens an archive proposal; no state changes
   until human merge.” The current paragraph otherwise conflicts with its own
   human-only authority rule
   (`#1004@475b9cb3:docs/plans/THE_KEEL_2026-07-17.md:317-345,420-423,442-443`). Define how an
   external signer is authenticated before “signed” becomes a gate, and reuse
   an owned receipts family instead of silently creating another ledger.
6. **Correct the first vertical slice's prerequisites.** A fenced Runtime Host
   write lease, stable admitted `intent_id`, and named budget authority precede
   the first protected effect. Then fence each provider/consequential-tool
   attempt—not just the outer task—with reservation, claim, typed completion or
   quarantine, and receipt. Broad storage consolidation may follow in Phase 3;
   do not make it a prerequisite for closing the dangerous effect seam, but do
   not build that seam on an ambiguous writer or run-derived key
   (`dharma_swarm/swarm.py:632-666`;
   `dharma_swarm/runtime_lifecycle_identity.py:32-65`;
   `#1004@475b9cb3:docs/plans/THE_KEEL_2026-07-17.md:387-405`).
7. **Defer execution to Titanium and decouple the witness.** State that Keel
   implementation packets follow Titanium's current Phase-0 exit and Phase
   1→4 order. An outside witness gates an external-value claim; it must not gate
   an internal dispatch-safety repair
   (`docs/plans/TITANIUM_GRADE_REPOSITORY_HARDENING_2026-07-10.md:1267-1467`;
   `#1004@475b9cb3:docs/plans/THE_KEEL_2026-07-17.md:409-423`).
8. **Scope the Harness reach claim.** Replace “verified not to reach” with the
   exact roots/detectors actually measured, and say that dynamic dispatch and
   unsupported effect syntax remain unverified. The present scanner misses
   known subprocess calls in its own `swarm` closure
   (`#1004@475b9cb3:docs/plans/THE_KEEL_2026-07-17.md:265-268`; evidence command
   E13b).
9. **Remove stale merge sequencing.** #1004 still recommends merging #1005
   first, but #1005 is already merged at `a47c110c`; replace that sentence with
   a current merged-main dependency statement
   (`#1004@475b9cb3:docs/plans/THE_KEEL_2026-07-17.md:411-413`; evidence command
   E17).
10. **Refresh the PR description at exact head.** At current head `475b9cb3`,
   the connector reports one file and +451 lines, while the body says +431; the
   body also retains the false one-call budget claim and the stale #1005-first
   recommendation. Reproduce with the PR metadata connector and evidence
   commands E1, E15, E17, and E19.

After those edits: rebase, run exact-head DocOps and the one-file diff check,
obtain a provider-diverse raw-source review, and let the operator decide merge.
Even if merged, #1004 remains an inert working-plan proposal unless canonical
authority later ratifies it; it launches no runtime behavior
(`#1004@475b9cb3:docs/plans/THE_KEEL_2026-07-17.md:9-17`).

## The coherent-system target

The repository should converge on this authority flow:

```text
authenticated ingress derives request identity and authorization context
    -> one Runtime Host / fenced writer lease admits and binds stable intent_id
    -> work-admission transaction:
       intent/task + authorization + bounds + admission event/outbox
       COMMIT
    -> before each consequential provider/tool effect:
       canonical operation digest + child attempt/effect identity
       + budget reservation + fenced effect claim + effect_requested + outbox
       COMMIT effect-admission transaction
    -> that provider/tool effect executes outside the database transaction
    -> after each effect:
       typed outcome | OUTCOME_UNKNOWN quarantine + budget settlement/refund
       + receipt + event/outbox + task transition only when appropriate
       COMMIT effect-completion transaction
    -> idempotent projections: ontology, dashboard, search, analytics, training
```

No database transaction spans a provider or network call. `ExecutionIdentity`
currently has no `intent_id`, and `TaskBoard` generates `task_id` internally;
the Phase-2 admission packet must extend the TaskBoard seam to accept and bind a
pre-minted stable `intent_id`, while retaining distinct attempt, run, claim, and
effect identities
(`dharma_swarm/spine/identity.py:28-52`;
`dharma_swarm/task_board.py:310-358`).

Current source has more than one composition root: `orchestrate_live` creates a
`SwarmManager` with the canonical `STATE_DIR`, while `api.main.get_swarm()` can
create another manager with the class default `.dharma`
(`dharma_swarm/orchestrate_live.py:253-273`;
`api/main.py:89-109`; `dharma_swarm/swarm.py:116-124`). This is not proof both
are deployed simultaneously; it is proof the source permits competing runtime
owners. Titanium already requires a durable daemon ownership lease and refusal
of a second writer
(`docs/plans/TITANIUM_GRADE_REPOSITORY_HARDENING_2026-07-10.md:1374-1411`).

### Authority by fact, not by file count

| Logical fact family | Proposed authority | Physical constraint |
|---|---|---|
| portfolio, governance, merge, deployment, irreversible decisions | protected Git authority surfaces + human operator | never delegated to an ontology or runtime DB |
| ontology schema/type definitions | reviewed code/ADR + human merge | runtime data cannot silently redefine the schema |
| reviewed semantic ontology instances | one ratified `OntologyStore` path | operational outcomes project only after typed review/promotion |
| admitted intent, task, attempt, claim, lease, budget, effect, operational outcome, receipt, event, outbox | Runtime Host | `runtime.db` is a candidate only after explicit TaskBoard/event-family migration |
| memory context/read/write/promotion policy | MemoryKernel front door; subordinate stores are classified explicitly | canonical promotion remains KnowledgeOps/Chetana/human governed |
| NATS/JetStream delivery and redelivery | transport layer | carries facts; does not own domain truth |
| Board cards, dashboard, search, vectors | projections | Board's event log remains facade audit evidence until explicitly migrated |
| immutable payload bytes | existing ratified artifact owner | referenced and digest-verified through `artifact_records(payload_path, checksum)` |

This separation respects the documented ontology proposal's code-defined,
operator-merge boundary and the current MemoryKernel boundary rather than
treating one file as universal truth
(`docs/architecture/ADRs/ADR-008-ontology-api-name-grammar.md:10-18`;
`CLAUDE.md:122`;
`docs/architecture/MEMORY_KERNEL_PROD_BAR.md:8-30`). Operational provider/effect
outcomes belong to Runtime Host; only a reviewed semantic result may be
promoted or projected into ontology. The existing `store_sync` flows in the
opposite direction—ontology `Outcome` to runtime `ArtifactRecord`—so reversing
or retiring it is an explicit authority migration, not a drop-in projector swap
(`dharma_swarm/engine/store_sync.py:74-110`).

`runtime.db` already mixes operational tables, memory facts/edges, context
bundles, and projections, so the state ADR must be record-family granular
(`dharma_swarm/runtime_state.py:30-283`). Board cards are projections, but the
Board event log remains the facade's audit source until migration proves a new
owner (`docs/architecture/SWARM_BOARDSTORE_SPEC.md:34-38,2203-2212`). Payload
records already include path and checksum; do not create a new blob substrate
without an owner and migration
(`dharma_swarm/runtime_state.py:112-127`).

The existing manifest names runtime, ontology, and Board event-log paths but
omits TaskBoard, MessageBus, and memory DB authority/backup roles
(`ACTIVE_SURFACE_MANIFEST.yaml:15-34`; `dharma_swarm/swarm.py:632-647`). The
first state packet must inventory every store as `canonical`, `derived`,
`cache`, `mirror`, `evidence`, or `host_local`, with owner process, schema
version, backup owner, and reconstruction source. Titanium Phase 3 already
requires that authority table and semantic empty-host restore
(`docs/plans/TITANIUM_GRADE_REPOSITORY_HARDENING_2026-07-10.md:1413-1441`).
Mechanically ratchet proliferation: every proposed store, schema, or persistence
path must declare its fact family, authority/projection role, writer process,
schema version and migration, backup or rebuild source, and a negative control
showing an undeclared store is rejected. The current optional registry does not
enforce that contract (`dharma_swarm/storage_schema_registry.py:1-35,139-212`).

## Whole-swarm execution order

This is a proposed order under existing owners, not a new track.

### 0. Contain, if and only if a live probe shows exposure

Verify production ingress, paid dispatch, live mutation, direct-spine bypass,
and writer count. If an unsafe mode is live, the operator disables it while
retaining evidence. Container defaults already set evolution shadow on, live
mutation off, and spine dispatch on, but configuration defaults do not prove a
running host's state (`docker-compose.yml:78-109`).

### 1. Repair and merge the doctrine/evidence layer

This documentation repair and already-authorized Titanium Phase-0 work run
independently and may proceed in parallel.

1. Apply the ten #1004 corrections above; obtain exact-head review; leave merge
   and any later canonical ratification to the human operator.
2. Treat #1007 as candidate evidence, not an execution ledger. Its idempotency
   row cites a nonexistent `_clear_attempt_identity_metadata`, its one-call-site
   budget count omits the argument-bearing call, and its day estimates lack a
   protocol (`#1007@994d45f:reports/governance/keel/ARCHITECTURE_AUDIT_2026-07-18.md:30-38,50-61,129-143`;
   evidence commands E14–E15). Correct or supersede those rows before homing
   findings.
3. Keep #1006 docs-only and parked. It calls itself “operator-ratified” while
   its gate grants no authority; labels C1 “production truth” although its seam
   remains default-off shadow; orders C1 production wiring before the C2
   reliability ring; supplies its own environment bootstrap instead of
   Titanium's frozen bootstrap; and reports a subsystem gauntlet score that
   cannot become a whole-repo quality claim
   (`#1006@c4037b6:docs/plans/DHARMAGRAPH_ASCENT_SPEC_2026-07-17.md:1,15-30,40-46,88-106,144-156,178-220`).

### 2. Finish Titanium Phase 0 on merged main

Do not redo merged packets. Reconcile the receipts for #1005, #1019, #1026,
#1027, #1028, #1029, #1031, and #1032 against their acceptance contracts, then
continue from the first unfinished blocker among WP-0S and WP-0A through WP-0I,
including C1R/C1/C2 and F1/F2. Phase 0 closes only with one independent WP-0I
fresh-clone exit on merged main in which `make test-fast` runs twice as required
by the frozen protocol (evidence command E17)
(`docs/plans/TITANIUM_GRADE_REPOSITORY_HARDENING_2026-07-10.md:1261-1333`;
`docs/governance/ACTIVE_TRACK.yaml:1835-1895`). Do not open a separate “Keel
implementation” track or truth store.

### 3. Ratify findings into existing owners

After Phase 0, the operator maps each accepted finding to an existing track,
owned surface, finding ID, acceptance test, rollback, and packet. The
Ratification Act should decide runtime-host ownership, task-lifecycle authority,
and the state-authority table; it should not create another orchestrator,
ledger, or universal policy engine
(`#1004@475b9cb3:docs/plans/THE_KEEL_2026-07-17.md:247-274,409-423,427-445`;
`docs/governance/ACTIVE_TRACK.yaml:118-133`).

### 4. Execute one vertical hull in Titanium's Phase 1→4 order

1. **Security boundary packet (Phase 1):** authenticated ingress and confined
   mutation/effect execution; no public fail-open route
   (`docs/plans/TITANIUM_GRADE_REPOSITORY_HARDENING_2026-07-10.md:1335-1366`).
2. **Runtime Host + identity packet (Phase 2):** one writer lease; API/dashboard
   client path identified; extend TaskBoard admission to accept and bind a
   pre-minted stable `intent_id`; name budget authority; retain unique
   attempt/claim IDs; add retry-identity and stale-writer fencing regressions
   (`dharma_swarm/task_board.py:232-264,310-357`;
   `docs/plans/TITANIUM_GRADE_REPOSITORY_HARDENING_2026-07-10.md:1368-1411`).
3. **Atomic dispatch gateway packet (Phase 2):** reserve budget and claim before
   each provider or consequential-tool effect; derive child attempt/effect keys
   beneath the stable intent and canonical operation digest;
   settle/refund/quarantine after each effect;
   keep consequential production activation default-off; use provider-native
   idempotency where supported; add bypass-resistance and crash-window tests
   (`dharma_swarm/graph/durable_invoker.py:395-524,630-707`;
   `docs/plans/TITANIUM_GRADE_REPOSITORY_HARDENING_2026-07-10.md:1374-1409`).
4. **Lifecycle authority/outbox packet (Phase 3):** ratify the record-family
   authority table and co-locate only facts requiring atomicity. Work admission
   commits stable intent/task, authorization, bounds, event, and outbox. Before
   each consequential effect, a separate transaction commits child
   attempt/effect identity, canonical operation digest, reservation, fenced
   claim, request event, and outbox. The effect runs outside every DB
   transaction. Its completion
   transaction commits typed outcome/quarantine, settlement/refund, receipt,
   event/outbox, and a task transition only when appropriate. Add migrations,
   backup, boot reconciliation, and semantic restore
   (`dharma_swarm/runtime_state.py:198-283`;
   `docs/plans/TITANIUM_GRADE_REPOSITORY_HARDENING_2026-07-10.md:1413-1441`).
5. **Composition-root cutover + bounded Harness packet (Phase 4):** route API,
   dashboard, CLI, cron, and workers through the selected Runtime Host; fence
   stale/non-owner writers; explicitly migrate the authority direction of
   `store_sync` only after proof. Combine static and dynamic coverage for that
   vertical path, with duplicate, missing-store, timeout, completion-ambiguity,
   and process-kill controls. Activate consequential production dispatch only
   after all canonical routes and bypass negatives pass; then widen slice by
   slice
   (`dharma_swarm/engine/store_sync.py:74-163`;
   `#1004@475b9cb3:docs/plans/THE_KEEL_2026-07-17.md:265-274`;
   `docs/plans/TITANIUM_GRADE_REPOSITORY_HARDENING_2026-07-10.md:1443-1467`).

### 5. Unify evaluation after the hull is trustworthy

Define the typed domain evaluation-result protocol. Arena may author results
only for the frozen orchestration taskpack/scorer it actually owns; DarwinEngine
and `ZeroWeightOrchestratorV1` keep their current domains until parity, caller,
and evidence migration justify a keep/adapt/retire decision. Repair the evolve
API and require mutation-attributable evaluation before any promotion claim
(`api/routers/commands.py:25-32`; `dharma_swarm/evolution.py:2150-2255`;
`dharma_swarm/coordination/arena/runner.py:408-542`).

### 6. Restore, soak, then decide Postgres

Prove backup coverage for every canonical store, empty-host restore, boot
reconciliation, a common semantic recovery cut, and no duplicated consequential
effect. Independent replicas of multiple SQLite files do not create one
cross-store transaction cut; use event/outbox watermarks and boot reconciliation,
or co-locate facts that must commit atomically. The VPS Litestream
config currently covers only `runtime.db`, while the older config covers a
different partial set; no tracked restore command was found
(`scripts/ops/litestream.yml:1-16`; `scripts/litestream.yml:1-61`; evidence
command E16). Measure p95/p99 transaction and lock wait, busy rate, queue
depth/age, WAL growth and checkpoint duration, backup lag, restore time, and
host/power-loss behavior under concurrent claims, reservations, receipt
appends, telemetry, long readers/writers, crash/restart, and migration
interruption. Current runtime and TaskBoard use WAL with `synchronous=NORMAL`,
so the accepted durability and RPO model must be ratified and fault-tested
(`dharma_swarm/runtime_state.py:437-454`;
`dharma_swarm/task_board.py:121-134`). Use those measurements—not DB filename
count—to accept SQLite or trigger a Postgres ADR.

### 7. Launch one externally legible specimen

Only after the vertical hull passes security, crash, replay, restore, and bypass
controls should one venture specimen exercise it. Separate delivery,
consumption, retention, and outcome evidence as #1004 already requires
(`#1004@475b9cb3:docs/plans/THE_KEEL_2026-07-17.md:317-341,401-405`). External
evidence validates externally scoped claims; it does not waive internal quality
floors.

## Launch gates

“Launch #1004” and “launch the organism” are different decisions.

**Working-plan operator review gate:** the ten corrections above; one-file
exact-head diff; DocOps green relative to an honest baseline; provider-diverse
raw-source review; human-only merge. No runtime change or canonical authority
follows merely from the merge
(`#1004@475b9cb3:docs/plans/THE_KEEL_2026-07-17.md:9-17,100-106`).

**Organism production gate:** all of the following are independently evidenced
on merged main or the exact deployed artifact:

- Titanium Phase 0/WP-0I passed from a fresh clone
  (`docs/plans/TITANIUM_GRADE_REPOSITORY_HARDENING_2026-07-10.md:1261-1308`);
- production ingress and mutation boundaries fail closed
  (`docs/plans/TITANIUM_GRADE_REPOSITORY_HARDENING_2026-07-10.md:1335-1366`);
- exactly one Runtime Host owns the writer lease; a second owner is refused
  (`docs/plans/TITANIUM_GRADE_REPOSITORY_HARDENING_2026-07-10.md:1374-1411`);
- every canonical operational write route—API, CLI, cron, dashboard, and
  worker—traverses Runtime Host, and stale/non-owner writers are fenced; the
  lexical SQLite-connect count is discovery evidence, not proof of route closure;
- every consequential dispatch and child provider/tool attempt has admitted
  intent, authorization, stable canonical operation digest, budget, fenced
  claim, provider/effect identity, and typed outcome/ambiguity semantics
  (`#1004@475b9cb3:docs/plans/THE_KEEL_2026-07-17.md:232-243`;
  `docs/plans/TITANIUM_GRADE_REPOSITORY_HARDENING_2026-07-10.md:1374-1401`);
- for each effect class and declared fault model, the crash matrix proves local
  gateway invocation counts and retry/quarantine behavior. A real provider
  call's remote outcome remains `OUTCOME_UNKNOWN` unless provider-native dedupe
  or outcome-query evidence resolves it
  (`docs/plans/TITANIUM_GRADE_REPOSITORY_HARDENING_2026-07-10.md:1376-1400,1411`);
- every canonical store is owned/backed up; no undeclared persistence path can
  pass admission; and an empty-host restore reaches a common semantic recovery
  cut without duplicating an external effect
  (`docs/plans/TITANIUM_GRADE_REPOSITORY_HARDENING_2026-07-10.md:1413-1441`);
- SQLite WAL/lock/queue behavior, backup lag, and restore time meet ratified
  p95/p99, RPO, and RTO thresholds under contention, abrupt process death, and
  host/power loss (`dharma_swarm/runtime_state.py:437-454`;
  `dharma_swarm/task_board.py:121-134`);
- the bounded dispatch Harness has a retained mutation control and failure
  control
  (`#1004@475b9cb3:docs/plans/THE_KEEL_2026-07-17.md:265-274`); and
- the reviewed source head equals the deployed artifact, with no unreviewed
  bypass or live-mutation mode
  (`#1004@475b9cb3:docs/plans/THE_KEEL_2026-07-17.md:93-106,232-243`).

## Review-branch validation boundary

`git diff --check` passes, the focused Darwin real-fitness test passes, and the
changed-file DocOps check passes with count drift treated as advisory. Strict
`make docops-integrity` fails on the clean pinned base before this document is
added: Python LOC, test-file, test-function, Markdown-line, and generated
auto-section baselines are already stale. This review makes no strict-green
claim and does not expand its one-file boundary to regenerate unrelated DocOps
projections. Evidence command E18 reproduces both results. The PR should remain
draft until the operator decides whether upstream strict convergence must land
first.

## Evidence appendix — runnable commands

Run source-executing commands from a clean checkout detached at
`26ea66fd07f3fbf688b6399d34c68b9042e20686`. Run `make bootstrap` first and use
`.venv/bin/python`; plain system Python is not a valid dependency proof. This
review's focused rerun used Python 3.12.13 and pytest 9.1.1 and returned
`1 passed`. Git-object commands pin their own commit.

### E1 — source snapshots and one-file boundary

```bash
git rev-parse 26ea66fd07f3fbf688b6399d34c68b9042e20686^{commit}
git rev-parse 475b9cb3c0e055318d85a71170a8d768df70144a
git diff --name-only 26ea66fd07f3fbf688b6399d34c68b9042e20686...475b9cb3c0e055318d85a71170a8d768df70144a
git show 475b9cb3c0e055318d85a71170a8d768df70144a:docs/plans/THE_KEEL_2026-07-17.md | nl -ba
```

### E2 — fail-open and direct-bypass inventory

```bash
git grep -n -E 'Fail-open|WITHOUT idempotency|DHARMA_SPINE_DISPATCH|legacy|direct|complete_idempotent_side_effect failed' \
  26ea66fd07f3fbf688b6399d34c68b9042e20686 -- \
  dharma_swarm/graph/durable_invoker.py dharma_swarm/orchestrator.py
```

### E3 — graph effects scope

```bash
git grep -n -E 'EffectsProvider|SimulatedEffects' \
  26ea66fd07f3fbf688b6399d34c68b9042e20686 -- '*.py'
```

### E4 — graph library integration probe

```bash
git grep -n -E '\b(GraphBuilder|CompiledGraph|GraphPersistenceKernel|SimulatedEffects)\b' \
  26ea66fd07f3fbf688b6399d34c68b9042e20686 -- '*.py' ':!tests/**' |
  rg -v '^[^:]+:dharma_swarm/graph/'
```

Expected: no lexical non-test Python adopter outside `dharma_swarm/graph/`.
This is not a dynamic reachability proof.

### E5 — evolve API signature mismatch

```bash
make bootstrap
PYTHONPATH=. .venv/bin/python -c \
  "import inspect; from api.models import EvolveRequest; from dharma_swarm.swarm import SwarmManager; print(inspect.signature(SwarmManager.evolve)); print(sorted(EvolveRequest.model_json_schema()['properties']))"
```

### E6 — live Darwin real-test path

```bash
make bootstrap
PYTHONPATH=. .venv/bin/python -m pytest -q \
  tests/test_evolution.py::test_run_cycle_uses_inferred_component_pytest_for_real_fitness
```

Pinned result in this review: `1 passed`.

### E7 — Arena/Darwin bridge probe

```bash
git grep -n -E 'ArenaRunner|ZeroWeightOrchestratorV1|coordination\.arena' \
  26ea66fd07f3fbf688b6399d34c68b9042e20686 -- \
  dharma_swarm/evolution.py dharma_swarm/orchestrate_live.py \
  dharma_swarm/swarm.py dharma_swarm/orchestrator.py dharma_swarm/agent_runner.py
git grep -n -E 'from dharma_swarm\.evolution import|import dharma_swarm\.evolution|DarwinEngine\(' \
  26ea66fd07f3fbf688b6399d34c68b9042e20686 -- dharma_swarm/coordination
```

Interpret only within these named live-composition paths: no Arena↔Darwin bridge
appears there. This is not a repo-global absence proof.

### E8 — bounded storage lexical counts

```bash
git grep -n -E '(sqlite3|aiosqlite)\.connect\(' \
  26ea66fd07f3fbf688b6399d34c68b9042e20686 -- '*.py' | wc -l
git grep -n -E '(sqlite3|aiosqlite)\.connect\(' \
  26ea66fd07f3fbf688b6399d34c68b9042e20686 -- dharma_swarm api | wc -l
git grep -h -I -o -E '[A-Za-z0-9_.-]+\.db([^A-Za-z0-9_.-]|$)' \
  26ea66fd07f3fbf688b6399d34c68b9042e20686 -- |
  sed -E 's/[^A-Za-z0-9_.-]+$//' | sort -u | wc -l
git grep -h -I -o -E '[A-Za-z0-9_.-]+\.db([^A-Za-z0-9_.-]|$)' \
  26ea66fd07f3fbf688b6399d34c68b9042e20686 -- dharma_swarm api |
  sed -E 's/[^A-Za-z0-9_.-]+$//' | sort -u | wc -l
git ls-tree -r --name-only 26ea66fd07f3fbf688b6399d34c68b9042e20686 |
  rg '(^|/)[^/]*ledger[^/]*\.(py|go|ts|tsx|rs)$' |
  rg -v '^tests/' | wc -l
```

Pinned outputs: `360`, `181`, `107`, `30`, `14`.

### E9 — Postgres runtime integration probe

```bash
git grep -n -i -E 'psycopg|asyncpg|postgresql://' \
  26ea66fd07f3fbf688b6399d34c68b9042e20686 -- \
  pyproject.toml uv.lock docker-compose.yml Dockerfile\* dharma_swarm api scripts
```

### E10 — OTel runtime adoption probe

```bash
git grep -n -i -E 'to_otel_span|opentelemetry|OTLP' \
  26ea66fd07f3fbf688b6399d34c68b9042e20686 -- \
  pyproject.toml uv.lock dharma_swarm api scripts packages
```

### E11 — signing adoption probe

```bash
git grep -n -E 'sign_receipt\(|sign_promotion_verification\(' \
  26ea66fd07f3fbf688b6399d34c68b9042e20686 -- '*.py' \
  ':!tests/**' ':!dharma_swarm/forge_v1/forge_v2/verify_promotion.py' \
  ':!packages/telos-kernel/telos_kernel/receipt.py'
```

Expected: no non-test caller after excluding the defining modules. The
implementations themselves still exist; this tests adoption, not capability.

### E12 — storage registry production-adoption probe

```bash
git grep -n -E '(register_schema|read_jsonl_versioned|write_jsonl_versioned)\(' \
  26ea66fd07f3fbf688b6399d34c68b9042e20686 -- '*.py' \
  ':!dharma_swarm/storage_schema_registry.py' ':!tests/**'
```

Expected: no output.

### E13 — existing scanner at whole-runtime roots

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=. .venv/bin/python -c \
"from tests.antithesis_support.seam_ledger import import_closure,scan_module,REPO_ROOT
for roots in [('dharma_swarm.organism',),('dharma_swarm.orchestrator',),('dharma_swarm.swarm',),('dharma_swarm.orchestrate_live',)]:
 c=import_closure(roots); e=[x for p in c.values() for x in scan_module(p.relative_to(REPO_ROOT).as_posix())]
 print(roots,len(c),len(e),sum(x['classification']=='bypass' for x in e),sum(x['classification']=='mediated' for x in e))"
```

### E13b — scanner blindness negative control

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=. .venv/bin/python -c \
"from tests.antithesis_support.seam_ledger import import_closure,scan_module,REPO_ROOT
c=import_closure(('dharma_swarm.swarm',))
e=[x for p in c.values() for x in scan_module(p.relative_to(REPO_ROOT).as_posix())]
print('files_present','dharma_swarm.providers' in c,'dharma_swarm.swarm' in c)
print([x for x in e if (x['file'],x['line']) in {('dharma_swarm/providers.py',727),('dharma_swarm/swarm.py',1538)}])"
```

Pinned output: `files_present True True`, then `[]`. Both modules are reachable;
the known subprocess effects are not detected.

### E14 — #1007 stale/nonexistent retry-clear citation

```bash
git grep -n '_clear_attempt_identity_metadata' \
  26ea66fd07f3fbf688b6399d34c68b9042e20686 -- '*.py'
git grep -n '_clear_attempt_identity_metadata' \
  994d45f5fee2d27bd91358bf2609578e18b3baf8 -- '*.py'
```

Expected: no output from either exact tree.

### E15 — budget predicate call sites

```bash
git grep -n 'is_budget_exceeded(' \
  26ea66fd07f3fbf688b6399d34c68b9042e20686 -- dharma_swarm
git grep -n 'is_budget_exceeded(' \
  994d45f5fee2d27bd91358bf2609578e18b3baf8 -- dharma_swarm
```

Expected call sites: `agent_registry.py:479` and
`replication_protocol.py:493`, plus the definition at `agent_registry.py:908`,
in both exact trees.

### E16 — restore-command probe

```bash
git grep -n -E 'litestream restore|restore .*runtime\.db' \
  26ea66fd07f3fbf688b6399d34c68b9042e20686 -- \
  scripts docs docker-compose.yml Makefile .github
```

Expected: no tracked restore command.

### E17 — already-merged Titanium packet receipts

```bash
git log --format='%h %s' 26ea66fd07f3fbf688b6399d34c68b9042e20686 |
  rg '#(1005|1019|1026|1027|1028|1029|1031|1032)\b'
```

Expected commits include `a47c110c`, `6b1c5438`, `1e71e1d4`, `524a0caa`,
`35b11a30`, `84bdc6dc`, `1021b9cc`, and `944dc895`. Presence proves ancestry,
not acceptance; receipt reconciliation is still required.

### E18 — review-diff and DocOps baseline truth

```bash
git diff --check
make docops-integrity
python3 scripts/docops/check_docops_integrity.py \
  --changed-from=26ea66fd07f3fbf688b6399d34c68b9042e20686 \
  --counts-advisory
```

Pinned review result: diff check passes; strict DocOps fails on the clean base
and review branch for the stale baselines named above; changed-file advisory
mode passes. Run the strict command in a clean base checkout to distinguish
pre-existing drift from the expected one-document count delta.

### E19 — current #1004 metadata/body drift

```bash
gh pr view 1004 --repo AmitabhainArunachala/dharma_swarm \
  --json headRefOid,changedFiles,additions,deletions,body,updatedAt
```

Pinned connector observation at `2026-07-19T08:54:01Z`: head
`475b9cb3c0e055318d85a71170a8d768df70144a`, one changed file, +451/−0. The
body still says +431, one budget-predicate call site, and “merge #1005 first.”

---

**Operator authority remains singular:** merge, credentials, deployment,
publication, payments, irreversible effects, and any portfolio change require
the human operator. Provider/model-diverse LLM review is adversarial pressure;
it is not external organizational independence
(`#1004@475b9cb3:docs/plans/THE_KEEL_2026-07-17.md:100-106,420-423`).
