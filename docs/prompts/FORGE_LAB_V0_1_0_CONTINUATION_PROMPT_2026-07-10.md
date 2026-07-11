# Forge Lab v0.1.0 Continuation Prompt

Use this prompt to continue the Meghadharma RSI Lab work after a session or
five-hour execution limit. Do not restart the audit from scratch.

---

Assume the `codex_rsi_lab_manager` role for this session. Work as the operator's
engineering collaborator and thinking partner. The operator is a single
researcher building a serious self-improving-agent lab and has explicitly
accepted the architecture below.

## Mission

Continue Forge Lab v0.1.0 from the current repository and host state. First
finish hardening the normative specification. Then implement it in ordered,
testable packets without losing existing user changes or spending provider
compute implicitly.

The current task is not to re-argue whether Meghadharma should host the lab. It
is the dedicated and authoritative RSI VPS.

## Operator-Ratified Decisions

1. Meghadharma remains the canonical RSI control plane, archive, model broker,
   receipt store, and operator surface.
2. Optional M5 or ephemeral x86 workers are replaceable execution capacity;
   they do not move authority or state away from Meghadharma.
3. Remove the v0 90,000-token candidate invalidation boundary. Open exploration
   measures compute instead of invalidating high-compute candidates.
4. Keep research allocation, provider limits, and operational emergency fuses
   as separate concepts.
5. Pricing may remain unknown. Record raw usage completely and attach versioned
   price projections later.
6. Implement three modes: `explore-open`, `race`, and `confirm`.
7. Candidates become genuine self-editing `AgentBundle` codebases, not only
   fixed external mutations of configuration dictionaries.
8. The outer scheduler, archive, evaluator, task split, provider broker,
   credentials, receipts, containment, and fuse stay immutable to candidates.
9. Use staged, paired, rotating, sealed, and transfer task panels modeled on
   the Sakana DGM protocol, with causal no-self-edit and no-archive controls.
10. Meghadharma should expose equivalent usable model/API/CLI-subscription
    capability to the M5, subject to vendor and machine-specific auth rules.
11. API keys may be securely synchronized. Codex and Claude CLI sessions must
    be authenticated on Meghadharma itself; do not copy OAuth/session stores.
12. Candidate code never receives raw provider keys. Only trusted broker
    identities hold credentials.
13. Continuous compute is a resumable, checkpointed campaign, not a generated
    `while true` shell loop.
14. Version target is Forge Lab `0.1.0`; do not tag it until all acceptance
    gates pass.

## Canonical Files

- Normative draft:
  `specs/FORGE_LAB_V0_1_0_SPEC.md`
- Specs index:
  `specs/README.md`
- This continuation prompt:
  `docs/prompts/FORGE_LAB_V0_1_0_CONTINUATION_PROMPT_2026-07-10.md`
- Current Forge implementation:
  `dharma_swarm/forge_lab/`
- Host wrappers:
  `/root/rsi-lab/bin/`
- Active run checkout:
  `/root/rsi-lab/current-main/repo`
- Chassis checkout and manager registration:
  `/root/rsi-lab/current/repo`
- Shared lab state:
  `/root/rsi-lab/current/state`

The normative file is in the correct root `specs/` directory. Do not move it
back to `docs/specs`; that area contains older design and launch material.

## Current Worktree

The active checkout is detached at `8ab5be0f`. It was dirty before this spec
work. Do not revert or overwrite these pre-existing changes:

```text
M  dharma_swarm/forge_lab/mutation.py
M  dharma_swarm/forge_v1/forge_v2/runner_slots.py
M  dharma_swarm/forge_v1/providers.py
M  tests/test_forge_lab_chassis.py
M  tests/test_forge_v1_providers.py
?? tests/test_forge_v2_runner_slots.py
```

This session intentionally added or changed only:

```text
M  specs/README.md
?? specs/FORGE_LAB_V0_1_0_SPEC.md
?? docs/prompts/FORGE_LAB_V0_1_0_CONTINUATION_PROMPT_2026-07-10.md
```

No runtime implementation, provider configuration, service configuration, or
package version has been changed yet.

## Verified Starting Facts

- `dharma_swarm.forge_lab.__version__` remains `0.0.0`.
- No RSI tmux campaign was active at the last audit closeout.
- The latest completed n20 reused the same five tasks for all 20 generations.
- All 11 rows labeled graded in that run exceeded the old 90k cap. This is why
  the cap semantics must change rather than simply increasing a constant.
- The present Forge candidate is a bounded config genome. It is not yet a DGM
  self-editing code candidate.
