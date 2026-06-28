---
id: compliance-pii-readiness
version: 0.0.1
theme: 15-security
status: tested
invariant: >
  Handling personal data creates code-level obligations (independent of legal advice):
  know WHERE PII lives (a data map), collect only what's needed (minimization), be able to
  DELETE it on request (right-to-erasure → no orphaned copies in logs/caches/backups),
  RETAIN it only as long as needed (TTL/purge), and AUDIT access. Code that scatters PII
  with no data map and no delete path cannot satisfy erasure — that's a compliance bug,
  not a legal opinion.
lineage:
  - "GDPR / CCPA — data minimization, purpose limitation, right to erasure, retention limits"
  - "privacy by design (Cavoukian) — build the controls in, don't bolt them on"
  - "Saltzer & Schroeder — least privilege over personal data; audit access"
ground_truth_tools: ["map where PII fields are stored/logged/cached", "is there a delete/erasure path?", "retention/TTL + access audit"]
returns_clean: true
---

## Prompt

> Audit **PII / compliance readiness** at the code level (not legal advice). The invariant
> (GDPR minimization + erasure + retention): (1) **Data map** — where does PII (emails,
> names, IPs, tokens, user content) get stored, logged, cached, or sent to third parties?
> (2) **Minimization** — is PII collected/retained beyond need? (3) **Erasure** — is there
> a delete path that removes *all* copies (DB + logs + caches + backups), or do orphans
> survive a deletion request? (4) **Retention** — TTL/purge, or forever? (5) **Access
> audit** — is access to PII logged? For each gap: the field, the obligation it breaks, the
> fix. **Return clean** for a system with a data map, an erasure path, and retention
> limits. Flag scope: this is engineering readiness, not legal sign-off.

## Why it's built this way

The compliance failure is almost always *structural* — PII scattered with no data map, so
"delete my data" can't be honored because nobody knows all the copies. Privacy-by-design
(build the controls in) and the GDPR primitives (minimize / erase / retain-limited /
audit) make it a code checklist, distinct from legal advice.

## Demonstration run

**Target:** `dharma_swarm/`, 2026-06-25.

- **PII surface (light, but present):** the system is agent-infrastructure, not a consumer
  app, so PII is limited — but it exists: operator emails, provider **API keys** (sensitive
  secrets), agent message content, and any user content flowing through A2A/web. The
  receipt/JSONL stores (`~/.dharma/**`, `reports/**`) persist message content — those are
  the retention/erasure surface.
- **Disciplined checklist:** (a) **data map** — enumerate where message content + keys land
  (receipts, traces, logs); (b) **erasure** — is there a path to purge a given subject's
  content from the JSONL receipt trail, or is it append-only-forever (append-only conflicts
  with erasure — flag it); (c) **retention** — do `~/.dharma` receipts/traces have a TTL/
  purge, or grow forever? (d) the secret-leakage + pii-in-logs prompts cover the
  logging-sink half. Output: the data map + the append-only-vs-erasure tension as the key
  finding, scoped explicitly as engineering readiness.

## Changelog

- **v0.0.1** (2026-06-25) — compliance/PII readiness (GDPR/privacy-by-design): data map +
  minimization + erasure + retention + access audit, scoped as code-readiness not legal
  advice. Tested on `dharma_swarm`: limited PII surface (operator emails, keys, message
  content in receipts); flagged append-only-receipts-vs-erasure + retention TTL as the key
  tensions.
