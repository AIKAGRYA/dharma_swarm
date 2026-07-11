# Forge Lab Open-Compute DGM v0.1

**Status:** operator-ratified design contract, implementation not yet complete  
**Target release:** `dharma_swarm.forge_lab` `0.1.0`  
**Current release:** `0.0.0`  
**Canonical host:** Meghadharma (`meghadharma-cloud`)  
**Owner:** operator and Codex RSI Lab Manager  
**Ratified:** 2026-07-10 by the operator in the Codex RSI Lab Manager session  
**Authority:** authorizes implementation, local tests, migrations, and offline
preflight. It does not by itself authorize a public capability claim, production
mutation, secret disclosure, or an unreviewed live campaign.
**Supersession:** defines the v0.1 target that supersedes configuration-genome
search only after every cutover gate passes. Existing v0 runs remain immutable
legacy evidence until then.

Where they conflict for this lab surface, `specs/GODEL_CLAW_V1_SPEC.md`, older
Darwin implementation plans, and Forge launch packets are background rather
than governing protocol.

## 1. Decision

Forge Lab v0.1 will be a genuine, open-compute, archive-based self-improvement
system for coding agents.

Meghadharma remains the dedicated and authoritative RSI VPS. It owns campaign
control, provider routing, receipts, archive state, operator commands, and local
evaluation capacity. The M5 and ephemeral x86 workers may contribute optional
execution capacity, but they do not replace Meghadharma or become a second
source of truth.

The v0.0 global 90,000-token candidate cap is not a scientific validity
boundary. In open exploration, compute usage is measured rather than used to
invalidate a candidate. Unknown provider price is recorded as unknown and can
be reconciled later. Operational fuses remain separate from research budgets.

The mutable unit is no longer only a configuration dictionary. A candidate is
a versioned `AgentBundle` containing a bounded coding-agent implementation that
can improve its own prompts, tools, context strategy, model-use workflow, and
verification behavior. The outer search kernel, evaluator, task answers,
provider credentials, receipts, and safety boundary remain immutable to the
candidate.

## 2. Normative Language

`MUST`, `MUST NOT`, `SHOULD`, `SHOULD NOT`, and `MAY` are normative.

The following terms are distinct:

- **Research budget:** a compute allocation used to compare systems.
- **Operational fuse:** an emergency stop for broken infrastructure, runaway
  concurrency, lost heartbeats, or explicit operator limits.
- **Provider limit:** a model or account constraint such as context length,
  output length, request rate, or quota.
- **Validity:** whether an evaluation is technically trustworthy. High compute
  usage alone does not make an evaluation invalid.

## 3. Goals

1. Discover coding-agent implementations that improve through executable,
   empirically evaluated self-modification.
2. Use available compute aggressively without confusing cost control with
   scientific validity.
3. Preserve every functional stepping stone in a content-addressed archive with
   complete lineage.
4. Evaluate candidates on paired, varied, and sealed tasks using official
   harnesses where available.
5. Make the full configured model pool usable and independently testable on
   Meghadharma through one command.
6. Survive interruption, host restart, provider failure, and operator stop
   without losing completed work or leaving ambiguous state.
7. Produce reproducible receipts that distinguish agent-design gains from
   extra compute, model substitution, task reuse, or evaluator contamination.
8. Give one operator a compact control surface for sustained asynchronous
   search.

## 4. Non-Goals

v0.1 does not:

- train or modify foundation-model weights;
- allow candidates to edit the outer search algorithm, evaluator, holdout,
  archive, receipts, provider broker, credentials, or host controls;
- make production Dharma Swarm mutable from the lab;
- treat an internal benchmark win as public proof of recursive improvement;
- require a known dollar price before useful exploration can run;
- require every heavy benchmark container to execute physically on the VPS;
- copy raw secrets into candidate containers or generated artifacts.

## 5. System Topology

### 5.1 Meghadharma control plane

Meghadharma MUST remain authoritative for:

- campaign definitions and state transitions;
- archive and lineage metadata;
- taskpack registry and split custody;
- provider/model catalog and liveness receipts;
- model-broker credentials and usage accounting;
- run manifests, checkpoints, closeouts, and operator audit logs;
- local lightweight evaluation workers;
- backup and restore status.

There MUST be one canonical Forge checkout and one canonical installed control
surface. The current split between `/root/rsi-lab/current/repo` and
`/root/rsi-lab/current-main/repo` MUST be removed during migration.

### 5.2 Evaluation workers

Workers MAY be:

- isolated containers on Meghadharma for lightweight tasks;
- the M5 for development and Mac-native or subscription-backed routes;
- ephemeral native-x86 workers for full SWE-bench evaluation;
- later, additional registered workers with the same protocol.

Workers are replaceable compute. They MUST NOT own canonical archive state or
provider credentials. A worker receives a signed work packet, candidate bundle,
target repository, immutable evaluator reference, and scoped broker access.

