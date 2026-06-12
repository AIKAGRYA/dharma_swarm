# Goal B — Independent Verifier Re-Adjudication (post-builder)

- mission_id: `20260605T141918Z-goal-b-broker-paper-execution-membrane-continuation`
- adjudicator: `opus_composer`
- generated_at_utc: `2026-06-06T` (session re-verification)
- method: 6-lane adversarial re-verification (each lane prompted to REFUTE the builder claim against real code + artifacts), read-only.

## Why this document exists

The mission's original verifier receipt (`r-3d65dfd87f713ca3`, gemini-flash-worker,
`2026-06-05T14:25:49Z`, status=blocked) was recorded **45 minutes before the
builder completed** (`r-1cdc48587d0f060b`, codex_composer, `2026-06-05T15:10:36Z`).
It adjudicated the *prior Agni* evidence, not the final fixture membrane. Every
blocker it cited now has a corresponding builder artifact. This re-adjudication
verifies those final artifacts independently — neither trusting the builder's
self-grade nor re-using the stale block.

## Hard status — UNCHANGED and CORRECT

`live_readiness=0` · `live_authority=false` · `broker_write_authority=false` · `clean=false`

These are not just held — they are **defensible**. The membrane imports no broker
SDK; the false/zero invariants are hard-coded constants (`broker_paper_membrane.py:18-21`);
and the live Hyperliquid surface the contract feared was **not found on disk/env**
(only a read-only info-endpoint client at `~/.hermes/.../hyperliquid_client.py` —
no signing, no order placement; no live-order repo, no `HYPERLIQUID_PRIVATE_KEY`
alias located). The fixture cannot place a live order.

## Runtime verification (executed, not asserted)

- `./.venv/bin/python -m pytest tests/test_capital_lab_broker_paper_membrane.py -q` → **6 passed (0.29s)**
- `autonomy_spine.py verify --phase complete --json` → **`complete_valid: true`** (4 completed / 1 blocked / status review). The 14:25Z `task_not_closed` block was a timing artifact; the ledger is now coherent.

## Lane verdicts

| Lane | Verdict | Safety holds | One-line truth |
|---|---|---|---|
| authority-fence | partial | ✅ | Real safety = "imports no broker + hardcoded zeros". The AST fence itself is name-match-only and bypassable (`__import__`, `hyperliquid_client`, subprocess, exec) — **overclaimed as a live-bleed control**, but not load-bearing. |
| idempotency-duplicate | partial | ✅ | Determinism, dedup, durable replay all **genuinely confirmed**. Gap: dedup is id-string-only — a colliding id with different economics silently returns the first order (footgun only on a future real-broker route). |
| lifecycle-parity | **confirmed** | ✅ | All 7 events (submit/ack/partial/full/cancel/reject/expire) real; state machine enforces legality. Only cosmetic nits. |
| reconciliation | partial | ✅ | Mismatch **detection** is real (genuine field-diff → flag). But "block" is a JSON flag + latching bool **no lifecycle method reads** — not an enforcement halt. Price/limit drift is structurally invisible (no price field). |
| kill-switches | partial | ✅ | **The headline gap.** Reconciliation-mismatch + duplicate-order halts are real. The 4 *environmental* kill-switches (heartbeat / stale-data / max-loss / order-rate-exposure) are **hardcoded `True` literals with no detector**. The Agni→continuation "closure" of order_rate/exposure and rejection_drill (false→true) is a **relabel, not an implementation.** |
| overclaim-audit | **confirmed** | ✅ | No material overclaim. Lone nit: `score:80.0` in the feasibility packet has a positive affordance, but is co-located with `live_readiness:0 / clean:false / fixture_or_internal_only:true`. |

## Synthesis

- **Safety: GREEN (7/7 lanes).** Nothing here can touch live capital.
- **Honesty of the safety *story*: AMBER.** Real: lifecycle parity, idempotency, mismatch detection. Theater (label-not-behavior): the 4 environmental kill-switches, the feasibility drill booleans (constants not wired to call outcomes), and the reconcile "block" (flag, not a gate). This is the **same Goodhart/label-reader pathology** found in the Harbor anti-Goodhart gate audit (2026-06-05) — a drill that *asserts a boolean* rather than *detects a behavior*.
- **Completeness: correctly BLOCKED.** External paper-broker evidence absent (by design); live authority correctly refused pending an explicit operator lease.

## Honest terminal state

`fixture_membrane_safe_but_drills_partly_overclaimed` — keep `clean=false`,
`live_readiness=0`. **Do not** promote toward live on the strength of the
kill-switch receipts; they do not yet detect anything.

## The one real-gap slice (if this lane is kept)

Replace the 4 hardcoded environmental kill-switch booleans with real detectors
(heartbeat clock, order-rate counter, max-loss accounting, stale-data age check),
wire the feasibility drill booleans to actual `reject/cancel/expire` call outcomes,
and make a tripped `kill_switch_engaged` actually gate the order lifecycle
(check-before-mutate) instead of being an unread flag. Add a price field +
economics-mismatch guard on duplicate submit. All offline/fixture — no provider,
no broker, no operator lease required for the *honesty* fix.

## REMEDIATION (same session, post-adjudication) — the theater is now real

The operator confirmed capital_lab is a serious autonomous-hedge-fund program,
not a toy. The #1 finding (kill-switch theater) was therefore remediated, not
just reported:

- **New module `dharma_swarm/capital_lab/risk_governor.py`** — a real
  `RiskGovernor` with detect-and-halt controls: order-rate (rolling window),
  per-symbol position, gross-exposure (notional), heartbeat staleness,
  market-data staleness, drawdown. Each control DETECTS from observed state and
  latches `engaged`, blocking subsequent orders until an explicit operator reset.
- **`run_kill_switch_drills()` no longer returns hardcoded `True`** — it delegates
  to `run_risk_kill_switch_drills()`, where each drill injects an adverse
  condition, proves the detector fires (`observed > limit`, real numbers),
  proves a clean negative control does NOT fire, and proves the next order is
  halted. There are no `engaged=True` literals.
- **Reconciliation mismatch now ENFORCES** — `reconcile()` trips the governor, and
  `submit()` is a pre-trade gate that refuses orders while engaged. The "block"
  is no longer a flag nobody reads. (`test_reconciliation_mismatch_actually_blocks_next_order`.)
- **Verification**: 21/21 capital_lab tests pass (8 risk-governor incl. the
  anti-theater `test_kill_switch_drills_are_real_not_hardcoded`, 8 membrane incl.
  2 new enforcement tests, 5 alpha). ruff F-checks clean. Proof loop regenerated:
  every drill `real_detection=True`; `score=80.0`, `live_readiness=0`,
  `clean=False`, `external_broker_paper_evidence=False` all preserved.

Still pending (next increments, by design): price field on `OrderState`/snapshot
for price-drift reconciliation; duplicate-economics-mismatch guard; wiring fills
into the governor for live position/exposure tracking; then the research-informed
sophistication layer (VaR/CVaR, 15c3-5 pre-trade controls, deflated-Sharpe on the
Goal A alpha side).

> No live orders placed, no live keys read, no profit or live-readiness claim made.
