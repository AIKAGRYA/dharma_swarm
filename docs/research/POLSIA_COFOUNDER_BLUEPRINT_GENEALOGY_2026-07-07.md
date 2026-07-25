# Polsia / Cofounder — Blueprint & Genealogy Dossier (2026-07-07)

**Method:** deep-research fan-out (100 agents: 5 search angles → 18 sources
fetched → 58 claims extracted → 25 top claims through 3-vote adversarial
verification → 20 confirmed / 5 refuted / 0 unverified). Afferent only — no
outreach, no contact. Every organ below carries an evidence class
(NECESSITY-INFERENCE / GENEALOGY / BEHAVIORAL / INFRA-EXHAUST) and a
confidence grade; anything without evidence is UNKNOWN, never guessed.
**Consumers:** `scripts/governance/tam_axes.py` (Company-Builder Parity
board, track `company-builder-parity-2026-07`), lane_F world-triangulation
successors.
**Access caveat:** most primary URLs 403'd through the egress proxy;
verification rests on search-index verbatim matches + multi-domain
corroboration (robust against the prior fabricated-interview failure mode,
but exact quote wording carries residual uncertainty).

---

## 1. The headline: genotype vs phenotype

The phenotype (marketing) says "autonomous AI companies." The recoverable
genotype says:

- **Polsia is repo-visible commodity assembly.** Its own GitHub dump
  (github.com/PolsiaAI/Polsia) self-describes nine role-specialized agents
  that **shell out to the Anthropic Claude Code CLI as a subprocess**
  (`claude -p "..." --output-format json`, OAuth via a mounted `~/.claude`)
  on **Celery Beat schedules**, over Next.js 14 / FastAPI / PostgreSQL 16 /
  Redis / ChromaDB / nginx / Docker Compose. No LangGraph, CrewAI, AutoGen,
  or any LLM SDK in requirements.txt; no Temporal-class durable execution —
  Celery. (GENEALOGY/INFRA-EXHAUST; stack HIGH, CLI-loop MEDIUM.)
- **Cofounder publishes doctrine, not implementation.** A departmentalized
  "superoptimizer" manager-agent over engineering/sales/marketing/design
  departments with integration-driven "Flows", plus one genuinely
  differentiated organ: a **three-tier memory system** (working / core /
  long-term, active consolidation, MemGPT lineage, evaluated on
  MemoryAgentBench). All of it vendor self-description; orchestration
  engine, durable execution, tenancy = UNKNOWN. (BEHAVIORAL vendor-claim,
  MEDIUM.)
- **Neither company publishes**: safety/approval-interrupt mechanics, audit
  trails, or any third-party-verifiable revenue. That absence is confirmed,
  and it is exactly the seat our receipt spine + telos gates occupy.

## 2. Polsia — organ-by-organ

