# Agent Onboarding

This is the generic first stop for any new agent entering `dharma_swarm`. It ties live tool status, codebase context tools, governance, active build tracks, and persistent-agent state into one route.

Start here:

```bash
cd ~/dharma_swarm
make onboard
```

`make onboard` is read-only session status. It reports the current
checkout/toolchain verdict and a local GitNexus observation (CLI vs pin
1.6.9, MCP wiring, index meta vs HEAD). It never runs `analyze`, never
opens LadybugDB, and never claims a live MCP handshake. It is not edit
admission or whole-organism orientation. Host pin/repair is
`make gitnexus-ensure`; reindex is `gitnexus analyze --skip-agents-md`.

For Fable 5 / `fable_5_cursor`, read
[`FABLE5_ONBOARDING_MAP.md`](FABLE5_ONBOARDING_MAP.md) only after this
command and the first-read surfaces it names. That map is an operational
route for a specific hub-coordinator identity; it is not a new authority
surface.

Packet-bound preflight and closeout are required when changed paths match Merge
Master Mike's `HOT_PATH_PATTERNS` in `scripts/runtime/pr_merge_control.py`; they
are optional otherwise. A narrower lane or campaign contract may require them
more broadly. When a packet is required or voluntarily used, use these targets
around the actual implementation work:

```bash
make agent-build-preflight PACKET=<path>
# make the smallest scoped change and run the task-specific test
make agent-build-closeout PACKET=<path>
```

Both commands require the same exact Session Entry packet. Preflight binds the
baseline and allowed scope; closeout verifies the resulting scope and runs the
governance bundle. `make onboard` alone is session status, not proof that the
build is admitted or complete.

GitHub-only agents cannot see local credentials, `dkeys`, or live process environment. Do not conclude "no LLM provider is configured" from repository contents alone; that claim requires a current local `make onboard`, `dkeys list`, `python -m dharma_swarm.api_key_audit --no-agentic`, or `/api/chat/status` check from the operator machine.

## First Five Minutes

Read in this order:

1. `make onboard` output: live branch, active tracks, dirty tree, stale docs, and next command.
2. [`CLAUDE.md`](../../CLAUDE.md): repo behavior, engineering rules, architecture summary, build/test commands.
3. [`SWARM_GENOME.md`](../governance/SWARM_GENOME.md): compact first-token map and claim-language guard. Per [`CANONICAL_DOC_STACK.md`](../governance/CANONICAL_DOC_STACK.md)'s first-read list, this is the forced first-read surface; `SOVEREIGN_MANIFEST.md` remains the deeper architecture/doctrine authority but is depth-on-demand, not forced.
4. [`ACTIVE_TRACK.yaml`](../governance/ACTIVE_TRACK.yaml): current build portfolio and owned surfaces.
5. [`ANTI_SLOP_RULES.md`](../governance/ANTI_SLOP_RULES.md): hard and advisory anti-slop gates.

Everything else is depth-on-demand. [`CANONICAL_DOC_STACK.md`](../governance/CANONICAL_DOC_STACK.md)
owns this first-read rule; if this section drifts, that file wins.

Do not read the whole repo. Pick the smallest route that gives you evidence.

## Context Tool Stack

Use this stack before inventing a new search/indexing path:

| Need | First tool | When blocked |
|---|---|---|
| Local code graph, impact, call paths | GitNexus MCP (`make gitnexus-status`) | `make gitnexus-ensure`, then `gitnexus analyze --skip-agents-md` |
| Semantic repo navigation | Context+ MCP | use `rg` plus targeted file reads |
| Exact text/evidence | `rg` | `git grep`, then `find`/`grep` |
| Repo/PR/issue/CI state | GitHub MCP or `gh` | local `git` if remote is unavailable |
| Current library/API docs | Context7 MCP | official docs only |
| Public-code search | `/Users/dhyana/.local/bin/src search 'context:global ...'` | sourcegraph.com/search |
| This repo on Sourcegraph | workspace `SRC_ENDPOINT` after Starter clone | GitNexus + `rg` |
| Sourcegraph-like self-hosted search | Sourcebot, if running | GitNexus + Context+ |
| Google Drive docs | GDrive MCP, after auth | ask operator for local copies |
| SQL/schema inspection | Postgres MCP, after DSN | SQLite/read-only local probes |

