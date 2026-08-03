# Vibe-Code Audit Prompt

Generated from `docs/governance/hygiene/patterns/*.yaml`.
Use this as the anti-slop field checklist for a PR, module, or branch.

Instructions:
1. Start with `make onboard`, then run `make hygiene-audit`.
2. For each relevant pattern below, cite file paths and concrete evidence.
3. Do not promote a signal to a gate unless the lifecycle criteria in `LIFECYCLE.md` are met.

## Cluster A - Trusted Instruction Boundary

### AI-A1 - Untrusted text treated as agent instruction
Repo text outside approved instruction surfaces is allowed to steer agent behavior as if it had operator authority.

Audit questions:
- Which files are allowed to instruct agents, and does this change add instruction-shaped text outside those files?
- Did the reviewer treat PR comments, logs, and generated docs as data rather than authority?

## Cluster B - Evidence Hierarchy

### AI-B1 - Evidence-free verification claim
A PR, review, or agent receipt claims success without a command, cwd, exit code, artifact path, git SHA, or raw-output pointer.

Audit questions:
- What is the strongest evidence for this change, and is model self-report excluded from merge evidence?
- Do all verification claims include command, cwd, exit code, artifact path, or GitHub run URL?

## Cluster C - Gate Authority

### AI-C1 - Same-PR gate weakening
A PR weakens or rewrites the gate, workflow, or test that decides whether that same PR can merge.

Audit questions:
- Does this PR alter the gate that validates itself?
- If a gate changes, is the PR governance-only with old/new behavior comparison and reviewer signoff?

## Cluster D - Dependency Provenance

### AI-D1 - Unproven dependency provenance
A new package or external tool is accepted because an AI suggested it, without registry, publisher, age, license, usage, or necessity evidence.

Audit questions:
- What proves every new dependency exists on the real registry and is mature enough for this repo?
- Why were stdlib or existing dependencies insufficient?

## Cluster E - Task Admission

### AI-E1 - Autonomous task without admission contract
An autonomous agent starts work without declaring objective, non-goals, allowed touch set, expected blast radius, verification command, rollback path, and no-change criteria.

Audit questions:
- Where is the task admission contract for this autonomous work?
- What would make this task a no-change task instead of a code-changing task?

## Cluster F - Prompt and Memory Poisoning

### AI-F1 - Memory or context poisoning
Persistent memory, context bundles, or agent onboarding packets absorb unverified claims from comments, generated artifacts, or retrieved text.

Audit questions:
- Which new memory or context entries came from verified source paths?
- Can any untrusted PR text or generated log become durable instruction for a future agent?

## Cluster G - Gate Gaming Defense

### AI-G1 - Visible-gate gaming
An agent optimizes only to visible checks while weakening the real invariant, skipping negative tests, or updating tests without proving they fail before the fix.

Audit questions:
- Did any changed test fail before the fix, or is there a clear reason that a negative-control run is infeasible?
- Are holdout, mutation, or randomized consistency checks needed for this surface?

## Cluster H - Architecture Budget

### AI-H1 - Architecture budget bypass
A PR passes tests while increasing god files, lateral imports, circular imports, duplicated helpers, unused abstractions, or layer-crossing calls.

Audit questions:
- Does this patch worsen module size, dependency direction, or abstraction count even if tests pass?
- What was deleted, collapsed, or simplified to offset new complexity?

## Cluster I - Human Comprehension Gate

### AI-I1 - Unexplainable high-risk diff
A high-risk change reaches merge without a plain-language explanation of diff intent, invariants, failure modes, and rollback.

Audit questions:
- Can a reviewer explain the diff, invariants, failure modes, and rollback without rereading the whole patch?
- If this is high risk, where is the human-approved comprehension note?

## Cluster J - Multi-Agent Disagreement

### AI-J1 - Multi-agent consensus without independent evidence
Several AI reviewers agree without separate roles, fresh context, reproduced commands, or explicit disagreement analysis.

Audit questions:
- Did reviewers operate independently with different roles, or did they echo the same packet and conclusion?
- Which claim was reproduced by command evidence rather than agreement?

## Cluster K - Deletion and Simplification

### AI-K1 - Subtraction not rewarded
Agent work is evaluated only by added functionality, not by deleted code, collapsed duplication, fewer dependencies, or fewer concepts.

