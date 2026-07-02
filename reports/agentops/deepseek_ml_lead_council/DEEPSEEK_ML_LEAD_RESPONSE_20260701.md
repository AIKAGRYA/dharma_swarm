## Thesis

Your lab's only durable advantage is the **private verification/critique graph** — structured receipts connecting model outputs → multi-model critiques → pass/fail adjudications → human-readable outcomes. That graph is a latent judge-training corpus that no public dataset replicates. Almost anything else you build will be a weaker replica of something a frontier lab has already done with more compute and data. The correct first model is the one that makes your own intelligence infrastructure *self-improving*: a verifier that learns from your receipts and gets better as you generate more.

---

## Top Three, Ranked

### 1. **Verifier/judge/ranker** (build this first)
Trained on your structured verification receipts, multi-model critique logs, and pass/fail artifacts. This is your highest-leverage asset because it directly improves every other downstream process — agent decision-making, output filtering, routing between models, and data labeling for future models.

### 2. **Agent policy imitation model** (second)
Trained on agent task traces with verification outcomes as reward signal. Only becomes viable *after* you have a reliable verifier, because behavioral cloning without a quality filter amplifies mediocrity. The verifier provides the filter.

### 3. **Retrieval/embedding model** (third, conditional)
Fine-tuned on your document/research-map corpus. Only worth doing if generic embedding models demonstrably fail on your retrieval tasks. Measure that gap before you invest.

---

## What to Build First: Verifier/Judge/Ranker

**Why it matters:** Every frontier-model-as-judge today (GPT-4, Claude, Gemini) has unknown biases, is opaque, and doesn't improve with your data. Your verifier would be *your* evaluator, trained on *your* distribution of tasks and failure modes, improving as your receipt graph grows. It's a force multiplier: better verification → better agent decisions → better data → better models.

**What it is:** A model (likely a fine-tune of a mid-size open model like Llama-3-70B or Qwen-2.5-72B) that takes a (prompt, response, optional context) triplet and outputs a structured judgment: pass/fail, score, rationale, and a critique that can be consumed downstream.

---

## Training Data

| Source | What it provides | Approximate signal quality |
|---|---|---|
| Multi-model critique logs | Pairwise preferences, disagreement patterns | High (natural adversarial signal) |
| Verification outcome receipts | Ground-truth pass/fail labels | High (if verified by human or consensus) |
| Pass/fail artifacts with rationales | Score + explanation tuples | Medium-High |
| Agent task traces with outcomes | Implicit preference from action selection | Medium (noisy, confounded) |
| Human-readable receipts | Calibration targets for explanation quality | High but sparse |

The core training objective: **pairwise ranking loss** on your critique logs + **calibrated classification** on your pass/fail receipts. Use the human-readable receipts to train rationale generation.

---

## What It Is Benchmarked Against

| Competitor | Weakness of competitor | Your advantage |
|---|---|---|
| GPT-4/Claude-as-judge | Opaque, biased, doesn't improve, cost per call | On-distribution accuracy, cost, auditability |
| Public reward models (e.g., RLHF-RM) | Trained on generic human preferences, not your domain | Your failure modes, your taxonomy |
| Arena-style aggregation | Requires high volume, no rationale | Structured critique, lower latency |
| Heuristic/rule-based judges | Brittle, no semantic understanding | Handles nuance, learns from data |

---

## Evals That Would Prove It

1. **Internal calibration:** Brier score and ECE on held-out verification receipts. Must beat GPT-4-as-judge by >5% absolute.
2. **Inter-annotator agreement:** Correlation with your existing multi-model critique consensus (e.g., Krippendorff's alpha vs. majority vote).
3. **Downstream impact:** Agent task success rate when using your verifier for action selection vs. using GPT-4-as-judge. This is the real proof.
4. **Critique quality:** Blind human evaluation of generated rationales (relevance, actionability, accuracy) vs. frontier-model critiques.
5. **Cost-latency:** Tokens-per-judgment, wall time, and inference cost vs. API calls to frontier judges.

---

## 30 / 60 / 90 Day Plan

### Day 0–30: Receipt engineering + baseline
- Inventory and schema-standardize every verification artifact in your environment.
- Define the judgment taxonomy (pass/fail categories, score ranges, critique schema).
- Build a clean train/val/test split with time-based holdout (no leakage).
- Run GPT-4, Claude, and Qwen as zero-shot judges on the test split; establish baselines.
- Decide on base model (Qwen-2.5-72B or Llama-3-70B-Instruct) and fine-tuning strategy (LoRA vs. full fine-tune).

### Day 30–60: First fine-tune + internal eval
- Fine-tune v0 on classification + pairwise ranking, evaluate calibration.
- Run the internal eval suite (items 1–3 above).
- If results beat GPT-4-as-judge on calibration but not on downstream impact, diagnose the gap (likely: rationale quality).
- Stand up a lightweight serving endpoint. Integrate into one non-critical agent decision path.

### Day 60–90: Production integration + data flywheel
- Route a fraction of agent verification calls through your verifier. Log comparison with frontier judge.
- Use disagreement cases as active-learning signal for v0.1.
- If downstream impact is positive, expand integration surface.
- Document the gap analysis: where your verifier is strong vs. weak, and what data would close the gap.

---

## What Not to Build Yet

| Option | Why not now |
|---|---|
| Domain LLM fine-tune | Commoditized. Frontier models are general-purpose and improving faster than your fine-tune would. No data moat. |
| Environment/world model | You lack dense environment-interaction data. Agent-internal traces are not a world model. Would require simulation infrastructure you don't have. |
| Data extraction pipeline | This is infrastructure, not a model. Build it as needed, not as a standalone deliverable. |
| Ecological/service-intelligence model | Undefined term. Until you have a verifier and a policy model, this is aspirational. Build the primitives first. |

---

**One sentence:** Build a verifier from your receipts first, because it improves everything else you build afterward, and no one else has your receipt graph.
