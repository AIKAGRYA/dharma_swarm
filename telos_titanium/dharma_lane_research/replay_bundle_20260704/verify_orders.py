import itertools

# Kinds: 0=Proven, 1=Tested, 2=Witnessed, 3=Attested
names = ["Proven", "Tested", "Witnessed", "Attested"]
n = 4
# Rows from core.md admissibility matrix (canonical modalities per claim strength, kind-level):
rows = {
    "deductive":     {0},        # Proven_by only
    "empirical":     {1, 2},     # thresholded Tested_by, replayable Witnessed_by
    "differential":  {1, 0},     # thresholded differential Tested_by, Proven_by
    "observational": {2},        # replayable Witnessed_by
    "attested":      {3},        # Attested_by
}

pairs = [(i, j) for i in range(n) for j in range(n) if i != j]
posets = []
for bits in range(1 << len(pairs)):
    rel = set((i, i) for i in range(n))
    for k, (i, j) in enumerate(pairs):
        if bits >> k & 1:
            rel.add((i, j))
    ok = all(not (i != j and (j, i) in rel) for (i, j) in rel)
    if ok:
        ok = all((a, d) in rel for (a, b) in rel for (c, d) in rel if b == c)
    if ok:
        posets.append(rel)
print(f"total posets: {len(posets)}")

def is_upset(S, rel):
    return all(y in S for x in S for y in range(n) if (x, y) in rel)

upset_ok = [rel for rel in posets if all(is_upset(S, rel) for S in rows.values())]
discrete = set((i, i) for i in range(n))
print(f"posets making ALL rows up-sets: {len(upset_ok)}")
for rel in upset_ok:
    print("  ->", "DISCRETE" if rel == discrete else sorted((names[a], names[b]) for (a, b) in rel if a != b))

# total orders reproducing rows as up-sets
totals = [rel for rel in posets if all((i, j) in rel or (j, i) in rel for i in range(n) for j in range(n))]
tot_ok = [rel for rel in totals if all(is_upset(S, rel) for S in rows.values())]
print(f"total orders: {len(totals)}; total orders reproducing rows: {len(tot_ok)}")

# threshold models: exists poset + per-row threshold t_r with canonical set == {m : m >= t_r}
count_threshold = 0
for rel in posets:
    ok = True
    for S in rows.values():
        if not any({m for m in range(n) if (t, m) in rel} == S for t in range(n)):
            ok = False
            break
    if ok:
        count_threshold += 1
print(f"posets admitting a threshold model for ALL rows: {count_threshold}")
