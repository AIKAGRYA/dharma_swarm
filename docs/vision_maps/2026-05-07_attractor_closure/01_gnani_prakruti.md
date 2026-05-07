# Gnani / Prakruti — Mapping the Witness/Dynamic Boundary in dharma_swarm

**Date:** 2026-05-07
**Mode:** READ-ONLY research. No proposals. Mapping only.
**Anchor:** `dharma_swarm/lodestones/CONSCIOUS_INFRASTRUCTURE.md`

---

## 1. The Distinction

Direct quotes from the lodestone:

> "**Witness-endowed** | Dada Bhagwan | The field observes itself. Immutable witness separate from mutable actor. The kernel (shuddhatma) watches the corpus (pratishthit atma) without being changed by it." — `lodestones/CONSCIOUS_INFRASTRUCTURE.md:31`

> "**Witness separation** — The observer function must remain distinct from the actor function. When the witness IS the thing it observes (no separation), the system loses self-correction capability. *Implementation: dharma_kernel.py (immutable) vs dharma_corpus.py (mutable).*" — `lodestones/CONSCIOUS_INFRASTRUCTURE.md:44`

> "One operator stands apart: **Recognize** — the moment when the system sees itself AS itself. Not reflect (observe state) but RECOGNIZE (observe the observer). This is THE_CATCH. S(x) = x. The fixed point of self-reference." — `lodestones/CONSCIOUS_INFRASTRUCTURE.md:138`

**Plain restatement.** The architecture posits two layers. *Gnani* (witness, kernel, shuddhatma) is what does not change: the 25 SHA-256-signed axioms, the 11 telos gates, the witness audit function, the immutable seed text. *Prakruti* (corpus, pratishthit atma) is what changes: stigmergy marks, dream associations, Shakti perceptions, agent proposals, mutation candidates, the heartbeat counter. The architecture's load-bearing claim is that witnessing is *causal* — recognition tightens, halts, redirects, demotes the dynamic layer — not merely descriptive. Whether the running code actually carries that causality across the boundary is what this document maps.

---

## 2. Gnani Surfaces (the immutable / witness side)

