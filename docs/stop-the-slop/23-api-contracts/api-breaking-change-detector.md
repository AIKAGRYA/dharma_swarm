---
id: api-breaking-change-detector
version: 0.0.1
theme: 23-api-contracts
status: tested
invariant: >
  Your public API is a contract with callers you don't control (Hyrum's law: every
  observable behavior is depended upon by someone). A change is breaking if it removes/
  renames a field, narrows a type, makes an optional input required, changes a status
  code, or alters semantics — and breaking changes need a version bump + deprecation
  window, not a silent deploy. Detect by diffing the API surface, not by guessing.
lineage:
  - "Hyrum's law — with enough users, every observable behavior is depended on"
  - "semantic versioning — breaking changes are a MAJOR signal to consumers"
  - "Meyer (DbC) — weakening a postcondition / strengthening a precondition breaks callers"
ground_truth_tools: ["diff the API schema (OpenAPI/types/router signatures) old vs new", "find removed/renamed/narrowed fields", "consumer/client code"]
returns_clean: true
---

## Prompt

> Detect **breaking API changes**. The invariant (Hyrum, semver, DbC): the public
> surface is a contract; a change breaks callers if it **removes/renames a field,
> narrows a type, makes an optional input required, changes a status code/error shape,
> or alters semantics**. Diff the API surface (OpenAPI spec, response models, router
> signatures) between versions and classify each change:
> **non-breaking** (add optional field/endpoint) vs **breaking** (the above). For each
> breaking change: what callers break, and the safe path (version bump + deprecation
> window, or additive-only). **Return clean** for purely additive diffs.

## Why it's built this way

Hyrum's law is why "no one uses that field" is wrong, and DbC is the precise rule
(strengthening a precondition / weakening a postcondition breaks callers). The
discipline is diffing the *surface* mechanically (the schema is the contract), not
eyeballing the handler.

## Demonstration run

**Target:** `dharma_swarm/api/` — **25 routers** — 2026-06-25.

- **The instrument:** FastAPI generates an **OpenAPI schema** — that's the diff-able
  contract. The audit routes to comparing the committed OpenAPI (or the Pydantic
  response models) across versions; the dashboard even consumes it via
  `openapi-typescript` (a real client → breaking changes break the dashboard build).
- **Disciplined output:** rather than guess, the prompt says: snapshot the OpenAPI
  schema in CI and **diff it per PR** (`oasdiff`); flag removed/renamed/narrowed fields
  as breaking. Since a typed client (`openapi-typescript`) already consumes the schema,
  the dashboard build is a built-in breaking-change tripwire — recommend wiring the
  schema-diff as an explicit gate. (Current state: UNASSESSED without the two-version
  diff — honestly noted, with the exact instrument to run.)

## Changelog

- **v0.0.1** (2026-06-25) — API breaking-change detector (Hyrum/semver/DbC): diff the
  OpenAPI/type surface, classify breaking vs additive. Tested on `dharma_swarm/api`: 25
  routers + a typed `openapi-typescript` consumer → recommended schema-diff-in-CI
  (`oasdiff`); honestly UNASSESSED without the version diff.
