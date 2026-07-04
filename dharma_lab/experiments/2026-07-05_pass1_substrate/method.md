# Method

## Objective

Run Pass 1 substrate research through the lab router without performing the
research in this seed commit. The experiment records model responses and
receipts so later synthesis can compare independent arrivals.

## Planned Routes

| Route | Provider | Model/reference | Status |
|---|---|---|---|
| `claude_opus` | Anthropic via `dharma_swarm.runtime_provider` | Claude Opus family; seed registry currently records `claude-opus-4-8` | live-capable |
| `gpt5` | OpenAI via `dharma_swarm.runtime_provider` | GPT-5 family; seed registry currently records official `gpt-5.5` / `gpt-5.4` docs | planned |
| `gemini_3_pro` | Google AI via `dharma_swarm.runtime_provider` | Gemini 3 Pro family; seed registry currently records Gemini 3.1 Pro preview and Gemini 3.5 Flash docs | planned |
| `monlam_tibetan` | Hugging Face reference | MonlamAI Tibetan reference; current verified HF item is RoBERTa fill-mask, not chat LLM | corpus/model gap |

## Corpus Search

The first run should search these corpus domains when populated:

- `dharma_lab/corpus/buddhist/`
- `dharma_lab/corpus/jain/`
- `dharma_lab/corpus/quantum_foundations/`

At seed time these directories are empty; the run script records the empty
state rather than pretending retrieval occurred.

## Modality Rules

Single-model outputs are `Attested_by`. Cross-model agreement can be promoted
to `Tested_by` only after a separate agreement predicate compares response
hashes, claims, and disagreements. Nothing in this experiment is `Proven_by`
unless a proof checker verifies a formal artifact.

## Reproducibility

Each run writes:

- one response JSON per executed route under runtime-created `responses/`;
- one lab-wide `dharma_lab.inference.v1` receipt through the router;
- a copy of each route receipt into this experiment's `receipts/` directory.

Future reruns should compare question hash, route config hash, response hash,
and receipt hash. Drift is expected for live frontier calls and must be
reported explicitly in `report.md`.
