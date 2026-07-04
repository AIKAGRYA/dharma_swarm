# Dharma Swarm Project Brain

This file is the repo-local entrypoint for decision-grade memory. It does not
replace `AGENTS.md`, `README.md`, source files, or the trusted wiki under
`~/.dharma/knowledge/wiki`; it points agents to the current compiled truth and
the append-only timeline.

Start here:

- [Brain Index](docs/brain/index.md)
- [Brain Timeline](docs/brain/timeline.md)
- [Karpathy LLM Wiki Integration Plan](docs/plans/2026-07-05-karpathy-llm-wiki-system-integration.md)

Rules:

- Keep raw evidence in receipts, reports, source files, or the governed wiki.
- Put only decision-grade current truth in `docs/brain/index.md`.
- Append events to `docs/brain/timeline.md`; do not rewrite history there.
- If a decision changes, update compiled truth and add a timeline entry with
  source refs.

