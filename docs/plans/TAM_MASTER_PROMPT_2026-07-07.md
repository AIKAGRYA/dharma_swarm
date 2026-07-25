# TAM — Transdimensional Abundance Machine: forged master prompt (2026-07-07)

**Role:** agent-forged master prompt, ratification-PENDING. Produced at the
operator's request ("use the master-prompt-forge skill for this and feed it
back to me") to turn the operator's TAM seed into an execution-ready prompt
for a future build session. **These are NOT operator words** except the name
**TAM = Transdimensional Abundance Machine** (operator-supplied, 2026-07-07);
the metric design and wiring are agent-proposed and become doctrine only on
operator ratification.
**Authority:** subordinate to `docs/vision_maps/NORTH_STAR.md` (§5, §7, §8,
§11) and the honesty rule that competitor figures are source-pending until
receipted. This file owns no rules and no state until ratified.
**Method:** forged via the in-repo `master-prompt-forge` skill
(`docs/skills/master-prompt-forge/`) — repo-agent template + verbatim
workspace-hygiene block + quality-gate self-check. The skill is not installed
into `.claude/skills/` (so not invokable as a session Skill); its documented
contract was applied directly.
**Rule:** if this file disagrees with `make onboard`, `ACTIVE_TRACK.yaml`, or
any receipt, trust those.

---

## What TAM is, in one breath

The **Transdimensional Abundance Machine** is a live instrument — the same
shape as the Frontier Ledger and the DharmaGraph↔LangGraph differential
oracle — that answers one plain question continuously: **"How close are we to
being a verifiably BETTER Polsia / cofounder.co?"** Soul in the name; clarity
in the number. Its single legible output is the **Company-Builder Parity %**,
on a repo-wide capability board, with a history chain that shows whether the
gap is closing over time. It weaves into what we already built with zero new
mechanism — it clones `frontier_ledger.py`, reuses the row/velocity model,
and reads existing honest-status owners for its axes.

**The wedge (already documented, 2026-06 world-scan):** Polsia's own
claimed-vs-actual ARR gap is ~4.4× (`reports/anatomy_altitude_2026-06-10/
lane_F_world.md:35`). The autonomous-revenue category has no evidence layer.
A telos-gated engine that publishes third-party-verifiable receipted revenue
("honest ARR") exceeds on an axis incumbents structurally cannot follow —
because publishing real receipts would expose their gap. That is the headline
differentiator row on the board.

**Naming ledger (resolved):** TAM = Transdimensional Abundance Machine (the
organ). The existing *Total Addressable Market* usage in
`foundations/FIVE_FOURTEEN_A.md:49` is untouched; the Darshan work-packet dir
`reports/tam/` is untouched. The machine writes to `reports/governance/tam/`.

---

## THE FORGED MASTER PROMPT (copy-paste block)

