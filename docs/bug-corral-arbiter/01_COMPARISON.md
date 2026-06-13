### §1.1 — Prompt interpretation

The original prompt asked for a destructive consolidation pass, not a reading list. Its core target was exactly ten files under `docs/bug-corral/`, with `09_PROVENANCE.md` written first and `00_INDEX.md` written last (`00_ORIGINAL_PROMPT.md:53-69`, VERIFIED). It required every distinct finding to survive while repetition, narration, redundant context, and dead cross-references are removed (`00_ORIGINAL_PROMPT.md:16-18`, VERIFIED). It also required live Python, JSON, CI, and imported tooling to stay in place with pointer entries only (`00_ORIGINAL_PROMPT.md:73-91`, VERIFIED).

The literal hard rules are at `00_ORIGINAL_PROMPT.md:197-206` (VERIFIED): no information loss, no fabrication, no relocation of live code, no Category 8 plans, no emoji or forbidden wording, no silent assumptions, no batching for approval, preserve file:line citations, preserve dates and authors, and mark superseded branch/worktree context. The prompt also pre-decided root audit stubs, stale `xray_report.md`, machine-readable artifacts larger than 5 KB, inter-agent inbox evidence, and the Telos AI feasibility audit (`00_ORIGINAL_PROMPT.md:210-217`, VERIFIED).

The key ambiguity is the tension between the original zero-loss language and the operator's later tightening to signal quality over document preservation. Agent A explicitly re-scoped the job around "only what is still useful for understanding what is broken, risky, inconsistent, incomplete, or uncertain today" (`A_devin_09_PROVENANCE.md:3-6`, UNVERIFIED as operator intent but verified as A text). Agent B stayed closer to the first prompt text by marking 90 files as pending delete and preserving large verbatim sections (`B_perplexity_09_PROVENANCE.md:3-8`, VERIFIED; `B_perplexity_01_TRUTH_VERIFIERS.md:21-43`, VERIFIED). Given the operator's mid-task tightening, Agent A's interpretation is more faithful: the final corral should be a current operator map, not a compressed archive of every finder document.

### §1.2 — Manifest comparison

Agent A reports a whole-repo scan: 1,012 tracked Markdown files were scored by finder-function and finding tokens, yielding 355 finding-bearing candidates, split into 202 current-era and 153 older files (`A_devin_09_PROVENANCE.md:15-22`, VERIFIED as A text). Current `origin/main` has 1,011 tracked Markdown files, while the arbiter packet branch has 1,018; A's count is therefore plausible for its exact branch/time but not exactly reproducible on current `origin/main` without A's lost scratch scorer. A's action model is MERGE 41, KEEP-LIVE 25, ARCHIVE-INDEX 30, DROP-DUP 11, EXCLUDE 266 (`A_devin_09_PROVENANCE.md:8-11`, VERIFIED). A does not publish a total-byte rollup for the full 355; it lists hashes for MERGE and DROP-DUP sources (`A_devin_09_PROVENANCE.md:373-428`, VERIFIED).

Agent B reports 90 audited source files and 1,493,478 total bytes (`B_perplexity_09_PROVENANCE.md:3-6`, VERIFIED). B's target counts are 11 truth verifiers, 6 anti-slop files, 14 repo x-rays, 15 inventories, 8 doctrine files, 31 incident files, and 5 archived findings (`B_perplexity_09_PROVENANCE.md:18-28`, VERIFIED). B is primarily a finder-index manifest, not a whole-repo scan. Its dispositions are mostly PENDING-DELETE, with out-of-scope and live-code lists separated later (`B_perplexity_09_PROVENANCE.md:10-16`, VERIFIED).