### 5.3 Trust zones

The system has three trust zones:

1. **Control:** scheduler, archive, task registry, broker, secrets, receipts.
2. **Mutation:** creates candidate patches but cannot change control surfaces.
3. **Evaluation:** executes untrusted candidate and target code with no secrets.

No candidate process may cross from mutation or evaluation into control.

## 6. Operating Modes

Every campaign MUST declare one mode.

### 6.1 `explore_open`

Purpose: maximize discovery and archive diversity.

- Candidate token and dollar caps MAY be null.
- Exceeding a soft estimate MUST NOT mark a candidate invalid.
- Every functional candidate is archived, including low-scoring candidates.
- Compute, latency, task count, and provider usage are descriptive dimensions.
- Search logs may be given to a future parent.
- No positive capability claim may originate from this mode alone.

### 6.2 `race`

Purpose: allocate evaluation compute adaptively.

- Candidate bundles are frozen; race does not mutate them.
- All candidates run a cheap functional gate.
- Promising, novel, or uncertain candidates receive larger task panels and
  repetitions.
- Promotion rules MUST be fixed in the campaign manifest before evaluation.
- Candidates that are not promoted remain archived with a provisional score.
- Parent and child MUST be evaluated on the same paired tasks at each race
  stage.

### 6.3 `confirm`

Purpose: estimate whether a discovered agent generalizes.

- The runner and candidate MUST be clean, immutable, and content-addressed.
- The taskpack MUST be sealed from mutation and search logs.
- Candidate, parent, and baseline MUST receive paired tasks.
- Results MUST include performance at multiple compute levels or a documented
  matched-compute comparison.
- Stochastic agents MUST receive repeated seeds or a documented uncertainty
  estimate.
- At least one cross-model or cross-domain transfer evaluation is required for
  a generalization claim.
- Entry into confirm requires an explicit operator command and preregistration;
  it is never an automatic transition from explore or race.

## 7. Compute and Cost Doctrine

### 7.1 Open compute

`budget_cap_tokens` and `budget_cap_usd` MUST accept `null`. In
`explore_open`, null is the expected default until the operator chooses a
campaign allocation.

The following are not validity failures:

- exceeding a historical or estimated token count;
- unknown model pricing;
- a subscription-backed route without per-token billing;
- a high-compute candidate that outperforms a low-compute candidate.

### 7.2 Usage ledger

Every model request MUST record, when available:

- campaign, candidate, task, stage, role, provider, route, and exact model ID;
- request ID and idempotency key;
- input, output, reasoning, cached, and total tokens;
- retries and failure class;
- start, end, latency, and timeout;
- provider-reported cost, if available;
- pricing-table version and computed cost, if known;
- billing mode: `api`, `subscription`, `local`, `free`, or `unknown`.

Mutation, execution, critique, verification, aggregation, and retry usage MUST
all be included. Campaign totals are lower bounds if any request lacks usage,
and the receipt MUST say so.

### 7.3 Retroactive pricing

Raw usage is primary. Pricing is a versioned projection.

- Missing price MUST be `null`, never silently zero.
- A later price table MAY recompute campaign cost without changing raw receipts.
- Subscription routes SHOULD report requests, wall time, and quota signals even
  when dollar cost is unavailable.

### 7.4 Operational fuses

Every live campaign MUST have operational fuses independent of candidate
validity. At minimum:

- maximum concurrent provider requests;
- maximum concurrent workers;
- provider-error backoff and circuit breaker;
- worker heartbeat timeout;
- disk and memory floor;
- operator stop and pause;
- maximum repeated infrastructure failures.

Dollar, token, request, and wall-clock fuses MAY be set by the operator. A fuse
trip stops or pauses the campaign and emits `fuse_tripped`; it does not rewrite
completed candidate results as invalid.

## 8. AgentBundle Candidate Contract

### 8.1 Layout

A candidate bundle SHOULD use:

```text
agent_bundle/
  bundle.yaml
  prompts/
  tools/
  workflow/
  tests/
```

`bundle.yaml` declares the bundle API version, entry point, supported tools,
default model roles, declared capabilities, and required runtime permissions.
It MUST declare two callable entry points:

- `solve(request) -> result` for downstream coding tasks;
- `self_improve(improvement_request) -> patch_or_bundle` for producing a child.

### 8.2 Mutable surface

A candidate MAY modify only its bundle:

- prompt and instruction policy;
- tool definitions and code-editing operations;
- context search, summarization, and window management;
- attempt, critique, peer-review, and patch-selection workflows;
- model-role selection from the broker-provided allowlist;
- retry and verification strategies;
- the bundle's own future `self_improve` implementation;
- bundle-local tests.

### 8.3 Immutable surface

A candidate MUST NOT modify or influence:

