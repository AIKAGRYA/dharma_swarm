# 01 — Current State (live snapshot)

**Custody: VERIFIED 2026-07-06 via commands below. Re-run before trusting.**

This is the read-first "where are we right now" page. Numbers here are live
probes, not memory. Anything older than a day: re-run the commands.

## Repo pointer

- Checkout: `/Users/dhyana/dharma_swarm`
- Branch: `agent/magpie-seed`
- HEAD (this pass): `fdde37bad chore(gitignore): ignore generated runtime receipt exhaust`
- Prior brick: `f18fe8476 sarathi: add reversibility-gated wake brick`

## Working tree

`git status --short` = **17 entries** (was ~863 before the gitignore commit; the
generated receipt exhaust is now ignored, so the tree is legible again).

Tracked modified: only 3 generated governance report files
(`reports/governance/active_track_evidence.*`, `track_portfolio.json`).

Untracked of interest for THIS goal:

- `dharma_swarm/holon_system/` — new facade package (this pass).
- `tests/test_holon_system_imports.py` — facade proof test (this pass).

The rest of the untracked entries are other agents' in-flight work
(`docs/agent_tasks/*`, `specs/naga_ir/`, `telos_titanium/`, trust-forge scripts).
**Do not stage or revert those** — not this goal's scope (constraint #7).

## Fleet state — `dgc agent status --json`

Command:

```bash
.venv/bin/python -m dharma_swarm.dgc_cli agent status --json
```

Result: **17 agents registered, 0 service_alive.** Registration is identity;
liveness is receipts. Nothing is breathing as a standing service right now.

| Seat | model | registered | service_alive | heartbeat_seen | liveness |
|---|---|---|---|---|---|
| sarathi | gemini-2.5-flash | yes | no | no | unknown |
| hermes-m5 | gemini-2.5-flash | yes | no | no | unknown |
| codex_composer | gpt-5.5 | yes | no | yes | error |
| fable_composer | claude-fable-5 | yes | no | no | unknown |
| fugu_ultra | fugu-ultra | yes | no | no | unknown |

Known warning still emitted by the CLI:

```text
[holon] provider 'sakana' -> 'sakana' is not a valid ProviderType; defaulting to claude_code
```

That is the Fugu provider drift (proof gate 3).

## Runtime home counts (`~/.dharma`)

| Path | Count |
|---|---:|
| `~/.dharma/agents` | 67 |
| `~/.dharma/ginko/agents` | 52 (legacy registry, not the active home) |
| `~/.dharma/a2a/cards` | 49 |
| `~/.dharma/external_agents` | 26 |
| `~/.dharma/a2a_bus/inboxes` | 187 |
| `~/.dharma/a2a_bus/state` | 20 |
| `~/.dharma/a2a_bus/bridge_heartbeats` | 11 |
| `dharma_swarm/docs/agents` | 11 (repo docs, not runtime) |

Identity-home sprawl is real: `agents` (67) + `ginko/agents` (52) +
`docs/agents` (11) + `external_agents` (26) are four different homes.

## Sarathi runtime surfaces — still MISSING

```text
MISSING ~/.dharma/a2a_bus/state/sarathi.json
MISSING ~/.dharma/a2a_bus/inboxes/sarathi
MISSING ~/.dharma/a2a_bus/bridge_heartbeats/sarathi.json
MISSING ~/.dharma/agents/sarathi/gateway/sarathi_gateway.py
MISSING ~/.dharma/agents/sarathi/HOLARCHY_CONTRACT.md
MISSING ~/.dharma/agents/sarathi/SUB_HOLON_ROSTER.yaml
```

∴ **Sarathi is identity + a committed gate + a reusable wake-shell profile +
read-only proof receipts. It is NOT alive. `wake_loop_active` is false.**

## What is committed vs still open

- Reversibility gate: **committed** (`f18fe8476`), tests pass. (The prompt's
  "known uncommitted critical file" line is now stale.)
- `holon_system/` facade package: **added this pass**, 11 import tests pass.
- Front-door docs 01-07: **added this pass** (this file is 01).
- Collapse of the `holon/` fork (138 copies, ~3-4 distinct): **not done** — see
  `12_LOAD_HOLON_COLLAPSE_PLAN.md`. `sprawl_guard.py` correctly stays red.

## Re-run this snapshot

```bash
cd /Users/dhyana/dharma_swarm
git status --short
.venv/bin/python -m dharma_swarm.dgc_cli agent list
.venv/bin/python -m dharma_swarm.dgc_cli agent status --json
python3 scripts/governance/sprawl_guard.py
```
