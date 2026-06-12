# A2A Runtime Spine Workflow

Role: operating workflow for this active track.

## Working Lane

Canonical clean worktree for this Codex pass:

```text
/Users/dhyana/dharma_swarm_a2a_active
branch: codex/a2a-active-track-20260613
base: origin/main @ 9c76b2106
```

Do not continue A2A/NATS build work on the stale dirty
`/Users/dhyana/dharma_swarm` `qwen/spine-adoption` lane.

Current mission ledger:

```text
mission_id: a2a-runtime-spine-20260613
mission_dir: /Users/dhyana/.dharma/ds_goals/a2a-runtime-spine-20260613
repo receipt: reports/a2a/nats_reset/2026-06-13/DS_GOAL_MISSION.json
```

## Loop Pattern

Use the existing autonomy spine and receipt loops:

```bash
make onboard
ds-goal init --goal "A2A Runtime Spine production hardening: broker topology, ack tiers, drain reset, shared-state graph, readiness quorum"
ds-goal run --mission-id <id> --duration-hours 6 --dispatch-mode tmux
ds-goal status --mission-id <id>
```

For smaller verifier loops:

```bash
make codex-loop-init GOAL="Verify A2A ack-tier invariants" MODE=verification NAME="a2a-ack-tier"
make codex-loop-validate LOOP_ID=<id> PHASE=ready
make codex-loop-record LOOP_ID=<id> STATUS=pass EVIDENCE="pytest tests/test_a2a_send.py tests/test_a2a_inbox_bridge.py tests/test_a2a_reply_capture.py"
```

For quorum-style review:

```bash
make context-quorum-check AGENT=codex_composer RISK=Q3 QUESTION="Is A2A Runtime Spine production-ready after the reset receipts?"
python3 scripts/runtime/a2a_prod_readiness_solicit.py --date YYYY-MM-DD
python3 scripts/runtime/a2a_prod_readiness_quorum.py --date YYYY-MM-DD --allow-not-ready --write-latest
make long-harness-init GOAL="A2A Runtime Spine brownfield production hardening" MODE=brownfield
```

## First Build Sequence

1. Baseline broker and filesystem inbox state.
2. Render active-track subtree and YAML criteria.
3. Add or verify tests that prohibit publish-only production claims.
4. Add dry-run/drain tooling if existing manual commands are insufficient.
5. Back up and reset stale inbox/broker state with receipts.
6. Run send -> bridge -> domain reply -> capture against a small test agent.
7. Generate quorum solicitation packets, send them through governed A2A routes,
   and collect two persistent-agent / three-model readiness quorum records.
8. Run:
   - `make hygiene-check`
   - `make docops-integrity`
   - `python3 scripts/governance/check_track_status.py`
   - `python3 scripts/governance/render_active_track_includes.py --check`

## Stop Conditions

Stop and mark the track not production-ready if:

- broker reset has no backup receipt;
- a send only reaches `PUBLISH_ACCEPTED`;
- bridge ack is represented as semantic peer reply;
- a graph/vector/board projection is treated as authority;
- model quorum lacks three distinct model families, median readiness is below
  80, or any reviewer reports red blockers;
- any destructive broker or filesystem operation lacks before/after evidence.
