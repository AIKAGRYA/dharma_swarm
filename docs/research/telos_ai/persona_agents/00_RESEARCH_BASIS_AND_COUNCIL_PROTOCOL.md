# TELOS Persona Council - Research Basis And Run Protocol

Date: 2026-06-14
Status: v0 prompt research basis
Scope: TELOS Morning Refinery / ARTICULATE_ESSENCE_EXTRACTOR_NODE

## Why Personas, But Carefully

The council should use personas as disciplined interpretive stances, not as
costumes. Current research supports the idea that persona prompts can shift
model behavior, style, coverage, and diversity of generated material, but it
does not support the lazy claim that "expert persona" automatically improves
truth. The design principle is therefore: use personas to create different
reading vectors, then use evidence discipline and synthesis checks to prevent
beautiful overreach.

Primary source basis:

- Anthropic's prompting guidance says clear roles, context, examples, and
  structured prompts improve steerability; it also recommends XML/structured
  boundaries for complex prompts. See:
  https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/claude-prompting-best-practices
- OpenAI's prompt engineering guidance recommends explicit identity,
  instructions, examples, and context sections, and says prompts should be
  versioned in code with tests/evaluation rather than treated as loose reusable
  objects. See:
  https://developers.openai.com/api/docs/guides/prompt-engineering
- "Principled Personas" finds persona prompting has mixed effects and can be
  sensitive to irrelevant details. This argues for functional, domain-relevant
  personas with explicit output tests rather than elaborate fictional biography.
  See: https://arxiv.org/abs/2508.19764
- "Persona Hub" shows that many personas can tap diverse perspectives within an
  LLM for synthetic data and knowledge-rich generation. This supports using
  diverse lenses for idea extraction, while still requiring source discipline.
  See: https://arxiv.org/abs/2406.20094
- "RoleLLM" treats role profile construction and role-conditioned instruction as
  a systematic capability, not a magic phrase. This supports dense role prompts
  with concrete role knowledge and task-specific instruction. See:
  https://arxiv.org/abs/2310.00746
- Multi-agent debate and peer-review papers show that independent agents can
  improve reasoning and factual validity when they exchange critique, but later
  controlled work warns that group dynamics can also fail. Use independent first
  passes, then synthesis, then contradiction review. See:
  https://arxiv.org/abs/2305.14325 and https://arxiv.org/abs/2311.08152
- CAMEL and AutoGen support role-based multi-agent collaboration patterns, but
  the lesson for this council is protocol clarity, not agent theatrics. See:
  https://arxiv.org/abs/2303.17760 and https://arxiv.org/abs/2308.08155
- Generative Agents shows the value of memory, reflection, and retrieval for
  believable agent behavior. For TELOS, that means each persona needs persistent
  viewpoint memory and repeated calibration, not a fresh vague prompt each run.
  See: https://arxiv.org/abs/2304.03442
- In-context vectors and activation steering show that model behavior can be
  shaped through latent-state interventions, but natural-language persona
  prompting is only a weaker, prompt-level analog. Do not claim persona prompts
  create clean "subspaces." Treat that as a useful metaphor until measured. See:
  https://arxiv.org/abs/2311.06668, https://arxiv.org/abs/2312.06681, and
  https://arxiv.org/abs/2505.22637

## Council Design Rules

1. Every persona reads the raw or typo-clean morning page independently before
   seeing other agents' outputs.
2. Every persona must quote or paraphrase source anchors before interpretation.
3. Every persona must separate explicit source, grounded inference, and
   speculative cross-pollination.
4. No persona may praise, diagnose, coach, flatter, or convert the page into
   product language unless the source itself makes that move.
5. Each persona must output both enrichment and restraint: what this lens opens,
   and where it could distort.
6. The synthesis agent should not average the agents. It should braid
   convergences, preserve contradictions, and mark unresolved tensions.
7. A contradiction pass should run after synthesis. Its job is to find
   unsupported elevation, false coherence, decorative citations, and leaked
   product assumptions.

## Run Order

Stage 1: source normalization. Create a typo-preserving raw capture and a
typo-clean working transcript.

Stage 2: six independent readings. Use the six persona files in this directory.
Require each agent to produce source anchors, themes, cross-pollinations,
failure checks, and one distillation.

Stage 3: synthesis. Create or revise the ARTICULATE_ESSENCE_EXTRACTOR_NODE from
the six outputs. The node should be richer than the source, but still obviously
belong to the source.

Stage 4: challenge. Run a seventh critique pass: "Where did the council overread,
flatten, theologize, productize, or hallucinate?"

Stage 5: user correction. The user's correction becomes first-class data. A node
that cannot be corrected by the source person is not a living node.

