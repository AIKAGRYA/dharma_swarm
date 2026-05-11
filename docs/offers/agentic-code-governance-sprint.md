# Agentic Code Governance Sprint

**Offer type:** Paid service engagement (3-7 days)
**Target buyer:** Engineering leads at AI-heavy teams shipping with copilots, agents, or LLM-generated code.
**Price range:** $5K-$25K depending on repo count, team size, and repair scope.

---

## The Problem

Your team ships faster with AI coding tools. But faster is not safer.

- **AI slop accumulates.** Generated code that works but is untested, undocumented, poorly typed, or cargo-culted from training data. It passes CI. It ships. It rots.
- **Provenance is invisible.** You cannot tell which code was human-written, which was AI-generated, and which was AI-modified. When a security audit or SOC2 review asks "who wrote this?", you have no answer.
- **Agents act without governance.** Autonomous coding agents (Devin, Cursor, Copilot Workspace, Claude Code) make PRs, merge code, and modify infrastructure. There is no gate between "agent wants to act" and "action happens."
- **Evals are missing.** You measure agent throughput (PRs merged, tickets closed) but not agent quality (defect rate, revert rate, downstream breakage, maintenance cost).

Every week this compounds. The codebase drifts further from governed, auditable, high-quality software.

---

## What We Deliver

### Phase 1: Audit (Day 1-2)

- **Repo scan** with Semgrep + custom dharma_swarm rules for AI slop patterns:
  - Dead code from abandoned generations
  - Duplicated logic across AI-generated files
  - Missing type annotations on public APIs
  - Hardcoded values that should be config
  - Test gaps: modules with 0% coverage
  - Security: exposed secrets, unsafe deserialization, path traversal
- **Provenance mapping:** Git-blame analysis to identify AI-generated vs human-written code. Commit message pattern analysis. PR author classification.
- **Agent audit:** Inventory of all AI agents with repo access. Permission scope analysis. Action history review.
- **Ranked slop report:** Every finding scored by severity (critical/high/medium/low) and estimated maintenance cost ($/year).

### Phase 2: Install Gates (Day 3-5)

- **Packet provenance:** Every code change gets a signed provenance record: who proposed it, what agent generated it, which model, what prompt, gate decisions, test results.
- **CI gates:** Pre-merge checks that block AI-generated code unless it passes:
  - Type coverage threshold (configurable, default 80%)
  - Test coverage for new code (configurable, default 70%)
  - Slop score below threshold
  - Human review required for agent PRs above a diff-size threshold
- **Eval framework:** Per-agent quality scoring:
  - Defect introduction rate
  - Revert rate
  - Time-to-merge vs time-to-revert ratio
  - Downstream breakage attribution
- **Audit ledger:** Append-only log of all agent actions, gate decisions, and outcomes. Queryable. Exportable for compliance.

### Phase 3: Repair (Day 5-7, optional)

- **Governed agent repair loops:** We run dharma_swarm's Darwin Engine against your worst slop. The engine proposes fixes, gates check them, tests validate them, and only improvements that pass all gates get merged.
- **Delivered as PRs** with full provenance, test results, and before/after metrics.
- **You approve every merge.** No autonomous spam. The system proposes; you decide.

---

## Deliverables

| Artifact | Format | Retention |
|---|---|---|
| Slop Report | Markdown + JSON | Permanent in your repo |
| Provenance Records | JSONL (append-only) | Your CI pipeline |
| CI Gate Config | YAML / GitHub Actions | Your repo |
| Eval Dashboard | JSON metrics + optional Grafana | Your infra |
| Audit Ledger | SQLite + JSONL export | Your repo |
| Repair PRs | GitHub PRs with provenance | Your repo |

---

## Why Us

dharma_swarm is the only agent framework with **telos-gated autonomy**: 11 dharmic safety gates that run *before* the agent acts, not as audit after. We built packet provenance, witness chains, signed execution, and autonomous treasury management for our own system. Now we install it in yours.

- **Not a SaaS.** We install governance *in your repo*, not behind our API.
- **Not a dashboard.** We install gates that *block bad code*, not dashboards that *show you* bad code after it shipped.
- **Not a consultant who writes a PDF.** We deliver PRs, CI configs, and running code.

---

## Competitive Context

| Player | What they sell | What they lack |
|---|---|---|
| ServiceNow Autonomous Workforce | Role-scoped AI specialists (IT, CRM, HR) | No code governance |
| Microsoft Agent 365 | Agent registry, lifecycle, audit logging | No slop detection, no repair |
| OpenAI AgentKit | Agent builder + evals | No CI integration, no provenance |
| AWS Bedrock AgentCore | Runtime, policy, memory, evals | Cloud-only, no repo-level gates |
| Semgrep / CodeQL | Static analysis rules | No agent awareness, no provenance |

We are the only team that combines **slop detection + provenance + CI gates + governed repair** in one engagement.

---

## Engagement Model

1. **Scope call** (30 min, free): We look at your repo(s), estimate slop density, and quote.
2. **Deposit:** 50% upfront, 50% on delivery.
3. **Sprint:** 3-7 days depending on scope. Daily async updates. Final walkthrough call.
4. **Ongoing (optional):** Monthly governance check + slop trend report. $2K/month.

---

## Contact

Email: [REDACTED - set via economic_spine.py outreach config]
Subject line: "Code Governance Sprint — [your company]"
