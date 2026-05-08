# Operating Company Kernel Vision

**Date:** 2026-05-07
**Status:** long-horizon vision map, not an implementation grant
**Subordinate to:** `docs/governance/BUILD_SESSION_ENTRYPOINT.md`, `docs/governance/SOVEREIGN_MANIFEST.md`, and `docs/governance/CANONICAL_DOC_STACK.md`

This document names the long-horizon architecture for Dharma Swarm as an
AI-native operating company kernel. It does not replace the active
operator-brief build track, and it does not authorize parallel substrates.
Every future implementation must enter through bounded WorkPackets and reuse
the existing organs where possible.

The vision is allowed to be ambitious. It is not allowed to be unverifiable.

---

## North Star

Dharma Swarm becomes a solo-operator AI company organism: it senses the world,
selects bounded work, ships artifacts, earns revenue, buys compute, trains or
evaluates specialist models from verified traces, and improves itself under
telic governance.

"Hungry" means measurable metabolism, not mythology:

- It consumes truth: repo state, market signals, customer feedback, cost data,
  failures, human judgments, and governance evidence.
- It turns truth into work: opportunities become WorkPackets, not ambient agent
  motion.
- It turns work into evidence: every run has source inputs, tests, gates,
  changed artifacts, and a report.
- It turns evidence into revenue: offers, audits, fixes, and customer signals
  are measured before scale claims.
- It turns revenue into compute: model spend, routing choices, and future GPU
  ownership are justified by a treasury, not desire.
- It turns compute into learning: traces become playbooks, routing policies,
  evals, and only eventually specialist models.

The core claim: Dharma should not merely coordinate agents. It should close the
business loop around agents so that the system can fund and improve the exact
capabilities that produce verified value.

---

## Core Loop

The operating company kernel is real only when this loop has durable state at
every edge:

```text
world/repo/market truth
-> OperatingFactBundle
-> Morning Cockpit
-> OpportunityEngine
-> WorkPacket
-> AgentOps
-> tests/gates/evidence
-> shipped artifact
-> revenue/customer signal
-> Human YDS + KaizenReview
-> budget/model allocation
-> Darwin proposals
-> next WorkPacket
```

The loop is closed when a completed artifact changes the next packet selection,
budget decision, routing policy, skill/playbook, or Darwin proposal. A dashboard
that only summarizes facts is not closure. A proposal generator that ignores
outcomes is not closure. A revenue note that cannot alter compute allocation is
not closure.

---

## Existing Organs To Reuse

These are current substrates or current declared fact surfaces. Later code must
attach to them before adding any new organ.

| Organ | Current surface | How the kernel should reuse it | Status |
|---|---|---|---|
| Operator Ground Truth | `dharma_swarm/operator_core/operating_facts.py` | Use `OperatingFactBundle`, `OrganBoundary`, source manifests, missing-source reporting, Human YDS, burn, and revenue facts as the first truth intake. | PARTIAL |
| Daily Operating Brief | `dharma_swarm/daily_operating_brief.py` | Reuse as the human-facing synthesis layer inside Morning Cockpit rather than creating another brief writer. | PARTIAL |
| AgentOps | `AgentOpsRunFact` and `agentops` organ boundary in `operating_facts.py` | Treat bounded repo execution reports as the only admissible autonomous-work evidence. Resolve branch-specific runner/script availability before scaling. | DECLARED/PARTIAL |
| KaizenReview | `KaizenReviewFact`, `dharma_swarm/kaizen_ops_local.py`, `dharma_swarm/kaizen_stats.py` | Consume completed AgentOps reports, extract waste/playbook candidates, and feed next-packet recommendations. | PARTIAL |
| Human YDS | `HumanQualityRatingFact`, `append_human_yds_rating()` | Preserve human quality ratings as authoritative; AI ratings are advisory only. | PARTIAL |
| RuntimeState | `dharma_swarm/runtime_state.py` | Keep live operational state in the existing runtime-state store rather than creating a new state memory. | PRESENT |
| DocOps | `docs/governance/*`, `scripts/system_map_populator.py`, `reports/system_map/latest.json` | Treat doc/system-map checks as truth inputs to Morning Cockpit when available; expose absence explicitly. | PARTIAL |
| DarwinEngine | `dharma_swarm/evolution.py` | Use for proposal/evolution pressure only after evidence and safety gates exist; do not bypass its shadow/autonomy locks by documentation. | PRESENT, APPLY BLOCKED |
| Fractal Rooms | Existing vision/spec references; verify concrete module path per branch before use. | Reuse as a room/work substrate only where the current branch has the module and tests. | BRANCH-DEPENDENT |
| Economic modules | `dharma_swarm/economic_engine.py`, `dharma_swarm/economic_agent.py`, `dharma_swarm/economic_spine.py` | Reuse for revenue, cost, and value accounting before inventing a new commercial ledger. | PARTIAL |

