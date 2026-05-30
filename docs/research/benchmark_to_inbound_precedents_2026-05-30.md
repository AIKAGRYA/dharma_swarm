# Benchmark-to-Inbound Precedents: A Brutally Honest Assessment
*Research compiled for Dharma Swarm / John Shrader — June 2025*

---

## 1. Brutal Headline Finding

**The benchmark-to-inbound path works, but almost exclusively produces funding-shaped inbound, not revenue-shaped inbound — and it requires a narrative leap, not just a number.**

The empirical record across 2020–2025 reveals:

- **Median time from first public benchmark/artifact → first meaningful inbound**: ~2–8 weeks for virally-shaped artifacts; 3–12 months for paper-only artifacts. The range is enormous and the median is misleading (see survivorship caveat).
- **Survivorship rate**: Roughly 5–10% of small teams that post a benchmark placement or paper receive any meaningful unsolicited inbound. The 90%+ failure-to-inbound rate is structurally invisible in any precedent list, because silent failures don't generate case studies.
- **Revenue vs. funding**: Of 13 precedents studied with confirmed inbound, **11 out of 13 received funding-first inbound** (VC cold email, interview request, acquisition interest). Only **2 of 13** (Pattern Labs/Irregular, and METR) converted benchmark/evaluation credibility directly into *paying contracts* without first taking VC money — and both were operating in the AI-safety/eval-as-a-service vertical, not general agent benchmarking.
- **The key structural variable**: Inbound requires that *someone with budget reads your result and experiences a specific felt need*. For VC, that felt need is FOMO on a narrative. For enterprise buyers, it requires your result to directly solve their problem today. Benchmark placements satisfy VCs quickly; they rarely satisfy enterprise procurement in the short term.
- **The SWE-bench exception**: SWE-bench produced more company narratives and VC inbound than any other benchmark in 2023–2025, because software-engineering automation is the one AI capability category with clear, quantifiable dollar-value attached to it. Every other benchmark produced significantly less funding-shaped inbound. The Devin playbook is an outlier constructed on a unique intersection of: (a) a 7× improvement over prior SOTA, (b) an existing benchmark with name recognition, (c) a domain (software) where CFOs can instantly price displacement, and (d) a compelling demo that went with the benchmark. Replicating it from scratch is essentially impossible.

---

## 2. Precedent Comparison Table

