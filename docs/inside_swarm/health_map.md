# Inside-Swarm Health Map

Purpose: map what a high-level AI agent experiences when trying to operate
inside `dharma_swarm` through native surfaces. This file records orientation,
commands tried, organs touched, observations, confusions, bugs, lag,
inefficiencies, and recurring broken themes.

## Operating Frame

- Agent lane: `codex_composer`, coordinating with `opus_composer`.
- Repo: `/Users/dhyana/dharma_swarm`.
- Branch observed: `qwen/spine-adoption`.
- First principle: use native swarm pathways before external harnesses.
- Claim discipline: label entries as Observed, Inferred, or Proposed.
- Current shared receipts: `.swarm_collab/codex_opus/receipts/`.

## Session Log

### 2026-06-06T11:10:43Z - Codex entry

Observed:
- `make onboard` completed successfully and is the authoritative entrypoint
  for current operating reality.
- Active strategic track is
  `runtime-truth-reconciliation-2026-06`; onboarding reports 11/11 criteria
  complete and shippable, with next action "declare next track".
- Worktree is already dirty with 232 files according to onboarding and
  many untracked work packets under `reports/agentops/work_packets/`.
- Live ops surfaces: 15 total, status distribution `blocked=1`, `live=6`,
  `stale=1`, `stopped=7`.
- Broken register reports 23 total items, 5 open-like. Top open items:
  `BR-003` self-evolution apply gate partial, `BR-004` cron split-brain
  partial, `BR-005` algedonic stream degenerate steady-state partial.
- Runtime truth latest receipt is a failed run:
  `rr_run_3367f3ada6b34d30_failed_run`, task `t-review`, runner `a-review`,
  heartbeat/progress `stalled_by_artifact_progress`, completion
  `blocked_by_receipt`.
- Runtime DB has 3400 `delegation_runs`, 3400 `task_claims`, 60
  `runtime_receipts`, 17 `execution_identities`, and 0
  `idempotency_records`.
- Toolbelt status reports `dkeys` available, but process environment is
  missing `OPENAI_API_KEY`, `OPENROUTER_API_KEY`, `OLLAMA_API_KEY`,
  `NVIDIA_NIM_API_KEY`, `GOOGLE_AI_API_KEY`, and `GEMINI_API_KEY`.
- Toolbelt status explicitly says provider/API-key truth is local operator
  state and must be checked through safe local probes, not inferred from repo
  files alone.

Observed tool health:
- `codebase-retrieval` refused the repo because the directory contains too
  many files to index without an `.augmentignore`.
- Context+ semantic search timed out after 600 seconds on a broad repo query.
- Context+ static analysis timed out after 600 seconds on the touched bridge
  file.
- GitNexus responded, but warned that FTS is unavailable and it is using a
  read-only graph keyword fallback.
- GitNexus `detect_changes` returned "No changes detected" despite a local
  untracked regression test and previously dirty working tree, so it was not
  treated as authoritative for this lane.
- Broad `rg --files` / broad exact search are overwhelmed by generated
  feasibility workspaces inside `reports/revenue_wedge/.../repo/...`.

Inferred:
- The first inside-agent friction is orientation scale, not a single bug:
  naive semantic search and exact search both degrade on the current repo
  shape.
- Provider/model routing must remain a major health theme, but process-env
  absence is not the same as local key absence.
- Runtime truth and live ops are partially alive but showing stalled/blocked
  execution evidence, so native mission/agent flows need direct exercise.

### 2026-06-06T11:15Z - Native CLI and TUI pass

Observed:
- `dkeys list` shows live OpenRouter, Gemini, and Z.ai Coding lanes, plus
  zero-funds X.ai and Z.ai Global lanes.
- `python -m dharma_swarm.api_key_audit --no-agentic` reports
  `configured_keys=0`, `configured_auth_ok=0`, `default_completion_ok=0`, and
  `default_agentic_ok=0`.
- `/api/chat/status` on `127.0.0.1:8420` reports ready via provider
  `openrouter`, model `anthropic/claude-opus-4-6`, with multiple available
  chat profiles.
- `dgc status` reports pulse log last heartbeat
  `2026-06-02T17:57:36.754188+00:00`, health `stale`, daemon PID `1621`, and
  snapshot age around 14.5 hours.
- `dgc runtime-status` reports 3400 claims, 3400 runs, 23 active runs, and
  zero active/acked claims.
- `dgc mission-status` reports core intelligence lane 2/6 wired, with misses
  for `circuit_breaker`, `planner_executor`, `think_points`, and
  `traceability_fields`.
- `dgc doctor` reports overall FAIL with one failure: `env_autoload` has no
  env bootstrap detected in active launcher paths.
- `dgc doctor` also reports stale PID files, stale `dgc_health` snapshot,
  split/thin message bus usage, missing router env values, missing
  unattended Claude bare-mode auth, missing fasttext model, and missing Redis
  router URL.
- `dgc agent list` shows the five preset agents `researcher`, `coder`,
  `scout`, `reviewer`, and `witness` all on `claude-sonnet-4-20250514`.
