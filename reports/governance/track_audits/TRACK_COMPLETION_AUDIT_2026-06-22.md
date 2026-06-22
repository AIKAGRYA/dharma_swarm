# Track Completion-Claim Audit — 2026-06-22 (Opus 4.8 panel)

**Mandate (operator):** three high-level models seriously, at an audit level,
critically review each active track's **completion claims**.
**Reviewer policy (operator):** Opus 4.8+ caliber only — see
`docs/governance/TRACK_REVIEW_PROTOCOL.md`.

**Method.** Three **independent Opus 4.8 runs** (`opus-run-A/B/C`) each examined
all 7 active tracks **criterion by criterion**, opening the referenced
code/tests and running them, and classified each completion criterion as
SUBSTANTIVE / PROXY / GAMED / FALSE with a per-track opinion
(CLEAN / QUALIFIED / ADVERSE / DISCLAIMER) plus a 5-axis health grade.
Decorrelation comes from independent runs at the same high tier, per policy.
Raw attestations: `track_audits/opus-run-{A,B,C}.audit.json` and
`track_signoffs/opus-run-{A,B,C}.signoff.json`.

> This supersedes the earlier mixed-panel (opus+sonnet+haiku) run; under the
> Opus-4.8+ policy the lighter models no longer carry a vote. Their receipts
> were retired (git history preserves them).

---

## Opinion matrix (3 independent Opus 4.8 runs)

| Track | run A | run B | run C | Consensus | Claim holds? | Quorum grade |
|---|---|---|---|---|---|---|
| `runtime-truth-reconciliation` | QUALIFIED | CLEAN | QUALIFIED | **QUALIFIED** | ✅ 3/3 | **D · attested SHIPPABLE** |
| `provider-routing-consolidation` | CLEAN | CLEAN | CLEAN | **CLEAN** | ✅ 3/3 | **D · attested SHIPPABLE** |
| `truth-graph-platform` | QUALIFIED | QUALIFIED | QUALIFIED | **QUALIFIED** | ❌ 3/3 | F · OVERSTATED |
| `runtime-truth-nats` | ADVERSE | ADVERSE | ADVERSE | **ADVERSE** | ❌ 3/3 | F · OVERSTATED |
| `runtime-truth-spine-adoption` | QUALIFIED | QUALIFIED | QUALIFIED | **QUALIFIED** | ❌ 3/3 | F · IN_PROGRESS (7/8) |
| `loop-closure` | ADVERSE | ADVERSE | ADVERSE | **ADVERSE** | ❌ 3/3 | F · IN_PROGRESS (10/11) |
| `composer-holon-spine-longrun` | DISCLAIMER | DISCLAIMER | QUALIFIED | **DISCLAIMER** | ❌ 3/3 | F · OVERSTATED |

**Portfolio: F (46.4)** — track-mean 46.4, objective coverage 0.33 (cap 84.9).
**Attested SHIPPABLE (close):** reconciliation, provider-routing.
**OVERSTATED (file-green, panel withholds):** nats, truth-graph, composer-holon.

The three independent Opus 4.8 runs agreed on the audit opinion for **6 of 7
tracks** (the lone split: composer-holon, where run C said QUALIFIED vs
DISCLAIMER — all three still agree the claim does **not** hold).

---

## Systemic finding — the gate is gameable (unanimous)

All three runs independently flagged the same proxy/gamed/false criteria where
file-grade green ≠ capability done:

1. **Tautological grep** — `nats_transport_landed` greps `"NATS"` inside
   `NATS_SUBSTRATE_MASTER_SPEC.md`. (GAMED, 3/3)
2. **Missing owned surfaces** — nats declares `a2a_nats_contact.py` /
   `a2a_core_contact.py`; neither exists. (FALSE, 3/3)
3. **File-exists over a "NOT CLOSED" body** — `loop1_closure_receipt_exists`
   is green while the receipt reads **`VERDICT: NOT CLOSED`**. (GAMED/FALSE, 3/3)
4. **Import-line over a dead import** — `agent_runner_calls_spine` passes on an
   `invoke_agent` import that `run_task` never calls; orchestrator dispatch is
   default-OFF behind `DHARMA_SPINE_DISPATCH`. (PROXY/GAMED, 3/3)
5. **Operator-machine-only proof** — `gate1_witnessed`,
   `composer_wake_witness_pending` cite `/Users/dhyana/...`; not reproducible. (3/3)

**Recommendation:** convert these to content/witness checks — assert
`VERDICT: CLOSED` not file existence; assert the bypass dict is literally `{}`
(already done — it honestly fails); assert owned-surface files exist; require a
repo-checkable receipt hash, not an operator-path narrative. The
sign-off-gated `make track-health` quorum already backstops this.

---

## Recommended disposition

- **Close now (Opus 4.8 panel attests, claim holds):**
  `runtime-truth-reconciliation`, `provider-routing-consolidation`.
- **Hold for one named proof:** `truth-graph-platform` — one live NATS
  round-trip (replace the hand-authored receipt); strong code otherwise.
- **Do NOT close — material work remains (claim fails 3/3):**
  `runtime-truth-nats` (build/repoint the contact modules),
  `runtime-truth-spine-adoption` (wire agent_runner, default the flag, drain
  the allowlist), `loop-closure` (close Loop 1 on the canonical DB, write the
  retrospective), `composer-holon-spine-longrun` (repo-verifiable wakes,
  reconcile to main).
- **Harden the gate:** replace the 5 gameable proxies above with
  content/witness checks.
- **Rebalance the spine:** all 7 tracks serve `substrate-nativeness`; open a
  track on `revenue-external-humans-served` and `research-depth` (both at zero).
