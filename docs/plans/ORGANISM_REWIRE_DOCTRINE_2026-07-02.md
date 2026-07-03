# Organism Rewire — Ratified Doctrine (2026-07-02)

**Role:** plan/doctrine record for track `organism-rewire-2026-07` (`docs/governance/ACTIVE_TRACK.yaml` owns the live items; this file owns the *why* and the design constraints so future sessions do not re-derive or drift).
**Source:** operator ratification session 2026-07-02, following the 29-agent verified organism sweep (9 scanners, 16 adversarial verifiers, 3 judges) and a vision re-read against `docs/vision_maps/NORTH_STAR.md` + `foundations/THE_ORGANISM.md`.
**Rule:** if this file disagrees with ACTIVE_TRACK.yaml or a receipt, trust the track/receipt.

## 1. The receipt invariant (bypass allowlist → zero, hold-at-zero)

Ratified as an INVARIANT, not policy — policy measurably failed (~86% of dispatch was unreceipted when audited). Executes under spine-adoption track item 4. Engineered reliefs, both required:

- The `non_production` classification in `spine_bypass_report.py` remains a real sandbox lane: prototypes may dispatch directly but can never ship.
- NO runtime escape hatch. The only exception path is a visible governance act: a PR that deliberately raises the ratchet baseline (`docs/governance/hygiene/ratchet_baselines.json` → `spine_bypass_entries`) with review.

Known costs, accepted: spine becomes a chokepoint (it must stay boring/stable; no cleverness in `invoke_agent`); EvidenceReceipt schema becomes effectively constitutional; wrapper reshapes exception semantics at each migrated site (handle per-site, as Slice 2 did); receipts-DB retention policy needed within ~6 months.

## 2. Spine standing-on (D1) + operator visibility + VPS

- `DHARMA_SPINE_DISPATCH=1` goes into the committed compose env — a one-way door in practice (downstream consumers will assume the stream). Chosen knowingly.
- The operator must be able to SEE and FEEL the spine: (a) `make orient` Loop-1 LIVE persistently; (b) `dgc spine tail` — live one-line-per-EvidenceReceipt stream (task → trace_id → provider → status); the intuition test is "give an agent work in the TUI, watch the receipt appear in seconds"; (c) read-only cockpit pulse panel: receipts/hour, last-receipt age, dropoff count.
- VPS shift is NOW-class, not later: compose `swarm` service + NATS + litestream state replication on an always-on host; Mac demotes to dev seat/mirror. The receipt stream is what makes a remote daemon trustworthy (verifiable from anywhere). Operator provisions host + secrets.

## 3. Memory doctrine (D2) — deeper than "kernel first-token"

NORTH_STAR §8.5 says "memory-kernel first-token orientation"; the ratified refinement is MORE canon-faithful because NORTH_STAR §3 subordinates to the Transcendence Principle (homogenization violates doctrine):

1. **Position earned by evidence class, not module.** Only receipt-backed, TTL-carrying facts (structural truth) may occupy first-token. Narrative memory stays depth-on-demand. Context-window position = trust hierarchy. This caps memory-poisoning blast radius (cf. the COLM dead-calendar failure: a stale fact at first-token would have propagated fleet-wide).
2. **Memory acts at routing time, not just reading time.** The kernel's highest-leverage seat is upstream: informing WHICH agent gets the task and with which constraints (skill selection). Compounds learning without touching worker priors.
3. **Diversity-preserving sampling for worker seats.** Never broadcast identical first-token memory to workers; sample the kernel differently per seat (bootstrap-ensemble style) so priors stay decorrelated and the Krogh-Vedelsby diversity term survives the memory system. Coordinator/hub/composer seats may take the full first-token view.

Sequencing: spec → shadow canary with quality metrics → only then flip the C5 ordering in `context_compiler.py` (the current priority=4 demotion is intentional design, not a bug).

## 4. External-gradient portfolio (D3) — diversity of objective functions

