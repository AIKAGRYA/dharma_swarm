# Dharma Helm — Leg One: the Instrument — Bounded Spec

```yaml
document_role: active_spec
status: DRAFT_PENDING_OPERATOR_MERGE
scope: leg one only (the instrument) — first shippable live Dharma Helm
assembled_at: 2026-08-19
assembled_by: Fable (spec-assembly lane, /to-spec)
source_of_truth: wayfinder MAP #1277 — CLEARED 2026-08-19, 100/100
canonical_repository: AIKAGRYA/dharma_swarm
tracks: helm-worldclass-terminal-2026-06 (terminal/**) ·
        dharmagraph-engine-2026-07 (ledger repairs — coordinate, never unilateral)
authority: none of its own
```

## 0. What this document is — and is not

This is the `/to-spec` collapse of the **cleared** wayfinder map
[Wayfinder MAP: first shippable live Dharma Helm #1277](https://github.com/AIKAGRYA/dharma_swarm/issues/1277),
per **closing ruling 5** ([issuecomment-5330445451](https://github.com/AIKAGRYA/dharma_swarm/issues/1277#issuecomment-5330445451)).

**It decides nothing.** Every normative line below traces to a ratified source, cited
inline. Where the map ruled, this document copies the ruling. Where a genuinely
undecided point surfaced during assembly it is parked in §10 `OPEN-QUESTION` — it is
not resolved here.

This file makes no repo-level authority claim — `docs/AGENTS.md:13-27` reserves such
claims for its named canon files, and this is not one of them. It is bound by, and
assembles, exactly three ratified sources: map #1277, the five closing rulings
([issuecomment-5330445451](https://github.com/AIKAGRYA/dharma_swarm/issues/1277#issuecomment-5330445451)),
and the 2026-08-19 handoff packet. It replaces nothing and decides nothing. It does
**not** admit the Nihonga master spec (see §11); that document's §0 precedence ladder
(owner state and receipts ≻ admitted code and tests ≻ governance canon ≻ ADRs and owner
contracts ≻ documents) is CANDIDATE reference only — cited, never bound
(`NIHONGA_HELM_FRONTIER_MASTER_SPEC.md` §0:24-30 @ `25c2a5409`).

**Sources assembled** (all read in full during assembly, 2026-08-19):

| # | Source | Ref |
|---|---|---|
| 1 | Wayfinder map body — Destination, Notes/locks, Decisions, obligations, Out of scope | issue #1277 |
| 2 | Five closing rulings — MAP CLEARED 100/100 | [issuecomment-5330445451](https://github.com/AIKAGRYA/dharma_swarm/issues/1277#issuecomment-5330445451) |
| 3 | Destination in the operator's own words (raw verbatim + append law) | [issuecomment-5328869849](https://github.com/AIKAGRYA/dharma_swarm/issues/1277#issuecomment-5328869849) |
| 4 | Frontier locks (speed bar, curator seat, hand list, zen-depth) | [issuecomment-5329454472](https://github.com/AIKAGRYA/dharma_swarm/issues/1277#issuecomment-5329454472) + Notes |
| 5 | Living-graph lock + fleet amendment | [issuecomment-5329825138](https://github.com/AIKAGRYA/dharma_swarm/issues/1277#issuecomment-5329825138), [issuecomment-5329857722](https://github.com/AIKAGRYA/dharma_swarm/issues/1277#issuecomment-5329857722) |
| 6 | Alive bar resolution | #1279 [issuecomment-5205570486](https://github.com/AIKAGRYA/dharma_swarm/issues/1279#issuecomment-5205570486) |
| 7 | Truth contract resolution | #1280 [issuecomment-5206806789](https://github.com/AIKAGRYA/dharma_swarm/issues/1280#issuecomment-5206806789) |
| 8 | Chassis resolution | #1281 [issuecomment-5205703537](https://github.com/AIKAGRYA/dharma_swarm/issues/1281#issuecomment-5205703537) |
| 9 | Tree/cutover resolution | #1385 [issuecomment-5329611894](https://github.com/AIKAGRYA/dharma_swarm/issues/1385#issuecomment-5329611894) |
| 10 | Slices 2–5 resolution | #1386 [issuecomment-5330028853](https://github.com/AIKAGRYA/dharma_swarm/issues/1386#issuecomment-5330028853) |
| 11 | Living-graph round 2 verdict | #1388 [issuecomment-5329612518](https://github.com/AIKAGRYA/dharma_swarm/issues/1388#issuecomment-5329612518) |
| 12 | Frontier scan report | `reports/wayfinder/research/badass_terminal_frontier_scan_2026-08-18.md` @ `84ec2ea4c` (branch `research/badass-terminal-frontier-scan-20260818`) |
| 13 | Living-graph round-2 report | `reports/wayfinder/research/living_graph_round2_2026-08-18.md` @ `29a1e9bdd` (same branch) |
| 14 | Build handoff / mission packet | `~/handoffs/2026-08-19_helm_legone_build_handoff.md` |
| 15 | Nihonga master spec — **reference only, `CANDIDATE_NOT_ADMITTED`** | `docs/plans/nihonga_helm_frontier/NIHONGA_HELM_FRONTIER_MASTER_SPEC.md` @ `25c2a5409` |

Session evidence: `make onboard` run in this worktree — **READY (exit 0)**, branch
`spec/helm-legone-20260819` @ `1f2419a7d526`, clean, base `origin/main`, authority: none.

---

## 1. Destination

### 1.1 The operator's own words — canon

The map records these as canon (2026-08-18, emphatic; spelling normalized only, wording
his). Copied verbatim from the map body:

> I want the most badass terminal in the world. I want amazing design, bleeding-edge speed, access to all models, and the ability to manipulate and check in and run the entire swarm from one single surface. To have it clean and zen and fast and smooth and a very high level of aesthetic and simplicity — and a recursively deep command center that is slightly complicated but just in the right way, that can see into and run and manipulate all the running processes. I want the main agents to be extensions of the swarm brain, able to speak and connect to the deepest parts of the swarm and the repo and codebase itself — not just helpful front-end figureheads, but woven into the context and packed with tools and able to manipulate elements and run workflows and understand the whole repo inside and out — to be more efficient token-per-token machines than any of the frontier models I would otherwise use in a siloed way. I want every interaction in the swarm recorded and saved — a full living graph and living database of all the transactions that go on, accessible through the Helm. This is a start.

**Append-below-quote law (locked).** *"This is a start"* marks the Destination **open**:
future pourings **append below his quote; nothing overwrites it**
(#1277 Destination; [issuecomment-5328869849](https://github.com/AIKAGRYA/dharma_swarm/issues/1277#issuecomment-5328869849)).
The raw verbatim with typos preserved is the provenance record and lives in that
comment — it is never edited, and the normalized reading above is the one carried in
the map.

### 1.2 Working decomposition — **Fable's read, not operator words**

Marked as such on the map. Six movements:

1. **One surface, one object** — seat = tip = canon.
2. **Zen speed** — amazing design; clean/zen/fast/smooth; bleeding-edge speed as
   first-class.
3. **Recursively deep command center** — complexity only in the right way; sees into,
   runs, and manipulates all running processes.
4. **Swarm-brain agents** — all models on call; primary seats context-woven,
   tool-packed, whole-repo-fluent — more efficient token-per-token than any siloed
   frontier model.
5. **The governed hand** — check in / run / manipulate the entire swarm from the
   surface. Retained ratified canon: the hand **consumes** the truth contract + RUDRA R0
   trusted join, never precedes them; cannot-lie and self-attestation remain locked
   decisions of the map.
6. **Total memory** — every interaction recorded; a living graph + living database of
   all transactions, queryable through the Helm.

### 1.3 What leg one is

**This spec = leg one: the instrument** (#1277 Destination). One real terminal chassis,
a live primary-agent seat, an honest read-only organism view, and **no fake-live
theater**. No effectful hand in leg one. Leg two (seat=tip unification) and leg three
(the governed hand on RUDRA R0) are **beyond this map** — see §7.3.

Destination-level breadth ≠ leg-one floor: *"access to all models"* is destination-level;
**the 7/7 fixed-order bar is the leg-one ship floor, not a ceiling** (#1277 Notes,
2026-08-18 ruling).

---

## 2. Locks

Every subsection is copied from a ratified source. Citations are on each lock.

### 2.1 Alive bar (locked)

Source: #1279 resolution [issuecomment-5205570486](https://github.com/AIKAGRYA/dharma_swarm/issues/1279#issuecomment-5205570486);
restated in #1277 Notes ("Alive bar (locked)") and reaffirmed unchanged 2026-08-18.

**Alive means (all required):**

1. **Primary seat** — one orchestrator Helm agent that can call a standing multi-model
   bench (not a single locked chat brain pretending to be the fleet).
2. **On-call cardinality** — **≥ 7 logical models** on the real path, counted as
   `model_pool` floor-class logical entries (or newly registered equivalent ids).
3. **On-call definition** — **recently verified**: successful live completion receipt
   within **TTL = 24h**. Not key-presence. Key-live without a fresh receipt does **not**
   count.
4. **Standing named bench, fixed priority order** (must-have set for healthy alive):
   1. **Fable 5**
   2. **GPT 5.6** (operator name; also called GPT Sol 5.6)
   3. **Grok 4.5** — Grok 4.6 may supersede when available; **same seat lineage**, not a
      second required count, until decided otherwise
   4. **Fugu Ultra**
   5. **Kimi K3**
   6. **Opus 5.0**
   7. **Opus 4.8**
5. **Power doctrine (operator)** — these seats define the real-path tier; other real-path
   models must be **≥ GPT-5.5 class**; workhorses sit one tier down (e.g. Kimi
   2.7-coding class) and do **not** replace the seven for the on-call count unless
   promoted by a later decision.
6. **Catalog honesty** — required names **must be registered** in the model pool (or
   explicit canonical logical id + route) **and** produce verify receipts before they
   count. No declared-but-green fiction. Existing shortfalls are **catalog debt, not
   permission to fake alive**.
7. **Below 7** — Helm remains **usable degraded** with a visible **N/7 on-call** banner;
   it is **not "alive" for ship criteria** while under floor.
8. **Read-only organism facets (min real, non-fixture)** — workspace (repo/branch/dirty)
   + runtime status + **on-call board (N/7 + verify ages)** + one task/board or mission
   surface. All other surfaces may be explicit `UNKNOWN`.
9. **10-minute prove-alive journey** — open Helm → see N/7 board with verify ages → one
   real primary orchestrator turn → switch to a second on-call model and get a real
   reply → open one RO facet with real data → missing facets show `UNKNOWN`, never green
   fiction.
10. **Out of this bar** — effectful hands, full A2A mesh, councils as a ship requirement,
    fixture playground as live.

**"No effectful hand" wording (locked, #1280):** no **workspace/runtime mutation** for
slice 1. **Live model calls are allowed** outbound contacts — they are not "hands".

**Measured code gap carried from #1279 (evidence, not optional):** floor catalog asserts
**13** entries with `MODEL_POWER_FLOOR = kimi-k2.6` (`tests/test_model_pool.py`,
`evolution_roster.py`); present in pool: `kimi-k3`, `gpt-5.5`, `claude-opus-4.8`; not
cleanly first-class: Fable 5, GPT 5.6, Grok 4.5/4.6, Fugu Ultra, Opus 5.0; **no hard
min-7 verified-on-call gate exists** (`live_routes` + `key_oracle` only).

### 2.2 Chassis (locked)

Source: #1281 resolution [issuecomment-5205703537](https://github.com/AIKAGRYA/dharma_swarm/issues/1281#issuecomment-5205703537);
#1277 Notes ("Chassis (locked)").

**Evolve the latest mainline Dharma Bun + Ink terminal as the only product chassis:**

- **Presentation:** `terminal/` (`@dharma/terminal`, Bun + React + **Ink 5.x**,
  packageManager `bun@1.3.11`) — Ink version superseded by closing ruling 3, see §5.3.
- **Runtime:** `python3 -m dharma_swarm.terminal_bridge stdio` (+ provider adapters).
- **Baseline:** **`origin/main` tip** for `terminal/`; whole-repo checkouts may lag —
  always rebase/implement from fresh main.
- Seats inspire, **do not replace** the chassis. Operator Seat = **patterns only**.

**Explicit non-choices:**

| Candidate | Role |
|---|---|
| Claude Code / Codex / Grok **apps** | **Not chassis.** Provider seats and competitive inspiration. |
| Python Textual TUI | Legacy; already declared replacement target |
| Fixture playground | IA reference only |
| Full Operator Seat branch merge | **Out for slice 1** — patterns only (honesty, joined RO, launch identity) |
| OpenTUI / full Rust rewrite | **Radar only** — not a first-ship chassis flip |

Chassis must host: primary orchestrator + ≥7 verified on-call seats + lean RO facets;
seats plug into the shell via pool/adapters.

### 2.3 Slice-1 information architecture — the Quiet Lever (locked)

Source: #1277 Notes ("Slice-1 IA (locked — Quiet Lever)").

- Conversation-centered.
- Compact **persistent truth band** (attachment/resync + N/7 ages).
- Workspace / runtime / TaskBoard / receipts open **contextually**.
- Five-place / Inspector preserved as a **future seam**.
- **Defer** the visible 45/35/20 whole-organism canvas; the maximalist forge layout is
  **non-binding**.
- **The Helm is an epistemic instrument for the organism, not the organism.**

### 2.4 Truth contract (locked)

Source: #1280 resolution [issuecomment-5206806789](https://github.com/AIKAGRYA/dharma_swarm/issues/1280#issuecomment-5206806789);
#1277 Notes ("Truth contract (locked)"). This is **law**, not aspiration.

**Purpose (vision altitude).** Protect **maximum truthful agency** over the organism
(Jagat Kalyan body): the operator must never believe a loop closed, work finished, fang
fired, or a seat "on call" **on narration alone**. UI chrome serves this; it is not the
telos. Truth is **pramana for work + organism claims**, not model-badge taxonomy.

**ONE LAW (Helm speech).** No status, spawn, ship, "closed", "done", or "on call" may be
claimed except via a **real, gated, verifiable, diversity-preserving** outcome — or
explicit **claim (not verified)** / **UNKNOWN**.

**Claim classes — both required for slice 1.**
1. **Work outcomes** — done, tests green, merged, deployed, A2A replied, experiment
   improved fitness.
2. **Organism self-status** — loop closed, evolution applied, gate held, swarm lift,
   trust gate, fleet "alive".
Unmeasured → **UNKNOWN** (or graded claim), **never soft green**.

**Pramana location.** **Owners + receipts** are truth. Ink only **projects** grades. No
semantic truth solely in Bun state.

**Multi-model.** The ordered 7 are **ensemble substrate** for decorrelated organism
judgment, not a second product. On-call = **verified within 24h**, never "online now".

**Formal nucleus (R2A — law; field names may refine at implementation):**

```
RouteVerification {
  logical_seat, canonical_lineage, route, served_identity,
  observed_at, expires_at, receipt_ref, result
}

OnCall(v, now) ⇔
  v.result == ok
  ∧ now < v.expires_at
  ∧ served_identity matches canonical_lineage
  ∧ evidence non-synthetic
```

**Lifecycle boundaries are non-substitutable:** `CONFIGURED · CONTACTED · WORKING ·
RETURNED · VERIFIED` (plus *claim-not-verified* as speech).

**Freshness dimensions are orthogonal, not paint:** `simulation · cache · stale ·
fresh · unknown · clock_skew`. **Future timestamps → `UNKNOWN`/`CLOCK_SKEW`, never
fresh.**

**Invalid promotions must be impossible in the evaluator**, not merely discouraged in UI.

**Session continuity (R1C).** Slice 1: **resume conversation transcript only**; organism
attachment is **re-probed** and stays **UNKNOWN** until authoritative resync. Same-process
is not the only mode; full durable organism continuity is **not** required for first ship.

**Ship-blocker kill.** Any path where the operator can take a **consequential action** or
believe a **loop / fang / on-call / done** on narration alone.

**Explicit non-goals of the contract.** Fixture-watermark taxonomy alone; multi-renderer
chassis; optional "soft honesty".

**Known false today (must close under this spec):** `live_routable` → route `ready`
without receipt (`dharma_swarm/terminal_bridge.py` ~1732–1754 — the mapping is live on
`origin/main` at `terminal_bridge.py:1733`; `model_status.py` still documents the receipt
requirement); surface authority as six booleans without owner/time/expiry
(`terminal/src/types.ts:448` `SurfaceAuthorityState`); `terminal/src/freshness.ts` treats
future timestamps as fresh.

### 2.5 Frontier lock 1 — leg-one speed bar (locked)

Source: #1277 Notes "Frontier locks (2026-08-18, operator verbatim: *'on board with all
of that except not sure abou tth eliving graph... needs more reserach. lock the rest
in'*)", item (1); numbers from the frontier scan report §Lane A, "Numbers — the
measurable speed bar".

**The Lane A table binds leg one, inside the forge outer budgets.**

| Metric | Target | Owner | Source/rationale |
|---|---|---|---|
| App frame compute+write (state→bytes) | **≤10 ms p95**, ≤16.7 ms max | App | 60 fps budget; headroom vs emulator's 5–38 ms |
| End-to-end keypress→glyph | **≤50 ms p95** on foot/kitty/Alacritty-class | Emulator+App | 15–24 ms emulator + 33 ms Ink throttle worst case |
| Sustained UI under log flood (10 MB/min) | **≥30 fps** live region, 60 fps burst; **zero dropped input** | App | Emulators ingest 11 MB in 0.25–0.41 s — the app must be the non-bottleneck via `<Static>` |
| Full-frame repaint size | ≤ terminal viewport (never taller) | App | Ink erase/rewrite mechanics (`ink.tsx`) |
| Cold start → first frame | **≤150 ms** | App | Codex-CLI rewrite rationale; measure our own |
| Steady-state RSS | **≤120 MB** | App | Typical Ink >50 MB; emulator adds 43–174 MB |
| Frame tearing | **0** (all frames BSU/ESU-wrapped) | App | Mode 2026 adoption list |

**Forge outer budgets the table sits inside** (`MASTER_FORGE_SPEC.md:827-846`, evidence
package): first paint p95 ≤250 ms; key-to-paint p95 <50 ms / p99 <100 ms under a
5k-node graph @ 10 ev/s; stream-event-to-visible p95 <100 ms; place switch p95 <50 ms;
warm bridge p95 <2 s; <250 MiB @ 5k-node/50k-event; 24 h soak.

**Also locked in the same ruling:**
- **`<Static>` append-only law** — all history/logs through `<Static>`; the live region
  stays O(viewport). Single biggest log-flood lever.
- **Ink 7 upgrade = adopted direction** (sequenced by closing ruling 3, §5.3).
- **kitty keyboard protocol** — progressive enhancement (`CSI > 1 u`, query `CSI ? u`).
- **OSC 8 hyperlinks** on entities; **OSC 9 notifications**, feature-detected.
- **mode-2026 (synchronized output) and mode-2027 (grapheme clustering) detection** —
  detect, never assume; measure widths app-side.

### 2.6 Frontier lock 2 — curator-seat law (locked)

Source: #1277 Notes, frontier locks item (2); design principles from the frontier scan
report §Lane C.

The winning seat is a **curator, not an accumulator**. Locked design law:

1. **Compile, don't accumulate** — smallest high-signal token set per step.
2. **Structure-aware repo artifacts** — AST chunks, symbol/dependency graphs, hybrid
   semantic+grep.
3. **Invest in the ACI** — tool ergonomics beat model upgrades.
4. **Cache-aligned layout** — stable prefix, append-only turns; never mutate early
   context.
5. **Gate the tool surface** — few, retrieval-selected tools, not every mount.
6. **Quarantine exploration; single writer** — subagents return summaries, one agent
   writes.
7. **Compact before ~100K working context.**
8. **Prefer fixed pipelines for routine steps** — agency only where branching pays.

**Claim law (locked):** token-efficiency claims — including the destination's
"more efficient token-per-token than a siloed frontier model" — are **provable only via
the preregistered two-arm protocol**: worker≠judge, hidden fail-to-pass tests, identical
harness across arms, k=5 trials, headline metrics **resolved-per-dollar AND pass^5**,
seat "wins" only if both beat baseline with a bootstrap 95% CI excluding zero (frontier
report §Lane C, "The honest measurement protocol"). The experiment itself is **later
radar**, not leg-one scope (§7.3) — the law is what binds: **no efficiency claim without
that protocol.**

### 2.7 Frontier lock 3 — hand steal/reject list (locked; the hand itself is **leg three**)

Source: #1277 Notes, frontier locks item (3); patterns from the frontier scan report
§Lane B.

**⚠️ Scope note:** this list is **locked now, built later**. Leg one has **no effectful
hand** (§2.1). The list binds the leg-three design so nobody re-litigates it there; it
creates **no leg-one implementation work**.

**ADOPT:**
1. **Sandbox × approval as orthogonal axes** (Codex).
2. **Plan mode as a hard gate** — edits mechanically blocked until the plan is approved.
3. **Non-delegable consent** — relayed approvals are untrusted; no agent supplies consent
   for the human.
4. **Deny rules bind in every mode** + un-approvable floors.
5. **Competing-diff review** — side-by-side agent diffs plus combined diff.
6. **Tool-call-boundary steering** — steering input lands at the next tool-call boundary
   (defined interruption semantics).

**REJECT:**
1. **Approval-by-timeout** (auto-proceed after silence).
2. **Post-hoc approval** (spend everything, then present a PR — authority collapses into
   after-the-fact review).
3. **Cosmetic gating** (a freeze that is prose, not enforced capability — Replit's
   canonical cost).

### 2.8 Frontier lock 4 — zen-depth grammar + accessibility law (locked)

Source: #1277 Notes, frontier locks item (4); pattern library from the frontier scan
report §Lane E.

**Grammar — every level must be:**
1. **Spatially stable** — users navigate by location memory; panels never move.
2. **Self-labeling** — the level announces what it is and what keys it takes.
3. **Reversible** — one Esc, one pop.

**Locked mechanisms:**
- **Fractal keys** — same verbs at every zoom, narrower scope.
- **Typed `:target` addressability** — jump anywhere by name.
- **Three-tier disclosure** — footer keys → `?` overlay → docs.

**Accessibility law (locked):**
- **ANSI16 fallback** — reserve truecolor for surfaces; the user's palette wins; never
  hardcode truecolor against it.
- **No decorative glyph noise** — nerd-font/braille glyphs optional, always with text
  equivalents (terminals have no accessibility tree; braille spinners read as noise).

**Named anti-patterns (locked as prohibitions):** shortcut wall; decorative glyph noise;
hardcoded truecolor — each a restatement of a locked item above (three-tier disclosure,
the no-decorative-glyph accessibility law, the ANSI16-fallback law).
*Research observation, NOT a lock:* the frontier scan's Lane E additionally names
"chrome maximalism" (itself marked "(assessment)" there) and "invisible modes" as
anti-patterns — recorded for orientation only; no ruling binds them
(`badass_terminal_frontier_scan_2026-08-18.md` §Lane E).

### 2.9 Living-graph lock — two layers + tripwires (locked)

Source: #1277 Notes "Living-graph lock (2026-08-18, operator tapped *'Two-layer +
tripwires'*)" + the fleet amendment
([issuecomment-5329857722](https://github.com/AIKAGRYA/dharma_swarm/issues/1277#issuecomment-5329857722));
verdict detail #1388 [issuecomment-5329612518](https://github.com/AIKAGRYA/dharma_swarm/issues/1388#issuecomment-5329612518);
evidence `reports/wayfinder/research/living_graph_round2_2026-08-18.md` @ `29a1e9bdd`.

**The SHAPE is locked; the engine stays swappable by design.** The substrate dichotomy
was false — **the ledger already exists**.

**(L1) Immutable ledger** = the estate's **EXISTING** `~/.dharma/state/runtime.db`
(529 MB WAL SQLite on the live dispatch path — 144,679 `runtime_receipts`, 116,216 FTS5
`session_events`) **+ the hash-chained receipt log**
(`~/.dharma/witness/claim_evidence_receipts.jsonl`). Repaired via **six wiring items**:

1. Monotonic offsets + tail cursor.
2. `execution_identities` backfill (18%→100%) + recursive-CTE walker.
3. Cost/token population on the write path (0.4%→~100%).
4. Wire the three zero-row tables — `artifact_links`, `memory_edges`, `retrieval_log`.
5. Enable `graph/persistence.py`.
6. DSSE signing + file-touch refs on dispatch receipts.

Plus **Litestream off-box custody** per the same spec.

**Ownership (hard):** all six are built **through the `dharmagraph-engine` track**. Its
phased spec (`docs/plans/DHARMAGRAPH_PHASED_SPEC_2026-07-05.md`) **§5 forbids building a
new truth store of any kind** — **no unilateral Helm-side edits**. Coordinate.

**(L2) Living projection** = a **rebuildable bi-temporal graph above the ledger**
(Graphiti pattern): incremental ingest + entity resolution; **supersession, never
deletion**; background consolidation; provenance-to-episode; fully re-projectable.
**Roles never merge: the ledger is never mutated; the graph is never trusted over its
log.**

**Fleet clause (amended after operator challenge — verbatim: *"but we already have 3 vps
that are writers..."*).** The fleet **already runs per-node ledgers** — live probe
receipts 2026-08-18: meghadharma `~/.dharma/state/runtime.db` 580K (last write Aug 11),
agni 476K (last write Jul 25), trishula unreachable by ssh alias at probe time. **No host
writes another host's store**, so SQLite's per-file single-writer limit is not violated
and the fleet's existence does **not** fire the Postgres trigger. What the fleet adds:
a **hub merge projection** — the Mac (hub; NAT permits Mac→VPS pulls only) pulls VPS
ledger segments and merges them into the Helm's query surface, ordered at merge time by
causation ids + timestamps, so "every interaction in the swarm" spans all hosts. Per-node
ledgers stay append-only and locally verifiable (hash chains per node). Recorded
observation: VPS ledgers are near-silent — the merged graph will be Mac-heavy until fleet
write paths wake.

**Re-worded tripwires:**
- **Postgres** (it would live on megha, the only all-reachable host) fires **only** if
  hosts ever need **SYNCHRONOUS writes to one shared store** — global transactions /
  global consistency. **Never** from the mere existence of per-node writers.
- **XTDB evaluation** fires only if **routine retroactive re-grading** becomes real
  (unchanged).
- **Quine sidecar** = radar option for standing pattern alerts; holds no truth.

**⚠️ Prerequisite repair — binding.** The `runtime_receipts` **write-path stall since
2026-08-15** (defect **#1391**) is **repaired before any Helm build against the ledger**.
It rides the DharmaGraph END-TO-END campaign; it is not Helm-track work.

---

## 3. Locked implementation obligations 1–7

Source: #1277 "Locked implementation obligations (not fog — no decision tickets; enter
/to-spec)". These are **mandatory consequences** of the closed aliveness + chassis
decisions. **Do not re-grill; do not treat as optional.**

**1. Pool registration** for required on-call seats — Fable 5 → GPT 5.6 → Grok 4.5/4.6
lineage → Fugu Ultra → Kimi K3 → Opus 5.0 → Opus 4.8 — with **canonical logical ids /
routes**.

**2. Fresh verification receipts (TTL 24h)** — on-call means **verified within 24h**,
never "online now", never key-only or `live_routable`-only.

**3. N/7 on-call chrome** projecting **verified count + ages**; **degraded banner** when
under floor.

**4. Evaluator-hard promotions** — invalid claim→verified paths must be **impossible in
code**, not UI-discouraged.
*Named code debt:* the bridge maps `live_routable` → route `ready`
(`dharma_swarm/terminal_bridge.py:1733`, verified present on `origin/main` at assembly
time); surface authority is **six booleans without owner/time/expiry**
(`terminal/src/types.ts:448` `SurfaceAuthorityState`).

**5. RouteVerification-shaped evidence** — `logical_seat, canonical_lineage, route,
served_identity, observed_at, expires_at, receipt_ref, result`; **OnCall only if**
`result = ok ∧ now < expires_at ∧ identity match ∧ non-synthetic`.

**6. Freshness dimensions separate from lifecycle** — `simulation / cache / stale / fresh
/ unknown / clock_skew`. **Future timestamps must not count as fresh.**
*Named code debt:* `terminal/src/freshness.ts` today treats future as fresh.

**7. S2 + S3 of the self-awareness contract** (added 2026-08-18 by the Slices ruling,
#1386) — **owner projection envelopes** for MissionControl / TaskBoard / RuntimeState /
Swarm / A2A / evolution with explicit **freshness / divergence / unknown**, bound to the
**six organism regions**, with **mocks removed**.
*Named code debt:* `terminal/src/mockContent.ts` **boot-theater dies in leg one** — it
seeds placeholder tabs at boot, and boot chrome can read as organism truth if authority
flags are ignored.
**S4 (recursive Inspector) + S5 (Inspector presentation) are explicitly excluded** — they
are the **first post-ship ratchet**, built later under the locked zen-depth grammar.
Sub-ruling: the prove-alive journey requires **no self-attestation** beyond S1 custody
landing with the stack.

---

## 4. Bound forge clauses and explicit deferrals

Source: closing ruling 4
([issuecomment-5330445451](https://github.com/AIKAGRYA/dharma_swarm/issues/1277#issuecomment-5330445451));
clause texts from the frontier scan report §Lane F ("Most valuable unadopted forge
clauses"), citing `~/dharma_tui_reverse_spec_20260804/master_forge_spec/MASTER_FORGE_SPEC.md`.
The master-forge package remains **evidence/inspiration only**; only the three clauses
below are bound by the ruling.

### 4.1 Bound — three clauses

**A. Protocol v2 envelope** (`MASTER_FORGE_SPEC.md:733-759`) — `schema_version`,
`correlation_id` / `causation_id` / `parent_id`, monotonic sequence, attachment digest;
**the same golden vectors tested in TS and Python**.

**B. Owner adapter declaration contract** (`:780-795`) — every owner adapter declares its
**freshness clock**, its **partial / stale / unavailable semantics**, a **deterministic
fixture**, and **no side effects on read**.

**C. 400-line ratchet on new-and-touched code** (`:687-713`; enforcement script
`terminal/scripts/ratchet.sh:9-19`, present on `origin/main`) — **monotonic descent**.
Scope as ruled: **new and touched** code, not a whole-tree rewrite. (Measured starting
condition, frontier report §Lane F: `app.tsx` 151 KB, `protocol.ts` 150 KB,
`Sidebar.tsx` 113 KB, `RepoPane.tsx` 102 KB — the ratchet is nowhere near met today.)

**D. Performance budgets** — already bound via §2.5 (ruling 4: "performance budgets
already bound").

### 4.2 Deferred — explicitly out of leg one

| Clause | Where it goes | Ruling |
|---|---|---|
| **Consequence Shoreline** (pre-effect boundary card) | **Leg three** | closing ruling 4 |
| **Crash-boundary honesty** | **Leg three** | closing ruling 4 |
| **Non-recursive permit carve-out** | **Leg three** | closing ruling 4 |
| **IntentPlan compilation** | **Leg three** | closing ruling 4 |
| **Context Mirror** (bounded inspectable per-turn bundle + omissions ledger) | **Leg-1.5 radar** | closing ruling 4 |
| **Deterministic graph viewport** | **Living-graph merge layer** | closing ruling 4 |

---

## 5. Sequencing

Source: #1385 resolution
[issuecomment-5329611894](https://github.com/AIKAGRYA/dharma_swarm/issues/1385#issuecomment-5329611894);
closing ruling 3; #1277 Notes "Territory note (2026-08-18)"; handoff packet §Hard
constraints.

### 5.1 Ship lane

**The stack ships.** Ship lane = the 5-deep draft stack, in order:

**#1324 → #1327 → #1341 → #1349 → #1382** (tip `25c2a5409`, Slice-1 HelmContextEnvelope
custody).

Operator's ratified option text, verbatim:

> The merge-shape stack #1324→#1382 is the ship lane: rebase onto current main after parents land, rerun all gates, land slice by slice. The seat 74b2370a1 becomes the dual-run instrument — you keep sitting in it daily until the stack proves itself live, then it's archived as evidence. Honors the locked chassis decision; costs rebase work against moving main.

- **Parents land by the operator's hand only.** No merge is authorized by any ruling on
  this map; **the merge arm stays operator-only**.
- **Rebase trigger = parents landing** — the event, not a calendar date.
- **Verification = full gate rerun**, per the Nihonga whole-system Helm PR's own text.
- Land **slice by slice**.

### 5.2 Dual-run and cutover

- **Seat `74b2370a1`** (tmux `dharma_nihonga_helm`) = the operator's **daily instrument**;
  he keeps sitting in it **until the stack proves itself live**.
- The stack is **previewed** (e.g. `helm-ahab-preview`) but carries **no daily-driver
  duty** until it goes live.
- **Cutover = the moment the stack's shipped Helm meets the leg-one alive bar** — its own
  **verifiable event**, not a vibe.
- After cutover the seat is **archived as evidence — never merged**.

### 5.3 Implementation ticket ONE — Ink 5.1 → 7 migration

**Closing ruling 3 fixes this as the first implementation ticket of leg one.**

- **Position:** **after** the stack rebases onto current main, **before** S2/S3.
- **Golden frames re-gold once** (one authorized re-gold for the migration).
- **Alt-screen mode available to every slice** thereafter.
- **Starting point (measured):** `terminal/package.json` declares `"ink": "^5.1.0"` on
  `origin/main`; current upstream Ink is 7.1.1 (npm 2026-07-16). Ink 7.0.0 (2026-04-08)
  added the fullscreen-cockpit toolkit — `alternateScreen`, `useWindowSize`, `usePaste`,
  `useAnimation`, `useBoxMetrics`, `suspendTerminal()`, hard wrapping (frontier report
  §Lane A(c), §Lane E(c)).
- **Entailed by the ruling, not a new decision:** Ink 7 requires **React ≥19.2 and Node
  ≥22** (frontier report §Lane A(c)); the Helm runs **React 18.3.1** (§Lane F). The React
  major upgrade therefore sits inside ticket one — Ink 7 cannot land without it.

### 5.4 Order after ticket one

Per the handoff packet and #1386: **S2** (owner projection envelopes) → **S3** (organism
views, `mockContent.ts` boot-theater dies) → the remaining obligations (pool registration,
24h receipts, N/7 chrome, evaluator-hard promotions, RouteVerification evidence, freshness
dimensions). Cutting these into tickets is `/to-tickets` work, not this document's.

### 5.5 Build-lane prerequisites outside this spec

1. **Five parent draft merges** #1324 → #1327 → #1341 → #1349 → #1382 — **operator's hand
   only**.
2. **#1391** — `runtime_receipts` write-path stall repair; rides the **DharmaGraph
   END-TO-END campaign**; **precedes any Helm build against the ledger** (§2.9).
3. **Ownership boundary:** `terminal/**` = helm track
   (`helm-worldclass-terminal-2026-06`). Ledger repairs = `dharmagraph-engine-2026-07`
   track territory — coordinate, **never unilateral**.

---

## 6. Testing decisions and gates

Restatement only — every line below is already ruled elsewhere in this document.

| Gate | Binding rule | Source |
|---|---|---|
| **Definition of done** | The alive bar, nothing else | §8 |
| **Rebase gate** | Full gate rerun after the stack rebases onto then-current main | §5.1 |
| **Ink migration gate** | Golden frames re-gold **once**; alt-screen available to every slice | §5.3 |
| **Speed gate** | Lane A table (§2.5) inside the forge outer budgets | §2.5 |
| **Evaluator gate** | Invalid claim→verified promotions impossible **in code** | §3 obligation 4 |
| **Freshness gate** | Future timestamps → `UNKNOWN`/`CLOCK_SKEW`, never fresh | §2.4, §3 obligation 6 |
| **Mock-death gate** | `mockContent.ts` boot theater removed; organism views bound to real owners | §3 obligation 7 |
| **Protocol gate** | Same Protocol v2 golden vectors pass in **both** TS and Python | §4.1 A |
| **Adapter gate** | Every owner adapter ships a deterministic fixture and takes no side effects on read | §4.1 B |
| **Size gate** | 400-line ratchet on new-and-touched code, monotonic descent | §4.1 C |
| **Post-ship richness gate** | Any visual richness beyond locked tokens must pay the **20%-over-control deletion threshold** | §7.1 |
| **Efficiency-claim gate** | No token-per-token efficiency claim without the preregistered two-arm protocol | §2.6 |
| **Runtime-verification law** | Typecheck / green CI alone is never "done" — runtime verification required | handoff packet §Your first three moves (software-factory law) |

---

## 7. Scope guards

### 7.1 Closing rulings 1 and 2 — what leg one deliberately does not get

Source: [issuecomment-5330445451](https://github.com/AIKAGRYA/dharma_swarm/issues/1277#issuecomment-5330445451).

**Ruling 1 — Council UX is OUT of leg one.** Primary seat + truthful N/7 bench only.
Council orchestration UX (specialist panels, verdict views) is **post-ship**, unlocked
when council runs are real organism events.

**Ruling 2 — Visual depth at first ship = locked tokens only.** Palette, composition
breakpoints, honesty chrome, zen-depth grammar, accessibility law — **as already locked**.
**All richness = post-ship ratchet paying the 20%-over-control deletion threshold.**

### 7.2 Out of scope (from the map)

- Multi-renderer chassis mashup (Ink + Bubble Tea + Ratatui + OpenTUI in one process)
- Shipping the fixture playground as the product
- Binding the full master-forge phase 0–10 backlog as the plan
- Aesthetic-only rewrites without a live seat
- Dashboard / web as the primary surface for this epic
- Full A2A mesh and full evolution/RSI cockpit for first ship
- Multi-human operator design for slice 1

### 7.3 Beyond this map — do not re-import this fog

Source: #1277 "Beyond this map (future maps, not this effort — preserved from fog at
clearing)".

- **Leg two — seat = tip unification.** The Helm the operator sits in and the evolved tip
  become one self-updating object under the truth contract. Charts as its own map after
  leg one ships and **cutover completes**.
- **Leg three — the governed hand.** First workspace/runtime mutation path, gated on
  **RUDRA R0 trusted join** + one-shot permit / credential-isolated actuator. The
  operator's 2026-08-18 words make the hand **destination-core**; emphasis raised, **gate
  unchanged**. The forge hand-clauses re-enter here.
- **Later radar.** Codex OSS pattern harvest · Rust/native worker earn-in · OpenTUI vs Ink
  re-eval after slice-1 alive (Ink 7 ruled first) · Bubble Tea / Ratatui inspiration-only
  · Context Mirror (leg-1.5 seat transparency) · deterministic graph viewport (rides the
  living-graph merge) · S4 + S5 recursive Inspector (first post-ship ratchet) · council
  orchestration UX (post-ship) · visual richness beyond tokens (post-ship ratchet,
  20%-over-control threshold) · seat-efficiency experiment (preregistered protocol) ·
  Quine sidecar (standing alerts) · XTDB evaluation (bitemporal tripwire).

**Rule (from the map's clearing):** new fog discovered during `/to-spec` or build
**re-opens as fresh child tickets on #1277** — nothing resurrects silently, nothing is
decided in place.

---

## 8. Definition of done

**Leg one is done when the alive bar is met — nothing else counts as done.**
(#1279 resolution; #1277 Notes "Alive bar (locked)"; handoff packet §What "done" means.)

Primary orchestrator + **7/7 verified on-call** logical models (24h TTL, fixed order
Fable 5 → GPT 5.6 → Grok 4.5/4.6 → Fugu Ultra → Kimi K3 → Opus 5.0 → Opus 4.8) · honest
read-only organism view (S2 + S3 live, mocks dead) · truthful **N/7** chrome with degraded
banner · the **prove-alive 10-minute journey** · the speed bar (key→glyph ≤50 ms p95,
`<Static>` flood law, cold start ≤150 ms, zero tearing) · **zero fake-live claims**.

**Under 7 verified = degraded, NOT ship-alive.**

**The truth-contract line, standing over everything above:**
**no fake-live, and no claimed-done without a verifier.** On-call means a **verified
receipt ≤24h** — never key-presence, never `live_routable`. Any path where the operator
can take a consequential action, or believe a loop / fang / on-call / done, **on narration
alone** is a **ship-blocker kill**.

---

## 9. Ownership and workspace rules carried into build

Source: handoff packet `~/handoffs/2026-08-19_helm_legone_build_handoff.md` §Hard
constraints (itself derived from the map's rulings).

- **Merges are OPERATOR-ONLY.** Everything produced under this spec is a **draft PR**.
- **`terminal/**` = helm track.** Living-graph ledger repairs = **dharmagraph-engine
  track**; coordinate, never unilateral; **no new truth store** (spec §5).
- **Citation-or-silence** — `file:line` or a runnable command on every claim.
- **Runtime receipts never enter git.**
- **Isolated fresh worktrees only** — the main checkout is dirty on a vision branch;
  never build there.
- **Do not touch the operator's seat** — tmux `dharma_nihonga_helm` @ `74b2370a1`
  dual-runs until cutover.
- **Known trap:** fresh-worktree pre-commit hooks fall back to system python3.9 and fail
  falsely — commit with `PATH="$HOME/dharma_swarm/.venv/bin:$PATH"`. **Never
  `--no-verify`.**
- **Build discipline:** software-factory lanes — **name the verifier before writing
  code**; vertical slices; negative controls; **runtime verification** (typecheck or green
  CI alone is never "done").

---

## 10. OPEN-QUESTION (child ticket needed)

Assembly surfaced exactly one point that the ratified sources do not settle. **It is not
resolved here.** Per the map's clearing rule it re-opens as a fresh child ticket on #1277.
**Filed as child ticket [#1400](https://github.com/AIKAGRYA/dharma_swarm/issues/1400).**

**OPEN-QUESTION 1 — Where do leg-one RouteVerification receipts live, and does that make
#1391 a hard blocker for the whole leg?**

- Obligation 2 requires fresh verification receipts (TTL 24h); obligation 5 gives
  `RouteVerification` a `receipt_ref` — **neither names the store** (#1280 resolution;
  #1277 obligations 2 and 5).
- The living-graph lock names the ledger as the existing `runtime.db` + hash-chained
  witness log and **forbids new truth stores** (§2.9, DharmaGraph spec §5).
- The frontier scan measured that the Helm writes **no receipt at all** today:
  `terminal_bridge.py:106` → `~/.dharma/terminal/` persists only `working_memory.json`
  (3.1 K, rolling last-8 turns) — "no request/response log, no receipt, no correlation id
  … the least-instrumented organ in the estate" (living-graph round-2 report §Lane I.5,
  `living_graph_round2_2026-08-18.md` @ `29a1e9bdd`).
- The map states the prerequisite as conditional: **#1391 is repaired "before any Helm
  build on the ledger."**

**The undecided point:** if leg-one verification receipts are written to / read from
`~/.dharma/state/runtime.db`, then **#1391 blocks the entire leg**, and receipt custody
belongs to the dharmagraph-engine track. If they may live in a Helm-local receipt surface,
that surface's relationship to spec §5 ("no new truth store") needs an explicit ruling.
**Operator ruling required — do not choose during `/to-tickets` or build.**

---

## 11. References

**Ratified (binding):**
- [Wayfinder MAP: first shippable live Dharma Helm #1277](https://github.com/AIKAGRYA/dharma_swarm/issues/1277) — CLEARED 2026-08-19, 100/100. Body: Destination, Notes/locks, Decisions index, obligations 1–7, Out of scope, Beyond this map.
- Closing rulings — [issuecomment-5330445451](https://github.com/AIKAGRYA/dharma_swarm/issues/1277#issuecomment-5330445451).
- Destination in his own words + append law — [issuecomment-5328869849](https://github.com/AIKAGRYA/dharma_swarm/issues/1277#issuecomment-5328869849).
- Frontier locks — [issuecomment-5329454472](https://github.com/AIKAGRYA/dharma_swarm/issues/1277#issuecomment-5329454472).
- Living-graph lock + fleet amendment — [issuecomment-5329825138](https://github.com/AIKAGRYA/dharma_swarm/issues/1277#issuecomment-5329825138), [issuecomment-5329857722](https://github.com/AIKAGRYA/dharma_swarm/issues/1277#issuecomment-5329857722).
- [#1279 aliveness bar](https://github.com/AIKAGRYA/dharma_swarm/issues/1279) · [#1280 truth contract](https://github.com/AIKAGRYA/dharma_swarm/issues/1280) · [#1281 chassis](https://github.com/AIKAGRYA/dharma_swarm/issues/1281) · [#1385 tree/cutover](https://github.com/AIKAGRYA/dharma_swarm/issues/1385) · [#1386 Slices 2–5](https://github.com/AIKAGRYA/dharma_swarm/issues/1386) · [#1388 living graph round 2](https://github.com/AIKAGRYA/dharma_swarm/issues/1388).
- Defect [#1391](https://github.com/AIKAGRYA/dharma_swarm/issues/1391) — `runtime_receipts` write-path stall (prerequisite repair).

**Research (sourced evidence behind the locks):**
- `reports/wayfinder/research/badass_terminal_frontier_scan_2026-08-18.md` @ `84ec2ea4c`, branch `research/badass-terminal-frontier-scan-20260818` — Lanes A–F; per-claim URLs fetched 2026-08-18; UNVERIFIED markers preserved.
- `reports/wayfinder/research/living_graph_round2_2026-08-18.md` @ `29a1e9bdd`, same branch — Lanes G–I; internal lane verified against `origin/main`.
- `reports/wayfinder/research/chassis_candidate_inventory_first_live_helm.md`, branch `research/chassis-candidate-inventory-first-live-helm` (ticket #1278).
- `reports/wayfinder/research/terminal_chassis_and_bleeding_edge_tui_2026-08-06.md` (ticket #1281).

**Reference only — binds nothing:**
- **Nihonga Helm Frontier Master Active-Spec — `status: CANDIDATE_NOT_ADMITTED`**:
  `docs/plans/nihonga_helm_frontier/NIHONGA_HELM_FRONTIER_MASTER_SPEC.md` (706 lines,
  `prepared_at: 2026-08-15`), reachable at `25c2a5409` on the stack tree. It is **cited,
  never bound**: closing ruling 5 keeps it `CANDIDATE`, and **admission is earned later,
  slice by slice, as slices land**. Its own §0 states no replacement has occurred until
  admission. Useful reference sections: §3.2 five places and composition breakpoints;
  §4.1 the 20 named palette tokens; §5.1–5.2 / §7.2 `Claim<…>` construction boundary and
  the seven-seat `N/7` roster; §6.1 the six organism regions with the seven-state honesty
  set; §10 the S1–S5 slice ladder; §12.2/§12.4 the gate list including the
  20%-over-control deletion threshold.
- `~/dharma_tui_reverse_spec_20260804/master_forge_spec/` — evidence/inspiration only;
  **only** the three clauses in §4.1 are bound (closing ruling 4).
- `~/dharma_helm_playground_20260806` — reference prototype; not the ship path.
- Build handoff packet: `~/handoffs/2026-08-19_helm_legone_build_handoff.md`.

---

*Assembled 2026-08-19 by Fable (spec-assembly lane) as the `/to-spec` collapse of cleared
map #1277. This document decides nothing; it assembles ratified rulings. New decisions
re-open as fresh child tickets on #1277 — nothing resurrects silently.*