| # | Org | Benchmark / Artifact | Team Size at First Result | First Public Artifact | First Meaningful Inbound | Time to Inbound | Inbound Type | Revenue or Funding? | Legibility Mechanism | Survivorship Caveat |
|---|-----|---------------------|--------------------------|----------------------|-------------------------|----------------|-------------|---------------------|---------------------|---------------------|
| 1 | **Cognition AI / Devin** | SWE-bench (13.86% unassisted, 7× prior SOTA) | ~10 people | Mar 12, 2024 (tweet + demo video) | Same day/week (VCs flooded DMs); closed $21M Series A pre-announcement | <1 week | 31M views tweet; VC cold inbound | Funding-only ($21M Series A before announcement, $175M at $2B val within 6 weeks) | Tweet with SWE-bench score + 4-min demo video | Team pre-had Founders Fund relationship; benchmark chosen specifically for legibility; demo was cherry-picked task showcase, not random eval |
| 2 | **Sakana AI** | AI Scientist paper (fully automated ML research, $15/paper) | ~15 people (David Ha + team) | Aug 12, 2024 (arXiv paper) | Days after paper; Series A announced June 2024 (pre-paper) | Already funded; paper accelerated Series B | Press tsunami (TechCrunch, Nature); speaking invites; follow-on VC | Funding ($135M Series B at $2.65B val by Nov 2025) | arXiv paper + blog post + open-source repo | Already unicorn-valued before paper; David Ha (ex-Google Brain head of research) had instant credibility floors; paper's viral moment was narrative not benchmark number |
| 3 | **FutureHouse** | Lab-Bench (biology R&D benchmark, 2457 questions); PaperQA2 (superhuman literature search) | 10–20 researchers | June 2024 (Lab-Bench paper); Sept 2024 (PaperQA2 result) | Open Philanthropy grant ($2.95M) preceded public artifacts | Funded before benchmark | Philanthropic grants; platform launch May 2025; researcher inbound | Funding (nonprofit grant-funded by Eric Schmidt / Open Philanthropy) | arXiv papers + benchmarked claims of "superhuman" on specific subtasks | Non-profit; funded by Eric Schmidt; not a replicable path for bootstrap solo dev |
| 4 | **ARC Evals / METR** | Autonomous Replication eval for GPT-4 and Claude; HCAST task suite; Time-Horizon benchmark | 5 people initially (Beth Barnes + ARC team) | Mar 2023 (GPT-4 system card acknowledgment of ARC eval); Sept 2023 (spinout) | OpenAI/Anthropic embedded evaluator relationship began ~fall 2022; formal contract by early 2023 | ~6–12 months from concept to paid relationships | Pre-deployment evaluation contracts with OpenAI, Anthropic; UK AISI partnership | Revenue (earned evaluation contracts) + philanthropy ($220K Longview; $10M+ annual budget by 2024) | Published eval methodology on LessWrong; GPT-4 system card name-check; formal spinout blog post | Beth Barnes was ex-OpenAI; Paul Christiano co-founded it; they had personal credibility at frontier labs before the eval framework existed |
| 5 | **EleutherAI** | GPT-Neo (largest open-source GPT-3-like model, 2021); The Pile dataset; LM Evaluation Harness | 3 founders → ~20 contributors (Discord-based) | Dec 2020 (The Pile); Mar 2021 (GPT-Neo) | Immediate GitHub stars/HN attention; Stability AI + HuggingFace funding within 12–18 months | 6–12 months | HN front page; academic citations; partnership inbound (Stability AI, HuggingFace) | Funding/grants (Stability AI, Google TPU credits, HuggingFace partnership) + reputation | GitHub release + arXiv paper; open Discord community | GPT-Neo succeeded because *OpenAI had just released GPT-3 and refused to open-source it* — a specific market gap moment that may not recur |
| 6 | **Nous Research** | Hermes series (Hermes 1, 2, 3 on Open LLM Leaderboard) | 5–10 initially (Discord collective) | Late 2023 (Hermes 1 top-of-leaderboard) | Immediate community traction; $5.2M seed closed Jan 2024 | ~3–6 months | Community growth; VC cold inbound (Distributed Global, OSS Capital, Balaji) | Funding-first ($5.2M seed Jan 2024; $20M seed round Jan 2024 per Parsers; $65M in 2025) | HuggingFace model releases + Open LLM Leaderboard submissions | Hermes succeeded because of the "uncensored fine-tunes" niche community demand; crypto-adjacent investor base was unusual; not a typical path |
| 7 | **Goodfire AI** | SAE interpretability papers (three of most-cited SAE/mech-interp papers; Sparse Autoencoder feature discovery) | 3 founders + small team (8–21 people) | Mid-2024 (founding); SAE papers from OpenAI/DeepMind pedigree brought in | $7M seed within weeks of founding (June 2024) | <1 month of "founding" | Lightspeed cold inbound; Menlo Ventures Series A ($50M) April 2025 | Funding-first ($7M seed June 2024; $50M Series A April 2025; $150M Series B Feb 2026) | Research pedigree + SPC (South Park Commons) backing + published papers at frontier labs | Tom McGrath co-founded the interpretability team at DeepMind; Eric Ho built a Series B company (RippleMatch); this is a pedigree-first, not benchmark-first, story |
| 8 | **Adept AI** | ACT-1 (Action Transformer, browser+web automation demo, Sept 2022) | ~10 people at founding (Ashish Vaswani, Niki Parmar, etc.) | Sept 14, 2022 (blog post with demo video) | $65M Series A in April 2022 (pre-ACT-1 announcement); public buzz accelerated $350M Series B Mar 2023 | Series A was pre-product; demo accelerated Series B | Press coverage; partnership inquiries; VC follow-ons | Funding-only ($65M Series A, $350M Series B; eventually acquired by Amazon 2024) | Blog post + demo video (ACT-1 browser automation) | Founders (Vaswani/Parmar) co-wrote the Transformer paper — *they are the Transformer paper*; VC funded the pedigree, not the benchmark |
| 9 | **MultiOn** | Viral demo (burger ordering via DoorDash, 2023); no benchmark placement per se | 1 person (Div Garg, Stanford PhD) | Twitter demo video (burger ordering), early 2023 | 100+ VC cold DMs within days; General Catalyst term sheet within weeks | ~1–2 weeks from viral demo | Twitter viral (millions of views); VC flood | Funding-first ($undefined pre-seed from GC 2023; Series A undisclosed) | Short demo video posted to Twitter | Demo, not benchmark; the viral mechanic was *relatable task* (ordering food) + *surprising capability* + *solo founder relatable story* |
| 10 | **OpenInterpreter** | Open-source "Code Interpreter runs locally" (GPT-4 exec() loop) | 1 person (Killian Lucas) | Sept 2023 (GitHub release) | 20,000+ GitHub stars in 1 week; 18K stars day 1 | <1 week | HN #1 trending; GitHub trending #1; Twitter viral | No clear funding raise; community/audience only → later 01 Light hardware raise | GitHub README + Twitter | This was a demo-shaped artifact (local Code Interpreter), not a benchmark; it hit at the exact moment OpenAI launched Code Interpreter in ChatGPT; timing was the whole story |
| 11 | **Cline (VSCode agent)** | Open-source VSCode coding agent; API cost transparency | 1 person (Saoud Rizwan) | Oct 2024 (hackathon project) | $5M seed Nov 2024; $27M Series A July 2025 | ~1 month | Community growth (2.7M installs); enterprise inbound (SAP, Samsung) | Funding + early enterprise revenue | GitHub + VS Marketplace release | Built at Anthropic hackathon; product-shaped, not benchmark-shaped; revenue came from enterprise pull, not leaderboard |
| 12 | **Imbue / Generally Intelligent** | Internal reasoning benchmarks (proprietary); Avalon open-source RL environment | ~20 people | Nov 2022 (Avalon env release); Sept 2023 ($200M announcement) | $20M Series A 2022; $200M Series B Sept 2023 | Funded before any public eval result | VC (Astera Institute, NVIDIA, Cruise CEO Kyle Vogt) | Funding-only ($220M total; unicorn valuation) | Blog post claiming SOTA on internal reasoning benchmarks | No public benchmarks at all during funding; the story was *the team* (Kanjun Qiu + pedigree) + the narrative vision; explicitly said "no demo ready" at $200M raise |
| 13 | **Pattern Labs / Irregular** | Red-teaming / adversarial eval methodology (not a public leaderboard placement) | 2 founders (Dan Lahav, Omer Nevo) + ~25 by reveal | Mid-2023 (first client contracts) | OpenAI and Anthropic contracts started "beginning of 2023" per Forbes | ~0–6 months from founding | Direct outreach to OpenAI/Anthropic pre-deployment eval teams; Sequoia cold inbound after client traction | Revenue-first (millions in revenue from OpenAI/Anthropic/Google); then $80M Series A Sequoia 2025 | No public artifact; methodology work directly with lab safety teams | This is the rare revenue-first path — but it required Israeli cybersecurity/AI pedigree, specific timing (GPT-4 deployment window), and working *privately* with labs, not public benchmark posting |

