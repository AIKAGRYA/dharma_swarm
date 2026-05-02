# Inquiry Chain v3 Integration Addendum

Status: INTEGRATED ADDENDUM
Date: 2026-05-02
Branch checked: `feat/inquiry-chain-phase1`
Source plan: `~/.claude/plans/now-reserach-this-and-jaunty-owl.md`

## Verdict

Plan v3 is workable, but it should not be executed verbatim.

It integrates with the ontology-native inquiry chain only if Track A and Track B are interpreted as parts of one canonical memory substrate. The goal is not another prompt artifact plus another set of manual skills. The goal is to make Signal, Question, Claim, Evidence, and Doctrine the typed memory projection for inquiry, with TelicSeam and OntologyHub as the current write path.

The highest-leverage correction is this:

```text
memory tools -> evidence manifest -> ontology/memory admission -> Codex prompt
manual notes -> TelicSeam inquiry writers -> OntologyHub -> brief/audit projections
```

Do not let Track A become "use every memory tool until the story feels true." Do not let Track B create another memory surface outside the ontology write path.

## Verified Anchors

- Branch is `feat/inquiry-chain-phase1`.
- Phase 1.1 schema commit exists: `5327c3b feat(ontology): inquiry chain types`.
- Brief canonicalization commit exists: `7969498 feat(brief): canonicalize ontology-native insight brief`.
- Chetana HIGH self-patch commit exists: `9446e13 fix(causal-ledger,r-repair): patches from Codex 5.5 cross-check (HIGH)`.
- `Signal`, `Question`, `Evidence`, `Claim`, and `Doctrine` are registered in `dharma_swarm/ontology.py`.
- `AgentIdentity.is_principal` exists in `dharma_swarm/ontology.py`.
- `TelicSeam` is the non-blocking runtime write seam in `dharma_swarm/telic_seam.py`.
- `OntologyActionGateway` is the fail-closed product-flow gateway in `dharma_swarm/ontology_action_gateway.py`.
- The canonical brief writer is `dharma_swarm.insight_brief`; the production start is documented as 2026-05-02 at 04:30 WITA in `docs/plans/ontology-native-flow-001-insight-brief.md`.
- The single-memory direction is documented in `docs/architecture/MEMORY_SYSTEM_FUSION_MAP_2026-05-01.md`: introduce `MemoryKernel`, make vector/graph/palace surfaces projections, and add `PriorRetrievalController`.

## Required Corrections Before Execution

### 1. Track A Is An Admission Sweep, Not A Tool Census

The "ALL memory tools" sweep should produce one scratch evidence manifest, not a pile of equally authoritative memories.

Use this schema for `~/.dharma/codex/alignment_sweep_2026-05-02.md`:

```text
claim_id:
claim:
source_uri:
source_line:
tool_or_store:
pramana_tag: G|B|P|I|S
confidence:
freshness:
contradicts:
admit_to_prompt: yes|no
reason:
```

Every prompt claim must be admitted through this manifest. If two stores disagree, the prompt should cite the disagreement instead of smoothing it away. This is the same discipline the future `MemoryKernel` should enforce with truth states and contradiction edges.

### 2. Track A Must Ask Codex For Memory-System Integration Explicitly

Add one fifth design question to the Codex power prompt:

```text
How should R_repair, gate_calibration, causal_ledger, inquiry-chain objects,
and future MemoryKernel atoms be reconciled into one memory protocol rather
than five semi-parallel truth stores?
```

This matters because the current four anti-correlation asks are local fixes. The global risk is that each fix creates another trusted metric file with its own lifecycle. Codex should be asked to name the unifying contract.

### 3. Track B.1 Must Use Actual Schema States

The pasted plan says `status='asserted'` for open claims. The current `Claim` schema uses `lifecycle_state` enum values:

```text
proposed, accepted, deprecated
```

So `record_claim()` must write `lifecycle_state="proposed"` and the brief must render proposed claims, not asserted claims.

`Question.lifecycle_state` is correct as:

```text
open, answered, abandoned
```

`Doctrine` also needs correction. The current schema does not include `signer_agent_id`. Principal authority should be checked against an `AgentIdentity` row before creating the Doctrine, but the Doctrine row itself should use existing fields:

```text
doctrine_id
text
lifecycle_state="signed"
signed_by_human_at
kernel_signature
version
```

If signer provenance is required, add it through link metadata or extend the schema in a separate commit. Do not silently write a non-schema property and assume it is governed.

### 4. Track B.1 Should Add One Inquiry Helper

Do not copy-paste five full `create_object` blocks. Add one private helper inside `TelicSeam`:

```python
def _record_inquiry_object(
    self,
    type_name: str,
    properties: dict[str, Any],
    *,
    created_by: str,
    links: list[tuple[str, str, str]] | None = None,
) -> str | None:
    ...
```

Each public `record_signal`, `record_question`, `record_claim`, `record_evidence`, and `record_doctrine` remains best-effort and non-blocking, but the invariant is centralized:

