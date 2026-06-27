---
title: Learned Auditable Orchestrator Spec
path: docs/architecture/LEARNED_AUDITABLE_ORCHESTRATOR_SPEC.md
slug: learned-auditable-orchestrator-spec
doc_type: reference
status: draft
summary: Verified primary-source engineering details from TRINITY, Conductor, VentureBeat, and Sakana Fugu artifacts for learned/auditable orchestration build planning.
source:
  provenance: external_research_synthesis
  kind: reference
  origin_signals:
    - https://arxiv.org/abs/2512.04695
    - https://arxiv.org/pdf/2512.04695
    - https://arxiv.org/abs/2512.04388
    - https://openreview.net/forum?id=U23A2BUKYt
    - https://openreview.net/pdf?id=U23A2BUKYt
    - https://venturebeat.com/orchestration/how-sakana-trained-a-7b-model-to-orchestrate-gpt-5-claude-sonnet-4-and-gemini-2-5-pro
    - https://github.com/SakanaAI/fugu
  cited_urls:
    - https://arxiv.org/abs/2512.04695
    - https://arxiv.org/pdf/2512.04695
    - https://arxiv.org/abs/2512.04388
    - https://openreview.net/forum?id=U23A2BUKYt
    - https://openreview.net/pdf?id=U23A2BUKYt
    - https://venturebeat.com/orchestration/how-sakana-trained-a-7b-model-to-orchestrate-gpt-5-claude-sonnet-4-and-gemini-2-5-pro
    - https://github.com/SakanaAI/fugu
  generated_hint: human_or_agent_authored_repo_doc
  fetched_at: '2026-06-22T00:00:00+09:00'
disciplines:
  - multi_agent_systems
  - software_architecture
  - research_synthesis
  - verification
inspiration:
  - learned_orchestration
  - sakana_trinity
  - sakana_conductor
  - sakana_fugu
connected_relevant_files:
  - dharma_swarm/evolution.py
  - docs/architecture/DARWIN_ENGINE_QUICK_START_GUIDE.md
  - docs/architecture/MODEL_ROUTING_CANON.md
  - docs/architecture/ORCHESTRATOR_LEDGERS.md
improvement:
  room_for_improvement:
    - Convert these verified deltas into an implementation ADR before runtime authority.
    - Replace temp artifact paths with repo-pinned receipts if this becomes a build contract.
---

# Learned Auditable Orchestrator Spec

Role: reference / collaborator handoff. This file is not runtime authority until promoted by ADR or active build spec.

## Verified paper details (collaborator handoff)

### Fetch receipt

Primary-source artifacts fetched to `/private/tmp/fugu_sources/` on 2026-06-22 Asia/Tokyo.

| Artifact | Local path | SHA-256 |
|---|---|---|
| TRINITY PDF | `/private/tmp/fugu_sources/trinity.pdf` | `54f1e8dc1a4735a947743cd4aaf473c804becc42a12145cc297967b4796e56b7` |
| TRINITY arXiv source | `/private/tmp/fugu_sources/trinity_src.tar` | `7974dcefa9992d07751e94a2f8f883b69d40775caf8cc04160cdf05af08f2543` |
| Conductor arXiv PDF | `/private/tmp/fugu_sources/conductor_arxiv.pdf` | `db4dca59a25206cc94da1b491d082e01bcd849e3756ee164e3cfb8aac6772a6b` |
| Conductor arXiv source | `/private/tmp/fugu_sources/conductor_src.tar` | `bf625b73037f2a6ad9290ef83262f28b3095df1b951d97074fafa4fca5ff4cf4` |
| Conductor OpenReview PDF | `/private/tmp/fugu_sources/conductor_openreview.pdf` | `26004a6dfe21737c0a69638ce6483ddde352003dba81227404da607ee05ebf7e` |
| Fugu technical report | `/private/tmp/fugu_sources/fugu_report.pdf` | `00a0e5065551c80c12a019018e18d8365cc3da229303f1765aa49fdf22876ce2` |
| Fugu repo archive/configs | `/private/tmp/fugu_sources/fugu_configs.zip` and `/private/tmp/fugu_sources/fugu_zip/fugu-main/configs/` | `1303b7e1828e349697032a80508c5a881f7708420e18c720febc257c7a9b6b5f` |
| VentureBeat article snapshot | `/private/tmp/fugu_sources/venturebeat_jina.md` | `ef35bbaebe91a444f17551ef68239c178c5284e6502940a4656a4a37ab12f12b` |

Note: direct `venturebeat.com` fetch returned a Vercel security checkpoint / 429. The readable article text was fetched through a Jina Reader snapshot and cross-checked against the Conductor paper where it reported benchmark numbers.

