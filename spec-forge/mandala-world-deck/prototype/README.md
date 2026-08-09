# Mandala World Deck — interactive fixture prototype

This is a disposable, self-contained browser prototype. It uses synthetic fixture data, makes no network requests, holds no credentials, and cannot execute commands against Dharma Swarm or any external system.

## Open it

```bash
cd /private/tmp/dharma-world-deck-spec.M4gvRb/spec-forge/mandala-world-deck/prototype
python3 -m http.server 4173
```

Then open <http://127.0.0.1:4173>.

## What to try

1. Take the 30-second tour.
2. Select each of the three quest pins.
3. Switch between **World**, **Decide**, **Run**, and **Evidence** without losing the selected quest.
4. Compare the map with its complete list equivalent.
5. Toggle **Neutral** and **Gameful**; literal facts and permissions remain unchanged.
6. Save a proposal-only decision draft. It exists only in the current browser tab and sends nothing.
7. Pause motion and pause the run-following view.
8. Narrow the browser to phone width and use the full experience with keyboard or touch.

## Deliberate fixture cases

- **Runtime Spine Hardening:** specified, permission expired/proposal-only, execution running, verification passed but stale and contradicted, outcome unobserved.
- **World Radar Intake:** mixed-time and incompatible scopes; the prototype refuses to join or rank them.
- **External Contact Loop:** outcome measured, target not met, causal attribution unknown.

## Limits

- This is not integrated into Cockpit V2.
- It does not read real APIs or represent current system state.
- It is a product-feel prototype, not implementation proof or permission to build the live command surface.
