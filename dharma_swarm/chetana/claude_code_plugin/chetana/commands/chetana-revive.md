---
description: Propose revival for stale atoms — re-integrate, don't exile.
argument-hint: "[--all] [--apply] [<atom_path>]"
---

Run `python -m dharma_swarm.chetana.cli revive $ARGUMENTS` using the chetana python (resolution order in the chetana SKILL.md).

Default is `--all` (every atom past `stale_after`); a specific atom path overrides.

Two modes — the difference matters:
- **Without `--apply`** (default): output is a PROPOSAL only. Nothing on disk changes. Present the proposed patches to the user.
- **With `--apply`**: each revived atom is rewritten in place with a fresh `stale_after`, updated `confidence`, and a new entry appended to `provenance.revival_chain`, routed through the governance gates. Only pass `--apply` when the user has explicitly asked to apply (include `--reviewer <name>` when they do).

Never jump straight to `--apply` because "the proposal looked fine" — propose first, apply on confirmation.

Report format: `revive: <n> atoms examined · <n> proposals` (proposal mode) or `revive --apply: <n> rewritten, revival_chain appended · <paths>` (apply mode). If zero atoms are stale, say that — it's a healthy result, not a failure.
