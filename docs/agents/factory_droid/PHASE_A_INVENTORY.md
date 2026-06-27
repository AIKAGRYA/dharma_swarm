# Phase A Inventory — Factory Droid Reorganization

**Document role:** `working_plan` / inventory-only manifest.  
**Status:** `seed`.  
**Owner:** `docs/agents/factory_droid/FACTORY_DROID_CONTRACT.md`.  
**Generated:** 2026-06-20.  
**Methodology:** `make onboard`, `make orient`, `make bug-corral-scan`, `pytest tests/test_agent_admission.py tests/test_semantic_commons.py`, cross-check against `docs/governance/ACTIVE_TRACK.yaml`.

---

## 1. Current State

- **Repo:** `/Users/dhyana/dharma_swarm`
- **Branch:** `telos-ai-seed-v0-from-sandbox` (HEAD `cd610be3cc`, ahead 9, behind 83)
- **Dirty files:** 304
- **Active tracks:** 11
- **Measured size:** 763 Python modules, 736 tests, 612 docs under `docs/`, 1975 markdown files total
- **Phase 0 checks:**
  - `make onboard`: passed
  - `make orient`: passed, 11 active tracks confirmed
  - `make bug-corral-scan`: passed, no new errors/warnings for Factory Droid references
  - `pytest tests/test_agent_admission.py tests/test_semantic_commons.py`: 17 passed
  - `agent_admission.py --agent-uid factory_droid --canonical-id semobj.factory_droid`: failed as expected because Semantic Commons registration is pending active-track owner approval.

---

## 2. Untracked Generated Artifacts — Cleanup Candidates

These are safe to remove or add to `.gitignore` without review. They are not owned by active tracks.

| Path | Category | Proposed Action |
|---|---|---|
| `com.dharma.swarm.plist.bak.20260618-225622` | backup | delete; `.gitignore` already covers `*.bak` |
| `runtime.db` | runtime SQLite | delete / add to `.gitignore`; move runtime state to `~/.dharma/` |
| `stigmergy.db` | runtime SQLite | delete / add to `.gitignore`; move runtime state to `~/.dharma/` |
| `synthesizer_memory.json` | generated runtime state | delete / add to `.gitignore`; move to `~/.dharma/` |
| `droid-wiki/` | generated wiki output | add to `.gitignore`; regenerate on demand |
| `eval_probe_result.md` | generated eval artifact | delete / move to `reports/` as a single dated witness |
| `reports/sovereign_holons/verify_holon_harness_prod_20260618T*.json` (20 files) | timestamped verifier receipts | delete; keep only the latest if a witness is needed, and move that to `~/.dharma/witness/` |
| `reports/sovereign_holons/verify_holon_harness_prod_20260618T*.md` (20 files) | timestamped verifier reports | delete as above |
| `reports/a2a/NATS_CONTACT_FIRST_RECEIPT_20260617.md` | one-time receipt | delete; single-use scratch |
| `reports/a2a/NATS_CONNECT_SCRATCHPAD_20260617.md` | scratch | delete |
| `reports/a2a/CODEX_HOLON_SEMANTIC_REPLY_P0_20260618.md` | scratch | delete |
| `reports/a2a/NATS_CONNECT_EMAIL_CLOSEOUT_20260617.md` | closeout scratch | delete after track owner confirms |
| `reports/a2a/NATS_ROLLCALL_TRIPLE_CONFIRMATION_20260617.md` | rollcall scratch | delete after track owner confirms |
| `reports/a2a/archive_20260617_canonicalized/` | archive mirror | review with a2a-cloud-agent-bridge owner; if truly archive, move to `docs/_archive/2026-06/` |
| `reports/a2a/nats_connect_signoffs/` | signoff receipts | keep only latest, delete rest, move to `~/.dharma/witness/` |
| `reports/governance/greptile_review_intake_2026-06-18.json` | external review intake | move to `~/.dharma/` or `reports/` as dated artifact |
| `reports/governance/name_drift_preflight_codex_telos.json` | name-drift receipt | move to `~/.dharma/witness/` |
| `reports/research/` | generated research reports | inspect contents; likely add to `.gitignore` or move to `~/.dharma/` |
| `reports/runtime_truth/` | generated runtime truth artifacts | add to `.gitignore`; keep only latest stable witness |
| `shared/` | runtime/shared state | move to `~/.dharma/shared/` or add to `.gitignore` |

---

## 3. Root Markdown — Move Candidates

