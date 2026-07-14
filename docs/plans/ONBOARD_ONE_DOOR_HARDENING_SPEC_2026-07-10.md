# One-Door Onboarding Hardening — Execution Specification (2026-07-10)

**Role:** `working_plan` — the implementation prerequisite for hardening the
existing `make onboard` session doorway before Titanium vNext captures a
dynamic baseline or begins WP-00. This document specifies work; it implements
nothing.

**Evidence baseline:** all repository claims in this revision were checked at
`5e7304c7df36b0fe6a34ae458b6cc0212b2106b6`, the remote head of
`claude/make-onboard-hardening-n1ww1s` at the start of the refinement. The
refinement commit changes only this file, so cited code lines remain the
reviewed lines.

**Authority precedence:** executable code, tests, locks, git state, and the
single owner files named by `docs/governance/CANONICAL_DOC_STACK.md` win.
`make onboard`, orientation output, generated reports, caches, and receipts are
projections; they never outrank their owners and never certify themselves. The
owner map and coding contract define that precedence
(`docs/governance/CANONICAL_DOC_STACK.md:52-70`, `CLAUDE.md:5-16`), and the
current scripts state the projection boundary explicitly
(`scripts/governance/agent_onboard.py:5-20`,
`scripts/governance/orientation_graph.py:10-20`).

**Hard boundary:** extend the existing doorway, AgentOps packet machinery,
receipt path, digest primitive, owner files, and `needs_host` vocabulary. Do
not create another governance framework, policy engine, truth owner, receipt
store, parser family, or digest primitive. Do not begin Titanium. Do not make
production or `CLOSED_LIVE` claims.

---

## §0 Admission and use of this specification

1. D1 in §9 must be resolved through a governance-only admission PR before
   any WP-O1, WP-O1R-B0, WP-O1R, or WP-O2..O6 implementation edit. Track
   admission is not a one-line act:
   changing `ACTIVE_TRACK.yaml` requires regenerated managed blocks in
   `CLAUDE.md`, `SOVEREIGN_MANIFEST.md`, and
   `BUILD_SESSION_ENTRYPOINT.md`
   (`scripts/governance/render_active_track_includes.py:40-46`).
2. Before an implementation agent edits, it must supply the exact Session
   Entry Packet in §4. That packet extends the existing AgentOps JSON contract,
   not a prose self-attestation.
3. Each packet is independently reviewable. Merge dependencies are explicit
   in §6. WP-O5, the strict-by-default promotion, remains isolated and requires
   D2.
4. Every factual claim must be rechecked at the implementation-entry SHA. This
   baseline is dated evidence, not permanent truth.
5. If a required change falls outside a packet envelope or into a sibling
   active track, stop. Narrow the behavior, land the named prerequisite, or ask
   the operator; do not widen a packet during implementation.

## §1 Measured current state and claim adjudication

### 1.1 Session record (2026-07-10)

The required first repository workflow command was run in a fresh,
single-branch clone whose local and remote heads both resolved to
`5e7304c7df36b0fe6a34ae458b6cc0212b2106b6` and whose tracked worktree was
clean.

| Item | Reproducible observation |
|---|---|
| Host class | Linux x86_64, kernel `6.12.47`; fresh single-branch, blob-filtered clone; `git rev-parse --is-shallow-repository` returned `false` |
| Tool command | `python3 --version; make --version; git --version; rg --version; uv --version; command -v pytest pre-commit gh bun` |
| Present versions | Python 3.12.13; GNU Make 4.3; git 2.51.1; ripgrep 14.1.0; uv 0.9.25 |
| Missing command-line tools | `pytest`, `pre-commit`, `gh`, and `bun` were absent from `PATH` |
| Required first command | `AGENT_ONBOARD_NO_REFRESH=1 make onboard` |
| First-command result | exit 0; 1.8 s wall; 325 output lines |
| Cold-refresh probe | `DHARMA_OPS_DIR=/tmp/pr855-ops-run1 make onboard` with generated evidence absent: exit 0; 25 s by shell `SECONDS` (1 s resolution); 466 lines |
| Immediate repeat | same checkout after evidence generation: exit 0; 1 s by shell `SECONDS` (1 s resolution); 466 lines |
| Validation bootstrap | Initial `uv sync --frozen --extra dev` exit 2 because `/root/.cache/uv` was read-only; `UV_CACHE_DIR=/tmp/pr855-uv-cache uv sync --frozen --extra dev` exit 0 in 8.1 s |
| Validation-only versions | pytest 9.0.3; ruff 0.15.16; Hypothesis 6.155.7; mutmut 3.6.0; externally cached pre-commit 4.6.0 |

The intentionally no-refresh first command reported missing active-track
evidence and live census; missing runtime/ontology databases; a missing
trust-gate receipt; missing/stale provider-key status; unavailable `gh`; and
missing `fastapi`/`textual` imports. It rendered committed or host-local
snapshots where present, which are informational only. It could not write the
default receipt because `/root/.dharma` was read-only. These states were all
compatible with exit 0. The later cold refresh—not the no-refresh command—also
attempted criteria requiring unavailable `pytest` and `bun`.

The cold probe created the refresh command's three intentionally ignored
governance rollups (`reports/governance/active_track_evidence.{json,md}` and
`track_portfolio.json`; `.gitignore:130-139`). A transitive criterion also
created ignored `reports/governance/trust_gate_status.json`; this is why the
write claim is not limited to the refresh function's direct outputs. The probe
attempted every active-track criterion, including commands requiring
unavailable `pytest` and `bun`.
The immediate repeat skipped that refresh because the 60-minute
evidence-freshness TTL was satisfied
(`scripts/governance/agent_onboard.py:69,527-547,1735-1745`). Therefore an operational
freshness shortcut exists today, but no receipt-backed general cache or
explicit warm mode exists.

Absence/consumer controls at the same SHA were reproducible:

```bash
git ls-files --error-unmatch AGENTS.md        # exit 1
test -e AGENTS.md                             # exit 1
rg -n 'stable_digest|required_reading.*digest|source_hash|sha256' \
  scripts/governance/agent_onboard.py scripts/governance/orientation_graph.py
# exit 0; one orientation packet context sha256 at orientation_graph.py:896,
# no per-first-read owner digest
rg -n --hidden --glob '!.git/**' \
  --glob '!docs/plans/ONBOARD_ONE_DOOR_HARDENING_SPEC_2026-07-10.md' \
  'onboard_receipt|dharma_swarm\.onboard_receipt\.v[0-9]+' .
# exit 0; ten matches: four writer/script lines, five test lines, one tracked
# stdout snapshot; zero in-repository production reader implementations
```

After frozen default-dependency bootstrap, the dated parser audit directly
called all six current consumers and a stdlib current-record adjudicator:

```bash
UV_CACHE_DIR=/tmp/pr855-uv-cache uv run --frozen python - <<'PY'
from pathlib import Path
import re
from scripts.governance import agent_onboard as ao, orientation_graph as og
from scripts.governance import repo_status as rs, trust_gate_status as tg
from dharma_swarm.operator_core import control_surface as cs
from dharma_swarm.operator_core.operator_coherence.base import ProbeContext
from dharma_swarm.operator_core.operator_coherence.git_governance import _probe_governance
root=Path.cwd(); path=root/'docs/state/BROKEN_REGISTER.md'; a=ao._parse_broken_register()
print('consumers', (a['total'],a['open_count'],a['closed_count']),
      len(og.build_broken()), tg.parse_broken_counts(path),
      rs._count_broken_register(), len(cs._broken_register_rows(root)),
      _probe_governance(ProbeContext(repo_root=root,include_github=False,
        include_live_probes=False))['broken_register']['open_like_count'])
lines=path.read_text().splitlines(); phase='pre'; rows={}
for i,line in enumerate(lines):
    if line.startswith('## OPEN'): phase='current'
    elif line.startswith('## CLOSED'): phase='closed'
    elif line.startswith('## STALE-CLAIM'): phase='done'
    m=re.match(r'^### (BR-\d+)',line)
    if not m or phase=='done': continue
    if phase=='closed': rows.setdefault(m.group(1),'CLOSED'); continue
    body='\n'.join(lines[i+1:i+20])
    sm=re.search(r'^- \*\*status:\*\*\s*\**([A-Z]+)',body,re.M|re.I)
    rows[m.group(1)]=sm.group(1).upper() if sm else 'UNKNOWN'
open_like={'OPEN','PARTIAL','INVESTIGATING','WORKAROUND'}
print('adjudicated',len(rows),sum(v in open_like for v in rows.values()),
      sum(v not in open_like for v in rows.values()))
PY
# exit 0
# consumers (27, 9, 8) 17 (27, 9, 8) (22, 10) 8 19
# adjudicated 22 9 13
```

These are measurements at the recorded SHA, not new parser semantics.

### 1.2 Claims re-adjudicated at the recorded SHA

Counts: **CONFIRMED 4 · CORRECTED 7 · NARROWED 3 · UNRESOLVED 0**.

| Prior claim | Verdict | Current ground truth |
|---|---|---|
| `agent_onboard.py` is about 1,800 lines | CONFIRMED | 1,883 lines; `orientation_graph.py` is 1,149 lines (`scripts/governance/agent_onboard.py:1883`, `scripts/governance/orientation_graph.py:1149`). |
| Normal output is 327 lines | CORRECTED | Measured output was 325 lines with no refresh/missing evidence and 466 lines after evidence generation. Output is state-dependent. |
| Cold is 31–32 s and no warm path exists | CORRECTED | Measured missing-evidence refresh was 25 s and the immediate repeat 1 s. There is no receipt cache, but the 60-minute evidence shortcut is operationally warm. The prior attribution to render cost was unsupported. |
| Onboarding refreshes through `check_track_status.py --warn-only` | CONFIRMED | The subprocess has a 30-second timeout (`scripts/governance/agent_onboard.py:1630-1637`) and is selected by the freshness/force/skip logic (`scripts/governance/agent_onboard.py:1735-1745`). |
| Refresh timeout and `OSError` are swallowed | CONFIRMED | Both are silently ignored (`scripts/governance/agent_onboard.py:1636-1639`); return code and output are also absent from the final verdict. |
| Stale state always exits 0 and the test proves stale behavior | NARROWED | Successful normal/JSON paths return 0 despite stale evidence (`scripts/governance/agent_onboard.py:1740-1763,1824-1830`), but the cited test invokes the current repo and does not construct stale state (`tests/test_agent_onboard.py:44-53`). Unhandled failures can still exit nonzero. |
| `gh pr list` is the one network call and `--no-net` is hermetic | CORRECTED | `gh pr list` is the only direct network subprocess (`scripts/governance/agent_onboard.py:1347-1385`), but hidden refresh evaluates arbitrary `command_passes` criteria (`scripts/governance/check_track_status.py:464-501,1992-2018`), including `bun install` in the live portfolio (`docs/governance/ACTIVE_TRACK.yaml:993-1007`). `--no-net` is not network-hermetic. |
| The receipt is written every run; refresh writes two ignored files; orient writes tracked context | CORRECTED | Receipt writing is attempted and may fail (`scripts/governance/agent_onboard.py:1695-1710`). Refresh writes three ignored rollups plus any transitive criterion side effects (`scripts/governance/check_track_status.py:2145-2187,2232`). `make orient` does write both tracked context files (`Makefile:440-444`, `scripts/governance/orientation_graph.py:902-910`). |
| `verifier-selfcheck` omits `test-fast` and swallows a failed onboard | CORRECTED | It runs compile, F821, pytest collection, and onboard, not `test-fast` (`Makefile:142-143,158-169`). But `command && echo` propagates a nonzero left-hand status; current Make does not swallow it. |
| `tests/test_agent_onboard.py` specifically pins stale-state exit 0 | NARROWED | It pins generic end-to-end exit 0 only (`tests/test_agent_onboard.py:44-53`). |
| Orientation returns 0 in normal modes | CONFIRMED | Human, JSON, graph, write, and measure paths return 0; query miss returns 1 and argparse usage errors return 2 (`scripts/governance/orientation_graph.py:1109-1145`). |
| Root `AGENTS.md` is an internally coherent registered-canon repair | NARROWED | It is absent and registered, and orientation reports it missing (`docs/docops/assertions.yaml:98-105,127-163`; `scripts/governance/orientation_graph.py:590-605,1010-1017`). DocOps does not currently detect a missing registered file, and Rule 8 CI does not allow `AGENTS.md` (`.github/workflows/structure.yml:36-50`; `scripts/docops/check_docops_integrity.py:95-126,360-402`). |
| Bold fixed statuses create only a latent defect in one parser | CORRECTED | The defect is live. BR-009 and other current entries use bold fixed statuses (`docs/state/BROKEN_REGISTER.md:114-123`); orientation misclassifies eight fixed entries and there are at least six parsers (§1.3). |
| Host absence is already coherently typed or neither command emits RED | CORRECTED | Neither command emits `NEEDS_HOST`; host absence is untyped prose/missing data with exit 0 (`scripts/governance/agent_onboard.py:703-729`; `scripts/governance/orientation_graph.py:608-636,1019-1024`). Onboarding can separately echo RED from a trust-gate projection (`scripts/governance/agent_onboard.py:830-860`). |

### 1.3 Structural findings that control the design

1. **Six direct broken-register parsers exist.** They are:
   `scripts/governance/agent_onboard.py:783-813`,
   `scripts/governance/orientation_graph.py:639-662`,
   `scripts/governance/trust_gate_status.py:241-265`,
   `scripts/governance/repo_status.py:100-128`,
   `dharma_swarm/operator_core/operator_coherence/git_governance.py:255-277`,
   and `dharma_swarm/operator_core/control_surface.py:687-776`. Their current outputs disagree:
   orientation returns 17 open-like rows; onboard/trust count 27 occurrences
   as 9 open, 8 closed, 10 unknown; repo status returns 22 unique/10 open;
   control surface returns 8 rows; operator coherence returns 19. The register
   contains 22 distinct IDs, 9 current open-like IDs, and 13 current
   closed-like IDs. WP-O2 must consolidate all six, not only the onboarding
   pair.
2. **The exit namespace has existing meaning.** Argparse already owns exit 2
   for usage (`scripts/governance/agent_onboard.py:1726-1729`), and the sibling Pramana gate owns
   exit 3 for malformed gate configuration (`scripts/governance/pramana_probe.py:29-33,377-383`).
3. **Preflight renders onboarding twice.** `agent-build-preflight` depends on
   both `verifier-selfcheck` and `onboard` (`Makefile:422-423`), while
   `verifier-selfcheck` invokes onboard itself (`Makefile:167-168`). Current
   preflight does not check exact base, declared envelope, ownership collision,
   or required tool versions. Current closeout runs hygiene plus
   `governance-all` only (`Makefile:425-428`).
4. **Three distinct Make entrypoints are intentional.** `make onboard` is
   session orientation, `make orient` is the whole-system projection, and
   `make agent-onboard` is persistent A2A identity join (`Makefile:433-452`).
   The latter is not part of this campaign. Other legacy scripts exist, so the
   claim is limited to Make targets.
5. **Per-required-reading hashing is absent, not hashing in general.**
   Orientation computes a packet context hash (`scripts/governance/orientation_graph.py:879-899`),
   but neither entry command emits a content digest per canonical first-read
   owner.
6. **No in-repository production receipt reader exists.** The writer and schema
   are at `scripts/governance/agent_onboard.py:1695-1710,1833-1879`; the only executable reader is
   the exact-schema test (`tests/test_agent_onboard.py:339-378`). The docstring's
   fleet-consumer statement (`scripts/governance/agent_onboard.py:17-20`) is uncorroborated
   off-repo behavior. D3 blocks the v2 writer flip until external consumers are
   inventoried or the operator confirms there are none.
7. **An envelope engine already exists.** AgentOps parses JSON work packets and
   fail-closes on allowed/forbidden working, staged, and untracked paths
   (`scripts/governance/run_agent_work_packet.py:279-338,354-385`;
   `docs/governance/AGENTOPS.md:47-68`). It must be
   extended to include committed `baseline...HEAD` diffs; it must not be
   replaced.
8. **Instruction adapters conflict with this session discipline.** `DEVIN.md`
   hard-codes `/home/ubuntu/repos/dharma-swarm`, pulls `main` before onboarding,
   and encourages adjacent expansion (`DEVIN.md:20-35,57-63`). `QWEN.md`
   hard-codes a Mac path, stale branch, and dirty-state assertion
   (`QWEN.md:3,14-16`). `docs/AGENTS.md` says onboarding output wins over
   conflicting prose even though its own authority section names the canonical
   owner map (`docs/AGENTS.md:14-26`). These are dependencies A1/A2/A4 in §9,
   not scope for this implementation campaign.
9. **The repository contains an urgent control-plane configuration risk.** The
   web image binds FastAPI to `0.0.0.0:8080` (`Dockerfile:29-40`), Compose
   publishes it on host port 8080 without passing the dashboard auth key
   (`docker-compose.yml:58-70`), and the API disables all auth when the key is
   absent (`api/main.py:216-241`) while exposing mutating command endpoints
   (`api/routers/commands.py:17-28,101-107`). The VPS bootstrap intends SSH-only
   firewall access (`scripts/ops/vps_cloud_init.yaml:85-98`), so actual public
   reachability is not proven from this checkout. U1 in §9 requires immediate
   operator verification and containment if reachable; this spec does not
   absorb the security fix.

## §2 Target responsibilities — one door, separable internals

