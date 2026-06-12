---
description: Scan the wiki for under-covered topics + recurring open questions.
argument-hint: "[--focus <topic>] [--queue <path>]"
---

Run `python -m dharma_swarm.chetana.cli gap-scan $ARGUMENTS` using the chetana venv.

Output is a markdown report listing:
- Topic gaps: `[[wikilinks]]` referenced ≥2 times in atoms but no article exists for them
- Open questions: `?` sentences appearing repeatedly in atom bodies

Pass `--queue <path>` to write a structured JSONL gap queue for downstream agents to research.