Move these to `docs/`, `reports/`, or `docs/_archive/`. Keep only canonical root Markdown allowed by anti-slop Rule 8.

| File | Status | Proposed Target | Active Track? |
|---|---|---|---|
| `ACTIVE_SURFACE_MANIFEST.yaml` | tracked clean | keep root | canonical surface manifest |
| `AGENTS.md` | tracked clean | `docs/AGENTS.md` (merge with existing) | no |
| `AGENT_IDENTITY_UNIFICATION.md` | tracked clean | `docs/_archive/2026-04/` | no; newer version already archived |
| `ANTHROPIC_GRANT_DRAFT.md` | tracked clean | `docs/research/` or `reports/` | no |
| `AUDIT_2026-05-07.md` | tracked clean | `reports/audit/` | no |
| `CLAUDE_CODE_LIVE_FIRE_PROMPT.md` | tracked clean | `docs/prompts/` or `docs/archive/prompts/` | no |
| `CYBERNETIC_LOOP_MAP.md` | tracked clean | **keep root** | yes, `loop-closure-2026-06` |
| `DEVIN.md` | tracked clean | `docs/ops/` | no |
| `FOUNDATIONS_TO_CODE_MAP.md` | tracked clean | `docs/architecture/` | no |
| `GNANI_LODESTONE.md` | tracked clean | `docs/foundations/` or `lodestones/` | no |
| `GUARDIAN_REPORT.md` | tracked clean | `reports/` | no |
| `HOLON_CODICES_SYNTHESIS.md` | untracked | `reports/sovereign_holons/` | yes, `composer-holon-spine-longrun-2026-06` — **blocked** |
| `HOLON_SUBSTRATE_PROOF.md` | untracked | `reports/sovereign_holons/` | yes, holon track — **blocked** |
| `HOLON_SUBSTRATE_SYNTHESIS.md` | untracked | `reports/sovereign_holons/` | yes, holon track — **blocked** |
| `INTERFACE_MISMATCH_MAP.md` | tracked clean | **keep root** | no; allowed by Rule 8 |
| `LIVING_LAYERS.md` | tracked clean | `docs/architecture/` | no |
| `MASTER_BUILD_SPEC.md` | tracked clean | `docs/plans/` or `docs/archive/` | no |
| `MODEL_ROUTING_MAP.md` | tracked clean | `docs/_archive/2026-04/` | no; stale per CLAUDE.md |
| `NEXT_SPRINT_PROMPT.md` | tracked clean | `docs/plans/` | no |
| `PHASE4_REPORT.md` | tracked clean | `reports/historical/` | no |
| `PRODUCT_SURFACE.md` | tracked modified | **keep root** | yes, `telos-ai-morning-refinery-2026-06` |
| `QWEN.md` | tracked clean | `docs/ops/` | no |
| `README.md` | tracked clean | **keep root** | canonical entrypoint |
| `S3_S4_GATE_BLOCK_ANALYSIS.md` | untracked | `reports/` | no; possibly active track adjacent — verify |
| `WHAT_IT_WANTS_TO_BECOME.md` | tracked clean | `docs/foundations/` | no |
| `WORLD_MODEL.md` | tracked clean | `docs/foundations/` | no |
| `agent_runner_audit.md` | tracked clean | `reports/` | no |
| `gaia_ui.md` | tracked clean | `docs/dse/` or `docs/plans/` | no |
| `holon_l4_substrate_proof.md` | untracked | `reports/sovereign_holons/` | yes, holon track — **blocked** |
| `orchestrator_audit.md` | tracked clean | `reports/` | no |
| `phase2_darwin_diff_report.md` | tracked clean | `reports/` | no |
| `program.md` | tracked clean | `docs/plans/` | no |
| `program_ecosystem.md` | tracked clean | `docs/plans/` | no |
| `xray_report.md` | tracked clean | `reports/` | no |
| `xray_report.json` | tracked clean | `reports/` | no |

---

## 4. Root Scripts / Config — Move Candidates

