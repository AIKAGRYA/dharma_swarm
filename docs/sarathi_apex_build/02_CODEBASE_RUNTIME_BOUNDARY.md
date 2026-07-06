# 02 — Codebase / Runtime Boundary

**Custody: doctrine, VERIFIED against live layout 2026-07-06.**

The split is correct. The disease is *drift across* the split, not the split
itself.

## The three homes

| Home | Is | Holds | In git? |
|---|---|---|---|
| `/Users/dhyana/dharma_swarm` | source code | modules, tests, schemas, docs, CLI/API, versioned logic | YES |
| `/Users/dhyana/.dharma` | mutable runtime | identities, state, ledgers, inboxes, heartbeats, receipts, leases | NO |
| `/Users/dhyana/.hermes/hermes-agent` | third-party product | NousResearch Hermes Agent (35 top-level dirs) + its own runtime | NO (side ecosystem) |

One sentence: **code integrity lives in git; mutable runtime state lives under
`~/.dharma`; Hermes is a separate product we benchmark against, not our lineage.**

## Why the split is right

- Source is reviewable, testable, diffable, and reproducible only when it is in
  git. Runtime state is per-machine, high-churn, and often secrets-adjacent —
  committing it corrupts history and leaks.
- A runtime wrapper (e.g. a launchd/tmux shim) MAY live under `~/.dharma`, but
  the real implementation it calls MUST live in the repo (constraint #11).

## The drift (what actually goes wrong)

1. **Source-like scripts living only in runtime.** A `.py` with real logic under
   `~/.dharma/agents/<name>/...` that has no repo owner. Fix: repo owns logic;
   `~/.dharma` gets a thin `from dharma_swarm... import main` shim.
2. **Multiple identity homes.** Live counts: `~/.dharma/agents` (67),
   `~/.dharma/ginko/agents` (52, legacy), `dharma_swarm/docs/agents` (11, repo
   docs), `~/.dharma/external_agents` (26). Four homes = four truths.
3. **Hyphen/underscore duplicates.** `hermes-m5` vs `hermes_m5`, composer
   variants. Same seat, two slugs, two state files.
4. **Runtime state without a repo-tracked map entry.** A live surface under
   `~/.dharma` that nothing in git declares. `ACTIVE_SURFACE_MANIFEST.yaml` is
   the repo-side registry that is supposed to close this gap.
5. **"Alive" claims from identity docs.** A `SOUL.md` / `identity.json` existing
   is NOT liveness. Liveness = a fresh service heartbeat or wake receipt. Live
   proof today: 17 registered, 0 service_alive.

## The rule going forward

Every new artifact must be classified as exactly one of:

```text
code     -> dharma_swarm/ (git)
runtime  -> ~/.dharma/    (not git; must have a repo map entry)
doc      -> docs/         (git)
receipt  -> reports/ or ~/.dharma; commit only if explicitly curated
archive  -> compost; named as such
```

If a thing is "code that happens to run from `~/.dharma`", it is code: put the
logic in `dharma_swarm/holon_system/...` and leave a shim in `~/.dharma`.

## Boundary verdict

Split = CORRECT. Enforcement = PARTIAL. The `holon_system/` facade package
(added this pass) is the repo-side home so runtime shims finally have something
canonical to import. The remaining drift (identity homes, hyphen dupes,
`holon/` fork) is tracked in `07_BACKLOG.md` and gated by `sprawl_guard.py`.
