---
title: VWRITE v3 — The 7-Station Refinery (Writing-Empire Reboot)
date: 2026-06-11
status: PROPOSED
supersedes: VWRITE v2 (2026-05-03, ~/.claude/plans/pull-up-vwrite-iterative-pretzel.md)
---

# VWRITE v3 — The 7-Station Refinery

**Anti-theater clause:** No agent may cite this memo as evidence of progress. This is a design document recovered and completed from a stalled (rate-limited) 2026-06-10/11 session. Nothing in it is built. No code was written or edited in producing it.

---

## 0. Provenance — recovered artifacts this document is grounded in

Every historical claim below traces to one of these recovered artifacts. Claims that could not be traced are marked **UNRECOVERED** and not elaborated.

| # | Artifact | Path | What it grounds |
|---|----------|------|-----------------|
| A1 | Six-lane research workflow output (status: `completed`, 6 lane result objects, findings tagged verified/probable/speculative) | `~/.claude/projects/-Users-dhyana/de42d62c-c8e8-4544-8221-0c253e2896ce/workflows/wf_2e5aada2-8f1.json` | AGNI archaeology, article audit, infra inventory, loose-thread inventory, role-company evidence, writer playbook |
| A2 | Master plan with PART 2 synthesis (written before the session died, last modified 2026-06-11 00:57) | `~/.claude/plans/artha-idea-refinery-master-plan.md` | The 7-station refinery shape, divergence-round corrections, and the **OPERATOR DECISIONS 2026-06-11** block |
| A3 | Memory write from the same session | `~/.claude/projects/-Users-dhyana/memory/project_artha_scout_2026_06_10.md` | ARTHA recon, governance constraints, the writing-empire research record, second-round operator decisions |
| A4 | VWRITE v2 redesign (2026-05-03, never built) | `~/.claude/plans/pull-up-vwrite-iterative-pretzel.md` | The quality ladder: 10-agent MoA, 5-judge gate, human voice gate, DPO-over-prompts, 8-dim rubric, κ≈0.2–0.4 voice ceiling |
| A5 | AGNI VPS salvage (pulled 2026-06-11, before this recovery) | `~/.dharma/salvage/agni_vps_2026-06-11/` (`vwrite/` state+scripts+graveyard, `AGNI_READER_SCHOLAR/` DOKKA corpus 7.2M, `content/` incl. ~70 `awaiting_dhyana` drafts) | Primary evidence for the death causes; the practice corpus; the draft inventory |

Primary-evidence spot-checks performed during this recovery, directly in A5:

- `vwrite/scripts/publish_substack.py` contains the literal line `print(f"  [SKIP] No title found in {filepath.name}")` — the silent title-mismatch skip is real code, not lore.
- `vwrite/state/published.jsonl` last successful API publish: 2026-04-19 ("Before the Ruling"). `vwrite/state/publish_tracker.json` frozen at `{"last_publish_date": "2026-04-19", "count_today": 1}`.
- `vwrite/graveyard/` holds five `s_020_autonomous_agents-auto` drafts dated Apr 9 → May 15 — the seed-collapse (one seed feeding every draft for a month) is visible in the filenames.
- `vwrite/scripts/approve_article.py` exists — the approval gate was a script the operator had to know to run; nothing pushed it to him.

**UNRECOVERED:** the VPS-side memo `feedback_vwrite_silent_failures.md` (lives at `/root/.claude/projects/-root/memory/` on the AGNI VPS per A4; not in the local salvage). The "13 articles stranded 8 days because a cron wrapper swallowed stdout" claim therefore rests on the research lane's `verified` tag in A1, not on a locally held log. Treat the *count* and *duration* as lane-verified, not re-verified here.

**UNRECOVERED:** any partially-written synthesis draft beyond A2/A3. Searches of `~/.claude/plans/`, `~/.dharma/knowledge/staging/2026-06-11/` (only generic stop-hook atoms), and `~/.dharma/cross/` found nothing further. Conclusion: the synthesis was *saved into A2 PART 2 before the session died* — less was lost than feared.

---

## 1. Why VWRITE died — the four documented death causes

VWRITE (व्रत, "The Vow") was created on the AGNI VPS the day OpenClaw was killed (2026-03-26) and published via API until 2026-04-19 (A1, A5). It did not die of bad writing. It died of four last-mile failures, all of one species: **the system could not see itself fail, and the operator could not see the system.**

