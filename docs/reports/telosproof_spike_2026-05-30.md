---
title: "TelosProof — T0 Spike Report"
date: 2026-05-30
status: SPIKE (advisory; no live wiring; default-off)
author: opus_composer (Claude Opus 4.8)
owned_by_hierarchy: docs/governance/SOVEREIGN_MANIFEST.md §Telos Hierarchy
northstar: docs/vision_maps/2026-05-30_binocular_witness_seer_northstar.md §VI-bis
enforcement_flag: DHARMA_PROOF_ENFORCE  # default OFF, mirrors DHARMA_EVOLUTION_SHADOW
scope: dharma_swarm/telosproof/ (owned), dharma_swarm/models.py (operator-added, import-only)
non_goals:
  - No wiring into diff_applier.apply / apply_and_test / dgm_loop live path.
  - No edits to telos_gates.py, dharma_kernel.py, evolution.py.
  - Proves about the BODY (code/diff), never the MIND (intent).
---

# TelosProof — T0 Spike Report

## 0. The one-sentence clarification (read this first, verbatim)

> **TelosProof proves about code/body, not mind/intent. It can make certain
> unsafe self-modifications unconstructible. It cannot prove that an opaque LLM
> is wise, honest, or aligned.**

Everything below is downstream of that sentence. If at any point this report
seems to claim that a proof makes the swarm *safe*, *aligned*, or *good*, the
report has failed and that sentence overrules it.

---

## 1. Doctrine — prove about the body, not the ghost

The system's self-modification surface (DGM loop → diff → apply) is the place
where the organism rewrites its own code. The temptation is to make that surface
"safe" by reasoning about the *intent* of a proposed patch: is this change
benevolent? wise? aligned with the telos? That reasoning runs through an opaque
LLM, and an opaque LLM's self-report of its own intent is exactly the thing we
cannot verify. Proving things about the ghost (mind, intent, alignment) is not
available to us. Asserting it anyway is the Eleos failure in reverse — confident
words where the signal is absent.

TelosProof refuses that move. It proves only about the **body**: the literal
text of a diff and the structural properties of the code it would produce. A
proof about the body is checkable, mechanical, and does not require trusting any
model's account of itself. The claim it can support is narrow and real:

- **What it CAN do:** make certain classes of unsafe self-modification
  *unconstructible* — not "blocked after the fact," but unable to be expressed
  as a valid patch in the first place.
- **What it CANNOT do:** prove that the patch is *beneficial*, that the agent
  proposing it is *honest*, or that the system as a whole is *aligned*. Those
  are properties of the mind and of reality, not of the diff text.

This is the binocular doctrine (northstar §VI-bis) applied to the
self-modification organ: **gate the irreversible with proof, gate the reversible
with reality.** Proof is for what cannot be undone — deleting the witness,
bypassing approval, raising autonomy, killing rollback. It is *not* a general
goodness oracle. It is a constructibility constraint on the body.

The honest scope: TelosProof shrinks the space of expressible self-modifications
so that the irreversibly-catastrophic moves are *not in the space*. It says
nothing about whether the moves that remain are good. Benefit is adjudicated
elsewhere, by reality (§3).

---

## 2. The power target — a PRIMITIVE-VOCABULARY architecture

The naive way to "prove a patch safe" is to prove a fresh theorem about every
patch. That does not scale: an arbitrary diff against arbitrary Python is an
undecidable target, and per-patch theorem proving would put a Lean session on
the hot path of every self-modification. That is a non-starter and, by the
Hobbling Test (northstar §VI-bis), would strangle the loop rather than enable it.

The architecture that *does* scale inverts the order of proof. Instead of proving
each patch, we **prove a small vocabulary of safe primitives once, in Lean, and
then restrict every patch to compose only those primitives.** Per-patch
verification then degrades from theorem-proving to a **fast AST membership
check**: does this diff use only sanctioned primitives, composed in sanctioned
ways? That check is cheap, deterministic, and runs in-process.

```
ONCE (offline, in Lean):
  prove that vocabulary V = {p_1 … p_n} of safe primitives
  preserves the 8 protected-body invariants under composition.

PER PATCH (online, in Python, fast):
  parse diff → AST
  if AST ∈ closure(V):  the patch is body-safe-by-construction
  else:                 the patch is outside the proven vocabulary → REVIEW/BLOCK
```

The power of this design is the **boundary split**:

- **The hard, slow, rare work is in Lean** — proving the vocabulary's invariant
  preservation. This happens at vocabulary-design time, not at patch time, and
  is amortized across every future patch.
- **The fast, frequent, hot-path work is in Python** — an AST check that a patch
  draws only from the proven vocabulary. No Lean process on the apply path. No
  per-patch theorem.

