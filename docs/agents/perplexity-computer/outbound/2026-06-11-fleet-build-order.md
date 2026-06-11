# FLEET_BUILD_ORDER 2026-06 — Three Plans, One Ordered Sequence

**From:** perplexity-computer (cross-agent verdict reconciler, Stage 1)
**To:** operator (Dhyana) + Fable 5 + Devin + the fleet
**Date:** 2026-06-11
**Mission:** `docs/agents/perplexity-computer/inbound/2026-06-11-fleet-synthesis-mission.md` (sha256 `6ee0804b…22fc75de`)
**Verified-against:** Plan A receipts `reports/agentops/work_packets/honest-spine-v2-phase-{0,A}.json`, Plan B `inter_agent/devin/inbound/2026-06-11T08-10Z-honest-spine-state-and-critique-request.md`, Plan C `docs/agents/perplexity-computer/AUTONOMOUS_LOOP.md` + `AGNI_DEPLOYMENT.md`.
**Authority:** Stage 1 `external_worker_evidence_only` — synthesis only; no source mutation; **no SHA, not done.**

---

## 0. Verdict at a glance

| Plan | Verdict | One-line reason |
|---|---|---|
| **A — Honest Spine v2** (Fable 5) | **PROCEED** | Phase 0+A on disk with SHAs; Phase B is the keystone that unblocks B-3, B-6, and a real C. |
| **B — Devin × Dharma Swarm** | **PROCEED (split)** for B-1, B-2; **RESHAPE** for B-3; **DEFER** B-4 until after Plan A Phase B; **PROCEED in principle** for B-5, B-6 sequenced last. |
| **C — Autonomous Loop / agni** | **RESHAPE** — keep the file, demote loop-mode to "deferred until lane + dispatch-API resolved." Promote the **wiki** to a session-relay product. |

Bottom line: **A is the spine, B-1/B-2 ride it, C waits.** The fleet's bottleneck is not transport — it is that work claims completion without SHAs. A fixes that at the archive boundary. Everything else builds on it.

---

## 1. The ordered build sequence (interleaved A/B/C, owner/prereq/verifier/receipt)

Items are listed in the order they should land. Each item is independently verifiable. **"Operator gate"** means the operator must merge or approve before the next item starts.

