---
description: Render the memory palace — 10 pillar rooms + 5 system rooms as JSON Canvas.
---

Run `python -m dharma_swarm.chetana.cli palace` using the chetana python (resolution order in the chetana SKILL.md).

Output is written to `~/.dharma/knowledge/memory_palace.canvas` (kepano's open JSON Canvas spec — open in Obsidian or any Canvas-capable tool to navigate atoms by pillar).

Rooms:
- **Pillar rooms (10)**: Levin, Kauffman, Jantsch, Deacon, Friston, Hofstadter, Aurobindo, Dada Bhagwan, Varela, Beer
- **System rooms (5)**: Telos (Jagat Kalyan), R_V Research, Phoenix, Foundations, Operations

After the run: confirm the `.canvas` file exists and report its path plus a one-line summary (how many atoms placed, any room left empty). An empty room is worth naming — it usually marks a pillar with no trusted atoms yet, which is a gap-scan lead.

Do not hand-edit the `.canvas` file; re-render instead.
