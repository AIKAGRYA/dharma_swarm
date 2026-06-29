# Forge v1 — Real SWE-bench-Verified on RunPod (runbook)

The Forge measures the swarm vs best-of-N on real code-repair bugs. The test
suites run in Docker; the models are API calls. On the M5 the harness works but
**emulates** amd64 (~11 min/instance). For the **full 500-instance run** use a
native x86 box. RunPod CPU pods now support Docker — here's the path.

## 1. Provision the pod (RunPod)
- **Type:** **CPU Pod** (NOT GPU — the models are API calls, no local inference).
- **Template:** a Docker-enabled image (RunPod CPU pods support Docker runtime + network volumes).
- **Size:** **16–32 vCPU, 64–128 GB RAM**. (Epoch AI runs all 500 Verified in ~62 min on 32 core / 128 GB.)
- **Disk / network volume:** **150 GB+** (SWE-bench needs ~120 GB during a run at `--cache_level env`).
- **Arch:** x86_64 (default on RunPod CPU pods).

## 2. Get the code onto the pod
- `git clone` this lane (branch `forge-v1/tokenbroker-scoreboard-20260620`) OR copy `dharma_swarm/forge_v1/` + `scripts/runpod_swebench_setup.sh`.
- The forge_v1 package is self-contained for the SWE-bench path (swebench_real.py uses the official harness).

## 3. Keys (the only real gate besides the box)
- Export the live model key for whichever frontier you're testing:
  - `export ANTHROPIC_API_KEY=...` (for opus-4.8 — currently auth-failing locally; fix via `dkeys`/billing)
  - `export OPENAI_API_KEY=...` (gpt-5 — currently `insufficient_quota`; needs billing)
  - `export GEMINI_API_KEY=...` (works today)
- The box runs whatever patches the models produce; the models call out from the pod.

## 4. Run
```bash
bash scripts/runpod_swebench_setup.sh        # installs swebench, checks docker+disk
# then the real benchmark (strongest live model):
python -m dharma_swarm.forge_v1.run_real --n 500 --model claude-opus-4.8 \
    --namespace ghcr.io/epoch-research --cache_level env --max_workers 8
```

## 5. The speed unlock — Epoch AI prebuilt registry
Un-optimized SWE-bench images total ~2 TB and build slowly. **Epoch AI publishes a
layer-optimized registry: 30 GiB for all 500 Verified images.** Pass
`--namespace ghcr.io/epoch-research` so the harness **pulls** prebuilt images
instead of building from source → full run ≈ 1 hour instead of days.
Verify the current namespace at https://epoch.ai/latest/swebench-docker.

## Cost sketch
- RunPod CPU pod (16–32 vCPU): a few $/hr, ~1–2 hr for a full run = single-digit $.
- Model API: depends on model × 500 instances × best-of-N. opus-4.8 best-of-3 over
  500 instances is the main spend — estimate before launching; start with `--n 20`.

## Honest status (2026-06-20)
- The Forge SWE-bench adapter is **built, committed, and proven** on the M5
  (instance `psf__requests-2317` resolved via the official harness).
- Remaining for a full real number: this box + restored opus/gpt-5 quota. Until
  then, real runs execute on **Gemini** (the only live frontier key here).
