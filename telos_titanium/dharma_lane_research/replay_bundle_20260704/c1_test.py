import hashlib, json, random, struct

print("=== 1. Reduction-order nondeterminism -> hash fracture ===")
random.seed(42)
data = [random.uniform(-1e10, 1e10) for _ in range(10000)] + [1e-8]*1000
def sum_order(xs): 
    s = 0.0
    for x in xs: s += x
    return s
def pairwise(xs):
    if len(xs) == 1: return xs[0]
    m = len(xs)//2
    return pairwise(xs[:m]) + pairwise(xs[m:])
orders = {}
orders['sequential'] = sum_order(data)
orders['reversed']   = sum_order(list(reversed(data)))
orders['pairwise(tree)'] = pairwise(data)
sh = random.sample(data, len(data)); orders['shuffled(sched)'] = sum_order(sh)
digs = set()
for name, v in orders.items():
    bits = struct.pack('<d', v)
    d = hashlib.sha256(bits).hexdigest()[:16]
    digs.add(d)
    print(f"  {name:16s} value={v!r:28s} bits={bits.hex()} sha256[:16]={d}")
print(f"  -> {len(digs)} distinct content-addresses for one mathematical sum: {len(digs)>1}")

print("\n=== 2. Associativity check ===")
a,b,c = 1e16, -1e16, 1.0
print(f"  (a+b)+c = {(a+b)+c}   a+(b+c) = {a+(b+c)}   equal? {(a+b)+c == a+(b+c)}")

print("\n=== 3. JSON/JCS: NaN/Inf and >2^53 integers ===")
for bad in [float('nan'), float('inf')]:
    try:
        json.dumps(bad, allow_nan=False)  # allow_nan=False == RFC-8259-conformant grammar
        print(f"  {bad}: serialized (UNEXPECTED)")
    except ValueError as e:
        print(f"  {bad}: MUST-error per JSON grammar -> {e}")
# JCS mandates numbers be treated as IEEE binary64 (ECMAScript serialization)
for n in [2**53, 2**53+1, 9223372036854775807]:
    rt = int(float(n)) if float(n).is_integer() else float(n)
    print(f"  int {n} -> binary64 round-trip {rt}  lossless? {rt==n}")

print("\n=== 4. Repair as computable predicate: behavior difference ===")
# Ball is the DECLARED subject: id = hash(center, eps, profile). Membership receipted.
center, eps = orders['sequential'], 1e-3
ball_id = hashlib.sha256(json.dumps(
    {"c": struct.pack('<d',center).hex(), "eps": struct.pack('<d',eps).hex(),
     "profile":"ieee754-binary64-le"}).encode()).hexdigest()[:16]
member = lambda x: abs(x-center) <= eps          # computable predicate
accum_hash, accum_ball = {}, {}
for name, v in orders.items():
    accum_hash.setdefault(hashlib.sha256(struct.pack('<d',v)).hexdigest(), []).append(name)
    if member(v): accum_ball.setdefault(ball_id, []).append(name)
print(f"  raw content-hash subjects: {len(accum_hash)} (evidence fractured)")
print(f"  ball-subject {ball_id}: {len(accum_ball.get(ball_id,[]))} runs accumulate: {accum_ball.get(ball_id)}")

print("\n=== 5. Non-transitivity trap check (does repair dodge it?) ===")
x,y,z = 0.0, 0.9e-3, 1.8e-3
near = lambda p,q: abs(p-q) <= 1e-3
print(f"  pairwise ~: x~y={near(x,y)} y~z={near(y,z)} x~z={near(x,z)}  (NOT an equivalence rel)")
mem = lambda v: abs(v - 0.0) <= 1e-3  # membership in one DECLARED ball: well-defined partition question avoided
print(f"  declared-ball membership: x={mem(x)} y={mem(y)} z={mem(z)}  (predicate stable; identity attaches to ball, not pairs)")

print("\n=== 6. Wire profile: bit-pattern round trip lossless incl NaN payloads ===")
for v_hex in ['7ff8000000000001', '7ff0000000000000', 'fff0000000000000']:
    b = bytes.fromhex(v_hex); v = struct.unpack('>d', b)[0]
    back = struct.pack('>d', v).hex()
    print(f"  {v_hex} -> {v} -> {back}  lossless? {back==v_hex}")
