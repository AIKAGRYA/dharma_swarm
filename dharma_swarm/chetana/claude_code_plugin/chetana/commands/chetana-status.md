---
description: Show chetana memory state — staged / trusted / quarantine counts.
---

Run `python -m dharma_swarm.chetana.cli status` using the chetana python (resolve per the chetana SKILL.md: dev-worktree venv → repo `.venv` → `python3` + PYTHONPATH; first one that can `import dharma_swarm.chetana` wins).

Print the CLI output as-is — do not paraphrase or reformat the counts.

Expected output shape: counts for staged / trusted / quarantined atoms plus last-capture info. Zero counts everywhere on a fresh machine is a valid state, not an error.

If chetana isn't importable in any known python, say exactly that and point the user at `cd ~/dharma_chetana && pip install -e ".[mcp,dev]"`. Do not invent counts and do not report "no atoms" when the real problem is a missing install.