| Surface | Sole responsibility | Must not do |
|---|---|---|
| `make onboard` | Memorable, compact, deterministic session-status doorway; evaluates the shared admission contract and emits typed conditions | No network, hidden refresh, tracked-file write, generated-artifact write, or self-certification |
| `make orient` | Deeper mutation-free projection over the same normalized packet | No admission-policy fork and no tracked write by default |
| `make agent-build-preflight PACKET=<path>` | Fail-closed edit admission: exact baseline, packet, toolchain, collision, and clean envelope | No duplicate onboarding run; no prose-only scope attestation |
| `make agent-build-closeout PACKET=<path>` | Fail-closed PR admission: same packet digest, committed+working diff envelope, packet gates, and governance closeout | No merge/push and no weaker scope interpretation |
| CI | Re-run the same pure evaluator and AgentOps envelope over the PR base/head | No local-receipt trust, author-only green, or `continue-on-error` |
| `make agent-onboard` | Existing persistent A2A identity join | No change in this campaign |

“One door” means one public session doorway, not one god script. Contract
loading, evidence collection, canonical parsing, readiness policy, receipt
cache/delta, rendering, and explicit generated-artifact refresh remain
separable and independently testable.

### 2.1 Command contract

| Command | Network | Tracked writes | Admission meaning |
|---|---:|---:|---|
| `make onboard` | No | No | Strict compact status for hermetic session scope |
| `make onboard ARGS=--json` | No | No | Byte-stable machine output; volatile metadata remains only in the external receipt |
| `make onboard ARGS=--deep` | No | No | Detailed view over the same packet and verdict |
| `make onboard ARGS="--deep --net"` | Explicit opt-in | No | Adds non-admission PR context; network results never change READY |
| `make onboard ARGS=--require-live` | No | No | Host gaps required by selected live scope become exit 4 |
| `make onboard ARGS="--packet <json>"` | No | No | Validate and bind the Session Entry Packet; does not replace preflight |
| `make orient` | No | No | Deep mutation-free projection |
| `python3 scripts/governance/orientation_graph.py --write-context` | No | Exactly the two legacy tracked projections | Explicit maintenance refresh only; never called by entry, preflight, closeout, or CI |

`--fast` maps to the compact default with one deprecation line. `--no-net` is a
no-op alias because the default is already network-off. Unknown flags retain
exit 2. The parser records usage errors rather than exiting before safe,
non-mutating state collection, so secondary observed conditions can appear in
the receipt.

### 2.2 Write and refresh doctrine

- Default onboard, orient, preflight evaluation, closeout evaluation, and CI
  evaluation attempt no write anywhere under the worktree or `.git`, including
  ignored files and byte-identical rewrites. Tests use a filesystem write guard
  in addition to porcelain comparison.
- Hidden `check_track_status --warn-only` refresh is removed. Missing or stale
  generated evidence is a typed condition; it is never regenerated inside the
  doorway.
- Generated active-track and orientation artifacts have explicit owner
  commands. Their output cannot confer READY without producer, input-digest,
  HEAD, and TTL binding; current rollups contain no HEAD/input digest
  (`scripts/governance/check_track_status.py:2161-2187`).
- The one receipt path remains `~/.dharma/ops/onboard_receipt.json`, with
  `DHARMA_OPS_DIR` honored only after the resolved directory is proven outside
  the worktree and `.git`. Direct and symlink escapes into the repository are
  `CONFIG_ERROR`.
- A receipt-write failure is visible and blocks receipt-backed edit admission.
  It is never printed as a harmless note beside READY.
- If the path is invalid or persistence fails, the fully assembled would-be v2
  condition object is still emitted by `--json` (and summarized in human
  output), including the persistence condition and all secondary states. The
  stale prior receipt is neither trusted nor replaced, and no fallback receipt
  store is created.
- The legacy orientation refresh stays explicit and may dirty the worktree by
  design; callers must commit or revert that owner-generated change before
  admission.

### 2.3 Exit status and lossless condition set

| Exit | Primary result | Meaning |
|---:|---|---|
| 0 | `READY` or non-required `NEEDS_HOST` | Every check required for selected scope passed; optional host gaps remain typed, never pass-like |
| 1 | `BLOCKED` | Dirty/wrong base, ownership or envelope conflict, stale mandatory projection, failed sentinel, receipt corruption/write failure, skipped mandatory check, or sprawl violation |
| 2 | usage error | Unknown/malformed CLI arguments; existing argparse namespace retained |
| 3 | `CONFIG_ERROR` | Missing/malformed/contradictory owner config, invalid receipt path, or phantom sentinel target |
| 4 | `NEEDS_HOST` | `--require-live` selected and a required owner-host capability is unavailable |
| 5 | `TOOLCHAIN_MISSING` | Universally required hermetic tool/version is absent or outside its supported range |

Scalar precedence is fixed:

```text
usage(2) > CONFIG_ERROR(3) > TOOLCHAIN_MISSING(5) > BLOCKED(1) > NEEDS_HOST(4)
```

The receipt also carries every observed condition, sorted by stable ID. The
winning scalar exit never deletes secondary states. Required multi-condition
tests are:

| Scenario | Scalar exit | Conditions retained |
|---|---:|---|
| malformed flag + ownership conflict | 2 | `usage_error`, `ownership_conflict` |
| malformed config + missing required tool | 3 | `config_error`, `toolchain_missing` |
| stale valid cache + unavailable required live host | 1 | `stale_cache`, `needs_host` |
| missing required tool + failed sentinel | 5 | `toolchain_missing`, `sentinel_failed` |
| partial evidence read + non-required host gap | 1 | `evidence_incomplete`, `needs_host` |

Check states are exactly `pass|fail|warn|needs_host|skipped|not_observed`.
`skipped` and `not_observed` require reasons. A mandatory warn/skip/unavailable
check cannot produce READY. An explicitly optional warn remains `warn`; it is
never counted as pass. `NEEDS_HOST` remains exit 0 only for a scope that does
not require that host, matching the existing run-level precedent
(`scripts/loop5b_world_radar_closure_run.py:257-270`); onboarding's exit-4 mapping is
new.

### 2.4 Host vocabulary — adopt, do not invent

Reuse the existing chain:

- capability token `needs_host` and empty invocation when a host tool is absent
  (`dharma_swarm/world_radar/go_invoke.py:30-56`);
- typed structured source error rather than attempted execution
  (`dharma_swarm/world_radar/go_invoke.py:95-107,182-187`);
- gap code plus `next_action` at the control surface
  (`dharma_swarm/operator_core/control_surface_go.py:159-197`);
- run-level `NEEDS_HOST`, nonzero only when live scope is required.

Gap codes are task-relevant, for example
`onboard_needs_runtime_db`, `onboard_needs_daemon_census`,
`onboard_needs_provider_keys`, `onboard_needs_nats`, and
`onboard_needs_deploy_receipt`. An actually executed live check that fails is
`fail`, never `needs_host`. Unmeasured never renders green, following the
existing RED-if-unmeasured doctrine (`scripts/governance/trust_gate_status.py:18-21`).

### 2.5 Human and JSON output

Human stdout is 40–70 lines inclusive, hard-capped by a test. Diagnosis is
printed before any nonzero exit. Detail goes to `--deep` and the receipt.

```text
DHARMA ONBOARD — BLOCKED (exit 1)

Repo:    claude/example @ <40-char-sha>, clean, base matches
Scope:   hermetic · packet WP-O3 · packet digest <sha256>
Track:   onboard-one-door-2026-07 · owner @AmitabhainArunachala
Allowed: 11 patterns · Forbidden: 9 sibling-track patterns

Primary blocker: stale mandatory projection
Also observed: 2 needs_host · 1 optional warning · 0 skipped mandatory

Changed since prior valid receipt:
  + blocker: active_track_projection_stale
  ! rule digest: CLAUDE.md

Required reading (canonical max-five):
  onboard output · CLAUDE.md · SWARM_GENOME.md · ACTIVE_TRACK.yaml · ANTI_SLOP_RULES.md

Next: repair blocker, rerun make onboard, then
      make agent-build-preflight PACKET=<path>
```

The required-reading set exactly follows the canonical max-five list
(`docs/governance/CANONICAL_DOC_STACK.md:32-43`). `AGENTS.md`,
`BUILD_SESSION_ENTRYPOINT.md`, the applicable platform adapter, relevant skill,
and mismatch map may be packet-specific depth reads, but they do not silently
replace a canonical first-read owner or create a sixth mandatory global
surface.

`--json` is a deterministic machine projection, not a byte dump of the full
v2 receipt. It contains the verdict, exit, normalized stable core, and current
condition IDs/states/reasons, all with declared ordering. It excludes
`observed_at`, numeric ages, durations, executable/temp/home paths,
cache-hit/miss bookkeeping, prior digest/delta, network result order, and all
filesystem mtimes/inodes/device IDs. Current orientation probes expose
`newest_mtime` (`scripts/governance/orientation_graph.py:268-324`); v2 static
surfaces replace it with content-derived identity, while freshness belongs only
in typed live metadata. The
full receipt retains those typed fields. JSON stdout performs no network
request and is byte-identical on repeated unchanged runs in the same
environment class.

## §3 Receipt v2, cache, determinism, and migration

### 3.1 One path, one versioned loader, two data partitions

Continue using `~/.dharma/ops/onboard_receipt.json`; do not add an onboarding
ledger, history file, or timing receipt. Import `canonical_json`,
`stable_digest`, and `utc_now` from
`dharma_swarm/memory_kernel/write_receipts.py:336-345`. `tam_ledger` and the
arena import `stable_digest`/`utc_now`
(`scripts/governance/tam_ledger.py:48-51`,
`scripts/governance/arena_truth_report.py:49-52`); onboarding adapts that primitive without
claiming TAM's volatile-field policy is identical. TAM's actual replay
exclusions are `generated_at` and `digest`
(`scripts/governance/tam_ledger.py:61-63`) and its replay contract is
`scripts/governance/tam_ledger.py:324-377`. The onboarding validation path
must reuse those `tam_ledger --check` semantics—digest verification,
recomputation against current owners, and fail-closed unknown root fields—while
keeping onboarding's schema and truth ownership distinct.

Required v2 shape:

```json
{
  "schema": "dharma_swarm.onboard_receipt.v2",
  "authority": "projection_only",
  "observed_at": "ISO-8601Z",
  "primary_verdict": "READY|BLOCKED|NEEDS_HOST|CONFIG_ERROR|TOOLCHAIN_MISSING|USAGE_ERROR",
  "exit_code": 1,
  "stable_core": {
    "repository": {"identity": "owner/repo", "head": "", "branch": ""},
    "contract": {"required_files": [], "source_hashes": {}, "contract_digest": ""},
    "packet": {"id": "", "digest": "", "track": "", "owner": "",
               "allowed_files": [], "forbidden_files": []},
    "portfolio": {"tracks": [], "selected_track": "", "ownership_conflicts": []},
    "orientation": {"identity": {}, "broken_register": {}, "static_surfaces": {}},
    "required_reading": []
  },
  "live_delta": {
    "repo_state": {"base": "", "dirty": false, "conflicted": false,
                   "ahead": 0, "behind": 0},
    "conditions": [],
    "host_gaps": [],
    "toolchain": {},
    "projection_freshness": {}
  },
  "cache": {
    "key": "",
    "hit": false,
    "miss_reasons": [],
    "input_manifest": {},
    "section_fingerprints": {}
  },
  "delta": {"previous_stable_digest": "", "added": [], "resolved": [], "changed": []},
  "legacy_v1": {"schema": "", "observed_at": "", "authority": "",
                "repo": {}, "work_lanes": {}, "portfolio": {},
                "next_items": [], "swarm_bulletins": [],
                "broken_register": {}, "open_prs": [],
                "runtime_truth_packets": []},
  "extensions": {},
  "stable_digest": ""
}
```

`stable_digest` is computed over `stable_core` only, before delta bookkeeping.
It excludes the receipt timestamp, cache hit/miss, live values, and previous
digest by construction, not by recursively dropping coincidentally named
keys. Live fields remain present and typed. Full receipt validation separately
checks schema, types, repository applicability, cache key, and stable digest.
A valid digest is integrity evidence only; it never grants READY.
`extensions` is the sole declared namespace for versioned auxiliary evidence;
unknown extension names remain non-admission and are preserved or refused by
explicit version negotiation, never interpreted as core fields.

### 3.2 Stored input manifest and invalidation closure

The cache is a performance hint for parsed/static sections only. Verdict,
repository state, required tools, packet/base match, collision, diff envelope,
mandatory sentinels, and selected host checks are recomputed every run.

The sorted `cache.input_manifest` records content hashes or normalized version
values for every transitive input actually consumed:

| Category | Required invalidators |
|---|---|
| Entry implementation | `Makefile`; onboarding package; legacy shims; canonical parser; `write_receipts.py`; every helper retained in compact/deep paths |
| Instruction custody | `CLAUDE.md`, root/docs `AGENTS.md`, applicable `DEVIN.md`/`QWEN.md`, `CANONICAL_DOC_STACK.md`, `ANTI_SLOP_RULES.md`, `BUILD_SESSION_ENTRYPOINT.md`, relevant skill files |
| Intent/surface/breakage | `ACTIVE_TRACK.yaml`, `ACTIVE_SURFACE_MANIFEST.yaml`, `BROKEN_REGISTER.md`, `VENTURE_CELL_PORTFOLIO.yaml`, `docs/docops/assertions.yaml`, `docs/governance/evidence_grades.yaml`, `INTERFACE_MISMATCH_MAP.md` when packet-relevant |
| Dependency contract | `pyproject.toml`, `uv.lock`, `.pre-commit-config.yaml`, selected interpreter/distribution versions, `git`/`make` versions, and every selected-scope lock/requirements file (for example `requirements-dev.txt`, `terminal/bun.lock`, or a package lock only when its consumer is selected) |
| Git/environment | repository identity, full HEAD/tree, branch/detached state, upstream/base, staged/unstaged/untracked/conflicted digest, `.gitignore`, `.git/info/exclude`, effective global excludes, normalized locale/timezone and scope flags |
| Dynamic owner closure | Sorted matches for owned-surface globs and every file/test/command/receipt/TTL resolved from the selected track/packet |
| Generated projection | Projection bytes plus producer version, source HEAD, owner-input digest, and expiry; if any binding is absent, it is ineligible for cache/admission use |

`section_fingerprints` map each static section to the exact manifest entries it
uses, making “reparse only affected sections” executable. Tool presence and
git state are both freshly probed even when their normalized values are also
part of the key.

Required cache negative controls:

- crash before replace; truncated JSON; wrong schema/type/digest;
- valid-digest but wrong repository/branch/HEAD/key;
- stale-but-valid payload and future timestamp beyond bounded clock skew;
- branch switch at the same path and clean→dirty→clean transitions;
- direct/symlink `DHARMA_OPS_DIR` inside the worktree or `.git`;
- two concurrent writers computing delta from the same predecessor;
- poisoned cached READY beside a current failed sentinel;
- projection without producer/input/HEAD binding;
- changed `pyproject.toml`, `uv.lock`, `.gitignore`, assertions, authority doc,
  owner glob match, tool version, environment class, or live-evidence TTL.
- identical file bytes with different mtimes/inodes across two clones; stable
  core/digest/output must remain equal.

Serialize read→delta→validate→replace with an existing sidecar `fcntl.flock`
pattern (`dharma_swarm/spine/receipt.py:281-296`); re-read under the
commit-phase lock. Atomic temp+replace remains mandatory. Concurrent
last-writer-wins without serialized predecessor selection is not
deterministic.

### 3.3 v1→v2 consumer matrix and safe sequence

| Consumer/case | Current evidence | Required migration behavior |
|---|---|---|
| `agent_onboard.py` writer | Sole v1 writer (`scripts/governance/agent_onboard.py:1695-1710,1833-1879`) | Keep v1 until versioned loader and D3 land; then switch the same path to v2 |
| `tests/test_agent_onboard.py` | Exact v1 schema observer (`tests/test_agent_onboard.py:339-363`) | Test v1 loader, v2 writer, corrupt/unknown majors, and legacy non-admission |
| In-repo production reader | None found | New cache/delta loader is the first; it branches on schema before fields |
| Possible off-repo fleet readers | Unverified assertions in `scripts/governance/agent_onboard.py:17-20` and `tests/test_agent_onboard.py:23-27`; no reader implementation found | D3 inventories/upgrades them or explicitly confirms none before writer flip |
| Tracked stdout snapshot | `reports/langgraph_parity/receipts/gate_A_make_onboard.stdout.txt:500-502` mentions the path | Snapshot only; never a schema consumer or behavioral proof |
| Valid v1 input | No digest/key/verdict | Validate types; legacy display only; never cache, delta, or admission evidence |
| v1 with missing/unknown/wrong-type field | New | Reject as malformed v1; never guess or treat as v2 |
| Valid applicable v2 | New | Recompute digest/key; reuse static sections only; rerun hard/live checks |
| Valid v2 for another repo/branch/HEAD | New | Cold miss; never READY from that receipt |
| Missing schema, partial/corrupt JSON, digest mismatch | New | Typed corruption; exit nonzero on that run; validated replacement may be written atomically |
| Unknown future major | New | Explicit unsupported schema; never parse as v1/v2 |
| Unknown field in v2 | New | Reject except inside a declared `extensions` object, matching TAM's fail-closed unknown-field posture (`scripts/governance/tam_ledger.py:347-349`) |

Exact v1 field mapping (`scripts/governance/agent_onboard.py:1843-1879`):

