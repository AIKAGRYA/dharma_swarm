# Governance

This document indexes the concise operational policy for hygiene gates.

## Hygiene Policy

- [QUALITY_GATES.md](/Users/dhyana/dharma_swarm/docs/governance/QUALITY_GATES.md)
  owns the Dharmic Hygiene Mesh gate contract: Python target, package target,
  report filenames, modes, budgets, and advisory/blocking ratchet.
- [docs/governance/ANTI_SLOP_RULES.md](/Users/dhyana/dharma_swarm/docs/governance/ANTI_SLOP_RULES.md)
  owns Dharma-specific anti-slop rule descriptions and promotion notes.
- [docs/governance/CI_GATES.md](/Users/dhyana/dharma_swarm/docs/governance/CI_GATES.md)
  owns existing CI security gate policy for CodeQL, Semgrep, and Gitleaks.
- [docs/governance/PROMPT_GOVERNANCE.md](/Users/dhyana/dharma_swarm/docs/governance/PROMPT_GOVERNANCE.md)
  owns the rule that external LLM prompts must become validated prompt packs
  before agents can run them as cleanup lanes.

Use this document as an index and coherence surface. Do not duplicate detailed
rule bodies here when another `docs/governance/` document owns them.