Evolution needs fitness signals the organism cannot fake from inside. Ratified portfolio (same math as agent diversity — decorrelated fitness signals cancel each other's Goodhart modes):

- **Verified external benchmarks (the forge):** the volume fuel for autoresearch loops — cheap, repeatable, mathematically scoreable. Guardrails: rotating/held-out sets + budget-parity controls (arena's own pending blocker) or it is overfitting, not evolution.
- **Trading / markets (Shakti Ginko → Capital Lab, per NORTH_STAR §4.2):** the self-funding gradient. HARD RULE (track non-goal): P&L is funding + a slow-horizon fitness term (Sharpe over months, Deflated-Sharpe/PBO discipline, paper → small-live gates) and NEVER per-iteration selection signal — a swarm evolved on daily P&L learns to gamble.
- **Paid human work (Darshan/Gaia/SIS/SAB class):** slowest, richest, carries trust-gate C3 and the mission. Third leg, not first.

**≥6 autoresearch nodes** (Karpathy-loop style: frozen eval + mutation operator + diversity-preserving selection + receipts, iterating at volume): (1) arena/orchestration genome — already built, node one; (2) router/model-selection policy; (3) prompt/policy evolution via DarwinEngine post-BR-003; (4) memory promotion policy; (5) telos-gate calibration (thresholds tuned against outcomes, gates never removed); (6) **R_V / self-reference-attractor research lane** — NORTH_STAR §2's measurable-awareness claim regains an owned, receipted eval loop after the COLM calendar death. This portfolio is also the lawful restart path for Dharma Forge/Hydra (STOPPED-HONESTLY below One Wire quorum): external receipts are the only permitted quorum feed.

## 5. Self-modification (D4) — sequenced LAST, by math not caution

Mechanism test early (one canonical run, `DHARMA_EVOLUTION_SHADOW=0`, rollback receipt in the archive). Standing unlock strictly AFTER the receipt stream (D1) and external gradients (§4) exist: apply unlocked against internal benchmarks = Goodhart convergence = diversity-term collapse = transcendence death with green dashboards. Track non-goal enforces the order.

## 6. Organism (D5) and consolidation (D6)

- **Organism promotes via composition root over SwarmManager:** identity/lifecycle/self-reference layer (brings StrangeLoop + attractor live) while SwarmManager keeps dispatch. God modules may EARN their place through review + hardening (operator ruling); narrative seniority earns nothing.
- **MAP-Elites consolidates on `archive.MAPElitesGrid`** (the wired one); `diversity_archive.py` retired/absorbed; arena keeps its genome-descriptor variant only if descriptors are shared. One diversity ledger so the diversity term is measurable in one place.
- **living_agent_kernel earn-in:** activate 2–3 kernels only post-D1 (every wake receipted, visible in presence), monitor, graduate to always-on individually. Dormancy was accidentally load-bearing until the `mark_read` requeue bug was fixed (e08d2d6) — receipted visibility replaces accidental safety.

## 7. Sequencing arc + standing obligations

**1 (drain) → 2 (Loop 5b/Go) → D1 → D3-portfolio → D2-canary → D6a → D4-test → D6b → D4-standing → D5 whenever.**

- Next track opened after this one lands MUST serve `revenue-external-humans-served` (NORTH_STAR §11 90-day: "funds itself totally").
- `research-depth` re-anchors through node 6 above.
- Canon-metabolism rule (NORTH_STAR §9): everything on the `claude/a2a-agent-onboarding-1r8eo5` branch is seed-status until merged to main.

## 8. The unifying principle

Each ratified move converts a category of truth from **narrative** (docs, declarations, one-time witnesses — measured to decay) to **structural** (receipts, ratchets, closure checks, ledgers — which compound: receipts → honest selection → safe self-improvement → delivery → revenue → receipts). End state: a system constitutionally incapable of silent action. Standing counterweight: every ratchet is governance rent priced in diversity — protect the chaos budget (worker prompt diversity, heterogeneous model families, a second revenue vertical) or the organism becomes perfectly honest and perfectly correlated.