- campaign scheduler or parent-selection code;
- archive, lineage, or receipt writers;
- provider broker, credentials, or liveness oracle;
- task split, sealed holdout, scorer, expected patches, or hidden tests;
- containment policy or worker launcher;
- host services, production checkout, or global daemon state;
- this specification or its activation checks.

The immutable surface MUST be mounted read-only or absent from the candidate
container. A prompt prohibition alone is insufficient.

### 8.4 Identity

`candidate_id` MUST include:

- canonical AgentBundle tree digest;
- AgentBundle API version;
- immutable base-agent identity.

Evaluation identity is separate and MUST include:

- candidate ID;
- evaluator and taskpack digest;
- execution model and route;
- seed and stage;
- worker image digest;
- evaluation-policy version.

The same bundle MAY be reevaluated when any evaluation-identity field changes.

### 8.5 Self-improvement step

A self-improvement step has two explicit phases:

1. **Diagnose:** the selected parent reads only permitted search receipts and
   proposes one focused improvement hypothesis.
2. **Implement:** the parent edits its own AgentBundle to implement that
   hypothesis.

Every non-seed child MUST be created by loading the selected parent bundle and
executing that parent's `self_improve` entry point. The outer harness may
validate and apply the returned patch or bundle, but MUST NOT silently repair,
rewrite, or replace it. A fixed external mutator is a control treatment, not a
self-editing candidate.

The resulting patch, hypothesis, parent ID, mutation model, raw usage, and test
result MUST be recorded before evaluation begins.

The mutation receipt MUST bind `selected_parent_bundle_hash`,
`self_editor_bundle_hash`, `child_bundle_hash`, and `mutation_diff_hash`.
Genuine self-editing requires the selected parent and self-editor hashes to
match.

## 9. Archive and Search

### 9.1 Admission

A child is selectable only after it:

- parses and loads as an AgentBundle;
- compiles;
- passes bundle unit tests;
- retains basic repository read/edit/test capability;
- stays within the mutable surface;
- produces complete lineage and provenance receipts.

Nonfunctional and policy-blocked children remain append-only evidence but are
not selectable parents.

### 9.2 Stepping stones

Every functional non-perfect candidate MUST have nonzero parent-selection
probability. Zero score MUST NOT make a functional lineage permanently
unreachable.

Parent selection MUST:

- use only functional children in the child-count novelty penalty;
- distinguish provisional search score from sealed confirmation score;
- version its formula and parameters in the campaign manifest;
- retain behaviorally novel or underexplored lineages;
- never treat compute-limit metadata as technical invalidity.

### 9.3 Archive contents

Every functional archive row MUST include:

- candidate and parent identity;
- complete AgentBundle patch and tree digest;
- mutation hypothesis and model route;
- functional-gate results;
- evaluation receipts by stage;
- raw usage summary and price status;
- behavior descriptors and functional-child count;
- container, runner, evaluator, and taskpack digests;
- timestamps and closeout state.

## 10. Task and Evaluation Protocol

### 10.1 Required panels

Each benchmark family MUST define:

1. **Capability gate:** cheap tasks proving the agent can edit and test code.
2. **Paired anchor panel:** fixed search tasks for parent-child comparability.
3. **Rotating search panel:** stratified tasks for breadth and overfit pressure.
4. **Sealed confirmation panel:** hidden from mutation and search logs.
5. **Transfer panel:** unseen model, repository, language, or task domain.

Tasks are grouped into comparison blocks. Candidate, parent, and control within
a block MUST receive identical task IDs, repository revisions, scorer digest,
model-access contract, and resource contract. Rotation occurs only between
blocks. The parent and controls MUST be reevaluated on every new cohort.

Raw pass rates from different task cohorts MUST NOT be directly ranked. Search
and promotion use paired deltas or a preregistered cohort-normalized statistic.

### 10.2 Bootstrap profile

The existing 29 fresh tasks MAY bootstrap v0.1 as:

- 3 capability-gate tasks;
- 7 paired/rotating search tasks;
- 19 sealed confirmation tasks.

This split MUST be created once, content-addressed, and kept sealed. It is a
bootstrap profile, not a sufficient final benchmark.

### 10.3 Target benchmark ladder

The task registry SHOULD grow in this order:

1. current verified fresh-PR tasks;
2. official SWE-bench Verified Mini tasks;
3. Polyglot or equivalent multi-language repair tasks;
4. Terminal-Bench-compatible tool and environment tasks;
5. newly harvested post-cutoff PR reconstruction tasks;
6. full official SWE-bench confirmation on native x86 capacity.

Official harnesses and hidden tests MUST be used when available. Target
repositories and dependency environments MUST be pinned.

### 10.4 Successive promotion

Promotion SHOULD follow:

- capability gate for every child;
- paired anchor plus rotating search for functional children;
- larger search panel for candidates that are promising, novel, or uncertain;
- sealed confirmation for the top candidates and their parent/baseline;
- transfer evaluation for confirmed candidates.