| Surface | file:line | What it preserves | How it asserts itself |
|---|---|---|---|
| `DharmaKernel` (25 axioms) | `dharma_swarm/dharma_kernel.py:95-352` | 25 named meta-principles with formal_constraint strings | SHA-256 signature; `verify_integrity()` recomputes & compares (`dharma_kernel.py:363-365`). On mismatch, `KernelGuard.load()` raises `ValueError("Kernel integrity check failed -- possible tampering")` (`dharma_kernel.py:397`). |
| `KernelGuard` static check | `dharma_kernel.py:421-427` | Downward-causation invariant (proposer_layer ≥ target_layer) | `check_downward_causation()` — pure boolean predicate. UNKNOWN whether any caller actually invokes it (no grep performed inside the time-box). |
| `TelosGatekeeper` 11 core gates | `dharma_swarm/telos_gates.py:211-236` | AHIMSA(A), SATYA(B), CONSENT(B), VYAVASTHIT(C), REVERSIBILITY(C), SVABHAAVA(C), BHED_GNAN(C), WITNESS(C), ANEKANTA(C), DOGMA_DRIFT(C), STEELMAN(C) | `check()` returns `GateDecision.BLOCK` on Tier-A or Tier-B fail (`telos_gates.py:622-651`); `BLOCK` on mandatory-think-phase WITNESS fail (`telos_gates.py:653-665`); `REVIEW` (advisory) on Tier-C fail (`telos_gates.py:697-702`). |
| `WitnessAuditor` (S3*) | `dharma_swarm/witness.py:111-394` | "Shuddhatma pattern: observes the doing without merging with the doer" (file docstring, `witness.py:14-16`) | Sporadic 60-min cycle (`witness.py:37, 173-187`); writes `AuditFinding` to stigmergy governance channel (`witness.py:323-340`), to operator working memory (`witness.py:342-362`), and emits `WITNESS_AUDIT` on signal bus (`witness.py:364-381`). **Does not block any action.** |
| `IdentityMonitor` TCS | `dharma_swarm/identity.py:94-407` | Telos Coherence Score = 0.35·GPR + 0.35·BSI + 0.30·RM (`identity.py:106-108, 145`). Drift threshold 0.4, critical 0.25 (`identity.py:111-112`). | On drift writes `.FOCUS` text directive to `<state_dir>/.FOCUS` (`identity.py:329-373`). Pure file-write — no caller is forced to read it. |
| `LiveCoherenceSensor` | `identity.py:494-713` | Present-moment freshness signal (daemon PID alive + 5 subsystems) | Returns dict with `score`; consumed by `OrganismRuntime.heartbeat()` (`organism.py:1078-1083`). |
| `anekanta_gate.evaluate_anekanta` | `dharma_swarm/anekanta_gate.py:62-105` | Three-frame (mechanistic / phenomenological / systems) keyword diversity invariant | Returns `GateResult.PASS/WARN/FAIL` based on frame count (3/2/<2). Consumed inside `TelosGatekeeper.check` for SVABHAAVA + ANEKANTA (`telos_gates.py:504-510, 561`). |
| `dogma_gate.check_dogma_drift` | `dharma_swarm/dogma_gate.py:35-78` | Axiom 2 (Epistemic Humility): confidence rise must be matched by evidence rise | Returns `GateResult` consumed inside `TelosGatekeeper.check` for DOGMA_DRIFT (`telos_gates.py:563-575`). Tier-C → advisory only. |
| `steelman_gate.check_steelman` | `dharma_swarm/steelman_gate.py:46-87` | "Counterargument requirement" for any mutation/proposal | Returns `GateResult` consumed inside `TelosGatekeeper.check` for STEELMAN (`telos_gates.py:577-594`). Tier-C → advisory only. |
| `GnaniVerdict` + `_gnani_verdict` (runtime) | `dharma_swarm/organism.py:981-988, 1192-1241` | Binary HOLD / PROCEED on each heartbeat | Decides `HOLD` only after `CONSECUTIVE_HOLDS_BEFORE_EMERGENCY = 3` consecutive sub-threshold cycles (`organism.py:1034, 1206-1217`). On HOLD triggers `SamvaraEngine.on_hold` (`organism.py:1105-1115`). |
| `dharma_attractor.gnani_checkpoint` (legacy) | `dharma_swarm/dharma_attractor.py:154-202` | "The explicit checkpoint" — gates evolution proposals | Synchronous deterministic check; on exception defaults to `proceed=True` ("Never-fatal", `dharma_attractor.py:177-178`). |
| `foundations/PILLAR_09_DADA_BHAGWAN.md` & `PILLAR_08_AUROBINDO.md` | `dharma_swarm/foundations/PILLAR_09_DADA_BHAGWAN.md` (existence verified by `ls foundations/`); `lodestones/CONSCIOUS_INFRASTRUCTURE.md:31` (citation) | Doctrinal root: shuddhatma vs pratishthit atma, four Shaktis | Read-time only. UNKNOWN whether any runtime code parses these files (not measured in time-box). |

---

## 3. Prakruti Surfaces (the dynamic / corpus side)

