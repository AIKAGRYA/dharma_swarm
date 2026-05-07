# Live Ops Dashboard

**Status:** seeded Slot 6 megafile
**Scope:** current operator-facing state summary
**Refresh rule:** prefer live probes over this snapshot when they disagree

This file is a compact state surface for cold agents. It is not a replacement
for `dgc status`, cron state, test output, GitHub checks, or the system map. It
points to the live surfaces an agent should inspect before acting.

## Current Live Surfaces

| Surface | Path / command | Current role |
|---|---|---|
| System map report | `reports/system_map/latest.json` | OrganState perception output |
| System map CLI | `dgc map list`, `dgc map drifted`, `dgc map gaps` | Read-only organ queries |
| Cron schedule | `~/.dharma/cron/jobs.json` | Metabolic job declarations and last status |
| Launchd clock | `launchctl list | rg 'com.dharma'` | Process attachment truth |
| DocOps gate | `make docops-integrity` | Documentation authority and count checks |
| Coherence Delta gate | `.github/workflows/coherence-delta.yml` | PR-body map reread discipline |
| Interface register | `INTERFACE_MISMATCH_MAP.md` | Runtime failure and mismatch memory |
| Broken register | `docs/state/BROKEN_REGISTER.md` | Declared-vs-actual contradictions |

## Current Phase 1 State

- PR template discipline is installed.
- Coherence Delta field presence is machine-checked in CI.
- DocOps can reject unregistered authority-scope claims.
- OrganState exists and the system-map populator emits organ facts.
- `system-map-populator` is scheduled in `~/.dharma/cron/jobs.json`.
- `tcs_heartbeat` is scheduled and has a cron handler.

## Not Yet Closed

- OrganState does not yet drive Darwin, Shakti, PR classification, or runtime
  gates.
- Coherence Delta validates field presence, not the truth of each answer.
- Several cron jobs may still report `last_status: error`; treat the cron file
  as a mixed-health surface until each job is verified.
- Static navigation remains partial/stale compared with live xray output.

## First Probe Sequence

Run these before any major follow-up:

```bash
make docops-integrity
python scripts/system_map_populator.py --audit-dir /Users/dhyana/.dharma/audit --output reports/system_map/latest.json
python -m dharma_swarm.dgc_cli map list --path reports/system_map/latest.json
python -m dharma_swarm.dgc_cli map gaps --path reports/system_map/latest.json
launchctl list | rg 'com.dharma'
```

If these disagree, trust the command outputs over this file and update this file
or `docs/state/BROKEN_REGISTER.md` in the same PR.
