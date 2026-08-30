# Proposal: lean PR CI without dropping merge power

**Role:** `working_plan` (per `docs/AGENTS.md` document types). Not canon.
**Status:** DRAFT. Implementation is **not** authorized by this file until
reviewers ratify the decisions in §8.
**Track:** `repository-titanium-hardening-2026-07` (CI membrane / workflows).
**Not a merge-authority change.** Mike, branch protection, and the six
required contexts stay as they are unless a later slice explicitly edits
`scripts/governance/ci_parity_manifest.json` and live protection in the same
PR.

A sketch implementation exists as draft PR #1428
(`ci/lean-pr-membrane-20260820`). **Do not merge it.** It was written before
this proposal and is a conversation artifact, not a ratified change.

---

## 0. What this is asking

Make PR CI **faster and leaner** by spending fewer GitHub runners on questions
the diff cannot affect, while keeping **the same merge power**: a required
failure still blocks, an advisory failure still cannot fake green, and every
contracted check name still *reports*.

This is not “add more red checks.” It is not “leave GitHub.” It is not
“pytest 3.11 off pull requests” until protection is edited in the same change.

---

## 1. How to think about CI here (the membrane)

Start with the membrane, not the YAML.

| Question | Where the answer lives on `origin/main` |
|---|---|
| What is allowed to **block merge**? | `docs/governance/CI_TRUTH_CONTRACT.json` `required` (six entries: DocOps, gitleaks, pytest 3.11, pytest 3.12, Coherence Delta, onboarding) |
| Does live GitHub protection match that list? | `scripts/governance/ci_parity_manifest.json` + `.github/workflows/ci-parity.yml` |
| If a job **does not run**, does merge wedge? | `tests/test_workflow_path_filters.py` — a required check with workflow `paths:` never reports, and the queue waits forever |
| When is the question even **applicable**? | `scripts/ci/classify_changed_paths.py` (already used inside `tests.yml` for advisory jobs) |

Four buckets. Every job belongs in exactly one:

1. **Required on every PR** — must always *report* (pass/fail). Six of these.
2. **Advisory, contracted name** — must report something. `SKIPPED` is pass;
   `MISSING` is a permanent `DEGRADED` verdict
   (`tests/test_workflow_path_filters.py:278-291`).
3. **Advisory, uncontracted** — path-filter or nightly freely.
4. **Nightly / weekly / merge_group** — full power, off the PR critical path.
   Already exists: `.github/workflows/nightly-tests.yml`, CodeQL/semgrep weekly
   crons.

Lean is rearranging jobs among those buckets. It is not a fifth CI.

---

## 2. What is true on `origin/main` today

Live count from `git ls-tree origin/main .github/workflows` (2026-08-20,
`abc8bd35c`): **51** workflow files; **33** trigger on `pull_request`; **12**
of those carry a workflow-level `paths:` filter.

The in-tree diagnosis is already written, and part of it is stale:

```
scripts/ci/classify_changed_paths.py:5-10
33 of this repository's 48 workflows trigger on `pull_request` and only 5 carry
a `paths:` filter ... a measured 435-deep queue on 2026-08-07, in which a
single Dependabot PR (`dependabot/uv/h2-4.4.1`) accounted for 28 runs
```

The **5-filter** figure is no longer true (12 workflows now have `paths:`).
The **multiplier** claim still is: `tests.yml` cannot take a workflow-level
`paths:` filter because it publishes the two required pytest contexts
(`.github/workflows/tests.yml:14-17`). Dependabot `uv.lock` PRs still fire
the contracted advisory scans that have no classifier job.

Required pytest still installs with live pip, twice, plus a second unpinned
ruff:

```
.github/workflows/tests.yml:89-120
matrix: python-version: ["3.11", "3.12"]
pip install -e ".[dev]"
pip install ruff
```

The hermetic path already exists and is pinned:

```
.github/workflows/hermetic.yml:45-71
UV_VERSION: "0.11.2"
uv lock --check
uv sync --frozen --extra dev
```

CodeQL, Semgrep, and the quality ratchet are **deliberately unfiltered at
workflow level** because their check names are in
`docs/governance/CI_TRUTH_CONTRACT.json` `advisory`. Their own comments name
the correct fix and leave it undone, e.g. quality-ratchet:

