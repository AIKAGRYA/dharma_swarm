import hashlib, math

# Empirical RO test: template with hex hole for n-bit truncated SHA-256.
# Fixed point: trunc_hash(receipt bytes with h inserted) == h
n = 16
N = 1 << n
hexw = n // 4
templates = 300
have_fp, counts, first_fracs = 0, [], []
example = None
for t in range(templates):
    cnt, first = 0, None
    for h in range(N):
        hx = format(h, '0%dx' % hexw)
        r = b'receipt|template=%d|payload=jagat|hash=%s|' % (t, hx.encode())
        d = int.from_bytes(hashlib.sha256(r).digest()[:n//8], 'big')
        if d == h:
            cnt += 1
            if first is None: first = h
            if example is None: example = r
    counts.append(cnt)
    if cnt: have_fp += 1; first_fracs.append(first / N)
print(f'templates={templates} n={n}bit')
print(f'fraction with >=1 fixed point: {have_fp/templates:.3f}  (predicted 1-1/e = {1-math.exp(-1):.3f})')
print(f'mean fixed points/template: {sum(counts)/templates:.3f}  (predicted 1.000)')
print(f'mean first-hit fraction of search space: {sum(first_fracs)/len(first_fracs):.3f}  (predicted (e-2)/(e-1) = {(math.e-2)/(math.e-1):.3f})')
print('example self-hash-containing receipt (16-bit trunc):', example)
d = hashlib.sha256(example).digest()[:2].hex()
print('verify: trunc digest =', d, '| contained:', d.encode() in example)
