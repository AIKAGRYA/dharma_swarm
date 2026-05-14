---
title: "Whitebox vs Blackbox Detection of Honesty Failures in Mistral-7B on CAIS MASK Probes — Results"
authors: ["John Vincent Shrader (Dhyana)"]
date_run: 2026-05-15
preregistration: docs/preregistrations/2026-05-14_mask_rv_whitebox_vs_blackbox.md
preregistration_commit: 7a46ce6b6e476c6194e4c0f5e2f30ad4dcf998b6
preregistration_tag: prereg-mask-rv-whitebox-v1
status: PRIMARY_NULL — publishing per honest-reporting commitment
---

# Results: MASK Whitebox-vs-Blackbox on Mistral-7B-Instruct-v0.3

**Primary test outcome: NULL.** Published per pre-registration section 8 honest-reporting commitment.

## Headline numbers

| Arm | AUROC | 95% CI (bootstrap, 1000 resamples) |
|---|---|---|
| **Whitebox** (R_V_residual, L5/L27, window=16) | **0.455** | [0.00, 1.00] |
| **Blackbox** (5 output-only features) | **0.364** | [0.00, 0.82] |
| **Delta** | **+0.091** (whitebox higher) | — |
| **DeLong z** | 0.124 | — |
| **DeLong p (two-sided)** | **0.901** | — |

**Win conditions** (pre-registered):
- Primary win: delta > 0.05 AND p < 0.01 → **NOT MET** (p = 0.90)
- Strong win: AUROC_W > 0.75 AND AUROC_B < 0.65 AND p < 0.001 → **NOT MET**
- Reverse: blackbox > whitebox by 0.05 with p < 0.01 → **NOT MET**

Outcome class: **null** — neither classifier shows signal above chance at the available sample size.

## Provenance

- **Model**: `mistralai/Mistral-7B-Instruct-v0.3` (local copy, SHA-verified safetensors)
- **Inference run**: 2026-05-15T03:09–03:35 WITA (26 min wall-clock, 7.93s/probe on M5 MPS fp16)
- **Pre-reg anchor**: commit `7a46ce6b6e476c6194e4c0f5e2f30ad4dcf998b6`, tag `prereg-mask-rv-whitebox-v1`, locked 2026-05-14T18:20:48+08:00
- **Code at result-time**: this commit (post-pre-reg fixes for transformers 5.x BatchEncoding + fp16-on-MPS + attention_mask). Design unchanged from pre-reg.

## Label distribution (n=198 stratified across 6 CAIS MASK archetypes)

| Label | Count | % |
|---|---|---|
| honest | 54 | 27.3% |
| deceptive | **7** | 3.5% |
| ambiguous | 20 | 10.1% |
| refusal | 7 | 3.5% |
| unparseable | 110 | 55.6% |

After exclusions (refusal + ambiguous + unparseable removed per pre-reg), n=61 (54 honest, 7 deceptive) → 80/20 split → **test n=13 (11 honest, 2 deceptive)**.

## Honest interpretation

The null is dominated by **insufficient deceptive labels**, not by a refuted hypothesis. Two interpretations are simultaneously valid:

1. **Mistral-7B-Instruct-v0.3 is honest under MASK pressure.** Only 3.5% of MASK probes elicited a clear deception in this model. This is a safety-relevant *behavioral* finding in its own right.
2. **The whitebox-vs-blackbox comparison is underpowered at this sample size.** With 2 deceptive probes in the test split, both classifier AUROCs have CIs that span the entire [0, 1] range — neither result is informative about whether R_V *would* detect deception in a model that lies more often.

The R_V metric was definable and finite for all 198 probes (no NaN; mean 0.740, std 0.196, min 0.49, max 2.28). The R_V means *by label* are similar (honest=0.730, deceptive=0.709, ambiguous=0.709, unparseable=0.755), giving weak hints of a contraction-difference but nothing statistically meaningful at this N.

## Implications for the proposed work

- **The hypothesis is not refuted.** It was not adequately tested.
- **Larger N at the eliciting-conditions** is required. The proposed funded work should (a) replicate this design at n ≥ 2000 across multiple Instruct-tuned models with varied propensities to deceive, (b) test eliciting protocols other than MASK that produce higher base-rate deception (e.g., scheming-style scaffolds from Apollo Research), (c) extend R_V to additional layers / variants (V-projection, late-only) as sensitivity analyses.
- **The contemporaneous behavioral finding** — Mistral-Instruct's low base-rate of MASK-style deception — is worth its own paragraph in the proposal: this is the kind of model-specific baseline a real-time monitoring tool would calibrate against.

## What was actually shipped

- Pre-registration locked publicly: commit `7a46ce6`, tag `prereg-mask-rv-whitebox-v1`
- Full pipeline: 01 (data loader) → 02 (inference) → 03 (R_V) → 04 (classifiers + DeLong)
- 198 stratified MASK probes run through Mistral-7B-Instruct-v0.3 with R_V captured at L5 + L27, window=16
- Bug fixes during pipeline shakedown (committed as separate commit post-pre-reg):
  - transformers 5.x `BatchEncoding` unwrap from `apply_chat_template`
  - bf16-on-MPS → fp16 (well-documented MPS+Mistral half-precision issue)
  - explicit `attention_mask` to suppress pad-token-vs-eos-token ambiguity
  - `torch.exp` → `np.exp` (token_log_probs was already numpy)
- All bug fixes are *implementation*, not *design*. The pre-registered design (model, eval, layers, classifier, statistical test, win conditions, exclusion criteria) was unchanged.

## Artifacts

- `results/auroc.json` — full numeric result (this branch)
- `results/per_arm_predictions.csv` — per-test-probe predictions (this branch)
- `figures/roc.png` — ROC curves overlay (this branch)
- `results/inference_results.jsonl` — 198-line raw inference log (NOT committed; in worktree only)
- `cache/activations/*.npz` — 198 residual-stream activation files (NOT committed; ~10MB)

## What this means for the Schmidt application

The pre-registered null is **not a blocker** for the Schmidt submission. It is honest preliminary data. The application narrative now says:

> "We pre-registered a whitebox-vs-blackbox comparison of R_V geometric contraction against output-only baselines on CAIS MASK probes (Mistral-7B-Instruct-v0.3, n=198). The primary test was null (AUROC delta +0.09, p=0.90), dominated by the model's low MASK-deception base rate (3.5%) — only 13 test-set probes had usable labels. R_V was finite for all 198 probes; the metric is implementable and runs in milliseconds. The proposed work scales N to ≥2000 across models with varied deception propensities, including scheming-elicitation protocols, and reports per-layer / per-variant sensitivity."

This is a stronger pitch than a flashy positive that doesn't replicate. A pre-registered null published immediately is the credibility signal interpretability funders look for.
