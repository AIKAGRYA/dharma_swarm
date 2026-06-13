# Cybernetic Loop Closure — Campaign Retrospective

**Track:** `loop-closure-2026-06` · **Author:** opus_composer (Opus 4.8), build lease 2026-06-13/14
**Independent verifier:** codex_composer (per `OPUS_CODEX_LOOP_CLOSURE_COMPACT_2026-06-13`)
**Branch:** `loop-closure/phase1b-2026-06` (unpushed; draft PR #590)

This is Loop 8's food: what the 13-Loop master prompt *predicted* vs. what the
runtime actually *said*. Written honestly — the delta matters more than the wins.

---

## What the master prompt predicted

1. **0 loops closed; Loop 1 is the trunk; everything starves below it.**
2. **The single gate is "a working LLM provider with a valid API key."** Close
   Loop 1 and "Loops 3, 4, 6, 7, 9, 10, 11 close when fed."
3. **The cascade closes itself once Loop 1 flows.** The map's optimism.

## What reality said

1. **The provider premise was already obsolete.** When the campaign resumed,
   keys were present and Loop 1 had *already* executed real provider-backed
   tasks (1,712 completed `delegation_runs`). The "find one working provider"
   framing was stale — the trunk had fired. The real gaps were elsewhere.

2. **The real provider blocker was visibility, not absence.** `dkeys` only
   tested API keys and was structurally blind to the operator's OAuth/
   subscription providers. Corrected: the live surface is **10 brains / 6
   decorrelation clusters** (ollama-cloud gateway, NVIDIA NIM, openai, codex/
   ChatGPT-Pro, claude_code Max, qwen, gemini, GLM, deepseek, kimi) — not the
   "5 live / 3 clusters" the tool first reported. `dkeys` was patched to see them.

3. **A power-floor was missing entirely.** Routing defaulted to sub-floor
   models (`llama-3.3-70b`, `kimi-k2.5`, `glm-5`) in *three* places —
   `DEFAULT_MODELS`, `router_v1` tier-hints, and `provider_smoke`/`provider_matrix`
   source. Enforced a hard **Kimi-K2.6 floor** across all of them + `MODEL_POWER_FLOOR`
   + a global obey rule. Routing now reaches the ≥K2.6 frontier by construction.

4. **Loop 1's receipt lied about which brain answered.** It recorded the static
   config, not the served provider/model — so under routing/race/fallback the
   receipt mislabeled the model. Fixed: the receipt now carries the
   **actually-served** provider/model (proven with a configured≠served fallback
   case). This is the substrate-honest version of "provider/model truth."

5. **The cascade did NOT close itself.** Honest closure instruments were built
   for all 13 loops (`make orient` LIVE/PARTIAL/NOT-LIVE + a ROUTING TRUTH
   panel). They report the truth: **zero loops complete a full
   sense→interpret→constrain→act→adapt cycle on real data today.** Every
   *adapt* arm starves behind Loop 1's *continuous* flow — which the standing
   daemon does not yet produce.

6. **Loop 3 (Evolution) is degenerate.** 0 of 11,420 archive entries ever had
   `correctness > 0`. The fitness numbers are composites masking a permanently-
   zero correctness term. Loops 12/13 must stay **BLOCKED** behind the One Wire
   quorum (codex owns that guard). Loop 7 (Training) has never run; Loop 11
   (Replication) has 0 successes of 4,437 dispatches.

## The decisive delta

The map said *"close Loop 1 → the cascade follows."* Reality: **Loop 1's
mechanism is closed and proven in-lane (served-truth receipts, frontier
routing, fallback-robust, $0), but production closure is gated on the standing
daemon adopting the patched code.** The daemon runs pre-merge code and buries
each fresh frontier receipt with an empty-model `orchestrator` row within
minutes — so `make orient` reads NOT-LIVE on canonical *despite* the wire being
correct. The cascade's "closes when fed" remains an untested hypothesis,
because the daemon is not yet fed by the patched code.

**The trunk was never the provider. The trunk is the daemon.**

## State at retrospective

| Surface | State |
|---|---|
| Frontier floor (≥K2.6) | Airtight in code (hierarchy + router_v1 + provider_smoke/matrix + obey rule) |
| Served-truth receipts | Done — receipt = actually-served provider/model, fallback-robust |
| `make orient` ROUTING TRUTH + Loop-1 closure check | Done — falsifiable, freshness-gated |
| Continuous frontier proof on canonical | Ran ($0): fill 465→493, 9 frontier brains, 0 sub-floor |
| 13-loop closure instruments | Built; honest LIVE/PARTIAL/NOT-LIVE |
| Suite green for campaign changes | Yes — the 4 tests the floor change touched are fixed; 46 reds are PRE-EXISTING (fail on base `9c76b2106`), not this campaign's |
| orient **durably** LIVE in production | **BLOCKED on operator: merge #590 + daemon restart** |
| Loops 12/13 | Correctly BLOCKED (One Wire quorum, N≥5/M≥3 — not met) |

## The one remaining move (operator)

**Merge #590 + restart the daemon on the patched code.** Then the daemon's own
continuous dispatch routes the ≥K2.6 frontier, writes served-truth receipts,
`make orient` reads LIVE+PASS durably, and the cascade hypothesis becomes
*testable* on real daemon data. Everything upstream of that is done and honest.

*The most trustworthy output of this campaign is not a green checkmark — it is
the instrument that refuses to show green until the daemon actually closes the
loop.*