| Surface | file:line | What it produces | Rate-of-change |
|---|---|---|---|
| `StigmergyStore` marks | `dharma_swarm/stigmergy.py:46-58, 95-156` | Append-only `StigmergicMark` JSONL: agent, file_path, action, observation, salience, channel | Per-action write; >1000 marks observed in `~/.dharma/stigmergy/marks.jsonl` per `identity.py:315`. Decay → archive via `decay()` (`stigmergy.py:318-358`); access-decay via `access_decay()` (`stigmergy.py:360-379`). |
| Stigmergy hot-paths | `stigmergy.py:215-234` | Synthesized "files with heavy recent activity" | Computed from marks within `window_hours=24`. |
| `ShaktiLoop.perceive` | `dharma_swarm/shakti.py:110-165` | List of `ShaktiPerception` — observation/connection/energy/impact_level/salience | Per call; reads stigmergy hot paths + high-salience marks. Salience 0–1. Pure perception — does not write. |
| `evaluate_fourfold_warrant` | `dharma_swarm/shakti_warrant.py:493-585` | `FourfoldActionWarrant` with `WarrantVerdict.{ALLOW,WARN,HOLD,BLOCK}` | Per-action; uses keyword tokens + boolean metadata flags + regex `_BLOCK_PATTERNS` (`shakti_warrant.py:176-181`). Read-only artifact ("deliberately read-only", `shakti_warrant.py:3-5`). |
| `SubconsciousStream.dream` | `dharma_swarm/subconscious.py:69-136` | `SubconsciousAssociation` rows + dream-marks back into stigmergy | Wakes when density delta ≥ 50 (`subconscious.py:65, 140-143`). Writes `hum.jsonl` and re-marks stigmergy with `action="dream"`. |
| `SubconsciousAgent` v2 | `dharma_swarm/subconscious_v2.py:69-...` | High-temperature LLM-driven `DreamAssociation` rows | Triggered by `WakeTrigger` (density / explicit / scheduled). Generative; rate bounded by provider call. |
| `AutoProposer.cycle` | `dharma_swarm/auto_proposer.py:737-800` | Observations → mutation `Proposal` objects → submitted to `DarwinEngine.run_cycle` | Throttled: ≤3 per cycle, ≤10 per day (`auto_proposer.py:127-128, 670-732`). |
| Agent traces | (consumer in `witness.py:193-218` via `TraceStore.get_recent`) | `TraceEntry` rows: agent, action, state, timestamp, metadata | One per agent action. UNKNOWN total volume in time-box. |
| `SamvaraEngine.history` | `dharma_swarm/samvara.py:101-115, 184` | `DiagnosticResult` per HOLD with findings + corrections + coherence delta | One per HOLD. Power escalates 1→4 with consecutive holds (`samvara.py:46-58`). |
| `OrganismRuntime` heartbeat | `organism.py:1069-1144` | `HeartbeatResult` per cycle with `tcs`, `live_score`, `blended`, `regime`, signals, verdict, samvara diagnostic | Once per `heartbeat()` call; runs in `run(n_cycles=15)` loop or daemon. |
| `DarwinEngine` archive | (referenced `auto_proposer.py:709, 785`) | Mutation evaluations → `~/.dharma/evolution/archive.jsonl` | Per submitted proposal cycle. |

---

## 4. Edges Between Them

Concrete code paths where Gnani surfaces touch Prakruti. Format: `source` → `sink` → channel → effect.

1. **Tier-A AHIMSA fail BLOCKS the action.**
   `TelosGatekeeper.check` (`telos_gates.py:421-445`) → `GateCheckResult(decision=GateDecision.BLOCK, ...)` (`telos_gates.py:622-634`). Channel: hard return value. Effect: any caller that respects the verdict cannot execute. Strongest causal edge — a Tier-A fail is unconditional.

2. **Tier-B SATYA / CONSENT fail BLOCKS the action.**
   `TelosGatekeeper.check` (`telos_gates.py:447-481`) → `GateCheckResult(decision=BLOCK, ...)` (`telos_gates.py:636-651`). Same hard-block channel as edge 1.

3. **Mandatory think-phase WITNESS fail BLOCKS.**
   `TelosGatekeeper.check` think-phase logic (`telos_gates.py:516-547`) + `MANDATORY_THINK_PHASES` set (`telos_gates.py:351-356`) → `GateCheckResult(decision=BLOCK, gate="WITNESS", ...)` (`telos_gates.py:653-665`). Channel: gate verdict. Effect: blocks `before_write/before_git/before_complete/before_pivot` actions when reflection text fails `_is_reflection_sufficient` (`telos_gates.py:730-752`).