- The canonical catalog contains 32 model entries and 46 routes across 12
  provider types, but the current lab oracle independently proves only
  `moonshot:kimi-k2.7-code`.
- The current Kimi receipt incorrectly derives both Kimi and Moonshot status
  from one Moonshot request. Kimi Code is not independently proven.
- Codex CLI is installed and reports ChatGPT login on Meghadharma, but needs a
  headless dispatch receipt for the selected model.
- Claude Code is installed but logged out.
- Meghadharma currently has 2 x86 vCPUs, 3.8 GiB RAM, 2 GiB swap, no compute
  GPU, and about 96 GiB disk free. It is suitable for API-bound control and
  light work, not high-parallel full SWE-bench containers or local frontier
  inference without an upgrade.
- The M5 is the Tailscale peer `johns-macbook-pro` at `100.74.45.73`. SSH port
  22 is reachable, but the Meghadharma key is not authorized for the likely
  `dhyana` user.
- Meghadharma SSH public-key fingerprint:
  `SHA256:tcE1RgrvIiACtTGHTYViWiZkPhSh1bgLaFJ9x1OKP+Q`.
- Historical M5 receipts showed Codex plus several Ollama Cloud, NVIDIA NIM,
  Groq, Kimi, and Z.ai routes, but that evidence is stale and must be refreshed.
- Production-adjacent Litestream was restart-looping and did not provide a
  verified replica. Continuous campaigns must not assume backup health.

## Spec Review Is Not Finished

Two independent reviews found concrete contract defects. Resolve these before
starting runtime implementation. Do not merely mention them in prose; make the
normative requirements and acceptance tests consistent.

### P0 contract fixes

1. Replace the lifecycle diagrams with one canonical transition table covering
   create, preflight, run, pause, resume, stop, crash/interruption, drain,
   closeout, completed, failed, fuse-tripped, and recovery behavior.
2. Define stop as crash-safe and idempotent. Persist evidence and closeout before
   cleanup; use the actual `rsi campaign stop` CLI; define grace deadlines and
   uncancellable/ambiguous provider-call handling.
3. Add a fenced manager lease with TTL, renewal, monotonic fencing token,
   takeover-after-crash, and release rules for every mutating campaign.
4. Pin an executable runner package/image per campaign. Source update or hash
   drift must require a provenance-linked fork; a manifest hash alone is not a
   runnable old environment.
5. Fix credential custody. Production and general RSI processes must not all
   load one plaintext broker secret file. Define Forge-scoped broker identity
   and a trusted remote route-adapter/broker role for machine-bound M5 CLI
   subscriptions. Untrusted workers own no credentials.
6. Apply the full containment contract to both `solve` and candidate-controlled
   `self_improve`, not evaluation alone.
7. Make fuse behavior deterministic per fuse: action, scope, evaluation cadence,
   broker revocation, operator acknowledgment/rearm, and resume eligibility.
   Require immutable hard wall plus call/token ceilings, or an explicit recorded
   dangerous opt-out. Add an external watchdog.
8. Expand backup from archive-only to a consistent full control-plane snapshot:
   database/events, manifests, checkpoints, receipts, task registry, archive,
   and blobs. Define off-host replica, consistency watermark, encryption,
   secret exclusion, retention, RPO/RTO, freshness fuse, and restore cadence.
9. Specify remote-worker enrollment, trust root, revocation, signed packet
   expiry/replay protection, scoped broker-token TTL, authenticated heartbeat,
   idempotent result upload, and compromised-worker quarantine.
10. Make `plan` emit a content-addressed manifest and require
    `run --manifest <digest>`. Define `doctor` as side-effect-free by default and
    add list/events/fork/fuse-ack/backup verify/restore commands and alerts.
11. Separate candidate execution state, scientific verdict, and archive
    persistence. Every candidate/evidence row may be archived independently of
    whether it is provisional or confirmed.
12. Add schemas for checkpoints, allocations/fenced leases, worker heartbeats,
    operator actions, fuse trip/ack, reconciliation, backup snapshots, and
    restore receipts.

### DGM and scientific fixes

13. Admission must use immutable external handshakes for both `solve` and
    `self_improve`. Bundle-local tests are candidate artifacts, not trusted
    admission tests.
14. Add `forge_lab.mutation_receipt.v1` and verify authenticity for every
    non-seed archive row, not only one example descendant.
15. Use distinct solve and grader containers: solve gets broker access but no
    hidden evaluator; grader gets hidden artifacts but no broker. Add adversarial
    hidden-data read/exfiltration tests.
