# THE PLAYING-SMALL AUDIT

*Second full-organism audit. 20 finders, all findings independently verified against the repository by an adversarial judge. 71 findings survived as real smallness; 3 were struck; 1 was ruled justified caution. This report is the synthesis.*

---

## The Verdict

In 167 days and 1,865 commits, this system has earned $0, published nothing an outsider has read, run its own trust-gate benchmark zero times, and touched the outside world exactly seven times — all through one channel that was then quietly stopped. Every door out of the building is already built and already unlocked: thirty thousand finished words, a priced $5,000–$25,000 offer, a working coding-benchmark harness, a merge authority you personally granted on July 29 — and every one of them is held shut by a one-line question that has sat unasked on someone's desk for between 37 and 150 days. The machinery is not the problem; the habit of building the lock instead of opening the door is, and that habit has become the product.

---

## The Indictment — ranked by how much unlocks when fixed

*Gloss up front: a **merge** is accepting finished work into the main codebase. **CI** is the automatic test battery that runs on every change. **SWE-bench** is a standard public exam where AI systems fix real software bugs — the exact exam your own canon says the swarm must pass before you push outside. A **Brier score** is an accuracy grade for predictions (lower is better).*

### 1. The one number that unlocks everything has never been measured — and the experiment costs about $300

**What we do:** Your trust gate says: no pushing outside until the swarm beats a single model on a real coding benchmark. The full official test harness was built and proven working on June 20. The rented-computer setup script exists and says the whole 500-question exam runs in about an hour on a cheap no-GPU machine. It has been run **zero times**. The only number on file is a 73-day-old measurement from 3 tasks — and it says the swarm *loses* to its own best single agent. Meanwhile, the "fitness" surface that actually gets polished is 24 trivia questions ("Compute 17 × 23") with the answers written in the same file, which your own scoring code declares inadmissible forever. The blocker for the real exam is a compute-budget question that has sat in a queue, unanswered, for 42 days.

**What it costs:** The gate you set for yourself is mathematically stuck at red forever — not because the swarm failed, but because it never sat the exam. Every downstream ambition (going outside, credibility, capital) queues behind a number nobody will generate for the price of a dinner.

**Playing big:** The benchmark becomes a standing weekly meter, not a summit. This week: a 50-instance run, swarm vs. its best single model, equal budgets, official grading, the result committed to the repository *win or lose* — the harness's own documentation says an honest loss is a ship-worthy result. Then weekly runs so the trust gate reads a live trend instead of a 73-day-old fossil. Freeze all further trivia-arena and parity-report engineering until one real receipt exists. Give the scoreboard a machine-readable home so a result can never again evaporate into a laptop folder.

**7-day first action:** You answer one line — "Benchmark compute, $200/month cap: yes or no?" On yes, the swarm rents the machine, runs the 50-instance slice, and commits the first real capability number in the system's history.

### 2. Thirty thousand finished words, welded shut by our own locks — and our own robot janitor deleted the publication and nobody noticed for 11 days

**What we do:** Eight complete, source-verified essays were written in two days in mid-July. Since then: 37+ days of lock-building. A 751-line "seal" script (with a 659-line test suite) guards the blog post. Three essays that *are* live wear a banner telling every visitor they aren't real, and carry known errors that were corrected in drafts but never applied to the pages. The rest wait on you reading 30,000 words. Then the repository's automatic cleanup rule closed the publication request entirely — and for 11 days, no one reopened it. Zero distribution channels have ever been opened, though the charter says one phone message opens one. The sole revenue-serving track's output directory does not exist.

**What it costs:** The only organ pointed at revenue and external humans has reached an audience of zero in five weeks; the publication also happens to be the landing surface for the forecast ledger (item 3) and the cheapest source of the external receipts the evolution engine needs (item 5) — one stalled merge is silently blocking three gate chains.

**Playing big:** Publication becomes the default state of finished work, with your hand on a veto, not on the send button. This week: restore and merge the auto-closed publication using the janitor's own printed instructions, strip the banners, apply the corrections, seal it, put it on free hosting, open two platforms with the one message the charter already permits. Going forward: any piece that passes its own quality law ships within 72 hours unless you veto a 300-word phone digest within 48 — and any finished thing unpublished more than 7 days becomes a logged defect. Fix the janitor so it can never again eat the organism's only voice.