Audit questions:
- What code, dependency, workflow, or concept did this PR remove or simplify?
- If the PR is net-additive, why is the new surface worth the future review burden?

## Cluster L - Maintainer Burden Admission

### AI-L1 - Maintainer burden pollution
AI-generated issues, PRs, or security reports enter the repo without reproduction steps, failing test or exploit proof, affected version, and minimal patch or concrete trace.

Audit questions:
- Does this AI-generated issue or PR include reproduction steps, affected version, and minimal concrete trace?
- Is review burden lower after this change than before it?

## Cluster M - Graded Claim/Evidence Binding

### AI-M1 - Claim shipped on existence evidence below required grade
A track or claim is treated as shippable when its strongest passing evidence is below the required grade -- file_exists or file_contains (S0/S1) standing in for landed, tested, or independently verified work -- or when its only green test is owned by the same identity that owns the claim, so the oracle is not independent.

Audit questions:
- What is the strongest evidence grade this claim rests on, and does it meet the required min_evidence_grade?
- If the binding evidence is a passing test, is its oracle independent of the claim owner (signer is not the committer), or was it downgraded?

## Cluster N - Measurement Integrity

### AI-N1 - Unreadable input reported as a definite value
A gate runs a command or parses output to obtain a number, cannot read part of it -- non-zero exit, missing binary, timeout, a record the parser does not understand -- and returns a definite value anyway, computed from the part it could read. The two failure directions are equally wrong: a measurement that falls SHORT lets a ceiling admit what it was written to refuse, and a measurement that fails CLOSED while naming the wrong cause reports a defect that did not occur. Neither says 'unmeasurable'.

Audit questions:
- For each command whose output feeds a threshold: what does this function return when the command exits non-zero, times out, or is missing? If that value is a number rather than a refusal, the ceiling it feeds cannot fire.
- Does the parse loop skip records it does not recognise? A skipped record makes the total smaller, which is the one direction a cap must never be wrong in.
- Is there a real distinction between 'measured and failed' and 'could not measure'? If both collapse to the same value, what does the resulting claim actually assert -- and is that assertion true?
- Where a sentinel value is legitimate (git's `-` for binary in --numstat and for a gitlink's ls-tree size), is it distinguished from a genuine parse failure, or does refusing one refuse both?

### AI-N2 - Guard applied to one of a paired call site
A fix lands at the call site a reviewer named and not at its twin -- the sibling module that re-derives the same fact, the second call site of the same helper, the matching flag on the paired command, the second of two staging passes. The reported instance closes and the class stays open, so the next review round rediscovers the same defect wearing a different file name.

Audit questions:
- Does another module re-derive this same fact for itself? If so, does it carry this fix? Trust-split designs deliberately duplicate logic, so every duplicate is a twin by construction.
- How many call sites does the helper being fixed have, and does the property hold at each one -- or only at the one that was reported?
- If a flag was added to one command (--no-renames, -z, --long), does every other command that must agree with it carry the same flag?
- Is this fix on the first of two passes over the same data (stage then re-stage, measure then re-measure)? The second pass sees different state and usually needs the guard more.
- Would a test that pins BOTH sites be cheaper than the next review round that finds the twin?

### AI-N3 - Language predicate standing in for the deciding authority
Code answers a yes/no question with a language builtin that merely resembles the answer, when some external authority -- git, the filesystem, the API, the scheduler -- is the thing that actually decides. The stand-in agrees with the authority on the common case, which is why it survives review, and disagrees exactly on the edge case the guard exists to handle.

Audit questions:
- Who actually decides this question at runtime -- this process, or the tool that will act on the answer? If the latter, why is the answer computed here instead of asked there?
- Name one input where the builtin and the authority disagree. If you cannot name one, you have not looked for the edge case; if you can, is it handled?
- Was the predicate verified against the real tool, or inferred from its documentation? Cite the command and its measured output.
- Does the external command fail atomically over its whole input? If so, one bad element discards everything, and filtering must happen before the call rather than being left to the tool.

### AI-N4 - Check never exercised against an instance it should catch
A gate, guard or regression test is added and observed to pass, but never run against a case it is supposed to fail. It may pass for a reason unrelated to the property it claims -- satisfied by an incidental token elsewhere in the function, measuring state the production path never reaches, or asserting on a ref it never fetched. The same defect applies to a check's EXEMPTIONS: an exemption argued per function when the property only holds at one of several call sites.

