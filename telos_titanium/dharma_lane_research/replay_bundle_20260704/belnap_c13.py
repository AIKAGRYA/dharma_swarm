from itertools import product

# --- Part 1: P({s,c}) with union IS the Belnap knowledge-order half ---
# Belnap A4 knowledge order: N <= T <= B, N <= F <= B, T,F incomparable
K_LE = {('N','N'),('N','T'),('N','F'),('N','B'),('T','T'),('T','B'),('F','F'),('F','B'),('B','B')}
def k_le(a,b): return (a,b) in K_LE
def k_join(a,b):  # oplus / gullibility
    for c in ['N','T','F','B']:
        if k_le(a,c) and k_le(b,c) and all(not (k_le(a,d) and k_le(b,d)) or k_le(c,d) for d in ['N','T','F','B']):
            return c
phi = {frozenset():'N', frozenset({'s'}):'T', frozenset({'c'}):'F', frozenset({'s','c'}):'B'}
subsets = list(phi)
iso_order = all( (a<=b) == k_le(phi[a],phi[b]) for a,b in product(subsets,repeat=2) )
iso_join  = all( phi[a|b] == k_join(phi[a],phi[b]) for a,b in product(subsets,repeat=2) )
print("order-iso P({s,c},subset) = (A4,<=_k):", iso_order)
print("union = oplus (knowledge join):     ", iso_join)

# --- Part 2: spec behavior model — ORMap union of events, derived status ---
# Event = (type, id, ref). Derived per (key,t): support bit, unresolved-challenge bit.
def status(events):
    support = any(e[0]=='evidence_seen' for e in events)
    opened  = {e[1] for e in events if e[0]=='challenge_opened'}
    resolved= {e[2] for e in events if e[0]=='challenge_resolved'}
    unresolved = bool(opened - resolved)
    return frozenset((['s'] if support else []) + (['c'] if unresolved else []))
def canonical(events):  # collapse: boolean, per core.md conjuncts (evidence>=1 AND no unresolved challenge)
    st = status(events); return ('s' in st) and ('c' not in st)

r1 = {('evidence_seen','e1',None), ('challenge_opened','k1',None)}       # replica 1: 'both'
r2 = {('challenge_resolved','res1','k1')}                                 # replica 2 saw the resolution
print("\nreplica1 status:", set(status(r1)), "canonical?", canonical(r1))
merged = r1 | r2   # ORMap join = union; NO new evidence event
print("after union w/ resolution (no re-proof): status:", set(status(merged)), "canonical?", canonical(merged))

# --- Part 3: countermodel for Belnap4-as-primitive-CRDT-merged value ---
# If 'both' were a primitive value merged by oplus, resolution could never lower it:
b_after = k_join('B', status_val := phi[status(r2)])  # merge B with replica2's local view
print("\nprimitive-Belnap merge: B oplus", status_val, "=", b_after, "-> canonical stays", b_after=='T')
# oplus is monotone: nothing joins with B to give T. Verify absorbing:
print("B absorbing under oplus:", all(k_join('B',x)=='B' for x in ['N','T','F','B']))

# --- Part 4: Status_o is NOT a semilattice homomorphism (must be derived read-model) ---
hom = status(r1|r2) == frozenset(set(status(r1))|set(status(r2))) and True
lhs, rhs = phi[status(r1|r2)], k_join(phi[status(r1)],phi[status(r2)])
print("\nStatus_o(join(a,b)) =", lhs, " vs oplus of parts =", rhs, "-> homomorphism?", lhs==rhs)
