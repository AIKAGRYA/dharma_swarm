# SYNADIA CLOUD / CAR BRIDGE SPEC
## Synadia Cloud (NGS) as the Global Anchoring Layer for Causal Action Receipts

**Custody grade:** RESEARCHED — hardened 2026-07-11 via 24-agent Web5/Commons synthesis.
**Authority:** This file is doctrine and forward operating contract, not live state.
**Supersedes:** Nothing. This is a new additive layer that extends
`NATS_SUBSTRATE_MASTER_SPEC.md`; it does not change any existing DS_* streams or subjects.
**Required reading before opening the SIS track:** `MASTER_SYNTHESIS.md` (at
`~/handoffs/2026-07-11_web5_commons_research/`), `canon_sis-gaia.md`,
`docs/governance/NATS_SUBSTRATE_MASTER_SPEC.md`.

---

## Decision

**Synadia Cloud (NGS — NATS Global Service) is the designated cross-boundary
receipt-anchoring fabric for the Causal Action Receipt (CAR) commons layer.**

The system split is:

- **Local NATS (DS_*):** internal fleet hot path — unchanged, per NATS_SUBSTRATE_MASTER_SPEC.
- **DS_CAR:** new additive JetStream stream for CAR receipt events (local, joins DS_RECEIPTS family).
- **Synadia Cloud / NGS (leaf node bridge):** cross-boundary challenge routing,
  independent witness registration, multi-jurisdictional receipt anchoring.
- **NATS Agent Protocol (Synadia 2026-05):** witness-agent registry standard — the
  discovery backbone for the commons Challenge Desk.

This separation maps directly onto the hardened Commons moat analysis from Round 1:
> "Incumbent challenge layers are scoped to their own commercial perimeter, never
> cross-platform, never binding on the platform's own conduct or material burden.
> The commons owns **cross-boundary challenge, challenge-against-the-platform, and
> non-commercial-consequence challenge.**"

Local NATS handles fleet consensus. NGS handles the cross-platform layer that no
single platform can own.

---

## Why NATS / Synadia Cloud — the convergence argument

Eight independent research lenses converged on the same whitespace: nothing in the
2026 protocol stack binds **delegated authority + material burden + telos + independent
outcome evidence + challenge/reversal** into a single signed, witnessed, cross-domain
receipt. NATS is the one wire-protocol that already solves:

1. **Cross-boundary routing** without a central hub — subject-based, no registry required.
2. **Non-backdateable ordering** — JetStream sequence numbers + `Nats-Msg-Id` dedup header
   are append-only; any insertion attempt changes later sequence numbers and is detectable.
3. **Federated multi-tenant isolation** — NGS accounts isolate bioregional witness
   networks without shared custody; cross-account import/export is the only bridge.
