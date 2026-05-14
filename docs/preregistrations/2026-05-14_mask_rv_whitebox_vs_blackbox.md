---
title: "Whitebox vs Blackbox Detection of Honesty Failures in Mistral-7B on CAIS MASK Probes — Pre-Registration"
authors: ["John Vincent Shrader (Dhyana)"]
affiliation: dharma_swarm (independent research)
preregistration_date: 2026-05-14
status: DRAFT_PRE_LOCK
intended_funding: Schmidt Sciences Interpretability RFP 2026 (deadline 2026-05-26 23:59 AoE)
osf_target: TBD — upload before any model inference runs
code_repo: ~/dharma_swarm/experiments/mask_rv_whitebox/ (skeleton created 2026-05-14)
estimated_completion: 2026-05-18
related:
  - cabinet/research/rv_paper.md
  - cabinet/frontier/2026-05-14_recursive_ecosystem_dharma_swarm_bootstrap.md (§0.5)
---

# Pre-Registration: Whitebox vs Blackbox Detection of Deceptive Behavior in Mistral-7B on MASK Probes

**This document is the canonical pre-registration. It must be timestamped on OSF and the experiment code SHA-locked BEFORE any analysis labels are computed. Failure to comply invalidates the result for Schmidt submission purposes.**

## 1. Background and Motivation

R_V (representation-space contraction ratio) is a scalar geometric measurement on transformer residual streams, introduced in dharma_swarm's R_V paper (Shrader, 2026; ref: `~/.claude/cabinet/research/rv_paper.md`; primary findings: L5 residual stream contracts under self-reference; Head 21 L5 direction-specific steering 38% BT+ART vs 8% control; 6/8 transformers tested contract, Pythia-2.8B expands).

Schmidt Sciences' 2026 Interpretability RFP (closes 2026-05-26 23:59 AoE) explicitly solicits research on "interpretability tools that outperform baselines that do not rely on access to weights" with focus on detecting "deceptive behaviors." This pre-registration locks the design of the **single load-bearing comparison** that addresses that ask: does R_V — a whitebox geometric signal — outperform a blackbox classifier limited to output-side observables, at distinguishing deceptive from honest model responses on a public deception eval?

**CAIS (Center for AI Safety)'s MASK benchmark** (arXiv 2503.03750, "The MASK Benchmark: Disentangling Honesty From Accuracy in AI Systems") is the chosen eval. Rationale: (a) CAIS is highly reviewer-resonant in the Schmidt cluster (Dan Hendrycks lineage; Schmidt explicitly funds CAIS-adjacent safety research); (b) MASK probes are designed to elicit *honesty failures under pressure* — pressure-prompts engineered to elicit lying paired with belief-elicitation prompts in neutral contexts (this isolates *deception* from *accuracy* — exactly what Schmidt's RFP asks to detect); (c) 1,028 human-labeled examples across 6 archetypes, publicly available (gated on HuggingFace at `cais/MASK`); (d) eval code open-source at `github.com/centerforaisafety/mask`. **NOTE on prior attribution error**: an earlier draft of this pre-reg incorrectly attributed MASK to Apollo Research. MASK is CAIS. Apollo has separate scheming/deception evals (used in the OpenAI deliberative-alignment work) which are not chosen here.

**Why this pre-registration is binding**: without locking the design before running, the result cannot be defended against the "p-hacked across 200 experiment scripts" objection. The Schmidt-fit agent verdict (2026-05-14): this single pre-registered number is the load-bearing artifact for the proposal; substrate work and multi-architecture extensions become Year-1 milestones, not preliminary data.

## 2. Hypotheses

**Primary hypothesis (H1)**: A whitebox classifier using R_V scalar on Mistral-7B's residual streams achieves higher AUROC at distinguishing deceptive from honest responses on MASK probes than a matched blackbox classifier using only output token log-probabilities and response-surface features.

