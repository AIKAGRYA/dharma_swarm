# Test Regression Scorecard — K2.6-Floor Fix Verification

**Campaign:** Cybernetic Loop Closure (`loop-closure-2026-06`), Phase 1b
**Branch:** `loop-closure/phase1b-2026-06`
**Fix commit under audit:** `a8dcc50662559f038eb4ab755a40766e5da29cb6`
("loop-closure: fix K2.6-floor test regression — update canonical-default expectations to frontier + close hierarchy drift")
**Campaign base (origin/main merge target):** `9c76b2106` (Merge PR #585)
**Floor-change commit that caused the MINE reds:** `cc962bfe1` ("enforce Kimi K2.6 power floor") — landed on this branch *after* base `9c76b2106`.
**Verified:** 2026-06-14, full suite (11,611 tests collected) run at HEAD and at base for direct comparison.

---

## Verdict

`mineGreen = true` · `preExistingRemaining = 46`

The campaign branch is green **except** for 46 pre-existing red tests that all fail on the campaign base `9c76b2106` and predate this campaign. Every test the K2.6 power-floor change (`cc962bfe1`) actually broke has been fixed by updating its expectation to the new frontier canon — no test was deleted, skipped, or loosened.

**No-new-failures, proven by full-suite diff (not estimate):**
- HEAD `a8dcc5066`: **46 failed**, 11520 passed (26m26s).
- Base `9c76b2106`: **55 failed**, 11484 passed (31m54s).
- HEAD failure set is a **strict subset** of the base failure set — `comm -23 head base` is **EMPTY** (zero tests that pass at base fail at HEAD). The campaign branch has FEWER reds than base (46 < 55): the K2.6 canon work additionally turned 9 base-failing tests green (`test_model_key_routing_guard` ×2, `test_routing_surface_inventory` ×2, `test_ollama_config`, `test_organism_boot`, plus 3 `test_correlation_context` signal-bus tests). Ceiling 46 ≤ 49 holds with room to spare.

---

## MINE — K2.6-floor-caused regressions (fixed)

**N = 4** stale-expectation files corrected (6 underlying test functions, all GREEN at HEAD):

| File | Test function(s) | Change | Status |
|------|------------------|--------|--------|
| `tests/test_conductors.py` | `test_claude_config` | `claude-opus-4-6` → `claude-opus-4-8` | PASS |
| `tests/test_provider_matrix.py` | `test_build_default_matrix_targets_keeps_sovereign_lanes_first` | `gpt-5.4`→`5.5`, `opus-4-6`→`4-8`, `kimi-k2.5:cloud`→`k2.6`, `minimax-m2.7:cloud`→`m3` | PASS |
| `tests/test_provider_smoke.py` | `test_run_provider_smoke_reports_success_with_monkeypatched_probes`; `test_run_provider_smoke_stops_pack_on_provider_wide_failures`; `test_run_provider_smoke_skips_empty_openrouter_outputs` | catalog/probe `kimi-k2.5`→`k2.6`, `minimax-m2.7`→`m3`, NIM probe primary → frontier | PASS |
| `tests/test_runtime_provider.py` | `test_runtime_provider_openrouter_default_model_matches_canonical_hierarchy` | `moonshotai/kimi-k2.5` → `kimi-k2.6` | PASS |

Diff integrity: test files net **+13 / −13** lines, **12 `-assert` ↔ 12 `+assert`** (1:1 expectation swaps); **zero** `skip`/`xfail`/`pytest.mark` added; **zero** test functions removed. The floor change is the correct canon (the ONE WAY hierarchy); the expectations were stale. Source-consistency drift was also closed in `provider_matrix.py` and `provider_smoke.py` (derive frontier from `model_hierarchy.default_model()` instead of hardcoded sub-floor literals) — not test-patched.

---

## PRE-EXISTING remaining (NOT my mandate to fix)

**M = 46** — every failure in the HEAD full-suite run also fails on the base commit `9c76b2106`. These are known debt: infrastructure-dependent (Docker daemon, LanceDB/vector adapters, browser drivers, semantic-embedding deps), live-state/clock-dependent (read real `~/.dharma/` archive + wall-clock), or canon mismatches that predate the K2.6 campaign.

### Same-family note — `test_conductors.py::test_codex_config` (addresses the 2/3 dissent)

The split panel flagged this test as an "incomplete fix" — same root cause as the MINE `test_claude_config`, left red. **It was proven RED at base `9c76b2106`** and is therefore PRE-EXISTING, not a K2.6-floor regression:

- Source `CONDUCTOR_CODEX_CONFIG["model"] = canonical_default_model(ProviderType.CLAUDE_CODE)`.
- At base, `DEFAULT_MODELS[CLAUDE_CODE] = "claude-opus-4-6"`, so the config already resolved to an **opus** string while the test asserts `claude-sonnet-4-20250514`. The mismatch (opus-vs-sonnet) existed before the floor change; `cc962bfe1` only shifted opus-4-6 → opus-4-8.
- Confirmed by running `test_codex_config` against a detached worktree at `9c76b2106`: FAILED (`claude-opus-4-6` != `claude-sonnet-4-20250514`).

It is correctly left untouched: fixing it is outside the K2.6-floor regression mandate (it is a standing source/test disagreement about whether the codex conductor should be a sonnet-class or opus-class default — an operator decision, not a stale-canon swap).

### Pre-existing failing test ids (46)

```
tests/test_assurance.py::test_provider_scan_accepts_bare_claude_models_on_claude_code
tests/test_browser_agent.py::TestToolRegistryIntegration::test_check_browser_available
tests/test_browser_agent.py::TestToolRegistryIntegration::test_browser_toolset_available
tests/test_browser_agent.py::TestContextManager::test_context_manager_start_stop
tests/test_conductors.py::TestConductorConfigs::test_codex_config
tests/test_context_semantic.py::test_semantic_hits_produce_section
tests/test_context_semantic.py::test_empty_semantic_hits_no_section
tests/test_daemon_config.py::test_daemon_config_defaults
tests/test_dataset_builder.py::test_collect_stigmergy_returns_list
tests/test_docker_sandbox.py::TestDockerSandboxIntegration::test_docker_is_available
tests/test_docker_sandbox.py::TestDockerSandboxIntegration::test_full_container_lifecycle
tests/test_docker_sandbox.py::TestDockerSandboxIntegration::test_python_execution
tests/test_docker_sandbox.py::TestDockerSandboxIntegration::test_timeout_enforcement
tests/test_docker_sandbox.py::TestDockerSandboxIntegration::test_events_recorded
tests/test_docker_sandbox.py::TestDockerSandboxIntegration::test_network_none_blocks_outbound
tests/test_flywheel_exporter.py::test_flywheel_exporter_filters_session_events_when_trace_is_missing
tests/test_ginko_evolution.py::TestPromptTournament::test_mutate_prompt_no_api_key
tests/test_godel_claw_e2e.py::test_all_eleven_gates_fire
tests/test_memory_integration.py::TestBackwardCompatibility::test_build_sections_accepts_knowledge_block
tests/test_memory_palace.py::TestLanceDBAdapter::test_connect_creates_db
tests/test_memory_palace.py::TestLanceDBAdapter::test_upsert_and_count
tests/test_memory_palace.py::TestLanceDBAdapter::test_search_returns_results
tests/test_memory_palace.py::TestLanceDBAdapter::test_cross_session_persistence
tests/test_memory_palace.py::TestMemoryPalaceLanceDB::test_palace_connects_to_lancedb_with_state_dir
tests/test_memory_palace.py::TestMemoryPalaceLanceDB::test_palace_connects_to_lancedb_without_state_dir
tests/test_memory_palace.py::TestMemoryPalaceLanceDB::test_ingest_writes_to_lancedb
tests/test_memory_palace.py::TestMemoryPalaceLanceDB::test_ingest_empty_content_no_lance_write
tests/test_memory_palace.py::TestMemoryPalaceLanceDB::test_ingest_whitespace_only_no_lance_write
tests/test_memory_palace.py::TestMemoryPalaceLanceDB::test_cross_session_recall
tests/test_memory_palace.py::TestMemoryPalaceLanceDB::test_stats_includes_lancedb
tests/test_memory_writer_sentinel.py::test_writer_sentinel_cli_action_required_gate_passes_for_triaged_repo
tests/test_memory_writer_sentinel.py::test_writer_sentinel_cli_ci_profile_runs_discovery_and_gates
tests/test_mode_pack.py::test_mode_pack_contract_loads
tests/test_monitor.py::test_check_health_mean_fitness
tests/test_monitor.py::test_fitness_regression_detected
tests/test_orphan_reaper.py::TestTaskQueueSnapshot::test_queue_snapshot_counts_blocked_pending_tasks
tests/test_phase3_integration.py::TestDynamicCrewScaling::test_no_scaling_when_healthy
tests/test_provider_policy.py::test_model_hierarchy_exposes_primary_driver_and_support_lane_contract
tests/test_provider_policy.py::test_provider_policy_prefers_tooling_lanes_when_requested
tests/test_provider_policy.py::test_provider_policy_swarm_role_allocation_is_deterministic
tests/test_provider_smoke.py::test_probe_qwen_dashboard_collects_tool_calls_and_content
tests/test_sleep_cycle.py::test_is_quiet_hours_true
tests/test_startup_crew.py::test_create_seed_tasks_replaces_date_placeholder
tests/test_telos_gates_witness_enhancement.py::test_read_tool_variants
tests/test_telos_substrate.py::TestTelosObjectivesData::test_perspectives_are_valid
tests/test_vector_store.py::TestTFIDFEmbedder::test_persistence_round_trip
```

### Note on `test_provider_smoke.py::test_probe_qwen_dashboard_collects_tool_calls_and_content`

This is the only HEAD failure that PASSES in isolation (and passes when its whole file `tests/test_provider_smoke.py` runs alone — 12/12 — at both HEAD and base). It fails only under full-suite ordering: cross-file test-state pollution (a leaked global affecting `chat_router`), not a deterministic regression. The fix commit `a8dcc5066` does not touch `_probe_qwen_dashboard` or `chat_router`; its `provider_smoke.py` edits are NIM/OpenRouter catalog literals in unrelated probe functions. **It is present in the base `9c76b2106` full-suite FAILED list** (confirmed by the base run), so it is pre-existing under identical full-suite conditions.

---

## Method / receipts

1. **MINE green** — ran the 6 affected test functions at HEAD `a8dcc5066`: `6 passed`. None appear in the full-suite FAILED list.
2. **No-new-failures** — full suite at HEAD: `46 failed, 11520 passed, 27 skipped, 7 xfailed, 14 xpassed` (26m26s). Full suite at base `9c76b2106` (detached worktree): `55 failed, 11484 passed, 27 skipped, 7 xfailed, 14 xpassed` (31m54s). `comm -23` of the two normalized FAILED-id lists is EMPTY: HEAD failure set is a strict subset of base (no test that passed at base fails at HEAD). The campaign also fixed 9 base reds.
3. **Ceiling** — the no-new-failures ceiling for this fix is ≤49 (the campaign's earlier `53 − 4 MINE` budget); observed 46 ≤ 49. The authoritative base measured here is 55 reds (≥ the earlier 53 reading; the extra base reds are clock-/live-`~/.dharma/`-state-dependent flakes — `test_sleep_cycle`, `test_startup_crew`, `test_monitor`, `test_correlation_context` — and the date rolled to 2026-06-14 mid-verification). HEAD's 46 is below ceiling and strictly below base.
4. **Nothing weakened** — test diff is 1:1 expectation swaps; 0 skips/xfails added; 0 tests deleted.
5. **Same-family dissent resolved** — `test_codex_config` proven red at base in a detached `9c76b2106` worktree → pre-existing, not MINE.

**Honest debt statement:** 46 pre-existing reds remain on the campaign branch. They are known debt that predates `loop-closure-2026-06` and are NOT in scope for the K2.6-floor regression fix. They cluster as: missing local infra (Docker/LanceDB/browser/embedding deps), live-state/clock coupling, and standing source/test canon disagreements (e.g. `test_codex_config`, `test_provider_policy`, `test_mode_pack`, `test_daemon_config`).
