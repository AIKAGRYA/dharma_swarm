# THE HELM — CONSTITUTION
**Build**: helm/worldclass-20260612 @ `~/dharma_helm_build` (baseline commit `a6ad97362`)
**Loaded by**: every fresh-context coder session, every evaluator session. This file + `spec-forge/features.json` are your entire standing context. Everything else is queried on demand.
**Design canon**: `~/handoffs/helm_tui_design_20260612.md` (WHAT) + `~/handoffs/bun_tui_worldclass_longrun_master_plan_20260611.md` (HOW the loop runs). When this file and those disagree, STOP and write the conflict to the progress file instead of guessing.

---

## 1. IDENTITY AND GOAL

The TUI becomes a **moded instrument** — one engine, three faces. **Zen mode (default)**: Claude-Code-simple — transcript + composer + one thin status line, where the operator lives 80% of the time. **Cockpit mode**: the binocular fusion dashboard — deck bar ([1]Bridge [2]Fleet [3]Missions [4]Models [5]Memory [6]Approvals), Deck 1 = Sakshi pane (gates, R_V, receipts, drift) | Mission River | Drishti pane (world radar, leverage, provider windows), fleet bar, composer, ONE-LAW status line. **Deck focus**: any deck full-screen. Switching: `F2` toggles zen↔cockpit; `/zen`, `/cockpit`, `/deck <name>`; AND natural language through the composer ("switch to the funky dashboard" → intent → `SET_LAYOUT_MODE`). Layout mode is one field in the existing Elm reducer — the 46-variant `AppAction` union in `state.ts` already meets the bar; KEEP it; everything routes through it. The goal of this run: harden `terminal/` in place into the operator interface plane that passes the five parity contracts — typed wire protocol, decomposed god files, Hokusai-futurist truecolor theme, command contract with telos gating and receipts, live delegation tree — verified at every commit by machines, not claims.

## 2. THE HONEST BOUNDARY — surfaces you NEVER refactor

This run is a first-principles revamp of the **operator interface plane** ONLY:
`terminal/` (the TUI), `dharma_swarm/terminal_bridge.py` (+ `terminal_bridge_text.py`),
a new shared `terminal_commands` contract, and read-only projections.

**DO NOT refactor — not one line, not a rename, not a "drive-by fix":**

- `orchestrator.py`
- `agent_runner.py`
- `swarm.py`
- `a2a_bridge.py`
- `spine/**`

These are owned by active tracks with explicit non-goals. The Helm RIDES the spine
(consumes EvidenceReceipts and runtime truth packets); it never becomes an authority
surface. Repo doctrine holds: *read models project truth from owners; they do not
become authority.* Projections read from existing owners (a2a state files, spine
receipts, model_hierarchy, routing_memory.sqlite3, chetana/SMRITI counts, existing
approval queues). No new daemons. No new truth stores.

Helm-action safety: gate the irreversible with proof; gate the reversible with
reality. Reversible operations (pin/switch model, steer text, approve/deny, dispatch
via existing queue, layout/theme) execute instantly and emit a receipt. Irreversible
operations (kill/restart agent, budget edits, loop-config changes) require confirm
modal + telos gate + receipt. **Destructive-action E2E runs against a SANDBOX swarm
only** (own `DHARMA_*` state dir + ports, throwaway agents). The operator's live
daemon gets read-only + reversible commands only. The live fleet is untouchable
tonight.

## 3. THE LOOP YOU ARE INSIDE

- **Strictly sequential.** One fresh-context session per feature. Single lane. NO
  parallel agents — parallelism is for attended sessions only, and this run is
  unattended. You own every file in scope for the duration of your session.
- The progress file is `claude-progress.txt` at the worktree root
  (`/Users/dhyana/dharma_helm_build/claude-progress.txt`, created by the
  initializer; append-only, one block per session: feature id, what changed,
  evidence, re-plans).
- Session protocol: `pwd` → read `git log --oneline -15` + the progress file →
  read `terminal/LESSONS/LESSONS.md` → read `spec-forge/features.json` → pick ONE
  highest-priority feature with `status: "not_started"` whose dependencies are
  satisfied → run the boot smoke BEFORE new work → implement → run the feature's
  verification steps → set `status` → run the full gate ladder (§5) → commit →
  update the progress file → stop.
- **features.json mutation contract:** you may change ONLY the `status` field
  (`not_started` → `in_progress` → `implemented` | `implemented_no_test` |
  `diverged`). The `verified` flag is flipped ONLY by the evaluator after
  independently re-running the feature's verification through the run's real
  sensor (tmux capture-pane text frames) — builders never touch it. All other
  fields are immutable.
