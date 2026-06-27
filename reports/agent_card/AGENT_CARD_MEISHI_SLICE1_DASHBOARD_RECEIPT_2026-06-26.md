# Agent Card Meishi Slice 1 Dashboard Receipt

Generated: 2026-06-26
Mission ID: agent-card-meishi-rolodex-2026-06-26
Status: dashboard rolodex/detail surface implemented

## What Landed

Slice 1 adds the first dashboard-native Agent Card rolodex:

- `dashboard/src/app/dashboard/agent-cards/page.tsx`
  - Adds `/dashboard/agent-cards` as a dense operational Agent Card surface.
  - Renders summary counts, search, trust-grade filter, role filter, readiness
    filter, trading-card grid, and sticky detail panel.
  - Uses the existing Next rewrite path to call `/api/agent-cards`.
- `dashboard/src/components/agent-cards/AgentCardMeishi.tsx`
  - Adds compact trading-card style meishi cards with identity, role, model,
    harness, card count, capabilities, trust grade, findings, source count, and
    handoff readiness.
- `dashboard/src/components/agent-cards/AgentCardDetailPanel.tsx`
  - Adds expandable identity, handoff, A2A envelope, Semantic Commons,
    authority, findings, sources, and raw JSON layers.
  - Adds copy buttons for full JSON and NATS/A2A handoff subjects.
- `dashboard/src/hooks/useAgentCards.ts`
  - Adds polling TanStack Query hooks for the Agent Card index and individual
    cards.
- `dashboard/src/lib/agentCards.ts`
  - Adds reusable filtering, sorting, readiness, blocked-state, and role helper
    logic.
- `dashboard/src/lib/types.ts`
  - Adds TypeScript types aligned to the live Agent Card API payloads.
- `dashboard/src/lib/api.ts`
  - Adds typed fetch helpers for `/api/agent-cards`,
    `/api/agent-cards/{agent_uid}`, and
    `/api/agent-cards/{agent_uid}/public`.
- `dashboard/src/lib/dashboardNav.ts` and
  `dashboard/src/components/layout/Sidebar.tsx`
  - Add the `Agent Cards` route beside the existing `Agents` route without
    replacing the current agent workspace.
  - Remove the duplicate manual `Opportunities` nav entry because it is already
    supplied by the canonical control-plane route deck.
- `dashboard/src/app/dashboard/layout.tsx`
  - Suppresses the global `OperatorMicrographics` panel only on
    `/dashboard/agent-cards` routes so the rolodex is the first visible
    operator surface.
- `dashboard/src/lib/agentCards.test.ts`
  - Covers search, trust/role/readiness filters, blocked status, handoff
    readiness, and stable role extraction.

## Boundary

This slice is still read-only. It does not mutate live cards, registrations,
Semantic Commons, NATS, passports, LivingDock files, runtime authority, or the
existing `/dashboard/agents` workspace.

## Verification

Commands:

```bash
node --test --experimental-strip-types dashboard/src/lib/agentCards.test.ts dashboard/src/lib/dashboardNav.test.ts dashboard/src/lib/api.test.ts
npm run lint --prefix dashboard -- src/app/dashboard/layout.tsx src/app/dashboard/agent-cards/page.tsx src/components/agent-cards/AgentCardMeishi.tsx src/components/agent-cards/AgentCardDetailPanel.tsx src/hooks/useAgentCards.ts src/lib/agentCards.ts src/lib/agentCards.test.ts src/lib/dashboardNav.ts src/components/layout/Sidebar.tsx
curl -fsS http://127.0.0.1:3420/api/agent-cards
```

Results:

- Node dashboard tests: 14 passed.
- Targeted ESLint for new/modified Agent Card dashboard files: passed.
- Next proxy smoke test: `ok 39 3 40`.
- Playwright visual smoke: `/dashboard/agent-cards` rendered with live data,
  first viewport focused on the Agent Cards rolodex, and zero relevant browser
  console messages.

Repo-wide checks:

- `npm run lint --prefix dashboard` is currently blocked by an existing
  unrelated `react-hooks/set-state-in-effect` error in
  `dashboard/src/components/cockpit/ActiveTrackPortfolioBoard.tsx`.
- `./dashboard/node_modules/.bin/tsc --noEmit --project dashboard/tsconfig.json`
  remains blocked by existing dashboard TypeScript/test debt, including the
  current `.ts` test import convention and pre-existing runtime-control-plane
  type gaps.

## Current User-Facing Shape

The new dashboard route answers the first core identity questions:

- who the agent claims to be;
- whether it is verified, registered, discovery-only, evidence-only, or
  quarantined;
- where the backing card/source evidence lives;
- whether public, extended, and operator handoff packets are ready;
- what A2A, Semantic Commons, authority passport, and identity invariant
  evidence supports the card;
- which NATS/A2A subject names should be used for handoff.

## Next Slice

Recommended Slice 2:

- Add row comparison mode for identity, model, authority, endpoints, status,
  findings, and handoff readiness.
- Add markdown, public A2A, and jCard/vCard export helpers.
- Start the NATS projection proof behind a disabled-by-default command.
- Remediate the three quarantine findings or add explicit quarantine receipts.
