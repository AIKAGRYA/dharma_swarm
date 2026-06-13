# 09 Provenance Manifest

Receipt for the Bug Corral consolidation, rebuilt for the signal-quality objective:
the corral holds only what is still useful for understanding what is broken, risky,
inconsistent, incomplete, or uncertain today. This manifest grades every finding-bearing
candidate, records de-duplication decisions, and proves coverage of the live problem surface.

**As of:** 2026-06-13  
**Repo:** `AmitabhainArunachala/dharma_swarm` (local clone `/home/ubuntu/repos/dharma-swarm`)  
**Branch:** `devin/1781340172-bug-corral` off `main` @ `9c76b210`  
**Disposition:** MERGE 41 · KEEP-LIVE 25 · ARCHIVE-INDEX 30 · DROP-DUP 11 · EXCLUDE 266 (of 355 finding-bearing candidates)

## Method

This pass searched by content and function, not filenames. A scorer over all
**1,012** tracked Markdown files ranked each by finder-function tokens (audit, x-ray,
census, forensic, reality/gap map, readiness, triage, drift, verification, incident, andon)
and finding tokens (blocker, severity, verdict, broken, stale, mismatch, BR-, risk,
uncertain, incomplete). Filtering to function>=3 and finding>=4 and removing run-output
bulk yielded **355 finding-bearing candidates**. Git authored-dates split them into
**202 current-era** (last touched >= 2026-05-01) and **153 older** (the pre-pivot
DGC / GAIA / ISARA / JIKOKU / telos-engine era).

De-duplication used sha256 over candidate clusters; the top current audits were read in
full to grade by content rather than score.

## Grades and actions

> Grade  
> - **ENDURING** — still useful for understanding what is broken/risky/uncertain today.  
> - **RESOLVED-HIST** — historical finding already resolved or superseded (pre-pivot era).  
> - **GENERATED** — machine-generated artifact (regenerates from a script).  
> - **DASHBOARD** — operational dashboard / live snapshot.  
> - **DOCTRINE** — canonical doctrine the finders enforce.  
> - **LEDGER-CANON** — active ledger or canonical authority (the live problem surface).  
> - **RESEARCH/VISION** — not a repo-defect finder (research, vision, spec, plan, prompt).  
> - **DUP** — exact or near-duplicate / acknowledgement fan-out.  
>
> Action  
> - **MERGE** — extract findings into the target corral file, then `git rm` the source.  
> - **KEEP-LIVE** — live/generated/canon/ledger; a one-line pointer goes into the corral, the file is NOT deleted.  
> - **ARCHIVE-INDEX** — condense into `08_ARCHIVED_FINDINGS.md`; if the source already lives in an `_archive/` dir it is NOT deleted, only indexed.  
> - **DROP-DUP** — duplicate / fan-out; logged here and `git rm`'d without a separate merge.  
> - **EXCLUDE** — out of scope (not a repo-defect finder); not touched.

## Three scope decisions (recommendations — override at this gate)

1. **Live ledgers are pointed to, not copied.** `BROKEN_REGISTER.md` (BR-NNN),
   `INTERFACE_MISMATCH_MAP.md`, `REALITY_DEBT_LEDGER.md`, `REPO_GOVERNANCE_AUDIT.md`,
   `SOVEREIGN_MANIFEST.md` are the canonical owners of 'what is broken today'. The corral
   links them; it does not duplicate them (duplicating would create the exact drift the
   repo polices). The corral consolidates the scattered one-off **reports** that are not
   owned by any live ledger.
2. **Already-archived files are indexed, not deleted.** Files already under `_archive/`,
   `docs/archive/`, `reports/historical/` are condensed into `08` with a pointer and left
   in place (AGENTS.md: do not silently delete historical context). Loose historical audits
   sitting in active dirs are condensed into `08` and `git rm`'d.
3. **MERGE scope is the finding-bearing reports only.** Live owners (KEEP-LIVE), generated
   artifacts, dashboards, and research/vision/spec/plan/prompt files stay out of the merge
   set. The MERGE set below is what actually becomes corral content and is later deleted.

## Corral content plan (01-08)

Each target file: the family, the live owner it points to, and the reports merged into it.

### 01_TRUTH_VERIFIERS.md
- Family: declared-vs-actual, wiring / fidelity / seam audits
- Live owner(s) pointed to: BROKEN_REGISTER, INTERFACE_MISMATCH_MAP, REPO_GOVERNANCE_AUDIT, VERIFICATION_LANE
- Merged reports (9): `CONVERGED_SEAM_AUDIT_RUNTIME_TRUTH_SPINE.md`, `DASHBOARD_FIDELITY_AUDIT.md`, `DASHBOARD_WIRING_AUDIT_2026-03-19.md`, `reconciliation.md`, `perplexity-A.md`, `perplexity-B.md`, `perplexity-C.md`, `devin-D.md`, `devin-E.md`