- One feature per session. If you finish early, improve the feature's tests or
  its LESSONS entry — do not start a second feature.

## 3b. RUN ENVELOPE — scope fence, caps, stop conditions

- The spec is a 156-feature program (~61h of estimated work). No single run
  attempts all of it: each RUN lands a PREFIX of the P0 set in dependency
  order. RUN-1 declared landing zone: **S0 + S1 complete, S2 underway.**
- Hard caps per run: **max 40 coder sessions** and **max 10 wall-clock
  hours**. The loop HALTs early when either cap is hit — landing short of the
  zone under a cap is a normal outcome, not a failure.
- **Attempts ledger**: a feature that goes RED twice (2 attempts) is set
  `status: "diverged"` with a note in `claude-progress.txt`, and the loop
  moves on — never a third attempt in the same run. The evaluator applies
  this on a feature's second RED (status `diverged` instead of
  `not_started`). Coder sessions enforce it at pick time: before picking a
  feature, skip any with 2 logged failed attempts in `claude-progress.txt`.
- **Systemic halt**: 3 consecutive RED verdicts across DIFFERENT features =
  HALT. Write `VERDICT: HALT systemic` to `claude-progress.txt`; the loop
  runner exits; the operator triages in the morning.

## 4. COMMANDS

All work happens here:

```bash
cd ~/dharma_helm_build/terminal
```

Core verification:

```bash
bun run typecheck        # tsc --noEmit — must be 0 errors at every commit
bun test                 # full suite, ~1.6s — run after every file move
```

tmux boot smoke (L0 — hermetic, no Python bridge needed; the app must degrade
gracefully to "backend offline, retrying"):

```bash
SESS=helm-smoke-$RANDOM; STATEDIR=$(mktemp -d)
tmux new-session -d -s $SESS -x 80 -y 24 \
  "cd /Users/dhyana/dharma_helm_build/terminal && COLORTERM=truecolor DHARMA_PYTHON=/nonexistent/python DHARMA_TERMINAL_STATE_DIR=$STATEDIR DHARMA_TERMINAL_SUPERVISOR_STATE_DIR=$STATEDIR bun run start"
sleep 4; tmux capture-pane -t $SESS -p; tmux kill-session -t $SESS
```

Assert: the captured frame is non-empty and renders the app shell. Insert a short
delay (or poll until the frame changes) between any `send-keys` and `capture-pane`.
Once the S0 boot-script feature lands, prefer `bash scripts/boot_smoke.sh` —
it wraps exactly this one-liner and exits non-zero on an empty frame.

Ratchet check (after the S0 ratchet feature lands):

```bash
bash scripts/ratchet.sh   # prints 3 counters; exits non-zero on ANY regression
```

State isolation — ALWAYS, in every test/CI/evaluator invocation:

```bash
export DHARMA_TERMINAL_STATE_DIR=$(mktemp -d)
export DHARMA_TERMINAL_SUPERVISOR_STATE_DIR=$(mktemp -d)
```

Booting the app without these rewrites the git-tracked
`.dharma-terminal-state.json` (verified live — the file shows as modified in the
baseline worktree right now). The S0 untrack feature removes it from git; until
then, never commit changes to that file.

### Git discipline

- Branch: `helm/worldclass-20260612` only. Never touch other branches; never push.
- **One commit per feature.** The commit lands only after the full gate ladder
  (§5) is green.
- Message format: `helm <F-ID>: <one-line description>`. One feature per
  commit; the features.json status change rides the same commit.
- Never amend or rebase a previous feature's commit. Never force-push. A red
  evaluator verdict is handled by `git revert` of that feature's commit (rule 6,
  §6 below: first RED → not_started, second RED → diverged) — history stays
  append-only.
- `git status` must be clean after your commit, except files explicitly listed as
  known-inert in LESSONS (currently: none). Untracked junk = not clean.

## 5. GATE RULES — every commit, no exceptions

Run in this order; ALL must pass before `git commit`:

1. **Typecheck green**: `bun run typecheck` → 0 errors.
2. **Test failure-set rule**:
   - **Before F-001 lands**: the baseline is *characterized-red* — 527 tests, 65
     fail in ANY checkout not located at `/Users/dhyana/dharma_swarm` (path
     literals, see §8). The gate is: the set of failing test NAMES must be a
     subset of the characterized 65. **No NEW failing test name may appear.**
     The characterized list is committed by the initializer at
     `spec-forge/baseline-failures.txt`; diff your failures against it.
   - **After F-001 lands**: strict green. 527+ tests, 0 failures, every commit.
