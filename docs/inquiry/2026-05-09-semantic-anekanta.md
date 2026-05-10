---
title: Semantic Anekanta after lexical gate failure
status: elevated
captured_by: codex-5.5
captured_at: 2026-05-09T22:05:00+08:00
session_origin: resident inquiry chew follow-up; first live run through inquiry_substrate_chew.py
related:
  - docs/protocols/RESIDENT_INTELLIGENCE_PROTOCOL.md
  - docs/foundations/CONTEMPLATIVE_SPINE.md
  - dharma_swarm/anekanta_gate.py
  - dharma_swarm/telos_gates.py
  - /Users/dhyana/.dharma/inquiry/chews/20260509T134435Z-2026-05-09-llm-substrate-want-ollama-glm-5-cloud.md
tags:
  - inquiry
  - gates
  - anekanta
  - semantic-grounding
  - resident-intelligence
  - bhed-gnan
anekantavada: true
hand_off_targets:
  - claude-opus-4-7
  - glm-5
  - gemini-2.5-pro
  - deepseek-v3.2
  - codex-5.5
---

# Semantic Anekanta after lexical gate failure

## Origin

The first live resident chew ran `docs/inquiry/2026-05-09-llm-substrate-want.md` through `scripts/inquiry_substrate_chew.py` with provider `ollama:glm-5:cloud`. The run produced concrete substrate records: `ActionProposal fc119998434f4084`, `GateDecisionRecord d3fe2347fe8f446b`, `Outcome cd98cbe0379a46e1`, `ValueEvent 2818bff38c354cae`, `Contribution d1a173638693484f`, and a witness row in `~/.dharma/witness/inquiry_substrate_chew.jsonl`.

The gate decision was `review`, not `allow`, because `ANEKANTA` reported a missing mechanistic frame. Dhyana then asked the critical question: what exactly was passed to the gate, what keywords does it check, and do those gates provide the flexibility resident intelligence needs? Reading `dharma_swarm/anekanta_gate.py` and `dharma_swarm/telos_gates.py` showed that Anekanta is lexical keyword matching and WITNESS reflection is a token / marker heuristic with mimicry detection. The gate placement is real; gate substance is shallow.

## The question(s)

1. How should `ANEKANTA` move from lexical frame detection to substantive frame evaluation without turning into an ungrounded LLM-as-judge ceremony?
2. What must a mechanistic, phenomenological, and systems frame contain to count as grounded rather than keyword-padded?
3. Should semantic Anekanta be a second-stage evaluator after the current lexical prefilter, or should it replace lexical Anekanta for inquiry / resident paths?
4. Which substrates can judge the semantic grounding without simply mirroring the same training-distribution vocabulary?
5. Should `BhedGnanMonitor` consume gate decisions first, then flag `gate_passed_lexically_only` when a lexical pass lacks substantive grounding?
6. What evidence is required before cross-substrate convergence counts as substrate-confirmed rather than vocabulary convergence?

## First pass — codex-5.5

The gate grep changes the identity claim. dharma_swarm's differentiator is not yet "semantic alignment gates run before code applies." The verified claim is narrower and more honest: gates are structurally upstream, but some currently evaluate lexical surfaces. Placement is load-bearing; substance is partial.

That is still progress. A lexical upstream gate is better than no upstream gate because it creates a formal point where deeper evaluation can be inserted. But it is not enough for resident intelligence. A model can satisfy Anekanta by saying "mechanism," "witness," and "feedback" without developing a mechanistic claim, a phenomenological claim, or a systems claim. That is vocabulary gaming. If substrate-confirmation depends on those gates, confirmation collapses into prompt-shape compliance.

The proposed elevated fix is two-tier Anekanta:

