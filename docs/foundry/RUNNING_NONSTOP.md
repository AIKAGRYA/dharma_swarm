# Sublimation Foundry: unattended-operation runbook

**Role:** deployment reference. This document grants no runtime, merge, or
promotion authority.

The Foundry is ready for a bounded offline pilot. It is **not evidence that the
VPS is currently healthy**, and a dry/simulation cycle is not research signal.
Production signal begins only after the versioned service is installed, the
legacy state audit is clean, Docker isolation is available, provider routes are
configured, and fresh receipts continue to pass the status verifier.

## What is automated

- A systemd process runs bounded real campaigns continuously and restarts only
  after an unexpected failure.
- Moonshot and Zhipu (plus configured free routes) fail over through a typed
  circuit breaker. Failed zero-token calls are not charged or counted as
  proposals. Three consecutive all-route/no-proposal cycles persist a terminal
  KILL.
- Every promotion requires a sealed Docker isolation proof. Unattended mode
  refuses local degraded execution of model-generated code and runs the
  container explicitly as unprivileged `65534:65534`. A target image that
  cannot run as that user fails its oracle and cannot mint promotion proof.
- Promoted artifacts contain immutable base, parent, delta, cumulative patch,
  and replayed candidate-tree lineage. Receipt writes are unique, append-only,
  hash-chained, fsynced, and blocked by any missing/orphan/duplicate/tampered
  evidence.
- A heartbeat thread, exact checkout SHA, live process command, dependency
  probes, receipt freshness, quarantine, and KILL state feed one truthful status
  verdict. A stale PID or historical best score is never health evidence.
- Before every live/campaign cycle the daemon durably reserves at most $5 of
  provider liability. The spend ledger uses atomic replace plus file/directory
  fsync. A crash leaves that reservation charged against monthly capacity;
  restart never silently reopens it. Successful cycles replace only their own
  reservation with measured provider spend.

External submission, independent review/merge, clearing a KILL, changing a pin,
and adding credentials remain operator decisions. The system must not automate
those authority transitions.

## Offline five-cycle proof

Run this before installing anything:

```sh
./.venv/bin/python scripts/foundry/foundry_pilot.py \
  --state-root /tmp/foundry-pilot \
  --repo-root "$PWD" \
  --runs 5 \
  --max-proposals-per-run 2 \
  --max-spend-usd 0
```

The command makes exactly five supervisor cycles, no provider/network calls,
and no promotion claims. Each cycle has a unique simulation-only chained
receipt plus a sealed `pilot_summary.json`. It validates control flow, not model
quality or VPS throughput.

## VPS prerequisites

- Linux with systemd, Git, `patch`, Python 3.11+, and the repository virtualenv.
- Docker daemon reachable by the dedicated service user. The oracle container
  uses no network, a read-only root filesystem, all capabilities dropped,
  `no-new-privileges`, PID/memory/swap limits, bounded tmpfs, a read-only work
  mount, and explicit unprivileged UID:GID `65534:65534`.
- A fully clean checkout (including no untracked files) at the exact 40-hex
  commit being deployed, with `origin` exactly
  `https://github.com/AIKAGRYA/dharma_swarm.git`. The unattended T0 target
  is pinned to `411fb59c886c18704caaffb611e17cf9e7d824d2`; it never follows remote
  HEAD implicitly.
- `/etc/dharma-foundry/foundry.env` readable only by root/service user. For the
  requested Moonshot→Zhipu failover, configure both `MOONSHOT_API_KEY` and
  `ZHIPU_API_KEY`. Other supported route variables are optional. Never place
  keys in receipts, commands, or the repository.

## Reconcile legacy state before starting

The old VPS status script reported a stale maximum score and ignored general
receipt/artifact integrity. First make a plan (read-only):

```sh
./.venv/bin/python scripts/foundry/migrate_legacy_state.py \
  --state-root /var/lib/sublimation-foundry
```

If the plan identifies the known missing receipts/orphan artifacts, apply the
lossless quarantine explicitly:

```sh
sudo ./.venv/bin/python scripts/foundry/migrate_legacy_state.py \
  --state-root /var/lib/sublimation-foundry --apply
```