- create typed object
- create any defined inquiry links
- flush once
- debug-log and return `None` on failure

This keeps TelicSeam consistent with its existing runtime behavior while avoiding five divergent mini-writers.

### 5. Track B.2 Must Pass Registry Context Into Rendering

`InsightBriefBuilder._render_markdown()` is currently a static method that receives only `today`, `artifact_id`, `witness_id`, and cited Outcome claims.

Do not put `registry.get_objects_by_type(...)` inside that static method unless the signature changes. Cleaner contract:

```text
compose()
  -> collect outcomes
  -> collect open inquiry summaries from gateway.registry
  -> call _render_markdown(..., open_claims=..., open_questions=...)
```

Brief rendering rules:

- render `Claim.lifecycle_state == "proposed"` with `confidence < 1.0`
- render `Question.lifecycle_state == "open"`
- count Evidence using `claim_has_evidence` links first, then `evidence_refs` as fallback
- cap each section at 5
- skip empty sections

This keeps the brief as a projection over ontology state, not a second memory query engine.

### 6. Track B.3 Should Prefer Registry Traversal Over Raw SQL JSON

`OntologyHub` stores object properties as JSON text in the `objects` table. The plan says "three SQL queries," but raw `json_extract(...)` assumes SQLite JSON1 behavior and bakes schema details into the audit layer.

Preferred implementation:

- load through `get_shared_registry()` or `OntologyHub.load_into_registry()`
- use registry objects and links for correctness
- keep SQL only for simple row counts or time-window prefiltering

If raw SQL is used, tests must prove it works on the local SQLite build and must not assume every object property is promoted to a column.

### 7. Track B.3 Must Verify `dgc_cli.py` Reality Before Adding Verbs

Current `dgc_cli.py` in this branch is a 534-line argparse entrypoint with only the visible `status` parser in `main()`. The installed script points to `dharma_swarm.dgc_cli:main` via `pyproject.toml`.

So `dgc audit gates --days 7` is safe to add here, but do it as a real parser branch with a small handler:

```text
audit
  gates --days N
```

Tests should dispatch through `main(["audit", "gates", "--days", "7"])`, not only call `audit_queries` directly.

### 8. Track B.4 Must Be A Manual Projection, Not A New Skill Memory

`codex_skills/` already exists as an untracked directory with `terminal-guardian`. The two new skill directories do not collide, but they must be thin adapters:

```text
observe_signal -> TelicSeam.record_signal
assert_claim   -> TelicSeam.record_claim
```

They must not write JSONL, markdown, or their own state file. The DB row is the memory. The skill output is only the object id and enough CLI text for a human to continue.

## Sequencing Change

Use this execution order:

1. Patch the plan with this addendum reference.
2. Build B.1 first if implementation starts today, because B.2 through B.4 depend on the exact writer contract.
3. Draft Track A after B.1 if the Codex prompt wants to cite final writer APIs. Draft Track A before B.1 only if it remains design-only and does not cite unbuilt methods as real.
4. Build B.2, then B.3, then B.4.
5. Send the Codex power prompt only after the alignment manifest is written and contradictions are explicit.

The original "Track A first" order is acceptable only for a pure design request. It is not acceptable if the prompt claims Phase 1.2 APIs already exist.

## Reversibility Correction

Do not present `git reset --hard 5327c3b` as a normal rollback in this worktree. The worktree has unrelated tracked and untracked changes. The normal rollback path is:

```text
git revert <phase_commit_sha>
```

Only use `git reset --hard` in a disposable or freshly recreated worktree after explicitly saving unrelated work. This is not pedantry; otherwise the rollback plan can destroy user or other-agent state.

## Acceptance Additions

Add these checks to v3 acceptance:

- B.1 tests prove `record_claim()` writes `lifecycle_state="proposed"`.
- B.1 tests prove `record_doctrine()` refuses a non-principal signer.
- B.1 tests prove Doctrine creation uses only schema-valid properties unless a schema-extension commit lands first.
- B.2 tests prove the brief skips inquiry sections when there are no open items.
- B.2 tests prove Evidence counts come from links when present.
- B.3 tests dispatch through `dgc_cli.main(["audit", "gates", "--days", "7"])`.
- B.4 tests or smoke checks prove manual skills do not create sidecar state.
- No implementation commit stages unrelated dirty files.

## What Not To Add

- Do not add another durable prompt-log or prompt-memory store for Track A.
- Do not make Chroma, contextplus, claude-mem, or Chetana authoritative for prompt claims. They are sources into the evidence manifest.
- Do not introduce a new "inquiry memory" module parallel to OntologyHub.
- Do not create Cause or Movement runtime rows as part of this phase.
- Do not let Doctrine signing become automatic. It is principal-only and manual until the authority model has more data.

## Bottom Line

This v3 plan integrates cleanly if it is treated as an ontology-native memory projection plan. It becomes AI theater if it is treated as a ritual sweep across many memory tools plus a set of skill wrappers.

The next concrete build should be B.1 with the schema corrections above.
