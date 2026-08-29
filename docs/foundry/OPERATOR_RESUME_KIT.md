# Operator Resume Kit — start here when you've forgotten everything

**Role:** reference (operator kit). No runtime/merge/governance authority.
Owned by `organism-rewire-2026-07` (next-item 15). Written for a mobile,
intermittent-wifi operator who does not need to remember what they built —
the system remembers for you.

If you opened this and have no idea where you are: that's fine. Do step 1.

---

## 1. The restart line (paste this to a fresh cloud agent from anywhere)

> Read `docs/foundry/OPERATOR_RESUME_KIT.md`, the latest walking-brief issue,
> and `docs/governance/ACTIVE_TRACK.yaml`. In 3 lines tell me: what's running,
> what's waiting on me, and the single highest-leverage next thing. Then do
> that next thing and open a draft PR.

That one line is both your all-nighter kickoff and your after-a-week-away
restart. Same line every time. The agent reads the state back to you — you
never have to recall it.

## 2. Your daily glance (30 seconds, on your phone)

Open the pinned **Walking Brief** GitHub issue. It posts once a day and tells
you, in phone-sized chunks:

- whether anything is halted (kill-switch),
- what is waiting on your one tap (Needs John + Merge window),
- the Sublimation Foundry lane health (green = fine, red = look),
- the one-time unblocks still pending.

If you read one thing a day, read that. It is your external memory.

## 3. Your three recurring one-tap actions

Only these are ever truly yours. Everything else the system does itself.

1. **Merge.** In the brief's "Merge window", tap a walk-ready PR → merge (or
   ask for changes). This is how work you and agents did actually lands.
2. **Approve the wedge, once.** The first paid product can't go out until you
   say yes to the offer + price in `docs/offers/agent-behavior-verification.md`
   (gate 1 in `reports/revenue_wedge/first_cash_receipt_status.md`). One yes,
   one time.
3. **Keep the lights on.** If a provider credit runs low, top it up
   (`docs/foundry/OPERATOR_UNBLOCKS.md` lists the admissible routes). That's the
   whole "funding" job for now.

## 4. Your one stop button

If anything ever feels wrong: GitHub → Actions → run **`loop-emergency-stop`**.
One tap halts every automated lane. The Foundry does not resume from marker
deletion or a generic `loop-resume`; it requires the halt-bound OpenSSH-signed
procedure in `docs/foundry/RUNNING_NONSTOP.md`. This is what lets you walk away
without watching — being gone is never risky.

## 5. What this even is (for total memory loss)

You are building a **witness**: a system that turns claims into receipts. The
Sublimation Foundry points it at open-source AI code (improve it, verify it,
publish the misses) and at other people's agents (a ~$2,500 "did this agent do
what it claimed" check). The money and the receipts feed the swarm's own
evolution. You don't run it by remembering it — you run it with the restart
line and the daily glance. That's the whole system.

---

*If this file is stale, the restart line still works — it will tell you what
changed. Trust the walking brief and ACTIVE_TRACK over this page.*
