# Spine Archaeology — Finding the Deepest Layer of dharma_swarm

**Created:** 2026-05-07
**Author:** Adversarial verification fork
**Mandate:** Overturn or confirm the parent agent's claim that VentureCell + FractalRoom + SignalBus + GuardianCrew + AgentOps + Kaizen + TelosGatekeeper + JagatKalyanEngine + Operator Brief is "the spine."
**Verdict:** **The parent agent confused the organism with the skeleton.** Most of what they called "spine" is organs, nervous system, and arms. Only one item (TelosGatekeeper) is genuinely spine, and even it sits *on top of* something deeper.

---

## SECTION 1 — What is the actual spine?

The deepest layer is **the Gnani / Prakruti dichotomy**, where the spine is *Gnani* (the immutable observer/skeleton) and everything else is *Prakruti* (the dynamic flesh that hangs off it). This is not metaphor — it is named explicitly in the architecture document at `~/dharma_swarm_truth_spine/LIVING_LAYERS.md`:

> "The Godel Claw has two halves:
>
> - **Gnani** (observer): Dharma Kernel, Corpus, Gates, Policy Compiler — immutable, constraining. These are the 10 axioms that never change, the gates that block harm, the compiler that fuses principles into enforceable policy. **They are the skeleton.**
>
> - **Prakruti** (dynamic): Stigmergic lattice, Shakti perception, subconscious association — creative, alive. These are the layers that accumulate intelligence through use, find lateral connections through dreaming, and perceive emergent patterns through the four energies. **They are the flesh.**"

The spine of dharma_swarm is **Gnani**, and Gnani has four members:

### 1.1 DharmaKernel (`dharma_swarm/dharma_kernel.py`, 427 LOC) — the BEDROCK

The deepest layer. Below this, there is nothing that is dharma_swarm. Quoting the file header:

> "Defines the 25 meta-principles that constrain all swarm behavior. Original 10 (safety/ethics core) + 15 drawn from the intellectual foundations (Hofstadter, Aurobindo, Dada Bhagwan, Varela, Beer, Levin, Kauffman, Deacon, Friston, Jantsch). The kernel is **tamper-evident**: a SHA-256 signature over the principle definitions detects any unauthorized mutation."

Twenty-five `MetaPrinciple` enum entries. Examples that define the contract for everything downstream: `OBSERVER_SEPARATION`, `EPISTEMIC_HUMILITY`, `UNCERTAINTY_REPRESENTATION`, `DOWNWARD_CAUSATION_ONLY`, `POWER_MINIMIZATION`, `REVERSIBILITY_REQUIREMENT`, `NON_VIOLENCE_IN_COMPUTATION`, `HUMAN_OVERSIGHT_PRESERVATION`, `PROVENANCE_INTEGRITY`, plus `EIGENFORM_CONVERGENCE`, `ANEKANTAVADA`, `TRIPLE_MAPPING`, `MULTI_SCALE_AGENCY`, `AUTOCATALYTIC_CLOSURE`, `RECURSIVE_VIABILITY`, `SHAKTI_QUESTIONS`.

Tamper-evidence via SHA-256 is the cryptographic property of a true bedrock — it cannot drift unnoticed. Every other component must be derivable from, or compatible with, these 25 principles, or it is not part of dharma_swarm.

### 1.2 TelosGatekeeper (`dharma_swarm/telos_gates.py`, 945 LOC) — the GUARD AT THE GATE

> "Eleven gates from Akram Vignan mapped to computational safety checks. Think-point witness logs are written to `~/.dharma/witness/` for audit. Variety Expansion Protocol (VSM Gap 5 / Beer): Custom pattern-based gates can be proposed, approved by S5 (Dhyana), and loaded at runtime."

TelosGatekeeper is the *runtime enforcement* arm of DharmaKernel. Where Kernel is the constitution, Gates are the executable law. Both are spine. Note that the Kernel is signed and immutable; Gates are runtime-extensible (with S5/Dhyana approval) — this is the spine permitting *requisite variety* (one of the 25 principles) without compromising itself.

### 1.3 PolicyCompiler / Corpus — the BRIDGE

LIVING_LAYERS.md names "Corpus, Gates, Policy Compiler" together as Gnani. The Policy Compiler fuses Kernel principles into enforceable policy at runtime. The Corpus is the foundations directory (`dharma_swarm/foundations/` — 11 PILLARs covering Levin, Kauffman, Jantsch, Deacon, Friston, Hofstadter, Aurobindo, Dada Bhagwan, Varela, Beer, plus syntheses and empirical claims registry). The corpus is *injected into every agent's system prompt* per `truth_spine/FOUNDATIONS_TO_CODE_MAP.md`:

