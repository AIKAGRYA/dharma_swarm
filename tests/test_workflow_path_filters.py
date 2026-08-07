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
    doc = yaml.safe_load((WORKFLOWS / "tests.yml").read_text())
    offenders = []
    for name, body in doc["jobs"].items():
        condition = " ".join(str(body.get("if", "")).split())
        if "needs.changes.outputs" not in condition:
            continue
        if "== 'true'" in condition or '== "true"' in condition:
            offenders.append(f"{name}: fail-closed comparison: {condition}")
        if "!cancelled()" not in condition:
            offenders.append(
                f"{name}: missing !cancelled(), so a FAILED classifier would "
                f"skip this job instead of running it: {condition}"
            )
        if "always()" in condition:
            offenders.append(
                f"{name}: always() keeps this job running after the run is "
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


def test_the_classifier_is_reachable_from_the_workflow() -> None:
    """The `changes` job invokes a real file; a rename would silently make the
    step fail, and every consumer would then fail open to running everything —
    correct, but it would quietly undo the whole change."""
    doc = yaml.safe_load((WORKFLOWS / "tests.yml").read_text())
    steps = doc["jobs"]["changes"]["steps"]
    runs = " ".join(str(s.get("run", "")) for s in steps)
    assert "scripts/ci/classify_changed_paths.py" in runs
    assert (REPO_ROOT / "scripts" / "ci" / "classify_changed_paths.py").exists()


# Reviewed on PR #1285 (Devin, 4 valid findings). Each of these filters was
# keyed on the *topic* of its workflow rather than on the *inputs its jobs
# actually read*, so each gate stopped firing on exactly the change it exists
# to catch. The cited line is the code that consumes the path.
GATE_INPUTS: dict[str, tuple[tuple[str, str], ...]] = {
    "hermetic.yml": (
        # codeowners_blast_radius.py:68 builds the import graph over the package;
        # :224 grades it against CODEOWNERS. Filtering to lockfiles meant a PR
        # adding a heavy module, or deleting an ownership entry, ran no check.
        ("dharma_swarm/**/*.py", "codeowners_blast_radius.py:68 rglob"),
        (".github/CODEOWNERS", "codeowners_blast_radius.py:224 reads it"),
    ),
    "quality-ratchet.yml": (
        # The ratchet grades counters against this JSON and enforces
        # --max-baseline-age-days 45 on it. A PR touching only the baseline
        # matched nothing and ran no gate.
        (
            "docs/governance/hygiene/ratchet_baselines.json",
            "quality-ratchet.yml --max-baseline-age-days grades this file",
        ),
        (
            "docs/governance/hygiene/patterns/**",
            "ratchet_counters.py measure_hygiene_patterns_enforced_or_resolved "
            "globs docs/governance/hygiene/patterns/*.yaml as an UP counter, so "
            "lowering a pattern's stage is a regression",
        ),
    ),
    "semgrep.yml": (
        # --config .semgrep at semgrep.yml:54,:82,:84. Deleting a detection rule
        # must run the scanner, not silence it.
        (".semgrep/**", "semgrep.yml --config .semgrep"),
        (
            "scripts/governance/run_semgrep_with_ca.sh",
            "semgrep.yml invokes it directly",
        ),
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
    "fourfold-warrant.yml": (
        (
            ".pre-commit-config.yaml",
            "the only non-.py member of _HOT_PATHS in shakti_warrant.py:185, "
            "so **/*.py alone cannot cover the hot-path set",
        ),
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
    """GATE_INPUTS lists .pre-commit-config.yaml by hand. If a future non-.py
    entry joins _HOT_PATHS, this catches it rather than the table silently
    going stale — the AI-N4 shape (a check never exercised against the instance
    it should catch)."""
    import re

    source = (REPO_ROOT / "dharma_swarm" / "shakti_warrant.py").read_text(
        encoding="utf-8"
    )
    block = re.search(r"_HOT_PATHS = frozenset\(\s*\{(.*?)\}", source, re.DOTALL)
    assert block, "_HOT_PATHS literal not found in shakti_warrant.py"
    entries = re.findall(r'"([^"]+)"', block.group(1))
    assert entries, "no _HOT_PATHS entries parsed"

    doc = yaml.safe_load(
        (WORKFLOWS / "fourfold-warrant.yml").read_text(encoding="utf-8")
    )
    paths = list(_pull_request_stanza(doc).get("paths") or [])
    uncovered = [
        entry
        for entry in entries
        if not entry.endswith(".py") and entry not in paths
    ]
    assert not uncovered, (
        "hot paths the fourfold-warrant filter cannot see, so a PR touching "
        f"only them would skip the attestation gate: {uncovered}"
    )