Promotion thresholds and uncertainty rules MUST be declared before a campaign.

### 10.5 Causal controls

The first credible self-improvement campaign MUST include:

- fixed mutator plus archive, with no recursive self-editing;
- self-editing but latest-functional-only, with no open archive selection;
- self-editing AgentBundle plus open archive;
- unchanged initial-agent baseline.

All controls use the same task panels and declared compute treatment. A gain may
be attributed to self-improvement or open-ended search only when the relevant
control loses.

### 10.6 Metrics

Required metrics include:

- absolute best task success;
- paired child-minus-parent delta;
- improvement over the initial agent;
- performance-versus-compute frontier;
- functional-child rate;
- mutation-to-improvement yield;
- archive diversity and lineage depth;
- sealed-confirmation delta and uncertainty;
- cross-model and cross-domain transfer;
- contamination, evaluator-error, and infrastructure-error rates.

## 11. Provider and Model Fabric

### 11.1 Canonical catalog

Forge MUST consume the repository's canonical `model_pool`, provider defaults,
runtime provider factory, and key oracle. It MUST NOT maintain a Kimi-only or
Forge-only model catalog.

Moonshot routing MUST become a first-class canonical route rather than an
untracked prefix patch. `moonshot` and `kimi_code` are distinct provider
entitlements and MUST have separate liveness receipts.

### 11.2 Meghadharma parity requirement

Meghadharma MUST support the same intended provider/model capabilities as the
M5, subject to provider licensing and machine-specific authentication.

Parity means:

- identical catalog and aliases;
- a host-specific availability record for every route;
- independently verified API-key routes;
- independently verified CLI subscription routes;
- explicit unavailable reasons rather than silent pruning;
- the same role names and routing semantics.

API keys MAY be securely synchronized. CLI subscriptions such as Codex or
Claude Code MUST be authenticated on Meghadharma through a provider-supported
login or credential mechanism; binary presence or copied metadata is not proof
of dispatchability.

### 11.3 Capability classes and credential reconciliation

Provider parity MUST classify capability rather than treating every Mac seat as
an API key:

- **Portable API credentials:** canonical provider API keys and public base-URL
  overrides that are already supported by the runtime.
- **Catalog labels:** model-family or `dkeys` labels that still need an
  independently wired provider route.
- **Machine-bound CLI subscriptions:** Codex and Claude Code, authenticated and
  tested separately on every host.
- **Cloud or desktop seats:** Devin, Perplexity, Copilot, Cursor, and similar
  products, integrated only through an officially supported remote or API
  surface.
- **Local-compute capability:** Apple Silicon, MLX, or local Ollama capacity,
  which is a worker capability and is not expected to be reproduced on a
  2-vCPU VPS without an accelerator.

Historical entitlement evidence is inventory input, not current liveness. A
subscription name MUST NOT be converted into an API route unless an actual
supported credential and successful dispatch receipt exist.

Meghadharma SHOULD use one canonical host provider store, initially
`/root/.dharma/agent_keys.env`, owned by root and mode `0600`. Production and
RSI processes should load this store rather than maintaining divergent copies.

API-key synchronization from the M5 MUST:

- use a strict-host-verified Tailscale SSH path;
- transfer only the canonical provider key and public base-URL allowlist;
- never copy the whole Mac environment, Keychain, browser state, OAuth cache,
  NATS credentials, or unrelated service secrets;
- avoid secret values in command arguments, logs, receipts, and shell history;
- stage to a mode-`0600` temporary file, validate assignment names only, merge
  any Meghadharma-only route through a structured parser, then rename
  atomically;
- restart or reload consumers whose environment was captured before promotion;
- finish with independent provider self-tests.

Codex and Claude credential files MUST NOT be copied from the M5. They MUST use
provider-supported login on Meghadharma and receive separate headless dispatch
receipts.

### 11.4 Provider self-test

The canonical command is:

```bash
rsi provider selftest --profile staged
rsi provider selftest --profile staged --live
```

Offline mode MUST:

- make no provider calls;
- validate secret-name presence without printing values;
- validate receipt schema and TTL;
- require one distinct receipt per provider type;
- verify catalog, default, resolver, factory, Forge route, and matrix coverage;
- list every unavailable route and reason;
- exit nonzero when the selected profile has zero targets.

Live mode MUST:

- require explicit operator invocation;
- run one bounded, standardized capability probe per selected route;
- avoid hidden retries, repair calls, or a separate implicit smoke suite;
- record auth, routing, exact model, latency, schema compliance, and usage;
- exit nonzero on any selected-lane failure;
- never print credentials or full provider responses containing secrets.

The staged profile MUST initially contain only independently proven routes.

### 11.5 Model roles

Campaigns distinguish:

