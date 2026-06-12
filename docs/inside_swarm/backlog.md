# Inside-Swarm Backlog

This backlog is generated from inside-agent experience. Items should be moved
or linked to the canonical Broken Register only after evidence is strong enough
and ownership is clear.

## Open

### ISH-001 - Repo-scale orientation tools degrade on broad search

Status: open
Category: orientation, tooling
Evidence:
- `codebase-retrieval` refused `/Users/dhyana/dharma_swarm` as too large
  without `.augmentignore`.
- Context+ semantic search timed out after 600 seconds on a broad native
  entrypoint query.
- Context+ static analysis timed out after 600 seconds on a touched-file
  check.
- Broad exact search is overwhelmed by generated nested repos under reports.
Impact:
- A new high-level agent can easily form false conclusions from incomplete or
  noisy search.
Next:
- Identify canonical ignore/scope patterns for code-intelligence tools.
- Prefer `make onboard`, GitNexus targeted query, and scoped `rg` paths.

### ISH-002 - Provider truth split between local key store, env, and API

Status: partially repaired
Category: provider-routing
Evidence:
- `dkeys list` shows live OpenRouter, Gemini, and Z.ai Coding.
- `bash scripts/runtime/codex_toolbelt_status.sh` reports provider env vars
  missing.
- `python -m dharma_swarm.api_key_audit --no-agentic` reports zero configured
  keys.
- `/api/chat/status` reports ready via OpenRouter.
- `dgc doctor --quick` previously failed `env_autoload`.
Impact:
- Native agents can fail or appear unavailable depending on which surface
  they consult.
Repair:
- Added canonical runtime env bootstrap helpers to
  `dharma_swarm/api_keys.py`.
- `dharma_swarm/dgc_cli.py` and `dharma_swarm/api_key_audit.py` now use the
  same bootstrap path.
- Bootstrap loads local env/key files including `~/.dharma/agent_keys.env` and
  normalizes dkeys aliases such as `GEMINI_API_KEY -> GOOGLE_AI_API_KEY`.
- Unresolved shell placeholders such as `GOOGLE_AI_API_KEY=$GEMINI_API_KEY`
  are treated as absent rather than valid keys.
- Updated `scripts/load_runtime_env.sh` to source
  `~/.dharma/agent_keys.env` directly for shell/daemon launchers.
- Replaced the deprecated OpenRouter default model
  `xiaomi/mimo-v2-pro` with `moonshotai/kimi-k2.5`.
- Repaired `dgc provider-smoke` local Ollama selection:
  it now asks the live Ollama daemon for `/api/tags`, preserves manifest tags
  as fallback, filters embedding-only models out of chat probes, and tries the
  strongest installed chat model before missing generic defaults.
- Provider smoke now stops a provider model pack after the first success, or
  after provider-wide terminal failures such as missing config, auth failure,
  or insufficient credits.
- HTTP 402 / insufficient-credit provider responses are classified as
  `insufficient_credits` rather than generic `error`.
Verification:
- `dgc doctor --quick` now reports `env_autoload` PASS, `provider_env` PASS,
  and overall WARN instead of FAIL.
- `dgc provider-smoke --json` now verifies local Ollama successfully through
  `deepseek-v3.1:671b-cloud` with installed model source `runtime_api`.
- At repair time, `python -m dharma_swarm.api_key_audit --no-agentic`
  reported `configured_keys=2`, `configured_auth_ok=2`, and
  `default_completion_ok=2` for OpenRouter and Google AI; current OpenRouter
  completion is separately blocked by account credits.
- Broad provider/doctor/agent/TUI seam tests passed: 336 tests.
- Provider-smoke focused tests passed: 75 tests.
Remaining:
- NVIDIA NIM remains missing `NVIDIA_NIM_API_KEY` in provider smoke.
- OpenRouter now reports `insufficient_credits`; this is an account/balance
  condition, not a model routing or deprecated-default failure.

### ISH-003 - Runtime truth latest receipt is stalled/blocked

Status: open
Category: runtime-truth, mission-execution
Evidence:
- `make onboard` reports latest runtime receipt
  `rr_run_3367f3ada6b34d30_failed_run`.
- Task `t-review`, runner `a-review`, heartbeat/progress
  `stalled_by_artifact_progress`, completion `blocked_by_receipt`.
- Missing machine fields include `mission_id`, `idempotency_record`, and
  `artifact_refs`.
- `dgc runtime-status` reports 23 active runs but zero active/acked claims.
Impact:
- Inside-agent mission state may not be actionable or resumable from native
  runtime truth alone.
Next:
- Exercise `ds-goal status` / native agent run listing if available.
- Inspect runtime receipt owner before changing anything.

### ISH-004 - Existing Broken Register already identifies key partial organs

Status: open
Category: broken-register, self-improvement
Evidence:
- Onboarding top open items include `BR-003` self-evolution apply gate,
  `BR-004` cron split-brain, and `BR-005` algedonic stream degenerate
  steady-state.
Impact:
- New inside-agent findings should be reconciled with these existing BR items
  instead of creating duplicate repair tracks.