Status meanings:

- PRESENT: concrete module exists and can be imported or tested in this
  checkout.
- PARTIAL: fact shape or implementation exists, but closure or runtime coverage
  is unproven.
- DECLARED/PARTIAL: a contract exists, but the producer path must be verified
  on the active branch.
- BRANCH-DEPENDENT: do not claim presence without checking the worktree.

---

## Five Metabolisms

### 1. Truth Metabolism

Truth metabolism ingests reality and preserves source provenance.

Inputs:

- repo state: git status, tests, DocOps report, system map, broken register
- operating state: RuntimeState, latest AgentOps report, latest KaizenReview
- human truth: Human YDS, explicit operator notes and decisions
- market truth: customer conversations, pricing notes, demand signals
- cost truth: token spend, provider spend, local compute use, unpriced spans

Outputs:

- `OperatingFactBundle`
- source manifest with present/missing/optional inputs
- Daily Operating Brief sections
- missing-source failures for major absent producers

No truth source may be silently inferred. Missing inputs must appear as missing
inputs, not as empty success.

### 2. Work Metabolism

Work metabolism converts truth into bounded execution.

The only acceptable autonomous unit is `WorkPacket`: a typed task with scope,
owner, allowed files, expected evidence, gates, rollback story, and acceptance
criteria. Until a concrete `WorkPacket` type is implemented or confirmed in the
current branch, the name is a reserved interface and the packet shape must be
kept explicit in reports.

Work flow:

- Morning Cockpit selects next leverage point.
- `OpportunityEngine` proposes candidate WorkPackets.
- Human or policy approval picks one packet.
- AgentOps executes only within the packet.
- Tests, gates, and scope checks decide whether anything can be promoted.

### 3. Learning Metabolism

Learning metabolism turns completed work into better future behavior.

Minimum learning outputs:

- KaizenReview of every real AgentOps packet
- Human YDS rating for at least one completed artifact per week
- playbook update candidates promoted into `SkillLibrary`
- routing/cost notes from hard versus repetitive tasks
- Darwin proposals only from verified traces, never from vibes

Learning is not model training by default. Most useful learning should first be
playbooks, evals, routing rules, prompt changes, and task decomposition
patterns. Fine-tuning is later and must be evidence-backed.

### 4. Revenue Metabolism

Revenue metabolism turns capability into a commercial offer and measures market
contact.

First offer:

`AI Codebase Governance + AgentOps Audit`

The offer should produce a repo audit report, prioritized findings, bounded fix
packets, and before/after evidence. The first revenue loop can start with
operator-owned sales notes, but it must become a `RevenueLedger` or reuse an
existing economic module as a fact producer before claims of company viability.

Revenue is measured before scale. If no one pays, replies, books, renews,
refers, or changes behavior, the loop has no market truth.

### 5. Compute Metabolism

Compute metabolism allocates model and hardware spend by measured return.

Rules:

- Frontier models are for hard reasoning, synthesis, safety review, and tasks
  where failure is expensive.
- Open or local models are for repeated extraction, classification, formatting,
  retrieval, and cheap eval passes where quality is measured.
- Specialist models are trained only from verified traces with stable schemas,
  human or gate labels, and held-out evals.
- GPU ownership is forbidden as an identity claim. Revenue, utilization,
  queueing delay, provider cost, data sensitivity, and maintenance burden must
  be measured first.

`ComputeTreasury` is the future accounting surface for this. Until then, burn
reports and model-routing telemetry are the source of truth.

---

## Missing Organs

These names are reserved public interface names. They are not implemented by
this document.

