# Go Idea Spark Ingest Spine Integration

Date: 2026-06-03 UTC
Branch: `trust-build-compass`
Base HEAD observed: `4bb47aed`
Controlling spec: `docs/specs/GO_IDEA_SPARK_INGEST_SPINE_MASTER_BUILD.md`

## Status

This build line wires the Go ingest family into a receipt-first Idea Spark spine.
It is implemented as a conceptual PR stack over a dirty local worktree; do not
merge the whole worktree as one PR without splitting or reviewing unrelated
staged changes.

Completed slices:

| Slice | Result | Primary files | Evidence |
| --- | --- | --- | --- |
| PR1 Go CI | `world_scout_go` is under `make go-ci` | `Makefile`, `tools/world_scout_go/go.mod` | `~/.dharma/agents/codex_planner/evidence/go-idea-spark-ingest-spine-pr1/` |
| PR2 Spool | durable append/list/replay spool in Go SDK | `tools/go_sdk/spool/` | `~/.dharma/agents/codex_planner/evidence/go-idea-spark-ingest-spine-pr2/` |
| PR3 Receipts | world runtime can project canonical receipts | `tools/world_signal_ingestor_go/main.go`, `dharma_swarm/world_radar/go_bridge.py`, `dharma_swarm/operator_core/world_radar/receipt_bridge.py` | `~/.dharma/agents/codex_planner/evidence/go-idea-spark-ingest-spine-pr3/` |
| PR4 Robustness | large JSONL scanner, context/retry/backoff, partial success | `tools/world_signal_ingestor_go/main.go`, `tools/world_scout_go/scout.go` | `~/.dharma/agents/codex_planner/evidence/go-idea-spark-ingest-spine-pr4/` |
| PR5 Observability | ingest summary, retry count, idempotent cost event | `dharma_swarm/world_radar/go_bridge.py`, `tools/world_scout_go/health.go` | `~/.dharma/agents/codex_planner/evidence/go-idea-spark-ingest-spine-pr5/` |
| PR6 Triage | deterministic Idea Spark v0 tuple gates promotion | `dharma_swarm/world_radar/analysis.py`, `tests/test_world_signal_analysis.py` | `~/.dharma/agents/codex_planner/evidence/go-idea-spark-ingest-spine-pr6/` |
| PR7 NATS | optional ack-gated NATS projection behind `DHARMA_INGEST_NATS=1` | `dharma_swarm/operator_core/ingest_nats.py`, `dharma_swarm/world_radar/go_bridge.py` | `~/.dharma/agents/codex_planner/evidence/go-idea-spark-ingest-spine-pr7/` |

## Runtime Contract

Default transport:

```text
Go ingestor -> receipt files -> Python receipt projection -> board/inbox
             -> ingest_run_summary.json
             -> ingest_run_summaries.jsonl
             -> ingest_cost_ledger.jsonl
```

Optional hot transport:

```text
receipt files -> Python ingest_nats adapter
              -> existing NATS ack verifier
              -> publish only when ack_verified
```

Authority boundaries:

- Go collects, normalizes, hashes, emits receipts, reports health, and exposes
  retry counts.
- Python owns triage, policy, board/inbox projection, NATS authority status, and
  economic event projection.
- Receipt files remain replay truth even when NATS is enabled.
- `ingest_cost_ledger.jsonl` uses neutral compute units only; it is not USD
  pricing and does not call `EconomicSpine.spend_tokens`.

## Branch And PR Hygiene

Open PR scan on 2026-06-03 UTC found one broad path match:

| PR/branch | Evidence | Action |
| --- | --- | --- |
| `#332 devin/1779503110-staging-promote-hermes-wiring` | touches `Makefile`, updated 2026-06-02T23:03:59Z; title is ops/Hermes wiring | Do not merge into this ingest stack. Rebase/cherry-pick only if a Makefile conflict appears. |

Go/sense/world branches with no open PR found by direct `gh pr list --head`:

| Branch | Latest observed commit | Action |
| --- | --- | --- |
| `chore/go-sense-organ-roadmap` | `177e2467`, 2026-05-09 | Do not merge whole branch; cherry-pick docs only if still useful. |
| `docs/go-language-boundary-policy` | `87c0766f`, 2026-05-09 | Cherry-pick only after comparing with this stack's boundary docs. |
| `feat/go-evidence-sense-organ-v0` | `a2741bef`, 2026-05-09 | Superseded by PR2/PR3 receipt SDK/spool work; cherry-pick only with tests. |
| `feat/go-evidence-sense-organ-v0-closure` | `0b11bccb`, 2026-05-09 | Superseded/duplicate; do not merge wholesale. |
| `feat/go-github-repo-ingestor` | `a4aa32f9`, 2026-05-12 | Cherry-pick cache-hardening only after diffing against current `github_ingestor_go`. |
| `feat/go-receipt-sdk` | `0bd9c221`, 2026-05-09 | Superseded by `tools/go_sdk/receipt` plus new `spool`; do not merge wholesale. |
| `feat/world-radar-shakti-safe-convergence-2026-05-13` | `3befc1e9`, 2026-05-13 | Older world-radar convergence branch; cherry-pick only after board/triage tests pass. |

## Final Verifier Set

Required before review:

```bash
make onboard
make go-ci
./.venv/bin/python -m pytest -q \
  tests/test_ingest_nats.py \
  tests/test_world_signal_analysis.py \
  tests/test_world_radar_go_bridge.py \
  tests/test_go_evidence_ingestor_bridge.py \
  tests/test_go_github_ingestor_bridge.py \
  tests/test_nats_live_contact.py
python3 scripts/runtime/codex_agent_loops.py validate --loop-id go-ingest-pr7-nats --phase complete --json
```

## Rollback

Rollback by reverting the stack files in reverse order:

1. PR7: `dharma_swarm/operator_core/ingest_nats.py`, `tests/test_ingest_nats.py`,
   NATS status additions in `go_bridge.py`, and NATS env isolation in
   `tests/conftest.py`.
2. PR6: triage additions in `dharma_swarm/world_radar/analysis.py`,
   `tests/test_world_signal_analysis.py`, and `WORLD_ZEITGEIST.md`.
3. PR5: ingest summary/cost event additions in `go_bridge.py` and retry count in
   `tools/world_scout_go`.
4. PR4-PR1: revert by slice only after checking the receipt evidence directory
   for the exact verifier commands.

No default live NATS call, external publish, or USD cost accounting is introduced.

## PR Description Draft

Title:

```text
feat(go-ingest): wire receipt-first Idea Spark ingest spine
```

Body:

```text
## Summary
- Put all production Go ingest modules under `make go-ci`, including `world_scout_go`.
- Add durable Go SDK spool/replay primitives and canonical receipt projection for world signals.
- Harden JSONL/context/retry/partial-failure behavior.
- Add ingest summaries, neutral-unit cost events, deterministic Idea Spark v0 triage, and optional ack-gated NATS projection.

## Authority
- Receipt files remain replay truth.
- Python owns triage, policy, economic events, and NATS authority status.
- NATS is disabled by default and never claims liveness without existing verifier ack proof.

## Verification
- `make go-ci`
- bridge/world pytest set listed in `reports/agentops/go_idea_spark_ingest_spine_integration_2026-06-03.md`
- Codex loop receipts under `~/.dharma/codex_loops/go-ingest-pr*`

## Rollback
Revert by PR slice in reverse order; no production transport or pricing model is enabled by default.
```
