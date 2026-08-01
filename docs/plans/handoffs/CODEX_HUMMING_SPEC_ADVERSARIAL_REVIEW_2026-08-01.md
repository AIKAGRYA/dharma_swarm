# Codex Adversarial Review — Harness · Loop · Graph Humming Spec

**Date:** 2026-08-01  
**Review role:** independent adversarial second pass  
**Subject:** `docs/plans/HARNESS_LOOP_GRAPH_HUMMING_SPEC_2026-08-01.md`  
**Subject pin:** `2d4aa5a1f86b2030454b7cb504239c4d78d73816`  
**Request:** `docs/plans/handoffs/HUMMING_SPEC_CODEX_ADVERSARIAL_REVIEW_REQUEST_2026-08-01.md` on PR #1186  
**Repository truth base used for live enforcement checks:** `c4ab31e63b410e3ec73a49bb4fd6a73e7fe2852b`  
**Authority:** review only. This document grants no edit, merge, deployment, loop-closure, archive-fitness, or self-improvement authority.

## 0. Frozen rubric

This rubric was fixed before assigning any score.

Each dimension is scored from 0 to 25.

| Band | Verdict | Meaning |
|---:|---|---|
| 0–5 | `CONTRADICTED` | The proposal materially misframes the problem or would make the system less trustworthy. |
| 6–12 | `PARTIAL` | Useful elements exist, but major omissions, category errors, or non-enforceable criteria prevent execution as written. |
| 13–19 | `SUPPORTED_WITH_FINDINGS` | The majority is directionally correct, but bounded structural repairs are required before execution. |
| 20–23 | `SUPPORTED` | Complete enough to execute; remaining findings are local and non-architectural. |
| 24–25 | `STRONGLY_SUPPORTED` | Mechanically complete, adversarially credible, and aligned with current runtime and governance truth. |

Dimension subweights are also frozen:

- **A. Article coverage (25):** taxonomy 6; prescribed ordering 7; behavior/cadence/path diagnosis 6; all four loop levels 6.
- **B. Enforcement realism (25):** non-charmable checks 7; live-path and merge-blocking reality 7; causal evidence 6; rollback and negative controls 5.
- **C. Future-proofing (25):** research accuracy 7; frontier coverage 6; evaluator/self-reference containment 7; architectural adaptability 5.
- **D. Governance fit (25):** surface ownership 7; WIP/adoption mechanics 6; authority separation 6; BR-id and provenance hygiene 6.

Overall verdict bands:

| Total | Overall verdict |
|---:|---|
| 0–24 | `CONTRADICTED` |
| 25–49 | `WEAK_PARTIAL` |
| 50–69 | `PARTIAL` |
| 70–84 | `SUPPORTED_WITH_FINDINGS` |
| 85–94 | `SUPPORTED` |
| 95–100 | `STRONGLY_SUPPORTED` |

## 1. Verdict

| Dimension | Score | Verdict |
|---|---:|---|
| A. Article coverage | **18/25** | `SUPPORTED_WITH_FINDINGS` |
| B. Enforcement realism | **8/25** | `PARTIAL` |
| C. Future-proofing | **16/25** | `SUPPORTED_WITH_FINDINGS` |
| D. Governance fit | **15/25** | `SUPPORTED_WITH_FINDINGS` |
| **Overall** | **57/100** | **`PARTIAL — REQUEST_CHANGES`** |

The spec has the correct strategic center: Dharma Swarm's recurring defect is often not an absent mechanism but a **dead causal edge** between a producer and a later decision. The proposed consumption doctrine, supervisor honesty, and attempt to join harness, loop, and graph work are valuable (`HARNESS_LOOP_GRAPH_HUMMING_SPEC_2026-08-01.md:20-39`, `:88-99`).

The current version is not safe to execute as the portfolio controller. It collapses three different disciplines into one universal four-predicate score, treats advisory checks and caller grep as enforcement, reverses the article's safety-first order in several places, proposes installing a fail-open hook as a safety gate, and routes topology genomes through the legacy DAG executor rather than the neutral graph runtime (`HARNESS_LOOP_GRAPH_HUMMING_SPEC_2026-08-01.md:20-39`, `:104-142`, `:297-304`, `:451-522`).

The right disposition is **repair V1 in place or issue a narrow V2**. The underlying workstreams do not need to be discarded.

## 2. Highest-severity findings

### F1 — P0: the universal `LIVE / EVENTED / ENFORCED / USED` definition is a category error

V1 declares every layer humming only when all four predicates hold (`HARNESS_LOOP_GRAPH_HUMMING_SPEC_2026-08-01.md:20-39`). This is not faithful to the article's own separation of concerns.