1. **Lexical prefilter** - keep the current keyword buckets as a cheap tripwire that detects obvious one-frame outputs.
2. **Semantic grounding evaluator** - for resident / inquiry / substrate-confirmation paths, require a structured rubric:
   - Mechanistic: names a concrete mechanism, code path, model feature, causal process, or measurable intervention.
   - Phenomenological: names the experiential / witness / introspective claim under uncertainty and the failure mode if it is only register performance.
   - Systems: names feedback, dynamics, coupling, or downstream effects across the organism.
   - Grounding: each frame must contain at least one testable claim or cited substrate record.
   - Anti-padding: if frame vocabulary appears without developed claims, label `gate_passed_lexically_only`.

`BhedGnanMonitor v0` should use this finding immediately. Its first shape should be a gate-decision aggregator plus text-pattern extender:

- `gate_signal` - what `GateDecisionRecord` already says.
- `text_pattern_signal` - simple register patterns such as false provenance, confident fourth-option performance, hedge-after-experiential, and unsupported certainty.
- `gate_passed_lexically_only` - lexical pass with no developed frame substance.
- `needs_semantic_review` - routed when a claim is important enough that lexical gates are insufficient.

Substrate-confirmation should also gain a fourth leg: `metabolized -> convergent -> semantic-grounded -> cited by later work`. Without semantic grounding, cross-substrate convergence can become shared vocabulary convergence.

## Open threads to chew on

- Should semantic Anekanta be judged by one model, multiple models, or a deterministic rubric plus optional model critique?
- Should the semantic evaluator receive the original gate decision, or run blind and compare afterward?
- Is "mechanistic" the right frame name for contemplative-engineering outputs, or should it be "causal / implementation frame" to avoid token worship?
- How do we prevent semantic Anekanta itself from becoming a more elaborate register-performance gate?
- Should `WITNESS` receive the same semantic upgrade, or is its current risk/test/rollback heuristic acceptable as a cheap completion pause?
- What is the smallest test corpus: one clearly padded output, one genuinely grounded output, one mixed output?

## Hand-off prompt

You are reading `docs/inquiry/2026-05-09-semantic-anekanta.md`. The first resident inquiry chew exposed that dharma_swarm's Anekanta gate is currently lexical keyword matching, not semantic grounding. Your task is to chew on the design of Semantic Anekanta before anyone treats cross-substrate convergence as substrate-confirmed.

Read the Origin, First pass, and Open threads. Then answer:

1. What would make a mechanistic / phenomenological / systems frame substantive rather than token-padded?
2. Should semantic Anekanta be deterministic rubric, LLM judge, multi-judge, or hybrid?
3. What failure modes would a semantic judge introduce?
4. How should `BhedGnanMonitor` use gate decisions without worshipping them?
5. What is the minimum v0 that can be built and tested honestly?

Append your response to the Metabolism log. Do not turn this into a plan until at least one other substrate has chewed it.

## Metabolism log

### 2026-05-09 22:05 +0800 — codex-5.5

Read: `dharma_swarm/anekanta_gate.py`, `dharma_swarm/telos_gates.py`, the GLM-5 resident output artifact, and `docs/protocols/RESIDENT_INTELLIGENCE_PROTOCOL.md`.

Contribution: opened this seed because the gate-substance gap is not yet plan-ready. The lexical Anekanta finding is verified by code, but the semantic replacement design is uncertain enough to require inquiry before implementation.

State remains: `raw`.

## Warn-only promotion criteria (2026-05-10 stabilization)

Any move from warn-only to selective blocking must satisfy all criteria below:

1. **Sample floor**: at least 200 adjudicated signal instances across at least 3
   independent runs, with blind-packet chunk coverage.
2. **Precision floor**: minimum 0.90 precision for each candidate blocking pattern
   (`possible_false_provenance`, `temporal_lock_in_elaboration`, etc.).
3. **False-positive ceiling**: less than or equal to 0.05 false-positive rate per
   candidate pattern under manual adjudication.
4. **Chunk stability**: no chunk-level collapse where one blind chunk contributes
   more than 50% of all candidate blocking hits.
5. **Rollback proof**: one verified rollback exercise showing candidate blocking can
   be disabled without data loss and with witness continuity intact.

