---
title: Anti-Slop Architecture Audit & Sync Report
path: docs/plans/ANTI_SLOP_ARCHITECTURE_AUDIT_2026-07-03.md
slug: anti-slop-architecture-audit-2026-07-03
doc_type: audit_report
status: active
summary: >-
  Structural/hygiene audit of the whole repository (2026-07-03): what the
  anti-slop apparatus actually enforces vs aspires to, where truth-projection
  drift and duplication live, what was fixed this session with receipts, and
  what is deferred with reasons. Companion strategy doc:
  docs/plans/FABLE5_CAMPAIGN_ROADMAP_2026-07-03.md.
source:
  provenance: repo_local
  kind: audit
  origin_signals:
    - make onboard (2026-07-03, HEAD 4c4f5aa)
    - four parallel evidence sweeps (root staleness, docs duplication +
      frontmatter census, enforcement-infrastructure reality check,
      code drift + dormant directories)
    - scripts/governance/spine_bypass_report.py (fresh run)
    - scripts/governance/trust_gate_status.py (fresh run)
  cited_urls: []
  generated_hint: agent_authored_repo_doc
disciplines:
  - software_architecture
  - operations
  - knowledge_management
  - verification
connected_relevant_files:
  - docs/plans/FABLE5_CAMPAIGN_ROADMAP_2026-07-03.md
  - docs/plans/BLUEPRINT_FOR_ELEGANCE_2026-07-03.md
  - docs/governance/ANTI_SLOP_RULES.md
  - docs/interface_mismatches.yaml
  - INTERFACE_MISMATCH_MAP.md
---

# Anti-Slop Architecture Audit & Sync Report — 2026-07-03

**Role:** structural/hygiene audit record. The same-day
`FABLE5_CAMPAIGN_ROADMAP_2026-07-03.md` owns campaign strategy (what to build
next and why); this file owns the *structural* layer — duplication, drift,
enforcement reality, and the wiring that keeps future AI-generated content
from rotting the repo. The two are deliberately non-overlapping.
**Rule:** if this file disagrees with `make onboard`, a receipt, or the code,
trust those. Findings below carry their evidence inline so they can be
re-verified rather than believed.

---

## 1. What is genuinely healthy (anti-slop bearing fruit)

Credit before critique — the enforcement lattice here is denser than almost
any repo of this size, and most of it actually blocks:

- **13+ blocking PR gates**: tests (py3.11/3.12 + Go contracts + AST syntax
  sweep), one-way quality ratchet (45-day baseline freshness), hygiene delta
  ratchet (touched-file net-new violations), semgrep local rules (strict in
  CI), gitleaks (full history), structure Rules 8/9, test-hygiene, module
  budget, docops integrity (path guards, canonical guard, **TTL staleness as
  a hard FAIL**), plus 9 pre-commit uplift guards (kernel checksum, secrets,
  mismatch adjacency, spine ownership…).
- **The ratchet design is correct**: counters move one way, unmeasurable
  fails closed, `--tighten` adopts improvements only on green. Baselines in
  `docs/governance/hygiene/ratchet_baselines.json` currently hold
  `spine_bypass_entries=0`, `modules_over_500_lines=207` (DOWN),
  `silent_exception_swallows=244` (DOWN), `ruff_undefined_or_redefined=0`.
- **The canonical maps are alive, not decorative**: `INTERFACE_MISMATCH_MAP.md`
  x-rayed 2026-07-02; `CYBERNETIC_LOOP_MAP.md` audited 2026-07-02 by a
  read-only verifier with receipts; onboarding renders live track evidence
  with a trust-check banner that explicitly downgrades existence-only checks.
