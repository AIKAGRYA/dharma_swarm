---
title: Blueprint for Elegance — Re-Wiring Strategy
path: docs/plans/BLUEPRINT_FOR_ELEGANCE_2026-07-03.md
slug: blueprint-for-elegance-2026-07-03
doc_type: blueprint
status: active
summary: >-
  Target structural architecture and incremental re-wiring roadmap derived
  from the 2026-07-03 anti-slop audit: one-owner-many-projections doctrine,
  wire-or-retire for aspirational standards, four delta-gates that close the
  enforcement gaps, and self-reinforcing cleanliness loops — all sized
  against governance rent.
source:
  provenance: repo_local
  kind: blueprint
  origin_signals:
    - docs/plans/ANTI_SLOP_ARCHITECTURE_AUDIT_2026-07-03.md
    - docs/plans/FABLE5_CAMPAIGN_ROADMAP_2026-07-03.md
    - docs/governance/hygiene/ratchet_baselines.json
  cited_urls: []
  generated_hint: agent_authored_repo_doc
disciplines:
  - software_architecture
  - operations
  - knowledge_management
connected_relevant_files:
  - docs/plans/ANTI_SLOP_ARCHITECTURE_AUDIT_2026-07-03.md
  - scripts/governance/hygiene/ratchet_counters.py
  - scripts/docops/check_docops_integrity.py
  - .github/workflows/structure.yml
---

# Blueprint for Elegance — 2026-07-03

**Role:** the re-wiring design that converts the audit's findings into a
small, sequenced set of structural moves. Deliberately **not** a campaign
plan (the Fable-5 roadmap owns that) and **not** new governance machinery
(BR-022's warning stands): every move below extends an existing owner —
docops, the ratchet, structure.yml — or retires a dead promise.
**Rule:** ACTIVE_TRACK.yaml owns admission; nothing here is admitted work
until a track item cites it. If a move conflicts with a track's non-goals,
the track wins.

---

## 1. Target state: three doctrines

**D-A · One owner, many projections.** Every fact lives in exactly one
owner surface (code, a receipt, a YAML the tooling renders from). Anything
else that states the fact is a *projection* and must be either (a) generated
by a script, or (b) carry `last_synced` + fall under a freshness gate. A
hand-edited copy with neither is a defect, not a doc. (This is already the
repo's implicit doctrine — onboarding, trust gates, and the codex audit all
say "projection, not authority." The blueprint just extends it to the two
surfaces that escaped: the mismatch YAML and dated-count prose.)

**D-B · Wire or retire.** A declared standard must name its enforcing
mechanism and that mechanism must exist. If it can't earn a gate (or a
scheduled advisory report), the standard doc moves to `_archive/` — an
archived aspiration is honest; a live dead standard is slop that trains
agents to ignore all standards.

**D-C · Delta-gates over mandates.** New enforcement applies to *new or
touched* material only; existing debt is held by ratchet, never by blanket
rule. This is the Transcendence Principle's governance-cost clause made
structural: light System-2 damping, no retroactive System-3 mandates.

## 2. The wiring moves

Ordered by leverage ÷ risk. Each names its owner mechanism, acceptance
criterion (existing instruments only), and cost note.

### W1 — Projection-freshness gate (kills the F1 drift class)
**Extend:** `scripts/docops/check_docops_integrity.py` (it already does TTL
staleness as hard FAIL for `assertions.yaml` docs).
**Move:** register machine-projection files (`docs/interface_mismatches.yaml`
first) in the docops assertion config with a `last_synced` TTL (45 days,
matching the ratchet-baseline age gate). Stale projection → same FAIL path
as a stale doc.
**Accept:** letting `last_synced` age past TTL fails `docops.yml` on PR.
**Cost:** near-zero — reuses an existing hard gate; no new workflow.

### W2 — Frontmatter: retire the dead standard, gate the real one
**Reality:** the `pkm-phd-stigmergy-v1` normalizer is deleted; adoption
regressed to ~29%. Re-imposing it on 1,300 files would be a System-3
mandate with real diversity cost and no consumer that needs it.
**Move (two honest halves):**
1. Archive `docs/plans/2026-04-02-frontmatter-alignment-map.md` with a
   header stating the normalizer no longer exists (D-B: retire).
2. Add a **delta-gate** in docops: new `.md` files under `docs/governance/`,
   `docs/plans/`, `docs/architecture/` (the directories agents actually
   navigate by metadata) must carry minimal frontmatter
   (`title/doc_type/status/summary`). Everything existing is grandfathered;
   other directories stay free.
**Accept:** a new un-fronted file in a governed dir fails `docops.yml`;
`frontmatter_doc_count` becomes a ratchet counter (UP) so adoption can only
rise.
**Cost:** small; scoped to 3 dirs, new files only.

### W3 — Close the 500/1000 gap for new files only
**Extend:** `scripts/governance/check_module_budget.py` (`LINE_BUDGET`).
**Move:** newly-added `dharma_swarm/` modules gate at **500** (the law
CLAUDE.md already states); grandfathered files keep the current 1000/+10%
treatment; the aggregate ratchet keeps holding the 207-file debt DOWN.
**Accept:** a new 600-line module fails `module-budget.yml`; no
grandfathered file newly fails.
**Cost:** near-zero; aligns the gate with the already-declared law. God-object
*reduction* stays campaign-owned (roadmap C-3) — this only stops new debt.

