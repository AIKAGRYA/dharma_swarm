# HELM Effect Lane — operator decision packet (design only, nothing built)

status: PROPOSAL_AWAITING_OPERATOR_WORD
author: night-watch takeover (claude), leg-two P7
locus: codex/helm-legtwo-20260902 · Johns-MacBook-Pro

## The desire this answers
The operator's stated dream (2026-09-01→02): run real work — an RSI cycle, a
capital drill, a workflow — *from the cockpit seat*. Today that is structurally
excluded by design: the chat lane is no-tools, narration authority NONE, and the
Wayfinder plan §8 forbids any "post-hoc approval or broad effectful hand." That
exclusion is what makes the current seat trustworthy. This packet proposes the
ONE lawful door through it, and builds nothing until the operator rules.

## Design: the typed one-shot effect hand

```
OwnedEffect<Owner, Scope, OneUse>
  owner:   the canonical Python owner that will execute (never the model,
           never the terminal) — e.g. capital_lab.risk_governor drills,
           forge_lab rsi newrun --preset fast, gaia_sis_night_ledger report
  scope:   an enumerated effect id from a REGISTRY committed in the repo —
           free-text commands are never effects
  one_use: minted per request, expires in 120s, single redemption
```

Flow (two-tap, mirrors OwnedContext):
1. Operator types intent ("run the capital drills"). The terminal maps it ONLY
   against the effect registry (local match, never model-invented).
2. The Python owner mints `OwnedEffect` + shows a confirmation card: owner,
   exact command, writes it will make, budget. Model prose CANNOT mint.
3. Operator confirms (Enter on the card = tap two). Terminal redeems the
   one-shot; owner executes in its own process; every stdout/stderr line lands
   as typed events; an EffectReceipt (boundary → start → end → outcome,
   authority=OWNER_EXECUTED) goes to the session store.
4. Timeout/decline burns the token. A replayed or forged token is refused by
   the same one-shot cache discipline the context handoff already proved.

## What keeps it lawful (invariants)
- Registry-only scopes: adding an effect = a reviewed commit, never a prompt.
- The chat model never gains tools; it can only *suggest* a registry intent,
  and the suggestion renders as `authority NONE` prose exactly as today.
- Two taps minimum, card shows the real command; no standing approvals, no
  batch approvals, no "yolo" flag in v1.
- Receipts are stamped by the owner; the terminal renders, never asserts.
- Kill switch: an env-less file flag (`~/.dharma/helm/EFFECTS_DISARMED`)
  fail-closes the whole lane; doctor reports its state.

## Threat cases considered
- Prompt-injected "run X": model prose can't mint; registry match is local. DEAD.
- Token replay after cancel: one-shot cache + 120s expiry. DEAD.
- Registry drift (effect does more than its card said): card text is generated
  from the owner's own declaration at mint time; a mismatch test pins it.
- Operator fatigue (rubber-stamping): v1 keeps effects rare and coarse; the
  card shows writes, not vibes. Revisit only with usage receipts.

## Cost of NOT building it
Every "use the cockpit copiously" ambition dead-ends at narration; operators
shell out to run anything, splitting receipts from the seat that asked.

## The one decision
**Build the effect lane v1 (registry + OwnedEffect + two-tap card + receipts,
~1 slice) — yes or no?** A yes starts a normal slice through the same
build → no-mistakes → iterate loop; a no keeps the seat read-only and this
packet stands as the recorded design.
