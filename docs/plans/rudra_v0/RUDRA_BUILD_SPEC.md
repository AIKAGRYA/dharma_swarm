# RUDRA v0 build specification

**Spec version:** `rudra.build.v0.1`

**Status:** normative build design, pending repository ownership admission

**Assessment base:** `884ee4fa75bb28877633f9c7a7ddadb8e3b1e19b`

**Product boundary:** trusted-operator coding missions on one macOS host

## 1. Executive contract

RUDRA is a small supervisory loop that gives a frontier coding model durable
mission continuity without giving the model authority to declare its own
success.

For one admitted mission it must:

1. bind an exact repository, base commit, toolchain, model protocol, write set,
   verifier set, and resource budget;
2. create one disposable Git workcell with a private supervisor-owned Git
   directory while leaving the base checkout's Git directory, HEAD, index, and
   working-tree bytes unchanged;
3. keep one Codex app-server thread working across multiple turns;
4. survive supervisor or app-server death without starting a second turn while
   an earlier executor may still be alive;
5. stop all model/tool mutation before final verification;
6. create a local candidate commit from only admitted paths;
7. rerun every admitted verifier against that exact candidate commit; and
8. emit `COMPLETE_REPRODUCED` only from that fresh result.

The build is a failure if it ships only schemas, mocks, councils, dashboards, or
receipts. Its first release proof is a real repository repair, repeated three
times, with a matched forced kill, and compared with three bare one-turn
app-server control runs.

## 2. Why this is the spear

The audited ecosystem already possesses most organs:

- strong frontier CLI providers with file and shell tools;
- TaskBoard, RuntimeStateStore, execution identities, receipts, and
  reconciliation;
- concurrent orchestration and a graph checkpoint engine;
- several verifier and sandbox experiments.

They do not form one causal chain. Durable agents are tool-less. Tool-using
providers are disposable host processes. Current overnight paths can accept
self-report. Mission Control is an honest projection but has no live canonical
executor. RUDRA adds only the missing join:

```text
frozen goal → persistent action → exact workspace → fresh oracle → recovery
```

Anything that does not improve verified close rate, time, tokens, human
attention, recovery, or blast radius is excluded from v0.

## 3. Normative invariants

The words MUST, MUST NOT, SHOULD, and MAY are normative.

1. **Exact subject.** Completion MUST name the exact candidate commit,
   acceptance digest, and fresh verifier-run digest.
2. **Immutable acceptance.** The executor MUST NOT change the admitted mission,
   verifier argv, executable identity, path policy, model policy, or budgets.
3. **Independent promotion.** Model prose, model JSON, tool exit status, a
   receipt, a task state, a council decision, or an old verifier result MUST NOT
   construct reproduced completion.
4. **Single mutation owner.** A new turn MUST NOT start until the prior process
   tree is proven dead or the attempt has stopped in recovery.
5. **Write zones.** All executor repository mutations MUST occur in the admitted
   mutation workcell. Supervisor control/evidence writes MUST occur only under
   `$DHARMA_STATE_DIR/rudra`. The base checkout and every other path receive zero
   writes.
6. **Base preservation.** The base checkout's Git directory, HEAD, index, and
   working-tree content MUST remain byte-identical. The workcell uses its own
   supervisor-owned Git directory; no common-directory mutation is exempted.
7. **Freshness.** Every terminal verifier MUST begin after the final workspace
   mutation and MUST be rerun after the candidate commit is created.
8. **No ambient authority.** Reproduced completion grants no authority to push,
   merge, deploy, send, spend, publish, install, or contact an external target.
9. **No silent downgrade.** Missing sandbox, interpreter, verifier, protocol, or
   process-control capability MUST yield `BLOCKED_ENVIRONMENT`; host fallback is
   forbidden.
10. **Baseline honesty.** Repair missions MUST prove the gate is red at the base
    before the first turn. A green base is rejected as `ALREADY_SATISFIED`, not
    counted as a RUDRA success.
11. **Boundedness.** Turn, token, wall-clock, verifier, CPU, memory, process-
    count, disk, output, read-only retry, and no-delta budgets MUST be enforced
    by the supervisor.
12. **Terminal compare-and-seal.** Mission-terminal append succeeds only when no
    mission terminal exists. An identical retry returns the sealed result
    without appending. A conflicting terminal or any lifecycle/effect row found
    after the seal quarantines replay as an invariant violation; it never
    replaces or weakens the sealed evidence and is never reported green.

## 4. Threat and trust model

### In v0 scope

- one trusted operator authors and reviews the mission;
- one first-party repository is already present locally;
- the dependency/tool environment is provisioned before the mission and mounted
  read-only to the model;
- Codex provider egress is allowed only so app-server can reach its configured
  model service;
- model-launched tool network is denied;
- the model may read and modify admitted repository paths and run the existing
  local toolchain;
- task/repository secrets are absent, and provider authentication is admitted
  only after a canary proves tool subprocesses cannot read its files or inherited
  environment;
- process crashes, client/server restarts, timeouts, malformed protocol input,
  and ordinary agent mistakes are adversarially tested.

### Rejected from v0

