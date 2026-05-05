# AGENTS.md

This file is the repo-local instruction entrypoint for AI coding agents.
It complements `CLAUDE.md`; it does not replace it.

## Mandatory Read Order

Before making changes, read:

1. `CLAUDE.md`
2. `docs/governance/BUILD_SESSION_ENTRYPOINT.md`
3. `docs/governance/SOVEREIGN_MANIFEST.md`
4. `docs/governance/CANONICAL_DOC_STACK.md`
5. `docs/governance/REPO_GOVERNANCE_AUDIT.md`

If those files disagree on behavior, `CLAUDE.md` wins.
If they disagree on architecture or measured repo state, verify against the filesystem and record drift in `REPO_GOVERNANCE_AUDIT.md`.

## Change Discipline

- Do not add root-level Markdown unless it is an agent instruction file or explicitly approved canon.
- Do not create new routers, bridges, adapters, ledgers, registries, or memory stores before checking the existing substrate table in the build-session entrypoint and audit synthesis.
- Do not treat `reports/generated/**`, `.dharma_psmv_hyperfile_branch*/**`, or `reports/**/state/**` as canonical truth.
- For documentation work, read `docs/AGENTS.md` before editing anything under `docs/`, `reports/`, `specs/`, `foundations/`, or `lodestones/`.
- Do not run live swarm/autonomy or `gitnexus analyze` unless the task explicitly asks for it.

## Verification

Use the repo-specific Python environment when tests are needed:

```bash
/Users/dhyana/dharma_swarm/.venv/bin/python -m pytest
```

For docs-only changes, at minimum run:

```bash
git diff --check
```

Run broader tests only when the doc change touches commands, runtime contracts, CI, or operator procedures.
