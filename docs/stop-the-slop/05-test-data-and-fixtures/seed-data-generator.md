---
id: seed-data-generator
version: 0.0.1
theme: 05-test-data-and-fixtures
status: tested
invariant: >
  Seed/fixture data must be FAITHFUL to the real schema (no invented fields),
  REFERENTIALLY consistent (foreign keys resolve to real parents), DISTRIBUTED
  like production (realistic enum mixes and time spread, not clustered at "now"),
  EDGE-COVERING on purpose (empty, max, long, unicode, soft-deleted), and
  REPRODUCIBLE (fixed seed). Boring `User 1` / `test@test.com` data hides exactly
  the bugs seed data exists to surface.
lineage:
  - "Claessen & Hughes 2000 (QuickCheck) — generate varied inputs; shrink toward edge cases"
  - "Myers — equivalence partitioning & boundary-value analysis (the deliberate edges)"
  - "Codd 1970 — the relational model; referential integrity is a constraint, not a vibe"
ground_truth_tools: ["the actual schema file (parse it; do not assume fields)", "a fixed-seed PRNG", "the ORM's own types/migrations"]
returns_clean: true
---

## Prompt

> Generate a reproducible seed script that creates realistic, varied development/
> demo data. The invariant you defend: seed data must be **faithful** to the real
> schema, **referentially** consistent, **distributed** like production,
> **edge-covering** on purpose, and **reproducible**. Boring `User 1` /
> `test@test.com` data hides the bugs seeding exists to expose.
>
> **For "ground truth" in a generation task, faithfulness replaces measurement:**
> the schema is the instrument. Read it; never invent a field.
>
> **My context:**
> - Schema: in the files provided — **parse it first; enumerate every table,
>   column, type, enum, nullability, and foreign key before writing a line.**
> - ORM: `[Prisma | Drizzle | node-postgres | Supabase | SQLAlchemy | …]`
> - Domain: `[e.g. B2B project-management for freelance designers]`
> - Scale: `[e.g. 20 users, 50 projects, 200 tasks across statuses/dates]`
>
> **Hard rules:**
> 1. **Schema-faithful or stop.** Use only fields that exist in the schema. If any
>    field's meaning, enum set, or relationship is unclear, **ask before guessing**
>    — do not invent columns, statuses, or relations.
> 2. **Culturally varied identities.** Names, emails, company names look real and
>    span regions. No `John Doe`, no `Acme Inc`.
> 3. **Production-like distributions.** Timestamps spread across realistic ranges
>    (old, recent, this week) — never a cluster at `now()`. Enum values in a
>    believable mix (not all `in_progress`).
> 4. **Deliberate edge cases** (Myers boundaries): a user with 0 children, a parent
>    with 0 and one with many, an extremely long text field, a name with unicode/
>    emoji, and a soft-deleted row **iff** the schema supports it.
> 5. **Referential integrity** (Codd): every foreign key resolves to a real parent;
>    relationships are coherent (a task's project is owned by the task's assignee,
>    etc.).
> 6. **Reproducible:** seed the PRNG with a fixed value so reruns are identical.
> 7. **One runnable file** at the ORM's idiomatic path (e.g. `prisma/seed.ts`),
>    with a clear `main()` and a **count summary** printed at the end.
>
> Do not invent fields not in the schema. If a field is unclear, ask before
> guessing. If the schema is too ambiguous to seed safely, say so and list exactly
> what you need — do not produce a plausible-looking script against a guessed schema.

## Why it's built this way

The kit's version is already strong (varied identities, edge cases, fixed seed).
Two upgrades make it *disciplined*: (1) **parse-the-schema-first / faithfulness-or-
stop** — the generation-task analogue of "route to ground truth": the schema is the
instrument, and inventing a field is the generative form of slop; (2) explicit
**lineage** — the deliberate edge cases are Myers' boundary-value analysis, the
"varied inputs that surface bugs" is QuickCheck's whole thesis, and referential
integrity is Codd's constraint, not a nicety.

## Demonstration run — with an honest applicability note

`dharma_swarm` is **not a relational CRUD app** with a seedable schema (it's an
agent runtime over Pydantic models + 29 `aiosqlite` stores, no `CREATE TABLE`
app schema). A live DB-seed demo would be fabricated — so per our own rule, we
don't fake one. Instead we demonstrate the load-bearing discipline against a
**real** artifact: `dharma_swarm/models.py` (29 Pydantic models).

- **Faithfulness check (the core discipline):** pointed at `models.py`, the prompt
  must generate instances using only the 29 models' declared fields/enums and
  **refuse to invent** a field — exactly the "don't guess the schema" rule. A
  Pydantic model *is* a schema; valid varied instances respect its types,
  `Enum` choices, and `Optional`/required nullability, which is the same contract
  the SQL version enforces.
- **What does NOT transfer:** referential integrity across tables (no relational
  FK graph here) — correctly **out of scope** for this repo rather than invented.

The point of including this honest note: a disciplined library says "this prompt
doesn't apply to this repo, and here's the part that does" instead of
manufacturing a demo. That refusal is the product.

## Changelog

- **v0.0.1** (2026-06-25) — rewrite of a kit's seed-data prompt. Added parse-the-
  schema-first / faithfulness-or-stop (the generation analogue of route-to-ground-
  truth), explicit lineage (QuickCheck, Myers boundaries, Codd integrity), and an
  honest applicability note (dharma_swarm has no relational schema to seed; demoed
  the faithfulness discipline against real Pydantic models instead of faking a DB).
