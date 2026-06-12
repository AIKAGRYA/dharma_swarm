# Operator Design Feedback — live-pixel review, 2026-06-12

Source: real screenshots of the booted TUI at 244x68 (offline hermetic), reviewed by the
operator's conductor + three independent design critics (color/identity, layout/hierarchy,
interaction/discoverability). Screenshot: /tmp/helm_live_120x40.png. This file is
DESIGN TRUTH for S4 (theme) and S7 (UX) features — read it before any UI work.
It does not change feature definitions; where it names a NEW requirement, that lands
as an operator-sanctioned feature addition at a batch boundary (receipted), not mid-run.

## What the pixels showed (ground truth)

- The app owns no canvas: background is the terminal profile's `#222733`, not `night`.
  Body text is cool ANSI white, not `foam` paper-cream. The Hokusai identity currently
  exists ONLY in the ScenicStrip.
- 21 bordered containers on one screen (15 tab pills + 6 chrome boxes) — the named
  "container soup" anti-pattern, shipped. Plus a stray ~3-col bordered "T" sliver at the
  chat pane's left edge (collapsed-pane rendering bug — track and kill).
- ~22% of a 68-row screen carries information; bottom ~20 rows are dead; the footer
  floats mid-screen. The stack is height-blind in BOTH directions (overflows at 40 rows,
  strands space at 68).
- Status contradicts itself: OFFLINE (red) + state READY (green) on one row; offline
  said 3x, model name 3x, ready 3x, mode 2x — 14 status tokens, 3 surfaces, no single
  source of truth.
- Footer keys line: 26 bindings in one ~230-col row, at 2.16:1 contrast (illegible), with
  unlabeled chord runs (`^G ^R ^O ^M ^A ^P ^E ^T ^Y panes`) AND three byte-collisions:
  `^I`=Tab, `^M`=Enter, `^H`=Backspace in legacy encoding. Missing entirely: `?`, Enter-to-send, quit.
- The composer (the most important element) is fixation #4-5: thin box, dim `>`, no
  placeholder, no cursor, no focus signal — while "mode tab navigation" above and below
  implies typing won't compose.