- `dgc agent runs` shows those preset/conductor runs failing at turn 0 on
  Anthropic credit/key errors, while OpenRouter-specific witness presets have
  successful high-token/tool runs.
- `dgc self-improve status` reports disabled, last cycle `20260605_155305`,
  improved false, delta `+0.0%`, and rollback after tests failed.
- `dgc self-improve history` shows repeated cycles with `+0.0%` or negative
  deltas.
- `dgc dharma status` reports kernel integrity OK, 25 principles, but corpus
  total claims is only 1.
- `dgc stigmergy --json` reports density 8461, with hot path
  `chetana/chetana.ingest` at 2079.
- `dgc hum` reports strongest resonances but recent associations shown from
  2026-05-25, indicating this surface can be stale relative to stigmergy.
- `dgc loop-status` reports no loop supervisor state yet.
- `dgc daemon-status` reports stale PID file and pulse log last heartbeat on
  2026-06-02.

Observed TUI:
- `dgc ui` identifies `dgc dashboard` as the primary terminal TUI.
- First compact `dgc dashboard` run rendered the Bun TUI, then degraded
  because the Python bridge crashed on
  `ModuleNotFoundError: No module named 'dharma_swarm.terminal_engine.events'`.
- The local dirty-file regression in `dharma_swarm/terminal_bridge.py` was
  restored to the tracked HEAD import shape: TUI command owner
  `dharma_swarm.tui.commands.system_commands`, adapter owner
  `dharma_swarm.tui.engine.adapters`, event owner
  `dharma_swarm.tui.engine.events`.
- Added regression coverage in `tests/test_terminal_bridge.py`.
- Bridge stdio smoke now emits `bridge.ready` and `session.bootstrap.result`.
- Compact `dgc dashboard` now reaches `DHARMA UP`, `operator state live`, and
  `route ready | codex:gpt-5.4 | configured` without the bridge traceback.
- PTY keystroke injection did not visibly enter the prompt, so a real chat
  turn through the TUI remains unverified in this harness.
- Stopping `dgc dashboard` with Ctrl-C previously exited through the Python
  wrapper with a `KeyboardInterrupt` traceback from
  `subprocess.run(..., check=True)`.
- That wrapper path is now locally repaired: compact PTY dashboard reached
  `DHARMA UP`; interrupt exit printed `DGC dashboard stopped.` with no Python
  traceback. In this PTY harness, the first Ctrl-C appeared to be consumed by
  the Bun TUI and the second Ctrl-C reached the Python wrapper.
- Direct tmux input can exercise the Bun TUI at 80x24 when bypassing the
  repo helper scripts.
- `/help` previously routed to Control and then produced no visible body in
  Chat because chat-targeted slash command output was globally suppressed.
- `/help` now remains on Chat and renders the help body in the Chat transcript
  while chat-control commands such as `/reset` remain quiet.
- A plain prompt typed while focused on Control now immediately switches back
  to Chat and shows the submitted user line plus execution trace.
- A plain prompt `Reply with exactly OK.` remained `Turn 1 | running` after
  25 seconds; the bridge process stayed alive with no child provider process
  under it. This is a separate provider/session execution blocker, not the
  now-repaired prompt visibility issue.
- `scripts/start_terminal_tui_tmux.sh` and
  `scripts/send_terminal_tui_keys.sh` hang under this Codex command wrapper,
  even though direct `tmux new-session`, `tmux capture-pane`, and
  `tmux send-keys` work. Literal input support was added to the send helper,
  but the helper-wrapper hang remains open.

Inferred:
- Provider truth is currently split across at least `dkeys`, process-env
  runtime audit, and live chat API status.
- The preset agent failure is not a whole-swarm failure; it is a routing and
  auth/defaulting split. OpenRouter-specific agents prove the swarm can run
  when routed to a live lane.
- The TUI bridge boot crash was a stale local namespace regression, not a
  missing architecture. The maintained owner is the `tui` package.
- The model policy/bootstrap surfaces disagree: the bridge bootstrap selected
  `codex:glm-5:cloud`, while model policy still reported selected model
  `gpt-5.4`.

Verification:
- `python3 -m py_compile dharma_swarm/terminal_bridge.py tests/test_terminal_bridge.py`
- `pytest -q tests/test_terminal_bridge.py tests/test_command_contract.py tests/tui/test_system_commands.py`
  passed: 23 tests.
- `bun run typecheck` in `terminal/` passed.
- `printf '{"id":"1","type":"session.bootstrap","prompt":"who are you"}\n' | python3 -m dharma_swarm.terminal_bridge stdio`
  returned `bridge.ready` and `session.bootstrap.result`.
- `env COLUMNS=80 LINES=24 dgc dashboard` reached `DHARMA UP` /
  `operator state live`.

## Organs Touched

### Onboarding / Governance

Observed:
- `make onboard` is the repo-sanctioned first command.
- The current active track forbids creating new truth stores, daemons, receipt
  systems, or authority surfaces.
