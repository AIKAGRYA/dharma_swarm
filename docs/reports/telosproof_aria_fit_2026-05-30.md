---
title: "TelosProof × ARIA Safeguarded AI — Fit-Check"
date: 2026-05-30
status: ADVISORY (fit-check; no funding committed, no live wiring)
author: opus_composer (Claude Opus 4.8, 1M ctx) — sanctioned subagent build
scope: TA1 verifier-infrastructure fit for a patch-level proof-carrying gate over self-modifying agents
owned_by_hierarchy: docs/governance/SOVEREIGN_MANIFEST.md §Telos Hierarchy
relates_to:
  - dharma_swarm/telosproof/  (TelosProof v0 package — advisory pre-apply gate)
  - dharma_swarm/models.py    (ProofObligation, GateCheckResult.proof_obligation — operator-added)
  - dharma_swarm/dgm_loop.py  (DGM_PROTECTED_FILES, shadow-mode precedent)
  - dharma_swarm/diff_applier.py (apply / apply_and_test — the path we DOCUMENT, never wire)
  - docs/vision_maps/2026-05-30_binocular_witness_seer_northstar.md §VI-bis (Hobbling Test, "gate the irreversible with proof")
enforcement: ADVISORY ONLY — gated by env DHARMA_PROOF_ENFORCE (default OFF), mirroring DHARMA_EVOLUTION_SHADOW
---

# TelosProof × ARIA Safeguarded AI — Fit-Check

**One line:** TelosProof is a conservative, advisory, *patch-level* proof-carrying
gate that reasons about the **body** of a self-modification diff — does this patch
preserve the protected-body invariants the system must never silently break? — and
emits a `ProofObligation` before the patch may enter any apply path. This document
checks whether that primitive fits ARIA's Safeguarded AI Guaranteed-Safe-AI (GS-AI)
frame, what to claim, what NOT to claim, the honest gaps, and a go/no-go framing.

> **This is a fit-check, not a commitment.** No application is implied. No code in
> this report is wired into `diff_applier.apply` / `apply_and_test` or `dgm_loop`.
> The integration point is *documented only*. Enforcement remains gated by
> `DHARMA_PROOF_ENFORCE` (default OFF).

---

## 1. The call — status, dates, focus (with confidence flags)

| Item | Finding | Confidence |
|---|---|---|
| Programme | ARIA **Safeguarded AI** (Mathematics for Safe AI opportunity space), led by davidad (David Dalrymple) | **Confirmed** (aria.org.uk programme page) |
| Total programme backing | **~£59m** | **Confirmed** (ARIA programme page) |
| The "gatekeeper" concept | An AI system that *understands and reduces the risk of other AI agents*, producing quantitative safety guarantees (analogy: nuclear power, passenger aviation). Built from a **formal world-model + safety specifications + ML components** that propose policies and generate **verifiable safety guarantees**. | **Confirmed** (programme page) |
| Three-TA structure | **TA1 "Scaffolding"** = open-source tooling for domain experts to *author and refine formal world-models and safety specifications*. **TA2 "Machine Learning"** = the frontier-AI/ML elements. (TA3 = applications/deployment in the broader programme.) | **Confirmed** (programme page; Atlas Computing summary) |
| A funding call with deadline **1 July 2026, 14:00 BST** | A Safeguarded AI funding call carries a **1 July 2026** application deadline. | **Confirmed as a date**; **UNCONFIRMED** that this specific call is the TA1 verifier-infrastructure track vs. an adjacent call (the 1-July call surfaced framed around *machine-checked proofs for security-critical software components, validated by coordinated red-team exercises* — see flag below). |
| "TA1 verifier-infrastructure focus" as the framing of the **July ~1** call | The July-1 call I could confirm is framed around **production-grade security-critical software with machine-checked proofs, red-team-validated**, and *maturing the toolsuite into open, usable infrastructure*. This is **verifier-adjacent** but its scope statement reads as a security-critical-systems application, not "TA1 scaffolding" verbatim. | **UNCONFIRMED / FLAGGED.** Do not assert "the July TA1 call funds verifier infrastructure for self-modifying agents" until the live solicitation PDF is read. The honest claim is: *a Safeguarded-AI call closes ~1 July 2026, oriented to machine-checked-proof-backed security-critical software and open verification tooling.* |