| # | Death cause | Evidence | v3 antidote (§2) |
|---|-------------|----------|------------------|
| D1 | **Silent publisher failure** — title-format mismatch between generator and publisher; every article hit `[SKIP] No title found` and the pipeline reported nothing | A5 `publish_substack.py` (literal skip line); A1 agni-archaeology lane (verified) | Station 7's publish step is loud and *verified*: a publish emits a receipt or an alarm, never silence |
| D2 | **Swallowed cron output** — wrapper discarded stdout; articles sat stranded ~8 days with zero alarms | A1 (verified; VPS memo itself UNRECOVERED locally); A5 `publish_tracker.json` frozen at 2026-04-19 corroborates the stall | Every station logs to an append-only visible file; a watchdog alarms when any station's output file stops growing |
| D3 | **Hidden approval gates** — drafts waited in `awaiting_dhyana/` for a yes nobody knew to give; `approve_article.py` had to be discovered and run by hand | A5 (script + ~70 stranded drafts in salvage `content/`); A1 agni-articles lane: stall pattern maps to batch approvals (probable) | Approvals *reach* the operator: one daily approval queue surfaced in the morning briefing, with a one-tap upgrade path |
| D4 | **Stuck idea-seeder** — every draft Apr 18 → May 21 generated from one seed (`s_020`) | A5 graveyard filenames (5× `s_020_autonomous_agents-auto`, Apr 9–May 15); A1 (verified) | Seed rotation driven by live DOKKA/NIKKI practice data + a novelty/dedupe guard |

Cross-cutting finding (A1, loose-threads lane): six "different" dead projects — AGNI Substack, DOKKA/NIKKI corpus, DARSHAN articles, capital_lab IG-12 dossiers, hermes posting scripts, the standing blog/arXiv priority — are ONE writing thread that died **six times at the same spot**: nothing could publish-and-measure, and approvals never reached the operator. Drafting and thinking always worked. The last mile never existed. **Therefore v3 builds the last mile first.**

---

## 2. VWRITE v3 = the 7-station refinery

v3 is the writing-lane instantiation of the refinery shape already approved in A2 (`FIND → FIRST CUT → PANEL DEBATE → GAUNTLET → SMALL REAL TEST → EVOLVE → ESCALATE`), with v2's quality ladder (A4) folded into the middle stations and the four antidotes baked in as **design laws**, not features.

### Design laws (non-negotiable, every station)

1. **No silent stations** (kills D1, D2). Every station emits a visible `[PASS]/[SKIP]/[BLOCKED]` line to an append-only JSONL it owns. A watchdog (natural home: the always-on hermes gateway on the AGNI VPS, per A2 §VPS-utilization — *proposal, needs design pass*) alarms when any station's output file stops growing beyond its expected cadence. The Apr 19–27 incident is the canonical enemy.
2. **ESCALATE is load-bearing** (kills D3). Every prior collapse shared "no operator in the loop." The baseline channel is a **single daily approval queue rendered into the morning briefing** at `~/.dharma/sessions/captures/daily/<date>/morning_briefing.md` (this file is already produced daily by the 04:30 wake cron — existing surface, no new daemon). Each item: title, one-paragraph why, judge scores, APPROVE/REVISE/KILL slots. Upgrade path: Telegram bot one-tap (key-day item). One yes per batch, never per post.
3. **Publish is verified or it didn't happen** (kills D1). The publish step must (a) post, (b) read the post back from the platform (RSS/API), (c) write a receipt `{url, title_hash, timestamp, readback_ok}` to `published.jsonl`, (d) alarm on any mismatch. A publish without a readback receipt is a FAILURE, loudly.
4. **Seed diversity guard** (kills D4). FIND may not emit a seed whose embedding similarity to the last N seeds exceeds threshold (Qdrant on the AGNI VPS is the natural dedupe memory — A2 proposal). Seed sources rotate through live practice data: fresh DOKKA reading notes, NIKKI journal entries (hermes still runs NIKKI nightly — A1, verified), recognition events, plus the salvaged `awaiting_dhyana` backlog.
5. **NIKKI theater test in EVOLVE** (from A2): a reflection only counts if it changes next-cycle behavior (a measurable config/prompt diff).
6. **No fine-tuning promises** (from A1 writing-infra lane + A4): the training substrate is export-only by design; voice = capture-prompting from the salvaged corpus. Fine-tuning stays a someday-dataset.

### The stations