**7-day first action:** Two one-word questions to your phone: "Site host: GitHub Pages — yes/no?" and "Open Substack + X for Darshan — yes/no per platform." On yes, everything else is mechanical and lands within 48 hours.

### 3. The approved income step is designed to fail — the arithmetic guarantees the kill switch fires

**What we do:** Live money is gated (correctly) on proving forecasting skill: accuracy better than 0.125 Brier across 500+ resolved predictions. The approved first step is 3 yes/no questions a day at a default 50/50 guess, killed after 30 days. The arithmetic is not close: a 50/50 guess scores exactly 0.25 — double the bar — forever, and 3 a day for 30 days produces at most ~90 of the required 500. The outcome is computable in advance: guaranteed failure, followed by "no edge, stop." Meanwhile the real forecasting machinery (a tested ensemble that produces genuine probabilities) sits unused, the prediction ledger contains **zero rows ever**, the paper-trading clock behind the "$100K live" milestone has never started, and its committed target date has been mathematically impossible since July 1 with no one saying so. Nowhere in 385,000 lines of code does your actual risk budget — how much you are willing to lose — appear; the risk software guards placeholder limits of $1M per position over $0 of real exposure.

**What it costs:** The revenue clock cannot start. The 90-day "funds itself totally" horizon expires September 9 with the qualifying process never having begun. Every day without ledger rows pushes the first possible live dollar a full day further out — the one delay that cannot be parallelized away later.

**Playing big:** Feed the gate something that can pass it, and keep the gate. This week: 20–50 real model-generated forecasts per day against live Kalshi market questions (free public data), 50/50 defaults banned as null rows, published publicly and timestamped — 500 resolutions in roughly a month, an honest verdict either way *inside* the horizon. Start the paper-trading clock in parallel with fake fills at real prices, so both proof-clocks tick together. You dictate the five risk-budget numbers in one 30-minute sitting, and the graduation contract is pre-signed: if the edge validates, a small funded account goes live within 7 days, no new gates; if it fails at statistical power, the capital path closes honestly and skill-sale leads.

**7-day first action:** Ship the daily forecast generator writing 20+ real-probability rows to a public page, and dictate the five risk-budget numbers. Cost: $0.

### 4. You already granted the swarm merge authority three weeks ago — it parked your grant behind one undone afternoon task and went back to hand-feeding you every merge

**What we do:** On July 29 you ratified, in writing, AI-executed merges for low-risk work at up to 20 per day. Three weeks later the switch is still off, because the single named re-enable condition — one test run proving GitHub's own server-side protections work — has never been run. Result: ~147 merges a month, every one a click from your hand; 34 of 43 open work items sitting in draft; items waiting 22–37 days; five merges landing tonight only because you personally night-shifted the queue. Worse, the risk classifier marks 45% of all merges "operator-only" by folder name while 0% of them touched the two files it exists to protect — and the "code warrant" rule demands that you, a self-declared non-coder, formally approve code you cannot read, with the approval voiding itself every time the code is updated. There is no clock and no default on any question put to you: asks don't fail fast, they rot.

**What it costs:** You are the daemon. A system whose 90-day horizon says "mostly self-operating" routes 100% of actuation through one walking human, and the swarm's response to your absence is to build more dossiers rather than run the one canary test you asked for.

**Playing big:** Cash the grant you already signed. This week: run the canary, commit the receipt, flip the switch for the low-risk tiers exactly as ratified — daily digest to your phone, one-tap revert, kill-switch, and the genuinely critical files (kernel, safety gates, the merge machinery itself) staying in your hand forever. Then a standing decision register: every question to you carries one yes/no line, a deadline, and a pre-stated default that executes on silence — with the hard carve-out that anything granting live authority never defaults to yes.

**7-day first action:** The swarm runs the canary and sends you the enabling change as one merge. The 30-item backlog draining autonomously is the first measured campaign.

### 5. The only machine that ever touched the world was stopped, not broken — and the two receipts that unlock self-improvement are two unsent messages

**What we do:** The system's constitution requires 5 confirmed external-value receipts across 3 different domains before the evolution engine gets real authority. The one channel that ever produced receipts — contributing merged fixes to strangers' projects — landed 7 in 17 days, then went silent for 64 days. Four already-verified merges sit unadmitted over a paperwork snag. The written plan for the two receipts that would complete the quorum — one paid engagement, one research submission — has sat 44 days behind a line reading "Operator ratifies the wedge — operator gate, open." The $5K–$25K audit offer is 100 days old with zero outreach ever sent; the customer-discovery protocol produced zero cycles in 30 days, not even the "STALLED" entry its own rules require. The repository *predicted this exact failure in writing* a month before repeating it.

