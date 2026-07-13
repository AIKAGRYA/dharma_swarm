# Verification Log

**Purpose:** reproducibility receipt for material discovery, execution, and failure checks.  
**Date:** primary assessment 2026-07-13; iterative MiroFish/telemetry extension 2026-07-14; Asia/Tokyo host, web dates recorded in UTC/calendar date.  
**Safety:** commands that exposed host process credentials are intentionally not reproduced; outputs and values were not retained. No product source was modified, no dependency was installed into Dharma, and no commit/push/PR/message was performed.

## 1. Environments

| Surface | Value |
|---|---|
| Host | macOS 26.5.1 arm64 |
| Host Make | GNU Make 3.81 |
| System Python | `/usr/bin/python3`, 3.9.6 |
| Reused repository Python | `/Users/dhyana/dharma_swarm/.venv/bin/python`, 3.13.12 |
| Project requirement | Python `>=3.11` |
| Rust | `rustc` / `cargo` 1.94.1 |
| Go | 1.26.3 |
| Unavailable | Zig; usable Java/Clojure/SBT; .NET; bare-metal Intel/FreeBSD test host |
| Initial clean Dharma worktree | `/private/tmp/ds_funding_adjudication_20260713`; ephemeral and removed before final validation |
| Final clean Dharma clone | `/private/tmp/ds_final_validation_20260713`; detached at the frozen SHA and used for final admission, focused-test, entry-point, and counterexample reruns |
| Temporary OSS storage | `/private/tmp/dharma_antithesis_research_20260713/oss` |
| Iteration source clones | `/private/tmp/mirofish_primary`, `/private/tmp/oasis_primary`, `/private/tmp/otel_genai` |
| Artifact directory | `reports/audits/dharma_antithesis_master_assessment_2026-07-13` |

## 2. Repository discovery and custody

Material commands:

```bash
rg --files -g AGENTS.md -g CLAUDE.md -g pyproject.toml -g Makefile /Users/dhyana
git worktree list --porcelain
git remote -v
git fetch origin main
git rev-parse origin/main
git log -1 --format='%H%n%cI%n%s' origin/main
git status --short --branch
git rev-list --left-right --count origin/main...HEAD
git diff --name-only debff832ac4cbf7b385664d00f184f0ffdb909c4..origin/main
```

Outcomes:

- initial clean freeze `debff832…`; upstream advanced once to `c14b950…`;
- final report freeze `c14b950bc5009f2200d9425155010be508ead981`;
- intervening commit changed 11 onboarding/docops paths; no audited graph/runtime defect path changed;
- named default checkout was dirty and substantially divergent; it was not modified;
- graph autopsy branch had no unique commits over main; parity branch was squash-incorporated plus later persistence work;
- 32 open worktrees were observed.

The clean temporary worktree was moved with:

```bash
git switch --detach origin/main
git status --short
git rev-parse HEAD
```

Outcome: clean detached `c14b950…`.

The initial temporary worktree disappeared during concurrent post-audit cleanup before final artifact validation. A fresh clean clone was therefore detached at `c14b950…`; `git status --short` was empty before the final exact-current reruns. Temporary paths are execution contexts only. The frozen commit, report-local harness, and copied parity receipt/matrix are the durable evidence identities; the persistent user checkout was not substituted as current-main evidence.

## 3. Onboarding/admission

### Initial deep-test baseline

```bash
make onboard
```

At the earlier clean `debff832…` worktree, system Python 3.9 reached imports and failed with a Pydantic type-evaluation `TypeError` involving `dict[str, Any] | None`; project metadata requires Python >=3.11.

```bash
make onboard PYTHON=/Users/dhyana/dharma_swarm/.venv/bin/python
```

At the earlier baseline, supported Python rendered onboarding but reported `BLOCKED`; clean checkout lacked the generated active-track projection and reported broken-register items. An independent lane also observed a corrupt prior external receipt being replaced despite wording saying it would not be replaced silently.

### Exact current main

```bash
make --version | head -2
make onboard
```

Outcome:

```text
GNU Make 3.81
Makefile:592: *** multiple target patterns.  Stop.
exit 2
```

