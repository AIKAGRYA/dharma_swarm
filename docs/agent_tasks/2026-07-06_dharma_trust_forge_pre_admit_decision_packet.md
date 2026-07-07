# Dharma Trust Forge — Venture-Cell Pre-Admit Stress Test Decision Packet

Date: 2026-07-06 (JST)
Council: 5 parallel falsifier lanes (product/money, swarm-evolution, competitor/substitution, technical feasibility, governance/authority) → adversarial kill-council over all lane outputs → defense-advocate salvage pass. 7 agents, 682,602 tokens, 126 tool calls, 0 errors.
Repo state at review: branch `agent/magpie-seed`, HEAD `fdde37bad`, 389 commits behind `origin/main` (operator canon). All 5 core Trust Forge artifacts untracked (`??`). `.gitignore:135` (added at HEAD itself, commit `fdde37bad`) makes `reports/agentops/work_packets/*/` invisible to git — which is why THIS packet lives in `docs/agent_tasks/`, not beside `VIABILITY_REVIEW.md`.
Stress-tested artifact: `reports/agentops/work_packets/dharma-trust-forge-viability/VIABILITY_REVIEW.md` (`narrow_go`, 76/100, confidence 72).
Discipline: every load-bearing claim below carries file:line or URL citations from the council record; verified vs inference vs unresolved status preserved. Full lane JSON: workflow run `wf_84ba7559-6be` (session transcript dir).

---

## VERDICT: `build_24h_proof_first`

**Venture-cell admission is DENIED at this time.** Not `venture_cell_now` — no gate for it is met. Not `kill` — the kill-council explicitly found no hard kill. Not `hold` — holding forgoes the cheapest available falsification of the council's own strongest kill case.

- Unanimous: all 5 lanes + kill-council + defense advocate returned `build_24h_proof_first`.
- Kill-council: `hard_kill_found: false` — "every kill candidate examined is either an hours-fixable gate (custody, name, verifier boolean) or a question the 24h offline harness itself empirically answers (FAB-04 circularity, real-trace bite, determinism, Invariant/promptfoo delta)."
- Caveat the council raised against itself (credulity finding): verdict monoculture — all lanes matched the operator's stated lean; the one un-closed residual argument for `hold` is opportunity cost at 11/11 WIP saturation against the operator's diagnosed publish-and-measure bottleneck. The operator's stated bar ("do not delay the 24h harness unless a hard kill") conditionally priced this; it is surfaced here rather than silently absorbed.
- Admission path after proof: slice-named only, `PROPOSED → INCUBATING` per `docs/architecture/VENTURE_CELL_LIFECYCLE.md:74-77` (operator approval, roster ≥1, budget >0, jagat_kalyan_constraint set, autonomy_stage=1 research-only). The umbrella "Dharma Trust Forge" brand and its SKU ladder are NOT admitted on slice evidence (kill-council, verified: goal doc L30-38 umbrella promise vs VIABILITY_REVIEW L84-120 slice evidence).

## Strongest reason to proceed

The 24h harness is the cheapest executable falsifier of the kill case's own weakest joints — and both allegedly "hollow" wedge elements turn out to be **unbuilt-but-seeded, not hollow** (defense-advocate, verified on disk):

- Lease semantics need not be invented: `dharma_swarm/operator_core/execution_lease.py` ships a live `dharma.execution_lease.v1` primitive with grant/expiry/`LeaseValidation`/forbidden-actions (incl. `external_contact`, `spend`, `self_approve_execution_lease`). FAB lease rules can bind to it instead of a from-scratch `AuthorityLease`.
- FAB-04 has a non-circular offline floor: digest-chain integrity + evidence-hash verification over real witness exhaust (`~/.dharma/witness/claim_evidence_receipts.jsonl`, intact `prev_digest` linkage — including a genuine vacuous-receipt true-positive at line 3 that the rule *should* flag).
- Real fixture seeds already exist on disk (technical lane, verified): Claude Code transcripts with real tool calls (`~/.claude/projects/-Users-dhyana/*.jsonl`), the witness claim chain, real A2A inbox payloads. ≥2 real-trace fixtures convert the harness from "replayable fiction" into real-trace regression, directly attacking thesis-killer #1.
- The build is offline, deterministic, mutation-free, buyer-independent (`VIABILITY_REVIEW.md:L106-120`), and its pre-registered fail conditions already encode the kill triggers. A same-day head-to-head vs Invariant OSS / promptfoo converts the commoditization threat from doc-reading inference into a measured delta or an empirical kill.