### A. Conductor — exact engineering details

#### A1. Workflow-step schema and serialization

The Conductor does **not** serialize the plan as JSON in the paper. It emits text after its reasoning, then the workflow is parsed as three same-length Python lists:

```python
model_id = [2, 0]
subtasks = [
  "Develop an efficient algorithm to count the number of complete subarrays of an array",
  "Implement the algorithm described by the previous agent in Python"
]
access_list = [[], ["all"]]
```

Published schema facts:

- `model_id`: integer worker IDs in step order.
- `subtasks`: natural-language prompts/instructions in step order.
- `access_list`: per-step visibility over prior routing messages.
- `[]`: current worker sees no previous routing steps.
- `["all"]`: current worker sees all previous routing messages.
- Alternate fine-grained topology ablation: `[0,2,3]` can make visible outputs at specific prior positions; this generalized form did **not** materially beat the simple `[]` / `"all"` scheme in reported ablations.

The prompt-format contract shown in the paper includes these required names exactly:

```text
model_id
subtasks
access_list
```

Execution semantics:

- The first selected model receives the user question plus its assigned subtask.
- Later models receive the prior subtask/assistant-response message history selected by that step's `access_list`.
- The final model's answer is returned to the user.
- Available models are passed as ordinal entries such as `Model 0`, `Model 1`, not by provider name, to reduce prior-name bias during exploration.

Recursive prompt termination convention:

```python
model_id = []
subtasks = []
access_list = []
```

This means the previous final response is accepted and returned as-is.

#### A2. GRPO objective, reward, baseline, KL, and credit assignment

The paper uses the GRPO objective exactly in this form:

```tex
J(\theta)=
\mathbb{E}_{q\sim D,\, \{o\}^G_1\sim\pi_\theta(\cdot\mid q)}
\left[
\frac{1}{G}\sum_{i=1}^G
\Big(
\min\!\big(
r_i A_i,\;
\mathrm{clip}(r_i,\,1-\epsilon,\,1+\epsilon)\,A_i
\big)
-\beta\,\mathbb{D}_{\mathrm{KL}}(\pi_\theta\,\|\,\pi_{\text{ref}})
\Big)
\right]
```

Advantage normalization:

```tex
A_i=\frac{r_i-\mathrm{mean}(\{r_1,\dots,r_G\})}{\mathrm{std}(\{r_1,\dots,r_G\})}.
```

Conductor-specific reward is terminal/final, not per-step:

| Condition | Reward |
|---|---:|
| Cannot parse Python lists of `subtasks`, worker IDs, and `access_list` | `0` |
| Well-formatted workflow final output matches solution `s_i` | `1` |
| Well-formatted workflow final output does not match `s_i` | `0.5` |

Training hyperparameters published for the arXiv Conductor:

| Field | Value |
|---|---|
| Base model | `Qwen2.5-7B` |
| Max Conductor completion length | `1024` |
| Iterations | `200` |
| Questions per iteration | `4` |
| Rollouts per question / GRPO group size | `64` |
| Effective batch size | `256` |
| Temperature | `1.0` |
| Optimizer | `AdamW` |
| AdamW β1 / β2 | `0.9` / `0.999` |
| GRPO clip epsilon as reported | `0.2` |
| Base LR | `0.000001` |
| LR schedule | cosine, warmup ratio `0.03` |
| Reference-model sync | disabled |
| KL penalty | `0` |
| Entropy term | not published / not present in objective |
| GPUs | `2 NVIDIA H100 80GB GPUs` |

Cost penalty finding: the fetched arXiv/OpenReview paper and Fugu technical report do **not** publish an explicit reward term of the form `correctness - λ * cost`. Cost is handled operationally through max workflow length, constrained evaluation settings, token/reasoning budgets, and efficiency reporting. If our GRPO planner plan includes a cost penalty, that is a local extension, not a copied Conductor objective.

Recursive credit assignment:

| Field | Value |
|---|---|
| Recursive finetune iterations | `20` |
| Recursive finetune data | `350` samples: `175 LiveCodeBench` + `175 RLPR` |
| Rollouts per sample | `64` |
| Batch size | `256` |
| KL / reference sync | none |
| Initial non-recursive round discount | `0.25` |
| Round handling | rewards normalized across rounds |

#### A3. Randomized-agent-pool procedure

Published algorithmic procedure:

```text
randomly sampled k-model subset from the larger total pool of n workers
```

Exact `k` is not specified in the paper text/source beyond `k <= n`. The main full pool has `n = 7` workers. Evaluation user cases restrict to closed-only and open-only subsets after finetuning.

Main Conductor worker pool (`n=7`):