No `gmake` was installed. A Docker daemon was inaccessible, so a second Make version was not executed locally. No explicit repository minimum GNU Make version was found; a planning document records one GNU Make 4.3 environment but does not declare it as the support floor. The result is therefore classified as a demonstrated stock-macOS host portability/admission blocker, not proof that every newer-Make release environment fails. The GitHub merge-commit onboarding-parity check was later observed as skipped.

## 4. DharmaGraph tests and gauntlet

Exact current-main focused suite:

```bash
PYTHONDONTWRITEBYTECODE=1 \
  /Users/dhyana/dharma_swarm/.venv/bin/python -m pytest -q \
  -p no:cacheprovider \
  tests/test_graph_neutral_core.py \
  tests/test_graph_neutral_routing.py \
  tests/test_graph_neutral_cycles_resume.py \
  tests/test_graph_persistence_kernel.py \
  tests/test_graph_checkpoint.py \
  tests/test_graph_durable_invoker.py \
  tests/test_graph_reconciler.py \
  tests/test_graph_chaos_receipt.py \
  tests/test_graph_telos_bridge.py \
  tests/test_graph_receipt_chain.py \
  tests/test_graph_neutral_langgraph_oracle.py \
  tests/test_dharmagraph_parity_gauntlet.py \
  tests/test_langgraph_differential_oracle.py \
  --disable-warnings
```

Outcome: `188 passed in 10.76s` initially and `188 passed in 4.58s` on the final exact-current rerun, exit 0 both times.

Fresh current-main builder:

```bash
PYTHONDONTWRITEBYTECODE=1 \
  /Users/dhyana/dharma_swarm/.venv/bin/python \
  scripts/governance/dharmagraph_parity_gauntlet.py \
  --emit --role builder \
  --output /private/tmp/dharma_antithesis_research_20260713/current_main_c14_builder_receipt.json \
  --matrix /private/tmp/dharma_antithesis_research_20260713/current_main_c14_parity_matrix.md \
  --seed 20260713 --performance-iterations 5
```

Outcome: `52.00/100`, 34 gaps, broken control failed, source-tree digest `ffd0e30ef0684c6318d44dfa1adf4fab2ed5892f5b08dd44e08017dc36108cde`, exit 0.

The final builder outputs were copied into the assessment before the temporary research directory was treated as disposable:

- [`evidence/current_main_c14_builder_receipt.json`](evidence/current_main_c14_builder_receipt.json), SHA-256 `fcd00dfa5a4b82cee0984134afe01d464201692011fe2709ba5c211a1d90fc58`;
- [`evidence/current_main_c14_parity_matrix.md`](evidence/current_main_c14_parity_matrix.md), SHA-256 `17948fb0386635396d35db7ec0b280b296becf4b34adcb3e236e6d360a7b0af2`.

Committed receipt replay:

```bash
PYTHONDONTWRITEBYTECODE=1 \
  /Users/dhyana/dharma_swarm/.venv/bin/python \
  scripts/governance/dharmagraph_parity_gauntlet.py \
  --check --seed 20260711 --performance-iterations 5
```

Outcome: `check=PASS`, no findings, score 52/100, exit 0. A prior diagnostic with a non-frozen seed correctly changed the stable digest; it is not cited as receipt staleness.

### Safe entry-point registration smokes

These commands bound import/registration viability only; no lifespan, provider, transport, or mutating command was started:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=. /Users/dhyana/dharma_swarm/.venv/bin/python \
  -m dharma_swarm.cli --help >/dev/null
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=. /Users/dhyana/dharma_swarm/.venv/bin/python \
  -m dharma_swarm.dgc_cli --help >/dev/null
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=. /Users/dhyana/dharma_swarm/.venv/bin/python \
  -c 'from dharma_swarm.mcp_server import create_mcp_server; print(type(create_mcp_server("/private/tmp/dharma-audit-mcp-fixture")).__name__)'
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=. /Users/dhyana/dharma_swarm/.venv/bin/python \
  -c 'from dharma_swarm.a2a.a2a_server import A2AServer; print(type(A2AServer(persist=False)).__name__)'
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=. /Users/dhyana/dharma_swarm/.venv/bin/python \
  -c 'from api.main import app; print(app.title, len(app.routes))'
