# Executive Verdict

## Scope and evidence freeze

**Assessment date:** 2026-07-13  
**Dharma baseline:** `origin/main` at `c14b950bc5009f2200d9425155010be508ead981`  
**Document role:** dated audit report. It is subordinate to `CLAUDE.md`, `docs/governance/ACTIVE_TRACK.yaml`, `docs/governance/SOVEREIGN_MANIFEST.md`, source code, tests, runtime owners, and external primary evidence. It does not replace canonical truth.

**Iterative extension:** 2026-07-14 research adds MiroFish/OASIS scenario-generation and observability/telemetry prior art. It does not move the frozen Dharma baseline or reinterpret later working-tree state as baseline evidence.

## Verdict

**Dharma Swarm is an unusually ambitious, integration-rich research and operations repository, but it is not a production-closed autonomous organism. DharmaGraph is a real deterministic graph kernel plus a production-wired durability/reconciliation seam, but it is not the organism's graph runtime. The system is partial: substantial engineering, strong local ideas, and many tests coexist with broken admission, false-green evaluation, duplicated execution paths, unsafe fail-open behavior, and zero production-live cybernetic-loop closures.**

This is not a verdict that “nothing works.” A focused DharmaGraph suite passed **188/188** tests on exact current main, its fresh parity gauntlet honestly returned **52.00/100, 34 gaps, NOT_FINISHED**, and its durable invoker/reconciler are genuinely wired into the Orchestrator and SwarmManager. The problem is the promotion boundary: scoped correctness is repeatedly narrated as system capability before production-path, concurrency, authority, and live-closure obligations are met.

Antithesis is the correct company. It has built a credible, active, technically differentiated deterministic simulation platform: a FreeBSD/bhyve-derived single-vCPU hypervisor controls a whole containerized deployment while a proprietary explorer searches executions and produces replay/debug artifacts. The strongest public efficacy evidence is the etcd team's 2025 campaign. The public record does **not** prove “100% deterministic,” universal automatic root cause, superiority to alternative testing under equal budgets, or coverage of true multicore weak-memory behavior. Its core is closed, pricing is undisclosed, and its search quality cannot be independently audited.

The strategic conclusion is narrow: **do not build an Antithesis clone and do not add another executor. Build a bounded replay laboratory around the existing DharmaGraph kernel and one real production dispatch seam, then consider an Antithesis proof of concept only after Dharma has a hermetic representative target.**

## 2026-07-14 iteration: MiroFish and observability

**MiroFish is useful as a scenario-workbench pattern, not as a telemetry system, deterministic simulator, forecast oracle, or source of independent consensus.** Its pinned workflow turns seed documents into an LLM-generated graph and personas, runs OASIS social actions, then synthesizes reports and interviews. Combined with Dharma-designed intervention branches, that can expand stakeholder rehearsal, adversarial narratives, and replay-lab scenario corpora. The generated agents remain correlated through shared source material, graph construction, prompts, model families, and platform dynamics. Every output must therefore keep `origin_kind="simulated"` as a provenance tag—not a sixth evidence modality; any forecasting claim must survive frozen-cutoff hindcasts, preregistered proper scoring, simple and single-agent baselines, repeated seeds, model-family diversity, sensitivity analysis, and holdout evaluation. Prefer the Apache-2.0 OASIS interfaces; do not import MiroFish's AGPL-3.0 code into a distributable component without explicit review.

**The observability opportunity is a membrane around Dharma's proof plane, not a replacement for it.** Preserve canonical owners, receipts, replay bundles, verifier results, and promotion decisions. Project them one way through a pinned `DharmaTelemetryProjectionV1` into OpenTelemetry/OTLP, then use exactly one backend for trace queries, cohort differencing, and SLOs. Operational analysis may emit a `HypothesisCandidate` or replay task; it cannot mint evaluator authority. Temporal-style event history, ATIF trajectory interchange, Honeycomb/ClickStack-style outlier comparison, Hubble/Tetragon ambient witnesses, and span-correlated profiles each answer a different question and must keep their completeness and authority limits explicit.

This extension does not outrank the original next move. The first telemetry slice should be a small adapter and golden fixture alongside RFC-001—not a platform deployment—and the scenario lane should remain isolated until its hindcast and licensing gates pass.

## Ten findings that matter