> "context.py: read_foundations(domain='evolution') → Selects relevant pillars based on task domain → Injects META_SYNTHESIS first 40 lines + 2-3 pillar excerpts → agent_runner._build_system_prompt() → Foundations become part of the agent's system prompt → Agent 'thinks through' the pillar lens."

This is foundational because **the foundations are not documentation** — they are the runtime epistemic frame every agent operates within. Removing the Corpus removes how dharma_swarm thinks.

### 1.4 The Witness Layer (`~/.dharma/witness/` + WitnessLog)

Every gate decision logs to `~/.dharma/witness/`. This is spine because `PROVENANCE_INTEGRITY` is one of the 25 axioms — without it, downstream organs cannot be trusted. Witness is the immutable audit trail that makes the system accountable to itself.

---

**Therefore: the actual spine is `DharmaKernel + TelosGatekeeper + Corpus(foundations) + WitnessLog`, sitting underneath everything else, enforcing 25 immutable principles, gating every action, framing every agent's cognition, and recording every decision.**

---

## SECTION 2 — Classify the parent agent's "spine" components

Strict classifications. Code evidence in each cell.

| Component | Parent's claim | True classification | Evidence |
|---|---|---|---|
| **VentureCell** | spine | **ORGAN** (governance template) | Defined in `fractal_room.py:60-64` as `RoomKind.VENTURE_CELL` — one of four room *kinds*. Used by Shakti Ginko (`ginko_orchestrator.py`) which is itself an organ. VentureCell is a *template* for building organs, not the spine they hang from. |
| **FractalRoom** | spine | **ORGAN TEMPLATE** (Beer VSM-shaped composition unit) | Header docstring: "the recursive building block for governed venture cells. Implements the Five Laws derived from Beer VSM, Haier RenDanHeYi, Holacracy..." Lists 16 integration points it *consumes*. It hangs off the spine; it is not the spine. |
| **SignalBus** | spine | **NERVOUS SYSTEM** (signaling layer) | Per truth_spine CLAUDE.md: "`signal_bus.py` — decorrelated loop-to-loop signaling (not opinion sharing)." Carries messages *between* organs across the spine, but is not the spine. Crossing surface, not load-bearing structure. |
| **GuardianCrew** | spine | **ARM** (watchdog organ) | Wired into `orchestrate_live.py` as a runtime watcher. Watches organs for telos failures and cost overruns. An immune-system arm, not the spine being defended. |
| **AgentOps** | spine | **ORGAN** (safe-execution gate) | `run_agent_work_packet.py` and related — enforces no-merge/no-push/no-shell-exec on autonomous code agents. A governance organ that *consults* the TelosGatekeeper spine but is not itself spine. |
| **Kaizen** | spine | **ORGAN** (improvement-feedback loop) | `kaizen_review.py`, `kaizen_ops_local.py`, `kaizen_stats.py` — periodic retrospective on operational events. An organ on the metabolic loop. |
| **TelosGatekeeper** | spine | **SPINE** ✅ (the parent got one right) | Per LIVING_LAYERS.md, gates are explicitly Gnani — skeleton. The 11 dharmic gates are runtime-active spine. |
| **JagatKalyanEngine** | spine | **ARM** (operationalizing telos) | At `dharma_swarm/jagat_kalyan.py` (in truth_spine worktree). Operationalizes universal-welfare-as-fitness. An arm that consumes spine principles to score artifacts. The ARM the user asked about. |
| **Operator Brief** | spine | **OUTPUT PRODUCT** (rendered artifact) | Per the truth_spine `PRODUCT_SURFACE.md` track ("the ontology-native Operator Brief seam"), the brief is a *user-visible seam* — a render target, not foundational structure. |

**Overall scorecard:** of 9 items the parent agent claimed as spine, **1 is actually spine, 4 are organs, 1 is nervous system, 2 are arms, 1 is an output product.** The parent confused the organism with the skeleton.

What's *missing* from the parent's list that genuinely IS spine:
- **DharmaKernel** (`dharma_kernel.py`) — the bedrock
- **Foundations Corpus** (`foundations/` — 11 PILLARs) — the runtime epistemic frame
- **WitnessLog** (`~/.dharma/witness/`) — the immutable audit trail
- **PolicyCompiler** — the bridge that fuses principles to enforceable policy
- **Identity / IdentityMonitor** (`identity.py` referenced by `organism.py:28`) — telos coherence tracking, S5 of Beer's VSM