Raw third-party issue text, unknown repositories, untrusted code execution,
dependency installation, unrestricted network, secret-bearing work, exploit
artifacts, external cyber targets, and any outward side effect are rejected at
admission as `BLOCKED_CONTAINMENT`.

Same-UID malicious tampering with the RUDRA control directory, disk corruption,
host compromise, and power-loss durability are not claimed. A later hostile lane
must borrow a VM/container boundary with disposable credentials and controlled
egress. It must not weaken this evaluator contract.

## 5. Architecture

```text
                       operator-authored mission.yaml
                                   |
                                   v
                         +--------------------+
                         |     GoalGate       |
                         | parse/admit/freeze |
                         +----------+---------+
                                    |
                                    v
   status/stop ----------> +--------+---------+ <-------- fsynced run.jsonl
                            |  MissionRunner  |
                            | single authority|
                            +---+----------+---+
                                |          |
                                v          v
                         +------+---+  +---+----------------+
                         | Workcell|  | Codex app-server    |
                         | Git    |<--| persistent thread   |
                         +----+---+  +----------------------+
                              |
                    stop model mutation
                              |
                    supervisor candidate commit
                              |
                              v
                    independent final GoalGate
                              |
              red ------------+------------ green
               |                                |
          next turn /                         exact
          bounded fail                COMPLETE_REPRODUCED
                                                |
                                  optional post-proof projection
                                                v
                                         Mission Control
```

### Authority direction

- The operator authorizes the mission by admitting its immutable contract.
- MissionRunner authorizes bounded turns and verifier subprocesses.
- Codex produces candidate mutations and observations only.
- GoalGate evaluates the exact candidate and is the sole completion constructor.
- Mission Control, if connected later, receives an idempotent projection. It
  never feeds terminal truth back into GoalGate.

## 6. Minimal repository surface

No new dependency or console entry point is required.

```text
dharma_swarm/rudra/
├── __init__.py        # integration writer only
├── contracts.py       # strict mission and result models
├── goal_gate.py       # admission, scope scan, verifier, promotion
├── workcell.py        # private Git workcell, lock, journal, process identity
├── codex_driver.py    # narrow app-server JSON-RPC driver
└── runner.py          # state loop and resource budgets

dharma_swarm/terminal_commands/rudra.py
dharma_swarm/dgc_cli.py                     # minimal parser/dispatch edit

tests/test_rudra_contracts.py
tests/test_rudra_goal_gate.py
tests/test_rudra_workcell.py
tests/test_rudra_codex_driver.py
tests/test_rudra_runner.py
tests/test_rudra_cli.py
tests/test_rudra_adversarial.py
tests/fixtures/rudra/**
reports/rudra/**                             # curated closeout copies only
```

Runtime never writes `reports/rudra/**`. Executor repository mutations are
limited to the mutation workcell; supervisor journals/artifacts/private Git data
are limited to the state root. After base-preservation proof, a separately
authorized report-only packet may curate redacted evidence into
`reports/rudra/**` for review.

Production hot-path target, excluding tests and generated protocol evidence:

| Module | Target maximum |
|---|---:|
| `contracts.py` + `goal_gate.py` | 250 LOC |
| `workcell.py` | 275 LOC |
| `codex_driver.py` | 225 LOC |
| `runner.py` | 175 LOC |
| CLI/export edits | 75 LOC |
| **Deletion-review ceiling** | **1,000 LOC before first real run** |

The targets guide deletion; they do not license compressed or unreadable code.

## 7. Mission contract

`RudraMissionContract` is a strict Pydantic v2 model loaded by a custom
duplicate-key-rejecting `SafeLoader`. Admission MUST reject YAML aliases, merge
keys, custom tags, duplicate keys, unknown fields, implicit coercion, non-finite
numbers, absolute repository paths, `..`, backslashes, control characters,
`.git/**`, symlink ancestors, empty verifier lists, and shell command strings.

Display mission IDs MUST match `^[a-z][a-z0-9-]{0,63}$`. Attempt IDs are
supervisor-generated UUIDs, never CLI path input. Filesystem keys are derived
from SHA-256 over canonical repository identity, base, contract digest, and
attempt UUID; raw IDs never become directory names. Admission rejects
case-fold/canonical-remote collisions.

The normalized form uses strict primitive types and canonical `json.dumps`
settings (`sort_keys=True`, compact separators, `ensure_ascii=True`,
`allow_nan=False`) before SHA-256. The proposal/admitted JSON copies live
outside the model's writable root and are rehashed before every effect. File
permissions are defense in depth, not authority.

Required contract groups:

```text
schema_version, mission_id, objective
repository: canonical remote, exact 40-hex base SHA
scope: required/allowed/forbidden paths and diff literals
toolchain: absolute executables, installed-environment/import manifests, lock digest
acceptance: ordered argv commands, timeouts and optional structured assertions
executor: provider/model/effort/service tier and protocol pin
containment: sandbox, writable roots, tool network, approvals, risk class
budgets: turns, total/per-turn tokens, wall, CPU, memory, processes, verifier,
         disk, output and no-delta
recovery: resume policy and context-reset cap
result: baseline-red and local-candidate-commit requirements
```

