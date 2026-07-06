import itertools, math
from math import comb

print("=== 1. Meet-only inexpressibility of amplification ===")
# Trust values in [0,1], meet = min (totally ordered chain lattice).
# Enumerate ALL terms buildable from inputs with meet only (any nesting/repetition).
# Claim: sup over all meet-terms = min(inputs) <= max(inputs); amplification (> max) inexpressible.
inputs = [0.8, 0.8, 0.7]
def all_meet_terms(vals, depth=3):
    terms = set(vals)
    for _ in range(depth):
        terms |= {min(a,b) for a in terms for b in terms}
    return terms
T = all_meet_terms(inputs)
print("inputs:", inputs, "| max meet-term value:", max(T), "| can exceed max input?", max(T) > max(inputs))

print("\n=== 2. Independent (decorrelated) fusion exceeds meet AND join ===")
p = 0.8  # each attestor accuracy, prior 0.5
post2 = p*p / (p*p + (1-p)*(1-p))
print(f"two independent p={p} attestors agree -> posterior {post2:.4f}  (> join {p})")
# Condorcet, N=10, p=0.7, majority (>=6), ties broken 50/50
N, q = 10, 0.7
maj = sum(comb(N,k)*q**k*(1-q)**(N-k) for k in range(6, N+1)) + 0.5*comb(N,5)*q**5*(1-q)**5
print(f"Condorcet N={N} p={q} independent majority accuracy: {maj:.4f} (> {q})")

print("\n=== 3. Countermodel: 'correlated evidence composes by MEET' violates evidence monotonicity ===")
# Two FULLY correlated attestations of same claim, trust 0.9 and 0.6.
# Discarding the weaker source leaves a single 0.9 attestation. Any sound parallel
# composition must be >= what you get by ignoring evidence.
t1, t2 = 0.9, 0.6
print(f"sources (fully correlated): {t1}, {t2}")
print(f"  meet  -> {min(t1,t2)}   (LESS than discarding the 0.6 source entirely -> {t1})  UNSOUND")
print(f"  join  -> {max(t1,t2)}   (idempotent, no double count)  sound floor")

print("\n=== 4. Nominal-tag amplification overclaims under residual correlation ===")
# Common-cause model: with prob rho, all N attestors copy one latent source (acc p);
# with prob 1-rho they vote independently. Tags say 'disjoint family' either way.
def maj_acc(N, p, rho):
    ind = sum(comb(N,k)*p**k*(1-p)**(N-k) for k in range(N//2+1, N+1))
    if N % 2 == 0:
        ind += 0.5*comb(N,N//2)*p**(N//2)*(1-p)**(N//2)
    return rho*p + (1-rho)*ind
for rho in (0.0, 0.3, 0.6, 1.0):
    print(f"  N=10 p=0.7 rho={rho}: true accuracy {maj_acc(10,0.7,rho):.4f}  (tag-licensed claim: {maj_acc(10,0.7,0.0):.4f})")

print("\n=== 5. C1: computable predicate + behavior difference ===")
def disjoint(ic_a, ic_b):  # independence_class = (method_lineage, model_family, harness)
    return all(x != y for x, y in zip(ic_a, ic_b))
e1 = (("cot","fam_A","harness_1"), 0.8)
e2 = (("cot","fam_A","harness_2"), 0.8)   # shared lineage+family -> correlated branch
e3 = (("tool_verified","fam_B","harness_3"), 0.8)
def compose(a, b):
    if disjoint(a[0], b[0]):
        pa, pb = a[1], b[1]
        return pa*pb / (pa*pb + (1-pa)*(1-pb))  # amplify
    return max(a[1], b[1])  # correlated: join (idempotent)
print(f"e1+e2 (shared class):   {compose(e1,e2):.4f}  <- no amplification")
print(f"e1+e3 (disjoint class): {compose(e1,e3):.4f}  <- amplified past join")
