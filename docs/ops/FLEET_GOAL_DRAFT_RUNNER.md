# Fleet goal draft runner

Role: reference. Subordinate to `CLAUDE.md` and the Mission Control owner
contract in `dharma_swarm/mission_control.py`; this is not fleet authority.

The executable adapter is `python -m dharma_swarm.mission_control_fleet
--state <private-directory> --config <operator-config.json>`. Add `--once`
for a bounded pass. Verify its behavior with:

```sh
python -m pytest tests/test_mission_control_fleet.py tests/test_mission_control.py -q
```

The config contains `workers` keyed by host identity and a `goals` list.
Each worker has an operator-authored `argv` and `side_effects: "none"`.
Each goal has `id`, `title`, `objective`, ordered `workers`,
`interval_seconds` (3600–604800), and explicit `sources` with `id` and `argv`.
Optional limits are `timeout_seconds` (default 240, maximum 600),
`retry_seconds` (default 300), `max_attempts` (default 3), and `enabled`.
Commands receive no shell expansion. Worker input is JSON on stdin. A source
command must output only the intended, non-secret evidence; never configure
raw environment dumps, credentials, or unfiltered private logs as sources.

Deployment must enforce the worker contract outside the prompt: no enabled
tools, plugins, MCP services, shell hooks, or human-facing delivery. A config
declaration alone is not a sandbox. The deployed command must have its own
hard deadline shorter than the controller timeout. Remote process termination
cannot be inferred from closing SSH. These workers produce drafts only;
effectful execution requires a different executor with actual fencing.

TaskBoard and RuntimeStateStore retain tasks, attempts, claims, receipts,
source checkpoints, and previous results. A local file lock permits one
controller per state directory. A failed attempt rotates to the next worker
after backoff; exhaustion blocks that goal for operator review. Unexpired
leases block replay. Canonical Mission Control recovers expired claims.
Source collection failure creates no unfounded task. Status and artifacts
are projections under the explicitly supplied state directory.

Acceptance checks bind the draft to its task and attempt and require literal
quotations from supplied sources. They do **not** certify the model's
interpretation, actual goal achievement, or authorization for its proposed
next action. Every accepted artifact retains `review_required: true`.
An operator can pause a goal with `enabled: false` and restart the service.
Cancelled tasks stay blocked. Failed tasks reach a bounded attempt limit;
inspect the owner records before explicitly admitting replacement work.

Use systemd with `Restart=on-failure`, explicit memory/CPU limits, and a
private state directory. Back up both SQLite owners together while the
controller is stopped or while holding the controller lock. Restore into a
separate directory and inspect it before use. A standby controller must stay
disabled until the previous controller is fenced; this adapter does not
provide a distributed leader election or automatic database failover.

The independent Rushabdev transport watchdog is executable as
`python scripts/ops/agni_nats_watchdog.py`. It reads the current bridge
endpoint rather than a stale host address, while checking service health,
the heartbeat, and JetStream advertisement. Verify it with
`python -m pytest tests/test_agni_nats_watchdog.py -q`.
