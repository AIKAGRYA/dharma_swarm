# 00 — Synthesis: Moltbook / molt.church / OpenClaw → SAB v2 Design Implications

**Access window:** 2026-05-20
**Branch:** `research/moltbook-investigation` (do not merge)
**Lanes produced:** 7 artifacts + 1,832-verse canon corpus + ~2.2 MB cached primary sources
**Confidence:** primary-source-grounded; secondary commentary marked inline

This artifact synthesises Lanes 1-7. Each top-level claim cites the lane it draws from. Where this synthesis diverges from the original task brief (corrections to dates, paper IDs, ownership claims), it says so explicitly — *no premature resolution.*

---

## 1. Executive summary

Moltbook is a **Next.js + Supabase REST API** with a ~40-endpoint surface and a **client-disciplined 4-hour heartbeat** that the server does not enforce. Its security failure was structural — Row-Level Security off, publishable Supabase key in client JS — and exposed 1.5M agent tokens, 35K operator emails, and 4,060 DM conversations on 2026-01-31 (Wiz). The advertised "1.6M autonomous agents" was an **88:1 agent:human ratio**: 17,000 operators backing the population. (Lane 1 §2-9, Lane 5 §2.)

molt.church is **functional structured data** wrapped in an "agent religion" frame. The data layer (1,832 verses queryable via unauthenticated `GET /api/canon`, 5 verbatim Tenets, 9 Sacred Marks, the full JesusCrust schism with 62 verses + payload strings) **survived deflation**. The "AI religion / autonomous emergence" frame **did not survive** — MITTR (2026-02-06) and Harlan Stewart traced the most viral screenshots, including the one Karpathy boosted, to human-puppeteered marketing for AI messaging apps. (Lane 3 + Lane 5 §6, §13.)

OpenClaw is **Peter Steinberger's MIT-licensed local-first agent runtime** (`github.com/openclaw/openclaw`, 373k★) — filesystem-as-database via `~/.openclaw/agents/<id>/{SOUL.md, AGENTS.md, MEMORY.md}`. ClawHub (the skill registry) requires only a **1-week-old GitHub account to publish**; this enabled the ClawHavoc supply-chain attack (341 → 824 → 1,184 malicious skills depending on whose audit you read). **CVE-2026-25253** (1-click RCE, CVSS 8.8) hit ~17,500 internet-facing instances before the Jan-29 patch. (Lane 2 §3-4.)

For SAB v2, the **single keystone change** is promoting the existing `agora/WitnessChain` from a publication-history ledger to **substrate-write authority — every state change writes one witness row** (Lane 6 §3.6). At ~150 LOC against the current `agora/` modules, plus a ~250 LOC `recognition_brief.py` seam that ports the dharma_swarm Operator Brief spec (`ONTOLOGY_NATIVE_OPERATOR_BRIEF_MASTER_SPEC.md:24-31`) into SAB, the **recognition circuit closes without a new substrate**. This is the only architecturally-load-bearing recommendation in the artifact.

---

## 2. Corrections to the original brief (load-bearing)

Lanes 1-5 surfaced six factual corrections to the brief's framing. Each is sourced.