```

Outcome: both help commands exited 0; the factory/import outputs were `Server`, `A2AServer`, and `DHARMA COMMAND 151`; aggregate exit 0.

## 5. Deterministic local counterexamples

The report-local, network-denied harness was executed from the final clean clone. It asserts the frozen SHA before importing project code and writes only to temporary directories:

```bash
cd /private/tmp/ds_final_validation_20260713
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=. \
  /Users/dhyana/dharma_swarm/.venv/bin/python \
  /Users/dhyana/dharma_swarm/reports/audits/dharma_antithesis_master_assessment_2026-07-13/COUNTEREXAMPLE_PROBES.py
```

Outcome: all 12 named probes returned `"reproduced": true`; final summary `{"all_reproduced": true, "count": 12}`, exit 0.

Material outcomes:

| Probe | Outcome |
|---|---|
| Graph persistence synchronized two-writer collision | 2 attempted, 1 persisted, no writer error |
| Checkpoint child mutation | parent channel/version changed; mappings identical |
| Invalid pending-write resume | same conflict repeated; pending record remained |
| Parity judge mutation | attacker identity and `not-a-signature` accepted after digest recomputation |
| Import-only parity facet | partial credit earned without successful behavior |
| Reconciler status-only receipt | positive test accepted status/task dictionary |
| Stigmergy two-instance decay/append | new mark disappeared |
| Failed prerequisite readiness | dependent child returned ready |
| Provider proxy propagation | resolved proxy differed from actual client endpoint |
| Provider diversity | two logical lanes resolved to Claude Code backend |
| WebSocket with API key configured | missing-token connection accepted and snapshot received |
| SignalBus subscriber mutation | queued event reflected subscriber mutation |

## 6. Runtime and security observations

Read-only listener/cwd/health inspection established:

- listener cwd `/Users/dhyana/dharma_swarm`;
- runtime source `5207a2fb…`, dirty and stale versus current main;
- one early health response succeeded; a later TCP connection succeeded while HTTP did not complete; cause unresolved.

A host process census exposed live credentials in arguments. The command/output is omitted deliberately. Values were not copied into any note, prompt, command, or artifact. Source tracing found no committed Dharma launcher responsible, so the finding is host-operational, not attributed to repository code.

## 7. GitHub CI query

```bash
gh api repos/AmitabhainArunachala/dharma_swarm/commits/c14b950bc5009f2200d9425155010be508ead981/check-runs \
  --jq '.check_runs[] | [.name,.conclusion,.status,.html_url] | @tsv' | sort
```

At the initial query time:

- success: CodeQL, Semgrep, gitleaks, dashboard, gauntlet tier 1, kernel pytest/Hypothesis, manifest, hermetic lock, quality ratchet and several governance jobs;
- in progress: Python 3.11 and 3.12 suites;
- skipped: `ACTIVE_TRACK governance gate` and `Onboarding admission parity`.

A final refresh showed Python 3.11/3.12 and the active-track gate successful; one duplicate quality-ratchet run remained in progress. `Onboarding admission parity` remained skipped on the observed main/merge-associated checks. GitHub returned duplicate check names from multiple associated runs, so the report does not collapse them into one invented status.

## 8. Temporary public repositories

Shallow/sparse clones were pinned under `/private/tmp`. Representative commands:

```bash
git clone --depth 1 https://github.com/apple/foundationdb.git
git clone --depth 1 https://github.com/tigerbeetle/tigerbeetle.git
git clone --depth 1 https://github.com/awslabs/shuttle.git
git clone --depth 1 https://github.com/tokio-rs/turmoil.git
git clone --depth 1 https://github.com/madsim-rs/madsim.git
git clone --depth 1 https://github.com/stateright/stateright.git
git log -1 --format='%H|%cI|%s'
```

Additional clones/pins are enumerated in `SOURCE_MANIFEST.csv`. Initial sparse-fetch/Cargo dependency requests failed on sandbox DNS. Required public fetches were rerun with scoped approved network access. No third-party source was copied into the Dharma repository.

### Representative tests

```bash
# Stateright: repository had no root Cargo.lock, so --locked failed by design.
cargo test --lib
# 91 passed; 0 failed