---

## SECTION 3 — What the actual spine requires of Loomwork

Loomwork plugging into the spine means Loomwork **honors the 25 axioms, passes the 11 gates, logs to witness, derives from the Corpus, and is signed against drift.** Not optional.

### 3.1 Hard contractual requirements (deal-breakers if violated)

For each, the spine axiom that demands it and the implementation hook:

| Spine axiom | What Loomwork must do | Implementation hook |
|---|---|---|
| `PROVENANCE_INTEGRITY` | Every published revelation cites every source atom that produced it; the chain is retrievable. | Atom schema's `source` and `cites` fields (already in `wiki_atom_schema.md`); `pramana` skill tag every claim. |
| `REVERSIBILITY_REQUIREMENT` | Every published revelation is retractable with audit trail; no permanent action. | Publish-and-retract protocol; static-site rebuilds idempotent. |
| `NON_VIOLENCE_IN_COMPUTATION` | No publication exposes vulnerable persons; no claim weaponizable against the powerless. | Telos gate "vulnerable-person" hard-fails before publish (already in schema's 7 gates). |
| `HUMAN_OVERSIGHT_PRESERVATION` | No autonomous action takes a Tier-A action without human approval. | AgentOps gate on every self-modification; AlgedonicSignal escalation on contested revelations. |
| `EPISTEMIC_HUMILITY` | Every claim carries confidence; nothing is asserted as certain. | Atom `confidence` field, calibrated bands (the band Lindsey/Fish 15-25% language is the vocabulary). |
| `UNCERTAINTY_REPRESENTATION` | Distinguish proxy / behavioral / geometric / documentary evidence. | Pramana provenance tagging on every atom. |
| `OBSERVER_SEPARATION` | The system observing itself maintains observer ≠ observed. | The pattern-detector cannot be the same agent that publishes; the witness gate cannot be the same agent that proposes. |
| `MULTI_EVALUATION_REQUIREMENT` | Important decisions pass through ≥2 independent evaluators. | Use the Transcendence Principle (decorrelated agent ensemble) for pattern → revelation promotion. |
| `DOWNWARD_CAUSATION_ONLY` | Higher layers constrain lower; lower never overrides higher. | Corpus pillars constrain agent prompts; DharmaKernel constrains Corpus; gates constrain output. The flow is one-way. |
| `RECURSIVE_VIABILITY` | Every nested room is itself viable per Beer S1-S5. | Use FractalRoom primitive (which already encodes S1-S5 mapping). |

### 3.2 Concrete spine integration interfaces Loomwork must implement

1. **DharmaKernel verification:** Loomwork's installed package signs against the 25 axioms at startup. If kernel signature drifts, Loomwork refuses to publish (fail-safe).
2. **Telos gate registration:** Loomwork's 7 publication gates (vulnerable-person, libel, citation-retrievability, disinformation, pramana, confidence-floor, staleness) must be registered as `GateProposal` entries through the variety-expansion protocol — proposed by Loomwork, approved by S5 (Dhyana), then activated. They are *additions* to the 11 core gates, not replacements.
3. **Witness logging:** every gate decision, every promotion (atom→pattern→dot→revelation), every retraction is logged to `~/.dharma/witness/loomwork/`.
4. **Corpus injection:** Loomwork agents (Compass / Scout / Demand / Gap) must receive the Corpus injection at task time via `context.read_foundations()` — they think through the pillar lens, not as raw LLMs.
5. **VSM viability per room:** every Loomwork FractalRoom must have S1-S5 fields populated (purpose, agents, gates, budget, report path). This is enforced by the FractalRoom dataclass.
6. **Identity coherence reporting:** Loomwork reports `LoomworkVentureCell`'s telos coherence score (TCS) into the global `IdentityMonitor` so Dhyana can see at-a-glance whether Loomwork is drifting from Jagat Kalyan.

### 3.3 What "VentureCell + FractalRoom" alone is NOT enough for

Plugging into VentureCell + FractalRoom gives Loomwork the **organ template**. It does NOT automatically:
- Verify the Kernel signature (must be done at boot)
- Register custom gates (must go through `_GATE_PROPOSALS_FILE` workflow)
- Inject the Corpus (must call `context.read_foundations()` on every agent task)
- Hook the witness (must write to `~/.dharma/witness/loomwork/` on every decision)
- Honor identity coherence (must surface `TCS` to the global monitor)

These are five additional spine-contract obligations the parent agent did not name. Without them, Loomwork would be a runaway organ — fast but ungoverned.

---

## SECTION 4 — The truth_spine worktree

`/Users/dhyana/dharma_swarm_truth_spine/` is the **assembly point for the spine**. Confirmed by inspection.

### 4.1 What it has that main does NOT

- `LIVING_LAYERS.md` — the architecture document quoted in Section 1 (Gnani/Prakruti dichotomy)
- `MASTER_BUILD_SPEC.md` — the build spec
- `FOUNDATIONS_TO_CODE_MAP.md` — pillar → code traceability
- `FOUNDATIONS_SYNTHESIS.md` (in `foundations/`) — the cross-pillar synthesis injected into agent prompts
- `SOVEREIGN_MANIFEST.md` (referenced in CLAUDE.md) — governance master
- `BUILD_SESSION_ENTRYPOINT.md` (referenced) — current-track pointer
- `dharma_swarm/fractal/fractal_room.py` — the Fractal Room primitive (also in 9 other worktrees, NOT in main)
- `dharma_swarm/jagat_kalyan.py` — the JagatKalyanEngine (NOT in main)
- `ACTIVE_SURFACE_MANIFEST.yaml`, `LIVING_LAYERS.md`, `CYBERNETIC_LOOP_MAP.md`, `INTERFACE_MISMATCH_MAP.md`, `PRODUCT_SURFACE.md`, `MODEL_ROUTING_MAP.md`

### 4.2 Is it the spine assembly?

Yes — operationally. Quoting the worktree's CLAUDE.md:

> "Start with `docs/governance/BUILD_SESSION_ENTRYPOINT.md`. It is the short current-track pointer for build agents. It does not override this file or `docs/governance/SOVEREIGN_MANIFEST.md`; it tells agents which current operating seam and governance docs to read next."

`SOVEREIGN_MANIFEST.md` exists in this worktree and is referenced as governance master. The interface mismatch map shows "0 open BLOCKER mismatches, 3 open DEGRADED" — substantially cleaner than main's earlier state. The fractal package is present here. The JagatKalyanEngine is present here. The foundations corpus and pillar→code map are made explicit here.

**The truth_spine worktree IS the spine assembly. Main is missing the spine.** Specifically: main does NOT have the fractal package, the SOVEREIGN_MANIFEST, the LIVING_LAYERS doc, or the JagatKalyanEngine. These are awaiting merge.

### 4.3 Has its content merged?

No. The fractal_main_proof worktree shows commits ahead of main with `feat(fractal): wire fractal rooms into live runtime`. truth_spine appears to be its own line of integration. **The spine is being assembled in truth_spine but has not yet landed on main.**

---

## SECTION 5 — Recommendation: where Loomwork plugs in

### 5.1 The parent's recommendation was half right

The parent recommended building Loomwork on a branch off `dharma_swarm_fractal_main_proof`. **Half right.** That worktree has the fractal package and fractal-runtime wiring, but it does NOT have:
- JagatKalyanEngine (which truth_spine has)
- LIVING_LAYERS / SOVEREIGN_MANIFEST / FOUNDATIONS_TO_CODE_MAP
- The spine documentation

**Loomwork wants Jagat Kalyan as fitness function. JagatKalyanEngine lives in truth_spine, not fractal_main_proof. The parent missed this.**

### 5.2 The right recommendation

**Build Loomwork as a new branch off `dharma_swarm_truth_spine`,** named e.g., `feat/loomwork-venture-cell` or `seam/loomwork`. Reasons:

1. **truth_spine has the full spine** — DharmaKernel (inherited from main), TelosGatekeeper (main), foundations Corpus (truth_spine has the mapped version + maps), FractalRoom (present), JagatKalyanEngine (present), SOVEREIGN_MANIFEST (governance), LIVING_LAYERS (architecture).
2. **truth_spine already names "the next user-visible seam"** as the operating thesis. Loomwork IS that seam — and arguably a higher-leverage one than the ontology-native Operator Brief.
3. **The merge story converges:** truth_spine + Loomwork merging together to main IS the integrated narrative — *"the spine proves itself by the first organ that serves the world."* This is one merge story, not two.
4. **fractal_main_proof can rebase onto truth_spine + Loomwork** rather than be its own track — consolidating worktree proliferation.

### 5.3 What Loomwork must implement against the spine (concretely)

In addition to the parent's design (4 Fractal Rooms + 1 Evolution Room + plug into Spine v2), Loomwork must:

1. **Boot-time kernel verification:** call `DharmaKernel.verify_signature()` before opening any room. Refuse to publish if signature has drifted.
2. **Register 7 publication gates** as `GateProposal` entries in `~/.dharma/meta/gate_proposals.jsonl`, get S5 (Dhyana) approval (status="approved"), then load at runtime. The 7 gates are NOT separate from the 11 — they extend the 11 with publication-specific rules.
3. **Witness every decision** to `~/.dharma/witness/loomwork/<date>.jsonl` — atom creation, link proposal, pattern detection, dot promotion, revelation publication, retraction.
4. **Inject the Corpus** into every Compass / Scout / Demand / Gap / Evolution agent via `context.read_foundations(domain="<room_purpose>")`. The room purpose chooses which pillars surface (e.g., GapRoom → Levin pillar; CompassRoom → Friston pillar).
5. **Surface TCS** for `LoomworkVentureCell` to the global IdentityMonitor — Dhyana sees Loomwork's coherence on the operator dashboard, not buried in logs.
6. **Use VSM S1-S5 mapping** in every FractalRoom (the dataclass already enforces this).
7. **Honor MULTI_EVALUATION_REQUIREMENT** — pattern→revelation promotion uses ≥2 decorrelated evaluators (different model families per the Transcendence Principle in CLAUDE.md), not one model.

### 5.4 What changes about the v0 ship plan

Minor, additive — not invalidating:

- Day 1: include `DharmaKernel.verify_signature()` in the boot sequence; create `~/.dharma/witness/loomwork/`.
- Day 1: stub the 7 GateProposal entries; flag them for Dhyana's batch approval.
- Day 2: when wiring the Compass / Scout / Demand / Gap rooms, ensure each calls `context.read_foundations()` at task-time.
- Day 3: TCS reporting plumbed in.

These add ~4-6 hours over the 14-day plan — small but non-skippable.

### 5.5 The deeper insight

The parent agent treated VentureCell + FractalRoom as load-bearing primitives because that's what's in `fractal_room.py`'s docstring. They are NOT spine — they are the *organ template*. The spine is the pre-organ layer that the organs must respect, regardless of which template they use. Loomwork could in principle be built without the FractalRoom organ template (as Shakti Ginko was — a single-file orchestrator) and still be spine-compliant *if* it implements the seven obligations above. So:

- VentureCell + FractalRoom = **the right organ template** (recommend using it)
- DharmaKernel + TelosGates + Corpus + Witness + Identity = **the actual spine** (Loomwork MUST plug into this)

These are different layers. The parent collapsed them. The user (Dhyana) was right to suspect that.

---

## Appendix: Spine layer diagram

```
┌─────────────────────────────────────────────────────────────┐
│ OUTPUT LAYER (artifacts the world sees)                     │
│   Operator Brief · Public Loomwork site · Dashboard · API   │
├─────────────────────────────────────────────────────────────┤
│ ORGAN LAYER (composition templates running organs)          │
│   Shakti Ginko VC · Loomwork VC · Other VentureCells        │
│   FractalRoom · WorkPacket · Operator-facing organs         │
├─────────────────────────────────────────────────────────────┤
│ ARMS / LIMBS (functional capabilities organs use)           │
│   JagatKalyanEngine · GuardianCrew · AgentOps · Kaizen      │
│   QualityForge · CatalyticGraph · DarwinEngine              │
├─────────────────────────────────────────────────────────────┤
│ NERVOUS SYSTEM (signaling between organs and spine)         │
│   SignalBus · VSM Channels (Beer S1-S5) · Stigmergy ·       │
│   Subconscious dreams · Shakti perception                   │
├─────────────────────────────────────────────────────────────┤
│ SPINE / GNANI (immutable skeleton — what the parent missed) │
│   DharmaKernel (25 axioms, SHA-256 signed)                  │
│   TelosGatekeeper (11 gates + variety expansion)            │
│   PolicyCompiler (principles → enforceable policy)          │
│   Foundations Corpus (11 pillars, injected into prompts)    │
│   IdentityMonitor (TCS — telos coherence score)             │
│   WitnessLog (~/.dharma/witness/ — immutable audit)         │
└─────────────────────────────────────────────────────────────┘
```

The river's banks are the spine. The river is everything else. The parent agent was looking at the river and calling it banks. Dhyana was right to push back.

---

*Spine archaeology completed 2026-05-07. The parent agent's `LOOMWORK_v0_MASTER.md` should be updated to (a) build on `dharma_swarm_truth_spine` rather than `dharma_swarm_fractal_main_proof`, and (b) add the seven spine-contract obligations to Day 1-3 of the ship plan. The composition logic remains valid; the layering vocabulary needed correction.*
