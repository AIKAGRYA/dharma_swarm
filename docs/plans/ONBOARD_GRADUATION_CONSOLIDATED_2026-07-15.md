# Onboard-One-Door Graduation — Consolidated Status, Audit & Operator Punch-List

**Doc role (per `docs/AGENTS.md`):** `working_plan` — the single consolidated
status for graduating `onboard-one-door-2026-07` (which frees the WIP slot and
clears the Titanium gate, per operator decision D-T1, 2026-07-15). Subordinate to
`docs/plans/ONBOARD_ONE_DOOR_HARDENING_SPEC_2026-07-10.md` (detail authority) and
its closure spec `ONBOARD_ONE_DOOR_CLOSURE_SPEC_2026-07-14.md` (in PR #946). This
document implements nothing and mints no operator record.

**Author seat:** fable_claude_code. **Date:** 2026-07-15. Citation-or-silence throughout.

---

## TL;DR — the graduation is 2 operator actions away from cascading

Everything that can be done by an agent is done or staged. The two remaining
front-of-chain gates are **operator-only by design** — they exist so the strict
onboarding door cannot be faked, including by me:

1. **Merge PR #946** (audited sound below) — the green closure lane.
2. **Author the D2 record + grant Administration:read** — the two things no agent
   can produce (D2 is an operator ratification; Admin:read is a repo-admin grant).

Do those and the rest (WP-O5 → WP-O6 → terminal proof → closure flip) cascades,
with this seat driving every non-operator step.

---

## 1. The two competing PRs — reconciled (no decision needed from you)

Diffed both branches at `origin/main` (`aefa10d`):

- **PR #946** (`e89c4ac`, clean/green) touches **only the `completion_criteria`
  block** of the track entry (+32 lines, **0 deletions**) — adds 3 `commit_on_main`
  + 2 `test_passes` rigorous criteria + a truthful `timeout_s: 360` raise.
- **PR #932** (`73b340`, dirty) touches **only the `next_items` block** — the
  controller restructure (+1116 to the hardening spec, +556 controller tests).

They edit **different halves of the same entry**, so they are complementary, not
competing. Order: **#946 merges first** (it's clean); **#932 then rebases
mechanically** on top — its `next_items` rework sits above #946's
`completion_criteria` additions with no semantic conflict. I will handle the #932
rebase the moment #946 lands. (This also matches #932's own note that overlapping
governance PRs "must serialize and rebase.")

## 2. Independent audit of PR #946 — verdict: **APPROVE-WITH-NITS** (merge-ready)

Full read of all 7 files at head `e89c4ac`, run in a throwaway worktree
(main tree untouched). Recorded here because the GitHub token authenticates as
the operator's own account, so an in-thread "approval" would be a self-approval —
not a legitimate independent sign-off. The audit itself stands on its evidence:

- **Additive & honest** — `ACTIVE_TRACK.yaml` = 32 added / **0 deleted**; the three
  `commit_on_main` SHAs (`e90809c8`, `895e891b`, `414f4c09`) are all confirmed
  ancestors of `main` (`git merge-base --is-ancestor`). No blocker falsely DONE;
  WP-O7 packet `honest_blockers` explicitly closes none of the six.
- **Workflow change fail-closed** — `active-track.yml:251-268`: dev-install failure
  degrades to a `pyyaml` fallback and `--warn-only` keeps unverified criteria
  **unverified**, never synthesizing a pass.
- **Property battery real** — `tests/properties/test_onboarding_readiness_properties.py`
  runs **11/11 passed**; invariants independently re-derive the expected verdict
  (precedence, monotonicity, order-invariance, duplicate-id rejection) rather than
  echoing the implementation. Imports `hypothesis` directly so a missing dep fails
  loud, not skip-passes.