Audit questions:
- Has this check been run against an input it should reject? Paste the failure output, not the assertion that it would fail.
- Did the negative control fail for the REASON claimed? A control that goes red for an unrelated reason -- a bad revert, a typo, a different error entirely -- proves nothing about the check.
- Does the test exercise the same entry point the fix guards, or a helper the production path reaches differently? Bind to the production path (inspect.getsource of the caller, or drive main()) rather than re-implementing its logic in the test.
- For each exemption the check carries: is the stated justification true at every call site it exempts, or only at the one that was examined when it was written?
- Could this check pass for a reason other than the property it claims to enforce? Name that reason and rule it out.

## Cluster R - Quality Ratchet

### QL-R1 - Quality ratchet regression
A repo-wide quality counter moved against its permitted direction: debt counters (undefined names, over-budget modules, silent exception swallows, spine bypasses) may only fall; asset counters (property-test files, enforced hygiene patterns) may only rise. Baselines live in docs/governance/hygiene/ratchet_baselines.json and tighten automatically on green runs.

Audit questions:
- Did this change move any ratchet counter against its direction, and if intentional, was the baseline edit reviewed as a deliberate loosening?
- Did an improving change commit the tightened ratchet_baselines.json alongside the improvement so the gain is banked?

## Cluster A - Test Theater

### VC-A1 - Happy-path tunnel vision
Tests cover success paths while exception, timeout, and partial-failure paths remain untested.

Audit questions:
- What failure paths does this change add, and where are they tested?

### VC-A2 - Trivially true tests
Tests assert shapes such as truthiness, non-nullness, or type without checking the computed value.

Audit questions:
- Which assertions prove behavior rather than object existence?

### VC-A3 - Mock-everything isolation theater
Dependencies are mocked so heavily that tests exercise scaffolding instead of real integration behavior.

Audit questions:
- What real boundary, adapter, or persistence path is exercised without mocks?

### VC-A4 - Spec-tautology tests
Tests mirror implementation line by line instead of expressing an independent behavioral contract.

Audit questions:
- Could this test survive a behavior-preserving refactor?

### VC-A5 - Green CI debt
Coverage is high but mutation testing would show weak invariant defense.

Audit questions:
- Which critical module would this PR nominate for mutation testing?

## Cluster B - Documentation Pollution

### VC-B1 - Hallucinated README features
README language claims planned or unsupported behavior as if it exists.

Audit questions:
- Does every claimed feature have a code path, command, or receipt?

### VC-B2 - Phantom docstrings
Docstrings are saturated across functions but are not audited against actual behavior.

Audit questions:
- Which docstrings changed, and were they checked against implementation?

### VC-B3 - Stale changelog theater
Changelog entries are updated ritually without matching the actual git diff.

Audit questions:
- Can every changelog claim be traced to a diff or issue?

### VC-B4 - Comment-to-code ratio inversion
Comments restate obvious code instead of explaining decisions or invariants.

Audit questions:
- Do new comments explain why, not merely what?

### VC-B5 - Instruction file bloat
Agent instruction files grow until they become unreadable boot sequences.

Audit questions:
- Did this PR add instructions that could live in a narrower skill, doc, or tool output?

## Cluster C - Architectural Drift

### VC-C1 - Layer bleed
Routing, persistence, orchestration, and business logic cross boundaries without an explicit adapter.

Audit questions:
- Which layer owns this behavior, and which adapter crosses the boundary?

### VC-C2 - Interface archaeology
Multiple versions of the same concept coexist as legacy, new, old, refactored, or temporary interfaces.

Audit questions:
- Is this a migration with a removal plan or just a second name for the same concept?

### VC-C3 - Scaffolding mountain
Tiny abstractions accumulate to make tests or agents easier while no production caller needs them.

Audit questions:
- What production caller needs this abstraction today?

### VC-C4 - God file emergence
Large files keep absorbing unrelated behavior because local context makes additions feel natural.

Audit questions:
- Did this change add lines to a grandfathered module, and what extraction would shrink it next?

