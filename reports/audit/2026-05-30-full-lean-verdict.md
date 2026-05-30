---
title: Full Lean 4 for TelosProof — verified pros/cons + the power-maximizing verdict
date: 2026-05-30
source: dharma-lean-frontier-research workflow (5 live-web lanes + synthesis), 6 agents
note: 1 lane (autoformalization) failed structured output; recovered via Lanes 2+4 (Leanstral). Verdict is grounded but treat as decision-input, not gospel.
corrects: my earlier "go Lean for the engine" steer — directionally right, imprecise. Sharpened below.
---

# The honest correction (where I was imprecise)

I said "go Lean for the engine, spend power on the extractor." The research sharpens it: **Lean YES — but as a one-time primitive-VERIFIER, not a per-patch runtime checker.** Proving *every patch* in Lean is slow (2–5s cold, daemon needed), unproven at patch-scale (zero autonomous-system precedents), and — for the *decidable boolean invariants* TelosProof v0 needs — buys **no more trust than a hardened SMT solver.** The powerful move is different and better.

# ⭐ The verdict

> **Verify a small safe-PRIMITIVE vocabulary in Lean ONCE; restrict self-modification patches to compose ONLY from those verified primitives; then each patch is a fast AST-check that it uses nothing outside the vocabulary.**

This is how seL4/CompCert actually achieve their guarantees (verify once; the verified artifact is fixed). It gives you Lean's full power *without* per-patch Lean latency:
- ✅ Dependent-type expressiveness (captures even temporal invariants — replay/rollback), one-time.
- ✅ Scales to 1000s of patches/year (each is a cheap composition-check, not a proof search).
- ✅ Future-proofs to 2030 (add primitives, re-use proofs; export to Rocq/Isabelle if Lean ever collapses).
- ✅ Auditable (primitives transparent; patches AST-checkable).

**Power lives in three places — none of them is "more Lean":** (1) the **verified primitive library** (one-time Lean investment), (2) **constraining the modification space** so verification stays decidable, (3) the **diff→ChangeSummary translator soundness** — the real trusted base; false-positives fine, false-negatives forbidden. A perfect Lean proof over a leaky translator proves nothing.

# Full Lean 4 — pros (why Lean over Dafny *when you invest*)
- **Architectural resilience to AI-assisted compromise:** Lean's ~5K-line kernel has **7 independent implementations (Lean Kernel Arena)** — multiple independent watchers. A Z3-dependent system (Dafny, F*) has a single solver as a single point of compromise; Lean assumes Z3 *will* fail.
- **Proof portability:** Lean proofs export to Rocq/Isabelle → survive kernel bugs or ecosystem collapse. Dafny/F*/Verus can't credibly offer this.
- **Dependent types** capture the full semantics of all 8 protected invariants (incl. temporal), not just SMT-decidable logic → scales to richer invariants 2027-28 without solver saturation.
- **Autoformalization is ready (May 2026):** Leanstral generates Lean proofs at ~1/15 Claude cost (31.9% FLTEval). So **"the swarm proves its own patches" is near-term, not sci-fi** — and Lean is the target it's converging on.
- **Kernel-trust gap closing:** Lean4Lean (WITS 2026) is mechanizing the metatheory → roadmap to a verified kernel by 2027. No other system has this trajectory.

# Full Lean 4 — cons (the honest costs)
- **Kernel trust is aspirational, not delivered** today (lean4lean/lean4checker still research-grade). So "Lean-grade trust" is a 2027 promise, not a 2026 fact.
- **No production precedent** for patch-level autonomous verification (unknown unknowns are real).
- **Latency:** 2–5s cold, mathlib imports 5–15min; a persistent daemon is mandatory (lifecycle/restart complexity in a critical path).
- **Rare ecosystem:** ~50 Lean experts worldwide; 4–8 weeks to become productive. Hiring/skill bottleneck.
- **Translator is still unverified TCB** — *identical risk across all substrates.* Lean proves the invariants, not that your diff→summary mapping is faithful.
- **SMT still in the chain** — Lean automation bottoms out in Z3; timeouts → conservative reject + fallback needed.
- **Reproducibility:** must pin Lean version + toolchain + mathlib commit (4.29 ≠ 4.30 invalidates proofs).

# The power-vs-elegance resolution (your tie-breaker, vindicated)
The research says it literally: **"the elegant path loses power; the powerful path looks messy upfront."** Elegant = rewrite in Lean (18–24mo, beautiful, ecosystem unproven at systems scale) — *rejected.* Powerful = Lean verifies a ~200–300 LOC primitive vocabulary; Python stays Python; patches restricted to safe primitives; per-patch AST check — *messy upfront, scales + future-proofs.* Your instinct to lean toward power points **here**, not at full-codebase Lean.

# Recommended path (ship velocity + power target)
- **v0 (days, advisory):** fast decidable boolean gate — Python AST → `ChangeSummary` → invariant check (optionally Z3-backed). Carried by the elegant optional field (`proof_obligation`). Ships now; nothing enforced.
- **v1 (the power investment, ~4 weeks):** formalize the 8 invariants + a safe-primitive vocabulary in Lean (~200–300 LOC, ~5K proofs via Leanstral), Lean→JSON export, Python→Lean translator (~200 LOC), Lean daemon (~150 LOC), wired advisory-first into the DGM apply-path.
- **Obsess over the translator's conservatism in both phases** — that's the real TCB.
- **Substrate when you invest: Lean** (over Dafny) for resilience + portability + temporal expressiveness + Leanstral.

# Novelty positioning (the gap, closed)
**Cite, don't claim-invent:** descends from Necula-Lee **Proof-Carrying Code (1996)**, **seL4** (Klein 2009+), **Davidad's Guaranteed-Safe-AI (2024)**, plus 2026 neighbors (Layered Mutability, SEVerA). **Genuinely novel** = *patch-level invariant proof before apply, at autonomous-agent scale* (seL4/CompCert verify *fixed* components; you verify *evolving* patches) + the *Lean-kernel / Python-DGM boundary separation.* Claim novelty only there.

# 👁 Drishti bonus (real external leverage)
**UK ARIA "Safeguarded AI" programme (£59m) has a funding call due ~July 1, 2026**, TA1 (verifier infrastructure) doubled-down. This is *funded, active, and exactly this problem.* A proof-carrying-gate-for-self-modifying-agents spike is a credible fit. Worth a serious look before the deadline.