```
.github/workflows/quality-ratchet.yml:24-28
Per-JOB filtering (as tests.yml does) is the correct answer here ...
it is deliberate follow-up, not done here.
```

Same comment shape in `.github/workflows/codeql.yml` and
`.github/workflows/semgrep.yml`.

Fourfold warrant is a **whole-diff** gate and must stay unfiltered
(`tests/test_workflow_path_filters.py` `WHOLE_DIFF_GATES`). This proposal
does not touch it.

Pytest on PRs is already a slice: `-m "not slow and not docker and not
network"` with `--timeout=30` (`.github/workflows/tests.yml:138-140`).
Nightly runs the rest (`.github/workflows/nightly-tests.yml`).

---

## 3. The failure modes this proposal refuses

These are the ways a “make CI faster” PR wedges `main`. They are already
tested. Any implementation slice that trips one is a bug, not an
optimization.

| Failure | Why it is fatal | Guard |
|---|---|---|
| Workflow-level `paths:` on a **required** workflow | Check never reports; branch protection waits forever | `test_no_required_workflow_carries_a_paths_filter` |
| Workflow-level `paths:` on a **contracted advisory** name | Check is `MISSING`; CI truth `DEGRADED` on every docs-only PR | `test_no_contracted_check_name_comes_from_a_path_filtered_workflow` |
| Advisory job `if: == 'true'` | Classifier failure/skip → empty output → job skipped (fail closed) | `test_every_conditional_job_fails_open` (`!= 'false'` + `!cancelled()`) |
| Advisory step inside the required pytest job | False-green pattern `check_ci_parity.py` rejects | `.github/workflows/tests.yml:108-116` |
| Drop pytest 3.11 from `pull_request` without editing protection | Required context `pytest (3.11)` stops reporting | `ci_parity_manifest.json:7-17` (`regression_sensitive: true`) |
| Skip a **matrix** job and keep the name `codeql / ${{ matrix.language }}` | Skipped matrix jobs often do not publish the contracted name | Flatten to a literal `codeql / python` if that job is skipped |

Classifier posture stays **fail open**: unreadable diff → every class true
(`scripts/ci/classify_changed_paths.py:19-24`). A classifier bug must run
too much, never too little (AI-N4).

---

## 4. Proposed slices (ratify before coding)

### Slice A — per-job skip for the three heavy contracted advisory scans

**Intent:** docs-only and lockfile-only PRs still *publish* `codeql / python`,
`semgrep`, and `Quality ratchet - repo-wide fitness function`, but as
`skipped`. Python / dashboard / hygiene diffs still run the scans.

**How:** reuse `scripts/ci/classify_changed_paths.py` from a `changes` job in
`.github/workflows/codeql.yml`, `semgrep.yml`, and `quality-ratchet.yml`.
Do **not** add workflow-level `paths:`.

**Proposed classes** (open question §8.1):

| Class | Fire when | Skip when (examples) |
|---|---|---|
| `codeql` | `*.py`, `pyproject.toml`, or `codeql.yml` | docs-only; `uv.lock`-only |
| `semgrep` | `*.py`, `*.go`, `dashboard/`, `terminal/`, `.semgrep/`, or `semgrep.yml` | docs-only; `uv.lock`-only |
| `quality_ratchet` | `*.py`, `docs/governance/hygiene/`, `scripts/governance/hygiene/`, or `quality-ratchet.yml` | docs-only; `uv.lock`-only |

`uv.lock` stays in the existing `python` class so **required pytest still
runs** on Dependabot bumps. It is omitted from the analysis classes so those
bumps do not enqueue CodeQL/Semgrep/the ratchet.

`merge_group`, `push`, and `schedule` keep current behavior: the classifier
already returns all-true for non-`pull_request` events
(`scripts/ci/classify_changed_paths.py` `resolve()`). Weekly CodeQL/semgrep
and merge-queue scans still run.

Self-coverage: editing the classifier script forces every class; editing
`tests.yml` forces only the tests.yml classes (`go`/`dashboard`/`terminal`/
`python`); editing `codeql.yml` forces only `codeql`.

CodeQL today is a one-language matrix (`python`). If Slice A skips that job,
flatten the name to the literal contracted string `codeql / python` so skip
still reports.

**Verifier (must fail before the change, pass after):**