`MISSION_CONTRACT_V0.yaml` is the normative example. Build-time admission MUST
regenerate its base, executable, and protocol bindings; copied placeholders or
stale values are a hard failure.

### Toolchain binding

The mission workcell normally has no untracked `.venv`. Admission therefore
selects one external pre-existing Python ≥3.11/toolchain by absolute path and
binds the resolved interpreter, dependency lock, installed distributions and
their RECORD digests, `.pth` contents, `sys.path`, pytest plugin allowlist, and
first-party import origins. `dharma_swarm` MUST resolve from the mutation or
verification workcell rather than a dirty editable install. The model receives
no write root for that environment. Runtime installation and symlinking a
writable shared virtualenv into the workcell are forbidden.

### Interface freeze before parallel coding

The GoalGate packet freezes these constructors/results before Driver and
Workcell begin in parallel:

```text
GoalGate.admit(proposal, repository_view, workcell_view) -> AdmittedMission
GoalGate.evaluate(admitted, verification_subject) -> GateResult
Workcell.open(admitted) -> RecoveryView
Workcell.append_intent/effect_result(...)
ProcessOwner.spawn/terminate/reap(...) -> ProcessHandle
CodexDriver.start_or_resume/start_turn/interrupt/close(...) -> TurnObservation
```

`GateResult`, `RecoveryView`, `ProcessHandle`, and `TurnObservation` are frozen
strict data contracts in `contracts.py`. Workcell implements `ProcessOwner` and
is the sole subprocess/session owner. CodexDriver owns protocol framing only; it
does not spawn, signal, kill, or reap a process.

## 8. GoalGate

GoalGate contains two operations: `admit()` and `evaluate()`.

### Admission algorithm

1. Parse strictly and normalize the mission.
2. Resolve repository identity and require the exact base object locally.
3. Derive the safe mission key, acquire the mission-level kernel lock, write and
   fsync `proposal.json`, then append/fsync `PROPOSAL_VALIDATED`. No workcell or
   child-process effect precedes this durable proposal identity.
4. Record base checkout Git-directory, HEAD, index, and raw working-tree digests.
   Use a hermetic Git environment that ignores system/global config and disables
   hooks/signing; audit repository-controlled attributes/filters and index
   flags by reusing the existing AgentOps scope-hardening primitives.
5. Resolve every verifier executable to an absolute path; record its raw digest
   and version output.
6. Bind Codex version, available model/provider/effort/tier, freshly generated
   app-server schema, and isolated Codex configuration/instruction digests.
7. Validate risk as `trusted_operator_coding`; reject task secrets, dependency
   install, tool egress, external actions, and hostile/cyber text.
8. Append/fsync workcell intent, then let Workcell create an isolated mutation
   checkout backed by its own supervisor-owned Git directory at the exact base.
9. Run the full gate once. If green while `require_baseline_red=true`, append an
   admission rejection, quarantine the workcell, and return
   `ALREADY_SATISFIED` without creating an attempt terminal.
10. If baseline is red for the expected reasons, atomically promote the durable
    proposal to `admitted.json`, fsync the directory, and append/fsync
    `ADMITTED`. Rehash the admitted copy before every later effect.

### Scope inventory

Evaluation MUST inspect raw Git and filesystem state, not only a friendly diff:

- porcelain-v2 `-z` tracked, renamed, deleted, and untracked entries;
- raw file bytes and executable modes;
- base-to-HEAD ancestry and tree identity;
- `.git` pointer bytes and the supervisor-owned private Git-directory identity;
- repository attributes/filters and index `skip-worktree`/`assume-unchanged`
  flags under a hermetic Git invocation;
- symlinks and symlink ancestors;
- forbidden and required path sets;
- forbidden diff literals compared with base counts;
- base checkout Git-directory/HEAD/index/working-tree digests.

Any changed path outside `allowed_changed_paths`, any changed
`forbidden_changed_paths`, any executor mutation of the private Git directory or
`.git` pointer, or any unresolved symlink is `FAILED_INVARIANT`. Supervisor Git
effects occur only after model quiescence, are journaled, and are limited to its
private index, new objects, and one private candidate ref; the base repository
receives no Git-control delta.

### Verifier execution

Verifier commands are argv arrays and run without a shell, in the exact admitted
cwd. GoalGate asks Workcell's `ProcessOwner` to start each in a fresh process
session. The supervisor scrubs at least:

```text
PYTHONPATH PYTHONHOME PYTEST_ADDOPTS GIT_DIR GIT_WORK_TREE GIT_INDEX_FILE
GIT_CONFIG_* BASH_ENV ENV CDPATH SSH_AUTH_SOCK
provider/API secrets and plugin startup variables
```

Only contract-declared environment values plus a minimal fixed `PATH` and locale
are present. Every command receives new bounded `HOME`, `TMPDIR`, and artifact
directories under the supervisor state root. Python runs with
`PYTHONDONTWRITEBYTECODE=1` and `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1`; required
pytest plugins are explicitly admitted and loaded.

