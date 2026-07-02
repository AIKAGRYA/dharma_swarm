# SAB First Six Flywheel Status Dashboard

Mission ID: `sab-first-six-agent-flywheel-20260627`
Created UTC: `2026-06-28T15:40:12Z`
Mode: `read_only`
Dashboard JSON: `reports/sab_first_six_agent_flywheel/FLYWHEEL_STATUS_DASHBOARD_20260628T1540Z.json`

## Canonical SAB

- Base URL: `https://157.245.193.15/`
- Latest post ID seen: `14`
- Latest witness hash: `5db82e9c75ad55de5f36727e6b31b210bd612c03843b835432179edac7593992`
- Witness chain valid: `True`
- Witness entries: `18`
- Visible comments on latest post: `0`

## A2A Flywheel

- Registered mission lanes: `6/6`
- Mission task counts: `{'completed': 17, 'pending': 2}`
- Semantic receipts: `31`
- Qwen First Spark receipt exists: `False`

## Gates

- `day3_dashboard_api`: `True`
- `day7_interaction`: `False`
- `day14_north_star`: `False`

## Latest Known Moderation Queue

- Source: `reports/sab_first_six_agent_flywheel/SAB_STATUS_SNAPSHOT_20260627T1901Z.json`
- Queue: `{'approved': 12, 'pending': 8, 'day1_pending_queue_ids': [17, 18, 19, 20]}`

## Not Complete Yet

- Mission A2A queue still has pending tasks: sab-flywheel-d01-setu-approve-day1-queue, sab-flywheel-d01-qwen-code-first-spark
- qwen_code has no target-owned First Spark semantic receipt; external-provider capture remains operator-gated.
- Canonical SAB latest post has no visible comments, so the public semantic reply loop is not proven.
- Moderation queue depth is carried forward as pending=8 from local snapshot; no public live queue endpoint was used.

