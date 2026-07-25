---
id: pii-in-logs-scan
version: 0.0.1
theme: 16-observability
status: tested
invariant: >
  Logs are long-lived, widely-readable, and exported to third-party aggregators —
  so personal data (emails, names, tokens, payment info, full request bodies) in a
  log line is a privacy incident waiting to be discovered. The rule: log identifiers
  and references, never the sensitive value itself; redact at the logging boundary,
  not by hoping no one logs the wrong thing. Data minimization applies to logs too.
lineage:
  - "Saltzer & Schroeder — least privilege; logs grant broad read access"
  - "GDPR / data minimization — process (and retain) only what's necessary"
  - "defense in depth — redact at the sink, don't rely on every caller's discipline"
ground_truth_tools: ["grep/AST for sensitive vars reaching log/print sinks", "the logging formatter (does it redact?)", "what fields enter structured logs"]
returns_clean: true
---

## Prompt

> Scan for **PII / secrets in logs**. The invariant (data minimization): logs are
> long-lived and broadly readable, so a sensitive value in a log line is a latent
> breach. Find sensitive data (email, name, token, password, API key, full
> request/response bodies, PAN) reaching a **log/print sink**. For each: `file:line`,
> the field, and the fix — **log an identifier/reference, not the value**, and prefer
> **redaction at the formatter** (so it can't leak even if a caller is careless).
>
> Distinguish logging a **reference** (`user_id=123` — fine) from the **value**
> (`email=a@b.com` — not). **Return clean** if no sensitive value reaches a sink — and
> credit a redacting formatter if one exists.

## Why it's built this way

The durable fix is structural (redact at the sink — defense in depth), not "remember
not to log secrets" (which fails at scale). The discipline is the reference-vs-value
distinction (an id is fine, the value isn't) so the scan doesn't flag healthy
identifier logging.

## Demonstration run

**Target:** `dharma_swarm/`, 2026-06-25. Tool: grep for sensitive vars in log/print
sinks.

- **2 candidate sites** where a sensitive-looking name (`email`/`token`/`key`/`secret`)
  appears in a `log`/`print` call — a **low** count, i.e. the codebase mostly does not
  log sensitive values. 🟢 return-clean-leaning.
- **Disciplined output:** a 2-line checklist — for each, confirm whether it logs the
  **value** (fix: log a reference / redact) or just a **reference/length** (fine). Plus
  the structural recommendation: add a **redacting log formatter** for `api_key`/`token`
  fields so future careless callers can't leak — defense in depth beats per-caller
  discipline.

**Result:** mostly clean (2 to confirm), with the formatter-level redaction as the
durable hardening — not a manufactured wall of "you might log PII."

## Changelog

- **v0.0.1** (2026-06-25) — PII-in-logs scan (Saltzer–Schroeder/GDPR/defense-in-depth):
  value-vs-reference distinction, redact-at-the-sink fix, return-clean. Tested on
  `dharma_swarm`: only 2 candidate sites → short checklist + formatter-redaction
  recommendation, not alarm.
