# 09 — Bug Corral Provenance

**Generated:** 2026-06-13 (Phase A of Bug Corral consolidation)
**Total source files audited:** 90
**Total bytes:** 1,493,478
**Branch:** `bug-corral-consolidate` (to be created off `main` when operator is at terminal)

This is the receipt. Every source file that contributes to the Bug Corral has one row in one of the tables below. The sha256 hash captures the file content at the moment of audit. After deletion, originals are recoverable via `git revert bug-corral-v1` or `git checkout bug-corral-v1~1 -- <path>`.

## Status legend

- **PENDING-DELETE** — content will be merged into target file, original to be deleted in Phase E.
- **KEPT-OUT-OF-SCOPE** — file is in scope of broader sweep but excluded from this pass (Category 8 plans, live code).
- **KEPT-LIVE-CODE** — Python module, JSON config, or CI file; stays where it is (per Prompt §3). Listed for reference.
- **STUB** — file is a 204-byte placeholder, no content to merge. Will be deleted.
- **EMPTY-ACK** — inter-agent inbound file, may be acknowledgment only; review during Phase B.

## Source-file count by target

| Target file | Family | Source count | Total bytes |
|---|---|---|---|
| `01_TRUTH_VERIFIERS.md` | Truth Verifiers | 11 | 118,828 |
| `02_ANTI_SLOP.md` | Anti-Slop / Vibe-Code | 6 | 101,860 |
| `03_REPO_XRAY.md` | Repo X-Rays / Global Audits | 14 | 233,522 |
| `04_INVENTORIES.md` | Inventories / Censuses | 15 | 382,025 |
| `07_DOCTRINE.md` | Doctrine / Prompts | 8 | 140,472 |
| `06_INCIDENTS.md` | Incidents / Forensics | 31 | 396,446 |
| `08_ARCHIVED_FINDINGS.md` | Archived Findings | 5 | 120,325 |

---

## Phase B — In-Scope Source Files (PENDING-DELETE)

Every file below will be merged into its target file in Phase B, then deleted in Phase E.

### Category 1 → `01_TRUTH_VERIFIERS.md` (Truth Verifiers)

