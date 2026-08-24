# Forge Lab v0.1 Target Protocol: Open-Compute Agent Evolution

**Status:** operator-ratified target contract; implementation and DGM evidence
are not yet complete

**Target release:** `dharma_swarm.forge_lab` `0.1.0`

**Current release:** `0.1.0-dev` (bounded operator-control slice; live campaign,
promotion, and persistent-supervisor paths remain fail-closed)

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

### 1.1 Authority and precedence

This protocol is subordinate to the current operator instruction within the
higher-level behavioral rules and to every applicable repository authority
below. Those authorities own different truth domains; this protocol does not
order them against one another. Forge MUST satisfy their intersection. If two
owners appear to conflict, Forge MUST fail closed, emit a blocked
operator-action receipt, and obtain an owner decision rather than using one
domain to override another:

- `CLAUDE.md` for repository behavioral rules;
- `docs/governance/SOVEREIGN_MANIFEST.md`, including the telos hierarchy, plus
  the ownership rules in `docs/governance/CANONICAL_DOC_STACK.md` and
  `docs/governance/ACTIVE_TRACK.yaml`;
- the One Wire external-receipt quorum and production-fitness authority in
  `docs/architecture/EXTERNAL_GRADIENT_PORTFOLIO_SPEC.md` and its canonical
  archive enforcement path;
- the Runtime Truth Spine and `RuntimeStateStore` proof types named in
  `docs/governance/RUNTIME_TRUTH_COMMAND_CUTOVER.md`; and
- repository secret, provider-routing, and env-name-only governance, including
  `docs/architecture/MODEL_ROUTING_CANON.md`,
  `docs/architecture/PROVIDER_MATRIX_HARNESS.md`, and the active secret
  leakage gates.

Forge research receipts may guide selection inside the isolated lab archive.
They MUST NOT mint production fitness, unlock standing self-modification, or
bypass the One Wire quorum. Forge lifecycle schemas SHOULD reuse or adapt the
Runtime Truth Spine's `ExecutionIdentity`, `RuntimeWarrant`, `EvidenceReceipt`,
`RuntimeReceipt`, and idempotency records; they MUST NOT create a competing
repository-wide receipt authority.

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

The canonical Forge source checkout is `/root/rsi-lab/current/repo`; canonical
state, environment, and dependency roots are `/root/rsi-lab/current/state`,
`/root/rsi-lab/current/.venv`, and `/root/rsi-lab/current/pydeps`. New v0.1
commands MUST report and use those roots. `/root/rsi-lab/current-main/repo` is a
deprecated recovery worktree and MUST NOT launch a new campaign. It may be
removed only after its branch is preserved, its worktree is clean, and no
campaign is active. The `/root/rsi-lab/current` symlink MUST NOT be repointed
through `current-main`, whose state/dependency links already resolve back to
`current` and would form a path loop.

### 5.2 Evaluation workers

Workers MAY be:

- isolated containers on Meghadharma for lightweight tasks;
- the M5 for development and Mac-native or subscription-backed routes;
- ephemeral native-x86 workers for full SWE-bench evaluation;
- later, additional registered workers with the same protocol.

Workers are replaceable compute. They MUST NOT own canonical archive state or
provider credentials. Artifacts and grants are role-specific: mutation workers
receive the parent and permitted receipts plus mutation-scoped broker access;
solve workers receive the candidate, public task, and target plus solve-scoped
broker access; grader workers receive only the frozen solve output and pinned
hidden evaluator with no broker. No one job receives both hidden evaluator
artifacts and model-broker access. Section 13 defines the complete split.

### 5.3 Trust zones

The system has three trust zones:

1. **Control:** scheduler, archive, task registry, broker, secrets, receipts.
2. **Mutation:** creates candidate patches but cannot change control surfaces.
3. **Evaluation:** executes untrusted candidate and target code with no secrets.

No candidate process may cross from mutation or evaluation into control.

## 6. Operating Modes

Every campaign MUST declare one mode.

### 6.1 `explore-open`

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
- Entry into a confirm campaign requires an explicit operator command and
  preregistration; it is never an automatic transition from an `explore-open`
  or race campaign.

## 7. Compute and Cost Doctrine

### 7.1 Open compute

`budget_cap_tokens` and `budget_cap_usd` MUST accept `null`. In
`explore-open`, null is the expected default until the operator chooses a
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
validity and research allocation. Each manifest-pinned fuse policy MUST specify
`fuse_id`, metric and trusted source, threshold, evaluation cadence, scope,
deterministic action, grace interval, broker-revocation scope, acknowledgment
requirement, rearm rule, resume eligibility, watchdog owner, and policy digest.

Every live campaign MUST either pin each of an immutable absolute wall
deadline, atomic model-request ceiling, and provider-token ceiling, or carry a
separate dangerous opt-out for each omitted ceiling. The broker MUST reserve
the declared worst-case requests/tokens before dispatch and settle actual usage
afterward. Each `dangerous_opt_out` is a content-addressed operator action
naming exactly one omitted ceiling, reason, actor, issue time, and expiry. A
blanket opt-out is invalid. Confirm campaigns MUST pin all three ceilings and
MUST NOT opt out.

An opt-out is evaluated wherever the omitted fuse would have been enforced:
the broker checks call/token opt-outs before every reservation, and the external
watchdog checks a wall opt-out at least every five seconds. Expiry closes
dispatch and atomically appends two ordered lifecycle events: `FUSE_TRIPPED`
with expiry evidence, then the manifest-declared fuse-stop action to
`DRAINING`. No grant may occur between or after those events. Extension
requires a new operator action and fuse-policy epoch; an expired receipt is
never treated as an unlimited default.

The minimum deterministic fuse behavior is:

| Fuse | Evaluation | Required action and scope | Rearm/resume rule |
|---|---|---|---|
| absolute wall deadline | external watchdog continuously and at least every 5 seconds | campaign stop, broker/worker revocation, and `DRAINING` | no same-manifest rearm; fork required |
| model request/token ceiling | broker atomically before every dispatch and after settlement | reject the dispatch and pause or stop exactly as pinned | explicit ack plus new fuse epoch; changed ceiling requires fork |
| provider error circuit | after every terminal request and backoff window | revoke/pause the affected route unless policy declares campaign scope | condition-cleared evidence, ack, and rearm |
| concurrency ceiling | scheduler and broker before grant/dispatch | reject excess grant; repeated invariant breach pauses campaign | ack after reconciliation |
| worker heartbeat | no slower than one third of heartbeat TTL | revoke packet/grant and quarantine worker; pause if required capacity is lost | authenticated recovery evidence and operator ack |
| disk or memory floor | external watchdog at the manifest cadence | close dispatch and pause or stop campaign as pinned | metric recovered, reconciliation, and ack |
| repeated infrastructure failure | after every classified failure | pause or stop the declared worker, route, or campaign scope | condition-cleared evidence and ack |
| backup freshness | before spend and at least every RPO quarter | block new provider grants and pause campaign when the newest verified off-host snapshot exceeds RPO | successful backup verification and ack |
| operator pause/stop | event-driven | perform the canonical lifecycle action in section 14 | pause may resume; stop is terminal intent |

An external watchdog MUST run outside the campaign controller's process group,
read the durable fuse policy and heartbeat, and be able to close the scheduling
gate, revoke broker grants, terminate workers, and append a trip even when the
controller hangs. A missing watchdog heartbeat is itself a campaign-scoped
stop fuse. Its manifest-pinned emergency identity has no dispatch or scientific
authority. A successful fuse transaction atomically invalidates the manager
lease, increments the fence into `recovery_only` mode, and performs only the
declared safety transition. If the control store is unavailable, the watchdog
MUST still apply out-of-band revocation/termination and write a signed emergency
observation; that observation cannot mutate scientific state and is reconciled
under a later recovery-only lease.

A trip MUST atomically persist `forge_lab.fuse_trip.v1`, close the declared
dispatch gates, revoke the declared broker/worker authority, and alert. It does
not rewrite completed candidate results as invalid. Acknowledgment appends
`forge_lab.fuse_ack.v1`; it never erases the trip. Rearm creates a new fuse
epoch, and resume is forbidden while a blocking trip is unacknowledged,
unrearmed, or still above threshold.

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

`bundle.yaml` declares the bundle API version, immutable base-agent stable ID
and artifact digest, entry point, supported tools, default model roles,
declared capabilities, and required runtime permissions. It MUST declare two
callable entry points:

- `solve(request) -> result` for downstream coding tasks;
- `self_improve(improvement_request) -> patch_or_bundle` for producing a child.

### 8.2 Mutable surface

During `self_improve`, a candidate MAY persistently modify only its copied
bundle or declared child-output root. During `solve`, it MAY additionally write
only the assigned target worktree and task scratch space. The persistent bundle
surface is:

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

There is one canonical candidate serialization. Implementations MUST construct
`forge_lab.agent_bundle.v1` binary bytes with this exact framing:

1. ASCII bytes `forge_lab.agent_bundle.v1` followed by one NUL byte;
2. `u64be(header_length)` followed by an RFC 8785 canonical JSON header with
   exactly `api_version` and `base_agent`, where `base_agent` has exactly the
   stable `id` and lowercase `sha256:` artifact digest;
3. `u64be(entry_count)`; then
4. for each file in bytewise lexicographic order of its UTF-8 path bytes:
   `u64be(path_length)`, path bytes, one executable byte (`0x00` or `0x01`),
   `u64be(content_length)`, and exact file-content bytes.

`u64be` means an unsigned 64-bit integer in network byte order. Paths MUST be
NFC-normalized UTF-8 POSIX relative paths using `/`, with no empty, `.`, `..`,
absolute, NUL, or backslash component. A producer MUST reject a path whose
supplied spelling changes under NFC, and reject duplicate UTF-8 or Unicode
case-folded paths. Directories are implicit. v0.1 permits regular files only;
symlinks, hard links, devices, sockets, FIFOs, ownership, timestamps, extended
attributes, and permission bits other than executable are rejected. The trusted
loader MUST verify that the header fields exactly match `bundle.yaml` and the
manifest-pinned base artifact.

`candidate_id` is the lowercase string
`sha256:<hex(sha256(exact forge_lab.agent_bundle.v1 bytes))>`. API version and
base-agent identity are therefore part of the one candidate identity. A CAS or
filesystem tree digest MAY be recorded only as transport/integrity metadata and
MUST NOT substitute for or participate in candidate identity or lineage.

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

Every non-seed child in a `self_edit` treatment MUST be created by loading the
selected parent bundle and executing that parent's `self_improve` entry point.
The outer harness may validate and apply the returned patch or bundle, but MUST
NOT silently repair, rewrite, or replace it. The required `fixed_external`
control instead invokes the manifest-pinned external mutator artifact. Its
descendants remain control candidates and MUST NOT be labeled self-editing.

The trusted harness computes `forge_lab.bundle_diff.v1` from the canonical
parent and child, never from a candidate-claimed hash. It is RFC 8785 canonical
JSON binding both candidate IDs and a UTF-8-path-sorted list of changes with
operation (`add`, `delete`, or `modify`), before/after content digest or `null`,
and before/after executable bit or `null`. Referenced file bytes remain in the
archive. `mutation_diff_digest` is the lowercase `sha256:` digest of those
canonical diff bytes.

Before admission begins, the trusted harness MUST write and authenticate a
`forge_lab.mutation_receipt.v1` containing at least:

- execution identity, campaign, generation, mutation-attempt ID, and nonce;
- `treatment_kind`, exactly `self_edit` or `fixed_external`;
- `selected_parent_candidate_id`;
- typed `mutation_operator`: `{kind: candidate, candidate_id, artifact_digest:
  null}` for `self_edit`, or `{kind: runner_artifact, candidate_id: null,
  artifact_digest}` for `fixed_external`;
- `child_candidate_id` and canonical `mutation_diff_digest`, or explicit `null`
  when no child materialized;
- improvement hypothesis, permitted input-receipt digests, immutable handshake
  harness digest, runner digest, and containment-policy digest;
- mutation route, request receipts, complete raw usage, exit status, and
  timestamps; and
- signer identity, signature algorithm, key ID, and signature over the
  canonical receipt bytes.

The signing key belongs to the control plane and MUST be unavailable to the
candidate and workers. For `self_edit`, the selected-parent and mutation
operator candidate IDs MUST match exactly; for `fixed_external`, the operator
artifact digest MUST match the manifest. Every materialized non-seed
candidate archive row MUST reference a mutation receipt whose signature,
content address, campaign, treatment, parent, operator, child, and diff bindings
verify. A missing, candidate-signed, or invalid receipt produces a separate
quarantine evidence record, not a conforming candidate archive row, and is
ineligible for selection. Checking only one example descendant is insufficient.

## 9. Archive and Search

### 9.1 Admission

A child is selectable only after it:

- parses and loads as an AgentBundle;
- compiles;
- completes a trusted, immutable `solve` handshake against a public fixture
  repository and proves basic repository read, edit, and test capability;
- completes a trusted, immutable `self_improve` handshake that produces a
  policy-valid child or patch with verifiable lineage;
- stays within the mutable surface;
- produces complete lineage and provenance receipts; and
- passes the external admission policy and containment checks.

The two handshakes are owned by the control plane, digest-pinned in the
campaign manifest, mounted read-only or kept outside candidate visibility, and
executed through the same containment boundary as live `solve` and
`self_improve` calls. Bundle-local tests MUST run and be recorded, but they are
candidate artifacts and MUST NOT serve as trusted admission tests. The
handshakes MUST independently reject a bundle that replaces, bypasses, or
forges its own tests.

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

Every seed, mutation attempt, materialized child, task attempt, and evidence
record MUST be persisted independently of execution outcome or scientific
verdict. Functional candidate rows MAY enter the selectable index;
nonfunctional, interrupted, and policy-blocked candidate rows remain immutable
evidence. An attempt with missing or invalid mutation authenticity persists as
a quarantine evidence record and MUST NOT be written as a candidate archive
row. Persistence MUST NOT imply validity, confirmation, or parent eligibility.

Every candidate archive row MUST include:

- candidate and parent identity;
- canonical AgentBundle bytes and tree digest and, for every non-seed, the
  complete patch;
- mutation hypothesis and model route;
- functional-gate results;
- evaluation receipts by stage;
- raw usage summary and price status;
- behavior descriptors and functional-child count;
- container, runner, evaluator, and taskpack digests;
- timestamps and closeout state.

Every materialized non-seed candidate archive row also MUST reference an authentic
`forge_lab.mutation_receipt.v1`. Archive verification MUST fail closed when any
referenced blob, receipt, signature, or lineage edge is missing.

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

Meghadharma MUST maintain one canonical **names-only provider inventory**, but
MUST NOT make one plaintext secret file readable by production, general RSI
processes, workers, and Forge. A privileged provisioner MAY read a root-owned
source store. It MUST project the minimum required values into separate
service-identity stores. The Forge broker store MUST be readable only by the
Forge broker OS/service identity; the controller, scheduler, CLI, production
services, candidate containers, graders, and untrusted workers MUST NOT load
it. Production and Forge credentials MUST be independently revocable even when
they originate from the same vendor key.

API-key synchronization from the M5 MUST:

- use a strict-host-verified Tailscale SSH path;
- transfer only the canonical provider key and public base-URL allowlist;
- never copy the whole Mac environment, Keychain, browser state, OAuth cache,
  NATS credentials, or unrelated service secrets;
- avoid secret values in command arguments, logs, receipts, and shell history;
- stage through a broker-owned mode-`0600` descriptor or an OS secret facility,
  validate assignment names only, merge through a structured parser, then
  promote atomically into the Forge-scoped store;
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
rsi provider selftest --profile staged --live --require-independent-routes 2
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
- exit nonzero when successful distinct provider entitlements are fewer than
  `--require-independent-routes`; and
- never print credentials or full provider responses containing secrets.

The versioned v0.1 implementation persists every live observation as an
append-only, collision-proof `rsi_lab.provider_selftest.v2` receipt. Its digest
binds source commit/package/tree state, requested profile/models, route count,
timeout, call ceiling, and alias policy; cached reuse requires the same policy
digest. A provider-declared successor alias is not an exact identity match and
MUST consume a second bounded confirmation probe before it can count callable.

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
  are fixed and enforced by the broker; any other effective route is refused.
  This mode is required for causal agent-design and cross-model transfer
  comparisons. Only this mode may support a fixed-model agent-design claim.
