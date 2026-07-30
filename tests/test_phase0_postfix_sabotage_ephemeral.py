"""Ephemeral post-fix sabotage proof for the PR #1164 verifier refinement."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest


if (
    sys.version_info[:2] == (3, 12)
    and os.environ.get("GITHUB_ACTIONS") == "true"
    and os.environ.get("PHASE0_POSTFIX_CHILD") != "1"
):
    root = Path(__file__).resolve().parents[1]
    checker = root / "scripts/governance/check_nats_live_production_evidence.py"
    original = checker.read_text(encoding="utf-8")
    env = os.environ.copy()
    env["PHASE0_POSTFIX_CHILD"] = "1"
    env.pop("PYTHONPATH", None)
    observations: list[dict[str, object]] = []

    def run(label: str, argv: list[str], *, expect_zero: bool) -> None:
        completed = subprocess.run(
            argv,
            cwd=root,
            env=env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=600,
            check=False,
        )
        tail = "\n".join((completed.stdout or "").splitlines()[-30:])
        met = (completed.returncode == 0) if expect_zero else (completed.returncode != 0)
        observations.append(
            {
                "label": label,
                "argv": argv,
                "exit_code": completed.returncode,
                "expected": "zero" if expect_zero else "nonzero",
                "expectation_met": met,
                "tail": tail,
            }
        )
        if not met:
            raise AssertionError(json.dumps(observations, indent=2, sort_keys=True))

    try:
        run(
            "refined NATS evidence tests pass",
            [sys.executable, "-m", "pytest", "tests/test_nats_live_production_evidence.py", "-q", "--tb=short"],
            expect_zero=True,
        )

        weakened_runner = original.replace(
            "resolved_runner == canonical_runner,",
            "recorded_runner.name == CANONICAL_MATRIX_RUNNER.name,",
            1,
        )
        if weakened_runner == original:
            raise AssertionError("runner provenance mutation did not apply")
        checker.write_text(weakened_runner, encoding="utf-8")
        run(
            "alternate canonical-basename runner regression goes red",
            [
                sys.executable,
                "-m",
                "pytest",
                "tests/test_nats_live_production_evidence.py::test_common_contract_rejects_alternate_existing_runner_with_canonical_basename",
                "-q",
                "--tb=short",
            ],
            expect_zero=False,
        )
        checker.write_text(original, encoding="utf-8")

        weakened_receipt = original.replace(
            'receipt_payload.get("task_id") == row.get("task_id"),',
            'bool(receipt_payload.get("task_id")),',
            1,
        )
        if weakened_receipt == original:
            raise AssertionError("semantic receipt mutation did not apply")
        checker.write_text(weakened_receipt, encoding="utf-8")
        run(
            "semantic receipt identity regression goes red",
            [
                sys.executable,
                "-m",
                "pytest",
                "tests/test_nats_live_production_evidence.py",
                "-q",
                "--tb=short",
                "-k",
                "happy_path_rejects_semantic_receipt_identity_mismatch and task_id",
            ],
            expect_zero=False,
        )
    finally:
        checker.write_text(original, encoding="utf-8")

    restored = subprocess.run(
        ["git", "diff", "--exit-code", "--", str(checker.relative_to(root))],
        cwd=root,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    observations.append(
        {
            "label": "checker restored byte-for-byte",
            "exit_code": restored.returncode,
            "expected": "zero",
            "expectation_met": restored.returncode == 0,
            "tail": restored.stdout,
        }
    )
    print("PHASE0_POSTFIX_SABOTAGE_BEGIN")
    print(json.dumps(observations, indent=2, sort_keys=True))
    print("PHASE0_POSTFIX_SABOTAGE_END")
    if restored.returncode != 0:
        raise AssertionError("checker was not restored")
    raise RuntimeError("PHASE0_POSTFIX_SABOTAGE_COMPLETE")


@pytest.mark.timeout(30)
def test_phase0_postfix_sabotage_ephemeral() -> None:
    pytest.skip("post-fix sabotage executes in the isolated Python 3.12 collection lane")
