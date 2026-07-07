# Countermodel test: does Proven_by(schema validation) recover the AUTHORITY
# that Attested_by carried at boot? Or only well-formedness?
import json, hashlib

# A minimal genesis schema (decidable well-formedness check)
def valid_genesis(doc):
    return (isinstance(doc, dict)
        and set(doc) == {"version", "modalities", "succession_rule", "cohort"}
        and isinstance(doc["modalities"], list) and len(doc["modalities"]) >= 1
        and isinstance(doc["succession_rule"], str)
        and isinstance(doc["cohort"], list))

g1 = {"version": 1, "modalities": ["Attested_by","Proven_by","Assumed"],
      "succession_rule": "k_of_n_reattest", "cohort": ["alice","bob","carol"]}

# Rival genesis: same schema, HOSTILE semantics (adversary's cohort, rule inverted)
g2 = {"version": 1, "modalities": ["Attested_by","Proven_by","Assumed"],
      "succession_rule": "mallory_sole_authority", "cohort": ["mallory"]}

print("g1 well-formed:", valid_genesis(g1))
print("g2 well-formed:", valid_genesis(g2))
print("g1 hash:", hashlib.sha256(json.dumps(g1,sort_keys=True).encode()).hexdigest()[:16])
print("g2 hash:", hashlib.sha256(json.dumps(g2,sort_keys=True).encode()).hexdigest()[:16])
print()
print("Schema validation distinguishes legitimate from hostile genesis:",
      valid_genesis(g1) != valid_genesis(g2))
