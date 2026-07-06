# 12 — `load_holon` Collapse Plan: 136→1 / current 138→1

Purpose: stop the holon bridge/runtime fork disease before Sarathi grows on top
of the wrong body.

## Current count receipt

Current full `/Users/dhyana` scan on 2026-07-06:

```text
holon_bridge.py: 138 instances
holon_runtime.py: 138 instances
git roots containing these files: 69
relative paths per root:
  69 dharma_swarm/holon_bridge.py
  69 dharma_swarm/holon_runtime.py
  69 holon/holon_bridge.py
  69 holon/holon_runtime.py
```

This differs from the prior `136 copies / 68 trees` statement by +2 files / +1
git root. Treat the older count as stale, not as a contradiction of the disease:
the invariant is still **many tree copies, two module homes per tree, one concept**.

## The three live `load_holon` versions

| Label | Path | Lines | SHA-1 | Verdict |
|---|---|---:|---|---|
| dev-397 | `/Users/dhyana/dharma_swarm/dharma_swarm/holon_bridge.py` | 397 | `20948569d3f36d01c3982367bcdb764dc0875487` | Current fork branch version; includes additive LivingDock/dialogue-provider work. Not canonical because branch is 381 behind origin/main. |
| fork-127 | `/Users/dhyana/dharma_swarm/holon/holon_bridge.py` | 127 | `86a92697c26de6381ef61f2a5b7fcdfbcbd38e81` | Same-tree standalone fork using `holon.contracts/providers`; keep only as temporary migration source/tests, not runtime canonical. |
| deploy-204 | `/Users/dhyana/dharma_swarm_main/dharma_swarm/holon_bridge.py` | 204 | `192ce506734c9e458e1ea8cce1a0867927e4b150` | Matches `origin/main:dharma_swarm/holon_bridge.py` exactly in this verification. Canonical base. |
| origin-main-204 | `git show origin/main:dharma_swarm/holon_bridge.py` | 204 | `192ce506734c9e458e1ea8cce1a0867927e4b150` | **Canonical source of truth for collapse.** |

## Behavioral diff summary

### fork-127 → deploy/origin-204

The 127-line `holon/` fork is older and weaker:

- imports `holon.contracts.LLMRequest` and `holon.providers.ProviderRouter` rather than the repo's canonical `dharma_swarm.models.LLMRequest` + runtime provider door;
- accepts a wider 96-character name slug; deploy/origin validates a 64-character registry slug and strips newline/carriage return;
- defaults missing model to `holon-echo-v1`; deploy/origin fails if `identity.json` has no `model`;
- lacks provider enum validation/coercion through the real runtime provider;
- lacks the detailed read-only sovereign-holon doctrine in the module docstring.

### deploy/origin-204 → dev-397

The 397-line dev version is mostly additive:

- adds `HolonDialogueContext` and `HolonDialogueProviderError`;
- adds `DHARMA_HOLON_DIALOGUE_PROVIDER` and `DHARMA_HOLON_DIALOGUE_MODEL` overrides;
- refuses agentic subprocess provider types (`claude_code`, `codex`) for direct read-only dialogue;
- adds LivingDock context summaries from identity/living-agent/dialogue/receipt files;
- extends `build_request()` and `holon_reply()` with optional context and request-model override.

Those additions may be useful, but they are on the behind fork and should be
ported intentionally onto `origin/main`, not made canonical by default.

## Canonical choice

**Canonical now:** `origin/main:dharma_swarm/holon_bridge.py` (204 lines,
SHA-1 `192ce506734c9e458e1ea8cce1a0867927e4b150`).

Reason:

1. The operator-ratified estate decision says `origin/main` is canon, not the
   `agent/magpie-seed` fork.
2. Deploy body matches `origin/main` exactly, so the code that is closest to
   runtime reality and the code that is closest to repo canon agree.
3. The `holon/` fork is behaviorally weaker and imports a separate provider
   stack.
4. The dev-397 additions are additive but unproven on the canonical branch.

## Collapse plan

### Phase 0 — no mutation, proof only

- Keep this document as the receipt of the diff.
- Do not delete duplicate trees from a dirty fork.
- Do not register Sarathi wake profile until the gate and collapse base are on a
  clean branch off `origin/main`.

### Phase 1 — rescue keystone onto canonical tree

- Create or use a clean worktree from `origin/main`.
- Add only:
  - `dharma_swarm/operator_core/reversibility_gate.py`
  - `tests/test_reversibility_gate.py`
  - these Sarathi map docs.
