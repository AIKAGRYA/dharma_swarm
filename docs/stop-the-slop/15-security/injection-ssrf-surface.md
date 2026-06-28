---
id: injection-ssrf-surface
version: 0.0.1
theme: 15-security
status: tested
invariant: >
  Injection happens when untrusted input reaches an interpreter sink — a shell, a SQL
  engine, an HTML renderer, a URL fetcher, an eval — as code instead of data. The fix is
  always parameterization/escaping at the sink + allow-listing, never input blacklisting.
  SSRF is the URL-fetch case: a server fetching an attacker-influenced URL can reach
  internal services. Trace taint from source to sink; a string-built command is the smell.
lineage:
  - "taint analysis — untrusted source flowing to a dangerous sink without sanitization"
  - "OWASP — Injection (A03) & SSRF (A10); parameterize, don't concatenate"
  - "least privilege — the sink's blast radius (shell=anything, SSRF=internal network)"
ground_truth_tools: ["grep/AST for sinks: subprocess(shell=True), string-built SQL, eval, server-side URL fetch", "trace untrusted source → sink", "parameterization/allow-list at the sink"]
returns_clean: true
---

## Prompt

> Audit the **injection / SSRF surface**. The invariant (taint analysis): untrusted
> input reaching an interpreter sink as code = injection. Find the sinks — `subprocess`
> with `shell=True` or string-built commands, string-concatenated SQL, `eval`/`exec`,
> template rendering, and **server-side URL fetches** (SSRF) — and for each, trace
> whether **untrusted input can reach it**. For real taint paths: the source→sink trace
> and the fix (parameterize / pass arg lists not shell strings / allow-list the URL host
> / escape at the sink). Rank by sink blast radius (shell ≫ SQL ≫ SSRF-to-internal).
> **Return clean** for sinks fed only by trusted constants.

## Why it's built this way

The bug is a *taint path*, not the sink's existence (a `subprocess` call with a constant
is fine). The discipline is tracing source→sink and fixing at the sink
(parameterization/allow-list), because input blacklisting always loses.

## Demonstration run

**Target:** `dharma_swarm/`, 2026-06-25.

- **Shell sinks:** **66** files use `subprocess`, of which **4 use `shell=True`** — those
  4 are the priority: confirm none interpolate untrusted input into the shell string
  (if they do → command injection; fix = arg list, no `shell=True`). The other 62 (arg-
  list form) are far safer.
- **SSRF:** `web_search.py` fetches URLs server-side, and result **`citations`/URLs are
  attacker-influenceable** → if `fetch_content` follows them without host allow-listing,
  that's SSRF to internal services (cross-refs the hardening + agent-security prompts).
- **SQL:** the repo uses parameterized `execute(?, (...))` (seen in the n+1 scan) — good;
  flag any string-built query.
- **Output:** prioritized taint list — the 4 `shell=True` sites and the `web_search`
  fetch path first; parameterized SQL credited.

## Changelog

- **v0.0.1** (2026-06-25) — injection/SSRF surface (taint/OWASP-A03+A10): trace
  source→sink, fix at the sink, rank by blast radius. Tested on `dharma_swarm`: 4
  `shell=True` sites + the `web_search` URL-fetch (SSRF) as priorities; parameterized SQL
  credited.
