# vulture whitelist — names that look unused but are reflectively or
# decorator-invoked. Each reference here marks the symbol as "used" so vulture
# stops false-positive flagging.
#
# Convention: prefix-comment groups by source pattern. Add new entries with a
# brief reason. Re-run `make vulture` after edits to verify whitelist still
# matches reality.
#
# Generated 2026-05-09 as part of code-quality stack rollout.

# ---------------------------------------------------------------------------
# Pydantic model patterns — fields/validators are accessed via reflection
# ---------------------------------------------------------------------------
ConfigDict
model_config
model_validator
field_validator
model_dump
model_dump_json
model_validate
model_validate_json
model_fields
model_post_init

# ---------------------------------------------------------------------------
# pytest fixtures, plugins, hooks — invoked by collection / discovery
# ---------------------------------------------------------------------------
pytest_collection_modifyitems
pytest_configure
pytest_addoption
pytest_sessionstart
pytest_sessionfinish
pytest_runtest_setup
pytest_runtest_teardown

# ---------------------------------------------------------------------------
# FastAPI / Typer route handlers — invoked via decorator registration
# ---------------------------------------------------------------------------
# (HTTP methods on routers; CLI command callbacks register via @app.command)

# ---------------------------------------------------------------------------
# Async lifecycle hooks — called by event-loop / scheduler frameworks
# ---------------------------------------------------------------------------
__aenter__
__aexit__
__aiter__
__anext__
on_startup
on_shutdown
on_event

# ---------------------------------------------------------------------------
# dharma_swarm-specific — invoked via gate / kernel / cron registry
# ---------------------------------------------------------------------------
# Add specific patterns here AFTER baseline run identifies them. Do not
# pre-populate; let the first vulture run surface real false positives.