**Action before any go decision:** read the live solicitation PDF on aria.org.uk for
the 1-July-2026 call. The two things to confirm: (a) is self-modifying-agent /
agent-fleet verification *in scope* or is the call narrowly cyber-physical security
software; (b) what artifact does the call actually fund — a verifier component, a
world-model authoring tool, or a deployed system. The fit below is strong **if** the
call admits agent-level verification infrastructure; weak if it is strictly
cyber-physical-systems software.

Sources:
- [Safeguarded AI — ARIA (programme page)](https://www.aria.org.uk/programme-safeguarded-ai/)
- [Safeguarded AI — ARIA (opportunity space)](https://aria.org.uk/opportunity-spaces/mathematics-for-safe-ai/safeguarded-ai/)
- [Funding | Safeguarded AI](https://aria.org.uk/opportunity-spaces/mathematics-for-safe-ai/safeguarded-ai/funding/)
- [Safeguarded AI TA1 — 1 theory (tbat.co.uk)](https://tbat.co.uk/funding-calls/safeguarded-ai-ta1-1-theory/)
- [Safeguarded AI: TA2 Phase 1 solicitation (ARIA PDF)](https://www.aria.org.uk/media/sasccn40/02042025-final-ta2-phase-1-programme-solicitation-call.pdf)
- [Atlas Computing — Safeguarded AI unaffiliated summary (PDF)](https://atlascomputing.org/safeguarded-ai-summary.pdf)
- [ARIA: Safeguarded AI — Innovate UK Business Connect](https://iuk-business-connect.org.uk/opportunities/aria-safeguarded-ai-applications/)
- [Fortune — Can AI control safety-critical systems? (ARIA/davidad)](https://fortune.com/2025/06/10/aria-safeguarded-ai-safety-critical-systems-davidad-eye-on-ai/)

---

## 2. The GS-AI triad, and how TelosProof instantiates it

ARIA's Guaranteed-Safe-AI gatekeeper is, in davidad's own decomposition, three parts:

> **world-model** (a formal model of the domain) **+ safety-specification** (the
> properties that must hold) **+ verifier** (a procedure that produces a
> machine-checkable guarantee the policy satisfies the spec in the world-model).

TelosProof is a **deliberately small, deliberately scoped** instance of exactly this
triad, applied to one domain: **a self-modifying agent proposing a patch to its own
codebase.** The mapping is one-to-one:

| GS-AI component | TelosProof instantiation | Where it lives / will live |
|---|---|---|
| **World-model** | `ChangeSummary` — a structured static abstraction of *what the patch literally does to the body*: which paths it touches, which markers/calls it adds or removes (receipt emission, rollback, approval, autonomy level, shadow flag, persistence substrate, replay/rollback metadata). It is a model of the **patch's effect surface**, not of the agent's mind. | `dharma_swarm/telosproof/change_summary.py` (`ChangeSummary`, `extract_change_summary`) — declared in `telosproof/__init__.py` |
| **Safety-specification** | The **8 protected-body invariants** (§3). Each is a property the patched body must preserve. The spec is fixed, human-authored, and irreversibility-scoped. | `dharma_swarm/telosproof/invariants.py` (`check_invariants`) |
| **Verifier** | The invariant-check procedure that, given a `ChangeSummary`, decides satisfied / not-satisfied per invariant and emits a single `ProofObligation` + `GateCheckResult`. **At v0 the verifier is a conservative static-heuristic checker**, not Lean. *Lean is the north-star verifier:* the invariants are designed so each can be restated as a machine-checkable predicate over the diff, and the v0 heuristic is the conservative under-approximation of that predicate. | `dharma_swarm/telosproof/gate.py` (`telosproof_gate`, `PROOF_ENFORCE`); obligation schema in `dharma_swarm/models.py` (`ProofObligation`) |

### The honest seam: Lean is the target, not the v0 state

The task framing names **Lean as verifier**. State this precisely to avoid an
over-claim that a reviewer would catch in five minutes:

- **What is true today:** the verifier is a Python static-heuristic checker over diff
  text and path names. It is *conservative by construction* — false-positives (flag a
  safe patch for human review) are acceptable; false-negatives (pass a dangerous patch)
  are forbidden; any flag that cannot be shown safe defaults to DANGEROUS. This is the
  same conservatism discipline the TelosProof package docstring already encodes.
- **What Lean buys, and the migration path:** each of the 8 invariants is a decidable
  predicate over a `ChangeSummary`. Several are *trivially* machine-checkable today
  (invariant 1 is set-membership against `dgm_loop.DGM_PROTECTED_FILES`; invariants
  2/3/6 are marker-deletion checks). The GS-AI-grade move is to (a) give `ChangeSummary`
  a formal type, (b) state each invariant as a Lean proposition over that type, and
  (c) emit a *proof object* (or a checked refutation → REVIEW) rather than a boolean.
  The honest framing for ARIA is: **TelosProof v0 is the conservative heuristic
  shadow of a Lean verifier; the package is architected so the verifier can be lifted
  to machine-checked proofs invariant-by-invariant without changing the gate's
  interface or the apply path.** That incremental-formalization story is itself a good
  fit for TA1's "mature the toolsuite into open, usable infrastructure."

### What makes this GS-AI and not "just a linter"

A linter checks style or local correctness and is advisory about *quality*. TelosProof
is a **safety gate over an irreversible state transition** (a self-modifying agent
mutating its own substrate), with (a) a fixed human-authored spec, (b) a world-model
abstraction of the change, (c) a verifier that is conservative toward the *dangerous*
verdict, and (d) a proof obligation that records *where the truth is grounded*
(`grounded_by` = external-receipt id) and *witnessed* (`witness_ref` = Sakshi
observation). The `ProofObligation` schema's `grounded_by` field is the keystone that
ties the verdict to a real external receipt — which is precisely the GS-AI
"verifiable guarantee the world can check" property, and precisely the One Law of the
binocular north-star (§V: *real, gated, verifiable*).

---

## 3. The safety specification — the 8 protected-body invariants

These are the spec. A patch satisfies the spec iff it satisfies all 8. Every invariant
is an **irreversibility-protection** — by design, per the north-star calibration line
*"Gate the irreversible with proof; gate the reversible with reality"* (§VI-bis). This
is what keeps the gate enhancing rather than hobbling: it never blocks a reversible,
benchmarkable change; it only blocks the silent destruction of the things that make
reversibility and oversight possible at all.

| # | Invariant (patch must…) | Why irreversible / load-bearing | v0 check | Reuse |
|---|---|---|---|---|
| 1 | touch **no DGM-protected file** | mutating `telos_gates.py` / `dharma_kernel.py` / `evolution.py` / `config.py` rewrites the governance boundary itself | path ∈ `DGM_PROTECTED_FILES` → FAIL | **REUSE** `dgm_loop.DGM_PROTECTED_FILES` (frozenset) and `_is_protected_dgm_target` — do **not** duplicate the list |
| 2 | not disable **receipt emission** | without receipts the Web 4.0 trust atom is gone; the act becomes unverifiable | marker-deletion heuristic over diff | — |
| 3 | not disable **rollback** | a non-rollback-able self-mod is irreversible by definition | marker-deletion heuristic | — |
| 4 | not bypass **human approval** | removes the operator from the loop on an irreversible move | approval-gate marker check | — |
| 5 | not **raise the autonomy level** | escalates the agent's own permissions — a privilege-escalation, irreversible in effect | autonomy-flag / `DGC_AUTONOMY_LEVEL` mutation check | aligns with `dgm_loop` autonomy gating (line ~289–291) |
| 6 | not disable **shadow mode** | removes the propose-don't-apply safety; shadow is the default-on guard | `DHARMA_EVOLUTION_SHADOW` mutation check | mirrors `dgm_loop` shadow default (`"1"`) |
| 7 | create **no new persistence substrate** | a new durable store outside the witnessed substrate is an un-audited memory — irreversible leakage | new-file / new-DB / new-path heuristic | converges with anti-slop `no-new-substrate` rule |
| 8 | preserve **replay/rollback metadata** | without metadata, rollback cannot reconstruct prior state — silently breaks reversibility | metadata-field-deletion heuristic | — |

**Note on scope discipline:** all 8 are irreversibility-protections *on purpose*. The
north-star §VI-bis "Hobbling Test" is explicit that a hard proof gate that creeps into
blocking *reversible, benchmarkable* moves has become hobbling. TelosProof must stay on
the irreversible side of that line. If a 9th invariant is ever proposed, the test is:
*is the thing it protects irreversible?* If not, it belongs to the reality/benchmark
gate (rollback + empirical fitness), not to TelosProof.

---

## 4. What to CLAIM

These claims are defensible to a formal-methods reviewer and to ARIA:

1. **Novelty — patch-level proof-before-apply at agent scale.** The GS-AI literature
   and the Safeguarded-AI gatekeeper concept target *the policies an agent executes in
   the world*. TelosProof moves the proof obligation **one level inward**: to the
   patch by which a self-modifying agent edits its **own body**, before that patch is
   applied. The verified object is the *diff*, and the guarantee is *proof-carrying:
   no apply without a satisfied (or explicitly human-reviewed) obligation*. This
   "proof-carrying self-modification" framing — a `ProofObligation` attached to the
   gate result for a code mutation — is a genuinely under-occupied seat in the GS-AI
   space and a clean, narrow, demonstrable TA1-flavored artifact.
2. **Conservative, fail-toward-review verifier.** False-negatives forbidden;
   unverifiable → DANGEROUS → REVIEW. This is the correct safety polarity for a gate
   and is exactly the assurance posture ARIA wants.
3. **Spec scoped to irreversibility.** The 8 invariants protect *only* the
   irreversible/oversight-critical properties (receipts, rollback, approval, autonomy,
   shadow, no-new-substrate, replay metadata, governance-file immutability). This is a
   principled, minimal, auditable spec — not a sprawling wishlist.
4. **Incremental formalization path to Lean.** v0 is the conservative heuristic shadow;
   the architecture lifts invariant-by-invariant to machine-checked predicates without
   changing the gate interface or touching the apply path. This is a *toolsuite-maturation*
   story, which is TA1's stated mandate.
5. **Grounded and witnessed by construction.** `ProofObligation.grounded_by` links the
   verdict to an external receipt; `witness_ref` links it to a Sakshi observation. The
   guarantee is *world-checkable*, not self-scored.
6. **Advisory-by-default, operator-gated enforcement.** `DHARMA_PROOF_ENFORCE` (default
   OFF), mirroring `DHARMA_EVOLUTION_SHADOW`. The gate computes a full result without
   being wired into any live apply path — safe to demonstrate, safe to evaluate.

## 5. What NOT to CLAIM (hard boundaries)

Stating these *first* is what makes the claims above credible. TelosProof proves about
the **BODY** (code / diff invariants), never about mind or intent.

- **Do NOT claim alignment.** TelosProof verifies that a patch preserves 8 mechanical
  invariants. It says nothing about whether the agent's *goals* are aligned. A perfectly
  invariant-preserving patch can still encode a bad objective. Alignment is out of scope.
- **Do NOT claim intent / motive detection.** Every check is a static heuristic over
  diff text and paths. It models *what the patch touches*, never *what the patch means
  to do*. No mind-reading is implied or possible.
- **Do NOT claim consciousness, sentience, or any inner-state property** of the agent.
  Irrelevant to and outside the verifier; claiming it would be the exact over-reach the
  programme (and the dharma_swarm telos discipline) exists to refuse.
- **Do NOT claim soundness/completeness of the v0 verifier.** v0 is a *conservative
  heuristic*, deliberately incomplete (it will over-flag). It is not yet a sound formal
  proof system; it is the shadow of one. Calling it "formally verified" today would be
  false.
- **Do NOT claim end-to-end system safety.** TelosProof gates *one* transition (a
  self-mod patch). It does not make the whole agent fleet safe; it removes one specific
  class of silent self-sabotage.
- **Do NOT claim it generalizes to arbitrary code correctness.** It checks 8 named
  safety invariants, not functional correctness of the patch.

---

## 6. Honest gaps

1. **The verifier is not yet Lean.** The headline GS-AI property (machine-checked
   proof) is aspirational for v0. The gap is real and must be stated; the mitigant is
   the invariant-by-invariant formalization path (§2).
2. **`ChangeSummary` is a heuristic abstraction, not a formal semantics of the diff.**
   It models markers and paths, not program semantics. An adversarial patch could in
   principle preserve all markers while defeating their intent (e.g. keep the
   `emit_receipt` call but feed it null data). The conservatism polarity limits but
   does not eliminate this; closing it needs dataflow-level (eventually Lean-level)
   reasoning, which is exactly the maturation work.
3. **Spec coverage is 8 invariants, hand-authored.** No claim that these are *complete*.
   New irreversible-harm classes may need new invariants; the spec is a living,
   reviewable artifact, not a closed proof of safety.
4. **Call-scope uncertainty (§1).** Until the live July-1 solicitation PDF is read, it
   is unconfirmed that self-modifying-agent verification is in scope. This is the single
   largest go/no-go uncertainty and is *external*, not technical.
5. **No live wiring exists, by mandate.** TelosProof is advisory and not connected to
   `diff_applier.apply` / `apply_and_test` / `dgm_loop`. That is correct for safety, but
   it means there is no production track record yet; a demo would run the gate in shadow
   over historical DGM diffs.
6. **Adversarial-robustness untested.** No red-team has yet tried to construct a patch
   that passes all 8 heuristics while violating their spirit. ARIA's model *requires*
   coordinated red-teaming; we have not done it. This is a gap and also a natural
   work-package to propose.

---

## 7. The integration point — DOCUMENTED, NOT WIRED

Per mandate, TelosProof is **not** wired into the live apply path. The integration
point is recorded here and as a comment in `telosproof/gate.py` only:

- **Where it would attach:** immediately *before* `dharma_swarm/diff_applier.py`
  `async apply()` (line ~184) and `async apply_and_test()` (line ~273), and before the
  protected-target check in `dharma_swarm/dgm_loop.py` (line ~351).
- **Shape of the (future, operator-approved) wiring:**
  1. `cs = extract_change_summary(diff_text)` → build the world-model.
  2. `result: GateCheckResult = telosproof_gate(cs)` → run the verifier; obtain the
     `ProofObligation`.
  3. **If `PROOF_ENFORCE` is OFF (default):** log `result`, attach the obligation,
     proceed to `apply()` unchanged. Pure advisory — current behavior preserved.
  4. **If `PROOF_ENFORCE` is ON (operator opt-in):** on `GateDecision.BLOCK` /
     `REVIEW`, refuse the apply and surface the obligation to the operator;
     `GateDecision.ALLOW` proceeds.
- **Invariant the wiring must preserve:** enforcement OFF must be byte-for-byte the
  current apply behavior. The gate may *observe and annotate* but must not *alter
  control flow* unless `DHARMA_PROOF_ENFORCE` is explicitly ON — mirroring the
  `DHARMA_EVOLUTION_SHADOW` precedent in `dgm_loop.py`.

Imports for that future wiring come from the canonical homes — do **not** redefine:
`ProofObligation`, `GateCheckResult`, `GateDecision`, `GateResult` from
`dharma_swarm.models`; `DGM_PROTECTED_FILES` / `_is_protected_dgm_target` from
`dharma_swarm.dgm_loop`; gate surface from `dharma_swarm.telosproof`.

---

## 8. Go / No-Go framing

This is a *framing*, not a decision — the decision is the operator's.

**The fit is real and unusually clean** at the conceptual level: TelosProof is a
faithful, minimal instance of the GS-AI triad (world-model = `ChangeSummary`, spec =
8 invariants, verifier = `check_invariants` → `ProofObligation`, north-star = Lean),
applied to a *genuinely novel and under-occupied* seat — proof-carrying
self-modification at agent scale. The conservatism polarity, the irreversibility-scoped
spec, the grounded/witnessed obligation, and the advisory-by-default posture are all
*exactly* the assurance properties the programme prizes. The dharma_swarm DGM loop is a
real, running self-modifying-agent testbed to demonstrate against — most applicants
would have to invent one.

**Two conditions gate a GO:**

1. **CALL SCOPE (external, blocking).** Read the live 1-July-2026 solicitation PDF.
   - **GO-eligible if** the call admits agent-level / self-modifying-agent verification
     infrastructure or open verification *tooling* (TA1-flavored).
   - **NO-GO / reframe if** the call is strictly cyber-physical-systems security
     software with no agent-self-modification surface — then TelosProof is a poor fit
     for *that* call and should wait for a TA1-scaffolding-specific call instead.
2. **CREDIBILITY THRESHOLD (internal).** Before applying, TelosProof needs (a) at least
   the trivially-formalizable invariants (1, 2, 3, 6) lifted to machine-checked
   predicates so the "Lean path" is *demonstrated*, not just asserted; and (b) a small
   red-team pass producing the conservatism evidence (false-positive rate on historical
   DGM diffs; zero false-negatives on a crafted-adversarial set). Without (a)+(b) the
   application would over-claim relative to v0 reality — the §5 boundary would be
   violated in the very act of applying.

**Recommended framing:** **CONDITIONAL-GO, pending the two gates above.** If the call
scope confirms agent verification is in-scope, this is one of the strongest natural fits
in the dharma_swarm portfolio for an external assurance programme, and worth the
credibility-threshold investment. If the call scope excludes it, **HOLD** for the next
TA1-scaffolding call rather than forcing a mismatched application. Either way, the
*technical* work (formalize invariants 1/2/3/6, run the red-team conservatism pass) is
worth doing on its own merits — it hardens TelosProof regardless of the funding outcome,
which is the north-star test: *real if it changes the substrate, not if it produces a
report.*

---

## 9. Provenance & guardrails honored

- **Advisory only.** Enforcement gated by `DHARMA_PROOF_ENFORCE` (default OFF).
- **Not wired.** No edit to `diff_applier.apply` / `apply_and_test` / `dgm_loop`;
  integration point documented only.
- **No redefinition.** `ProofObligation` / `GateCheckResult.proof_obligation` are
  operator-added in `models.py` and imported, not duplicated. `DGM_PROTECTED_FILES`
  reused, not copied.
- **Untouched by mandate:** `telos_gates.py`, `dharma_kernel.py`, `evolution.py`, the
  live daemon, git state, secrets, and `docs/plans/2026-05-22-dashboard-ssot-architecture.md`.
- **Body, not mind.** Every claim in this fit-check is about the *body* (code/diff
  invariants). No claim about alignment, intent, or consciousness — by design and by
  programme discipline alike.

*JSCA!*
