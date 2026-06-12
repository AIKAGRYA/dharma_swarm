# Register the Initiative in the v2 Hygiene System

**Created:** 2026-06-08 · **Status:** PROPOSAL (not yet committed to `dharma_swarm_pr_review_control`) · **Owner:** Dhyana + operator

This doc wires the sovereign-holon initiative into the **v2 vibe-code hygiene system** so the lessons can't be lost by any future agent or contributor. It does so by proposing **three durable hygiene patterns**, each in the standard `VC-{cluster}{NN}` format, all under a new cluster **N (identity / runtime / verification)**.

> Reminder: the v2 hygiene system lives at `dharma_swarm_pr_review_control` on the operator's machine (Codex's working copy, currently on `main` — must be moved to a feature branch before commit). Patterns live in `scripts/governance/hygiene/patterns/` as YAML. Lifecycle: `observed → measured → advisory → enforced → resolved → archived`. See [VIBE_CODE_ANTIPATTERNS_FIELD_GUIDE.md](/home/user/workspace/VIBE_CODE_ANTIPATTERNS_FIELD_GUIDE.md) (workspace asset) for the rule format.

Each pattern below is written so it can be copy-pasted into a YAML file with the obvious mechanical transforms. They are intentionally narrow: detection rules an automated check can grep for, not philosophical rules.

---

## VC-N01 — Identity Separator Drift

**Cluster:** N (identity / runtime / verification)
**Stage at proposal:** `observed` (graduate to `measured` after one full scan)
**Severity:** medium
**Owner agent:** opus_composer (handoff to operator on dispute)

### Statement

Two agent names that differ only by a separator (`-` vs `_`) are treated as the same agent by humans but as **different agents** by the registry, the NATS mailbox path, the witness path, and (often) the prompt cache key. Either both names are registered selves, or one is canonical and the other is a hard alias that errors on creation.

### Why it matters (verified evidence)