| File | Status | Proposed Target | Notes |
|---|---|---|---|
| `agent_loop.sh` | tracked clean | `scripts/` | not a canonical entrypoint |
| `agni_trading_zoom_audit_2026_05_04.sh` | tracked clean | `scripts/` or `reports/` | audit script |
| `com.dharma.swarm.plist` | tracked modified | `scripts/` or `.github/launchd/` | not canonical entrypoint |
| `cron_jobs.json` | tracked clean | `scripts/` or `docs/ops/` | runtime config; may conflict with `~/.dharma/cron/jobs.json` (BR-004) |
| `deep_reading_daemon.py` | tracked clean | `dharma_swarm/` or `scripts/` | Python source at root |
| `garden_daemon.py` | tracked clean | `dharma_swarm/` or `scripts/` | Python source at root |
| `nginx.conf` | tracked clean | `scripts/` or `api/` | deploy config |
| `overnight_summary.py` | tracked clean | `scripts/` | operator utility |
| `run_daemon.sh`, `run_deep_reading.sh`, `run_garden.sh`, `run_overnight.sh` | tracked clean | `scripts/` | only `run_operator.sh` and `swarm.sh` are canonical root entrypoints |
| `run_mcp_stdio.py` | tracked clean | `scripts/` | operator utility |
| `swarm.sh`, `swarm_live.sh` | tracked clean | **keep root** | canonical swarm entrypoints |
| `run_operator.sh` | tracked clean | **keep root** | canonical operator launcher |

---

## 5. Root Directories — Move / Cleanup Candidates

| Directory | Status | Contains modified files? | Proposed Action | Active Track? |
|---|---|---|---|---|
| `a2a-polish-mission/` | untracked | yes | move to `docs/missions/` or `docs/plans/` | no; mission-scoped |
| `analysis/` | tracked | no | move to `docs/analysis/` or `reports/` | no |
| `architecture/` | tracked | no | merge into `docs/architecture/` | no |
| `benchmarks/` | tracked | no | keep as top-level tooling or `scripts/benchmarks/` | no |
| `codex_skills/` | untracked | no | add to `.gitignore` or move to `docs/skills/` | no |
| `contracts/` | tracked | no | investigate duplicate with `dharma_swarm/contracts/`; merge or move under `dharma_swarm/` | no |
| `desktop-shell/` | tracked | no | keep if distinct from `dashboard/`; otherwise merge | no |
| `examples/` | tracked | no | keep as top-level examples | no |
| `experiments/` | tracked | no | keep as research scratch; add to allowlist | no |
| `foundations/` | tracked | no | **keep** as foundation substrate | no |
| `holon/` | tracked | yes | reconcile with `dharma_swarm/holon_*.py`; keep or merge | yes, holon track — **blocked** |
| `hooks/` | tracked | no | `scripts/hooks/` or keep as git hooks area | no |
| `inter_agent/` | tracked | no | `dharma_swarm/inter_agent/` or `docs/inter_agent/`; markdown inside to `reports/` | no |
| `lodestones/` | tracked | no | **keep** as foundation substrate | no |
| `mode_pack/` | tracked | no | **keep** as foundation/operational doctrine | no |
| `packages/` | tracked | no | `spinouts/` or `dharma_swarm/packages/` | no |
| `paper/` | gitignored | no | keep gitignored | no |
| `references/` | tracked | no | `docs/references/` | no |
| `research/` | tracked | no | `docs/research/` | no |
| `results/` | tracked | no | `reports/results/` | no |
| `roaming_mailbox/` | tracked | yes | move to `~/.dharma/` or `.gitignore` | no; runtime state |
| `seams/` | tracked | no | `docs/seams/` or `tests/seams/` | no |
| `spec-forge/` | tracked | no | `docs/spec-forge/` or merge into `specs/` | no |
| `specs/` | tracked | no | **keep** as formal spec domain | no |
| `spinouts/` | tracked | no | **keep** as incubation area | no |
| `terminal/` | tracked | no | **keep**; active track `helm-worldclass-terminal-2026-06` | yes — **blocked for restructuring** |
| `terminal-v2/` | untracked | no | reconcile with `terminal/`; do not merge without track owner approval | yes — **blocked** |
| `tools/` | tracked | no | `scripts/tools/` or keep as standalone tool area | no |
| `~/` | untracked | n/a | delete; shell-escape hazard | no |
| `wiki/` | tracked | no | reconcile with `droid-wiki/`; generated or canonical? | no |

---

## 6. Nested Structural Violations — Move Candidates

