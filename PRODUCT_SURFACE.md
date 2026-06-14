# Product Surface

The canonical DHARMA product surface is the dashboard web app.

Rules:
- The dashboard is the primary operator and user-facing interface.
- Browser and desktop shells wrap the same dashboard application.
- New parallel GUIs are not introduced unless they are explicitly promoted into the product surface.
- Runtime, API, and shell work should converge on the dashboard instead of forking into alternate control planes.

Current landing mode:
- `/dashboard/cockpit` is the canonical human front door for John.
- `dashboard/src/app/dashboard/cockpit/page.tsx` intentionally aliases the control-surface implementation.
- `dashboard/src/app/dashboard/control-surface/page.tsx` is the technical implementation route for the cockpit, not a separate front door.
- `dashboard/src/app/dashboard/qwen35/page.tsx` remains the active surgical chat shell.
- `api/routers/chat.py` is the backing chat surface for the chat shells.
- `run_operator.sh` and `scripts/dashboard_ctl.sh` are the supported local control entrypoints for running the surface.
