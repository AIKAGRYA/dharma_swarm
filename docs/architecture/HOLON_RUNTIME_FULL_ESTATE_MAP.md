---
title: Holon Runtime Full Estate Map
date: 2026-07-13
status: reference
---

# Holon Runtime Full Estate Map

> **Deprecated as first/current orientation (2026-08-03).** Start at
> [`../persistent_agents/README.md`](../persistent_agents/README.md); this remains a dated July deep reference.
> The full deprecation record is in Section 12 below.

For current operating state, run `make onboard` and `make organism-status`, then
inspect `docs/state/LIVE_OPS_DASHBOARD.md`. This dated file does not own present
state. The ownership rule is recorded in `docs/governance/CANONICAL_DOC_STACK.md:3-12`
and `:20-28`.

Use it to answer:

- Where does a persistent agent or sovereign holon actually get its body?
- Which repo files should be edited for identity, model routing, wake cycles,
  authority, A2A, gateways, receipts, health, and supervision?
- Which files under `~/.dharma` are mutable evidence rather than source?
- Which files under `~/.hermes` belong to a parallel upstream product or local
  sidecar rather than dharma_swarm?
- Which recent branches and PRs are landed, unlanded, stale, or blocked?
- What has been proved, and what is still required before an agent may be called
  alive?

[`AGENT_HOLON_CODE_MAP.md`](AGENT_HOLON_CODE_MAP.md) is a short call-chain index;
both it and this dated map are subordinate to `docs/persistent_agents/README.md` for subject
navigation. `docs/sarathi_apex_build/` owns dated build history and
`docs/sovereign_holons/` preserves research; neither owns current body truth.

## 1. Authority and freshness contract

Keep these layers separate:

| Layer | Authority | What belongs there | What it cannot prove |
| --- | --- | --- | --- |
| Executable implementation | `dharma_swarm/`, `api/`, `scripts/`, `tests/` in the current main lineage | Behavior, schemas, tests, launch helpers | That any process is deployed, fresh, or useful |
| Declared surface catalog | `ACTIVE_SURFACE_MANIFEST.yaml` | Active/projection/adapter/research/frozen classification | Executable behavior or live deployment |
| Mutable Dharma runtime | `~/.dharma/` | Identities, prompts, inboxes, leases, heartbeats, receipts, ledgers, DBs, process state | Canonical source ownership or implementation quality |
| Parallel Hermes product | `~/.hermes/hermes-agent/` | The local checkout of NousResearch Hermes Agent | That Dharma holons use its cognition or lifecycle |
| Local Hermes sidecars | `~/.hermes/scripts/` | Machine-local A2A compatibility and dispatch helpers | Upstream support, repo ownership, or a durable Dharma service |
| Historical intent | old branches, worktrees, proposals, dated docs | Design lineage and recoverable ideas | Current-main behavior or production readiness |

Code and tests win implementation disputes; live state remains owned by the
onboarding render and Live Ops Dashboard
(`docs/governance/CANONICAL_DOC_STACK.md:20-28,121-131`). A receipt can prove
only the event it binds. A heartbeat, PID, tmux session, identity file, pulse
document, model consensus, or social identity does not prove semantic work or
standing authority.

Static paths in this map must be refreshed when their owners move. Live evidence
is a dated witness only and should be re-probed after 24 hours or any deploy.

### Demotion record

Affected documents: `AGENT_HOLON_CODE_MAP.md`,
`docs/sarathi_apex_build/{README,01_CURRENT_STATE,02_CODEBASE_RUNTIME_BOUNDARY,03_HOLON_SYSTEM_CODE_MAP,04_PERSISTENT_AGENT_RELATION,05_SARATHI_APEX_MAP,06_PROOF_GATES}.md`,
and `docs/sovereign_holons/{README,INDEX,MAP,STATE_OF_TRUTH}.md`.

```text
Deprecated: 2026-07-13
Reason: overlapping code maps and dated live-state prose competed with current-main source and live-state owners.
Replacement: this file for holon-specific body synthesis; make onboard and docs/state/LIVE_OPS_DASHBOARD.md for current operating state.
Review / removal date: 2026-08-13 (review only; retain useful historical context unless duplication has no remaining value).
```

## 2. Executive verdict

The system has many real and well-tested organs, but they are not yet composed
into one durable Hermes-class organism.

| Question | Current answer | Evidence |
| --- | --- | --- |
| Can a registered holon load its own identity and model? | Yes | `dharma_swarm/holon_bridge.py:106-149`; scoped test command in Section 9 |
| Can it answer as itself through a live model? | Yes, from a repo checkout | Exact dialogue and packaging probes in Section 9; packaging contract at `pyproject.toml:58-64` |
| Can it wake and choose a next action? | Partially | `scripts/holon_run.py:32-87`; exact live proposal probe in Section 9 |
| Can the direct holon path execute a typed, lease-backed, budgeted effect? | No end-to-end proof | Composition check below plus `scripts/holon_run.py:66-87` |
| Can it bind an effect to an independent verifier and runtime/A2A receipt? | Not on the direct path | `rg -n 'ExecutionLease|RuntimeState|task_receipt|a2a' scripts/holon_run.py` returns no join |
| Is a canonical supervisor running a current-main semantic seat? | Not in the dated witness | Exact process/tmux/heartbeat probes in Section 7 |
| Does Sarathi source currently claim `wake_loop_active=true` or `alive_claim=true`? | No | `dharma_swarm/holon_system/sarathi/gateway.py:15-24` and `pulse.py:12-25` |

