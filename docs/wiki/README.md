---
title: dharma_swarm wiki — canonical-knowledge layer
status: seed
provenance: docs/specs/HYBRID_MEMORY_SUBSTRATE_V01_MASTER_BUILD.md; docs/vision_maps/NORTH_STAR.md §9; reports/operator_debrief_2026-08-09/OPERATOR_DEBRIEF.md
updated: 2026-08-09
---

# The dharma_swarm wiki

This directory is the **canonical-knowledge layer of the hybrid memory
substrate, metabolized to git as reviewed text**. It is the "Karpathy LLM
Wiki" layer of the three-layer hybrid defined in
`docs/specs/HYBRID_MEMORY_SUBSTRATE_V01_MASTER_BUILD.md` §2: the
LLM-maintained, human+agent-readable synthesis layer where knowledge
compounds under an explicit schema, while MemoryKernel stays the typed
governance bus and the GO/world_radar spine stays receipt-first external
perception.

Why text in git and not a database: the canon-metabolism rule.
`docs/vision_maps/NORTH_STAR.md` §9 — canon may be *seeded* anywhere, but
"nothing is canonical until it is **metabolized to main**", and "`git` main
is the single ordering authority". A wiki page in this directory is a claim
that has been written down, cited, and pushed through review like any other
change; that is what makes it canonical rather than split-brain.

## The three-class state doctrine

Every piece of organism state belongs to exactly one class:

| Class | Lives | Rule |
|---|---|---|
| **Runtime receipts** | `~/.dharma/` | Never enter git (CLAUDE.md "Runtime receipts never enter git"); loop-generated, machine-owned, append-only. |
| **Canonical knowledge** | `docs/wiki/` (here) | Reviewed TEXT in git; every claim cited (`file:line` or runnable command); metabolized to main per NORTH_STAR §9. |
| **Derived indexes** | untracked / `generated/status` | Rebuilt on demand, never hand-edited, never authoritative (e.g. `reports/governance/active_track_evidence.md` is untracked and CI-published — CLAUDE.md "For machine-readable status"). |

If a page here disagrees with code or with a runtime receipt, the page is
wrong: "when prose and code disagree — including this file — the code is the
truth" (CLAUDE.md, opening paragraph).

## Page schema

Every page carries YAML frontmatter:

```yaml
---
title: <human title>
status: seed | reviewed | promoted
provenance: <source files / receipts / commands this page is compiled from>
updated: YYYY-MM-DD
---
```

- `seed` — written by one agent, cited, not yet independently reviewed.
- `reviewed` — a second agent or the operator verified every citation.
- `promoted` — reached via the MemoryKernel promotion seam (spec §3 Seam B):
  the frontmatter must then also carry the promotion receipt id and source
  atom ids. No page may claim `promoted` without that receipt.

Raw sources stay immutable; pages cite them, never replace them
(spec §2: "Raw sources stay immutable").

## Current pages

- `ORGANISM_IDENTITY.md` — the One Line, telos, hierarchy, ONE LAW, needle.
  This is the page injected into agents.
- `ORGAN_MAP.md` — the organ table with honest statuses, plus what was
  observed alive/dead at runtime on 2026-08-09.
- `SEEING.md` — where every knowledge/state store lives, what is empty, and
  the one-command fullness check (`python3 scripts/governance/darshan_pack.py`).