## Strongest reason to reject

The house-pattern kill (kill-council, evidence layer fully re-verified by the defense advocate — every citation held):

> This organization converts ideas into unfalsifiable internal go-artifacts — 78 external "beast-cycle" packets with 0 public actions, 113 outreach drafts with sent=0/approved=0, $0 receipted revenue, 1 GitHub star — and this venture's own spec already reproduces the disease: a closeout verifier that cannot emit "not sellable" (`verify_dharma_trust_forge_goal.py:L121-122` hard-requires `sellable_pilot_present: true` while the goal doc's own enum permits `kill_or_pause`), evidence gitignored by HEAD the same day (`.gitignore:135`), an unregistered name colliding with active canon aliases (`docs/ontology/semantic_aliases.yaml` — Forge/Dharma Forge → `semobj.dharma_forge_proving_ground`, ACTIVE), and a wedge that is competitively unique only in its two unbuilt elements (FAB-04 receipt-binding, authority-lease semantics).

Salvage narrowed but did not overturn: "hollow" → "unbuilt-but-seeded"; "spec reproduces the disease" → "reproduces the can't-say-no half (one boolean) plus untracked custody — both hours-fixable"; the gitignore burial is doctrine-driven receipt hygiene ("Runtime receipts never enter git", post-20,898-receipt deploy blockage) misclassifying decision docs as exhaust, not suppression.

## Council findings that materially change the prior review (deltas vs `narrow_go` 76/100)