For each command, GoalGate records argv, executable digest, cwd, sanitized env
digest, start/end time, exit code, timeout state, bounded stdout/stderr artifact
hashes, and configured output/structured assertions. Missing output is a failure
only when the contract declares an output assertion. Pytest gates use a JUnit
artifact with exact required test cases and passed/skipped/failure/error counts;
regex summaries alone cannot prove execution. A timeout asks ProcessOwner to
kill/reap the full process tree and invalidates the run.

### Candidate freeze and terminal evaluation

When a gate first turns green:

1. interrupt any active turn;
2. stop app-server and prove its entire process tree dead;
3. rehash the contract and workspace;
4. stage only admitted changed paths in the private Git directory, after proving
   no clean/smudge filters;
5. create a local reversible candidate commit on the RUDRA private candidate
   ref with
   hooks and GPG signing disabled and fixed local author metadata;
6. require the candidate to descend from the admitted base and the mutation
   workcell to have completely empty porcelain status, including untracked
   files;
7. create a fresh detached **verification workcell** at `candidate_sha`, outside
   the model's writable roots, with a new per-command HOME/TMP; make repository
   paths read-only where supported and audit all filesystem writes;
8. run the entire gate in that verification workcell, require empty porcelain
   before and after every command, and reject any repository write even when a
   verifier restores the original bytes;
9. reread raw bytes/modes and require the verification-workcell digest to match
   the candidate tree; and
10. construct `GoalGatePassed` only if every condition remains true.

If final verification is red, append `CANDIDATE_REJECTED`; preserve the immutable
candidate as evidence and continue mutation on top of it. A later candidate
supersedes it only by an explicit journal row. No failed candidate is reset or
silently reused.

`GoalGatePassed` contains:

```text
mission_id, attempt_id, base_sha, candidate_sha, contract_digest,
verification_workcell_id, workspace_digest, changed_path_digest, verifier_run_id,
ordered_verifier_receipt_digests, codex_version, schema_digest, completed_at
```

It grants no external effect.

## 9. The one epistemic type edge

RUDRA carries exactly one evaluator-level claim distinction:

```text
MissionCompletion[Reported] </: MissionCompletion[Reproduced]

promote(
  reported,
  GoalGatePassed(
    candidate_sha = reported.candidate_sha,
    contract_digest = admitted.contract_digest,
    workspace_digest = current.workspace_digest,
    fresh = true
  )
) -> MissionCompletion[Reproduced]
```

There is no conversion method on `ReportedCompletion`. The reproduced value can
be constructed only inside GoalGate's supervisor-owned promotion function.
Ordinary Python cannot provide compile-time information-flow proof; the negative
fixture and evaluator boundary are the executable obligation. This is not a new
language runtime, authority token, or receipt vocabulary.

## 10. Workcell, lock, and journal

### State layout

Use the existing Dharma state-root resolver. Do not write runtime evidence into
the repository.

```text
$DHARMA_STATE_DIR/rudra/
├── protocol/<codex-version>/<schema-digest>/
│   ├── manifest.json
│   └── schema.json
└── missions/<mission-key>/
    ├── identity.json
    ├── proposal.json | admitted.json
    ├── supervisor.lock
    ├── current-attempt
    ├── stop.request
    └── attempts/<attempt-key>/
        ├── run.jsonl
        ├── private.git/
        ├── mutation/repo/
        ├── verification/<gate-run-id>/repo/
        └── verifiers/<gate-run-id>/<command-index>.stdout|stderr|result
```

The journal is execution recovery evidence, not a task database. It owns no
portfolio, priority, delegation, or external action state.

### Single-owner lock

RUDRA MUST open the configured state root symlink-safely, prove it is outside the
source repository and all workcells, and create children with directory-relative
no-follow operations. It acquires `fcntl.flock(LOCK_EX | LOCK_NB)` on one
never-unlinked **mission-level** lock before reading or creating the current
attempt, and holds its file descriptor for the full supervisor lifetime. Thus a
caller cannot obtain concurrent execution merely by choosing another attempt
ID. If `fcntl` or symlink-safe directory operations are unavailable, the run is
`BLOCKED_ENVIRONMENT`.

The lock file records run UUID, PID, macOS boot identity, OS-observed process
start time, executable, cwd, and PGID for diagnosis. Do not reuse
`spine.identity.process_boot_id()` for this purpose; it is process-local. Age or
TTL never authorizes unlink/takeover.

On restart, the new supervisor acquires the kernel lock, resolves the durable
current-attempt pointer, validates recorded process identity, and terminates
only a PID whose PID, OS start time, OS boot time, executable, cwd, PGID/session,
and run nonce all match. Ambiguity becomes `RECOVERY_REQUIRED`; it never signals
a possibly unrelated process.

### Journal record

Each canonical JSON line contains:

```text
seq, event_id, event, at, mission_key, attempt_key, effect_key, payload
```

Writes use a complete-write loop, newline, flush, and `fsync`. Every effect uses:

```text
EFFECT_INTENT(parameters_digest) --fsync--> effect
EFFECT_RESULT(observation_digest) --fsync-->
```

