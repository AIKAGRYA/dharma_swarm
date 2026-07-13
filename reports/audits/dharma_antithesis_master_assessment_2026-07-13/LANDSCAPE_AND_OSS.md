# Landscape and Open-Source Systems

**Original cutoff/access date:** 2026-07-13  
**Iterative extension:** MiroFish, OASIS, and telemetry/monitoring sources accessed 2026-07-14; the frozen Dharma baseline remains unchanged.  
**Inspection policy:** primary documentation plus pinned public source where available; vendor behavior remains reported unless executed. Temporary clones/build output stayed under `/private/tmp/dharma_antithesis_research_20260713/oss`, `/private/tmp/mirofish_primary`, `/private/tmp/oasis_primary`, and `/private/tmp/otel_genai` and are not part of this report.  
**Document role:** dated landscape report, not an endorsement or license opinion.

## 1. Discovery method, research systems, and category map

Discovery proceeded by problem class, then current primary documentation/papers, pinned public source and representative tests, customer engineering reports, and finally secondary market context. A candidate was promoted when it exposed a materially distinct proof boundary, a credible Dharma integration seam, or decisive counterevidence. Runtime/language mismatches and source-poor products were retained only as explicit watchlist or vendor-reported entries; README claims were not promoted to reproduced behavior.

The original cutoff is 2026-07-13. The 2026-07-14 iteration added social-world generation, agent-trajectory interchange, durable history replay, distributed telemetry, outlier analysis, service/network observability, and continuous profiling. Research saturation was not formally logged under the protocol's two-successive-search stop rule, so the result is a broad bounded landscape, not a claim that every private product or unpublished project was found.

No single candidate replaces the proposed Dharma core. The space is split across different proof boundaries:

```text
source-integrated deterministic simulation
  FoundationDB | TigerBeetle VOPR | MadSim | Turmoil

concurrency schedule exploration
  Loom | Shuttle | Hermit

explicit-state / formal models
  Stateright | TLA+/TLC | Apalache | Alloy | P

input/stateful property generation and fuzzing
  Hypothesis | QuickCheck | LibAFL | AFL++

real-cluster semantic fault testing
  Jepsen | lineage-driven fault injection

whole-container deterministic simulation
  Antithesis | emerging dhyve/Bedrock experiments

live chaos and cloud fault injection
  Gremlin | Steadybit | AWS FIS | Azure Chaos Studio

bounded record/replay and generated testing
  Meticulous | Replay.io | Diffblue

agent evaluation, observability, policy, simulation
  Agent Control/Galileo | Google Agent Evaluation | LangSmith
  Braintrust | Phoenix | Langfuse | Patronus | Credo AI

generative social worlds and intervention workbenches
  MiroFish | OASIS

telemetry and agent-trajectory interchange
  OpenTelemetry/OTLP | OpenInference | Harbor ATIF

operational trace analytics and anomaly comparison
  Grafana Tempo/TraceQL | Honeycomb BubbleUp | ClickStack Event Deltas

durable history replay and ambient witnesses
  Temporal | Hubble/Tetragon | Pyroscope

formal commercial verification
  TrustInSoft | Certora
```

The central analytical error is to compare these as if they answer one question. A hypervisor may replay an execution but lack a useful oracle. Jepsen may detect a semantic violation on a real cluster but not replay the exact schedule. Model checking may exhaust a finite abstraction that omits the production defect. An immutable trace is not a replayable execution. An LLM judge is not ground truth.

### Serious-candidate decision record

“Adoption not measured” is deliberate: repository activity, funding, and customer quotations are not interchangeable with an audited installed base.