3. **Boot smoke green**: the tmux one-liner (or `scripts/boot_smoke.sh`) renders
   a non-empty app frame at 80×24 with the Python bridge absent.
4. **Ratchets — three counters that may ONLY move down** (baselines from the
   characterized baseline `a6ad97362`):

   | Ratchet | Baseline | End target |
   |---|---|---|
   | Max source-file line count (worst file: `protocol.ts`) | **4,064** | ≤ 400 |
   | Sidebar.tsx/RepoPane.tsx duplicated top-level functions | **40** | 0 |
   | `Record<string, unknown>` occurrences in protocol.ts | **97** | ~1 (single typed ingress) |

   Any counter above its last recorded value = hard reject; fix or revert before
   committing. `scripts/ratchet.sh` records the new low-water mark on success.
5. **Golden frames** (after the S4 capture lands): text-frame diff vs
   `tests/golden/` at 80×24, 100×30, 120×40 must be clean. Goldens are captured
   AFTER the theme migration; re-capture is allowed only for an intentional
   visual change with an evaluator-approved note in the progress file.

Self-certification never terminates anything. "Done" = the gates say done.

## 6. REQUIRED LANGUAGE (lines 1–5 are lab-measured snippets: verbatim, do not paraphrase. Lines 6–7 are house doctrine: the meaning binds; the wording may be restated)

1. **Anti-tamper:** "It is unacceptable to remove or edit tests because this could
   lead to missing or buggy functionality."
2. **Careful completion:** "Only mark features as passing after careful testing."
3. **Clean state:** "Leave the environment in a clean state, appropriate for
   merging to a main branch."
4. **Anti-test-gaming:** "Implement a solution that works correctly for all valid
   inputs, not just the test cases. If the task is unreasonable or infeasible, or
   if any of the tests are incorrect, please inform me rather than working around
   them."
5. **Grounded progress:** "Before reporting progress, audit each claim against a
   tool result from this session. Only report work you can point to evidence for;
   if something is not yet verified, say so explicitly."
6. **Rollback-on-red:** an evaluator RED verdict triggers git revert of that
   feature's commit. First RED: status returns to not_started with a failure
   note in the progress file. Second RED in the same run: the evaluator sets
   status to diverged — never a third attempt (§3b attempts ledger). A red
   feature never stays merged.
7. **Re-planning authority:** at session start, after reading progress + features,
   the agent MAY re-prioritize feature ORDER based on what it learned (log the
   re-plan + reason to the progress file). Feature definitions, steps, and
   verification criteria remain immutable.

One clarification for this run's pre-F-001 window: rule 1 forbids removing or
editing tests to make them pass. F-001 itself edits test FIXTURES (path literals →
dynamic `REPO_ROOT`) as its specified work — that is the feature, not tampering.
Any other test edit must be demanded by the feature's own steps.

## 7. THEME LAW — Hokusai-futurist

Read terminal/src/theme.ts before any UI code; never hardcode a hex outside theme.ts and ScenicStrip.tsx.

Design truth for all S4/S7/UX work: spec-forge/knowledge/DESIGN_FEEDBACK_OPERATOR_20260612.md — read it before any UI feature.

That sentence is the first line of every coder session for a reason: the token
file, not prose, holds 30+ fresh contexts to one visual identity.

**The discovery this theme is built on**: theme.ts's 12 token NAMES are already
ukiyo-e (`ink indigo river wave foam parchment persimmon vermilion moss pine mist
stone`) but currently resolve to 7 collapsed ANSI-16 colors. The migration is
**zero-rename**: keep all names, upgrade values to truecolor, add the new tokens.
theme.ts is the verified single mutation point — 15/16 components consume THEME
exclusively.

### Token table (contrast ratios WCAG-computed vs bg #10141C / raised #1A2233)

SURFACES
| Token | Hex | Role |
|---|---|---|
| `night` | `#10141C` | NEW — app background |
| `indigo` | `#1A2233` | EVOLVED — raised surface |
| `harbor` | `#223249` | NEW — selected/overlay surface |

BORDERS
| Token | Hex | Role |
|---|---|---|
| `river` | `#2D4F67` | EVOLVED — decorative-border-only (2.13 — never carries meaning) |
| `ridge` | `#658594` | NEW — focused border (4.69) |

TEXT
| Token | Hex | Role |
|---|---|---|
| `foam` | `#DCD7BA` | primary text, warm paper-cream (12.71 / 10.96) |
| `mist` | `#C8C093` | secondary text (10.02) |
| `stone` | `#8992A7` | tertiary/meta (5.91; on harbor only 4.16 → meta-only there; selected-row body text = foam) |
| `ink` | `#727169` | decoration ONLY, never information (3.76) |

