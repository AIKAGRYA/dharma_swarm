# CONTEXT_ENGINEERING - codex_telos

## Minimal Context

For most tasks, load only:

1. `make onboard` output.
2. `docs/vision_maps/TELOS_MORNING_REFINERY_V0.md`.
3. `docs/research/telos_ai/empire_agents/README.md`.
4. `tests/test_telos_morning_refinery.py`.
5. `PRODUCT_SURFACE.md`.

Use `~/.dharma/telos/TELOS_ALGORITHM_V0.md` as local dogfood context, not as
repo authority.

## Search Rules

- Search `docs/research/telos_ai/**` before broad repo search.
- Search `docs/agents/codex_telos/**` for accountability.
- Search `~/.dharma/telos/` for private canonical store state.
- Do not search or copy raw morning-page text into repo docs.

## Compression Rule

When handing off, preserve:

- what was changed,
- what was verified,
- which gates remain unbuilt,
- whether any external receipt exists.

Never compress away the noetic-before-empire boundary.
