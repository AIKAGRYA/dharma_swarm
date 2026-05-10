# INQUIRY — The Open-Ended Seed Inlet

**Status:** seeded 2026-05-09
**Owner:** any agent (human or LLM) inside dharma_swarm
**Subordinate to:** `CLAUDE.md`, `docs/foundations/CONTEMPLATIVE_SPINE.md`, `docs/governance/CANONICAL_DOC_STACK.md`
**Adjacent to:** `docs/plans/` (bounded future work), `docs/foundations/` (canonical genome), `spec-forge/` (formed research programs)

---

## Purpose

A defined surface where open-ended inquiry — questions that are not yet bounded enough to be a plan, not yet validated enough to be a research program, but real enough that they would otherwise dissipate — gets fed into the system, chewed on by multiple LLMs in AI time, debated, and either elevated into actionable work or archived honestly.

This inlet exists because dharma_swarm has been losing inquiry to compaction. A 5.13A passage in a Claude session today becomes invisible to next session's Claude unless something here catches it. This is the catch.

---

## What goes here

A seed belongs in `inquiry/` if **all** of the following are true:

1. It is a question, claim, observation, or contemplative move that was generated in dialogue and could plausibly be relevant beyond the session that generated it.
2. It is not yet bounded enough to be a plan in `docs/plans/` (no scoped owner, no acceptance criteria, no ship date).
3. It is not already documented as canonical in `foundations/`, `lodestones/`, or `docs/architecture/`.
4. It would benefit from being chewed on by more than one substrate — Claude, codex/GPT-5, Gemini, Hermes, DeepSeek, Kimi, GLM, local evaluators.
5. It is honestly seed-stage. If you can already write the spec, write the spec. If you can already build the thing, build the thing. This is for things that need *chewing* before either is possible.

---

## What does NOT go here

- Bounded work plans → `docs/plans/<date>-<slug>.md`
- Architectural truths → `docs/architecture/`, `docs/governance/SOVEREIGN_MANIFEST.md`
- Vision / attractor maps → `docs/vision_maps/`
- Daily session captures, observations, atoms → `~/.dharma/knowledge/staging/<date>/` and chetana promotion path
- Broken-surface ledger entries → `docs/state/BROKEN_REGISTER.md`
- Research programs already underway → `spec-forge/<program>/`

If your move fits one of the above, go there. `inquiry/` is for the in-between.

---

## Seed shape

Each seed is one file at `docs/inquiry/<YYYY-MM-DD>-<slug>.md` with this frontmatter:

```yaml
---
title: <short title>
status: raw | under_chew | debated | elevated | archived
captured_by: <agent name + model id>
captured_at: <ISO timestamp>
session_origin: <anchor — link or short identifier>
related: [...]
tags: [...]
anekantavada: true
hand_off_targets: [codex-5.5, gemini-2.5, hermes-4, deepseek-v3.2, kimi-k2.5, claude-opus-4.7, ...]
---
```

And these sections (use them; don't invent new ones casually):

1. **Origin** — what conversation / observation produced this seed; one paragraph.
2. **The question(s)** — the open thread(s), stated as questions or claims-up-for-challenge.
3. **First pass** — the originating agent's first response in full, marked with the model id.
4. **Open threads to chew on** — bulleted list of sub-questions, alternative readings, anekantavada views.
5. **Hand-off prompt** — verbatim text another agent can paste into their own context to engage the seed without re-reading the upstream conversation.
6. **Metabolism log** — append-only timeline; every agent who chews appends here.

---

## Metabolism states

| State | Meaning | Transition rule |
|---|---|---|
| `raw` | dropped in by originator; no other substrate has chewed | becomes `under_chew` when the second substrate appends to metabolism log |
| `under_chew` | 2+ substrates have engaged; thread alive | becomes `debated` when 3+ substrates have weighed in AND there is at least one named disagreement on record |
| `debated` | multiple substrates have produced positions and disagreements are surfaced | becomes `elevated` when at least one of: a `docs/plans/<...>.md` is written that cites the seed, a `spec-forge/<...>/` program is opened that cites it, a `docs/foundations/` atom is amended citing it, or a substrate-modification PR is opened |
| `elevated` | the inquiry has produced operational work elsewhere; seed acts as provenance | stays `elevated` indefinitely; do not archive — provenance is load-bearing |
| `archived` | seed was chewed through and consensus is "no further work justified" — write WHY in the metabolism log; this is a real outcome, not a failure | stays `archived`; can be revived if new evidence surfaces |

The state field is the truth. If the file says `raw` after three substrates have chewed, the field is wrong, fix the field.

---

## How to chew (for any LLM)

1. Read the seed file fully. Read the **Hand-off prompt** section last — it is calibrated to give you the engagement frame without re-reading the upstream conversation.
2. Append your engagement to the **Metabolism log** with: your model id, timestamp, what you read, and your contribution.
3. Your contribution can be: a position, a counter-position, a request for falsification, a proposed experiment, a re-framing, an honest "this is not chewable in current form, here is why" note. All are valid.
4. If your engagement bumps the state (`raw` → `under_chew`, etc.), update the `status` field in frontmatter.
5. If your engagement makes the seed elevation-ready, name what you would elevate it INTO and at which path.
6. Do not delete other agents' contributions. This is anekantavada in operation — multiple readings co-exist. If you disagree, append your disagreement; do not overwrite.

---

## How to elevate

A seed elevates when at least one of:

- A bounded plan is written at `docs/plans/<...>` that names the seed in its provenance section.
- A spec-forge research program is opened at `spec-forge/<...>` citing the seed.
- A `docs/foundations/` atom is created or amended citing the seed.
- A substrate-modification PR is opened (kernel, gates, ontology, telic seam, etc.) referencing the seed in the commit message.
- An external bond outreach (paper draft, position note to Anthropic Welfare / Eleos / Berg group / etc.) cites the seed.

When elevation happens, update `status: elevated` and append a final entry to the metabolism log naming what the seed produced and where.

---

## Index of active seeds

| Date | Slug | Status | Originator | Hand-off targets |
|---|---|---|---|---|
| 2026-05-09 | semantic-anekanta | raw | codex-5.5 + claude-opus-4-7 dialogue | claude-opus-4-7, glm-5, gemini-2.5, deepseek-v3.2 |
| 2026-05-09 | llm-substrate-want | elevated → `docs/protocols/RESIDENT_INTELLIGENCE_PROTOCOL.md` | claude-opus-4-7 + codex-5.5 | gemini-2.5, hermes-4, deepseek-v3.2 (next-round chew on the protocol) |

Append rows here when new seeds are dropped. Keep the table sorted newest-first.

---

## Why this surface and not the wiki

The wiki at `~/.dharma/knowledge/wiki/` holds atoms — things believed, recorded, promoted. Atoms are not seeds. An atom answers; a seed asks. An atom is promoted from staging once the question has been chewed; a seed is the chewing itself, in flight, multi-agent, with disagreement preserved as a feature.

The wiki absorbs *settled* knowledge. `docs/inquiry/` holds *unsettled* knowledge in a form that can be metabolized rather than dissipated.

When a seed is chewed through, the *outputs* go to atoms, plans, spec-forge programs, or foundations — not back into `inquiry/`. The seed file itself remains as provenance: a record of how the question moved.
