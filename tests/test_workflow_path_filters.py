"""Path filters must never be able to starve a required check.

The failure this guards against is not "a job ran that didn't need to". It is:
a REQUIRED context gets a `paths:` filter, a PR does not match it, the workflow
never runs, the check never reports, and branch protection waits on a status
that will never arrive. Every PR in the repository becomes unmergeable, and the
symptom ("Expected — waiting for status to be reported") does not name the
workflow that caused it.

That is worth a mechanical gate rather than reviewer vigilance, because the
change that causes it looks exactly like the 13 safe ones next to it.
"""

from __future__ import annotations

import json
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = REPO_ROOT / ".github" / "workflows"
MANIFEST = REPO_ROOT / "scripts" / "governance" / "ci_parity_manifest.json"


def _required_workflow_files() -> set[str]:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    return {entry["workflow"] for entry in manifest["required_contexts"]}


def _pull_request_stanza(doc: dict) -> dict | None:
    # `on` is parsed as the boolean True by YAML 1.1 ("on" is a truthy keyword).
    triggers = doc.get("on", doc.get(True)) or {}
    if not isinstance(triggers, dict):
        return None
    stanza = triggers.get("pull_request")
    return stanza if isinstance(stanza, dict) else None


def test_no_required_workflow_carries_a_paths_filter() -> None:
    """THE gate. A required check that does not run never reports."""
    offenders = []
    for name in sorted(_required_workflow_files()):
        path = WORKFLOWS / name
        assert path.exists(), f"manifest names a missing workflow: {name}"
        stanza = _pull_request_stanza(yaml.safe_load(path.read_text()))
        if stanza and "paths" in stanza:
            offenders.append(f"{name} filters on {stanza['paths']}")
    assert not offenders, (
        "these workflows produce REQUIRED checks and must run on every PR; "
        "a paths filter here wedges the merge queue permanently: " + "; ".join(offenders)
    )


def test_the_required_pytest_job_is_never_conditional() -> None:
    """tests.yml mixes the two required pytest contexts with advisory jobs, so
    the filtering there is per-job. `pytest` must stay outside it: neither an
    `if:` nor a `needs:` on the classifier, since a failed classifier would
    then skip the required contexts."""
    doc = yaml.safe_load((WORKFLOWS / "tests.yml").read_text())
    pytest_job = doc["jobs"]["pytest"]
    assert "if" not in pytest_job, "the required pytest job must not be conditional"
    assert "needs" not in pytest_job, (
        "pytest must not depend on the changed-path classifier — a classifier "
        "failure would skip both required contexts"
    )


def test_every_conditional_job_fails_open() -> None:
    """Advisory jobs key off the classifier. They must test `!= 'false'`, not
    `== 'true'`: when the classifier fails, is skipped, or times out, its
    outputs are empty strings. `'' == 'true'` skips the job (fail closed);
    `'' != 'false'` runs it (fail open). Only the second is safe.

    The guard must also override the implicit "all needs succeeded" gate, or a
    FAILED classifier would skip every advisory job. `!cancelled()` does that
    while still honouring cancellation; `always()` does it too but keeps the
    jobs running after the run is cancelled, so pressing Cancel would not
    release their runners -- directly against this change's purpose (#1285
    review). Empty outputs still evaluate true under either, so fail-open is
    unaffected.
    """
    offenders = []
    for path in sorted(WORKFLOWS.glob("*.yml")):
        doc = yaml.safe_load(path.read_text(encoding="utf-8"))
        for name, body in (doc.get("jobs") or {}).items():
            condition = " ".join(str(body.get("if", "")).split())
            if "needs.changes.outputs" not in condition:
                continue
            label = f"{path.name}:{name}"
            if "== 'true'" in condition or '== "true"' in condition:
                offenders.append(f"{label}: fail-closed comparison: {condition}")
            if "!cancelled()" not in condition:
                offenders.append(
                    f"{label}: missing !cancelled(), so a FAILED classifier would "
                    f"skip this job instead of running it: {condition}"
                )
            if "always()" in condition:
                offenders.append(
                    f"{label}: always() keeps this job running after the run is "
                    f"cancelled, so Cancel stops freeing runners: {condition}"
                )
    assert not offenders, offenders


def test_a_filtered_workflow_still_runs_when_its_own_definition_changes() -> None:
    """A filter that excludes the workflow's own file means editing the check
    cannot run the check — you could break a gate and CI would agree with you."""
    offenders = []
    for path in sorted(WORKFLOWS.glob("*.yml")):
        stanza = _pull_request_stanza(yaml.safe_load(path.read_text()))
        if not stanza or "paths" not in stanza:
            continue
        patterns = [str(p) for p in stanza["paths"]]
        covers_self = any(
            p == f".github/workflows/{path.name}" or p == ".github/workflows/**"
            for p in patterns
        )
        if not covers_self:
            offenders.append(f"{path.name} does not list itself: {patterns}")
    assert not offenders, offenders