Next:
- Read `docs/state/BROKEN_REGISTER.md` and link confirmed inside-agent
  observations to the correct BR IDs.

### ISH-005 - TUI chat input path was confusing and partly invisible

Status: partially repaired
Category: TUI, input-handling, agent-experience
Evidence:
- `dgc dashboard` now reaches `DHARMA UP` and `operator state live`.
- Direct tmux input can type into the Bun TUI at 80x24.
- Before repair, `/help` routed to Control and produced no visible help body
  in Chat.
- Before repair, a plain prompt typed from Control submitted to Chat but left
  the operator staring at Control, making the turn look lost.
Impact:
- A high-level agent operating from inside the TUI could not trust whether a
  command or prompt had been accepted.
Repair:
- `/help` now targets Chat instead of Control.
- Chat-targeted slash command output is still suppressed for chat-control
  commands such as `/reset`, but `/help` is allowed to render its help body.
- Plain prompts now activate Chat before appending the user line and execution
  trace.
Verification:
- `cd terminal && bun run verify:command-routing` passed: 325 tests.
- Compact 80x24 direct tmux TUI showed `/help` body in Chat.
- Compact 80x24 direct tmux TUI showed a prompt submitted from Control as
  `Turn 1 | running` in Chat with the user line and trace visible.
Remaining:
- The active provider turn did not complete; tracked separately as `ISH-012`.
- The repo tmux helper scripts are unreliable under this Codex wrapper;
  tracked separately as `ISH-011`.
Next:
- Continue with provider/session execution after bootstrap.
- Recheck from the user's real terminal once the helper-wrapper issue is
  isolated.

### ISH-006 - Preset agents default to failing Anthropic lane

Status: resolved locally
Category: provider-routing, agent-wake
Evidence:
- `dgc agent list` shows the five preset agents on
  `claude-sonnet-4-20250514`.
- `dgc agent runs` shows recent preset/conductor runs failing at turn 0 on
  Anthropic key/credit errors.
- OpenRouter-specific witness presets successfully ran with real tokens and
  tools.
- Root cause in `dharma_swarm/autonomous_agent.py`: preset wake reused the
  shared preset `AgentIdentity`, and `--model` changed only `identity.model`
  while leaving `identity.provider` on Anthropic.
Impact:
- Native agent wake appears broken for default presets even though other
  provider lanes work.
Repair:
- Preset agents now route to `claude_code:claude-sonnet-4-6`.
- `cli_wake` copies preset identity before applying overrides.
- `--model` now resolves TUI aliases and explicit `provider:model` routes into
  provider plus model.
- `dgc agent list` now prints provider and model.
Verification:
- `pytest -q tests/test_autonomous_agent.py tests/test_autonomous_agent_router_path.py tests/tui/test_model_routing.py tests/test_terminal_bridge.py tests/test_command_contract.py tests/tui/test_system_commands.py`
  passed: 96 tests.
- `python -m py_compile dharma_swarm/autonomous_agent.py dharma_swarm/terminal_commands/agents.py tests/test_autonomous_agent.py`
  passed.
- Dry route check confirmed `--model gemini` constructs
  `openrouter:google/gemini-2.5-pro` without live provider spend.
Remaining:
- Provider env/bootstrap truth is still split and tracked separately.

### ISH-007 - TUI model bootstrap and model policy disagree

Status: open
Category: TUI, model-routing
Evidence:
- Bridge bootstrap smoke selected `codex:glm-5:cloud`.
- Same payload's model policy reported selected model `gpt-5.4`.
Impact:
- The operator sees inconsistent route truth at exactly the moment they are
  trying to orient.
Next:
- Trace `TerminalBridge._build_session_bootstrap` and
  `_build_model_policy_summary` selected-model flow.

### ISH-010 - Routing surface inventory invariant is stale

Status: open
Category: tests, provider-routing, orientation
Evidence:
- `pytest -q tests/test_layer_separation.py tests/test_routing_surface_inventory.py tests/test_models.py tests/test_model_manager.py`
  failed in `test_autonomous_agent_exposes_model_router_and_codex_stays_direct`.
- The test expects exactly one
  `await self._model_router.complete_for_task(` call in
  `dharma_swarm/autonomous_agent.py`.
- `git show HEAD:dharma_swarm/autonomous_agent.py | rg -n "complete_for_task"`
  shows two such call sites already existed at HEAD.
Impact:
- A routing inventory test encodes stale topology and can mislead agents into
  treating a pre-existing router shape as a fresh regression.
Next:
- Decide whether the invariant should allow both Anthropic and runtime-open
  routed call sites, or whether one path should be collapsed intentionally.

### ISH-011 - TUI tmux helper scripts hang under Codex wrapper

Status: open
Category: TUI, tooling, verification-harness
Evidence:
- `env SESSION_NAME=codex_terminal_tui_probe ... scripts/start_terminal_tui_tmux.sh`
  hung under the Codex command wrapper and left a stuck
  `/usr/bin/env bash scripts/start_terminal_tui_tmux.sh` process without
  starting tmux.