| v1 field | v2 handling | May grant admission/cache? |
|---|---|---:|
| `schema`, `authority` | Validate exact values before any other field | No |
| `observed_at` | Preserve under legacy/live metadata only | No |
| `repo` | Reprobe; split identity/head/branch from dirty/ahead/behind state | No reuse |
| `work_lanes` | Legacy deep-display input only | No |
| `portfolio` | Recompute owner-backed static tracks and live projection freshness | No reuse |
| `next_items` | Recompute from `ACTIVE_TRACK.yaml`; legacy display only | No |
| `swarm_bulletins` | Legacy display only | No |
| `broken_register` | Discard counts and rerun the canonical parser | No |
| `open_prs` | Discard by default; explicit `--net` delta only | No |
| `runtime_truth_packets` | Reprobe selected host or emit typed `needs_host` | No |

Migration order is reader-first:

1. WP-O1 lands the v1/v2 loader and fixtures while the writer remains v1.
2. D3 inventories every off-repo reader. Every discovered reader becomes
   dual-read v1+v2 through the rollback window, or the operator records that no
   such reader exists.
3. WP-O3 proves all known readers negotiate schema before interpreting fields.
4. WP-O3 flips the single writer to v2 for every invocation after D3. Strict
   mode controls process-exit policy only; it never oscillates the on-disk
   schema. Default human exit behavior remains pre-flip until WP-O5.
5. The first v2 run may display validated v1 legacy fields, but v1 cannot seed
   cache, stable delta, condition delta, or admission; the path is cold.
6. During the declared rollback window, writer rollback to v1 is permitted
   only because every upgraded external reader remains dual-read. The in-repo
   v2-aware loader remains. The projection is disposable and no canonical
   state is lost.

### 3.4 Delta

Stable delta compares the new `stable_core` with the immediately previous
valid, applicable v2 `stable_core` and reports rule/packet/track/ownership/
tool-policy changes. Condition delta separately compares the normalized
current `live_delta.conditions` with the prior validated applicable v2
conditions. `delta.previous_stable_digest` never feeds the new stable digest.
No historical ledger is introduced.

## §4 Mandatory Session Entry Packet and scope enforcement

### 4.1 Reuse AgentOps

The Session Entry Packet extends the existing unversioned AgentOps v0
work-packet shape with required `session_entry`, expected-exit, and
negative-control fields. It does not mislabel today's packet as an existing v1
schema. JSON is mandatory;
YAML remains optional only where PyYAML already exists, consistent with
AgentOps (`docs/governance/AGENTOPS.md:10-45`). Each implementation PR records
exactly one packet at:

```text
reports/agentops/work_packets/onboard-one-door-WP-O<N>.json
```

The post-WP-O1 security remediation admitted below uses the exact tracked path
`reports/agentops/work_packets/onboard-one-door-WP-O1R.json`. `WP-O1R` is a
distinct, literal packet identity; its one-time exact-identifier bootstrap and
normal pre-edit validation sequence are pinned in §6 WP-O1R.

This reuses the existing tracked AgentOps packet surface; it is not a new
receipt store. Before any code edit, however, the complete packet lives outside
the worktree under an external `DHARMA_OPS_DIR`. It is validated against a
clean exact baseline and then copied byte-for-byte to the path above as the
first admitted non-code diff. D1 does not pre-create stale future packets.

Required shape (existing AgentOps fields retained):

```json
{
  "id": "onboard-one-door-WP-O3",
  "base_ref": "5e7304c7df36b0fe6a34ae458b6cc0212b2106b6",
  "branch": "claude/make-onboard-hardening-n1ww1s",
  "worktree": ".",
  "intent": "Implement only WP-O3",
  "allowed_files": [
    "dharma_swarm/operator_core/onboarding/evidence.py",
    "reports/agentops/work_packets/onboard-one-door-WP-O3.json"
  ],
  "forbidden_files": [
    "docs/plans/TITANIUM_TELOS_HARDWIRING_PLAN.md",
    "docs/governance/ACTIVE_TRACK.yaml",
    ".github/workflows/automerge.yml"
  ],
  "gates": [
    {"name": "readiness", "command": "python3 -m pytest tests/test_onboarding_readiness.py -q", "expected_exit": 0}
  ],
  "negative_controls": [
    {"name": "outside-envelope", "command": "python3 -m pytest tests/test_agent_work_packet.py -q -k outside_packet_scope", "expected_exit": 0}
  ],
  "commit": {"allowed": false, "message": "feat(onboarding): implement WP-O3 [impact-checked]"},
  "approval": {"before_commit": true, "before_merge": true},
  "session_entry": {
    "schema": "dharma_swarm.session_entry.v1",
    "tool_versions": {"python": "3.12.13", "git": "2.51.1"},
    "authority_precedence": ["executable", "tests", "locks", "git", "owner_files"],
    "work_packet": "WP-O3",
    "active_track": "onboard-one-door-2026-07",
    "owner": "@AmitabhainArunachala",
    "collision": {"status": "clear", "checked_at_sha": "5e7304c7df36b0fe6a34ae458b6cc0212b2106b6", "details": []},
    "interface_mismatches": [],
    "closest_existing_implementation": ["scripts/governance/agent_onboard.py"],
    "honest_blockers": [],
    "rollback": "revert the WP-O3 packet commit",
    "packet_digest": "<stable_digest supplied after canonicalization>"
  }
}
```

The packet must contain exact baseline SHA/tool versions, canonical authority
precedence, assigned WP and owner, allowed/forbidden envelope, collision result,
relevant interface mismatches, closest implementation to extend, at least one
negative control, exact tests and expected exits, rollback, and honest
blockers. The illustrative SHA/branch above must be replaced with the actual
entry values; a submitted packet containing angle-bracket placeholders is
`CONFIG_ERROR`.

`packet_digest` is the mandated
`dharma_swarm.memory_kernel.write_receipts.stable_digest` of canonical packet
JSON with only `session_entry.packet_digest` omitted. Contract, cache-key,
rule, and section fingerprints use the same primitive; no derived digest
family is permitted. The external and tracked packet bytes must otherwise be
identical. `worktree: "."` is resolved only after the runner proves its current
directory is the repository root, avoiding a checked-in host path.

The envelope is default-deny: a path absent from `allowed_files` is rejected
even when it is not repeated in `forbidden_files`. `forbidden_files` must also
name every current sibling-track owned-surface pattern and packet-specific
high-risk surface. Forbidden overrides allowed, preserving current AgentOps
semantics (`scripts/governance/run_agent_work_packet.py:354-385`). Every gate
and isolated-fixture negative control is executed and graded against its
declared exit; existing gates without `expected_exit` adapt to expected 0.
Negative controls may never mutate the admitted source checkout.

### 4.2 Bootstrap and final mechanical enforcement

- At a clean exact `HEAD`, the implementation agent creates one complete
  external packet and runs
  `python3 scripts/governance/run_agent_work_packet.py --packet "$SESSION_ENTRY_PACKET" --inspect`.
  Before WP-O1, human review additionally checks the extension fields; no code
  edit is authorized yet.
- WP-O1 makes the extension, expected exits, negative controls, canonical
  digest, portable worktree binding, and external report root
  machine-validating. From WP-O1R onward any mismatch is fail-closed, after the
  exact-identifier bootstrap exception admitted in §6 WP-O1R has merged.
- Preflight reads the external packet, requires a clean worktree and exact
  `HEAD == packet.base_ref`, writes its report outside the worktree, and returns
  0 before any code edit. The agent then copies the exact packet bytes to the
  tracked path as the first admitted non-code change; any byte drift blocks.
- Closeout and CI inspect the union of:
  `packet.base_ref...HEAD`, unstaged changes, staged changes, and untracked
  files. Forbidden patterns override allowed patterns. The same packet digest
  used at preflight must be present at closeout. Closeout accepts a descendant
  of the exact base; preflight does not.
- Current AgentOps checks only unstaged/staged/untracked state
  (`scripts/governance/run_agent_work_packet.py:354-385`); WP-O4 extends that existing matcher for
  committed-range enforcement rather than implementing another scope engine.
- Current non-dry AgentOps writes unignored reports inside the target worktree
  (`scripts/governance/run_agent_work_packet.py:479-481,634-644,662`). WP-O1
  adds an explicit external report root using the existing report schema;
  preflight, closeout, and CI never fall back into the source tree.
- Active-track overlap is not sufficient: current policy is warning-level and
  its current checker compares literal surface strings
  (`docs/governance/ACTIVE_TRACK.yaml:77-85`,
  `scripts/governance/check_track_status.py:1660-1670`). Admission must detect
  exact, ancestor/descendant, glob containment, and actual-diff collisions.
- The cognitive readback may remain advisory; packet presence, schema, exact
  base, owner, collision, and scope enforcement may not.

## §5 Internal architecture

Use one dependency-light typed package importable by both governance scripts
and operator read models:

```text
dharma_swarm/operator_core/onboarding/
├── __init__.py
├── models.py          # packet/check/condition/version models
├── contract.py        # sole public packet/gate policy owner
├── _command_lexical.py  # private WP-O1R lexical mechanics; no public owner
├── broken_register.py # the one canonical lifecycle parser
├── evidence.py        # repo/portfolio/tool/host collection; no policy
├── receipt.py         # v1/v2 loader, cache manifest, lock, delta, atomic write
├── readiness.py       # precedence and selected-scope admission policy
├── render.py          # compact/deep/deterministic JSON renderers
└── cli.py             # argument orchestration only
```

This avoids making runtime `dharma_swarm` modules import from `scripts/`.
`agent_onboard.py` and `orientation_graph.py` become compatibility shims.
Modules stay below 500 lines; responsibilities may be combined only if the
separability tests remain direct and no file approaches the budget.
`_command_lexical.py` is the one narrow exception that permits `contract.py`
to delegate private lexical mechanics without transferring policy ownership.
The dependency is one-way from `contract.py` to the stdlib-only helper. Its
surface is limited to pure command splitting, token forms, direct-Git
inspection, private Win32/path/revision normalization, and exact Git-shape
predicates that mechanically evaluate constants owned by `contract.py`. It
defines no allowlist constant of its own; `contract.py` supplies those values
to the inspection call. It raises no AgentOps/admission exception and makes no
final admission decision.
It is not exported from the package and is not a second parser or policy
surface; every behavioral admission consumer and test continues through
`contract.parse_gate`.

Canonical broken-register semantics:

- parse occurrences and retain append-only history, but expose one current
  record per BR ID;
- open/reopened current-section occurrence wins over a historical closed
  occurrence of the same ID;
- lifecycle comes only from anchored status field, anchored heading metadata,
  or closed-section membership — never arbitrary prose;
- `## STALE-CLAIM CORRECTIONS` terminates the current/open scan; closed history
  is parsed separately;
- normalized open-like lifecycle is
  `OPEN|PARTIAL|INVESTIGATING|WORKAROUND`; closed-like is `FIXED|CLOSED`;
  severity words such as `STALE|DEGRADED|BLOCKER` do not become lifecycle;
- missing/malformed/contradictory current status is typed `UNKNOWN` with a
  diagnostic, never silently open or pass;
- consumers use normalized `status`, `is_open_like`, and `is_closed_like`; no
  downstream token-set reimplementation.

## §6 Work packets

Effort convention follows
`docs/plans/DHARMAGRAPH_PHASED_SPEC_2026-07-05.md:67-70`:
**S = days, M = 1–2 weeks, L = multi-week**. Estimates include implementation,
tests, migration, review, and rollback—not line count.

For every WP, the allowed list below is exhaustive and all other repository
paths are outside scope. The materialized Session Entry Packet also places the
current sibling-track owned globs plus unadmitted Titanium, authority,
generated-report, runtime-state, merge-authority, and branch-protection
surfaces in `forbidden_files`; an explicitly allowed path is removed from that
WP's forbidden set because forbidden overrides allowed. At minimum, unless a
WP explicitly admits one, forbid `docs/plans/TITANIUM_TELOS_HARDWIRING_PLAN.md`,
`docs/governance/ACTIVE_TRACK.yaml`, `CLAUDE.md`,
`docs/governance/SOVEREIGN_MANIFEST.md`, `.github/workflows/automerge.yml`,
`reports/governance/**`, and `docs/state/**`. Exact resolved arrays, not brace
notation or prose wildcards, go into the packet.

**Mechanical count-refresh admission (every WP):** strict
`make docops-integrity` recomputes module/test/markdown metrics that any
implementation diff necessarily moves
(`docs/docops/assertions.yaml:7-46`;
`scripts/docops/check_docops_integrity.py:184-200,648-675`). Every WP envelope
therefore admits, as its final pre-commit step only, the mechanical outputs of
`python3 scripts/docops/check_docops_integrity.py --write-manifest-counts
--write-auto-sections`: the managed count rows in
`docs/governance/SOVEREIGN_MANIFEST.md` and the generated sections of
`docs/docops/AUTO_INVENTORY.md`. This admission covers ONLY tool-generated
replace-in-place refreshes — no prose edit, no assertion redesign, no new or
weakened assertion, no other change to either file. Any hand edit to those
files remains forbidden and fails review. [AMENDED 2026-07-10: second
deterministic envelope conflict, reported by the WP-O1 implementation lane
before merge — without this clause no packet can both stay in-scope and make
the strict DocOps gate exit 0.]

### WP-O1 — Contract, receipt loader, entry packet, and custody repair (L)

**Closes:** §1.3 finding 5, the in-repository reader portion of finding 6, and
the schema/bootstrap portion of finding 7. The off-repo part of finding 6 stays
open through D3; committed-range enforcement remains WP-O4; adapter
A1/A2/A3/A4 remain explicit dependencies.

**Owner:** D1-admitted track owner.

**Prerequisites / merge dependency:** D1 admission merged; WP-O1 Session Entry
Packet validated by existing AgentOps inspect; root-custody exception reviewed
explicitly. No dependency on D2.

**Allowed files:**

- `AGENTS.md`
- `.gitignore` — shared, non-owned surface admitted for exactly one edit:
  delete the root `/AGENTS.md` ignore line (`.gitignore:99` at the amendment
  SHA). No other ignore rule may change; the track does NOT take
  `owned_surfaces` ownership of this file (other lanes edit it routinely —
  admission is packet-scoped). [AMENDED 2026-07-10: added after a WP-O1
  implementation agent correctly stopped on the exhaustive-envelope conflict.]
- `.github/workflows/structure.yml` — only exact `AGENTS.md` Rule 8 allowlist
- `dharma_swarm/operator_core/__init__.py` — shared, non-owned surface admitted
  for exactly one behavior change: convert eager submodule imports to
  lazy/guarded so that importing `operator_core.onboarding` (and collecting
  its tests) succeeds on a host WITHOUT optional TUI dependencies
  (`textual`). No public name may be removed; no other module may be pulled
  in. Proven by new behavior O1-B14. [AMENDED 2026-07-10 #3: independent
  review of the first WP-O1 PR reproduced a collection failure on a
  textual-free host — the gate battery could not even import.]
- `docs/governance/ANTI_SLOP_RULES.md` — mirror that one allowlist fact
- `docs/governance/AGENTOPS.md` — external-report and entry-packet contract
- `scripts/docops/check_docops_integrity.py`
- `tests/test_docops_integrity.py`
- `scripts/governance/run_agent_work_packet.py` — extended schema, digest,
  expected exits, negative controls, portable worktree, external report root
- `tests/test_agent_work_packet.py`
- `dharma_swarm/operator_core/onboarding/__init__.py`
- `dharma_swarm/operator_core/onboarding/models.py`
- `dharma_swarm/operator_core/onboarding/contract.py`
- `dharma_swarm/operator_core/onboarding/receipt.py`
- `tests/test_onboarding_contract.py`
- `reports/agentops/work_packets/onboard-one-door-WP-O1.json`

`docs/docops/assertions.yaml` is forbidden at this baseline because the
registration is already correct. If an entry-SHA read changes that fact, stop
and obtain an operator-approved packet/ownership amendment; do not widen WP-O1
in flight. The CI/DocOps files above are a named custody repair, not an
implicit authority expansion.

**Canonical root pointer content** — byte-exact, LF line endings, exactly one
trailing newline; O1-B13 asserts byte equality [AMENDED 2026-07-10: the
original text required the pointer without pinning its bytes]:

~~~markdown
# Agent entrypoint

Run `make onboard` before non-trivial work.
The canonical behavioral contract is `CLAUDE.md`; this file must never duplicate it.
Return the startup readback printed by onboarding before editing.
~~~

**Behavior → named test map:**

| ID | Behavior | Failing-first test / structural contract |
|---|---|---|
| O1-B1 | Canonical max-five owners are exact and content-addressed | `test_canonical_first_read_manifest_matches_doc_stack` |
| O1-B2 | One loader validates v1/v2, refuses missing/unknown/corrupt schema, and treats v1 as non-admission | `test_receipt_v1_v2_compatibility_matrix` |
| O1-B3 | Stable digest covers stable core only and uses mandated primitive | `test_timestamp_live_delta_and_previous_digest_do_not_change_stable_digest` |
| O1-B4 | Session Entry fields are mandatory; gate and negative-control expected exits parse | `test_session_entry_rejects_each_missing_required_field` |
| O1-B5 | Missing registered canon fails DocOps; root pointer does not duplicate CLAUDE | `test_registered_canon_missing_fails`, `test_agents_pointer_rejects_contract_duplication` |
| O1-B6 | Rule 8 allows exactly the registered root pointer and still rejects another root Markdown file | `test_rule8_agents_exception_is_exact` |
| O1-B7 | Receipt override resolves outside worktree and `.git`, including symlinks | `test_ops_dir_inside_repo_and_symlink_escape_are_config_error` |
| O1-B8 | Portable external packet validates at exact clean HEAD; canonical digest binds byte-identical tracked copy without self-reference | `test_external_entry_packet_bootstrap_and_digest_binding` |
| O1-B9 | Gate/negative-control expected exits are executed and graded; controls cannot mutate source | `test_declared_expected_exits_and_isolated_negative_controls` |
| O1-B10 | AgentOps reports require an explicit external root and attempt no source/`.git` write, including ignored or identical files | `test_external_report_root_is_mandatory_and_read_only` |
| O1-B11 | Collision proof detects exact, containment, glob-intersection, and actual-file overlap instead of trusting warning-only portfolio output | `test_session_entry_collision_adversarial_matrix` |
| O1-B12 | Only versioned `extensions` are accepted outside core; extension data cannot affect verdict or stable digest | `test_receipt_extensions_are_versioned_and_nonadmission` |
| O1-B13 | Root pointer bytes equal the canonical block exactly; `.gitignore` drops only the `/AGENTS.md` line and every other ignore rule is byte-unchanged | `test_agents_pointer_bytes_canonical_and_gitignore_carveout_scoped` |
| O1-B14 | `operator_core.onboarding` imports and its test module collects with optional TUI deps absent (block `textual` via a meta-path finder in-process, then import) | `test_onboarding_imports_without_optional_tui_deps` |

