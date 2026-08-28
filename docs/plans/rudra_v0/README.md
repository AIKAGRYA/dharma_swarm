# RUDRA v0 — pointed-spear build package

**Status:** build-ready specification; no product code, tracker state, or runtime
has been changed.

**Evidence base:** `origin/main` at
`884ee4fa75bb28877633f9c7a7ddadb8e3b1e19b`, inspected in the clean checkout
`/Users/dhyana/ds_rudra_audit_20260814` on 2026-08-14. The build must recompute
and bind a fresh base before any repository edit.

## The destination

RUDRA turns one operator-authored coding mission into one persistent frontier
model thread inside one private Git workcell. It may work unattended and use the
full coding toolchain inside that workcell. It succeeds only when a frozen,
independent executable gate passes from a fresh detached verification workcell
against the exact candidate commit.

The first proof is deliberately brutal and small:

1. Run one real repair three times with RUDRA and three times with a bare
   one-turn app-server control.
2. Kill one matched run in each arm during active work.
3. Recover without a second executor, an unauthorized write, a stale green
   result, or human steering.
4. Accept only a fresh verifier pass against the exact admitted contract and
   candidate commit.

That is the missing join between Dharma's powerful model, durable intent,
tool-using execution, and independent truth. The multi-agent team builds the
engine in parallel; the v0 engine itself remains one supervisor, one workcell,
and one model thread. Product concurrency is earned after the spinal cord works.

## Read order

1. [`WAYFINDER_HANDOFF.md`](WAYFINDER_HANDOFF.md) — destination, resolved
   decisions, remaining empirical fog, and explicit non-goals.
2. [`RUDRA_BUILD_SPEC.md`](RUDRA_BUILD_SPEC.md) — normative architecture,
   invariants, state machine, interfaces, recovery rules, and phase gates.
3. [`MISSION_CONTRACT_V0.yaml`](MISSION_CONTRACT_V0.yaml) — executable contract
   example for the first real repair.
4. [`WORK_PACKET_DAG.yaml`](WORK_PACKET_DAG.yaml) — disjoint multi-agent build
   packets, dependencies, write scopes, joins, and stop conditions.
5. [`TEST_AND_BURNIN_PLAN.md`](TEST_AND_BURNIN_PLAN.md) — negative controls,
   crash matrix, A/B proof, and burn-in.
6. [`RUDRA_GOAL.md`](RUDRA_GOAL.md) — launch-ready native `/goal` objective and
   operating contract for a long build session.

Run the following from this directory to check the package's cross-file
structure and DAG invariants:

```bash
/Users/dhyana/dharma_swarm/.venv/bin/python validate_spec.py
```

## The hard cuts

- no Dharma-owned VMM;
- no new scheduler, task database, receipt ontology, memory system, router, or
  general agent framework;
- no Mission Control, NATS, Temporal, graph runtime, council, self-evolution, or
  external action in the v0 hot path;
- no dangerous bypass, sandbox fallback, runtime dependency installation, or
  untrusted/cyber workload;
- no model self-report, process exit code, dashboard state, or receipt can mint
  reproduced completion;
- freeze for deletion review if the first executable hot path exceeds 1,000 new
  production lines before the real vertical slice runs.

## Launch boundary

This package does **not** itself authorize repository work. At the evidence base,
the active-track portfolio is at its 10-track ceiling and the proposed RUDRA
surfaces are not owned. The first build action is a small human-ratified ownership
amendment. After that merges, all coding starts in fresh, packet-specific
worktrees from one exact base; the shared dirty checkout is never used.
