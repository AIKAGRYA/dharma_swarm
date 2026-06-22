# The Seeing Organ — First Real Meal (world-signal seed batch)

**Run:** 2026-06-22T02:43:09.285552Z · **Source:** docs report: Screenshot Tool Seed Batch (Devin, 2026-06-21) — untrusted world-signal

The first batch of REAL world-signals run through the live Stage 0/1/2 pipeline (not fixtures). The report's 18 tool-claims were treated as untrusted input; evidence refs were hand-assembled from each claim's real provenance; the VERDICT fell out of the structural moat (>=2 decorrelated evaluator families AND >=2 decorrelated source families; a high-quality refutation dominates). **Persuasive prose did not corroborate anything — independent evidence did.**

## Stage 0 — safety
- All 18 envelopes safe: **True**
- All payloads fenced (instruction/data separation held): **True**
- No signal tripped injection markers (the seed batch was benign); the fence held regardless. Quarantine of high-risk signals is exercised by the adversarial test, not faked here.

## Stage 1 — Frontier Council verdicts
`{'corroborated': 9, 'insufficient': 7, 'refuted': 2}`

| signal | verdict | evaluator families | source families | refutations |
|---|---|---|---|---|
| cost_control | corroborated | 3 | 3 | 0 |
| markitdown | corroborated | 3 | 3 | 0 |
| dspy | corroborated | 3 | 3 | 0 |
| continue | corroborated | 3 | 3 | 0 |
| dify | corroborated | 3 | 2 | 0 |
| twenty | corroborated | 3 | 2 | 0 |
| docuseal | corroborated | 3 | 2 | 0 |
| anytype | corroborated | 3 | 2 | 0 |
| papermark | corroborated | 3 | 2 | 0 |
| huly_docuseal_identity | refuted | 0 | 1 | 2 |
| open_notebook_identity | refuted | 0 | 1 | 2 |
| maybe | insufficient | 0 | 1 | 0 |
| headroom_perf | insufficient | 0 | 1 | 0 |
| last30days_skill | insufficient | 0 | 1 | 0 |
| taste_skill | insufficient | 0 | 1 | 0 |
| agent_reach | insufficient | 0 | 1 | 0 |
| career_ops | insufficient | 0 | 1 | 0 |
| pm_skills | insufficient | 0 | 1 | 0 |

## Stage 2 — advisory warrant-pressure (read-only)
Only **corroborated** receipts produce pressure; weight rises with decorrelated agreement; `dispatch_authority` stays **False** on every projection (held False: **True**).

| signal | claim | weight | eval families | source families | dispatch_authority |
|---|---|---|---|---|---|
| markitdown | MarkItDown reliably converts heterogeneous documents to Markdown and is usable as the Phase-0 ingestion seam. | 0.6011 | 3 | 3 | False |
| cost_control | Tiered model selection + prompt caching + output-token minimization materially reduce LLM operating cost. | 0.5749 | 3 | 3 | False |
| dspy | DSPy is a usable framework for typed, evaluable LLM modules with optimizers. | 0.5749 | 3 | 3 | False |
| continue | Continue is a real, independently distributed open coding-assistant with a context-provider model. | 0.5096 | 3 | 3 | False |
| dify | Dify is a real, self-hostable OSS LLM workflow platform. | 0.4416 | 3 | 2 | False |
| twenty | Twenty is a real, self-hostable open CRM with a customizable object model. | 0.4416 | 3 | 2 | False |
| docuseal | DocuSeal is a real OSS e-signature/document tool with an API and JS SDK. | 0.4416 | 3 | 2 | False |
| anytype | Anytype is a real local-first/E2EE knowledge OS with an independent sync protocol and clients. | 0.432 | 3 | 2 | False |
| papermark | Papermark is a real OSS document-sharing tool with analytics and a published API/CLI. | 0.4224 | 3 | 2 | False |

## What this proves
- The organ eats **real input**, not fixtures, end to end.
- The moat **discriminates**: a tool Devin independently reproduced (MarkItDown) and claims backed by independent providers (cost-control) corroborate; single-origin briefs and an unreproduced vendor benchmark (Headroom 60-95%) fall to *insufficient*; the two screenshot identity mismatches are preserved as *refuted* contradictions, not silently normalized.
- The whole run is **read-only**: corroborated signals become advisory pressure only. Nothing dispatched, nothing mutated. Acting on what was seen remains the gated step (Stage 3, not enabled).

*This is a demonstration run. It creates no authority surface and mutates no owner. Insufficient != false — it means not yet cross-validated by decorrelated evidence.*