- Red used twice for expected hermetic-offline (should be `ink ○`/`persimmon ⚠`; reserve
  `vermilion` for danger). The one line that earns a status color ("backend offline,
  retrying") is plain white, with no retry count/countdown/remedy.
- ScenicStrip: best color on screen, 8 rows tall (budget: ≤2), left-aligned with 74% dead
  band at width. Its palette ≈ the spec palette — the app must rise to the strip, not
  vice versa. LANDMINE: strip paints own BG `#1f2637`; against `night #10141C` it becomes
  a visible floating slab. Operator ruling: treat strip band as a raised `indigo` surface
  (its BG may change to `indigo #1A2233` — this is the ONE sanctioned exception to
  verbatim preservation, decided 2026-06-12).

## Binding directives for S4/S7 coders (in addition to the token table)

1. **Own the canvas**: root-level `night #10141C` background; `foam #DCD7BA` body text.
   This single change carries most of the identity.
2. **Status truth**: offline = `ink ○` or `persimmon ⚠`, never vermilion; suppress READY
   wherever the bridge is down; color the footer status line per AGENT_STATES.
3. **One accent discipline**: `wave` = THE chrome accent (brand + active item);
   `ridge` = focused border; the teal-everywhere pattern dies. `parchment` re-aims at
   seer/model-identity surfaces (e.g. the model name), off mode/focus labels.
4. **Legibility floor**: keys line and inactive labels to `stone` (≥4.5:1); `ink` is
   decoration-only; de-bold empty values (`unknown/idle/0` render in `stone`, not bold foam).
5. **De-soup**: target ≤2 borders per frame (focused composer + at most one focused pane);
   header/summary/footer become unbordered lines separated by spacing. Borders are not
   separators; space is.
6. **Salience order on first paint**: composer (accent border + visible cursor + ghost
   placeholder `> Type a message · / commands · ? keys`) > transcript > one status line >
   ≤2 rows scenic. Kill the user-facing "tab navigation mode" concept: printable keys
   always reach the composer; chords navigate.
7. **Footer**: ≤1 row, ≤5 per-pane hints + permanent `? help`; everything else lives in
   the `?` overlay. Resolve the `^I/^M/^H` collisions in the keymap table; retire the
   duplicate Tab/arrow pair; digits go to deck jumps.

## NEW requirements not covered by existing features (add at batch boundary as F-157+)

- **Fill law**: transcript flexGrows to claim all spare height; composer pinned beneath;
  status line bottom-anchored. Graded at 244x68: zero dead rows below the footer.
- **Max-width measure**: prose/transcript clamps ~100 cols at wide terminals; no
  full-width border rules; surplus width → gutter or cockpit side panes.
- **Status single-source**: one StatusModel projection; offline/model/ready each appear
  EXACTLY once per frame (gradeable).
- **De-border task**: explicit feature to remove per-widget borders (gradeable:
  borderStyle instances rendered per frame ≤2).
- **Offline that breathes**: retry counter + countdown + `^R retry now` + `○` glyph +
  input-queued promise in the status line.
- **Earned pills / activity badges**: panes render in the bar only with data or active
  subscription; off-screen activity badges (k9s-style).
- **Boot row discipline**: first frame row is app-owned (no shell echo above the UI at
  boot, or explicit accepted-inline decision recorded).
- **"T" sliver bug**: collapsed pane renders as 3-col bordered box — find and fix.

## Evaluator criteria additions (apply when grading S4/S7 features)

- Offline/model/ready each appear exactly once per frame.
- Global keys line ≤1 row with ≤5 hints and zero unlabeled chord runs.
- ≤2 bordered containers per frame.
- Zero dead rows below the status line at 244x68 capture.
- Composer is the highest-salience element on first paint (accent border + cursor + placeholder).
- No vermilion outside genuine danger states.

## LIVE INTERACTION FINDINGS (conductor at the keyboard, 2026-06-12, tmux tour)

Driven by real keystrokes into the running app (offline hermetic, 120x40 then live-resized
to 80x24). Frames at /tmp/helm_tour_*.txt. OBSERVED behaviors, not review opinions:

1. **Typing/echo: GOOD.** Composer echoed instantly; Enter moved the message into the
   transcript as a structured turn. The turn/trace rendering (`◇ Turn 1 | running`,
   trace steps) is a strong foundation — keep it.
2. **BUG — the offline turn lies forever.** Turn 1 showed `running` + optimistic trace
   steps ("bootstrapping context", "selecting route") and never resolved to a
   failed/queued state while the backend was down. The "offline that breathes"
   requirement must include turn-level honesty: offline send → `queued (backend
   offline)` state, never perpetual `running`.
3. **BUG — /help silently swallowed.** Typed `/help` + Enter on Chat: no command echo,
   no response, no error — zero visible feedback. (The adopted baseline includes a
   /help-routing fix whose tests pass; the LIVE behavior still swallows it offline.)
   Rule: no command may ever produce zero visible feedback; minimum is an echoed turn
   with a queued/failed status.
4. **BUG — Shift-Tab navigates FORWARD.** From Repo, BTab x2 landed on Models (forward)
   instead of back toward Chat. Reverse tab navigation is broken or unbound; the keys
   line advertises it anyway.
5. **COPY BUG — Models pane describes itself as "Structured operator transcript."**
   Pane description strings are copy-pasted; audit all 15.
6. **BUG — perpetual "Model policy loading..."** in Models pane while offline; same
   dishonest-pending class as finding 2.
7. **`?` types into the composer** — confirmed no help overlay exists yet (planned S7).
8. **Live resize 120→80: transient artifacts, good recovery.** Stale 120-wide pill
   fragments floated for ~2-5s before compact mode rendered. The compact render itself
   is GOOD: compressed header, one-line scrollable tab bar `◂ Repo Commands [Models] ▸`
   — this exact widget is what F-021 should promote to ALL widths. Parity contract #3
   grading must include a settle-time bound (artifacts gone ≤1s after resize).
9. **Per-pane contextual keys already exist** (Models pane showed `^L refresh models |
   j/k select route | Enter apply | ^X claude opus | ^F codex responsive | ^V cost`) —
   the contextual mechanism is live; the problem is volume (keys block wrapped to 4
   rows at 80x24) and the global cram prepended to it. Model-switch keybinds already
   exist (^X/^F) — S6 should build on them, not reinvent.
10. **"T" sliver confirmed live** in every pane, all widths.

## ABUSE ROUND 2 (conductor, 2026-06-12 ~11:57 local, visible-window computer-use)

Frames: /tmp/abuse_paste.txt, /tmp/abuse_modelswitch.txt, /tmp/helm_abuse_live.png.
Tour regression diff vs 10:12 tour: 0 diff lines on all frames (infrastructure features
changed zero pixels — correct).

11. **PASS — rapid-fire typing**: 60 chars sent with no inter-key delay landed intact
    and instantly in the composer.
12. **NEW P0 BUG — multi-line paste swallowed wholesale.** Bracketed paste of 3 lines
    (incl. unicode ∿≋仏) produced ZERO occurrences anywhere — not in composer, not in
    transcript, no error. Isolation: single-line paste works (bracketed AND raw); the
    bug is newline handling in paste input. Parity contract #1 explicitly requires
    multi-line paste — this needs a feature (F-171 candidate at next boundary):
    multi-line paste shall land in the composer as a multi-line draft (or explicit
    line-join), never be dropped.
13. **BUG (same silent-swallow class as /help) — ^X model-switch gives no feedback
    offline.** On Models pane, ^X (advertised "claude opus") changed nothing visible:
    route display still codex:gpt-5.4, no queued/failed indication. Every advertised
    action must produce visible feedback (extends F-158's rule beyond slash commands
    to keybind actions).
14. **Screenshot shows scrollback ghost-frames** above the live UI in the attached
    terminal (stale earlier render visible above current frame) — same family as
    F-170 boot-row discipline; alt-screen would fix both.

## OPERATOR LIVE VERDICT + CONDUCTOR REAL-BACKEND SESSION (2026-06-12 ~12:30)

**THE OPERATOR FLUNKED THE CURRENT APP** using it live against the real backend:
"totally flunking grade... terrible... super confusing... not even interactive...
slow and clunky." This verdict is the grading baseline. His screenshot + the
conductor's own real-backend session (operator lane, real bridge, real codex)
decoded it into named causes:

15. **Trace noise IS the chat.** "hello?" produced 11 lines of plumbing (Trace
    expanded by default, raw session hex IDs, request numbers, "Turn completed")
    with the actual reply buried beneath. Operator-facing rule: response is the
    star, trace is ONE collapsed line (`✓ 2.3s · codex:gpt-5.4 · ^T details`);
    raw IDs NEVER render in the transcript.
16. **CONFIRMED LIVE — the silent answer drop (worst bug).** Conductor asked the
    real system "who are you and what can you do?" → backend routed it as an
    identity intent → answered via an `assistant` event → TS layer does not handle
    `assistant` events (bridge_events.md unhandled list) → the answer was DISCARDED
    and the turn rendered as "◇ Turn 1 | complete" with NO response text at all.
    The system speaks; the TUI throws the words away and stamps it complete.
17. **No conversation memory + per-turn session teardown.** Both operator turns and
    conductor turns show full bootstrap→session-ended per message (the wire
    mismatch: TS sends history, Python ignores it). Operator's "not interactive"
    = same canned router monologue twice + multi-second-to-minutes turn latency
    dominated by session startup.
18. **Raw JSON error blob dumped into chat** (conductor's first sandboxed attempt):
    a full pretty-printed error object incl. schema_version/timestamps rendered in
    the conversation; AND the failure carried a ✓ checkmark ("✓ Status | session
    failed") with "Turn failed" as a buried sub-bullet. Errors render as one human
    line + status color; glyphs must match semantics; turn state must be loud.
19. **Scenic strip shatters on the operator's actual terminal font** — renders as
    confetti blocks, not Fuji/waves. Art must degrade gracefully or be absent
    (zen default); never assume glyph coverage.
20. **Reprioritization (operator word, 2026-06-12): the felt experience is the
    priority axis.** The chat-experience cluster (trace collapse, assistant-event
    handling, session continuity, turn honesty, zen mode, one-line tabs) is pulled
    forward in pick order ahead of remaining infrastructure depth.
