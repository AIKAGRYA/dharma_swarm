import itertools

M = ['P', 'T', 'W', 'A']  # Proven, Tested, Witnessed, Attested (positive modalities)

# core.md claim-strength admissibility rows (canonical modalities per strength)
ROWS = {
    'deductive':     {'P'},
    'empirical':     {'T', 'W'},
    'differential':  {'T', 'P'},
    'observational': {'W'},
    'attested':      {'A'},
}

def all_partial_orders(elems):
    pairs = [(a, b) for a in elems for b in elems if a != b]
    n = len(pairs)
    for mask in range(2 ** n):
        rel = {(e, e) for e in elems}
        for i in range(n):
            if mask >> i & 1:
                rel.add(pairs[i])
        # antisymmetry
        if any((b, a) in rel for (a, b) in rel if a != b):
            continue
        # transitivity
        ok = True
        for (a, b) in rel:
            for (c, d) in rel:
                if b == c and (a, d) not in rel:
                    ok = False
                    break
            if not ok:
                break
        if ok:
            yield rel

def up(rel, t):
    return {m for m in M if (t, m) in rel}

total_found, principal_found, upset_found = [], [], []
count = 0
for rel in all_partial_orders(M):
    count += 1
    is_total = all((a, b) in rel or (b, a) in rel for a in M for b in M)
    # (1) principal-filter model: each row = up-set of one threshold modality
    principal_ok = all(any(up(rel, t) == row for t in M) for row in ROWS.values())
    # (2) arbitrary up-set model: each row upward-closed in rel
    upset_ok = all(all((a, b) not in rel or b in row for a in row for b in M)
                   for row in ROWS.values())
    if principal_ok:
        principal_found.append((rel, is_total))
    if upset_ok:
        upset_found.append((rel, is_total))
        if is_total:
            total_found.append(rel)

print(f"partial orders on 4 elements enumerated: {count}")
print(f"TOTAL orders reproducing rows even as arbitrary up-sets: {len(total_found)}")
print(f"partial orders reproducing rows as PRINCIPAL filters (threshold model): {len(principal_found)}")
print(f"partial orders where all rows are up-sets (arbitrary thresholds): {len(upset_found)}")
nontrivial = [r for (r, _) in upset_found if any(a != b for (a, b) in r)]
print(f"  ...of which non-discrete (order does any work): {len(nontrivial)}")
for r in nontrivial:
    print("   nontrivial surviving order:", sorted((a, b) for (a, b) in r if a != b))
