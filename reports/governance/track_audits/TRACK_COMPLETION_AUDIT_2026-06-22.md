# Track Completion-Claim Audit — 2026-06-22

**Mandate (operator):** have three high-level agents/models seriously, at an
audit level, critically review each active track's **completion claims**.

**Method.** Three independent auditors on different model families
(`audit-opus`, `audit-sonnet`, `audit-haiku`) each examined all 7 active
tracks **criterion by criterion**, opening the referenced code/tests and
running them where useful, and classified every completion criterion as:

- **SUBSTANTIVE** — passing genuinely proves the capability
- **PROXY** — green only proves a file/string exists; capability not established
- **GAMED** — the check passes tautologically (e.g. grep a word in the doc that names it)
- **FALSE** — the claim does not hold even at face value (missing file, failing test, non-reproducible receipt)

Each issued a per-track audit opinion: **CLEAN / QUALIFIED / ADVERSE / DISCLAIMER**.
Raw attestations: `reports/governance/track_audits/audit-{opus,sonnet,haiku}.audit.json`.

> Fable 5 was unavailable this run; the third seat used opus. Decorrelation
> still held: opus/sonnet audited adversarially, haiku more leniently — the
> disagreement is visible below and is the point.

---

## Opinion matrix

| Track | opus | sonnet | haiku | Consensus | Claim holds? |
|---|---|---|---|---|---|
| `runtime-truth-reconciliation` | CLEAN | CLEAN | CLEAN | **CLEAN** | ✅ unanimous |
| `provider-routing-consolidation` | QUALIFIED | QUALIFIED | CLEAN | **QUALIFIED** | ✅ unanimous (holds) |
| `truth-graph-platform` | QUALIFIED | QUALIFIED | CLEAN | **QUALIFIED** | ⚠️ 2/3 say live-NATS proof unearned |
| `runtime-truth-nats` | ADVERSE | ADVERSE | ADVERSE | **ADVERSE** | ❌ unanimous |
| `runtime-truth-spine-adoption` | ADVERSE | ADVERSE | QUALIFIED | **ADVERSE** | ❌ unanimous (claim false 3/3) |
| `loop-closure` | ADVERSE | ADVERSE | QUALIFIED | **ADVERSE** | ❌ unanimous (claim false 3/3) |
| `composer-holon-spine-longrun` | DISCLAIMER | ADVERSE | QUALIFIED | **ADVERSE/DISCLAIMER** | ❌ unanimous (not clean) |

**Bottom line.** The file-grade reports **5/7 SHIPPABLE**. The audit finds only
**2 tracks whose completion claims genuinely hold** (reconciliation,
provider-routing), **1 real-but-unearned** (truth-graph: code is real, the
live-NATS proof is pre-staged), and **4 whose completion claims do not hold**
(nats, spine-adoption, loop-closure, composer-holon).

---

## Systemic finding — the grader is gameable

Across tracks the auditors independently identified the same root cause: the
completion gate (`check_track_status.py`) is `file_exists` / `file_contains`.
Concrete instances where green ≠ done:

1. **Tautological grep** — `nats_transport_landed` greps `"NATS"` inside a file
   named `NATS_SUBSTRATE_MASTER_SPEC.md`. Cannot fail. (GAMED, all 3 auditors)
2. **File-exists over a "NOT DONE" body** — `loop1_closure_receipt_exists` is
   green while the receipt's own text reads **`VERDICT: NOT CLOSED`**. (GAMED/PROXY)
3. **Import-line over dead imports** — spine-adoption's `*_calls_spine` criteria
   pass on imports that are placeholders / behind a default-OFF flag;
   `agent_runner.run_task()` never calls `invoke_agent`. (PROXY, opus+sonnet)
4. **Missing owned surfaces** — nats declares `a2a_nats_contact.py` /
   `a2a_core_contact.py` as owned surfaces; **neither file exists**. (FALSE, all 3)
5. **Operator-machine-only proof** — `gate1_witnessed`, `composer_wake_witness`,
   readiness packets cite `/Users/dhyana/...`; not reproducible from the repo. (DISCLAIMER)

**Recommendation:** convert these specific proxies to content/witness checks —
e.g. assert `VERDICT: CLOSED` (not file existence), assert the bypass dict is
literally empty (already done for `bypass_allowlist_empty`, which honestly
fails), assert owned-surface files exist, and require a repo-checkable receipt
hash rather than an operator-path narrative. This is exactly the gap the
sign-off-gated `track_health_grade.py` quorum was built to cover.

---

## Per-track audit

### `runtime-truth-reconciliation` — CLEAN ✅ (close it)
Unanimous. 11/11 criteria substantive or appropriate regression guards. Real
frozen read-model with an authority guard (`__post_init__` rejects
`is_authoritative=True`), 23-value axis enum, SHA-256 no-write test, and a
real-SQLite A2A single-persistence test. **No material gaps — operator may close.**

