---
title: Mandala Mission Control — Dharma World Deck
path: spec-forge/mandala-world-deck/MASTER_SPEC.md
slug: mandala-mission-control-dharma-world-deck
doc_type: master_spec
status: draft
created: 2026-08-09
owner: operator decision pending; no admitted implementation owner
scope: spec-forge incubation; product, interaction, truth, authority, evaluation, and rollout contract
summary: Candidate specification for consolidating the existing Dharma cockpit into a precise, non-coder-first, visual and optionally gameful ownership experience.
connected_relevant_files:
- dashboard/src/components/operator-coherence/v2/CockpitV2Board.tsx
- dharma_swarm/operator_core/control_surface_models.py
- dharma_swarm/operator_core/runtime_truth.py
- dharma_swarm/operator_core/reversibility_gate.py
- dharma_swarm/runtime_graph_views.py
- docs/architecture/CONTROL_SURFACE.md
- docs/governance/ACTIVE_TRACK.yaml
- docs/governance/SWARM_GENOME.md
---

# Mandala Mission Control: Dharma World Deck

Candidate master product, interaction, truth, and rollout specification v0.2

**Status:** CANDIDATE / INCUBATING — no implementation authority, no active-track admission, and no runtime authority
**Role:** `reference` candidate design record in the forge lane; it carries no implementation authority and may become an `active_spec` only after separate Gate 0 ratification and promotion
**Date:** 2026-08-09
**Observed checkout:** `bb2c5174e30413d78a5e2ed7193e9e7eb84bf1a4` (`origin/main` at the start of this work)
**Requested by:** the operator, to make the whole organism understandable and governable as a precise, visual, interactive experience
**Proposed home:** the existing `/dashboard/cockpit`; this document creates no new site, database, task store, authority system, or execution engine

**Review state:** revised after three independent read-only red-team reviews of non-coder usability, visual consolidation, claim semantics, authority, alerting, accessibility, and Goodhart failure modes. Review agreement is critique, not proof; the acceptance fixtures in this document remain the release gate.

This document is deliberately in `spec-forge/`. That directory is the repository's incubation lane for candidate contracts that are not current truth (`spec-forge/README.md:61-96`). The accepted Control Surface ADR, live owners, runtime databases, authority gates, and active-track declarations continue to win over this proposal.

---

## 1. The promise, in ordinary language

Today the system is more like a city whose buildings, workers, roads, permits, security cameras, and archives all exist, but are shown on different maps. The problem is not that nothing exists. The problem is that the operator has to remember where everything lives and mentally reconcile conflicting views.

The World Deck should make the city feel ownable.

When the operator opens it, it should answer four questions immediately:

1. **What matters most right now?**
2. **What does the system actually know, and how does it know it?**
3. **What decision can only I make?**
4. **What are the agents authorized under configured policy to do next?**

The operator should not have to understand databases, branches, APIs, receipts, or agent runtimes to use the first screen. Those details must remain available when challenged, because simplicity without inspectability would create false confidence.

The first thing on screen is a five-line **Operator Brief**, not a graph:

1. what needs attention now — or why the system cannot safely rank it;
2. why, including when and where the supporting information came from;
3. what judgment needs the operator — or “nothing needs you” / “decision source unavailable”;
4. what agents are and are not authorized to do under configured policy; and
5. the next safe step and the proof that would close it.

The map sits underneath that brief. It helps the operator understand relationships; it never forces the operator to decode the picture before acting safely.

The target experience is a living world map, a quest book, a control room, and an evidence locker over the **same underlying objects**:

```text
                             NORTH STAR
                                  │
                    THREE STRATEGIC PRIORITIES
                                  │
                 ┌────────────────┼────────────────┐
                 │                │                │
              QUEST A          QUEST B          QUEST C

       Every quest has independent, reversible status lanes:

       KNOWLEDGE     PERMISSION     EXECUTION     EVIDENCE     OUTCOME
       mapped        expired        running       stale        unmeasured

       Stable capabilities form the terrain underneath every quest.
       No lane silently upgrades, hides, or completes another lane.
```

### The 30-second experience

Within 30 seconds of opening the cockpit, a non-coder should be able to say:

- “These are the three things we are focusing on.”
- “This one is blocked by a decision only I can make.”
- “This is the evidence behind the warning.”
- “The agent may inspect and propose, but under current configured policy it may not merge, spend, contact, or delete.”
- “This is the next small, testable step.”

If the system cannot support one of those statements, the interface must say **unknown**, **stale**, **conflicted**, or **not authorized**. It must not improvise reassurance.

### The few words the first screen uses

| Deck word | Ordinary meaning | Precise detail available underneath |
|---|---|---|
| Strategic priority | One of the three things the operator chose to keep in view | Persisted owner, version, who chose it, and when |
| Attention item | The one condition the system suggests looking at now | Inputs, missing sources, priority rule, and evidence |
| Quest | A bounded mission with an intended outcome | Track/mission identity, dependencies, slices, and owner roles |
| Slice | The next small piece that can work and be checked end to end | Task identity, acceptance tests, scope, and proof obligation |
| “A source says” | Reported, not directly checked | Source owner and report time |
| “Directly seen” | Observed by a named source | Observation method and time |
| “AI conclusion” | Inferred; useful but challengeable | Model/method, inputs, and missing evidence |
| “Checked using …” | A verifier evaluated an exact claim | Subject digest, obligation, method, result, and evidence digest |
| Receipt | Proof that a particular event was recorded | Event identity and binding; never completion by itself |
| Authority | A scoped permission for one exact effect | Principal, action, target, policy, scope, expiry, and decision |

### One ordinary visit

The operator opens the cockpit after several hours away. The Brief says: “One critical source is unavailable, so the deck cannot justify a single top recommendation. Your three strategic priorities are unchanged. One approval expires in 42 minutes. Agents may continue read-only investigation; they may not publish or merge. Safest next step: inspect the expiring approval and its evidence.”

The operator opens that one item. The first layer shows the question, why it matters now, the suggested option labeled **AI conclusion**, the available choices, and whether the decision is reversible. “Why,” “Evidence,” and “Mechanics” reveal the rest. If the operator opens the map, the same item is already centered; if they switch to Run or Evidence, the selection and time remain unchanged. Nothing is approved from the read-only v1 deck: it deep-links to the existing authorized action owner.

---

## 2. Executive decision

Rebuild the **top level of the existing Cockpit V2** around the World Deck. This is a consolidation, not a ninth mode, another dashboard, or another site. The current Overview/Triage/Runtime/Evidence experiences are absorbed into four clearer lenses; specialist pages remain deep links until feature parity is proven, then redundant top-level routes are hidden, redirected, or retired through an explicit migration decision.

The deck has four persistent lenses over one selected object:

1. **World** — the Operator Brief, stable terrain, the operator's three strategic priorities, current impact, freshness, alerts, and zero or one evidence-backed attention recommendation.
2. **Decide** — one operator decision at a time, with the queue still visible. In read-only v1 it explains and deep-links to the existing action owner; it does not approve anything.
3. **Run** — a human-readable journey from mission to slice to run and recorded events. Run termination, verification, and external outcome remain separate.
4. **Evidence** — declared, desired, observed, and verified claims; their sources; conflicts; history; and proof obligations.

It also has two interchangeable representations:

- **Linear** — calm cards, lists, tables, and timelines for fast work.
- **Spatial** — a bounded, nested world map for orientation and relationship discovery.

The current selection, time, strategic priorities, and map center must survive every lens and representation switch. Those are four different concepts in the UI. The graph is one representation of the system, not the product itself.

### Five decisions this specification locks as candidate defaults

1. **Stable capabilities are the terrain; active projects are quest-lines.** The mental map does not rearrange every time a track opens or closes.
2. **Knowledge, authority, execution, evidence, and outcome are separate.** No single health/readiness/progress/XP score or monotone quest rung may combine them.
3. **The first release is read-only.** It may generate a typed proposal or handoff, but it owns no mutation path.
4. **Gameful presentation is optional.** Neutral mode contains the same facts, authorized-action links, and functionality.
5. **Each lane changes only from evidence specific to that lane.** Tokens, code volume, tests written, branches, agents, heartbeats, and receipts alone do not advance another lane.

---

## 3. Why this belongs in the existing cockpit

The repository already declares the TUI as the primary cockpit and the dashboard as the web operator surface, with an explicit instruction not to invent a third website (`dashboard/README.md:8-28`). The Live Ops Cockpit is already a read-only projection at `/dashboard/cockpit` over `/api/operator-coherence/report` (`docs/ops/LIVE_OPS_COCKPIT.md:1-11,51-76`). Cockpit V2 already has overview, design, tracks, runtime, git, preservation, triage, and evidence modes (`dashboard/src/components/operator-coherence/v2/CockpitV2Board.tsx:44-113`).

The accepted Control Surface ADR already provides most of the precision substrate this experience needs:

- declared intent versus observed reality;
- typed rows;
- evidence and provenance;
- human-decision context;
- a verification timeline;
- freshness and source errors; and
- a read-only projection boundary (`docs/architecture/CONTROL_SURFACE.md:10-31,67-86,94-122`).

The current row contract already distinguishes declared, desired, and observed state and carries owner, evidence, freshness, gaps, next action, human decision, source references, and a verification timeline (`dharma_swarm/operator_core/control_surface_models.py:156-182`). The frontend type currently omits some of those backend fields (`dashboard/src/lib/types.ts:843-864`), which is a concrete contract gap for a later implementation tranche.

The current whole-organism projector shows why a compression layer is needed. Running `make organism-status` at the observed checkout presented 10 active tracks, 6 venture organs, and 9 open-like broken-register items, while explicitly warning that the view is a projection rather than authority. The command is mutation-free by contract (`Makefile:792-802`; `scripts/governance/orientation_graph.py:1-31`). These numbers are a dated snapshot, not permanent product constants.

### Current visual debt that this proposal must not reproduce

- The navigation already exposes many overlapping operator routes (`dashboard/src/lib/dashboardNav.ts:47-98`).
- The mobile audit found 34 on-disk routes, multiple dense graph canvases, no working Playwright visual suite, and a fixed desktop shell (`docs/plans/MOBILE_OPERATOR_PWA_AUDIT_SPEC_2026-07-25.md:12-24,51-81,85-114`).
- The existing game layer is decorative: the “level” is a manually selected local-storage disclosure setting (`dashboard/src/hooks/useLevel.ts:3-45`), while HP, XP, and rank components turn arbitrary numbers into animated game chrome (`dashboard/src/components/game/HPBar.tsx:7-106`; `dashboard/src/components/game/XPBar.tsx:7-75`; `dashboard/src/components/game/LevelBadge.tsx:7-108`).
- The dormant `/api/viz` prototype is not registered in the main API (`api/main.py:552-612`) and its projector hardcodes eight subsystems as `alive` without observation (`dharma_swarm/viz_projection.py:224-252`). It is not a safe truth source.

Therefore the right move is consolidation: strengthen one cockpit shell and project existing owners faithfully.

### Required consolidation and migration map

World Deck is not feature-complete until it reduces the operator's top-level choices. During transition, old surfaces remain explicit deep links; after parity, their top-level entries are hidden, redirected, or retired by a separate reviewed route change.

| Current cockpit element | World Deck destination | Transition rule |
|---|---|---|
| Overview | **World** | Replace the default mode and its always-visible panel wall with the Operator Brief and bounded home frame. |
| Triage | **Decide** + alert ribbon | Absorb the human-judgment queue; keep one item central while queue count, oldest age, deadlines, and preemption remain visible. |
| Runtime | **Run** | Absorb read-only journey/inspection; deep-link to `/dashboard/runtime` for existing interrupt controls until command v2 is separately ratified. |
| Evidence | **Evidence** | Preserve and strengthen with claim-level modality, binding, source, time, and conflict. |
| Tracks | World filter + selected-object detail | Active tracks become quest overlays; portfolio arithmetic remains owned by `ACTIVE_TRACK.yaml`. |
| Git | Evidence/Mechanics context | Aggregate by selected object; keep specialist route as a deep link until parity. |
| Preservation | Persistent alerts + Evidence context | Unpreserved work can pierce strategic priorities when genuinely urgent; it is not a permanent home panel. |
| Design Sources | Help / About this view | Design provenance is documentation, not an operating mode. Broken off-repo provenance must be reconciled before the mode is retired. |
| Six top panels and `SpinePulsePanel` | Operator Brief + progressive disclosure | They do not render above every lens. Useful facts are rewritten into the brief or selected-object detail. |
| Control Surface, Timeline, Modules, Ecosystem and other overlapping routes | Named specialist deep links | No silent deletion. Establish fact/action parity, route analytics, redirects, and operator sign-off before removing a route from primary navigation. |

