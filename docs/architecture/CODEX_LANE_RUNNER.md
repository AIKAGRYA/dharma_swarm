# Codex Lane Runner

The Codex lane runner is the durable substrate for background Codex work.

It uses three separations:

- active operator worktrees stay untouched
- each lane gets a dedicated git worktree under `~/.dharma/codex_lanes/worktrees/`
- logs, heartbeat, manifest, mission, and reports live under `~/.dharma/codex_lanes/<lane>/`

Start a lane:

```bash
CODEX_LANE_MISSION_FILE=/path/to/mission.md scripts/start_codex_lane_tmux.sh cleanup-audit
```

Find it later:

```bash
scripts/status_codex_lane_tmux.sh cleanup-audit
tmux attach -t codex_lane_cleanup-audit
cat ~/.dharma/codex_lanes/cleanup-audit/README.md
```

Stop it:

```bash
scripts/stop_codex_lane_tmux.sh cleanup-audit
```

The runner can survive a terminal closing because the long-lived process is
inside tmux. If the machine restarts, start the same lane name again; it reuses
the same lane state directory and worktree.

Defaults:

- base ref: `origin/main`
- branch: `codex-lane/<lane>`
- state root: `~/.dharma/codex_lanes`
- worktree: `~/.dharma/codex_lanes/worktrees/<lane>`
- sandbox: Codex `workspace-write`

Use `CODEX_LANE_DANGEROUS_FULL_AUTO=1` only for a disposable lane worktree with
a narrow mission and a clear rollback plan.
