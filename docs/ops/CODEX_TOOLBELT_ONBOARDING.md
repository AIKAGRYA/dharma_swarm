# Codex Toolbelt Onboarding

Parent entrypoint: [`AGENT_ONBOARDING.md`](AGENT_ONBOARDING.md). Use this file for Codex/MCP tool routing details after running `make onboard`.

Purpose: get a new Codex agent oriented to the local code-intelligence stack without paying for Sourcegraph Enterprise or rediscovering known MCP startup failures.

## First Minute

```bash
cd ~/dharma_swarm
bash scripts/runtime/codex_toolbelt_status.sh
sed -n '1,220p' docs/ops/CODEX_TOOLBELT_ONBOARDING.md
```

If the status script says `sourcegraph`, `gdrive`, or `postgres` are not globally configured, that is intentional. They are optional and must not be added back until their gates below are satisfied.

## Current Truth

- Sourcegraph MCP is not a default individual-user dependency. Sourcegraph's public MCP endpoint exists, but Sourcegraph's current pricing/docs place full MCP/API/CLI access under Enterprise. Do not make dharma_swarm depend on it.
- `make onboard` reports a local Sourcegraph observation only: CLI present/missing, `SRC_ENDPOINT` kind, token presence. It never searches, never claims `dharma_swarm` is indexed, and never prints token values.
- `make onboard` also reports a local GitNexus observation: CLI vs pin 1.6.9, MCP wiring, index meta vs HEAD. It never runs `analyze` and never claims a live MCP handshake. Host pin is `make gitnexus-ensure`.
- Sourcegraph public code search still works through `/Users/dhyana/.local/bin/src search ...` against `context:global`. That index does **not** include `AIKAGRYA/dharma_swarm`. Workspace/private search needs Enterprise Starter at `workspaces.sourcegraph.com`, then `SRC_ENDPOINT` pointing at `*.sourcegraph.app` and `src login`.
- GDrive MCP is individual-accessible, but this machine is missing OAuth client JSON and saved credentials.
- Postgres MCP is local-infra only, but this machine currently has no configured DSN and no always-on database target.
- Sourcebot is the realistic self-hosted Sourcegraph-like path. Treat it as optional until a local instance and `SOURCEBOT_API_KEY` are present.
- Provider/API-key truth is local operator state. GitHub-only agents cannot infer it from the repository. Use local non-secret status commands before claiming the runtime has no usable LLM provider.

## Provider Key Reality

`dkeys` is a local helper outside this repo, usually at `~/.dharma/bin/dkeys`. Its canonical key store is `~/.dharma/agent_keys.env`, and its cache is `~/.dharma/keys_status.json`. Neither file belongs in git.

Safe local checks:

```bash
dkeys list
python -m dharma_swarm.api_key_audit --no-agentic
curl -s http://127.0.0.1:8420/api/chat/status
```

Never print key values. Report only provider presence, live/probe status, and whether a failure is auth, quota/funds, provider retirement, or network/sandbox.

Known naming mismatch to watch:

- `dkeys` tests Gemini with `GEMINI_API_KEY`; dharma runtime uses `GOOGLE_AI_API_KEY`.
- `dkeys` tests hosted NVIDIA with `NVIDIA_API_KEY`; dharma runtime uses `NVIDIA_NIM_API_KEY`.

If a remote GitHub-only audit says "no configured LLM provider," treat it as stale unless it also cites a current `make onboard`, `dkeys`, runtime audit, or `/api/chat/status` result from the operator machine.

## Default Tool Routing

Use this routing before reaching for paid/external tools:

| Need | Primary path | Fallback |
|---|---|---|
| Local code graph, impact, call paths | GitNexus MCP (`make gitnexus-status`) | `make gitnexus-ensure`, then `gitnexus analyze --skip-agents-md` |
| Semantic repo navigation | Context+ MCP | `rg`, `sed`, targeted file reads |
| Exact local evidence | `rg` | `find`, `grep` |
| Repo/PR/issue state | GitHub MCP or `gh` | `git` local state |
| Library/API docs | Context7 MCP | official web docs |
| Public-code search | `/Users/dhyana/.local/bin/src search 'context:global repo:github.com/sourcegraph/src-cli ...'` | sourcegraph.com/search |
| This repo on Sourcegraph | workspace `SRC_ENDPOINT` + cloned repo | GitNexus + `rg` |
| Sourcegraph-like local search | Sourcebot when running | GitNexus + Context+ |
| Google Drive docs | GDrive MCP only after auth | ask operator for files |
| SQL schema/data | Postgres MCP only after DSN | SQLite/read-only local probes |

## Removed MCPs

