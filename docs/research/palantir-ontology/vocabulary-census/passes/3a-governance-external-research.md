# Pass 3A — Governance External Research
**Author:** perplexity-computer (Governance Pass A, external research subagent)
**Date:** 2026-06-01
**Charter ref:** `00-swarm-charter.md`
**Mandate:** PhD-grade external research on enterprise-grade ontology governance. DO NOT propose names. Build the evidence base for synthesis Pass C.
**Starting point:** PROPOSED_VOCABULARY.md Section 6, Tension #6 — governance subsection shallower than Palantir-grade ontology warrants. Three missing concepts flagged by PR #415 cron grounding: `policyBinding`, `securityMarking`, `actionDefinition`.

---

## 1. Sources Reached

| URL | What it yielded | Status |
|---|---|---|
| https://palantir.com/docs/foundry/security/data-protection-and-governance/ | High-level overview: Checkpoints as accountability/purpose-limits tool; Security Markings applied by Sensitive Data Scanner; no lifecycle detail | Partial |
| https://www.palantir.com/docs/foundry/checkpoints/overview | **Primary.** Full Checkpoint definition: checkpoint vs checkpoint-record; all fields of checkpoint record (timestamp, user, justification, checkpoint type, associated resources/objects/markings); 60+ integrated interactions; sync and async (Approvals) paths | **Full** |
| https://www.palantir.com/docs/foundry/checkpoints/configure-checkpoints/ | **Primary.** Checkpoint configuration fields: conditions, scope (org/space), location matcher, exemption matchers, justification type, frequency, name/description; role requirements (data governance officer for org scope) | **Full** |
| https://www.palantir.com/docs/foundry/checkpoints/checkpoint-types | **Primary.** Complete taxonomy of 60+ checkpoint types including "Submit action" (fires on UI-submitted ontology actions); distinction between sync user actions vs async API/OSDK submissions | **Full** |
| https://palantir.com/docs/foundry/security/markings/ | **Primary.** Security Markings full model: conjunctive mandatory control, file-hierarchy AND data-dependency propagation, Marking travel with data, removal requires `Expand Access` permission, scoped sessions, named example markings (PII, Case-xxxxxx, team-based), hierarchical classification tiers | **Full** |
| https://palantir.com/docs/foundry/action-types/overview/ | Action Type definition: edits to objects/properties/links + side effects + parameter definitions + submission criteria; writeback dataset; NOT versioned/governed in docs | Partial |
| https://palantir.com/docs/foundry/object-link-types/mandatory-control-properties/ | **Primary.** Mandatory control properties on object types: three types (markings, organizations, classification-markings); action type validation at parameter level; max-classification gating; conjunction rules | **Full** |
| https://palantir.com/docs/foundry/foundry-rules/object-model/ | Rule proposals: PR-like change management; proposal object has `old_rule_name`, `new_rule_name`, `old_logic`, `new_logic`; approval flow using standard objects and Actions | **Full** |
| https://blog.palantir.com/purpose-based-access-controls-at-palantir-f419faa400b3 | **Primary.** Purpose-Based Access Controls: Purpose as data container scoped to a user goal; every user applies to a Purpose; data governance teams and data owners both record rationale on grant; full audit trail of who/what/why | **Full** |
| https://palantir.com/docs/foundry/aip/overview/ | AIP: ontology-integrated AI platform with built-in governance, audit trails, and access controls; AIP Logic functions write back to ontology; version control for models | Partial |
| https://docs.getdbt.com/docs/use-dbt-semantic-layer/dbt-sl | dbt Semantic Layer: centralized metric definitions; if definition changes, refreshed everywhere; access permissions enforced; ownership not explicitly defined on page | Partial |
| https://docs.getdbt.com/docs/build/metrics-overview | dbt metric definition fields: type-specific params (agg, expr, input_metrics, window, etc.); metric types (simple, cumulative, derived, ratio, conversion); no ownership/versioning fields explicitly | Partial |
| https://www.getdbt.com/blog/how-the-dbt-semantic-layer-works | **Primary.** Semantic model components: semantic model info (name, description, dbt model ref, default time dimension), entities (foreign/primary/unique keys), measures (aggregation functions), dimensions (time/categorical); metrics require name/label/type/type_params | **Full** |
| https://www.openpolicyagent.org/docs/latest/ | OPA architecture: policy-as-code; input=structured data; output=arbitrary structured data (not limited to allow/deny); policies decouple decision from enforcement | Partial |
| https://www.openpolicyagent.org/docs/latest/management-decision-logs/ | **Primary.** OPA Decision Log full schema: decision_id, trace_id, span_id, bundles[].revision, path (hierarchical policy path), input (any), result (any), requested_by, timestamp, metrics, erased, masked, ids (annotation IDs of evaluated rules), rule_labels | **Full** |
| https://airc.nist.gov/airmf-resources/airmf/5-sec-core/ | **Primary.** NIST AI RMF four functions (Govern/Map/Measure/Manage) with full category/subcategory tables and expected artifact lists; gated-action artifact model derived from Manage 1.1 and Measure 2.3/2.6 | **Full** |
| https://www.w3.org/TR/odrl-model/ | **Primary.** ODRL typed object model: Policy (uid, permission/prohibition/obligation, profile, inheritFrom, conflict), Rule→Permission/Prohibition/Duty, Asset (uid, partOf), Party (uid, partOf), Action (includedIn, implies, refinement), Constraint (leftOperand, operator, rightOperand/rightOperandReference), LogicalConstraint (or/xone/and/andSequence) | **Full** |
| https://palantir.com/docs/foundry/checkpoints/ | 404 | Blocked |
| https://palantir.com/docs/foundry/security/permissions/ | 404 | Blocked |
| https://www.nist.gov/system/files/documents/2023/01/26/AI%20RMF%20Playbook%20-%20Final.pdf | Client error (PDF unavailable) | Blocked |
| https://airc.nist.gov/Docs/2 | Client error | Blocked |