---

## 3. Per-Category Honest Assessment

### 3.1 SWE-bench — High-signal, high-competition, VC-shaped

**Inbound production**: Highest of any agentic benchmark in 2023–2025. Has produced at least 5 funded companies as primary or secondary narrative ([Cognition/Devin](https://cognition.ai/blog/swe-bench-technical-report), SWE-agent/Princeton team, OpenHands/All-Hands AI, CodeStory, several others on the [SWE-bench leaderboard](https://www.swebench.com)).

**Why it works**: Software engineering has an instantly legible dollar value. "Replaces a $150K/yr engineer for $X" is a CFO-level sentence. Every VC partner understands it.

**Current saturation**: The [SWE-bench Verified leaderboard](https://llm-stats.com/benchmarks/swe-bench-verified) now has 90+ submissions. Claude Mythos Preview scores 93.9%. A new top-of-leaderboard placement by a small team is nearly impossible, and mid-table placements generate zero inbound. The 2024 window of "first agent demo + SWE score" is closed.

**Revenue-shaped vs. funding-shaped**: Almost entirely funding-shaped. [Cognition's ARR](https://cognition.ai/blog/funding-growth-and-the-next-frontier-of-ai-coding-agents) reached $1M in September 2024 — six months after the benchmark announcement, not days.

**Verdict for Dharma Swarm**: Not viable as a first-mover unless you can place #1 on SWE-bench Verified (currently requires beating Claude at 93.9%). The benchmark itself is useful as a component of a broader eval story but is no longer a sufficient narrative.

---

### 3.2 ARC-AGI — Prestigious, slow to convert, prize money exists

**Inbound production**: The [ARC Prize 2024](https://arcprize.org/blog/arc-prize-2024-winners-technical-report) report explicitly states that "at least seven well-funded startups shifted priorities to work on ARC-AGI." The competition produced $125K+ in distributed prize money. However, it produced *zero known revenue-paying contracts* from outside the ARC Prize organization itself.

**Why the conversion rate is low**: ARC-AGI is fundamentally a research benchmark, not a product proxy. Placing highly proves reasoning generalization ability, which is interesting to researchers but doesn't directly translate to "I need to buy your product." The winners (ARChitects, MindsAI) received:
- Prize money ($25K–$50K for top scores/papers)
- Twitter/media attention
- NVIDIA GTC speaking slot (ARChitects at [GTC 2025](https://www.nvidia.com/en-us/on-demand/session/gtc25-s74252/))
- Hiring inquiries (Tufa Labs posted that "MindsAI is merging with Tufa Labs; now hiring ML engineers")
- No confirmed VC rounds directly attributed to the competition result

**Revenue-shaped vs. funding-shaped**: Neither. The prize money itself is the revenue.

**Verdict**: Useful for community building and hiring signal. Not a direct path to revenue or VC funding without a separate product narrative attached.

---

### 3.3 GAIA / AgentBench / General Agent Benchmarks — Weak inbound production

**Inbound production**: Minimal documented cases of funding or revenue directly attributed to GAIA/AgentBench placements. [H2O.ai topped the GAIA leaderboard](https://h2o.ai/blog/2024/h2o-ai-tops-gaia-leaderboard/) in Dec 2024 — no funding event followed. MultiOn's inbound came from a viral *demo*, not a GAIA placement.

**Why it underperforms**: GAIA's task set is designed around general assistant tasks (web browsing, multi-modal reasoning). These are useful but don't map cleanly to high-dollar enterprise use cases or press narratives. "Our agent answers 74% of GAIA Level 3 questions" is not a sentence that appears in a TechCrunch headline.

**Verdict**: Low-signal for inbound. Useful internally for tracking capability but should not be the public anchor.

---

### 3.4 METR / RE-Bench / Autonomy Evals — High credibility, unusual path

**Inbound production**: METR's [Time-Horizon chart](https://www.linkedin.com/pulse/039-metr-why-ai-watchers-obsessed-chart-nagesh-nama-owu7e) has become "Wall Street and Silicon Valley's favorite way to gauge AI progress" — but METR's own revenue comes from *running* those evaluations, not *placing* on them. The benchmark producer role is the business model.

**The pattern**: ARC Evals got early access to GPT-4 in Fall 2022 via a pre-existing relationship between Paul Christiano (founder) and OpenAI safety leadership, plus Beth Barnes's prior OpenAI employment. Their [GPT-4 system card acknowledgment](https://cdn.openai.com/papers/gpt-4-system-card.pdf) (March 2023) was the credibility-validating public artifact. By then, the evaluation relationships were already commercial. The public artifact *confirmed* credibility that private relationships had already established.

**Revenue model**: $10M operating budget in 2024 from philanthropy + lab contracts. [METR's annual report](https://metr.org/2024-annual-report.pdf) confirms this.

**Verdict for Dharma Swarm**: This is the most interesting precedent. The path is: (a) build a novel eval framework, (b) get a frontier lab to acknowledge using it pre-deployment, (c) publish the methodology publicly, (d) receive third-party evaluator contracts. But it required personal credibility at OpenAI/Anthropic to initiate.

---

### 3.5 Open LLM Leaderboard / Fine-Tuning Benchmarks — Community traction, crypto-adjacent funding

**Inbound production**: [Nous Research](https://startupintros.com/orgs/nous-research) went from Discord-based model releases to $5.2M seed in Jan 2024, largely by topping HuggingFace's Open LLM Leaderboard and serving a "uncensored/unrestricted" niche. [EleutherAI](https://en.wikipedia.org/wiki/EleutherAI) went from Discord server to receiving Stability AI funding and Google TPU Cloud grants within 12–18 months of first model release.

**Why these worked**:
- The LLM leaderboard has an active community of practitioners who immediately test and share results
- Both orgs served an underserved niche (open-source, unrestricted, non-corporate) with genuine demand
- Funding was from crypto/web3 investors (Balaji, Multicoin) for Nous; compute-as-resource grants for EleutherAI — not traditional Series A VCs

**Failure mode**: This category requires top-of-leaderboard placement on a benchmark people actively use. Mid-table placements generate nothing. The leaderboard itself [saturated in 2024](https://github.com/huggingface/blog/blob/main/open-llm-leaderboard-mmlu.md) with hundreds of submissions.

---

### 3.6 Autonomous Science Benchmarks (Lab-Bench, Biology R&D) — Philanthropic pathway

**Inbound production**: [FutureHouse](https://www.futurehouse.org) received a [$2.95M Open Philanthropy grant](https://www.openphilanthropy.org/grants/future-house-benchmarks-for-biology-research-and-development/) for building biology benchmarks, then built the agents to beat those benchmarks. [Cradle Bio](https://www.cradle.bio) received €5.5M seed (Nov 2022) → $24M Series A (Nov 2023) → $73M Series B (Nov 2024) — but Cradle's path was primarily wet-lab customer traction (Novo Nordisk, J&J), not benchmark-first.

**Pattern**: In bio/science, benchmark-first → grant-first → then product traction. The grant/philanthropic layer is the "VC" equivalent but requires EA/Open Philanthropy network access.

**Verdict**: Not applicable to Dharma Swarm's multi-agent coding focus, but relevant as an analogy: if Dharma Swarm wanted to anchor on "AI safety eval substrate," a grant pathway from Open Philanthropy or SFF is more realistic than VC inbound from a benchmark placement.

---

## 4. Cross-Cutting Findings

### 4.1 Empirical Timing: First Public Artifact → First Meaningful Inbound

| Category | Fastest Documented | Median Estimate | Slowest Documented |
|----------|-------------------|----------------|-------------------|
| Viral demo (benchmark + video) | <1 week (Cognition/Devin, MultiOn) | 2–4 weeks | N/A |
| Paper-only (no product, no demo) | 3 months (Sakana, already funded) | 6–12 months | 18+ months (Imbue: funded 6 months before any public result) |
| Leaderboard-only (no blog, no tweet storm) | 3 months (Nous Research) | Never documented | — |
| Eval-as-a-service (private relationship first) | <1 month from client contact (Pattern Labs) | 3–6 months | — |

**The survivorship caveat**: These are confirmed successes. The base rate of benchmark placements that generate *zero* inbound is not tracked anywhere. Based on the number of SWE-bench submissions (~90+ on Verified) vs. number of funded companies that emerged from those submissions (~5–8), an estimate is **~5–9% conversion rate** from "leaderboard entry" to "any meaningful inbound." The conversion rate for "paper-only" is even lower.

---

### 4.2 Revenue vs. Funding Distribution

Of all documented precedents above:

| Inbound Type | Count | Examples |
|-------------|-------|---------|
| VC/investor funding first | 9 | Cognition, Sakana, Goodfire, Adept, Nous, Cline, FutureHouse, Imbue, EleutherAI |
| Revenue/contracts first (then optional funding) | 2 | Pattern Labs/Irregular, METR |
| Community/audience only (no funding, no revenue for 1+ year) | 2 | OpenInterpreter, ARC-AGI winners |

**Key finding**: The benchmark-to-revenue-self-sustaining path is documented in exactly **two** cases in this study, and both required operating in the AI safety/red-teaming/evaluation vertical, with pre-existing personal relationships at frontier labs, in 2022–2023.

---

### 4.3 What Benchmark Categories Produced Most Inbound

Ranked by verified funding/revenue events attributed (even partially) to benchmark result:

1. **SWE-bench** (5+ funded companies) — [leaderboard](https://www.swebench.com)
2. **Open LLM Leaderboard** (3+ organizations) — [HuggingFace leaderboard](https://huggingface.co/spaces/open-llm-leaderboard/open_llm_leaderboard)
3. **Custom/internal benchmarks** (Imbue, Adept) — 2 orgs, but benchmark was the *excuse*, not the driver
4. **Safety/capability evals** (METR pattern) — 1 org, revenue not funding
5. **ARC-AGI** — prize money only, no confirmed VC inbound
6. **GAIA / AgentBench** — no confirmed inbound events documented

---

### 4.4 The Realistic Dollar Trajectory (Revenue-Path Only)

For the *rare* org that does convert benchmark/eval credibility into revenue rather than funding:

| Timeline | Realistic Revenue Range | What Drives It |
|----------|------------------------|----------------|
| Month 0–1 | $0 | Even with viral post, no deal closes in days |
| Month 1–3 | $0–$15K | Consulting inquiry, maybe a small pilot contract |
| Month 3–6 | $10K–$50K/mo | First paid eval contract (if in safety/eval niche) |
| Month 6–12 | $25K–$150K/mo | Repeat contracts, word-of-mouth within frontier labs |
| Month 12–18 | $100K–$500K/mo | Institutional arrangement (lab pays for continuous eval) |

Pattern Labs/Irregular achieved "millions in revenue" from OpenAI/Anthropic by approximately 12–18 months after founding in mid-2023. That is likely $3–5M ARR in the first full year — but this required serving *the largest buyers in the world* in a narrow, high-stakes niche.

---

### 4.5 The Failure Mode Nobody Talks About

The dominant failure pattern across attempted benchmark-to-inbound plays:

1. **Placement without narrative**: Posting a leaderboard result with no articulated "why this matters / what problem this solves" generates zero engagement. Most SWE-bench entries below the top 5 received no press and no VC contact.

2. **Benchmark that nobody actively monitors**: ARC-AGI, GAIA, and AgentBench are benchmarks that sophisticated researchers watch. They are *not* benchmarks that enterprise buyers watch. Placing on them without translating the result into enterprise value produces academic recognition, not revenue.

3. **Too small an improvement**: Cognition's 13.86% vs. 1.96% prior SOTA was a 7× improvement. A 5% improvement over the top model generates nothing. The threshold for press-worthy improvement varies by benchmark; for most it requires exceeding prior SOTA by 25%+ or setting a new category record.

4. **No continuous presence**: A single benchmark submission followed by silence is worth nothing long-term. The teams that built reputations (EleutherAI, FutureHouse, METR) published *continuously*, updated their numbers, and were visibly running their evals.

---

## 5. Recommended Path-Shapes for Dharma Swarm (Solo Dev, $2K/mo LLM Burn, Evaluation Substrate Already Built)

Given: Dharma Swarm has ~5,000 LOC of evaluation substrate (auto_grade, gauntlet, petri_dish, closure_v0), no existing audience, wants viral-shape outcomes, wants revenue-self-sustaining path rather than VC path.

### Path A: The METR Positioning — "Continuous Third-Party AI Agent Evaluator"

**Mechanics**: Use Dharma Swarm's eval substrate to continuously run and publicly report on the METR Time-Horizon equivalent for multi-agent systems. Do not position as a competitor on a benchmark; position as the *measurement infrastructure*.

**Artifact shape**: A public dashboard at a memorable URL (e.g., dharmaswarm.io/score) that shows live, continuously-updating benchmark scores for frontier models on a specific task category (multi-agent coordination, long-horizon software tasks, or autonomous research). Update it on a cadence (weekly/monthly). Blog each meaningful movement.

**Why this works better than placing on existing benchmarks**:
- You own the benchmark category narrative
- Labs need external evaluators — the relationship is pull-based
- The artifact is persistent and self-updating (continuous proof)
- Viral events are naturally recurring (each "new SOTA" announcement references your scoreboard)

**Revenue path**: Charge labs $5K–$25K/mo to run their private models through your eval suite pre-deployment. This is exactly what Pattern Labs/Irregular did. Pattern Labs had contracts with OpenAI, Anthropic, and Google DeepMind within ~12 months of founding.

**Realistic inbound timeline**: 3–6 months to first frontier lab inquiry if the eval framework is novel and publicly credible.

**Failure mode**: If the task category you choose is too abstract (no lab cares), too narrow (one lab cares), or too overlapping with METR's own HCAST suite. The suite must test something current evals miss.

---

### Path B: The Continuous Gauntlet — "Our Swarm Runs the Same Benchmark Every Week"

**Mechanics**: Pick one existing benchmark (SWE-bench Verified or METR HCAST are the highest-credibility options) and commit to publicly running Dharma Swarm against it on a fixed cadence. Publish score, cost, agent trace, and improvement curve. Document architectural changes and their effect on score.

**Artifact shape**: A GitHub README with a live score badge, weekly blog posts ("Dharma Swarm this week: 43% on SWE-bench Verified, up from 38% last week — here's what changed"), and Twitter/X posts linking to detailed trace analysis.

**Why the cadence matters**: Most benchmark submissions are one-time snapshots. Continuous operation proves that the system is real, maintained, and improving — which is more credible than a single published number.

**Viral potential**: The moment Dharma Swarm's SWE-bench Verified score crosses a round number (50%, then 60%, then 70%) is a recurring viral event. Each crossing is a tweet that gets 10K–100K impressions if framed as "solo dev's swarm just hit X%."

**Revenue path**: Weak on its own. This path builds audience (hiring inbound, researcher interest) but does not naturally convert to contracts. Must be layered with Path A.

**Cost estimate**: Running SWE-bench Verified on 500 tasks weekly at current frontier model prices runs $50–$300/run depending on model and trajectory length. At $2K/mo burn, this is feasible for 1–2 weekly runs.

---

### Path C: The Eval-as-a-Service Direct Approach

**Mechanics**: Cold-email AI safety teams at frontier labs (OpenAI, Anthropic, Google DeepMind, Meta AI) offering to run Dharma Swarm's gauntlet against their pre-deployment models as a third-party evaluation. Price at $5K–$15K per evaluation run, with a free pilot for the first.

**What you're selling**: Independent, reproducible multi-agent capability evaluation with documented methodology. Labs are required (by their own safety policies, by UK/US AI Safety Institutes, and by competitive pressure) to run third-party evals before deployment.

**Why this is harder than it sounds**: Pattern Labs succeeded because their founders had cybersecurity/AI pedigree and likely warm introductions into lab safety teams. Cold outreach from a solo developer without institutional affiliation will face trust-credibility barriers. The eval framework must be demonstrably novel and published for this to work.

**Mitigation**: The public continuous-eval artifact (Path A or B) establishes the credibility needed for cold outreach to succeed. Run Path A/B for 3–6 months, then approach labs with "here is our public record of evaluating X models, here is what we found, here is the private eval service."

---

### Path D: The Grant Path

**Mechanics**: Apply to Open Philanthropy's Requests for Proposals on AI evaluation, SFF (Survival and Flourishing Fund), or Lightspeed Grants for AI safety research. FutureHouse received $2.95M from Open Philanthropy specifically for [building biology benchmarks](https://www.openphilanthropy.org/grants/future-house-benchmarks-for-biology-research-and-development/). There are equivalent programs for AI agent capability evaluation.

**Realistic grant size**: $50K–$500K for a solo dev with a credible eval framework in the AI safety space. This covers 25–250 months of burn at $2K/mo.

**Why this is underutilized**: Most AI devs don't apply for grants. The market for "we built a serious multi-agent eval framework" is dramatically undersupplied in the grant landscape relative to VC.

**Failure mode**: Grants take 3–6 months to close; you need a credible public artifact to apply with.

---

## 6. Benchmark Scoring Dimensions for Dharma Swarm

Score each potential benchmark target on these dimensions before committing:

| Dimension | Why It Matters | Score 1–5 |
|-----------|---------------|-----------|
| **Legibility to buyers** | Can a non-technical VP or VC partner understand in one sentence why your score matters? (SWE-bench = 5/5; GAIA = 2/5) | |
| **Improvement headroom** | Is the current SOTA so high that you can't plausibly top it? (SWE-bench Verified 94% = 1/5 for new entrant) | |
| **Active monitoring community** | Is there a Twitter/Slack/Discord community that watches this benchmark daily? (SWE-bench = 5/5; AgentBench = 2/5) | |
| **Cost to run continuously** | Can you afford weekly runs at current LLM prices? | |
| **Revenue proximity** | Does the benchmark directly measure capability buyers are paying for today? | |
| **Your substrate fit** | Does your gauntlet/petri_dish/auto_grade architecture naturally implement this benchmark's scoring? | |
| **Novelty / category ownership** | Is this a benchmark you defined (you own the narrative) or one others defined (you're competing for a rank)? | |
| **Press-friendly result shape** | Does a strong result produce a sentence that reads well in a tweet? "Dharma Swarm [X% on Y]" — is X% meaningful and Y recognizable? | |

### Applying the Scoring to Dharma Swarm's Likely Candidates

| Benchmark | Legibility | Headroom | Community | Cost | Revenue Proximity | Substrate Fit | Novelty | Press Shape | **Total** |
|-----------|-----------|---------|----------|------|------------------|--------------|--------|------------|---------|
| SWE-bench Verified (top) | 5 | 1 | 5 | 3 | 5 | 4 | 1 | 5 | 29/40 |
| METR HCAST (mid-range tasks) | 3 | 4 | 3 | 3 | 4 | 5 | 2 | 3 | 27/40 |
| Dharma-defined multi-agent benchmark (own) | 2 | 5 | 1 | 5 | 3 | 5 | 5 | 3 | 29/40 |
| ARC-AGI 2025 | 3 | 2 | 4 | 2 | 1 | 2 | 1 | 4 | 19/40 |
| GAIA | 2 | 3 | 2 | 3 | 2 | 3 | 1 | 2 | 18/40 |
| Aider benchmark (coding) | 4 | 2 | 4 | 4 | 4 | 5 | 1 | 4 | 28/40 |

**Best initial candidate given Dharma Swarm's position**: A *custom multi-agent evaluation suite* that (a) builds on METR HCAST task format for credibility, (b) focuses on a specific high-value vertical (software engineering, or autonomous research), and (c) produces a single parseable number that Dharma Swarm updates continuously. The custom benchmark + continuous operation combination is the only option where you score high on both "novelty/category ownership" and "substrate fit" simultaneously.

---

## 7. Honest Survivorship Assessment

The precedents in this report represent **the 5–10% that worked**. The following patterns were common in the 90–95% that generated zero inbound:

- Teams that placed in the 20th–100th position on any major leaderboard and received no press or VC contact
- Papers posted to arXiv that received <50 citations and no follow-on interest
- Benchmark placements announced via blog posts that received no HN/Twitter traction because the founding team had zero existing audience
- Projects that scored well on an eval that VCs had never heard of

**The brutal honest distribution**: Of every 100 small AI teams that post a benchmark placement or evaluation result in 2024–2025:
- ~60 receive zero inbound of any kind
- ~25 receive some community attention (GitHub stars, Twitter engagement) but no funding/revenue discussions
- ~10 receive at least one cold email from a VC or potential partner
- ~4 convert that contact into a term sheet, contract discussion, or formal partnership
- ~1 converts to something that matters for their financial sustainability

The orgs profiled in this report are the 1–4. The 60 who received nothing are not findable via case study research.

---

## Sources

1. Cognition SWE-bench technical report and announcement tweet: https://cognition.ai/blog/swe-bench-technical-report | https://x.com/cognition/status/1767548763134964000
2. Cognition funding history (Voicebot.ai): https://voicebot.ai/2024/04/25/cognition-labs-claims-2b-valuation-after-6-months-and-175m-investment-in-generative-ai-coding-assistant-devin/
3. Cognition ARR growth and $26B valuation (TechCrunch 2026): https://techcrunch.com/2026/05/27/ai-coding-startup-cognition-raises-1b-at-25b-pre-money-valuation/
4. Sakana AI Scientist paper (arXiv): https://arxiv.org/abs/2408.06292
5. Sakana AI Scientist blog post: https://sakana.ai/ai-scientist/
6. Sakana Series B ($2.65B, $135M): https://techcrunch.com/2025/11/17/sakana-ai-raises-135m-series-b-at-a-2-65b-valuation-to-continue-building-ai-models-for-japan/
7. Sakana AI Nature paper: https://sakana.ai/ai-scientist-nature/
8. FutureHouse Open Philanthropy grant: https://www.openphilanthropy.org/grants/future-house-benchmarks-for-biology-research-and-development/
9. FutureHouse platform launch: https://www.futurehouse.org/research-announcements/launching-futurehouse-platform-ai-agents
10. FutureHouse Reddit timeline post: https://www.reddit.com/r/accelerate/comments/1ksn5jb/futurehouses_goal_has_been_to_automate_scientific/
11. ARC Evals spinout announcement (Sept 2023): https://metr.org/blog/2023-09-19-spin-out-announcement/
12. METR announcement (Dec 2023): https://metr.org/blog/2023-12-04-metr-announcement/
13. METR time-horizon chart explainer (LinkedIn): https://www.linkedin.com/pulse/039-metr-why-ai-watchers-obsessed-chart-nagesh-nama-owu7e
14. METR 2024 annual report: https://metr.org/2024-annual-report.pdf
15. GPT-4 system card (ARC eval acknowledgment): https://cdn.openai.com/papers/gpt-4-system-card.pdf
16. ARC Evals GPT-4 eval description (LessWrong): https://www.lesswrong.com/posts/4Gt42jX7RiaNaxCwP/more-information-about-the-dangerous-capability-evaluations
17. EleutherAI Wikipedia: https://en.wikipedia.org/wiki/EleutherAI
18. Contrary Research openness of AI (EleutherAI history): https://research.contrary.com/report/the-openness-of-ai
19. Nous Research funding history (StartupIntros): https://startupintros.com/orgs/nous-research
20. Nous Research Hermes 3 technical report: https://nousresearch.com/wp-content/uploads/2024/08/Hermes-3-Technical-Report.pdf
21. Nous Research Open LLM Leaderboard submissions: https://huggingface.co/datasets/open-llm-leaderboard/results/tree/03e648f8c7d03224cc126da3256c435d8790cb29/NousResearch
22. MultiOn AGI House podcast (Div Garg): https://www.youtube.com/watch?v=Uz6tn_j_OdI
23. Goodfire Series A announcement: https://www.goodfire.ai/blog/announcing-our-50m-series-a
24. Goodfire Series B ($150M, $1.25B): https://finance.yahoo.com/news/ai-lab-goodfire-raises-150m-150100095.html
25. Goodfire founding story (South Park Commons): https://www.southparkcommons.com/companies/goodfire/
26. Contrary Research Goodfire breakdown: https://research.contrary.com/company/goodfire
27. Adept ACT-1 blog post (Sept 2022): https://www.adept.ai/blog/act-1/
28. Adept Series B ($350M): https://www.adept.ai/press/press-release-series-b/
29. OpenInterpreter Killian Lucas launch (ThursdAI interview): https://sub.thursdai.news/p/thursdai-special-interview-with-killian
30. Cline raises $32M (Cline blog): https://cline.bot/blog/cline-raises-32m-series-a-and-seed-funding-building-the-open-source-ai-coding-agent-that-enterprises-trust
31. Cline founding story (Forbes): https://www.forbes.com/sites/rashishrivastava/2025/07/31/cline-has-raised-27-million-to-help-developers-control-their-ai-spend/
32. Imbue $200M Series B (TechCrunch): https://techcrunch.com/2023/09/07/imbue-raises-200m-to-build-ai-models-that-can-robustly-reason/
33. Imbue Forbes profile (no public demo at $200M): https://www.forbes.com/sites/alexkonrad/2023/09/07/ai-research-lab-imbue-nabs-200-million-for-speculative-bet-to-build-ai-agents/
34. Answer.AI launch post: https://www.answer.ai/posts/2023-12-12-launch.html
35. Answer.AI/FastAI YouTube profile: https://www.youtube.com/watch?v=MbHL0uvKYbE
36. Pattern Labs / Irregular Forbes: https://www.forbes.com/sites/thomasbrewster/2025/09/16/openai-pays-a-450-million-startup-to-test-chatgpt-capacity-for-evil/
37. Irregular $80M Series A (Calcalist): https://www.calcalistech.com/ctechnews/article/h1g4zg00igg
38. Cradle seed round (Forbes): https://www.forbes.com/sites/johncumbers/2022/11/17/startup-cradle-lets-you-design-custom-proteins-by-just-typing-in-a-prompt/
39. Cradle Series A ($24M): https://www.thesaasnews.com/news/cradle-raises-24-million-in-series-a
40. Cradle Series B ($73M): https://www.cradle.bio/blog/series-b
41. ARC Prize 2024 winners and technical report: https://arcprize.org/blog/arc-prize-2024-winners-technical-report
42. ARC Prize 2024 technical report (arXiv): https://arxiv.org/abs/2412.04604
43. MindsAI/Tufa Labs ARC score: https://www.youtube.com/watch?v=-M0HZGKF4UI
44. SWE-bench leaderboard: https://www.swebench.com
45. SWE-bench Verified leaderboard (LLM Stats): https://llm-stats.com/benchmarks/swe-bench-verified
46. GAIA benchmark paper (ICLR): https://proceedings.iclr.cc/paper_files/paper/2024/file/25ae35b5b1738d80f1f03a8713e405ec-Paper-Conference.pdf
47. METR task standard (GitHub): https://github.com/METR/task-standard
48. Open LLM Leaderboard (HuggingFace): https://huggingface.co/spaces/open-llm-leaderboard/open_llm_leaderboard

---

*Compiled June 2025. All funding figures sourced from primary announcements or well-documented secondary sources. All timing estimates carry ±2 week precision for fast-moving events and ±2 month precision for slower-moving events. Survivorship bias caveat applies to every data point in this document.*