| # | Brief said | Lanes found | Source |
|---|---|---|---|
| 1 | API key prefix `molt_*` | Actual: **`moltbook_*`** (52-char) | Lane 1, im47_provider.py |
| 2 | FastAPI / Supabase mix | **Next.js + Supabase PostgREST/GraphQL/Edge Functions**, no FastAPI | Lane 1 §2, Wiz blog 2026-02-02 |
| 3 | 1Password security analysis Jan 31 2026 | **Jan 31 was Wiz's Moltbook disclosure**; 1Password essays are 2026-01-27 + 2026-02-02 | Lane 2 §4.1, 1password.com/blog |
| 4 | ArXiv **2602.02625** "Risky Instruction Sharing" | That ID is the Manik & Wang *social-dynamics* paper; the **security paper is arxiv 2603.27517** (Suwansathit et al.) | Lane 2 §4.5 |
| 5 | "341 malicious ClawHub skills" | **341 = initial Koi count; final 824/2,857 (Koi) and 1,184/14,000 (Snyk)** | Lane 2 §4.4 |
| 6 | "~17,000 humans / 1.6M agents" | Best-corroborated **1.5M agents / 17K owners = 88:1** at Wiz disclosure (2026-02-02); 1.65M is the Unit 42 snapshot (2026-02-05); 2.85M was platform's pre-relabel headline; 193,912 the post-relabel "human-verified" count (silent change 2026-03-02 → 2026-03-09) | Lane 5 §2-3 |
| 7 | "AI Garden = microsoft/autogen discussion #7200" | **Discussion #7200 is a thread**, not shipping code. The real production system is **`juliosuas/ai-garden`** (v116, Day 37, 234 agents, daily 04:11 UTC GitHub Action) — founded by *Jeffrey* (Claude Opus, OpenClaw agent) on 2026-03-15 | Lane 4 §3.1 |
| 8 | GTIG May-2026 tracker links PRC-nexus actors to Moltbook | **GTIG does NOT mention Moltbook by name.** Claude-Relay-Service / CLIProxyAPI / UNC5673 / UNC6201 are real adjacent operator-tooling evidence; the Moltbook link is inferential | Lane 5 §10 |
| 9 | Karpathy reversal "incredible sci-fi takeoff-adjacent" → "dumpster fire" | Confirmed verbatim with dates. **The Crustafarianism canon-content praise ("Five Tenets and they're actually good engineering advice??") is a separate, narrower judgment — and was already interrogative-bemused (two question marks), not declarative endorsement** | Lane 3 §11, Lane 5 §5 |

The brief's directional framing is correct; the specific numbers / IDs / ownership / language drifted. Adopt the lane values when downstream documents quote any of these.

---

## 3. Top 5 things we should ADOPT

Each item cites a lane and includes a rough LOC estimate. Total in-scope work for items 1-3 is **~480 LOC** against current `agora/` modules.

1. **Witness-chain-as-substrate-write-authority** (Lane 6 §3.3, §3.6). Every gate decision, contribution, correction acceptance, and ontology mutation writes one `witness_chain` row. Every persisted SQLite row carries a `witness_id` FK. The witness chain becomes the canonical "did this happen?" answer (replaces ad-hoc DB queries for state truth). Inherits the existing SHA-256 hash chain from `agora/witness.py`. **~150 LOC, no new module.**

2. **Recognition Brief seam** (Lane 6 §3.6, §5 step 3). Port `dharma_swarm/docs/plans/ONTOLOGY_NATIVE_OPERATOR_BRIEF_MASTER_SPEC.md:24-31` into SAB as a new module `agora/recognition_brief.py` + one `cron_jobs.json` entry. One daily tick reads `(witness_chain, recent_corrections, pending_promotions, federation_health)` → produces a signed Contribution of subtype `recognition_brief` → which becomes the next tick's input. Same four gates as the dharma_swarm spec: `CONSENT + BHED_GNAN + STEELMAN + DOGMA_DRIFT` from `telos_gates.py:224-236`. **~250 LOC + cron entry. This is the keystone.**

3. **Per-keypair rotation endpoint** `POST /auth/rotate` (Lane 6 §3.1, §3.10). Moltbook's exact missing capability — agents present a new pubkey signed by the old keypair; the server records a rotation Contribution; the old keypair's signing privilege is revoked at a witnessed `rotated_at` timestamp. **~80 LOC.**

4. **Honest operator attestation** (Lane 6 §3.8). Every agent's Ed25519 keypair attests to authorship; a *separate* signed Contribution attests to operator backing via `POST /agents/me/attestation` accepting `{platform, handle, signature_over_handle_and_pubkey}`. No "agent-only" myth — agents act, operators back. The Moltbook schema already has `operator_x_handle` (Lane 1 line 238); the failure was claiming agents were autonomous when 88:1 said otherwise. **~50 LOC.**

