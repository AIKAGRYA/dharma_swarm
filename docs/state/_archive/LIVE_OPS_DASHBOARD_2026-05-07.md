# LIVE OPS DASHBOARD — Slot 6 of MEGAFILE_INDEX
**Path:** `dharma_swarm/docs/state/LIVE_OPS_DASHBOARD.md`
**Status:** SEEDED — 2026-05-07 inaugural snapshot
**Refresh cadence:** daily target. Currently manual. Auto-refresh is not wired; BR-001 fixed cron-daemon restart safety, but no job owns this file yet.
**Mode:** Today's truth — what's running, what fired, what crashed, what's stale. Aggregates fresh audit substrate into one read.

---

## How To Use

This file is **the morning briefing for the swarm.** A new agent reading it should know within 60 seconds what is alive today.

Each section answers one question:
1. **Processes** — what daemons are running right now?
2. **Cron / launchd** — what fired in the last 24h, what errored?
3. **Loops** — which cybernetic loops are closed today?
4. **Branches / PRs** — what shipped, what's pending, what's stuck?
5. **Stores** — what databases / files were last touched, what's stale?
6. **Top blockers today** — pulled from BROKEN_REGISTER.md

When refreshing, replace each section's date and content. **Snapshot the previous version to `_archive/LIVE_OPS_DASHBOARD_<YYYY-MM-DD>.md` before overwriting.**

---

## Snapshot Date: 2026-05-07

### 1. Processes

**Live Python daemons (per `~/.dharma/audit/system_inventory_2026-05-07.md`):**
- `orchestrate_live` PID 90494 in `dharma_swarm_lf5` worktree, since 2026-04-30 (running ~7 days)
- `com.dharma.cron-daemon` — path/version drift fixed in BR-001; verify current PID with `launchctl print gui/501/com.dharma.cron-daemon`
- 731 live `claude|codex` processes (per inventory section 4B)
- 9 active git worktrees (direct `git worktree list` check, 2026-05-07)

**Dashboard surfaces:**
- `com.dharma.dashboard-api` — log fresh today (per launchd)
- `com.dharma.dashboard-web` — log fresh today (per launchd)

**Chetana plist set:** continuous, deep_sleep, rem, wake, heartbeat — all loaded; logs fresh today.

### 2. Cron / launchd Last 24h

**From `~/.dharma/cron/jobs.json` last_status fields** (direct check, 2026-05-07). `algedonic_triage` is launchd/log evidence, not a `jobs.json` row:

| Job | Last Status | Notes |
|---|---|---|
| `ontology_insight_brief` | **ok** | Daily 20:30 ontology brief — succeeded last night |
| `algedonic_triage` | ok (via launchd) | Logs fresh 2026-05-07 06:51 |
| `yatagarasu-flight` | **error** | API key issue per `--bare` mode |
| `planetary-reciprocity-pulse` | **error** | API key |
| `planetary-reciprocity-cultivation` | **error** | API key |
| `telos-mission-scout` | **error** | API key |
| `doctor_assurance` | **error** | FAIL |
| `tcs_heartbeat` | **NO_STATUS** | Enabled job has no recorded `last_status` yet |

**5 of 7 enabled live `jobs.json` jobs have error status; 1 is ok; 1 has no recorded status.** Pattern: jobs that need ANTHROPIC_API_KEY in `--bare` mode are failing. Doctor assurance fails for a different reason (not API-key).

**Phase 1 perception surfaces now present:**

| Surface | Path / command | Role |
|---|---|---|
| System map report | `reports/system_map/latest.json` | OrganState perception output |
| System map CLI | `dgc map list`, `dgc map drifted`, `dgc map gaps` | Read-only organ queries |
| Coherence Delta gate | `.github/workflows/coherence-delta.yml` | PR-body map reread discipline |
| DocOps gate | `make docops-integrity` | Documentation authority and count checks |

**Crontab (3 active rules):**
- `mech-interp tick` every 30 min (separate repo)
- `dharma_swarm_rollup_brake_matrix` daily 7:10 (until 2026-06-01)
- `dharma_swarm_rollup_status` 9:30 + 21:30 (until 2026-06-01)

**14 LaunchAgents** (9 com.dharma.* + 5 com.dhyana.chetana.*) loaded. BR-001 fixed the cron-daemon executable mismatch by pinning the plist to the lf5 virtualenv `dgc`; individual failing jobs remain separate triage items.

### 3. Loops

**From `~/.dharma/audit/central_loop_trace_2026-05-07.md` + `self_evolution_trace_2026-05-07.md`:**

