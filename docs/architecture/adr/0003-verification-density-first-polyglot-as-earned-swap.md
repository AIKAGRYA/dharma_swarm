# ADR 0003 — Verification density first; polyglot as an earned swap

**Status:** Accepted (2026-05-30)
**Deciders:** @AmitabhainArunachala (operator) + opus_composer (Opus 4.8), grounded by a 6-agent research+red-team pass (`wf_5e11d13d-48a`) and external input from Grok.
**Supersedes/relates:** docs/vision_maps/2026-05-30_binocular_witness_seer_northstar.md (§VI-bis Hobbling Test); reports/audit/2026-05-30-full-lean-verdict.md.

## Context

An external model (Grok) recommended a Python+Rust+Go+Lean polyglot architecture to future-proof dharma_swarm. The operator — a visionary solo non-engineer building for AI's inevitable evolution — pushed back on the human-bus-factor objection: AI maintainers are getting more powerful, and *different languages can verify each other*.

Both points are partly right. A 6-agent research/red-team pass established:

- **AI can already mostly maintain polyglot** for the *writing* (Go ~95%, Rust ~85–92%, Lean ~70% today → ~85% by mid-2027; cost negligible). The bus-factor objection genuinely weakens under AI maintenance.
- **But the real driver of AI-maintainability is verification density + clean contracts, not language count.** AI's strength is generate-and-check-against-spec; its failure mode is unverified drift, *amplified* by parallelism. A verification-heavy system is *more* AI-maintainable.
- **"Languages verify each other" is the Transcendence Principle applied to implementations** — decorrelated failure modes (Python logic / Rust ownership / Go races / Lean proofs) catch what each alone would miss. Powerful, but expensive; spend it surgically on the highest-stakes invariants.
- **Edge curve (honest, conditional):** polyglot *without* verification = **−5 to −8%** (worse than Python monoculture). *With* verification: ~0% now → +1–2% (6mo) → +3–5% (1yr). The edge is positive only *riding on* verification.
- **The crossover is a verification threshold, not a calendar:** ≥45% test density (we are at **59.6% — PASS**) + 3–5 Lean-formalized axioms + mutation testing + one live proof-carrying example. ~3–4 months at current velocity.
- **Deepest finding:** *proof-carrying code is more maintainable than bus-dependent knowledge.* Verification density doesn't just make polyglot safe — it dissolves the bus-factor objection, because the knowledge lives in proofs/contracts, not a human head.

## Decision

1. **Build verification density now.** Extend TelosProof to a Lean primitive-vocabulary (v1), formalize 3–5 DharmaKernel axioms in Lean, add mutation testing to CI, land one live proof-carrying shadow evolution, make the Guardian/contract schemas machine-readable, and build automated cross-language contract/IDL synthesis. This is the AI-ready substrate *and* the polyglot-ready substrate — they are the same thing.
2. **Stay Python-dominant.** Python remains the intelligence/orchestration layer (~70–80%).
3. **Lean is the one second language we adopt now — scoped to the verification kernel.** Not Aeneas-translates-Rust pipelines; just the proof-carrying gate's primitive vocabulary.
4. **Rust and Go are deferred — adopted later, one module at a time, evidence-gated** (a proven, measured performance/scale need + revenue to fund it), behind verified seams so adoption is a clean swap, not a rewrite.
5. **Cross-language verification is reserved for the highest-stakes invariants** (the safety kernel), where decorrelated checking earns its maintenance cost.

## Consequences

- **Now:** ~0% architecture friction; clear positive, compounding verification edge; zero bus-factor risk for the polyglot we *haven't* adopted.
- **~3–4 months:** verification threshold crossed → polyglot becomes a clean, positive-edge, AI-maintained swap available on demand.
- **1 year (vision):** a proof-carrying, multi-language, AI-maintained system — 50%+ test density, 5–8 Lean axioms, mutation testing in CI, one Rust↔Go contract pair with Lean proofs-of-properties, `DHARMA_PROOF_ENFORCE=1` at high autonomy; Opus-5-class agents auditing across languages + proofs simultaneously; ~40% fewer prod bugs; 1–2 FTE of founder time freed for revenue.

## Explicitly NOT now
Full Rust/Go rewrite · force polyglot before revenue · flip `DHARMA_PROOF_ENFORCE` before thresholds · cross-language FFI before contracts are automated · hire polyglot specialists before the substrate is solid.

## Guardrail
This decision is itself subject to the **Hobbling Test** (north-star §VI-bis): if verification density ever starts *taxing every move* instead of *enabling* faster AI maintenance, relax it (Wu-Wei Clearance). And it is **revenue-sensitive** — a real paying customer or investor requirement can re-open the polyglot timeline at any point.