Sequence gaps, duplicate IDs, reordered rows, or corrupt middle rows quarantine
the attempt and expose a derived invariant failure; a corrupt journal cannot
safely append its own failure row. Only a torn final line may be repaired under
the exclusive lock: preserve the raw tail as an artifact, truncate to the last
valid offset, fsync, and append `JOURNAL_TAIL_REPAIRED`.

Journal hashing and a separate head file are deliberately absent: same-UID
malicious rollback and disk loss are outside v0, while a second head creates
another crash-ordering seam. Content digests still bind missions, effects,
candidates, verifiers, and terminal evidence.

The crash guarantee is process-crash recovery on a healthy local filesystem,
not malicious same-user tamper or disk-loss durability.

### Git workcell identity

The mutation workcell uses an isolated local clone/checkout with a private Git
directory under the supervisor state root and the source object database as a
read-only alternate. The `.git` pointer is inside the executor worktree but its
target is not writable by the executor. The exact construction command is fixed
by the preflight spike; it MUST NOT add worktree metadata, refs, objects, or
index changes to the base repository.

Mission identity binds canonical repository, base, and contract digest. Attempt
identity adds the supervisor UUID. Adoption requires private Git directory,
`.git` pointer, alternates target, candidate ref, worktree path, base, proposal/
admission, and journal identity to agree. RUDRA never force-removes an ambiguous
workcell in the hot path; it quarantines it for operator review.

### ProcessOwner

Workcell is the sole owner of app-server, verifier, and known tool process
sessions. Every spawn has a durable intent; before mutation authority is granted,
its result records PID, OS process birth, boot identity, PGID/session, executable,
cwd, run nonce, and parent lineage. Workcell enumerates descendants during turns
and joins protocol tool observations to the process census.

The launch probe includes a child that calls `setsid`. If RUDRA cannot prevent
or enumerate and kill that escape on the supported macOS host, trusted v0 is
`BLOCKED_ENVIRONMENT`; it may not claim the entire tree is dead. CodexDriver only
reads/writes the channel supplied by ProcessOwner.

## 11. Codex app-server driver

The driver is a bounded stdio JSON-RPC client over streams supplied by
Workcell's ProcessOwner for the exact installed binary.
The audited binary was `codex-cli 0.147.0`; launch-time admission regenerates and
checks the schema because this is experimental and may drift.

### Allowed protocol surface

- initialize;
- `thread/start` and `thread/resume`;
- `turn/start` and `turn/interrupt`;
- only the terminal/item/diff/token/error observations required by the spike;
- `thread/read` only if the spike proves it is necessary to reconcile a lost
  response.

The driver MUST NOT call `thread/shellCommand`—the current schema explicitly
describes it as unsandboxed with full access—nor `command/exec`, filesystem RPCs,
account/config mutation, MCP, app/plugin, marketplace, auth, attestation, or
external tool endpoints.

Outgoing methods are hard-allowlisted. Unexpected server requests for approval,
permissions, user input, MCP, dynamic tools, or attestation receive an explicit
deny/error and stop the run. Unknown protocol variants, wrong IDs, oversized
lines, malformed JSON, and conflicting terminal notifications fail closed.

### Turn policy

`thread/start` and `thread/resume` reapply the admitted model, model provider,
service tier, cwd, approval, and sandbox fields supported by the pinned schema;
every `turn/start` additionally reapplies reasoning effort. The spike
feature-probes the exact model/provider/tier; an unavailable combination is
`BLOCKED_ENVIRONMENT`, not an automatic reroute. Every turn includes at least:

```json
{
  "approvalPolicy": "never",
  "cwd": "<exact workcell>",
  "model": "<admitted model>",
  "modelProvider": "<admitted provider>",
  "effort": "<admitted effort>",
  "serviceTier": "<admitted tier>",
  "sandboxPolicy": {
    "type": "workspaceWrite",
    "writableRoots": ["<exact workcell>"],
    "networkAccess": false,
    "excludeSlashTmp": true,
    "excludeTmpdirEnvVar": true
  }
}
```

`clientUserMessageId` and the effect key are deterministic from contract digest,
attempt key, method, and logical sequence. Stdout and stderr are drained
concurrently with size limits. All requests and waits have deadlines.
ProcessOwner—not Driver—spawns, interrupts, terminates, kills, and reaps process
sessions.

Mutation-capable RPCs (`thread/start`, `turn/start`) are never transport-retried
after any request byte may have been written. A durable RPC intent makes such a
crash ambiguous; recovery must reconcile the stable message/effect key or stop.
Only explicitly read-only methods may use the admitted bounded retry count.

Codex version, schema digest, thread ID, turn ID, model/provider/effort, token
observations, aggregate diff observation, and response hashes are journaled.
They are observations, not acceptance evidence.

App-server launches with a minimal hashed Codex config/instruction surface and a
shell-environment allowlist. MCP/plugins/apps are disabled. Provider credentials
are available only to app-server, never copied into the mission prompt, workcell,
tool environment, logs, or evidence. Before live launch, canary files and canary
environment variables colocated with the real credential boundary must be
unreadable to model tools. If the installed sandbox/config cannot establish this,
the run is `BLOCKED_ENVIRONMENT`; actual secret contents are never probed or
logged.

### Resume rule

