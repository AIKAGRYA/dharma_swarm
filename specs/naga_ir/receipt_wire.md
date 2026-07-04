# NĀGA Receipt Wire

Status: draft

Review target: PR #2 wire schema

## Wire identity

The receipt schema id is `dharma.naga_receipt.v1`. [confidence: 94/100] A conforming receipt is a JSON object whose canonical signature input is the JSON Canonicalization Scheme byte sequence of the receipt with `signatures` removed. [confidence: 92/100] [RFC 8785](https://www.rfc-editor.org/rfc/rfc8785), [RFC 3339](https://www.rfc-editor.org/rfc/rfc3339)

## Encoding profile

The measured object is the serialized receipt. [confidence: 95/100] The threshold is: JCS canonical JSON, no duplicate object names, all timestamps in UTC RFC 3339 form with `Z`, all hash strings matching `^sha256:[0-9a-f]{64}$`, and all signature records matching the shape below. [confidence: 93/100] [RFC 8785](https://www.rfc-editor.org/rfc/rfc8785), [RFC 3339](https://www.rfc-editor.org/rfc/rfc3339)

```json
{
  "signer_id": "principal.example",
  "key_id": "redacted-key-id",
  "alg": "ed25519",
  "signed_at": "2026-07-03T15:00:00Z",
  "signature": "base64url:example"
}
```

The `signature` field encoding is profile-specific, but a canonical receipt requires at least one signature that verifies against the canonical signature input. [confidence: 92/100]

## Signature policy

The measured object is `(signature, key_id, trust_base_id)`. [confidence: 94/100] The PR #2 profile admits `ed25519` signatures encoded as unpadded base64url strings matching `^base64url:[A-Za-z0-9_-]+$`. [confidence: 92/100] `key_id` must resolve through `authority.trust_base_id` or a checked-refinement receipt to a public key, signer role, and key validity window; otherwise `signatures_valid` fails closed. [confidence: 93/100] [RFC 8032](https://www.rfc-editor.org/rfc/rfc8032)

## Receipt object

The measured object is one JSON object. [confidence: 98/100] The admission threshold is that every required top-level field is present, every hash is a `sha256:` hash URI, every TTL uses UTC RFC 3339 format, and every evidence record validates against its modality contract. [confidence: 93/100]

| Field | Type | Required | Threshold | Confidence |
|---|---|---:|---|---:|
| `schema_version` | string | yes | equals `dharma.naga_receipt.v1` | 98/100 |
| `receipt_id` | string | yes | stable id scoped to subject and claim | 92/100 |
| `subject` | object | yes | content hash or source selector present | 94/100 |
| `claim` | object | yes | typed claim id and fragment id present | 94/100 |
| `claim_hash` | string | yes | hash URI derived from canonical claim object | 95/100 |
| `evidence` | array | yes | length >= 1 for canonical claims | 93/100 |
| `authority` | object | yes | trust base, fragment id, and fragment version present | 95/100 |
| `causal_origin` | object | yes | producer trace present or explicitly redacted | 91/100 |
| `epistemic_origin` | object | yes | checker trust base present | 95/100 |
| `ttl` | object | yes | `expires_at > issued_at` | 93/100 |
| `challenge_base` | object | yes | mesh id and evidence horizon present | 95/100 |
| `challenge_state` | object | yes | cached summary marked non-authoritative | 94/100 |
| `clock` | object | yes | observed time and allowed skew present | 91/100 |
| `prev_receipt_hash` | string or null | yes | null for genesis, hash URI otherwise | 91/100 |
| `signatures` | array | yes | at least one valid signer for canonical transfer | 89/100 |

## Subject

`subject` identifies the artifact whose authority is under review. [confidence: 94/100] The threshold is one of `content_hash`, `path + git_commit`, `symbol + git_commit`, or `packet_id + payload_hash`; path-only subjects are non-canonical. [confidence: 93/100]

`subject_id` is defined by derivation, not chosen. [confidence: 94/100] If `content_hash` is present, `subject_id == content_hash`; otherwise `subject_id` is `sha256:` plus the SHA-256 digest of the JCS object containing the admitted selector fields. [confidence: 93/100]

```json
{
  "kind": "source_symbol",
  "path": "dharma_swarm/coalgebra.py",
  "symbol": "bisimilar",
  "git_commit": "HEAD",
  "content_hash": "sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
}
```

## Claim

`claim` is defined as one typed proposition about one fragment. [confidence: 92/100] A claim with multiple independent propositions must be split unless one verifier discharges the conjunction as a single obligation. [confidence: 90/100] This keeps `Proven_by` evidence from silently covering only part of an English sentence. [confidence: 93/100]

`claim_hash` is defined by derivation, not chosen. [confidence: 95/100] The derivation is `sha256:` plus the SHA-256 digest of the JCS canonical claim object covering `claim_id`, `claim_class`, `claim_strength`, normalized `statement`, `scope`, `fragment_id`, and `obligation_hash` when present; `authority_key` must use `claim_hash`, not bare `claim_id`. [confidence: 95/100]

```json
{
  "claim_id": "claim.example.contract.bound",
  "claim_class": "contract",
  "claim_strength": "deductive",
  "fragment_id": "fragment.example.contract",
  "statement": "The named fragment satisfies the stated contract under the named trust base.",
  "scope": {
    "paths": ["specs/naga_ir/core.md"],
    "symbols": []
  }
}
```

## Evidence record

Every evidence item has a modality-specific body and a shared envelope. [confidence: 94/100] The shared threshold is `modality`, `method`, `result`, `trust_base_id`, `fragment_id`, `issued_at`, and `ttl_expires_at` present; records missing any shared field are inadmissible. [confidence: 95/100]

```json
{
  "modality": "Proven_by",
  "method": "verifier-name",
  "result": "pass",
  "trust_base_id": "trust.example.v1",
  "fragment_id": "fragment.example",
  "issued_at": "2026-07-03T15:00:00Z",
  "ttl_expires_at": "2026-07-10T15:00:00Z",
  "body": {}
}
```

## Proven_by

`Proven_by` records deductive evidence from a named verifier over a bounded fragment. [confidence: 94/100] The threshold is `result == "pass"`, verifier version present, obligation hash present, assumptions present, and trust base matching the authority pair. [confidence: 93/100] [First-Class Verification Dialects for MLIR](https://users.cs.utah.edu/~regehr/papers/pldi25.pdf), [Fifteen Years of Viper](https://pm.inf.ethz.ch/publications/EilersSchwerhoffSummersMueller25.pdf)

Required body fields:

| Field | Threshold | Confidence |
|---|---|---:|
| `verifier` | non-empty string | 96/100 |
| `verifier_version` | non-empty string | 94/100 |
| `obligation_hash` | hash URI | 94/100 |
| `assumptions` | array, explicit even if empty | 95/100 |
| `resource_limits` | timeout or bound present | 90/100 |
| `output_hash` | hash URI or redacted hash URI | 91/100 |

## Tested_by

`Tested_by` records statistical or example-based evidence and must not be treated as proof. [confidence: 96/100] The threshold for canonical use is that the harness, seed, coverage metric, coverage threshold, observed coverage, mutation policy, and result are all recorded and the observed values meet the declared thresholds. [confidence: 93/100]

Required body fields:

| Field | Threshold | Confidence |
|---|---|---:|
| `harness` | non-empty string | 95/100 |
| `seed` | explicit value or deterministic seed policy | 92/100 |
| `coverage_metric` | named metric | 92/100 |
| `coverage_threshold` | numeric, required for canonical use | 92/100 |
| `coverage_observed` | numeric, required for canonical use | 92/100 |
| `mutation_policy` | `required`, `not_applicable`, or `not_claimed_noncanonical` | 92/100 |
| `mutation_threshold` | numeric when `mutation_policy == "required"` | 90/100 |
| `mutation_score` | numeric and threshold-satisfying when `mutation_policy == "required"` | 90/100 |
| `mutation_not_applicable_reason` | non-empty when `mutation_policy == "not_applicable"` | 90/100 |
| `bounds` | array of explicit exclusions or limits | 91/100 |

## Witnessed_by

`Witnessed_by` records runtime observation bound to identity and freshness. [confidence: 91/100] The threshold is a runtime identity, observed value hash, replay or trace hash, TTL, observed time, and maximum clock skew; a witness beyond TTL or beyond allowed skew is historical evidence but cannot support canonization. [confidence: 94/100] The `observed_at` and `max_clock_skew_ms` body fields are wire-only freshness-envelope extensions beyond the core required fields. [confidence: 93/100]

Required body fields:

| Field | Threshold | Confidence |
|---|---|---:|
| `runtime_id` | non-empty runtime identity | 94/100 |
| `identity` | signed or trust-base-resolved witness identity | 93/100 |
| `observed_value_hash` | hash URI of observed value or redacted value | 93/100 |
| `replay_hash` | hash URI, trace hash, or explicit non-replayable marker | 91/100 |
| `observed_at` | UTC RFC 3339 timestamp | 92/100 |
| `max_clock_skew_ms` | non-negative integer bound | 92/100 |
| `ttl_expires_at` | UTC RFC 3339 timestamp after observation | 93/100 |

## Challenged_by

`Challenged_by` records a counterclaim that blocks canonization while unresolved. [confidence: 95/100] The threshold is a challenge receipt id, adversary identity, counterexample or narrowing argument, and resolution state in `open`, `refuted`, `accepted`, or `expired`. [confidence: 93/100]

## Attested_by

`Attested_by` records human or authority sign-off. [confidence: 93/100] The threshold is signer identity, role, jurisdiction or authority scope, TTL, and signature; it is never sufficient alone for safety or effect-boundary claims. [confidence: 95/100]

## Authority

`authority` names the epistemic ceiling for transfer. [confidence: 95/100] The threshold is exact match between `authority.trust_base_id`, `authority.fragment_id`, `authority.fragment_version`, `epistemic_origin.trust_base_id`, every admissible evidence trust base, and the current trust base, fragment, and fragment version unless a checked refinement receipt is named. [confidence: 94/100]

```json
{
  "trust_base_id": "trust.example.v1",
  "fragment_id": "fragment.example",
  "fragment_version": "git:HEAD",
  "authority_scope": "canonical_within_fragment",
  "transfer_rule": "recheck_on_trust_base_change"
}
```

## Authority key

`authority_key` is defined by derivation, not chosen. [confidence: 95/100] The derivation is `sha256:` plus the SHA-256 digest of the JCS canonical object `{subject_id, claim_hash, trust_base_id, fragment_id, fragment_version}`; the result must equal `challenge_base.authority_key`. [confidence: 95/100]

## Origin

`causal_origin` answers what produced the artifact; `epistemic_origin` answers what checked the claim. [confidence: 96/100] The threshold is that both records exist and neither can satisfy the other's required fields. [confidence: 95/100]

## Challenge base

`challenge_base` names the event base used to establish absence of unresolved challenges. [confidence: 95/100] The threshold is a mesh id, query key, evidence horizon, horizon bounds, snapshot observation time, and base snapshot hash; a receipt without a challenge base cannot be canonical. [confidence: 96/100]

```json
{
  "mesh_id": "mesh.pr2.naga_ir",
  "authority_key": "sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
  "evidence_horizon": "P14D",
  "horizon_start": "2026-06-19T15:00:00Z",
  "horizon_end": "2026-07-03T15:00:00Z",
  "snapshot_observed_at": "2026-07-03T15:00:00Z",
  "base_snapshot_hash": "sha256:cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc"
}
```

## Challenge state

`challenge_state` is a cached summary of open dispute pressure and is never authoritative by itself. [confidence: 96/100] Canonization requires a query over `challenge_base`, not trust in this summary. [confidence: 96/100]

```json
{
  "authoritative": false,
  "observed_at": "2026-07-03T15:00:00Z",
  "unresolved_count": 0,
  "challenge_receipt_ids": []
}
```

## Clock

`clock` bounds freshness decisions. [confidence: 91/100] Canonicality requires `observed_at <= ttl.expires_at` and `clock_uncertainty_ms <= max_clock_skew_ms`; otherwise the result is `unknown`, not `canonical`. [confidence: 92/100]

```json
{
  "observed_at": "2026-07-03T15:00:00Z",
  "clock_uncertainty_ms": 100,
  "max_clock_skew_ms": 5000
}
```

## Canonicality

A receipt is canonical at observation time `t` only if the shared predicate in [core.md](core.md) holds over `(receipt, mesh_state, current, t)`. [confidence: 95/100] Signature verification, signer/key trust resolution, admissible evidence, TTL liveness, authority matching, clock skew, and challenge-base query success are all required. [confidence: 94/100] Canonicality is a predicate over receipt plus mesh state at time `t`, not an eternal status bit. [confidence: 96/100]

## Example

This example is non-canonical because its hashes and signature are illustrative placeholders. [confidence: 98/100] It is also non-canonical because `Attested_by` cannot discharge a `deductive` claim without admissible `Proven_by` evidence. [confidence: 96/100] It demonstrates field shape only; a canonical receipt must use real content hashes, admissible evidence for the claim strength, and a verifiable signature. [confidence: 97/100]

```json
{
  "schema_version": "dharma.naga_receipt.v1",
  "receipt_id": "receipt.example.001",
  "subject": {
    "kind": "source_file",
    "path": "specs/naga_ir/core.md",
    "git_commit": "HEAD",
    "content_hash": "sha256:dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd"
  },
  "claim": {
    "claim_id": "claim.naga.core.canonization.bound",
    "claim_class": "contract",
    "claim_strength": "deductive",
    "fragment_id": "fragment.specs.naga_ir.core.canonization",
    "statement": "Canonization is bounded by evidence, horizon, TTL, and trust base."
  },
  "claim_hash": "sha256:abababababababababababababababababababababababababababababababab",
  "evidence": [
    {
      "modality": "Attested_by",
      "method": "human_review",
      "result": "pass",
      "trust_base_id": "trust.pr2.spec_review.v1",
      "fragment_id": "fragment.specs.naga_ir.core.canonization",
      "issued_at": "2026-07-03T15:00:00Z",
      "ttl_expires_at": "2026-07-10T15:00:00Z",
      "body": {
        "principal": "reviewer",
        "role": "spec_reviewer",
        "jurisdiction": "repo_pr2",
        "signature_ref": "sig:example"
      }
    }
  ],
  "authority": {
    "trust_base_id": "trust.pr2.spec_review.v1",
    "fragment_id": "fragment.specs.naga_ir.core.canonization",
    "fragment_version": "git:HEAD",
    "authority_scope": "draft_spec",
    "transfer_rule": "recheck_on_trust_base_change"
  },
  "causal_origin": {
    "producer": "codex",
    "artifact_trace": "redacted",
    "redaction_policy": "prompt_hash_only"
  },
  "epistemic_origin": {
    "trust_base_id": "trust.pr2.spec_review.v1",
    "checker": "decorrelated_review_council"
  },
  "ttl": {
    "issued_at": "2026-07-03T15:00:00Z",
    "expires_at": "2026-07-10T15:00:00Z"
  },
  "challenge_base": {
    "mesh_id": "mesh.pr2.naga_ir",
    "authority_key": "sha256:eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee",
    "evidence_horizon": "P14D",
    "horizon_start": "2026-06-19T15:00:00Z",
    "horizon_end": "2026-07-03T15:00:00Z",
    "snapshot_observed_at": "2026-07-03T15:00:00Z",
    "base_snapshot_hash": "sha256:ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff"
  },
  "challenge_state": {
    "authoritative": false,
    "observed_at": "2026-07-03T15:00:00Z",
    "unresolved_count": 0,
    "challenge_receipt_ids": []
  },
  "clock": {
    "observed_at": "2026-07-03T15:00:00Z",
    "clock_uncertainty_ms": 100,
    "max_clock_skew_ms": 5000
  },
  "prev_receipt_hash": null,
  "signatures": [
    {
      "signer_id": "principal.example",
      "key_id": "redacted-key-id",
      "alg": "ed25519",
      "signed_at": "2026-07-03T15:00:00Z",
      "signature": "base64url:example"
    }
  ]
}
```
