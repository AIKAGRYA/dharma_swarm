---
description: Propose revival for stale atoms — re-integrate, don't exile.
argument-hint: "[--all] [--apply] [<atom_path>]"
---

Run `python -m dharma_swarm.chetana.cli revive $ARGUMENTS` using the chetana venv.

If the user passed `--apply`, the revived atom is rewritten in place with a fresh `stale_after`, updated `confidence`, and a new entry appended to `provenance.revival_chain`. Without `--apply`, the output is a proposal only.

Default: `--all` (every atom past stale_after). Specific atom path overrides.
