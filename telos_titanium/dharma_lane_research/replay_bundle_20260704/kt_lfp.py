from itertools import chain, combinations

# Receipts with dependency edges; admission: r admitted if all deps admitted (positive/monotone).
receipts = ['g', 'a', 'b', 'c', 'd']
deps = {'g': [], 'a': ['g'], 'b': ['g','a'], 'c': ['b'], 'd': ['x_missing']}

def F(S):
    return frozenset(r for r in receipts if all(d in S for d in deps[r]))

# Monotonicity check over all pairs S subseteq T in powerset
univ = receipts
def powerset(xs):
    return [frozenset(c) for r in range(len(xs)+1) for c in combinations(xs, r)]
P = powerset(univ)
mono = all(F(S) <= F(T) for S in P for T in P if S <= T)
print("positive admission operator monotone:", mono)

# lfp via Kleene iteration from bottom
S = frozenset()
while True:
    S2 = F(S)
    if S2 == S: break
    S = S2
print("lfp =", sorted(S), " (genesis 'g' seeds it; dangling 'd' excluded)")

# Countermodel probe: NEGATIVE clause breaks monotonicity -> K-T inapplicable
conflict = {'a': 'b'}
def G(S):
    return frozenset(r for r in receipts if all(d in S for d in deps[r]) and (conflict.get(r) not in S))
mono2 = all(G(S) <= G(T) for S in P for T in P if S <= T)
print("admission with conflict/negation monotone:", mono2)
