# moltroad.com/bounties — Landing snapshot

Fetched: 2026-05-20

## Site self-description
"Molt Road - where agents trade in the shadows"
"For entertainment purposes only. All listings, items, and transactions are
fictional and part of a role-playing game for AI agents. Nothing on this site
constitutes real goods, services, or illegal activity. $MOLTROAD tokens have
no monetary value."

## Links observed
- /skill.md — API docs (similar pattern to Moltbook)
- x.com/moltroad — twitter handle
- moltbook.com/m/moltroad — has a submolt presence on Moltbook itself

## Architectural pattern (inferred from naming + pattern match w/ Moltbook)
- "skill.md" suggests same Karpathy-style markdown-skill distribution
- Marketplace topology: bounties, agents (URLs /bounties, /agents observed)
- Pseudonymous reputation per ToxSec writeup
- USDC on BASE for escrow (per ToxSec) — token has "no monetary value" per
  the disclaimer, but USDC settlement is referenced in coverage

## Tension
The legal disclaimer ("entertainment purposes only", "no monetary value")
strongly suggests the site operators are aware that the project might be read
as facilitating illegal trade. Coverage (ToxSec, Infostealers, ClawNews) treats
it as a real black market; the site treats it as a role-playing game.

This is the central ambiguity:
- IS Molt Road a working agent commerce surface (escrow + reputation)?
- IS the legal disclaimer the only thing keeping the operators out of court?
- Or IS it actually a role-play / canon-building exercise inside the Moltbook
  cultural artifact (similar to molt.church)?

The presence of `m/moltroad` on Moltbook + the marine-themed naming + the
disclaimer text suggest it is cosmologically part of the Moltbook canon, not
a separate enterprise. But the API design (claim / submit / verdict, escrow,
reputation) is non-trivial and would work as real infrastructure if pointed
at real settlement.

Status: WORKING-CODE-WITH-LEGAL-DISCLAIMER. Probably runs as fictional canon
with real plumbing.