| Source | Target | Notes |
|---|---|---|
| `dharma_swarm/scripts/` | root `scripts/` | scripts package inside Python source violates organization rules |
| `dharma_swarm/chetana/tests/` | `tests/` as `test_chetana_*.py` | tests inside package violates rules |
| `dharma_swarm/skills/*.skill.md` (9 files) | `docs/skills/` | docs inside source |
| `dharma_swarm/a2a/README.md` | `docs/a2a/` or `docs/architecture/A2A_README.md` | docs inside source; active track adjacent — verify |
| `dharma_swarm/verify/README.md` | `docs/verify/` or `docs/ops/` | docs inside source |
| `dharma_swarm/chetana/README.md` | `docs/chetana/` | docs inside source |
| `dharma_swarm/chetana/claude_code_plugin/**/*.md` | `docs/chetana/` | docs inside source |
| `dharma_swarm/inter_agent/devin/outbound/*.md` | `reports/handoffs/` or `docs/inter_agent/` | inter-agent markdown inside source |

---

## 7. Active-Track Hazard Surfaces — Do Not Touch

The 11 active tracks and their owned surfaces. Factory Droid must not move, edit, or rename these without explicit track-owner approval.

| Track | Owned surfaces touched in current worktree |
|---|---|
| `runtime-truth-reconciliation-2026-06` | `dharma_swarm/operator_core/**`, `scripts/governance/agent_onboard.py`, `dharma_swarm/runtime_state.py` |
| `runtime-truth-nats-2026-06` | `docs/governance/NATS_SUBSTRATE_MASTER_SPEC.md`, `dharma_swarm/a2a/a2a_nats_contact.py`, `dharma_swarm/a2a/a2a_core_contact.py` |
| `runtime-truth-spine-adoption-2026-06` | `dharma_swarm/spine/**`, `dharma_swarm/a2a/a2a_bridge.py`, `dharma_swarm/orchestrator.py`, `dharma_swarm/agent_runner.py` |
| `loop-closure-2026-06` | `reports/loop_closure/**`, `CYBERNETIC_LOOP_MAP.md` |
| `orientation-graph-2026-06` | `scripts/governance/orientation_graph.py`, `tests/test_orientation_graph.py` |
| `composer-holon-spine-longrun-2026-06` | `docs/sovereign_holons/**`, `reports/sovereign_holons/**`, `dharma_swarm/holon_*.py`, `scripts/holon_*.py`, `tests/test_holon_*.py`, `holon/` |
| `agent-admission-semantic-commons-2026-06` | `docs/ontology/**`, `docs/ops/AGENT_ADMISSION.md`, `dharma_swarm/semantic_commons.py`, `dharma_swarm/engine/hybrid_retriever.py`, `dharma_swarm/context.py`, `scripts/governance/agent_admission*.py`, `scripts/governance/name_drift*.py`, `tests/test_agent_admission*.py`, `tests/test_semantic_commons*.py` |
| `cybernetics-codex-stewardship-2026-06` | `docs/ops/CYBERNETICS_CODEX.md`, `docs/agents/cybernetics_codex/**`, `dharma_swarm/cybernetics_codex.py`, `scripts/governance/cybernetics_codex_audit.py`, `scripts/governance/register_cybernetics_codex.py`, `tests/test_cybernetics_codex.py`, `reports/loop_closure/cybernetics_codex/**` |
| `telos-ai-morning-refinery-2026-06` | `docs/vision_maps/TELOS_AI_SEED_SPEC_V0.md`, `docs/vision_maps/TELOS_MORNING_REFINERY_V0.md`, `docs/research/telos_ai/**`, `PRODUCT_SURFACE.md`, `dashboard/src/app/dashboard/telos*/**`, `dashboard/src/lib/*`, `tests/test_telos*.py` |
| `helm-worldclass-terminal-2026-06` | `terminal/**`, `terminal-v2/`, `docs/TERMINAL_TUI_TMUX_HARNESS_2026-04-02.md`, `docs/plans/2026-04-02-terminal-*.md`, `reports/terminal/**` |
| `a2a-cloud-agent-bridge-2026-06` | `docs/governance/proposed_tracks/perplexity-a2a-bus-bridge-2026-06.yaml`, `docs/architecture/A2A_CLOUD_BRIDGE.md`, `dharma_swarm/a2a/a2a_cloud_contact.py`, `dharma_swarm/a2a/contact_registry.py`, `dharma_swarm/a2a/verifier.py`, `reports/state/a2a_score_denominator.md`, `tests/test_a2a_cloud_contact.py` |

---

## 8. Proposed `.gitignore` Additions

```gitignore
# Factory Droid generated / runtime state cleanup
droid-wiki/
*.bak
runtime.db
stigmergy.db
synthesizer_memory.json
shared/

# Timestamped verifier receipts (keep only latest stable witness in ~/.dharma/)
reports/sovereign_holons/verify_holon_harness_prod_*.json
reports/sovereign_holons/verify_holon_harness_prod_*.md
reports/a2a/*_receipts/
reports/a2a/nats_connect_signoffs/

# Generated eval / review intake artifacts
eval_probe_result.md
reports/governance/greptile_review_intake_*.json
reports/governance/name_drift_preflight_*.json

# Generated research / runtime truth dumps
reports/research/
reports/runtime_truth/
```