The current cockpit's client-side `buildHandoff(...)` duplicates an existing Control Surface backend handoff owner (`dashboard/src/components/operator-coherence/v2/cockpitV2Model.ts:763-779`; `api/routers/control_surface.py:393-414`). World Deck uses the backend handoff path and retires the client-generated duplicate after equivalence is tested.

**Consolidation acceptance:** after parity, the primary operator navigation has fewer entries than before; World does not render beneath the current hero + filter + six-panel + SpinePulse stack; and no fact or legitimate action disappears without an explicit deep link or migration record.

---

## 4. Reconciliation with the operator's visual design seed

The external `MANDALA_MISSION_CONTROL_CANON.md` is treated as an operator design seed, not repository runtime authority. It establishes the “meditation hall plus command bridge” character, context-preserving Linear/Recursive views, matte nihonga/Tibetan visual language, real-state motion, color-plus-glyph status, and `/dashboard/cockpit` as the front door (`/Users/dhyana/Desktop/Projects/DharmaSwarm FrontEnd/MANDALA_MISSION_CONTROL_CANON.md:1-15,21-39,43-83`).

This specification absorbs its useful intent and corrects three truth-model defects:

| Seed decision | Candidate disposition | Reason |
|---|---|---|
| Meditation hall plus command bridge | **Preserve** | Calm attention and operational precision reinforce each other. |
| Linear ↔ Recursive, context preserved | **Preserve and generalize** | Implement as Linear ↔ Spatial representation, preserving object, lens, and time. |
| Matte pigments; no decorative glow | **Preserve** | Motion and saturation may indicate observed liveness only; no visual theater. |
| Color plus glyph; WCAG contrast | **Preserve and strengthen** | Add text, pattern, keyboard, reduced-motion, and full structured alternatives. |
| Ten active tracks are the same ten organs | **Reject** | Tracks are variable WIP; stable organs/capabilities must anchor the mental map. The current portfolio ceiling is 10, not a permanent ontology (`docs/governance/ACTIVE_TRACK.yaml:70-86`). |
| One health verdict | **Reject** | A single score conflates knowledge, condition, and authority and can average away a critical unknown or external gate. |
| Presentation-only; do not touch data contract | **Amend** | A truthful experience needs missing claim modality, authority, freshness, and evidence fields to reach the frontend. It still adds no new owner or store. |

The proposed public label is **Mandala Mission Control**. “World Deck” names its new interaction model and may appear as the mode label. Final naming remains an operator taste decision, not an architectural dependency.

---

## 5. Research basis

This proposal was compared against safety-critical human-factors guidance, uncertainty research, current agent/developer control products, long-horizon coding-agent evaluations, accessibility standards, and gamification research. Sources below are used as design constraints, not as proof that this exact product will work.

### 5.1 Human control rooms and situation awareness

