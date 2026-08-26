# Benchmark Run Config — 50-instance SWE-bench-Verified swarm-vs-single (2026-08-19)

Mission ratified 2026-08-18 (yes-sheet row 1): run a 50-instance
SWE-bench-Verified swarm-vs-single benchmark under a **$200/month compute cap**,
which itself sits inside the **$500/month total burn ceiling**. This document is
the run playbook: the exact commands, the secrets needed, and where the result
gets published so the trust gate can read it.

**Plain-language framing for the operator:** we are testing whether a team of
AI models fixing real software bugs beats one strong model working alone, on 50
bugs drawn fairly in advance, without spending more than the monthly budget.

**Scope honesty, stated up front: 50 instances is a pipeline shakedown, not a
C2-clearing sample.** C2 admissibility (live seats, >=2 model families, budget
parity, significance controls — `scripts/governance/trust_gate_status.py:177-195`)
is satisfied by the harness design, but at n=50 pairs the confidence interval
will usually be too wide to promote a positive claim
(`positive_claim_gate`, `dharma_swarm/forge_v1/forge_v2/stats.py:62-72`), and
SWE-bench-Verified is marked `possible_pretrain`
(`dharma_swarm/forge_v1/forge_v2/provenance.py:40-49`), so any lift is an upper
bound until rerun on post-cutoff tasks. Expect `inconclusive_low_power` or
`measured_negative` as legitimate outcomes; the point of this run is that the
whole pipe works end to end at a known cost.

---

## 0. Budget model (read before renting anything)

Two meters, one cap:

| What | Metered by | Where |
|---|---|---|
| Model API spend (real $ + shadow $ for free routes) | `Budget` per attempt (`dharma_swarm/forge_v1/forge_v2/budget.py:37-57`), aggregated per month by `monthly_ledger.py` | `~/.dharma/forge_v1/spend/YYYY-MM.jsonl` (runtime state, never in git) |
| Box rental (RunPod etc.) | **NOT metered by the ledger** — track it in the provider's billing page | operator |

Both must fit inside the same $200/month. The runner refuses to start any run
whose **worst-case** model spend exceeds the month's remainder
(`check_run_admission`, `dharma_swarm/forge_v1/forge_v2/monthly_ledger.py`);
worst case = `--budget-usd` × instances × replicates × 2 arms
(`worst_case_run_usd`, same module). At the defaults below:

- 50 instances × 1 replicate × 2 arms × $0.25/attempt = **$25 worst case**
- with `--replicates 3` it is $75 worst case

Actual spend is recorded after the run (real + shadow dollars from every
attempt's budget) and counts against the next run's admission check.

Check the month's meter at any time:

```bash
python3 -c "from dharma_swarm.forge_v1.forge_v2.monthly_ledger import month_key, month_spend_usd, remaining_monthly_usd; import time; m=month_key(time.time()); print(m, 'spent:', round(month_spend_usd(m),2), 'remaining of 200:', round(remaining_monthly_usd(200.0, m),2))"
```

---

## 1. Pre-register the sample (BEFORE the run, commit the receipt)

The 50 instance ids are drawn by a seeded, stratified sampler — stratified by
repository AND by gold-patch size bucket (S <= 10 changed lines, M 11-40,
L > 40) so the sample cannot be cherry-picked toward easy repos or tiny
patches. Deterministic given the seed. Script:
`scripts/forge/sample_swebench_instances.py`.

On any machine where the HF `datasets` library can load
`princeton-nlp/SWE-bench_Verified` (network or local HF cache):

```bash
python3 scripts/forge/sample_swebench_instances.py \
    --n 50 --n-explore 20 --seed 20260819 \
    --dump-listing reports/governance/forge_benchmark/swebench_verified_listing.json
```

This writes the frozen sample + receipt to
`reports/governance/forge_benchmark/swebench_verified_sample_n50_seed20260819.json`
(seed, strata populations, quotas, dataset identity, listing digest, and the
frozen EXPLORE/CONFIRM split of 20/30 via
`split_explore_confirm`, `dharma_swarm/forge_v1/forge_v2/provenance.py:13-16`).

If `datasets` is unavailable the sampler prints fetch instructions and exits 3
— it never fabricates ids. Rerun later with
`--listing reports/governance/forge_benchmark/swebench_verified_listing.json`
for a fully offline draw.

**Commit both JSON files to git before the benchmark run starts.** That commit
IS the pre-registration: the instance list is on record before any result
exists, so nobody (including us) can quietly swap instances afterwards.

---

## 2. Rent and prepare the box

Native x86_64 Linux, no GPU — the models are API calls; Docker only runs the
hidden test suites. Box spec and setup are already scripted
(`scripts/runpod_swebench_setup.sh:9-12`): 16-32 vCPU, 64-128 GB RAM,
150+ GB disk, Docker-enabled RunPod CPU pod template.

```bash
git clone <this repo> dharma_swarm && cd dharma_swarm
bash scripts/runpod_swebench_setup.sh          # docker sanity, venv, swebench deps, disk check
source .venv-forge/bin/activate
```

The setup script's step 3 recommends the Epoch AI prebuilt-image registry for
direct harness runs (`scripts/runpod_swebench_setup.sh:35-41`); the forge
runner path pulls prebuilt amd64 images from the `swebench` Docker Hub
namespace by default (`DEFAULT_NAMESPACE`,
`dharma_swarm/forge_v1/swebench_real.py:71`), so no extra flag is needed.

---

## 3. Secrets and environment

Export on the box (never commit; gitleaks blocks secrets in git):

```bash
export GOOGLE_AI_API_KEY=...     # Gemini family
export ZHIPU_API_KEY=...         # GLM family (default forge generator, runner_slots.py:20)
export NVIDIA_NIM_API_KEY=...    # NIM-served family
export KIMI_API_KEY=...          # Kimi family
export DOCKER_CONTEXT=default    # on Linux; the laptop default is colima-forge-swebench (swebench_real.py:66)
export FORGE_SWEBENCH=1          # enables the live Docker grading path in gated tests
```

Key-name aliases (GEMINI_API_KEY, GLM_API_KEY, NVIDIA_API_KEY, ...) are
normalized by `dharma_swarm/api_keys.py:204-215`; the names above are the ones
the runtime expects (`dharma_swarm/api_keys.py:111-137`).

Preflight, in order:

```bash
python3 scripts/check_provider_credits.py                       # keys live?
FORGE_SWEBENCH=1 python3 -m pytest tests/test_forge_v1_swebench.py -q   # one real Docker eval (slow first pull)
```

---

## 4. The benchmark run

The runner is `dharma_swarm/forge_v1/forge_v2/runner.py` — matched budgets per
arm, paired bootstrap CI, cross-family critic gate, EXPLORE/CONFIRM split,
full receipts. Feed it the pre-registered ids in their frozen order;
`--n-explore 20` reproduces exactly the receipt's split (the receipt's
`instance_ids` is EXPLORE then CONFIRM).

