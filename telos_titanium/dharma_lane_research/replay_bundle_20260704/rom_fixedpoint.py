import hashlib, random, math

# Random oracle model at small scale: n-bit truncated SHA-256.
# Template T with one n-bit hole; body(h) = T || hex(h). Fixed point: H_n(body(h)) == h.
n = 16
N = 1 << n
def Hn(data: bytes) -> int:
    return int.from_bytes(hashlib.sha256(data).digest()[:4], 'big') % N

trials = 2000
have_fp = 0
scan_fracs = []  # fraction of space scanned (random order) until first fixed point, given exists
rng = random.Random(7)
for t in range(trials):
    template = f"receipt template #{t}: id=".encode()
    fps = [h for h in range(N) if Hn(template + format(h, '04x').encode()) == h]
    if fps:
        have_fp += 1
        # expected position of first hit under random scan ~ N * 1/(K+1)
        k = len(fps)
        scan_fracs.append(1.0/(k+1))

p_emp = have_fp/trials
print(f"P(>=1 fixed point) empirical = {p_emp:.4f}   theory 1-1/e = {1-1/math.e:.4f}")
print(f"E[scan fraction | exists] empirical = {sum(scan_fracs)/len(scan_fracs):.4f}   theory (e-2)/(e-1) = {(math.e-2)/(math.e-1):.4f}")
# (e-2)/(e-1) ~ 0.418 => ~0.418 * 2^256 ~ 2^254.7 ~ "2^255 expected search". 
print(f"log2(0.418 * 2^256) = {256 + math.log2((math.e-2)/(math.e-1)):.1f}")

# Exclusion-based derivation degenerates to assignment: H(f(x)) constant in x
template2 = b"body-without-id-and-sigs"
vals = {Hn(template2) for _ in range(5)}
print(f"exclusion: H(body minus id) is constant, |values|={len(vals)} -> x := c (assignment, no fixed-point search)")