1. **Current main fails its mandated local admission command on the stock macOS toolchain.** On the host's GNU Make 3.81, `make onboard` fails at parse time with `Makefile:592: *** multiple target patterns. Stop.` The merge commit's GitHub “Onboarding admission parity” check was skipped. This is a demonstrated host-local admission/portability blocker, not cosmetic debt; because the repository does not declare a minimum GNU Make version, the evidence does not establish that newer-Make CI or release environments are blocked.
2. **The repository's own live-closure language is more truthful than much of its surrounding prose:** `HARNESS_PROVEN 11/13`, `CLOSED_LIVE 0/13`. A harness pass is not proof that a daemon consumed an owner-surface result on a later cycle.
3. **DharmaGraph does not own the production execution hot path.** No non-test production importer uses `GraphBuilder`, `CompiledGraph`, `GraphPersistenceKernel`, `GraphCheckpointStore`, or `GraphTelosBridge`. Production uses the durable-invoker/reconciler seams while `workflow.py`, topology compilation, loop checkpoints, and LangGraph-parity clones remain separate execution/persistence surfaces.
4. **The 52/100 parity number is an inventory, not readiness.** Importable shapes earn partial credit; application rows execute a clone instead of the neutral engine; some performance facets and completeness checks are unconditional. The stored semantic receipt does replay successfully on current source, but its “judge signature” is not authenticated authority.
5. **The neutral graph core has real strengths.** Deterministic bulk-synchronous scheduling, validate-before-commit channel writes, cycles/resume/fork surfaces, SQLite effect ownership, receipt chaining, and boot/tick reconciliation are coherent enough to preserve and harden. The 188-test focused suite is meaningful scoped evidence.
6. **Durability is not concurrency-safe.** Reproduced counterexamples lost one of two concurrent graph persistence writes, showed child checkpoint mutation aliasing the parent, and left an invalid pending-write journal permanently poisonous. “Exactly once” is only conditional effectively-once and deliberately fails open when its store is unavailable.
7. **Core Swarm state paths have reproduced correctness defects.** Cross-instance stigmergy decay loses a concurrent append; failed prerequisites can become dispatchable before failure propagation; SignalBus subscribers can mutate the queued event object; the full Organism is off by default in the canonical API launcher.
8. **Security boundaries are not production-grade.** Configured bearer authentication does not protect WebSockets; an unauthenticated socket received a chat snapshot in a deterministic probe. Separately, host process inspection revealed live credentials in Cursor process arguments. No secret values are retained here; the latter is a host operational exposure, not a proven committed-code defect.
9. **The “ML/evolution” layer outruns its evidence.** Shadow evolution clears the proposed diff, tests unchanged baseline code, converts success into proposal fitness, and can feed that value into later selection. Provider base URLs are resolved then discarded, and two logical diversity lanes can resolve to the same Claude Code backend. There is model routing and heuristic selection, but little evidence of generalizable online learning that improves external task outcomes.
10. **The external lesson is controlled worlds plus hard oracles—not more agent consensus.** FoundationDB, TigerBeetle VOPR, Stateright, Shuttle, Turmoil, MadSim, Jepsen, model checking, and property-based testing each cover different failure surfaces. No one tool makes unmodeled behavior disappear. Determinism without a realistic workload and activated invariant is only repeatable blindness.

## Strongest asset

The strongest asset is the combination of a usable graph/durability kernel and a repository culture that already has vocabulary for owner, projection, receipt, AMBER, and `CLOSED_NOT_PROD`. Those are the right raw materials for executable promotion gates. The next step is to make the evaluator enforce them instead of letting prose or a score perform the promotion.

## Most dangerous unsupported belief

**That a large test count, a replayable receipt, or 52 parity points means the swarm is deterministic, integrated, or production-safe.** The neutral scheduler is explicitly candidate/test-only; application parity still exercises a clone; important properties can earn credit without behavior; and the running daemon was observed from a dirty checkout hundreds of commits behind current main.

## Highest-leverage next move

**Fix the GNU Make 3.81 onboarding regression, then implement RFC-001: `WorldV1` plus `ReplayBundleV1` around one existing graph failure, requiring 100 fresh-process replays with identical semantic trace and property result before any new parity feature or production migration.**

That move is reversible, exercises current assets, attacks false-green evidence directly, and creates the prerequisite for a meaningful Antithesis POC.

In parallel, define the one-way telemetry projection over the existing receipt seam and prove that disabling or corrupting export changes no canonical state. Do not select a production observability backend until one real causal query earns it.

## What not to build

- A custom deterministic hypervisor.
- Another scheduler, orchestrator, checkpoint store, receipt substrate, or graph DSL.
- A whole-swarm rewrite onto DharmaGraph before conformance evidence exists.
- An LLM council that converts agreement or confidence into technical truth.
- A generated society that converts persona count, interviews, votes, or narrative realism into prediction or standing.
- A second canonical event/receipt store hidden inside an observability platform.
- A full Grafana/ClickHouse/Honeycomb stack before one retained causal query and an explicit operator owner exist.
- A roadmap optimized for “LangGraph 100/100.”
- Automatic retries for non-idempotent external effects whose outcome is ambiguous.
- An Antithesis integration before a hermetic x86-64 Linux target, data boundary, seeded-defect corpus, and economic kill criteria exist.

## Decision, confidence, and decisive unknowns

Continue DharmaGraph, but change its success function: from surface parity to **replayable failure discovery and one production-seam conformance slice**. Preserve the current kernel; stop expanding its surface until persistence races, authority forgery, non-vacuous properties, and exact fresh-process replay are closed.

Confidence is **high** for the reproduced local defects and scoped current-main test results, **medium-high** for the target-architecture decision and public Antithesis architecture, and **medium** for market status, proprietary capability, and economics. Decisive unknowns are a clean full-suite rebuild, cross-platform onboarding admission, an attested production-live closure, hands-on commercial comparator trials, and an Antithesis POC against a representative hermetic target.
