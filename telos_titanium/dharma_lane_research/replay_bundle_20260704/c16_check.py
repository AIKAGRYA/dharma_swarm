import hashlib, itertools, random
random.seed(16)

# Model: G-Set CRDT of proposals (matches witness_mesh.md MeshState per-key EventSet, join=union)
def join(a, b): return a | b

# 1) ACI laws of join (exhaustive over small universe)
U = [frozenset(s) for s in itertools.chain.from_iterable(
    itertools.combinations(range(4), k) for k in range(5))]
aci = all(join(a,b)==join(b,a) for a in U for b in U) \
  and all(join(a,join(b,c))==join(join(a,b),c) for a in U for b in U for c in U) \
  and all(join(a,a)==a for a in U)
print("ACI (comm/assoc/idem) over 16-elt powerset lattice:", aci)

# 2) SEC: any delivery order/multiplicity of same update set -> same state
updates = [frozenset([i]) for i in range(6)]
states = set()
for trial in range(200):
    perm = random.sample(updates, len(updates)) + random.choices(updates, k=3)
    s = frozenset()
    for u in perm: s = join(s, u)
    states.add(s)
print("SEC: distinct converged states over 200 shuffled/duplicated deliveries:", len(states))

# 3) COUNTERMODEL ATTEMPT: deterministic selection (min-hash 'election') over the
# converged set = consensus without quorums/burn?  Show it fails consensus:
h = lambda x: hashlib.sha256(str(x).encode()).hexdigest()
elect = lambda s: min(s, key=h) if s else None
# (a) Agreement violated at any finite time: replicas with different delivered subsets
r1 = frozenset([frozenset([0]), frozenset([1])])       # replica 1 delivered {p0,p1}
r2 = frozenset([frozenset([0]), frozenset([2])])       # replica 2 delivered {p0,p2}
print("(a) partial-delivery elections equal?", elect(r1)==elect(r2),
      "->", sorted(elect(r1)), "vs", sorted(elect(r2)))
# (b) Irrevocability violated: a straggler proposal flips an already-announced election
s = frozenset([frozenset([1]), frozenset([2])])
before = elect(s)
flipped = False
for new in (frozenset([k]) for k in range(3, 5000)):
    s2 = join(s, frozenset([new]))
    if elect(s2) != before: flipped = True; break
print("(b) later arrival flips the election (no finality):", flipped)
# (c) Closing the set (declaring 'no more proposals count') IS agreeing on a value
# -> reduces to consensus; monotone join can never express set-closure:
# closure predicate is antitone (true->false as set grows), join is inflationary.
grows_break_closure = all(not (s < join(s, frozenset([frozenset([99])]))) == False for s in [r1, r2])
print("(c) join is strictly inflationary on fresh input (closure inexpressible):", grows_break_closure)
