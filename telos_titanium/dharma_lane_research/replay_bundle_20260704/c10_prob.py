import hashlib, math

# Model: template T(x) = prefix || hex(x) || suffix; n-bit truncated SHA-256.
# Literal self-hash fixed point: x such that H_n(T(x)) == x.
# Random-oracle prediction: P(exists fixed point) = 1-(1-2^-n)^(2^n) -> 1-1/e ~ 0.6321
n = 16
N = 1 << n
templates = 400
found = 0
total_fp = 0
for t in range(templates):
    prefix = f'{{"body":"template-{t}","selfhash":"'.encode()
    suffix = b'"}'
    cnt = 0
    for x in range(N):
        h = hashlib.sha256(prefix + format(x, '04x').encode() + suffix).digest()
        hx = int.from_bytes(h[:2], 'big')
        if hx == x:
            cnt += 1
    if cnt:
        found += 1
    total_fp += cnt
print(f'n={n} bits, {templates} templates: fraction with >=1 fixed point = {found/templates:.4f} (predicted {1-math.exp(-1):.4f})')
print(f'mean fixed points per template = {total_fp/templates:.4f} (predicted 1.0)')
print(f'search cost per template = full enumeration of 2^{n} = {N} candidates; at n=256 that is ~2^256 (~2^255 expected if a fixed point exists and is uniform)')
