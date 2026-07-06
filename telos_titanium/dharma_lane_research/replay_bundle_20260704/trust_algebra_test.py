import itertools, math, random
from fractions import Fraction

print("=== TEST 1: meet-only inexpressibility of amplification ===")
# Any term built from binary meet over variables x1..xn in a meet-semilattice
# equals the meet of a nonempty subset of the variables (idempotent, assoc, comm).
# Hence value <= min over that subset <= max over all inputs. Amplification
# (output > max input, or even > min) is inexpressible. Verify exhaustively on
# chain lattice {0,.25,.5,.75,1} for all meet-terms over 3 vars.
vals = [0, .25, .5, .75, 1]
ok = True
for assignment in itertools.product(vals, repeat=3):
    for subset in itertools.chain.from_iterable(itertools.combinations(range(3), r) for r in (1,2,3)):
        term = min(assignment[i] for i in subset)
        if term > min(assignment[i] for i in subset):  # tautology, but check vs inputs
            ok = False
        if term > max(assignment):
            ok = False
print("no meet-term ever exceeds max input:", ok)

print()
print("=== TEST 2: countermodel to 'correlated evidence composes by MEET' ===")
# Bayesian model: claim C, prior 0.5. Lane A: reports true state of C with
# reliability a=0.9. Lane B: deterministic (lossy) copy of A's REPORT with
# flip prob 0.25 (so B alone is a weaker channel). B is conditionally
# independent of C GIVEN A's report => fully correlated with A w.r.t. C.
prior = Fraction(1,2); a = Fraction(9,10); bflip = Fraction(1,4)
# P(C | A=yes)
pA = (a*prior) / (a*prior + (1-a)*(1-prior))
# B alone: P(B=yes|C) = a(1-bflip) + (1-a)bflip ; channel reliability of B
pB_given_C   = a*(1-bflip) + (1-a)*bflip
pB_given_nC  = (1-a)*(1-bflip) + a*bflip
pB = (pB_given_C*prior) / (pB_given_C*prior + pB_given_nC*(1-prior))
# Both A=yes and B=yes: since B depends only on A's report,
# P(C | A=yes, B=yes) = P(C | A=yes)  (B adds nothing beyond A)
pAB = pA
print(f"P(C|A) = {float(pA):.4f}   P(C|B) = {float(pB):.4f}")
print(f"P(C|A,B) = {float(pAB):.4f}  (Bayes-correct combination)")
print(f"meet(min) = {float(min(pA,pB)):.4f}   join(max) = {float(max(pA,pB)):.4f}")
print("=> 'correlated composes by meet' UNDERSHOOTS correct value by",
      f"{float(pAB - min(pA,pB)):.4f}; correct = JOIN (best representative).")
print("Meet rule means admitting a weaker correlated duplicate LOWERS trust ->",
      "violates evidence monotonicity; incentivizes evidence suppression.")

print()
print("=== TEST 3: amplification is CONDITIONAL (Condorcet inversion) ===")
def maj_correct(p, n):
    k0 = n//2 + 1
    return sum(math.comb(n,k)*p**k*(1-p)**(n-k) for k in range(k0, n+1))
for p in (0.7, 0.55, 0.5, 0.4):
    print(f"p={p}: individual={p:.3f}  majority-of-10 correct={maj_correct(p,10):.4f}")
print("=> independence AMPLIFIES ERROR when per-lane competence p<1/2;")
print("   'decorrelated => amplification' needs condition p>1/2 (LR>1).")

print()
print("=== TEST 4: Krogh & Vedelsby 1995 ambiguity decomposition, exact check ===")
# E_ens = Ebar - Abar for weighted-average ensembles, squared error.
random.seed(7)
for trial in range(3):
    n = 6
    w = [random.random() for _ in range(n)]; s=sum(w); w=[x/s for x in w]
    f = [random.uniform(-2,2) for _ in range(n)]  # member predictions
    y = random.uniform(-2,2)                      # target
    fbar = sum(wi*fi for wi,fi in zip(w,f))
    E_ens = (fbar - y)**2
    Ebar  = sum(wi*(fi-y)**2 for wi,fi in zip(w,f))
    Abar  = sum(wi*(fi-fbar)**2 for wi,fi in zip(w,f))
    print(f"trial {trial}: E_ens={E_ens:.6f}  Ebar-Abar={Ebar-Abar:.6f}  match={abs(E_ens-(Ebar-Abar))<1e-12}")
print("=> ensemble error = avg error - diversity: exceeds AVERAGE member, ")
print("   (not guaranteed to exceed BEST member); citation attribution correct.")

print()
print("=== TEST 5: a consistent amplification operator EXISTS (positive part) ===")
# log-odds / independent-likelihood-ratio fusion on (0,1): assoc, comm, monotone,
# exceeds join when both inputs > 1/2. Verify algebraic laws numerically.
def amp(x,y):
    ox, oy = x/(1-x), y/(1-y)
    o = ox*oy
    return o/(1+o)
random.seed(1); laws_ok = True
for _ in range(20000):
    x,y,z = (random.uniform(0.01,0.99) for _ in range(3))
    if abs(amp(amp(x,y),z) - amp(x,amp(y,z))) > 1e-9: laws_ok=False
    if abs(amp(x,y)-amp(y,x)) > 1e-12: laws_ok=False
    if x>0.5 and y>0.5 and not amp(x,y) > max(x,y): laws_ok=False
    if x<0.5 and y<0.5 and not amp(x,y) < min(x,y): laws_ok=False
print("assoc/comm/amplifies-above-join iff both>1/2, degrades if both<1/2:", laws_ok)