- Run `.venv/bin/python -m pytest tests/test_reversibility_gate.py tests/test_holon_bridge.py -q`.
- Commit that as the first Sarathi brick.

### Phase 2 — one `load_holon` module home

- Declare `dharma_swarm/holon_bridge.py` the only runtime import path.
- Migrate `holon/tests/test_standalone_runtime.py` and any surviving standalone
  package importers to `dharma_swarm.holon_bridge` / `dharma_swarm.holon_runtime`,
  or explicitly archive the standalone package outside runtime import scope.
- Add a governance check that fails if a runtime file imports `holon.holon_bridge`
  or if another `load_holon` definition appears outside an allowlisted fixture.

### Phase 3 — port only proven dev additions

- If direct read-only dialogue needs the dev-397 LivingDock provider/context work,
  port it as a small patch onto the canonical `origin/main` file.
- Required tests before porting:
  - unsafe provider override refuses `claude_code`/`codex`;
  - safe provider override resolves through runtime provider;
  - LivingDock context reads only bounded evidence and truncates at max chars;
  - existing `tests/test_holon_bridge.py` remains green.

### Phase 4 — cleanup copies

- After the canonical PR lands, treat all other worktrees as disposable mirrors.
- Delete or archive stale worktrees only through an operator-approved cleanup pass.
- Never force-delete from the live dirty worktree during Sarathi build.

## The invariant after collapse

There is exactly one runtime `load_holon` implementation:

```text
dharma_swarm/holon_bridge.py::load_holon
```

Any other file may test it, wrap it, or document it, but may not redefine it.

---

## Independent verification addendum (fable_composer, 2026-07-06)

Second seat re-counted with a *stated method*, because this session's whole
lesson is "two agents disagreed because neither said how they counted."

### SHA discrepancy resolved (not a contradiction)

The session handoff and the first agent quoted different hashes for the SAME
three files. Both are correct; they used different algorithms:

| File (lines) | raw `shasum` (SHA-1) | `git hash-object` (git blob) | `shasum -a 256` |
|---|---|---|---|
| dev-397 `dharma_swarm/dharma_swarm/holon_bridge.py` | `20948569d3f3…` | `470a7bb582ab…` | `62029f2aa0f0…` |
| fork-127 `dharma_swarm/holon/holon_bridge.py` | `86a92697c26d…` | `5a0b2463e1a3…` | `b33e230746d9…` |
| deploy-204 `dharma_swarm_main/dharma_swarm/holon_bridge.py` | `192ce506734c…` | `2d601da33246…` | `6221d7f3729b…` |

The handoff's `62029f2a / b33e2307 / 6221d7f3` are **sha256**. The first agent's
`20948569 / 86a92697 / 192ce506` are **SHA-1**. Same bytes, different lens.

### Canonical proof strengthened to git-object identity

`git hash-object` of the deploy body = `2d601da33246b9f056e74ec4bdd05c301bc1f299`,
which equals `git rev-parse origin/main:dharma_swarm/holon_bridge.py`
= `2d601da33246b9f056e74ec4bdd05c301bc1f299`. So deploy-204 **is** the origin/main
blob by object identity, not by text comparison. Canonical choice confirmed.

### "42 files / 5,668 lines" was an inconsistent pair — resolved

- `git ls-files 'dharma_swarm/holon*.py' | xargs wc -l` -> **18 files / 5,668 lines**.
- Add the `holon/` fork package: `dharma_swarm/holon*.py` + `holon/*.py`
  -> **42 files / 8,986 lines**.

The handoff mixed selectors: 42 came from counting *with* the fork, 5,668 from
counting *without* it. The correct singular statement:
**18 canonical holon files = 5,668 lines; the `holon/` fork adds 24 files.**

### Distinct-content census (the number that matters for collapse)

In-repo tracked `holon_bridge.py`: 6 copies but only **4 distinct contents**
(`192ce506` x2 = origin/main mirror, `7a0399be` x2 = a nested worktree variant,
`86a92697` x1 fork, `20948569` x1 dev). Estate-wide 138 copies are overwhelmingly
worktree mirrors. **Real drift = 3-4 implementations, not 138.** Collapse is
therefore tractable: reconcile ~4 files, then let worktree mirrors age out.

### Machine-checkable done-condition added

The collapse is "done" when `python3 scripts/governance/sprawl_guard.py` exits 0
on a clean branch off `origin/main`. Proven: it exits 1 on today's dirty tree
(flags the `holon/` fork) and 0 on a collapsed tree. See
`91_SPRAWL_HARNESS_RUNBOOK.md`.