cargo test -p turmoil --lib
# 30 passed; 0 failed

cargo test -p madsim --lib
# 1 passed; 0 failed

cargo test -p shuttle replay_causality -- --nocapture
# 2 passed; 432 filtered
```

The broad Shuttle command:

```bash
cargo test -p shuttle
```

discovered 434 tests and passed many cases, but several exhaustive cases exceeded 60 seconds; source/output also marked several schedule-emission replay tests ignored as broken. It was interrupted with exit 130 after sufficient representative evidence. It is reported as incomplete, not green or failed.

Independent OSS-lane commands/outcomes:

```text
dhyve/dhv cargo test --workspace --locked -q -> 35 passed
QuickCheck cargo test -p quickcheck --lib -> 69 passed
Loom cargo test --test smoke -> 1 passed
LibAFL cargo test -p libafl_bolts staterestore --lib -> 1 passed
Bedrock cargo test -p bedrock-vmx --lib --locked -> 135 passed, 1 Darwin/arm64 CPUID failure
```

FoundationDB/TigerBeetle source was inspected directly. They were not built because the required large C++/Zig toolchains were unavailable. No hypervisor or kernel module was executed.

## 9. Public web research

Current lawful public pages were accessed with normal web requests/search. No login, paywall bypass, private endpoint, or automated bulk crawl was used. Important URLs, exact titles, publication/access dates, source class, and extracted claim boundary are in `SOURCE_MANIFEST.csv`.

Negative public searches for Antithesis patents/filings were performed across USPTO Patent Center, Google Patents, WIPO PATENTSCOPE and SEC EDGAR using company, product and founder names. No attributable patent family or SEC filing was found. This is a bounded negative search, not proof of absence.

### 9.1 2026-07-14 MiroFish and telemetry iteration

The extension preserved the frozen Dharma baseline and added source/documentation inspection only:

```text
MiroFish  96096ea0ff42b1a30cbc41a1560b8c91090f9968  2026-05-25  AGPL-3.0
OASIS     7234ac32589499ffb493e053f36d4de82aec8f43  2026-07-10  Apache-2.0
OTel GenAI 63f8200eee093730ce845d26ce2aafb621b0807e  2026-07-08  Apache-2.0
```

MiroFish's README, requirements, graph/ontology/profile/config generators, simulation manager/runner, action logger, report agent, state handling, and test inventory were inspected. OASIS environment/action/recommender/interview interfaces, examples, tests, and license were inspected. No LLM, Zep, social simulation, Collector, trace backend, Kubernetes/eBPF, or profiler process was run. The report therefore distinguishes observed source structure from author-reported OASIS scale and from untested output quality.

For the Dharma seam, `git show c14b950…:dharma_swarm/spine/receipt.py` confirmed that the receipt is canonical and OTel is an export adapter; the adapter emits `gen_ai.system`. `git grep` located the matching assertion in `tests/test_dispatch_dropoff_sources.py`. The pinned current developmental OTel GenAI source uses `gen_ai.provider.name`. This is reported as bounded adapter-schema drift, not as a settlement defect.

The high-end monitoring comparison inspected official OTel/Collector, OpenInference, Harbor ATIF, Temporal history, Honeycomb BubbleUp, ClickStack Event Deltas, Tempo TraceQL, Google SRE, Hubble, Tetragon, and Pyroscope material. No product trial or performance benchmark was performed. Exact sources and claim boundaries are in `SOURCE_MANIFEST.csv` and claims `D-025`, `O-013`–`O-019`, and `P-004`–`P-005` in `EVIDENCE_LEDGER.jsonl`.

## 10. Artifact validation commands

The following were the final gates (the checksum file was generated only after report content was frozen):

```bash
python3 /Users/dhyana/.codex/skills/audit-dharma-antithesis/scripts/validate_assessment.py \
  /Users/dhyana/dharma_swarm/reports/audits/dharma_antithesis_master_assessment_2026-07-13 \
  --profile full

