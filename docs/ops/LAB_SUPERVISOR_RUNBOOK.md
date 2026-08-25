---
doc_role: reference
scope: bounded operation of the Sublimation Foundry and RSI Lab supervisor
authority: subordinate to CLAUDE.md and executable supervisor contracts
---

# Lab Supervisor runbook

This supervisor is a five-minute, lock-protected inspection and recovery loop.
It is not a standing reasoning agent and it does not certify research quality.
Each tick reads declared evidence, derives one of `Healthy`, `Degraded`,
`Halted`, or `Blocked`, performs only configured bounded actions, and appends a
hash-chained receipt. The executable state machine is in
`dharma_swarm/lab_supervisor/engine.py`; reproduce its contract with
`python3 -m pytest -q tests/test_lab_supervisor.py tests/test_lab_supervisor_cli.py`.

## Authority boundary

The complete action vocabulary is `inspect`, `keep_halted`,
`quarantine_provider`, `rotate_provider`, `run_bounded_trial`, and
`prune_disposable`. Commands are exact argument arrays, never shell strings.
Shells, remote login/copy, Git, GitHub, destructive file tools, deploy/merge
verbs, inline Python, and secret-looking arguments are rejected by
`dharma_swarm/lab_supervisor/config.py`.

KILL/HALT evidence is latched in both runtime state and the receipt history.
Removing a STOP file, restarting this supervisor, deleting only `state.json`,
or receiving a healthy probe cannot clear it. This repository intentionally
provides no unattended clear operation. A human-reviewed replacement state
root and an external acknowledgement receipt are required before a halted lab
can ever be considered for a new campaign.

The shipped systemd unit omits `--allow-actions`, and configuration defaults to
`dry_run: true`. Both the CLI flag and `dry_run: false` are required for an
action. The installer validates a clean exact 40-character Git SHA but never
enables or starts the units. It defaults to a dedicated
`dharma-lab-supervisor` account and never creates that account or grants it
permissions. Provision only read access to declared evidence and write access
to the supervisor state root. A later live-action override must enumerate the
minimum lab paths required by its exact adapters in `ReadWritePaths`; adding
`--allow-actions` alone does not widen the shipped filesystem sandbox. The
safe unit permits only `AF_UNIX`; any network-bearing probe or bounded model
trial needs a separately reviewed address-family override.

Subprocesses receive a static environment containing only a fixed system
`PATH`, `LANG`, `LC_ALL`, and `TMPDIR`. `HOME`, `PYTHONPATH`, provider keys, and
all other caller environment values are deliberately absent. A live provider
adapter must obtain authority through its own reviewed credential membrane;
the supervisor will not forward ambient credentials.

## Configuration

Store configuration outside Git with mode `0600`. Do not place API keys,
provider tokens, `.env` paths, credentials, prompts, or raw model payloads in
it. The following is a shape example, not host truth:

```json
{
  "schema": "dharma.lab_supervisor.config.v1",
  "policy": {
    "dry_run": true,
    "cadence_seconds": 300,
    "max_subprocess_calls_per_tick": 8,
    "max_actions_per_lab_per_day": 24,
    "max_trials_per_lab_per_day": 5,
    "max_provider_actions_per_lab_per_day": 6,
    "max_cleanup_actions_per_lab_per_day": 2,
    "probe_retry_attempts": 2,
    "circuit_failure_threshold": 3,
    "circuit_cooldown_seconds": 1800,
    "min_free_disk_bytes": 1073741824,
    "max_load_per_cpu": 2.0
  },
  "labs": [
    {
      "name": "sublimation-foundry",
      "kind": "sublimation_foundry",
      "state_root": "/root/.dharma/foundry",
      "evidence_paths": [
        "/root/.dharma/foundry/kill_metrics.json",
        "/root/.dharma/foundry/receipts"
      ],
      "halt_paths": ["/root/.dharma/foundry/STOP"],
      "max_stale_seconds": 1800,
      "bounded_trial": {
        "argv": [
          "/opt/dharma/dharma_swarm/.venv/bin/python",
          "/opt/dharma/dharma_swarm/scripts/foundry/run_campaign.py",
          "dry-run",
          "flashinfer",
          "--generations",
          "1",
          "--per-generation",
          "2",
          "--budget",
          "0",
          "--state-root",
          "/root/.dharma/foundry/supervised-trials"
        ],
        "feature_argv": [
          "/opt/dharma/dharma_swarm/.venv/bin/python",
          "/opt/dharma/dharma_swarm/scripts/foundry/run_campaign.py",
          "dry-run",
          "--help"
        ],
        "timeout_seconds": 600
      },
      "trial_interval_seconds": 3600,
      "disposable_paths": ["/root/.dharma/foundry/cache"],
      "disposable_min_age_seconds": 86400
    },
    {
      "name": "rsi-lab",
      "kind": "rsi_lab",
      "state_root": "/root/rsi-lab",
      "evidence_paths": [
        "/root/rsi-lab/evidence",
        "/root/rsi-lab/experiments"
      ],
      "halt_paths": ["/root/rsi-lab/HALT"],
      "max_stale_seconds": 1800,
      "status_probe": {
        "argv": ["/root/rsi-lab/current/.venv/bin/python", "-m", "dharma_swarm.forge_lab", "sync", "status", "--json"],
        "feature_argv": ["/root/rsi-lab/current/.venv/bin/python", "-m", "dharma_swarm.forge_lab", "sync", "status", "--help"],
        "cwd": "/root/rsi-lab/current/repo",
        "timeout_seconds": 60
      },
      "trial_interval_seconds": 3600,
      "disposable_paths": ["/root/rsi-lab/cache"],
      "disposable_min_age_seconds": 86400
    }
  ]
}
```

