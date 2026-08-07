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
    `'' != 'false'` runs it (fail open). Only the second is safe."""
    doc = yaml.safe_load((WORKFLOWS / "tests.yml").read_text())
    offenders = []
    for name, body in doc["jobs"].items():
        condition = str(body.get("if", ""))
        if "needs.changes.outputs" not in condition:
            continue
        if "== 'true'" in condition or '== "true"' in condition:
            offenders.append(f"{name}: {condition.strip()}")
        if "always()" not in condition:
            offenders.append(f"{name}: missing always(), skips when classifier fails")
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
