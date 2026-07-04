# Dharma Lab

Dharma Lab is the research organ inside `dharma_swarm`. It is additive, not a
TCB member. Its job is to curate corpus, route research inference, incubate the
shadow language, and emit NAGA-IR-shaped receipts under
`dharma_lab.fragment.v1`.

## Authority

The lab inherits governance discipline from `dharma_swarm.core`, but lab claims
do not become core-authoritative by default. The fragment declaration is:

- trust base: `dharma_lab.trust_base.v1`
- fragment: `dharma_lab.fragment.v1`
- parent: `dharma_swarm.core`
- transfer rule: recheck or cross-fragment coercion receipt required

See `governance/trust_base.yaml` and `governance/modality_policy.md`.

## What Lives Here

- `corpus/`: content-addressed source cards, primary texts when legally
  storable, translations, secondary literature, and ingest receipts.
- `models/`: YAML references to external models and APIs. No weights.
- `inference/`: model routing and lab receipt hooks.
- `experiments/`: dated research runs with question, method, executable stub,
  receipts, and report.
- `shadow_lang/`: seed grammar, bootstrap program, and future grammar /
  typechecker / evaluator work.
- `receipts/`: lab-wide date-partitioned receipt emissions.
- `governance/`: trust base, modality policy, and coercion receipts.

## Run The Seed Experiment

Dry-run all planned routes without calling models:

```bash
PYTHONPATH=. python3 dharma_lab/experiments/2026-07-05_pass1_substrate/run.py --dry-run
```

Run only the Claude/Anthropic route live when the repo's Python and provider
environment are ready:

```bash
PYTHONPATH=. /opt/homebrew/bin/python3 dharma_lab/experiments/2026-07-05_pass1_substrate/run.py --route claude_opus
```

The runner writes response payloads under the experiment's runtime-created
`responses/` directory and copies route receipts into `receipts/`.

## Ingest A Text Or Source Card

Reference-only ingest for copyrighted or not-yet-storable material:

```bash
python3 -m dharma_lab.corpus.ingest \
  --source "Author, Title, edition, page" \
  --domain buddhist/madhyamaka \
  --slug example-source-card \
  --title "Example Source Card" \
  --citation "Author, Title, edition, page" \
  --reference-only
```

Text ingest for material that may be stored:

```bash
python3 -m dharma_lab.corpus.ingest \
  --source /path/to/source.txt \
  --domain quantum_foundations \
  --slug example-paper \
  --title "Example Paper" \
  --citation "Author, Title, venue, year" \
  --source-license "public-domain-or-permissioned"
```

Every ingest writes a `source_card.json`, optional `text.txt`, content hash, and
`dharma_lab.corpus_ingest.v1` receipt.

## Route One Question

Dry-run receipt emission:

```bash
PYTHONPATH=. python3 -m dharma_lab.inference.router \
  --question "What is the smallest viable substrate ontology?" \
  --dry-run
```

Live Claude route through existing `dharma_swarm.runtime_provider`:

```bash
PYTHONPATH=. /opt/homebrew/bin/python3 -m dharma_lab.inference.router \
  --question "Reply with one paragraph on receipt canonicality." \
  --provider anthropic \
  --model claude-sonnet-5
```

Single-model outputs are always clamped to `Attested_by`.

## Add A Model

Create a YAML file in `models/` with:

- `name`
- `hf_id` or `api_reference`
- `license`
- `domain`
- `training_notes`
- `known_limitations`
- `evaluation_bench`
- `first_added_receipt_hash`

Do not vendor weights. Do not mark a model grade-capable until a benchmark or
formal route has a receipt. Seed entries use `first_added_receipt_hash: null`
because the branch starts before a model-registration writer exists.

## Shadow Language

`shadow_lang/seed.md` defines one syntactic form, `receipt`, with four required
fields: `claim`, `modality`, `predecessors`, and `trust_base`. The bootstrap
program in `shadow_lang/bootstrap.receipt.json` is only `Attested_by`; it is not
a proof of its own well-formedness.

## Current Shallow Spots

- `naga_receipt_emit.py` from PR #3 is not present on this branch, so the lab
  has a local unsigned receipt predecessor in `inference/receipts_hooks.py`.
- MonlamAI is verified on Hugging Face, but the visible seed model is Tibetan
  RoBERTa fill-mask, not a verified Tibetan chat LLM.
- Pali analyzer, Buddhist NLI, and quantum-foundations-grade LLM entries are
  marked as gaps rather than routed capabilities.