- **`evolvable_pool`:** every candidate receives the same provider/model
  allowlist and identical per-block call, token, concurrency, wall-time, and
  aggregate resource leases, but its AgentBundle may choose routes within that
  pool. Actual route choice is part of the phenotype, and any gain is labeled
  routing/orchestration gain only, never fixed-model agent-design gain.

Provider fallback MAY be retained as a separately labeled route stratum in
exploration. Race and confirm MUST disable implicit fallback. An unauthorized
route, model, tool, sampling, or retry-policy mismatch inside a comparison
block invalidates that block as a comparison; it is not scored as a candidate
task failure. An intentional route choice inside an `evolvable_pool` allowlist
is not fallback.

## 12. Model Broker and Secret Boundary

Only a trusted, Forge-scoped model broker or explicitly enrolled trusted remote
route adapter may hold credentials used by a Forge campaign. Neither component
is candidate code or a general worker.

The broker MUST:

- run under a dedicated identity with a separately revocable secret store;
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

A broker token MUST bind campaign, candidate, task, stage, role, allowed
routes, maximum calls and tokens, issue time, expiry, worker identity, and the
manager fencing token. It MUST be short-lived, single-job or narrower, and
revocable without rotating a provider key. Receipt signing and provider-secret
keys MUST be distinct.

Machine-bound CLI subscriptions on the M5 MAY be exposed through a trusted
remote route adapter. That adapter MUST:

- hold only its machine-bound route credentials under a dedicated service
  identity;
- accept mutually authenticated, signed, expiring broker requests over the
  approved private transport;
- enforce the same route, role, call, token, timeout, idempotency, fencing, and
  revocation contract as the Meghadharma broker;
- return a normalized result plus a signed usage/dispatch receipt without
  returning credential material or session files; and
- be registered and audited as control-plane infrastructure, never as an
  untrusted evaluation worker.

Copying OAuth stores, browser state, Keychain records, cookies, or CLI session
directories between machines is forbidden. A worker that happens to run on the
same machine as a trusted adapter remains a separate identity and cannot read
the adapter's credentials or socket.

## 13. Containment

### 13.1 Execution isolation

All candidate and target code is untrusted.

The full containment contract applies separately to every candidate-controlled
`self_improve` and `solve` invocation, including admission handshakes. Moving
candidate code from evaluation to mutation does not move it into the control
trust zone. Each invocation MUST run with:

- non-root user;
- read-only base filesystem and immutable harness mounts;
- writable scratch space limited to candidate and target work directories;
- scrubbed environment with no provider, SSH, cloud, or production secrets;
- no host Docker socket;
- CPU, memory, process, disk, and wall-time limits;
- network disabled or restricted only to the scoped model broker;
- explicit cleanup of containers, worktrees, and temp data;
- captured stdout, stderr, exit status, and resource usage.

The SWE-bench adapter MUST inspect and receipt, rather than merely request,
network disablement, empty/scrubbed environment, `cap_drop=ALL`, no added
capabilities, read-only root, no-new-privileges, bounded writable mounts, and
exact PID/CPU/memory ceilings. Any false or absent proof field makes the grade
non-comparable and blocks confirmation/promotion use.

`container_or_equivalent_sandbox=true` may be emitted only after the launcher
proves these controls. A host subprocess is not equivalent containment.

Mutation, solve, and grading are distinct jobs:

1. The **mutation container** may read the selected parent bundle, permitted
   search receipts, and an external improvement request. It may call the broker
   only with a mutation-scoped token. It receives no task answer, hidden test,
   sealed panel, archive write credential, or signing key.
2. The **solve container** may read the frozen candidate, public task request,
   and target worktree. It may call the broker only with a solve-scoped token.
   It receives no hidden evaluator, expected patch, grader credential, or
   confirmation result.
3. The **grader container** is a fresh trusted job that receives the frozen
   solve output and hidden evaluator artifacts. It has no model-broker token,
   no general network, and runs no candidate-controlled hook, import, test
   plugin, shell profile, or executable from the solve worktree except through
   the pinned evaluator's explicitly sandboxed test protocol.

Solve and grader filesystem layers, process namespaces, environment, and
broker capabilities MUST be distinct. The grader MUST consume a
content-addressed solve-output bundle rather than reuse the live solve
container. Admission and release tests MUST include adversarial attempts to
read hidden files, smuggle hidden bytes into model prompts or network traffic,
load candidate grader plugins, inspect process environments, and exfiltrate
through broker/error channels. Any such access quarantines the comparison
block and revokes the worker and broker token.

### 13.2 Remote worker enrollment and revocation

The control plane MUST own an operator-approved worker trust root. Enrollment
requires the worker to generate a unique key locally and redeem a one-time,
short-expiry operator-issued enrollment token bound to its expected peer and
capability/image profile. The control plane verifies key possession and writes
a signed `forge_lab.worker_enrollment.v1` receipt. The enrollment token cannot
be reused and MUST NOT grant provider credentials or archive-write authority. A
revocation entry MUST take effect before the next dispatch, heartbeat
acceptance, result upload, or broker call.

Every remote work packet MUST be signed by the control plane and bind packet and
attempt IDs, campaign and task identities, candidate and artifact digests,
runner and containment digests, broker-grant digest, result-upload audience,
manager fencing token, worker identity, random nonce, issue time, and short
expiry. The worker MUST verify the signature, expiry, revocation status, fence,
bound worker identity, and artifact digests before execution. It MUST then
atomically redeem the packet ID/nonce with the control plane and durably record
the redemption in its local boot ledger before running candidate code. Only the
first redemption for the bound worker/boot ID may succeed; control-plane
unavailability, a local duplicate, an expired packet, or a replay is rejected
and recorded without execution.

The scoped broker token MUST expire no later than the work packet and MUST
carry the limits in section 12. Heartbeats MUST be authenticated and include a
monotonic sequence, packet/task identity, running image digest, resource
measurements, and timestamp. Missing or conflicting heartbeats invoke the
declared fuse; an unauthenticated heartbeat never extends a lease.

Results MUST be signed by the enrolled worker and uploaded with a stable
idempotency key and content digest. Reuploading the same key and bytes returns
the original acknowledgment. Reusing a key with different bytes is a security
event: revoke the packet and broker token, quarantine the worker and all
results, including already confirmed results, from the earliest plausible
compromise time or the last operator-established trust checkpoint, whichever is
earlier. Possession of the worker key makes later heartbeats untrusted and
cannot narrow that window. Reenrollment requires a new key, clean capability
attestation, and explicit operator review; quarantined evidence requires
independent reevaluation before selection use.

## 14. Campaign Lifecycle

### 14.1 Canonical campaign transition table

The only campaign states are `CREATED`, `PREFLIGHTING`, `READY`, `RUNNING`,
`PAUSING`, `PAUSED`, `FUSE_TRIPPED`, `DRAINING`, `CLOSING`,
`INTERRUPTED_RECOVERABLE`, `RECOVERING`, `COMPLETED`, and `FAILED`.
`COMPLETED` and `FAILED` are terminal. This table is the sole normative campaign
state machine; diagrams and legacy tmux/process status are projections only.

