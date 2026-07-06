import hashlib, json, itertools, time

# --- Test 1: Does Proven_by(schema validation) select an authoritative genesis?
# Minimal well-formedness checker (decidable, as claimed).
SCHEMA = {"required": {"version": str, "founders": list, "rules": dict, "ttl_s": int}}
def well_formed(doc):
    return all(k in doc and isinstance(doc[k], t) for k, t in SCHEMA["required"].items())

G  = {"version":"1.0","founders":["cohortA"],"rules":{"renewal":"k-of-n"},"ttl_s":86400}
G2 = {"version":"1.0","founders":["attacker"],"rules":{"renewal":"attacker-only"},"ttl_s":10**9}
print("Genesis G   well-formed:", well_formed(G))
print("Rival  G'   well-formed:", well_formed(G2))
print("=> Proven_by(schema) grades BOTH identically; it proves well-formedness, not authority.\n")

# --- Test 2: TTL expiry evaluation after expiry (circularity probe)
def authority_valid(doc, now, boot_time):
    # The TTL rule lives INSIDE the genesis. After expiry, is the TTL rule itself in force?
    expired = now > boot_time + doc["ttl_s"]
    # To declare 'expired => invalid' we must trust doc['ttl_s'] semantics, i.e. an expired rule.
    return not expired
now = 1000000; boot = 0
print("At t>TTL, authority_valid =", authority_valid(G, now, boot),
      " (the check itself used the expired rule => evaluator must hardcode expiry semantics)\n")

# --- Test 3: '3-receipt multi-sig hash cycle' feasibility (deepseek option), toy scale.
# Cycle: A contains H(B), B contains H(C), C contains H(A). Fixed-point search on truncated hash.
def H(x, bits):
    return hashlib.sha256(x).hexdigest()[: bits // 4]
for bits in (8, 12, 16, 20):
    tries = 0; t0 = time.time(); found = False
    # search: guess H(A) field value, build C,B,A, check consistency
    for guess in itertools.count():
        tries += 1
        gA = format(guess % (2**bits), "0{}x".format(bits//4))
        C = ("receiptC|sig3|refA:" + gA).encode()
        B = ("receiptB|sig2|refC:" + H(C, bits)).encode()
        A = ("receiptA|sig1|refB:" + H(B, bits)).encode()
        if H(A, bits) == gA:
            found = True; break
        if tries > 2**(bits+3): break
    print(f"hash-cycle {bits}-bit: found={found} tries={tries} ({time.time()-t0:.2f}s)")
print("=> tries scale ~2^bits; at 256-bit a literal content-hash cycle is computationally infeasible.")
