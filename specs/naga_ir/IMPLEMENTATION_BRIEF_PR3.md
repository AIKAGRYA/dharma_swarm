# PR #3 Implementation Brief

**Audience:** a fresh code-focused agent picking this up after PR #2 spec triple merges.

**Objective:** wire `scripts/governance/assurance_boundary.py` to emit `dharma.naga_receipt.v1` receipts alongside the existing `assurance_boundary_report.v1` verdict, without changing the verdict, exit codes, or blocking semantics.

**Non-objective:** do not implement PR #4 (SAB shadow export), PR #5 (titanium-verify metadata), or anything else in the locked arc. This PR is one file's worth of change plus its tests.

---

## 1. Read these first, in order

1. `specs/naga_ir/iteration_log/STATE.md` — chain state and constraints
2. `specs/naga_ir/core.md` v4 — full spec
3. `specs/naga_ir/receipt_wire.md` — wire schema, JCS canonicalization, ed25519 policy
4. `specs/naga_ir/witness_mesh.md` — mesh event types and merge rules (PR #3 emits mesh events, does not implement merge)
5. `scripts/governance/assurance_boundary.py` (430 lines, headed docstring is authoritative)

Do not proceed until you have read all five. STATE.md tells you where the artifacts live, why they exist, and which decisions cannot be re-litigated in code.

## 2. Facts you can rely on

- Branch: `telos_titanium/naga_ir`, off `titanium/phase-1e-ci-wiring` tip (commit 47194c39 at brief-write time).
- File to modify: `scripts/governance/assurance_boundary.py` only. Anything outside `scripts/governance/` or `packages/telos-kernel/` requires an explicit note in the PR description.
- Existing schema constant: `REPORT_SCHEMA_VERSION = "assurance_boundary_report.v1"` at line 60.
- Existing exit codes: 0 hold, 1 violated, 2 broken. Preserve exactly.
- AB-01/02/03 are measured + ratchet-banked (drift-preventing); AB-04/05 are hold-at-zero (fail-on-first-violation). This asymmetry is real and must survive PR #3.
- Signing key material: not present in the repo. PR #3 emits receipts with `signatures: [{alg: "ed25519", key_id: "unsigned-dev-<host>", sig: "sha256:<jcs_digest_of_content>"}]` in dev mode; a follow-up PR wires real keys. Do not block PR #3 on key infrastructure.

## 3. Q10 decision (locked)

**One `dharma.naga_receipt.v1` per contract per boundary run, plus one aggregating receipt per run. Six receipts total per invocation.**

- Five per-contract leaf receipts:
  - `AB-01` receipt: claim class `contract`, claim body `"boundary_record_classes_frozen_and_versioned"`, evidence `Proven_by(assurance_boundary_ab01, telos-kernel-tcb-v1, <boundary_packages_union>)`
  - `AB-02` receipt: claim `"no_silent_exception_swallow_in_boundary"`, evidence `Proven_by(assurance_boundary_ab02, ..., <boundary_packages_union>)`
  - `AB-03` receipt: claim `"no_fire_and_forget_asyncio_task_in_boundary"`
  - `AB-04` receipt: claim `"no_direct_provider_import_outside_runtime_provider"`
  - `AB-05` receipt: claim `"active_surface_manifest_layers_resolve"`
- One aggregate receipt: claim class `contract`, claim body `"assurance_boundary_v0_holds_under_telos_kernel_tcb_v1"`, evidence carries five `prev_receipt_hash` links to the leaves.

Confidence 87/100. Reversible in code if the assurance_boundary emitter turns out to want fewer receipts; the spec does not forbid the reverse. Flag any conflict in the PR description rather than working around it silently.

## 4. Concrete tasks

### 4.1 Add receipt emitter module

Create `scripts/governance/naga_receipt_emit.py`. Stdlib-only (assurance_boundary.py is stdlib-only per governance-surface law; keep the same discipline). Exports:

```python
def emit_boundary_receipts(
    report: BoundaryReport,
    *,
    boundary_run_id: str,
    trust_base_id: str = "telos-kernel-tcb-v1",
    fragment_id: str = "assurance-boundary-v0",
    now_utc_iso: str,
    prev_receipt_hash: str | None = None,
    key_id: str = "unsigned-dev",
) -> list[dict]:
    ...
```

Return value: a list of six canonicalized receipt dicts, aggregate last. Each receipt:

- `schema_version: "dharma.naga_receipt.v1"`
- `receipt_id: "urn:uuid:<uuid4>"` (or a boundary-run-derived deterministic id if the coder prefers reproducibility; document either choice)
- `subject`: `{"kind": "code-fragment", "id": "<boundary_packages_union>", "hash": "sha256:<git_tree_hash_of_boundary>"}`
- `claim`: `{"class": "contract", "id": "AB-0X", "body": "<claim body from §3>"}`
- `claim_hash`: SHA-256 of JCS-canonicalized claim object, formatted `sha256:<hex>`
- `authority`: `{"trust_base_id": trust_base_id, "fragment_id": fragment_id, "authority_key": "sha256:<hash_of_(claim_hash, trust_base_id, fragment_id)>"}`
- `evidence`: single-element list for leaves; five-element for aggregate
  - Leaf: `[{"modality": "Proven_by", "method": "assurance_boundary_ab0X_ast_static", "params": {"boundary_packages": [...], "boundary_modules": [...], "python_version": "..."}, "result": "pass" | "fail", "verdict_hash": "sha256:<hash_of_violation_list>"}]`
  - Aggregate: `[{"modality": "Proven_by", "method": "assurance_boundary_aggregator", "params": {"leaf_receipt_hashes": [<5 hashes>]}, "result": "pass" if exit_code == 0 else "fail"}]`
- `causal_origin`: `{"agent": "assurance_boundary", "version": "<git_sha_of_this_module>", "invocation": boundary_run_id, "agent_trace": None}`
- `epistemic_origin`: `{"trust_base_id": trust_base_id, "fragment_id": fragment_id, "verifier_pass": "assurance_boundary_v0"}`
- `ttl`: `{"observed_at": now_utc_iso, "expires_at": "<now + P14D>", "clock_uncertainty_ms": 500, "max_clock_skew_ms": 30000}`
- `challenge_base`: `{"mesh_id": "dharma-swarm-main", "query_key": "sha256:<authority_key>", "evidence_horizon": "P14D", "base_snapshot_hash": "sha256:<placeholder-until-mesh-exists>"}`
- `challenge_state`: `{"authoritative": false, "unresolved_count": 0, "queried_at": now_utc_iso}`
- `prev_receipt_hash`: as passed
- `signatures`: `[{"alg": "ed25519", "key_id": key_id, "sig": "sha256:<jcs_digest_over_signature_input>"}]` (dev-mode stub; a follow-up PR replaces with real ed25519)

Signature input per wire spec: JCS-canonicalized receipt with `signatures` field removed. Use `json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")` as the JCS approximation; a strict RFC 8785 implementation is not stdlib-available and the wire spec permits sorted-keys JSON as a v1-compatible subset (document this in the module docstring).

### 4.2 Wire the emitter into `assurance_boundary.py`

Two touch points:

1. At the top of `main()`, generate `boundary_run_id = "urn:uuid:<uuid4>"` and capture `now_utc_iso = datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")`.
2. After the `BoundaryReport` is constructed and BEFORE the existing print/JSON output, call `emit_boundary_receipts(...)` and write the six receipts to `<repo_root>/reports/naga_receipts/<YYYY>/<MM>/<DD>/boundary_<boundary_run_id_short>.jsonl`. One receipt per line, aggregate last. Do NOT write to a fixed path that overwrites prior runs.

Add a CLI flag `--emit-receipts / --no-emit-receipts` defaulting to `--emit-receipts`. `--no-emit-receipts` preserves pre-PR-#3 behavior exactly.

**Do not change the existing JSON verdict output or exit codes.** Receipt emission is additive. If receipt emission fails for any reason (disk full, key stub error), log to stderr and continue with the existing verdict — receipt emission MUST NOT convert an exit-0 into an exit-2.

### 4.3 Tests

Add `tests/test_assurance_boundary_receipts.py`:

- `test_emits_six_receipts_per_run` — invoke on a fixture repo state; assert six receipts, aggregate last.
- `test_receipt_schema_shape` — every receipt validates against a hand-written schema check (do not require jsonschema; use dict-key assertions).
- `test_claim_hash_stable_under_reorder` — permute the claim dict's key order, JCS-canonicalize, hash — must match.
- `test_aggregate_links_to_leaves` — aggregate's `evidence[0].params.leaf_receipt_hashes` matches the five leaves' SHA-256 self-hashes.
- `test_exit_code_unchanged_by_emission` — same fixture, `--emit-receipts` and `--no-emit-receipts` must produce identical exit codes.
- `test_emission_failure_does_not_change_verdict` — patch the writer to raise, assert exit code unchanged, assert stderr note.
- `test_receipts_write_to_dated_path` — assert the `reports/naga_receipts/YYYY/MM/DD/` structure.

Do not add integration tests that require the mesh, ed25519 keys, or a running SAB — those are PR #4+ concerns.

### 4.4 Mechanical checks before push

Run these from the repo root against `scripts/governance/naga_receipt_emit.py` + tests:

```bash
python -m py_compile scripts/governance/naga_receipt_emit.py
python -m py_compile scripts/governance/assurance_boundary.py
python scripts/governance/assurance_boundary.py --emit-receipts
python scripts/governance/assurance_boundary.py --no-emit-receipts
pytest tests/test_assurance_boundary_receipts.py -x
```

All five must pass. The two `assurance_boundary.py` invocations must produce identical exit codes on a clean checkout.

Governance surface law check: `naga_receipt_emit.py` imports only from Python stdlib. No third-party imports. Grep for `^import\|^from` in the new module and confirm every top-level import is stdlib.

## 5. Inherited spec constraints

1. `sha256:` URI form for every hash. No bare hex, no ellipsis placeholders after the prefix.
2. RFC 3339 UTC timestamps with `Z` suffix. No local time.
3. JCS-approximation via `json.dumps(sort_keys=True, separators=(",", ":"))` for signing input.
4. `challenge_state.authoritative: false` always (the mesh doesn't exist yet; the receipt cannot self-attest liveness).
5. `challenge_base.base_snapshot_hash` may be a documented placeholder until PR #4 wires the mesh; call this out in the emitter docstring.
6. Never emit an empty signatures array — always include the dev-mode stub entry.
7. Coalgebra + type-theory are non-normative; do not import or reference them.
8. NĀGA-IR ≠ ETH Nagini. If you touch imports, do not add `nagini` anywhere.

## 6. Scope boundary

- Do not implement the mesh (`witness_mesh.md` scope, PR #4+).
- Do not implement real ed25519 signing. Dev-mode stub only.
- Do not modify `packages/telos-kernel/`.
- Do not modify `dharma_swarm/coalgebra.py` or `docs/telos-engine/01_SATTVA_VISION.md`.
- Do not touch `scripts/governance/hygiene/ratchet.py` — AB-01/02/03 measurement stays there.
- Do not add a receipt verifier — that's a separate PR. Emission only.
- Do not add a CLI to READ receipts. Only emit and write to disk.
- Do not add metrics, logging frameworks, or third-party deps.

## 7. Acceptance criteria for merge

- Six receipts emitted per boundary run, verified in tests.
- Exit codes identical to pre-PR-#3 behavior for `--emit-receipts` and `--no-emit-receipts` on the same fixture.
- All seven tests in `test_assurance_boundary_receipts.py` green.
- New module is stdlib-only.
- PR description includes: (a) confirmation that Q10 (one-per-contract + aggregate) worked, or (b) an explicit note that a different mapping was needed and why.
- No modifications outside `scripts/governance/` and `tests/`.
- No new files under `packages/telos-kernel/`.
- Mechanical sweep on any spec files you added or edited: 0 exclamations, 0 italics, 0 sha placeholders, 0 empty signatures, 0 headers over 6 words.

## 8. Rollback plan

If PR #3 lands and downstream (PR #4 SAB export) discovers the six-receipts-per-run shape is wrong, revert is one commit: `git revert <pr3-merge-sha>`. The receipts directory (`reports/naga_receipts/`) is write-only and can be safely deleted; no other code reads from it in PR #3 scope.

## 9. If you get stuck

- Uncertainty about receipt field: `specs/naga_ir/receipt_wire.md` is authoritative. If it doesn't answer, add a `# TODO(pr3-clarification):` comment and continue.
- Uncertainty about wire format canonicalization: use `json.dumps(sort_keys=True, separators=(",", ":"))` and document; upgrade to real JCS in a follow-up.
- Conflict with existing `assurance_boundary.py` behavior: DO NOT WORK AROUND. Add a note in the PR description, flag it for review. The existing verdict semantics are the higher authority; receipts adapt to it, not the reverse.
- Anything philosophical: this is code work. If a decision feels like it needs a philosophical framing, you are out of scope. Ask a human.

## 10. Provenance of this brief

- Written by Fable (session Fable-2026-07-04-JST) after three-round agent iteration (Devin+, Codex+, Fugu+) converged the spec to v4 at 95/100.
- Q10 decided by Fable at user request (2026-07-04 16:11 JST). One-per-contract + aggregate, confidence 87/100, reversible if code says otherwise.
- Branch decision made by user: `telos_titanium/naga_ir` off `titanium/phase-1e-ci-wiring`.
- This brief is a hand-off document, not a spec. If it conflicts with `core.md`, `receipt_wire.md`, or `witness_mesh.md`, THE SPEC WINS. Update this brief to match.