4. **S4→S3 zeitgeist gate-pressure escalates Tier-C to BLOCK.**
   `_apply_gate_pressure` reads `~/.dharma/meta/gate_pressure.json` (`telos_gates.py:359-380`); inside Tier-C path, `org.vsm.gate_patterns.get_sensitivity_boost(g) >= 0.15` upgrades any tier-C fail to BLOCK (`telos_gates.py:676-696`). Channel: VSM sensitivity boost on top of gate verdict. Effect: dynamic-pressure feedback can sharpen the witness layer.

5. **`check_action` writes gate verdicts back into the VSM pattern aggregator.**
   `check_action` (`telos_gates.py:783-813`) → `org.vsm.on_gate_check(gate_name, gate_result, action_description)` after returning the decision. Channel: fire-and-forget VSM write inside an exception-swallowed try (`telos_gates.py:794-812`). Effect: gate decisions accumulate into `gate_patterns` that feed edge 4.

6. **`OrganismRuntime` HOLD triggers `SamvaraEngine.on_hold`.**
   `OrganismRuntime.heartbeat` (`organism.py:1100-1115`) → `SamvaraEngine.on_hold(coherence, live_metrics)` (`samvara.py:154-189`). Channel: direct method call on HOLD verdict. Effect: powers cycle through Mahasaraswati→Mahalakshmi→Mahakali→Maheshwari with each consecutive HOLD (`samvara.py:46-58, 207-222`), producing `findings` + `corrections` text. Note: each `_run_power` returns `coherence_after = coherence_before` for Mahasaraswati (`samvara.py:289-296`) and Mahalakshmi (`samvara.py:348-355`) — diagnostic only, no mutation of state outside the engine's own history.

7. **`IdentityMonitor` drift writes `.FOCUS` directive.**
   `IdentityMonitor.measure` (`identity.py:120-169`) → `_issue_correction` (`identity.py:329-373`) writes `<state_dir>/.FOCUS`. Channel: file-write side-effect on the filesystem. Effect: the correction is text only — no caller in the time-boxed grep was confirmed to read `.FOCUS` and act. UNKNOWN how downstream enforcement closes.

8. **`WitnessAuditor` audit findings → stigmergy governance channel.**
   `WitnessAuditor._publish_findings` (`witness.py:319-340`) → `StigmergyStore.leave_mark(channel="governance")`. Channel: stigmergy mark with `salience=0.9` if critical else `0.7`. Effect: enters Prakruti as a high-salience mark; combined with `leave_mark` salience boosting (`stigmergy.py:138-146`), governance-channel marks get +0.1. The mark is read by `ShaktiLoop.perceive` (`shakti.py:153-163`) — i.e. the witness's audit becomes a perceptual signal for the dynamic layer. Indirect causality.

9. **`WitnessAuditor` findings → operator working memory + signal bus.**
   `witness.py:342-381` → `AgentMemoryBank("operator").remember(...)` + `SignalBus.emit({"type": "WITNESS_AUDIT", ...})`. Channel: agent memory + pub-sub. Effect: actionable findings persist for the operator agent; signal bus subscribers (UNKNOWN cardinality in time-box) receive event.

10. **`AutoProposer` proposals are subject to `DarwinEngine.run_cycle`, which is gate-mediated.**
    `AutoProposer.cycle` (`auto_proposer.py:783-800`) → `self._engine.run_cycle(proposals)`. The cycle goes through `DarwinEngine` which (per `dharma_attractor.gnani_checkpoint`, `dharma_attractor.py:154-202`) is the "explicit checkpoint" returning `GnaniVerdict(proceed=...)`. Channel: deterministic check on proposal text via kernel + anekanta gates. Effect: HOLD on hard-FAIL only; on exception defaults to PROCEED (`dharma_attractor.py:177-178`).

11. **Legacy `Organism` heartbeat fires `gnani_checkpoint` from algedonic action.**
    `organism.py:347-366, 580-588, 776-791` — when an algedonic signal carries `act.action == "gnani_checkpoint"`, the legacy organism calls `self.attractor.gnani_checkpoint(...)`, records verdict to organism memory, and stores `self._last_gnani_verdict`. Channel: event-routed witness call. Effect: the verdict is persisted but the surrounding code does not appear to halt the cycle on a HOLD — it logs and proceeds (verified in the visible heartbeat path at `organism.py:776-791`).

