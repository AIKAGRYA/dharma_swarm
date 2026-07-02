# Decorrelated Review Council

conviction_gate: **hold_blockers**
target_score: 95
critics: 1 required=1
score_min: 0
score_avg: 0.0

## Blockers

- nvidia-nim-minimaxm3: ReadTimeout
- persistent-agent:palantir-pilot: persistent A2A worker is not currently running

## Critics

- `nvidia-nim-minimaxm3` `nvidia_nim:minimaxai/minimax-m3` ok=False verdict=blocked score=0 actual=-
  summary: nvidia-nim-minimaxm3 could not run.
  blocker:

## Persistent Agent

- `palantir-pilot` status=stopped fresh=False
  blocker: persistent A2A worker is not currently running
