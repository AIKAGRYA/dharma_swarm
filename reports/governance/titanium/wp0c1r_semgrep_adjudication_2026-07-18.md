# WP-0C1R — Semgrep dynamic-baseline adjudication (2026-07-18)

**Finding:** TIT-004 (adjudication half; scanner fail-closed semantics are WP-0C1)
**Base:** clean merged `origin/main` at `1e806bdc272cc61f983f42dd7577e58b39781a25`
**Scanner:** semgrep 1.168.0 (the ratified toolchain pin), installed via
`PYTHONNOUSERSITE=1 python3 -m pip install --break-system-packages --ignore-installed PyJWT "semgrep==1.168.0"`
**Command:** `bash scripts/governance/run_semgrep_with_ca.sh --config .semgrep --error --metrics=off --json`
(the wrapper expands `--config .semgrep` to `.semgrep/dharma-anti-slop.yml` + `.semgrep/security.yml`) → exit 1, 21 findings, 6 scan warnings.
**Host:** Linux x86_64, Python 3.11.15.

## Headline results

1. **The security rule set is clean.** `.semgrep/security.yml` produced **zero
   findings** on the dynamic baseline. The "3 shell=True + 1 eval" pre-existing
   findings referenced by the `Makefile` `semgrep` target comment are no longer
   present on merged main; that comment is stale relative to this measurement.
2. **All 21 findings come from `.semgrep/dharma-anti-slop.yml`** (in-house
   governance rules, both WARNING severity by design — the rule text itself
   records that the allowlist is incomplete and tightening is future work).
3. **The 6 scan errors are semgrep bash-parser syntax warnings** on shell
   scripts (`session_start.sh:63`, `gate1_witness.sh:34`,
   `run_pytest_with_repo_env.sh:14`, `worktree_cleanup_2026-06-10.sh:145`,
   `worktree_cleanup_second_pass_2026-06-11.sh:110`,
   `overnight_controller_legacy.sh:275`), not rule findings; the Python rules
   in both configs are unaffected.

## Adjudication table (every finding, per spec § WP-0C1R)

Verdict vocabulary: `FIXED` / `FALSE_POSITIVE` / `OWNER_DEFERRED` (a typed
deferral with owner + reason; per spec it prevents Phase 0 closure until
resolved).

### Rule `dharma.no-unauthorized-dharma-write` — 18 findings, all OWNER_DEFERRED

The rule's own sanctioned remedies are (a) route through `RuntimeStateStore`,
or (b) add the file to the rule allowlist AFTER declaring the owned surface in
`ACTIVE_SURFACE_MANIFEST.yaml` (rule text, `.semgrep/dharma-anti-slop.yml:10-17`).
`ACTIVE_SURFACE_MANIFEST.yaml` contains no palantir surface declaration
(grep `palantir` → no matches at base), and that manifest is not in WP-0C1R's
allowed files — declaring new owned surfaces is an operator/governance act,
not a scanner cleanup. Allowlisting without the declaration is exactly the
"broad ignore to make the result green" the spec forbids.

