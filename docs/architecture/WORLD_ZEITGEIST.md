# World Zeitgeist Radar

Zeitgeist now means external world signal, not internal repo health.

The live path is:

1. Public scout receipts and operator drops land in `~/.dharma/meta/world_*.jsonl`.
2. `tools/world_signal_ingestor_go` normalizes them into `world_signal_feed.jsonl`.
3. `dharma_swarm.world_signal_analysis` groups them into movements and applies the promotion rule.
4. Weak but interesting movements get Markdown and JSON incubation artifacts under `~/.dharma/meta/world_radar/incubations/`.
5. Promotion-ready movements are written to `world_zeitgeist_inbox.jsonl`.
6. `ZeitgeistScanner` publishes those into canonical `zeitgeist.jsonl`.
7. `ShaktiExecutive` turns them into `ecosystem_scan` opportunities with `strategic_vision`.

Promotion is intentionally conservative: a movement must clear `score >= 0.62` and have either two independent public sources, or an operator drop plus a concrete public evidence URL/source.

Hourly public fetch is wired through cron handler `world_scout`, but network fetching is gated by `DHARMA_WORLD_SCOUT_FETCH=1` or job-level `fetch=true`. Without the flag, the handler reports `WAITING_EXTERNAL` rather than silently pretending to scan the world.

Internal runtime pressure is separate. Witness logs, shared notes, stigmergy density, and `gate_pressure.json` are owned by `InternalPressureScanner`, not by zeitgeist.