```markdown
# MASTER PROMPT — TAM (Transdimensional Abundance Machine): the live "Company-Builder Parity" metric + board

## Role & target agent
Claude (fresh repo session, full tool access) on
AmitabhainArunachala/dharma_swarm. Operator = John / Dhyana holds all
ratification authority. Run `make onboard` FIRST and trust it over this
prompt. This is a governance-instrument build in the same idiom as the
Frontier Ledger you already shipped — reuse, do not reinvent.

## Goal
Build the **Transdimensional Abundance Machine (TAM)** — ONE
plain-language, always-re-runnable instrument that answers, on a repo-wide
board: **"How close are we to being a verifiably BETTER Polsia /
cofounder.co — as a single percentage and a per-capability Kanban?"** The
machine's name carries the telos (abundance across every dimension the
organism serves); its single legible output is deliberately plain — the
**Company-Builder Parity %**. Snapshot research already exists (2026-06
world-scan); turn it into a LIVE, digest-stamped, `--check`-replayable
instrument that weaves into the existing Frontier Ledger, and whose history
chain shows whether the gap is CLOSING over time. Phase 0 ships the
instrument + first honest render + a track proposal; no world-facing action.

## Inferred assumptions (correct any that are wrong)
- **Naming — RESOLVED by operator (2026-07-07): TAM = Transdimensional
  Abundance Machine** (the instrument/organ name). Its single headline
  output stays the plain **Company-Builder Parity %** (`parity_pct`) — soul
  in the name, clarity in the number. Do NOT overload the existing
  *Total Addressable Market* usage (`foundations/FIVE_FOURTEEN_A.md:49`);
  do NOT write into the Darshan-owned `reports/tam/` — the machine's
  surface is `reports/governance/tam/`.
- **Scope:** measurement only — afferent (read competitor PUBLIC data +
  our own honest status). Efferent-closed: no outreach, no publishing, no
  benchmarking claims. Consistent with chamber doctrine.
- **Home:** a NEW active track `company-builder-parity-2026-07` serving
  the uncovered spine objective `revenue-external-humans-served`,
  complementing `hyperbolic-time-chamber-2026-07`. If the operator prefers
  folding it into the chamber track, that's a one-line change — flag it,
  don't assume irreversibly.
- **Clarity over math:** the operator explicitly does NOT want fancy
  mathematical names. The headline is a percentage a non-engineer
  understands. Internal rigor (digests, replay) stays under the hood.

## Context the executing agent needs (verify every file:line before trusting)
- **The instrument to CLONE:** `scripts/governance/frontier_ledger.py` —
  reuse its `stable_digest`, `write_surface` (receipt.json + .md +
  history.jsonl triad), `check()` replay contract (seal recomputes, pinned
  input shas, markdown is a pure render, history chain intact + tip
  references receipt), and `render_markdown`. Build
  `scripts/governance/tam_ledger.py` as its sibling writing
  `reports/governance/tam/` (NOT `reports/tam/`, which is Darshan-owned).
- **Row / comparator model to REUSE:** `dharma_swarm/chamber/ledger_rows.py`
  — mirror `FIELD_COMPARATORS` (capability -> {value, unit, receipt};
  "only entries with a citation carry a number"), the
  `add(capability, ours, *, commensurable, note)` engine, and
  `capability_summary(rows)`. Here the "field" column is a NAMED COMPETITOR
  capability (Polsia / Cofounder), each cell citing a source URL or repo
  receipt — the commensurability rule (`score_c2` /
  `trust_gate_status.py`) applies: an unmeasured/uncited competitor cell
  renders UNKNOWN, never a guess.
- **Velocity (gap-closing over time):** `dharma_swarm/chamber/ledger_history.py`
  `append_history` / `compute_velocity` / `read_chain` — reuse verbatim so
  the board shows d(parity)/dt (are we catching up?).
- **Tri-color verdict + portfolio reader:** `scripts/governance/trust_gate_status.py`
  `verdict_for` (GREEN>=0.8 / AMBER>=0.4 / RED), `parse_cell_statuses`
  (reads `VENTURE_CELL_PORTFOLIO.yaml`). Reuse; do not re-implement.
- **CI digest gate:** `scripts/governance/check_track_status.py`
  `check_receipt_valid(..., expect_digest=True)`. Wire the track criterion
  by copying the shape of `arena_truth_receipt_valid` in `ACTIVE_TRACK.yaml`.
- **Capability axes (the rows) come from existing honest-status owners —
  read, don't duplicate:** `docs/governance/VENTURE_CELL_PORTFOLIO.yaml`
  (`cells[]` incl. `external_operator: cofounder.co ... supersedes Polsia`,
  line 82), `reports/swarm_genome/<latest>/SYNTHESIS.md` §Organ-Health
  table (Working/Semi-working/Aspirational vocabulary), NORTH_STAR §7 organ
  table, `ACTIVE_TRACK.yaml` `vital_signs.dimensions`.
- **The competitor facts (source-pending — carry that label):**
  `reports/anatomy_altitude_2026-06-10/lane_F_world.md` (Polsia :30-45,
  Cofounder :11-28) and `docs/research/AI_COMPANY_OPERATOR_GROUNDING_PACK_2026-06-12.md`
  (the exceed-vectors). Polsia's **4.4× claimed-vs-actual ARR gap
  (`:35`)** is the load-bearing wedge: the honest-ARR axis is where we
  structurally exceed — incumbents can't publish receipted revenue without
  exposing the gap. NORTH_STAR §5 flags these figures source-pending;
  preserve that honesty (cite URLs, mark unverified).
- **The Kanban render already exists and is generic:**
  `dashboard/src/components/operator-coherence/CoherenceKanban.tsx` renders
  any `KanbanLane[]` (`dashboard/src/lib/operatorCoherence.ts`). A repo-wide
  capability board = lanes as parity buckets ("Behind" / "At parity" /
  "Ahead" / "No competitor equivalent" / "Unmeasured"), cards = capabilities.
  The governance receipt (`reports/governance/tam/`) is the SOURCE OF TRUTH;
  the dashboard optionally reads its JSON. The one-page markdown table IS
  the board if no UI wiring is done in Phase 0.

<workspace-hygiene>
## Workspace hygiene (read this before touching anything)

Before making any change, gather the following — read-only, no writes:

- Repo root (`git rev-parse --show-toplevel`), current branch, and
  upstream tracking branch.
- `git worktree list` — is this checkout one of several worktrees on the
  same repo? Note any siblings.
- Dirty state: `git status --short` — count of modified/untracked files.
  If this count is large (dozens to hundreds), treat the tree as **user
  property to preserve**, not clutter to clean — see "Dirty-Worktree
  Quarantine Mode" below.
- Lockfiles present (`package-lock.json`, `pnpm-lock.yaml`, `poetry.lock`,
  `Cargo.lock`, `go.sum`, etc.) and which dependency manager they imply.
- Generated / vendor / cache directories (`node_modules/`, `dist/`,
  `build/`, `.venv/`, `__pycache__/`, `target/`, `.next/`) — do not
  descend into these for edits; do not "clean" them unless asked.
- The project's actual test/lint/build commands (check `Makefile`,
  `package.json` scripts, `pyproject.toml`, CI config) rather than
  assuming a generic `npm test` / `pytest` invocation.

**Forbidden by default** (only do these if the user explicitly asked for
this exact operation, and even then, confirm current state and flag the
risk first):

- `git reset --hard`, `git clean -f` / `-fdx`, `git checkout -- .`
- Force-push, rewriting published history, `--no-verify` / skipping hooks
- Mass reformatting or repo-wide auto-fix passes
- Dependency upgrades/downgrades not directly requested
- Deleting or moving files outside the stated scope of the task
- Mixing new agent-driven work into an already-chaotic worktree without
  the user's explicit go-ahead

## Dirty-Worktree Quarantine Mode

Trigger this posture whenever the workspace has a large number of
pre-existing uncommitted or unfamiliar changes that are **not** part of
the current task:

1. Do not touch, stash, or discard the existing changes. Inventory them
   (file count, rough categories, whether they look intentional or
   stale) and report the inventory before doing anything else.
2. Do the new work in a clean sibling worktree or fresh clone instead of
   inside the contaminated tree:
   `git worktree add -b <new-branch> <new-path> <commit-ish>`
   creates an isolated working tree and branch from a chosen commit
   without disturbing the original.
3. If the user wants the dirty tree cleaned up, that is a separate,
   explicit task — never bundle it into an unrelated feature/fix prompt.
4. If unsure whether uncommitted work is intentional, ask before treating
   it as disposable. It is not.
</workspace-hygiene>

## Constraints & non-goals
- Reuse the frontier-ledger mechanism; write NO new digest/receipt/chain
  primitives (import them). New logic is only the TAM row-set + the
  competitor comparator map.
- No new truth store; read existing owners (portfolio, genome, NORTH_STAR,
  active-track). The instrument is `authority: projection_only` — it owns
  no fact, exactly like `frontier_ledger.py` and `trust_gate_status.py`.
- Honesty is the product: every competitor number carries a source URL and
  a source-pending/verified label (NORTH_STAR §5 rule); every "ours" cell
  traces to a repo owner; unmeasured = UNKNOWN, never a flattering guess.
  The whole point vs Polsia is that our number is checkable.
- No efferent action (no outreach, publishing, benchmarking claims, PR to
  external repos). No gate/ratchet/One-Wire weakening. Files < 500 lines.
- Do NOT overload "TAM = Total Addressable Market"; do NOT write into
  `reports/tam/` (Darshan-owned) — use `reports/governance/tam/`.
- Do NOT touch sibling-track surfaces (`dharma_swarm/coordination/**`,
  `council/**`, arena reports) except through their own next-items.

## Deliverables
1. `scripts/governance/tam_ledger.py` — a frontier-ledger sibling:
   renders `reports/governance/tam/{tam_receipt.json (digest-stamped),
   COMPANY_BUILDER_PARITY.md (the board), tam_history.jsonl (velocity
   chain)}`; `--check` replays byte-for-byte or fails non-zero.
2. **The metric, plainly:** one headline `parity_pct` (0% = far below the
   Polsia/Cofounder capability baseline; 100% = at parity on everything
   they do; >100% = we exceed on axes they can't match — honest-ARR
   receipts, telos gates, fractal survival pressure). Plus a per-capability
   table: each row = a capability, columns = OURS status | COMPETITOR
   (Polsia/Cofounder) | parity bucket (Behind/At/Ahead/No-equivalent/
   Unmeasured) | source citations. The honest-ARR row is explicitly the
   headline differentiator.
3. First **honest render** committed (expect it to be sparse and mostly
   "Behind"/"Unmeasured" — that IS the day-one truth, like the Frontier
   Ledger's 4/13-measured first render; do not inflate it).
4. Draft `ACTIVE_TRACK.yaml` entry `company-builder-parity-2026-07`
   (serves `revenue-external-humans-served`) with a `tam_receipt_valid`
   (`expect_digest: true`) completion criterion + a `tam_ledger.py --check`
   `command_passes` criterion; run `render_active_track_includes.py`.
5. A short dossier `docs/plans/TAM_TRANSDIMENSIONAL_ABUNDANCE_MACHINE_<date>.md`:
   the machine's name + telos (Transdimensional Abundance Machine), the
   plain metric definition (Company-Builder Parity %), the axis list +
   where each "ours"/"competitor" value is sourced, the resolved naming
   (TAM = the organ; parity % = the number; the FIVE_FOURTEEN_A market-TAM
   and Darshan reports/tam/ left untouched), and the operator decision queue.
6. (Optional, only if time) wire a `KanbanLane[]` producer feeding the
   existing `CoherenceKanban.tsx` — else the markdown table is the board and
   this is a next-item.

## Evidence / verification discipline
- Every claim = a command run this session or a file:line read this
  session. Committed receipts are claims until replayed.
- Run and show: `python3 scripts/governance/tam_ledger.py` then
  `python3 scripts/governance/tam_ledger.py --check` (OK); the governance
  checker `check_receipt_valid(..., expect_digest=True)` passes on the
  receipt; `python3 -m pytest tests/test_tam_ledger.py -q` green (add
  tests mirroring the frontier-ledger tests: seal, replay, UNKNOWN honesty,
  velocity, competitor-cell-requires-citation).
- Every competitor number shows its source URL; every "ours" cell shows
  its repo owner; anything unverifiable renders UNKNOWN with the gap named.
- `check_track_status.py` reads the new track as rigorous (>=1
  receipt_valid/command_passes/test_passes criterion, no open blocker);
  hygiene delta-ratchet REGRESSIONS(0); boundary audit clean.

## Subagent / swarm strategy (proportionate)
Mostly single-pass (it's a clone of an existing instrument). Optionally one
research subagent to REFRESH the Polsia/Cofounder public capability facts
(their sites/pricing may have moved since 2026-06) with fresh source URLs
before the first render — afferent read only. One adversary check: can the
parity_pct be gamed to look higher than honest (e.g. by marking
Unmeasured rows as Ahead)? If so, fix before committing.

## Done when
- `tam_ledger.py` runs and `--check` replays green; the receipt passes the
  real governance checker with `expect_digest`.
- The board renders one clear headline `parity_pct` + a per-capability
  table with source citations and honest UNKNOWNs.
- The draft track entry + dossier exist; `render_active_track_includes.py
  --check` is clean; the naming decision and operator decision queue are
  explicit.
- Nothing efferent happened; no sibling surface touched; files < 500 lines;
  and a second render would populate velocity (gap-closing over time).
```

---

## Operator decision queue (for when this prompt is fed to a build session)
1. **Ratify** the metric design (Company-Builder Parity %) and the machine
   name TAM = Transdimensional Abundance Machine (done — naming resolved).
2. **Track placement:** new `company-builder-parity-2026-07` serving
   `revenue-external-humans-served` (recommended — finally covers the gap),
   OR fold into `hyperbolic-time-chamber-2026-07`.
3. **Competitor refresh:** approve the one afferent research subagent to
   re-pull Polsia/Cofounder public facts with fresh source URLs before the
   first render (their sites may have moved since 2026-06).
4. **Board surface:** markdown table only for Phase 0 (recommended), or wire
   `CoherenceKanban.tsx` now.
