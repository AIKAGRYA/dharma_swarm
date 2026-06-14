# Runtime Spine Hardening Progress - Dispatch Mode Gate

Date: 2026-06-14 JST
Track: `runtime-truth-spine-adoption-2026-06`
Starting hardening score: 65/100
Current hardening score: 70/100

## Gate Passed

- 65 to 70: orchestrator and A2A ingress dispatch modes are now
  machine-checkable. This does not prove default spine adoption. It proves that
  orchestrator source remains opt-in spine, the persistent LaunchAgent spec now
  declares `DHARMA_SPINE_DISPATCH=1`, and every scanned A2A submit path is
  either spine-native, legacy-quarantined, non-production, or unknown-free.
- Post-70 hardening: `thinkodynamic_director` named-runner execution now
  traverses `invoke_agent` and emits an `EvidenceReceipt`, reducing unwrapped
  `AgentRunner.run_task` production/direct paths from 2 to 0. This is concrete
  debt retirement, not a readiness-score increase. The strict dispatch-mode
  gate now also depends on production direct-runner clearance, so this cannot
  regress invisibly.
- Post-70 manual script drain: all five manual live-script AgentRunner calls
  now traverse `run_manual_agent_runner_via_spine()`. These scripts remain
  manual/operator probes, not daemon/default runtime proof.

## Fresh Evidence

```text
python3 scripts/governance/spine_dispatch_mode_report.py --strict
Orchestrator mode:              spine_opt_in_legacy_default
Current process state:          legacy_default_in_current_process
Persistent daemon launch state: spine_enabled_launch_spec
Daemon health self-report:      missing_runtime_dispatch
Live census state:              proof_gaps_present
Live census proof-gap surfaces: 7
Live source-stale surfaces:     2
A2A spine-native adapters:      1
A2A legacy-quarantined paths:   0
A2A unknown paths:              0
AgentRunner legacy direct paths:      0
AgentRunner spine-wrapped paths:      1
AgentRunner manual live scripts:      0
Manual live spine-wrapped:            5
Production direct-runner clear: yes
Manual direct-runner clear:     yes
65->70 score gate:              PASS

Live census proof gaps:
  substrate.dharma_daemon: status=live; pids=93875; source_state=source_changed_after_process_start; proof_gaps=daemon_dispatch_runtime_unproven,daemon_process_source_stale,daemon_runtime_receipts_active_head_dirty
    runtime_receipt_active_head: clean=false; total=7769; latest=2026-06-13T23:13:37.937601+00:00; windows=5m:56/56,15m:56/56,60m:224/224
  substrate.dharma_cron: status=stopped; pids=none; source_state=unknown; proof_gaps=substrate_dharma_cron_stopped
  transport.a2a_bridge: status=stopped; pids=none; source_state=unknown; proof_gaps=a2a_inbox_bridge_stopped
  dashboard.local: status=live; pids=70585; source_state=source_changed_after_process_start; proof_gaps=dashboard_control_surface_rows_slow,dashboard_control_surface_source_stale
  tmux.cockpit: status=stopped; pids=none; source_state=unknown; proof_gaps=tmux_cockpit_stopped
  mission.forge_reality_arena: status=stopped; pids=none; source_state=unknown; proof_gaps=mission_forge_reality_arena_stopped
  remote.agni: status=stale; pids=none; source_state=unknown; proof_gaps=remote_agni_stale
```

Focused verifier:

```text
pytest -q tests/test_manual_spine_runner.py tests/test_spine_dispatch_mode_report.py --tb=short
6 passed
```

Syntax verifier:

```text
python3 -m py_compile scripts/governance/spine_dispatch_mode_report.py
exit 0
```

Live daemon check:

```text
lsof -nP -iTCP:7433 -sTCP:LISTEN
Python 93875 dhyana 18u IPv4 ... TCP *:7433 (LISTEN)

ps -p 93875 -o pid,ppid,command
93875 93874 ... /opt/homebrew/bin/dgc orchestrate-live
```

Launch spec check:

