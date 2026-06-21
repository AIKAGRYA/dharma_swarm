# DGC / Self-Evolution Report — Phase 8

## Result

- Command exit codes: `{'build_protocol_cli_help.txt': 0, 'make_verify_corral_strict.txt': 0, 'make_verify_corral.txt': 0}`.
- `DHARMA_EVOLUTION_SHADOW=1` was set for this phase.
- Candidate sealed/proof files found by name scan: `5` (`sealed_or_proof_candidates.txt`).
- BR-003 excerpt captured in `broken_register_br003_excerpt.txt`.

## Interpretation

- No live apply was attempted; `DHARMA_EVOLUTION_SHADOW=0` was never set.
- `verify-corral` and `verify-corral-strict` outputs are the authority for whether shadow/evolution evidence is currently healthy.
- If no usable sealed packet is present, shadow-apply remains untested rather than claimed healthy.

## BR-003 excerpt

```text
26:> **Re-verification pass executed 2026-06-15 (perplexity-computer, Stage 1 EVIDENCE_ONLY):** the register had drifted 22 days since the 2026-05-24 git touch. All 5 OPEN items below have refreshed `last_verified` dates with a `re-verification 2026-06-15` note. No new BRs opened in this pass. No status flips: behavior on disk is unchanged for BR-003 / BR-004 / BR-005 / BR-013 / BR-014. Anti-Slop note: PROD-issue #521 cites this BR-003 as 'Owner doc' but its own owner doc `docs/governance/PROD_READINESS_TOP10.md` does not exist on any branch — BR-003 is real and tracked here; the PROD-issue is the orphan.
34:### BR-003 — Apply gate present but closed (self-evolution loop)
40:- **root_cause:** Two parallel apply paths share zero import edge. Build Protocol (`tools/build_protocol/`) self-declared shape-only; DarwinEngine `apply_diff_and_test` at `evolution.py:2156` env-locked closed by `DHARMA_EVOLUTION_SHADOW=1` default. `grep "from dharma_swarm.tools.build_protocol"` returns 0 hits inside `dharma_swarm/dharma_swarm/`.
41:- **blast_radius:** Self-evolution trace reported 96 dryruns; direct disk check on 2026-05-07 found 9 current dryrun dirs, 4 `proof_packet.json` files, and 0 `applied` markers. Sediment-to-crystallization mechanism remains absent. Kernel + telos_gates static for 6+ weeks.
42:- **evidence:** `~/.dharma/audit/self_evolution_trace_2026-05-07.md`; `find ~/.dharma/build_protocol/dryruns -mindepth 1 -maxdepth 1 -type d | wc -l` = 9; `find ~/.dharma/build_protocol -name proof_packet.json | wc -l` = 4; vision_maps `05_autopoiesis_evolution.md`.
43:- **status:** PARTIAL — 2026-05-07 partial closure: `tools/build_protocol/cli.py` now exposes `dharma-build shadow-apply <dryrun_root>`, which calls `DarwinEngine.apply_sealed_packet(..., shadow=True)` and archives the proof result without live mutation. Live apply remains intentionally gated. **End-to-end exercise on 2026-05-07 (this commit):** ran `python -m tools.build_protocol.cli shadow-apply ~/.dharma/build_
```

## Raw evidence

- `build_protocol_cli_help.txt`
- `make_verify_corral.txt`
- `make_verify_corral_strict.txt`
- `broken_register_br003_excerpt.txt`
- `sealed_or_proof_candidates.txt`
