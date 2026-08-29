# Shakti System MVP

Document role: bounded experiment and implementation witness.
Replaces: nothing.
Subordinate to: the repository behavior contract, governed document stack,
active-track owner, executable code, and tests.

## What this is

This prototype is the smallest executable form of the proposed human–AI–world
operating system. It is not a new foundation model. It is a typed causal runtime
around models and people:

```text
human intention
    -> multiple agent proposals
    -> exact human grant
    -> fenced, bounded world effect
    -> observation (facts only)
    -> proposed interpretation
    -> exact human ratification
    -> changed next cycle
```

The technical claim is narrow and testable: cycle two must be computationally
joined to cycle one's observed consequence. A repeated prompt or a model saying
it learned is not enough. The evaluator admits only integer revision `0` and
one separately ratified integer revision `1`; truthy substitutes are not grants.

## Technology used and technology created

The MVP uses existing Dharma Swarm technology:

- Python dataclasses and protocols for typed transitions.
- The existing stable SHA-256 serializer for deterministic proposal,
  observation, and receipt identities. These hashes are integrity joins, not
  signatures or proof of truth.
- `foundry.patches.write_immutable_beneath` for a no-follow, local-only fixture
  effect.
- `foundry.shakti_local_world` for witnessing the validated grant at execution,
  retaining the exact expected local receipt together with its completion
  fence, requiring the cycle commit marker, and re-reading the referenced
  artifact at each policy decision boundary.
- `ExecutionIdentity` for run, trace, correlation, parent, causation, and
  idempotency joins without inventing task lifecycle state.
- `RuntimeStateStore` for the existing WAL-backed SQLite session events,
  operator actions, execution identities, idempotency fences, and runtime
  receipts.
- The deterministic reversibility classifier before the fixture effect.

The new technology is the transition protocol in
`dharma_swarm/foundry/shakti_system.py`: a participatory causal kernel in which
authority and evidence are structurally separate from agent cognition. Models
can later occupy the agent ports; they cannot manufacture the human grants or
promote their own interpretation into policy.

There is deliberately no transferable “verified evidence” object, structural
protocol, mint capability, or tokenless factory. `PolicyDelta.create(...)` and
`next_cycle_context(...)` each require the same concrete local-world adapter to
re-read the artifact at that moment. The adapter also rejects a recomputed
receipt whose authority or causality fields differ from the exact receipt it
derived from the validated deliberation and grant, or whose completion fence
cannot find the exact terminal cycle marker.

No Store, Ledger, Registry, scheduler, event bus, daemon, provider route, API,
or dashboard was added.

## The human blanks and this fixture's limit

The kernel defines two places that automation cannot silently fill in a real
operator surface:

1. `approve <proposal-prefix>`: which proposed action is actually authorized,
   by the owner of the intention, and why?
2. `ratify <delta-prefix>`: what—if anything—does the observed result mean for
   the next cycle?

An agent can draft either side of these decisions. It cannot grant them. This
MVP does not yet persist and resume an interactive session at both boundaries.
The no-flag command previews the first boundary without writing anything. The
flagged command preauthorizes fixed proposal choices, reasons, and an
interpretation so the two-cycle plumbing can be tested deterministically. It is
a canned fixture, not evidence that a human made those choices live and not
cryptographic authentication.

## Run it

Preview the proposals and stop before all world effects:

```bash
python3 scripts/foundry/run_shakti_system_mvp.py demo \
  --artifact-root /tmp/shakti-system-preview \
  --runtime-db /tmp/shakti-system-preview/runtime.db
```

The preview exits with status `3`, prints the exact expected confirmation, and
does not create the artifact root or runtime database.

Run the admitted two-cycle local fixture:

```bash
python3 scripts/foundry/run_shakti_system_mvp.py demo \
  --preauthorize-canned-demo \
  --artifact-root /tmp/shakti-system-mvp \
  --runtime-db /tmp/shakti-system-mvp/runtime.db
```

