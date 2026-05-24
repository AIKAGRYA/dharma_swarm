# Routers and TaskBoard — Distinct Roles, Not Duplicates

**Status:** Authoritative
**Audience:** Any agent (human or AI) auditing the repo for "router proliferation" or "duplicate TaskBoard" anti-patterns
**Purpose:** Prevent incorrect consolidation proposals by pinning the distinct domain each router and each TaskBoard reference owns

---

## Why this doc exists

Recent hostile audits of `dharma_swarm` have proposed two consolidations that look correct from filename inspection (`grep -l "router"`) but are wrong from domain inspection:

1. **"Fold `swarm_router.py` and `smart_router.py` into `intent_router.py`"** — these are three different abstractions over three different domains.
2. **"Delete the duplicate `TaskBoard` in `orchestrator.py`"** — that `TaskBoard` is a typing `Protocol`, not a competing implementation.

`make docops-integrity` reports `router_files=13, orchestrator_files=4` as tracked metrics. Those numbers reflect the **breadth of distinct routing/orchestration concerns** the repo handles, not duplication. This document records which concern each file owns so future audits don't conflate them.

---

## The three "routers" — three different jobs

| Module | Domain | Input | Output | Importers (non-test) |
|---|---|---|---|---|
| `intent_router.py` | Natural language → typed task decomposition | NL task description | `Intent`, sub-tasks, complexity, parallelism hint | 5 (`swarm.py`, `skill_composer.py`, `terminal_commands/infrastructure.py`, `terminal_commands/meta.py`, `operator_core/intent_payloads.py`) |
| `swarm_router.py` | Swarm role → deterministic execution plan | `SwarmRole` (PLANNER/CODER/CRITIC/RESEARCHER) + blackboard contract | `SwarmExecutionPlan` over `provider_policy` | 1 (`provider_policy.py`) |
| `smart_router.py` | LLM request → cost tier | `LLMRequest` | `SmartRouteDecision` (FREE/CHEAP/MID/PREMIUM tier + reranked candidates) | 1 (`provider_policy.py`) |

### Why they are not duplicates

They sit on three different layers of the call stack:

```
User intent (NL)
   │
   ▼
intent_router.py        ── decomposes intent into tasks
   │
   ▼
swarm_router.py         ── assigns swarm roles, builds execution plan
   │
   ▼
smart_router.py         ── selects LLM cost tier within the chosen role
   │
   ▼
provider_policy.py      ── selects concrete provider candidates
```

Folding any pair would collapse two distinct concerns into one module and lose the seam where future agents (or future routing strategies) can intervene cleanly.

### Source-of-truth docstrings (verbatim)

**`intent_router.py`:**
> Intent Router — smart task decomposition and skill matching. Takes a natural language task description, detects intent, estimates complexity, decomposes into sub-tasks if needed, and routes to the best available skills.

**`swarm_router.py`:**
> Deterministic swarm-routing plan on top of provider policy.

**`smart_router.py`:**
> SmartRouter: Cost-aware model routing for dharma_swarm. Routes tasks to the cheapest model that can handle them: Simple tasks → free tier; Medium tasks → mid tier; Complex tasks → premium. Integration point: sits between router_v1 (classification) and provider_policy (candidate selection), adding explicit cost-tier mapping and decision logging.

### What a correct consolidation would look like

If a future agent finds a *real* duplicate, the standard for a consolidation proposal is:

1. Both modules implement the same domain abstraction (not just have "router" in the name)
2. Both have overlapping public API surfaces with semantically equivalent methods
3. Folding produces a single module whose docstring and tests still make sense
4. The diff is net-negative LOC with no behavioral changes
5. All importers of the folded module continue to type-check and pass tests

None of those conditions hold for `intent_router` / `swarm_router` / `smart_router`.

---

## The "duplicate TaskBoard" — Protocol vs implementation

`grep -rn "^class TaskBoard" dharma_swarm/` returns two hits:

```
dharma_swarm/orchestrator.py:55:class TaskBoard(Protocol):
dharma_swarm/task_board.py:72:class TaskBoard:
```

These are **not** duplicate implementations. They are a typing pattern:

- **`orchestrator.py:55`** declares `class TaskBoard(Protocol)` — a [PEP 544](https://peps.python.org/pep-0544/) structural typing protocol. It is a **type contract**, not an implementation. The `Orchestrator` class uses it to express "I depend on something that looks like a TaskBoard" without coupling to the concrete class.

- **`task_board.py:72`** declares `class TaskBoard` — the **concrete implementation** with aiosqlite-backed FSM, dependency tracking, and CRUD.

This is typed dependency injection done correctly. Deleting the Protocol would:

- Break the type signature of `Orchestrator.__init__(...)`
- Lose static-analysis coverage for what `Orchestrator` requires
- Force tighter coupling between `orchestrator.py` and the concrete `task_board.py`

### How to verify a Protocol vs an implementation

Quick check before proposing deletion:

```python
# Look at the class definition
class Foo(Protocol):    # ← Protocol = type contract, do not delete blindly
    ...

class Foo:              # ← concrete class, may or may not be a duplicate
    ...
```

Or via the AST: `Protocol` in the bases tuple ⇒ structural typing contract.

---

## The four "orchestrators" — distinct lifecycles

`make docops-integrity` reports `orchestrator_files=4`. The four:

| Module | Lifecycle | Status |
|---|---|---|
| `orchestrate.py` | Subprocess-spawning cohort orchestrator (`claude -p` instances), 4 named plans | Foundational; CLI entry via `python3 -m dharma_swarm.orchestrate` |
| `orchestrator.py` | Async in-process `Orchestrator` class with dispatch/fan_out/fan_in/route_next/tick/run; 10 importers including `swarm.py` | Load-bearing async coordinator; **not** marginal |
| `orchestrate_live.py` | The 15+ concurrent-loop live runner (`make live` / `dgc orchestrate-live`) | Live; boots health API on `:7433` |
| `ginko_orchestrator.py` | Trading-specific daily cycle | Domain-specific; isolate, do not generalize |

These are four different lifecycles, not four implementations of the same abstraction. A "5th orchestrator" proposal should be challenged with: *which of these four lifecycles is your new orchestrator a duplicate of, and why is folding into that lifecycle the wrong move?*

If the answer is "none of the above," the new module is doing a new job and should be named after its job (e.g., `cohort_dispatch`, `acceptance_loop`, `mailbox_runner`) — never the generic word `orchestrator`.

---

## The 13 routers — what they actually are

`router_files=13` includes all `*router*.py` modules. Most of them are domain-specific routing within distinct subsystems:

- `intent_router.py` — NL → tasks (described above)
- `swarm_router.py` — role → execution plan (described above)
- `smart_router.py` — request → cost tier (described above)
- `decision_router.py` — collaboration decision routing
- `router_v1.py` — routing-signal extraction (feeds `smart_router`)
- `router_retrospective.py` — post-hoc routing learning
- `routing_memory.py` — routing history persistence
- Plus six more in subsystems (mailbox routing, opportunity routing, etc.)

Audit standard: before proposing to fold any pair, run `grep "from dharma_swarm.<module>"` to find importers, then read the docstring of each to confirm the domain. **Filename similarity is not domain similarity.**

---

## The audit principle

> A consolidation proposal that does not cite the docstrings of the modules being folded, and does not enumerate the importers being updated, is not yet ready for review.

This is the bar. It prevents grep-based audits from proposing changes that look elegant but introduce real bugs.

---

## Related docs

- `docs/architecture/SWARM_SUBSTRATE.md` — the substrate spec; this doc supports it by clarifying which existing modules the substrate facade wraps
- `docs/governance/SOVEREIGN_MANIFEST.md` — canonical metrics including `router_files` and `orchestrator_files`
- `docs/governance/ACTIVE_TRACK.yaml` — current intent SSoT
