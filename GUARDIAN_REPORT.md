# GUARDIAN CREW REPORT
*Generated: 2026-05-10T13:31:09.420767+00:00*
*Src root: /Users/dhyana/dharma_swarm_lf5/dharma_swarm*

## Summary
| Severity | Count |
|----------|-------|
| BLOCKER  | 0 |
| DEGRADED | 2 |
| WARNING  | 1 |
| TOTAL    | 3 |

## BLOCKERs
*None.*

## DEGRADED
### 1. Stale loop output: telos objectives
**Check:** `LOOP_WATCHER:freshness` | **File:** `/Users/dhyana/.dharma/telos/objectives.jsonl`

objectives.jsonl last modified 257.8h ago (threshold: 72h). The telos objectives loop may not be running.

**Fix:** Check if the telos objectives loop is active; restart if needed.

### 2. Repeated errors: openrouter (12 in last 1000 log lines)
**Check:** `ROUTER_PROBE:log_errors` | **File:** `N/A`

Provider openrouter appears 12 times in error patterns. Possible dead provider.

**Fix:** Check openrouter API key and quota; consider moving it lower in CANONICAL_SEED_ORDER.

## WARNINGs
### 1. Loop artifact missing: memory (memory palace db)
**Check:** `LOOP_WATCHER:existence` | **File:** `N/A`

Expected artifact for memory loop not found in /Users/dhyana/.dharma

**Fix:** Run `dgc orchestrate-live` to boot the memory loop

## Checked By
- **AUDITOR**: Import chains, method existence, syntax errors across all modules
- **LOOP_WATCHER**: Cybernetic loop artifact existence + freshness + evolution quality
- **ROUTER_PROBE**: Circuit breaker state, log error patterns, missing API keys

---
*Guardian Crew runs every 4 hours. Report overwrites previous. BLOCKERs trigger GitHub issues via world_actions.github_create_issue().*