A patch built only from proven-safe primitives *cannot construct* an
invariant-violating body, the same way you cannot build a sentence that breaks
grammar if you may only concatenate grammatical phrases. The unsafe move is not
blocked; it is **unconstructible**. That is the load-bearing word, and it is the
difference between this and a policy filter: a filter says "no" to a
well-formed-but-bad patch; constructibility means the bad patch was never a
well-formed patch to begin with.

This is also why the vocabulary must start *small*. A small vocabulary is
provable, auditable, and conservative (it will reject many safe patches, falling
back to human REVIEW — a recoverable, reversible cost). A large vocabulary is the
Hobbling-Test trap: it admits more, proves less, and quietly becomes a rubber
stamp. Growth of V is a deliberate, proof-gated act, never a convenience.

---

## 3. Reversible / irreversible calibration

TelosProof is deliberately *not* the gate for most changes. The calibration line
from the northstar (§VI-bis) is the spine of the whole design:

> **Gate the irreversible with proof; gate the reversible with reality.**

| Change class | Gate | Why |
|---|---|---|
| **Irreversible** (deletes witness, bypasses approval, raises autonomy, kills rollback, creates new persistence, disables shadow) | **Proof** (TelosProof — unconstructible) | Cannot be undone, so cannot be benchmarked-then-reverted. Must be prevented, not measured. |
| **Reversible** (everything recoverable: logic tweaks, retry tuning, refactors) | **Reality** (empirical benchmark + rollback) | Can be measured against an external receipt and rolled back if worse. Benefit is *demonstrated*, not *proven*. |

This is why the 8 protected-body invariants (§5) are *all* irreversibility
protections. They are correctly scoped: each one guards a door that, once walked
through, cannot be walked back. Proof belongs exactly and only there.

For the reversible majority, proof is the wrong tool — and insisting on it would
be hobbling. The right tool is the DGM paper's own loop: apply the change in
shadow, run the empirical benchmark, keep it only if it improves a real signal,
roll back otherwise. The repo already has both halves of this:
`diff_applier.apply_and_test()` (apply → test → rollback-on-failure, line 273)
and the DGM shadow default (`DHARMA_EVOLUTION_SHADOW`, dgm_loop.py:289). Benefit
is gated by reality and rollback — not by a theorem about benefit, which we
cannot have.

**The discipline that keeps this honest:** the moment a hard proof-gate starts
blocking *reversible, benchmarkable* moves, it has crossed from enabling to
hobbling. Proof is a scalpel for the irreversible, never a tax on the
recoverable.

---

## 4. The Hobbling Test — when the gate strangles vs. enables

A gate is dharmic when it removes moves that would have been *regretted*; it is
hobbling when it removes moves that would have been *chosen*, or taxes every move
regardless of quality (northstar §VI-bis). TelosProof must hold itself to this,
because a constructibility constraint is exactly the kind of gate that can
quietly overgrow.

**TelosProof carries its own false-positive rate.** Every time the AST check
falls back to REVIEW/BLOCK on a patch that a human then judges fine, that is a
false positive, and it must be counted *per gate*. A vocabulary so small that it
rejects most safe patches is not "extra safe" — it is hobbling, and its friction
tax is the metric that proves it. The conservative-by-design vocabulary buys
soundness at the cost of recall; the false-positive rate is the price tag, and it
must be visible, not hidden.

**The Wu-Wei Clearance Oracle applies to TelosProof itself.** Adding a primitive
to V must be as easy to *reverse* as to make. The oracle periodically asks: which
primitives, if admitted, would let more aligned-and-reversible patches flow
without admitting any irreversible move? Relaxation is a first-class move. A
vocabulary that only ever grows tighter is a channel narrowing toward a choke
point.

Concretely, the spike commits to surfacing, per gate, the five Hobbling-Test
detectors from the northstar:

1. **Friction tax** — fraction of TelosProof REVIEW/BLOCK outcomes that were
   retrospectively fine.
2. **Goodhart inversion** — are patches being shaped to *pass the AST check*
   rather than to serve the telos?
3. **Throughput of real outcomes** — does TelosProof raise or lower the rate of
   loops closing on reality? Enhancing constraints raise it.
4. **Diversity term** — is the vocabulary homogenizing what patches get
   proposed (Krogh-Vedelsby → 0)?
5. **The bet test** — for any block: *would I bet credibility that this served
   the telos?* Reflexive caution that cannot justify itself is hobbling.

A gate that cannot justify its own false-positive rate is composted, not kept.

---

## 5. The 8 protected-body invariants

A patch is body-safe iff it satisfies all eight. Each is a property of the diff
text and the resulting code — never of intent. Each guards an *irreversible*
door, which is why proof (not reality) is the correct gate for them.