- `EVENTED` is a cadence property of a loop. A per-invocation safety harness can be correct without a cron, webhook, or heartbeat.
- `USED` is a feedback property of a loop. A graph compiler or pre-action authorization gate need not feed its output into a later adaptive cycle.
- `LIVE` is deployment status, not semantic correctness. A candidate graph can be correct but not production-admitted; a live legacy executor can be incorrect.
- `ENFORCED` has different meanings at runtime, in CI, and at merge admission. V1 does not distinguish them.

This conflation makes the scoreboard gameable: a harness can acquire a meaningless trigger and consumer merely to satisfy the same shape as a feedback loop, while a graph can receive a caller without actually constraining the path.

Replace the universal definition with typed contracts:

| Discipline | Required predicates |
|---|---|
| Harness | `IN_PATH`, `PRE_ACTION`, `FAIL_CLOSED_FOR_SCOPED_RISK`, `IDENTITY_BOUND`, `RECEIPTED`, `NON_BYPASSABLE` |
| Loop | `TRIGGERED`, `STATE_PERSISTS`, `BOUNDED`, `VERIFIED`, `OUTPUT_CHANGES_A_LATER_CYCLE` |
| Graph | `COMPILED`, `EDGE_ENFORCED`, `STATE_DURABLE`, `INTERRUPTIBLE_WHERE_REQUIRED`, `TERMINATION_BOUNDED` |
| Event lane | `SOURCE_AUTHENTICATED`, `DELIVERY_DURABLE`, `DEDUPLICATED`, `CONSUMER_ACKNOWLEDGED`, `BACKPRESSURED` |

`LIVE` should remain a deployment qualifier on any of those contracts, not one predicate that changes their meaning.

### F2 — P0: “USED” is necessary for a feedback loop but not sufficient for `CLOSED_LIVE`

V1 says predicate 4 upgrades `HARNESS_PROVEN` to `CLOSED_LIVE` (`HARNESS_LOOP_GRAPH_HUMMING_SPEC_2026-08-01.md:35-39`). The canonical loop map requires a separate live owner-surface proof on the daemon branch that actually runs, and each loop has a different remaining criterion: served-provider truth, real production memory, production scheduler state, non-synthetic trajectories, live roster/probation materialization, or external quorum (`CYBERNETIC_LOOP_MAP.md:7-16`, `:70-107`).

A static caller or consumer can be a no-op. A same-harness consumer can still be circular evidence. A downstream component can read a value and ignore it. Therefore the stronger doctrine should be:

> A loop closes only when a live producer receipt and a later live consumer receipt share causal identity, the consumed value causes a non-empty decision delta, and a negative control or ablation removes that delta.

Minimum closure evidence:

1. producer receipt with source identity and output digest;
2. consumer receipt naming the producer receipt or consumed trace IDs;
3. later-cycle or post-restart read when persistence is part of the claim;
4. decision delta or action delta attributable to the consumed value;
5. negative control showing no delta when the value is absent, stale, invalid, or substituted;
6. the loop-specific owner criterion from `live_owner_surface_criteria`.

This preserves V1's best insight while preventing a one-line caller from manufacturing closure.

### F3 — P0: the enforcement matrix confuses existence, advisory observation, merge blocking, and runtime blocking

V1 requires a test, a closure/governance check, and CI placement for every wire, with checks entering advisory before promotion (`HARNESS_LOOP_GRAPH_HUMMING_SPEC_2026-08-01.md:451-471`). It then calls the resulting layer `ENFORCED`.

Current CI truth does not support that claim. The contract explicitly states that required checks block merge while advisory checks do not; the required set is currently DocOps, gitleaks, Python 3.11 tests, Python 3.12 tests, Coherence Delta, and onboarding parity (`docs/governance/CI_TRUTH_CONTRACT.json:1-65`). A new advisory job can fail forever without blocking merge. A test can exist without being selected by a required job. A governance report can exist without any merge or runtime consumer.

Freeze four enforcement levels:

| Level | Meaning |
|---|---|
| `OBSERVED` | A receipt or report is emitted. |
| `CHECKED` | A deterministic checker replays the claim and fails on a negative control. |
| `MERGE_BLOCKING` | A required context or Merge Master gate consumes the checker result and blocks admission. |
| `RUNTIME_BLOCKING` | The consequential action cannot commit when the check, warrant, lease, budget reservation, or receipt preparation fails. |

Only `MERGE_BLOCKING` or `RUNTIME_BLOCKING` should satisfy V1's word `ENFORCED`, with the applicable level named per claim.

The current scoreboard contains multiple charmable checks (`HARNESS_LOOP_GRAPH_HUMMING_SPEC_2026-08-01.md:503-522`):

- `rg` proves text reachability, not live execution or causal use;
- a non-test caller can still be behind a permanently false flag;
- a registered SignalBus consumer can be a no-op or fail before acknowledgement;
- “Brier receipts present” does not establish calibration without probabilistic forecasts and independently known outcomes;
- a source diff cannot mechanically prove semantic gate monotonicity;
- “CI contract diff reviewed” is a human statement, not a check.

