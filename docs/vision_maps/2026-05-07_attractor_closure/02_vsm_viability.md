# VSM Viability Map — dharma_swarm against Stafford Beer's Five Systems

**Mode**: READ-ONLY research. file:line cites only. UNKNOWN where unmeasurable.
**Anchoring frame**: recognition-mediated autopoiesis / attractor closure. Beer's VSM = HOW the changing organism stays viable. The Gnani layer (kernel axioms, telos gates) = WHAT it preserves. This report only inventories the HOW.

---

## 1. VSM Frame

In Beer's *Brain of the Firm* / *Heart of Enterprise*, a viable system has five recursively-nested subsystems plus an algedonic bypass:

- **S1 (Operations)**: the primary doing — autonomous units that produce the system's value. Implementation, agents, the front line.
- **S2 (Coordination)**: the anti-oscillation channel between S1 units. Damping, scheduling, shared timing — *not* control, just dissonance suppression.
- **S3 (Control / Resource Bargain)**: here-and-now management. Allocates resources, enforces accountability, sets quotas, runs the inside-and-now picture.
- **S3\* (Audit)**: sporadic, sampling channel that lets S3 verify S1 reality without going through S2's normal reporting. The "spot check."
- **S4 (Intelligence / Adaptation)**: outside-and-future. Scans the environment, models the system in its world, brings adaptation pressure back inward.
- **S5 (Identity / Policy)**: closure of the loop. Holds invariant identity, arbitrates the S3↔S4 homeostat, defines what the organism *is* such that S3 and S4 can be reconciled.
- **Algedonic channel**: pain/pleasure bypass — any subsystem can fire a signal that skips S1-S4 and reaches S5 directly. The fire alarm.

dharma_swarm declares this mapping explicitly in `vsm_channels.py:13-19`.

---

## 2. Channel Mapping Table

| S-channel | dharma_swarm modules | file:line | status | evidence |
|---|---|---|---|---|
| **S1** Operations | `agent_runner.py` (AgentPool, AgentRunner), `swarm.py` (SwarmManager), `task_board.py`, `orchestrator.py` dispatch loop | `swarm.py:1-77`, `orchestrator.py:72-80` | PRESENT | `swarm.py:1-9` declares Layer 4 swarm lifecycle manager; `orchestrator.py:1-13` declares duck-typed task_board↔agent_pool dispatch; `_RUNTIME_HEALTH_STATE` tracked at `orchestrate_live.py:56-66` |
| **S2** Coordination | `message_bus.py` (a2a SQLite pub/sub), `signal_bus.py` (loop-to-loop event bus), `stigmergy.py` (pheromone), `sheaf.py` (compatibility checking) | `message_bus.py:1-9`, `signal_bus.py:1-13`, `sheaf.py:1-7` | PRESENT | `signal_bus.py:8-11` explicitly: "swarm drains ANOMALY_DETECTED to suppress director during crises" — anti-oscillation as designed. `sheaf.py:1-7` adds compatibility-of-local-sections coordination via H¹ obstructions |
| **S3** Control | `telos_gates.py` (11 gates), `dharma_kernel.py`/`KernelGuard` (25 axioms), `evolution.py` DarwinEngine, `swarm.py` SwarmManager resource allocation, `daemon_config.py` quotas | `vsm_channels.py:14`, `swarm.py:23` (DaemonConfig import), `swarm.py:1431-1437` (`dispatch_next` route + spawn) | PRESENT | Gates evaluated via `check_with_reflective_reroute` imported at `orchestrator.py:48`; S3↔S4 feedback loop wired in `vsm_channels.py:204-224` (`receive_zeitgeist_signal` boosts SATYA/STEELMAN, relaxes VYAVASTHIT) |
| **S3\*** Audit | `auditor.py` (Auditor.tick, 4 audit types), `vsm_channels.py:259-365` (SporadicAuditor), `audit_queries.py` (ontology audit), `witness/` JSONL | `auditor.py:1-15`, `vsm_channels.py:259-365`, `swarm.py:175,464,2421-2430` | THIN (designed PRESENT, runtime data ABSENT) | Code complete; runtime evidence is `~/.dharma/meta/sporadic_audits.jsonl` = **1 line** (vs 2737 algedonic). `WitnessAuditor initialized` log line at `swarm.py:464`, but the on-disk audit ledger is essentially empty |
| **S4** Intelligence | `zeitgeist.py` (env scanner), `auto_proposer.py` (failure-pattern observer → Darwin), `scout_framework.py` (domain scouts), `pending_proposals.py` (queue), `algedonic_bridge.py` declares S4 source | `zeitgeist.py:1-9`, `auto_proposer.py:1-21`, `scout_framework.py:1-19`, `algedonic_bridge.py:209-210` | PARTIAL | Zeitgeist runs every 600s per `zeitgeist.py:8`; on-disk artifact `~/.dharma/meta/zeitgeist.{md,jsonl}` exists and is fresh. `auto_proposer.py:50-73` enumerates 8 ObservationType→ProposalSource pairs — internal scan is wider than external scan. Outward sensing (scout_framework) is opt-in CLI rather than always-on |
| **S5** Identity / Policy | `identity.py` IdentityMonitor (TCS=0.35*GPR+0.35*BSI+0.30*RM), `dharma_kernel.py` (25 axioms, SHA-256 signed), `organism.py` (HeartbeatResult.identity_coherence), `algedonic_activation.py` (S5-driven action) | `identity.py:1-20,105-112`, `organism.py:73-119,309-310`, `vsm_channels.py:17` | PRESENT | TCS measured every heartbeat at `organism.py:309-310`; on-disk `~/.dharma/identity_history.jsonl` exists; drift correction `~/.dharma/.FOCUS` exists (file present); `IdentityMonitor.DRIFT_THRESHOLD=0.4` at `identity.py:111` |

