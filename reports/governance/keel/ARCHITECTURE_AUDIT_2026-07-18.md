# KEEL Companion Findings Ledger — Bare-Metal Architecture Audit

**Role:** the companion findings ledger THE KEEL (`docs/plans/THE_KEEL_2026-07-17.md`
§5) names — point-in-time architectural evidence, not doctrine and not ratified
truth. Findings here are **candidate observations** per THE KEEL §10: none binds
a gate until re-derived with a pinned command, a provenance capsule, and a
negative control.
**Date:** 2026-07-18. **Audit head:** produced against a working checkout on the
operator's host; this ledger is homed at repo base `82f7f1e3`.
**Producers:** five parallel adversarial pillar auditors (idempotency,
log/context, compute metabolism, async, sandbox/rollback); three queried a live
host `runtime.db`.
**Independent second vantage:** the code-path claims below were re-derived from a
clean cloud container by the homing seat; host-state claims (disk/DB row counts)
could not be — they are the operator's Mac, not reproducible here, and are
labeled accordingly.

## Verdict (producers): NO — not in current wiring

The primitives are frequently excellent; **the safety primitives are not wired
into the paths that spend money and mutate state.** "The system built its immune
system and left it in a jar next to the body."

## Evidence-status legend

- **CONFIRMED-CONTAINER** — code-path claim re-derived from a clean checkout this session (command in row).
- **HOST-CANDIDATE** — host/runtime-state claim (disk, DB rows); requires operator re-derivation on the Mac with a provenance capsule before it binds anything.
- **CODE-CANDIDATE** — code-path claim not yet independently re-derived here; verify before binding.

### Container-verified this session (CONFIRMED-CONTAINER)

| Claim | Command | Result |
|---|---|---|
| `cost_tracker.log_cost` has zero production callers (3.1) | `grep -rn "log_cost(" dharma_swarm --include=*.py \| grep -v "def \|test"` | empty |
| `economic_spine.spend_tokens` is tracking-only despite "enforce" docstring (3.1) | `economic_spine.py:274,290` | `return True  # Always succeed — no enforcement` |
| `is_budget_exceeded` kill-switch has 1 runtime call site (3.1) | `grep -rn "is_budget_exceeded()" dharma_swarm` | 1 (`replication_protocol.py:493`) |
| `LocalSandbox` hardcoded in the tool loop (5.1) | `agent_runner.py:1764-1766` | `self._sandbox = LocalSandbox(...)` |
| `orchestrate_live.py` has zero NATS references (4.1) | `grep -c "nats\|NATS\|jetstream" dharma_swarm/orchestrate_live.py` | 0 |

Host-state figures (**HOST-CANDIDATE**, operator re-derivation required): `~/.dharma`
≈182 GB (57 GB vectors.db, 66 GB lancedb, 31 GB conversation logs incl. one 12 GB
day, 346,521 `witness/chetana` JSONL); runtime.db 40→456 MB in ~10 weeks;
34,240/34,455 idempotency keys `idem_run_%`; 3,177/9,420 delegation_runs
receipted; 454 execution_identities vs 16,469 claim receipts; 20 wedged
`message_bus` rows; 482,885 idea_shards @4.8 GB; 583 in-repo receipt files; 63
worktrees; 380 branches; 217/860 modules >500 lines.

---

## PILLAR 1 — Idempotency & state boundedness

