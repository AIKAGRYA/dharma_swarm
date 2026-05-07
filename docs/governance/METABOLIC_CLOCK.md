# Metabolic Clock

Date verified: 2026-05-07

## Canonical Surfaces

- Scheduler state: `~/.dharma/cron/jobs.json`
- Active daemon label: `com.dharma.cron-daemon`
- Active daemon command observed through launchd:
  `/Users/dhyana/dharma_swarm_lf5/.venv/bin/dgc cron daemon`
- Long-running swarm label: `com.dharma.swarm`
- System-map rollup: `reports/system_map/latest.json`

## Current Truth

The metabolic clock is live. At initial verification, the running launchd
process for `com.dharma.cron-daemon` was alive while `/opt/homebrew/bin/dgc
--help` exposed only `status` and `audit`, making restart unsafe. After the CLI
patch, both `/opt/homebrew/bin/dgc` and the live
`/Users/dhyana/dharma_swarm_lf5/.venv/bin/dgc` command surface expose `cron`.
The daemon was then restarted and observed running under launchd.

`~/.dharma/cron/jobs.json` is the current scheduler state surface. On
2026-05-07 it had 23 jobs, 7 enabled jobs, 5 enabled jobs with `last_status =
error`, 1 enabled job with `last_status = ok`, and 1 enabled job with no
`last_status`.

## Operating Rules

- Do not unload or reload `com.dharma.cron-daemon` unless the target `dgc`
  binary exposes `cron daemon`.
- Treat `~/.dharma/cron/jobs.json` as the job-state authority for scheduler
  health.
- Fix failed jobs as separate scoped work packets. Do not mix job-level fixes
  with launchd/clock convergence.
- Re-read the clock through `reports/system_map/latest.json` after any scheduler
  or CLI change.

## Drift To Watch

- Enabled jobs can keep failing while the daemon itself remains alive.
- A null `last_status` is neither healthy nor failed until a job-specific probe
  explains it.
- Live daemon code can diverge across worktrees; clock handlers must exist in
  the launchd-targeted worktree, not just the source worktree under edit.
