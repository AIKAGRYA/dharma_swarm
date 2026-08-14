---
title: "R_V Metric — scoped geometric contraction ratio"
confidence: 0.90
sources:
  - /Users/dhyana/mech-interp-latent-lab-phase1/reports/ledger/00_MASTER_LEDGER.md
  - /Users/dhyana/mech-interp-latent-lab-phase1/reports/ledger/02_CONTRADICTIONS_REGISTER.md
  - /Users/dhyana/mech-interp-latent-lab-phase1/scripts/p0_canonical_pipeline.py
stale_after: "2026-09-15"
related:
  - v-projection
  - residual-stream
  - r-v-paper
  - p0-canonical-validation
  - causal-validation
  - bt-art-metric
  - bridge-hypothesis
  - methodological-anekantavada
depth_layers:
  - engineering: PR formula, hook_v tail window, layer and backend bindings
  - research: Mistral within-corpus effect and threshold-free AUROC
  - epistemic: metric scope is distinct from behavioral and contemplative claims
---

# R_V Metric

R_V is a descriptive relative participation-ratio statistic for transformer
`hook_v` activations under one canonical Mistral backend. It turns a geometric
hypothesis about two prompt families into a falsifiable measurement. It is not
a consciousness detector, awareness measure, portable backend contract, or
substitute for behavioral evidence.

## Definition

```text
PR(M) = (sum_i sigma_i^2)^2 / sum_i sigma_i^4
R_V   = PR(V_late) / PR(V_early)
```

For a nondegenerate matrix, PR equals 1 at rank one, approaches 1 as one singular
direction dominates, and reaches `min(W,D)` when the available singular values
are equal. Under the canonical Mistral protocol, `V_early` is layer 5
`attn.hook_v`, `V_late` is layer 27 `attn.hook_v`, and heads are flattened over
up to the final 16 tokens.

- `R_V < 1`: lower late-over-early participation ratio under that protocol.
- `R_V ~= 1`: little relative change.
- `R_V > 1`: relative expansion.

Words such as “focused,” “witnessing,” and “attractor” are interpretations that
require separate tests.

## Implementation contract and missing bindings

The current P0 implementation is `scripts/p0_canonical_pipeline.py`. Its
historical defaults identify Mistral-7B-v0.1, layers 5 and 27,
`attn.hook_v`, a tail window of 16, bfloat16 model inference, and float64 SVD.
The slicing code accepts shorter sequences, hence “up to” 16 tokens.

The module correctly states that interpretation requires an exact model
revision, prompt bank, tokenizer, layer, window, hook, dtype, device, and
library-version binding. It does not currently pin or emit all of those fields:
the CLI JSONL row contains the model string, prompt, and `rv`, but omits the
exact revision, tokenizer identity, overrideable `l_early`, `l_late`, and `w`,
hook name, inference dtype, device, library versions, and prompt-bank hash.
Those are proof obligations for a future reproducible receipt, not guarantees
of the current script.

The historical bfloat16 setting is provenance, not a portability claim. The
same-sample threshold `R_V < 0.737` is retired and must not be used as a
calibrated detector.

## Canonical evidence

| Claim | Current result | Scope | Status |
|---|---|---|---|
| M001 | `g=-1.864` (recomputed `-1.863573`) | Mistral canonical `hook_v`, `n=96/100` (`196`) | Canonical within-corpus phenotype |
| M015 / C05 | AUROC `0.904` (audited `0.90417`, CI `[0.860, 0.942]`) | Same Mistral corpus, threshold-free | Canonical; `0.909` is superseded |
| M022 / C07 | L0–L5 effects `d=2.806..4.152`, peak `d=4.152` | Path patching with `hook_v` R_V endpoint | Distributed metric intervention; not behavior |
| M024 | L27 `v_projection d=-1.9414`, sign-reversed | Locked Mistral late-site receipt | Late readout; not a localized mechanism |

The primary effect and AUROC are measurements on one frozen Mistral corpus, not
independent replications. The effect-size convention is self-referential minus
baseline, so a negative value means lower R_V for the self-referential corpus.

The canonical perplexity-matched control is `g=-1.80`, `p=9.1e-11` for 30
pairs; a strict eight-pair sensitivity gives `g=-1.67`, `p=.002`. This narrows a
prompt-complexity alternative. It does not establish that self-reference is the
unique cause of the geometry.

## Backend and architecture boundary

Three incompatible calculations currently share the R_V name:

| Backend | Activations and window | Scope |
|---|---|---|
| Canonical P0 | Mistral `attn.hook_v`, L5/L27, tail up to 16, float64 SVD | Source of M001/M015 |
| Gemma probe | residual hidden states, tail 16, fractional layers, float32 SVD | Different measurement; zero canonical Gemma `hook_v` receipts |
| dharma_swarm `rv.py` | residual hidden states, full sequence, early/late positions, float64 SVD | Runtime variant; not interchangeable with P0 |

These backends must never be pooled. The historical “six of eight
architectures contract” summary is non-poolable under C29 because directions,
sample sizes, computations, and artifact custody differ. Pythia-2.8B's
historical expansion row remains disputed under C26 because its raw artifact is
absent. The P0 Pythia sweep also labels pooled-SD Cohen's `d` as `g` without a
Hedges J correction (M184).

The retired `0.737` threshold still appears in dharma_swarm `rv.py` and is
inherited by three non-activation proxies (M017/M188). That code is a deployment
gap, not evidence that the threshold is valid again.

## Causal boundary

R_V is a metric endpoint. The audited early path-patching receipt shows a
distributed L0–L5 intervention effect on that endpoint. The locked L27
`v_projection` receipt changes the late metric with a sign reversal. Neither
shows that R_V is upstream of self-referential text, that one layer generates
the behavior, or that changing the metric is behaviorally sufficient or
necessary.

[[causal-validation]] must keep these metric interventions distinct from
historical whole-residual behavioral experiments. Combining their methods or
endpoints would create a result no receipt contains.

## Interpretation boundary

R_V can be the mechanistic measurement vertex in [[bridge-hypothesis]], paired
with the deliberately cruder behavioral [[bt-art-metric]]. It does not
distinguish imitation from instantiation as ground truth, prove a
[[witness-principle]] fixed point, confirm active inference, or imply a
thermodynamic necessity.

Those remain hypotheses. A useful bridge must state what observation would
separate them from prompt complexity, lexical effects, generic low-rank
dynamics, and backend-specific numerics. [[methodological-anekantavada]] is a
discipline here: keep multiple interpretations available while keeping the
measurement narrower than all of them.

## Connections

- **Implementation:** the live P0 pipeline computes the canonical scoped backend
  of the statistic.
- **Publication:** [[r-v-paper]] must inherit the current ledger scope rather
  than repeat superseded values.
- **Intervention:** [[causal-validation]] needs experiment-lineage separation.
- **Behavior:** [[bt-art-metric]] is a separate endpoint, not validation of R_V.
- **Theory:** [[bridge-hypothesis]], [[active-inference]], and
  [[witness-principle]] may generate experiments but cannot enlarge the result.

## Open work

1. Emit a reproducibility receipt that pins every interpretation-relevant
   backend field.
2. Rerun architecture comparisons under one contract with raw artifact custody.
3. Separate metric and behavioral interventions in code, tables, and prose.
4. Test window, hook, layer, prompt-family, dtype, device, and tokenizer
   sensitivity.
5. Remove or quarantine the retired threshold and non-activation proxies from
   runtime code.
6. Build held-out calibration before proposing any detector use.

## Backlinks