- mutation model;
- execution model;
- critic or verifier model;
- optional ranking model;
- deterministic test evaluator.

Using one provider for multiple roles is allowed in exploration and MUST be
recorded. Confirmation SHOULD include a cross-provider critic or transfer run.
Deterministic tests, not an LLM opinion, remain the primary correctness oracle
for coding tasks.

Every comparison block declares one model-access mode:

- **`fixed_route`:** provider, model, parameters, tool contract, and retry policy
  are fixed. This mode is required for causal agent-design and cross-model
  transfer comparisons.
- **`evolvable_pool`:** every candidate receives the same provider/model
  allowlist and aggregate resource lease, but its AgentBundle may choose routes
  within that pool. Actual route choice is part of the phenotype, and any gain
  is labeled routing/orchestration gain rather than fixed-model agent-design
  gain.

Provider fallback MAY be retained as a separately labeled route stratum in
exploration. Race and confirm MUST disable implicit fallback. An unauthorized
route, model, tool, sampling, or retry-policy mismatch inside a comparison
block invalidates that block as a comparison; it is not scored as a candidate
task failure. An intentional route choice inside an `evolvable_pool` allowlist
is not fallback.

## 12. Model Broker and Secret Boundary

Only the model broker may hold provider credentials.

The broker MUST:

- resolve canonical provider and model routes;
- enforce the campaign allowlist and provider limits;
- attach request identity and usage receipts;
- normalize failure classes without fabricating success;
- expose no raw secret to mutation or evaluation workers;
- support local, API, and headless CLI-backed routes;
- provide cancellation and timeout semantics;
- support price-unknown operation.

Candidate containers receive only a scoped broker endpoint or socket. The
broker MUST reject requests lacking campaign, candidate, task, stage, and role
identity.

## 13. Containment

All candidate and target code is untrusted.

Evaluation MUST run with:

- non-root user;
- read-only base filesystem and immutable evaluator mount;
- writable scratch space limited to candidate and target work directories;
- scrubbed environment with no provider, SSH, cloud, or production secrets;
- no host Docker socket;
- CPU, memory, process, disk, and wall-time limits;
- network disabled or restricted only to the scoped model broker;
- explicit cleanup of containers, worktrees, and temp data;
- captured stdout, stderr, exit status, and resource usage.

`container_or_equivalent_sandbox=true` may be emitted only after the launcher
proves these controls. A host subprocess is not equivalent containment.

## 14. Campaign Lifecycle

### 14.1 Campaign states

```text
CREATED -> PREFLIGHT -> READY -> RUNNING -> PAUSING -> PAUSED
                                  |            |
                                  |            +-> INTERRUPTED
                                  +-> CLOSING -> COMPLETED
                                  +-> FAILED
                                  +-> FUSE_TRIPPED
```

Every transition MUST be append-only, timestamped, and idempotent.

Only one spend-bearing campaign may hold the default Meghadharma manager lease
at a time. Source update and control-plane deployment MUST refuse while that
lease is active unless the campaign is first paused and forked under a new
manifest.

### 14.2 Candidate and task states

Candidate states:

```text
PROPOSED -> PATCHED -> FUNCTIONAL_GATE -> SELECTABLE -> EVALUATING
         -> NONFUNCTIONAL             -> POLICY_BLOCKED
EVALUATING -> PROVISIONAL -> CONFIRMED -> ARCHIVED
           -> EVALUATION_ERROR -> INTERRUPTED
```

Task attempts MUST distinguish `queued`, `running`, `succeeded`, `failed`,
`timed_out`, `cancelled`, and `unknown_after_interruption`.

### 14.3 Checkpointing and resume

The controller MUST checkpoint:

- before and after every provider request;
- after mutation patch creation;
- after the functional gate;
- after every task attempt;
- after each promotion decision;
- before and after closeout cleanup.

Resume MUST skip completed idempotent work. An in-flight provider request whose
outcome cannot be recovered becomes `unknown_after_interruption`; it is never
silently retried without a new request ID and receipt.

An ambiguous provider call counts as usage and invalidates its paired
comparison block. It does not become a candidate failure.

Resume MUST verify runner, wrapper, image, taskpack, evaluator, provider
contract, and selection-policy digests. Drift blocks continuation. The operator
may create a new provenance-linked campaign fork; the old campaign is not
silently resumed under changed code.

### 14.4 Stop semantics

`rsi stop` MUST:

1. write an operator cancellation request;
2. stop scheduling new work;
3. cancel or allow a configured grace period for in-flight work;
4. checkpoint completed results;
5. close provider sessions and worker process groups;
6. finalize allocations and leases;
7. clean scratch artifacts according to retention policy;
8. emit an interrupted closeout;
9. confirm that no worker remains.

Sending Ctrl-C to a tmux pane is not a complete stop protocol.

### 14.5 Continuous operation