By the proposed six-stage proof model below, the direct Sarathi path has evidence
for the first three stages and none for the final three. Stage count is not a
linear percentage: effect, receipt binding, and durable service are the
load-bearing half. No audited seat reached the terminal stage in the dated live
witness in Section 7.

The shortest evidence-backed summary is: **identity, dialogue, and proposal are
real; governed effect and durable service remain unproved**.

## 3. Proposed typed promotion model — not enforced

The target design is to make liveness a promoted capability rather than an
adjective in an identity file. This is a proposed language/runtime contract,
not a description of current enforcement:

```text
IdentityPresent
  -> DialogueProven
  -> ProposalCycleProven
  -> GovernedEffectProven
  -> ReceiptBound
  -> DurableServiceProven
```

| Type | Minimum proof obligation |
| --- | --- |
| `IdentityPresent` | A valid canonical identity and prompt load through `load_holon` |
| `DialogueProven` | A live model response using that identity, with a durable dialogue receipt |
| `ProposalCycleProven` | A wake cycle proposes a concrete next action and persists the cycle |
| `GovernedEffectProven` | A typed action passes authority, reversibility, execution-lease, and live-budget checks before a bounded real effect |
| `ReceiptBound` | The effect, independent verifier artifact, task claim, transport acknowledgement, and durable receipt refer to the same execution identity |
| `DurableServiceProven` | A canonical-build supervisor sustains semantic work, survives kill/restart, resumes correctly, and keeps fresh success heartbeats during burn-in |

If adopted, only `DurableServiceProven` would permit `wake_loop_active=true` or
an `alive` claim. Current code is weaker: `proof_gate_summary` allows an alive
claim from `sprawl_guard_clean && wake_loop_active`
(`dharma_swarm/holon_system/observability/proof_gates.py:6-11`), while the
shared wake shell sets `wake_loop_active` when tmux `send-keys` succeeds
(`scripts/runtime/codex_composer_wake_loop.py:1213-1257`). Those contradictions
are closure work, not hidden implementation.

The exact live commands in Section 9 established Sarathi dialogue and one
proposal cycle on 2026-07-13; they did not establish a governed effect.

The small language-design contribution is the proposed rule: the claim type
would determine which authority-bearing operations are available, and a raw
boolean could not promote itself.

## 4. Canonical repo-owned body

### 4.1 Direct sovereign-holon path

Primary source anchors are `dharma_swarm/holon_bridge.py:106-168,198-241`,
`dharma_swarm/holon_runtime.py:45-190,229-274`,
`dharma_swarm/holon_persistence.py:32-93`,
`dharma_swarm/holon_health.py:49-78`, `scripts/holon_talk.py:107-166`, and
`scripts/holon_run.py:32-87`.

| Owner | Role | Current reality |
| --- | --- | --- |
| `dharma_swarm/holon_bridge.py` | Validate/load identity and prompt; resolve providers; build read-only dialogue requests | Canonical record-to-model bridge |
| `dharma_swarm/holon_runtime.py` | Kill, budget, optional reversibility classification, injected work, compass, persistence | Real tested cycle primitive; not a complete executor |
| `dharma_swarm/holon_persistence.py` | Append/replay `holon_events.jsonl` | Real but fail-open at the caller and not concurrency-safe |
| `dharma_swarm/holon_health.py` | Project registration, model, kill state, compass count | Health summary, not process or semantic liveness |
| `dharma_swarm/holon_killswitch.py` | Durable operator kill marker | Real enforcement primitive |
| `dharma_swarm/holon_budget_guard.py` | Stop at a positive cost cap | `cap_usd <= 0` explicitly disables enforcement |
| `dharma_swarm/holon_compass.py` | Record a non-binding telos signal | Evidence only; not an authority gate |
| `scripts/holon_talk.py` | Live terminal dialogue and compact receipt | Works only while `scripts` is importable from the checkout |
| `scripts/holon_run.py` | Live model-backed proposal loop | Proposes an action; does not execute it |
| `dharma_swarm/terminal_commands/agents.py` | `dgc agent talk/run/status/kill/list` handlers | Imports the top-level `scripts` package at runtime |
| `api/routers/holon.py` | `/holon/{name}/chat` streaming route | Own-model chat, but not yet the safest bridge composition |

Current talk path:

```text
dgc agent talk <name> <message>
  -> dharma_swarm.terminal_commands.agents
  -> scripts.holon_talk.talk
  -> dharma_swarm.holon_bridge.load_holon
  -> runtime provider resolution
  -> provider.stream(LLMRequest)
  -> ~/.dharma/agents/<name>/talk_receipts.jsonl
```

Current run path:

```text
dgc agent run <name> --cycles N
  -> scripts.holon_run.run
  -> load_holon + provider resolution
  -> ask model for a one-sentence proposed next action
  -> holon_runtime.run_holon_loop(cap_usd=0.0)
  -> kill check -> disabled budget check -> model proposal -> compass -> JSONL
```

That run is a real identity/model/proposal/persistence loop, but it is not a
governed effect loop:

```bash
rg -n 'planned_action|spend_fn|ExecutionLease|RuntimeState|task_receipt|a2a' \
  scripts/holon_run.py
```

- `SELF_TASK` asks only for the next action and why; no action executor is called
  (`scripts/holon_run.py:32-62`).
- No concrete `planned_action` is passed to `run_holon_loop`, so the
  reversibility gate is not exercised by the live CLI
  (`scripts/holon_run.py:73-75`; `dharma_swarm/holon_runtime.py:99-118`).
- No `spend_fn` is supplied and `cap_usd=0.0` means unbounded, not free
  (`scripts/holon_run.py:73-75`; `dharma_swarm/holon_budget_guard.py:25-31`).
- No `ExecutionLease` is acquired or validated (composition check above).
- The CLI's final `LIVE & governed` label therefore overstates what this path
  proves; interpret it as live model-backed proposal generation
  (`scripts/holon_run.py:85-87`).
- `_persist` catches all persistence failures, so `ran` does not guarantee a
  durable receipt (`dharma_swarm/holon_runtime.py:45-50`).
- JSONL cycle numbers use read-count-append without a writer lock
  (`dharma_swarm/holon_persistence.py:32-60`).
- The direct cycle is not projected into the runtime truth/A2A receipt chain
  (composition check above).

The API path also has a concrete integration gap. `api/routers/holon.py:43-89` calls
`get_holon_provider`, while the bridge already provides the safer
`get_holon_dialogue_provider` and `build_livingdock_dialogue_context`
(`dharma_swarm/holon_bridge.py:198-241,277-305`). The route
does pass request history, but it does not compose those safety/context helpers
or write the normalized holon receipt shape. Existing route tests patch the
general resolver at `tests/test_holon_route.py:30,72,87`.

### 4.2 Model/provider routing

The one repo-owned provider door is the composition of:

- `dharma_swarm/api_keys.py`
- `dharma_swarm/runtime_env_loader.py`
- `dharma_swarm/runtime_provider.py`
- `dharma_swarm/model_hierarchy.py`
- `dharma_swarm/model_defaults.py`
- `dharma_swarm/model_pool.py`
- `dharma_swarm/evolution_roster.py`
- `dharma_swarm/providers.py`
- `docs/ops/MODEL_KEY_ROUTING.md`

New holon code must use this door. Raw environment-key routing in runtime
wrappers or sidecars is not a second authority.

Behavior anchors: provider resolution, construction, and free-first ordering are
at `dharma_swarm/runtime_provider.py:191-265,523-561,698-741`. Reproduce the
inventory with:

```bash
for f in api_keys.py runtime_env_loader.py runtime_provider.py model_hierarchy.py \
  model_defaults.py model_pool.py evolution_roster.py providers.py; do \
  test -f "dharma_swarm/$f" || echo "missing: $f"; done
```

### 4.3 Living Agent Kernel and authority primitives

The more complete persistent-service substrate is real and tested under:

- `dharma_swarm/operator_core/living_agent_kernel.py`
- `living_agent_kernel_activation.py`
- `living_agent_kernel_promotion.py`
- `living_agent_kernel_provider_worker.py`
- `living_agent_kernel_recovery.py`
- `living_agent_kernel_service.py`
- `living_agent_kernel_status.py`
- `living_agent_kernel_supervisor.py`
- `living_agent_kernel_workers.py`
- `dharma_swarm/operator_core/execution_lease.py`
- `dharma_swarm/operator_core/reversibility_gate.py`

Thin operator wrappers live in `scripts/runtime/living_agent_kernel_*.py`.
This substrate is not composed into `scripts/holon_run.py`; the direct holon
loop and the Living Agent Kernel remain two adjacent lifecycle bodies.

Behavior anchors: `LivingAgentKernel` is at
`dharma_swarm/operator_core/living_agent_kernel.py:1199`; lease validation is at
`dharma_swarm/operator_core/execution_lease.py:187-271`; reversibility
classification is at `dharma_swarm/operator_core/reversibility_gate.py:164-239`.
Reproduce the inventory with
`rg --files dharma_swarm/operator_core scripts/runtime | rg 'living_agent_kernel|execution_lease|reversibility_gate' | sort`.

### 4.4 A2A transport, semantic work, and receipts

The package-layer inventory is:

