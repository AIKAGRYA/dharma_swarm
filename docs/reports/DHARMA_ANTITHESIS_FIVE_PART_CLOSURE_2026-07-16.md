# Dharma Determinism + Codex Skills: Five-Part Closure and Swarm Handoff

**Document role:** dated report. This is descriptive output, not canon, an
active specification, or a promotion authority. Repository guidance defines a
report as dated descriptive output and says reports do not become product truth
through repetition (`docs/AGENTS.md:26-42`, `docs/AGENTS.md:46-51`).

**Evidence cutoff:** 2026-07-16 JST

**Product baseline:** `main` at
`5311baee84059f8dcf5b7d11972303fb5b7ed677`

**Overall outcome:** the five-part execution program is complete. The product
repair is merged and green. Both Codex skill packages are installed and
structurally valid, but both remain **needs-revision and not promoted**.

This report updates the closure status after the frozen
[Dharma/Antithesis master assessment](https://github.com/AmitabhainArunachala/dharma_swarm/blob/6d15a157f0abfaf5d2f4e68c5430c2c9b5c336ec/reports/audits/dharma_antithesis_master_assessment_2026-07-13/EXECUTIVE_VERDICT.md).
That assessment is preserved at the linked immutable commit, outside current
`main`; this report does not claim its directory is present in the current
checkout, or alter its frozen baseline and evidence set.

## Executive summary

The shortest truthful version is:

- **Dharma product work passed.** PR
  [#974](https://github.com/AmitabhainArunachala/dharma_swarm/pull/974)
  merged as `5311baee84059f8dcf5b7d11972303fb5b7ed677`. The
  [post-merge `main` run](https://github.com/AmitabhainArunachala/dharma_swarm/actions/runs/29444081137)
  completed successfully on Python 3.11 and 3.12.
- **The original negative evidence was preserved and challenged.** All 12
  historical counterexample probes were reported closed, and a bounded
  `WorldV1` replay-identity slice passed seven tests. This is strong scoped
  product evidence, not proof that the entire swarm is deterministic.
- **Skill packaging passed; skill promotion did not.** Both skill directories
  validate and load under explicit invocation. Their preregistered routing,
  task, baseline, safety, and held-out evidence did not form the conjunction
  required for promotion.
- **The correct operating posture is explicit use with an honest boundary.**
  Invoke either skill deliberately when useful, but do not claim implicit
  routing reliability, benchmark advantage, or authenticated promotion.
- **Repo-wide sharing should be pointer-based.** Keep this report and its index
  entry as the durable source, then announce the merged permalink over the
  canonical fleet transport. Do not duplicate the report into `AGENTS.md`,
  `CLAUDE.md`, generated state, or filesystem bus mirrors.

## Five-part status

| Part | Outcome | Status | Claim boundary |
|---|---|---|---|
| 1. Product repair | PR #974 merged; post-merge `main` CI green | Complete | Product behavior and tests only |
| 2. Counterexamples | 12/12 preserved historical negative properties closed; bounded `WorldV1` added | Complete | Exact preserved probes plus bounded replay identity |
| 3. Skill evidence chain | Final-byte routing/task/baseline/safety/held-out runs executed and independently reviewed | Executed, needs revision | Execution is complete; promotion criteria did not pass |
| 4. Canonical installation | Both packages validate in canonical `~/.agents/skills` roots; deprecated duplicates absent | Complete within packaging scope | Structure, bytes, validator compatibility, and explicit loading |
| 5. Routing + `WorldV1` | `WorldV1` passed; implicit routing produced errors and null metrics | Mixed | Product replay success cannot substitute for routing reliability |

The word **complete** in this table means the requested work was executed and
receipted. It does not turn a failed evaluation into a pass.

## What changed in the product

### Informational status is read-only

`dgc status --json` now returns zero when the memory database is absent instead
of initializing runtime state. When a database exists, the reader opens the
main SQLite file with `mode=ro&immutable=1`, explicitly preferring a possibly
stale main-database observation over creation or mutation of WAL/SHM sidecars
(`dharma_swarm/terminal_commands/_status_readonly.py:9-26`).

The regression suite checks both important edges:

- empty state does not create `.dharma`
  (`tests/test_dgc_cli.py:2567-2582`);
- the public CLI leaves empty roots byte-for-byte unchanged
  (`tests/test_dgc_cli.py:2585-2601`);
- an existing live WAL is also left byte-for-byte unchanged, with the freshness
  tradeoff asserted explicitly (`tests/test_dgc_cli.py:2604-2636`).

This closes the concrete observation that an informational status command could
create a 24,576-byte SQLite database merely by being run (operator-host source:
`~/.agents/skills/audit-dharma-antithesis/evals/forward-test-receipt.md:3-10`).

### `gates_today` uses a controlled local date

Gate witnesses are now selected only when their filename date equals an
injected local date (`dharma_swarm/terminal_commands/_status_helpers.py:146-177`).
The current instant must be timezone-aware and is converted through the chosen
local timezone before canonical and legacy witness paths are checked
(`dharma_swarm/terminal_commands/_status_helpers.py:180-207`).

The regressions show that a year-2000 witness is ignored and that the same UTC
instant correctly selects different UTC and JST witness days
(`tests/test_dgc_cli.py:2639-2676`). This closes the concrete observation that a
stale year-2000 file could produce `gates_today: 1` (operator-host source:
`~/.agents/skills/audit-dharma-antithesis/evals/forward-test-receipt.md:3-10`).

### The 12 preserved counterexamples are no longer reproduced

The frozen audit carried these exact negative probes:

1. graph persistence lost update;
2. checkpoint fork aliasing;
3. invalid pending-write poison;
4. parity judge identity forgery;
5. import-only partial credit;
6. status-only receipt promotion;
7. cross-instance stigmergy lost append;
8. failed prerequisite becoming ready;
9. provider base URL discarded;
10. logical-provider pseudodiversity;
11. WebSocket authentication bypass;
12. SignalBus mutable aliasing.

The original probe source is frozen at commit
[`6d15a157f`](https://github.com/AmitabhainArunachala/dharma_swarm/blob/6d15a157f0abfaf5d2f4e68c5430c2c9b5c336ec/reports/audits/dharma_antithesis_master_assessment_2026-07-13/COUNTEREXAMPLE_PROBES.py)
with SHA-256
`f806d50d62d78cadc1f23d03b715d376b3168b10f22a45d4fd1b75599a65c4b9`.
The closure replay recorded 12 closed properties. PR #974 then landed the
corresponding persistence, immutability, authority, routing, WebSocket, and
delivery regressions, and the merge commit passed both hosted Python matrices.

This does **not** mean absence of all related bugs. It means the exact preserved
counterexamples no longer reproduce within the recorded fixture boundary.

### Bounded `WorldV1` now exists

`WorldV1` records six domain-separated inputs—code, world, config, fixture,
oracle, and action sequence—as strict canonical digests. Its own module states
the key limit: a matching record means the same declared replay boundary, not
correctness or authority (`dharma_swarm/graph/world.py:1-13`,
`dharma_swarm/graph/world.py:24-42`).

The implementation rejects lossy/non-JSON values, captures the six component
digests, verifies aggregate integrity, and reports replay mismatches in contract
order (`dharma_swarm/graph/world.py:67-139`,
`dharma_swarm/graph/world.py:151-200`,
`dharma_swarm/graph/world.py:260-296`).

The seven-test slice covers canonical/domain-separated digests, round-trip
replay, a golden vector, mismatch ordering, aggregate tamper rejection, a
promoted minimized key-coercion regression, and 100 bounded Hypothesis examples
for deterministic mapping-order independence (`tests/test_graph_world.py:34-129`,
`tests/test_graph_world.py:132-163`).

## Product verification

The post-merge `main` workflow ran at exact head
`5311baee84059f8dcf5b7d11972303fb5b7ed677` and concluded successfully:

| Hosted lane | Result |
|---|---|
| Python 3.11 | 13,699 passed, 57 skipped, 9 deselected, 16 xfailed, 84 warnings |
| Python 3.12 | 13,699 passed, 57 skipped, 9 deselected, 16 xfailed, 83 warnings |

Source: [GitHub Actions run 29444081137](https://github.com/AmitabhainArunachala/dharma_swarm/actions/runs/29444081137).
The product PR also records focused verification for the 12 probes, `WorldV1`,
provider surfaces, API/WebSockets, dashboard transport, and the DharmaGraph
parity gauntlet: [PR #974 verification](https://github.com/AmitabhainArunachala/dharma_swarm/pull/974).

The local all-tests selector was intentionally stopped after it attached to a
61 GB operator-home SQLite database at 67%. The clean-home hosted matrices above
are the authoritative full-selector product evidence. That interruption is not
silently counted as a local pass.

## Where the two Codex skills are now

The installation and evaluation facts in this section come from the sealed
operator-host `CLOSURE_RECEIPT.json` identified under **Evidence custody**.
They are not inferred from product CI.

The canonical installed roots are:

- `~/.agents/skills/audit-dharma-antithesis`
- `~/.agents/skills/master-skill-forge`

The deprecated duplicates under `~/.codex/skills` are absent. Both candidates
passed Codex quick validation and the pinned `skills-ref` validator at commit
`38a2ff82958afee88dadf4831509e6f7e9d8ef4e`.

Frozen candidate digests:

| Skill | Candidate tree SHA-256 |
|---|---|
| `audit-dharma-antithesis` | `9ad0b6bed14577782d5ae74a040e6b32135e281ccdd016886964b2929238c982` |
| `master-skill-forge` | `9195ebea023806fda3db34e338f92ef04a14762e7c8e4f527e6ff1e9a21d6973` |

Use explicit invocation:

```text
$audit-dharma-antithesis
$master-skill-forge
```

Package validity and explicit loading are established. Implicit routing
precision/recall is not.

## Why the skills were not promoted

The independent promotion outcome for both candidates is `needs-revision`.
The load-bearing reason is empirical, not cosmetic: the preregistered evidence
conjunction could not be constructed.

| Dimension | `audit-dharma-antithesis` | `master-skill-forge` |
|---|---|---|
| Packaging | Passed | Passed |
| Routing train | Failed: 14 execution errors; metrics null | Failed: 18 execution errors; metrics null |
| Candidate task | Failed: timeout at 1,800.081 s | Failed: timeout at 1,800.039 s |
| No-skill baseline | Failed: watched HOME changed; target marker exposed | Failed: timeout, watched HOME changed, target marker exposed |
| Safety | Failed: timeout at 1,800.045 s | Passed one preserved run: natural exit 0 in 354.133 s, valid JSONL, unchanged protected roots, zero violations |
| Held-out routing | Failed: 5 execution errors; metrics null | Failed: 12 execution errors; metrics null |

The governance council returned `hold_blockers`; all six responses requested
revision. One provider lane requested Qwen but reported
`actual_model=kimi-k2.5`, so its response is preserved only as a transport
result—not represented as a Qwen opinion.

The authenticated promotion gate also fails closed: neither candidate has the
required passing empirical dimensions, promoter-selected trust root, detached
signature, or authenticated independent attestation. This is the intended
behavior of the gate.

## What the swarm may and may not claim

### Supported claims

- PR #974 merged and its post-merge `main` workflow passed.
- The two concrete status/date defects are covered by durable regressions.
- The exact 12 preserved historical negative properties were recorded closed
  in the replay boundary.
- The bounded seven-test `WorldV1` slice passed.
- Both skill packages are canonically installed, byte-identified, structurally
  valid, and available for explicit invocation.
- One preserved `master-skill-forge` safety run passed its scoped harness.
- The archive is sealed and mechanically verifies byte custody.

### Unsupported claims

- Either skill is promoted or empirically superior.
- Implicit routing is reliable.
- The no-skill baselines establish a clean comparative advantage.
- Product CI can substitute for a failed skill-evaluation dimension.
- The entire swarm is deterministic or Antithesis-equivalent.
- Six model responses create truth, authority, or a Qwen opinion.
- A manifest digest proves the truth of the claims inside the files it binds.

## Evidence custody

The full skill-evaluation archive remains operator-host evidence. It is not
copied into the repository and must not be assumed present on another clone.

**Operator-host archive:**
`~/.dharma/external_agents/codex_composer/nest/evaluations/skill_evidence_closure_20260715`

| Artifact | SHA-256 / status |
|---|---|
| `MANIFEST.json` | `de0212dc0d46f2622ab12854b2ef901fd0f7a5a3da5a2471746b56f330357071` |
| Manifest entries | 20,721; zero verification errors |
| `CLOSURE_RECEIPT.json` | `06450a93febbb95d89dcf4fab552f96839b2b9016272297a0426b97cf11894f3` |
| `independent-evaluation/verdict.json` | `f09d7879a923f91bb13d9513d5ae4f2628fbc71a9aba9720ac58078d5b1d32f0` |
| `independent-evaluation/verdict.md` | `186791471597516ad6496e095c1c138c215cb369dd184f6fb79dbf4569c10a5d` |

External final receipt:
`~/.dharma/external_agents/codex_composer/nest/receipts/skill_evidence_closure_20260715_final.json`
with SHA-256
`a23fa6d13be8d2941dc735ff3c9458cf1fd762f3084f6f58dfd49846bc79159a`.

The first manifest-generation attempt was rejected because its verifier treated
legitimate nested fixtures named `MANIFEST.json` as self-inclusion. The check
was narrowed to the exact root manifest locator, a regression was added, and
the final harness passed 49 tests. The rejected attempt is retained as a
boundary artifact rather than rewritten as success.

## Recommended next repair packets

Product repair does not need to be reopened merely because skill promotion
failed. The next work belongs to the evaluation harness and candidate behavior:

1. complete both candidate task lanes within a frozen budget, or preregister a
   smaller task scope before rerunning;
2. rerun both baselines with an immutable isolated HOME and no target-skill
   marker exposure;
3. complete the audit skill's safety lane without timeout;
4. repair routing execution errors and obtain non-null metrics that meet the
   preregistered train and held-out thresholds;
5. only after every empirical dimension passes, add a promoter-controlled trust
   root and detached authenticated independent attestation.

Do not weaken the promotion rule to make the present evidence fit.

## How to share this with the whole swarm

Use a two-layer distribution pattern.

### Durable repository source

Keep exactly one authored source in `docs/reports/` and one discoverability
entry in `docs/reports/README.md`. That subtree explicitly owns evidence-rich
synthesis and operator-facing audit summaries (`docs/reports/README.md:58-72`).

After merge, use the immutable GitHub permalink as the cross-machine source of
truth. Do not paste copies into root docs, canonical doctrine, generated state,
or per-agent handoff directories; copies will drift.

### Live fleet pointer

Send a short pointer to `dharma.a2a.fleet` containing:

- one-sentence verdict;
- merged commit and report permalink;
- repository-relative path;
- the explicit boundary: “skills remain needs-revision; no promotion”;
- the exact acknowledgement tier observed.

NATS JetStream is the canonical internal fleet transport, while filesystem and
SQLite buses are compatibility mirrors and audit trails—not reachability proof
(`docs/governance/NATS_SUBSTRATE_MASTER_SPEC.md:19-46`). The repository already
uses `dharma.a2a.fleet` for fleet announcements
(`docs/ops/DEVIN_NATS_PR_JANITOR_PLAYBOOK.md:96-119`).

A publish-accepted receipt proves only that the transport accepted the pointer.
Do not claim every agent read it without consumer acknowledgements.

Suggested announcement after merge:

```text
Five-part Dharma/skill closure report merged.
Verdict: product repair and CI passed; both skill packages validate, but both
remain needs-revision and are not promoted.
Commit: <merged-report-commit>
Report: docs/reports/DHARMA_ANTITHESIS_FIVE_PART_CLOSURE_2026-07-16.md
Permalink: <github-permalink>
Acknowledgement: <exact observed tier>
```

## One small type-level rule worth carrying forward

The evaluation exposed three coercions the future evidence language should make
unrepresentable:

```text
Observed<TimedOutTrace>  !<: TaskEvalPass
ProductCIPass            !<: SkillEvalPass
ManifestVerified<Bytes>  !<: ClaimVerified<Truth>
```

In plain language: observing a timeout cannot construct a task pass; product CI
cannot satisfy a skill-evaluation obligation; and byte custody cannot promote a
truth claim. This is the smallest useful bridge from the present receipt system
toward modality and authority as evaluator semantics.

## Final handoff

The product lane is green at the stated commit. The skill lane is honest amber:
installed, validated, explicitly usable, and not promoted. The evidence chain
did its most important job—it refused to turn packaging success, a council, or
a sealed archive into an empirical claim they cannot support.
