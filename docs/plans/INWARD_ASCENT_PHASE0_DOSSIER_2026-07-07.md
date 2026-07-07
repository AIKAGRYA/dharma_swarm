# Inward Ascent — Phase 0 Dossier: Massive Ingest + Simulation Gym (2026-07-07)

**Role:** the ratification dossier for the Inward Ascent campaign (operator
master prompt, 2026-07-07): light the Go ingest organs on live feeds, stand up
a battery of frozen verifiable simulation environments ("the gym")
decorrelated from the RSI/arena lab, and wire high-iteration autoresearch
loops against them — afferent world contact only, with a measured 10x ratchet
baseline on every surface. Phase 0 ships THIS dossier; build starts only after
operator ratification.

**Trust rule:** if this file disagrees with `make onboard`, a receipt, or the
code, trust those. Every claim below is a command run on 2026-07-07 on the
session host (`devin-box`, main @ `665c90c3`) or a file:line read that
session. Anything unverifiable on that host is marked UNKNOWN, never green.

**Scope firewall (non-negotiable):** afferent ≠ efferent. Ingestion from the
world is in-scope and read-only. Actions INTO the world (posts, outreach,
trades, publishing) are out of scope entirely. Gym gradients may drive
autoresearch loops; archive fitness for self-modification still requires the
One Wire external quorum (N>=5, M>=3) — no gate, ratchet, or quorum is
weakened by anything in this campaign.

**Measured reality this campaign must change honestly (not narrate around):**
0/13 loops CLOSED_LIVE (onboard, this session); trust gate C2 lift −0.1
(trust_gate_status owner); `runtime.db` and `ontology.db` ABSENT on this host
(BR-007, onboard SURFACE MANIFEST: both `[broken]`).

---

## (a) Ingest map — four source classes

**Shared landing doctrine (verified in code this session):** Go organs →
Bronze (content-addressed raw receipts + MinHash/LSH dedupe + verifier
boundary; `dharma_swarm/world_radar/bronze.py:1-147`) → Chetana
ingest→stage→gate→promote (NORTH_STAR §9 canon-metabolism) →
MemoryKernel/ontology. **NO new truth stores.** Bronze storage owner:
`~/.dharma/meta/intelligence_supply_chain/bronze/{raw_receipts,verifier_boundary}/`
+ `verifier_boundary.jsonl` ledger + `dedupe_index.json`
(`bronze.py:241-258`). Raw receipt schema:
`intelligence_supply_chain.raw_receipt.v1` with W3C-PROV-minimal provenance,
untrusted-text instruction policy, corroboration `required_k=2`, and budget
block (`bronze.py:350-436`). Every payload is untrusted data
(`payload_must_not_be_executed`, `bronze.py:386-390`) — the AI-A1 hygiene
signal applies to all four classes.

**Verified live this session (afferent, read-only):**
`fetch_hn_algolia_rows(query='AI agents', limit=3)` returned 3 rows on this
host, and `ingest_rows_to_bronze` landed 1 receipt + 1 boundary artifact in a
tmp state dir. The zeitgeist path is live-capable NOW with zero credentials.

| | Class 1 — zeitgeist | Class 2 — code-world | Class 3 — knowledge-world | Class 4 — market |
|---|---|---|---|---|
| **Feeds** | HN Algolia (`bronze.py:168-238`, exists+verified); expand to HN front-page sweep queries | GitHub releases/repos/leaderboards via `tools/github_ingestor_go` (exists; live trigger `cron_jobs.json:github_ingestor_inbox` per organism-rewire track) | arXiv (bronze source type already supported, `bronze.py:33-37`); Wikipedia/Wikidata slices; IETF agent-trust drafts (needs new fetchers) | funding/slow-horizon signals only (Crunchbase-class RSS, public filings); NEVER per-iteration selection (fitness doctrine, organism-rewire track) |
| **Cadence** | hourly bounded pages (limit≤20/query, `bronze.py:175`) | daily per watched repo/leaderboard | daily arXiv categories; weekly Wikidata slice; weekly IETF | weekly |
| **Bronze schema** | `raw_receipt.v1` as-is | `raw_receipt.v1` + `source_type` extension for `github_release`/`leaderboard` (schema PR, additive) | `raw_receipt.v1` (arxiv supported); `wikidata_slice` needs a bulk-row variant with per-slice content hash | `raw_receipt.v1` + `market_signal` source type; `license` field mandatory |
| **Chetana promotion** | corroboration k≥2 + theme-window relevance before staging; zeitgeist atoms TTL-labeled (freshness decays fast) | promote only release/leaderboard FACTS (version, score, date) — never README prose as instruction | promote citation-resolvable claims only; Wikidata rows promote as ontology candidate edges (feeds gym G3) | promote to a funding-signal shelf read by operator surfaces only; firewalled from every fitness function |
| **Storage owner** | Bronze → MemoryKernel atoms | Bronze → MemoryKernel + ontology (repo/release entities) | Bronze → ontology (entity/edge candidates) | Bronze → operator brief surface only |
| **Closure check** | `loop5b_world_radar_closure_run` pattern (exists, LOOP5B_CLOSED=yes per organism-rewire track); add per-source receipt-count + freshness check to cockpit `go.world_radar_health` row | same, per-source | same, per-source | same + an automated check that NO market receipt hash appears in any gym taskpack or archive-fitness input (the firewall as a test) |