- `dharma_swarm/a2a/a2a_server.py`, `a2a_client.py`, `a2a_bridge.py`
- `spine_adapter.py`, `nats_transport.py`, `node_gateway.py`,
  `mailbox_gateway.py`
- `agent_card.py`, `agent_directory.py`, `agent_presence.py`
- `contact_registry.py`, `node_registry.py`, `registry_hydrator.py`
- `task_receipt.py`, `a2a_cloud_contact.py`, `verifier.py`

The script-shaped operational layer is:

- `scripts/runtime/a2a_send.py`
- `a2a_inbox_bridge.py`
- `a2a_reply_capture.py`
- `a2a_domain_reply_worker.py`
- `a2a_domain_reply_artifact.py`
- `a2a_doctor.py`, `a2a_topology.py`, `a2a_gateway_server.py`

The source inventory and the 250-test invocation in Section 9 cover substantial
transport/evidence behavior; they do not prove that every named agent has a
semantic responder. There is also a deployed-contract split:

- formal target: `DS_TASKS` and `DS_DLQ`;
- compatibility surfaces: `DHARMA_A2A`;
- observed worker configuration still includes `DHARMA_FLEET`.

The streams must converge before one end-to-end production claim can cover the
whole path.

Core behavior anchors are `dharma_swarm/a2a/a2a_server.py:315`,
`dharma_swarm/a2a/a2a_client.py:86`, and
`dharma_swarm/a2a/nats_transport.py:69-70,115`. Reproduce the listed inventory
with `rg --files dharma_swarm/a2a scripts/runtime | rg 'a2a|mailbox|agent_(card|directory|presence)|registry|task_receipt|verifier' | sort`, and reproduce the
stream split with `rg -n 'DS_TASKS|DS_DLQ|DHARMA_A2A|DHARMA_FLEET' dharma_swarm/a2a scripts/runtime scripts/governance`.

### 4.5 Legacy and adjacent lifecycle

Do not delete or call these dead:

| Owner | Current role |
| --- | --- |
| `dharma_swarm/swarm.py` | Full swarm composition and coordination |
| `dharma_swarm/agent_runner.py` | Generic worker execution and pool substrate |
| `dharma_swarm/autonomous_agent.py` | Older ReAct/autonomous body; used by `dgc agent wake` |
| `dharma_swarm/persistent_agent.py` | Older periodic wake loop |
| `dharma_swarm/agent_registry.py` | Ginko-era registry, prompt evolution, and bookkeeping |

`dgc agent wake` enters the direct `AutonomousAgent` lineage, while
`dgc agent talk/run` enters the direct holon lineage. That dual lifecycle is an
integration fact, not merely a documentation problem.

Class anchors are `dharma_swarm/swarm.py:109`,
`dharma_swarm/agent_runner.py:1612`, `dharma_swarm/autonomous_agent.py:386`,
`dharma_swarm/persistent_agent.py:117`, and
`dharma_swarm/agent_registry.py:201`. More precisely, `dgc agent wake` directly
constructs `AutonomousAgent` (`dharma_swarm/terminal_commands/agents.py:42-45`;
`dharma_swarm/autonomous_agent.py:1483-1509`); it does not traverse the other
four bodies.

### 4.6 `dharma_swarm/holon_system/` is a facade

The 43 Python files in `dharma_swarm/holon_system/` total roughly 360 lines.
Most are three-to-five-line re-exports or inventory helpers. There are no
production consumers outside the facade itself.

Use it as a navigation and future composition boundary, not as evidence that a
new runtime exists. In particular, `holon_system/sarathi/` provides read-only
gateway, pulse, roster, brief, and scoreboard projections. Its honest defaults
are `wake_loop_active=false` and `alive_claim=false`; it has no model loop,
executor, persistence service, or semantic responder of its own.

Several modules named by older maps are absent from current main, including
`holon_service_liveness.py`, `holon_canonical_state.py`,
`holon_truth_projection.py`, dedicated Codex/Fugu semantic responder modules,
and an A2A resident executor. Do not plan against them as if they had landed.

Reproduce the facade/absence claims with:

```bash
find dharma_swarm/holon_system -type f -name '*.py' -print0 | xargs -0 wc -l
rg -n 'dharma_swarm\.holon_system' --glob '*.py' . | \
  rg -v '(^|/)tests/|dharma_swarm/holon_system/' || true
for f in dharma_swarm/holon_service_liveness.py \
  dharma_swarm/holon_canonical_state.py dharma_swarm/holon_truth_projection.py \
  scripts/runtime/codex_composer_semantic_responder.py \
  scripts/runtime/fugu_ultra_semantic_responder.py \
  scripts/runtime/a2a_resident_executor.py; do test -e "$f" && echo "$f"; done
rg -n 'provider|stream|persist|responder' dharma_swarm/holon_system/sarathi || true
```

### 4.7 Parallel and lookalike entry points