Sourcegraph Enterprise MCP is not a dependency. Sourcegraph, GDrive, and Postgres MCPs were removed from global Codex config because they were unprovisioned and caused repeated scout startup warnings. Re-add them only through the gates in [`CODEX_TOOLBELT_ONBOARDING.md`](CODEX_TOOLBELT_ONBOARDING.md).

GitNexus, Context+, Context7, Sourcebot, and the `/Users/dhyana/.local/bin/src` binary are Mac-operator-machine tools. They may be absent for cloud/web/GitHub-only agents; fall back to `rg`/`git grep`, official docs, or web search per the table above rather than treating their absence as a failure.

## Task Routes

| Task | Read these first |
|---|---|
| Any code change | [`BUILD_SESSION_ENTRYPOINT.md`](../governance/BUILD_SESSION_ENTRYPOINT.md), [`SOVEREIGN_MANIFEST.md`](../governance/SOVEREIGN_MANIFEST.md), [`000_MASTER_COHERENCE_SYNTHESIS.md`](../../reports/audit/end_to_end/000_MASTER_COHERENCE_SYNTHESIS.md), [`CANONICAL_DOC_STACK.md`](../governance/CANONICAL_DOC_STACK.md) |
| Architecture/navigation | [`NAVIGATION.md`](../architecture/NAVIGATION.md), [`MEGAFILE_INDEX.md`](../MEGAFILE_INDEX.md), GitNexus/Context+ |
| Runtime wiring or bugfix | [`INTERFACE_MISMATCH_MAP.md`](../../INTERFACE_MISMATCH_MAP.md), [`CYBERNETIC_LOOP_MAP.md`](../../CYBERNETIC_LOOP_MAP.md), relevant tests |
| Current live state | [`LIVE_OPS_DASHBOARD.md`](../state/LIVE_OPS_DASHBOARD.md), [`BROKEN_REGISTER.md`](../state/BROKEN_REGISTER.md), `~/.dharma` evidence |
| Active build track | [`ACTIVE_TRACK.yaml`](../governance/ACTIVE_TRACK.yaml), [`active_track_evidence.md`](../../reports/governance/active_track_evidence.md), current `make onboard` output |
| Persistent agents | Check the current branch for `docs/agents/` and `docs/research/persistent_agents*/`; if absent, ask the operator for the latest packet rather than inventing L4 readiness claims. |
| Joining the A2A fleet as a NEW persistent identity | `make agent-register`, [`A2A_AGENT_ONBOARDING.md`](A2A_AGENT_ONBOARDING.md), [`A2A_QUICKSTART.md`](A2A_QUICKSTART.md) |
| Fable 5 hub coordination | [`FABLE5_ONBOARDING_MAP.md`](FABLE5_ONBOARDING_MAP.md), `examples/agents/fable_5_cursor.registration.json`, current `make onboard` output |
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
8. When a packet is required or voluntarily used, run
   `make agent-build-closeout PACKET=<path>` before PR handoff.
9. Update the owning doc only if the change alters durable truth.

## Handoff Prompt

Use this for a new Codex agent:

```text
Repo: <repo-root>
(substitute the local checkout path, e.g. /Users/dhyana/dharma_swarm on the operator Mac)

Start by running:

cd <repo-root>
make onboard

Read `docs/ops/AGENT_ONBOARDING.md`, then follow the task route that matches the assignment.

Use GitNexus + Context+ + rg as the default large-codebase context stack. Treat Sourcegraph, GDrive, and Postgres MCPs as optional and removed unless their gates in `docs/ops/CODEX_TOOLBELT_ONBOARDING.md` are green.

Never print secrets. Do not revert user or other-agent changes. Do not add new substrates before checking `docs/governance/BUILD_SESSION_ENTRYPOINT.md` and `reports/audit/end_to_end/000_MASTER_COHERENCE_SYNTHESIS.md`.
```
