# First Fire — witness record and fire ladder, 2026-08-18

**Executes:** yes-sheet ratification row 6
(docs/plans/YES_SHEET_RATIFICATION_2026-08-18.md:19) with the operator's live
authorization this session, verbatim: "Ok light the fire when ready 🙏🏻".

## What happened

The first live invocation of `DarwinEngine.apply_diff_and_test`
(dharma_swarm/evolution.py) in this organism's history — the event BR-003
recorded as never having occurred. One planted-red-then-real-green cycle on
the toy module `experiments/first_fire/probe.py`, in a disposable scratch
worktree on a GitHub-hosted runner, under a one-shot 24h grant minted in the
operator's name and consumed when the pair started.

- Workflow run: https://github.com/AIKAGRYA/dharma_swarm/actions/runs/32126326325
  (first-fire.yml on `main` @ `8cc04b71`, the #1379 merge commit; conclusion
  success, 2026-08-18T10:21:12Z → 10:22:16Z)
- Receipt artifact: `first-fire-receipt` (ID 9320496691, zip sha256
  `264373f4d77ff515b5feeefb4b6385967cd5e4ebb93711a843372c2992094ee7`)

## Receipt (verbatim from the run log)

```json
{
  "schema": "dharma.first_fire.plumbing.v1",
  "ts": "2026-08-18T10:22:13.213940Z",
  "grant_id": "first-fire-plumbing-20260818",
  "granted_by": "AmitabhainArunachala",
  "named_function": "DarwinEngine.apply_diff_and_test",
  "host": "runnervmzvulz",
  "git_base_sha": "8cc04b71987ba83cd166495f83185d3510d33660",
  "scratch": "/home/runner/work/_temp/evolution_worktrees/first-fire-first-fire-plumbing-20260818",
  "allowed_paths": ["experiments/first_fire/probe.py"],
  "red": {
    "diff_sha256": "e4f37dbac7403bf4bf9abf34c9daf38d16b5a01e4f2d1970c9d3fcbbb43ced44",
    "pass_rate": 0.0,
    "skipped": false,
    "file_restored": true,
    "ok": true
  },
  "green": {
    "diff_sha256": "e4fc277b80498fde7e03ef4ddf5f3ca4c65b796ada6e09aa784f8acacac21d68",
    "pass_rate": 1.0,
    "skipped": false,
    "applied": true,
    "ok": true
  },
  "valid": true,
  "note": "valid only if planted-red rolled back AND green applied:true with a non-empty diff hash. This is a plumbing receipt, not DGM."
}
```

## Validity check against the converged spec (FIRST_FIRE_DECISION_DOSSIER_2026-08-18.md)

- Planted red genuinely failed (`pass_rate 0.0`, `skipped false`) and was
  rolled back (`file_restored true`) — the empty-diff auto-pass hole
  (evolution.py:2379-80) demonstrably did not fire. ✓
- Real green genuinely applied (`applied true`) and passed (`pass_rate 1.0`,
  `skipped false`). ✓
- Both diff hashes non-empty and distinct. ✓
- Scratch worktree on a CI runner; host is not `meghadharma-cloud`; no live
  checkout touched. ✓
- One-shot dated grant, consumed at pair start; expires 2026-08-19T10:30Z. ✓

**Claim boundary:** this proves the self-modification plumbing works end to
end under grant, receipt, and rollback discipline. It is not DGM, not
capability uplift, and not a live-organism mutation.

## Fire ladder — next rung

**Fire 2 — real module, deadline 2026-08-21T10:22Z (72h after this receipt):**

- Target: one real (non-toy) module chosen for low blast radius, named in the
  fire-2 grant.
- Requires: a NEW dated one-shot grant (this one is consumed), same
  planted-red-then-real-green shape, same scratch/CI-runner rule, same
  receipt validity conditions.
- The green diff from fire 2 does not self-merge: it lands, if at all, as an
  ordinary PR through the merge queue with a human merge — the per-fire
  human-merge boundary the ratification preserved.
- If the deadline passes unfired, the ladder pauses and the next ask to the
  operator says so; nothing escalates on silence (standing default rule:
  live-authority never defaults to yes).