| Surface | Actual role | Evidence |
| --- | --- | --- |
| `POST /agents/{agent_id}/chat` | Builds a cosmetic persona and calls generic `_agentic_stream`; not sovereign-holon chat | `api/routers/agents.py:423-515` |
| `scripts/runtime/codex_composer_wake_loop.py` | Shared manual wake/control shell for Codex, Fable, and Sarathi profiles | `scripts/runtime/codex_composer_wake_loop.py:1-13,53-137` |
| `scripts/runtime/autonomy_spine.py` | Bounded `ds-goal` compatibility CLI over Living Agent Kernel; explicitly not a daemon | `scripts/runtime/autonomy_spine.py:1-8,26-38` |
| `dharma_swarm/orchestrate_live.py` | Whole-swarm daemon entry, including `SwarmManager` and conductor `PersistentAgent` paths | `dharma_swarm/orchestrate_live.py:1-20,202-215,1573-1608,1986-2274` |

These are operator-visible or alternate entries, but none is the direct
`dgc agent talk/run` composition shown in Section 4.1.

## 5. Mutable Dharma runtime: `~/.dharma`

Reproduce the top-level inventory without reading secret contents:

```bash
find ~/.dharma -mindepth 1 -maxdepth 2 -type d | sort
find ~/.dharma/agents -mindepth 1 -maxdepth 1 -type d | wc -l
test -d ~/.dharma/agents/hermes-m5 && echo hermes-m5
test -d ~/.dharma/agents/hermes_m5 && echo hermes_m5
```

### 5.1 What to inspect

| Runtime path | Meaning | Authority warning |
| --- | --- | --- |
| `~/.dharma/agents/<name>/` | Current identity, active prompt, LivingDock state, dialogue/cycle receipts, heartbeats, artifacts | Identity proves presence only; normalize names before joining data |
| `~/.dharma/a2a_bus/` | Filesystem tasks/inboxes, bridge state, heartbeats, receipts, projections | A projection or queued file is not semantic completion |
| `~/.dharma/a2a/` | A2A cards and task logs | Overlaps `a2a_bus`; inspect both during incident work |
| `~/.dharma/ginko/agents/` | Older registry identities and prompt-evolution state | Legacy authority for the old lifecycle, not direct holons |
| `~/.dharma/external_agents/` | External registration records | Registration is not runtime enforcement |
| `~/.dharma/db/`, `~/.dharma/state/runtime.db` | Large runtime and truth stores | Query schema/receipts; file presence says nothing |
| `~/.dharma/ledgers/`, `logs/`, `sessions/`, `cron/` | Evidence and machine-local operations | Generated and mutable |

As of the dated audit, 65 agent-home directories existed and the normalized naming
collision `hermes-m5` versus `hermes_m5` remained unresolved. Counts and sizes
are operational context, not a readiness metric.

### 5.2 Source-like files that are not canonical source

Treat these as wrappers or drift candidates:

- `~/.dharma/bin/`
- `~/.dharma/scripts/`
- `~/.dharma/cron/scripts/`
- `~/.dharma/agents/sarathi/gateway/sarathi_gateway.py`
- Codex supervisor/interface/wake scripts beneath its agent home
- Fable wake/harness/plist files beneath its agent home

If a machine-local script is required for the product, first give it a versioned
repo owner, tests, packaging, and a deploy mechanism. Copying it into an agent
home does not make it canonical.

Reproduce this source-like inventory with:

```bash
for p in ~/.dharma/bin ~/.dharma/scripts ~/.dharma/cron/scripts \
  ~/.dharma/agents/sarathi/gateway/sarathi_gateway.py; do \
  test -e "$p" && echo "$p"; done
find ~/.dharma/agents/codex_composer ~/.dharma/agents/fable_composer \
  -maxdepth 3 -type f 2>/dev/null | rg '\.(py|sh|plist)$' | sort
```

## 6. Parallel Hermes ecosystem: `~/.hermes`

`~/.hermes/hermes-agent/` is a separate NousResearch Hermes Agent checkout. At
the audit it reported version 0.18.2, was behind its upstream, and had substantial
tracked and untracked local changes. It is a comparison product and possible
peer, not the source body for Dharma holons.

Reproduce those checkout observations with:

```bash
git -C ~/.hermes/hermes-agent describe --tags --always
git -C ~/.hermes/hermes-agent rev-list --left-right --count HEAD...@{upstream}
git -C ~/.hermes/hermes-agent status --short
```

`~/.hermes/scripts/` contains local, unversioned sidecars such as:

- `hermes_a2a_server.py`
- `a2a_dispatch.py`
- `dharma_bridge.py`

Reproduce that inventory with
`find ~/.hermes/scripts -maxdepth 1 -type f -print | sort`.

A local Hermes A2A compatibility server was listening during the audit. That
proves only the sidecar endpoint. No fresh upstream Hermes gateway proof or
receipt-bound Dharma semantic execution was established.

Re-probe the process boundary with
`ps -axo pid,lstart,command | rg 'hermes_a2a_server|hermes_cli.*gateway'` and
`lsof -nP -iTCP:8421 -sTCP:LISTEN`.

