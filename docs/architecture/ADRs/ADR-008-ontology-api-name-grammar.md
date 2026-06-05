# ADR-008: Ontology `api_name` Grammar, Status Lifecycle, and Versioning

> **Date:** 2026-06-01
> **Status:** PROPOSED (awaiting operator ratification; grill in progress)
> **Decision:** An ObjectType's public identifier is `api_name = dharma.<domain>.<TypeName>` — a **stable, unversioned** string where `<domain>` is lowercase snake_case and `<TypeName>` is the type's internal `name` field verbatim (PascalCase). **No `.v<N>` suffix.** Version lives in the existing `ObjectType.version: int` field. Lifecycle is `TypeStatus` = experimental → active → promoted (operator-only promotion). Breaking changes deprecate the type and introduce a new `TypeName`, never a name-version bump.
> **Companions:** PR #410 (`palantir-api-discipline.md` grounding), PR #408 (typed-proposal envelope + schema-alignment gate), PR #409 (OMS hardening), PR #406 (W1 telos-gate-in-`execute_action`).

---

## Context

dharma_swarm has **five agents** (claude, perplexity, devin, hermes, mike) editing one ontology concurrently. Palantir Foundry — the grounding reference — does ontology with a *single* forward-deployed engineer and a centralized Object Metadata Service (OMS) authority. We have no single authority; the replacement is a **typed-proposal envelope** (#408) + a **schema-alignment CI gate** (#408, KARMA-style) + **operator-only merge**. The ontology is **defined in code** (`dharma_swarm/ontology.py`: 22 module-level `_X = ObjectType(...)` definitions, registry built at import by `create_dharma_registry()`); there is no runtime OMS service. "Proposals" are therefore typed PRs and the gate runs in CI.

This ADR exists because the multi-agent model produced a **live, concrete conflict** that proves the grammar was under-specified:

- **PR #408** (perplexity) enforced `dharma.<domain>.<TypeName>.v<N>` with an **UpperCamel** TypeName.
- **PR #409** (devin) backfilled all 21 existing types as **lowercase** `dharma.<domain>.<entity>.v<N>`.
- **Every one of devin's 21 names fails perplexity's regex.** Two competent agents built two incompatible grammars for the same field — exactly the multi-agent ontology-editing problem #405 §7.1 flagged as unsolved.

A second, deeper ambiguity sat underneath it: **two version numbers**. `ObjectType.version: int` already existed on `main`; #409's `api_name` carried its *own* version in the `.v<N>` suffix. Nothing defined their relationship — the agents weren't even versioning the same thing.

A `/grill-with-docs` session (2026-06-01) resolved both against **verified Palantir grounding** (#410, `palantir-api-discipline.md`, multiple Foundry doc citations). The decisive evidence:

> *"Avoid versioned Object Type names. **Bad: `Message_v2`. Worse: `Message_v3_Embedded`.**"* — Palantir Foundry Solutions Architect, *Ontology and Pipeline Design Principles*, Nov 2025

Palantir uses **plain, unversioned api_names** plus stable RIDs as the immutable identifier; the api_name is a *mutable human-readable shorthand*, and `.v<N>` is "a Protobuf idiom, not an OMS idiom." Our enforced `.v<N>` pattern was **exactly the prohibited anti-pattern**. Versioning in Foundry is carried by schema versions + the metadata-status lifecycle + breaking-change migrations (deprecate old type, create new) — never by the name.

## Options Considered

| # | Grammar | Verdict |
|---|---------|---------|
| A | `dharma.<domain>.<lowercase_entity>.v<N>` (#409) | ✗ versioned name (anti-pattern); lossy (`ResearchThread`→`thread`); breaks api_name↔name 1:1 |
| B | `dharma.<domain>.<UpperCamel>.v<N>` (#408) | ✗ versioned name (anti-pattern); case correct |
| C | `dharma.<domain>.<PascalCase>.v<N>` (operator's first pick, ADR draft) | partial — case correct, but `.v<N>` is the anti-pattern; leaves the two-version problem unresolved |
| D | **`dharma.<domain>.<PascalCase>` + version in `version:int`** (CHOSEN) | ✓ Palantir-aligned; resolves the two-version problem; api_name↔name 1:1 trivial |
| E | raw Foundry `lowerCamelCase` (`flightAlert`) | ✗ for us — loses the 1:1 mapping to our PascalCase internal `name`; our types are already PascalCase |

## Decision

**Option D.** The synthesis is strictly better than any single agent's answer, and makes everyone partially right: PascalCase (the operator's instinct) + drop `.v<N>` (perplexity/#410's verified grounding) + reuse the `version: int` field that already exists.

### Grammar

```
api_name = "dharma." <domain> "." <TypeName>
  <domain>   = lowercase, snake_case        e.g. research, agent, governance, economic
  <TypeName> = the ObjectType's `name` field, verbatim (PascalCase)

regex: ^dharma\.[a-z][a-z0-9_]*\.[A-Z][A-Za-z0-9]*$      # NO version suffix
```

Examples (TypeName is the literal `name=` on each `_X = ObjectType(...)`):

```
dharma.research.ResearchThread
dharma.agent.PersistentAgentIdentity
dharma.governance.GateDecision
dharma.economic.ValueEvent
dharma.governance.AuditFinding          # the consolidation target (devin's 13→1)
```

Because `<TypeName>` *is* the internal `name`, ALIGN-002 (api_name ↔ name is 1:1) is trivially satisfied and the mapping is lossless and human-traceable.

### Sibling conventions (Palantir-grounded)

PascalCase applies to **object types**. Palantir's docs ([Create an object type](https://www.palantir.com/docs/foundry/object-link-types/create-object-type)) mandate *different* casing per ontology element — adopted verbatim:

| Element | Casing | Example |
|---|---|---|
| **ObjectType** api_name | **PascalCase** (uppercase first) | `dharma.research.ResearchThread` |
| **Property** api_name | camelCase (lowercase first) | `telosAlignment`, `createdAt` |
| **Action / Function** api_name | lowerCamelCase | `proposeEntry`, `promoteStatus` |
| **LinkDef** api_name | camelCase (by analogy to properties; verify vs Foundry link-type docs if load-bearing) | `authoredBy`, `derivedFrom` |

A single global casing was the wrong question: Foundry deliberately uses PascalCase for *types* and camelCase for *properties/actions* because they signal different things (a type vs. a value/verb). perplexity's camelCase grounding was correct **for properties and queries** — it was mis-scoped to object types.

### Status lifecycle

`TypeStatus` (from #409) is monotonic: `experimental` → `active` → `promoted`.

- `experimental` — agent-proposed, not yet trusted as a stable contract.
- `active` — merged to `main`, usable by all agents.
- `promoted` — operator-blessed public contract. Promotion is **operator-only** (a separate `ProposalKind.PROMOTE_STATUS` envelope, `blessed_by` = operator handle). Agents may never propose `promoted`.

**api_name mutability is tied to status** (Palantir *Statuses* rule, grounded via #413): an `api_name` may be **renamed only while `experimental`** — it is **frozen on `active`** and immutable once `promoted`. This is the guard against the silent-breakage failure mode #410 documents: once a type is `active`, downstream consumers (OAG queries, OSDK codegen) rely on the name being stable.

### Versioning / SEMVER policy

`version: int` is the **only** version mechanism (the `.v<N>` suffix is gone).

- **Additive / non-breaking** (new optional property, new link, new action, doc edit): evolve the type **in place**; bump `version: int`. api_name unchanged.
- **Breaking** (remove/rename/retype a property, change a link's cardinality or target, change an action signature): **do not mutate a `promoted` type.** Deprecate it (`status` → a `deprecated` state, with `replacement` pointer) and introduce a **new `TypeName`** (hence a new api_name). This is the Palantir migration discipline, not a name-version bump.
- A `promoted` api_name is immutable: its contract never changes shape; only additive evolution is permitted, and truly breaking change means a new type.

## Consequences

### Positive
- **One version mechanism, in the right place.** The two-version ambiguity that split #408/#409 is gone.
- **Palantir-aligned.** We stop enforcing the exact anti-pattern Palantir documents against.
- **api_name is a true stable contract** — safe for the forthcoming OSDK-style codegen (hermes's piece) and for OAG typed queries.
- **ALIGN-002 trivial**; the schema-alignment gate's job gets simpler.

### Negative
- #409 must rebase its 21 backfilled api_names (drop `.v1`, PascalCase the TypeName). One-time, mechanical.
- #408's envelope/regex must drop the `.v<N>` group and the gate's ALIGN-007 pattern updates. Small.
- "No version in the name" requires discipline: breaking change = new type, which is heavier than a version bump (intentionally — it's the Palantir guardrail against silent breakage).

### Neutral
- `version: int` keeps its meaning (it was always there); it is now the single version field rather than a redundant one.
- LinkDef/ActionDef api_name grammar is **not** decided here (see Open Questions).

## Open Questions for Operator

These surfaced in the grill and are **not** yet resolved — ADR-008 should not be considered final until they are:

1. **Status authority on backfill.** #409 backfills 21 existing types as `active` directly in code, bypassing the `experimental → active` proposal flow. Is `active`-on-merge correct for code-defined types (with `experimental` reserved for in-PR proposals), or should a type become `active` only via an explicit step? *(The related sub-question — when api_names may change — is now answered in Status lifecycle above: renamable only while `experimental`, frozen on `active`, per #413's Palantir grounding.)*
2. **Gate authority — blocking or advisory?** Is the schema-alignment gate a hard CI failure (blocking), or advisory input to mike + operator? Palantir has a single OMS authority; we have a gate + mike + operator. Which is final?
3. ~~**LinkDef / ActionDef api_names.**~~ **RESOLVED** (Palantir-grounded — see *Sibling conventions* above): actions/functions → lowerCamelCase, properties → camelCase, links → camelCase. Only object types are PascalCase.
4. **#409 uniqueness guard is process-local** (verified, #410): two agents in parallel processes can both `register_type` the same api_name without detecting the conflict; the CI gate only runs in CI. Is CI-time enforcement sufficient, or does the runtime registry need a guard?

## Related Decisions

- PR #410 — `palantir-api-discipline.md` (the verified grounding for this ADR).
- PR #408 — typed-proposal envelope + schema-alignment gate (the multi-agent OMS-authority replacement).
- PR #409 — OMS hardening (`TypeStatus`, `api_name` field, uniqueness guard) — rebases its api_name values to this grammar.
- PR #406 — W1: telos gate hard-wired into `execute_action` (the kinetic-layer chokepoint).
- ADR-006 — SHAKTI_GINKO organ (prior ADR; template followed here).

## Status History

- **2026-06-01** — PROPOSED on branch `docs/adr-008-ontology-api-grammar`, authored by claude (opus_composer) from the `/grill-with-docs` session + verified Palantir grounding. Operator ratifies by merge; the four Open Questions remain for the grill's next rounds.
