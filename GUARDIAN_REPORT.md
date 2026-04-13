# GUARDIAN CREW REPORT
*Generated: 2026-04-13T10:33:22.274633+00:00*
*Src root: /Users/dhyana/dharma_swarm_lf5/dharma_swarm*

## Summary
| Severity | Count |
|----------|-------|
| BLOCKER  | 1 |
| DEGRADED | 2 |
| WARNING  | 1 |
| TOTAL    | 4 |

## BLOCKERs
### 1. PalaceQuery.__init__() missing in memory_palace.py
**Check:** `AUDITOR:method_exists` | **File:** `memory_palace.py`

Class PalaceQuery exists but method __init__ is not defined

**Fix:** Add `def __init__(self, ...)` to PalaceQuery

## DEGRADED
### 1. TaskBoard.get_by_title() missing in task_board.py
**Check:** `AUDITOR:method_exists` | **File:** `task_board.py`

Class TaskBoard exists but method get_by_title is not defined

**Fix:** Add `def get_by_title(self, ...)` to TaskBoard

### 2. TelosGraph.get_by_name() missing in telos_graph.py
**Check:** `AUDITOR:method_exists` | **File:** `telos_graph.py`

Class TelosGraph exists but method get_by_name is not defined

**Fix:** Add `def get_by_name(self, ...)` to TelosGraph

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