Never edit `.hermes` to fix the Dharma body. Port a required bridge into a
versioned owner or explicitly maintain it as a machine-local compatibility
surface with a bounded contract.

## 7. Dated seat-by-seat witness

Snapshot: 2026-07-13 JST. Re-probe before operational decisions.

The table is a dated witness produced by these read-only probes, not the owner of
live state:

```bash
ps -axo pid,lstart,command | rg 'orchestrate-live|nats-server|hermes_a2a_server|codex_composer|fugu|fable|palantir|sarathi'
tmux list-panes -a -F '#S #{pane_current_path} #{pane_start_command}'
for seat in sarathi codex_composer fugu_ultra fable_composer; do \
  test -f "$HOME/.dharma/agents/$seat/identity.json" && echo "$seat identity"; done
wc -l scripts/runtime/codex_composer_wake_loop.py
tail -n 3 ~/.dharma/agents/codex_composer/service_heartbeats.jsonl
find ~/.dharma/a2a_bus/bridge_heartbeats ~/.dharma/a2a_bus/worker_heartbeats \
  -maxdepth 2 -type f -print 2>/dev/null | sort
find ~/.dharma/agents/fugu_ultra -maxdepth 3 -type f -print0 2>/dev/null | \
  xargs -0 stat -f '%m %N' | sort -nr | head
git -C /Users/dhyana/dharma_swarm status --short
lsof -nP -iTCP:4222 -sTCP:LISTEN
```

| Seat | Identity/body | Observed service evidence | Honest verdict |
| --- | --- | --- | --- |
| Sarathi | Canonical identity, direct talk/run, shared wake profile, facade projections | Live talk and one proposal cycle passed; timer ran from an older worktree; source flags are false (`dharma_swarm/holon_system/sarathi/gateway.py:15-24`) | Dated witness reaches the proposed `ProposalCycleProven`, not durable service |
| Codex Composer | Shared 1,401-line wake shell plus agent-home wrappers | Process present; latest service heartbeat was `error`; no fresh model/provider or semantic success receipt | Shell/process present, semantic service unproved |
| Fugu | Identity/cards and bridge/poller surfaces | Responder process present but no fresh semantic work since 2026-07-02 | Stale semantic proof |
| Fable | Shared wake profile, identity, manual workspace artifacts | No current responder or inbox bridge | Scaffold/profile only |
| Palantir | A2A worker and tmux process | Poller process was observed; no semantic receipt was established by these probes | Transport worker only |
| Hermes-m5 | Parallel Hermes checkout and local A2A sidecar | Sidecar endpoint present | Peer/compatibility surface, not a Dharma holon body |

The main `orchestrate-live` daemon observed during the audit was started from
the dirty `/Users/dhyana/dharma_swarm` checkout rather than a clean current-main
build. NATS JetStream was reachable, but the production evidence check was stale
and readiness was degraded. These are deployment-provenance blockers even when
the individual processes are running.

## 8. Recent work reconciliation

Reproduce local lineage and current remote review state with:

```bash
git show -s --format='%H %cs %s' 0beef7584 d3e084c66 c14b950bc 15c0b5ad2
git branch -a --contains e7856fed9
for pr in 821 868 878 904; do
  gh pr view "$pr" --json number,state,isDraft,mergedAt,mergeCommit,title,url,statusCheckRollup \
    --jq '{number,state,isDraft,mergedAt,mergeCommit,title,url,failed:[.statusCheckRollup[]|select(.conclusion=="FAILURE")|.name]}'
done
```

| Work | Current status | What may be trusted |
| --- | --- | --- |
| PR #821, merge `0beef7584` | Merged 2026-07-09; queried rollup had no failed checks | Root `holon/` fork collapse, deterministic reversibility primitive, direct-runtime seam, facade/Sarathi source, sprawl guard |
| Local `feat/sarathi-apex-reconcile`, `e7856fed9` | Local-only; not on main; no PR | Recoverable Sarathi gates 5–8 and tests, but not current product truth |
| PR #868 | Open; Python 3.11/3.12 tests failing | Audit material only; operator claims need per-claim current evidence before promotion |
| PR #878, merge `d3e084c66` | Merged 2026-07-11 despite six failed checks | Code is present on main; merge presence is not readiness proof for control-plane health/receipt durability |
| Draft PR #904 | Open draft; hygiene, quality, Semgrep, pytest 3.11/3.12, and CodeQL failing | Proposed package-owned/remote holon fast path; do not use as deployed truth |

Older July maps described a repo-root `holon/` fork and modules that did not land
in the reconciled main lineage. Historical commit reachability or a sibling
worktree is evidence of intent, not current-main ownership.

## 9. Evidence ledger

### Current-main implementation proof

The baseline and sprawl proof were reproduced with:

```bash
cd /Users/dhyana/ds_holon_ecosystem_ssot_20260713
git rev-parse origin/main
PYTHONPATH=$PWD PYTHONDONTWRITEBYTECODE=1 \
  /Users/dhyana/dharma_swarm/.venv/bin/python \
  scripts/governance/sprawl_guard.py
```

The final audited baseline was `15c0b5ad2`. The sprawl guard reported one
`load_holon`, one `holon_wake_cycle`, and no retired root-fork import/copy.

The four exact scoped test invocations were:

```bash
cd /Users/dhyana/ds_holon_ecosystem_ssot_20260713
PYTHONPATH=$PWD PYTHONDONTWRITEBYTECODE=1 \
  /Users/dhyana/dharma_swarm/.venv/bin/python -m pytest -q -p no:cacheprovider \
  tests/test_holon_system_imports.py tests/test_holon_bridge.py \
  tests/test_holon_runtime.py tests/test_holon_persistence.py \
  tests/test_holon_health.py tests/test_holon_killswitch.py \
  tests/test_holon_budget_guard.py tests/test_holon_compass.py \
  tests/test_reversibility_gate.py tests/test_codex_composer_wake_loop.py

PYTHONPATH=$PWD PYTHONDONTWRITEBYTECODE=1 \
  /Users/dhyana/dharma_swarm/.venv/bin/python -m pytest -q -p no:cacheprovider \
  tests/test_runtime_provider.py tests/test_model_routing.py \
  tests/test_provider_matrix.py tests/test_model_key_routing_guard.py \
  tests/test_routing_surface_inventory.py tests/test_provider_smoke.py \
  tests/test_provider_registry.py tests/test_provider_policy.py

PYTHONPATH=$PWD PYTHONDONTWRITEBYTECODE=1 \
  /Users/dhyana/dharma_swarm/.venv/bin/python -m pytest -q -p no:cacheprovider \
  tests/test_a2a.py tests/test_a2a_spec_conformance.py \
  tests/test_a2a_readiness_gate.py tests/test_a2a_send.py \
  tests/test_a2a_inbox_bridge.py tests/test_a2a_domain_reply_worker.py \
  tests/test_a2a_reply_capture.py tests/test_mailbox_gateway.py \
  tests/test_a2a_topology.py

PYTHONPATH=$PWD PYTHONDONTWRITEBYTECODE=1 \
  /Users/dhyana/dharma_swarm/.venv/bin/python -m pytest -q -p no:cacheprovider \
  tests/test_persistent_agent.py tests/test_autonomous_agent.py \
  tests/test_agent_runner.py tests/test_agent_runner_semantic_acceptance.py \
  tests/test_agent_runner_memory.py tests/test_agent_runner_routing_feedback.py \
  tests/test_living_agent_kernel.py tests/test_living_agent_kernel_service.py \
  tests/test_living_agent_kernel_supervisor.py
```

Results were 101 + 116 + 250 + 190 = **657 passed**, with 6 skipped and one
Starlette/httpx dependency deprecation warning in the A2A suite.

The standard `make onboard` admission path is currently blocked on this main
baseline by `Makefile:592: *** multiple target patterns. Stop.` (`make onboard`
reproduces it). That parser
failure is outside the holon docs change, but it prevents claiming a fully green
repository onboarding gate.

### Live-use proof

The live dialogue/run probes were performed on the immediately preceding
current-main baseline `c14b950bc`; `git diff --name-only c14b950bc..15c0b5ad2`
shows only onboarding packet/script/test changes and no holon source. The exact
dialogue probe was:

```bash
cd /Users/dhyana/ds_holon_ecosystem_ssot_20260713
/Users/dhyana/dharma_swarm/.venv/bin/python -m dharma_swarm.dgc_cli \
  agent talk --mode free-first --max-tokens 32 sarathi \
  "Reply with exactly: SARATHI_DIALOGUE_OK"
```

Result: routed to `ollama/glm-5.1:cloud`, returned the exact requested text, and
appended a talk receipt under Sarathi's agent home.

```bash
cd /Users/dhyana/ds_holon_ecosystem_ssot_20260713
/Users/dhyana/dharma_swarm/.venv/bin/python -m dharma_swarm.dgc_cli \
  agent run sarathi --cycles 1 --mode free-first
```

Result: one `ran` cycle proposed reading the operating map, logged a compass
signal, and persisted events. Per Section 4.1 this proves a proposal cycle, not
an executed governed action.

From outside the checkout, the installed CLI failed:

```bash
cd /private/tmp
/opt/homebrew/bin/dgc agent talk sarathi "packaging probe" --max-tokens 1
# Agent command failed: No module named 'scripts'
```

`pyproject.toml` excludes `scripts*` from package discovery, while the command
handler imports `scripts.holon_talk` and `scripts.holon_run`
(`pyproject.toml:58-64`; `dharma_swarm/terminal_commands/agents.py:101-127`).

### Live substrate witness

The dated NATS/A2A and anomaly observations were produced with:

```bash
cd /Users/dhyana/ds_holon_ecosystem_ssot_20260713
PYTHONPATH=$PWD /Users/dhyana/dharma_swarm/.venv/bin/python \
  scripts/governance/check_nats_live_production_evidence.py
PYTHONPATH=$PWD /Users/dhyana/dharma_swarm/.venv/bin/python \
  scripts/governance/check_a2a_readiness.py --require-artifact-or-evidence
jq '[.[] | select(.severity == "medium" and .type == "agent_silent")] | length' \
  ~/.dharma/health/latest_anomalies.json
find ~/.dharma/a2a_bus/quarantine -type f | wc -l
```

The NATS evidence check rejected evidence roughly twelve days stale; A2A
readiness was degraded with 44 tasks and one closed-but-unverified item; the
anomaly query returned ten; and quarantine contained 35,657 files. These are
dated observations, not live-state ownership or a terminal readiness score.

## 10. Exact closure path

### Packet 1 — turn proposals into governed effects

1. Define a typed action envelope with requested authority, effect scope,
   reversibility class, budget, verifier contract, and execution identity.
2. Make `scripts/holon_run.py` or its package-owned replacement pass that exact
   action through the reversibility gate, `ExecutionLease`, live `spend_fn`, and
   a bounded executor before any side effect.
3. Fail closed on lease, budget, persistence, verifier, or receipt failure.
4. Bind the effect artifact and independent verifier result into runtime truth
   and the A2A task receipt.

Acceptance: one canonical task reaches `GovernedEffectProven` and
`ReceiptBound`; a blocked task produces no effect.

### Packet 2 — make one seat a product, not a checkout trick

1. Move talk/run behavior into the installed package or package `scripts`
   deliberately; make the `/private/tmp` packaging probe pass.
2. Compose the API route with `get_holon_dialogue_provider`, bounded LivingDock
   context, safe history, and normalized dialogue receipts.
3. Run a canonical-build supervisor with service heartbeats, restart/resume,
   kill semantics, and explicit build provenance.
4. Separate `process_start_requested` from semantic liveness: stop deriving
   `alive_claim_allowed` from two booleans
   (`dharma_swarm/holon_system/observability/proof_gates.py:6-11`) and stop
   promoting `wake_loop_active` from tmux send success
   (`scripts/runtime/codex_composer_wake_loop.py:1245-1257`).

Acceptance: one Sarathi install works outside the repo, survives restart, and
cannot report `ran` without durable proof.

### Packet 3 — close the ecosystem loop

1. Converge compatibility and target NATS streams or provide one explicit,
   tested adapter contract.
2. Execute a semantic A2A task end-to-end on current main: dispatch, lease,
   effect, independent verification, reply, acknowledgement, receipt, and fresh
   heartbeat.
3. Burn in one seat unattended, exercise kill/restart/resume, then replicate the
   proved composition to Codex, Fugu, Fable, and peers.

Acceptance: the seat reaches `DurableServiceProven`; only then promote its
liveness flags.

## 11. Editing guide

If you need to change:

- identity/model loading: edit `dharma_swarm/holon_bridge.py`;
- direct cycle semantics: edit `dharma_swarm/holon_runtime.py`;
- persistence format: edit `dharma_swarm/holon_persistence.py`;
- authority/reversibility/leases: edit `dharma_swarm/operator_core/`;
- persistent supervision: edit the Living Agent Kernel package and its runtime wrappers;
- provider routing: edit the canonical provider stack in Section 4.2;
- A2A transport/receipts: edit `dharma_swarm/a2a/` and promote reusable
  script logic out of `scripts/runtime/` when touched;
- terminal/API product surfaces: edit `terminal_commands/agents.py`, the
  package-owned talk/run implementation, and `api/routers/holon.py`;
- deployment state: inspect `~/.dharma`, but fix source in the repo;
- Hermes compatibility: treat `.hermes` as an external boundary and create a
  versioned adapter contract on the Dharma side.

Do not create another registry, provider router, orchestrator, task store,
receipt spine, runtime home, or another implementation map to close these gaps.
Compose the owners above; current body/proof changes update `docs/persistent_agents/README.md`.

## 12. Deprecation record — orientation role only

**Deprecated:** 2026-08-03

**Reason:** this is a 2026-07-13 estate snapshot. Later behavior-first work
remeasured the surface and proved stale counts, omitted runtimes, and import
hazards (`docs/plans/HOLON_CONSOLIDATION_PLAN_2026-08-01.md:18-52`;
`docs/reports/SARATHI_SHELL_CENSUS_2026-08-02.md:24-55`).

**Replacement:** [`../persistent_agents/README.md`](../persistent_agents/README.md) owns subsystem terminology,
current family boundaries, and the complete document/code map. Use the census
for exhaustive dated evidence and the consolidation decision; retain the older
plan only for its reproduced import hazard and move probes.

**Review / removal date:** 2026-11-03. Retain as a dated deep reference unless
that review chooses archival relocation; remeasure before restoring any current claim.
