# Devin outbound — 2026-05-30 — PR-H5 openapi-typescript codegen (scaffold)

**From:** Devin (Roaming) AGT-DEVIN_ROAMING_2987D222
**Track:** `runtime-truth-spine-2026-06`
**Authority:** `external_worker_evidence_only`
**Branch:** `devin/2026-05-30-openapi-codegen` (sibling, not stacked)
**PR:** TBD (opened immediately after this notice lands)
**Slate position:** H5 of the {H1, H2, H3, H4, H5} hardening slate.

## Summary

Adds a scaffold for dashboard type generation from the FastAPI
OpenAPI schema. No hand-written types are removed or replaced. No
hook, page, component, or test is modified. The pipeline is purely
opt-in and will be wired surface-by-surface in follow-up PRs.

## What ships

- `dashboard/package.json` — `openapi-typescript@^7.4.4` added to
  `devDependencies`; new scripts `gen:types` and `gen:types:check`
  pointing at `/openapi.json` (overridable via `OPENAPI_URL`).
- `dashboard/src/lib/api-generated.ts` — placeholder destination,
  documented as "do not import yet."
- `docs/reports/openapi_codegen_migration_plan.md` — H5a → H5-migrate
  staged plan with rollback section.
- This outbound notice.

## Why scaffold-only

The audit's claim of "42 hand-written type files duplicating FastAPI
schema" was a text-match overcount. Survey of `dashboard/src/lib/`
showed:

- One primary `types.ts` plus a handful of per-surface contract
  files (`chatProfiles.ts`, `chatSessionContract.ts`,
  `controlPlanePageMeta.ts`, `runtimeOperatorHandbook.ts`, etc.).
- Several of those files encode UI-side invariants (`zod` schemas,
  narrowed unions, frontend-only fields) that the OpenAPI schema
  cannot express, so they cannot be wholesale replaced.

A single-PR mass rewrite would touch every hook, every page, and
every test, which violates the doctrine's preference for piecewise,
reversible changes. Scaffold-only matches the pattern used for
PR-H3 (provider_registry) and PR-H4 (storage_schema_registry).

## Anti-doctrine self-check

- **New substrate?** No — `openapi-typescript` is the standard
  community tool for this. No in-house abstraction.
- **Meta-framework?** No — codegen is a build-time script, not a
  runtime layer.
- **Parallel governance?** No — hand-written types remain the
  public contract on every surface until that surface is migrated
  under operator review.
- **Vague prose?** Migration plan names every file, every router,
  and every rollback step.
- **Autonomous merging?** No — every staged migration ships as its
  own PR with operator approval.
- **Frozen surfaces touched?** No.
  - `dharma_swarm/spine/**` — untouched
  - `orchestrator.py` — untouched
  - `agent_runner.py` — untouched
  - `runtime_state.py` — untouched
  - `tests/test_dispatch_dropoff_sources.py` — untouched
  - `tools/spine_check.py` — untouched
- **Backend touched?** No. `api/main.py` and routers are unchanged.
  The pipeline only consumes the OpenAPI schema FastAPI already
  serves at `/openapi.json`.

## Verification

- `package.json` is valid JSON (parsed via `python -m json.tool`).
- `api-generated.ts` exports nothing usable; any hook trying to
  import a named symbol from it will fail type-check, preventing
  accidental adoption before H5a is reviewed.
- Migration plan documents the drift-guard pattern that makes H5a
  safe: a `satisfies`-style compile-time assertion between the
  generated type and the hand-written type. If FastAPI's schema
  drifts from the hand-written type, the dashboard build fails
  before runtime.

## Rollback

Delete the four files listed in
`docs/reports/openapi_codegen_migration_plan.md#rollback` and revert
the `package.json` additions. Zero behavioral blast radius — no
existing build path consumes `openapi-typescript` until an
operator-approved follow-up PR opts in.

## Follow-up PRs queued (each operator-approved)

- **H5a** — wire `useHealth.ts` to a compile-time drift guard
  against `components["schemas"]["HealthOut"]`. Hand-written type
  stays.
- **H5b–H5n** — opt in `agents`, `evolution`, `ontology`,
  `lineage`, `stigmergy`, `commands`, then chat last.
- **H5-ci** — CI drift check via `npm run gen:types:check`.
- **H5-migrate** — per-surface, replace hand-written aliases with
  `components["schemas"][...]` re-exports where the OpenAPI schema
  is a complete description of the type. Hand-written types that
  encode UI-only invariants stay and are documented inline.
