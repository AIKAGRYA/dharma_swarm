# World Zeitgeist Radar

This subsystem gives Dharma Swarm outside-world eyes. It is separate from
internal repo health, witness pressure, and local shared notes.

## Plain-Language Shape

The loop is:

1. `world_scout_go` fetches public sources when live fetch is explicitly enabled.
2. `world_signal_ingestor_go` normalizes raw receipts into scored world signals.
3. `world_radar/analysis.py` groups signals into movements, applies source weights,
   and decides whether each movement is watchlist, incubating, or promotion-ready.
4. `world_radar/rnd.py` writes deterministic verify/connect/evolve artifacts for
   incubating movements.
5. `world_radar/go_bridge.py` publishes the board, brief, health, and promotion inbox.
6. `zeitgeist.py` reads only external world feeds and writes canonical
   `meta/zeitgeist.jsonl`.
7. `ShaktiExecutive` reads those promoted world signals and turns them into
   opportunity-board rows with strategic vision.
8. `frontier_refill` admits only mature, evidenced rows into
   `frontier_tasks_pending.jsonl`, preserving the strategic vision in task
   metadata for TelicSeam outcome feedback.

The intended result is not "we saw a company." The result is "we saw a public
movement, verified enough evidence, asked first-principles questions, connected
adjacent signals, and routed a concrete next artifact into the swarm."

## Runtime Artifacts

Primary state lives under `~/.dharma/meta/`:

- `world_signal_board.json`: movement board with scores, deterministic Idea
  Spark triage tuples, source counts, status, cascade queries, and strategic
  vision.
- `world_signal_brief.md`: morning-readable summary.
- `world_zeitgeist_inbox.jsonl`: promotion-ready movements for `zeitgeist.py`.
- `zeitgeist.jsonl`: canonical external feed consumed by Shakti.
- `world_operator_drops.jsonl`: operator-supplied public signals.
- `world_radar/world_radar_health.json`: scan health and source failures.
- `world_radar/ingest_run_summary.json`: latest Go ingest run summary with
  source counts, accepted/rejected counts, bytes, retries, freshest receipt,
  provisional compute units, and NATS transport status.
- `world_radar/ingest_run_summaries.jsonl`: append-only run-summary history.
- `world_radar/ingest_cost_ledger.jsonl`: append-only idempotent provisional
  cost events. The unit is `neutral_compute_unit`; this is not USD pricing.
- `world_radar/source_weights.json`: learned source priors.
- `world_radar/incubations/*/{verify,connect,evolve}.{json,md}`: R&D workups.
- `receipts/world_signals/*.json`: canonical Go evidence receipts. JSONL feeds
  are derived projections; receipt files remain replay authority.

Internal pressure lives separately:

- `internal_pressure.jsonl`
- `internal_pressure.md`
- `gate_pressure.json`

`gate_pressure.json` is written by `InternalPressureScanner`, not by the external
zeitgeist scanner.

## Fetch Gating

Live public fetch is explicit:

- Cron job: `handler=world_scout`, `fetch=true`
- Env override: `DHARMA_WORLD_SCOUT_FETCH=1`

The orchestrator loop runs `run_world_radar_go_once(scout_fetch=False)`. That
normalizes existing receipts and keeps the brief/board fresh without opening an
unbounded live network scan inside the metabolic heartbeat.

The cron handler canonicalizes the promotion inbox into `zeitgeist.jsonl` after
each live scout pass. The intended safe order is:

1. `world_scout`
2. `shakti_executive`
3. `frontier_refill`

`world_scout` is the only live-fetch step in that chain. `ShaktiExecutive` only
refreshes `opportunity_board.json`; it does not dispatch work. `frontier_refill`
is the first execution-adjacent membrane.

## Source Model

Default source families are Hacker News, GitHub repositories, GitHub advisories,
arXiv Atom feeds, Reddit JSON endpoints, and configured URLs from
`~/.dharma/meta/world_radar/sources.json`.

Operators can add a public signal directly:

```bash
python -m dharma_swarm.world_radar.cli drop \
  --title "SubQ managed agent runtime" \
  --url "https://example.com/subq" \
  --note "Operator saw this public launch" \
  --tag agentic \
  --tag runtime
```

## Promotion Rule

A movement becomes promotion-ready only when:

- weighted score is at least `0.62`, and
- deterministic Idea Spark v0 triage passes with the tuple
  `novelty`, `telos_fit`, `tractability`, and `source_confidence`, and
- it has either two independent public source families, or an operator drop with
  a concrete URL/source.

Single-source signals above `0.42` become incubating, not promoted. Incubation
creates R&D artifacts and cascade queries so the next scan can verify or reject
the movement.

## Safety Properties

- Radar board, brief, health, inbox, and source-weight writes use tmp-then-rename
  persistence.
- A world-radar lock serializes cron and orchestrator no-fetch passes.
- Go ingest NATS projection is disabled unless `DHARMA_INGEST_NATS=1`; when
  enabled it must report `ack_verified`, `ack_unverified`, or `unavailable`
  using the existing NATS verifier surfaces. Receipt files remain authoritative.
- Source-weight learning is event-idempotent through
  `world_radar/source_feedback_ledger.json`.
- Recent `zeitgeist.jsonl` history is deduped for 14 days so repeated scans do
  not make the same public signal look newly discovered forever.
- Incubating/watchlist world rows are blocked from frontier admission even if
  they have a high score.
