# WP-0C1R — Ratified dispositions and strict-scan closure (2026-08-02)

**STATUS: RATIFIED AND EXECUTED — pending human merge of the carrying PR.**
The operator ratified the two disposition decisions prepared by the
2026-07-29 draft adjudication
(`reports/governance/titanium/wp0c1r_semgrep_adjudication_2026-07-29.md`):
decision **A1** for the 18 `dharma.no-unauthorized-dharma-write` findings and
decision **B1** for the 3 `dharma.no-new-substrate` findings, in the operator
session of 2026-08-02 ("F1 approved / C1R approved"). The human merge of the
PR carrying this record is the durable signature of that ratification, per the
campaign's standing approval mechanism (`approval.before_merge`).

**Finding:** TIT-004 (adjudication half; scanner fail-closed semantics are WP-0C1)
**Base:** `origin/main` at `d664c014` lineage (see carrying PR for exact base)
**Scanner:** semgrep 1.168.0 (ratified pin; `Makefile` `SEMGREP_PIN`)
**Command:** `DHARMA_SEMGREP_EXPECTED_VERSION=1.168.0 bash scripts/governance/run_semgrep_with_ca.sh --config .semgrep --error --metrics=off`

## Result after execution

**Exit 0 — `Ran 10 rules on 1577 files: 0 findings.`** The strict scan is
green for the first time since the 2026-07-18 baseline. The required
security-only scan (`make semgrep`, `.semgrep/security.yml`) was already clean
and is unchanged.

## Executed dispositions

### Decision A1 — 18 × `dharma.no-unauthorized-dharma-write` → RESOLVED_BY:surface-declaration

Per the rule's own documented procedure (`.semgrep/dharma-anti-slop.yml`
Rule 1 message; `docs/governance/ANTI_SLOP_RULES.md` § "Rule 1"):

1. The Palantir research-pilot family (17 files) and
   `dharma_swarm/verifier_ranker_v0/inventory.py` are declared as
   `research_state_participants` in `ACTIVE_SURFACE_MANIFEST.yaml`
   (participants in the canonical state_dir slices they read/write; no new
   slice minted; local-only research artifacts, never committed).
2. Exactly those 18 files — no globs — were added to Rule 1's
   `paths.exclude` with the ratification cited inline.
3. The contract test
   `tests/test_semgrep_wrapper.py::test_rule1_research_excludes_are_declared_manifest_participants`
   pins allowlist ⊆ declaration equivalence so neither can drift alone.

### Decision B1 — 3 × `dharma.no-new-substrate` → RESOLVED_BY:role-header

Per Rule 2's documented options (`.semgrep/dharma-anti-slop.yml` Rule 2
message; role vocabulary in `docs/governance/ANTI_SLOP_RULES.md`):

1. `dharma_swarm/bridge_registry.py`, `dharma_swarm/graph_store.py`, and
   `dharma_swarm/knowledge_units.py` each carry a `closure-layer-role: exempt`
   file-header declaring them subordinate adapters/projections under the
   MemoryKernel doctrine (`CLAUDE.md`: "MemoryKernel — canonical front door
   ... legacy stores are subordinate adapters and projections"). `exempt` is
   the truthful vocabulary token: they are neither read-only views, caches,
   nor scheduled-removal mirrors; consolidation is future memory-architecture
   work outside this campaign.
2. Exactly those 3 files were added to Rule 2's `paths.exclude` with the
   ratification cited inline.
3. The contract tests
   `tests/test_semgrep_wrapper.py::test_rule2_excludes_carry_closure_layer_role_headers`
   and `::test_anti_slop_allowlists_contain_no_globs` pin header presence and
   forbid glob widening (the plan's "no broad ignores" constraint,
   `docs/plans/TITANIUM_GRADE_REPOSITORY_HARDENING_2026-07-10.md:724`).

## Boundary notes

- The WP-0C1R spec's allowed-files clause admits "source files containing
  findings" and narrow proof tests, and admits rule/config edits for
  demonstrated false positives. These dispositions are not false-positive
  claims: they follow the rules' own documented resolution procedure
  (declare-then-allowlist / role-then-allowlist), executed only after the
  operator's ratification. That distinction is disclosed here rather than
  reinterpreted.
- No finding was fixed by rewriting runtime behavior; the 18 research files
  and 3 substrate modules are byte-identical except the three role headers.
- The scanner wrapper, required-scan target, and governance orchestration
  were not touched (WP-0C1 owns them).
- Historical records (2026-07-18 baseline, 2026-07-29 draft) are preserved
  unmodified; this record supersedes their DRAFT status, not their content.

## Reproduction

```bash
DHARMA_SEMGREP_EXPECTED_VERSION=1.168.0 \
  bash scripts/governance/run_semgrep_with_ca.sh --config .semgrep --error --metrics=off
# expect: exit 0, "Ran 10 rules on ... files: 0 findings."
python3 -m pytest -q tests/test_semgrep_wrapper.py
```
