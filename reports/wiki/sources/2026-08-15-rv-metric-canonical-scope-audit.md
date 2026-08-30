# R_V metric canonical-scope audit

Observed: 2026-08-15T01:40:00+09:00

Canonical sources:

- `/Users/dhyana/mech-interp-latent-lab-phase1/reports/ledger/00_MASTER_LEDGER.md`
  (`sha256:d7839e8fc70a65ed864b3b1b97c0a1aeb65fcb16150efc92f852f9cc31bf73bc`)
- `/Users/dhyana/mech-interp-latent-lab-phase1/reports/ledger/02_CONTRADICTIONS_REGISTER.md`
  (`sha256:4dda2cd62ff32ec946bd76f83719fb0f3cf06acf07983488d5b053a643f16daa`)
- `/Users/dhyana/mech-interp-latent-lab-phase1/scripts/p0_canonical_pipeline.py`
  (`sha256:737a48ce944a64b162253fa6df8200f763663e7241ba42df2a7c4d57185e6c07`)

## Audited claims

- **RV1 / M001 — primary effect.** The current primary R_V result is
  `g=-1.864` (recomputed `-1.863573`) for Mistral-7B-v0.1, canonical `hook_v`,
  tail-16 L5/L27, `n=96/100` (`196` total). It is a within-corpus phenotype,
  not an independent replication and not a cross-architecture result.
- **RV2 / M015 / C05 — detector scope.** The current threshold-free AUROC is
  `0.904` (audited `0.90417`, CI `[0.860, 0.942]`) on the same Mistral
  canonical `hook_v` corpus, `n=196`. The old `0.909` is superseded (M016).
- **RV3 / M022 / C07 — early intervention scope.** Audited path patching on
  the R_V metric has a distributed L0-L5 effect, peaking at Cohen `d=4.152`.
  The endpoint is `hook_v` R_V. It does not license a localized L5 origin or a
  behavioral endpoint.
- **RV4 / M024 — late intervention scope.** L27 `v_projection` patching has a
  sign-reversed `d=-1.9414` effect on the metric. L27 is a late readout under
  this receipt, not a demonstrated behavioral mechanism.
- **RV5 / M092 / M093 / C26 / C29 — architecture scope.** The historic
  "six of eight" tally is non-poolable because directions, sample sizes, and
  artifact custody differ. Pythia-2.8B's `g=+1.64` row remains disputed because
  its raw artifact is absent. Architecture rows must be reported separately;
  neither a universal contraction nor a pooled architecture rate is licensed.
- **RV6 — interpretation boundary.** The ledgers establish a scoped geometric
  measurement and metric interventions. They do not establish consciousness,
  a witness fixed point, active-inference identity, a thermodynamic necessity,
  or geometry as ground truth for "instantiation." Those are hypotheses or
  analogies and must be labeled as such with discriminating experiments.
- **RV7 — implementation contract.** The current P0 code defines R_V from
  `attn.hook_v` at Mistral layers 5 and 27 over the final 16 tokens, with
  float64 SVD. Its module contract explicitly says the statistic is not a
  detector, consciousness/awareness measure, or portable backend contract;
  historical bfloat16 is provenance, and the same-sample 0.737 threshold is
  retired. Its CLI JSONL row records the model string, prompt, and `rv`, but not
  exact revision, tokenizer identity, overrideable `l_early`, `l_late`, or `w`,
  hook name, inference dtype, device, library versions, or prompt-bank hash.
- **RV8 / M176–M179 — backend identity.** Three incompatible computations share
  the R_V name: canonical Mistral `hook_v` tail-16, Gemma residual-hidden
  tail-16, and dharma_swarm `rv.py` residual-hidden full-sequence. They must
  never be pooled. There are zero canonical Gemma `hook_v` receipts.
- **RV9 / M017 / M188 — deployment gap.** The retired `0.737` threshold remains
  in dharma_swarm `rv.py` and is inherited by three non-activation proxies. Code
  presence is a known gap, not renewed calibration.
- **RV10 / M184 — estimator label.** The P0 Pythia sweep uses pooled sample SD
  with `ddof=1` but no Hedges J correction. Its field named `g` is Cohen's `d`.
- **RV11 / M060 — perplexity control.** The canonical perplexity-matched Mistral
  control is `g=-1.80`, `p=9.1e-11` for 30 pairs; the strict eight-pair
  sensitivity result is `g=-1.67`, `p=.002`. This narrows a prompt-complexity
  alternative but does not establish that R_V uniquely tracks self-reference.
- **RV12 — definition consequences and sign.** For nondegenerate matrices,
  participation ratio equals 1 at rank one, approaches 1 as one singular
  direction dominates, and reaches `min(W,D)` when the available singular
  values are equal. The reported Mistral effect is self-referential minus
  baseline, so a negative value means lower R_V for the self-referential corpus.

## Article repair rule

Replace complete evidence and interpretation blocks. Do not substitute a new
number into an old universal, causal, diagnostic, medical, contemplative, or
cross-architecture host claim. Preserve the definition and implementation of
the metric where current code still supports them.
