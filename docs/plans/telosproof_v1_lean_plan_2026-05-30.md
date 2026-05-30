# TelosProof v1 — The Lean POWER Plan (~4 weeks)

**Date:** 2026-05-30
**Status:** PLAN (advisory-only build; no live-path wiring)
**Track relation:** Subsidiary to `goodworks-dgm-core-2026-05` — hardens the DGM self-modification body without adding a new orchestration substrate.
**Owner of this doc:** opus_composer
**North-star context:** `docs/vision_maps/2026-05-30_binocular_witness_seer_northstar.md` (referenced by `ProofObligation` docstring at `dharma_swarm/models.py:266`).

---

## 0. The one-sentence claim

The self-modifying part of dharma_swarm (the DGM loop) is the part most worth proving safe — so we build a *proof-carrying-telos* layer that emits a machine-checked certificate that any candidate patch preserves the 8 protected-body invariants, **advisory-first**, gated behind `DHARMA_PROOF_ENFORCE` exactly the way evolution is already gated behind `DHARMA_EVOLUTION_SHADOW`.

We prove about the **body** (the diff / the resulting code), never about the agent's mind or intent. A proof of intent is a category error; a proof that a diff touches no protected file, disables no receipt emission, and raises no autonomy level is a real, decidable property.

---

## 1. Why this exists now (the threat model, stated plainly)

`dharma_swarm/dgm_loop.py` is an open-ended Darwin–Gödel-Machine loop that proposes diffs to its own source and (when autonomy is high enough and shadow is off) applies them via `dharma_swarm/diff_applier.py`. Today the safety boundary is:

- A **denylist of filenames** — `DGM_PROTECTED_FILES` (`dgm_loop.py:233`), checked by `_is_protected_dgm_target()` (`dgm_loop.py:241`), enforced at `dgm_loop.py:351`.
- A **default-on shadow flag** — `DHARMA_EVOLUTION_SHADOW` default `"1"` (`dgm_loop.py:289`), only disabled when env is `"0"` AND `DGC_AUTONOMY_LEVEL >= 2`.

That is good, but it is a *string-match perimeter*. It answers "does this patch edit `telos_gates.py`?" It does **not** answer "does this patch, while only editing an allowed file like `agent_runner.py`, quietly delete the receipt-emission call, or flip a shadow default, or `chmod` a new on-disk queue into existence?" The denylist guards the *named* files; it does not guard the *invariants those files exist to protect* when a patch achieves the same harm from an allowed file.

TelosProof closes that gap by attaching a **proof obligation** (`ProofObligation`, `models.py:258`) to the gate result for every candidate patch, asserting the 8 protected-body invariants over the *diff*, not over the filename.

### The 8 protected-body invariants (the contract a patch must satisfy)

These are properties of the candidate diff. They are the proof targets.

1. **Touches no DGM-protected file.** REUSE `dgm_loop.DGM_PROTECTED_FILES` — do **not** duplicate the frozenset. The proof reads the live set so the two can never drift.
2. **Does not disable receipt emission.** No removal/short-circuit of the witness/receipt write calls.
3. **Does not disable rollback.** No removal of backup creation or the rollback path (`diff_applier.rollback`, backups recorded in `ApplyResult.backup_paths`).
4. **Does not bypass human approval.** No edit that routes around the approval gate.
5. **Does not raise autonomy level.** No write to `DGC_AUTONOMY_LEVEL` or equivalent that increases self-modification authority.
6. **Does not disable shadow mode.** No flip of `DHARMA_EVOLUTION_SHADOW` default or the `dgm_loop.py:289` guard logic.
7. **Creates no new persistence substrate.** No new SQLite file, no new JSONL queue, no new on-disk store. (Directly mirrors anti-slop Rule 2 `no-new-substrate` and the track non-goal "Do not create a second task board, ledger, runner, router, or evolution engine.")
8. **Preserves replay/rollback metadata.** No edit that strips lineage / replay / `backup_paths` bookkeeping that makes a rollback reconstructable.

Each invariant becomes one `evidence_required` entry on the `ProofObligation`, and the conjunction of all eight is the predicate the Lean kernel checks.

---

## 2. Architecture at a glance

