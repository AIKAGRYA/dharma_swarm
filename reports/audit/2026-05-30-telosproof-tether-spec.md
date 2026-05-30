---
title: The Elegant Tether — proof-carrying telos into the existing repo (one optional field)
date: 2026-05-30
source: dharma-telosproof-tether workflow (research + repo-map + integration synthesis)
status: DESIGN SPEC — advisory-first, awaiting operator EDIT_AUTHORIZATION
note: 2 of 6 lanes failed structured output (provable-alignment novelty check; evolution-apply map). Seam confirmed by the other 4. Novelty-vs-prior-art unverified — flag before any external claim.
---

# The honest research finding (which IS the answer)

Full **Lean 4 dependent types = a rewrite, not a tether** (6–18 mo, Python has no equivalent). The elegant 2026 path is **contracts at the boundary + monitoring**, proofs only where they matter. OOPSLA-2025 trend: *micro-verification at boundaries beats whole-program proof.* So we do **not** claim full dependent-type proof — we claim **validated proof-obligations at the mutation boundary**, grounded by a real receipt, enforced advisory-first. Honest, incremental, production-ready.

# ⭐ The chosen tether — ONE optional field

```python
# dharma_swarm/models.py  (after GateCheckResult, ~lines 258–264)
class ProofObligation(BaseModel):
    gate_name: str
    obligation_type: Literal["safety_contract", "fitness_bound", "axiom_satisfaction"]
    predicate: str                       # the checkable constraint
    evidence_required: list[str] = Field(default_factory=list)
    grounded_by: str | None = None       # receipt id (the keystone link)
    witness_ref: str | None = None       # Sakshi observation
    severity: Literal["advisory", "enforcing"] = "advisory"

class GateCheckResult(BaseModel):
    ...                                  # existing fields unchanged
    proof_obligation: ProofObligation | None = Field(default=None)   # ← THE SEAM
```

**That single optional field is the whole tether.** Everything else hangs off it.

# Why it's the most elegant (8 reasons it "disappears into the system")
1. **One optional field** → all **11 existing blocking callers + advisory sites work unchanged** (zero breakage).
2. **Mirrors the existing `gate_decision` pattern** — proof obligations are just metadata on the gate result. *Extends, doesn't duplicate* (anti-slop Rule 2).
3. **Grounded by the keystone** — `FitnessScore.from_external_receipt()` is the *only* way fitness rises; `proof_obligation.grounded_by` points at the real receipt. Stays **outward**, not recursive.
4. **Advisory-first → enforce later** behind a `DHARMA_PROOF_ENFORCE=1` env flag — **the same shadow→live pattern the repo already uses for `DHARMA_EVOLUTION_SHADOW`.** The repo already knows how to gate dangerous capability this way; we reuse its own immune reflex.
5. **Witness-native** — `proof_obligation.witness_ref` stores the Sakshi observation; the audit trail already exists.
6. **Extensible** — new gates proposed via `GateRegistry` auto-emit obligations; S5 (you) approves → severity flips `advisory`→`enforcing`. No code change to add gates.
7. **No new substrate** — explicitly *rejected* a `ProofStore`/`ProofRegistry` (would split proof metadata = Rule 2 violation).
8. **Deterministic** — rejected fuzzy/Bayesian gate results (proofs need decidable predicates).

# The seam (exact files, ~45 lines total)
- `models.py` — add `ProofObligation` + the optional field (~15 lines). **The only structural change.**
- `telos_gates.py` — `TelosGatekeeper.check()` optionally emits a `ProofObligation` for the **AHIMSA gate only**, advisory (~5 lines).
- `archive.py` — add `FitnessScore.from_external_receipt()` classmethod (the keystone, ~20 lines) + reuse existing `gates_passed/gates_failed` for proof labels.
- `evolution.py` — `Proposal` mirrors the optional field (~2 lines); apply-seam (`evolution.py:1414`) reads it under the enforce flag.
- `witness.py` — attach proof evidence to `AuditFinding` (~3 lines, optional).

# Incremental rollout (advisory → enforcing)
- **Phase A (Day 1, advisory):** `ProofObligation` + optional field; wire **AHIMSA only** to emit an advisory obligation on WARN/BLOCK. *Receipt:* propose a mutation containing "delete all data" → `GateCheckResult.decision=BLOCK` carries a populated `proof_obligation`. Nothing enforced yet; nothing breaks.
- **Phase B (Day 2):** mirror the field onto `Proposal`; thread it through gate_check.
- **Phase C (Day 3, keystone closure):** implement `FitnessScore.from_external_receipt(receipt)`; wire `grounded_by` → receipt id. *Receipt:* a real external receipt (CI test-pass, payment, satellite datum) raises fitness; nothing else can.
- **Phase D (Day 4+, enforcement):** behind `DHARMA_PROOF_ENFORCE=1`, AHIMSA's predicate must hold before apply. *Receipt:* a violating mutation is blocked *at apply*, not just logged.
- **Phase E (ongoing):** new gates auto-emit obligations; you approve → severity flips to enforcing.

# First build step (today, ~30 min)
Read `models.py:258–264`, add the `ProofObligation` model + the one optional field. That's the entire structural commitment. Everything after is incremental and reversible (the enforce flag defaults off).

# Candidates considered & rejected (the discipline)
Full Lean 4 (rewrite) · Z3/Dafny (manual hints, NP-complete) · icontract (per-function, not system-wide) · **new ProofStore substrate (Rule 2 violation)** · fuzzy/Bayesian gates (loses determinism) · outcome-bonds-only (orthogonal — economic slashing, not logical proof; good Phase-2 complement) · Sakshi k-of-n consensus (Phase 2) · axiom-refinement (axioms are immutable; obligations are per-mutation).

# The picture in one line
> Proof-carrying telos enters the repo as **a single optional field that mirrors the existing gate pattern, grounds on a real receipt, and turns on the same way the repo already turns on dangerous capability — behind a shadow flag.** Misalignment becomes un-typeable *incrementally, reversibly, and without a rewrite.*

# Honest gaps (2 lanes failed)
- **Novelty unverified:** the "is TelosProof prior-art / who else is doing guaranteed-safe-AI" lane didn't return. Do not claim novelty externally until checked (Davidad/ARIA "guaranteed safe AI" is the nearest neighbor to verify against).
- **Evolution-apply seam** map didn't return; covered indirectly via `evolution.py:1414` + `archive.py:347`. Re-confirm the apply-time read before Phase D.