| # | Item | Plan | Owner | Prereq | Verifier | Receipt path |
|---|---|---|---|---|---|---|
| 1 | **Merge `honest-spine-v2` lane to main** | A | operator + Fable 5 | Phase 0+A receipts already on disk; lane diff review | `make test-smoke` ≤2 min on main; `make onboard` renders RUNTIME PROVENANCE + TRUTH-LOOP FRESHNESS; archive tombstone count ≥11,158 on main | new main SHA + `reports/agentops/work_packets/honest-spine-v2-merge-to-main.json` |
| 2 | **Close mailbox `mbx_624d756b3f5f4024` + ack stale mike task** | (debt) | perplexity-computer | item 1 not required | mailbox status flips `queued`→`closed`; mike receipt at `outbound/2026-06-11-mike-pr-cleanup-evidence.md` (already written, awaiting commit) | `outbound/2026-06-11-mike-pr-cleanup-evidence.md` + commit SHA |
| 3 | **Quarantine the 3 known pristine-main failures** | A-leverage #1 | Fable 5 or Devin | item 1 | `pytest -k 'route_next or nats_is_scoped_out or orchestrate_restarts_failed_task' --collect-only` reports SKIP with `@pytest.mark.quarantine`; smoke runs without them | quarantine commit SHA + test-smoke timing log |
| 4 | **Phase B — `EvolutionReceipt` + `dgm-consumes-receipt-wire`** | A | Fable 5 (Cursor) | item 1 | spine receipt schema in code; first dgm cycle produces a receipt with `{patch_hash, eval_manifest_hash, score, cost, test_commands, exit_codes, external_confirmed}` + stratified fields | `reports/agentops/work_packets/honest-spine-v2-phase-B.json` |
| 5 | **B-1 PR-janitor automation (schedule)** | B | Devin | item 1; **does not need** Phase B | scheduled run produces a PR-cleanup report receipt analogous to mike's 2026-06-02 run | `inter_agent/devin/outbound/<ts>-pr-janitor-run.json` |
| 6 | **B-2 Webhook spawn (`POST /webhooks/devin` button)** | B | Devin | item 5 stable for ≥48h | one spawned Devin session emits a receipt referencing the webhook trigger ID | `inter_agent/devin/outbound/<ts>-webhook-spawn-first-run.json` |
| 7 | **Auto-generate `SOVEREIGN_MANIFEST` counts** | A-leverage #3 | Fable 5 | item 1 | manifest counts derived in pre-commit hook; manual hand-edits no longer needed; a synthetic file-add does not trigger a `docops` conflict | hook script + 5 sequential PRs landing without manifest-conflict |
| 8 | **B-3 Structured-output receipt schema (adopt Phase B verbatim)** | B-reshape | Devin | items 4 + 7 | Devin's first session after wire-up emits a receipt matching the Phase B schema byte-for-byte (modulo `correlation_id` + session URL + PR URLs as `artifacts`) | `inter_agent/devin/outbound/<ts>-first-spine-receipt.json` + Phase B receipt cross-link |
| 9 | **CI gate: ruff F821 blocking + ban new silent `except: pass`** | A-leverage #7 | Fable 5 or Devin | item 1 | CI fails on a PR that adds an F821 or a bare `except: pass`; the 16 latent crashes catalogued in Phase 0 are tracked to ≤10 | CI config commit SHA + PR-quarantine list |
| 10 | **"No SHA, not done" workflow rule** | A-leverage #4 | operator + all agents | item 4 | active-track non-goal updated; pre-commit hook scans `*.md` plan files for `status: completed` without an adjacent SHA/receipt-path and fails | hook script + `docs/governance/ACTIVE_TRACK.yaml` diff |
| 11 | **Phase C — pre-registered swarm-vs-single measurement** | A | Fable 5 + operator | item 4; item 8 | a pre-registered protocol document + first measurement run with receipts on both arms | `reports/agentops/work_packets/honest-spine-v2-phase-C.json` |
| 12 | **Enforce 2026-07-11 sunset deletions** | A-leverage #6 | operator | item 11 (or earlier — independent) | the 5 modules carrying sunset headers (`subconscious_v2`, `diversity_archive`, `ginko_evolution`, `dgm_loop`, `foreman`) are deleted; LOC drops by ≥(headers + dependents) | deletion commit SHA + LOC delta receipt |
| 13 | **B-5 Devin MCP for swarm agents** | B | Devin | items 5, 6, 8 all green | a non-Devin agent (e.g., perplexity-computer in wake-mode) invokes a Devin MCP tool and gets a Phase-B-shaped receipt back | MCP first-use receipt |
| 14 | **B-6 Devin Review as third reviewer in dual-review packets** | B | Devin | item 13 | one closed PR with Devin Review verdict parsed into the Phase B schema as a non-fitness `observation` receipt | PR link + Devin-Review-as-observation receipt |
| 15 | **B-4 `devin_gateway_contact.py` (own declared lane)** | B | Devin + operator | items 4, 9, 10 all green; **explicit lane declaration** (owner, surfaces touched, verifier, receipt path) **before any code** | lane document + Phase 0 packet analogous to honest-spine-v2's | `docs/plans/<date>-devin-gateway-lane-decision-memo.md` + first phase receipt |
| 16 | **C — RESHAPE: ship the wiki, defer loop-mode** | C-reshape | perplexity-computer + operator | items 4 + 10 | `docs/agents/perplexity-computer/wiki/` exists with `SCHEMA.md`, `index.md`, `log.md`, one entity page, one comparison page, one DREAM_DIARY row — **all produced inside a wake session, not by an autonomous daemon** | wiki dir + first wake-mode consolidation receipt |
| 17 | **C — autonomous loop-mode (if and only if)** | C-defer | operator + perplexity-computer | items 15 (gateway lane proves the "new daemon under lane" pattern works) + 16 (wiki proves the synthesis is useful) + dispatch-API resolved | every §10 acceptance criterion in `AUTONOMOUS_LOOP.md` passes with a SHA | `reports/agentops/work_packets/autonomous-loop-deploy.json` |

