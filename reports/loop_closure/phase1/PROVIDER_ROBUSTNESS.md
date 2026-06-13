# Provider Robustness Receipt — Phase 1

**Track:** `loop-closure-2026-06` (Cybernetic Loop Closure)
**Phase:** 1 — Loop 1 (provider chain + dispatch) robustness across the model-routing hierarchy
**Lane:** `/Users/dhyana/ds_loop_closure` (branch `loop-closure/phase1b-2026-06`)
**Date:** 2026-06-13
**Author:** fable_composer (Opus 4.8)
**Script:** [`prove_served_receipt_multiprovider.py`](../../../prove_served_receipt_multiprovider.py)
**Receipt store (lane-local):** `_proof_state/served_receipt_proof.db` → `delegation_runs.receipt_json`
**Total cost:** $0 (free providers only)

---

## VERDICT: ROBUST — 5 of 5 served-receipt proofs passed + fallback proven

Loop 1's receipt now carries the **actually-served provider/model truth**, not a
config-assertion. Five real network dispatches each produced a receipt whose
`provider` and `model` match the brain that *actually served the response*
(`runner._last_served_*` ← `response.provider` / `response.model`), with
`latency_ms > 0` and a non-empty result. A sixth dispatch proved the
configured≠served fallback case: the receipt names the **served** provider, not
the configured-dead one.

This is served-provider truth across the model-routing hierarchy: every receipt
below was written by the **real** path — `runtime_provider.resolve_runtime_provider_config`
→ `create_runtime_provider` (THE ONE WAY), then `Orchestrator._run_task_via_spine`
with `DHARMA_SPINE_DISPATCH=1` (the REAL spine), persisted to and read back from
the lane DB.

**Providers passed: 5 / 5. Fallback proven: YES.**

---

## Per-provider served-receipt table

All 5 dispatched through THE ONE WAY then the REAL spine path. Each receipt's
`provider`+`model` matches the actually-served identity (`runner._last_served_*`
← `response.provider` / `response.model`); `latency > 0`; result non-empty;
`status=ok`; persisted to `delegation_runs.receipt_json`.

| # | Configured provider | Served model (receipt) | Receipt matches served | Latency | Status |
|---|---------------------|------------------------|------------------------|---------|--------|
| 1 | `ollama_local` | `ollama/mistral:latest` | YES | 49,856 ms | ok |
| 2 | `ollama_cloud_glm5` | `ollama/glm-5` | YES | 19,918 ms | ok |
| 3 | `ollama_cloud_deepseek` | `ollama/deepseek-v3.2` | YES | 109,330 ms | ok |
| 4 | `ollama_cloud_qwen` | `ollama/qwen3-coder:480b-cloud` | YES | 5,015 ms | ok |
| 5 | `nvidia_nim` | `nvidia_nim/meta/llama-3.3-70b-instruct` | YES | 28,147 ms | ok |

Each row is a real network call to a real brain. The served identity
(`response.provider` / `response.model`) is the source of truth; the receipt is
asserted equal to it, not to the static config.

### Receipts read back from the lane DB (verification, not the in-memory object)

Re-reading `_proof_state/served_receipt_proof.db` `delegation_runs.receipt_json`
(round-trip, after the run finished) returns 6 rows, all `status=completed`,
`rstatus=ok`:

```
provider='nvidia_nim' model='meta/llama-3.3-70b-instruct' latency_ms=14975   <- FALLBACK (served)
provider='ollama'     model='mistral:latest'              latency_ms=49856
provider='ollama'     model='glm-5'                       latency_ms=19918
provider='ollama'     model='deepseek-v3.2'               latency_ms=109330
provider='ollama'     model='qwen3-coder:480b-cloud'      latency_ms=5015
provider='nvidia_nim' model='meta/llama-3.3-70b-instruct' latency_ms=28147   <- per-provider [5]
```

Persistence is proven by the DB round-trip, not by the live object.

---

## Fallback: configured ≠ served