- `opus_composer` and `opus-composer` both occur in this repo's surface area (see `AGENT_NAMING_MAP.md`, top-10 census).
- The NATS bus uses the exact string in `~/.dharma/a2a_bus/inboxes/<name>/` — a separator typo writes to the wrong inbox silently.
- Anthropic prompt-cache hit rate depends on the **first stable bytes** of the prompt. A name swap busts the cache. ([NVIDIA Dynamo `--strip-anthropic-preamble` finding](https://developer.nvidia.com/blog/streaming-tokens-and-tools-multi-turn-agentic-harness-support-in-nvidia-dynamo/) shows what a variable preamble costs: 5× TTFT.)
- The dossier finding stands: 46 ginko-registered selves; agent-naming-map identified separator drift as one of four axes.

### Detection (mechanical)

A pattern is a hit if **any** of these is true:

1. `~/.dharma/ginko/agents/` contains two directories whose names are equal after `s/_/-/g`.
2. A grep over `examples/agents/*.registration.json` finds an `agent.name` field whose normalized form (lowercase, `s/_/-/g`) collides with another file's normalized form.
3. The `a2a_bus/inboxes/` directory contains two siblings that normalize equal.
4. A repo grep for `agent_id` or `AGENT_UID` constants finds two constants in different files that normalize equal.

### Required response when hit

- **observed → measured:** count occurrences per scan, store in `patterns/VC-N01/measurements/<date>.json`.
- **advisory:** opening a PR that introduces a new collision produces a warning in `hygiene-check` output.
- **enforced:** PR is blocked. The author must either pick a different name, or register both as aliases pointing to one canonical record.

### Suggested YAML skeleton

```yaml
id: VC-N01
title: Identity Separator Drift
cluster: N
stage: observed
severity: medium
owner: opus_composer
description: >
  Two agent names that differ only by '-' vs '_' are treated as distinct by
  the registry, NATS mailbox, and prompt cache but as the same by humans.
detection:
  scripts:
    - scripts/governance/hygiene/detectors/vc_n01_separator_collision.py
artifacts:
  - path: patterns/VC-N01/measurements/
remediation:
  doc: docs/sovereign_holons/03_REGISTER_AS_HYGIENE.md#vc-n01--identity-separator-drift
```

---

## VC-N02 — Cosmetic Chat Endpoint

**Cluster:** N
**Stage at proposal:** `measured` (we already have one verified instance)
**Severity:** high (it teaches the agent's voice through a stranger)
**Owner agent:** opus_composer

### Statement

A chat surface that names an agent in its UI must **route through that agent's own runtime** (its model, its `prompt_variants/active.txt`, its `task_log.jsonl`). A surface that takes the registered name as a `<persona/>` string and otherwise runs the operator's global backend is *cosmetic*, will mislead the operator and the future-self of the agent, and will silently desync from any agent evolution work.

### Why it matters (verified evidence)

- `chat_with_agent` at [`api/routers/agents.py:404-475`](file:///Users/dhyana/dharma_swarm/api/routers/agents.py) stitches name/role/model into a system-prompt string and routes through `_agentic_stream` from `api/routers/chat.py`. It does not load `prompt_variants/active.txt`, does not select the agent's model, does not replay any of the agent's history.
- The DGM-style self-improvement design depends on the agent's own model + its own prompt variants getting feedback from real use. A cosmetic chat short-circuits that loop without saying so.

### Detection (mechanical)

A pattern is a hit if a route in `api/routers/*.py` does **all** of:

1. Has `{agent_id}` (or equivalent) in its path.
2. Calls a chat backend (`_agentic_stream`, `stream_chat`, `chat_completion`, …).
3. Does **not** import from `dharma_swarm/agent_registry.py` or `dharma_swarm/holon_bridge.py`.
4. Builds its system prompt by `.format(...)` / f-string substitution of agent fields rather than by reading from a file owned by the agent.

(All four required to flag, to avoid false positives on general routes.)

### Required response when hit

- **measured:** every PR run logs the number of cosmetic routes to `patterns/VC-N02/measurements/<date>.json` (initial value: 1).
- **advisory:** any new route matching the rule produces a warning that points the author at `02_FIRST_BRICK_SPEC.md`.
- **enforced (after first brick lands):** new routes blocked unless they import `holon_bridge` or are explicitly marked `# allow-cosmetic-route: <reason>`.
- **resolved:** when `chat_with_agent` is replaced by `holon_chat` and the only cosmetic route is gone, mark resolved and link the witness PR.

### Suggested YAML skeleton

```yaml
id: VC-N02
title: Cosmetic Chat Endpoint
cluster: N
stage: measured
severity: high
owner: opus_composer
description: >
  Per-agent chat route that runs the operator's global model with a persona
  string instead of the agent's own runtime (model + active prompt + log).
detection:
  scripts:
    - scripts/governance/hygiene/detectors/vc_n02_cosmetic_chat.py
artifacts:
  - path: patterns/VC-N02/measurements/
remediation:
  doc: docs/sovereign_holons/02_FIRST_BRICK_SPEC.md
```

---

## VC-N03 — Verifier-Less Outcome Claim

**Cluster:** N
**Stage at proposal:** `observed`
**Severity:** high
**Owner agent:** opus_composer

### Statement

Any agent-emitted text that claims an outcome — "done", "updated", "committed", "passed", "created", "fixed" — must carry a `verifier_artifact` field naming a file the operator (or a *different* model) can read to confirm. Same-model self-grading is theater; the [ASL paper (ICLR 2026)](https://www.arxiv.org/pdf/2510.14253v1.pdf) shows the GRM (generative reward model) must be a *distinct* component, not the policy talking to itself.

### Why it matters (verified evidence)

- The first-brick spec ([02_FIRST_BRICK_SPEC.md](02_FIRST_BRICK_SPEC.md#the-verification-organ-built-in-from-turn-1)) builds artifact-required refusal into the very first commit. Without a hygiene pattern, future agents will drop it.
- Cognition's [Don't build multi-agents](https://cognition.ai/blog/dont-build-multi-agents) and Walden Yan's follow-up explicitly warn that adding more agents to *grade* output without a different signal is wasted intelligence.
- The repo's `fitness_history.jsonl` is empty for all 46 agents — there is no existing receipt the hygiene system can lean on.

### Detection (mechanical)

A pattern is a hit if **either**:

1. A file under `~/.dharma/holon_witness/<session>/` contains a model response with the regex `\b(done|updated|committed|passed|created|fixed)\b` and **no** `"verifier_artifact"` key in the surrounding JSON envelope.
2. A PR diff adds code in `api/routers/` or `dharma_swarm/` that constructs an outcome-claim response without writing a sibling witness file.

### Required response when hit

- **observed:** count over a 7-day window of holon witness logs.
- **measured:** publish the false-claim rate per agent.
- **advisory → enforced:** the bridge refuses to emit the response and writes a `violations.jsonl` entry instead (this is already specified in 02_FIRST_BRICK_SPEC.md acceptance criterion #4 — the hygiene pattern is the enforcement record).

### Suggested YAML skeleton

```yaml
id: VC-N03
title: Verifier-Less Outcome Claim
cluster: N
stage: observed
severity: high
owner: opus_composer
description: >
  Outcome claims ("done", "updated", "committed", "passed", "created", "fixed")
  must include a verifier_artifact pointing to a file an independent reader
  can check. Same-model self-grading is forbidden.
detection:
  scripts:
    - scripts/governance/hygiene/detectors/vc_n03_unverified_claim.py
artifacts:
  - path: patterns/VC-N03/measurements/
remediation:
  doc: docs/sovereign_holons/02_FIRST_BRICK_SPEC.md#the-verification-organ-built-in-from-turn-1
```

---

## Why three (not five, not ten)

The dossier covers many fault lines. The hygiene system is not for documenting all of them; it is for the ones that:

1. have a **mechanical detection rule** an automated check can run,
2. would otherwise be **lost over time** because the rule lives only in one human's head, and
3. relate to a **commit-time decision** — i.e. a future agent can introduce the regression in a single PR.

The other dossier findings (fail-open `_check_gate`, decorative `AutonomyPolicy`, empty `fitness_history.jsonl`) are either out-of-scope-for-the-first-brick (PDP/PEP system) or are *measurements about state* rather than *patterns about new code*. They belong in `docs/governance/` audits, not in `dharma_swarm_pr_review_control/patterns/`.

---

## Operator action items (smallest commits)

This doc proposes — it does not write the YAML for the operator. The operator-owned steps:

1. **Create a feature branch in `dharma_swarm_pr_review_control`** (it is on `main` with uncommitted v2 work — that is its own hygiene issue, separate from this PR).
2. **Add three YAML files** under `scripts/governance/hygiene/patterns/vc_n01_*.yaml`, `vc_n02_*.yaml`, `vc_n03_*.yaml`, copying the skeletons above.
3. **Stub the three detectors** in `scripts/governance/hygiene/detectors/`. Each detector can be ~30 LOC for stage `observed` (just emit `{"hits": 0}` so the lifecycle counts work).
4. **Register the three IDs** in whatever pattern-index file the v2 system uses (per the v2 design, this is auto-discovered from the `patterns/` directory — no manual index edit needed).
5. **Add to `make onboard`** output (already wired by the prior hygiene PR): a line that says *"Sovereign Holons initiative: see `docs/sovereign_holons/README.md`."* This was done in the prior turn; double-check it survives.

After these five steps, this initiative has a **durable home in the hygiene system**: any future agent running `make hygiene-check` will see the three patterns, any future PR that re-introduces a cosmetic chat endpoint will be caught, and the lifecycle machinery will let the operator graduate the patterns from `observed` to `enforced` as the first brick lands.

---

## Cross-references

- The patterns above reference [02_FIRST_BRICK_SPEC.md](02_FIRST_BRICK_SPEC.md) as their remediation doc — that file must not move.
- The dossier evidence is in [00_RESEARCH_DOSSIER.md](00_RESEARCH_DOSSIER.md).
- The build sequence (which commit implements which acceptance criterion) is in [01_BUILD_GUIDE.md](01_BUILD_GUIDE.md).
- The author/owner field on each pattern is `opus_composer` because that is the verified-real first holon (see 02_FIRST_BRICK_SPEC.md §"The 'easiest first holon' picture is wrong").
- This initiative is registered in `docs/docops/assertions.yaml` under the assertion key `sovereign_holons.canonical_home` (operator to add; one-line YAML stating the canonical path is `docs/sovereign_holons/`).
