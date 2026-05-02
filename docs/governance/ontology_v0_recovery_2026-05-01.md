# Ontology v0 Recovery — Source-Grounded Map of Dhyana's World
**Date**: 2026-05-01
**Scope**: Recover the durable structure of John Vincent ("Dhyana") Shrader's life-system; translate to a typed ontology for Dharma Swarm's next-seam engineering.
**Author**: Claude Opus 4.7, working from filesystem, not from memory of vibes.
**Citation discipline**: file paths and line numbers where verifiable. Where I can't verify, I mark `LIKELY`, `SPECULATIVE`, or `CONTRADICTED`.

---

## A. Context Recovery Map

Eight arcs. For each: earliest verifiable evidence, strongest current artifact, current state, what it is *trying to become*.

### A.1 Contemplative arc (Akram Vignan, 24+ years)
- **Earliest evidence**: `~/.dharma/knowledge/wiki/concepts/akram-vignan.md` (14.5KB, confidence 0.90); identity statement in every CLAUDE.md ("24 years contemplative practice, Mahatma status").
- **Strongest artifact**: 25 kernel axioms in `dharma_swarm/dharma_kernel.py` lines 28–73 (verified count). The axiom set is the contemplative arc *operationalized as code constraints* — not a mood, not a flavor: a SHA-256-signed integrity-checked invariant set.
- **Status**: Ground-truth. Immovable. The axiom set's hash `KernelGuard.load()` will refuse to start if mutated (`dharma_kernel.py:381–399`).
- **Trying to become**: a *substrate constraint*, not a side-channel. Already partly there: Tier-A AHIMSA gate blocks immediately on harm patterns. Not yet there: the gate is keyword-substring (CONFIRMED at `telos_gates.py:422`), not yet semantic — which is the gap `living_gates` memory entry calls out.

### A.2 AI / agentic systems arc (Dharma Swarm)
- **Earliest evidence**: `~/dharma_swarm/` git history reaches early 2024; `aux_mem_from_old_mac.md` references 717 evolution entries in pre-M5 "DHARMIC_GODEL_CLAW" runs.
- **Strongest artifact**: `dharma_swarm/ontology.py` registers 16 ObjectTypes (lines 858–1468); SQLite store `~/.dharma/ontology.db` (17.5 MB, WAL, FTS5) holds 1,806 Outcomes, 1,803 Contributions, 1,803 ValueEvents (per `dharma_briefs/MASTER_SYNTHESIS_2026-05-01.md` substrate audit).
- **Status**: ~1.25% of production Python imports the ontology (85 of 6,793 files; verified in master synthesis 2026-05-01). The substrate exists; adoption is shallow.
- **Trying to become**: a Palantir-style structurally-unavoidable ontology — typed objects + typed actions + writeback + witness — not a graph of nouns. The Operator Brief seam is its first proof.

### A.3 Ontology / semantic-systems arc
- **Earliest evidence**: `~/.dharma/knowledge/wiki/concepts/semantic-ontology.md`; `ontology.py` predates the Karpathy-wiki adoption.
- **Strongest artifact**: `OntologyActionGateway` at `ontology_action_gateway.py:19–200` — fail-closed wrapper that runs `TelosGatekeeper.check()` before every mutation; raises `OntologyGatewayError` on BLOCK.
- **Status**: Gateway works. Most of the codebase still bypasses it. Decision chain (ActionProposal → GateDecision) is registered as ObjectType but **not yet recorded** by `agent_runner` (zero `record_dispatch` / `record_gate_decision` calls; CONFIRMED in master synthesis).
- **Trying to become**: the load-bearing seam. Today's Operator Brief is the first surface that makes ontology adoption visible to *you*, not just to the agents.

### A.4 Mechanistic interpretability / R_V arc
- **Earliest evidence**: `R_V_PAPER/` family in `~/ALL MECH INTERP/mech-interp-latent-lab-phase1/` (v009, v010, v011 .tex). **CONTRADICTION RESOLVED**: the path `~/mech-interp-latent-lab-phase1/` is empty; the actual lab lives at `~/ALL MECH INTERP/mech-interp-latent-lab-phase1/`. CLAUDE.md's `~/mech-interp-latent-lab-phase1/` reference is wrong / stale path.
- **Strongest artifact**: paper v011 (Desktop copy and ALL-MECH-INTERP copy). Cabinet `worldview/bridge.md` ties R_V geometry to L3→L4 behavioral and Akram contemplative.
- **Status**: NeurIPS abstract due 2026-05-04 (3 days). Mistral 83% exhausted; cross-arch (Llama-3.1-70B + Pythia) and multi-token bridge identified as oral-tier moves.
- **Trying to become**: the *third vantage point* on the unified phenomenon — empirical credibility for the contemplative-mechanistic-behavioral triple mapping.

### A.5 Trading / calibration arc
- **Earliest evidence**: `~/AGNI-AUNT-HILLARY-PSMV/SHAKTI_GINKO/`, `~/rushabdev_work/rushabdev/`, AGNI VPS at `157.245.193.15`.
- **Strongest artifact**: `~/rushabdev_work/rushabdev/` v4 trading lab (Polymarket-focused; risk limits, scoreboard, paper broker, kill paths). Per wiki `trading-lab-evolution.md`: +$466 7d PnL as of 2026-04-17.
- **Status**: ACTIVE but blind (Anthropic credit depleted in trading branch). v4 in 7-day observation window before cutover.
- **Trying to become**: a *calibration substrate*. The deepest insight from `trading-lab-evolution.md`: trading is naturally swabhaav-disciplined because P&L is ground truth. This makes trading the *canonical CalibrationEvent producer* for the ontology.