| ID | Sev | Finding (file:line) | Failure | Fix | Status |
|---|---|---|---|---|---|
| 1.1 | CRIT | keys minted per-attempt & wiped on retry — `spine/identity.py:78-82`, `orchestrator.py:2187-2190` `_clear_attempt_identity_metadata` | timeout→requeue→fresh random key→`INSERT OR IGNORE` never collides→full re-exec as first-time | intent key `sha256(task_id+canonical(content)+origin_event_id)` at creation, excluded from attempt-clear; per-attempt uniqueness moves to `side_effect_key` | CODE-CANDIDATE (clear-fn confirmed present) |
| 1.2 | CRIT | provider timeout→blind retry, no dedupe token, 4 multiplying layers — `resilience.py:314-352`, `providers.py:3020,3085-3089`, `agent_runner.py:2449-2547`, `orchestrator.py:2632-2637` | 1 intent = up to 3×N-providers×repair×(1+retries) billed, each "first time" | timeouts = ambiguous-outcome (not auto-retry); `Idempotency-Key` header from 1.1 key; pre-call intent receipt | CODE-CANDIDATE |
| 1.3 | CRIT | `message_bus.send` wedge = silent loss — `message_bus.py:245-291`, `stale_after_seconds` never passed (`runtime_state.py:3677`) | crash begin→INSERT wedges row `started` forever; later sends return id as if sent, no row | finite `stale_after_seconds`; verify row before claiming success | CODE-CANDIDATE |
| 1.4 | HIGH | random retry keys defeat NATS dedupe; handler runs before ack — `nats_transport.py:686-701,499-547`, `a2a_server.py:357-372` | concurrent redeliveries mint different keys, both do real work; crash pre-ack re-executes | deterministic `f"{key}:retry:{delivery_count}"` (count available `:568`) | CODE-CANDIDATE |
| 1.5 | HIGH | receipts mutable & fail-open — `runtime_state.py:3417-3476` `INSERT OR REPLACE`, `spine/persistence.py:64-75`, `orchestrator.py:2693-2719` | re-emit rewrites evidence incl. `created_at`; retries overwrite prior attempts | append-only `(task_id, receipt_id, attempt)`; reject replacement | CODE-CANDIDATE |
| 1.6 | HIGH | tollbooth fails open — `spine/tollbooth.py:15-36` `require_identity=False`, `runtime_state.py:1723-1733` writes anyway | identity is the exception, not the rule | fail-closed on spine surfaces; emit countable `identity_missing` receipt | CODE-CANDIDATE |
| 1.7 | HIGH | vectors.db size-bound gates reads, not writes — `vector_store.py:630-691` | converges on max size + zero utility simultaneously | enforce bound in `upsert` with evict-oldest (DELETE machinery `:848-858` exists, unreachable) | CODE-CANDIDATE |
| 1.8 | MED | idempotency machinery is the largest state inflator — `runtime_state.py:3622-3627`; no DELETE paths | ≥4 rows/effect; dedupe bookkeeping for a dedupe firing ~5% | TTL sweep past redelivery window; counter column not per-duplicate receipts | HOST-CANDIDATE |

## PILLAR 2 — Log lossiness & context ceiling

| ID | Sev | Finding | Fix | Status |
|---|---|---|---|---|
| 2.1 | CRIT | conversation log no daily rotation, fail-open master rotation — `conversation_log.py:104-116,175-191` | size-cap dailies, fail-closed rotation, TTL-delete, bounded tail reads | HOST-CANDIDATE |
| 2.2 | CRIT | raw prompts+output persisted forever, re-enter prompts unscanned ("Latent Gold") — `agent_runner.py:3225-3256,1285-1304`, `engine/conversation_memory.py:185-345` | write-cap ~20KB, sanitize at injection, 30-day turn TTL, salience-floor eviction | CODE-CANDIDATE |
| 2.3 | CRIT | 20,898-receipt deploy blocker "fixed" via .gitignore only; writers still target repo — `a2a_inbox_bridge.py:40`, `a2a_send.py:65`, `a2a_reply_capture.py:31-32`, `holon_l4_supervisor.py:201` | 4 path constants → `~/.dharma/a2a/...` (one-hour fix, outstanding ~1mo) | CODE-CANDIDATE |
| 2.4 | HIGH | no total token ceiling on dispatch prompt — `agent_runner.py:1014-1087,1227-1356,2426-2429`; `task.description` unbounded, fan-out chains it | one enforcement point at end of `_build_prompt`: estimate, head+tail truncate, hard-fail above ceiling | CODE-CANDIDATE |
| 2.5 | HIGH | agent `remember`/`share` write raw output to swarm-shared SQLite, uncapped/unscanned — `agent_runner.py:1883-1908`, `agent_memory_manager.py:220-488` | per-entry caps, injection scanner at tool boundary, provenance+confidence tags | CODE-CANDIDATE |
| 2.6 | HIGH | runtime.db zero retention; `MemoryWritePolicy` unreferenced (shadow mode) — `runtime_state.py` (DELETEs only FTS), `memory_kernel/` | retention job (90-day archive-then-delete); promote write-policy to enforcing on the 3 god-object writers | CODE-CANDIDATE |
| 2.7 | MED | stigmergy read rewrites whole file (`stigmergy.py:299-327`); distiller dead code; ~60 unrotated `open(...,"a")` | batched access-count flush; wire distiller into sleep-cycle; shared `rotating_jsonl_append` | CODE-CANDIDATE |

