# Product Surface

The canonical DHARMA product surface is the dashboard web app.

Rules:
- The dashboard is the primary operator and user-facing interface.
- Browser and desktop shells wrap the same dashboard application.
- New parallel GUIs are not introduced unless they are explicitly promoted into the product surface.
- Runtime, API, and shell work should converge on the dashboard instead of forking into alternate control planes.
- **Research surfaces are not product surfaces.** A research surface (e.g. `dharma_swarm/invariant_observatory.py`, the GPLOT lodestone family, the cultivation observer) writes `ExternalOutcomeRecord` rows into the existing telemetry plane and is read by existing consumers. It does not introduce a new dashboard, control plane, or database. Promotion of a research surface to product/control authority is gated by a documented promotion review (see `ACTIVE_SURFACE_MANIFEST.yaml` `research_surfaces[].promotion_gate`).

Current landing mode:
- `dashboard/src/app/dashboard/qwen35/page.tsx` is the canonical landing experience for the active chat shell.
- `api/routers/chat.py` is the backing chat surface for that shell.
- `run_operator.sh` and `scripts/dashboard_ctl.sh` are the supported local control entrypoints for running the surface.
