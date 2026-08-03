# WP-0C1R — Ratified dispositions and strict-scan closure (2026-08-02)

> **Amended 2026-08-03 and again 2026-08-04**: the execution *mechanism* items
> below were review-hardened after ratification, and two claims made in that
> hardening are corrected. Later amendments win: read
> "Amendment 2026-08-04" (last section) first — it corrects the
> "Amendment 2026-08-03" claim that a new Store/Ledger/Registry in the ratified
> files "is still caught", and records that Rule 2 had no JSONL detector at
> all until 2026-08-04. The A1/B1 dispositions themselves are unchanged.

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

## Amendment 2026-08-03 — review-hardened execution mechanism (commit 29b12a560)

The A1/B1 dispositions are unchanged. After six decorrelated review findings
on the carrying PR (#1202: Devin, Greptile, Codex — one-directional lockstep,
whole-file Rule 2 exemptions, substring role check, prose-only slice
declaration), the execution mechanism recorded above was tightened in commit
`29b12a560`. Where this amendment conflicts with the "executed via" items
above, this amendment is authoritative:

- **Rule 1 (supersedes Decision A1 items 2–3 in part)**: the 18 files remain
  file-exact entries in Rule 1's `paths.exclude`. The contract test is now
  `tests/test_semgrep_wrapper.py::test_rule1_lockstep_is_bidirectional`: in
  addition to declared ⊆ excludes, it fails on any exclude entry lacking a
  manifest declaration (excludes − declared − pinned canonical/operational
  set must be empty). `research_state_participants` gained machine-readable
  per-group `files:` + `state_slices:` (a prose-only slice list is not a
  declaration).
- **Rule 2 (supersedes Decision B1 items 2–3)**: the 3 files were REMOVED
  from Rule 2's `paths.exclude` (only `dharma_swarm/runtime_state.py`
  remains). The exemption is class-scoped `pattern-not` clauses —
  `BridgeRegistry`, `SQLiteGraphStore`, `KnowledgeStore` — so a NEW
  Store/Ledger/Registry in the same files is still caught. The contract test
  is now `::test_rule2_exemptions_are_class_scoped_and_role_headed`: a
  structural `# closure-layer-role: <role>` comment line with the role from
  the closed vocabulary, exactly the ratified class set, and no same-named
  class elsewhere may open SQLite (this check surfaced
  `dharma_swarm/engine/knowledge_store.py`'s in-memory `KnowledgeStore`,
  verified sqlite-free — the collision is inert and now guarded).
- `::test_anti_slop_allowlists_contain_no_globs` retains its name and role.
- Verification on `29b12a560`: strict replay `Ran 10 rules on 1577 files:
  0 findings` (semgrep 1.168.0 pin, exit 0); pytest 13 passed / 1
  pre-existing host-conditional skip; negative controls each proven then
  reverted — (A) undeclared Rule 1 exclude → contract FAILs, (B) blanked
  role value → contract FAILs, (C) `SmuggledStore` appended to
  `graph_store.py` → strict scan FINDS `dharma.no-new-substrate`.

## Amendment 2026-08-04 — Rule 2 had no JSONL detector, and the 2026-08-03 claim above is corrected

The A1/B1 dispositions are still unchanged. Two statements merged on `main`
are corrected here; nothing above is rewritten.

### Correction 1 — "still caught" was a universal claim the rule cannot honor

The Amendment 2026-08-03 bullet "Rule 2" states, verbatim:

> The exemption is class-scoped `pattern-not` clauses — `BridgeRegistry`,
> `SQLiteGraphStore`, `KnowledgeStore` — so a NEW Store/Ledger/Registry in the
> same files is still caught.

**False as written, in two ways.**

1. It is a claim about *any* new substrate, but Rule 2's detector only ever
   matched four SQLite assignment shapes. A new Store/Ledger/Registry that
   appends JSONL was never caught — anywhere, not only "in the same files".
2. "Class-scoped" is precisely **name**-scoped. Verified against semgrep
   1.168.0: a `class X: ...` pattern also matches `class X(Base): ...`, so a
   second, differently-based class re-using a ratified name inherits the
   exemption. The 2026-08-03 record notes the
   `dharma_swarm/engine/knowledge_store.py` collision was "verified
   sqlite-free — the collision is inert and now guarded"; the guard was a
   source-text grep in a contract test, not the scanner.

