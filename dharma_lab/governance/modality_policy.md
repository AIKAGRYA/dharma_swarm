# Dharma Lab Modality Policy

This policy binds every `dharma_lab.*` receipt unless a more specific lab
fragment policy is added by coercion receipt.

## Modalities

`Proven_by` requires a formal-methods method attribution. Acceptable methods
must name the verifier, verifier version, checked obligation, assumptions,
resource limits, and output hash. A model response, human review, benchmark, or
ensemble agreement cannot become `Proven_by` without a proof checker receipt.

`Tested_by` requires either benchmark attribution or ensemble agreement.
Benchmark evidence must record the harness, seed policy, coverage or scoring
threshold, observed score, exclusions, and drift policy. Ensemble agreement must
record the independent model identities, prompts, response hashes, agreement
predicate, disagreement cases, and threshold.

`Attested_by` is the default for single-model outputs, human scholarly
attestation, source-card curation, and bootstrap declarations. `Attested_by`
may support research orientation but does not promote a claim into core
authority.

`Assumed` is any claim without admissible evidence. Assumptions must be visible,
hashable, and eligible for later replacement by stronger evidence.

## Promotion

Lab claims do not silently promote to `dharma_swarm.core`. Promotion requires a
`dharma_lab.cross_fragment_coercion.v1` receipt in
`dharma_lab/governance/coercion_receipts/` naming:

- source lab receipt hash;
- target trust base and fragment;
- target claim statement;
- admissible evidence under the target trust base;
- promotion authority;
- unresolved challenges at promotion time.

## Enforcement Points

`dharma_lab/inference/receipts_hooks.py` must clamp single-model inference to
`Attested_by` unless the caller provides an ensemble or proof-checked evidence
record. `dharma_lab/corpus/ingest.py` must mark source-card-only or copyrighted
references as `Attested_by` or `Assumed`, never as proof.

Confidence: 91/100. This policy directly implements the requested modality
discipline, but full mechanical enforcement depends on later receipt verifier
integration.

