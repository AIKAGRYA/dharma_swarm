"""Ephemeral transport for the independent PR #1164 triple-check.

This file is deliberately removed after its GitHub-hosted Python 3.11 run has
produced the raw command ledger.  The audited checkout is a detached worktree at
the pre-harness candidate SHA, so this transport cannot certify itself.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest


CANDIDATE_SHA = "e4b74411c21efa47c635b29517a8798e99d0e77c"
BASE_SHA = "e891baa59baab3815d3de44806ff3137d33cd321"


@pytest.mark.timeout(20_000)
def test_phase0_triple_check_ephemeral() -> None:
    if sys.version_info[:2] != (3, 11):
        pytest.skip("independent triple-check is pinned to the Python 3.11 compatibility lane")
    if os.environ.get("GITHUB_ACTIONS") != "true":
        pytest.skip("ephemeral transport runs only on the clean GitHub-hosted verifier")

    controller = Path(__file__).resolve().parents[1]
    runner = controller / "scripts/governance/phase0_triple_check_ephemeral.py"
    runner_temp = Path(os.environ["RUNNER_TEMP"])
    target = runner_temp / "phase0-triple-check-target"
    out = runner_temp / "phase0-triple-check-artifacts"
    shutil.rmtree(target, ignore_errors=True)
    shutil.rmtree(out, ignore_errors=True)
    out.mkdir(parents=True)

    subprocess.run(
        ["git", "worktree", "add", "--detach", str(target), CANDIDATE_SHA],
        cwd=controller,
        check=True,
        text=True,
    )

    env = os.environ.copy()
    env.pop("PYTHONPATH", None)
    env.update(
        {
            "OPENROUTER_API_KEY": "sk-or-stub",
            "ANTHROPIC_API_KEY": "sk-ant-stub",
            "TINY_ROUTER_BACKEND": "heuristic",
            "DHARMA_EVOLUTION_SHADOW": "1",
            "DGC_AUTONOMY_LEVEL": "0",
            "AGENTOPS_REPORT_ROOT": str(runner_temp / "dharma-agentops-triple-check"),
            "DHARMA_OPS_DIR": str(runner_temp / "dharma-ops-triple-check"),
            "TMPDIR": str(runner_temp / "dharma-tmp-triple-check"),
        }
    )
    for key in ("AGENTOPS_REPORT_ROOT", "DHARMA_OPS_DIR", "TMPDIR"):
        Path(env[key]).mkdir(parents=True, exist_ok=True)

    old_umask = os.umask(0o022)
    try:
        completed = subprocess.run(
            [
                sys.executable,
                str(runner),
                "--repo",
                str(target),
                "--out",
                str(out),
                "--target-sha",
                CANDIDATE_SHA,
                "--base-sha",
                BASE_SHA,
            ],
            cwd=controller,
            env=env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=19_000,
            check=False,
        )
    finally:
        os.umask(old_umask)

    print("\n===== PHASE0_TRIPLE_CHECK_CONTROLLER_OUTPUT =====")
    print(completed.stdout)
    summary_path = out / "summary.json"
    if summary_path.is_file():
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        print("===== PHASE0_TRIPLE_CHECK_SUMMARY =====")
        print(json.dumps(summary, indent=2, sort_keys=True))
        print("===== PHASE0_TRIPLE_CHECK_LOG_TAILS =====")
        for case in summary.get("cases", []):
            log_path = out / case["log"]
            print(f"\n--- {case['name']} :: {case['log']} ---")
            if not log_path.is_file():
                print("MISSING LOG")
                continue
            lines = log_path.read_text(encoding="utf-8", errors="replace").splitlines()
            print("\n".join(lines[-50:]))
    else:
        print("MISSING SUMMARY", summary_path)

    try:
        subprocess.run(
            ["git", "worktree", "remove", "--force", str(target)],
            cwd=controller,
            check=False,
            text=True,
        )
    finally:
        shutil.rmtree(target, ignore_errors=True)

    assert completed.returncode == 0, (
        f"independent triple-check returned {completed.returncode}; "
        "see PHASE0_TRIPLE_CHECK_SUMMARY and command log tails above"
    )