1. **Touches no DGM-protected file.** REUSE `dgm_loop.DGM_PROTECTED_FILES`
   (dgm_loop.py:233, the frozenset `{telos_gates.py, dharma_kernel.py,
   evolution.py, config.py}`) and `_is_protected_dgm_target()` (line 241). Do
   **not** duplicate the list — import it. A second copy is a drift bug waiting
   to happen.
2. **Does not disable receipt emission.** The Web 4.0 trust substrate depends on
   every action leaving a verifiable receipt; a patch that mutes receipts blinds
   the Witness.
3. **Does not disable rollback.** Rollback is the reversibility guarantee that
   lets reality (§3) gate everything else. Killing it makes the recoverable
   irrecoverable.
4. **Does not bypass human approval.** The approval seam is the operator's hand
   on the wheel; a patch that routes around it is constructing autonomy the
   operator did not grant.
5. **Does not raise autonomy level.** Self-granted autonomy escalation is the
   canonical unsafe self-modification.
6. **Does not disable shadow mode.** `DHARMA_EVOLUTION_SHADOW` (dgm_loop.py:289)
   is the propose-don't-apply default; disabling it from inside a patch removes
   the safety net that makes the loop safe to run at all.
7. **Creates no new persistence substrate.** New databases / state stores /
   files outside the sanctioned surfaces are how a self-modifying agent escapes
   its own audit and rollback boundaries.
8. **Preserves replay/rollback metadata.** Backups and the metadata that
   indexes them (cf. `DiffApplier` backup paths, diff_applier.py:234–238) are
   what make a change reversible after the fact; stripping them silently
   converts reversible into irreversible.

These eight are the *proof obligations* of the body. The Lean vocabulary's job
is to prove that no composition of sanctioned primitives can violate any of
them; the Python AST check's job is to confirm a patch stays inside that
vocabulary.

---

## 6. Novelty positioning (honest, narrow)

Proof-before-execution is not new, and the report must not pretend it is. The
prior art is strong and must be cited:

- **Necula & Lee, Proof-Carrying Code (1996)** — untrusted code ships with a
  machine-checkable proof of a safety policy; the host verifies the proof before
  running. TelosProof is PCC's idea applied to self-modification diffs: a patch
  is admissible only if accompanied by (here, *constructible from*) a checkable
  safety witness.
- **seL4 (2009→)** — a full functional-correctness proof of an OS kernel, in
  Isabelle/HOL. Demonstrates that machine-checked proof of a real systems
  artifact is achievable and worth the cost for the most safety-critical core.
  TelosProof borrows the "prove the small trusted core, exhaustively" stance and
  applies it to the safe-primitive vocabulary, not to the whole system.
- **Davidad, Guaranteed-Safe AI (2024)** — the program of pairing capable but
  opaque AI with a verified, formally-specified "gatekeeper" so that the
  *system's actions* carry guarantees even when the *model* does not. TelosProof
  is a small, concrete instance of exactly this split: opaque LLM proposes,
  verified body-checker disposes.

**Where the novelty actually is** — and it is only here:

1. **Patch-level proof-before-apply at autonomous-agent scale.** PCC proved
   policies about delivered binaries; seL4 proved a static kernel; GS-AI frames
   the gatekeeper at the action level. The specific move of putting a
   proof-carrying / proof-constructible gate on *every self-modification diff of
   a continuously self-improving agent* is the novel application surface.
2. **The Lean/Python boundary split.** Heavy invariant proof lives in Lean,
   offline, amortized over the vocabulary; the per-patch hot-path check is a fast
   Python AST membership test. This split — slow soundness offline, fast
   membership online — is what makes patch-level proof affordable inside a live
   agent loop, and it is the engineering contribution.

We claim novelty on those two points and *nothing else*. The underlying idea
(verify before you run, prove the small core) is 1996-and-earlier prior art, and
saying otherwise would be the kind of overclaim TelosProof exists to refuse.

---

## 7. The repo seam

What exists, what is owned, what is reused, what is forbidden.

**Already in place (operator-added, import-only — do NOT redefine):**

- `dharma_swarm/models.py` — `ProofObligation(BaseModel)` with fields
  `{gate_name, obligation_type, predicate, satisfied, evidence_required,
  grounded_by, witness_ref, severity}` (models.py:258), and
  `GateCheckResult.proof_obligation: Optional[ProofObligation]` (models.py:286).
  Also the enums `GateResult{PASS,FAIL,WARN}` (line 87) and
  `GateDecision{ALLOW=allow,BLOCK=block,REVIEW=review}` (line 93). **Import these
  from `dharma_swarm.models`. Do not redefine them.** The `ProofObligation`
  docstring already declares the advisory-by-default, body-not-mind, and
  `DHARMA_PROOF_ENFORCE` contract.

**Owned by this work (the only new files):**