### A.6 Writing / VWrite arc
- **Earliest evidence**: References in cabinet, no separate codebase. **CONFIRMED**: VWrite does not exist as a repo (verified by exhaustive search).
- **Strongest artifact**: 107-article Karpathy wiki at `~/.dharma/knowledge/wiki/concepts/`; transmission-document concept atom; `write` skill.
- **Status**: Deferred behind NeurIPS. The wiki *is* the writing substrate today.
- **Trying to become**: *transmission artifacts* — text that performs, not describes. The ROE / S(x)=x material is the natural source.

### A.7 Dharma Swarm / dharmic-agora / ROE arc
- **Earliest evidence**: `~/dharmic-agora/` (canonical, last commit 2026-03-03); `ai_reciprocity_ledger.py` inside swarm.
- **Strongest artifact**: dharmic-agora SABP/1.0 (Syntropic Attractor Basin Protocol) — federated basin protocol with witness chain. Distinct codebase, distinct purpose: external attractor, not internal swarm.
- **Status**: dharmic-agora dormant since March; ROE ("Recursive Ontology Engine") **does not exist as a separate codebase** — the closest match is `ai_reciprocity_ledger.py` inside swarm. `recursive_ontology` returns no separate hits. `LIKELY`: ROE is a *concept name* you've used informally for what `dharma_swarm.ontology` actually is.
- **Trying to become**: external-facing federated basin (agora) and internal-facing typed ontology (swarm) — two surfaces of one stance. Right now the bridge is unbuilt.

### A.8 Human operating-system arc
- **Earliest evidence**: 4:30 AM invariant; `~/.smriti/`; `~/.dharma/sessions/captures/daily/` directories.
- **Strongest artifact**: `~/dharma_briefs/2026-05-01-brief.md` (shipped today, first cron-produced brief). Each line cites `ontology://KnowledgeArtifact/.../cites/Outcome/...`.
- **Status**: Operator Brief seam **is live as of today**. WitnessLog count moved 0 → 4. KnowledgeArtifact 0 → 4. The decision-clarity chain is breathing.
- **Trying to become**: the daily proof that ontology-grounded artifacts *help you decide* better than the prior morning routine. Falsification milestone: 2026-05-08 (still at 4 = failure); 2026-05-15 (you stop reading it = failure).

### Unresolved contradictions / what needs human disambiguation
1. CLAUDE.md path `~/mech-interp-latent-lab-phase1/` does not exist; actual path is `~/ALL MECH INTERP/mech-interp-latent-lab-phase1/`. **Update CLAUDE.md.**
2. ROE / "Recursive Ontology Engine" — is this a future codebase, or is it the rename of what `dharma_swarm.ontology` already is? **Needs your judgment.**
3. dharmic-agora has been dormant 60 days. Is it dormant because de-prioritized, or because waiting on swarm-internal ontology to mature? **Needs your judgment.**
4. AGNI-AUNT-HILLARY-PSMV is named like a trading kit, but is actually a knowledge distillation. The actual trading kit is `rushabdev_work`. **Naming drift; rename or document.**

---

## B. The Real Primitives (refined from your provisional list)

I'll define each primitive in source-grounded form. Where the type already exists in `ontology.py`, I cite the line. Where it doesn't, I mark `MISSING`.

### B.1 HumanOperator
- **Plain meaning**: You. Singleton. Dhyana. The S5 in Beer's VSM, the gate-approver, the doctrine-author.
- **Why it matters**: Without HumanOperator as an explicit type, "human review" remains a vibes operation. With it, every gate decision can name *whose* judgment is being substituted for / deferred to.
- **Required**: `name` (immutable), `role` (operator), `axiom_authority` (boolean — can sign axioms? today: only Dhyana).
- **Allowed actions**: `ApproveProposal`, `SignDoctrine`, `ApproveGateProposal`, `RetireClaim`, `ReviseTelos`.
- **Required gates**: none — HumanOperator is the gate floor.
- **Status**: **MISSING** in `ontology.py`. AgentIdentity (line 951) covers human-as-agent partially, but the `axiom_authority` distinction is not encoded. **Recommend: add HumanOperator as 17th ObjectType, or extend AgentIdentity with `is_principal: bool`.**

### B.2 Agent
- **Plain meaning**: Any actor that can mutate state. Free-tier, paid-tier, internal, external.
- **Maps to**: `AgentIdentity` at `ontology.py:951–1002`. 17 roles enum'd.
- **Required**: name (immutable), agent_id, role, status, provider, model.
- **Allowed actions**: Spawn (gate: AHIMSA), Retire.
- **Failure mode I see in repo**: the master synthesis says directors (`thinkodynamic_director.py`, `overnight_director.py`) **bypass** ontology — they execute as agents but never register as `AgentIdentity`. That's the agent-shadow bug.

### B.3 Signal
- **Plain meaning**: Anything observed but not yet adjudicated. Market tick, log line, user message, alert, RSS hit.
- **Required**: source, timestamp, raw_payload, observer.
- **Status**: **MISSING** as ObjectType. `WitnessLog` (line 1175) handles internal-process observations but not external-world Signals. **Recommend: add `Signal` as the entry point to the Opportunity loop.**