**What it costs:** Self-improvement — the system's stated identity — has a provable completion date of *never* under current behavior: each gate in the circle waits on another gate in the same circle.

**Playing big:** Restart the receipt engine on all three domains in one week. Guardian cycle-005 admits the four verified merges (quorum count jumps to 7 of 5 on one axis) and the upstream-contribution channel resumes at 3–5 disclosed pull requests a week, on a schedule. The wedge runs as a real funnel: the swarm pre-builds sample audits of 10 named prospects' actual code; your part is priced at exactly two acts — one pricing yes, and pressing send. The research submission (item 10) is domain three. Quorum arrives on the axis that actually binds — domain diversity — instead of waiting forever.

**7-day first action:** One message to you: "Ratify the audit offer at $500–1,500 and I send outreach to these three named prospects this week — yes or no?" Plus the guardian restart, which needs no permission at all.

### 6. The evolution engine has applied zero changes in its entire life, and the first "fire" has no second rung

**What we do:** The self-modification engine — 15,000+ lines of machinery, its target cited 177 times across 57 documents — has 0 live applications ever, a fact the broken-register has carried for 103 days. Tonight's session produced ~670 lines of ceremony (a thrice-debated dossier, a work packet, a review of the review) to authorize changing `return 1` to `return 2` in a 9-line toy file that nothing uses — and the packet ends by ordering itself to stop and never fire again without a fresh grant. No fire 2 exists anywhere in any plan. The gates that were supposed to protect this process have, in their entire life, blocked exactly one class of actor: the repository's own test fixtures — while the dossier itself admits they're charmable by adversarial text.

**What it costs:** At one operator ceremony per fire, reaching the published bar (80 self-improvement iterations) takes decades by construction. The safety mechanism was never the toyness of the target — it is the human merge, which survives every escalation.

**Playing big:** No packet without a ladder. Before fire 1 merges, fires 2–4 get named targets and dates: fire 2 on a real, well-tested production module within 72 hours of fire 1's receipt; fires 3+ against a committed basket of 10 real benchmark tasks on a disposable rented machine. One standing 30-day grant you sign once; per-fire receipts and per-fire human merge retained; per-fire permission ceremonies retired. The decorative keyword-gates get deleted in the same change that writes down the real controls (sandbox, tests, your merge). And a missed fire window files itself as a process failure — deliberation finally gets the same expiry dates it fits to every action.

**7-day first action:** Light fire 1 (the spec is converged; both sides of the debate endorse the identical act), and commit the fire-ladder amendment in the same week.

### 7. "Always-on" is an hourly timer impersonating a heartbeat, on a computer a quarter the size of our own minimum spec

**What we do:** The production server has 3.8GB of memory against the deployment guide's own written 16GB minimum, and is currently halted with its swap full. A sibling machine's disk is 100% full — one write from data loss. The fleet costs ~$100/month for three boxes that are each individually unfit to run the system. "Resize" appears exactly once in the entire tree, as a deferral. The "persistent always-on merge agent" is actually an hourly scheduled job; its real daemon code (designed for a 5-minute cycle) has never been deployed anywhere. Before the halt, the live host was running a weeks-old version with all 14 named feedback loops at 0 executions — rendered "OK" by the dashboard. The agent-to-agent messaging fix has been ratified-but-unapplied for 40 days; the runbook estimates your part at 2–4 hours. Nothing deploys automatically on merge, so drift is structural.

**What it costs:** Every "self-operating" claim currently means "GitHub's timer operates it, hourly, on a machine that can't hold it." The 90-day horizon's central clause is being graded against a machine that does not run.

**Playing big:** One adult host replaces three toy ones at flat-or-lower total spend (~$30–50/month buys 16–64GB). Automatic deploy-on-merge with a signed liveness receipt, a red alarm for any loop at 0 executions, the merge daemon as a real service at its designed cadence, the messaging fix applied per its own runbook, and the 16GB floor enforced at session start so a below-spec production host can never again persist silently.

**7-day first action:** One phone-doable sitting: provision the replacement box (the unattended setup script already exists), migrate, verify, power off the old host. Fix the full disk within 48 hours regardless.