| Station | What it does (writing lane) | Reuses (verified in A1/A3 — never rebuild) | v2 layer absorbed (A4) |
|---|---|---|---|
| **1 FIND** | Seed inbox fed by DOKKA notes, NIKKI entries, recognition events, `awaiting_dhyana` backlog, world-radar drops | DOKKA corpus (salvaged, 7.2M), NIKKI nightly cron (live), world_radar/Go scout (needs repair — A3) | L0 seed+brew |
| **2 FIRST CUT** | Deterministic triage: novelty (Qdrant), telos-fit, voice-lane fit; promote ≥ threshold | `world_radar/analysis.py` triage shape; Ollama on AGNI VPS as free pre-filter (A2 proposal) | — |
| **3 PANEL DEBATE** | 3–5 seats argue the piece's angle, write a dossier with dissent preserved | DARSHAN bundle schema (claim_ledger/counterframes/gate_decisions — A1 writing-infra: the best existing precedent); council/business-mind skills | L1 10-agent MoA, *thinned* — see §3 |
| **4 GAUNTLET** | Hard quality gate: the 8-dim rubric scored by a decorrelated judge panel; deterministic pass criteria (composite ≥ 4.0, no dim < 3.0, no slop veto) | `idea_gauntlet.py` shape (cashclaw branch — A3); ECC humanizer/anti-slop patterns | L5 advisory editorial + L6 5-judge hard gate, with Bradley–Terry calibration deferred until gold pairs exist |
| **5 SMALL REAL TEST** | Draft → operator voice gate → publish to agnirecursivefire → fan-out derivatives (Notes/X/Bluesky per key-day keys) | ECC article-writing/content-engine/crosspost skills; hermes xitter + humanizer (A1) | L7 human voice gate (irreducible — κ≈0.2–0.4 voice ceiling, A4) + L8 publish |
| **6 EVOLVE** | Telemetry readback (Substack RSS exists today — A3), engagement capped at 30% of fitness, kills become anti-atoms, prompt-population mutation | `substack-pull-analytics.py` (read-only, exists); experiment ledger contract (A2) | L9 chetana write-back + DPO-over-prompts + Karpathy loop (v3-stretch, *after* the last mile is alive) |
| **7 ESCALATE** | The daily approval queue in the morning briefing; only cell births, posting batches, money, scale-ups, and taste questions reach the operator | morning briefing cron (live); Telegram bot = key-day upgrade | — |

### Build order (last mile first — the inversion that distinguishes v3 from every dead ancestor)

1. **Publish adapter + readback receipt** (Substack session auth = key-day blocker; Bluesky/Telegram free APIs as same-day fallbacks). Verify locally — note the v2-era `publish_substack.py` `idna.core` failure was never verified fixed (A2 divergence corrections); a Mac-local adapter supersedes the VPS script.
2. **Approval queue in the morning briefing** (render + parse loop).
3. **Watchdog + station logging contract** (design law 1).
4. **FIND with seed rotation** from the salvaged corpus + live NIKKI.
5. Stations 2–4 (triage, panel, gauntlet) — only after a draft can actually reach the world.
6. EVOLVE loops (DPO/Karpathy from A4) — last, once there is real telemetry to learn from.

First cargo: per **operator decision A2 §OPERATOR-DECISIONS #2**, the DARSHAN article does NOT go to agnirecursivefire (DARSHAN is its own venture). AGNI's first cargo comes from AGNI's own lane — the ~70 salvaged `awaiting_dhyana` drafts are the candidate pool (operator picks; decision point §5.2).

---

## 3. Hardwire vs role-company — the verdict

The question: staff the refinery as a persistent AI company (CEO/CTO/editor agents) or hardwire it as code?

The research lane (A1, role-company, 15 findings) found the persona-seeding literature **genuinely cuts both ways** — and the honest reading is asymmetric:

- **Against personas:** personas in system prompts do not improve task accuracy (Zheng et al., EMNLP 2024 — verified); MetaGPT/ChatDev gains come from SOPs + typed artifacts + executable feedback, not personalities; most of multi-agent-debate's gain is just voting/ensembling; the Berkeley MAST taxonomy (arXiv 2503.13657 — verified) shows free-form agent companies fail via role-disobedience and weak verification; in-house, the persistent-strategist pattern produced the phantom-target incident (A3 governance record).
- **For diversity:** decorrelation gains are real but come from **model** diversity, not persona diversity. (A2 divergence note: two supporting arXiv IDs in business-mind SKILL.md could not be verified — treat seat counts as testable defaults, not proven optima.)

**The verdict (the real one, not the romantic one): do NOT build a persona company. John is the CEO.**

