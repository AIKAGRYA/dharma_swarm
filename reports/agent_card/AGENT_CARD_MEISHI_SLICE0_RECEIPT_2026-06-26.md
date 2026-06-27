# Agent Card Meishi Slice 0 Receipt

Generated: 2026-06-26
Mission ID: agent-card-meishi-rolodex-2026-06-26
Status: implemented read-only index/checker slice

## What Landed

Slice 0 adds the first working Agent Card meishi substrate:

- `dharma_swarm/a2a/agent_card_index.py`
  - Builds a read-only joined projection over live A2A cards, external
    registrations, identity invariants, authority passports, LivingDock files,
    Semantic Commons, and NATS subject hints.
  - Emits public/extended/operator readiness hints without claiming authority.
  - Computes card/source digests and trust grades.
  - Reports malformed metadata, forbidden aliases, unresolved Semantic Commons
    identity, duplicate live card UIDs, and invalid identity invariants.
- `scripts/governance/agent_card_check.py`
  - CLI wrapper for writing `reports/agent_card/index.json`,
    `reports/agent_card/findings.json`, and `reports/agent_card/index.md`.
  - Supports `--strict` for failing on error findings.
- `tests/test_agent_card_index.py`
  - Covers join behavior, forbidden live alias detection, duplicate UID
    detection, malformed metadata resilience, and report writing.
- `tests/test_agent_card_check.py`
  - Covers checker report writing and strict-mode failure.
- `api/routers/agent_cards.py`
  - Adds read-only `/api/agent-cards`, `/api/agent-cards/{agent_uid}`, and
    `/api/agent-cards/{agent_uid}/public` endpoints.
  - Public card output intentionally omits local source paths and raw findings.
- `tests/test_agent_cards_router.py`
  - Covers list and public-card lookup by hyphen/underscore alias.

## Live Index Result

Command:

```bash
./.venv/bin/python scripts/governance/agent_card_check.py --json
```

Result:

- card files indexed: 33
- projected agents: 39
- status: fail
- error findings: 3
- warning findings: 40
- trust grades:
  - verified: 3
  - registered: 12
  - discovery: 14
  - evidence_only: 7
  - quarantine: 3

The checker is intentionally honest: the live card system is now visible, but
not yet clean.

## Live Error Findings

- `fable_5_cursor`: forbidden live card alias. Current live registration treats
  `fable_5_cursor` as an agent, while Semantic Commons lists that spelling as a
  forbidden alias under `semobj.sarathi`.
- `opencalw`: forbidden live card alias. Semantic Commons marks it as a typo
  collision with OpenClaw.
- `opus_forge_architect`: duplicate live card UID. Both
  `opus-forge-architect.json` and `opus_forge_architect.json` resolve to the
  same `agent_uid`.

## Verified Agents In Current Index

The current read-only join can fully verify these agents from card,
registration, invariant, authority, and Semantic Commons evidence:

- `codex_composer`
- `codex_telos`
- `palantir_pilot`

## Verification

Commands:

```bash
pytest -q tests/test_agent_card_index.py tests/test_agent_card_check.py
pytest -q tests/test_agent_card_index.py tests/test_agent_card_check.py tests/test_agent_cards_router.py tests/test_a2a_spec_conformance.py tests/test_agent_admission.py
pytest -q tests/test_a2a_spec_conformance.py tests/test_agent_admission.py
make semantic-commons-check
```

Results:

- new Agent Card tests: 7 passed
- Agent Card + A2A/admission combined suite: 93 passed, 1 warning
- existing A2A/admission tests: 84 passed, 1 warning
- Semantic Commons check: 0 errors, 0 warnings
- compile check with repo venv: passed for `agent_card_index.py`,
  `agent_card_check.py`, and `agent_cards.py`

## Boundary

This slice is read-only. It does not mutate live cards, registrations,
Semantic Commons, NATS, passports, LivingDock files, or runtime authority. It
creates the projection layer needed for the future dashboard, handoff exports,
and live NATS publication.

## Next Slice

Recommended Slice 1:

- Add dashboard `Agent Cards` list/detail surfaces using the new projection.
- Add a strict live-card remediation plan for the three quarantine findings.
- Add public/extended card export helpers for A2A and handoff packets.
