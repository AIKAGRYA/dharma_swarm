"""Concrete counterexample check against the lemma:
   'liveness properties have no finite witnesses (Alpern-Schneider 1985)'.

Model: infinite traces over alphabet {0,1} (1 = state satisfies P),
represented as ultimately-periodic lassos (u, v) = u . v^omega, |u|,|v| <= K.
Lasso semantics (sound & complete for omega-regular props on UP traces):
  F P  (eventually P)        holds iff '1' in u+v
  G F P (infinitely often P) holds iff '1' in v

Definitions (Alpern & Schneider, 'Defining Liveness', IPL 21(4), 1985):
  liveness(prop): every finite word w extends to some infinite trace in prop
  good prefix (finite POSITIVE witness): finite w s.t. ALL extensions satisfy prop
  bad prefix  (finite refuter):          finite w s.t. ALL extensions violate prop
"""
from itertools import product

K = 4
def words(maxlen, minlen=0):
    for n in range(minlen, maxlen + 1):
        yield from (''.join(t) for t in product('01', repeat=n))

def FP(u, v):  return '1' in (u + v)
def GFP(u, v): return '1' in v

def exists_ext(w, prop, want):
    return any(prop(w + u, v) == want
               for u in words(K) for v in words(K, minlen=1))

finite_words = list(words(K))

# 1. F P is LIVENESS: every finite word has a satisfying extension
live_FP = all(exists_ext(w, FP, True) for w in finite_words)

# 2. F P HAS a finite positive witness: the run of
#    program: n=0; while True: n+=1; if n==5: print(P)
#    prefix w = '00001' -> check NO extension violates F P
w = '00001'
good_prefix_FP = not exists_ext(w, FP, False)

# 3. G F P is liveness too...
live_GFP = all(exists_ext(w2, GFP, True) for w2 in finite_words)
# ...but has NO good prefix (no finite positive witness)
no_good_prefix_GFP = all(exists_ext(w2, GFP, False) for w2 in finite_words)
# ...and NO bad prefix (no finite refuter) either
no_bad_prefix_GFP = all(exists_ext(w2, GFP, True) for w2 in finite_words)

print(f"F P   is liveness (Alpern-Schneider def):        {live_FP}")
print(f"F P   has finite positive witness '00001':       {good_prefix_FP}")
print(f"G F P is liveness:                               {live_GFP}")
print(f"G F P has NO finite positive witness (<= {K}):     {no_good_prefix_GFP}")
print(f"G F P has NO finite refuter (<= {K}):              {no_bad_prefix_GFP}")
print()
if live_FP and good_prefix_FP:
    print("COUNTEREXAMPLE STANDS: 'eventually P' is a liveness property")
    print("WITH a finite witness -> blanket lemma as stated is FALSE.")
    print("Correct boundary: finite positive witnessability = co-safety/open sets,")
    print("not 'non-liveness'. True unwitnessable case = G F P (neither open nor closed).")