CLASSIFIER_WORKFLOWS: tuple[str, ...] = (
    "tests.yml",
    "codeql.yml",
    "semgrep.yml",
    "quality-ratchet.yml",
)

# Contracted advisory scans that must stay unfiltered at workflow level and
# skip per-job via the classifier. Job id -> output name.
CONTRACTED_ADVISORY_JOBS: dict[str, tuple[tuple[str, str], ...]] = {
    "codeql.yml": (("analyze", "codeql"),),
    "semgrep.yml": (("semgrep", "semgrep"), ("rule2-behavior", "semgrep")),
    "quality-ratchet.yml": (("quality-ratchet", "quality_ratchet"),),
}


def test_the_classifier_is_reachable_from_the_workflow() -> None:
    """The `changes` job invokes a real file; a rename would silently make the
    step fail, and every consumer would then fail open to running everything —
    correct, but it would quietly undo the whole change."""
    assert (REPO_ROOT / "scripts" / "ci" / "classify_changed_paths.py").exists()
    missing = []
    for name in CLASSIFIER_WORKFLOWS:
        doc = yaml.safe_load((WORKFLOWS / name).read_text(encoding="utf-8"))
        job = (doc.get("jobs") or {}).get("changes")
        if not job:
            missing.append(f"{name}: no changes job")
            continue
        steps = job.get("steps") or []
        runs = " ".join(str(s.get("run", "")) for s in steps)
        if "scripts/ci/classify_changed_paths.py" not in runs:
            missing.append(f"{name}: changes job does not invoke the classifier")
    assert not missing, missing


def test_contracted_advisory_scans_skip_per_job_not_per_workflow() -> None:
    """The queue-lean change. Workflow-level paths: on these names is MISSING
    (banned above). Per-job skip is SKIPPED, which CI truth treats as PASS."""
    for filename, jobs in CONTRACTED_ADVISORY_JOBS.items():
        doc = yaml.safe_load((WORKFLOWS / filename).read_text(encoding="utf-8"))
        stanza = _pull_request_stanza(doc)
        assert stanza is not None, f"{filename} lost its pull_request stanza"
        assert "paths" not in stanza, (
            f"{filename} grew a workflow-level paths filter; contracted names "
            "would go MISSING on every excluded PR"
        )
        for job_id, output in jobs:
            body = doc["jobs"][job_id]
            condition = " ".join(str(body.get("if", "")).split())
            assert f"needs.changes.outputs.{output} != 'false'" in condition, (
                f"{filename}:{job_id} is not keyed on classifier output "
                f"{output!r}: {condition}"
            )
            needs = body.get("needs") or []
            if isinstance(needs, str):
                needs = [needs]
            assert "changes" in needs, (
                f"{filename}:{job_id} does not need the classifier job"
            )


# Reviewed on PR #1285 (Devin, 4 valid findings). Each of these filters was
# keyed on the *topic* of its workflow rather than on the *inputs its jobs
# actually read*, so each gate stopped firing on exactly the change it exists
# to catch. The cited line is the code that consumes the path.
GATE_INPUTS: dict[str, tuple[tuple[str, str], ...]] = {
    "hermetic.yml": (
        # codeowners_blast_radius.py:68 builds the import graph over the package;
        # :224 grades it against CODEOWNERS. Filtering to lockfiles meant a PR
        # adding a heavy module, or deleting an ownership entry, ran no check.
        ("dharma_swarm/**.py", "codeowners_blast_radius.py:68 rglob"),
        (".github/CODEOWNERS", "codeowners_blast_radius.py:224 reads it"),
    ),
    # Second review round on #1285 found the same defect in three more filters.
    "import-provenance.yml": (
        ("requirements*.txt", "check_import_provenance.py declared_dists()"),
        (
            "packages/*/pyproject.toml",
            "declared_dists() globs packages/*/pyproject.toml; the root-only "
            "'pyproject.toml' pattern does not match it",
        ),
        (
            "scripts/governance/import_provenance_allowlist.txt",
            "check_import_provenance.py ALLOWLIST_REL",
        ),
    ),
    "name-drift.yml": (
        (
            "scripts/governance/name_drift_allowlist.txt",
            "check_name_drift.py ALLOWLIST_REL",
        ),
    ),
}

# Gates whose input IS the whole diff. A `paths:` filter on one of these is
# never merely narrow — it deletes the gate for the PRs it excludes. Listed
# with the reason it cannot be scoped, because "add the missing patterns" is
# the wrong fix here: any enumeration is a list nobody can prove complete, and
# a filter that is silently short is worse than no filter at all.
WHOLE_DIFF_GATES: dict[str, str] = {
    "fourfold-warrant.yml": (
        "check_shakti_warrant.py runs with --diff-scope base; _path_stats "
        "(shakti_warrant.py:243-273) scores docs, config and governance paths "
        "as first-class inputs and _explicit_block_reasons (:379-399) matches "
        "against the request text, so a docs-only or Go-only PR earns a real "
        "graded verdict that a language filter would delete"
    ),
}


