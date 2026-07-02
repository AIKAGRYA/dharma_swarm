# Persistent Agent Hierarchy Receipt - 2026-06-30

## Summary

The prior flat census was incomplete for ownership decisions. The real hierarchy is not just repo-local `.dharma/agents` records. The higher-level persistent-agent home is:

`/Users/dhyana/.dharma/agents`

That directory currently has 62 immediate entries: 59 agent directories and 3 markdown marker files. It contains sovereign holon identities, living-agent manifests, Codex workcell/passport agents, signal-test agents, and live service state.

## Operator-Facing Hierarchy

### L0 - Standing Conductors

Defined in `dharma_swarm/conductors.py`.

| Agent | Role | Wake Interval | Explicit Priority |
| --- | --- | ---: | --- |
| `conductor_claude` | phenomenological oversight / senior conductor | 3600s | R_V paper progress, stigmergy, conductor findings, low-validated claims, coordination |
| `conductor_codex` | infrastructure and code health conductor | 1800s | daemon health, imports, launchd/cron, hot paths, failing tests |

These are code-configured `PersistentAgent` loops. `conductor_claude` is the explicit strategic owner for R_V / mech-interp progress; `conductor_codex` is the infrastructure-owner counterpart.

### L1 - Registered Sovereign Holons

Authoritative CLI source: `dgc agent list` via `dharma_swarm.terminal_commands.agents._cmd_agent_list()`.

| Holon | Model | Compass Signals | Current Health |
| --- | --- | ---: | --- |
| `codex_composer` | `gpt-5.5` | 401 | registered, service heartbeat fresh |
| `codex_worker_spine` | unset | 0 | registered, no service heartbeat |
| `devin-roaming-2987d222` | unset | 0 | registered, no service heartbeat |
| `fable_composer` | `claude-fable-5` | 0 | registered, no service heartbeat |
| `opus_composer` | `claude-opus-4-8` | 399 | registered, no service heartbeat |
| `sarathi` | `@frontier` | 0 | registered, no service heartbeat |

These are the agents intended for `dgc agent talk/run/status/kill`.

### L2 - Sovereign Holon Filesystem Identities

Filesystem classification of `/Users/dhyana/.dharma/agents` found four high-signal holon directories:

| Agent | Role / Status | Durable Signals |
| --- | --- | --- |
| `codex_composer` | `code_writing_and_verification`, active | `identity.json`, `living_agent.json`, `HOLON_CONTEXT.md`, `runtime_fields.json`, `last_receipt.json`, `supervisor/`, `compass_signals.jsonl` |
| `opus_composer` | `lead_orchestrator`, candidate | `identity.json`, `living_agent.json`, `passport.json`, `identity_invariant.json`, `state.md`, `role.md`, `runtime_fields.json`, `last_receipt.json`, `OPERATING_MANUAL.md`, `SOUL.md`, `context/`, `work/`, `handoff/` |
| `fable_composer` | `master_composer`, standing loop pending | `identity.json`, `OPERATING_MANUAL.md`, `SOUL.md` |
| `sarathi` | `apex_holon`, genesis authored not yet breathing | `identity.json`, `OPERATING_MANUAL.md`, `SOUL.md` |

Two additional registered identities exist:

| Agent | Durable Signals |
| --- | --- |
| `codex_worker_spine` | `identity.json` |
| `devin-roaming-2987d222` | `identity.json`, `living_agent.json` |

### L3 - Live Runtime Evidence

Runtime checks found:

| Surface | Evidence |
| --- | --- |
| `dharma_holon_l4_codex_composer` | tmux session running `scripts/holon_l4_service.py codex_composer`; process is live |
| `codex-composer-wake` | tmux wake loop session exists |
| `dharma_a2a_inbox_bridge_fable_composer` | A2A bridge loop running |
| `dharma_a2a_inbox_bridge_hermes_m5` | A2A bridge loop running for `hermes-m5` |
| `dharma_a2a_inbox_bridge_opus_composer` | A2A bridge loop running |
| `dharma_local_nats` | local NATS bus running |
| `warp_oz_monitor` | external agent inbox monitor running |
| `merge-master-mike` | daemon session exists |