`validate-config` executes only each separately declared `feature_argv`; it
never discovers a mutating subcommand by executing the action itself. A missing
feature probe remains unverified and must not be enabled for live actions.

The Foundry defaults above follow the current repository daemon's
`~/.dharma/foundry` state convention (`dharma_swarm/foundry/daemon.py:36`) and
STOP marker (`dharma_swarm/foundry/killswitch.py:21`). The documented bounded
dry-run arguments are owned by `scripts/foundry/run_campaign.py:144`. RSI paths
remain host-declared because this supervisor package does not own an RSI state
layout. Run `validate-config` on the accepted host; a declared command that is
absent is `Blocked`, not silently substituted.

## Prove before enabling

1. Pin one accepted repository SHA and one reviewed config hash.
2. Run `validate-config`; retain the JSON output.
3. Run five dry ticks for each lab, verifying five new chain-valid receipts and
   no external actions.
4. Run five pre-approved bounded trials per lab under their existing hard cost
   fuses. A hermetic Foundry dry-run qualifies as pipeline evidence, not as a
   scientific improvement. RSI live execution remains disallowed until its
   immutable-release and containment gates are independently closed.
5. Remove each halt marker only in a disposable fixture and prove the
   supervisor remains `Halted` because the latch persists.
6. Review disk/load floors, daily call and action caps, adapter command hashes,
   and the receipt chain.
7. Ask the operator for separate deployment authority. The install helper may
   then render inert units from the exact SHA. Enabling the timer and adding a
   live-action override are separate operator actions.

Useful commands:

```bash
python scripts/runtime/lab_supervisor.py validate-config --config /etc/dharma/lab-supervisor.json
python scripts/runtime/lab_supervisor.py tick --config /etc/dharma/lab-supervisor.json --state-root /var/lib/dharma/lab-supervisor
scripts/runtime/status_lab_supervisor.sh --config /etc/dharma/lab-supervisor.json --state-root /var/lib/dharma/lab-supervisor
scripts/runtime/install_lab_supervisor.sh --repo /opt/dharma/dharma_swarm --config /etc/dharma/lab-supervisor.json --python /opt/dharma/dharma_swarm/.venv/bin/python --expected-sha FULL_SHA
```

Runtime receipts live only under the configured supervisor state root and must
never enter Git. Cleanup follows no symlinks, deletes files only, and accepts
only explicitly configured descendants whose path names include `tmp`, `temp`,
or `cache`; evidence, receipts, archives, and runs are rejected.
Cleanup is deliberately reactive, not periodic: it is considered only when the
free-disk safety floor is breached, and remains subject to age, path, and daily
action caps. Normal timer ticks do not prune merely because the cadence elapsed.

`validate-config` returns exit 4 if any declared command is unavailable,
missing its feature probe, or fails that probe. `tick` returns exit 4 only for
supervisor-internal failure such as lock contention or an invalid receipt
chain. A correctly observed lab-level `Halted` or `Blocked` state remains a
successful inspection transaction (exit 0) with a receipt.

Version 1 fixes `policy.cadence_seconds` at 300 because the shipped timer is a
five-minute timer; configuration that claims another cadence is rejected. The
receipt verifier streams the chain and caches only a stat-bound verification
summary for the unchanged file, so normal ticks do not load or parse the full
history repeatedly. Blank, truncated, non-object, or hash-invalid rows block
all effects. The installer requires the declared service account to exist and
creates its private state directory mode 0700 under that account.
