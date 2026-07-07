import json, hashlib, math, random

def jcs(obj):
    # RFC 8785 subset sufficient here: sorted keys, no whitespace, ensure_ascii=False
    return json.dumps(obj, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()

R = json.load(open('/Users/dhyana/dharma_swarm/telos_titanium/dharma_lane_research/ucl_genesis_receipt_bc5ae73f.json'))

# 1. receipt_id predicate: sha256(JCS(receipt - {receipt_id, signatures}))
body = {k: v for k, v in R.items() if k not in ('receipt_id', 'signatures')}
rid = 'sha256:' + hashlib.sha256(jcs(body)).hexdigest()
print('receipt_id recomputed :', rid)
print('receipt_id in file    :', R['receipt_id'], '=> MATCH' if rid == R['receipt_id'] else '=> MISMATCH')

# 2. Behavior difference: mutate one byte of body -> predicate must flip
body2 = dict(body); body2['schema_version'] = body2['schema_version'] + 'x'
rid2 = 'sha256:' + hashlib.sha256(jcs(body2)).hexdigest()
print('tamper flips predicate:', rid2 != R['receipt_id'])

# 3. claim_hash: spec says JCS canonical claim object over claim_id, claim_class,
# claim_strength, statement, scope, fragment_id (+obligation_hash when present)
c = R['claim']
claim_obj = {k: c[k] for k in ('claim_id','claim_class','claim_strength','statement','scope','fragment_id') if k in c}
ch = 'sha256:' + hashlib.sha256(jcs(claim_obj)).hexdigest()
print('claim_hash recomputed :', ch, '=> MATCH' if ch == R['claim_hash'] else '=> MISMATCH vs ' + R['claim_hash'])
# try full claim object as-is
ch2 = 'sha256:' + hashlib.sha256(jcs(c)).hexdigest()
print('claim_hash (full obj) :', ch2, '=> MATCH' if ch2 == R['claim_hash'] else '=> no')

# 4. authority_key = sha256 of JCS {subject_id, claim_hash, trust_base_id, fragment_id, fragment_version}
ak_obj = {'subject_id': R['subject']['subject_id'], 'claim_hash': R['claim_hash'],
          'trust_base_id': R['authority']['trust_base_id'], 'fragment_id': R['authority']['fragment_id'],
          'fragment_version': R['authority']['fragment_version']}
ak = 'sha256:' + hashlib.sha256(jcs(ak_obj)).hexdigest()
print('authority_key recomp  :', ak, '=> MATCH' if ak == R['challenge_base']['authority_key'] else '=> MISMATCH vs ' + R['challenge_base']['authority_key'])

# 5. base_snapshot_hash of empty object? sha256 of '{}'
print('sha256("{}")          :', hashlib.sha256(b'{}').hexdigest(), 'vs', R['challenge_base']['base_snapshot_hash'])

# 6. subject_id: subject has kind=receipt_self, subject_id given. Spec: subject_id = sha256 of JCS of admitted selector fields (no content_hash present)
s = R['subject']
for candidate in [{'kind': s['kind']}, {'kind':'receipt_self'},]:
    sid = 'sha256:' + hashlib.sha256(jcs(candidate)).hexdigest()
    print('subject_id try', candidate, '->', sid, 'MATCH' if sid == s['subject_id'] else '')
