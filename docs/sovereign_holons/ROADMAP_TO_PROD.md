# ROADMAP TO PRODUCTION — the sovereign holon, 5 steps

**Date:** 2026-06-09 · **Author:** opus_composer, grounded in a reuse-map + per-organ gap audit.
**Two anchoring facts:** (1) **~85% of production substrate already exists** in dharma_swarm — the holon is a specialized instance inside it, never a parallel stack. (2) **Governance (Step 3) is the critical path** — it's what makes "sovereign" true vs. "smart chatbot," and it's a design problem (weeks), not a code problem (hours). Self-evolution is v1.5, deliberately out of v1.

Order follows Sid Buddhisara's safe-escalation stack (verification → govern → background): **don't animate the loop until the gate can refuse.**

---

## Step 1 — RUNWAY (clear the substrate, declare the lane) · *supervised, ~½ day*
**Goal:** a single buildable repo where the bridge can import.
**Reuse:** existing repo, `ACTIVE_TRACK.yaml` lane policy, `make governance-all`.
**Net-new:** merge `living_agent_kernel.py` (+ satellites) into main from `dharma_capital_lab`; reconcile the `external_agent_registration.py` 510→527 fork; declare the holon lane in a dedicated worktree; commit the `docs/sovereign_holons/` set.
**Green:** `python3 -c "import dharma_swarm.operator_core.living_agent_kernel"` exits 0 · lane declared · branch clean.
**Risk:** cross-worktree merge, 5 orphan-dir risk (KILL-NOTHING compost). **Needs you watching + git unlocked.** (= BUILD_STEP_ZERO #3/#4.)

## Step 2 — BRIDGE (talk to opus_composer as itself, read-only) · *8–16h*
**Goal:** the record→runtime bridge — the "first brick." A registered identity runs as *itself*.
**Reuse:** `runtime_provider.resolve_runtime_provider_config` (model door, the 1 wired organ), `conversation_log.log_exchange` (witness, no new owner), the `agents` API router, the dashboard chat overlay.
**Net-new (~150 LOC):** `holon_bridge.py` (`load_holon("opus_composer")` from `~/.dharma/agents/<name>/` → `RunningHolon`), the `POST /holon-chat` route, `tests/test_holon_bridge.py`.
**Green:** all **6 hardened verifiers** pass (see `02_FIRST_BRICK_SPEC` appendix) — you hold a real conversation with opus_composer running its *own* model/prompt/memory, witnessed, and it does NOT fall through to `_agentic_stream`.
**Risk:** low — pattern is Anthropic Managed Agents (session/harness/sandbox), verifiers already written.

## Step 3 — GOVERN (the critical path · the empty seat) · *effort forks on a strategic decision — see below*
**Goal:** "sovereign **within the banks**" — the agent is bounded by its values/authority. The empty seat in the 2026 field.

**⚠️ CORRECTION (2026-06-09, reconciled against prior verified audits):** the original draft said "reuse `telos_gates` as the PDP, ~2–3 weeks." **That is wrong.** Per `project_telos_gate_cannot_govern_selfmod` (6/1, 3-agent convergence) and the 6/5 hostile safety audit: the telos gate is a **paraphrase-evadable keyword heuristic with NO separable PDP** (decision+enforcement fused; REVIEW→PASS; `autonomy_policy` never read). `TelosProof` is vacuous (0 runtime importers); the "external reader gate" is self-graded. **You cannot "reuse" these as enforcement — they are the theater the audits named.** AND: your **5/30 trust→compass pivot deliberately chose NOT to build the fence** (pre-revenue, low-stakes) — the **COMPASS** (`_apply_compass_pull`, a bounded pull, not a refusing gate) is the *chosen* mechanism. So Step 3 is a **strategic fork, not a wiring task**:

- **Path 3a — COMPASS as banks (honest, cheap, aligned with 5/30):** v1 "sovereign within banks" = the agent is *pulled* toward telos (ledger-grounded, anti-Goodhart), not *gated*. No hard PEP. Honest framing: "bounded by a compass, not a fence." Effort: ~days (wire `_apply_compass_pull` into the holon loop). Limit: it cannot *refuse* — fine while stakes are low, dishonest to call "enforced."
- **Path 3b — build the real PDP/PEP (reverses 5/30; research-grade):** the 6/1 prescription — PDP/PEP split (NIST ABAC/OPA), typed versioned `GateDefinition`, semantic+structural risk classifier (SHACL + LLM-judge) replacing keyword scanning, REVIEW→hold/quarantine, `autonomy_policy` read before every tool call, fail-closed. This is the genuine "empty seat." Effort: **weeks–months of design, not 2–3 weeks**; the audits call it the real unsolved blocker. Only justified when a tripwire trips (real money / irreversibility / real autonomy — none tripped yet).

**Green (3a):** compass pull is wired + logged, holon choices measurably bent toward ledgered telos. **Green (3b):** a forbidden action is BLOCKED not warned · gate-crash → no action · `autonomy_policy.can_*` actually read · semantic paraphrase of a harmful edit is caught (the 6/1 test the keyword gate fails).
**Operator decision (the real one):** 3a now (honest compass, matches your pivot) and 3b only when stakes trip — OR commit to 3b now as a deliberate reversal. **Do NOT mislabel 3a as "enforced governance"** — that's the exact failure the 6/5 audit flagged.

## Step 4 — ANIMATE (persistent + autonomous, under the gate) · *~1 week*
**Goal:** it wakes, self-tasks, acts under the PEP, remembers across wakes, survives restart. Only *after* Step 3 — never animate an ungoverned loop.
**Reuse:** `PersistentAgent.wake()` + `_generate_self_task` (already work!), `AgentCronScheduler`, `hibernation`, `orchestrate_live`, `a2a_bus`, `economic_spine`/`budget.py` (per-cycle cost).
**Net-new:** `dgc agent wake <name>` for *registered* agents (today only 2 hardcoded conductors run); session→event-log replay so it resumes mid-flight; kill-switch.
**Green:** runs unattended N cycles · every action gated + receipted + budget-checked · accumulates memory/skills across wakes · survives kill→restart · `dgc agent kill` works.
**Risk:** medium — mostly wiring existing parts; the hard correctness (gate) is already done in Step 3.

## Step 5 — PRODUCTIONIZE (reliable, operable, at scale) · *1–2 weeks + ongoing*
**Goal:** a durable, observable, trustworthy service you can steer — and safely spawn a second holon.
**Reuse:** `control_surface.py` + dashboard + `dgc status` (SLO/health view), `budget.py` + `rollup_brakes` (cost caps + circuit breakers), `make governance-all` + the 6 verifiers (eval-gate-as-CI), `orchestrator` + isolated subagents (the 2026 single-threaded-writes consensus for multi-holon).
**Net-new:** wire cost-cap *enforcement* (today logs, doesn't halt); the outcome-claim-without-artifact refusal filter; a holon health panel; **close the ginko→agents migration** (`AGENT_HOME_RECONCILIATION`); optionally un-shadow `DGMLoop` (bounded self-evolution = v1.5) with a defined fitness function + skill-persistence home.
**Green:** durable service with dashboard + alerts + kill-switch + enforced cost caps · CI-gated deploys · a 2nd holon spawns safely · ginko fork closed.
**Risk:** low-medium — glue + observability; self-evolution (if included) re-opens design work, so keep it explicitly v1.5.

---

## Honest timeline (forks on the Step 3 decision)
- **Talkable demo (Steps 1–2):** ~1 week. A real sovereign-*identity* you converse with.
- **Bounded-by-compass (Steps 1–2 + 3a + 4):** ~2–3 weeks. Honest "sovereign within a compass," persistent, autonomous — *not* a refusing gate, and labeled as such. Aligns with the 5/30 pivot.
- **Hard-enforced governance (3b):** **+weeks-to-months, research-grade.** Only when a tripwire trips (money / irreversibility / real autonomy). This is the genuine empty seat and the genuine cost.
- **Production surface (Step 5):** +1–2 weeks of reuse-wiring on top of whichever Step 3 path.

## The one line that matters
Steps 1, 2, 4, 5 are mostly **reuse + wiring** of an 85%-built substrate — cheap and fast. **Step 3 is the whole ballgame, and it's a *decision*, not a task:** ship the honest COMPASS now (pull-not-gate, matches your pivot, days) and build the real PDP/PEP only when stakes demand it — **but never mislabel the compass as "enforced governance"** (the 6/5 audit's exact warning). The keyword `telos_gates` is not reusable as a fence; treating it as one is how the prior "all gates pass" theater happened.