### F4 — P0: H1 proposes installing a hook whose present failure policy contradicts the claimed gate

H1 says to install `hooks/telos_gate.py` as a `PreToolUse` gate and accept a recorded denial under `~/.dharma/quarantine/` (`HARNESS_LOOP_GRAPH_HUMMING_SPEC_2026-08-01.md:104-115`). The tracked Claude settings currently register only `SessionStart` (`.claude/settings.json:1-13`), so the baseline finding is correct.

The proposed implementation is not safe as written:

- tier-A or tier-B denial returns before the witness logging block, so denied actions are not recorded by this hook;
- the only log sink shown is `~/.dharma/witness/`, not the claimed quarantine path;
- empty input is allowed;
- malformed JSON or type errors are allowed;
- the top-level catch-all also allows unexpected failures (`hooks/telos_gate.py:130-184`).

Installing it unchanged would add the appearance of a fail-closed harness while preserving fail-open parser and crash paths. It is also Claude-Code-seat-specific, not a universal Dharma Swarm effect boundary.

H1 must become two slices:

1. **H1a harden the hook:** strict schema; unknown gated tool fails closed; denial receipt written before return; parse/crash behavior explicitly chosen by risk class; sabotage tests; no catch-all allow for consequential tools.
2. **H1b install the hardened hook:** tracked settings plus an end-to-end Claude Code hook test.

The repo-wide harness must still live below the seat-specific hook at the actual effect dispatcher.

### F5 — P0: H2 attaches an LLM judge to the wrong side of the CaMeL boundary

V1 correctly cites CaMeL for control-flow/data-flow separation, but combines that with a judge tier for side-effect tools (`HARNESS_LOOP_GRAPH_HUMMING_SPEC_2026-08-01.md:116-142`). CaMeL's contribution is deterministic capability and information-flow enforcement outside the model, not permission granted by a second stochastic model (Debenedetti et al., *Defeating Prompt Injections by Design*, arXiv:2503.18813).

The safe division is:

- deterministic provenance and capability policy decides which effects are structurally possible;
- a model judge may add a denial, abstention, explanation, or escalation;
- a model judge may never upgrade an effect from denied/unproven to authorized;
- timeout or unavailable judge must not widen capabilities;
- external text may populate data fields but may not choose the capability, destination, authority class, or graph edge.

H2 should introduce a typed action/effect envelope, not merely provenance tags in receipt metadata.

### F6 — P0: the phase order violates the article's prescribed order

The article's order is harness first; then the simplest agent loop plus grader; then graph structure for known mandatory decisions; then event and hill-climbing loops. V1's P0 mixes a prompt feedback wire, graph fixes, loop acceptance, shell-loop bounding, shell policy, and hook installation, while the stronger semantic harness, kernel bridge, sandbox isolation, and context provenance work remain in P3 (`HARNESS_LOOP_GRAPH_HUMMING_SPEC_2026-08-01.md:473-500`).

This allows L1, L2, E2, E3, and G2 to create new live consumption, optimizer, event, and execution edges before H2 establishes the provenance/capability boundary they depend on.

Required phase order is in §6 below.

### F7 — P0: G2 closes the metadata gap through the legacy executor, not the neutral graph engine

G2 proposes invoking `execute_topology_genome_workflow` from the live orchestrator (`HARNESS_LOOP_GRAPH_HUMMING_SPEC_2026-08-01.md:297-304`). That function calls `genome.compile(node_functions)` and executes the result through `CompiledWorkflow` (`dharma_swarm/workflow.py:612-682`). `TopologyGenome.compile` constructs dependency-list `WorkflowStep` objects and returns that legacy executor (`dharma_swarm/topology_genome.py:68-125`).

Therefore G2 would make genomes execute, but it would not make the candidate Pregel runtime constrain the live path. It risks cementing the exact split V1 diagnoses: a rigorous neutral graph engine beside a weaker production DAG.

Replace G2 with:

1. define the topology-genome-to-neutral-DharmaGraph compiler;
2. shadow-run legacy and neutral engines on the same genome and compare semantic outcomes;
3. require durable receipts, negative controls, and parity acceptance;
4. flip one scoped production lane only after the neutral engine passes;
5. retire or explicitly demote the legacy bridge after migration.

A grep for a caller is not sufficient evidence.

### F8 — P0: “monitors must have actuators” violates separation of duties when stated universally

The narrower finding is correct: a state named `PAUSE_LOOP` must either pause the loop or be renamed as a recommendation (`HARNESS_LOOP_GRAPH_HUMMING_SPEC_2026-08-01.md:88-99`, `:236-251`). The doctrine sentence “monitors must have actuators” is too broad.