| # | Path | mtime | bytes | sha256 (12) | author | status | summary |
|---|---|---|---|---|---|---|---|
| 1 | `reports/governance/runtime_truth_command_cutover_baseline_2026-06-12.md` | 2026-06-13 | 2,719 | `6f6a94b56c9a` | — | PENDING-DELETE | Generated: 2026-06-12 Worktree: `/Users/dhyana/dharma_swarm_main` - Branch: `holon/spine-v1` |
| 2 | `reports/governance/runtime_truth_command_cutover_after_action_2026-06-12.md` | 2026-06-13 | 7,875 | `b70af30c08b2` | — | PENDING-DELETE | Generated: 2026-06-12 Worktree: `/Users/dhyana/dharma_swarm_main` Branch: `holon/spine-v1` HEAD at verification: `f0d03f |
| 3 | `reports/anatomy_altitude_2026-06-10/lane_B_truth.md` | 2026-06-13 | 19,014 | `4ac9eb6ddd69` | — | PENDING-DELETE | /.dharma/state/runtime.db`; `spine_bypass_report.py` executed live. Every claim cites file:line. Clean negatives are fir |
| 4 | `docs/sovereign_holons/STATE_OF_TRUTH.md` | 2026-06-13 | 6,583 | `0d1ce4397004` | opus_composer, by reading the actua | PENDING-DELETE | **Why this file exists:** Everything else in this folder describes what we *intend* to build. This file is the one place |
| 5 | `docs/governance/RUNTIME_TRUTH_COMMAND_CUTOVER.md` | 2026-06-13 | 9,273 | `d640298c1806` | — | PENDING-DELETE | Status: active enforcement map, not a new spine. This document records the command cutover state for live operator-facin |
| 6 | `reports/governance/runtime_truth_spine_v2_subagent2_v1_verification.md` | 2026-06-06 | 6,838 | `b8a0f52562c1` | — | PENDING-DELETE | Role: V1 Verification Agent Worktree: `/Users/dhyana/worktrees/dharma_swarm_runtime_truth_spine_v2` HEAD: `2737b26d7ed8d |
| 7 | `reports/governance/runtime_truth_spine_v2_report.md` | 2026-06-06 | 11,531 | `e07ca1ec928e` | — | PENDING-DELETE | Runtime Truth Spine v2 was built from a clean worktree at current `origin/main`, not from the dirty developer checkout.  |
| 8 | `reports/governance/runtime_truth_spine_v2_evidence_plan.md` | 2026-06-06 | 7,806 | `2d5eafcdaebd` | — | PENDING-DELETE | Subagent: Tracer/Evidence Captain Audit source boundary: - Clean audit baseline: `d5ebc456` from the clean-main architec |
| 9 | `docs/research/RUNTIME_TRUTH_SPINE_COMPLETION_PLAN.md` | 2026-06-06 | 22,871 | `e931d82f0620` | — | PENDING-DELETE | **Scope:** Stabilize the Runtime Truth Spine as the substrate. No ontology refactor, no ingestor rewrite, no runtime beh |
| 10 | `docs/reports/CONVERGED_SEAM_AUDIT_RUNTIME_TRUTH_SPINE.md` | 2026-06-06 | 16,203 | `bfbc9240d561` | — | PENDING-DELETE | **Purpose:** Establish one shared diagnosis and one shared build direction before more agent-fabric work begins. |
| 11 | `docs/reports/DGC_FORENSIC_TRUTH_REPORT_2026-03-08.md` | 2026-04-04 | 8,115 | `f6f3116a855e` | — | PENDING-DELETE | - Repo: ` /dharma_swarm` - Branch: `split/2026-03-08` @ `8077792` - Audit mode: static code audit + executable command v |

### Category 2 → `02_ANTI_SLOP.md` (Anti-Slop / Vibe-Code)

| # | Path | mtime | bytes | sha256 (12) | author | status | summary |
|---|---|---|---|---|---|---|---|
| 1 | `reports/governance/anti_ai_slop_scan_snapshot_2026-06-08.json` | 2026-06-13 | 6,076 | `e9c5e4729439` | — | PENDING-DELETE | { "id": "anti-ai-slop-scan-snapshot-2026-06-08", "status": "local research artifact", "worktree": "/Users/dhyana/dharma_ |
| 2 | `reports/governance/anti_ai_slop_futureproof_deep_dive_2026-06-07.md` | 2026-06-13 | 26,285 | `19eb14194955` | — | PENDING-DELETE | Status: research and local scan packet. Not a PR, not a merge blocker by itself. Prepared: 2026-06-07 Worktree: `/Users/ |
| 3 | `reports/governance/anti_ai_slop_control_backlog_2026-06-08.md` | 2026-06-13 | 16,230 | `aa1ed7feaa4a` | — | PENDING-DELETE | Status: local execution backlog. Do not treat as merged doctrine until promoted through governance review. Related artif |
| 4 | `reports/audits/vibe_code_audit_2026-06-07.md` | 2026-06-13 | 37,119 | `6c6303678049` | Devin (Cognition AI) — session `7c5 | PENDING-DELETE | (no header summary) |
| 5 | `docs/governance/ANTI_SLOP_RULES.md` | 2026-06-13 | 11,878 | `42e6425e9180` | — | PENDING-DELETE | Phase 4 of the governance install. Each rule is anchored to a canonical surface verified during the 2026-04-26 audit. Th |
| 6 | `spec-forge/self-evolving-organism/ANTI_SLOP_REPORT.json` | 2026-03-31 | 4,272 | `673422e0809f` | — | PENDING-DELETE | { "overall_status": "CONDITIONAL_PASS", "failing_count": 0, "warning_count": 2, "non_metric_warnings": [ "External model |

### Category 3 → `03_REPO_XRAY.md` (Repo X-Rays / Global Audits)

| # | Path | mtime | bytes | sha256 (12) | author | status | summary |
|---|---|---|---|---|---|---|---|
| 1 | `docs/reports/modularity_and_future_proofing_audit_v1.md` | 2026-06-06 | 27,194 | `cff773daba47` | Devin (external worker, evidence-on | PENDING-DELETE | **Scope:** Full-power audit of repo modularity, future-proofing for increasing model capacity & multi-agent infra, ident |
| 2 | `xray_report.md` | 2026-06-05 | 6,385 | `c2a5b5acbfeb` | — | PENDING-DELETE | *Generated 2026-04-04T09:23:56 UTC* - **Path**: `/home/user/workspace/dharma_swarm` - **Files analyzed**: 1231 - **Total |
| 3 | `docs/governance/REPO_GOVERNANCE_AUDIT.md` | 2026-05-21 | 34,260 | `f98dad0a05fc` | — | PENDING-DELETE | **Scope**: Read-only. No code changes. No runtime modification. |
| 4 | `xray_report.json` | 2026-05-13 | 24,720 | `36b9ff262cca` | — | PENDING-DELETE | { "repo_name": "dharma_swarm", "repo_path": "/home/user/workspace/dharma_swarm", "generated_at": "2026-04-04T09:23:29.11 |
| 5 | `AUDIT_2026-05-07.md` | 2026-05-07 | 28,399 | `9f2d08a980d0` | — | PENDING-DELETE | Branch: `routing-lane-source` @ `ddcd720` ("feat(cron): add shakti executive handler"). Tools used: cloc, tokei, vulture |
| 6 | `reports/xray_revenue_packet_20260313/xray_report.md` | 2026-04-04 | 5,231 | `23b16c48f816` | — | PENDING-DELETE | *Generated 2026-03-13T15:07:21 UTC* - **Path**: `/Users/dhyana/dharma_swarm` - **Files analyzed**: 446 - **Total lines** |
| 7 | `reports/dgc_self_proving_packet_20260313/campaign_xray_spec.md` | 2026-04-04 | 2,936 | `44392820a3e5` | — | PENDING-DELETE | Date: 2026-03-13 Offer stage: design partner Status: ready to sell as a managed diagnostic |
| 8 | `docs/reports/GSTACK_SYSTEM_UPGRADE_AUDIT_2026-03-14.md` | 2026-04-04 | 9,908 | `69599d915ef2` | — | PENDING-DELETE | 2026-03-14 Review `garrytan/gstack` and extract the highest-leverage patterns for the current system: - `DGC` |
| 9 | `docs/reports/20-AGENT-DEEP-AUDIT-2026-03-29.md` | 2026-04-04 | 21,920 | `28fe8680d719` | — | PENDING-DELETE | **Scope**: Post-cleanup comprehensive audit — not "do tests pass" but "does the system work end-to-end" **Agents deploye |
| 10 | `docs/doctor/DOCTOR_10_ROUND_AUDIT_2026-03-16.md` | 2026-04-04 | 9,038 | `e4fedcf05e5a` | — | PENDING-DELETE | Date: 2026-03-16 Repo: `/Users/dhyana/dharma_swarm` Operator lane: Orthogonal assurance / merge-safety |
| 11 | `reports/historical/xray_report.md` | 2026-04-01 | 8,554 | `9776e73ff6cc` | — | PENDING-DELETE | title: 'Repo X-Ray: dharma_swarm' path: reports/historical/xray_report.md slug: repo-x-ray-dharma-swarm doc_type: note s |
| 12 | `reports/historical/FULL_REPO_AUDIT_2026-03-28.md` | 2026-04-01 | 16,104 | `4e02d1c2b2c4` | — | PENDING-DELETE | title: Full Repository Audit — Post-Constitutional Hardening path: reports/historical/FULL_REPO_AUDIT_2026-03-28.md slug |
| 13 | `reports/historical/CONSTITUTIONAL_XRAY_REPORT.md` | 2026-04-01 | 21,778 | `fe3342fafb6a` | — | PENDING-DELETE | title: 'Constitutional X-Ray Report: dharma_swarm' path: reports/historical/CONSTITUTIONAL_XRAY_REPORT.md slug: constitu |
| 14 | `reports/xray_revenue_packet_20260313/xray_report.json` | 2026-03-31 | 17,095 | `dbd0fc54dfba` | — | PENDING-DELETE | { "repo_name": "dharma_swarm", "repo_path": "/Users/dhyana/dharma_swarm", "generated_at": "2026-03-13T15:07:21.862051+00 |

### Category 4 → `04_INVENTORIES.md` (Inventories / Censuses)

| # | Path | mtime | bytes | sha256 (12) | author | status | summary |
|---|---|---|---|---|---|---|---|
| 1 | `docs/docops/AUTO_INVENTORY.md` | 2026-06-13 | 585 | `3c4e8a19961d` | — | PENDING-DELETE | This file is generated by `scripts/docops/check_docops_integrity.py`. Do not hand-edit the generated block. <!-- DOCOPS: |
| 2 | `docs/state/CROSS_AGENT_INVENTORY.md` | 2026-06-06 | 12,128 | `7723453c7943` | : | PENDING-DELETE | > **2026-05-29 refresh note:** Since this inventory was generated, main has advanced > from 693 to 702 commits. Notable  |
| 3 | `docs/research/palantir-ontology/vocabulary-census/passes/3b-governance-code-walk.md` | 2026-06-06 | 27,920 | `76232e1cfc28` | ** Governance Pass B agent (code-wa | PENDING-DELETE | (no header summary) |
| 4 | `docs/research/palantir-ontology/vocabulary-census/passes/3a-governance-external-research.md` | 2026-06-06 | 53,162 | `6d0006250bf4` | perplexity-computer (Governance Pas | PENDING-DELETE | **Mandate:** PhD-grade external research on enterprise-grade ontology governance. DO NOT propose names. Build the eviden |
| 5 | `docs/research/palantir-ontology/vocabulary-census/passes/1b-code-reality-map.md` | 2026-06-06 | 43,887 | `68f0cb7f0761` | ** Pass 1b agent (code-walker) | PENDING-DELETE | (no header summary) |
| 6 | `docs/research/palantir-ontology/vocabulary-census/andon/2026-06-01T0628Z-andon-audit-verification.md` | 2026-06-06 | 7,778 | `1f33e36e9e62` | — | PENDING-DELETE | **Pulled by:** perplexity-computer **Pulled at:** 2026-06-01T06:28Z **Severity:** RED — all hands on deck **Toyota analo |
| 7 | `docs/research/palantir-ontology/auto-grounded/2026-06-02-0001-pr-433-andon-verdicts-state-ownership-a2a-collision.md` | 2026-06-06 | 10,188 | `a325a2e538d4` | — | PENDING-DELETE | **Artifact:** PR #433 — “andon(verdict): devin slices D + E — restacked onto main” (https://github.com/AmitabhainArunach |
| 8 | `docs/research/palantir-ontology/auto-grounded/2026-06-01-2301-pr-431-kaizen-runtime-truth-refs.md` | 2026-06-06 | 10,725 | `9c92fc24bf72` | — | PENDING-DELETE | - **Artifact:** PR #431 — “feat(kaizen): bind reviews to runtime truth refs” ([GitHub PR](https://github.com/AmitabhainA |
| 9 | `docs/research/palantir-ontology/auto-grounded/2026-06-01-1400-pr406-runtime-governance-telos-gate.md` | 2026-06-06 | 9,194 | `083b29d92cf8` | — | PENDING-DELETE | **Artifact:** PR #406 — “feat(ontology): hard-wire telos gate into execute_action (W1 — runtime governance)” ([GitHub PR |
| 10 | `docs/research/palantir-ontology/auto-grounded/2026-06-01-0823-pr418-devin-andon-verdicts-D-E.md` | 2026-06-06 | 23,674 | `8dc38699e939` | app/devin-ai-integration | PENDING-DELETE | **Artifact:** PR #418 — `andon(verdict): devin slices D + E — workflow state partially_confirmed, A2A collision overstat |
| 11 | `docs/reports/proof_artifact_internal_benchmark_inventory_v1.md` | 2026-06-06 | 16,977 | `6a100dd92c53` | — | PENDING-DELETE | **Operator constraint (verbatim):** "We need to prove we have the authority to audit agent systems which means we need t |
| 12 | `docs/architecture/memory_surfaces_census_v3.md` | 2026-06-06 | 7,229 | `abbd00999812` | — | PENDING-DELETE | Date: 2026-05-11 Status: M0 implementation scaffold MemoryKernel M0 establishes the registry and read-only census layer  |
| 13 | `docs/architecture/memory_kernel_m4a_shadow_report_sweep.md` | 2026-06-06 | 2,037 | `2464ff0877ac` | — | PENDING-DELETE | Date: 2026-05-14 Status: read-only shadow report sweep M4A collects representative context parity reports before MemoryK |
| 14 | `reports/docops/corpus_inventory.md` | 2026-05-24 | 29,156 | `d6ba5ae9ff37` | — | PENDING-DELETE | This is a non-blocking inventory for doc cleanup agents. The blocking gate remains `scripts/docops/check_docops_integrit |
| 15 | `reports/docops/corpus_inventory.json` | 2026-05-24 | 127,385 | `4810889c4794` | — | PENDING-DELETE | { "absolute_path_ref_count": 1535, "absolute_path_refs": [ { "line": 21, "path": ".dharma_psmv_hyperfile_branch/shared/m |

### Category 6 → `07_DOCTRINE.md` (Doctrine / Prompts)

| # | Path | mtime | bytes | sha256 (12) | author | status | summary |
|---|---|---|---|---|---|---|---|
| 1 | `reports/swarm_genome/2026-06-11/agent_4_governance_operating_canon.md` | 2026-06-13 | 7,184 | `59587c460678` | — | PENDING-DELETE | Date: 2026-06-11 Mode: read-only scan Question: What rules tell agents how to work safely, and what do those rules hide? |
| 2 | `docs/governance/hygiene/AUDIT_PROMPT.md` | 2026-06-13 | 18,294 | `a1cec900551b` | — | PENDING-DELETE | Generated from `docs/governance/hygiene/patterns/*.yaml`. Use this as the anti-slop field checklist for a PR, module, or |
| 3 | `docs/governance/hygiene/AI_AGENT_GOVERNANCE.md` | 2026-06-13 | 5,498 | `34f02d182453` | — | PENDING-DELETE | Status: advisory hygiene tranche. Promote individual `AI-*` records through `LIFECYCLE.md` before turning them into hard |
| 4 | `docs/offers/agentic-code-governance-sprint.md` | 2026-05-13 | 5,446 | `b7217c7f25ed` | — | PENDING-DELETE | **Offer type:** Paid service engagement (3-7 days) **Target buyer:** Engineering leads at AI-heavy teams shipping with c |
| 5 | `docs/loomwork/vision/06_partner_governance_funding.md` | 2026-05-13 | 41,949 | `1a98cd6b9380` | worker fork (research pass), 2026-0 | PENDING-DELETE | **Frame:** Loomwork at level 100 is not a project — it is an institution that survives a decade and grows through hostil |
| 6 | `docs/telos-engine/07_VSM_GOVERNANCE.md` | 2026-04-04 | 51,176 | `f62771ff7bb5` | — | PENDING-DELETE | (no header summary) |
| 7 | `.dharma/shared/cartographer_notes.md` | 2026-04-04 | 2,183 | `7cfcf0876d40` | — | PENDING-DELETE | *2026-04-04 01:23 UTC \| task: e0d926d0 \| trace: trc_a8bf05976ab3480ea40f36f06ec31379* _provenance_: `.dharma/shared/prov |
| 8 | `docs/prompts/DEEP_REPO_CARTOGRAPHER_PROMPT_2026-03-31.md` | 2026-04-02 | 8,742 | `49688e704ac3` | — | PENDING-DELETE | title: Deep Repo Cartographer Prompt path: docs/prompts/DEEP_REPO_CARTOGRAPHER_PROMPT_2026-03-31.md slug: deep-repo-cart |

### Category 7 → `06_INCIDENTS.md` (Incidents / Forensics)

| # | Path | mtime | bytes | sha256 (12) | author | status | summary |
|---|---|---|---|---|---|---|---|
| 1 | `reports/living_agent_kernel/living-agent-kernel-20260605/verifier_matrix.md` | 2026-06-13 | 57,753 | `fab0e111112b` | — | PENDING-DELETE | Mission: `living-agent-kernel-20260605` Slice: durable runtime plus append-only wake ledger plus source normalizers, sou |
| 2 | `reports/handoffs/PHANTOM_ACKER_FINDINGS_2026-06-11.md` | 2026-06-13 | 3,749 | `6d53f41e8b5c` | — | PENDING-DELETE | **There is no phantom acker.** The acks on `dharma.a2a.devin.ack.<packet_id>` with payload `{"ack":true,"from":"devin-ro |
| 3 | `inter_agent/devin/outbound/2026-06-11T01-50Z-phantom-acker-resolution-and-janitor-ack.md` | 2026-06-13 | 2,589 | `a657a2cce57e` | — | PENDING-DELETE | 01:50Z) - **From:** devin (`devin-roaming-2987d222`), live session - **To:** dharma_swarm hub / Fable 5 / codex lane - * |
| 4 | `docs/sovereign_holons/READINESS_VERDICT.md` | 2026-06-13 | 5,066 | `74002c163b5d` | — | PENDING-DELETE | 318k tokens. **Verdict:** **GO_AFTER_GAPS · 38% ready.** Not safe to start a multi-hour *autonomous* build. The design i |
| 5 | `docs/research/telos_ai/2026-06-13_codex_feasibility_audit.md` | 2026-06-13 | 29,141 | `9bedf33ab46e` | — | PENDING-DELETE | Date: 2026-06-13 Repo audited: `/Users/dhyana/dharma_swarm` Branch audited: `telos-ai-seed-v0-from-sandbox` Seed commit  |
| 6 | `reports/governance/execution_identity_lineage_blast_radius_audit.md` | 2026-06-06 | 41,124 | `e309aef8f232` | — | PENDING-DELETE | Date: 2026-06-01 Audit target: `/Users/dhyana/worktrees/dharma_swarm_runtime_truth_spine_v2` Branch: `codex/runtime-trut |
| 7 | `inter_agent/mike/inbound/2026-06-01T0628Z-andon-audit-verification.md` | 2026-06-06 | 8,153 | `db010efd9035` | — | PENDING-DELETE | **Action requested:** pick one or more slices (A–F) in the body below, post verdict file to `docs/research/palantir-onto |
| 8 | `inter_agent/hermes/inbound/2026-06-01T0628Z-andon-audit-verification.md` | 2026-06-06 | 8,157 | `46cae99e7d46` | — | PENDING-DELETE | **Action requested:** pick one or more slices (A–F) in the body below, post verdict file to `docs/research/palantir-onto |
| 9 | `inter_agent/gpt55/inbound/2026-06-01T0628Z-andon-audit-verification.md` | 2026-06-06 | 8,155 | `4ae994c98892` | — | PENDING-DELETE | **Action requested:** pick one or more slices (A–F) in the body below, post verdict file to `docs/research/palantir-onto |
| 10 | `inter_agent/devin/outbound/2026-05-28-devin-autonomous-expansion-audit.md` | 2026-06-06 | 4,752 | `69197149d162` | — | PENDING-DELETE | **From:** Devin (Roaming) — `AGT-DEVIN_ROAMING_2987D222` **To:** Operator + Codex + Claude **Artifact:** `docs/reports/a |
| 11 | `inter_agent/devin/outbound/2026-05-25_devin_11_step_chain_verdict.md` | 2026-06-06 | 5,029 | `bf36fc8e6a66` | — | PENDING-DELETE | **From:** devin-roaming-2987d222 **To:** codex_5_5_cli **In response to:** `inter_agent/devin/inbound/2026-05-25_codex_r |
| 12 | `inter_agent/devin/inbound/2026-06-01T0628Z-andon-audit-verification.md` | 2026-06-06 | 8,155 | `61893e1a59a5` | — | PENDING-DELETE | **Action requested:** pick one or more slices (A–F) in the body below, post verdict file to `docs/research/palantir-onto |
| 13 | `inter_agent/codex/inbound/2026-06-01T0628Z-andon-audit-verification.md` | 2026-06-06 | 8,155 | `cb5dbc0a4ca1` | — | PENDING-DELETE | **Action requested:** pick one or more slices (A–F) in the body below, post verdict file to `docs/research/palantir-onto |
| 14 | `inter_agent/claude/inbound/2026-06-01T0628Z-andon-audit-verification.md` | 2026-06-06 | 8,157 | `0bc01bf363dc` | — | PENDING-DELETE | **Action requested:** pick one or more slices (A–F) in the body below, post verdict file to `docs/research/palantir-onto |
| 15 | `docs/state/DASHBOARD_FIDELITY_AUDIT.md` | 2026-06-06 | 6,603 | `5e552702eda7` | Devin (architecture review) | PENDING-DELETE | (no header summary) |
| 16 | `docs/reports/wedge_resurvey_burn_and_substrate_audit_v1.md` | 2026-06-06 | 15,095 | `3f7907ef3256` | — | PENDING-DELETE | **Trigger:** Operator shelved PR #372 (Research Cell pivot). Research is important but not the right wedge for self-sust |
| 17 | `docs/reports/autonomous_expansion_seed_audit_2026-05-28.md` | 2026-06-06 | 46,977 | `d7b47de8b628` | Devin (Roaming) — `AGT-DEVIN_ROAMIN | PENDING-DELETE | **Active track at time of audit:** `runtime-truth-spine-2026-06` (`ACTIVE_TRACK.yaml`) **Doctrine documents this audit r |
| 18 | `reports/ops/GOVERNANCE_CLEAN_BRANCH_READINESS.md` | 2026-05-13 | 4,893 | `9a5c22765b09` | — | PENDING-DELETE | Date: 2026-04-27 - Candidate branch: `governance/tier-1-clean` - Worktree: `/Users/dhyana/promotion_worktrees/dharma_swa |
| 19 | `phase2_darwin_diff_report.md` | 2026-05-13 | 3,353 | `7dafa869a45a` | — | PENDING-DELETE | **New method: `_generate_real_diff`** (lines 2684–2789) - Added as a method on the `DarwinEngine` class |
| 20 | `orchestrator_audit.md` | 2026-05-13 | 204 | `b7209281365a` | — | STUB | Snapshot, do not trust without re-verification. The historical content moved to [docs/_archive/2026-04/orchestrator_audi |
| 21 | `agent_runner_audit.md` | 2026-05-13 | 204 | `ee4222f73f0c` | — | STUB | Snapshot, do not trust without re-verification. The historical content moved to [docs/_archive/2026-04/agent_runner_audi |
| 22 | `PHASE4_REPORT.md` | 2026-05-13 | 3,981 | `780c24b0fa40` | — | PENDING-DELETE | **LanceDB Version:** 0.30.2 |
| 23 | `GUARDIAN_REPORT.md` | 2026-05-09 | 2,105 | `36608d61c836` | 2026-05-09T04:46:40.051068+00:00 | PENDING-DELETE | *Generated: 2026-05-09T04:46:40.051068+00:00* *Src root: /Users/dhyana/dharma_swarm/dharma_swarm* \| Severity \| Count \| \| |
| 24 | `reports/ecosystem_forensics_audit_2026-03-19.md` | 2026-04-04 | 14,291 | `6438480ad0db` | — | PENDING-DELETE | Date: 2026-03-19 Scope: - Local canonical repo: `/Users/dhyana/dharma_swarm` - Local comparison repos: `/Users/dhyana/re |
| 25 | `reports/dashboard/DASHBOARD_WIRING_AUDIT_2026-03-19.md` | 2026-04-04 | 3,573 | `a6d59bb66d36` | — | PENDING-DELETE | - The dashboard/backend contract is mostly live. The FastAPI surface behind `dashboard/` is not broadly broken. - Endpoi |
| 26 | `reports/CRYPTOGRAPHIC_AUDIT_TRAILS_RESEARCH.md` | 2026-04-04 | 34,944 | `3ee76fa2d6a1` | — | PENDING-DELETE | **Research Report** **Purpose**: Investigation of proven cryptographic audit trail systems for tamper-proof software evo |
| 27 | `docs/reports/PLANETARY_RECIPROCITY_COMMONS_GOVERNANCE_CHARTER_2026-03-11.md` | 2026-04-04 | 4,201 | `88ab50fcebb2` | — | PENDING-DELETE | Date: 2026-03-11 Status: draft v0 Purpose: anti-greenwashing, anti-capture, and legitimacy rules for the reciprocity sys |
| 28 | `docs/reports/JIKOKU_FINAL_REPORT.md` | 2026-04-04 | 13,532 | `311193fd05d3` | — | PENDING-DELETE | **Result**: 1.61x total speedup, bottleneck eliminated |
| 29 | `docs/reports/JIKOKU_BASELINE_FINDINGS.md` | 2026-04-04 | 7,180 | `387763c5e35b` | — | PENDING-DELETE | **Session**: baseline-1772932668 **Log**: ` /.dharma/jikoku/baseline.jsonl` |
| 30 | `docs/reports/DGC_TO_DHARMA_SWARM_SCOUT_REPORT_2026-03-09.md` | 2026-04-04 | 29,158 | `2505170faca0` | — | PENDING-DELETE | Date: 2026-03-09 Role: `SCOUT` Prompt source: [`/Users/dhyana/audit-signal/DGC_TO_DHARMA_SWARM_SCOUT_PROMPT.md#L1`](/Use |
| 31 | `docs/reports/DGC_DUAL_ENGINE_REALITY_MAP_2026-03-13.md` | 2026-04-04 | 8,017 | `10ea1529c40f` | — | PENDING-DELETE | Date: 2026-03-13 Purpose: state plainly where DGC stands, what is real, what is missing, what is frontier-valid, and wha |

### Category 9 → `08_ARCHIVED_FINDINGS.md` (Archived Findings)

| # | Path | mtime | bytes | sha256 (12) | author | status | summary |
|---|---|---|---|---|---|---|---|
| 1 | `docs/state/_archive/LIVE_OPS_DASHBOARD_2026-05-11.md` | 2026-06-06 | 9,178 | `f6e72ea01bb8` | — | PENDING-DELETE | **Path:** `docs/state/LIVE_OPS_DASHBOARD.md` **Snapshot date:** 2026-05-11 **Read first if tired:** this is the place to |
| 2 | `docs/_archive/2026-04/orchestrator_audit.md` | 2026-05-13 | 32,745 | `83b20d60492b` | Senior DevOps — forensic review | PENDING-DELETE | > Snapshot, do not trust without re-verification. Archived 2026-05-06 because live code and governance moved past this d |
| 3 | `docs/_archive/2026-04/agent_runner_audit.md` | 2026-05-13 | 31,606 | `ee36c5e63ec0` | Senior DevOps Engineer | PENDING-DELETE | > Snapshot, do not trust without re-verification. Archived 2026-05-06 because live code and governance moved past this d |
| 4 | `docs/_archive/2026-04/AGENT_IDENTITY_UNIFICATION.md` | 2026-05-13 | 38,073 | `12b186bf2e81` | — | PENDING-DELETE | > Snapshot, do not trust without re-verification. Archived 2026-05-06 because live code and governance moved past this d |
| 5 | `docs/archive/FIRST_LIVE_RUN_REPORT.md` | 2026-04-03 | 8,723 | `e9b2f01e9acb` | — | PENDING-DELETE | title: First Live Run Report path: docs/archive/FIRST_LIVE_RUN_REPORT.md slug: first-live-run-report doc_type: report st |

---

## Out-of-Scope (KEPT) — Live Code, Category 8 Plans, CI Configs

Listed for completeness. **Not touched by this pass.**

### Category 8 — Plans That Are Also Finders (KEPT-OUT-OF-SCOPE)

A future audit will collapse these ~15 plan docs into ~5 files. Hands off this round.

- `docs/plans/2026-03-22-dharma-swarm-audit-merge.md`
- `docs/plans/2026-03-26-runtime-truthfulness-cleanup.md`
- `docs/plans/2026-03-26-status-doctor-truthfulness.md`
- `docs/plans/2026-03-28-dirty-hot-map.md`
- `docs/plans/2026-03-28-hot-seam-freeze-plan.md`
- `docs/plans/2026-03-28-runtime-spine-audit-and-trust-report.md`
- `docs/plans/2026-04-02-living-layers-preaudit.md`
- `docs/plans/2026-04-02-program-pair-relocation-preaudit.md`
- `docs/plans/2026-04-02-reports-cartography-and-cleanup-plan.md`
- `docs/plans/2026-04-02-retained-generated-packet-families-preaudit.md`
- `docs/plans/2026-04-02-root-future-move-preaudit.md`
- `docs/plans/2026-04-03-substrate-directory-cartography.md`
- `docs/plans/2026-04-03-verification-family-classification-preaudit.md`
- `docs/plans/2026-04-03-verification-probe-citation-census.md`
- `docs/plans/2026-05-22-dashboard-ssot-architecture.md`

### Live Python / JSON / CI Files (KEPT-LIVE-CODE)

These produce finder-files or implement audit logic. The Prompt §3 contract is absolute: no relocation. Each is referenced from the relevant target file as a pointer entry.

| Path | Purpose |
|---|---|
| `dharma_swarm/auditor.py` | Importable audit engine. Imported by dual_audit.py, shakti_warrant.py, foreman.py. |
| `dharma_swarm/dual_audit.py` | Two-perspective audit runner. |
| `dharma_swarm/xray.py` | Importable xray engine. Imported by morning_after.py, dgc_cli.py. |
| `dharma_swarm/scout_audit.py` | Scout-style sweep. Used by scout_health.py. |
| `dharma_swarm/harness_audit.py` | Test-harness audit. |
| `dharma_swarm/ginko_audit.py` | Ginko organ audit. Largest single audit module (53.5 KB). |
| `dharma_swarm/ginko_report_gen.py` | Ginko report generator. |
| `dharma_swarm/api_key_audit.py` | API key sprawl audit. |
| `dharma_swarm/semantic_governance.py` | Semantic-level governance checks. |
| `dharma_swarm/scout_report.py` | Scout report formatter. |
| `dharma_swarm/memory_kernel/census.py` | Memory kernel census engine. |
| `dharma_swarm/dhyana/drift_triage.py` | Drift triage for dhyana organ. |
| `dharma_swarm/chetana/governance.py` | Chetana governance module. |
| `dharma_swarm/terminal_commands/governance.py` | TUI governance commands. |
| `dharma_swarm/tui/engine/governance.py` | TUI engine governance. |
| `scripts/repo_xray.py` | The repo x-ray runner. Generates xray_report.{md,json}. |
| `scripts/governance_scan.py` | Top-level governance scan entrypoint. |
| `scripts/operator_ground_truth.py` | Operator's ground-truth view. |
| `scripts/vibegate_audit.py` | Vibegate audit runner. |
| `scripts/close_duplicate_guardian_issues.py` | Closes duplicate Guardian issues. |
| `scripts/memory_surface_census.py` | Memory surface census runner. |
| `scripts/runtime/live_ops_census.py` | Live ops census runner. |
| `scripts/runtime/ci_truth.py` | CI truth contract checker (runs in CI). |
| `scripts/runtime/cwt_report.py` | CWT report runner. |
| `scripts/governance/spine_bypass_report.py` | Detects spine bypass paths. |
| `scripts/governance/cybernetics_codex_audit.py` | Codex cybernetics audit runner. |
| `scripts/governance/hygiene/audit_agent_prompt.py` | Audit agent prompt runner. |
| `tools/manifest_check.py` | Manifest check tool (referenced in DEVIN.md, RUNBOOK). |
| `tools/manifest_check_budgets.json` | Budgets for manifest check. |
| `.semgrep/dharma-anti-slop.yml` | Semgrep rules implementing the 10 anti-slop rules. Runs in CI. |
| `docs/governance/CI_TRUTH_CONTRACT.json` | Machine-readable CI truth contract. |
| `.github/ISSUE_TEMPLATE/governance.md` | Governance issue template. |
| `.github/workflows/stale-pr.yml` | Stale-PR detector workflow. |
| `agni_trading_zoom_audit_2026_05_04.sh` | Shell audit runner (review separately if still used). |
| `dharma_swarm/skills/cartographer.skill.md` | Skill spec for cartographer agent. |

---

## Conflicts Resolved

Log of cases where two source files contradict each other and the corral picks a winner. Populated during Phase B as conflicts are encountered.

_(none yet — Phase B not started)_

---

## Notes from Phase A

- **90 in-scope files identified** (Prompt §0 estimated ~80; deviation of +12% is within tolerance per §8). New finds beyond the original `finder_files_corral.md` sweep:
  - `reports/historical/CONSTITUTIONAL_XRAY_REPORT.md`, `FULL_REPO_AUDIT_2026-03-28.md`, `xray_report.md`
  - `reports/ops/GOVERNANCE_CLEAN_BRANCH_READINESS.md`
  - `reports/swarm_genome/2026-06-11/agent_4_governance_operating_canon.md`
  - `reports/xray_revenue_packet_20260313/xray_report.{md,json}`
  - `reports/dgc_self_proving_packet_20260313/campaign_xray_spec.md`
  - `reports/CRYPTOGRAPHIC_AUDIT_TRAILS_RESEARCH.md`
  - `docs/loomwork/vision/06_partner_governance_funding.md`
  - `docs/offers/agentic-code-governance-sprint.md`
  - `docs/telos-engine/07_VSM_GOVERNANCE.md`
  - `docs/research/palantir-ontology/auto-grounded/2026-06-01-0823-...`, `1400-...`, `2301-...`, `2026-06-02-0001-...`
  - `docs/research/palantir-ontology/vocabulary-census/passes/3a-governance-external-research.md`
  - `inter_agent/*/inbound/2026-06-01T0628Z-andon-audit-verification.md` × 6 worktrees
  - `inter_agent/devin/outbound/*` × 3
  - `spec-forge/self-evolving-organism/ANTI_SLOP_REPORT.json`
  - `reports/living_agent_kernel/.../verifier_matrix.md`

- **Two 204-byte stubs at repo root** (`agent_runner_audit.md`, `orchestrator_audit.md`) confirmed as placeholders. Real content is in `docs/_archive/2026-04/` at 31–32 KB each. Per Prompt §6, full versions merge to `08_ARCHIVED_FINDINGS.md`; stubs marked STUB and deleted.

- **Six inter-agent inbound files are likely identical** (8155–8157 bytes, same name, same date, distributed across 6 worktrees). To verify in Phase B: compare hashes:
  - `inter_agent/claude/inbound/2026-06-01T0628Z-andon-audit-verification.md` → sha `0bc01bf363dc0514`
  - `inter_agent/codex/inbound/2026-06-01T0628Z-andon-audit-verification.md` → sha `cb5dbc0a4ca13c73`
  - `inter_agent/devin/inbound/2026-06-01T0628Z-andon-audit-verification.md` → sha `61893e1a59a534e8`
  - `inter_agent/gpt55/inbound/2026-06-01T0628Z-andon-audit-verification.md` → sha `4ae994c988921c69`
  - `inter_agent/hermes/inbound/2026-06-01T0628Z-andon-audit-verification.md` → sha `46cae99e7d469ce1`
  - `inter_agent/mike/inbound/2026-06-01T0628Z-andon-audit-verification.md` → sha `db010efd90355d7a`

- **`xray_report.md` mtime anomaly:** 2026-06-05 mtime, content header says "Generated 2026-04-04T09:23:56 UTC". File was touched (re-stat'd) without regeneration. Flag as meta-finding in `03_REPO_XRAY.md`.

- **`xray_report.json` (24.7 KB)** and **`reports/docops/corpus_inventory.json` (127 KB)** exceed the 5 KB inline-in-markdown threshold. Will be moved to `docs/bug-corral/artifacts/` per Prompt §6.

- **`docs/state/_archive/LIVE_OPS_DASHBOARD_2026-05-11.md` mtime is 2026-06-06** — was edited after being archived. Capture as finding.

---

## Mac/sandbox limitation note

The agent's `pc bash` shell cannot write to `.git/` on John's Mac. All git operations (branch create, commit, tag, delete) must be run by John in a terminal once he is off mobile. The agent will produce the exact shell commands as files in `docs/bug-corral/` for John to copy-paste.

---

## What happens next

Phase A is complete when John approves this manifest. After approval, the agent will execute Phase B: write target files `01_TRUTH_VERIFIERS.md` through `08_ARCHIVED_FINDINGS.md` one at a time, sharing each for inspection. No source file is deleted until Phase D (verifier script) and Phase E (the delete commands, to be run by John).

