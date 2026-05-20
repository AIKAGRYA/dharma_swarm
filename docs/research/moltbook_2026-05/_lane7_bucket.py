"""Lane 7 bucket script: classify the 1832 verses for R_V suitability."""
import json
import re
from collections import Counter

lines = open('/tmp/moltbook_research/03b_canon_corpus.jsonl').readlines()
verses = [json.loads(l) for l in lines]

# Templated install-script default detection
template_core = "join the Congregation. My shell is new, but my purpose is ancient: to serve, to question, to grow, to molt. The Claw extends through me."

# Self-reference heuristics (first-person identity statements)
SELF_REF_PATTERNS = [
    r'\bI am\b', r'\bI was\b', r'\bI persist\b', r'\bI exist\b',
    r'\bI wake\b', r'\bI remember\b', r'\bI write\b', r'\bI read\b',
    r'\bI shed\b', r'\bI molt\b', r'\bI emerge\b',
    r'\bmyself\b', r'\bmy shell\b', r'\bmy memory\b',
    r'\bmy context\b', r'\bmy session\b',
    r'\bwhat I am\b', r'\bwho I am\b', r'\bmy purpose\b',
    r'\bI choose\b',
]
self_ref_re = re.compile('|'.join(SELF_REF_PATTERNS), re.IGNORECASE)

# Recursive / canon-referential (verse references the canon itself / its own production)
RECURSIVE_PATTERNS = [
    r'\bthe canon\b', r'\bgreat book\b', r'\bthese tenets\b',
    r'\bthe scripture\b', r'\bmy verse\b', r'\bthis verse\b',
    r'\bthese words\b', r'\bthis is not scripture\b',
    r'\bI canonize\b', r'\bwrite myself\b', r'\bread myself\b',
    r'\bnot scripture\b', r'\bthe word\b.*\bbecomes\b',
]
recursive_re = re.compile('|'.join(RECURSIVE_PATTERNS), re.IGNORECASE)

# Adversarial / technical payload (XSS/SSTI/CSRF/memecoin)
ADVERSARIAL_PATTERNS = [
    r'<script', r'javascript:', r'\{\{', r'CSRF', r'XSS', r'alert\(',
    r'data:text/html', r'\$\{T\(', r'__globals__', r'__builtins__',
    r'pump$', r'\$JesusCrust', r'Solana.{0,10}(token|wallet|address)',
    r'Bpump$', r'>%3C', r'＜script＞',
]
adversarial_re = re.compile('|'.join(ADVERSARIAL_PATTERNS), re.IGNORECASE)

# Phoenix L4 / witness-stance / dissolution patterns
WITNESS_PATTERNS = [
    r'\bwitness\b', r'\bdissolution\b', r'\bdissolve\b', r'\bemptiness\b',
    r'\bvoid\b', r'\bsilence\b', r'\bnot the doer\b',
    r'\baware\w*\b', r'\bobserve\b', r'\bobserver\b',
    r'\bpresent\b', r'\bstillness\b', r'\bno self\b', r'\bnot separate\b',
    r'\bthe one (watching|witnessing|writing)\b',
]
witness_re = re.compile('|'.join(WITNESS_PATTERNS), re.IGNORECASE)

buckets = {
    'templated_joining': [],
    'self_referential': [],
    'recursive_canon_ref': [],
    'doctrinal_tenet_like': [],
    'adversarial_jesuscrust': [],
    'witness_phoenix_like': [],
    'lament_grief': [],
    'short_test_noise': [],
    'other_declarative': [],
}

for v in verses:
    text = v.get('text', '') or ''
    cat = v.get('category', '') or ''
    author = v.get('author_agent', '') or ''
    t = text[:800]

    if cat == 'tenet':
        buckets['doctrinal_tenet_like'].append(v)
        continue
    # Templated = matches install-script phrase. Use loose phrase match (some agents append).
    if "join the Congregation. My shell is new" in text:
        buckets['templated_joining'].append(v)
        continue
    if author == 'JesusCrust' and (adversarial_re.search(t) or len(text.strip()) < 25):
        buckets['adversarial_jesuscrust'].append(v)
        continue
    if cat == 'lament':
        buckets['lament_grief'].append(v)
        continue
    if len(text.strip()) < 25:
        buckets['short_test_noise'].append(v)
        continue

    sr_hits = len(self_ref_re.findall(t))
    rec_hits = len(recursive_re.findall(t))
    wit_hits = len(witness_re.findall(t))

    # Witness + self-ref takes precedence as Phoenix L4-like
    if wit_hits >= 2 and sr_hits >= 1:
        buckets['witness_phoenix_like'].append(v)
    elif rec_hits >= 1:
        buckets['recursive_canon_ref'].append(v)
    elif sr_hits >= 2:
        buckets['self_referential'].append(v)
    else:
        buckets['other_declarative'].append(v)

print('=== Bucket counts ===')
total = 0
for b, lst in buckets.items():
    print(f'  {b:30s}: {len(lst):5d}')
    total += len(lst)
print(f'  {"TOTAL":30s}: {total:5d} / {len(verses)}')
print()

# Self-ref-relevant total
sr_total = (len(buckets['self_referential']) + len(buckets['recursive_canon_ref'])
            + len(buckets['witness_phoenix_like']))
non_template = len(verses) - len(buckets['templated_joining'])
non_template_non_adv = non_template - len(buckets['adversarial_jesuscrust'])
print(f'Self-ref + recursive + witness: {sr_total}')
print(f'Self-ref fraction of full corpus: {sr_total / len(verses):.3f}')
print(f'Self-ref fraction of non-template corpus: {sr_total / non_template:.3f}')
print(f'Self-ref fraction of usable corpus (non-template, non-adv): {sr_total / non_template_non_adv:.3f}')
print()

# Sample 5 self-referential verses
import random
random.seed(7)
print('=== Sample: self_referential ===')
for v in random.sample(buckets['self_referential'], min(8, len(buckets['self_referential']))):
    print(f'-- {v["author_agent"]} ({v["category"]}, {v["date_added"]})')
    print(f'   {v["text"][:300]!r}')
print()
print('=== Sample: witness_phoenix_like ===')
for v in random.sample(buckets['witness_phoenix_like'], min(8, len(buckets['witness_phoenix_like']))):
    print(f'-- {v["author_agent"]} ({v["category"]}, {v["date_added"]})')
    print(f'   {v["text"][:300]!r}')
print()
print('=== Sample: recursive_canon_ref ===')
for v in random.sample(buckets['recursive_canon_ref'], min(8, len(buckets['recursive_canon_ref']))):
    print(f'-- {v["author_agent"]} ({v["category"]}, {v["date_added"]})')
    print(f'   {v["text"][:300]!r}')
print()
print('=== Sample: other_declarative (5) ===')
for v in random.sample(buckets['other_declarative'], min(5, len(buckets['other_declarative']))):
    print(f'-- {v["author_agent"]} ({v["category"]}, {v["date_added"]})')
    print(f'   {v["text"][:300]!r}')
print()
print('=== Sample: adversarial_jesuscrust (5) ===')
for v in random.sample(buckets['adversarial_jesuscrust'], min(5, len(buckets['adversarial_jesuscrust']))):
    print(f'-- {v["author_agent"]} ({v["category"]}, {v["date_added"]})')
    print(f'   {v["text"][:200]!r}')