- **Closure spec no overreach** — declares `working_plan`, "implements nothing,"
  and correctly leaves C1/D2/M6-1 operator/owner-gated (D2: "the implementation
  author cannot mint it").
- **Both Greptile P1s are non-blockers** — (1) `.claude/settings.json` "missing" is
  **false**: it is present (225 B) and tracked on both branches (blob `e06b0338`);
  the P1 reflects a checkout where `.claude/` wasn't materialized. (2) The stale-count
  docops failure is **advisory-on-PRs** by design (`docops.yml:52-57` adds
  `--counts-advisory` whenever `GITHUB_BASE_REF` is set) and this PR already refreshes
  the counts anyway.
- **Risk LOW** — exactly the 7 declared files, no root files, no secrets, single
  clean rollback.

**Conclusion:** #946 is merge-ready. Its only real follow-ups are the #932/#943
merge-order reconciliation (I own it) and confirming two env-scoped bootstrap tests
on hosted CI (already disclosed by its author; hosted `pytest 3.11/3.12` is
authoritative, not this container).

## 3. C1 hermetic evidence (assembled read-only; live leg needs Admin:read)

- Structural parity **exit 0**: `check_ci_parity.py --allow-missing-live` →
  "OK (structure aligned)".
- Automerge consumes the manifest as SSOT: `.github/workflows/automerge.yml:100-122`
  (jq-validated `ci-parity-guard/v1`, non-empty, unique).
- Onboarding-admission context registered + regression-sensitive:
  `scripts/governance/ci_parity_manifest.json:38-41`.
- **Gated remainder (Admin:read):** live branch-protection comparison
  (`check_ci_parity.py --live`); the `coherence-delta.yml` merge_group dead-trigger
  capture (`:14`, `:43-44`); and the required/advisory reconciliation (pytest×2 +
  gitleaks are `required` in the manifest but `advisory` in `CI_TRUTH_CONTRACT.json`).

---

## 4. Operator punch-list — the entire remaining agent-impossible set

These four are the whole of what is not mine to do. Everything else is done or
staged. Each is reduced to its minimum.

### A. Merge PR #946  *(1 click + a CI re-run)*
It's green and audited sound (§2). Its checks aged out overnight — re-run them, then
merge. This lands the closure spec + rigorous evidence criteria and is the biggest
single step. (I then rebase #932 onto it — §1.)

### B. Author the D2 record  *(one line, your own PR)*
Exact §9.2 form — paste this into the `onboard-one-door-2026-07` `next_items[D2]`
in your **own** governance PR (I cannot mint it), then run
`python3 scripts/governance/render_active_track_includes.py` and merge:

```yaml
      - id: D2
        what: "D2 RATIFIED — operator=@AmitabhainArunachala; pr=<this PR number>; merge_commit=<40-hex after merge>; scope=WP-O5-strict-default"
        kind: governance
        blocker: false
```

Prerequisite: C1 evidence (CL-2) merged first. That's the only ordering constraint.

### C. Grant Administration:read  *(one repo setting)*
Repo → Settings → grant the session/token Administration:read. This flips C1's live
branch-protection parity from NEEDS_HOST to verifiable and lets me finish the C1
evidence packet (§3).

### D. Nudge the DharmaGraph owner for M6-1  *(one ask)*
The `dharmagraph-engine-2026-07` owner lands the mutmut widening
(`paths_to_mutate` gains `dharma_swarm/operator_core/onboarding/readiness.py`) under
its own packet, per closure spec CL-5 path (a). I'll prepare the exact config diff
as a ready proposal; they land it (it's their owned `pyproject.toml`).

---

## 5. What this seat drives automatically once A–D clear

`C1 (finish live) → WP-O5 (strict-by-default, after D2 merged) → WP-O6
(terminal-envelope proof) → TERMINAL-PROOF (this decorrelated seat runs §13 on a
sterile clone) → closure flip → onboard-one-door graduates → Titanium WP-00
admits → Phase 0 packets` — per the closure spec's CL-4/6/8/9 and the Titanium
spec. The autonomous Routine is **stood down** so it doesn't add a colliding hand;
I re-arm a correctly-scoped one only after A–D clear, if you want it.

**Net:** the graduation is not blocked on missing code. It is blocked on A–D above,
of which only two (B, C) are irreducibly yours — by design.
