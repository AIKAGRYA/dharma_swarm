# VentureCell Operator OS 8h Autonomous Build Spec

Date: 2026-06-02
Status: ready-to-launch spec, not launched
Doc class: active_spec candidate / working plan

## Executive Frame

Run an 8h+ autonomous Codex build mission that moves VentureCell Operator OS
from the current first brick to a usable native company-OS surface.

The north star is to surpass Polsia and Cofounder by fusing:

- Polsia's autonomous-company ambition;
- Cofounder's company workspace, departments, Canvas, tasks, Library, and
  Plan/Execute shell;
- Karpathy-style LLM wiki as an agent-native knowledge substrate;
- Dharma Swarm governance: Darshan, Chetana, TaskBoard, A2A receipts,
  governed admission, DecisionLog, Go evidence receipts, and ds-goal leases.

Do not clone either product. Build the Dharma version.

Current base:

- commit `5d27d706` added `dharma_swarm/venture_cell/operator_os/`;
- generated digest status is `blocked_on_external_reader_gate`;
- autonomy is `L0_read_only_plan`;
- Chetana/wiki is visible but too large for naive scanning:
  `large_projection_needs_index`;
- product-build score is about 52/100.

Target after this run: at least 70/100. The system should have a real
operator-facing projection, live local surface loading, receipts, tests, and a
next MemoryKernel build packet.

## Non-Negotiables

- Use existing DS organs. Do not create a new runner, queue, task board,
  memory plane, dashboard substrate, router, daemon, or authority system.
- No external outreach, spending, deployment, publishing, protected merge,
  payment, credential mutation, or live authority claim.
- No fake NATS/A2A liveness. A2A filesystem rows are evidence only until live
  contact is proven. NATS is only live if current ack proof exists.
- Preserve unrelated dirty work. Never run `git add -A`.
- Do not promote Chetana atoms into trusted memory without Chetana gates.
- Do not mark heartbeat as progress. Productive means artifact, test, receipt,
  or commit.
- If the old mission `20260602-venturecell-operator-os-8h` is still running,
  treat it as stale coordination unless it closes tasks with receipts.

## Existing Surfaces To Reuse

- `dharma_swarm/venture_cell/operator_os/`
- `dharma_swarm/venture_cell/darshan/`
- `dharma_swarm/venture_cell/darshan/external_reader_gate.py`
- `dharma_swarm/task_board.py`
- `dharma_swarm/operator_core/a2a_task_lifecycle.py`
- `dharma_swarm/operator_core/a2a_durable_projection.py`
- `dharma_swarm/operator_core/governed_work_admission.py`
- `dharma_swarm/operator_core/control_surface.py`
- `dharma_swarm/operator_core/control_surface_go.py`
- `dharma_swarm/daily_operating_brief.py`
- `dharma_swarm/chetana/`
- `scripts/runtime/autonomy_spine.py`
- `scripts/runtime/long_running_harness.py`
- `reports/venture_operator_os/20260602-8h/`

Allowed new surfaces:

- `dharma_swarm/venture_cell/operator_os/cli.py`
- `dharma_swarm/venture_cell/operator_os/live_loader.py`
- `dharma_swarm/venture_cell/operator_os/memory_kernel.py`
- tests scoped to those surfaces.

If a smaller change fits an existing module, prefer the existing module.

## Build Lanes

Use fixed lanes. If subagents are available, assign one lane per agent. If not,
execute serially and write lane receipts.

1. Mission control: baseline, stop conditions, touched-path declaration,
   ds-goal and long-harness receipts.
2. Live surface builder: load TaskBoard and A2A rows into Operator OS from
   explicit paths/state roots.
3. MemoryKernel builder: build the first read-through Chetana/wiki index or a
   fully specified implementation packet if indexing is too large for this run.
4. Operator surface builder: add one CLI or control-surface row and write JSON
   plus Markdown digest artifacts.
5. Adversary/verifier: attack false autonomy, privacy, fake liveness, dirty
   scope, and missing receipts.
6. Reporter: final report, scorecard, handoff, next 8h run packet.

## Phased Run

Phase 0, first 30 minutes:

- run onboarding and toolbelt checks;
- capture dirty tree and conflict state;
- read the current Operator OS digest;
- declare exact file scope.

Phase 1, hours 0.5-2:

- implement live loaders for TaskBoard and A2A queue rows;
- keep all inputs path-injected and read-only;
- add tests with temporary DB/state roots.

Phase 2, hours 2-4:

- add CLI or control-surface projection;
- write both JSON and Markdown digest artifacts under
  `reports/venture_operator_os/<run_id>/`;
- prove real current Darshan state remains blocked on external-reader gate.

Phase 3, hours 4-6:

- add MemoryKernel read-through snapshot/index over Chetana/wiki;
- bounded scan must not pretend to be nanosecond recall;
- if full index is too large, emit an implementation packet with tests and
  exact interfaces.

Phase 4, hours 6-8:

- run focused tests;
- run compile/static checks for touched package;
- write verifier matrix, adversary audit, build receipt, scorecard, and
  operator handoff;
- commit only scoped files if tests pass.

## Scorecard

Target: at least 70/100 by the end.

| Area | Points | Requirement |
|---|---:|---|
| Mission hygiene | 10 | baseline, dirty scope, receipts, no stale heartbeat claim |
| Live loaders | 15 | TaskBoard and A2A rows load through explicit paths |
| Operator surface | 15 | CLI or control-surface row plus JSON/Markdown digest |
| Governance | 15 | external-reader gate and governed admission block correctly |
| MemoryKernel | 15 | indexed/read-through Chetana/wiki plan or first implementation |
| Tests | 15 | focused pytest and compile checks pass |
| Reporting | 10 | verifier matrix, adversary audit, score, handoff |
| Commit discipline | 5 | scoped commit only; unrelated dirty tree preserved |