```text
plutil -p /Users/dhyana/Library/LaunchAgents/com.dharma.swarm.plist
ProgramArguments = cd /Users/dhyana/dharma_swarm && source .env && TINY_ROUTER_BACKEND=heuristic dgc orchestrate-live
EnvironmentVariables.DHARMA_SPINE_DISPATCH = 1
EnvironmentVariables.PATH = /usr/local/bin:/usr/bin:/bin:/opt/homebrew/bin
```

Live-ops census snapshot:

```text
python3 scripts/runtime/live_ops_census.py --write
/Users/dhyana/.dharma/ops/live_process_census.json

make orient
Generated: 2026-06-14T00:10:25Z
Daemon spine: launch=spine_enabled_launch_spec; running=not_inspected_no_secret_env_dump
[live] substrate.dharma_daemon proof_gaps=daemon_dispatch_runtime_unproven,daemon_process_source_stale,daemon_runtime_receipts_active_head_dirty
[stopped] substrate.dharma_cron proof_gaps=substrate_dharma_cron_stopped
[stopped] transport.a2a_bridge proof_gaps=a2a_inbox_bridge_stopped
[live] dashboard.local proof_gaps=dashboard_control_surface_rows_slow,dashboard_control_surface_source_stale
[stopped] tmux.cockpit proof_gaps=tmux_cockpit_stopped
[stopped] mission.forge_reality_arena proof_gaps=mission_forge_reality_arena_stopped
[stale] remote.agni proof_gaps=remote_agni_stale
summary.by_status = {"blocked": 1, "live": 6, "stale": 1, "stopped": 7}
notable runtime blockers: daemon/default dispatch unproven; daemon source stale; dharma cron stopped; A2A inbox bridge stopped; dashboard rows slow and source stale; tmux cockpit stopped; Forge supervision stopped; remote AGNI stale; terminal.tui stopped

python3 scripts/governance/agent_onboard.py --fast --no-net
Daemon spine  : launch=spine_enabled_launch_spec; running=not_inspected_no_secret_env_dump

curl --max-time 3 -fsS http://127.0.0.1:7433/health
curl: (28) Operation timed out after 3009 milliseconds with 0 bytes received

nc -vz 127.0.0.1 7433
Connection to 127.0.0.1 port 7433 [tcp/*] succeeded!
```

Governance and regression checks:

```text
python3 scripts/governance/check_track_status.py
exit 0; runtime-truth-spine-adoption-2026-06 all 9 completion criteria pass — SHIPPABLE; operator lifecycle review required

python3 scripts/governance/render_active_track_includes.py --check
exit 0

make onboard
exit 0; active portfolio renders current=70/100

make orient
exit 0

make hygiene
exit 2; no rule to make target `hygiene'

make hygiene-check
exit 0; Hygiene integrity OK

make test-hygiene
exit 0; No findings.

make uplift-guards
exit 0

make module-budget
exit 0; No target Python files changed. OK.

make nats-substrate-contract
54 passed

pytest -q tests/test_spine_dispatch_mode_report.py tests/test_spine_adoption_dispatch.py tests/test_orchestrator_spine_dispatch.py tests/test_spine_persistence_invariant.py --tb=short
27 passed

