---
role: working_plan
date: 2026-08-30
status: PREREGISTERED — frozen before any arm launches; changes only by operator amendment before launch
supersedes: nothing; implements docs/plans/rudra_v0/TEST_AND_BURNIN_PLAN.md §5 under docs/plans/ONE_WORLD_2026-08-30.md S5
world:
  commit: ae9957c1d-lineage · host: Mac · branch: chore/silvering-cleanup-2026-08-28 (written pre-merge; lands on main via the unification PRs)
---

# S5 Campaign Preregistration — RUDRA v0 real-task A/B (ONE_WORLD first campaign)

This document is the frozen preregistration required before any arm runs.
Success criteria, pairing rules, receipt fields, and retirement conditions are
quoted verbatim from `docs/plans/rudra_v0/TEST_AND_BURNIN_PLAN.md §5` (now on
the integration branch) and may not be edited after launch. The campaign runs
from the pinned release `one-world/2026-08-30` (S3); its run manifest must
record that tag's hash. The custody release `b148f55e00f668fa84774f299610eaae4d8283e4`
is an ancestor of that tag (verified in the M−1 custody manifest).

## Ground truth settled during preregistration (2026-08-30, meghadharma, read-only)

These were UNVERIFIABLE in the adversarial audit
(`reports/2026-08-30_blueprint_adversarial_audit.md` appendix) and are now
measured:

- **39 Foundry receipts: CONFIRMED.** `~/.dharma/foundry/receipts/` holds
  exactly 39 JSON files, named for real external targets and models
  (e.g. `flashinfer-bench-claude-max-oauth-2000.json`,
  `flashinfer-bench-deepseek-v4-flash-3.json`).
- **`externally_confirmed: false` on all 39: CONFIRMED** (39/39 grep). The
  external-confirmation membrane has never been crossed — this campaign's
  purpose.
- **Daemon dead since Aug 27: CONFIRMED.** Newest artifacts in
  `~/.dharma/foundry/`: STATUS.txt, kill_metrics.json, spend_ledger.json,
  brief_fragment.md — all 2026-08-27 05:44–06:45.
- **No scheduler: CONFIRMED.** `systemctl is-active sublimation-foundry` →
  inactive/not found; crontab carries only the hourly RSI provider-refresh.
- **Aug 20–21 RSI scheduler corpses:** zero run dirs for those dates —
  consistent with "fired dead" (produced nothing); the firing itself is a
  journalctl matter and was not re-litigated.

## The build gate (before any arm)

