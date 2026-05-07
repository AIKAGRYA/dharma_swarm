# `cron_jobs.json` — declarative job specs

This file is the **declarative source-of-truth** for jobs that should be running
in the dharma_swarm cron substrate. It is the spec, not the live state.

## Two files, two complementary roles

| File | Role | Schema | Owner | Mutable by |
|------|------|--------|-------|-----------|
| `<repo>/cron_jobs.json` | **declarative spec** — what jobs SHOULD exist | JSON list of job specs | source-controlled | git commits |
| `~/.dharma/cron/jobs.json` | **runtime state** — what the daemon is currently tracking | `{jobs: [...], updated_at: ...}` | `dharma_swarm/cron_scheduler.py` | the daemon (atomic write) |

Both files are intentional. The split that BR-004 in
`docs/state/BROKEN_REGISTER.md` flagged was not a split-brain — it was a
documentation gap. This README closes that gap.

## Read paths in code

The repo file (this one) is read by:

- `dharma_swarm/launchd_job_runner.py` — looks up a job spec by id for one-shot
  invocation by launchd. The launchd plist names a job id; this runner finds
  the spec and executes it.
- `dharma_swarm/pulse.py:_check_and_run_cron_jobs` — pulse-driven cron loop
  reading the same declarative specs. Updates its own last-run tracker at
  `~/.dharma/cron_last_run.json`.
- `api/module_truth.py` — module inventory display (read-only documentation
  surface).
- `tests/test_launchd_job_runner.py`, `tests/test_pulse.py` — coverage.

The live runtime file (`~/.dharma/cron/jobs.json`) is read by:

- `dharma_swarm/cron_scheduler.py` — the daemon's authoritative reader/writer.
  It tracks `last_status`, `last_run_at`, `next_run_at`, and per-job metadata
  on every tick.
- `dharma_swarm/cron_daemon.py` — daemon loop that calls `cron_scheduler.tick()`.
- `dharma_swarm/doctor.py` — health checks normalize/validate the live file.

## Migration script

`scripts/cron_unify.py` is the idempotent reconciler. It reads both files,
proposes a unified live file (`~/.dharma/cron/jobs.unified.json`), and writes
an audit row to `~/.dharma/audit/cron_split_brain_<ts>.json`. It does NOT
mutate the live file. Operator review then atomic-swaps:

```
cp ~/.dharma/cron/jobs.json ~/.dharma/cron/jobs.json.bak
mv ~/.dharma/cron/jobs.unified.json ~/.dharma/cron/jobs.json
```

As of 2026-05-07 the live file is already the canonical superset (all 17 repo
job ids are id-collisions in live), so unification is a no-op.

## When to edit which

- **Adding a new job that should always run on every checkout:** add it to
  `cron_jobs.json` (this file). The daemon will pick it up on next sync.
- **Tweaking a running job's schedule or runtime state:** the live file is
  the right surface only at operator time; for permanent changes, edit the
  declarative spec here and let the daemon reconcile.
- **Inspecting why a job last failed:** read the live file's `last_status` /
  `last_error` fields, or check `~/.dharma/cron/logs/`.

## Reference

- `docs/governance/METABOLIC_CLOCK.md` — scheduler state snapshot
- `docs/state/BROKEN_REGISTER.md` BR-004 — the gap this README closes
- `dharma_swarm/cron_scheduler.py:JOBS_FILE` — live file canonical owner
- `scripts/cron_unify.py` — reconciliation utility
