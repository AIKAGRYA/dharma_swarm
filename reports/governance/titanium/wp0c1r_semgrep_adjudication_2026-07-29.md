# WP-0C1R — Semgrep pinned strict re-run + typed adjudication (2026-07-29)

**STATUS: DRAFT — PENDING OPERATOR RATIFICATION.** Adjudication authority is
the operator's; this record only prepares the typed disposition table. No
disposition below is final until ratified.

**Finding:** TIT-004 (adjudication half; scanner fail-closed semantics are WP-0C1)
**Base:** current `origin/main` at `2bc461eb201c75445b43fc1ac98b5edfe3539286`
**Scanner:** semgrep 1.168.0 — the ratified toolchain pin (`Makefile:434`
`SEMGREP_PIN ?= 1.168.0`; wrapper default in
`scripts/governance/run_semgrep_with_ca.sh:93`), installed via
`uv pip install "semgrep==1.168.0"`; `semgrep --version` → `1.168.0`;
JSON `version` field → `1.168.0`.
**Command:** `bash scripts/governance/run_semgrep_with_ca.sh --config .semgrep
--error --metrics=off --json` with `DHARMA_SEMGREP_EXPECTED_VERSION=1.168.0`
(the wrapper expands `--config .semgrep` to `.semgrep/dharma-anti-slop.yml` +
`.semgrep/security.yml`, `run_semgrep_with_ca.sh:58-59`) → **exit 1, 21
findings, 7 scan warnings**, 1563 paths scanned.
**Historical baseline:** `reports/governance/titanium/wp0c1r_semgrep_adjudication_2026-07-18.md`
(unmodified by this packet).

## Headline results

1. **The security rule set remains clean.** All rule ids in
   `.semgrep/security.yml` carry the `dharma.security.` prefix
   (`.semgrep/security.yml:6,24,32,46,59,67`); the current scan JSON contains
   **zero** findings with that prefix. The WP-0C1 required scan's premise
   (`make semgrep` runs `security.yml` only, `Makefile:435-436`) is unaffected.
2. **The finding set is path:line-identical to the 2026-07-18 baseline.**
   21 findings: 18 × `dharma.no-unauthorized-dharma-write` + 3 ×
   `dharma.no-new-substrate`, at exactly the same `path:line` coordinates as
   the baseline table. Nothing was resolved and nothing new appeared in the
   rule findings between the two runs.
3. **Rule-id rendering note:** the JSON `check_id`s appear as
   `semgrep.dharma.no-unauthorized-dharma-write` / `semgrep.dharma.no-new-substrate`
   — semgrep prefixes the config directory path (`.semgrep/`) onto the declared
   ids `dharma.no-unauthorized-dharma-write` (`.semgrep/dharma-anti-slop.yml:10`)
   and `dharma.no-new-substrate` (`.semgrep/dharma-anti-slop.yml:54`). Same
   rules; rendering only.
4. **Scan warnings: 7 (baseline had 6).** Six are the same bash partial-parse
   warnings the baseline recorded (`session_start.sh:63`, `gate1_witness.sh:34`,
   `run_pytest_with_repo_env.sh:14`, `worktree_cleanup_2026-06-10.sh:145`,
   `worktree_cleanup_second_pass_2026-06-11.sh:110`,
   `overnight_controller_legacy.sh:275`). One is new:
   `terminal/scripts/golden_diff.sh:83` (bash partial-parse, `terminal/**` is
   owned by `helm-worldclass-terminal-2026-06`). These are parser warnings,
   not rule findings; the Python rules in both configs are unaffected.
5. **Lineage note:** the baseline's base commit
   `1e806bdc272cc61f983f42dd7577e58b39781a25` exists as an object in this
   repository but is **not an ancestor** of current main
   (`git merge-base --is-ancestor 1e806bdc… HEAD` → exit 1; history lineage
   was rewritten between the two runs). The baseline↔current identity above is
   therefore established by exact `path:line` match of every finding, not by
   commit ancestry.