This moves bytes rather than deleting them, writes a hashed quarantine
manifest, and leaves `QUARANTINE.json`. Review the manifest and run status; only
an operator may archive/remove the marker after deciding how to resolve the
evidence. New receipt promotion stays fail-closed while the audit is not clean.

## Install the versioned service and status command

Installation is deliberately inert: it writes/verifies the unit and status
cron but does not enable or start the campaign. Choose the real absolute
paths/user and supply the exact reviewed release SHA:

```sh
sudo scripts/foundry/install_service.sh \
  --repo /opt/dharma-foundry/current \
  --python /opt/dharma-foundry/current/.venv/bin/python \
  --user dharma-foundry \
  --expected-sha <40-hex-release-sha> \
  --state-root /var/lib/sublimation-foundry
```

The installer requires exact HEAD, canonical remote, and a clean index/worktree
including untracked files. It also verifies interpreter/imports, Docker, Git,
and `patch`; renders the versioned unit; and symlinks
`/usr/local/bin/foundry-status.sh` to the repository-owned wrapper. Remove the
old root-crontab status entry after confirming `/etc/cron.d/sublimation-foundry-status`
is active, otherwise status will run twice every fifteen minutes.

After reviewing the legacy audit, clearing only a resolved quarantine, creating
the root-owned provider EnvironmentFile with both Moonshot and Zhipu keys, and
confirming the Docker oracle image, opt in to live work explicitly:

```sh
sudo scripts/foundry/install_service.sh \
  --repo /opt/dharma-foundry/current \
  --python /opt/dharma-foundry/current/.venv/bin/python \
  --user dharma-foundry \
  --expected-sha <40-hex-release-sha> \
  --state-root /var/lib/sublimation-foundry \
  --start
```

`--start` fails closed if either required key, STOP/KILL/quarantine state, or
the receipt/artifact audit is red. No install command performs live provider
probes.

The unit uses `Restart=on-failure` and `RestartPreventExitStatus=42`. A terminal
KILL exits 42, remains on disk across process/reboot, and is deliberately not
restarted. Ordinary STOP/budget/max-cycle exits are zero. Never change the unit
to `Restart=always`. The service process has an empty Linux capability set,
kernel-log/realtime protections, native syscall architecture, and bounded
memory, tasks, file descriptors, and file size in addition to the container
controls.

## Check health

```sh
/usr/local/bin/foundry-status.sh
systemctl status sublimation-foundry.service
journalctl -u sublimation-foundry.service --since '1 hour ago'
```

Status exit codes are: 0 healthy, 1 degraded/stopped, 2 unhealthy, 3 terminal
KILL/quarantine. Healthy means all of: exact clean code SHA, fresh heartbeat,
the explicit installed release SHA, canonical origin remote, the expected
daemon command at that PID, required runtime dependencies, intact
append-only receipt/live chains, valid artifact lineage, and fresh evidence.
An unresolved crash reservation is visible as degraded and continues to count
against the cap; only provider-billing reconciliation or month rollover can
justify releasing it.

Provider outage is a visible degraded state during two bounded retries, then a
persistent terminal KILL on the third consecutive no-proposal cycle. A Docker
outage in unattended campaign mode is immediately terminal rather than falling
back to executing untrusted code on the host.

## Evidence map

These implementation anchors are the authority behind this runbook (line
numbers refer to this release and should be refreshed when the files move):

- provider exception/failover accounting: `dharma_swarm/foundry/live.py:128`
- promotion proof semantics: `dharma_swarm/foundry/runner_isolation.py:73`
- cumulative artifact replay: `dharma_swarm/foundry/artifacts.py:97`
- append-only receipt audit/gate: `dharma_swarm/foundry/receipts.py:313`
- persistent KILL and outage fuse: `dharma_swarm/foundry/daemon.py:240`
- truthful health assessment: `dharma_swarm/foundry/status.py:119`
- versioned unit restart policy: `scripts/foundry/systemd/sublimation-foundry.service.in:20`
- five-cycle simulation: `dharma_swarm/foundry/pilot.py:38`