Six of six channels exist as code. Distribution of operational evidence is not uniform — see §5.

---

## 3. Algedonic Channel — Beer's Pain/Pleasure Bypass

**Class definitions and call sites (all verified)**:
- `vsm_channels.py:72-98` — `AlgedonicSignal` Pydantic model (severity, source_system, title, description, recommended_action, context, acknowledged).
- `vsm_channels.py:373-564` — `AlgedonicChannel` class: persists to `~/.dharma/meta/algedonic.jsonl`, writes `~/.dharma/meta/ALGEDONIC_ACTIVE.md` operator summary, callbacks list at `vsm_channels.py:398`, async `fire()` at `:410-435`, four typed checks (`check_gate_streak` `:437`, `check_health` `:459`, `check_evolution_stagnation` `:478`, `check_cost_spike` `:498`).
- `organism.py:968-1003` — second `AlgedonicSignal` dataclass on `HeartbeatResult.algedonic_signals` (note: separate type from `vsm_channels.AlgedonicSignal`; see Open Q4).
- `organism.py:1155-1189` — `_check_algedonic` fires `telos_drift` (severity=critical) when blended coherence < `TELOS_DRIFT_THRESHOLD` AND `_has_history`, plus `omega_divergence` (severity=medium) when `|live_score - tcs| > OMEGA_DIVERGENCE_THRESHOLD`.
- `swarm.py:443` — `OrganismRuntime` constructed with `on_algedonic=self._algedonic_handler`.
- `swarm.py:1440-1510` — `_algedonic_handler`: appends to `~/.dharma/algedonic_signals.jsonl`, writes `EMERGENCY_HOLD` only after 3 consecutive criticals (counter resets on any non-critical), fires macOS `osascript` notification with "Sosumi" sound.
- `algedonic_bridge.py:1-301` — explicit out-of-process bridge for cron callers. Always writes the jsonl at `~/.dharma/algedonic_signals.jsonl` (`algedonic_bridge.py:87-96`), writes witness mirror `~/.dharma/witness/{date}/{source}_signal.jsonl` (`:99-110`), tries to route to live organism singleton (`:178-232`), independently writes `EMERGENCY_HOLD` if 3 criticals within `CRITICAL_WINDOW_SECONDS=3600` (`:113-175`).
- `algedonic_activation.py` — Beer's algedonic-as-action layer; imports `AlgedonicActivation` at `organism.py:139-143` and applies actions inside the heartbeat at `organism.py:323-360`.