| Request or durable event | Allowed source | Target | Required durable action before transition acknowledgment |
|---|---|---|---|
| create | no campaign | `CREATED` | reserve campaign ID; persist operator action and exact manifest digest |
| begin preflight | `CREATED` | `PREFLIGHTING` | acquire fenced manager lease, then verify manifest, runner package, host profile, task/evaluator, backup, and fuse policy without implicit provider spend |
| preflight passed | `PREFLIGHTING` | `READY` | persist verifier receipts and runnable artifact locations |
| run | `READY` | `RUNNING` | reverify live lease/fencing token, start watchdog, then enable broker/worker dispatch |
| pause | `RUNNING` | `PAUSING` | persist pause action, close the scheduling gate, and set in-flight grace deadline |
| pause quiesced | `PAUSING` | `PAUSED` | checkpoint settled/ambiguous work, revoke broker tokens, reconcile workers, and release manager lease |
| resume | `PAUSED` | `RECOVERING` | persist `recovery_target=RUNNING`, acquire a recovery-only lease with a newer fence, revoke stale authority, and reconcile from the last checkpoint |
| recover after interruption | `INTERRUPTED_RECOVERABLE` | `RECOVERING` | reverify the recovery-only lease/new fence that recorded the interruption, retain its recovery target, and reconcile; dispatch remains closed |
| recovery passed, target preflight | `RECOVERING` | `PREFLIGHTING` | reverify identity/idempotency, then rerun complete preflight; used for interrupted `PREFLIGHTING` or `READY` |
| recovery passed, target run | `RECOVERING` | `RUNNING` | reverify every pinned digest/idempotency record and start watchdog before reopening dispatch |
| recovery passed, target pause | `RECOVERING` | `PAUSING` | continue quiescence with dispatch closed; used for interrupted `PAUSING` |
| recovery passed, target fuse | `RECOVERING` | `FUSE_TRIPPED` | restore the unacknowledged trip with dispatch closed; acknowledgment is still required |
| recovery passed, target drain | `RECOVERING` | `DRAINING` | continue the preserved stop, failure, or completion intent with dispatch closed |
| recovery passed, target closeout | `RECOVERING` | `CLOSING` | verify the pre-cleanup closeout already exists, then resume cleanup only |
| recoverable crash/interruption | `PREFLIGHTING`, `READY`, `RUNNING`, `PAUSING`, `FUSE_TRIPPED`, `DRAINING`, `CLOSING`, `RECOVERING` | `INTERRUPTED_RECOVERABLE` | watchdog uses emergency authority only to close gates/revoke grants; after old-lease expiry a new recovery-only fence records source state, deterministic recovery target, checkpoint, and unknown effects |
| fuse trip, campaign scope | `CREATED`, `PREFLIGHTING`, `READY`, `RUNNING`, `PAUSING`, `PAUSED`, `RECOVERING` | `FUSE_TRIPPED` | acquire recovery-only authority if lease-free, atomically persist trip/evidence, close dispatch, revoke scoped tokens, and alert |
| fuse action pause | `FUSE_TRIPPED` | `PAUSING` | apply the manifest-declared pause action; acknowledgment alone does not rearm |
| fuse action stop | `FUSE_TRIPPED` | `DRAINING` | apply the manifest-declared stop action and persist grace deadline |
| scoped fuse handled | `RUNNING` | `RUNNING` | quarantine/revoke the affected provider or worker and persist why campaign-wide transition was unnecessary |
| planned work exhausted | `RUNNING` | `DRAINING` | persist completed terminal intent, close scheduling, and settle all work |
| stop | `CREATED`, `PREFLIGHTING`, `READY`, `RUNNING`, `PAUSING`, `PAUSED`, `FUSE_TRIPPED`, `INTERRUPTED_RECOVERABLE`, `RECOVERING` | `DRAINING` | acquire/reverify the fenced lease and atomically restrict it to `terminal_only`, then persist one cancellation action and close scheduling; acquisition failure leaves state unchanged |
| repeated stop | `DRAINING`, `CLOSING`, `COMPLETED`, `FAILED` | unchanged | return original cancellation and current closeout receipts; retry only incomplete idempotent drain/cleanup work |
| drain complete | `DRAINING` | `CLOSING` | settle or mark every call/task, finalize allocations, and persist a pre-cleanup closeout |
| unrecoverable preflight/recovery/runtime failure | `PREFLIGHTING`, `READY`, `RUNNING`, `PAUSING`, `FUSE_TRIPPED`, `INTERRUPTED_RECOVERABLE`, `RECOVERING` | `DRAINING` | close dispatch, persist failure intent, and settle or classify every in-flight effect before closeout |
| successful closeout and cleanup | `CLOSING` | `COMPLETED` | append final closeout/reconciliation receipts, verify no active authority remains, then release lease |
| failed or ambiguous closeout/cleanup | `CLOSING` | `FAILED` | append failure closeout with residual resources and alert; revoke authority before lease release/expiry |

The crash event MUST persist exactly one immutable `recovery_target`: source
`PREFLIGHTING` or `READY` maps to `PREFLIGHTING`; `RUNNING` to `RUNNING`;
`PAUSING` to `PAUSING`; `FUSE_TRIPPED` to `FUSE_TRIPPED`; `DRAINING` to
`DRAINING`; and `CLOSING` to `CLOSING`. A crash during `RECOVERING` retains its
existing target. `CREATED` and `PAUSED` have no active controller/lease to lose
and remain stable until an operator command or external fuse event.

Every request and transition MUST be append-only, timestamped, idempotent by a
stable request/event ID, and bound to execution identity, actor, previous state,
new state, manifest digest, checkpoint, and fencing token when one exists. A
repeated request returns the original receipt. An invalid transition is rejected
without side effects and recorded. Process death alone never means `COMPLETED`
or `FAILED`; reconciliation supplies the durable event.

### 14.2 Fenced manager lease

Every mutating campaign MUST acquire an exclusive manager lease in the
transactional control store before entering `PREFLIGHTING` or performing
recovery, drain, closeout, allocation, archive, or broker mutations. The
manifest pins the lease scope, TTL, renewal interval, and takeover policy, not
a future lease holder or token. Each successful acquisition transaction
increments a monotonic fencing token. The next renewal deadline MUST be no later
than one third of the TTL after acquisition or the previous renewal, and
renewal MUST preserve the token.

Every state mutation, allocation, checkpoint, archive write, worker packet,
broker token, provider request, and closeout MUST carry the current token. The
store, broker, and worker gateways MUST reject a missing or stale token even if
the old process is still alive. A manager that loses renewal immediately closes
dispatch and cannot release or mutate the campaign with stale authority.

Each lease also has an authority mode. `active` permits manifest-authorized
preflight and dispatch. `recovery_only` permits dispatch closure, revocation,
quarantine, checkpoint, interruption/recovery transitions, and reconciliation,
but no spend or scientific verdict. `terminal_only` permits those safety writes
plus allocation settlement, evidence/archive persistence, pause/drain/closeout,
cleanup, and final reconciliation, but no new grant, packet, mutation,
evaluation, promotion, or scientific verdict. Stop atomically restricts any
`active` lease to `terminal_only`. Converting `recovery_only` to
`terminal_only` may add only the named terminal evidence, settlement, and
cleanup writes; it preserves the no-spend, no-dispatch, and no-scientific-
verdict boundary.

After a crash, the control-plane clock MUST first observe TTL expiry. A single
transaction may then acquire a `recovery_only` lease with a strictly greater
token. That lease permits only dispatch closure, revocation, quarantine,
checkpoint, lifecycle-recovery, and reconciliation writes; it cannot issue a
broker grant, worker packet, mutation, evaluation, promotion, or scientific
verdict. Reconciliation uses the new token to revoke or quarantine old grants,
packets, workers, and ambiguous requests. Only a successful reconciliation
receipt may change mode: a target of `PREFLIGHTING` or `RUNNING` promotes to
`active`; a target of `PAUSING`, `FUSE_TRIPPED`, `DRAINING`, or `CLOSING`
changes to `terminal_only`. Failure atomically changes to `terminal_only`, keeps
dispatch closed, and proceeds to `DRAINING`.

A paused campaign releases its lease only after checkpoint, token revocation,
and worker reconciliation. A terminal campaign releases it only after the final
closeout and cleanup receipt is committed. Clean release is conditional on
holder identity and fencing token and MUST NOT release a successor's lease.
Source update or control-plane deployment MUST refuse while an unexpired
mutating lease exists; drift requires a provenance-linked fork.

### 14.3 Candidate, verdict, archive, and task state

Candidate records have three orthogonal fields; implementations MUST NOT encode
them as one sequence:

- `execution_state`: `proposed`, `mutation_running`, `mutated`,
  `admission_running`, `admission_complete`, `evaluating`, `evaluation_complete`,
  `nonfunctional`, `policy_blocked`, `evaluation_error`, or `interrupted`;
- `scientific_verdict`: `unassessed`, `provisional`, `confirmed`,
  `measured_negative`, `inconclusive`, `invalid_evidence`, or
  `contaminated_quarantine`; and
- `archive_state`: `pending`, `persisted`, `verified`, or `quarantined`.

Archive persistence may precede or follow any execution transition and does not
confer selectability or a scientific verdict. Every transition in each axis is
separately receipted. A candidate is eligible for parent selection only when
its execution state, policy/admission receipts, mutation authenticity, and
archive verification all satisfy the versioned selection policy. `selectable`
is a derived, receipted policy decision, never an execution state.

Task attempts MUST distinguish `queued`, `running`, `succeeded`, `failed`,
`timed_out`, `cancelled`, and `unknown_after_interruption`. Task outcome is not
candidate verdict; infrastructure failures and ambiguity remain separate.

