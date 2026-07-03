# Fable 5 Campaign Roadmap — Full-Repo Audit & Next Phases (2026-07-03)

**Role:** plan/roadmap record from a fresh-eyes full-repo audit (post the 2026-06/07 PR campaign). Proposes the next high-leverage coding campaigns and their sequencing. `docs/governance/ACTIVE_TRACK.yaml` owns live track state; this file owns the *why-this-next* reasoning so future sessions do not re-derive it.
**Source:** operator request 2026-07-03 ("step back, fresh eyes, full audit, master plan the next phases"). Evidence: `make onboard`, fresh `trust_gate_status.py` run (2026-07-03), `spine_bypass_report.py`, three parallel audit sweeps (code health/dormancy, PR-campaign reconstruction 2026-06-15→07-02, outward/revenue+research surfaces).
**Rule:** if this file disagrees with ACTIVE_TRACK.yaml, a receipt, or `make onboard`, trust the track/receipt/onboard output. Opening any campaign below as a track requires the normal ACTIVE_TRACK.yaml entry + render step; this doc is proposal, not admission.

---

## 1. Fresh-Eyes Verdict — five findings the plan hangs on

**F1 — The substrate is built; almost none of it is LIVE.** 0 of 13 cybernetic loops are CLOSED_LIVE (11 HARNESS_PROVEN, 2 BLOCKED on One Wire quorum N=3/5, M=1/3). Every track closed in the 2026-06-30 graduation batch closed as `VERIFIED_SLICE` with an explicit "not a production live-readiness claim." Spine dispatch sits behind `DHARMA_SPINE_DISPATCH` (unflipped in prod); the evolution apply gate is held shut (`DHARMA_EVOLUTION_SHADOW=1`, BR-003). The system is a fully-instrumented engine that has never been left running.

**F2 — The core thesis is currently measured as FALSE in-house.** Trust gate C2 = 0.05 RED: latest measured swarm lift is **-0.1** — the swarm loses to its best single agent (`reports/anatomy_altitude_2026-06-10/lane_E_organism_vision.md`). The Transcendence Principle (CLAUDE.md) is proven mathematics *given its three conditions*; the measurement says at least one condition (most plausibly quality aggregation and/or error decorrelation) does not hold in the current wiring. The Arena exists to make this falsifiable but still lacks best-single-model + budget-parity controls (its own open blocker).

**F3 — Two of three spine objectives are unowned, and the doctrine already says which is next.** All 5 active tracks serve `substrate-nativeness`. `revenue-external-humans-served` and `research-depth` have zero tracks (BR-022; `ACTIVE_TRACK.yaml`). Recorded revenue: $0 against NORTH_STAR §11's 90-day "funds itself totally." The organism-rewire track's item 8 is already doctrine: *the next track opened MUST serve revenue-external-humans-served.*

**F4 — Process metabolism is crowding out delivery, uncosted.** Of 73 main commits since 2026-06-15, the largest bucket (16) is governance-ops cadence; ratchets/gates add 6 more. BR-022(2): governance rent is uninstrumented — CLAUDE.md doctrine says every gate must be evaluated against its diversity cost, but no instrument computes it. Governance grows; nothing prices it.

**F5 — The verification substrate is exceptional, which is exactly what makes big autonomous coding campaigns cheap here.** 12,639 collected tests, CI ratchets, receipt schemas, adversarial-verify culture, mismatch map at 0 open BLOCKERs, Go organs compiled+tested in CI. High-agency model campaigns are safest where verification is dense — this repo has already paid that cost. The debt side: 153 top-level modules exceed the 500-line limit (worst: `thinkodynamic_director.py` 5,255; `agent_runner.py` 3,385; `orchestrator.py` 3,220), which is the main tax on every future campaign's context window.

**The one-sentence diagnosis:** the organism has spent its recent campaigns perfecting its inward truth machinery; the highest-leverage next moves are to (a) turn that machinery ON for real, (b) let it honestly measure the transcendence claim, and (c) point it outward at the two unowned objectives — before governance rent compounds further.

---

## 2. What "Fable 5 campaign" should mean here

A campaign is a good fit for high-capability autonomous coding when it is: (1) bounded to owned surfaces, (2) verifiable by existing tests/receipts/ratchets rather than operator vibes, (3) heavy on cross-file synthesis and spec-to-code reasoning, (4) light on credentials/infrastructure only the operator holds. Each campaign below states its acceptance criteria in existing-instrument terms and isolates the operator-only steps into §5's decision queue so agent work never blocks on them silently.

