---
id: hardening-checklist
version: 0.0.1
theme: 10-production-hardening
status: tested
invariant: >
  Hardening is triage, not rewriting. Rank by P(incident) × blast-radius, and
  every finding must name the SPECIFIC line, the SPECIFIC mechanism, and the
  SPECIFIC consequence ("line 34: a Stripe timeout loses the payment-intent id and
  the retry double-charges") — never "add error handling." Output is a tiered
  checklist; no code until the human picks. A generic checklist is noise; a
  line-and-mechanism checklist is a runbook.
lineage:
  - "Nygard 2007 (Release It!) — stability & capacity patterns; failures cascade"
  - "Gray 1985 — Why Do Computers Stop: faults are normal; design for them"
  - "Saltzer & Schroeder 1975 — validate at the boundary; least privilege"
ground_truth_tools: ["read the actual file(s)", "trace each external call's failure modes", "the real traffic/load class"]
returns_clean: true
---

## Prompt

> I have working prototype code I want to ship — **no rewrite**, just the focused
> pass that fixes what will actually bite me in production. The invariant (Nygard,
> Gray): faults are normal; rank by `P(incident) × blast_radius`, and every finding
> is **line-specific and mechanism-specific** — "add error handling" is useless,
> "line 34: a timeout here loses the id and the retry double-charges" is a runbook.
>
> **Context:** files: `[paths]` · what it does: `[1–2 sentences]` · where it runs:
> `[server action | API route | job | client]` · load: `[low | med | high]`.
>
> **Read the file(s), then produce a checklist grouped into:**
> - **Correctness** — things actually wrong that will cause incidents
> - **Failure handling** — external call fails / times out / returns an unexpected
>   shape (name the shape and the line that assumes it)
> - **Edge cases** — empty, very large, concurrent, partial state
> - **Security** — input validation, auth checks, secret leakage, injection, SSRF
> - **Observability** — where you'll be *blind* when it breaks (no log/metric/context)
>
> Each item: **`file:line` → mechanism → consequence**, rated
> **must-fix-before-ship | should-fix-soon | nice-to-have**. Weight by the stated
> load (a race at high traffic is must-fix; at low traffic, should-fix).
>
> **Do not write code yet.** Wait for me to pick. **Return clean** on any category
> that's genuinely solid — don't invent a finding to fill all five buckets.

## Why it's built this way

The kit's version already nails the "be specific" rule and the no-code-yet gate.
We add the **ranking model** (P×blast-radius, weighted by real load — Nygard's
capacity thinking) and **return-clean per category**, so a solid file doesn't get
five manufactured findings. Gray's lesson — faults are normal — is why "failure
handling" is its own bucket, not an afterthought.

## Demonstration run

**Target:** `dharma_swarm/web_search.py` (596 lines), `PerplexityProvider.search`,
2026-06-25. Runs: async, on agent/research paths. Load: low–med.

| Bucket | `file:line` → mechanism → consequence | Severity |
|---|---|---|
| Failure handling | `web_search.py:122` `except Exception as exc` — catches *everything* (incl. bugs, asyncio.CancelledError on older patterns) around the httpx call; a real fault is flattened to "no results" with no distinction between "rate-limited" and "code bug" | should-fix-soon |
| Failure handling | `:126–131` parses `data["choices"][0]["message"]["content"]` — **assumes the success shape**; on an error/empty body the API returns no `choices`, so this raises `IndexError`/`KeyError` *inside* the broad catch → silent empty result, no signal | **must-fix-before-ship** |
| Edge/perf | `:114` `httpx.AsyncClient(timeout=30)` — 30s is very long on a request-bound path; under load a slow upstream ties up the caller. Make it lower + configurable | should-fix-soon |
| Observability | the broad catch at `:122` — is `exc` logged *with the query and provider*? If not, every search failure is invisible. Confirm a structured log on the failure branch | should-fix-soon |
| Security (SSRF) | if `fetch_content(url)` follows `citations`/result URLs server-side, those are attacker-influenceable → SSRF; validate/allowlist the host before fetching | must-fix **iff** server-side fetch is reachable |

**Return-clean note:** auth/secret handling here is fine — keys come from env
(`API_KEY_ENVS`) and aren't logged in the read paths seen; not flagged.

## Changelog

- **v0.0.1** (2026-06-25) — rewrite of a kit's production-hardening prompt. Added
  the P×blast-radius ranking weighted by real load (Nygard), faults-are-normal
  framing (Gray), and return-clean-per-category. Tested against
  `dharma_swarm/web_search.py` — produced 5 line-and-mechanism findings (the
  unchecked `choices[0]` shape at :126 is the real must-fix) and explicitly cleared
  the auth/secret bucket.
