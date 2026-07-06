import random

# Model: G-Set CRDT of proposals, join = union (join-semilattice).
# Check 1: convergence under arbitrary delivery orders/duplication (ACI laws).
random.seed(7)
U = list(range(8))
for trial in range(2000):
    deltas = [frozenset(random.sample(U, random.randint(0, 4))) for _ in range(5)]
    o1 = deltas[:]; random.shuffle(o1); o1 += random.sample(deltas, 2)
    o2 = deltas[:]; random.shuffle(o2); o2 += random.sample(deltas, 3)
    s1 = frozenset().union(*o1); s2 = frozenset().union(*o2)
    assert s1 == s2
print("Check 1 PASS: union-join converges regardless of order/duplication (ACI)")

# Check 2: 'local election' = deterministic rank-max over the converged set.
# max is a semilattice homomorphism: max(A U B) = max(max(A), max(B))
# => the elected winner itself converges (max-register CRDT), no consensus protocol,
# but the winner is PROVISIONAL: it can flip when new proposals arrive.
rank = {u: (u * 37) % 23 for u in U}
key = lambda x: (rank[x], x)
flips = 0
for trial in range(2000):
    A = frozenset(random.sample(U, random.randint(1, 5)))
    B = frozenset(random.sample(U, random.randint(1, 5)))
    assert max(A | B, key=key) == max({max(A, key=key), max(B, key=key)}, key=key)
    w = max(A, key=key)
    if any(key(x) > key(w) for x in U if x not in A):
        flips += 1
print("Check 2 PASS: rank-max commutes with join (election converges w/o quorum)")
print(f"Check 2b: winner dethroned by a later proposal in {flips}/2000 cases -> no irrevocable decision; finality would need closure knowledge = consensus (FLP territory)")

# Check 3: plural trust bases => permanent plurality even on the SAME converged set.
S = frozenset(U)
trustA = frozenset(x for x in S if x % 2 == 0)
trustB = frozenset(x for x in S if x % 3 == 0)
wA = max(S & trustA, key=key); wB = max(S & trustB, key=key)
print(f"Check 3: same converged set, different covers -> winners A={wA}, B={wB}, equal={wA == wB}")
print("=> observer-indexed election gives plurality exactly when covers don't share the top-ranked element (SCP quorum-intersection analogue)")