Independent witnesses, auditors, graders, and safety monitors should often be unable to actuate the system they evaluate. Combining observation, judgment, authorization, and execution increases self-approval and telemetry-manipulation risk.

Replace it with:

> Every intervention-shaped output must have a typed disposition: `OBSERVATION`, `RECOMMENDATION`, `AUTHORIZATION_REQUEST`, or `ACTUATION`. Only an explicitly authorized actuator may execute the last category, and its receipt must name the independent observation and authorization it consumed.

L3 can still implement an expiring, bounded pause actuator without granting every monitor action authority.

### F9 — P1: H5's “memory must not shrink” acceptance criterion rewards bloat, not retained capability

H5 proposes detecting context collapse by requiring playbook length and key count not to shrink over compactions without a curation receipt (`HARNESS_LOOP_GRAPH_HUMMING_SPEC_2026-08-01.md:162-184`). This is directly Goodhartable. A playbook can preserve every key while becoming redundant, contradictory, stale, or too expensive. TiMem reports value partly through reducing recalled memory while retaining utility, so raw non-shrinkage is not the research target (arXiv:2601.02845).

Replace size monotonicity with held-out capability and integrity metrics:

- answer/retrieval success on frozen context-eval cases;
- source-attribution and contradiction rate;
- stale-claim rejection;
- token and latency budget;
- semantic coverage of protected facts;
- explicit curation receipt for deletion or supersession;
- ablation showing the playbook improves later work over raw recall alone.

### F10 — P1: rlimits do not provide default-deny networking for `LocalSandbox`

H6 combines CPU/memory/file-size rlimits with “default-deny network” for `LocalSandbox` (`HARNESS_LOOP_GRAPH_HUMMING_SPEC_2026-08-01.md:185-196`). POSIX resource limits do not themselves create a network namespace or syscall policy.

The honest alternatives are:

- require Docker/namespace/seccomp isolation for untrusted or network-denied work and fail closed if unavailable;
- use an OS sandbox mechanism with a tested network-deny boundary;
- retain `LocalSandbox` as a weak subprocess tier and name that limitation in every receipt.

A unit test that a cooperative command cannot connect is not proof against arbitrary code unless the OS boundary is actually present.

### F11 — P1: L1's caller grep can close Loop 7 while importing an untrusted strategy into the system prompt

L1's acceptance is one non-definition caller plus a reinforcement test (`HARNESS_LOOP_GRAPH_HUMMING_SPEC_2026-08-01.md:198-210`). That proves reachability, not that a live non-synthetic trajectory changed a later decision safely.

It also places trace-derived strategy text into the live system prompt before H2's provenance/capability boundary and H5's context curation are established.

Require a shadow/canary path first:

- only receipt-grounded, source-classified strategies;
- injection scan and maximum top-k/character budget;
- strategy IDs and prompt digest in the dispatch receipt;
- no strategy text may alter tool capability or authorization fields;
- counterfactual paired run without the strategy;
- rollback switch and invalid-strategy negative control;
- live owner-surface criterion from Loop 7, not grep.

### F12 — P1: L2 couples the producer optimizer and evaluator too tightly

V1 proposes turning on an LLM judge and then applying GEPA-style evolution to grader rubrics and repair prompts (`HARNESS_LOOP_GRAPH_HUMMING_SPEC_2026-08-01.md:212-235`). GEPA is strong evidence for reflective prompt optimization against an external metric; its reported gains do not prove that a co-evolved evaluator remains an independent truth source (Agrawal et al., arXiv:2507.19457).

Do not let one optimization loop simultaneously rewrite the producer, repair prompt, rubric, and judge on the same data. Require:

- immutable, versioned holdout tasks and outcomes;
- producer and evaluator epochs separated;
- deterministic correctness checks remain authoritative;
- human- or externally-grounded labels for calibration;
- Brier score only for explicit probability forecasts against known outcomes;
- abstention and expected-calibration-error tracking;
- old, new, and adversarial evaluator ensemble before promotion;
- evaluator candidate has no write access to its own held-out evidence.

The Red Queen Gödel Machine's fixed evaluation epochs are more relevant to this separation than a simple “co-evolve both” instruction (arXiv:2606.26294).

### F13 — P1: L5 cannot honestly promise a cost ceiling without an authoritative spend source

L5 adds a cumulative token/cost ceiling to the shell loop (`HARNESS_LOOP_GRAPH_HUMMING_SPEC_2026-08-01.md:252-261`). The repo has already learned this lesson in Sarathi: a parent loop can enqueue work whose downstream provider cost never reaches the parent's direct-spend ledger.

Until a lineage-aware budget source charges parent, children, retries, fallback providers, and tool-mediated model calls, L5 should claim only cycle and wall-clock bounds. A cost bound must reserve from an authoritative hierarchical ledger before dispatch and reconcile actual receipts afterward.

