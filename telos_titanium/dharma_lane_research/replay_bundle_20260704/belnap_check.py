from itertools import product

# Belnap-4 encoded as pairs (p, n): p = told-true bit, n = told-false bit
# Neither=(0,0)  True=(1,0)  False=(0,1)  Both=(1,1)   -- standard P({t,f}) encoding
V = [(p,n) for p in (0,1) for n in (0,1)]
name = {(0,0):'N',(1,0):'T',(0,1):'F',(1,1):'B'}

# knowledge order: componentwise <=
le_k = lambda a,b: a[0]<=b[0] and a[1]<=b[1]
# truth order: p increases, n decreases
le_t = lambda a,b: a[0]<=b[0] and a[1]>=b[1]

# bilattice ops (Fitting/Ginsberg standard)
k_join = lambda a,b: (a[0]|b[0], a[1]|b[1])   # oplus (gullibility)
k_meet = lambda a,b: (a[0]&b[0], a[1]&b[1])   # otimes (consensus)
t_join = lambda a,b: (a[0]|b[0], a[1]&b[1])   # or
t_meet = lambda a,b: (a[0]&b[0], a[1]|b[1])   # and
neg    = lambda a: (a[1],a[0])

# 1) iso to P({support,challenge}): subsets under inclusion, union = k_join
def to_set(a): return frozenset((['s'] if a[0] else [])+(['c'] if a[1] else []))
assert all(le_k(a,b) == (to_set(a)<=to_set(b)) for a in V for b in V), "knowledge order != inclusion"
assert all(to_set(k_join(a,b)) == to_set(a)|to_set(b) for a in V for b in V), "oplus != union"
assert all(to_set(k_meet(a,b)) == to_set(a)&to_set(b) for a in V for b in V), "otimes != intersection"
print("ISO OK: (Belnap4, <=k, oplus, otimes) ~= (P({s,c}), subset, union, intersection)")

# 2) truth ops & negation are NOT plain set ops: they mix components
bad_or  = [ (a,b) for a in V for b in V if to_set(t_join(a,b)) == to_set(a)|to_set(b) ]
mismatch = [(name[a],name[b]) for a in V for b in V if to_set(t_join(a,b)) != to_set(a)|to_set(b)]
print("truth-join != union on pairs:", mismatch)
assert all(neg(a)!=a or a in [(0,0),(1,1)] for a in V)
print("negation fixes exactly N and B:", [name[a] for a in V if neg(a)==a])

# 3) interlacing laws HOLD in the algebra (they exist; spec just never uses them)
def monotone(op, le):
    return all(not(le(a,a2) and le(b,b2)) or le(op(a,b),op(a2,b2))
               for a in V for a2 in V for b in V for b2 in V)
print("interlacing: and,or monotone in <=k:", monotone(t_meet,le_k), monotone(t_join,le_k))
print("interlacing: otimes,oplus monotone in <=t:", monotone(k_meet,le_t), monotone(k_join,le_t))

# 4) canonical? as spec'd = boolean collapse: support present AND no unresolved challenge
canonical = lambda a: a==(1,0)
print("canonical? partitions:", {name[a]: canonical(a) for a in V})

# 5) EVENT-SET model of the mesh (witness_mesh.md): per authority key,
# events = {evidence_seen e, challenge_opened c, challenge_resolved r(c)}
# derived status(S) = (has admissible evidence, has unresolved challenge)
def status(S):
    return (1 if 'e' in S else 0, 1 if ('c' in S and 'r' not in S) else 0)
# restoration-without-re-proof: add resolution event, canonical flips back, evidence NOT re-proven
S1 = {'e'}            # canonical
S2 = {'e','c'}        # Both -> blocked
S3 = {'e','c','r'}    # resolved -> canonical again, same evidence event
print("trajectory:", [ (sorted(s), name[status(s)], canonical(status(s))) for s in (S1,S2,S3) ])
# 6) COUNTERMODEL CHECK on 'free in the ORMap union': status is NOT a lattice hom
# (union of sets can DECREASE knowledge-order status) -- this is exactly the honest remainder
A={'e','c'}; B={'r'}
print("status(A)=",name[status(A)], " status(A|B)=",name[status(A|B)],
      " k-descent under union:", not le_k(status(A), status(A|B)) or status(A)!=k_join(status(A),status(B)))
print("hom fails:", status(A|B) != k_join(status(A),status(B)))
