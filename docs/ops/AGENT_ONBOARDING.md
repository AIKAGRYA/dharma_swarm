# Agent Onboarding

This is the generic first stop for any new agent entering `dharma_swarm`. It ties live tool status, codebase context tools, governance, active build tracks, and persistent-agent state into one route.

Start here:

```bash
cd ~/dharma_swarm
make onboard
```

`make onboard` is read-only. It prints the live Codex/MCP toolbelt status, branch/dirty-tree state, and links to the highest-value docs.

GitHub-only agents cannot see local credentials, `dkeys`, or live process environment. Do not conclude "no LLM provider is configured" from repository contents alone; that claim requires a current local `make onboard`, `dkeys list`, `python -m dharma_swarm.api_key_audit --no-agentic`, or `/api/chat/status` check from the operator machine.

## First Five Minutes

Read in this order:

1. [`CLAUDE.md`](../../CLAUDE.md): repo behavior, engineering rules, architecture summary, build/test commands.
2. [`CODEX_TOOLBELT_ONBOARDING.md`](CODEX_TOOLBELT_ONBOARDING.md): large-codebase context tools, MCP health, Sourcegraph/GDrive/Postgres gates, Sourcebot lane.
3. [`BUILD_SESSION_ENTRYPOINT.md`](../governance/BUILD_SESSION_ENTRYPOINT.md): mandatory build-session read order and current active track.
4. [`MEGAFILE_INDEX.md`](../MEGAFILE_INDEX.md): the ten durable onboarding surfaces.
5. The task-specific row below that matches the work you are doing.

Do not read the whole repo. Pick the smallest route that gives you evidence.

## Context Tool Stack

Use this stack before inventing a new search/indexing path:

| Need | First tool | When blocked |
|---|---|---|
| Local code graph, impact, call paths | GitNexus MCP | run `npx gitnexus analyze`, then retry |
| Semantic repo navigation | Context+ MCP | use `rg` plus targeted file reads |
| Exact text/evidence | `rg` | `git grep`, then `find`/`grep` |
| Repo/PR/issue/CI state | GitHub MCP or `gh` | local `git` if remote is unavailable |
| Current library/API docs | Context7 MCP | official docs only |
| Public-code search | `/Users/dhyana/.local/bin/src search 'context:global ...'` | web search |
| Sourcegraph-like self-hosted search | Sourcebot, if running | GitNexus + Context+ |
| Google Drive docs | GDrive MCP, after auth | ask operator for local copies |
| SQL/schema inspection | Postgres MCP, after DSN | SQLite/read-only local probes |

Sourcegraph Enterprise MCP is not a dependency. Sourcegraph, GDrive, and Postgres MCPs were removed from global Codex config because they were unprovisioned and caused repeated scout startup warnings. Re-add them only through the gates in [`CODEX_TOOLBELT_ONBOARDING.md`](CODEX_TOOLBELT_ONBOARDING.md).

## Task Routes

| Task | Read these first |
|---|---|
| Any code change | [`BUILD_SESSION_ENTRYPOINT.md`](../governance/BUILD_SESSION_ENTRYPOINT.md), [`SOVEREIGN_MANIFEST.md`](../governance/SOVEREIGN_MANIFEST.md), [`000_MASTER_COHERENCE_SYNTHESIS.md`](../../reports/audit/end_to_end/000_MASTER_COHERENCE_SYNTHESIS.md), [`CANONICAL_DOC_STACK.md`](../governance/CANONICAL_DOC_STACK.md) |
| Architecture/navigation | [`NAVIGATION.md`](../architecture/NAVIGATION.md), [`MEGAFILE_INDEX.md`](../MEGAFILE_INDEX.md), GitNexus/Context+ |
| Runtime wiring or bugfix | [`INTERFACE_MISMATCH_MAP.md`](../../INTERFACE_MISMATCH_MAP.md), [`CYBERNETIC_LOOP_MAP.md`](../../CYBERNETIC_LOOP_MAP.md), relevant tests |
| Current live state | [`LIVE_OPS_DASHBOARD.md`](../state/LIVE_OPS_DASHBOARD.md), [`BROKEN_REGISTER.md`](../state/BROKEN_REGISTER.md), `~/.dharma` evidence |
| Active build track | [`ONTOLOGY_NATIVE_OPERATOR_BRIEF_MASTER_SPEC.md`](../plans/ONTOLOGY_NATIVE_OPERATOR_BRIEF_MASTER_SPEC.md), [`NEXT_10_SUBSTRATE_TODO.md`](../plans/NEXT_10_SUBSTRATE_TODO.md), [`HANDOFF_ONTOLOGY_NATIVE_OPERATOR_BRIEF.md`](../plans/HANDOFF_ONTOLOGY_NATIVE_OPERATOR_BRIEF.md) |
| Persistent agents | Check the current branch for `docs/agents/` and `docs/research/persistent_agents*/`; if absent, ask the operator for the latest packet rather than inventing L4 readiness claims. |
| Docs or governance edits | [`CANONICAL_DOC_STACK.md`](../governance/CANONICAL_DOC_STACK.md), [`REPO_GOVERNANCE_AUDIT.md`](../governance/REPO_GOVERNANCE_AUDIT.md) |
| Doctrine/telos | [`OPERATIONAL_DOCTRINE.md`](../doctrine/OPERATIONAL_DOCTRINE.md), [`LIVE_ROADMAP.md`](../doctrine/LIVE_ROADMAP.md), [`SOVEREIGN_MANIFEST.md`](../governance/SOVEREIGN_MANIFEST.md) |
| Foundations/glossary | [`foundations/INDEX.md`](../../foundations/INDEX.md), [`foundations/GLOSSARY.md`](../../foundations/GLOSSARY.md) |

## Non-Negotiables

- Do not revert changes you did not make.
- Do not add new runtime substrates when canonical substrates already exist.
- Do not add top-level docs or source files.
- Do not claim an agent is L4 unless the readiness evidence proves it.
- Do not print secret values. Report only presence/absence of keys or credential files.
- Do not re-enable optional MCPs globally unless their gates are green.

## Large-Codebase Work Pattern

1. Run `make onboard`.
2. Identify the task route above.
3. Use GitNexus or Context+ for structure before reading many files.
4. Use `rg` for exact evidence.
5. Before modifying a shared symbol, check impact/blast radius.
6. Make the smallest scoped change.
7. Run the relevant test or read-only status script.
8. Update the owning doc only if the change alters durable truth.

## Handoff Prompt

Use this for a new Codex agent:

```text
Repo: /Users/dhyana/dharma_swarm

Start by running:

cd /Users/dhyana/dharma_swarm
make onboard

Read `docs/ops/AGENT_ONBOARDING.md`, then follow the task route that matches the assignment.

Use GitNexus + Context+ + rg as the default large-codebase context stack. Treat Sourcegraph, GDrive, and Postgres MCPs as optional and removed unless their gates in `docs/ops/CODEX_TOOLBELT_ONBOARDING.md` are green.

Never print secrets. Do not revert user or other-agent changes. Do not add new substrates before checking `docs/governance/BUILD_SESSION_ENTRYPOINT.md` and `reports/audit/end_to_end/000_MASTER_COHERENCE_SYNTHESIS.md`.
```