### F14 — P1: `CLOSED_LIVE ≥ 5` is an arbitrary count target that invites easy-loop selection

L6 and scoreboard criterion 2 define success as at least five of thirteen loops closed against a live runtime DB (`HARNESS_LOOP_GRAPH_HUMMING_SPEC_2026-08-01.md:262-276`, `:503-522`). The canonical campaign currently requires promotion one loop at a time against declared owner criteria; it does not authorize substituting an aggregate count for those criteria (`CYBERNETIC_LOOP_MAP.md:70-107`).

A count target encourages closing whichever loops are easiest rather than the dependency-critical trunk. Replace it with named milestones:

1. Loop 1's existing closure campaign and host-bound proof;
2. one memory/context loop with real external work and later served-context consumption;
3. one verification loop whose verdict changes later routing or admission;
4. one event loop with durable delivery, consumer acknowledgement, and backpressure;
5. any further loop only after its owner criterion is named in the plan.

The overall spec may use these as milestones, not as a universal terminal condition or production-readiness claim.

### F15 — P1: E2 must default to bounded triage/proposal, not automatic self-improvement execution

E2 routes `GAUNTLET_REGRESSION` directly into a targeted self-improvement cycle (`HARNESS_LOOP_GRAPH_HUMMING_SPEC_2026-08-01.md:333-348`). A regression signal can be noisy, duplicated, stale, maliciously induced, or caused by the evaluator rather than the producer.

The first live edge should be:

`regression → deduplicated incident → diagnosis/proposal → deterministic reproduction → human or existing promotion authority`

not:

`regression → mutation loop`.

Add event identity, cooldown, deduplication, causal component attribution, immutable reproduction, budget reservation, and propose-only default. One Wire remains necessary but is not a general authorization token for every self-improvement action.

### F16 — P1: E3 is operationally under-specified and is not yet an event-driven reviewer

E3 proposes a hosted `claude -p --max-turns 8` workflow-dispatch reviewer (`HARNESS_LOOP_GRAPH_HUMMING_SPEC_2026-08-01.md:349-371`). Current merge-control code constructs local `claude` or `codex` commands and strips the Anthropic API key by default unless explicitly configured (`scripts/runtime/pr_merge_control.py:686-766`). A hosted GitHub runner does not thereby acquire the CLI binary, authentication, model entitlement, stable output contract, or receipt transport.

`workflow_dispatch` is also manually triggered, so it does not by itself solve the article's event-driven-loop requirement.

Specify the executable service boundary, authentication owner, secret scope, timeout, concurrency, deduplication, kill-switch behavior, receipt schema, commit pin, and event trigger before counting this item.

### F17 — P1: governance routing is honest in prose but not yet executable

V1 correctly adds no new track, preserves BR-id reference hygiene, and marks many surfaces unowned (`HARNESS_LOOP_GRAPH_HUMMING_SPEC_2026-08-01.md:8-18`, `:104-196`). Those are strengths.

However, a spec that is not itself adopted into exact `next_items`, packets, or owner decisions cannot coordinate P0–P3. Several items cross partially owned surfaces while naming only a nearest track. For example L1 joins loop-closure evidence to a Titanium-owned runtime file; G2 joins graph and arena surfaces; H2/H4 touch merge-critical unowned gates; E2 joins loop and safety surfaces.

Before implementation, add an adoption table with:

- exact changed-file globs;
- exact owning track for every file;
- required cross-track acknowledgement;
- work-packet requirement and baseline;
- merge-risk tier;
- operator-only decisions;
- conflicts with open PRs;
- whether the item is an existing track next-item or waits unadmitted.

“No new track” is good portfolio discipline only if the work is actually admitted by the existing owners.

## 3. Workstream dispositions

