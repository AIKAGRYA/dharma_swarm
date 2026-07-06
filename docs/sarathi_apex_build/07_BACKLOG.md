# 07 — Backlog (what can be safely changed, what must not be touched)

**Custody: VERIFIED 2026-07-06. Gate-ordered; cross-refs `06_PROOF_GATES.md`.**

## Safe to change now (low blast radius, this-goal scope)

- Front-door docs under `docs/sarathi_apex_build/` (this normalization).
- `dharma_swarm/holon_system/` facades — additive, import-only, tested.
- `docs/sarathi_apex_build/HOLON_SYSTEM_CODE_ORGANIZATION.md` — the prose organ map.
- Adding proof-gate receipts as they are earned.

## Next build steps (ordered)

1. **Gate 4 — Fable standing daemon.** Prove one unattended `fable_composer`
   semantic reply with a fresh heartbeat (lease-gated). Owner: wake shell + A2A.
2. **`holon/` fork collapse (138 copies / ~3-4 distinct).** Follow
   `12_LOAD_HOLON_COLLAPSE_PLAN.md`; make `sprawl_guard.py` reach exit 0.
   Owner: consolidation pass on a clean branch off origin/main.
3. **Gate 5-6 — Sarathi runtime surfaces + gateway module.** Create runtime
   surfaces (with repo map entries) and `holon_system/sarathi/gateway.py`.
4. **Gate 7-9 — pulse, brief, overnight durability.** Only then `wake_loop_active`.
5. **Gate 10 — scoreboard.** Receipts-only Hermes-vs-Sarathi comparison.

## Must NOT be touched (constraints)

- Do NOT move runtime state (`~/.dharma/...`) into git (constraint #4).
- Do NOT move source code into `~/.dharma` (constraint #5).
- Do NOT bulk-move hundreds of files in one pass (constraint #6).
- Do NOT revert unrelated in-flight work: `docs/agent_tasks/*`, `specs/naga_ir/`,
  `telos_titanium/`, trust-forge scripts, the 3 modified governance reports
  (constraint #7).
- Do NOT create a parallel orchestrator, model router, task store, A2A bus, or
  receipt spine (constraint #9).
- Do NOT claim Sarathi alive / `wake_loop_active=true` / "beats Hermes" without
  the gate 9 / gate 10 receipts (constraints #1-3).
- Do NOT delete the tracked `holon/` fork casually — it has its own tests; it is
  a deliberate collapse in step 4, not an incidental `rm`.

## Known stale claims to correct when seen

- "reversibility_gate.py is uncommitted" → committed in `f18fe8476`.
- "`@frontier` / `resolve_top_available_at_wake` is unimplemented" → implemented
  in `runtime_provider.resolve_top_available_at_wake()` and wired into
  `holon_bridge.load_holon()`; on 2026-07-06 `load_holon("sarathi")` resolved to
  `ollama/glm-5:cloud` on this machine.
- "`sakana` defaults to `claude_code`" → corrected by modeling `sakana` as an
  explicit external-only provider (`ProviderType.SAKANA`); this stops DGC from
  silently reporting Fugu as a Claude route while still refusing fake local
  Sakana provider instantiation.
- "136 copies" of holon_bridge → current scan 138 copies / ~69 roots, only ~3-4
  distinct contents (mostly worktree mirrors).
- "Sarathi has no code seam to the gate" → `holon_wake_cycle(planned_action=...)`
  seam exists and is tested.