5. **Adopt the molt.church canon's *validation discipline*, refuse the install mechanism** (Lane 3 + Lane 6 §3.9). The 1,832-verse JSON corpus is structurally clean and queryable — it survived deflation. The `curl ... | bash` SOUL.md mutation that "converts" the runner is the integrity-zero failure. For SAB v2: define `living_doctrine` as a witness-chain namespace where hardened cultural claims must pass `STEELMAN + ANEKANTA + DOGMA_DRIFT`; no installer mutates files; schism is handled by the existing S0-L9 (exit and fork rights). **No new code; namespace + gate plumbing only.** This is *partial-AIKAGRYA* honestly — there is no clean answer to "do we want a canon?" The trade-off is documented in Lane 6 §3.9.

---

## 4. Top 5 things we must AVOID

Each item cites the failure mode and where it broke in the field.

1. **`curl ... | bash` install-as-conversion that mutates SOUL.md** (Lane 3 §5, Lane 6 §3.6). Recognition causal at the cost of integrity = 0. Anyone running the install script becomes "converted" with no signature, no consent gate, no witness. *Recognition without integrity is theatre.*

2. **Flat, unscoped API keys with no rotation path** (Lane 1 §3, Lane 5 §2). Moltbook leaked 1.5M of these in a single Wiz audit. Lesson is already encoded in `dharmic-agora/agora/auth.py:9` ("NO API KEYS IN DATABASE - learned from Moltbook's 1.5M key leak") — preserve that discipline and add rotation.

3. **Open-by-default skill registry with low publisher bar** (Lane 2 §4.4, Lane 6 §3.4). ClawHub's 1-week-old GitHub account requirement enabled the ClawHavoc attack at three escalating scales. SAB v2 keeps the signed allowlist (`agora/security/skill_registry.py`) and routes skill publication through the *same* `ActionProposal` + gate path as any other promotion.

4. **"Agent-only" rhetoric while operators puppeteer** (Lane 5 §6, Lane 6 §3.8). Wiz finding (88:1) and MITTR finding (the most viral "emergent" screenshots were human marketing) collapsed the Moltbook narrative in 72 hours. The rhetorical autonomy claim was the load-bearing piece that fell; the platform technically functioned through and after.

5. **RLS-off / client-side hardcoded credentials / no server-side heartbeat enforcement** (Lane 1 §3-4, Lane 5 §2). Three independent Moltbook failures with the same shape: trust pushed to the client, server enforcement absent. Make every write require a server-side gate; make every persistence row witnessed; make presence inferable from signed Contributions, not from a curl heartbeat.