## Master `/goal` Prompt

Paste this into Codex `/goal` or use it as the `ds-goal init --goal` text.
Treat "Codex 5.5" as the local Codex executor label, not an official product
claim.

```text
/goal Run an 8h+ autonomous Dharma Swarm build mission: VentureCell Operator OS Level 70.

Mission:
Advance the committed Operator OS brick from about 52/100 to at least 70/100 by wiring a real operator-facing, receipt-backed company-OS surface over existing Dharma Swarm organs. Fuse Polsia ambition, Cofounder workspace structure, Karpathy-style LLM wiki memory, and Dharma governance. Do not clone Polsia or Cofounder. Do not create a new control plane.

Base:
- repo: /Users/dhyana/dharma_swarm
- commit anchor: 5d27d706 Add VentureCell Operator OS projection
- current digest: reports/venture_operator_os/20260602-8h/operator_os_digest.md
- current status: blocked_on_external_reader_gate
- current autonomy: L0_read_only_plan

Hard boundaries:
- no external outreach, spending, deploy, publish, push, merge, payment, credential mutation, or live authority claim
- no fake A2A/NATS liveness; filesystem receipts are evidence only
- no trusted Chetana promotion without Chetana gates
- no new runner, DB, queue, task board, dashboard substrate, router, or daemon
- preserve unrelated dirty work; never git add -A
- heartbeat is not progress; only artifacts, tests, receipts, and commits count

Opening ritual:
cd /Users/dhyana/dharma_swarm
export RUN_ID="venturecell-operator-os-level70-$(date -u +%Y%m%dT%H%M%SZ)"
mkdir -p "$HOME/.dharma/goal_runs/$RUN_ID" "reports/venture_operator_os/$RUN_ID"
git status --short --branch > "$HOME/.dharma/goal_runs/$RUN_ID/git_status_start.txt"
git diff --stat > "$HOME/.dharma/goal_runs/$RUN_ID/git_diff_stat_start.txt"
git diff --name-only --diff-filter=U > "$HOME/.dharma/goal_runs/$RUN_ID/conflicts_start.txt"
make onboard | tee "$HOME/.dharma/goal_runs/$RUN_ID/onboard_start.txt"
bash scripts/runtime/codex_toolbelt_status.sh | tee "$HOME/.dharma/goal_runs/$RUN_ID/toolbelt_start.txt" || true
make long-harness-init RUN_ID="$RUN_ID" MODE=brownfield RISK=Q2 MAX_ROUNDS=4 GOAL="VentureCell Operator OS Level 70: live local projection, memory kernel, receipts, verifier matrix" | tee "$HOME/.dharma/goal_runs/$RUN_ID/long_harness_init.txt" || true

Build lanes:
1 mission_control: baseline, scope, receipts, stale-runner truth
2 live_surface: TaskBoard and A2A loaders with injected paths/state roots
3 operator_surface: CLI or control-surface row plus JSON/Markdown digest writer
4 memory_kernel: Chetana/wiki read-through index or exact implementation packet
5 adversary_verifier: false-liveness, privacy, gate, dirty-scope, and receipt tests
6 reporter: final scorecard, verifier matrix, handoff, next packet

Required outputs:
- live local Operator OS digest under reports/venture_operator_os/$RUN_ID/
- one CLI or control-surface path to render the projection
- tests for TaskBoard/A2A loaders and blocked external-reader state
- MemoryKernel read-through index or build packet
- verifier_matrix.md, adversary_audit.md, build_receipt.md, operator_handoff.md
- scoped commit only if focused tests pass

Minimum verification:
pytest -q tests/test_venture_cell_operator_os_projection.py
pytest -q tests/test_darshan_external_reader_gate.py tests/test_control_surface.py -k 'GoReceiptRows or external_reader'
pytest -q tests/test_governed_work_admission.py tests/test_a2a_task_lifecycle.py tests/test_daily_operating_brief.py
python -m compileall -q dharma_swarm/venture_cell/operator_os

Stop if live external authority is required, if touched paths collide with unrelated dirty work, if tests require weakening a gate, or if the run cannot produce an artifact within 90 minutes.
```

## Launch Commands

Use a fresh mission id. Do not reuse the stale `20260602-venturecell-operator-os-8h`
runner.

```bash
ds-goal init \
  --mission-id 20260602-venturecell-operator-os-level70 \
  --owner codex \
  --risk Q2 \
  --mode build \
  --goal "$(sed -n '/^```text$/,/^```$/p' docs/plans/2026-06-02-venturecell-operator-os-8h-autonomous-build-spec.md | sed '1d;$d')"

ds-goal run \
  --mission-id 20260602-venturecell-operator-os-level70 \
  --duration-hours 8 \
  --verify-every-minutes 20 \
  --lease-minutes 90 \
  --sleep-seconds 90 \
  --max-dispatch 1 \
  --agents codex \
  --dispatch-mode tmux \
  --agent-command 'codex=codex exec --dangerously-bypass-approvals-and-sandbox -C /Users/dhyana/dharma_swarm --add-dir /Users/dhyana/.dharma - < {prompt_path}'
```

## Expected Finish State

- DS has a real local Operator OS surface, not only a projection module.
- The system still refuses external growth/comms until the external-reader Go
  receipt exists.
- Agents can inspect the VentureCell state through one command/surface.
- MemoryKernel work is either implemented as a bounded read-through index or
  reduced to a precise next build packet.
- Every claim has a receipt path, test output, or explicit blocker.