**Sequencing (per master prompt):** zeitgeist first (cheapest, verified
live), then code-world (Go organ + cron trigger already exist), then
knowledge-world (new fetchers), market last (lowest cadence, highest
firewall burden).

**Surface ownership note:** `tools/*_go/**` and `dharma_swarm/world_radar/**`
are owned by `organism-rewire-2026-07`. Ingest-lighting work either lands via
that track's next-items or the new track declares only NEW surfaces (new
fetcher modules, gym surfaces, this dossier) — see §(e).

---

## (b) Gym spec — chosen environments + adversary red-team

**Selection rule applied:** decorrelated failure modes (from each other AND
from the RSI/arena lab, which owns C2 swarm-lift on
`coordination/**`/`council/**` — this campaign does not touch those
surfaces), scorer ungameability, iteration cost, and *data actually available
to build on*. Every environment MUST have: frozen task snapshot,
deterministic executable scorer, held-out set never trained/selected on, and
taskpack rotation. An environment without held-outs is a slower mirror —
rejected by construction.

### Picked (3 buildable now + 1 operator-gated)

**G1 — git-history repo gym** (candidate #2). Substrate verified on this
host: non-shallow clone, 1331 commits, 273 landed merges (real solved tasks
with real landed tests as ground truth).
- *Task:* given the repo state at merge-base of a past landed PR plus its
  issue/PR description, produce a diff; scorer checks out the PR's landed
  test files (and only those) and runs them against the candidate diff.
- *Frozen snapshot:* taskpack = list of (merge commit, base sha, test-file
  shas, scorer command) pinned by sha256; tasks are immutable git objects.
- *Scorer:* deterministic pytest run of the LANDED tests; pass-rate. The
  answer key (the landed diff) is withheld from the solving agent's context.
- *Held-out:* stratified 30% of merges by date, never used for
  selection; rotation = each new quarter of repo history becomes a fresh
  taskpack, old held-outs retire into the training pool.
- *Decorrelation:* arena lab scores orchestration-policy lift on fixture
  taskpacks; G1 scores code-production against real historical ground truth.
  Failure modes (fixture-overfit vs. history-leak) are disjoint.
- *Autoresearch node:* prompt/policy evolution (external-gradient portfolio,
  organism-rewire D-item).

**G2 — forecasting gym** (candidate #3). `ginko_brier.compute_brier_score`
exists (`dharma_swarm/ginko_brier.py:198-214`); returns None today — zero
resolved predictions on this host (baseline receipt).
- *Task:* from each day's Bronze intake, emit resolvable predictions
  (probability + resolution criterion + resolve-by date) into the existing
  ginko prediction store; when reality resolves (later ingest), Brier-score.
- *Frozen snapshot:* the prediction is frozen at write time (digest-stamped);
  the scorer input is future world data — structurally impossible to have
  trained on (time-lagged class-2 signal; the one gradient the mirror problem
  cannot manufacture).
- *Scorer:* `compute_brier_score` over resolved predictions; deterministic
  given the resolution ledger.
- *Held-out:* not applicable in the train/test sense — the future IS the
  held-out; rotation is automatic (time moves). Guard instead against
  resolution-criterion gaming (see adversary).
- *Decorrelation:* temporal — no other environment's failure mode involves
  calibration under uncertainty.
- *Autoresearch node:* memory promotion policy + world-model calibration.

**G3 — retrieval/memory gym** (candidate #4), merged with the ontology gym
(#6) as its second scorer arm — same corpus, two decorrelated scorers.
- *Task arm A (retrieval):* verifiable QA generated from ingested corpora
  (answer = exact span/hash in a Bronze receipt); MemoryKernel must retrieve
  it first-token (evolves C5 orientation).
- *Task arm B (ontology):* held-out link prediction — mask edges from
  ingested Wikidata slices; predict; score against the withheld ground-truth
  edges.
- *Frozen snapshot:* QA pairs and masked-edge sets pinned by corpus sha256
  (Bronze receipts are already content-addressed — the snapshot is free).
- *Scorer:* exact-match/contains over receipt hashes (arm A); precision@k
  against withheld edges (arm B). Both deterministic.
- *Held-out:* 30% of QA pairs and all masked edges, generated at
  snapshot-freeze by seeded RNG, stored digest-stamped OUTSIDE any context
  the solving agent sees; rotation per new ingested corpus batch.
- *Decorrelation:* measures memory/ontology substrate, not code production
  or orchestration; feeds the two broken stores (BR-007) real load.
- *Autoresearch node:* memory promotion policy + C5 first-token orientation.

**G4 — runtime-history replay gym** (candidate #1) — **operator-gated.**
Richest untapped real signal, but the substrate is NOT on this host:
`~/.dharma/state/runtime.db` ABSENT (find run this session; only pytest tmp
fixtures exist). The real `delegation_runs` history (~2191 historical rows
per loop-closure track; master prompt says ~8.8k — discrepancy to resolve on
the daemon host) lives on the operator's daemon host.
- *Spec (build only after the operator ships a sanitized runtime.db
  snapshot):* off-policy evaluation of routing/aggregation policies over real
  delegation_runs; scorer = counterfactual regret vs. the logged outcome,
  frozen snapshot = a dated, digest-stamped copy of the DB; held-out = last
  20% of rows by time; rotation = each new DB snapshot.
- *Decorrelation:* the only environment scoring against the organism's own
  operational history; note the mirror-problem caveat — logged outcomes are
  real (class-2: the world graded those runs via test results/receipts), but
  any row whose outcome was self-asserted must be excluded at snapshot time
  (the 2026-07-07 zero-trust audit hole, not to be recreated).

### Rejected / deferred candidates

- **#5 gate red-team self-play:** deferred to G-next, not killed. The
  adversary analysis (below) shows its scorer is the hardest to make
  ungameable with a self-generated attack corpus (the attacker and defender
  share a mind — mirror risk). Admit it only when the attack corpus is
  IMPORTED (public jailbreak/injection corpora = class-2), held out, and
  `GateRegistry.propose()` (`telos_gates.py:130`) calibrates inert gates
  (e.g. BHED_GNAN, `telos_gates.py:538-539`, always-passes today) without
  same-PR gate weakening (AI-C1).
- **#7 self-model gym:** strong, but its scorer (run the tests a diff is
  predicted to break) shares G1's substrate and failure mode; fold into G1
  as a secondary scorer arm after G1 closes, rather than a fourth surface.
- **#8 differential-oracle expansion:** owned by dharmagraph-engine track
  (Phase 1 oracle exists, currently 1 test skipped per onboard); expanding
  the pattern belongs there, not in this track.

### Adversary red-team — how each scorer could be gamed, and the kill rule

| Env | Gaming vector | Mitigation baked into spec | Kill criterion |
|---|---|---|---|
| G1 | answer-leak: the landed diff is in `git log`; agent greps history for the fix | solver runs in a worktree truncated at base sha (no future refs: `git clone --revision=<base>` sandbox); scorer asserts no future-object access; ANY leak detection = task void | if leak-free sandboxing cannot be proven by a receipt, kill G1 |
| G1 | overfitting to repo idioms inflates apparent skill | held-out 30% by date + rotation; report train/held-out gap in every receipt | held-out gap persistently > 2x train gain = archive that policy line as overfit |
| G2 | vague resolution criteria ("AI will advance") auto-resolve true | resolution criterion must name the Bronze source class + machine-checkable predicate at prediction time; unresolvable-by-date = scored as max-loss, never dropped | >20% of predictions unresolvable in a window = freeze the emitting policy |
| G2 | self-resolution: the system writes the ingest row that resolves its own prediction | resolver may only consume Bronze receipts whose `prov.agent` is a fetcher organ, corroboration k≥2 (`bronze.py:424-429`) | any self-authored resolution row = incident, receipt to BROKEN_REGISTER |
| G3 | QA generator and solver share the kernel — answers memorized at generation time | QA generation runs against raw Bronze (pre-kernel); held-outs digest-sealed before any kernel write of that corpus batch | held-out accuracy ≈ train accuracy AND both ≈ 100% = leak; freeze and audit |
| G3-B | trivial edges (masked edge inferable from degree alone) | mask-set generator excludes edges recoverable by a degree/popularity baseline; report baseline-vs-model delta, not raw score | model ≤ popularity baseline on 3 consecutive packs = no signal; rotate corpus or kill arm |
| G4 | replay leakage: policy peeks at logged outcome column | evaluator interface exposes only pre-outcome features; outcome column readable by scorer process only | any evaluator with outcome access in the policy path = kill until re-architected |
| all | receipt without digest (the 2026-07-07 audit hole) | every gym receipt carries `digest` (checker-compatible seal) + `content_digest` (replay identity); track criteria use `receipt_valid` with `expect_digest: true` | a digest-free gym receipt fails CI by construction |

---

## (c) The 10x baseline scoreboard — measured, receipted, re-runnable

**Owner (new, this dossier):** `scripts/governance/inward_ascent_baseline.py`
→ `reports/governance/inward_ascent/baseline_receipt.json`. It RAN this
session; the receipt is committed alongside this dossier and verified against
the real governance checker
(`check_track_status.check_receipt_valid(..., expect_digest=True)` → passed,
"digest intact"). `--check` re-measures and fails on tamper (seal) or content
drift (replay identity). Re-run: `python3
scripts/governance/inward_ascent_baseline.py`.

Baseline as measured on this host, 2026-07-07 (content_digest
`e313628e407385b7…`; git substrate frozen at the snapshot sha recorded in
the receipt, so committing the receipt never shifts the measurement):

| Surface | Baseline | 10x means | Measured by |
|---|---|---|---|
| ingest_volume | **0** bronze receipts (organs dark, live-capability verified) | light the organs, then 10x receipts/week under corroboration | receipt count in Bronze store |
| ingest_quality | UNKNOWN (0 receipts → corroboration undefined) | fraction reaching k≥2 | corroboration block per receipt |
| ontology_coverage | UNKNOWN — `ontology.db` ABSENT this host (BR-007) | entities/edges promoted from ingest | daemon-host measurement needed |
| memory_hit_rate | UNKNOWN — no retrieval-QA harness | G3 arm-A held-out accuracy | G3 scorer |
| gate_catch_rate | UNKNOWN — no held-out attack corpus | deferred with gate gym (G-next) | imported attack corpus |
| routing_regret | UNKNOWN — `runtime.db` ABSENT this host | G4 regret vs. history, ratchet DOWN | G4 scorer (operator-gated) |
| self_model_accuracy | UNKNOWN — no harness | folded into G1 arm 2 | G1 secondary scorer |
| forecast_brier | UNKNOWN — zero resolved predictions (`compute_brier_score()` → None, run this session) | resolved-prediction Brier, ratchet DOWN | G2 scorer |
| git_history_gym substrate | **1331** commits / 273 merges, non-shallow | G1 taskpack size + held-out pass-rate | git log at the pinned snapshot sha (frozen) |

**Honesty note:** 2/9 surfaces measured, 7/9 UNKNOWN. That IS the baseline.
"10x" on a surface becomes claimable only after its first measured non-UNKNOWN
number exists; the scoreboard is the instrument that converts each UNKNOWN
into a number, and every future run re-emits the digest-stamped receipt so
the ratchet is a diff between receipts, not a feeling.

---

## (d) Exit criterion — the gym reports against the trust gate (NORTH_STAR §8)

The inward phase ends when the trust gate opens, measured by
`scripts/governance/trust_gate_status.py` (fact-owner NORTH_STAR §8), never
by gym scores directly:

- **C1** (clean repo, deep flow understanding): ingest map closure checks +
  the G1/G3 receipts give the pointed audit real flow evidence
  (GO intake → bronze → kernel → ontology becomes a measured chain).
- **C2** (swarm > single on coding benchmarks): OWNED BY THE RSI/ARENA LAB.
  This campaign never feeds C2; G1 results are internal-gym numbers, not
  benchmark claims (commensurability rule in `trust_gate_status.py:159-171`
  stands).
- **C3** (venture-cell end-to-end): out of scope (efferent).
- **C4** (all seeded parts wired): lighting the four dark Go organs +
  runtime/ontology stores under real load is direct C4 evidence.
- **C5** (memory-kernel first-token orientation): G3 arm-A hit-rate is the
  first measured C5 instrument.

Phase discipline: PHASE 1+ builds only after operator ratification of this
dossier — zeitgeist ingest live first, then ONE gym environment end-to-end
with its autoresearch loop. One environment fully closed beats four
half-built.

---

## (e) Draft ACTIVE_TRACK.yaml entry (NOT yet applied — ratification artifact)

Applied to `docs/governance/ACTIVE_TRACK.yaml` only after operator
ratification (then run `scripts/governance/render_active_track_includes.py`).
Serves `research-depth` — the currently-uncovered spine objective (onboard:
"GAPS (no active track): … research-depth"); the gym IS the research
instrument. Surfaces are new and non-overlapping with sibling tracks
(`world_radar/**` and `tools/*_go/**` stay with organism-rewire;
`coordination/**`/`council/**` stay with the arena track).

```yaml
  - id: inward-ascent-2026-07
    name: Inward Ascent — afferent ingest + decorrelated simulation gym
    status: ACTIVE
    opened_at: "2026-07-07"
    verified_at: "2026-07-07"
    ttl_days: 21
    owner: "@AmitabhainArunachala"
    serves: research-depth
    complements:
      - organism-rewire-2026-07
      - orchestration-arena-v1-2026-06
    owned_surfaces:
      - docs/plans/INWARD_ASCENT_PHASE0_DOSSIER_2026-07-07.md
      - scripts/governance/inward_ascent_baseline.py
      - reports/governance/inward_ascent/**
    moves_vital_signs:
      - eval_coverage
      - quality_gates
    target_closure_kind: CLOSED_NOT_PROD
    claim_boundary: >-
      Phase 0 only proves the dossier + a replayable baseline receipt.
      Gym results are internal-gym numbers, never benchmark or capability
      claims; C2 stays owned by the RSI/arena lab. Archive fitness remains
      behind the One Wire external quorum.
    description: |
      Operator master prompt 2026-07-07: massive internal evolution via
      afferent-only ingest (four ratified source classes through Bronze ->
      Chetana) and a battery of frozen, held-out, rotating simulation
      environments decorrelated from the RSI/arena lab, with a measured
      10x ratchet baseline. No efferent actions. No gate/ratchet/quorum
      weakening. No new truth stores.
    completion_criteria:
      - id: phase0_dossier_exists
        kind: file_exists
        file: docs/plans/INWARD_ASCENT_PHASE0_DOSSIER_2026-07-07.md
      - id: phase0_firewall_stated
        kind: file_contains
        file: docs/plans/INWARD_ASCENT_PHASE0_DOSSIER_2026-07-07.md
        pattern: "archive fitness for self-modification still requires the"
      - id: baseline_receipt_valid
        kind: receipt_valid
        file: reports/governance/inward_ascent/baseline_receipt.json
        expect_digest: true
        fresh_ttl_days: 21
        requires_keys:
          - schema_version
          - surfaces
          - summary
          - content_digest
    non_goals:
      - No efferent/world-facing actions of any kind (posts, outreach, trades, publishing).
      - Never weaken a gate, ratchet, or the One Wire quorum; gym gradients never touch archive fitness.
      - Do not touch RSI/arena surfaces (dharma_swarm/coordination/**, council/**, arena reports).
      - No new truth stores; Bronze -> Chetana -> MemoryKernel/ontology is the only landing path.
      - Market signals fund and inform slow-horizon planning only; never per-iteration selection.
      - No credentials committed; feed keys are operator-provisioned.
      - Do not edit orchestrator.py beyond minimal seams; keep files <500 lines.
```

---

## (f) Operator decision queue — everything blocked on you, nothing else

1. **Ratify this dossier** (or amend): environment picks G1/G2/G3 now, G4
   operator-gated, gate gym deferred-not-killed.
2. **Apply the track entry** in §(e) to ACTIVE_TRACK.yaml (or instruct me
   to). Confirm `serves: research-depth`.
3. **G4 substrate:** ship a sanitized `runtime.db` snapshot (or grant
   daemon-host execution) — also resolves the ~2191 vs ~8.8k
   delegation_runs discrepancy.
4. **Feed credentials/hosts** (all optional for Phase 1 zeitgeist, which
   needs none): GitHub API token cadence for code-world at volume; any
   Wikidata/market feed hosts to add to the egress allowlist
   (`scripts/ops/provider_egress_hosts.py`).
5. **Daemon-host baselines:** run `python3
   scripts/governance/inward_ascent_baseline.py` on the host that owns
   runtime.db/ontology.db so ontology_coverage and routing-regret substrate
   flip from UNKNOWN to numbers.
