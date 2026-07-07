import json, math, random, struct, hashlib

print("=== 1. IEEE 754 non-associativity ===")
a, b, c = 1e16, -1e16, 1.0
print("(a+b)+c =", (a+b)+c, " a+(b+c) =", a+(b+c), " equal?", (a+b)+c == a+(b+c))

print("\n=== 2. Reduction-order dependence (simulated parallel sums) ===")
random.seed(7)
xs = [random.uniform(-1,1)*10**random.uniform(0,12) for _ in range(100000)]
def tree_sum(v):
    while len(v) > 1:
        v = [v[i]+v[i+1] if i+1 < len(v) else v[i] for i in range(0, len(v), 2)]
    return v[0]
sums = set()
for trial in range(20):
    random.shuffle(xs)
    sums.add(struct.pack('<d', tree_sum(xs)).hex())
print("distinct bit patterns across 20 shuffled reductions:", len(sums))
print("=> distinct content-addresses (sha256 of bits):", len({hashlib.sha256(bytes.fromhex(s)).hexdigest() for s in sums}))

print("\n=== 3. JSON/JCS: NaN, Infinity, >2^53 ===")
for v in (float('nan'), float('inf')):
    try:
        s = json.dumps(v, allow_nan=False)
        print(v, "->", s)
    except ValueError as e:
        print(repr(v), "-> ValueError (no JSON grammar production):", e)
n = 2**53 + 1
print("2^53+1 =", n, "as IEEE double ->", int(float(n)), " lossy?", int(float(n)) != n)
print("JCS/ES number serialization of 2^53 and 2^53+1 as doubles:",
      repr(json.dumps(float(2**53))), repr(json.dumps(float(2**53+1))), "(collide)")

print("\n=== 4. Countermodel attempt A: quantize-to-grid then hash (rescues content-addressing?) ===")
eps = 1e-6
def qhash(x): return hashlib.sha256(struct.pack('<d', round(x/eps)*eps)).hexdigest()[:8]
u, v = 1.2345675e0, 1.2345665e0   # differ by 1e-6 straddling a grid boundary
print("|u-v| =", abs(u-v), " qhash(u)==qhash(v)?", qhash(u)==qhash(v), "-> boundary fracture persists")

print("\n=== 5. Countermodel attempt B: pairwise tolerance as identity (transitivity) ===")
e = 1.0
p, q, r = 0.0, 0.9*e, 1.8*e
close = lambda x,y: abs(x-y) <= e
print("close(p,q):", close(p,q), " close(q,r):", close(q,r), " close(p,r):", close(p,r),
      "-> epsilon-closeness NOT transitive; identity must attach to a FIXED declared enclosure, not pairwise tolerance")

print("\n=== 6. Fixed declared enclosure IS a well-defined identity ===")
lo, hi = 1.23456, 1.23457
member = lambda x: lo <= x <= hi
print("member(u):", member(u), " member(v):", member(v), "-> same subject via enclosure ID; membership decidable/receiptable")
