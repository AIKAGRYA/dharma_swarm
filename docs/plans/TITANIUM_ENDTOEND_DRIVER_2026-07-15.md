# Titanium End-to-End Driver — the long-running executor prompt

**Doc role (per `docs/AGENTS.md`):** `working_plan` — the durable, self-contained
execution driver for taking Titanium from PREP-ONLY to a truthfully-green Phase 0.
Subordinate to `docs/plans/TITANIUM_GRADE_REPOSITORY_HARDENING_2026-07-10.md` (the
spec) and `docs/governance/ACTIVE_TRACK.yaml` (the live ledger). Any session can
execute this by reading it top-to-bottom and running the **Driver protocol** below.

**Author seat:** fable_claude_code. **Created:** 2026-07-15.
**Operator mandate (2026-07-15):** "do it all, finish end to end; create a
long-running prompt to execute it." This doc + the recurring Routine that fires it
are that mechanism.

---

## The goal

Titanium's north star: **`main` truthfully green from a clean clone** (spec:19,
spec:292). Titanium implementation (WP-00 → Phase 0 packets) cannot begin until the
`onboard-one-door-2026-07` track graduates — which, per operator decision D-T1
(`TITANIUM_WP00_ADMISSION_DRAFT_2026-07-15.md`), is *also* what frees the WIP slot
Titanium needs. So the entire near-term job reduces to: **graduate onboard-one-door.**

## Two hard locks only the operator can open (the driver holds here)

No automation, no agent, and no amount of cleverness passes these. State them every
firing until they clear:

1. **Administration:read grant** — until provisioned, C1's live branch-protection
   parity is `NEEDS_HOST` (spec:1416). The driver assembles everything hermetic; the
   live comparison waits on this grant.
2. **D2 ratification record** — operator-authored strict-by-default record
   (spec §9.2). The spec explicitly forbids the implementation author from minting it;
   WP-O5 preflight verifies it is a merged ancestor. The driver prepares the *template*
   and the preconditions, but the operator writes and merges the record.

A third structural fact: **no agent self-merges.** Every PR the driver opens is a
draft; operator/Merge-Master-Mike authority merges.

## The unified critical path (dependency order)

From `ACTIVE_TRACK.yaml` 1909-1912:
**C1 → D2 → WP-O5; (WP-O5 + M6-1) → WP-O6 → TERMINAL-PROOF → onboard graduates →
Titanium WP-00 admits → Phase 0 packets (WP-0S,0A,0B,0C1R,0C1,0C2,0D,0E,0F1,0F2,0G,0H)
→ WP-0I clean-room proof → Phase 0 exit.**

| # | Item | Owner | Driver can advance? | Blocked on |
|---|---|---|---|---|
| 1 | **C1** — strict door fails closed (required-context/parity/automerge/merge-queue) | merge authority | **Partly — hermetic evidence assembled (below)** | Admin:read (live leg) + merge authority captures merge-queue evidence |
| 2 | **D2** — strict-by-default ratification | **operator only** | No — prepare template only | operator authors + merges; needs C1 first |
| 3 | **WP-O5** — promote strict exits to default | onboard-one-door owner | No (cross-track code) | C1 + merged D2 |
| 4 | **M6-1** — mutmut/`pyproject.toml` config | **DharmaGraph owner** | No (cross-track) — prepare proposed config only | DharmaGraph owner lands it or transfer merges |
| 5 | **WP-O6** — terminal-envelope proof | onboard-one-door owner | No (cross-track code) | WP-O5 + M6-1 |
| 6 | **TERMINAL-PROOF** — independent §13 proof on sterile clone | **this seat qualifies** (authored none of WP-O1..O6) | **Yes — but LAST** | WP-O6 merged |
| 7 | **WP-00 admission** | operator + owners | Materials ready (`TITANIUM_WP00_ADMISSION_DRAFT_2026-07-15.md`) | onboard graduated; D-T2 enactment |
| 8 | **Phase 0 packets** | new hardening track + owners | Design ready (WP-0A/0S notes; findings re-verified) | WP-00 merged |

Reality: **items 3–8 cannot start until D2 clears (item 2), which needs C1 (item 1),
whose live leg needs Admin:read.** The chain is operator-gated at the front. Opening
the two locks cascades everything.

---

## C1 hermetic-evidence packet (assembled 2026-07-15, read-only)

What the strict onboarding door + CI authority provably do **without** admin access:

- **Structural parity aligned** — `python3 scripts/governance/check_ci_parity.py
  --allow-missing-live` → **exit 0** ("OK (structure aligned)"). Every manifest
  required-context maps to a real producing job whose effective name matches, and the
  false-green defenses (job-level `continue-on-error`, regression-sensitive step
  `continue-on-error`, merge_group self-skip) are checked.
- **Automerge consumes the manifest as SSOT** — `.github/workflows/automerge.yml:100-122`
  loads `scripts/governance/ci_parity_manifest.json` at runtime via `jq`, validating
  schema `ci-parity-guard/v1`, non-empty `required_contexts`, and context uniqueness.
  No private hardcoded list (confirms the TIT-007 consolidation half).