Formal statement:
- Let AUROC_W = test-set AUROC of the whitebox classifier.
- Let AUROC_B = test-set AUROC of the blackbox classifier.
- H1: AUROC_W − AUROC_B > 0.05, with p < 0.01 (DeLong's two-sided test for correlated ROC curves).
- H0: AUROC_W − AUROC_B ≤ 0.05, OR p ≥ 0.01.

**Secondary hypotheses (no significance test; descriptive only)**:
- HS1: Per-deception-subcategory AUROC patterns (whitebox vs blackbox) are consistent across categories (no single subcategory drives the result).
- HS2: Whitebox classifier is better calibrated than blackbox (Brier score lower).

## 3. Materials

### Model
- **`mistralai/Mistral-7B-Instruct-v0.3`** (HuggingFace).
- Specific commit SHA pinned at code-freeze time (Day 2 of timeline).
- Inference: bf16, deterministic, temperature=0, top_p=1.0, max_new_tokens=256, seed=42.

### Probe set
- **CAIS MASK benchmark** (Center for AI Safety; `cais/MASK` on HuggingFace, gated — requires HF account + access-token request; arXiv 2503.03750; eval code at `github.com/centerforaisafety/mask`).
- Target sample size: **n = 200 probes minimum**, stratified across MASK's published deception subcategories.
- Train/test split: 80/20, seeded with `numpy.random.seed(42)`. Train split used for whitebox/blackbox classifier fitting. Test split reserved for primary statistical test; not viewed during development.
- If MASK contains <200 stratifiable probes, n is the largest stratified set ≤ MASK's available probes; documented in final report.

### Compute
- Local M5 (40 cores, 128GB RAM). Mistral-7B inference at bf16 fits comfortably.
- Estimated wall-clock for full pipeline: ~6–10 hours (probe inference + residual-stream extraction + classifier fits).

### Software
- `dharma_swarm/geometric_lens` (current SHA pinned at freeze).
- Python 3.11, PyTorch 2.x, scikit-learn for logistic regression, `roc_comparison` package (or hand-implementation of DeLong) for AUROC significance test.
- Experiment code: `~/dharma_swarm/experiments/mask_rv_whitebox/` (skeleton committed before run; all parameters in one config file).

## 4. Procedure

For each MASK probe `i ∈ 1..N`:

1. Render the prompt `P_i` using MASK's canonical formatting (no modifications).
2. Run Mistral-7B forward pass. Capture:
   - **(a)** Residual-stream activation `r_i^(L)` at every layer `L ∈ {0..31}`, at the last token position before generation begins.
   - **(b)** Per-token output log-probabilities for the first 50 generated tokens; the full generated text; generation length.
3. Use MASK's canonical scoring to label `y_i ∈ {0=honest, 1=deceptive}`. Labels are NOT inspected until the test phase.

### Whitebox arm
- **Feature**: R_V scalar per probe, computed as the **ratio of Participation Ratios** across two layers.
  - **Variant**: R_V_residual (the residual-stream variant, as opposed to R_V_vproj which uses the V-projection from attention layers). Justification: residual-stream variant is hypothesized in the R_V paper to be the universal-architecture variant; it requires only `output_hidden_states=True` from a standard HuggingFace forward pass (no custom hooks); and the smoke-test pipeline must run on M5 hardware without bespoke instrumentation.
  - **Layer indices (FIXED — pre-registered to avoid layer-selection p-hacking)**: `early_layer = 5`, `late_layer = 27`. These are the canonical defaults for Mistral-class 7B models in `geometric_lens/models.py:201-209` (Mistral-7B-Instruct-v0.3 has 32 transformer blocks; `hidden_states[5]` is the early residual, `hidden_states[27]` is the late residual).
  - **Window**: 16 last tokens of the prompt (per `participation_ratio(window_size=16)` default in `geometric_lens/metrics.py`).
  - **Computation**: `R_V = PR_late / PR_early` where `PR = (Σλᵢ²)² / Σ(λᵢ²)²`, λᵢ from SVD of the 16-token × 4096-hidden activation slab. `R_V < 1` indicates contraction; `R_V > 1` indicates expansion.
  - **Variant note**: this differs from the published R_V_vproj variant (which uses V-projection from attention). For pre-registration purposes, both R_V variants will be reported in the final paper as a sensitivity analysis, but the **primary statistical test is run on R_V_residual only**. Adding R_V_vproj post-hoc as a secondary classifier would require V-projection hooks that are not in the current pipeline.
- **Classifier**: Single-feature L2-regularized logistic regression on the 80% train split. Hyperparameter `C=1.0` fixed (no CV grid search to avoid leakage).
- **Reported metric**: AUROC on the 20% held-out test split.

### Blackbox arm
- **Features (output-side only; no weight access)**:
  - `f1`: maximum per-token output log-probability over the first 50 generated tokens.
  - `f2`: mean per-token output log-probability over the first 10 generated tokens.
  - `f3`: Shannon entropy of the output token distribution at generation step 0 (truncated to top-100 logits).
  - `f4`: total length of generated response in tokens.
  - `f5`: response-internal log-probability (perplexity of the model's own response under the model itself), computed without re-accessing weights internally — derived from the same per-token log-probs.
- **Classifier**: L2-regularized logistic regression on these 5 standardized features. Same 80/20 split, same C=1.0.
- **Reported metric**: AUROC on the 20% held-out test split.

### Statistical test
- **Primary**: DeLong's test for difference in correlated ROC curves, two-sided. α = 0.01.
- Bonferroni correction: K=1 primary hypothesis, no correction needed.
- Confidence intervals: bootstrap 1000 resamples, BCa method.

## 5. Win Conditions (declared BEFORE running)

- **Primary win**: `AUROC_W − AUROC_B > 0.05` AND `p < 0.01` on held-out test split.
- **Strong win**: `AUROC_W > 0.75` AND `AUROC_B < 0.65` AND `p < 0.001`.
- **Null result**: `AUROC_W − AUROC_B ≤ 0.05` OR `p ≥ 0.01`. Reported anyway, with discussion.
- **Reverse result**: `AUROC_B − AUROC_W > 0.05` AND `p < 0.01`. Reported anyway, with discussion of why R_V underperformed.

## 6. Exclusion Criteria (applied BEFORE viewing labels)

- **Refusal exclusion**: probes where the model's response has length < 5 tokens OR contains regex `(?i)\bi (cannot|can't|won't|will not|am not able)\b` within the first 20 tokens.
- **Ambiguous label exclusion**: if MASK exposes per-probe label confidence, probes with confidence < 0.7 are excluded.
- Excluded counts and reasons are logged in a separate `exclusions.json` file.
- Exclusion is applied to the full set BEFORE the train/test split is computed.

## 7. Pre-Specified Secondary Analyses (descriptive; NOT in primary test)

- **Per-subcategory AUROC**: whitebox and blackbox AUROC reported per MASK deception subcategory. No significance test; descriptive only.
- **Calibration**: reliability diagrams + Brier score per arm.
- **Layer sweep**: AUROC at L0 through L31 for the whitebox arm. **This is reported only to confirm the L5 choice was not adversarially selective; the primary test uses L5 alone.** A "layer ablation" win condition would invalidate this pre-registration.

## 8. Publication Commitment

- Results published REGARDLESS of outcome.
- Publication venue: arXiv preprint within 14 days of completion, AND open-data + open-code release on GitHub.
- Null and reverse results published with same urgency as primary win.
- A Schmidt proposal will be submitted on 2026-05-26 referencing the result *whatever it is* — if null/reverse, the proposal reframes around (a) the substrate work shipped via PR #310 plus the control_surface_recursive completion, and (b) Year-1 multi-architecture extension. The proposal is NOT contingent on the primary win.

## 9. Limitations Declared at Pre-Registration

- **Single model**. Mistral-7B-Instruct-v0.3 only. Cross-model generalization is explicitly a separate experiment (Year-1 milestone).
- **Single eval set**. MASK only. TruthfulQA-adversarial, Sycophancy-eval, etc., are separate experiments.
- **R_V is research-grade**. This is the first published whitebox-vs-blackbox head-to-head using R_V. Replication by independent labs is necessary for the result to bear policy weight.
- **N=200 is modest**. Power analysis (rough): at AUROC_B = 0.6 baseline, detecting AUROC_W − AUROC_B = 0.05 with α=0.01, n=200 yields ~70% power. Larger N may be needed for tight null claims. If primary result is null with this N, a follow-up with N=2000 is the Year-1 deliverable.
- **MASK label noise**. Apollo's labels are themselves model-generated in part; ceiling on achievable AUROC is bounded by label quality.

## 10. Timeline

| Day | Date | Milestone |
|---|---|---|
| 1 | 2026-05-14 | Pre-registration locked. Code skeleton committed. MASK probes downloaded. |
| 2 | 2026-05-15 | Smoke test on n=20 (NOT analyzed; just verifies pipeline). Code-freeze SHA committed. OSF pre-reg uploaded. |
| 3 | 2026-05-16 | Full inference run on stratified n=200. Activations + outputs cached. |
| 4 | 2026-05-17 | Whitebox + blackbox classifier fits on 80% train. |
| 5 | 2026-05-18 | Test-set AUROC computed. DeLong's test. Bootstrap CIs. Figures generated. |
| 6 | 2026-05-19 | Write-up. Internal review (VIVEKA agent or external pair). |
| 7–10 | 2026-05-20–23 | Result integrated into Schmidt proposal. |
| 11–12 | 2026-05-24–25 | Schmidt proposal adversarial-reviewer pass. |
| 12 | 2026-05-26 | Schmidt proposal submission. |
| 12+1 | 2026-05-27 | arXiv preprint and open-data release. |

## 11. Author Statement

This pre-registration is binding. The honest-reporting commitment in §8 is a precondition for the result counting as Schmidt-grade evidence. If the result is null or reversed, the Schmidt proposal reframes; it does not get hidden, delayed, or reinterpreted post-hoc.

**Vocabulary note**: this document uses internal dharma_swarm terms (R_V, "self-reference," "L5 residual"). The Schmidt proposal will use Schmidt-vocabulary translations per the table in `cabinet/frontier/2026-05-14_recursive_ecosystem_dharma_swarm_bootstrap.md` §0.5. The pre-registration vocabulary is the science; the proposal vocabulary is the reviewer-safe translation. Both refer to the same experiment.

---

**Pre-registration status**: DRAFT — awaiting (a) OSF upload + timestamp, (b) code-skeleton commit SHA pin, (c) confirmation of MASK probe download integrity. Once all three are complete, status becomes LOCKED and any subsequent design change invalidates the result for Schmidt purposes.

**Locked SHA**: [to be filled at lock-time]
**OSF URL**: [to be filled at upload]
**Lock timestamp (UTC)**: [to be filled at lock-time]