- docs-only path set → `codeql`/`semgrep`/`quality_ratchet` are false
- `uv.lock` → `python` true, analysis classes false
- `test_no_contracted_check_name_comes_from_a_path_filtered_workflow` still green
- fail-open test extended to the new workflows

### Slice B — hermetic uv install on required pytest (and other Python jobs in `tests.yml`)

**Intent:** same required tests, less install time and no live-index
`pip install -e ".[dev]"` sitting next to hermetic.yml.

**How:** `tests.yml` workflow `env.UV_VERSION` matches Makefile / hermetic
(`0.11.2`). Pytest job: `uv lock --check` then `uv sync --frozen --extra
dev`; ruff from the frozen extra (drop `pip install ruff`). Same install
shape for the Python-using advisory jobs in that workflow. Nightly optional
in the same slice or a follow-up.

Do **not** shallow-clone pytest (`fetch-depth: 0` stays). The suite uses git
history; a depth-1 clone is a flake farm, not a lean-up.

**Verifier:** extend `tests/test_bootstrap_contract.py` so `tests.yml` must
pin the same `UV_VERSION`, check lock before frozen sync, and must not
contain `pip install -e` / `pip install ruff` as commands.

### Slice C — later, only with a protection edit

**Not in the first implementation.** `pytest (3.11)` and `pytest (3.12)` are
both `regression_sensitive` and required on every PR
(`ci_parity_manifest.json:7-17`).

A later option: pytest 3.12 on `pull_request`; both versions on
`merge_group` + nightly. That is a **membrane edit**. It is only legal if
the manifest, live branch protection, and the workflow change in the same
PR. Until then, keep both on every PR and just make install cheap (Slice B).

### Explicitly out of scope

- Switching forges (Forgejo/Gitea/GitLab/SourceHut). Mike, Codex/Copilot
  native reviews, and `gh pr merge` are GitHub-shaped
  (`docs/ops/PR_REVIEW_CONTROL.md`, `docs/governance/MMM_CHARTER.md`).
- Path-filtering `fourfold-warrant.yml` (whole-diff gate).
- Promoting advisory checks to required.
- Putting advisory ruff/style inside the required pytest job.
- Claiming live queue-depth reduction before a post-merge observation.

---

## 5. What “stronger” means here (without more PR jobs)

- **Hermetic pytest** (Slice B): lockfile drift fails the required suite, not
  only `hermetic.yml`.
- **False-green ratchet stays:** `ci-parity.yml` already fails a required job
  that swallows errors. Do not hide advisory steps inside pytest.
- **Nightly is the place for more power:** slow/docker/network, Playwright,
  mutation. If nightly is red and nobody looks, that is an attention bug, not
  a reason to put it on every PR.
- **Merge queue is the place for base-sensitive checks.** The manifest
  already marks `regression_sensitive`. That is how “tested against latest
  `main`” is supposed to work.
- **Local first.** Every contract entry already has `local_command`. CI that
  only fails in GitHub is weak.

Do not strengthen by promoting advisory → required. That is how the 57-PR
DocOps jam happened (`docs/governance/PR_QUALITY_GATES.md`).

---

## 6. Cost / benefit (what we can claim now)

| Claim | Status |
|---|---|
| Docs-only PRs stop launching CodeQL (30 min timeout), Semgrep, and whole-tree ratchet | Predicted from Slice A design; **unproven until observed on GitHub** |
| Dependabot `uv.lock` PRs stop launching those three, still run required pytest | Predicted; depends on ratifying “lockfile ∉ analysis classes” (§8.1) |
| Each remaining Python PR still pays a tiny `changes` job per workflow | Real; one short runner vs a 15–30 min scan |
| Pytest wall-clock of the test body is unchanged | Slice B only changes install |
| Merge blockers unchanged | Slice A/B by construction; Slice C is the one that would change them |

The 2026-08-07 435-deep queue is the last measured queue-depth figure in
tree (`scripts/ci/classify_changed_paths.py:7-8`). This proposal does not
pretend that number is current. Slice A’s success metric is a **new**
measurement: for one docs-only PR and one Dependabot PR after merge, count
workflow runs vs a matched PR from before.

---

## 7. Implementation sketch (parked)

