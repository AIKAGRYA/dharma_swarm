# Packet 06: Venture Cells And External Value

Packet ID: `ctx.venture-external-value`

Use when touching Venture Cells, Darshan, Livelihood Loom, TELOS, revenue
wedges, external-human proof, public offers, or real-world action gates.

Do not use for SAB community posting unless the task is explicitly outbound
recruiting or external consent. Use `ctx.sab-flywheel` for the SAB loop.

## Authority Model

- Portfolio owner: `docs/governance/VENTURE_CELL_PORTFOLIO.yaml`
- Active-track owner: revenue/external-human tracks in
  `docs/governance/ACTIVE_TRACK.yaml`
- Organ owners: `dharma_swarm/venture_cell/**`, TELOS docs/reports,
  Livelihood Loom docs/reports
- Proof owner: external acted receipts, consented sanitized artifacts, redacted
  durable evidence outside private raw material

Core invariant: internal artifacts do not count as external value. Real external
humans served means someone outside the repo read, replied, acted, paid, or gave
consented feedback.

## Mission

Move Dharma Swarm from internal coherence to real-world usefulness while
preserving consent, privacy, and honest status. The packet prevents agents from
turning designs, drafts, or imagined outreach into claims of traction.

## First Reads

L0 Safety:

- `make onboard`
- `docs/governance/VENTURE_CELL_PORTFOLIO.yaml`

L1 Route:

- `telos-ai-morning-refinery-2026-06` track in `ACTIVE_TRACK.yaml`
- `docs/governance/VENTURE_CELL_REVENUE_WEDGE.md`
- `docs/architecture/VENTURE_CELL_LIFECYCLE.md`

L2 Owners:

- `dharma_swarm/venture_cell/**`
- `docs/agents/livelihood_loom_ceo/CONTEXT_ENGINEERING.md`
- `docs/agents/codex_telos/CONTEXT_ENGINEERING.md`
- `docs/ops/OPERATOR_IDEA_SPARK_LIVE_INGEST.md`

L3 Evidence:

- `reports/livelihood_loom/**`
- `reports/telos_ai/**`
- `reports/revenue_wedge/first_cash_receipt_status.md`
- `reports/idea_spark/**`

L4 Search:

- `rg -n "external|acted_receipt|consent|FIRST_EXTERNAL|revenue|human" docs reports dharma_swarm tests`
- `rg -n "Livelihood|TELOS|Darshan|VentureCell|external_action" dharma_swarm docs reports tests`

L5 Seat:

- `livelihood_loom_ceo`, `codex_telos`, or a venture-cell owner only after
  loading that seat's wake/context files.

## Live Probes

```bash
make onboard
python3 -m dharma_swarm.idea_spark.cli health --json
```

For Livelihood Loom:

```bash
pytest tests/test_venture_cell_livelihood_loom.py tests/test_venture_cell_external_actions.py
```

For TELOS:

```bash
pytest tests/test_telos_morning_refinery.py
```

## Retrieval Contract

- Query: "external acted receipt consent boundary TELOS"
  Source family: TELOS reports and active track.
- Query: "Livelihood Loom CEO context public enabler consent state"
  Source family: Livelihood Loom agent docs, charter, reports.
- Query: "venture cell portfolio one law external readers replied"
  Source family: Venture Cell portfolio and lifecycle.

## Operating Loop

1. Classify the work: design, internal artifact, consented draft, external
   action, external acted receipt, or revenue.
2. Read the cell's portfolio status and active track gate.
3. Confirm consent and privacy boundary before external action.
4. Generate or inspect the artifact.
5. If external action is needed, keep operator in the loop.
6. Store redacted durable evidence only.
7. Do not upgrade cell status without proof.

## Guardrails

- Do not claim external traction from internal drafts.
- Do not expose private raw morning pages, worker data, emails, or secrets.
- Do not send outreach without operator approval.
- Do not treat a design-only or incubating cell as live.
- Do not weaken the One Law: a cell grows by real, gated, verifiable outcome.
- Do not conflate Darshan, Campaign X-Ray, Livelihood Loom, TELOS, and SAB.

## Context Budget

- Tiny: `make onboard`, Venture Cell portfolio, this packet.
- Standard: tiny plus cell-specific context engineering file, latest report,
  active track gate.
- Deep: standard plus lifecycle docs, tests, sanitized artifacts, and redacted
  external receipts.

## Done Criteria

Complete means:

- work stage is labeled honestly;
- consent/privacy boundary is explicit;
- any external claim has redacted durable evidence;
- relevant tests or status probes are run;
- no cell status is upgraded without proof.

## Agent Prompt Block

```text
You are working in Dharma Swarm using context packet ctx.venture-external-value.
Classify the work stage before acting: design, internal artifact, consented draft,
external action, external acted receipt, or revenue. Load the Venture Cell
portfolio and the cell-specific context file. Do not send outreach or expose raw
private material without operator approval. Do not claim external value unless a
real outside human acted and redacted durable evidence exists.
```

## Handoff Receipt Shape

```json
{
  "packet_id": "ctx.venture-external-value",
  "cell_id": "",
  "work_stage": "design|internal_artifact|consented_draft|external_action|external_acted_receipt|revenue",
  "consent_boundary": "",
  "private_material_excluded": true,
  "external_evidence": [],
  "commands_run": [],
  "tests": [],
  "status_change": "none",
  "next_operator_decision": ""
}
```
