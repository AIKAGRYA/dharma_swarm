# Company-Builder Parity — the TAM board

**Machine:** Transdimensional Abundance Machine (TAM) · **Schema:** `tam_ledger.v1` · **Generated:** 2026-07-07T11:41:33Z
**Replay:** `python3 scripts/governance/tam_ledger.py --check`

## Headline: Company-Builder Parity = **35.0%** [RED]

Baseline: Polsia (polsia.com) + Cofounder (cofounder.co) — public data snapshot 2026-06-10, reports/anatomy_altitude_2026-06-10/lane_F_world.md; refresh of competitor facts is an open next-item, not silently assumed current.

0% = far below the Polsia/Cofounder capability baseline; 100% = at parity on everything they do; >100% = we exceed on axes they cannot match. Math this render: 3.5 / 10 comparable capabilities (Behind=0, At parity=1, Ahead=1.5; Unmeasured=0 **and stays in the denominator** — not measuring can never inflate this number; no-equivalent rows are watched separately).

**Velocity:** unmeasured — needs a second render (this chain is the point: the board must show d(parity)/dt over time)

## The board

### Behind (6)

- **Org-shaped multi-agent orchestration (departments, roster, routing)**
  - ours: WIRED_BUT_DORMANT — dharma_swarm/orchestrator.py + dharma_swarm/spine/invoke.py (reports/anatomy_altitude_2026-06-10/lane_F_world.md:21)
  - note: deeper than the department metaphor, but live spine-dispatch persistence on the daemon host is still operator-pending (organism-rewire-2026-07 D1)
  - Cofounder: CLAIMED [vendor-claim] — departmentalized agents (Engineering/Sales/Marketing/...) with managers and shared context (https://cofounder.co)
- **Customer-facing execution (inbox warming, outbound, Stripe, support)**
  - ours: ABSENT — clean negative — reports/anatomy_altitude_2026-06-10/lane_F_world.md:25 (venture_cell/ holds only darshan/ + operator_os/)
  - Cofounder: CLAIMED [vendor-claim] — inbox warming, outbound, paid marketing, Stripe, support automation (https://cofounder.co)
- **Go-to-market milestone scaffold (incorporation -> product -> sales -> scale)**
  - ours: ABSENT — clean negative — reports/anatomy_altitude_2026-06-10/lane_F_world.md:26 (no staged GTM state machine in the repo)
  - Cofounder: CLAIMED [vendor-claim] — milestone scaffold from incorporation to scale (https://cofounder.co)
- **Public pricing + billing surface (revenue-share alignment)**
  - ours: ABSENT — clean negative — reports/anatomy_altitude_2026-06-10/lane_F_world.md:42 (no billing surface, customer object, or funnel)
  - Polsia: SHIPPED [vendor-claim] — $49/mo + 20% revenue share, publicly priced (https://polsia.com/; https://www.contextstudios.ai/blog/polsia-how-a-solo-founder-hit-1m-arr-in-30-days-with-ai-agents)
- **Distribution, paying customers, ARR**
  - ours: ABSENT — $0 revenue across every economic surface — reports/anatomy_altitude_2026-06-10/lane_F_world.md:199 (clean negative #1); docs/governance/VENTURE_CELL_PORTFOLIO.yaml revenue_usd: 0
  - Polsia: CLAIMED [source-pending] — ~$10M ARR claimed 5 months post-launch, 7,600 customers, 85% month-2 retention — unverified, and a 4.4x claimed-vs-actual gap is documented (claimed $3M+ vs $689K run-rate) (https://en.ain.ua/2026/05/25/ai-startup-polsia-with-no-employees-raised-30m-in-funding/; https://aiweekly.co/alerts/polsia-solo-founder-raises-30m-at-250m-valuation; https://zilla.so/blog/polsia-review)
- **End-to-end company operation by agents (research -> code -> ads -> support -> sales)**
  - ours: ASPIRATION — docs/governance/VENTURE_CELL_PORTFOLIO.yaml (live cell statuses read at render time; see portfolio_live_read)
  - note: one externally-serving publication cell; no full-company loop
  - Polsia: CLAIMED [vendor-claim] — nine AI agents end-to-end (research, code, ads, support, sales) (https://polsia.com/)

### At parity (2)

- **Exception-based human-in-the-loop approval of dangerous actions**
  - ours: RUNS — dharma_swarm/telos_gates.py + evolution gate PEP (reports/anatomy_altitude_2026-06-10/lane_F_world.md:22)
  - Cofounder: CLAIMED [vendor-claim] — approval required when potentially dangerous actions are taken (https://cofounder.co)
- **Extensibility: MCP, custom APIs, skills, custom codebase**
  - ours: RUNS — dharma_swarm/skills.py (SkillRegistry) + the four tracked skill registries (CLAUDE.md §Skills & Agent Role Registries)
  - Cofounder: CLAIMED [vendor-claim] — connect MCP, custom APIs, custom skills, or an entire custom codebase (https://cofounder.co)

### Ahead (1)

- **Typed, witnessed decision gates (auditable approval records)**
  - ours: RUNS — dharma_swarm/telos_gates.py (GateRegistry/TelosGatekeeper) + ~/.dharma/witness/ (reports/anatomy_altitude_2026-06-10/lane_F_world.md:28)
  - Cofounder: CLAIMED [vendor-claim] — 'potentially dangerous' vibes-based approval; no typed or witnessed decision record published (https://cofounder.co)
  - exceed-vector: reports/anatomy_altitude_2026-06-10/lane_F_world.md:28 — 'auditable in a way Cofounder structurally is not'

### No competitor equivalent (exceed-vector watch) (2)

- **Verifiable (receipted) revenue — 'honest ARR' a third party can check** ⭐ headline differentiator
  - ours: WIRED_BUT_DORMANT — dharma_swarm/spine/receipt.py (EvidenceReceipt) RUNS at the dispatch chokepoint; $0 receipted revenue to date (reports/anatomy_altitude_2026-06-10/lane_F_world.md:28,44)
  - note: THE HEADLINE DIFFERENTIATOR: incumbents structurally cannot publish receipted revenue without exposing their claims gap; unrealized until real dollars flow through the receipt spine
  - Polsia + Cofounder: ABSENT [third-party-report] — no incumbent publishes third-party-verifiable revenue; Polsia's documented 4.4x claimed-vs-actual ARR gap shows why they cannot (https://zilla.so/blog/polsia-review)
- **Governed self-evolution of the operating substrate (DGM-class)**
  - ours: WIRED_BUT_DORMANT — dharma_swarm/evolution.py + dgm_loop.py — 'Semi-working / dangerous overclaim risk' (reports/swarm_genome/2026-06-11/SYNTHESIS.md §Organ Health Table)
  - Polsia + Cofounder: ABSENT [vendor-claim] — no public evidence either system self-modifies its own substrate under governance (public surfaces checked 2026-06-10, reports/anatomy_altitude_2026-06-10/lane_F_world.md) (https://cofounder.co; https://polsia.com/)

### Unmeasured (1)

- **Competitor internal architecture quality / production reliability**
  - ours: RUNS — repo-inspectable: 770+ modules (python3 xray.py), test suite, docs/architecture/NAVIGATION.md
  - Polsia + Cofounder: UNKNOWN [unverifiable] — SPECULATIVE — neither publishes architecture (reports/anatomy_altitude_2026-06-10/lane_F_world.md:18,204); no citable claim exists, so this row is UNMEASURED, not guessed (NO CITATION)

## Honesty & doctrine

- authority: `projection_only` — this board owns no fact; it projects lane_F world triangulation, the venture-cell portfolio, and the genome organ-health table.
- efferent action: none — afferent measurement only (no outreach, no publishing, no benchmark claims).
- portfolio live-read at render time: 11 cells declared; ACTIVE-class: ['darshan-publication', 'goodworks-dgm'].
- naming: TAM = Transdimensional Abundance Machine (operator-resolved 2026-07-07); TAM = Total Addressable Market (foundations/FIVE_FOURTEEN_A.md:49) and the Darshan-owned reports/tam/ are deliberately not overloaded.
- every competitor number carries a source URL and a verification label (NORTH_STAR §5 source-pending rule); anything unverifiable renders UNMEASURED with the gap named.

