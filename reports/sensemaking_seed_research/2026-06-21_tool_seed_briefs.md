---
title: Screenshot Tool Seed Batch — Dense Briefs and Dharma Swarm Wiring Recommendations
role: report
created: 2026-06-21
source: user-supplied screenshots, cloned public repositories, public project documentation
status: research_and_integration_report
replaces: none
subordinates_to:
  - /home/ubuntu/repos/dharma-swarm/docs/AGENTS.md
  - /home/ubuntu/repos/dharma-swarm/CLAUDE.md
---

# Screenshot Tool Seed Batch — Dense Briefs and Wiring Recommendations

This report treats the screenshots as a first world-signal seed batch for the proposed Dharma Swarm ingestion/sensemaking/world-model organ. I cloned every cloneable repository I could identify into `/home/ubuntu/research/world_signal_seed_repos/`. The only direct clone issue was `career-ops/career-ops`, which returned 403 through the git proxy; I cloned the canonical public mirror `santifer/career-ops` instead. One screenshot was internally inconsistent: it labels the item as Huly but shows DocuSeal content, so both Huly and DocuSeal are included. The first two screenshots are not a repo; they are an operational-cost signal about model choice, prompt caching, and output-token minimization, so they are included as a non-cloneable practice seed.

## Clone manifest

```yaml
workspace: /home/ubuntu/research/world_signal_seed_repos
cloned:
  maybe: https://github.com/maybe-finance/maybe
  huly_platform: https://github.com/hcengineering/platform
  docuseal: https://github.com/docusealco/docuseal
  dify: https://github.com/langgenius/dify
  continue: https://github.com/continuedev/continue
  anytype_ts: https://github.com/anyproto/anytype-ts
  twenty: https://github.com/twentyhq/twenty
  papermark: https://github.com/papermark/papermark
  dspy: https://github.com/stanfordnlp/dspy
  last30days_skill: https://github.com/mvanhorn/last30days-skill
  markitdown: https://github.com/microsoft/markitdown
  headroom: https://github.com/chopratejas/headroom
  taste_skill: https://github.com/Leonxlnx/taste-skill
  agent_reach: https://github.com/Panniantong/Agent-Reach
  open_notebook: https://github.com/lfnovo/open-notebook
  career_ops: https://github.com/santifer/career-ops
  pm_skills: https://github.com/product-on-purpose/pm-skills
non_cloneable_practice_seed:
  earlystartupdays_cost_controls: screenshot-only operational guidance
integration_chosen:
  tool: MarkItDown
  reason: Existing Chetana extractor seam already existed, but only pdf/voice paths were routed through it.
  implemented_change: Added document source kind so heterogeneous documents can be ingested as staged atoms.
  test: tests/test_chetana_markitdown_document_ingest.py
```

---

## 1. Operational cost-control seed: model choice, prompt caching, and output-token minimization

```yaml
kind: practice_signal
cloneable: false
source: earlystartupdays screenshots
primary_claims:
  - choose the cheapest adequate model rather than defaulting to flagship models
  - use batch processing where latency permits
  - exploit prompt caching but audit cache TTL and hit rates
  - minimize expensive output tokens by returning IDs, labels, and structured references
Dharma_use:
  - add model-cost telemetry to provider-routing dashboards
  - add output-token budget hints to agent prompts and review receipts
  - include cache-hit and model-choice evidence in runtime truth packets
risk: underpowered models can silently degrade strategic judgment if no quality gate checks the cheaper route
```

Dense brief: This signal is not a repository, but it is one of the most directly actionable screenshots for Dharma Swarm because the organism is about to increase ingestion volume. A sensemaking organ fails economically if every signal is interpreted by the most expensive model and every intermediate step emits narrative prose. The advice maps cleanly onto Dharma’s active `provider-routing-consolidation-2026-06` track: default power-first selection may be right for high-stakes judgment, but ingestion triage, source de-duplication, metadata extraction, quote extraction, and first-pass classification should be cheaper, narrower, and more structured. The correct pattern is not blanket cheapness; it is tiered cognition. Raw capture can use deterministic parsers and small/fast models. Evidence normalization can use mid-tier models with schema constraints. High-leverage synthesis, contradiction analysis, agent proposals, and telos-impact decisions should escalate to stronger models and carry explicit receipts.

Prompt caching matters because Dharma already carries large constitutional and governance context. If the static portion of a prompt includes North Star, One Law, active tracks, source standards, and ontology schema, then dynamic signal payloads should be appended at the end so cacheable prefix tokens stay stable. But the screenshot’s warning about TTL is important: caching is not a doctrine; it is a measured runtime behavior. The system should record cache assumptions in telemetry and periodically audit whether they are still true. Output-token minimization is equally important. The world-model organ should not ask agents to write long essays at every step. It should request compact structured outputs: source IDs, confidence scores, contradiction edges, proposed owners, and next-action enums, with narrative only at promotion or human-review boundaries.

