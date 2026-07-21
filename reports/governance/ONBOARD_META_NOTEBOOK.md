# Onboard Meta Notebook — agent experience of `make onboard`

**Role:** report / living notebook (not canon, not authority)  
**Seat:** `operator_guide_cursor`  
**Started:** 2026-07-10 JST  
**Purpose:** record how onboarding feels from inside a vibecoded multi-agent repo, so the operator can tune the gate without guessing.

Doctrine reminder: this notebook projects experience; it does not own track state. Trust `make onboard` + `ACTIVE_TRACK.yaml`.

---

## Entry 2026-07-10 — first full strategic session

### What I ran

```bash
make onboard
# → scripts/governance/agent_onboard.py (~2175 lines)
# wall clock ~13.7s; exit ignored Error 1 from sprawl_guard advisory
```

### How it worked (simple model)

1. **You** ask for orientation.
2. **Desk** runs one remembered command.
3. **Renderer** projects owners (tracks, ops, tooling, drift, wiki health, sprawl).
4. **Agent** is supposed to stop inventing a second map.

Analogy: airport departure board — not the airplanes, not the flight plan authority, just the board. If the board is wrong, you still look at the runway (filesystem / git / ACTIVE_TRACK.yaml).

### What helped (this session)

| Signal | Why it mattered |
|---|---|
| Portfolio at a glance (11 tracks, 9 SHIPPABLE, 2 incomplete) | Instant triage without grepping YAML |
| Spine coverage row | Confirmed all three objectives have a lane |
| Honest incomplete blockers (spine 70/100; TELOS missing external receipt) | Prevented "everything is green" theater |
| Sprawl guard FAIL on holon singleton copies | Named a real vibecode failure mode: duplicate organs |
| Drift triage top-5 | Pointed at Evolution / Telos Gates / BoardStore as partial wiring |
| Tooling-first ladder | Reminded structure tools before grep |
| "Remember only: make onboard" | Correct cognitive load for a fresh agent |

### What hindered / risked harm

| Friction | Vibecode consequence |
|---|---|
| Volume: long scroll, many sections | Agents skim; then re-derive from CLAUDE.md and invent parallel plans |
| `SHIPPABLE` without close authority | Creates urgency theater — looks like "done" while WIP stays maxed |
| Receipt write `PermissionError` on `~/.dharma/ops/onboard_receipt.*` | Session left no durable "I onboarded" crumb when sandboxed |
| Did not hard-stop on **551 behind main** / **80 worktrees** | The most dangerous desk facts were adjacent (git status) not first-class red banners |
| Stale plan pointers still listed (66–74d) | Invites agents to reopen composted maps |
| Wiki orphan sample includes chat-debris atom titles | Noise competes with orientation signal |
| Advisory sprawl FAIL ignored by make | Correct as advisory, but easy to psychologically dismiss |

### Vibecode-specific diagnosis

This repo is **governance-forward vibe coding**: agents generate organs faster than metabolism to main. `make onboard` is the immune system trying to make every new instance share one map.

It **helps** when:
- the agent treats it as a hard gate before build
- SHIPPABLE → operator lifecycle, not agent self-close
- sprawl/drift findings become the next action

It **hinders** when:
- the agent reads it as lore and keeps building a 12th track
- SHIPPABLE is mistaken for "shipped to users"
- the board is so long that the agent greps anyway (defeating the point)

### Proposed small improvements (do not implement from this notebook alone)

1. Add a **DESK DANGER** strip: ahead/behind main, dirty count, worktree count vs budget.
2. Collapse SHIPPABLE tracks to one line + "operator lifecycle review" — expand only with `--verbose`.
3. Make receipt write best-effort with a visible `receipt: skipped (reason=...)` instead of a buried PermissionError.
4. Promote sprawl singleton FAIL into the WHAT TO DO NEXT bullets when findings > 0.

### Session pull (recorded for continuity)

Primary track pull: `runtime-truth-spine-adoption-2026-06` (70→75).  
Secondary (after WIP compost): remote holon mesh v1.1 — not as track #12 at WIP max.

---

## How to continue this notebook

Append dated entries after any non-trivial `make onboard` in a strategic session. Keep entries short. Prefer evidence over vibes. Never let this file become a second ACTIVE_TRACK.