Draft PR #1428 is an unratified sketch of Slices A+B. Reviewers should
**read this file, not that diff**, until §8 is decided. If the sketch is
useful after ratification, cherry-pick; if not, delete the branch.

Known sketch defects to treat as warnings, not as the plan:

- Packet preflight did not complete on the authoring host because
  `.git/info/exclude` contained an active `.gitnexus/` line. That is a host
  constraint, not a CI design fact.
- The classifier comment on main still says “5 path filters / 48 workflows.”
  Any implementation slice should correct those numbers to the live count.

---

## 8. Decisions needed before any implementation PR

Comment on the proposal PR. A silent “looks fine” is not ratification of a
row.

### 8.1 Analysis-class scope (Slice A)

**A1 (recommended).** `uv.lock` does **not** fire CodeQL/Semgrep/ratchet.
Dependabot bumps keep required pytest, drop the heavy scans.

**A2.** Any lockfile or `pyproject.toml` change fires all three scans
(safer, less lean).

**A3.** Semgrep also stays on for `dashboard/` and `terminal/` (owasp pack
is not Python-only) — this is the recommended Semgrep row if A1 wins.

### 8.2 First slice width

**B1 (recommended).** Land Slice A (classifier) alone. Measure queue.
Then Slice B (uv) as a second PR.

**B2.** Land A+B together (one PR, two mechanical changes).

**B3.** Slice B only (install), leave the multiplier for later.

### 8.3 CodeQL skip reporting

**C1 (recommended).** Flatten CodeQL to a non-matrix job named exactly
`codeql / python` so `skipped` still matches the contracted name.

**C2.** Leave the matrix and accept a possible `MISSING` on skipped PRs
(advisory only, but it degrades the operator report — the thing the
unfiltered comments exist to protect).

### 8.4 Slice C (dual Python)

**D1 (recommended now).** Do not split pytest 3.11 off `pull_request`.

**D2.** Authorize a later membrane PR: 3.12 on PR, both on merge_group,
with protection + `ci_parity_manifest.json` in the same change.

### 8.5 uv cache

**E1 (recommended for first land).** No `actions/cache` / `setup-uv` in the
first slice. Match hermetic.yml: pinned uv, frozen sync, no extra action
SHA. Revisit cache if install time is still the wall after Slice A.

**E2.** Add a SHA-pinned cache in Slice B.

---

## 9. Suggested review stance

This is a **governance/CI** proposal, not a runtime change. Useful review
questions:

1. Is fail-open still the right classifier posture now that it would skip
   CodeQL/Semgrep, not only Go/dashboard jobs?
2. Is skipping CodeQL on `uv.lock` acceptable, or is lockfile resolution a
   CodeQL input in practice?
3. Is flattening the CodeQL matrix a check-name change GitHub will treat as
   a new check (brief `MISSING` on in-flight PRs)?
4. Should Slice A also cover other contracted advisory workflows
   (module-budget, test-hygiene, pudgala-rigor), or are those cheap enough
   to leave always-on?

Non-goals for review: rewriting Mike, changing required contexts, or
migrating off GitHub.

---

## 10. Citation index

| Fact | Source |
|---|---|
| Six required merge contexts | `docs/governance/CI_TRUTH_CONTRACT.json:6-55` |
| Protection manifest / regression_sensitive pytest | `scripts/governance/ci_parity_manifest.json:6-42` |
| MISSING vs SKIPPED | `tests/test_workflow_path_filters.py:278-291` |
| Classifier multiplier diagnosis (stale counts, live queue story) | `scripts/ci/classify_changed_paths.py:5-17` |
| Live workflow counts 51 / 33 PR / 12 `paths:` | `git ls-tree origin/main .github/workflows` @ `abc8bd35c` |
| Required pytest never path-filtered | `.github/workflows/tests.yml:14-17`, `tests.yml:85-90` |
| Live pip install on required pytest | `.github/workflows/tests.yml:103-120` |
| Hermetic uv pin | `.github/workflows/hermetic.yml:45-71` |
| Per-job filter named as undone follow-up | `.github/workflows/quality-ratchet.yml:24-28` (same shape in codeql.yml, semgrep.yml) |
| Nightly full suite | `.github/workflows/nightly-tests.yml` |
| Merge membrane / Mike | `docs/ops/PR_REVIEW_CONTROL.md`, `docs/governance/MMM_CHARTER.md` |
