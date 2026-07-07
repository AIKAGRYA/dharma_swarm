import json, hashlib

path="/Users/dhyana/dharma_swarm/telos_titanium/dharma_lane_research/ucl_genesis_receipt_bc5ae73f.json"
r=json.load(open(path))

def jcs(o):
    # receipt uses only ASCII strings, ints, null, bool -> json.dumps with sort_keys+compact == RFC8785 here
    return json.dumps(o, sort_keys=True, separators=(',',':'), ensure_ascii=False).encode()

body={k:v for k,v in r.items() if k not in ("receipt_id","signatures")}
rid="sha256:"+hashlib.sha256(jcs(body)).hexdigest()
print("recomputed receipt_id:", rid)
print("stored     receipt_id:", r["receipt_id"])
print("MATCH (exclusion-based derivation verified):", rid==r["receipt_id"])

ch="sha256:"+hashlib.sha256(jcs(r["claim"])).hexdigest()
print("claim_hash match:", ch==r["claim_hash"], ch)

# Adversarial: does the receipt ANYWHERE literally contain its own hash hex? (it must not, per claim)
hexpart=r["receipt_id"].split(":")[1]
raw=open(path,'rb').read().decode()
count=raw.count(hexpart)
print("occurrences of own hash hex in file:", count, "(1 = only in receipt_id field, excluded from hash input)")
# confirm the hash-input bytes do NOT contain the hash
print("hash input contains own hash:", hexpart in jcs(body).decode())