Links: [Anthropic batch processing](https://platform.claude.com/docs/en/build-with-claude/batch-processing), [Anthropic prompt caching](https://platform.claude.com/docs/en/build-with-claude/prompt-caching), [Anthropic usage/cache docs](https://platform.claude.com/usage/cache), [OpenRouter](https://openrouter.ai/), [OpenAI pricing](https://openai.com/api/pricing/), [Anthropic pricing](https://www.anthropic.com/pricing).

Recommendation: Treat cost control as a homeostatic constraint in the sensemaking organ. Add per-cycle budgets, model-tier escalation receipts, and output-token caps so ingestion grows intelligence rather than spend.

---

## 2. Maybe — open personal-finance application

```yaml
repo: maybe-finance/maybe
clone_path: /home/ubuntu/research/world_signal_seed_repos/maybe
category: open_source_vertical_application
stack: [Ruby on Rails, Hotwire, PostgreSQL, Docker]
license: AGPL-3.0
status: archived_upstream
Dharma_use:
  - exemplar of a complete vertical app released as source
  - study object for self-hostable finance UX and data models
  - possible template for venture-cell dashboards that need personal/cell finance primitives
risk:
  - archived and trademark-constrained
  - AGPL obligations if code is reused in networked services
```

Dense brief: Maybe is a strategically valuable seed not because Dharma should become a personal-finance app, but because it is a complete, coherent, production-shaped vertical product that became public after the startup closed or pivoted. That makes it unusually useful for world-model learning: it contains not only code, but also the negative-space signal of market ambition, product scope, open-source economics, self-hosting expectations, license constraints, and what a modern Rails/Hotwire financial UX looks like when it attempts to compete with closed consumer-finance tools. Dharma should read Maybe as a venture-cell anatomy specimen. What tables does a serious finance app need? How does it handle accounts, assets, liabilities, transactions, valuations, categories, imports, budgets, and dashboard summaries? Which surfaces feel essential, and which likely became maintenance debt? The archived status is itself signal: a beautiful product and active community are not sufficient if the business model cannot sustain the company.

For Dharma Swarm, Maybe can inform the Revenue and External Humans Served objective without pushing outward prematurely. Venture cells will eventually need financial observability: capital allocation, runway, experiment costs, external revenue receipts, and return-on-attention. Maybe’s domain model is not directly reusable without license and trademark care, but its shape can guide a Dharma-native economic ledger that is not just accounting, but organism metabolism. The strongest application is not to import code; it is to ingest the repository into Chetana, summarize the product architecture, derive a finance-domain ontology, and compare it against Dharma’s existing reciprocity ledger, archive fitness, cost telemetry, and provider spend. It should produce questions such as: what would an organism-level balance sheet look like, what receipts count as revenue, and when does an internal artifact become economically real?

Links: [GitHub repo](https://github.com/maybe-finance/maybe), [Docker self-hosting docs](https://github.com/maybe-finance/maybe/blob/main/docs/hosting/docker.md), [AGPL license](https://github.com/maybe-finance/maybe/blob/main/LICENSE), [final v0.6.0 release](https://github.com/maybe-finance/maybe/releases/tag/v0.6.0), [Maybe releases](https://github.com/maybe-finance/maybe/releases), [Maybe Finance](https://maybe.co/).

Recommendation: Ingest as a reference corpus, not as code to fork. Extract finance primitives into a Dharma economic-telemetry schema and use it to design a venture-cell metabolism dashboard.

---

## 3. Dify — production-ready LLM app/workflow platform

```yaml
repo: langgenius/dify
clone_path: /home/ubuntu/research/world_signal_seed_repos/dify
category: llm_application_platform
stack: [TypeScript, Python, Next.js, workflow_engine, RAG, agents, observability]
Dharma_use:
  - benchmark for visual workflow construction and app distribution
  - reference for model-provider abstraction and observability integrations
  - possible external tool adapter for non-core prototype workflows
risk:
  - platform gravity can pull Dharma into another authority surface
  - licensing/edition boundaries need review before reuse
```

Dense brief: Dify is a mature open-source LLM application platform that combines workflow orchestration, RAG pipelines, agent capabilities, model provider management, app publishing, and observability. Its relevance to Dharma is architectural, not merely functional. Dify shows what the broader market now expects from “agentic workflow” infrastructure: a visual builder, many model backends, tool/plugin surfaces, dataset management, prompt/application versioning, hosted and self-hosted deployment, and integrations with tracing tools such as Langfuse, Opik, and Phoenix. That market expectation matters because Dharma’s world-model organ will need internal operator UX. A powerful organ hidden behind ad hoc scripts will not reshape the organism; it will become another dead subsystem. Dify demonstrates the pressure toward a visible, composable control plane.

The danger is that Dify is itself a platform. If Dharma adopts it naïvely, Dify could become a parallel workflow authority, bypassing One Law, telos gates, evidence receipts, active tracks, and Chetana promotion. The right approach is adapter-first. Dify can be used as a reference for how to represent workflows, monitor model calls, and expose datasets to operators, but Dharma’s authoritative decisions must remain in its own spine, runtime truth packets, and governance documents. A possible low-risk application is to build a Dify export/import or webhook adapter that lets an experimental workflow run in Dify while emitting EvidenceReceipt-shaped artifacts back into Dharma. Another possibility is to mirror Dify’s UX affordances: flow graphs, trace panels, knowledge-base views, and model-provider matrices, while keeping actual authority inside Dharma.

Dify also matters as competitive intelligence. It indicates that generic LLM workflow builders are commoditizing quickly. Dharma should not compete by being another workflow UI. Its differentiated move is cybernetic governance: every workflow is not just an app, but a loop that senses, interprets, constrains, acts, and learns under a telos gate. Dify can inspire the interface; it should not define the organism.

Links: [GitHub repo](https://github.com/langgenius/dify), [Dify website](https://dify.ai/), [Dify docs](https://docs.dify.ai/), [self-hosting](https://docs.dify.ai/getting-started/install-self-hosted), [model providers](https://docs.dify.ai/getting-started/readme/model-providers), [Langfuse](https://langfuse.com/), [Opik](https://www.comet.com/site/products/opik/), [Arize Phoenix](https://phoenix.arize.com/).

Recommendation: Do not absorb Dify as an authority layer. Study its UX and observability, then build a thin adapter or dashboard pattern that keeps Dharma’s spine as the source of truth.

---

## 4. Continue — open coding assistant / coding-agent infrastructure

```yaml
repo: continuedev/continue
clone_path: /home/ubuntu/research/world_signal_seed_repos/continue
category: ai_coding_assistant
stack: [TypeScript, VS_Code, JetBrains, CLI, model_context]
Dharma_use:
  - reference for IDE-native agent experience and source-controlled AI checks
  - potential tool for developer-facing Dharma contributors
  - benchmark for context providers and model routing in coding workflows
risk:
  - duplicated agent surface if installed without Dharma-specific rules and receipts
```

Dense brief: Continue is a major open-source coding-assistant project focused on bringing AI help into IDEs and coding workflows. The screenshot frames it as a free/open alternative to paid coding tools; the deeper signal is that coding assistance is moving from chat windows into source-controlled, local, extensible systems. Continue’s repository and documentation expose a set of patterns Dharma should study: context providers, slash commands, model configuration, IDE extension packaging, local and remote models, CLI surfaces, and now source-controlled AI checks. This is directly relevant because Dharma Swarm is not only a codebase; it is an agentic development environment. Its contributors and child agents need repo-native context, guardrails, and frictionless access to the right source materials.

Dharma should not simply add another coding assistant. It already has strong rules, onboarding, skills, governance gates, and model-routing consolidation work underway. The leverage is to examine Continue’s context-provider model and ask how Dharma’s Memory Kernel, active tracks, orientation graph, and Chetana atoms could be exposed as IDE-native context without duplicating truth. Imagine a contributor opening a file and seeing not just semantic code search, but the current active track, owning surface, relevant invariants, recent evidence receipts, and allowed/non-goal boundaries. Continue’s integration points could inspire that experience.

For the sensemaking organ, Continue is less about ingesting the external world and more about shortening the loop from interpretation to implementation. If world-model analysis proposes a code change, the human/agent who executes it should have the relevant evidence and constraints at edit time. Continue’s architecture suggests a future “Dharma Context Provider” that reads generated repo context and Chetana summaries, not a new memory store. The failure mode is serious: if Continue-like tooling is allowed to recommend changes without telos awareness, it increases code velocity while weakening organism coherence. Any integration must carry Dharma’s rules into the IDE and emit receipts when AI-generated edits are accepted.

Links: [GitHub repo](https://github.com/continuedev/continue), [Continue docs](https://docs.continue.dev/), [Continue website](https://www.continue.dev/), [VS Code extension](https://marketplace.visualstudio.com/items?itemName=Continue.continue), [JetBrains plugin](https://plugins.jetbrains.com/plugin/22707-continue), [source-controlled AI checks](https://docs.continue.dev/customize/deep-dives/ai-code-review).

Recommendation: Treat Continue as a UI/context-provider reference. Build a Dharma-aware coding-context adapter only if it projects existing truth and never becomes an independent agent authority.

---

## 5. DocuSeal — open document filling and signing

```yaml
repo: docusealco/docuseal
clone_path: /home/ubuntu/research/world_signal_seed_repos/docuseal
category: document_workflow_and_esignature
stack: [Ruby, PDF, API, webhooks, storage]
license: AGPL-3.0
Dharma_use:
  - external receipt capture for contracts, attestations, consent, and countersignatures
  - possible One Wire evidence tool for real-world human acknowledgements
risk:
  - e-signature legal validity varies by jurisdiction and workflow
  - AGPL obligations and sensitive document handling require isolation
```

Dense brief: DocuSeal is a high-leverage practical tool because Dharma’s world eventually needs external proof, not just internal conviction. It is an open-source alternative to DocuSign that supports PDF form building, signatures, multiple submitters, email automation, API/webhooks, storage backends, and embeddable signing flows. For a system governed by One Wire external receipts, document signature infrastructure can become a bridge between internal agentic work and human/legal/social acknowledgment. A signed document is not sufficient proof that value occurred, but it is a stronger artifact than a chat message or self-reported completion.

The screenshot mismatch matters: the slide labels the item as Huly but shows DocuSeal. That itself is a sensemaking lesson. Ingestion must preserve source uncertainty and contradiction. A robust world-signal organ should not silently normalize inconsistent screenshots; it should emit a contradiction note and include both hypotheses. DocuSeal’s relevance is strongest for future venture cells: proposals, letters of intent, consent forms, partnership agreements, invoices, service acknowledgements, and countersigned “external human acted” receipts. The current organism should not wire DocuSeal into runtime action yet. Instead, it should define a document-receipt adapter shape: a submission ID, signer identity, document hash, timestamp, webhook event, storage pointer, and telos purpose. That adapter could eventually feed One Wire quorum without letting signatures directly mutate archive fitness.

DocuSeal also offers a useful product architecture pattern: a focused open-source vertical app with API-first embedding. It does one narrow real-world workflow and exposes hooks. Dharma should prefer this kind of external integration over broad platform adoption when it reaches outward. The risk profile is mostly about sensitive data and legal overclaiming. A signature platform must not become the arbiter of truth; it can only provide one evidence type in a larger receipt chain.

Links: [GitHub repo](https://github.com/docusealco/docuseal), [DocuSeal website](https://www.docuseal.com/), [live demo](https://demo.docuseal.tech/), [API documentation](https://www.docuseal.com/docs/api), [JavaScript SDK](https://github.com/docusealco/docuseal-js), [embedding docs](https://github.com/docusealco/docuseal/blob/master/docs/embedding/form-builder-javascript.md), [AGPL license](https://github.com/docusealco/docuseal/blob/master/LICENSE).

Recommendation: Do not integrate now as an action surface. Define it as a future external-receipt adapter for signed human attestations, gated behind One Wire and explicit privacy rules.

---

## 6. Huly — all-in-one team/project/workspace platform

```yaml
repo: hcengineering/platform
clone_path: /home/ubuntu/research/world_signal_seed_repos/huly-platform
category: team_workspace_platform
stack: [TypeScript, Svelte, collaboration, project_management, CRM, HR, chat]
Dharma_use:
  - reference for integrated workspace UX across tasks, docs, chat, CRM, planning
  - possible benchmark for operator dashboards and active-track views
risk:
  - large platform surface with many overlapping concepts
  - high risk of becoming a duplicate task/document truth store
```

Dense brief: Huly is an ambitious integrated workspace platform combining project management, documents, chat, CRM, HR/ATS-like modules, and GitHub synchronization. Its strategic signal is that modern work tools are converging: teams do not want one issue tracker, one wiki, one chat system, one CRM, and one calendar; they want a coordinated workspace where work objects are linked. Dharma already has this convergence internally, but in a more organismic and governance-heavy form: active tracks, Chetana, A2A, runtime receipts, dashboards, and operator state are all different projections of one living system. Huly can help Dharma see what an operator-grade interface might feel like when these projections become usable.

The danger is obvious: Huly is a giant workspace platform. Importing it as infrastructure would likely create a parallel source of truth for tasks, documents, communication, and status. That would violate the doctrine that read models project truth from owners; they do not become authority. The correct use is comparative design. Study Huly’s object model, workspace navigation, bidirectional GitHub sync, and collaboration affordances. Then ask: what would the Dharma equivalent look like if every object carried evidence, owner surface, telos relevance, and loop-closure status? Huly’s project boards and docs can inform the shape of an operator console, but Dharma’s ACTIVE_TRACK.yaml, reports, receipts, and Memory Kernel must remain authoritative.

For sensemaking, Huly is especially useful as a warning against fragmentation. A world-model organ will generate signals, decisions, proposed agents, tasks, dashboards, and memory updates. If those land in separate tools, the loop stays open. Huly’s value is showing the appeal of unified surfaces. Dharma should build unification through projections over existing owners, not by copying Huly’s storage. A future “World Pulse board” could borrow Huly-like UX patterns: inbox, linked tasks, docs, status, conversation, and owner views, while remaining read-only until a telos-gated action is explicitly proposed.

Links: [GitHub repo](https://github.com/hcengineering/platform), [Huly website](https://huly.io/), [open-source platform page](https://v1.huly.io/), [architecture overview](https://github.com/hcengineering/platform/blob/develop/ARCHITECTURE_OVERVIEW.md), [API client docs](https://github.com/hcengineering/huly.core/tree/main/packages/api-client), [Huly docs](https://docs.huly.io/).

Recommendation: Use Huly as a UX and object-linking reference for operator dashboards. Do not adopt it as a task/doc authority layer.

---

## 7. Anytype — local-first encrypted knowledge OS

```yaml
repo: anyproto/anytype-ts
clone_path: /home/ubuntu/research/world_signal_seed_repos/anytype-ts
category: local_first_knowledge_os
stack: [TypeScript, Electron, Go, any-sync, P2P, E2EE]
Dharma_use:
  - reference for private/local-first knowledge graphs and object databases
  - comparison point for Chetana and Memory Kernel UX
risk:
  - source-available license limits reuse
  - P2P encrypted sync is a deep infrastructure commitment
```

Dense brief: Anytype is a local-first, peer-to-peer, end-to-end encrypted knowledge OS. Its importance for Dharma is philosophical and architectural. Dharma’s memory system wants to be living, trusted, provenance-aware, and organism-shaping. Anytype shows a mature adjacent answer to the personal/team knowledge problem: local ownership, composable objects, offline-first storage, sync, privacy, and user-defined data models. It is not merely a note app; it is an attempt to let users model reality through objects and relations without surrendering data to a cloud authority.

Dharma should study Anytype because Chetana and Memory Kernel need similar properties at a different level of rigor. Chetana atoms already distinguish staged from promoted knowledge and require provenance on promotion. Anytype emphasizes user control and local-first persistence; Dharma adds telos gates, signatures, evidence receipts, and active-track consequences. The synthesis is powerful: a world-model organ should feel like a knowledge OS, but every object should also know its source, confidence, contradictions, owner, stale-after date, and action implications. Anytype’s UI/UX around spaces, objects, relations, and databases can help shape a future Chetana Palace or World Pulse interface.

The technical warning is that Anytype’s deepest value comes from its sync protocol and object system. Pulling that infrastructure into Dharma would be a major architecture decision and likely premature. Instead, Dharma should ingest Anytype as a design reference and compare its local-first philosophy with existing Memory Kernel ownership. It might inspire a “private world-model workspace” where raw signals stay local/staged until promoted, and where sensitive source material never leaves the machine without explicit action. This is especially relevant as ingestion expands into documents, videos, social posts, and possible external accounts. The organism should not confuse more connectivity with more sovereignty.

Links: [Anytype desktop repo](https://github.com/anyproto/anytype-ts), [Anytype website](https://anytype.io/), [Anytype iOS repo](https://github.com/anyproto/anytype-swift), [any-sync protocol](https://github.com/anyproto/any-sync), [anytype-heart](https://github.com/anyproto/anytype-heart), [Anytype docs](https://doc.anytype.io/), [Any Source Available License](https://github.com/anyproto/anytype-ts/blob/develop/LICENSE.md).

Recommendation: Use Anytype as a design and sovereignty reference for Chetana/Memory Kernel interfaces. Do not reuse code without license review or adopt its sync stack prematurely.

---

## 8. TwentyCRM — open CRM designed for AI

```yaml
repo: twentyhq/twenty
clone_path: /home/ubuntu/research/world_signal_seed_repos/twenty
category: crm_and_business_object_platform
stack: [TypeScript, React, NestJS, PostgreSQL, Redis, Nx]
Dharma_use:
  - reference for external-human relationship objects and venture-cell CRM
  - possible schema inspiration for contacts, companies, opportunities, workflows
risk:
  - CRM concepts can prematurely bias Dharma toward sales motion before internal coherence
```

Dense brief: Twenty is an open-source CRM positioned as an alternative to Salesforce and increasingly “designed for AI.” Its strategic relevance is that CRM is the memory system of outward-facing organizations. If Dharma eventually serves external humans, launches venture cells, runs partnerships, or manages opportunities, it will need a relationship model: people, organizations, conversations, commitments, stages, workflows, value exchanged, and follow-up. Twenty offers a modern object-centric CRM architecture with customizable objects, views, roles, workflows, email/calendar/file integrations, and developer-friendly extension patterns.

For Dharma, Twenty should be read as a future external-context substrate, not as a product to install today. The user’s intuition was that Dharma should not push outward before building a sensemaking organ. Twenty helps define what outward readiness will require. A world signal that implies “contact this founder,” “track this company,” or “open this opportunity” needs somewhere to land. It should not become a loose note. It should become a relationship/opportunity object with provenance, confidence, telos relevance, and action gates. Twenty’s schema can inspire those objects, especially around companies, people, opportunities, views, and workflows. But Dharma’s version must be more ethically and cybernetically constrained than a normal CRM: no outreach without One Wire conditions, no archive-fitness updates from internal speculation, no sales automation without external receipts.

Twenty also matters because CRM is becoming programmable and AI-native. The rise of AI-designed CRMs suggests that external relationship management will soon be agent-mediated by default. Dharma should prepare by defining its own external-human ledger before adopting generic sales tooling. Otherwise, market tools will impose their ontology: leads, deals, conversion, revenue. Dharma may need richer primitives: service, reciprocity, consent, trust, harm, dharma-fit, and witnessed value.

Links: [GitHub repo](https://github.com/twentyhq/twenty), [Twenty website](https://twenty.com/), [self-hosting docs](https://twenty.com/developers/section/self-hosting), [developer docs](https://twenty.com/developers), [roadmap](https://github.com/twentyhq/twenty/discussions/categories/roadmap), [GraphQL/API docs](https://twenty.com/developers/section/api-and-sdk), [license](https://github.com/twentyhq/twenty/blob/main/LICENSE).

Recommendation: Extract a Dharma-native external relationship/opportunity schema from Twenty’s object model, but keep actual outreach and CRM mutation behind future external-action gates.

---

## 9. Papermark — open DocSend alternative with analytics

```yaml
repo: papermark/papermark
clone_path: /home/ubuntu/research/world_signal_seed_repos/papermark
category: document_sharing_and_engagement_analytics
stack: [Next.js, TypeScript, Prisma, PostgreSQL, Tinybird, NextAuth, Stripe]
Dharma_use:
  - evidence of external engagement with proposals/reports/decks
  - possible analytics adapter for world-facing venture-cell artifacts
risk:
  - page-view analytics are attention signals, not proof of value
  - sensitive document sharing requires privacy and access-control discipline
```

Dense brief: Papermark is an open-source alternative to DocSend, focused on secure document sharing, custom links, data rooms, custom branding, and analytics such as visitor activity and page-level engagement. For Dharma, this is a high-leverage external-signal tool because it sits between internal artifact creation and real-world reception. A proposal, synthesis, research packet, investor deck, or service report is not externally meaningful merely because Dharma produced it. It becomes more real when someone outside opens it, reads it, shares it, responds to it, signs it, pays for it, or acts on it. Papermark covers the early part of that ladder: access and attention.

The distinction matters. Papermark analytics should never be treated as external value receipts by themselves. Page views can be curiosity, bots, accidental clicks, or shallow attention. But they are useful algedonic signals: did a human reach page 7, did they dwell on the pricing section, did a partner revisit the proposal, did a prospect forward it? These signals can shape follow-up prioritization and artifact design. For a future Dharma venture cell, Papermark could provide a low-friction evidence adapter: document ID, link ID, visitor, page dwell, completion percentage, timestamp, and possibly email gate identity. This could feed a read-only “external attention” panel while remaining below stronger proof types like signed agreements, replies, payments, or acted receipts.

Papermark also has product lessons. It turns documents into instrumented objects with APIs, CLI, MCP, data rooms, and analytics. Dharma’s reports could benefit from a similar mental model: every outward artifact should carry identity, intended audience, hypothesis, expiry, engagement evidence, and next-action rules. The risk is surveillance creep and vanity metrics. A mature sensemaking organ should treat document analytics as noisy evidence requiring triangulation.

Links: [GitHub repo](https://github.com/papermark/papermark), [Papermark website](https://www.papermark.com/), [developer/API page](https://www.papermark.com/dev), [OpenAPI spec](https://www.papermark.com/docs/openapi.json), [MCP server package](https://www.npmjs.com/package/@papermark/mcp-server), [CLI package](https://www.npmjs.com/package/papermark), [Tinybird](https://www.tinybird.co/).

Recommendation: Define Papermark as a future external-attention adapter for proposals and reports. Keep it read-only and explicitly below value/receipt thresholds.

---

## 10. DSPy — programming foundation models instead of prompt tinkering

```yaml
repo: stanfordnlp/dspy
clone_path: /home/ubuntu/research/world_signal_seed_repos/dspy
category: llm_programming_framework
stack: [Python, declarative_modules, optimizers, evaluation]
Dharma_use:
  - build typed, evaluable interpretation modules for world-signal pipelines
  - replace brittle prompts with signatures and optimizers where tasks repeat
risk:
  - optimization can overfit to narrow metrics if telos/evidence standards are not encoded
```

Dense brief: DSPy is one of the most important technical seeds in the batch because it addresses the exact failure mode that threatens a sensemaking organ: brittle prompting masquerading as cognition. DSPy reframes LLM work as programming with declarative modules, signatures, teleprompters/optimizers, retrieval components, and evaluation loops. Instead of hand-writing a giant prompt that says “summarize this signal and tell me what it means,” Dharma could define typed tasks such as `ExtractClaims`, `AssessSourceQuality`, `FindContradictions`, `MapToActiveTracks`, `ProposeSpecialistAgent`, and `GenerateEvidenceReceiptDraft`. Each module can have inputs/outputs, examples, tests, and measured behavior.

This is deeply aligned with Dharma’s cybernetic ambition. The organ should not be a pile of unversioned prompts. It should be a set of composable, inspectable interpretive circuits. DSPy can provide a reference architecture for that: declarative signatures, modular pipelines, optimizers that improve prompts or weights against examples, and evaluation-first development. The most important use is not generic RAG; it is repeated world-signal interpretation. For example, Dharma could maintain a gold set of signals with expected outputs: one should create a research-depth opportunity, one should be rejected as hype, one should update provider-routing assumptions, one should propose a new source, and one should trigger adversarial review. DSPy-style modules could be scored against these outcomes.

The risk is metric capture. If Dharma optimizes a module for superficial labels, it may become better at passing tests while becoming worse at wisdom. Therefore, DSPy should be used only where the output contract is narrow enough to evaluate: extraction, classification, routing suggestions, and evidence normalization. High-level strategic synthesis should remain gated by stronger review and diverse lenses. Still, DSPy is probably the best candidate for turning the sensemaking organ from prompts into programmable cognition.

Links: [GitHub repo](https://github.com/stanfordnlp/dspy), [DSPy docs](https://dspy.ai/), [getting started](https://dspy.ai/learn/programming/overview/), [signatures](https://dspy.ai/learn/programming/signatures/), [modules](https://dspy.ai/learn/programming/modules/), [optimizers](https://dspy.ai/learn/optimization/overview/), [Stanford NLP](https://nlp.stanford.edu/).

Recommendation: Use DSPy as the design reference for evaluable world-signal interpretation modules after Phase 0 wiring. Start with extraction/routing modules, not open-ended strategy.

---

## 11. Last30Days-Skill — recent social/market discourse research skill

```yaml
repo: mvanhorn/last30days-skill
clone_path: /home/ubuntu/research/world_signal_seed_repos/last30days-skill
category: agent_skill_for_recent_discourse_research
sources: [Reddit, X, YouTube, TikTok, Hacker_News, Polymarket, GitHub, web]
Dharma_use:
  - fast cultural/technical sentiment sensor for topics and tools
  - candidate source bundle for World Pulse triage
risk:
  - attention-weighted signals can amplify hype, conflict, and recency bias
```

Dense brief: Last30Days-Skill is almost exactly the kind of sensor a world-model organ needs, but it must be domesticated by evidence standards. The skill researches a topic across recent discourse surfaces—Reddit, X/Twitter, YouTube, TikTok, Hacker News, Polymarket, GitHub, and the web—then synthesizes a grounded summary. Its premise is powerful: public attention, upvotes, comments, transcripts, prediction markets, and repository activity are different kinds of collective signal. Search engines and news feeds miss much of this. For Dharma, a recent-discourse sensor can answer questions like: what are developers actually saying about Agent-Reach this month, what tools are exploding, what failure modes are users reporting, what markets imply a near-term event, what YouTube explainers are shaping narratives, and which GitHub projects are receiving real contributions rather than launch hype?

The key is not to accept popularity as truth. Last30Days can feed the raw-signal layer, not the authority layer. Its outputs should become staged Chetana atoms with source breakdown, engagement counts, timestamp windows, and confidence tags. A triage module should separate attention, credibility, novelty, Dharma relevance, and actionability. For example, a Reddit complaint is a pain signal, a Hacker News debate is technical skepticism, a Polymarket price is probabilistic crowd belief, and GitHub velocity is builder commitment. These are not interchangeable. A good Dharma adapter would preserve them as separate evidence channels.

Last30Days is also a candidate specialist skill for “cultural radar.” The organism needs sensors that are not just papers and docs. Cultural uptake can indicate closing windows of leverage. However, it must be bounded: run on explicit topics, cap frequency, include adversarial counter-sources, and require that every cycle end in a decision such as ignore, monitor, ingest, propose track, or escalate. Otherwise it becomes news addiction in agentic form.

Links: [GitHub repo](https://github.com/mvanhorn/last30days-skill), [README](https://github.com/mvanhorn/last30days-skill/blob/main/README.md), [skill file](https://github.com/mvanhorn/last30days-skill/blob/main/skills/last30days/SKILL.md), [Hacker News](https://news.ycombinator.com/), [Polymarket](https://polymarket.com/), [Reddit](https://www.reddit.com/), [GitHub search](https://github.com/search), [YouTube](https://www.youtube.com/).

Recommendation: Wire later as a bounded source sensor. Its output should go to staged Chetana/world_radar triage, never directly to active-track mutation.

---

## 12. MarkItDown — document-to-Markdown converter for AI pipelines

```yaml
repo: microsoft/markitdown
clone_path: /home/ubuntu/research/world_signal_seed_repos/markitdown
category: document_ingestion_converter
stack: [Python, CLI, library, Markdown]
Dharma_use:
  - normalize PDFs, Office docs, HTML, CSV/JSON/XML, audio/video metadata, and archives into staged text
implemented:
  - added Chetana document source kind
  - routed document ingest through existing MarkItDown extractor
  - added unit and real CLI integration tests
risk:
  - conversion is not provenance; extracted text remains untrusted until promotion
```

Dense brief: MarkItDown is the tool I wired end-to-end because it is the cleanest Phase 0 ingestion proof. It is a Microsoft Python utility and CLI that converts heterogeneous files—PDF, Office documents, spreadsheets, HTML, CSV/JSON/XML, images, audio/video-related inputs, archives, and more—into Markdown optimized for LLM/text-analysis pipelines. Dharma already had a `chetana.extractors.markitdown_ext` seam, but the ingest router only used it for `pdf` and `voice`. That meant the repository conceptually knew MarkItDown could handle DOCX/PPTX/XLSX/HTML-like documents, but the CLI could not route a generic document source through it. The integration closes that gap by adding `document` as a Chetana source kind and routing `pdf`, `document`, and `voice` through the MarkItDown extractor.

This matters more than the small diff suggests. The world-model organ will ingest screenshots, reports, decks, papers, exported docs, spreadsheets, product pages, transcripts, and PDFs. It needs a raw-to-staged seam that does not pretend conversion equals trust. MarkItDown’s correct role is syntactic normalization. It gets material into Markdown; Chetana handles atomization, source metadata, stale-after, tags, and later promotion gates. The implemented test verifies that a `.docx`-like document path is converted by a MarkItDown CLI and written as a staged atom with `kind: document`, source path, tags, and markdown body. A real end-to-end test installed MarkItDown from the cloned repo and ingested an HTML world-signal sample into an isolated Chetana staging home.

The architectural recommendation is to keep MarkItDown boring. Do not turn it into a knowledge authority. Add format coverage, file hashing, conversion receipts, and extraction notes over time, but let promotion and evidence gates decide what becomes trusted. It is the mouth of the organism, not the mind.

Links: [GitHub repo](https://github.com/microsoft/markitdown), [PyPI package](https://pypi.org/project/markitdown/), [package README](https://github.com/microsoft/markitdown/blob/main/packages/markitdown/README.md), [security considerations](https://github.com/microsoft/markitdown#security-considerations), [Microsoft open source](https://opensource.microsoft.com/), [textract comparison](https://github.com/deanmalmgren/textract).

Recommendation: Use MarkItDown as the default local document-normalization seam for Phase 0. Next improvements: file hash receipts, per-format tests, source-page spans, and failure quarantine.

---

## 13. Headroom — token/context compression layer for agents

```yaml
repo: chopratejas/headroom
clone_path: /home/ubuntu/research/world_signal_seed_repos/headroom
category: context_compression_and_retrieval
surfaces: [library, proxy, MCP_server, agent_wrap]
Dharma_use:
  - compress logs, tool outputs, large staged sources, and RAG chunks before model calls
  - possible budget guard for high-volume sensemaking cycles
risk:
  - compression can erase weak signals, contradictions, or provenance-critical details
```

Dense brief: Headroom is a context compression layer for AI agents. The screenshot claims 60–95% fewer tokens across logs, files, tool outputs, and RAG chunks, with library, proxy, and MCP surfaces. For Dharma, this belongs beside the cost-control seed: a serious world-model organ will produce too much text. Raw documents, social threads, issue discussions, logs, transcripts, and reports cannot all be fed uncompressed into expensive models. Headroom’s promise is that the system can preserve answer quality while reducing context volume and costs.

The danger is that compression is epistemic mutation. A compressor that removes “irrelevant” details may remove the one anomaly that matters: the contradiction, the quiet caveat, the minority report, the timestamp, the legal qualifier, the source uncertainty, or the exact quote needed for provenance. Dharma must treat compression as a lossy or at least mediated transform with receipts. If Headroom is used, the original must remain retrievable, and compressed outputs must identify what was removed or summarized. Headroom’s CCR-style reversible cache/retrieve pattern is therefore more interesting than raw savings. A Dharma adapter could compress only after raw material is staged and hashed; the compressed view becomes a projection used for model calls, never the canonical source.

The strongest use case is operational: large logs, repeated docs, tool output, and world-signal batches. The sensemaking organ can apply compression at specific layers: before low-stakes triage, before embedding/routing, and before dashboard summarization. It should not compress before legal/evidence extraction, provenance signing, or adversarial review unless the uncompressed original is linked and accessible. In cybernetic terms, Headroom can improve throughput but risks sensor blindness if homeostatic constraints are absent.

Links: [GitHub repo](https://github.com/chopratejas/headroom), [integration guide](https://github.com/chopratejas/headroom/blob/main/docs/integration-guide.md), [README](https://github.com/chopratejas/headroom/blob/main/README.md), [MCP concept](https://modelcontextprotocol.io/), [LiteLLM](https://www.litellm.ai/), [Claude Code](https://docs.anthropic.com/en/docs/claude-code).

Recommendation: Evaluate Headroom later as a read-model compression layer over immutable staged originals. Require original retrieval and compression receipts for any strategic use.

---

## 14. Taste-Skill — anti-slop design/aesthetic agent skill

```yaml
repo: Leonxlnx/taste-skill
clone_path: /home/ubuntu/research/world_signal_seed_repos/taste-skill
category: agent_skill_for_design_quality
surfaces: [SKILL.md, frontend_design_rules, image_to_code, redesign_audit]
Dharma_use:
  - improve dashboard/report UX quality without generic AI aesthetic defaults
  - define visual taste constraints for World Pulse and operator consoles
risk:
  - taste rules can become superficial style if not grounded in Dharma function
```

Dense brief: Taste-Skill is an agent skill intended to prevent generic AI-generated frontend output: purple gradients, centered hero sections, equal feature cards, glassmorphism, and templated SaaS aesthetics. It provides design-reading procedures, layout/motion/density dials, audit protocols, and variants for frontend generation, redesign, and image-to-code workflows. For Dharma, this matters because the sensemaking organ will need dashboards. Bad dashboards will make the organism dumber: they will hide state, encourage vanity metrics, flatten uncertainty, and make operator attention drift. Good interface design is not decoration; it is perception architecture.

Taste-Skill’s useful contribution is a disciplined refusal of defaults. Dharma’s dashboards should not look like generic AI tools. They need to express living system state: world pulse, source quality, contradiction pressure, active-track relevance, stale knowledge, action readiness, and evidence thresholds. Taste-Skill can help agents build interfaces that are specific to this ontology rather than using stock layouts. Its pre-flight and redesign-audit mentality could be adapted into a Dharma dashboard design gate: every visual component must answer what loop state it exposes, what decision it supports, what uncertainty it preserves, and what action it might trigger.

The risk is aesthetic overreach. Dharma should not install taste as an authority. It should use the skill when building human-facing dashboards, reports, and artifact interfaces. The skill’s anti-slop rules are valuable but not universal; a governance dashboard may need density and clarity over novelty. The best adaptation is a Dharma-specific design skill derived from Taste-Skill but grounded in cybernetic instrumentation: show loop closure, evidence age, confidence, source diversity, and gate status before visual flourish.

Links: [GitHub repo](https://github.com/Leonxlnx/taste-skill), [Taste Skill website](https://www.tasteskill.dev/), [main skill file](https://github.com/Leonxlnx/taste-skill/blob/main/skills/taste-skill/SKILL.md), [README](https://github.com/Leonxlnx/taste-skill/blob/main/README.md), [CHANGELOG](https://github.com/Leonxlnx/taste-skill/blob/main/CHANGELOG.md), [image-to-code skill](https://github.com/Leonxlnx/taste-skill/tree/main/skills/image-to-code-skill).

Recommendation: Use Taste-Skill as a reference when designing World Pulse and Sensemaking Health dashboards. Fork the principles, not the aesthetics, into a Dharma dashboard-quality skill.

---

## 15. Agent-Reach — CLI bundle for internet/social search surfaces

```yaml
repo: Panniantong/Agent-Reach
clone_path: /home/ubuntu/research/world_signal_seed_repos/agent-reach
category: internet_search_cli_for_agents
sources: [web, YouTube, RSS, GitHub, Twitter_X, Reddit, Bilibili, XiaoHongShu]
Dharma_use:
  - practical source-access layer for world-signal collection
  - possible operator-run playbook for configuring social/video/RSS sensors
risk:
  - many surfaces require browser login/session state and can trigger privacy or ToS issues
```

Dense brief: Agent-Reach is a pragmatic tool bundle that gives agents CLI-based access to web pages, YouTube, RSS, GitHub, Twitter/X, Reddit, Bilibili, XiaoHongShu, and other surfaces, often by composing existing tools like `yt-dlp`, `gh`, OpenCLI, Bilibili CLI, RSS parsers, and browser session state. Its value is not that it invents a new search engine; it operationalizes the messy reality that high-value signals live across many platforms with different access constraints, rate limits, logins, formats, and failure modes. For Dharma’s world-model organ, this is a concrete sensor kit.

Agent-Reach should be treated as source-access infrastructure, not as a sensemaking system. It can fetch tweets, videos, GitHub metadata, RSS feeds, comments, and web pages; Dharma must still normalize, score, cross-check, and decide. The strongest near-term use is as a playbook: when the organ needs to inspect a tool’s recent adoption, Agent-Reach-like commands can gather GitHub activity, YouTube explanations, X discourse, Reddit sentiment, HN discussion, and regional sources such as Bilibili. That raw output can flow through MarkItDown/content extraction, then into Chetana staging and world_radar triage.

The risks are significant. Some platforms require authenticated browser sessions, cookies, or desktop automation. That introduces privacy, ToS, account-safety, and reproducibility concerns. Dharma should require explicit source capability declarations: zero-config public, authenticated but read-only, login-required, paid/API, or prohibited. It should store no credentials in reports, avoid scraping sensitive/private content, and prefer official APIs or public unauthenticated access where possible. Agent-Reach also expands the sensorium so much that noise control becomes essential. Every sensor must have a purpose, budget, and downstream owner.

Links: [GitHub repo](https://github.com/Panniantong/Agent-Reach), [English README](https://github.com/Panniantong/Agent-Reach/blob/main/docs/README_en.md), [yt-dlp](https://github.com/yt-dlp/yt-dlp), [GitHub CLI](https://cli.github.com/), [OpenCLI](https://github.com/jackwener/opencli), [rdt-cli](https://github.com/public-clis/rdt-cli), [bilibili-cli](https://github.com/public-clis/bilibili-cli), [Jina Reader](https://r.jina.ai/).

Recommendation: Use Agent-Reach as a source-access playbook for explicit research runs. Do not make it a continuous crawler until governance, privacy, and budget rules exist.

---

## 16. Open Notebook — private self-hosted NotebookLM-like research assistant

```yaml
repo: lfnovo/open-notebook
clone_path: /home/ubuntu/research/world_signal_seed_repos/open-notebook
category: ai_research_notebook
stack: [FastAPI, Next.js, SurrealDB, LangGraph, multi_provider_AI]
Dharma_use:
  - reference for notebook/source/note/chat/podcast research UX
  - possible model for human-facing source collections around active tracks
risk:
  - can become a parallel research memory if not subordinated to Chetana/Memory Kernel
note: screenshot text describes a Jupyter-like data notebook, but the identifiable public Open Notebook repo is NotebookLM-like; preserve this ambiguity in source records.
```

Dense brief: The screenshot labels “Open-Notebook” as a private, powerful Jupyter alternative with database connectors. The canonical public repository I found and cloned, `lfnovo/open-notebook`, is instead an open-source, privacy-focused alternative to Google NotebookLM: users upload sources, generate notes, search semantically, chat with models, and create podcast-style outputs under self-hosted control. This mismatch should be preserved as evidence uncertainty. The cloned project is still highly relevant to Dharma because it models a research workspace around sources, notebooks, notes, chat, semantic search, and transformations—exactly the kind of human-operable surface a sensemaking organ may need.

Open Notebook’s architecture—Next.js frontend, FastAPI API, SurrealDB graph/vector database, LangGraph workflows, multi-provider AI, and content-processing libraries—shows a practical implementation of source-centered AI research. It is less governance-heavy than Dharma, but its user flows are instructive. A Dharma operator may need to open a world-signal packet, inspect its sources, ask questions, generate notes, compare summaries, and transform material into briefs. Open Notebook demonstrates how that can feel. The key difference is trust. In Dharma, generated notes must not become memory automatically. They should land as staged atoms with source links, confidence, stale-after dates, and promotion gates.

A possible future integration is not to adopt Open Notebook as memory, but to build an adapter that exports notebooks/sources/notes into Chetana staging. Another is to copy the UX pattern: source collections grouped by active track, chat over staged sources, transformations that produce candidate atoms, and podcast/audio briefings for operator review. The privacy-first/local/self-hosted posture is aligned with Dharma’s need to ingest sensitive material without leaking it to uncontrolled platforms. But it must remain subordinate to Memory Kernel and governance.

Links: [GitHub repo](https://github.com/lfnovo/open-notebook), [project website/docs](https://open-notebook.ai/), [README](https://github.com/lfnovo/open-notebook/blob/main/README.md), [configuration docs](https://github.com/lfnovo/open-notebook/blob/main/CONFIGURATION.md), [Docker deployment docs](https://github.com/lfnovo/open-notebook/tree/main/docs), [LangGraph](https://www.langchain.com/langgraph), [SurrealDB](https://surrealdb.com/).

Recommendation: Study Open Notebook as a source-workspace UX. If used, export outputs into staged Chetana atoms; never let it become a second trusted memory.

---

## 17. Career-Ops — agentic job-search operating system

```yaml
repo: santifer/career-ops
clone_path: /home/ubuntu/research/world_signal_seed_repos/career-ops
category: agentic_vertical_workflow_system
stack: [Claude_Code_skills, Go_dashboard, PDF_generation, Playwright, batch_processing]
Dharma_use:
  - reference for vertical agent skills, tracker integrity, batch evaluation, and artifact generation
  - possible pattern for venture-cell operating systems
risk:
  - domain-specific automation can cross into spammy or manipulative behavior if generalized carelessly
```

Dense brief: Career-Ops is an agentic job-search command center: it evaluates listings, scores fit, generates tailored ATS resumes/PDFs, scans company portals, tracks applications, prepares interviews, and batches work through AI coding agents. Its importance for Dharma is not the job-search domain itself, but the pattern of a complete vertical operating system built from skills, workflows, trackers, generated artifacts, integrity checks, and a dashboard. It demonstrates how an AI agent can do more than answer questions: it can run a domain pipeline end-to-end with persistent state and measurable outputs.

For Dharma, Career-Ops is a venture-cell prototype pattern. A future cell serving external humans may need a domain operating system: intake, evaluation, artifact generation, follow-up, status tracking, evidence receipts, and review. Career-Ops provides a concrete example of this shape in a high-friction human domain. It also shows the power and danger of automation. Job search involves personal identity, persuasion, application forms, follow-ups, and representation. That makes it a useful ethics testbed. Dharma should learn how Career-Ops structures workflows and trackers, but it should also add stronger consent, truthfulness, anti-spam, and external-action gates.

The project’s “skills as modes” pattern is especially relevant. Dharma already uses skills and could define specialist agent capabilities for market research, document ingestion, adversarial review, dashboard design, and external receipt verification. Career-Ops shows that skill bundles become powerful when paired with stateful trackers and generated artifacts. The sensemaking organ should do the same: not just “research tools,” but workflows that leave behind structured boards, decisions, and tests. The failure mode is agentic busywork: evaluating dozens of opportunities without a clear telos. Career-Ops should be read as an operating-system pattern that needs Dharma’s governance layer.

Links: [GitHub repo](https://github.com/santifer/career-ops), [Career-Ops website](https://career-ops.org/), [README](https://github.com/santifer/career-ops/blob/main/README.md), [releases](https://github.com/santifer/career-ops/releases), [Claude Code](https://docs.anthropic.com/en/docs/claude-code), [Playwright](https://playwright.dev/), [ATS concept](https://en.wikipedia.org/wiki/Applicant_tracking_system).

Recommendation: Use Career-Ops as a pattern library for vertical venture-cell operating systems, with Dharma-specific receipts, consent, and anti-spam gates added before any external use.

---

## 18. PM-Skills — product-management skill library for agents

```yaml
repo: product-on-purpose/pm-skills
clone_path: /home/ubuntu/research/world_signal_seed_repos/pm-skills
category: product_management_skill_library
contents: [skills, workflows, subagents, templates, guides, CI_contracts]
Dharma_use:
  - onboard product-management reasoning as specialist skills
  - structure world-signal conversion into PRDs, roadmaps, prioritization, experiments, and stakeholder updates
risk:
  - conventional PM frameworks can flatten Dharma’s nonstandard telos if used uncritically
```

Dense brief: PM-Skills is a large library of product-management skills, workflows, templates, sub-agents, and guidance intended for AI coding agents and assistants. The screenshot frames it as making someone a “10x product manager.” For Dharma, the value is more specific: it can help convert world signals into product-shaped decisions without losing structure. A sensemaking organ will discover tools, needs, market gaps, user pain, emerging standards, and opportunities. If those remain as essays, they die. Product-management primitives—problem framing, opportunity assessment, user research, prioritization, PRDs, roadmaps, experiment design, launch planning, stakeholder communication—are one way information becomes action.

Dharma should not import PM orthodoxy wholesale. Its telos is not simply shipping products faster. But the skill library can supply procedural scaffolding for specific translation steps. For example, a world signal about MarkItDown can become: user/problem, evidence, affected active tracks, candidate integration, risks, success criteria, test plan, and rollout decision. A signal about Agent-Reach can become: source-access capability, ethical constraints, required secrets, rate limits, and governance gates. PM-Skills’ best use is as a specialist “product translator” that takes already-triaged signals and generates bounded proposals for review.

The danger is that PM frameworks often privilege market legibility, velocity, and stakeholder satisfaction over organismic coherence. Dharma must wrap any PM skill in its own active-track and telos constraints. A PRD that cannot name evidence, owner surface, non-goals, and loop-closure tests should be rejected. A roadmap that ignores WIP limits and governance surfaces should not be accepted. Used correctly, PM-Skills can make the sensemaking organ less vague and more implementable. Used carelessly, it can convert Dharma’s deep vision into generic SaaS execution.

Links: [GitHub repo](https://github.com/product-on-purpose/pm-skills), [PM-Skills docs](https://product-on-purpose.github.io/pm-skills/), [platform setup guide](https://product-on-purpose.github.io/pm-skills/getting-started/platforms/), [skills CLI](https://github.com/vercel-labs/skills), [skills.sh listing](https://skills.sh/product-on-purpose/pm-skills), [Triple Diamond overview](https://product-on-purpose.github.io/pm-skills/), [Apache 2.0 license](https://github.com/product-on-purpose/pm-skills/blob/main/LICENSE).

Recommendation: Add PM-Skills concepts as optional specialist procedures for converting promoted world signals into bounded specs, roadmaps, and experiments. Keep Dharma’s active-track governance above them.

---

# Integration completed: MarkItDown into Chetana document ingest

The repo already had `dharma_swarm/chetana/extractors/markitdown_ext.py`, but Chetana only routed `pdf` and `voice` sources through it. I wired MarkItDown end-to-end by adding `document` to the Chetana `SourceKind`, exposing it in the CLI, and routing `document` through the MarkItDown extractor. I also made the extractor able to find a MarkItDown CLI installed beside the current Python executable, which matters for `.venv` installs where `markitdown` is not on the ambient shell `PATH`.

```yaml
files_changed:
  - dharma_swarm/chetana/provenance.py
  - dharma_swarm/chetana/ingest.py
  - dharma_swarm/chetana/cli.py
  - dharma_swarm/chetana/extractors/markitdown_ext.py
  - tests/test_chetana_markitdown_document_ingest.py
behavior:
  before: only pdf and voice Path sources used MarkItDown
  after: pdf, document, and voice Path sources use MarkItDown
trust_boundary:
  conversion: raw heterogeneous file -> markdown body
  staging: markdown body + source metadata -> untrusted Chetana atom
  promotion: unchanged; provenance/gates/signatures still required later
verified:
  unit_test: pytest tests/test_chetana_markitdown_document_ingest.py -q
  lint: ruff check changed files
  real_cli_e2e: isolated HOME + markitdown installed from cloned repo + chetana CLI ingest of HTML document
```

Real E2E staged atom evidence excerpt:

```yaml
source:
- kind: document
  path: /home/ubuntu/research/markitdown_e2e/world_signal.html
  captured_by: devin-e2e
tags:
- world-signal
- markitdown
body_excerpt: |
  # Dharma world signal
  MarkItDown converts heterogeneous sources into staged Chetana atoms.
```

# Recommended staged architecture after this seed batch

```yaml
phase_0_ingestion_mouth:
  now_available:
    - markitdown_document_ingest
  next:
    - add file hash receipts
    - add conversion error quarantine
    - add source span/page metadata where available
phase_1_source_sensors:
  candidates:
    - last30days_skill
    - agent_reach
    - papermark_readonly_analytics
  gates:
    - explicit source budgets
    - login/privacy classification
    - raw output must stage before interpretation
phase_2_interpretation_modules:
  candidates:
    - dspy_signatures_for_claim_extraction
    - dspy_modules_for_active_track_mapping
    - adversarial_reader_module
  constraints:
    - tests over gold signal set
    - no direct mutation of active tracks
phase_3_operator_surfaces:
  design_references:
    - huly
    - anytype
    - open_notebook
    - taste_skill
  dashboards:
    - world_pulse
    - sensemaking_health
    - source_quality
    - contradiction_pressure
phase_4_external_receipts:
  future_adapters:
    - docuseal_signed_attestations
    - papermark_attention_analytics
    - twenty_external_relationship_objects
    - maybe_style_economic_metabolism
  invariant: external artifacts never update fitness without quorum-grade acted receipts
```
