---
id: graceful-shutdown-audit
version: 0.0.1
theme: 14-state-and-lifecycle
status: tested
invariant: >
  On shutdown (SIGTERM, deploy, scale-down) a process must DRAIN: stop accepting new
  work, finish or safely checkpoint in-flight work, flush buffers, release resources —
  within the platform's grace period before SIGKILL. A process that ignores SIGTERM and
  gets hard-killed tears in-flight state, drops queue messages, and corrupts partial
  writes. Crash-only design (always-safe-to-kill) is the strong form; graceful drain is
  the pragmatic floor.
lineage:
  - "Gray — faults (incl. shutdown) are normal; the stop path is a first-class path"
  - "Candea & Fox — crash-only software: recovery == restart, so always be kill-safe"
  - "12-factor IX — fast startup & graceful shutdown on SIGTERM"
ground_truth_tools: ["SIGTERM/atexit handlers; do they drain?", "in-flight work checkpointing", "the deploy grace period vs drain time"]
returns_clean: true
---

## Prompt

> Audit **graceful shutdown**. The invariant (12-factor IX, crash-only): on SIGTERM the
> process must **drain** — stop intake, finish/checkpoint in-flight work, flush, release —
> inside the grace period. Check: (1) is **SIGTERM** handled (not just `KeyboardInterrupt`)
> with a drain, or ignored → hard-kill tears state? (2) is in-flight work **checkpointed**
> so a kill is recoverable? (3) are async tasks/connections **awaited closed** (`aclose`,
> task cancellation handled)? For each gap: what's lost on kill, the fix. **Crash-only
> bonus:** is the process always-safe-to-kill (idempotent restart)? **Return clean** for a
> process that drains or is provably kill-safe.

## Why it's built this way

The shutdown path is the one people don't test and the platform exercises on every deploy.
Gray says treat it as first-class; crash-only (Candea–Fox) is the gold standard
(always-restartable); 12-factor is the floor (handle SIGTERM, drain). The discipline is
checking the *stop* path with the same rigor as the start path.

## Demonstration run

**Target:** `dharma_swarm/`, 2026-06-25. **32** files reference
shutdown/signal/`aclose`/KeyboardInterrupt.

- **Audit shape:** the swarm runs **daemons** (`cron_daemon`, roaming dispatchers,
  background loops) — these are the drain-critical processes. Probe each: does it handle
  **SIGTERM** (deploy/scale-down signal) — not only `KeyboardInterrupt` (Ctrl-C, the dev
  path)? Several swallow `KeyboardInterrupt: pass` (seen in the error audit), which covers
  Ctrl-C but **not** SIGTERM drain. Flag daemons with no SIGTERM handler: on a cloud
  scale-down they're hard-killed mid-dispatch → torn receipts/in-flight tasks.
- **Crash-only angle (credit):** the receipt/idempotency substrate means restart is
  largely safe — lean into that (make every loop checkpoint so a kill is a no-op on
  restart). Output: per-daemon SIGTERM+drain check, crediting the receipt-based
  recoverability.

## Changelog

- **v0.0.1** (2026-06-25) — graceful-shutdown audit (Gray/crash-only/12-factor): SIGTERM
  drain + in-flight checkpoint + async close. Tested on `dharma_swarm`: 32 shutdown-
  related files; flagged daemons handling only `KeyboardInterrupt` (not SIGTERM) as the
  drain gap; credited receipt-based restart-safety.