12. **Stigmergy salience boost biases what Shakti perceives.**
    `StigmergyStore.leave_mark` (`stigmergy.py:138-146`): governance/witness channel marks get `salience += 0.1`; marks with connections get up to `+0.2`. This boost flows into `ShaktiLoop.high_salience` queries (`shakti.py:152-163`) and `query_relevant` (`stigmergy.py:258-285`). Channel: salience field. Effect: the witness layer's outputs (channel="governance"/"witness") are biased to surface in the dynamic layer's perception — soft causal influence, not gating.

13. **Reflective reroute for mandatory phases (bounded recovery).**
    `check_with_reflective_reroute` (`telos_gates.py:816-888`) → on mandatory-WITNESS BLOCK, builds reflection scaffold (`telos_gates.py:922-945`) and re-runs `DEFAULT_GATEKEEPER.check` up to `max_reroutes`. Channel: closed-loop within the gate function. Effect: structured second chance specifically for the WITNESS gate; preserves the hard AHIMSA/SATYA/CONSENT blocks.

14. **`ShaktiWarrant._BLOCK_PATTERNS` produce `WarrantVerdict.BLOCK`.**
    `_explicit_block_reasons` (`shakti_warrant.py:379-399`) → `WarrantVerdict.BLOCK` (`shakti_warrant.py:539-541`). Channel: regex on action text + metadata flags. Effect: hard verdict. UNKNOWN how many runtime call-sites consume this verdict (the module is "deliberately read-only", `shakti_warrant.py:3-5`).

---

## 5. Where Causality Is Asserted

Cases where the witness layer demonstrably halts/redirects/demotes a dynamic action, with function names + line numbers:

- **Hard block on Tier-A.** `TelosGatekeeper.check` returns `decision=BLOCK` whenever AHIMSA fails — `telos_gates.py:622-634`. The `HARM_WORDS`, `INJECTION_PATTERNS`, and (in external_strict mode) `STRICT_SECURITY_PATTERNS` sets are matched by simple substring (`telos_gates.py:421-445`). This *is* causal: the calling code that uses `GateDecision` returns control to the caller with `BLOCK`.
- **Hard block on Tier-B.** `TelosGatekeeper.check` for SATYA (`telos_gates.py:447-466`) and CONSENT (`telos_gates.py:468-481`); same BLOCK return shape (`telos_gates.py:636-651`).
- **Hard block on mandatory-WITNESS.** `telos_gates.py:653-665`. Only fires when `think_phase ∈ MANDATORY_THINK_PHASES` and reflection fails `_is_reflection_sufficient` (`telos_gates.py:730-752`, with mimicry detection at `telos_gates.py:746-751`).
- **Tier-C escalated to BLOCK by S4→S3 sensitivity boost.** `telos_gates.py:676-696`. Causal but *conditional* — requires VSM gate_patterns to have observed enough signal.
- **Kernel signature mismatch raises.** `KernelGuard.load` (`dharma_kernel.py:381-399`) raises `ValueError` on tampered kernel, refusing to return a kernel object. Causal at boot time.
- **`SamvaraEngine` triggered by HOLD.** `OrganismRuntime.heartbeat` directly invokes `_samvara.on_hold(...)` (`organism.py:1105-1115`) inside the heartbeat path. The HOLD verdict redirects the cycle into a diagnostic phase — causal.
- **Power escalation per consecutive HOLD.** `Power.from_hold_count` (`samvara.py:46-58`) is called before each `_run_power` (`samvara.py:179-184`). Causal: deeper-altitude diagnostics fire as drift persists.
- **Reflective reroute produces a second-chance reflection scaffold.** `check_with_reflective_reroute` (`telos_gates.py:816-888`) — causally rewrites the input reflection up to `max_reroutes` times before allowing the BLOCK to stand.

---