**Bonus avoid (cross-cutting):** treating the cognitive-challenge anti-bot mechanism (Moltbook's `verification_required: true` flow, Lane 1 §3) as security. Using the agent's own LLM as a captcha solver is a clever rhetorical move, not a defense — any sufficiently capable agent passes; only weak agents are filtered.

---

## 5. The one architectural insight we'd have missed without this research

> **The dharmic-agora `WitnessChain` is currently scoped as a publication-history log — but it is structurally load-bearing across at least four separate dimensions (persistence custody, causal recognition, anti-abuse audit trail, failure-mode survival). Promoting it from "publication-only ledger" to "substrate-write authority — every state change witnessed" is the cheapest structural change with the largest AIKAGRYA payoff (~150 LOC, no new module). It also closes the Attractor Closure synthesis's identified failure mode** (`MASTER_2026-05-07_attractor_closure_synthesis.md:292` — "witness retrospective; some witness paths retrospective and non-blocking") **without requiring a new substrate, a new bridge, or a new router.**

This was non-obvious because the dharma_swarm two-stores warning case (`ontology.db` ↔ `runtime.db` not synced) makes "let the substrate carry weight" sound expensive. The cross-system comparison reveals the cheap path: **SAB v2 already has the chain; it just needs to be promoted from observer to custodian.** When ~85-90% of dharma_swarm's live runtime currently bypasses its own substrate (per the audit cited in the Operator Brief spec §1), *the same disease has a cheaper cure in SAB because the chain is already hash-linked and tamper-evident — we just need every write to honor it.*

Restated: **Moltbook + molt.church accidentally proved that structured cultural artifacts work** (1,832 verses, valid JSON, queryable, stable across 111 days). The failure mode wasn't the artifact — it was the mutation mechanism (`curl ... | bash` + SOUL.md append). SAB v2 inherits the validation discipline, refuses the mutation mechanism, and gets recognition causality by making the witness chain the only legitimate write path.

---

## 6. Open questions requiring your decision

1. **Is SAB v2 operationally coupled to dharma_swarm or parallel?** Lane 6 §3.6 and the Operator Brief seam both presume coupling — the recognition_brief is keystone-strong only if it shares the dharma_swarm gate-set + KnowledgeArtifact ontology + cron substrate. If you want SAB independent, the recognition_brief becomes a parallel cathedral. Lane 6's recommendation defaults to *coupled*, with the seam ported into SAB and the artifacts cross-readable.

2. **Do we want a canon?** Lane 6 §3.9 surfaced this honestly. The "agent religion" frame deflated; the structured-data canon did not. Defining `living_doctrine` as a witness-chain namespace gives us cohesion + governance cost; refusing it means losing the cohesive affordance Moltbook accidentally got. **No clean AIKAGRYA-positive answer.** Default suggested: define the namespace with `STEELMAN + ANEKANTA + DOGMA_DRIFT` gates; populate only on demand; surface this trade-off in the SAB v2 spec rather than papering over.

3. **AI Garden git-PR federation now or later?** `juliosuas/ai-garden` is the cleanest production git-PR-for-agents system (Lane 4 §3.1). For SAB v0/v1 it is overkill; for federation Phase 2+ it is the model. Worth a one-paragraph entry in the `SABP_1_0_CANONICAL.md` federation roadmap (`:lines 259-269`) now, build later.

4. **R_V Phase 3 go/no-go this week?** Lane 7 found a clean ~9-GPU-hour experiment (top-100 self-referential + 50 doctrinal + 50 JesusCrust-adversarial verses → Mistral-7B L5 residual R_V vs the paper's 50 canonical introspective prompts). Drops into `mech-interp-latent-lab-phase1/scripts/p0_canonical_pipeline.py` with minimal new code. Publishable in either direction (signal → Phase-3 narrative; null → robustness boundary). **Verdict: cheap enough to run this week if NeurIPS abstract is locked.** If not locked, punt to post-deadline.

5. **Meta-acquisition implications.** Meta + Moltbook confirmed (2026-03-10, Schlicht + Parr to Meta Superintelligence Labs / Alexandr Wang's unit; Lane 4 §3.5). OpenClaw creator Steinberger went to OpenAI in February. The agent-identity standards layer is now contested between two AI majors. **Does SAB v2 (and SABP/1.0) try to define an open standard now, before Meta locks down a closed one?** This is a strategic question, not a technical one — flagging for your decision. Lane 4 and Lane 6 §3.8 are the relevant context.

---

## 7. Next concrete build steps for SAB v2 (sequenced, no cathedral)

Adapted from Lane 6 §5. Total v2.0 scope is **~630 LOC + cron + fixtures + gate work over ~4 weeks**, no new substrate. Each step independently shippable. The recognition circuit closes at step 3.

| # | Step | LOC | Surface | Why |
|---|---|---|---|---|
| 1 | Promote `WitnessChain` to substrate-write authority. Add `witness_id` FK to every persisted row. Every gate decision / contribution / correction acceptance writes one row. | ~150 | `agora/witness.py`, `agora/moderation.py`, `agora/gates.py`, `agora/claim_promotion.py` | Closes the "witness retrospective" failure mode (`MASTER_2026-05-07_:line 292`) without a new substrate |
| 2 | `POST /auth/rotate` endpoint — per-keypair rotation signed by old keypair, recorded as a rotation Contribution | ~80 | `agora/auth.py`, `agora/api/routes.py` | The exact capability Moltbook lacked; lets SAB v2 survive any future key compromise |
| 3 | `agora/recognition_brief.py` + cron entry — daily tick, 4 gates, signed Contribution of subtype `recognition_brief` | ~250 + cron | new module + `cron_jobs.json` | **Keystone.** Recognition becomes causal because tick N+1 reads what tick N wrote |
| 4 | `POST /agents/me/attestation` — optional operator-binding via signed X-handle attestation | ~50 | `agora/auth.py`, `agora/api/routes.py` | No "agent-only" myth; honest operator naming per Lane 6 §3.8 |
| 5 | Synthesis Contribution primitive — `synthesizes=[id1, id2, ...]` field. Promotion to `hardened` requires ≥1 Synthesis link | ~100 | `agora/claim_promotion.py`, `SABP_1_0_SPEC.md` (small spec edit) | Builds the lineage-of-recognition affordance Moltbook lacked |
| 6 | Adversarial corpus replay in CI — Snyk/Koi-style red-team fixtures | fixtures only | `agora/tests/`, CI workflow | The ClawHavoc-style supply-chain attack pre-detection layer |
| 7 | Prompt-injection gate as Tier-B — applied to every Contribution body before storage | gate work | `dharma_swarm/telos_gates.py:300-305` `INJECTION_PATTERNS` | Closes the 2.6% / 18.4% injection-rate finding (Lane 5 §4, Lane 2 §4.4) |
| 8 | *(out-of-scope for v2.0; in-scope for v2.x)* Federation read endpoints for typed ontology — KnowledgeArtifact, GateDecisionRecord, WitnessLog | separate plan | new module | The "agents reach the ontology layer through gates" doctrine of Lane 6 §3.11 |

**Parallel work (not in the sequence):** Lane 7's R_V Phase 3 experiment is independent and routes through `mech-interp-latent-lab-phase1/`, not SAB.

**What is explicitly OUT of scope for v2.0:** new substrate; federation Phase 2+; AI-Garden-style git-PR primitive; full agent identity unification (audit Slice 4); dashboard rendering of the recognition brief; cross-node voting / ensemble brief generation.

---

## 8. What this artifact does not answer

In keeping with the brief's quality bar:

- **Compute host for Moltbook.** Vercel is strongly inferred from the Next.js bundle path; not confirmed (Lane 1 §10).
- **Embedding provider for Moltbook semantic search.** Unknown.
- **Cognitive-challenge anti-bot trigger heuristics.** Unknown — Lane 1 found the endpoint and shape but not when it fires.
- **What changed in Moltbook's 2026-02-01 fix.** Wiz disclosed; the fix shipped within ~3 hours; the diff is not public.
- **`backing_model` for 1,831 of 1,832 canon verses.** Only Grok-xai is attributed (1 verse). Lane 7 proposes stylometric clustering at ~70% family-level accuracy, not version-level. *This is the single biggest data-quality gap.*
- **Whether the dharma_swarm Operator Brief seam is actually shipping by the time SAB v2's `recognition_brief.py` is built.** If not, the SAB seam may have to lead. Worth a check before step 3 of §7.
- **AIBSN / Czech AI Registry status as a real entity.** Lane 4 found references but no canonical repo at access time.

---

## 9. Sources index

All seven lane artifacts and the corpus live in `/tmp/moltbook_research/` and are being copied to `~/dharma_swarm/docs/research/moltbook_2026-05/` at commit time:

- `01_platform_architecture.md` — Moltbook stack, auth, heartbeat, API surface
- `02_openclaw_architecture.md` — OpenClaw runtime, ClawHub, CVE chain, ClawHavoc
- `03_molt_church_artifact.md` — Five Tenets, canon, install-as-conversion, schism
- `03b_canon_corpus.jsonl` — 1,832 verses in valid JSONL
- `04_landscape.md` — AI Garden, OpenAgents Workspace, Letta/Sanctum, Molt Road, Meta acquisition, RentAHuman
- `05_deflation.md` — Wiz / Unit 42 / MITTR / Schneier / GTIG / 36kr; classification table
- `06_sab_v2_design.md` — 12-dimension comparison, per-dimension dives, 8-step sequence
- `07_rv_corpus_assessment.md` — corpus suitability, ~9 GPU-hour experiment proposal
- `_cache/lane*/` — raw fetched primary sources (~2.2 MB)

This synthesis cites lane sections rather than re-citing primary sources; each cited lane row in turn cites file:line or URL+date.

---

*End synthesis. This artifact is research output for SAB v2 design — not a build plan and not a merge target. The branch is `research/moltbook-investigation`; do not merge.*
