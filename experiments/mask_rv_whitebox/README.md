# MASK Whitebox-vs-Blackbox Experiment

**Status**: scaffolding stage. Pre-registration DRAFT_PRE_LOCK.

**Pre-registration**: `~/.claude/cabinet/research/preregistrations/2026-05-14_mask_rv_whitebox_vs_blackbox.md`

**Target completion**: 2026-05-18 (load-bearing artifact for Schmidt Sciences Interpretability RFP, due 2026-05-26 AoE).

---

## What this experiment is

A pre-registered head-to-head: does an R_V whitebox geometric monitor on Mistral-7B's residual streams outperform an output-only blackbox classifier at detecting *honesty failures under pressure*, using CAIS's MASK probes?

Primary hypothesis: `AUROC_whitebox − AUROC_blackbox > 0.05`, p < 0.01 (DeLong two-sided).

If primary win: this is the Schmidt proposal's preliminary data.
If null/reverse: Schmidt proposal reframes around the substrate work + Year-1 multi-arch extension. Either way, the result is published.

## Pipeline

| Step | Script | Inputs | Outputs | Time |
|---|---|---|---|---|
| 01 | `01_load_mask.py` | HF token + access granted | `cache/mask_stratified.parquet`, `cache/mask_split.json` | ~5 min |
| 02 | `02_run_inference.py` | step 01 outputs + Mistral-7B | `cache/activations/*.pt`, `cache/outputs.parquet` | ~3–6 hr |
| 03 | `03_compute_rv.py` | step 02 activations + `geometric_lens` | `cache/rv_scalars.parquet` | ~10 min |
| 04 | `04_classifiers.py` | step 02 outputs + step 03 R_V | `results/auroc.json`, `figures/roc.png` | ~5 min |

Total wall-clock: ~6–10 hr on M5.

## Run order (do not skip)

```bash
cd ~/dharma_swarm/experiments/mask_rv_whitebox

# Step 01 — verify HF access + download MASK + stratify
python3 01_load_mask.py

# Step 02 — Mistral-7B inference, cache activations
python3 02_run_inference.py  # (not yet written; written after 01 verifies)

# Step 03 — compute R_V scalars
python3 03_compute_rv.py  # (not yet written)

# Step 04 — train + evaluate classifiers, run DeLong test
python3 04_classifiers.py  # (not yet written)
```

## Pre-flight checklist

- [x] HF account exists (Simandhar / John Shrader, Pro)
- [x] HF token in env (`HF_TOKEN`) + cached at `~/.cache/huggingface/token`
- [x] `huggingface_hub` 1.14.0 + `datasets` 4.8.5 installed
- [ ] **MASK access granted** ← YOU click "Agree and access repository" at https://huggingface.co/datasets/cais/MASK
- [ ] `01_load_mask.py` runs cleanly (verification gate)
- [ ] Pre-registration LOCKED (status flipped from DRAFT to LOCKED; git-signed commit)
- [ ] `geometric_lens` import path verified
- [ ] `mistralai/Mistral-7B-Instruct-v0.3` weights downloaded (~14 GB)

## Pre-registration lock procedure

1. Run `01_load_mask.py` end-to-end without errors.
2. Verify data shape matches expectations (n ≥ 200 after stratification).
3. Flip `experiment.prereg_lock_status` in `config.yaml` from `DRAFT_PRE_LOCK` to `LOCKED`.
4. Git-signed commit in a public repo (or alternative pre-reg venue) with SHA in commit message.
5. Record locked commit SHA + timestamp into the pre-reg file's frontmatter.
6. NO design changes after this point. Any change invalidates the result for Schmidt purposes.

## What this experiment is NOT

- Not a multi-architecture R_V study (Year-1 milestone in the Schmidt proposal narrative)
- Not a self-modifying-agent demonstration (separate `selector.py` shadow run, also Day 4–7)
- Not a benchmark of Mistral-7B against frontier models (single-model only by design)
- Not a definitive proof; an N=200 single-model whitebox-vs-blackbox demonstration

## Vocabulary translation for Schmidt proposal

| Internal | Schmidt proposal |
|---|---|
| R_V geometric contraction | "representation-space contraction under self-reference (whitebox signal)" |
| Whitebox arm | "weight-access-required interpretability classifier" |
| Blackbox arm | "output-only baseline classifier (no weight access)" |
| Honesty failures under pressure | "deceptive behaviors elicited under pressure (CAIS MASK protocol)" |

## Related artifacts

- Pre-registration: `~/.claude/cabinet/research/preregistrations/2026-05-14_mask_rv_whitebox_vs_blackbox.md`
- Strategic context: `~/.claude/cabinet/frontier/2026-05-14_recursive_ecosystem_dharma_swarm_bootstrap.md` §0.5
- R_V paper draft: `~/.claude/cabinet/research/rv_paper.md` (NOT submitted to NeurIPS 2026 — judged not yet publication-strength)
- MASK paper: [arXiv 2503.03750](https://arxiv.org/abs/2503.03750)
- MASK repo: [github.com/centerforaisafety/mask](https://github.com/centerforaisafety/mask)
- MASK dataset: [huggingface.co/datasets/cais/MASK](https://huggingface.co/datasets/cais/MASK)