| Path:line | Family | Owner able to resolve | Deferral reason |
|---|---|---|---|
| `dharma_swarm/palantir_pilot_manifest.py:16` | palantir pilot | operator (surface admission) | defines `DEFAULT_DHARMA_HOME` for the pilot manifest; needs surface declaration or RuntimeStateStore route |
| `scripts/governance/palantir_pilot_audit.py:25` | palantir pilot | operator | same family |
| `scripts/governance/register_palantir_pilot.py:39` | palantir pilot | operator | same family |
| `scripts/research/palantir_contribution_packets.py:289` | palantir research | operator | `scripts/research/**` is unowned by any active track |
| `scripts/research/palantir_deep_ingest.py:121` | palantir research | operator | same |
| `scripts/research/palantir_learning_backlog.py:353` | palantir research | operator | same |
| `scripts/research/palantir_pilot_curriculum.py:457` | palantir research | operator | same |
| `scripts/research/palantir_pilot_orientation.py:268` | palantir research | operator | same |
| `scripts/research/palantir_pilot_query.py:126` | palantir research | operator | same |
| `scripts/research/palantir_playbook_evals.py:305` | palantir research | operator | same |
| `scripts/research/palantir_public_source_cards.py:652` | palantir research | operator | same |
| `scripts/research/palantir_public_source_index.py:207` | palantir research | operator | same |
| `scripts/research/palantir_query_cookbook.py:297` | palantir research | operator | same |
| `scripts/research/palantir_source_card_balanced_expand.py:133` | palantir research | operator | same |
| `scripts/research/palantir_source_card_cleanup.py:340` | palantir research | operator | same |
| `scripts/research/palantir_source_card_playbooks.py:436` | palantir research | operator | same |
| `scripts/research/palantir_source_card_quality.py:342` | palantir research | operator | same |
| `dharma_swarm/verifier_ranker_v0/inventory.py:243` | verifier ranker | operator | unowned module referencing `~/.dharma`; needs owner declaration or RuntimeStateStore route |

One decision resolves 17 of 18: either admit the palantir pilot's `~/.dharma`
slice as a declared surface (then allowlist those files with a rule test), or
direct migration of the family to `RuntimeStateStore` under a research-surface
owner. The 18th (`verifier_ranker_v0`) is the same choice for that module.

### Rule `dharma.no-new-substrate` — 3 findings, all OWNER_DEFERRED

The rule requires either wrapping the store in an existing canonical store or
declaring a closure-layer role (`canonical-store | derived-view | plugin-sink |
cache | legacy-mirror | migration-mirror | exempt`) in a file-header comment
(`.semgrep/dharma-anti-slop.yml:47-59`). Classifying core memory substrates is
a memory-architecture ownership decision — CLAUDE.md names `MemoryKernel` as
the canonical front door with legacy stores as "subordinate sources, adapters,
projections, or promotion feeds" — and none of these three files carries a
role today. A drive-by header claim from a scanner-cleanup packet would be an
untruthful governance assertion.

| Path:line | Store | Owner able to resolve | Deferral reason |
|---|---|---|---|
| `dharma_swarm/bridge_registry.py:215` | bridges.db (SQLite) | memory-kernel consolidation owner | needs truthful closure-layer role vs MemoryKernel |
| `dharma_swarm/graph_store.py:141` | four-graph storage | memory-kernel consolidation owner | same |
| `dharma_swarm/knowledge_units.py:179` | KnowledgeStore (SQLite) | memory-kernel consolidation owner | same |

## Consequences for the campaign

- `make semgrep-strict` remains **red on merged main** until the operator
  resolves the two deferral groups above; per spec, OWNER_DEFERRED prevents
  Phase 0 closure. WP-0C1 ("preserve WP-0C1R's clean result") inherits this
  blocker for its finding-set premise, but its fail-closed semantics work
  (missing scanner → nonzero; stdin/timeout hygiene) does not depend on the
  finding set being empty and can proceed.
- No code fix ships in this packet because zero findings were mechanically
  fixable inside WP-0C1R's allowed files without fabricating governance
  claims; this record is the complete adjudication the spec requires.

## Reproduction

```bash
python3 -m pip install --break-system-packages --ignore-installed PyJWT "semgrep==1.168.0"
bash scripts/governance/run_semgrep_with_ca.sh --config .semgrep --error --metrics=off --json
# exit 1; 21 results, ids dharma.no-unauthorized-dharma-write (18) and
# dharma.no-new-substrate (3); zero results from .semgrep/security.yml
```

**Typed verdict for WP-0C1R:** `BLOCKED_OPERATOR` (adjudication complete;
resolution requires the operator decisions enumerated above). This record
makes no `PASS` claim for `make semgrep-strict`.
