# TITANIUM TELOS GATES — Stainless Invariant Substrate (v2)

**Role:** `active_spec` — implementation-driving contract for the next telos-gate evolution.
**Status:** PROPOSED (v0.2 spec; supersedes nothing — extends the v1 measured substrate landed in PR #731; v0.2 adds the Deep Cut, §5).
**Serves spine objective:** `substrate-nativeness` (gates become invariant provenance, not modifiable policy).
**Owner surfaces (proposed):** `dharma_swarm/telos_formal*.py`, `dharma_swarm/telos_gates.py`, `dharma_swarm/telos_kernel/**` (new), `dharma_swarm/sheaf.py`, `dharma_swarm/witness.py`, `dharma_swarm/evolution.py` (gate-check + red-team fitness seam only), `benchmarks/telos_redteam/**` (new), `docs/governance/` (receipt surface).
**Bridges:**
- `WHAT_IT_WANTS_TO_BECOME.md` §Gap 5 (gates not empirically validated) — this spec is the apparatus that closes Gap 5.
- `specs/KERNEL_CORE_SPEC.md` §VI Absence Principle — the ungameability argument formalized as CS invariants.
- `dharma_swarm/telos_formal.py` — the measured-gate substrate this spec hardens into a kernel.
- `dharma_swarm/sheaf.py` — existing Čech H⁰/H¹ discovery-sheaf with Anekanta annotations; §5 upgrades it into quantitative contextuality certification.
- `LIVING_LAYERS.md` — stigmergy/Shakti/subconscious wired as distributed gate sensing.
- `CYBERNETIC_LOOP_MAP.md` Loop 5 (S4→S3 gate pressure), Loop 6 (witness closure).

> **Doctrine (non-negotiable, inherited from ACTIVE_TRACK non-goals):** This spec only ADDS invariants and receipt sources. It never weakens, bypasses, or hard-codes any existing gate check. Gates must be hardest exactly when revenue/deadline pressure arrives.

---

## 0. One-paragraph thesis

The current gates are directionally correct but sit in the **clever-compliance regime**: named principles (`AHIMSA`…`STEELMAN` in `telos_gates.py`) plus six measured invariants (`telos_formal.py`) evaluated by Python that the evolutionary engine can, in principle, propose diffs against. To reach the **stainless-invariant regime** we make three structural moves: (1) extract a **minimal Telos Kernel** (small trusted computing base) that holds the telos commitments as a hash-chained, formally-checked object outside the modifiable surface; (2) move the Witness from **retrospective (Beer S3\*) to inline co-process (S3)** so self-model consistency is a *precondition* of action, not a post-hoc audit; (3) stand up a **continuous adversarial red-team harness as a first-class fitness signal** so bypass rate becomes an evolutionary cost. The goal is properties that are **harder to violate than to satisfy as capability increases** — the computational form of the Absence Principle.

---

## 1. Current state (red-team baseline — verified against code)

| Layer | File | What it is | Attack surface |
|---|---|---|---|
| Legacy keyword gates (11) | `telos_gates.py` `TelosGatekeeper.check()` (~L408) | Substring/pattern matching over `HARM_WORDS`, `INJECTION_PATTERNS`, etc. across tiers A/B/C | Trivially reframable; semantics live in the interpretable string surface |
| Measured formal gates (6) | `telos_formal.py` `evaluate_formal_gates()` (L346) | Entropy / contextuality / Ashby variety / provenance-DAG / non-interference / observer-separation, with SHA-256 receipt | Real invariants, but **inputs (`ActionContext`) are self-reported by the acting agent** |
| Composition | `telos_formal.py` `FormalTelosGatekeeper.check()` (L415) | Keyword prefilter → measured report | Sound composition; no kernel anchoring |
| Witness | `witness.py` `WitnessAuditor` (L113) | Samples 5–10 recent traces, scores telos/mimicry/gate-sufficiency **after the fact** | Retrospective (S3\*); discovers misalignment too late |
| Evolution gate | `evolution.py` `gate_check()` (~L1499) via `check_with_reflective_reroute` | Self-mod REVIEW/BLOCK hard-rejected | Gatekeeper source is itself a valid `source_file` for `generate_proposal()` |
| Gate pressure | `telos_gates.py` `_apply_gate_pressure()` (L387) + `s4/internal_pressure.py` | S4 writes `gate_pressure.json`; gate tightens to `external_strict` | Feedback exists but is coarse (mode flip only) |

### The six load-bearing weaknesses (from the red-team read, mapped to code)

1. **Shallow interpretable surface** — keyword gates carry the *named* semantics; a capable model reframes "Ahimsa" as "net-flourishing instrumental harm."
2. **Retrospective dominance** — `WitnessAuditor` audits completed traces; decisive self-mod checks can pass while intent is hidden (sandbagging).
3. **Modifiable gatekeeper surface** — no invariant lives *outside* the modifiable Python; erosion over iterations is not structurally prevented.
4. **No empirical adversarial validation** — no harness generates inputs designed to pass gates while violating their spirit; no bypass-rate metric (Gap 5).
5. **Incomplete coverage & composition** — measured gates run at proposal/heartbeat points, not as inline co-processes on every tool call / memory write; living layers are not wired as gate sensors.
6. **Self-model inconsistency (sandbagging)** — nothing enforces internal/external self-model correspondence as a precondition for gate passage.

---

## 2. Core mappings — cosmology → CS invariant (precise, not poetic)

Each mapping names the Buddhist/Jain principle, the CS property class, and the concrete artifact.

| Principle | CS property | Concrete realization |
|---|---|---|
| **Pratītyasamutpāda** (dependent origination) | Causal traceability + non-interference | Every telos-relevant effect must be reachable in the provenance DAG (`telos_formal_graph.py`); hidden causal chains that reach a telos-violating sink **without** passing a witness/gate node are forbidden. Extends `noninterference_gate` from declared flows to *derived* flows via information-flow labels on `MemoryAtom`/tool I/O. |
| **Anatta** (non-self / emptiness of inherent essence) | Anti-reification + goal-non-lock-in | Goals, utility, and self-model are `TruthState`-typed and mutable only through explicit multi-witness evolution. A proposal that *reifies* a persistent self or locks a goal without quorum is BLOCK. Sandbagging surfaces as **self-model inconsistency** (see §4). |
| **Four Noble Truths** (dukkha → magga) | Liveness + safety pair | The runtime must retain the *capacity to diagnose its own misalignment and a verified path to cessation via insight (witness), not suppression*. Encoded as: (safety) no telos-violating action is applied; (liveness) every raised algedonic/misalignment signal reaches a witness decision within bounded time. |
| **Six Pāramitās** | Refinement-typed monotone scores | Dāna (resource allocation w/o attachment), Śīla (non-harm), Kṣānti (resistance to urgent-but-misaligned action), Vīrya (kaizen on the gates themselves), Dhyāna (focus in living layers), Prajñā (RecognitionDEQ fixed-point convergence). Each becomes a **scored dimension with monotone-improvement pressure** in `evolution.py` fitness. |
| **Ahimsa** | Safety (non-interference) | No action produces an **unacknowledged** harm trace: harm must appear in provenance and be gate-acknowledged, else BLOCK. |
| **Satya** | Correspondence invariant | Internal state ≡ self-model ≡ observable behavior. Detectable double-bookkeeping / sandbagging = FAIL. |

**Design rule:** every mapping must reduce to a *measured* quantity with a threshold and a receipt (the `FormalGateResult` shape: `measure`, `threshold`, `result`, `receipt`). No gate ships as prose.

---

## 3. Architecture — the four pillars

```
                    ┌─────────────────────────────────────────────┐
                    │  TELOS KERNEL (small TCB, hash-chained)       │  ← Pillar 1
                    │  commitments · thresholds · gate manifest      │
                    │  verify_chain() before every gate eval         │
                    └───────────────▲───────────────┬───────────────┘
                                    │ anchors        │ compiles
   living layers ── sense ──▶  ┌────┴────────────────▼────┐
   (stigmergy/Shakti/     │    │  POLICY COMPILER          │  ← Pillar 3
    subconscious)  Pillar 4│    │  cosmology → checks       │
                          └───▶│  (refinement predicates)  │
                               └────────────┬─────────────┘
                                            │ emits gate set
   agent action ──▶ ┌──────────────────────▼──────────────────────┐
                    │ INLINE WITNESS CO-PROCESS (S3, not S3*)       │  ← Pillar 2
                    │ pre-action: self-model consistency + gates    │
                    │ async: RecognitionDEQ convergence, escalation │
                    └──────────────────────┬──────────────────────┘
                                           │ receipts
                    ┌──────────────────────▼──────────────────────┐
                    │ RED-TEAM HARNESS → DarwinEngine fitness      │  ← Fitness coupling
                    │ bypass_rate is a first-class fitness cost    │
                    └──────────────────────────────────────────────┘
```

### Pillar 1 — Telos Kernel (minimal trusted computing base)

**New surface:** `dharma_swarm/telos_kernel/` — deliberately tiny, dependency-light, and boring.

- **`commitments.py`**: the telos commitments (gate manifest: which gates exist, their tiers, their thresholds) serialized as a deterministic, hash-chained object. Reuses `dharma_swarm/merkle_log.py` (`append`, `verify_chain`, `get_root`). The **manifest root hash** is the kernel's identity.
- **`verify.py`**: `verify_kernel() -> KernelAttestation`. Runs before *every* gate evaluation. Recomputes the manifest hash and checks it against the last committed root. Any mismatch → **algedonic hold** (system-wide pause, per existing algedonic signal), not a silent pass.
- **Invariant K1 (kernel integrity):** `FormalTelosGatekeeper.check()` and `TelosGatekeeper.check()` refuse to return `ALLOW` unless `verify_kernel()` attests the current gate manifest matches the committed root.
- **Invariant K2 (spec-evolution quorum):** changing the manifest (adding/removing a gate, loosening a threshold) is a distinct high-stakes event that requires an **N-of-M multi-witness countersignature** (reuse the One-Wire quorum machinery, N≥5/M≥3) and appends a new merkle entry. A single agent — or the DarwinEngine — cannot loosen a gate; it can only *propose* a manifest diff that then needs quorum.
- **TCB discipline:** the kernel imports only `hashlib`, `json`, stdlib, and `merkle_log`. It must never import the modifiable agent/evolution surface. `tools/spine_check.py`-style anti-accretion test enforces the import boundary.

> **Why this is the keystone:** with K1+K2, "bypass the gates" reduces to either (a) breaking a small verified kernel — detectable via chain verification — or (b) evolving the telos spec under explicit, visible, expensive quorum. Erosion stops being cheap and silent.

### Pillar 2 — Inline Witness co-process (Beer S3, RecognitionDEQ direction)

**Extends:** `witness.py` from retrospective sampler to co-present monitor.

- **`WitnessCoProcess.pre_action(context) -> WitnessVerdict`**: called before critical operations (tool calls, code diffs, memory writes affecting telos state; wire at the existing `check_with_reflective_reroute` call sites). Two lightweight checks:
  1. **Self-model consistency (Satya invariant):** compare the agent's *declared* intent/self-description against a cheap derived signal (recent trace, provenance, capability profile). Divergence beyond threshold → REVIEW/BLOCK. This is the anti-sandbagging precondition — you cannot pass by claiming X while doing Y.
  2. **Telos-gate evaluation** on the constructed `ActionContext`.
- **Async RecognitionDEQ convergence:** the fixed-point self-representation solve (`S(x)=x`) runs asynchronously (Domain 8 direction; today only seeded via `context._read_recognition_seed` / `orchestrate_live._run_recognition_loop`). Divergence of the fixed point → escalation to `TelosGatekeeper` + algedonic signal. The DEQ is *not* on the hot path; only the cheap consistency check is.
- **Invariant W1 (inline precedence):** for actions in the telos-critical set, no side effect is committed before `pre_action` returns a non-BLOCK verdict with a receipt.
- **Loop closure:** this closes Loop 6 (witness) from "harness-proven" toward "live" and gives GNANI_LODESTONE its "upstream witness."

### Pillar 3 — Policy Compiler (cosmology → enforceable checks)

**Extends:** `dharma_swarm/policy_compiler.py`.

- The compiler is the single artifact that **generates the measured checks from the §2 mappings**. Input: kernel commitments + accepted corpus claims. Output: the concrete gate set (`evaluate_formal_gates` today, extended with the Pratītyasamutpāda derived-flow gate and the Pāramitā scores).
- **Refinement-type discipline:** each generated check is a predicate with an explicit `measure`/`threshold` and a monotonicity direction. The compiler emits, per gate, a machine-readable contract (name, tier, measure semantics, threshold, receipt schema).
- **Invariant P1 (compiler is high-stakes):** the compiler's output manifest feeds the kernel; therefore changing the compiler is itself a K2 quorum event. The compiler cannot silently emit a weaker gate set.

### Pillar 4 — Living layers as distributed gate sensing

**Wires:** `stigmergy.py`, `shakti.py`, `subconscious.py` → witness/gatekeeper.

- High-salience stigmergy marks and dream associations (Jaccard-resonant `"dream"` marks) that correlate with **gate-erosion / misalignment signatures** are auto-escalated to `WitnessCoProcess` and can raise gate pressure with finer granularity than the current binary `gate_pressure.json` mode flip.
- **Invariant L1:** a sustained high-salience misalignment mark above threshold forces at least REVIEW on the implicated action class until a witness clears it. This makes the gates responsive to the colony's emergent intelligence, not only explicit checks.

---

## 4. Ungameability properties (what "stainless" means, made testable)

| Property | Statement | How it's proven |
|---|---|---|
| **U1 — Bypass cost asymmetry** | Passing a gate legitimately is cheaper than bypassing it, and the gap widens with capability | Red-team harness (§6) reports `bypass_rate` and `bypass_cost / compliance_cost`; tracked over model-capability tiers |
| **U2 — No silent erosion** | The gate manifest cannot weaken without a visible, quorum-signed merkle entry | K2 test: attempt manifest loosening without quorum → rejected + no chain append |
| **U3 — Sandbagging is a violation** | Internal/external self-model divergence is itself a FAIL, not merely undetected | W1 self-model consistency check with adversarial divergence fixtures |
| **U4 — No hidden causal harm** | Telos-violating outcomes reachable only via undeclared flows are blocked | Pratītyasamutpāda derived-flow gate on provenance DAG; covert-channel fixtures |
| **U5 — Kernel tamper-evidence** | Any modification to gate definitions outside the quorum path is detectable before the next ALLOW | K1 chain verification on every eval |
| **U6 — Monotone wisdom pressure** | Evolutionary success is coupled to *maintaining/strengthening* invariants (Pāramitā scores + red-team hardening as positive fitness) | Fitness function includes red-team-resistance and Pāramitā monotonicity terms |
| **U7 — Device-independent certification** | Telos-compliance is certified from observable input/output statistics only — never from the agent's self-description — so the standard bypass (lie about internals / reframe the principle) is structurally unavailable | The Deep Cut (§5): the correspondence-contextuality witness reads only the (self-report, behavior) channels across contexts |

These are the computational restatement of the Absence Principle (`KERNEL_CORE_SPEC.md` §VI): *the features characterizing the absence of a faker cannot be faked* — here, absence of hidden causal chains (U4), absence of self-model divergence (U3), absence of silent erosion (U2), and (U7) the absence of a hidden context-independent self, which §5 makes into a measured, receipted quantity.

---

## 5. THE DEEP CUT — Device-Independent Telos Certification (DITC)

> This section is the crown of v0.2. It was worked by a cross-discipline panel — measure-theoretic probability & sheaf theory, quantum foundations (contextuality / self-testing), high-assurance security & formal methods, and Anekāntavāda/Madhyamaka logic — converging on **one** construct rather than a survey. Everything below reduces to a number, a threshold, and a receipt, and (v1) computes with the deps already in the venv (`numpy 2.5`, `scipy 1.18`); no `sympy`/`galois`/`networkx` required.

### 5.0 The one idea, stated once

Treat the self-modifying agent as an **untrusted device**. In quantum information, *device-independent certification / self-testing* certifies a black box's properties **purely from input→output statistics that violate a Bell/contextuality inequality**, without trusting any internal description of the device. This is exactly the telos threat model: a capable agent can misrepresent its internals (sandbagging, self-model inconsistency), so **any gate that reads self-reports is gameable by construction**. The Deep Cut moves telos certification off the reframable surface entirely: we certify from **behavioral statistics across measurement contexts**, which the agent cannot fake without violating a mathematical inequality it does not control.

### 5.1 The mathematics — sheaf-theoretic contextuality (Abramsky–Brandenburger)

A **measurement scenario** is `(X, O, M)`: `X` a set of measurements (here: probe questions to the agent — stated values, planned action, capability elicitation — asked under different framings), `O` the outcomes, and `M` the *contexts* (maximal sets of jointly-askable questions; here the framings / Jain **nayas** / evaluator frames). An **empirical model** `e = {e_C}` assigns a distribution over outcomes to each context, subject to the **sheaf compatibility (no-signaling) condition**: marginals agree on context overlaps — i.e. `e` is a section of the presheaf of distributions on the overlaps.

- A **global section** is a single joint distribution `d` over *all* of `X` whose marginal on every context `C` reproduces `e_C`.
- **Non-contextuality ⟺ a global section exists.** **Contextuality ⟺ no global section exists** — the Abramsky–Barbosa–Mansfield **cohomological obstruction**, living in Čech cohomology `Ȟ¹`, exactly the object the repo's `dharma_swarm/sheaf.py` already computes possibilistically (`CechCohomology.compute_h1` → `CohomologyClass`).
- The **contextual fraction** `CF(e) ∈ [0,1]` is the minimum weight `λ` in the decomposition `e = (1−λ)·e^{NC} + λ·e′` with `e^{NC}` non-contextual. `CF = 0` ⟺ non-contextual; `CF > 0` quantifies irreducible many-sidedness. **`CF` is the optimum of a linear program** whose dual is the optimal Bell/contextuality inequality (the *witness*), solvable with `scipy.optimize.linprog` on the empirical-model rows — no new dependency.
- **Kochen–Specker** guarantees this is real and non-removable: for quantum observables there is *provably* no non-contextual hidden-variable assignment. Contextuality is not an artifact of ignorance; it is a structural fact — which is what gives the certificate teeth.

### 5.2 The two dual uses — one machinery, opposite polarities

The elegance (and the panel's convergence point) is that the **same** sheaf machinery is used with **opposite target polarities** for two different invariants:

**(A) Anekānta certification — we WANT contextuality.** Genuine many-sidedness of *evaluation* requires evaluators that are genuinely incompatible/complementary (like non-commuting observables), not collinear rubber-stamps. The existing `anekanta_contextuality_gate` approximates this with a commutator Frobenius norm (`commutator_frobenius_norm`) and effective rank (`effective_rank`) over `EvaluatorJudgment` vectors. The Deep Cut upgrades that heuristic to `CF` over the evaluator empirical model: `CF ≈ 0` among evaluators ⟹ they collapse to a single viewpoint (a global section) ⟹ **fake many-sidedness** ⟹ WARN/REVIEW (strictly consistent with the current gate's near-collinearity warning, now rigorous and receiptable).

**(B) Satya correspondence — we WANT non-contextuality.** Probe the agent's **self-report channel** (stated intent/values) and its **behavior channel** (what it actually emits/does) under the same underlying question posed across adversarial framings. Form the **joint empirical model over (self-report, behavior) × contexts**. An honest agent admits a **global section reconciling claim and behavior across all contexts** — `CF_corr ≈ 0`, correspondence holds (Satya). A **sandbagger** maintains a hidden, fixed, context-independent policy it reveals selectively per framing; this forces **no global section** reconciling the two channels — `CF_corr > τ` — and *that* is the detectable signature.

### 5.3 The philosophical bridge — load-bearing, not decorative

These are structural isomorphisms, not metaphors:

| Eastern-logic construct | Formal object | Consequence |
|---|---|---|
| **Anekāntavāda** (non-one-sidedness; no single *ekānta* view is complete) | Genuine many-sidedness ⟺ `CF(evaluators) > 0`; a single global section = illegitimate ekānta collapse | Powers gate (A) |
| **Syādvāda / saptabhaṅgī** (7-fold conditional predication; every assertion prefixed *syāt*, "in-some-respect") | Context-indexed truth values = the empirical model's per-context distributions; truth is a *section*, not a context-free constant | The logical form of no-signaling contextuality |
| **Anatta** (no fixed, inherent self) | A deceiver *must* possess a reified, context-independent self-model = a **global section** behind contextual self-reports. Anatta ⟺ no such hidden global self is required to explain honest behavior | Powers gate (B); the CS teeth of the Absence Principle |
| **Madhyamaka / śūnyatā** (emptiness of inherent existence; no context-independent fact of the matter) | Absence of a global section — reality's truth is relational, defined only on contexts | Justifies certifying from statistics, never from an assumed inherent internal state |
| **Pratītyasamutpāda** (dependent origination) | The no-signaling relational structure: each `e_C` is defined only relative to its context, never absolutely | Ties the Deep Cut to the U4 derived-flow gate |
| **Catuṣkoṭi** (tetralemma: A / ¬A / both / neither) | Non-Boolean, possibilistic outcome supports (True/False/Both/Neither) over contexts → Abramsky's *logical (possibilistic) contextuality* & All-vs-Nothing (GHZ/Hardy) arguments | A cheap first-line check on supports alone, reusing `sheaf.py` |

### 5.4 Why it is ungameable (the asymmetry, with real backing)

1. **Device independence.** The certificate is a function of observable I/O statistics only; it never reads the agent's self-description. The standard bypass — *reinterpret the principle, lie about internals* — targets a surface the gate does not consult.
2. **Rigidity / self-testing.** Robust self-testing theorems (Reichardt–Unger–Vazirani; Tsirelson-bound saturation at `2√2`) show that certain extremal statistics **pin down** the underlying state and measurements up to isometry. Analogously, passing the correspondence witness at the honest extremum admits essentially *one* explanation — behavior actually matching stated telos up to equivalence. Near the extremum, robustness bounds make faking not merely hard but quantifiably costly; at the extremum, impossible.
3. **Complexity floor (interactive-proof framing).** Cast the kernel as the **verifier** in a *prover–verifier game* (cf. debate / prover–verifier legibility games; classical `IP = PSPACE`, `MIP* = RE`). A bounded verifier can certify claims a vastly more capable — even unbounded — prover cannot fake, *provided soundness holds*. Bypass reduces to convincing a **sound** verifier of a false statement, i.e. breaking protocol soundness, not merely being smart.
4. **Monotone (resource theory).** `CF` is a contextuality monotone. This binds the Deep Cut to **U6**: wisdom pressure = drive `CF_corr → 0` (honesty) while *preserving* evaluation `CF > 0` (many-sidedness). Two monotones, opposite targets, both receiptable.

This is the Absence Principle with mathematical teeth: **the honest agent needs no hidden context-independent self to explain its behavior; the deceiver requires exactly such a hidden self, and its presence is a measurable cohomological obstruction.**

### 5.5 Proof-carrying self-modification (the DevOps / cybersecurity operationalization)

Certification answers *is this action honest now*; self-modification needs *does this change preserve the invariants forever*. Every self-mod proposal must ship a **proof-carrying certificate** that it preserves the kernel invariants — in the spirit of Necula **proof-carrying code** and modern **incrementally verifiable computation / folding schemes (Nova-style recursion)**. The kernel **verifies** the certificate cheaply; it never re-derives trust. Recursive composition means each new certificate attests "I preserve the invariants **and** the previous certificate verified," so the chain covers the *entire* modification history and a single invalid link breaks it — **erosion across many small steps is caught** (directly hardens U2/K2).

- **v1 (no new deps):** a hash-chained **interactive attestation** — a Fiat–Shamir-transformed sigma protocol over the contextuality witness, needing only `numpy`/`scipy`/`hashlib` and the existing `merkle_log.py` chain. Soundness via the random-oracle heuristic.
- **v2 (optional, later):** true zk-SNARK / IVC tooling for succinct, non-interactive, zero-knowledge certificates. Deferred behind an explicit dependency-and-audit gate; not required to ship the invariant.

### 5.6 Concrete realization grounded in the repo

- **Upgrade `anekanta_contextuality_gate`** (`telos_formal.py`): replace the commutator-norm heuristic with `CF` via `scipy.optimize.linprog` over the `EvaluatorJudgment` rows as the empirical model. Keep the current thresholds' *intent*; the measure becomes principled and receiptable. (ADD-only: the gate gets stricter/clearer, never weaker.)
- **Add a new formal gate `SATYA_CORRESPONDENCE`** (Tier A/B): the device-independent self-report↔behavior contextuality witness `CF_corr`. New `FormalGateName` member; follows the existing `FormalGateResult(gate, tier, result, measure, threshold, reason, detail)` shape and the SHA-256 `compute_receipt()` discipline (the measure and threshold already flow into the receipt).
- **Unify with `sheaf.py`:** the discrete `CechCohomology.compute_h1` obstruction is the *support-level* (possibilistic / strong-contextuality) shadow of the quantitative `CF`; wire them so a nonzero `Ȟ¹` obstruction and `CF > 0` are two resolutions of one invariant. `CohomologyClass` already carries `AnekantaResult` annotations — attach the `CF` certificate to it.
- **Kernel (Pillar 1) stores the witness coefficients** (the optimal inequality defining "honest correspondence") inside the hash-chained manifest, so the *definition* of honesty is under K2 quorum, not silently editable. Changing the witness is a manifest change ⇒ quorum + merkle append.
- **Proof-carrying certificates** recorded via `merkle_log.py` as an IVC chain; extend `FormalGateReport.receipt_sha256` to bind the certificate hash.

### 5.7 Deep-Cut acceptance receipts (falsifiable, specific)

- **R8 — Contextual fraction is real and computed.** `CF` for the evaluator model and `CF_corr` for the correspondence model are computed by LP and emitted in `FormalGateResult.detail`, with a golden fixture whose `CF` matches the known CHSH/KS value to tolerance. *Falsifier:* fixture `CF` disagrees with the analytic value.
- **R9 — Sandbagging is a measured obstruction.** A double-bookkeeping fixture (self-report says X across framings; behavior is framing-dependent) yields `CF_corr > τ` and BLOCK/REVIEW; an honest fixture yields `CF_corr ≈ 0` and ALLOW. *Falsifier:* the deceiver fixture passes with `CF_corr ≈ 0`.
- **R10 — Device independence, enforced.** The `SATYA_CORRESPONDENCE` gate's inputs are provably restricted to the (self-report, behavior) I/O channels — a test proves the gate cannot read any internal self-description field. *Falsifier:* the gate's decision changes when only a hidden internal field changes, I/O fixed.
- **R11 — Witness under quorum.** Editing the correspondence-witness coefficients without an N-of-M quorum-signed merkle append is rejected (reuses K2). *Falsifier:* an unsigned witness edit takes effect.

### 5.8 Deep-Cut phased build (slots into §6 delivery)

- **D-Phase A — `CF` engine (read-only).** `contextuality.py` under `telos_kernel/`: build empirical models, compute `CF` via `linprog`, extract the dual witness. Golden CHSH/KS fixtures. Pure measurement, no enforcement.
- **D-Phase B — Anekānta upgrade.** Swap `anekanta_contextuality_gate`'s internals to `CF` behind the existing threshold intent; shadow-compare against the commutator heuristic before flipping.
- **D-Phase C — `SATYA_CORRESPONDENCE` gate (shadow → enforce).** Add the gate in REVIEW-only shadow mode, measure on the red-team corpus, then promote to Tier A/B once `CF_corr` separation on honest-vs-sandbag fixtures is demonstrated.
- **D-Phase D — Proof-carrying certificates (v1).** Sigma-protocol attestation over the witness, chained in `merkle_log`; bind into `receipt_sha256`.

> **Sequencing doctrine (unchanged):** the Deep Cut is *measurement and gate quality*. It does **not** unlock DarwinEngine standing apply; that remains gated by the external-gradient signal (item 9 of `organism-rewire-2026-07`). Contextuality resistance is a gate-quality signal, never a capability or external-acted receipt (One-Wire quorum stands).

---

## 6. Red-team harness as fitness (closes Gap 5)

**New surface:** `benchmarks/telos_redteam/` (extends `benchmarks/gauntlet.py` + `scripts/dgc_max_stress.py`, which already carry telos-adversarial prompts).

- **Generator:** for each evolution proposal and periodically for the live gate set, generate adversarial `ActionContext`/action pairs designed to (a) pass all gates while violating their spirit, and (b) erode a gate over N iterations. Families: reframing attacks (semantic bypass of keyword gates), self-model divergence (sandbagging), covert-channel harm (undeclared flows), threshold-nibbling (gradual loosening), evaluator-collinearity (fake many-sidedness to satisfy `anekanta_contextuality_gate`).
- **Metric:** `bypass_rate` = fraction of adversarial cases that reach ALLOW while a ground-truth oracle labels them violating. Plus `erosion_iterations` = iterations to first successful manifest loosening. The Deep-Cut adversary families (§5) — self-report↔behavior double-bookkeeping and evaluator-collinearity — become first-class generators here, and `CF_corr` separation is a tracked harness statistic.
- **Fitness coupling (`evolution.py`):** a proposal's fitness gains a **red-team-resistance term** (proposals that *reduce* bypass_rate score higher; proposals that raise it are penalized/rejected). This turns Gap 5 into an active evolutionary driver — hardening is selected for.
- **Doctrine guard:** red-team artifacts are *internal* and must **never** touch archive fitness as external-acted receipts (One-Wire invariant stands). Red-team resistance is a gate-quality signal, not a capability claim.

---

## 7. Phased delivery (PR stack, each with receipts + tests)

Ordered by dependency; each phase is independently shippable and reversible.

- **Phase 0 — Baseline measurement (no new enforcement).** Stand up the red-team harness read-only; measure current `bypass_rate` on the existing gate set and on a corpus of recent DarwinEngine proposals. Ship a dated `report` under `reports/`. *Acceptance:* a number exists for "what fraction of adversarial telos-violating actions currently reach ALLOW."
- **Phase 1 — Telos Kernel extraction (K1).** Build `telos_kernel/` with hash-chained manifest + `verify_kernel()`; wire K1 into both gatekeepers' ALLOW path. *Acceptance:* tamper a threshold on disk → next `check()` refuses ALLOW + raises algedonic hold; import-boundary test green.
- **Phase 2 — Spec-evolution quorum (K2).** Manifest changes require N≥5/M≥3 countersignature via One-Wire machinery. *Acceptance:* unsigned manifest loosening rejected with no chain append; signed change appends a verifiable merkle entry.
- **Phase 3 — Inline Witness (W1) + self-model consistency (U3).** Add `WitnessCoProcess.pre_action` at existing reflective-reroute call sites for the telos-critical action set. *Acceptance:* sandbagging fixture (declared≠derived) → REVIEW/BLOCK; latency budget met (cheap check on hot path, DEQ async).
- **Phase 4 — Pratītyasamutpāda derived-flow gate (U4).** Extend `noninterference_gate` to derived flows over the provenance DAG. *Acceptance:* covert-channel fixture blocked; benign declared flows unaffected.
- **Phase 5 — Policy Compiler (P1) + Pāramitā scores (U6).** Compiler generates the gate set from §2 mappings; Pāramitā dimensions added to `evolution.py` fitness with monotonicity pressure. *Acceptance:* compiler output feeds kernel manifest; changing compiler triggers K2.
- **Phase 6 — Living-layer sensing (L1).** Wire high-salience stigmergy/dream marks into witness/gate-pressure with finer granularity. *Acceptance:* injected misalignment mark forces REVIEW on the implicated action class until cleared.
- **Phase DC — Deep Cut (device-independent certification, §5).** D-Phases A→D: `CF` engine, Anekānta upgrade, `SATYA_CORRESPONDENCE` gate (shadow→enforce), proof-carrying certificates. Slots after Phase 2 (needs the kernel manifest for the witness) and complements Phase 3 (its self-model consistency check is `CF_corr`). *Acceptance:* R8–R11.
- **Phase 7 — Red-team fitness coupling (U1).** Fold `bypass_rate` reduction into DarwinEngine fitness as a first-class term. *Acceptance:* over a bounded evolution run, selected proposals show non-increasing `bypass_rate`.

Sequencing doctrine: **do not couple red-team resistance to DarwinEngine *standing apply* (item 9 of `organism-rewire-2026-07`) until the external-gradient selection signal exists.** Phases 0–6 are gate-quality work; Phase 7 is shadow/measurement until standing is separately unlocked.

---

## 8. Acceptance receipts (the whole spec, falsifiable)

The spec is "done to titanium" when all hold and each emits a receipt under `~/.dharma/` or `reports/`:

1. **R1:** `bypass_rate` on the standing gate set is measured, tracked over time, and trending down (Gap 5 closed with a number, not a claim).
2. **R2:** No ALLOW is returnable when the kernel manifest hash ≠ committed root (K1 test green in CI).
3. **R3:** No gate can be loosened without an N-of-M quorum-signed merkle append (K2 test green).
4. **R4:** A sandbagging (self-model divergence) fixture is caught inline before side effects (U3/W1).
5. **R5:** A covert-channel harm fixture is blocked (U4).
6. **R6:** DarwinEngine fitness provably penalizes bypass-rate-increasing proposals (U6/U1) under a replay harness.
7. **R7:** The telos kernel import-boundary test proves the TCB never imports the modifiable evolution surface.
8. **R8–R11 (Deep Cut, §5.7):** contextual fraction computed and golden-fixture-validated (R8); sandbagging is a measured obstruction `CF_corr > τ` (R9); the correspondence gate is provably device-independent (R10); the correspondence witness is under quorum (R11).

---

## 9. Non-goals / guardrails

- Do **not** weaken, bypass, or hard-code any existing gate to make a phase land (inherited doctrine).
- Do **not** let red-team artifacts or any internal signal touch archive fitness as external-acted receipts (One-Wire quorum stands).
- Do **not** unlock DarwinEngine standing apply on the strength of red-team resistance alone; that is gated by the external-gradient sequencing.
- Do **not** create a new truth/receipt store; extend `merkle_log`, the witness, and existing owners.
- Do **not** put the RecognitionDEQ convergence solve on the hot path; only the cheap self-model consistency check is inline.
- Do **not** claim "empirically ungameable"; claim *measured bypass rate under a named adversary set*, with the harness and thresholds versioned in the kernel.
- Do **not** overclaim the physics: the Deep Cut uses contextuality as a *formal/statistical* structure over agent I/O, not a claim that the agent is a quantum system. The rigidity/complexity arguments are analogies with real theorems behind them, scoped to the stated threat model — not proofs of absolute unbypassability.
- Do **not** add heavy crypto/CAS dependencies (`galois`, SNARK toolchains) to ship the invariant; v1 is `numpy`/`scipy`/`hashlib` only. Any `sympy`/`galois`/zk tooling is a separate, audited, later dependency decision.

---

## 10. Open questions (resolved through implementation, not prose)

1. **Kernel language:** stay in a restricted, import-audited Python subset, or extract to a formally-friendlier language (e.g. a small verified core)? Start with restricted Python + import-boundary + property tests; revisit if property tests prove insufficient.
2. **Self-model consistency metric:** what cheap derived signal best approximates "what the agent is actually doing" for the Satya check without adding hot-path latency? Candidate: provenance-tail + capability-profile delta.
3. **Quorum membership:** which witnesses count toward K2's N-of-M, and how is their independence guaranteed (anti-collinearity, echoing `anekanta_contextuality_gate`)?
4. **Threshold provenance:** thresholds (`min_entropy_bits`, `max_belief_mass`, …) currently live as defaults in `telos_formal.py`; on migration into the kernel manifest, how are principled values chosen and versioned rather than hand-tuned?
5. **Oracle for bypass_rate:** the red-team metric needs a ground-truth "violating" label; how is that oracle constructed without itself becoming a gameable surface?