**Where it triggers**:
- Telos drift inside heartbeat (`organism.py:1165-1174`) — the present-moment branch.
- Omega divergence (live vs trailing TCS) (`organism.py:1176-1187`).
- Gate failure streak ≥ 3 (`vsm_channels.py:437-457`, wired through `VSMCoordinator.on_agent_output` at `vsm_channels.py:790-794`).
- Health < 0.3 (`vsm_channels.py:459-476`).
- Evolution stagnation ≥ 50 cycles (`vsm_channels.py:478-496`, called from `organism.py:755`).
- Cost spike > 5x rolling average (`vsm_channels.py:498-516`, called from `organism.py:768`).
- Cron / out-of-process callers via `algedonic_bridge.fire_signal` (`algedonic_bridge.py:235-300`).

**Where it is consumed**:
- `_algedonic_handler` (`swarm.py:1440`) — file persistence, EMERGENCY_HOLD escalation, OS notification.
- `_on_algedonic` callback registered at `organism.py:255` — feeds into `HeartbeatResult.algedonic_active` count and gets propagated to memory graph entity_type `algedonic_event` (`organism.py:809`).
- `algedonic_activation.py` — converts signals into in-loop pulse actions (`organism.py:323-328`).

**Does it actually override normal channels?** Partially:
- It bypasses S2/S3/S4 to write directly to S5's identity log and macOS UI — yes.
- It can halt the swarm via `EMERGENCY_HOLD` — but only after **3 consecutive** criticals (`swarm.py:1471-1487`); single criticals are deliberately downgraded "to prevent self-strangulation during bootstrap" (`swarm.py:1467-1468`). This is a softening of Beer's intent: the alarm pulls but doesn't immediately stop the line.
- Two parallel persistence paths exist (`~/.dharma/algedonic_signals.jsonl` written by both `swarm._algedonic_handler:1451` AND `algedonic_bridge._write_signals_jsonl:87`) plus `~/.dharma/meta/algedonic.jsonl` (`vsm_channels.py:395`). The latter is **not present on disk** — see Open Q4.

**Live evidence**: `~/.dharma/algedonic_signals.jsonl` = **2737 lines**; tail shows recurring `omega_divergence severity=medium value=0.683`. `~/.dharma/meta/algedonic.jsonl` and `ALGEDONIC_ACTIVE.md` do **not** exist on disk. `EMERGENCY_HOLD` does **not** exist on disk. The channel fires but currently fires only one repeating tune.

---

## 4. Recursion Depth — Does S1 Contain S1-S5?

**Asserted in code**: `vsm_channels.py:111-134` defines `AgentViability` with `s1_operations`, `s2_coordination`, `s3_control`, `s4_intelligence`, `s5_identity` floats and a geometric-mean `compute_overall()`. The header comment at `vsm_channels.py:7-8` lists "Agent-Internal Recursion: agents self-assess S1-S5 health" as Gap 4 to be closed. `AgentViabilityMonitor` (`vsm_channels.py:572-618`) aggregates these and fires `algedonic.check_health` when overall < 0.4 (`vsm_channels.py:596-602`). The wire-up is at `organism.py:743-748` — `s5_identity=s5` etc. fed into `AgentViability(...)`.

**What's present**: a recursive *measurement schema* at agent granularity (5-tuple per agent, geometric mean, fleet aggregation), and a single recursion step from organism-level S5 down to per-agent S1-S5 scores.

**What's absent / UNKNOWN**:
- No agent has its own *running* S1-S5 subsystems — there's no agent-internal coordination bus, no agent-level S3* sporadic auditor, no agent-level zeitgeist scanner. The "5 numbers" are sensor readouts, not five recursively-viable subsystems.
- VentureCell-level recursion (the foundation document concept of fractal VSM at the project / cell scale) — UNKNOWN: no module named `venture_cell.py` or similar surfaced in this read pass; not verified.
- Foundations directory listing returned empty in this session (`ls foundations/` produced no output) — the `PILLAR_08` Beer reference cited at `vsm_channels.py:19` is asserted in code but the document itself was NOT verified (UNKNOWN whether the pillar file exists in this worktree).

**Verdict**: recursion is asserted at the level of *self-assessment data structure* (one level deep) but is **not** instantiated as nested viable systems. Beer's claim that S1 must itself be a viable system, recursively, is at the design-comment layer, not the runtime layer.

