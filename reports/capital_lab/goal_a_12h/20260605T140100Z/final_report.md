# Dharma Capital Lab Goal A Alpha Evidence Membrane

- mission_id: 20260605T140100Z-dharma-capital-lab-goal-a-alpha-evidence-12h
- harness_run_id: dharma-capital-lab-goal-a-alpha-evidence-12h-20260605T140100Z
- run_id: 20260605T140100Z
- final_status: alpha_evidence_partial_clean_false
- score: 41.73
- clean: false
- live_readiness: 0
- live_authority: false
- capital_return_claim: false
- broker_write_authority: false

## Authority Boundary

- evidence-only packet generation
- no broker writes, transfers, withdrawals, or order payload signing
- no secret values read or recorded
- prior route, dashboard, cache, and paper evidence remains input-only

## Artifact Hashes

- alpha_evidence_scorecard.json: 38038e9af82ebf9af65b07e6186b68c8cb399eaf7056124259d699a5fb695f45
- alpha_graveyard_packet.json: 118f6b7a02c34f5dfb659de3c6f27a00192e5c19b0ae90138debec3a1eb29296
- data_lineage_packet.json: 3c8edb82810e6ec61d31f42508b7562f0dedb82be3af9610633f5a93972b2269
- independent_evaluator_receipt.json: 0732e5fbe669e6694bdda6eb54ad562f2c976cfc8c0a2ed9ac6a2b8e47ce97ec
- leakage_gauntlet_receipt.json: 32435acc9aadd946468910672d67ebb511d0437296ee597dfdfeb3aabd6a2871
- provider_readiness_packet.json: c06ee14ff3681d199cdfd82f036208e3487b7123bfa309be3f173c8373e0681b
- strategy_evidence_packet.json: ad2c3d3e7f07228d3fc14fcd4414daf900a45dadf178f5a749b5f17c1bb9357e
- walk_forward_oos_receipt.json: b64b1b35da1927503d24ad10a1a27a0318b45300aa72491d4d999215c015753a

## Score Caps

- provider_or_data_lineage_gate_not_clean: cap=79.0
- leakage_gauntlet_not_clean: cap=79.0
- walk_forward_oos_not_clean: cap=78.0

## Blockers

- no_promotion_grade_provider
- provider_gate_failed:point_in_time_safe
- provider_gate_failed:corporate_actions_available
- provider_gate_failed:delisted_symbols_available
- provider_gate_failed:license_ref_present
- provider_gate_failed:raw_payload_hashes_present
- provider_gate_failed:normalized_dataset_hash_present
- provider_gate_failed:feature_availability_timestamps_present
- provider_gate_failed:promotion_grade
- no_clean_lineage_receipt
- lineage_requires_license_raw_hash_normalized_hash_calendar_corporate_actions_delisting_feature_timestamps
- gate_failed:provider_clean
- gate_failed:promotion_grade_provider
- gate_failed:point_in_time_lineage
- gate_failed:feature_availability_timestamps
- gate_failed:frozen_universe
- gate_failed:walk_forward_oos
- gate_failed:final_holdout_touched_once
- gate_failed:baselines_complete
- gate_failed:cost_model_complete
- gate_failed:capacity_check
- gate_failed:correlation_check
- gate_failed:leakage_gauntlet_passed
- gate_failed:model_council_review
- gate_failed:quant_gates_review

## Next Actions

- Attach promotion-grade point-in-time provider receipts with license, raw hashes, normalized hashes, corporate actions, delisting coverage, and feature timestamps.
- Run the leakage gauntlet on frozen historical data before scoring a clean strategy packet.
- Execute walk-forward OOS with baselines, costs, capacity, correlation, and one-use final holdout receipts.