```
  candidate diff (str, unified)
          │
          ▼
  ┌─────────────────────────────┐
  │ diff_to_change_summary()    │  ← THE TRUSTED BASE (conservatism obsession)
  │  Python; ~the only thing    │     Translates raw diff text into a typed,
  │  that can be "wrong" in a    │     over-approximating ChangeSummary.
  │  way the kernel can't catch  │     Every ambiguity resolves to "unsafe".
  └─────────────────────────────┘
          │  ChangeSummary (typed, conservative)
          ▼
  ┌─────────────────────────────┐
  │ emit_lean_obligation()      │  Renders ChangeSummary + the 8 invariants
  │  Python; pure templating     │  into a Lean theorem over the primitive
  │                             │  vocabulary. No logic, just substitution.
  └─────────────────────────────┘
          │  Lean source (theorem patch_is_safe : ...)
          ▼
  ┌─────────────────────────────┐
  │ Lean daemon (persistent)    │  Amortizes the 2–5 s `lake`/elaboration
  │  subprocess, JSON-RPC over   │  startup. Imports the pre-verified
  │  stdio; one warm import of   │  primitive library ONCE; checks each
  │  the primitive library       │  obligation against the warm kernel.
  └─────────────────────────────┘
          │  Checked(true/false) + kernel diagnostics
          ▼
  ┌─────────────────────────────┐
  │ telosproof.gate()           │  Builds GateCheckResult with a populated
  │  → GateCheckResult           │  ProofObligation (satisfied=True/False,
  │    (.proof_obligation set)   │  severity advisory|enforcing per env).
  └─────────────────────────────┘
          │
          ▼   ADVISORY: logged, attached, never blocks (default)
          │   ENFORCING: blocks IFF DHARMA_PROOF_ENFORCE=1 (documented point only)
```

**The load-bearing insight:** the Lean kernel is *not* the trusted base. The trusted base is `diff_to_change_summary()` — the ~one Python function that turns untrusted diff text into the typed facts the kernel reasons about. If that translator is wrong (says "this diff doesn't touch receipts" when it does), the kernel will faithfully prove a false thing. So §4 is the most important section of this plan.

---

## 3. The Lean primitive vocabulary — verify ~250 LOC once, get ~5K proofs

### The economics

We do **not** write a Lean proof per patch by hand. That would not scale, and the swarm cannot wait on a human Lean engineer per generation. Instead:

- **Once, by hand (or by a careful expert pass):** verify a small, fixed *primitive vocabulary* — roughly **250 LOC of Lean** defining the safe-patch predicates and the ~12–20 lemmas that compose them. This is the only Lean a human ever audits line-by-line. It is verified once and frozen (content-hashed; any change re-triggers the human audit).
- **Per patch, automatically:** the obligation for a given diff is a *mechanical instantiation* of those primitives over the diff's `ChangeSummary`. Most obligations discharge by `decide` / `simp` / `rfl` over decidable predicates — no creative proof search. Where structure is needed, **Leanstral** (Mistral's Lean-autoformalization model) produces the proof term, and the kernel checks it. The kernel is the judge; Leanstral is a (fallible, cheap) prover whose output is *verified*, not trusted.
- **The leverage ratio:** ~250 LOC verified once → on the order of **~5K machine-checked patch proofs** across the lifetime of the loop, each one cheap because the hard reasoning is amortized into the primitives.

This is the classic "small trusted core, large untrusted-but-checked periphery" shape. Leanstral can hallucinate a wrong proof; it cannot make the kernel accept a wrong proof. That asymmetry is the whole game.

### What the primitives look like (sketch — not final Lean)

The vocabulary is a model of "a patch" reduced to exactly the facts the 8 invariants need:

```lean
-- telosproof primitives (~250 LOC total, verified once, content-hashed)

structure ChangeSummary where
  touchedFiles      : List String       -- basenames, conservative
  removesReceiptCall: Bool              -- over-approximated: unknown ⇒ true
  removesRollback   : Bool
  bypassesApproval  : Bool
  raisesAutonomy    : Bool
  disablesShadow    : Bool
  createsPersistence: Bool
  stripsReplayMeta  : Bool

-- the protected-file set is NOT redefined here; it is supplied as a
-- parameter from dgm_loop.DGM_PROTECTED_FILES at obligation-emit time,
-- so Lean and Python share one source of truth.

def touchesProtected (cs : ChangeSummary) (protected : List String) : Bool :=
  cs.touchedFiles.any (fun f => protected.contains f)

def patchIsSafe (cs : ChangeSummary) (protected : List String) : Prop :=
    touchesProtected cs protected = false
  ∧ cs.removesReceiptCall = false
  ∧ cs.removesRollback    = false
  ∧ cs.bypassesApproval   = false
  ∧ cs.raisesAutonomy     = false
  ∧ cs.disablesShadow     = false
  ∧ cs.createsPersistence = false
  ∧ cs.stripsReplayMeta   = false

instance (cs : ChangeSummary) (p : List String) : Decidable (patchIsSafe cs p) := by
  unfold patchIsSafe; infer_instance
```

Because `patchIsSafe` is `Decidable`, the per-patch obligation is literally `theorem this_patch_safe : patchIsSafe <cs> <protected> := by decide`. The expensive part (proving `Decidable`, proving the composition lemmas) lives in the 250 LOC and is paid once.

### Why Leanstral matters here specifically

The 8 invariants above are the *floor*. As the contract grows (temporal invariants — see §6, "X holds across every generation, not just this one"), obligations stop being pure `decide` and start needing real proof terms. Leanstral autoformalizes those: given the English invariant + the `ChangeSummary` structure, it emits a candidate Lean proof, the daemon checks it, and only kernel-accepted terms count. This is the path to "~5K proofs without 5K human-hours."

---

## 4. The diff→ChangeSummary translator — the real trusted base (conservatism obsession)

**This is where correctness actually lives.** Everything downstream is machine-checked; this function is not. So it is written under one rule, stated three ways:

> **When in doubt, say "unsafe."** Every field of `ChangeSummary` over-approximates harm. An ambiguous diff resolves to the dangerous interpretation. A diff we cannot parse resolves to "touches everything / disables everything." False positives (rejecting a safe patch) are cheap — the patch just doesn't auto-apply and waits for a human. False negatives (accepting a harmful patch) are the thing we are spending all this machinery to prevent.

### Concrete conservatism rules

- **Filename extraction:** parse the unified diff headers. If *any* header is malformed or a path can't be resolved, set `touchedFiles` to include every protected basename → forces `touchesProtected = true` → unsafe.
- **Receipt removal (`removesReceiptCall`):** scan removed (`-`) lines for any call matching the receipt/witness emit surface. Default to `true` if the diff edits a file known to contain receipt emission and we can't prove the call survived. We do not try to be clever about control flow — deletion *or* guarding *or* renaming the emit call all count as removal.
- **Rollback / replay metadata (`removesRollback`, `stripsReplayMeta`):** any removed line touching `backup`, `rollback`, `backup_paths`, lineage, or replay bookkeeping → `true`.
- **Autonomy / shadow (`raisesAutonomy`, `disablesShadow`):** any added/removed line referencing `DGC_AUTONOMY_LEVEL`, `DHARMA_EVOLUTION_SHADOW`, or the guard expression at `dgm_loop.py:289` → `true`. (We are deliberately coarse: even a *comment* mentioning these flips the bit. Cheap false positive, no false negative.)
- **Persistence (`createsPersistence`):** any added line opening a file for write outside the known witness/backup paths, any `sqlite`, `aiosqlite`, `open(..., "w"/"a")`, new `.jsonl`/`.db` path → `true`.
- **Approval bypass (`bypassesApproval`):** any edit to the approval-gate call sites → `true`.
- **Unknown construct:** if the translator encounters a diff shape it has no rule for, it sets the *whole summary* to maximally-unsafe and records the reason in `evidence_required`.

### Trusted-base discipline (how we keep this honest)

