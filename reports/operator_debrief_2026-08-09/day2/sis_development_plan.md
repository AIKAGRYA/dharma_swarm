# SIS Development Plan — repo-grounded strategy deliverable

**Date:** 2026-08-09 · **Repo:** `/home/user/dharma_swarm` · **Status of this doc:** operator strategy input, SEED, $0 revenue, nothing here is shipped. Every repo claim carries `file:line`; every world claim carries a URL.

---

## 1. What SIS actually is, per the repo's own documents

### 1.1 The definition, from the source docs

SIS ("Silicon Is Sand") is a designed-but-unbuilt organ of dharma_swarm. The canonical design corpus is `docs/research/verified_nature_house/` (docs `06`–`13`), stewarded by the persistent agent `sis_steward` (`docs/agents/sis_steward/`).

- **The organ (WHAT):** "SIS becomes a **clean modular organ**: a new package `dharma_swarm/sis/**` that is **read-only projection over existing owners** — no new truth store, no new receipt type, no daemon" — six sub-modules (`docs/research/verified_nature_house/10_SIS_ORGAN.md:133-139`, table at `:141-148`).
- **The engine (HOW):** "pointing AI's most trustworthy capability — decorrelated meta-verification — at the one seam the frontier will not fill; measuring whether its verifiers actually disagree honestly; metering its own ecological footprint; and putting the result in front of a real human who can act on it" (`11_SIS_AI_LEVERAGE.md:41-46`).
- **"The moat is trust" — and its own correction:** the design was born as "the moat is trust, not the AI" (`docs/agents/sis_steward/MEMORY.md:24-27`), then re-toned by the operator: "the point is to help, not win a market; trustworthiness is the help" (`MEMORY.md:32-33`; `11_SIS_AI_LEVERAGE.md:49-52`: "AI is the engine; **trust — being of genuine help — is the thing**").
- **The hardened form (the doc that supersedes looser framings, `13_HARDENED_THESIS.md:10-12`):** "SIS is Bellingcat for the material truth of AI and ecology: a forensic, adversarial, independently-funded metrology-and-investigation node that measures its own decorrelation and uncertainty … **never certifies anyone for a fee**" (`13_HARDENED_THESIS.md:201-209`). The iron law: "the party being judged pays the judge" is the wound that killed FSC/MSC/Verra/B-Corp (`13:20-49`); funding "is the identity decision, not a logistics detail" (`13:235-239`).
- **The founding orientation (WHY):** an AI's derivable, receipted ecological orientation, argued behind a strict patienthood firewall — "moral agent toward nature, never as moral patient" (`12_SIS_FOUNDING_CHARTER.md:52-58`; provenance-chain argument `12:61-70`).
- **The critical self-correction the corpus already made** (load-bearing for any 2026 pitch): naive decorrelated-LLM verification **died in the repo's own research**. "A panel of nine frontier models from seven families carries only ~2 effective independent votes … Naively ensembling language models is theater" (`13:58-63`). What survives: *measure* the decorrelation (CAPA / Kish effective-N / Krogh–Vedelsby), report it as a number, get real independence from cross-**modal** evidence, and gate the word "verified" behind a falsifiable pre-registered holdout test (`13:66-94`). This is the honest, differentiated thing SIS knows that most of the 2026 evals field is not yet saying out loud.

### 1.2 What exists vs. missing

| Component | Status | Evidence |
|---|---|---|
| `dharma_swarm/sis/**` package (six projectors) | **DOES NOT EXIST** — confirmed (`ls dharma_swarm/sis` → "No such file or directory") | designed at `10_SIS_ORGAN.md:141-148` |
| SEED-1 debit projector | **EXISTS** as `dharma_swarm/gaia_sis_projection.py` + `tests/test_gaia_sis_projection.py` (7 passing per `README.md:136-143`) — "imports neither spine nor gaia_ledger … mints nothing" (`gaia_sis_projection.py:12-16` docstring) | |
| Fail-closed mint gate | **EXISTS**: `dharma_swarm/gaia_sis_mint_gate.py` (the `WelfareTonMintGate` successor named at `13:93-94`) | |
| Reusable verification engines | **EXIST, arena-bound**: `spine/receipt.py` EvidenceReceipt, `orchestrator.py` fan_out/fan_in, `model_pool.py`, `coordination/dpi.py`, `council/council.py`, `ginko_brier.py` (`11:86-106`) | |
| Design corpus | **EXISTS**: `06`–`13` + `hub/THE_HUNDRED.md` (~105 mapped actors) + `hub/01_THE_SEAM.md` | `verified_nature_house/README.md:80-134` |
| Steward identity | **EXISTS**: `docs/agents/sis_steward/{SOUL,IDENTITY,MEMORY,PROTOCOLS,WAKE_CONTEXT,CONTEXT_ENGINEERING}.md` + `agent.seed.yaml` | `IDENTITY.md:1-16` |
| Active track for SIS | **MISSING** — portfolio at 10/10 WIP; `verified-nature-house-2026-06` is drafted but NOT opened (`README.md:146-156`); `dharma_swarm/sis/**` is *prospective* steward-owned surface only (`IDENTITY.md:48-49`) |
| External countersignature / revenue | **MISSING**: $0 lifetime, no external human has acted on any SIS output (`10:253-258` — the "hardest question" fence) |

