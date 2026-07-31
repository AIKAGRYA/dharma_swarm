# Archived: Model Routing Map

Snapshot, do not trust without re-verification. The historical content moved to [docs/_archive/2026-04/MODEL_ROUTING_MAP.md](docs/_archive/2026-04/MODEL_ROUTING_MAP.md).

## Live seat notes (verify against code)

- Sarathi apex seat (PR-S3, operator ruling 2026-07-30): model identity
  resolves from `DGC_DIRECTOR_SARATHI_MODEL`, else the Anthropic frontier
  default from `dharma_swarm/model_hierarchy.py` (`default_model`), else the
  hard fallback named in `_sarathi_model_identity()` — see
  `scripts/runtime/codex_composer_wake_loop.py:90`. The former
  gemini-2.5-flash default is retired; the code is the truth for the current
  resolution.