| Item | Disposition | Required correction |
|---|---|---|
| H1 PreToolUse | `REQUEST_CHANGES` | Harden fail-open/error and denial-receipt behavior before installation; keep it seat-specific, not the universal harness. |
| H2 semantic gate | `REQUEST_CHANGES` | Typed deterministic capabilities/provenance first; judge deny/abstain only, never grant. |
| H3 shell policy | `SUPPORTED_WITH_FINDINGS` | One policy owner, canonical digest, both consumers plus sabotage parity tests. |
| H4 kernel bridge | `PARTIAL` | “Degrade to current behavior” is shadow/advisory, not enforced; scope and fail-closed promotion must be explicit. |
| H5 context playbooks | `REQUEST_CHANGES` | Replace size non-shrinkage with held-out utility, provenance, contradiction, cost, and ablation metrics. |
| H6 sandbox | `REQUEST_CHANGES` | rlimits for resources; OS/container boundary for networking; receipts name isolation tier. |
| L1 StrategyReinforcer | `REQUEST_CHANGES` | Move after provenance harness; canary plus causal/ablation closure proof, not grep. |
| L2 judge + GEPA | `REQUEST_CHANGES` | Separate producer/evaluator epochs and data; immutable holdout; calibrated probability semantics. |
| L3 supervisor actuator | `SUPPORTED_WITH_FINDINGS` | Typed observation/authorization/actuator roles, expiry, kill path, negative controls. |
| L4 earned acceptance | `SUPPORTED` | Seeded empty-success negative control is the right proof shape. |
| L5 loop bounds | `SUPPORTED_WITH_FINDINGS` | Cycle/time cap now; cost only after authoritative hierarchical accounting. |
| L6 live closure | `REQUEST_CHANGES` | Named dependency-critical owner criteria, not aggregate five-of-thirteen target. |
| L7 orphaned verification | `PARTIAL` | Wire only behind existing safety and promotion boundaries; prove real callers and result consumption. |
| G1 DAG honesty | `SUPPORTED` | Cycle fail and atomic checkpoint are bounded honesty fixes. |
| G2 topology execution | `REQUEST_CHANGES` | Compile to neutral DharmaGraph; differential shadow before live flag; do not crown legacy DAG. |
| G3 gauntlet ascent | `SUPPORTED_WITH_FINDINGS` | Score increase is evidence only if the frozen rubric and judge custody remain independent. |
| G4 agents as nodes | `SUPPORTED_WITH_FINDINGS` | Mock test is component proof; add shadow production seam, durable identity, budget, and effect fencing. |
| G5 HITL | `SUPPORTED` | One protocol with default reject and durable request/response identity is appropriate. |
| E1 cron unification | `SUPPORTED` | One authority plus drift checker and durable schedule receipts. |
| E2 regression consumer | `REQUEST_CHANGES` | Default to incident/diagnosis/proposal, with dedup/cooldown/reproduction before mutation. |
| E3 hosted reviewer | `REQUEST_CHANGES` | Define executable/auth/receipt service and automatic trigger; workflow-dispatch alone is not event-driven closure. |
| E4 NATS afferents | `SUPPORTED_WITH_FINDINGS` | Host evidence, durable consumer acknowledgement, dedup, backpressure, no prose liveness. |
| R1–R7 | `SUPPORTED_AS_CANDIDATES` | Keep arena/chamber/gauntlet-only admission; none directly authorizes live mutation or evaluator promotion. |

## 4. Research review

### 4.1 Sources V1 reads substantially correctly

- **GEPA** supports reflective prompt evolution against explicit feedback and reports strong sample efficiency versus GRPO and MIPROv2; it does not by itself validate self-rewriting graders (arXiv:2507.19457).
- **ACE** supports structured, incremental context playbooks and identifies context collapse; it does not support monotonic playbook byte or key growth (arXiv:2510.04618).
- **CaMeL** strongly supports deterministic control/data-flow separation and capabilities outside the model; this argues against making an LLM judge the positive authorization boundary (arXiv:2503.18813).
- **DGM, HGM, Red Queen, and Group-Evolving Agents** are relevant candidate generators for self-improvement and lineage analysis, but their inclusion does not relax evaluation custody, One Wire, or human promotion authority (arXiv:2505.22954, 2510.21614, 2606.26294, 2602.04837).
- **MAST** is a useful failure taxonomy for post-run classification, but classification accuracy and actionability need an independently labeled validation set (arXiv:2503.13657).
- **RUVER-BENCH** supports V1's caution that long-context rubric judges remain noisy; deterministic task outcomes must remain primary where available (arXiv:2606.29920).

### 4.2 Missing or underweighted work

The following sources are more directly relevant to the structural gaps than several of V1's distant self-improvement papers:

1. **ETAS: Effect-Typed Agent Systems** (arXiv:2607.17780). This postdates most of V1's bibliography and directly motivates a typed action trace carrying effects, policies, approvals, and audit evidence. It is the closest research analogue to the constitutional action envelope proposed in §5.
2. **Composable Effect Handling for LLM Scripts** (arXiv:2507.22048; ACM LMPL 2025). Separating workflow logic from LLM, I/O, concurrency, and authorization effects is directly applicable to one effect dispatcher and live/record/replay/deny handlers.
3. **Agent libOS** (arXiv:2606.03895). Explicit capabilities and runtime primitives are more relevant to harness authority than adding more prompt-level gates.
4. **HarnessX** (arXiv:2606.14249). A trace-driven harness foundry is directly relevant to V1's L4 ambition, but its candidates must pass independent, immutable evaluations before promotion.
5. **Agent Lightning** (arXiv:2508.03680). Its decoupling of agent execution from training and hierarchical credit assignment addresses V1's missing causal-credit problem across parent loops, child agents, retries, and tools.
6. **Automated Design of Agentic Systems / Meta Agent Search** (arXiv:2408.08435). This is foundational prior work for R5 and should precede AFlow/MaAS/EvoAgentX in the lineage.
7. **AgentSentry** (arXiv:2602.22724). Counterfactual re-execution at tool-return boundaries is a stronger test for whether untrusted data changed a later action than caller grep or static consumer registration.
8. **AgentDyn** and **AutoDojo** (arXiv:2602.03117, 2606.15057). Adaptive injection evaluation should complement the fixed seeded corpus; static pattern success does not establish robust harness safety.
9. **SHADE-Arena**, **BashArena**, and constitutional black-box monitoring work (arXiv:2506.15740, 2512.15688, 2603.00829). These are directly relevant to highly privileged agents, sabotage detection, and the risk that optimized monitors overfit or saturate.
10. **Causal Past Logic for distributed agent runtimes** (arXiv:2605.20923). This is relevant to causal closure receipts and temporal claims across asynchronous consumers.