The completed JSON report includes two sealed cycle receipts and seven executable
assertions:

- cycle two's `parent_run_id` is cycle one's `run_id`;
- cycle two's `causation_id` is cycle one's observation ID;
- the two cycle input hashes differ;
- cycle two's proposal cites cycle one's observation;
- the human-ratified policy changes the recommended agent from builder to
  witness;
- exactly two `participatory_cycle` commit markers exist under one correlation
  ID in the runtime store;
- the required five local artifact reads complete: policy-delta creation,
  next-context admission, revised deliberation, revised execution, and final
  closeout each re-read the local artifact.

Two immutable JSON artifacts appear under `cycles/`. The second names the first
cycle's observation and the ratified reason for changing course.

## Observation is not interpretation

The world adapter may report only bounded facts in this MVP:

- a regular file was observed;
- its byte count;
- its SHA-256 digest.

“Prioritize the witness next” is a separate `PolicyDelta`. Its constructor asks
the same concrete local-world adapter to match the exact issued receipt and
re-read the artifact—not merely trust a raw, structurally compatible, or
self-sealed value. `next_cycle_context(...)` repeats that read after human
ratification and before the interpretation can affect cycle two. Neither call
returns a proof object that can be replayed elsewhere. This is the prototype's
small contribution toward an AI-native language where epistemic modality and
permission are evaluator semantics:

```text
Observed[LocalFixture, ArtifactDigest]
    != Interpreted[PolicyDelta]
    != Ratified[Owner, PolicyState]
```

The executable test shows that this local program enforced those transitions
inside its stated trust boundary. A receipt alone does not prove that the
interpretation is true or that an untrusted in-process caller is honest.

## Commit and retry semantics

The idempotency fence is acquired before runtime metadata is written. A retry
of the same operation cannot recreate the effect or regress a completed record.
After the world consequence is observed, the fence records that the effect was
consumed; the `participatory_cycle` receipt is then written last, atomically
with the observation event, and is the cycle commit marker. If that final
transaction fails, the effect remains fenced but no completed cycle marker
exists. Partial pre-marker records therefore describe an incomplete closeout,
not a completed cycle.

This ordering does not turn SQLite into an attestation system or make the local
effect transactionally atomic with the filesystem. It makes the narrower state
claim honest and prevents duplicate execution. Recovery is intentionally
bounded but incomplete: after a terminal marker failure, retries remain fenced
to avoid replaying the effect, and this MVP does not yet reconstruct the absent
marker from the completed idempotency row. That stranded effect is not eligible
for `PolicyDelta` creation or next-cycle admission.

## What this MVP does not claim

- It makes no external network request and uses no model provider.
- It does not prove a cosmic sender, divine provenance, consciousness, or that
  a coincidence has a particular cause.
- It does not prove external-world usefulness. `local_fixture` is the only
  evidence authority admitted here.
- It does not authenticate a remote human or organization.
- The canned CLI does not test live human choice at either permission boundary.
- It does not run unattended, contact anyone, pay, publish, deploy, or mutate a
  production system.
- SQLite receipts are durable causal records, not cryptographic attestations of
  reality.

## The next earned layer

The kernel becomes a useful real-world technology by replacing ports, not by
building another model first:

1. Put existing frontier models behind `CouncilAgent` adapters and preserve
   proposal diversity and provenance.
2. Replace the CLI flag with a persisted or authenticated interactive surface
   that grants one exact proposal, stores the pause, then separately ratifies
   one exact policy delta.
3. Add a leased connector for one reversible real-world domain.
4. Define domain-specific observers that distinguish measurement from
   interpretation and carry source authority.
5. Evaluate whether evidence-conditioned cycle two produces better external
   outcomes than a matched non-learning control.

Only after that comparison is positive has the MVP earned broader orchestration,
a participant UI, or model training.