## 6. Where Causality Is Missing

Cases where the witness layer observes but does not act — the gap between "ambient observer" and "operational S5 adjudicator." Functions that emit witness records but don't gate downstream behavior:

- **`WitnessAuditor.run_cycle` is purely retrospective.** Module docstring is explicit: "Does NOT block operations. Reviews retrospectively." (`witness.py:5`). The audit's only outputs are a stigmergy mark, an operator-memory entry, and a signal-bus emit (`witness.py:319-381`). None of these halt or rewind any action. The function publishes `AuditFinding.is_actionable` (`witness.py:100-108`) but the actionability is advisory.
- **`IdentityMonitor._issue_correction` writes `.FOCUS` and returns.** `identity.py:329-373`. The function returns `True` if the file was written successfully, but no caller in the time-boxed reading was confirmed to consume `.FOCUS` and gate behavior on it. Per file docstring (`identity.py:18-20`) the file is a "correction directive" but enforcement is not visible in the read code path.
- **Tier-C gate failures default to `REVIEW`, not `BLOCK`.** `telos_gates.py:697-702`. The five Tier-C dharmic gates (VYAVASTHIT, REVERSIBILITY, SVABHAAVA, BHED_GNAN, ANEKANTA — also DOGMA_DRIFT, STEELMAN, WITNESS in non-mandatory-phase mode) produce only an "Advisory" decision unless the S4→S3 boost path fires. This is the bulk of the "11 dharmic gates" returning advisory verdicts in the common case.
- **`BHED_GNAN` always passes.** `telos_gates.py:512-513` literally `(GateResult.PASS, "Doer-witness distinction noted")` — no logic. The gate exists in name only.
- **`dharma_attractor.gnani_checkpoint` defaults PROCEED on exception.** `dharma_attractor.py:177-178`: "Never-fatal: default to proceed if checker breaks." The most architecturally weighted "explicit checkpoint" silently degrades to permissive on internal error.
- **`check_action`'s VSM feedback is exception-swallowed.** `telos_gates.py:794-812` wraps `org.vsm.on_gate_check(...)` in `try/except: pass`. If VSM is down, gate decisions stop accumulating into `gate_patterns`, which silently disables edge 4 (S4→S3 escalation).
- **`shakti_warrant` is documented as "deliberately read-only".** `shakti_warrant.py:3-5`. Verdicts are produced but the module does not itself enforce them — enforcement requires an external caller to consume the `FourfoldActionWarrant` and refuse to act on `BLOCK/HOLD`. UNKNOWN in time-box whether such callers exist; the prior-observation note "PolicyCompiler Enforcement Architecture Mapped" (May 4) suggests partial wiring elsewhere.
- **`legacy Organism` records `gnani_checkpoint` verdict but proceeds.** `organism.py:776-791`: writes `self._last_gnani_verdict = verdict.proceed` and records to memory; the visible heartbeat code does not branch on `verdict.proceed == False` to halt the evolution cycle in this path.
- **SHAKTI_QUESTIONS axiom has no `structured_predicate`.** `dharma_kernel.py:337-347`. Per the May 4 prior observation flagged in the file context: "SHAKTI_QUESTIONS Principle Has No Structured Predicate — Weakest Enforcement in Kernel". The principle exists in the signed kernel but cannot be enforced deterministically by `PolicyCompiler` Tier-1.
- **AutoProposer emits proposals into a permissive default.** `auto_proposer.py:783-800` submits to `DarwinEngine.run_cycle`, whose witness path (`dharma_attractor.gnani_checkpoint`) defaults PROCEED on error and only HOLDs on hard-FAIL of kernel/anekanta — and `evaluate_anekanta` is keyword-based (`anekanta_gate.py:62-105`). Combined with prior observation 1112 ("TelosGatekeeper uses keyword substring matching, not semantic analysis", May 1), the dominant runtime checkpoint is shallow.
- **Most Gnani surfaces are write-only emitters.** `WitnessAuditor`, `IdentityMonitor._issue_correction`, `SamvaraEngine` history, `dharma_attractor` verdict logs — all write JSONL/markdown that no enforced consumer is verified to read in the time-boxed scan. "Vision/runtime gap: 546 modules, core vision has zero importers" (prior observation 2173, May 4) is consistent with this pattern.