### 4.3 Research adoption rule that should replace the current generic rule

A research mechanism may enter a live path only after all of:

1. candidate generated in an isolated lane;
2. immutable evaluator version selected before candidate results are known;
3. hermetic replay plus adaptive/adversarial cases;
4. counterfactual or ablation evidence for the claimed causal benefit;
5. no access by the candidate to held-out labels, evaluator internals, or promotion credentials;
6. independent review and current-track ownership;
7. scoped canary with rollback;
8. no One Wire, chamber, safety-TCB, or human-authority relaxation.

## 5. Missing architecture: the constitutional action envelope

V1 adds many valuable wires but does not create the singular enforcement boundary the repository now lacks.

Every consequential effect should enter one typed envelope whose action class determines mandatory fields:

```text
ActionEnvelope
  execution_identity
    task_id / run_id / trace_id / claim_id / causation_id / parent_run_id
  graph_position
    graph_id / node_id / allowed_edge / attempt / checkpoint_id
  context_identity
    context_digest / prompt_version / memory_receipt_ids
  capability
    tool / effect_kind / resource / destination / allowed_domain
  provenance
    planner_source / argument_sources / trust_labels / external_content_ids
  risk_and_reversibility
    risk_class / rollback_plan / irreversible_boundary
  authority
    warrant / lease / operator_approval / expiry / scope
  budget
    parent_reservation / child_reservation / currency / token ceiling
  idempotency
    side_effect_key / operation_hash / ownership_token
  verification
    deterministic_checks / evaluator_version / required_abstention_policy
  outcome
    result_digest / cost / error / rollback_status
  evidence
    prepared_receipt / committed_receipt / consumer_closeback
```

A read-only research call may require only identity, context, graph position, capability, and a receipt. A code apply, outbound communication, payment, deployment, credential operation, or merge must require the full applicable contract. Callers must not choose which controls to omit.

The envelope should pass through one effect dispatcher with live, record, replay, shadow, and deny handlers. This is where CaMeL-style capability separation, runtime warrants, reversibility, hierarchical budget reservations, idempotency, and transactional evidence become one constitution rather than optional adjacent organs.

## 6. Corrected execution order

### P0 — Constitutional harness before new autonomy

1. Define typed discipline-specific closure contracts and enforcement levels.
2. Define `ActionEnvelope` and a single scoped effect-dispatch seam.
3. H3: consolidate shell policy with a frozen policy digest and sabotage tests.
4. H1a: harden the PreToolUse hook; H1b installs it only after fail-closed and denial-receipt tests pass.
5. H2a: deterministic provenance/capability enforcement; no positive judge authority.
6. H6: resource limits plus an honest isolation-tier contract; require strong sandbox for untrusted work.
7. Add hierarchical parent/child budget reservation or prohibit aggregate-cost claims.

### P1 — Simplest bounded loop plus deterministic grader

1. L4: earned semantic acceptance with empty-success negative control.
2. L5: cycle and wall-clock bounds; receipt-grounded cost bounds only when authoritative.
3. L1: StrategyReinforcer in shadow/canary after H2a, with causal and ablation receipts.
4. L3: one typed, expiring pause actuator consuming an independent supervisor recommendation.
5. L7: one orphaned verifier wired behind existing promotion authority.

### P2 — Graph only where the path is already known

Implement a minimal production macrograph:

```text
ADMIT
  -> COMPILE_CONTEXT
  -> EXECUTE_AGENTIC_NODE
  -> VERIFY
  -> DECIDE
  -> AUTHORIZE_EFFECT
  -> COMMIT_EFFECT_AND_RECEIPT
  -> CONSUME_CLOSEBACK
  -> COMPLETE | RETRY | ESCALATE
```

Open-ended research, coding, and synthesis remain inside `EXECUTE_AGENTIC_NODE`. Approval, verification, external effect authorization, retry exhaustion, and completion are explicit edges.

