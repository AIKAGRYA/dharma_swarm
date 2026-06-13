# 09 Provenance Manifest

The receipt for the bug-corral consolidation. Every in-scope source file with its
size, sha256, git dates, original category, target corral file, and deletion status.

**As of:** 2026-06-13  
**Repo:** `AmitabhainArunachala/dharma_swarm` (local clone `/home/ubuntu/repos/dharma-swarm`)  
**Branch:** `devin/1781340172-bug-corral` off `main` @ `9c76b210`  
**Files in manifest:** 62 (DELETE 40 · KEEP-LIVE 17 · EXCLUDE 5)

> Status legend  
> - **DELETE** — historical finder; merge into the target corral file, then `git rm`.  
> - **KEEP-LIVE** — live, generated, or canonical doctrine. A one-line pointer goes into the
>   corral; the file itself is NOT deleted (extends the prompt 3 live-code contract to live/
>   generated markdown). Listed as KEPT-LIVE-CODE in the success criteria.  
> - **EXCLUDE** — not a problem-finder (build report, external research, product spec, live
>   task board). Proposed out of scope; listed as KEPT-OUT-OF-SCOPE. Awaiting operator confirm.

## Scope reconstruction note

The canonical index `/home/user/workspace/finder_files_corral.md` does not exist on this
machine, so this scope was **reconstructed by enumerating the repo** (operator-approved).
Reconstruction is approximate; the category boundaries and the DELETE/KEEP-LIVE/EXCLUDE
splits are judgment calls that need operator confirmation at this gate.

Enumeration deltas (prompt 8 stop-condition data):

- Content-signal search (severity/verdict/drift/x-ray/census tokens) over `*.md`: **611 files**.
- Filename-token search (audit/xray/census/verif/slop/forensic): **77 files** (18 were one
  timestamped harness-run family, 7 were identical copies of one ANDON message).