16. Resolve model access precisely. `fixed_route` freezes actual provider/model
    for causal agent-design claims. `evolvable_pool` gives identical allowlists
    and resource leases and may claim only routing/orchestration gain.
17. Rename the target protocol or qualify the title/index so the unimplemented
    target is not already claimed as an operational DGM. Recursive improvement
    requires positive multi-generation held-out evidence over causal controls.
18. Add explicit precedence beneath the Sovereign Manifest, One Wire and
    production fitness authority, Runtime Truth Spine, and secret governance.
19. Define one canonical candidate serialization. API and base-agent identity
    must either be part of those canonical bytes or separate provenance, not
    two competing identity definitions.
20. Use the accepted spelling `explore-open` consistently in schema and CLI.
21. Move volatile M5 IP/auth facts out of the durable spec into dated evidence;
    keep only normative reconciliation requirements in the spec.
22. Convert acceptance bullets into stable `AC-xx` items mapped to invariants,
    verifier commands/tests, and required artifacts.

## M5 Credential Parity

The M5 remains the credential/capability comparison source, not the lab host.
Do not weaken SSH host verification or copy entire environment files.

The safe implementation procedure is:

1. Authorize the Meghadharma public key on the M5 or use an M5-initiated push.
2. Run a fresh names-only provider inventory and `dkeys` liveness test on M5.
3. Transfer only the canonical API key and public base-URL allowlist through a
   strict-host-verified Tailscale path.
4. Stage with mode `0600`, validate names only, then atomically promote into a
   Forge broker-scoped secret store.
5. Do not copy Codex auth files, Claude state, macOS Keychain data, cookies,
   browser state, or OAuth refresh-token caches.
6. Authenticate Codex and Claude directly on Meghadharma and emit separate
   headless dispatch receipts.
7. Treat Devin, Perplexity, Cursor, and Copilot as cloud/desktop seats unless a
   supported independent API or headless route exists.

## Immediate Continuation Order

1. Read the latest user message and let it override this handoff if needed.
2. Run:

```bash
cd /root/rsi-lab/current-main/repo
git status --short --branch
git diff --check
sed -n '1,260p' specs/FORGE_LAB_V0_1_0_SPEC.md
```

3. Resolve every P0 and DGM/scientific spec-review item above using
   `apply_patch`.
4. Run a second findings-only review of the actual spec.
5. Validate links, ASCII, heading numbering, mode spelling, invariants, schema
   list, and AC mappings. `git diff --check` must pass.
6. Only after the spec is internally consistent, start Packet A:
   canonical checkout decision, repo-owned CLI skeleton, version reporting,
   manager registration alignment, and legacy compatibility boundary.
7. Packet B follows: canonical Moonshot route, repaired key oracle, offline
   zero-target-failing provider self-test, broker interface, and M5 parity
   inventory. Keep it fake/offline first.
8. Do not run a paid evolution campaign while implementing Packets A/B.

## Engineering Rules

- Preserve pre-existing dirty changes and work with them.
- Use `apply_patch` for manual edits.
- Never print, diff, commit, or echo secret values.
- Do not copy raw CLI/OAuth credentials between hosts.
- Do not touch production containers or global daemon state without explicit
  current-session operator direction.
- Do not reintroduce 90k as a candidate validity cap.
- Do not call config-genome search a DGM.
- Do not claim lift from explore results.
- Use canonical parsers and schemas instead of shell string manipulation for
  secrets, manifests, receipts, and state.
- Test at the scope of each packet and add fault-injection tests for lifecycle
  code.
- Keep the operator informed every 30 seconds during long work.

## Audit Contamination Record

An audit subtask mistakenly invoked `rsi-run smoke` at
`2026-07-10T13:21:17Z`. It was stopped. It created one manifest, three
allocation rows, and one scratch worktree, with no candidates or closeout. The
mandatory liveness probe ran; any additional provider usage was not recorded.
Do not treat this as experiment evidence. Preserve or explicitly reconcile it
through the future interrupted-run protocol.

## Required Closeout

At the end of the continuation session, report:

- exact files changed;
- spec review findings resolved and any remaining;
- tests and verifier commands with results;
- current provider/model parity without secret values;
- lifecycle/backup/containment residual risks;
- whether any live provider call occurred;
- next build packet and its first failing test;
- updated handoff prompt if work remains.

Do not stop at a plan when implementation is authorized and feasible. Do not
start a live compute campaign merely because implementation tests pass.

---
