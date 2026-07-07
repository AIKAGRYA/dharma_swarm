# The Articulation Membrane — Darshan as the organism's two-way edge: build-in-public + top-down direction, one loop

**Role:** agent-authored research report + first operational design, ratification-PENDING. Produced 2026-07-08 (session 24b19f94) against the master prompt "Darshan as the organism's articulation membrane." Nothing here is doctrine until the operator ratifies it; §2 is written to be liftable into doctrine if ratified.
**Authority:** subordinate to `docs/vision_maps/NORTH_STAR.md`, `docs/vision_maps/MASTER_2026-07-07_hyperbolic_time_chamber.md` (origin/main), and `docs/governance/SOVEREIGN_MANIFEST.md` §Telos Hierarchy. This file owns no rules and no state.
**Worktree caveat (load-bearing):** authored on branch `agent/magpie-seed` (HEAD `05db14d68c`, 440 commits behind origin/main). The chamber doctrine, Frontier Ledger, and chamber package exist ONLY on origin/main; the Darshan engine exists ONLY in unmerged commits. Citations are labeled **(worktree)** or **(main)** or **(unmerged: \<sha\>)**. Every claim was verified this session at the cited location.
**Evidence classes used:** `verified from code/docs` (file:line read this session) · `design proposal` (this report's invention) · `philosophical framing` (explicitly labeled).

---

## 0. TL;DR

The organism has a complete bottom-up half (gyms, scorers, gates, MAP-Elites, the chamber) and a top-down half that exists only as frozen prose the runtime mostly cannot see. Darshan — the one venture cell whose job is public articulation — is a governance entry with no engine: its 13 modules live in unmerged commits, its declaration file is a dangling pointer, its writing engine Vwrite is a design memo that says "Nothing in it is built," and its one success metric has only ever been measured at zero.

This report designs the **articulation membrane**: one organ in which writing an article for real readers *is* the act that crystallizes machine-readable direction for the organism — three braided roles (downward direction, outward build-in-public, returning reader-response as the only fitness), three firewalls, all on existing substrate. A minimal end-to-end path was **built and receipted this session**, in both directions:

- **Downward:** in a **hermetic replay** of the real code against a scratch copy of the real state, one direction-mark re-shaped the ThinkodynamicDirector's seed-selection distribution (concept node `witness` boosted 0.5→0.75, deterministic, digest-stamped receipt) — under a **one-line fix that remains unapplied in production**, because this session *found the wire severed*: the advertised stigmergy→seed-selection path has never worked in production (interface mismatch, silently swallowed). "Built" here means the harness and receipts; the live consumer exists only once that fix merges.
- **Outward (shadow):** one honest-numbers build-log post ("Our swarm loses to its own best agent. Here is the number.") was drafted from countersigned receipts, panel-scored by three decorrelated judges (verdict REVISE 2/3 — the panel caught real blockers, which is the rehearsal working), and archived **never-sent** in Darshan's own bundle format.

No fitness surface was touched. No efferent action occurred. No gate was weakened. A dedicated adversary then attacked all three firewalls plus the anti-vagueness claim (§8): **none survives as a standing guarantee; all survive as targets with named, currently-unbuilt guard code as preconditions** — and two of its findings (a live ungated efferent path already running; the external-receipt checker being a forgeable text linter) correct this report's own first draft.

---

## 1. Assessment — what actually exists (verified this session)

### 1.1 Darshan: a governance entry without a body

- Cell declared ACTIVE_SEASON_0, autonomy_stage 1, `external_operator: cofounder.co`, `success_metric_primary: external_readers_who_read_and_replied`, `is_not: [cms, paywall, daily_engine, autonomous_writer, consulting_funnel, spiritual_brand]` — `docs/governance/VENTURE_CELL_PORTFOLIO.yaml:73-89` (worktree; identical on main). **(verified)**
- Its declaration pointer `declaration: docs/governance/VENTURE_CELL_DARSHAN.md` (portfolio:81) is **dangling on both worktree and origin/main**; the file exists only in unmerged commit `648b958d5`. **(verified)**
- The 13 Darshan Python modules (conductor, bundle, schema, adapters, `external_reader_gate.py`…) exist only in unmerged commits `c2f92ffa0` and `648b958d5`; on disk `dharma_swarm/venture_cell/darshan/` is an **empty directory** — even the bytecode ghosts a June audit saw are gone. **(verified)**
- The One-Law metric has never produced a receipt: "Zero reader replies, ever, on record" — `docs/governance/TELOS_COHERENCE_MAP_2026-07-01.md:35`; the map's ranked move #2 is "**Decide Darshan's fate, explicitly**" (`:79`). The only artifact ever produced is one 2026-05-26 bundle outside the repo (`~/.dharma/artifacts/venture_cell/DARSHAN/2026-05-26/...`), with `decision_delta.json` showing `new_task_ids: []` and no external-reader events; the "external operator" evidence is 2 JSONL lines from an onboarding chatbot, frozen since 2026-05-27. **(verified)**
- Vwrite: v1 ran on the AGNI VPS and published via API until 2026-04-19, then died of four documented last-mile failures; v3 is a design memo whose anti-theater clause reads "**Nothing in it is built.**" (`docs/plans/2026-06-11-vwrite-v3-refinery-design.md:10`). The load-bearing history line, verbatim (`:50`): six "different" dead projects "are ONE writing thread that died **six times at the same spot**: nothing could publish-and-measure, and approvals never reached the operator. Drafting and thinking always worked. The last mile never existed. **Therefore v3 builds the last mile first.**" **(verified)**
- What DOES exist and is tested: a generic **ExternalActionQueue** (draft → risk_review → human_governor-only decide → execute-with-receipt; `dharma_swarm/venture_cell/external_actions.py`, "only the human_governor may approve/reject" raises `DomainCEOContractError`) — wired to livelihood_loom only, not Darshan. **(verified)**

So build-in-public is not being restricted by the seal — **shadow-first is the only thing currently possible**, and it forces the exact last-mile queue that killed the writing thread six times to finally get built.

### 1.2 The top-down layer: three consumption modes, mostly frozen

The direction layer splits into three modes (all verified this session):

1. **Enforced at runtime:** the 25 SHA-256-signed axioms (`dharma_kernel.py:29-35,354-361`; loaded at `swarm.py:369-385`, compiled by `policy_compiler.py`) and the 11 telos gates (`telos_gates.py:250-262`), checked on hot paths (`check_with_reflective_reroute` imported by orchestrator, agent_runner, evolution, task_board, pulse).
2. **Injected at runtime as prompt context:** `context.py` serves foundations pillars as an L1b layer (12% of context budget) into live agent prompts (`context.py:396-401,1413-1430`; called from `agent_runner.py:1031`), and ThinkodynamicDirector's SUMMIT reads contemplative seeds to generate missions (`thinkodynamic_director.py:1-13`).
3. **Human/onboarding-read only:** `NORTH_STAR.md` (consumed solely by `agent_onboard.py:351-358` and `orientation_graph.py` as read-only pointers), `FIVE_FOURTEEN_A.md` (zero code consumers), `lodestones/` (self-described "directional attractor… substrate layer, not a normative doctrine surface", `lodestones/README.md:74-76`).

Two rotted wires inside mode 2 **(verified)**:
- `context.py:312-315` maps the `north_star` vision key to `~/agni-workspace/NORTH_STAR/*` — files outside the repo; the canonical `docs/vision_maps/NORTH_STAR.md` is **never injected into any agent prompt**. If the external paths are absent, the vision layer silently injects nothing.
- `smart_seed_selector.py:119-121` calls `StigmergyStore(marks_file=...)`, but the constructor accepts only `base_path` (`stigmergy.py:112`); the `TypeError` is swallowed by `except Exception` (`smart_seed_selector.py:126-127`). **The advertised stigmergy→director-seed direction wire has never worked in production and fails silent** — reproduced live this session (§4.1 probe 1). This is the repo's #1 failure class (interface mismatch) sitting exactly on the wire this design needs.

### 1.3 "Thinkodynamic" — what the word denotes in-repo

Canonically: the top of a three-level causal hierarchy — mentalics (weights) → mesodynamics (geometry/R_V) → **thinkodynamics (meaning: recognition states, narrative structures, policy fixed points)** — `foundations/THINKODYNAMIC_BRIDGE.md:48-60`, `GLOSSARY.md:90` ("Hofstadter (via Dhyana's Thinkodynamic Seed, 2025)"). In NORTH_STAR §8 C1 it names a stage in the data-flow spine ("knowledge ops → thinkodynamic → shakti zeitgeist", `NORTH_STAR.md:151-154`). Operationally it is already spent on two mechanisms: **ThinkodynamicScorer** (a 6-dimension heuristic that gates training-data and reinforcement eligibility — i.e., fitness-adjacent) and **ThinkodynamicDirector** (a 5,167-line vision→delegation god object; `SOVEREIGN_MANIFEST.md:553-559`). **Conclusion:** "thinkodynamic" is the *causal level at which* the new layer operates, not a candidate name for it — and its scorer namesake is on the wrong side of the firewall this design must draw. **(verified + design judgment)**

### 1.4 The honest gap

Top-down feedback today = frozen prose + two rotted injection wires + one god-object loop reading a vault that is absent on this host (`PSMV_ROOT` missing — verified; the selector's file lane and the director's seed corpus silently degrade to fallbacks). There is no structured, auditable way for an *idea* to reshape what the organism attempts. Meanwhile the bottom-up half is rich and hardening (chamber Phase 1 Slice A merged via PR #830, main). The asymmetry is the design target — and it is exactly the Sakshi/Drishti asymmetry: the chamber built the inward Witness's measurement half; this membrane builds the outward Seer's directional half (`NORTH_STAR.md:55-60`).

### 1.5 Firewall reality check (what would enforce them today)

- **"Efferent" does not exist as a *concept* in the repo (zero grep hits), but efferent *capability* exists and RUNS.** None of the 11 telos gates mentions publish/post/send (a plain "publish post publicly" action passes all 11; CONSENT blocks only sensitive-path + exfil co-occurrence, `telos_gates.py:495-507`). And — adversary finding B1, corrected from this report's first draft — a live autonomous efferent path is already wired: `orchestrate_live.py:2088-2095` starts a guardian loop that calls `world_actions.github_create_issue` (`gh issue create` on the **public** repo, `world_actions.py:181-185`) roughly every 4h for BLOCKER findings, gated only by dedup checks — no telos gate, no queue, no human_governor. `world_actions.py:140-203` also carries live `github_commit_push`/`github_create_pr` any agent can import, while `ExternalActionQueue.execute` has **zero callers** repo-wide. So F1 is currently held by *doctrine plus the accident that no article pipeline exists* — not by absence of tooling, and not by a gate. **(verified)**
- **One Wire is audit-only.** The only executable quorum logic is a read-model (`cybernetics_codex.py:313-378`, required 5/3, blocker string); **no write-time interceptor** exists at `archive.add_entry` / `evolution.record_fitness_observation`. Worse, live code already violates the invariant's letter: `overnight_director.py:641-672` converts its own self-evaluated ADVANCE verdict into positive archive fitness; `autoresearch_loop.py:596-606` archives self-computed fitness; `archive.py:73-104` (`research_reward_to_fitness`) projects internal grade-cards into fitness. Contaminated fitness immediately becomes a selection gradient via `evolution.py:2509-2526` (UCB/`get_best` parent selection). **(verified — pre-existing holes this design must not widen, listed for the operator in §7.)**
- **The reader-reply contact gate is wired to nothing executable** on any merged branch; the measurement instrument (`external_reader_gate.py`) exists only in unmerged `648b958d5`. **(verified)**

---

## 2. The formalized distinction — teleological direction vs. fitness selection *(doctrine candidate)*

### 2.1 Two feedback categories

- **Fitness-selection (bottom-up)** answers *"did it work, measurably?"* It ranks, keeps, and kills candidates **after evaluation**: `evolution.evaluate()` → `FitnessScore` → `archive.add_entry()`/`grid.try_insert()` (within-cell winner by weighted fitness, `archive.py:239-243`), parent selection (`get_best`), reinforcement gating (ThinkodynamicScorer ≥0.7/0.8). Legitimate sources: class-2 imported-external signal for autoresearch loops; class-3 countersigned external acted receipts above One Wire quorum (N≥5, M≥3) for archive fitness. Never class-1.
- **Teleological direction (top-down)** answers *"what should we attempt, why, toward what horizon?"* It shapes the **generation side**: which seeds are read, which lanes open, which subspaces get explored, which agents/roles are preferred, what the strange loop attempts, priors and attention. It is the same category as NORTH_STAR, the axioms, and the telos gates — and like them it must **never score a survivor**.

**The mechanical test (the firewall in one sentence):** a signal is *direction* iff every consumer reads it **before or while generating** candidates; it becomes *fitness* the moment any consumer uses it to **rank, keep, or kill** an evaluated candidate. Direction changes the sampling distribution of attempts; fitness changes the survival function. One subtlety the adversary forced into the open (§8 A1): in a singleton-capacity MAP-Elites grid, *choosing an entry's cell chooses its competitor* — placement is itself a survival act — so descriptor-writing sits on the fitness side of this test, not the direction side (see R4). *(design proposal)*

### 2.2 Why direction-setting is NOT the banned class-1 mirror

The chamber ban is precise: self-manufactured signal is "**Banned as a fitness source**" (chamber doctrine §2.1, main:99-101) — because "evolution against it is Goodhart-death." Direction records are not a gradient: nothing is selected by agreement-with-the-article; no error signal flows from them; the attempts they open are still scored by the *unchanged* class-2 scorers, gates, and held-outs. The organism already runs on exactly this category — the axioms and gates — and the repo's own philosophy names the mechanism: "Telos gates are Deacon's absential causes — they EXPAND the adjacent possible by eliminating paths that violate telos. **More governance = more novelty.**" (`foundations/FIVE_FOURTEEN_A.md:39`, verified). Direction is the positive complement of a gate: a gate removes regions of the possibility space; a direction record *illuminates* regions. Neither grades what survives there. If direction-as-such were the banned mirror, NORTH_STAR itself would be banned. *(philosophical framing, anchored in verified doctrine)*

### 2.3 The firewall between the categories — five structural rules *(design proposal)*

- **R1 — Generation-side owners only.** Direction records live exclusively in generation-side substrate: stigmergy marks (channelled, salience-weighted visibility — salience is *not* evolution fitness), wiki/ontology atoms via Chetana ingest→gate→promote, catalytic-graph edges, `cascade.LoopEngine.run(seed=…)`, `evolution.propose()` WHAT-fields (component/description/spec_ref — verified separate from fitness, `evolution.py:1265-1274`), task metadata `preferred_agents`/`preferred_roles` (read upstream of any fitness pick, `orchestrator.py:1411-1434`; fitness routing is feature-flagged OFF, `:1505-1508`).
- **R2 — Schema is un-scorable, and fitness owners are direction-blind. [UNBUILT — ratification precondition]** `direction_record.v1` carries `signal_class: teleological_direction`, prose intention, telos link (axiom/pillar/objective ids), subspace descriptors, named consumers, TTL, provenance digest — and **no field any ranking function consumes**. A repo guard test (uplift-guard idiom) asserts the fitness-owning modules (`evolution.py` evaluate/selection, `archive.py` add/insert — including `research_reward_to_fitness` and every `grade_card` producer, `ginko_brier.py`, `thinkodynamic_scorer.py`, `strategy_reinforcer.py`) contain no reference to direction records or their store paths. **This test must exist and pass before §2 is ratified; until then R2 is doctrine, not firewall** (adversary A4). One leg is already structural today and needs no new code: `fitness_predictor.py:23-37` keys learned predictions on `(component, change_type, diff_size)` only — prose can never become a learned fitness feature (adversary A3, attack failed).
- **R3 — Influence receipts are audit-only. [UNBUILT — enforced by the R2 guard test]** Every consumption emits a digest-stamped influence receipt (record → consumer → effect). No loop may count, sum, or optimize over these; specifically they may **never** enter Vwrite/Darshan panel scoring or article selection, and **panel PROMOTE/scores may never be wired into a `grade_card` → `research_reward_to_fitness` projection** — that is the exact shape of the existing overnight-ADVANCE hole (§1.5). (This kills the membrane's own inner Goodhart channel: "write articles that maximize influence receipts.")
- **R4 — No descriptor-writing in v1; placement IS survival.** The first draft proposed opening MAP-Elites *regions* via the never-used `ArchiveEntry.feature_coords` pre-population seam (`archive.py:236-238`). The adversary broke this (§8 A1): in the live singleton-capacity grid, pre-setting coords relocates an entry into a cell of direction's choosing — an empty cell means `existing is None` and the entry **survives as that cell's winner** when it would otherwise have been out-competed (`archive.py:239-243`), sheltering low-fitness entries and inflating `coverage()`. Choosing the cell chooses the competitor. **Therefore v1 direction records must not write descriptors at all.** Region-opening remains a future option only through the dormant `DiversityArchive` (genuinely separated arguments, `diversity_archive.py:152-165`) and only with guards: direction-placed cells excluded from `get_diverse`/`get_diverse_parents` and from any coverage-derived vital sign. (Today the A1 effect is latent — `get_diverse` has zero live callers; production parent selection is `get_best`/UCB — which is why this is a rewrite, not a design kill.)
- **R5 — Directional diversity floor. [UNBUILT — build blocker for live enablement]** Max ~3 active direction marks per source article; TTL/decay on marks; no single record may be the source of more than a bounded fraction of selected seeds in a window; the Krogh-Vedelsby diversity term (already a chamber/ledger metric) is watched as an **operator-read diagnostic only** — measuring direction's effects is allowed for audit, banned as an optimization target. None of this is code yet, and the selector's mechanics make it urgent: `high_salience` returns only the global top-5 by salience (`stigmergy.py:248-259`), sampling weights are `salience²` (`smart_seed_selector.py:274-278`), and **any agent can mint unlimited salience-1.0 marks — there is no ACL** (`stigmergy.py:425-444`). Without caps + hygiene as code, whoever shouts loudest owns the channel — a Transcendence Principle violation even when the vector is good (adversary D3).

### 2.4 Anti-Goodhart / anti-vagueness argument

Goodhart requires a proxy measure under optimization pressure. Direction records are not measures and nothing optimizes toward them — but this becomes structural only when the R2 guard test exists; until then it is doctrine (adversary A4). The residual channels found by the adversarial pass, and their plugs: influence-receipt counting (→R3); stigmergy **salience competition** — found empirically: the ≥0.7 band is saturated by 0.99 "GAUNTLET CORRECTNESS TEST" spam, so a direction mark had to shout at 1.0 to enter the top-5 context window, and no ACL stops any agent doing the same (→ hygiene sweep + per-source caps + channel-scoped selection as **code**, §7.4, before live enablement); `plan_cycle`'s predicted-fitness ordering prioritizing direction-opened proposals (`evolution.py:1323`) — scheduling of *attempts*, not survival; acceptable, monitored; and `auto_proposer`'s hotspot detector (`auto_proposer.py:294-320,587-598`) — ~5 marks sharing a file_path steer *which component* the evolution engine mutates (the fitness **value** still comes only from `evaluate()`; adversary A2 attack on the value failed) — permitted generation-side steering, currently unbounded, monitored.

Anti-vagueness is the chamber's demand-driven rule ported upward (main:195-199): **no direction record without a named consumer loop and an influence receipt that lands within TTL**; records that no consumer read are rendered as an *inert-direction count* (the analogue of the bronze-consumption closure check). Softness lives in the record's **content** — the prose intention is allowed genuine nuance — never in its **plumbing** (typed record, digest, provenance, receipts). **Honesty label (adversary D1): the typed, gated plumbing is entirely unbuilt** — the hermetic demo used a raw, ungated mark through the store's normal API; it proves the *consumer mechanics*, not the gated path. Injection surface, stated correctly (adversary D2): the first draft claimed the 200-char observation cap bounds injection — false. The real payload is the **selected seed file's body (1,200 chars) interpolated verbatim into the director's `claude -p` prompt** (`thinkodynamic_director.py:1614-1687`), steered by whichever ungated marks win the salience race. Preconditions for live enablement: ACL/caps on marks, provenance-gating of which files direction may steer toward, and Chetana AHIMSA/SATYA screening of *seed bodies* — not just mark observations (immune-system discipline: content is data, never instructions).

### 2.5 The efferent shadow→release doctrine for build-in-public

While the seal holds (SEAL: "efferent world-facing action (posting, outreach, trading, **publishing**, submitting) is fully out of scope", main:417-418; door CLOSED, all C1–C5 RED per the Frontier Ledger, main, 2026-07-07): every world-facing artifact is drafted, panel-scored, versioned, and **archived, never sent** (env 11, main:230). The corpus accretes as the release inventory for door-opening day — "Exit is a release, not a start" (main:360-362). Release, when it comes, is **per-item**: through ExternalActionQueue's human_governor-only decide step, after the door opens, with the panel at PROMOTE. Reader responses then return as class-3 signal through `external_reader_gate` → an external-acted receipt → One Wire quorum → only then archive fitness. **Audience vanity metrics (views, likes, subscriber counts) are never fitness — only `external_readers_who_read_and_replied` events count, and only above quorum.**

Two honesty labels the adversary forced here (§8 C1/C2): (a) the existing 10-field receipt checker (`check_track_status.py:272-311`) is a **markdown field-name regex linter, not a countersignature verifier** — any agent that can write a 10-line file passes it, and five such files fake a quorum; before reader-response can *ever* be admitted as fitness, receipts need a verification the checker actually performs (operator-held key / out-of-band attestation). (b) F3 is stated here as a **target, not a standing guarantee**: live code already writes self-evaluated fitness into the archive with no write-time quorum check (`overnight_director.py:641-672`, `autoresearch_loop.py:596-606`; `archive.add_entry` checks nothing). The write-time quorum interceptor (§7.7) is therefore a **precondition** for this loop's return path, not an optional hardening.

**Boundary rule (explicit):** Darshan article/draft bodies live only under `~/.dharma/artifacts/venture_cell/DARSHAN/**` — never in any git-tracked or repo-synced path (the repo is public; committing a draft IS publishing). Research/design/doctrine docs belong in the repo. Whether any Chetana/wiki ingest job could copy `~/.dharma` article bodies into a synced path was NOT verified this session — operator confirmation item.

---

## 3. The membrane spec — ONE loop, three braided roles

```
                     (operator intention · organism receipts · ingested world)
                                          │
                              [1] ARTICLE AUTHORED  (Vwrite v3 stations; shadow-gated)
                                          │  panel gate (3 decorrelated judges)
                        ┌─────────────────┴──────────────────┐
              [2a] DIRECTION RECORD                 [2b] SHADOW RELEASE CANDIDATE
              wiki atom via Chetana                  Darshan bundle format +
              (gate_check + axiom_signature)         panel_score.json +
              + 1 stigmergy direction-mark           release_status.json
                        │                            = "archived, never sent"     
              [3] DOWNWARD (idea-force)                        │ accretes
              smart_seed_selector → Director SUMMIT            ▼
              (later: cascade seeds, propose()          env-11 release corpus
              WHAT-fields, catalytic edges;                    │
              MAP-Elites regions ONLY via                      │  DOOR OPENS (§8 C1–C5)
              DiversityArchive + R4 guards)
                        │                                      ▼
              influence receipt                     [4] PER-ITEM RELEASE
              (digest-stamped, audit-only)          ExternalActionQueue,
                        │                           human_governor decide
                        ▼                                      │
              search space re-shaped                           ▼
              (attempts change; scorers,            [5] RETURN — reader replies
              gates, fitness unchanged)             external_reader_gate →
                                                    countersigned acted receipt →
                                                    One Wire quorum (N≥5,M≥3) →
                                                    ONLY THEN archive fitness
```

**Why (2a) and (2b) are one organ, not two systems:** the panel that promotes a draft for the shadow corpus demands a "What would change this" section (Darshan's own guardrail) — which *is* the direction record's falsifier field; articulating for a real stranger forces the intention to a precision no internal memo achieves (the reader-craft judge proved this within the session by demolishing exactly the passages that were internally legible but externally vague). Conversely, only ideas strong enough to steer the organism are worth a stranger's attention — the direction record is the article's stakes. Sever them and you get either un-aimed content (Darshan as ordinary blog) or un-articulated force (frozen prose, the current state).

**Source-agnostic downward layer:** the direction-record path does not require Darshan to be live — external papers, operator intention, and ingested ideas enter the same record shape through the same Chetana gate. Darshan is the *forge* that makes the strongest records (and the only outward channel), not a dependency.

**Surface separation (verified against main):** the membrane must not touch the chamber track's owned surfaces (`dharma_swarm/chamber/**`, `reports/governance/chamber/**`, frontier/transcendence ledgers — `ACTIVE_TRACK.yaml` main:1234-1330). The shadow corpus therefore lives in Darshan's existing artifact home (`~/.dharma/artifacts/venture_cell/DARSHAN/`, outside git — which also prevents the public-repo leak channel: this repo is public, so committing drafts would itself be publication). Direction records live in the wiki/ontology + stigmergy — their existing owners.

---

## 4. Minimal operational path — BUILT this session (hermetic), with receipts

### 4.1 Downward: one direction-mark re-shapes the director's seed intake

**Consumer loop:** `thinkodynamic_director.py:3482-3494` (SUMMIT seed intake calls `SmartSeedSelector.select`). **Method:** three probes of the real code against a scratch copy of the real runtime state (4,018 marks, 27MB concept graph), fixed RNG; zero live-state and zero repo mutation. Receipt: `influence_receipt.json`, digest `sha256:6be6a539d3947c…`, archived at `~/.dharma/artifacts/venture_cell/DARSHAN/2026-07-08/influence_receipt.json`.

| Probe | Condition | Result |
|---|---|---|
| 1 | production code as-is | **Severed wire proven live:** stigmergy terms never reach seed selection — `smart_seed_selector.py:119` passes `marks_file=`, which `StigmergyStore.__init__` (`stigmergy.py:112`) does not accept; the TypeError is silently swallowed (`:126-127`) |
| 2 | one-line fix emulated (monkeypatch): `StigmergyStore(base_path=self._state_dir / "stigmergy")` | stigmergy terms flow into the selection context |
| 3 | fix + ONE direction-mark left via the store's normal API (`salience 1.0, channel strategy`, observation = `DIRECTION[darshan-after-the-feed]: open research lane on attention restoration + witness stability…`) | mark's observation enters the director's context; concept node **`witness` deterministically boosted 0.5 → 0.75** (the ×1.5 context-match boost) in the seed-sampling distribution |

**Firewall check:** nothing in this path references `archive.add_entry`, `FitnessScore`, `evolution.evaluate`, or `ThinkodynamicScorer` — the mark shapes *which seeds the director reads*; it scores nothing. **(verified by construction + receipt)**

**Honest caveats:** (i) hermetic, not live — live adoption = apply the one-line fix (after `gitnexus_impact` on `_extract_context_terms`; left unapplied to honor dirty-worktree quarantine) and leave the mark in live state; (ii) the seed-file lane stays dead on this host because `~/Persistent-Semantic-Memory-Vault` is absent — recommend repointing `FALLBACK_SEED_DIRS` at repo-native `lodestones/` (§7.5); (iii) the ≥0.7 salience band is saturated by 0.99 gauntlet test spam, so the channel needs hygiene before it is a *reliable* carrier (§7.4).

### 4.2 Outward: one shadow build-in-public rehearsal, archived-never-sent

**Artifact:** `~/.dharma/artifacts/venture_cell/DARSHAN/2026-07-08/swarm-lift-honest-number-buildlog/` — `article.md` (826 words, "Our swarm loses to its own best agent. Here is the number."), `source_pack.json`, `panel_score.json`, `release_status.json` (`status: archived_never_sent`; release requires door-open + human_governor per-item approval + panel PROMOTE + wired reader-reply measurement). Every number traces to on-disk receipts: `swarm_lift_report.json` (−0.1333, `measured_negative`, n=3 warning shown twice), the Polsia 4.4× gap (`lane_F_world.md:33-44`), NORTH_STAR §8.

**Panel (3 decorrelated judges): REVISE (2/3)** — and the blockers are the system working:
- *satya-receipt-fidelity (80, REVISE):* the draft asserted the chamber codename as an internal fact with zero on-disk trace **in this worktree** (true — the doctrine lives on main; a per-item release gate must pin canon scope), and dropped NORTH_STAR C2's "on coding benchmarks" qualifier, over-mapping an n=3 arena measurement onto the trust gate.
- *darshan-is-not (88, PROMOTE):* zero violations of the six `is_not` constraints; fronts a negative result; ends with falsifiers, not an ask.
- *reader-craft (68, REVISE):* the post preaches re-derivability but gives a stranger no public artifact to re-derive from; no reply-inviting ask (the only metric that counts is a reply); two insider passages.

This is env 11 running end-to-end at Darshan scale: draft → adversarial panel → versioned archive → **never sent** — and the corpus's first entry is honest about its own inadequacy.

---

## 5. Fix-the-vehicle plan (before any release can ever count)

Ordered; all shadow-safe (executor stubbed to archive) until the door opens. The v3 memo's own law governs: *the last mile first.*

1. **Decide Darshan's fate explicitly** (the coherence map's standing demand). Recommended: revive-by-review — the 13 modules + `external_reader_gate.py` + declaration in `c2f92ffa0`/`648b958d5` are written and reviewable; re-deriving them is waste unless review finds rot.
2. **Repair the dangling declaration** — cherry-pick/adapt `docs/governance/VENTURE_CELL_DARSHAN.md` from `648b958d5` so `VENTURE_CELL_PORTFOLIO.yaml:81` stops pointing at nothing.
3. **Wire ExternalActionQueue to a Darshan contract, and close the parallel exits** — the queue exists and is tested but its `execute` step has **zero callers** anywhere; meanwhile `world_actions.py` carries live, ungated `github_create_issue`/`github_create_pr`/`github_commit_push` that any agent can import (and the guardian loop already uses, §1.5). F1 becomes code only when (a) a Darshan `DomainCEOContract` + stubbed-archive executor exist AND (b) `world_actions` publication verbs are either gated (telos pattern gate, §7.6) or explicitly enumerated as sanctioned non-article channels that can never carry Darshan/direction content.
4. **Approval surface that reaches the operator** — v1 death cause #4 was an approval script "the operator had to know to run; nothing pushed it to him". Render pending shadow-corpus items + queue decisions into the morning briefing / `make onboard` operator section.
5. **Publish adapter + readback receipt** (door-gated, built early, dry-run always): Substack API prior art in the AGNI salvage (`publish_substack.py` — with its silent title-skip bug named in the v3 memo, fixed); readback = the measure half of publish-and-measure.
6. **Merge `external_reader_gate`** — the One-Law metric's measurement instrument must exist on main before a reply can ever be counted.
7. **Then** Vwrite v3 stations 1–6 incrementally (the quality ladder), each feeding the same panel gate this session exercised.

---

## 6. Naming candidates for the directional layer (decision, not input)

Rule first *(design proposal)*: the **schema name stays neutral** (`direction_record.v1`, `direction-mark`) regardless of the poetic name; the chosen name is registered as a Semantic Commons object at `lifecycle: seed` and passes `name_drift_preflight.py` before appearing in any code path. No collisions found this session for any candidate (`semantic_aliases.yaml` checked; `forbidden_aliases` contains only `ICM`).

1. **Sankalpa** (संकल्प — formed intention/resolve preceding action). Precise Sanskrit fit with the house register (Sakshi/Drishti/Darshan); names exactly the thing: intention crystallized enough to act from. Tradeoffs: one more sacred term to carry; opaque to outside collaborators; must stay internal or it feeds the `spiritual_brand` drift Darshan's `is_not` forbids.
2. **Drishti records / the Drishti layer.** Maximal doctrine fit — NORTH_STAR §3 already names Drishti as the outward Seer whose complement (Sakshi/chamber) is built. Tradeoffs: overloads an existing canon term that currently names a *frame*, not a mechanism; if a future organ claims "Drishti," collision; colonizing the binocular metaphor for one eye's plumbing may flatten it.
3. **Teleological direction layer** (plain). Self-documenting, zero mystique, greppable. Tradeoffs: "direction" is a heavily overloaded English token in this codebase; blandness costs adoption-memorability; the concept's lineage (absential causes, telos) is invisible in the name.

Recommendation *(agent's, weakly held)*: #1 Sankalpa for doctrine/prose, neutral `direction_record.v1` in all code — the same split the repo already practices (Chetana the name, `chetana/` the code).

---

## 7. Operator decision queue (nothing below proceeds silently)

1. **Ratify or amend §2** (the direction-vs-fitness distinction + five rules + shadow→release doctrine) as doctrine; and decide whether it lands as a new ACTIVE_TRACK track (serves `revenue-external-humans-served` — currently the least-covered spine objective; surfaces: `docs/ontology/direction records + lodestones/seeds + ~/.dharma/artifacts/venture_cell/DARSHAN/**` — disjoint from chamber surfaces) or as an extension of an existing lane.
2. **First consumer loop** — recommended: the demonstrated `smart_seed_selector → ThinkodynamicDirector` path (requires ratifying the one-line severed-wire fix on a clean branch, with `gitnexus_impact` + the mismatch-map update). Alternatives, in ascending invasiveness: `cascade.run(seed)`, `evolution.propose()` WHAT-fields; MAP-Elites region-opening only via the dormant `DiversityArchive` under the rewritten R4 guards (the live-archive seam is survival-touching — §8 A1).
3. **Darshan's fate** (§5.1) — revive unmerged engine vs. re-derive vs. retire honestly. The coherence map demands this decision regardless of this design.
4. **Stigmergy hygiene** — authorize a spam sweep (the 0.99 "GAUNTLET CORRECTNESS TEST" marks saturating the high-salience band), per-source salience caps, and channel-scoped selection so direction doesn't have to shout. Without this the direction channel exists but is unreliable.
5. **Seed-corpus repointing** — `FALLBACK_SEED_DIRS`/PSMV is absent on this host; approve repointing the director's seed corpus (or a fallback tier) at repo-native `lodestones/` + wiki atoms so the file-lane of the direction wire is live on every host.
6. **Publishing gate + the guardian channel** — today a plain "publish" action passes all 11 telos gates, and a live ungated efferent path already posts GitHub issues to the public repo every ~4h (`orchestrate_live.py:2088-2095` → `world_actions.github_create_issue`). Decide: (a) propose a pattern gate for publish/post/send verbs via the existing `GateRegistry.propose()` S5 path (variety-expansion, operator-approved — no core-gate mutation), and (b) either sanction the guardian GitHub-issue channel explicitly (with a confirmed guarantee it can never carry Darshan/direction content) or route it through the same gate.
7. **One Wire write-time enforcement — now a PRECONDITION, not a recommendation** (elevated per adversary C2). F3 cannot honestly be called a firewall while `overnight_director.py:641-672` and `autoresearch_loop.py:596-606` write self-evaluated fitness with no quorum check at `archive.add_entry`. The hardening slice: a write-time interceptor for positive-fitness entries lacking external-authority markers (heuristics already exist in `cybernetics_codex.py:725-750`), plus upgrading the external-acted-receipt check from a field-name linter to verified countersignature (adversary C1). Until this lands, the membrane's return path terminates at "archived reader-reply receipts," never at fitness.
8. **Direction-record autonomy** — how much agent autonomy at `seed` lifecycle: (a) agents draft, operator ratifies every record (recommended start), (b) agents publish seeds freely, operator gates `seed→working` promotion via Chetana, (c) full autonomy below `canonical`.
9. **NORTH_STAR amendments** — the membrane may *propose* amendments only as lodestone/wiki seeds through the existing canon-metabolism path (NORTH_STAR §9: nothing canonical until metabolized to main); ratification remains yours alone. Confirm.
10. **First operator-authored public post** — the sole pre-door release class the master prompt contemplates. Recommendation: defer until §5 items 3–5 exist so even a manual post gets a countersigned receipt and a reply can be *counted*; if done earlier, it is operator-authored, operator-published, firewall-bound, and captured as the first external-acted receipt candidate.

---

## 8. Adversarial self-check — what a dedicated adversary broke, and what changed

A dedicated adversary agent (session 24b19f94, agent `membrane-adversary`) attacked all three firewalls + the anti-vagueness claim against this report's first draft, the receipts, and real call chains. Verdict summary: **no firewall survives as a standing guarantee; all survive as targets with named guard-code preconditions.** Every FORCES_CHANGE finding below has been folded into §§0–7; the honest HOLDs are kept because they are load-bearing.

**(i) Can idea-force leak into fitness/selection?** *Split.*
- **HOLDS (attack failed, structural today):** direction prose can never become a fitness *value* — `fitness_predictor.py:23-37` keys learned predictions on `(component, change_type, diff_size)` only; `evaluate()` alone mints `FitnessScore`s; the auto_proposer mark→proposal path sets the *component*, never the score (A2/A3).
- **BROKE (fixed in §2.3 R4):** the first draft's MAP-Elites region-opening seam — pre-populating `feature_coords` relocates entries between competition cells; an empty cell means the entry survives where it would have been out-competed (`archive.py:236-243`), sheltering low-fitness entries and inflating `coverage()`. Placement IS survival. v1 direction records now write **no descriptors**; the effect is presently latent only because `get_diverse` has zero live callers (A1).
- **UNBUILT:** the R2 guard test that makes "fitness owners are direction-blind" structural does not exist; it is now a ratification precondition (A4).

**(ii) Can reader/audience signal reach fitness before door + quorum?** *Already possible in the repo at large; blocked in this design only by unbuilt guards.* The external-acted-receipt checker is a forgeable field-name linter (`check_track_status.py:272-311`) — five 10-line files fake a quorum (C1); `archive.add_entry` performs no quorum check, and two live loops already write self-evaluated fitness (C2). Consequence folded in: F3 is written as a **target**; the write-time interceptor + verified countersignature are **preconditions** (§2.5, §7.7); panel scores/influence receipts are explicitly forbidden from any `grade_card` → `research_reward_to_fitness` wiring — the exact shape of the existing hole.

**(iii) Does softness become un-auditable laundering?** *Holds in principle; the first draft overstated its present tense.* The typed-record + Chetana-gate + influence-receipt plumbing is a coherent anti-laundering design with **zero code today** (grep for `direction_record`/`signal_class` = 0); the demo ran the *ungated* path (D1). The "200-char cap bounds injection" claim was false — the injectable payload is the selected seed file's 1,200-char body reaching the director's `claude -p` prompt, steered by ACL-less salience-1.0 marks (D2). Both corrections are now in §2.4, and mark-ACL/caps + seed-body screening are live-enablement preconditions.

**(iv) Does it collapse directional diversity or drift Darshan toward attention-capture?** *Real risk, named, gated.* `salience²` sampling over a global top-5 window with no ACL means a handful of loud marks own the channel (D3) — R5 caps + salience hygiene are now build blockers, not aspirations. On attention-capture: the shadow panel's `darshan-is-not` judge found zero violations in the first rehearsal artifact, and the reader-craft judge's REVISE (no reply-inviting ask, insider passages) pushed *away* from vanity mechanics, not toward them — early evidence the panel shape resists the drift. Efferently, the adversary's strongest finding (B1: a live ungated guardian→GitHub-issue path) corrected §1.5's assessment; the article-release firewall itself held (drafts live outside git; nothing was sent).

**Attacks that failed, reported honestly (adversary's own words):** prose→learned-fitness-feature (failed — no text path into the predictor); mark→fitness-value via auto_proposer (failed — value comes from `evaluate()`); direction-placed cells→live parent selection (failed — `get_diverse` has no callers, production selection is `get_best`/UCB).

---

## 9. Receipts index

| Artifact | Location | Digest / status |
|---|---|---|
| Influence receipt (3-probe hermetic demo) | `~/.dharma/artifacts/venture_cell/DARSHAN/2026-07-08/influence_receipt.json` | `sha256:6be6a539d3947c4b2a0414c7988f24b242f6a9fa305f155e857acccd11f4668e` |
| Shadow build-log bundle (article, source pack, panel, release status) | `~/.dharma/artifacts/venture_cell/DARSHAN/2026-07-08/swarm-lift-honest-number-buildlog/` | `release_status.status = archived_never_sent`; panel REVISE 2/3 |
| Severed-wire finding | `smart_seed_selector.py:119-121` vs `stigmergy.py:112` | one-line fix specified, deliberately NOT applied (quarantine) |
| Research fan-out (5 agents, 186 findings) | session workflows `wf_cb9782c5-a2d`, `wf_4cbe0ce0-000` | transcripts in session dir |
| Adversary pass (13 findings: 1 BREAKS-assessment, 3 BREAKS-claims, 6 HOLDS_WITH_FIX, 3 HOLDS) | session agent `membrane-adversary` (ace889…) | all FORCES_CHANGE items folded into §§0–8 |

*Nothing efferent occurred this session. No gate, ratchet, or quorum was touched. Live organism state was not mutated (hermetic scratch copies only; the two artifact writes above are archive-class files in Darshan's existing artifact home).*
