# Terminal TUI tmux Harness

This is the operator-side harness for driving the Bun TUI through a real TTY.

## Scripts

- `scripts/start_terminal_tui_tmux.sh`
- `scripts/stop_terminal_tui_tmux.sh`
- `scripts/status_terminal_tui_tmux.sh`
- `scripts/capture_terminal_tui_tmux.sh`
- `scripts/send_terminal_tui_keys.sh`

Shared boundary: `scripts/terminal_tui_tmux_common.sh` — all of the scripts
above run tmux on a private managed server socket, not the default one.

Defaults:

- tmux session name: `dharma_terminal_tui` (`DHARMA_TERMINAL_TMUX_SESSION`)
- tmux socket: `CODEX_MANAGED_helm_tui` (`DHARMA_TERMINAL_TMUX_SOCKET`), under
  `TMUX_TMPDIR` `/tmp` (`DHARMA_TERMINAL_TMUX_TMPDIR`)

Root provenance is fail-closed: if `DHARMA_TERMINAL_ROOT` points at a tree
other than the one the launcher lives in (paths are resolved to their real
locations first), the
launcher refuses with exit 2 unless `DHARMA_TERMINAL_ROOT_OVERRIDE_OK=1` is
set. The launcher also verifies liveness of the Python bridge process after
boot and tears down a session it created if the boot is unhealthy.

## Commands

Start:

```bash
cd /Users/dhyana/dharma_swarm
./scripts/start_terminal_tui_tmux.sh
```

Stop:

```bash
cd /Users/dhyana/dharma_swarm
./scripts/stop_terminal_tui_tmux.sh
```

Status:

```bash
cd /Users/dhyana/dharma_swarm
./scripts/status_terminal_tui_tmux.sh
```

Capture:

```bash
cd /Users/dhyana/dharma_swarm
./scripts/capture_terminal_tui_tmux.sh 80
```

Send keys:

```bash
cd /Users/dhyana/dharma_swarm
./scripts/send_terminal_tui_keys.sh C-r
./scripts/send_terminal_tui_keys.sh h e l l o
```

Attach directly (the session lives on the managed socket, so a plain
`tmux attach -t dharma_terminal_tui` will not find it):

```bash
env -u TMUX TMUX_TMPDIR=/tmp tmux -L CODEX_MANAGED_helm_tui -f /dev/null attach -t '=dharma_terminal_tui'
```

`./scripts/status_terminal_tui_tmux.sh` prints the exact attach and capture
commands for the current configuration.

## Important implementation note

The harness starts the TUI as a real TTY process inside tmux. Do not run the
Ink app through `tee` or another stdout pipe during launch, because that breaks
TTY semantics and makes keyboard interaction unreliable.

Logging is handled with `tmux pipe-pane` instead.

## Computer Use status

Playwright MCP was installed and configured for Codex at:

- `/Users/dhyana/.codex/config.toml`
- `/Users/dhyana/.local/npm/bin/playwright-mcp`

That is useful for browser automation after Codex restarts and reloads MCP
servers. It does not itself provide full desktop control of the TUI. For the
Bun terminal surface, this tmux harness is the current practical interaction
path from Codex.