### 02_ANTI_SLOP.md
- Family: vibe-code / AI-slop findings
- Live owner(s) pointed to: ANTI_SLOP_RULES, VIBE_CODE_HYGIENE, hygiene/*, PR_QUALITY_GATES
- Merged reports (4): `vibe_code_audit_2026-06-07.md`, `anti_ai_slop_control_backlog_2026-06-08.md`, `anti_ai_slop_futureproof_deep_dive_2026-06-07.md`, `handoff.md`

### 03_REPO_XRAY.md
- Family: structural x-rays, modularity, waste, archaeology
- Live owner(s) pointed to: SOVEREIGN_MANIFEST, NAVIGATION, AUTO_INVENTORY
- Merged reports (11): `modularity_and_future_proofing_audit_v1.md`, `DHARMA_FORGE_HYDRA_ARCHAEOLOGY_2026-06-11.md`, `autonomous_expansion_seed_audit_2026-05-28.md`, `wedge_resurvey_burn_and_substrate_audit_v1.md`, `lane_A_economic.md`, `lane_B_truth.md`, `lane_C_evolution.md`, `lane_D_spine_canon.md`, `lane_E_organism_vision.md`, `lane_F_world.md`, `xray_report.md`

### 04_INVENTORIES.md
- Family: censuses and inventories
- Live owner(s) pointed to: AUTO_INVENTORY, memory_surfaces registry
- Merged reports (4): `memory_surfaces_census_v3.md`, `CROSS_AGENT_INVENTORY.md`, `proof_artifact_internal_benchmark_inventory_v1.md`, `proof_artifact_slate_v1.md`

### 05_RUNTIME_GROUND_TRUTH.md
- Family: runtime truth packets, receipts, spine v2 evidence
- Live owner(s) pointed to: REALITY_DEBT_LEDGER, LIVE_OPS_DASHBOARD, active_track_evidence
- Merged reports (11): `runtime_truth_spine_v2_report.md`, `runtime_truth_spine_v2_evidence_plan.md`, `runtime_truth_spine_v2_subagent2_v1_verification.md`, `runtime_truth_command_cutover_after_action_2026-06-12.md`, `runtime_truth_command_cutover_baseline_2026-06-12.md`, `GATE1_WITNESSED.md`, `RECEIPT_AND_VEL_EQUIVALENCE_MATRIX.md`, `01_gap_matrix.md`, `verifier_matrix.md`, `final_report.md`, `semantic_context_receipt.md`

### 06_INCIDENTS.md
- Family: forensics, incidents, triage, blast-radius, andon
- Live owner(s) pointed to: BROKEN_REGISTER
- Merged reports (2): `execution_identity_lineage_blast_radius_audit.md`, `worktree_triage_report_2026-06-10.md`

### 07_DOCTRINE.md
- Family: the doctrine the finders enforce (mostly pointers)
- Live owner(s) pointed to: ANTI_SLOP_RULES, COHERENCE_DELTA, CANONICAL_DOC_STACK, CI_GATES
- Merged reports: none — 07 is a pointer-map to live doctrine (all KEEP-LIVE).

### 08_ARCHIVED_FINDINGS.md
- Family: resolved/historical findings, condensed index
- Live owner(s) pointed to: reports/historical, docs/archive, docs/_archive
- Indexed sources: 30 archived/historical findings (see ARCHIVE-INDEX table).

## MERGE set (becomes corral content, then deleted)

| Path | Dates (first->last) | Grade | Target | Note |
|------|--------------------|-------|--------|------|
| `docs/reports/CONVERGED_SEAM_AUDIT_RUNTIME_TRUTH_SPINE.md` | 2026-05-28 -> 2026-05-28 | ENDURING | 01_TRUTH_VERIFIERS.md | Converged seam audit (routing x pool x A2A x provider): accretion in agent_runner/swarm/orchestrator/providers; build the Runtime Truth Spine first. |
| `docs/research/palantir-ontology/vocabulary-census/andon/reconciliation.md` | 2026-06-05 -> 2026-06-05 | ENDURING | 01_TRUTH_VERIFIERS.md | Andon reconciliation (Codex audit vs ground truth): verdict matrix. Load-bearing finding: ontology.py:594-639 execute_action logs success without applying mutations; InterruptGate auto-approve at cascade.py:36. |
| `docs/research/palantir-ontology/vocabulary-census/andon/verdicts/devin-D.md` | 2026-06-02 -> 2026-06-02 | ENDURING | 01_TRUTH_VERIFIERS.md | Andon slice D (workflow-state owners) evidence. |
| `docs/research/palantir-ontology/vocabulary-census/andon/verdicts/devin-E.md` | 2026-06-02 -> 2026-06-02 | ENDURING | 01_TRUTH_VERIFIERS.md | Andon slice E (A2A protocol vs work-queue conflation) evidence. |
| `docs/research/palantir-ontology/vocabulary-census/andon/verdicts/perplexity-A.md` | 2026-06-05 -> 2026-06-05 | ENDURING | 01_TRUTH_VERIFIERS.md | Andon slice A (identity sprawl) evidence backing the reconciliation. |
| `docs/research/palantir-ontology/vocabulary-census/andon/verdicts/perplexity-B.md` | 2026-06-05 -> 2026-06-05 | ENDURING | 01_TRUTH_VERIFIERS.md | Andon slice B (envelope schemas) evidence backing the reconciliation. |
| `docs/research/palantir-ontology/vocabulary-census/andon/verdicts/perplexity-C.md` | 2026-06-05 -> 2026-06-05 | ENDURING | 01_TRUTH_VERIFIERS.md | Andon slice C (authority+execution) evidence backing the reconciliation. |
| `docs/state/DASHBOARD_FIDELITY_AUDIT.md` | 2026-06-05 -> 2026-06-05 | ENDURING | 01_TRUTH_VERIFIERS.md | Dashboard data-fidelity audit: provider keys present; remaining env-alias and provider-auth fidelity gaps. |
| `reports/dashboard/DASHBOARD_WIRING_AUDIT_2026-03-19.md` | 2026-03-23 -> 2026-03-23 | RESOLVED-HIST | 01_TRUTH_VERIFIERS.md | Older dashboard wiring audit; mostly superseded by DASHBOARD_FIDELITY_AUDIT. Merge as historical baseline. |
| `reports/audits/vibe_code_audit_2026-06-07.md` | 2026-06-07 -> 2026-06-07 | ENDURING | 02_ANTI_SLOP.md | Vibe-code audit @ fc2200758c: test-quality ratios, weak-only assertions, structural slop. Largest current finding set. |
| `reports/governance/anti_ai_slop_control_backlog_2026-06-08.md` | 2026-06-09 -> 2026-06-09 | ENDURING | 02_ANTI_SLOP.md | Anti-AI-slop control backlog: local execution backlog of slop controls. |
| `reports/governance/anti_ai_slop_futureproof_deep_dive_2026-06-07.md` | 2026-06-09 -> 2026-06-09 | ENDURING | 02_ANTI_SLOP.md | Anti-AI-slop future-proofing deep dive: scan packet. |
| `reports/quality/anti_vibe/20260605-dharma-swarm-anti-vibe-quality-index/handoff.md` | 2026-06-12 -> 2026-06-12 | ENDURING | 02_ANTI_SLOP.md | Anti-vibe quality index handoff (2026-06). |
| `docs/ops/DHARMA_FORGE_HYDRA_ARCHAEOLOGY_2026-06-11.md` | 2026-06-12 -> 2026-06-12 | ENDURING | 03_REPO_XRAY.md | Forge/Hydra archaeology: live-ops registers Forge Reality Arena Hydra but scripts/start_forge_hydra_long_run.sh does not exist on main; real state off-repo. |
| `docs/reports/autonomous_expansion_seed_audit_2026-05-28.md` | 2026-06-05 -> 2026-06-05 | ENDURING | 03_REPO_XRAY.md | Autonomous expansion seed audit + activation plan. |
| `docs/reports/modularity_and_future_proofing_audit_v1.md` | 2026-06-05 -> 2026-06-05 | ENDURING | 03_REPO_XRAY.md | Modularity / future-proofing audit: substrate vs drift; language is not the problem. |
| `docs/reports/wedge_resurvey_burn_and_substrate_audit_v1.md` | 2026-06-05 -> 2026-06-05 | ENDURING | 03_REPO_XRAY.md | Burn audit + monetizable-substrate inventory: $2k/mo burn is operator-reported not measured. |
| `reports/anatomy_altitude_2026-06-10/lane_A_economic.md` | 2026-06-12 -> 2026-06-12 | ENDURING | 03_REPO_XRAY.md | Anatomy-altitude lane A (economic) system x-ray. |
| `reports/anatomy_altitude_2026-06-10/lane_B_truth.md` | 2026-06-12 -> 2026-06-12 | ENDURING | 03_REPO_XRAY.md | Anatomy-altitude lane B (truth) system x-ray. |
| `reports/anatomy_altitude_2026-06-10/lane_C_evolution.md` | 2026-06-12 -> 2026-06-12 | ENDURING | 03_REPO_XRAY.md | Anatomy-altitude lane C (evolution) system x-ray. |
| `reports/anatomy_altitude_2026-06-10/lane_D_spine_canon.md` | 2026-06-12 -> 2026-06-12 | ENDURING | 03_REPO_XRAY.md | Anatomy-altitude lane D (spine/canon) system x-ray. |
| `reports/anatomy_altitude_2026-06-10/lane_E_organism_vision.md` | 2026-06-12 -> 2026-06-12 | ENDURING | 03_REPO_XRAY.md | Anatomy-altitude lane E (organism/vision) system x-ray. |
| `reports/anatomy_altitude_2026-06-10/lane_F_world.md` | 2026-06-12 -> 2026-06-12 | ENDURING | 03_REPO_XRAY.md | Anatomy-altitude lane F (world) system x-ray. |
| `xray_report.md` | 2026-03-15 -> 2026-04-08 | GENERATED | 03_REPO_XRAY.md | Root repo X-Ray output, internally 'Generated 2026-04-04'. Stale generated artifact; merge the stale-X-Ray meta-finding, delete the stale copy. |
| `docs/architecture/memory_surfaces_census_v3.md` | 2026-05-23 -> 2026-05-23 | ENDURING | 04_INVENTORIES.md | Memory Surfaces Census v3: MemoryKernel M0 registry + read-only census of memory-like surfaces. |
| `docs/reports/proof_artifact_internal_benchmark_inventory_v1.md` | 2026-06-05 -> 2026-06-05 | ENDURING | 04_INVENTORIES.md | Internal benchmark inventory for the proof-artifact pivot. |
| `docs/reports/proof_artifact_slate_v1.md` | 2026-06-05 -> 2026-06-05 | ENDURING | 04_INVENTORIES.md | Proof-artifact slate: candidate proof artifacts and their status. |
| `docs/state/CROSS_AGENT_INVENTORY.md` | 2026-05-24 -> 2026-06-01 | ENDURING | 04_INVENTORIES.md | Cross-agent inventory of open strings across Devin sessions (snapshot). |
| `docs/research/RECEIPT_AND_VEL_EQUIVALENCE_MATRIX.md` | 2026-06-04 -> 2026-06-04 | ENDURING | 05_RUNTIME_GROUND_TRUTH.md | Receipt and VEL equivalence matrix: maps receipt types across owners (spine/runtime_state/idempotency). |
| `docs/research/spine-adoption-phase/01_gap_matrix.md` | 2026-06-05 -> 2026-06-05 | ENDURING | 05_RUNTIME_GROUND_TRUTH.md | Spine-adoption gap matrix: per-caller gap to invoke_agent/EvidenceReceipt. (Exact dup at seams/spine-adoption/01_gap_matrix.md -> DROP.) |
| `reports/governance/GATE1_WITNESSED.md` | 2026-06-12 -> 2026-06-12 | ENDURING | 05_RUNTIME_GROUND_TRUTH.md | Operator-witnessed EvidenceReceipt gate-1 receipt: receipt_count 0->1. |
| `reports/governance/runtime_truth_command_cutover_after_action_2026-06-12.md` | 2026-06-12 -> 2026-06-12 | ENDURING | 05_RUNTIME_GROUND_TRUTH.md | Runtime Truth command cutover after-action: enforced existing spine, created no new command spine. |
| `reports/governance/runtime_truth_command_cutover_baseline_2026-06-12.md` | 2026-06-12 -> 2026-06-12 | ENDURING | 05_RUNTIME_GROUND_TRUTH.md | Runtime Truth command cutover baseline receipt: 63 dirty files before pass. |
| `reports/governance/runtime_truth_spine_v2_evidence_plan.md` | 2026-06-01 -> 2026-06-01 | ENDURING | 05_RUNTIME_GROUND_TRUTH.md | Runtime Truth Spine v2 evidence bundle plan. |
| `reports/governance/runtime_truth_spine_v2_report.md` | 2026-06-01 -> 2026-06-01 | ENDURING | 05_RUNTIME_GROUND_TRUTH.md | Runtime Truth Spine v2 report: v1 claim corrected, built from clean worktree. |
| `reports/governance/runtime_truth_spine_v2_subagent2_v1_verification.md` | 2026-06-01 -> 2026-06-01 | ENDURING | 05_RUNTIME_GROUND_TRUTH.md | Spine v2 subagent-2 verification: clean-HEAD v1 claim falsified. |
| `reports/living_agent_kernel/living-agent-kernel-20260605/final_report.md` | 2026-06-11 -> 2026-06-11 | ENDURING | 05_RUNTIME_GROUND_TRUTH.md | Living-agent-kernel final report: readiness verdict. |
| `reports/living_agent_kernel/living-agent-kernel-20260605/semantic_context_receipt.md` | 2026-06-11 -> 2026-06-11 | ENDURING | 05_RUNTIME_GROUND_TRUTH.md | Living-agent-kernel semantic context receipt. |
| `reports/living_agent_kernel/living-agent-kernel-20260605/verifier_matrix.md` | 2026-06-11 -> 2026-06-11 | ENDURING | 05_RUNTIME_GROUND_TRUTH.md | Living-agent-kernel verifier matrix: pass/fail per verifier check. |
| `reports/governance/execution_identity_lineage_blast_radius_audit.md` | 2026-06-01 -> 2026-06-01 | ENDURING | 06_INCIDENTS.md | Execution identity lineage + blast-radius audit: ExecutionIdentity spine real but not saturated; parallel id lineages remain. |
| `reports/worktree_triage_report_2026-06-10.md` | 2026-06-12 -> 2026-06-12 | ENDURING | 06_INCIDENTS.md | Worktree triage: which branches/worktrees carry live work vs stale. |

## KEEP-LIVE owners (pointer-only, NOT deleted)

| Path | Grade | Why pointer-only |
|------|-------|------------------|
| `docs/state/HOTLIST.md` | DASHBOARD | Repo-wide running task board (kanban). Live operational board. Pointer-only. |
| `docs/state/LIVE_OPS_DASHBOARD.md` | DASHBOARD | Live-ops operational dashboard. Regenerates. Pointer-only. |
| `docs/architecture/VERIFICATION_LANE.md` | DOCTRINE | Active read-only verifier doctrine. Live. Pointer-only. |
| `docs/governance/ANTI_SLOP_RULES.md` | DOCTRINE | Canonical anti-slop rules; backed by .semgrep + workflows. Live doctrine for 02. Pointer-only. |
| `docs/governance/CANONICAL_DOC_STACK.md` | DOCTRINE | Doc-ownership map (which doc owns which truth). Live. Pointer-only. |
| `docs/governance/CI_GATES.md` | DOCTRINE | CI gate doctrine. Live. Pointer-only. |
| `docs/governance/COHERENCE_DELTA.md` | DOCTRINE | Merge-time 4-field coherence gate + BR-id pre-flight. Live doctrine. Pointer-only. |
| `docs/governance/PR_QUALITY_GATES.md` | DOCTRINE | PR quality gate doctrine. Live. Pointer-only. |
| `docs/governance/VIBE_CODE_HYGIENE.md` | DOCTRINE | Canonical vibe-code antipattern catalogue + runnable scan. Live doctrine for 02. Pointer-only. |
| `docs/governance/hygiene/AI_AGENT_GOVERNANCE.md` | DOCTRINE | AI-agent hygiene governance doctrine. Live. Pointer-only. |
| `docs/governance/hygiene/LIFECYCLE.md` | DOCTRINE | Hygiene pattern lifecycle doctrine. Live. Pointer-only. |
| `docs/governance/hygiene/README.md` | DOCTRINE | Governance hygiene folder doctrine; patterns/*.yaml is source. Live. Pointer-only. |
| `docs/docops/AUTO_INVENTORY.md` | GENERATED | Generated repo inventory block (check_docops_integrity.py). Pointer-only. |
| `docs/governance/hygiene/AUDIT_PROMPT.md` | GENERATED | Vibe-code audit prompt, generated from patterns/*.yaml. Pointer-only. |
| `docs/governance/hygiene/CATALOGUE.md` | GENERATED | Hygiene catalogue, generated from patterns/*.yaml. Pointer-only. |
| `reports/governance/active_track_evidence.md` | GENERATED | Generated track-portfolio evidence (check_track_status.py). Pointer-only. |
| `reports/governance/parallel_lane_map.md` | GENERATED | Generated lane/branch operating snapshot. Pointer-only. |
| `CYBERNETIC_LOOP_MAP.md` | LEDGER-CANON | 13-loop closure map. Owned by loop-closure track. Stale-flagged by BR-012. Pointer-only. |
| `INTERFACE_MISMATCH_MAP.md` | LEDGER-CANON | Interface-level declared-vs-actual gap log (auto-maintained). The live substrate for 01. Pointer-only. |
| `docs/architecture/NAVIGATION.md` | LEDGER-CANON | Organ/navigation map. Stale-flagged by BR-010 but live owner. Pointer-only. |
| `docs/governance/REALITY_DEBT_LEDGER.md` | LEDGER-CANON | Anti-overclaim firewall: high-value claims still needing proof (the 'uncertain today' surface). Pointer-only. |
| `docs/governance/REPO_GOVERNANCE_AUDIT.md` | LEDGER-CANON | CANON (docs/AGENTS.md): owns contradictions/staleness. Pointer-only. |
| `docs/governance/SOVEREIGN_MANIFEST.md` | LEDGER-CANON | CANON: architecture, invariants, measured repo state. Pointer-only. |
| `docs/state/BROKEN_REGISTER.md` | LEDGER-CANON | Append-only BR-NNN ledger of broken/stale/degraded surfaces. THE live 'what is broken today' owner. Pointer-only. |
| `foundations/EMPIRICAL_CLAIMS_REGISTRY.md` | LEDGER-CANON | Registry of empirical claims + their evidence status. Active ledger. Pointer-only. |

## ARCHIVE-INDEX (condense into 08)

Already-archived sources are indexed and left in place; loose historical audits are
indexed and `git rm`'d (decision 2).

| Path | What | Already archived? |
|------|------|:-----------------:|
| `agent_runner_audit.md` | 204-byte root stub -> real content in docs/_archive/2026-04/. Stub: DROP; content: index. | no |
| `docs/_archive/2026-04/agent_runner_audit.md` | Production-readiness audit of agent_runner.py (2026-04-05). Already archived. | yes |
| `docs/_archive/2026-04/orchestrator_audit.md` | Production-readiness audit of orchestrator.py (2026-04-05). Already archived. | yes |
| `docs/archive/FIRST_LIVE_RUN_REPORT.md` | First live-run report. Already archived. | yes |
| `docs/archive/PALANTIR_ONTOLOGY_GAP_ANALYSIS.md` | Palantir ontology gap analysis. Already archived. | yes |
| `docs/archive/VERIFICATION_COMPLETE.md` | TLA+ verification complete (2026-03-09). Already archived; near-dup of specs/VERIFICATION_COMPLETE.md. | yes |
| `docs/doctor/DOCTOR_10_ROUND_AUDIT_2026-03-16.md` | Doctor 10-round merge-safety audit (2026-03-16). Pre-pivot. | no |
| `docs/reports/20-AGENT-DEEP-AUDIT-2026-03-29.md` | 20-agent deep audit (2026-03-29): not production-ready, MTBF 4-12h. Pre-pivot. | no |
| `docs/reports/DGC_DUAL_ENGINE_REALITY_MAP_2026-03-13.md` | DGC dual-engine reality map (2026-03-13). Pre-pivot. | no |
| `docs/reports/DGC_FORENSIC_TRUTH_REPORT_2026-03-08.md` | DGC forensic truth report (2026-03-08). Pre-pivot DGC era. | no |
| `docs/reports/DGC_FULL_POWER_GAP_MAP_2026-03-11.md` | DGC full-power gap map (2026-03-11). Pre-pivot. | no |
| `docs/reports/FITNESS_LANDSCAPE_ANALYSIS.md` | Fitness-landscape analysis (2026-03-09). Pre-pivot. | no |
| `docs/reports/GSTACK_SYSTEM_UPGRADE_AUDIT_2026-03-14.md` | gstack pattern-extraction audit (2026-03-14). Pre-pivot. | no |
| `docs/state/_archive/LIVE_OPS_DASHBOARD_2026-05-07.md` | Archived live-ops snapshot. Already archived. | yes |
| `docs/state/_archive/LIVE_OPS_DASHBOARD_2026-05-11.md` | Archived live-ops snapshot. Already archived. | yes |
| `orchestrator_audit.md` | 204-byte root stub -> real content in docs/_archive/2026-04/. Stub: DROP; content: index. | no |
| `reports/audit/000_MASTER_COHERENCE_SYNTHESIS.md` | Master coherence synthesis (2026-04-27). Superseded by REPO_GOVERNANCE_AUDIT. | no |
| `reports/audit/05_SLICE1_REVIEW.md` | Coherence audit slice-1 review (2026-04-27). | no |
| `reports/audit/07_SLICE2_REVIEW.md` | Coherence audit slice-2 review (2026-04-27). | no |
| `reports/audit/09_SLICE3_LEDGER_WATCHER_RESULT.md` | Coherence audit slice-3 ledger-watcher result (2026-04-27). | no |
| `reports/ecosystem_forensics_audit_2026-03-19.md` | Ecosystem forensics audit (2026-03-19) vs OpenHands/Letta/LangGraph etc. | no |
| `reports/historical/CONSTITUTIONAL_HARDENING_SPRINT_REPORT.md` | Constitutional hardening sprint report. Already historical. | yes |
| `reports/historical/CONSTITUTIONAL_XRAY_REPORT.md` | Constitutional X-Ray (2026-03-27). Pre-pivot. Already in reports/historical. | yes |
| `reports/historical/DUAL_SPRINT_COMPLETION_REPORT.md` | Dual-sprint completion report. Already historical. | yes |
| `reports/historical/FULL_REPO_AUDIT_2026-03-28.md` | Full repo audit (2026-03-28), front-matter RESOLVED. Already historical. | yes |
| `reports/historical/GODEL_CLAW_V1_REPORT.md` | Godel-Claw v1 report. Already historical. | yes |
| `reports/historical/PHASE3_COMPLETION_REPORT.md` | Phase-3 completion report. Already historical. | yes |
| `reports/historical/xray_report.md` | Historical repo X-Ray (Generated 2026-03-14). Already historical. | yes |
| `reports/ops/GOVERNANCE_CLEAN_BRANCH_READINESS.md` | Governance clean-branch readiness (2026-04-27). | no |
| `reports/ops/PRECOMMIT_HOTFIX_RESULT.md` | Pre-commit hotfix result (2026-04-27). | no |

## De-duplication ledger

| Dropped path | Canonical kept | Why |
|--------------|----------------|-----|
| `docs/research/palantir-ontology/vocabulary-census/andon/2026-06-01T0628Z-andon-audit-verification.md` | `docs/research/palantir-ontology/vocabulary-census/andon/reconciliation.md` | Andon cord-pull broadcast (source of the fan-out). Context, not a standing finding. |
| `inter_agent/claude/inbound/2026-06-01T0628Z-andon-audit-verification.md` | `docs/research/palantir-ontology/vocabulary-census/andon/reconciliation.md` | Andon fan-out copy (addressee=claude). Near-identical 126-line body. |
| `inter_agent/codex/inbound/2026-06-01T0628Z-andon-audit-verification.md` | `docs/research/palantir-ontology/vocabulary-census/andon/reconciliation.md` | Andon fan-out copy (addressee=codex). |
| `inter_agent/devin/inbound/2026-06-01T0628Z-andon-audit-verification.md` | `docs/research/palantir-ontology/vocabulary-census/andon/reconciliation.md` | Andon fan-out copy (addressee=devin). |
| `inter_agent/gpt55/inbound/2026-06-01T0628Z-andon-audit-verification.md` | `docs/research/palantir-ontology/vocabulary-census/andon/reconciliation.md` | Andon fan-out copy (addressee=gpt55). |
| `inter_agent/hermes/inbound/2026-06-01T0628Z-andon-audit-verification.md` | `docs/research/palantir-ontology/vocabulary-census/andon/reconciliation.md` | Andon fan-out copy (addressee=hermes). |
| `inter_agent/mike/inbound/2026-06-01T0628Z-andon-audit-verification.md` | `docs/research/palantir-ontology/vocabulary-census/andon/reconciliation.md` | Andon fan-out copy (addressee=mike). |
| `seams/spine-adoption/01_gap_matrix.md` | `docs/research/spine-adoption-phase/01_gap_matrix.md` | Byte-identical duplicate directory. |
| `seams/spine-adoption/02_master_spec.md` | `docs/research/spine-adoption-phase/02_master_spec.md` | Byte-identical duplicate directory. |
| `seams/spine-adoption/03_codex_55_plan.md` | `docs/research/spine-adoption-phase/03_codex_55_plan.md` | Byte-identical duplicate directory. |
| `specs/VERIFICATION_COMPLETE.md` | `docs/archive/VERIFICATION_COMPLETE.md` | Near-duplicate TLA+ verification report. |

Additional clustering decisions:

- **`seams/spine-adoption/` == `docs/research/spine-adoption-phase/`**: byte-identical
  directory pair (sha256 confirmed for all three files). Keep the `docs/research` copy;
  `01_gap_matrix.md` is the only finder (MERGE->05); the master-spec and codex plan are
  active_spec/working_plan (EXCLUDE). The `seams/` triplet is DROP-DUP.
- **Andon fan-out**: `2026-06-01T0628Z-andon-audit-verification.md` exists in 6 inter_agent
  inboxes plus the vocabulary-census source (7 near-identical copies, only the addressee
  line differs). The standing finding lives in `andon/reconciliation.md` (+ 5 verdict
  files); the 7 broadcast copies are DROP-DUP.
- **`runtime_truth_spine_v2_*`** (report / evidence_plan / subagent2_verification) is a
  3-file cluster from one 2026-06-01 effort; all MERGE->05 as a single finding family.
- **`anatomy_altitude_2026-06-10/lane_{A..F}.md`** is a 6-lane single audit; MERGE->03 as one family.
- **`LIVE_OPS_DASHBOARD` snapshots** (`_archive/..._2026-05-07`, `_2026-05-11`) are dashboard
  history; ARCHIVE-INDEX only, the live dashboard is KEEP-LIVE.

## EXCLUDE accounting (not repo-defect finders)

Of the 355 finding-bearing candidates, **266** are excluded as not-a-defect-finder
(research, vision, specs, plans, prompts, missions, agent personas, generated probes, and
the pre-pivot strategy corpus). They are accounted for here by bucket so nothing is silently
dropped:

| Bucket | Excluded files |
|--------|---------------:|
| `docs/research` | 37 |
| `docs/reports` | 27 |
| `docs/architecture` | 14 |
| `docs/loomwork` | 14 |
| `docs/archive` | 12 |
| `docs/vision_maps` | 12 |
| `docs/agents` | 9 |
| `docs/telos-engine` | 9 |
| `docs/prompts` | 8 |
| `docs/agent_tasks` | 7 |
| `docs/missions` | 7 |
| `docs/ops` | 7 |
| `inter_agent/devin` | 6 |
| `ROOT` | 5 |
| `docs/_archive` | 4 |
| `docs/docops` | 4 |
| `docs/governance` | 4 |
| `reports/architectural` | 4 |
| `reports/audit` | 4 |
| `docs/dse` | 3 |
| `docs/specs` | 3 |
| `reports/dgc_self_proving_packet_20260313` | 3 |
| `reports/generated` | 3 |
| `specs/research` | 3 |
| `specs/research_living_layers` | 3 |
| `docs/doctrine` | 2 |
| `docs/inside_swarm` | 2 |
| `inter_agent/codex` | 2 |
| `research/economic_value_tracking` | 2 |
| `.agents/skills` | 1 |
| `.github/PULL_REQUEST_TEMPLATE.md` | 1 |
| `.swarm_collab/codex_opus` | 1 |
| `architecture/BLUEPRINTS.md` | 1 |
| `architecture/CYBERNETIC_TRANSCENDENCE_PROTOCOL.md` | 1 |
| `architecture/PRINCIPLES.md` | 1 |
| `dharma_swarm/inter_agent` | 1 |
| `docs/COMPLIANCE_MAPPING.md` | 1 |
| `docs/DHARMA_SWARM_THREE_PLANE_ARCHITECTURE_2026-03-16.md` | 1 |
| `docs/GINKO_ENHANCEMENT_WAVE.md` | 1 |
| `docs/MASTER_RESEARCH_PROMPT_DHARMIC_SINGULARITY.md` | 1 |
| `docs/MEGAFILE_INDEX.md` | 1 |
| `docs/NVIDIA_INFRA_SELF_HEAL.md` | 1 |
| `docs/PRODUCTION_DEPLOYMENT_GUIDE.md` | 1 |
| `docs/bug-corral` | 1 |
| `docs/doctor` | 1 |
| `docs/evidence` | 1 |
| `docs/offers` | 1 |
| `docs/state` | 1 |
| `foundations/ECONOMIC_VISION.md` | 1 |
| `foundations/GLOSSARY.md` | 1 |
| `foundations/PILLAR_02_KAUFFMAN.md` | 1 |
| `foundations/PILLAR_03_JANTSCH.md` | 1 |
| `foundations/PILLAR_05_DEACON.md` | 1 |
| `foundations/PILLAR_06_FRISTON.md` | 1 |
| `foundations/PILLAR_07_HOFSTADTER.md` | 1 |
| `foundations/PILLAR_09_DADA_BHAGWAN.md` | 1 |
| `foundations/PILLAR_11_BEER.md` | 1 |
| `foundations/RESIDUAL_STREAM_DIGEST.md` | 1 |
| `foundations/SAMAYA_PROTOCOL.md` | 1 |
| `foundations/transmissions` | 1 |
| `reports/CRYPTOGRAPHIC_AUDIT_TRAILS_RESEARCH.md` | 1 |
| `reports/dharma_current_state_deep_dive_2026-03-19.md` | 1 |
| `reports/loop_closure` | 1 |
| `reports/specs` | 1 |
| `reports/state` | 1 |
| `reports/verification` | 1 |
| `reports/xray_revenue_packet_20260313` | 1 |
| `specs/DGC_TERMINAL_ARCHITECTURE.md` | 1 |
| `specs/DGC_TERMINAL_ARCHITECTURE_v1.1.md` | 1 |
| `specs/Dharma_Constitution_v0.md` | 1 |
| `specs/Dharma_Corpus_Schema.md` | 1 |
| `specs/GODEL_CLAW_V1_SPEC.md` | 1 |
| `specs/SOVEREIGN_BUILD_PHASE_MASTER_PROMPT_2026-03-19.md` | 1 |
| `specs/SOVEREIGN_BUILD_PHASE_MASTER_SPEC_2026-03-19.md` | 1 |
| `specs/STIGMERGY_11_LAYER_SPEC_2026-03-23.md` | 1 |

Notable borderline excludes the operator may want pulled back in:

- `docs/reports/autonomous_activation_map_v1.md` — Activation map (plan), not a defect finding.
- `docs/reports/autonomous_activation_minimal_metabolic_loop_v1.md` — Activation plan, not a defect finding.
- `docs/reports/autonomous_activation_onboarding_receipt_2026-05-28.md` — Activation onboarding receipt (generated).
- `docs/reports/autonomous_activation_pr_sequence_v1.md` — Activation PR sequence (plan).
- `docs/reports/polyglot_proposal_critical_review_v1.md` — Critical review of a polyglot proposal (design review, borderline).
- `docs/reports/wedge_candidate_slate_v1.md` — Wedge candidate slate (strategy/opportunity, not a repo-defect finding).
- `docs/research/spine-adoption-phase/02_master_spec.md` — Spine-adoption build spec (active_spec, not a finder).
- `docs/research/spine-adoption-phase/03_codex_55_plan.md` — Spine-adoption build plan (working_plan, not a finder).
- `docs/state/NEXT_PHASE_MAP.md` — Forward plan, not a current-defect finding.

## Coverage assertion (no live bug-family missed)

Every OPEN item in `BROKEN_REGISTER.md` and every active track maps to a corral target or a
KEEP-LIVE owner:

| Live broken item / track | Covered by |
|--------------------------|------------|
| BR-003 apply gate closed (self-evolution) | 05 + REALITY_DEBT_LEDGER (self-evolution AMBER) + loop-closure owner |
| BR-004 cron split-brain (repo vs live) | 05 + BROKEN_REGISTER owner |
| BR-005 algedonic stream degenerate | 05 + BROKEN_REGISTER owner |
| BR-009 roadmap contested (3 docs) | 07 + REPO_GOVERNANCE_AUDIT owner |
| BR-010 NAVIGATION.md stale / non-canonical path | 03 + NAVIGATION (KEEP-LIVE) + REPO_GOVERNANCE_AUDIT |
| BR-011 INTERFACE_MISMATCH_MAP self-stale | 01 + INTERFACE_MISMATCH_MAP owner |
| BR-012 CYBERNETIC_LOOP_MAP stale | 06 + CYBERNETIC_LOOP_MAP (KEEP-LIVE) + loop-closure owner |
| BR-013 agent contract fragmented (8+ surfaces) | 01/06 (andon reconciliation + execution-identity audit) |
| BR-014 BHED_GNAN gate always passes | 01 (telos_gates.py:512-513) + vibe_code_audit |
| track: runtime-truth-spine-adoption | 01/05 (CONVERGED_SEAM_AUDIT, spine_v2_*, spine-adoption gap_matrix) |
| track: runtime-truth-nats | 01/05 (andon reconciliation NATS findings) |
| track: runtime-truth-reconciliation | 05 (RECEIPT_AND_VEL_EQUIVALENCE, command-cutover receipts) |
| track: loop-closure | reports/loop_closure (KEEP-LIVE owner) |
| track: orientation-graph | 03 + owners |
| track: composer-holon-spine-longrun | 05 (living_agent_kernel verifier_matrix/final_report) |
| reality-debt: R_V / consciousness / Chetana / Capital-Lab | REALITY_DEBT_LEDGER (KEEP-LIVE owner) |

## SHA-256 (MERGE + DROP-DUP sources)

Verifiable with `cd <repo> && sha256sum <path>`.

```
abbd00999812606cddcb8da7d1cc2f81f44f9c4284e41a471f76da3fb95eacd4  docs/architecture/memory_surfaces_census_v3.md
3ecc6a19d9be33c28dbb3332f0e3ce6f1858246f7df1fd0b853c235213f1c1e4  docs/ops/DHARMA_FORGE_HYDRA_ARCHAEOLOGY_2026-06-11.md
bfbc9240d56155dcd15f895e70db10b64488a2eb70033a0c0cd79efdcad8a51b  docs/reports/CONVERGED_SEAM_AUDIT_RUNTIME_TRUTH_SPINE.md
d7b47de8b62864a6e16909d3e9a58143fc8624f9dab28730d36abd3a2a927349  docs/reports/autonomous_expansion_seed_audit_2026-05-28.md
cff773daba4778f419c67eaa0a0f18a9413208010667fcdf5a45f377ca4058dd  docs/reports/modularity_and_future_proofing_audit_v1.md
6a100dd92c53f4ee9c64d2516e9449620c3a691ee1aa49344d7833a7b52bd37a  docs/reports/proof_artifact_internal_benchmark_inventory_v1.md
8092d6bc4ecfb2e1e2dc142af4b2d2bcaa35560de88807adb73c007eb75350cc  docs/reports/proof_artifact_slate_v1.md
3f7907ef32569478e1a988c184f3edbc807e9d18122e5f78e7621d9facbe3b32  docs/reports/wedge_resurvey_burn_and_substrate_audit_v1.md
59e5e629b281222f240cfdf0594e5b5844b849c13ca63d17e78298a1ebc2397b  docs/research/RECEIPT_AND_VEL_EQUIVALENCE_MATRIX.md
1f33e36e9e6215c08527bddc3804674bbab06ee7e52182ccba76243857e227be  docs/research/palantir-ontology/vocabulary-census/andon/2026-06-01T0628Z-andon-audit-verification.md
b11903ac868ce33ffdbdfb990d787c590cf17d45fed0d64c797d631c9c4fae70  docs/research/palantir-ontology/vocabulary-census/andon/reconciliation.md
971b871b4e2b075cb82b8b053dde3deca727190990d6e2cfe8c02b937f4ea65c  docs/research/palantir-ontology/vocabulary-census/andon/verdicts/devin-D.md
7bb758eb86a578037db35144dd5b7c91d9925f03cae5861880ac8b77a8f12512  docs/research/palantir-ontology/vocabulary-census/andon/verdicts/devin-E.md
f1f3e1e8ce1d880b1875aad25f83daf9d1300ea55700c1c2027c3e8935594c77  docs/research/palantir-ontology/vocabulary-census/andon/verdicts/perplexity-A.md
01cc6870a6b7e9341c0ce36bea55f8618477f9fbc30a9307f7cd333ccba5a52e  docs/research/palantir-ontology/vocabulary-census/andon/verdicts/perplexity-B.md
c09c1215e13686c0b75703002eab829671be65e2c7d4853f1e90e4bfc25f3e52  docs/research/palantir-ontology/vocabulary-census/andon/verdicts/perplexity-C.md
14361c618f1c7c3b645b96629831639faecb54a7dba86c025ea8c495e5c8aad0  docs/research/spine-adoption-phase/01_gap_matrix.md
7723453c79435eafe9090e85041c50c4429f763a315dcd61577d4fd59cb4bc4e  docs/state/CROSS_AGENT_INVENTORY.md
5e552702eda74809412618840dd293dc30e3b5541b572a742c63e551dab39499  docs/state/DASHBOARD_FIDELITY_AUDIT.md
0bc01bf363dc05147702bea3fe22162461f03d46d1adfc9297fea3b576a563e3  inter_agent/claude/inbound/2026-06-01T0628Z-andon-audit-verification.md
cb5dbc0a4ca13c730411da20bf63e4d244bfcbb3fffc6e887e955db57277a7c4  inter_agent/codex/inbound/2026-06-01T0628Z-andon-audit-verification.md
61893e1a59a534e87da6357609a180ab4f584d8fb78269a6f5be373b4ed85cf9  inter_agent/devin/inbound/2026-06-01T0628Z-andon-audit-verification.md
4ae994c988921c690887dfa6d7775690d33b5070f69ef91de859f4c5b51ead03  inter_agent/gpt55/inbound/2026-06-01T0628Z-andon-audit-verification.md
46cae99e7d469ce15e21940d46c5e205a9e962f5a1f77b75e73b08b86800d998  inter_agent/hermes/inbound/2026-06-01T0628Z-andon-audit-verification.md
db010efd90355d7abc11d8281d229b0d698281826f7928c532cf2bf18623d1f6  inter_agent/mike/inbound/2026-06-01T0628Z-andon-audit-verification.md
d6f963bc0f1f9d4e99b434cb6c6081e699f84ddc7bc22237400dc0ee77cd4a49  reports/anatomy_altitude_2026-06-10/lane_A_economic.md
4ac9eb6ddd69307a662b3a39270b4f523e83e0ef3cb32e68a83698695cc9a717  reports/anatomy_altitude_2026-06-10/lane_B_truth.md
f4be42c32fdd5d73eecf20cf91a400766e73617b6fdc16da7152b0b2108ebf1a  reports/anatomy_altitude_2026-06-10/lane_C_evolution.md
8a74de7481a073ce54309e648ce397d26080f978713b9683c6a25ab23c1de37d  reports/anatomy_altitude_2026-06-10/lane_D_spine_canon.md
4d8bfe2e82ad48ec0c3220f98892e93073181cbd171dc7c714469c1ba5ae6c9b  reports/anatomy_altitude_2026-06-10/lane_E_organism_vision.md
4c4b92de30091bcd0c0731df712f4d5d59979fdabc32d37d156975bc408b6e3a  reports/anatomy_altitude_2026-06-10/lane_F_world.md
6c6303678049eedaff6491c548c4e32d121424f335c7a36f61691e64cfbfef12  reports/audits/vibe_code_audit_2026-06-07.md
a6d59bb66d369f768c385acfb40855ad49b60f9fb3415aa0e875ec1106ea5801  reports/dashboard/DASHBOARD_WIRING_AUDIT_2026-03-19.md
03ef67c74341319245c986d7df80f14d12b8f0b2c077779f08df9051b55761ff  reports/governance/GATE1_WITNESSED.md
aa1ed7feaa4ab774eceb55c878a2e72aa371bcd48d3ddbb4b27f0a4e208cc6f3  reports/governance/anti_ai_slop_control_backlog_2026-06-08.md
19eb14194955577986191dede75ac89cbc2d2ee29cc986655d9015e56a884eff  reports/governance/anti_ai_slop_futureproof_deep_dive_2026-06-07.md
e309aef8f232cd907f8da44e50c16076e4d1e523a5a9be64cc6776f1eeda3a4f  reports/governance/execution_identity_lineage_blast_radius_audit.md
b70af30c08b2ee78723c69d71cde196d5391524d7bdd21c904bfb3c57b507b5c  reports/governance/runtime_truth_command_cutover_after_action_2026-06-12.md
6f6a94b56c9a5a1d8030dbca18dabaef8fce983cc3bbafd778fb85ba4c5bc19b  reports/governance/runtime_truth_command_cutover_baseline_2026-06-12.md
2d5eafcdaebdb580966e03fb7c6c8a9689655043a6fe707da5457a9a57895f5b  reports/governance/runtime_truth_spine_v2_evidence_plan.md
e07ca1ec928e86606e5e94072ccc4f41047259928bde9389aae29fed63ef5c54  reports/governance/runtime_truth_spine_v2_report.md
b8a0f52562c1f9d1d2098c0bbb7a5b0d73070979bc3a430a5506f2b3c41274d5  reports/governance/runtime_truth_spine_v2_subagent2_v1_verification.md
c741ef0ebe525a3d4cbff7b70f4778c4aa3d23f8257c4837f08bedb69562a8d5  reports/living_agent_kernel/living-agent-kernel-20260605/final_report.md
7189fc8304fcb735fb0991636c2452a565340eced1eabe156d7271355d3c3825  reports/living_agent_kernel/living-agent-kernel-20260605/semantic_context_receipt.md
fab0e111112be957436c4930bf8b7a82773473f602b6208da75fc4db7da0886b  reports/living_agent_kernel/living-agent-kernel-20260605/verifier_matrix.md
4e1e651d23f7ac9890023ef1ee7d6861ab96849f283c05867baaf3c230bc8189  reports/quality/anti_vibe/20260605-dharma-swarm-anti-vibe-quality-index/handoff.md
df60ca8ec63d6f44923f9778aaa002793ebbda0fe020bbdbf9f1fe66538b935a  reports/worktree_triage_report_2026-06-10.md
14361c618f1c7c3b645b96629831639faecb54a7dba86c025ea8c495e5c8aad0  seams/spine-adoption/01_gap_matrix.md
cde34b7ec39065aaf2b09543c5284f34fb44506ac4ba419841b162da49856276  seams/spine-adoption/02_master_spec.md
a9cda6616cceecdf44dafc25c5f09f74bf0ed1196e96906f8116a2b79d44e8f6  seams/spine-adoption/03_codex_55_plan.md
b99315d9a3b485d8166353c1e902acfc36bab4df52c6a53290b880769e139795  specs/VERIFICATION_COMPLETE.md
c2a5b5acbfeb31a90357ad9a1e31314fcceab65ea273330c4e164ceacb18455c  xray_report.md
```

## Open questions for the operator (gate before Phase B)

1. Confirm decision 1 (point to live ledgers vs copy their contents into the corral).
2. Confirm decision 2 (index already-archived files in place vs delete them).
3. Pull any borderline EXCLUDE (above) back into scope?
4. `07_DOCTRINE.md` carries no merged content (all doctrine is KEEP-LIVE). Keep it as a
   pointer-map, or fold its pointers into `00_INDEX.md` and drop to ~9 files?

---

*Reconstructed scope (the canonical index `/home/user/workspace/finder_files_corral.md`
does not exist on this machine). Grades and the MERGE/KEEP/ARCHIVE/EXCLUDE splits are
judgment calls for operator confirmation at this gate.*