| Property | Value |
|----------|-------|
| Configured (primary) provider | `ollama` — a `DeadProvider` whose `.complete()` raises (connection refused) |
| Router | a **real** `ModelRouter` (`dharma_swarm.providers.ModelRouter`, `max_attempts=1`) |
| Policy selection | the real policy router selected `ollama` as primary → chain `[ollama, nvidia_nim]` (ollama ranks #1 in the free hierarchy) |
| What happened | dead `ollama .complete()` raised → router walked the real chain → `nvidia_nim` **SERVED** |
| Served (fallback) provider/model | `nvidia_nim/meta/llama-3.3-70b-instruct` |
| Receipt names | `nvidia_nim/meta/llama-3.3-70b-instruct` (the **SERVED** brain), **NOT** the configured-dead `ollama` |
| Proven on | attempt 1 |
| Latency / status | 14,975 ms / ok |
| Persisted | YES — lane DB row 1 above |

The receipt followed the served brain through a real fallback walk, not the
config. That is the load-bearing property: when the configured primary is dead,
the receipt does not lie about who answered.

---

## Is the Loop 1 receipt robust across the model-routing hierarchy? — Plainly

**YES — ROBUST.** The Loop 1 receipt reflects **served-provider truth, not
config-assertion**, across the model-routing hierarchy:

- **5 of 5** distinct served-receipt proofs passed (each a real network call,
  served identity = receipt, latency > 0, non-empty result, persisted).
- The **configured ≠ served fallback** is **proven**: a real `ModelRouter`
  walked from a dead configured primary to a live fallback, and the receipt
  named the **served** fallback, not the configured-dead provider.

This closes the labeling-provenance nit that stood against the original Loop 1
closure receipt (`LOOP1_CLOSURE_RECEIPT.md`), where the receipt's provider/model
were copied from static `AgentConfig` rather than the served response. Here the
receipt is sourced from `runner._last_served_*` ← the actual `response.provider`
/ `response.model`, so the receipt now proves *who actually answered*, not just
*who we dispatched to*.

---

## HONEST PROVIDER-COUNT CAVEAT (read this)

The campaign target was **≥5 distinct REAL free providers**. That bar is **NOT
met by distinct provider integrations** on this machine. Stated plainly:

- **Only TWO distinct allowed-free provider integrations have live working keys
  here:** `ollama` (`OLLAMA_API_KEY` — free cloud subscription + local server)
  and `nvidia_nim` (`NVIDIA_API_KEY` — free 50/day tier). This exactly matches
  the recon allow-list `["ollama", "nvidia_nim"]`.
- **Every other allowed-free provider FAILS to serve** through the real provider
  path: `groq` = 403 auth-denied; `siliconflow` = 401 invalid-key;
  `cerebras` = 404 no-model-access (key present, no served model);
  `sambanova` / `together` / `fireworks` = no key at all.

The 5 VERIFIED served-receipt proofs were reached by exercising `ollama` across
its **genuinely-distinct serving backends** — 1 local (`mistral`) + 3 distinct
cloud frontier model **families** (`glm-5`, `deepseek-v3.2`,
`qwen3-coder:480b`) — plus `nvidia_nim`. Each is a real network call to a real
brain with a correct served-vs-receipt match. So:

> **5 distinct served *models / backends* passed (robust). But only 2 distinct
> *provider integrations* have live keys. The "≥5 providers" target is met at
> the model/backend granularity, NOT at the distinct-provider-integration
> granularity.**

This is an infrastructure (key-availability) limit, not a robustness gap in the
receipt path. The receipt mechanism is proven robust across every brain it could
actually reach. To meet "≥5 distinct provider integrations" verbatim requires
**operator action: live keys for ≥3 more allowed-free providers** (groq,
siliconflow, cerebras, sambanova, together, or fireworks) — which is already the
standing Phase-1 escalation item in the track (`[ops] (blocker) Operator
escalation: one real provider key`).

---

## What remains

- **For verbatim "≥5 distinct providers":** operator supplies live keys for ≥3
  more allowed-free providers; re-run `prove_served_receipt_multiprovider.py`
  with those provider types added to the per-provider list.
- **For the standing daemon:** as noted in `LOOP1_CLOSURE_RECEIPT.md`, the
  long-running daemon adopts the served-truth receipt only after the spine
  receipt patch merges and the daemon restarts on patched code. This report
  proves the path in-lane; it does not retroactively fix the daemon's pre-merge
  dispatches.

The receipt path itself: **ROBUST. 5/5 served proofs + fallback. $0.**
