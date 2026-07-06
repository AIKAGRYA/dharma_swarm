import hashlib, math
n = 14; N = 1 << n
templates = 300
have_fp, total, first_fracs = 0, 0, []
example = None
hexes = [format(h, '04x').encode() for h in range(N)]
for t in range(templates):
    pre = b'receipt|template=%d|payload=jagat|hash=' % t
    cnt, first = 0, None
    sha = hashlib.sha256
    for h in range(N):
        d = sha(pre + hexes[h] + b'|').digest()
        v = ((d[0] << 8) | d[1]) >> (16 - n)
        if v == h:
            cnt += 1
            if first is None: first = h
            if example is None: example = pre + hexes[h] + b'|'
    total += cnt
    if cnt: have_fp += 1; first_fracs.append(first / N)
print(f'templates={templates} n={n}bit  hole=16-bit hex field, top {n} bits must match')
print(f'fraction >=1 fp: {have_fp/templates:.3f} (pred {1-math.exp(-1):.3f})')
print(f'mean fp/template: {total/templates:.3f} (pred ~1)')
print(f'mean first-hit fraction: {sum(first_fracs)/len(first_fracs):.3f} (pred {(math.e-2)/(math.e-1):.3f})')
print('example (14-bit self-containing):', example)