```bash
IDS="$(python3 -c "import json; r=json.load(open('reports/governance/forge_benchmark/swebench_verified_sample_n50_seed20260819.json')); print(','.join(r['instance_ids']))")"

PYTHONPATH="$PWD" DOCKER_CONTEXT=default python3 -m dharma_swarm.forge_v1.forge_v2.runner \
    --instances "$IDS" \
    --n-explore 20 \
    --replicates 1 \
    --budget 60000 \
    --budget-usd 0.25 \
    --monthly-cap-usd 200 \
    --grade-timeout 1800 \
    --label swebench50_shakedown
```

Notes:

- `--monthly-cap-usd 200` (also the default) is the refuse-to-start gate: if
  the worst-case spend of this run does not fit in what is left of the month's
  $200, the runner prints the reason and exits with code 2 without making a
  single model call.
- `--replicates 1` keeps the shakedown at ~100 Docker grades (50 instances × 2
  arms). Grading is sequential in this runner, so budget several hours of
  wall-clock. Raise replicates only after the pipe is proven.
- Generator/verifier default to the pinned recent-frontier pair
  (`dharma_swarm/forge_v1/forge_v2/runner_slots.py:18-21`); the run is blocked
  with evidence if no cross-family pair is callable (`runner.py`, blocked
  branch) — that is a key problem, not a harness problem.
- Artifacts land under `~/.dharma/forge_v1/forge_v2/<label>_<timestamp>/` —
  `decision_record.json` (the run receipt: pass rates, paired lift CI,
  closeout, contamination state) and `ledger.jsonl` (per-attempt receipts).
  Copy `decision_record.json` off the box before shutting it down.

---

## 5. Publish the result (trust-gate readable)

The trust gate's C2 condition reads the newest `reports/anatomy_*` directory
whose name contains a `YYYY-MM-DD` date, scanning its `*.md` files for the
literal pattern `swarm_lift = <number>`
(`find_swarm_lift` + `_LIFT_RE`, `scripts/governance/trust_gate_status.py:109-174`).

After the run, create (in git, committed):

```
reports/anatomy_benchmark_<YYYY-MM-DD>/swebench50_shakedown.md
```

containing, verbatim from `decision_record.json` (no rounding games):

```markdown
# SWE-bench-Verified 50-instance swarm-vs-single shakedown (<date>)

Pre-registered sample: reports/governance/forge_benchmark/swebench_verified_sample_n50_seed20260819.json
Decision record: <path of the copied decision_record.json>

swarm_lift = <contrast_vs_class_null.mean>

- CI (paired bootstrap): [<lower>, <upper>], n = <n_pairs>
- closeout: <closeout>
- contamination: possible_pretrain (SWE-bench-Verified is public; lift is an upper bound)
- spend this run: $<usd + shadow_usd total>; month meter: ~/.dharma/forge_v1/spend/<YYYY-MM>.jsonl
- 50 instances is a pipeline shakedown, not a C2-clearing sample.
```

Then verify the gate actually reads it:

```bash
python3 scripts/governance/trust_gate_status.py | head -40
```

Publish the honest number whatever its sign — a negative or inconclusive lift
recorded truthfully is a valid, ship-worthy result (the same rule the runner
itself applies: a CI lower bound <= 0 is a successful run,
`dharma_swarm/forge_v1/forge_v2/runner.py:1-13`).

---

## 6. Shutdown checklist

1. Copy `decision_record.json`, `ledger.jsonl`, and the roster probe off the box.
2. Confirm the spend row landed: the meter command in §0 shows this run's total.
3. Note the box rental cost next to the model spend; both count against the $200.
4. Stop the pod. Nothing on the box is state we keep — all receipts are copied
   or already committed.