Live BR coverage favors A structurally but A overstates liveness. Current `BROKEN_REGISTER.md` says BR-003, BR-004, BR-005, BR-013, and BR-014 remain open or partial (`docs/state/BROKEN_REGISTER.md:30-61`, `:107-127`, VERIFIED). BR-009 through BR-012 are marked fixed in their own rows (`docs/state/BROKEN_REGISTER.md:63-105`, VERIFIED). A maps BR-003 through BR-014 to targets, but labels BR-009 through BR-012 under "Every OPEN item" even though current main marks them fixed (`A_devin_09_PROVENANCE.md:349-364`, VERIFIED as A text; repo status contradicts it). B does not provide an equivalent BR coverage table.

De-duplication strongly favors A. A collapses the seven-copy andon fan-out into `andon/reconciliation.md`, drops the byte-identical `seams/spine-adoption/` triplet against `docs/research/spine-adoption-phase/`, and marks `specs/VERIFICATION_COMPLETE.md` as a near-duplicate of `docs/archive/VERIFICATION_COMPLETE.md` (`A_devin_09_PROVENANCE.md:220-244`, VERIFIED). B notices the six inter-agent andon copies but leaves them PENDING-DELETE in separate target categories (`B_perplexity_09_PROVENANCE.md:91`, `:125-132`, `:260-266`, VERIFIED). B does not list the seams duplicate triplet or the `VERIFICATION_COMPLETE.md` near-duplicate.

The manifest overlap is 44 paths. A has 38 content/delete paths not present in B. B has 46 pending-delete paths not present in A. Several B-only rows are real files, but some are unsafe scope choices: B marks `docs/docops/AUTO_INVENTORY.md`, `docs/governance/ANTI_SLOP_RULES.md`, `docs/governance/REPO_GOVERNANCE_AUDIT.md`, `docs/governance/hygiene/AUDIT_PROMPT.md`, and `docs/governance/hygiene/AI_AGENT_GOVERNANCE.md` as PENDING-DELETE even though A correctly treats comparable live/generated/canon surfaces as pointer-only (`A_devin_09_PROVENANCE.md:46-60`, `:152-180`, VERIFIED; `B_perplexity_09_PROVENANCE.md:52`, `:64`, `:84`, `:103-104`, VERIFIED). B also marks JSON machine artifacts for deletion instead of artifact relocation or pointer handling.

Only in A, with current `origin/main` evidence:

| Path | Evidence |
|---|---|
| `docs/archive/PALANTIR_ONTOLOGY_GAP_ANALYSIS.md` | exists, 31462 bytes, sha `4d3ec811e5e1` |
| `docs/archive/VERIFICATION_COMPLETE.md` | exists, 9618 bytes, sha `1fc8f1665b16` |
| `docs/ops/DHARMA_FORGE_HYDRA_ARCHAEOLOGY_2026-06-11.md` | exists, 19696 bytes, sha `3ecc6a19d9be` |
| `docs/reports/DGC_FULL_POWER_GAP_MAP_2026-03-11.md` | exists, 7574 bytes, sha `42264a7c26cc` |
| `docs/reports/FITNESS_LANDSCAPE_ANALYSIS.md` | exists, 18576 bytes, sha `a4643bed6724` |
| `docs/reports/proof_artifact_slate_v1.md` | exists, 21359 bytes, sha `8092d6bc4ecf` |
| `docs/research/RECEIPT_AND_VEL_EQUIVALENCE_MATRIX.md` | exists, 36892 bytes, sha `59e5e629b281` |
| `docs/research/palantir-ontology/vocabulary-census/andon/reconciliation.md` | exists, 11855 bytes, sha `b11903ac868c` |
| `docs/research/palantir-ontology/vocabulary-census/andon/verdicts/devin-D.md` | exists, 5926 bytes, sha `971b871b4e2b` |
| `docs/research/palantir-ontology/vocabulary-census/andon/verdicts/devin-E.md` | exists, 5799 bytes, sha `7bb758eb86a5` |
| `docs/research/palantir-ontology/vocabulary-census/andon/verdicts/perplexity-A.md` | exists, 17717 bytes, sha `f1f3e1e8ce1d` |
| `docs/research/palantir-ontology/vocabulary-census/andon/verdicts/perplexity-B.md` | exists, 14546 bytes, sha `01cc6870a6b7` |
| `docs/research/palantir-ontology/vocabulary-census/andon/verdicts/perplexity-C.md` | exists, 15998 bytes, sha `c09c1215e136` |
| `docs/research/spine-adoption-phase/01_gap_matrix.md` | exists, 19723 bytes, sha `14361c618f1c` |
| `docs/state/_archive/LIVE_OPS_DASHBOARD_2026-05-07.md` | exists, 8372 bytes, sha `57927854477b` |
| `reports/anatomy_altitude_2026-06-10/lane_A_economic.md` | exists, 22355 bytes, sha `d6f963bc0f1f` |
| `reports/anatomy_altitude_2026-06-10/lane_C_evolution.md` | exists, 20473 bytes, sha `f4be42c32fdd` |
| `reports/anatomy_altitude_2026-06-10/lane_D_spine_canon.md` | exists, 22907 bytes, sha `8a74de7481a0` |
| `reports/anatomy_altitude_2026-06-10/lane_E_organism_vision.md` | exists, 29323 bytes, sha `4d8bfe2e82ad` |
| `reports/anatomy_altitude_2026-06-10/lane_F_world.md` | exists, 32615 bytes, sha `4c4b92de3009` |
| `reports/audit/000_MASTER_COHERENCE_SYNTHESIS.md` | missing on current `origin/main` |
| `reports/audit/05_SLICE1_REVIEW.md` | missing on current `origin/main` |
| `reports/audit/07_SLICE2_REVIEW.md` | missing on current `origin/main` |
| `reports/audit/09_SLICE3_LEDGER_WATCHER_RESULT.md` | missing on current `origin/main` |
| `reports/governance/GATE1_WITNESSED.md` | exists, 850 bytes, sha `03ef67c74341` |
| `reports/historical/CONSTITUTIONAL_HARDENING_SPRINT_REPORT.md` | exists, 12962 bytes, sha `679f79f353f6` |
| `reports/historical/DUAL_SPRINT_COMPLETION_REPORT.md` | exists, 18681 bytes, sha `0dadffd3d777` |
| `reports/historical/GODEL_CLAW_V1_REPORT.md` | exists, 28174 bytes, sha `3bf3df7e347f` |
| `reports/historical/PHASE3_COMPLETION_REPORT.md` | exists, 27925 bytes, sha `7b1a1bf6ec74` |
| `reports/living_agent_kernel/living-agent-kernel-20260605/final_report.md` | exists, 44636 bytes, sha `c741ef0ebe52` |
| `reports/living_agent_kernel/living-agent-kernel-20260605/semantic_context_receipt.md` | exists, 20363 bytes, sha `7189fc8304fc` |
| `reports/ops/PRECOMMIT_HOTFIX_RESULT.md` | exists, 2947 bytes, sha `14a2eee2d821` |
| `reports/quality/anti_vibe/20260605-dharma-swarm-anti-vibe-quality-index/handoff.md` | exists, 3418 bytes, sha `4e1e651d23f7` |
| `reports/worktree_triage_report_2026-06-10.md` | exists, 20448 bytes, sha `df60ca8ec63d` |
| `seams/spine-adoption/01_gap_matrix.md` | exists, 19723 bytes, sha `14361c618f1c` |
| `seams/spine-adoption/02_master_spec.md` | exists, 21086 bytes, sha `cde34b7ec390` |
| `seams/spine-adoption/03_codex_55_plan.md` | exists, 28369 bytes, sha `a9cda6616cce` |
| `specs/VERIFICATION_COMPLETE.md` | exists, 6388 bytes, sha `b99315d9a3b4` |

Only in B, with B manifest evidence and current `origin/main` status:

| Path | Evidence |
|---|---|
| `.dharma/shared/cartographer_notes.md` | B says 2183 bytes, sha `7cfcf0876d40`, PENDING-DELETE; missing on current `origin/main` |
| `AUDIT_2026-05-07.md` | B says 28399 bytes, sha `9f2d08a980d0`, PENDING-DELETE; missing on current `origin/main` |
| `GUARDIAN_REPORT.md` | B says 2105 bytes, sha `36608d61c836`, PENDING-DELETE; missing on current `origin/main` |
| `PHASE4_REPORT.md` | exists, 3981 bytes, sha `780c24b0fa40` |
| `docs/_archive/2026-04/AGENT_IDENTITY_UNIFICATION.md` | exists, 38073 bytes, sha `12b186bf2e81` |
| `docs/architecture/memory_kernel_m4a_shadow_report_sweep.md` | exists, 2037 bytes, sha `2464ff0877ac` |
| `docs/docops/AUTO_INVENTORY.md` | exists, 585 bytes, current sha `c35edcc7bfae`; B manifest sha `3c4e8a19961d` is stale |
| `docs/governance/ANTI_SLOP_RULES.md` | exists, 11878 bytes, sha `42e6425e9180` |
| `docs/governance/REPO_GOVERNANCE_AUDIT.md` | exists, 34260 bytes, sha `f98dad0a05fc` |
| `docs/governance/RUNTIME_TRUTH_COMMAND_CUTOVER.md` | exists, 9273 bytes, sha `d640298c1806` |
| `docs/governance/hygiene/AI_AGENT_GOVERNANCE.md` | exists, 5498 bytes, sha `34f02d182453` |
| `docs/governance/hygiene/AUDIT_PROMPT.md` | exists, 18294 bytes, sha `a1cec900551b` |
| `docs/loomwork/vision/06_partner_governance_funding.md` | exists, 41949 bytes, sha `1a98cd6b9380` |
| `docs/offers/agentic-code-governance-sprint.md` | exists, 5446 bytes, sha `b7217c7f25ed` |
| `docs/prompts/DEEP_REPO_CARTOGRAPHER_PROMPT_2026-03-31.md` | exists, 8742 bytes, sha `49688e704ac3` |
| `docs/reports/DGC_TO_DHARMA_SWARM_SCOUT_REPORT_2026-03-09.md` | exists, 29158 bytes, sha `2505170faca0` |
| `docs/reports/JIKOKU_BASELINE_FINDINGS.md` | exists, 7180 bytes, sha `387763c5e35b` |
| `docs/reports/JIKOKU_FINAL_REPORT.md` | exists, 13532 bytes, sha `311193fd05d3` |
| `docs/reports/PLANETARY_RECIPROCITY_COMMONS_GOVERNANCE_CHARTER_2026-03-11.md` | exists, 4201 bytes, sha `88ab50fcebb2` |
| `docs/research/RUNTIME_TRUTH_SPINE_COMPLETION_PLAN.md` | exists, 22871 bytes, sha `e931d82f0620` |
| `docs/research/palantir-ontology/auto-grounded/2026-06-01-0823-pr418-devin-andon-verdicts-D-E.md` | exists, 23674 bytes, sha `8dc38699e939` |
| `docs/research/palantir-ontology/auto-grounded/2026-06-01-1400-pr406-runtime-governance-telos-gate.md` | exists, 9194 bytes, sha `083b29d92cf8` |
| `docs/research/palantir-ontology/auto-grounded/2026-06-01-2301-pr-431-kaizen-runtime-truth-refs.md` | exists, 10725 bytes, sha `9c92fc24bf72` |
| `docs/research/palantir-ontology/auto-grounded/2026-06-02-0001-pr-433-andon-verdicts-state-ownership-a2a-collision.md` | exists, 10188 bytes, sha `a325a2e538d4` |
| `docs/research/palantir-ontology/vocabulary-census/passes/1b-code-reality-map.md` | exists, 43887 bytes, sha `68f0cb7f0761` |
| `docs/research/palantir-ontology/vocabulary-census/passes/3a-governance-external-research.md` | exists, 53162 bytes, sha `6d0006250bf4` |
| `docs/research/palantir-ontology/vocabulary-census/passes/3b-governance-code-walk.md` | exists, 27920 bytes, sha `76232e1cfc28` |
| `docs/research/telos_ai/2026-06-13_codex_feasibility_audit.md` | B says 29141 bytes, sha `9bedf33ab46e`, PENDING-DELETE; missing on current `origin/main` |
| `docs/sovereign_holons/READINESS_VERDICT.md` | exists, 5066 bytes, sha `74002c163b5d` |
| `docs/sovereign_holons/STATE_OF_TRUTH.md` | exists, 6583 bytes, sha `0d1ce4397004` |
| `docs/telos-engine/07_VSM_GOVERNANCE.md` | exists, 51176 bytes, sha `f62771ff7bb5` |
| `inter_agent/devin/outbound/2026-05-25_devin_11_step_chain_verdict.md` | exists, 5029 bytes, sha `bf36fc8e6a66` |
| `inter_agent/devin/outbound/2026-05-28-devin-autonomous-expansion-audit.md` | exists, 4752 bytes, sha `69197149d162` |
| `inter_agent/devin/outbound/2026-06-11T01-50Z-phantom-acker-resolution-and-janitor-ack.md` | exists, 2589 bytes, sha `a657a2cce57e` |
| `phase2_darwin_diff_report.md` | exists, 3353 bytes, sha `7dafa869a45a` |
| `reports/CRYPTOGRAPHIC_AUDIT_TRAILS_RESEARCH.md` | exists, 34944 bytes, sha `3ee76fa2d6a1` |
| `reports/dgc_self_proving_packet_20260313/campaign_xray_spec.md` | exists, 2936 bytes, sha `44392820a3e5` |
| `reports/docops/corpus_inventory.json` | B says 127385 bytes, sha `4810889c4794`, PENDING-DELETE; missing on current `origin/main` |
| `reports/docops/corpus_inventory.md` | B says 29156 bytes, sha `d6ba5ae9ff37`, PENDING-DELETE; missing on current `origin/main` |
| `reports/governance/anti_ai_slop_scan_snapshot_2026-06-08.json` | exists, 6076 bytes, sha `e9c5e4729439` |
| `reports/handoffs/PHANTOM_ACKER_FINDINGS_2026-06-11.md` | exists, 3749 bytes, sha `6d53f41e8b5c` |
| `reports/swarm_genome/2026-06-11/agent_4_governance_operating_canon.md` | exists, 7184 bytes, sha `59587c460678` |
| `reports/xray_revenue_packet_20260313/xray_report.json` | exists, 17095 bytes, sha `dbd0fc54dfba` |
| `reports/xray_revenue_packet_20260313/xray_report.md` | exists, 5231 bytes, sha `23b16c48f816` |
| `spec-forge/self-evolving-organism/ANTI_SLOP_REPORT.json` | exists, 4272 bytes, sha `673422e0809f` |
| `xray_report.json` | exists, 24720 bytes, sha `36b9ff262cca` |