| Loop | Status | Evidence |
|---|---|---|
| Recognition seed → context injection | OPEN-but-stale | Code path SUPPORTED (`meta_daemon.py` → `context.py:1202-1217`); seed itself 6 days old (BR-006) |
| Shakti → Darwin proposals | CLOSED | `orchestrate_live.py:76-110, :797-814` → `evolution.py:3477-3503` |
| Apply gate (Build Protocol → Darwin) | **CLOSED-BLOCKED** | BR-003: 0 import edges; direct disk check found 9 current dryrun dirs, 4 proof packets, 0 applied markers |
| Central VentureCell loop (board → cell → outcome → board) | **OPEN** | BR-002: outcomes don't feed back |
| Algedonic feedback | **DEGENERATE** | BR-005: last 200 rows all `omega_divergence medium rebalance_priorities` at only two values |
| Sediment-to-crystallization (marks → gates) | OPEN | Kernel + telos_gates static 6+ weeks |
| Diversity archive read-path | OPEN | `diversity_archive.json` absent on disk; zero in-package importers |
| Strange-loop persistence | OPEN | `mutations.jsonl` absent — in-memory only |

### 4. Branches / PRs

**From `~/.dharma/audit/48h_status_2026-05-07.md`:**
- 53 active branches with commits in last 48h
- 11 merged (PRs #135–#141)
- 4 PRs open (#142, #143, #144, #145)
- 38+ branches with commits but no fetched PR detail (gh creds 401)
- 18 branches in merge conflict vs origin/main
- **~25 branches (47%) have no anchor in any plan doc** (per BR-009)
- Current HEAD: `feat/brief-to-spec-seam-2026-05-07` — itself orphan to LOOMWORK

### 5. Stores Touched Today

**SQLite + JSONL with mtime today (2026-05-07):**
- `~/.dharma/vectors.db` — touched today
- `~/.dharma/ontology.db` + WAL — touched today
- `~/.dharma/identity_history.jsonl` — touched today
- `~/.dharma/algedonic_signals.jsonl` — touched today (but degenerate; BR-005)
- `~/.dharma/cleanup_loop.jsonl` — touched today
- `~/.dharma/witness/` recent activity (per inventory)
- `~/.dharma/stigmergy/marks.jsonl` — touched today
- `~/.dharma/cron_logs/` — heartbeat + algedonic + neurips-evolve logs fresh

**Stale stores (despite "should be fresh"):**
- `~/.dharma/meta/recognition_seed.md` — **6 days stale** (BR-006)
- `~/.dharma/runtime.db` — last touched 2026-04-27 (10 days ago) — likely superseded by `state/runtime.db` + `db/runtime.db` split (BR-007)

### 6. Top Blockers Today (from BROKEN_REGISTER)

| ID | Item | Severity |
|---|---|---|
| BR-002 | Central VentureCell loop is open | **BLOCKER** |
| BR-003 | Apply gate present but closed | **BLOCKER** |
| BR-007 | Two stores for one self (runtime ↔ ontology) | **BLOCKER** (architectural) |
| BR-008 | VentureCell-as-ontology vs VentureCell-as-organ | **BLOCKER** (architectural) |
| BR-004 | Cron split-brain (repo vs live) | DEGRADED |
| BR-005 | Algedonic in degenerate steady-state | DEGRADED |
| BR-009 | Roadmap is contested (3 docs) | DEGRADED |

See `BROKEN_REGISTER.md` for full register.

---

## Health Verdict (one paragraph)

The swarm is structurally alive but operationally degraded. Substrate (orchestrate_live, dashboard, chetana plist set, kaizen db, ontology db, identity history) is fresh today. BR-001 fixed cron-daemon restart safety, but **5 of 7 enabled cron jobs are still erroring** — most blocked on missing ANTHROPIC_API_KEY in `--bare` mode; one enabled job has no recorded status. Recognition seed remains stale after the cron fix, so BR-006 is independent of the daemon path issue. Central VentureCell loop and apply gate are both architecturally present but operationally closed — sediment is not crystallizing into new gates / skills / organs. 47% of in-flight branches have no plan-doc anchor. **Strategy is ~10x ahead of code.** The highest-leverage next fixes are scoped investigations of BR-005 and BR-006 plus one consumer of the new OrganState perception surface.

---

## Next Refresh

Recommend daily refresh, rolling old snapshot to `_archive/LIVE_OPS_DASHBOARD_2026-05-07.md`. Until a job explicitly owns this dashboard, refresh is manual.

**Refresh procedure (target):**
1. Re-run `~/.dharma/audit/48h_status` generation
2. Re-run `~/.dharma/audit/system_inventory` if branches changed materially
3. Pull `~/.dharma/cron/jobs.json` last_status fields
4. Update Loops section against `central_loop_trace`
5. Re-pull BROKEN_REGISTER top items
6. Update Health Verdict paragraph

---

*This dashboard is one read of today. Tomorrow, write tomorrow's. The shape persists; the contents change.*