1. `Gemini-2.5-Pro`
2. `Claude-Sonnet-4`
3. `GPT-5`
4. `DeepSeek-R1-Distill-Qwen-32B`
5. `Gemma3-27B-instruct`
6. `Qwen3-32B`
7. `Qwen3-32B` reasoning / thinking mode

#### A4. Context format and inference/synthesis loop

Worker-agent settings in constrained evaluation:

| Field | Value |
|---|---|
| Worker max completion tokens | `4096` |
| Worker decode temperature | `0.2` |
| Gemini reasoning minimum | `128` tokens |
| Claude reasoning minimum | `0` |
| GPT-5 reasoning | `minimal` |
| Qwen3-32B top-p | `0.8` |
| Qwen3-32B top-k | `20` |
| Qwen3-32B presence penalty | `1.0` |

Unconstrained evaluation budgets:

| Model | Max completion tokens | Reasoning budget |
|---|---:|---|
| Gemini Pro 2.5 | `65535` | `32768` |
| Claude Sonnet 4 | `64000` | `32768` |
| GPT 5 | `128000` | `high` |
| R1-Distill-Qwen-32B | `20480` | `N.A` |
| gemma-3-27b-it | `20480` | `N.A` |
| Qwen3-32B (thinking) | `20480` | `enabled` |
| Qwen3-32B | `20480` | `N.A` |

Inference loop:

1. Conductor receives user question and available numbered model list/metadata.
2. Conductor emits up to 5 workflow steps as `model_id`, `subtasks`, `access_list`.
3. Runtime parses those Python lists.
4. Runtime executes steps sequentially.
5. Each worker gets only the user question plus its subtask plus allowed prior subtask/assistant response messages.
6. Final worker output is returned, unless recursive mode makes another Conductor call.
7. Recursive mode caps recursion depth; empty lists return previous answer.

Fugu-Ultra engineering extension from the technical report: intra-workflow function-call trajectories are isolated by agent; an agent observes another agent's actions/outputs only through the `access_list`, while inter-workflow shared memory persists across the multi-turn conversation.

#### A5. Conductor benchmark numbers and ablations

Unconstrained Conductor comparison:

| Model | M500 | MMLU | RLPR | LCB | AIME25 | BCB | GPQA-D | Avg. |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| gemma-3-27b-it | 39.8 | 81.3 | 16.67 | 13.14 | 20.7 | 14.86 | 38.4 | 32.12 |
| Qwen3-32B | 73.5 | 83.5 | 31.00 | 21.21 | 20.0 | 30.41 | 64.1 | 53.81 |
| Qwen3-32B (thinking) | 80.7 | 84.1 | 37.25 | 25.86 | 72.9 | 28.38 | 66.8 | 56.57 |
| R1-Distill-Qwen-32B | 82.5 | 84.4 | 33.50 | 26.86 | 63.0 | 33.07 | 58.1 | 54.49 |
| Claude Sonnet 4 | 96.0 | 91.4 | 36.70 | 46.54 | 74.3 | 37.16 | 77.7 | 65.69 |
| Gemini 2.5 Pro | 96.0 | 92.4 | 40.55 | 67.24 | 78.3 | 37.51 | 84.8 | 70.97 |
| GPT 5 | 99.0 | 93.5 | 42.20 | 82.90 | 90.8 | 32.75 | 82.3 | 74.78 |
| Conductor | 99.4 | 94.1 | 44.75 | 83.93 | 93.3 | 37.86 | 87.5 | 77.27 |

Controlled in-distribution comparison:

| Model / baseline | MATH500 | MMLU | RLPR | LiveCodeBench | Avg. |
|---|---:|---:|---:|---:|---:|
| Gemini Pro 2.5 (4K/128) | 85.30 ± 1.42 | 91.53 ± 0.26 | 39.57 ± 1.50 | 40.14 ± 2.20 | 64.14 |
| Claude Sonnet 4 | 82.90 ± 1.59 | 90.66 ± 1.01 | 32.60 ± 0.35 | 38.00 ± 1.50 | 61.04 |
| GPT 5 (4K/minimal) | 74.45 ± 2.19 | 89.79 ± 0.65 | 33.13 ± 1.29 | 57.50 ± 2.32 | 63.72 |
| MASRouter | 80.60 ± 0.89 | 86.28 ± 2.77 | 32.80 ± 4.77 | 27.86 ± 3.24 | 56.89 |
| MoA | 83.10 ± 2.65 | 88.46 ± 0.76 | 38.37 ± 0.95 | 38.57 ± 3.50 | 62.13 |
| RouterDC | 59.25 ± 4.22 | 87.52 ± 0.06 | 27.53 ± 2.22 | 35.33 ± 2.34 | 52.41 |
| Smoothie (Independent) | 76.85 ± 1.74 | 83.28 ± 0.16 | 34.35 ± 0.80 | 31.21 ± 2.02 | 56.42 |
| Smoothie (Dependent) | 76.95 ± 2.06 | 83.56 ± 0.27 | 34.45 ± 0.67 | 31.00 ± 2.04 | 56.48 |
| Conductor | 89.33 ± 0.58 | 93.14 ± 0.36 | 42.63 ± 0.65 | 64.29 ± 2.01 | 72.35 |