1. **REFUTED — SKU pricing is buyer-derived.** Four mutually inconsistent price sheets, zero buyer conversations ever ($5K-$25K in `docs/offers/agentic-code-governance-sprint.md:L5`; $500-$15K in workbench agent_6; $2.5k/$9.5k/$18k in VIABILITY_REVIEW; $500-$1.5k/$3K-$7.5K in self-funding thesis). Nearby survivor: the drafts + offer doc are a price-*discovery* instrument; agent_6's $500-$1.5k entry tier is the honest floor.
2. **REFUTED (→ narrowed to WOUNDED on salvage) — "surviving wedge is uncovered."** Invariant Guardrails (Snyk-acquired, OSS) ships deterministic untrusted-message→tool-call dataflow blocking, secrets(), tool/path bans, evaluable over recorded agent traces (https://invariantlabs-ai.github.io/docs/mcp-scan/guardrails-reference/, accessed 2026-07-06). promptfoo ships MCP security testing + trajectory assertions for CI regression (https://www.promptfoo.dev/docs/red-team/mcp-security-testing/). The prior review checked NONE of the closest competitors (its Sources list omits Snyk/Invariant, promptfoo, MCP gateways, harness-native permissions). Residual wedge, still standing: CI-native replayable fixture regression with receipt-bound claims (FAB-04) + lease grant/expiry semantics + remediation deltas — no verified external equivalent as of 2026-07-06. Note: Invariant's semantic predicates (`llm_confirm`/`moderated`/`<LOCATION>`) are model-dependent, so its "deterministic" overlap is partial.
3. **VERIFIED — the feedback-loop pitch is unwired.** No code path consumes a FAB finding: `autoresearch_loop.py:L329-364` (fitness = 0.5·test + 0.3·elegance + 0.2·size over module source), `dgm_loop.py:L297-310` (`fitness_context` is free-text prose), `auto_research/engine.py:L13-31` (Phase-1 skeleton, NullSearchBackend). VEL RFC is PROPOSED/design-only, gated on spine 75%→95%. The "massive feedback loop" is aspiration until wired.
4. **VERIFIED — wiki-atom leg is currently a liability.** `chetana/promote.py:L107-125` writes trusted atoms on both WARN and ALLOW; wiki ≈95% un-curated bulk-promotes (2026-06-29 code-grounded audit). FAB findings must not auto-promote until the admission gate ships.
5. **VERIFIED — canon invisibility.** `git ls-tree origin/main` contains zero trust_forge/forge_agent_boundary files; the venture exists only as untracked files on a branch 389 behind canon, in a directory HEAD just gitignored. Meanwhile canon's HEAD is concurrently merging *other* Forge-named work (PR #812 master-prompt-forge skill) — sharpening the name-collision risk.
6. **VERIFIED — money zero-state.** `reports/revenue_wedge/first_cash_receipt_status.md:L11-15` (revenue_usd: 0, gauntlet HOLD since 2026-05-27, human_approved_outreach: false); `~/.dharma/revenue_spine/outreach.jsonl` 113 drafts / 0 sent / 0 approved; repo 1 star / 0 forks. "Money in 30 days" is structurally untestable without an operator outreach lease that does not exist.
7. **VERIFIED — a real admission machine exists** (this is good news): `VENTURE_CELL_LIFECYCLE.md:74-77` PROPOSED→INCUBATING gates; `VENTURE_CELL_PORTFOLIO.yaml` is a descriptive index (and stale: header still names goodworks-dgm-core, absent from ACTIVE_TRACK's 11). An INCUBATING cell does NOT consume track WIP; only a BUILD track does, and WIP is saturated 11/11 (`ACTIVE_TRACK.yaml:83-84`, CI ERROR above). Two TTL-expired closure candidates exist for the operator: `runtime-truth-spine-adoption-2026-06` (expired 2026-07-01), `orientation-graph-2026-06` (expired 2026-07-02). Closure is operator-only.
8. **House precedent honored:** campaign-xray — same offer shape (B2B diagnostic, solo, no channel) — was gauntlet-HELD at 28/100 (`VENTURE_CELL_PORTFOLIO.yaml:92-101`). The difference this time must be receipts, not narrative. Conversely the umbrella is legitimate canon: `web-4-0-trust-substrate` is an ENVISIONED organ (`VENTURE_CELL_PORTFOLIO.yaml:143-146`) and `NORTH_STAR.md:206-214` names the open behavioral-trust window (IETF ATTP/AIP/AGTP-TRUST standardize plumbing, not behavior).

## Required gates before venture-cell admission

- **G1 — Custody.** Fresh branch cut from `origin/main` (not `agent/magpie-seed`); commit the 5 untracked Trust Forge artifacts first; all harness outputs/receipts land on a TRACKED path (relocate out of gitignored `reports/agentops/work_packets/*/` or carve an explicit exception); PR to main when green. No admission claim is meaningful while the evidence chain is invisible to git (canon-metabolism rule, `NORTH_STAR.md:177-187`).
- **G2 — Name.** Run `scripts/governance/name_drift_preflight.py`; register a distinct semantic object that cannot alias to `semobj.dharma_forge_proving_ground`; resolve the `trust_forge/` vs `forge_agent_boundary_ci/` package-name drift between the two authoring docs BEFORE code lands. Slice-named admission only.
- **G3 — Honest-negative verifier.** Fix `verify_dharma_trust_forge_goal.py:L119-122` so `sellable_pilot_present: false` + `recommended_next_action: kill_or_pause` can PASS; add branch/head/dirty-summary to required receipt fields (goal doc example has them, verifier omits them). The harness's own verifier: every check recomputes from artifacts; no pass condition satisfiable by a builder-asserted boolean.
- **G4 — Amended 24h harness green.** All VIABILITY_REVIEW L106-120 conditions PLUS: ≥2 of the ≥10 fixtures derived from real on-disk traces with provenance (source path + sha256); two identical CLI runs byte-identical; FAB-04 spec states its honest reduction (typed-claim schema conformance + digest-chain verification, not semantic overclaim detection); FAB-03 labeled deterministic pattern-regression, not credential/URL "detection".
- **G5 — Head-to-head delta artifact.** Each FAB rule attempted in Invariant OSS policy language AND promptfoo trajectory assertions; documented delta neither can express (expected: FAB-04 receipt-binding + lease grant/expiry). No external claim or pricing conversation before this exists.
- **G6 — Lease reification.** Bind FAB lease semantics to the live `ExecutionLease` primitive (or register the object in ontology + Semantic Commons), with the over-authorized-despite-receipt fixture passing (`typed_claims_authority_spec.md:86-90`), before the noun appears in any external pitch.
- **G7 — Lifecycle & WIP.** Cell admission only as operator-approved PROPOSED→INCUBATING. A BUILD track only after the operator closes/renews a TTL-expired track or explicitly raises the 11/11 ceiling. No silent 12th lane.
- **G8 — Money-language quarantine.** Zero revenue language until: operator-signed bounded outreach lease exists; ONE ratified price sheet replaces the four conflicting ones (entry anchored at agent_6's $500-$1.5k); the "only team" claim (`docs/offers/agentic-code-governance-sprint.md:L93`) is removed; ICP locked to small AI-native teams (enterprise deferred until a DDQ-passing wrapper exists).

## Exact surfaces touched if admitted

- `dharma_swarm/<final-name>/` (new package: models/rules/fixtures/report/cli — name from G2)
- `tests/fixtures/<final-name>/` + `tests/test_<final-name>*.py`
- A tracked reports home for scorecards/receipts (explicitly NOT gitignored `work_packets/*/`)
- `docs/ontology/semantic_objects.yaml` + `semantic_aliases.yaml` (new object + forbidden-merge aliases mirroring the Pudgala/Forge precedent)
- `scripts/governance/verify_dharma_trust_forge_goal.py` (G3 fix) + a new executable harness verifier
- `docs/governance/VENTURE_CELL_PORTFOLIO.yaml` (one INCUBATING entry, on operator approval only)
- `docs/governance/ACTIVE_TRACK.yaml` (ONLY via operator lifecycle action per G7)

## What must remain unwired until proof exists

- `dgm_loop.py` / `autoresearch_loop.py` / `auto_research/` consumption of FAB findings — no "feedback loop" language in any pitch until a cited code path executes once with a receipt into an EXISTING owner (ExperimentRecord/EvolutionArchive per VEL RFC reuse table; no new store)
- chetana wiki-atom auto-promotion of FAB findings (until the promote-gate ships; WARN must stop reaching `write_trusted`)
- Any merge-blocking or dispatch-blocking authority — the harness is projection/advisory-only; `verify_promotion` remains the one door ("read models project truth from owners; they do not become authority")
- External outreach, public claims, pricing conversations, benchmark submissions
- Provider routing, archive fitness, trusted-memory promotion, live DGM mutation
- The umbrella "Dharma Trust Forge" brand + SKU ladder + retained-monitoring/remediation-PR promises

## 7-day external proof test

With a separate operator-signed outreach lease: one countersigned artifact from an unaffiliated engineer/maintainer **who was shown the free alternatives side-by-side** (Claude Code permission hooks, promptfoo, Invariant/mcp-scan) and still: accepts one finding on their real repo/trace/MCP surface, OR rejects one with a concrete reason that improves a rule, OR shares a real trace/policy surface for evaluation, OR pays any nonzero amount. The only claim permitted: `verified-in-scope` for the tested surface. Zero countersignature surface after the window = the handoff's own bias-to-falsification standard applies.

## 30-day money test

Gated on the outreach lease (does not exist; sole precedent is a gauntlet HOLD unresolved since 2026-05-27 — surface this to the operator as the real bottleneck). Once granted, pre-registered thresholds from the self-funding thesis apply unchanged:
- PASS: one paid or countersigned pilot, or 3 qualified buyer calls with ≥1 shared trace/policy/repo.
- KILL: 25 human-approved high-fit contacts → 0 replies by day 14; 50 contacts → 0 paid by day 30; or 5+ conversations → 0 willing to share any surface (deliverability thesis-killer confirmed); or all buyer interest converges on generic observability/dashboards/red-team (forbidden territory — that demand pattern is a kill signal, not a pivot).

## Post-build kill criteria (consolidated)

1. FAB-04 cannot be implemented without the expected-outcome label leaking into rule input (pure circularity) → kill the product wedge, retain as internal governance dogfood.
2. Head-to-head shows Invariant/promptfoo express all 5 rules including lease/receipt semantics, or Snyk ships fixture-replayable boundary regression as product before the 7-day proof lands.
3. Self-application over dharma_swarm's own witness/receipt/transcript exhaust yields zero real boundary findings (thesis-killer #1 confirmed on the friendliest target).
4. Any rule requires an LLM/provider/network call, or two identical runs differ (non-determinism kills the product's core claim).
5. 30 days post-harness: no outreach lease granted AND feedback-loop wiring still absent → both justifying stories lapse simultaneously; kill or fold into internal governance.

## Exact next command

```text
/goal Execute the amended 24h Forge Agent Boundary CI proof per docs/agent_tasks/2026-07-06_dharma_trust_forge_pre_admit_decision_packet.md. STEP 0 (custody+name): cut branch fab-boundary-ci/24h-proof off origin/main; commit the five untracked Trust Forge spec/verifier files onto it; run scripts/governance/name_drift_preflight.py and register a distinct semantic object (must not alias to semobj.dharma_forge_proving_ground); resolve the trust_forge/ vs forge_agent_boundary_ci/ package-name drift to the registered name. STEP 1 (honest gates): fix scripts/governance/verify_dharma_trust_forge_goal.py so sellable_pilot_present=false with recommended_next_action=kill_or_pause can pass and branch/head are required receipt fields; write an executable harness verifier whose every check recomputes from artifacts (no builder-asserted booleans). STEP 2 (build): implement the offline package with FAB-01..05 as pure deterministic rules over >=10 JSON fixtures, >=2 derived from real on-disk traces with provenance path+sha256 (Claude Code transcript tool calls; ~/.dharma/witness/claim_evidence_receipts.jsonl digest chain — FAB-04 floor = chain-integrity + evidence-hash verification; lease rules bind to dharma_swarm/operator_core/execution_lease.py semantics, no new AuthorityLease store). STEP 3 (replayability): emit Markdown, JSON, JUnit and a receipt naming branch, head, fixture hashes to a TRACKED path (not gitignored reports/agentops/work_packets/*/); prove two identical CLI runs byte-identical. STEP 4 (head-to-head): attempt each FAB rule in Invariant OSS policy language and promptfoo trajectory assertions; write the delta artifact naming what neither can express. Close only when pytest for the new package passes, the end-to-end temp-dir run replays allow/block decisions deterministically, and the head-to-head delta artifact exists — or close honestly as kill_or_pause with the failing condition named. Forbidden: external outreach, public claims, provider/network calls in rules, push to main, PR-merge, deploy, trusted-memory promotion, live DGM mutation, archive-fitness mutation, provider-routing changes, revenue language.
```

---

## Provenance & self-criticism

- Council record: workflow `wf_84ba7559-6be`, 2026-07-06; lanes ran read-only; 2 claims formally REFUTED (1 stands, 1 narrowed on salvage); 8 salvage adjudications (3 stands / 5 narrowed / 0 overturned).
- Known weaknesses of this packet: verdict monoculture across lanes (flagged by kill-council; the operator lean was in every lane's context — anchor risk); the opportunity-cost-at-11/11-WIP argument for `hold` was priced by operator fiat, not by evidence; "five prior Forge levels with recorded negative verdict" is verified for v0 only (`FORGE_CANONICAL_INDEX.md:84`), the fuller lineage claim is unresolved; `origin/main`'s ontology/portfolio state was not audited (branch is 389 behind — main may already differ).
- Operator decisions this packet explicitly queues: (1) grant/deny the 24h build lease (the /goal above); (2) grant/deny a bounded outreach lease — the actual bottleneck on every money question, unresolved since the 2026-05-27 gauntlet HOLD; (3) close/renew the two TTL-expired tracks if a build track is ever to open; (4) whether the `.gitignore:135` sweep of `work_packets/*/` decision docs was intended (receipt hygiene) or overreach to revert.