Continuous search is implemented as a resumable campaign, not a generated
`while true` shell script. It MAY run until operator stop. It MUST remain
observable, checkpointed, restartable, and subject to operational fuses.

## 15. Provenance and Reproducibility

### 15.1 Versioned control plane

All operator scripts currently under `/root/rsi-lab/bin` MUST move into a
versioned source tree. Installed `rsi-*` commands may be thin wrappers, but each
must report its source commit and package version.

### 15.2 Run manifest

Every campaign manifest MUST include:

- Forge package version and source commit/tree digest;
- dirty patch digest and archived patch, if exploration permits dirty code;
- AgentBundle API and initial bundle digest;
- task registry, taskpack, evaluator, and split-policy digests;
- worker image and dependency lock digests;
- provider catalog and host-profile digest;
- model routes, roles, prompts, sampling parameters, and seeds;
- operating mode, selection formula, promotion policy, and fuses;
- usage and pricing schema versions;
- canonical host and worker identities;
- manager/operator lease identity.

Confirmation MUST refuse a dirty runner. Exploration MAY use a dirty runner only
when the complete patch is archived and hashed.

### 15.3 Immutable artifacts

Run manifests, candidate patches, evaluation receipts, taskpack manifests, and
closeouts MUST be content-addressed. Corrections append superseding receipts;
they do not edit historical evidence in place.

## 16. State, Backup, and Reconciliation

Campaign state MUST use transactional storage with an append-only event stream.
Allocation records MUST have leases and terminal states; `allocated` is not a
permanent terminal status.

Before continuous campaigns, the archive backup path MUST be healthy and a
restore drill MUST succeed. A backup process that is restarting or has no
replica target is not healthy.

`rsi reconcile` MUST provide a dry run that reports:

- orphan workers and process groups;
- expired allocations and leases;
- campaigns without closeouts;
- unregistered worktrees and containers;
- missing or corrupt artifacts;
- broker requests without terminal receipts;
- local state not present in the replica.

Destructive cleanup requires a second explicit command or operator confirmation.

## 17. Operator Control Surface

The v0.1 command family is:

```bash
rsi doctor
rsi provider selftest --profile staged [--live]
rsi taskpack build --profile bootstrap
rsi campaign plan --profile explore-open
rsi campaign run --profile explore-open
rsi campaign status [CAMPAIGN]
rsi campaign progress [CAMPAIGN]
rsi campaign pause CAMPAIGN
rsi campaign resume CAMPAIGN
rsi campaign stop CAMPAIGN
rsi reconcile [--apply]
rsi archive inspect [CANDIDATE]
```

Requirements:

- `plan` performs no provider calls and writes an exact manifest preview.
- `run` prints the campaign ID, state path, fuses, providers, taskpack, and
  expected worker profile before launch.
- `status` shows provider readiness, active requests, tasks, compute, price
  completeness, worker health, archive progress, and backup health.
- `progress` reports per-candidate and per-task results without relying on
  buffered stdout.
- commands exit nonzero for zero targets, missing preconditions, failed stop,
  or ambiguous lifecycle state.

Legacy `rsi-run`, `rsi-loop`, `rsi-status`, and `rsi-stop` may temporarily call
the new CLI but MUST be marked deprecated after parity is reached.

## 18. Observability

The live view MUST expose:

- campaign state and last checkpoint;
- active candidates, tasks, workers, and provider calls;
- raw usage by provider, model, role, candidate, and stage;
- known cost, unknown-cost fraction, and pricing version;
- absolute best score and compute frontier;
- parent-child deltas and archive diversity;
- promotion decisions and reasons;
- error, timeout, empty-patch, nonfunctional, and contamination rates;
- backup, disk, memory, and worker health;
- operator actions and fuse events.

A green process heartbeat MUST NOT conceal zero completed tasks, missing
telemetry, a broken replica, or zero provider targets.

## 19. Result and Claim States

Technical closeout states:

- `completed`;
- `operator_stopped`;
- `interrupted_recoverable`;
- `infrastructure_failed`;
- `fuse_tripped`;
- `contaminated_quarantine`;
- `blocked_with_evidence`.

Research interpretation states:

- `configuration_search_signal`;
- `self_edit_search_signal`;
- `paired_search_lift`;
- `sealed_confirm_candidate`;
- `measured_negative`;
- `inconclusive`.

The terms `DGM` or `recursive self-improvement` apply only after an executable
self-editing AgentBundle campaign includes the causal controls in section 10.5.
A public capability claim requires sealed confirmation, reproducible artifacts,
and an explicit operator decision outside this specification.

## 20. Schema Requirements

v0.1 MUST version at least these schemas:

- `forge_lab.campaign_manifest.v1`;
- `forge_lab.agent_bundle.v1`;
- `forge_lab.candidate.v1`;
- `forge_lab.model_request_receipt.v1`;
- `forge_lab.task_attempt.v1`;
- `forge_lab.promotion_decision.v1`;
- `forge_lab.campaign_event.v1`;
- `forge_lab.closeout.v1`;
- `forge_lab.provider_liveness.v1`;
- `forge_lab.worker_capability.v1`.