git diff --check
exit 0
```

## Dispatch Truth

- `dharma_swarm/orchestrator.py:2351` branches on
  `DHARMA_SPINE_DISPATCH`. Without that environment variable set to `1`, the
  default path remains direct `runner.run_task(task)`.
- `/Users/dhyana/Library/LaunchAgents/com.dharma.swarm.plist` now sets
  `DHARMA_SPINE_DISPATCH=1`, so the next LaunchAgent-started daemon is
  configured for the spine path. The already-running daemon was not restarted in
  this slice; daemon/default dispatch still needs a fresh live receipt proof.
- `dharma_swarm/a2a/a2a_bridge.py:126` is the one spine-native A2A adapter.
- `ingest_trishula_inbox`, both HTTP node-gateway submit endpoints, local A2A
  client dispatch, and NATS consume now route through `submit_via_spine`; they
  are no longer direct `A2AServer.submit()` bypasses.
- No A2A legacy submit paths remain on the migration allowlist.
- `dharma_swarm/thinkodynamic_director.py:1429` now contains the sole named
  swarm `AgentRunner.run_task` call, and it is inside
  `_run_named_swarm_runner_via_spine` behind `invoke_agent`. The scanner now
  classifies it as `spine_wrapped_direct_runner`, reducing legacy direct
  AgentRunner paths from 2 to 0.
- `scripts/live_claude_code.py`, `scripts/live_fanout.py`,
  `scripts/live_genome_test.py`, and `scripts/live_test.py` now call
  `run_manual_agent_runner_via_spine()`. The scanner classifies the five call
  sites as `manual_live_spine_wrapped`, with zero direct manual script calls.

## Still Not Production-Ready

Score does not move beyond 70 because the blockers are still real:

- The persistent LaunchAgent spec is now configured for default-spine dispatch,
  but the already-running daemon has not been restarted or proven with a fresh
  daemon/default EvidenceReceipt.
- A2A submit bypasses are drained, but this is not enough for production
  readiness without daemon/default dispatch and live receipt saturation.
- `agent_runner.py` adoption remains open: the dispatch-mode report now shows
  zero unwrapped `thinkodynamic_director` direct-runner paths and zero direct
  manual live scripts, but manual wrappers are still operator probes and the
  daemon/default path still needs a controlled live proof.
- Runtime receipt saturation and idempotency coverage for major command
  surfaces are not yet proven.
- The dispatch-mode verifier now performs a bounded, non-secret daemon
  `/health` probe and records the current runtime-dispatch self-report as
  unproven. The latest strict gate observed
  `daemon_health_self_report=missing_runtime_dispatch`; earlier bounded probes
  also alternated through `timeout`. The daemon health API source exposes
  `runtime_dispatch` for the next daemon start, but the current live daemon
  still has not produced a bounded runtime-dispatch self-report.
- The live daemon process is now identified from listener ownership as PID
  `93875`; the fresh census reads its start time through Darwin `libproc` as
  `2026-06-13T13:55:10Z` and proves it predates runtime source changes through
  `2026-06-13T21:10:58Z`.
- The dashboard control-surface endpoint is live and returns rows slowly, and
  listener ownership identifies PID `70585`; the fresh census reads its start
  time through Darwin `libproc` as `2026-06-13T16:58:24Z` and proves it predates
  control-surface/dashboard UI changes through `2026-06-13T23:40:08Z`. Treat
  the live API projection as requiring controlled restart/proof before it can
  support a score increase.
- Live process truth is still split: daemon/API/NATS are live, but the A2A
  inbox delivery bridge, cron daemon, terminal TUI, and tmux cockpit remain
  stopped or unproven, Forge supervision is stopped, remote AGNI is stale, and
  daemon/default runtime dispatch remains unproven.
- Dashboard, terminal, composer, provider/model, and longrun runtime claims
  still need source-age/error/risk labeling before the runtime spine can be
  called production-ready.

## Checkpoint: A2A Bridge No-Start Proof In Dispatch Gate

Date: 2026-06-14 21:55 JST

Fresh live-census and status-script checks keep the dispatch score at 70/100
while making the A2A inbox bridge state harder to misread:

```text
python3 scripts/runtime/live_ops_census.py --write
exit 0

bash scripts/status_a2a_inbox_bridge_tmux.sh
exit 0
status=stopped
heartbeat.timestamp=2026-06-11T18:51:37Z
consumer=hermes_inbox
filter_subject=dharma.agent.hermes-m5.inbox
deliver_policy=new
ack_policy=explicit
num_pending=0
num_ack_pending=0
```

The current `transport.a2a_bridge` census row carries:

```text
status=stopped
proof_gaps=a2a_inbox_bridge_stopped,a2a_inbox_bridge_heartbeat_stale
consumer_probe=consumer_inspectable
semantic_reply_claim=false
peer_model_processed_claim=false
```

This proves the durable consumer and historical bridge artifacts are
inspectable. It does not prove live bridge delivery, semantic reply handling,
or peer model processing. Score stays 70/100.
