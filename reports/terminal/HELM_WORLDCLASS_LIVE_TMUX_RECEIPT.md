# Helm Worldclass Terminal Live Tmux Receipt

Date: 2026-06-29
Track: `helm-worldclass-terminal-2026-06`
Receipt role: live compact-terminal proof for the current checkout.

## Verdict

PARTIAL LIVE PROOF.

The current checkout's terminal boots in a real tmux session at `80x24` and
renders the chat shell without off-screen content in the captured frame. This
receipt does not certify the full world-class helm branch, golden corpus, or
merge readiness.

## Commands Run

- `bun run typecheck` in `terminal/` -> passed.
- `bun test tests/app.test.ts` in `terminal/` -> 208 pass, 0 fail.
- `python3 -m py_compile dharma_swarm/terminal_bridge.py` -> passed.
- `env COLUMNS=80 LINES=24 timeout 8 bun run start` -> rendered the shell but
  failed raw-mode because stdin was not a real TTY.
- `env SESSION_NAME=dharma_terminal_tui_codex_80 DHARMA_TERMINAL_TUI_STATE_DIR=/Users/dhyana/.dharma/terminal_tui_codex_80 scripts/start_terminal_tui_tmux.sh`
  -> started disposable tmux session.
- `tmux display-message -p -t dharma_terminal_tui_codex_80 '#{window_width}x#{window_height}'`
  -> `80x24`.
- `env SESSION_NAME=dharma_terminal_tui_codex_80 scripts/capture_terminal_tui_tmux.sh 120`
  -> captured the pane below.
- `env SESSION_NAME=dharma_terminal_tui_codex_80 scripts/stop_terminal_tui_tmux.sh`
  -> stopped the disposable session.

## Captured 80x24 Pane

```text
╭──────────────────────────────────────────────────────────────────────────────╮
│ DHARMA  UP | codex:gpt-5.4 | REA | Chat                                      │
│ configured                                                                   │
╰──────────────────────────────────────────────────────────────────────────────╯

[Chat] Mission Repo Commands Models Ontology ▸

╭──────────────────────────────────────────────────────────────────────────────╮
│ Chat                                                                         │
│ Live operator exchange, assistant output, and command spillover that still   │
│ belongs in chat.                                                             │
│                                                                              │
│ Dharma Terminal                                                              │
│ Keyboard-first operator shell. Backend bridged over stdio.                   │
│ Use plain prompts or slash commands. Chat carries the conversation; the      │
│ surrounding tabs expose runtime, tools, and system state.                    │
╰──────────────────────────────────────────────────────────────────────────────╯

╭──────────────────────────────────────────────────────────────────────────────╮
│ >                                                                            │
╰──────────────────────────────────────────────────────────────────────────────╯

╭──────────────────────────────────────────────────────────────────────────────╮
│ status  route confirmed -> codex:gpt-5.4                                     │
│ route  ready | codex:gpt-5.4 | configured                                    │
│ keys  Tab tabs | Enter send | ^B side | ↑/↓ scroll                           │
╰──────────────────────────────────────────────────────────────────────────────╯
```

## Blockers

- `scripts/terminal_guardian_preflight.sh` is missing in this checkout, so the
  required terminal-guardian preflight could not run.
- `terminal/scripts/golden_capture.sh`, `terminal/scripts/ratchet.sh`,
  `terminal/tests/golden/120x40/chat.txt`, and
  `terminal/tests/compactShell.test.tsx` are still missing in this checkout.
- The sibling worktree `/Users/dhyana/dharma_helm_build` contains a mature helm
  branch and closeout packet, but its terminal surface has substantial drift
  from this checkout. Copying only marker files would create false readiness.