Cost-efficiency tables:

| Model | Performance | Token usage | Avg. cost / cost |
|---|---:|---:|---:|
| Conductor vs 5× consensus/reflect on MMLU | 93.14 | 735.2 | 0.009 |
| MoA | 62.13 | 11203 | 0.04855 |
| Smoothie | 56.48 | 9909 | 0.03929 |
| RDC | 52.41 | 840 | 0.00561 |
| MasRouter | 56.89 | 4970 | 0.01345 |
| Conductor | 72.35 | 1820 | 0.02384 |

VentureBeat engineering writeup cross-check: it reports the same average `77.27%`, AIME25 `93.3%`, GPQA-Diamond `87.5%`, LiveCodeBench `83.93%`, MoA `11,203` tokens, Conductor `1,820` tokens, and average `three steps per workflow`.

OOD under cost constraints:

| Model | AIME25 | BigCodeBench | GPQA-D | Avg. |
|---|---:|---:|---:|---:|
| R1-Distill-Qwen-32B | 30.00 | 24.3 | 51.01 | 35.10 |
| gemma-3-27b-it | 6.67 | 10.8 | 33.33 | 16.93 |
| Qwen3-32B (thinking) | 23.33 | 20.9 | 59.09 | 34.44 |
| Qwen3-32B | 23.33 | 23.0 | 54.05 | 33.46 |
| Gemini Pro 2.5 | 46.67 | 35.1 | 75.25 | 52.34 |
| Claude Sonnet 4 | 35.33 | 35.8 | 67.30 | 46.14 |
| GPT 5 | 46.67 | 33.8 | 72.73 | 51.07 |
| Conductor | 66.67 | 37.8 | 81.31 | 61.93 |

Recursion:

| Model | AIME25 | BigCodeBench | GPQA-D | Average score |
|---|---:|---:|---:|---:|
| Conductor | 66.67 | 37.8 | 81.31 | 61.93 |
| Conductor-Recursive | 66.67 | 40.0 | 82.32 | 63.00 |

Ablations:

| Ablation | MATH500 | MMLU | RLPR | LiveCodeBench |
|---|---:|---:|---:|---:|
| fine-grained access | 88.67 | 93.55 | 42.28 | 61.24 |
| w/o few-shot | 82.00 | 92.69 | 41.50 | 54.86 |
| w/o subtasks | 88.5 | 92.75 | 41.95 | 58.62 |
| Conductor | 89.33 | 93.14 | 42.63 | 64.29 |

Agent-selection ablation:

| Model | AIME | BigCodeBench | GPQA-D | Avg. |
|---|---:|---:|---:|---:|
| Claude Sonnet 4 | 74.30 | 37.16 | 77.70 | 63.0533 |
| Gemini 2.5 Pro | 78.30 | 37.51 | 84.80 | 66.8700 |
| GPT-5 | 90.80 | 32.75 | 82.30 | 68.6167 |
| Conductor w/ all GPT-5 | 93.33 | 33.50 | 82.60 | 69.8100 |
| Conductor | 93.30 | 37.86 | 87.50 | 72.8867 |

Replacing trained Conductor with frontier-model conductor:

| Model | LCB | AIME | BigCodeBench | GPQA-D | Avg. |
|---|---:|---:|---:|---:|---:|
| GPT-5 conduct 7 models | 50.86 | 76.67 | 34.50 | 77.78 | 59.9525 |
| GPT-5 conduct | 67.43 | 93.30 | 33.10 | 86.36 | 70.0475 |
| Gemini 2.5 Pro conduct | 70.29 | 93.30 | 35.13 | 87.62 | 71.5850 |
| Conductor | 83.93 | 93.30 | 37.86 | 87.50 | 75.6475 |

Debate-round finding: no primary-source table isolates `with debate rounds` vs `without debate rounds`. The paper reports emergent verification/refinement/debate-style strategies, compares against 5× self-reflection baselines, and separately ablates subtasks, few-shot conditioning, fine-grained access, all-GPT-5 agent selection, recursive scaling, and frontier-model-as-conductor.

### B. TRINITY — exact engineering details

#### B1. Problem formulation and CoordinationHead dimensions

