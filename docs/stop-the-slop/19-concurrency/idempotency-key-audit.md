---
id: idempotency-key-audit
version: 0.0.1
theme: 19-concurrency
status: tested
invariant: >
  Any operation that can be retried (network call, queue consumer, webhook, paid
  mutation) MUST be idempotent — the same request applied twice produces one effect —
  or the retry double-applies (double-charge, duplicate row, repeated email). Safe
  retry requires an idempotency key the receiver dedups on, or a naturally-idempotent
  operation (PUT, upsert). Retry without idempotency is a bug amplifier.
lineage:
  - "REST — PUT/DELETE idempotent by design; POST is not, so it needs a key"
  - "exactly-once is a fiction; at-least-once delivery + idempotent handler = effectively-once"
  - "Nygard — retries are normal; design the receiver to absorb them"
ground_truth_tools: ["find retried/at-least-once paths (queues, webhooks, dispatch)", "do mutations carry/dedup an idempotency key?", "the dedup store"]
returns_clean: true
---

## Prompt

> Audit **idempotency** of retried mutations. The invariant: at-least-once delivery is
> the reality, so any retried operation must be idempotent or it double-applies. For
> each mutation reachable by a retry/queue/webhook/dispatch path: does it carry an
> **idempotency key** the receiver dedups on, or is it naturally idempotent (upsert/
> PUT)? If neither, a retry duplicates the effect — name the concrete consequence
> (double-charge / duplicate record / repeated side effect). **Credit** existing
> idempotency substrate; **return clean** where mutations are keyed or upsert-shaped.

## Why it's built this way

"Exactly-once" doesn't exist at the transport layer; the only real design is
at-least-once + an idempotent handler. The discipline is tracing which mutations are
actually retried and checking each for a dedup key — not assuming the framework handles
it.

## Demonstration run

**Target:** `dharma_swarm/`, 2026-06-25. The repo's dispatch path is the retried surface.

- **Substrate present (strong credit):** **43** files reference idempotency —
  `IdempotencyRecord` is named in the governance canon as "exactly-once substrate," and
  the spine emits a single `EvidenceReceipt` per dispatch. So the core dispatch path
  *has* a dedup mechanism. 🟢
- **Audit (the open part):** does **every** retried mutation route through the
  idempotency substrate, or are there bypass paths (cf. the spine-bypass allowlist) that
  retry a side effect without a key? Probe: A2A re-delivery and any provider call that
  is retried (`providers.py` backoff) followed by a state write — confirm the write is
  keyed/upsert, not a blind re-apply. Named as the open item, substrate credited.

## Changelog

- **v0.0.1** (2026-06-25) — idempotency audit (REST/at-least-once/Nygard). Tested on
  `dharma_swarm`: credited the `IdempotencyRecord` + single-`EvidenceReceipt` substrate
  (43 files); flagged retried-mutation-without-key bypass paths as the open probe.