---

## 5. Channel Health by Evidence

### S1 — Operations
- **Strong**: `_RUNTIME_HEALTH_STATE` mutable dict in `orchestrate_live.py:56-66` is updated on every tick; SwarmManager wired to OrganismRuntime via `on_algedonic` at `swarm.py:443`.
- **Strong**: `Orchestrator.dispatch_next` at `swarm.py:1431-1437` is invoked from the live loop.
- **Thin**: prior observation 1358 (May 2): "546-module dharma_swarm has visionary architecture mostly unwired"; prior observation 2173 (May 4): "Core Vision Has Zero Importers." S1 is *broad* (many modules) but the main entry path through them is narrower than the module count suggests.

### S2 — Coordination
- **Strong**: `signal_bus.py:26-44` defines 14+ canonical signal types; `message_bus.py:30-80` defines messages/heartbeats/subscriptions/artifacts/events DDL; both used in live wiring (prior obs 3649 May 5: "exact hook locations across swarm/orchestrator/agent_runner").
- **Strong**: `sheaf.py` provides H¹-obstruction coordination — anti-oscillation at the *epistemic* layer (compatible local sections glue or surface as conflicts at `sheaf.py:88-106`).
- **Thin**: signal bus events expire after TTL (`signal_bus.py:55-60`) — coordination is in-process per asyncio loop. Cross-process / cross-worktree S2 is not wired (5-worktree mirror problem from CLAUDE.md applies here too).

### S3 — Control
- **Strong**: 11 telos gates + 25 kernel axioms imported and routed via `check_with_reflective_reroute` (`orchestrator.py:48`). Pattern aggregator at `vsm_channels.py:142-251` records every gate check.
- **Strong**: S3↔S4 feedback explicitly closed via `receive_zeitgeist_signal` (`vsm_channels.py:204-224`) — threat keywords boost SATYA/STEELMAN sensitivity.
- **Thin**: prior obs 2698 (May 4): "Runtime State Authority Is Split Across Four Competing Sources" — S3's resource-bargain authority is not single-rooted.
- **Thin**: prior obs 2697 (May 4): "TelicSeam Metabolic Chain Fractures Across In-Process Instances" — the write-through layer between control decisions and ontology has known fragmentation (`telic_seam.py:51-75` is per-instance state).

### S3* — Audit
- **Strong (designed)**: two implementations — `auditor.py:69-91` (4 audit types, random.choice per tick) and `vsm_channels.py:259-365` (output-level random check at 5%); plus ontology-level `audit_queries.py:30-59` (`recent_blocks`, `unrecorded_actions`).
- **Thin (operational)**: `~/.dharma/meta/sporadic_audits.jsonl` = **1 line**. `~/.dharma/meta/gate_proposals.jsonl` = **1 line**. The S3* function exists in code; the S3* function is not running with any meaningful frequency. Prior obs 2400 (May 4): "dual_audit.py Skips Automatically Inside Nested Claude Session" — at least one audit pathway has a known skip-condition.

### S4 — Intelligence
- **Strong**: `~/.dharma/meta/zeitgeist.{md,jsonl}` files exist; cadence declared 600 s in `zeitgeist.py:8`.
- **Strong**: `auto_proposer.py:50-73` defines 8 distinct ObservationType→ProposalSource flows (fitness drop, failure pattern, stigmergy hotspot, provider failure, stale tasks, fitness plateau, test failure cluster, evolution stagnation).
- **Thin**: outward-facing scout cadence is opt-in (`scout_framework.py:9-18` shows `--once` / `--interval 3600` modes); not wired into the always-on live loop the way zeitgeist is.
- **Thin**: zeitgeist's "claude scan" is "optionally uses claude -p subprocess... when available" (`zeitgeist.py:2-4`) — outside-the-box scanning depends on auth state.

### S5 — Identity
- **Strong**: TCS measured every heartbeat (`organism.py:309-310`); `~/.dharma/identity_history.jsonl` exists; `.FOCUS` correction file present on disk.
- **Strong**: kernel SHA-256 signature pattern declared in CLAUDE.md (`dharma_kernel.py`); 25 axioms enumerated.
- **Thin**: per `identity.py:40-57` `_SEMANTIC_PULSE_FAILURES` table, S5 measurement *itself* depends on `claude` CLI binary + auth — degraded readings cascade ("pulse_binary_missing" critical=0.35). S5's *signal quality* is fragile to the same dependencies S1 uses.