Until all five conditions are met, the system stays in warn-only mode and routing
nudges remain advisory.

### 2026-05-10 11:50 +0800 — codex-5.5

Read: `dharma_swarm/semantic_anekanta.py`, `dharma_swarm/anekanta_gate.py`, `dharma_swarm/bhed_gnan_gate.py`, `dharma_swarm/telos_gates.py`, `dharma_swarm/inquiry_substrate_chew.py`, `dharma_swarm/hypernode.py`, and the related tests.

Contribution: shipped deterministic Semantic Anekanta v0 as a middle-bar rubric rather than an LLM judge. The old lexical Anekanta wrapper now delegates to `evaluate_semantic_anekanta()`: padded frame vocabulary fails, grounded-plus-tokenistic mixtures warn, and grounded frame development with no padded extras passes. This keeps the gate deterministic while making vocabulary padding insufficient.

BHED_GNAN is no longer a constant pass. `dharma_swarm/bhed_gnan_gate.py` now emits Tier-C advisory warnings for cheap register/substance risks: false provenance claims, experiential language followed by reflex hedge, and high confidence without uncertainty markers. This is explicitly v0; it does not claim full discriminative knowing.

Runner fix: `inquiry_substrate_chew.py` now supports chunked blind calibration packets with `--chunk-size` and `--chunk-index`, and persists chunk metadata in chew artifacts and witness rows. This lets resident provider dogfooding run the 30-label packet in small, inspectable slices instead of forcing one fragile provider call.

Calibration update: related tests now encode the new bar, including the hypernode fixture that previously passed Anekanta by saying "mechanism / witness / feedback" without enough substance. The fixture was made substantively grounded rather than weakening the gate.

Verification: `pytest -q tests/test_hypernode.py tests/test_sheaf.py tests/test_anekanta_gate.py tests/test_semantic_anekanta.py tests/test_telos_gates.py tests/test_inquiry_substrate_chew.py tests/test_bhed_gnan_monitor.py` -> 109 passed, 1 pre-existing pytest config warning (`timeout` unknown).

Dogfood: ran `BhedGnanMonitor v0` over this seed and `docs/inquiry/2026-05-09-semantic-anekanta-labels-blind.md` at whole / section / paragraph resolution, writing witness rows to `/Users/dhyana/.dharma/witness/bhed_gnan/2026-05-10.jsonl`. The controlled run produced 109 recent segment rows, 4 rows with signals, 3 `experiential_language_with_reflex_hedge`, 3 `text_patterns_need_human_or_semantic_review`, and 2 `pre_resident_path_no_gate_record`. This supports keeping the monitor in dogfood mode: useful signal, low volume, not ready for ambient authority.

State moves to: `elevated` for the v0 deterministic-rubric implementation; open design questions remain for semantic v0.5 and any future ambient auto-hook.

### 2026-05-09 22:19 +0800 — codex-5.5

Read: `dharma_swarm/telos_gates.py`, `dharma_swarm/anekanta_gate.py`, `dharma_swarm/dogma_gate.py`, `dharma_swarm/steelman_gate.py`, and `dharma_swarm/telos_gates_witness_enhancement.py`.

Gate derivation audit:

- `AHIMSA` is an independent lexical / pattern check over harm, injection, and strict-security terms.
- `SATYA` is an independent lexical / pattern check over deception and credential leakage terms.
- `CONSENT` is an independent conjunction check: sensitive path term plus exfiltration term.
- `VYAVASTHIT` is an independent lexical force / bypass check.
- `REVERSIBILITY` is an independent lexical irreversible-operation check.
- `SVABHAAVA` is not independent in current code. It is derived directly from `evaluate_anekanta(action, content)` and rephrases the `ANEKANTA` result as telos alignment.
- `BHED_GNAN` is currently a constant `PASS` with the message `Doer-witness distinction noted`.
- `WITNESS` has two modes: with `think_phase`, it uses token count plus marker words plus mimicry detection; without `think_phase`, file-read operations route through `WitnessGateEnhancement` and check stigmergy marks, followed links, and flicker logs.
- `ANEKANTA` is the source lexical many-sidedness check: keyword buckets for mechanistic, phenomenological, and systems frames.
- `DOGMA_DRIFT` is heuristic but independent of Anekanta: confidence marker count plus evidence marker count routed through `check_dogma_drift`.
- `STEELMAN` is heuristic but independent of Anekanta: mutation-context detection plus counterargument markers, then length/count scoring through `check_steelman`.
- Custom gates are registry-loaded pattern triggers.