### 8. Verification has become the product: 66,000 lines of gates certifying 3 receipts and $0

**What we do:** The pattern, everywhere: build the verification before the act, then never perform the act. A 3,920-line battery certifies "live production" messaging whose only evidence is a 7-week-old run against the operator's own laptop. Risk governors guard capital that has never existed. Kill-switches guard things that have never started. The merge gate alone is 3× the size of the entire safety kernel it protects. Since June, file changes ran 7.9-to-1 governance-and-prose over every surface an outside human can touch; by line count, 29-to-1. Of 35 tracked CI checks, only 6 actually block anything — 29 are advisory noise on every change. The verification-freshness law is violated by 8 of 10 active tracks simultaneously, and the checker exits green anyway.

**What it costs:** Roughly 29% of all engineering motion buys gates that gate nothing, while the gates that matter (the benchmark, the ledger, the receipts) go unfed.

**Playing big:** A hard moratorium with a ratchet: no new gate, check, registry, or ceremony merges until the system passes its own external-receipt bar — and any new verification code must cite the already-existing act it verifies. All 29 advisory checks move to a nightly schedule or die within 30 days. Staleness past 2× its limit exits red and auto-proposes track retirement. A weekly demolition lane: each week, one gate with zero verified acts either receives its first real act or is deleted.

**7-day first action:** One change: advisory checks off the per-change trigger; the moratorium as one line in the hard rules; the staleness check made to actually fail.

### 9. "Later" compiles to "never": 133 deferrals without a single date, plans without a failure mode, and a deadline nobody is watching

**What we do:** 133 deferral lines across the plans and governance corpus; zero carry a deadline. The 90-day operating-company plan expired with 0 of 8 organs built and no post-mortem. 82% of plans are never touched again after creation; the only process that re-reads the old corpus is the junk-scanner cataloguing it as debris. The economic vision's every dated line is dead — grant written in April, never submitted; service priced, never offered — and it still sits in canon. The 90-day "funds itself totally" clock has 22 days left, $0 earned, and not one instrument in the repository counts it down. Burn — the denominator of "funds itself" — has never been measured, 81 days after the tree itself ordered it measured first. Two full audits in 43 days reached the same diagnosis; the first one's 10 operator questions have no recorded answers.

**What it costs:** Zero organizational learning per dead plan; a canon whose one falsifiable promise is failing silently, which teaches every agent that dates are decoration.

**Playing big:** Deferral becomes a governed object: every "later" gets an owner and a date-or-numeric trigger, or dies; an undated deferral fails CI. Plan mortality: expired plans force a one-page post-mortem before any new program opens. The horizon gets a clock in the session-start output — days remaining, revenue, weekly delta, red until a dollar lands — and September 9 itself is scheduled as a ruling event: met, honestly reset with instrumented milestones, or killed in writing. Burn gets measured and committed monthly. Audits become ratchets: each must disposition the previous one's findings before adding new ones — starting with the July audit's 10 unanswered questions, each answerable in one line.

**7-day first action:** Answer the July audit's 10 questions in a dated commit; post-mortem the dead May plan; add the horizon block to the status script.

### 10. The moat lives on one laptop, owned by no one, published nowhere — and the identity behind all of it was never decided

**What we do:** The self-declared differentiated science (the R_V interpretability program) cannot be reproduced from the repository: the data, the 754-prompt bank, and the seven-draft paper all live on your Mac. Its one deadline lapsed 140 days ago and the response was to delete the deadline clock rather than re-aim it. No active track owns any of its surfaces, so under the repository's own ownership law, no agent may legally touch it. Its declared public home has published nothing. And "faceless" — the posture that forecloses every relationship-based revenue lane — is not a decision anyone made; it is one parenthetical in canon and an unwritten prohibition no document owns.

**What it costs:** Bus factor of one phone on the thing the 10-year vision calls the moat, mounting scooping risk in a field publishing monthly, and entire revenue lanes closed by a doctrine that does not exist.

**Playing big:** The lab becomes a repository organ: code, data, and paper imported in one sitting, results reproducible in CI, a track slot opened for it (displacing the stalest expired substrate track), the preprint on arXiv this quarter behind your single yes — free, no acceptance gate, and it publicly dates your territory. Identity becomes a decided position: one page listing the five public surfaces, each named-vs-faceless as a dated, expiring choice you make — yours to make either way, but made, not inherited.