- `env SESSION_NAME=codex_terminal_tui_probe scripts/send_terminal_tui_keys.sh --literal /help`
  also hung under the Codex command wrapper and did not inject text.
- Direct `tmux new-session`, `tmux capture-pane`, and `tmux send-keys` worked
  for the same TUI session.
Repair:
- `scripts/send_terminal_tui_keys.sh` now has `--literal` / `--text` support
  using `tmux send-keys -l`, which is the required mode for prompt text.
Remaining:
- The helper scripts still hang when invoked through this Codex command
  wrapper, so the literal helper mode is not yet live-verified through the
  helper itself.
Impact:
- The official-looking helper path can make TUI input look broken even when
  direct tmux input works.
Next:
- Trace the scripts with `bash -x` in a real terminal or PTY.
- Add script-level timeouts or replace wrapper use in agent harnesses with
  direct tmux primitives until the hang is understood.

### ISH-012 - TUI codex chat turn stalls after bootstrap

Status: open
Category: TUI, provider-adapter, session-execution
Evidence:
- Compact 80x24 TUI accepted `Reply with exactly OK.` from Control and moved
  the turn to Chat.
- After 25 seconds, Chat still showed `Turn 1 | running` with only
  bootstrap/route-selection trace and no assistant text or session end.
- Status changed to `route confirmed -> codex:gpt-5.4`.
- The live bridge process existed as
  `/Users/dhyana/dharma_swarm/.venv/bin/python -m dharma_swarm.terminal_bridge stdio`.
- `pgrep -P <terminal_bridge_pid>` showed no child provider process under the
  bridge while the turn was running.
- `TerminalBridge._handle_session_start()` is supposed to emit `session.ack`
  before streaming the adapter, so the current stall is after prompt
  visibility and before usable model output.
Impact:
- The TUI can now show that a prompt was accepted, but it still cannot be
  trusted as a working agent seat until provider turns complete or fail
  visibly.
Next:
- Directly exercise `terminal_bridge` with a `session.bootstrap` followed by
  `session.start` and a timeout.
- Inspect `dharma_swarm/tui/engine/adapters/codex.py` process spawn and error
  emission behavior.
- Ensure provider startup failure becomes a visible TUI error instead of an
  indefinite running turn.

## Resolved / Locally Repaired

### ISH-008 - TUI stop path prints KeyboardInterrupt traceback

Status: resolved locally
Category: TUI, CLI-wrapper, input-handling
Evidence:
- Stopping `dgc dashboard` with Ctrl-C previously exited through
  `dharma_swarm/terminal_commands/surfaces.py` and printed a Python
  `KeyboardInterrupt` traceback from `subprocess.run(..., check=True)`.
Repair:
- `cmd_tui()` now catches `KeyboardInterrupt` at the dashboard wrapper
  boundary and returns cleanly.
- Added focused tests for Bun dashboard and legacy TUI interrupt paths.
Verification:
- `pytest -q tests/test_terminal_surfaces.py tests/test_dgc_cli.py tests/test_terminal_bridge.py tests/test_command_contract.py tests/tui/test_system_commands.py tests/tui/test_tui_entrypoint.py`
  passed: 130 tests.
- `python -m py_compile dharma_swarm/terminal_commands/surfaces.py tests/test_terminal_surfaces.py dharma_swarm/terminal_bridge.py`
  passed.
- `cd terminal && bun run typecheck` passed.
- Compact `env COLUMNS=80 LINES=24 python -m dharma_swarm.dgc_cli dashboard`
  reached `DHARMA UP`; interrupt exit printed `DGC dashboard stopped.` with no
  Python traceback.
Remaining:
- In the PTY harness, the first Ctrl-C appeared to be consumed by the Bun TUI
  and restored the cursor; the second Ctrl-C reached the wrapper and exited
  cleanly. Real-terminal stop ergonomics should still be checked with the
  broader TUI interaction pass.

### ISH-009 - Local terminal bridge namespace regression crashed TUI boot

Status: resolved locally
Category: TUI, bridge transport, protocol/event projection
Evidence:
- First `dgc dashboard` run crashed on
  `ModuleNotFoundError: No module named 'dharma_swarm.terminal_engine.events'`.
- Restored `dharma_swarm/terminal_bridge.py` to the tracked HEAD import
  owners: `dharma_swarm.tui.commands.system_commands`,
  `dharma_swarm.tui.engine.adapters`, and `dharma_swarm.tui.engine.events`.
- Added `tests/test_terminal_bridge.py`.
Verification:
- `pytest -q tests/test_terminal_bridge.py tests/test_command_contract.py tests/tui/test_system_commands.py`
  passed, 23 tests.
- `python3 -m py_compile dharma_swarm/terminal_bridge.py tests/test_terminal_bridge.py`
  passed.
- `bun run typecheck` in `terminal/` passed.
- Bridge stdio smoke returned `bridge.ready` and
  `session.bootstrap.result`.
- `dgc dashboard` reached `DHARMA UP`.
