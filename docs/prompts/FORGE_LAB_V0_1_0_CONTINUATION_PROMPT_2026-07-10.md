# Forge Lab v0.1.0 Continuation Prompt

Use this prompt to continue the Meghadharma RSI Lab work after a session or
five-hour execution limit. Do not restart the audit from scratch.

---

Assume the `codex_rsi_lab_manager` role for this session. Work as the operator's
engineering collaborator and thinking partner. The operator is a single
researcher building a serious self-improving-agent lab and has explicitly
accepted the architecture below.

## Mission

Continue Forge Lab v0.1.0 from the current repository and host state. The
normative hardening pass is complete; implement it in ordered, testable packets
without losing existing user changes or spending provider compute implicitly.
Resume at the first incomplete packet rather than reopening resolved design.

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
- Repo-owned control scripts and legacy inventory:
  `scripts/forge_lab/`
- Canonical checkout and manager registration:
  `/root/rsi-lab/current/repo`
- Canonical shared lab state:
  `/root/rsi-lab/current/state`
- Installed legacy host wrappers pending cutover:
  `/root/rsi-lab/bin/`
- Deprecated recovery worktree; never launch a new campaign here:
  `/root/rsi-lab/current-main/repo`

The normative file is in the correct root `specs/` directory. Do not move it
back to `docs/specs`; that area contains older design and launch material.

## Current Worktree

The canonical checkout is `/root/rsi-lab/current/repo` on
`forge/chassis-v0`. Recovery merge `fac803dc` unifies:

- current upstream `ed5ede2f`;
- preserved Forge substrate/spec commit `f37eb387`;
- hardened normative spec commit `a8245310`; and
- manager registration/presence commits `a5921869` and `1627250f`.

The only merge conflict was the A2A alias table. Its resolution retained both
the current `perplexity` alias and all `codex_rsi_lab_manager` aliases. Packet A
is now implemented as a fail-closed control-surface checkpoint; inspect the
latest local commit and preserve any newer user changes before continuing.

`/root/rsi-lab/current-main/{state,pydeps,.venv}` already symlinks back through
`/root/rsi-lab/current`; repointing `current` to `current-main` would create a
loop. Its recovery branch is preserved and its worktree was clean at Packet A
closeout. Keep it recovery-only unless the operator separately chooses to
remove it after reconfirming that no campaign is active.

## Verified Starting Facts

- `dharma_swarm.forge_lab.__version__` is `0.1.0-dev`; only version reporting
  and the fail-closed Packet A command tree are implemented. Operational
  commands return exit 3 and `NOT_IMPLEMENTED`; Packet A does not claim AC-26.
- `scripts/forge_lab/rsi` is a repo-owned development launcher with canonical,
  overridable repo/venv/pydeps defaults. The eventual installed `rsi` console
  entry point remains deferred because `pyproject.toml` has another active
  track owner.
- The 13 installed `rsi-*` sources are preserved byte-for-byte, non-executable,
  and explicitly noncanonical under `scripts/forge_lab/legacy_v0/`. Installed
  host wrappers were not changed or invoked.
- Packet A plus manager/registry verification passed 44 tests. The established
  offline Forge regression set passed 52 tests with one live-model test skipped.
  The async archive cases require host execution because the command sandbox
  blocks their worker thread; the isolated host run made no network/provider
  calls. Both runs emitted only the pre-existing unknown `timeout` config
  warning from the available pytest environment.
- No RSI tmux campaign is active.
- The 2026-07-11 smoke experiment completed at 05:04 UTC as
  `inconclusive_low_power`: 3 graded rows, 296,559 tokens, seed and best pass
  rate both 1/3, Merkle verification passed, and scratch cleanup completed.
- That legacy run repeated the same three tasks, marked the seed invalid under
  the old 90k boundary, ignored later free-form instructions, and emitted async
  client cleanup warnings. It is evidence for the v0 gaps, not a DGM claim.
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

## Spec Review Resolution

The 22 recorded P0 and scientific defects are resolved in `a8245310`. The
normative spec now includes the canonical lifecycle table; crash-safe stop;
fenced active/recovery/terminal lease modes; executable runner artifacts;
scoped broker/remote-adapter custody; mutation/solve/grader isolation;
deterministic watchdog fuses; full control-plane backup/restore; authenticated
remote workers; manifest-only launch; orthogonal candidate/verdict/archive
state; and the complete schema set.

Scientific closure includes immutable external admission handshakes, authentic
typed self-edit and fixed-external mutation receipts, byte-exact AgentBundle
identity, exact `fixed_route`/`evolvable_pool` claim boundaries, coequal
repository authority constraints, `explore-open` spelling, volatile-host
evidence separation, and AC-01 through AC-26 mapped to every invariant.

Two fresh findings-only rereviews returned PASS: one for P0/operational
consistency and one for DGM/scientific consistency. Mechanical validation found
balanced Markdown tables/fences, ASCII-only text, valid local links, contiguous
AC IDs, complete invariant mapping, and a clean `git diff --check`.

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
BASE=/root/rsi-lab/current
cd "$BASE/repo"
git status --short --branch
git diff --check
HOME=/tmp/rsi-packet-a-home \
PYTHONPATH="$BASE/repo:$BASE/pydeps${PYTHONPATH:+:$PYTHONPATH}" \
"$BASE/.venv/bin/python" -m pytest -q tests/forge_lab_v1
```

3. Packet A is complete: fail-closed repo-owned CLI skeleton and version
   reporting, canonical checkout/runbook, isolated manager defaults, and
   byte-for-byte legacy-wrapper custody. Do not edit the active-track-owned
   `pyproject.toml` until its owner coordinates the eventual `rsi` console
   entry point.
4. Keep installed `/root/rsi-lab/bin/rsi-*` wrappers unchanged until the new CLI
   reaches lifecycle parity; never route new commands into legacy tmux control.
5. Start Packet B with
   `tests/forge_lab_v1/test_provider_selftest.py::test_provider_selftest_fails_when_offline_profile_has_zero_verified_routes`:
   canonical Moonshot route, repaired key oracle, offline zero-target-failing
   provider self-test, broker interface, and M5 parity inventory. Keep it
   fake/offline first.
6. Do not run a paid evolution campaign while implementing Packets A/B.

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
