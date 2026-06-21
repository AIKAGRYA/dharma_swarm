# Memory Kernel Report — Phase 6

## Result

- Command exit codes: `{'memory_kernel_promotion_smoke.txt': 0, 'memory_kernel_knowledgeops_bridge_smoke.txt': 0, 'operator_prod_smoke.txt': 2, 'memory_kernel_readiness_strict.txt': 2, 'memory_kernel_readiness.txt': 2, 'memory_kernel_burn_in.txt': 2, 'memory_kernel_write_receipt_smoke.txt': 0}`.
- Control surface memory-related rows captured: `13` (`memory_control_surface_rows.json`).

## Interpretation

- `memory-kernel-readiness`, `memory-kernel-readiness-strict`, and `operator-prod-smoke` outputs are the authority for readiness; see raw `.txt` evidence.
- Safe smoke targets were run with `HOME` and `DHARMA_STATE_DIR` pointed at the isolated test root, so any writes should stay under `.e2e_state/full_swarm_test_20260621/`.
- Any non-zero target is treated as degraded/failure evidence, not papered over.

## Raw evidence

- `memory_kernel_readiness.txt`
- `memory_kernel_readiness_strict.txt`
- `operator_prod_smoke.txt`
- `memory_kernel_burn_in.txt`
- `memory_kernel_write_receipt_smoke.txt`
- `memory_kernel_promotion_smoke.txt`
- `memory_kernel_knowledgeops_bridge_smoke.txt`
- `control_surface_rows_after_memory.json`
- `memory_control_surface_rows.json`


## Failure details

- `memory-kernel-readiness`: target emitted readiness payload then make exited non-zero; see `memory_kernel_readiness.txt.tail80.txt`.
- `memory-kernel-readiness-strict`: exited non-zero; see `memory_kernel_readiness_strict.txt.tail80.txt`.
- `operator-prod-smoke`: exited non-zero; see `operator_prod_smoke.txt.tail80.txt`.
- `memory-kernel-burn-in`: exited non-zero; see `memory_kernel_burn_in.txt.tail80.txt`.
- Write-receipt, promotion, and knowledgeops bridge smokes exited 0 under isolated HOME/state.
