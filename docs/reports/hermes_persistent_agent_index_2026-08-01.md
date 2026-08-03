---
title: Hermes Persistent Agent Index
date: 2026-08-01
status: report
partially_fulfils: docs/agent_tasks/hermes_full_persistent_agent_index_2026-05-28.md
---

# Hermes Persistent Agent Index

> ## ⚠️ ERRATA — this report FAILED adversarial verification (2026-08-01)
>
> An independent verifier re-opened the citations and ran its own searches.
> Most of the report holds — every hard executed claim it re-ran landed exactly,
> and it found **zero invented files**. But the following claims are **verified
> FALSE** and must not be relied on until corrected:
>
> | Claim in this report | Refutation |
> |---|---|
> | §3 Provider Matrix: browser agent "none grounded in repo files" | `dharma_swarm/browser_agent.py` is 719 lines, `class BrowserAgent` at :148 (Playwright, SSRF blocklist at :57). Dormant ≠ absent. |
> | §4: synthesis agent "none grounded / UNSOURCED" | `dharma_swarm/synthesis_agent.py` (323 lines), imported in **production** by `cron_runner.py` and `kaizen_ops_local.py`. |
> | §2.12 / §5 Gap 10: "8 workflows carry the kill-switch guard" | **4 workflow files, 5 job-level guards** — `automerge.yml:91`, `codex-mention-router.yml:49`, `loop-watcher.yml:45` and `:131` (two jobs), `merge-master-mike-backlog.yml:77`. Reproduce: `grep -rn "Halt on loop kill-switch" .github/workflows/`. (`walking-brief.yml:12` matches only as a comment stating it does **not** carry the guard.) |
> | *(this errata's own first revision)*: "Exactly 4: … `sarathi-wake-lane.yml:86`" | Wrong membership. `.github/workflows/sarathi-wake-lane.yml` **does not exist** at HEAD, at `origin/main`, or at this packet's `base_ref` — it existed only on the closed, force-replaced PR-S6 branch (#1188, never merged). `loop-watcher.yml` is the file that was missed. |
> | §2.9 / §4: "`GET /agents` (api/routers/agents.py:46) serves nothing" | The route is `api/routers/agents.py:303-312`, returns `await swarm.list_agents()`, and never touches the ginko registry. `:46` is a lazy accessor. |
> | §2.12: "`claude` and `devin` are in `DEFAULT_REQUIRED_REVIEWERS`" | `pr_merge_control.py:71` is `("codex", "claude")`. `devin` appears only in `DEFAULT_A2A_NATS_SUBJECTS`. |
> | §5 Gap 2 / §7 PR 2: "`qwen_code` declares an empty subject" | The key is **absent**, not empty — PR 2's edit targets a field that does not exist. |
> | §5 Gap 1: "there are five registries" | There is a **sixth**: `docs/ops/FLEET_FIELD_REGISTRY.yaml` + `scripts/runtime/fleet_field_registry.py`, with a non-advisory `--check` validator (exit 2). |
>
> **Surfaces this report MISSED** (each verified present):
> `dharma_swarm/sleep_time_agent.py` (606 lines, imported by `orchestrator.py`,
> `organism.py`, `knowledge_extractor.py`); the entire **cron subsystem** —
> `cron_scheduler.py`/`cron_runner.py`/`cron_daemon.py`/`cron_job_runtime.py`/
> `cron_portable_context.py`/`cron_algedonic_handlers.py`/`cron_signal_deep_sweep.py`
> = 2,312 lines, plus `dgc cron daemon` (`dgc_cli.py:1266,:2216`) and a checked-in
> launchd unit — a **second agent runtime** this index does not account for; and
> `garden_daemon.py`, which spawns `claude -p` subprocesses to run skill cycles.
>
> One correction this report gets RIGHT against an older doc:
> `dharma_swarm/holon_system/` is **47 files / 1,345 lines**, not the 43/360 stated
> at `docs/architecture/HOLON_RUNTIME_FULL_ESTATE_MAP.md:332`.
>
> Do not treat this as the finished index. It is a verified-partial first pass,
> and the frontmatter says `partially_fulfils` for that reason — the 2026-05-28
> P0 is NOT discharged.
>
> **§7's three-PR build plan additionally failed Codex review (PR #1198) and must
> not be executed as written.** Verified defects in it: it invents a third
> `ActionEnvelope` when `semantic_governance.ActionEnvelope` and
> `living_agent_kernel.AgentRunEnvelope` already exist; it never calls the
> `authorize()` it defines, leaving lease and budget checks dead; it asserts a
> mailbox consumer that no listed edit creates; it extends `EvidenceReceipt`
> without adding a producer, so the receipt_id criterion cannot be met; it
> swaps `holon_wake_cycle` for `run_holon_loop` without adapting
> `sarathi_wake_daemon.py:381-390`, which calls `.get()` on what would become a
> list; and its acceptance command uses a positional `1` where the CLI requires
> `--cycles 1`. Treat §7 as a sketch that needs a rewrite, not a plan.


## Header note — what this is and why it is dated today

This report **partially fulfils the P0 task filed 2026-05-28** at
`docs/agent_tasks/hermes_full_persistent_agent_index_2026-05-28.md`, and **the
P0 remains open.** That task required the deliverable at
`docs/reports/hermes_persistent_agent_index_2026-05-28.md`. That file does not
exist and never did (`test -e` → absent). The debt is roughly nine weeks old.

Do not mark the P0 complete on the strength of this file. The errata block
above names the claims that were verified false and marks §7's three-PR build
plan NOT EXECUTABLE AS WRITTEN; the frontmatter records `partially_fulfils`
for the same reason. What is discharged is the *inventory* shape (§§1-7); what
is outstanding is every surface the errata lists.

It is dated **2026-08-01**, not backdated to the request date, because every
claim in it was verified against the working tree *today*. Backdating would
imply the inventory reflects the 2026-05-28 codebase, which it does not — a
`persistent_agent.py` line number valid in May is not evidence in August. The
2026-05-28 task defines the required *shape* (Sections 1-7 below map 1:1 to its
"Output Required" list); the *content* is a current-main reading.

**Authority.** Where this report and
[`docs/architecture/HOLON_RUNTIME_FULL_ESTATE_MAP.md`](../architecture/HOLON_RUNTIME_FULL_ESTATE_MAP.md)
(dated 2026-07-13) disagree, the divergences are called out explicitly in
"Agreement with the estate map" below. This report does not supersede the estate
map as the holon body reference; it is the wider cross-provider agent inventory
the estate map does not attempt.

**Evidence discipline.** Per the source task's constraints
(`:189-196`): every surface carries `file:line` evidence; all 162 claimed paths
were existence-checked with `test -e` before reporting (0 missing); nothing is
reported that could not be cited. Rows marked `inferred:true` in the sweeps are
flagged **[INF]**. Counts stated as "verified live" were produced by executing
the command shown, in this session.

**Runtime-evidence caveat, stated up front.** The only agent lane on this box
with persisted receipts is `sarathi` — 20 cycle records in
`~/.dharma/agents/sarathi/holon_events.jsonl`, cycles 0..19, first
`2026-07-30T15:57:06Z`, last `2026-08-01T12:03:01Z`, all `record.status == "ran"`.
Their `reply` fields cite brief paths under
`/tmp/.../scratchpad/sarathi-live/` and `/tmp/.../scratchpad/sarathi-state/`.
**These cycles were produced by prior agent sessions invoking the daemon by hand
into temporary state roots — they are not evidence of a standing production
service.** Read them as "the code path executes", never as "the organism is
alive".

---

## 1. Executive Map

The honest one-paragraph version: **dharma_swarm has an unusually large number of
correct, well-tested agent organs and almost no composition between them.** Every
primitive the task asks about exists — identity homes, wake loops, kill switches,
budget caps, reversibility gates, autonomy dials, execution leases, evidence
receipts, an A2A 1.0 card/task stack, a NATS transport, a merge-executing GitHub
agent. What does not exist is a single path on which more than three of them are
joined, a single address at which an agent can be reached, or a single vocabulary
in which an agent can be named.

### The shape of the estate

129 distinct persistent-agent surfaces survive deduplication (the six
sweeps reported the same organ under as many as three aliases each). They sort
into six strata:

1. **The sovereign-holon core** (`dharma_swarm/holon_*.py`, 7 modules, ~1,000
   lines). Small, sharp, tested. `holon_wake_cycle`
   (`dharma_swarm/holon_runtime.py:53`) is the richest authority composition in
   the repo: kill-check → budget-check → reversibility gate → runner → compass →
   persist. This is the closest thing to a real organism.
2. **The classic persistent-agent stack** (`persistent_agent.py`,
   `autonomous_agent.py`, `agent_runner.py`, `conductors.py`,
   `orchestrate_live.py`). Older, larger, ReAct-shaped, with cron self-waking and
   a witness log. It has produced **zero receipts on this checkout** and is
   reachable only through a launchd unit whose `WorkingDirectory` is an operator
   Mac path.
3. **The Living Agent Kernel** (`operator_core/living_agent_kernel*.py`, ~9
   modules). A full wake-queue OS — leases, recovery, promotion membrane,
   supervisor plans, hash-chained proof ledger. **Nothing runs it.** Every
   satellite module's own docstring disclaims process authority
   (`living_agent_kernel_supervisor.py:3-4`: "intentionally does not call
   launchctl, tmux, or spawn processes"), and `~/.dharma/living_agent_kernel`
   does not exist.
4. **The A2A layer** (`dharma_swarm/a2a/**` plus `scripts/runtime/a2a_*.py`).
   Spec-shaped and heavily tested. Exactly **one** agent — `codex_composer` — has
   a closed send→bridge→dock→semantic-reply→receipt path. The declared canonical
   task stream `DS_TASKS` has neither a real producer nor a real consumer.
5. **The registry sprawl.** Nine role vocabularies, five fleet rosters, two
   alias maps, two agent-home roots, four lease types, six mailbox address
   spaces. No two agree, and the only mechanical reconciler covers two of them
   and always exits 0.
6. **The GitHub-side fleet** — and this is the surprise. The *only* stratum with
   proven, scheduled, autonomous, effect-producing agents is
   `.github/workflows/`. `automerge.yml` has 8,388 runs; the mention router
   actually merges code; `pr-ci-health.yml` rebases branches hourly. The
   organism's real always-on limbs are GitHub Actions, not Python daemons.

### The three cross-cutting defects

Each is grep- or execution-verified, not inferred.

**D1 — Split agent home.** `dharma_swarm/holon_bridge.py:32` roots the agent home
at `~/.dharma/agents`; `dharma_swarm/agent_registry.py:27,221` roots it at
`~/.dharma/ginko/agents`. Identical on-disk schema (`identity.json` +
`prompt_variants/active.txt`). `holon_bridge.py:6-8` declares `ginko/agents`
non-canonical and nothing migrates it. The same FastAPI process serves both
populations: `api/routers/agents.py:46-48` reads ginko,
`api/routers/holon.py:52` reads `~/.dharma/agents`.

**D2 — The one live holon is unregistered.** `sarathi` writes killswitch,
persistence and compass state into the canonical home but has no
`identity.json`. Executed:

```
python3 -c "from dharma_swarm.holon_bridge import load_holon; load_holon('sarathi')"
→ FileNotFoundError: no registered agent at /root/.dharma/agents/sarathi/identity.json

python3 -c "from dharma_swarm.holon_health import holon_health_rows; print(holon_health_rows())"
→ []
```

So `dgc agent status` prints "No registered holons."
(`dharma_swarm/terminal_commands/agents.py:160`) while 20 wake cycles sit on
disk. The **write** surfaces (`holon_persistence.py:29`,
`holon_killswitch.py:20`, `holon_compass.py:26`) never require `identity.json`;
the **read** surfaces (`holon_bridge.py:120`, `holon_health.py:55,76`) do.

**D3 — The live wake path skips `run_holon_loop`.**
`scripts/runtime/sarathi_wake_daemon.py:373` calls `holon_wake_cycle` directly.
Everything implemented only in `run_holon_loop` is therefore dead on the
production lane: the pass^k streak / meltdown classification
(`dharma_swarm/holon_runtime.py:270-279` — verified 0 of 20 records carry
`passk_streak_after`) and the `spend_fn` mid-loop budget re-read (`:255`). The
daemon also passes no `planned_action`, and the gate step is conditional on it
(`holon_runtime.py:99`) — so **the in-loop reversibility gate never fires in
production**; gating happens only downstream inside `delegate_all`. Separately,
the GDS detector (`:197`, threshold 0.25) fires on 20/20 successful cycles
because the compass scores `telos_alignment == 0.0` for every real reply
(verified by aggregating `record.signal.telos_alignment`): a constant-true alarm,
not a signal. And `sarathi_wake_daemon.py:387` increments its spend ledger from
`result["cost_usd"]`, a key `holon_runtime.py` never writes (`grep -n cost_usd` →
no match) — the ledger increments by `0.0` forever.

### Agreement with the estate map

This report **agrees with** `HOLON_RUNTIME_FULL_ESTATE_MAP.md` §2 on every
executive-verdict row: identity/dialogue/proposal are real; governed effect,
receipt binding, and durable service are unproved. It independently confirms §2's
"Can it bind an effect to an independent verifier and runtime/A2A receipt? — Not
on the direct path" by the stronger method of grepping the whole tree rather than
one script: **no file imports both `telos_gates` and `reversibility_gate`**, and
**no file imports both `reversibility_gate` and `execution_lease`**.

It **agrees** with §4.6 that top-level `holon_system/` does not exist (only
`dharma_swarm/holon_system/`).

It **disagrees** with §4.6's "no production consumers" — that claim is false,
and this report repeated it in an earlier revision. Two runtime scripts import
the package directly:
`scripts/runtime/sarathi_wake_daemon.py:81-86` (`sarathi.plan`, `sarathi.roster`,
`sarathi.wake`) and `scripts/runtime/sarathi_proof_window.py:43-55`
(`sarathi.delegate`, `sarathi.plan`, `sarathi.proof`, `sarathi.roster`,
`sarathi.wake`). Reproduce:

```bash
grep -rln "from dharma_swarm\.holon_system\|import dharma_swarm\.holon_system" \
  --include=*.py . | grep -v "^./tests/" | grep -v "^./dharma_swarm/holon_system/"
```

Both files are the only non-test, non-package importers. Consolidation work
must therefore treat `holon_system/sarathi/` as load-bearing and check those
two scripts for compatibility, not as an unused facade.

Three places where **the code has moved since 2026-07-13**:

| Estate map claim | Location | Current truth (verified today) |
| --- | --- | --- |
| `scripts/runtime/codex_composer_semantic_responder.py` listed among modules "absent from current main" | `:342-346`, `:355` | **PRESENT**, ~1,400 lines, and it is the only surface that closes an A2A semantic loop. `fugu_ultra_semantic_responder.py` and `a2a_resident_executor.py` remain absent, as do the three `holon_*` modules. |
| "The 43 Python files in `dharma_swarm/holon_system/` total roughly 360 lines" | `:332` | **47 files, 1,345 lines** (`find … \| wc -l`). Still a facade — the conclusion holds, the count does not. |
| `proof_gate_summary` permits an alive claim from two booleans | `:120-125` | Still true (`observability/proof_gates.py:6`), and now additionally **dormant**: zero production callers — the only importer outside its own package is the facade `__init__.py:3`. |

One point the estate map is right about that this report wants to amplify:
§10 Packet 1 asks for "a typed action envelope with requested authority, effect
scope, reversibility class, budget, verifier contract, and execution identity."
That envelope is exactly the `authority` block of the
`PersistentAgentDescriptor` in Section 6, and it is the highest-value work
identified anywhere in this inventory.

---

## 2. Persistent Agent Table

Runtime status vocabulary is the task's: `live`, `callable-but-partial`,
`scaffolded`, `prompt-only`, `dormant`, `stale/unknown`.

**Deduplication note.** The six sweeps produced 138 raw entries; the same organ
appears under up to three aliases (e.g. `holon_runtime` /
`holon-wake-cycle-composition`; `execution_lease` × 3;
`a2a_task_lifecycle` / `a2a-task-queue-jsonl` / `a2a-task-receipt`). Merged rows
say so. **129 distinct surfaces** result (counted mechanically in the tally below §2.12).

### 2.1 Sovereign holon core

| Agent / Surface | Path(s) | Runtime Status | Provider Target | Role | Skills | Memory / FS | Routing Hook | Evidence Hook | A2A Readiness | Problems |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Holon loader / dialogue bridge | `dharma_swarm/holon_bridge.py` | live | any `ProviderType` via `resolve_runtime_provider_config`; `claude_code`, `anthropic` | Loads a registered agent as itself and streams a read-only reply. No tools, no governance | — | `~/.dharma/agents/<n>/{identity.json,prompt_variants/active.txt,dialogue/*,sanctum/receipts/}` | `:152` `get_holon_provider`; `:210` dialogue override via `DHARMA_HOLON_DIALOGUE_PROVIDER` | `HolonDialogueContext.evidence_paths` `:301,:355` | Not A2A; HTTP only via `POST /holon/{name}/chat` (`api/routers/holon.py:52-68`, mounted `api/main.py:577,580`) | Hard-requires `identity.json` (`:106`) — **D2**; **D1** split home (`:32` vs `agent_registry.py:221`) |
| Wake-cycle body + loop | `dharma_swarm/holon_runtime.py` (merges `holon-wake-cycle-composition`) | live | none directly — runner is injected (`:42`) | The one place ≥3 authority primitives compose | — | `holon_events.jsonl`; optional MemoryKernel pack `:129-137` | injected runner owns provider | cycle record per wake; `halted:unverified` downgrade `:184-190` | none | **D3**: live caller skips `run_holon_loop` and passes no `planned_action`, so gate (`:100`) is inert; GDS alarm constant-true (`:197`); `:210` uses `locals().get("summary_lines")` to pick evaluator arity |
| Cycle persistence (U6) | `dharma_swarm/holon_persistence.py` | live | — | Append-only restart-resume log | — | `~/.dharma/agents/<n>/holon_events.jsonl` | — | the log is the receipt | none | `:51` recomputes the cycle index by re-reading the whole file — O(n) per append and not concurrency-safe |
| Health projection (U9) | `dharma_swarm/holon_health.py` | callable-but-partial | — | Read-only projection: registered/model/kill/compass count | — | `identity.json`, `compass_signals.jsonl`, `control/kill_requested.json` | — | — | none | `:76-78` counts only dirs with `identity.json` → `holon_health_rows() == []` while 20 cycles exist (**D2**); no consumer outside `dgc` and `sarathi/pulse.py:8` |
| Telos compass (Step 3a) | `dharma_swarm/holon_compass.py` | live | `ThinkodynamicScorer` | Non-binding alignment signal; cannot refuse | — | `~/.dharma/agents/<n>/compass_signals.jsonl` (20 lines on this box) | — | signal lines carry `telos_alignment`, `witness_quality` | none | Scores `0.0` on 20/20 real replies — below `LOW_ALIGNMENT=0.4` (`:22`) and the GDS threshold; saturated at the alarm floor |
| Kill switch (U7) | `dharma_swarm/holon_killswitch.py` (merges 2 aliases) | live | — | Durable operator stop; highest precedence in the wake loop | — | `~/.dharma/agents/<n>/control/kill_requested.json` | — | the file is the receipt | none | Checked only between cycles (`holon_runtime.py:83`); keyed by holon **name** only — cannot express "kill this action" |
| Budget guard (U8) | `dharma_swarm/holon_budget_guard.py` (merges 2) | live | — | The only halting USD primitive | — | stateless | — | `CostLimitExceeded` | none | **One importer repo-wide** (`holon_runtime.py`); `cap_usd <= 0` → unbounded (`:30`), so a default descriptor is fail-open; live cap bounds ~$0 of direct spend |

### 2.2 Classic persistent-agent stack

| Agent / Surface | Path(s) | Runtime Status | Provider Target | Role | Skills | Memory / FS | Routing Hook | Evidence Hook | A2A Readiness | Problems |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `PersistentAgent` + `AgentCronScheduler` | `dharma_swarm/persistent_agent.py` | callable-but-partial | anthropic, codex, openrouter (`:106`) | Self-waking conductor: cron → memory → stigmergy → bus → task → gate → ReAct → witness | 4 default crons (`:190`): memory_consolidation, stigmergy_scan, inbox_check, identity_evolution | `MessageBus` at `<state>/db/messages.db` (`:362`); `witness/conductor_<n>.jsonl` (`:171`); `profiles/` (`:337`) | `model_router` → AutonomousAgent (`:159`) | WAKE/BLOCKED/ADAPT/ERROR witness events (`:557`) | none | **No receipts on this checkout** — `~/.dharma/witness/` holds only `witness_20260801.jsonl`, no `conductor_*.jsonl`; `:306,:327` swallow all cron exceptions into a returned string |
| `AutonomousAgent` / `AgentIdentity` / `PRESET_AGENTS` | `dharma_swarm/autonomous_agent.py` | live | anthropic, claude_code, codex, openrouter (`:33-35`) | ReAct engine under every persistent agent; 5 preset identities (`:1391`) | 13 tools incl. `bash`, `read_file`, `stigmergy_mark`, `web_search` | `AgentMemoryBank(identity.name)` (`:422`) | optional `model_router`; `:329` keeps cheap-first order | `AgentResult` (`:259`) | none | `cli_wake` builds the agent **without** a router by documented legacy behaviour (`:1487-1491`) — CLI wakes bypass shared routing; `INTERFACE_MISMATCH_MAP.md:39` keeps a skipif active |
| Conductor identity configs | `dharma_swarm/conductors.py` | prompt-only | `ANTHROPIC` if key set else `CLAUDE_CODE` (`:18-22`) | Declares `conductor_claude` (3600s) and `conductor_codex` (1800s) | — | — | consumed by `orchestrate_live.py:1691` | — | none | `_resolve_conductor_provider` runs at **import time** (`:74,:84`) — a key loaded later does not change the provider |
| `run_conductor_loop` | `dharma_swarm/orchestrate_live.py:1684` | callable-but-partial | inherited | Daemon host: one `PersistentAgent` per config, crash-restart (`:1714`) | — | — | `"conductors"` in `task_factories` (`:2325`) | supervision heartbeat only | none | `:2300-2302` states a conductors tick proves **task liveness, not a completed wake cycle**; `com.dharma.swarm.plist` targets `/Users/dhyana/dharma_swarm` |
| `AgentRunner` / `AgentPool` | `dharma_swarm/agent_runner.py` | live | resolved per task (`:630,:687`) | Fleet per-agent process manager; heartbeat liveness (`:3323`) | — | — | `:687` `_build_route_request` | heartbeats | none | **Spine adoption declared, never performed**: `:61-63` imports `invoke_agent` under `# noqa: F401 (spine-adoption declaration)`; `grep -c invoke_agent` = 2 (comment + import), zero calls in 3,496 lines |

### 2.3 Living Agent Kernel

| Agent / Surface | Path(s) | Runtime Status | Provider Target | Role | Skills | Memory / FS | Routing Hook | Evidence Hook | A2A Readiness | Problems |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `LivingAgentKernel` | `dharma_swarm/operator_core/living_agent_kernel.py` (merges 2) | callable-but-partial | none — does not dispatch providers | Governed run envelope, wake ledger with leases/recovery, 6 wake sources, daemon control | `READ_ONLY_TOOLS` `:56`; `WRITE_TOOLS` incl. bounded `apply_patch` (`:2596`) | `~/.dharma/living_agent_kernel` (`:52`) — **absent on this box** | — | `ProofLedgerEntry` hash-chained (`:404`), `RuntimeTruthPacket` | wake source `a2a` is first-class (`:1276,:2058`) | **Authority is 100% caller-declared**: `grep -c 'reversibility_gate\|telos_gates\|execution_lease'` = **0** in 2,921 lines. `telos_decision` defaults `"allow"` (`:293`) and is read verbatim from the wake payload (`:1473`); same for `workspace_lease_present` (`:1480`) and `scanner_verdict` (`:1478`) |
| LAK satellite modules | `operator_core/living_agent_kernel_{service,supervisor,activation,promotion,workers,provider_worker,recovery,status}.py` | scaffolded | provider_worker only | Process-and-authority ring: locks, launchd/tmux **plans**, promotion membrane, worker receipts, crash-resume | — | shared `KernelRunStore` | — | receipt ledgers | — | Every module disclaims process authority in its own docstring (`supervisor:3-4`, `activation:3-4`, `workers:3-5`). The supervisor renders launchd plans it never installs; label `com.dharma.living-agent-kernel` has no plist in the repo |
| LAK runtime CLI family | `scripts/runtime/living_agent_kernel_{service,supervisor,worker,worker_process,provider_worker,recovery,activation,promotion,status}.py` | callable-but-partial | provider_worker | `service.py --forever` is the only loop (`while cycles is None …`, 60s) | — | `~/.dharma/living_agent_kernel/` | `:15` → `run_kernel_daemon_service` | — | `autonomy_spine.py:3-8` bridges ds-goal missions but "does not start a standing daemon" | **`--forever` is invoked by nothing** — no Makefile target, no tmux launcher, no workflow references `living_agent_kernel_service.py` |

### 2.4 Authority, gate and effect primitives

| Agent / Surface | Path(s) | Runtime Status | Provider Target | Role | Skills | Memory / FS | Routing Hook | Evidence Hook | A2A Readiness | Problems |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Reversibility gate | `operator_core/reversibility_gate.py` (merges 2) | live | — | `ActionClass` (4) + `NEVER_AUTO_PATTERNS` (28) + `GateDecision`; the floor the dial cannot widen | — | stateless, stdlib-only | `classify_action` `:237` | `GateDecision.to_dict()` → `dharma.reversibility_gate_decision.v1` (`:134`) | — | `GateDecision` carries no `correlation_id`/`actor`, so it cannot be joined to a receipt without re-stamping (`holon_runtime.py:104`, `delegate.py:221` both embed the raw dict) |
| Autonomy dial | `operator_core/autonomy_dial.py` (merges 2) | live | — | `DGC_SARATHI_AUTONOMY` → 4 levels; fail-closed (missing→propose, invalid→shadow, `:55`) | — | env only | `current_autonomy_level` `:65` | — | — | Process-global; the only per-call override seam is `delegate_all(level=…)` (`delegate.py:198`) |
| Execution lease | `operator_core/execution_lease.py` (merges 3 aliases) | scaffolded | — | Phase-A file lease: build/validate/write, `allowed_paths`, budget, forbidden actions | — | `~/.dharma/a2a_bus/leases/` (`:104`) | — | lease file | — | **There is no `class ExecutionLease`** — it is a dict with `schema_version: dharma.execution_lease.v1` (`:18`). One production consumer (`codex_composer_wake_loop.py:39-46`); no module in `dharma_swarm/` calls it. `validate_execution_lease` checks `isinstance(lease, Mapping)` at `:200` *after* calling `.get()` at `:199` — dead guard |
| Governed work admission | `operator_core/governed_work_admission.py` | live | — | `WorkKind` (6) → allow/review/block, deterministic | — | — | — | `GovernedWorkAdmission` | — | Pure function over **caller-declared booleans**; every mechanically verifiable input (telos, scanner, lease, quorum) is asserted by the requester. 3 importers |
| Telos gates | `dharma_swarm/telos_gates.py`, `dharma_swarm/models.py` | live | — | 11 `CORE_GATES` (verified live), tiers A/B/C, reflective reroute, variety-expansion registry | — | `~/.dharma/witness/` | `check_action` `:805` | `GateCheckResult` (`models.py:266`) | — | Substring matching with no word-boundary discipline; `models.GateDecision` **name-collides** with the reversibility gate's dataclass (verified: not the same object) |
| Telos-gate → effect joins | `agent_runner.py:2232`, `api/chat_tool_execution.py:208`, `autonomous_agent.py:954`, `guardrails.py` | live | — | The four places a gate stands between decision and effect | — | — | — | TelicSeam record (`agent_runner.py:2246-2296`) | — | **None of the four touches the reversibility gate, a lease, or a budget.** `api/chat_tool_execution.py:208` is nonetheless the best fail-closed template in the repo (timeout / exception / malformed / not-ALLOW all quarantine and raise, `:242`) |
| Fourfold action warrant | `dharma_swarm/fourfold_action_warrant.py`, `policy_compiler.py` | callable-but-partial | — | Evidence-threshold warrant (≥50 files, 5 categories) before triggering actions | — | — | `policy_compiler.py:137` | `FourfoldActionWarrant` | — | **Off by default** — needs `DHARMA_FOURFOLD_ACTION_WARRANT_GATE` (`:320-335`). Its trigger verbs (push/merge/execute/dispatch/spawn/write) duplicate `NEVER_AUTO_PATTERNS` with different semantics and no shared source |
| Spend / budget primitives | `evolution_safety_runtime.py:270`, `economic_spine.py` | callable-but-partial | — | `model_spend_allowed()` env/lease gate; `AgentBudget` token tracking | — | — | — | `safety_summary` `:285` | — | `EconomicSpine.spend_tokens` **always returns True** by design (`:291`); `InsufficientBudgetError` (`:142`) is defined and never raised. Three unrelated spend units (tokens / USD / boolean) with no conversion |
| `proof_gate_summary` | `holon_system/observability/proof_gates.py` | dormant | — | 15-line boolean AND with a schema stamp | — | — | — | `dharma.holon_system.proof_gates.v1` | — | **Zero production callers** (verified). Both params default `False`; nothing computes them. Named "proof gate", is not a gate |
| `operator_core/permissions.py` | `operator_core/permissions.py`, `tui/engine/governance.py` | dormant | — | The only per-**tool-call** permission primitive: blocked/gated/auto-approved tool sets | — | `~/.dharma/sessions/<id>/audit.jsonl` | — | JSONL audit | — | **Not importable**: `:13` → `tui.engine.events` → `tui/engine/__init__.py:25` → `from textual import work` → `ModuleNotFoundError` (verified). Near-duplicate of `tui/engine/governance.py:25,47` |
| `holon_system/authority/**` | 4 files, 3-5 lines each | scaffolded | — | Star-import re-exports of `operator_core` | — | — | — | — | — | No production caller — the two live gate callers import `operator_core` directly. `authority/permissions.py` inherits the textual breakage |
| Sarathi unattended proof | `holon_system/sarathi/proof.py` | live | none — dial hard-pinned to PROPOSE | 14-cycle verdict; the only surface that can earn `wake_loop_active` | — | — | `dial_advance_on_pass` `:154` | `ProofVerdict` `:88` | — | `receipt_exists` is an injected callable — the audit is only as honest as the injector; only `dispatched` rows require receipts (`:26`), so a propose-pinned dial produces a clean window trivially |

### 2.5 Receipts and runtime state

| Agent / Surface | Path(s) | Runtime Status | Provider Target | Role | Skills | Memory / FS | Routing Hook | Evidence Hook | A2A Readiness | Problems |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Runtime Truth Spine | `dharma_swarm/spine/{__init__,invoke,receipt,identity,routing,persistence,warrant,tollbooth,adapters}.py` | live | — | The one blessed invocation path; `ExecutionIdentity` carries trace/correlation/task/run across layers | — | `delegation_runs.receipt_json` (`persistence.py:29`) | `RoutingDecision` | `EvidenceReceipt` (`receipt.py:41`); `VerifiedMachineReceipt.with_chain/verify` (`:253,:259`) | A2A ingress converges via `a2a/spine_adapter.py:33` | `EvidenceReceipt` has **no authority field** — cannot answer "what permitted this"; `cost_usd` (`:73`) is never fed to `check_cost_cap`; `agent_runner.py` declares adoption without calling it |
| Closure v0 receipts | `operator_core/closure_v0.py` | live | — | `WorkPacket` (allowed/forbidden paths, review tier), `ClosureEvidenceReceipt` | — | — | `decide_next` `:239` | `__post_init__:84` **raises if `success != (exit_code == 0)`** — the one receipt that structurally cannot lie | — | `EvidenceReceipt = ClosureEvidenceReceipt` alias still live at `:90` despite "removed in a follow-up PR"; `WorkPacket.allowed_paths` is never checked against a lease's `allowed_paths` |
| A2A task lifecycle | `operator_core/a2a_task_lifecycle.py` (merges 3 aliases) | callable-but-partial | — | Claim/close contract over the file bus; receipt mirroring | — | `~/.dharma/a2a_bus/tasks/queue.jsonl` (`:67`); inboxes (`:72`) | — | `dharma_a2a_task_receipt.v1` (`:139`) with a free-form `authority` field (`:113`) — the only authority slot on any receipt | this **is** the readiness surface (`check_a2a_readiness.py:12`) | **No enqueue function exists** — 11 governance scripts police rows nothing in-repo creates; `claim_task` does unlocked read-modify-write of the whole file (`:385-404`) |
| Runtime state store | `dharma_swarm/runtime_state.py` | live | — | SQLite: `TaskClaim`, `WorkspaceLease`, `RuntimeReceipt`, `IdempotencyRecord`, `OperatorAction` | — | `<state>/…` | — | `RuntimeReceipt` `:714` | — | **There is no `class RuntimeState`.** `WorkspaceLease` (`:610`) is lease vocabulary #2 of 4, with no conversion to the others |
| Runtime truth packet | `operator_core/runtime_truth.py`, `operator_core/contracts.py` | live | — | `RuntimeTruthState` (10), `ProofGrade` (5), `MutationTruth` (8 effect booleans, `:115`) | — | — | — | `RuntimeTruthPacket` `:130` | — | **Two live definitions** of `RuntimeTruthState`/`RuntimeTruthPacket` reconciled only by an alias import (`runtime_truth.py:22`); `authority_state` (`:146`) reports observability, not permission, despite the name |

### 2.6 A2A protocol, transport and directory

| Agent / Surface | Path(s) | Runtime Status | Provider Target | Role | Skills | Memory / FS | Routing Hook | Evidence Hook | A2A Readiness | Problems |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| A2A protocol core | `a2a/{a2a_server,a2a_client,a2a_bridge}.py` | live | — | 8-state task lifecycle with guarded transitions (`a2a_server.py:123`); in-process delegation with cycle guard | — | — | `AGENT_UID_ALIASES` + `resolve_agent_uid` | — | canonical server side; wired at `api/main.py:161-186` | Aliases applied on the agent-inbox route, bypassed on the compat route (`a2a_send.py:105-107`) |
| Agent cards + `CardRegistry` | `a2a/agent_card.py` (merges 2) | live | — | A2A 1.0 cards, JWS, security schemes, `AgentSkill` (18 names), canonical inbox subject grammar (`:85-86`) | 18 skill names | `~/.dharma/a2a/cards/` — **absent on this box** | `AGENT_UID_ALIASES` `:41-51` | — | canonical | Auth is declaration-only — 5 schemes advertised, only APIKey enforced (at the gateway). `_skills_for_role` (`:390-428`) is role vocabulary #6. Alias `opus → opus_composer` targets an identity in no roster and no card |
| Node gateway | `a2a/node_gateway.py` | live | — | HTTP door: well-known card, submit/cancel/get/stream, API-key gated | — | — | `init_gateway` `:93` | `submit_task_via_spine` → receipt (`:333,:453`) | serves `/.well-known/agent-card.json` (`:314`); mounted `api/main.py:604,609` | — |
| Spine adapter | `a2a/spine_adapter.py` | live | — | The single blessed A2A submit path; exactly one `EvidenceReceipt` per dispatch | — | — | `:33`, `:178` | `(result, EvidenceReceipt)` | convergence point for 4 ingress edges | — |
| Mailbox gateway | `a2a/mailbox_gateway.py` (merges 2) | callable-but-partial | NATS `DHARMA_A2A` | One-egress HTTPS door for sandboxed agents; token→uid, publish anywhere, drain only own | — | `~/.dharma/a2a_gateway/{agent_tokens.json,receipts.jsonl}` — absent | `_subject_for_peer` `:169` | `_record_receipt` `:193` | HTTPS fallback for agents without NATS | **Not mounted on the main app** — `grep mailbox api/main.py` → nothing. Only `scripts/runtime/a2a_gateway_server.py:92-93` mounts it |
| A2A gateway server | `scripts/runtime/a2a_gateway_server.py` | callable-but-partial | NATS | Slim uvicorn host for the mailbox door | — | — | — | — | — | No compose service, no Makefile target, no cron entry starts it |
| Agent directory | `a2a/agent_directory.py` | live | — | Stable-UID read model merging cards + nodes + onboarding + telemetry; credential refs never values | — | — | `_SOURCE_ORDER` `:20` | — | — | Read model over sources that disagree — it cannot fix the drift it merges |
| Presence roster | `a2a/agent_presence.py` (merges 2) | dormant | — | 8 hardcoded `REGISTERED_AGENT_UIDS` (`:15-24`, verified live) | — | `~/.dharma/a2a_bus/{agents,heartbeats}.json` | `_ALIASES` `:26-29` (alias map #2, 2 entries) | — | — | Only non-facade importer is a test; hardcoded roster drifts silently; 2 GHOSTs (`codex_composer`, `hermes-m5`) verified via `a2a_agent_onboard.py --json` |
| Contact registry | `a2a/contact_registry.py` | scaffolded | — | Read-only routing denominator, local vs cloud | — | — | `default_contact_registry` `:158` | — | — | Not exported from `a2a/__init__.py` lazy map; no importer in `api/` or `scripts/runtime/` |
| Node registry + hydrator | `a2a/node_registry.py`, `a2a/registry_hydrator.py` (merges 2) | live | — | Fleet **nodes** (VPS/Macs) with health + credential redaction; hydrated from onboarding receipts | — | `~/.dharma/a2a/nodes.json` | — | — | — | Hydration explicitly does **not** assert liveness (`registry_hydrator.py:22-27`); naming collision — `/api/fleet` serves nodes while "fleet" elsewhere means agents |
| NATS transport (`DS_TASKS`) | `a2a/nats_transport.py`, `nats_transport_support.py` | callable-but-partial | NATS JetStream | Declared canonical task path: `publish_task` `:328`, `consume_message` `:466`, topology `:162,:248` | — | RuntimeStateStore idempotency | — | — | implemented and heavily tested | **No production producer and no consumer.** Only callers are governance/evidence scripts. `ensure_task_consumer` never runs outside tests, so the durable is never created |
| Cloud contact ingress | `a2a/a2a_cloud_contact.py` | dormant | NATS | The declared ingress adapter into `DS_TASKS` | — | — | `publish_cloud_ingress` `:151` | — | — | **Zero callers** — no route, CLI, or daemon constructs `CloudContactIngress` |
| Task receipt quarantine | `a2a/task_receipt.py` | callable-but-partial | — | Validates receipts in an inbox; quarantines and bounces invalid | — | `~/.dharma/a2a_bus/quarantine/` | — | — | — | Globs the same `*.json` dock as two other producers with a third schema expectation |
| A2A topology constants | `scripts/runtime/a2a_topology.py` | live | — | Stream/subject/DLQ/durable constants; compat `DHARMA_A2A` vs target `DS_TASKS` | — | — | — | — | — | `COMPATIBILITY_TO_TARGET` (`:84-86`) declares a migration nothing imports |
| Operator send | `scripts/runtime/a2a_send.py` | live | NATS | Publishes one file as `dharma.a2a.send.v1`; waits for ack/reply | — | `reports/a2a/send_receipts/` (gitignored) | `subject_for_route` `:104` | send receipt | self-declared compatibility contact, not production readiness (`:22-27`) | **Route asymmetry**: default `ROUTE_A2A` (`:744`) has no bridge behind it; **alias asymmetry**: compat route skips `resolve_agent_uid` (`:105-107`) while the inbox route applies it |
| Inbox bridge | `scripts/runtime/a2a_inbox_bridge.py` + 3 tmux scripts (merges 2) | live | none — pure transport | Drains a JetStream durable into a filesystem dock; publishes ack | — | dock `~/.dharma/a2a_bus/inboxes/<uid>/`; `bridge_heartbeats/`; `semantic_jobs/<uid>.sqlite3` | `--agent-uid hermes-m5 --loop` in the launcher | `dharma.a2a.inbox_bridge_heartbeat.v1` | strongest A2A plumbing in `scripts/` | Liveness = `tmux has-session` + mtime, **no restart on crash**; default seat hardcoded `hermes-m5`; the semantic-jobs sqlite is **write-only** — no reader anywhere |
| Reply capture | `scripts/runtime/a2a_reply_capture.py` | live | NATS | Send receipt → durable subscribe → NO_REPLY / untyped / typed receipt | — | `reports/a2a/reply_receipts/` | — | — | — | All receipt dirs gitignored (`.gitignore:122`) — invisible to CI and to a fresh checkout |
| Domain reply worker | `scripts/runtime/a2a_domain_reply_worker.py`, `a2a_domain_reply_artifact.py` | live | — | Validates a target-owned outbox artifact and publishes the typed domain receipt | — | `~/.dharma/a2a_bus/outboxes/<uid>/` | — | `reports/a2a/domain_reply_receipts/` | — | Exactly one in-repo producer of the outbox (`codex_composer_semantic_inbox_drain.py:267-268`); every other uid's outbox is permanently empty |
| A2A doctor | `scripts/runtime/a2a_doctor.py` | live | AGNI hub | One-command readout: identity, stream, consumer, live roster | — | — | — | — | — | — |
| NATS substrate checks | `scripts/governance/check_nats_{substrate_contract,live_production_evidence}.py`, `run_nats_live_production_matrix.py`, `operator_core/nats_live_contact.py` | live | NATS | Mechanical verification that the transport contract holds | — | `reports/governance/nats_live_production_matrix/latest.json` | — | matrix json | — | **These checks are the only production-shaped callers of `publish_task`/`consume_message`** — the gate is green while the path it verifies carries no traffic |
| Transport facades | `holon_system/transport/{__init__,a2a_send,inbox_bridge,reply_capture,domain_reply}.py` | scaffolded | — | 3-line `import *` shims over `scripts/runtime` | — | — | — | — | — | Importing the "library" facade depends on the scripts tree layout, since each target inserts `REPO_ROOT` into `sys.path` at import |

### 2.7 Mailboxes and buses

| Agent / Surface | Path(s) | Runtime Status | Provider Target | Role | Skills | Memory / FS | Routing Hook | Evidence Hook | A2A Readiness | Problems |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `RoamingMailbox` | `dharma_swarm/roaming_mailbox.py` (merges 2) | live | — | Git-friendly file queue: `tasks/`, `responses/`, `receipts/` claim fence (`:220` `O_CREAT\|O_EXCL`) | — | `<repo>/roaming_mailbox/` default (`:50`) | `recipient` on `MailboxTask` (`:57`) | receipts as claim fence | transport-only, no auth | `receipts/` is created at runtime (`:123`) but is **not git-tracked**, so the fence never travels with a sync as `:218` promises |
| Committed queue state | `roaming_mailbox/tasks/*.json`, `responses/*.json` | dormant | — | 3 tasks, 1 response — the only git-tracked queue instance | — | — | — | — | — | 2 tasks queued since 2026-03-26 and 2026-05-29; `mbx_c1e05575f1914c1e.json:17` carries `depends_on` **inside `metadata`**, not top-level where `ready_tasks` reads it — marked responded while its dependency is still queued; recipient `hermes` but responder `perplexity-computer` |
| `RoamingPoller` | `dharma_swarm/roaming_poller.py` (merges 2) | dormant | provider-agnostic (`--command`) | Remote-side worker: claim → subprocess with `ROAMING_*` env → respond → git push | — | — | `_env_for_task` `:86-101` | — | git-sync only | **Zero invocations** — verified `grep` over `scripts/`, `Makefile`, `*.sh`, `*.plist`, `.github/` returns nothing outside the module and its test. `sync_outbound` (`:60-65`) never stages `receipts/` — fence loss |
| `RoamingDispatchDaemon` | `dharma_swarm/roaming_dispatch_daemon.py` | dormant | — | Local loop: sync → collect responses → dispatch new work → push | — | `receipts/*.imported.json` | — | — | — | No invocation site; blocking `time.sleep` inside an async loop (`:142`); swallows all exceptions (`:140-141`); its git sync **does** stage receipts (`:55`) — disagreeing with the poller's |
| `RoamingOperatorBridge` | `dharma_swarm/roaming_operator_bridge.py` | callable-but-partial | — | Adapts `OperatorBridge` work orders onto mailbox transport | — | `roaming_mailbox/receipts/` | — | `.imported.json` idempotency receipt | — | Return path dead for live data: `collect_response` requires `metadata.bridge_task_id` (`:83-85`) which no hand-authored task has |
| Sarathi private mailbox | `sarathi_wake_daemon.py:237`, `holon_system/sarathi/delegate.py:311-325` | callable-but-partial | — | The only autonomous in-repo producer of roaming tasks | — | `~/.dharma/sarathi/mailbox/` | `delegation.recipient` | `invoke_receipts/` | — | **Producer with zero consumer** — pollers default to `<repo>/roaming_mailbox`; `grep 'sarathi/mailbox'` finds only writers and the read-only proof window. `delegate.py:24-25` justifies "dispatched" semantics on "live pollers claim queued tasks", which is false for this root |
| Roaming onboarding | `dharma_swarm/roaming_onboarding.py` | callable-but-partial | — | Binds an external harness into 4 identity surfaces + a receipt | — | `living_agent.json`, a2a card, `state/runtime.db`, `onboarding/receipts/` | — | `OnboardingReceipt` `:100` | writes the card the hydrator reads | Neither `~/.dharma/onboarding` nor `~/.dharma/a2a` exists here — `hydrate_from_receipts` would produce an empty registry |
| `MessageBus` | `dharma_swarm/message_bus.py` | live | — | Async aiosqlite bus: send/receive/reply/publish, artifacts, event stream | — | `<state>/db/messages.db` | — | — | — | none found |
| `OperatorBridge` | `dharma_swarm/operator_bridge.py` | callable-but-partial | — | Durable SQLite work-order queue with claim/heartbeat/respond/ack | — | SQLite | — | — | — | **Claim side effectively dead**: the only `claim_task` caller is the dormant `RoamingOperatorBridge:45`; nothing in `api/` or `terminal/` imports it |
| `inter_agent/<seat>/` git docks | `inter_agent/` (13 seats, merges 2) | live (as files) | — | Git-tracked inbound/outbound docks; step 4 of the canonical join route | — | `inbound/`, `outbound/` | `a2a_agent_onboard.py:36,46` | — | reachable without NATS creds | **Write-only** — no code reads `inter_agent/*/inbound/`. Seat names are callsigns (`codex`, `hermes`, `mike`) and three (`claude`, `gpt55`, `rushabdev`) appear in no other registry |
| Declared mailbox addresses | `examples/agents/*.registration.json:14`, `external_agent_registration.py:499` | callable-but-partial | — | Each agent declares one reachable address | — | — | — | — | — | **Four incompatible schemes across 10 cards** (compat subject ×6, canonical inbox ×2, `file://` ×1, `roaming_mailbox://` ×1) and **no resolver dispatches on the field** |

### 2.8 Runners, daemons and operator scripts

| Agent / Surface | Path(s) | Runtime Status | Provider Target | Role | Skills | Memory / FS | Routing Hook | Evidence Hook | A2A Readiness | Problems |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Sarathi wake daemon | `scripts/runtime/sarathi_wake_daemon.py` (merges 3) | callable-but-partial | **none** — `invoker=None`, ~$0 direct spend (`:22-32`) | Gate-9 wrapper binding the dial to real work; plans against backlog + roster; enqueues sub-holon tasks | — | `<root>/sarathi/{mailbox,briefs,spent_usd,spend.lock}` | `make_wake_work_fn` + `holon_wake_cycle` (`:80-88`); dial at `:244` | `wake_daemon_report_run_NNNN.json`; briefs | mailbox-only; `git push`/`merge pr` are NEVER_AUTO | **One-shot by construction** (`--cycles` default 1; `:51` says the operator's scheduler re-invokes). Never self-claims liveness (`:303`). Fail-closed spend ledger (`:157`) — but the `cost_usd` key it reads is never written (**D3**) |
| Sarathi proof window | `scripts/runtime/sarathi_proof_window.py` | callable-but-partial | none — dial pinned to PROPOSE (`:174`) | Gate-10 ceremony: 14 cycles + Sakshi audit → PASS/FAIL; the only surface that can earn `wake_loop_active` | — | `proof_window_report.json`, briefs | `evaluate_unattended_proof` | verdict json | none | Fails closed by design and **there is no evidence it has ever passed** — the required `kill_path_receipt.json` is operator-created and absent; the lane prints "kill-path receipt: ABSENT — a proof run will fail closed, by design" |
| Multi-seat wake loop | `scripts/runtime/codex_composer_wake_loop.py` (merges 3, incl. `WAKE_PROFILES`) | callable-but-partial | model **identity strings only** — no provider client is ever constructed | 3 admitted seats (codex_composer, fable_composer, sarathi); read-only orientation pass; classifies A2A inbox work | — | 8 canonical context paths incl. `agent_passports/<uid>.json` | `_codex/_claude/_sarathi_model_identity` `:71-101` | nest heartbeat/status/receipts + append-only jsonl | reads inbox/heartbeat/state, refuses to call a publish "collaboration", **sends nothing** (`:1134-1141`) | **No supervisor at all** — zero references in `*.sh`, `*.plist`, `Makefile`, `.github/`. `stop_loop` writes `wake_loop_active:false` even when tmux is missing (`:1265-1286`). `agent_passports/` has no writer anywhere (`find -name 'agent_passport*'` → 0) |
| Codex semantic responder | `scripts/runtime/codex_composer_semantic_responder.py`, `..._semantic_inbox_drain.py` (merges 2) | live | direct-API only — `PREFERRED_LOW_COST_RUNTIME_PROVIDERS` minus OLLAMA/CLAUDE_CODE/CODEX | **The only surface that closes an A2A semantic loop.** Claims a delivery under lease, runs the model drain, publishes the domain reply | — | `processed_deliveries.jsonl`, `pending_publish/`, `dead_letter/` | `_resolve_runtime_critic_defaults` (drain `:143-171`) | `reports/a2a/semantic_inbox_drains/`, heartbeat, canonical state projection | **full** — DLQ after 5 attempts, upstream bridge freshness check | Declares `RESPONDER_LAUNCHD_LABEL` (`:64`) with **no such plist in the repo**; no tmux trio, no Makefile target; `CANONICAL_PROJECTION_AVAILABLE` hardcoded `False` (`:65`). *(Estate map §4.6 lists this file as absent — it is present.)* |
| Merge Master Mike daemon | `scripts/runtime/merge_master_mike_daemon.py` | callable-but-partial | none direct — fans out to `codex,claude` | D4 coordination shell around `pr_merge_control.py`; receipt asserts `can_merge/approve/push/edit` all false | — | `~/.dharma/external_agents/merge_master_mike/nest/`, `~/.dharma/pr_review/` | `build_fanout_command` `:441-480` | cycle receipts, `latest_cycle.json`, action log | NATS probe in status, not an inbox participant | **The cloud heartbeat bypasses it** — `merge-master-mike-backlog.yml:152` runs `pr_merge_control.py` directly. The `plist` is generated on demand (`:709`), not checked in. `:279` names "tmux session existence as completion proof" as forbidden |
| Devin A2A agent | `scripts/runtime/devin_a2a_agent.py` (merges 2) | callable-but-partial | none — transport/presence only | Resident fleet seat: WSS to AGNI, `devin_inbox` durable, dock writes, 60s heartbeats | — | dock, card, `bridge_heartbeats/` | `DEVIN_NATS_URL` default `wss://157.245.193.15:8443` (`:90`) | heartbeat docs with `messages_received`/`uptime_s` | reference implementation of a persistent seat | **Subject split** — binds `dharma.a2a.devin`, not its canonical `dharma.agent.devin-roaming-2987d222.inbox`. Hardcoded IP literal; `AGENT_UID` hardcoded; `make a2a-up` is foreground with no supervisor |
| Palantir pilot worker | `scripts/runtime/palantir_pilot_a2a_worker.py` (merges 2) | callable-but-partial | no external model — public-source only | Full semantic A2A seat: subscribe, ack, build answer, publish typed reply | — | `worker_heartbeats/`, outbox, logs | subject `dharma.a2a.palantir-pilot` | `dharma.a2a.palantir_pilot.worker_heartbeat.v1` + per-packet receipts | most complete non-composer seat | tmux-only, no restart, liveness inferred from session + heartbeat |
| Composer background loop | `scripts/composer_background_loop.py` + 3 tmux scripts (merges 2) | callable-but-partial | shells out to `claude` CLI (`--permission-mode dontAsk`) and `codex` CLI | Watches the convergence dir and **wakes external agents by shelling out**; copies each composer's answer into the other's inbox | — | `~/.dharma/a2a_bus/operator/composer_background_loop/` | `claude_command` `:464-492` | heartbeat, receipts, convergence markdown | filesystem bus only | **`DRY_RUN=1` in the shipped launcher** — the start path monitors and never wakes. Liveness by process-table regex (`:92-95`). `ROOT` hardcoded to `${HOME}/dharma_swarm`. No test file for an ~830-line supervisor that can invoke `claude --permission-mode dontAsk` |
| Composer console | `scripts/composer_console.py` | live | — | Operator TUI writing `OPERATOR_STEER_*.md` into both composer inboxes | — | `composer_console_log.jsonl`, convergence dir | — | — | — | **Format collision on a shared path** — writes `.md` into the dock whose only consumer globs `*.json` (`codex_composer_semantic_responder.py:467`); operator steers are structurally invisible to it |
| Hermes heartbeat poll | `scripts/hermes_heartbeat_poll.py` | callable-but-partial | — | Cron-invoked liveness write + capability-matched task claim | — | `~/.dharma/agents/hermes-m5/state.json` | `HERMES_CAPABILITIES` match `:200-205` | — | — | **Path bug, highest confidence in this report**: `:59` reads `~/.dharma/a2a_bus/queue.jsonl`, missing the `tasks/` component every other participant uses. Hermes polls a file nothing writes, forever. The test monkeypatches `QUEUE_FILE` (`tests/…:44`) so the wrong constant is never exercised |
| `holon_talk` | `scripts/holon_talk.py` | callable-but-partial | free-first chain (excludes CLAUDE_CODE) or identity-declared with fallback | One-shot live conversation with a registered holon | — | `talk_receipts.jsonl` | `_resolve_provider` `:88-95` | talk receipt per exchange | none | **No test file**, yet `holon_run.py:17-30` imports four of its private helpers — a load-bearing private API across `scripts/`. PASS decided by string-matching failure markers (`:32-39`) |
| `holon_run` | `scripts/holon_run.py` | callable-but-partial | same as `holon_talk` | The proof a holon runs itself: plugs a live runner into `run_holon_loop` | — | persistence session | `run_holon_loop(…, cap_usd=0.0)` `:73-75` | persisted event count `:85-87` | none | `cap_usd` hardcoded `0.0` (`:74`) — a declared-first route to a metered provider runs under a zero cap. No test file. Fragile dual-import shim (`:17-30`) |
| `holon_smoke` | `scripts/holon_smoke.py` | callable-but-partial | declared route then full low-cost chain | Live end-to-end bridge smoke (U3) | — | none — writes no receipt | `holon_bridge` `:97` | stdout only | none | **Exits 2 when `CLAUDECODE` is set** (`:99-103`) — structurally unverifiable by any agent session. "In-character" is substring matching against six words |
| Overnight / all-out autopilots | `scripts/{overnight,allout,codex_overnight}_autopilot.py`, `thinkodynamic_director.py` + launchers | callable-but-partial | not resolvable from `scripts/` — 12-line shims | Wall-clock-bounded unattended supervisors; allout evolves its own prompt | — | task board, status snapshots, tmux logs | `sys.path.insert(0, Path.home()/"dharma_swarm")` (`:9`) | status snapshots | none | The shims **hardcode `~/dharma_swarm`** into `sys.path` — they import the wrong tree or fail on any other host. No restart. `allout_autopilot.py` is ~1,400 lines with a self-modifying prompt step and no test file |
| `dgc agent` CLI | `dharma_swarm/terminal_commands/agents.py` | live | — | Operator door: wake/list/talk/run/kill/status | presets + registered holons | — | dispatched from `dgc_cli.py:617` | — | — | `:109,:125` import from `scripts.holon_talk`/`scripts.holon_run` — a packaged console script (`pyproject.toml:60` ships only `dharma_swarm*`) reaching into `scripts/`, so `dgc agent talk/run` breaks outside a source checkout |

### 2.9 Identity registries

| Agent / Surface | Path(s) | Runtime Status | Provider Target | Role | Skills | Memory / FS | Routing Hook | Evidence Hook | A2A Readiness | Problems |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `AgentRegistry` (JIKOKU) | `dharma_swarm/agent_registry.py` (merges 2) | live (class) / dormant (store) | `MODEL_PRICING` from `model_pool` (`:36-47`) | Per-agent identity home, task log, fitness history, generational prompt variants | — | `~/.dharma/ginko/agents/<n>/{identity.json,task_log.jsonl,fitness_history.jsonl,prompt_variants/}` | — | task + fitness logs | — | **D1** — root disagrees with `holon_bridge.py:32`; `~/.dharma/ginko` does not exist here, so `GET /agents` (`api/routers/agents.py:46`) serves nothing. `AgentIdentity.name` is a free string validated against nothing |
| External registration manifests | `examples/agents/*.registration.json` (10) | live (as declarations) | per-card `model_identity` | Git-tracked A2A identities: uid, callsign, harness, department/role, endpoint, mailbox, authority, 8-boolean `autonomy_policy`, workspace policy | — | `~/.dharma/external_agents/<uid>` | — | — | `canonical_transport_subject` | **8 of 10 disagree with `a2a_inbox_subject()`** (verified live, list in §5); 4 are INVISIBLE (card, no roster); `role` is vocabulary #7 |
| `docs/agents/<uid>/` seeds | `docs/agents/{cybernetics_codex,sis_steward,palantir_pilot}/agent.seed.yaml` + 2 doc-only dirs | callable-but-partial | — | In-repo identity homes with `dharma-agent-seed-v0` machine-readable seed | — | pointers to `~/.dharma` | `mailbox.nats_subject` | receipts dir | declared | Only 3 of 5 have a seed; only 2 of 3 have a code reader; `cybernetics_codex` is a **third registration path** (seed + manifest) bypassing the canonical six-step route; card-path spelling drift inside one file (`:2` vs `:21`) |
| `holon_system/identity/**` | 4 files, 5-11 lines | scaffolded | — | Re-exports `AgentRegistry`, `a2a_inbox_subject`, plus `canonical_agent_uid()` | — | — | — | — | — | `canonical_agent_uid` (`canonical_names.py:6-8`) maps `-`→`_`, the **opposite** of `_slug` in `codex_composer_wake_loop.py:104-105`; applying it corrupts real uids. No production caller |
| Sarathi sub-holon roster | `holon_system/sarathi/roster.py` | callable-but-partial | — | Apex's 4 sub-holons as a hardcoded tuple (`:7`) | hermes-m5, codex_composer, fugu_ultra, fable_composer | optional override file | — | — | — | **`fugu_ultra` is a phantom seat** — no card, no roster row, no WakeProfile, no dock; the repo's own fleet message says so — yet the daemon delegates to it every cycle (`sarathi_wake_daemon.py:243`). 2 of 4 have no WakeProfile. `load_roster()` has no schema |
| Constitutional roster | `dharma_swarm/agent_constitution.py` | live | ANTHROPIC | 6 frozen `AgentSpec` rows with VSM function, gates, spawn authority, memory namespace | operator, archivist, research_director, systems_architect, strategist, witness | `~/.dharma/agent_memory/<ns>` | `_pool_model_id()` `:58-69`, asserts on unknown pool id | — | — | **Spelling drift on a live authority check**: `:169` grants spawn authority over `archaeologist` (a-r-c-h-**A**-e) while 8 other surfaces spell it `archeologist`; `runtime_can_spawn_worker` (`:391-401`) is a plain `in` test, so the correctly-spelled worker is denied. Roster names are disjoint from every other registry |
| `AgentRole` enum | `dharma_swarm/models.py:45-67` | live | — | The canonical 19-value role vocabulary (verified live) | 19 roles | — | — | — | — | Missing `builder` and `jagat_kalyan`, which exist as skill files — `AgentRole('builder')` raises `ValueError` (verified). Hand-duplicated into `ontology.py:1306-1313` |
| Ontology role enum | `dharma_swarm/ontology.py:1300-1320` | live | — | Agent ObjectType schema with a 19-value role ENUM | — | — | — | — | — | Hand copy, not derived. They agree today; adding an `AgentRole` member would silently break ontology validation |
| `ROLE_BRIEFINGS` | `dharma_swarm/daemon_config.py:149-179` | live | — | **The only role→persona text that reaches a built system prompt** (`agent_runner.py:955,962-966`) | 5 PSMV roles (verified live) | — | — | — | — | Covers 5 of 8 skill files; the rest get `"You are a {role} agent in the DHARMA SWARM."` — silent degradation, never an error |
| Intent router tables | `dharma_swarm/intent_router.py:205-291` | live | — | 9-name skill keyword/description vocabulary for TF-IDF routing | 9 incl. `deployer`, `monitor` | — | — | — | — | `deployer` and `monitor` exist in **no other registry** — routing to either yields a name nothing can instantiate. Omits `jagat_kalyan`. Keyword lists duplicate `.skill.md` frontmatter and already differ |
| `ROLE_PROFILES` | `dharma_swarm/context.py:1019-1080` | live | — | 5 per-role context-layer weight profiles | 5 | — | `agent_runner.py:995-999` | — | — | Third independent copy of the per-role-weight idea; field names do not even match `ContextWeights` in the skill frontmatter, and the skill-side weights are read into a model no consumer uses |
| `startup_crew` skill→role map | `dharma_swarm/startup_crew.py:80-99,359-400` | live | 8 provider types | **The one place the skill registry becomes runtime agents** | 7 mapped skills | — | `_SKILL_ROLE_MAP` | — | — | 7 entries for 8 skills — `jagat_kalyan` falls through to `GENERAL` (`:373`), colliding with `builder` (`:87`). Copies `skill.model` verbatim with no pool validation (`:380`). Swallows registry failure into `DEFAULT_CREW` at `logger.debug` (`:384-385`) |
| `ACTIVE_SURFACE_MANIFEST.yaml` | root + `tools/manifest_check.py`, `operator_core/control_surface.py` | live | — | Declared control-plane intent: state dir, 23 api routers, dashboard nav, `agents:` block | — | `~/.dharma` paths | — | `python3 tools/manifest_check.py` → all checks passed | `cybernetics_codex` declared, `runtime_status: declared_not_started` | The `agents:` block registers **subsystems**, not identities — it cannot reconcile against any roster. Hardcodes one agent's state path (`:31`). `manifest_check` proves module existence, not identity agreement |
| A2A onboard drift checker | `scripts/governance/a2a_agent_onboard.py`, `Makefile:797-802` | live | — | **The only mechanical cross-registry reconciler** | — | — | — | `make agent-register` / `--json` | — | Advisory only — "always exits 0" (`:15`, confirmed `:141`). Reconciles 2 of ~8 registries. Absent from `CI_TRUTH_CONTRACT.json`. Current drift (verified today): 2 ghosts, 4 invisibles |

### 2.10 Model routing registries

| Agent / Surface | Path(s) | Runtime Status | Provider Target | Role | Skills | Memory / FS | Routing Hook | Evidence Hook | A2A Readiness | Problems |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `MODEL_POOL` + `EVOLUTION_ROSTER` | `dharma_swarm/{model_pool,evolution_roster,model_defaults}.py` | live | 31 logical models (verified live) | The declared "ONE model-grain source"; ordered provider routes, tiers, power floor | — | — | `live_routes(key_oracle)`, **fail-open on `oracle=None`** (`:19-21,364`) | import-time coherence guard `:336-361` | — | Self-declared incomplete (`:22-24`, "STEP 2 … no call sites are switched yet"). 6 provider lanes guard-exempt (`:319-333`); 13 of 20 `DEFAULT_MODELS` have no pool entry |
| Lane defaults + `DGC_DIRECTOR_*` | `model_hierarchy.py`, `model_defaults.py`, `thinkodynamic_director.py`, `runtime_provider.py` | live | 11 `DGC_DIRECTOR_*_MODEL` env vars | Per-provider defaults, tier membership, lane-role priorities, intelligence seeds | — | — | `default_model(provider)` `:260-262` | — | — | The env namespace has **no registry** — 11 vars read from 4 files with no shared constant, no doc, no validation; `DGC_DIRECTOR_CODEX_MODEL` read in 3 places independently. `MODEL_INTELLIGENCE` (`:273`) is an uncheckable prose contract |
| `OrganismRouter._TIER_MODELS` | `dharma_swarm/model_routing.py:225-230` | dormant | 4 tiers | Complexity/language classification + budget-pressure routing | — | — | — | — | — | **Zero production callers** — `grep OrganismRouter` hits tests only, though the docstring claims it is wired into "the organism's nervous system". 3 of 4 tier ids resolve to `None` in the pool (`claude-sonnet-4-6` vs pool's `claude-sonnet-4.6`) |
| TUI model targets | `dharma_swarm/tui/model_routing.py` | live | pool-projected | Operator picker, with an import-time faithfulness guard | — | — | `resolve_model_target` | — | — | **None** — the only model registry in the repo that is actually derived rather than duplicated |
| `MODEL_ROUTING_MAP.md` | root | stale/unknown | — | 13-line archived stub; one live Sarathi note | — | — | — | — | — | Content archived; survives at root as a redirect. Its one live claim is correct but duplicates a fact the code owns |
| `MODEL_ROUTING_CANON.md` | `docs/architecture/` | stale/unknown | — | Declares itself "the single story for model and provider selection" | — | — | — | — | — | Every code cross-link is a machine-specific absolute path (`/Users/dhyana/…`, `:101-104,147-149,162-164`) resolving in no checkout. Never mentions `model_pool.py` — **two documents each claim to be the single source** |

### 2.11 Skill and agent-instruction registries

| Agent / Surface | Path(s) | Runtime Status | Provider Target | Role | Skills | Memory / FS | Routing Hook | Evidence Hook | A2A Readiness | Problems |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `SkillRegistry` + swarm skills | `dharma_swarm/skills.py`, `dharma_swarm/skills/*.skill.md` (8) | callable-but-partial | OPENROUTER, CLAUDE_CODE | 8 subagent personas with model/autonomy/tags/keywords/context_weights | 8 (verified live) | discovered from repo, `~/.dharma/skills/`, `.dharma/skills/` (`:185-189`); hot-reload 5s | `SkillDefinition.model/.provider` → `startup_crew.py:373-381` | live `discover()` | — | **The persona body is dead** — `agent_runner.py:947-966` never imports `skills.py`; `stage_executor.py:130` returns `description` in the `system_prompt` slot. Two skills are not `AgentRole` members. `mistralai/mistral-small-3.1-24b-instruct` (`researcher`/`validator` frontmatter) has no pool entry — the pool serves the `:free` variant |
| `.agents/skills/*/SKILL.md` | 5 dirs | prompt-only | external harnesses | Testing/verification playbooks for Devin et al. | 5 | — | — | — | — | **No in-repo reader** — grep finds only prose references; nothing validates they parse or that their commands exist. `testing-provenance/` declares `name: testing-provenance-ontology` (`:2`), the only dir/name mismatch |
| `.warp/skills/*/SKILL.md` | 4 dirs | prompt-only | Warp/Oz | Operator skills, each declaring a hard authority boundary | 4 | — | — | `oz-verify-claim.yml` | — | `docs/ops/OZ_INTEGRATION.md:14` claims a weekly `oz-repo-hygiene` schedule — **no such workflow exists**. `oz-verify-claim` is in no CI contract. `land-the-plane/SKILL.md:42` cites a `SkillRegistry` receipt for a registry that never parses `.warp` (`skills.py:185-189`) |
| chetana Claude Code plugin | `dharma_swarm/chetana/claude_code_plugin/**` | dormant | Claude Code | 1 skill, 5 lifecycle hooks, 6 slash commands | chetana | — | — | — | — | Not installed — `~/.claude/plugins` does not exist; the repo's tracked `.claude/settings.json` has no `enabledPlugins`. `plugin.json:8` homepage is a machine-specific `file:///Users/dhyana/…` path |
| `dgc skills` / `dgc orchestrate` | `terminal_commands/{meta,infrastructure}.py`, `dgc_cli.py` | live | — | Operator read of the skill registry; IntentRouter decomposition | — | — | — | — | — | Prints metadata only (`meta.py:108-113`), never the system prompt — reinforcing the false impression that the persona body is wired |

### 2.12 GitHub-side agents

The only stratum with proven, scheduled, effect-producing autonomy. 48 workflow
files (`ls .github/workflows/*.yml | wc -l`); 14 hold write authority with
autonomous triggers.

| Agent / Surface | Path(s) | Runtime Status | Provider Target | Role | Skills | Memory / FS | Routing Hook | Evidence Hook | A2A Readiness | Problems |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Automerge lane | `.github/workflows/automerge.yml` | live | GitHub Actions + `MERGEMASTERMIKE_PAT` | Triage, label-enrol, evaluate required checks, dispatch the router. **Never merges** (`:20`) | — | PR labels + dispatch-marker comments | events + hourly cron `45 * * * *` | `<!-- automerge-dispatch:${ready_key} -->` (`:298-347`) | none | Dispatch is inert without the PAT — the `${MIKE_PAT:-$GH_TOKEN}` fallback silently no-ops (`:78-85,:323`). Auto-enrols **every** open non-draft unlabelled PR with `mike-watch` on every pass (`:178-188`). Hot-path list at `:76` is oracle #1 of 3 |
| Merge Master Mike router | `.github/workflows/codex-mention-router.yml`, `scripts/runtime/pr_merge_control.py` | live | GITHUB_TOKEN; NATS secrets | **The only surface that executes a merge**: packet → gate → tier policy → `gh pr merge --squash --auto` | — | `${RUNNER_TEMP}/dharma-pr-review/`, `~/.dharma/pr_review` | mention gate `:29-45`; dispatch from automerge | `dharma.pr_review.mike_merge_receipt.v1` (`pr_merge_control.py:1678-1690`) | publishes to 8 `dharma.a2a.*` subjects when `--nats-session` | Merges as `github-actions[bot]`, not a Mike identity. Backlog fanout armed by loose substring matching (`:108-112`). `REQUIRED_REVIEWERS=codex` (`:167`) vs the script default `('codex','claude')` — the cloud quorum is one family |
| Mike backlog heartbeat | `.github/workflows/merge-master-mike-backlog.yml` | live | NATS secrets | Hourly scan of ≤100 PRs, packets for ≤5 | — | mike_fanout artifacts | cron `17 * * * *` | summary + artifact | always `--nats-session` | Scheduled runs default to `--packet-only` with `merge_mode off` — the hourly heartbeat merges nothing and **does not exercise the D4 daemon** |
| `pr_merge_control.build_gate` | `scripts/runtime/pr_merge_control.py:1295` | live | — | The widest merge-admission authority: draft, mergeable, reviews, coherence, CI truth, threads, receipts, risk | — | — | `HOT_PATH_PATTERNS` `:95` | `MERGE_GATE.json/.md` | — | **Never joined to the reversibility gate** — zero references to `classify_action`/`ActionClass`/`execution_lease` (verified). The NEVER_AUTO floor on merges lives only in the sibling CI check |
| Automerge tier policy | `.github/workflows/automerge-tier-policy.yml`, `scripts/governance/check_automerge_tier_policy.py` | live | — | Read-only admission: tier by path, diff ceiling, decorrelated quorum, rate limit, **reversibility floor** (`:238-262`) | — | `automerge_tier_policy.json` | loaded from the default branch so a PR cannot loosen itself | check-run status | — | Deliberate **vacuous-pass bootstrap** when absent from the default branch (`:60-76`). Gates on PR **title** + changed paths only — the diff body is never classified. Two reviewer families maximum |
| `loop-emergency-stop` | `.github/workflows/loop-emergency-stop.yml` | live | — | One-tap operator STOP; writes `KILLSWITCH` to the `loop-control` branch | — | `refs/heads/loop-control:docs/ops/loop_control/KILLSWITCH` | `workflow_dispatch` only | the file records actor/reason/run URL | — | `contents:write` on the whole repo; loop-control confinement is convention + test, not token scope. **Exercised exactly once** (run 30697803959, 2026-08-01T11:30:04Z, success) |
| `loop-resume` | `.github/workflows/loop-resume.yml` | live | — | Removes the KILLSWITCH; refuses unless the operator types `resume` | — | `refs/heads/loop-control` | `workflow_dispatch` only | step summary | — | none |
| Kill-switch guard contract | `tests/test_loop_killswitch_workflows.py`, `docs/ops/loop_control/README.md` | live | — | The shared first-step guard; unknown state fails closed | — | — | first step of guarded jobs | test pins guard as `steps[0]` | — | **Pinned set is 3 workflows** (`:26-30`) but 8 carry the guard — the other 5 can silently drop it. **Verified current state: branch `loop-control` exists (`40254231aa6d…`), KILLSWITCH file ABSENT — the switch is not engaged** |
| `walking-brief` | `.github/workflows/walking-brief.yml`, `scripts/runtime/walking_brief.py` | live | — | Daily read-only operator brief posted to a pinned issue | — | the issue thread | cron `0 21 * * *` | `<!-- walking-brief:v1 -->` | — | Deliberately **unguarded** by the kill switch (`:11-15`) — one autonomous issue-writer survives STOP. 2 scheduled runs, both success |
| `pr-ci-health` | `.github/workflows/pr-ci-health.yml` + 2 scripts | live | `PR_CI_HEALTH_PUSH_TOKEN` | Hourly triage / rerun / force-with-lease rebase. Never merges | `.claude/commands/pr-ci-health.md` | one auto tracking issue | cron `0 * * * *` + push to main | tracking issue + `ci-stranded-rebase-skipped` label | — | **No kill-switch guard** — a STOP does not stop hourly rebasing. Broadest permission set in the repo (`:58-63`) |
| `pr-dedupe` | `.github/workflows/pr-dedupe.yml` | live | — | Closes snapshot PRs and duplicate-title groups; deletes head branches | — | — | `pull_request_target` + cron `15 */6 * * *` | governance close comment | — | `pull_request_target` + `contents:write` on untrusted PR metadata; trust boundary is jq logic, not token scope. Deletes refs. **No guard** |
| `stale-pr` | `.github/workflows/stale-pr.yml` | live | — | Weekly staleness sweep; bots 11/14d, humans 27/30d | — | the `stale` label | cron `30 6 * * 1` | governance comment | — | **No guard**; `contents:write` used solely to delete branches |
| `docops-reconcile-main` | `.github/workflows/docops-reconcile-main.yml` | callable-but-partial | `DOCOPS_RECONCILE_TOKEN` | Regenerates counts after every merge; Tier 1 pushes **directly to main**, Tier 2 opens a bot PR | — | `chore/docops-autorefresh` branch | push to main | reconcile commit; `verify_head_checks()` | — | **The one workflow that can write to protected main** (`:158`). Header documents a 102-run silent failure. **No guard.** `pr-ci-health.yml:189-196` refuses to touch its branch to avoid a fight |
| `active-track` publisher | `.github/workflows/active-track.yml` | live | — | Advisory PR gate + force-push of derived rollups to `generated/status` | — | `refs/heads/generated/status` | PR + push + cron `23 13 * * 1` | orphan commit | — | Top-level perms read-only but the publish job self-grants `contents:write` (`:440`). Publishes with `--warn-only` (`:474`) — a blocking finding still yields a green-looking payload. **No guard** |
| `branch-janitor` | `.github/workflows/branch-janitor.yml` | live | — | Weekly TTL sweep; scheduled run is always dry-run, deletion needs dispatch + archive tags | — | `archive/pr<N>--<branch>` tags | cron `45 6 * * 1` | artifact reports | — | Job-local escalation to `contents:write` (`:72-74`) is easy to miss |
| `bot-pr-limit` | `.github/workflows/bot-pr-limit.yml` | live | — | Throttles automation PRs by intent (headRef pattern), not author | — | — | `pull_request` | error annotation + comment | — | The lane table is a hand-maintained case statement (`:41-58`) — any new automation lane evades the throttle until someone edits the file |
| `pr-collision-detect` | `.github/workflows/pr-collision-detect.yml` | live | — | BR-id collision commenter; the net named in `CLAUDE.md` | — | — | `pull_request` | comment upsert | — | none |
| `coherence-delta` | `.github/workflows/coherence-delta.yml` | live | — | Required context; **self-heals** by deriving and posting the Coherence Delta comment, then grading it | — | — | `pull_request` + merge_group | the comment it authored | — | **A gate that writes the evidence it grades** (`:3-8,26-30`) |
| `oz-verify-claim` (W1) | `.github/workflows/oz-verify-claim.yml` | dormant | Warp Oz cloud, `WARP_API_KEY` | The only workflow running a general-purpose LLM agent on the repo | `oz-verify-claim` | — | `pull_request` | PASS/FAIL/UNPROVEN comment | — | Entirely gated on `WARP_API_KEY`; when unset the job warns and does nothing **while its check reads green** (`:25-39`) — its own comment names this failure mode. Grants PR+issues write to a third-party action driven by a free-text prompt |
| `a2a-agni-live-contact` | `.github/workflows/a2a-agni-live-contact.yml` | callable-but-partial | AGNI NATS hub | Runner-side live fleet survey (sandboxes cannot reach the hub) | — | — | push to one ad-hoc branch + dispatch | run log only | **this is the A2A liveness probe** | Effectively dispatch-only — no schedule, so live fleet contact is never measured on a cadence. Its own header records that no peers are live on the hub |
| Sarathi wake lane | `.github/workflows/sarathi-wake-lane.yml` | scaffolded | github.token only — **no model secrets** | Intended GitHub-hosted standing wake loop; state round-tripped through orphan `sarathi-state` | — | `refs/heads/sarathi-state:state/sarathi/**` | cron `30 20 * * *` | artifacts + brief issue comment | mailbox-only | **NOT ON MAIN** — `git cat-file -e origin/main:…` fails (verified). Branch `sarathi-state` does not exist on origin (verified). Carries the guard but is not in the pinned set. Hardcoded fallback issue `1168` |
| Sarathi kill receipt | `.github/workflows/sarathi-kill-receipt.yml` | scaffolded | — | Operator attestation that the kill path works; Gate 9 input | — | `sarathi-state:state/sarathi/kill_path_receipt.json` | `workflow_dispatch` only | receipt cites corroborating run ids | — | **NOT ON MAIN** (verified). No guard step. Corroborates only the single newest success of each control workflow (`per_page=1`) |
| `TRUSTED_REVIEW_LOGINS` | `scripts/runtime/pr_merge_control.py:1017-1029`, `automerge_tier_policy.json`, `.github/CODEOWNERS` | live | Codex + Copilot reviewer Apps | The bot review/merge trust boundary; exact match keeps the `[bot]` suffix | — | — | consulted when `DHARMA_PR_ACCEPT_GITHUB_REVIEWS=true` | synthesized receipt with `source='github_review'` | 8 NATS subjects — a wider roster than the trust map | Only **one** reviewer family required in the cloud. `claude` and `devin` are in `DEFAULT_REQUIRED_REVIEWERS` (`:61-71`) with **no** `TRUSTED_REVIEW_LOGINS` entry — neither can ever satisfy the bridge |
| Advisory commenters | `.github/workflows/{spine-adoption,semgrep,gitleaks}.yml` | live | — | Non-merging commenters/annotators; gitleaks is required | — | — | PR + merge_group | comments / annotations | — | `spine-adoption` is explicitly advisory — the hard gate is `scripts/uplift_guards/check_spine_ownership.py` |
| Read-only gate set (rollup) | 25 workflows incl. `tests.yml`, `hermetic.yml`, `docops.yml`, `ci-parity.yml`, `codeql.yml`, `kernel-*.yml`, `langgraph-oracle.yml` | live | — | Take no autonomous action on repo state; emit check conclusions only | — | — | mostly `pull_request` + merge_group | check conclusions | — | Of 48 workflows, only **6** contexts are branch-protection required (`scripts/governance/ci_parity_manifest.json`) — a wall of green is not evidence of merge admission |

**Row count: 129 distinct surfaces**, counted mechanically from the tables above
(11-column rows, headers and separators excluded):

| § | Section | Rows |
| --- | --- | --- |
| 2.1 | Sovereign holon core | 7 |
| 2.2 | Classic persistent-agent stack | 5 |
| 2.3 | Living Agent Kernel | 3 |
| 2.4 | Authority, gate and effect primitives | 12 |
| 2.5 | Receipts and runtime state | 5 |
| 2.6 | A2A protocol, transport and directory | 21 |
| 2.7 | Mailboxes and buses | 11 |
| 2.8 | Runners, daemons and operator scripts | 15 |
| 2.9 | Identity registries | 14 |
| 2.10 | Model routing registries | 6 |
| 2.11 | Skill and agent-instruction registries | 5 |
| 2.12 | GitHub-side agents | 25 |
| | **Total** | **129** |

One of the 129 (the last row of §2.12) is a deliberate rollup covering 25
read-only CI gates that take no autonomous action; counting those individually
would give 153 surfaces and no additional insight.

---

## 3. Provider Matrix

Which agents can plausibly run under each provider class, per the source task's
categories. "Identity-only" marks a surface that *names* a model but constructs
no client — a distinction that matters enormously here and that the raw sweeps
established by reading `scripts/runtime/codex_composer_wake_loop.py` end to end
(1,405 lines, zero provider constructions).

| Provider class | Agents that genuinely dispatch | Identity-only / declared | Evidence |
| --- | --- | --- | --- |
| **OpenAI / Codex** | `codex_composer_semantic_responder` (direct-API chain); `composer_background_loop` (shells `codex` CLI); `AutonomousAgent`/`PersistentAgent` when `ProviderType.CODEX` resolves | `codex_composer` WakeProfile → `DGC_DIRECTOR_CODEX_MODEL` or `default_model(CODEX)`; `conductor_codex` | `codex_composer_wake_loop.py:71-77`; `composer_background_loop.py:455-462`; `conductors.py:81` |
| **Claude / Claude Code** | `holon_bridge`/`holon_talk`/`holon_run`/`holon_smoke` (declared route or free chain); `composer_background_loop` (shells `claude --permission-mode dontAsk`); `AutonomousAgent` | `fable_composer` → `default_model(CLAUDE_CODE)` = `claude-opus-4-6`; `conductor_claude`; `sarathi` → `default_model(ANTHROPIC)` | `holon_bridge.py:152`; `holon_talk.py:63-95`; `composer_background_loop.py:464-492`; `codex_composer_wake_loop.py:78-101` |
| **Grok** | **none** | `grok_build` has a registration card and a canonical subject — one of only two cards whose subject matches spec | `examples/agents/grok_build.registration.json:14` |
| **Gemini** | **none on any live path** | `gemini-3-pro` is a `MODEL_POOL` entry; `docs/sarathi_apex_build/08_…:12` still claims a `GOOGLE_AI` fallback the code no longer has | `model_pool.py`; contradicted by `codex_composer_wake_loop.py:98-101` |
| **Local model** | `AutonomousAgent`/`AgentRunner` via OpenRouter/Ollama when resolved | pool tail: `qwen2.5-coder:14b`, `deepseek-coder-v2:16b`, `llama3.2`; the semantic responder **deliberately excludes** OLLAMA | `codex_composer_semantic_inbox_drain.py:42-50` |
| **GitHub Action** | The entire §2.12 set — **the only proven autonomous dispatchers in the repo** | — | `automerge.yml` 8,388 runs; router executes `gh pr merge` |
| **Shell / Python worker** | `a2a_inbox_bridge`, `palantir_pilot_a2a_worker`, `devin_a2a_agent`, `merge_master_mike_daemon`, `sarathi_wake_daemon` (all `invoker=None` or pure transport), `RoamingPoller` (subprocess responder) | — | `sarathi_wake_daemon.py:22-32`; `palantir_pilot_a2a_worker.py:9-12` |
| **Browser agent** | **none grounded in repo files** | — | not reported |

Two provider-layer facts worth pulling out:

- **The seats' minds are not pool-verified.** `fable_composer` and `sarathi`
  both resolve to `claude-opus-4-6`, which `model_pool.entry_for_model_id`
  returns `None` for; it is a declared operator-pinned exception
  (`model_pool.py:319-333`) that the import-time coherence guard deliberately
  skips. Correct-by-exemption, but it means the wake seats bypass the pool.
- **`live_routes` fails open.** `model_pool.py:19-21,364` treats
  `oracle=None` as "routable", so a missing key oracle makes every route look
  live.

---

## 4. Activation Graph

What happens if the operator says *"Run Dharma Swarm against this repo goal."*

**There is no single answer, because there is no single entrypoint.** There are
four disjoint activation paths. Below is each, with every broken edge marked
`✗ BROKEN`.

### Path A — `dgc agent` (the operator's actual door)

```
operator
  → dgc agent wake <preset> ................ terminal_commands/agents.py:42
      → autonomous_agent.cli_wake ........... autonomous_agent.py:1483
          ✗ BROKEN: constructs AutonomousAgent with NO model_router
            (autonomous_agent.py:1487-1491) — CLI wakes bypass shared routing
      → AutonomousAgent.wake ................ autonomous_agent.py:434
          → telos check_action ............... autonomous_agent.py:954
          → AgentMemoryBank .................. autonomous_agent.py:422
      → AgentResult (no spine receipt)
  → dgc agent talk|run <holon> ............. terminal_commands/agents.py:101,118
      ✗ BROKEN: imports scripts.holon_talk / scripts.holon_run
        (agents.py:109,125) — pyproject.toml:60 ships only dharma_swarm*,
        so this breaks outside a source checkout
      → holon_bridge.load_holon ............. holon_bridge.py:106
          ✗ BROKEN for the one live holon: requires identity.json;
            load_holon('sarathi') → FileNotFoundError (verified)
  → dgc agent status ....................... terminal_commands/agents.py:148
      ✗ BROKEN: holon_health_rows() == [] while 20 cycles exist (verified)
```

### Path B — the whole-swarm daemon

```
operator → dgc orchestrate-live ............ dgc_cli.py:420,1462
  → task_factories["conductors"] ........... orchestrate_live.py:2325
      → run_conductor_loop ................. orchestrate_live.py:1684
          → PersistentAgent per CONDUCTOR_CONFIGS ... :1700
              ✗ BROKEN: conductors.py:74,84 resolve the provider at
                IMPORT time — a key loaded later is ignored
          → _run_with_restart .............. :1714
              ✗ BROKEN as evidence: :2300-2302 states a tick proves task
                liveness, not a completed wake cycle
      → PersistentAgent.run_loop ........... persistent_agent.py:580
          → wake() 10-step heartbeat ....... persistent_agent.py:369
              → MessageBus receive ......... persistent_agent.py:362  [LIVE]
              → TelosGatekeeper ............ persistent_agent.py:432  [LIVE]
              → AutonomousAgent.wake ....... persistent_agent.py:447  [LIVE]
              → witness JSONL .............. persistent_agent.py:557
                ✗ BROKEN: no conductor_*.jsonl exists on this box —
                  the loop has never run here
  supervisor: com.dharma.swarm.plist (KeepAlive true)
      ✗ BROKEN: WorkingDirectory is /Users/dhyana/dharma_swarm
```

### Path C — Sarathi apex (the only lane with a scheduler)

```
.github/workflows/sarathi-wake-lane.yml (cron 30 20 * * *)
  ✗ BROKEN: NOT ON origin/main (verified); branch sarathi-state absent
  → scripts/runtime/sarathi_wake_daemon.py
      → autonomy dial ...................... autonomy_dial.py:65
          ✗ WEAK: workflow default is `propose` — plans, dispatches nothing
      → holon_wake_cycle ................... sarathi_wake_daemon.py:373
          ✗ BROKEN: calls holon_wake_cycle, not run_holon_loop, so pass^k
            streak + spend_fn are dead (0/20 records carry passk_streak_after)
          ✗ BROKEN: passes no planned_action, so the in-loop reversibility
            gate (holon_runtime.py:99-100) never fires
          → killswitch ..................... holon_runtime.py:83   [LIVE]
          → check_cost_cap ................. holon_runtime.py:89   [LIVE but ~$0]
              ✗ BROKEN: increments from result["cost_usd"], a key
                holon_runtime.py never writes — ledger stays 0.0 forever
          → make_wake_work_fn → delegate_all ... delegate.py:195
              → classify_action FLOOR ....... delegate.py:218,225  [LIVE]
              → autonomy dial CEILING ....... delegate.py:237,249  [LIVE]
              → mailbox.enqueue_task ........ delegate.py:311-325
                  ✗ BROKEN: writes to ~/.dharma/sarathi/mailbox/tasks/;
                    RoamingPoller and RoamingDispatchDaemon both default to
                    <repo>/roaming_mailbox — ZERO consumers for this root.
                    delegate.py:24-25 justifies "dispatched" on the premise
                    that live pollers claim queued tasks. False here.
          → compass log_signal ............. holon_runtime.py:166
              ✗ DEGENERATE: telos_alignment 0.0 on 20/20 → GDS alarm
                constant-true
          → holon_persistence.save_cycle_record ... holon_runtime.py:218 [LIVE]
  liveness: only sarathi_proof_window.py can earn it
      ✗ BROKEN: requires an operator-written kill_path_receipt.json that
        is absent by design; no evidence it has ever passed
```

### Path D — A2A (the only path that closes, for exactly one agent)

```
scripts/runtime/a2a_send.py --route agent-inbox --to codex_composer
  ✗ BROKEN by default: --route defaults to ROUTE_A2A (a2a_send.py:744) →
    dharma.a2a.<recipient>, which no bridge subscribes to
    (a2a_inbox_bridge.py:98-99 filters dharma.agent.<uid>.inbox)
  ✗ BROKEN alias asymmetry: ROUTE_A2A skips resolve_agent_uid (:105-107)
    while ROUTE_AGENT_INBOX applies it — "devin" yields two disjoint mailboxes
  → NATS DHARMA_A2A
  → a2a_inbox_bridge (durable pull) ........ a2a_inbox_bridge.py:597-611  [LIVE]
      → dock ~/.dharma/a2a_bus/inboxes/<uid>/<packet_id>.json ....... :407
      → semantic_jobs sqlite ............... :138-209
          ✗ BROKEN: write-only — no module in the repo reads it
      → publish ack_subject ................ [LIVE]
  → codex_composer_semantic_responder ...... :467 globs *.json, :424 schema gate
      ✗ BROKEN for every other agent: no other uid has a responder process.
        Docks for hermes-m5, devin, merge_master_mike, grok_build accumulate
        deliveries nothing drains.
      ✗ BROKEN by format collision: composer_console.py:213-225 writes
        OPERATOR_STEER_*.md and composer_background_loop.py:542-545 copies
        arbitrary-named files into the SAME dock. Three schemas, one directory,
        each consumer silently skipping the other producers' files.
      → semantic drain → outbox artifact ... inbox_drain.py:267-268  [LIVE]
  → a2a_domain_reply_worker ................ :146-151  [LIVE]
  → a2a_reply_capture → receipt ............ :388-394  [LIVE]
      ✗ BROKEN as shared evidence: reports/a2a/*_receipts/ is gitignored
        (.gitignore:122) — invisible to CI and to any fresh checkout

Declared canonical alternative (DS_TASKS):
  a2a_cloud_contact.publish_cloud_ingress ... a2a_cloud_contact.py:151
      ✗ BROKEN: ZERO callers anywhere
  nats_transport.publish_task ............... :328
      ✗ BROKEN: only governance/evidence scripts call it
  nats_transport.consume_message ............ :466
      ✗ BROKEN: no daemon binds a durable; ensure_task_consumer never runs
        in production, so the DS_TASKS durable is never even created
```

### The role slots the task asked about

| Slot | Who fills it | Status |
| --- | --- | --- |
| **Entrypoint** | `dgc agent` / `dgc orchestrate-live` / `a2a_send` / a GitHub PR event | ✗ four disjoint doors, no single one |
| **Router** | `model_router` → `AgentRunner._build_route_request:687`; `spine/routing.py` | partial — `cli_wake` and `agent_runner` both bypass it |
| **Registry** | 5 competing rosters (§2.9) | ✗ no canonical registry |
| **Planner** | `delegate_all` (`delegate.py:195`) for Sarathi; `IntentRouter` for skills | partial — plans reach a mailbox nobody polls |
| **Worker agents** | `AutonomousAgent`, `PersistentAgent`, `palantir_pilot`, `codex_composer` responder | only the responder closes a loop |
| **Reviewer agents** | `chatgpt-codex-connector[bot]` via the router; `oz-verify-claim` | ✗ Oz is dormant; only one reviewer family required |
| **Synthesis agent** | **none grounded in repo files** | ✗ UNSOURCED |
| **Evidence log** | `holon_events.jsonl`, spine `EvidenceReceipt`, `reports/a2a/*_receipts/` | ✗ three stores, gitignored, no join key agreed (`trace_id` vs `correlation_id`) |
| **Dashboard / status surface** | `api/routers/{agents,fleet}.py`, `make organism-status`, `generated/status` branch | partial — `/agents` reads the empty ginko root (**D1**); `holon_health` is exposed in neither `api/` nor the dashboard |

---

## 5. Gaps Blocking Agents From Firing Together

Blunt, ranked by how much each one blocks the others. Every claim is
grep- or execution-verified.

**1. There is no canonical agent registry — there are five, and they disagree.**
`REGISTERED_AGENT_UIDS` (8, `a2a/agent_presence.py:15-24`) vs
`examples/agents/*.registration.json` (10) vs `inter_agent/` (13 seats) vs
`WAKE_PROFILES` (3, `codex_composer_wake_loop.py:110-138`) vs Sarathi's
`DEFAULT_ROSTER` (4, `holon_system/sarathi/roster.py:7`). Verified drift today:
2 GHOSTs (`codex_composer`, `hermes-m5` — rostered, no card), 4 INVISIBLEs
(`grok_build`, `merge_master_mike`, `qwen_code`, `sis_steward` — card, no
roster), 3 seats in no registry at all (`claude`, `gpt55`, `rushabdev`), and one
phantom (`fugu_ultra`) that Sarathi delegates to every cycle
(`sarathi_wake_daemon.py:243`). The only reconciler covers 2 of ~8 registries and
**always exits 0** (`a2a_agent_onboard.py:15,141`).

**2. Six mailbox address spaces, and no resolver dispatches on the declared
address.** `<repo>/roaming_mailbox/`; `~/.dharma/sarathi/mailbox/`;
`~/.dharma/a2a_bus/tasks/queue.jsonl`; `~/.dharma/a2a_bus/inboxes/<uid>/`; NATS
`dharma.a2a.<name>`; NATS `dharma.agent.<uid>.inbox`. The 10 registration cards
pick among four schemes at `examples/agents/*.registration.json:14` and nothing
reads that field. **8 of 10 cards disagree with `a2a_inbox_subject()`** (verified
by executing the comparison): six use the legacy compat subject, `sis_steward`
uses callsign-with-hyphen where the spec wants uid-with-underscore, and
`qwen_code` declares an empty subject.

**3. The declared canonical task stream has neither a producer nor a consumer.**
`DS_TASKS` (`a2a/nats_transport.py:69`) is fully built and heavily tested.
`publish_task`'s only callers are governance scripts; `consume_message` has no
non-test caller; `ensure_task_consumer` never runs in production so the durable
is never created; and the one declared ingress, `publish_cloud_ingress`
(`a2a_cloud_contact.py:151`), has **zero callers**. Meanwhile the compat sender
states `CANONICAL_RUNTIME_TRUTH_NATS_TASK_PATH = False` (`a2a_send.py:85`). The
migration mapping exists (`a2a_topology.py:84-86`) and nothing imports it.

**4. There is no universal task envelope, and the authority primitives have
never been composed.** Verified: **no file imports both `telos_gates` and
`reversibility_gate`**; **no file imports both `reversibility_gate` and
`execution_lease`**; `living_agent_kernel.py` contains **zero** references to any
of the three across 2,921 lines. `GateDecision.requires_execution_lease`
(`reversibility_gate.py:129`) is computed, serialized, and never acted on.
`pr_merge_control.build_gate` — the widest merge authority in the repo — has no
reversibility reference at all.

**5. Nothing supervises any Python agent.** The complete inventory: one daily
GitHub cron for Sarathi (**not on main**), one hourly cron that bypasses the D4
daemon, one daily read-only brief. Everything else is `tmux new-session`, which
does not restart a crashed process. Two supervisors are *declared and absent* —
`RESPONDER_LAUNCHD_LABEL = "com.dharma.codex-composer-semantic-responder"`
(`codex_composer_semantic_responder.py:64`) is stamped into every heartbeat with
no plist in the repo, and `living_agent_kernel_supervisor.py:35` plans
`com.dharma.living-agent-kernel`, which likewise has no plist. The LAK's
`--forever` mode is invoked by nothing.

**6. Liveness is self-reported everywhere, by four weak mechanisms.**
Heartbeat-file mtime; `tmux has-session`; **process-table regex**
(`composer_background_loop.py:92-95` greps for `codex exec.*codex_composer`);
and self-written `status.json`. `merge_master_mike_daemon.py:279` names
"treating tmux session existence as completion proof" as a forbidden inference —
and `codex_composer_wake_loop.py:1265-1286` writes `wake_loop_active:false` even
when tmux is missing. No surface is probed by anything external to itself.

**7. Nine role vocabularies and two agent-home roots.** Roles: `AgentRole` (19)
/ skill files (8) / `ROLE_BRIEFINGS` (5) / `CONSTITUTIONAL_ROSTER` (6, disjoint
names) / `intent_router` (9, inventing `deployer` and `monitor`) /
`agent_card._skills_for_role` (9) / registration-card `role` (8 more) /
`ontology.py` (hand copy) / `context.ROLE_PROFILES` (5). No two are equal
(verified live). Homes: `~/.dharma/agents` vs `~/.dharma/ginko/agents` (**D1**).
And a live authority check is broken by a **spelling**: `agent_constitution.py:169`
grants spawn authority over `archaeologist` while eight surfaces spell it
`archeologist`, so `runtime_can_spawn_worker` (`:391-401`) denies the correctly
spelled worker.

**8. The persona layer is decorative.** Editing any
`dharma_swarm/skills/*.skill.md` body has zero runtime effect:
`agent_runner._build_system_prompt` (`:947-966`) never imports `skills.py` and
sources only `ROLE_BRIEFINGS`; `fs_substrate/stage_executor.py:130` puts
`skill.description` in the tuple slot documented as `system_prompt`;
`swarm.py:2979-2989` and `dgc skills` project metadata only. `ROLE_BRIEFINGS`
covers 5 of 8 skills and the rest silently degrade to
`"You are a {role} agent in the DHARMA SWARM."` (`agent_runner.py:966`).

**9. Spine adoption is declared, not performed — and receipts cannot carry
authority.** `agent_runner.py:61-63` imports `invoke_agent` under
`# noqa: F401 (spine-adoption declaration)`; `grep -c invoke_agent` = 2 (the
comment and the import), **zero calls in 3,496 lines**. Separately,
`EvidenceReceipt` (`spine/receipt.py:41`) has no `action_class`, no `lease_id`,
and no admission decision — a dispatch receipt cannot answer "what authority
permitted this". `delegate.py:170` works around it by stuffing the gate dict into
`RoutingDecision.attributes`. And `EvidenceReceipt.cost_usd` (`:73`) is never fed
to `check_cost_cap` — the only per-dispatch cost record and the only USD enforcer
have never met.

**10. Nothing enforces any of the above, and the kill switch does not cover the
bots that act.** `check_name_drift.py` resolves imports, not agent names;
`manifest_check.py` reconciles module existence, not identity;
`a2a_agent_onboard.py` is advisory and in no CI contract. Of 48 workflows only
**6** contexts are branch-protection required. The kill-switch guard is pinned
for **3** workflows (`tests/test_loop_killswitch_workflows.py:26-30`) while 8
carry it — and the five most destructive autonomous bots carry **none**:
`pr-ci-health` (hourly rebase + push), `pr-dedupe` (closes PRs, deletes
branches, on `pull_request_target`), `stale-pr` (closes PRs, deletes branches),
`docops-reconcile-main` (**can push directly to protected main**), and
`active-track`'s publisher. An operator STOP does not stop any of them.

**Honourable mentions** (real, but they block fewer things): four lease
vocabularies with zero conversions; four name collisions (`GateDecision`,
`EvidenceReceipt`, `RuntimeTruthPacket`, `GovernancePolicy`);
`operator_core/permissions.py` unimportable without `textual`;
`hermes_heartbeat_poll.py:59` reading a queue path missing its `tasks/`
component — and its test monkeypatching the constant so the bug is unreachable;
and `reports/a2a/*_receipts/` being gitignored, which makes the entire A2A
evidence chain invisible from a fresh checkout.

---

## 6. Proposed Canonical Schema — `PersistentAgentDescriptor`

The full field-by-field reference, with the supplying repo surface (or
`UNSOURCED`) for every field, is a standalone document:

**[`docs/architecture/PERSISTENT_AGENT_DESCRIPTOR.md`](../architecture/PERSISTENT_AGENT_DESCRIPTOR.md)**

Summary of what it adds beyond the task's original 23-field draft, and why:

- **An `authority` block** (`permissions`, `trust_level`, `authority_ceiling`,
  `reversibility_floor`, `budget`, `lease_ref`). This is Packet 1 of the estate
  map's closure path (`HOLON_RUNTIME_FULL_ESTATE_MAP.md:646-658`) rendered as
  data. Without it a descriptor is a phone book, not a control plane.
- **A `Kind` column on every field**, `D` (declared) or `O` (observed). The
  failure this prevents is already in the codebase:
  `AuthorityPassport.telos_decision` defaults to `"allow"`
  (`living_agent_kernel.py:293`) and is populated verbatim from an untrusted
  wake payload (`:1473`), so a caller that omits the field is granted permission
  for free.
- **`last_seen` marked observe-only.** Every liveness signal in the repo today
  is self-reported (Gap 6).

Field-sourcing headline: of the 23 fields the 2026-05-28 task named, **3 are
fully `UNSOURCED`** (`latency_class`, `cost_class`, `mcp_tools`), **1 is
unsourced at agent granularity** (`owner` — only `CODEOWNERS`-level exists),
**2 are partial** (`working_directory`, `trust_level`), and **5 are
`CONFLICTING`** (`id`, `role`, `inbox_path`, `memory_paths`, `lifecycle_state`)
— which is strictly worse, because a loader must pick a winner and demote four
existing sources.

The load-bearing raw material already in the repo, ranked:

1. `ActionClass` (4) + `NEVER_AUTO_PATTERNS` (28) + `GateDecision`
   (`operator_core/reversibility_gate.py:47,63,118`) — stdlib-only,
   deterministic, total, already the discriminant at three independent call
   sites. Verified: `classify_action("git push origin main")` →
   `operator_only`, `never_auto_hit='git push'`.
2. `MutationTruth` (`operator_core/runtime_truth.py:115`) — eight effect
   booleans that map nearly 1:1 onto the NEVER_AUTO verb classes. The best
   existing *effect* descriptor.
3. `AutonomyLevel` + the `may_*` predicates (`autonomy_dial.py:36,76,81,86`) —
   the only primitive that declares its composition contract ("gate = floor,
   dial = ceiling", `:6`) and accepts a per-call override.
4. `GovernedWorkRequest`/`Admission`/`WorkKind`
   (`governed_work_admission.py:15,24,46`) — already the pydantic shape a kernel
   run carries; its weakness (all inputs caller-declared) is exactly what the
   descriptor fixes.
5. `spine.ExecutionIdentity` (`spine/identity.py:28`) — the existing carrier for
   `trace_id`/`correlation_id`/`task_id`/`run_id`, and the right owner of the
   correlation-name dispute.

---

## 7. Immediate Build Plan — the 3-PR path

Sized to be independently mergeable and independently valuable. Each honours
`HOLON_RUNTIME_FULL_ESTATE_MAP.md:708-710`: **compose existing owners, add no
new registry, router, task store, or receipt spine.**

### PR 1 — Descriptor schema + a projecting loader (no behaviour change)

**Create**
- `dharma_swarm/agent_descriptor.py` — the pydantic `PersistentAgentDescriptor`
  and a `load_descriptors()` that **projects** from existing owners
  (`agent_presence.REGISTERED_AGENT_UIDS`, `examples/agents/*.registration.json`,
  `WAKE_PROFILES`, `sarathi/roster.py`, `inter_agent/`, `CardRegistry`) rather
  than storing anything. Every field carries `source: str` naming the file it
  came from and `kind: Literal["declared","observed"]`.
- `tests/test_agent_descriptor.py`.

**Edit**
- `scripts/governance/a2a_agent_onboard.py` — widen from 2 registries to all
  five rosters, using the loader. Keep exit 0 for now.
- `docs/architecture/PERSISTENT_AGENT_DESCRIPTOR.md` — mark fields as sourced
  when PR 1 lands their projection.

**Tests**: descriptor round-trips for all 5 rosters; a golden test pinning the
current drift numbers (2 ghosts, 4 invisibles, 8/10 subject mismatches) so any
change to drift is visible in a diff; `latency_class`/`cost_class`/`mcp_tools`
assert `None` and are documented as backlog.

**Success criteria**: `python3 -c "from dharma_swarm.agent_descriptor import
load_descriptors; print(len(load_descriptors()))"` enumerates every uid in every
roster with its source; `make agent-register` reports drift across all five;
no runtime behaviour changes.

### PR 2 — One canonical address + drift becomes a gate

**Edit**
- `examples/agents/*.registration.json` — set every
  `metadata.canonical_transport_subject` to `a2a_inbox_subject(agent_uid)`,
  fixing the 8 verified mismatches, and fill `qwen_code`'s empty subject.
- `scripts/runtime/a2a_send.py:105-111` — apply `resolve_agent_uid` on **both**
  routes, killing the alias asymmetry that gives `devin` two mailboxes.
- `scripts/hermes_heartbeat_poll.py:59` — `a2a_bus/tasks/queue.jsonl`. **Remove
  the `QUEUE_FILE` monkeypatch from `tests/test_hermes_heartbeat_poll.py:44`**
  and assert the constant directly, so the bug class cannot recur.
- `dharma_swarm/holon_system/identity/canonical_names.py:6-8` — delete or invert
  `canonical_agent_uid`; it currently corrupts every hyphenated uid.
- `docs/governance/CI_TRUTH_CONTRACT.json` — add the drift check as **advisory**
  first, then required once green.

**Create**
- `tests/test_agent_address_coherence.py` — a ratcheted baseline asserting the
  card subject equals `a2a_inbox_subject(uid)` for all 10 cards, and that
  `sarathi_wake_daemon`'s mailbox root has at least one configured consumer.

**Tests**: existing `tests/test_a2a_send.py`, `test_a2a_inbox_bridge.py`,
`test_hermes_heartbeat_poll.py` must stay green.

**Success criteria**: the address-coherence test passes at 10/10 (from 2/10); a
default-route `a2a_send` reaches the same dock as an inbox-route send; `hermes`
polls the file the rest of the system writes.

### PR 3 — The typed action envelope: one governed effect, receipt-bound

This is estate-map Packet 1 and the whole point of PRs 1-2.

**Create**
- `dharma_swarm/action_envelope.py` — `ActionEnvelope` carrying
  `ExecutionIdentity` (`spine/identity.py:28`), the requested `ActionClass`,
  `MutationTruth` effect scope, `budget`, and `lease_ref`. Plus
  `authorize(envelope) -> AuthorizedAction | Refusal`, which composes **in this
  order**: `classify_action` floor → `AutonomyLevel` ceiling →
  `find_execution_lease_for_task` when
  `GateDecision.requires_execution_lease` → `check_cost_cap`. Fail closed on
  every absence, using `api/chat_tool_execution.py:208` as the template.
- `tests/test_action_envelope.py`.

**Edit**
- `dharma_swarm/holon_runtime.py:99` — make the gate step **unconditional**;
  a `planned_action` of `None` becomes `operator_only`, not "skip the gate".
- `scripts/runtime/sarathi_wake_daemon.py:373` — call `run_holon_loop` with a
  real `spend_fn` and a `planned_action`, closing **D3**.
- `dharma_swarm/holon_runtime.py` — write `cost_usd` into the cycle record so
  the daemon's ledger at `:387` stops incrementing by zero.
- `dharma_swarm/spine/receipt.py:41` — add optional `action_class`,
  `lease_id`, and `admission_decision`, so a receipt can answer "what authority
  permitted this". Extend `tools/manifest_check.py:75-85`, which already
  enforces the canonical definition site.
- Register `sarathi` properly: write `identity.json` so **D2** closes and
  `holon_health_rows()` stops returning `[]`.

**Tests**: `tests/test_holon_runtime.py` gains a case asserting that a wake
cycle with no `planned_action` **halts**; a case asserting a `NEEDS_LEASE`
action with no lease halts; an end-to-end case where one envelope produces one
effect, one lease reference, one budget decrement, and one `EvidenceReceipt`
sharing a single `trace_id`.

**Success criteria** (the estate map's, verbatim at `:657-658`): *one canonical
task reaches `GovernedEffectProven` and `ReceiptBound`; a blocked task produces
no effect.* Concretely — `dgc agent run sarathi 1` produces a cycle record whose
`gate_decision`, `lease_ref`, `cost_usd`, and spine `receipt_id` all carry the
same `trace_id`, and `DGC_SARATHI_AUTONOMY=shadow dgc agent run sarathi 1`
produces a `halted:*` record and zero mailbox writes.

**Explicitly out of scope for all three PRs**: making anything a standing
service. That is estate-map Packet 2/3 and needs a supervisor decision
(launchd vs GitHub Actions vs the LAK service) that this inventory does not make
for the operator. Note only that today the answer is *GitHub Actions* — it is
the sole stratum with proven, scheduled, autonomous effect.