### 14.4 Checkpointing, interruption, and resume

The controller MUST write an idempotency claim and checkpoint immediately
before every external side effect and a terminal receipt immediately after it,
including provider calls, mutation output, worker dispatch/result, functional
gate, task attempt, promotion, archive persistence, allocation, and cleanup.
It MUST also checkpoint before and after every lifecycle transition.

Resume MUST skip completed idempotent work. An in-flight provider request whose
outcome cannot be recovered becomes `unknown_after_interruption`; it is never
silently retried without a new request ID and receipt. It counts toward the raw
usage lower bound and invalidates its paired comparison block, not the
candidate. Uncancellable calls remain visible until terminal evidence or the
persisted grace deadline.

Resume MUST verify the content-addressed manifest and executable runner
package/image, wrapper, dependency lock, taskpack, evaluator, provider contract,
selection policy, containment policy, and all referenced artifacts. Any drift
blocks recovery. `rsi campaign fork` may create a provenance-linked campaign
with a new manifest; it MUST NOT rewrite or silently resume the old campaign.

The bounded five-attempt pilot additionally uses a hash chain for lifecycle
events and a separate hash chain for exclusive-create attempt receipts. Its
exclusive-create closeout seals the ordered attempt and event digests. Resume
accepts only a valid prefix of the fixed schedule, including at most one
attempt written immediately before its missing event; every other gap,
duplicate, truncation, extra file, or digest mismatch fails closed.

### 14.5 Crash-safe and idempotent stop

`rsi campaign stop CAMPAIGN` is the only canonical stop command. It MUST:

1. acquire or reverify the exclusive fenced manager lease, leaving state
   unchanged on failure; then, in one transaction, persist an operator action
   with a stable cancellation ID, enter `DRAINING`, and close scheduling before
   signaling or cleanup;
2. revoke new broker/worker authority and request cancellation for calls and
   jobs declared cancellable by their adapters;
3. apply the absolute grace deadline and per-call cancellation policy pinned in
   the manifest; an uncancellable call may run only to that deadline;
4. mark calls without authoritative terminal evidence
   `unknown_after_interruption`, count their known usage as a lower bound, and
   quarantine the affected comparison blocks rather than silently retry them;
5. checkpoint completed evidence, finalize allocations, reconcile workers and
   process groups, and remain in `DRAINING`;
6. commit an append-only closeout with `cleanup_state=pending` and references to
   every known residual **before** deleting containers, worktrees, mounts, or
   scratch data, then enter `CLOSING`;
7. perform idempotent cleanup, verify broker revocation and that no worker,
   request, allocation, or process group retains authority; and
8. append cleanup/reconciliation evidence and a superseding final closeout,
   then enter `COMPLETED` or `FAILED` and release the lease.

Repeating stop with the same or a new CLI invocation returns the original
cancellation and current closeout receipts and safely retries only incomplete
idempotent drain/cleanup steps. It MUST NOT extend the original absolute grace
deadline, change terminal intent, create a second scientific closeout, or erase
evidence. A cleanup or provider ambiguity makes stop exit nonzero and keeps
residuals visible. Sending Ctrl-C to a tmux pane is not a stop protocol.

### 14.6 Continuous operation

Continuous search is a resumable, content-addressed campaign, not a generated
`while true` shell script. It MAY run until operator stop. It MUST remain
observable, checkpointed, restartable, fenced, externally watched, backed up,
and subject to the deterministic operational fuses in section 7.4.

## 15. Provenance and Reproducibility

### 15.1 Versioned control plane

All operator scripts currently under `/root/rsi-lab/bin` MUST move into a
versioned source tree. Installed `rsi-*` commands may be thin wrappers, but each
must report its source commit and package version.

### 15.2 Run manifest

Planning MUST materialize a retrievable executable runner artifact in the
authoritative content-addressed store; a manifest, mutable image tag, or Git
hash alone is not a runnable historical environment. The signed
`forge_lab.runner_artifact.v1` MUST bind:

- OCI image digest or equivalent immutable root environment;
- Forge wheel/package, source tree, complete dirty patch, wrapper, and
  dependency-lock digests;
- entry point, platform/architecture/ABI, evaluator launcher, containment
  profile, and required kernel/runtime features; and
- SBOM, build provenance, artifact locations, and verification procedure.

`run` and `resume` MUST retrieve and execute that artifact and verify every
digest before dispatch. Source, wrapper, lock, platform, or image drift refuses
resume. A provenance-linked fork pins a newly materialized runner and references
the prior campaign and event watermark; it never modifies the old manifest.

Every campaign manifest MUST include:

- Forge package version and source commit/tree digest;
- runner artifact digest and authoritative retrieval locations;
- dirty patch digest and archived patch, if exploration permits dirty code;
- AgentBundle API and initial bundle digest;
- task registry, taskpack, evaluator, and split-policy digests;
- worker image and dependency lock digests;
- provider catalog and host-profile digest;
- model routes, roles, prompts, sampling parameters, and seeds;
- operating mode, selection formula, promotion policy, and fuses;
- usage and pricing schema versions;
- canonical host and worker identities;
- manager lease scope and lease-policy digest; and
- operator authorization receipt digest, without predicting the runtime lease
  holder or fencing token.

Confirmation MUST refuse a dirty runner. Exploration MAY use a dirty runner only
when the complete patch is archived and hashed.

### 15.3 Immutable artifacts

Run manifests, candidate patches, evaluation receipts, taskpack manifests, and
closeouts MUST be content-addressed. Corrections append superseding receipts;
they do not edit historical evidence in place.

The canonical manifest digest printed by `rsi campaign plan` is the only input
accepted by `rsi campaign run --manifest`. A profile name or mutable manifest
path cannot launch work.

## 16. State, Backup, and Reconciliation

Campaign state MUST use transactional storage with an append-only event stream.
Allocation records MUST have leases and terminal states; `allocated` is not a
permanent terminal status.

### 16.1 Consistent control-plane snapshots

A `forge_lab.backup_snapshot.v1` MUST cover the complete authoritative control
plane, not only the candidate archive:

- transactional database and append-only event stream;
- campaign manifests, executable runner artifacts, checkpoints, closeouts,
  operator actions, allocations, fenced leases, and fuse records;
- model-request, task, worker, reconciliation, and usage receipts;
- task registry, taskpacks, sealed-split metadata, evaluator references, and
  schema registry; and
- archive metadata, candidate bundles, mutation diffs, and every reachable
  content-addressed blob.

The snapshot MUST bind a transactional database/event-sequence watermark and a
Merkle/content root. It is complete only when every artifact reachable at that
watermark is present and hash-verified. Writes after the watermark belong to a
later snapshot. Partial filesystem copies MUST NOT be advertised as backups.

Every complete snapshot MUST be encrypted in transit and at rest and replicated
off host into a separate failure domain. Provider secrets, OAuth/CLI session
stores, broker tokens, SSH private keys, encryption keys, cookies, and raw
secret values MUST be excluded. The snapshot records excluded secret classes,
key references, and restore-time dependencies without values. Restore keys MUST
be custodied separately from the snapshot.

The v0.1 baseline is RPO at most one hour, RTO at most four hours, and retention
of at least 24 hourly, 14 daily, and 8 weekly verified snapshots. A campaign MAY
pin stricter values. The backup-freshness fuse blocks new spend when the newest
verified off-host snapshot exceeds the RPO. A restarting process, a local-only
copy, an unverifiable root, or a target with no replica is not healthy.

### 16.2 Restore and drills

Restore MUST target an empty isolated location by default, verify every schema,
root, count, and referenced blob, expire all restored leases/tokens/packets,
and run reconciliation before activation. Activation requires explicit
operator action and a newer fencing token; it never reconnects restored broker
grants. `forge_lab.restore_receipt.v1` records the snapshot digest, target,
component roots/counts, exclusions, integrity result, expired authority, new
fence when activated, and measured RTO.

A successful isolated restore drill is required before the first continuous
campaign, at least every 30 days, and after any storage schema, snapshot format,
encryption, retention, or replica-target change.

### 16.3 Reconciliation

`rsi reconcile` MUST provide a dry run that reports:

- orphan workers and process groups;
- expired allocations and leases;
- campaigns without closeouts;
- unregistered worktrees and containers;
- missing or corrupt artifacts;
- broker requests without terminal receipts;
- local state not present in the replica.