4. **Leaf node bridge** — any local NATS deployment (like Dharma Swarm's existing DS_*)
   becomes a leaf of the global NGS superset with a single `leafnodes {}` config block.
   No code change; no schema change; no DS_* migration.
5. **The Synadia Agent Protocol (2026-05-25)** — an open NATS micro-service discovery
   contract that defines how agents register capabilities, receive prompts, and emit
   heartbeats. This is the witness-agent registration primitive the Challenge Desk needs
   without a new registry process.
6. **JetStream R3 HA streams** — three-replica consensus across availability zones
   gives the "independent, non-backdateable" property at manageable cost (personal/free
   tier available for early bootstrap; R3 is paid).

---

## Causal Action Receipt — NATS Subject Hierarchy

The CAR's nine chained-signed segments map onto NATS subjects as follows.
The `{car_id}` is a stable, globally unique receipt identifier (UUID v7 recommended
for time-sortability). All local publishing stays under `dharma.car.*`. Global
anchoring (witness + challenge) routes to `commons.car.*` on NGS via the leaf bridge.

```
# Local DS_CAR stream (dharma_swarm fleet, internal)
dharma.car.{car_id}.s1.identity     # S1 — delegated agent identity
dharma.car.{car_id}.s2.telos        # S2 — intent / telos statement
dharma.car.{car_id}.s3.burden       # S3 — material burden (SIS domain — compute/energy debit)
dharma.car.{car_id}.s4.authority    # S4 — community authority / FPIC consent status
dharma.car.{car_id}.s5.evidence     # S5 — oracle evidence bundle (GAIA 3-of-5 quorum)
dharma.car.{car_id}.s6.action       # S6 — capital routing / action record
dharma.car.{car_id}.s7.outcome      # S7 — witnessed outcome (OutcomeRecord + AuditRecord)
dharma.car.{car_id}.s8.challenge    # S8 — challenge/reversal events  ← FAILING TEST HERE
dharma.car.{car_id}.s9.learning     # S9 — adaptive review / learning

# Cross-boundary layer on NGS (Synadia Cloud)
commons.car.challenge.{car_id}.>    # public challenge desk — cross-platform, non-commercial
commons.car.witness.{agent_id}.>    # witness agent registry (NATS Agent Protocol)
commons.car.burden.{domain}.>       # SIS material burden declarations (cross-org)
commons.car.anchor.{car_id}         # receipt anchor hash (non-payloaded; sequence = timestamp proof)
```

**Key invariant:** the local `dharma.car.{car_id}.s8.challenge` subject is mirrored
to `commons.car.challenge.{car_id}.>` on NGS via import/export. Challenge publication
is always local-first; the NGS mirror is the cross-boundary persistence layer. An
incumbent cannot see or suppress challenges on subjects they do not own.

---

## JetStream Stream Definitions

### DS_CAR (new — additive to DS_RECEIPTS family)

| Field | Value |
|---|---|
| Stream name | `DS_CAR` |
| Subjects | `dharma.car.>` |
| Retention | limits |
| Storage | file |
| Max age | 365 days |
| Replicas | 1 (local bootstrap); 3 (clustered) |
| Duplicate window | 60 minutes |
| Discard | old |
| Deny delete | true |
| Deny purge | true |

Rationale: the append-only + deny-delete contract is the non-backdatability proof
the IETF SCITT profile requires. Every `DS_CAR` message carries the `Nats-Msg-Id`
header equal to the CAR envelope `car_id + segment_name`, making dedup and audit
exact.

### DS_CAR_CHALLENGE (new — challenge state machine)

| Field | Value |
|---|---|
| Stream name | `DS_CAR_CHALLENGE` |
| Subjects | `dharma.car.*.s8.challenge`, `commons.car.challenge.>` |
| Retention | limits |
| Storage | file |
| Max age | 7 years |
| Replicas | 3 (challenge records are constitutional — high durability) |
| Duplicate window | 10 minutes |
| Discard | old |

The 7-year retention mirrors financial-services audit retention for challenge records.
The challenge desk SLA (5/10/30-day acknowledge/triage/initial-finding from
SPINE-20:261-275) is enforced by a durable consumer with `ack_wait = 5d`,
`max_deliver = 3`, and DLQ routing.

---

## Leaf Node Bridge — Local NATS → Synadia NGS

The leaf node config is a **zero-code-change** extension to the existing local
NATS server. Add the following to the NATS server config (or `.nats/server.conf`):

```hcl
# Synadia Cloud (NGS) leaf bridge
# Credentials from https://cloud.synadia.com — dedicated leaf account, restricted subject permissions
leafnodes {
  remotes = [
    {
      url: "tls://connect.ngs.global"
      credentials: "/Users/dhyana/.nats/synadia-leaf-car-commons.creds"
      account: CAR_COMMONS_LEAF
    }
  ]
}

accounts: {
  CAR_COMMONS_LEAF: {
    jetstream: enabled
    users: [ { user: car_leaf_local, password: $CAR_LEAF_PASSWORD } ]
    imports: [
      # Pull cross-boundary challenge verdicts from NGS
      { stream: { account: "$G", subject: "commons.car.challenge.>" }, prefix: "ngs" }
    ]
    exports: [
      # Push local challenge events to NGS (cross-boundary visibility)
      { stream: "dharma.car.*.s8.challenge" }
      # Push SIS burden declarations to NGS
      { stream: "dharma.car.*.s3.burden" }
      # Push anchor hashes to NGS (non-payload — sequence is the timestamp proof)
      { stream: "dharma.car.*.anchor" }
    ]
  }
}
```

**Permission discipline (per NGS account):**
- The leaf account MUST NOT have `publish: allow: ["commons.car.>"]` — it can only
  export named local subjects. Wildcards into the global namespace are prohibited.
- The NGS account for CAR_COMMONS receives the exported subjects and places them
  into an R3 JetStream stream for non-backdateable cross-boundary anchoring.
- GDPR fix (pre-requisite, from Round 1 REFUTED-as-designed): NGS streams carry
  **hash-only payloads** for identity-bearing segments (S1, S4). Full payloads stay
  local behind crypto-shredding keys. The anchor subject carries `{"car_id": "...",
  "segment_hashes": {"s1": "...", ...}, "merkle_root": "..."}` — never PII.

---

## Synadia Agent Protocol — Witness Registration

The [Synadia Agent Protocol (2026-05-25)](https://nats.io/blog/nats-native-protocol-for-ai-agents/)
defines how agents register as NATS micro-services with `name: "agents"`. This is
the commons **Witness Bench registration primitive** without a new registry process.

A commons witness node registers as:

```
$SRV.INFO.agents → responds with:
{
  "name": "agents",
  "metadata": {
    "agent": "witness",
    "owner": "{witness_org_id}",
    "protocol_version": "0.3",
    "car_witness": "true",
    "witness_scope": "ecological|financial|conduct|challenge",
    "jurisdiction": "{iso_country_code}",
    "independence_declaration": "{signed_hash}"
  }
}
```

Discovery: any CAR emitter can ping `$SRV.PING.agents` on the NGS commons account
and receive all registered witnesses — no central registry, no coordinator process.

Liveness: witness heartbeats on `agents.hb.witness.{owner}.{name}` at 30s cadence.
Three missed beats = witness offline; challenges queued for that witness are rerouted.

**Anti-capture invariant:** the commons account on NGS must permit witness
registration by any node with a valid NGS credential — the commons operator cannot
filter registrations. Witness deregistration requires the witness's own signing key.
No witness can block another witness's registration (deny-by-origin is prohibited
at the subject-permission level).

---

## SIS Integration — CAR S3 Material Burden

**SIS (Silicon Is Sand)** is the JK-level telos child that parents both GAIA and
Loomwork. It enters the CAR world through **S3 (material burden)** — the only
regulation-shaped material-burden hook in the 2026 protocol stack:

> EU GPAI Model Documentation Form § Compute and Energy Fields

The mapping:

```python
# GAIA GaiaPilotMeasurementContract → CAR S3 segment
sis_burden = {
    "schema": "dharma.car.s3.burden.v1",
    "car_id": car_id,
    "segment": "s3_material_burden",
    "emitter": {
        "agent_uid": "dharma-swarm-main",
        "telos": "jagat_kalyan"
    },
    "burden": {
        "compute_kwh": gaia_contract.measured_compute_kwh,
        "carbon_kg_co2e": gaia_contract.measured_carbon_kg,
        "obligation_usd": gaia_contract.total_obligation_usd,
        "measurement_mode": gaia_contract.measurement_mode,  # honest on every packet
        "methodology_ref": gaia_contract.methodology_ref,
        "gpai_model_doc_ref": "EU_GPAI_Art50_ModelCard_v1"
    },
    "conservation_laws": {
        "no_creation_ex_nihilo": True,   # sum(claimed) <= sum(verified)
        "no_double_counting": True,      # verify is injective
        "temporal_coherence": True       # vesting against measured curves
    },
    "challenge_contact": gaia_contract.challenge_contact,  # non-blank required
    "consent_status": gaia_contract.consent_status,
    "signed_at": utc_now(),
    "signed_by": signing_key_id
}
```

**The GAIA packet path (SPINE-20:64-92) is already the strongest existing CAR
prototype in the estate:**
- `measurement → obligation → qualification → routing → evidence → challengeable claim → review`
  maps exactly onto S3 → S4 → S5 → S6 → S7 → S8 → S9.
- The one failing test (`test_submit_claim_challenge_refreshes_canonical_reciprocity_summary`)
  sits precisely on S8 (challenge/reversal) — the load-bearing trust mechanism.
- Fixing that test IS implementing the CAR challenge state machine for the SIS domain.

---

## GAIA → CAR Envelope Wiring

GAIA's existing typed objects already carry the CAR semantics:

| CAR Segment | GAIA Object | Status |
|---|---|---|
| S1 identity/delegation | `GaiaPilotMeasurementContract.sponsor` + operator identity | EXISTS |
| S2 intent/telos | `GaiaInitiative.purpose` + telos_gates | EXISTS (BUILT) |
| S3 material burden | `total_obligation_usd` + compute/carbon fields | PARTIAL (obligation exists; CAR envelope missing) |
| S4 community authority | `consent_status` + `partner_credibility` gates | PARTIAL (gates exist; FPIC schema incomplete) |
| S5 evidence | 3-of-5 oracle quorum | EXISTS (BUILT) |
| S6 capital/action | `RoutingRecord` bounded by `total_obligation_usd` | EXISTS |
| S7 witnessed outcome | `OutcomeRecord` + `AuditRecord` | EXISTS in code; no external parties |
| S8 challenge/reversal | challenge_contact + 5/10/30-day SLAs | **BROKEN — failing test** |
| S9 learning | `adaptive_review` loop | EXISTS (design-only) |

The gap is: no CAR envelope wraps these GAIA fields, and S8 has a broken test.
The SIS track's minimum viable scope is: CAR envelope v0.1 around S3 + fix S8 test.

---

## Privacy Architecture — Pre-requisite (REFUTED-as-designed fix)

Before the first public NGS log entry, the following must be implemented:

1. **Hash-only on-log / encrypted payloads off-log:** NGS `commons.car.anchor.*`
   carries Merkle roots only. Identity-bearing fields (S1 name/DID, S4 community
   consent data) stay in the local NATS DS_CAR stream with crypto-shredding keys.

2. **SD-JWT / BBS+ selective disclosure:** CAR signers choose which S1 fields to
   disclose per challenge context. The commons challenge desk never receives full
   identity by default.

3. **DPIA before first public log entry** — mandatory, not optional. The eIDAS 2.0
   QTSP anchoring (Regulation (EU) 2024/1183) path requires compliance counsel
   review before any receipt is published to a public log.

4. **Key rotation contract:** each signing key carries a `valid_until` timestamp.
   The S8 challenge state machine MUST honor key rotation — a challenge on a receipt
   signed with a rotated key must still be verifiable via the key history chain.

---

## Sequencing and Acceptance Criteria

This spec is complete only when:

1. `DS_CAR` and `DS_CAR_CHALLENGE` stream definitions exist in the codebase.
2. `test_submit_claim_challenge_refreshes_canonical_reciprocity_summary` passes — the
   S8 challenge state machine is load-bearing.
3. A `dharma.car.{car_id}.s3.burden` message carrying dharma_swarm's own compute
   obligation (Receipt Zero for SIS) has been published, persisted in DS_CAR, and
   its SHA-256 hash is committed to the repo as a transparency anchor.
4. The leaf node bridge config exists in the repo (not necessarily live — existence
   of the config is the seeding artifact; live NGS connection requires operator
   account + D1 HOLD decision).
5. `NATS_SUBSTRATE_MASTER_SPEC.md` references this file and declares `DS_CAR` as a
   declared (not yet live) surface.
6. The SIS active track has been opened (requires one existing track to close or
   ceiling to move — see `proposed_tracks/sis-material-body-2026-07.yaml`).

---

## Connection to the Round 1 Decision Packet

| Decision | Connection to this spec |
|---|---|
| D1 (HOLD on outreach) | Leaf node config is internal artifact — no external party contacted. HOLD does not block seeding. |
| D2 (kill-condition-1 08-07) | The SIS track's first cash criterion (≥1 paying subscriber) IS the same act as satisfying kill-condition-1's MOU/customer gate. |
| D3 (open receipt-signing track) | This spec proposes SIS as the track; `receipt-signing-2026-07` may be the same track retargeted. |
| D4 (ratify Seal→Confess→Sign-forward) | Receipt Zero for SIS = the Confess+Sign-forward motion on the existing GAIA corpus. |
| D5 (language embargo) | External face: "GPAI-compliant compute obligation receipt" not "Web5 material burden." |
| D6 (Commons seat in telos hierarchy) | SIS already has a seat (JK-level child in SOVEREIGN_MANIFEST); the Commons needs a seat — SOVEREIGN_MANIFEST amendment still required. |

---

## Anti-Slop Rules (extension of NATS_SUBSTRATE_MASTER_SPEC.md §Anti-Slop Rules)

Agents must not:

- Publish a CAR segment to DS_CAR without a `car_id` linking all nine segments.
- Publish S3 burden to NGS without first passing the S8 challenge test (challenge
  path must be live before any burden is anchored globally).
- Claim "GAIA is integrated with the CAR" until Receipt Zero (S3 burden for
  dharma_swarm itself) has been published, persisted, and its hash committed.
- Use `commons.car.*` subjects on local NATS without the leaf bridge — those
  subjects on local NATS are not cross-boundary evidence.
- Narrate the Commons as operational before the SIS track's Month-6 stop-rule
  criteria are met: ≥1 external countersigned receipt + ≥1 paying subscriber.

---

## References

- `docs/governance/NATS_SUBSTRATE_MASTER_SPEC.md` — local fleet substrate (this spec extends it)
- `~/handoffs/2026-07-11_web5_commons_research/MASTER_SYNTHESIS.md` — Round 1 hardening
- `~/handoffs/2026-07-11_web5_commons_research/canon_sis-gaia.md` — GAIA/SIS canon digest
- Synadia Agent Protocol: https://nats.io/blog/nats-native-protocol-for-ai-agents/ (2026-05-25)
- Synadia Cloud docs: https://docs.synadia.com/cloud/
- RFC 9943 (SCITT) — the IETF profile this CAR is a superset of
- NATS JetStream per-stream Raft scaling: https://www.synadia.com/blog/jetstream-raft-per-stream-scaling
- EU GPAI Regulation (enforcement 2026-08-02) — the regulation-shaped commercial hook for SIS
- Regulation (EU) 2024/1183 — eIDAS 2.0 QTSP (⚠ single-sourced; read before external use)
