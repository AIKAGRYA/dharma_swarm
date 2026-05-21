# Command Plane — Vision

**Status:** Queued track. Active track is `trace-identity-coverage-2026-05`.
**Spec:** `docs/plans/2026-05-21-command-plane-design-lock.md`
**Checklist:** `docs/plans/COMMAND_PLANE_CHECKLIST.md`
**Multi-agent protocol:** `docs/plans/COMMAND_PLANE_MULTIAGENT_PROTOCOL.md`

---

## The problem

The dashboard has **26 routes**. Four of them clone the same shell with a different "current" tile. `/dashboard/opportunities` is in the nav but has no `page.tsx`. The cockpit page (`/dashboard/control-surface`) is the only one with real operator-action affordances, but it's buried at position 2 in a flat 17-item COMMAND nav. The rest is decoration (`AmbientParticles`, `ScanLines`) or scaffolding that never finished.

The operator can't find the surface that matters because nothing has been declared canonical.

## What we're aiming at

An **observatory-leaning cockpit** — watch most of the time, intervene when something matters. Built as **seven verb-zones** (operate, converse, observe, evaluate, relate, sense, recall) arranged in a hexagonal 1+6 spatial frame. Each zone has its own *cadence* (operating refreshes per second; remembering breathes per hour — like a body with different rhythms in different regions).

The visual register is **Nihonga (日本画) / iwa-enogu** — mineral pigments grounded in 400 years of Edo painting (Hokusai's Gunjō, Sesshū's Sumi, Kōrin's Bengara). Not because Japan is fashionable; because the discipline of using 3-5 mineral colors with semantic purpose is the opposite of the AI-template aesthetic. Numbers are the protagonist. UI chrome is stage-hand.

**2D is canonical truth.** Each zone has a clean 2D rendering. 3D is opt-in per zone, gated on a 60fps benchmark, only where it earns its keep. No always-3D substrate, no "wonky now refined later" promise that history would punish.

## What "world-class and bleeding edge" means here

Not "Linear with better graphics" — Linear is already world-class. The bleeding-edge move is **substrate-as-surface**: the UI exposes dharma_swarm's own structure (catalytic graph, agent activity, evidence chains) as the navigation, not as decoration on top of a generic SaaS shell.

It is **earned** by the cultural anchor: Dhyana carries 400+ years of Japanese aesthetic discipline through actual practice. The Nihonga palette is not cosplay because the practitioner is real. No competitor can clone the surface without first earning the substance.

The bleeding edge is what's **earthen rendered with discipline**.

## What it's NOT

- Not an R_V framing. R_V is research, not a UI substrate.
- Not a "living system" metaphor with poetic gloss. Each zone has its own *cadence* — refresh rate, not metaphor. Code says `cadence`.
- Not a fractal-everything Procrustean architecture. Zones share a *grammar* (`{verb, signal, cadence, children?}`), not chrome.
- Not always-3D. 2D is the canonical truth; 3D is garnish where it earns.
- Not a rewrite. Existing `/dashboard/control-surface` with its 4 cockpit components is the foundation; v2 refines and extends it.
- Not new substrate. The renderer-agnostic data layer (FastAPI → typed row models → either renderer) IS the substrate; both 2D and 3D views over the same model.

## Why a queued track, not active

`trace-identity-coverage-2026-05` is the formally active track. Its non-goals include *"Do not add dashboard/API surface unless it is implemented and manifest-registered."* Per governance, only one ACTIVE track at a time.

This work is queued behind it. When trace-identity closes, this track opens. The spec, checklist, and multi-agent protocol exist now so the next operator (human or agent) can pick up in <5 minutes without re-running the grill.

## The single sentence

**A Nihonga-anchored observatory+cockpit where the substrate is the surface, the numbers are the brand, and seven verb-zones breathe at their own rhythms.**