- **Hardwire** FIND, FIRST CUT, GAUNTLET, EVOLVE, ESCALATE as code with deterministic scorers.
- **Staff only PANEL DEBATE**, with 3–5 seats defined as **thin role files** — mandate + rubric + output contract, NOT personality backstories — each pinned to a *different model* through dharma_swarm's existing provider door: `runtime_provider.resolve_runtime_provider_config()` → `create_runtime_provider()`, ordered by `model_hierarchy`. This is also the future-proofing answer: **roles are markdown files any runtime can load; models are swappable through the hierarchy that already exists.** No model string is ever hardcoded into a seat.
- Run the panel as independent takes → one synthesizer that preserves dissent; max 1 rebuttal round (voting carries most of the gain; long debates don't).
- Producer briefs (copywriter/visual) appear only in SMALL REAL TEST and are graded solely by real platform metrics.
- Orchestrator: `frontier_council.py` already implements the exact model-agnostic seat pattern (frozen seat dataclass) — but it survives **only in a safety snapshot, not on main**, while `sealed_packet_apply.py:32` still references it (A1, verified phantom). Revive-vs-minimal-rewrite is an architecture call to make when the build reaches station 3, not a default (A2 divergence note).

Reconciliation with the operator's "we want our own entire company" decision (A2 §OPERATOR-DECISIONS #4): the COMPANY is real — dharma_swarm + the refinery is the production floor, venture cells (AGNI publication, DARSHAN newspaper, ARTHA tests, capital_lab) are the business units, panels are the brain trust, John is the CEO. What we don't build is persona-executives; structure carries the gains.

---

## 4. Loose-thread consolidation map

Which stalled threads merge into the refinery, in what order, ranked by revival value (A1 loose-threads lane; order adjusted for the A2 operator decisions):

| Rank | Thread | State | Merges into | Revival move |
|---|---|---|---|---|
| 1 | **AGNI Substack** (agnirecursivefire, 12 live posts, 6 subs, silent since Apr 19) | Stalled, real, voice above-commodity (A1) | The publication v3 serves — operator-decided to CONTINUE | First closed publish+measure loop: one salvaged `awaiting_dhyana` draft through stations 5→7 |
| 2 | **DOKKA/NIKKI corpus** (~1,400 notes, 60 recognition events; NIKKI still runs nightly) | The genuinely alive part | Station 1 (FIND) seed source + the voice moat | Wire the salvage + nightly NIKKI into seed rotation; this is what made article quality track practice data (A1, verified) |
| 3 | **VWRITE v2 redesign** (May 3, never built) | Complete prior art | Stations 3–6 quality ladder | Absorb, don't rebuild: rubric, judge-panel shape, human voice gate, DPO loop (deferred) |
| 4 | **DARSHAN article + bundle schema** | One finished, gate-reviewed article; pipeline-as-artifact | Schema → stations 3–4; the article itself → the **separate** DARSHAN cell (operator decision) | Adopt claim_ledger/counterframes/gate_decisions as the panel dossier format |
| 5 | **hermes posting/analytics scripts** (xitter, humanizer, substack RSS pull, 4 sab_post scripts) | Working code, wrong wiring | Stations 5–6 adapters | Generalize; note hermes Substack monitoring is NOT confirmed cron-wired (A2 divergence — verify or wire) |
| 6 | **capital_lab IG-12 dossier pipeline** (ran once, manually) | Manual precedent | Station 3 shape | Copy the seed→dossiers→verdict shape; no code to salvage |
| 7 | **"Blog posts / arXiv" standing priority** | Declared, never operationalized | Becomes a refinery *lane*, not a project | Feed as seeds once the loop closes |

Explicitly NOT merged: LOOMWORK (composted-but-tagged, operator decree — A1); the DARSHAN *article* as AGNI cargo (operator decision); the AGNI VPS as runtime (it is a salvage site + utility node — scraper/Ollama/Qdrant/watchdog roles proposed in A2, design pass pending).

---

## 5. Operator decision points

Already decided 2026-06-11 (recorded in A2, restated here so nobody re-asks): agnirecursivefire continues; DARSHAN is a separate venture cell; AGNI's voice is the broad idea-lattice, not confessional-only; VWRITE v3 quality-ladder thrust approved; VPS-maximization directive issued.

**Still open — only the operator can make these calls:**

1. **KEY DAY scheduling** — the one-day credentials sprint: Substack session auth for agnirecursivefire, Bluesky app password, Telegram bot token, X keys (check write pricing), all stored via `dkeys add`. Nothing external can publish until this happens. *(yes/no + a date)*
2. **First cargo selection** — which of the ~70 salvaged `awaiting_dhyana` drafts ships first through the full loop (or: none of them; write fresh). *(pick one)*
3. **Approval channel** — is the morning-briefing daily queue sufficient as the v3 baseline, or is the Telegram one-tap bot a key-day requirement before the first publish? D3 says under-investing here is how the thread died every time. *(baseline vs phone-first)*
4. **Transparency posture** — agnirecursivefire is de facto openly-AI ("frominsidetheloop", first-person AI voice). Confirm staying openly-AI given FTC 2026 AI-disclosure enforcement; Substack ToS is silent (verified in A2). This is now a compliance decision, not just a brand one. *(confirm/change)*
5. **Cell-birth YES** — formal registration: AGNI-revival venture cell + ACTIVE_TRACK v2 node serving `revenue-external-humans-served` (the only uncovered spine objective). *(yes/no)*
6. **Voice-gate cadence** — v2's human voice gate is irreducible (κ ceiling). How many pieces/week is the operator willing to voice-gate? This sets the publish cadence ceiling honestly. *(a number)*

Honest horizon, divergence-corrected (A2): **2–5 years to meaningful revenue.** Do not plan resources on 18–36 months.

---

## 6. What v3 keeps and drops from v2

**Keeps:** the 8-dim rubric with anchored 1/3/5; the human voice gate as the irreducible top gate; judge decorrelation across model families; anti-slop veto; chetana write-back (publish → trusted atom, kill → anti-atom); the gold-set/Goodhart protections; the "honest section" stance (voice automation is impossible; the system fails-to-suppress transmission, it cannot manufacture it).

**Drops/defers:** Best-of-N=2 full double-runs (cost, defer); Bradley–Terry calibration until 50+ gold pairs exist; the 10-agent MoA at full width (start 3–5 panel seats, widen on evidence); the VPS as runtime (Mac is hub; VPS is salvage + utility node); LoRA-DPO stretch goals until the last mile has been alive for a month.

**Inverts:** v2's build order started at the generation layer (weeks 2–3) and reached publish-verification last. v3 builds the last mile first. That inversion *is* the lesson of the six deaths.

---

## Feedback to the stalled session

**What was recovered (vs. feared lost): nearly everything.**

- The plan file you saved survived intact: `~/.claude/plans/artha-idea-refinery-master-plan.md` — including PART 2 (the writing-empire synthesis) AND the OPERATOR DECISIONS block timestamped after the research round. Your synthesis largely *did* land before the rate limit hit.
- The memory write survived: `~/.claude/projects/-Users-dhyana/memory/project_artha_scout_2026_06_10.md`, updated through the second operator-decision round.
- The full six-lane workflow output survived with all findings and confidence tags: `~/.claude/projects/-Users-dhyana/de42d62c-c8e8-4544-8221-0c253e2896ce/workflows/wf_2e5aada2-8f1.json` (status `completed`, 84KB of structured results).
- The May 3 VWRITE v2 redesign: `~/.claude/plans/pull-up-vwrite-iterative-pretzel.md`, complete.
- The AGNI VPS salvage at `~/.dharma/salvage/agni_vps_2026-06-11/` — and this recovery spot-checked the primary evidence in it: the `[SKIP] No title found` line exists in `publish_substack.py`; `publish_tracker.json` is frozen at 2026-04-19; the graveyard's five `s_020` filenames confirm the seed collapse.

**What was lost or remains unrecovered:**

- The VPS-side `feedback_vwrite_silent_failures.md` memo is not in the local salvage — the "13 articles / 8 days" specifics rest on the research lane's verification only.
- The chetana staging atoms for the session (`~/.dharma/knowledge/staging/2026-06-11/`) captured only generic stop-hook noise, no content — the Stop-hook extract of the dying session added nothing.
- No in-flight synthesis draft beyond what's in the master plan was found; if you had unsaved prose in context, it is gone — but its content is reconstructed in this document.

**What the next session should do first:**

1. Put this document in front of the operator and collect decisions §5.1–5.6 — especially KEY DAY scheduling and first-cargo selection. Nothing else is blocked on thinking; everything external is blocked on credentials.
2. Pre-key-day build (no keys needed): the approval-queue render into the morning briefing + the station logging/watchdog contract (design laws 1–3). These are the D2/D3 antidotes and they are pure local plumbing.
3. Salvage one more thing from the VPS while it's reachable: `/root/.claude/projects/-root/memory/feedback_vwrite_silent_failures.md` (closes the one UNRECOVERED evidence gap) and verify which of `:8501/:8200/:8100` services matter (the queued VPS circuit audit).
4. Do not start the generation/judge layers until a draft can verifiably reach the world. The inversion is the design.