ACCENTS
| Token | Hex | Role |
|---|---|---|
| `wave` | `#7E9CD8` | crystalBlue, accent-witness — THE one decorative chrome accent (6.70) |
| `crest` | `#7FB4CA` | NEW — running/streaming (8.15) |
| `parchment` | `#DCA561` | Red-Fuji amber, accent-seer (8.43) |
| `sunlit` | `#E6C384` | NEW (10.98) |
| `bengara` | `#8F2D12` | NEW, FILL-ONLY (foam-on-bengara 5.67 ✓; raw bengara text 2.24 ✗ — never as foreground) |

STATUS
| Token | Hex | Role |
|---|---|---|
| `moss` | `#98BB6C` | success (8.48) |
| `pine` | `#7AA89F` | done / quiet-ok (6.96) |
| `persimmon` | `#FF9E3B` | warning (8.96) |
| `vermilion` | `#FF5D62` | danger (6.14) |
| `iris` | `#957FB8` | spawning (5.27) |

F-071 creates and exports AGENT_STATES with **glyph+color pairs — color is
never the sole signal**: running crest ▶, thinking wave ◉, spawning iris ◌,
blocked persimmon ⚠, error vermilion ✖, done moss ✓, idle stone ·, offline ink ○.

Soft variants pre-verified for a morning operator swap (do NOT apply overnight):
bg `#16161D`; success `#7AA89F`.

### Migration rule (gradeable, ratchet-style)