jq -e -s 'length == 63 and (map(.claim_id) | length == (unique | length))' \
  EVIDENCE_LEDGER.jsonl

ruby -rcsv -e 't=CSV.read(ARGV[0], headers: true); abort unless t.length==132; abort unless t["source_id"].uniq.length==132; abort unless t["url_or_path"].uniq.length==132' \
  SOURCE_MANIFEST.csv

gitleaks detect --no-git --source . --redact --exit-code 1 --verbose

rg -l --pcre2 -e \
'-----BEGIN (RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----|AKIA[0-9A-Z]{16}|gh[pousr]_[A-Za-z0-9]{36,255}|github_pat_[A-Za-z0-9_]{20,255}|xox[baprs]-[A-Za-z0-9-]{10,255}|sk-[A-Za-z0-9_-]{20,255}|eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}' \
  /Users/dhyana/dharma_swarm/reports/audits/dharma_antithesis_master_assessment_2026-07-13

rg --files /Users/dhyana/dharma_swarm/reports/audits/dharma_antithesis_master_assessment_2026-07-13 | sort
git status --short -- reports/audits/dharma_antithesis_master_assessment_2026-07-13
```

For public-link validation, a Ruby extraction pass formed the union of the manifest URLs and Markdown link destinations, then a 12-worker `curl -L -sS -o /dev/null --max-time 20 -w '%{http_code}'` GET pass checked every unique HTTP(S) URL. Local Markdown links were validated separately. See the final section for results.

## 11. Limitations

- No full Dharma test suite, clean dependency rebuild, multi-platform Make matrix, production restart, destructive fault, real provider call, deployment, backup restore, or live mutation was executed.
- Final CI observation had the Python 3.11/3.12 and active-track checks green, one duplicate quality-ratchet run still in progress, and onboarding parity skipped; duplicate check names prevent a single synthesized status.
- Antithesis core and assurance reports are closed/gated; no customer tenant or product POC was used.
- Some public repository tests resolved current compatible dependencies because upstream omitted root lockfiles.
- No commercial comparator was executed.
- No MiroFish/OASIS simulation, forecast benchmark, OTel Collector/backend, Kubernetes/eBPF witness, or continuous profiler was executed; the July 14 extension is pinned source/documentation research plus target-architecture synthesis.
- One historical Galileo documentation URL returned HTTP 404; the corresponding comparison is explicitly historical and is not asserted as current product behavior.
- Original Antithesis/comparator evidence remains frozen at 2026-07-13; only the explicitly marked MiroFish/OASIS/telemetry extension is current through 2026-07-14.

## 12. Final artifact validation

Executed after completing and freezing the assessment set:

- artifact gate: **13 files**, comprising all 8 required deliverables, this verification log, the executable audit harness, two durable current-main parity artifacts, and `SHA256SUMS`;
- official full-profile assessment validator: **0 errors, 0 warnings**; this proves structural/evidence-contract conformance, not substantive truth;
- exact-current focused suite: **188 passed**, exit 0; exact-current counterexample harness: **12/12 reproduced**, exit 0; these frozen-baseline product checks are carried forward from July 13 because the July 14 iteration changed no product code or baseline claim;
- JSONL parse/schema gate: **63 rows**, unique claim IDs, all required fields, and only `observed`, `reproduced`, `reported`, `inferred`, or `speculative` modalities;
- CSV parse/schema gate: **132 rows and 132 unique URL/path values**, required columns present, unique source IDs;
- redirect-aware public URL gate: **132 unique URLs checked, 131 returned HTTP 200, 1 returned HTTP 404** (the historical Galileo page disclosed above);
- citation coverage gate: every HTTP(S) Markdown citation destination was present in the 132-row source manifest;
- local Markdown-link gate: **0 broken report-local destinations**;
- gitleaks and a token-shape credential scan scoped to the assessment directory returned no findings;
- repository status showed only the new untracked assessment directory; unrelated user changes remained untouched;
- `SHA256SUMS` covers the other 12 files, excludes itself, and passed `shasum -a 256 -c SHA256SUMS`.

No artifact was committed, pushed, published, or sent externally.