Important distinction: A2A bridge liveness is not the same as sovereign holon service liveness. In `holon_health_rows()`, only `codex_composer` currently has a fresh sovereign service heartbeat.

### L4 - Living Agents

These have `living_agent.json` plus receipt/state evidence:

`artha_cream`, `claude_code_cli_20260521t064502z`, `codex_5_5_cli`, `codex_forgewright`, `codex_gpt5_api`, `codex_telos`, `cursor_remote_agent`, `cybernetics_codex`, `fable_5_cursor`, `forge_measurement_guardian`, `hermes_m5`, `hermes_m5_bootstrap`, `kimi-2-6-claw`, `livelihood_loom_ceo`, `magpie`, `merge_master_mike`, `opus_forge_architect`, `palantir_pilot`, `perplexity-computer`, `qwen_code`, `strategy_librarian`, `warp_oz`.

Specialist assignment added 2026-06-30: `qwen_code` is the house `machine_learning_specialist` and steward for the installed `NVIDIA/skills` stack. See `docs/agents/qwen_code/ML_SPECIALIST_CHARTER.md` and `reports/agentops/NVIDIA_SKILL_STEWARD_ASSIGNMENT_20260630.md`.

### L5 - Codex Workcell / Passport Agents

These have `passport.json`, `state.md`, `role.md`, context manifests, work directories, or handoff directories:

`ci_measurement_guardian`, `codex`, `codex-agni`, `codex-capital-lab-execution-90`, `codex-capital-lab-goal`, `codex-cashclaw`, `codex-dharma-capital-lab`, `codex-goal-a-alpha-evidence`, `codex-living-agent-kernel`, `codex_cashclaw_live_intake`, `codex_command_plane_dogfood`, `codex_goodworks_dgm`, `codex_integrator`, `codex_loop2_repair`, `codex_loop_auditor`, `codex_pge_goal`, `codex_planner`, `context_librarian`, `frontend_allnight_builder`, `loop_repair_codex`, `operator_os_research_sentinel`, `repo_cartographer`.

### L6 - Preset Wake Agents

CLI-facing preset agents from `PRESET_AGENTS`:

| Agent | Role | CWD |
| --- | --- | --- |
| `researcher` | researcher | `/Users/dhyana/mech-interp-latent-lab-phase1` |
| `coder` | coder | `/Users/dhyana/dharma_swarm` |
| `scout` | scout | `/Users/dhyana/jagat_kalyan` |
| `reviewer` | reviewer | `/Users/dhyana` |
| `witness` | witness | `/Users/dhyana` |

These are wakeable identities, not necessarily standing sovereign holons.

### L7 - Repo-Local Agent Pools

The previous flat census still matters as a lower-tier pool:

| Registry | Count |
| --- | ---: |
| repo `.dharma/agents` file-backed agents | 29 |
| repo `.dharma/ginko/agents` agents | 51 |
| repo runtime DB `agent_identity` rows | 28 |

These are agent pool / experiment / local runtime records, not the top-level sovereign hierarchy.

## Ownership Implication

For the Gemma / recursive-prompt / SAE strange-loop line:

1. Strategic owner: `conductor_claude`, because its first explicit priority is R_V paper progress and mechanistic/phenomenological oversight.
2. Operational owner: `codex_composer`, because it is the only registered sovereign holon with fresh service heartbeat and has the L4 live service.
3. Execution support: `researcher` for the mech-interp repo, `coder` for scripts and Make targets, `witness` for receipts, and `forge_measurement_guardian` or `ci_measurement_guardian` for non-circular verification.

If a single accountable owner is required, assign `codex_composer`, with `conductor_claude` as supervising conductor.

## Verification Commands

Commands run:

- Classified `/Users/dhyana/.dharma/agents` immediate entries by durable signal files.
- Ran `holon_health_rows()` from the repo venv.
- Ran `_cmd_agent_list()` from the repo venv.
- Checked tmux panes with `tmux list-panes -a`.
- Checked live process evidence with `pgrep -fl dharma`, `pgrep -fl holon`, and `pgrep -fl conductor`.

No secrets or private key material were read.