### B.4 Claim
- **Plain meaning**: A proposition asserted as true. Distinct from Signal (which is just observation). Distinct from Evidence (which supports a Claim).
- **Status**: **MISSING** as a first-class ObjectType. Claims today live as free text inside `KnowledgeArtifact.content` — which is why citation auditing is so painful (your `claim-auditor` skill exists precisely because Claims aren't typed).
- **Recommend**: typed `Claim` with required `evidence_links`, `confidence`, `status` (asserted / verified / contradicted / retired), `proposer`.

### B.5 Evidence
- **Plain meaning**: Anything that supports or refutes a Claim.
- **Status**: Closest existing: `KnowledgeArtifact.provenance` field. **Recommend**: typed `Evidence` with required `kind` (measurement / citation / experiment_result / market_outcome / direct_observation), `claim_id`, `direction` (supports / refutes), `strength`.

### B.6 Question
- **Plain meaning**: An open inquiry. The thing that, when answered, becomes a Claim.
- **Status**: **MISSING**. The `chetana-gap-scan` skill produces Questions implicitly (under-covered topics, recurring open issues) but they aren't typed objects. **Recommend**: `Question` as an explicit type — it's the input to the Inquiry loop.

### B.7 Doctrine / Axiom
- **Plain meaning**: A rule asserted as binding. Axioms are sacred, immutable, signed. Doctrines are derived rules that can be revised.
- **Maps to**: 25 axioms in `dharma_kernel.py:36–73` (MetaPrinciple enum). Doctrine-as-distinct-from-axiom is **MISSING**.
- **Recommend**: `Doctrine` ObjectType for revisable rules (e.g. "for refactors, prefer one bundled PR" — already in your auto-memory but not in the substrate).

### B.8 ActionProposal
- **Plain meaning**: A proposed mutation, before gate evaluation.
- **Maps to**: `ActionProposal` ObjectType at `ontology.py:1262`. **EXISTS** but **agent_runner does not call `record_dispatch` to instantiate it** (CONFIRMED in master synthesis).
- **Failure mode**: today's substrate has the schema for proposal-as-typed-object but most actions skip the proposal phase and go straight to mutation. The Operator Brief seam will start fixing this.

### B.9 GateDecision
- **Plain meaning**: The result of running TelosGatekeeper against an ActionProposal. Records which gate fired and why.
- **Maps to**: `GateDecision` ObjectType at `ontology.py:1301`. **EXISTS** but **not recorded by agent_runner** (zero `record_gate_decision` calls).
- **Critical gap**: without GateDecision objects, gate enforcement is ephemeral — you can't audit which actions were blocked, why, by which gate. **This is the #1 substrate gap in the decision chain.**

### B.10 Action / ExecutionLease
- **Plain meaning**: An ActionProposal that passed gates and is being executed. ExecutionLease (`ontology.py:1332`) is the live-handle.
- **Status**: ExecutionLease type EXISTS. Verify it's being created — likely partial.

### B.11 Artifact / KnowledgeArtifact
- **Plain meaning**: Persistent output. File, paper, brief, prompt, measurement, code, model output.
- **Maps to**: `KnowledgeArtifact` at `ontology.py:1065`. 10 sub-types via the `artifact_type` enum. **EXISTS and is being used** — today's brief is one.

### B.12 Outcome
- **Plain meaning**: The empirical result of an action — verified, persisted.
- **Maps to**: `Outcome` at `ontology.py:1372`. **1,806 instances** in DB. The most-populated type. This is your existing strength.

### B.13 ValueEvent
- **Plain meaning**: A contribution to telos, measurable. Not synonymous with money.
- **Maps to**: `ValueEvent` at `ontology.py:1402`. **1,803 instances**.
- **Open question for you**: ValueEvent's *taxonomy* is not yet codified. What kinds of value? (decision_clarity / proven_capability / cited_artifact / paying_customer / saved_hour / falsification_passed / etc.) This is a Section-K question.

### B.14 Memory
- **Plain meaning**: Anything intended for future-you / future-agent retrieval.
- **Status**: Distributed across SMRITI, MEMORY.md, chetana atoms, memory-graph MCP, stigmergy. **Not a unified type.** The chetana grand-memory effort is the unification attempt.
- **Recommend**: do *not* add a Memory ObjectType yet. Instead: every other primitive should be addressable by chetana. Memory is the projection, not a primitive.

### B.15 Capability
- **Plain meaning**: A skill an agent can execute. 704 skills are indexed already.
- **Status**: **MISSING** as ObjectType. Skills are markdown files in `~/.claude/skills/`. **Recommend** typed `Capability` only when you have multiple humans/agents needing to query it; until then it's filesystem-shaped.

### B.16 Loop
- **Plain meaning**: A named feedback cycle. 13 loops documented in `CYBERNETIC_LOOP_MAP.md`.
- **Status**: **MISSING** as ObjectType. The map is markdown. Whether to type it depends on whether you want runtime loop-status as queryable substrate.
- **Recommend**: defer until at least one loop is closed and you want to track health.

### B.17 ProductThesis / Opportunity / MarketSignal
- **Plain meaning**: The Dharma Radar primitives. Opportunity = pain point + addressable user; ProductThesis = bet on a solution; MarketSignal = external evidence.
- **Status**: `VentureCell` at `ontology.py:1468` is the closest existing type — Ginko cell. But ProductThesis as separate from VentureCell is **MISSING**.
- **Recommend**: do *not* add these yet. The Operator Brief loop must run live for at least 2–3 weeks before you encode the next layer of opportunity-to-product types. Premature ontology = the Palantir lesson reversed.

### B.18 ResearchClaim / CalibrationEvent / Contribution
- **Maps to**: `Contribution` at `ontology.py:1438` (1,803 instances). ResearchClaim and CalibrationEvent are **MISSING** as distinct types.
- **Trading insight**: the trading lab is the canonical CalibrationEvent producer. Encoding `CalibrationEvent` would let trading P&L feed agent fitness — but this is downstream of Operator Brief.

### B.19 WitnessEvent / WitnessLog
- **Maps to**: `WitnessLog` at `ontology.py:1175`. EXISTS, currently 4 instances, growing.
- **Failure mode I expect**: WitnessLog is single-purpose now. In 2 weeks it will be the most queried type. Index it early.

### Primitives summary — what to add vs. what already exists

| Status | Type |
|---|---|
| Already typed and used | AgentIdentity, KnowledgeArtifact, TypedTask, Outcome, ValueEvent, Contribution, WitnessLog, EvolutionEntry, ResearchThread, Experiment, Paper, CustodianRole |
| Already typed, **not yet recorded by callers** | ActionProposal, GateDecision, ExecutionLease, VentureCell |
| Missing, recommend adding | HumanOperator, Signal, Claim, Evidence, Question, Doctrine |
| Missing, recommend NOT adding yet | ProductThesis, Opportunity, MarketSignal, CalibrationEvent, ResearchClaim, Capability, Loop, Memory |

That gives an Upper Ontology v0 of **~18 types**, not 100. Inside the user's stated 12–20 range.

---

## C. Typed Actions

The mutation grammar. Every action: input → gate → output → witness → optional value event.

The key principle from your Palantir-lesson: **an action is the only legitimate mutation**. Raw `INSERT` / `update_object()` calls are the bypass to scan for and stop.

### C.1 Already implemented (gateway-mediated)
At `ontology_action_gateway.py:45–165`:
- `create_object_or_fail(type_name, properties)`
- `update_object_or_fail(object_id, updates)`
- `link_or_fail(link_name, source_id, target_id, metadata)`
- `execute_action_or_fail(object_type, action_name, object_id, params)` — runs `TelosGatekeeper.check()` if action_def declares gates.

### C.2 Required but currently bypassed
| Action | Input | Output | Gate | Witness | Status |
|---|---|---|---|---|---|
| ProposeAction | actor + intent + draft_params | ActionProposal | none (proposal is read-only intent) | should record | **NOT CALLED by agent_runner** |
| EvaluateGate | ActionProposal | GateDecision | n/a | always | **NOT CALLED** |
| ExecuteLeased | GateDecision (ALLOW) | ExecutionLease + side effects | already in gateway | yes | partial |
| RecordOutcome | ExecutionLease + result | Outcome | none | yes | **WORKING** (1,806 instances) |
| RecordValueEvent | Outcome + value_kind + magnitude | ValueEvent | none | yes | **WORKING** (1,803) |
| RecordContribution | ValueEvent + actor | Contribution | none | yes | **WORKING** (1,803) |

### C.3 Recommended new actions
| Action | Input | Output | Required gate | Witness |
|---|---|---|---|---|
| ObserveSignal | source + payload | Signal | AHIMSA (input scrub) | yes |
| AssertClaim | Signal[] | Claim (status=asserted) | DOGMA_DRIFT, STEELMAN | yes |
| AttachEvidence | Claim + Evidence | Link | none | yes |
| AdjudicateClaim | Claim + Evidence[] + actor | Claim (status=verified/contradicted) | SATYA, ANEKANTA | yes |
| RetireClaim | Claim + Evidence (refuting) | Claim (status=retired) | SATYA | yes |
| ConvertClaimToDoctrine | verified Claim + HumanOperator approval | Doctrine | requires HumanOperator (B.1) | yes |
| AskQuestion | Signal | Question | none | yes |
| AnswerQuestion | Question + Claim | Link | DOGMA_DRIFT | yes |
| RegisterAgent | name + provider + capabilities | AgentIdentity | AHIMSA | yes |
| AssignTask | TypedTask + AgentIdentity | Link | none | yes |
| ApprovePromotion | EvolutionEntry + HumanOperator | EvolutionEntry (state=promoted) | requires HumanOperator | yes |

### C.4 Failure modes to design against (from substrate audit)
- **Raw write bypass**: `agent_runner.py:2875,3013` records Outcome/ValueEvent/Contribution but skips ActionProposal/GateDecision. Decision chain has no audit.
- **Director shadow**: `thinkodynamic_director.py`, `overnight_director.py` do not register as AgentIdentity. They mutate state with no traceable actor.
- **String-only refs**: `thinkodynamic_director.py:294,450,2678` references ontology objects by string ID, not via gateway. Renames will silently break.

---

## D. Core Loops

I'll evaluate the seven you proposed against actual repo state.

### D.1 Operator Brief loop (already named the first seam)
**Object chain**: `Outcome[]` (already populated) → `KnowledgeArtifact (brief)` → `WitnessLog` → emit to user → user reads → user makes decision.
**Status**: **LIVE as of 2026-05-01.** First brief shipped. Chain breathes.
**Success**: WitnessLog grows daily without manual reruns. User reads the brief instead of prior morning routine.
**Failure**: WitnessLog stays at 4 by 2026-05-08.
**Human judgment required**: which Outcomes are *worth surfacing*. Today's brief is repetitive (5 eval_probe_task entries) — that's the substrate honestly reporting; the *content quality* gap is the human-co-creation surface.

### D.2 Inquiry loop
**Object chain**: Question → Evidence[] → Claim (asserted) → Adjudication → Claim (verified) → Doctrine | Memory.
**Status**: **NOT BUILT.** Question, Claim, Evidence, Doctrine all missing as ObjectTypes.
**Earliest legitimate build**: after Operator Brief proves daily uptake. Likely 2026-05-15+.

### D.3 Opportunity loop (Dharma Radar — *as sense organ*, not newsletter)
**Object chain**: Signal → PainPoint → Opportunity → ProductThesis → Artifact → Launch → Outcome → ValueEvent.
**Status**: **NOT BUILT.** All upstream types (Signal, PainPoint, Opportunity, ProductThesis) missing.
**Critical correction adopted**: this is a *typed pipeline*, not a newsletter. The newsletter would be one downstream artifact of the pipeline.
**Earliest legitimate build**: after Inquiry loop, because Opportunity needs Claim/Evidence already typed.

### D.4 Build loop
**Object chain**: Spec (Question/Claim) → TypedTask[] → AgentIdentity execution → Artifact → PR → Outcome.
**Status**: **PARTIAL.** TypedTask (75 instances), AgentIdentity (23), Outcome (1,806) all working. But Spec and PR are not typed — Spec lives in markdown, PR is GitHub-state.
**Recommend**: do not type Spec yet. The friction would not pay back. Type PR later when multi-agent PR contention becomes a problem.

### D.5 Calibration loop (trading)
**Object chain**: Prediction (Claim?) → Trade → Outcome (P&L) → CalibrationEvent → Update agent fitness.
**Status**: **NOT WIRED.** Trading is in `rushabdev_work` and AGNI VPS. Outcomes there don't flow into swarm ontology.
**Lever**: trading is the most rigorously calibrated thing in your stack. Wiring it as CalibrationEvent producer would be high-value. But not before Operator Brief proves uptake.

### D.6 Governance loop
**Object chain**: ActionProposal → TelosGatekeeper.check() → GateDecision → (ALLOW/BLOCK/REVIEW) → audit.
**Status**: **HALF-BROKEN.** Gateway runs gates. But agent_runner doesn't record GateDecision. Gates fire ephemerally. **This is the most urgent integrity gap** — the governance loop is the proof-of-correctness for the whole substrate, and it's not auditable.
**Fix**: instrument `agent_runner` to call `record_dispatch` (creates ActionProposal) and `record_gate_decision` (creates GateDecision) before/after every gateway call. ~1 day of work.

### D.7 Identity / agent loop
**Object chain**: RegisterAgent → TaskClaim → Contribution → reputation accrual → authority adjustment.
**Status**: **PARTIAL.** AgentIdentity, TypedTask, Contribution all typed. Reputation is implicit (`fitness_average` field on AgentIdentity). Authority is not modeled.
**Open question**: what authority can an external agent earn? This is a Section-K question. Until you decide, leave it unmodeled.

---

## E. Dharma Swarm Ontology Diagnosis

What I found inspecting the runtime, not the docs.

**Substrate state (verified 2026-05-01)**:
- 16 ObjectTypes registered. 9 in active use; 4 schema-ready-but-not-recorded; 3 newly-shipped (since today's brief).
- DB at `~/.dharma/ontology.db`, 17.5 MB, WAL+FTS5, modified today.
- `Outcome | 1806`, `Contribution | 1803`, `ValueEvent | 1803`, `TypedTask | 75`, `AgentIdentity | 23`, `WitnessLog | 4`, `KnowledgeArtifact | 4`.
- **Adoption ratio**: 85 of 6,793 production Python files import the ontology = 1.25%. CLAUDE.md / older audits cited ~12% — that was *before* the repo grew 18× while ontology adoption grew 4×.

**Top gaps, ranked**:

1. **GateDecision recording is missing from `agent_runner`.** The schema is ready (`ontology.py:1301`); zero runtime records. This is *the* leverage point. Until decisions are persisted, the governance claim is unverifiable.
2. **Director shadow.** `thinkodynamic_director.py` and `overnight_director.py` mutate state without registering as `AgentIdentity` and without going through the gateway. They are the canonical "raw write bypass."
3. **`world_actions.py` ungated** in research-integration worktree. `github_create_pr` is wired to autonomous_agent without TelosGatekeeper. Risk is promotion-dependent (only fires when that worktree is promoted), but the surface is real.
4. **Decision-chain types unrecorded**: ActionProposal (1262), GateDecision (1301), ExecutionLease (1332), VentureCell (1468). Schema ready, no callers create instances.
5. **Legacy `Entity` / `ONTOLOGY` dict** in `ontology.py:1564` deprecated for removal **2026-05-08**. Honor the date.
6. **TelosGatekeeper substring matching** at `telos_gates.py:422`. Multi-layer (also injection patterns, credential patterns, exfil patterns, think-phase, S4→S3 escalation). But the *primary AHIMSA path* is substring. Living-gates work is the upgrade target.

**Two leverage points to wrap first** (next-seam candidates):
- **agent_runner.py instrumentation** for ActionProposal + GateDecision recording. ~1 day. Closes the governance loop audit.
- **Director-to-AgentIdentity registration**. ~half day. Closes the agent shadow.

Both are smaller than "wrap Ginko" or "wrap world_actions." Both have higher leverage because they affect every action in the system.

---

## F. Human Co-Creation Requirements

Where *only you* can decide. Where agents can draft. Where it must be co-created.

### F.1 Human (you) must decide
- The 25 axioms. Already done. They're signed.
- Which gates are Tier-A (block immediately). Today: only AHIMSA. Adding any Tier-A is a doctrinal act.
- The taxonomy of `ValueEvent` kinds. Today implicit. Section-K question.
- The definition of "harm" (drives AHIMSA's HARM_WORDS list). Today substring; needs your judgment to upgrade.
- The definition of "truth-tracking" — what makes a Claim verified vs. contradicted vs. needs-more-evidence.
- What counts as `axiom_authority` — is it only you? When does a council get the authority? Who else can sign Doctrine?
- What gets *retired* vs. *revived*. Decay-revive philosophy is in chetana — the *thresholds* are yours.
- What this system **refuses to claim** (this is the negative space; almost more important than what it asserts).

### F.2 Agents can draft / infer
- Property schemas (the field list inside an ObjectType).
- Test scaffolding for new types.
- Migration plans for existing data.
- Audit reports against the substrate.
- Sample instances for new types.
- UI views over typed data.
- Documentation of ObjectTypes.
- The `record_dispatch` / `record_gate_decision` instrumentation in `agent_runner`.

### F.3 Must be co-created
- The grammar of `ProductThesis` (what fields, what gates, what success criteria).
- The taxonomy of `ValueEvent` (you decide the categories; an agent can populate from history).
- The semantics of `GateDecision.reason` — agent emits it, but you decide what level of detail is mandatory.
- The ontology evolution rule — what's the process for adding a new ObjectType? Today there's no rule, which means anything can grow. This is a load-bearing absence.
- Agent identity / authority model — what permissions does each role enum value confer?

---

## G. Semantic Ontology v0

Compact upper ontology — 18 types. Where the type exists today, line citation. Where it's recommended-new, marked `NEW`.

```yaml
HumanOperator:                          # NEW
  description: Singleton — Dhyana. The S5, the axiom signer.
  required_properties: [name, axiom_authority]
  allowed_links: [signed, approved]
  allowed_actions: [SignDoctrine, ApprovePromotion, ApproveGateProposal, RetireClaim]
  gates: [none — is the gate floor]

Agent:                                  # ontology.py:951 (AgentIdentity)
  description: Any actor that mutates substrate state.
  required_properties: [name, agent_id, role, status, provider, model]
  allowed_links: [executed, claimed, contributed]
  allowed_actions: [Spawn, Retire, ClaimTask]
  gates: [AHIMSA on Spawn]

Signal:                                 # NEW
  description: Observation, pre-adjudication. Entry to inquiry/opportunity loops.
  required_properties: [source, timestamp, raw_payload, observer]
  allowed_links: [generated, supports, refutes]
  allowed_actions: [ObserveSignal]
  gates: [AHIMSA on payload]

Claim:                                  # NEW
  description: Asserted proposition. The atom of knowledge.
  required_properties: [statement, proposer, status (asserted|verified|contradicted|retired), confidence]
  allowed_links: [evidenced_by, contradicted_by, became_doctrine]
  allowed_actions: [AssertClaim, AdjudicateClaim, RetireClaim]
  gates: [DOGMA_DRIFT, STEELMAN, ANEKANTA on assert; SATYA on adjudicate]

Evidence:                               # NEW
  description: Anything that supports/refutes a Claim.
  required_properties: [kind, claim_id, direction, strength, source_artifact]
  allowed_links: [evidences, refutes]
  allowed_actions: [AttachEvidence]
  gates: [SATYA]

Question:                               # NEW
  description: Open inquiry. Becomes a Claim when answered.
  required_properties: [text, opener, status (open|answered|abandoned)]
  allowed_links: [answered_by, generated_by]
  allowed_actions: [AskQuestion, AnswerQuestion, AbandonQuestion]
  gates: [none]

Doctrine:                               # NEW
  description: Revisable rule. Distinct from Axiom (immutable).
  required_properties: [text, signer (HumanOperator), version, status]
  allowed_links: [derived_from_claim, supersedes]
  allowed_actions: [SignDoctrine, ReviseDoctrine, RetireDoctrine]
  gates: [requires HumanOperator]

ActionProposal:                         # ontology.py:1262
  description: Proposed mutation, pre-gate.
  status: typed but unrecorded (gap #1)
  required_properties: [proposer, intent, draft_params]
  allowed_links: [gated_by, executed_as]
  allowed_actions: [ProposeAction]

GateDecision:                           # ontology.py:1301
  description: TelosGatekeeper output for an ActionProposal.
  status: typed but unrecorded (gap #1)
  required_properties: [proposal_id, decision (ALLOW|BLOCK|REVIEW), gate_results, reason]
  allowed_links: [gates, blocked]

ExecutionLease:                         # ontology.py:1332
  description: Live handle for an approved action.
  required_properties: [proposal_id, agent_id, leased_at, expires_at]
  allowed_actions: [LeaseAction, ReleaseLease]

KnowledgeArtifact:                      # ontology.py:1065
  description: Persistent output. Brief, paper, prompt, measurement, code, model output.
  required_properties: [title, artifact_type, content, provenance]
  allowed_actions: [Verify (SATYA), Index, Publish (BHED_GNAN, STEELMAN, DOGMA_DRIFT, CONSENT)]

Outcome:                                # ontology.py:1372
  description: Empirical result of an action. 1,806 live instances.
  required_properties: [action_id, result, verified_at]

ValueEvent:                             # ontology.py:1402
  description: Telos-relevant impact. Not synonymous with money. 1,803 live.
  required_properties: [outcome_id, kind (NEEDS TAXONOMY — section K), magnitude]

Contribution:                           # ontology.py:1438
  description: Attribution of ValueEvent to actor. 1,803 live.
  required_properties: [value_event_id, actor_id, share]

WitnessLog:                             # ontology.py:1175
  description: Observation of a process moment. Every gate-decision ought to write here.
  required_properties: [observation, observer, context]

TypedTask:                              # ontology.py:1110
  description: Discrete unit of work. 75 live.

EvolutionEntry:                         # ontology.py:1142
  description: Proposed change to the system itself. Requires AHIMSA + SATYA + REVERSIBILITY.

Experiment:                             # ontology.py:887
  description: Research run. R_V experiments live here.
```

That's 18 upper types. Five new (HumanOperator, Signal, Claim, Evidence, Question, Doctrine — actually six). Twelve already typed.

Conspicuously *not* included v0: ProductThesis, Opportunity, MarketSignal, Capability, Loop, Memory, Paper-as-distinct-from-KnowledgeArtifact (Paper is at line 923 today; consider folding into KnowledgeArtifact), CustodianRole (kept; in use), VentureCell (kept; pre-Ginko).

---

## H. Action Ontology v0

```yaml
ProposeAction:
  actor_types: [Agent, HumanOperator]
  input_objects: [intent_string, draft_params, optional inputs]
  output_objects: [ActionProposal]
  required_gates: [none — proposal is read-only intent]
  witness_events: [WitnessLog]
  failure_modes: [missing actor, malformed params]

EvaluateGate:
  actor_types: [TelosGatekeeper (system)]
  input_objects: [ActionProposal]
  output_objects: [GateDecision]
  required_gates: [n/a — this IS the gate]
  witness_events: [WitnessLog (always)]
  failure_modes: [gate registry corruption, kernel signature mismatch]

ExecuteLeased:
  actor_types: [Agent]
  input_objects: [GateDecision (decision=ALLOW)]
  output_objects: [ExecutionLease, side effects]
  required_gates: [already enforced upstream by EvaluateGate]
  witness_events: [WitnessLog]
  failure_modes: [lease expiry, idempotency violation]

RecordOutcome:
  actor_types: [Agent (auto), HumanOperator (override)]
  input_objects: [ExecutionLease, result_payload]
  output_objects: [Outcome]
  required_gates: [SATYA on result_payload (no fabricated metrics)]
  witness_events: [WitnessLog]
  failure_modes: [fabricated metrics — currently the dominant risk]

RecordValueEvent:
  actor_types: [Agent (auto)]
  input_objects: [Outcome, value_kind, magnitude]
  output_objects: [ValueEvent]
  required_gates: [SATYA, DOGMA_DRIFT (no inflated value claim)]
  witness_events: [WitnessLog]
  failure_modes: [inflated magnitude, missing evidence link]

ObserveSignal:
  actor_types: [Agent, HumanOperator]
  input_objects: [source, payload]
  output_objects: [Signal]
  required_gates: [AHIMSA (input scrub)]
  witness_events: [WitnessLog]
  failure_modes: [PII leak in payload, source spoofing]

AssertClaim:
  actor_types: [Agent, HumanOperator]
  input_objects: [statement, supporting_signals]
  output_objects: [Claim (status=asserted)]
  required_gates: [DOGMA_DRIFT, STEELMAN, ANEKANTA]
  witness_events: [WitnessLog]
  failure_modes: [unsupported claim, hidden conflicts of interest]

AdjudicateClaim:
  actor_types: [HumanOperator (canonical), Agent (provisional)]
  input_objects: [Claim, Evidence[]]
  output_objects: [Claim (status=verified|contradicted)]
  required_gates: [SATYA, ANEKANTA]
  witness_events: [WitnessLog]
  failure_modes: [premature closure, evidence asymmetry]

ConvertClaimToDoctrine:
  actor_types: [HumanOperator only]
  input_objects: [Claim (status=verified)]
  output_objects: [Doctrine]
  required_gates: [requires HumanOperator authority]
  witness_events: [WitnessLog (mandatory)]
  failure_modes: [agent attempts to self-promote — must be blocked]

RegisterAgent:
  actor_types: [HumanOperator, system (orchestrator)]
  input_objects: [name, provider, model, capabilities]
  output_objects: [AgentIdentity]
  required_gates: [AHIMSA]
  witness_events: [WitnessLog]
  failure_modes: [provider misconfig, capability inflation]

ApprovePromotion:
  actor_types: [HumanOperator only]
  input_objects: [EvolutionEntry]
  output_objects: [EvolutionEntry (state=promoted)]
  required_gates: [AHIMSA, SATYA, REVERSIBILITY]
  witness_events: [WitnessLog (mandatory, audit_all)]
  failure_modes: [agent self-promotion, irreversible damage]
```

---

## I. What NOT to Encode Yet

The temptations, named so you can resist them:

1. **SubCompany / Spinout as ObjectType**. You have a `spinouts/` folder in dharma_swarm. Don't type it until at least one spinout has 3 months of revenue. Until then, a folder is right-sized.
2. **NewWorldOrder / superhub / Shakti-changes-the-world as a public surface**. The structural invariant beneath these phrases — *self-referential systems converging on shared attractors* — is fine as private worldview. Don't expose it as a product noun. Founders who lead with cosmology lose credibility.
3. **ShaktiPulse / ShaktiSignal / vague affective objects**. The four Shakti energies are tagged on existing ObjectTypes (ResearchThread.shakti_energy, etc.) — that's the right level. Adding ShaktiPulse as its own type would be vibes-as-data.
4. **Generic Insight without Evidence**. Skill: `chetana-ingest` lets you stage atoms. Resist promoting "Insight" as a typed object — Claim + Evidence is the discipline; Insight without evidence is the failure mode.
5. **Commerce objects (Customer, Subscription, Invoice) before ValueEvent taxonomy is decided**. You have ValueEvent. Define its kinds first. Commerce objects are *projections* of certain ValueEvent kinds, not parallel types.
6. **Rust / Go rewrites of `dharma_swarm.ontology`**. Python-as-substrate is fine for now. Rewrite when you have hot paths that profile-prove a bottleneck.
7. **Dashboard surfaces over substrate that hasn't ticked daily for 14 days**. UI is only as honest as the substrate. The brief is markdown for a reason.
8. **Memory as ObjectType**. Memory is a projection of every other type via chetana. Adding it would create circular reference soup.
9. **`Loop` as ObjectType**. Until at least one loop is closed and you want runtime status as queryable — keep it as markdown.
10. **OpenClaw revival, content-factory v2**. The post-mortem at `~/.dharma/knowledge/wiki/concepts/openclaw-sunset.md` exists for a reason.

---

## J. Next Three Repo Moves (concrete, sequenced)

The Operator Brief is **shipped today**. The first move is to make sure it doesn't backslide. Then close the governance audit gap. Then add Signal/Claim/Evidence — the smallest expansion that makes the Inquiry loop typeable.

### J.1 Stabilize Operator Brief (this week, ≤ 3 days)
- Verify the cron actually runs without manual reruns. Prove it by checking WitnessLog count on 2026-05-02, 2026-05-03.
- Diversify the Outcome surface: today's brief is 5× `eval_probe_task` because that's what's in the DB. Get 2 non-eval Outcomes into the substrate (e.g. one R_V experiment Outcome, one trading-lab Outcome) so the brief proves it can read real signal.
- Track on falsification milestones: 2026-05-08 WitnessLog ≥ 7 (one per day); 2026-05-15 you-still-read-it.

### J.2 Close the governance audit gap (≤ 2 days)
- Instrument `agent_runner.py` (around lines 2875, 3013) to call `record_dispatch(ActionProposal)` and `record_gate_decision(GateDecision)` for every action that goes through `OntologyActionGateway`.
- Add an integration test: gateway-mediated action MUST produce one ActionProposal and one GateDecision in the DB. Fail loud if not.
- Side benefit: once GateDecision is populated, you get the *first audit query* — "show me every BLOCKed action in the last 7 days." This is the smallest artifact that would make you trust the system more tomorrow.

### J.3 Add Signal + Claim + Evidence + Question (≤ 1 week)
- Four ObjectTypes. Mostly schema work — they're small.
- Don't wire actions yet beyond `ObserveSignal` and `AssertClaim`. No Adjudicate flow until you've used AssertClaim manually for 3 days.
- Acceptance: chetana-ingest pipes raw notes into Signal; you can manually promote a Signal to Claim; the brief surfaces "claims awaiting evidence" alongside Outcomes.
- This unlocks the Inquiry loop and is the prerequisite for any Dharma-Radar work.

**Explicitly deferred** (do not start before J.3 is shipped):
- AGENTS.md substrate-native definition
- Raw-write bypass scanner (would be useful but premature; today only 2 directors bypass — fix them by hand)
- Dharma Radar spec
- ProductThesis ObjectType
- HumanOperator ObjectType (interesting, but extending AgentIdentity with `is_principal: bool` is the cheaper move)

---

## K. Questions Only You Can Answer

These are the founder-judgment questions. Agents can draft against any answer; only you can pick.

1. **What must this system never optimize away?** Candidates: the human-review step on Doctrine creation; the immutability of the 25 axioms; the substrate-honest content of the Operator Brief (no editorial sweetening); the requirement that `record_outcome` only fire on *measured* results.
2. **What does ValueEvent mean beyond money?** Propose a starting taxonomy, then refine: `decision_clarity`, `falsification_passed`, `cited_artifact`, `peer_uptake`, `revenue`, `time_saved`, `risk_avoided`, `axiom_signed`. Pick 5–7. The brief, the trading lab, and the paper all want to write into this taxonomy.
3. **What kinds of claims should Dharma Swarm refuse to make?** Hard ones to start the list: claims about another human's interior state; claims that R_V proves consciousness; claims about market direction with confidence > X%; claims that bypass the 15–25% empirical band on substrate-relevant inner states.
4. **What authority can an external agent earn, and what is permanently reserved to you?** Today every role is permission-equivalent within `AgentIdentity`. Decide: does a `researcher` role get `AssertClaim` authority? `AdjudicateClaim`? `SignDoctrine`? Almost certainly the answer for SignDoctrine is *only HumanOperator forever*; the others need a graded answer.
5. **Is dharmic-agora dormant because deprioritized, or because waiting on swarm-internal ontology to mature?** This decides whether to revive it now or close it as completed-research and roll its lessons into swarm.
6. **Is "ROE / Recursive Ontology Engine" a future codebase or a rename of `dharma_swarm.ontology`?** If the former, what does it have that the existing module doesn't? If the latter, just rename.
7. **What's the smallest artifact, beyond today's brief, that would make you trust the system more tomorrow?** My guess: a query that returns "every gate BLOCK in the last 7 days" with proposer, target, reason. That's the audit proof for the governance loop. But you decide what would actually move you.
8. **Falsification of the whole substrate**: if it's 2026-09-01 and the system has NOT done X, you'd kill it. What is X? Possible answers: "produced one ValueEvent that paid for its own compute"; "blocked one action you would later have regretted"; "produced one Claim you cited in a paper or post." Pick.

---

## Concluding stance (non-poetic, source-grounded)

The substrate has 16 typed objects, a fail-closed gateway, 25 signed axioms, 11 gates, and 1,800+ Outcomes flowing. The first ontology-grounded artifact for *you* — the daily brief — shipped today.

The biggest gap is not the absence of types. It's the absence of **recorded decisions**: agent_runner skips ActionProposal/GateDecision creation, so governance is unauditable. Closing that is one engineer-day.

The second biggest gap is **director shadow**: two modules execute without registering as Agents. Half a day.

After those two: Signal/Claim/Evidence/Question give you the Inquiry loop. After that: the Opportunity loop is naturally typeable.

Don't add ProductThesis, Opportunity, MarketSignal, Capability, Loop, or Memory yet. Don't spin out a separate ROE codebase. Don't expose superhub or ShaktiPulse as public surface. Don't rewrite in Rust.

Run the brief. Audit the gates. Type the inquiry chain. That's the work.

---

**Verification appendix** — claims I cannot fully verify and you should sanity-check before trusting this document:
- The 1,806 / 1,803 / 1,803 DB counts are quoted from `~/dharma_briefs/MASTER_SYNTHESIS_2026-05-01.md` (today, by Codex). I did not run a fresh `sqlite3 ~/.dharma/ontology.db` count.
- "agent_runner.py:2875,3013 calls record_outcome / record_value_event / record_contribution but never record_dispatch / record_gate_decision" — quoted from the same master synthesis. I did not grep agent_runner directly.
- The R_V paper path issue (CLAUDE.md says `~/mech-interp-latent-lab-phase1/`; actual is `~/ALL MECH INTERP/...`) — verified by `find` at synthesis time.
- "VWrite does not exist as a separate codebase" — verified by depth-2 home-directory search; LIKELY rather than CONFIRMED because I did not search depth ≥ 3.

If any of those four claims is wrong, the Section J prioritization may shift slightly but the structure of A-K stands.