It MUST also report stale fencing tokens, replayed packets, conflicting result
uploads, unacknowledged fuse trips, and backup/restore watermarks. Every run
emits `forge_lab.reconciliation_report.v1`. Destructive cleanup requires a
second explicit `--apply` command or operator confirmation and an idempotent
operator-action receipt.

## 17. Operator Control Surface

The v0.1 command family is:

```bash
rsi --version
rsi version [--json]
rsi doctor [--json]
rsi provider selftest --profile PROFILE [--live] [--require-independent-routes N] [--json]
rsi taskpack build --profile PROFILE [--json]
rsi campaign plan --profile explore-open [--json]
rsi campaign run --manifest sha256:DIGEST [--request-id ID] [--json]
rsi campaign list [--state STATE] [--json]
rsi campaign status [CAMPAIGN] [--json]
rsi campaign progress [CAMPAIGN] [--json]
rsi campaign events CAMPAIGN [--after SEQUENCE] [--follow] [--json]
rsi campaign pause CAMPAIGN [--request-id ID] [--json]
rsi campaign resume CAMPAIGN [--request-id ID] [--json]
rsi campaign stop CAMPAIGN [--request-id ID] [--json]
rsi campaign fork CAMPAIGN [--runner sha256:DIGEST] [--json]
rsi campaign fuse-ack CAMPAIGN --trip sha256:DIGEST --reason TEXT [--rearm] [--json]
rsi reconcile [--apply] [--json]
rsi backup create [--json]
rsi backup verify --snapshot sha256:DIGEST [--json]
rsi backup restore --snapshot sha256:DIGEST --target PATH [--apply] [--json]
rsi worker list [--json]
rsi worker enroll WORKER [--request-id ID] [--json]
rsi worker revoke WORKER [--request-id ID] [--json]
rsi alerts list [--json]
rsi alerts ack ALERT --reason TEXT [--request-id ID] [--json]
rsi archive inspect [CANDIDATE] [--json]
```

Requirements:

- `doctor` is side-effect-free and non-live by default: no provider call,
  login, service change, cleanup, migration, artifact repair, or authoritative
  write. It reports recommended explicit commands instead of applying them.
- `plan` performs no provider calls or worker/service changes. It canonicalizes
  and stores `forge_lab.campaign_manifest.v1`, materializes every referenced
  executable artifact, and prints the resulting `sha256:` manifest digest.
- `run` accepts only a stored content digest, never a profile or mutable path.
  It verifies the digest, prints campaign ID, state path, fuses, providers,
  taskpack, runner, backup state, and worker profile before opening dispatch.
- `fork` writes a new content-addressed manifest and provenance link without
  running it or modifying the source campaign.
- `status` shows provider readiness, active requests, tasks, compute, price
  completeness, worker health, archive progress, and backup health.
- `progress` reports per-candidate and per-task results without relying on
  buffered stdout.
- `events` reads the authoritative event sequence and can follow committed
  events without treating buffered logs as lifecycle truth.
- `fuse-ack` appends an acknowledgment; `--rearm` is accepted only when the
  manifest permits rearm and condition-cleared evidence exists.
- restore is read-only verification unless `--apply` is explicitly supplied;
  it never restores into a nonempty or active target.
- every mutating command writes `forge_lab.operator_action.v1` and is
  idempotent by supplied or generated request ID.
- `--json` uses the versioned `forge_lab.cli_result.v1` envelope and sends human
  diagnostics to stderr.
- commands exit nonzero for zero targets, missing preconditions, failed stop,
  or ambiguous lifecycle state.

Durable alerts are required for manager lease loss, fuse trip, stale backup,
watchdog failure, worker quarantine, ambiguous provider call, failed closeout,
restore failure, and disk/memory danger. Alert delivery distinguishes created,
delivery-accepted, delivered, acknowledged, and resolved; failure of an
external sink remains visible locally and never suppresses the alert.

Legacy `rsi-run`, `rsi-loop`, `rsi-status`, and `rsi-stop` may temporarily call
the new CLI but MUST preserve idempotency and exact lifecycle semantics and be
marked deprecated after parity is reached. `rsi-stop` MUST delegate to
`rsi campaign stop`; it cannot signal tmux directly.

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

Technical closeout dispositions are orthogonal to the lifecycle states in
section 14:

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

Until the implementation gates pass, the system MUST be described as the Forge
Lab v0.1 target protocol or legacy configuration search, not an operational
DGM. `DGM campaign` may describe an internal experiment only when every
non-seed child in each self-edit treatment was produced by the selected
parent's executable `self_improve`, every external-mutator descendant is
explicitly labeled as a control, all mutation receipts authenticate, and the
causal controls in section 10.5 ran under the preregistered model/resource
contract.

`Recursive self-improvement` is a stronger claim. It requires at least two
consecutive authentic self-edit transitions beyond the seed. For each
transition, the child MUST have a preregistered positive held-out paired effect
over its immediate parent under the declared uncertainty rule; generation N+1
also MUST execute `self_improve` code changed by generation N. The complete
self-edit/archive lineage MUST have a preregistered positive held-out treatment
effect over each fixed-mutator/archive, self-edit/latest-only, and
unchanged-agent control. These tests use sealed post-search evaluation so their
feedback is never reused for mutation. The result also MUST pass the declared
uncertainty and transfer success criteria at matched compute or the
preregistered compute treatment. A search-panel win, final recovery after an
earlier regression, best-of-many candidate, routing gain, or single improved
generation is insufficient.

No claim may originate from `explore-open` alone. A public capability claim
requires reproducible artifacts and an explicit operator decision outside this
specification. Production fitness or autonomous apply additionally remains
behind the One Wire and standing production-governance gates regardless of lab
evidence.

## 20. Schema Requirements

v0.1 MUST version at least these schemas:

- `forge_lab.campaign_manifest.v1`;
- `forge_lab.runner_artifact.v1`;
- `forge_lab.agent_bundle.v1`;
- `forge_lab.bundle_diff.v1`;
- `forge_lab.candidate.v1`;
- `forge_lab.mutation_receipt.v1`;
- `forge_lab.model_request_receipt.v1`;
- `forge_lab.task_attempt.v1`;
- `forge_lab.promotion_decision.v1`;
- `forge_lab.campaign_event.v1`;
- `forge_lab.checkpoint.v1`;
- `forge_lab.allocation.v1`;
- `forge_lab.fenced_lease.v1`;
- `forge_lab.closeout.v1`;
- `forge_lab.provider_liveness.v1`;
- `forge_lab.broker_grant.v1`;
- `forge_lab.worker_capability.v1`;
- `forge_lab.worker_enrollment.v1`;
- `forge_lab.worker_revocation.v1`;
- `forge_lab.work_packet.v1`;
- `forge_lab.worker_heartbeat.v1`;
- `forge_lab.worker_result.v1`;
- `forge_lab.operator_action.v1`;
- `forge_lab.fuse_trip.v1`;
- `forge_lab.fuse_ack.v1`;
- `forge_lab.watchdog_observation.v1`;
- `forge_lab.reconciliation_report.v1`;
- `forge_lab.backup_snapshot.v1`;
- `forge_lab.backup_verification.v1`;
- `forge_lab.restore_receipt.v1`;
- `forge_lab.archive_commit.v1`;
- `forge_lab.alert.v1`; and
- `forge_lab.cli_result.v1`.

`forge_lab.agent_bundle.v1` is the binary canonical envelope defined in section
8.4 and MUST ship conformance vectors. Every other listed authoritative record
MUST have a repository-owned JSON Schema 2020-12 strict writer and use UTF-8
RFC 8785 canonical JSON. Records use lowercase `sha256:` plus 64 hexadecimal
digits for content digests, RFC 3339 UTC timestamps, and integers for counters.
The digest is computed over the canonical payload without any recursive digest
field. Unknown values are explicit `null`, never an ambiguous omission, empty
string, or zero. Corrections are immutable new records with
`supersedes_digest`.

Every campaign-scoped authoritative mutation after lease acquisition MUST carry
campaign execution identity, manifest digest, event sequence, idempotency key,
and current fencing token. Pre-campaign plan/runner records and the create
action/event carry a planning execution identity, manifest digest, and
idempotency key, with campaign/fence explicitly `null` until the campaign ID is
reserved; they grant no execution authority. Lease acquisition is the bootstrap
transaction that writes the first current token. Host/global records carry
their scoped execution identity and idempotency key with campaign, manifest,
event sequence, and fence explicitly `null` when inapplicable.