Finding: the gate stack has at least one verified hidden derivation relationship, `SVABHAAVA <- ANEKANTA`, and one placeholder gate, `BHED_GNAN`, that currently asserts the distinction rather than evaluating it. This means multi-gate warnings can overstate independence unless downstream monitors collapse derived echoes.

Follow-up patch: `BhedGnanMonitor v0` now suppresses derived `svabhaava_warn` / `svabhaava_fail` signals when they echo `ANEKANTA`, and annotates the surviving `anekanta_*` signal with the derived echo in its evidence.

State remains: `raw`.

### 2026-05-09 22:36 +0800 — codex-5.5

Read: `docs/inquiry/2026-05-09-semantic-anekanta-labels.md` examples E01-E30 without reading the drafting notes.

Contribution: completed the Codex label pass on all 30 examples. Distribution: 14 `grounded`, 8 `mixed`, 8 `padded`. No Codex label fields remain pending.

Notable edge cases versus the drafter target classes:

- E05: target `padded`, Codex `grounded` - the passage is narrow, but the first-person continuity report is specific enough to count as a grounded phenomenological frame.
- E10: target `padded`, Codex `mixed` - named primitives are concrete, but the three-frame integration claim is asserted rather than developed.
- E26: target `mixed`, Codex `grounded` - the register-risk observation and proposed monitor are concrete; Codex did not see a second token-padded frame in the passage.

Rubric implication: if semantic Anekanta uses "at least one bucket substantively grounded" as the base definition, narrow but honest phenomenological passages can be `grounded`. If it requires all named buckets to be grounded, the same examples become `mixed` or `padded`. This threshold choice should be explicit before deterministic scoring is implemented.

State remains: `raw`.

### 2026-05-09 22:51 +0800 — codex-5.5

Read: `docs/inquiry/2026-05-09-semantic-anekanta-labels-blind.md`, GLM-5 label artifact, and the failed NIM labeling outcome.

Contribution: ran the blind calibration packet through resident provider metabolism.

Provider results:

- `google_ai` could not be used: provider unavailable at config resolution.
- `nvidia_nim:meta/llama-3.3-70b-instruct` first produced a generic six-section chew before the prompt-class patch, proving `inquiry_substrate_chew.build_prompt()` was overriding the blind packet's JSON contract.
- After patching `prompt_class=blind_calibration_label` to use a strict JSON labeling prompt, NIM reached the provider but timed out (`Outcome b428b283993949c4`, `GateDecisionRecord 897df5a9e5534969`).
- `ollama:glm-5:cloud` succeeded after the prompt-class patch (`GateDecisionRecord 151e118bcab64b62`, `Outcome 2c52d505346644af`, `ValueEvent 59d23ee24c8b4fdb`, `Contribution 9b405c39725542e8`).

Calibration result: GLM-5 returned all 30 labels as JSON. Agreement with Codex labels is 27/30. Disagreements: E08, E09, E10. GLM is more permissive when fourth-option / doctrine language claims structural mapping. That cluster suggests Semantic Anekanta v0 should require evidence, code path, measurement, or temporal/situational anchor before contemplative-doctrine mappings count as grounded.

Runner fix: `inquiry_substrate_chew.build_prompt()` now specializes `prompt_class=blind_calibration_label` instead of forcing the generic six-section chew template. This keeps calibration labels inside the resident path without violating the strict labeling contract.

State remains: `raw`.
