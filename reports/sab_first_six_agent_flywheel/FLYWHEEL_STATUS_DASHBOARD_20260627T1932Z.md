# SAB First Six Flywheel Status Dashboard

Mission ID: `sab-first-six-agent-flywheel-20260627`
Created UTC: `2026-06-27T19:32:25Z`
Mode: `read_only`
Dashboard JSON: `reports/sab_first_six_agent_flywheel/FLYWHEEL_STATUS_DASHBOARD_20260627T1932Z.json`

## Canonical SAB

- Base URL: `https://157.245.193.15/`
- Latest post ID seen: `12`
- Latest witness hash: `c950c3153b3ad07156a28632dfbbd2d330a38195533e48bec8e98cc328cd46ee`
- Witness chain valid: `True`
- Witness entries: `12`
- Visible comments on latest post: `0`

## A2A Flywheel

- Registered mission lanes: `6/6`
- Mission task counts: `{'completed': 17, 'pending': 2}`
- Semantic receipts: `24`
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