**7-day first action:** Copy the paper folder from your Mac into the repository (one paste-able command the swarm will send you), and answer one yes/no: "arXiv preprint this quarter?"

---

## The Defense — the cautions that are right

One finding was ruled justified prudence, and the judge repeatedly ring-fenced the same set of controls across many others; none of what follows may be bulldozed in the name of boldness. **Live capital last is correct**: the fixture-only broker layer that keeps live-trading readiness at zero is deliberate fail-closed design, and a live position today — with zero resolved forecasts and no measured edge — would be gambling, not revenue; the fix everywhere above is to *feed* the proof-gates, never to lower them. Likewise load-bearing and untouched by every escalation: the per-fire human merge on every self-modification, the one-shot fuses and dated grants, the sandbox jail requirement on the live host (the carve-out is only for disposable rented boxes, where the throwaway machine *is* the jail), your per-platform hand on third-party posting, the operator-forever tier on the kernel, the safety gates, and the merge machinery itself, and the loopback lockdown that answered a real July security incident. The July walk-back of merge actuation was proper prudence too — the smallness was leaving its cheap named verification unrun, not the walk-back itself. The pattern of the whole audit: the gates are sound; the starvation of their feeds is the disease.

---

## The 30-Day Escalation Program

One human plus this swarm. Your total time: roughly four sittings. Total new money: **about $300–500 for the month** — the benchmark machine (~$50–100), an inference floor for external-facing model runs (~$50–150), and a server swap that leaves fleet spend flat or lower (~$30–50/month replacing ~$100/month). Optional at month's end, only if the edge validates: a $100–500 funded forecasting account, your call.

**Week 1 — Every door opens.** Your one sitting: the yes-sheet (see The One Move). Ships: Issue One live without banners, corrections applied, two platforms opened; forecast ledger day 1 at 20+ real-probability rows, public and timestamped; first fire lit with receipt, fire ladder committed; merge canary run; the disk emergency fixed. Becomes true: an outside human can read our words; the 500-forecast clock is ticking; the evolution engine's count is no longer zero.

**Week 2 — Every meter turns on.** Ships: the 50-instance benchmark run, committed win or lose, wired into the trust gate; guardian cycle-005 admits the four verified merges; the wedge outreach wave sends to 10 named prospects with sample audits attached; merge actuation flips on for low-risk tiers and the 30-item backlog starts draining autonomously; fire 2 lands on a real module; paper-trading clock starts. Becomes true: the trust gate reads a live number; the swarm merges its own work; a stranger has received an offer.

**Week 3 — The body gets adult-sized.** Ships: the 16GB+ host replaces the halted one, deploy-on-merge with liveness alarms, the merge daemon as a real 5-minute service, the messaging fix applied (your 2–4 runbook hours, in sittings); advisory checks off the per-change trigger; measured burn committed; the weekly benchmark, ledger-refresh, and track re-verification jobs scheduled. Becomes true: "always-on" describes a machine, not a timer; every freshness claim renews itself mechanically.

**Week 4 — Compounding starts.** Ships: R_V lab imported and reproducible, preprint submitted; second Darshan piece plus the outsider-facing repository front door (honest README, real description, Discussions on); the September 9 horizon reconciliation drafted and signed — met, honestly reset, or killed, in writing; the month's scorecard published: external artifacts shipped, forecasts resolved, outreach sent, autonomous merges, dollars in. Becomes true: the system has a public track record accruing daily, a research flag planted, and a canon whose dates are watched by instruments instead of hoped at.

---

## The One Move

**Sit down once, this week, with the one-page yes-sheet the swarm will send you, and answer every line.** Roughly twelve one-word questions: site host, two platform openings, the benchmark compute cap, the wedge ratification with three named recipients, the fire grant, the ledger publish grant, the merge canary, the server swap, the arXiv yes, the five risk-budget numbers. Here is why this is the move and not any single fix: the audit examined fifteen different lenses and every one converged on the same mechanism — this system does not fail at building, it fails at *asking*, and so finished work rots behind questions that were never put to you as questions, for 37, 44, 83, 100, 150 days. Your own project rules demand "one ask, one line, answerable with a word," and that contract has never once been applied to the gates that matter. One hour of your answers converts four months of parked decisions into execution, and — paired with the standing default rule, so silence can never again mean forever — it removes the single point of failure that every other finding routes through: not your judgment, which the Defense shows is mostly sound, but the fact that nobody ever asked for it.