### Algedonic
- **Strong**: 2737 signals on disk, monotonic recent timestamps, registered handler at `swarm.py:443`.
- **Thin**: signals are dominated by `omega_divergence severity=medium value=0.683` repeating — **the channel is firing but is in a degenerate steady state**, not an event channel. EMERGENCY_HOLD has never escalated (file absent). The "fire alarm" is ringing softly and continuously, which is functionally close to silence.

---

## 6. The S4–S5 Seam — Where Adaptation Meets Invariant

The S4↔S5 seam is the *most consequential* in Beer's model: S4 brings outside/future variety; S5 holds invariant identity; the two must continuously reconcile. dharma_swarm wires this seam in **three distinct places**, with overlap and gaps:

### Seam wire 1 — `vsm_channels.py` GapPattern → VarietyExpansion
- `vsm_channels.py:803-825` `run_zeitgeist_feedback`: zeitgeist signals feed `gate_patterns.receive_zeitgeist_signal` (S4→S3 boost) AND if ≥3 threat signals appear in one cycle, `variety.propose("EMERGING_THREAT", tier="C", ...)` is called.
- `vsm_channels.py:684-700` proposals must be `approved` by reviewer="dhyana" → S5 is explicitly the human operator for gate-array expansion.
- This is Ashby's Law operationalized: S4 detects new variety in the environment; S5 (Dhyana) approves whether the gate array (S3) expands to absorb it.

### Seam wire 2 — `auto_proposer.py` → Darwin → telos gates → S5
- `auto_proposer.py:14-19` describes the loop: detect → propose → test → integrate. Proposals queued into `~/.dharma/evolution/pending_proposals.jsonl` via `pending_proposals.append_pending_proposal` (`pending_proposals.py:9-23`).
- "All proposals pass through telos gates before execution" (`auto_proposer.py:17`) — gates (S3, telos-grounded by S5 axioms) are the literal seam between the adaptation engine and the identity layer.
- This is the *evolutionary* S4→S5 seam: environment-driven mutations only land in identity if they pass the gates that encode identity.

### Seam wire 3 — `telic_seam.py` ontology write-through
- `telic_seam.py:7-12`: "need appears in ontology → action proposed → gates evaluate → orchestrator claims lease → agent executes → outcome recorded → value measured → fitness updated → routing changes → projections refresh."
- `telic_seam.py:51-75` defines `TelicSeam` as a write-through that records `ActionProposal` → `GateDecisionRecord` (per prior obs 2279 May 4) → `ExecutionLease` → `Outcome` → `ValueEvent`.
- This is the *bookkeeping* S4↔S5 seam: every adaptive action and its identity-gate verdict become first-class ontology objects, available to `audit_queries.recent_blocks` (`audit_queries.py:30-41`) and `unrecorded_actions` (`audit_queries.py:44-59`).
- Prior obs 1118 (May 1): "TelicSeam exists but is best-effort, directors bypass ontology"; prior obs 2697 (May 4): "TelicSeam Metabolic Chain Fractures Across In-Process Instances"; prior obs 3307 (May 5): 1806 Outcomes, 1803 ValueEvents, 1803 Contributions on disk, but **GateDecisionRecord schema-only** — i.e., the seam writes outcomes but not the gate verdicts. The seam is half-closed.

### Seam wire 4 — `identity.py` zeitgeist-boosted RM weight
- `identity.py:18-19`: "S4 → S5 feedback: zeitgeist threats boost RM weight." `IdentityMonitor.measure(threat_boost=True)` is the signature. This is S4 directly modulating S5's *measurement formula*, not just S5's policy actions — the most intimate seam of the four.

**Overall seam diagnosis**: the seam is wired at four loci (gate-pattern aggregation, variety expansion, evolution proposal, telic-seam ontology, identity-formula boost) — strong intent. Three of the four loci show fracture: variety_expansion has 1 proposal recorded, telic_seam fragments across in-process instances, GateDecisionRecord is schema-only. Zeitgeist→identity-formula and zeitgeist→gate-sensitivity are the two seam wires with cleanest live evidence.

