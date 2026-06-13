# BUG CORRAL — Convergent Audit, Merge, and Compaction Prompt

**Operator:** John Vincent Shrader
**Repo:** `/Users/dhyana/dharma_swarm` (canonical worktree on John's MacBook Pro M5 Max)
**Branch policy:** Work on a fresh branch off latest `main`. Do not push. Commit locally.
**Target folder:** `docs/bug-corral/`
**Target file count:** exactly **10 files**
**Out-of-scope (hands off):** all 15 plan-docs in Category 8 of `/home/user/workspace/finder_files_corral.md` — leave them untouched. A separate audit will circle back to them later.

---

## 0. Why this exists (read this first, do not skip)

The dharma_swarm repo has accumulated ~80 files whose function is to **find problems** — truth verifiers, anti-slop scans, repo x-rays, inventories, censuses, runtime ground-truth scripts, incident forensics, governance doctrine. They have drifted into nine overlapping families. The same findings are stated in 3–8 different files with subtly different framing, dates, and authors. Agents reading the repo cannot tell which finder file is canonical. Some are 204-byte stubs masquerading as real audits. Some have stale 2026-04 content with fresh 2026-06 mtimes. Some live only in `_archive/` but are still cited.

Your job is to **corral every distinct finding into ten files, with zero information loss, and delete the originals**. The promise is that after this pass, an agent (or John) can answer the question "what is currently broken or drifting in this repo?" by reading ten files, not eighty.

This is not a summarization task. It is a **convergence task**. Every distinct claim, file:line citation, severity rating, owner attribution, and date must survive into the corral. What gets dropped is **only**: repetition, narration, throat-clearing, redundant context-setting, and dead intra-doc cross-references.

You will be graded on three axes:
1. **Coverage** — does every unique finding from the originals appear in the corral? (Diff-checkable.)
2. **Fidelity** — are claims preserved verbatim where they reference file:line, severity, or date? (Spot-checkable.)
3. **Reversibility** — if the operator panics, can the originals be restored from git + the provenance file?

If you cannot meet all three, **stop and ask**. Do not proceed with half-confidence.

---

## 1. Source of truth: which files are in scope

The full inventory is at `/home/user/workspace/finder_files_corral.md` (the corral file already written, ~80 files across 9 categories).

**In scope (consolidate into corral):**
- Category 1 — Truth Verifiers (10 files)
- Category 2 — Anti-Slop / Vibe-Code (8 files)
- Category 3 — Repo X-Rays / Global Audits (markdown only — leave Python modules in place; see §3)
- Category 4 — Inventories / Censuses (markdown only)
- Category 5 — Runtime Ground-Truth Scripts (markdown outputs only; leave .py and .json in place; see §3)
- Category 6 — Governance Doctrine & Prompts (markdown only)
- Category 7 — Incident / Forensic Reports
- Category 9 — Deprecated / Archived Copies (`_archive/`)

**Out of scope:**
- Category 8 — Plans That Are Also Finders. **Do not touch these 15 files.** A future audit pass will collapse them.
- Live Python modules and JSON configs (see §3 for the contract).
- The corral file itself (`finder_files_corral.md`) — leave it in `/home/user/workspace/` as the working index.
- Anything under `.git/`, `node_modules/`, `__pycache__/`, `.venv/`, `dashboard/.next/`.

If you encounter a file in scope that the corral file did not list, **add it to the work** — the corral was a 95% sweep, not a guarantee.

---

## 2. The 10 target files (folder: `docs/bug-corral/`)

| # | Filename | Merges from |
|---|---|---|
| 0 | `00_INDEX.md` | A map of the corral itself: what each file contains, what was merged in, what was deleted, links to provenance |
| 1 | `01_TRUTH_VERIFIERS.md` | Category 1 — all "docs vs code vs wired" findings |
| 2 | `02_ANTI_SLOP.md` | Category 2 — all vibe-code / AI-slop findings and rules |
| 3 | `03_REPO_XRAY.md` | Category 3 — global repo audits and x-ray reports (markdown) |
| 4 | `04_INVENTORIES.md` | Category 4 — all census/inventory findings (markdown) |
| 5 | `05_RUNTIME_GROUND_TRUTH.md` | Category 5 — runtime/operator/CI ground-truth reports (markdown outputs) |
| 6 | `06_INCIDENTS.md` | Category 7 — forensic / incident / blast-radius reports |
| 7 | `07_DOCTRINE.md` | Category 6 — audit prompts, cartographer notes, AI agent governance doctrine |
| 8 | `08_ARCHIVED_FINDINGS.md` | Category 9 — content rescued from `_archive/` before originals are deleted |
| 9 | `09_PROVENANCE.md` | Per-source-file: full path, mtime, size, sha256, target corral file, line range, deletion status. The receipt. |

**File 00 is written last** — it indexes the other nine.
**File 09 is written first** — it is the manifest the merge runs against.

---

## 3. The Python / JSON contract (do not break this)

Some "finder files" are live Python modules, JSON contracts, or CI configs. **These do not move.** They stay at their current paths because non-test code imports them or CI loads them.

Specifically, leave in place:
- `dharma_swarm/auditor.py`, `dual_audit.py`, `xray.py`, `scout_audit.py`, `harness_audit.py`, `ginko_audit.py`, `ginko_report_gen.py`, `api_key_audit.py`, `semantic_governance.py`, `scout_report.py`
- `dharma_swarm/memory_kernel/census.py`
- `dharma_swarm/dhyana/drift_triage.py`
- `dharma_swarm/chetana/governance.py`, `dharma_swarm/terminal_commands/governance.py`, `dharma_swarm/tui/engine/governance.py`
- All `scripts/repo_xray.py`, `scripts/governance_scan.py`, `scripts/operator_ground_truth.py`, `scripts/vibegate_audit.py`, `scripts/close_duplicate_guardian_issues.py`, `scripts/memory_surface_census.py`, `scripts/runtime/*.py`, `scripts/governance/**/*.py`
- `tools/manifest_check.py`, `tools/manifest_check_budgets.json`
- `.semgrep/dharma-anti-slop.yml`
- `docs/governance/CI_TRUTH_CONTRACT.json`
- `tests/test_*.py` for any of the above
- `.github/ISSUE_TEMPLATE/governance.md`, `.github/workflows/stale-pr.yml`

For each LIVE Python/JSON finder, the corral must contain a **pointer entry** in the relevant target file: name, path, what it does, who imports it, last-touched date. This is a one-line reference, not a content merge. The code stays where it is.

**If a Python module's docstring contains audit findings or doctrine (not just code documentation),** extract those findings into the corral and leave the docstring in place. Mark the duplication in `09_PROVENANCE.md`.

---

## 4. Execution order (do not deviate)

### Phase A — Manifest (write `09_PROVENANCE.md` first)

1. Walk every file listed in scope. For each one capture:
   - Full path (absolute, starting `/Users/dhyana/dharma_swarm/`)
   - Filesystem mtime (YYYY-MM-DD)
   - Size in bytes
   - sha256 hash of file contents
   - Author/owner (parse from file header — "Author:", "Auditor:", "Produced by:")
   - Original category (1–9 from the corral file)
   - Target corral file (01–08)
   - One-sentence statement of what the file claims/finds
2. Write `09_PROVENANCE.md` as a single table with all of this.
3. **Stop. Share the file with John. Get explicit go-ahead before Phase B.**

### Phase B — Extraction (per target file, one at a time)

For each target file 01 through 08:

1. **Read every source file** assigned to that target (per `09_PROVENANCE.md`).
2. **Extract distinct findings.** A distinct finding is any claim that:
   - Cites a file:line (e.g. "`dharma_swarm/spine/orchestrator.py:147` returns stale data")
   - Names a duplicate, drift, or stale artifact
   - Assigns a severity (BLOCKER / CRITICAL / MAJOR / MINOR / INFO)
   - Records an owner verdict ("GO_AFTER_GAPS", "BLOCKED", "RESOLVED")
   - States a fact about what is wired vs what is documented
3. **Deduplicate.** If two files state the same finding:
   - Pick the most recent or most specific phrasing
   - List ALL source files that stated it (in a "Sources:" footnote on the finding)
   - Preserve the earliest date the finding appeared
4. **Preserve verbatim quotes** for any finding that includes:
   - A file:line citation
   - A severity rating
   - An operator-stated constraint (anything in the user's voice)
   - A verdict line
5. **Write the target file** with this structure:
   ```
   # [Family name]
   
   **Consolidated from N source files. Provenance: `09_PROVENANCE.md`.**
   **Last source touched:** YYYY-MM-DD
   
   ## Headline state
   [One paragraph: what is true about this family of findings right now.]
   
   ## Findings (sorted by severity, then date desc)
   
   ### [Severity] · [Finding ID] · [One-line summary]
   - **Sources:** `path/a.md`, `path/b.md` (the originals)
   - **First reported:** YYYY-MM-DD by [author]
   - **Last confirmed:** YYYY-MM-DD by [author]
   - **Detail:** [verbatim or near-verbatim claim, with file:line citations preserved]
   - **Status:** OPEN / RESOLVED / DEFERRED / SUPERSEDED
   
   ## Live tooling pointers
   [One-line refs to Python/JSON files that produce findings in this family, per §3]
   
   ## Superseded / archived sources
   [List of source files that contributed but added nothing not captured above.]
   ```
6. **Share the target file with John after writing it.** Get an explicit "next" before moving on. Do not batch.

### Phase C — Index (`00_INDEX.md`)

After 01–08 and 09 exist:
1. Write `00_INDEX.md` as the front door. It must contain:
   - One-paragraph statement of what the corral is and why it exists
   - A table of the 10 files with one-line summaries
   - The "as of" date
   - A pointer to `09_PROVENANCE.md` for the receipt
   - A standing note: "Plans in Category 8 of the original corral are out of scope here. A future pass will collapse them."
2. Share with John.

### Phase D — Verify (the diff gate)

Before any delete:
1. Write a Python script at `scripts/governance/verify_bug_corral.py` that:
   - Reads `09_PROVENANCE.md`
   - For each source file, extracts distinct findings (file:line patterns, severity tokens, verdict lines, dates)
   - For each finding, greps the target corral file for either the verbatim claim or a near-match
   - Outputs a report: `coverage_report.md` listing any finding present in originals but absent from corral
2. Run it. If coverage_report.md is non-empty, **fix the corral, do not delete originals.**
3. Iterate until coverage_report.md shows 100% (or John explicitly approves the gaps).

### Phase E — Delete (only after Phase D passes)

1. Build a single shell script `scripts/governance/delete_corraled_originals.sh` that `git rm`s every source file listed in `09_PROVENANCE.md` (Categories 1, 2, 3-md, 4-md, 5-md, 6-md, 7, 9 only — never the LIVE Python/JSON files from §3).
2. Show John the script before running.
3. After John approves: run it. Commit with message:
   ```
   chore(bug-corral): consolidate ~80 finder-files into docs/bug-corral/ (10 files)
   
   See docs/bug-corral/09_PROVENANCE.md for full source-file → target mapping
   and sha256 hashes. Reversible via git revert; nothing lost.
   ```
4. Tag the commit `bug-corral-v1`.

---

## 5. Hard rules

1. **No information loss.** If a finding appears in any source file and is not in the corral, the audit failed.
2. **No fabrication.** If a source file is empty (e.g. the 204-byte `agent_runner_audit.md` stub) say so explicitly in `09_PROVENANCE.md`: "Empty stub. Nothing to merge."
3. **No relocation of live code.** §3 contract is absolute.
4. **No touching of Category 8 plans.** Hands off.
5. **No emoji. No exclamation points. No "scrape/crawl" language.**
6. **No silent assumptions.** Every time you pick a winner between two conflicting source statements, log it in `09_PROVENANCE.md` under a "Conflicts resolved" section with the rationale.
7. **No batching of writes for approval.** Share each target file individually. The operator wants to inspect each one.
8. **Preserve file:line citations exactly.** Never paraphrase `dharma_swarm/spine/orchestrator.py:147` into "the spine orchestrator file" — preserve the citation.
9. **Preserve dates and authors.** Even if a finding is 18 months old, its original date and author belong in the corral entry.
10. **If a source file's content is dependent on a worktree or branch that no longer exists,** capture the finding and mark it `Status: SUPERSEDED — original context: <branch/worktree>`.

---

## 6. Edge cases — pre-decided

- **Two 204-byte stubs at repo root (`agent_runner_audit.md`, `orchestrator_audit.md`):** these are placeholders. Mark them as empty stubs in provenance. The full versions in `docs/_archive/2026-04/` are the real content; merge those into `08_ARCHIVED_FINDINGS.md` and delete both stubs.
- **`xray_report.md` with stale 2026-04-04 content but 2026-06-05 mtime:** preserve the original generation date in the finding ("Generated 2026-04-04, last re-stat 2026-06-05"). Flag the stale-mtime anomaly as its own meta-finding in `03_REPO_XRAY.md`.
- **`xray_report.json`:** 24 KB machine-readable. Do not inline into a markdown corral file. Move it to `docs/bug-corral/artifacts/xray_report.json` and reference it. Same rule for any other machine-readable output >5 KB.
- **Files referencing branches/worktrees no longer present:** preserve the finding, mark the branch context, do not attempt to verify against current state.
- **Files in `inter_agent/*/inbound/`:** treat as evidence, not as the audit itself. If the body of the message is an audit, merge it. If it's an acknowledgment, log in provenance and skip.
- **Codex's `2026-06-13_codex_feasibility_audit.md`:** this is a recent audit-of-concept for TELOS AI. Merge into `06_INCIDENTS.md` under a "Recent audits" subsection — it documents what was found in yesterday's work.

---

## 7. What success looks like

When done:
- `docs/bug-corral/` contains exactly 10 markdown files plus an optional `artifacts/` subfolder for >5 KB machine-readable outputs.
- `09_PROVENANCE.md` lists every source file with sha256, mtime, target, and status. Every entry has a deletion status: DELETED, KEPT-LIVE-CODE, KEPT-OUT-OF-SCOPE.
- `coverage_report.md` (from the verifier script) shows 100% finding coverage, or every gap is explicitly approved by John.
- `git log --diff-filter=D --name-only` on the corral commit lists every deleted file; `git show bug-corral-v1` reveals the full mapping.
- An agent or John can answer "what is broken or drifting?" by reading `00_INDEX.md` and then at most 2 of the other 9 files. No agent needs to read the originals.
- The originals are recoverable via `git revert bug-corral-v1` or `git checkout bug-corral-v1~1 -- <path>`.

---

## 8. Stop conditions (when to interrupt and ask John)

Pause and ask if any of these occur:
- Phase A reveals more than 100 source files (the corral file said ~80; significant deviation is a signal).
- Two source files have directly contradictory findings (e.g., one says "BLOCKER", one says "RESOLVED" on the same artifact, with no superseding date).
- A source file is encrypted, binary, or unreadable.
- The verifier script's coverage_report.md has more than 10 uncovered findings after one fix pass.
- You encounter a finder file whose function isn't clearly covered by any of the 10 target files (a new category is needed).
- Any file in scope is currently being edited (`.swp`, lock file, recently modified in last 5 minutes).

Each stop should produce a single concrete question, the data backing it, and three options for resolution.

---

## 9. Tools and conventions

- Use `pc bash` for all Mac filesystem operations (`api_credentials=["pc"]`).
- Use `pc files read` for batch reading source files (max 20 paths per call, 256 KiB per file).
- Use `pc files write` for writing corral files to `/Users/dhyana/dharma_swarm/docs/bug-corral/`.
- For the sha256 manifest: `pc bash 'cd /Users/dhyana/dharma_swarm && shasum -a 256 <file>'`.
- For git operations: write the shell script, show John, then `pc bash` to run it after approval.
- Markdown headers ≤ 6 words, no italics, no emoji.
- Citations as inline markdown links — anchor text is the source name, never "source" or raw URL.

---

## 10. The opening move

Start by:
1. Reading `/home/user/workspace/finder_files_corral.md` end-to-end.
2. Running the file enumeration on the Mac to catch anything the corral file missed.
3. Writing `09_PROVENANCE.md` as a complete manifest.
4. Sharing it with John.
5. Waiting for go-ahead.

Do not write `01_TRUTH_VERIFIERS.md` or anything else until provenance is approved.

The first deliverable is the receipt. Everything else flows from it.
