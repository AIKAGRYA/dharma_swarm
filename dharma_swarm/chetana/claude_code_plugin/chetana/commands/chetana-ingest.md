---
description: Capture raw content (note / webclip / pdf / session / voice) into a staged atom.
argument-hint: "<source-path-or-text> [--kind ...] [--title ...] [--tag ...]"
---

Run `python -m dharma_swarm.chetana.cli ingest $ARGUMENTS` using the chetana venv.

The result is one (or more) staged atom in `~/.dharma/knowledge/staging/<today>/`. Staged atoms are NOT trusted — they require `chetana promote` (which routes through the dharma telos gates) before entering the wiki.

Source kinds:
- `note` — inline text or markdown file
- `webclip` — Obsidian Web Clipper output
- `pdf` — passes through MarkItDown
- `session` — Claude Code JSONL transcript
- `voice` — voice memo (routes through MarkItDown)
- `external` — anything else
