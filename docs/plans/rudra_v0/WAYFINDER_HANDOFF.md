# Wayfinder handoff — RUDRA v0

## Route ruling

Wayfinder's early-exit applies: the destination and irreversible technical
choices are already sharp enough for one governed build program. Creating an
issue-map now would add a second planning surface without reducing material
fog. This handoff is the decision capsule; `WORK_PACKET_DAG.yaml` is the
execution decomposition. No tracker was mutated.

The companion `/domain-modeling` skill required by the Wayfinder charting route
is not installed in this environment. The domain map below was therefore
derived directly from the pinned implementation and names each existing owner
instead of inventing a replacement model.

## Destination

Ship a trusted-operator, single-host RUDRA v0 that accepts one immutable coding
mission, creates one exact-base private Git workcell, drives one pinned Codex
app-server thread, survives supervisor or app-server death, and emits
`COMPLETE_REPRODUCED` only after an independent verifier passes against the
exact candidate commit and admitted contract.

The build is proven by three real RUDRA attempts versus three bare one-turn
app-server baselines, with a matched force-kill in each arm. A green result with
no valid patch, a stale test result, a changed test, an unauthorized write, a
surviving orphan process, or a model merely saying “done” is a failed
destination.

## Decisions so far

### Build the missing join, not a new substrate

RUDRA owns only the hot loop joining persistent context, coding tools, exact
workspace identity, recovery, and executable verification. It does not own a
new task board, scheduler, event bus, receipt spine, memory system, hypervisor,
or general orchestration framework.

### One workcell before a swarm of workcells

The implementation team works in parallel. The product v0 runs one supervisor,
one model thread, and one workcell. This isolates causality and makes recovery
falsifiable. After 30 replayable missions, a two-workcell DAG may be earned by
measured closure or wall-time improvement.

### GoalGate owns terminal truth

The model can report completion. Only GoalGate can reproduce it. Verifier
commands, path policy, budgets, base SHA, and acceptance digest are normalized
and frozen before execution. A verifier must be freshly run by the supervisor
against the final candidate commit.

### The private workcell is truth; the thread is context

Private Git state survives model-server failure and can be independently
inspected without mutating the base repository's Git directory. Thread history
is useful but discardable. Recovery always kills or proves dead the former
process tree, reconciles Git, and runs GoalGate before resuming or starting a
compact replacement thread.

### Use Codex app-server, not disposable CLI turns

The installed Codex 0.147.0 schema exposes `thread/start`, `thread/resume`,
`turn/start`, `turn/interrupt`, token notifications, and aggregate diff. RUDRA
uses only that narrow JSON-RPC surface. It never invokes the schema's explicitly
unsandboxed `thread/shellCommand`, never calls `command/exec`, and denies every
unexpected approval or dynamic-tool request.

### Separate provider egress from tool egress

Codex may contact its configured model service. Commands launched for the
mission have network denied. A launch canary proves model-visible tools cannot
read provider credentials. There are no mission secrets, dependency installs,
external actions, or hostile inputs in v0.

### A mission journal is not a task store

An append-only, fsynced JSONL file outside the model's writable root records
sequenced intent and result events for process-crash recovery. It deliberately
does not claim tamper evidence against the same host user. It does not own
mission priority, portfolio state, or task assignment. Mission Control and
RuntimeStateStore remain later projection owners after the local proof.

### Use `dgc rudra`, not `dgc mission`

The existing repository already uses “mission status” for structural inventory.
The new commands are `dgc rudra run`, `dgc rudra status`, and `dgc rudra stop`
so reproduced execution truth cannot be confused with present structural
status.

### Candidate commit is the completion subject

After the first green verification, the supervisor stages only admitted paths,
creates a local reversible candidate commit, and reruns the complete gate
from a fresh detached verification workcell at that clean commit. Any verifier
repository mutation invalidates the result. The tuple
`(candidate_sha, contract_digest, verifier_run_id)` is the exact subject of
reproduced completion. No push or merge follows automatically.

### Governance is two joins, not a new campaign

At assessment base the portfolio is 10/10 and RUDRA surfaces are unowned. A
small human-ratified ownership amendment must merge first. The recommended home
is the existing `organism-rewire-2026-07` track because it already owns
RuntimeStateStore and hosted the Mission Control packets. The build then lands
as a separate PR from a fresh exact base. The first real repair is a later
Titanium-owned candidate and must receive its own scoped admission.

## Native domain map

