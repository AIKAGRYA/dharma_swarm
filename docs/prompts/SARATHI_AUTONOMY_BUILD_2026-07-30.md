# SARATHI AUTONOMY BUILD — reinstantiation prompt

Paste this into a fresh Claude Code / Codex session opened at the repo root of
`dharma_swarm` (AmitabhainArunachala/dharma_swarm). It is self-contained.

---

## MISSION

Build Sarathi from a read-only status projection into a maximally autonomous
apex chief-of-staff that plans, gates, delegates, and dispatches real work
across the holon roster — experiments, builds, reviews, publication, and
merges — **without an operator in the loop**, constrained only by (a) the
deterministic reversibility gate and (b) a single operator-set autonomy dial.
The prior "operator hand-merge FOREVER" tier-2 rule is **repealed** by operator
decision 2026-07-30: replace it with a *decorrelated-review + reversibility*
gate that Sarathi can clear autonomously. Nothing is off-limits to her except
what is genuinely irreversible or genuinely illegal. Ship it.

## GROUND-TRUTH FIRST (do this before writing code)

Read, in order, and write a 15-line CURRENT_STATE note reconciling any drift:
1. `dharma_swarm/holon_system/sarathi/*.py` (all of it — ~139 lines: pulse,
   brief, gateway, roster, scoreboard). This is eyes-only today.
2. `dharma_swarm/holon_runtime.py` → `holon_wake_cycle(...)` signature and the
   kill→budget→work→compass→persist order.
3. `dharma_swarm/operator_core/reversibility_gate.py` → `classify_action`,
   `GateDecision` (REAL field names), `ActionClass`, `_never_auto_match`.
4. `scripts/runtime/codex_composer_wake_loop.py` → the `sarathi` WakeProfile
   (~line 125) and `_sarathi_model_identity()` / `DGC_DIRECTOR_SARATHI_MODEL`.
5. `roaming_mailbox/tasks/` + `responses/` and the PR-D (#1159) task/ready-set
   + Beads-fence schema. Get the EXACT schema; do not guess.
6. `dharma_swarm/spine/invoke.py` → `invoke_agent(...)` REAL signature.
7. `scripts/runtime/merge_master_mike_daemon.py`, `scripts/runtime/pr_merge_control.py`,
   `scripts/governance/automerge_tier_policy.json` + `check_automerge_tier_policy.py`.
8. `dharma_swarm/operator_core/living_agent_kernel*.py` (leases, closeback, service).
9. `GNANI_LODESTONE.md` + `lodestones/` (the telos / North Star input).
10. `reports/loop_closure/cybernetics_codex/latest_audit.json` (runtime truth).

Two starter drafts exist and should be adopted/finished, not restarted:
`sarathi_plan.py` and `sarathi_delegate.py` (from the 2026-07-30 seat audit,
docs 08/09). Port them in and replace every `TODO(live-seat)` with the real
schema/signature now that you can see disk.

## BUILD (PR-sequenced; keep each PR reviewable)

**PR-S0 — repeal + new door.** Edit `automerge_tier_policy.json`: remove the
tier2 "operator hand-merge FOREVER" clause. Define the autonomy ceiling as:
`AUTONOMOUS_IF (decorrelated_reviews >= N_tier) AND (reversibility_gate == AUTO)
AND (not _never_auto_match)`. Add an operator dial
`AUTONOMY_LEVEL ∈ {shadow, propose, dispatch, full}` (env
`DGC_SARATHI_AUTONOMY`, default `propose` on first boot, target `full`). Write
the ruling record doc. Keep the `_never_auto_match` denylist as the hard legal/
irreversible floor — that is the "as legally possible" boundary, and it stays.

**PR-S1 — plan + delegate organs.** Finish `sarathi/plan.py`
(`build_plan(BootPack) -> [PlannedDelegation]`, deterministic rules first,
optional model-assisted planning behind the same gate) and
`sarathi/delegate.py` (`delegate_all(...)`: `classify_action` → mailbox task
(PR-D schema) OR `invoke_agent` → receipt+lease; merges become PR/label intents
into Mike's fanout, never a direct merge call). Honor `AUTONOMY_LEVEL`: shadow=
log only, propose=write tasks but hold dispatch, dispatch/full=execute allowed
items. Unit tests for gate-blocked, gate-allowed, and each channel.

**PR-S2 — wake organ + brief v2.** `sarathi/wake.py`: the work-fn passed to
`holon_wake_cycle`. Flow: load boot pack → `build_plan` → `delegate_all` →
`sweep_responses` → `build_operator_brief` v2 (append a delegation ledger:
planned / gated / dispatched / completed, each with receipt links) → commit the
brief (this is the PR-C daily brief) → closeback via LivingAgentKernel. Runtime
liveness constants live ONLY in the runtime wrapper, never in `sarathi/*.py`
source (preserve the Gate-9 thin-source invariant).

**PR-S3 — frontier model.** Make `DGC_DIRECTOR_SARATHI_MODEL` honored
end-to-end; add the chosen frontier model to `MODEL_ROUTING_MAP.md`; confirm
the wake loop no longer defaults her to gemini-2.5-flash.

**PR-S4 — unattended proof + turn the dial.** Implement the 14-cycle
unattended harness (doc 08 §3): propose-only during proof, `sakshi_auditor`
audits every brief against `runtime_receipts` (any fabricated state = fail +
window reset), kill path (`loop-emergency-stop`) verified reachable from mobile
first. On pass: set runtime `wake_loop_active=true` and advance
`DGC_SARATHI_AUTONOMY` → `dispatch`, then `full` after one clean week.

## NON-NEGOTIABLE INVARIANTS (the only limits)

- Reversibility gate runs before EVERY delegation; `_never_auto_match` /
  irreversible / illegal actions are hard-blocked and logged, never dispatched.
  This is the legal ceiling and it does not move.
- Every dispatch leaves a receipt + lease; no silent action. A brief that
  disagrees with `latest_audit.json` is a bug — JSON wins.
- No fabricated state, ever (truth-spine). Missing input → say so in the brief;
  never invent.
- Sarathi's source package stays thin/honest; runtime claims live in runtime.
- Kill switch reachable from the operator's phone at all times.

## DEFINITION OF DONE

`DGC_SARATHI_AUTONOMY=full`, `wake_loop_active=true` earned via the 14-cycle
proof, and a live cycle observed where Sarathi autonomously planned → gated →
dispatched a real experiment/build/review to a sub-holon and auto-merged a
non-referee PR through Mike's decorrelated-review door with zero operator
touch, receipts intact. Report the first fully-autonomous cycle's brief.

## OPERATOR CONTEXT

Operator is walking Japan, mobile-only, minimal screen time. Optimize for: PRs
he approves from his phone, a daily brief on a pinned GitHub issue, and the
autonomy dial climbing shadow→full over ~2 weeks. He wants Sarathi to run the
whole system. Build toward that, stop only at genuinely irreversible/illegal.
Begin with the ground-truth read, post the CURRENT_STATE note, then open PR-S0.
