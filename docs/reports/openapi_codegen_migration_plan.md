# PR-H5 — openapi-typescript codegen migration plan

**Status:** scaffold-only. This PR adds the generation pipeline. No
hand-written dashboard types are removed or replaced in this PR.

**Authority:** `external_worker_evidence_only` — every subsequent
migration step (H5a, H5b, …) ships as its own operator-approved PR.

**Active track:** `runtime-truth-spine-2026-06`.

## Why scaffold-only

The hardening audit framed the dashboard's hand-written types as
"42 type files duplicating the FastAPI schema." Surveying the
actual code revealed two corrections to that framing:

1. The dashboard does not have 42 separate type files. It has one
   primary `dashboard/src/lib/types.ts` plus a handful of per-surface
   contract files (e.g. `chatProfiles.ts`, `chatSessionContract.ts`,
   `controlPlanePageMeta.ts`, `runtimeOperatorHandbook.ts`). These
   are not pure DTO mirrors — several encode UI-side invariants and
   `zod` runtime validation that the OpenAPI schema does not express.
2. Wholesale replacement of those types with `components["schemas"]`
   from `openapi-typescript` would touch every hook, every page, and
   every test in a single PR. That violates the doctrine's preference
   for piecewise, reversible changes on the active runtime-truth-spine
   track.

The mitigation is the same scaffold-only contract pattern used for
PR-H3 (provider_registry) and PR-H4 (storage_schema_registry):

- New module / new pipeline is purely additive.
- Existing code paths are untouched.
- Opt-in is per-surface, behind a review gate.
- Rollback = delete the new files; zero blast radius.

## What this PR adds

| Path | Purpose |
|------|---------|
| `dashboard/package.json` | adds `openapi-typescript` devDep + `gen:types`, `gen:types:check` scripts |
| `dashboard/src/lib/api-generated.ts` | placeholder destination file for codegen; documents the migration target; intentionally empty so no hook can import from it yet |
| `docs/reports/openapi_codegen_migration_plan.md` | this document |
| `inter_agent/devin/outbound/2026-05-30-devin-openapi-codegen.md` | outbound notice |

What this PR **does not** do:

- Does not run codegen in CI.
- Does not replace any hand-written types.
- Does not modify any hook, page, component, or test.
- Does not modify `api/main.py` or any router (no backend changes).
- Does not modify any frozen surface
  (`dharma_swarm/spine/**`, `orchestrator.py`, `agent_runner.py`,
   `runtime_state.py`, `tests/test_dispatch_dropoff_sources.py`,
   `tools/spine_check.py`).

## Generation entry point

The FastAPI app (`api/main.py`) already serves the OpenAPI schema at
`/openapi.json` (default port `8420`, matching the dashboard's
`DEFAULT_INTERNAL_API_URL`). The new npm scripts target that URL by
default and honor `OPENAPI_URL` for CI or non-default deployments:

```bash
# Default (FastAPI on 127.0.0.1:8420):
cd dashboard && npm run gen:types

# Override (CI, alt port, alt host):
OPENAPI_URL=http://api.internal/openapi.json npm run gen:types

# Drift check (non-zero exit if generated file is stale):
cd dashboard && npm run gen:types:check
```

## Staged migration

Each stage is one PR. Each PR is operator-approved before the next
starts. Each stage is independently revertable.

### H5a — first opt-in surface (`useHealth` against `/api/health`)

- Run `npm run gen:types` against a live FastAPI to populate
  `api-generated.ts` with real types.
- In `useHealth.ts`, import the generated type alongside the
  hand-written `HealthOut`, then assert structural equivalence at
  compile time using a satisfies-style check:

  ```ts
  import type { components } from "@/lib/api-generated";
  import type { HealthOut } from "@/lib/types";
  type GeneratedHealth = components["schemas"]["HealthOut"];
  // Compile-time drift guard — if the FastAPI schema drifts from the
  // hand-written type, this assignment fails type-check.
  const _drift_guard: GeneratedHealth = {} as HealthOut;
  void _drift_guard;
  ```

- Does NOT remove `HealthOut` from `types.ts`. Does NOT change the
  hook's public type. The only purpose is to prove the round-trip.

### H5b — H5n — expand opt-in surfaces one router at a time

In rough order of how schema-stable each router is, judged from
existing audit reports:

- `health` (smallest, most stable) — covered in H5a
- `agents`
- `evolution`
- `ontology`
- `lineage`
- `stigmergy`
- `commands`
- `chat` and chat-session contracts (LAST — these encode the most
  UI-side invariants and likely keep hand-written types even after
  migration completes)

Each step adds a drift guard, leaves the hand-written type in place,
and is reviewed against a generated diff.

### H5-ci — CI drift check

Add `npm run gen:types:check` (or equivalent) to CI on a job that
spins up the FastAPI app, regenerates types, and fails if the
committed `api-generated.ts` differs from a fresh generation. This
catches backend schema changes that the dashboard hasn't picked up.

### H5-migrate — replace hand-written types where safe

Per-surface, replace the hand-written type alias with a re-export
from `api-generated`:

```ts
// before:
export interface HealthOut { ... }

// after:
import type { components } from "@/lib/api-generated";
export type HealthOut = components["schemas"]["HealthOut"];
```

Hand-written types that encode UI invariants the OpenAPI schema
cannot express (validation refinements, narrowed unions, frontend-
only fields) are kept and documented inline.

## Rollback

This PR is fully reversible by deleting four files:

```
dashboard/src/lib/api-generated.ts
docs/reports/openapi_codegen_migration_plan.md
inter_agent/devin/outbound/2026-05-30-devin-openapi-codegen.md
```

…and reverting the `package.json` additions (devDep + two scripts).
No installed dependency is required for the rest of the codebase to
build, because `openapi-typescript` is a devDependency only invoked
by an explicit npm script.

## Anti-doctrine self-check

- New substrate? No — adds a build-time codegen step to existing
  Next.js/TypeScript tooling.
- Meta-framework? No — uses the widely-adopted
  [`openapi-typescript`](https://github.com/openapi-ts/openapi-typescript)
  library; no in-house abstraction.
- Parallel governance? No — generated types live alongside hand-
  written types; the hand-written types remain the public contract
  until each surface is explicitly migrated under operator review.
- Vague prose? Each migration stage names the file edited, the
  router targeted, and the rollback step.
- Autonomous merging? No — every stage ships as its own PR with
  operator approval.
- Frozen surfaces touched? No.