- Curated finder-doctrine set after removing run-output bulk and adding token-less finders
  (REALITY_DEBT_LEDGER, BROKEN_REGISTER, INTERFACE_MISMATCH_MAP, hygiene/*, etc.): **60 files**
  (+2 X-Ray JSON artifacts = 62 manifest rows).

The prompt assumed ~80 source files; the honest range here is ~45 (delete-only) to ~90+
(if the borderline reports below are pulled in). **Operator: please confirm the DELETE set,
the KEEP-LIVE set, and whether to add any borderline candidates before Phase B.**

## Manifest

| # | Path | Size B | Git first | Git last | Author/Owner | Cat | Target | Status | Claim |
|---|------|-------:|-----------|----------|--------------|:---:|--------|--------|-------|
| 1 | `docs/archive/VERIFICATION_COMPLETE.md` | 9618 | 2026-04-03 | 2026-04-03 | Dhyana | 1 | 01_TRUTH_VERIFIERS.md | DELETE | TLA+ verification complete for TaskBoardCoordination (2026-03-09), status archival. Near-dup of specs/VERIFICATION_COMPLETE.md. |
| 2 | `docs/reports/CONVERGED_SEAM_AUDIT_RUNTIME_TRUTH_SPINE.md` | 16203 | 2026-05-28 | 2026-05-28 | AmitabhainArunachala (Perplexity+Codex converged) | 1 | 01_TRUTH_VERIFIERS.md | DELETE | Converged seam audit of routing x pool x A2A x provider (2026-05-28): compress around one blessed runtime rail. |
| 3 | `docs/state/DASHBOARD_FIDELITY_AUDIT.md` | 6603 | 2026-06-05 | 2026-06-05 | Devin (architecture review) | 1 | 01_TRUTH_VERIFIERS.md | DELETE | Dashboard data fidelity audit (2026-05-20): provider keys present, remaining env-alias and provider-auth issues. |
| 4 | `reports/dashboard/DASHBOARD_WIRING_AUDIT_2026-03-19.md` | 3573 | 2026-03-23 | 2026-03-23 | AmitabhainArunachala | 1 | 01_TRUTH_VERIFIERS.md | DELETE | Dashboard wiring audit (2026-03-19): backend contract mostly live, Claude lane health-check defect. |
| 5 | `specs/VERIFICATION_COMPLETE.md` | 6388 | 2026-03-09 | 2026-03-09 | John Shrader | 1 | 01_TRUTH_VERIFIERS.md | DELETE | TLA+ verification complete for TaskBoardCoordination (2026-03-09 10:21:30). Near-dup of docs/archive/VERIFICATION_COMPLETE.md. |
| 6 | `reports/audits/vibe_code_audit_2026-06-07.md` | 37119 | 2026-06-07 | 2026-06-07 | Devin (Cognition AI) | 2 | 02_ANTI_SLOP.md | DELETE | Vibe-code audit report (2026-06-07) @ fc2200758c; subordinate to ANTI_SLOP_RULES.md. |
| 7 | `reports/governance/anti_ai_slop_control_backlog_2026-06-08.md` | 16230 | 2026-06-09 | 2026-06-09 | AmitabhainArunachala | 2 | 02_ANTI_SLOP.md | DELETE | Anti-AI-slop control backlog (2026-06-08), local execution backlog, not merged doctrine. |
| 8 | `reports/governance/anti_ai_slop_futureproof_deep_dive_2026-06-07.md` | 26285 | 2026-06-09 | 2026-06-09 | AmitabhainArunachala | 2 | 02_ANTI_SLOP.md | DELETE | Anti-AI-slop future-proofing deep dive (2026-06-07): research/scan packet, not a merge blocker. |
| 9 | `docs/doctor/DOCTOR_10_ROUND_AUDIT_2026-03-16.md` | 9038 | 2026-03-17 | 2026-03-17 | John Shrader | 3 | 03_REPO_XRAY.md | DELETE | Doctor 10-round assurance/merge-safety audit (2026-03-16): hardened scanners to stop false positives. |
| 10 | `docs/reports/20-AGENT-DEEP-AUDIT-2026-03-29.md` | 21920 | 2026-03-29 | 2026-03-29 | John Shrader (20-agent run) | 3 | 03_REPO_XRAY.md | DELETE | 20-agent deep audit synthesis (2026-03-29): system novel but not production-ready, MTBF 4-12h. |
| 11 | `docs/reports/GSTACK_SYSTEM_UPGRADE_AUDIT_2026-03-14.md` | 9908 | 2026-03-15 | 2026-03-15 | John Shrader | 3 | 03_REPO_XRAY.md | DELETE | Audit reviewing garrytan/gstack to extract patterns for DGC/Dharma Swarm (2026-03-14). |
| 12 | `docs/reports/autonomous_expansion_seed_audit_2026-05-28.md` | 46977 | 2026-06-05 | 2026-06-05 | Devin (Roaming) AGT-DEVIN_ROAMING_2987D222 | 3 | 03_REPO_XRAY.md | DELETE | Autonomous expansion seed audit + activation plan (2026-05-28). Dup of inter_agent/devin/outbound/2026-05-28-devin-autonomous-expansion-audit.md. |
| 13 | `docs/reports/modularity_and_future_proofing_audit_v1.md` | 27194 | 2026-06-05 | 2026-06-05 | Devin (external worker) | 3 | 03_REPO_XRAY.md | DELETE | Modularity and future-proofing audit (2026-05-30): substrate vs drift, language is not the problem. |
| 14 | `reports/historical/CONSTITUTIONAL_XRAY_REPORT.md` | 21778 | 2026-04-04 | 2026-04-04 | Claude (Augment Code), committed: Dhyana | 3 | 03_REPO_XRAY.md | DELETE | Constitutional X-Ray report (analysis date 2026-03-27), 6-layer constitutional analysis. |
| 15 | `reports/historical/FULL_REPO_AUDIT_2026-03-28.md` | 16104 | 2026-04-04 | 2026-04-04 | Dhyana | 3 | 03_REPO_XRAY.md | DELETE | Full repository audit post-constitutional-hardening (2026-03-28). Front-matter status RESOLVED. |
| 16 | `reports/historical/xray_report.md` | 8554 | 2026-04-04 | 2026-04-04 | Dhyana (repo_xray.py) | 3 | 03_REPO_XRAY.md | DELETE | Historical repo X-Ray, internally 'Generated 2026-03-14T02:02:51 UTC'. |
| 17 | `reports/xray_revenue_packet_20260313/xray_report.md` | 5231 | 2026-03-14 | 2026-03-14 | John Shrader (repo_xray.py) | 3 | 03_REPO_XRAY.md | DELETE | Repo X-Ray inside revenue packet, 'Generated 2026-03-13T15:07:21 UTC' (446 files). |
| 18 | `xray_report.md` | 6385 | 2026-03-15 | 2026-04-08 | John Shrader (repo_xray.py) | 3 | 03_REPO_XRAY.md | DELETE | Root repo X-Ray, internally 'Generated 2026-04-04T09:23:56 UTC' (1231 files, 417,937 lines). EDGE: stale content vs fresh mtime (see notes). |
| 19 | `reports/xray_revenue_packet_20260313/xray_report.json` | 17095 | 2026-03-14 | 2026-03-14 | repo_xray.py | 3 | 03_REPO_XRAY.md (artifacts/) | DELETE | 17,095-byte machine-readable X-Ray output. Per prompt 6: move to artifacts/, do not inline. |
| 20 | `xray_report.json` | 24720 | 2026-04-08 | 2026-04-08 | repo_xray.py | 3 | 03_REPO_XRAY.md (artifacts/) | DELETE | 24,720-byte machine-readable X-Ray output. Per prompt 6: move to docs/bug-corral/artifacts/, do not inline. |
| 21 | `docs/architecture/memory_surfaces_census_v3.md` | 7229 | 2026-05-23 | 2026-05-23 | Dhyana | 4 | 04_INVENTORIES.md | DELETE | Memory Surfaces Census v3 (2026-05-11): MemoryKernel M0 registry + read-only census of memory-like surfaces. |
| 22 | `docs/reports/proof_artifact_internal_benchmark_inventory_v1.md` | 16977 | 2026-06-05 | 2026-06-05 | Devin / AmitabhainArunachala | 4 | 04_INVENTORIES.md | DELETE | Internal benchmark inventory for proof-artifact pivot (2026-05-30). |
| 23 | `docs/reports/wedge_resurvey_burn_and_substrate_audit_v1.md` | 15095 | 2026-06-05 | 2026-06-05 | AmitabhainArunachala | 4 | 04_INVENTORIES.md | DELETE | Burn audit + monetizable-substrate inventory (2026-05-29): $2k/mo burn is operator-reported not measured. |
| 24 | `docs/state/CROSS_AGENT_INVENTORY.md` | 12128 | 2026-05-24 | 2026-06-01 | John Shrader | 4 | 04_INVENTORIES.md | DELETE | Cross-agent inventory of open strings across 12 Devin sessions (generated 2026-05-21, refreshed 2026-05-29). |
| 25 | `reports/governance/GATE1_WITNESSED.md` | 850 | 2026-06-12 | 2026-06-12 | AmitabhainArunachala (gate1_witness.sh) | 5 | 05_RUNTIME_GROUND_TRUTH.md | DELETE | Operator-witnessed EvidenceReceipt gate-1 receipt (2026-06-11): receipt_count 0->1. |
| 26 | `reports/governance/runtime_truth_command_cutover_after_action_2026-06-12.md` | 7875 | 2026-06-12 | 2026-06-12 | AmitabhainArunachala | 5 | 05_RUNTIME_GROUND_TRUTH.md | DELETE | Runtime Truth command cutover after-action (2026-06-12): enforced existing spine, created no new command spine. |
| 27 | `reports/governance/runtime_truth_command_cutover_baseline_2026-06-12.md` | 2719 | 2026-06-12 | 2026-06-12 | AmitabhainArunachala | 5 | 05_RUNTIME_GROUND_TRUTH.md | DELETE | Runtime Truth command cutover baseline receipt (2026-06-12): 63 dirty files before pass. |
| 28 | `reports/governance/runtime_truth_spine_v2_evidence_plan.md` | 7806 | 2026-06-01 | 2026-06-01 | Dhyana (Tracer/Evidence subagent) | 5 | 05_RUNTIME_GROUND_TRUTH.md | DELETE | Runtime Truth Spine v2 evidence bundle plan (2026-06-01). |
| 29 | `reports/governance/runtime_truth_spine_v2_report.md` | 11531 | 2026-06-01 | 2026-06-01 | Dhyana (Codex) | 5 | 05_RUNTIME_GROUND_TRUTH.md | DELETE | Runtime Truth Spine v2 report (2026-06-01): v1 claim corrected, built from clean worktree. |
| 30 | `reports/governance/runtime_truth_spine_v2_subagent2_v1_verification.md` | 6838 | 2026-06-01 | 2026-06-01 | Dhyana (V1 Verification Agent) | 5 | 05_RUNTIME_GROUND_TRUTH.md | DELETE | Runtime Truth Spine v2 subagent-2 verification (2026-06-01): clean-HEAD v1 claim falsified. |
| 31 | `docs/reports/DGC_FORENSIC_TRUTH_REPORT_2026-03-08.md` | 8115 | 2026-03-09 | 2026-03-09 | John Shrader | 7 | 06_INCIDENTS.md | DELETE | DGC forensic truth report (2026-03-08): DGC real/operational but not full blueprint stack; NVIDIA lanes runtime-blocked. |
| 32 | `inter_agent/devin/inbound/2026-06-01T0628Z-andon-audit-verification.md` | 8155 | 2026-06-05 | 2026-06-05 | perplexity-computer (to devin) | 7 | 06_INCIDENTS.md | DELETE | ANDON RED audit-verification pull (2026-06-01). EDGE: 7 identical copies exist across inter_agent/*/inbound; body is an audit, so merged. |
| 33 | `reports/ecosystem_forensics_audit_2026-03-19.md` | 14291 | 2026-03-23 | 2026-03-23 | AmitabhainArunachala | 7 | 06_INCIDENTS.md | DELETE | Ecosystem forensics audit (2026-03-19): comparison vs OpenClaw/Goose/OpenHands/Letta/LangGraph etc. |
| 34 | `reports/governance/execution_identity_lineage_blast_radius_audit.md` | 41124 | 2026-06-01 | 2026-06-01 | Dhyana | 7 | 06_INCIDENTS.md | DELETE | Execution identity lineage + blast-radius audit (2026-06-01) of codex/runtime-truth-spine-v2 worktree. |
| 35 | `agent_runner_audit.md` | 204 | 2026-04-05 | 2026-05-06 | (stub) | 9 | 08_ARCHIVED_FINDINGS.md | DELETE | 204-byte stub pointing at docs/_archive/2026-04/agent_runner_audit.md. Empty stub, nothing to merge. |
| 36 | `docs/_archive/2026-04/agent_runner_audit.md` | 31606 | 2026-05-06 | 2026-05-06 | Senior DevOps Engineer (committed: Dhyana) | 9 | 08_ARCHIVED_FINDINGS.md | DELETE | Full production-readiness audit of agent_runner.py (3024 lines), dated 2026-04-05. Real content behind the root stub. |
| 37 | `docs/_archive/2026-04/orchestrator_audit.md` | 32745 | 2026-05-06 | 2026-05-06 | Senior DevOps forensic review (committed: Dhyana) | 9 | 08_ARCHIVED_FINDINGS.md | DELETE | Full production-readiness audit of orchestrator.py (2208 lines), dated 2026-04-05. Real content behind the root stub. |
| 38 | `docs/state/_archive/LIVE_OPS_DASHBOARD_2026-05-07.md` | 8372 | 2026-05-11 | 2026-05-11 | Dhyana | 9 | 08_ARCHIVED_FINDINGS.md | DELETE | Archived 2026-05-07 live-ops dashboard snapshot (Slot 6 of MEGAFILE_INDEX). |
| 39 | `docs/state/_archive/LIVE_OPS_DASHBOARD_2026-05-11.md` | 9178 | 2026-06-01 | 2026-06-01 | John Shrader | 9 | 08_ARCHIVED_FINDINGS.md | DELETE | Archived 2026-05-11 live-ops dashboard / morning brief snapshot. |
| 40 | `orchestrator_audit.md` | 204 | 2026-04-05 | 2026-05-06 | (stub) | 9 | 08_ARCHIVED_FINDINGS.md | DELETE | 204-byte stub pointing at docs/_archive/2026-04/orchestrator_audit.md. Empty stub, nothing to merge. |
| 41 | `INTERFACE_MISMATCH_MAP.md` | 15754 | 2026-04-04 | 2026-06-12 | Guardian Crew (guardian_crew.py, auto every 4h) | 1 | 01_TRUTH_VERIFIERS.md | KEEP-LIVE | Auto-maintained interface-mismatch / docs-vs-code map; last X-Ray 2026-05-20. Auto-regenerates, so pointer-only. |
| 42 | `docs/architecture/VERIFICATION_LANE.md` | 3708 | 2026-04-03 | 2026-04-03 | Dhyana | 1 | 01_TRUTH_VERIFIERS.md | KEEP-LIVE | Active read-only verifier doctrine for DGC + dharma swarm (status: active). |
| 43 | `docs/governance/REALITY_DEBT_LEDGER.md` | 3505 | 2026-06-12 | 2026-06-12 | AmitabhainArunachala | 1 | 01_TRUTH_VERIFIERS.md | KEEP-LIVE | Anti-overclaim firewall ledger of high-value claims needing proof. Live append-style ledger (2026-06-12). |
| 44 | `docs/governance/REPO_GOVERNANCE_AUDIT.md` | 34260 | 2026-04-04 | 2026-05-20 | Multi-model (Claude/DeepSeek/GPT-OSS/Codex/RUFLO), committed: Dhyana | 1 | 01_TRUTH_VERIFIERS.md | KEEP-LIVE | CANON per docs/AGENTS.md (owns contradictions/staleness). Multi-model convergent audit (2026-04-04). Live authority, pointer-only. |
| 45 | `docs/governance/ANTI_SLOP_RULES.md` | 11878 | 2026-04-27 | 2026-06-12 | Dhyana | 2 | 02_ANTI_SLOP.md | KEEP-LIVE | Canonical 10 anti-slop rules; backed by .semgrep/dharma-anti-slop.yml + workflows. Live gate doctrine. |
| 46 | `docs/governance/VIBE_CODE_HYGIENE.md` | 25839 | 2026-06-11 | 2026-06-11 | AmitabhainArunachala | 2 | 02_ANTI_SLOP.md | KEEP-LIVE | Canonical vibe-code antipattern catalogue + runnable scan. Live doctrine (2026-06-11). |
| 47 | `docs/docops/AUTO_INVENTORY.md` | 585 | 2026-05-06 | 2026-06-12 | generated: check_docops_integrity.py | 4 | 04_INVENTORIES.md | KEEP-LIVE | Generated repo inventory block (DOCOPS metric). Regenerates from script, so pointer-only. |
| 48 | `reports/governance/active_track_evidence.md` | 10395 | 2026-05-20 | 2026-06-12 | generated: check_track_status.py | 5 | 05_RUNTIME_GROUND_TRUTH.md | KEEP-LIVE | Generated track-portfolio evidence (schema v2). Referenced by CLAUDE.md. Regenerates, pointer-only. |
| 49 | `reports/governance/parallel_lane_map.md` | 9188 | 2026-06-12 | 2026-06-12 | generated (AmitabhainArunachala) | 5 | 05_RUNTIME_GROUND_TRUTH.md | KEEP-LIVE | Generated non-destructive operating snapshot of lanes/branches. Regenerates, pointer-only. |
| 50 | `docs/state/BROKEN_REGISTER.md` | 25713 | 2026-05-07 | 2026-05-24 | Dhyana | 7 | 06_INCIDENTS.md | KEEP-LIVE | Append-only persistent register of broken/stale/degraded surfaces (BR-NNN). Canonical incident ledger, referenced by CLAUDE.md. |
| 51 | `docs/governance/CANONICAL_DOC_STACK.md` | 10064 | 2026-04-04 | 2026-06-12 | Dhyana | 6 | 07_DOCTRINE.md | KEEP-LIVE | Canonical doc-ownership map (which doc owns which truth). Live, referenced by onboarding. |
| 52 | `docs/governance/COHERENCE_DELTA.md` | 12246 | 2026-05-07 | 2026-06-12 | Dhyana | 6 | 07_DOCTRINE.md | KEEP-LIVE | Coherence Delta merge-gate doctrine. Live, referenced by CLAUDE.md pre-flight check. |
| 53 | `docs/governance/hygiene/AI_AGENT_GOVERNANCE.md` | 5498 | 2026-06-09 | 2026-06-09 | AmitabhainArunachala | 6 | 07_DOCTRINE.md | KEEP-LIVE | AI-agent hygiene governance doctrine (advisory tranche). Live. |
| 54 | `docs/governance/hygiene/AUDIT_PROMPT.md` | 18294 | 2026-06-09 | 2026-06-09 | generated: audit_agent_prompt.py | 6 | 07_DOCTRINE.md | KEEP-LIVE | Vibe-code audit prompt, GENERATED from hygiene/patterns/*.yaml. Regenerates, pointer-only. |
| 55 | `docs/governance/hygiene/CATALOGUE.md` | 9617 | 2026-06-09 | 2026-06-09 | generated: make hygiene-check | 6 | 07_DOCTRINE.md | KEEP-LIVE | Hygiene catalogue, GENERATED from hygiene/patterns/*.yaml. Regenerates, pointer-only. |
| 56 | `docs/governance/hygiene/LIFECYCLE.md` | 1294 | 2026-06-09 | 2026-06-09 | AmitabhainArunachala | 6 | 07_DOCTRINE.md | KEEP-LIVE | Hygiene pattern lifecycle doctrine (observed->measured->advisory->enforced->resolved->archived). Live. |
| 57 | `docs/governance/hygiene/README.md` | 2373 | 2026-06-09 | 2026-06-09 | AmitabhainArunachala | 6 | 07_DOCTRINE.md | KEEP-LIVE | Governance hygiene folder doctrine; patterns/*.yaml is source of truth. Live. |
| 58 | `PHASE4_REPORT.md` | 3981 | 2026-04-08 | 2026-04-08 | DHARMA SWARM | - | (n/a — excluded) | EXCLUDE | Phase-4 LanceDB build report (what was built). Build report, not a finder. Propose out of scope. |
| 59 | `docs/state/HOTLIST.md` | 5077 | 2026-05-24 | 2026-06-01 | John Shrader | - | (n/a — excluded) | EXCLUDE | Repo-wide running task board (kanban). Live operational board, not a finder. |
| 60 | `phase2_darwin_diff_report.md` | 3353 | 2026-04-08 | 2026-04-08 | DHARMA SWARM | - | (n/a — excluded) | EXCLUDE | Phase-2 Darwin Engine implementation report. Build report, not a finder. Propose out of scope. |
| 61 | `reports/CRYPTOGRAPHIC_AUDIT_TRAILS_RESEARCH.md` | 34944 | 2026-03-09 | 2026-03-09 | Research Agent | - | (n/a — excluded) | EXCLUDE | Research report on cryptographic audit-trail systems (Sigstore etc). External research, not a repo finder. |
| 62 | `reports/dgc_self_proving_packet_20260313/campaign_xray_spec.md` | 2936 | 2026-03-13 | 2026-03-13 | John Shrader | - | (n/a — excluded) | EXCLUDE | 'Campaign X-Ray' product/offer spec (managed diagnostic). Product spec, not a repo finder. |

## SHA-256 manifest

Verifiable with `cd <repo> && shasum -a 256 <path>` (or `sha256sum`).

```
1fc8f1665b166ea854d8cb0ac5d5b44b96b807f94aee23f7414af6c751d1cf9d  docs/archive/VERIFICATION_COMPLETE.md
bfbc9240d56155dcd15f895e70db10b64488a2eb70033a0c0cd79efdcad8a51b  docs/reports/CONVERGED_SEAM_AUDIT_RUNTIME_TRUTH_SPINE.md
5e552702eda74809412618840dd293dc30e3b5541b572a742c63e551dab39499  docs/state/DASHBOARD_FIDELITY_AUDIT.md
a6d59bb66d369f768c385acfb40855ad49b60f9fb3415aa0e875ec1106ea5801  reports/dashboard/DASHBOARD_WIRING_AUDIT_2026-03-19.md
b99315d9a3b485d8166353c1e902acfc36bab4df52c6a53290b880769e139795  specs/VERIFICATION_COMPLETE.md
6c6303678049eedaff6491c548c4e32d121424f335c7a36f61691e64cfbfef12  reports/audits/vibe_code_audit_2026-06-07.md
aa1ed7feaa4ab774eceb55c878a2e72aa371bcd48d3ddbb4b27f0a4e208cc6f3  reports/governance/anti_ai_slop_control_backlog_2026-06-08.md
19eb14194955577986191dede75ac89cbc2d2ee29cc986655d9015e56a884eff  reports/governance/anti_ai_slop_futureproof_deep_dive_2026-06-07.md
e4fedcf05e5a36f8103d2d8d5db745b5aaa47d892099769d160a07b6a7a23884  docs/doctor/DOCTOR_10_ROUND_AUDIT_2026-03-16.md
28fe8680d71902d3bf66406939c60b0971cc1d9c65bbe847e12b9d03a82f3a42  docs/reports/20-AGENT-DEEP-AUDIT-2026-03-29.md
69599d915ef2cc7a5dbaf2f756b3d7a8a4be124c5ca73da23bca23a95d152618  docs/reports/GSTACK_SYSTEM_UPGRADE_AUDIT_2026-03-14.md
d7b47de8b62864a6e16909d3e9a58143fc8624f9dab28730d36abd3a2a927349  docs/reports/autonomous_expansion_seed_audit_2026-05-28.md
cff773daba4778f419c67eaa0a0f18a9413208010667fcdf5a45f377ca4058dd  docs/reports/modularity_and_future_proofing_audit_v1.md
fe3342fafb6a32d1598ce263ac460e5c36f215778eba6988805375989d773d01  reports/historical/CONSTITUTIONAL_XRAY_REPORT.md
4e02d1c2b2c43adaddc6d910a45efdf63836875d7f3eaf957390f761d24e56c1  reports/historical/FULL_REPO_AUDIT_2026-03-28.md
9776e73ff6cc4c4e77afbfa10ffeb21da893cd60a4b1389056ad587b80522e28  reports/historical/xray_report.md
23b16c48f8168c45a83aeedae3ea4e3304b85169410ef8a0496d73cc4f1c2bf0  reports/xray_revenue_packet_20260313/xray_report.md
c2a5b5acbfeb31a90357ad9a1e31314fcceab65ea273330c4e164ceacb18455c  xray_report.md
dbd0fc54dfbaa9c97a287c4c3ad8491dacd66930826c5fcbed80f7bf1070d5ce  reports/xray_revenue_packet_20260313/xray_report.json
36b9ff262cca667c8e572949ac23383a7139eb34c22b41f582a33945fda07280  xray_report.json
abbd00999812606cddcb8da7d1cc2f81f44f9c4284e41a471f76da3fb95eacd4  docs/architecture/memory_surfaces_census_v3.md
6a100dd92c53f4ee9c64d2516e9449620c3a691ee1aa49344d7833a7b52bd37a  docs/reports/proof_artifact_internal_benchmark_inventory_v1.md
3f7907ef32569478e1a988c184f3edbc807e9d18122e5f78e7621d9facbe3b32  docs/reports/wedge_resurvey_burn_and_substrate_audit_v1.md
7723453c79435eafe9090e85041c50c4429f763a315dcd61577d4fd59cb4bc4e  docs/state/CROSS_AGENT_INVENTORY.md
03ef67c74341319245c986d7df80f14d12b8f0b2c077779f08df9051b55761ff  reports/governance/GATE1_WITNESSED.md
b70af30c08b2ee78723c69d71cde196d5391524d7bdd21c904bfb3c57b507b5c  reports/governance/runtime_truth_command_cutover_after_action_2026-06-12.md
6f6a94b56c9a5a1d8030dbca18dabaef8fce983cc3bbafd778fb85ba4c5bc19b  reports/governance/runtime_truth_command_cutover_baseline_2026-06-12.md
2d5eafcdaebdb580966e03fb7c6c8a9689655043a6fe707da5457a9a57895f5b  reports/governance/runtime_truth_spine_v2_evidence_plan.md
e07ca1ec928e86606e5e94072ccc4f41047259928bde9389aae29fed63ef5c54  reports/governance/runtime_truth_spine_v2_report.md
b8a0f52562c1f9d1d2098c0bbb7a5b0d73070979bc3a430a5506f2b3c41274d5  reports/governance/runtime_truth_spine_v2_subagent2_v1_verification.md
f6f3116a855ed1f3cb9558db5bd3b23288582b69132bdebddcc907ca06ac90d5  docs/reports/DGC_FORENSIC_TRUTH_REPORT_2026-03-08.md
61893e1a59a534e87da6357609a180ab4f584d8fb78269a6f5be373b4ed85cf9  inter_agent/devin/inbound/2026-06-01T0628Z-andon-audit-verification.md
6438480ad0db5c095c0d1626ad4e65728bf9df276e86e886791a0473ad68d5e3  reports/ecosystem_forensics_audit_2026-03-19.md
e309aef8f232cd907f8da44e50c16076e4d1e523a5a9be64cc6776f1eeda3a4f  reports/governance/execution_identity_lineage_blast_radius_audit.md
ee4222f73f0cdf5f87073cb71052e64b4940cab4908690be51bf4888669aa03f  agent_runner_audit.md
ee36c5e63ec00b1ccace63c60fa9af4d1b92236306e03777aa45a4a3a3e7958a  docs/_archive/2026-04/agent_runner_audit.md
83b20d60492bab1a62261a31ad261a5aba99c036815450df09e269ec678dd4e7  docs/_archive/2026-04/orchestrator_audit.md
57927854477b0d3b5e2b8a6dbf07e5064f9d02c413a7f1a1f00b81aa25b40a36  docs/state/_archive/LIVE_OPS_DASHBOARD_2026-05-07.md
f6e72ea01bb898e5cc12631ea95fff46c9c55eb965c5665f02f76785d1e407f8  docs/state/_archive/LIVE_OPS_DASHBOARD_2026-05-11.md
b7209281365a3336483beda72dbb9e8135ddbbbd4d5f57d7649618fee00588db  orchestrator_audit.md
7cbbe319852d4c397deb03c2920fa17f08b943a64e477a7d970d6b85c4a9b7d5  INTERFACE_MISMATCH_MAP.md
18a9d458cdbba32f706972e32ccc621b8e562387fb21922447be56ad9f06178a  docs/architecture/VERIFICATION_LANE.md
63e8c761dd727ca3ce0eb805d5f54bc05f7373c9aa5c1a561ea880384dd5c7c4  docs/governance/REALITY_DEBT_LEDGER.md
f98dad0a05fcaad15164d4b8c1753018d5bc39660b575489ff1213773aa74695  docs/governance/REPO_GOVERNANCE_AUDIT.md
42e6425e91802a9222417a793fbfad3c406f382f6f3839a67b4a589b10f4a042  docs/governance/ANTI_SLOP_RULES.md
30b00171b287d9afbb2bbc9124546ceabf849919e93eb24278af61b641d969b3  docs/governance/VIBE_CODE_HYGIENE.md
c35edcc7bfaef731486dc3f6fb3c335490f82551bdcd4920d347443826f13034  docs/docops/AUTO_INVENTORY.md
c7fa3ae33bfe91dbc4884014e78867216ee12aee35116a4834d7ff181dd19c0d  reports/governance/active_track_evidence.md
edd2ab9cb644a18647a30807a7f9f7b3ee0d972784f27235183365afd1481a66  reports/governance/parallel_lane_map.md
f58a86a9e7b81f8efcd9e956e78e2e5de45af6b0c7264edea595766b587f6c9c  docs/state/BROKEN_REGISTER.md
5e7003c4dbe7ac0af352d5038c99b0cd5a146571e02f6ba919a158aa980d832c  docs/governance/CANONICAL_DOC_STACK.md
6bfc94447c803f7574463cf34b3b7fad883c4279b89003ee6af3d92146781ec9  docs/governance/COHERENCE_DELTA.md
34f02d1824530ae48f1e29b802a90c1c0fdfbd94899d18ea307bf996741cac30  docs/governance/hygiene/AI_AGENT_GOVERNANCE.md
a1cec900551bacc93fcd41df6c4f6aeb0930911b8fdf79b1a875c8cc06c75b2a  docs/governance/hygiene/AUDIT_PROMPT.md
fd28d49551198ac00a934cfcf0a19e1c5c902eec466f60132154c8b4fe645576  docs/governance/hygiene/CATALOGUE.md
112b2b2e93016327a5d07ec000d3428ea21eb5144bc3de687c4125278986982d  docs/governance/hygiene/LIFECYCLE.md
c1cc30fbe6cc8af5f5ae1b7ba96a93f5b684c6591c02777a6d13fde7dccf0f53  docs/governance/hygiene/README.md
780c24b0fa4078a5356c2a9677481edeee67c25f02b6a61b68b3243ceb6bf22d  PHASE4_REPORT.md
510803f62984ed4eb4ad4a4a1b99e422b8d412c6aac5dcb96b7871634ef09761  docs/state/HOTLIST.md
7dafa869a45a497d0d564da44f9775532f080372bb7a039e0c566f38a0ac477f  phase2_darwin_diff_report.md
3ee76fa2d6a158aecac5b2fa9efcfc75b1b15b444e9dd77dba7e14e76783d5b4  reports/CRYPTOGRAPHIC_AUDIT_TRAILS_RESEARCH.md
44392820a3e56f9749e31bdeb40670cf08bab236e8247b3ae14b7eab5a01a5f3  reports/dgc_self_proving_packet_20260313/campaign_xray_spec.md
```

## Empty stubs

- `agent_runner_audit.md` (204 B) and `orchestrator_audit.md` (204 B) at repo root are
  placeholders pointing at the `docs/_archive/2026-04/` full versions. Empty stubs; the
  archived full versions are the real content (rescued into `08_ARCHIVED_FINDINGS.md`).

## Edge cases

- **Stale-mtime X-Ray:** `xray_report.md` is internally 'Generated 2026-04-04' (git last
  2026-04-08). The prompt cited a 2026-06-05 filesystem mtime anomaly; that mtime lived on
  John's Mac. On this fresh clone all filesystem mtimes are clone-time and meaningless, so
  this manifest uses git dates + internal 'Generated' dates instead of `stat` mtime. The
  stale-content meta-finding will still be flagged in `03_REPO_XRAY.md`.
- **X-Ray JSON >5 KB:** `xray_report.json` (24,720 B) and
  `reports/xray_revenue_packet_20260313/xray_report.json` (17,095 B) will be moved to
  `docs/bug-corral/artifacts/` and referenced, not inlined.
- **ANDON duplicates:** `2026-06-01T0628Z-andon-audit-verification.md` exists in 7 inbound
  folders (claude, codex, devin, gpt55, hermes, mike) plus the vocabulary-census andon dir.
  One copy (devin) is in the DELETE set as the canonical; the other copies are acknowledgement
  fan-out and will be logged here, not separately merged.
- **Codex feasibility audit MISSING:** prompt 6 references
  `2026-06-13_codex_feasibility_audit.md`. It is NOT tracked or untracked in this clone
  (likely uncommitted on John's Mac). Cannot merge what is not present — operator input needed.

## Conflicts and scope decisions

- **Near-duplicate TLA+ reports:** `docs/archive/VERIFICATION_COMPLETE.md` and
  `specs/VERIFICATION_COMPLETE.md` are near-identical TaskBoardCoordination verification
  records (2026-03-09). Both kept in the DELETE set; `01_TRUTH_VERIFIERS.md` will carry one
  finding citing both as Sources.
- **autonomous_expansion_seed_audit duplicate:** `docs/reports/autonomous_expansion_seed_audit_2026-05-28.md`
  duplicates `inter_agent/devin/outbound/2026-05-28-devin-autonomous-expansion-audit.md`.
  The docs/reports copy is treated as canonical.
- **Live/generated markdown not deleted:** INTERFACE_MISMATCH_MAP, AUTO_INVENTORY,
  active_track_evidence, parallel_lane_map, hygiene/CATALOGUE, hygiene/AUDIT_PROMPT are
  machine-generated; ANTI_SLOP_RULES, VIBE_CODE_HYGIENE, CANONICAL_DOC_STACK, COHERENCE_DELTA,
  BROKEN_REGISTER, REALITY_DEBT_LEDGER are live canonical doctrine/ledgers referenced by
  CI / CLAUDE.md / onboarding. Deleting them would break generators or canon, so they are
  KEEP-LIVE (pointer only). This is the chief place operator judgment is requested.

## Borderline candidates not included

Excluded as build/strategy/research rather than problem-finders, but defensibly finder-ish:

- `docs/reports/polyglot_proposal_critical_review_v1.md` — critical review of polyglot proposal.
- `docs/reports/PERFORMANCE_WASTE_PROFILE.md` — performance/waste profile.
- `docs/reports/FITNESS_LANDSCAPE_ANALYSIS.md` — fitness landscape analysis.
- `docs/reports/DGC_DUAL_ENGINE_REALITY_MAP_2026-03-13.md`, `docs/reports/DGC_FULL_POWER_GAP_MAP_2026-03-11.md` — reality/gap maps.
- `docs/reports/JIKOKU_BASELINE_FINDINGS.md` — baseline findings.
- `reports/historical/WAVE2_ACCEPTANCE_CHECKLIST.md`, `reports/worktree_triage_report_2026-06-10.md` — acceptance/triage.