| Candidate | Deployment and security boundary | Adoption evidence | Replay/minimization artifact | Known failure or limit | Dharma integration constraint |
|---|---|---|---|---|---|
| Antithesis | closed customer environment around containerized x86-64 workloads; security/assurance detail partly gated | named customer engineering reports and market reporting; exact installed base not audited | deterministic rerun/debug artifacts are public claims; explorer and minimization quality proprietary | one-vCPU guest model, closed core, unknown pricing/data assurances, no hands-on POC here | partner only after representative hermetic target and exportable-regression contract |
| FoundationDB Simulation | source-integrated into FDB, not a general deployable service; runs production logic inside its simulated world | mature production project and published engineering lineage; simulator adoption outside FDB not measured | seeds and traces reproduce modeled executions; general counterexample minimization not established publicly | product-specific C++ substrate and explicit world adapters | adapt controlled-world/site/fault principles, not code or runtime |
| TigerBeetle VOPR | source-integrated Zig simulator around TigerBeetle; no separate tenant/service boundary | active production project; VOPR external adoption not measured | seed/commit replay and state checkers; general minimization not established | application-specific storage/network/state model and Zig runtime | adapt invariant density, explicit fault sites, and state checking |
| Jepsen | operates real clusters and may require privileged nemesis access; test harness is outside the SUT | mature research/engineering lineage; this audit did not quantify deployments | durable operation history and semantic checker result; exact schedule replay/minimization absent | environment and scheduler remain nondeterministic; results can be `unknown` | adapt history/checker semantics; retain as real-cluster complement |
| Hypothesis | in-process Python test dependency; executes user test code under the test process's permissions | highly active package; downstream adoption not quantified here | persistent interesting examples and strong input/action shrinking | no scheduler, network, model, tool, or filesystem world control; stability depends on code/version | borrow now for scenario generation/shrinking inside `WorldV1` |
| Stateright + TLA+/TLC + Apalache | offline explicit/symbolic models, isolated from production unless a translation/refinement layer exists | established research/open-source tools; Dharma-specific use unmeasured | abstract action/counterexample traces; minimization varies and is not production replay | finite/model bounds and abstraction omissions can prove the wrong system | model only small ownership/checkpoint/authority protocols and require a tested refinement fixture |
| LibAFL | harness-defined native/process executor with observers, corpus, and objective; security follows harness isolation | active framework; Dharma applicability not measured | solution corpus, state restore, and harness-defined minimizers | controls only what the harness exposes; no automatic semantic oracle or distributed world | borrow executor/feedback/corpus architecture only after RFC-001 provides a safe harness |
| MiroFish/OASIS | Python/Vue workbench over live LLM and graph-memory services; OASIS supplies the social-platform environment | MiroFish has high public interest and OASIS has a research paper; installed base and prediction accuracy were not audited | MiroFish per-round action logs, generated reports, and post-run interviews; OASIS environment/action interfaces can support proposed intervention branches; no exact controlled-world replay or minimizer established | correlated pseudodiversity, live external dependencies, ordinary JSON state, stochastic recommendation/LLM behavior, no public calibrated forecast benchmark found in the pinned MiroFish tree | use only to generate stakeholder/scenario corpora; prefer Apache-2.0 OASIS interfaces over importing AGPL-3.0 MiroFish code |
| OpenTelemetry ecosystem | cross-process instrumentation and lossy export through SDK/OTLP/Collector into one selected backend | broad ecosystem; this assessment did not audit an installed Dharma deployment | spans, links, events, metrics, exemplars, queries, and profiles; telemetry retention/sampling are not replay | incoming context is forgeable; spans can be missing or sampled; status and scores lack Dharma property/authority semantics | project canonical receipts one-way into a pinned `dharma.*` semantic layer; never read telemetry back as promotion authority |

## 2. Highest-value open-source comparison

| System | Execution/determinism boundary | Fault/search strategy | Oracle and counterexample | Dharma applicability | Verdict |
|---|---|---|---|---|---|
| FoundationDB Simulation | production FDB code in one deterministic process; virtual cluster/time/network/disk/machines | seeded ensembles, workloads, Buggify faults | assertions/workload checks; seed and trace replay | strongest conceptual prior art; implementation is FDB-specific | adapt principles |
| TigerBeetle VOPR | production TigerBeetle code; clock/network/disk stubbed; seed + commit | packet loss/reorder/partition/replay, disk corruption, time acceleration | thousands of assertions and state checkers; exact seed replay | excellent invariant/fault/site precedent, Zig/product-specific | adapt principles |
| Jepsen | real clusters; scheduler/environment not deterministic | generators plus nemeses over network/process/storage/time | operation histories and semantic checkers; `true/false/unknown` | best semantic history/checker model and real-world complement | adapt semantics |
| Stateright | explicit finite actor/model transition system | BFS/DFS/on-demand/symmetry reductions | temporal/safety properties and concrete action path | good for small ownership/checkpoint/task protocols | model selectively |
| TLA+/TLC + Apalache | explicit or symbolic finite transition model | exhaustive/random TLC; bounded SMT in Apalache | invariant/deadlock/liveness counterexample trace; preserves unknown/bounds | high value after a small runtime contract exists | build small model |
| Hypothesis | generated values/action sequences; no scheduler/world control | stateful rules, targeting, persistent examples, shrinking | Python assertions/invariants; minimized persistent examples | best immediate Python dependency | borrow now |
| Shuttle | instrumented Rust threads/tasks and synchronization | randomized/PCT/DFS-like schedules, replay | panic/assertion/deadlock; schedules | strong schedule-testing precedent, poor Python fit; replay gaps disclosed | inspect/borrow concepts |
| Loom | Rust code rewritten to Loom primitives | bounded scheduling/memory-choice exploration | assertions and serialized search checkpoint | useful for Rust components only | optional for Rust |
| Turmoil | multiple Tokio hosts in one thread; seeded virtual network/fs/time | latency/drop/partition/crash/torn write | user assertions/tests; seed replay | excellent fault API precedent, runtime mismatch | do not depend |
| MadSim | deterministic Rust async/runtime ecosystem replacements | seeded schedule/network/time/failure simulation | application assertions and replay | powerful if code is built for it; Dharma is not | do not port runtime |
| P | actor/event language and controlled runtime | DFS/random/A*, state caching, monitors | safety/deadlock/liveness; choice/schedule replay | language/monitor precedent | model only |
| Alloy | bounded relational/temporal model | SAT/Kodkod finite scope | instance/counterexample | schema and authority constraints | secondary tool |
| LibAFL | harness-defined executor, observers, feedback, objective, corpus/state | extensible coverage/search/mutation/scheduling | objective solution corpus; state restore | best exploration architecture to borrow; possible later service | borrow architecture |
| AFL++ | instrumented/forkserver native processes | coverage-guided mutation/minimization | crash/hang/path input corpus | parser/protocol/native extension fuzzing | use at edges |
| Hermit | x86-64 Linux process syscall/time/RNG/thread control | seeded chaos/serialized threads | user oracle; seed/record-replay | useful reference, maintenance mode and incomplete ambient control | avoid dependency |
| dhyve | bare-metal FreeBSD/Intel single-vCPU VM; branch-count time, deterministic devices | snapshot/fork/replay tree; manual state/fault mutations | final register/RAM/device hashes; no general oracle/search found | closest new open Antithesis analog, too immature/specialized | watch/lab only |
| Bedrock | experimental single-vCPU Intel deterministic VM/COW fork | user-defined exploration above fork boundary | user-provided | instructive, host-danger warning and GPL | do not run/integrate |
| Molly/LDFI | causal lineage from concrete good runs | SAT/Z3 minimal message/crash cuts then rerun | pre/post success oracle; bounded exhaustion | valuable only after trustworthy lineage/oracle | reimplement paper later |

