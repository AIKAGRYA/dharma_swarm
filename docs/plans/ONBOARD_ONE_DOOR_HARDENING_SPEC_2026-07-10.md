# One-Door Onboarding Hardening — Execution Specification (2026-07-10)

**Role:** `working_plan` — a buildable hardening specification for the existing
`make onboard` entrypoint, written for a zero-context agent. It creates no new
truth store and no new governance authority; every artifact it touches already
exists or repairs an already-registered custody defect.

**Trust rule:** if this file disagrees with `make onboard`, `ACTIVE_TRACK.yaml`,
a receipt, or the code, trust those and re-verify — this repo moves ~60
commits/week. Every evidence claim below carries a `file:line` citation or a
dated measurement; anything uncited is design, not fact.

**Status:** proposed. Strict-by-default behavior approved in principle by the
operator; the actual flip is a deliberate operator promotion (see §6 WP-O5),
mirroring the `hygiene/promote.py` advisory→enforced doctrine — never
auto-escalated from inside the gate.

**Companion evidence:** two adversarial audits of the onboarding machinery and
of the reusable governance conventions, performed 2026-07-10 against
`212df1a8c2` (this branch's HEAD, even with `origin/main`).

---

## §0 How to use this spec

- Each work packet (§6) is independently shippable, carries its own allowed
  files, acceptance criteria, and a kill criterion. Ship them in order; do not
  batch WP-O5 (the strictness flip) into any other packet.
- The §1 baseline is a dated observation set, not permanent truth. Before
  building a packet, re-verify the specific lines it cites.
- The §10 track skeleton is `status: PROPOSED` until the operator ratifies
  admission (or folds the work under an existing track — a one-line change
  either way).

## §1 Measured current state (honest baseline)

### 1.1 Measurements (2026-07-10, this host, HEAD `212df1a8c2`)

| Measure | Value |
|---|---:|
| `make onboard` wall time, run 1 | 32.0 s |
| `make onboard` wall time, run 2 (immediately after) | 31.4 s |
| Output lines | 327 |
| Warm/cold distinction | **none exists** — both runs pay full render cost |
| Receipt written | `~/.dharma/ops/onboard_receipt.json`, schema `dharma_swarm.onboard_receipt.v1`, `authority: projection_only`, atomic tmp+replace, every run |
| `agent_onboard.py` | 1883 lines |
| `orientation_graph.py` | 1149 lines |

The only cache today is the 60-minute evidence-freshness TTL
(`EVIDENCE_STALE_MINUTES = 60`, `agent_onboard.py:69`) which gates whether
`check_track_status.py --warn-only` is re-invoked — the ~31 s render cost
itself is paid on every run.

### 1.2 Claims adjudication — the draft spec's evidence section, verified

Anti-slop discipline: the prior draft's claims were adversarially checked
before being built upon. Verdicts:

| Draft claim | Verdict | Ground truth |
|---|---|---|
| `agent_onboard.py` ≈ 1,800 lines | CONFIRMED (1883) | `agent_onboard.py:1883` |
| normal mode renders ~486 lines | CORRECTED | 327 lines measured here; output varies with repo state — either way, 5–8× over a readable budget |
| cold refresh took >20 s | CORRECTED | 31–32 s measured, **and there is no warm path at all** |
| refreshes evidence via `check_track_status.py --warn-only` | CONFIRMED | `agent_onboard.py:1636`, `timeout=30` |
| refresh timeout and `OSError` swallowed | CONFIRMED | `agent_onboard.py:1638` — silent `pass` |
| stale state does not change exit code | CONFIRMED **by design and by test** | docstring `agent_onboard.py:29` "Exit code: always 0 on stale state"; enforced by `tests/test_agent_onboard.py:44-53` (`test_onboard_exits_zero_in_repo`) |
| it may make network calls | SHARPENED | exactly one: `gh pr list ...` (`agent_onboard.py:1373-1377`), **on by default**, skipped only under `--fast`/`--no-net` (`:1731`) |
| it writes a local receipt and may trigger evidence refresh | CONFIRMED + EXTENDED | receipt every run (`:1695-1710`); refresh writes gitignored derived files (`reports/governance/active_track_evidence.json`, `track_portfolio.json` — `.gitignore:136,138`); **and** `make orient --write-context` writes two **tracked** files (`reports/orientation/repo_context.{json,md}`, both in `git ls-files`) |
| `verifier-selfcheck` does not execute `test-fast` | CONFIRMED | `Makefile:158-169` — syntax, F821, pytest **collection only**, then onboard door; gate [4/4] uses `&& echo`, so a failing onboard would not fail the target |
| tests explicitly require onboarding to exit zero on stale state | CONFIRMED | `tests/test_agent_onboard.py:41-53` |
| `orientation_graph.py` always exits zero in normal modes | CONFIRMED | exit 1 only on `--query` miss (`:1127-1129`); argparse exit 2 on unknown flag |
| orientation reports root `AGENTS.md` missing | CONFIRMED | `AGENTS.md` absent on disk yet **registered canon** in `docs/docops/assertions.yaml` (`canonical_guard.registered:162`, `path_guards.include:100`) — an existing custody defect, so creating it is a repair, not a new surface |
| parser classifies fixed BRs as open because it misses `**FIXED ...**` | CORRECTED — latent, not live | `orientation_graph.build_broken` (`:643-662`) would miss a bold status value and only terminates at the literal `## CLOSED` heading (`## STALE-CLAIM CORRECTIONS` at `BROKEN_REGISTER.md:231` does not terminate the scan). Today's register uses the plain `- **status:** OPEN` form, so **no live false positive exists** — the defect is real but latent, and only in this one parser |
| cloud-host absence appears as RED/missing agent state | CORRECTED | neither script emits `RED` or `NEEDS_HOST` at all; census `status` strings are forwarded verbatim (`orientation_graph.py:608-636,1019-1024`). The typed host vocabulary exists elsewhere in the repo (§2.4) and is simply not adopted here |

### 1.3 Structural findings the draft missed

1. **Three divergent broken-register parsers**, not two:
   `orientation_graph.build_broken` (`:643`, fragile),
   `agent_onboard._parse_broken_register` (`:783`, strips leading markup —
   handles bold statuses), and
   `trust_gate_status.parse_broken_counts` (`:247-265`, docstring: "same parse
   as agent_onboard.py"). One canonical parser must absorb all three.
2. **The proposed exit-code table collided with two existing repo contracts.**
   `agent_onboard.py:1726-1729` already documents exit **2 = unknown CLI flag**
   (argparse default, kept deliberately: "silently proceeding on a typo'd flag
   would mask broken automation"), and `pramana_probe.py:29-33,377-383` owns
   exit **3 = CONFIG ERROR** ("a phantom gate is a config error, not a
   verdict"). §2.3 realigns the contract to respect both.
3. **`agent-build-preflight` runs onboarding twice**: the target depends on
   `verifier-selfcheck onboard hygiene-check` (`Makefile:422`) and
   `verifier-selfcheck` itself invokes `make onboard` as gate [4/4]
   (`Makefile:167-168`). ~60 s of duplicated render per preflight.
4. **Three doors already exist**: `make onboard` (session admission),
   `make orient` (whole-system projection), and `make agent-onboard`
   (`a2a_agent_onboard.py`, `Makefile:451-452`) — the latter is fleet-IDENTITY
   join for a new persistent A2A agent and is **out of scope**; this spec must
   not blur it into the session door.
5. **No source hashing exists today.** Nothing computes `sha256(CLAUDE.md)` or
   any canonical-doc digest; `docs/governance/CANONICAL_DOC_STACK.md` (the doc
   ownership map, 182 lines) names the "max 5 first-read surfaces" but nothing
   fingerprints them. The required-reading digest lane (§4) is a genuine gap
   fill.
6. **Network default is ON.** `net = not (fast or no_net)`
   (`agent_onboard.py:1731`). The hardened door inverts this: no network by
   default, `--net` opts in.

## §2 Design decision — one strict door

`make onboard` becomes the only public onboarding and admission door. It:

1. validates the behavioral contract (canonical rule files exist, parse, and
   hash);
2. validates repository state (branch/HEAD readable, no merge conflict, no
   unexpected pre-existing dirt);
3. resolves active-track ownership for the declared/touched scope;
4. validates cached evidence against owner content hashes;
5. runs bounded admission sentinels (each with an explicit timeout; a sentinel
   that cannot run is a typed failure, never a silent pass);
6. builds a compressed orientation projection;
7. computes the delta from the previous onboarding receipt;
8. prints `READY`, `BLOCKED`, `NEEDS_HOST`, `CONFIG_ERROR`, or
   `TOOLCHAIN_MISSING` — diagnosis always rendered before any nonzero exit;
9. writes the existing receipt (same path, schema bumped to v2) outside the
   repository; and
10. returns a meaningful exit code (§2.3).

### 2.1 Command modes

| Command | Purpose | Network | Tracked-file writes | Expected use |
|---|---|---:|---:|---|
| `make onboard` | strict compact admission | No | No | every session |
| `make onboard ARGS=--json` | machine packet (deterministic) | No | No | agent harness |
| `make onboard ARGS=--deep` | full orientation detail (today's 327-line render lives here) | No | No | investigation |
| `make onboard ARGS="--deep --net"` | + open-PR context via `gh` | Yes | No | explicit request |
| `make onboard ARGS=--require-live` | live daemon-host admission | No | No | daemon-host work |
| `make onboard ARGS=--write-context` | legacy orientation artifacts | No | `reports/orientation/repo_context.{json,md}` only | legacy consumers |

`make orient` remains as a compatibility alias for
`make onboard ARGS="--deep --write-context"`. `make agent-onboard` (A2A
identity join) is untouched and stays a separate door with a separate purpose.

Legacy flags: `--fast` maps to the new default (compact, no net, no refresh)
with a one-line deprecation notice; `--no-net` becomes a no-op with the same
notice. Unknown flags keep the existing argparse exit-2 contract.

**Behavior change ledger** (each is deliberate and test-pinned):
network default flips ON→OFF; evidence-refresh failure flips
silently-swallowed→verdict-affecting; stale mandatory evidence flips
warn→block (after WP-O5); duplicate render in preflight is removed.

### 2.2 Writes doctrine (refined from the draft's "no repo writes")

- Default path writes **no tracked repository files**. Ever.
- The evidence refresh (`check_track_status.py --warn-only`) writes only
  gitignored derived artifacts (`.gitignore:136,138`); that is permitted on
  the default path, but its **outcome is no longer swallowed**: a refresh
  timeout/`OSError` becomes a typed warning, and stale *mandatory* evidence
  flips the verdict (post-WP-O5) instead of rendering a ⚠ that exits 0.
- `--write-context` is the only mode that writes tracked files, and only the
  two legacy orientation artifacts.
- The receipt (`~/.dharma/ops/onboard_receipt.json`) stays outside the repo,
  atomic tmp+replace, exactly as today (`agent_onboard.py:1695-1710`).

### 2.3 Exit-code contract (realigned to existing repo conventions)

| Exit | Verdict | Meaning | Precedent honored |
|---:|---|---|---|
| 0 | `READY` (or `NEEDS_HOST` without `--require-live`) | all checks required for the selected scope passed; host gaps listed, non-blocking | `loop5b_world_radar_closure_run.py:257-259` — "missing operator state is not a failure", exit 0 |
| 1 | `BLOCKED` | ownership conflict, conflicted/dirty base, failed admission sentinel, stale mandatory evidence, schema violation | `pramana_probe.py` exit 1 = gate failed; `tam_ledger.py --check` exit 1 = finding |
| 2 | usage error | unknown/malformed CLI flags (argparse) | already documented+tested in `agent_onboard.py:1726-1729` |
| 3 | `CONFIG_ERROR` | malformed/contradictory canonical config: missing `AGENTS.md`/`CLAUDE.md`, unparseable `ACTIVE_TRACK.yaml`, phantom sentinel target | `pramana_probe.py:377-383` — exit 3, "no verdict exists" |
| 4 | `NEEDS_HOST` | `--require-live` requested and required daemon/VPS state is unavailable | new code, reusing the `needs_host` token vocabulary (§2.4) |
| 5 | `TOOLCHAIN_MISSING` | required hermetic toolchain absent or wrong version | new code |

The draft's table (2=BLOCKED_REPO, 3=NEEDS_HOST, 4=CONFIG_ERROR) is
superseded: it would have made a typo'd flag indistinguishable from a blocked
repo and put CONFIG_ERROR on a different number than the sibling gate the
operator already knows. Precedence when multiple apply:
usage(2) > CONFIG_ERROR(3) > TOOLCHAIN_MISSING(5) > BLOCKED(1) > NEEDS_HOST(4).
The command always renders its diagnosis before returning nonzero.

### 2.4 Host-scope typing (adopt, don't invent)

Reuse the existing three-layer vocabulary end to end:

- token `needs_host` at the capability seam — as
  `world_radar/go_invoke.py:30-56` does for the Go toolchain (empty argv +
  structured `{"source","stage","error"}`, never an exception into the
  caller);
- verdict `NEEDS_HOST` + exit-0-unless-required at the run level — as
  `loop5b_world_radar_closure_run.py:59-71,257-259` does;
- a cockpit-style gap code per gap (`onboard_needs_runtime_db`,
  `onboard_needs_daemon_census`, `onboard_needs_provider_keys`,
  `onboard_needs_nats`, `onboard_needs_deploy_receipt`) with a `next_action`
  string — as `control_surface_go.py:159-197` does with
  `go_world_radar_needs_host`.

Host gaps are **task-relevant** only: runtime-DB absence blocks runtime-state
work under `--require-live`, never hermetic work. Host absence is never
rendered as RED production failure on a non-owner host; an **actually
executed** live failure stays red. Unmeasured never renders green
(RED-if-unmeasured doctrine, `trust_gate_status.py:19-20`).

### 2.5 Output contract

Compact human output: 40–70 lines, hard-capped by a rendering budget test.

~~~text
DHARMA ONBOARD — READY

Repo:    claude/example @ abc123, clean, ahead 0 / behind 0
Scope:   hermetic
Track:   onboard-one-door-2026-07 (serves: substrate-nativeness)
Owns:    Makefile, scripts/governance/onboarding/**, AGENTS.md
Blocked: none
Host:    2 gaps (runtime_db, daemon_census) — non-blocking, see --deep

Changed since previous onboard (receipt delta):
  + sentinel added: docops-custody
  - blocker resolved: stale track evidence
  ! rule digest changed: CLAUDE.md

Required reading (content-addressed):
  1. CLAUDE.md                            sha256:ab12…
  2. AGENTS.md                            sha256:cd34…
  3. docs/governance/BUILD_SESSION_ENTRYPOINT.md   sha256:…
  4. docs/governance/ACTIVE_TRACK.yaml    sha256:…
  5. <track-relevant SKILL.md, if any>    sha256:…

Startup readback required before editing (template in receipt):
  branch / SHA / worktree / verdict / track / allowed / forbidden /
  blockers / non-goals / mismatches / tests / host gaps / rollback

Next: make agent-build-preflight   ·   close: make agent-build-closeout
~~~

The current 327-line render is preserved verbatim under `--deep` during
migration (§9), then compressed section-by-section. Detail beyond the compact
view lives in the JSON receipt and `--deep`, never in the default render.

## §3 Machine packet, digest, cache, delta

### 3.1 One receipt, schema v2

Continue writing the existing path — `~/.dharma/ops/onboard_receipt.json`
(`DHARMA_OPS_DIR` override honored). No second ledger, no new receipt
directory. Schema bumps `dharma_swarm.onboard_receipt.v1` →
`dharma_swarm.onboard_receipt.v2`; the writer rejects nothing, but any
**reader** of the receipt (fleet consumers, the delta engine) must accept v1
and v2 and refuse unknown *future* majors explicitly.

Digest/time primitives are **imported**, never redefined:
`stable_digest`, `canonical_json`, `utc_now` from
`dharma_swarm/memory_kernel/write_receipts.py:336-346` — the same primitives
`tam_ledger.py:48-51` and `arena_truth_report.py:49` already import.
(`frontier_ledger.py:70-79` locally redefined them; that divergence is the
cautionary example, not the pattern.)

Volatile-field doctrine follows `tam_ledger.py:63`:
`_VOLATILE_KEYS = ("observed_at", "stable_digest")` are excluded from the
replay/delta comparison but the digest covers every stable field.

Required v2 shape (v1 fields are a strict subset carried forward —
`repo`, `work_lanes`, `portfolio`, `next_items`, `swarm_bulletins`,
`broken_register`, `open_prs`, `runtime_truth_packets` all survive):

~~~json
{
  "schema": "dharma_swarm.onboard_receipt.v2",
  "observed_at": "ISO-8601Z",
  "authority": "projection_only",
  "verdict": "READY|BLOCKED|NEEDS_HOST|CONFIG_ERROR|TOOLCHAIN_MISSING",
  "exit_code": 0,
  "scope": "hermetic|live",
  "repo": { "worktree": "", "branch": "", "head": "", "ahead": "", "behind": "",
            "dirty_files": 0, "dirty_top_dirs": {}, "conflicted": false },
  "contract": { "required_files": [], "source_hashes": {}, "contract_digest": "" },
  "portfolio": { "summary": "", "spine_coverage": null, "evidence_age_minutes": null,
                 "tracks": [], "selected_track": "", "ownership_conflicts": [] },
  "readiness": { "checks": [], "blockers": [], "warnings": [], "host_gaps": [] },
  "orientation": { "identity": {}, "broken_open": [], "liveness": {},
                   "spine": {}, "toolchain": {} },
  "required_reading": [ { "path": "CLAUDE.md", "sha256": "" } ],
  "startup_readback_template": {},
  "delta": { "previous_digest": "", "added": [], "resolved": [], "changed": [] },
  "next_items": [], "swarm_bulletins": [], "broken_register": {},
  "open_prs": [], "runtime_truth_packets": [], "work_lanes": {},
  "stable_digest": ""
}
~~~

Each entry in `readiness.checks` is typed:
`{id, status: "pass|fail|warn|needs_host|skipped", detail, gap_code?, next_action?}`.
`skipped` must carry a reason; a check that could not run is never counted as
`pass` (the pramana phantom-gate lesson).

### 3.2 Cache design — the receipt IS the warm cache

Cache validity key:

~~~text
stable_digest({
  "schema": "dharma_swarm.onboard_cache_key.v1",
  "head": <HEAD sha>,
  "owners": { path: sha256 for CLAUDE.md, AGENTS.md,
              docs/governance/ACTIVE_TRACK.yaml,
              docs/governance/CANONICAL_DOC_STACK.md,
              docs/governance/BUILD_SESSION_ENTRYPOINT.md,
              Makefile, docs/state/BROKEN_REGISTER.md,
              docs/docops/assertions.yaml,
              <track-relevant skill files> },
  "impl": sha256 of scripts/governance/onboarding/** sources
})
~~~

**Warm path** (key matches previous receipt): reuse parsed contracts,
portfolio graph, and static orientation sections; **always rerun** the cheap
live checks — git branch/HEAD/dirty/conflict, toolchain presence, bounded
sentinels — then compute delta and render. Target < 1 s.

**Cold path** (any owner hash changed): reparse only affected owners, rebuild
only affected orientation sections, replace the receipt after packet
validation. Target < 5 s. (Baseline being replaced: 31–32 s with no warm path
at all — §1.1.)

Constraints (each is a named test in WP-O3):

- no cached result may override a current hard failure;
- malformed/corrupt cache is ignored and regenerated, never trusted;
- a stale cache can never yield `READY`;
- cache writes are atomic (`tmp` + `replace`, as today);
- cache failure never modifies repository files;
- timestamps never invalidate stable content (`_VOLATILE_KEYS`);
- network results are never part of default cache validity.

The 31 s baseline is dominated by unconditional deep rendering and subprocess
fan-out (`spine_bypass_report --json`, drift triage, worktree budget, spine
imports). The warm path avoids re-rendering deep sections; the compact default
never runs them.

### 3.3 Delta — coherence compounding without context growth

Each run compares the new stable packet against the immediately previous
receipt (only one prior receipt is ever needed; historical truth stays with
its owners). The compact delta reports: new/resolved blockers, changed rule
digests, changed active track/ownership, changed required reading, changed
toolchain, changed host requirements, changed verification command. Delta
computation uses the stable digest minus `_VOLATILE_KEYS` — the same replay
comparison discipline as `tam_ledger.check()` (`tam_ledger.py:324-377`).

## §4 Rule-study enforcement

No command proves cognitive understanding; the design therefore pairs machine
evidence (content-addressed required reading) with an agent readback, and
leaves CI as the final independent layer.

### 4.1 Root `AGENTS.md` — a custody repair

`AGENTS.md` is already registered canon (`docs/docops/assertions.yaml`
`canonical_guard.registered:162`) and absent on disk; DocOps custody and
`make orient` both report it MISSING today. Create it as a short pointer:

~~~markdown
# Agent entrypoint

Run `make onboard` before non-trivial work.
The canonical behavioral contract is `CLAUDE.md` — this file must never
duplicate it.
Return the startup readback printed by onboarding before editing.
~~~

A contract test rejects content duplication (any paragraph of `CLAUDE.md`
appearing in `AGENTS.md` fails).

### 4.2 Required reading digests

The receipt carries `required_reading[]` with per-file sha256 — the first
content-addressing of the canonical doc stack (§1.3 finding 5). The list is
derived from `CANONICAL_DOC_STACK.md`'s "max 5 first-read surfaces" plus the
track-relevant skill file; it is rendered with digests so a session can prove
*which version* of the rules it onboarded against, and the delta engine can
say "rule digest changed" instead of hoping someone re-reads.

### 4.3 Startup readback

Before editing, the agent returns the readback (template emitted in the
receipt and printed by the compact render):

~~~yaml
startup_readback:
  branch: ""            # from receipt.repo
  head: ""
  worktree: "clean|dirty|conflicted"
  verdict: "READY|BLOCKED|NEEDS_HOST"
  track: ""
  serves: ""
  allowed_files: []     # from the selected track's owned_surfaces + WP allowlist
  forbidden_files: []   # sibling-track owned surfaces
  blockers: []
  non_goals: []
  adjacent_mismatches: []   # INTERFACE_MISMATCH_MAP entries touching the scope
  required_tests: []
  host_gaps: []
  rollback: ""
  rule_digest: ""       # receipt.contract.contract_digest
~~~

Enforcement is staged, per the pudgala/AI-M1 machinery: advisory first
(readback presence is a rendered reminder), promotable to enforced through
`scripts/governance/hygiene/promote.py` by the operator — never
auto-escalated from inside the gate (`check_claim_evidence_binding.py:12-17`
doctrine). CI verifies behavior and scope; it does not trust the readback
alone.

## §5 Architecture

`scripts/governance/agent_onboard.py` (1883 lines) and
`orientation_graph.py` (1149 lines) both exceed the 500-line ceiling and
duplicate parsing. Decompose into one typed package; both legacy scripts
become thin compatibility shims over it.

~~~text
scripts/governance/onboarding/
├── __init__.py
├── models.py            # typed packet/check/delta models, schema version, _VOLATILE_KEYS
├── contract.py          # required rule files, sha256 hashing, canonical pointers
├── repo_state.py        # branch, HEAD, dirty/conflict, ahead/behind
├── portfolio.py         # active tracks, ownership, WIP, scope resolution
├── broken_register.py   # THE one canonical BR parser (absorbs all three)
├── orientation.py       # compressed deep projection over existing owners
├── toolchain.py         # pinned tool presence/version readiness
├── readiness.py         # verdict + exit-code decision (the mutation target)
├── cache.py             # receipt-backed cache key + atomic persistence
├── delta.py             # previous/current stable-packet comparison
├── render.py            # compact human + deterministic JSON output
└── cli.py               # argument parsing and orchestration
~~~

Rules: every module < 500 lines; digest/time imported from
`memory_kernel/write_receipts` (§3.1); `broken_register.py` is imported by
`trust_gate_status.parse_broken_counts`, `agent_onboard`, and
`orientation_graph` — parity-tested against all three before any old parser
is deleted; `orientation_graph.py` keeps its CLI surface but delegates to
`onboarding/orientation.py` (no second parser, no second packet model).
New modules carry spine headers where the guard requires them.

## §6 Work packets

### WP-O1 — Universal contract and packet schema

**Allowed files:** `AGENTS.md`, `docs/docops/assertions.yaml` (only if the
registration needs adjustment), `scripts/governance/onboarding/{__init__,models,contract}.py`,
`tests/test_onboarding_contract.py`.

**Behavior:** root `AGENTS.md` exists as the §4.1 pointer and DocOps custody
goes green on it; required-reading hashes generate; packet v2 validates;
stable digest excludes volatile keys; missing canonical contract →
`CONFIG_ERROR` (exit 3).

**Tests:** missing `AGENTS.md` → 3; duplicated rule content rejected; changed
`CLAUDE.md` changes `contract_digest`; timestamp does not change
`stable_digest`; malformed packet rejected; v1-receipt readers still parse.

**Acceptance:** `make docops-integrity` green including `AGENTS.md`;
`pytest tests/test_onboarding_contract.py -q` green.
**Kill criterion:** if DocOps custody cannot recognize `AGENTS.md` without
weakening `check_canonical_guard`, stop — repair the guard first, separately.

### WP-O2 — One parser, typed host scope

**Allowed files:** `scripts/governance/onboarding/{broken_register,orientation}.py`,
`scripts/governance/orientation_graph.py`, `scripts/governance/agent_onboard.py`
(delegation seam only), `scripts/governance/trust_gate_status.py`
(delegation seam only), matching tests.

**Behavior:** one canonical BR parser absorbs the three divergent ones; bold
`**FIXED 2026-xx-xx**` values parse; status expressed in the H3 heading
parses; both `## CLOSED ITEMS` and `## STALE-CLAIM CORRECTIONS` terminate the
open scan; open-like/closed-like buckets stay
`{OPEN, PARTIAL, INVESTIGATING, WORKAROUND}` / `{FIXED, CLOSED}`
(`trust_gate_status.py:243-244`). Host-local absence renders as typed
`needs_host` checks with gap codes (§2.4); an executed live failure stays red;
a cloud seat never claims all persistent agents failed.

**Tests:** plain/bold/heading statuses; `PARTIAL`; `WORKAROUND`; malformed
status; section termination; parity fixtures asserting identical counts from
all three legacy call sites; no-runtime-DB / stale-runtime-DB / non-owner-host
/ owner-host-with-stale-evidence scenarios.

**Acceptance:** parity suite green; legacy parsers deleted (not shimmed) in
the same PR their parity proof lands.
**Kill criterion:** if any consumer needs semantics the canonical parser can't
express, extend the parser — never fork it.

### WP-O3 — Unified CLI, readiness, cache, delta, render

**Allowed files:** `scripts/governance/onboarding/{cli,readiness,cache,delta,render,repo_state,portfolio,toolchain}.py`,
`scripts/governance/agent_onboard.py` (shim), matching tests.

**Behavior:** §2.1 modes; §2.3 exit codes behind `--strict` /
`DHARMA_ONBOARD_STRICT=1` (default behavior unchanged in this packet);
network off by default, `--net` opts in; §2.2 writes doctrine; receipt-backed
warm cache with §3.2 constraints; deterministic JSON (two runs on identical
state differ only in `_VOLATILE_KEYS`); startup readback template; delta vs
previous receipt; refresh timeout/`OSError` becomes a typed warning instead of
a silent `pass`.

**Tests:** every verdict; warm hit; owner-hash invalidation; corrupt cache;
no-network assertion (socket guard on default path); no-tracked-write
assertion (`git status --porcelain` unchanged); determinism; each §3.2
constraint by name.

**Acceptance:** `make onboard` behavior byte-identical for existing consumers
while `--strict` is off; strict mode fully green in tests.
**Kill criterion:** if warm path cannot hit < 1 s without skipping a live
check (git/toolchain/sentinels), keep the live checks and miss the target —
correctness beats the budget; record the measured number.

### WP-O4 — Makefile integration and compatibility

**Allowed files:** `Makefile`, `scripts/governance/orientation_graph.py`
(alias layer), make-contract tests.

**Behavior:** `make onboard` is the sole public session door; `make orient`
delegates to `onboard --deep --write-context`; `agent-build-preflight`
consumes strict readiness **once** (kills the double render — §1.3 finding 3);
`verifier-selfcheck` gate [4/4] propagates a nonzero onboard instead of
`&& echo`-swallowing it; `agent-build-closeout` remains the handoff gate;
`make agent-onboard` untouched; legacy flags get deprecation lines; unknown
flags exit 2.

**Tests:** target equivalence; orient compatibility; strict exit propagation
through make; single packet generation per preflight; unknown flag; deep /
write-context compatibility.

**Kill criterion:** if any CI job depends on today's `orient` output paths,
keep writing both artifacts byte-compatibly; never break a consumer to win
the alias.

### WP-O5 — The strictness flip (isolated, operator-gated)

**Allowed files:** `scripts/governance/onboarding/readiness.py` (default
flip), `tests/test_agent_onboard.py`, `Makefile` (if the flag plumbs through),
`docs/governance/BUILD_SESSION_ENTRYPOINT.md` (one-line behavior note).

**Behavior:** strict verdicts become the default; `--no-strict` remains for
one deprecation cycle. This packet — and only this packet — updates
`test_onboard_exits_zero_in_repo` and the `:29` docstring contract, because
they currently pin the opposite behavior **on purpose**
(`tests/test_agent_onboard.py:41-53`). The flip commit is small enough to read
in one screen and reverts atomically.

**Acceptance:** operator ratification recorded (the same deliberate-promotion
doctrine as `hygiene/promote.py` — the gate never flips itself); full suite
green with the updated contract tests.
**Kill criterion:** any unexplained CI red after the flip → revert the whole
packet (one revert), not partial patches; a rollback reopens this spec's
hardening finding rather than silently restoring always-zero.

### WP-O6 — Performance and mutation hardening

**Allowed files:** performance/property tests, `pyproject.toml`
(`[tool.mutmut]` scope widening only), onboarding modules only where a
measured issue is found.

**Behavior:** warm < 1 s, cold < 5 s, measured as median and p95 over ≥5 runs
with a timing receipt (reuse the `--measure` receipt pattern —
`orientation_graph.py:481-518` already writes
`~/.dharma/ops/orientation_timing_receipt.json`); compact output within the
40–70 line budget; widen the **existing** mutmut gate
(`pyproject.toml:79-99`, currently scoped to `dharma_swarm/spine/receipt.py`)
to include `scripts/governance/onboarding/readiness.py`; hypothesis
properties live in `tests/properties/` beside
`test_canonical_replay_properties.py`.

**Required mutants killed:** stale-evidence→READY; failed-sentinel→READY;
NEEDS_HOST→pass under `--require-live`; skipped-check counted as pass;
cache-hit overriding a live failure.

**Kill criterion:** no performance target is ever met by removing a required
validation; if the two conflict, the target loses and the receipt records the
number.

## §7 Negative controls

- Remove `AGENTS.md` → exit 3, verdict `CONFIG_ERROR`.
- Corrupt `ACTIVE_TRACK.yaml` → exit 3.
- Create an `owned_surfaces` overlap → exit 1 (strict), warning (pre-flip).
- Change any required rule file → cache key changes, cold path taken.
- Mark stale evidence fresh in a fixture → property test fails.
- Force `readiness.py` to return READY with a failed sentinel → mutant killed.
- Convert a `needs_host` check to `pass` → mutant killed.
- Add a network call to the default path → socket-guard test fails.
- Write a tracked file on the default path → porcelain test fails.
- Reintroduce a bold-`**FIXED**` BR as open → parser test fails.
- Feed a v3 receipt to the delta engine → typed refusal, not a crash.

## §8 Performance targets

| Path | Target | Baseline |
|---|---:|---:|
| Warm `make onboard` | < 1 s | n/a (no warm path exists) |
| Cold `make onboard` | < 5 s | 31–32 s |
| Compact output | 40–70 lines | 327 lines |
| Default network calls | 0 | 1 (`gh pr list`, on by default) |
| Default tracked-file writes | 0 | 0 (already true — keep it pinned by test) |
| Canonical reads on warm hit | changed owners only | all owners, every run |

## §9 Migration and compatibility

1. WP-O1/O2 land behind the existing scripts — zero behavior change.
2. WP-O3 lands strict mode behind `--strict`; default output stays available
   via `--deep` verbatim during migration.
3. WP-O4 switches `make onboard` to the compact render (still exit-0 default)
   and aliases `orient`.
4. WP-O5 flips strict-by-default in one atomic, operator-ratified commit that
   also updates the exit-0 contract tests.
5. Receipt path stays stable; schema bumps to v2; readers accept v1+v2 and
   refuse unknown future majors.
6. Duplicate BR/orientation parsers are deleted only after their parity tests
   pass (WP-O2), never left as divergent shims (the two-parser drift is how
   the latent `**FIXED**` defect survived).

Rollback: revert Makefile aliases and CLI defaults together; the receipt path
never moves; cache files are safe to delete (canonical state unaffected);
root `AGENTS.md` remains even on rollback because it closes a pre-existing
custody defect; a rollback that restores always-zero reopens this spec's
finding — it does not close it.

## §10 Dovetail with the active portfolio

The onboarding surfaces (`Makefile`, `scripts/governance/agent_onboard.py`,
`scripts/governance/orientation_graph.py`, root `AGENTS.md`) are owned by
**no active track** (verified across all nine tracks' `owned_surfaces`
2026-07-10; the only historical owner, `orientation-graph-2026-06`, is
SHIPPED/closed). Admission creates no overlap conflict — but the portfolio
sits at 9 active tracks with `warn_active: 8` already exceeded and
`max_active: 10` (`ACTIVE_TRACK.yaml:77-85`).

**Operator decision D1 (required before build):** admit the skeleton below as
the 10th track (at the hard WIP ceiling), or fold this work under
`sovereign-safety-tcb-2026-07` (it is admission/gate machinery and fits that
track's "add gate sources, never weaken a check" doctrine) — a one-line
change either way.

**Operator decision D2 (required before WP-O5):** ratify the strict-by-default
flip explicitly; §6 WP-O5 will not ship on "approved in principle".

Proposed skeleton (`status: PROPOSED`):

~~~yaml
- id: onboard-one-door-2026-07
  name: One-door onboarding — strict, fast, deterministic session admission
  status: PROPOSED
  serves: substrate-nativeness
  owner: "@AmitabhainArunachala"
  complements: [sovereign-safety-tcb-2026-07, merge-master-mike-d4-2026-06]
  owned_surfaces:
    - AGENTS.md
    - Makefile
    - scripts/governance/onboarding/**
    - scripts/governance/agent_onboard.py
    - scripts/governance/orientation_graph.py
    - tests/test_agent_onboard.py
    - tests/test_orientation_graph.py
    - tests/test_onboarding_*.py
  moves_vital_signs: [quality_gates, context_efficiency]
  completion_criteria:   # rigorous-only; existence checks are not closure
    - kind: command_passes
      command: ["python3", "-m", "pytest", "tests/test_onboarding_contract.py",
                "tests/test_onboarding_readiness.py", "-q"]
    - kind: command_passes
      command: ["make", "onboard"]
    - kind: receipt_valid
      file: ~/.dharma/ops/onboard_receipt.json
      requires_keys: [schema, verdict, exit_code, contract, readiness,
                      required_reading, delta, stable_digest]
  non_goals:
    - Do not weaken any gate, ratchet, or DocOps custody check to make onboarding green.
    - Do not create a second receipt store, orientation parser, or packet model.
    - Do not fold `make agent-onboard` (A2A identity join) into the session door.
    - Do not flip strict-by-default without explicit operator ratification (D2).
    - Do not meet a performance target by removing a required validation.
    - Do not touch sibling-track owned surfaces except through their own next-items.
~~~

## §11 Completion criteria

1. `make onboard` is the only command a new agent must remember; `orient` is
   an alias; `agent-onboard` remains a distinct, documented identity door.
2. Compact output ≤ 70 lines; today's full render reachable via `--deep`.
3. Warm < 1 s and cold < 5 s, proven by a committed-format timing receipt
   (median + p95, ≥5 runs).
4. Default path: zero network calls, zero tracked-file writes — both pinned
   by tests.
5. Strict verdicts and the §2.3 exit codes are default, operator-ratified,
   with the old exit-0 contract tests consciously replaced (not deleted
   silently).
6. Host absence is task-aware `NEEDS_HOST` with gap codes; never fake RED,
   never fake green.
7. One broken-register parser; bold/heading statuses parse; parity with all
   three legacy call sites proven before deletion.
8. Root `AGENTS.md` exists, custody-green, pointer-only.
9. Required-reading digests + startup readback emitted in receipt and render.
10. Orientation and onboarding share one typed packet implementation; every
    module < 500 lines.
11. Cache invalidation, delta computation, and the readiness mutants are
    tested (mutmut scope widened, hypothesis properties in
    `tests/properties/`).
12. `agent-build-preflight` consumes strict readiness exactly once;
    `verifier-selfcheck` propagates onboard failure.
13. CI remains the final independent enforcement layer — the readback and the
    local receipt prove integrity, never authenticity.

## §12 References

- `scripts/governance/agent_onboard.py` — current door (1883 lines; exit-0
  doctrine `:29`; receipt writer `:1695-1710`; refresh `:1630-1639`;
  `gh` call `:1373-1377`; flag contract `:1726-1731`).
- `scripts/governance/orientation_graph.py` — deep projection (fragile BR
  parser `:643-662`; write-context `:902-910`; timing receipt `:481-518`).
- `scripts/governance/check_track_status.py` — evidence owner (exit contract
  `:2239-2254`; `command_passes` runner `:464-501`).
- `dharma_swarm/memory_kernel/write_receipts.py:336-346` — `canonical_json`,
  `stable_digest`, `utc_now`.
- `scripts/governance/tam_ledger.py:304-377` — the `--check` replay contract
  and `_VOLATILE_KEYS` doctrine.
- `scripts/governance/trust_gate_status.py` — `verdict_for` thresholds,
  RED-if-unmeasured, `parse_broken_counts`.
- `dharma_swarm/world_radar/go_invoke.py:30-56`,
  `scripts/loop5b_world_radar_closure_run.py:59-71,257-270`,
  `dharma_swarm/operator_core/control_surface_go.py:159-197` — the
  `needs_host` vocabulary chain.
- `scripts/governance/pramana_probe.py:29-33,377-383` — exit-3 config-error
  precedent; phantom targets are config errors, not verdicts.
- `scripts/governance/hygiene/promote.py` +
  `scripts/governance/check_claim_evidence_binding.py:12-17,45-65` — the
  operator-promoted advisory→enforced ratchet.
- `pyproject.toml:79-99` — existing mutmut gate to widen;
  `tests/properties/` — existing hypothesis suite to extend.
- `docs/governance/CANONICAL_DOC_STACK.md` — first-read surfaces and doc
  ownership; `docs/docops/assertions.yaml` — custody registration (JSON in a
  `.yaml` file; both consumers `json.loads` first).
- `docs/plans/DHARMAGRAPH_PHASED_SPEC_2026-07-05.md` — the spec-format
  precedent this document follows.