### `provider-routing-consolidation` — QUALIFIED ✅ (claim holds)
Unanimous that the claim holds. The keystone is genuinely fixed:
`provider_policy` reads `context['preferred_provider']`, pins it at chain
position 0, and short-circuits re-ranking; `power_first` default sorts by
intelligence; `ZhipuProvider` is fully wired (enum → class → factory → default).
**Qualification:** the two rank systems still coexist (power-first overrides at
routing time but the old `_PROVIDER_RANK` was not deleted — honest, documented);
no e2e test proves the *production* call path exercises the new selection; Stage
5 drift cleanup deferred. Closeable for declared scope; add an e2e production-path
test and schedule Stage 2/5 as follow-on.

### `truth-graph-platform` — QUALIFIED ⚠️ (real code, unearned NATS proof)
Implementation is genuine and tested (22/22): receipt gate with on-disk
quarantine, agent-presence RED/GREEN staleness, orientation packet,
`write_repo_context` idempotency. **Material exception:** the committed
`reports/orientation/nats_e2e_receipt.json` was hand-authored in the same PR
(commit 936d365), not generated by a live broker; the demo fails
connection-refused here, and both BLOCKER next_items remain open. **To close:**
run a live NATS broker, regenerate the receipt for real, clear the two blockers.

### `runtime-truth-nats` — ADVERSE ❌ (claim does not hold)
Unanimous ADVERSE. Both declared owned-surface modules
(`a2a_nats_contact.py`, `a2a_core_contact.py`) **do not exist**. The only
non-trivial criterion is a tautological grep. Real NATS code lives *outside*
the track's surfaces and its `consume_message` is itself a spine bypass. The
sole next_item — the entire deliverable — is openly unfinished. **To close:**
create/repoint the contact surfaces, wire them into dispatch with receipts,
add a real round-trip criterion against a test broker.

### `runtime-truth-spine-adoption` — ADVERSE ❌ (the keystone; claim false)
Claim "every production dispatch flows through `invoke_agent`" is false:
orchestrator spine dispatch is **default-OFF** (`DHARMA_SPINE_DISPATCH=1`),
`agent_runner.run_task()` never calls `invoke_agent` (the import is a
placeholder), and **5 live bypasses remain** (the `bypass_allowlist_empty`
criterion honestly FAILS — this is the 7/8). Only `a2a_bridge.submit_via_spine`
is genuinely wired. GATE 1 evidence is operator-machine-only. **To close:** wire
the trishula path + agent_runner, flip the default ON, drain the allowlist to
`{}`, and add a default-path receipt test.

### `loop-closure` — ADVERSE ❌ (1 of 13 loops, and that one says NOT CLOSED)
`LOOP1_CLOSURE_RECEIPT.md` literally records `VERDICT: NOT CLOSED` (proof wrote
to a sandbox DB, not canonical `runtime.db`) while the criterion is green on
file existence. Loops 2–11 PARTIAL with no closure receipts; 12–13 BLOCKED
behind the One-Wire quorum; Phase 1a and the real provider key are open
blockers; `RETROSPECTIVE.md` is missing. Most passing criteria concern the
`cybernetics_codex` persona (`declared_not_started`), orthogonal to "wire 13
loops." **To close:** close Loop 1 against canonical DB, wire the cascade with
real receipts, write the retrospective, and assert receipt *content* not existence.

### `composer-holon-spine-longrun` — ADVERSE / DISCLAIMER ❌
The substrate is real in-repo (`holon_runtime.py`, `test_holon_bridge.py`
29 pass, `test_holon_runtime.py`). But all 4 declared blockers remain open per
the track's **own** documents: the readiness packet self-states it is "a
confidence-lift packet, not a launch receipt"; the wake witness is one-shot and
lives on `/Users/dhyana/`; `living_agent_kernel` import is unresolved; the lane
is not reconciled to GitHub main. `holon_runtime` uses a plain Callable — no
`invoke_agent`, so the `depends_on: spine-adoption` is not enforced in code.
**To close:** publish a PASSED verifier output, fix the import, prove
repo-verifiable unattended wakes, wire through `invoke_agent`, reconcile to main.

---

## Recommended disposition

- **Close now (claims hold):** `runtime-truth-reconciliation`, `provider-routing-consolidation`.
- **Hold pending a small, named proof:** `truth-graph-platform` (one real NATS round-trip).
- **Do NOT close on file-grade — material work remains:** `runtime-truth-nats`,
  `runtime-truth-spine-adoption`, `loop-closure`, `composer-holon-spine-longrun`.
- **Harden the gate:** replace the 5 gameable proxies named above with
  content/witness checks; this is the same gap `make track-health` (the
  sign-off quorum) now covers as a backstop.
