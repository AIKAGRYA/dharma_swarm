# Command Plane — Multi-Agent Protocol

**Status:** Queued track infrastructure. Use this when spawning teams for command-plane work.
**Spec:** `docs/plans/2026-05-21-command-plane-design-lock.md`
**Vision:** `docs/plans/COMMAND_PLANE_VISION.md`
**Checklist:** `docs/plans/COMMAND_PLANE_CHECKLIST.md`

---

## Purpose

This document is how a human or agent picks up command-plane work cold. It is the **hand-off brief** that turns 15+ scattered conversations into a single workstream any agent can join in under 5 minutes.

Three failure modes it prevents:
1. **Re-running the grill** — every locked decision is in the spec; new sessions don't re-decide
2. **Parallel-session collision** — every team checks the checklist before claiming work
3. **Off-track drift** — every team prompt reminds the agent that command-plane is QUEUED behind trace-identity

---

## The 30-second brief (read first, every session)

| Question | Answer |
|---|---|
| What is the command plane? | Observatory+cockpit, 2D canonical with 3D where it earns, Nihonga palette, 7 verb-zones, numbers as protagonist. Read `COMMAND_PLANE_VISION.md`. |
| What's the spec? | `docs/plans/2026-05-21-command-plane-design-lock.md`. Locked. Do not re-debate. |
| What's the current track? | `trace-identity-coverage-2026-05` is ACTIVE. Command-plane is QUEUED. Most command-plane work must wait or be feature-flagged. |
| What can I work on now? | Anything in `COMMAND_PLANE_CHECKLIST.md` Phase 0 (pre-flight, mechanical). Phase 1+ formally starts when trace-identity closes. |
| Who owns this? | @AmitabhainArunachala |
| What must I NOT do? | Reopen design decisions. Add new top-level dashboard surface (active track's non-goal). Use R_V framing. Use "living system / heartbeat" metaphor language. |

---

## Team-spawn template

Copy-paste this when spawning agents for command-plane work. Substitute `{LANE}` and `{TASK}`.

```
You are {NAME} on team command-plane-redesign. Team lead: team-lead.

LOCKED CONTEXT (DO NOT RE-DEBATE):
- Spec: docs/plans/2026-05-21-command-plane-design-lock.md
- Vision: docs/plans/COMMAND_PLANE_VISION.md
- Checklist: docs/plans/COMMAND_PLANE_CHECKLIST.md
- Active track: trace-identity-coverage-2026-05 (command-plane is QUEUED)

LOCKED DECISIONS:
- Species: observatory+cockpit, observatory-leaning
- Container: Web (Next.js) → Desktop (Tauri 2) → Mobile later
- Theme: adaptive + moon/sun toggle
- Density: variable (focused / overview)
- 3D: 2D canonical; 3D opt-in per zone; <View>-per-zone mandatory; 60fps locked target
- IA: 7 verb-zones (COCKPIT/TALK/WATCH/JUDGE/MAP/SENSE/REMEMBER); shared grammar, NOT shared chrome; asymmetric depth; hex positioning frame (never rendered)
- Cadence: heterogeneous per zone, NO "heartbeat" metaphor language in code
- Stack: Next 16 + React 19.2 + Tailwind v4 + R3F + drei + Motion 3D + TanStack Query
- Type: Commit Mono primary
- Palette: Nihonga / iwa-enogu (Sumi / Gofun / Tetsu / Gunjō / Rokushō / Murasaki / Ōdo / Bengara / Shu)
- Motion: 3 vocabularies (motion.instant / motion.navigate / motion.ambient)
- Signature: numbers as protagonist; Rokushō dot ambient pulse

YOUR LANE: {LANE}
YOUR TASK: {TASK}
ACCEPTANCE: {ACCEPTANCE}

CONSTRAINTS:
- Do not add dashboard/API surface unless implemented and manifest-registered (active track non-goal)
- Do not modify terminal_bridge.py (over LOC ceiling)
- Do not commit the untracked codex-composer page
- Do not skip pre-commit hooks
- Read CLAUDE.md "GitNexus" section before editing any symbol; run gitnexus_impact

REPORT VIA SendMessage to team-lead. Evidence-cited, terse, file:line refs.
```

---

## Recommended team shapes per phase

### Phase 0 — Pre-flight (mechanical, no design decisions)
- Solo Claude session. No team needed.
- Skills: `/verification-before-completion` (verify each fix at runtime)

### Phase 1 — Tokens + palette revaluation
- 2-agent team:
  - `token-archaeologist` — audit every consumer of existing tokens, build the rename/revalue map
  - `palette-implementer` — execute the value swap, kill `glowText()`, add `motion.ts`
- Skills: `/frontend-design`, `/everything-claude-code:design-system`

### Phase 2 — Cockpit v2 (2D)
- 4-agent team:
  - `registry-builder` — custom shadcn registry + 6 primitives
  - `cockpit-refactor` — port the 4 cockpit components to new tokens
  - `craft-reviewer` — Linear-grade scrutiny each commit (this is the existing scout from `command-plane-frontier`; reuse them)
  - `visual-regression-baseline` — Storybook + Argos baselines
- Skills: `/frontend-design`, `/everything-claude-code:nextjs-turbopack`, `/claude-api:webapp-testing`

### Phase 3 — 3D benchmark
- 3-agent team:
  - `r3f-craft-specialist` (existing scout) — implement center zone in R3F
  - `benchmark-runner` — measure 60fps on M2 Air 8GB; report at each iteration
  - `fallback-wirer` — Tab toggle + auto-fallback logic
- Skills: `/frontend-design`, `/superpowers:verification-before-completion`

### Phase 4-5 — Per-zone migration
- Spawn one agent per zone simultaneously (zones are independent once Phase 2-3 ship). Use `team_name=command-plane-redesign` and `name={zone}-builder`.
- Idle teammates can be reused across zones.

### Phase 6 — Final adversarial acceptance
- Re-spawn the original `command-plane-stress-test` team (red-team, fractal-architect, craft-reviewer, r3f-craft-specialist) to validate the shipped state.

---

## Coordination rules

1. **Before claiming a checklist item:** SendMessage to team-lead announcing the item ID. Team-lead either confirms or redirects.
2. **Before committing:** verify `make governance-all` passes locally. If docops drift, run `python3 scripts/docops/check_docops_integrity.py --write-auto-sections` against staged-only state (stash unstaged first, then commit, then unstash).
3. **After commit:** update `COMMAND_PLANE_CHECKLIST.md` with `[x]` + commit hash, in the same PR.
4. **Conflict with another agent:** `gh pr list --search "<keyword>"` before pushing. If overlap, coordinate or close-as-redundant.
5. **Hitting an undecided question:** add it to the "Cross-cutting open decisions" section in the checklist. Do not unilaterally decide.
6. **Hitting a real bug:** open a `BR-NNN` entry in `BROKEN_REGISTER.md`. Reference it in the PR.

---

## Living-state pointer (where to look for "what's next")

When a new session opens cold and wants to help, the priority order is:

1. **`make onboard`** — current active track, prerequisites, completion criteria, next items
2. **`docs/plans/COMMAND_PLANE_CHECKLIST.md`** — what's done, what's next, in command-plane specifically
3. **`docs/plans/2026-05-21-command-plane-design-lock.md`** — the spec; do not re-debate
4. **`git log -10 --oneline`** — what just shipped
5. **`docs/plans/COMMAND_PLANE_VISION.md`** — the why, in <2 minutes

If `make onboard` shows trace-identity-coverage still ACTIVE: this work is queued. Help with trace-identity, or do Phase 0 mechanical items only.

---

## Hand-off rituals

### Closing a session (any agent)
- Update `COMMAND_PLANE_CHECKLIST.md` "Last touched" with date + summary
- Mark any newly-completed items
- Add any new open decisions to "Cross-cutting open decisions"
- Commit checklist update in the same PR as the work it tracks

### Opening a session
- Read this doc (you are here)
- Read the checklist
- Run `make onboard`
- Pick one item from the checklist that's `[ ]` and not blocked
- Announce intent before starting

### Closing the track (when trace-identity ships and command-plane opens)
- Move command-plane-redesign-2026-05 block from `queued_tracks` to `active_track` in `ACTIVE_TRACK.yaml`
- Set verified_at, prerequisites, completion_criteria from the checklist's Phase-1-completion items
- Run `make onboard` to verify
- This is governance work — coordinate with @AmitabhainArunachala first

---

## What makes this multi-agent-safe

| Failure mode | Mitigation |
|---|---|
| Two agents do the same work | Checklist items have IDs; agents announce claims via SendMessage; PR collision detect catches dupes |
| New agent re-runs the grill | Spec is locked, in `2026-05-21-command-plane-design-lock.md`; vision in `COMMAND_PLANE_VISION.md`; both pointed to from this doc |
| Decisions drift between sessions | Lock doc is the source of truth; check vs spec on every PR |
| Off-track work creeps in | Active track non-goals reminder in every team-spawn template |
| Checklist rots | Update is part of the commit, not a separate task |
| Aesthetic discipline slips | `craft-reviewer` scout reused as a per-PR reviewer agent |

---

## When in doubt

Re-read the vision doc. Then read this doc. Then start.