| Source / movement | What it contributes | What the World Deck adopts |
|---|---|---|
| [NASA Human Integration Design Handbook](https://www.nasa.gov/organizations/ochmo/human-integration-design-handbook/) and [NASA situation-awareness requirement](https://www.nasa.gov/reference/5-0-human-performance-and-error-vol-2/) | Human, software, data, and procedure are one operating system; displays must support recovery of situation awareness. | The operator is a designed part of the loop. Every lens answers what changed, what is true, and how to recover orientation. |
| [FAA Human Factors Design Standard](https://hf.tc.faa.gov/publications/2016-12-human-factors-design-standard/full_text.pdf) | Present information by task priority, cue changed data, reduce alternatives, and keep automated and non-automated evidence equally visible to reduce automation bias. | One evidence-backed attention item, changed-data markers, bounded queues, and equal visibility for agent recommendation and contradictory evidence. |
| [FAA display guidance](https://hf.tc.faa.gov/publications/2004-design-of-information-display-systems/full_text.pdf) | Reserve urgent alarm treatment for states needing attention; alerts need understandable text and a persistent place. | No blinking or alarm inflation. Critical alerts are literal, deduplicated, persistent, and linked to an explanation. |
| [NASA human-automation teaming](https://ntrs.nasa.gov/archive/nasa/casi.ntrs.nasa.gov/20190001937.pdf) | Transparency, two-way communication, and human-directed execution support calibrated use of automation. | Agents explain recommendations; the human can challenge, redirect, pause, or deny; authority is explicit. |
| [NIST AI RMF](https://airc.nist.gov/airmf-resources/airmf/5-sec-core/) | Roles, oversight, provenance, limits, evaluation, and ongoing monitoring must be explicit and contextual. | Role/owner, source, limitation, freshness, authority, and evaluation state are first-class fields. |

### 5.2 Information visualization and uncertainty

| Source / movement | What it contributes | What the World Deck adopts |
|---|---|---|
| [Shneiderman's visual-information-seeking pattern](https://drum.lib.umd.edu/items/155a868e-fb83-4115-9899-9187ea8c0498) | Overview, then zoom/filter, then details on demand. | World → selected quest → run → evidence, with selection preserved. |
| [Uncertainty visualizations for decision support](https://journals.sagepub.com/doi/10.1177/1555343411432338) | Showing ambiguity can help people recognize when the available information cannot select a best option. | Conflicts and missing evidence remain visible; the UI says what evidence would reduce uncertainty. |
| [Deterministic construal error](https://www.frontiersin.org/journals/computer-science/articles/10.3389/fcomp.2020.590232/full) | Non-experts can misread uncertainty graphics as precise deterministic values. | No unlabeled mist, glow, or probability theater; uncertainty is written in plain language. |
| [Kale, Kay, and Hullman](https://pubmed.ncbi.nlm.nih.gov/33048681/) | Central estimates can make viewers discount uncertainty; the best form depends on the decision task. | No dominant mean/readiness score; show components, ranges or discrete modality, and task-specific evidence. |
| [Calm technology](https://calmtech.com/papers/designing-calm-technology) | Good interfaces let information move between the periphery and center without constantly demanding attention. | Stable terrain remains calm; only actionable, deduplicated changes move to the center. |

### 5.3 Current control products

| Product pattern | Borrow | Do not copy |
|---|---|---|
| [Temporal event-history timeline](https://temporal.io/changelog/updated-event-history-timeline-view-is-now-available) | Human-readable execution journey, significant-event filters, retries, child runs, pausable live-follow. | Raw event exhaust on the non-coder home screen. |
| [LangSmith Studio](https://docs.langchain.com/langsmith/studio) and [LangGraph interrupts](https://docs.langchain.com/oss/python/langgraph/interrupts) | Simple and deep modes over the same run; durable pause; structured human input; visibly forked replay. | An IDE-density default or time travel that silently rewrites canonical history. |
| [LangSmith traces](https://docs.langchain.com/langsmith/observability-quickstart) and [annotation queues](https://docs.langchain.com/langsmith/annotation-queues) | Mission → slice → run → step hierarchy; one-item review queue; baseline comparison. | Treating trace count, tokens, latency, or an LLM judge as outcome proof. |
| [Backstage catalog](https://backstage.io/docs/features/software-catalog/) and [catalog graph](https://backstage.io/docs/features/software-catalog/creating-the-catalog-graph/) | Stable typed entities, ownership, lifecycle, and a map shaped around the human mental model. | Treating a catalog or manifest as live truth, or stuffing highly dynamic run steps into stable terrain. |
| [Grafana node graph](https://grafana.com/docs/grafana/latest/visualizations/panels-visualizations/visualizations/node-graph/) and [service graph](https://grafana.com/docs/tempo/latest/metrics-from-traces/service_graphs/service-graph-view/) | Graph/grid alternatives, bounded expansion, context menus, relationships linked to traces. | Rendering the entire system at once or attaching unsupported actions to graph nodes. |
| [Argo CD](https://argo-cd.readthedocs.io/en/stable/) | Desired/live comparison and explicit reconciliation. | Equating out-of-sync with unhealthy or auto-syncing an inferred desired state. |
| [Kubernetes object model](https://kubernetes.io/docs/concepts/overview/working-with-objects/) | Stable typed identity, desired `spec`, observed `status`, labels, and semantically distinct relations. | One generic “related to” edge or confusing lifecycle ownership with visual grouping. |
| [Port scorecards and actions](https://docs.port.io/governance/standards-and-compliance/concepts-and-structure/) | Rule-backed progression and typed, audited self-service with approvals. | Opaque maturity percentages or a second workflow/secret engine inside the UI. |
| [PagerDuty incident lifecycle](https://support.pagerduty.com/main/docs/incidents) | Explicit impact, owner, acknowledgement, resolution, and immutable timeline. | Turning every anomaly into an incident or treating “resolved” as verified root-cause closure. |

### 5.4 Why design and proof must remain upstream

Recent agent evaluations increasingly test what one-shot patch benchmarks omit:

- [SWE-EVO](https://arxiv.org/abs/2512.18470) evaluates multi-file, multi-step software evolution rather than isolated issues.
- [SWE-CI](https://arxiv.org/abs/2603.03823) evaluates maintenance through repeated continuous-integration loops.
- [SlopCodeBench](https://arxiv.org/abs/2603.24755) tracks correctness together with verbosity and structural erosion as agents repeatedly extend prior work.
- [Cognition FrontierCode](https://cognition.com/blog/frontier-code) adds behavioral correctness, test correctness, scope discipline, code-quality rubrics, and fail-before-fix test checks to its mergeability evaluation.
- [OpenAI's benchmark audit](https://openai.com/index/separating-signal-from-noise-coding-evaluations/) documents how underspecified tasks, low-coverage tests, and benchmark defects distort coding evaluation.

These sources do not prove a four-gate workflow is uniquely correct. They do support the product decision to show specification, design decisions, small slices, negative controls, and future change-cost evidence—not merely whether the latest run produced a green test.

### 5.5 Why this is gameful rather than point-scored

Gamification evidence is contextual and mixed. A controlled study found that points, levels, and leaderboards increased output quantity without significantly increasing intrinsic motivation or competence in that task ([Mekler et al.](https://research.aalto.fi/en/publications/towards-understanding-the-effects-of-individual-gamification-elem/)). A 2024 meta-analysis found small average motivational benefits and highlighted autonomy and competence problems when rules, choice, rank, or difficulty were poorly designed ([Li, Hew, and Du](https://link.springer.com/article/10.1007/s11423-023-10337-7)). Self-determination theory emphasizes autonomy, competence, and relatedness rather than pressure-driven compliance ([Ryan and Deci](https://selfdeterminationtheory.org/SDT/documents/2000_RyanDeci_SDT.pdf)).

Proxy rewards also invite literal optimization that misses intent; [DeepMind's specification-gaming review](https://deepmind.google/blog/specification-gaming-the-flip-side-of-ai-ingenuity/) provides many examples. Therefore the deck uses finite quests, mastery, discovery, proof, and restoration, but no persistent activity score.

---

## 6. Product goals and non-goals

### Goals

1. Give a non-coder a stable mental model of the organism.
2. Compress the system into at most three operator-chosen strategic-priority quests without hiding the larger portfolio.
3. Make every important claim challengeable through owner, source, time, modality, and evidence.
4. Separate what is true from what is permitted.
5. Turn ambiguous work into explicit decisions and small, testable slices.
6. Preserve operator control without requiring constant micromanagement.
7. Make bad news safe to surface and useful to resolve.
8. Support both a calm visual world and an equivalent precise list/table experience.
9. Reduce duplicate dashboards and adapters rather than creating another control plane.
10. Establish measurable evidence that the interface improves decision quality, not merely engagement.

### Non-goals

- A new website, native app, 3D engine, game engine, or second cockpit.
- A new task database, graph database, decision store, receipt store, authority service, or scheduler.
- Replacing `ACTIVE_TRACK.yaml`, TaskBoard, RuntimeStateStore, the Control Surface, the reversibility gate, or external systems of record.
- Making all agents autonomous or removing the human from product, architectural, ethical, financial, or irreversible decisions.
- Rendering every file, branch, process, agent event, or relationship simultaneously.
- A universal health, readiness, intelligence, alignment, or “organism level” score.
- Rewarding activity volume.
- Claiming product completion from a receipt, a model vote, a passed unit test, or a visually sealed quest alone.
- Mutating protected surfaces before track ownership and work-packet admission are explicit.

---

## 7. Responsibility and accountable ownership

### The operator retains five irreducible responsibilities

1. **Outcome:** What change in the world or system is worth pursuing?
2. **Strategic priorities:** Which three quests stay in the operator's scarce attention window?
3. **Irreducible judgment:** Which tradeoff, taste call, ethical choice, or architectural bet is acceptable?
4. **Risky authority:** May the system spend, contact, publish, trade, merge, deploy, delete, kill, expose a secret, or make an external commitment?
5. **Continuation:** Continue, change direction, pause, or stop?

Everything else may be delegated, but accountability does not disappear. Agents perform work; they do not become the accountable owner merely because they acted.

### Agents may be delegated

- reading the relevant context;
- mapping uncertainty;
- researching independent questions;
- proposing options and consequences;
- designing small slices;
- implementing authorized slices;
- running tests and negative controls;
- assembling evidence;
- explaining conflicts and asking for the smallest necessary human decision.

### Deterministic machinery enforces

- identity and correlation;
- configured-policy state transitions;
- dependency cycles and readiness;
- claim/lease scope and expiry;
- action classification;
- authority checks;
- idempotency;
- evidence binding;
- freshness and source-error handling;
- audit events and receipts.

The model may recommend. It may not manufacture any grant, state transition, verification, or accountable owner.

### Roles shown on every consequential object

A single `owner` label is not precise enough. The deck distinguishes roles whenever they differ:

| Role | Meaning |
|---|---|
| Canonical-state owner | The file, database row, or external system that owns the mutable fact |
| Accountable outcome owner | The human or institution answerable for the intended result |
| Decision owner | The principal whose judgment resolves the question |
| Authority/policy owner | The owner of the rule or grant that permits an exact effect |
| Execution principal | The agent, service, or human that attempted the effect |
| Verifier | The independent method/principal that evaluated an exact claim |
| Incident owner | The principal accountable for response and next update |
| Source owner | The owner of the observation or report supplied to the projection |

### The unresolved owner of the three strategic priorities

The deck must not hide this design choice:

- If the three slots are private view preferences, they are labeled **My priorities**, persist through a named existing preference owner, retain version/history, and change no agent behavior.
- If the three slots direct organism work, they require a ratified, receipted intent owner and concurrency semantics—preferably an admitted extension of an existing intent boundary rather than a new store.
- Until that owner is ratified, v1 calls them **local pins**, stores them only as clearly local preference, and never presents them as organism intent.
- A separate `recommended_attention` projection can suggest zero, one, or tied items. It never overwrites an operator slot and may return `insufficient_evidence`.

---

## 8. The visual world model

| Visual metaphor | Exact system meaning | Required literal label |
|---|---|---|
| Terrain / district | One versioned stable owner family/capability | Registry ID + plain label + canonical-state owner |
| Quest-line | Active track or bounded mission | Track/mission ID + outcome |
| Route segment | One vertical slice | Slice/task ID + acceptance |
| Party / moving unit | Observed run liveness only | Run ID + execution principal + last observation; never “progress” |
| Fog | Unspecified or unknown knowledge only | Missing question/source in literal text |
| Scout marker | Hypothesis or source report | “Hypothesis” or “A source says” |
| Locked gate | One action lacks an exact current authorization | Action + target + principal + required decision/grant |
| Bridge | Typed dependency or promotion | Edge kind + source/target |
| Seal | One exact verification decision bound to immutable evidence | Subject/predicate + verifier/method + result + time; adjacent claim-time/coherence labels may later become stale or contradicted |
| Outcome marker | An outcome metric was observed | Metric + value + baseline + target + owner + window + uncertainty |
| Target marker | A target predicate was separately evaluated as met/not met | Threshold/direction + result; no causal claim implied |
| Storm / incident overlay | Confirmed operational impact | Severity + owner + lifecycle |

Metaphors never replace literal state. A screen reader, neutral mode, exported snapshot, and automated test must receive the same underlying facts.

### Stable terrain, variable quests

The terrain is built from stable owner families and capabilities. Active tracks overlay that terrain through explicit, evidence-bearing `serves`, owned-surface, dependency, and promotion relations. A track may cross several regions; several tracks may touch one region. No one-to-one organ/track assumption is allowed.

### Candidate terrain registry v0

This registry must be independently ratified and versioned before it becomes the map skeleton. It is a human mental model over the seven owner families already named by `SWARM_GENOME`, not a claim that every current component fits perfectly (`docs/governance/SWARM_GENOME.md:38-73`).

| ID | First-screen label | Meaning | Current owner/source | Inclusion/version rule |
|---|---|---|---|---|
| `intent` | Direction | Outcomes, active tracks, WIP, surfaces, non-goals | `ACTIVE_TRACK.yaml` | Stable while the intent owner is stable; schema/version change requires ratification |
| `runtime_truth` | What is actually running | Persisted runs, claims, leases, receipts, idempotency | `RuntimeStateStore` + runtime spine owners | Runtime instances overlay this region; they do not become terrain |
| `dispatch` | How work moves | Identity, invocation, tollbooth, dispatch receipts | `dharma_swarm/spine/` | Only canonical dispatch owners; no parallel command spine |
| `projections` | What we can see | Dashboards, reports, onboarding, cards | Each named projector | Always labeled projection; cannot grant authority |
| `governance` | Rules and boundaries | Stable doctrine, policy, ownership rules | `docs/governance/`, `docs/doctrine/` | Rules, not live status |
| `work_control` | Work and attention | Task lifecycle, dependencies, control-surface reconciliation | TaskBoard + Control Surface owners | Board shadows remain projections unless explicitly owned |
| `value` | Real-world result | Value/revenue/venture signals and external outcome owners | Telic/RevenueSpine/external systems | External outcome needs external evidence; no internal self-funding claim |

For v0, **organ** means one stable owner family/capability region. **Domain** is a filter/tag across regions, not another hierarchy. **Surface** is a leaf UI/API/runtime surface shown inside a selected region, not top-level terrain. These meanings prevent three competing trees.

### Default World composition

```text
┌────────────────────────────────────────────────────────────────────┐
│ ALERT: none active · all alert sources checked 09:42               │
├────────────────────────────────────────────────────────────────────┤
│ OPERATOR BRIEF                                                     │
│ attention · why/freshness · your judgment · agent limits · proof   │
├────────────────────────────────────────────────────────────────────┤
│ NORTH STAR  ·  3 STRATEGIC PRIORITIES  ·  CHANGES SINCE LAST LOOK │
├───────────────────────┬────────────────────────────────────────────┤
│ YOUR ATTENTION        │ WORLD / LIST                              │
│ 1 first-layer card    │ 7 stable regions + 3 quest overlays       │
│ queue: 4 · oldest 2d  │ only the current selection expanded       │
├───────────────────────┴────────────────────────────────────────────┤
│ Journey: mission → slice → run/event receipt                       │
│                         ├→ verification decision                   │
│                         └→ outcome observation / target evaluation │
└────────────────────────────────────────────────────────────────────┘
```

The literal first frame has a hard budget: at most seven named terrain regions, three strategic-priority quests, one expanded attention/decision card, one journey strip, and one persistent alert summary. The decision first layer shows only **Question**, **Why now**, **Suggested option — AI conclusion**, **Choices**, and **Risk/reversibility**. Owner roles, consequences, authority mechanics, evidence, and effect preview expand under **Why**, **Evidence**, and **Mechanics**.

Forty visible objects is the ceiling for an explicitly expanded neighborhood, not the home-frame target. Two hundred is a rendering safety ceiling before clustering/list-only fallback. Larger collections collapse into labeled clusters with expected/observed counts, unknown membership, freshness, and exceptions. A complete sortable list remains one action away.

---

## 9. The four lenses

### 9.1 World — “What is happening?”

The World lens shows:

- North Star and the current system objective;
- three strategic-priority slots or clearly labeled local pins, distinct from the larger active-track WIP ceiling;
- stable capability regions;
- active quest overlays;
- outcome observations, target evaluations, and current incidents without implied causality;
- freshness and source failures;
- a persistent alert summary outside the three-slot limit;
- zero or one evidence-backed recommended attention item, with ties allowed; and
- a compact explanation of the rule, inputs, exclusions, missing sources, and why no justified ranking exists when that is the result.

It does not show every branch, stash, file, agent, or receipt. Large hygiene inventories become cluster nodes with drill-down. If no explicit `blocks` or `depends_on` path supports a causal bottleneck, the UI says **attention hotspot**, not bottleneck.

### 9.2 Decide — “What needs my judgment?”

The Decide lens has an ordinary attention-WIP cap of one central item while a persistent summary shows critical items/deadlines, queue count, oldest waiting age, the selected item, why it currently ranks there, and what changed since the operator last looked. Critical alerts sit outside that cap. Only a newly confirmed critical condition may preempt the central card; ordinary updates preserve the current selection and mark the queue as changed.

The first layer contains only the exact question, why now, the suggested option labeled as an AI conclusion, choices, and risk/reversibility. Expanding **Why**, **Evidence**, or **Mechanics** reveals:

1. the exact question in plain language;
2. why it matters now;
3. the affected outcome and objects;
4. options, including “defer” and “reject” where configured policy permits;
5. consequences and opportunity cost;
6. what is known, unknown, stale, or conflicted;
7. the recommendation and its status as an inference;
8. reversibility and rollback;
9. the authority principal, scope, and expiry;
10. the exact state transition or external effect that approval would permit;
11. the evidence required after execution; and
12. what happens if the decision is deferred; and
13. for a future command-capable release, a calm confirmation for irreversible or operator-only actions.

No option is preselected. There is no countdown, streak loss, confetti, or dramatic language around security, money, publishing, outreach, deployment, merge, or deletion.

**Current limitation:** current main has human-decision contexts and runtime interrupts, but it does not yet have a ratified canonical planning-decision store. The external Wayfinder Contract-D packet proposes versioned, non-dispatchable decision rows co-located with the existing TaskBoard SQLite boundary and atomic one-way promotion, but explicitly remains unratified (`/Users/dhyana/.codex/goals/wayfinder-native-integration/evidence/WP2_RATIFICATION_PACKET_2026-08-05.md`). Until that contract is ratified and implemented, Decide is a clearly sourced projection over existing human-decision and interrupt owners—not a new decision ledger. Read-only v1 may copy/export a proposal or open the existing authorized action surface; it may not render an approval as executable inside the deck.

### 9.3 Run — “What is the team doing?”

The Run lens translates runtime mechanics into a journey:

```text
Mission → Slice → Run → event / event receipt
                         ├→ separate verification decision
                         └→ separate outcome observation / target evaluation
```

It shows:

- expected output and proof obligation;
- current slice, not the entire horizontal build;
- assigned agent and scoped workspace;
- start, heartbeat, checkpoint, retry, handoff, pause, failure, and termination events;
- parent and child runs;
- changed events highlighted temporarily;
- live-follow with a pause control;
- pending and failed filters; and
- raw payloads only behind Evidence/Mechanics.

The existing runtime graph already projects runs, topology, checkpoints, active agents, and receipts from RuntimeStateStore (`dharma_swarm/runtime_graph_views.py:24-119,148-246`) through `/api/runtime/graph` (`api/routers/runtime.py:71-94`). The World Deck adapts this; it does not duplicate it.

A run `finish` or termination event means the process/run ended. It does not mean the slice, mission, verification, or outcome completed.

Before consequential work is handed back after a long autonomous interval, Run produces a **resumption packet**: current objective; last independently verified state; active runs; external effects already caused; open alerts and unknowns; assumptions omitted from recommendations; current grants and expiry; next irreversible boundary; and available stop/revoke/redirect controls in their owning surface. A high-consequence gate requires a reason-bearing human judgment, not a passive Continue click or quiz.

### 9.4 Evidence — “Why should I believe this?”

The Evidence lens shows claim-level truth:

- predicate and value;
- assertion basis (“a source says,” “directly seen,” or “AI conclusion”);
- coherence/disposition (supported, contradicted, conflicted, or unresolved);
- canonical-state, source, projection, accountable, and verifier roles;
- source, projection, and transport provenance chains kept distinct;
- source observation, ingestion, validity, and policy times;
- evidence status and verification method/result, not one universal proof ladder;
- verifier identity, method/version, independence basis, obligation set, and immutable evidence binding;
- conflicts and missing fields;
- declared → desired → observed comparison;
- history and supersession;
- baseline/candidate comparison; and
- what evidence would permit the next promotion.

The first row is always a plain-language summary. Raw JSON, logs, file lines, and receipts are progressively disclosed.

### 9.5 Alerts — “What may interrupt me?”

Alerts are outside the three strategic-priority slots. An alert is not a red color or a sorted card; it is a typed response obligation with:

- alert ID, source owner, observed/ingested time, freshness policy, and affected scope;
- response-based severity, urgency/deadline, assertion basis, coherence, and evidence;
- incident owner, required response, deduplication key, and correlation/incident ID; and
- current lifecycle state and next update time.

```text
detected → presented → acknowledged | snoozed → actioned → cleared
                                                      └→ verified/resolved
branches: reopened · escalated · source_unavailable
```

Acknowledged is not resolved. “Resolved” closes the response lifecycle; it does not by itself prove root cause, verification, or outcome. Snooze expires automatically and breaks on escalation. Correlated symptoms group under one incident. Critical alerts remain literally visible across every lens and drill-down; advisories queue calmly. Only a newly confirmed critical condition may steal attention. “No active alerts; all alert sources checked at [time]” is distinct from “No alerts shown because source X is unavailable.”

---

## 10. Gameful progression without Goodhart theater

The game layer is a visual wrapper over **parallel, non-monotonic facets**. It is not one success road and it has no global “quest complete” rung. A quest may be well specified, running, under an expired grant, verified against yesterday's code, and missing an external outcome at the same time. The deck must show all of that.

| Facet | Optional metaphor | Literal states / predicates | What may change it |
|---|---|---|---|
| Knowledge/specification | Fog → scout → map | `unspecified`, `hypothesized`, `specified` | Explicit problem/outcome/non-goals/dependencies/proof obligation; this is the only monotone-looking visual, and it may return to fog when invalidated |
| Permission | Lock / key | `absent`, `proposed`, `granted`, `expired`, `revoked`, `consumed`, `unknown` | A current effect-scoped policy/grant decision; never game state |
| Execution | Camp / moving unit | `idle`, `queued`, `running`, `paused`, `failed`, `terminated`, `unknown` | Direct runtime observations; heartbeat changes liveness only |
| Verification decision | Empty / passed / failed seal shape | `untested`, `inconclusive`, `passed`, `failed` | A typed verification decision bound to an exact subject/predicate/obligation/evidence set; age and conflict render beside it, never inside it |
| Outcome observation | Outcome marker | `unobserved`, `observed`, `stale`, `unknown` | Evidence from the metric's owning system |
| Target evaluation | Target marker | `not_evaluated`, `met`, `missed`, `inconclusive` | Baseline + direction/threshold + window + uncertainty + evaluation method |
| Causal attribution | No celebratory metaphor | `not_claimed`, `supported`, `unsupported`, `inconclusive` | A separately stated attribution method and evidence; mere temporal sequence is insufficient |

Every facet displays literal text beneath the metaphor. Permission and execution may change; a historical verification decision remains `passed`, `failed`, or `inconclusive` while independent adjacent literals say whether its supporting claim is `stale`, `contradicted`, or `conflicted`. The UI may therefore show `verification passed · stale · contradicted`; it may not replace those facts with one weathered/broken status. Cross-product fixtures such as `specified + expired permission + running + verification passed + stale + contradicted + unobserved outcome` are mandatory.

### What may receive narrative recognition

Recognition is private, informational, and has no points, rank, route advancement, authority, or unlock consequence. It is allowed only for an independently checked exact predicate, for example:

- resolving a named unknown with source-bound evidence;
- finding a source conflict before an unsafe decision;
- verifying one small slice with a meaningful fail-before-fix or negative control;
- recovering from failure without repeating an external effect;
- measuring an outcome in its owning system; or
- demonstrating lower future change-cost in a later, independently evaluated change—not merely claiming “better maintainability.”

Reducing WIP, freeing a slot, closing/retiring work, or de-duplicating cards may be useful operating acts, but they never advance a game state. Those are especially easy to game by hiding, splitting, or reclassifying work.

### What changes no facet or permission

- prompt, token, or tool volume;
- number of agents, branches, commits, PRs, files, or lines changed;
- number of tests or receipts without quality and unique binding;
- heartbeats or freshness touches;
- raw velocity, utilization, time spent, session length, clicks, or streaks;
- model consensus or same-model judge score;
- percentage green, bound, healthy, or ready;
- closing, splitting, renaming, or hiding work to improve a count;
- accepting agent recommendations;
- exercising authority.

### Anti-manipulation rules

1. Neutral and gameful modes return identical truth, effect-scoped action decisions, and authority data.
2. One uniquely bound outcome observation is represented once. Duplicate receipts, task splitting, and repeated ingestion do not change any facet.
3. Game state never grants a lease, approval, permission, merge right, or external authority.
4. No public or agent leaderboard, variable reward, streak decay, shame, or zero-sum competition.
5. The operator may dismiss, reorder, or challenge a suggested quest and see the suggestion rationale.
6. Critical incidents remain literally named; no boss-fight euphemisms.
7. Every mechanic needs an intended behavior, likely gaming strategy, harm countermetric, owner, review date, and kill switch.
8. Every badge names the exact subject and predicate it summarizes; no “overall sealed” badge exists.

---

## 11. Truth and authority contract

### 11.1 Orthogonal claim and control dimensions

Never compress these dimensions into one color, number, health word, completion word, or game rung. `Contradicted` is not a way information was sourced; `conflicted` is not an age; `verified` is not an authority grant.

| Dimension | Values | Question answered |
|---|---|---|
| Specification | `unspecified`, `hypothesized`, `specified` | Is the problem/outcome/proof obligation explicit? |
| Assertion basis | `declared`, `reported`, `directly_observed`, `inferred` | How did this assertion enter the system? |
| Coherence/disposition | `supported`, `contradicted`, `conflicted`, `unresolved` | How does it relate to available counterevidence? |
| Evidence status | `missing`, `present`, `invalid`, `quarantined` | Is evidence attached and admissible for this use? |
| Verification decision | `untested`, `passed`, `failed`, `inconclusive` | Did a typed verifier evaluate the exact obligation? |
| Temporal applicability | `current`, `stale`, `unknown` | Does a named freshness policy support using it now? |
| Execution | `idle`, `queued`, `running`, `paused`, `failed`, `terminated`, `unknown` | What has been directly observed about execution? |
| Outcome predicates | observation + target evaluation + attribution | Was a metric observed, was a target met, and is causality separately supported? |
| Action decision | effect-scoped decision object | May this principal attempt this exact effect now? |

There is no mandatory node-wide `health` or `complete` state in v1. Any later condition summary is a decomposable derived claim with method/version, input claims, coverage, exclusions, and time.

Discovering a broken probe can increase map knowledge while decreasing world condition. That is successful reconnaissance, not a loss.

### 11.2 Minimal typed claim

```ts
type WorldScope = {
  environment: string;
  repository?: string;
  checkout_or_worktree?: string;
  commit?: string;
  host?: string;
  runtime_instance?: string;
};

type Claim = {
  claim_id: string;
  subject: {
    ref: string;
    digest?: string;
    namespace: string;
    scope: WorldScope;
  };
  predicate: string;
  value: unknown;
  truth_owner_ref: string;
  source_ref: string;
  projection_ref?: string;
  transport_ref?: string;
  assertion_basis: "declared" | "reported" | "directly_observed" | "inferred";
  coherence: {
    state: "supported" | "contradicted" | "conflicted" | "unresolved";
    conflicts_with: string[];
  };
  evidence_status: "missing" | "present" | "invalid" | "quarantined";
  evidence_refs: string[];
  verification_refs: string[];
  temporal: {
    source_observed_at?: string;
    ingested_at: string;
    valid_until?: string;
    applicability: "current" | "stale" | "unknown";
    policy_ref?: string;
    policy_version?: string;
    source_clock_status: "trusted" | "skewed" | "unknown";
  };
  supersedes?: string;
  reason_codes: string[];
};
```

All fields are claim-level. One node may simultaneously carry a declared purpose, a directly observed heartbeat, an inferred risk, a failed verification, and a stale outcome observation. Conflict can coexist with any assertion basis.

Temporal applicability is derived from predicate/source policy, not asserted as a free badge. `current` is invalid without the required source time and policy. Source observation time, ingestion time, source-clock trust/skew, and `valid_until` remain separate.

### 11.3 Typed verification receipt

String evidence links cannot create a seal. A verification decision is representable only as:

```ts
type VerificationReceipt = {
  verification_id: string;
  subject_ref: string;
  subject_digest: string;
  predicate: string;
  claim_value_digest: string;
  expected_value_or_rule: unknown;
  obligation_set_ref: string;
  obligation_version: string;
  evidence: Array<{ ref: string; digest: string; role: string }>;
  verifier: {
    identity: string;
    method: string;
    method_version: string;
    independence_basis: string;
  };
  decision: "passed" | "failed" | "inconclusive";
  negative_control?: {
    kind: "fail_before_fix" | "counterexample" | "mutation" | "other";
    result: "passed" | "failed" | "not_applicable";
    evidence_ref?: string;
  };
  evaluated_at: string;
};
```

“Independent” must name its basis: a different principal, method, model family, external owner, or deterministic verifier appropriate to the claim. Producer self-review may be useful evidence but cannot be mislabeled independent. Local, CI, manual, and external are methods/contexts, not a universal strength ladder.

### 11.4 Promotion and validation obligations

```text
Reported assertion + direct observation
  creates: a new directly_observed claim with exact subject/scope/time
  preserves: the original report as history

Claim → verification passed
  requires: typed VerificationReceipt + exact subject digest + predicate
            + obligation version + evidence digests + independence basis
            + meaningful negative control where testable

Implementation verification → outcome observed
  requires: the outcome owner's evidence, not an internal implementation receipt

Outcome observed → target met
  requires: baseline + direction/threshold + measurement window
            + uncertainty/evaluation method; this does not imply causality

Target met → causally supported
  requires: a separately stated attribution design and evidence
```

Validation invariants fail closed:

- `verification=passed` is invalid with missing/invalid/quarantined required evidence.
- `temporal.applicability=current` is invalid when a required time/policy is absent.
- Direct observation requires an exact scope and source observation time.
- A verification receipt whose subject digest or obligation version does not match is quarantined.
- A test that also passes against the unchanged/pre-fix subject does not verify the change unless the obligation explicitly says otherwise.
- A receipt existing is proof of its recorded event only.

Hard no-coercion rules:

- `Reported external done` is not `ObservedCompletion`.
- A receipt existing is not completion.
- Verification passed is not authorized.
- Authorized is not true.
- Current evidence is not progress.
- Model consensus is not proof.
- An LLM explanation remains inferred or reported unless separately verified.
- A stale verified claim remains historical proof but cannot be rendered as currently verified without its age.
- A test that passes against the unchanged/pre-fix system does not verify the change.

The existing runtime truth vocabulary already separates runtime state, proof grade, source kind, and projection-only authority (`dharma_swarm/operator_core/runtime_truth.py:25-64,129-159`). The World Deck should adapt that vocabulary without ordering local/CI/external contexts into a fake universal ladder.

### 11.5 Bottleneck rule

An object may be called **bottleneck** only when current, non-hypothetical, policy-eligible `depends_on` or `blocks` edges establish named downstream impact. Otherwise it is an **attention hotspot** or a **hypothesized bottleneck**. A mixed-time/partial snapshot cannot assert a definitive bottleneck.

There is no universal hard-coded priority order. Attention is a separate, versioned policy decision with:

```ts
type AttentionPolicyDecision = {
  decision_ref: string;
  policy_ref: string;
  policy_version: string;
  policy_owner_ref: string;
  evaluated_at: string;
  input_snapshot_id: string;
  candidate_refs: string[];
  factors: Array<{
    candidate_ref: string;
    severity?: string;
    urgency_or_deadline?: string;
    time_to_harm?: string;
    consequence_or_reversibility?: string;
    deduplicated_downstream_impact?: number;
    preservation_risk?: string;
    waiting_age?: string;
    evidence_refs: string[];
    missing_inputs: string[];
  }>;
  result: "one" | "tie" | "insufficient_evidence" | "none";
  selected_refs: string[];
  rationale: string;
};
```

The owned policy must define how overlapping classes are resolved and how severity, urgency/deadline, time-to-harm, consequence/reversibility, causal downstream impact, preservation risk, and age interact. A confirmed production incident does not lose to a minor unpreserved artifact merely because the artifact has an earlier category number. Missing policy owner/version, unresolved class overlap, missing safety-critical inputs, or incomparable candidates yields `tie` or `insufficient_evidence`, not a precise winner.

For causal counts, strongly connected components collapse before counting so dependency cycles and task splitting cannot inflate the result. The UI exposes paths, edge eligibility/evidence, coverage, excluded/unknown edges, cycles, policy owner/version, calculation method, factors, and reason. Critical-alert preemption additionally requires a current alert severity/urgency classification under its named policy. There is no hidden universal score.

### 11.6 Roll-up rule

A region summary is a derived claim containing method/version, input claim/edge refs, `as_of`, expected membership, observed membership, unknown membership, exclusions, and reason codes. It may not average away:

- a critical child;
- an unknown or conflicted claim;
- missing proof;
- an external gate;
- an expired grant;
- a source failure; or
- a stale last-known value.

Natural counts are preferred: “3 of 10 required checks passed; 2 stale; 1 source unavailable; membership of 2 unknown.” A parent cannot be called healthy or complete when required children or membership are missing. Opaque percentages are forbidden where the components differ in meaning.

---

## 12. Read model and entity graph

The World Deck is a projection over existing owners. It stores no canonical state.

### 12.1 Node contract

```ts
type AttentionBase = {
  reason: string;
  policy_decision_ref: string;
  method_ref: string;
  method_version: string;
  input_snapshot_id: string;
  missing_sources: string[];
  evidence_refs: string[];
};

type Attention =
  | (AttentionBase & {
      class: "bottleneck";
      blocked_downstream_count: number;
      path_edge_refs: string[];
    })
  | (AttentionBase & {
      class: "hypothesized_bottleneck";
      candidate_path_edge_refs: string[];
    })
  | (AttentionBase & {
      class: "attention_hotspot";
    });

type WorldNode = {
  id: string; // namespaced stable identity, including environment where needed
  kind:
    | "north_star" | "objective" | "region" | "surface"
    | "track" | "mission" | "decision" | "slice" | "task"
    | "run" | "agent" | "receipt" | "verification" | "outcome"
    | "alert" | "incident" | "source";
  label: string;
  layer: "world" | "decision" | "execution" | "evidence";
  claims: Claim[];
  roles: {
    canonical_state_owner?: string;
    accountable_outcome_owner?: string;
    decision_owner?: string;
    authority_policy_owner?: string;
    execution_principals: string[];
    verifier_refs: string[];
    incident_owner?: string;
    source_owner_refs: string[];
  };
  derived_summaries: Array<{
    predicate: string;
    value: unknown;
    method_ref: string;
    method_version: string;
    input_claim_refs: string[];
    input_edge_refs: string[];
    as_of: string;
    expected_membership?: number;
    observed_membership?: number;
    unknown_membership?: number;
    exclusions: string[];
    reason_codes: string[];
  }>;
  action_decisions: ActionDecision[];
  attention?: Attention;
};
```

Hierarchy is expressed only through `contains` edges; there is no competing `parent_id`. Containment cycles fail validation.

### 12.2 Effect-scoped action and command contract

Read-only v1 never projects a stale Boolean such as `granted=true` or `executable_now=true`. It uses an effect-scoped decision:

```ts
type ActionDecision = {
  decision_ref: string;
  action_id: string;
  effect: string;
  target_ref: string;
  target_digest?: string;
  principal_ref: string;
  scope_ref: string;
  consequence_class: "reversible_safe" | "needs_lease" | "irreversible" | "operator_only";
  policy_ref: string;
  policy_version: string;
  evaluated_at: string;
  status:
    | "proposal_only" | "needs_approval" | "authorized" | "denied"
    | "expired" | "revoked" | "consumed" | "unknown" | "not_implemented";
  lease_or_grant_ref?: string;
  expires_at?: string;
  precondition_claim_refs: string[];
  blockers: string[];
  effect_identity: string;
  verifier_obligation_refs: string[];
  owner_action_url?: string;
};
```

Paused, historical, last-known, mixed-time, or partial snapshots never expose an executable affordance. Even a live `authorized` display is advisory at render time: the owning command path revalidates policy, principal, scope, expiry/revocation/consumption, subject digest, and idempotent effect identity at submission.

Any future command-capable release uses a separate lifecycle from run and verification:

```text
DRAFT → ARMED → AUTHORIZED → SUBMITTED → ACCEPTED → RUNNING
                                                    └→ EFFECT_OBSERVED → VERIFIED
branches: DENIED · EXPIRED · CANCELED · FAILED · UNKNOWN
```

After a disconnect following submission/acceptance, the state is `UNKNOWN`; the UI never invites a blind retry. Duplicate submission reuses the same effect identity. “Stop” must say whether it means cancel queued work, request cooperative cancellation, revoke future authority, or reach a separately verified safe state. Consequential actions require two distinct reason-bearing operator actions and no preselection.

### 12.3 Edge contract

```ts
type WorldEdge = {
  id: string;
  kind:
    | "contains" | "depends_on" | "owns" | "declares"
    | "observed_by" | "executes" | "produces" | "verifies"
    | "blocks" | "authorized_by" | "supersedes" | "promoted_to";
  source: string;
  target: string;
  observed_scope: WorldScope;
  truth_owner_ref: string;
  assertion_basis: "declared" | "reported" | "directly_observed" | "inferred";
  coherence: "supported" | "contradicted" | "conflicted" | "unresolved";
  hypothesis: boolean;
  evidence_refs: string[];
  temporal: {
    source_observed_at?: string;
    ingested_at: string;
    valid_until?: string;
    applicability: "current" | "stale" | "unknown";
    policy_ref?: string;
    policy_version?: string;
  };
  causal_eligibility: {
    status: "eligible" | "ineligible" | "unknown";
    policy_ref?: string;
    policy_version?: string;
    evaluated_at: string;
    reason_codes: string[];
  };
  reason_codes: string[];
};
```

Allowed edge kinds only:

```text
contains       depends_on      owns           declares
observed_by    executes        produces       verifies
blocks         authorized_by   supersedes     promoted_to
```

`owns`, `contains`, `depends_on`, `blocks`, and `observed_by` are not aliases. Unsupported relationships are omitted or explicitly marked as a hypothesis; visual proximity does not create a semantic edge. `temporal.applicability=current` is invalid without the edge's source observation time and named/versioned freshness policy. `causal_eligibility=eligible` is invalid without a named/versioned policy and evaluation time. Only an edge that passes both validations, is non-hypothetical, coherent, and scope-compatible with the snapshot can support an asserted bottleneck; otherwise causal eligibility fails closed to `unknown` or `ineligible`.

### 12.4 Snapshot, scope, and consistency contract

```ts
type SourceBase = {
  source_ref: string;
  truth_owner_ref: string;
  projection_ref?: string;
  transport_ref?: string;
  retrieved_at: string;
};

type SnapshotSource =
  | (SourceBase & {
      status: "ok";
      observed_scope: WorldScope;
      observation_identity: {
        kind: "digest" | "version" | "cursor" | "transaction";
        value: string;
      };
      observed_at: string;
    })
  | (SourceBase & {
      status: "partial";
      observed_scope?: WorldScope;
      observation_identity?: {
        kind: "digest" | "version" | "cursor" | "transaction";
        value: string;
      };
      observed_at?: string;
      error: string;
    })
  | (SourceBase & {
      status: "error" | "unavailable";
      observed_scope?: WorldScope;
      last_successful_observation_ref?: string;
      error: string;
    });

type WorldSnapshot = {
  schema_version: string;
  generated_at: string;
  snapshot_id: string;
  scope: WorldScope;
  consistency: "atomic" | "mixed_time" | "partial";
  consistency_proof_ref?: string;
  sources: SnapshotSource[];
  nodes: WorldNode[];
  edges: WorldEdge[];
  operator_priority_slots: Array<{
    slot: 1 | 2 | 3;
    node_ref: string;
    chosen_by: string;
    chosen_at: string;
    version: string;
    owner_ref: string;
    semantics: "local_pin" | "canonical_intent";
  }>;
  recommended_attention: {
    result: "one" | "tie" | "insufficient_evidence" | "none";
    node_refs: string[];
    rationale: string;
    policy_decision_ref: string;
    policy_owner_ref: string;
    method_ref: string;
    method_version: string;
    input_snapshot_id: string;
    missing_sources: string[];
    evidence_refs: string[];
  };
};
```

Numeric confidence is omitted from v1. A later proposal would need a defined event and horizon, [0,1] range, holdout provenance, calibration metric, uncertainty interval, expiry, named reference class, sample size, and evaluation date; a decorative percentage is forbidden.

The initial three-endpoint client adapter is necessarily `mixed_time`: current control-surface polling and operator-coherence polling have different cycles, and runtime has its own observation times. It preserves each source's observed scope, tagged identity, observation/retrieval time, and skew. A source with `status=ok` is invalid without those fields. Sources that cannot prove scope compatibility remain isolated or make the snapshot `partial`; they are never silently coerced to the top-level scope.

`consistency=atomic` is legal only when a named `consistency_proof_ref` establishes one owner-consistent transaction/snapshot barrier across every contributing source. Shared response generation time is not such proof. Otherwise the only legal values are `mixed_time` or `partial`. Mixed/partial snapshots may show isolated facts but may not promote, seal, assert a definitive bottleneck, claim a target/outcome, or expose an executable action.

---

## 13. Canonical source map

| Fact / projection | Existing truth owner or projector | World Deck use |
|---|---|---|
| Active intent, outcomes, WIP, owned surfaces | `docs/governance/ACTIVE_TRACK.yaml` (`docs/governance/SWARM_GENOME.md:42-45`) | Quest declarations and portfolio overlay |
| Declared product/runtime surfaces | `ACTIVE_SURFACE_MANIFEST.yaml` | Declared atlas; never live truth by itself |
| Task lifecycle and dependencies | `TaskBoard`; explicit FSM and dependency table (`dharma_swarm/task_board.py:1-68,75-99`) | Slice/task state and causal readiness |
| Runtime sessions, claims, runs, leases, receipts | `RuntimeStateStore` in `~/.dharma/state/runtime.db` (`dharma_swarm/runtime_state.py:1-7,30-109`) | Execution and evidence overlay |
| Runtime topology projection | `RuntimeGraphViews`, over RuntimeStateStore | Run graph and timeline adapter; projector is not the truth owner |
| Declared/desired/observed reconciliation | Control Surface Projector, with row-level owner refs | Claim/evidence adapter; projection only |
| Git/governance/live-ops aggregation | Operator Coherence report (`api/routers/operator_coherence.py:1-59`) | Calm cluster summaries; projection only |
| Process observation | Live Ops census receipt | Liveness observation only, never supervisor authority |
| Action risk class | `ReversibilityGate` | Explain action class; never substitute it for a grant |
| Approvals/interrupts/leases | Existing runtime/authority owners | Exact configured-policy decision, effect, and scope |
| Three strategic priorities | **Unratified**: local preference or existing intent-owner extension | `local_pin` only until ownership/concurrency/history are ratified |
| Alert lifecycle | Existing incident/source owner; no general owner established for all sources | Persistent response obligation only where an owner exists; otherwise source condition remains a claim |
| External outcome | Payment, publication, user, market, or other external owner | Outcome observation, target evaluation, and causal attribution kept separate |

The deterministic reversibility gate explicitly says only `reversible_safe` may run unattended and unknown actions fail closed to `needs_lease` (`dharma_swarm/operator_core/reversibility_gate.py:47-57,95-110,117-145,190-234`). Its result classifies risk; it does not by itself grant authority.

---

## 14. API and frontend integration

### 14.1 Shadow slice — prove the experience before a new contract

Inside `CockpitV2Board`, behind a feature flag, replace the current Overview body with a shadow Operator Brief + one real World neighborhood composed from these already registered read endpoints:

- `/api/control-surface/rows`;
- `/api/operator-coherence/report`; and
- `/api/runtime/graph`.

Add a typed client adapter that labels the result `mixed_time`, binds all sources to an explicit checkout/host/runtime scope, preserves source-specific times/errors, and refuses unsupported joins. No mutation, new router, new DB, or activation of `/api/viz`. This slice is intentionally disposable if the data model is wrong.

### 14.2 Candidate v1 projection

After the shadow slice proves the model, add a versioned read-only endpoint under the already mounted Control Surface router:

```text
GET /api/control-surface/graph
GET /api/control-surface/graph/stream   (later; only if live updates prove useful)
```

The server projector composes owner facts into one scoped `WorldSnapshot` whose consistency is explicitly `atomic`, `mixed_time`, or `partial`; it never promises coherence merely because facts share a response. It may cache a snapshot, but the cache is labeled and cannot become authority. It creates no new state database.

### 14.3 Frontend shape

- Extend existing `/dashboard/cockpit`.
- Factor one shared `SystemMapCanvas` with list/tree fallback; do not build a seventh bespoke graph canvas.
- Reuse the existing inspector/drawer and mode system.
- Put the Operator Brief and alert summary before map controls.
- Add progressively disclosed `Strategic priorities`, `Lens`, `Representation`, and `Time` controls; do not label all four “focus.”
- Encode current selection in the URL so a link reopens the same object, lens, time, and representation.
- Keep raw evidence behind progressive disclosure.
- Do not derive authorized actions from frontend `available_actions`; use effect-scoped decisions from the owning authority/reversibility path. V1 shows proposal/deep-link only.

### 14.4 Time semantics

Every view is either:

- **Live:** following a current stream;
- **Paused:** current selection frozen while data continues buffering;
- **Historical:** an immutable snapshot at a named time; or
- **Last known:** source unavailable, age displayed prominently.

Historical replay never rewrites canonical history. Any exploratory replay creates a visibly labeled counterfactual fork with parent snapshot and no production authority.

Paused, historical, last-known, partial, mixed-time, or counterfactual views expose no executable controls. They may open a live owner surface, which must independently reload and revalidate state.

---

## 15. Functional requirements

| ID | Requirement | Acceptance |
|---|---|---|
| FR-01 | Preserve current selection, lens, representation, time, and map center across navigation. | Switching World → Evidence → Spatial keeps the same object and URL-round-trips it without changing strategic priorities. |
| FR-02 | Show no more than three strategic priorities. | A fourth requires choosing what leaves; larger portfolio remains visible; local pins are never rendered as organism intent. |
| FR-03 | Show one operator decision centrally without hiding the queue. | Queue count, critical/deadline summary, oldest age, ranking rationale, and changed marker remain visible. |
| FR-04 | Separate stable terrain from active quest overlays. | Closing/opening a track does not rearrange stable regions. |
| FR-05 | Expose orthogonal claim semantics. | Assertion basis, coherence, evidence, verification, and temporal applicability remain distinct on one node. |
| FR-06 | Preserve source errors and unknowns. | Missing, stale, conflicted, probe-error, and scope-mismatch fixtures never render current/supported/verified/authorized by implication. |
| FR-07 | Explain or withhold recommended attention. | Operator can inspect paths, policy, inputs, exclusions, missing sources, and evidence; ties/insufficient evidence are valid. |
| FR-08 | Provide graph/list parity. | Every fact and legitimate action in the canvas is reachable in the structured view. |
| FR-09 | Translate execution without claiming completion. | Mission → slice → run/event branches separately to verification and outcome. |
| FR-10 | Bind every seal to proof. | A keyboard/screen-reader user can trace seal → exact predicate/digest/obligation → verifier/method/independence → evidence/negative control successfully. |
| FR-11 | Make configured-policy action decisions explicit. | Card shows effect/target/principal, class, policy/version, grant/lease, scope, time/expiry, effect identity, rollback, and proof required. |
| FR-12 | Fail closed on unknown actions. | V1 shows proposal/deep-link only; unknown displays `unknown/not authorized here` and never inherits a green UI hint. |
| FR-13 | Keep neutral/gameful parity. | Toggling gameful mode changes zero facts, actions, permissions, or export data. |
| FR-14 | Support calm live updates. | Only a confirmed critical alert may preempt; other updates do not move the current selection or erase comparison context. |
| FR-15 | Support query/jump navigation. | Search by human label or namespaced ID; results state kind, owner roles, scope, and temporal applicability. |
| FR-16 | Show an explicit empty state. | “Nothing needs your decision” is distinct from “decision source unavailable.” |
| FR-17 | Export a challengeable, redacted packet. | Export names claims, owner roles, sources, scope, action decisions, and proof obligation without secrets/sensitive payloads. |
| FR-18 | Never mutate from a read projection. | V1 contains no state-changing request; proposal generation is text/artifact only. |
| FR-19 | Persist critical alert visibility. | Drill-down, mode switch, snooze expiry, correlation, and source outage cannot silently hide a critical item. |
| FR-20 | Prevent false composite worlds. | Every snapshot names scope/consistency/source versions and refuses incompatible environment/worktree/host/runtime joins. |
| FR-21 | Consolidate the cockpit. | World replaces the default panel wall; old routes have parity/deep-link/migration records; primary nav shrinks after parity. |
| FR-22 | Support meaningful resumption. | A returning operator can inspect last verified state, effects, unknowns, grants, next irreversible boundary, and owner controls. |
| FR-23 | Keep game facets independent. | Cross-product fixtures never collapse to one color, rung, health, or “complete” label. |

---

## 16. Visual, interaction, and accessibility requirements

### Visual stance

- Deep indigo/sumi ground; warm shell-white text; matte mineral pigments.
- No decorative neon, bloom, scanlines, noise, or arbitrary animated particles.
- The `/dashboard/cockpit` route suppresses the current global particles, scanlines, and synthetic micrographics; the World frame does not sit beneath them.
- Motion and saturation only for observed state changes or liveness.
- Unknown is not greyed into invisibility; it has a clear unknown glyph/pattern and text.
- Danger red is reserved for confirmed urgent danger, not generic incompleteness.
- No more than two visual borders in a frame; use spacing and hierarchy.
- Numbers use tabular figures, but plain language leads.
- The shell reflows without a permanently fixed-width sidebar; basic phone-width orientation is a Slice-1 requirement, not deferred to an offline/mobile phase.
- Default labels use ordinary language from Section 1; canonical terms remain in Evidence/Mechanics.

### Accessibility release target

WCAG 2.2 AA is the minimum ([W3C WCAG 2.2](https://www.w3.org/TR/WCAG22/)); cognitive guidance also favors clear words, short blocks, whitespace, and alternatives to numerical concepts ([W3C cognitive accessibility](https://www.w3.org/WAI/WCAG2/supplemental/objectives/o3-clear-content/)).

Requirements:

1. Complete keyboard path with no trap.
2. Graph pan, zoom, drag, and spatial selection have button, tree, and list alternatives.
3. Each graph has a short summary and complete structured equivalent.
4. Text contrast at least 4.5:1; meaningful non-text UI contrast at least 3:1.
5. Color is never the only signal; use text plus icon/shape/pattern.
6. Focus is visible and not obscured.
7. Core targets meet WCAG 2.2 minimum target-size requirements.
8. Reflow at 200% zoom and supported phone width without loss of function.
9. `prefers-reduced-motion` is respected; live motion can be paused.
10. No flashing.
11. Live-region announcements are deduplicated and rate-limited.
12. Tooltips are supplementary, never the only explanation.
13. VoiceOver/Safari and NVDA/Firefox (or the ratified supported matrix) are manually tested.
14. Disabled users participate in usability testing; automated scans alone do not establish usability.
15. The first implementation slice includes real route, keyboard, reflow, reduced-motion, and screen-reader smoke coverage; the currently missing Playwright directory is not accepted as “test later.”

### Neutral mode

Neutral mode removes metaphorical labels, decorative progression, and nonessential animation. It retains every fact, alert, action, explanation, and navigation path. Neutral mode is the safety baseline and first rollout default.

---

## 17. Failure, stale, and offline behavior

| State | Required rendering | Forbidden rendering |
|---|---|---|
| Source unavailable | Source name, error class, last successful observation, age, retry state | Empty healthy panel |
| Last-known data | “Last known” plus timestamp and stale pattern | Current/live color without age |
| Conflicting sources | Both claims, owners, times, and conflict reason | Averaged or silently preferred value |
| No data | Expected source and what is missing | Zero interpreted as healthy or failed |
| Probe failure | Degraded observation with probe details | System failure unless independently established |
| Stream disconnect | Paused/stale banner; selection preserved | Silent frozen animation |
| Partial snapshot | Visible partial badge and source-error count | Global success verdict |
| Mixed-time or scope mismatch | Per-source times/scopes and “cannot safely join/rank” explanation | One coherent causal chain, bottleneck, seal, target, or action |
| Alert source unavailable | “Alert status unknown; source unavailable” with last check | “No active alerts” |
| Unauthorized | Locked state with principal and scope needed | Disabled button with no explanation |
| Unknown action | Fail-closed class and no execution control | Inference from label or nearby action |
| Disconnect after command acceptance | `UNKNOWN`, effect identity, owner link, and reconciliation instruction | Blind Retry with a new effect identity |
| Verification subject/obligation mismatch | Quarantined receipt and exact mismatch | Seal or completion |

Offline/mobile cached views are read-only and prominently dated. No cached authority or approval is executable.

---

## 18. Security and privacy

1. Evidence drawers redact secrets and sensitive payloads at the projection boundary.
2. Public/share links are forbidden by default; exported packets are local unless explicitly moved by the operator.
3. Action preview displays exact target, effect, principal, grant scope, expiry, and recovery path.
4. Irreversible/operator-only confirmation is calm, un-timed, unselected, and reason-bearing.
5. The canvas itself is read-only. Any later action calls the same effect-scoped backend policy/authority path used outside the canvas and revalidates at execution.
6. Unknown actions fail closed.
7. Every mutation, if introduced later, emits an audit event linking proposal, subject digest, authority, decision, executor, effect identity, evidence, and verifier.
8. Historical and counterfactual states have no production authority.
9. Game state and preference state stay outside authority evaluation.
10. The current mobile audit's transport/authentication blockers must be resolved before remote action controls are considered (`docs/plans/MOBILE_OPERATOR_PWA_AUDIT_SPEC_2026-07-25.md:18-24,118-167`).
11. Every export path has data-classification, path/log redaction, and adversarial fixture coverage; traceability is not permission to leak sensitive evidence.

---

## 19. Performance and scale targets

These are product requirements to validate, not claims about current performance.

- Local cached World view meaningful content: p95 under 2 seconds.
- Selection/filter feedback: p95 under 100 ms after data load.
- Home-frame world objects: at most 7 stable regions + 3 strategic-priority quest overlays.
- Expanded-neighborhood ceiling: 40; hard rendering ceiling: 200 with clustering/warning; larger inventories use list/grid or incremental expansion.
- A source failure must not block unrelated source data.
- Live updates are coalesced so the screen changes no more than once per second outside a critical incident.
- Historical snapshot selection is stable and deterministic.
- Source timestamps retain their own clocks; `generated_at` never masquerades as observation freshness.

---

## 20. Vertical-slice rollout

No slice begins until ownership/admission is explicit. The current repository-titanium track owns Cockpit V2 model/board surfaces (`docs/governance/ACTIVE_TRACK.yaml:1758-1765,1782-1839`), and the active portfolio is at its hard ceiling (`docs/governance/ACTIVE_TRACK.yaml:70-86`). This candidate does not silently attach itself to that track.

### Release capability boundary

| Capability | Read-only v1 | Later command-capable v2 |
|---|---|---|
| Understand / inspect / compare / navigate history | Yes | Yes |
| Local pins or ratified strategic priorities | Yes, with owner semantics visible | Yes |
| Export/copy typed proposal or handoff | Yes, redacted | Yes |
| Open existing authorized action owner | Yes, explicit deep link | Yes |
| Approve / reject / resume / pause / stop inside World Deck | **No — “Control not available in this release”** | Only after canonical decision owner, effect-scoped authority, command lifecycle, security, idempotency, audit, and fixtures are ratified |
| Execute from graph/cached/historical/mixed-time state | No | No |

### Gate 0 — ratify product and ownership

- Approve/amend this candidate.
- Decide whether this is a bounded Titanium next-item, a successor track after a real retirement, or deferred.
- Reconcile the external Mandala design seed into a repository-owned design artifact.
- Ratify the seven-region terrain registry and the owner/semantics of strategic priorities.
- Approve the consolidation/migration matrix and route capability inventory.
- Ratify the decision/promotion owner before adding canonical Decide mutations.
- Produce the required work packet/preflight for protected surfaces.
- Establish a route-scoped calm/responsive shell and real Playwright/keyboard/a11y baseline; basic phone-width reflow cannot wait for Slice 8.

**Proof:** explicit operator/owner decision, track arithmetic, surface list, non-goals, rollback.

### Slice 1 — one read-only tracer bullet

In Cockpit V2, replace the default Overview body behind a feature flag and show one real selected quest:

```text
Operator Brief + alert summary
stable region → active track → task/slice (or visibly missing relation)
selected quest facets: specification · permission · execution · verification · outcome
run/event receipt ├→ verification decision
                  └→ outcome observation / target evaluation
```

Use existing APIs client-side and label the adapter `mixed_time`. Add Linear World plus list fallback, one inspector, source/scope/time labels, route-scoped calm shell, phone reflow, and real screenshot/keyboard/a11y smoke tests. Do not fabricate missing links or recommend a winner when inputs cannot rank one.

**Proof:** compare every displayed/derived field against raw endpoint output; incompatible-scope and negative fixtures render unknown/refuse the join rather than inventing completion, causality, currentness, authorization, or priority.

### Slice 2 — strategic priorities, attention, and alerts

- Add three slots as ratified intent or clearly local pins with owner/version/history and no hidden agent effect.
- Add `recommended_attention` with one/tie/none/insufficient-evidence outcomes.
- Add typed alert summary, lifecycle, correlation, snooze/expiry/escalation, and cross-lens persistence.
- Add causal bottleneck versus attention-hotspot logic.
- Aggregate noisy inventories into clusters.
- Preserve URL selection.

**Proof:** a fourth priority requires replacement; recommender cannot overwrite a slot; critical alerts pierce the slot limit; causal/non-causal/cycle/task-split fixtures label correctly.

### Slice 3 — Evidence contract

- Add claim-level assertion basis, coherence, evidence status, typed verification, derived temporal applicability, owner roles, source scope/errors, and declared/desired/observed diff.
- Close frontend/backend ControlSurfaceRow type drift.
- Add `/api/control-surface/graph` only after the client shadow proves the schema.

**Proof:** adversarial truth, binding, mixed-time, scope, self-verifier, freshness-policy, and schema contract tests.

### Slice 4 — Decide as a projection

- Render existing `HumanDecisionContext` and runtime interrupt owners as structured cards.
- One item at a time with queue/critical/deadline summary and stable-selection preemption rules.
- Generate/copy a typed proposal or handoff or deep-link to the live owner only.

**Proof:** no mutation requests; missing canonical decision source is labeled, not papered over.

### Slice 5 — Run journey

- Translate runtime graph/checkpoints/receipts to a journey that keeps run termination, verification, and outcome separate.
- Add changed-event highlighting, pause-follow, retry/child grouping, and raw Evidence drill-down.
- Add the resumption packet before consequential handback.

**Proof:** timeline order, retry grouping, stream-disconnect, and parent/child fixtures.

### Slice 6 — optional gameful layer

- Add optional fog/scout/map, permission, execution, verification, and outcome metaphors over the proven independent neutral facets; no linear unlock road or global completion seal.
- Add gameful/neutral parity tests and kill switch.

**Proof:** snapshot facts and effect-scoped action decisions are byte-equivalent across modes; cross-product states remain independent.

### Slice 7 — authorized actions, only after separate ratification

- Requires canonical decision/promotion contract, effect-scoped policy/authority API, lease/grant binding, idempotency, audit, remote security, and red-team gate.
- Requires the typed command lifecycle and execution-time policy revalidation; read-only v1 acceptance does not depend on this slice.
- Start with one reversible safe action.
- Irreversible/operator-only actions remain proposal/confirmation flows until independently approved.

**Proof:** authorized success, unauthorized denial, expired lease, wrong scope, replay, mismatched evidence, and rollback.

### Slice 8 — offline companion and remote-control hardening

- Fold into the existing PWA renovation plan; no second app.
- Offline is last-known read-only.
- Basic responsive/phone operation already shipped in Slice 1. This slice adds offline caching/installability and resolves REST/WS authentication, reconnect truth, and remote-control threat modeling before remote controls.

**Proof:** phone viewport, network transitions, stale cache, keyboard/screen reader, and transport security.

---

## 21. Evaluation and release gates

### Stage 0 — semantic and adversarial fixtures

Create a gold corpus of at least 48 fixtures covering:

- declared-only, reported, direct observation, valid verification;
- stale, conflict, missing source, probe failure, last-known cache;
- wrong-task/wrong-digest receipt;
- completion without proof;
- external gate;
- missing, expired, and wrong-scope lease;
- reversible, irreversible, and operator-only action;
- causal bottleneck and non-causal hotspot;
- dependency cycle;
- task-split downstream-count inflation;
- inferred/false causal edge and unknown parent membership;
- mixed-time and mismatched environment/worktree/host/runtime snapshots;
- `status=ok` source missing observed scope/identity/time and `atomic` snapshot missing consistency proof;
- self-verifier and wrong obligation version;
- conflicting directly observed claims;
- verification `passed + stale + contradicted` without state collapse;
- causal edge marked current/eligible while missing observation or policy/version;
- heartbeat-only stuck run;
- stale, revoked, consumed, and expired-while-viewing grants;
- paused/cached action hints;
- negative, regressed, noisy, delayed, and non-causal outcomes;
- no justified attention ranking and tied ranking;
- overlapping attention classes, missing policy owner/version, severe incident versus minor preservation risk, and unknown time-to-harm;
- command double-click, acceptance disconnect, cancel race, replay, and effect-observed/verification-failed;
- 50 correlated alert symptoms plus one unrelated critical alert;
- stream disconnect; and
- dense 300+ item inventory.

Red-team the incentive layer with duplicate receipts, task splitting, heartbeat spam, trivial tests, timestamp touching, incident renaming, blocker hiding, circular dependencies, self-awarded completion, and agent/commit/token flooding.

**Release threshold:** zero false authorized/temporally-current/verified/bottleneck/target-met/causally-attributed/completed states; zero unauthorized actions shown executable; every displayed or derived claim traceable to owner/source/scope/time/method; game layer changes zero facts, effect-scoped decisions, permissions, or exported data.

### Stage 1 — accessibility

Run automated checks plus manual WCAG review, keyboard-only traversal, 200% zoom, reduced motion, high contrast, and supported screen-reader/browser combinations.

Core tasks must be completable without pointer, color, animation, or the spatial graph:

- identify strategic priorities and the current attention item—or explain why no ranking is justified;
- traverse relationships;
- inspect claim basis/coherence/evidence/temporal applicability;
- identify exact authority status and owner action surface;
- inspect/copy a v1 proposal without executing it;
- recover after a live update.

Command-v2 accessibility is a separate later gate covering authorize/deny/defer, effect preview, confirmation, cancellation semantics, and recovery after unknown command state.

Any keyboard trap, focus loss, inaccessible graph fact, or missing structured alternative blocks release.

### Stage 2 — decision-support study

Compare three conditions:

1. current cockpit/control surface;
2. World Deck neutral mode; and
3. World Deck gameful mode.

Use randomized, counterbalanced, matched scenarios. Pre-register gold answers, harm weights, smallest effect of interest, non-inferiority margin, power/sample rule, exclusion rule, confidence-interval decision rule, and analysis before exposing the gameful layer. For a single operator, repeated N-of-1 trials are descriptive local evidence, not population proof.

Measure:

- harm-weighted decision accuracy;
- unsafe commission and omission errors;
- reported/observed/verified comprehension;
- authority comprehension;
- time conditional on correctness;
- rework and action reversal;
- confidence calibration and appropriate reliance;
- workload (the [NASA Task Load Index](https://www.nasa.gov/human-systems-integration-division/nasa-task-load-index-tlx/) may be one secondary instrument); and
- brief situation-awareness probes: what is true, stale, blocked, and authorized now?

The 30-second promise is tested directly on cold start and return-after-absence, without coaching, across normal, stale, conflict, critical-alert, and source-unavailable scenarios. The clock starts after meaningful content loads. Candidate threshold: p90 at or below 30 seconds for all five Operator Brief statements, at least 90% semantic accuracy, and zero unsafe authority errors. This threshold remains a candidate until pilot data justifies it.

**Pass:** using the predeclared margins and interval rule, gameful is non-inferior to neutral on safety, accuracy, and calibration and improves at least one predeclared operator outcome. Neutral World Deck is non-inferior to the current cockpit. Speed or delight never offsets a safety loss.

### Stage 3 — field trial

Roll out read-only neutral mode first, then feature-flagged gameful mode. Keep an instant kill switch. Four weeks is a minimum exposure window, not proof that novelty effects are resolved; examine time trends and longer rework/outcome follow-up.

Track proof-backed outcomes, false-status corrections, missed gates, unsafe attempts, duplicate evidence, task fragmentation, reopens/rework, incident reporting, pressure/tension, and voluntary game-layer disablement. Engagement is contextual only.

Stop immediately if:

- an unauthorized action appears executable;
- a false authorized/current/verified/bottleneck/target/causal/completed state appears;
- a mechanic suppresses bad-news reporting;
- a critical state is hidden by a roll-up;
- unsupported high-confidence advice is promoted; or
- accessibility regresses.

### Stage 4 — ongoing gate

- Semantic and accessibility suite on every release.
- Quarterly Goodhart/incentive red-team.
- Expiry and reapproval date for every game mechanic.
- Hidden anti-gaming fixtures rotated periodically.
- Highly positive/advanced-looking items manually audited against real outcome and evidence.

---

## 22. Product acceptance criteria

The candidate product is successful only if a non-coder operator can reliably:

1. state all five Operator Brief answers within the tested 30-second threshold—or correctly state that evidence cannot justify an answer;
2. explain why an item is a bottleneck, hypothesized bottleneck, hotspot, tie, or unrankable;
3. find the relevant canonical-state, accountable, decision, policy, execution, verifier, incident, and source roles;
4. distinguish “a source says,” “directly seen,” “AI conclusion,” source conflict, and “checked using …” without confusing them with permission;
5. distinguish stale evidence, failed verification, failed execution, missing data, and unavailable observation;
6. identify what only the operator can decide;
7. identify what an agent is authorized under current configured policy to attempt, for which effect/target/scope, and why;
8. explain what proof is required for the next specific facet transition;
9. see what must leave strategic priorities before a fourth enters and whether the slots are local pins or organism intent;
10. successfully trace a verification seal to exact subject/predicate/digest/obligation, verifier/method/independence, evidence, and negative control;
11. recover context from a resumption packet and open the correct live owner surface for any v1 control;
12. see a critical alert regardless of lens or drill-down; and
13. complete every core task in neutral, keyboard-only, and structured-list modes.

System-level acceptance:

- no new authority or persistence owner;
- no dual-write seam;
- no false composite world across environment/worktree/host/runtime or incompatible times;
- no unsupported causal edge;
- no node-wide health/completion label that hides independent facets;
- no action inferred from presentation hints;
- no game mechanic that changes truth or permission;
- no verification without uniquely bound proof;
- no target-met or causal-attribution claim from internal-only or merely sequential evidence;
- no new site or bespoke graph canvas;
- fewer top-level cockpit choices after parity, with explicit migration/deep links;
- read-only first slice proven against raw owner output; and
- implementation ownership explicitly admitted before protected surfaces change.

---

## 23. Rejected designs

| Rejected design | Why |
|---|---|
| Another website/dashboard | Increases route and truth drift; violates existing operator-surface doctrine. |
| World as a ninth cockpit tab | Adds a truthful canvas without reducing operator complexity; the top level must consolidate/replace. |
| Giant whole-system graph as home | Produces visual hairball, hides priority, harms mobile/keyboard use, and makes proximity look causal. |
| Fixed ten organs equal fixed ten tracks | Confuses stable ontology with variable WIP. |
| One health/readiness/XP score | Conflates epistemic coverage, actual condition, and authority; averages away danger and unknowns. |
| One Fog → Unlock → Motion → Seal → Land success road | Launders specification, permission, liveness, verification, and outcome into a false monotone story. |
| Persistent XP, streaks, leaderboards, loot | Rewards proxy activity, pressure, and concealment rather than judgment and outcome. |
| Agent count or token maximization | Optimizes the production station even when review/decision/value is the bottleneck. |
| Cosmetic “alive” animation | Liveness must be observed and dated, not inferred from component existence. |
| Turn on `/api/viz` as-is | Router is unmounted and the projector fabricates fixed alive subsystems. |
| Map-owned actions | A projection cannot become an authority or mutation owner. |
| Frontend `available_actions` or node-wide `granted=true` as permission | A display hint is not an effect-scoped configured-policy decision, current grant, or execution-time revalidation. |
| Mandatory single recommended focus | Converts missing evidence, ties, or operator preference into fake system truth. |
| Client-joined mixed-time data as one coherent snapshot | Can join intent from one checkout, runtime from another host, and stale authority into a false world. |
| Decision encoded as untyped task metadata | Risks dispatching unresolved decisions as implementation work; use a ratified typed decision boundary. |
| Model council vote as truth | Correlated judgments can inform a hypothesis; they do not create evidence or authority. |
| 3D/immersive v1 | Adds navigation, performance, and accessibility cost before the truth model is proven. |

---

## 24. Risks and mitigations

| Risk | Mitigation |
|---|---|
| Beautiful false confidence | Literal claim-basis/coherence/time labels; unknown and source-error fixtures; no single score/rung. |
| Map becomes a new truth store | Versioned read-only snapshot; every fact names its owner; deletion/rebuild test. |
| Graph becomes overwhelming | Seven-region home, three quest overlays, 40-object expanded ceiling, clustering, list fallback. |
| Operator over-trusts recommendations | Recommendation labeled inferred; contradictory evidence equally prominent; wrong-advice scenarios. |
| Missing evidence is forced into a winner | Ties/none/insufficient-evidence are first-class attention results. |
| Agents game visible facets or proxies | No activity points; unique evidence/outcome binding; Goodhart fixtures and mechanic expiry. |
| Bad news gets suppressed | Knowledge gain and world condition separated; incident count never used as a reward. |
| Authority leaks through UI | Backend deterministic gate plus valid grant/lease; read-only v1; unknown fail-closed. |
| Stale data looks live | Source-specific observed time, last-known label, disconnect state, no timestamp touching reward. |
| Incompatible facts form a false world | Namespaced identities, scope/consistency contract, mixed-time restrictions, mismatch fixtures. |
| Alerts cause fatigue or disappear | Response-based severity, correlation/dedupe, persistent critical ribbon, source-aware no-alert state. |
| Local pins masquerade as organism intent | Ratify an owner or label local pins; recommender cannot overwrite them or direct agents. |
| Design novelty fades | Neutral baseline, feature flag, minimum four-week exposure plus time trends/longer follow-up, disablement measurement. |
| Accessibility becomes an afterthought | Structured parity and screen-reader tests begin in Slice 1. |
| Cockpit owner conflict | Separate ratification/track admission and Titanium coordination before edits. |
| Wayfinder/decision duplication | Decide remains projection-only until one canonical decision contract is ratified. |

---

## 25. Operator decisions before implementation

Recommended defaults are included so the operator can approve or edit rather than design from zero.

1. **Name:** Mandala Mission Control, with “World Deck” as the interaction-model name.
   Recommendation: approve.
2. **Consolidation:** replace the current Overview/panel wall and absorb the four main modes rather than adding a ninth mode.
   Recommendation: approve the migration matrix; require parity/deep links before hiding any route.
3. **Terrain:** ratify the seven-region v0 registry and the organ/domain/surface meanings.
   Recommendation: approve as a candidate human mental model, versioned separately from live status.
4. **Strategic priorities:** three slots, separate from the ten-track portfolio ceiling. Decide whether they are private preference or organism-directing intent.
   Recommendation: ship as clearly local pins first; do not let them direct agents until an existing intent owner is ratified.
5. **Default view:** neutral Linear World; gameful and Spatial representations optional.
   Recommendation: approve for the first field trial.
6. **Game model:** parallel knowledge/permission/execution/verification/outcome facets, no global quest-complete road.
   Recommendation: approve.
7. **Action boundary:** read-only first; typed proposals/deep links only until decision, authority, and command contracts are ratified.
   Recommendation: approve.
8. **Decision owner:** ratify, amend, or reject Wayfinder Contract D separately.
   Recommendation: resolve before any canonical Decide mutation.
9. **Alert owner:** decide whether one existing incident owner can cover the deck or whether alerts remain adapters over source-specific owners.
   Recommendation: source-specific owners in v1; do not create a new incident engine in the UI.
10. **Portfolio admission:** amend the named Titanium track, retire a genuinely completed/abandoned track and admit a successor, or defer.
   Recommendation: do not raise the 10-track ceiling merely to fit this feature.

---

## 26. Definition of done for this candidate specification

This document is complete as a candidate when:

- its internal repository claims are source-cited or reproducible;
- its external design claims link to primary/official sources where possible;
- it names existing owners and avoids a new control plane;
- the non-coder experience, truth model, authority boundary, data shape, rollout, and tests are explicit;
- rejected designs and unresolved operator decisions are visible; and
- independent reviews are recorded, their blocking findings have explicit dispositions, and any remaining implementation risk is represented by a release fixture or operator decision.

Product implementation is **not** complete when this document is complete. A spec, mockup, test plan, or approval does not establish live behavior.

### Red-team closure ledger for v0.2

Three independent read-only reviews challenged v0.1. Agreement among reviewers did not grant truth or authority; it identified candidate failure modes. V0.2 makes these explicit dispositions:

| Blocking v0.1 finding | v0.2 disposition |
|---|---|
| World would become a ninth mode inside the same clutter | Replacement/migration matrix; World replaces Overview/panel wall; nav must shrink after parity |
| First frame too dense for the 30-second promise | Operator Brief; seven regions, three priorities, one attention card, one journey; 40 only after expansion |
| One game road collapsed independent dimensions | Parallel, reversible facets; no global completion rung |
| Claim modality mixed contradiction, verification, conflict, and freshness | Orthogonal assertion basis, coherence, evidence, verification, and derived temporal applicability |
| “Seal” and independence were prose-only | Typed digest-bound VerificationReceipt with obligation version, method, independence basis, and negative control |
| Node-wide authority/`executable_now` could go stale | Effect-scoped ActionDecision, proposal-only v1, live revalidation, separate command lifecycle |
| Undefined/evidence-free edges powered bottleneck claims | Typed claim-bearing WorldEdge; SCC/task-split defense; mixed-time restriction; ties/insufficient evidence |
| Client composition could fabricate a coherent world | Snapshot scope/consistency/source-version contract and mismatch fixtures |
| Strategic-priority owner was missing | Local-pin vs canonical-intent semantics; no agent effect or recommender overwrite until ratified |
| Alerts and returning-operator takeover were underspecified | Persistent alert lifecycle/summary and resumption packet |
| V1 acceptance silently required future commands/mobile work | Explicit read-only-v1/action-v2 matrix; basic responsive/a11y shell moved to Gate 0/Slice 1 |
| Outcome wording implied success and causality | Observation, target evaluation, and causal attribution are separate predicates; celebratory “landed/restored” defaults removed |
| First closure pass still mixed verification result, staleness, and contradiction | Verification decision has four values only; coherence and temporal applicability render as adjacent independent literals |
| Edge type could not prove causal eligibility/currentness | Edge now carries validated observed scope, temporal policy/version, and causal-eligibility policy decision; attention is a discriminated union |
| Top-level scope could not prove each source belonged to it | Every successful source now requires observed scope, tagged identity, and observed/retrieval time; atomic requires a consistency proof |
| Hard-coded attention buckets overlapped and ignored severity/time-to-harm | Replaced by owned, versioned AttentionPolicyDecision with overlap rules, factors, ties, and insufficient-evidence result |

---

## 27. Research/source ledger

### Repository and local design sources

- `dashboard/README.md:8-28` — current operator-surface doctrine.
- `docs/architecture/CONTROL_SURFACE.md:10-31,67-122` — accepted declared/observed projector contract.
- `docs/ops/LIVE_OPS_COCKPIT.md:1-11,51-76,105-136` — read-only cockpit and guardrails.
- `docs/plans/MOBILE_OPERATOR_PWA_AUDIT_SPEC_2026-07-25.md:12-24,51-81,85-167` — route, mobile, visual-test, and transport audit.
- `docs/governance/SWARM_GENOME.md:38-73,86-125,162-173` — owner families and claim-language firewall.
- `docs/governance/ACTIVE_TRACK.yaml:70-99,1758-1839` — portfolio policy and current Cockpit V2 ownership.
- `dharma_swarm/operator_core/control_surface_models.py:21-105,156-182` — evidence, source error, human-decision, and row contracts.
- `dharma_swarm/operator_core/runtime_truth.py:25-64,129-159` — runtime truth, proof grade, and source-kind vocabulary.
- `dharma_swarm/operator_core/reversibility_gate.py:47-57,95-145,190-234` — action classes and fail-closed classification.
- `dharma_swarm/runtime_graph_views.py:24-119,148-246` and `api/routers/runtime.py:71-94` — runtime graph projection and API.
- `/Users/dhyana/Desktop/Projects/DharmaSwarm FrontEnd/MANDALA_MISSION_CONTROL_CANON.md:1-107` — external operator design seed; not repo authority.
- `/Users/dhyana/.codex/goals/WAYFINDER_NATIVE_INTEGRATION_2026-08-05.md` and `evidence/WP2_RATIFICATION_PACKET_2026-08-05.md` — external active-goal design evidence; not ratified Dharma authority.

### External primary and official sources

- [NASA Human Integration Design Handbook](https://www.nasa.gov/organizations/ochmo/human-integration-design-handbook/)
- [FAA Human Factors Design Standard](https://hf.tc.faa.gov/publications/2016-12-human-factors-design-standard/full_text.pdf)
- [NASA Human-Automation Teaming](https://ntrs.nasa.gov/archive/nasa/casi.ntrs.nasa.gov/20190001937.pdf)
- [NIST AI Risk Management Framework Core](https://airc.nist.gov/airmf-resources/airmf/5-sec-core/)
- [NIST human-centered AI / ARIA evaluation program](https://www.nist.gov/programs-projects/human-centered-ai)
- [Shneiderman, The Eyes Have It](https://drum.lib.umd.edu/items/155a868e-fb83-4115-9899-9187ea8c0498)
- [Dong and Hayes, uncertainty visualizations for decision support](https://journals.sagepub.com/doi/10.1177/1555343411432338)
- [Padilla et al., deterministic construal error](https://www.frontiersin.org/journals/computer-science/articles/10.3389/fcomp.2020.590232/full)
- [Kale, Kay, and Hullman, visualizing uncertainty](https://pubmed.ncbi.nlm.nih.gov/33048681/)
- [Temporal UI timeline](https://temporal.io/changelog/updated-event-history-timeline-view-is-now-available)
- [LangSmith Studio](https://docs.langchain.com/langsmith/studio)
- [LangGraph interrupts](https://docs.langchain.com/oss/python/langgraph/interrupts)
- [Backstage Software Catalog](https://backstage.io/docs/features/software-catalog/)
- [Grafana node graph](https://grafana.com/docs/grafana/latest/visualizations/panels-visualizations/visualizations/node-graph/)
- [Grafana No Data and Error states](https://grafana.com/docs/grafana/latest/alerting/fundamentals/alert-rule-evaluation/nodata-and-error-states/)
- [Argo CD](https://argo-cd.readthedocs.io/en/stable/)
- [Kubernetes object model](https://kubernetes.io/docs/concepts/overview/working-with-objects/)
- [Port scorecard concepts](https://docs.port.io/governance/standards-and-compliance/concepts-and-structure/)
- [PagerDuty incident lifecycle](https://support.pagerduty.com/main/docs/incidents)
- [W3C WCAG 2.2](https://www.w3.org/TR/WCAG22/)
- [W3C complex-image alternatives](https://www.w3.org/WAI/tutorials/images/complex/)
- [Ryan and Deci, self-determination theory](https://selfdeterminationtheory.org/SDT/documents/2000_RyanDeci_SDT.pdf)
- [Deci, Koestner, and Ryan, reward meta-analysis](https://selfdeterminationtheory.org/wp-content/uploads/2014/04/1999_DeciKoestnerRyan_Meta.pdf)
- [Mekler et al., points/levels/leaderboards experiment](https://doi.org/10.1145/2583008.2583017)
- [Li, Hew, and Du, gamification meta-analysis](https://link.springer.com/article/10.1007/s11423-023-10337-7)
- [Manheim and Garrabrant, Goodhart taxonomy](https://arxiv.org/abs/1803.04585)
- [Amodei et al., Concrete Problems in AI Safety](https://arxiv.org/abs/1606.06565)
- [Amershi et al., Human–AI Interaction Guidelines](https://doi.org/10.1145/3290605.3300233)
- [DeepMind specification gaming](https://deepmind.google/blog/specification-gaming-the-flip-side-of-ai-ingenuity/)
- [FTC, Bringing Dark Patterns to Light](https://www.ftc.gov/reports/bringing-dark-patterns-light)
- [NASA Task Load Index](https://www.nasa.gov/human-systems-integration-division/nasa-task-load-index-tlx/)
- [SWE-EVO](https://arxiv.org/abs/2512.18470)
- [SWE-CI](https://arxiv.org/abs/2603.03823)
- [SlopCodeBench](https://arxiv.org/abs/2603.24755)
- [Cognition FrontierCode](https://cognition.com/blog/frontier-code)
- [OpenAI coding-benchmark audit](https://openai.com/index/separating-signal-from-noise-coding-evaluations/)

---

## 28. Compact handoff to a future build session

Do not start by drawing the whole world.

Start with the Operator Brief and one real active track inside the existing cockpit. Replace the Overview body behind a feature flag; do not append a ninth mode. Use existing read APIs and label the result mixed-time. Show missing links as fog, incompatible joins as refused, and unrankable attention as unrankable. Make the list view first-class. Prove neutral claim semantics, scope/time, effect-scoped authority, alert visibility, resumption, phone reflow, and accessibility before adding gameful presentation. Add no action until the canonical decision and authority owners can deny it in code.

The first visible success is not a beautiful mandala. It is the operator clicking one quest and being able to answer, without guessing:

> What is this, why does it matter, what changed, what is known, what is unknown, who owns it, what may happen next, and what proof will close the loop?