### §1.3 — File-01 comparison

A's file-01 is the right shape for the operator: 230 lines, 10 normalized findings, severities, statuses, dates, and live-owner pointers (`A_devin_01_TRUTH_VERIFIERS.md:1-25`, VERIFIED). It carries 39 distinct file:line citations and 7 OPEN findings plus one IN PROGRESS finding. B's file-01 is 3,341 lines, 19 source sections, and about 240 distinct file:line citations, but it is mostly a verbatim preservation bundle. B's own index admits it merged 19 files and then begins source-section dumps (`B_perplexity_01_TRUTH_VERIFIERS.md:1-58`, VERIFIED). B is useful as raw evidence; it is not a usable phone-readable bug corral front door.

Faithfulness checks against current `origin/main`:

| Claim | Repo check |
|---|---|
| `dharma_swarm/ontology.py:594-639` for `execute_action` | UNVERIFIED as cited and contradicted by current main. Those lines now cover `get_object`, `get_objects_by_type`, `update_object`, and `put_object`, not `execute_action`. Current `execute_action` is at `dharma_swarm/ontology.py:774-977` and applies declared updates through `update_object` at `:934-957`, then records success at `:958-977` (VERIFIED). A's TV-01 is stale or wrong against current main. |
| `dharma_swarm/checkpoint.py:97-106` default `auto_approve=True` | VERIFIED false on current main. `auto_approve` defaults to `False` at `checkpoint.py:98-106`; `interrupt()` approves without a callback only if `_auto_approve` is true, otherwise rejects at `checkpoint.py:115-127`. `cascade.py:36` still instantiates `InterruptGate()` (VERIFIED). A's auto-approve detail is stale; the remaining issue, if any, is missing handler behavior, not default approval. |
| `dharma_swarm/cascade.py:36` singleton | VERIFIED. `_interrupt_gate = InterruptGate()` exists at `cascade.py:36`. |
| `dharma_swarm/runtime_state.py:352` `TaskClaim.claim_id` | VERIFIED false as cited. Current `runtime_state.py:352` is inside `SELF_MOD_RECEIPT_TYPES`; `TaskClaim` is at `runtime_state.py:495-506`, with `claim_id` at `:496`. A's identity-sprawl finding may remain real, but this line citation drifted. |
| `dharma_swarm/a2a/a2a_server.py:213` `trace_id` | VERIFIED false as cited. Current `a2a_server.py:213` is `to_agent`; `trace_id` is at `a2a_server.py:224`. A's envelope finding may remain real, but this line citation drifted. |

