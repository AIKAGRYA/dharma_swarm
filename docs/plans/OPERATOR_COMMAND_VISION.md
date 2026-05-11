# Operator Command Vision — Unified Intent-to-Value Pipeline

> **Status:** Vision / North Star  
> **Date:** 2026-05-04  
> **Relates to:** `NEXT_10_SUBSTRATE_TODO.md`, `ONTOLOGY_NATIVE_OPERATOR_BRIEF_MASTER_SPEC.md`

## 1. The Problem

Dharma Swarm has **five command surfaces** that each reimplement the same
operations independently:

| Surface | File | Commands | Stack |
|---------|------|----------|-------|
| CLI | `dgc_cli.py` (7,078 lines) | 185 subcommands | argparse |
| TUI slash commands | `tui/commands/system_commands.py` | 43 slash commands | Textual |
| Terminal bridge | `terminal_bridge.py` | ~20 request types | JSON stdio |
| API routes | `api/routers/commands.py` | small subset | FastAPI |
| Dashboard client | `dashboard/src/lib/api.ts` | REST calls | Next.js |

These surfaces share no command contract. Adding a command to one surface
does not add it to others. Behavior diverges silently. There is no parity
test. This is **surface entropy**.

## 2. The Grand Vision

One protocol. Every surface.

```
User (any surface)
    │
    ▼
┌─────────────────────────────────────────┐
│         INTENT RESOLUTION               │
│  Natural language → structured command  │
│  (IntentRouter + knowledge_units +      │
│   _resolve_prompt_intent)               │
└───────────────┬─────────────────────────┘
                │
                ▼
┌─────────────────────────────────────────┐
│         COMMAND ENGINE                  │
│  Shared typed commands               │
│  dharma_swarm/terminal_commands/*.py    │
│  register() + dispatch() protocol       │
│  One implementation, every surface      │
└───────────────┬─────────────────────────┘
                │
                ▼
┌─────────────────────────────────────────┐
│         DHARMIC GOVERNANCE              │
│  Telos gates, DharmaKernel, Gnani      │
│  (gated execution, alignment check)     │
└───────────────┬─────────────────────────┘
                │
                ▼
┌─────────────────────────────────────────┐
│         VALUE MEASUREMENT               │
│  operator_brief → ValueEvent            │
│  Prescription return-score updates      │
│  (reinforcement loop on skill quality)  │
└─────────────────────────────────────────┘
```

### Surfaces become thin clients:

- **CLI** (today: argparse; future: Rust/clap) → calls Command Engine
- **TUI** (today: Textual; future: Ratatui) → calls Command Engine
- **Terminal bridge** → transport/dispatch glue over Command Engine
- **Desktop app** (Tauri + Next.js dashboard) → calls Command Engine
- **API** (FastAPI) → calls Command Engine
- **Mobile** (future: Tauri Mobile or React Native) → calls Command Engine

### Existing pieces that wire into this:

| Piece | File | Role in pipeline |
|-------|------|-----------------|
| IntentRouter | `intent_router.py` | NL → task decomposition, skill matching, complexity estimation |
| Prompt intent resolver | `terminal_bridge.py:_resolve_prompt_intent()` | NL → intent kind (command, chat, agent, evolution) |
| Knowledge prescriptions | `knowledge_units.py:get_prescriptions_for_intent()` | Intent → learned skills with return-score reinforcement |
| Mission state machine | `mission_contract.py:MissionState` | Task → mission tracking with thesis, blockers, delegation |
| Dharma attractor | `dharma_attractor.py` | Ambient alignment field biasing agents toward true dharma |
| Operator brief | `operator_brief/insight_brief.py` | Gated artifact production with witness/gate/value chain |
| Value events | `operator_brief/value_events.py` | Value measurement per agent per time period |
| Command payloads | `operator_core/command_payloads.py` | Shell-neutral payload builders (early embryo) |

## 3. Phased Path

### Phase 1 — Command Extraction (THIS PR)

Extract `dgc_cli.py` into `dharma_swarm/terminal_commands/` with ~10
domain modules. Each module has:
- `cmd_*()` functions (the implementations)
- `register(sub)` (adds argparse entries)
- `dispatch(command, args)` (routes to cmd_ functions)

Add `test_command_contract.py` parity gate cross-referencing CLI commands
against TUI slash commands and terminal bridge request types.

`dgc_cli.py` becomes ~200-line thin dispatcher.

**This creates the importable shared command layer that every future
surface calls into.**

### Phase 2 — Protocol Formalization

- Define JSON-RPC or typed message protocol over the command modules
- `terminal_bridge.py` delegates to `terminal_commands/` for command
  execution (bridge reduction per `terminal-bridge-reduction-map.md`)
- TUI slash commands import from `terminal_commands/` instead of
  reimplementing
- API routes delegate to `terminal_commands/`
- Command telemetry: every invocation produces an ontology event

### Phase 3 — Rust Acceleration

- Rust CLI launcher (clap) → calls Python command engine via JSON-RPC
  or subprocess. Startup time <10ms.
- Ratatui TUI → GPU-accelerated terminal rendering, calls same protocol
- The Python modules remain the "brain"; Rust is the fast shell

### Phase 4 — Unified App

- Tauri desktop app wrapping Next.js dashboard with Rust command backend
- Same command protocol, native app (~5MB)
- Mobile surface via Tauri Mobile or React Native
- Every surface: one protocol, one command engine, one value pipeline

## 4. The Intent-to-Value Loop (The Dharmic Differentiator)

What makes this architecture unique is not the CLI decomposition —
every large project does that. What is unique is the **intent-to-value
pipeline** that the command engine enables:

1. User expresses fuzzy intent ("help me ship this feature")
2. IntentRouter decomposes into sub-tasks with complexity + skill matching
3. Knowledge prescriptions match learned skills with return-score weighting
4. MissionState tracks the mission end-to-end (thesis, tasks, blockers)
5. DharmaAttractor aligns execution to user's true dharma (not just task)
6. Telos gates verify each action (AHIMSA, SATYA, consent, steelman, drift)
7. Operator brief produces KnowledgeArtifact with full witness chain
8. ValueEvent measures what was actually delivered
9. Prescription return-scores update (skills that produce value get boosted)
10. User evolves — the system learns what "true dharma" means for THIS user

This is the "AI does everything end-to-end while helping the user evolve
and make a living with his true dharma" vision. The command extraction
(Phase 1) creates the shared layer that makes steps 1-10 composable
across every surface.

## 5. Design Principles

- **Protocol over surface**: Define commands once, render everywhere
- **Typed contracts**: Every command has typed request/response; enables
  Rust codegen, TypeScript codegen, JSON schema validation
- **Lazy loading**: Only load the module for the invoked command
- **Ontology-native telemetry**: Command invocations are ontology events
- **Intent-first**: Surfaces resolve intent THEN dispatch to commands
- **Value-measured**: Every command execution feeds the value loop
- **Dharma-aligned**: Governance gates are part of the pipeline, not bolted on

## 6. What This Replaces

After Phase 4, the following are retired:

- `dgc_cli.py` monolith → thin dispatcher + `terminal_commands/`
- `tui_legacy.py` → retired (Ratatui or current Textual)
- Duplicated slash-command implementations → import from `terminal_commands/`
- Surface-specific command reimplementations → one shared layer
- Undiscoverable commands → semantic intent resolution routes to them