Then:

1. G1 legacy honesty fixes;
2. neutral-DharmaGraph shadow seam and differential outcomes;
3. G5 one default-reject HITL protocol;
4. G4 agent-as-node adapter with durable identity and effect fencing;
5. G2 topology genomes compile to the neutral engine, not the legacy DAG;
6. G3 gauntlet ascent and scoped production promotion.

### P3 — Event and hill-climbing loops

1. E1 durable schedule authority and drift check;
2. E4 durable afferents with acknowledgement/backpressure;
3. E2 regression-to-incident/proposal, default propose-only;
4. E3 authenticated automatic reviewer service, not merely workflow-dispatch;
5. L2 judge canary with immutable labels and calibration;
6. GEPA/ACE/HarnessX/workflow-search candidates through separated evaluator epochs;
7. named `CLOSED_LIVE` promotions as each owner criterion passes;
8. only then consider evaluator evolution or broader self-improvement.

## 7. Non-charmable scoreboard replacements

| V1 criterion | Replacement |
|---|---|
| `rg` finds StrategyReinforcer caller | Executed live-canary receipt names strategy IDs and prompt digest; counterfactual run omitting strategy removes the decision delta; invalid strategy is rejected. |
| `CLOSED_LIVE >= 5` | Named owner-surface milestones, each with host binding, causal consumer receipt, negative control, and non-author review. |
| test says supervisor paused | Runtime actuator receipt plus loop tick proves pause honored, expiry/resume works, and observer cannot self-authorize. |
| every signal has registered consumer | Typed topic registry plus delivery receipt, consumer acknowledgement, no-op/failed-consumer negative control, and explicit observation-only topics. |
| gauntlet score increases | Frozen rubric, exact candidate SHA, judge custody, mutation/sabotage proof, and semantic row-level delta. |
| topology function has a caller | Shadow execution through neutral graph on representative genomes; semantic differential report; checkpoint/retry/idempotency proof. |
| Brier receipts exist | Probability forecasts on immutable independently labeled outcomes; Brier/ECE/coverage/abstention reported by version. |
| gate diff is monotonic | Frozen machine-readable policy manifest plus mutation tests that weaken each protected rule and prove the gate fails. |
| CI contract diff reviewed | Checker appears in a required context or is consumed by Merge Master; advisory status is reported as `CHECKED`, not `ENFORCED`. |

## 8. Merge conditions for PR #1186

PR #1186 should remain draft or receive `REQUEST_CHANGES` until the spec does all of the following:

1. Replace the universal humming predicates with typed harness/loop/graph/event contracts.
2. Redefine `ENFORCED` using explicit observed, checked, merge-blocking, and runtime-blocking levels.
3. Replace “USED” with causal consumption plus decision delta and negative control; preserve every loop's owner-specific live criterion.
4. Split H1 into hardening and installation; remove the false quarantine-receipt and fail-closed implications from the current hook.
5. Make H2 deterministic capabilities/provenance first and prohibit judge-granted authority.
6. Reorder phases so constitutional harness work precedes L1, L2, E2, E3, and G2.
7. Replace G2's legacy-DAG route with a neutral-DharmaGraph compiler and differential shadow admission.
8. Replace the aggregate `CLOSED_LIVE >= 5` terminal criterion with named dependency-critical milestones.
9. Replace every grep/existence/review-prose acceptance with executed, receipted, negative-control evidence.
10. Separate producer, rubric, and evaluator evolution by versioned epochs and immutable holdouts.
11. Add the constitutional action envelope/effect-dispatch boundary or explicitly mark it as the prerequisite campaign kernel for all consequential workstreams.
12. Add an exact surface-owner/adoption table before any item becomes executable.
13. Add the missing effect-system, capability-runtime, harness-evolution, credit-assignment, adaptive-security, and AI-control research listed in §4.2.

## 9. Confidence and limits

**Review confidence: 0.91.** The subject was read at its pinned SHA; current CI truth, merge-control semantics, hook implementation, topology compiler, legacy workflow bridge, and loop-closure claim boundary were checked against current main.

This review did not access the operator's live daemon database, provider secrets, GitHub branch-protection settings, or external runtime receipts. It therefore makes no new liveness, deployment, branch-protection, provider, or `CLOSED_LIVE` claim. Those remain host- and owner-bound by the existing governance contracts.

## Final disposition

**`REQUEST_CHANGES — PARTIAL (57/100)`**

V1 identifies the right disease—dead causal edges—and contains many high-value work items. The repair is to stop treating every layer as the same loop, make enforcement levels honest, establish one constitutional effect boundary, preserve independent monitors, migrate topology execution to the neutral graph rather than the legacy DAG, and move all compounding adaptation behind those foundations.
