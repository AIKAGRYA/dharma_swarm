"""Forge v1 — REAL SWE-bench-Verified verifier (the L3 flip).

The offline `swebench.py` fixtures are inline files run by the inline `verify()`.
Real SWE-bench-Verified tasks are NOT inline files: each is a repo@commit plus a
HIDDEN FAIL_TO_PASS / PASS_TO_PASS suite that only exists inside the instance's
Docker image. So we do NOT force them into `harness.verify()`. Instead this
module exposes a thin adapter over the OFFICIAL swebench evaluation harness:

  - `verified_instances(n)`  : load raw SWE-bench-Verified instances (HF dataset
                               `princeton-nlp/SWE-bench_Verified`).
  - `verify_prediction(instance, model_patch)` : run swebench's own evaluation
                               entrypoint (`swebench.harness.run_evaluation.main`)
                               in Docker — build/pull the instance's amd64 image,
                               apply the patch, run the hidden tests, parse the
                               official report — and return the real resolved
                               verdict (bool).

We reuse swebench's `main()` rather than reimplementing image build / patch
apply / test parsing. The only thing we own is: marshalling one prediction into
the predictions-file shape swebench expects, isolating swebench's relative
`logs/` artifacts into a gitignored scratch dir, and reading `resolved` out of
the per-instance `report.json`.

Notes that bit us / will bite a re-runner:
  * swebench writes artifacts to RELATIVE `logs/run_evaluation/...` and
    `logs/build_images/...` under the *current working directory*. We chdir into
    a scratch dir under ~/.dharma for the duration of the run so nothing lands
    in the repo. (No env override exists in swebench 4.x — the constants are
    hard-coded relative Paths.)
  * SWE-bench publishes prebuilt amd64 instance images on Docker Hub under the
    `swebench` namespace (e.g. `swebench/sweb.eval.x86_64.psf_1776_requests-2317`).
    Passing `namespace="swebench"` makes the harness PULL these instead of doing
    a slow local emulated build. This is the difference between minutes and tens
    of minutes on Apple-silicon amd64 emulation.
  * On non-Linux (macOS) the harness skips the RLIMIT_NOFILE bump; that's fine.

SWEBENCH_NOTES — honest hardware finding (2026-06-20, M5 128GB via colima+qemu):
  The OFFICIAL harness is FUNCTIONAL on this box: the prebuilt amd64 image pulls,
  the container runs under qemu-x86_64, the hidden FAIL_TO_PASS/PASS_TO_PASS suite
  executes, and the verdict parses. A full smoke run discriminated correctly on
  psf__requests-2317 (gold -> resolved=True in ~688s; empty -> resolved=False).
  BUT emulated amd64 makes full-scale runs IMPRACTICAL here:
    - First-time image PULL of one ~3.6GB instance image takes ~tens of minutes.
    - Under qemu the Python test suite runs at a tiny fraction of native CPU, so
      a single instance eval is ~11-12 min wall-clock — and instances whose tests
      make LIVE NETWORK calls (e.g. parts of the `requests` suite) can stall/hang
      in the sandboxed emulated container rather than failing fast.
  Conclusion: this adapter is correct and will run at scale on a NATIVE amd64
  host (a cloud Linux/x86_64 box). On this Apple-silicon M5 it is suitable for
  one-off proofs, not for benchmarking the full SWE-bench-Verified set. The live
  Docker path is therefore kept behind FORGE_SWEBENCH=1 in tests so offline/CI
  never pays the emulation cost.
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

DATASET_NAME = "princeton-nlp/SWE-bench_Verified"
SPLIT = "test"

# Docker Hub namespace that hosts prebuilt amd64 instance images. Setting this
# makes swebench PULL prebuilt images instead of building locally (huge speedup
# on emulated amd64). Set to None to force a local build instead.
DEFAULT_NAMESPACE = "swebench"

# All swebench artifacts (logs, build dirs, predictions files, reports) live
# here — OUTSIDE the repo, so they are never committed. The state dir is
# resolved through the canonical helper (honors DHARMA_HOME-style overrides),
# is gitignored at the repo level, and lives on a different tree entirely.
from dharma_swarm.daemon_config import dharma_state_dir  # noqa: E402

SCRATCH_ROOT = dharma_state_dir() / "forge_v1" / "swebench_runs"


def _ensure_docker_host() -> None:
    """swebench uses the Python Docker SDK (`docker.from_env()`), which defaults
    to /var/run/docker.sock and ignores `docker context`. On this machine Docker
    is served by a colima profile at a non-default socket. If DOCKER_HOST is
    unset, resolve it from the active `docker context` so the SDK finds the
    daemon the CLI is already using."""
    if os.environ.get("DOCKER_HOST"):
        return
    import json as _json
    import subprocess as _sp

    try:
        out = _sp.run(
            ["docker", "context", "inspect"],
            capture_output=True,
            text=True,
            timeout=20,
        )
        if out.returncode == 0:
            data = _json.loads(out.stdout)
            host = data[0]["Endpoints"]["docker"]["Host"]
            if host:
                os.environ["DOCKER_HOST"] = host
    except (OSError, KeyError, IndexError, json.JSONDecodeError) as e:
        # Leave DOCKER_HOST unset; swebench will raise a clear DockerException.
        print(f"[swebench] unable to infer DOCKER_HOST from docker context: {e}", flush=True)


def verified_instances(n: int = 1, instance_ids: list[str] | None = None) -> list[dict[str, Any]]:
    """Return up to `n` raw SWE-bench-Verified instances (dicts).

    Each instance has at least: instance_id, repo, base_commit, patch (the gold
    fix), test_patch, FAIL_TO_PASS, PASS_TO_PASS, environment_setup_commit.

    If `instance_ids` is given, load exactly those (ignores n). swebench's loader
    pulls the HF dataset and caches it locally on first call.
    """
    from swebench.harness.run_evaluation import load_swebench_dataset

    ds = load_swebench_dataset(DATASET_NAME, SPLIT, instance_ids=instance_ids)
    instances = [dict(i) for i in ds]
    if instance_ids is None:
        instances = instances[:n]
    return instances


def instance_image_key(instance: dict[str, Any], namespace: str | None = DEFAULT_NAMESPACE) -> str:
    """The Docker image the harness will pull/build for this instance. Useful for
    pre-warming the cache or asserting an image is available before a run."""
    from swebench.harness.run_evaluation import make_test_spec

    spec = make_test_spec(instance, namespace=namespace, instance_image_tag="latest")
    return spec.instance_image_key


def verify_prediction(
    instance: dict[str, Any],
    model_patch: str,
    *,
    namespace: str | None = DEFAULT_NAMESPACE,
    timeout: int = 1800,
    force_rebuild: bool = False,
    run_id: str | None = None,
    keep_logs: bool = True,
    max_workers: int = 1,
) -> bool:
    """Run the OFFICIAL swebench Docker evaluation for ONE (instance, patch) and
    return the real resolved verdict.

    The verdict comes from swebench's per-instance ``report.json`` and is never
    self-reported.  This delegates to ``verify_predictions`` so the single-item
    path and batch path cannot drift.
    """
    results = verify_predictions(
        [(instance, model_patch)],
        namespace=namespace,
        timeout=timeout,
        force_rebuild=force_rebuild,
        run_id=run_id,
        keep_logs=keep_logs,
        max_workers=max_workers,
    )
    return bool(results[instance["instance_id"]])


def verify_predictions(
    predictions: list[tuple[dict[str, Any], str]],
    *,
    namespace: str | None = DEFAULT_NAMESPACE,
    timeout: int = 1800,
    force_rebuild: bool = False,
    run_id: str | None = None,
    keep_logs: bool = True,
    max_workers: int = 1,
) -> dict[str, bool]:
    """Run official SWE-bench Docker evaluation for a batch of predictions.

    This is the throughput seam used by the Forge/RSI grade queue: one
    predictions file, one swebench harness invocation, and ``max_workers``
    controls the harness' internal parallelism. Verdicts still come only from
    official per-instance ``report.json`` files.
    """
    if not predictions:
        return {}
    instance_ids = [instance["instance_id"] for instance, _patch in predictions]
    if len(set(instance_ids)) != len(instance_ids):
        raise ValueError("verify_predictions requires unique instance_id values per batch")

    # Import here so the module imports cleanly even without Docker/swebench env.
    from swebench.harness.run_evaluation import main as swebench_main
    from swebench.harness.constants import RUN_EVALUATION_LOG_DIR

    _ensure_docker_host()

    if run_id is None:
        first_id = predictions[0][0]["instance_id"]
        run_id = f"forge_v1_batch_{first_id}_{int(time.time())}"
    model_name = "forge_batch"

    SCRATCH_ROOT.mkdir(parents=True, exist_ok=True)
    work_dir = SCRATCH_ROOT / run_id
    work_dir.mkdir(parents=True, exist_ok=True)

    prediction_rows = [
        {
            "instance_id": instance["instance_id"],
            "model_patch": model_patch,
            "model_name_or_path": model_name,
        }
        for instance, model_patch in predictions
    ]
    preds_path = work_dir / "predictions.json"
    preds_path.write_text(json.dumps(prediction_rows))

    prev_cwd = Path.cwd()
    os.chdir(work_dir)
    try:
        eff_force_rebuild = force_rebuild and namespace is None
        swebench_main(
            dataset_name=DATASET_NAME,
            split=SPLIT,
            instance_ids=instance_ids,
            predictions_path=str(preds_path),
            max_workers=max(1, int(max_workers)),
            force_rebuild=eff_force_rebuild,
            cache_level="env",
            clean=False,
            open_file_limit=4096,
            run_id=run_id,
            timeout=timeout,
            namespace=namespace,
            rewrite_reports=False,
            modal=False,
            report_dir=str(work_dir),
        )
        resolved: dict[str, bool] = {}
        for instance, model_patch in predictions:
            instance_id = instance["instance_id"]
            report_file = (
                Path(RUN_EVALUATION_LOG_DIR)
                / run_id
                / model_name.replace("/", "__")
                / instance_id
                / "report.json"
            )
            resolved[instance_id] = _resolved_from_report(
                report_file,
                instance_id,
                empty_ok=(model_patch == ""),
            )
    finally:
        os.chdir(prev_cwd)
        if not keep_logs:
            import shutil

            shutil.rmtree(work_dir, ignore_errors=True)
    return resolved

def _resolved_from_report(report_file: Path, instance_id: str, *, empty_ok: bool) -> bool:
    """Read `resolved` out of the official per-instance report.json.

    For an empty patch swebench may short-circuit before writing a per-instance
    report.json (it's classified empty in make_run_report). If empty_ok and the
    file is absent, an empty patch is correctly unresolved -> False.
    """
    if not report_file.exists():
        if empty_ok:
            return False
        raise RuntimeError(
            f"swebench produced no report at {report_file} for {instance_id}; "
            "image build/pull or infra likely failed — refusing to fake a verdict."
        )
    content = report_file.read_text().strip()
    if not content:
        if empty_ok:
            return False
        raise RuntimeError(f"empty report.json at {report_file} for {instance_id}")
    report = json.loads(content)
    return bool(report.get(instance_id, {}).get("resolved", False))
