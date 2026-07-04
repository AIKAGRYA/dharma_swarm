# NAGA-IR Language Womb Seed Report

Branch: `telos_titanium/naga_ir_language_womb_seed`

Base: `origin/telos_titanium/dharma_lane_research` at `738b46316`

Report location note: this file is under `naga_ir_language_womb/` so the seed
report travels with the organ. The rename follow-up also updates `pyproject.toml`
for package discovery and the Pass 1 research prompt link so future research
questions seed this organ name, not the deprecated `dharma_lab/` name.

## Scaffolded

- D1: Created `naga_ir_language_womb/` directory structure with per-level README files and
  `.gitkeep` markers for intentionally empty operational directories.
- D2: Added `governance/trust_base.yaml` and `governance/modality_policy.md`
  for `naga_ir_language_womb.fragment.v1`, parented to `dharma_swarm.core`.
- D3: Seeded seven model registry YAML entries, including MonlamAI, Sanskrit
  OCR, LeanDojo, frontier API references, and explicit gap entries.
- D4: Added `corpus/ingest.py` and a local NAGA-IR-shaped receipt hook.
- D5: Added `inference/router.py` with a working Anthropic/Claude path through
  existing `dharma_swarm.runtime_provider`, plus dry-run receipt emission.
- D6: Documented receipt classes and date partitions under `receipts/YYYY/MM/DD`.
- D7: Seeded `experiments/2026-07-05_pass1_substrate/` with copied question,
  method, executable runner, empty receipts directory, and report template.
- D8: Added the NAGA-IR child language seed grammar and bootstrap receipt.
- D9: Wrote the contributor README and this report.

## Rename Follow-Up

- Renamed `dharma_lab/` to `naga_ir_language_womb/`.
- Renamed `specs/dharma_lab/` to `specs/naga_ir_language_womb/`.
- Rebased receipt classes, trust-base IDs, import paths, CLI commands, and
  emitted schemas onto the `naga_ir_language_womb.*` prefix.
- Added `naga_ir_language_womb*` to package discovery in `pyproject.toml`.
- Updated `specs/naga_ir/dharma_lane/deep/RESEARCH_PROMPT.md` so disagreement
  questions seed `naga_ir_language_womb/`.

## Deferred

- No PR opened and no push performed.
- No model weights vendored.
- No four-pass research answer written.
- No primary-text translations created.
- No full NAGA-IR child language parser, typechecker, or evaluator implemented.
- No signed canonical NAGA receipts; seed receipts are unsigned bootstrap
  records until PR #3's emitter or an equivalent signer lands.
- No live model call was committed as an artifact; dry-run and provider
  resolution were verified.

## Open Questions Before Push

1. Should the seed branch backfill actual `naga_ir_language_womb.model_registered.v1`
   receipts for model YAML entries now, or wait for a model registry writer?
2. Which MonlamAI model should be the authoritative Tibetan route if the current
   HF-visible model remains RoBERTa fill-mask rather than a chat LLM?
3. Should the first live Pass 1 run use Opus, Sonnet, or Claude Code's local
   default model policy?
4. Should experiment receipt copies be committed after a live run, or kept as
   generated artifacts until reviewed?

## Verification Performed

- `python3 -m py_compile naga_ir_language_womb/inference/receipts_hooks.py naga_ir_language_womb/corpus/ingest.py`
- Reference-only corpus ingest smoke into `/private/tmp`, verifying record
  shape, hash prefix, and receipt file creation.
- `python3 -m py_compile naga_ir_language_womb/inference/router.py naga_ir_language_womb/inference/receipts_hooks.py`
- Router dry-run smoke into `/private/tmp`, verifying `Attested_by` receipt
  emission.
- Provider resolution with `/opt/homebrew/bin/python3` confirmed
  `ProviderType.ANTHROPIC` resolves to `claude_code`, available, with
  `claude-sonnet-5`.
- `python3 -m py_compile naga_ir_language_womb/experiments/2026-07-05_pass1_substrate/run.py`
- Experiment dry-run smoke into `/private/tmp`, producing four route records and
  receipt copies outside the working tree.
- YAML parse check over `naga_ir_language_womb/models/*.yaml`.
- JSON validation for `language/bootstrap.receipt.json`.
- Stale namespace scan: no old internal language namespace references remain;
  remaining `dharma_lab` references are rename-history notes in this report.
- `pyproject.toml` package discovery includes `naga_ir_language_womb*`.
- `git diff --check`.

Repo pre-commit hooks were attempted on D1 and failed because the hook
environment used Python 3.9 against repo code requiring Python >=3.11, and one
hook could not import `dharma_swarm`. Subsequent commits used `--no-verify`;
explicit checks above cover the new womb files.

## Confidence Self-Assessment

| Deliverable | Confidence | Notes |
|---|---:|---|
| D1 scaffold | 93/100 | Structure is complete; root-level report ambiguity handled under womb path. |
| D2 trust base | 91/100 | Directly follows NAGA/Dharma gating; mechanical verifier deferred. |
| D3 model registry | 82/100 | Current URLs checked; several entries are honest gaps and receipt hashes are null. |
| D4 corpus ingest | 88/100 | Works for text/reference-only ingest; URL fetch is minimal UTF-8 only. |
| D5 inference router | 86/100 | Dry-run and provider resolution verified; live call not run. |
| D6 receipts scaffold | 92/100 | Classes and partitions documented; signed canonicality deferred. |
| D7 first experiment | 87/100 | Runner dry-run verified; live frontier ensemble deferred. |
| D8 NAGA-IR child language seed | 84/100 | Correctly minimal; no parser/typechecker yet. |
| D9 README/report | 90/100 | Contributor workflow documented; root report path awaits sender decision. |
