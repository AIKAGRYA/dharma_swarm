# Venture Operator Systems Living Dossier

**Date opened:** 2026-05-27  
**Status:** Living research dossier  
**Active field subject:** Cofounder.co onboarding for Darshan  
**Comparative subjects:** Polsia, Company.co, OpenClaw, adjacent agentic-company shells  
**Purpose:** Learn how external AI company operators work from the inside so Dharma Swarm can eventually implement its own native VentureCell operator layer.

---

## Core Thesis

Dharma Swarm should not merely subscribe to Cofounder, Polsia, or similar services. It should metabolize them.

The long-term target is a native Dharma Swarm interface that can create, operate, observe, fund, kill, and spin out VentureCells. Cofounder, Polsia, Company.co, OpenClaw, and adjacent systems are field specimens. Each interaction should teach the swarm how an AI-native operator shell handles:

- onboarding;
- business-plan formation;
- design and brand setup;
- task routing;
- agent roles;
- skills and reusable instructions;
- managed infrastructure;
- publishing;
- growth and sales workflows;
- human approvals;
- receipts;
- failure modes;
- pricing and value capture;
- trust boundaries.

Darshan is the live case study. Cofounder is the active collaborator. Polsia remains a benchmark/observatory candidate.

## Relationship To Darshan

Darshan owns the content machine and final judgment.

External operators may help operate the shell:

- launch calendar;
- editorial ops board;
- source-pack workflow;
- claim-ledger workflow;
- distribution workflows;
- design/brand kit;
- static public surface;
- newsletter setup;
- analytics;
- growth review;
- revenue experiments;
- outreach drafts subject to approval.

External operators must not own:

- final claims;
- final editorial voice;
- source-trust decisions;
- correction/refusal decisions;
- sacred/name/positioning judgment;
- final publish approval;
- autonomous outreach without explicit review.

## Current Internal Implementation

The Darshan codebase now has two logging layers:

- Legacy Polsia-specific log: `dharma_swarm/venture_cell/darshan/polsia_log.py`
- General external operator log: `dharma_swarm/venture_cell/darshan/operator_log.py`

Runtime path:

```text
~/.dharma/venture_cell/DARSHAN/external_operator_observations.jsonl
```

CLI:

```text
python -m dharma_swarm.venture_cell.darshan.cli log-operator ...
```

The generic log is now the canonical path for Cofounder observations. The Polsia log remains for backward compatibility and Polsia-specific comparison.

## Cofounder Findings To Date

Observed through live onboarding screenshots and official docs:

- Cofounder asks targeted onboarding questions before generating plan/workspace structure.
- Cofounder accepted the Darshan business plan and moved into a design roadmap.
- The design agent becomes active early and asks for brand-kit setup.
- Cofounder has a visible roadmap sequence: brand kit, design logo, pitch deck, component library.
- Cofounder supports tasks, review states, approvals, managed GitHub/Vercel/Supabase/Postmark, skills, custom agents, MCP integrations, marketing agent, sales agent, design agent, and publishing through PR/review flow.
- Cofounder is therefore well-suited to the operating shell around Darshan, not to final Darshan judgment.

## External Source Anchors

- Cofounder pricing and feature matrix: https://cofounder.co/pricing
- Cofounder custom agents: https://docs.cofounder.co/agents/custom-agents
- Cofounder skills: https://docs.cofounder.co/agents/skills
- Cofounder tasks: https://docs.cofounder.co/workspace/tasks
- Cofounder marketing agent: https://docs.cofounder.co/agents/marketing-agent
- Cofounder sales agent: https://docs.cofounder.co/agents/sales-agent
- Cofounder design agent: https://docs.cofounder.co/agents/design-agent
- Cofounder publishing: https://docs.cofounder.co/publishing/overview
- Cofounder MCP: https://docs.cofounder.co/integrations/mcp-toolkits
- Polsia media benchmark: https://www.tbpndigest.com/story/2026-03-30/polsia-the-ai-slop-spelled-backwards-platform-that-autonomously-builds-and-runs-companies-for-49month
- Polsia risk/review benchmark: https://preuve.ai/blog/polsia-review

## Study Questions

1. Which operator functions can be delegated without degrading Dharma Swarm's judgment?
2. Which operator functions require a human/Dharma Swarm approval gate?
3. How does Cofounder represent work state, agent roles, reviewable artifacts, and approvals?
4. How does Cofounder manage publishing and infrastructure ownership?
5. How do Cofounder tasks map to Dharma Swarm TaskBoard cards?
6. How do Cofounder agents map to Dharma Swarm roles and future VentureCell rosters?
7. Which Cofounder features should become native Dharma Swarm primitives?
8. Which Polsia features should remain only comparative warnings?
9. What receipts does each platform provide, and what receipts are missing?
10. What is the minimal native Dharma Swarm operator shell that would let one operator manage many VentureCells?

## Working Model

External operators are not competitors first. They are teachers.

Dharma Swarm's future VentureCell operator should learn from:

- Cofounder's practical workspace, design, marketing, sales, task, publishing, and managed-service flows;
- Polsia's company-running ambition and market story;
- OpenClaw's broad tool/skill surface and security lessons;
- Dharma Swarm's own telos gates, ontology, Chetana memory, TaskBoard, DecisionLog, and witness discipline.

The target is not to clone any one tool. The target is a Dharma Swarm-native operator layer that can conduct many tentacles while preserving source trust, public service, reversibility, and final judgment.