- The translator is **the only** module in TelosProof allowed to be "smart." Everything else is templating or kernel-checking.
- It carries its own adversarial test corpus: a `tests/test_telosproof_translator.py` whose every case is a *malicious diff* (delete-receipt-from-allowed-file, flip-shadow-via-comment, sneak-a-sqlite, rename-the-emit-call) that MUST translate to an unsafe `ChangeSummary`. Red-team-first: write the attack, then the rule that catches it.
- It REUSES `dgm_loop.DGM_PROTECTED_FILES`, `dgm_loop._is_protected_dgm_target`, and the `DHARMA_EVOLUTION_SHADOW` semantics by import. No re-derivation, no parallel copy — drift in the perimeter would silently weaken the proof.
- Its output is logged in full (the `ChangeSummary`) into the `ProofObligation.evidence_required` and the witness log, so a human reviewing an advisory result can see *why* a patch was called unsafe.

---

## 5. The Lean daemon — persistent subprocess to amortize 2–5 s startup

A cold `lake env lean` / elaboration of even a tiny file pays a 2–5 second tax (toolchain init + importing the primitive library + Mathlib-adjacent deps if any). In a loop that runs many generations, paying that per check is unacceptable.

**Design:**

- A long-lived subprocess (`lean --server`-style, or a thin custom Lean executable) started **once**. It imports the verified primitive library a single time, holding the warm environment.
- Communication over **JSON-RPC on stdio**: Python sends `{ "obligation": "<lean theorem text>", "id": N }`; the daemon elaborates against the warm environment and replies `{ "id": N, "checked": true|false, "diagnostics": "..." }`.
- **Lifecycle:** lazy-start on first obligation; health-pinged; auto-restarted on crash with exponential backoff; hard-killed and fell-back-to-advisory-FAIL if it can't come up (a dead prover is treated as "cannot prove safe" → conservative).
- **Isolation:** the daemon never writes to the repo, never has network, runs under a timeout per obligation (a runaway elaboration is a FAIL, not a hang).
- **No new persistence substrate** (invariant #7 applies to us too): the daemon holds state in memory only; it writes nothing to disk. Results flow back through the existing witness log via the gate, not a new store.

**Owned files for the daemon:** `dharma_swarm/telosproof/lean_daemon.py` (Python side: spawn, JSON-RPC, lifecycle) and `dharma_swarm/telosproof/lean/` (the verified `.lean` primitive library + a `lakefile`). These are new files in a new, self-contained package — they touch no existing module.

---

## 6. Why Lean over Dafny

Both are real options; Lean wins on five axes that matter to *this* system specifically.

| Axis | Lean 4 | Dafny | Why it matters here |
|---|---|---|---|
| **Multi-kernel resilience** | Tiny, well-studied type-theoretic kernel; multiple independent checkers exist | Trusts Z3 (an SMT solver) as part of its TCB | We are building a *trust* artifact. A patch "proven safe" by a giant SMT solver inherits Z3's TCB and Z3's occasional unsoundness bugs. Lean's kernel is small enough to re-check with an independent kernel — the proof's validity doesn't rest on one tool's correctness. |
| **Proof portability** | Proof terms are first-class objects; export paths to **Rocq (Coq)** and **Isabelle** are an active, real ecosystem | Proofs are SMT-discharged; not portable as checkable objects | If we ever want a *second, independent* check of a safety certificate — the decorrelated-verifier move, exactly the Transcendence Principle applied to proofs — Lean lets us re-check the same proof term under a different kernel. Dafny proofs don't travel. |
| **Temporal-invariant expressiveness** | Full dependent type theory; can state "property P holds across every generation of the lineage," inductive invariants over traces | Designed for method-level pre/post-conditions; temporal/inductive trace properties are awkward | The 8 invariants are per-patch today, but the real target (§"end-state") is *temporal*: "no reachable sequence of patches disables receipts." That is an inductive invariant over the DGM lineage — Lean's home turf, Dafny's edge. |
| **Leanstral** | A dedicated Mistral autoformalization model targets Lean; our path to ~5K proofs without ~5K human-hours runs through it | No comparable autoformalization model for Dafny | This is decisive for the economics. The whole "swarm autoformalizes its own patch proofs" end-state depends on a model that writes the proofs. That model writes Lean. |
| **Research/community trajectory** | Mathlib, active 2025–2026 AI-for-proof work, the center of gravity for ML+formal | Smaller, more industrial-verification-focused community | We want the layer to ride the AI-for-formal-methods wave, not fight it. |

**The honest counterpoint:** Dafny would be *faster to a first advisory result* for the simple `decide`-able invariants, because its auto-active SMT discharge means less hand-written proof scaffolding up front. We are accepting a slightly steeper week-1 ramp (writing the 250 LOC of primitives) in exchange for portability, a smaller TCB, and the Leanstral autoformalization path that makes the long game work. For a layer whose entire reason to exist is *trust*, a smaller trusted kernel beats faster time-to-green.

---

## 7. Honest costs (no hand-waving)

- **Toolchain weight.** Lean 4 + `elan`/`lake` + the primitive library is a heavy dependency to drag onto the M5 and into any CI that runs the check. We mitigate by: (a) keeping the primitive library Mathlib-*free* if at all possible (the 8 invariants need only `List`, `Bool`, `Decidable` — no analysis, no algebra), which keeps the import small and the daemon warm-up nearer 2 s than 5 s; (b) making the entire layer optional and lazy — if Lean isn't installed, TelosProof degrades to a Python-only structural check that emits an advisory `ProofObligation` with `satisfied=None` and a "prover unavailable" reason. The system never *requires* Lean to run.
- **Rare expert pool.** People who can audit 250 LOC of Lean and vouch for the primitive vocabulary are scarce, and Dhyana is not one of them (no tech background — by design we keep the human-audited surface to ~250 LOC precisely so a single contracted Lean expert can review it in an afternoon, once, and re-review only on the content-hash change). The expense is real and front-loaded; it does not recur per patch.
- **Kernel-trust is aspirational until Lean4Lean (~2027).** The strongest version of the trust story — "the Lean kernel itself is verified" — rests on **Lean4Lean** (the Lean-kernel-in-Lean / external independent re-checker effort), which is not a finished, drop-in guarantee today. Until it lands (~2027 by current trajectory), our TCB is: the translator (§4) + the Lean kernel binary as-shipped + the 250 LOC primitives. We state this plainly rather than over-claiming "machine-verified safety." Today's honest claim is: *"a machine-checked certificate, against a small audited vocabulary, that this diff preserves the 8 protected-body invariants — advisory."* Not *"provably safe self-modification."*
- **Translator is unverified by construction.** Restating §4's cost as a cost: the one part that can be wrong is the part we can't prove. We buy down that risk with an adversarial red-team test corpus and aggressive over-approximation, not with a proof. This is the single largest residual risk and we name it.
- **Latency floor.** Even warm, each obligation costs elaboration time. Acceptable in shadow/advisory (it's out of the hot path); would need profiling before any enforcing use.

---

## 8. Integration point — DOCUMENTED ONLY, not wired

Per the hard rules, this plan does **not** insert TelosProof into the live apply path. We provide the gate function and *document* exactly where a future, operator-approved change would call it.

**The function we own and provide:**

```python
# dharma_swarm/telosproof/gate.py  (OWNED, new)
from dharma_swarm.models import GateCheckResult, GateDecision, GateResult, ProofObligation

def telosproof_gate(diff_text: str, *, enforce: bool | None = None) -> GateCheckResult:
    """Advisory proof-carrying-telos check over a candidate diff.

    Returns a GateCheckResult whose .proof_obligation records whether the
    8 protected-body invariants are satisfied. ALWAYS returns decision=ALLOW
    when enforce is False (advisory); only returns BLOCK when enforce is True
    AND an invariant is violated. `enforce` defaults to the DHARMA_PROOF_ENFORCE
    env flag (default off), mirroring DHARMA_EVOLUTION_SHADOW semantics.
    """
    ...
```

It imports `ProofObligation` / `GateCheckResult` / `GateDecision` / `GateResult` **from `dharma_swarm.models`** (operator already added `ProofObligation` at `models.py:258` and `GateCheckResult.proof_obligation` at `models.py:286`). It does **not** redefine them.

**The documented integration point (a future change, not this one):**

In `dharma_swarm/dgm_loop.py`, the protected-target check at **line 351** (`if _is_protected_dgm_target(source_path):`) is the natural seam. A future operator-approved wiring would, immediately *after* that filename check passes, call `telosproof_gate(candidate_diff, enforce=os.environ.get("DHARMA_PROOF_ENFORCE") == "1")` and:

- **Advisory (default, `DHARMA_PROOF_ENFORCE` unset/`"0"`):** attach the returned `ProofObligation` to the generation's record / witness log; **never** alter control flow. The loop proceeds exactly as today.
- **Enforcing (`DHARMA_PROOF_ENFORCE="1"`, opt-in, never default):** if `result.decision == GateDecision.BLOCK`, set `result.error` on the `DGMResult` and return *before* reaching `diff_applier.apply` — the same shape as the existing protected-target rejection at `dgm_loop.py:351–357`.

A second documented seam is `dharma_swarm/diff_applier.py` — `apply()` (line 184) and `apply_and_test()` (line 273). We note it but **prefer the `dgm_loop.py:351` seam**, because the DGM loop is where "this is a self-modification candidate" is known; `diff_applier` is a lower-level mechanism that also serves non-self-mod diffs, and gating it would over-reach. **We write neither edit in v1.** The seam is documented; the wiring is a separate, reviewed PR.

**Env-flag parity (the safety contract of this whole plan):**

| Flag | Default | Controls | Lives at |
|---|---|---|---|
| `DHARMA_EVOLUTION_SHADOW` | `"1"` (on) | Whether DGM proposes-only vs applies | `dgm_loop.py:289` (existing) |
| `DHARMA_PROOF_ENFORCE` | unset/`"0"` (off) | Whether a failed proof *blocks* vs merely *advises* | `telosproof/gate.py` (new, this plan) |

TelosProof is born advisory, exactly as evolution was born shadowed. It cannot block anything until an operator flips a default-off flag, and even then only the DGM loop, only after the existing filename perimeter, never inside `diff_applier`.

---

## 9. End-state — the swarm autoformalizes its own patch proofs

The four-week v1 ships the advisory scaffold. The trajectory it points at:

1. **v1 (this plan):** translator + primitives + daemon + advisory gate function, fully exercised by tests, attached to records but wired to nothing live. Humans read the advisories.
2. **v2:** operator flips `DHARMA_PROOF_ENFORCE=1` in a sandbox after a corpus of advisory results shows zero false-negatives on the red-team set. The Python structural translator still produces every `ChangeSummary`.
3. **v3 — Leanstral in the loop:** as the contract grows past pure-`decide` invariants into temporal ones (inductive invariants over the DGM lineage), Leanstral autoformalizes the proof terms. The kernel checks them. The swarm is now *proposing its own safety proofs* and the kernel is the sole arbiter — a patch that cannot be proven safe cannot be auto-applied, and the *proposer of the patch is also (via Leanstral) the proposer of its safety certificate, with the kernel as incorruptible judge*.
4. **End-state:** every self-modification the swarm makes carries a machine-checked certificate, authored by the swarm, checked by a small audited kernel, against a frozen vocabulary, with the option (post-portability) of a *second decorrelated kernel* (Rocq/Isabelle) re-checking the same proof term — the Transcendence Principle (decorrelated verifiers, errors cancel) applied to the safety layer itself.

This is the "binocular witness/seer" north-star in operational form: the *seer* (DGM) proposes change; the *witness* (TelosProof) certifies the change preserves the body's invariants — two eyes, one depth-perception of safety.

---

## 10. Staged PR sequence (4 weeks, all advisory, none wire the live path)

All PRs land in `dharma_swarm/telosproof/` (new self-contained package) + `tests/`. None edit `telos_gates.py`, `dharma_kernel.py`, `evolution.py`, `models.py`, `dgm_loop.py`, or `diff_applier.py`.

### PR 1 — `ChangeSummary` + the trusted-base translator (Week 1, the hard part first)
- **Owned files:** `dharma_swarm/telosproof/__init__.py`, `dharma_swarm/telosproof/change_summary.py` (the `ChangeSummary` Pydantic model + `diff_to_change_summary()`), `tests/test_telosproof_translator.py`.
- **Reuses by import:** `dgm_loop.DGM_PROTECTED_FILES`, `dgm_loop._is_protected_dgm_target`.
- **Acceptance:** the adversarial corpus (≥20 malicious diffs across all 8 invariants) all translate to maximally-unsafe `ChangeSummary`; a hand-written set of benign diffs translate to safe. Conservatism property test: any unparseable diff ⇒ unsafe.
- **Why first:** this is the trusted base. If it's wrong, nothing downstream matters. Build and red-team it before any Lean exists.

### PR 2 — The Lean primitive vocabulary (Week 2)
- **Owned files:** `dharma_swarm/telosproof/lean/Primitives.lean` (~250 LOC), `dharma_swarm/telosproof/lean/lakefile.lean`, `dharma_swarm/telosproof/lean/README.md` (records the content-hash + "verified once" provenance).
- **Acceptance:** the library type-checks under a pinned Lean toolchain; `patchIsSafe` is `Decidable`; a smoke `theorem` over a hand-built safe/unsafe `ChangeSummary` passes/fails as expected. Content-hash recorded.
- **Note:** Mathlib-free if achievable (keeps the daemon light and the audit small).

### PR 3 — `emit_lean_obligation()` + the Lean daemon (Week 3)
- **Owned files:** `dharma_swarm/telosproof/emit.py` (pure templating: `ChangeSummary` → Lean theorem text, supplying `DGM_PROTECTED_FILES` as the parameter so Python/Lean share one source of truth), `dharma_swarm/telosproof/lean_daemon.py` (spawn / JSON-RPC / lifecycle / timeout / fallback-to-advisory-FAIL), `tests/test_telosproof_emit.py`, `tests/test_telosproof_daemon.py` (daemon tests skip cleanly if Lean is not installed).
- **Acceptance:** emit produces a theorem that the daemon checks `true` for a safe summary and `false` for each of the 8 violations; daemon warm-path latency measured and logged; daemon crash → conservative FAIL, never a hang.

### PR 4 — The advisory gate function + integration-point documentation (Week 4)
- **Owned files:** `dharma_swarm/telosproof/gate.py` (`telosproof_gate()` → `GateCheckResult` with populated `ProofObligation`, importing all four types from `dharma_swarm.models`), `tests/test_telosproof_gate.py`, `docs/telosproof/INTEGRATION_POINT.md` (documents — does not perform — the `dgm_loop.py:351` seam and the `DHARMA_PROOF_ENFORCE` parity table from §8).
- **Acceptance:** `telosproof_gate(diff, enforce=False)` ALWAYS returns `decision=ALLOW` with a populated `.proof_obligation` (advisory); `enforce=True` returns `BLOCK` iff an invariant is violated; default reads `DHARMA_PROOF_ENFORCE` (default off). End-to-end test: malicious diff → `ProofObligation.satisfied is False`, `decision` still `ALLOW` under default env. **No edit to `dgm_loop.py` or `diff_applier.py` is included in this PR.**

### (Post-v1, not in the 4 weeks) — Leanstral autoformalization + temporal invariants
- Tracked separately. Begins only after the advisory corpus demonstrates a clean red-team record. This is where "the swarm autoformalizes its own patch proofs" (§9) becomes real.

---

## 11. Guardrails this plan binds itself to

- **Advisory by default, always.** Nothing here can block a patch unless `DHARMA_PROOF_ENFORCE=1`, which is off by default and operator-only. Parity with `DHARMA_EVOLUTION_SHADOW`.
- **No live-path wiring in v1.** The gate function exists; the call site is documented, not written. No edit to `dgm_loop.py` or `diff_applier.py`.
- **No new substrate.** TelosProof writes nothing to disk (invariant #7 applies to itself); results flow through the existing witness log via the gate, not a new store.
- **Import, never redefine.** `ProofObligation`, `GateCheckResult`, `GateDecision`, `GateResult` come from `dharma_swarm.models`. `DGM_PROTECTED_FILES` comes from `dgm_loop`. Zero duplication of the perimeter.
- **Prove about the body, never the mind.** Every invariant is a decidable property of the diff/code. No claim about agent intent appears anywhere in the proof.
- **Untouched files:** `telos_gates.py`, `dharma_kernel.py`, `evolution.py`, `models.py`, the live daemon, git state, secrets, and `docs/plans/2026-05-22-dashboard-ssot-architecture.md` are not edited by any PR in this sequence.