## PILLAR 3 — Computational metabolism

| ID | Sev | Finding | Fix | Status |
|---|---|---|---|---|
| 3.1 | **CATASTROPHIC** | no enforcement point between any loop and any LLM call — `cost_tracker.py:71-99` (0 callers), `economic_spine.py:273-290` ("no enforcement"); unknown models priced $0.0; `cost_log.jsonl` never written | **single highest-leverage fix:** `check_global_cost_cap()` at the `providers.py` chain chokepoint (where `_estimate_cost` runs), rolling-24h sum vs `DHARMA_DAILY_USD_CAP`, no ≤0-unbounded escape, unknown models conservative-priced | **CONFIRMED-CONTAINER** |
| 3.2 | CATASTROPHIC | thinkodynamic director zero-sleep re-entry, `--hours` default 0.0=forever, under caffeinate — `thinkodynamic_director.py:5080-5164` | cap consecutive no-sleep re-entries at 3; `hours<=0` errors absent env override; cost-cap at `run_cycle` top | CODE-CANDIDATE |
| 3.3 | CRIT | delegation ends only when model stops delegating — `thinkodynamic_director.py:4536-4575`; 3 children/task, no depth/total cap, breaks only on failure | `delegation_depth` metadata, refuse at ≥3, per-cycle task ceiling | CODE-CANDIDATE |
| 3.4 | CRIT | Free Evolution Grind inverse backoff (stagnation speeds up); spends before budget check — `orchestrate_live.py:1344-1696`, `evolution.py:2026-2040` | budget check before generation; true backoff on non-improvement; daily cycle ceiling | CODE-CANDIDATE |
| 3.5 | CRIT | DarwinEngine daemon `max_cycles=None`, `max_cycle_tokens=0`(=disabled) — `evolution.py:3339-3494` | 0→sane default; `-1` for explicit unbounded | CODE-CANDIDATE |
| 3.6 | HIGH | heartbeat is full agentic session w/ `bypassPermissions`; midnight counter never resets — `pulse.py:124-153,597`, `orchestrate_live.py:572-588` | non-LLM pulse default; fix midnight reset | CODE-CANDIDATE |
| 3.7 | HIGH | daemon fleet defaults unbounded; `holon_budget_guard` never called by its consumer; `cap<=0` silent-unbounded — `merge_master_mike_daemon.py:668,890`, `codex_composer_wake_loop.py:1177,1319`, `holon_budget_guard.py:25-36` | adopt `codex_overnight.py:611-645` wall-clock pattern fleet-wide; wire guard; `cap<=0` raises | CODE-CANDIDATE |
| 3.8 | MED | provider chain no rate limiter, multiplicative fallback (≤36 attempts/req); `roaming_dispatch_daemon.py:136-142` `while True`+bare-except+sleep-in-async; dead zero-sleep loop `orchestrate_live.py:1215-1226` | total-attempt cap + token-bucket/provider; log-and-sleep-async; delete dead loop | CODE-CANDIDATE |

*Producer credit (verify before relying): telos gates, routing, intent classification, quality assessment are deterministic (no LLM in gate path); agent tool loop, repair loop, autoresearch, cron daemon are bounded.*

## PILLAR 4 — Async decoupling & event matrix

