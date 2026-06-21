# Preflight Summary — Full Swarm E2E 2026-06-21

## Branch / commit

- Worktree: `/home/ubuntu/pr-work/full-swarm-e2e-20260621`
- Branch: `devin/full-swarm-e2e-test-20260621`
- Commit tested: `726bc9d4d4add60c46f102d1ceee3a065c474892`
- State root intended for this run: `/home/ubuntu/pr-work/full-swarm-e2e-20260621/.e2e_state/full_swarm_test_20260621`
- Actual preflight caveat: `make onboard` wrote a machine receipt to `/home/ubuntu/.dharma/ops/onboard_receipt.json`; this owner does not respect the repo-local state root by default.

## What make onboard says is live

- Active portfolio: 7 co-equal tracks rendered from `docs/governance/ACTIVE_TRACK.yaml`.
- Shippable now line observed: runtime truth reconciliation, runtime truth NATS, truth graph platform, composer holon spine longrun, provider routing consolidation.
- Main next blockers observed: spine adoption bypasses and provider chain hardening with no real key required.

## What make orient generated

- `reports/orientation/repo_context.json`
- `reports/orientation/repo_context.md`
- Loop 1 closure reported `NOT LIVE`: no persisted EvidenceReceipt yet.
- Broken register projection reported 15 open-like items.

## What make status reported

```text
python3 scripts/governance/repo_status.py
============================================================
  DHARMA SWARM — REPO STATUS
  2026-06-21 13:50 UTC
============================================================

📌 Branch: devin/full-swarm-e2e-test-20260621
   Last commit: 726bc9d4 Merge pull request #658 from AmitabhainArunachala/claude/loop-closure-cascade-2je1gw

🎯 Active Track: Runtime Truth Reconciliation — operator-visible truth packets
   ID: runtime-truth-reconciliation-2026-06
   Status: ACTIVE
   Verified: 2026-06-20

📋 Open PRs: 8 total, 0 stale (>14d)
   #660 (app/devin-ai-integration) Add dashboard runtime inside-out testing skill
   #659 (AmitabhainArunachala) chore(governance): ops report 2026-06-21T1200Z — spine 93.8%
   #653 (AmitabhainArunachala) chore(governance): ops report 2026-06-21T0600Z — spine 93.8%
   #649 (AmitabhainArunachala) chore(governance): ops report 2026-06-20T0600Z — spine 93.8%
   #647 (AmitabhainArunachala) [codex] governance: refresh active track and fitness propert
   ... and 3 more

🔧 Broken Register: 21 total, 8 open-like

📊 Hotlist: 39 items — 9 done, 3 WIP, 27 pending

🧪 Test functions: 11820

⚠️  Warnings:
   - 8 open broken register items

============================================================
  Run `make onboard` for full operating reality
  Run `make status` for this quick snapshot
============================================================
```

## Known broken/open/partial surfaces before the gauntlet

From `make orient`: BR-003, BR-004, BR-005, BR-009, BR-010, BR-011, BR-012, BR-013, BR-014, BR-015, BR-016, BR-017, BR-018, BR-021, BR-022.

## Unsafe to mutate

- External outreach/email/social/payment/trade/deploy actions.
- Live DGC apply (`DHARMA_EVOLUTION_SHADOW=0`) without separate approval.
- Production GitHub merge/PR automation beyond the final draft evidence PR.
- Real provider key creation or secret printing.

## Raw outputs

See `00_preflight/*.txt`.