TRINITY objective and policy:

```tex
f_\theta:\ \mathcal{H}\to\R^{|\mathcal{A}|},\qquad 
\pi_\theta(a\mid s)\ \propto\ \exp\!\big(f_\theta(h(s))_a\big),\ a\in\mathcal{A}.
```

```tex
J(\theta)\ :=\ \E_{\tau\sim\pi_\theta}[R(\tau)]
```

Representation / action facts:

| Field | Published value/detail |
|---|---|
| Coordinator SLM | `Qwen3-0.6B` |
| Hidden size | `d_h = 1024` inferred from parameter table and source text |
| Agent pool size | `L = 7` |
| Role logits | `3` (`Thinker`, `Worker`, `Verifier`) |
| Output size | `L + 3 = 10` logits |
| Default head | single linear layer, no bias: `z = W h`, `W ∈ R^{n_a × d_h}` |
| Linear head params | `10240` (`10 × 1024`) |
| SVF trainable params | `9216` |
| Total trainable default | `19456` (`10240 + 9216`), under 20K |
| SLM layer selected for SVF | second-to-last layer of Qwen3-0.6B |
| Head input position | penultimate output-token hidden state by default |

Head architecture exact forms:

```tex
\mathbf{z}=\mathbf{W}\mathbf{h}, \qquad \mathbf{W}\in\mathbb{R}^{n_a\times d_h}.
```

```tex
\mathbf{u}=\mathrm{ELU}(\mathbf{U}\mathbf{h}), \qquad
\mathbf{z}=\mathbf{V}\mathbf{u}\cdot \sigma
```

```tex
\mathbf{z}=\mathbf{W}\,(\mathbf{h}\odot \boldsymbol{\alpha})
```

Block-diagonal-10 exact output form:

```tex
z_j=\mathbf{w}_j^\top \mathbf{h}_j,\qquad
h_j=\begin{cases}
\left\lfloor \tfrac{d_h}{10}\right\rfloor+1,& j\le (d_h\bmod 10)\\[2pt]
\left\lfloor \tfrac{d_h}{10}\right\rfloor,& \text{otherwise}
\end{cases}.
```

Parameter table:

| Component | Params |
|---|---:|
| SVF | 9216 |
| linear | 10240 |
| low-rank | 20680 |
| sparse | 11266 |
| block-diagonal-2 | 5120 |
| block-diagonal-10 | 1024 |

#### B2. sep-CMA-ES config and fitness

Published sep-CMA-ES state and sampling equation:

```tex
D_t=\mathrm{diag}(\sqrt{s_{1,t}},\ldots,\sqrt{s_{n,t}})\succ0,
\qquad
y \;=\; m_t+\sigma_t D_t z,\ \ z\sim\mathcal N(0,I_n).
```

Population and replication:

```tex
\lambda=\lceil 4+3\ln n\rceil
```

Study-specific instantiation:

```tex
n\approx 10000,
\lambda=\lceil 4+3\ln 10000\rceil=32,
m_{\mathrm{CMA}}=16,
m_{\mathrm{RS}}=32
```

Budget equations:

```tex
B_{\mathrm{env}}=m_{\mathrm{CMA}}\lambda T
```

```tex
N=\big\lfloor (m_{\mathrm{CMA}}\lambda/m_{\mathrm{RS}})\,T\big\rfloor
=\big\lfloor (16\cdot 32/32)\,T\big\rfloor\approx \lfloor 16\,T\rfloor
```

Published iteration/budget references:

- Proposition range: `T ∈ [2,60]`.
- REINFORCE comparison ran `60` iterations with batch size equal to sep-CMA-ES per-iteration evaluation size.
- If using `n≈10000`, `λ=32`, `m_CMA=16`, `T=60`, then the budget implied by the paper's formula is `16 × 32 × 60 = 30,720` Bernoulli terminal evaluations.
- Introduction frames the regime as `1.5k--40k evaluations for a 10k-dimensional problem`.

Fitness definition:

- `R(τ) ∈ {0,1}` terminal reward at the end of a full multi-turn trajectory.
- Each trajectory run is an atomic Bernoulli evaluation.
- Candidate fitness is estimated by averaging terminal reward over replicated end-to-end runs.

The fetched paper does **not** publish a concrete initial `σ_0` value or initial parent vector beyond the sep-CMA-ES variables `m_t`, `σ_t`, and `D_t`. It does publish Xavier-uniform initialization for the low-rank head, but that is a head-ablation initialization, not the sep-CMA-ES sigma/init config.

#### B3. Per-turn protocol and termination

Per-turn transcript and selection:

```tex
\mathcal{C}_{k-1} = \big(Q, O_1, \ldots, O_{k-1}\big)
```

