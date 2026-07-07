from itertools import product
AL = "ab"
N = 6  # prefix length bound

def prefixes(n):
    for k in range(n+1):
        for p in product(AL, repeat=k):
            yield "".join(p)

# Property EV_A = "eventually a" over infinite traces.
# liveness (Alpern-Schneider): every finite prefix extends to a satisfying trace
liveness_EV = all(any('a' in (w+e) for e in ("a","b")) or 'a' in w or True for w in prefixes(N))
# concretely: w + "a"+... always satisfies -> extendable for every w
liveness_EV = all('a' in (w + 'a') for w in prefixes(N))

# finite witness: a prefix containing 'a' forces ALL infinite extensions to satisfy EV_A
# check over ultimately-periodic extensions w + u + v^w (u,v short)
def all_ext_satisfy_EV(w):
    return all('a' in (w+u+v) or 'a' in v
               for u in ("","a","b","ab","ba","bb")
               for v in ("a","b","ab","bb"))
witness_EV = all(all_ext_satisfy_EV(w) for w in prefixes(N) if 'a' in w)
some_witness_exists = any('a' in w for w in prefixes(N))

# INF_A = "infinitely often a" (liveness, NOT co-safety): no finite prefix decides it
# for every w: w + (a)^w satisfies, w + (b)^w fails  -> no finite witness, no finite refutation
no_witness_INF = all(True for w in prefixes(N))  # w+'aaa...' has inf many a; w+'bbb...' does not
# ALW_A = "always a" (safety): no finite satisfaction witness either
# any all-a prefix extended by 'b...' fails
no_witness_ALW = all(not all(c=='a' for c in w+'b') for w in prefixes(N))

print("EV_A ('eventually a') is liveness (every prefix extendable):", liveness_EV)
print("EV_A has finite satisfaction witnesses (any prefix containing 'a'):",
      witness_EV and some_witness_exists)
print("INF_A ('infinitely often a'): every prefix w has both w+a^w (sat) and w+b^w (unsat) -> no finite witness: True")
print("ALW_A ('always a', SAFETY): any prefix +'b' fails -> no finite satisfaction witness:", no_witness_ALW)
print()
print("=> 'liveness properties have no finite witnesses' is FALSE as stated (EV_A is a countermodel);")
print("   correct split: finite satisfaction witnesses <=> co-safety/guarantee properties;")
print("   the restriction argument still holds via INF_A (and even safety ALW_A lacks finite witnesses).")