- **Onboarding admission parity context is registered and regression-sensitive** —
  `scripts/governance/ci_parity_manifest.json:38-41` (`context: "Onboarding admission
  parity"`, `job: onboarding-admission`, `regression_sensitive: true`). This is the C1
  ledger claim, confirmed.

What C1 still needs (the gated remainder):

- **Live branch-protection comparison** — `check_ci_parity.py --live` needs
  Administration:read (operator lock #1). Until then the committed manifest cannot be
  proven equal to enforced branch protection.
- **Merge-queue evidence** — the parity check flags a **dead-trigger**:
  `.github/workflows/coherence-delta.yml:14` subscribes to `merge_group` but every job
  self-skips on it (`:43-44`, `github.event_name != 'merge_group'`). This is *allowed*
  today only because Coherence Delta is `regression_sensitive: false`; the
  regression-sensitive `onboarding-admission` context must be confirmed to actually run
  in the merge queue (not self-skip) for C1 to prove the strict door fails closed on
  blocked truth. Capturing that is merge-authority's evidence step.
- **The `advisory`-vs-`required` contradiction** (TIT-007): `pytest (3.11)`,
  `pytest (3.12)`, `gitleaks` are `required` in the parity manifest but `advisory` in
  `docs/governance/CI_TRUTH_CONTRACT.json`. C1 (and WP-0F1 later) must reconcile these
  two committed surfaces to one required set before the live parity can be trusted.

**C1 verdict:** hermetic foundation GREEN; closure blocked on Admin:read (operator) +
merge-authority merge-queue capture. Reproduce the hermetic evidence with the commands
cited above.

---

## Driver protocol (run this every firing)

Read `make onboard` state, then walk the chain. For each firing:

1. **Refresh state** — `git fetch origin main`; regenerate the projection with
   `python3 scripts/governance/check_track_status.py`; `make onboard`.
2. **Re-read the six gate items** — `sed -n '2013,2036p' docs/governance/ACTIVE_TRACK.yaml`.
   Record which are still `blocker: true`.
3. **Watch open PRs** — check CI + review comments on any open Titanium-lane PR
   (currently #952). Fix small/confident CI failures; ask on ambiguity; skip no-ops.
4. **Advance the front actionable item:**
   - If **Admin:read is now provisioned** → run `check_ci_parity.py --live`, capture
     the live parity result, and assemble the complete C1 evidence packet for merge
     authority. Reconcile the required/advisory contradiction as a proposed change
     (draft PR under the CI-authority surface owner — do not self-merge).
   - If **D2 record is merged** → verify it's a merged ancestor, then the onboard-one-door
     owner (or operator-reassigned seat) may proceed to WP-O5.
   - If **WP-O6 is merged** → this seat runs TERMINAL-PROOF: sterile fresh clone, bind
     the exact final candidate, run §13, post receipts, open the proof PR.
   - If **onboard-one-door has graduated** (status closed / all six items cleared) →
     enact WP-00: the D-T2 organism-rewire ownership extension and the
     `repository-titanium-hardening-2026-07` admission entry (materials already drafted),
     capture the fresh baseline, run `render_active_track_includes.py --check` +
     track-status checker, open the admission PR.
   - If **WP-00 is merged** → begin Phase 0 packets in dependency order
     (WP-0S → 0A → 0B → 0C1R → 0C1 → 0C2 → 0D → 0E → 0F1 → 0F2 → 0G → 0H → 0I), one
     bounded PR per owner, failing-first contract test, finding id, rollback. **Re-verify
     TIT-002 by re-bisecting before touching `build_engine.py`** (it drifted — see
     `TITANIUM_PREP_2026-07-15.md`).
5. **Surface operator locks** — if either lock is still closed, state the exact ask
   (Admin:read grant; D2 record) plainly. If nothing changed since last firing and no
   PR needs attention, **re-arm silently — do not message the operator**.

## Bounded mandate (safety rails — do not cross)

- **Never self-merge.** Every change is a draft PR; operator/Mike authority merges.
- **Never mint D2** or any operator-reserved ratification. Prepare templates only.
- **Respect track ownership.** Do not autonomously rewrite `onboard-one-door` code
  (WP-O5/WP-O6) or DharmaGraph's `pyproject.toml` (M6-1) unattended — those need their
  owner or an explicit operator reassignment. Prepare proposals; coordinate.
- **No unbounded rewrite** (spec contract). One finding, one owner, one bounded PR.
- **Citation-or-silence.** Every claim carries `file:line` or a runnable command.
- **Strict admission door.** Governance/onboarding-surface PRs need a Session Entry
  Packet, exact-base custody, bare-`python3` gate commands, no forbidden/allowed overlap.

## Stop conditions

Stop the recurring Routine when any holds:
- Phase 0 exit gate passes on merged `main` (mission complete), **or**
- the operator says stop, **or**
- the chain is fully blocked on the two operator locks with no PR needing attention
  (then it just re-arms quietly and waits — it does not spam).

---

## The two asks, restated for the operator (front of the chain)

1. **Grant Administration:read** on the repo (one-time GitHub settings action) →
   unblocks C1's live branch-protection parity.
2. **Author the D2 strict-by-default ratification record** (after C1) → unblocks WP-O5
   and everything downstream.

Everything else the driver carries. These two are yours alone.