| Missing organ | Responsibility | Existing substrate to reuse first | Minimum reality test |
|---|---|---|---|
| `OperatingCompanyKernel` | Compose the metabolisms into one operating loop. | `OperatingFactBundle`, RuntimeState, Daily Operating Brief, economic modules. | One run changes the next WorkPacket from prior evidence. |
| `MorningCockpit` | Daily source manifest, operating brief, missing-source failure, next-move recommendation. | `build_operating_fact_bundle()`, `build_daily_operating_brief()`, DocOps/system map. | `make morning-cockpit` writes manifest and fails visibly on missing major sources. |
| `OpportunityEngine` | Convert truth and market signals into ranked WorkPacket candidates. | Operator facts, economic modules, existing opportunity/dispatcher code if present. | At least one candidate becomes a real packet and its outcome feeds back. |
| `EvidenceLedger` | Durable evidence index for runs, gates, tests, artifacts, customer signals, and cost. | WitnessLog/Ontology where already used, reports, RuntimeState. | A shipped artifact can be traced to inputs, gates, and later customer signal. |
| `RevenueLedger` | Commercial fact producer for offers, invoices, replies, paid work, and customer outcomes. | EconomicEngine/EconomicLedger/RevenueSignalFact. | One offer or audit has durable revenue/customer-status rows. |
| `ComputeTreasury` | Cost, budget, utilization, model allocation, and GPU lease/own decisions. | BurnReportFact, model routing, economic modules. | Model spend can be attributed to packet, artifact, and outcome. |
| `ModelFoundry` | Eval, route, fine-tune, and maintain specialist models. | Provider/model routing, QLoRA/LoRA/DPO lanes, verified traces. | A specialist beats baseline on held-out eval and has rollback. |
| `SkillLibrary` | Promote recurring successful work patterns into reusable playbooks. | KaizenReview, Human YDS, existing `docs/SKILL_LIBRARY.md` if kept canonical. | One promoted skill is reused in a later packet and improves the run. |
| `SafetyKernel` | Governance wrapper for autonomy, security, safety evals, and release gates. | Telos gates, kernel, OWASP/NIST/MLCommons references, existing test/gate surfaces. | A risky packet is blocked or routed to human review with durable evidence. |

---

## Research Spine

The research lesson is not "build a magical autonomous company." It is that
closed loops work when they have executable actions, objective evaluators,
memory, and governance.