### Complementarity evidence

Current Jepsen source contains an Antithesis bridge that substitutes Antithesis-controlled RNG choices and converts composed Jepsen checkers into exploration assertions. This is primary evidence that deterministic execution and semantic history checking are complements, not substitutes: [Jepsen repository](https://github.com/jepsen-io/jepsen).

Hypothesis itself warns that derandomized stability depends on unchanged tests, Hypothesis version, and Python version. It is a generator/shrinker and persistent example engine, not a whole-world deterministic runtime: [Hypothesis documentation](https://hypothesis.readthedocs.io/).

The lineage-driven fault-injection insight is strong: use causal provenance from a successful execution to derive minimal failure combinations, then rerun them concretely. Its assurance remains bounded by the execution horizon, failure model, lineage completeness, and oracle. Use the [SIGMOD 2015 LDFI paper](https://people.ucsc.edu/~palvaro/molly.pdf) as prior art. The public Molly repository is stale, has no license grant, and an inspected verifier path appears to read `post` for both pre/post guards; do not copy it.

## 3. Pinned repository and license manifest

Activity and releases were checked on 2026-07-13. “License” is an engineering inventory, not legal advice; mixed/component licenses require counsel before redistribution.

| Repository | Pinned commit | Commit date | License at pin | Activity/maturity | Inspection/test result |
|---|---|---|---|---|---|
| [apple/foundationdb](https://github.com/apple/foundationdb) | `c8e36e0b0ae5fb9820a5a4f73fecfdabc543d49d` | 2026-07-12 | Apache-2.0 | mature, highly active | inspected simulator/fault/RNG source; no build (large C++ toolchain) |
| [tigerbeetle/tigerbeetle](https://github.com/tigerbeetle/tigerbeetle) | `97c7a8ef385270ebe0e1b75959d3d21d134629df` | 2026-07-10 | Apache-2.0 | active production project | inspected VOPR network/state checker; no Zig installed |
| [jepsen-io/jepsen](https://github.com/jepsen-io/jepsen) | `f89e6575cc32de801f92c2de08aabae09ae1164c` | 2026-07-03 | core EPL-1.0; some modules EPL-2.0/dual terms | active; v0.3.11 2026-03-10 | inspected checker/generator/Antithesis bridge; no Clojure runtime |
| [stateright/stateright](https://github.com/stateright/stateright) | `ab8c8be9341505e0f71edbe5dd88ed275bd976a4` | 2025-07-27 | MIT | mature but slower activity | `cargo test --lib`: **91 passed** |
| [awslabs/shuttle](https://github.com/awslabs/shuttle) | `c8a46d3965048df3207ec920dae066bc9c4d9d89` | 2026-06-16 | Apache-2.0 | active research/engineering | selected replay tests **2 passed**; 434-case package suite stopped after long exhaustive cases; ignored tests disclose broken schedule-emission replay path |
| [tokio-rs/turmoil](https://github.com/tokio-rs/turmoil) | `481407d3bea1498e2f8259280b41986f392272fa` | 2026-05-27 | MIT | active | `cargo test -p turmoil --lib`: **30 passed** |
| [madsim-rs/madsim](https://github.com/madsim-rs/madsim) | `519950efb4711464f300ed7edf2967ed62d5f502` | 2026-02-16 | Apache-2.0 | active | narrow library suite: **1 passed** |
| [tokio-rs/loom](https://github.com/tokio-rs/loom) | `948c8cc78b178ede6eeff3afc7d97f2f4ea08559` | 2026-02-20 | MIT | stable; v0.7.2 2025-08-12 | smoke test **1 passed**; source documents model limits |
| [HypothesisWorks/hypothesis](https://github.com/HypothesisWorks/hypothesis) | `23b4358de3a715e519d81c17a1c8d21908ad9154` | 2026-07-12 | MPL-2.0 | highly active; v6.156.6 | source inspected; local execution blocked by missing dependency/network fetch |
| [BurntSushi/quickcheck](https://github.com/BurntSushi/quickcheck) | `eb00091c62db13b350253a5e8109b8667364117a` | 2026-04-02 | MIT or Unlicense | active | library tests **69 passed** |
| [AFLplusplus/LibAFL](https://github.com/AFLplusplus/LibAFL) | `f749dbf8aa8092bcacea3a7142fa645afe16d5b4` | 2026-07-12 | Apache-2.0 or MIT | highly active | state-restore test **1 passed**; architecture inspected |
| [AFLplusplus/AFLplusplus](https://github.com/AFLplusplus/AFLplusplus) | `ad5304010ae3be9d5cdc1ba51b09e14169c5cb87` | 2026-07-12 | core AGPL-3.0; mixed components | highly active; v5.02c | source/metadata inspected, not built |
| [apalache-mc/apalache](https://github.com/apalache-mc/apalache) | `d9f0633ebd0d54cca134c7ac993a3a458aa451f6` | 2026-07-10 | Apache-2.0 | active; v0.58.3 | inspected; Java toolchain unavailable |
| [tlaplus/tlaplus](https://github.com/tlaplus/tlaplus) | `227f61b983d0203a06db8184da45aed421e8f1b8` | 2026-07-03 | MIT | mature; 1.8.0 prerelease | inspected; not run |
| [AlloyTools/org.alloytools.alloy](https://github.com/AlloyTools/org.alloytools.alloy) | `ed89fdb16c58aea17a55e312c44f99e31aa63ee1` | 2026-06-11 | root MIT statement; solver components vary | mature | inspected; not run |
| [p-org/P](https://github.com/p-org/P) | `857776015de5f2683f11945728a1dc57f4b74b33` | 2026-06-03 | MIT | active | inspected; .NET unavailable |
| [facebookexperimental/hermit](https://github.com/facebookexperimental/hermit) | `bad5003464f867a05234155580f49ec99b627252` | 2026-07-11 | BSD-3-Clause | README says maintenance mode/no active development | source inspected; no x86-64 Linux run |
| [pgraug/dhyve-src](https://github.com/pgraug/dhyve-src) | `66e0b1a1b6942096fb1d19563a4fbc218dbd8142` | 2026-06-20 | root BSD-2-Clause; embedded trees mixed | created 2026-06-05; no release | user-space `dhv` workspace **35 passed**; no bare-metal run |
| [oss-garage/bedrock](https://github.com/oss-garage/bedrock) | `e2bede4f007f122cc561bb28d84db4f6535d4cc0` | 2026-07-02 | GPL-2.0 | experimental; no release | VMX library **135 passed, 1 platform-specific failure** on Darwin arm64; no hypervisor run |
| [palvaro/molly](https://github.com/palvaro/molly) | `a3a6d7950814e1154253357a03e7d64754c464b8` | 2018-11-04 | **no license file found** | stale since 2018 | source inspected; apparent verifier defect; do not reuse code |
| [666ghj/MiroFish](https://github.com/666ghj/MiroFish) | `96096ea0ff42b1a30cbc41a1560b8c91090f9968` | 2026-05-25 | AGPL-3.0 | active public project; v0.1.2 2026-03-07 | workflow, simulation logs, report agent, state persistence, and test inventory inspected; not executed because it requires live LLM/Zep services |
| [camel-ai/oasis](https://github.com/camel-ai/oasis) | `7234ac32589499ffb493e053f36d4de82aec8f43` | 2026-07-10 | Apache-2.0 | active research/open-source substrate | environment/action/interview/recommendation surfaces and tests inspected; million-agent and social-validity claims not reproduced |
| [open-telemetry/semantic-conventions-genai](https://github.com/open-telemetry/semantic-conventions-genai) | `63f8200eee093730ce845d26ce2aafb621b0807e` | 2026-07-08 | Apache-2.0 | active but GenAI documents are marked Development and no release was published | current `gen_ai.provider.name`, agent/workflow fields, and schema status inspected; schema not executed |

### Build limitations

The host had Rust/Cargo and Go, but no Zig, working Java/Clojure/SBT, .NET, or bare-metal Intel/FreeBSD environment. No kernel module or hypervisor was loaded. Initial Cargo downloads failed under sandbox DNS, then were rerun with approved network access. Several repositories do not commit root lockfiles, so tests resolved current compatible dependencies in disposable clones; this is recorded rather than disguised as a hermetic build. The July 14 MiroFish/OASIS/telemetry extension was source-and-documentation inspection only; no live LLM, Zep, Kubernetes, eBPF, Collector, trace backend, or profiling service was started.

## 4. New/open deterministic hypervisor watchlist

### dhyve

The June 2026 [dhyve source](https://github.com/pgraug/dhyve-src) is the closest public architectural analog to Antithesis found in this audit. It builds on FreeBSD bhyve, uses retired-branch-count virtual time and exact branch fences, deterministic RNG/timers/I/O, one vCPU, Linux guest patches, snapshot/fork/replay paths, final state hashes, and a Director. Source inspection found manual memory/register mutation and fault scripts, but no automatic coverage-guided explorer or general semantic oracle. Bare-metal FreeBSD, Intel VMX, patched guest, age, and mixed component licensing make it a watchlist/lab artifact, not a dependency.

### Bedrock

Bedrock is an experimental Rust deterministic hypervisor with single-vCPU execution and copy-on-write forks. Its [official architecture post](https://brink.dev/blog/2026/06/25/bedrock-deterministic-hypervisor/) limits supported CPUs/kernels and explicitly de-prioritizes security; repository warnings include possible host freeze/hang/corruption. It is valuable prior art and unsafe as a Dharma integration target.

### Hermit

Hermit determinizes many x86-64 Linux process sources through syscall interception, serialized threads, seeded scheduling, performance counters, and replay. Its own README says external network responses and filesystem changes remain uncontrolled and that the project is in maintenance mode: [Hermit repository](https://github.com/facebookexperimental/hermit). It demonstrates why a boundary must be named, not why Dharma should embed it.

## 5. Commercial chaos/fault injection

All behavior in this section is vendor-reported; no product was executed.

| Product | Architecture and current evidence | Determinism/replay boundary | Dharma use and limit |
|---|---|---|---|
| Gremlin | SaaS control plane and outbound-polling agents target host/container/Kubernetes CPU, memory, disk, process, time, network, DNS; current release notes through June 2026 | reruns faults against a changed live world; no seeded schedule/state snapshot/minimizer | later live-canary layer; borrow blast radius, abort checks, audit logs; privileged agent risk. [Docs](https://www.gremlin.com/docs/fault-injection-experiments) |
| Steadybit | central platform, one agent per boundary, HTTP discovery/action extensions; immediate stop/rollback on control loss; extension kit MIT | live perturbation, no deterministic world | strongest fail-safe/extension precedent; adapt rollback and Discovery/Action/Event split. [Architecture](https://docs.steadybit.com/install-and-configure/install-agent/agent-architecture) |
| AWS FIS | templates specify targets/actions/order/IAM/reports and CloudWatch-alarm stop conditions | managed live AWS failures; stopped experiments do not replay a schedule | useful only for AWS deployment canaries; borrow IAM and stop-condition discipline. [Templates](https://docs.aws.amazon.com/fis/latest/userguide/experiment-templates.html) |
| Azure Chaos Studio | service-direct and VM-agent faults in steps/parallel branches; scenario reports; workspace/scenario surfaces in preview | managed live Azure failures | run/config/RBAC precedent; preview/cloud lock-in. [Overview](https://learn.microsoft.com/en-us/azure/chaos-studio/chaos-studio-overview) |

These should sit outside the deterministic fixture lane. A chaos-run receipt is evidence that an experiment occurred, not that it can be exactly replayed or that its invariant coverage was complete.

## 6. Record/replay and autonomous test generation

| Product | What it does | Evidence boundary and relevance |
|---|---|---|
| Meticulous | records browser sessions, selects a corpus, replays base/head while stubbing XHR/fetch/WebSocket, storage, cookies, time, timers, scheduling | strongest commercial bounded-replay analogy; browser/session limited, backend mocked, privacy-sensitive. Adapt explicit capture boundary. [Docs](https://app.meticulous.ai/docs) |
| Replay.io / Replay QA | records environmental inputs/nondeterminism for browser re-execution; current QA explores journeys and uses evidence plus a judge model | “effective” application-level determinism, not general distributed search; public QA repo lacks explicit license. Adapt immutable causal artifact, not product dependency. [How Replay Works](https://www.replay.io/blog/how-replay-works) |
| Diffblue Cover | compiles/inspects Java/Kotlin bytecode, generates and validates regression tests in IDE/CLI/CI | coverage preserves observed behavior, not intended semantics; useful isolation/review/rollback precedent; language mismatch. [Overview](https://cover-docs.diffblue.com/get-started/what-is-diffblue-cover) |
| TrustInSoft Analyzer | abstract interpretation/formal analysis of configured C/C++/Rust entry points/properties | exhaustive only within modeled semantics/entry points/environment; useful precedent for scope-carrying proof. [Soundness](https://www.trust-in-soft.com/solutions/by-goals/soundness) |
| Certora Prover | code plus CVL properties -> SMT proof or concrete counterexample | strongest property-first commercial discipline; smart-contract/language mismatch. [Docs](https://docs.certora.com/en/latest/) |

## 7. Adjacent and emerging agent evaluation, simulation, observability, and policy

### Highest-signal candidates

| Candidate | Current architecture/status | What Dharma should adapt | What it does not prove |
|---|---|---|---|
| [Agent Control / Galileo](https://github.com/agentcontrol/agent-control) | Apache-2.0 `Scope + Condition + Action`; selectors/evaluators at pre/post tool/LLM hooks; `Deny > Steer > Observe`; pin `83188b62c63e2b4ff9ada87048fd99605184ee5a`, 2026-07-08 | typed hook/policy separation and effect-class-specific fail behavior | no deterministic world, epistemic modality, snapshot or replay; an older Galileo timeout page stated that timed-out metrics could leave dependent rules untriggered, but direct final validation returned HTTP 404, so this is historical counterevidence rather than a claim about current behavior |
| [Google Gemini Enterprise Agent Platform evaluation](https://docs.cloud.google.com/gemini-enterprise-agent-platform/optimize/evaluation/evaluate-simulated) | pre-GA; immutable agent-version snapshot; generated eval case with hidden conversation plan; simulated user; tool interceptors for data/503/latency; immutable trace and raters; docs updated 2026-07-10 | immutable agent/eval-case versioning and environment/tool interceptor | LLM-generated user/world/judge adds stochastic correlated error; trace immutability is not replay |
| [Patronus Generative Simulators](https://www.patronus.ai/blog/introducing-generative-simulators) / DWM | research/preview: LLM-generated tasks, tools, rewards, rollouts; DWM preview announced 2026-06-25 | watch capability-based curriculum/world ideas | no demonstrated reusable infrastructure; generated world/reward/oversight can share failure modes |
| [Phoenix](https://github.com/Arize-ai/phoenix) | OpenTelemetry/OpenInference traces, evaluations, datasets/experiments, ATIF trajectory import; Elastic License 2.0; pin `06bbbe9a07b578f96da0882cb3ee4d2490f1bd30` 2026-07-13 | interoperability schemas, deterministic/idempotent span IDs | idempotent trace upload does not mean deterministic execution; ELv2 constraints |
| [Langfuse](https://github.com/langfuse/langfuse) | OTEL traces, prompts, evaluations, datasets; self-hostable open-core; core MIT plus enterprise directories; pin `32299eff8ea498b2efbd2e9d3a61396a4766e122` | low-friction observability UI/schema if needed | traces/scores do not replay a world; mixed license and sensitive storage |
| [LangSmith](https://docs.langchain.com/langsmith/evaluation) | traces, production/curated/synthetic datasets, offline/online evaluation; proprietary platform, MIT SDK | dataset-to-experiment feedback lifecycle | LLM judgments and traces are not proof/replay; self-hosting is operationally heavy |
| [Braintrust](https://www.braintrust.dev/docs/evaluate) | dataset + task + score; immutable experiments; remote/cloud execution; Apache-2.0 SDK | honest ground-truth caveat and immutable experiment record | no scheduler/world control; split managed/self-hosted sovereignty |
| [Credo AI](https://www.credo.ai/product) | proprietary registry/cards/control-library/governance knowledge graph claims; GAIA first roadmap release May 2026 | governance taxonomy/market signal | public runtime-enforcement maturity unresolved |

Agent observability products can help store and inspect evidence, but their records must remain projections over a canonical local trace. LLM graders should be `reported` or `observed` inputs with calibration data, never automatic proof authority.

### MiroFish and OASIS: what transfers, and what does not

At pinned commit `96096ea0ff42b1a30cbc41a1560b8c91090f9968`, [MiroFish](https://github.com/666ghj/MiroFish) implements a legible end-to-end workbench:

```text
seed documents
  -> LLM ontology + Zep knowledge graph
  -> LLM-generated personas and simulation configuration
  -> OASIS Twitter/Reddit environment
  -> per-round action logs
  -> ReportAgent synthesis
  -> post-run agent/report interviews
```

That is genuinely useful prior art for scenario construction. The MiroFish pieces to adapt are the seed-to-world pipeline, environment/platform adapters, per-round action stream, and human-facing ability to inspect or interview a simulated world. The lower-level [OASIS](https://github.com/camel-ai/oasis) substrate is the better reuse candidate: it is Apache-2.0, exposes an environment/action interface, recommendation systems, interviews, and platform extension points that can support Dharma-designed intervention branches. Its [paper](https://arxiv.org/abs/2411.11581) reports simulations up to one million users and reproductions of several social phenomena; those results and their external validity were not reproduced here.

MiroFish is not a proof or telemetry system. Its platform logs record round, wall-clock timestamp, agent, action, arguments, result, and success, while completion is inferred from a `simulation_end` record. The inspected records do not bind causal parents, exact world/model/prompt/config digests, authenticated authority, property activation, or replay identity. State is written as ordinary JSON; live LLM/Zep calls and unbound randomness sit outside a controlled replay boundary. The same model family can help generate ontology, personas, configuration, actions, and report, so thousands of agents are correlated samples—not thousands of independent witnesses.

The disposition is therefore:

- **adapt now:** the MiroFish world-workbench UX and stakeholder/persona generation, plus Dharma-designed intervention branches over an OASIS-style environment interface;
- **use only as:** `ScenarioCorpus` with `origin_kind="simulated"`, scoped to its seed/generator manifest; this is a source-kind tag, not an evidence-ledger modality;
- **do not copy without counsel:** MiroFish implementation code, because the pinned repository is AGPL-3.0;
- **do not permit:** a MiroFish report, agent vote, or apparent emergence to satisfy an operational promotion gate;
- **forecasting gate:** frozen historical cutoffs, preregistered Brier/log score, real-data and simple/single-agent baselines, repeated seeds, model-family diversity, and sensitivity analysis over personas, prompts, graph construction, and recommendation algorithm. Until it beats those baselines on holdout events, call it an exploratory hypothesis generator.

### Telemetry and monitoring frontier: a five-plane separation

The strongest transferable pattern is not one vendor stack. It is a separation of planes:

```text
1. canonical execution history   Dharma owner records, receipts, ReplayBundleV1
2. telemetry projection          OpenTelemetry/OTLP + pinned dharma.* fields
3. evaluation ledger             datasets, trials, scorers, baselines, lineage
4. operational analysis          TraceQL, cohort deltas, SLOs, alerts, profiles
5. promotion authority           proposition-specific evaluator capability
```

Planes 2–4 make evidence inspectable; none may mint authority for plane 5.

| System/pattern | What to borrow | Hard boundary |
|---|---|---|
| [OpenTelemetry](https://opentelemetry.io/docs/specs/otel/overview/) + [Collector](https://opentelemetry.io/docs/collector/) | OTLP transport; resources and instrumentation scope; span events; parent/child for synchronous causality; span links for fork/join, prerequisites, `replay_of`, and `verification_of`; redaction/transform/export membrane | OTel is a cross-cutting observability API, not a canonical event store. Incoming trace context/baggage is correlation data, never authority. Collector/export failure must not change runtime truth. |
| [OpenTelemetry GenAI](https://github.com/open-telemetry/semantic-conventions-genai) + [OpenInference](https://github.com/Arize-ai/openinference) | provider/model/agent/workflow/tool vocabulary and broad agent-framework instrumentation; pin a local adapter version | GenAI conventions are still Development. Generic evaluation fields omit Dharma's activated property, exact manifest scope, proposition, and evaluator capability. |
| [Harbor ATIF](https://github.com/harbor-framework/harbor/blob/16a510cecbda385d9d98b50d5096d7c36378f95a/rfcs/0001-trajectory-format.md) | portable ordered agent/user/tool/observation trajectory, costs, multi-agent references, context-management markers | interaction completeness is not causal completeness or controlled-world replay; timestamps and most integrity fields are optional, and `extra` is not typed authority. Export ATIF from canonical history, never ingest it as proof. |
| [Temporal history](https://github.com/temporalio/temporal/blob/710be0d0e30cf578df910235c048e474768a5565/docs/architecture/history-service.md) | keep append-only workflow history distinct from mutable visibility indexes; replay deterministic orchestration decisions; isolate nondeterministic external calls as recorded activities; replay history corpus in CI | durable history replay is not semantic property proof, schedule exploration, or safe retry of non-idempotent effects. Do not adopt Temporal merely to obtain a UI. |
| [Honeycomb BubbleUp](https://docs.honeycomb.io/investigate/analyze/identify-outliers/) / [ClickStack Event Deltas](https://clickhouse.com/blog/faster-root-cause-for-slow-traces-with-clickstack-event-deltas) | compare a failed/rejected foreground cohort with scope-matched passing baseline across every useful dimension; rank discriminating fields | output is a `HypothesisCandidate`, never a claim, verifier result, remediation command, or promotion input. |
| [Tempo TraceQL](https://grafana.com/docs/tempo/latest/traceql/) | structural trace queries, trace-derived RED metrics, service graphs, and exemplars that jump from an aggregate to a contributing trace/receipt | sampled or incomplete spans can skew topology and metrics. A trace tree is neither execution replay nor authority. Use one backend only if operations already warrant it. |
| [Google SRE burn-rate alerts](https://sre.google/workbook/alerting-on-slos/) | multi-window alerts and synthetic canaries for settlement, idempotency, invalid-promotion rejection, later-cycle consumption, and export loss | SLO compliance is operational health, not truth of an individual claim. Alerts create investigation tasks, not automatic promotion/remediation. |
| [Hubble](https://docs.cilium.io/en/stable/observability/hubble/index.html) and [Tetragon](https://tetragon.io/docs/overview/) | later Linux/Kubernetes independent witness for network flows, unexpected egress, process/file/syscall activity, and replay-lab boundary enforcement; [Hubble metrics](https://docs.cilium.io/en/stable/observability/metrics/) expose lost-event counters | privileged, platform-specific, operationally heavy, and semantically blind. Lost or absent ambient events cannot prove non-occurrence. |
| [Pyroscope span profiles](https://grafana.com/docs/pyroscope/latest/configure-client/trace-span-profiles/) | later trace-to-profile drill-down for CPU, allocation, mutex, and blocking hotspots | profiling answers where resources were consumed, not whether a claim or effect was correct. |

Sampling rule: canonical receipts, settlement, promotion attempts, verifier results, replay bundles, and all five property-result states are retained at 100%. Tail/dynamic sampling is allowed only for remote operational projections. `sampled` is declared at projection-run/trace/query scope from the pinned sampler decision and covered owner-sequence range; `lost` is declared there from unexpected owner-sequence gaps, cursor lag, or terminal export failure because a missing span cannot report its own loss. [OpenTelemetry's agent-to-gateway guidance](https://opentelemetry.io/docs/collector/deploy/other/agent-to-gateway/) also makes clear that trace-consistent tail sampling requires all spans for a trace to reach the same decision point.

## 8. Dharma relevance and integration constraints

| Need | First choice | Why | Integration cost | License/IP risk |
|---|---|---|---:|---|
| Python action generation/shrinking | Hypothesis | native, mature state machines and example DB | low | MPL-2.0 dependency review; ordinary use acceptable subject to counsel |
| semantic operation history/checkers | adapt Jepsen concepts | tri-state result and nemesis/history discipline | medium | reimplement interfaces; do not copy incompatible code casually |
| graph/effect/authority protocol model | TLA+ then Apalache | small explicit model plus bounded symbolic CI | medium | MIT/Apache-2.0 |
| concurrency in Rust adapters | Loom/Shuttle | schedule/memory exploration | medium | MIT/Apache-2.0 |
| network/fs simulation for new Rust service | Turmoil or MadSim | strong controlled worlds | high unless new Rust subsystem already justified | MIT/Apache-2.0 |
| parser/protocol fuzzing | AFL++/LibAFL | mature coverage and corpus machinery | medium-high | AGPL core for AFL++; LibAFL permissive |
| local telemetry projection | OTel/OTLP plus pinned `dharma.*` and OpenInference fields | existing Dharma receipt adapter already points here; keeps backend optional | low-medium | stable OTel core, evolving GenAI conventions; schema pin required |
| portable agent trajectory | ATIF export from canonical event/receipt history | useful for offline eval, visualization, and training interchange | low | open RFC, but optional/extensible fields cannot carry proof authority |
| operational trace query/UI | one of existing ClickHouse/ClickStack, Tempo/Grafana, or managed Honeycomb | high-cardinality cohort comparison and exemplar drill-down | medium-high | choose one; SaaS privacy or self-hosted operational burden |
| generative stakeholder/scenario corpus | adapt MiroFish concepts over OASIS interfaces | best new source of human-world interventions and interviewable personas | medium | prefer Apache-2.0 OASIS; MiroFish AGPL; no prediction authority |
| workflow-history replay | adapt Temporal's history/visibility/activity distinction | strong precedent for durable deterministic orchestration and CI history replay | medium | do not import a new orchestrator to solve observability |
| ambient network/process witness | Hubble/Tetragon after a Linux/Kubernetes target exists | catches instrumentation escapes and proves the tripwire itself is alive | high | privileged eBPF and incomplete/lost-event boundary |
| trace-linked continuous profiling | Pyroscope or OTel Profiles only after causal correctness | performance triage linked to exact execution scope | medium-high | statistical signal, not correctness evidence |
| tool/LLM authority hooks | inspect/adapt Agent Control ideas | explicit hook and priority model | medium | Apache-2.0 source; broader Galileo proprietary |
| real infrastructure chaos | Steadybit/Gremlin/cloud native | live canary after local proof | medium-high | commercial and privileged-agent review |
| whole-container exploration | Antithesis POC | strongest mature general platform found | high | proprietary, data/economics unknown |
| custom deterministic hypervisor | none | not Dharma's current bottleneck | extreme | deep platform and component license risk |

## 9. Recommended composition

```text
Hypothesis state machine
  -> Dharma WorldV1 choices and fault adapters
  -> Jepsen-style invoke/ok/fail/info causal history
  -> tri-state/non-vacuous semantic properties
  -> minimized persistent replay bundle
  -> exact fresh-process verifier

small parallel TLA+ model
  -> TLC/Apalache counterexample
  -> translated executable fixture

later:
  causal lineage -> bounded LDFI candidate generation
  hermetic container target -> Antithesis POC
  attested live deployment -> Steadybit/Gremlin/cloud chaos canary

orthogonal scenario lane:
  seed corpus -> OASIS-style world/personas/interventions
              -> simulated ScenarioCorpus only
              -> hindcast calibration before any forecast use

one-way observability membrane:
  canonical receipt / ReplayBundleV1 (100%, append-only)
    -> pinned DharmaTelemetryProjectionV1
    -> OTel Collector (redact, transform, export)
    -> exactly one query backend
    -> cohort delta / alert emits HypothesisCandidate
    -> exact replay + verifier required before promotion
```

This composition respects the hard boundary: **determinism is a repeatability mechanism, search is a discovery mechanism, and an oracle gives the result meaning.** None can substitute for the other two.