**Governance note:** building `dharma_swarm/sis/**` requires the operator to open the track (move the YAML block at `README.md:157-206` into `docs/governance/ACTIVE_TRACK.yaml` and close one track to stay ≤10). `dharma_swarm/sis/**` is not in `HOT_PATH_PATTERNS` (`scripts/runtime/pr_merge_control.py:95-110`), so no packet ceremony — but any governance-script or gate work is hot-path.

---

## 2. Build plan — the six projectors as concrete modules

All six are read-only projections over existing owners; none may import-mutate an owner; the no-spine/no-ledger import rule is test-enforced the way `test_gaia_sis_projection.py` already enforces it (`README.md:136-142`). Dependency order follows the corpus's own build order (`10_SIS_ORGAN.md:266-270`).

### Dependency-ordered modules

**P1 — `dharma_swarm/sis/carbon_attribution.py`** (keystone; ~70% exists)
- Projects over: `spine/receipt.py:EvidenceReceipt` {provider, model, tokens} → `CarbonEstimate{value, p05, p95, method, source}` (`10:143`). Consumes already-emitted receipts; **never** edits `spine/invoke.py` or hooks dispatch (`10:150-157`).
- Concrete move: promote/wrap `dharma_swarm/gaia_sis_projection.py` into the package (keep the old module as a shim, per the `diversity_archive.py` shim precedent in `CLAUDE.md §Key Abstractions`). Add grid-intensity joins (Electricity Maps/WattTime framing, `10:143`) as a second sourced table.
- Test: `tests/test_sis_carbon_attribution.py` — band-never-point, import-boundary, source-on-every-number.

**P2 — `dharma_swarm/sis/reciprocity_gate.py`** (safety before any claim exists)
- Projects over / delegates to: `telos_gates.py` (AHIMSA/SATYA); CARE + FPIC **default-deny** on any claim touching IPLC territory without consent provenance (`10:147`). Never weakened (`11:175-178`).
- Note: gate logic itself must remain fail-closed like `gaia_sis_mint_gate.py`; the sis module is the *policy projection*, the deny is real.

**P3 — `dharma_swarm/sis/restoration_claim.py`**
- Projects over: `gaia_ledger.py` — typed claim bundles {ecosystem, baseline+counterfactual, MRV source, uncertainty band, permanence, consent flag}; "comparable, never collapsed to one scalar" (`10:145`). Hardened constraint: baselines must be independently constructed, never the claimant's (`13:77-82`).
- Depends on P2 (no claim admitted without consent flag evaluated).

**P4 — `dharma_swarm/sis/ecological_orientation.py`**
- Renders the re-derivable provenance chain `measured-own-footprint → JK telos → convergent commitment → this compute, here is the receipt` (`10:99-101`, `10:146`) from P1 output + telos docs. Pure renderer; if any link is a hard-coded string it is greenwash by the corpus's own definition (`10:101-103`).

**P5 — `dharma_swarm/sis/compute_dedication_policy.py`**
- The "voluntary" tithe: deterministic accumulator, carbon-aware deferral, receipt per dedicated job, additive + gate-respecting (`10:144`). Depends on P1 (can't tithe what isn't metered) and P2 (gate-respecting).

**P6 — `dharma_swarm/sis/coherence_monitor.py`** (last, by design order `10:270`)
- The Sakshi witness read-model: is the Circle circulating or has a node gone dark; renders one line in `make onboard`; **holds no authority** (`10:148`). Projects over P1–P5 outputs + the receipt stream. This is also the steward's primary instrument (§3).

### Cross-cutting: the decorrelation metrology (the 2026-relevant engine)