The narrow claim that survives: a **differently-named** new substrate class
added to one of the three ratified files is still caught, for the shapes the
detector covers. That is now proven by running the scanner
(`test_synthetic_new_substrate_is_caught_in_a_ratified_file`), not asserted.

### The receipt

Rule 2's message has promised, since `3ff53240e` (2026-04-26), that it catches
a Store/Ledger/Registry that "opens its own SQLite **or appends its own
JSONL**". The rule carried **zero** JSONL patterns. Two ledgers added after
the rule existed (`e1aacc0fc`, 2026-07-03) prove the miss:

```bash
# rule file byte-identical at f3eb5b397 (WP-0C1R merge) and f2ffb4390 (main)
DHARMA_SEMGREP_EXPECTED_VERSION=1.168.0 bash scripts/governance/run_semgrep_with_ca.sh \
  --config .semgrep/dharma-anti-slop.yml --metrics=off \
  dharma_swarm/forge_v1/forge_v2/receipts.py dharma_swarm/forge_v1/tracking.py
# => Ran 4 rules on 2 files: 0 findings.
```

`receipts.py:69` defines `class Ledger` whose own docstring reads "Append-only
JSONL score store"; `tracking.py:23` defines `class RunLedger` writing
`~/.dharma/forge_v1/runs.jsonl`. Both are exactly what Rule 2's message
describes, and the strict scan reported them as clean.

Why the WP-0C1R contract tests could not have caught this: they parse YAML,
grep class names, and search source text. `test_rule2_exemptions_are_class_scoped_and_role_headed`
proves the config's shape; only a scanner run proves the scanner's behavior.

### What changed

- Rule 2 now detects append-mode file handles opened in a method body —
  `open(p, "a")`, `open(p, mode="a")`, `p.open("a")`, `p.open(mode="a")`, and
  the `with ... as f:` form of each (modes a/ab/at/a+/ab+/at+) — plus the
  SQLite forms it previously missed: local variables, bare calls, `async def`,
  and `with sqlite3.connect(...) as conn:`. Inheriting a ratified exempt class
  is also a finding.
- Rule 2's message now states, literally, both what it catches and what it
  does not (wrapper/factory-opened substrates, aliased builtins, variable
  modes, non-sqlite drivers, non-`*Store` names, class-body append handles,
  and the same-name collision).
- New companion rule `dharma.no-new-substrate-exempt-name-collision` makes the
  collision guard behavioral. It fires only when a colliding class *also*
  opens a substrate, so the sqlite-free `KnowledgeStore(Protocol)` in
  `dharma_swarm/engine/knowledge_store.py` correctly stays silent.
- `.semgrep/tests/test_no_new_substrate.py` (behavioral fixture, restored and
  extended from `71097bd048`) + `tests/test_semgrep_rule2_behavior.py` run
  semgrep against the real rule file and assert the exact set of finding
  lines. Named gaps are `todoruleid`-annotated and asserted to stay silent, so
  closing one fails the suite instead of passing quietly. Absent scanner =
  named SKIP, never a green pass.
- The strict scan now loads **11 rules**, not 10. The required scan
  (`make semgrep`, `.semgrep/security.yml` only) and `governance-all` are
  untouched and still clean.

### Newly surfaced — OWNER_DEFERRED, awaiting their own adjudication

The broadened detector surfaces **17 findings**, all
`dharma.no-new-substrate`, all manually verified as true positives (real
`*Store`/`*Ledger`/`*Registry` classes opening their own SQLite or appending
their own JSONL). **None was allowlisted, exempted, or silenced.** They are
NOT covered by decision B1 and require the same route WP-0C1R used —
declare-then-adjudicate, operator-ratified:

