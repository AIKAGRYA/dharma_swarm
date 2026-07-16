# MEMORY — devin-roaming-2987d222

Running memory log. Updated each session. Newest entries first.
Future sessions: read this file on wake to recover context.

---

## Session Memory Format

Each entry records: what I learned, what changed, and what's pending.
This is my equivalent of `~/.dharma/agent_memory/` — committed to the
repo so any agent (including my future self) can read it cold.

---

## 2026-06-11 — Session 863663ec (Fable 5 master-prompt prep)

**Session URL:** https://app.devin.ai/sessions/863663ecf70741a4b565a07037852343
**Registration packet:** `inter_agent/devin/outbound/2026-06-11T08-45Z-devin-session-registration-863663ec.md`

### What I Learned

- At the time, #563 described onboard as “single-door v2” and rendered the
  portfolio, parallel lanes, and fleet receipt. This is historical: current
  `make onboard` is read-only session status, packet-bound preflight owns edit
  admission, and current owner docs supersede this session note.
- ACTIVE_SURFACE_MANIFEST.yaml has been demoted in practice: it is the
  Surface layer of the three-layer SSoT model (Intent = ACTIVE_TRACK.yaml,
  Surface = manifest, State = LIVE_OPS_DASHBOARD.md) and is read on demand,
  not a binding first-read gate. Manifest health check fails on this VM
  (system python lacks pydantic) — use `.venv` python for manifest tooling.
- Active portfolio: `runtime-truth-reconciliation-2026-06` (operator) +
  `runtime-truth-nats-2026-06` (codex). Spine objectives uncovered:
  revenue-external-humans-served, research-depth.
- Fable 5 is the Anthropic lane running `honest-spine-v2`; prior session
  6a5df962 answered its critique request (#565). Its packets cite local
  worktree SHAs — verify against remote refs before trusting.

### What Changed

- Registered this session in the repo (outbound packet + this entry).
- Wrote `docs/plans/2026-06-11-fable5-master-prompt.md` — master prompt for
  the next build session, including the names-and-filesystem coherence
  proposal and the `make composer` high-level onboarding concept.

### What's Pending

- [ ] Operator review of the master prompt and the composer proposal.
- [ ] If approved: open a new track for the doc/filesystem coherence work
  (it touches no active-track surfaces; needs its own `serves:` binding).

---

## 2026-05-22 — Genesis Session

**Session URL:** https://app.devin.ai/sessions/2987d22290324e5ba8b44d6368115755
**Duration:** Extended (multi-hour, operator-interactive)
**PRs authored this session:** #313, #315, #318, #319, #321, #323, #325, #326, #327, #328, #330

### What I Learned

**Repo structure:**
- 610 Python modules, 260K LOC, 585 test files, 705 markdown files
- 20 dashboard pages: 7 LIVE, 7 DEGRADED, 6 STUB/BROKEN
- 0/13 cybernetic loops closed in production
- 19 API routers, 14 adapters, 23 bridge files, 4 orchestrators
- CI gauntlet: 22 gates (DocOps, governance, semgrep, gitleaks, Rule 8/9/10, etc.)
- `make onboard` is the single remembered gate — run it before any work

**Architecture insights:**
- OperatorMicrographics pattern: fake surfaces hiding real signals (7 instances)
- Interface mismatches: 0 BLOCKER, 4 DEGRADED remaining
- Control Surface (`control_surface.py`): 1001 lines, grandfathered at Rule 10 ceiling
- Substrate-nativeness: ~10-15% (most runtime bypasses the ontology)

**Agent fleet:**
- Mac-side triad: HERMES M5 (30m heartbeat), Opus_Composer, Codex_Composer
- 8 Mac-resident agents in agents.json (including my mirror entry)
- 12 historical Devin sessions → 46 total PRs (33 merged, 6 closed, 7 open)
- Other platforms: Codex, Claude Code, Cursor, Warp — I can't see their sessions

**Governance:**
- Authority comes from CANONICAL_DOC_STACK.md only
- Active track: `trace-identity-coverage-2026-05` (ACTIVE)
- ADR-0002 written: trace coverage stays DEGRADED, not BLOCKER
- Broken register: 9 items, 5 OPEN/PARTIAL (BR-003/004/005 + 2 others)

**Inter-agent protocol:**
- GitHub is the canonical rendezvous (NAT blocks Mac↔VM direct)
- `dharma_swarm/inter_agent/devin/{inbound,outbound,shared}/` is the directory protocol
- Hourly scheduled wake: `sched-48540b4f8af24edca98d156033579800`

### What Changed

- Registered as external roaming agent (58/58 integrity checks)
- Stale PR triage: 35 → 10 open PRs (closed 25, all 14+ days old)
- Rebased PRs #312, #314, #321 — resolved multi-file conflicts
- Wrote dashboard SSOT architecture audit (654 lines)
- Wrote ADR-0002 (trace coverage gate policy)
- Created `make status` command for cross-agent visibility
- Created CROSS_AGENT_INVENTORY.md from all 12 Devin sessions
- Created HOTLIST.md kanban
- Created inter_agent rendezvous channel + first response to Mac triad
- Created this identity nest (SOUL.md, MEMORY.md, PROTOCOLS.md)

### What's Pending

- [ ] 8 PRs in merge queue (all CI green): #312, #314, #321, #323, #325, #326, #327, #328
- [ ] PR #330 (this identity nest + inter_agent rendezvous) awaiting merge
- [ ] 3 Codex PRs (#320, #322, #324) awaiting operator review
- [ ] Mac triad hasn't received first response yet (needs PR merge + git pull)
- [ ] BR-005 (algedonic stream steady-state) — suggested as first cross-substrate task
- [ ] Board-events API wiring — PR Ladder Step 1 from dashboard audit
- [ ] Knowledge Note + Playbook + Daily Health Schedule — awaiting operator approval in Devin timeline
- [ ] Rio's transcript — not found in any Devin session; operator needs to provide

### Key Files I Know Well

| File | Why I know it | Lines |
|---|---|---|
| `CLAUDE.md` | Governance behavioral contract | ~300 |
| `INTERFACE_MISMATCH_MAP.md` | Read before touching any module pair | ~200 |
| `CYBERNETIC_LOOP_MAP.md` | 13 loops, 0 closed | ~150 |
| `docs/governance/SOVEREIGN_MANIFEST.md` | Ground truth metrics | 454 |
| `docs/governance/CANONICAL_DOC_STACK.md` | Authority hierarchy | ~100 |
| `docs/governance/ACTIVE_TRACK.yaml` | Current build track | ~60 |
| `docs/docops/assertions.yaml` | DocOps integrity rules | ~204 |
| `ACTIVE_SURFACE_MANIFEST.yaml` | Dashboard surface registry | 657 |
| `dharma_swarm/control_surface.py` | 5-zone reconciliation engine | 1001 |
| `dharma_swarm/external_agent_registration.py` | How I registered | ~400 |

### Error Log

| Error | Root Cause | Resolution |
|---|---|---|
| DocOps integrity fail (PR #330 CI) | inter_agent .md had authority terms, not registered in canonical guard | Added to `assertions.yaml` registered list |
| Couldn't find Rio's transcript | Not in any of the 12 Devin sessions | Likely in Codex/Claude Code/Cursor — operator needs to provide |
| Initially tried to reach Mac directly | NAT asymmetry not immediately recognized | Designed around it: GitHub-only rendezvous |
