# ForgeRSILab Meghadharma PR-Suite Closeout

Run id: `megha_pr_suite_controlsplit_auth_20260704T031305Z`  
Host: `meghadharma`  
Repo/branch/head: `/root/ds_forge_spine_v0`, `feat/rsi-lab`, `569187fac07aa9d4bbc9ea670cc4d126a249ca44`  
Local evidence copy: `reports/forge_rsi_lab/megha_pr_suite_controlsplit_auth_20260704T031305Z/`

## What Ran

This was a deterministic ForgeRSILab PR-suite harvest and fail-to-pass validation
run. It did not call an LLM model. The running process was:

```bash
python3 scripts/runtime/forge_pr_suite_harvest_loop.py
```

The loop used GitHub PR metadata, local git checkouts, pytest-style
fail-to-pass validation, and `/root/.venv-forge/bin/python` on Meghadharma.
The model-powered solver/evolution phase remains a later step.

## Closeout Numbers

- Started: `2026-07-04T03:13:06Z`
- Finished: `2026-07-04T11:13:10Z`
- Cycles: `32`
- Repos scanned: `pallets/click`, `pallets/werkzeug`, `pallets/flask`, `pallets/jinja`, `pytest-dev/pytest`, `django/django`, `encode/httpx`, `encode/starlette`, `psf/requests`, `pydantic/pydantic`
- Raw candidate observations: `2230`
- Seen candidates: `71`
- Unique candidates validated: `50`
- Validation receipts: `50`
- Strict valid imported tasks: `3`

Validated task rows:

- `https://github.com/pytest-dev/pytest/pull/14647` — `testing/test_reports.py`
- `https://github.com/pytest-dev/pytest/pull/14588` — `testing/io/test_pprint.py`
- `https://github.com/pytest-dev/pytest/pull/14624` — `testing/test_conftest.py`

## Authority Boundary

The closeout records:

- `source_code_mutation_allowed: false`
- `source_of_truth_mutated: false`
- `live_apply_allowed: false`
- `live_apply_performed: false`
- `archive_fitness_mutated: false`
- `official_score_claimed: false`
- `taskbed_import_allowed: true`
- `promotion_gate: verify_promotion_only`

So this run is meaningful as benchmark taskbed evidence. It is not evidence of
model solving, autonomous self-evolution, official benchmark score, or production
promotion.

## Local Artifact Hashes

- `closeout.json`: `c7f56657a4840a8efb5943987ea3b7781fadd0196ae18a3ebe687434b3585ada`
- `validated_c00_20260704T031306Z.jsonl`: `8f5089f2f52fdf1dc8b9cbd4f36d153394560a9f98dbf5f97139ff58b9586940`

## Interpretation

Conclusive/significant:

- The current ForgeRSILab harness can run for a full 8-hour window on Meghadharma.
- The authenticated PR-suite harvester and de-duper work across a 10-repo Python corpus.
- The fail-to-pass validator is strict enough to reject most candidates and admit only 3 usable tasks.
- The authority boundary held: no live apply, source mutation, archive-fitness mutation, or public score claim.

Not yet conclusive:

- No LLM solved these tasks.
- No budget-matched model comparison ran.
- No E4 significance gate or autonomous evolution promotion passed.
- The next proof step is exact-ID grade-only execution for the 3 imported tasks.
