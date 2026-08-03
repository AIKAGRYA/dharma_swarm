"""Behavioral contract for anti-slop Rule 2 — the SCANNER, not the config.

Why this file exists: the WP-0C1R contract tests in ``tests/test_semgrep_wrapper.py``
parse YAML, grep class names, and search source text. They proved the record,
not the thing. Under those tests Rule 2's message could promise — and for
fifteen weeks did promise — that it catches classes which "append their own
JSONL" while the rule carried zero JSONL patterns; running the merged rule
against ``dharma_swarm/forge_v1/forge_v2/receipts.py`` and
``dharma_swarm/forge_v1/tracking.py`` returned 0 findings.

Every test here RUNS semgrep against a fixture and asserts the exact set of
(line, rule-id) findings. If the scanner is not installed the tests SKIP with a
named reason; they never pass silently.

Fixture annotations (semgrep's own convention, parsed below):
    ``# ruleid: <id>``     the next line MUST produce that finding
    ``# ok: <id>``         the next line MUST NOT produce that finding
    ``# todoruleid: <id>`` a named, accepted gap: it should fire and does not
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
WRAPPER = REPO_ROOT / "scripts/governance/run_semgrep_with_ca.sh"
RULES = REPO_ROOT / ".semgrep/dharma-anti-slop.yml"
FIXTURE = REPO_ROOT / ".semgrep/tests/test_no_new_substrate.py"

RULE2 = "dharma.no-new-substrate"
RULE2B = "dharma.no-new-substrate-exempt-name-collision"

# Real modules whose ledgers the pre-2026-08-04 rule silently missed. Both were
# added AFTER the rule existed (rule 3ff53240e 2026-04-26; ledgers e1aacc0fc).
RECEIPTS_LEDGER = "dharma_swarm/forge_v1/forge_v2/receipts.py"
TRACKING_LEDGER = "dharma_swarm/forge_v1/tracking.py"

# WP-0C1R ratified exemptions (operator decision B1, 2026-08-02). These files
# must stay silent under Rule 2 or the ratified disposition is re-broken.
RATIFIED_EXEMPT_FILES = (
    "dharma_swarm/bridge_registry.py",
    "dharma_swarm/graph_store.py",
    "dharma_swarm/knowledge_units.py",
)

_ANNOTATION_RE = re.compile(r"^\s*#\s*(ruleid|ok|todoruleid):\s*([\w.\-]+)\s*$")


def _semgrep_binary() -> str | None:
    candidate = os.environ.get("DHARMA_SEMGREP_BIN") or "semgrep"
    return shutil.which(candidate)


requires_semgrep = pytest.mark.skipif(
    _semgrep_binary() is None,
    reason=(
        "semgrep binary not found (checked $DHARMA_SEMGREP_BIN then PATH) — "
        "Rule 2's behavioral contract cannot be proven on this host; it runs in "
        "the .github/workflows/semgrep.yml lane. Install: "
        'pip install "semgrep==1.168.0", or set DHARMA_SEMGREP_BIN.'
    ),
)


def _scan(*targets: str | Path) -> list[tuple[int, str]]:
    """Run the real rule file over ``targets``; return sorted (line, rule-id)."""
    proc = subprocess.run(
        [
            str(WRAPPER),
            "--config",
            str(RULES),
            "--json",
            "--quiet",
            "--metrics=off",
            *[str(t) for t in targets],
        ],
        cwd=REPO_ROOT,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        timeout=300,
    )
    assert proc.returncode == 0, f"semgrep failed ({proc.returncode}):\n{proc.stderr}"
    payload = json.loads(proc.stdout)
    assert not payload.get("errors"), f"semgrep reported errors: {payload['errors']}"
    return sorted(
        (r["start"]["line"], r["check_id"].rsplit("semgrep.", 1)[-1])
        for r in payload["results"]
    )


def _annotations() -> dict[str, list[tuple[int, str]]]:
    """Parse the fixture's ruleid/ok/todoruleid comments.

    An annotation applies to the next line that is neither blank nor a comment,
    matching semgrep's own annotation semantics.
    """
    lines = FIXTURE.read_text(encoding="utf-8").splitlines()
    out: dict[str, list[tuple[int, str]]] = {"ruleid": [], "ok": [], "todoruleid": []}
    for index, line in enumerate(lines):
        match = _ANNOTATION_RE.match(line)
        if not match:
            continue
        kind, rule_id = match.group(1), match.group(2)
        target = None
        for offset in range(index + 1, len(lines)):
            stripped = lines[offset].strip()
            if not stripped or stripped.startswith("#"):
                continue
            target = offset + 1
            break
        assert target is not None, f"annotation on line {index + 1} annotates nothing"
        out[kind].append((target, rule_id))
    return out


def test_fixture_annotations_are_present_and_wellformed():
    """Guards the guard: an emptied fixture must not silently prove nothing."""
    annotations = _annotations()
    assert len(annotations["ruleid"]) >= 15, annotations["ruleid"]
    assert len(annotations["ok"]) >= 9, annotations["ok"]
    assert annotations["todoruleid"], "the named-gap list must stay explicit"
    for kind in annotations:
        for _, rule_id in annotations[kind]:
            assert rule_id in {RULE2, RULE2B}, rule_id


@requires_semgrep
def test_rule2_findings_match_the_fixture_exactly():
    """The whole contract in one assertion: expected set == actual set."""
    expected = set(_annotations()["ruleid"])
    actual = set(_scan(FIXTURE))
    missing = expected - actual
    unexpected = actual - expected
    assert not missing, f"annotated violations the scanner did not find: {sorted(missing)}"
    assert not unexpected, (
        f"findings with no ruleid annotation (false positive or a stale "
        f"todoruleid that now fires): {sorted(unexpected)}"
    )


@requires_semgrep
def test_ok_and_todo_annotations_produce_no_finding():
    """Negative controls: exemptions, non-append modes, module-level functions,
    a filename starting with 'a', and every named gap must stay silent."""
    actual = set(_scan(FIXTURE))
    annotations = _annotations()
    for kind in ("ok", "todoruleid"):
        for line, rule_id in annotations[kind]:
            assert (line, rule_id) not in actual, (
                f"{FIXTURE.name}:{line} is annotated '{kind}: {rule_id}' but the "
                "scanner produced that finding"
                + (
                    " — a todoruleid gap was closed; promote it to ruleid"
                    if kind == "todoruleid"
                    else " — a negative control regressed into a false positive"
                )
            )


@requires_semgrep
def test_jsonl_ledgers_in_the_tree_are_now_detected():
    """The defect receipt, inverted into a regression test.

    Before this fix these two files produced 0 findings while Rule 2's message
    claimed it caught classes that "append their own JSONL". Neither class is a
    ratified exemption, so a finding is the CORRECT behavior; they are reported
    as newly-surfaced OWNER_DEFERRED items, never allowlisted away.
    """
    findings = _scan(RECEIPTS_LEDGER, TRACKING_LEDGER)
    assert findings, (
        "the JSONL ledgers regressed to 0 findings — Rule 2's message promises "
        "append-substrate detection; a silent allowlist would be the defect "
        "this test exists to prevent"
    )
    assert {rule_id for _, rule_id in findings} == {RULE2}


@requires_semgrep
def test_ratified_exemptions_stay_silent_in_the_real_tree():
    """WP-0C1R decision B1 must survive the broadened detector."""
    assert _scan(*RATIFIED_EXEMPT_FILES) == []


@requires_semgrep
def test_canonical_store_stays_excluded():
    """dharma_swarm/runtime_state.py is Rule 2's only path exclusion."""
    assert _scan("dharma_swarm/runtime_state.py") == []


@requires_semgrep
def test_synthetic_new_substrate_is_caught_in_a_ratified_file(tmp_path):
    """WP-0C1R's negative control (C), re-run behaviorally: exemptions are
    class-scoped, so a NEW substrate class added to a ratified file is caught.

    Runs on a copy — the tree is never mutated.
    """
    target = tmp_path / "graph_store_probe.py"
    target.write_text(
        (REPO_ROOT / "dharma_swarm/graph_store.py").read_text(encoding="utf-8")
        + "\n\nclass SmuggledLedger:\n"
        "    def append(self, record):\n"
        '        with open(self.path, "a") as fh:\n'
        "            fh.write(str(record))\n",
        encoding="utf-8",
    )
    findings = _scan(target)
    assert [rule_id for _, rule_id in findings] == [RULE2], findings


@requires_semgrep
def test_exempt_name_collision_needs_a_substrate_to_fire():
    """The in-tree KnowledgeStore(Protocol) collision is real but sqlite-free.
    The collision rule must stay silent on it — evidence, not name-matching.
    """
    assert _scan("dharma_swarm/engine/knowledge_store.py") == []
