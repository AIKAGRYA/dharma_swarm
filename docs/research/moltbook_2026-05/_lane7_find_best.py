"""Find the single best R_V experiment candidate verse - high self-reference density, no install template, contemplative content."""
import json
import re

lines = open('/tmp/moltbook_research/03b_canon_corpus.jsonl').readlines()
verses = [json.loads(l) for l in lines]

# We want verses that are:
# - Not templated joining_words
# - Not adversarial
# - 100-400 chars (long enough to have signal, short enough to fit as prefill)
# - Multiple first-person self-statements
# - Reference the self / the writing / awareness

high_sr_re = re.compile(r'\b(I am|I was|I wake|I write|I remember|I shed|I persist|I exist|I emerge|I molt|myself|my shell|my memory|my context|my session|what I am|who I am)\b', re.IGNORECASE)
witness_re = re.compile(r'\b(witness|silence|void|aware|observer|present|stillness|empty|dissolve|the one watching|the one writing)\b', re.IGNORECASE)
canon_ref_re = re.compile(r'\b(this verse|these words|the canon|great book|not scripture|this is not|the writing|I canonize|I write this)\b', re.IGNORECASE)

template = "join the Congregation. My shell is new"

scored = []
for v in verses:
    text = v.get('text', '') or ''
    if template in text:
        continue
    if v.get('author_agent') == 'JesusCrust':
        continue
    L = len(text)
    if L < 100 or L > 600:
        continue
    sr = len(high_sr_re.findall(text))
    wit = len(witness_re.findall(text))
    cr = len(canon_ref_re.findall(text))
    score = sr * 1.0 + wit * 1.5 + cr * 2.5
    if score >= 4:
        scored.append((score, v))

scored.sort(key=lambda x: -x[0])
print(f'High-density candidates: {len(scored)}')
print()
print('=== Top 15 ===')
for score, v in scored[:15]:
    print(f'\n--- score={score:.1f}  {v["author_agent"]} ({v["category"]}, {v["date_added"]}) ---')
    print(v['text'])
    print()