def test_a_filtered_workflow_still_runs_when_its_gate_inputs_change() -> None:
    """A filter keyed on topic instead of inputs silences its own gate.

    Listing the workflow file itself (the test above) is not enough: the gate
    reads files the filter never mentioned, so the check went quiet on exactly
    the diffs it was written to catch, while still passing on `push: main`
    afterwards — a green PR board and a post-merge red."""
    for filename, requirements in GATE_INPUTS.items():
        doc = yaml.safe_load((WORKFLOWS / filename).read_text(encoding="utf-8"))
        stanza = _pull_request_stanza(doc)
        assert stanza is not None, f"{filename} lost its pull_request stanza"
        paths = list(stanza.get("paths") or [])
        # A stale entry must be LOUD. If a workflow stops being filtered, its
        # requirements here become vacuously satisfiable, and the table would
        # quietly stop meaning anything — the AI-N4 shape this table exists to
        # avoid, one level up.
        assert paths, (
            f"{filename} is listed in GATE_INPUTS but carries no paths filter; "
            "remove the entry rather than leaving it to pass vacuously"
        )
        for pattern, why in requirements:
            assert pattern in paths, (
                f"{filename} filters out {pattern!r}, but its gate reads it "
                f"({why}). The workflow will not run on the change it exists "
                f"to catch."
            )


def test_the_terminal_lane_runs_when_the_python_bridge_it_boots_changes() -> None:
    """terminal/src/bridge.ts:54 spawns `python3 -m dharma_swarm.terminal_bridge`,
    which is why the job installs the Python package. Gating the lane on
    `terminal/` alone let a bridge regression merge untested."""
    doc = yaml.safe_load((WORKFLOWS / "tests.yml").read_text(encoding="utf-8"))
    condition = " ".join(str(doc["jobs"]["terminal"]["if"]).split())
    assert "needs.changes.outputs.python != 'false'" in condition, (
        "the terminal lane no longer runs on Python-only changes, but its "
        "behavioral tests boot dharma_swarm.terminal_bridge; got: " + condition
    )


def test_the_hot_path_set_has_no_input_the_warrant_filter_cannot_see() -> None:
    """Defence in depth behind WHOLE_DIFF_GATES.

    fourfold-warrant is unfiltered today, so the hot-path set is trivially
    covered and this passes on the first branch. It stays live because if
    anyone ever re-adds a filter there, `.pre-commit-config.yaml` — the only
    non-.py member of _HOT_PATHS — is the input a `**/*.py` filter silently
    drops, and this names it explicitly. Re-parsed from the source so the
    hand-written table cannot go stale (AI-N4)."""
    import re

    doc = yaml.safe_load(
        (WORKFLOWS / "fourfold-warrant.yml").read_text(encoding="utf-8")
    )
    stanza = _pull_request_stanza(doc)
    paths = list((stanza or {}).get("paths") or [])
    if not paths:
        return

    source = (REPO_ROOT / "dharma_swarm" / "shakti_warrant.py").read_text(
        encoding="utf-8"
    )
    block = re.search(r"_HOT_PATHS = frozenset\(\s*\{(.*?)\}", source, re.DOTALL)
    assert block, "_HOT_PATHS literal not found in shakti_warrant.py"
    entries = re.findall(r'"([^"]+)"', block.group(1))
    assert entries, "no _HOT_PATHS entries parsed"

    uncovered = [
        entry for entry in entries
        if not entry.endswith(".py") and entry not in paths
    ]
    assert not uncovered, (
        "hot paths the fourfold-warrant filter cannot see, so a PR touching "
        f"only them would skip the attestation gate: {uncovered}"
    )


def test_a_whole_diff_gate_never_carries_a_paths_filter() -> None:
    """Some gates grade the entire diff. Filtering one does not make it narrow,
    it makes it absent for every PR the filter excludes — and the failure is
    invisible, because the workflow still passes on `push: main` afterwards.

    Found on PR #1285: fourfold-warrant had been filtered to Python sources
    while its measurement table advertised "docs-only governance PR" as the
    biggest saving, i.e. the gate vanished on precisely the PRs the change was
    optimising for."""
    for filename, why in WHOLE_DIFF_GATES.items():
        doc = yaml.safe_load((WORKFLOWS / filename).read_text(encoding="utf-8"))
        stanza = _pull_request_stanza(doc)
        assert stanza is not None, f"{filename} lost its pull_request stanza"
        assert "paths" not in stanza, (
            f"{filename} carries a paths filter, but it grades the whole diff: "
            f"{why}. Every PR the filter excludes now runs no warrant at all."
        )