| Organ | Evidence | Confidence | Finding |
|---|---|---|---|
| Agent loop / model routing | GENEALOGY (repo README:40, docker-compose mounts `~/.claude:ro`, tests mock `call_claude()` subprocess) | MEDIUM (core `app/` package absent from dump) | Claude Code CLI subprocess per agent; single-vendor Anthropic; no framework lineage |
| Orchestration topology | GENEALOGY/INFRA-EXHAUST (repo + 36kr) | HIGH | Nine agents (Orchestrator/'CEO', social, outreach, support, ads, finance, planning, competitor-research, codegen) on staggered Celery Beat schedules; the Orchestrator is itself one scheduled agent, not a runtime dispatch hierarchy. Exact cron cadences NOT verified (refuted 0-3 as standalone claim) |
| Durable task execution | GENEALOGY (repo) | HIGH | Redis + Celery. NOT Temporal-class; no crash-resume/exactly-once evidence |
| Retrieval / memory | GENEALOGY (repo) | HIGH | ChromaDB |
| Billing / metering | BEHAVIORAL + NECESSITY (fee structure corroborated across 7+ sources; Stripe in requirements.txt) | HIGH | $49/mo subscription (reviews cite $29–59) + 20% commission on managed ad spend + 20% revenue share + ~$1/task credits — requires metering of BOTH user ad spend and user revenue. zilla.so worked example: stacked fees can reach $1,600/mo on a $5k-revenue business |
| Per-tenant provisioning | BEHAVIORAL founder-stated + NECESSITY (Mixergy #2298, verified real) | MEDIUM | Engineering agent given "a web server, a GitHub account, a database" — implies per-customer infra provisioning; whether automated at 8,000+ company scale is an OPEN QUESTION (manual-assist allegations untested) |
| Outbound | GENEALOGY (requirements.txt) | MEDIUM | SendGrid + tweepy — commodity vendor calls, no Instantly/Smartlead-class warm-inbox machinery evidenced |
| Approval/HITL, audit trail, sandbox isolation | — | **UNKNOWN / no evidence** | Nothing published. The repo dump contains no approval, audit, or tenancy-isolation code |

**Provenance caveat (HIGH):** the repo is a one-shot dump — 2 commits, both
"Add files via upload", both 2026-03-18, no license, core `app/` package
missing, and no verified backlink from production polsia.com (which 403s).
It evidences a *claimed architecture snapshot*, not production. A
skeptic-built "Open Source Polsia Alternative That Actually Works"
(janwilmake/openpolsia) exists.

**Revenue reality (MEDIUM, third-party-corroborated in direction):**
founder-claimed figures escalate $689K (Mixergy, Mar 2026) → $6.2M (Apr) →
$10M+ (June, around the $30M raise at $250M — Sound Ventures lead, True
Ventures et al., round itself HIGH-confidence). 36kr's decomposition of the
~$10M: **~$4.6M true subscription ARR** (consistent with ~7,600 × $49/mo) +
~$2M one-time task packages + ~$2M pass-through ad spend counted as revenue
— an inflated-ARR pattern, ~2.2× headline-vs-recurring. Best-performing
Polsia-launched customer company at review time: **~$50/mo gross MRR**. A
public firsthand-audit allegation calls the launched businesses "hollow
shells" (@panphora, verified tweet; allegation, not finding). **No
independent audit of any figure exists.**

## 3. Cofounder (General Intelligence Company) — organ-by-organ

| Organ | Evidence | Confidence | Finding |
|---|---|---|---|
| Orchestration doctrine | BEHAVIORAL vendor-claim (Cofounder 2 announcement, GIC "superoptimization" essay, Forbes, USV blog) | MEDIUM | "Superoptimizer" manager agent delegating across departments with shared context; "Flows" = event/schedule/manual-triggered workflow generation over "hundreds of integrations" |
| Memory system ⭐ | GENEALOGY (MemGPT lineage) + vendor engineering post; benchmark verified real (arXiv 2507.05257) | MEDIUM | Three tiers: working (per-session workspace) / core (active consolidation compressing sessions into compact knowledge + preferences — a consolidation pipeline, NOT RAG-over-transcripts) / long-term (self-deciding ontologies); sleep-time compute; dual memory-agent/real-time-agent design; evaluated on MemoryAgentBench; "state of the art" self-reported with NO recoverable score. **The one plausibly proprietary organ across both companies** |
| Tool execution | INFRA-EXHAUST | LOW | Browserbase case study = the single third-party stack fingerprint (browser automation vendor) |
| Durable execution, tenancy, context isolation, MCP-ecosystem pinning, approval mechanics | — | **UNKNOWN** | No surviving public evidence at all — the engine behind the doctrine is a black box |

**Entity/funding (HIGH):** The General Intelligence Company of New York
(CEO Andrew Pignanelli), $8.7M seed led by Union Square Ventures (Dec
2025), >$10M total within ~12 months of founding.

## 4. Genealogy map — commodity vs proprietary

| Reference-architecture organ | Polsia lineage | Cofounder lineage | Commodity? |
|---|---|---|---|
| Agent loop | Claude Code CLI (Anthropic) | UNKNOWN (vendor doctrine only) | **Commodity** (a CLI call) |
| Durable execution | Celery/Redis | UNKNOWN | **Commodity** (and weak — no Temporal-class durability anywhere) |
| Memory/retrieval | ChromaDB | MemGPT-descended 3-tier consolidation | Polsia commodity; **Cofounder plausibly proprietary** |
| Billing/metering | Stripe + rev-share metering | UNKNOWN | Commodity + one custom metering leg |
| Outbound | SendGrid/tweepy | integrations layer (claim) | Commodity |
| Tenancy/provisioning | per-tenant web server + GitHub + DB (founder-stated) | UNKNOWN | Possibly Polsia's one hard-won organ (automation at scale unproven) |
| Approval/HITL, audit, safety | ABSENT from all published evidence | ABSENT | **The empty seat** |

**Moat synthesis (MEDIUM):** Polsia's moat is distribution/narrative
velocity (and possibly provisioning automation), **not architecture**.
Cofounder's candidate moat is the memory/consolidation pipeline. Verifiably
absent for both: third-party revenue verification, published
safety/approval mechanics, audit trails.

## 5. Corrections to our own priors (bind these)

1. **The "4.4× claimed-vs-actual ARR gap" is REFUTED as stated** (1-2 vote).
   The $689K is founder-stated too, and predates the $3M+ claims by weeks of
   documented hypergrowth — a claims-inconsistency finding at ~1.45×
   contemporaneous, not independent verification. zilla.so is an anonymous
   SEO-style blog (near-identical clones at preuve.ai/cto.new). The honest
   replacement: **36kr's ~2.2× headline-vs-recurring decomposition** +
   "no independent audit exists." lane_F_world.md:35 and any doc repeating
   4.4× must carry this downgrade. (CLAUDE.md TAM track description
   corrected in the same commit as this dossier.)
2. **Polsia's build timeline is UNKNOWN** — both the "~30 days" narrative
   (lane_F snapshot / contextstudios headline) and the competing "six
   months, Paris, ~$1M pre-seed" story were refuted (0-3 each).
3. **Founder is Ben Cera** (Broca appears in refuted material).
4. **"$49/mo" survives; "$50/mo at interview time" refuted** — carry $49
   with the $29–59 review range.
5. **36kr English headline "$200M financing, $72M revenue" is a RMB
   mistranslation** (¥→$): never cite those dollar figures.

## 6. What this means for dharma_swarm (the exceed-map, re-verified)

- **The empty seat is confirmed, and bigger than assumed.** Not only does
  neither incumbent publish verifiable revenue — neither publishes ANY
  approval mechanics, audit trail, or safety layer. Our typed gates +
  witnessed receipts occupy a seat the verified public record shows is
  empty across the category.
- **The architecture gap is smaller than the marketing gap.** Polsia's
  evidenced engine (scheduled Claude-CLI subprocesses on Celery) is
  architecturally *shallower* than our existing orchestration/spine layer.
  The Behind lanes on the parity board are distribution/billing/customer
  organs — commodity genealogy, assembleable — not deep tech.
- **The one organ worth studying is Cofounder's memory consolidation**
  (core-memory tier: session→knowledge compression + sleep-time compute).
  Our MemoryKernel is the corresponding organ; MemoryAgentBench
  (arXiv 2507.05257) is a real, adoptable eval frame.
- **Honest-ARR thesis stands, restated soberly:** the category's revenue
  numbers are founder-dominated, decomposition-disputed, and unaudited —
  the wedge is "no incumbent's numbers are third-party verifiable," not any
  single gap multiplier.

## 7. Open questions (untested, do not assert)

1. Does the PolsiaAI/Polsia dump correspond to production polsia.com, or is
   it a sanitized/aspirational mirror?
2. Cofounder's durable execution, tenancy, context isolation, and actual
   MCP-ecosystem pinning — zero public evidence.
3. Polsia retention/cohort revenue post-raise (churn risk implied by ~$50/mo
   best-case customer outcomes; no fresh third-party data).
4. Is Polsia's per-tenant provisioning automated at 8,000+ company scale, or
   manually assisted (36kr/Reddit allegation untested)?

## 8. Source register (quality-labeled)

Primary: github.com/PolsiaAI/Polsia (curated dump — see provenance caveat);
mixergy.com/interviews/this-ai-generates-689k (verified real via Apple
Podcasts id 1000752668901). Secondary: eu.36kr.com/en/p/3825813697565316
(¥-mistranslation warning); gtmnow.com/gtm-192 (founder narrative relay);
forbes.com (contributor-tier) + builtinnyc.com + blog.usv.com (Cofounder
round). Vendor blogs: generalintelligencecompany.com (memory post,
superoptimization essay, agent-native-engineering); cofounder.co/resources.
Blog/forum, handle with care: zilla.so/blog/polsia-review (anonymous,
SEO-style); news.ycombinator.com item 48252194; x.com/panphora (scam
allegation, firsthand-audit claim). Rejected as unreliable by extractors:
polsia.com landing (403/no claims), aiready.so, aitoolsclub.com,
preuve.ai (zilla clone).

Benchmark: arXiv 2507.05257 (MemoryAgentBench) — verified real.
