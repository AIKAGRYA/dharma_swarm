# Cross-Agent Inventory — All Open Strings Across All Devin Sessions

**Generated:** 2026-05-21T13:00Z (content refresh note added 2026-05-29)
**Source:** All 12 Devin sessions in org `amitabhainarunachala` + repo state
**Method:** `devin_session_search` + `devin_session_events` (message history) + `gh pr list --limit 100` + repo filesystem

> **2026-05-29 refresh note:** Since this inventory was generated, main has advanced
> from ~693 to 702 commits. Notable additions: perplexity-computer registered (PR #376),
> third-witness verification posted on PRs #375/#376, spine v2 landed (#427),
> OMS hardened (#409), KARMA gate landed (#408), multi-track doctrine amended (#396).
> Session 12 (this session) extended with adversarial review + doc refresh work.

---

## 1. DEVIN SESSION MAP (12 sessions, oldest → newest)

| # | Session | Date | PRs | Status | Key Deliverable |
|---|---------|------|-----|--------|-----------------|
| 1 | **Prove dharma_swarm Loop Gauntlet** | May 4 | 16 (10 merged, 4 closed, 2 open?) | suspended/inactivity | Authority/Revenue Loop, TelicSeam wiring, Repo Reality Gauntlet |
| 2 | **Find missing trial session** | May 4 | 9 (all merged) | suspended/inactivity | NEXT_10_SUBSTRATE_TODO Items 2, 3, 8; agent allocation plan |
| 3 | **Productive work on own branch** | May 5 | 4 (2 merged, 1 closed, **2 open**) | suspended/out_of_quota | Cold-lane test coverage, circular dep analysis, **PRs #117 + #131 still open** |
| 4 | **Dharma Swarm hGO Ingest** | May 10 | 2 (1 merged, 1 closed) | suspended/inactivity | RevenueCell v0, 8-phase codex spec, Contemplative Spine, full wiring audit |
| 5 | **Go Track Full Map** (child of #4) | May 10 | 0 | completed | Go track map (6 files, 1300 LOC, 9 unbuilt packets G5-G13). **Deliverable NOT committed to repo** |
| 6 | **Find codebase bugs discrepancies** | May 10 | 1 (merged #195) | suspended/inactivity | Full anti-slop audit, bug pattern analysis (interface drift = 38%) |
| 7 | **Single source of truth control plane** | May 11 | 3 (all merged #202, #203, #307) | suspended/inactivity | Manifest Health API, dashboard research, Spatial Canvas plan |
| 8 | **Scan RTN** | May 12 | 0 | suspended/inactivity | 23 RTNs mapped. **Deliverable NOT committed to repo** |
| 9 | **Control-surface Operator Cockpit v1** | May 12 | 1 (merged #244) | suspended/inactivity | Cockpit dashboard 5-zone layout |
| 10 | **Backend prep for Cockpit** (child of #9) | May 12 | 1 (merged #254) | suspended/inactivity | Structured evidence models. **Only 15% complete when suspended** |
| 11 | **3 biggest problems** | May 18 | 0 | suspended/inactivity | Analysis: dispatch_dropoff loop, god objects, interface drift |
| 12 | **THIS SESSION** | May 20-21 | 8 (#313-#326) | running | Track lifecycle, BoardStore/Dhyana/Sakshi, env aliases, architecture review, next-phase map |

---

## 2. OPEN STRINGS — THINGS STARTED BUT NOT FINISHED

### A. Open PRs from past Devin sessions (still open on GitHub)

| PR | Session | Age | What it does | Status |
|----|---------|-----|-------------|--------|
| **#117** | Productive work | 16 days | refactor: 6 module consolidation moves per MODULE_METABOLISM_STRATEGY | **STALE — needs rebase, likely conflicts** |
| **#131** | Productive work | 16 days | fix: structural coherence — resolve NEW-05, advance NEW-07, add AgentIdentity | **STALE — needs rebase, likely conflicts** |

### B. Deliverables produced but never committed to repo

| Deliverable | Session | What it contains | Where it lives |
|-------------|---------|-----------------|----------------|
| **Go Track Full Map** | Go Track Full Map | 6 Go files, 2 unmerged branches, 9 unbuilt packets (G5-G13), Python↔Go bridge map | Only on that session's VM (expired). **Lost unless user has local copy** |
| **RTN Analysis** | Scan RTN | 23 Recursive Transition Networks mapped end-to-end | Only on that session's VM (expired). **Lost unless user has local copy** |
| **Bug Pattern Report** | Find codebase bugs | Interface drift = 38% of bugs, full category breakdown | Attached as message in session. **Not in repo** |
| **Backend prep models** | Backend prep | EvidenceItem, SourceRef, HumanDecisionContext, VerificationEvent, AgentHandoffPrompt | Session was 15% done. **Unclear what was committed vs lost** |

### C. Planned but never started

| Plan | Session | What was planned | Why stopped |
|------|---------|-----------------|-------------|
| **Spatial Canvas** | Single source of truth | PR 3 of planned 3-PR sequence — React Flow powered by manifest health | Session suspended after PR 1+2. Never started |
| **Go packets G5-G13** | Go Track Full Map | 9 Go modules mapped but not built | Analysis-only session, no code work |
| **MODULE_METABOLISM_STRATEGY execution** | Productive work | Full module consolidation plan | Session ran out of quota after 2 of 6 moves |

### D. Architecture analyses never operationalized

| Analysis | Session | Key Finding | Actionable? |
|----------|---------|------------|-------------|
| 23 RTN network map | Scan RTN | Full feedback loop topology | Yes — could inform loop closure priority |
| 3 biggest problems | 3 biggest problems | dispatch_dropoff, god objects, interface drift | Yes — dispatch_dropoff still not fixed |
| Bug pattern taxonomy | Find bugs | 38% interface drift, recurring root causes | Yes — INTERFACE_MISMATCH_MAP was last updated based on this |
| Invariant command plane | THIS SESSION | Control Surface = root, 5 zones, ~140 LOC patch | Yes — nav reorder + drift triage panel |
| Dashboard fidelity audit | THIS SESSION | 9 LIVE, 13 PROVIDER-GATED, 5 STUB pages | In repo as docs/state/DASHBOARD_FIDELITY_AUDIT.md |

---

## 3. OPEN STRINGS — REPO-WIDE (not session-specific)

### 35 Open PRs (by category)

**Merge-ready (CI green, from recent sessions):**
- #321 — TaskBoard adapter + BR closure (THIS SESSION)
- #323 — env alias normalization (THIS SESSION)
- #325 — Codex toolbelt onboarding (THIS SESSION)
- #326 — Next-phase map + hotlist (THIS SESSION)

**Need review (from Codex/Copilot/John):**
- #312 — Wire governed live MemoryKernel release gate
- #314 — Pin router/TaskBoard domains; refresh manifest counts
- #320 — ADR-007: Retire AutoProposer
- #322 — Trim COMMAND nav to 9 items
- #324 — CWT v0 read-only collector

**Stale (14+ days old, likely need rebase):**
#44, #55, #58, #59, #99, #117, #131, #142, #143, #144, #145, #147, #148, #149, #150, #151, #152, #158, #161, #168, #181, #182, #190, #191, #271, #297

### Active Track Blockers
- **ADR-0002** — missing; blocks trace-identity-coverage track closure
- **CorrelationContext defaulting** — operator-brief, BoardStore, Sakshi need trace metadata
- **Guardian DEGRADED finding** — for artifacts missing metadata.trace_id

### Seeded Packages (0 wired to runtime)
- `dharma_swarm/board/` — 1,144 LOC, Card schema + facade + TaskBoard adapter
- `dharma_swarm/dhyana/` — 205 LOC, drift triage (wired to `make onboard` output)
- `dharma_swarm/sakshi/` — 281 LOC, append-only provenance chain

### Cybernetic Loops
- **4 of 13 closed in bounded replay** (Loops 1, 2, 5, 6)
- **0 of 13 all-history daemon clean**; historical dispatch_dropoff rows remain
- **7 partial, 2 blocked**; Loops 12/13 remain blocked behind One Wire quorum
- Canon: `CYBERNETIC_LOOP_MAP.md` and `scripts/governance/cybernetics_codex_audit.py --json`

### Broken Register
- 5 open items: BR-003 (evolution gate, PARTIAL), BR-004, BR-005 + others

### Code Health Issues
- `terminal_bridge.py` — 2,539 lines, **128 over Rule 10 ceiling** (needs decomposition)
- CYBERNETIC_LOOP_MAP.md — 16+ days stale
- INTERFACE_MISMATCH_MAP.md — 17+ days stale
- LIVE_OPS_DASHBOARD.md — 10+ days stale

---

## 4. WHAT I COULD NOT FIND

### Rio's Transcript
**Searched all 12 Devin sessions (message history + event search for "rio", "Rio", "transcript").** No matches. Also searched all 705+ markdown files in the repo for `\bRio\b` — no matches.

**Likely explanations:**
- This transcript exists in a **Codex session** (I can't see those)
- It's in a **Claude Code session** (I can't see those)
- It's in **Cursor or Warp** history (I can't see those)
- It might have been a conversation with a person named Rio that happened outside any agent

**John:** If you can paste the Rio transcript here or tell me where it lives, I can integrate it.

### Non-Devin Agent Work
I can only see the 12 Devin sessions. I **cannot** see:
- Codex sessions (you mentioned several agents)
- Claude Code sessions
- Cursor sessions
- Warp terminal history
- VPS work
- Copilot SWE agent context (I can see its PRs, like #271, but not its reasoning)

---

## 5. THE REAL PROBLEM: YOU ARE THE ROUTING LAYER

### Current State
```
John (human) ←→ Devin session 1
John (human) ←→ Devin session 2
John (human) ←→ ...
John (human) ←→ Devin session 12
John (human) ←→ Codex agent 1
John (human) ←→ Codex agent 2
John (human) ←→ Claude Code
John (human) ←→ Cursor
John (human) ←→ Copilot SWE agent
John (human) ←→ Terminal agent
John (human) ←→ 3 VPSs
```

Every arrow is a manual copy-paste. **You are the bottleneck in a system designed to transcend individual bottlenecks.** This is the exact opposite of the Transcendence Principle.

### Why This Happens
1. **No shared state surface.** Each agent has a different view of reality. HOTLIST.md and NEXT_PHASE_MAP.md are static — they're already stale.
2. **No task assignment protocol.** Agents don't know what other agents are doing. You manually prevent conflicts.
3. **No cross-session memory.** Devin sessions can't see each other's history. Knowledge notes are empty.
4. **No auto-coordination.** When an agent finishes, nothing auto-triggers the next step.

### What Would Fix This

#### Tier 1: Things I can do RIGHT NOW (this session)

1. **Populate Devin Knowledge Notes** — persistent cross-session memory. I'll create notes for:
   - Current repo state (active track, broken register, open PRs)
   - Agent allocation rules (who works on what)
   - Coordination protocol (check HOTLIST.md before starting work)
   - Provider key status
   
   Every future Devin session will automatically see these.

2. **Create a Devin Playbook** — a reusable prompt template that:
   - Runs `make onboard` first
   - Reads HOTLIST.md and NEXT_PHASE_MAP.md
   - Claims a task from the hotlist
   - Updates the hotlist when done
   - Follows Coherence Delta

3. **Set up a Scheduled Devin Session** — daily `make onboard` + stale doc detection + HOTLIST refresh. Auto-files issues when things drift.

#### Tier 2: Things that need repo changes (PR)

4. **`make status`** — a single command that shows:
   - Active track + blockers
   - Open PRs by triage tier
   - Broken register
   - Stale docs
   - Last agent activity timestamp
   Any agent on any platform can run this.

5. **`.github/copilot-instructions.md`** — so Copilot coding agent follows the same coordination protocol.

6. **GitHub Agentic Workflows** — markdown-based automation for:
   - Auto-triage PRs older than 14 days
   - Auto-detect stale docs
   - Auto-update HOTLIST.md on PR merge

#### Tier 3: Architectural (longer-term)

7. **Use GitHub Issues as the coordination bus** — agents claim Issues, Issues reference the task, PRs close Issues. Every agent platform (Devin, Codex, Copilot, Claude Code) can read/write Issues.

8. **Agent registration in ACTIVE_SURFACE_MANIFEST.yaml** — each agent declares what it's working on. Others check before starting.

---

## 6. RECOMMENDED IMMEDIATE ACTIONS

| Priority | Action | Effect |
|----------|--------|--------|
| **P0** | Populate Devin Knowledge Notes | Every future Devin session starts with full context |
| **P0** | Create coordination playbook | New sessions auto-claim from HOTLIST |
| **P1** | Merge #321, #323, #325, #326 | Clear the merge queue |
| **P1** | Close stale PRs (#44, #55, #142-#152) | Drop PR queue from 35 → ~15 |
| **P1** | Write ADR-0002 | Close active track |
| **P2** | Add `make status` command | Any agent, any platform can check state |
| **P2** | Set up scheduled session for daily health | Auto-detect drift |
| **P3** | GitHub Agentic Workflows | Auto-triage, auto-stale-detect |
