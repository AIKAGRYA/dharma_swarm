# Governance Hygiene

This folder is the single home for vibe-code, anti-slop, and AI-agent hygiene
signals that are broader than the hard rules in
`docs/governance/ANTI_SLOP_RULES.md`.

The contract is lifecycle first, not prose first:

- `patterns/*.yaml` is the source of truth. Each file has a stable id,
  lifecycle stage, detector, audit questions, and optional enforcement rule.
  `VC-*` records cover code-quality antipatterns. `AI-*` records cover
  agent-governance failure modes.
- `CATALOGUE.md` and `AUDIT_PROMPT.md` are generated from those pattern files.
- `baselines/` stores dated non-blocking scan outputs.
- `archive/` keeps retired pattern ids available for old citations.
- `FITNESS_FUNCTIONS.md` registers executable architecture invariants that run
  continuously in CI and local pytest.

Run:

```bash
make hygiene-check
make hygiene-audit
```

Add a new finding by copying the nearest pattern file, assigning the next stable
id in its namespace and cluster, and regenerating:

```bash
python3 scripts/governance/hygiene/audit_agent_prompt.py --write
make hygiene-check
```

Promotion to a hard gate happens only after the lifecycle criteria in
`LIFECYCLE.md` are met. Until then, scan output is advisory evidence for review,
not a merge blocker.

## AI-Agent Governance Tranche

The `AI-*` records encode repo hygiene hazards that are specific to coding
agents: trusted instruction boundaries, fake verification, same-PR gate
weakening, dependency provenance, task admission, prompt and memory poisoning,
gate gaming, architecture-budget drift, high-risk comprehension, multi-agent
independence, simplification rewards, and maintainer-burden control.

Read [`AI_AGENT_GOVERNANCE.md`](AI_AGENT_GOVERNANCE.md) for the merge-facing
doctrine. Merge Master Mike should treat these as final-gate hygiene questions:
green CI is necessary, but not enough, when an AI-generated patch increases
authority, dependency, memory, architecture, or review burden.

## Source Bibliography

The initial `VC-*` pattern set comes from the 2026-06-07 vibe-code antipattern
field guide and baseline scan prepared for this repo. The initial `AI-*` pattern
set is grounded in NIST SSDF / SP 800-218A, OWASP LLM and MCP risk catalogues,
package-hallucination research, empirical LLM-code-security work, AI
productivity studies in mature repositories, and maintainer-economics research
on vibe coding. Pattern files cite concrete sources until a signal is promoted
or externally revalidated.