### W4 — Root placement beyond markdown
**Extend:** `structure.yml` Rule 8 (same diff-filter=A pattern).
**Move:** block **any** new root-level file outside an allowlist seeded with
the current root inventory (all existing files grandfathered by
construction). Pair it with a short `docs/ops/` migration recipe for the
deferred executable moves (`run_overnight.sh` cluster → `scripts/daemons/`,
`nginx.conf` → deploy dir) that the **operator** runs on the machines whose
launchd/cron paths would break — the repo-side `git mv` lands only in the
same change as the operator's path update.
**Accept:** CI blocks a new root file; allowlist file count only shrinks
(ratchet counter `root_allowlist_entries`, DOWN).
**Cost:** small; one workflow edit + one recipe doc.

### W5 — Dormant-directory disposition (operator-gated)
**Move:** present the 11 orphan dirs (audit F5) to the operator with three
verdicts available per dir: ARCHIVE (move under `docs/_archive/` or
`spinouts/` with a dated README), ADOPT (an active track claims it in
`owned_surfaces:`), or DELETE (compost the listing to
`~/.claude/cabinet/_compost/` first, per the worktree-budget protocol).
Resolve the `roaming_mailbox/` top-level-vs-package ambiguity while there.
**Accept:** every top-level dir is either referenced by code/Makefile, owned
by a track, or archived — verifiable by re-running the audit's sweep.
**Cost:** zero runtime risk (all zero-reference), but judgment is the
operator's: seeds are not slop.

### W6 — Memory front-door boundary ratchet
**Extend:** `scripts/governance/hygiene/ratchet_counters.py`.
**Move:** add counter `legacy_memory_direct_imports` (DOWN, baseline 8) —
production modules importing `memory_palace`/`memory_lattice` directly
instead of via `memory_kernel`. New code can't widen the bypass; the D2
spec-first work (organism-rewire item 6) drains the 8.
**Accept:** counter in `ratchet_baselines.json`, held by `quality-ratchet.yml`.
**Cost:** near-zero; measurement only. Respects the rewire track's surface
ownership — the *migration* stays theirs (D2), only the no-new-bypass floor
is added, mirroring how `spine_bypass_entries` worked.

### W7 — One archive convention
**Move:** fold `docs/archive/` into `docs/_archive/2026-03/` (its content
era), update inbound links, leave a one-line pointer README. Mechanical,
wide, zero semantic risk — a good bot-PR.
**Accept:** `docs/archive/` contains only the pointer README; docops link
guards green.

### W8 — Wire the Pramāṇa Probe as a scheduled advisory (not a gate)
**Extend:** the existing weekly governance cron family in
`.github/workflows/`.
**Move:** run `docs/stop-the-slop/probe/probe.py` weekly, publishing its
report under `reports/governance/` the way ops reports already land. It
stays **advisory** — its detectors (god-objects, churn, phantom deps,
narrative comments) overlap ratcheted counters, so gating it would be
double governance rent. If, after a quarter, its signal adds nothing over
the ratchets: retire it (D-B cuts both ways).
**Accept:** a dated probe report appears weekly; zero new blocking checks.

## 3. Sequencing

```
now ──► W1 projection gate ─► W3 500-line delta ─► W4 root gate      [pure extensions, 1 PR each]
  └──► W2 frontmatter retire+delta (needs a canonical-dirs decision)
  └──► W6 memory boundary counter (coordinate wording with organism-rewire D2)
W5 dormant dirs · W7 archive fold ── operator-gated / bot-PR, anytime
W8 probe cron ──────────────────── after W1–W4 land (avoid gate-noise overlap)
```

Nothing above opens a new track: W1–W4, W6–W8 are single-PR extensions of
surfaces owned by the governance/hygiene tooling; W5 is an operator
decision packet. If the operator wants them tracked, they fit as next-items
on existing tracks rather than new admission.

## 4. Self-reinforcing loops (why this stays clean)

- **Ratchets make cleanliness monotonic** (W2/W4/W6 add counters): once a
  number improves, CI holds it. No willpower required.
- **Freshness gates make drift loud** (W1): a projection that stops being
  maintained becomes a red PR check, not a silent lie.
- **Wire-or-retire keeps the standard set small and true** (W2/W8): the set
  of declared standards converges on the set of enforced ones — antifragile
  to future generated content because every new "standard" doc must
  immediately answer "what enforces you?"
- **Delta-gates preserve diversity**: nothing retroactive, nothing blanket;
  the governance cost of each move is one CI check on new material.

## 5. On new agents and governance primitives: mostly, don't

The audit's F2 shows this repo's failure mode is not too few enforcement
agents — it is **promised agents that never ship** (Mismatch-Resolver, the
frontmatter normalizer). Recommendations:

1. **No standards-enforcement agent.** docops + ratchet + structure.yml are
   the standards enforcers; W1–W4 complete them. An agent here would be a
   new truth owner — forbidden by standing non-goals.
2. **No artifact-lifecycle agent.** The hygiene pattern lifecycle
   (`advisory → enforced/resolved` via `promote.py`) already is one; feed it
   instead (each audit finding class can become a pattern YAML).
3. **The one genuinely missing primitive is the projection registry** (W1):
   a list, inside docops config, of "files that claim to mirror another
   surface." That's a config stanza, not an agent.
4. **Retire dead promises explicitly** — the mismatch YAML now states its
   resolver never existed; do the same wherever a doc names a nonexistent
   tool (grep for the pattern during W2's archive pass).

## 6. Anti-goals

- No new governance mechanisms, truth stores, receipt systems, or naming
  schemes (standing doctrine; BR-022).
- No blanket retroactive standards — delta-gates and ratchets only.
- No touching sibling-track owned surfaces except through their next-items
  (W6 explicitly defers the memory migration to D2).
- No deleting operator-machine-coupled root executables from a cloud seat.
- No gating the Pramāṇa Probe — advisory or retirement, nothing between.
