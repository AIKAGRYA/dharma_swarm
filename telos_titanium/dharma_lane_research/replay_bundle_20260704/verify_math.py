import json, hashlib, math, itertools, sys

print("=" * 70)
print("CHECK 1: Number of partial orders on a 4-element labeled set")
# enumerate all reflexive, antisymmetric, transitive relations on {0,1,2,3}
n = 4
pairs = [(i, j) for i in range(n) for j in range(n) if i != j]
count = 0
posets = []
for bits in range(1 << len(pairs)):
    rel = set((i, i) for i in range(n))
    ok = True
    for k, (i, j) in enumerate(pairs):
        if bits >> k & 1:
            rel.add((i, j))
    # antisymmetry
    for (i, j) in list(rel):
        if i != j and (j, i) in rel:
            ok = False
            break
    if not ok:
        continue
    # transitivity
    for (a, b) in rel:
        for (c, d) in rel:
            if b == c and (a, d) not in rel:
                ok = False
                break
        if not ok:
            break
    if ok:
        count += 1
        posets.append(frozenset(rel))
print(f"partial orders on 4 labeled elements = {count}  (claim: 219)")

print("=" * 70)
print("CHECK 2: meet-term never exceeds inputs (a AND b <= a, <= b) in every")
print("poset on 4 elements where the meet exists  — exhaustive")
violations = 0
meets_checked = 0
for rel in posets:
    le = lambda x, y: (x, y) in rel
    for a in range(n):
        for b in range(n):
            lower = [z for z in range(n) if le(z, a) and le(z, b)]
            meets = [m for m in lower if all(le(z, m) for z in lower)]
            if meets:
                m = meets[0]
                meets_checked += 1
                if not (le(m, a) and le(m, b)):
                    violations += 1
print(f"meets checked across all 219 posets: {meets_checked}, violations: {violations} (claim: 0)")

print("=" * 70)
print("CHECK 3: arithmetic claims")
v = 0.95 ** 100
print(f"0.95^100 = {v:.6f}  (claim: ~0.006)")
# log-odds fusion of two independent p=0.8
odds = (0.8/0.2) * (0.8/0.2)
p = odds / (1 + odds)
print(f"two independent p=0.8 fuse (log-odds) = {p:.4f}  (claim: ~0.94)")
# Ed25519 cycles at 168 MHz
for cyc in (720_000, 1_265_078):
    ms = cyc / 168e6 * 1000
    print(f"{cyc} cycles @168MHz = {ms:.2f} ms  (claim: 4.3-7.5 ms range)")
ctrl_cycles = 8e-6 * 168e6
print(f"8us control law = {ctrl_cycles:.0f} cycles; ratio 1,265,078/{ctrl_cycles:.0f} = {1_265_078/ctrl_cycles:.0f}x  (claim: 941x)")
print(f"vs 1000us loop period: {720_000/ (1000e-6*168e6):.1f}x to {1_265_078/(1000e-6*168e6):.1f}x  (claim: 3-8x)")
print(f"1 - 1/e = {1 - 1/math.e:.4f}  (random-oracle fixed-point existence prob claim)")

print("=" * 70)
print("CHECK 4: genesis receipt hash recomputation")
path = "/Users/dhyana/dharma_swarm/telos_titanium/dharma_lane_research/ucl_genesis_receipt_bc5ae73f.json"
raw = open(path, "rb").read()
print(f"file bytes: {len(raw)}  (claim: 2036)")
print(f"storage hash sha256(file) = {hashlib.sha256(raw).hexdigest()}")
print(f"  claim:                    8f34148808193655665812b08b2c826e53d084c5eefc15a68e8ae9e2d61cd76a")
obj = json.loads(raw)

def jcs(o):
    # RFC 8785 for this object: only strings, ints (0), null, arrays, objects -> python dumps matches
    return json.dumps(o, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")

reduced = {k: v for k, v in obj.items() if k not in ("receipt_id", "signatures")}
rid = hashlib.sha256(jcs(reduced)).hexdigest()
print(f"derived receipt_id  = sha256:{rid}")
print(f"  claim/in-file     = {obj['receipt_id']}")
print(f"  MATCH: {('sha256:' + rid) == obj['receipt_id']}")
ch = hashlib.sha256(jcs(obj["claim"])).hexdigest()
print(f"derived claim_hash  = sha256:{ch}")
print(f"  in-file           = {obj['claim_hash']}")
print(f"  MATCH: {('sha256:' + ch) == obj['claim_hash']}")
empty = hashlib.sha256(jcs({})).hexdigest()
print(f"sha256(JCS({{}}))     = {empty}")
print(f"  claim (base_snapshot_hash) = 44136fa355b3678a1146ad16f7e8649e94fb4fc21fe77e8310c060f61caaff8a")
print(f"  MATCH: {empty == '44136fa355b3678a1146ad16f7e8649e94fb4fc21fe77e8310c060f61caaff8a'}")
