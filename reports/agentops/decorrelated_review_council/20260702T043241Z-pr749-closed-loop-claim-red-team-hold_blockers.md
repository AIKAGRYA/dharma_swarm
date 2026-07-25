# Decorrelated Review Council

conviction_gate: **hold_blockers**
target_score: 95
critics: 1 required=1
score_min: 0
score_avg: 0.0

## Blockers

- openrouter-minimaxm3: APIStatusError Error code: 402 - {'error': {'message': 'Insufficient credits. Add more using https://openrouter.ai/settings/credits', 'code': 402}}
- openrouter-minimaxm3: disagreement=Error code: 402 - {'error': {'message': 'Insufficient credits. Add more using https://openrouter.ai/settings/credits', 'code': 402}}
- persistent-agent:palantir-pilot: persistent A2A worker is not currently running

## Critics

- `openrouter-minimaxm3` `openrouter:minimax/minimax-m3` ok=False verdict=blocked score=0 actual=-
  summary: openrouter-minimaxm3 could not run.
  blocker: Error code: 402 - {'error': {'message': 'Insufficient credits. Add more using https://openrouter.ai/settings/credits', 'code': 402}}

## Persistent Agent

- `palantir-pilot` status=stopped fresh=False
  blocker: persistent A2A worker is not currently running
