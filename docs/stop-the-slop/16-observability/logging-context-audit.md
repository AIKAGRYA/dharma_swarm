---
id: logging-context-audit
version: 0.0.1
theme: 16-observability
status: tested
invariant: >
  When something breaks at 3am, you have only what you logged. Every failure path
  must emit a log carrying the operation name, the IDs that scope it (user/request/
  trace), and the original cause — and a caught-and-swallowed error with NO log is
  a guaranteed blind spot. You cannot debug what you did not record; an empty except
  is the darkest place in the system.
lineage:
  - "Gray 1985 — faults are normal; instrument for the failure you will have"
  - "Gregg (USE method) — observe utilization/saturation/errors on every resource"
  - "structured logging — context as fields, not prose, so it's queryable"
ground_truth_tools: ["AST/grep for catch-without-log", "the repo's swallow counter", "the real logging stack (structlog/sentry)"]
returns_clean: true
---

## Prompt

> Audit **observability of failure paths**. The invariant (Gray): when it breaks you
> have only what you logged. Every `except`/error path must log the **operation**,
> the **scoping IDs** (user/request/trace), and the **cause** (`from exc` /
> `cause:`). A swallowed error with no log is a guaranteed blind spot.
>
> **Find:** (1) `except` blocks that **don't log** (silent swallows — the worst);
> (2) logs that fire but **omit context** (no IDs, no operation, message-only);
> (3) critical paths (external calls, mutations) with **no** success/failure signal.
> For each: `file:line`, what's missing, and the minimal fix (log with fields /
> add the trace id / re-raise with cause).
>
> **Ground it in counts** (route to truth): measure how many silent swallows exist;
> rank by path criticality. **Return clean** for paths that already log with full
> context — and don't flag a *narrow, intentional* swallow (e.g. `except
> KeyboardInterrupt: pass`) the way you'd flag a broad blind one.

## Why it's built this way

Observability findings are easy to fake ("add logging everywhere"). The discipline
is to **measure the blind spots** (count the silent swallows), separate the broad
dangerous swallow from the narrow intentional one, and require *context* (queryable
fields), not just "a log exists." Gray is why failure paths get first-class
instrumentation; structured logging is why context must be fields.

## Demonstration run

**Target:** `dharma_swarm/`, 2026-06-25.

- **Measured blind spots:** `silent_exception_swallows = 244` (the repo's own
  ratchet counter) — 244 `except … : pass` sites with no witness. Plus **2,275**
  `except Exception` sites, many of which catch broadly; the audit asks of each: does
  it log `operation + ids + exc`?
- **The discipline's nuance (don't over-flag):** `cli.py:271 except
  KeyboardInterrupt: pass` and `diagnostics.py:70 except json.JSONDecodeError: pass`
  are **narrow and intentional** — not blind spots. The audit targets the **broad,
  witness-less** swallow (`except Exception: pass`), which is the real 3am hole.
- **Output:** rank the 244 by path criticality (a swallow in `a2a_client.py` /
  `agent_runner.py` dispatch path >> one in a CLI helper), and wire the fix to the
  existing `silent_exception_swallows` ratchet so it can only ratchet **down**.

**Return-clean note:** narrow intentional swallows are explicitly spared — a generic
"log everything" recommendation would be noise.

## Changelog

- **v0.0.1** (2026-06-25) — observability/logging-context audit (Gray/Gregg/
  structured logging): measure the blind spots, require queryable context, spare
  narrow intentional swallows, ratchet down. Tested on `dharma_swarm/`: grounded in
  the real 244 silent swallows + 2,275 broad catches, ranked by path criticality,
  wired to the existing ratchet.