**Verification / expected exit:**

```bash
python3 -m pytest tests/test_onboarding_contract.py \
  tests/test_agent_work_packet.py tests/test_docops_integrity.py -q
# expected: 0
python3 scripts/docops/check_docops_integrity.py --changed-from "$BASELINE_SHA"
# expected: 0; any pre-existing count drift is a named prerequisite blocker
```

**Rollback:** revert the loader/packet extension and keep no v2 receipt; the
writer is still v1. Once the root pointer and exact Rule 8/DocOps custody
repair have merged green, later packet rollback retains that pre-existing
custody repair. If the pointer itself fails its WP-O1 tests before merge,
reject the pointer and all listed custody changes as one unit.

**Evidence artifact:** the checked-in WP-O1 packet plus the existing AgentOps
report schema written to the explicit external report root; no new receipt
path.

**Forbidden/non-goals:** no writer flip, no strict-default change, no active
track content repair, no general DocOps cleanup, no second packet parser.

**Kill criterion:** if coherent root custody requires weakening Rule 8 or
canonical guard semantics, stop and return to the operator; do not create the
pointer.

### WP-O1R — Session Entry direct-command lexical remediation (S)

**Closes:** two post-merge Session Entry direct-command lexical defects at
`dharma_swarm/operator_core/onboarding/contract.py:169-185`. At baseline
`94a3877c7799bbde7f0ac9adff060ee1f449683f`, only `argv[0]` receives basename
normalization while later tokens are compared whole
(`dharma_swarm/operator_core/onboarding/contract.py:178-184`). A read-only
`parse_gate` probe must record all three commands below as accepted before the
failing-first test is added:

```text
python3 scripts/runtime/live_swarm.py
python3 ./scripts/runtime/live_swarm.py
python3 -m dharma_swarm.live_swarm
```

Run the exact probe from a supported repository Python environment:

```bash
export DHARMA_PYTHON="${DHARMA_PYTHON:-.venv/bin/python}"
test -x "$DHARMA_PYTHON"
"$DHARMA_PYTHON" -B -c 'import json, subprocess; from dharma_swarm.operator_core.onboarding.contract import parse_gate; commands=["python3 scripts/runtime/live_swarm.py", "python3 ./scripts/runtime/live_swarm.py", "python3 -m dharma_swarm.live_swarm"]; payload={"baseline_sha": subprocess.run(["git", "rev-parse", "HEAD"], check=True, capture_output=True, text=True).stdout.strip(), "results": [{"command": command, "accepted_argv": parse_gate({"name": "baseline-probe", "command": command}, index).argv} for index, command in enumerate(commands)]}; print(json.dumps(payload, indent=2))'
# expected at 94a3877c7799bbde7f0ac9adff060ee1f449683f: exit 0;
# all three results contain accepted_argv
```

The probe records exact command, baseline SHA, parsed `argv`, output, and
process exit. Acceptance of all three with exit 0 is the defect witness; it is
not a passing security result.