```tex
R_k \in \{\text{Thinker (T)}, \text{Worker (W)}, \text{Verifier (V)}\}
```

Termination rule:

```tex
\tau = \min\{\,k \le K : R_k=\mathrm{V}\ \text{and}\ u_k=\texttt{ACCEPT}\,\}
```

Fallback if no acceptance:

```tex
\tau = K
```

Verifier output contract:

```tex
u_k \in \{\texttt{ACCEPT}, \texttt{REVISE}\}
```

Maximum turns in experiments: `K = 5`.

Published role contracts (exact prompts are not included in the fetched source/PDF):

| Role | Published contract |
|---|---|
| Thinker | strategy / high-level plans / decompositions / critiques; may propose subgoals and next role |
| Worker | concrete task progress: derivation, code snippet, numerical result, etc. |
| Verifier | check correctness/completeness/responsiveness; output `ACCEPT` or `REVISE` plus optional diagnosis |

#### B4. Why sep-CMA-ES beats RL/imitation in the paper

Published argument:

- The coordination head is about `10K` parameters.
- Rewards are binary terminal rewards.
- Each atomic evaluation requires multiple LLM calls, so the evaluation budget is tight.
- Parameter correlations are weak / nearly block-separable; inter-block interference is low.
- REINFORCE sees noisy global returns, weak inter-block signal, poor credit assignment, and unstable learning.
- SFT can label direct single-step agent selection, but multi-turn label generation becomes intractable.

SFT label-cost derivation:

```tex
3 \times 7\text{k} \times 7 = 147\text{k}
```

```tex
7^4 \cdot 3^5 = 583{,}443 \approx 5.8 \times 10^5
```

```tex
1.5 \times 10^5 \times 5.8 \times 10^5 \approx 8.7 \times 10^{10}
```

sep-CMA-ES vs RS gain ratio:

```tex
\frac{\text{CMA gain in }J}{\text{RS gain in }J}
\ \gtrsim\
\frac{\bar\kappa_{\mu,\lambda}}{2}\cdot
\frac{T}{\ln\!\big(\max\{e,\lfloor (m_{\mathrm{CMA}}\lambda/m_{\mathrm{RS}})\,T\rfloor\}\big)}\cdot \eta^2
\ -\ \frac{C}{\ln\!\big(\max\{e,\lfloor (m_{\mathrm{CMA}}\lambda/m_{\mathrm{RS}})\,T\rfloor\}\big)} .
```

Steady-regime contraction:

```tex
\frac{\bar\kappa_{\mu,\lambda}}{n}\,(1-O(\varepsilon_H))
```

#### B5. TRINITY benchmark and ablation numbers

Head ablation:

| Head | LiveCodeBench | MATH500 | MMLU | RLPR |
|---|---:|---:|---:|---:|
| linear | 0.615 | 0.880 | 0.916 | 0.401 |
| low-rank | 0.597 | 0.770 | 0.914 | 0.344 |
| sparse | 0.400 | 0.811 | 0.917 | 0.372 |
| block-diagonal-2 | 0.336 | 0.776 | 0.897 | 0.378 |
| block-diagonal-10 + argmax | 0.551 | 0.812 | 0.802 | 0.376 |

Component ablation:

| Method | LiveCodeBench | MATH500 | MMLU | RLPR | Average |
|---|---:|---:|---:|---:|---:|
| TRINITY | 61.46 | 88.00 | 91.56 | 40.72 | 70.44 |
| w/o Singular value fine-tuning | 55.68 | 85.85 | 90.10 | 39.77 | 67.85 |
| w/o Thinker-role selection | 57.80 | 86.20 | 92.75 | 38.00 | 68.69 |
| w/o Tri-role selection | 58.28 | 82.00 | 91.64 | 36.15 | 67.02 |
| w/ Last token | 50.85 | 87.00 | 82.19 | 38.60 | 64.66 |
| Claude-4-Sonnet only | 39.09 | 82.25 | 88.23 | 34.90 | 61.12 |
| Gemini Pro 2.5 only | 46.51 | 83.05 | 79.41 | 43.00 | 62.99 |
| GPT-5 only | 59.54 | 75.66 | 90.74 | 37.87 | 65.95 |

Learning algorithm comparison:

| Method | LiveCodeBench | MATH500 | MMLU | RLPR |
|---|---:|---:|---:|---:|
| REINFORCE | 0.253 | 0.459 | 0.500 | 0.266 |
| RS | 0.374 | 0.794 | 0.897 | 0.345 |
| SFT | 0.592 | 0.786 | 0.906 | 0.360 |
| sep-CMA-ES | 0.615 | 0.880 | 0.916 | 0.401 |

