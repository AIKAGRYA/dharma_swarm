# A2A Daemon Wiring Audit

Role: operational witness for subtracks `01-canonical-nats-topology` and
`05-persistent-agent-workflow-and-quorum`.

The A2A production path depends on long-running local or remote handlers, not
only on broker storage. A durable consumer can exist and still do no useful
work if the LaunchAgent points at a deleted module, stale script, wrong broker,
or crash-looping adapter.

## Audit Command

```bash
python3 scripts/runtime/a2a_daemon_wiring_audit.py --write --json
```

Default receipt:

```text
reports/a2a/nats_reset/2026-06-13/A2A_DAEMON_WIRING_AUDIT.json
```

The audit is read-only. It parses `~/Library/LaunchAgents/*.plist`, checks
A2A/NATS candidate jobs, validates module/script targets against their declared
`WorkingDirectory`, classifies `DHARMA_NATS_URL` broker scope, and scans recent
stdout/stderr logs for repeated missing-module, missing-script, import, and
timeout failures.

## Current Finding

The first live receipt was `FAIL`.

Observed issue classes:

- `missing_module_target`
- `missing_script_target`
- `broker_scope_mismatch`
- `missing_python_module`
- `missing_script_file`
- `import_error`

Current failing surfaces include:

- `com.dhyana.nats-a2a-bridge`
- `com.dhyana.nats-receipt`
- `com.dhyana.a2a-core-contact`
- `com.dharma.a2a.hermes-m5`
- `com.hermes.a2a-server`

This explains why AGNI can show pending messages while the local system keeps
checking filesystem inboxes: several declared always-on A2A/NATS daemons are
not actually wired to live targets.

The stale declarations were then quarantined, not silently edited in place:

- Tool: `scripts/runtime/a2a_launchagent_quarantine.py`
- Receipt:
  `reports/a2a/launchagent_quarantine_receipts/20260612T184702Z-a2a-launchagent-quarantine.json`
- Backup root:
  `/Users/dhyana/.dharma/a2a_bus/quarantine/launch_agents/20260612T184702Z`
- Pointer left in place:
  `/Users/dhyana/Library/LaunchAgents/DHARMA_A2A_RUNTIME_SPINE_README.md`

The refreshed daemon-wiring receipt now reports top-level `PASS`. It sees only
the remaining non-broken A2A/NATS-like declarations:

- `com.dhyana.loop.a2a-fleet`
- `com.dhyana.nats`

This proves stale daemon declaration cleanup only. It does not prove live
Fable/Hermes handlers, target-owned review, or production readiness.

## Interpretation Rule

`PASS` means the declared daemon targets exist and do not contradict the
expected broker scope. It does not prove semantic peer work, reviewer quorum, or
production readiness.

`FAIL` blocks production confidence because peer-agent contact cannot be assumed
while the declared handlers are missing or pointed at the wrong broker.

## Repair Plan

Use the live-handler repair plan to join this daemon audit with current AGNI
delivery gaps:

```bash
python3 scripts/runtime/a2a_live_handler_repair_plan.py --write --json
```

Receipt:

```text
reports/a2a/nats_reset/2026-06-13/A2A_LIVE_HANDLER_REPAIR_PLAN.json
```

The repair plan remains the live-handler authority. After quarantine and
post-Qwen reset it has no failing daemon entries, zero delivery gaps, and
`READY_TO_MUTATE`; it still lists Fable and Hermes as missing target-owned
reviewer records.
