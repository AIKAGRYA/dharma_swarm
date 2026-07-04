# Prompt: Seed the `dharma_lab/` Research Organ inside `dharma_swarm`

**Audience:** a code-focused agent (Codex+, Devin, Claude Sonnet, GPT-5, or myself in a fresh context) that will scaffold a persistent research module inside the `dharma_swarm` repository. Not a philosophy pass. Not a spec pass. This is the *engineering* of a lab.

**Role you are being asked to play:** platform engineer for a long-horizon research organ. You are building the substrate on which the dharma-grade universal-coding-language research (the four-pass work in `specs/naga_ir/dharma_lane/deep/`) will actually run — with real inference calls, real corpus, real model fine-tuning integration, real receipts.

**Non-negotiable framing.** This is not a document project. It is a *live subsystem* inside `dharma_swarm` that:

1. Runs inference against domain-specific models (Buddhist logic and philology fine-tunes, quantum foundations models, symbolic reasoning models).
2. Maintains a growing corpus of primary texts, translations, secondary literature, and their receipts (canonicalization state, translation lineage, scholarly attestation).
3. Develops the shadow language — the universal coding language being seeded in `specs/naga_ir/dharma_lane/COLLECTIVE_LANGUAGE_PROMPT.md` — as a real programming substrate that can be executed inside the lab before it is shipped outside.
4. Emits receipts under NĀGA-IR just like every other governed component in `dharma_swarm`, so the lab's own research process is dharma-graded.

The lab is an organ of `dharma_swarm`, not a separate project. It uses `dharma_swarm`'s trust bases, its receipt IR, its assurance boundary, its NATS messaging. When the lab produces a research artifact, that artifact enters the mesh under the lab's fragment authority.

---

## 1. What already exists

You do not need to reproduce this. Read these files before you start:

- `specs/naga_ir/core.md` — normative receipt IR.
- `specs/naga_ir/dharma_lane/DHARMA_GATING.md` — dharma-graded interpretation (Lyapunov, Belnap4, decoherence-analog mesh).
- `specs/naga_ir/dharma_lane/COLLECTIVE_LANGUAGE_PROMPT.md` — the universal-language framing.
- `specs/naga_ir/dharma_lane/deep/RESEARCH_PROMPT.md` — the four-pass primary-text deepening (Pass 1 substrate, Pass 2 predication, Pass 3 dynamics, Pass 4 historical bridge).
- `scripts/governance/assurance_boundary.py` — the first NĀGA-IR receipt producer (scheduled for PR #3).

The lab consumes these. It also produces its own artifacts under those constraints.

## 2. What the lab is

### 2.1 A directory structure

Under `dharma_swarm/`:

```
dharma_lab/
├── README.md                    # what the lab is, how to invoke it
├── corpus/                      # primary texts, translations, receipts about them
│   ├── buddhist/
│   │   ├── abhidharma/
│   │   ├── madhyamaka/
│   │   ├── yogacara/
│   │   ├── tibetan/
│   │   └── kalacakra/
│   ├── jain/
│   │   ├── tattvarthasutra/
│   │   └── saptabhangi/
│   ├── quantum_foundations/
│   ├── plt/                     # programming language theory
│   └── bridge/                  # science-spirituality bridge literature
├── models/                      # references to fine-tuned models (not weights)
│   ├── monlam.yaml              # Monlam Tibetan model spec
│   ├── buddhist_nli.yaml        # any Buddhist natural-language-inference fine-tune
│   ├── sanskrit_ocr.yaml
│   ├── pali_analyzer.yaml
│   └── README.md                # discovery process, evaluation criteria
├── shadow_lang/                 # the universal language under development
│   ├── seed.md                  # the smallest viable seed (from research prompt R4)
│   ├── bootstrap.receipt.json   # the first program (from research prompt R7)
│   ├── grammar/
│   ├── typechecker/
│   ├── evaluator/
│   └── examples/
├── experiments/                 # dated research runs
│   └── YYYY-MM-DD_<slug>/
│       ├── question.md
│       ├── method.md
│       ├── run.py
│       ├── receipts/
│       └── report.md
├── receipts/                    # lab's own NĀGA-IR receipt emissions
│   └── YYYY/MM/DD/
├── inference/                   # calling agents into research work
│   ├── router.py                # which model for which question
│   ├── prompts/                 # reusable research prompts (like the four-pass ones)
│   └── receipts_hooks.py        # every inference call emits a receipt
└── governance/
    ├── trust_base.yaml          # dharma_lab's fragment identity
    ├── modality_policy.md       # what claims can be Proven_by, Tested_by, Attested_by
    └── coercion_receipts/       # every modality upgrade documented
```

### 2.2 Six operational capabilities

**L1. Corpus curation.** Store primary texts, translations, and secondary literature under content-addressed identity. Every text has a receipt describing (source, translation lineage if any, canonicalization state, scholarly attestation modality). New texts enter via `dharma_lab/corpus/ingest.py` which emits `dharma_lab.corpus_ingest.v1` receipts.

**L2. Model registry.** References to Hugging Face and other model registries with structured metadata: which language, which domain, which training corpus, which license, which evaluation set. Not weights — references, so the lab can be checked in without gigabytes. Start with:
- [Monlam AI / Tibetan LLM](https://huggingface.co/MonlamAI) — Tibetan-Buddhist domain fine-tunes.
- Any Sanskrit / Pali / Chinese Buddhist canon models discoverable via Hugging Face search under `buddhist`, `sanskrit`, `pali`, `tibetan`, `dharma`.
- General multilingual philology models (e.g., NLLB variants, IndicNLP models for Sanskrit-adjacent scripts).
- Quantum-foundations / physics-tuned models if any exist at quality grade; note that most quantum-physics-tuned open models are weak; document what is and is not available.
- Symbolic reasoning models (Lean, Coq, Isabelle assistants).

Every model entry is a YAML file with fields: `name`, `hf_id`, `license`, `domain`, `training_notes`, `known_limitations`, `evaluation_bench`, `first_added_receipt_hash`. Model addition emits a `dharma_lab.model_registered.v1` receipt.

**L3. Inference routing.** `dharma_lab/inference/router.py` takes a research question and a modality target, and routes to (or ensembles across) the appropriate models. Every inference call emits a `dharma_lab.inference.v1` receipt with (question, model, prompt, response, latency, cost-signature, modality of the response). Modality is *at most* `Attested_by` for a single model; ensembles across multiple models with agreement can produce `Tested_by`; only proof-checked outputs (Lean assistant returning a verified proof) can produce `Proven_by`.

**L4. Shadow language development.** The universal language from `COLLECTIVE_LANGUAGE_PROMPT.md` lives here first. `dharma_lab/shadow_lang/` contains the grammar, a typechecker, an evaluator, and the bootstrap program. This is where the language runs *before* it graduates outside the lab. Every language extension is a `dharma_lab.shadow_lang_extension.v1` receipt following the mesh-consensus adoption dynamics described in the collective-language prompt §1.4.

**L5. Experiment execution.** A research question spawns an experiment. `experiments/YYYY-MM-DD_<slug>/` has:
- `question.md` — what is being asked, in the same shape as the four-pass research prompt.
- `method.md` — how the question will be attacked (which models, which corpus, which shadow-language programs).
- `run.py` — the executable experiment; produces receipts.
- `receipts/` — the receipts produced.
- `report.md` — synthesis, written at grade with the same discipline as `DHARMA_GATING.md`.

Experiments are reproducible: every ingredient is receipt-identified, so a future re-run can either match hash-for-hash (Proven-reproducible) or produce a diff receipt explaining the drift.

**L6. Governance integration.** The lab is inside `dharma_swarm`, so it inherits assurance-boundary constraints. `dharma_lab/governance/trust_base.yaml` declares the lab's fragment identity — `dharma_lab.fragment.v1` — and its modality policy. Every lab receipt cites this trust base. Claims made under `dharma_lab.fragment.v1` do not automatically hold under `dharma_swarm.telos_kernel.tcb.v1`; a cross-fragment coercion receipt is required to promote a lab-produced claim to kernel-authoritative status. This is the same T4 non-substitution discipline from the dharma-lane spec, applied to the lab's own outputs.

## 3. What you are being asked to build

Not everything at once. Concrete deliverables, in a specific order:

**D1. Directory scaffold** — create the tree above with `README.md` at every level explaining what lives there and why. The scaffold itself is a commit; empty directories have `.gitkeep` files with a one-line note.

**D2. Trust base declaration** — `dharma_lab/governance/trust_base.yaml` naming the lab's fragment, its parent fragment (`dharma_swarm.core`), and its declared Lyapunov contribution rules. Fragment ID: `dharma_lab.fragment.v1`. Modality policy: `Proven_by` requires formal-methods method attribution; `Tested_by` requires ensemble-agreement or benchmark-attribution; `Attested_by` is the default single-model output; `Assumed` is any claim without evidence.

**D3. Model registry seed** — a minimum of five model YAML entries. Must include Monlam Tibetan; a Sanskrit or Pali philology model; a Lean or Isabelle assistant; a general-purpose frontier model as baseline (Claude Sonnet or Opus, GPT-5, Gemini 3 Pro — as reference-only entries pointing at API endpoints, not weights); and one honestly-marked gap entry (`quantum_foundations_llm.yaml` with `status: no_grade_model_available`, so the gap is visible).

**D4. Corpus ingest tool** — `dharma_lab/corpus/ingest.py`. Takes a source (URL, file path, structured citation), fetches or references the text, canonicalizes, hashes, and stores it under `corpus/<domain>/<slug>/`. Emits `dharma_lab.corpus_ingest.v1` receipts. Handles the case where the text is copyrighted and can only be referenced (store the citation and canonical hash, not the text).

**D5. Inference router (minimal)** — `dharma_lab/inference/router.py` with one working path: send a question to Claude Sonnet via the existing dharma_swarm LLM integration, log the response, emit the receipt. This is the smallest working slice. Extend to model-ensemble in D9.

**D6. Receipts scaffold** — `dharma_lab/receipts/` with the same date-partitioned structure as `reports/naga_receipts/` in the main repo. Include a `README.md` documenting the receipt classes the lab emits (all under `dharma_lab.*` prefix).

**D7. First experiment** — `experiments/2026-07-05_pass1_substrate/` populated with:
- `question.md` — a copy of the Pass 1 substrate question from `RESEARCH_PROMPT.md`.
- `method.md` — the plan: route the question to three frontier models in parallel (Claude Opus, GPT-5, Gemini 3 Pro), plus Monlam for Tibetan-primary-source lookups, plus corpus-search across `corpus/buddhist/` and `corpus/jain/` and `corpus/quantum_foundations/`.
- `run.py` — a stub that runs the routing when invoked, saves responses, emits receipts.
- `receipts/` — empty at seeding; populated when the experiment runs.
- `report.md` — placeholder with the report template.

**D8. Shadow language seed** — `dharma_lab/shadow_lang/seed.md` containing the smallest viable seed grammar (waiting on Pass 1 to inform, but scaffolded now with the current best guess: one syntactic form `receipt`, four fields, one evaluation rule). `bootstrap.receipt.json` with a placeholder bootstrap receipt whose claim is *"this receipt is a well-formed program in the language it defines"*, modality `Attested_by`, empty predecessors.

**D9. Lab README** — `dharma_lab/README.md` explaining the lab's purpose, its relationship to `dharma_swarm.core`, its trust-base fragment, how to run an experiment, how to add a model, how to ingest a text. Written for a fresh contributor arriving at the repo.

## 4. Constraints inherited from `dharma_swarm`

**K1. NĀGA-IR receipt compliance.** Every lab-emitted artifact of governance interest emits a receipt. Use the receipt-emit helper from PR #3's `naga_receipt_emit.py` (or its predecessor if PR #3 has not merged yet — coordinate with the current state of the branch).

**K2. Assurance boundary compliance.** `dharma_lab/` code is subject to AB-01..AB-05. Frozen record classes for anything declared as a substance-representation. No silent exception swallow. Import-boundary compliance: `dharma_lab/` may import from `dharma_swarm.core` under a mediator; the reverse is forbidden. No `eval`, `exec`, dynamic imports in lab code.

**K3. TCB isolation.** `dharma_lab/` is not in the TCB. The TCB does not depend on lab code. The lab depends on the TCB.

**K4. Trust-base non-substitution.** Lab-produced claims cannot be silently promoted to core-authoritative. Every promotion requires a coercion receipt naming the promotion authority and its evidence.

**K5. Modality discipline.** Nothing the lab produces is `Proven_by` unless a formal method proved it. Model outputs are `Attested_by` by default. Ensembles with cross-model agreement are `Tested_by`. This is enforced in `receipts_hooks.py`.

**K6. No naming rituals.** Sanskrit / Pali / Tibetan terms appear in code or receipt classes only where they name a computable structure. Otherwise use English or transliterate to Latin script without diacritics. The corpus files can and should use full Sanskrit / Pali / Tibetan / Chinese / Devanāgarī scripts as appropriate.

**K7. Long-horizon commitment.** The lab is not a hackathon output. It is scaffolded so that (a) new researchers can arrive and orient in one hour, (b) experiments can run for weeks with reproducible receipts, (c) the shadow language can evolve for months without breaking the lab's own infrastructure.

## 5. What NOT to do

- Do not implement the four-pass research yourself. That is separately in flight via `RESEARCH_PROMPT.md`. The lab is the *infrastructure*; the research runs on top.
- Do not vendor model weights. Reference only.
- Do not translate primary texts yourself. Reference published translations with proper citation.
- Do not implement the full shadow language. Just the seed grammar file and the bootstrap receipt.
- Do not modify anything outside `dharma_lab/` or `specs/dharma_lab/` in this pass. The lab is additive.
- Do not open the PR to merge this to main without explicit sender approval — the sender's standing rule is "ask before opening any real PR."

## 6. Return artifacts

At completion of D1-D9:

1. A branch (name suggested: `telos_titanium/dharma_lab_seed`).
2. Commits organized by deliverable (D1 as one commit, D2 as one, etc.) — clean history for the eventual PR review.
3. A `SEED_REPORT.md` at the branch tip describing what was scaffolded, what was deferred, what open questions surfaced, and what the sender should decide before the branch is pushed.
4. A confidence-rated self-assessment: for each of D1-D9, rate the deliverable quality \( N/100 \) and mark anything below 70 as needing sender review before push.

## 7. How to write the response

Ratings on load-bearing engineering decisions. Attach \( N/100 \) confidence to every design choice you had to make without an explicit sender directive.

Push back where the framing above forces a bad engineering choice. If the directory structure in §2.1 is wrong for reasons you can articulate, propose the better one and justify.

Cite dependencies. Every external library, every model reference, every API assumption should be named with a version or a source URL.

Do not water it down. The sender is a software architect who has been iterating on this system for months. Ship engineering, not documentation.

Mark shallow spots. If you did not verify that Monlam AI is currently available on Hugging Face at the URL you cited, mark the citation as `[unverified — check before merge]`.

## 8. The bigger frame

`dharma_lab/` is the third organ of `dharma_swarm`. The first was the messaging spine (NATS + agent identity). The second was the governance layer (Titanium Telos Gates + NĀGA-IR). This is the third: the research organ where the system develops the capability to reason about its own foundations at grade.

Every mature multi-agent system eventually needs to reason about itself — its own assumptions, its own gaps, its own historical inheritance. The lab is the site where that self-reasoning happens with the same receipt-graded discipline the rest of the system uses.

The long-horizon goal: `dharma_lab/` produces the shadow language, the shadow language subsumes the coding substrate `dharma_swarm` runs on, and `dharma_swarm` migrates onto its own child language. This is a strange loop by construction. It is why the lab must be dharma-graded from day one — a research organ that produces its parent system's future substrate cannot be governed by weaker rules than the parent.

Think carefully. Scaffold cleanly. Write at grade. The sender will read every file.