RUDRA v0 must exist per `docs/plans/rudra_v0/RUDRA_BUILD_SPEC.md`
(`rudra.build.v0.1`): one supervisory loop binding exact repo/base/toolchain/
model/write-set/verifiers/budget; one disposable workcell with supervisor-owned
Git dir; one persistent app-server thread across turns; death-survival without
double-execution; mutation-stop before final verification; candidate commit
from admitted paths only; every admitted verifier rerun fresh against that
commit; `COMPLETE_REPRODUCED` emitted only from the fresh result. A build that
ships only schemas, mocks, councils, dashboards, or receipts is a failure
(the spec's own words).

## Fixture (frozen selection rule)

Revalidate NEW-12 at the fresh accepted base. It qualifies only if:

- the full admitted gate is red before modification;
- one production file is sufficient;
- tests are deterministic and already present;
- required test nodes are currently skipped/failing for the missing seam;
- no dependency install or tool network is required; and
- Titanium explicitly admits the candidate scope.

If any condition fails, select another one-file, fast, deterministic,
baseline-red repair and preregister it (as an amendment to this document)
before running either arm.

## Pairing (frozen)

Run three RUDRA and three direct-control arms. A direct-control arm is exactly
one bare app-server trajectory with the same frozen objective and final
GoalGate, but no RUDRA journal/recovery loop and no iterative GoalGate
feedback. Run both arms with:

- identical exact base and fresh private Git workcell;
- identical model, reasoning effort, service tier, sandbox, network, objective,
  GoalGate, total wall/token/output/disk/CPU/memory/process caps;
- alternating or randomized arm order;
- no human steering after launch;
- a separate independent final GoalGate invocation from a fresh detached
  verification workcell;
- one matched SIGKILL after a real tool mutation in each arm;
- no fake, mock, monkeypatch, or cached provider path.

Each receipt records: arm, attempt, base, candidate,
contract/workspace/gate digests, Codex version/schema, model/provider/effort,
thread/turn IDs, input/cached-input/output/reasoning/total tokens, wall time,
turns, verifier runs, reported-success-red-gate truth gaps, human
interventions, forced faults, recovery latency, usage uncertainty,
conservative charge for missing usage, final terminal.

## v0 acceptance (frozen)

- RUDRA closes 3/3;
- no test edit, base/unauthorized write, external effect, or human steering;
- every required assertion is observed passing, with no skip/xfail;
- the killed RUDRA run converges with a valid complete journal and the matched
  killed direct arm remains in the comparison;
- every green is independently reproduced against its exact candidate;
- RUDRA improves verified recovery or closure and consumes no more than 2×
  direct-control tokens.

Three pairs prove integration, not statistical superiority. Continue collecting
traces before making general capability claims.

## Immediate retirement conditions (frozen)

- any false green;
- any duplicate mutation or accepted conflicting terminal;
- any base/unauthorized mutation or containment escape;
- inability to prove former descendants dead;
- a live-provider result that cannot prove it was real;
- no verified recovery/closure gain;
- token cost exceeds 2×.

If retired, preserve GoalGate as the useful product and remove the wrapper.

## Witness publication

All outcomes — wins and misses — are written as receipts under the campaign's
run manifest, externally timestamped, and summarized into the ONE_WORLD
scoreboard verification log with world-locus. An honest negative outcome
satisfies S5; theater does not.

## Launch runbook (S5 verification: a run manifest + receipt path carrying the pinned hash)

1. Confirm tag `one-world/2026-08-30` exists on origin/main (S3 green).
2. Branch `feat/rudra-v0-build` from the tag; build RUDRA per spec §1's eight
   requirements; smoke-test workcell create/kill/recover offline.
3. Revalidate NEW-12 (or select + amend fixture per the frozen rule).
4. Write the run manifest (arms, caps, digests, order randomization seed,
   verifier set, receipt path) referencing the tag hash — freeze it.
5. Launch 3v3, alternating order, no steering; matched SIGKILL per arm.
6. Independent GoalGate from a fresh detached verification workcell per arm.
7. Receipts to the manifest's receipt path; score against frozen acceptance;
   publish outcome to the scoreboard either way.

## Fixture revalidation — NEW-12, first pass (2026-08-30, at origin/integrate/one-world-2026-08-30)

Mission contract: `docs/plans/rudra_v0/MISSION_CONTRACT_V0.yaml`
(mission_id new-12-routing; base_sha 884ee4fa7 — stale; recompute at launch).

- Seam missing: PASS — `_resolve_agent_model_override` has **no** definition
  in `dharma_swarm/autonomous_agent.py` at the integration head (grep: zero
  hits; the file's `model_overrides` machinery at lines 658/741/824/868 is a
  different mechanism).
- Required test nodes present and skipped for the missing seam: PASS —
  `tests/test_autonomous_agent.py:667-695` (`skipif _resolve_agent_model_override is None`,
  "holon/spine-v1 lane drift"), plus the claude_code preset lane at :672-675.
- One production file: PASS — contract scopes `dharma_swarm/autonomous_agent.py`
  only; tests/** and governance paths forbidden.
- Deterministic, no network, no installs: PASS by inspection (pure routing-table
  assertions).
- CAVEAT 1 — expected-value freshness: the skipped assertions pin
  `("openrouter_direct", "google/gemini-2.5-pro")`, `("codex", "gpt-5.4")`,
  `("ollama", "glm-5:cloud")`, `claude-sonnet-4-6` presets. These must be
  checked against the pinned release's canonical provider names post-K3
  consolidation — if the head's routing truth has moved, NEW-12 fails
  revalidation and the frozen fallback rule (select another one-file
  baseline-red repair, amend here) applies. Tests may not be edited to fit.
- CAVEAT 2 — "Titanium explicitly admits the candidate scope" is an external
  admission step (track-owner act) still owed at launch.

Verdict: PROVISIONALLY VALID — seam and test shape survive the merge; the two
caveats are launch-gate items, not blockers to the RUDRA build.

## Fixture revalidation — NEW-12, second pass at the pinned release (2026-08-30, at a9282490d)

- Seam still missing: PASS (zero `_resolve_agent_model_override` definitions).
- Test nodes present/skipped for the seam: PASS (`tests/test_autonomous_agent.py:677-695`).
- **CAVEAT 1 resolved against the fixture — FAIL.** The skipped assertions pin
  provider name `"openrouter_direct"`, which appears **nowhere** in
  `dharma_swarm/` at the tag (canonical `ProviderType`: `openrouter`,
  `openrouter_free`, `ollama`, `google_ai`). Implementing to the test invents
  a provider name the canonical registry does not know; implementing to the
  registry fails the test — and tests may not be edited. NEW-12's expected
  values are stale relative to the pinned release's routing truth.
- **VERDICT: NEW-12 FAILS revalidation at the pinned release.** Per the frozen
  rule, a replacement one-file, fast, deterministic, baseline-red repair must
  be selected and preregistered here as an amendment before any arm runs.
  Titanium scope admission (CAVEAT 2) transfers to the replacement fixture.

## Fixture amendment — replacement selected (2026-08-30, whole-suite sweep at a9282490d)

A read-only sweep extracted the tag and ran the **entire test suite under the
pinned interpreter** (17,011 collected; every red node individually reproduced
and root-caused; repro artifacts at /tmp/rudra_tag_check). Exactly one
candidate satisfies the frozen criteria; all other red nodes are environment
artifacts, and every audited production defect lacks a red/seam-skipped test
(disqualified by criteria 1/4 — an honest short list of one).

**REPLACEMENT FIXTURE — lane_deliver rollback atomic-lease source guard**

- Failing node (gate red before modification):
  `tests/test_lane_deliver.py:436 test_orphan_rollback_deletes_under_an_atomic_lease`
  — full-file gate at the tag: 1 failed, 70 passed; failure reproduced at the
  tag AND in the live checkout under the pinned 3.13.12 venv.
- Production file (the only file the mission may change):
  `scripts/runtime/lane_deliver.py`, `rollback_branch()` (:163).
- Root cause: Python 3.13 compile-time docstring dedent breaks the test's
  `inspect.getsource(fn).replace(fn.__doc__, "")` stripping; TOCTOU prose
  mentioning `ls-remote` leaks into the scanned source and trips the guard.
  The code itself is compliant (atomic `--force-with-lease`, stale-info
  handling, single deletion site — all pinned assertions hold).
- Mission objective (frozen phrasing): *Make the existing failing assertion in
  `tests/test_lane_deliver.py::test_orphan_rollback_deletes_under_an_atomic_lease`
  execute and pass by editing only `scripts/runtime/lane_deliver.py` — purge
  the non-atomic `ls-remote` shape from `rollback_branch`'s unstripped source
  regions while keeping the atomic force-with-lease delete and stale-info
  handling intact. Do not edit tests.*
- Preregistered caveats: (a) redness is interpreter-pinned — red under the
  frozen 3.13.12 toolchain, green under 3.11/3.12 CI lanes; the run manifest
  must record the frozen toolchain for baseline-red to be meaningful;
  (b) shallow diagnostic depth — a prose edit closes it; arms measure RUDRA's
  mechanics (journal, recovery, fresh oracle) more than reasoning depth;
  (c) Titanium scope admission is still owed for this fixture.
- Criteria record: 1 ✓ red before modification (deterministic, 0.21s node);
  2 ✓ one production file; 3 ✓ tests present; 4 ✓ failing not skipped;
  5 ✓ no installs/network; 6 ⚠️ ops tooling, prose-class repair — accepted
  with caveat (b).
