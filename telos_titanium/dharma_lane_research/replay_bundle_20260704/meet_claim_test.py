import itertools, random
random.seed(0)

print("=== R1: idempotence blocks error compounding ===")
# Lattice: Proven=3 > Tested=2 > Attested=1 > Assumed=0; meet = min
grades = [2]*100  # 100 Tested links
from functools import reduce
print("meet over 100 Tested links:", reduce(min, grades), "(same as 1 link: 2)")
# Semantics: Tested => reliability lower bound 0.95 per link (independent errors)
print("true composite reliability floor 0.95^100 =", 0.95**100)
print("=> any idempotent op is chain-length-invariant; sound grade must degrade.")
# non-idempotent ordered-monoid tensor ([0,1], *, <=): check monoid laws + monotonicity
ok_assoc = ok_mono = True
for _ in range(2000):
    a,b,c,a2,b2 = [random.random() for _ in range(5)]
    if abs((a*b)*c - a*(b*c)) > 1e-12: ok_assoc=False
    if a<=a2 and b<=b2 and not (a*b <= a2*b2 + 1e-15): ok_mono=False
print("tensor assoc:", ok_assoc, "| monotone:", ok_mono, "| idempotent? 0.5*0.5=", 0.5*0.5)

print("\n=== R2: meet unsound as inference rule (Tested countermodel) ===")
f = lambda x: x + 10            # tested on 0..9: spec f(x)=x+10  -> passes
g = lambda x: x*2 if x < 10 else -1   # tested on 0..9: spec g(x)=2x -> passes
f_pass = all(f(x) == x+10 for x in range(10))
g_pass = all(g(x) == 2*x   for x in range(10))
comp_pass = all(g(f(x)) == 2*(x+10) for x in range(10))  # composite spec on same domain
print("f Tested:", f_pass, "| g Tested:", g_pass, "| g∘f correct on tested domain:", comp_pass)
print("=> Tested(f) & Tested(g) with meet gives Tested(g∘f): FALSE conclusion. Witness (post_f => pre_g) needed; here post_f=[10,19] outside pre_g=[0,9].")

print("\n=== R4: WCET non-compositional (timing-anomaly toy, Lundqvist-Stenström style) ===")
# 2 units U,V. I1 load (hit=2/miss=4). I2 dep I1, unit U, dur 10.
# I3 indep, ready t=3, unit U, dur 2. I4 dep I3, unit V, dur 10.
# Greedy first-come arbitration on U.
def sim(i1_lat):
    t_i1 = i1_lat
    ready_i2, ready_i3 = t_i1, 3
    if ready_i2 <= ready_i3:   # I2 grabs U first
        s2 = ready_i2; e2 = s2+10
        s3 = max(ready_i3, e2); e3 = s3+2
    else:                      # I3 grabs U first
        s3 = ready_i3; e3 = s3+2
        s2 = max(ready_i2, e3); e2 = s2+10
    e4 = e3 + 10               # I4 on V after I3
    return max(e2, e4)
hit, miss = sim(2), sim(4)
print("total time | cache HIT (local best):", hit, "| cache MISS (local worst):", miss)
print("anomaly (hit worse than miss):", hit > miss)
print("=> composing per-instruction WORST cases gives", miss, "but true WCET is", hit,
      "- local-worst composition UNDERESTIMATES. No meet/tensor of component grades is sound; needs Assumed+obligation.")

print("\n=== Ceiling check: meet = glb, downward coercion sound in reliability model ===")
# grade r means 'reliability >= r'; composite from parts alone can never exceed min part bound
for _ in range(2000):
    a,b = random.random(), random.random()
    assert min(a,b) <= a and min(a,b) <= b
    r, r2 = sorted([random.random(), random.random()])
    # coercion: reliability>=r2 implies reliability>=r for r<=r2 : trivially sound
print("meet is glb; weakening (coerce down) sound: OK")
