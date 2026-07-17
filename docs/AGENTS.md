# Documentation Agent Instructions

**Scope:** AI agents (any brand) working in the prose layer — `docs/`,
`reports/`, `specs/`, `foundations/`, `lodestones/`, root Markdown. Repo-wide
behaviour, the onboarding status command, and its trust boundaries are
owned by `CLAUDE.md`; this file adds only prose-layer rules. Root `/AGENTS.md`
is the tracked minimal entrypoint; this file owns the prose-layer instructions.

Run `make onboard` before touching any doc. Its output is a read-only projection over fact owners, never a replacement:
on conflict, owner files win and the projection/generator must be repaired. Do not rewrite an owner to match generated output.
Memory/context work goes through MemoryKernel — see `CLAUDE.md` §Key Abstractions.

## Authority Model

Do not infer authority from confident language.
Authority comes from `docs/governance/CANONICAL_DOC_STACK.md`.

Only these files may make repo-level authority claims:

- `CLAUDE.md` for agent behavior.
- `docs/governance/SOVEREIGN_MANIFEST.md` for architecture, domains, invariants, and measured repo state.
- `docs/governance/CANONICAL_DOC_STACK.md` for document hierarchy and ownership.
- `docs/governance/BUILD_SESSION_ENTRYPOINT.md` for the stable boundary between
  session status, edit admission, closeout, CI, and agent registration.
- `docs/governance/REPO_GOVERNANCE_AUDIT.md` for contradictions and staleness.

All other docs must declare a narrower role: reference, plan, report, witness, archive, research, or experiment.

## Document Types

Use these roles when classifying or creating docs:

- `canon`: durable authority named in the canonical stack.
- `ADR`: one accepted, proposed, superseded, or rejected decision.
- `active_spec`: implementation-driving contract for current work.
- `working_plan`: bounded execution plan or handoff.
- `report`: dated descriptive output.
- `witness`: falsifiability artifact with captured evidence.
- `reference`: useful background that is not operational authority.
- `archive`: retained history, not current instruction.
- `experiment`: explicitly bounded exploration with no runtime authority.

Do not let one file play more than one authority role.

## Cleanup Rules

- Prefer updating or demoting an existing doc over creating a new one.
- If creating a new doc, state which existing doc it replaces or subordinates to.
- If a doc is stale, mark the replacement and owner before moving or deleting it.
- Generated artifacts must be indexed as generated artifacts, not promoted into doctrine.
- Plans and reports must not become product truth by repetition.
- Root docs are exceptional. New root Markdown needs explicit justification.

## Deprecation Format

When demoting a doc, use this information in the target owner or audit log:

```text
Deprecated: YYYY-MM-DD
Reason:
Replacement:
Review / removal date:
```

Do not silently delete historical context.

## Agent-To-Agent Semantic Experiments

Compressed AI-to-AI code language is allowed only as an experiment until it is proven human-decodable.

Rules:

- The experiment must live under `reports/` or `docs/plans/`, not in runtime state or canon.
- Every symbol set must include a human-readable legend.
- Every compact message must round-trip to plain English in tests or witness evidence before reuse.
- The compact layer must sit below docs, never replace docs.
- No opaque token language may control runtime behavior, gate decisions, commits, or state mutation.
- Candidate semantic ontologies discovered during cleanup are observations first. They may become ADRs or specs only after review.

This preserves the benefit of machine-native coordination without creating an unreviewable shadow doctrine.
