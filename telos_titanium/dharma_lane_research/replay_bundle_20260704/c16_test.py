"""C16 operational test: mesh convergence vs consensus vs local election.

Model: witness_mesh.md merge state = ORMap[AuthorityKey, EventSet],
join = union by event id (join-semilattice). Observer canonicality =
predicate indexed by observer trust base (core.md canonical?).
"""
import itertools, random

# --- 1. Mesh convergence: join is a semilattice => order-insensitive SET convergence
def join(a, b):
    out = dict(a)
    for k, v in b.items():
        out[k] = out.get(k, frozenset()) | v
    return out

events = [("k%d" % (i % 4), "e%d" % i) for i in range(12)]
def deliver(order):
    st = {}
    for k, e in order:
        st = join(st, {k: frozenset([e])})
    return st

orders = [random.sample(events, len(events)) for _ in range(50)]
states = [deliver(o) for o in orders]
convergence = all(s == states[0] for s in states)
print("1. CRDT convergence on SET (50 random delivery orders, identical state):", convergence)

# semilattice laws (computable predicate for 'mesh convergence')
a, b, c = states[0], deliver(orders[1][:6]), deliver(orders[2][:3])
laws = (join(a, a) == a and join(a, b) == join(b, a)
        and join(join(a, b), c) == join(a, join(b, c)))
print("   join idempotent/commutative/associative:", laws)

# --- 2. Same converged state, plural trust bases => plural canonical picks (local election)
# Two proposed extensions of the language, both fully witnessed in the mesh.
proposals = {"ext_A": {"witnessed_by": {"tb1", "tb2"}},
             "ext_B": {"witnessed_by": {"tb2", "tb3"}}}
def canonical_for(observer_tb, mesh):
    # core.md: authority_matches requires evidence trust base == current.trust_base_id
    return {p for p, m in mesh.items() if observer_tb in m["witnessed_by"]}

f1 = canonical_for("tb1", proposals)   # observer under trust base 1
f3 = canonical_for("tb3", proposals)   # observer under trust base 3
print("2. Same converged mesh, observer tb1 canonical set:", sorted(f1),
      "| observer tb3:", sorted(f3), "| single global pick exists:", f1 == f3)

# Any deterministic pick f(converged_state) alone would force the SAME pick on
# every observer -- i.e. an UNINDEXED judgment, which core.md's canonical?
# signature (…, current, t) structurally forbids. Making tb1 and tb3 agree
# anyway = agreement among parties with different admissibility rules =
# consensus, needing quorum/synchrony assumptions the spec's Quorum rule
# explicitly declines. So 'convergence' and 'election' are different
# predicates with different behavior, not synonyms.

# --- 3. Adoption = measured frontier overlap over declared covers (computable)
def jaccard(x, y):
    return len(x & y) / len(x | y) if (x | y) else 1.0
f2 = canonical_for("tb2", proposals)
print("3. Frontier overlap (adoption metric): J(tb1,tb2)=%.2f J(tb1,tb3)=%.2f J(tb2,tb3)=%.2f"
      % (jaccard(f1, f2), jaccard(f1, f3), jaccard(f2, f3)))
print("   balkanization detectable: J(tb1,tb3)=%.2f -> disjoint frontiers measurable" % jaccard(f1, f3))
