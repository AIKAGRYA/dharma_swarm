import json, hashlib, sys

OUT = "/private/tmp/claude-501/-Users-dhyana/f4e3640e-7f97-4b75-8403-ef7c49af3082/scratchpad/ucl/bootstrap_receipt.json"

# JCS (RFC 8785) for this value domain: all object keys are ASCII (UTF-16 code
# unit order == ASCII order), all numbers are the integer 0, values are
# strings/null/bool/arrays/objects -> python json with sort_keys + compact
# separators emits exactly the JCS byte sequence.
def jcs(o):
    return json.dumps(o, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")

def h(o):
    return "sha256:" + hashlib.sha256(jcs(o)).hexdigest()

T = "2026-07-04T00:00:00Z"

# subject: the receipt itself. selector fields = subject minus subject_id.
selector = {"kind": "receipt_self"}
subject_id = h(selector)
subject = {"kind": "receipt_self", "subject_id": subject_id}

claim = {
    "claim_id": "claim.ucl.genesis.self_wellformed",
    "claim_class": "definitional",
    "claim_strength": "axiomatic",
    "fragment_id": "fragment.ucl.kernel.v0",
    "statement": "This receipt is a well-formed program in the language it defines. UCL-0 is the least set of receipts containing this receipt and closed under the admission rules of fragment.ucl.kernel.v0. The identity of this receipt is derived, not chosen: receipt_id equals the sha256 hash URI of the JCS canonical form of this receipt with the fields receipt_id and signatures removed.",
    "scope": {"paths": [], "symbols": []},
}
claim_hash = h(claim)

trust_base_id = "trust.ucl.genesis.v0"
fragment_id = "fragment.ucl.kernel.v0"
fragment_version = "v0"

authority_key = h({
    "subject_id": subject_id,
    "claim_hash": claim_hash,
    "trust_base_id": trust_base_id,
    "fragment_id": fragment_id,
    "fragment_version": fragment_version,
})

base_snapshot_hash = h({})  # the empty mesh, content-addressed

body = {
    "schema_version": "dharma.naga_receipt.v1",
    "subject": subject,
    "claim": claim,
    "claim_hash": claim_hash,
    "evidence": [],
    "authority": {
        "trust_base_id": trust_base_id,
        "fragment_id": fragment_id,
        "fragment_version": fragment_version,
        "authority_scope": "axiomatic_root",
        "transfer_rule": "endorsement_quorum",
    },
    "causal_origin": {
        "producer": "claude-fable-5",
        "artifact_trace": "redacted",
        "redaction_policy": "prompt_hash_only",
    },
    "epistemic_origin": {
        "trust_base_id": trust_base_id,
        "checker": "none_at_genesis",
    },
    "ttl": {"issued_at": T, "expires_at": "2126-07-04T00:00:00Z"},
    "challenge_base": {
        "mesh_id": "mesh.ucl.genesis",
        "authority_key": authority_key,
        "evidence_horizon": "P0D",
        "horizon_start": T,
        "horizon_end": T,
        "snapshot_observed_at": T,
        "base_snapshot_hash": base_snapshot_hash,
    },
    "challenge_state": {
        "authoritative": False,
        "observed_at": T,
        "unresolved_count": 0,
        "challenge_receipt_ids": [],
    },
    "clock": {"observed_at": T, "clock_uncertainty_ms": 0, "max_clock_skew_ms": 0},
    "prev_receipt_hash": None,
}

# THE DERIVATION RULE: receipt_id = sha256 of the canonical signature input
# (JCS bytes of the receipt with receipt_id and signatures removed).
receipt_id = h(body)

receipt = dict(body)
receipt["receipt_id"] = receipt_id
receipt["signatures"] = []  # deferred-signature genesis

blob = jcs(receipt)
with open(OUT, "wb") as f:
    f.write(blob)

# Independent verification pass: re-read bytes, strip the two excluded fields,
# recompute, compare.
reloaded = json.loads(open(OUT, "rb").read().decode("utf-8"))
stripped = {k: v for k, v in reloaded.items() if k not in ("receipt_id", "signatures")}
recomputed = h(stripped)
assert recomputed == reloaded["receipt_id"], "FIXED-POINT CHECK FAILED"
assert jcs(reloaded) == blob, "JCS ROUND-TRIP FAILED"

print("subject_id        =", subject_id)
print("claim_hash        =", claim_hash)
print("authority_key     =", authority_key)
print("base_snapshot     =", base_snapshot_hash)
print("receipt_id        =", receipt_id)
print("recomputed id     =", recomputed)
print("bytes             =", len(blob))
print("VERIFIED: receipt_id == sha256(JCS(receipt - {receipt_id, signatures}))")