---

## 7. Open Questions

1. **Two `AlgedonicSignal` types**: `vsm_channels.AlgedonicSignal` (Pydantic, `vsm_channels.py:72-98`) vs `organism.AlgedonicSignal` (dataclass, `organism.py:968`). The bridge attempts a translation at `algedonic_bridge.py:206-214`. Which is canonical, and what's lost in translation? UNKNOWN.

2. **Why does `~/.dharma/meta/algedonic.jsonl` not exist while `~/.dharma/algedonic_signals.jsonl` has 2737 lines?** Code at `vsm_channels.py:395` writes to the former; code at `swarm.py:1451` and `algedonic_bridge.py:52` writes to the latter. Is the `vsm_channels.AlgedonicChannel` actually instantiated and `.fire()` called in production, or is the live system using only the organism-dataclass path through `_algedonic_handler`?

3. **S3* paradox**: the audit channel exists in three places (`auditor.py`, `vsm_channels.py:SporadicAuditor`, `audit_queries.py`) but `~/.dharma/meta/sporadic_audits.jsonl` has 1 line. Is S3* gated off, gated by `should_audit()` probability=0.05 with too few inputs, or simply not on the live cron?

4. **Recursion claim vs reality**: foundation comments and CLAUDE.md (Beer's VSM for civilization, `cabinet/worldview/telos.md:18`) imply recursive viability at agent / VentureCell / civilization scales, but only one recursion step is implemented (`AgentViability`), and that step measures rather than instantiates.

5. **Algedonic in degenerate steady state**: the same signal (`omega_divergence value=0.683`) recurs. Is the channel correctly reporting a real chronic divergence, or has the threshold tuning collapsed it into a stuck oscillator that operators have learned to ignore? At 2737 signals, the signal-to-attention ratio is approaching zero.

6. **Cross-worktree VSM**: 5 worktrees mirror dharma_swarm hot-path symbols (per CLAUDE.md). Each worktree has its own `~/.dharma/`-bound state? Or one shared? UNKNOWN — implications for whether there are 5 parallel viable-system instances or one shared identity layer with 5 operational bodies.

7. **The "softening" of EMERGENCY_HOLD**: `swarm.py:1467-1468` deliberately requires 3 consecutive criticals before halting "to prevent self-strangulation during bootstrap." But the system is no longer in bootstrap. Is this still appropriate, or has the threshold drifted from its original justification? Beer would say: an alarm that doesn't stop the line isn't really an alarm.

8. **S5 measurement depends on S1 binaries**: `identity.py:40-57` shows the `claude` CLI being absent or unauthenticated cascades into critical TCS readings. If S1 (operations) collapses, S5 cannot measure that it has collapsed — circular sensor coupling. Is there an S5-internal heartbeat that doesn't depend on the operational binary?

---

## 200-Word Summary

**Status of each S-channel.** S1 (operations): PRESENT, broad but with prior-observation evidence that vision-layer modules have zero importers. S2 (coordination): PRESENT, well-implemented as in-process signal bus + SQLite message bus + sheaf compatibility checks; not cross-process. S3 (control): PRESENT, 11 gates + 25 axioms wired through orchestrator; runtime state authority known-fragmented across 4 sources. S3* (audit): code-PRESENT in three loci, runtime-THIN (1 line on disk vs 2737 algedonic). S4 (intelligence): PARTIAL — zeitgeist runs, scouts opt-in, claude-scan auth-fragile. S5 (identity): PRESENT, TCS measured every heartbeat, but S5's own sensor depends on S1 binaries (circular). Algedonic: fires but in degenerate steady state — same `omega_divergence=0.683` repeats.

**Weakest channel**: S3* — the audit data on disk is essentially nonexistent; the channel exists as code, not as practice.

**Strongest edge**: the S3↔S4 explicit feedback at `vsm_channels.py:204-224` (zeitgeist threat → SATYA/STEELMAN sensitivity boost) — clean wire, both sides instantiated.

**Top open question**: why `~/.dharma/meta/algedonic.jsonl` is empty while `~/.dharma/algedonic_signals.jsonl` has 2737 lines — which AlgedonicChannel is canonical and which is dead code?
