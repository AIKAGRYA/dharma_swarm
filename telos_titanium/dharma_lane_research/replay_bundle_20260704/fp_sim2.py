import random, math
# P(random function on [N] has >=1 fixed point): #fp ~ Binomial(N,1/N) -> Poisson(1)
# exact: 1-(1-1/N)^N
for N in (256, 2**16, 2**32):
    print(f"N=2^{int(math.log2(N))}: exact P(>=1 fp) = {1-(1-1/N)**N:.6f}  (1-1/e = {1-1/math.e:.6f})")

# Monte Carlo with binomial draws (fast, exact model of ROM per-point independence)
trials=200000; N=2**20
hits=sum(1 for _ in range(trials) if any(random.random()<1/N for _ in range(0)) )  # skip slow path
# use numpy-free binomial via poisson approx check with small-N direct sim:
N=512; trials=5000; hits=0
for _ in range(trials):
    k=sum(1 for x in range(N) if random.randrange(N)==x)
    hits+= (k>=1)
print(f"direct sim N=512: {hits/trials:.4f}")

# E[first-hit position | >=1 fp] as fraction of N, random search order
# theory: E[1/(k+1) | k>=1] with k~Poisson(1)  => (e-2)/(e-1)
s = sum((1/(k+1))*math.exp(-1)/math.factorial(k) for k in range(1,80))/(1-1/math.e)
print(f"analytic E[1/(k+1)|k>=1] = {s:.6f} = (e-2)/(e-1) = {(math.e-2)/(math.e-1):.6f}")
print(f"=> conditional expected search at N=2^256: 2^{256+math.log2(s):.2f}  (claim says ~2^255)")
# unconditioned geometric-search-across-templates: E = N = 2^256; same order of magnitude
N=512; trials=4000; tot=0; cnt=0
for _ in range(trials):
    fps=[x for x in range(N) if random.randrange(N)==x]
    if fps:
        order=random.sample(range(N),N)
        tot += min(order.index(x) for x in fps)+1; cnt+=1
print(f"sim E[first-hit|exists]/N = {(tot/cnt)/N:.4f}")
