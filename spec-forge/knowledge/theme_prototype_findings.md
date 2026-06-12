# Theme Prototype Findings — Hokusai truecolor swap, verified live 2026-06-12

Prototype worktree: `/tmp/helm-theme-proto` (detached at fe7da0d03, LEFT ALIVE for conductor
screenshots). Frames: `/tmp/helm-theme-proto-frames/`. Verified diff:
`spec-forge/knowledge/theme_prototype.diff`. tmux sessions killed after capture.

## Headline results

1. **TEST-NEUTRAL: 527 pass / 0 fail BOTH before and after the truecolor swap.**
   Baseline (original ANSI-name theme, this worktree): 527 pass, 0 fail, 2838 expects, 12 files.
   Truecolor theme: 527 pass, 0 fail, 2838 expects. `tsc --noEmit` green.
   **Zero tests assert ANSI color names.** The expected "tests that assert color names break"
   risk DOES NOT EXIST at this HEAD. Mechanism: bun test runs non-TTY, so Ink/chalk renders at
   color level 0 — color values never reach `lastFrame()` output, only text/glyphs do.
   Consequence for S4: the value swap itself is free; golden frames in `tests/golden/pre-theme`
   are plain-text and unaffected. The real S4 risk is NOT the swap — it is any companion change
   that alters TEXT/layout (one-line tab bar, border removal), which WILL move golden frames.

2. **Truecolor pipeline proven end-to-end.** Hermetic boot (DHARMA_PYTHON=/nonexistent/python,
   both state dirs to mktemp, COLORTERM=truecolor) at 120x40 and 80x24; SGR captures contain
   `38;2` sequences with the exact spec hexes (203 occurrences in the 120x40 frame, zero
   legacy 3x/9x ANSI codes). Per-token presence in first-paint frames:
   | token | 38;2 RGB | 120x40 | 80x24 |
   |---|---|---|---|
   | foam | 220;215;186 | 3 lines | 3 |
   | stone | 137;146;167 | 10 | 8 |
   | ink | 114;113;105 | 21 | 4 |
   | wave | 126;156;216 | 6 | 2 |
   | parchment | 220;165;97 | 1 | 1 |
   | persimmon | 255;158;59 | 1 | 0 |
   | indigo→ridge sub | 101;133;148 | 3 | 3 |
   | river→crest sub | 127;180;202 | 14 (Sessions frame) | — |
   | mist / moss / pine / vermilion | — | 0 on first paint | 0 |
   mist/moss/pine/vermilion absence is app-state, not pipeline: their call sites (agent states,
   success/danger rows) don't render on the hermetic-offline first frame. vermilion=0 also
   matches the operator finding that the one line earning a status color ("backend offline,
   retrying") is plain foam/white today.

## Indigo/river call-site census (migration rule criterion #8)

`THEME.indigo` — 3 uses, ALL borderColor, ZERO Text uses (already criterion-#8 compliant):
- `src/components/Composer.tsx:12` (borderColor — the composer box)
- `src/components/ActivityPane.tsx:178` (borderColor)
- `src/components/ShellHeader.tsx:28` (borderColor)

`THEME.river` — 6 uses: 4 borderColor + **2 Text VIOLATIONS** of the migration rule:
- `src/components/OperatorSummaryBand.tsx:38,50` (borderColor)
- `src/components/ControlPane.tsx:1085` (borderColor)
- `src/components/SessionsPane.tsx:27` (borderColor)
- **`src/components/OperatorSummaryBand.tsx:51`** — `<Text color={THEME.river} bold>Operator Summary</Text>` ← must move off river before #2D4F67 lands
- **`src/components/ActivityPane.tsx:214`** — raw log entry Text color ← must move off river

## Invisible-text traps found (and prototype substitutions)

Editing theme.ts ONLY (per task), two spec values would have gone invisible:
- **indigo #1A2233**: all 3 call sites are borders; #1A2233 borders vanish on a dark canvas —
  including the Composer border, the element the operator ranked highest-salience. Prototype
  substitutes **ridge #658594** (the §7 focused-border token, 4.69:1). NOTED in theme.ts header.
- **river #2D4F67** (2.13:1, spec says "never carries meaning"): the 2 Text call sites above
  would be illegible. Prototype substitutes **crest #7FB4CA** (§7, 8.15:1, same Great-Wave
  ink-gradient family). NOTED in theme.ts header.
Real S4 sequencing: migrate the 2 river-as-Text call sites to another token FIRST, decide the
border policy (de-soup kills most borders; indigo becomes a raised SURFACE bg), THEN land the
true #1A2233/#2D4F67 values. Landing spec values before the call-site migration = invisible
composer border + invisible Operator Summary title.

## Other verified facts S4 should bank

- **theme.ts is genuinely the single mutation point**: zero hardcoded `color="..."` literals
  in src/ outside THEME consumption; ScenicStrip keeps its 21 verbatim hexes (sanctioned art
  exemption). One file edit re-skins the whole app.
- **`ridge` does not exist in theme.ts** — operator directive #3 ("ridge = focused border")
  and §7 require S4 to ADD tokens (night, harbor, ridge, crest, sunlit, bengara, iris), not
  just swap the 12.
- **§7 criterion #1 confirmed live**: at 120x40, ShellHeader + OperatorSummaryBand scroll off
  entirely (two-row bordered tab pills cost rows 1–7); header tokens (foam title, river band)
  never paint on the graded first frame. The one-line tab bar fix is what makes header theming
  visible at all.
- **"T" sliver bug confirmed** in this build too: 3-col bordered `│T │` box left of the main
  pane at both sizes (frame_120x40.txt lines 19–27).
- chalk honors COLORTERM=truecolor under tmux default TERM — no tmux terminal-features tweak
  was needed for the app side; capture -e re-emits stored RGB faithfully.
- Boot is fast and clean offline: rendered within ~1s of session create; stderr logs at
  /tmp/helm-theme-proto-frames/boot{120,80}.err.

## Artifacts

- `/tmp/helm-theme-proto-frames/frame_120x40.txt` + `.sgr.txt` (settled Chat frame)
- `/tmp/helm-theme-proto-frames/frame_120x40_sessions.txt` + `.sgr.txt` (Sessions pane, river borders live)
- `/tmp/helm-theme-proto-frames/frame_80x24.txt` + `.sgr.txt` (compact mode)
- `/tmp/helm-theme-proto-frames/theme_truecolor.ts` (the applied theme, also live in the worktree)
- `/tmp/helm-theme-proto-frames/bun_test_truecolor.log` (full 527-green run)
- `/tmp/helm-theme-proto-frames/statedirs.txt` (hermetic state dirs used)
