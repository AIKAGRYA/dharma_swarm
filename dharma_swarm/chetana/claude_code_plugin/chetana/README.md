# chetana — Claude Code plugin

**chetana** (चेतना) makes every Claude Code session part of a continuous memory-evolution cycle:

- `SessionStart` hook surfaces stale atoms, top wiki gaps, and recent captures into the new session's context.
- `Stop` hook ingests the finished JSONL into staged atoms (one per substantive turn).
- `PreCompact` hook drops a checkpoint to `~/.dharma/sessions/captures/in_flight/`.
- `SubagentStop` hook records subagent finishes to a daily manifest.

All hooks are non-blocking, bounded-time, and degrade gracefully if chetana isn't installed.

## Stale → revive, not exile

When an atom passes `stale_after`, the default move is **revive**: scan corpus for new neighbors / backlinks / answered questions, propose a patch, re-sign axioms, append a `revival_chain` entry. Quarantine is opt-in last resort (`/chetana-decay --quarantine`).

## Slash commands

- `/chetana-status` — staged / trusted / quarantine counts
- `/chetana-revive [--all] [--apply]` — re-integrate stale atoms
- `/chetana-gap-scan [--focus T]` — find under-covered topics + open questions
- `/chetana-ingest <source> --kind <kind>` — staged atom from raw input
- `/chetana-promote <path>` — gate-checked write to trusted wiki
- `/chetana-palace` — render JSON Canvas memory palace

## Wiring

Plugin is at `~/.claude/plugins/marketplaces/local-chetana/chetana/`. Marketplace is `local-chetana`. Enable in `~/.claude/settings.json`:

```json
{
  "extraKnownMarketplaces": {
    "local-chetana": {
      "source": {
        "source": "local",
        "path": "~/.claude/plugins/marketplaces/local-chetana"
      }
    }
  },
  "enabledPlugins": {
    "chetana@local-chetana": true
  }
}
```

## Code

The Python package lives in `dharma_swarm/chetana/` in this repo. `pip install -e .` from `~/dharma_swarm/` is enough; the hooks discover the venv automatically.

## Logs

- `~/.dharma/sessions/captures/chetana_hook.log` — every hook fire with timestamps
- `~/.dharma/sessions/captures/daily/<YYYY-MM-DD>/session_<id>.md` — per-session capture summaries
- `~/.dharma/sessions/captures/in_flight/<id>_<ts>.md` — pre-compact checkpoints
- `~/.dharma/sessions/captures/manifests/<YYYY-MM-DD>_closures.jsonl` — session-end manifest
- `~/.dharma/sessions/captures/subagents/<YYYY-MM-DD>_stops.jsonl` — subagent-stop manifest

## Smoke test

```bash
# Trigger SessionStart manually:
bash ~/.claude/plugins/marketplaces/local-chetana/chetana/scripts/session_start.sh

# Trigger Stop manually (after some session activity):
bash ~/.claude/plugins/marketplaces/local-chetana/chetana/scripts/session_stop.sh

# Inspect the log:
tail -20 ~/.dharma/sessions/captures/chetana_hook.log
```
