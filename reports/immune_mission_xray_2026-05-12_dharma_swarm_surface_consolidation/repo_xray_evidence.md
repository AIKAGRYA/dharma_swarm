# Repo X-Ray: dharma_swarm
*Generated 2026-05-12T15:03:06 UTC*

## Overview
- **Path**: `/Users/dhyana/dharma_swarm`
- **Files analyzed**: 807
- **Total lines**: 235,015 (198,154 non-blank)
- **Languages**: docs: 792 files (0 lines) | python: 633 files (170,265 lines) | config: 401 files (0 lines) | typescript: 168 files (64,009 lines) | javascript: 6 files (741 lines)

## Architecture
### Top Modules
- **tests**: 571 files, 154,383 lines, 1675 classes, 11110 functions — Contains 3 classes, 28 functions
- **terminal**: 44 files, 33,772 lines, 0 classes, 0 functions
- **dashboard**: 125 files, 30,272 lines, 0 classes, 0 functions
- **tools**: 24 files, 7,704 lines, 30 classes, 256 functions — Contains 2 classes, 14 functions
- **experiments**: 16 files, 3,154 lines, 23 classes, 111 functions — Contains 2 classes, 8 functions
- **results**: 8 files, 3,074 lines, 4 classes, 107 functions — Contains 1 classes, 26 functions
- **(root)**: 5 files, 1,291 lines, 0 classes, 19 functions — Contains 0 classes, 1 functions
- **.claude**: 5 files, 706 lines, 0 classes, 0 functions
- **analysis**: 1 files, 442 lines, 0 classes, 9 functions — Contains 0 classes, 9 functions
- **.semgrep**: 6 files, 141 lines, 0 classes, 25 functions
- **codex_skills**: 2 files, 76 lines, 0 classes, 4 functions

### Module Connections
- `(root)` → `dharma_swarm`
- `tools` → `dharma_swarm`
- `codex_skills` → `dharma_swarm`
- `analysis` → `dharma_swarm`
- `tests` → `dharma_swarm`
- `tests` → `tools`
- `tests` → `api`
- `tests` → `scripts`
- `.semgrep` → `dharma_swarm`

## Code Quality Signals
**Overall Grade: B** (score: 0.64)

- **Test ratio**: 288% (599 test files)
- **Docstring coverage**: 21%
- **Naming conventions**: 100%
- **Type annotation rate**: 86%
- **Avg complexity per file**: 44.3

## Complexity Hotspots
Functions with the highest cyclomatic complexity:

- `test_model_router_total_failure_writes_failed_completion_telemetry` in `tests/test_model_router_telemetry.py:223` — complexity=44, 108 lines
- `test_chat_status_reports_runtime_settings` in `tests/test_dashboard_chat_router.py:18` — complexity=40, 54 lines
- `summarize` in `results/experiment_gemma_scope_m5_20260507/run_gemma_scope_identity.py:166` — complexity=37, 122 lines
- `test_model_router_success_writes_telemetry_records` in `tests/test_model_router_telemetry.py:54` — complexity=35, 88 lines
- `run_experiment` in `experiments/live_pulse_v4.py:246` — complexity=34, 262 lines
- `test_codex_stream_surfaces_progress_and_command_execution` in `tests/tui/test_codex_adapter.py:227` — complexity=32, 102 lines
- `_witness_mandala_checks` in `tools/build_protocol/proof_artifact_to_spec.py:381` — complexity=30, 104 lines
- `test_curriculum_engine_derives_campaign_chain_from_opportunity_board` in `tests/test_curriculum_engine.py:108` — complexity=30, 74 lines
- `test_memory_kernel_iterates_normalized_atoms_with_authority_labels` in `tests/test_memory_kernel_adapters.py:101` — complexity=30, 29 lines
- `test_model_router_fallback_success_marks_fallback_in_telemetry` in `tests/test_model_router_telemetry.py:145` — complexity=29, 75 lines

## Largest Files
- `terminal/src/protocol.ts` — 3,886 lines (complexity=0)
- `terminal/tests/sidebar.test.ts` — 3,069 lines (complexity=0)
- `terminal/tests/protocol.test.ts` — 2,993 lines (complexity=0)
- `terminal/src/app.tsx` — 2,973 lines (complexity=0)
- `terminal/src/components/Sidebar.tsx` — 2,439 lines (complexity=0)
- `terminal/tests/repoPane.test.ts` — 2,353 lines (complexity=0)
- `dashboard/src/app/dashboard/qwen35/page.tsx` — 2,209 lines (complexity=0)

## External Dependencies
194 external packages: `../freshness, ../layout, ../repoControlPreview, ../routePolicy, ../src/components/OperatorSummaryBand, ../src/components/RepoPane, ../src/components/Sidebar, ../src/protocol, ../src/state, ../src/transcriptFormatting, ../src/types, ../theme, ../transcriptFormatting, ../types, ../verification, ./ChatInterface, ./ChatOverlay, ./HealthBadge, ./RepoPane, ./api`
*...and 174 more*

## Internal Coupling
Files with the most internal imports:

- `tests/test_godel_claw_e2e.py` imports 14 internal modules
- `tests/test_strange_loop_integration.py` imports 13 internal modules
- `tests/test_integration.py` imports 13 internal modules
- `tests/test_operator_core_adapters.py` imports 11 internal modules
- `tests/test_command_center.py` imports 11 internal modules
- `tests/test_strange_loop.py` imports 11 internal modules
- `tests/test_bootstrap_loops.py` imports 10 internal modules

## Risk Flags
- 🟡 **size**: Large file (647 lines). Consider splitting. (`tools/build_protocol/immune_xray.py`)
- 🟡 **size**: Large file (802 lines). Consider splitting. (`tools/build_protocol/proof_artifact_to_spec.py`)
- 🟡 **size**: Large file (539 lines). Consider splitting. (`tests/test_provider_matrix.py`)
- 🟡 **size**: Large file (596 lines). Consider splitting. (`tests/test_monitor.py`)
- 🟡 **size**: Large file (575 lines). Consider splitting. (`tests/test_vault_bridge.py`)
- 🟡 **size**: Large file (606 lines). Consider splitting. (`tests/test_neural_consolidator.py`)
- 🟡 **size**: Large file (528 lines). Consider splitting. (`tests/test_quality_gates.py`)
- 🟡 **size**: Large file (605 lines). Consider splitting. (`tests/test_providers_quality_track.py`)
- 🟡 **size**: Large file (509 lines). Consider splitting. (`tests/test_ontology_registry.py`)
- 🟡 **size**: Large file (523 lines). Consider splitting. (`tests/test_semantic_evolution.py`)
- 🟡 **size**: Large file (580 lines). Consider splitting. (`tests/test_bootstrap_loops.py`)
- 🟡 **size**: Large file (1161 lines). Consider splitting. (`tests/test_thinkodynamic_director.py`)
- 🟡 **size**: Large file (550 lines). Consider splitting. (`tests/test_autonomous_agent.py`)
- 🟡 **size**: Large file (530 lines). Consider splitting. (`tests/test_logic_layer.py`)
- 🟡 **size**: Large file (675 lines). Consider splitting. (`tests/test_a2a.py`)

## Recommended Next Steps
1. Improve documentation. Add docstrings to public functions and classes.
2. Refactor `test_model_router_total_failure_writes_failed_completion_telemetry` in `tests/test_model_router_telemetry.py` (complexity=44). Extract helper functions.
3. Split large files: tools/build_protocol/immune_xray.py, tools/build_protocol/proof_artifact_to_spec.py, tests/test_provider_matrix.py (647+ lines each).
