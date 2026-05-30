/**
 * AUTO-GENERATED — DO NOT EDIT BY HAND.
 *
 * This file is the destination for `npm run gen:types`, which runs
 * `openapi-typescript` against the FastAPI app's `/openapi.json` endpoint
 * and overwrites this file in place.
 *
 * STATUS (PR-H5 scaffold): not yet wired.
 * ------------------------------------------------------------------
 * This placeholder exists so that:
 *   1. The path `@/lib/api-generated` resolves under TypeScript strict
 *      checks without requiring contributors to run codegen on first
 *      checkout.
 *   2. Reviewers can see the migration target without diffing through
 *      a multi-thousand-line generated artifact in this PR.
 *
 * Until codegen runs against a live API, NO hook should import from
 * this module. Hand-written types in `./types.ts` (and the per-surface
 * contract files alongside it) remain the source of truth.
 *
 * MIGRATION
 * ------------------------------------------------------------------
 * See `docs/reports/openapi_codegen_migration_plan.md` for the
 * staged H5a → H5-migrate plan. The first surface targeted is
 * `useHealth.ts` against `GET /api/health`, behind a side-by-side
 * type assertion so any drift between generated and hand-written
 * shapes surfaces as a compile error rather than a runtime bug.
 *
 * REGEN
 * ------------------------------------------------------------------
 *   # from repo root, with FastAPI running on the default port (8420):
 *   cd dashboard
 *   npm run gen:types
 *
 *   # CI parity check (fails if generated file is stale):
 *   npm run gen:types:check
 *
 * The OpenAPI URL can be overridden via the OPENAPI_URL env var.
 */

// Intentionally empty. The codegen step will REPLACE this entire file
// with the typed `components`, `paths`, and `operations` exports from
// openapi-typescript. Do not add hand-written declarations here.

export {};