## Typed adjudication table (every current finding)

Disposition vocabulary for this re-run: `RESOLVED_BY:<commit/PR>` ·
`OWNER_DEFERRED:<owning track/authority>:<reason>` ·
`FALSE_POSITIVE:<justification>` · `NEW:<proposed owner-safe disposition>`.
Zero findings qualified for `RESOLVED_BY`, `FALSE_POSITIVE`, or `NEW`; all 21
carry over as `OWNER_DEFERRED` because the preconditions the baseline named
are still unmet on current main:

- `ACTIVE_SURFACE_MANIFEST.yaml` still contains no `palantir` or
  `verifier_ranker` surface declaration (grep on current main → no matches),
  which the rule text requires before allowlisting
  (`.semgrep/dharma-anti-slop.yml:14-17`).
- None of the three `no-new-substrate` files carries a closure-layer role
  header from the Rule 2 vocabulary (`.semgrep/dharma-anti-slop.yml:61-69`);
  their module docstrings (`dharma_swarm/bridge_registry.py:1-15`,
  `dharma_swarm/graph_store.py:1-15`, `dharma_swarm/knowledge_units.py:1-13`)
  declare no role.
- No active track owns any of the finding surfaces
  (`docs/governance/ACTIVE_TRACK.yaml` on current main has no match for
  `scripts/research`, `verifier_ranker`, `palantir_pilot`, `bridge_registry`,
  `graph_store`, or `knowledge_units`), so a drive-by fix or allowlist from
  this packet would fabricate a governance claim the spec forbids
  (plan § WP-0C1R, "Do not add broad ignores, global exclusions, or a new
  baseline merely to make the result green",
  `docs/plans/TITANIUM_GRADE_REPOSITORY_HARDENING_2026-07-10.md:724`).

### Rule `dharma.no-unauthorized-dharma-write` — 18 findings

| # | Path:line (verified 2026-07-29) | Disposition (DRAFT) |
|---|---|---|
| 1 | `dharma_swarm/palantir_pilot_manifest.py:16` | OWNER_DEFERRED:operator (surface admission):defines the pilot's `~/.dharma` path; needs `ACTIVE_SURFACE_MANIFEST.yaml` declaration or `RuntimeStateStore` route |
| 2 | `scripts/governance/palantir_pilot_audit.py:25` | OWNER_DEFERRED:operator (surface admission):same palantir-pilot family |
| 3 | `scripts/governance/register_palantir_pilot.py:39` | OWNER_DEFERRED:operator (surface admission):same palantir-pilot family |
| 4 | `scripts/research/palantir_contribution_packets.py:289` | OWNER_DEFERRED:operator (surface admission):`scripts/research/**` unowned by any active track |
| 5 | `scripts/research/palantir_deep_ingest.py:121` | OWNER_DEFERRED:operator (surface admission):same |
| 6 | `scripts/research/palantir_learning_backlog.py:353` | OWNER_DEFERRED:operator (surface admission):same |
| 7 | `scripts/research/palantir_pilot_curriculum.py:457` | OWNER_DEFERRED:operator (surface admission):same |
| 8 | `scripts/research/palantir_pilot_orientation.py:268` | OWNER_DEFERRED:operator (surface admission):same |
| 9 | `scripts/research/palantir_pilot_query.py:126` | OWNER_DEFERRED:operator (surface admission):same |
| 10 | `scripts/research/palantir_playbook_evals.py:305` | OWNER_DEFERRED:operator (surface admission):same |
| 11 | `scripts/research/palantir_public_source_cards.py:652` | OWNER_DEFERRED:operator (surface admission):same |
| 12 | `scripts/research/palantir_public_source_index.py:207` | OWNER_DEFERRED:operator (surface admission):same |
| 13 | `scripts/research/palantir_query_cookbook.py:297` | OWNER_DEFERRED:operator (surface admission):same |
| 14 | `scripts/research/palantir_source_card_balanced_expand.py:133` | OWNER_DEFERRED:operator (surface admission):same |
| 15 | `scripts/research/palantir_source_card_cleanup.py:340` | OWNER_DEFERRED:operator (surface admission):same |
| 16 | `scripts/research/palantir_source_card_playbooks.py:436` | OWNER_DEFERRED:operator (surface admission):same |
| 17 | `scripts/research/palantir_source_card_quality.py:342` | OWNER_DEFERRED:operator (surface admission):same |
| 18 | `dharma_swarm/verifier_ranker_v0/inventory.py:243` | OWNER_DEFERRED:operator (surface admission):unowned module referencing `~/.dharma`; needs owner declaration or `RuntimeStateStore` route |