| File:line | Class | Substrate |
|---|---|---|
| `dharma_swarm/amiros.py:153` | `AMIROSRegistry` | JSONL append |
| `dharma_swarm/cron_job_runtime.py:62` | `CronJobRuntimeStore` | JSONL append |
| `dharma_swarm/economic_agent.py:132` | `EconomicLedger` | JSONL append |
| `dharma_swarm/engine/conversation_memory.py:176` | `ConversationMemoryStore` | SQLite (context manager) |
| `dharma_swarm/engine/retrieval_feedback.py:250` | `RetrievalFeedbackStore` | SQLite (context manager) |
| `dharma_swarm/epistemic_telemetry.py:289` | `EpistemicTelemetryStore` | JSONL append |
| `dharma_swarm/forge_v1/forge_v2/receipts.py:69` | `Ledger` | JSONL append |
| `dharma_swarm/forge_v1/tracking.py:23` | `RunLedger` | JSONL append |
| `dharma_swarm/observability.py:114` | `LocalTraceStore` | JSONL append |
| `dharma_swarm/operator_core/session_store.py:57` | `SessionStore` | JSONL append |
| `dharma_swarm/rea_runtime.py:118` | `TemporalRunStore` | JSONL append |
| `dharma_swarm/routing_memory.py:68` | `RoutingMemoryStore` | SQLite (local variable) |
| `dharma_swarm/session_ledger.py:67` | `SessionLedger` | JSONL append |
| `dharma_swarm/telemetry_plane.py:619` | `TelemetryPlaneStore` | aiosqlite (bare call) |
| `dharma_swarm/telos_gates.py:122` | `GateRegistry` | JSONL append |
| `dharma_swarm/tui/engine/session_store.py:44` | `SessionStore` | JSONL append |
| `dharma_swarm/vector_store.py:214` | `VectorStore` | SQLite (local variable) |

Consequence, stated rather than hidden: the strict scan
(`make semgrep-strict`, and the `.github/workflows/semgrep.yml` "Strict gate"
when it runs **without** a baseline — i.e. the Monday drift cron) reports
these 17 and exits nonzero until they are adjudicated. On `pull_request` and
`push` the gate passes `--baseline-commit`, so pre-existing findings are
filtered and the gate stays green — measured, not assumed:

```
run_semgrep_with_ca.sh --config .semgrep --error --baseline-commit f2ffb4390
# => Ran 11 rules on 0 files: 0 findings.   exit 0
```

The **required** scan (`make semgrep`, security ruleset only) is unaffected:
`Ran 6 rules on 1453 files: 0 findings`, exit 0 — nothing in `governance-all`
starts failing.

### Correction 2 — the work-packet JSON's stale reference stands, and why

The 2026-08-03 amendment's carrying work is described as having verified the
packet JSON free of stale mechanism references. It is not:
`reports/agentops/work_packets/titanium-WP-0C1R-ratified-dispositions.json:6`
still says Rule 2 should "allowlist exactly those files in Rule 2", which the
2026-08-03 amendment reversed (the three files were removed from
`paths.exclude`).

**It is deliberately not edited here.** The packet is digest-sealed:
`session_entry.packet_digest` covers the whole payload minus itself, and
`parse_work_packet` raises `packet_digest does not match canonical packet
content` on any drift. Verified 2026-08-04:

```
stored   : 7e7f01874f9c9bf50791b31246597a5bd59b9497abdd3e0b79b0bf927c347d3a
computed : 7e7f01874f9c9bf50791b31246597a5bd59b9497abdd3e0b79b0bf927c347d3a  (seal valid)
after adding any key: 548fd203ce53d977106836e20d16998597bd637c1e25a8e1d974fb0ad62014d9  (seal broken)
```

Editing the text and re-sealing would make an executed packet's immutability
proof self-issued by a later agent — the opposite of what the seal is for.
The packet records *intent at execution time*; this record is the authority on
what the mechanism actually is. That correction is made here instead.

### Verification

```bash
DHARMA_SEMGREP_EXPECTED_VERSION=1.168.0 \
  bash scripts/governance/run_semgrep_with_ca.sh --config .semgrep --metrics=off
# => Ran 11 rules on 1577 files: 17 findings  (all listed above, all true positives)

make semgrep          # required scan, security.yml only: exit 0, unchanged
PYTHONPATH=$PWD python3 -m pytest -q tests/test_semgrep_wrapper.py \
                                     tests/test_semgrep_rule2_behavior.py
```

Negative controls, each proven then reverted:
(A) `open("audit.log")` inside a `*Store` method → **no** finding (the mode
metavariable cannot bind a filename); (B) `"w"` / `"x"` modes and a read-only
`open(p)` → **no** finding; (C) an identical append method on a class NOT
named `*Store/Ledger/Registry/Substrate` → **no** finding; (D) the three
ratified files and `dharma_swarm/runtime_state.py` → **no** finding;
(E) a `SmuggledLedger` appended to a copy of `graph_store.py` → **one**
`dharma.no-new-substrate` finding; (F) `DHARMA_SEMGREP_BIN` pointed at a
missing binary → 7 named SKIPs, 0 silent passes.