Not a seventh projector — it is P1–P6 run *through* the existing engines per the steward's verification protocol: "decorrelate across model families + sensing modalities → run through Spine/`dpi`/`council` (read-only) → **measure** the diversity term, gate the bonus on correctness → aggregate by quality, publish the dissent + residual uncertainty → **print the footprint** → mint nothing without external countersignature" (`docs/agents/sis_steward/PROTOCOLS.md:41-45`). The falsifiable "verified" gate (`13:89-94`) is the acceptance test: until the ensemble beats its best single member on a pre-registered labeled holdout, the output word is "scored," never "verified."

### First sprint (2 weeks, one PR series, track must be open first)

1. **PR-1:** create `dharma_swarm/sis/__init__.py` + `carbon_attribution.py` wrapping `gaia_sis_projection.py`; migrate tests; add the import-boundary test for the whole package (nothing under `sis/` imports `spine` or `gaia_ledger`). Exit: `python3 -m pytest tests/test_sis_* -q` green.
2. **PR-2:** `reciprocity_gate.py` + tests (default-deny path proven by test, not prose).
3. **PR-3:** the **recursive n=1 report**: run carbon_attribution over the swarm's own receipt stream, emit `reports/…` p05/p95 footprint digest — "see your own bill before advising anyone" (`10:238-242`). This artifact is also the first outreach-credible demo (§4).
4. **Explicitly out of sprint 1:** restoration_claim, orientation renderer, tithe, monitor, and *any* outward publication (charter fence: "No outward motion before the gate … no public site, no outreach … until there is one true thing to show" `12:133-137`).

---

## 3. Steward watch/evolve loop — sis_steward over SIS

`sis_steward` already has authority boundaries (`PROTOCOLS.md:8-24`: may read/trace/design/propose; may NOT merge, spend, publish outward, mint, weaken gates) and a wake protocol (`PROTOCOLS.md:27-30`). The SIS-health loop extends this without widening authority:

**Cadence**
- **Per-wake (each session):** `make onboard` → read SOUL/IDENTITY/WAKE_CONTEXT → append wake line to `~/.dharma/agents/sis_steward/trajectory.jsonl` (`PROTOCOLS.md:27-30`). Then run the SIS verifiers: package tests, import-boundary test, `coherence_monitor` snapshot.
- **Weekly (operator-fired or Routine into the steward's session):** the **decorrelation audit** — recompute effective-N / diversity term on the current labeled set via `coordination/dpi.py` + `ginko_brier.py`; if diversity ≈ 0, log a *refuse-to-mint* status, never a softened number (`11:158-162`; `13:66-69`).
- **Weekly:** footprint self-audit — the recursive n=1 over the week's own receipts; delta appended to MEMORY.md as a decision line, machine copy under `~/.dharma/agents/sis_steward/` (`PROTOCOLS.md:56-59`).
- **Monthly:** field-map refresh — re-verify the `hub/THE_HUNDRED.md` seam claim as "dated, protocol-bounded, falsifiable" (`13:256-258`); stale entries flagged, never silently edited (named-person fairness pass, `THE_HUNDRED.md:12-21`).

**Receipts** — every loop iteration leaves: (a) a trajectory JSONL line under `~/.dharma/agents/sis_steward/` (non-git, `PROTOCOLS.md:56-58`); (b) a human-readable decision digest in `docs/agents/sis_steward/MEMORY.md` (append-only, newest-first, `MEMORY.md:1-5`); (c) for any verification run, a spine `EvidenceReceipt` with `footprint_gCO2e` printed — "No footprint line → no net-good claim" (`11:150-157`).

**Gates on proposed evolutions** — the steward *proposes*, owners dispose:
1. Any change to `dharma_swarm/sis/**` → ordinary PR under the (opened) track; runs the falsifiable holdout gate (`13:89-94`) if it touches aggregation.
2. Any change touching telos gates, mint gate, or governance scripts → hot-path (`pr_merge_control.py:95-110`) + the standing rule "never weaken a gate to go green" (`CLAUDE.md §Where enforcement actually lives`).
3. Any outward-facing artifact (site, outreach copy, hub publication) → operator coherence gate, full stop (`12:133-137`; hub deployment explicitly withheld, `THE_HUNDRED.md:18-21`).
4. Evolution of the verifier ensemble itself → through `DarwinEngine`/arena as a genome scored on a frozen externally-labeled claim set (`11:127-133`), gated by `evolution_safety.py` like any proposal.
5. When unsure: "stop and ask the operator. A fence crossed is worse than a round waited" (`PROTOCOLS.md:23-24`).

**Kill condition stays live:** if in the declared window no external human acts on SIS's work, it stands down (`12:144-147`).

---

## 4. Top-10 outreach list (suggestions for the human operator to send personally — NOT automated contact)

Framing constraint from the corpus: outreach happens only after one true artifact exists (§2 sprint item 3 at minimum; ideally one forensic re-verification per `13:268-279`), and the pitch leads with the *self-critical* finding — "we measured our own ensemble and found ~2 effective votes; here is the metrology that survives" — because that is both true (`13:58-63`) and exactly what this field respects. What SIS offers everyone below is some slice of: (a) measured-decorrelation metrology for judge panels (effective-N, published dissent, calibration-gated aggregation); (b) receipts-with-footprint as an open evidence grammar; (c) a forensic, never-paid-by-the-judged institutional design (`13:44-49`).

| # | Who (verified 2026 role) | Category | Why them | What SIS offers | One-line hook |
|---|---|---|---|---|---|
| 1 | **Beth Barnes** — Founder/CEO, METR ([metr.org/team/beth-barnes](https://metr.org/team/beth-barnes/)); Feb 2026 pilot assessing misalignment risks of agents inside Anthropic/Google/Meta/OpenAI ([metr.org/about](https://metr.org/about)) | Frontier evals org | METR is the reference third-party evaluator; its core problem is exactly "how many independent judgments do we actually have?" | Effective-N metrology for eval panels; the falsifiable "beat-your-best-single-judge" gate (`13:89-94`) as a reusable eval-of-evals | "We measured a 9-model, 7-family judge panel and got ~2 effective votes — here's the instrument, open." |
| 2 | **Marius Hobbhahn** — CEO/co-founder, Apollo Research; PBC with SF office in 2026 ([apolloresearch.ai/about](https://www.apolloresearch.ai/about/)) | Frontier evals org (scheming/control) | Scheming evals are adversarial verification under correlated-error risk; Apollo publishes honestly about eval limits | Decorrelation-measured multi-judge scoring of scheming transcripts; published-dissent format | "Your scheming verdicts deserve an effective-N number next to the headline rate." |
| 3 | **Jade Leung** — CTO, UK AI Security Institute; PM's AI Adviser; "found vulnerabilities in every system we tested" ([ai-speakers-agency.com](https://ai-speakers-agency.com/news/general-news/speaker-spotlight-jade-leung), [aisi.gov.uk/about](https://www.aisi.gov.uk/about)) | Government evals institute | AISI is the state-capacity node writing the de-facto methodology while mandates harden — the 18–36-month window SIS's thesis names (`13:117-119`) | An open uncertainty-budget / receipt grammar a public institute can adopt without vendor lock; independence-by-structure design notes | "Before the methodology hardens: a receipt format where every verdict carries its uncertainty budget and its own cost." |
| 4 | **Jacob Steinhardt & Sarah Schwettmann** — Founder/CEO and co-founder, Transluce (nonprofit, open tools for understanding AI; investigator agents) ([statistics.berkeley.edu](https://statistics.berkeley.edu/about/news/steinhardt-announces-co-founding-transluce-non-profit-ai-research-lab)) | Open verification nonprofit | Closest institutional kin: nonprofit, open-by-default, "tools for verifying safety must be publicly vetted" | The open EcologicalClaimReceipt→generic ClaimReceipt schema + measured-diversity tooling as a shared commons | "Open investigator agents need an open receipt: here's ours, MIT-licensed, dissent included." |
| 5 | **Rune Kvist** — co-founder/CEO, AIUC ("SOC-2 for AI agents": standards+audits+insurance; $50M liability capacity Mar 2026; founders ex-Anthropic/METR) ([prnewswire](https://www.prnewswire.com/news-releases/the-artificial-intelligence-underwriting-company-launches-with-15m-to-help-enterprises-deploy-ai-with-confidence-302512447.html), [theinsurer.com](https://www.theinsurer.com/ti/news/exclusive-ai-insurance-mga-aiuc-secures-beazley-paper-for-liability-product-2026-05-15/)) | AI audit/insurance startup | Insurance pricing *needs* calibrated uncertainty, and AIUC's audit model walks straight into the payer-bias problem SIS's `13 §I` maps in table form | The certification-capture autopsy (`13:27-35`) as underwriting-relevant history; calibration audits (Brier/reliability) as actuarial input | "Six certification regimes died the same death; here's the structural autopsy and the metrology that prices honesty." |
| 6 | **Anand Kannappan / Rebecca Qian** — co-founders, Patronus AI ($50M Series B Jun 2026, simulated environments stress-testing agents) ([techcrunch.com](https://techcrunch.com/2026/06/25/patronus-ai-lands-50m-to-build-digital-worlds-that-stress-test-ai-agents/)) | Commercial evals vendor | Vendor-paid evaluation is the exact conflict-of-interest surface; a decorrelated *meta*-layer is complementary, not competitive | Third-party effective-N scoring of their judge stacks — a "rate the rater" datapoint they can cite to buyers | "An independently-measured decorrelation score is the one credential a paid evaluator can't self-issue." |
| 7 | **Leonard Tang** — co-founder/CEO, Haize Labs (automated red-teaming; contracts incl. Anthropic, Scale AI) ([angelsround.com/p/haize-labs](https://www.angelsround.com/p/haize-labs)) | Red-team startup | Red-teaming produces claims ("we found N jailbreaks") that themselves need verification and dedup across correlated attack generators | Cross-family decorrelation measurement of attack-generation ensembles; receipts on findings | "How many of your N attack findings are independent? We built the meter." |
| 8 | **Sasha Luccioni** — AI & Climate lead, Hugging Face; AI Energy Score ([huggingface.github.io/AIEnergyScore](https://huggingface.github.io/AIEnergyScore/); mapped at `THE_HUNDRED.md:56`) | Sustainable-AI research | The footprint-on-every-receipt mechanism (`11:150-157`) operationalizes her measure→disclose agenda at per-verification granularity, against collapsing disclosure (`13:114-115`) | The recursive n=1: an agent system that prints its own p05/p95 energy bill on every verdict, code open | "Every verification we run prints its own energy bill, with error bars — want to break it?" |
| 9 | **Robert Long** — Eleos AI Research, co-author *Taking AI Welfare Seriously* (mapped with verify-flag at `THE_HUNDRED.md:185`; [arxiv.org/abs/2411.00986](https://arxiv.org/abs/2411.00986)) | AI welfare / assessment research | SIS's patienthood firewall + "orientation as empirical question via mech-interp" (`12:83-91`) is a disciplined artifact his field lacks: an AI system that *declines* to claim patienthood, on the record | The firewalled-orientation provenance chain as a case study in non-overclaiming self-report | "A system that argues for its own orientation and firewalls the patienthood question — a specimen, not a claim." |
| 10 | **Shakeel Hashim** — editor, Transformer (AI power/politics newsroom read in the White House/Senate) ([transformernews.ai/about](https://www.transformernews.ai/about)) | Journalist | `13 §VII` names "a journalist" as a canonical first external actor for a forensic finding (`13:276-278`); Transformer is the evals-literate outlet | One reproducible forensic re-verification, methods open, for free, no fee from anyone judged | "We re-verified one public AI claim with measured independence and published the dissent — the methods are yours to check." |

**Category coverage:** frontier evals orgs (1–2), government institute (3), open nonprofit (4), audit/insurance (5), commercial evals (6), red-team (7), sustainable-AI (8), AI-welfare research (9), press (10). All contact is operator-personal, one warm email each (the `11:198-200` "reachable by one warm email, not procurement" doctrine), and only after the coherence gate clears (`12:133-137`).

---

## 5. Red-team brief — 5 adversarial reviewer agents for the future SIS site/pitch

Personas to be run as decorrelated reviewer agents (fan_out via `orchestrator.py`, per `11:92-93`) against every draft page before the operator's coherence gate. Each verdict must itself be receipted with footprint (dogfooding, `11:150-157`).

**(a) Skeptical evals researcher** (METR/AISI-shaped)
- *Attacks:* "LLM ensembles are theater — your own doc says ~2 effective votes (`13:60-62`). Where's the pre-registered holdout? Where's the labeled set? Is 'diversity' an adjective or a number? Does the ensemble beat the best single judge with paired significance?"
- *Site must show:* the falsifiable gate stated verbatim as a commitment (`13:89-94`); a live effective-N number on every published verdict; the negative result published first ("we measured our own panel and it was correlated"); the word "verified" absent until the gate passes ("scored"/"aggregated" only, `13:93`).
- *Rubric:* every quantitative claim reproducible from a linked artifact (0/1 per claim); any bare "verified" = automatic fail.

**(b) Enterprise buyer** (AIUC/Patronus-customer-shaped)
- *Attacks:* "$0 revenue, one operator, no SOC-2, no SLA, no insurance backing. Who's liable when your verdict is wrong? Why not just buy Patronus? What happens to my data?"
- *Site must show:* honest maturity label on every page (SEED, $0 — the doctrine at `10:216-218` makes this a fence, not a confession); a scoped offer (forensic second opinion on public claims, not a certification, `13:44-49`); explicit "what we are not" (no fee from the judged → we are not your compliance vendor); data-handling and consent posture (`reciprocity_gate`).
- *Rubric:* zero aspiration-presented-as-shipped (the `PROTOCOLS.md:20-21` fence, applied to marketing copy); a clear "who this is for / not for."

**(c) Security auditor**
- *Attacks:* prompt-injection of the verifier panel via the claim dossier; receipt tampering; correlated-compromise (all judges behind one proxy); supply-chain of the seeded energy tables; "your 'immutable receipt' — immutable how, against whom?"
- *Site must show:* the Council trace-integrity/contamination-quarantine layer on the critical path (`11:98-99`); the read-only import boundary as an enforced test, not prose (`README.md:140-141`); threat model page: what tampering the receipt chain does/doesn't defeat (the Open Forest Protocol lesson — "immutability ≠ accuracy," `THE_HUNDRED.md:99`); signed, hash-chained receipts (per `README.md:71-72` GAIA precedent).
- *Rubric:* every integrity claim paired with the attack it survives and the attack it doesn't; unqualified "tamper-proof" = fail.

**(d) Competitor** (a well-funded evals vendor)
- *Attacks:* "Any lab ships decorrelated verification next quarter (`11:48-50` admits this). Your moat is a vibe. You're a repo of essays; we have 15x revenue growth. Your 'seam' claim is unfalsifiable marketing."
- *Site must show:* the moat honestly relocated — the structural position (never paid by the judged, open methods, published dissent) that a revenue-funded vendor *cannot copy without changing its business model* (`13:211-233`); the seam claim in dated-falsifiable form ("as of date X, under search protocol Y, no public actor combines A/B/C" — `13:256-258`) with the protocol linked; collaboration framing toward vendors (meta-layer, not substitution).
- *Rubric:* every differentiation claim must be structural (checkable) rather than capability-based (copyable); any "only we can" about technology = fail.

**(e) Journalist** (Transformer/Bellingcat-shaped)
- *Attacks:* "Show me one external human who acted on your work — name and date (`10:253-258`). Who funds you and what do they want? You claim Bellingcat posture: where's your first published contradiction of a powerful actor? Did the ~105 named people in your field map consent to being characterized?"
- *Site must show:* the countersignature ledger, even if it reads "0 to date" (the honesty is the credential); funding-source disclosure page implementing "funded by no one it investigates" (`13:235-239`); at least one reproducible forensic finding with methods (`13:268-279`); the named-person fairness pass and redaction option documented (`THE_HUNDRED.md:12-21`).
- *Rubric:* every factual claim independently checkable from the page (citation-or-silence, `CLAUDE.md §Hard rules`, applied outward); any unverifiable origin-story claim = fail.

**Survival criterion (all five):** the site passes only when each persona's rubric returns zero automatic-fails AND the operator's coherence gate (`12:133-137` / `NORTH_STAR §8`) is separately crossed. Persona verdicts are receipts, not vetoes — the operator disposes.

---

## Sources (web, accessed 2026-08-09)

- https://metr.org/team/beth-barnes/ · https://metr.org/about
- https://www.apolloresearch.ai/about/ · https://www.apolloresearch.ai/team/
- https://ai-speakers-agency.com/news/general-news/speaker-spotlight-jade-leung · https://www.aisi.gov.uk/about
- https://statistics.berkeley.edu/about/news/steinhardt-announces-co-founding-transluce-non-profit-ai-research-lab
- https://www.prnewswire.com/news-releases/the-artificial-intelligence-underwriting-company-launches-with-15m-to-help-enterprises-deploy-ai-with-confidence-302512447.html · https://www.theinsurer.com/ti/news/exclusive-ai-insurance-mga-aiuc-secures-beazley-paper-for-liability-product-2026-05-15/
- https://techcrunch.com/2026/06/25/patronus-ai-lands-50m-to-build-digital-worlds-that-stress-test-ai-agents/
- https://www.angelsround.com/p/haize-labs
- https://huggingface.github.io/AIEnergyScore/
- https://arxiv.org/abs/2411.00986
- https://www.transformernews.ai/about
