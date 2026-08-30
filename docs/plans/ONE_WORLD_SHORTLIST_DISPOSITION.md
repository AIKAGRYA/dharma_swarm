---
role: report
date: 2026-08-30
status: FINAL — disposition recommendations only; deletion is a separate operator act
supersedes: nothing; subordinates to docs/plans/ONE_WORLD_2026-08-30.md
world:
  commit: a9282490d (tag one-world/2026-08-30) · host: Mac · branch: docs/one-world-sync-2026-08-30
---

# ONE WORLD — stranded shortlist disposition (metabolize-or-compost)

Read-only adjudication of the four lines left open by the unification
(#1493 `d86b7bf21`, tag `one-world/2026-08-30` = `a9282490d`). Method: `git
cherry`, ancestry, path-presence and diff inspection against `origin/main`.
No refs were created, moved, or deleted.

**Global caveat:** #1493 was a *squash* merge (single parent `fd4116fe`).
`git merge-base --is-ancestor` and patch-id equivalence are therefore N/A
for everything the unification absorbed; all "on main?" claims below are
content/path-based, matching the S2 verification convention already recorded
in `docs/plans/ONE_WORLD_2026-08-30.md`.

## 1. `feat/rsi-lab` — 59 commits ahead (tip `d98a6fb90`, 2026-07-04) — **COMPOST**

- (a) Unique content: the *original* July-04 RSI-lab prototype — 17
  `forge_v1/forge_v2/` modules absent on main (`scheduler.py`,
  `packet_guard.py`, `grade_queue.py`, `native_runner_contract.py`,
  `canonical_receipt.py`, `e4_discrimination.py`, `phase4_alpha.py`,
  `scaffold_variants.py`, `rsi_conductor.py`, `spine_loop.py`,
  `darwin_bridge.py`, …), 14 matching tests, plus July-02..04 receipts
  (`reports/governance/rsi_lab_repair_receipt_2026-07-02.md`,
  `reports/forge_rsi_lab/megha_pr_suite_controlsplit_auth_*/closeout.json`).
  `git cherry` shows 59/59 patch-unique vs main **and** vs
  `rsi-lab/canonical` — but that is because the canonical lineage was a
  deliberate *rebuild* (started 2026-07-15), not a continuation.
- (b) Verdict: **COMPOST** — superseded by the canonical RSI lineage
  adjudicated in `docs/plans/ONE_WORLD_M-1_CUSTODY.md` §1 and merged via
  **#1493 (`d86b7bf21`)**. Main now carries the functional successors:
  `forge_v2/taskbed_*`, `pr_suite_*`, `promote.py`/`verify_promotion.py`,
  and the `forge_lab/unattended_*` operations core. The branch is preserved
  immutably at `origin/estate/feat-rsi-lab` (identical tip `d98a6fb90`).
- (c) Already stale-listed in `docs/state/BRANCH_TTL_REGISTER.md` (59 ahead /
  671 behind at generation). Deletion is a separate operator act.
- Preserve-before-delete: nothing outside git. Local
  `~/.dharma/rsi-lab/receipts/` (39 files) all belong to the *canonical*
  lineage (2026-07-15 → 2026-08-28, incl. the `b148f55e` release receipt) —
  that lineage is merged; receipts unaffected by this branch's deletion.
  The branch-local July receipts stay reachable via the estate ref.

## 2. `rsi-worldclass-harness` (`origin/codex/rsi-worldclass-harness-20260810`, 27 commits, tip `4ac37e5bd`) — **COMPOST**

- (a) 24 of 27 commits are patch-equivalent to `rsi-lab/canonical`
  (already on main via #1493); `e9de1c727` is merge glue. Exactly **3
  unique commits**: `91be6a17f` + `4ac37e5bd` (fail-closed governed
  campaign controller: `forge_lab/campaign_*` ≈15 files, `paired_evaluation`
  /`paired_statistics`, `provider_attestation*`, `champion_store`,
  `pr_suite_execution*`, systemd units) and `9021f7ea8` (governance track
  opening). None of these files exist on main.
- (b) Verdict: **COMPOST** — the work packet on the branch itself
  (`reports/agentops/work_packets/rsi-worldclass-harness-WP-O99.json`)
  defines the harness as *shadow-only, disabled-by-default, never to run
  unattended while canaries are red*; it never ran. The reviewed, receipted
  successor for governed unattended campaigns — the `unattended_*` core
  (#1435, #1454–#1476) plus `campaign_control.py` — landed via **#1493
  (`d86b7bf21`)** and produced receipts through 2026-08-28. Preserved
  immutably at `origin/estate/codex-rsi-worldclass-harness-20260810`
  (identical tip). Salvage note: paired A/B evaluation + provider
  attestation have no main equivalent; if ever wanted, re-cut fresh from
  the estate ref — the branch itself is unmergeable (237k deletions stale
  vs main).
- (c) Not in the TTL register (register surveys local branches only; this
  line exists as remote refs). Deletion is a separate operator act.
- Preserve-before-delete: nothing outside git; WP-O99 and all code persist
  on the estate ref.

## 3. The sadhana stack (66 local `agent/sadhana-*` + 2 `backup/sadhana-*` + 7 origin branches) — **NEEDS-OWNER**

All unmerged; main contains **zero** sadhana paths. One campaign
(2026-08-23 → 08-27), clustered:

| Cluster | Refs | Content |
|---|---|---|
| C1 base hardening | `origin/agent/sadhana-integration-parent-20260825` (`e1d7c629b`, 72 ahead) | mission-control / dispatch / TaskBoard / crash-replay hardening; 0/6 spot-checked subjects exist on main — unique but interleaved and 5 days stale |
| C2 fenced candidate | `origin/agent/sadhana-vps-mobile-release-20260825` (`099668537` = C1+1) | `deploy/sadhana/` R1 candidate |
| C3 R2 + retirement | `origin/agent/sadhana-vps-mobile-release-r2-truthfix-final-20260826` **and** `origin/agent/sadhana-10day-retirement-20260827` (same tip `4c740a9e5`, 102 ahead) | R2 deployment, SSH custody chain, crash-safe standby retirement, `terminal/` mobile app (61 files) |
| C4 PR head | `origin/agent/sadhana-10day-retirement-final-20260827` (`3a3fab45f`, 104 ahead) | restacked C3; head of **draft PR #1453 — OPEN, CONFLICTING, untouched since 2026-08-27** |
| C5 clean restacks | `origin/agent/sadhana-10day-retirement-clean-20260827` (`9aa3d9301`, 1 commit) and `origin/agent/sadhana-10day-retirement-runtime-main-20260827` (`b13f629a5`, 3 commits, newest 2026-08-27 23:32 JST) | the entire release lane as main-based commits: fail-closed release + secure snapshot retirement + seal refresh |

The 66 local branches (52 distinct tips) are the campaign's working
history; intermediates may contain abandoned iterations not in the final
restacks and persist only while refs exist.

- (b) Verdict: **NEEDS-OWNER.** The lane is deliberately unpromoted and
  time-bounded by design (`deploy/sadhana/README.md`: "not an authority
  source"); main's `ACTIVE_TRACK.yaml` holds track
  `sadhana-10-day-program-2026-08` as **ACTIVE** (opened 2026-08-27,
  `ttl_days: 10` → TTL 2026-09-06, `target_closure_kind: CLOSED_NOT_PROD`),
  and retirement was mid-flight when work stopped. Landing the C5 restack
  vs closing the track un-landed depends on live host state
  (meghadharma-cloud `/var/lib/dharma-sadhana`, agni-openclaw) that code
  cannot adjudicate. If the owner closes it: COMPOST everything, with the
  C1 hardening subset flagged as the only re-extractable residue.
- (c) Not in the TTL register (tips 2026-08-27, inside the 14-day window at
  generation). Deletion is a separate operator act.
- **Preserve-before-delete (required):**
  1. The track's claim boundary names the preserved package at
     `/Users/dhyana/ds_sadhana_10day_release_final_20260827` — **that
     directory no longer exists** (only
     `ds_sadhana_mobile_control_isolated_20260823` does). The branch tips
     are now the *only* complete copy of the final release package; the
     ACTIVE_TRACK claim is stale and must be corrected either way.
  2. Host-side retirement/receipt state on the two VPS hosts was never
     captured to git — snapshot it before any ref deletion.
  3. Local `~/.dharma` holds only two scratch temp dirs
     (`sadhana-dashboard-generated.*`, `sadhana-unit-verify.*`) — nothing
     to preserve on this Mac. Branch-local work packets
     (`reports/agentops/work_packets/*SADHANA*`) are in git and safe while
     refs exist.

## 4. `integrate/chetana-grand-memory` (tips `4c70456ef`; Mac variant `c509d4e8`) — **NEEDS-OWNER**

- (a) The grand-memory *core* is superseded — main's `dharma_swarm/chetana/`
  is newer and larger (#1135 `ce2ea955f` et al.). Unique residue:
  - The **Plan v3 component suite** (both tips): 10 modules absent on main
    (`causal_ledger.py`, `witness_resolver.py`, `drift_monitor.py`,
    `welfare_attribution.py`, `autoresearch_history.py`,
    `r_repair_metric.py`, `casebook_mine.py`, `render_repair_briefing.py`,
    `register_disciplines.py`, `.dharma_protected_ids.jsonl`), 12 test
    files, and `tests/adversarial/dharma_laundering/` cases. No main
    reference to any of these exists — never landed, never retired.
  - **Mac variant only** (`c509d4e8`, = integrate tip − 2 tiny fixes + 8
    commits): `ptr_integrity.py`/`ptr_metric.py` +
    `PTR_CYBERNETIC_LOOP_SPEC.md`, `SHAKTI_ACTION_AUTHORITY_CONTRACT.md`,
    `SUBSTRATE_NATIVENESS_RUBRIC.md`, `STATE_DIR_OWNERS.md`, chetana hook
    lifecycle hardening, memory-gate honesty fixes. Main references
    *substrate-nativeness* as a concept (`ACTIVE_TRACK.yaml`) but none of
    these artifacts exist on main.
- (b) Verdict: **NEEDS-OWNER.** **PR #59 was CLOSED UNMERGED 2026-05-21** —
  the nearest thing to a retirement decision, but undocumented. The core is
  compost by supersession; the Plan v3 suite + Mac-variant governance
  contracts are tested, substantial work whose value is undecidable from
  code alone. If the owner declines: COMPOST with an explicit retirement
  note citing PR #59's unmerged close.
- (c) The local branch `integrate/chetana-grand-memory-2026-05-02` (tip
  `c509d4e8`, the Mac variant) is already stale-listed in
  `docs/state/BRANCH_TTL_REGISTER.md`. Deletion is a separate operator act.
- Preserve-before-delete: nothing outside git. `~/.dharma/chetana` and
  `~/.dharma/campaign_chetana` on this Mac belong to main's chetana lineage.

## Tally

| Line | Verdict | Superseding / deciding evidence |
|---|---|---|
| `feat/rsi-lab` (+59) | COMPOST | canonical rebuild → #1493 `d86b7bf21`; preserved at `origin/estate/feat-rsi-lab` |
| `rsi-worldclass-harness` (+27) | COMPOST | 24/27 already on main via #1493; unique 3 superseded by the merged `unattended_*` core; preserved at `origin/estate/codex-rsi-worldclass-harness-20260810` |
| sadhana stack (73 branches) | NEEDS-OWNER | live VPS host state + open draft PR #1453 + ACTIVE track with stale preservation claim |
| `integrate/chetana-grand-memory` (+27) | NEEDS-OWNER | core superseded by main's chetana; Plan v3 suite + Mac-variant contracts never adjudicated; PR #59 closed unmerged 2026-05-21 |

*World locus: commit `a9282490d` (tag `one-world/2026-08-30`) · host Mac ·
branch `docs/one-world-sync-2026-08-30`. Advisory only: register listing
and this report are not deletion verdicts; evidence-gated cleanup belongs to
`scripts/governance/branch_janitor.py` and the operator.*