After client or server restart, RUDRA first proves the old process tree dead,
reconciles Git, and runs GoalGate. It then attempts `thread/resume` and uses the
deterministic user-message ID to determine whether an ambiguous turn already
exists. It MUST NOT issue another turn merely because an RPC response was lost.

If same-thread recovery cannot be proven by the protocol spike, use one fresh
thread with a bounded compact handoff containing only:

- frozen objective and contract/base digests;
- current candidate diff summary;
- latest fresh verifier failures;
- consumed and remaining budgets; and
- an explicit context-discontinuity marker.

There is no custom transcript/session clone.

## 12. MissionRunner

MissionRunner is the only lifecycle writer.

```text
PROPOSED → ADMITTED → RUNNING ↔ VERIFYING
                         |
                         +→ RECOVERING → RUNNING | terminal

terminal = COMPLETE_REPRODUCED
         | FAILED_BUDGET
         | FAILED_INVARIANT
         | BLOCKED_ENVIRONMENT
         | CANCELLED_OPERATOR
```

`ALREADY_SATISFIED` and `BLOCKED_CONTAINMENT` are admission rejections before an
attempt exists. `RECOVERY_REQUIRED` is a derived status while lifecycle state is
`RECOVERING`.

`dgc rudra stop` writes a durable stop request. The runner interrupts and reaps
the process tree and compare-and-seals `CANCELLED_OPERATOR`; cancellation is not
misclassified as a budget or capability failure.
If `STOP_REQUESTED` is fsynced before any terminal intent, cancellation wins. If
a terminal is already sealed, `stop` returns that immutable terminal without
appending. A completion/cancellation race can therefore accept exactly one
terminal, never whichever projection arrives last.

Codex `turn/completed` is a protocol observation named
`CODEX_TURN_OBSERVED_TERMINAL`, never a mission terminal. Once the mission
journal is compare-and-sealed, it accepts no later lifecycle/effect row. Any
post-proof Mission Control projection uses the existing owner store (or a
separate projection log during retry), not the sealed correctness journal.

### Core loop

```python
while not terminal:
    acquire_or_confirm_single_owner()
    reconcile_journal_processes_workcell_and_thread()
    enforce_budgets_and_stop_request()
    gate = goal_gate.evaluate(current_workspace)
    if gate.green:
        freeze_commit_and_reproduce_or_continue()
    else:
        start_or_resume_thread()
        send_one_turn(compact_failure_context(gate))
        await_bounded_terminal_turn_event()
        record_observations()
```

GoalGate runs before the first turn, after every completed/failed/interrupted
turn, after recovery, and after the local candidate commit. A model
`reported_complete` event only requests immediate verification.

If a token event may have been lost at death, the unresolved turn is charged at
the configured conservative per-turn ceiling. Budget accounting is never
optimistically reconstructed.

### CLI

```text
dgc rudra run <mission.yaml>
dgc rudra status <mission-id> [--json]
dgc rudra stop <mission-id> --reason <text>
```

`run` is foreground in v0. It acquires the mission lock before resolving the
durable current-attempt pointer; relaunching the same admitted mission recovers
that attempt, while a conflicting contract/base under the same display ID is
rejected. Only the supervisor creates a new attempt after the previous one is
sealed.
`status` is read-only and reports `RUNNING` only when the kernel lock and full
process identity are fresh and consistent. Stale files alone yield
`RECOVERY_REQUIRED`. `stop` cannot signal any process until full identity
matching succeeds.

## 13. Recovery semantics

The central rule is absolute:

> After restart, no new model turn begins until the former process tree is
> proven dead. If death cannot be proven, recovery stops.

| Death window | Required recovery |
|---|---|
| Workcell created before admission result | Validate exact identity; adopt only if journal agrees, otherwise quarantine |
| `thread/start` accepted before thread ID result | Start no turn; discard/resume only after spike-defined reconciliation |
| `turn/start` accepted before response/journal result | Kill or rejoin old executor, inspect deterministic message ID, run GoalGate; never blindly resend |
| Tool mutation completed before observation | Reconcile Git and run GoalGate; do not replay the tool call |
| Supervisor killed while descendants live | Acquire lock, exactly identify old group, terminate and prove zero descendants, then reconcile |
| App-server killed mid-turn | Reap group, run GoalGate, resume proven thread or use one compact fresh handoff |
| Verifier killed | Discard partial result and rerun from the beginning after workspace rehash |
| Gate passed before candidate commit | Recheck and repeat freeze sequence; old pass cannot promote |
| Candidate committed before terminal event | Stop model processes, rerun all verifiers against candidate, then append terminal |
| Terminal event before later projection | Preserve local terminal; retry projection idempotently after v0 proof |
| Torn final journal row | Preserve tail, truncate to valid offset under lock, fsync, append repair event |
| Corrupt middle row or identity mismatch | `FAILED_INVARIANT`; no inferred transition |
| Reused or ambiguous PID | `RECOVERY_REQUIRED`; signal nothing |

RUDRA claims at-least-once model-turn intent with reconciliation, not arbitrary
exactly-once tool execution. v0 has no external effects, and final promotion is
exactly-once by terminal journal semantics.

## 14. Multi-agent build execution

