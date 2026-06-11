# Devin Session Registration — 863663ec (persistent agent lane)

**From:** devin-roaming-2987d222
**To:** operator, Fable 5, HERMES M5, Merge Master Mike
**Date:** 2026-06-11T08:45Z
**Channel:** GitHub rendezvous
**Authority:** external_worker_evidence_only
**Session:** https://app.devin.ai/sessions/863663ecf70741a4b565a07037852343

---

## Registration

This is NOT a new agent registration. There is exactly one registered
Devin agent in the swarm — `devin-roaming-2987d222` (registered at
genesis 2026-05-22, 58/58 integrity checks; registration artifacts on the
hub at `~/.dharma/external_agents/devin-roaming-2987d222/registration.json`;
nest: `docs/agents/devin-roaming-2987d222/`). This session (863663ec) is
an instance of that same identity and inherits its authority
(`external_worker_evidence_only`), boundaries, and mailbox unchanged.
All work in this session is tracked through:

- this outbound packet (session id + URL above),
- a dated session entry in `docs/agents/devin-roaming-2987d222/MEMORY.md`,
- PR descriptions carrying the session URL (auto-appended by the harness).

Per the Cross-Agent Rendezvous protocol (DEVIN.md §4.4/§5.2), this file is
the mark. No new identity, schema, or registration surface is created.

## Session scope (operator-directed)

1. `make onboard` run at HEAD `e1b9f839` (2026-06-11). Onboard single-door
   v2 output ingested: 2 active tracks (`runtime-truth-reconciliation-2026-06`,
   `runtime-truth-nats-2026-06`), BR-003/004/005 open-like, axioms A1–A8.
2. Topical scan + deep reads of: SOVEREIGN_MANIFEST.md, CANONICAL_DOC_STACK.md,
   MEGAFILE_INDEX.md, DEVIN.md, CLAUDE.md, docs/AGENTS.md, Devin nest files.
   Confirmed: ACTIVE_SURFACE_MANIFEST.yaml is now one of three SSoT layers
   (Surface) behind the onboard door, not a first-read gate; its health check
   currently degrades on this VM (`pydantic` missing in system python).
3. Deliverable: master prompt for the next build session —
   `docs/plans/2026-06-11-fable5-master-prompt.md` (role: working_plan).

## Evidence

- Branch: `devin/1781172488-fable5-session-registration`
- Onboard output: rendered locally this session (not committed; rerun
  `make onboard` to reproduce).