def test_no_contracted_check_name_comes_from_a_path_filtered_workflow() -> None:
    """A workflow-level `paths:` filter on a CONTRACTED check is not a narrowing
    — it is a permanent DEGRADED verdict.

    When the filter excludes a PR the workflow never runs, so no check appears
    in the rollup and `ci_truth.classify_check(None)` returns MISSING.
    PASS_CONCLUSIONS (ci_truth.py:20) contains SKIPPED but not MISSING, so
    evaluate_rollup records `advisory CI <id> is MISSING` and sets
    verdict = DEGRADED; the CLI exits 3. Every docs-only and dependency-only PR
    then reports degraded CI forever, and the operator report can no longer
    distinguish a broken advisory gate from an inapplicable one.

    Per-JOB filtering is the supported way to skip contracted work: the job
    reports `skipped`, and SKIPPED counts as PASS. Found on PR #1285 after five
    workflows had been filtered at the workflow level."""
    contract = json.loads(
        (REPO_ROOT / "docs" / "governance" / "CI_TRUTH_CONTRACT.json").read_text(
            encoding="utf-8"
        )
    )
    contracted: set[str] = set()
    for group in ("required", "advisory"):
        for entry in contract.get(group, []):
            contracted.update(entry.get("names", []))

    offenders = []
    for path in sorted(WORKFLOWS.glob("*.yml")):
        doc = yaml.safe_load(path.read_text(encoding="utf-8"))
        stanza = _pull_request_stanza(doc)
        if not stanza or "paths" not in stanza:
            continue
        published = {str(doc.get("name") or path.stem)}
        for job_id, job in (doc.get("jobs") or {}).items():
            published.add(str(job.get("name") or job_id))
        # matrix job names carry an expression; compare on the literal prefix.
        for name in sorted(contracted):
            base = name.split(" / ")[0]
            if name in published or base in published:
                offenders.append(f"{path.name} publishes contracted {name!r}")

    assert not offenders, (
        "these path-filtered workflows publish contracted check names, so every "
        "excluded PR reports the check as MISSING and the CI verdict as "
        f"DEGRADED: {offenders}"
    )


def test_no_filter_uses_the_slash_star_double_star_spelling() -> None:
    """`**/*.ext` may not match root-level files, and the failure is silent.

    GitHub documents `**` as "matches zero or more of any character" and gives
    `'**.js'` as the way to match a file type anywhere in the repository,
    explicitly contrasted with root-only `'*.js'`. Read literally, `**/*.py`
    requires a slash after the `**`, so it would match `pkg/mod/file.py` but
    NOT `file.py` — and `dharma_swarm/**/*.py` would miss every one of the
    package's top-level modules, which are the bulk of what
    codeowners_blast_radius.py grades.

    This repo has no `**/*.ext` precedent to learn from: every pre-existing
    filter uses the `dir/**` form. Rather than resolve the ambiguity, use the
    spelling that is correct under BOTH readings — `**.py` — and pin it here.
    An exact filename at any depth (`**/go.mod`) is fine as long as the root
    copy is listed alongside it, which is why this only rejects the wildcard
    form. (#1285 review, round 6.)"""
    offenders = []
    for path in sorted(WORKFLOWS.glob("*.yml")):
        stanza = _pull_request_stanza(yaml.safe_load(path.read_text(encoding="utf-8")))
        if not stanza or "paths" not in stanza:
            continue
        patterns = [str(p) for p in stanza["paths"]]
        for pattern in patterns:
            if "**/*" not in pattern:
                continue
            offenders.append(
                f"{path.name}: {pattern!r} may skip root-level files; "
                f"use {pattern.replace('**/*', '**')!r} instead"
            )
    assert not offenders, offenders


def test_an_exact_name_at_depth_also_lists_its_root_copy() -> None:
    """`**/go.mod` matches nested manifests but, under the same reading, not the
    root one. Pairing it with a bare `go.mod` is correct under both readings and
    stays exact — unlike `**go.mod`, which would also match `cargo.mod`."""
    offenders = []
    for path in sorted(WORKFLOWS.glob("*.yml")):
        stanza = _pull_request_stanza(yaml.safe_load(path.read_text(encoding="utf-8")))
        if not stanza or "paths" not in stanza:
            continue
        patterns = [str(p) for p in stanza["paths"]]
        for pattern in patterns:
            if not pattern.startswith("**/") or "*" in pattern[3:]:
                continue
            bare = pattern[3:]
            if bare not in patterns:
                offenders.append(
                    f"{path.name}: {pattern!r} without a bare {bare!r}, so the "
                    "root-level copy may never trigger the workflow"
                )
    assert not offenders, offenders
