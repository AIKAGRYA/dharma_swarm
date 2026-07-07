"""Countermodel check: does per-trust-base local descent compose across a mesh join?

State = receipt multiset. V_A(G) = number of receipts carrying an open A-obligation.
Trust base A's admission policy: delta V_A <= 0 (admit only resolutions or neutral).
Trust base B's admission policy: delta V_B <= 0, but B's V ignores A-obligations.
Join = union of admission histories (each receipt admitted under ONE base's policy).
"""
def vA(G): return sum(1 for r in G if r.get("openA"))
def vB(G): return sum(1 for r in G if r.get("openB"))

# A-local trajectory: admits r1 (resolves nothing, neutral), all delta vA <= 0
GA = []
trajA = [dict(id="a1"), dict(id="a2")]          # no openA flags: vA stays 0
# B-local trajectory: B admits receipts that carry A-obligations (legal under B: vB unchanged)
trajB = [dict(id="b1", openA=True), dict(id="b2", openA=True)]

ok_A_local = all(vA(GA + trajA[:i+1]) <= vA(GA + trajA[:i]) for i in range(len(trajA)))
ok_B_local = all(vB(trajB[:i+1]) <= vB(trajB[:i]) for i in range(len(trajB)))

# Mesh join: interleave both admission streams into one graph
G = []
hist = []
for r in [trajA[0], trajB[0], trajA[1], trajB[1]]:
    G = G + [r]
    hist.append(vA(G))

print("A-local descent holds:", ok_A_local)
print("B-local descent holds (under V_B):", ok_B_local)
print("V_A along joined trajectory:", hist)
print("global descent of V_A after join:", all(hist[i+1] <= hist[i] for i in range(len(hist)-1)))
