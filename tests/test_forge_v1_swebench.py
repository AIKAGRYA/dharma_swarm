"""Tests for the REAL SWE-bench-Verified adapter (forge_v1/swebench_real.py).

Two tiers:
  * OFFLINE (always run): assert the loader/adapter SHAPE without Docker — the
    raw instance has the SWE-bench fields the harness needs, the image-key maps
    to the Docker Hub prebuilt convention, and an absent empty-patch report is
    correctly read as unresolved (the gold path is never faked).
  * LIVE (gated on env FORGE_SWEBENCH=1): actually run the official swebench
    Docker harness on one instance and assert gold->resolved, empty->unresolved.
    Skipped by default so CI / offline never triggers slow multi-GB image pulls.

Run offline-only:  PYTHONPATH=. pytest tests/test_forge_v1_swebench.py -q
Run live too:      FORGE_SWEBENCH=1 PYTHONPATH=. pytest tests/test_forge_v1_swebench.py -q
"""
import json
import os

import pytest

from dharma_swarm.forge_v1 import swebench_real

LIVE = os.environ.get("FORGE_SWEBENCH") == "1"
LIVE_INSTANCE_ID = "psf__requests-2317"


def _require_swebench_dataset_loader() -> None:
    pytest.importorskip(
        "swebench.harness.run_evaluation",
        reason="optional swebench package is not installed",
    )


# --------------------------------------------------------------------------- #
# OFFLINE shape tests — no Docker, but DO hit the HF dataset loader (cached).
# --------------------------------------------------------------------------- #
def test_verified_instances_have_required_swebench_fields():
    """A real instance must carry the fields the official harness needs: the
    repo@commit, the gold patch, the hidden test patch, and the F2P/P2P suites.
    These are exactly what makes it NOT an inline-file task."""
    _require_swebench_dataset_loader()
    insts = swebench_real.verified_instances(n=1)
    assert len(insts) == 1
    inst = insts[0]
    for key in (
        "instance_id",
        "repo",
        "base_commit",
        "patch",
        "test_patch",
        "FAIL_TO_PASS",
        "PASS_TO_PASS",
    ):
        assert key in inst, f"missing required SWE-bench field: {key}"
    # gold patch is a non-empty unified diff
    assert inst["patch"].strip(), "gold patch must be non-empty"
    assert "diff --git" in inst["patch"] or "---" in inst["patch"]
    # F2P is a real (json-encoded) list of test node ids
    f2p = inst["FAIL_TO_PASS"]
    if isinstance(f2p, str):
        f2p = json.loads(f2p)
    assert isinstance(f2p, list) and len(f2p) >= 1


def test_instance_image_key_matches_docker_hub_convention():
    """The image-key the harness will pull must follow the swebench namespace /
    `sweb.eval.x86_64.<iid>` convention — this is the amd64 prebuilt image."""
    _require_swebench_dataset_loader()
    insts = swebench_real.verified_instances(instance_ids=[LIVE_INSTANCE_ID])
    key = swebench_real.instance_image_key(insts[0])
    assert key.startswith("swebench/sweb.eval.x86_64."), key
    # __ in the instance id becomes _1776_ in the docker tag
    assert "requests-2317" in key


def test_empty_patch_with_no_report_is_unresolved_not_faked(tmp_path):
    """The empty-patch discriminator: when swebench writes no per-instance report
    for an empty patch, we read that as unresolved (False) — never as a faked
    pass. And a MISSING report for a non-empty patch must RAISE, not silently
    pass."""
    missing = tmp_path / "report.json"
    # empty patch, no report -> False (correct)
    assert swebench_real._resolved_from_report(missing, "x", empty_ok=True) is False
    # non-empty patch, no report -> refuse to fake a verdict
    with pytest.raises(RuntimeError):
        swebench_real._resolved_from_report(missing, "x", empty_ok=False)


def test_resolved_from_report_reads_official_verdict(tmp_path):
    """Verdict comes from report[instance_id]['resolved'], the official field."""
    rf = tmp_path / "report.json"
    rf.write_text(json.dumps({"abc-1": {"resolved": True}}))
    assert swebench_real._resolved_from_report(rf, "abc-1", empty_ok=False) is True
    rf.write_text(json.dumps({"abc-1": {"resolved": False}}))
    assert swebench_real._resolved_from_report(rf, "abc-1", empty_ok=False) is False


# --------------------------------------------------------------------------- #
# LIVE test — real Docker, gated on FORGE_SWEBENCH=1.
# --------------------------------------------------------------------------- #
# The repo sets a global pytest-timeout of 300s; one emulated-amd64 SWE-bench
# gold run alone takes ~700s. Override the per-test timeout so the live test
# isn't killed mid-Docker-eval. (0 = disable; we give a generous 2400s bound.)
@pytest.mark.timeout(2400)
@pytest.mark.skipif(not LIVE, reason="set FORGE_SWEBENCH=1 to run the slow Docker eval")
def test_live_gold_resolves_and_empty_fails():
    _require_swebench_dataset_loader()
    insts = swebench_real.verified_instances(instance_ids=[LIVE_INSTANCE_ID])
    inst = insts[0]
    gold_resolved = swebench_real.verify_prediction(inst, inst["patch"], timeout=1800)
    assert gold_resolved is True, "gold patch must resolve the real instance"
    empty_resolved = swebench_real.verify_prediction(inst, "", timeout=1800)
    assert empty_resolved is False, "empty patch must NOT resolve"