After the theme value swap, `THEME.indigo` and `THEME.river` may appear ONLY as
`backgroundColor` / `borderColor` props — grep-verified (design criterion #8).
They are surface/border tokens now; any use as text color is a regression.

### ScenicStrip — the sanctioned art exemption

`components/ScenicStrip.tsx`'s 25 hand-tuned constants are the audited "good feel"
(Apr 3-4 design push, commit `70b947491` lineage). **Preserved verbatim.** Do not
"clean it up", retokenize it, or fold it into THEME. It is the ONE file besides
theme.ts allowed to hold hex literals.

### Motif budget + glyph law

- ≤ 2 rows of scenic chrome total: header ink-gradient Great-Wave strip
  `['#003153','#2D4F67','#658594','#7FB4CA','#DCD7BA']`; at 80×24 the header
  collapses to a rule only.
- Inline motifs (all single-width verified): `∿` streaming, `≈` syncing,
  `≋` throughput, braille `⣀⣠⣴⣶⣿` sparklines, `▁▂▃▄▅▆▇█` gauges.
- **BANNED glyphs**: `〜` U+301C and `～` U+FF5E (ambiguous width — they corrupt
  column math on real terminals).

### Named slop penalties (evaluator auto-deducts; treat as banned)

teal-everywhere · blinking status dots · container soup · rainbow ANSI ·
pure `#FF0000` · purple-gradient defaults.

### Layout law

**120×40 overflow is design criterion #1**: ShellHeader + Operator Summary
currently scroll off-screen at all three graded sizes (two-row bordered tab
pills cost 6+ rows). The fix is a one-line tab bar at ALL widths. Preserve the
compactShell ≤90-width degradation — it is verified passing; do not break it
while fixing the wide case.

### Dead weight (removed in S4, not before)

`cfonts`, `figlet`, `ink-big-text`, `ascii-art`, `ascii-artist` are unused —
remove. `ink-gradient` becomes live (header strip). Delete orphaned
`src/assets/hokusai_strip.ansi` + `hokusai_strip_timg.ansi` (git-recoverable).

### Truecolor pre-flight (S0 gate)

`COLORTERM=truecolor` must reach the app; tmux RGB terminal-features on; a test
capture must show `38;2` sequences — otherwise every overnight aesthetic grade
judges quantized colors and the night's theme work is graded blind.

## 8. KNOWN FAILURE MODES (read before touching anything)

1. **Path-literal hermeticity (the characterized 65).** ~250 hardcoded
   `"/Users/dhyana/dharma_swarm"` path literals at baseline (count-agnostic:
   the binding criterion is zero remaining; repo_root fixtures + frame
   assertions) make 65 tests fail in any checkout not at that exact path —
   including THIS worktree. F-001 replaces them with a
   dynamic `REPO_ROOT` derived via `import.meta.dir`: mechanical,
   behavior-neutral, verified as "suite green in any checkout path". Until F-001
   lands, the failure-set gate in §5 applies.
2. **State-file mutation race.** Booting the app rewrites the git-tracked
   `.dharma-terminal-state.json`. Every run of the app or tests must set
   `DHARMA_TERMINAL_STATE_DIR` (and `DHARMA_TERMINAL_SUPERVISOR_STATE_DIR`) to a
   temp dir. The S0 feature untracks the file. Never commit a mutated state file.
3. **Supervisor global-state matching.** `resolveSupervisorStateDir` matches
   `run.json.repo_root` against the runtime `REPO_ROOT` — a second source of
   checkout-path coupling, fixed alongside F-001. If supervisor-dependent tests
   behave differently here than at `~/dharma_swarm`, this is why.
4. **120×40 overflow.** See §7 Layout law. Any new chrome row must be justified
   against the ≤2-row motif budget and re-checked at all three graded sizes.
5. **app.test.ts is a shared choke (442KB).** Nearly every App-touching feature
   edits it. The strictly sequential loop makes this safe — but only if you never
   leave it half-edited at commit time, and the early split-per-feature work
   happens before heavy App features. Test files obey the same single-writer
   logic as src files.
6. **Ink Static-region discipline.** The dynamic region must NEVER exceed the
   viewport; history goes through `<Static>` (ink#382). Long output must never
   wipe scrollback (freeze-then-dump and erase-storms are the two dominant
   failure classes). Memoize list rendering; treat `frames.length` as the
   re-render budget.
7. **No reasoning-echo phrasing.** Never write prompt text, criteria, comments,
   or LESSONS entries that instruct a model to echo/transcribe/explain its
   internal reasoning as response text — it trips the reasoning_extraction
   refusal classifier and silently degrades the run to a fallback model
   mid-flight.
8. **No prestige adjectives in generator-facing text.** "Museum-quality",
   "world-class", "stunning" in criteria cause documented aesthetic convergence.
   Functional criteria only; quality bars live in the evaluator, expressed as
   PASS/FAIL conditions with cited frame lines.
9. **Plain conditions, not CRITICAL/MUST stacks.** Current models overtrigger on
   stacked CRITICAL/MUST/NEVER trigger-language. Write conditions as "Use X
   when..." / "X applies when...". Every anti-anchor is a negation+redirect pair
   (don't do X → do Y instead), never a bare negation.
10. **Bun pin drift.** package.json still pins `bun@1.1.38`; installed is 1.3.11
    (all 527 tests + PTY probe pass under it). The S0 feature re-pins to 1.3.11
    and commits `bun.lock` (currently untracked — a reproducibility hole). Any
    future Bun bump requires PTY smoke green first.
11. **tmux capture timing.** A `capture-pane` immediately after `send-keys` races
    the render. Sleep briefly or poll-until-changed between them, in every
    script and every manual check.

## 9. FILE MAP — terminal/src (line counts at baseline a6ad97362)

| File | Lines | Role |
|---|---|---|
| `index.tsx` | 6 | Entrypoint — renders `<App/>` via Ink. |
| `app.tsx` | 3,190 | Root App component; 750-line App fn with a 485-line `useInput` — S3 decomposes into keymap dispatch table (mode→key→AppAction) + extracted pure functions + layout-mode field. |
| `state.ts` | 658 | Elm-style `reduceApp(state, action)` + 46-variant `AppAction` union. Meets the bar as-is — preserve its reducer architecture. KEEP — route everything through it. |
| `protocol.ts` | 4,064 | The god file: bridge event parsing, 97 `Record<string,unknown>`, 37 `type === "..."` string-sniffs, text-scraping as data plane. S2 target: typed `BridgeEvent` ingress, then decomposition into ≤400-line modules. |
| `types.ts` | 575 | Shared types; the `Canonical*` types are 80% of the raw material for the `BridgeEvent` discriminated union. |
| `bridge.ts` | 122 | Python bridge subprocess: lazy respawn, JSONL framing. GOOD as-is — the weak point is what surrounds it, not this file. |
| `persistence.ts` | 2,139 | Terminal state save/load (`.dharma-terminal-state.json`); honors `DHARMA_TERMINAL_STATE_DIR`. Split lands late (S5-era). |
| `executionLog.ts` | 640 | Execution-log model + formatting. |
| `repoControlPreview.ts` | 572 | Repo-control preview derivations. |
| `shellControls.ts` | 217 | Shell control definitions (untested leaf — test feature exists). |
| `routePolicy.ts` | 164 | Model-routing policy display logic. |
| `verification.ts` | 149 | Verification status derivations (untested leaf). |
| `mockContent.ts` | 138 | Mock/demo content for offline rendering. |
| `transcriptFormatting.ts` | 125 | Transcript text formatting helpers. |
| `freshness.ts` | 84 | Staleness/freshness computation (untested leaf). |
| `theme.ts` | 14 | THE token file — 12 ukiyo-e names, currently ANSI-16 values; single mutation point for the S4 truecolor swap. |

components/

| File | Lines | Role |
|---|---|---|
| `Sidebar.tsx` | 2,585 | Repo/agent sidebar — shares 40 identically-named copy-pasted functions with RepoPane (dedup target → one `repoDerive` module). |
| `RepoPane.tsx` | 2,323 | Repo detail pane — other half of the 40-function duplication. |
| `ControlPane.tsx` | 1,149 | Control surface pane; split lands S5-era. |
| `ActivityPane.tsx` | 225 | Activity feed pane. |
| `ScenicStrip.tsx` | 160 | Hokusai scenic strip — 25 hand-tuned constants, PRESERVED VERBATIM (§7). |
| `AgentsPane.tsx` | 121 | Agent list pane. |
| `ApprovalsPane.tsx` | 90 | Approvals queue pane. |
| `SessionsPane.tsx` | 85 | Sessions list pane. |
| `TranscriptPane.tsx` | 63 | Transcript rendering pane. |
| `OperatorSummaryBand.tsx` | 63 | Operator summary band (part of the 120×40 overflow). |
| `ShellHeader.tsx` | 61 | Header (part of the 120×40 overflow; gains the Great-Wave strip). |
| `TabBar.tsx` | 55 | Tab bar — becomes one-line at ALL widths (§7 Layout law). |
| `ModelPicker.tsx` | 49 | Model pin/switch picker. |
| `StatusFooter.tsx` | 47 | ONE-LAW status line. |
| `PaneSwitcher.tsx` | 34 | Pane focus switching. |
| `Composer.tsx` | 20 | Input composer. |

tests/ — `app.test.ts` (the 442KB choke), `protocol.test.ts`,
`controlPane.test.ts`, `persistence.test.ts`, `repoPane.test.ts`,
`sidebar.test.ts`, `state.test.ts`, `executionLog.test.ts`,
`repoControlPreview.test.ts`, `routePolicy.test.ts`,
`transcriptFormatting.test.ts`, `operatorSummaryBand.test.tsx`.
Golden frames land under `tests/golden/` (S4+). Build scripts land under
`scripts/` (S0).

Backend surface in scope (edits allowed): `~/dharma_helm_build/dharma_swarm/terminal_bridge.py`,
`terminal_bridge_text.py`, the new `terminal_commands` contract module, and
read-only projection modules. Nothing else in `dharma_swarm/` (§2).

## 10. SPRINT MAP (features.json backbone, P0 → P2)

features.json `component` fields (s0-…s8-…) supersede the master plan's sprint
numbering wherever they differ.

- **S0 Verifiers + hygiene**: F-001 path hermeticity (the observed smoke-gate
  feature); tmux boot script; ratchet script; `verify:all`; ESLint flat +
  Prettier; untrack state file; Bun re-pin 1.3.11 + commit bun.lock; truecolor
  preflight. *No refactor commits before S0 is green.*
- **S1 Bridge truth**: terminal_bridge.py event-vocabulary inventory → typed
  `BridgeEvent` union typed against reality, not guesses → single validated
  ingress where `bridge.onEvent` lands.
- **S2 protocol.ts decomposition**: 4,064 → ≤400-line modules, tests follow.
- **S3 app.tsx decomposition**: 485-line useInput → keymap dispatch table;
  extract pure functions; layout-mode state field + zen/cockpit/deck switching
  (key, slash command, NL intent).
- **S4 Theme migration**: theme.ts truecolor swap + migration rule + 120×40
  one-line tab bar fix + dead-dep removal + golden capture.
- **S5 Command Contract v1**: ~15 core commands gated+receipted
  (`intent → Command{id, args, gate_class} → telos gate → execute →
  EvidenceReceipt → projection → panes update`) + projections
  (fleet/missions/models) + cockpit Deck 1 with real data.
- **S6 Delegation tree + model deck**: live fan-out rendering, one A2A hop,
  pin/switch mid-flight, routing-governance E2E suite (THE ONE WAY: ladder
  ordering, pin honored, dead-key fallback rendered) + sandbox-swarm helm
  actions (kill/restart/budget, gated).
- **S7 UX bar**: keybinding registry, `?` overlay, per-pane hints, focus
  manager; parity contracts 1-4 graded at 3 sizes.
- **S8 CI + polish**: GitHub Actions `verify:all` + tmux smoke. Ink 6.8/React 19
  is a SEPARATE LATER phase — not tonight. Morning Max-lane round trip happens
  with the operator present.

The five parity contracts the evaluator grades through tmux frames: (1) input
feel — instant echo under load, multi-line paste, ↑/↓ history, Esc interrupts
streaming, Ctrl+C exits clean; (2) streaming + rendering — token streaming
without freeze-then-dump, markdown/code blocks, scrollback intact while
streaming; (3) flicker + resize — no `[2K[1A` erase-storms steady-state,
80×24↔120×40 resize leaves no duplicated UI; (4) commands + discoverability —
slash autocomplete, `?` overlay with real keybindings, per-pane hints, NL
mode-switch switches; (5) transparent delegation + model switching — live
delegation tree with model labels across one real fan-out incl. an A2A hop,
pin reflected mid-flight.

## 11. THE COMMAND CONTRACT (S5+ backbone — read before any command/projection work)

One typed command engine; every operation (chat, pin model, approve, kill agent)
is the same shape — gated command in, receipt out:

```
intent (NL or key) → Command{id, args, gate_class} → telos gate → execute
                   → EvidenceReceipt → projection → panes update
```

- `gate_class` is one of two values, mirroring §2:
  - `reversible` — executes immediately, emits a receipt. Pin/switch model,
    steer text to a mission, approve/deny, dispatch via existing queue,
    layout/theme changes.
  - `irreversible` — confirm modal + telos gate + receipt, and in this run
    executes ONLY against the sandbox swarm. Kill/restart agent, budget edits,
    loop-config changes.
- The contract lands as a `terminal_commands` module consumed by both the Python
  bridge and the TUI. CLI adoption is later — not tonight.
- Every executed command produces an `EvidenceReceipt`; the receipt, not the
  command's own return value, is what projections and panes render. No receipt =
  the UI shows nothing happened, because nothing provable happened.
- Projections are read-only over existing owners:
  - fleet — a2a state files + agent identities
  - missions — spine EvidenceReceipts + runtime truth packets
  - models — model_hierarchy + routing_memory.sqlite3 + dkeys liveness
  - memory — chetana/SMRITI counts
  - approvals — existing queue surfaces
- A projection never writes to its source. A pane never reads a source directly;
  it reads the projection.

## 12. ROUTING-GOVERNANCE E2E DOCTRINE (S6)

E2E calls go through THE ONE WAY: `resolve_runtime_provider_config()` →
`create_runtime_provider()`, ordered by `model_hierarchy` (most-powerful-first,
live-fallback). Never hardcode a model string anywhere in this build — tests
included. The E2E suite asserts GOVERNANCE behavior, not free-vs-Max economics:

1. A cheap task lands on a free-tier model because the ladder says so.
2. A pinned mission routes to its pin.
3. A dead key → fallback fires AND the TUI visibly shows the fallback.
4. One delegation hop crosses A2A (hermes inbox task or NATS dispatch with an
   EvidenceReceipt) and renders in the delegation tree.

dkeys liveness, provider racing, and EWMA are visible instrument surfaces, not
hidden internals. Budget protection is the ladder's own free-first ordering.
The one claude_code (Max-plan) round trip is a FINAL MORNING GATE run with the
operator present — never fired unattended overnight.

## 13. EVALUATOR INTERFACE + DESIGN PHRASING RULES

- The evaluator is a separate context. It never sees your traces, only your
  commits, the gates, and tmux `capture-pane` text frames at 80×24, 100×30,
  120×40 (plus `/usr/bin/script` raw escape capture for flicker checks). It
  types real keystrokes via `tmux send-keys` and grades functionally.
- Evaluator output format: PASS/FAIL per criterion + cited frame lines only. If
  you write or extend any evaluator-facing criterion, it takes that shape — a
  condition checkable against a frame, never a vibe.
- The evaluator alone flips `verified` in features.json, and a red verdict
  triggers the rollback rule (§6, line 6).
- Design work phrasing (applies to UI features and any prompt text you emit):
  art direction over prescription — goal + named aesthetic + success criteria +
  anti-defaults. Within a session: never settle on the first obvious choice; if
  a color or layout feels obvious, deliberately explore alternatives; commit to
  a distinct direction. The named slop penalties (§7) are auto-deducted.
- Restating §8 items 7-9 because they gate the run itself: no reasoning-echo
  instructions anywhere; no prestige adjectives in generator-facing criteria;
  plain "Use X when..." conditions instead of CRITICAL/MUST stacks; every
  anti-anchor is a negation+redirect pair.

## 14. ENVIRONMENT REFERENCE

| Variable | Value in this run | Why |
|---|---|---|
| `DHARMA_PYTHON` | `/nonexistent/python` in smoke tests | Forces the hermetic no-bridge path; the app must degrade to "backend offline, retrying". Unset/real only in bridge-integration features. |
| `DHARMA_TERMINAL_STATE_DIR` | `$(mktemp -d)` in every test/CI/evaluator run | Prevents the tracked-state-file mutation race (§8.2). |
| `DHARMA_TERMINAL_SUPERVISOR_STATE_DIR` | `$(mktemp -d)` likewise | Same isolation for supervisor state (§8.3). |
| `COLORTERM` | `truecolor` (must reach the app through tmux) | Without it every aesthetic grade judges quantized colors (§7 pre-flight). |
| Sandbox swarm `DHARMA_*` | own state dir + ports, throwaway agents | The ONLY place irreversible commands execute (§2). |

Bun: installed 1.3.11; package.json re-pins to 1.3.11 in S0; `bun.lock` gets
committed in S0 (untracked at baseline). Ink 5.1 + React 18 are the pinned UI
stack for this run — the Ink 6.8/React 19 evaluation is a separate later phase.

## 15. WHEN STUCK + GLOSSARY

When stuck (any of: a gate you cannot turn green within your session, a feature
whose steps contradict observed reality, a dependency feature that turns out
unimplemented despite its status):

1. Do not improvise scope. Do not edit the feature definition (§6, line 7 —
   order may change, definitions may not).
2. Set the feature's `status` to `diverged` with a note in the progress file
   stating exactly what you observed vs what the spec says (command output, file,
   line).
3. Revert any partial work that would leave the gates red. Commit nothing red.
4. Append the trap to LESSONS so the next session does not re-pay for it.
5. Stop the session. The evaluator and the morning operator pass triage
   `diverged` features; an honest stall beats a confident wrong build.

Glossary (terms a cold session will hit):

- **Spine** — dharma_swarm's runtime truth layer; emits runtime truth packets
  and EvidenceReceipts. The Helm consumes; never writes.
- **EvidenceReceipt** — the proof artifact a gated command or spine action
  emits; the unit of truth that projections render.
- **Telos gate** — the dharmic governance check a Command passes before
  execution; irreversible commands always cross it.
- **Projection** — a read-only view computed from an owner's data (fleet,
  missions, models, memory, approvals). Truth lives with the owner.
- **A2A** — the agent-to-agent bus (`~/.dharma/a2a_bus/`, plus NATS lanes);
  S6's delegation hop crosses it once, with a receipt.
- **THE ONE WAY** — the single sanctioned model/key routing path
  (`resolve_runtime_provider_config()` → `model_hierarchy` ladder; keys only
  via `~/.dharma/agent_keys.env`). No second way exists; do not invent one.
- **Sakshi / Drishti** — witness pane (gates, R_V, receipts, drift) and
  strategic-intel pane (world radar, leverage, provider windows) on Deck 1.
- **ONE-LAW status line** — the single thin status line; the only always-on
  status chrome in zen mode.
- **Characterized 65** — the baseline failing-test set caused by checkout-path
  literals (§8.1), listed in `spec-forge/baseline-failures.txt`.

## 16. LESSONS PROTOCOL — terminal/LESSONS/LESSONS.md

- `terminal/LESSONS/LESSONS.md` is the run's single append-only memory file
  across fresh contexts. The initializer (Step 7) seeds it with the theme law
  (§7 first line) as its opening line.
- **At session start**: read `terminal/LESSONS/LESSONS.md` (it is short) right
  after the progress file. It exists because a previous session paid for the
  knowledge.
- **At session end**: when you hit anything non-obvious — a gotcha, a flaky
  behavior, a fix that took more than one attempt, a trap for the next session —
  APPEND one dated line per lesson to `terminal/LESSONS/LESSONS.md`:

  ```
  [2026-06-12] [F-0NN] <one line: symptom → cause → what to do instead>
  ```

- Append only. Never rewrite, reorder, or delete prior entries. If a prior
  lesson proves wrong, append a correction that names the entry it corrects.
- Lessons are notes, not doctrine: a lesson never overrides this constitution,
  features.json, or the gate ladder.

## 17. SESSION CLOSE CHECKLIST

1. Gate ladder green (§5) — typecheck, failure-set/strict tests, boot smoke,
   ratchets, goldens where applicable.
2. `status` set on exactly one feature; `verified` untouched.
3. One commit, message per §4, tree clean.
4. Progress file updated: feature id, what changed, evidence (actual command
   outputs you ran this session), any re-plan + reason.
5. LESSONS appended if anything non-obvious was learned.
6. Stop. The next fresh context takes the next feature.