The hallucination check mostly supports A's TV-10. `correlation_key` does not appear in current `origin/main` Python, JSON, YAML, or YML files (VERIFIED). No Python `SpecEnvelope` or class matching a spec-envelope artifact appears on current main (VERIFIED). No tracked `nats_a2a_bridge.py`, `a2a_nats_contact.py`, `a2a_durable_projection.py`, or `a2a_stale_claim_reaper.py` exists on current main (VERIFIED). There are doc and census references to `nats_a2a_bridge.py`, including `docs/agent_tasks/claude_guidance_perplexity_computer_2026-05-31.md:11`, `reports/handoffs/A2A_HUB_REPAIRS_2026-06-11.md:205`, and `scripts/runtime/live_ops_census.py:96` (VERIFIED), but no actual module. A is right that the upstream audit named artifacts not present as committed code. A is wrong to leave current-main-stale TV-01, TV-02, TV-03 wording uncorrected.

Distinct findings present in B but absent from A's file-01 are mostly scope, not format: runtime command cutover baseline/after-action, Lane B truth fabric, sovereign holon state/readiness, runtime-truth completion plan, and DGC forensic truth report. Several of those belong in `05_RUNTIME_GROUND_TRUTH.md`, `03_REPO_XRAY.md`, `06_INCIDENTS.md`, or `08_ARCHIVED_FINDINGS.md`, not necessarily in file-01. B's file-01 should be mined for missing scope, not merged as the truth-verifier file.

### §1.4 — Verdict

Agent A's interpretation matches the operator's tightened intent, and A's manifest is the better Phase B through E scope contract because it distinguishes MERGE, KEEP-LIVE, ARCHIVE-INDEX, DROP-DUP, and EXCLUDE while B marks live canon, generated inventories, JSON artifacts, duplicate fan-out, and doctrine as pending delete. Agent B contributes useful extra candidates, especially `docs/sovereign_holons/STATE_OF_TRUTH.md`, `docs/sovereign_holons/READINESS_VERDICT.md`, `reports/handoffs/PHANTOM_ACKER_FINDINGS_2026-06-11.md`, and `docs/research/telos_ai/2026-06-13_codex_feasibility_audit.md`, but B's manifest is unsafe as a delete plan. Do not merge A's `01_TRUTH_VERIFIERS.md` unchanged: its format should win, but TV-01, TV-02, TV-03 and several line citations must be corrected against current `main` before PR #592 is approved to continue.
