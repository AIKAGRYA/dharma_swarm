import random, itertools, numpy as np

# --- Part 1: CRDT join per witness_mesh.md ---
# MeshState = ORMap[AuthorityKey, EventSet]; join = union of content-addressed event ids per key.
# Derived projections (canonicality blocking) recomputed from the event set.
random.seed(42)
KEYS = ['k1','k2']
EVENTS = [('claim_seen','c1'),('evidence_seen','e1'),('evidence_seen','e2'),
          ('challenge_opened','ch1'),('challenge_resolved','ch1'),  # resolution names prior challenge
          ('ttl_expired','r1'),('receipt_superseded','r1->r2')]

def rand_state():
    return {k: frozenset(random.sample(EVENTS, random.randint(0,len(EVENTS)))) for k in KEYS}

def join(a,b):
    return {k: a.get(k,frozenset()) | b.get(k,frozenset()) for k in set(a)|set(b)}

def canonical_projection(state, key):
    # derived, recomputed from event set: evidence present AND no unresolved challenge (add-wins block)
    ev = state.get(key, frozenset())
    has_evidence = any(t=='evidence_seen' for t,_ in ev)
    open_ch  = {i for t,i in ev if t=='challenge_opened'}
    resolved = {i for t,i in ev if t=='challenge_resolved'}
    valid_resolved = resolved & open_ch          # valid only when it names a prior challenge IN THE SET
    unresolved = open_ch - valid_resolved
    return has_evidence and not unresolved

fails = 0
for _ in range(20000):
    a,b,c = rand_state(), rand_state(), rand_state()
    if join(a,b) != join(b,a): fails += 1                    # commutative
    if join(a,join(b,c)) != join(join(a,b),c): fails += 1    # associative
    if join(a,a) != a: fails += 1                            # idempotent
    # order-independence of the OBSERVABLE (canonicality projection): any delivery order, same verdict
    events_all = join(join(a,b),c)
    for key in KEYS:
        base = canonical_projection(events_all, key)
        for perm in itertools.permutations([a,b,c]):
            s = {}
            for st in perm: s = join(s, st)
            if canonical_projection(s, key) != base: fails += 1
print("CRDT property failures:", fails, "(0 = commutative-associative-idempotent join; projections order-independent)")

# challenge add-wins vs evidence: concurrent evidence + challenge -> blocked regardless of merge order
a = {'k1': frozenset([('evidence_seen','e1')])}
b = {'k1': frozenset([('challenge_opened','ch1')])}
print("add-wins block (both orders):", not canonical_projection(join(a,b),'k1'), not canonical_projection(join(b,a),'k1'))

# --- Part 2: density-matrix dichotomy ---
# If every available operation/measurement is diagonal in the fixed canonical basis
# (which the commutative merge design guarantees: nothing interferes, nothing rotates the basis),
# then tr(rho E) == tr(diag(rho) E) for all diagonal E: phases carry zero operational meaning.
rng = np.random.default_rng(0)
maxdiff = 0.0
for _ in range(2000):
    d = rng.integers(2,6)
    A = rng.normal(size=(d,d)) + 1j*rng.normal(size=(d,d))
    rho = A @ A.conj().T; rho /= np.trace(rho).real          # random density matrix w/ nonzero phases
    diag = np.diag(np.diag(rho))                              # classical distribution
    for _ in range(5):
        E = np.diag(rng.uniform(0,1,size=d))                  # diagonal POVM element (fixed-basis predicate)
        maxdiff = max(maxdiff, abs((np.trace(rho@E) - np.trace(diag@E)).real))
print("max |tr(rho E) - tr(diag(rho) E)| over diagonal E:", maxdiff)

# Conversely: phases ONLY become observable via a non-diagonal (non-commuting) operation:
rho = np.array([[0.5,0.5],[0.5,0.5]])   # coherent |+><+|
mix = np.array([[0.5,0.0],[0.0,0.5]])   # classical mixture
H = np.array([[1,1],[1,-1]])/np.sqrt(2) # basis-rotating op (what the CRDT design excludes)
Eplus = H @ np.diag([1,0]) @ H
print("coherent vs mixture, diagonal predicate:", np.trace(rho@np.diag([1,0])).real, np.trace(mix@np.diag([1,0])).real)
print("coherent vs mixture, non-commuting op needed to split them:", np.trace(rho@Eplus).real, np.trace(mix@Eplus).real)
