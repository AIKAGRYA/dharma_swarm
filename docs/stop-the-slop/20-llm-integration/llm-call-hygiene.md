---
id: llm-call-hygiene
version: 0.0.1
theme: 20-llm-integration
status: tested
invariant: >
  An LLM call is an unbounded, untrusted, costly network call. It must be BOUNDED
  (max tokens, timeout, retry cap), COST-CAPPED (budget enforced, not just tracked),
  INJECTION-AWARE (untrusted text in the prompt cannot be allowed to redirect the
  system instruction or trigger a tool), and SHAPE-VALIDATED (the response is parsed
  defensively — models return malformed/empty/refusal text). Treating an LLM call
  like a pure function is the new footgun.
lineage:
  - "Nygard (Release It!) — every remote call bounded + circuit-broken; LLM calls are remote calls"
  - "OWASP LLM Top 10 — LLM01 prompt injection, LLM04 model DoS, LLM10 unbounded consumption"
  - "Postel / defensive parsing — be strict about what you accept back"
ground_truth_tools: ["grep/AST for LLM call sites: max_tokens, timeout, retry, budget enforcement", "the cost tracker", "untrusted-text → prompt → tool path"]
returns_clean: true
---

## Prompt

> Audit **LLM call hygiene** in a codebase that *calls* models. The invariant
> (Nygard, OWASP LLM Top 10): an LLM call is an unbounded, untrusted, costly network
> call. Check every call site for:
>
> 1. **Bounds** — `max_tokens`, a **timeout**, a retry cap (unbounded retry on a paid
>    API is a cost+latency bomb).
> 2. **Cost cap** — is a budget **enforced** (call refused past a ceiling), or merely
>    *tracked* after the fact?
> 3. **Injection** — does untrusted text (user/web/tool output) enter the prompt in a
>    way that could override the system instruction or trigger a tool? (LLM01)
> 4. **Response shape** — is the response parsed **defensively** (empty/refusal/
>    malformed handled), or does it assume the happy shape? (cf. the `choices[0]` trap)
>
> Output: call-site → which of the four is missing → fix. **Credit** the call sites
> that already bound/cap/validate. **Return clean** on a well-bounded integration.

## Why it's built this way

LLM integration is a 2026 surface the generic kits don't cover at all, yet it's just
old discipline on a new call type: Nygard's "bound every remote call," OWASP's
injection/DoS, and defensive parsing of an unreliable response. The key distinction
the prompt forces: **cost tracked ≠ cost capped** (tracking tells you after you've
been billed; capping refuses the call).

## Demonstration run

**Target:** `dharma_swarm/` — an LLM-calling system — 2026-06-25.

- **Bounds (partial):** `max_tokens` set in **52** files (good coverage); exponential
  backoff exists (`providers.py:536`); **but** explicit per-call `timeout=` appears
  on essentially **1** provider path — **timeout coverage is the gap** (an LLM call
  with no timeout can hang a worker).
- **Cost (tracked, not proven-capped):** `cost_tracker.py` exists → cost is *tracked*.
  Open question: is there an **enforced** ceiling that refuses calls past budget, or
  only post-hoc accounting? Flag: verify a hard cap, don't assume.
- **Injection:** untrusted text enters via `web_search` results and A2A messages →
  trace whether any reaches a prompt that can trigger a tool (cross-refs the
  `ai-agent-security-audit`).
- **Response shape:** the `web_search.py:126` `choices[0]` assumption (from the
  hardening prompt) is exactly this smell — defensive parsing missing.

**Verdict:** good token budgets + cost tracking + backoff (credit); the open items are
**per-call timeouts**, an **enforced** cost cap, and defensive response parsing.
Balanced and specific, not "add error handling."

## Changelog

- **v0.0.1** (2026-06-25) — LLM-call hygiene (Nygard/OWASP-LLM/defensive-parsing):
  bounds, cost-capped-not-just-tracked, injection, response-shape. Tested on
  `dharma_swarm`: 52 files set max_tokens + cost_tracker present (credit); flagged
  sparse per-call timeouts, track-vs-cap, and the `choices[0]` shape gap.