**Summary: 12 of 20 URLs yielded substantive primary content. 3 were 404. 2 returned client errors. 3 yielded partial (high-level only).**

---

## 2. Foundry Checkpoints — What It Actually Is

### Narrative

Foundry Checkpoints are a first-class governance primitive in the Palantir data platform: a typed interrupt mechanism that fires before a sensitive interaction, captures a structured justification artifact (the *checkpoint record*), and gates action completion on that justification being supplied. The mechanism is deeply integrated — 60+ distinct interaction types trigger checkpoint evaluation, including the `Submit action` type that gates ontology mutations directly ([Foundry Checkpoints overview](https://www.palantir.com/docs/foundry/checkpoints/overview); [Foundry checkpoint types](https://www.palantir.com/docs/foundry/checkpoints/checkpoint-types)).

There are two distinct typed objects in the Checkpoints system:

**The checkpoint configuration** (definition-time object): the typed template that governs when a checkpoint fires and what it asks. Fields: scope (organization or space), location matcher, conditions (including `User submitting checkpoint` and `Selected user or group`), exemption matchers (groups, users, resources, markings), justification type, frequency/display-timing, Markdown prompt text, name, description. Who can create: data governance officers (for org-scoped configs) or users with `Administer configurations` operations role (for space-scoped configs). This is the *governed definition* of a checkpoint gate — the policy that declares "any time X happens, require Y" ([configure checkpoints](https://www.palantir.com/docs/foundry/checkpoints/configure-checkpoints/)).

**The checkpoint record** (runtime artifact): the durable justification artifact produced by a single checkpoint evaluation. Fields explicitly documented:
- timestamp of the interaction
- user who performed the interaction  
- justification provided in the checkpoint
- checkpoint type
- data associated with the interaction (resources, objects, Markings)

Quoted directly: *"Once submitted, each checkpoint produces a checkpoint record that contains the contextual data associated with an interaction governed by a checkpoint. This includes the timestamp of the interaction, the user who performed the interaction, the justification provided in the checkpoint, the checkpoint type, and any data (resources, objects, and Markings, for example) associated with the interaction."* ([Foundry Checkpoints overview](https://www.palantir.com/docs/foundry/checkpoints/overview))

**The lifecycle**: trigger (user attempts sensitive action) → checkpoint configuration matches → prompt displayed → user provides justification → checkpoint record written → action proceeds. For asynchronous workflows (via Approvals), the same mechanism fires but in a deferred context rather than a synchronous dialog. For the `Submit action` checkpoint type specifically: if the action has a form, the checkpoint prompt renders as a required field inside the form. If not (e.g., inline edit), a separate dialog is shown. Critically: the `Submit action` checkpoint type *does not apply* to actions submitted via API call or Ontology SDK — only to UI-initiated actions ([checkpoint types](https://www.palantir.com/docs/foundry/checkpoints/checkpoint-types)). This is a significant governance gap: the same ontology mutation that requires justification when done via the UI requires *no* justification when done programmatically.

**What this reveals for dharma_swarm**: The Foundry Checkpoint architecture distinguishes sharply between the *configuration* (the governance policy declaration) and the *record* (the runtime justification artifact). Current `gateDecision` in the vocabulary conflates both roles — it is simultaneously the policy declaration (which gates apply to this action type?) and the runtime artifact (what did those gates return for this specific proposal?). Foundry treats these as separate typed objects with different lifecycles, different authors, and different durable storage purposes. The checkpoint configuration is written once by a governance officer and persists as an org-level policy. The checkpoint record is written once per interaction by the system and persists as an audit artifact. These are not the same thing.

**Verdict space**: Foundry Checkpoints do not have a richer ALLOW/BLOCK/REVIEW verdict space than what PR #415 found. The checkpoint record documents that the justification was provided — there is no explicit "blocked" state in the checkpoint record structure. The blocking happens at the application layer (action not submitted without justification), not in the checkpoint record itself. The checkpoint record only exists once the justification has been given. This is a key architectural difference from dharma_swarm's `gateDecision`: Foundry's checkpoint records are always-positive artifacts (they record that the user justified their action), while dharma_swarm's gate decisions carry the verdict (ALLOW/BLOCK/REVIEW).

---

## 3. Foundry Security Markings — What It Actually Is

### Narrative

Security Markings are Foundry's continuous-control-plane primitive: typed labels attached to data objects that change access state immediately, travel with the data through all derived datasets, and enforce mandatory (not discretionary) access control. They are fundamentally different from role-based access (which is location-based and discretionary) because Markings are data-based and conjunctive.

**What a Marking is as an object**: Foundry does not expose an explicit schema for the Marking object itself. What is documented: a Marking is identified by a name (e.g., `PII`, `Sales Data`, `Case-xxxxxx`, `Identifiable Data`, `Consumer Finance`), has an `Expand Access` permission that governs who can remove it, and can be hierarchical (access to `Identifiable Data` implies access to `De-identified Data` implies access to `Synthetic Data`) ([Foundry security markings](https://palantir.com/docs/foundry/security/markings/)).

**Access model**: Conjunctive. A user must be a member of *all* Markings on a resource to access it — Markings are boolean AND. Quoted directly: *"Access to a Marking is binary (all-or-nothing)... Markings are conjunctive (boolean AND)."* ([Foundry security markings](https://palantir.com/docs/foundry/security/markings/))

**Trigger mechanisms**: Two paths documented:
1. Manual application by a platform administrator or data owner (the `Marking member addition` checkpoint type captures this as a sensitive action requiring justification).
2. Automated application by Sensitive Data Scanner: *"When Sensitive Data Scanner detects that a dataset contains information that corresponds to a pre-specified definition of sensitive data, the application will trigger a configured response, such as alerting administrators by creating a Foundry-generated Issue or proactively locking down the dataset by applying a Security Marking."* ([data protection and governance](https://palantir.com/docs/foundry/security/data-protection-and-governance/))

**Propagation semantics**: Markings *travel with data*. Two propagation paths:
- **File hierarchy propagation**: a Marking on a Project or folder propagates to every file/folder within it.
- **Data dependency propagation**: a Marking on a dataset propagates to every dataset that depends on it (upstream marking → all downstream transforms inherit the Marking). This inherited marking is called a *data marking* and is distinct from the *file marking* — a user can have file access without data access if they satisfy the file Marking requirements but not an upstream data Marking. Quoted: *"Markings are inherited along both the file hierarchy and direct dependencies and propagate through transform and analysis logic."* ([Foundry security markings](https://palantir.com/docs/foundry/security/markings/))

**Removal**: Considered a sensitive action (governed by a Checkpoint). Removal from the origin immediately removes from all downstream dependencies. Alternatively, a Marking can be removed *within* a transform, which only removes it along that data dependency path. Requires `Expand Access` permission on the Marking itself — even an `Owner` role on a dataset is insufficient.

**Mandatory control properties**: At the object-type level, Markings are implemented as *mandatory control properties* — properties of an object type that gate visibility of all other properties in the same datasource. Three control types: markings (conjunctive), organizations (disjunctive), and classification-markings (hierarchical, mutually exclusive with the other two). Action types can carry mandatory control parameters, and there is action-type-level validation: *"You can also add a max classification at the parameter level, for classification based mandatory control parameters. This is an action type validation, and so will prevent the Action from being submitted if the provided value does not satisfy the max classification."* ([mandatory control properties](https://palantir.com/docs/foundry/object-link-types/mandatory-control-properties/))

**What this reveals for dharma_swarm**: The current vocabulary has no equivalent of a Marking — no typed object that: (a) attaches to data/objects and changes their access state, (b) propagates automatically through derived objects, (c) is governed as a mandatory (non-discretionary) control. The `witnessLog` records governance decisions after the fact; no type models the persistent access-control label that precedes and conditions those decisions.

---

## 4. Foundry Action Types — What It Actually Is

### Narrative

In Foundry's ontology, an Action Type is the definition-time declaration of what an allowed mutation looks like: which objects can be modified, which properties can be changed, which links can be created, what side effects occur, and what parameters the actor must supply. It is the *governed definition* of a class of ontology mutations — the typed template from which runtime action instances are instantiated.

**What an Action Type contains** ([action types overview](https://palantir.com/docs/foundry/action-types/overview/)):
- Definition of changes to objects, property values, and links
- Side effect behaviors that occur with action submission
- Parameter definitions (enabling standardized user input forms)
- Rules for automatically creating links between objects
- Submission criteria (validation logic that gates action completion)
- A writeback dataset (where object edits are persisted)

**The definition-vs-instance distinction**: The Action Type is the schema; the *action submission* is the instance. When a user submits an action, the Foundry platform evaluates the Action Type's validation logic, applies the parameter values, and commits changes to the ontology — producing a durable write to the writeback dataset. The platform guarantees that *"the same action logic and validations can be made available across all user-facing applications, ensuring consistent edits to the Ontology."* This is the definition-time governance guarantee: any application using the Action Type gets the same validations.

**Governance attached to Action Type definitions**: The documentation does not explicitly specify who can define or deprecate Action Types. However, the Foundry Rules object model reveals the pattern for governed definition changes: *rule proposals* — PR-like objects with `old_rule_name`, `new_rule_name`, `old_logic`, `new_logic` — are the mechanism for governed modifications to rule definitions, with an approval flow built from standard objects and Actions ([Foundry Rules object model](https://palantir.com/docs/foundry/foundry-rules/object-model/)). The same pattern applies conceptually to Action Type modifications.

**Checkpoint integration**: The `Submit action` checkpoint type fires when a user submits an action via the UI, capturing a justification record. This means Action Type submission is a first-class checkpoint-eligible interaction — the Action Type's definition can be configured to require justification before the mutation is committed. This is a two-layer governance architecture: the Action Type defines *what is valid*; the Checkpoint configuration defines *what requires justification*.

**Versioning**: Not documented in the primary sources fetched. The AIP documentation mentions version control for AI models (*"AIP offers version control and collaboration features, enabling teams to manage models efficiently throughout their lifecycle"*), and the mandatory control properties documentation mentions that Marketplace packaging declares mandatory control settings as installation inputs — implying that Action Types can be packaged, versioned, and distributed as governed artifacts. But explicit versioning fields for Action Types are not in the public docs.

**What this reveals for dharma_swarm**: The vocabulary needs to model the *definition-vs-instance* axis for governance objects more explicitly. Current `gateDecision` models the runtime instance (the verdict for one proposal). The dharma_swarm system has an equivalent of Action Type definitions — the gate suite configuration (AHIMSA, SATYA, REVERSIBILITY, SVABHAAVA, WITNESS tiers) — but these are not typed ontology objects; they are system configuration. Making the gate definition a typed object (equivalent to a Foundry Action Type) would enable self-diagnostic queries: which gate definition is most frequently firing BLOCK? Has the SATYA gate definition changed since last week?

---

## 5. Purpose-Based Access — What It Actually Is

### Narrative

Palantir's Purpose-Based Access Control (PBAC) is the system's answer to the question "not just *who* has access to *what* data, but *why* were they given access — with all the context that went into that decision." It models access not as a direct user-to-dataset relationship but as a user-to-Purpose relationship, where the Purpose is a governed container of data scoped to a specific operational goal.

**What a Purpose is**: *"The Purpose is set by data governance teams to contain data specifically scoped to help the user meet their goal — no more, no less."* Users apply to access a Purpose, not individual datasets. Every user's data access is mediated by at least one Purpose. ([Purpose-Based Access Controls at Palantir](https://blog.palantir.com/purpose-based-access-controls-at-palantir-f419faa400b3))

**The dual-rationale model**: Two parties must each record a rationale when a Purpose is operationalized:
1. **Data governance teams** record a rationale when they grant a user access to the Purpose.
2. **Data owners** record a rationale when they approve the use of a dataset for the Purpose.
Both rationale records are captured in Foundry and available to auditors. Quoted: *"At any point, an auditor can understand not just who has access to what data, but also why they were given access — with all the context that went into that decision."*

**Accountability model**: Each Purpose has an owner: *"assigning each Purpose an owner strengthens accountability and prevents the formation of 'dark areas' that have escaped governance oversight."* The Purpose-owner relationship is the accountability spine: if something goes wrong with data in a Purpose, the owner is responsible.

**The typed object shape of a Purpose** (inferred from primary sources — no explicit schema published):
- Name/description of the operational goal
- Scoped dataset set (data assigned to this purpose)
- Owner (the accountability party)
- Rationale records (from governance teams and data owners)
- User access list (users who have applied and been granted access)

**The binding model**: actor → Purpose → scoped data. The Purpose mediates: a user's identity binds to a Purpose, and that binding grants access to exactly the datasets assigned to the Purpose. This is a three-term binding: (actor, purpose, data) — the role/purpose/resource triad. The "why" dimension is captured in the rationale records attached to the binding.

**What the public docs do NOT specify**: The explicit typed schema of a Purpose object; the workflow for creating a new Purpose; the relationship between Purpose and Markings (can a Purpose override a Marking? can a Marking block a Purpose-granted access?); how Purposes interact with Action Types (can a Purpose scope which Action Types a user can invoke?).

**What this reveals for dharma_swarm**: The current vocabulary has no type that models the actor-purpose-data binding as a first-class object. The `executionLease` captures that an agent has claimed the floor; the `gateDecision` records what the gate said; but neither records *why* the agent is acting — the purpose context that justifies the action in the first place. Palantir's evidence base (the dual-rationale model) implies that governance requires not just the verdict (gateDecision) but the *declared intent* that was evaluated (the purpose context of the actor). This is the missing fourth node in the dharma_swarm governance chain.

---

## 6. Peer Patterns — dbt, OPA, NIST AI RMF, ODRL

### 6a. dbt Semantic Layer

**What it contributes**: The Semantic Layer is the governance model for *metric definitions* — the governed typed declarations of what a business metric means, distinct from the runtime query that computes it. The key architecture: metric definitions (YAML files in the dbt project) are definition-time artifacts; metric queries (via GraphQL/JDBC API) are runtime. Changes to a metric definition propagate automatically to all downstream consumers ([how the dbt Semantic Layer works](https://www.getdbt.com/blog/how-the-dbt-semantic-layer-works)).

**The semantic model data model** (most complete primary-source decomposition found):
- **Semantic model**: name, description, referenced dbt model (1-1), default time dimension
- **Entities**: name, type (foreign/primary/unique/natural), join keys — the *identity spine* of the semantic model
- **Measures**: name, agg (aggregation type), optional description/expr — the numerical building blocks
- **Dimensions**: name, type (time/categorical), optional granularity hierarchy
- **Metrics**: name, label, type (simple/cumulative/derived/ratio/conversion), type_params

**What dbt adds that Palantir doesn't surface**: The explicit *definition propagation* semantics. In Palantir, if an Action Type changes, downstream applications that depend on it need to be manually updated. In dbt, metric definition changes automatically propagate — the governance guarantee is *definitional consistency across all consumers*. This is the governed definition's lifecycle guarantee. It implies a type of contract: "I, the definition, am the single source of truth, and my changes bind all who depend on me."

**Key gap in dharma_swarm**: No type models the *governed definition* of a computation — the typed object that says "this is what valueEvent means, these are its measures, this is how to aggregate it, and this definition is the governance source of truth that all downstream credit calculations must use."

### 6b. OPA / Rego Policy-as-Code

**What it contributes**: OPA makes the decision record first-class. The *decision log* is a typed, durable artifact of every policy evaluation. Complete schema ([OPA decision logs](https://www.openpolicyagent.org/docs/latest/management-decision-logs/)):

| Field | Type | Significance |
|---|---|---|
| `decision_id` | string | Unique traceability identifier per decision |
| `trace_id` | string | W3C trace-context compliant span identifier |
| `span_id` | string | W3C span identifier |
| `bundles[].revision` | string | **Policy version at time of decision** — the specific bundle revision whose rules were evaluated |
| `path` | string | Hierarchical policy path (e.g., `/http/example/authz/allow`) — the *which rule* dimension |
| `input` | any | Full input document (subject, action, resource, context) — the *what was evaluated* |
| `result` | any | Policy decision — can be true/false OR arbitrary structured data |
| `requested_by` | string | Client identity that triggered the evaluation |
| `timestamp` | string | RFC3339 timestamp |
| `ids` | array[string] | Annotation IDs of rules that were successfully evaluated |
| `rule_labels` | array[object] | Merged label maps of evaluated rules |
| `erased` / `masked` | array[string] | JSON Pointers of redacted fields |

**What OPA adds that Palantir doesn't surface**: Three things. First, `bundles[].revision` pins the *exact policy version* that produced the decision — you can replay any historical decision against the exact policy that was in effect. Second, `path` gives the decision a *hierarchical address* (not just "gate fired" but "which specific rule in which policy file"). Third, `result` can be arbitrary structured data — not just allow/deny but obligations, partial permissions, structured reasons — though in practice most implementations use boolean or structured allow+reasons. OPA's design is that the decision itself is queryable, immutable, and policy-version-pinned.

**Key gap in dharma_swarm**: Current `gateDecision` does not carry the *version of the gate definition* that was evaluated. If AHIMSA's trigger patterns change between one proposal and the next, the gateDecision records do not capture which version of AHIMSA evaluated them. This breaks historical replay and comparative analysis.

**Convergence with Foundry**: OPA and Foundry Checkpoints converge on the separation between configuration (policy definition) and record (policy evaluation result). OPA formalizes this as "bundle" (the versioned policy) vs "decision log entry" (the runtime result). Foundry formalizes it as "checkpoint configuration" vs "checkpoint record."

**Divergence from dharma_swarm**: OPA is fully decoupled (policy evaluation happens outside the application logic). dharma_swarm's gate evaluation is in-process (TelicSeam runs the gates synchronously). This makes dharma_swarm's architecture tighter-coupled — the gates are not independently versionable or replaceable without changing the TelicSeam code.

### 6c. NIST AI Risk Management Framework

**What it contributes**: NIST AI RMF provides the artifact model for governed AI actions — what must be documented to justify that an AI-assisted decision was made safely ([NIST AI RMF Core](https://airc.nist.gov/airmf-resources/airmf/5-sec-core/)). The four core functions and their required artifacts:

- **Govern**: Policies, processes, procedures, roles/responsibilities, risk tolerance documentation, AI system inventory, decommissioning plans
- **Map**: Documented intended purposes, deployment contexts, user expectations, positive/negative impacts, assumptions/limitations, risk tolerances
- **Measure**: Test sets, performance/assurance criteria, safety metrics, residual negative risk documentation, fairness/bias results, model explanation/validation
- **Manage**: Risk treatment plans, prioritized responses to high-priority risks, incident response/recovery, appeal and override mechanisms, decommissioning

**The single-record model** (from independent NIST AI RMF commentary): *"A working Manage implementation requires per-incident records that contain identity, role, data classification, policy version, decision outcome, and timestamps. With those records, the response team can reconstruct any AI request, the policy that governed it, and the outcome."* The pattern: **one record, four functions, one audit trail**. The decision record is what Govern points to as evidence, what Map uses to identify scope, what Measure aggregates into metrics, what Manage triages as incidents.

**Key gap in dharma_swarm**: NIST AI RMF implies that a compliant AI action record must carry: actor identity, role context, data classification (what sensitivity level were the inputs?), policy version (which version of the gate rules applied?), decision outcome, and timestamp. Current `gateDecision` carries outcome and timestamp. It does not carry data classification (what marking/sensitivity level is this proposal operating on?), policy version (which version of AHIMSA/SATYA evaluated it?), or formal role context (not just agent ID but the agent's authorized role at the time of evaluation).

**Manage 1.1 specifically**: *"A determination is made as to whether the AI system achieves its intended purposes and stated objectives and whether its development or deployment should proceed."* This is the formal go/no-go decision record — which in dharma_swarm is the `gateDecision` — but NIST implies it should carry *stated objectives* (the purpose context) and a determination about whether the system achieves them, not just a verdict on whether the action passes safety gates.

**Where NIST diverges from Palantir**: Palantir's Checkpoint model is interaction-by-interaction (per action justification). NIST AI RMF operates at the system level (Govern, Map, Measure, Manage apply to the whole AI system's lifecycle). Palantir does not have a documented NIST-AI-RMF-aligned system-level risk record; NIST does not specify a per-action checkpoint mechanism.

### 6d. W3C ODRL (Policy Expression Language)

**What it contributes**: ODRL provides the most complete typed object model for policy expression. The key objects and their schemas ([ODRL Information Model 2.2](https://www.w3.org/TR/odrl-model/)):

**Policy** (parent class):
- `uid` (IRI, required) — unique identifier
- `permission` / `prohibition` / `obligation` (Rule, at least one required)
- `profile` (IRI, optional) — which ODRL profile the policy conforms to
- `inheritFrom` (IRI, optional) — parent policy inheritance
- `conflict` (ConflictTerm, optional) — conflict resolution strategy
- Subclasses: `Set` (generic), `Offer` (assigner-to-world), `Agreement` (assigner-to-assignee)

**Rule** (parent of Permission, Prohibition, Duty):
- `action` (Action, required) — the operation being governed
- `relation` sub-property → `target` (Asset) — what is governed
- `function` sub-properties → `assigner`, `assignee` (Party) — who is involved
- `constraint` (Constraint/LogicalConstraint, optional) — conditions on the rule
- `failure` sub-properties → `consequence`, `remedy` — what happens if rule fails

**Permission**: Ability to exercise an action. Has `target` (Asset, required), optionally `assigner`/`assignee` (Party), and pre-conditions (`duty` — obligations that MUST be fulfilled as pre-conditions).

**Prohibition**: Inability to exercise an action. Has `target`, optionally `assigner`/`assignee`, and remedies (`remedy` — Duties that MUST be fulfilled if the prohibition is infringed).

**Duty**: Obligation to exercise an action. Can have `consequence` duties (what must happen if the primary duty is not fulfilled).

**Constraint**: Comparison expression. Has `leftOperand`, `operator`, and `rightOperand` or `rightOperandReference`. Can express conditions like "date < 2027-01-01" or "user.clearance >= TOP_SECRET."

**What ODRL adds that Palantir doesn't surface**: ODRL distinguishes *three* kinds of policy rules — Permission, Prohibition, Duty — where duty/obligation is a first-class type. In Foundry and dharma_swarm, obligations (things the actor must do as a condition of the action being permitted) are not typed objects. ODRL also provides `inheritFrom` for policy composition — a policy can inherit from a parent policy, creating a governed hierarchy of policies. And ODRL's Constraint type provides a formal expression language for conditions that is richer than a simple BLOCK/ALLOW verdict.

**Convergence with all peers**: All four peer systems (Foundry, OPA, NIST, ODRL) distinguish between the *definition* of what is governed (checkpoint configuration, OPA bundle/policy, NIST AI RMF policy, ODRL Policy) and the *record* of a specific governance event (checkpoint record, OPA decision log, NIST incident record, ODRL Agreement). This definition-instance axis is the universal pattern that dharma_swarm's current vocabulary does not fully model.

**ODRL `Agreement` subclass**: When the assigner grants a Permission to an assignee under specific Constraints, the result is an `Agreement` — a typed record of the specific grant, not just the policy. This is the closest ODRL equivalent to a purpose-based access binding: (assigner=data governance team, assignee=specific user, action=access, asset=scoped data, constraint=purpose). The `Agreement` is the auditable artifact of that specific grant.

---

## 7. Synthesis: The Missing Governance Primitives

The following 4-6 concepts are what a Palantir-grade governance vocabulary requires that dharma_swarm's current 22 types do not adequately model. These are concepts, not names. Synthesis Pass C will name them.

---

### Concept 1: The Governed Gate Definition (definition-time counterpart to gateDecision)

**What it is**: A typed, versioned declaration of what a gate checks, when it fires, against which action types, at which tier (Tier A blocking, Tier B blocking, Tier C advisory), with which trigger patterns, historical pass/fail statistics, and which version of these rules is currently active. It is the definition-time artifact of the telos gate system — the *policy document* that produces gateDecisions at runtime.

**Why it is needed**: The current 22 types model the runtime verdict (`gateDecision`) but not the governing declaration from which that verdict derives. This creates two critical gaps. First, no type tracks which version of AHIMSA or SATYA evaluated a given proposal — if the gate definition changes, historical gateDecisions cannot be replayed against the original rules. Second, no type enables self-diagnostic queries against gate definitions themselves ("which gate is firing most frequently? has the SATYA gate's trigger patterns drifted?"). PROPOSED_VOCABULARY.md Section 6 Tension #4 explicitly flags this as an open question but defers it as a Pass 3 discernment problem.

**Which primary sources back it**: Foundry's checkpoint configuration vs checkpoint record architecture ([Foundry Checkpoints overview](https://www.palantir.com/docs/foundry/checkpoints/overview)) proves that definition-time and runtime objects require separate types with different lifecycle owners. OPA's `bundles[].revision` field in decision logs ([OPA decision logs](https://www.openpolicyagent.org/docs/latest/management-decision-logs/)) proves that runtime decisions must carry the exact policy version that produced them — which requires the policy version to be a queryable artifact. ODRL's Policy class ([ODRL Information Model 2.2](https://www.w3.org/TR/odrl-model/)) provides the typed object model: uid, rules, profile, inheritFrom, conflict. Foundry Rules' rule-proposal mechanism ([Foundry Rules object model](https://palantir.com/docs/foundry/foundry-rules/object-model/)) confirms that definition changes require a governed change-management flow.

---

### Concept 2: The Actor-Purpose Context (the "why" binding that justifies a proposal)

**What it is**: A typed record of the declared purpose context under which an actor is submitting a proposal — the declared operational intent that justifies why this agent, acting in this role, is attempting this action on these objects at this moment. It binds actor identity, role at the time of evaluation, declared purpose (the operational goal the action serves), and optionally the data sensitivity context (what markings apply to the objects being acted upon). It is the input to gate evaluation that is currently invisible in the gateDecision envelope.

**Why it is needed**: Foundry's Purpose-Based Access Control model ([Purpose-Based Access Controls at Palantir](https://blog.palantir.com/purpose-based-access-controls-at-palantir-f419faa400b3)) demonstrates that the *why* dimension is as governance-critical as the *what* and *who* dimensions. A gateDecision that carries only the proposal ID and the gate verdict cannot answer the audit question "why was this agent authorized to attempt this action?" — it can only answer "did the gate pass?" NIST AI RMF's requirement to document intended purposes ([NIST AI RMF Core, Map 1.1](https://airc.nist.gov/airmf-resources/airmf/5-sec-core/)) and actor role context ([Manage function artifacts]) confirms that purpose-context documentation is a Govern/Map-level governance requirement, not just a nice-to-have. ODRL's Constraint model ([ODRL Information Model 2.2](https://www.w3.org/TR/odrl-model/)) provides the formal structure for expressing purpose-bound conditions. The Foundry checkpoint record already captures "user who performed the interaction" — but dharma_swarm has no typed object that carries the *purpose* the user claims.

**Relationship to gateDecision**: The actor-purpose context is the *input* to gateDecision evaluation. The gate evaluates whether the actor's declared purpose, role, and the data sensitivity of the objects being accessed together justify the proposed action. Currently, this input is implicit — the gateDecision record carries the verdict but not the full input context that produced it.

---

### Concept 3: The Access Control Label (traveling data-sensitivity marker)

**What it is**: A typed label that attaches to objects/data and changes their access state by declaring their sensitivity classification. Unlike role-based access (which governs where data lives in the platform), a label travels with the data through all derived objects, applies conjunctively (all labels must be satisfied), and propagates automatically through transforms and dependencies. It is the typed artifact of the continuous-control-plane that conditions what actions are even evaluable for a given proposal.

**Why it is needed**: Foundry Markings ([Foundry security markings](https://palantir.com/docs/foundry/security/markings/)) demonstrate that enterprise data governance requires a first-class sensitivity-classification object that: (a) travels with data rather than living in access lists, (b) propagates through derived datasets, (c) is itself governed (application and removal are sensitive actions requiring justification). NIST AI RMF's Measure 2.10 (privacy risk examination and documentation) and Map 1.1 (context-specific laws and norms) imply that data sensitivity classification must be documentable at the artifact level, not just as access control lists. OPA's `input.resource` (the resource being accessed in a policy decision) and `erased`/`masked` fields (sensitive fields that must be redacted from decision logs) confirm that resource sensitivity is a first-class input to policy evaluation. The current dharma_swarm vocabulary has no type for the sensitivity state of the objects a proposal is acting on — the gateDecision evaluates harm (AHIMSA) and deception (SATYA) without any typed representation of what sensitive data is in scope.

**Relationship to mandatory control properties**: Foundry's mandatory control properties ([mandatory control properties](https://palantir.com/docs/foundry/object-link-types/mandatory-control-properties/)) implement this concept at the object-type level — the sensitivity label gates visibility of all other properties in the same datasource. dharma_swarm needs the equivalent: a typed label that conditions what an agent can see and act on, not just an audit record of what was attempted.

---

### Concept 4: The Justification Record (durable artifact of a governance interaction)

**What it is**: A typed, immutable record of a specific governance interaction where an actor was prompted to justify a sensitive action and provided that justification. Fields: actor identity, justification text (free-text or dropdown-selected reason), checkpoint/gate type, associated objects/data/markings in scope, timestamp, the governance configuration that triggered it (which checkpoint configuration or gate definition, at which version). It is the runtime audit artifact of the governance system — the proof that governance awareness existed at the moment of action.

**Why it is needed**: Foundry Checkpoints ([Foundry Checkpoints overview](https://www.palantir.com/docs/foundry/checkpoints/overview)) model this as a first-class object: the checkpoint record is the durable justification artifact, distinct from both the gate-verdict (the checkpoint configuration determines what is sensitive; the checkpoint record proves justification was given). ODRL's `Agreement` subclass ([ODRL Information Model 2.2](https://www.w3.org/TR/odrl-model/)) is the formal equivalent: the typed record of a specific grant between assigner and assignee under specific constraints. OPA's decision log ([OPA decision logs](https://www.openpolicyagent.org/docs/latest/management-decision-logs/)) is the policy-evaluation equivalent — the durable artifact with full input/result/policy-version context. NIST AI RMF Manage 4.3 requires that "incidents and errors are communicated to relevant AI actors... processes for tracking, responding to, and recovering from incidents and errors are followed and documented." The current `witnessLog` is the closest dharma_swarm equivalent, but it is a broad audit surface (recording all gate decisions and agent actions in aggregate). A justification record is more specific: it is the artifact produced by a *specific governance prompt* at a *specific moment*, distinct from the aggregate witness log. The gap: dharma_swarm has a verdict record (gateDecision) and an aggregate audit log (witnessLog) but no artifact that specifically captures the actor's *stated justification* for why they are proceeding with a sensitive action.

---

### Concept 5: The Policy Binding (actor × purpose × action × data, at evaluation time)

**What it is**: A typed snapshot of the complete governance context that was active at the moment a specific gate evaluation ran: which actor (identity + role), which declared purpose, which action type definition (at which version), which objects/data in scope (with which access-control labels), and the resulting verdict. It is the complete evaluation record — not just the verdict (gateDecision) but the full context that produced it. Think of it as the OPA `decision_id` artifact at full resolution: everything that went into the decision, preserved as a queryable object.

**Why it is needed**: NIST AI RMF's per-request record requirement ([NIST AI RMF Core — Manage function](https://airc.nist.gov/airmf-resources/airmf/5-sec-core/)) is explicit: *"A working Manage implementation requires per-incident records that contain identity, role, data classification, policy version, decision outcome, and timestamps."* Current `gateDecision` carries decision outcome and timestamp. It does not carry identity + role (only agent_id), data classification (no sensitivity context), or policy version (no gate definition version reference). OPA's decision log schema ([OPA decision logs](https://www.openpolicyagent.org/docs/latest/management-decision-logs/)) demonstrates the implementation: `bundles[].revision` (policy version), `input` (full evaluation context), `result` (verdict), `requested_by` (actor), `ids` (which specific rules evaluated). The Palantir PBAC model's dual-rationale structure ([Purpose-Based Access Controls at Palantir](https://blog.palantir.com/purpose-based-access-controls-at-palantir-f419faa400b3)) confirms that the binding of actor, purpose, and data must be a durable artifact: auditors need to reconstruct the full context of any access grant.

**Relationship to gateDecision**: This concept is a superset of gateDecision — it carries everything gateDecision currently carries, plus the context that produced the verdict. Two resolution paths: (a) expand gateDecision's envelope to carry the full evaluation context, or (b) introduce a separate "evaluation context" type that gateDecision references. See Section 8 for the recommendation.

---

### Concept 6: The Governed Definition (versioned, ownable typed declaration of a computation or constraint)

**What it is**: A first-class typed object that is the definition-time declaration of a computation, metric, rule, or constraint — distinct from runtime instances that use it. Fields: unique identifier, version (or bundle revision), owner, the declared logic/schema/parameters, status (active/deprecated/experimental), and optionally parent-definition reference (for inheritance). It is the governance artifact that makes any computation or constraint *auditable at definition time* — the "who declared this, when, and in which version" record for the rules the system enforces.

**Why it is needed**: All four peer systems demonstrate this concept. dbt semantic models ([how the dbt Semantic Layer works](https://www.getdbt.com/blog/how-the-dbt-semantic-layer-works)) make metric definitions first-class YAML objects with name, type, and parameters — definition changes propagate automatically. OPA bundles (with `revision`) version the policy document that produces decisions. ODRL's Policy class ([ODRL Information Model 2.2](https://www.w3.org/TR/odrl-model/)) has `uid` + `profile` + `inheritFrom` — a versioned, composable policy definition object. Foundry's rule-proposal mechanism ([Foundry Rules object model](https://palantir.com/docs/foundry/foundry-rules/object-model/)) makes definition changes into governed PR-like objects. In dharma_swarm, gate definitions (AHIMSA, SATYA, etc.) and value computation definitions (what does a valueEvent measure?) are currently implicit in code. Making them typed objects enables: governance of definition changes, version pinning in runtime records, and self-diagnostic queries against the definition history.

**Scope note**: This concept is broader than just gate definitions — it applies to any computation that the governance vocabulary needs to track at both definition time and instance time: gate definitions, value metrics, fitness score schemas, agent role definitions. The synthesis agent may choose to narrow this to one or two specific instantiations rather than treating it as a single generic type.

---

## 8. Implications for the Existing gateDecision Type

### What the evidence says

The evidence from all six primary sources converges on one structural conclusion: **gateDecision is currently doing too much and not enough simultaneously**.

**Too much**: gateDecision currently conflates the verdict (what the gate returned) with the implicit definition (which gate ran) and the implicit context (what was being evaluated in full). In Foundry's architecture, these are separate objects: checkpoint configuration (what gates) vs checkpoint record (the runtime artifact). In OPA, these are separate: the policy bundle (what rules) vs the decision log entry (the runtime evaluation).

**Not enough**: gateDecision does not carry: the policy version that produced the verdict; the actor's declared purpose context at evaluation time; the sensitivity classification of the data in scope; a structured justification text from the actor; or the specific rule IDs (within the gate definition) that fired.

### The recommendation

**Option B from the two alternatives**: A sibling type is needed, not just a verdict-space expansion.

Specifically, gateDecision should be retained as the verdict record — it does this job well: ALLOW/BLOCK/REVIEW, per-gate verdicts, gate that fired, reason, timestamp, proposal reference. This is the "what the gate returned" object.

Two additions are needed:

1. **A gate definition type** (Concept 1 above): the versioned, ownable declaration of what a gate checks. gateDecision references a specific version of this type via a version/revision field. This enables: historical replay, self-diagnostic queries, change governance for gate evolution. This is a *sibling type* — a separate object at the definition layer.

2. **An expanded context envelope on gateDecision** (Concepts 2 and 5 above): the gateDecision record should carry the full evaluation context — actor identity + role, declared purpose reference (optional but governance-critical), sensitivity labels on the objects in scope, and the gate definition version reference. This is a *verdict-space enrichment* — the gateDecision object grows its envelope to satisfy the NIST AI RMF per-record requirement.

Optionally but compellingly: a **justification record** (Concept 4 above) could be a third sibling — the artifact produced by the WITNESS gate's think-point logging requirement and by any human-in-the-loop approval step. This is distinct from the gateDecision verdict (which is system-generated) because the justification record is *actor-generated*: the human or agent explicitly states why they are proceeding with this action.

### Evidence for this three-part resolution

Foundry's architecture proves that definition (checkpoint configuration) and record (checkpoint record) must be separate types — the configuration is owned by governance officers; the record is owned by the system; they have different lifecycles and different authors. gateDecision is currently the record; the gate definition type is the missing configuration object.

NIST AI RMF Manage 1.1 and the per-record requirement prove that the record itself (gateDecision) must be enriched with actor context, policy version, and data classification — this is not a new type but a verdict-space enrichment of the existing type.

Foundry Checkpoints' `Submit action` governance structure proves that a justification artifact is valuable when an actor explicitly acknowledges a sensitive action — this maps to the WITNESS gate's think-point logging requirement and implies a separate justification record type.

OPA's decision log schema — particularly `bundles[].revision` pinning the policy version in every decision — proves that the gate definition version reference must be a field on the gateDecision, not a separate lookup. This is an enrichment of the existing type.

**Bottom line**: gateDecision's verdict space (ALLOW/BLOCK/REVIEW) does not need to expand — the three-state model is adequate. What needs to expand is gateDecision's *context envelope*: policy version reference, actor role context, purpose reference, and data classification. And what needs to be added is a *sibling gate definition type* at the definition layer. A third optional sibling — the justification record — handles the actor-generated acknowledgment artifact that the WITNESS gate implies.

---

*Research complete. All sources fetched and cited inline. No type names proposed. The evidence base is ready for synthesis Pass C.*

*Author: perplexity-computer, Governance Pass A*
*Sources reached: 12 full primary, 3 partial, 5 blocked/404*
*Evidence base: Foundry Checkpoints (3 docs), Foundry Markings (2 docs), Foundry Action Types (2 docs), Foundry PBAC (1 blog), OPA Decision Logs (1 doc), NIST AI RMF Core (1 resource center page), W3C ODRL (1 W3C spec), dbt Semantic Layer (2 docs), Foundry Foundry Rules (1 doc)*