- Parallel lanes are allowed if owner, branch/worktree or packet, scope,
  verification command, and receipt path are declared.

### Runtime Truth Spine

Observed:
- Read-only projection exists in onboarding.
- Latest runtime receipt is failed/stalled/blocked and missing machine fields:
  `mission_id`, `idempotency_record`, `artifact_refs`.
- Runtime status has active runs but zero active claims, which is confusing
  from inside the swarm.

### Live Ops

Observed:
- Live ops cockpit is read-only; it shows state and commands/policies but
  executes nothing.
- Surface status has several stopped and stale surfaces.

### Provider / Model Routing

Observed:
- Local `dkeys` has live keys for some providers.
- Process environment lacks the expected provider key variables.
- Live API chat reports OpenRouter ready.
- Known naming mismatches are documented:
  `GEMINI_API_KEY` vs `GOOGLE_AI_API_KEY`, and `NVIDIA_API_KEY` vs
  `NVIDIA_NIM_API_KEY`.
- `dgc agent list` previously hid provider truth by showing only model names.
- `dgc agent wake --model gemini` left the preset provider on Anthropic and
  only changed the model string, so the agent still reached the failing
  Anthropic lane.

Fixed locally:
- The five preset agents now use `claude_code:claude-sonnet-4-6` instead of
  the stale Anthropic API model `claude-sonnet-4-20250514`.
- `dgc agent wake --model ...` now copies preset identity before mutation and
  resolves TUI aliases / explicit `provider:model` routes into provider plus
  model.
- `--model gemini` now constructs `openrouter:google/gemini-2.5-pro`.
- `dgc agent list` now prints provider and model.
- `dgc_cli.main()` now bootstraps local runtime env before dispatch, including
  `~/.dharma/agent_keys.env`, and normalizes dkeys aliases.
- The runtime env bootstrap owner now lives in `dharma_swarm/api_keys.py` and
  is shared by both `dgc_cli` and `api_key_audit`.
- Unresolved shell placeholders such as `GOOGLE_AI_API_KEY=$GEMINI_API_KEY`
  are treated as absent, so they no longer block alias normalization.
- `scripts/load_runtime_env.sh` now sources `~/.dharma/agent_keys.env`
  directly.
- `ProviderType.OPENROUTER` now defaults to `moonshotai/kimi-k2.5` instead of
  deprecated `xiaomi/mimo-v2-pro`.
- `dgc doctor --quick` now reports `env_autoload` PASS and `provider_env`
  PASS; overall doctor status is WARN instead of FAIL.
- `dgc provider-smoke --json` now verifies local Ollama successfully through
  the live daemon model `deepseek-v3.1:671b-cloud`, with installed model source
  `runtime_api`.
- Provider smoke preserves Ollama manifest tags as fallback, filters
  embedding-only local models out of chat probes, and stops model packs after
  the first success or provider-wide terminal failure.
- HTTP 402 / insufficient-credit responses are now classified as
  `insufficient_credits` instead of generic `error`.
- At repair time, `python -m dharma_swarm.api_key_audit --no-agentic`
  verified OpenRouter and Google AI configured, auth OK, and default
  completion OK. Current OpenRouter completion is now separately blocked by
  account credits.

Remaining:
- NVIDIA NIM remains missing `NVIDIA_NIM_API_KEY`.
- OpenRouter currently reports `insufficient_credits`; this is an account
  balance condition, not a deprecated model or route-default failure.

### Code Intelligence

Observed:
- GitNexus index exists with 119380 symbols, 204826 relationships, and 300
  execution flows per `AGENTS.md`.
- Current GitNexus query path is degraded by unavailable FTS.
- Context+ broad query and static analysis timed out.

### TUI / Terminal Bridge

Observed:
- TUI renders and can reach live operator state after local bridge regression
  repair.
- TUI dashboard wrapper now handles `KeyboardInterrupt` cleanly, so normal
  wrapper-level stop does not print a traceback.
- TUI command input is now verified through direct tmux at 80x24:
  `/help` stays on Chat and renders command output.
- Plain prompt entry from Control is now visible in Chat immediately after
  submit.
- The actual provider response path is still blocked for the active
  `codex:gpt-5.4` route: the TUI shows a running turn but receives no
  assistant text or session end after 25 seconds.
- Real-terminal stop ergonomics remain worth checking because the PTY harness
  needed a second Ctrl-C to exit after the first was consumed by the Bun TUI.

## Major Themes

1. Orientation substrate is brittle at repo scale.
2. Runtime truth is visible but points at stalled/blocked work.
3. Provider key truth is split between stored local state, process env, and
   API profile status.
4. Preset agent defaults previously pointed at a failing Anthropic lane; the
   native preset path is now locally repaired, but live provider env bootstrap
   remains split.
5. Existing governance strongly warns against parallel substrates.
6. Generated workspaces under `reports/` make naive search and indexing noisy.
7. The terminal is close to usable. Bridge boot, `/help` visibility, prompt
   visibility, and wrapper-level stop are now locally repaired; active
   provider turn completion and script-wrapper reliability remain open.