Hold-out tasks:

| Model | AIME | BigCodeBench | MT-Bench | GPQA-D | Average |
|---|---:|---:|---:|---:|---:|
| Gemini Pro 2.5 | 46.67 | 35.10 | 9.37 | 75.25 | 52.34 |
| GPT-5 | 46.67 | 33.80 | 9.35 | 72.73 | 51.07 |
| Claude-4-Sonnet | 35.33 | 35.80 | 9.28 | 67.30 | 46.14 |
| Qwen3-32B (reasoning) | 23.33 | 20.90 | 8.99 | 59.09 | 34.44 |
| DeepSeek-R1-Qwen-32B | 30.00 | 24.30 | 8.43 | 51.01 | 35.10 |
| Qwen3-32B (direct) | 20.00 | 23.00 | 9.03 | 54.05 | 33.46 |
| Gemma-3-27B-IT | 20.00 | 20.30 | 8.76 | 33.33 | 21.38 |
| TRINITY | 50.00 | 35.80 | 9.60 | 76.82 | 54.21 |

Unbounded LiveCodeBench result called out in text: pass@1 `0.862` on LiveCodeBench V6, vs GPT-5 `0.838`, Gemini 2.5-Pro `0.672`, Claude-4-Sonnet `0.465`; max collaboration turns from 2 to 6 improve `0.823` to `0.863`.

### C. Sakana Fugu technical report and config details

Fugu technical report architecture distinctions:

| Variant | Reported design |
|---|---|
| Fugu | latency-aware; selects a single worker per input; no role assignment; logits-only decision head; designed for low latency |
| Fugu-Ultra | performance-oriented; scales Conductor-style multi-agent workflows; up to 5 workflow steps; function-calling support and shared memory |

Fugu model card:

| Benchmark | Fugu-Ultra | Fugu | Claude Opus 4.8 | Gemini 3.1 | GPT-5.5 |
|---|---:|---:|---:|---:|---:|
| SWE Bench Pro | 73.7 | 59.0 | 69.2 | 54.2 | 58.6 |
| Terminal Bench 2.1 | 82.1 | 80.2 | 74.6 | 70.3 | 78.2 |
| LiveCodeBench | 93.2 | 92.9 | 87.8 | 88.5 | 85.3 |
| LiveCodeBench Pro | 90.8 | 87.8 | 84.8 | 82.9 | 88.4 |
| Humanity's Last Exam | 50.0 | 47.2 | 49.8 | 44.4 | 41.4 |
| CharXiv Reasoning | 86.6 | 85.1 | 84.2 | 83.3 | 84.1 |
| GPQA Diamond | 95.5 | 95.5 | 92.0 | 94.3 | 93.6 |
| SciCode | 58.7 | 60.1 | 53.5 | 58.9 | 56.1 |
| τ3 Banking | 20.6 | 21.7 | 20.6 | 8.4 | 20.6 |
| Long Context Reasoning | 73.3 | 74.7 | 67.7 | 72.7 | 74.3 |
| MRCRv2 | 93.6 | 86.6 | 87.9 | 84.9 | 94.8 |

Fetched `/configs/` directory contents are preserved verbatim at `/private/tmp/fugu_sources/fugu_zip/fugu-main/configs/`. Operationally relevant exact config fields:

| File | Exact fields |
|---|---|
| `configs/bundle.sh` | `BUNDLE_CODEX_VERSION="0.141.0"`; env key regex `^fish_[0-9a-f]{64}$`; hint `codex-fugu` |
| `configs/files/fugu.json` | model slugs `fugu`, `fugu-ultra`; context window `1000000`; provider API support true; `fugu-ultra` supports reasoning summaries, `fugu` does not; truncation limit `10000`; parallel tool calls true |
| `configs/formats/legacy/injects/profiles.fugu.toml` | `[profiles.fugu] model = "fugu"`, effort `high`, provider `sakana`, catalog `{{CODEX_HOME}}/fugu.json` |
| `configs/formats/modern/files/fugu.config.toml` | default model `fugu`, effort `high`, provider `sakana`, catalog `{{CODEX_HOME}}/fugu.json` |
| `configs/injects/model_providers.sakana.toml` | `base_url = "https://api.sakana.ai/v1"`; `env_key = "SAKANA_API_KEY"`; `wire_api = "responses"`; `stream_idle_timeout_ms = 7200000`; `stream_max_retries = 5`; `request_max_retries = 4` |

### Stage 1 build deltas — TRINITY specifics for CoordinationHead / CMA-ES-via-DarwinEngine