One operator decision still resolves 17 of 18 (admit the palantir pilot's
`~/.dharma` slice as a declared surface + allowlist with a rule test, or
direct migration of the family to `RuntimeStateStore` under a research-surface
owner); the 18th (`verifier_ranker_v0`) is the same choice for that module.

### Rule `dharma.no-new-substrate` — 3 findings

| # | Path:line (verified 2026-07-29) | Disposition (DRAFT) |
|---|---|---|
| 19 | `dharma_swarm/bridge_registry.py:215` | OWNER_DEFERRED:memory-kernel consolidation owner:needs a truthful closure-layer role vs `MemoryKernel` (Rule 2 vocabulary) before header/allowlist |
| 20 | `dharma_swarm/graph_store.py:141` | OWNER_DEFERRED:memory-kernel consolidation owner:same |
| 21 | `dharma_swarm/knowledge_units.py:179` | OWNER_DEFERRED:memory-kernel consolidation owner:same |

Classifying core memory substrates is a memory-architecture ownership
decision (CLAUDE.md names `MemoryKernel` as the canonical front door); a
drive-by header claim from a scanner-cleanup packet would be an untruthful
governance assertion.

## Consequences for the campaign

- `make semgrep-strict` remains **red on current main** (exit 1, 21 findings)
  until the operator ratifies and executes resolutions for the two deferral
  groups; per plan § WP-0C1R, OWNER_DEFERRED prevents Phase 0 closure.
- `make semgrep` (required scan, `security.yml` only, `Makefile:435-436`)
  keeps its clean-premise: zero security findings on current main.
- The historical 2026-07-18 baseline is **not promoted** to a current clean
  result; this re-run confirms the deferral set is unchanged, not resolved.

## Reproduction

```bash
uv pip install -p <venv-python> "semgrep==1.168.0"   # or: pip install "semgrep==1.168.0"
DHARMA_SEMGREP_EXPECTED_VERSION=1.168.0 \
  bash scripts/governance/run_semgrep_with_ca.sh --config .semgrep --error --metrics=off --json
# exit 1; 21 results: dharma.no-unauthorized-dharma-write (18) and
# dharma.no-new-substrate (3); zero results from .semgrep/security.yml
```

Environment caveat (proxied runners only): behind an intercepting egress
proxy, semgrep's own network version-check can hang (`semgrep --version`
observed at ~99 s), tripping the wrapper's 30 s version probe
(`run_semgrep_with_ca.sh:159`) with `SEMGREP_VERSION_TIMEOUT`. Export
`SEMGREP_ENABLE_VERSION_CHECK=0` (semgrep's supported switch) before the run;
with it, `semgrep --version` completes in ~1.4 s. This is a runner-environment
caveat, not a repo or wrapper defect.

**Typed verdict for WP-0C1R (this re-run):** `BLOCKED_OPERATOR` — the current
finding set is fully re-adjudicated in draft form; resolution requires the
operator decisions enumerated above. This record makes no `PASS` claim for
`make semgrep-strict` and awaits operator ratification.