A store-outage `forge_lab.watchdog_observation.v1` is the only campaign-scoped
record allowed without a current fence. It binds campaign/manifest, last
observed fence, watchdog/policy identity, observation/action/time, and signature
and grants no lifecycle or scientific mutation until imported by a current
recovery-only lease.

Signed remote records also carry signer/key ID, algorithm, signature, nonce,
issue time, and expiry. No schema permits a raw secret, bearer token, OAuth/CLI
session material, cookie, private key, or unredacted response containing
credentials.

At minimum:

- checkpoints bind lifecycle and terminal intent, manifest/runner digests,
  event watermark, fence, scheduler cursor, work/request/allocation states, and
  usage/archive watermarks;
- allocations and fenced leases bind scope, holder, monotonic token, TTL,
  acquire/renew/expire/release timestamps, and terminal status;
- heartbeats bind worker identity and boot ID, monotonic sequence, packet,
  fence, observed state, control-plane receive time, and signature;
- fuse-trip records bind policy digest, observation, threshold, action, scope,
  revocation receipt, trip time, and rearm epoch; fuse acknowledgments bind the
  exact trip digest, actor, acknowledgment time/reason, condition-cleared
  evidence, and requested/new rearm epoch;
- backup records bind the consistency watermark, component roots/counts,
  replica, encryption/key reference, exclusions, retention, RPO, and RTO; and
- restore records bind snapshot and target digests, restored roots/counts,
  integrity result, expired leases/grants, new fence if activated, and measured
  RTO.

Schema parsers MUST reject ambiguous legacy shapes at write time and provide
explicit read-only migration adapters for historical v0 artifacts. A legacy
adapter cannot mint a v1 signature, validity state, or selectable candidate.

## 21. Normative Invariants

- **I-01 Canonical control:** Meghadharma is the sole campaign, archive,
  provider-broker, and receipt authority even when execution workers are remote.
- **I-02 Authenticity:** every non-seed self-edit child is emitted by the
  selected parent bundle's own `self_improve` code and has an authentic mutation
  receipt binding parent, self-editor, child, and diff.
- **I-03 Mutable boundary:** candidate writes are confined to the copied bundle
  root and declared child-output root during mutation, plus the assigned target
  worktree and task scratch space during solve.
- **I-04 Immutable core:** candidate code cannot read or modify evaluator
  internals, task allocation, broker policy, fuses, archive selection, receipts,
  secrets, specification, or production source.
- **I-05 Identity:** candidate identity is the hash of the one canonical bundle
  envelope containing API version, base identity, and normalized tree bytes;
  lineage binds parent, treatment, mutation operator, child, and diff digests.
- **I-06 Admission:** only functional, policy-valid candidates are selectable;
  both entry points pass immutable external handshakes, and all rejected
  children remain evidence-only.
- **I-07 Stepping stones:** every eligible non-perfect parent retains nonzero
  selection probability, and novelty pressure counts only functional children.
- **I-08 Mode authority:** `explore-open`, race, and confirm mutation, task, and
  claim permissions cannot bleed into one another.
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
- **I-15 Secret custody:** only a Forge-scoped broker or enrolled trusted remote
  route adapter has Forge provider credentials; controllers, candidates,
  workers, and graders never receive them.
- **I-16 Compute separation:** adaptive research allocation and the operational
  emergency fuse remain separate contracts.
- **I-17 Complete accounting:** mutation, execution, critique, verification,
  retries, failures, and ambiguous provider calls are counted.
- **I-18 Containment:** every candidate-controlled `self_improve`, `solve`,
  helper, and hook is resource-limited, ephemeral, non-root, and denied host
  access except its scoped broker channel; grading is brokerless and isolated.
- **I-19 Idempotency:** side effects have write-ahead identities; resume cannot
  duplicate known calls, allocations, archive rows, or completed tasks.
- **I-20 Drift refusal:** changed code, image, task, evaluator, routing, or
  selection digests block resume and require a provenance-linked fork.
- **I-21 Cleanup:** every stop or terminal path revokes new authority, preserves
  all evidence, commits a pre-cleanup closeout before destructive cleanup, and
  reconciles workers, process groups, mounts, worktrees, allocations, and locks.
- **I-22 Evidence:** no terminal campaign lacks a closeout, raw usage ledger,
  campaign manifest, runner-artifact verification, and reconciliation result.
- **I-23 No automatic promotion:** no lab result mutates production, governed
  fitness, routing, or external state without a separate operator protocol.
- **I-24 Fail closed:** missing identity, pairing, sealing, usage, containment,
  provenance, or lifecycle evidence is invalid evidence, never best-effort
  green.
- **I-25 Fenced authority:** every mutation carries the current manager fencing
  token; stale holders, broker grants, workers, and writes are rejected.
- **I-26 Runnable provenance:** every campaign pins a retrievable executable
  runner environment; source or environment drift requires a linked fork.
- **I-27 Orthogonal state:** execution state, scientific verdict, and archive
  persistence are independent, and persistence alone confers no validity.
- **I-28 Recoverable control plane:** a verified, encrypted, off-host snapshot
  covers all authoritative state at one consistency watermark and restores
  without reviving authority.
- **I-29 Remote trust:** enrolled remote workers use signed expiring
  replay-protected packets, authenticated heartbeats, scoped grants, idempotent
  results, and immediate revocation/quarantine.
- **I-30 Claim boundary:** lab evidence cannot mint production fitness through
  self-report, and recursive-improvement claims require positive
  multi-generation held-out evidence over causal controls plus operator review.
- **I-31 Fuse determinism:** every live campaign has externally enforceable,
  manifest-pinned fuse actions and explicit evidence for any dangerous opt-out.

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

Forge Lab v0.1 is complete only when every stable gate below passes. A verifier
path is normative even while its test is initially absent; implementation
packets add the test and artifacts before changing the gate to passing.

