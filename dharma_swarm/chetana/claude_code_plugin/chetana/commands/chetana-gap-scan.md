---
description: Scan the wiki for under-covered topics + recurring open questions.
argument-hint: "[--focus <topic>] [--queue <path>]"
---

Run `python -m dharma_swarm.chetana.cli gap-scan $ARGUMENTS` using the chetana python (resolution order in the chetana SKILL.md).

Output is a markdown report listing:
- **Topic gaps**: `[[wikilinks]]` referenced ≥2 times across atoms but with no article of their own
- **Open questions**: `?` sentences appearing repeatedly in atom bodies

Pass `--queue <path>` to also write a structured JSONL gap queue for downstream research agents; confirm the file exists after the run before telling the user it was written.

Present the report as-is, then add one line of triage: the top 1-3 gaps you'd research first and why. Do not start researching the gaps unprompted — surfacing them is this command's whole job.

An empty report on a young wiki is normal; say "no gaps found at current corpus size" rather than treating it as an error.