- **The root-drain stub pattern works**: 9 former root files are now 3-line
  pointer stubs to `docs/_archive/2026-04/` — moved without breaking inbound
  links. Spine bypass allowlist verified at **zero** this session (fresher
  than even the roadmap's snapshot of 4).
- **Honest claim boundaries are cultural**: HARNESS_PROVEN vs CLOSED_LIVE,
  "existence checks are not closure", `VERIFIED_SLICE` graduation language.
  This is the single strongest antibody the repo has.

## 2. Findings, prioritized

### F1 — The dominant slop mode is truth-projection drift, not junk files

Every serious rot instance found is a **hand-maintained shadow copy of a fact
owned elsewhere**:

- `docs/interface_mismatches.yaml`: `last_synced: 2026-05-06` (2 months
  behind its canonical MD map), 5 of 25 entries ever migrated, two entries
  marked `open` whose bugs were verifiably fixed in code
  (`auto_proposer.py:297`, `orchestrate_live.py:458`), and `test_path`
  fields pointing at a `tests/mismatches/` directory that **never existed**.
  A pre-commit guard (`mismatch_registry.py`) was consuming this stale data.
  *(Fixed this session — see §3.)*
- `CLAUDE.md` described `diversity_archive.py` as "unwired standalone,
  candidate for consolidation" five days after D6a consolidated it into a
  deprecated shim (#755). *(Fixed this session.)*
- `LIVING_LAYERS.md` cites `orchestrate_live.py` at "356 lines" (it is
  ~1,700+); the frontmatter alignment map claims 89.8% docs adoption while
  measured reality is ~29%.

**Why it matters:** the repo's own CLAUDE.md §"CRITICAL" says frozen counts
in prose "is exactly how this section rotted." The pattern generalizes: any
file with a `last_synced`/dated-count field and no renderer or freshness
gate WILL drift, and agents downstream consume the drift as truth. The
Blueprint's W1 makes this a rule with teeth.

### F2 — A stratum of aspirational apparatus: standards whose enforcing tool was never built (or was deleted)

- **Frontmatter standard**: `docs/plans/2026-04-02-frontmatter-alignment-map.md`
  defines `pkm-phd-stigmergy-v1` and names
  `scripts/normalize_markdown_frontmatter.rb` as the normalizer. **That
  script does not exist.** Measured adoption: docs/ ~29% (199/697), root 0%,
  foundations/ ~4%, reports/ ~11%. The only code touching frontmatter
  (`check_docops_integrity.py`) counts it advisorily, never gates.
- **Stop-the-Slop "Pramāṇa Probe"** (`docs/stop-the-slop/probe/`): real,
  self-tested code (god-object, churn, phantom-dep, narrative-comment
  scans) wired into **zero** workflows or hooks.
- **"Mismatch-Resolver agent"** promised in `interface_mismatches.yaml` to
  migrate the remaining 20 entries: never built.
- **HUMAN_YDS ledger**: spec + writer module exist; the CLI is listed under
  "Still Missing."

**Why it matters:** each of these is a *declared standard with no owner
mechanism* — the precise definition of performative anti-slop. They cost
credibility: an agent reading the alignment map would "enforce" a dead
standard. Each needs one of two honest fates: wire it or retire it (Blueprint
W2/W8).

### F3 — The enforcement lattice has four precise gaps

| Standard (as documented) | Reality | Evidence |
|---|---|---|
| 500-line file law (CLAUDE.md) | Hard PR gate is **1000** lines (`check_module_budget.py:56`); the 500 law is only ratcheted in aggregate (207 grandfathered; largest 5,255) | `module-budget.yml`, `ratchet_baselines.json` |
| "Never save to root" | Gated for **markdown only** (Rule 8); nothing blocks new root `.py`/`.sh`/`.json` | `structure.yml` |
| Frontmatter on docs | Counted, never enforced (`--counts-advisory`) | `docops.yml:44` |
| Duplicate detection | PR-title dedupe for bot PRs only; **no content-level duplicate detection** | `pr-dedupe.yml`, `pr-collision-detect.yml` |

### F4 — Live-vs-live duplicate documents with no declared canonical

- `docs/GINKO_ENHANCEMENT_WAVE.md` ↔ `docs/plans/GINKO_ENHANCEMENT_WAVE.md`:
  byte-identical bodies. *(Removed the non-canonical copy this session.)*
- `docs/SPRINT_GOTCHAS.md` (6,001B) ↔ `docs/plans/SPRINT_GOTCHAS.md` (8,692B):
  **divergent** — needs human reconcile, not blind merge.
- `docs/YOLO_4AM_TASKS.md` ↔ `docs/plans/YOLO_4AM_TASKS.md`: divergent.
- `RECURSIVE_READING_PROTOCOL.md` exists **3×** (docs/, docs/architecture/,
  plus the SWARM variant), all divergent.
- Two competing archive conventions: `docs/archive/` (flat, 2026-03 era)
  vs `docs/_archive/` (date-partitioned). Same basenames exist in both
  lineages.

### F5 — Eleven dormant-orphan top-level directories

All last touched by the single 2026-06-24 import commit, zero inbound
references from code, Makefile, or workflows: `experiments/` (17 files),
`holon/`, `seams/`, `spinouts/`, `mode_pack/` (11), `lodestones/` (16),
`terminal/` (**53 files**, the largest), `desktop-shell/` (15), `packages/`,
`references/`¹, `results/`, `analysis/`. `benchmarks/` and `roaming_mailbox/`
are dormant-but-referenced (`orchestrate_live.py:1724`;
`dharma_swarm.roaming_mailbox` — note the import is the *package-internal*
module, so the top-level dir may be a stale copy: verify before touching).
`inter_agent/` is ACTIVE (A2A mailbox lane).

¹ `references/research/.../sources.json` is referenced by this audit's own
fixes; the dir is an archive-class research store, not code.

**Why it matters:** these are exactly the "outdated experiments mixed with
active code" drag the worktree-budget law exists to prevent — but at the
directory level, where no law currently looks. Disposition belongs to the
operator (Blueprint W5): they may be seeds, not slop.

### F6 — MemoryKernel front-door doctrine is only partially adopted

CLAUDE.md declares MemoryKernel "the canonical front door," yet 8 production
modules (`agent_runner`, `orchestrator`, `swarm`, `organism`,
`consolidation`, `context_compiler`, `sleep_cycle`, `worker_spawn`) still
import `memory_palace`/`memory_lattice` directly, vs 6 through the kernel.
Trust gate C5 = 0.20 RED measures the downstream symptom (memory not
first-token). The organism-rewire track's D2 owns the fix direction; what's
missing is a **boundary ratchet** so new code can't widen the bypass
(Blueprint W6).

### F7 — Governance rent remains unpriced (acknowledged, owned elsewhere)

BR-022 packet B / roadmap C-1 already owns this. Noted here only because it
bounds this audit's own recommendations: every wiring move in the Blueprint
is a delta-gate or read-only projection, never a new blanket mandate — the
Transcendence Principle prices governance in diversity loss.

## 3. Fixed this session (receipts)

| Commit | What | Verification |
|---|---|---|
| `00a3af8` | Untracked generated artifacts (`xray_report.{json,md}`, `synthesizer_memory.json` — the latter was gitignored yet tracked); gitignored the xray outputs | files remain on disk; canonical snapshot already at `reports/historical/` |
| `367dc7c` | Root drain wave 5: `PHASE4_REPORT.md` + `phase2_darwin_diff_report.md` → `docs/_archive/2026-07/`; `ANTHROPIC_GRANT_DRAFT.md` → `docs/` (live asset, sits with the YC application); deleted 2 zero-ref pointer stubs + the byte-identical GINKO copy; updated the 2 inbound `sources.json` paths | every candidate grep-verified zero-reference before touching; kept stubs with inbound links |
| `4f396b3` | Reconciled `interface_mismatches.yaml` (2 false-open entries flipped with code evidence, canonical-source declaration, phantom test paths made honest, `last_synced` refreshed); `PRODUCT_SURFACE.md` added to Rule 8 allowlist (was canon-in-docs, absent-in-CI); CLAUDE.md post-D6a correction; regenerated stale `AUTO_INVENTORY.md` section | 170 tests (`-k "mismatch or docops or structure"`) + 3 shim tests green; all 9 uplift guards pass; registry loads 5 entries / 0 open |

## 4. Deferred, with reasons (do not "finish" these blindly)

- **Root executables** (`run_overnight.sh` cluster, `deep_reading_daemon.py`,
  `garden_daemon.py`, `swarm.sh`, `nginx.conf`): moving them is
  doc-coupling-only *in the repo*, but the operator's Mac launchd/cron and
  any deployed VPS reference these **by absolute path outside git**. Moving
  them from a cloud seat would break the living daemon silently — the exact
  harm this audit exists to prevent. Needs the migration recipe in Blueprint
  W4 + operator execution.
- **Divergent doc pairs** (SPRINT_GOTCHAS, YOLO_4AM, RECURSIVE_READING ×3):
  content reconciliation requires a judgment call about which fork carries
  value; blind canonical-picking would destroy it.
- **Dormant-orphan directories** (F5): operator disposition; some may be
  intentional seeds/spinouts.
- **Load-bearing root files stay**: `GNANI_LODESTONE.md`, `LIVING_LAYERS.md`,
  `WHAT_IT_WANTS_TO_BECOME.md`, `program.md`, `program_ecosystem.md`,
  `swarm_live.sh`, `run_daemon.sh`, `com.dharma.swarm.plist` are read at
  root path by runtime code (`gnani_lodestone.py`,
  `long_context_sidecar_eval.py`, `dgm_loop.py`, `lifecycle.py`,
  `doctor.py`, Makefile install). Root is their sanctioned home until the
  readers change.
- **`docs/archive/` → `docs/_archive/` unification** (F4): mechanical but
  wide (link updates across vision maps); scheduled as Blueprint W7 rather
  than done in the same PR as substantive fixes.
