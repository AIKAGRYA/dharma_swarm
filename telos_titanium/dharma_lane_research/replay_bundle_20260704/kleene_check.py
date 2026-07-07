import hashlib

# (a) Byte-level quine: syntactic self-reference IS achievable (Kleene SRT construction).
q = 's = %r\nprint(s %% s)'
quine_src = q % q
import io, contextlib
buf = io.StringIO()
with contextlib.redirect_stdout(buf):
    exec(quine_src)
print("quine reproduces own bytes exactly:", buf.getvalue() == quine_src)

# So a receipt CAN quote its own full text / rules-template (the claim's quine-at-rules-level).
# But: can text contain its own HASH literally? Only via ROM fixed point.

# (b) Small-scale: find a receipt containing its own 16-bit truncated hash -> feasible, exists w.p. ~0.63
def h16(b): return hashlib.sha256(b).digest()[:2].hex()
found = None
for t in range(20):  # try a few templates; each has ~63% chance
    for x in range(1 << 16):
        cand = f"RECEIPT v{t} self_hash={x:04x} END".encode()
        if h16(cand) == f"{x:04x}":
            found = cand; break
    if found: break
print("16-bit self-hash receipt found:", found)
print("verify:", h16(found) == found.decode().split('self_hash=')[1][:4] if found else "n/a")
# (c) Full SHA-256 version = 2^256 candidate space; same construction, infeasible search.
