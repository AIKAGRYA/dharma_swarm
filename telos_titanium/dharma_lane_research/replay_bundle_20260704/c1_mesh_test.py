"""C1 lens test: computable predicates + behavior difference for
'mesh convergence + local election' vs 'consensus'.

P1: CRDT join (G-set union) is ACI -> convergence on SET is a computable,
    testable property (order/duplication insensitive).
P2: local election = deterministic choice fn over the set.
    (a) same delivered set => same choice (confluence of election)
    (b) IRREVOCABILITY FAILS: election flips on late arrival.
        Consensus (FLP sense) requires decided-once-stays-decided.
        => the mechanism computably FAILS the consensus decision predicate.
P3: adoption = frontier overlap over declared covers: computable statistic;
    disjoint covers => permanent zero overlap (balkanization observable,
    not an error state). SCP-slice analogy.
"""
import hashlib, itertools, random

random.seed(7)

def h(x):
    return hashlib.sha256(x.encode()).hexdigest()

# ---------- P1: join is ACI on random small instances ----------
def join(a, b):
    return a | b

U = [frozenset(random.sample(range(20), random.randint(0, 6))) for _ in range(30)]
assoc = all(join(join(a, b), c) == join(a, join(b, c))
            for a, b, c in itertools.product(U[:8], repeat=3))
comm = all(join(a, b) == join(b, a) for a, b in itertools.product(U[:12], repeat=2))
idem = all(join(a, a) == a for a in U)
print("P1 join ACI (assoc,comm,idem):", assoc, comm, idem)

# order-insensitivity: any delivery order of same multiset of updates -> same state
ops = [frozenset({i}) for i in range(8)]
states = set()
for perm in itertools.permutations(ops, 5):
    s = frozenset()
    for o in perm:
        s = join(s, o)
    # only permutations of the same 5 ops should agree; test one fixed combo
combo = ops[:5]
states = {frozenset().union(*perm) for perm in itertools.permutations(combo)}
print("P1 order-insensitive convergence (1 state from all orders):", len(states) == 1)

# ---------- P2: local election ----------
def elect(proposals, trust_base):
    """deterministic: argmax of keyed hash among proposals visible to trust base"""
    visible = [p for p in proposals if p[0] in trust_base]
    if not visible:
        return None
    return max(visible, key=lambda p: h(trust_base_key(trust_base) + p[1]))

def trust_base_key(tb):
    return h(",".join(sorted(tb)))

# proposals: (author, content)
props = {("a", "x1"), ("b", "x2"), ("c", "x3")}
TB = frozenset({"a", "b", "c"})

# (a) confluence: two observers w/ same trust base + same delivered set agree
e1, e2 = elect(props, TB), elect(props, TB)
print("P2a election agreement given identical set+trust:", e1 == e2)

# (b) irrevocability check: does a decided value ever change after more deliveries?
flips = 0
trials = 200
for t in range(trials):
    base = {("a", f"x{t}"), ("b", f"y{t}")}
    first = elect(base, TB)
    late = ("c", f"z{t}")
    after = elect(base | {late}, TB)
    if first != after:
        flips += 1
print(f"P2b irrevocability violations (election flipped on late arrival): {flips}/{trials}")
print("P2b => computable predicate 'decision stability' FAILS: not consensus.")

# consensus decision predicate (safety): once decide(v), forever decide(v).
# local election over a growing join-semilattice provably cannot satisfy it
# without a cut rule (= quorum certificate or burn-cost finality).

# ---------- P3: frontier overlap over declared covers ----------
def frontier(proposals, tb):
    e = elect(proposals, tb)
    return frozenset([e]) if e else frozenset()

def overlap(f1, f2):
    if not f1 and not f2:
        return 1.0
    return len(f1 & f2) / len(f1 | f2)

TB1 = frozenset({"a", "b"})       # cover 1
TB2 = frozenset({"b", "c"})       # cover 2, intersects
TB3 = frozenset({"d", "e"})       # disjoint cover -> balkanized
props2 = {("a", "p"), ("b", "q"), ("c", "r"), ("d", "s"), ("e", "t")}
f1, f2, f3 = frontier(props2, TB1), frontier(props2, TB2), frontier(props2, TB3)
print("P3 overlap(TB1,TB2) computable:", overlap(f1, f2),
      "| overlap(TB1,TB3):", overlap(f1, f3))
print("P3 disjoint covers -> permanent 0 overlap; observable metric, not error.")
