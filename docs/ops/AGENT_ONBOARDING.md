# Agent Onboarding

This is the generic first stop for any new agent entering `dharma_swarm`. It ties live tool status, codebase context tools, governance, active build tracks, and persistent-agent state into one route.

Product center: `dharma_swarm` is a telos-gated DGM Goodworks Intelligence Core: agent-first infrastructure for verifiable welfare, ecological MRV, and regenerative coordination.

Default assumption: do not build a generic agent framework. Reuse the existing DGM loop, Goodworks/GAIA ledgers, telos gates, context/wiki substrate, and governance checks before adding a runner, router, board, ledger, or orchestration layer.

Provider-key truth: the GitHub repo never contains API key values. A remote agent can only see env-var names and key-presence probes. If a local operator says `dkeys` is done, reconcile through local status surfaces (`/api/chat/status`, `dharma_swarm.api_key_audit`, `make onboard`, or the Goodworks dashboard); do not infer local provider readiness from GitHub alone.

Start here:

```bash
cd ~/dharma_swarm
make onboard
```

`make onboard` is read-only. It prints the live Codex/MCP toolbelt status, branch/dirty-tree state, and links to the highest-value docs.

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
| Active build track | `make onboard`, [`ACTIVE_TRACK.yaml`](../governance/ACTIVE_TRACK.yaml), [`COMMAND_PLANE_MULTIAGENT_PROTOCOL.md`](../plans/COMMAND_PLANE_MULTIAGENT_PROTOCOL.md), [`COMMAND_PLANE_CHECKLIST.md`](../plans/COMMAND_PLANE_CHECKLIST.md) |
| PGE autonomous build / long-running harness | [`PGE_AUTONOMOUS_BUILD_SYSTEM.md`](PGE_AUTONOMOUS_BUILD_SYSTEM.md), [`LONG_RUNNING_HARNESS.md`](LONG_RUNNING_HARNESS.md), [`COMMAND_PLANE_LONG_RUNNING_HARNESS_APPLICATION.md`](../plans/COMMAND_PLANE_LONG_RUNNING_HARNESS_APPLICATION.md), `scripts/runtime/long_running_harness.py`, `make long-harness-init GOAL="..." MODE=command-plane` |
| Strategy / coordination | [`agentic_harness_2026-05/00_index.md`](../strategy/agentic_harness_2026-05/00_index.md), [`strategy_librarian.registration.json`](../../examples/agents/strategy_librarian.registration.json), `~/.dharma/external_agents/strategy_librarian/CALL_CARD.md` |
| Persistent agents | [`PERSISTENT_AGENT_ONBOARDING_PACKET.md`](../agents/PERSISTENT_AGENT_ONBOARDING_PACKET.md), [`l4_readiness_report.md`](../research/persistent_agents_census_2026-05/l4_readiness_report.md), [`10_cultivation_architecture.md`](../research/persistent_agents_census_2026-05/10_cultivation_architecture.md) |
| Goodworks DGM / MRV | [`CLAUDE.md`](../../CLAUDE.md), [`WHAT_IT_WANTS_TO_BECOME.md`](../../WHAT_IT_WANTS_TO_BECOME.md), [`JAGAT_KALYAN_RECIPROCITY_COMMONS_2026-03-11.md`](../reports/JAGAT_KALYAN_RECIPROCITY_COMMONS_2026-03-11.md), [`GAIA_ECO_CONCEPTUAL_FRAMEWORK_2026-03-27.md`](../reports/GAIA_ECO_CONCEPTUAL_FRAMEWORK_2026-03-27.md), `dharma_swarm/goodworks_dgm/`, `scripts/runtime/goodworks_dgm_tick.py`, `scripts/runtime/seed_goodworks_mrv.py` |
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
- Do not claim local API keys are missing from repo evidence alone; remote agents do not have the operator's `dkeys` context.

## Large-Codebase Work Pattern

1. Run `make onboard`.
2. Identify the task route above.
3. Use GitNexus or Context+ for structure before reading many files.
4. Use `rg` for exact evidence.
5. Before modifying a shared symbol, check impact/blast radius.
6. Make the smallest scoped change.
7. Run the relevant test or read-only status script.
8. Update the owning doc only if the change alters durable truth.

## Context Quorum

For Q2+ code work, leave a machine-readable context receipt before the handoff:

```bash
make context-quorum-status
make context-quorum-init AGENT=repo_cartographer ROLE=repo-cartographer
make context-quorum-check AGENT=repo_cartographer RISK=Q2 QUESTION="what is being changed?"
make context-quorum-handoff AGENT=repo_cartographer SUMMARY="what changed and what remains"
```

Use `docs/ops/context_quorum_policy.json` as the protected-file and risk-level policy. Attach external receipt files for Context+, GitNexus, Qodo, Greptile, Augment, Sourcebot, Sourcegraph, or future SubQ-style tools instead of merely claiming they were checked.

## PGE Long-Running Harness

For multi-hour work, do not let one session plan, build, judge, and remember itself. Use the PGE autonomous-build standard and start a filesystem-backed Planner / Generator / Evaluator run:

```bash
make long-harness-init GOAL="Command-plane PR 2: context-dense operator shell" MODE=command-plane
make long-harness-status RUN_ID=<run-id>
make long-harness-validate RUN_ID=<run-id> PHASE=scaffold
```

The harness is not a daemon and not a new authority layer. It creates durable plan, contract, rubric, trace, progress, and handoff artifacts under `~/.dharma/harness_runs/`. For command-plane work, it applies after the current palette lane settles unless the operator explicitly reassigns file ownership.

Repo bridge: [`PGE_AUTONOMOUS_BUILD_SYSTEM.md`](PGE_AUTONOMOUS_BUILD_SYSTEM.md). External anchors: `~/.claude/projects/-Users-dhyana/memory/feedback_pge_harness_standard.md` and `~/.dharma/knowledge/wiki/concepts/pge-harness-pattern.md`.

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