1. **Use a logits-only coordinator, not a text-generating router.** The coordinator SLM may generate internally, but its decoded text is discarded for routing; the build should expose `h(s)` and route from head logits.
2. **Default head should be linear `W ∈ R^{10×1024}` for a 7-agent pool + 3 roles.** If we keep exactly 7 workers, this is `10,240` head params. Do not start with a generic MLP unless an ablation requires it.
3. **SVF is part of the default winning setup.** Add `9,216` singular-value-scale parameters on the selected Qwen3-0.6B second-to-last layer if we want to match the paper; if DarwinEngine only evolves head weights, document that as a deliberate simplification.
4. **If evolving head-only, use TRINITY's `n≈10000` CMA constants.** Set `λ = ceil(4 + 3 ln n) = 32`, candidate replications `m_CMA = 16`, and budget around the paper's `T≤60` regime. For `T=60`, expected terminal evaluations are `30,720`.
5. **If evolving head + SVF (`n=19,456`), recompute λ.** The paper's explicit `λ=32` is tied to `n≈10000`; using all `19,456` trainable params changes the formula and must be called out.
6. **Fitness must be terminal and Bernoulli first.** DarwinEngine should score full trajectories with `R(τ) ∈ {0,1}`, average replicated end-to-end runs per candidate, then rank/recombine. Avoid per-token/per-step proxy rewards unless separately ablated.
7. **Implement the tri-role protocol exactly enough to test the ablation.** Roles are Thinker, Worker, Verifier; max turns `K=5`; terminate only when selected role is Verifier and verifier emits `ACCEPT`; otherwise stop at `K`.
8. **Keep penultimate-token hidden state as the baseline.** The `w/ Last token` ablation collapses LiveCodeBench from `61.46` to `50.85`; last/EOS token routing should be marked unsafe until proven.
9. **Favor sep-CMA-ES over REINFORCE for Stage 1.** TRINITY's algorithm table is decisive in this regime: sep-CMA-ES beats REINFORCE on all four ID tasks, e.g. LiveCodeBench `0.615` vs `0.253`.
10. **Do not invent exact role prompts.** The paper publishes role contracts but not full role prompt strings; our prompts must be treated as local implementation choices.

### Stage 2 build deltas — Conductor specifics for GRPO planner plan

1. **Planner output format should be Python-list serialization, not JSON.** The paper parses `model_id`, `subtasks`, and `access_list` as Python lists after the model's chain-of-thought. JSON can be an internal safer format, but it would be a deviation.
2. **Use the simple `access_list` first.** Implement `[]` and `["all"]` exactly before adding `[0,2,3]` position lists; fine-grained access underperformed the simple scheme on LiveCodeBench (`61.24` vs `64.29`) despite slightly improving MMLU.
3. **Reward should initially be terminal parse/correctness only.** Published Conductor reward is `0` for parse failure, `1` for correct final workflow output, `0.5` otherwise. No explicit cost penalty is published. If we need cost-aware optimization, add it as a repo-local extension with a separate ablation.
4. **GRPO group size should be 64 per question.** The exact training loop is 4 questions/iteration × 64 rollouts/question = batch 256, 200 iterations.
5. **Disable KL for the baseline reproduction.** The paper disables reference-model sync and sets KL penalty to `0`; no entropy bonus is published.
6. **Constrain workflow length to 5.** Efficiency arises despite no explicit cost regularizer: average workflow length is ~3 steps, while allowed max is 5.
7. **Represent available workers ordinally.** Feed `Model 0`, `Model 1`, etc. plus metadata, not provider names, to reduce prior/model-name bias.
8. **Train randomized-pool robustness as a finetune, not from scratch.** Procedure is pretrained Conductor → randomly sampled `k`-model subset from `n` workers per question → modified input instructions. Since exact `k` is unpublished, make `k` configurable and log it in receipts.
9. **Recursion is a second finetune.** Match the published recipe: 20 iterations, 350 samples (`175 LCB` + `175 RLPR`), 64 rollouts/sample, no KL, `0.25` discount on the initial non-recursive round, normalize rewards across rounds.
10. **Recursive termination must be parseable.** Empty `model_id`, `subtasks`, and `access_list` means return previous answer. Non-empty lists launch another workflow under max recursion/call budget.
11. **Function-calling orchestration needs isolation.** Fugu-Ultra's technical report says same-workflow agent trajectories are isolated except through `access_list`; shared memory applies across workflows/conversation, not as an all-agent shared scratchpad inside the current workflow.
12. **Benchmark acceptance should include efficiency and ablations.** Minimum reproduction table should include unconstrained/constrained score, average calls/steps, token/cost, no-subtask, no-few-shot, fine-grained access, all-GPT-5, recursive, and frontier-model-as-conductor ablations.