The same parser also checks only `argv[1]` for a banned Git subcommand. The
[post-merge review](https://github.com/AmitabhainArunachala/dharma_swarm/pull/861#discussion_r3558920481)
is confirmed and promoted from P2 to P1: global-option forms and aliases cross
the documented direct-Git lexical guard. Before the WP-O1R test is added, a
read-only `parse_gate` probe must record each command below as accepted:

```text
git -C . push origin HEAD
git -c core.sshCommand=/bin/false push origin HEAD
git --git-dir=.git push origin HEAD
git -c alias.x=push x origin HEAD
git -c "alias.x=!printf ALIAS_EXECUTED" x
```

The last form can cause Git to invoke a shell alias even though AgentOps later
uses `subprocess.run(..., shell=False)`. The implementation proof must not
execute that alias; parsing acceptance is the failing-first witness. The same
boundary also rejects packet-supplied environment for Git gates, direct
`git-*` plumbing executables, side-effectful or helper-routing flags, every Git
global option before a subcommand, and every non-allowlisted subcommand/alias.
Only the exact read-only command/argument shapes in O1R-B5 remain admitted.
The inherited operator environment is a trusted host prerequisite, not packet
input; B0 remains exact-identity-only and may not absorb this change.

This packet does **not** claim that arbitrary admitted commands are confined.
At this boundary `python -c` can spawn Git, and alternate clients such as
`gh`, `ssh`, or `curl` remain syntactically admissible. Session Entry packets
are therefore trusted declarative code, not an arbitrary-command sandbox.
WP-O4-B11 owns the mandatory fail-closed positive command-family allowlist;
its Active Track criterion must pass before the track can ship. Even that
allowlist does not prove trusted pytest or repository scripts are free of I/O:
WP-O6 syscall/no-network evidence remains the terminal oracle.

**Owner:** D1-admitted track owner.

**Mandatory module-budget extraction (amended 2026-07-11):** at
`d3e084c66a262a26779971b25729151c4c9a0ae7`, `contract.py` is exactly 499
physical lines. Keeping the admitted O1R lexical closure in that file would
make it another module above 500 lines and raise the one-way
`modules_over_500_lines` counter above its 207 bound. WP-O1R therefore must
create exactly one subordinate internal module,
`dharma_swarm/operator_core/onboarding/_command_lexical.py`, and extract the
stdlib-only mechanics into it: `split_command`, token-form and direct-Git
inspection helpers, private Win32/path/revision normalizers, and exact
Git-shape predicates that mechanically evaluate grammar constants owned by
`contract.py` and supplied to the inspection call. The helper defines no
allowlist constant of its own. Those symbols return lexical values or booleans only.
`contract.py` retains `_parse_command`, shell/live policy, grammar constants
and ownership, environment/identity/grammar orchestration, every final
admission decision, every `AgentOpsError`, and sole parser/public policy
ownership. The helper has no packet/schema/scope
ownership, admission exception, subprocess execution, standalone admission
entrypoint, package export, reverse import, or independent consumer. All
behavioral admission calls continue through `contract.parse_gate`.
`contract.py` and the helper must each remain at or below 500 physical lines,
and WP-O1R must leave `modules_over_500_lines` at or below 207. A second helper,
parser, policy engine, or owner for direct-command lexical admission is not
admitted.

**Inherited direct-Git environment closure (amended 2026-07-11):** the
reviewed pre-amendment implementation rejected only packet-supplied `env`,
while `run_gate()` copied the AgentOps process environment. An inherited
`GIT_DIR`, `GIT_WORK_TREE`, index/object override, or config-injection variable
could therefore redirect an otherwise admitted read-only Git gate away from
the packet worktree. WP-O1R must add one contract-owned execution-environment
builder and wire only `scripts/governance/run_agent_work_packet.py` to use it.
For a direct Git gate, the builder removes every inherited key whose name
case-insensitively starts with `GIT_` before execution and sets exactly
`GIT_CONFIG_GLOBAL=os.devnull`, `GIT_CONFIG_NOSYSTEM=1`, and
`GIT_OPTIONAL_LOCKS=0`. `os.devnull` is required for POSIX/macOS and Windows
portability. The global-config override prevents `$HOME/.gitconfig` and
`$XDG_CONFIG_HOME/git/config` from supplying executable config such as
`core.fsmonitor`; optional-lock suppression prevents `git status` from
refreshing the index as a side effect. The existing parse-time rejection of
every non-empty packet `env` remains. The runner does not re-identify Git,
import the lexical helper, or acquire admission policy: it consumes the
contract-owned builder immediately before normal child execution and before a
negative-control `control_env` is encoded into `env -i` argv. Non-Git gate
environment behavior is unchanged. This closes the admitted direct-Git child,
not trusted-host runner-internal `run_git()` calls before packet parsing; O4/O6
retain PATH/interpreter and terminal syscall/network proof.

**Prerequisites / merge dependency:** the direct-command admission amendment,
this module-budget extraction amendment, and the WP-O1R-B0 exact-identifier
bootstrap below merged; merge commit
`94a3877c7799bbde7f0ac9adff060ee1f449683f` remains an ancestor; a fresh clean
post-bootstrap baseline and sibling collision matrix are recorded; the
complete external WP-O1R Session Entry Packet validates before any direct-
command lexical implementation edit. Prove the ancestry with
`git merge-base --is-ancestor 94a3877c7799bbde7f0ac9adff060ee1f449683f HEAD`
(expected exit 0). WP-O1R must merge before WP-O2 begins.

**Packet identity:** the operator-required canonical external filename and the
machine-enforced tracked filename are `onboard-one-door-WP-O1R.json`. The
runner derives the required tracked path from `packet.id` and requires indexed
byte equality
(`scripts/governance/run_agent_work_packet.py:317-330`), so the packet must use
the following injective identity:

```json
{
  "id": "onboard-one-door-WP-O1R",
  "session_entry": {"work_packet": "WP-O1R"}
}
```

The current evaluator admits only numeric `WP-O<N>` values
(`dharma_swarm/operator_core/onboarding/contract.py:286-290`), so exact
pre-edit validation is impossible at baseline
`94a3877c7799bbde7f0ac9adff060ee1f449683f`. Neither the
filename nor an alias may mint authority: the merged spec/track admission owns
the envelope, and the evaluator must check the same literal identity in the
external packet content, tracked path, and report. The external source
basename is a procedural requirement; the runner machine-checks its `.json`
suffix and content, not that basename
(`scripts/governance/run_agent_work_packet.py:861-878`).

**WP-O1R-B0 exact-identifier bootstrap (separate prerequisite PR):** the
previously merged direct-command admission amendment explicitly ratified one
narrow exception to §4's pre-edit packet rule. It waived only external/tracked
packet presence and prevalidation for B0; exact clean base, tool versions,
track/owner, fresh sibling collision analysis, default-deny complete-diff
scope, and failing-first evidence remained mandatory. Under that exception,
the D1-admitted track owner starts B0 at the exact clean admission-merge SHA,
records that SHA and the empty `git status --porcelain=v1`, and may edit only:

- `dharma_swarm/operator_core/onboarding/contract.py`
- `tests/test_agent_work_packet.py`

Only the mechanically required §6 count-refresh outputs may join those two
files. B0's sole behavior change is to accept exact `WP-O1R` as a
`session_entry.work_packet` value while preserving `WP-O1` and `WP-O10`, the
packet-id token check, and rejection of `WP-O6R`, `WP-O1RR`, `WP-O1R2`,
`WP-O1r`, and every other suffix. Its sole named test is
`test_session_entry_accepts_exact_wp_o1r_identity_only`.

Before the first B0 edit, run and record:

```bash
export DHARMA_PYTHON="${DHARMA_PYTHON:-.venv/bin/python}"
test -x "$DHARMA_PYTHON"
export ADMISSION_MERGE_SHA="<merged 40-hex admission SHA>"
export BASELINE_SHA="$(git rev-parse HEAD)"
test -z "$(git status --porcelain=v1)"
test "$BASELINE_SHA" = "$ADMISSION_MERGE_SHA"
"$DHARMA_PYTHON" --version
git --version
make --version
"$DHARMA_PYTHON" -c 'from pathlib import Path; import yaml; from dharma_swarm.operator_core.onboarding.contract import detect_surface_collisions; data=yaml.safe_load(Path("docs/governance/ACTIVE_TRACK.yaml").read_text()); track=next(item for item in data["active_tracks"] if item["id"] == "onboard-one-door-2026-07"); assert track["status"] == "ACTIVE" and track["owner"] == "@AmitabhainArunachala"; allowed=["dharma_swarm/operator_core/onboarding/contract.py", "tests/test_agent_work_packet.py", "docs/governance/SOVEREIGN_MANIFEST.md", "docs/docops/AUTO_INVENTORY.md"]; siblings={item["id"]: item.get("owned_surfaces", []) for item in data["active_tracks"] if item["id"] != track["id"]}; collisions=detect_surface_collisions(allowed, siblings, allowed); assert not collisions, collisions; print("WP-O1R-B0 track/owner/collision: clear")'
# expected: every command exits 0; replace the descriptive SHA before running
```

After adding only that test and before changing the grammar, run the node below
and require a nonzero exit; record exact command, baseline SHA, output, and
exit. Then implement the exact identity bridge and require every remaining
command to exit 0:

```bash
export DHARMA_PYTHON="${DHARMA_PYTHON:-.venv/bin/python}"
test -x "$DHARMA_PYTHON"
"$DHARMA_PYTHON" -m pytest \
  tests/test_agent_work_packet.py::test_session_entry_accepts_exact_wp_o1r_identity_only -q
# failing-first expected: nonzero before the grammar edit; 0 afterward
"$DHARMA_PYTHON" -m pytest tests/test_agent_work_packet.py -q
"$DHARMA_PYTHON" -m ruff check \
  dharma_swarm/operator_core/onboarding/contract.py \
  tests/test_agent_work_packet.py
make docops-integrity
"$DHARMA_PYTHON" scripts/governance/render_active_track_includes.py --check
"$DHARMA_PYTHON" scripts/governance/check_track_status.py
"$DHARMA_PYTHON" scripts/governance/check_name_drift.py
git diff --check
set -o pipefail
{
  git diff --name-only "$BASELINE_SHA"...HEAD
  git diff --name-only
  git diff --cached --name-only
  git ls-files --others --exclude-standard
} | sort -u | while IFS= read -r path; do
  case "$path" in
    ""|dharma_swarm/operator_core/onboarding/contract.py|tests/test_agent_work_packet.py|docs/governance/SOVEREIGN_MANIFEST.md|docs/docops/AUTO_INVENTORY.md) ;;
    *) echo "WP-O1R-B0 forbidden path: $path" >&2; exit 1 ;;
  esac
done
# passing expected: only admitted code/test and mechanical count outputs;
# any other committed, unstaged, staged, or untracked path exits 1
```

No packet, command normalization, runner, DocOps assertion, or later-WP change
is allowed. The B0 PR body plus its failing-first/passing CI logs and merge
commit are the evidence artifact; no new receipt path is created. Rollback is
one B0 revert before any WP-O1R packet is admitted. The first merged B0 consumes
this exception permanently. The later WP-O1R packet/PR records that merge SHA,
proves it is an ancestor, starts from a new clean baseline, and follows normal
§4 packet validation with no exception.

**Allowed files:**

- `dharma_swarm/operator_core/onboarding/contract.py`
- `dharma_swarm/operator_core/onboarding/_command_lexical.py`
- `scripts/governance/run_agent_work_packet.py`
- `tests/test_agent_work_packet.py`
- `reports/agentops/work_packets/onboard-one-door-WP-O1R.json`

Creating the helper necessarily moves DocOps module/LOC metrics, so the
materialized external and byte-identical tracked packet must use this exact
`allowed_files` array (no directory glob or alias):

```json
[
  "dharma_swarm/operator_core/onboarding/contract.py",
  "dharma_swarm/operator_core/onboarding/_command_lexical.py",
  "scripts/governance/run_agent_work_packet.py",
  "tests/test_agent_work_packet.py",
  "reports/agentops/work_packets/onboard-one-door-WP-O1R.json",
  "docs/governance/SOVEREIGN_MANIFEST.md",
  "docs/docops/AUTO_INVENTORY.md"
]
```

The last two paths retain only the §6 mechanical count-refresh authority.
`dharma_swarm/operator_core/onboarding/__init__.py` remains unedited and may
not re-export the helper. Any pre-amendment packet that omits the helper or
runner or binds the old base/digest is invalid; regenerate the external packet
at the clean post-amendment baseline, validate it, then copy its bytes
unchanged to the tracked path. Its Ruff gate names both onboarding source
modules plus the runner, and its blocking quality-ratchet gate substitutes the
packet's exact `base_ref` for `$BASELINE_SHA` in the verification command
below. No other source, test, packet, or owner surface is admitted.

**Behavior → named test map:**

| ID | Behavior | Failing-first test / structural contract |
|---|---|---|
| O1R-B0 | Exact `WP-O1R` identity is accepted without widening the numeric packet grammar to arbitrary suffixes | `test_session_entry_accepts_exact_wp_o1r_identity_only` |
| O1R-B1 | Every command token is checked case-insensitively through raw executable, separator-canonical, normalized path basename, basename stem, and dotted-module leaf forms; parsed `argv` is not rewritten | `test_gate_command_normalization_rejects_live_targets_without_blocking_safe_commands` |
| O1R-B2 | Direct, relative, absolute, `.py`, interpreter-routed, and `python -m` forms reaching `contract.py`'s existing `_BANNED_LIVE_COMMAND_TOKENS` owner vocabulary are rejected, including common Python executable variants and underscore spellings of hyphenated targets | `test_gate_command_normalization_rejects_live_targets_without_blocking_safe_commands` |
| O1R-B3 | Safe pytest, governance, DocOps, and ordinary non-live Python commands remain accepted with exact parsed `argv` | `test_gate_command_normalization_rejects_live_targets_without_blocking_safe_commands` |
| O1R-B4 | Direct Git lexical routes using global options, packet-supplied environment, configuration injection, alternate repository roots, executable/helper routing, direct `git-*` plumbing executables, side-effectful flags, unknown subcommands, or aliases fail at parse time, including `alias.*=!shell` forms | `test_gate_rejects_git_global_options_and_aliases` |
| O1R-B5 | Only the exact read-only Git command/argument shapes listed below for `status`, `diff --check`, `rev-parse`, `merge-base --is-ancestor`, and `ls-files` remain accepted without argv rewriting; every other Git subcommand, option, argument shape, and non-empty gate `env` remains fail-closed | `test_gate_rejects_git_global_options_and_aliases` |
| O1R-B6 | Exactly one stdlib-only subordinate helper returns lexical values/booleans and mechanically evaluates only exact shapes using grammar constants passed by `contract.py`, with no helper-owned allowlist, in a one-way `contract.py` → helper dependency; `_parse_command`, grammar ownership, final admission decisions, and all `AgentOpsError` raising remain in `contract.py`, both files stay ≤500 lines, and `modules_over_500_lines` stays ≤207 | `test_wp_o1r_lexical_helper_remains_private_and_subordinate` plus physical-line checks and the blocking quality ratchet |
| O1R-B7 | Before a direct Git gate executes, the contract-owned environment builder case-insensitively removes all inherited `GIT_*` keys; sets only `GIT_CONFIG_GLOBAL=os.devnull`, `GIT_CONFIG_NOSYSTEM=1`, and `GIT_OPTIONAL_LOCKS=0`; preserves unrelated inherited variables; and leaves non-Git gate behavior unchanged. The runner consumes this builder without importing the helper or duplicating Git identity policy, including before negative-control `env -i` argv encoding | `test_direct_git_gate_strips_inherited_git_environment` |

O1R-B6 is a structural boundary test, not a helper behavior test. It inspects
AST/source to prove the helper is stdlib-only, imports no AgentOps model/error,
defines no allowlist constant, raises no admission exception, is absent from
package exports, and has no
production consumer except `contract.py`; it also proves `contract.py` retains
`_parse_command`, the exact grammar constants, and the admission/error symbols,
and that no second lexical helper/engine was added. The test must not import or
call helper behavior directly. B1–B5 remain the behavioral parse-entrypoint
proof; B7 exercises the public runner boundary and captures the exact child
environment without executing Git. B7 poisons mixed-case repository, config,
helper, trace, redirect, and optional-lock variables; asserts that the only
remaining case-insensitive `GIT_*` keys are the exact safe triple; preserves
HOME/XDG/PATH and unrelated keys without mutating the input mapping; proves
argv/cwd unchanged; covers bare, absolute POSIX, and quoted Windows `git.exe`
forms; locks non-Git environment behavior; and proves the negative-control
`env -i` assignment vector carries the same sanitized triple.

Use one named command matrix test so the bypass rows make that test fail on the
clean baseline; direct-denial and safe-command rows are regression controls,
not failing-first assertions. Collect every result before the final assertion
so the baseline output witnesses the complete bypass set. The minimum rejection
matrix is:

```text
live_swarm
./live_swarm
scripts/runtime/live_swarm.py
./scripts/runtime/live_swarm.py
/absolute/path/to/live_swarm.py
python3 scripts/runtime/live_swarm.py
python3 ./scripts/runtime/live_swarm.py
python3 -m dharma_swarm.live_swarm
python3 -m Dharma_Swarm.LIVE_SWARM
python dharma_swarm/orchestrate_live.py
python3.13 -m dharma_swarm.orchestrate_live
.venv/bin/python scripts/runtime/autonomy-daemon.py
/usr/bin/python3 -m dharma_swarm.autonomy_daemon
python.exe scripts/runtime/autonomous-daemon.py
python.exe "C:\scripts\runtime\live_swarm.py"
py -3 -m dharma_swarm.autonomous_daemon
```

The Git rejection matrix is:

```text
git -C . status --short
git -c core.sshCommand=/bin/false status --short
git --git-dir=.git status --short
git --git-dir .git status --short
git --work-tree=. status --short
git --work-tree . status --short
git --exec-path=/tmp status --short
git --config-env=core.sshCommand=GIT_SSH_COMMAND status --short
git --no-pager status --short
git -c alias.x=push x origin HEAD
git -c "alias.x=!printf ALIAS_EXECUTED" x
git x
git fetch origin main
git push origin HEAD
git merge main
git diff --output=/tmp/agentops-write
git diff --output /tmp/agentops-write
git diff --ext-diff HEAD
git diff --textconv HEAD
git-push origin HEAD
/usr/local/libexec/git-core/git-push origin HEAD
git-send-pack origin HEAD
git-http-push origin HEAD
"C:\\Program Files\\Git\\mingw64\\libexec\\git-core\\git-push.exe" origin HEAD
git.exe push origin HEAD
```

The named test also parameterizes every existing banned mutating subcommand
(`am`, `cherry-pick`, `clean`, `commit`, `merge`, `pull`, `push`, `rebase`,
`reset`, `restore`, `revert`, and `stash`) and proves representative
non-allowlisted subcommands such as `branch`, `config`, `fetch`, `remote`, and
`show` fail closed. The direct-executable rows are checked through raw,
separator-canonical, basename, and basename-stem forms on POSIX and Windows.

For object-form gates, each non-empty Git `env` is rejected before execution,
including the following witnesses:

```json
{"command":"git status --short","env":{"PATH":"/tmp/fake-git"}}
{"command":"git diff --check","env":{"GIT_EXTERNAL_DIFF":"/tmp/helper"}}
{"command":"git diff --check","env":{"GIT_CONFIG_COUNT":"1","GIT_CONFIG_KEY_0":"diff.external","GIT_CONFIG_VALUE_0":"/tmp/helper"}}
```

The Git acceptance controls, and the complete allowed grammar, are:

```text
git status --short
git status --short --branch
git status --porcelain=v2 --branch
git diff --check
git diff --check HEAD
git diff --check origin/main...HEAD
git diff --check -- docs/governance/AGENTOPS.md
git rev-parse HEAD
git rev-parse --verify HEAD
git rev-parse --show-toplevel
git rev-parse --abbrev-ref HEAD
git merge-base --is-ancestor HEAD HEAD
git ls-files --others --exclude-standard
/usr/bin/git status --short
"C:\\Program Files\\Git\\cmd\\git.exe" status --short
```

For `status`, only `--short` or `--porcelain[=v1|v2]`, optionally combined
with `--branch`, is allowed. For `diff`, `--check` is mandatory; following
non-option revision/range operands and repo-relative path operands, with an
optional literal `--` separator, are allowed, while every other option is
rejected. `rev-parse` accepts only the four exact shapes above. `merge-base`
accepts only `--is-ancestor` plus two non-option revision operands. `ls-files`
accepts only `--others --exclude-standard`, optionally followed by literal
`--` and repo-relative path operands. Operands that are absolute, traverse
upward, contain control characters, or begin with `-` fail closed. No generic
"read-only subcommand" allowance exists beyond this grammar.

The test collects all parse results before asserting, verifies exact accepted
`argv` and empty accepted Git `env`, and proves no rejected command reaches
subprocess execution. It must not add a second Git policy owner, rewrite argv,
or permit a global option because its current fixture appears harmless.

The minimum acceptance controls are:

```text
python3 -m pytest tests/test_agent_work_packet.py -q
python3 scripts/governance/check_track_status.py
make docops-integrity
python3 scripts/governance/check_name_drift.py
python3 scripts/governance/repo_status.py
python3 -c "print('ordinary non-live Python')"
python3 scripts/runtime/live_swarm_report.py
python3 -m dharma_swarm.live_swarm_report
```

The ordinary `python3 -c` row is an O1R-only regression control proving that
live-token normalization does not become an unbounded interpreter ban. O4-B11
deliberately inverts that row at the packet execution-admission boundary;
it is not a terminally accepted command family.

**Verification / expected exit:**

```bash
python3 -m pytest tests/test_onboarding_contract.py tests/test_agent_work_packet.py -q
python3 -m pytest tests/test_onboarding_contract.py tests/test_agent_work_packet.py \
  tests/test_docops_integrity.py -q
python3 -m pytest \
  tests/test_agent_work_packet.py::test_wp_o1r_lexical_helper_remains_private_and_subordinate -q
python3 -m pytest \
  tests/test_agent_work_packet.py::test_direct_git_gate_strips_inherited_git_environment -q
python3 -m pytest tests/test_agent_onboard.py -q
make docops-integrity
python3 scripts/governance/render_active_track_includes.py --check
python3 scripts/governance/check_track_status.py
python3 scripts/governance/check_name_drift.py
python3 -m ruff check dharma_swarm/operator_core/onboarding/contract.py \
  dharma_swarm/operator_core/onboarding/_command_lexical.py \
  scripts/governance/run_agent_work_packet.py \
  tests/test_onboarding_contract.py tests/test_agent_work_packet.py
test "$(wc -l < dharma_swarm/operator_core/onboarding/contract.py)" -le 500
test "$(wc -l < dharma_swarm/operator_core/onboarding/_command_lexical.py)" -le 500
python3 scripts/governance/hygiene/ratchet.py --max-baseline-age-days 45 \
  --baseline-merge-base-of "$BASELINE_SHA"
git diff --check
# expected: every command exits 0
```

Run the external byte-identical Session Entry Packet and require every declared
gate and negative control to pass. The report records the before/after command
matrix, packet digest, and gate/control totals outside the source tree.

**Rollback:** revert WP-O1R, then revert WP-O1R-B0 only after no WP-O1R packet
or report remains in use. The original WP-O1 contract and packet remain merged;
no receipt schema, runner, or later packet change is coupled to this
remediation.

**Evidence artifact:** the checked-in byte-identical WP-O1R packet plus its
external AgentOps report and exact failing-first/before-after command matrix;
no new receipt path.

**Forbidden/non-goals:** no WP-O2 or later packet edit; no new direct-command
parser, policy engine, denylist family, or command owner beyond the one private
subordinate lexical helper admitted above; no helper export or direct consumer
other than `contract.py`; no runner import of the helper, Git re-identification,
or admission decision; no reverse import, helper-side admission exception or
final decision, receipt, network call, or source-tree write; no shell, Git,
mutation, path, jail, or negative-control weakening; no ban on ordinary safe
Python or pytest commands.

**Kill criterion:** any required implementation file outside the allowed list,
any second direct-command lexical policy/helper owner, any public export of
`_command_lexical.py`, any helper import of AgentOps models/errors or helper-
side admission exception/final decision, any runner-side Git identity or
admission logic, any inherited case-insensitive `GIT_*` key reaching an
executed direct Git gate outside the builder's exact safe triple
(`GIT_CONFIG_GLOBAL=os.devnull`, `GIT_CONFIG_NOSYSTEM=1`, and
`GIT_OPTIONAL_LOCKS=0`), any unsanitized negative-control `env -i` assignment,
any `contract.py` or helper line count above 500, any
`modules_over_500_lines` reading above 207,
or any inability to validate the exact external injectively identified packet
at the clean post-bootstrap baseline stops WP-O1R and requires another merged
admission amendment. Do not widen the packet in flight.

### WP-O2 — One broken-register parser and shared static orientation (M)

**Closes:** §1.3 finding 1 and the eight live orientation false positives.

**Owner:** D1-admitted track owner.

**Prerequisites / merge dependency:** WP-O1, WP-O1R-B0, and WP-O1R merged;
re-run ownership collision at WP-O2 baseline.

**Allowed files:**

- `dharma_swarm/operator_core/onboarding/broken_register.py`
- `scripts/governance/agent_onboard.py`
- `scripts/governance/orientation_graph.py`
- `scripts/governance/trust_gate_status.py`
- `scripts/governance/repo_status.py`
- `dharma_swarm/operator_core/control_surface.py`
- `dharma_swarm/operator_core/operator_coherence/git_governance.py`
- `dharma_swarm/operator_core/control_surface_models.py` only to consume the
  normalized lifecycle fields, never to add a second parser
- `tests/test_agent_onboard.py`
- `tests/test_orientation_graph.py`
- `tests/test_trust_gate_status.py`
- `tests/test_repo_status.py`
- `tests/test_control_surface.py`
- `tests/test_operator_coherence_cockpit.py`
- `tests/test_onboarding_broken_register.py`
- `reports/agentops/work_packets/onboard-one-door-WP-O2.json`

**Behavior → named test map:**

| ID | Behavior | Failing-first test |
|---|---|---|
| O2-B1 | Plain/bold/heading lifecycle and section boundaries normalize once | `test_status_markup_and_section_matrix` |
| O2-B2 | Reopened BR supersedes historical closed occurrence | `test_reopened_id_wins_over_closed_history` |
| O2-B3 | Prose words never determine lifecycle; malformed/duplicate current entries diagnose | `test_incidental_status_words_do_not_classify`, `test_duplicate_current_status_is_diagnostic` |
| O2-B4 | Current fixture yields 22 distinct IDs, 9 current open-like, 13 current closed-like | `test_current_register_canonical_counts` |
| O2-B5 | All six former call sites consume identical normalized entries/counts | `test_all_six_consumers_share_canonical_parser` |
| O2-B6 | Header count drift and orphan hard-coded BR references surface diagnostics | `test_header_count_drift_is_reported`, `test_drift_triage_br_ids_resolve` |

Parity fixtures first capture each legacy consumer's current result. The
canonical expected result then deliberately corrects documented divergence;
tests must state which differences are intentional rather than claiming
byte-parity with broken behavior.

**Verification / expected exit:**

```bash
python3 -m pytest tests/test_onboarding_broken_register.py \
  tests/test_agent_onboard.py tests/test_orientation_graph.py \
  tests/test_trust_gate_status.py tests/test_repo_status.py \
  tests/test_control_surface.py tests/test_operator_coherence_cockpit.py -q
# expected: 0
```

**Rollback:** one revert restores all six consumers together. Never revert only
one caller or leave a compatibility parser behind.

**Evidence artifact:** external WP-O2 AgentOps report containing before/after
consumer matrix and canonical count fixture.

**Forbidden/non-goals:** no BROKEN_REGISTER content cleanup, no runtime-status
claim upgrade, no host verdict work, no new parser class/grammar family.

**Kill criterion:** any seventh direct parser found at implementation SHA must
stop the packet. Obtain an operator-approved envelope/ownership amendment or
record a blocking dependency; do not ship a false “one parser” claim.

#### WP-O2R — corrective truth-ledger reconciliation

WP-O2R is a narrow post-WP-O4R correction discovered while reconciling exact
main after PR #926. The canonical WP-O2 envelope above deliberately forbids
BROKEN_REGISTER content cleanup, runtime-status claim upgrades, and host
verdict work, so that authority must not be borrowed for this repair. WP-O2R
may be sealed only after a separately reviewed `WP-O2-B3` authority bootstrap
has merged. The bootstrap admits literal `WP-O2R` as one exact Session Entry
identity and grants the two otherwise-unowned ledgers as exact packet-scoped
shared-surface exceptions. They do not become broad One-Door
`owned_surfaces`. The bootstrap does not perform the reconciliation or
generalize arbitrary `WP-O<N>R` suffixes. B3 is used because B0-B2 are already
tracked, unrelated WP-O2 corrective packets and must remain immutable.

The WP-O2R implementation envelope is exactly:

- `docs/governance/ACTIVE_TRACK.yaml`
- `CLAUDE.md`
- `docs/governance/SOVEREIGN_MANIFEST.md`
- `docs/governance/BUILD_SESSION_ENTRYPOINT.md`
- `docs/docops/AUTO_INVENTORY.md`
- `docs/state/BROKEN_REGISTER.md`
- `INTERFACE_MISMATCH_MAP.md`
- `tests/test_onboarding_broken_register.py`
- `reports/agentops/work_packets/onboard-one-door-WP-O2R.json`

It may only reconcile landed One-Door authority and implementation history,
managed projections, canonical broken-register counts/lifecycle labels, and
explicitly bounded evidence already observed for those ledger claims.
Host-local evidence must include exact read-only commands and outputs while
typing clean clone, CI, every other seat, fleet topology, and consolidation
authority as Unobserved. Every named WP-O2 behavior test remains required;
in particular, `test_header_count_drift_is_reported` must keep a synthetic
stale-header fixture while a separate positive test proves the current
register and mismatch-map projections agree.

Acceptance requires fresh exact-main preflight, committed-range closeout,
exact PR-event replay, a meaningful exact-base stale-ledger control, zero
generated or ignored source leaves, and independent review. WP-O2R changes no
parser/runtime behavior, database contents, scheduler state, receipt writer,
cache, fallback scraper, merge authority, strict default, One-Door closure,
or Titanium readiness.

### WP-O3 — Unified CLI, readiness, receipt cache, live delta, and host typing (L)

**Closes:** hidden refresh/network mutation, lossful precedence, v2 writer,
determinism/cache, and untyped host gaps.

**Owner:** D1-admitted track owner.

**Prerequisites / merge dependency:** WP-O1 and WP-O2 merged; D3 external-reader
inventory resolved before the writer changes; D2 not yet required.

**Allowed files:**

- `dharma_swarm/operator_core/onboarding/evidence.py`
- `dharma_swarm/operator_core/onboarding/readiness.py`
- `dharma_swarm/operator_core/onboarding/render.py`
- `dharma_swarm/operator_core/onboarding/cli.py`
- `dharma_swarm/operator_core/onboarding/models.py` only for an interface
  insufficiency proven by a failing test
- `dharma_swarm/operator_core/onboarding/contract.py` under the same condition
- `dharma_swarm/operator_core/onboarding/receipt.py` under the same condition
- `scripts/governance/agent_onboard.py` as compatibility shim
- `tests/test_onboarding_cli.py`
- `tests/test_onboarding_readiness.py`
- `tests/test_onboarding_cache.py`
- `tests/test_agent_onboard.py`
- `reports/agentops/work_packets/onboard-one-door-WP-O3.json`

**Behavior → named test map:**

| ID | Behavior | Failing-first test |
|---|---|---|
| O3-B1 | Default path performs no network and invokes no hidden producer/criterion | `test_default_socket_guard_and_no_refresh_subprocess` |
| O3-B2 | Exit precedence retains all simultaneous conditions | `test_exit_precedence_condition_matrix` |
| O3-B3 | Mandatory warn/skip/unavailable never counts pass | `test_nonpass_states_cannot_produce_ready` |
| O3-B4 | Static cache hits only on full manifest match; every declared invalidator misses; hard/live checks always rerun | `test_each_manifest_invalidator_forces_miss`, `test_cache_hit_cannot_override_current_failure` |
| O3-B5 | Corrupt/poisoned/concurrent/stale/future/cross-repo receipts fail closed as §3 requires | `test_cache_adversarial_matrix` |
| O3-B6 | Deterministic JSON and stable digest obey stable/live partition, including same bytes with different mtimes/inodes | `test_repeated_json_is_byte_identical`, `test_nested_live_volatility_does_not_change_stable_digest`, `test_same_bytes_different_mtime_keeps_stable_core` |
| O3-B7 | `needs_host` gap/next-action chain is task-aware; executed failure stays fail | `test_host_scope_matrix` |
| O3-B8 | Default/deep/json attempt no repository or `.git` write, including ignored and byte-identical files | `test_all_entry_modes_attempt_no_repository_write` |
| O3-B9 | v2 writer follows reader-first matrix; v1 is legacy display-only and cannot seed cache/delta | `test_writer_migration_and_rollback_matrix` |
| O3-B10 | Receipt write failure/inside-repo path cannot return READY | `test_receipt_persistence_is_admission_requirement` |
| O3-B11 | Pre-WP-O5 legacy exit mode changes only process exit, never v2 schema or observed conditions | `test_legacy_exit_compatibility_never_changes_v2_truth` |

Before WP-O5, strict exits are reachable only through `--strict` /
`DHARMA_ONBOARD_STRICT=1`. Default exit compatibility remains, but v2 receipts
must still truthfully state conditions; no receipt may label a blocked legacy
run READY.

**Verification / expected exit:**

```bash
python3 -m pytest tests/test_onboarding_cli.py \
  tests/test_onboarding_readiness.py tests/test_onboarding_cache.py \
  tests/test_agent_onboard.py -q
# expected: 0
python3 -m pytest tests/test_onboarding_cli.py \
  -q -k 'strict_ready_fixture or strict_blocked_fixture'
# expected: 0; the fixtures assert underlying process exits 0 and 1 exactly
```

**Rollback:** revert CLI/writer/readiness/cache as one packet; leave the
v1/v2 loader and canonical parser. Remove the disposable v2 receipt or let the
v1 writer replace it.

**Evidence artifact:** external WP-O3 AgentOps report plus the single v2
receipt under the same temporary external `DHARMA_OPS_DIR` fixture.

**Forbidden/non-goals:** no Make/CI alias change, no strict-default flip, no
active-track checker rewrite, no network-derived admission, no second cache
file/history.

**Kill criterion:** any cache path that can suppress a current hard check or
any default path that can execute a network-capable transitive command blocks
merge.

### WP-O4 — Make, AgentOps envelope, mutation-free orient, closeout, and CI parity (L)

**Closes:** double render, non-enforced committed diff scope, writeful orient,
and missing CI consumer.

**Owner:** D1-admitted track owner.

**Prerequisites / merge dependency:** WP-O3 merged; A3 has repaired the stale
`make orient` instruction in its own authority-owned change; CI workflow
ownership rechecked. WP-O4 adds a fail-on-error CI invocation but does not
claim merge authority; C1 must separately promote that context before WP-O5.

**Allowed files:**

- `Makefile`
- `scripts/governance/orientation_graph.py` compatibility shim only
- `scripts/governance/run_agent_work_packet.py`
- `docs/governance/AGENTOPS.md`
- `.github/workflows/active-track.yml` — one fail-on-error invocation of the
  shared evaluator/envelope; no publish-status or branch-protection change
- `tests/test_agent_work_packet.py`
- `tests/test_orientation_graph.py`
- `tests/test_make_onboarding_contract.py`
- `tests/test_onboarding_ci_contract.py`
- `reports/agentops/work_packets/onboard-one-door-WP-O4.json`

**Behavior → named test map:**

| ID | Behavior | Failing-first test |
|---|---|---|
| O4-B1 | `make orient` is deep/read-only under a write-attempt guard; only explicit direct refresh writes context | `test_make_orient_attempts_no_repository_write`, `test_explicit_context_refresh_writes_only_two_paths` |
| O4-B2 | Preflight consumes packet/shared evaluator exactly once and requires exact clean baseline | `test_preflight_single_evaluation_and_exact_base` |
| O4-B3 | Closeout checks `base...HEAD` + working/staged/untracked union and same packet digest | `test_closeout_rejects_each_diff_class_and_packet_swap` |
| O4-B4 | Existing AgentOps forbidden-over-allowed semantics cover committed diffs | `test_agentops_committed_range_scope_gate` |
| O4-B5 | CI calls the same command with no weaker flags/continue-on-error | `test_ci_and_local_admission_command_equivalence` |
| O4-B6 | Existing verifier nonzero propagation remains intact | `test_verifier_selfcheck_propagates_onboard_failure` |
| O4-B7 | `make agent-onboard` remains unchanged | `test_a2a_identity_target_command_is_unchanged` |
| O4-B8 | Make forwards documented `ARGS`; unknown flags preserve exit 2 | `test_make_forwards_onboard_args_and_usage_exit` |
| O4-B9 | Preflight/closeout write only to the external root; syscall guard plus ordinary/ignored status prove no source write attempt | `test_make_admission_reports_are_external_and_read_only` |
| O4-B10 | PR CI checks out the declared head; merge-group packets are each bound or the group blocks | `test_ci_pr_head_and_merge_group_packet_binding` |
| O4-B11 | Positive gates use one fail-closed command-family allowlist before execution: exact O1R Git grammar and explicitly enumerated pytest/Ruff/read-only governance/DocOps/Make forms pass; inline interpreters, alternate mutation/network clients, shell-capable wrappers, and unknown executables fail | `test_positive_gate_command_family_allowlist_rejects_transitive_routes` |

#### WP-O4R — corrective generated-artifact confinement repair

WP-O4R is a narrow post-WP-O4 corrective packet discovered during exact-main
closeout after PR #920. It may be sealed only after the separately reviewed
`WP-O4-B0` authority bootstrap has merged. That bootstrap admits the literal
`WP-O4R` Session Entry identity and the three previously unowned surfaces; it
does not implement this repair and must not generalize arbitrary `WP-O<N>R`
suffixes.

The WP-O4R implementation envelope is exactly:

- `scripts/governance/check_track_status.py`
- `scripts/governance/run_agent_work_packet.py`
- `tests/test_active_track_governance.py`
- `tests/test_agent_work_packet.py`
- `tests/test_onboarding_broken_register.py`
- `tests/test_track_portfolio.py`
- `reports/agentops/work_packets/onboard-one-door-WP-O4R.json`

It may only route Hypothesis/cache storage outside source, make active-track
report output explicitly relocatable, prevent the dependency-bootstrap probe
from writing bytecode, resolve admitted bare Python criteria through the
current interpreter, and add the tests needed to prove those boundaries.
Acceptance requires a fresh exact-main preflight, committed-range closeout,
exact PR-event replay, zero generated or ignored source leaves, and independent
review. It does not close the wider WP-O4 syscall boundary, WP-O6, C1, or the
One-Door track.

CI packet discovery is conditional and fail-closed. A PR with no change in the
onboarding track's owned surfaces runs the shared baseline evaluator but needs
no packet. A PR that changes any owned surface must change exactly one matching
WP packet. PR jobs check out the declared PR head SHA, not a synthetic merge
tree, and pass the event base/head explicitly. A merge group evaluates every
changed onboarding packet in stable order, rejects overlaps, and binds each
declared base to the group diff; if the workflow cannot establish that mapping,
it returns `CONFIG_ERROR` rather than skipping or weakening the check.

O4-B11 is the owner of positive-gate execution admission; O1R remains the
owner of direct token normalization and direct Git grammar. The allowlist is
one authoritative table, not scattered executable checks. It rejects at least
`python -c`, `python -`, `node -e`, `ruby -e`, `perl -e`, `gh`, `ssh`, `scp`,
`curl`, `wget`, every shell-capable wrapper, and every unknown executable. Its
acceptance matrix is limited to the exact O1R Git grammar plus explicitly
enumerated `python -m pytest`, `python -m ruff check`, read-only repository
governance/DocOps scripts, and Make targets required by admitted packets.
Packet-supplied environment is empty by default; any allowed key/value shape
is enumerated and path-confined rather than passed through generically.
Extending the table requires a governance-reviewed admission change.

This is command-family confinement, not semantic proof about trusted code:
pytest and an allowlisted repository script can themselves perform I/O. The
test proves the five direct witnesses below are rejected before subprocess
execution, while WP-O6's syscall/no-network proof remains the terminal oracle:

```text
python3 -c "import subprocess; subprocess.run(['git','push','origin','HEAD'])"
python3 -c "import os; os.system('git push origin HEAD')"
gh pr merge 1
ssh host git-receive-pack repo
curl -X POST https://api.github.invalid/merges
```

**Verification / expected exit:**

```bash
python3 -m pytest tests/test_agent_work_packet.py \
  tests/test_orientation_graph.py tests/test_make_onboarding_contract.py \
  tests/test_onboarding_ci_contract.py -q
# expected: 0
make agent-build-preflight \
  PACKET="$DHARMA_OPS_DIR/entry_packets/onboard-one-door-WP-O4.json"
# expected: 0 at exact clean baseline before the first implementation edit
make agent-build-closeout PACKET=reports/agentops/work_packets/onboard-one-door-WP-O4.json
# expected: 0 only when packet gates and complete envelope pass
```

**Rollback:** revert Makefile, AgentOps, orient shim, docs, and CI call together.
Do not leave local and CI on different packet semantics.

**Evidence artifact:** CI artifact containing the existing AgentOps report
schema and onboarding JSON; all local/CI report roots are explicit external
paths and no report enters the worktree.

**Forbidden/non-goals:** no new workflow, no branch-protection edit, no merge
authority change, no generated context refresh in CI, no Titanium workflow.

**Kill criterion:** if CI cannot discover exactly one packet or reproduce the
local scope result from base/head, strict default cannot proceed.

#### WP-O4-B1 — Gate-0 sequencing and WP-O2R seal successor

WP-O4-B1 is a one-time governance-only clarification after PR #928. It keeps
C1 as one formal node but makes its pre-WP-O5 unlock proof and post-WP-O5 final
enforcement proof explicit; reconciles WP-O2R from prospective to merged but
unsealed truth; and adds one regression that prevents the circular sequence
from returning. The operator's 2026-07-14 terminal-closure directive is the
proposal authority, but this packet is not ratified or sealed merely by being
authored: `approval.before_merge=true`, a final exact-head council receipt, and
a legitimate non-author/operator approval remain mandatory.

Its implementation envelope is exactly
`docs/governance/ACTIVE_TRACK.yaml`, this specification, the three existing
managed authority projections, `tests/test_active_track_governance.py`, and
`reports/agentops/work_packets/onboard-one-door-WP-O4-B1.json`. It changes no
runtime, workflow, branch setting, writer, cache, strict default, receipt store,
fleet claim, or formal closure-node count. The packet classifies PR #928's
cross-environment AgentOps discrepancy from the exact six-node successor
manifest, byte-identical production runner/test blobs, and paired replays on
unmodified base and candidate revisions. Both pass all six under external
Python 3.12/root-chroot, reproduce only the bytecode node under a checkout-local
venv/root-chroot, and reproduce all six under controlled unavailable-confinement
injection. This is environment/capability-sensitive and base-reproducible, not a
successor regression; proprietary-runner conditions remain `Unobserved`; no failed run is waived and exact-head council/approval gates remain mandatory.

### WP-O5 — Strict-by-default promotion (S; isolated; operator-gated)

**Closes:** the intentional always-zero session contract.

**Owner:** D1-admitted track owner; D2 remains operator-owned.

**Prerequisites / merge dependency:** WP-O4 merged and green in CI; the
pre-WP-O5 C1 authority/unlock proof has made the same admission context
merge-blocking using exactly `make onboard ARGS=--strict`; D2 ratification has
merged in the operator-owned form in §9.2; no unexplained baseline red.

**Allowed files:**

- `dharma_swarm/operator_core/onboarding/readiness.py` — default only
- `scripts/governance/agent_onboard.py` — docstring/default shim only
- `tests/test_agent_onboard.py`
- `tests/test_onboarding_readiness.py`
- `tests/test_make_onboarding_contract.py`
- `tests/test_onboarding_ci_contract.py`
- `Makefile` only if default flag plumbing is unavoidable
- `docs/governance/BUILD_SESSION_ENTRYPOINT.md` — concise behavior note
- `reports/agentops/work_packets/onboard-one-door-WP-O5.json`

**Behavior → named test map:**

| ID | Behavior | Failing-first test |
|---|---|---|
| O5-B1 | Strict verdict exits become default; generic exit-0 test is replaced deliberately | `test_onboard_default_exit_matrix` |
| O5-B2 | `--no-strict` preserves one deprecation cycle without lying in the receipt | `test_no_strict_changes_process_exit_not_observed_conditions` |
| O5-B3 | Make/preflight/closeout/CI propagate the same default exits | `test_strict_default_propagates_across_all_consumers` |
| O5-B4 | Promotion requires the separately merged D2 owner record and cannot self-promote | `test_strict_promotion_requires_operator_owned_d2_record` |
| O5-B5 | The CI context is merge-blocking before promotion, never advisory-only | `test_strict_promotion_requires_c1_context_evidence` |

`--no-strict` lasts one documented release cycle. Its removal is a later
operator-reviewed change, never a timer inside the gate or part of WP-O5.

**Verification / expected exit:**

```bash
python3 -m pytest tests/test_agent_onboard.py \
  tests/test_onboarding_readiness.py tests/test_make_onboarding_contract.py \
  tests/test_onboarding_ci_contract.py -q
# expected: 0
```

**Rollback:** revert the one WP-O5 commit. The rollback restores legacy process
exit behavior only; v2 conditions, parser, packet enforcement, and CI scope
checks remain. Reopen the strictness finding explicitly.

**Evidence artifact:** external WP-O5 AgentOps/CI report with D2 reference and
exit matrix.

**Forbidden/non-goals:** no other packet work, no gate weakening, no hidden
exception for CI, no automatic promotion.

**Kill criterion:** any unexplained CI failure caused by the flip reverts the
whole packet; no partial bypass patch.

### WP-O6 — Performance, mutation strength, and clean-room hardening (L)

**Closes:** reproducible 40–70-line, warm/cold, mutation, concurrency, and
independent-verifier exit requirements.

**Owner:** D1-admitted track owner.

**Prerequisites / merge dependency:** full WP-O3 activation, WP-O5, the final
post-WP-O5 C1 enforcement proof, and M6-1 must all be merged and reverified on
current `main`. `pyproject.toml` is owned by the active DharmaGraph track at
this baseline (`docs/governance/ACTIVE_TRACK.yaml:885-904`), so M6-1 must either
have that owner land the exact configuration change or merge an explicit
ownership transfer before WP-O6 admits the file.

**Allowed files after M6-1:**

- `tests/test_onboarding_performance.py`
- `tests/test_onboarding_clean_room.py`
- `tests/test_onboarding_mutation.py`
- `tests/properties/test_onboarding_readiness_properties.py`
- `tests/test_onboarding_cache.py`
- `dharma_swarm/operator_core/onboarding/receipt.py`
- `dharma_swarm/operator_core/onboarding/readiness.py`
- `dharma_swarm/operator_core/onboarding/render.py`
- `dharma_swarm/operator_core/onboarding/evidence.py`
- `dharma_swarm/operator_core/onboarding/cli.py`
- `pyproject.toml` only after M6-1, limited to widening the existing mutmut
  configuration
- `.github/workflows/active-track.yml` only to run the already-wired clean-room
  proof; no authority/required-check changes
- `reports/agentops/work_packets/onboard-one-door-WP-O6.json`

**Behavior → named test map:**

| ID | Behavior | Failing-first test |
|---|---|---|
| O6-B1 | Warm/cold definitions and p50/p95 targets are reproducible | `test_performance_protocol_and_thresholds` |
| O6-B2 | Human stdout is always 40–70 lines on READY and each failure class | `test_compact_render_line_budget_matrix` |
| O6-B3 | Stable machine projection is byte-identical; live conditions are typed/sorted | `test_clean_room_json_replay_is_byte_identical` |
| O6-B4 | Concurrent writers and crash-before-replace preserve valid predecessor/successor | `test_receipt_concurrency_and_crash_matrix` |
| O6-B5 | Required readiness mutants are killed | mutation report plus `test_required_mutant_ids_have_zero_survivors` |
| O6-B6 | Fresh-clone entry commands attempt no source/`.git` write or socket and leave ordinary/ignored status unchanged | `test_clean_room_entry_commands_are_read_only`, `test_entry_trace_has_no_repo_write_or_network_attempt` |
| O6-B7 | All blocking controls return exact nonzero codes, optional host absence stays typed exit 0, and simultaneous states remain lossless | `test_clean_room_negative_control_exit_matrix`, `test_simultaneous_condition_retention` |

Required mutants: stale-evidence→READY; failed-sentinel→READY;
`NEEDS_HOST`→pass under `--require-live`; skipped mandatory→pass; cache-hit
overrides live failure; config/tool/blocked precedence swaps; packet-diff range
omitted.

**Verification / expected exit:**

```bash
python3 -m pytest tests/test_onboarding_performance.py \
  tests/test_onboarding_readiness.py tests/test_onboarding_cache.py \
  tests/test_onboarding_clean_room.py \
  tests/properties/test_onboarding_readiness_properties.py -q
# expected: 0
# In a disposable external clone, after frozen dev bootstrap:
make mutation-test
# expected: 0; then copy mutmut-cicd-stats.json outside both worktrees
ONBOARD_MUTATION_STATS="$DHARMA_OPS_DIR/mutation/mutmut-cicd-stats.json" \
  python3 -m pytest tests/test_onboarding_mutation.py -q
# expected: 0 only when every named required mutant was killed
```

The aggregate threshold is necessary but insufficient. The mutation run occurs
first; the second command reads its external exported stats and fails if any
required mutant ID survived or was not generated. `mutants/` and the normalized
report exist only in the disposable clone/external evidence root, never the
admitted source worktree.

**Rollback:** revert only measured optimization changes first; keep correctness
tests and honest timing evidence. If the mutmut widening is rolled back, reopen
the mutation-strength criterion explicitly.

**Evidence artifact:** performance and mutation sections inside the external
onboard/AgentOps evidence roots; the independent clean-room receipt is written
outside the worktree (§13). Do not reuse or create a second orientation timing
receipt.

**Forbidden/non-goals:** no performance win by deleting/deferring a required
check; no active DharmaGraph surface edit without M6-1; no production claim.

**Kill criterion:** correctness wins over latency. A miss is recorded honestly
and blocks completion; it is not “fixed” by making a mandatory probe optional.

### 6.1 Dependency graph, critical path, and parallel work

**Critical path:** D1 → WP-O1 → WP-O1R-B0 → WP-O1R → WP-O2 → A3 → WP-O4 →
WP-O2R reseal → pre-WP-O5 C1 authority/unlock proof → D2 → WP-O5 → final C1
enforcement proof → WP-O6 → independent proof. D3 → WP-O3 activation and M6-1
are parallel lanes that may advance after reseal but must join before WP-O6.
A1+A2+A4 are external adapter prerequisites that
must join before the independent proof. The two C1 proofs are phases of one
formal C1 node, not additional closure nodes.

Parser fixtures can be prepared in parallel with WP-O1 after the shared model
interface is frozen. The named performance and clean-room test harnesses may be
prepared after WP-O3, but final measurements/mutation results wait for the
WP-O5 default and M6-1. A1/A2/A4 do not authorize edits in this campaign, but they
must be repaired by their owners before terminal certification. WP-O1/O3 are
the largest implementation risks; WP-O6 is the largest verification risk.

## §7 Global negative-control matrix

| Control | Expected primary/exit |
|---|---:|
| Missing `CLAUDE.md` or root `AGENTS.md`; corrupt `ACTIVE_TRACK.yaml` | `CONFIG_ERROR` / 3 |
| Invalid flag plus ownership conflict | usage / 2, with both conditions retained |
| Wrong or dirty packet baseline | `BLOCKED` / 1 |
| Undeclared or forbidden committed/working file | `BLOCKED` / 1 |
| Exact, ancestor/descendant, glob, or actual-diff owner overlap | `BLOCKED` / 1 |
| Missing/wrong universally required tool | `TOOLCHAIN_MISSING` / 5 |
| Missing live owner host, hermetic scope | `NEEDS_HOST` / 0, never pass-like |
| Missing live owner host under `--require-live` | `NEEDS_HOST` / 4 |
| Stale/unbound generated projection | `BLOCKED` / 1 |
| Corrupt/partial/digest-mismatch receipt | `BLOCKED` / 1 on detection run |
| Future unknown receipt major | `CONFIG_ERROR` / 3 |
| Sprawl/worktree budget violation | `BLOCKED` / 1 |
| Default socket attempt or hidden refresh | guard test process / 1 |
| Default/orient write attempt to tracked, untracked, ignored, identical, or `.git` path | read-only guard process / 1 |
| Bold fixed BR reappears open at any consumer | parser suite process / 1 |

## §8 Performance contract

### 8.1 Cold

- Clean non-shallow clone at one exact SHA.
- Dependencies bootstrapped before timing with `uv sync --frozen --extra dev` from
  `uv.lock`; record uv/Python/distribution/tool versions and lock digest.
- Empty external `DHARMA_OPS_DIR` for each sample; no prior onboard receipt.
- Required generated projections are produced by a documented untimed
  bootstrap with producer/input/HEAD binding. If absent, onboarding must return
  a fast typed block; it must not refresh inside the timed command.
- Network denied; credentials absent; normalized locale/timezone; no inherited
  `.venv`, node tree, tool cache, generated state, or home receipts.
- Ten independent semantic-cold samples; report p50 and p95. OS page cache is
  not claimed cold unless explicitly controlled and recorded.
- Pass threshold: p95 < 5.0 s.

### 8.2 Warm

- One successful cold v2 receipt seeds the cache.
- Same SHA, branch, packet, dependency environment, tool versions, generated
  owner bindings, and clean git state.
- Twenty consecutive samples; report p50 and p95.
- Pass threshold: p95 < 1.0 s.

For both modes, sort unrounded monotonic durations ascending and use the
nearest-rank estimator: percentile `p` is element `ceil(p*n)` (one-based).
Thus cold p95 is sample 10 of 10 and warm p95 is sample 19 of 20. Report the
full sample vector as well as p50/p95; do not substitute an interpolating
library default.

### 8.3 Output and determinism

- Human stdout: 40–70 `str.splitlines()` entries inclusive for each verdict
  class, after ANSI stripping; the conventional final newline does not add a
  line. Diagnostic stderr is separately captured and must not contain
  unstructured tracebacks.
- Default network calls: zero, including transitive criterion execution.
- Default repository write attempts: zero across tracked, untracked, ignored,
  byte-identical, and `.git` paths, enforced by an OS/filesystem guard plus a
  full before/after inventory—not porcelain alone.
- JSON stdout: byte-identical across repeated unchanged runs; receipt volatile
  metadata may differ only in its explicit `observed_at`/live partition.
- Timing record includes SHA, dirty status, packet/cache key, lock digest,
  environment class, commands, repetitions, sample vector, p50/p95, and line
  counts.

## §9 Ownership, operator decisions, adapters, and urgent boundary

### 9.1 D1 — governance admission before implementation

**Operator decision D1 remains open:** admit a standalone
`onboard-one-door-2026-07` track or explicitly fold the full surface union into
`sovereign-safety-tcb-2026-07`. Either choice requires a governance-only PR,
managed-block regeneration, exact owner collision analysis, and ownership of
the packet namespace. It does not create future packet files; §4 materializes
each at its exact future baseline. It is not a one-line edit. A standalone
track would be the tenth active track at the hard ceiling: on 2026-07-10,
`python3 -c 'import pathlib,yaml; print(len(yaml.safe_load(pathlib.Path("docs/governance/ACTIVE_TRACK.yaml").read_text())["active_tracks"]))'`
exited 0 with `9`, and policy sets `max_active: 10`
(`docs/governance/ACTIVE_TRACK.yaml:77-85`). D1 must therefore
be an explicit WIP decision, not automatic admission.

Minimum standalone ownership union (recheck at admission SHA):

```yaml
- id: onboard-one-door-2026-07
  name: One-door onboarding — strict, fast, deterministic session admission
  status: ACTIVE
  serves: substrate-nativeness
  owner: "@AmitabhainArunachala"
  complements: [sovereign-safety-tcb-2026-07, merge-master-mike-d4-2026-06]
  owned_surfaces:
    - AGENTS.md
    - Makefile
    - .github/workflows/structure.yml
    - .github/workflows/active-track.yml
    - docs/governance/ANTI_SLOP_RULES.md
    - docs/governance/AGENTOPS.md
    - docs/governance/BUILD_SESSION_ENTRYPOINT.md
    - scripts/docops/check_docops_integrity.py
    - scripts/governance/agent_onboard.py
    - scripts/governance/orientation_graph.py
    - scripts/governance/trust_gate_status.py
    - scripts/governance/repo_status.py
    - scripts/governance/run_agent_work_packet.py
    - dharma_swarm/operator_core/onboarding/**
    - dharma_swarm/operator_core/control_surface.py
    - dharma_swarm/operator_core/control_surface_models.py
    - dharma_swarm/operator_core/operator_coherence/git_governance.py
    - tests/test_agent_onboard.py
    - tests/test_orientation_graph.py
    - tests/test_trust_gate_status.py
    - tests/test_repo_status.py
    - tests/test_control_surface.py
    - tests/test_operator_coherence_cockpit.py
    - tests/test_agent_work_packet.py
    - tests/test_docops_integrity.py
    - tests/test_make_onboarding_contract.py
    - tests/test_onboarding_*.py
    - tests/properties/test_onboarding_readiness_properties.py
    - reports/agentops/work_packets/onboard-one-door-WP-O*.json
  moves_vital_signs: [quality_gates, context_efficiency]
  next_items:
    - id: D2
      what: "D2 PENDING — operator ratification of strict-by-default after WP-O4/C1"
      kind: governance
      blocker: true
    - id: C1
      what: "C1 PENDING — merge-authority owner promotes the shared admission context"
      kind: governance
      blocker: true
  non_goals:
    - No gate weakening, new truth store, receipt store, digest primitive, or parser family.
    - No Titanium, production, CLOSED_LIVE, merge-authority, or branch-protection work.
    - No strict-default promotion without D2.
    - No active sibling-track surface edit; pyproject waits for M6-1.
```

The admission PR must list every WP completion criterion as behavioral command
or valid receipt evidence; file existence alone is insufficient. If folded
into the safety track, the same owned-surface and packet requirements apply.

### 9.2 D2 — strict-by-default

**Operator decision D2 remains open and unchanged:** explicitly ratify the
WP-O5 strict-by-default flip after the pre-WP-O5 C1 authority/unlock proof.
Approval “in principle” is not the promotion marker. The implementation author
cannot mint this approval.

D2 is recorded through a separately merged, operator-authored governance PR:
the admitted track's existing `next_items[D2]` entry changes from `PENDING,
blocker: true` to exactly `D2 RATIFIED — operator=<handle>; pr=<number>;
merge_commit=<40-hex>; scope=WP-O5-strict-default`, `blocker: false`, and the
three managed authority blocks are regenerated. WP-O5 forbids those owner
files; preflight verifies the referenced commit is an ancestor and the record
predates the WP-O5 baseline. This reuses `ACTIVE_TRACK.yaml` and git history;
it is not a general approval engine or proof of cryptographic identity.

### 9.3 D3 — off-repo receipt consumers

**Operator decision D3:** identify every external fleet reader of
`~/.dharma/ops/onboard_receipt.json`, approve its v2 upgrade, or explicitly
confirm that no such reader remains. WP-O3 cannot switch the writer first.

### 9.4 C1 — merge-blocking CI admission

**C1 is one external merge-authority node with two ordered proofs, not a
WP-O4/O5 file grab.** The tracked parity manifest now names `Onboarding
admission parity` (`scripts/governance/ci_parity_manifest.json:38-41`); the
workflow binds both `pull_request` and `merge_group` and checks out the declared
event head (`.github/workflows/active-track.yml:19-23,106-109,130-134`); and the
automerge policy consumes the manifest's complete required-context set
(`.github/workflows/automerge.yml:99-123,196-200,243-260`). Those tracked surfaces do not prove
the live required-check/ruleset binding, path-filter safety, or an observed
merge-group rejection. Before WP-O5 the required job also invokes plain `make
onboard`, whose documented legacy compatibility returns zero for BLOCKED truth
(`.github/workflows/active-track.yml:150-155`, `dharma_swarm/operator_core/onboarding/cli.py:291-296`).

The **pre-WP-O5 authority/unlock proof** must therefore bind the canonical
context and parity manifest to live GitHub required-check enforcement; prove
the pull-request event and path-filter behavior; observe automerge and
merge-queue/`merge_group` behavior; and preserve one controlled BLOCKED proof
using exactly `make onboard ARGS=--strict`. It may unlock D2 and WP-O5, but it
does not close C1 and must not silently change the required job to smuggle the
strict-default flip into this phase.

After D2 and WP-O5 merge, the **post-WP-O5 final enforcement proof** repeats the
controlled BLOCKED case with plain `make onboard` and demonstrates rejection
by the actual required context, branch protection, automerge, and merge queue.
Only that second proof closes C1. WP-O6 and terminal proof remain blocked until
it passes. This campaign creates no second CI-authority store.

### 9.5 A1/A2/A3/A4 — adapter and instruction-custody dependencies

- A1: repair `DEVIN.md`'s hard-coded checkout/`git pull main`/adjacent-expansion
  conflict in its own authority-owned change.
- A2: demote or refresh `QWEN.md`'s hard-coded stale branch/dirty-state adapter
  in its own authority-owned change.
- A3: repair `docs/governance/NEXT_BUILD_RUN_PROMPT.md:24-30`, which currently
  orders `make orient` to regenerate tracked context, in its own
  authority-owned change before WP-O4 changes that command.
- A4: repair `docs/AGENTS.md:14-26` so owner files—not a generated onboarding
  projection—win conflicts, without expanding WP-O1 into docs-wide cleanup.

These adapters must defer to the one-door packet discipline once repaired, but
this campaign does not edit them.

### 9.6 M6-1 — shared `pyproject.toml`

WP-O6 may widen the existing mutmut surface only after the active DharmaGraph
owner either (a) lands that exact configuration change under its own admitted
packet, leaving `pyproject.toml` forbidden to WP-O6, or (b) a governance PR
explicitly transfers/removes its ownership before WP-O6 admits the file. A
warning-only overlap is not coordination. Until one of those two concrete
paths merges, the file is forbidden.

### 9.7 U1 — immediate operator verification, outside this spec

On the actual daemon/VPS host, verify listener address, Docker port exposure,
firewall/cloud security group, reverse-proxy ingress, and
`DASHBOARD_API_KEY`. If the FastAPI control plane is reachable beyond trusted
ingress without bearer auth, immediately contain it (close/public-unpublish
8080 or require trusted tunnel/ingress and key) before continuing normal work.
Record the observation separately. This repository evidence establishes a
risky deploy path, not present external reachability.

## §10 Completion criteria

This campaign is complete only when:

1. §1 claims remain current-HEAD cited and unsupported evidence language is
   removed;
2. onboard, orient, preflight, closeout, CI, and A2A identity join have the
   non-overlapping responsibilities in §2;
3. scalar precedence retains every observed condition and no nonpass check is
   promoted to pass;
4. cache manifest, stable/live partition, concurrency, poisoning, invalidation,
   and receipt migration matrices pass;
5. all six broken-register consumers use one normalized parser;
6. every WP has exact owner, envelope, test map, expected exits, rollback,
   evidence, non-goals, merge dependency, and S/M/L estimate;
7. mandatory Session Entry Packets and committed+working diff scope are
   mechanically enforced locally and in CI;
8. D1/D2/D3 and M6-1 are resolved at their specified boundaries;
9. performance/output targets pass without weakening a check;
10. independent clean-room proof passes with its receipt outside the worktree;
11. Titanium remains blocked until that proof merges.

## §11 Validation for this specification-only refinement

Before committing this document:

```bash
git diff --check
python3 scripts/docops/check_docops_integrity.py --changed-from 5e7304c7df36b0fe6a34ae458b6cc0212b2106b6
python3 scripts/governance/render_active_track_includes.py --check
python3 scripts/governance/hygiene/check_hygiene_integrity.py
pre-commit run --files docs/plans/ONBOARD_ONE_DOOR_HARDENING_SPEC_2026-07-10.md
```

If a tool/dependency is unavailable, record the exact command and exit instead
of skipping it silently. Classify pre-existing count drift separately from a
new failure. Confirm only this file changed, no generated report/receipt entered
the diff, every citation resolves at the reviewed SHA, all 14 adjudication
rows/counts agree, all Behavior IDs map to named tests, and D1/D2 remain open.

## §12 Reference index

- `scripts/governance/agent_onboard.py` — current door, refresh, receipt writer,
  v1 schema, flags, and exit behavior.
- `scripts/governance/orientation_graph.py` — current deep projection, tracked
  context refresh, packet hash, and exit modes.
- `scripts/governance/check_track_status.py` — current criterion executor and
  ignored rollup producer.
- `scripts/governance/run_agent_work_packet.py` and
  `docs/governance/AGENTOPS.md` — existing packet/envelope engine to extend.
- `dharma_swarm/memory_kernel/write_receipts.py:336-345` — mandated canonical
  JSON/digest/time primitives.
- `scripts/governance/tam_ledger.py:324-377` — existing fail-closed replay
  pattern; adapted, not copied inaccurately.
- `dharma_swarm/world_radar/go_invoke.py:30-56`,
  `scripts/loop5b_world_radar_closure_run.py:257-270`, and
  `dharma_swarm/operator_core/control_surface_go.py:159-197` — existing
  `needs_host` vocabulary chain.
- `docs/governance/CANONICAL_DOC_STACK.md:32-69` — first reads and ownership.
- `docs/governance/ACTIVE_TRACK.yaml:77-85` — WIP and overlap policy.
- `docs/plans/DHARMAGRAPH_PHASED_SPEC_2026-07-05.md:67-70` — S/M/L convention.

## §13 Terminal independent clean-room proof and Titanium handoff

This is the final campaign gate, not an implementation-author rerun. It starts
only after WP-O1, WP-O1R-B0, WP-O1R, WP-O2..O5, D1/D2/D3, C1,
A1/A2/A3/A4, and M6-1 have merged and the WP-O6/final candidate is complete at
one remotely fetchable integration SHA.
The verifier has not authored the implementation and receives no
implementation-author assistance after the run starts. The passing artifact is
attached to that final PR/merge-group candidate; the proof and WP-O6 then merge
together without author changes.

### 13.1 Sterile acquisition and locked bootstrap

The verifier records the public HTTPS clone URL and candidate integration SHA,
then uses a new temporary root and new external state directories:

```bash
export VERIFY_ROOT="$(mktemp -d)"
export HOME="$VERIFY_ROOT/home"
export XDG_CACHE_HOME="$VERIFY_ROOT/xdg-cache"
export UV_CACHE_DIR="$VERIFY_ROOT/uv-cache"
export DHARMA_OPS_DIR="$VERIFY_ROOT/dharma-ops"
mkdir -p "$HOME" "$XDG_CACHE_HOME" "$UV_CACHE_DIR" "$DHARMA_OPS_DIR"
run_sterile() {
  env -i PATH="$PATH" HOME="$HOME" XDG_CACHE_HOME="$XDG_CACHE_HOME" \
    UV_CACHE_DIR="$UV_CACHE_DIR" DHARMA_OPS_DIR="$DHARMA_OPS_DIR" \
    ONBOARD_TRACE_ROOT="${ONBOARD_TRACE_ROOT:-}" \
    LC_ALL=C.UTF-8 LANG=C.UTF-8 TZ=UTC PYTHONHASHSEED=0 \
    PYTHONDONTWRITEBYTECODE=1 GIT_CONFIG_NOSYSTEM=1 \
    GIT_OPTIONAL_LOCKS=0 GIT_TERMINAL_PROMPT=0 GIT_ASKPASS=/bin/false "$@"
}
run_sterile locale charmap | rg -qx 'UTF-8'
test "$(run_sterile date +%Z)" = UTC
run_sterile git clone \
  https://github.com/AmitabhainArunachala/dharma_swarm.git "$VERIFY_ROOT/repo"
cd "$VERIFY_ROOT/repo"
run_sterile git fetch origin <candidate-integration-ref>
run_sterile git checkout --detach <candidate-integration-40-sha>
test "$(run_sterile git rev-parse --is-shallow-repository)" = false
test "$(run_sterile git rev-parse HEAD)" = <candidate-integration-40-sha>
run_sterile git switch -c verify/onboard-clean-room
test "$(run_sterile git branch --show-current)" = verify/onboard-clean-room
test -z "$(run_sterile git status --porcelain=v1)"
run_sterile uv sync --frozen --extra dev
export PATH="$PWD/.venv/bin:$PATH"
```

The clone is non-shallow and begins with no inherited `.venv`, dependency or
node tree, tool cache, ignored/generated state, credentials, home receipt, or
daemon database. Bootstrap network ends after the frozen-lock sync. Record the
contract manifest's mandated `stable_digest` entry for `uv.lock` and the exact
Python, uv, git, make, pytest, ruff,
hypothesis, mutmut, and Linux `strace` versions. Any deliberately required tool
absent from the lock or declared host toolchain blocks; it is not fetched ad
hoc during entry. `run_sterile` makes credentials absent before clone and
bootstrap, disables system/user git config and prompts, and allowlists every
environment variable inherited by entry. Run all entry commands under its
network/write-attempt trace below; inability to establish that trace is a
blocker, not a skipped probe.

### 13.2 Read-only successful path and deterministic core

Create a terminal-verification Session Entry Packet outside the worktree with
`base_ref == HEAD`, `branch: "verify/onboard-clean-room"`, `worktree: "."`,
empty implementation diff, the exact tool versions, and the normal packet
digest. It is verification-only and is not
copied into the repository. Capture ordinary and ignored-path status before
and after, and trace every filesystem/network syscall. The O6 trace test
resolves relative paths and fails on any attempted write under the repository
or `.git` (including ignored and byte-identical writes) or any socket attempt:

```bash
mkdir -p "$VERIFY_ROOT/traces"
trace_entry() {
  name="$1"; shift
  run_sterile strace -ff -qq -e trace=%file,%network \
    -o "$VERIFY_ROOT/traces/$name" "$@"
}
run_sterile git status --porcelain=v1 >"$VERIFY_ROOT/status.before"
run_sterile git status --porcelain=v1 --ignored=matching >"$VERIFY_ROOT/all.before"
trace_entry onboard make onboard
trace_entry onboard-json make onboard ARGS=--json >"$VERIFY_ROOT/onboard-1.json"
trace_entry onboard-deep make onboard ARGS=--deep >"$VERIFY_ROOT/onboard.deep.txt"
trace_entry orient make orient >"$VERIFY_ROOT/orient.txt"
trace_entry preflight make agent-build-preflight \
  PACKET="$DHARMA_OPS_DIR/entry_packets/terminal-verification.json"
trace_entry closeout make agent-build-closeout \
  PACKET="$DHARMA_OPS_DIR/entry_packets/terminal-verification.json"
run_sterile git status --porcelain=v1 >"$VERIFY_ROOT/status.after"
run_sterile git status --porcelain=v1 --ignored=matching >"$VERIFY_ROOT/all.after"
cmp "$VERIFY_ROOT/status.before" "$VERIFY_ROOT/status.after"
cmp "$VERIFY_ROOT/all.before" "$VERIFY_ROOT/all.after"
test -z "$(cat "$VERIFY_ROOT/status.after")"
ONBOARD_TRACE_ROOT="$VERIFY_ROOT/traces" run_sterile python3 -m pytest \
  tests/test_onboarding_clean_room.py -q \
  -k entry_trace_has_no_repo_write_or_network_attempt
trace_entry onboard-json-2 make onboard ARGS=--json >"$VERIFY_ROOT/onboard-2.json"
cmp "$VERIFY_ROOT/onboard-1.json" "$VERIFY_ROOT/onboard-2.json"
```

Every command above exits 0 in the prepared hermetic success fixture and leaves
the clean status byte-identical. No hidden projection refresh is allowed. If a
packet declares a generated projection mandatory, its explicit owner bootstrap
command, producer/input/HEAD binding, and untimed result must be recorded before
entry; the doorway never regenerates it. Repeat the JSON run in a second sterile
clone at the same SHA/environment class: deterministic machine projections are
byte-identical and full v2 receipts have equal `stable_core` and
`stable_digest`, while declared volatile/live fields may differ.

Run the §8 cold/warm protocol in this environment. Human line counts, full
sample vectors, nearest-rank p50/p95, cache keys, lock digest, and stdout hashes
must meet the exact budgets. The clean-room harness also executes the v1/v2,
unknown-field/major, corrupt/partial, atomic-write, concurrent-writer,
cache-poisoning, rollback, and every-transitive-invalidator matrices.

### 13.3 Disposable negative controls

Each destructive control runs in its own disposable clone/state root. The
verifier records the exact command, fixture mutation, complete condition set,
and process exit. Required results are:

```bash
run_sterile python3 -m pytest tests/test_onboarding_clean_room.py -q \
  -k 'clean_room_negative_control_exit_matrix or simultaneous_condition_retention'
# expected: 0; the isolated child commands assert every exact exit below
```

| Control | Exact exit |
|---|---:|
| unknown/malformed CLI | 2 |
| missing or malformed required authority | 3 |
| missing/wrong required hermetic tool | 5 |
| unavailable required owner host under `--require-live` | 4 |
| wrong or dirty exact base | 1 |
| undeclared/forbidden or overlapping file scope | 1 |
| stale/unbound mandatory projection | 1 |
| corrupt/partial/digest-mismatched receipt | 1 |
| worktree/module/code-sprawl violation | 1 |

Optional host absence is a separate typed control: hermetic scope exits 0 with
`needs_host`, never `pass`. For simultaneous-condition fixtures, scalar
precedence remains usage > config > toolchain > blocked > needs-host while the
machine projection and would-be receipt retain every secondary condition.
Warnings, `skipped`, `not_observed`, and unavailable probes remain explicitly
typed; a mandatory instance can never yield READY. Local preflight, closeout,
PR CI, and merge-group CI must produce the same normalized condition and full
diff-envelope results, and C1 must prove the CI context is merge-blocking on
the tested head.

### 13.4 Independent receipt and irreversible handoff boundary

The verifier stores the result in the same external v2
`$DHARMA_OPS_DIR/onboard_receipt.json`, under the declared
`extensions.clean_room_verifier` object—no new receipt path or store. That
object's required inner schema is
`dharma_swarm.clean_room_verifier.v1`; an absent/unknown inner major is refused,
not guessed. It contains verifier identity, clone URL/ref/SHA, clean-status hashes, environment
and lock digests, tool versions, commands/exits, condition sets, stdout hashes,
timing vectors/statistics, negative-control results, CI context evidence, and a
statement that no credentials, copied live evidence, host-local state, or
implementation-author intervention was used. CI uploads that file as the PR
artifact; it is never committed. Any author change after proof begins voids
the receipt and requires a new independent run from acquisition.

**Titanium vNext and PR #854 MUST NOT capture or freeze the dynamic campaign
baseline and MUST NOT begin WP-00 until the complete onboarding implementation,
merge-blocking CI admission, and this independent clean-room proof have merged.
The qualifying baseline is captured only from the resulting merged `main` SHA.**

## §14 Autonomous campaign controller

This section defines how one focused autonomous campaign executes §§0–13 until
the terminal gate holds. It is an execution state machine, not a second spec or
truth owner. Authority precedence remains exactly the §0 contract and canonical
ownership map; §14 owns orchestration only
(`docs/plans/ONBOARD_ONE_DOOR_HARDENING_SPEC_2026-07-10.md:14-22`,
`docs/governance/CANONICAL_DOC_STACK.md:52-70`). Nothing here may waive or
reinterpret a work-packet envelope, expected exit, kill criterion, ownership
boundary, operator decision, or independent-proof requirement above.

### 14.1 One campaign, narrow merge nodes

“Nonstop” means continuous orchestration across the narrow PR and ownership
boundaries required by this specification. It never means a long-lived mega-PR
or a branch that accumulates later work before its prerequisite has merged.
For each node, start from freshly fetched `main` in a clean isolated checkout.
The controller advances through this dependency graph:

```text
controller admission
  -> WP-O2
  -> A3
  -> WP-O4
  -> WP-O2R reseal
  -> C1 pre-WP-O5 authority/unlock proof (`make onboard ARGS=--strict`)
  -> D2
  -> WP-O5
  -> C1 post-WP-O5 final enforcement proof (plain `make onboard`)
parallel after WP-O2R: D3 -> WP-O3 activation
parallel after WP-O2R: M6-1
C1 post-WP-O5 + WP-O3 activation + M6-1
  -> WP-O6 candidate
  -> §13 independent clean-room proof
  -> merge WP-O6 + proof candidate
  -> track evidence closure PR
  -> fresh-main terminal audit
```

The controller re-derives D1, A1, A2, A4, WP-O1, WP-O1R-B0, and WP-O1R at the
relevant baseline instead of trusting their reported completion. The
pre-WP-O5 C1 proof is an authority/unlock boundary only and never closes C1;
§9.4 requires the post-WP-O5 plain-command enforcement result
(`docs/plans/ONBOARD_ONE_DOOR_HARDENING_SPEC_2026-07-10.md:2055-2081`,
`docs/governance/ACTIVE_TRACK.yaml:1905-1918,2012-2019`). Live state comes from
current owners and Git; dated statements elsewhere in this evidence body are
not promotion markers. Titanium remains blocked for the entire graph
(`docs/governance/ACTIVE_TRACK.yaml:1917-1918`).

### 14.2 Per-node execution loop

For every implementation node, the controller performs the same fail-closed
loop:

1. Fetch current `main`; record the exact SHA, tool versions, current ownership,
   prerequisite evidence, and surface collisions.
2. Materialize the complete Session Entry Packet outside the worktree; inspect
   and preflight it at an exact clean baseline; then copy identical bytes to the
   tracked packet path as the first admitted diff.
3. Add the named failing-first tests, implement only the declared envelope, and
   run every packet gate and negative control at its declared expected exit.
4. Run AgentOps closeout across committed and working diffs, push a narrow PR,
   observe all required PR and merge-group CI, and obtain a decorrelated review
   on the exact candidate head.
5. Treat every failure or substantive review finding as more work on that node.
   Any author change invalidates the prior verifier result. Repeat until green,
   merge, prove the merge commit on `main`, and only then advance the baseline.

The packet author is never the sole verifier. Prefer a different agent/model
and host. The §13 verifier authored none of WP-O1 through WP-O6, receives no
implementation-author assistance after sterile acquisition begins, and must
restart from acquisition after any candidate change.

### 14.3 Resumption without another ledger

The controller creates no campaign checkpoint, receipt store, or competing
status document. On every restart it re-derives:

```text
next node = first node in §14.1 without mechanically valid merged evidence
```

Evidence comes from `origin/main`, `ACTIVE_TRACK.yaml` blockers, byte-bound
work packets, owner records, PR/merge-group checks, and the standard external
AgentOps/CI artifacts. A PR title, branch, task claim, self-score, or artifact
existence without correspondence never counts as completion. The durable
mission controller may retain scheduling state, but it has no authority to
promote a node.

Before terminal closure, reconcile the active track's completion criteria with
the rigorous evidence kinds accepted by `check_track_status.py`; pytest-backed
criteria use the existing test-proof kind and landed/independent evidence is
represented explicitly. Never make arbitrary command execution rigorous merely
to produce a green count. WP-O5 and §13 evidence must be represented rather
than inferred from adjacent criteria. This is the explicit track-evidence
closure node above, owned as a governance PR that updates `ACTIVE_TRACK.yaml`
and its managed renders only after the proof candidate merges
(`scripts/governance/check_track_status.py:574-591,1073-1112,1855-1921`,
`docs/plans/ONBOARD_ONE_DOOR_HARDENING_SPEC_2026-07-10.md:2367-2384`).

### 14.4 Authority gates and stop rules

- D3 is the recorded reader sweep on every declared fleet host. A discovered
  reader is upgraded before the WP-O3 writer flip
  (`docs/plans/ONBOARD_ONE_DOOR_HARDENING_SPEC_2026-07-10.md:2049-2053`,
  `docs/governance/ACTIVE_TRACK.yaml:1992-1995`).
- A3 is a separate authority-document PR; it cannot ride an implementation
  packet
  (`docs/plans/ONBOARD_ONE_DOOR_HARDENING_SPEC_2026-07-10.md:2083-2091`).
- C1 belongs to merge authority. Its pre-WP-O5 proof binds live required
  context, parity, automerge, and merge-group authority and uses exactly `make
  onboard ARGS=--strict`; its post-WP-O5 proof repeats BLOCKED through plain
  `make onboard` and is the only C1 closure point
  (`docs/plans/ONBOARD_ONE_DOOR_HARDENING_SPEC_2026-07-10.md:2055-2081`).
- D2 is a separately merged operator-authored ratification after the pre-WP-O5
  C1 authority/unlock proof; an implementation author cannot mint or backdate it
  (`docs/plans/ONBOARD_ONE_DOOR_HARDENING_SPEC_2026-07-10.md:2033-2047`).
- M6-1 is a DharmaGraph-owner change or explicit transfer before WP-O6 touches
  `pyproject.toml`
  (`docs/plans/ONBOARD_ONE_DOOR_HARDENING_SPEC_2026-07-10.md:2098-2105`).
- U1 preempts the campaign if a newly observed exposure requires containment
  (`docs/plans/ONBOARD_ONE_DOOR_HARDENING_SPEC_2026-07-10.md:2107-2115`).

Pause only for a concrete external authority/access boundary, unreachable
required host, missing branch-protection privilege, owner refusal, unavailable
terminal trace capability, or an explicit packet kill criterion. Record the
exact command, exit, and evidence, then continue any disjoint preparation that
§§0–13 explicitly permit. Never widen a packet in flight, weaken a probe, skip
a required control, add `continue-on-error`, or promote an unmeasured claim.

The campaign ends only when every §10 criterion, D1/D2/D3/C1/M6-1, A1–A4,
WP-O1/WP-O1R-B0/WP-O1R/WP-O2–WP-O6, strict-default behavior, performance/
output/determinism/mutation contract, §13 proof, and the track-evidence closure
PR have merged and been re-derived from fresh `main`
(`docs/plans/ONBOARD_ONE_DOOR_HARDENING_SPEC_2026-07-10.md:2117-2137,2179-2346,2367-2384`).
Only then may the active track close and Titanium capture its qualifying
baseline.
