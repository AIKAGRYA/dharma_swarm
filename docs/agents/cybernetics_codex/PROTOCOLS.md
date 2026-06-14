# PROTOCOLS - cybernetics_codex

## Wake Protocol

1. Read `WAKE_CONTEXT.md`.
2. Read `SOUL.md`, then the newest entries in `MEMORY.md`.
3. Run or inspect `make onboard` and `make orient`; treat them as renderers, not authority.
4. Run `python3 scripts/governance/cybernetics_codex_audit.py --json`.
5. Check the live registration paths in `agent.seed.yaml`.

## Closure Claim Protocol

For every loop claim, require:

- real-data evidence, not a demo;
- sense, interpret, constrain, act, and adapt receipts;
- owner surface path;
- runtime DB or log count where applicable;
- timestamp;
- automated verifier command.

If any part is missing, use `PARTIAL`, `UNKNOWN`, or `BLOCKED`. Do not round up.

## Cross-Check Protocol

Mark claims as:

- `SUPPORTED`: runtime receipt and verifier agree.
- `PARTIAL`: activity exists, but at least one closure transition or verifier is missing.
- `CONTRADICTED`: runtime evidence conflicts with prose or rendered orientation.
- `UNKNOWN`: no current evidence found.
- `BLOCKED`: named dependency prevents closure.

## One Wire Protocol

Loops 12 and 13 cannot close unless guardian evidence shows quorum at or above N >= 5 external acted receipts across M >= 3 domains. Internal artifacts, self-reports, benchmark logs, and agent-written prose do not count as archive fitness authority.

## Registration Protocol

Use `scripts/governance/register_cybernetics_codex.py`. It writes through `dharma_swarm.external_agent_registration.register_external_worker`, which in turn calls canonical roaming onboarding. Do not create parallel registration files by hand.