| Source | Lesson for Dharma |
|---|---|
| [Darwin Godel Machine, arXiv:2505.22954](https://arxiv.org/abs/2505.22954) | Self-improving coding agents need an archive, diversity, empirical validation, sandboxing, and human oversight. Dharma's Darwin proposals must be downstream of evidence, not free-running self-editing. |
| [AlphaEvolve white paper](https://storage.googleapis.com/deepmind-media/DeepMind.com/Blog/alphaevolve-a-gemini-powered-coding-agent-for-designing-advanced-algorithms/AlphaEvolve.pdf) and [DeepMind announcement](https://deepmind.google/blog/alphaevolve-a-gemini-powered-coding-agent-for-designing-advanced-algorithms/) | Evolutionary coding scales when programs are automatically evaluated. Dharma should start with governance/audit/codebase tasks because tests, lint, diff review, and customer acceptance can score them. |
| [FunSearch, Nature 2024](https://www.nature.com/articles/s41586-023-06924-6) | LLM creativity must be paired with systematic evaluators and a program database. This maps to OpportunityEngine plus EvidenceLedger, not free-form brainstorming. |
| [Voyager, arXiv:2305.16291](https://arxiv.org/abs/2305.16291) | Automatic curriculum, executable skill library, environment feedback, and self-verification compound. Dharma's `SkillLibrary` should emerge from successful packets, not from hand-written doctrine alone. |
| [Reflexion, arXiv:2303.11366](https://arxiv.org/abs/2303.11366) | Verbal feedback and episodic memory can improve later trials without weight updates. Dharma should exhaust KaizenReview, Human YDS, and playbooks before training models. |
| [SWE-agent, arXiv:2405.15793](https://arxiv.org/abs/2405.15793) | Agent-computer interfaces matter. AgentOps should have narrow tools, explicit file scope, test access, and reports designed for agents, not only humans. |
| [METR task-completion time horizons](https://metr.org/time-horizons/) and [2025 methodology note](https://metr.org/blog/2025-03-19-measuring-ai-ability-to-complete-long-tasks/) | Agent autonomy should be measured by task horizon and reliability, not by narrative confidence. Dharma packets should record estimated human duration and success/failure. |
| [LoRA, arXiv:2106.09685](https://arxiv.org/abs/2106.09685), [QLoRA, arXiv:2305.14314](https://arxiv.org/abs/2305.14314), [DPO, arXiv:2305.18290](https://arxiv.org/abs/2305.18290) | Specialist models are plausible once there are stable traces and preference labels, but adapters and preference optimization require clean datasets and evals first. |
| [FrugalGPT, arXiv:2305.05176](https://arxiv.org/abs/2305.05176) and [RouteLLM, arXiv:2406.18665](https://arxiv.org/abs/2406.18665) | Routing/cascades can reduce cost while preserving quality. Dharma should build model allocation and cost attribution before buying hardware. |
| [Lambda GPU cloud pricing](https://lambda.ai/service/gpu-cloud/pricing) | GPU economics are volatile and workload-dependent. Cloud GPU prices provide a live comparison point; ownership is justified only after utilization and revenue support it. |
| [NIST AI RMF](https://www.nist.gov/itl/ai-risk-management-framework), [OWASP LLM Top 10](https://owasp.org/www-project-top-10-for-large-language-model-applications), [MLCommons AILuminate](https://mlcommons.org/benchmarks/ailuminate/) | Safety is an operating discipline: govern, measure, manage, secure against prompt injection/excessive agency, and benchmark model behavior. `SafetyKernel` should wrap autonomy and release gates, not replace telos governance. |

---

## 90-Day Build Plan

### Days 1-30: Close The Morning Cockpit Loop

Goal: make the daily truth intake run end-to-end from existing fact producers.

Build target:

- `make morning-cockpit`

Required inputs:

- Operator Ground Truth via `OperatingFactBundle`
- DocOps/system-map report if available
- latest AgentOps reports
- latest KaizenReview
- explicit Human YDS path
- LLM burn/cost source
- Daily Operating Brief generation

Required outputs:

- rendered Morning Cockpit brief
- source manifest showing every present, missing, and optional input
- machine-readable bundle for later consumers
- explicit next-highest-leverage recommendation

Acceptance gates:

- The make target writes a source manifest.
- Missing major sources fail visibly or are marked as explicitly optional by policy.
- Daily Operating Brief generation is reused, not forked.
- Tests cover present and missing input behavior.
- Known `repo_cleanup` classifier bugs are fixed before any cleanup-derived signal is treated as truth. If the active branch lacks `repo_cleanup`, Morning Cockpit records it as absent rather than guessing.
- The active operator-brief seam remains the near-term track.

### Days 31-60: Make Work Metabolism Real

Goal: make bounded autonomous work the standard unit of execution.

Build path:

- Standardize `WorkPacket` as the only unit of autonomous execution.
- Run 3-5 real bounded AgentOps packets from different proposal sources.
- Pipe every AgentOps report into KaizenReview.
- Promote recurring successful patterns into a first `SkillLibrary` or playbook surface.
- Add Human YDS ratings to at least one completed artifact per week.

Acceptance gates:

- Every packet names allowed files, rollback path, gates, and expected evidence.
- No autonomous run is accepted without an AgentOps report.
- Every accepted report has a KaizenReview.
- At least one playbook/skill candidate is produced from repeated evidence.
- At least four Human YDS ratings exist by the end of the phase.
- Failed packets alter future packet selection or stop-doing guidance.

### Days 61-90: Add Revenue And Compute Treasury

Goal: connect Dharma's governance capability to commercial and compute reality.

Commercial offer:

- `AI Codebase Governance + AgentOps Audit`

Build path:

- Generate one real audit report from a repo using Dharma's own tools.
- Convert audit findings into bounded WorkPackets.
- Execute safe fixes where permitted.
- Add `RevenueLedger` and `ComputeTreasury` as explicit fact producers or clearly marked planned interfaces.
- Start model-routing and cost attribution: frontier model for hard reasoning, open/local models for repeated tasks, future specialist models only from verified traces.

Acceptance gates:

- One audit report has source repo, findings, evidence, and recommended packets.
- At least one finding becomes a WorkPacket and has an execution result.
- Revenue/customer signal is recorded in a durable ledger or planned-interface manifest.
- Compute spend is attributable to at least packet, model/provider, and outcome.
- GPU ownership is explicitly deferred unless measured revenue, utilization, and cost curves justify it.
- A model-routing decision can be explained by task difficulty, cost, and observed outcome.

---

## Public Interface Reservations

These names are reserved for later implementation. They must not be implemented
as new parallel substrates without an accepted WorkPacket:

- `OperatingCompanyKernel`
- `OpportunityEngine`
- `EvidenceLedger`
- `RevenueLedger`
- `ComputeTreasury`
- `ModelFoundry`
- `SkillLibrary`
- `MorningCockpit`

Implementation rule: every reserved interface must first declare which existing
substrate it reuses and which existing source of truth it refuses to duplicate.

---

## Anti-Mythology Rules

No organ is real until all six conditions are true:

1. It has a producer.
2. It has a schema.
3. It writes durable output.
4. It has at least one consumer.
5. It has tests or a repeatable check.
6. It has at least one real run using non-toy inputs.

Additional rules:

- Do not call a doc a system.
- Do not call a schema a loop.
- Do not call a report a ledger unless later runs consume it.
- Do not call a cost estimate a treasury unless it changes allocation.
- Do not call a model a specialist unless it beats a baseline on held-out evals.
- Do not call a revenue idea a market signal until a real external human acts.
- Do not let a future organ bypass telos gates, RuntimeState, operating facts,
  or evidence just because the name sounds like architecture.
- Do not start parallel substrates while the operator-brief seam is still the
  active implementation track.

The organism expands only by closing measured loops.