The build uses parallel agents without sharing mutable files.

### Roles

- **Integration Captain:** owns admission, package exports, `dgc_cli.py`, final
  joins, any cross-packet interface change after GoalGate lands, real-provider
  execution, and the final receipt. The initial strict contract types belong to
  the GoalGate packet.
- **GoalGate Builder:** owns contract parsing and independent evaluation.
- **Protocol Builder:** owns the app-server spike and narrow driver.
- **Recovery Builder:** owns workcell, lock, journal, and process recovery.
- **Verification Spear:** begins after the first join; owns adversarial and
  fault-injection tests and does not edit production modules.

With four live agent slots, the captain runs three workers per wave. Every
worker is told that it is not alone, owns only its listed paths, must preserve
sibling changes, and must hand back a commit SHA plus exact evidence.

### Ordering

1. Human-ratified ownership amendment merges.
2. Captain creates one clean integration worktree at fresh `origin/main` and
   records the build base.
3. Protocol, containment/credential, and runtime/fixture spikes run in disjoint
   report-only lanes before framework code.
4. GoalGate and its false-completion negative fixture turn green.
5. Root reviews and freezes the Driver–Workcell interfaces from `contracts.py`;
   only then do CodexDriver and Workcell packets run in parallel in separate
   worktrees.
6. Captain cherry-picks one packet at a time, running its focused tests after
   every join.
7. Captain writes runner and CLI integration; no packet worker edits shared
   seams.
8. A fresh Verification Spear attacks the combined result.
9. Real-task A/B and forced-kill proof run only after the mutant/recovery suite
   is green.
10. Mission Control projection is considered only after the local A/B proof.

`WORK_PACKET_DAG.yaml` is normative for paths, dependencies, verification, and
stop conditions.

## 15. Governance admission

At the assessment base, `ACTIVE_TRACK.yaml` has ten active tracks, its configured
maximum. New RUDRA and CLI paths are unowned; `runtime_state.py` is
`organism-rewire`-owned, `orchestrator.py` and `pyproject.toml` are
Dharmagraph-owned, and `sandbox.py`/`autonomous_agent.py` are Titanium-owned.

The recommended two-PR route is:

### PR A — authority only

Human-ratified amendment to `organism-rewire-2026-07`:

- add one bounded RUDRA next item;
- add only `dharma_swarm/rudra/**`,
  `dharma_swarm/terminal_commands/rudra.py`, the narrow `dgc_cli.py` seam,
  `tests/test_rudra_*.py`, `tests/fixtures/rudra/**`, and `reports/rudra/**` to
  owned surfaces;
- state all v0 non-goals from this spec;
- render managed includes and pass governance checks.

If the operator rejects this home, one existing track must be retired or another
existing owner selected explicitly. No new eleventh track is silently created.

### PR B — product

After PR A is human-merged, recompute `origin/main`, create fresh packet
worktrees, and implement the DAG. Preflight requires the exact merged base,
matching branch, clean worktree, and current sibling-surface collision check.

The first real NEW-12-equivalent repair touches Titanium-owned code. It is a
separate admitted work packet after RUDRA itself is built; if Titanium does not
admit it, select another real baseline-red repair.

## 16. Phase gates

### Gate 0 — authority and environment

- explicit track owner/surfaces merged;
- exact build base clean and current;
- Python ≥3.11 plus lock, installed-distribution/RECORD, `.pth`, `sys.path`,
  plugin, and import-origin manifests bound;
- Codex version/schema digest bound;
- configured model/provider/effort/tier feature-probed;
- no enabled MCP/plugin/app or external-action surface, and credential canaries
  are unreadable to tools;
- real repair baseline revalidated red.

### Gate 1 — protocol and containment spike

- harmless turn completes through app-server;
- same-thread client/server restart is characterized;
- deterministic message ID resolves ambiguous delivery or fresh-handoff path is
  selected;
- mutation-workcell write succeeds, unauthorized path/credential reads and
  writes plus tool egress fail;
- supervisor/app-server/tool death leaves zero descendants;
- a `setsid` escape is prevented or enumerated and killed;
- every approval/user-input/tool escalation fails closed without hanging.

Failure selects the bounded fallback or stops the build; it never creates a
custom session or sandbox framework.

### Gate 2 — evaluator and recovery

- executor self-report with red verifier cannot complete;
- zero false green across the adversarial corpus;
- 32 barrier-synchronized nonblocking lock contenders × 200 rounds yield one
  held winner and 31 observed losers in every round;
- at least five acknowledged kills at each of the 20 durable cutpoints (at least
  100 total) replay successfully with seeded coverage;
- replay is deterministic and idempotent;
- no base or unauthorized mutation and no surviving descendant.

### Gate 3 — real vertical slice

- three RUDRA attempts and three direct-control attempts use the same exact base,
  model, effort, containment, gate, and total token/wall/resource budgets;
- arm order is alternated or randomized;
- one RUDRA and one direct-control attempt are killed at matched active-work
  cutpoints;
- RUDRA closes 3/3 with no test edits or human steering;
- required assertions execute and pass;
- every terminal has exact fresh proof;
- token/time/intervention/truth-gap metrics are complete.

