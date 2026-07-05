---
name: roast
description: Stress-test an idea — or Claude's own work/plan — with a multi-persona adversarial council that defeats sycophancy, then return one verdict (GREEN / RESHAPE / KILL) plus the single cheapest test to run in 48h. Use before committing to a business idea, a build plan, a launch, a pricing call, or any decision where "Claude agreed with me" is a risk. The opposite of asking one model "is this good?".
---

# Roast — the anti-sycophancy council

Models fail to push back on the way you framed something ~88% of the time (the "ELEPHANT" finding;
humans ~60%), and personalization + a long conversation make them *more* agreeable, not less. So a
single Claude grading your idea is the worst possible judge — it wants you to like it. Roast replaces
that with a **council of adversarial personas run as separate agents with clean context**, then a judge
who never authored any of the analysis. This is the orchestrator stance: you conduct, the council works.

**Default posture is skeptical.** A roast that returns GREEN with no fatal flaws found is suspect — push
the contrarian harder. KILL and RESHAPE are the honest common outcomes.

Verdict definitions (use exactly these):
- **GREEN** — pursue as framed; the cheapest test is a confirmation step, not a rescue.
- **RESHAPE** — the core has value but a load-bearing assumption is wrong (buyer, channel, price, scope); the verdict must name what to change.
- **KILL** — the fatal flaw survives the expansionist's best case; stop, don't optimize.

## When to invoke

Before spend, before a launch, before building something non-trivial, before a pricing/positioning call,
or to stress-test Claude's *own* finished work (not just ideas). For ARTHA_CREAM (the revenue/campaign
lane — any work whose output is outreach, spend, or a paid offer): **every campaign idea passes roast
before any spend or outreach** — with the buyer persona load-bearing.

## Procedure (conductor)

1. **Frame** — restate the idea/work in one tight brief: what it is, who pays/benefits, the claimed
   edge, the cost of being wrong. Ask the user at most **3** sharp scoping questions only if the brief
   is genuinely ambiguous (target buyer? your real edge/distribution? budget + how fast to first
   dollar?). Don't stall on it — if unanswered in one exchange, state your assumptions in the brief
   and proceed.
2. **Fan out the council** — spin up the five working personas below as **parallel agents in ONE
   message** (the `Agent` tool; or the `Workflow` judge-panel pattern for heavier runs). Each gets the
   same brief and its own clean context. They do NOT see each other's output, and none may be told
   what verdict you expect.
3. **Judge** — a final, separate synthesis agent (it must NOT have authored any persona's analysis)
   reads all findings and returns the verdict block. Worker ≠ judge.
4. **Hand off** — if revenue-relevant, hand the verdict to the ARTHA_CREAM lane. Record non-obvious
   learnings.

## The council (each a separate agent, clean context)

| Persona | Sole job | Bias to enforce |
|---|---|---|
| **Contrarian** | Find the fatal flaw. Assume it fails — explain why. | maximally skeptical; scores low |
| **Expansionist** | Find the biggest realistic upside and the wedge to it. | optimistic; names the 10x path |
| **First-principles** | Reason from pure logic, *no* outside context or hype. | ignores what's trendy |
| **Deep-researcher** | Pull REAL market size, competitors, pricing via whatever research tools are live (web search, deep-research skill, tavily/exa if configured). | evidence only; cite sources |
| **Buyer** | Role-play the actual customer. Decide out loud: "I'd pay \$X / I wouldn't — here's why." Name the churn/CAC objection. | brutally self-interested |
| **Judge** | Synthesize all of the above into ONE verdict + scores + the cheapest 48h test. Authors none of the analysis. | decisive; no hedging |

Scoring: the four *opinion* personas (contrarian, expansionist, first-principles, buyer) each end
their analysis with a 0–10 viability score. The deep-researcher supplies evidence, not a score; the
judge weighs its findings when scores conflict. If the deep-researcher can't source a load-bearing
number, the judge must say so in WHY rather than let an invented number stand.

## Output format (the verdict block)

```
ROAST VERDICT: <GREEN | RESHAPE | KILL>   confidence: <low|med|high>
One line: <the call, blunt — what to kill, what to keep, where to aim>

WHY: <2-4 sentences — the load-bearing reasoning>
BIGGEST RISK: <the single thing most likely to kill it>
BIGGEST UPSIDE: <the realistic 10x if it works>
BUYER READ: <would the role-played customer actually pay? the real objection>

SCORES (x/10):  contrarian <n> · expansionist <n> · first-principles <n> · buyer <n>

▶ CHEAPEST 48h TEST: <the single, concrete, falsifiable action to run in the next 48 hours
  that tells you if this is worth pursuing — BEFORE writing any code or spending money.>
```

The **cheapest 48h test is mandatory** — a roast without one is incomplete. It converts "reshape" from
a vibe into one runnable next step. It must be falsifiable: name the action, the sample, and the
numeric threshold that counts as signal.

### Example of a great verdict block

```
ROAST VERDICT: RESHAPE   confidence: high
One line: kill the subscription, keep the audit — sell it as a $500 one-off to agencies, not a $19/mo tool to freelancers.

WHY: Freelancers churn out of $19/mo tools in under 90 days (buyer persona wouldn't renew; researcher
found 3 comparable tools with public churn complaints). But the same audit is a deliverable agencies
already bill clients for, and the contrarian's "nobody pays for reports" objection collapses at the
agency tier where the report IS the product.
BIGGEST RISK: agencies build this in-house with a GPT wrapper in an afternoon.
BIGGEST UPSIDE: productized-service wedge → retainer relationships → the actual 10x is the retainer, not the tool.
BUYER READ: agency owner pays $500 if the sample audit finds one issue their client would fire them over; balks at anything recurring before value is proven.

SCORES (x/10):  contrarian 3 · expansionist 7 · first-principles 5 · buyer 6

▶ CHEAPEST 48h TEST: send the sample audit to 15 agency owners you can reach warm; ask "would you pay
  $500 for this on your worst account?" ≥3 unambiguous yeses = proceed to one paid pilot; 0-1 = kill.
```

## Rails (do-nots)

- The judge must be a separate synthesis turn, never a persona that wrote analysis (worker ≠ judge).
- Never tell a persona the verdict you expect or share another persona's output with it.
- Deep-researcher claims must carry sources; no invented market numbers — an unsourced number is
  flagged in WHY, never silently used.
- Never return a verdict without the 48h test, and never a test without a numeric threshold.
- Never soften a KILL into a RESHAPE to be kind. That is the exact failure this skill exists to stop.
- Roast *proposes*; it does not spend, launch, or act. Acting on a GREEN is a separate, gated decision.

---
*Provenance: adapted by THE MAGPIE from the "4 upgrades to Claude Code" video (technique card
`~/.dharma/magpie/library/four-upgrades-claude-code-money.md`). BUILT 2026-06-26, additive/reversible.
NOT yet A/B-adopted — no separate-evaluator win logged; run the cheapest-test comparison before
promoting via find-skills.*