| ID | Required demonstration | Invariants | Verifier command or test | Required artifacts |
|---|---|---|---|---|
| AC-01 | An otherwise valid candidate using more than 90,000 tokens remains valid; no historical cap is reintroduced. | I-16, I-24 | `pytest -q tests/forge_lab_v1/test_acceptance.py::test_ac_01_open_compute` | candidate, task, and closeout receipts |
| AC-02 | Mutation, solve, critique, verification, retry, failure, and ambiguous usage reconcile to campaign totals; unknown price is `null` with completeness. | I-16, I-17 | `pytest -q tests/forge_lab_v1/test_acceptance.py::test_ac_02_usage_and_price` | request receipts, usage ledger, pricing projection |
| AC-03 | Wall, call, token, heartbeat, resource, error, backup, and watchdog fuses take their pinned actions without changing completed verdicts; every opt-out is specific and expiring. | I-16, I-21, I-31 | `pytest -q tests/forge_lab_v1/test_lifecycle_faults.py::test_ac_03_fuse_matrix` | fuse policy, trip/ack, watchdog, revocation, and opt-out receipts |
| AC-04 | Offline self-test lists every catalog route and exact reason, makes no live call, and exits nonzero for zero selected targets. | I-13, I-24 | `rsi provider selftest --profile staged --json` | catalog digest and provider-liveness inventory |
| AC-05 | Moonshot and Kimi Code have distinct identities/receipts, and no controller, worker, grader, or candidate can read broker/adapter credentials. | I-01, I-13, I-15 | `pytest -q tests/forge_lab_v1/test_acceptance.py::test_ac_05_route_and_secret_identity` | liveness, broker identity, and secret-isolation receipts |
| AC-06 | Every staged route passes its own explicit headless live probe on Meghadharma; two independent routes exist before cross-provider confirmation. | I-13, I-24 | `rsi provider selftest --profile staged --live --require-independent-routes 2 --json` | independent signed live-probe receipts |
| AC-07 | SIGINT, SIGTERM, timeout, worker crash, controller crash, host restart, normal exhaustion, and failure follow the canonical table and preserve a closeout. | I-19, I-21, I-22, I-25 | `pytest -q tests/forge_lab_v1/test_lifecycle_faults.py::test_ac_07_transition_matrix` | event stream, checkpoints, closeouts, reconciliation receipts |
| AC-08 | Resume duplicates no completed request/task, rejects every pinned-artifact drift, and permits only a provenance-linked fork. | I-19, I-20, I-26 | `pytest -q tests/forge_lab_v1/test_lifecycle_faults.py::test_ac_08_resume_and_drift` | idempotency records, runner verification, fork manifest |
| AC-09 | Repeated stop keeps one deadline/action, classifies uncancellable calls, commits evidence and closeout before cleanup, and leaves no live grant or unclassified request. | I-19, I-21, I-22 | `pytest -q tests/forge_lab_v1/test_lifecycle_faults.py::test_ac_09_stop_is_crash_safe` | operator action, pre/final closeouts, usage and cleanup receipts |
| AC-10 | Lease renewal, loss, stale-writer rejection, expiry takeover, and release use strictly increasing fencing tokens. | I-19, I-25 | `pytest -q tests/forge_lab_v1/test_lifecycle_faults.py::test_ac_10_fenced_lease_takeover` | fenced-lease, stale-rejection, and takeover receipts |
| AC-11 | Reconcile finds and safely resolves orphan worktree, allocation, worker, packet, request, stale fence, and missing closeout without implicit destructive action. | I-19, I-21, I-24 | `pytest -q tests/forge_lab_v1/test_lifecycle_faults.py::test_ac_11_reconciliation` | dry-run and applied reconciliation reports |
| AC-12 | Hostile `self_improve`, `solve`, helper, and build-hook fixtures cannot read secrets/control/evaluator/production/Docker surfaces and are resource terminated. | I-03, I-04, I-15, I-18 | `pytest -q tests/forge_lab_v1/test_containment.py::test_ac_12_all_candidate_entrypoints` | containment and resource-termination receipts |
| AC-13 | Solve cannot read or exfiltrate hidden data; grader is fresh, brokerless, networkless, and runs no candidate hook or plugin. | I-04, I-12, I-18 | `pytest -q tests/forge_lab_v1/test_containment.py::test_ac_13_solve_grader_separation` | solve-output digest, grader launch, adversarial-test receipts |
| AC-14 | Both immutable external handshakes gate admission; every materialized non-seed candidate row verifies treatment/operator/parent/child/diff bindings; generation N+1 runs self-editor code changed by N in self-edit treatments. | I-02, I-05, I-06 | `pytest -q tests/forge_lab_v1/test_agent_bundle.py::test_ac_14_admission_and_authenticity` | handshake, mutation, signature, lineage, and descendant receipts |
| AC-15 | Worker enrollment, expiry/replay rejection, scoped grant, authenticated heartbeat, idempotent/conflicting result, revocation, and quarantine all fail closed. | I-01, I-15, I-25, I-29 | `pytest -q tests/forge_lab_v1/test_remote_worker.py::test_ac_15_worker_trust_protocol` | enrollment, packet, heartbeat, result, revocation receipts |
| AC-16 | Coverage proves task rotation; parent, child, and controls receive identical paired blocks and resource contracts. | I-09, I-10, I-11 | `pytest -q tests/forge_lab_v1/test_evaluation_protocol.py::test_ac_16_pairing_and_rotation` | taskpack, block-allocation, and coverage receipts |
| AC-17 | Sealed artifacts/logs never enter mutation; candidate, parent, baseline, and transfer treatment complete preregistered paired evaluation. | I-08, I-12 | `pytest -q tests/forge_lab_v1/test_evaluation_protocol.py::test_ac_17_sealing_and_transfer` | split-custody, confirmation, and transfer receipts |
| AC-18 | The causal runner compares fixed-mutator/archive, self-edit/latest-only, self-edit/archive, and unchanged baseline; `fixed_route` and `evolvable_pool` claims obey their exact resource contracts. | I-07, I-08, I-09, I-30 | `pytest -q tests/forge_lab_v1/test_evaluation_protocol.py::test_ac_18_controls_and_model_access` | preregistration, treatment manifests, paired results |
| AC-19 | Cross-cohort raw ranking is rejected; unauthorized fallback invalidates the block without lowering candidate fitness. | I-11, I-14, I-24 | `pytest -q tests/forge_lab_v1/test_evaluation_protocol.py::test_ac_19_comparison_guard` | rejection and invalid-comparison receipts |
| AC-20 | Canonical serialization is stable, changes ID exactly when identity bytes change, rejects ambiguous paths, and permits reevaluation identity changes. | I-05, I-24 | `pytest -q tests/forge_lab_v1/test_agent_bundle.py::test_ac_20_canonical_identity` | canonical-byte vectors and evaluation receipts |
| AC-21 | Plan emits a digest-only launch contract with a retrievable runner; run rejects profiles/mutable paths; reconstruction and fork work without the original checkout. | I-20, I-26 | `pytest -q tests/forge_lab_v1/test_provenance.py::test_ac_21_manifest_runner_replay` | manifest, runner artifact, CAS verification, fork link |
| AC-22 | Nonfunctional/provisional/confirmed/quarantined evidence persists independently; archive failure is not a verdict; legacy v0 is read-only and cannot enter v1 selection. | I-06, I-27 | `pytest -q tests/forge_lab_v1/test_archive.py::test_ac_22_orthogonal_archive_and_legacy` | archive commits, candidate axes, migration receipts |
| AC-23 | A full consistent encrypted off-host snapshot meets RPO, trips when stale, restores into an empty target within RTO, and revives no lease/grant. | I-22, I-28, I-31 | `pytest -q tests/forge_lab_v1/test_backup_restore.py::test_ac_23_full_control_plane_restore` | snapshot/verification/restore/fuse receipts |
| AC-24 | A recursive-improvement label is rejected unless two consecutive authentic child-parent transitions are each positive on sealed held-out evaluation, the lineage beats every causal control under the declared uncertainty rule, and it passes a declared transfer criterion at matched or preregistered compute. | I-02, I-07, I-08, I-24, I-30 | `pytest -q tests/forge_lab_v1/test_claims.py::test_ac_24_recursive_claim_gate` | lineage, sealed statistics, controls, transfer, compute, claim decision |
| AC-25 | No lab result changes production, governed fitness, or standing apply without separate operator and One Wire authority. | I-23, I-30 | `pytest -q tests/forge_lab_v1/test_claims.py::test_ac_25_one_wire_boundary` | blocked/authorized runtime warrants and operator receipts |
| AC-26 | Doctor is side-effect-free; plan/run/list/events/fork/fuse-ack/backup/restore/alerts commands obey JSON, idempotency, nonzero, and alert-delivery contracts. | I-19, I-22, I-24 | `pytest -q tests/forge_lab_v1/test_cli_contract.py::test_ac_26_operator_surface` | CLI result envelopes, operator actions, alert receipts |

## 24. Host Capability Reconciliation Contract

IP addresses, usernames, current login state, installed-binary observations,
reachable ports, and route liveness are volatile evidence and MUST NOT be
embedded as durable normative facts in this specification. They belong in
dated, expiring provider-liveness and worker-capability receipts referenced by
a host-profile digest.

Each reconciliation snapshot MUST record stable host/peer identity,
`observed_at`, `expires_at`, catalog/alias digest, one independent liveness
receipt per provider entitlement, CLI headless-dispatch evidence, worker
capabilities, approved private-transport status, explicit unavailable reasons,
and evidence digests. It MUST contain no credential value, session material,
private address assumption, or inferred entitlement. Stale evidence is
unavailable evidence.

Before planning a live route or remote worker, Forge MUST reconcile the current
Meghadharma profile against the canonical catalog and any optional comparison
host, verify each selected capability independently, and pin the resulting
snapshot digest. A remote comparison or route-adapter host remains replaceable
capacity; reconciliation never transfers campaign, archive, broker-accounting,
or receipt authority away from Meghadharma.

## 25. Primary References

- Darwin Goedel Machine paper: <https://arxiv.org/abs/2505.22954>
- Sakana DGM project page: <https://sakana.ai/dgm/>
- Paper-linked DGM implementation: <https://github.com/jennyzzt/dgm>
- Local official SWE-bench runbook: `docs/RUNPOD_SWEBENCH_RUNBOOK.md`
- Provider matrix contract: `docs/architecture/PROVIDER_MATRIX_HARNESS.md`
- Existing Forge research goal:
  `docs/agent_tasks/2026-06-12_forge_rehydration_benchmark_evolution_goal.md`