---

## 3. The Campaign Portfolio

### Phase 1 — GO LIVE (finish substrate-nativeness; 2 campaigns, ~2–3 weeks)

#### Campaign 1A — Spine Adoption Endgame
- **Track:** existing `runtime-truth-spine-adoption-2026-06` (drive to SHIPPED, do not open new).
- **Work:** migrate `orchestrator.py` dispatch and `agent_runner.run_task` through `invoke_agent()` (the two remaining blocker slices); drain the 4-entry intentional-bypass allowlist (`node_gateway` submit endpoints ×2, `a2a_client._dispatch_local`, `nats_transport.consume_message` — reclassify or migrate per ORGANISM_REWIRE_DOCTRINE §1); enable allow-list-at-zero + hold-at-zero ratchet in uplift_guards CI; author `SPINE_ADOPTION_NARRATIVE.md` last.
- **Fable 5 fit:** `agent_runner.py` (3,385 lines) is the largest, riskiest migration surface — exactly the multi-file, semantics-preserving surgery where deep-context models earn their keep. Use the migration as the sanctioned moment to carve `agent_runner.py` toward the 500-line law (extraction into `dharma_swarm/spine/`-adjacent seams only; the track's non-goal forbids broad decomposition beyond invoke_agent routing).
- **Accept:** `spine_bypass_report.py` → 0 intentional, 0 unknown; ratchet baseline `spine_bypass_entries=0`; onboarding's `bypass_allowlist_empty` criterion flips green; GATE 1 (one live EvidenceReceipt on a real dispatch) witnessed after operator flips D1.
- **Operator gates:** D1 flag flip in compose (organism-rewire item 1), GATE 1 witness.

#### Campaign 1B — Live Promotion (harness → daemon-live)
- **Track:** existing `loop-closure-2026-06` + `organism-rewire-2026-07` items 2–3.
- **Work:** drain/quarantine the 2,191 historical `dispatch_dropoff` rows (loop-closure blocker 1); build `dgc spine tail` + read-only cockpit pulse panel (receipts/hour, last-receipt age, dropoff count); harden Go sense-organ invocation (compiled-binary/toolchain check, per-source errors to cockpit, `github_ingestor` live trigger go-g04, host-aware Loop-5b closure check); then promote HARNESS_PROVEN loops one at a time as each declared live owner-surface criterion passes on the daemon branch that actually runs — trunk first (Loop 1, then 2/6).
- **Fable 5 fit:** the promotion work is forensic — each loop needs its live criterion read against real daemon telemetry, with honest failure classification. This is adversarial-verification work, not feature typing.
- **Accept:** onboarding shows Loop 1 CLOSED_LIVE persistently; `cybernetics_codex` audit `closed_live_count` > 0 with valid receipts; dropoff backlog drained with a quarantine receipt.
- **Operator gates:** VPS provisioning + secrets (organism-rewire item 4) — the daemon needs an always-on host for "persistently."

### Phase 2 — PROVE OR FIX THE THESIS (the C2 campaign; can start in parallel with Phase 1)

#### Campaign 2 — Arena Truth: make the transcendence claim pay rent
- **Track:** existing `orchestration-arena-v1-2026-06`.
- **Work:** (i) implement best-single-model controls + budget-parity proof on every arena run (the track's blocker — no capability claim without it); (ii) wire arena scorecard + DPI receipts into a read-only governance report surface; (iii) run the honest measurement at volume; (iv) **if lift stays ≤ 0, treat that as the finding** and run the diagnosis the Transcendence Principle prescribes: measure the Krogh-Vedelsby diversity term and error-correlation across seats, then attack the weakest condition (candidates, in current-evidence order: quality aggregation in orchestrator fan-in; correlated errors from same-family seats; routing that ignores specialty). Feed arena winners into the cold-start trace corpus (labels only, zero weights — v1 doctrine).
- **Fable 5 fit:** designing a statistically honest eval harness (budget parity, significance gating, control arms) is the highest-reasoning-density work in the portfolio, and it is entirely hermetic — frozen taskpack, deterministic scorer, no external credentials.
- **Accept:** every arena run carries a best-single-model control + parity proof; C2 evidence line in `trust_gate_status.py` cites a fresh measured lift (whatever its sign) instead of the 2026-06-10 -0.1; a written diagnosis memo if lift ≤ 0.
- **Why this outranks everything but Phase 1:** every other ambition (revenue wedge quality, DGM-style self-improvement, the NORTH_STAR §8 bar) sits downstream of whether the swarm actually beats its best seat. Right now the only measurement says no. Nothing else de-risks the whole venture as much per token spent.

### Phase 3 — OPEN THE OUTWARD EDGE (new track — doctrine-mandated next)

#### Campaign 3 — Revenue Wedge v1: productize the Agentic Code Governance Sprint
- **Track:** NEW — `revenue-wedge-governance-sprint-2026-07`, `serves: revenue-external-humans-served` (BR-022 packet A; satisfies organism-rewire item 8's sequencing doctrine). Open after spine-adoption closes (keeps WIP at 5).
- **Why this wedge:** it is the only offer where the repo's *existing strengths are the product*. `docs/offers/agentic-code-governance-sprint.md` ($5K–$25K, 3–7 days) sells exactly what this repo has over-built for itself: slop-scans (71 hygiene patterns), provenance mapping, CI ratchets, agent-governance review signals (AI-A1…E1). Selling the internal immune system is a shorter path than Darshan, trading, or courses — and it converts F4's over-investment from pure cost into inventory.
- **Work:** (i) extract the hygiene/ratchet/provenance tooling into a client-runnable audit kit (target-repo-agnostic: point at any repo, produce the ranked slop/provenance report the offer promises); (ii) deliverable generator — the report an engineering lead pays for, rendered from scan receipts; (iii) engagement receipts flow through `RevenueSpine` (`/api/revenue` already has targets/outreach/payments/reinvest, human-approver-gated outreach preserved); (iv) acted-receipt path per `EXTERNAL_GRADIENT_PORTFOLIO_SPEC.md` — paid human work is the C3 leg and enters fitness ONLY via One Wire; (v) the missing `reports/revenue_wedge/first_cash_receipt_status.md` gate-evidence surface, honest at $0 until it isn't.
- **Fable 5 fit:** turning an internal tool-farm into a coherent external product is a synthesis/packaging problem across dozens of scripts — high-context, low-risk, fully testable against fixture repos.
- **Accept:** audit kit runs end-to-end against a non-dharma fixture repo in CI; one real outreach approved by the operator; C3 evidence line cites a receipts file that exists. (First actual cash is an operator/market outcome, not a code acceptance criterion — the code criterion is "nothing on our side blocks it.")
- **Operator gates:** wedge ratification, pricing, outreach approval, any client comms.

### Phase 4 — RESEARCH DEPTH (new track — reopen the R_V lane post-COLM)

#### Campaign 4 — The P0 Bridge Experiment: R_V ⟷ L4, co-tested
- **Track:** NEW — `rv-bridge-p0-2026-07`, `serves: research-depth`. Open after Phase 3's track is underway (WIP 6 ≤ max 10) or as the operator prefers.
- **Why:** NORTH_STAR §2 stakes the entire "measurable awareness" claim on a falsifiable program; the P0 gate (R_V and L4 compression on the *same* forward passes) "has never been co-tested in one experiment" — yet the code already exists (`l4_rv_correlator.py`, self-described "THE MISSING EXPERIMENT", plus `rv.py`/`system_rv.py`/`swarm_rv.py`/`bridge.py`). The COLM calendar death killed the paper, not the program. Organism-rewire item 8 explicitly demands this lane get "an owned, receipted eval loop again."
- **Work:** (i) run Rung 1 (lexical-confound control — highest priority, never run) and the P0 co-test from `docs/research/self_reference_attractor/RESEARCH_PROGRAM.md`; (ii) wire it as a receipted eval loop (frozen prompts, deterministic pipeline, receipts to an owned report surface) so it survives sessions instead of dying with a deadline; (iii) purge the remaining stale COLM references (`benchmarks/README.md:455`, `docs/telos-engine/`, `research/economic_value_tracking/README.md:325`, `living_map.py:411`); (iv) paper draft against a *live* venue chosen by the operator, deadline held in `~/.dharma/research_deadlines.json` (the post-COLM mechanism), never hardcoded.
- **Accept:** one receipted P0 run with the correlation reported either way; Rung 1 confound result recorded in `foundations/EMPIRICAL_CLAIMS_REGISTRY.md`; zero stale-COLM references.
- **Operator gates:** GPU/compute for the torch/transformers path; venue choice.

### Continuous / Cross-cutting (no new tracks; ride existing ones)

- **C-1 Governance Rent Ledger (BR-022 packet B):** instrument per-gate prevented-drift vs coordination-tax so governance additions are decided against a measure, not a vibe. Wire the Krogh-Vedelsby diversity term (now consolidated in `archive.py` post-D6a) into gate-addition review. HARD RULE from BR-022: do not add new governance machinery to close this — it must be a read-only ledger over existing witnesses.
- **C-2 Mike completion:** Slice 4 cloud heartbeat (the one failing onboarding criterion: no `schedule:` in `merge-master-mike-backlog.yml`) + Slice 3 cloud Claude reviewer once the operator provisions the secret and ratifies D1–D4. Small, additive, unblocks human-PR flow — a force multiplier for every campaign above.
- **C-3 God-object diet, opportunistic only:** carve the >500-line offenders ONLY when a campaign already owns the surface (Campaign 1A owns `agent_runner.py`/`orchestrator.py`). No standalone refactor track — that would repeat the inward-spiral failure mode this plan exists to break.
- **C-4 BR-014:** the `BHED_GNAN` gate hard-passes (`telos_gates.py:512`) — the most-central Gnani gate is inert. Fix must route through `GateRegistry.propose()` (direct edits governance-forbidden). Attach to Campaign 2's aggregation work, since a real gate there changes measured behavior.

---

## 4. Sequencing & WIP

```
now ──► 1A spine endgame ──► close spine-adoption ──► open Phase 3 (revenue)   [WIP stays ≤5]
  └──► 2  arena truth (parallel: disjoint surfaces)
  └──► 1B live promotion (paced by operator VPS + D1)
                     └──► Phase 4 (research) opens when operator ratifies      [WIP 6]
C-1..C-4 ride existing tracks throughout.
```

Priority if forced to choose one: **Campaign 2 (Arena Truth)**. A system that cannot beat its best single seat should not scale outward claims; a system that can, changes every downstream conversation (C2, the wedge's credibility, the grant/YC narrative) at once.

## 5. Operator Decision Queue (agent work must not silently block on these)

1. Flip `DHARMA_SPINE_DISPATCH=1` in the committed compose env (D1 — a one-way door, chosen knowingly per rewire doctrine) and witness GATE 1.
2. Provision the always-on VPS + secrets (daemon, NATS, litestream); Mac demotes to mirror.
3. Ratify Mike decisions D1–D4; provision the ANTHROPIC repo secret for the cloud reviewer.
4. Ratify the revenue wedge choice (this plan recommends the Governance Sprint) and its pricing/outreach policy.
5. Choose the research venue + provide GPU access for the P0 experiment.
6. TTL housekeeping: `runtime-truth-spine-adoption-2026-06` is past its 21-day verify TTL — re-verify or close-with-evidence.

## 6. Anti-Goals (inherited + new)

- No new governance mechanisms to fix governance (BR-022's own warning).
- No capability claims from the arena without budget-parity + best-single-model controls.
- No weakening of any telos gate, ratchet, or the One Wire quorum to make a loop or wedge "close."
- No standalone big-bang refactor of god objects; carving happens only inside owned campaign surfaces.
- No trained weights in Arena v1; no market P&L as per-iteration selection signal.
- No new truth stores, receipt systems, or parallel naming schemes; extend the existing owners.

---

## Appendix — Audit Evidence Snapshot (2026-07-03)

- Trust gate (fresh run): C1 0.79 AMBER · C2 0.05 RED (lift -0.1) · C3 0.30 RED ($0 revenue, 11 cells, 2 ACTIVE-class) · C4 0.34 RED · C5 0.20 RED (3 sections render before memory-kernel in `context_compiler.py`).
- Loops: 0 CLOSED_LIVE / 11 HARNESS_PROVEN / 2 BLOCKED (One Wire N=3/5, M=1/3). Runtime DB: 8,837 delegation runs (4,184 completed / 4,532 failed), 24,700 receipt rows, 2,191 historical dispatch_dropoff.
- Spine bypass: 6 `.submit()` sites — 1 adopted, 4 intentional, 0 unknown, 1 non-production.
- PR campaign 2026-06-15→07-02: 73 commits; top themes governance-ops 16, Pudgala 11, Mike 8, ratchets 6, telos formal gates 6.
- Broken register: 7 open-like (BR-003 blocker-class, BR-004/005/013/014/021 degraded, BR-022 strategic).
- Interface mismatch map: 0 open BLOCKERs; NEW-05 GUARDED, NEW-07/08 PARTIAL+, NEW-12 HALF-OPEN.
- Tests: 12,639 collected across ~805 test files. Size law: 153 top-level modules > 500 lines.
- Active tracks: 5, all `substrate-nativeness`; 9 open blocker items across them; `revenue-external-humans-served` and `research-depth` unowned.
