# Large-Codebase Navigation: Sourcegraph Cody

Phase 5 of the governance install. dharma_swarm has grown to ~500
Python modules with five worktree mirrors of every hot-path symbol.
Local Grep + GitNexus already cover most needs, but cross-worktree
caller graphs and architecture-wide queries benefit from a hosted
semantic index.

## Why Sourcegraph (vs Augment / Greptile / nothing)

| Tool | Pitch | Fit for dharma_swarm |
|---|---|---|
| **Sourcegraph Cody** | Code search + AI assistant indexed across repos | Best fit: native cross-repo search, GitHub-direct, free tier exists |
| Augment Code | Large-codebase context retrieval beyond token windows | Overlap with Sourcegraph; defer until Sourcegraph proves insufficient |
| Greptile | PR review + codebase Q&A API | Overlap with CodeRabbit (Phase 3); defer |
| Status quo (Grep + GitNexus) | Local; already in place | Already used; Sourcegraph adds cross-worktree mirror coverage |

The decisive factor for dharma_swarm is **the 5-worktree mirror problem**.
Symbols like `_complete_deferred_startup` exist in 5 places; editing
one is editing one-fifth of the truth. Sourcegraph indexes all 5 and
returns hits across them in a single query. Local Grep would miss
worktrees outside the current `cwd`.

## Setup (manual, one-time)

1. Create a Sourcegraph account at https://sourcegraph.com/sign-up.
2. Free tier covers up to 10 repos and unlimited Cody queries against
   public repositories. Pro tier ($9/mo individual) adds private repos
   and higher quotas.
3. Connect the Sourcegraph App to GitHub:
   - https://github.com/marketplace/cody
   - Select `AmitabhainArunachala/dharma_swarm`. Optionally also add
     the LF5 worktree if it lives in a separate GitHub repo.
4. Wait for the initial index (a few minutes for ~500 modules).
5. Install Cody for VS Code:
   `code --install-extension sourcegraph.cody-ai`
   Or use the web client at https://sourcegraph.com/cody.

## Three primary use cases

### 1. Cross-worktree drift detection

Replace the in-session `get_blast_radius` heuristic for hot-path
symbols. From Cody, ask:

```
Find every definition of _complete_deferred_startup across all
indexed repos. Show file path and line.
```

Expected: ≥5 hits across `dharma_swarm`, `dharma_swarm_lf5`,
`dharma_swarm_lf5_operator`, `dharma_swarm_dashboard_skill_worktree`,
`migration_delta/dharma_swarm_old`. If any are missing, drift has
occurred and the map needs an update.

### 2. Caller graphs for refactor blast-radius

Before refactoring a method on a hot-path class:

```
Show all call sites of RuntimeStateStore.record_task_claim.
Group by module.
```

Use this output when filling in the PR template's "Worktree mirrors
checked" section. Pasting the Sourcegraph output is acceptable evidence.

### 3. Architecture queries that backstop Semgrep rules

Semgrep Rule 1 (no-unauthorized-dharma-write) flags references to
`Path.home() / ".dharma"` outside the canonical-owner allowlist.
Sourcegraph can answer the inverse:

```
Show every read or write to a path under ~/.dharma in dharma_swarm,
grouped by module. Flag any module not in the canonical-owner
allowlist (runtime_state.py, system_rv.py, daemon_config.py, ...).
```

This is useful when reviewing Rule 1's WARNING-severity findings:
Sourcegraph's view often makes the read-vs-write classification clear
faster than reading each Semgrep hit individually.

## When Sourcegraph isn't the right tool

- **Single-file local edits**: Grep + Read are faster.
- **Symbol blast-radius inside a single repo**: GitNexus
  (`mcp__gitnexus__impact`, `get_blast_radius`) is faster and free.
- **Code review on a specific PR**: CodeRabbit (Phase 3) is purpose-built.
- **Just-in-time tutorial / docs lookup**: Context7 MCP is faster.

Use Sourcegraph for the queries it's actually best at: **cross-repo
+ semantic + architecture-wide**.

## Mismatch-map integration (Phase 5.3)

`scripts/governance/check_mismatch_map.py` parses
`INTERFACE_MISMATCH_MAP.md` and verifies every `file.py:LINE`
citation still references real code. It runs in CI via
`.github/workflows/mismatch-map.yml` on any PR that touches the map
or a cited module.

The drift checker:
- Skips citations to external deps (`huggingface_hub.py`, etc.).
- Maps bare module names (e.g., `swarm.py`) to their canonical paths
  via `BARE_MODULE_HINTS` in the script.
- Fails on missing files or line numbers past EOF.

Run locally:

```bash
make mismatch-check
# or:
python3 scripts/governance/check_mismatch_map.py
```

Sourcegraph + this checker form a two-layer safety net:
1. **The checker** catches mechanical drift (file moved or shrunk).
2. **Sourcegraph** catches semantic drift (the cited code still exists
   but its meaning changed).