| Concept | Existing/new owner | RUDRA relationship |
|---|---|---|
| Portfolio intent and surface authority | `docs/governance/ACTIVE_TRACK.yaml` | Admission prerequisite; never inferred from this spec |
| Task and mission projection | `TaskBoard`, `MissionControl` | Deferred projection; cannot make GoalGate green |
| Runtime identity and receipts | `RuntimeStateStore`, `ExecutionIdentity` | Adapt after v0 proof; no schema change in v0 |
| Immutable acceptance | New `RudraMissionContract` + `GoalGate` | RUDRA-owned, mission-specific evaluator |
| Execution workspace | Private Git directory + RUDRA workcell metadata | Exact mutable subject; base Git metadata remains untouched |
| Model context and tools | Pinned Codex app-server thread | Powerful executor; never completion authority |
| Recovery ordering | Mission-level OS lock + sequenced journal + sole ProcessOwner | Process-crash evidence, not a scheduler/task database |
| Final candidate | Local Git commit | Exact subject of fresh verification; reversible and not published |
| Terminal projection | Later `MissionControl` adapter | Idempotent reflection of reproduced local truth |

```text
operator-authored contract
          |
          v
      [GoalGate] ---- freezes ----> acceptance digest
          |                              |
          v                              |
  [single MissionRunner]                 |
       /          \                      |
      v            v                     |
[Git workcell] [Codex thread]            |
      |            |                     |
      +---- diff --+                     |
      |                                  |
      +---- fresh verifier <-------------+
                      |
            green exact candidate
                      |
                      v
          COMPLETE_REPRODUCED
                      |
             later projection only
                      v
               Mission Control
```

## Remaining decision tickets

These are empirical gates, not invitations to redesign the system.

### Ratify RUDRA ownership and scope — human decision

Approve the narrow `organism-rewire-2026-07` amendment, or explicitly select a
different existing track/retire one. Silence is not admission. No product edit
starts before the amendment merges.

### Prove app-server restart semantics — autonomous spike

On the launch base and installed binary: initialize, start thread, complete a
turn, observe token/diff events, kill server, restart, and resume. If resume is
not reliable, v0 uses a fresh thread with a compact verified handoff. It does
not build a session service.

### Prove macOS containment and process death — autonomous spike

Show an allowed mutation-workcell write, denied unauthorized write, denied
provider-credential read, denied tool network, timeout interruption, supervisor
SIGKILL, app-server death, `setsid` escape probe, descendant enumeration, and
zero remaining descendants. Any ambiguous old process yields
`RECOVERY_REQUIRED` and blocks a new turn.

### Bind one runtime environment — autonomous task

Record the resolved interpreter, `sys.path`, `.pth` files, installed distribution
RECORD digests, import origins, pytest plugins, absolute tool paths, and lockfile
digest. A fresh workcell does not contain the dirty checkout's untracked
virtualenv, so v0 uses a read-only, pre-existing interpreter environment and
performs no dependency installation.

### Revalidate the first repair — autonomous task

Prove the proposed NEW-12 verifier is red at the admitted base. If it is stale,
select another one-file, deterministic, fast, baseline-red repair without test
changes. `ALREADY_SATISFIED` is not a RUDRA win.

## Only legitimate v0 fog

The precise compact-handoff payload remains deliberately unspecified until the
restart spike establishes what app-server can resume. It may contain only the
frozen objective, base and contract digests, current candidate diff summary,
latest fresh verifier failures, consumed budget, and remaining budget. It may
not summarize an unverified claim as fact.

## Out of scope

- custom VMM, custom container runtime, or custom deterministic replay engine;
- raw third-party/cyber tasks, secret-bearing work, dependency installation, or
  unrestricted network;
- external send, spend, publish, deploy, push, merge, or account action;
- Mission Control as terminal authority;
- NATS/Temporal/cron/graph runtime in the execution hot path;
- model council, judge vote, self-grading, or LLM-as-terminal-verifier;
- self-evolution or automatic mutation of RUDRA;
- dashboards and long-lived daemonization;
- multi-model candidate tournaments before the single trajectory passes its A/B
  gate.

## Route kill rule

Delete the wrapper and retain GoalGate if RUDRA fails to improve verified
closure or recovery over direct Codex, if it costs more than 2× tokens, or if
one real repair requires another scheduler, task store, authority layer, or
session framework. Power is measured in verified closure, time, tokens, human
attention, recovery, and blast radius—not number of components.