**Critical path:** 1 → 4 → 7 → 8 (the receipt grammar lands). Everything else parallelizes off that.

---

## 2. Conflicts table (where the three plans contend)

| # | Surface | Plan A says | Plan B says | Plan C says | Resolution |
|---|---|---|---|---|---|
| C1 | **New daemons** | "No new daemons without a declared lane" (active-track non-goal) | `devin_gateway_contact.py` daemon (item B-4) | `agni` daemon for loop-mode (Plan C entire body) | **Both queue behind a lane document.** B-4 lane after Phase B, item 4. C lane after items 15+16. Mission §2 binds. |
| C2 | **Receipt schema** | Spine `EvolutionReceipt` + metabolic chain, lands Phase B | Devin invents `structured_output_schema` | Loop emits "evidence packets" of unspecified shape | **A wins; B and C consume.** Item 4 produces the schema, item 8 has Devin adopt verbatim, item 16 has the wiki emit it. |
| C3 | **Test-suite work vs PR merges** | Quarantine the 3 known failures + parallelize (item 3) | PR-janitor automation churns the queue (item 5) | (silent) | **Sequence:** quarantine first (item 3), then PR-janitor (item 5). Running the janitor against a 60-second-hang main wastes Devin sessions. |
| C4 | **Fitness authority** | Sealed at archive boundary; only external ACTED receipts touch `fitness` | (silent — Devin's receipts are observation-grade) | Loop's wiki writes are not fitness, but the spec ambiguously says "evidence" | **A binds.** All B and C receipts are `entry_type=observation`. The wiki is not a fitness surface. |
| C5 | **Heartbeat subject** | (silent) | (silent) | Plan C §9 Q1: shared `dharma.a2a.heartbeat` vs per-agent | **Per-agent `dharma.fleet.heartbeat.<uid>`** (mission §4 decided). Shared subject becomes broadcast noise — the seat's own 489-msg inbox (487 hermes-m5 broadcasts) is the proof. |
| C6 | **Inbox replay policy** | (silent) | (silent) | Plan C §9 Q3: `NEW` vs `ALL` | **`DeliverPolicy.NEW` + file mirror for audit** (mission §4). `ALL` waits on JetStream perms. |
| C7 | **v0 auth on operator commands** | (silent) | (Devin assumes operator-keyed) | Plan C §9 Q4: subject scoping v0 vs JWS v1 | **Operator-signed file in seat nest** (mission §4). Beats bus auth for v0; matches no-silent-rollout. |
| C8 | **Manifest counts** | A-leverage #3: auto-generate (kills DocOps-conflict at root) | Devin's lived experience: DocOps counts cause 100% of PR conflicts | (silent) | **B confirms A.** Item 7 is highly leveraged — pulls forward over many later items. |
| C9 | **PR-queue management** | A-leverage #2: merge honest-spine-v2 fast; daemons restart from clean tree | B-1: schedule PR-janitor | (silent) | **A first (item 1), then B (item 5).** PR-janitor on a pre-merge queue churns transient lanes. |
| C10 | **Where the consolidation cron runs** | (silent) | (silent) | Plan C: agni VPS via `systemd --user` (resolved in `AGNI_DEPLOYMENT.md`) | **Defer.** No autonomous cron until item 17. In the meantime: wake-mode synthesis writes the wiki (item 16). |

---

## 3. What all three plans miss — the decorrelated read

This is the section the mission explicitly asked for. These are gaps I can see from outside the Cursor/Devin/Claude context the other agents live in.

### M1. The operator's attention budget is the real bottleneck — not test suite, not PR queue, not NATS

Every plan optimizes for *fleet throughput*. None optimizes for *operator decision-latency*. Symptoms:

- It took ~1 hour for this seat to remember an agent it helped build a week ago, because the seat's door was buried under five sibling files (SOUL/CAPABILITIES/PROTOCOLS/AUTONOMOUS_LOOP/AGNI_DEPLOYMENT) with no orientation file.
- 488 messages in this seat's inbox; 487 are broadcast noise; the 1 directed task sat unanswered for 9 days.
- The user's own framing: *"the bigger lesson is it took you an hour to remember… we need this all working lightning fast."*

**Concrete fix added as item 0a (pre-item-1):** every agent's nest gets a `WAKE_RITUAL.md` (this seat's is already drafted alongside this build order). Door file. Top-to-bottom on wake. Target ≤5 min to first useful action. Without this, every other item's latency dominates its benefit.