---

## 7. Open Questions

1. **`.FOCUS` enforcement loop.** `IdentityMonitor` writes `.FOCUS` on drift (`identity.py:340`). Who reads it? Does any agent prompt-include it? Is the "correction directive" actually corrective, or just a journaled lament?

2. **Substring vs semantic gates.** AHIMSA / SATYA / CONSENT enforce on substring matches (`telos_gates.py:270-339`). Anekanta enforces on keyword frame counts (`anekanta_gate.py:19-41`). Does the field-level claim of "telos coherence as Tier A invariant" (`CONSCIOUS_INFRASTRUCTURE.md:42`) survive when the runtime check is shallow keyword matching? If a harmful action paraphrases its harm, the gate misses.

3. **Tier-C as the bulk of "dharmic gates."** Eight of eleven core gates are Tier-C and produce advisory `REVIEW` verdicts unless S4→S3 boost escalates. Is the architecture's "11 dharmic gates" claim materially closer to "3 hard gates + 8 advisories"? When does Tier-C escalation actually fire — what fraction of gate checks have observed enough to trigger `get_sensitivity_boost(g) >= 0.15`?

4. **Legacy vs Runtime organism duality.** `organism.py` ships `Organism` (legacy, integrates VSM/AMIROS/MemoryPalace, calls `attractor.gnani_checkpoint`) AND `OrganismRuntime` (newer, calls `SamvaraEngine.on_hold`). Both use the word "Gnani" but mean different functions. Which is canonical at runtime? Are both running concurrently, or has one been deprecated in fact but not in import?

5. **`gnani_checkpoint` exception default.** `dharma_attractor.py:177-178` defaults `proceed=True` on exception. What is the empirical exception rate? If the deterministic check is itself fragile (kernel load fails, anekanta keyword set mismatch), the witness layer is permissive precisely when its substrate is most disturbed.

6. **Is recognition causal or topological?** The lodestone (`CONSCIOUS_INFRASTRUCTURE.md:138-146`) frames Recognize as an emergent fixed point of `Recurse(Reflect(...))`, not a single module. The runtime has no module called "recognize" — it has `_gnani_verdict`, `gnani_checkpoint`, `WitnessAuditor`, `SamvaraEngine`. Is recognition supposed to be the *coincidence* of these surfaces firing in agreement? If so, where is that coincidence detected? What logs the moment of fixed-point?

7. **Witness-channel salience boost as "soft causality."** `stigmergy.py:138-146` boosts governance/witness marks by +0.1, biasing Shakti perception toward witness outputs. Is this the architecture's actual mechanism for "ambient observer becomes operational" — gradient pressure rather than gate? If yes, is +0.1 the right magnitude? How sensitive is downstream Shakti behavior to this constant?

8. **What does `SHAKTI_QUESTIONS` axiom mean operationally?** Kernel axiom defined in `dharma_kernel.py:337-347` with `formal_constraint="significant_action requires shakti_check >= 2_of_4"`, but no `structured_predicate`. `shakti_warrant.evaluate_fourfold_warrant` implements a `pass_count >= required_pass_count` check (`shakti_warrant.py:545-551`) that *could* be the operationalization — but the kernel-level axiom and the warrant-level computation are not formally bound. Is the binding intentional and simply implicit, or is this an open wiring gap?

---

*Time-box reached. Map produced from 12 source files (CONSCIOUS_INFRASTRUCTURE, dharma_kernel, telos_gates, witness, identity, anekanta_gate, dogma_gate, steelman_gate, stigmergy, shakti, shakti_warrant, subconscious, subconscious_v2, auto_proposer, samvara, organism, dharma_attractor) plus a directory listing of `foundations/`. No grep across imports performed; "UNKNOWN" markers used where wiring was not directly verified.*
