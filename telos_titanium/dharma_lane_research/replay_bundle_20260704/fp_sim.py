import random, math
# Part 1: P(random function on [N] has a fixed point) -> 1-1/e
for N in (256, 4096, 65536):
    trials = 20000
    hits = 0
    for _ in range(trials):
        # count fixed points without building full function: each f(x)==x w.p. 1/N independently
        # simulate directly for rigor on small N
        if any(random.randrange(N) == x for x in range(N)):
            hits += 1
    print(f"N={N}: P(>=1 fp) = {hits/trials:.4f}  (1-1/e = {1-1/math.e:.4f})")

# Part 2: E[position of first fixed point | >=1 exists], random search order, as fraction of N
N = 4096
trials = 30000
tot, cnt = 0, 0
for _ in range(trials):
    fps = [x for x in range(N) if random.randrange(N) == x]
    if fps:
        order = random.sample(range(N), N)
        pos = min(order.index(x) for x in fps) + 1
        tot += pos; cnt += 1
frac = (tot/cnt)/N
print(f"E[first-hit | exists] = {frac:.4f} * N   (theory (e-2)/(e-1) = {(math.e-2)/(math.e-1):.4f})")
print(f"=> at N=2^256: 2^{256+math.log2(frac):.2f}  (claim: ~2^255)")

# Part 3: analytic check of Poisson(1) conditional expectation E[1/(k+1)|k>=1] = (e-2)/(e-1)
s = sum((1/(k+1))*math.exp(-1)/math.factorial(k) for k in range(1,60))/(1-1/math.e)
print(f"analytic E[1/(k+1)|k>=1] = {s:.6f}")
