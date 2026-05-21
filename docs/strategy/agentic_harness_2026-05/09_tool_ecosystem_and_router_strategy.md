# 09 Tool Ecosystem And Router Strategy

Expert lens: large-codebase context strategist.
Local grounding: written after reading the 33-file local evidence base in `00_local_evidence_base.md`.
External grounding: Augment, Qodo, Sourcegraph Cody, Greptile, Cursor cloud agents, GitHub Copilot cloud agent, Claude Code MCP/subagents, OpenAI Agents SDK.

## Core Claim

No single context tool should become Dharma Swarm's brain. The router should use multiple imperfect tools according to task shape, cost, freshness, and trust level.

The core stack should be local-first and paid-tool-optional.

## Default Tool Order

Entrypoint:

- `make onboard`
- active track
- broken register

Exact local evidence:

- `rg`
- file reads
- tests
- git diff/log

Structural local intelligence:

- GitNexus
- Context+
- AST tools

Repo and PR state:

- GitHub CLI or GitHub app
- Actions logs
- branch/worktree status

Semantic external context:

- Context7 for library docs.
- official vendor docs.
- web only when current facts are needed.

Optional massive-context/code intelligence:

- Augment Context Engine MCP.
- Qodo Context Engine.
- Sourcegraph/Cody if provisioned.
- Greptile for PR review.
- Cursor/GitHub/Codex cloud agents for isolated delegated PRs.
- future SubQ-like provider as another quorum source, not a foundation.

## Tool Roles

Augment:

- Use for active development when local real-time indexing is available.
- Best for semantic and relationship-aware retrieval across code, commits, docs, tickets, and tribal knowledge.
- Watch cost per query.

Qodo:

- Use for deep implementation research, multi-file planning, impact questions, and architecture comparison.
- Good fit for a "second opinion" on complex changes.

Sourcegraph/Cody:

- Use when Enterprise access exists or self-hosted Sourcegraph is provisioned.
- Strong for repository-wide search and `@`-scoped context.
- Do not block Dharma Swarm on expensive enterprise access.

Greptile:

- Use as PR review and team preference learning layer.
- Good for post-diff review, not initial local exploration.

Cursor/GitHub/OpenAI/Claude cloud agents:

- Use for branch-isolated implementation tasks that can produce PRs, logs, and artifacts.
- Avoid for protected measurement changes unless policy is explicit.

GitNexus/Context+/rg:

- Keep central because they work locally, are cheap, and can be included in onboarding.

## Router Policy

Route by question:

- "Where is this exact thing?" use `rg`.
- "What depends on this symbol?" use GitNexus or AST.
- "What is the architecture around this?" use Context+ or Qodo/Augment.
- "What do current vendor docs say?" use Context7 or official docs.
- "Is this PR safe?" use tests, CI, Greptile if configured, and a human reviewer.
- "Can an agent implement this in isolation?" use cloud/background agent with branch and artifacts.

## Anti-Hallucination Rule

Agents may not claim a tool was checked unless there is a receipt. A receipt can be:

- command output saved in run state.
- MCP response artifact.
- URL and access timestamp.
- CI run URL.
- context manifest entry.

## Immediate Move

Make a `tool_registry.json` that records availability, cost, auth state, trust level, and best use. Do not install every tool globally. Broken MCP handshakes are worse than absent tools because they waste agent startup attention.
