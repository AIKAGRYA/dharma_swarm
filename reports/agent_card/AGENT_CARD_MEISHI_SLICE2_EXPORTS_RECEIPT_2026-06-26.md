# Agent Card Meishi Slice 2 Export Receipt

Generated: 2026-06-26
Mission ID: agent-card-meishi-rolodex-2026-06-26
Status: portable export and handoff formats implemented

## What Landed

Slice 2 turns Agent Cards from dashboard-only records into portable digital
meishi packets:

- `dharma_swarm/a2a/agent_card_exports.py`
  - Adds shared export shaping for:
    - public JSON
    - extended JSON
    - operator JSON
    - Markdown handoff brief
    - jCard JSON
    - vCard / `.vcf`
  - Keeps public packets small and safe.
  - Keeps extended packets richer while removing local filesystem paths and
    redacting absolute local path values.
  - Leaves operator JSON as the full local evidence packet for dashboard/native
    operator use.
- `api/routers/agent_cards.py`
  - Reuses the shared public-card exporter.
  - Adds `/api/agent-cards/{agent_uid}/exports/{format}`.
  - Supported format aliases include `public-json`, `extended-json`,
    `operator-json`, `markdown`, `md`, `jcard`, `vcard`, and `vcf`.
- `dashboard/src/lib/api.ts` and `dashboard/src/lib/types.ts`
  - Adds `AgentCardExportFormat`.
  - Adds `fetchAgentCardExportText(...)` for raw export packets.
- `dashboard/src/components/agent-cards/AgentCardDetailPanel.tsx`
  - Adds copy buttons for Markdown, vCard, and jCard.
  - Adds a `.vcf` download button.
  - Keeps JSON and NATS/A2A subject copy actions.
- `tests/test_agent_card_index.py`
  - Proves public exports omit local source evidence.
  - Proves extended exports include source counts but scrub local paths.
  - Proves Markdown, jCard, vCard, and export alias behavior.
- `tests/test_agent_cards_router.py`
  - Proves markdown/vCard export routes.
  - Proves extended JSON route is path-scrubbed.
  - Proves unsupported formats return `400`.

## Boundary

This slice remains read-only. It does not mutate live A2A cards,
registrations, Semantic Commons, NATS, authority passports, LivingDock files,
or runtime authority.

## Live Export Proof

Commands:

```bash
curl -fsS http://127.0.0.1:8420/api/agent-cards/codex_composer/exports/markdown
curl -fsS http://127.0.0.1:8420/api/agent-cards/codex_composer/exports/vcard
curl -fsS http://127.0.0.1:3420/api/agent-cards/codex_composer/exports/extended-json
```

Observed:

- Markdown begins with `# Agent Card: Codex_Composer`.
- vCard begins with `BEGIN:VCARD`, includes `X-AGENT-UID:codex_composer`,
  and includes Agent Card NATS handoff subjects.
- Extended JSON reports `dharma.agent_card.extended.v0`, `codex_composer`,
  `verified`, no `sources` field, no `/Users/dhyana` path leakage, and at
  least one `[local-path-redacted]` marker where local paths were present in
  source truth.

## Dashboard Proof

Playwright exercised `/dashboard/agent-cards` with the refreshed API:

- waited for live `39 shown`;
- clicked the `MD` export button;
- verified clipboard content was a real Markdown Agent Card packet;
- captured `/tmp/agent-cards-dashboard-exports.png`;
- observed zero relevant browser console messages.

## Verification

Commands:

```bash
pytest -q tests/test_agent_card_index.py tests/test_agent_cards_router.py
./.venv/bin/python -m py_compile dharma_swarm/a2a/agent_card_index.py dharma_swarm/a2a/agent_card_exports.py api/routers/agent_cards.py
npm run lint --prefix dashboard -- src/components/agent-cards/AgentCardDetailPanel.tsx src/lib/api.ts src/lib/types.ts
node --test --experimental-strip-types dashboard/src/lib/agentCards.test.ts dashboard/src/lib/api.test.ts dashboard/src/lib/dashboardNav.test.ts
pytest -q tests/test_agent_card_index.py tests/test_agent_card_check.py tests/test_agent_cards_router.py tests/test_a2a_spec_conformance.py tests/test_agent_admission.py
make semantic-commons-check
```

Results:

- Agent Card export/index/router tests: 11 passed, 1 existing warning.
- Python compile check: passed.
- Targeted dashboard lint: passed.
- Dashboard Node tests: 14 passed.
- Agent Card + A2A/admission regression: 97 passed, 1 existing warning.
- Semantic Commons check: 0 errors, 0 warnings.

## Next Slice

Recommended Slice 3:

- Add comparison mode for identity, authority, model, endpoint, findings, and
  handoff readiness.
- Add disabled-by-default NATS projection proof for public/status packets.
- Add explicit remediation receipts for the three quarantine findings.
- Add signed/canonical JSON preparation for future JWS/DID/VC wrappers.