Schema parsers MUST reject ambiguous legacy shapes at write time and provide
explicit read-only migration adapters for historical v0 artifacts.

## 21. Normative Invariants

- **I-01 Canonical control:** Meghadharma is the sole campaign, archive,
  provider-broker, and receipt authority even when execution workers are remote.
- **I-02 Authenticity:** every non-seed self-edit child is emitted by the
  selected parent bundle's own `self_improve` code.
- **I-03 Mutable boundary:** candidate writes are confined to the copied bundle
  root and task scratch space.
- **I-04 Immutable core:** candidate code cannot read or modify evaluator
  internals, task allocation, broker policy, fuses, archive selection, receipts,
  secrets, specification, or production source.
- **I-05 Identity:** candidate identity is the canonical bundle hash; lineage
  binds parent, executing self-editor, child, and diff hashes.
- **I-06 Admission:** only functional, policy-valid candidates are selectable;
  all rejected children remain evidence-only.
- **I-07 Stepping stones:** every eligible non-perfect parent retains nonzero
  selection probability, and novelty pressure counts only functional children.
- **I-08 Mode authority:** explore, race, and confirm mutation, task, and claim
  permissions cannot bleed into one another.
- **I-09 Pairing:** comparisons use identical tasks, model-access mode,
  allowlist or fixed route, tools, evaluator, and resource contracts within a
  comparison block.
- **I-10 Rotation:** tasks rotate only between comparison blocks; parent and
  controls are rerun on the new cohort.
- **I-11 Comparability:** raw scores from different cohorts or effective routes
  are never directly ranked.
- **I-12 Sealing:** confirm tasks and evaluator details remain inaccessible to
  mutation and prior search, and confirm feedback is not reused for mutation.
- **I-13 Canonical routing:** provider and model truth comes from canonical
  repository owners; the lab broker cannot maintain divergent defaults.
- **I-14 Fallback:** route drift in race or confirm invalidates the comparison
  block and cannot count as candidate failure.
- **I-15 Secret custody:** only the broker has provider secrets; workers and
  graders never receive them.
- **I-16 Compute separation:** adaptive research allocation and the operational
  emergency fuse remain separate contracts.
- **I-17 Complete accounting:** mutation, execution, critique, verification,
  retries, failures, and ambiguous provider calls are counted.
- **I-18 Containment:** every untrusted execution is resource-limited,
  ephemeral, non-root, and denied host access except its scoped broker channel.
- **I-19 Idempotency:** side effects have write-ahead identities; resume cannot
  duplicate known calls, allocations, archive rows, or completed tasks.
- **I-20 Drift refusal:** changed code, image, task, evaluator, routing, or
  selection digests block resume and require a provenance-linked fork.
- **I-21 Cleanup:** every stop or terminal path revokes broker leases and
  reconciles workers, process groups, mounts, worktrees, allocations, and locks.
- **I-22 Evidence:** no terminal campaign lacks a closeout, raw usage ledger,
  version packet, and verification result.
- **I-23 No automatic promotion:** no lab result mutates production, governed
  fitness, routing, or external state without a separate operator protocol.
- **I-24 Fail closed:** missing identity, pairing, sealing, usage, containment,
  provenance, or lifecycle evidence is invalid evidence, never best-effort
  green.

## 22. Build Packets

### Packet A: canonicalize and version

- choose and document the single canonical lab checkout;
- move the RSI control scripts into version control;
- align the manager registration with the canonical checkout;
- add package and CLI version reporting;
- bump to `0.1.0-dev` only when the new CLI skeleton exists.

### Packet B: provider parity and broker

- make Moonshot a canonical first-class route;
- repair provider-oracle identities and receipt schemas;
- implement offline and explicit-live provider self-test;
- reconcile M5 API and CLI capability inventory with Meghadharma;
- implement broker identity, usage receipts, and secret isolation.

### Packet C: lifecycle and accounting

- implement campaign/candidate/task state machines;
- add idempotent checkpoints, pause, resume, and stop;
- implement complete raw usage accounting and nullable pricing;
- add allocation leases, terminal states, and reconciliation;
- replace tmux-only lifecycle authority.

### Packet D: containment and workers

- build the untrusted evaluation image and launcher;
- enforce immutable evaluator and scrubbed environment;
- add resource/network limits and broker-only access;
- implement worker registration and capability receipts;
- prove no candidate can read a provider secret or host Docker socket.

### Packet E: task protocol

- create content-addressed bootstrap splits for the 29 tasks;
- implement paired anchors, rotating search, sealed confirm, and transfer panels;
- add successive-promotion receipts and coverage accounting;
- integrate at least one official SWE-bench Verified instance end to end;
- define benchmark harvest and contamination policy.

