#!/usr/bin/env bash
# Forge v1 — RunPod (or any native amd64 Linux) SWE-bench-Verified runner setup.
#
# WHY: SWE-bench's Docker harness runs the hidden TEST SUITES in containers. The
# MODELS (opus-4.8/gpt-5/gemini) are API calls — NO GPU needed. On the M5 the
# harness works but emulates amd64 (~11 min/instance); a native x86 box runs the
# full 500-instance Verified set in ~1 hour. This script provisions that box.
#
# BOX SPEC (RunPod CPU pod, Docker template):
#   - x86_64 (amd64) Linux, NO GPU
#   - 16-32 vCPU, 64-128 GB RAM, 150+ GB disk (SWE-bench min: 8 CPU/16GB/120GB)
#   - RunPod "CPU pod" now supports Docker runtime + network volumes (2025 upgrade)
#
# USAGE (on the pod, after `git clone` the forge lane / copy dharma_swarm/forge_v1):
#   export FORGE_MODEL_KEY=...            # the live model key (ANTHROPIC/OPENAI/GEMINI)
#   bash scripts/runpod_swebench_setup.sh
#   # then: python -m dharma_swarm.forge_v1.run_real   (or the harness directly)
set -euo pipefail

echo "[1/5] sanity: native amd64 + docker"
ARCH="$(uname -m)"
[ "$ARCH" = "x86_64" ] || { echo "WARN: arch=$ARCH (not x86_64). SWE-bench images are amd64 — native x86 strongly preferred."; }
docker info >/dev/null 2>&1 || { echo "ERROR: docker daemon not reachable. On RunPod pick a Docker-enabled CPU pod template."; exit 1; }
docker run --rm hello-world >/dev/null 2>&1 && echo "  docker OK"

echo "[2/5] python venv + deps"
PYBIN="${PYBIN:-python3}"
"$PYBIN" -m venv .venv-forge 2>/dev/null || true
# shellcheck disable=SC1091
source .venv-forge/bin/activate
pip install -q --upgrade pip
pip install -q swebench datasets anthropic openai google-generativeai
python -c "import swebench; print('  swebench', swebench.__version__)"

echo "[3/5] pre-pull the Epoch AI optimized image registry (KEY SPEEDUP)"
# Epoch AI publishes a layer-optimized registry: 30 GiB for ALL 500 Verified
# images (vs ~2 TB un-optimized). Pulling these once makes the full run ~62 min.
# Registry: ghcr.io/epoch-research/sweb-*  (see epoch.ai/latest/swebench-docker)
echo "  -> pass --namespace ghcr.io/epoch-research (or the current Epoch namespace)"
echo "     to run_evaluation so it PULLS prebuilt images instead of building from source."
echo "     Verify the current namespace at https://epoch.ai/latest/swebench-docker"

echo "[4/5] disk headroom check"
AVAIL_GB="$(df -BG --output=avail . | tail -1 | tr -dc '0-9')"
echo "  available: ${AVAIL_GB}GB (need >=120GB for env-cache; >=150GB comfortable)"
[ "${AVAIL_GB:-0}" -ge 120 ] || echo "  WARN: <120GB free — use --cache_level env and a network volume."

echo "[5/5] ready. Run the real benchmark:"
cat <<'RUN'
  # Forge wrapper on selected Verified instances (set provider keys first):
  python -m dharma_swarm.forge_v1.run_real \
      --instances django__django-12209 sympy__sympy-22914 \
      --best-of-n 3 --budget 20000 --grade-timeout 1800 \
      --swarm-second-model glm-5.2

  # Or directly via the official harness on a predictions file:
  python -m swebench.harness.run_evaluation \
      --dataset_name princeton-nlp/SWE-bench_Verified \
      --predictions_path preds.jsonl --run_id forge_v1 \
      --namespace ghcr.io/epoch-research --cache_level env --max_workers 8
RUN
echo "DONE. Models are API calls — ensure FORGE_MODEL_KEY / provider keys are exported."
