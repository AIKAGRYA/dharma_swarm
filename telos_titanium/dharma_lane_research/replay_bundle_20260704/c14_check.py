"""C14 math check: mesh join algebra + density-matrix dichotomy.

Model per witness_mesh.md:
  MeshState = ORMap[AuthorityKey, EventSet]  (event ids content-addressed)
  join = per-key union of event-id sets; resolution indexes are DERIVED
  projections recomputed from the merged event set (not from arrival order).
"""
import itertools, random, cmath

random.seed(7)

# ---------- Part 1: join-semilattice laws on the declared carrier ----------
def join(a, b):
    keys = set(a) | set(b)
    return {k: frozenset(a.get(k, frozenset()) | b.get(k, frozenset())) for k in keys}

def rand_state(nkeys=3, nev=5):
    return {f"k{i}": frozenset(random.sample(range(100), random.randint(0, nev)))
            for i in random.sample(range(nkeys + 2), nkeys)}

comm = assoc = idem = True
for _ in range(2000):
    a, b, c = rand_state(), rand_state(), rand_state()
    comm &= join(a, b) == join(b, a)
    assoc &= join(join(a, b), c) == join(a, join(b, c))
    idem &= join(a, a) == a
print("join commutative:", comm, "| associative:", assoc, "| idempotent:", idem)
print("=> 'commutator' [a,b] := join(a,b) vs join(b,a) diff is identically empty:",
      all(join(a, b) == join(b, a) for a, b in
          [(rand_state(), rand_state()) for _ in range(500)]))

# ---------- Part 2: canonicality is order-independent (add-wins challenge) ----------
# Derived projection: canonical iff evidence present AND no unresolved challenge.
# challenge_resolved counts only if it names a prior challenge_opened id (validity
# checked over the MERGED SET, not arrival order).
def canonical(event_set):
    ev = {e for e in event_set if e[0] == "evidence_seen"}
    opened = {e[1] for e in event_set if e[0] == "challenge_opened"}
    resolved = {e[1] for e in event_set if e[0] == "challenge_resolved" and
                e[1] in opened}  # valid only when it names prior challenge
    unresolved = opened - resolved
    return bool(ev) and not unresolved

events = [("evidence_seen", "ev1"), ("challenge_opened", "ch1"),
          ("challenge_resolved", "ch1"), ("evidence_seen", "ev2"),
          ("challenge_opened", "ch2")]
results = set()
for perm in itertools.permutations(events):
    s = frozenset()
    for e in perm:  # deliver in every possible order, one at a time
        s = s | {e}
    results.add(canonical(s))
print("canonicality over all", len(list(itertools.permutations(events))),
      "delivery orders -> single result:", results)
# add-wins: unresolved ch2 blocks despite evidence, in every order.

# ---------- Part 3: density-matrix dichotomy ----------
# Any rule that consumes only diag(rho) (probabilities) cannot distinguish
# rho from its dephasing Delta(rho). So: either rho is diagonal (= classical
# distribution) or off-diagonal phases exist but are operationally invisible.
def rand_rho(n=3):
    import random as r
    M = [[complex(r.gauss(0, 1), r.gauss(0, 1)) for _ in range(n)] for _ in range(n)]
    # rho = M M† / tr
    rho = [[sum(M[i][k] * M[j][k].conjugate() for k in range(n)) for j in range(n)]
           for i in range(n)]
    tr = sum(rho[i][i].real for i in range(n))
    return [[rho[i][j] / tr for j in range(n)] for i in range(n)]

def dephase(rho):
    n = len(rho)
    return [[rho[i][j] if i == j else 0 for j in range(n)] for i in range(n)]

ok = True
for _ in range(200):
    rho = rand_rho()
    d = dephase(rho)
    # every "spec-consumable" observable = diagonal probabilities
    probs_rho = [rho[i][i].real for i in range(3)]
    probs_d = [d[i][i].real for i in range(3)]
    ok &= all(abs(x - y) < 1e-12 for x, y in zip(probs_rho, probs_d))
    # and diag(rho) is a classical distribution:
    ok &= abs(sum(probs_rho) - 1) < 1e-9 and all(p >= -1e-12 for p in probs_rho)
print("diagonal-only rules cannot see phases; diag(rho) is a classical distribution:", ok)
print("off-diagonal mass exists but is unconsumed (decoration):",
      any(abs(rand_rho()[0][1]) > 1e-6 for _ in range(20)))