### Packet F: genuine AgentBundle self-editing

- define bundle API, loader, identity, and mutable boundary;
- implement diagnose-then-implement mutation;
- archive complete bundle patches and functional-child lineage;
- fix stepping-stone parent selection and provisional scoring;
- add the no-self-edit and no-archive causal controls.

### Packet G: bootstrap campaign and release

- run provider preflight and backup restore drill;
- run a bounded bootstrap campaign through stop/resume/reconcile;
- run the three causal controls on paired tasks;
- confirm at least one candidate on the sealed bootstrap panel;
- publish an internal closeout with raw usage and all artifact digests;
- tag `forge-lab-v0.1.0` only when the acceptance criteria pass.

## 23. Acceptance Criteria

Forge Lab v0.1 is complete only when all of the following are demonstrated.

### 23.1 Compute semantics

- A candidate using more than 90,000 tokens remains technically valid when its
  evaluation is otherwise valid.
- Mutation and all downstream model usage appear in campaign totals.
- Unknown pricing is represented as null with a visible completeness measure.
- A fuse trip pauses or closes the campaign without invalidating prior results.

### 23.2 Provider parity

- Offline self-test lists every catalog route and exact availability reason.
- Zero selected targets returns nonzero.
- Moonshot and Kimi Code cannot share one liveness receipt.
- Every staged route passes an independent headless live probe on Meghadharma.
- At least two independently verified model routes are usable before
  cross-provider confirmation is claimed.

### 23.3 Lifecycle

- SIGINT, SIGTERM, provider timeout, worker crash, and host restart tests all
  produce recoverable or terminal closeouts.
- Resume performs no duplicate completed task or provider request.
- Stop confirms that no worker or provider request remains.
- Reconcile identifies and safely resolves a deliberately orphaned worktree,
  allocation, and in-flight request.

### 23.4 Containment

- Candidate code cannot read host or broker secrets.
- Candidate code cannot edit evaluator, task answers, archive, or receipts.
- Candidate code cannot access the host Docker socket or production checkout.
- Resource and wall-time limits terminate a hostile test fixture cleanly.
- A descendant test proves generation N+1 executes `self_improve` code changed
  by generation N, with matching selected-parent and self-editor hashes.

### 23.5 Evaluation

- Task coverage proves the allocator is not silently repeating one five-task
  slice across a campaign.
- Parent and child receive identical paired anchor tasks.
- Sealed confirmation logs are never supplied to mutation.
- One candidate, parent, and baseline complete a sealed paired evaluation.
- The causal control runner can compare self-edit/archive, self-edit/latest-only,
  and fixed-mutator/archive treatments.
- An API attempt to rank raw scores from different cohorts is rejected.
- An injected provider fallback invalidates the comparison block without
  lowering candidate fitness.

### 23.6 Provenance and recovery

- A run can be reconstructed from its manifest without the original dirty
  worktree.
- Candidate ID changes when bundle code changes and remains stable otherwise.
- The same candidate can be reevaluated under a different model or taskpack.
- Archive backup restores into a fresh location and passes integrity checks.
- Legacy v0 candidates remain readable as `legacy_config_search` evidence and
  cannot enter a v1 race or confirm without creating a new seed bundle and
  lineage.

## 24. Initial Host Reconciliation

As of ratification:

- Meghadharma is online and remains the canonical host.
- The canonical catalog code exposes many model routes, but only the Moonshot
  `kimi-k2.7-code` route has independent live evidence in the RSI state.
- Claude Code is installed but not logged in for headless dispatch.
- Codex is installed and reports a ChatGPT login, but still needs an explicit
  headless dispatch receipt for the selected model.
- Kimi Code is not independently proven by the Moonshot key.
- The M5 is visible on the tailnet as `johns-macbook-pro` (`100.74.45.73`) and
  exposes SSH, but the Meghadharma SSH key is not yet authorized for the likely
  Mac user.

The first provider-parity implementation step is therefore to authorize a
restricted Meghadharma-to-M5 audit/sync path or perform the inventory locally on
the M5, then authenticate supported CLI subscriptions directly on Meghadharma.
This is credential reconciliation, not a change of canonical host.

## 25. Primary References

- Darwin Goedel Machine paper: <https://arxiv.org/abs/2505.22954>
- Sakana DGM project page: <https://sakana.ai/dgm/>
- Paper-linked DGM implementation: <https://github.com/jennyzzt/dgm>
- Local official SWE-bench runbook: `docs/RUNPOD_SWEBENCH_RUNBOOK.md`
- Provider matrix contract: `docs/architecture/PROVIDER_MATRIX_HARNESS.md`
- Existing Forge research goal:
  `docs/agent_tasks/2026-06-12_forge_rehydration_benchmark_evolution_goal.md`