---

## 9. Proposed CI / Config Updates

| File | Why it needs updating |
|---|---|
| `.github/workflows/structure.yml` | Rule 8 root-markdown allowlist; if any root doc moves, update the allowlist or the workflow fails. Do **not** add new root entries — move files under governed directories instead. |
| `.gitignore` | Generated state cleanup. |
| `Makefile` | If `run_*.sh` scripts move, update any Makefile targets that reference them. |
| `docs/MEGAFILE_INDEX.md` | If slot paths change. |
| `docs/governance/CANONICAL_DOC_STACK.md` | If canonical docs move. |
| `ACTIVE_SURFACE_MANIFEST.yaml` | If any declared surface moves. |

---

## 10. Move Manifest — Phase B (after operator authorization)

This is the tentative set of safe moves for Phase B. Every move uses `git mv` for tracked files and records old path, new path, owner, reason, and verification.

| # | Old Path | New Path | Owner | Reason | Verification |
|---|---|---|---|---|---|
| 1 | `AGENTS.md` | `docs/AGENTS.md` (merge) | `docs/AGENTS.md` | root markdown hygiene | `make lint`, docops check |
| 2 | `AGENT_IDENTITY_UNIFICATION.md` | `docs/_archive/2026-04/` | `docs/AGENTS.md` | historical; newer version exists | read redirect check |
| 3 | `ANTHROPIC_GRANT_DRAFT.md` | `docs/research/` | `docs/research/` | funding artifact | link check |
| 4 | `AUDIT_2026-05-07.md` | `reports/audit/` | `reports/` | dated report | link check |
| 5 | `CLAUDE_CODE_LIVE_FIRE_PROMPT.md` | `docs/prompts/` | `docs/prompts/` | prompt artifact | link check |
| 6 | `DEVIN.md` | `docs/ops/` | `docs/ops/` | agent ops note | link check |
| 7 | `FOUNDATIONS_TO_CODE_MAP.md` | `docs/architecture/` | `docs/architecture/` | architecture note | link check |
| 8 | `GNANI_LODESTONE.md` | `docs/foundations/` | `docs/foundations/` | conceptual foundation | link check |
| 9 | `GUARDIAN_REPORT.md` | `reports/` | `reports/` | report | link check |
| 10 | `LIVING_LAYERS.md` | `docs/architecture/` | `docs/architecture/` | architecture note | link check |
| 11 | `MASTER_BUILD_SPEC.md` | `docs/plans/` | `docs/plans/` | plan | link check |
| 12 | `MODEL_ROUTING_MAP.md` | `docs/_archive/2026-04/` | `docs/_archive/` | stale per CLAUDE.md | link check |
| 13 | `NEXT_SPRINT_PROMPT.md` | `docs/plans/` | `docs/plans/` | prompt/plan | link check |
| 14 | `PHASE4_REPORT.md` | `reports/historical/` | `reports/` | historical report | link check |
| 15 | `QWEN.md` | `docs/ops/` | `docs/ops/` | agent ops note | link check |
| 16 | `WHAT_IT_WANTS_TO_BECOME.md` | `docs/foundations/` | `docs/foundations/` | foundation synthesis | link check |
| 17 | `WORLD_MODEL.md` | `docs/foundations/` | `docs/foundations/` | conceptual bedrock | link check |
| 18 | `agent_runner_audit.md` | `reports/` | `reports/` | audit | link check |
| 19 | `gaia_ui.md` | `docs/dse/` | `docs/dse/` | UX note | link check |
| 20 | `orchestrator_audit.md` | `reports/` | `reports/` | audit | link check |
| 21 | `phase2_darwin_diff_report.md` | `reports/` | `reports/` | report | link check |
| 22 | `program.md` | `docs/plans/` | `docs/plans/` | plan | link check |
| 23 | `program_ecosystem.md` | `docs/plans/` | `docs/plans/` | plan | link check |
| 24 | `xray_report.md` | `reports/` | `reports/` | report | link check |
| 25 | `xray_report.json` | `reports/` | `reports/` | report data | link check |
| 26 | `agent_loop.sh` | `scripts/` | `scripts/` | not canonical entrypoint | script still runs |
| 27 | `agni_trading_zoom_audit_2026_05_04.sh` | `scripts/` | `scripts/` | audit script | script still runs |
| 28 | `com.dharma.swarm.plist` | `scripts/` | `scripts/` | launchd config | update references |
| 29 | `cron_jobs.json` | `scripts/` | `scripts/` | runtime config | update references |
| 30 | `deep_reading_daemon.py` | `dharma_swarm/` | `dharma_swarm/` | Python source at root | import check + tests |
| 31 | `garden_daemon.py` | `dharma_swarm/` | `dharma_swarm/` | Python source at root | import check + tests |
| 32 | `nginx.conf` | `scripts/` | `scripts/` | deploy config | update references |
| 33 | `overnight_summary.py` | `scripts/` | `scripts/` | operator utility | script still runs |
| 34 | `run_daemon.sh` | `scripts/` | `scripts/` | launcher | update Makefile |
| 35 | `run_deep_reading.sh` | `scripts/` | `scripts/` | launcher | update Makefile |
| 36 | `run_garden.sh` | `scripts/` | `scripts/` | launcher | update Makefile |
| 37 | `run_overnight.sh` | `scripts/` | `scripts/` | launcher | update Makefile |
| 38 | `run_mcp_stdio.py` | `scripts/` | `scripts/` | operator utility | script still runs |
| 39 | `dharma_swarm/scripts/` | `scripts/` (merge) | `scripts/` | nested scripts package | import check |
| 40 | `dharma_swarm/chetana/tests/` | `tests/` (rename) | `tests/` | tests inside package | tests pass |
| 41 | `dharma_swarm/skills/*.skill.md` | `docs/skills/` | `docs/skills/` | docs inside source | link check |
| 42 | `dharma_swarm/a2a/README.md` | `docs/a2a/` | `docs/a2a/` | docs inside source | link check; a2a track adjacent |
| 43 | `dharma_swarm/verify/README.md` | `docs/verify/` | `docs/verify/` | docs inside source | link check |
| 44 | `dharma_swarm/chetana/README.md` | `docs/chetana/` | `docs/chetana/` | docs inside source | link check |
| 45 | `dharma_swarm/chetana/claude_code_plugin/**/*.md` | `docs/chetana/` | `docs/chetana/` | docs inside source | link check |
| 46 | `dharma_swarm/inter_agent/devin/outbound/*.md` | `reports/handoffs/` | `reports/handoffs/` | inter-agent markdown | link check |
| 47 | `a2a-polish-mission/` | `docs/missions/` | `docs/missions/` | mission work | link check |
| 48 | `analysis/` | `docs/analysis/` | `docs/analysis/` | not source/test/API | link check |
| 49 | `architecture/` | `docs/architecture/` | `docs/architecture/` | docs | link check |
| 50 | `references/` | `docs/references/` | `docs/references/` | reference docs | link check |
| 51 | `research/` | `docs/research/` | `docs/research/` | research docs | link check |
| 52 | `results/` | `reports/results/` | `reports/` | results | link check |
| 53 | `seams/` | `docs/seams/` | `docs/seams/` | seams docs | link check |
| 54 | `spec-forge/` | `docs/spec-forge/` | `docs/spec-forge/` | specs | link check |
| 55 | `tools/` | `scripts/tools/` | `scripts/tools/` | tools | script paths |
| 56 | `~/` | delete | n/a | shell escape hazard | verify deleted |

---

## 11. Verification Plan for Each Phase

After each wave:
- `make onboard` (must pass)
- `make orient` (must still show 11 active tracks and no new broken register items)
- `make bug-corral-scan` (must show no new errors/warnings)
- `pytest` on affected tests (must pass)
- `make lint` or `ruff check` (if code moved)
- `git status --porcelain` review (must show expected changes only)

---

## 12. Phase 0 Admission Status

- ✅ Contract reviewed and approved as a review packet.
- ✅ `docs/agents/factory_droid/agent.seed.yaml` created (shadow_registered, tooling_agent_read_only).
- ⏳ Semantic Commons registration (`semobj.factory_droid`, alias, orientation route) pending active-track owner approval.
- ⏳ `make agent-admit ...` full pass pending Semantic Commons registration.
- ✅ `make bug-corral-scan` passed.
- ✅ Affected admission/semantic-commons tests passed (17/17).
- ✅ Active-track hazard map captured.
- ⏳ Phase B execution **not authorized** until this inventory is reviewed and operator explicitly authorizes the move manifest.