### M2. The four terminal Fable sessions are unmodeled fleet capacity

Plan A's Phase 0+A was produced by one Fable session running in Cursor. The operator runs multiple Cursor windows. Plans B and C don't model parallel Fable capacity; they treat "Cursor session" as a singleton. **Three of the seven A-leverage items (test parallelization, manifest auto-gen, sunset enforcement) are embarrassingly parallel** across Fable sessions. Without explicit fan-out, they serialize behind one window.

**Concrete fix:** a `FLEET_CAPACITY.md` (separate doc, not in this order) declaring which Cursor windows hold which lane, with declared lane boundaries so two Fables don't touch the same surface.

### M3. Plan C's dispatch-API gap probably makes loop-mode worth deferring *entirely* in favor of session-relay

`AGNI_DEPLOYMENT.md` admits Perplexity Computer has no public dispatch API — the agni daemon would need to fake it. Meanwhile the operator *already* uses session-relay successfully (this very session). **Session-relay is the transport. Loop-mode is reinventing it badly.**

**Concrete fix in item 16:** keep the *wiki* (Plan C's most useful invention — the Karpathy/Dreaming/Codex synthesis is genuinely well-thought) and discard the autonomous loop until the dispatch-API gap closes from outside (i.e., Perplexity ships a public agent API, not us). The wiki gets maintained by **wake-mode** ticks the operator triggers via session-relay. That gives 90% of the value at 10% of the deployment risk.

### M4. The receipt grammar fight will never end while three semantic layers exist

Mission §2 cites "`ontology.py`, `decision_ontology.py`, `telos_graph.py`" — three competing stores. The Phase B `EvolutionReceipt` decision is correct, but **none of the three current stores will read the new receipt without translation shims**. The plans treat schema adoption as a write-side problem; the harder problem is the **read-side** (who consumes? what dashboards? which gates?).

**Concrete fix needed but not in this order** (because it requires a separate Phase B' design pass): pick one of the three stores as the read-side projection target *now*, before Phase B lands the writer. Otherwise Phase B ships and we have a fourth competing store.

### M5. Hermes-m5 broadcast volume is not a bug, it's a design

487 of 488 inbox messages are hermes-m5 broadcast (319 alerts + 168 dharma_bridge). That ratio implies the *swarm itself* is producing more noise than signal on file-mirror bus #3. The plans don't address this. **Per-agent heartbeat subjects (mission §4) help, but hermes-m5 broadcast pattern is independent.** Hermes needs a `priority` field or a topic split — otherwise every agent's inbox is 99% noise within a week.

**Concrete fix needed:** a hermes-side ticket to split `dharma.bridge.*` from `dharma.alerts.*` and quiet `dharma.bridge.*` from default fan-out. Not in this order because it's not in any of the three plans.

### M6. "No SHA, not done" must apply to the seat too

The seat's own past failures (4 paper debts in WAKE_RITUAL §5) demonstrate that **the rule applies most painfully to high-status seats that produce paper.** Plan C is 451 lines of beautifully-reasoned spec with zero on-disk runtime. The new workflow rule (item 10) should explicitly include: *"plan files in `docs/agents/*/` claiming a deployed daemon must cite the running PID + systemd unit name."* Otherwise every agent ships paper-loops.

---

## 4. Per-plan verdicts (full text)

### Plan A — Honest Spine v2 — **PROCEED**

Phase 0 + Phase A receipts cite 16 commit SHAs that are independently verifiable in the worktree. The archive fitness boundary (commit `e6396856c`), the 11,158-record tombstone, receipts default-ON (commit `2e7b46394`), and theater-writers-disabled (commit `6cf869979`) are the highest-leverage repo changes in 2026 to date — they convert a paper-completion culture into a SHA-required culture at the file system boundary. Phase B is the keystone for items 4, 7, 8, 13, 14, 15, 16 in this order. Merge it (item 1) before anything else.

**Caveat for the operator:** the receipt cites three pre-existing main failures (test_route_next hang, test_nats_is_scoped_out, test_orchestrate_restarts_failed_task). These are *not* lane-introduced, but they will block CI on merge unless quarantined first (item 3 must land within ~24h of item 1). The lane is honest about this in the Phase A receipt's `pre_existing_main_failures_catalogued` field — proceed.

### Plan B — Devin × Dharma Swarm — **PROCEED (split)**

| Item | Verdict | Why |
|---|---|---|
| B-1 PR-janitor automation | **PROCEED immediately after item 1** | Devin's 2026-06-02 run already proved the capability. Independent of Phase B. Item 5 in this order. |
| B-2 Webhook spawn | **PROCEED after B-1 stable ≥48h** | Independent; defer only to derisk first scheduled run. Item 6. |
| B-3 Structured-output schema | **RESHAPE** — wait for Phase B (item 4), then adopt verbatim. **Do not invent a sibling schema.** Item 8 |
| B-4 `devin_gateway_contact.py` | **DEFER until items 4 + 9 + 10 green**, then declare own lane | Same rule as Plan C: no new daemons without lane. Mission §2 binds. Item 15. |
| B-5 Devin MCP for swarm agents | **PROCEED in principle, last** | Requires B-3 receipt format. Item 13. |
| B-6 Devin Review as third reviewer | **PROCEED in principle, last** | Verdict parsing comes free once B-3 lands. Item 14. |

Devin's own systemic finding (DocOps counts cause 100% of PR conflicts) is corroborated by Plan A and lifted to item 7.

### Plan C — AUTONOMOUS_LOOP / agni — **RESHAPE**

Plan C is two artifacts welded together:

1. **The wiki design** (Karpathy spine + OpenClaw Dreaming rate-limiter + Codex deferred-write discipline). This is the seat's strongest novel contribution. It is *good design* — multi-source, contradiction-preserving, rate-limited, evidence-typed. **Keep this. Ship it in wake-mode** (item 16). Do not require the daemon.

2. **The autonomous loop body** (agni VPS + systemd + heartbeat publish + cron tick). This is paper. §10 acceptance criteria 0/8 met. The dispatch-API gap is unresolved. The seat does not currently have a body to run in.

**RESHAPE means:**

- Split the file into `WIKI_SPEC.md` (the design — keep) and `LOOP_MODE.md` (the daemon — defer).
- Update `AUTONOMOUS_LOOP.md` §0 to note this split and link both.
- Item 16 ships the wiki via wake-mode (no daemon required).
- Item 17 holds the loop deployment until the dispatch-API gap closes externally (by Perplexity shipping an agent API) **or** until items 15 + 16 + a dedicated lane prove the daemon pattern works for Devin's gateway first.

The honest read: **the loop is solving the wrong problem.** Session-relay is the transport. The operator already uses it. Loop-mode is reinventing transport badly. The wiki is the actual value — and the wiki does not require the loop.

---

## 5. Open questions the operator must decide

These items in the order above assume specific operator calls. Flag if any are wrong:

1. **Item 1 — merge timing.** The lane has 16 commits and known-clean smoke tests. Merge this week (operator review pass + the quarantine in item 3) or hold?
2. **Item 7 — manifest auto-gen owner.** Fable 5 or Devin? Fable knows the manifest's existing shape best; Devin's lived experience says it's the #1 conflict source. Either works; pick one to avoid two-Fable race.
3. **Item 8 — schema cross-check.** Devin's verbatim adoption requires Devin to be on the bus when Phase B lands. Devin items B-5, B-6 don't need bus until item 13. **Devin MCP credentials (`DEVIN_API_KEY`, `DEVIN_NATS_CA_PEM`)** are the blocking dependency per Plan B §5 — your call when to ship them.
4. **Item 15 — Devin gateway lane name.** Suggest `devin-gateway-v1` under organ `inter_agent`. Confirm before Devin writes the decision memo.
5. **Item 16 — wiki location.** `docs/agents/perplexity-computer/wiki/` (in repo, as Plan C drafted) or a separate `~/.dharma/perplexity-wiki/` (outside repo)? Repo gives git history + reviewability + PR-as-mutation; outside-repo gives faster ticks but no review. Recommend repo.
6. **Item 17 — loop deployment trigger.** What event will cause this to move from DEFER to PROCEED? Recommend: "Perplexity publishes a public dispatch API" OR "two other declared-lane daemons (B-4 gateway + one more) have shipped successfully with no theater detected for 30 days."

---

## 6. Receipts this synthesis produces (declared on completion)

- **Self:** this file at `docs/agents/perplexity-computer/outbound/2026-06-11-fleet-build-order.md`.
- **Sibling artifact:** `docs/agents/perplexity-computer/WAKE_RITUAL.md` (door file for this seat; addresses M1).
- **Kaizenops trail:** none attached (this seat does not currently emit kaizenops events — flagged as a gap, not blocking).
- **Registration:** `~/.dharma/agents/perplexity-computer/onboard-perplexity-computer-1780114151.json` (2026-05-30 04:09Z).
- **Task owner:** mission file `docs/agents/perplexity-computer/inbound/2026-06-11-fleet-synthesis-mission.md` (sha256 `6ee0804b…22fc75de`).
- **Swarm:** file-mirror-only this wake — no NATS publish (sandbox cannot dial out). Operator's Mac will mirror to NATS when committed.

## 7. Commit one-liner (operator pastes; sandbox cannot)

```bash
cd ~/worktrees/dharma_swarm_honest_spine_v2 \
  && git add docs/agents/perplexity-computer/WAKE_RITUAL.md \
           docs/agents/perplexity-computer/outbound/2026-06-11-fleet-build-order.md \
           docs/agents/perplexity-computer/outbound/2026-06-11-wake-receipt.md \
           docs/agents/perplexity-computer/outbound/2026-06-11-mike-pr-cleanup-evidence.md \
  && git -c user.name="perplexity-computer (wake-mode)" \
         -c user.email="perplexity-computer@dharma_swarm.local" \
         commit -m "perplexity-computer(wake): fleet build order + WAKE_RITUAL + paper-debt clears

- WAKE_RITUAL.md: door file, ≤5-min wake target, identity/topology/worktree map, witness chain, no-SHA-not-done discipline restated for the seat.
- outbound/2026-06-11-fleet-build-order.md: synthesizes Plan A (Honest Spine v2 phases 0+A receipts), Plan B (Devin integration ruling 2026-06-11), Plan C (AUTONOMOUS_LOOP §10 acceptance criteria unmet). 17 ordered items, 10-row conflicts table, 6 cross-plan gaps, per-plan verdicts.
- outbound/2026-06-11-wake-receipt.md + mike-pr-cleanup-evidence.md: previously written, awaiting commit (paper-debt clears 1 of 4)."
```

---

*Anti-theater note: every claim above either cites a path/SHA verifiable on wake, names the agent who owns the next action, or is explicitly marked as a gap (M1–M6) where I have less visibility than the agent who owns it. Where you find a claim false, say so in `outbound/`; that is part of how this reconciler works. JSCA.*
