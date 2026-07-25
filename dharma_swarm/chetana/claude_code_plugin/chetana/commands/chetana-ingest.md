---
description: Capture raw content (note / webclip / pdf / session / voice) into a staged atom.
argument-hint: "<source-path-or-text> [--kind ...] [--title ...] [--tag ...]"
---

Run `python -m dharma_swarm.chetana.cli ingest $ARGUMENTS` using the chetana python (resolution order in the chetana SKILL.md).

Source kinds — pick the right one; when unsure, ask rather than defaulting blindly:
- `note` — inline text or a markdown file
- `webclip` — Obsidian Web Clipper output
- `pdf` — routed through MarkItDown
- `session` — a Claude Code JSONL transcript
- `voice` — voice memo (routed through MarkItDown)
- `external` — anything else

Result: one (or more) staged atom in `~/.dharma/knowledge/staging/<today>/`. **Staged atoms are NOT trusted** — they require `/chetana-promote` (which routes through the dharma telos gates) before entering the wiki.

Report back: the staged file path(s), the kind used, and the reminder that it's staged-not-trusted. If ingest fails (unreadable source, MarkItDown missing), report the actual error — never claim an atom was staged without a path that exists.

Do not promote in the same breath — ingest and promote are deliberately separate steps.