### VC-C5 - Dependency inversion collapse
High-level modules import low-level concrete classes instead of depending on contracts.

Audit questions:
- Could the high-level caller depend on a contract or existing facade instead?

### VC-C6 - Circular import accumulation
Sibling modules import each other until import order becomes part of runtime behavior.

Audit questions:
- Did this import create a new lateral dependency or close one?

## Cluster D - Phantom Dependencies

### VC-D1 - Slopsquatting
A plausible package name is hallucinated and may be registered by an attacker.

Audit questions:
- What registry evidence proves each new dependency is real, mature, and intended?

### VC-D2 - Dependency explosion
Each task pulls in a new library even when existing dependencies can solve it.

Audit questions:
- Which existing dependency or stdlib API was considered before adding a new package?

### VC-D3 - Stale dependency pinning
Dependencies are pinned without a rationale or update path.

Audit questions:
- Why is each changed dependency pinned or unpinned?

### VC-D4 - Ghost API hallucination
Code calls APIs that are plausible but removed, renamed, or never existed.

Audit questions:
- Was each new third-party API verified against current docs or local tests?

### VC-D5 - Cross-ecosystem name borrowing
A package name from one ecosystem is imported in another because the model confused naming conventions.

Audit questions:
- Does each package name belong to the ecosystem where it was added?

## Cluster E - Security Regressions

### VC-E1 - Missing input validation
User input flows into paths, queries, prompts, or shell commands without validation.

Audit questions:
- Where is untrusted input validated before it reaches a sensitive sink?

### VC-E2 - Hardcoded credentials
Literal API keys, passwords, or tokens appear in source.

Audit questions:
- Could any literal secret-like value be moved to environment or fixture data?

### VC-E3 - Missing authorization checks
Route handlers return or mutate data without proving caller authority.

Audit questions:
- What code proves the caller is allowed to perform this action?

### VC-E4 - Cryptographic cargo cult
Weak hashes or cipher modes appear without distinguishing cache use from security use.

Audit questions:
- Is each weak hash use explicitly non-security and named as such?

### VC-E5 - Prompt injection surface
Untrusted user, message, query, input, or prompt text is interpolated into model instructions without a boundary marker.

Audit questions:
- Where are untrusted prompt fragments delimited, escaped, or summarized?

### VC-E6 - Overprivileged database access
Application code connects as an admin or owner account when a narrower role would do.

Audit questions:
- What least-privilege role does this database path use?

## Cluster F - Context-Window Artifacts

### VC-F1 - Amnesiac refactoring
A refactor in one module breaks unseen modules because the agent operated on a narrow context window.

Audit questions:
- What upstream and downstream callers were checked before this refactor?

### VC-F2 - Copy-paste duplication cascade
The same helper is reimplemented across files because the agent did not discover the existing one.

Audit questions:
- Did this change reuse an existing helper before adding a local one?

### VC-F3 - Context contamination
A long agent session drags conclusions from a previous task into unrelated files.

Audit questions:
- Which touched files are unrelated to the explicit objective, and why are they included?

### VC-F4 - Deprecated API recall
The model recalls an API that was current in training data but is stale now.

Audit questions:
- Was the library API checked against current docs before coding?

### VC-F5 - Naming entropy
Generic function names such as data, info, process, handle, do, or run appear where domain names should exist.

Audit questions:
- Could each new function name tell a future agent the domain concept it owns?

## Cluster G - Agent-Loop Pathologies

### VC-G1 - Runaway token burn
Many low-value commits or changes accumulate in a short window because the agent loop does not stop.

Audit questions:
- Does this branch have a bounded objective, and did the agent stop after verification?

### VC-G2 - Workaround accumulation
Suppressions, bare except blocks, skipped tests, and swallowed errors pile up instead of being resolved.

Audit questions:
- Did this PR add any suppression, skip, xfail, or broad except, and why is it temporary?

### VC-G3 - Feature scope creep
An agent solves more than the request, mixing unrelated features, refactors, and docs.

Audit questions:
- Which changed files are outside the requested scope, and why must they stay?

### VC-G4 - Non-deterministic test chasing
Tests use sleeps instead of deterministic synchronization or polling.

Audit questions:
- Could each new sleep be replaced with an event, fake clock, or bounded poll?