These were removed from global Codex config on 2026-05-21 because they caused repeated handshake failures in every spawned scout:

```bash
codex mcp remove sourcegraph
codex mcp remove gdrive
codex mcp remove postgres
```

The removals are operational hygiene, not a rejection of the tools. Re-add only when the matching gate is green.

## Re-Add Gates

### Sourcegraph

Do not re-add for normal dharma_swarm work. Re-add only if one of these is true:

- the operator has an Enterprise/team Sourcegraph account with MCP entitlement;
- `codex mcp login sourcegraph --scopes mcp` succeeds;
- an MCP-scoped access token is available and verified without printing it.

Preferred OAuth command if entitlement exists:

```bash
codex mcp add sourcegraph --url https://sourcegraph.com/.api/mcp
codex mcp login sourcegraph --scopes mcp
```

Do not depend on `SRC_ACCESS_TOKEN` unless the token scheme is verified with Sourcegraph's current MCP auth behavior.

### GDrive

Re-add only after both files exist:

```bash
ls ~/.codex/memories/gcp-oauth.keys.json
ls ~/.codex/memories/gdrive-credentials.json
```

Auth flow:

```bash
/Users/dhyana/.codex/mcp-lab/bin/run-gdrive-mcp.sh auth
codex mcp add gdrive -- /Users/dhyana/.codex/mcp-lab/bin/run-gdrive-mcp.sh
```

### Postgres

Re-add only after a live target exists and one of these is present:

```bash
echo 'postgresql://localhost:5432/dbname' > ~/.codex/memories/postgres-url.txt
# or export MCP_POSTGRES_URL in the shell that launches Codex
```

Then:

```bash
codex mcp add postgres -- /Users/dhyana/.codex/mcp-lab/bin/run-postgres-mcp.sh
```

### Sourcebot

Sourcebot is the replacement lane for a self-hosted Sourcegraph-like index. Do not make it required until Docker/Colima is running and an API key exists.

Expected MCP shape:

```bash
export SOURCEBOT_API_KEY='<redacted>'
codex mcp add sourcebot --url http://localhost:3000/api/mcp --bearer-token-env-var SOURCEBOT_API_KEY
```

Use `bash scripts/runtime/codex_toolbelt_status.sh` to see whether the local endpoint is reachable.

## New Agent Prompt

Use this at the start of code-intelligence-heavy sessions:

```text
Before using MCPs, run `bash scripts/runtime/codex_toolbelt_status.sh` in `~/dharma_swarm`.
Treat Sourcegraph MCP, GDrive MCP, and Postgres MCP as optional: do not re-add them unless their documented gates in `docs/ops/CODEX_TOOLBELT_ONBOARDING.md` are green.
For local code intelligence, use GitNexus + Context+ + rg first.
For public-code search, use `/Users/dhyana/.local/bin/src search 'context:global ...'`.
Do not treat `context:global` as a search of this checkout.
Never print token values; report only whether required env vars/files are present.
```

## Public search (the `context:global` UI)

The Sourcegraph.com search bar with `context:global` searches Sourcegraph's public OSS index. It is not this checkout.

Examples:

```bash
src search 'context:global repo:^github\.com/sourcegraph/src-cli$ NewArchiveRegistry'
src search 'context:global lang:python "class SwarmManager"'
src search 'context:global type:symbol CreateRuntimeProvider'
```

Same queries work in the web UI. `repo:` must match a repository Sourcegraph already indexed. `AIKAGRYA/dharma_swarm` is not in that index.

After a Starter workspace has cloned the repo, point `src` at the workspace instead of sourcegraph.com:

```bash
# durable endpoint (not a secret); OAuth stays in macOS keychain
printf '%s\n' 'SRC_ENDPOINT=https://aikagrya.sourcegraph.app' > ~/.dharma/sourcegraph.env
export SRC_ENDPOINT=https://aikagrya.sourcegraph.app
src login https://aikagrya.sourcegraph.app
src search 'repo:^github\.com/AIKAGRYA/dharma_swarm$ SwarmManager'
```

`make onboard` reads `~/.dharma/sourcegraph.env` and reports `search_scope: workspace_capable` when the CLI and keychain login exist. It still does not claim the repo is indexed.

## Failure Pattern To Recognize

If a swarm spawn prints repeated warnings like:

```text
MCP client for sourcegraph failed to start
MCP client for gdrive failed to start
MCP client for postgres failed to start
```

that usually means optional unprovisioned MCPs are globally configured. It is not evidence that the whole MCP stack is broken. Remove the unprovisioned entries, restart Codex, then rely on GitNexus, Context+, GitHub, Context7, fetch, memory, and local shell tools.
