# Broken Register

**Status:** seeded Slot 7 megafile
**Scope:** declared-vs-actual contradictions that affect onboarding or runtime
**Rule:** if a PR closes, demotes, or creates one of these entries, update this
file in the same PR.

This register is narrower than a general todo list. It tracks places where an
agent would believe one thing from docs, names, or architecture and observe
something different in the repo or runtime.

## Active Entries

### BR-001: Megafile Slots Still Incomplete

- **Status:** PARTIAL
- **Declared:** The system should have ten discoverable onboarding megafiles.
- **Actual:** Slot 1, Slot 6, and Slot 7 are seeded; Slots 2, 3, 8, and 9 remain
  missing or fragmented.
- **Evidence:** `docs/MEGAFILE_INDEX.md`
- **Next bindable gap:** create one repo-local Slot 8 operator runbook after the
  Coherence Delta gate proves stable.

### BR-002: Coherence Delta Checks Presence, Not Truth

- **Status:** PARTIAL
- **Declared:** Every PR re-reads the map and names drift.
- **Actual:** CI now validates that the four fields are present and substantive,
  but it cannot prove the answers are true.
- **Evidence:** `.github/workflows/coherence-delta.yml`,
  `scripts/governance/check_pr_coherence_delta.py`
- **Next bindable gap:** add reviewer guidance or semantic checks once enough PR
  bodies exist to learn from.

### BR-003: OrganState Is Perception-Only

- **Status:** PARTIAL
- **Declared:** The swarm should make self-recognition causal.
- **Actual:** OrganState facts are produced and queryable, but Darwin, Shakti,
  PR classification, and proof contracts do not yet consume them.
- **Evidence:** `scripts/system_map_populator.py`,
  `dharma_swarm/operator_core/operating_facts.py`, `dharma_swarm/dgc_cli.py`
- **Next bindable gap:** wire one low-risk consumer to read
  `reports/system_map/latest.json`.

### BR-004: Static Navigation Is Not Fully Current

- **Status:** PARTIAL
- **Declared:** Agents can read a full module map before editing.
- **Actual:** `docs/architecture/NAVIGATION.md` exists, but live xray and the
  May 7 audit identify stale counts and missing current-state details.
- **Evidence:** `docs/architecture/NAVIGATION.md`, `README.md`, `CLAUDE.md`
- **Next bindable gap:** decide whether Slot 4 is a refreshed static atlas or a
  generated xray packet with a stable markdown front door.

### BR-005: Cron Health Is Mixed

- **Status:** PARTIAL
- **Declared:** The metabolic clock should be a single canonical live loop.
- **Actual:** The Dharma launchd processes are attached and system-map/tcs jobs
  exist, but older jobs may still report `last_status: error`.
- **Evidence:** `~/.dharma/cron/jobs.json`, `docs/state/LIVE_OPS_DASHBOARD.md`
- **Next bindable gap:** triage one failing cron job per PR.

## Recently Closed

### BR-019: Coherence Delta Honor-System Only

- **Status:** CLOSED by this closure slice.
- **Declared:** Coherence Delta should prevent PRs from bypassing the maps.
- **Actual before:** The PR template asked for fields, but no tool validated
  that they were filled.
- **Closure:** `.github/workflows/coherence-delta.yml` runs
  `scripts/governance/check_pr_coherence_delta.py` on PR bodies.
- **Residual drift:** BR-002 tracks truthfulness beyond field presence.
