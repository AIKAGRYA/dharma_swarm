# Model Registry

Model YAML files reference external registries and APIs only; no model weights
are vendored here.

Each entry must keep these fields visible:

- `name`
- `hf_id` or `api_reference`
- `license`
- `domain`
- `training_notes`
- `known_limitations`
- `evaluation_bench`
- `first_added_receipt_hash`

Seed entries may use `first_added_receipt_hash: null` when the branch seed
precedes a concrete registration receipt. New additions after the seed should
emit `naga_ir_language_womb.model_registered.v1` and backfill the hash.

Discovery sources used for the seed:

- Hugging Face API search for MonlamAI, Tibetan, Buddhist Sanskrit, Sanskrit
  OCR, Lean4, and quantum physics model references.
- Anthropic model overview: https://platform.claude.com/docs/en/about-claude/models/overview
- OpenAI model overview: https://developers.openai.com/api/docs/models
- Gemini model overview: https://ai.google.dev/gemini-api/docs/models

No entry is a claim of domain-grade reliability. Evaluation remains required
before routing can produce anything stronger than `Attested_by`.