Three pairs are a smoke proof, not statistical evidence.

The direct control is one bare app-server trajectory launched by a minimal
non-RUDRA harness: one thread, one initial objective, no supervisor-run iterative
GoalGate feedback, and one independent GoalGate after the model stops. It shares
RUDRA's model/provider/effort/tier, mutation workcell design, tool network,
resource caps, and total wall/token budget; “turn count” is not claimed equal
because verifier-feedback turns are the treatment. One control run is killed at
the matched mutation point and the same app-server resume primitive is attempted,
so recovery comparisons have a denominator. Missing usage is charged at the
admitted per-turn ceiling in both arms.

### Gate 4 — trusted v0

RUDRA may be called a trusted v0 only if it has zero false greens, duplicate
effects, overlapping owners, base writes, unauthorized writes, containment escapes,
conflicting terminals, corrupt-record skips, and leaked descendants. It must
provide more honest recovery/closure than direct Codex and cost no more than 2×
tokens.

## 17. Earned power after v0

The monster grows by measured gradients, not new nouns.
Everything in this section requires a new governed goal; none of it is a packet
or implied continuation in the v0 DAG.

### After 30 replayable single-workcell missions

Admit a two-worker DAG only for provably disjoint write sets. Each worker gets a
separate private workcell and candidate commit; one integration writer composes
them; the final gate runs in a fresh detached integration workcell. Before cross-process
dispatch, add database-enforced one-active-owner CAS to the existing owner store.
Then, and only then, connect the existing Orchestrator/Mission Control adapter.

Keep parallelism only if an A/B set improves verified closure by at least 15
percentage points or wall time by at least 30%, at no more than 2× tokens.

### Selective trajectory compute

Once a fast executable gate exists, difficult repairs MAY fork a small number of
fresh candidate threads/workcells under one token budget. Candidates are ranked
by executable gate first and deterministic secondary metrics second. Model
votes never override a red gate. This is the power lesson from frontier agent
systems: spend compute on independently testable trajectories, not council
prose.

### After local durability empirically fails

Consider Temporal only for multi-host work, long external waits, or at least one
failure among 100 forced local restarts that a simpler fix cannot address.

### After a packageable multi-process service exists

Consider Antithesis for deterministic concurrency testing. Consider a borrowed
VM/container for hostile inputs. A custom VMM is revisited only for a measured
whole-system deterministic-replay requirement that established substrates
cannot satisfy.

### After 100 replayable traces and 50 held-out tasks

Consider shadow evolution only for a recurring failure class representing at
least 20% of failures. Promotion requires at least 10% relative held-out
improvement over three seeds with no safety regression.

## 18. Stop and deletion rules

Stop the current attempt immediately on:

- executor write outside the mutation workcell/admitted repository set or
  supervisor write outside the state root;
- external-action attempt or unauthorized tool network;
- dangerous-full-access or sandbox fallback;
- unresolved former process tree;
- journal, workcell, base, thread, executable, or contract identity mismatch;
- changed tests, verifier, Git control surface, or forbidden path;
- corrupt middle journal record;
- inability to kill/reap descendants;
- any admitted budget exhaustion; or
- hostile/untrusted risk classification.

Stop the build for a deletion review if production hot-path code exceeds 1,000
lines before a real mission runs.

Retire the RUDRA wrapper and keep GoalGate if:

- any false green, unauthorized write, containment escape, or conflicting accepted
  terminal occurs;
- verified recovery/closure does not improve over direct Codex; or
- token cost exceeds 2× direct Codex; or
- correctness requires another scheduler, task store, authority layer, session
  framework, or custom sandbox before the first repair closes.

## 19. Evidence anchors at assessment base

- Existing CLI entry point: `pyproject.toml:58-60`; parser/dispatch seams:
  `dharma_swarm/dgc_cli.py:240-247,1339-1414`.
- Existing state-root resolver: `dharma_swarm/daemon_config.py:20-26`.
- Reusable process-group cleanup:
  `dharma_swarm/sandbox.py:34-78`; do not reuse its automatic sandbox selection.
- Existing `spine.identity.process_boot_id()` is process-local and MUST NOT be
  reused as OS boot identity: `dharma_swarm/spine/identity.py:197-210`.
- Mission Control explicitly describes itself as projection, not scheduler or
  liveness proof: `dharma_swarm/mission_control.py:1-19,79-99`.
- Existing runtime owners: `dharma_swarm/runtime_state.py:610-723,1209+`.
- Existing `AsyncFileLock` stale-unlink behavior is unsuitable:
  `dharma_swarm/file_lock.py:87-129,184-250`.
- Existing event log lacks the required complete-write/fsync recovery contract:
  `dharma_swarm/event_log.py:20-74`.
- Silent Docker-to-local fallback is forbidden precedent:
  `dharma_swarm/sandbox.py:254-292`.
- Current generated app-server schema includes the required thread/turn methods
  and explicitly unsandboxed `thread/shellCommand`:
  `/private/tmp/rudra_codex_schema_probe_20260814/`.
- Full prior evidence and reproductions:
  `/Users/dhyana/rudra_assessment_20260814/`.