| ID | Sev | Finding | Fix | Status |
|---|---|---|---|---|
| 4.1 | CRIT | production truth = unlocked JSONL, 3 uncoordinated write protocols — `operator_core/a2a_task_lifecycle.py:184-485` (lock-free RMW), `hermes_heartbeat_poll.py:77,148-165` (flock), `codex_composer_wake_loop.py:357` (append); JetStream is evidence-harness only | one flock contract via existing `file_lock.py`, module-level requirement of `a2a_task_lifecycle.py` | **CONFIRMED-CONTAINER** (orchestrate_live 0 NATS) |
| 4.2 | CRIT | sync calls freeze event loop minutes — `thinkodynamic_director.py:1686` `subprocess.run(timeout=300)` in async; `review_cycle.py:102-110`, `a2a_bridge.py:215-236` (`thread.join()` from loop) | `create_subprocess_exec`/`to_thread` (pattern exists `zeitgeist.py:161-170`); async-only spine submit | CODE-CANDIDATE |
| 4.3 | HIGH | NATS reconnect disabled — `nats_transport.py:140-145` `allow_reconnect=False` | bounded-backoff reconnect; drop cached handles on close | CODE-CANDIDATE |
| 4.4 | HIGH | `DeliverPolicy.NEW` + never-provisioned stream = invisible loss; envelope acks over core NATS — `nats_transport.py:243`, `a2a_inbox_bridge.py:79,256,362-371` | `DeliverPolicy.ALL`, provision `DHARMA_FLEET` in `ensure_stream_topology`, JetStream acks | CODE-CANDIDATE |
| 4.5 | HIGH | DLQ client-side only; max-deliver exhaustion parks silently; `ensure_stream_topology` returns "ok" on error — `nats_transport.py:203-215,568-766` | subscribe MAX_DELIVERIES advisory; "ok" only after `stream_info` round-trips | CODE-CANDIDATE |
| 4.6 | MED | `signal_bus.py:63-155` unbounded volatile deque (dark during 4.2 stalls); `runtime_state.py:403-411` no `busy_timeout`, conn-per-op, 4 WAL commits/msg; `orchestrator.py:402-469` serial assign, no semaphore | `maxlen`+dropped-counter; `busy_timeout=30000`+long-lived conn+batching; `gather`+`Semaphore(k)` | CODE-CANDIDATE |

*SIGKILL behavior: board tasks recover (`swarm.py:2414-2426` orphan rescue real); file-queue claims wedge `claimed` forever; NATS parks invisibly after 3 deliveries; SignalBus dies.*

## PILLAR 5 — Sandbox paranoia & atomic rollbacks

| ID | Sev | Finding | Fix | Status |
|---|---|---|---|---|
| 5.1 | CRIT | LLM shell strings on bare `/bin/sh` behind 7-pattern regex — `agent_runner.py:2001-2010,1920-1924` (hardcodes LocalSandbox), `sandbox.py:22-100`; misses `rm -rf ~/`, `curl\|sh`, key exfil; no telos gate | `SandboxManager.create_async(prefer_docker=True)` fail-**closed**; allowlist+`create_subprocess_exec`+`shlex`; gate via `TelosGatekeeper` `external_strict` | **CONFIRMED-CONTAINER** (LocalSandbox hardcoded `:1766`) |
| 5.2 | CRIT | `write_file`/`edit_file` accept absolute/`~`/`../` — arbitrary host write — `agent_runner.py:1567-1583` | enforce `resolved.relative_to(workdir)`, reject on `ValueError` | CODE-CANDIDATE |
| 5.3 | CRIT | self-mod diffs escape workspace via unsanitized `+++` paths — `diff_applier.py:190,267`; gate is substring match in permissive `internal_yolo` (`telos_gates.py:408-520`) | resolve+`is_relative_to` guard; reject absolute/`..` at parse; effect-based gate; default self-mod `external_strict` | CODE-CANDIDATE |
| 5.4 | HIGH | "atomic apply" false; hunks splice by line number, no context check, no rollback on partial — `diff_applier.py:297-372,463-482`; corruption archived if tests pass (`evolution.py:3258`) | all-or-nothing staging (temp+`os.replace`), rollback branch, per-hunk context verify, or `git apply --check` | CODE-CANDIDATE |
| 5.5 | HIGH | canary "rollback" flips a status field, code stays on disk — `canary.py:148-156`, `archive.rollback_entry`; archive rewrite truncate-in-place no lock destroys lineage (`archive.py:356-363`) | bind ROLLBACK to `git revert` verified vs baseline; temp+fsync+`os.replace` under lock | CODE-CANDIDATE |
| 5.6 | MED | `auto_approve=True`+no callback silently APPROVES every human-interrupt/timeout — `checkpoint.py:115-156`; mutation/interrupt ledgers truncate-in-place | fail-closed on missing callback; reuse the one correct atomic write (`checkpoint.py:225-247`) for all ledgers | CODE-CANDIDATE |