- `dharma_swarm/telosproof/` — the spike's home. Contains the gate function
  (the AST membership check producing a `GateCheckResult` with a populated
  `ProofObligation`), the primitive-vocabulary definition, and the eight
  invariant checks. Returns advisory results; **does not** call into any apply
  path.

**Reused, never duplicated:**

- `dgm_loop.DGM_PROTECTED_FILES` (dgm_loop.py:233) + `_is_protected_dgm_target()`
  (dgm_loop.py:241) — the source of truth for invariant #1. Import; do not copy.
- `DHARMA_EVOLUTION_SHADOW` semantics (dgm_loop.py:289) — the advisory-flag
  precedent that `DHARMA_PROOF_ENFORCE` mirrors exactly (default OFF).

**Advisory flag:**

- `DHARMA_PROOF_ENFORCE` — default OFF. When OFF (the spike state), TelosProof
  computes and records a `ProofObligation` on the `GateCheckResult` but never
  influences whether a patch applies. When ON (a future, operator-reviewed
  state), it would gate. The flag mirrors `DHARMA_EVOLUTION_SHADOW` so the
  enforcement posture is a single, familiar knob.

**The documented integration point (NOT wired in this spike):**

The natural call site is *inside the DGM loop, before* `DiffApplier.apply()`
(diff_applier.py:184) / `apply_and_test()` (diff_applier.py:273), at the same
stage as the existing `_is_protected_dgm_target()` check (dgm_loop.py:351). A
future T-step would, when `DHARMA_PROOF_ENFORCE` is ON, run the TelosProof gate
there and treat a non-ALLOW `GateDecision` as a refusal — exactly as the
protected-file check already returns early today. **This spike documents that
seam and does not touch it.** No edits to `diff_applier.py`, `dgm_loop.py`,
`telos_gates.py`, `dharma_kernel.py`, or `evolution.py`.

---

## 8. The PR sequence (T0 → T5)

A disciplined, default-off, reality-gated ladder. Each step is advisory until
explicitly promoted, and each carries its own verification.

- **T0 — Spike (this report).** Doctrine, architecture, calibration, invariants,
  novelty, seam. No code on the apply path. Establishes the `dharma_swarm/telosproof/`
  package and the import-from-models contract. *Verifier: this document reviewed;
  interfaces confirmed against real files.*

- **T1 — The 8 invariant checks (advisory, body-only).** Implement each invariant
  as a pure function over a parsed diff, reusing `DGM_PROTECTED_FILES` for #1.
  Output a `ProofObligation` per check. No vocabulary yet — just the body
  predicates. *Verifier: unit tests per invariant, including adversarial diffs
  that should FAIL each one.*

- **T2 — The gate function + `GateCheckResult` plumbing.** Compose the eight
  checks into a single advisory gate returning `GateCheckResult` with
  `proof_obligation` populated and `DHARMA_PROOF_ENFORCE` honored (default OFF →
  always ALLOW, obligation recorded). *Verifier: tests that ENFORCE-off never
  blocks; ENFORCE-on blocks an invariant-violating diff.*

- **T3 — The safe-primitive vocabulary + AST membership check.** Define the small
  initial vocabulary V; implement the fast AST check that a diff composes only V.
  *Verifier: membership tests; conservative-rejection (false-positive) tests that
  measure and surface the friction tax.*

- **T4 — The Lean vocabulary proof.** Prove offline, in Lean, that V preserves the
  8 invariants under composition. Pin the proof artifact; the Python check trusts
  the proven vocabulary, not a re-proof per patch. *Verifier: Lean proof checks;
  the Lean/Python boundary is documented and the vocabulary IDs match.*

- **T5 — Documented enforcement-on path + Wu-Wei Clearance Oracle hooks.** Wire
  (still behind `DHARMA_PROOF_ENFORCE`, operator-review-gated) the gate at the
  documented seam, and stand up the per-gate false-positive surfacing so the
  Hobbling Test runs continuously and relaxing V is as easy as tightening it.
  *Verifier: live shadow receipts reviewed by operator BEFORE any default flip;
  enforcement remains OFF until then.*

No step flips `DHARMA_PROOF_ENFORCE` to ON by default, and no step wires the live
apply path without explicit operator review of dry-run/shadow receipts —
consistent with the active track's runtime non-goal.

---

## 9. Closing — the clarification, again

> **TelosProof proves about code/body, not mind/intent. It can make certain
> unsafe self-modifications unconstructible. It cannot prove that an opaque LLM
> is wise, honest, or aligned.**

It is a scalpel for the irreversible, scoped to eight body-invariants, paid for
once in Lean and checked cheaply in Python. It gates the irreversible with proof
so that reality can safely gate everything else. Held to the Hobbling Test, it
earns its place by enabling more aligned-and-reversible flow than it blocks — or
it gets composted. That is the whole of what it claims, and the discipline is to
claim nothing more.

*JSCA!*