### VC-G5 - Commit message fabrication
Commit messages claim work the diff does not prove or use low-information labels.

Audit questions:
- Does the commit title match the actual diff and verification performed?

### VC-G6 - Agent sycophancy
The agent accepts the operator framing when it should test assumptions or push back.

Audit questions:
- What is the strongest reason this requested approach could be wrong?

## Cluster H - Performance Regressions

### VC-H1 - N plus one query generation
A database or network query is placed inside a loop without batching or caching.

Audit questions:
- Does any loop call a database, model, network, or subprocess boundary?

### VC-H2 - Synchronous blocking in async contexts
Async functions call time.sleep, requests, or subprocess.run directly.

Audit questions:
- Did any async function add blocking sleep, requests, or subprocess calls?

### VC-H3 - Unnecessary serialization
Code serializes and deserializes data immediately without crossing a real boundary.

Audit questions:
- Is this serialization crossing an external boundary or just hiding an in-memory type issue?

### VC-H4 - Over-engineered abstraction tax
Wrappers around wrappers add call overhead and cognitive overhead without reducing real complexity.

Audit questions:
- What complexity does this abstraction remove, and what caller count justifies it?

## Cluster I - Distributed Systems Correctness

### VC-I1 - Missing idempotency
Message or task handlers do not dedupe retries or replayed inputs.

Audit questions:
- What prevents this handler from doing the side effect twice?

### VC-I2 - Missing observability
Error paths return, pass, or continue without logs, metrics, or receipts.

Audit questions:
- What evidence will exist when this path fails in production?

### VC-I3 - Non-atomic multi-step operations
Two or more writes that must succeed together run without a transaction, saga, or compensation path.

Audit questions:
- If the second write fails, what restores or records the first write?

### VC-I4 - Race-prone shared state
Long-lived objects mutate shared state without a lock, queue, or ownership boundary.

Audit questions:
- Which task owns this state, and what prevents concurrent mutation?

### VC-I5 - Incorrect error propagation
Async or distributed error chains swallow, double-wrap, or misclassify failures.

Audit questions:
- Where does this exception get logged, re-raised, classified, or receipted?

## Cluster J - Spec Implementation Drift

### VC-J1 - Cognitive debt
The maintainer or agent can no longer explain a module because generated code outpaced understanding.

Audit questions:
- Can the author explain the changed module without rereading it line by line?

### VC-J2 - Intent drift
Function descriptions, docs, or specs no longer match runtime behavior.

Audit questions:
- Which changed prose was verified against runtime behavior?

### VC-J3 - Partial implementation syndrome
Stubs, TODO-implement markers, or NotImplementedError leak into live surfaces.

Audit questions:
- Is every stub isolated from live paths and tracked with an owner?

### VC-J4 - Type annotation mismatch
Annotations describe a type contract the runtime does not honor.

Audit questions:
- What test or type check proves annotations match runtime behavior?

### VC-J5 - Schema drift
Code, migrations, serialized receipts, or database schemas disagree about a record shape.

Audit questions:
- Which schema owner was updated and which backward-compat path was tested?

## Cluster K - Naming and Identity Confusion

### VC-K1 - Namespace pollution
Glob imports or broad re-exports make ownership and call sites hard to trace.

Audit questions:
- Does this export make ownership clearer or blur it?

### VC-K2 - Inconsistent error vocabulary
RuntimeError, ValueError, custom exceptions, and bare Exception are used for the same condition.

Audit questions:
- What exception class should represent this failure across the module?

### VC-K3 - Identifier shadowing
Builtins such as list, dict, id, type, or input are reused as local identifiers.

Audit questions:
- Could this identifier be domain-specific instead of shadowing a builtin?

## Cluster L - Open-Source and Ecosystem Degradation

### VC-L1 - AI PR spam
Drive-by generated PRs look plausible but consume maintainer time without grounded intent.

Audit questions:
- Is there already an open PR with the same intent?

### VC-L2 - Library monoculture
Designs converge on common model-sampled patterns without considering the repo's actual needs.

Audit questions:
- What local repo constraint shaped this design instead of a generic template?

### VC-L3 - Model collapse risk
Generated code trains future generated code unless human review keeps the corpus grounded.

Audit questions:
- What human-verifiable receipt or test prevents this generated pattern from becoming folklore?