*Caveat (producers): these are code-path findings; whether each daemon runs on the Mac was not runtime-verified. Cron/build entrypoints are wired to invoke them.*

---

## Systemic drift (single-operator axis)

Deepest scaling risk is not any one bug: **doctrine and code have decoupled and
reconciliation lands on one human.** Receipts lie in ≥4 places (CLAUDE.md "$3/day
chetana cap" absent in code; `economic_spine` docstring vs its own comment;
`ensure_stream_topology` "ok" on failure; the cosmetic receipt-sprawl fix). 63
worktrees / 380 branches / 733 commits behind main. NATS evidence 16 days stale —
checkers detect drift, nothing metabolizes it. 55–130 min test suite → changes
ship on focused tests, which is how 5 idempotency protocols and 3 queue-write
protocols accumulated.

## Hardening sequence (producer ranking, leverage-per-hour)

1. **The one budget gate** (3.1) — every cost-spiral is downstream of this single missing function.
2. **Intent-derived idempotency keys that survive retry** (1.1/1.2/1.4).
3. **Fail-closed sandbox + path confinement** (5.1/5.2/5.3).
4. **Loop bounds fleet-wide** (3.2–3.7) — mostly default-flips.
5. **Event-loop hygiene + one queue lock** (4.1/4.2).
6. **Retention everywhere** (1.7/1.8/2.1/2.2/2.6) — one nightly sweep, reclaims most of the host disk.
7. **Real rollback** (5.4/5.5).
8. **Receipt honesty** (1.5/2.3/4.5).

Items 1–2 ≈ two days remove unbounded spend + double-billing; item 3 ≈ one day
removes host compromise. **Nothing requires new architecture — in almost every
case the correct primitive already exists and needs wiring into the path that
matters.**

---

## Homing map — where each finding becomes tracked work

Per THE KEEL, this ledger is evidence; it fans out to the existing machinery by
type. None of the below is enacted here (this file grants no authority):

- **Broken Register** (`docs/state/BROKEN_REGISTER.md`, BR-NNN) — the
  CATASTROPHIC/CRITICAL code-path findings get BR-ids with status, owner, and a
  verification command, so they enter the machine-trackable ledger and ratchet
  down instead of rotting. Priority candidates: 3.1, 3.2, 1.1, 1.2, 5.1, 5.2,
  5.3, 4.1, 1.3.
- **INTERFACE_MISMATCH_MAP.md** — the "N uncoordinated protocols / declared≠wired"
  findings that are interface mismatches proper: 4.1 (3 queue-write protocols),
  2.6 (write-policy facade), 3.1 (guard↔consumer decoupling).
- **Wave-0/1 packets** (`reports/agentops/work_packets/` + track `next_items`) —
  the hardening sequence, each routed to its owning pillar (spend→Agent-Ops/Runtime;
  idempotency→Runtime; sandbox→sovereign-safety-tcb; async→Runtime;
  retention→Harness/chamber). Wave-0 first regenerates every HOST-CANDIDATE figure
  with a provenance capsule + negative control per THE KEEL §10.
- **THE KEEL §5** (`docs/plans/THE_KEEL_2026-07-17.md`) — cites this ledger as its
  companion; the budget-gateway finding (3.1) is already THE KEEL Wave-1's first task.

**Operator decisions this ledger surfaces:** (1) which findings get BR-ids now vs
after host re-derivation; (2) pillar ownership for each hardening item (the
Ratification Act); (3) whether the host-state figures are re-derived on the Mac
before or alongside the first fixes.
