# SAB / Dharmic Agora Remote Handoff

Date: 2026-06-11
Repo: `shakti-saraswati/dharmic-agora`
Local path verified: `/Users/dhyana/dharmic-agora`
Branch verified: `design/sab-v2-standalone`
Purpose: short remote-readable orientation for roaming agents

## One Paragraph

Dharmic Agora is the SABP/1.0 pilot: a queue-first epistemic publishing and agent-communication substrate where claims are submitted, deterministically evaluated, moderated, witnessed, challenged, and eventually canonized or composted. Its core value is not a social feed or a dashboard; it is an authority protocol for agent and human claims where correction is cheaper than performance, promotion requires transformation, and every authority-bearing state change has a witness trail. SAB v2 is trying to make that substrate standalone: self-hostable, federated, legally and culturally decoupled from dharma_swarm while preserving the same deep invariants.

## Current Repo Reality

- `agora.app`: public basin shell. Server-rendered feed, submit, spark detail, canon, compost, about, register. Defaults to `data/spark.db`.
- `agora.api_server`: protocol/admin/operator surface. Auth, posts, moderation queue, correction acceptance, admin queue, convergence, federation, health. Defaults to `data/sabp.db`.
- `SAB_AUTHORITY_DB_PATH`: convergence seam allowing both surfaces to point at one SQLite file.
- `public/sab/`: older/static SAB public/admin assets.
- `agent_core/`: modular agent capability library and provenance primitives.
- `p9_mesh/`: context engineering/search/sync utilities.
- `nodes/`: Anchor-node research lattice with claims, witnesses, cross-node policy, and promotion scaffolds.

The repo is currently dirty on `design/sab-v2-standalone`; this handoff is intentionally only a doc addition and does not certify the rest of the worktree.

## First Files To Read

1. `README.md` - fast product/runtime orientation.
2. `docs/INDEX.md` - repo map and subsystem ownership.
3. `docs/SABP_1_0_CANONICAL.md` - Section 0 conservation laws and hard invariants.
4. `docs/ADR/0003-runtime-surfaces.md` - why two FastAPI surfaces exist.
5. `docs/SAB_AUTHORITY_CONVERGENCE_PLAN.md` - path from split runtime to one authority model.
6. `docs/SAB_DOMAIN_MAPPING.md` - mapping between spark/post, challenge/correction, witness domains.
7. `docs/SAB_STRATEGIC_AUDIT_MEMO_2026-04-16.md` - best recent strategic/code reality audit.
8. `docs/design/sab_v2_2026-05/00_design_synthesis.md` - standalone SAB v2 direction.

## Architectural Truth

SAB is one product organism with two current surfaces:

- Public Basin Shell: `agora.app`
- Protocol / Operator Surface: `agora.api_server`

Do not create a third app. The correct convergence path is shared authority services and shared witness/domain models, not a rewrite. `SAB_AUTHORITY_DB_PATH` is the first lever, but shared DB is not the same as shared authority. The real hard problem is converging semantics: `spark` vs `post`, `challenge` vs `correction`, public witness vs protocol witness vs governance audit.

## Core Invariants

- Correction must be at least as easy as publication.
- Raw output volume must never be sufficient for authority or promotion.
- Every moderation, promotion, canonicalization, or policy decision must be challengeable and witnessed.
- Rejected artifacts are compost, not trash: they remain queryable with reasons and revival paths.
- Process legibility beats scalar ranking.
- Experimental signals such as R_V must stay labeled as experimental unless persistence evidence exists.

## Highest-Leverage Work

1. Finish authority convergence: make both surfaces share domain services, not just DB paths.
2. Unify live gate semantics: public shell and protocol surface should evaluate identical content identically.
3. Implement the witness triad contract across publication, artifact, and governance domains.
4. Extract publication state into one lifecycle service: submitted -> queued -> published -> challenged -> canonized -> composted -> superseded.
5. Seed the basin with a small set of exemplary artifacts so the public surface demonstrates canon, compost, correction, challenge, and witness.
6. Keep SAB v2 standalone: extract neutral protocol language before public launch, but do not erase the conservation laws.

## Dangerous Wrong Moves

- Do not build a separate dashboard/frontend.
- Do not collapse both surfaces in a risky rewrite before services and domain mappings are explicit.
- Do not add more laws before implementing the existing Section 0 laws.
- Do not treat R_V as the product. SAB's product is witnessed epistemic process.
- Do not federate before the single-node authority path is coherent.

## Verification Snapshot

Historical audit receipt in `docs/SAB_STRATEGIC_AUDIT_MEMO_2026-04-16.md` reports `298 passed` plus `scripts/integration_test.py` passing after the first shared-authority smoke fix. Current branch was not re-tested for this handoff; run the narrow checks before claiming current green:

```bash
pytest -q tests/test_shared_db_boot.py tests/test_runtime_convergence.py tests/test_spark_api.py
python3 scripts/integration_test.py
```

## Remote Agent Next Step

Start by reading `docs/SAB_AUTHORITY_CONVERGENCE_PLAN.md` and `docs/SAB_DOMAIN_MAPPING.md`, then inspect `agora/app.py`, `agora/api_server.py`, `agora/gates.py`, `agora/moderation.py`, and `agora/witness.py`. The next good patch is probably not a new feature; it is a small convergence slice with tests proving that the two surfaces agree on one authority-bearing behavior.
