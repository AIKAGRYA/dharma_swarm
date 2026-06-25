# Slice A — CONTEXT.md Stage-Contract Reader — Build Spec

**Track:** `filesystem-native-substrate-2026-06` · **Slice:** A (of A–D) · **Status:** spec (no code yet) · **Date:** 2026-06-24
**Reads with:** `docs/research/FILESYSTEM_AS_AGENT_SUBSTRATE_RESEARCH.md` (the four powers + the organism tie)

> **What this slice is.** A *read-only* loader that turns an on-disk numbered-folder
> workspace + per-stage `CONTEXT.md` contracts (Van Clief's ICM/MWP) into the swarm's
> *existing* primitives — `Task` objects with `depends_on` edges, dispatched through
> `spine.invoke_agent()`, handed off stage-to-stage via `handoff.py`. It adds **no
> orchestrator, no receipt type, no truth store.** It is the smallest possible wedge
> that makes a swarm pipeline legible, portable, and editable as a folder.

> **Articulation convention.** Lines marked **⟢ Why** make explicit the reasoning a
> normal spec leaves implicit — the "why this and not the obvious alternative." The
> final section collects the cross-cutting whys.

---

## 1. Scope (and the hard line around it)

In scope:
- Parse a workspace: `stages/NN-name/CONTEXT.md` (+ a workspace-root `CONTEXT.md`).
- Build a typed `StageContract` per stage (inputs / process / outputs / agent / type).
- Derive the stage DAG and emit `Task`s with `depends_on` edges.
- Dispatch each ready stage through `invoke_agent()`, with context **bounded to the
  Inputs table** (the token firewall).
- Persist each stage's declared output and hand it to the next stage.

Out of scope (later slices, explicitly): OKF export/import (Slice B), semantic query
(Slice C), self-organizing file moves (Slice D), watch-mode daemons.

**⟢ Why so small.** The dossier's value is the *convergence* claim: the swarm already
has the machinery. The way to prove that claim — not just assert it — is to ship the
thinnest layer that *reuses* the machinery end-to-end. A big slice would tempt
re-implementation and hide the convergence. Small slice = the convergence is the
deliverable.

---

## 2. The on-disk contract format (what the reader parses)

A workspace is a directory. Stages are numbered child folders. Each stage holds a
`CONTEXT.md`:

```
workspace/
  CONTEXT.md                 # workspace-level: title, type: workspace, shared refs
  _config/                   # workspace constants (read as Layer-3 reference)
  stages/
    01-scope/
      CONTEXT.md
      output/                # this stage writes here (Layer-4 working artifacts)
    02-research/
      CONTEXT.md
      output/
    03-synthesize/
      CONTEXT.md
      output/
```

A stage `CONTEXT.md`:

```markdown
---
type: stage                 # OKF-compatible concept type (forward-compat w/ Slice B)
stage: 02-research          # optional; defaults to the folder name
agent: researcher           # resolves to dharma_swarm/skills/researcher.skill.md
title: Research the scoped question
---

## Inputs

| Source       | File/Location          | Section/Scope     | Why                  |
|--------------|------------------------|-------------------|----------------------|
| prior stage  | ../01-scope/output/    | full              | the scoped question  |
| voice rules  | ../../_config/voice.md  | "Tone" section    | house style          |

## Process

1. Read the scoped question.
2. Find 5 sources; extract claims.
3. Write findings to ./output/findings.md

## Outputs

| Artifact | Location            | Format   |
|----------|---------------------|----------|
| findings | ./output/findings.md | markdown |
```

**⟢ Why YAML `type` even in Slice A.** Slice B (OKF export) requires every concept
file to carry a `type`. Baking it in now makes Slice B a *projection* of this format,
not a rewrite. Designing the on-disk shape so the next slice is additive is the whole
"converge, don't duplicate" discipline applied to our own roadmap.

**⟢ Why the four-column Inputs table (not a flat file list).** The `Section/Scope` and
`Why` columns are the token firewall and the audit trail. `Section/Scope` lets the
loader pull *part* of a file (not the whole thing) into context; `Why` is the
human-/agent-readable justification that makes the pipeline observable-by-default. A
flat list would lose both — and lose the thing that makes this an ICM contract rather
than a glorified `ls`.

**⟢ Why `agent:` resolves to an existing `*.skill.md`.** The swarm already stores agent
roles as markdown-with-frontmatter (`dharma_swarm/skills/`). Reusing that resolver
means a stage's role *is* a first-class swarm agent (architect, researcher, surgeon,
…), not a new parallel notion of "role." One naming system (per CLAUDE.md's SSOT rule),
not two.

---

## 3. Data model

New module `dharma_swarm/fs_substrate/stage_contracts.py` (Pydantic 2, frozen where
possible, <500 lines per CLAUDE.md):

```python
class StageInput(BaseModel):      # one row of the Inputs table
    source: str
    location: str                 # path relative to the stage CONTEXT.md
    scope: str = "full"           # "full" | a named section | a glob
    why: str = ""

class StageOutput(BaseModel):     # one row of the Outputs table
    name: str
    location: str
    fmt: str = "markdown"

class StageContract(BaseModel):   # one stage = one morphism
    stage_id: str                 # e.g. "02-research"
    order: int                    # parsed from the NN- prefix
    type: str = "stage"
    agent_role: str | None        # resolves against skills/
    title: str = ""
    inputs: list[StageInput]
    process: list[str]            # ordered Process steps
    outputs: list[StageOutput]
    path: str                     # abs path to the CONTEXT.md
    contract_sha256: str          # hash of the raw markdown (provenance)

class StageWorkspace(BaseModel):
    root: str
    stages: list[StageContract]   # sorted by `order`
```

**⟢ Why hash the contract (`contract_sha256`).** It is stamped into the
`EvidenceReceipt.attributes` at dispatch (see §5). That gives a provable join between
"what the folder declared" and "what actually ran" — the spine's read-models-project-
truth doctrine, applied to a stage. Without the hash, a later edit to `CONTEXT.md`
would silently desync the record from reality.

**⟢ Why `StageContract` ≈ a morphism (not just a config row).** Inputs typed + Outputs
typed = a declared interface between stages. This is the categorical-systems-theory tie
from the dossier made concrete: the DAG of stages composes *because* each stage names
its domain (Inputs) and codomain (Outputs). The data model is where the abstract pillar
becomes a dataclass.

---

## 4. Parsing & DAG derivation

```python
def parse_context_md(text: str, path: str) -> StageContract: ...
def load_workspace(root: str) -> StageWorkspace: ...
def to_tasks(ws: StageWorkspace) -> list[Task]: ...   # Task from dharma_swarm/models.py
```

Dependency derivation (two rules, in order):
1. **Explicit:** stage X depends on stage Y if any `StageInput.location` of X points
   into `../<Y>/output/`. (Precise — follows the actual data flow.)
2. **Fallback:** if a stage references no sibling output, it depends on the
   immediately-lower `order` (ICM's numeric default).

Each emitted `Task` carries:
- `task.metadata["stage_id"]`, `["stage_contract_sha256"]`, `["agent_role"]`
- `task.depends_on = [<task ids of upstream stages>]`

**⟢ Why derive deps from the Inputs table, not purely from folder numbers.** ICM's
numeric ordering is a *default*, not the truth — the truth is which stage actually
consumes which stage's output. Reading the dependency from the declared Inputs makes
the DAG match the real data flow (and allows fan-out: two independent stages at the
same level needn't serialize). Numbering is the fallback for the common linear case.

**⟢ Why emit `Task` + `depends_on` rather than run a `for stage in stages:` loop.** The
swarm's `TaskBoard` already enforces the dependency DAG, persistence, claim/recovery,
and readiness queries. An inline loop would re-implement state management the system
already owns — badly, and as a second authority. ICM says *"the agent never manages
pipeline state — the folders do."* In the swarm the refinement is: **the folder
*declares* the DAG; the TaskBoard *executes* it.** Declaration ≠ execution; don't
conflate them.

---

## 5. Dispatch & handoff (the spine path)

New `dharma_swarm/fs_substrate/stage_executor.py`:

```python
async def dispatch_stage(
    contract: StageContract,
    *, invoker: AgentInvoker, routing: RoutingDecision, context_id: str,
) -> EvidenceReceipt: ...
```

For each ready stage:
1. **Assemble bounded context** from `contract.inputs` only — load each listed
   file/section, capped by a `MemoryContextBudget` (the existing read-side firewall).
   Nothing outside the Inputs table enters the window.
2. **Resolve the agent** from `contract.agent_role` → the existing `skills/` loader →
   system prompt.
3. **Build a `RoutingDecision`** and call **`invoke_agent(task, agent_id, context_id,
   routing, invoker=...)`** → one `EvidenceReceipt`.
4. **Stamp** `receipt.attributes["stage_id"]`, `["stage_contract_sha256"]`.
5. **Persist output** to the declared `StageOutput.location`, then
   `HandoffProtocol.create_handoff(from=stage, to=next_stage, artifacts=[Artifact(...)])`.

**⟢ Why route every stage through `invoke_agent()` — even though a file pipeline
"could" just call a model.** `invoke_agent` is the swarm's single dispatch path; the
sibling `spine-adoption` track is actively draining bypass sites to zero. A stage
runner that called a provider directly would *create the very debt that track is
paying down*, and would emit no `EvidenceReceipt`. Going through the spine means this
slice **moves substrate-nativeness up as a side effect** instead of leaking it.

**⟢ Why reuse `handoff.py` instead of just reading the next stage's input files.** The
output files *are* the handoff medium (ICM: "one folder's output is the next's input").
But the typed `Handoff`/`Artifact` adds lineage (`handoff_chain`), priority/ack, and
trace correlation the swarm already understands — so a stage transition is visible to
the rest of the organism, not just to the filesystem. The file is the payload; the
Handoff is the *event*.

**⟢ Why `MemoryContextBudget` for the Inputs.** It is the existing fail-closed admission
budget (`max_admitted`, `max_total_chars`, per-atom truncation). Reusing it means the
token firewall isn't a new mechanism — it's the same boundary the MemoryKernel already
enforces, now driven by an on-disk declaration. One firewall, two front doors.

---

## 6. Integration point (how it reaches the running swarm)

Opt-in, additive, behind a flag — **not** a change to the default dispatch loop:

- A thin entry `run_workspace(root, ...)` callable from a `dgc` subcommand (e.g.
  `dgc fs-stage run <workspace>`), and optionally from `SwarmManager.dispatch_next()`
  *only* when a workspace path is registered (env/flag gated, default off).

**⟢ Why opt-in and flag-gated, not wired into the hot loop.** `orchestrator.py`,
`agent_runner.py`, and `swarm.py` are owned by `spine-adoption` and named in *this
track's* non-goals. Touching the default dispatch path would (a) collide with that
track's surfaces and (b) risk the running organism. A registered-workspace opt-in
gives full capability with zero blast radius on the default path — the surgical
boundary the operator asked for.

---

## 7. Module layout & what is reused

```
dharma_swarm/fs_substrate/
  __init__.py
  stage_contracts.py     # NEW: model + parse_context_md + load_workspace + to_tasks
  stage_executor.py      # NEW: dispatch_stage / run_workspace (calls invoke_agent)
tests/
  test_stage_contracts.py    # parse + DAG derivation + provenance hash
  test_okf_projection.py     # (placeholder for Slice B; created empty-skip now)
tests/fixtures/fs_substrate/sample_workspace/   # 3-stage fixture
```

Reused unchanged (the convergence, made explicit):

| Need | Reused owner | Not built |
|------|--------------|-----------|
| dispatch + receipt | `spine.invoke_agent`, `EvidenceReceipt` | a runner/receipt |
| dependency DAG | `Task.depends_on`, `TaskBoard` | a scheduler |
| stage→stage handoff | `handoff.py` (`Artifact`, `Handoff`) | a message format |
| agent role | `dharma_swarm/skills/*.skill.md` loader | a role registry |
| bounded context | `MemoryContextBudget` | a token limiter |

**⟢ Why a new package `fs_substrate/` rather than extending an existing module.**
Disjoint, declared owned-surface (the track's coordination plane) = zero overlap-WARN
with any sibling track. A new *package* (not edits to god-objects) is the cheapest way
to stay surface-clean while the god-objects remain owned by spine-adoption.

---

## 8. Test plan (maps 1:1 to the track's acceptance criteria)

| Track criterion | Test |
|---|---|
| `stage_contract_reader_exists` (`class StageContract`) | `test_parse_minimal_stage_contract` |
| `stage_reader_routes_through_spine` (`invoke_agent` referenced) | `test_dispatch_stage_calls_invoke_agent` (fake `AgentInvoker`, assert receipt + stamped attributes) |
| `stage_contract_test_passes` (`tests/test_stage_contracts.py`) | the file passes green |

Plus, beyond the criteria: DAG derivation (explicit + fallback), Inputs section-scoping,
contract-hash stability, malformed-`CONTEXT.md` failure mode (§9).

**⟢ Why a fake `AgentInvoker` in tests, not a live model.** Slice A's correctness is
*structural* — does the folder become the right DAG, does it route through the spine,
does the receipt carry the stage provenance. None of that needs a real LLM call; a fake
invoker keeps the test hermetic and fast (the repo's `asyncio_mode=auto` + offline-smoke
discipline). The model's *output quality* is out of scope for this slice.

**⟢ Why one acceptance criterion is `test_passes`, not just `file_contains`.** The
governance checker flags existence-only criteria as "not closure." A `test_passes`
criterion is the rigorous bar — it proves the reader *works*, not merely *exists*.

---

## 9. Failure modes & edge cases

- **Malformed `CONTEXT.md`** (missing Inputs/Process/Outputs section): fail closed with
  a precise error naming the stage path. ⟢ Why: a half-parsed contract that silently
  drops a dependency is worse than a hard stop — the observability property dies the
  moment the parse lies.
- **Dependency cycle** (Inputs reference forms a loop): reject at `to_tasks()` with the
  cycle path. ⟢ Why: the TaskBoard DAG assumes acyclicity; catch it at declaration.
- **Input path escapes the workspace** (`../../../etc`): reject (path traversal guard,
  per CLAUDE.md security rule). ⟢ Why: a workspace is portable/untrusted; treat its
  paths as input at a boundary.
- **Missing referenced input file:** fail the stage's readiness with a clear message;
  do not dispatch a stage whose declared inputs don't exist.

---

## 10. Acceptance criteria alignment (one honest correction)

The track currently points `stage_reader_routes_through_spine` at
`stage_contracts.py`. This spec puts the `invoke_agent` call in `stage_executor.py`
(parsing and dispatch are separate concerns). **At build time I will repoint that one
criterion to `stage_executor.py`** — a 1-line `ACTIVE_TRACK.yaml` edit — rather than
forcing dispatch logic into the parser to satisfy a misaimed check.

**⟢ Why flag this now.** Silently bending the code to fit a criterion (or silently
bending the criterion) is exactly the "lying green light" the organism's Mechanisms
doctrine forbids. Naming the correction in the spec keeps the gate honest.

---

## 11. Articulation notes — the implicit "why" (cross-cutting)

These are the reasons that don't attach to a single section but govern the whole slice.

1. **Why a folder reader is a *substrate* move, not a *feature*.** A feature serves one
   workflow; a substrate changes how every workflow is expressed. Making a pipeline a
   readable/editable/portable folder means *any* multi-stage task — research, build,
   review — can be authored by a human or an agent without touching code. The leverage
   is that it's general, which is why it serves `substrate-nativeness` and not a
   product organ.

2. **Why "the folder declares, the swarm executes" is the load-bearing inversion.** ICM
   (a single-agent tool) lets folders *be* the orchestrator because there's nothing
   else. The swarm *has* an orchestrator. So we don't replace it — we let the folder be
   the **declaration** and the existing spine/TaskBoard be the **execution**. This
   single distinction is what turns a borrowed idea into a converging one. Get it wrong
   (folder-as-executor) and you've built a second orchestrator and collided with
   spine-adoption.

3. **Why bounded-by-Inputs context is the real prize.** The flashy framing is "folders
   as pipelines." The durable win is the **token firewall**: a stage sees only its
   declared Inputs, so context stays in the 2k–8k band where models are sharp. This is
   `context_efficiency` (a vital sign this track moves) made structural rather than
   hoped-for. Everything else is plumbing around this.

4. **Why this slice is the antidote to its own anti-pattern.** A dossier about
   filesystem-context is "a paper about our own architecture" (the named anti-pattern)
   *until code runs*. Slice A is the smallest thing that converts the paper into a
   working capability that routes real dispatches through the spine. Shipping it is how
   the inward work earns its keep — "being that strengthens the body for doing."

5. **Why OKF-compat (`type`) is seeded here for an outward reason.** Slice A is inward
   (substrate). The `type` frontmatter is the thread to Slice B (OKF export), which is
   *outward* — portable knowledge that leaves the house. Seeding it now keeps the whole
   track tethered to Arjuna from its first commit, so the substrate work never drifts
   into pure recursion.

---

## 12. Estimate & exit

- ~1 module pair + 1 test file + 1 fixture workspace. No god-object edits.
- **Done when:** `tests/test_stage_contracts.py` is green, a 3-stage fixture workspace
  loads → emits a correct `depends_on` DAG → dispatches through a fake invoker →
  produces `EvidenceReceipt`s stamped with stage provenance → writes a handoff chain.
  At that point the track moves 2/5 → 5/5 on its completion criteria.
