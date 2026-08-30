# Installing the chetana Claude Code plugin

## Quick install (one-time, per machine)

```bash
# 1. Copy plugin into Claude Code's marketplaces directory
cp -R ~/dharma_swarm/dharma_swarm/chetana/claude_code_plugin \
      ~/.claude/plugins/marketplaces/local-chetana

# 2. Add to ~/.claude/settings.json:
#    enabledPlugins["chetana@local-chetana"] = true
#    extraKnownMarketplaces["local-chetana"] = {
#      "source": { "source": "directory", "path": "<expanded path above>" }
#    }
```

Or, if you prefer a symlink so plugin updates flow with `git pull`:

```bash
ln -s ~/dharma_swarm/dharma_swarm/chetana/claude_code_plugin \
      ~/.claude/plugins/marketplaces/local-chetana
```

Restart Claude Code. The plugin now activates on every session.

## What gets wired

- **SessionStart hook** — surfaces `chetana status` + decay scan + top wiki gaps as a `systemMessage` injected into the new session's context. 8s timeout.
- **Stop hook** — captures the just-finished session JSONL into staged atoms via `chetana ingest --kind session`. Async, 30s budget. Atoms stay staged until human/agent review.
- **SessionEnd hook** — appends a closure manifest row to `~/.dharma/sessions/captures/manifests/<date>_closures.jsonl`.
- **PreCompact hook** — drops a checkpoint to `~/.dharma/sessions/captures/in_flight/` so context loss doesn't lose the session.
- **SubagentStop hook** — records subagent stops to a daily manifest. Opt-out: `export CHETANA_CAPTURE_SUBAGENTS=0`.

## What gets exposed

- **Skill `/chetana`** — the canonical entry point; matches "chetana", "ingest this", "promote that atom", "what's stale", "revive my wiki", "find gaps", "memory palace", "what did I say last session".
- **Slash commands**:
  - `/chetana-status` — staged / trusted / quarantine counts
  - `/chetana-revive [--all] [--apply]` — re-integrate stale atoms
  - `/chetana-gap-scan [--focus T]` — under-covered topics + open questions
  - `/chetana-ingest <source> --kind <kind>` — staged atom from raw input
  - `/chetana-promote <path>` — gate-checked write to trusted wiki
  - `/chetana-palace` — render JSON Canvas memory palace

## How it discovers chetana

The hooks try (in order) the following Python interpreters:

1. `~/dharma_chetana/.venv/bin/python` (dev worktree)
2. `~/dharma_swarm/.venv/bin/python` (canonical install after merge)
3. `~/dharma_swarm_lf5/.venv/bin/python` (LF5 alt)

Each candidate is tested with `python -c "import dharma_swarm.chetana"`. First success wins. If none have chetana, hooks degrade gracefully — they log to `~/.dharma/sessions/captures/chetana_hook.log` and exit clean. They NEVER block a session.

## Disable temporarily

```bash
# In ~/.claude/settings.json:
"enabledPlugins": { "chetana@local-chetana": false }
```

Or set the env var before launching Claude Code:

```bash
export CHETANA_DISABLE_HOOKS=1   # not yet honored — placeholder for v0.4
```

## Logs

- `~/.dharma/sessions/captures/chetana_hook.log` — every hook fire, timestamped
- `~/.dharma/sessions/captures/daily/<YYYY-MM-DD>/session_<id>.md` — per-session capture summaries
- `~/.dharma/sessions/captures/in_flight/<id>_<ts>.md` — pre-compact checkpoints
- `~/.dharma/sessions/captures/manifests/<date>_closures.jsonl` — session-end events
- `~/.dharma/sessions/captures/subagents/<date>_stops.jsonl` — subagent stops
